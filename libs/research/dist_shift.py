"""DISTRIBUTION-SHIFT MONITOR -- constitution L2.10 / triage #128, built 2026-07-29.

THE QUESTION IT ANSWERS, which regime classification does NOT: *are we still operating in the
same world the signal was screened in?* A relationship can survive while the distribution beneath
it moves — vol compresses, liquidity thins, the correlation structure re-forms — and every
threshold the desk calibrated (z-score windows, cost floors, funding bars, depth guards) was fitted
in the OLD distribution. Regime labels answer "which state are we in"; this answers "has the
measuring stick itself changed", which is the failure mode that silently invalidates calibration.

DELIBERATELY MERGED, NOT A NEW AGENT (L2.9 upgrade-before-build): this is a library the existing
revalidation path and axis screens call. It owns no cadence, no state file, no pager.

ACTION SEMANTICS, and the direction matters: a detected shift NEVER promotes and never
auto-demotes. It (a) flags the axis for re-validation and (b) recommends a CONFIDENCE HAIRCUT --
downward only. A monitor that could raise confidence would be an alpha claim wearing a
diagnostic's clothes.

Method: two-sample, non-parametric, tiny — a two-sample KS statistic plus a variance-ratio and a
level shift in robust units, computed reference-window vs recent-window. No scipy dependency (the
KS critical value at 5% is the standard 1.36*sqrt((n+m)/nm) asymptotic form), so this runs in any
organ including the quota-free ones.

A SECOND, INDEPENDENT DETECTOR (2026-09-08) -- AND THE HAIRCUT NOW NEEDS BOTH. The KS/variance-
ratio composite is a two-sample comparison: it asks whether the recent window, taken as a bag,
looks like the reference bag. The second detector is SEQUENTIAL: a two-sided Page CUSUM run
through the recent window on the series standardised by the reference window. It accumulates a
persistent drift observation by observation, so it can say WHEN the stick moved
(`cusum_crossed_at`) rather than only whether, and it is a different mechanism from a bag
comparison rather than the same evidence re-weighed. Two charts, both on the one standardised
series: a level chart on z and a scale chart on |z|, each centred and scaled by the REFERENCE
window's own moments of the same quantity, so under no-shift the increments are mean-zero for ANY
tail shape and not only for a normal one. Standardised values are winsorised at 3 reference SDs:
one fat-tailed print is one observation, not a break.

MEASURED NULL (Monte Carlo 2026-09-08, 3000 pairs per cell, both windows drawn from one law):
  P(max chart > 9)   normal n=20/60/200/400: 4.8/4.8/5.1/7.7%    t(3): 4.9/5.0/6.9/9.6%
                     chi2(3): 5.0/4.9/8.1/11.8%
  P(max chart > 12)  normal: 1.8/0.9/0.8/1.0%   t(3): 1.9/0.9/1.2/1.2%   chi2(3): 2.0/1.0/1.5/1.2%
  The same charts on raw (z^2 - 1)/sqrt(2) with normal-theory constants alarmed 72% of the time on
  STATIONARY t(3) noise at n=60. A detector that always fires is one that always agrees, and a
  detector that always agrees is not a second detector -- which is why the constants are read
  from the reference window rather than assumed.
MEASURED POWER (normal reference, recent n=60 / n=200, P(max chart > 12)): level +1 SD 0.96/1.00;
  variance x4 0.99/1.00; variance x2 0.51/0.91; SD x0.15 0.98/1.00. BLIND SPOT, STATED: a variance
  HALVING sits below the chart's allowance (k=0.5) and is caught 1%/4%, so a bare variance-ratio
  flag at 0.5x from the KS side will generally NOT be corroborated and its haircut is withheld.
  That is strictly more evidence required to haircut, never less -- the only direction this
  change was permitted to move.

AGREEMENT RULE. `verdict` REMAINS the KS/variance-ratio composite, so every reader that flags an
axis for re-validation on it is unchanged. `cusum_verdict` is the second opinion, `agreement` is
whether the two coincide exactly, and `agreed_verdict` is the severity BOTH reach (STABLE < DRIFT
< SHIFT). The recommended `haircut` now follows `agreed_verdict`: it is never larger than what the
single detector recommended before (`haircut_single_detector` is kept beside it for the reader),
and it is zero unless both detectors see a move. Downward-only confidence, advisory, unchanged in
kind -- it is a haircut on confidence, never on size.

Pure numpy. import from libs.research.dist_shift.
"""
from __future__ import annotations

