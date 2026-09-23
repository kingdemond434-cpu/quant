"""Forecast discipline from pysystemtrade: normalise, diversify, buffer.

    F_i = clip( signal_i / E|signal_i| x K, -CAP, +CAP )         every sleeve on one scale
    F_combined = FDM x sum_i w_i F_i,   FDM = 1 / sqrt(w' rho w)   independent agreement counts
    IDM = 1 / sqrt(w' rho_instruments w)                            across instruments
    buffer: trade only when |target - current| > band x |target|   inertia against noise

WHY IT BELONGS HERE. The weak-signal compiler votes members with frozen weights and the
allocator sizes sleeves in heat; neither had a common conviction scale, so "+10" from a
breakout member and "+10" from a carry member meant different things and the sum meant
nothing. Normalising by the member's own expected absolute forecast puts them on one scale;
the diversification multiplier lets genuinely independent agreement raise conviction while
correlated agreement does not; the buffer keeps the target from being chased through cost.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

TARGET_ABS = 10.0
CAP = 20.0
MAX_MULTIPLIER = 2.5


def normalise(signal: np.ndarray, target_abs: float = TARGET_ABS, cap: float = CAP,
              halflife: float = 250.0) -> np.ndarray:
    """Scale a raw forecast so its EW mean absolute value is `target_abs`, then clip."""
    s = np.asarray(signal, dtype=float)
    out = np.full(s.size, np.nan)
    lam = 0.5 ** (1.0 / max(halflife, 1.0))
    ew_abs = float("nan")
    for i, v in enumerate(s):
        if not np.isfinite(v):
            continue
        ew_abs = abs(v) if not np.isfinite(ew_abs) else lam * ew_abs + (1 - lam) * abs(v)
        if ew_abs > 0:
            out[i] = float(np.clip(v / ew_abs * target_abs, -cap, cap))
    return out


def diversification_multiplier(rho: np.ndarray, weights: np.ndarray,
                               cap: float = MAX_MULTIPLIER) -> float:
    """1 / sqrt(w' rho w), floored at 1 and capped: correlated agreement earns nothing extra."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.full_like(w, 1.0 / max(w.size, 1))
    d = float(w @ np.asarray(rho, dtype=float) @ w)
    if d <= 0:
        return 1.0
    return float(min(cap, max(1.0, 1.0 / np.sqrt(d))))


def combine(forecasts: Mapping[str, float], weights: Mapping[str, float], rho: np.ndarray,
            names: list[str], cap: float = CAP) -> dict[str, Any]:
    w = np.array([float(weights.get(n, 0.0)) for n in names])
    f = np.array([float(forecasts.get(n, 0.0)) for n in names])
    fdm = diversification_multiplier(rho, w)
    raw = float((w / w.sum()) @ f) if w.sum() > 0 else 0.0
    return {"forecast": float(np.clip(fdm * raw, -cap, cap)), "raw": raw, "fdm": fdm}


def buffer(current: float, target: float, band: float = 0.10) -> tuple[float, bool]:
    """Position inertia: hold unless the target is outside the band around the current."""
    width = band * abs(target)
    if abs(target - current) <= width:
        return current, False
    edge = target - np.sign(target - current) * width
    return float(edge), True
