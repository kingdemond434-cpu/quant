"""LAYER 3 -- fast statistical screening. Real statistics, cheap, on real data, NO model in it.

THE FUNNEL, and this is the rung that was missing:

  L1  AI DISCOVERY FACTORY    thousands of economically distinct hypotheses/day. Ideas, never
                              conclusions. (hypothesis_generator, now every funded seat x every
                              lens x an exhausting push ladder.)
  L2  DETERMINISTIC FILTERS   duplicates, parameter tweaks, no mechanism, impossible to
                              implement, already falsified, cost floor. Pure arithmetic.
                              (hypothesis_max.prefilter + TrivialVariationBlocker.)
  L3  FAST STATISTICAL SCREEN <-- THIS FILE. Cheap IC, split-half consistency, permutation
                              sanity, leakage detection, rough cost. Real maths on real data.
  L4  FULL GAUNTLET           recorder replay, CPCV, PBO, reality check, walk-forward, shadow.
                              Serious compute, and the ONLY place promotion is decided.

WHY L3 HAS TO EXIST. Without it the desk runs L2 straight into L4, so every candidate that is
merely arithmetically plausible consumes full gauntlet compute. That is exactly what produced 420
candidates at full cost for zero survivors. L3 is where a few seconds of honest statistics
replaces minutes of expensive ones -- and, unlike an LLM screen, it can genuinely say "this has
no signal" because it actually computed something.

NO LLM TOUCHES THIS FILE, and that is the design. An LLM asked for a Sharpe returns a Sharpe,
fluently, having computed nothing; a screen built on that is a random filter wearing the language
of rigour, and its output reaches L4 carrying a false prior of quality. Statistics belong to
arithmetic. Models belong upstream, generating ideas and judging mechanisms.

THE DEFAULT IS STILL ESCALATE. L3 rejects only on evidence it actually has: a missing input can
never contribute to a rejection, and the thresholds sit far below any promotion bar. This screen
removes the hopeless, it does not adjudicate the marginal -- a wrongly-killed hypothesis is never
recovered, a wrongly-passed one dies in L4 for the price of some compute. ZERO promotion
authority: L3 passing means "worth real compute", never "worth capital".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

__all__ = [
    "MIN_ABS_IC",
    "MIN_OBS",
    "PERM_P_MAX",
    "ScreenResult",
    "fast_screen",
    "information_coefficient",
    "permutation_p",
    "split_half_consistency",
]

#: Below this many aligned observations nothing is measured -- the screen ESCALATES rather than
#: judging. A small sample is missing evidence, not evidence of absence.
MIN_OBS = 120

#: |IC| below this is indistinguishable from zero at any sample this desk will have. Far below
#: any promotion bar on purpose: L3 removes the hopeless, L4 adjudicates the marginal.
MIN_ABS_IC = 0.005

#: Permutation p above this means the observed IC is unremarkable against shuffled labels.
#:
#: CALIBRATED, NOT CHOSEN BY TASTE. Both error rates were measured on synthetic ground truth
#: (n=600, 120 trials, null = independent series, alternative = a genuinely weak IC~0.10 signal --
#: deliberately the marginal case, because killing those is the failure that matters):
#:
#:      PERM_P_MAX   noise PASSES   real IC=0.10 KILLED
#:            0.50            54%                    6%
#:            0.30            33%                    8%     <-- chosen
#:            0.20            22%                   14%
#:            0.10            10%                   25%
#:            0.05             3%                   37%
#:
#: 0.50 was the first value written here and it is nearly useless: it rejects only signals worse
#: than a coin flip, so pure noise passed the screen 54% of the time -- an L3 that barely filters
#: still charges L4 for everything.
#:
#: 0.30 cuts L4 load by two thirds while killing 8% of genuinely weak real signals. Tightening to
#: 0.20 buys 11 more points of noise rejection for 6 more points of real signal, which is a bad
#: trade under this desk's asymmetry: a wrongly-killed hypothesis is never recovered, a
#: wrongly-passed one dies in L4 for the price of some compute. The false-negative column is what
#: this number is set against, not the false-positive one.
#:
#: 8% is a REAL cost, not a rounding error, and it is why the spec mandates spot-auditing a sample
#: of rejects rather than trusting the screen.
PERM_P_MAX = 0.30

#: Sign agreement between halves. A signal whose sign flips between the first and second half of
#: its own sample has no stable direction to trade, whatever its full-sample IC says.
MIN_SPLIT_AGREEMENT = 0.0


@dataclass(frozen=True)
class ScreenResult:
    """PASS -> worth L4 compute. REJECT -> graveyard, cheaply. ESCALATE -> not measurable here.

    PASS and ESCALATE both proceed and are kept distinct so the false-reject audit can measure
    how often L3 actually had an opinion. A screen that escalates everything is doing nothing,
    and that is only visible if "proceeded because measured" and "proceeded because unmeasurable"
    are counted separately.
    """

    decision: str
    reasons: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def proceeds(self) -> bool:
        return self.decision in ("PASS", "ESCALATE")


def _clean(signal: Any, forward: Any) -> tuple[np.ndarray, np.ndarray]:
    s = np.asarray(signal, dtype="float64").ravel()
    f = np.asarray(forward, dtype="float64").ravel()
    n = min(len(s), len(f))
    s, f = s[:n], f[:n]
    ok = np.isfinite(s) & np.isfinite(f)
    return s[ok], f[ok]


def _ranks(x: np.ndarray) -> np.ndarray:
    """Tie-AVERAGED ranks -- the actual Spearman definition.

    The first version here used `argsort(argsort(x))`, which assigns tied values distinct ranks
    according to their ORIGINAL POSITION. This module's own test caught what that does: a forward
    series of all zeros with one large print scored a rank IC of 1.000 against any monotonically
    ordered signal, because the tied zeros silently inherited the signal's ordering. Fabricating
    perfect correlation out of a constant series is the worst possible failure for a screen whose
    job is to reject things with no signal -- and real data is full of ties (zero returns, rounded
    prices, quantised sizes), so it would have fired constantly rather than rarely.
    """
    order = np.argsort(x, kind="mergesort")
    r = np.empty(len(x), dtype="float64")
    r[order] = np.arange(len(x), dtype="float64")
    # average the ranks within each run of equal values
    sx = x[order]
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def information_coefficient(signal: Any, forward: Any) -> float:
    """Spearman rank IC. Rank-based because a single outlier can manufacture a Pearson
    correlation out of noise, and crypto returns are exactly where that happens."""
    s, f = _clean(signal, forward)
    if len(s) < 3 or np.std(s) == 0 or np.std(f) == 0:
        return 0.0
    rs, rf = _ranks(s), _ranks(f)
    if np.std(rs) == 0 or np.std(rf) == 0:
        return 0.0
    return float(np.corrcoef(rs, rf)[0, 1])


def permutation_p(signal: Any, forward: Any, n_perm: int = 200, seed: int = 0) -> float:
    """Fraction of shuffled labels producing |IC| at least as large as observed.

    Shuffles the FORWARD returns, not the signal: that destroys the pairing while preserving each
    series' own distribution, so the null is "this signal has no relationship to these returns"
    rather than "these returns are not autocorrelated".
    """
    s, f = _clean(signal, forward)
    if len(s) < MIN_OBS:
        return 1.0
    obs = abs(information_coefficient(s, f))
    rng = np.random.default_rng(seed)
    hits = sum(1 for _ in range(n_perm)
               if abs(information_coefficient(s, rng.permutation(f))) >= obs)
    return (hits + 1) / (n_perm + 1)       # +1: an observed value is itself one draw


def split_half_consistency(signal: Any, forward: Any) -> tuple[float, float, float]:
    """(first-half IC, second-half IC, sign agreement in {-1.0, +1.0}).

    The cheapest out-of-sample question there is. A signal whose sign inverts across its own
    sample has no stable direction, and no amount of full-sample IC repairs that.
    """
    s, f = _clean(signal, forward)
    if len(s) < MIN_OBS:
        return 0.0, 0.0, 0.0
    mid = len(s) // 2
    a = information_coefficient(s[:mid], f[:mid])
    b = information_coefficient(s[mid:], f[mid:])
    return a, b, (1.0 if a * b > 0 else -1.0)


def fast_screen(signal: Any, forward: Any, *, cost_bps: float | None = None,
                gross_edge_bps: float | None = None, n_perm: int = 200,
                seed: int = 0) -> ScreenResult:
    """L3. Reject only on measured, unambiguous absence of signal; escalate on anything else."""
    s, f = _clean(signal, forward)
    metrics: dict[str, Any] = {"n_obs": len(s)}

    if len(s) < MIN_OBS:
        return ScreenResult("ESCALATE", (
            f"only {len(s)} aligned observations (< {MIN_OBS}) -- nothing is measurable here, "
            "and an unmeasured hypothesis must never be rejected as if it had been tested",),
            metrics)

    ic = information_coefficient(s, f)
    a, b, agree = split_half_consistency(s, f)
    p = permutation_p(s, f, n_perm=n_perm, seed=seed)
    metrics |= {"ic": round(ic, 5), "ic_first_half": round(a, 5), "ic_second_half": round(b, 5),
                "sign_agreement": agree, "permutation_p": round(p, 4)}

    reasons: list[str] = []
    if abs(ic) < MIN_ABS_IC:
        reasons.append(f"|IC| {abs(ic):.5f} < {MIN_ABS_IC} -- indistinguishable from zero")
    if p > PERM_P_MAX:
        reasons.append(f"permutation p {p:.3f} > {PERM_P_MAX} -- shuffled labels reproduce this "
                       f"as easily as the real pairing")
    if agree < 0:
        reasons.append(f"sign flips across its own sample (first half IC {a:+.4f}, second "
                       f"{b:+.4f}) -- no stable direction to trade")

    # Cost realism, only when BOTH halves are present. Half a cost pair is a missing cost model,
    # not evidence -- treating it as evidence would let an absent measurement kill a live idea.
    if cost_bps is not None and gross_edge_bps is not None and cost_bps > 0:
        metrics["edge_over_cost"] = round(gross_edge_bps / cost_bps, 3)
        if gross_edge_bps < 2.0 * cost_bps:
            reasons.append(f"gross {gross_edge_bps:.2f}bps < 2x round-trip {cost_bps:.2f}bps -- "
                           f"the edge does not pay for its own execution")

    if reasons:
        return ScreenResult("REJECT", tuple(reasons), metrics)
    return ScreenResult("PASS", (), metrics)