from typing import Any, Literal

import numpy as np

Verdict = Literal["STABLE", "DRIFT", "SHIFT", "INSUFFICIENT-DATA"]

# Bands. Chosen to catch distributional MOVES, not noise: at n=m=60 the 5% KS critical value is
# ~0.248, so DRIFT starts where the two windows are formally distinguishable and SHIFT is reserved
# for a clearly different distribution. Variance ratio bands are 2x/0.5x -- a halving or doubling
# of realised variance re-prices every vol-scaled threshold the desk owns.
_VAR_BAND = 2.0
_VAR_BREAK = 4.0
_LEVEL_BAND = 1.0      # median move, in reference-window MADs
_LEVEL_BREAK = 2.5
_MIN_WIN = 20

# CUSUM (detector 2). k is Page's allowance -- half the shift, in reference SDs, the chart is tuned
# to catch; below it a drift is absorbed rather than accumulated. The two h's are the DRIFT and
# SHIFT boundaries on the largest excursion of either chart, set from the measured null in the
# header (~5% and ~1% at the window lengths the desk uses) rather than from a textbook ARL that
# assumes a known-normal reference. Raising either only withholds haircuts; lowering either is a
# policy change and moves by a ledgered decision or not at all.
_CUSUM_K = 0.5
_CUSUM_CLIP = 3.0
_CUSUM_DRIFT = 9.0
_CUSUM_BREAK = 12.0
_MAD_TO_SD = 1.4826    # MAD of a normal -> its SD

_SEVERITY = {"INSUFFICIENT-DATA": 0, "STABLE": 0, "DRIFT": 1, "SHIFT": 2}
_BY_SEVERITY = {0: "STABLE", 1: "DRIFT", 2: "SHIFT"}
_HAIRCUT = {"STABLE": 0.0, "DRIFT": 0.15, "SHIFT": 0.35, "INSUFFICIENT-DATA": 0.0}


