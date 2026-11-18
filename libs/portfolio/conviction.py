"""Conviction scaling (Build C row 143): evidence strength x agreement of independent signals.

A TWO-SIDED capital modifier on each sleeve's evidence weight:

    conviction = clip(strength x agreement, CONV_LO, CONV_HI)            in [0.5, 2.0]
    strength   = 1 + n/(n + CONV_K_N) x (2 DSR - 1) x CONV_SPAN          deflated Sharpe, by n
    agreement  = clip(sqrt((1 + k) / (1 + k_ref)), AGREE_LO, AGREE_HI)    independent corroboration

k counts the other sleeves on the SAME instrument, of ANOTHER mechanism, with positive expectancy
and |corr| < RHO_INDEP to the sleeve under the allocator's own `_corr_abs`; k_ref is the book's
median. It enters `pf_allocator` as a tilt of the posterior mean BEFORE the E[log W] solve
(`apply_conviction`, the `allocator_evidence` rule), never as a multiplier on the answer.

GROWTH GOVERNANCE. Rule 2: a deflated-Sharpe-strong, independently corroborated sleeve is raised up
to 2x. Rule 1: the switch `desks/mt5/data/CONVICTION_SCALING.json` defaults to SHADOW, so it cuts
nothing on the account until `research/conviction_shadow.py` measures robustly positive forward
dE[log W] and flips it by `conviction_promotion`; its downward half is billed as a missed-growth
line every pass (`missed_growth.published_conviction_lines`).

WHY THIS FILE AND NOT `capital_modifiers.py`. `capital_modifiers.py` and `rails.py` are SEALED
judge files (scripts/check_immutable_evaluator.py): a change to them is signed only by the audit
train (scripts/sign_train.py) on a CLEAR row. The registry row this modifier needs is `MODIFIER`
below -- the exact `capital_modifiers.Modifier` the sealed REGISTRY will carry once re-signed --
and the growth fence's G4 rule is asserted on it by the tests in the meantime.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from libs.portfolio.capital_modifiers import DESK, Modifier

#: Conviction scaling bounds and shape (see `conviction_factors`).
CONV_LO, CONV_HI = 0.5, 2.0
#: Days of evidence at which the strength term carries half its weight.
CONV_K_N = 120.0
#: Half-width of the strength band: DSR 1.0 with infinite n reads 1 + CONV_SPAN.
CONV_SPAN = 0.5
#: Two sleeves are INDEPENDENT signals when the allocator's own |corr| between them is below this.
RHO_INDEP = 0.3
AGREE_LO, AGREE_HI = 0.75, 1.5
#: The switch. Absent, unreadable or anything but {"mode": "LIVE"} reads SHADOW.
CONVICTION_SWITCH = DESK / "data" / "CONVICTION_SCALING.json"
#: Forward passes (distinct UTC days) the shadow comparison needs before it may flip the switch.
CONV_PROMOTE_N = 20

#: The registry row, two-sided by construction (G4: hi > 1.0).
MODIFIER = Modifier("conviction", CONV_LO, CONV_HI, "two_sided",
                    "libs.portfolio.conviction.conviction_factors -> "
                    "pf_allocator.apply_conviction_scaling (LIVE only; SHADOW leaves the evidence "
                    "byte-identical)",
                    "desks/mt5/reports/CONVICTION_SHADOW.json")


def conviction_mode(path: Path | None = None) -> str:
    """LIVE only when the switch file says so; everything else (absent too) reads SHADOW."""
    try:
        doc = json.loads((path or CONVICTION_SWITCH).read_text("utf-8"))
    except (OSError, ValueError):
        return "SHADOW"
    return "LIVE" if isinstance(doc, dict) and doc.get("mode") == "LIVE" else "SHADOW"


def _finite(a: Any) -> np.ndarray:
    arr = np.asarray(a, dtype=float)
    out: np.ndarray = arr[np.isfinite(arr)]
    return out


def evidence_strength(r: np.ndarray, n_trials: int, var_sharpes: float) -> tuple[float, float]:
    """(deflated Sharpe probability, strength multiplier) for one sleeve's daily R.

    strength = 1 + lam_n x (2 x DSR - 1) x CONV_SPAN, lam_n = n / (n + CONV_K_N). DSR 0.5 (the
    observed Sharpe is exactly what the search would produce by luck) is neutral; a deflated
    probability near 1 on a long record lifts toward 1 + CONV_SPAN and one near 0 cuts toward
    1 - CONV_SPAN. A short record is pulled toward 1.0 either way.
    """
    from libs.validation.dsr import expected_max_sharpe, probabilistic_sharpe_ratio
    x = _finite(r)
    n = int(x.size)
    if n < 3 or float(x.std()) <= 0:
        return 0.5, 1.0
    sr0 = expected_max_sharpe(max(int(n_trials), 1), max(float(var_sharpes), 0.0))
    dsr = float(probabilistic_sharpe_ratio(x, sr_benchmark=sr0))
    if not math.isfinite(dsr):
        return 0.5, 1.0
    lam = n / (n + CONV_K_N)
    return dsr, float(1.0 + lam * (2.0 * dsr - 1.0) * CONV_SPAN)


def agreement_counts(ev: Sequence[Any], corr_abs: np.ndarray) -> list[int]:
    """Per sleeve: other sleeves on the SAME instrument, of ANOTHER mechanism (family), with a
    positive mean and |corr| < RHO_INDEP to it. Zero for a sleeve whose own mean is not positive
    (it has no direction for anything to agree with)."""
    means = [float(_finite(e.daily_r).mean()) if _finite(e.daily_r).size else 0.0 for e in ev]
    out = []
    for i, e in enumerate(ev):
        if means[i] <= 0 or not getattr(e, "symbol", ""):
            out.append(0)
            continue
        k = 0
        for j, o in enumerate(ev):
            if (j != i and getattr(o, "symbol", "") == e.symbol
                    and getattr(o, "family", "") != getattr(e, "family", "")
                    and means[j] > 0 and float(corr_abs[i, j]) < RHO_INDEP):
                k += 1
        out.append(k)
    return out


def conviction_factors(ev: Sequence[Any], corr_abs: np.ndarray | None = None
                       ) -> dict[str, dict[str, Any]]:
    """One conviction multiplier per sleeve, two-sided, in [CONV_LO, CONV_HI].

    conviction = clip(strength x agreement), agreement = clip(sqrt((1 + k) / (1 + k_ref))) with
    k the sleeve's count of agreeing independent signals and k_ref the median count over the
    positive-mean sleeves -- so a sleeve corroborated more than the book's typical sleeve is
    lifted and one corroborated less is lowered, and a book where nothing corroborates anything
    reads 1.0 on this term. `corr_abs` defaults to the allocator's own `_corr_abs`.
    """
    if not ev:
        return {}
    if corr_abs is None:
        from libs.portfolio.robust_elog import _corr_abs
        corr_abs = _corr_abs(ev)
    from libs.validation.dsr import sharpe_ratio
    srs = [sharpe_ratio(_finite(e.daily_r)) for e in ev if _finite(e.daily_r).size >= 3]
    var_sr = float(np.var(srs, ddof=1)) if len(srs) >= 2 else 0.0
    ks = agreement_counts(ev, corr_abs)
    pos = [k for e, k in zip(ev, ks, strict=True)
           if _finite(e.daily_r).size and float(_finite(e.daily_r).mean()) > 0]
    k_ref = float(np.median(pos)) if pos else 0.0
    out: dict[str, dict[str, Any]] = {}
    for e, k in zip(ev, ks, strict=True):
        dsr, strength = evidence_strength(e.daily_r, int(getattr(e, "n_trials", 1) or 1), var_sr)
        agree = float(min(AGREE_HI, max(AGREE_LO, math.sqrt((1.0 + k) / (1.0 + k_ref)))))
        mult = float(min(CONV_HI, max(CONV_LO, strength * agree)))
        out[e.name] = {"dsr": round(dsr, 6), "n": int(_finite(e.daily_r).size),
                       "n_trials": int(getattr(e, "n_trials", 1) or 1),
                       "strength": round(strength, 6), "agreeing": int(k),
                       "k_ref": k_ref, "agreement": round(agree, 6), "factor": round(mult, 6)}
    return out


def apply_conviction(ev: Sequence[Any], factors: Mapping[str, Mapping[str, Any]]) -> list[Any]:
    """A NEW list with each sleeve's posterior mean tilted by its conviction factor:
    mean += (factor - 1) x |mean|, dispersion unchanged (the `allocator_evidence` rule). The
    input list and its arrays are never touched."""
    from dataclasses import replace as _replace
    out = []
    for e in ev:
        f = float((factors.get(e.name) or {}).get("factor", 1.0))
        arr = np.asarray(e.daily_r, dtype=float)
        mask = np.isfinite(arr)
        if abs(f - 1.0) < 1e-12 or not mask.any():
            out.append(e)
            continue
        new = arr.copy()
        new[mask] = new[mask] + (f - 1.0) * abs(float(arr[mask].mean()))
        out.append(_replace(e, daily_r=new))
    return out


def conviction_promotion(deltas: Sequence[float], current: str, n: int = CONV_PROMOTE_N
                         ) -> dict[str, Any]:
    """THE SWITCH'S RULE, in code and with no human gate.

    `deltas` are forward realised dE[log W] per pass (conviction book minus base book, one per
    distinct UTC day, oldest first). Over the last `n`:
      * SHADOW -> LIVE when mean - se > 0 (robustly positive forward growth);
      * LIVE -> SHADOW when mean + se < 0 (robustly negative: the modifier lost its authority);
      * otherwise the mode stands. Fewer than `n` matured passes is UNMEASURED and stands.
    """
    arr = np.asarray([float(d) for d in deltas if math.isfinite(float(d))][-n:], dtype=float)
    if arr.size < n:
        return {"mode": current, "changed": False, "verdict": "UNMEASURED", "n": int(arr.size),
                "need": n}
    mean = float(arr.mean())
    se = float(arr.std(ddof=1) / math.sqrt(arr.size)) if arr.size > 1 else 0.0
    nxt = current
    if current != "LIVE" and mean - se > 0:
        nxt = "LIVE"
    elif current == "LIVE" and mean + se < 0:
        nxt = "SHADOW"
    verdict = ("RAISES_ELOG" if mean - se > 0 else
               ("LOWERS_ELOG" if mean + se < 0 else "UNPROVEN"))
    return {"mode": nxt, "changed": nxt != current, "verdict": verdict, "n": int(arr.size),
            "mean_delta_logw": round(mean, 10), "se": round(se, 10)}
