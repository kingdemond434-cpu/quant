"""Where the regime will be when the book is actually held, not where it is when it is chosen.

WHAT WAS ALREADY HERE AND UNUSED. `GaussianHMM` estimates a full transition matrix by
Baum-Welch and has done since it was written. Nothing has ever read it. `pf_allocator` takes the
filtered posterior -- P(Z_t | data) -- tempers it, and hands it to `sample_worlds` as the regime
mix to draw scenarios from. So the desk sizes a book it will hold for days against the regime it
is in at the instant of the solve, and the matrix that says how long that will last sits in the
fitted object, unread.

That is a real error and not a refinement. An edge can be excellent inside a trend and terrible
around its termination; a book sized on "58% trend now" is sized wrong if the honest statement is
"58% trend now, 71% chance of leaving it before this book is closed".

    P(Z_t = k | D_t)          ->        P(Z_{t+h} = j | Z_t, age_t)

WHY A PLAIN MARKOV POWER IS NOT ENOUGH. transmat^h assumes persistence is memoryless: a trend two
bars old and a trend seventy bars old are given the same chance of surviving the next bar. Markets
are not usually like that, and the distinction between a young, a mature and an exhausted regime
is exactly the one this desk keeps trying to capture elsewhere. So the survival probability is
taken from the EMPIRICAL HAZARD BY AGE -- how often a run of this state that reached age d ended
at d -- and the chain is used only for WHERE it goes once it leaves. That factorisation (duration
says when, chain says where) is the standard hidden semi-Markov approximation.

FAILS CLOSED TO MEMORYLESS. The age-conditioned hazard is shrunk toward the chain's own
`1 - transmat[i,i]` by the number of runs still at risk at that age, with the same
`n / (n + k)` weight the rest of this desk uses for every other thin estimate. At an age only
three runs ever reached, the estimate IS the memoryless one. A duration model that confidently
extrapolates from four observations is worse than no duration model, because it is wrong in a
direction nobody can see.

WHAT THIS DELIBERATELY DOES NOT DO. It does not decide anything. It returns a distribution. The
consumer -- `sample_worlds` -- draws its scenario population from that distribution, and the
E[log W] solve then sizes against a world population that is automatically wider when a
transition is likely. Regime uncertainty therefore reduces exposure THROUGH THE OBJECTIVE rather
than through a hand-set haircut, which is the only version of it the desk can defend.

CLOCK-AGNOSTIC ON PURPOSE. Horizons are in BARS of whatever series the HMM was fitted on. Fitted
on daily closes, h=1 is tomorrow; fitted on H1, h=4 is four hours. The allocator's evidence is
daily sleeve returns so it passes a daily fit; an intraday consumer can pass an H1 fit to the
same code without a second implementation of any of this.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

#: Runs-at-risk needed at an age before the empirical hazard there is trusted over the chain's
#: memoryless rate. The same shrinkage constant idiom as `robust_elog._posterior_mu`.
HAZARD_K = 20.0
#: Ages beyond this are lumped into the last bucket. A regime that has persisted longer than any
#: run in the record is extrapolation, and the chain's flat rate is the honest answer there.
MAX_AGE = 400


@dataclass(frozen=True)
class TransitionForecast:
    """The regime term structure: where the state is now, and where it is likely to be later."""

    labels: tuple[str, ...]
    #: P(label) now -- the input posterior, summed onto labels.
    p_now: dict[str, float]
    #: Bars the most likely current state has persisted, from the fitted path.
    age_bars: int
    horizons: tuple[int, ...]
    #: h -> P(label) at t+h.
    p_ahead: dict[int, dict[str, float]]
    #: h -> P(the CURRENT label no longer holds at t+h).
    p_leave: dict[int, float]
    #: h -> normalised Shannon entropy of `p_ahead[h]`, in [0, 1]. 0 is certainty, 1 is
    #: "every regime equally likely". Reported, never applied as a multiplier: the widening of
    #: the world population IS the risk response.
    entropy: dict[int, float]
    #: How far the duration model was trusted over the memoryless chain, in [0, 1]. Zero means
    #: the record was too thin to say anything the chain did not already say.
    duration_weight: float
    #: Completed run lengths per label, so the age claim can be checked rather than believed.
    run_lengths: dict[str, list[int]] = field(default_factory=dict)
    note: str = ""

    def probs_at(self, h: int) -> tuple[tuple[str, float], ...]:
        """The `regime_probs` contract `WorldConfig` consumes, for horizon `h`."""
        d = self.p_ahead.get(int(h)) or self.p_now
        return tuple(sorted(d.items()))


def _runs(path: np.ndarray) -> tuple[dict[int, list[int]], int, int]:
    """Completed run lengths per state, plus the current state and how long it has run."""
    path = np.asarray(path).astype(int).ravel()
    if path.size == 0:
        return {}, -1, 0
    out: dict[int, list[int]] = {}
    start = 0
    for t in range(1, path.size):
        if path[t] != path[t - 1]:
            out.setdefault(int(path[start]), []).append(t - start)
            start = t
    return out, int(path[-1]), int(path.size - start)


def age_hazard(path: np.ndarray, k_states: int, transmat: np.ndarray,
               hazard_k: float = HAZARD_K, max_age: int = MAX_AGE) -> np.ndarray:
    """h[i, d] = P(a run of state i that reached age d ends at d), shrunk toward the chain.

    The current (censored) run counts in the at-risk denominator and never in the numerator: it
    has not ended, and scoring it as an ending would bias every hazard upward exactly when a
    regime is unusually long-lived, which is when the answer matters most.
    """
    runs, cur, cur_age = _runs(path)
    memoryless = np.clip(1.0 - np.diag(np.asarray(transmat, dtype=float)), 1e-6, 1.0 - 1e-6)
    out = np.repeat(memoryless[:, None], max_age + 1, axis=1)
    for i in range(k_states):
        lengths = np.asarray(runs.get(i, ()), dtype=int)
        if lengths.size == 0 and not (i == cur and cur_age > 0):
            continue
        for d in range(1, max_age + 1):
            at_risk = int((lengths >= d).sum()) + (1 if i == cur and cur_age >= d else 0)
            if at_risk <= 0:
                break
            ended = int((lengths == d).sum())
            emp = ended / at_risk
            lam = at_risk / (at_risk + hazard_k)
            out[i, d] = lam * emp + (1.0 - lam) * memoryless[i]
    return np.clip(out, 1e-6, 1.0 - 1e-6)


def _step_matrices(transmat: np.ndarray) -> np.ndarray:
    """Where a run goes GIVEN that it ends: the off-diagonal row, renormalised.

    The duration model owns the timing, so the chain is asked only the destination question. A
    state whose fitted row is pure self-transition has no opinion, and the mass is spread evenly
    rather than invented.
    """
    A = np.asarray(transmat, dtype=float).copy()
    k = A.shape[0]
    np.fill_diagonal(A, 0.0)
    rows = A.sum(axis=1)
    for i in range(k):
        if rows[i] <= 0:
            A[i] = 1.0 / max(1, k - 1)
            A[i, i] = 0.0
        else:
            A[i] /= rows[i]
    return A


def forecast(transmat: np.ndarray, posterior: np.ndarray, state_labels: dict[int, str],
             path: np.ndarray, horizons: tuple[int, ...] = (1, 2, 5),
             hazard_k: float = HAZARD_K, max_age: int = MAX_AGE) -> TransitionForecast:
    """Propagate (state, age) forward and report the label distribution at each horizon.

    The recursion is exact on the (state, age) product space -- no closed form is assumed and no
    matrix power is taken -- because the whole point is that the process is NOT memoryless.

    THE ONE APPROXIMATION, STATED. Age is observed only for the path's current run. States the
    posterior gives weight to but the path is not in are entered at age 0, which is the least
    informative assumption available and errs toward the memoryless rate rather than toward any
    particular duration claim.
    """
    A = np.asarray(transmat, dtype=float)
    k = A.shape[0]
    p0 = np.asarray(posterior, dtype=float).ravel()
    if p0.size != k or not np.isfinite(p0).all() or p0.sum() <= 0:
        raise ValueError(f"posterior of size {p0.size} for a {k}-state chain")
    p0 = p0 / p0.sum()

    runs, cur, cur_age = _runs(path)
    haz = age_hazard(path, k, A, hazard_k=hazard_k, max_age=max_age)
    dest = _step_matrices(A)

    n_runs = sum(len(v) for v in runs.values())
    duration_weight = float(n_runs / (n_runs + hazard_k)) if n_runs else 0.0

    # (state, age) mass. Age is capped at max_age; the last bucket absorbs, which is where the
    # hazard has already fallen back to the chain's flat rate anyway.
    m = np.zeros((k, max_age + 1))
    for i in range(k):
        age = min(cur_age, max_age) if i == cur else 0
        m[i, age] += p0[i]

    labels = tuple(sorted({str(v) for v in state_labels.values()}))

    def _onto_labels(mass: np.ndarray) -> dict[str, float]:
        out = dict.fromkeys(labels, 0.0)
        by_state = mass.sum(axis=1)
        for i in range(k):
            out[str(state_labels.get(i, str(i)))] = (
                out.get(str(state_labels.get(i, str(i))), 0.0) + float(by_state[i]))
        total = sum(out.values()) or 1.0
        return {lab: v / total for lab, v in out.items()}

    p_now = _onto_labels(m)
    # "The current label" is the one the BELIEF names, not the one the decoded path happens to
    # end on. The two agree whenever both come from the same fitted engine, which is the only way
    # this is called in production; when a caller passes a posterior that disagrees with the path,
    # `p_leave` must still answer the question that was asked -- how likely is the regime the desk
    # thinks it is in to still hold -- rather than silently answering about a different state.
    cur_label = max(p_now, key=lambda lab: p_now[lab]) if p_now else ""

    p_ahead: dict[int, dict[str, float]] = {}
    p_leave: dict[int, float] = {}
    entropy: dict[int, float] = {}
    want = sorted({int(h) for h in horizons if int(h) > 0})
    steps = max(want) if want else 0
    for step in range(1, steps + 1):
        nxt = np.zeros_like(m)
        for i in range(k):
            ages = np.flatnonzero(m[i] > 0.0)
            if ages.size == 0:
                continue
            mass = m[i, ages]
            leave = haz[i, np.minimum(ages + 1, max_age)]
            stay_age = np.minimum(ages + 1, max_age)
            np.add.at(nxt[i], stay_age, mass * (1.0 - leave))
            # A run that ends restarts its destination's clock at age 0, which is the whole
            # reason the age dimension exists.
            nxt[:, 0] += dest[i] * float((mass * leave).sum())
        m = nxt
        if step in want:
            d = _onto_labels(m)
            p_ahead[step] = d
            p_leave[step] = float(1.0 - d.get(cur_label, 0.0)) if cur_label else float("nan")
            vals = [v for v in d.values() if v > 0]
            h_max = math.log(len(labels)) if len(labels) > 1 else 1.0
            entropy[step] = float(-sum(v * math.log(v) for v in vals) / h_max)

    return TransitionForecast(
        labels=labels, p_now=p_now, age_bars=int(cur_age), horizons=tuple(want),
        p_ahead=p_ahead, p_leave=p_leave, entropy=entropy,
        duration_weight=duration_weight,
        run_lengths={str(state_labels.get(i, str(i))): sorted(v) for i, v in sorted(runs.items())},
        note=(f"{n_runs} completed runs; duration weight {duration_weight:.2f}"
              if n_runs else "no completed runs: memoryless chain only"),
    )