def _ks(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Two-sample KS statistic and its 5% asymptotic critical value."""
    grid = np.concatenate([a, b])
    grid.sort()
    ca = np.searchsorted(np.sort(a), grid, side="right") / len(a)
    cb = np.searchsorted(np.sort(b), grid, side="right") / len(b)
    d = float(np.max(np.abs(ca - cb)))
    crit = 1.36 * float(np.sqrt((len(a) + len(b)) / (len(a) * len(b))))
    return d, crit


def _mad(x: np.ndarray) -> float:
    return float(np.median(np.abs(x - np.median(x))))


def _page_cusum(x: np.ndarray, *, k: float = _CUSUM_K,
                h: float = _CUSUM_DRIFT) -> tuple[float, int | None]:
    """Two-sided Page CUSUM through `x`.

    Returns the largest excursion of either one-sided chart and the 1-based index of the FIRST
    step at which it exceeded `h` (None if never) -- the latter is the "when", which a bag
    comparison cannot give.
    """
    up = down = best = 0.0
    first: int | None = None
    for i, xi in enumerate(x.tolist(), 1):
        up = max(0.0, up + xi - k)
        down = max(0.0, down - xi - k)
        cur = max(up, down)
        if cur > best:
            best = cur
        if first is None and cur > h:
            first = i
    return best, first


def cusum_shift(reference: np.ndarray, recent: np.ndarray, *,
                name: str = "series") -> dict[str, Any]:
    """Detector 2: a two-sided Page CUSUM of the recent window standardised by the reference.

    Level chart on z, scale chart on |z|; each chart's increments are centred and scaled by the
    reference window's own moments of the same quantity, so the null is distribution-free up to
    the sampling error of those moments (see the measured table in the module header). The
    verdict is on the larger excursion of the two charts.
    """
    a = np.asarray(reference, dtype="float64")
    b = np.asarray(recent, dtype="float64")
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    base: dict[str, Any] = {
        "name": name, "n_ref": len(a), "n_recent": len(b), "cusum_k": _CUSUM_K,
        "cusum_clip_sd": _CUSUM_CLIP, "cusum_h_drift": _CUSUM_DRIFT, "cusum_h_break": _CUSUM_BREAK,
        "cusum_level": None, "cusum_scale": None, "cusum_stat": None, "cusum_crossed_at": None,
    }
    if len(a) < _MIN_WIN or len(b) < _MIN_WIN:
        return {**base, "verdict": "INSUFFICIENT-DATA",
                "detail": f"need >={_MIN_WIN} finite points per window"}

    med = float(np.median(a))
    scale = _mad(a) * _MAD_TO_SD
    if scale <= 0.0:
        # More than half the reference is one value; fall back to the SD before giving up.
        scale = float(a.std(ddof=1))
    if not scale > 0.0:
        return {**base, "verdict": "INSUFFICIENT-DATA",
                "detail": "reference window has no spread; nothing can be standardised against it"}
    za = np.clip((a - med) / scale, -_CUSUM_CLIP, _CUSUM_CLIP)
    zb = np.clip((b - med) / scale, -_CUSUM_CLIP, _CUSUM_CLIP)

    charts: dict[str, tuple[float, int | None]] = {}
    for chart, ra, rb in (("level", za, zb), ("scale", np.abs(za), np.abs(zb))):
        sd = float(ra.std(ddof=1))
        if not sd > 0.0:
            return {**base, "verdict": "INSUFFICIENT-DATA",
                    "detail": f"reference {chart} series is degenerate after winsorisation"}
        charts[chart] = _page_cusum((rb - float(ra.mean())) / sd)
    level, level_at = charts["level"]
    scl, scale_at = charts["scale"]
    stat = max(level, scl)
    verdict: Verdict = ("SHIFT" if stat > _CUSUM_BREAK
                        else "DRIFT" if stat > _CUSUM_DRIFT else "STABLE")
    firsts = [i for i in (level_at, scale_at) if i is not None]
    return {**base, "verdict": verdict, "cusum_level": round(level, 3),
            "cusum_scale": round(scl, 3), "cusum_stat": round(stat, 3),
            "cusum_crossed_at": min(firsts) if firsts else None}


def agreed_verdict(first: str, second: str) -> str:
    """The severity BOTH detectors reach: the weaker of the two readings.

    SHIFT+DRIFT is DRIFT (both saw a move; only one saw a break), anything+STABLE is STABLE, and
    INSUFFICIENT-DATA counts as no evidence rather than as a move. A haircut keyed on this can
    never exceed the haircut either detector would have recommended alone.
    """
    lo = min(_SEVERITY.get(first, 0), _SEVERITY.get(second, 0))
    return _BY_SEVERITY[lo]


def distribution_shift(reference: np.ndarray, recent: np.ndarray, *,
                       name: str = "series") -> dict[str, Any]:
    """Compare a recent window against a reference window on shape, spread and level.

    reference: the window the signal/threshold was calibrated in.
    recent:    the window the desk is trading in now.
    Returns the KS/variance-ratio `verdict` (unchanged), the independent `cusum_verdict`, their
    `agreement`, and a RECOMMENDED confidence haircut in [0, 0.5] that follows `agreed_verdict`
    -- downward only, requiring both detectors, and advisory: the caller decides, and the caller
    logs the decision.
    """
    a = np.asarray(reference, dtype="float64")
    b = np.asarray(recent, dtype="float64")
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < _MIN_WIN or len(b) < _MIN_WIN:
        return {"name": name, "verdict": "INSUFFICIENT-DATA",
                "cusum_verdict": "INSUFFICIENT-DATA", "agreement": True,
                "agreed_verdict": "INSUFFICIENT-DATA", "n_ref": len(a),
                "n_recent": len(b), "haircut": 0.0, "haircut_single_detector": 0.0,
                "detail": f"need >={_MIN_WIN} finite points per window"}

    d, crit = _ks(a, b)
    va, vb = float(a.var()), float(b.var())
    var_ratio = (vb / va) if va > 0 else float("inf") if vb > 0 else 1.0
    mad_a = _mad(a)
    level_move = abs(float(np.median(b) - np.median(a))) / mad_a if mad_a > 0 else 0.0

    ks_flag = d > crit
    var_flag = var_ratio > _VAR_BAND or var_ratio < 1.0 / _VAR_BAND
    var_break = var_ratio > _VAR_BREAK or var_ratio < 1.0 / _VAR_BREAK
    level_flag = level_move > _LEVEL_BAND
    level_break = level_move > _LEVEL_BREAK

    # SHIFT requires either a break-magnitude move OR agreement between two independent views
    # (shape + spread/level). One marginal indicator alone is DRIFT: it flags, it does not
    # conclude -- the same corroboration discipline the lookahead rail uses (axis_screen).
    corroborated = ks_flag and (var_flag or level_flag)
    if var_break or level_break or corroborated:
        verdict: Verdict = "SHIFT"
    elif ks_flag or var_flag or level_flag:
        verdict = "DRIFT"
    else:
        verdict = "STABLE"

    # DETECTOR 2, AND THE HAIRCUT FOLLOWS WHAT BOTH REACH. `verdict` above is untouched so the
    # re-validation flag readers key on is exactly what it was; only the haircut got stricter.
    cus = cusum_shift(a, b, name=name)
    cusum_verdict = str(cus["verdict"])
    agreed = agreed_verdict(verdict, cusum_verdict)
    haircut = _HAIRCUT[agreed]
    single = _HAIRCUT[verdict]
    if verdict == "STABLE" and agreed == "STABLE":
        action = ("none" if cusum_verdict == "STABLE" else
                  f"none (CUSUM alone reads {cusum_verdict}; one detector flags, it does not "
                  "conclude, and no haircut is recommended)")
    elif agreed == "STABLE":
        action = ("flag-for-revalidation (KS/variance-ratio only); confidence haircut WITHHELD "
                  f"-- the CUSUM reads {cusum_verdict} and does not corroborate")
    else:
        action = (f"flag-for-revalidation + confidence haircut at {agreed} (both detectors "
                  "reach it; advisory, downward only)")
    return {"name": name, "verdict": verdict, "haircut": haircut,
            "haircut_single_detector": single,
            "ks_d": round(d, 4), "ks_crit_5pct": round(crit, 4), "ks_flag": ks_flag,
            "var_ratio": round(var_ratio, 3) if np.isfinite(var_ratio) else None,
            "level_move_mads": round(level_move, 3),
            "cusum_verdict": cusum_verdict, "cusum_level": cus["cusum_level"],
            "cusum_scale": cus["cusum_scale"], "cusum_stat": cus["cusum_stat"],
            "cusum_crossed_at": cus["cusum_crossed_at"],
            "agreement": verdict == cusum_verdict, "agreed_verdict": agreed,
            "n_ref": len(a), "n_recent": len(b),
            "action": action,
            "note": ("regime labels say WHICH state; this says whether the measuring stick "
                     "moved. verdict = KS/variance-ratio composite; the haircut needs the CUSUM "
                     "to reach the same severity")}


def split_and_check(series: np.ndarray, *, recent_frac: float = 0.25,
                    name: str = "series") -> dict[str, Any]:
    """Convenience: split one series into reference (early) and recent (tail) and compare.

    Used by revalidation passes that hold a single history and want the honest question "does my
    own tail look like my own body?" without choosing windows by hand -- choosing the split point
    after seeing the answer is exactly the specification search the desk forbids elsewhere.
    """
    x = np.asarray(series, dtype="float64")
    cut = max(int(len(x) * (1.0 - min(max(recent_frac, 0.05), 0.5))), 0)
    return distribution_shift(x[:cut], x[cut:], name=name)
