"""THE CAUSAL / MECHANISM ADJUDICATOR (LAWS 5m). Pure numpy; no file, no registry, no bars.

For one candidate mechanism -- "x moves y after `lag` steps, in this direction, because ..." --
it climbs the DoWhy-style ladder and names the rung that broke:

    IDENTIFICATION   what effect is estimable at all: the estimand, the adjustment set actually in
                     hand, and every confounder the mechanism NAMES but nobody supplied. A named
                     confounder with no series is UNIDENTIFIABLE, not "assumed away".
    ESTIMATION       the effect of x_t on y_{t+lag} partialled on the controls, in standardised
                     units, against a CIRCULAR-BLOCK PERMUTATION NULL: x is rotated as a block so
                     its own autocorrelation survives and only its alignment with y is destroyed.
    COUNTERFACTUAL   what y would have done had x not happened: the fitted contribution of x
                     removed on the episodes where |x| was large, cumulatively and per episode.
    REFUTATION       placebo predictors (should not predict), random label (y rotated: the
                     observed effect must beat that null), negative controls (outcomes the
                     mechanism should NOT move), subset / subperiod sign stability, an
                     alternative common-factor explanation (does the effect survive each control
                     alone), a simpler explanation that subsumes it (y's own lag, a momentum
                     proxy), and disappearance (where the mechanism says it should be absent,
                     it must be), plus the claimed sign.

Verdicts: SUPPORTED / REFUTED / UNIDENTIFIABLE / UNMEASURED, with `failing_test` naming the rung
or the refutation that failed. UNMEASURED is a value (L1.28a): too few aligned observations is a
finding about the data, never a pass.

WHAT THIS IS NOT. It is not a gate in front of the gauntlet (L1.60): the lab RECORDS the verdict
on the candidate and reports it; the ten gates and the promoter keep their authority. The one
thing it does insist on is the candidate contract of LAWS 5k -- a candidate does not exist
without its falsifier and the explanations it must beat -- so `eligible` is false until both are
declared, whatever the numbers say.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

SUPPORTED = "SUPPORTED"
REFUTED = "REFUTED"
UNIDENTIFIABLE = "UNIDENTIFIABLE"
UNMEASURED = "UNMEASURED"
VERDICTS: tuple[str, ...] = (SUPPORTED, REFUTED, UNIDENTIFIABLE, UNMEASURED)

MIN_N = 60            # aligned observations below which nothing is estimated
MIN_SUBSET = 30       # a subset smaller than this is UNMEASURED, not a refutation
N_PERM = 300
ALPHA = 0.05
#: A refutation that keeps at least this share of the original effect and stays significant is
#: "not explained away"; below it, with significance gone, the alternative wins.
SURVIVAL_SHARE = 0.5
EPISODE_SD = 1.0      # |x| beyond this many sd is an "episode" for the counterfactual

REFUTATION_ORDER: tuple[str, ...] = (
    "claimed_sign", "random_label", "placebo", "negative_control", "subset",
    "common_factor", "simpler_explanation", "disappearance")


@dataclass
class Mechanism:
    """A candidate mechanism and everything the ladder needs to try to kill it.

    All arrays are aligned to the same clock at index t; the adjudicator itself shifts `effect`
    by `lag` so x_t is compared with y_{t+lag} and never with anything earlier -- the
    anti-lookahead rule is inside the alignment, not left to the caller.
    """

    name: str
    cause: np.ndarray
    effect: np.ndarray
    lag: int = 1
    claimed_sign: int = 0
    controls: dict[str, np.ndarray] = field(default_factory=dict)
    confounders_named: tuple[str, ...] = ()
    placebo_predictors: dict[str, np.ndarray] = field(default_factory=dict)
    negative_controls: dict[str, np.ndarray] = field(default_factory=dict)
    subsets: dict[str, np.ndarray] = field(default_factory=dict)
    simpler: dict[str, np.ndarray] = field(default_factory=dict)
    disappears_when: np.ndarray | None = None
    competing: tuple[str, ...] = ()
    falsifier: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    name: str
    passed: bool | None          # None = UNMEASURED
    statistic: float | None
    p: float | None
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name,
                "status": ("PASS" if self.passed else "FAIL") if self.passed is not None
                else UNMEASURED,
                "statistic": self.statistic, "p": self.p, "why": self.why}


@dataclass
class Adjudication:
    mechanism: str
    verdict: str
    failing_test: str
    identification: dict[str, Any]
    estimate: dict[str, Any]
    counterfactual: dict[str, Any]
    refutations: list[TestResult]
    eligible: bool
    eligibility_why: str
    n: int

    def to_dict(self) -> dict[str, Any]:
        return {"mechanism": self.mechanism, "verdict": self.verdict,
                "failing_test": self.failing_test, "n": self.n,
                "identification": self.identification, "estimate": self.estimate,
                "counterfactual": self.counterfactual,
                "refutations": [r.to_dict() for r in self.refutations],
                "eligible_for_promotion": self.eligible, "eligibility_why": self.eligibility_why}


# ------------------------------------------------------------------------------ arithmetic
def _arr(v: Any) -> np.ndarray:
    return np.asarray(v, dtype="float64").reshape(-1)


def align(x: np.ndarray, y: np.ndarray, lag: int,
          extras: Mapping[str, np.ndarray] | None = None
          ) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray], np.ndarray]:
    """x_t against y_{t+lag}, every extra series read AT t, non-finite rows dropped. Returns
    (x, y, extras_at_t, kept_index) where kept_index maps back into the original clock."""
    lag = max(1, int(lag))
    x, y = _arr(x), _arr(y)
    n = min(len(x), len(y)) - lag
    if n <= 0:
        return np.zeros(0), np.zeros(0), {}, np.zeros(0, dtype="int64")
    xs, ys = x[:n], y[lag:lag + n]
    ex: dict[str, np.ndarray] = {}
    mask = np.isfinite(xs) & np.isfinite(ys)
    for k, v in (extras or {}).items():
        a = _arr(v)
        if len(a) < n:
            a = np.concatenate([a, np.full(n - len(a), np.nan)])
        ex[k] = a[:n]
        mask &= np.isfinite(ex[k])
    idx = np.nonzero(mask)[0]
    return xs[idx], ys[idx], {k: v[idx] for k, v in ex.items()}, idx


def _z(v: np.ndarray) -> np.ndarray:
    sd = float(np.std(v))
    return (v - float(np.mean(v))) / sd if sd > 0 else v - float(np.mean(v))


def partial_effect(x: np.ndarray, y: np.ndarray,
                   controls: Sequence[np.ndarray] = ()) -> tuple[float, float]:
    """(beta, t) of y on x with an intercept and the controls, in standardised units."""
    n = len(x)
    if n < 4 or float(np.std(x)) == 0 or float(np.std(y)) == 0:
        return 0.0, 0.0
    cols = [np.ones(n), _z(x)]
    for c in controls:
        if float(np.std(c)) > 0:
            cols.append(_z(c))
    design = np.column_stack(cols)
    yz = _z(y)
    beta, *_ = np.linalg.lstsq(design, yz, rcond=None)
    resid = yz - design @ beta
    dof = max(1, n - design.shape[1])
    s2 = float(resid @ resid) / dof
    try:
        cov = s2 * np.linalg.pinv(design.T @ design)
        se = float(np.sqrt(max(cov[1, 1], 1e-18)))
    except np.linalg.LinAlgError:
        se = float("inf")
    b = float(beta[1])
    return b, (b / se if se > 0 and np.isfinite(se) else 0.0)


def block_size(n: int) -> int:
    return max(5, round(math.cbrt(float(n))))


def circular_block_null(x: np.ndarray, y: np.ndarray, controls: Sequence[np.ndarray],
                        beta_obs: float, *, rng: np.random.Generator, n_perm: int = N_PERM,
                        rotate: str = "x") -> tuple[float, np.ndarray]:
    """p-value of |beta_obs| against betas from circular rotations of x (or y) by at least one
    block: the rotated series keeps its own autocorrelation, only the alignment is broken."""
    n = len(x)
    blk = block_size(n)
    if n < 2 * blk or n_perm <= 0:
        return float("nan"), np.zeros(0)
    offsets = rng.integers(blk, n - blk + 1, size=n_perm)
    betas = np.empty(n_perm)
    for i, off in enumerate(offsets):
        if rotate == "x":
            betas[i] = partial_effect(np.roll(x, int(off)), y, controls)[0]
        else:
            betas[i] = partial_effect(x, np.roll(y, int(off)), controls)[0]
    p = (1.0 + float(np.sum(np.abs(betas) >= abs(beta_obs)))) / (n_perm + 1.0)
    return p, betas


# ---------------------------------------------------------------------------------- rungs
def identify(m: Mechanism) -> dict[str, Any]:
    x, y, ex, _ = align(m.cause, m.effect, m.lag, m.controls)
    unobserved = [c for c in m.confounders_named if c not in m.controls]
    n = len(x)
    why: list[str] = []
    if unobserved:
        why.append(f"named confounder(s) with no observed series: {unobserved}")
    if n < MIN_N:
        why.append(f"{n} aligned observation(s) < {MIN_N}")
    if n and float(np.std(x)) == 0:
        why.append("the cause never varies in the window")
    if n and float(np.std(y)) == 0:
        why.append("the effect never varies in the window")
    return {"estimable": not why, "n": n, "lag": max(1, int(m.lag)),
            "estimand": (f"E[y_(t+{max(1, int(m.lag))}) | do(x_t)] under linear adjustment for "
                         f"{sorted(ex) or 'nothing'}"),
            "adjustment_set": sorted(ex), "unobserved_confounders": unobserved,
            "why": "; ".join(why) or "identified by adjustment on the observed controls"}


def estimate(m: Mechanism, *, rng: np.random.Generator, n_perm: int = N_PERM) -> dict[str, Any]:
    x, y, ex, _ = align(m.cause, m.effect, m.lag, m.controls)
    n = len(x)
    if n < MIN_N:
        return {"n": n, "beta": None, "t": None, "p": None, "sign": 0,
                "why": f"{n} aligned observation(s) < {MIN_N}"}
    ctl = list(ex.values())
    beta, t = partial_effect(x, y, ctl)
    p, betas = circular_block_null(x, y, ctl, beta, rng=rng, n_perm=n_perm)
    return {"n": n, "beta": round(beta, 6), "t": round(t, 4),
            "p": (None if p != p else round(p, 4)),
            "sign": int(np.sign(beta)) if beta else 0, "block": block_size(n),
            "n_perm": len(betas),
            "null_q95": (round(float(np.quantile(np.abs(betas), 0.95)), 6) if len(betas)
                         else None),
            "units": "standardised (sd of y per sd of x)",
            "why": ("distinguishable from the circular-block null" if p == p and p < ALPHA
                    else "not distinguishable from the circular-block null")}


def counterfactual(m: Mechanism, est: Mapping[str, Any]) -> dict[str, Any]:
    """Had x not happened: remove x's fitted contribution on the large-|x| episodes."""
    beta = est.get("beta")
    if not isinstance(beta, (int, float)):
        return {"status": UNMEASURED, "why": "no estimate to invert"}
    x, y, _ex, idx = align(m.cause, m.effect, m.lag, m.controls)
    if len(x) < MIN_N:
        return {"status": UNMEASURED, "why": "too few aligned observations"}
    xz, ysd = _z(x), float(np.std(y)) or 1.0
    contribution = float(beta) * xz * ysd                    # in y's own units
    episodes = np.abs(xz) >= EPISODE_SD
    n_ep = int(np.sum(episodes))
    return {"status": "MEASURED", "n_episodes": n_ep,
            "y_observed_in_episodes": (round(float(np.sum(y[episodes])), 6) if n_ep else 0.0),
            "y_had_x_not_happened": (round(float(np.sum(y[episodes] - contribution[episodes])),
                                           6) if n_ep else 0.0),
            "attributed_to_x": (round(float(np.sum(contribution[episodes])), 6) if n_ep
                                else 0.0),
            "mean_y_in_episodes": (round(float(np.mean(y[episodes])), 6) if n_ep else None),
            "mean_y_outside": (round(float(np.mean(y[~episodes])), 6) if n_ep < len(y)
                               else None),
            "episode_index": [int(i) for i in idx[episodes][:50]],
            "why": (f"x's fitted contribution removed on {n_ep} episode(s) where |x| >= "
                    f"{EPISODE_SD:g} sd; linear, so it is the counterfactual OF THIS MODEL")}


