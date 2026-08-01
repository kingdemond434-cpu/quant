"""Canonical performance metrics, CROSS-VERIFIED on every call.

WHY THIS EXISTS -- adversarial finding W3.2, which the repo states but never enforced:

    "Independent backtest cross-check (adversarial finding W3.2 -- never trust a single
     bespoke engine)."                                    -- pyproject.toml
    "A one-person event-driven engine *will* contain subtle P&L bugs."
                                                          -- libs/backtest/cross_engine.py

libs/backtest/cross_engine.py shipped exactly that safeguard and was imported by ZERO entry
points. Meanwhile ~20 screens each rolled their own `_stats()` -- cumprod, drawdown, annualised
vol -- and those numbers are what gate promotion to capital. So the desk's most consequential
arithmetic ran in twenty hand-written copies with no independent check anywhere. That is the
precise condition W3.2 warns about, and it is a MONEY-PATH defect: a subtle error here does not
crash, it promotes a strategy that never worked.

THE FIX IS STRUCTURAL, NOT ADVISORY. Every metric below is computed TWICE by genuinely
different algorithms and the two must agree or the call raises:

    sharpe    mean/std on the raw series      vs  a two-pass mean/variance accumulation
    equity    np.cumprod(1+r)                 vs  exp(cumsum(log1p(r)))   -- product vs log-sum
    max_dd    vectorised maximum.accumulate   vs  an explicit running-peak loop
    cagr      from the cumprod terminal       vs  from the log-space terminal

These are not the same formula written twice: a transcription slip, an off-by-one, a misplaced
annualisation or a sign error changes one path and not the other, so it surfaces as a raised
VerificationError instead of a plausible-looking Sharpe.

FAIL CLOSED. Divergence raises rather than warning-and-continuing. A number the desk cannot
verify must never reach a promotion decision -- that is the fail-open-guard class the code
auditor prompt lists first among this codebase's own measured defect history.

WHY IT LIVES IN libs/validation AND NOT libs/backtest: importing anything from libs.backtest
executes that package's __init__, which pulls engine -> libs.data -> duckdb and
libs.core.config -> pydantic-settings. A metrics primitive that twenty lightweight screens call
cannot cost the platform stack -- that import weight is a large part of why the W3.2 safeguard
sat unwired for so long. The screens already import libs.validation.dsr, so this adds nothing
to their dependency budget. `compare_metrics` below is the CANONICAL comparator;
libs.backtest.cross_engine.verify_cross_engine delegates to it, so there is exactly one
implementation of the comparison in the codebase.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

__all__ = [
    "MetricsInputError",
    "MetricsVerificationError",
    "compare_metrics",
    "metrics",
    "metrics_or_zero",
]

# Tolerance: cumprod and exp(cumsum(log1p)) are algebraically identical but not bit-identical.
# Their relative gap grows with series length and |r|; 1e-6 sits far above float noise for the
# horizons this desk trades (<= ~1e5 bars) and far below any error a real bug would produce.
_TOL = 1e-6
_KEYS = ("sharpe", "cagr", "max_dd", "vol")


class MetricsInputError(ValueError):
    """Input that cannot yield an honest metric (too short, all-NaN, non-finite)."""


class MetricsVerificationError(AssertionError):
    """Two independent computations of the same metric disagreed. Never catch to proceed."""


def compare_metrics(ours: Mapping[str, float], reference: Mapping[str, float], *,
                    keys: Sequence[str], tolerance: float = 1e-6,
                    relative: bool = True) -> dict[str, float]:
    """CANONICAL cross-check: compare two metric sets, raise on divergence beyond tolerance.

    Returns the per-key relative differences when all are within tolerance. This is the single
    implementation in the codebase -- libs.backtest.cross_engine.verify_cross_engine delegates
    here and re-raises in its own error type, so the heavy engine path and the light screen path
    can never drift apart in what "verified" means.
    """
    diffs: dict[str, float] = {}
    breaches: list[str] = []
    for key in keys:
        a, b = float(ours[key]), float(reference[key])
        denom = max(abs(b), 1e-9) if relative else 1.0
        rel = abs(a - b) / denom
        diffs[key] = rel
        if rel > tolerance:
            breaches.append(f"{key}: ours={a:.8g} ref={b:.8g} rel_diff={rel:.3g}")
    if breaches:
        raise MetricsVerificationError(
            f"cross-engine divergence beyond tolerance {tolerance:g}: " + "; ".join(breaches))
    return diffs


def _drawdown_vectorised(equity: np.ndarray) -> float:
    return float((equity / np.maximum.accumulate(equity) - 1.0).min())


def _drawdown_loop(equity: np.ndarray) -> float:
    """Independent running-peak scan -- deliberately NOT the vectorised expression."""
    peak = -math.inf
    worst = 0.0
    for v in equity.tolist():
        peak = v if v > peak else peak
        dd = v / peak - 1.0
        worst = dd if dd < worst else worst
    return float(worst)


def _sharpe_two_pass(a: np.ndarray) -> float:
    """Mean/std via explicit two-pass accumulation (independent of np.mean/np.std)."""
    n = len(a)
    total = 0.0
    for v in a.tolist():
        total += v
    mean = total / n
    sq = 0.0
    for v in a.tolist():
        d = v - mean
        sq += d * d
    var = sq / (n - 1)                      # sample variance, matching ddof=1
    return 0.0 if var <= 0.0 else mean / math.sqrt(var)


def metrics(returns: Any, *, periods_per_year: float, turnover: Any = None,
            cost_per_turnover: float = 0.0, min_points: int = 50,
            tolerance: float = _TOL) -> dict[str, float]:
    """Annualised sharpe/cagr/max_dd/vol for a per-period return series, cross-verified.

    `turnover` + `cost_per_turnover` apply friction before measurement, because a gross number
    is not a decision input on this desk -- the carry sleeve's own history (funding harvested
    $113 against implied costs $876) is what that rule was bought with.

    Raises MetricsInputError on unusable input and VerificationError when the two independent
    computations disagree. Callers must not catch VerificationError to proceed: the whole point
    is that an unverifiable number never reaches a gate.
    """
    r = np.asarray(returns, dtype="float64").ravel()
    if turnover is not None:
        t = np.asarray(turnover, dtype="float64").ravel()
        if t.shape != r.shape:
            raise MetricsInputError(f"turnover shape {t.shape} != returns shape {r.shape}")
        r = r - t * float(cost_per_turnover)
    a = r[np.isfinite(r)]
    if len(a) < min_points:
        raise MetricsInputError(f"{len(a)} usable points < min_points={min_points}")
    if np.any(a <= -1.0):
        raise MetricsInputError("return <= -100% -- equity would be non-positive; "
                                "check units (fraction, not percent)")

    ann = math.sqrt(float(periods_per_year))

    # ---- path A: multiplicative
    cum_a = np.cumprod(1.0 + a)
    sd = float(np.std(a, ddof=1))
    sharpe_a = 0.0 if sd == 0.0 else float(np.mean(a)) / sd * ann
    cagr_a = float(cum_a[-1] ** (periods_per_year / len(a)) - 1.0)
    dd_a = _drawdown_vectorised(cum_a)
    vol_a = sd * ann

    # ---- path B: log-space + scalar accumulation (independent of every numpy call above)
    log_terminal = float(np.sum(np.log1p(a)))
    cum_b = np.exp(np.cumsum(np.log1p(a)))
    sharpe_b = _sharpe_two_pass(a) * ann
    cagr_b = float(math.exp(log_terminal * (periods_per_year / len(a))) - 1.0)
    dd_b = _drawdown_loop(cum_b)
    vol_b = math.sqrt(sum((v - sum(a.tolist()) / len(a)) ** 2 for v in a.tolist())
                      / (len(a) - 1)) * ann

    ours = {"sharpe": sharpe_a, "cagr": cagr_a, "max_dd": dd_a, "vol": vol_a}
    ref = {"sharpe": sharpe_b, "cagr": cagr_b, "max_dd": dd_b, "vol": vol_b}
    # Raises MetricsVerificationError naming the diverging metric and both values.
    compare_metrics(ours, ref, keys=_KEYS, tolerance=tolerance)

    return {"sharpe": round(sharpe_a, 4), "cagr": round(cagr_a, 4),
            "max_dd": round(dd_a, 4), "vol": round(vol_a, 4), "n": len(a)}


def metrics_or_zero(returns: Any, **kw: Any) -> dict[str, float]:
    """`metrics` but returning zeros on UNUSABLE INPUT -- never on verification failure.

    The bespoke `_stats()` implementations returned a zero dict for short samples, so this
    preserves that ergonomics for callers that screen many candidate series. A
    VerificationError still propagates: bad input is a normal condition, arithmetic the desk
    cannot verify is not.
    """
    try:
        return metrics(returns, **kw)
    except MetricsInputError:
        return {"sharpe": 0.0, "cagr": 0.0, "max_dd": 0.0, "vol": 0.0, "n": 0}


def self_test() -> None:
    """Prove the cross-check actually bites -- a guard nobody has seen fire is not a guard."""
    rng = np.random.default_rng(0)
    r = rng.normal(0.0004, 0.01, 2000)
    m = metrics(r, periods_per_year=365)
    assert m["n"] == 2000
    try:                                     # a corrupted reference MUST raise
        compare_metrics({"sharpe": 1.0}, {"sharpe": 1.5}, keys=("sharpe",), tolerance=_TOL)
    except MetricsVerificationError:
        return
    raise AssertionError("compare_metrics did not raise on divergence")
