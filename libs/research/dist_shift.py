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


def distribution_shift(reference: np.ndarray, recent: np.ndarray, *,
                       name: str = "series") -> dict[str, Any]:
    """Compare a recent window against a reference window on shape, spread and level.

    reference: the window the signal/threshold was calibrated in.
    recent:    the window the desk is trading in now.
    Returns a verdict plus a RECOMMENDED confidence haircut in [0, 0.5] -- downward only, and
    advisory: the caller decides, and the caller logs the decision.
    """
    a = np.asarray(reference, dtype="float64")
    b = np.asarray(recent, dtype="float64")
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < _MIN_WIN or len(b) < _MIN_WIN:
        return {"name": name, "verdict": "INSUFFICIENT-DATA", "n_ref": len(a),
                "n_recent": len(b), "haircut": 0.0,
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

    haircut = {"STABLE": 0.0, "DRIFT": 0.15, "SHIFT": 0.35,
               "INSUFFICIENT-DATA": 0.0}[verdict]
    return {"name": name, "verdict": verdict, "haircut": haircut,
            "ks_d": round(d, 4), "ks_crit_5pct": round(crit, 4), "ks_flag": ks_flag,
            "var_ratio": round(var_ratio, 3) if np.isfinite(var_ratio) else None,
            "level_move_mads": round(level_move, 3),
            "n_ref": len(a), "n_recent": len(b),
            "action": ("none" if verdict == "STABLE" else
                       "flag-for-revalidation + confidence haircut (advisory, downward only)"),
            "note": "regime labels say WHICH state; this says whether the measuring stick moved"}


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