def _sub_effect(m: Mechanism, mask: np.ndarray, rng: np.random.Generator, n_perm: int
                ) -> tuple[int, float, float]:
    x, y, ex, idx = align(m.cause, m.effect, m.lag, m.controls)
    mk = _arr(mask)
    if len(mk) < len(m.cause):
        mk = np.concatenate([mk, np.zeros(len(m.cause) - len(mk))])
    keep = mk[idx] > 0
    xs, ys = x[keep], y[keep]
    ctl = [v[keep] for v in ex.values()]
    if len(xs) < MIN_SUBSET:
        return len(xs), float("nan"), float("nan")
    b, _t = partial_effect(xs, ys, ctl)
    p, _ = circular_block_null(xs, ys, ctl, b, rng=rng, n_perm=n_perm)
    return len(xs), b, p


def refute(m: Mechanism, est: Mapping[str, Any], *, rng: np.random.Generator,
           n_perm: int = N_PERM, alpha: float = ALPHA) -> list[TestResult]:
    out: list[TestResult] = []
    beta = est.get("beta")
    if not isinstance(beta, (int, float)):
        return [TestResult(name, None, None, None, "no estimate to refute")
                for name in REFUTATION_ORDER]
    b0 = float(beta)
    x, y, ex, _ = align(m.cause, m.effect, m.lag, m.controls)
    ctl = list(ex.values())

    # claimed sign
    if m.claimed_sign:
        ok = int(np.sign(b0)) == int(np.sign(m.claimed_sign))
        out.append(TestResult("claimed_sign", ok, b0, None,
                              "measured sign agrees with the claim" if ok else
                              f"claimed {m.claimed_sign:+d}, measured {int(np.sign(b0)):+d}"))
    else:
        out.append(TestResult("claimed_sign", None, b0, None, "no sign was claimed"))

    # random label: rotate y instead of x
    p_y, _ = circular_block_null(x, y, ctl, b0, rng=rng, n_perm=n_perm, rotate="y")
    if p_y == p_y:
        out.append(TestResult("random_label", p_y < alpha, b0, round(p_y, 4),
                              "beats the rotated-outcome null" if p_y < alpha else
                              "no better than a rotated outcome"))
    else:
        out.append(TestResult("random_label", None, b0, None, "too short for a block null"))

    # placebo predictors
    if m.placebo_predictors:
        worst: TestResult | None = None
        for name, series in m.placebo_predictors.items():
            xp, yp, exp_, _ = align(series, m.effect, m.lag, m.controls)
            if len(xp) < MIN_N:
                continue
            bp, _tp = partial_effect(xp, yp, list(exp_.values()))
            pp, _ = circular_block_null(xp, yp, list(exp_.values()), bp, rng=rng, n_perm=n_perm)
            fail = pp == pp and pp < alpha and abs(bp) >= abs(b0)
            if fail and (worst is None or abs(bp) > abs(worst.statistic or 0.0)):
                worst = TestResult("placebo", False, round(bp, 6), round(pp, 4),
                                   f"placebo predictor {name!r} predicts at least as well "
                                   f"(beta {bp:+.4f} vs {b0:+.4f})")
        out.append(worst or TestResult("placebo", True, None, None,
                                       f"{len(m.placebo_predictors)} placebo(s) predict worse"))
    else:
        out.append(TestResult("placebo", None, None, None, "no placebo predictor supplied"))

    # negative controls: outcomes the mechanism must not move
    if m.negative_controls:
        hit: TestResult | None = None
        for name, series in m.negative_controls.items():
            xn, yn, exn, _ = align(m.cause, series, m.lag, m.controls)
            if len(xn) < MIN_N:
                continue
            bn, _tn = partial_effect(xn, yn, list(exn.values()))
            pn, _ = circular_block_null(xn, yn, list(exn.values()), bn, rng=rng, n_perm=n_perm)
            if pn == pn and pn < alpha and abs(bn) >= abs(b0):
                hit = TestResult("negative_control", False, round(bn, 6), round(pn, 4),
                                 f"the cause moves negative control {name!r} as much "
                                 f"(beta {bn:+.4f}): the mechanism is not specific")
                break
        out.append(hit or TestResult("negative_control", True, None, None,
                                     f"{len(m.negative_controls)} negative control(s) unmoved"))
    else:
        out.append(TestResult("negative_control", None, None, None,
                              "no negative control supplied"))

    # subsets / subperiods
    if m.subsets:
        flip: TestResult | None = None
        measured = 0
        for name, mask in m.subsets.items():
            n_s, b_s, p_s = _sub_effect(m, mask, rng, n_perm)
            if b_s != b_s:
                continue
            measured += 1
            if p_s == p_s and p_s < alpha and np.sign(b_s) != np.sign(b0):
                flip = TestResult("subset", False, round(b_s, 6), round(p_s, 4),
                                  f"sign flips in subset {name!r} (beta {b_s:+.4f} on {n_s})")
                break
        if flip is not None:
            out.append(flip)
        elif measured:
            out.append(TestResult("subset", True, None, None,
                                  f"sign stable across {measured} measured subset(s)"))
        else:
            out.append(TestResult("subset", None, None, None,
                                  f"every subset is below {MIN_SUBSET} observations"))
    else:
        out.append(TestResult("subset", None, None, None, "no subset supplied"))

    # alternative common-factor explanation: with each control REMOVED vs present
    if ex:
        explained: TestResult | None = None
        for name in ex:
            others = [v for k, v in ex.items() if k != name]
            b_without, _ = partial_effect(x, y, others)
            b_with, _ = partial_effect(x, y, ctl)
            p_with, _ = circular_block_null(x, y, ctl, b_with, rng=rng, n_perm=n_perm)
            gone = (abs(b_with) < SURVIVAL_SHARE * abs(b_without)
                    and (p_with != p_with or p_with >= alpha))
            if gone:
                explained = TestResult("common_factor", False, round(b_with, 6),
                                       (round(p_with, 4) if p_with == p_with else None),
                                       f"explained by common factor {name!r}: beta "
                                       f"{b_without:+.4f} -> {b_with:+.4f} once it is held")
                break
        out.append(explained or TestResult("common_factor", True, None, None,
                                           f"survives each of {sorted(ex)} held alone"))
    else:
        out.append(TestResult("common_factor", None, None, None,
                              "no common factor supplied to hold"))

    # a simpler explanation that subsumes it
    if m.simpler:
        subsumed: TestResult | None = None
        for name, series in m.simpler.items():
            xs2, ys2, ex2, _ = align(m.cause, m.effect, m.lag, {**m.controls, name: series})
            if len(xs2) < MIN_N:
                continue
            ctl2 = list(ex2.values())
            b2, _ = partial_effect(xs2, ys2, ctl2)
            p2, _ = circular_block_null(xs2, ys2, ctl2, b2, rng=rng, n_perm=n_perm)
            if abs(b2) < SURVIVAL_SHARE * abs(b0) and (p2 != p2 or p2 >= alpha):
                subsumed = TestResult("simpler_explanation", False, round(b2, 6),
                                      (round(p2, 4) if p2 == p2 else None),
                                      f"subsumed by simpler explanation {name!r}: beta "
                                      f"{b0:+.4f} -> {b2:+.4f}")
                break
        out.append(subsumed or TestResult("simpler_explanation", True, None, None,
                                          f"adds to {sorted(m.simpler)}"))
    else:
        out.append(TestResult("simpler_explanation", None, None, None,
                              "no simpler explanation supplied"))

    # disappearance where the mechanism says it should be absent
    if m.disappears_when is not None:
        n_a, b_a, p_a = _sub_effect(m, m.disappears_when, rng, n_perm)
        if b_a != b_a:
            out.append(TestResult("disappearance", None, None, None,
                                  f"{n_a} observation(s) where the mechanism should be absent "
                                  f"< {MIN_SUBSET}"))
        elif p_a == p_a and p_a < alpha and abs(b_a) >= SURVIVAL_SHARE * abs(b0) \
                and np.sign(b_a) == np.sign(b0):
            out.append(TestResult("disappearance", False, round(b_a, 6), round(p_a, 4),
                                  f"does not disappear where it should (beta {b_a:+.4f} on "
                                  f"{n_a})"))
        else:
            out.append(TestResult("disappearance", True, round(b_a, 6),
                                  (round(p_a, 4) if p_a == p_a else None),
                                  "absent where the mechanism says it should be"))
    else:
        out.append(TestResult("disappearance", None, None, None,
                              "no disappearance condition supplied"))
    return out


