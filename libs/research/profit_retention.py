"""Profit-retention engine: MFE/MAE, capture ratio, and exit overlays (pure, tested).

Building blocks for the gauntlet-gated exit study. They operate on a return series so they compose
with the sleeve backtests. The honesty rule lives in the CALLER: an overlay is promoted only if it
preserves CAGR and passes CPCV/DSR/PBO -- these functions just compute the candidate transforms;
they do not decide deployment, and must never run on a few dozen live points (fitting noise).
"""

from __future__ import annotations

import numpy as np


def cumulative_path(returns: np.ndarray) -> np.ndarray:
    """Cumulative compounded return path from per-period returns."""
    r = np.asarray(returns, dtype="float64")
    return np.cumprod(1.0 + r) - 1.0 if r.size else r


def mfe_mae(returns: np.ndarray) -> tuple[float, float]:
    """Maximum Favorable / Adverse Excursion of the cumulative path (peak gain, worst drawdown)."""
    cum = cumulative_path(returns)
    if cum.size == 0:
        return 0.0, 0.0
    return float(np.max(cum)), float(np.min(cum))


def capture_ratio(returns: np.ndarray) -> float | None:
    """Realized return / MFE -- the share of the peak favorable excursion actually kept. None if the
    path never went positive (capture undefined)."""
    r = np.asarray(returns, dtype="float64")
    if r.size == 0:
        return None
    mfe, _ = mfe_mae(r)
    realized = float(np.prod(1.0 + r) - 1.0)
    return realized / mfe if mfe > 0 else None


def vol_target_overlay(returns: np.ndarray, target_vol: float, *, lookback: int = 20) -> np.ndarray:
    """Scale exposure to a target per-period vol using trailing realized vol (never levers up >1x).
    The standard vol-trailing exit: cut size as volatility rises against you."""
    r = np.asarray(returns, dtype="float64")
    out = np.empty_like(r)
    for i in range(r.size):
        win = r[max(0, i - lookback):i]
        sd = float(np.std(win)) if win.size > 2 else target_vol
        scale = min(1.0, target_vol / sd) if sd > 0 else 1.0
        out[i] = r[i] * scale
    return out


def trailing_stop_exit(returns: np.ndarray, stop: float = 0.10) -> np.ndarray:
    """Flatten (zero subsequent returns) once the cumulative path draws down `stop` from its running
    peak -- a trailing exit for one holding episode (trend sleeves: let winners run, cut givers)."""
    r = np.asarray(returns, dtype="float64")
    out = r.copy()
    cum = peak = 0.0
    stopped = False
    for i in range(r.size):
        if stopped:
            out[i] = 0.0
            continue
        cum = (1.0 + cum) * (1.0 + r[i]) - 1.0
        peak = max(peak, cum)
        if cum <= peak - stop:
            stopped = True
    return out


def time_decay_exit(returns: np.ndarray, signal: np.ndarray, *, floor: float = 0.0) -> np.ndarray:
    """Zero the return whenever the edge signal (e.g. funding/basis carry) has decayed to/below
    `floor` -- a carry sleeve should exit when the carry disappears, not ride it to reversion."""
    r = np.asarray(returns, dtype="float64")
    s = np.asarray(signal, dtype="float64")
    return np.where(s > floor, r, 0.0)