def adjudicate(m: Mechanism, *, seed: int = 0, n_perm: int = N_PERM,
               alpha: float = ALPHA) -> Adjudication:
    """The whole ladder. The first rung that breaks names the verdict."""
    rng = np.random.default_rng(seed)
    has_falsifier = bool(str(m.falsifier or "").strip())
    has_competing = bool([c for c in m.competing if str(c).strip()])
    elig_why = ("falsifier and competing explanations declared" if has_falsifier and has_competing
                else "; ".join(w for w, ok in (("no falsifier declared", has_falsifier),
                                              ("no competing explanation declared", has_competing))
                               if not ok))
    ident = identify(m)
    if not ident["estimable"]:
        verdict = UNIDENTIFIABLE if ident["unobserved_confounders"] or (
            ident["n"] >= MIN_N) else UNMEASURED
        return Adjudication(m.name, verdict, "identification", ident,
                            {"n": ident["n"], "beta": None, "p": None, "why": ident["why"]},
                            {"status": UNMEASURED, "why": "not identified"}, [], False,
                            f"{verdict}: {ident['why']}", int(ident["n"]))
    est = estimate(m, rng=rng, n_perm=n_perm)
    if est.get("beta") is None:
        return Adjudication(m.name, UNMEASURED, "estimation", ident, est,
                            {"status": UNMEASURED, "why": "no estimate"}, [], False,
                            f"UNMEASURED: {est.get('why')}", int(est.get("n") or 0))
    cf = counterfactual(m, est)
    p = est.get("p")
    if not isinstance(p, (int, float)) or p >= alpha:
        return Adjudication(m.name, REFUTED, "estimation_null", ident, est, cf, [], False,
                            "REFUTED at estimation: no effect distinguishable from the "
                            "circular-block null", int(est["n"]))
    refs = refute(m, est, rng=rng, n_perm=n_perm, alpha=alpha)
    failed = next((r for r in refs if r.passed is False), None)
    if failed is not None:
        return Adjudication(m.name, REFUTED, failed.name, ident, est, cf, refs, False,
                            f"REFUTED by {failed.name}: {failed.why}", int(est["n"]))
    eligible = has_falsifier and has_competing
    return Adjudication(m.name, SUPPORTED, "", ident, est, cf, refs, eligible,
                        elig_why if eligible else f"SUPPORTED but ineligible: {elig_why}",
                        int(est["n"]))


def mechanism_from_spec(spec: Mapping[str, Any]) -> Mechanism:
    """A Mechanism from a plain mapping of arrays (what a lab hands over from its stores)."""
    def arrs(key: str) -> dict[str, np.ndarray]:
        v = spec.get(key) or {}
        return {str(k): _arr(a) for k, a in dict(v).items()}
    dw = spec.get("disappears_when")
    return Mechanism(
        name=str(spec.get("name") or "mechanism"), cause=_arr(spec["cause"]),
        effect=_arr(spec["effect"]), lag=int(spec.get("lag") or 1),
        claimed_sign=int(spec.get("claimed_sign") or 0), controls=arrs("controls"),
        confounders_named=tuple(str(c) for c in (spec.get("confounders_named") or ())),
        placebo_predictors=arrs("placebo_predictors"),
        negative_controls=arrs("negative_controls"), subsets=arrs("subsets"),
        simpler=arrs("simpler"),
        disappears_when=(_arr(dw) if dw is not None else None),
        competing=tuple(str(c) for c in (spec.get("competing") or ())),
        falsifier=str(spec.get("falsifier") or ""), detail=dict(spec.get("detail") or {}))
