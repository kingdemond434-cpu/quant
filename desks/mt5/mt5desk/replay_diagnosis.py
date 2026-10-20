"""Why a forward replay produced no trade at all -- a named cause on the row, never a bare zero.

The clock-law judge (2026-10-14) found 26 clocks reading n = 0 AND n_historical = 0: the replay
had never fired once since SHADOW_START. 24 were factor baskets the input layer now names
(`mt5desk.factor_inputs`); 2 were `formula` cells, `ts_backfill(std(spread, 12), k)` on GBPCAD
and GBPCHF H1, whose siblings on the same bars (std over 3 bars, decay, delta) fire normally. An
empty replay is a fact about the cell only once the family's own preconditions are shown to hold,
so this re-derives them, cheaply, from the same bars and call params, and returns one line:

    CAUSE_CODE: detail

It never changes a count, a signal or a status; the row carries it and the fence reads it.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _formula(df: pd.DataFrame, params: dict[str, Any]) -> str:
    from mt5desk.families import _h1

    from libs.research.alpha_grammar import evaluate, from_str, is_valid, terminal_frames

    expr = params.get("expr")
    if isinstance(expr, str) and "(" in expr:
        try:
            expr = from_str(expr)
        except ValueError:
            return f"FORMULA_INVALID: expression does not parse ({str(expr)[:80]})"
    if expr is None or not is_valid(expr):
        return f"FORMULA_INVALID: the production screen rejects {str(expr)[:80]}"
    norm = int(params.get("norm") or 240)
    entry_z = float(params.get("entry_z") or 1.5)
    d = _h1(df)
    need = max(2 * norm, 300)
    if len(d) < need:
        return f"FORMULA_SHORT_HISTORY: {len(d)} bars < {need} the family needs"
    frames = terminal_frames(d, raw=df, drivers=params.get("drivers"),
                             atr_n=int(params.get("atr_n") or 20))
    v = evaluate(expr, frames)
    r = v.rolling(norm, min_periods=norm)
    z = ((v - r.mean()) / r.std()).to_numpy(dtype=float)
    finite = np.isfinite(z)
    share = float(finite.mean()) if z.size else 0.0
    if finite.sum() < 0.05 * z.size:
        flat = {k: float(s.std()) for k, s in frames.items()
                if isinstance(s, pd.Series) and k in {"spread", "activity"}}
        return (f"FORMULA_DEGENERATE_SIGNAL: z finite on {share:.1%} of {z.size} bars (< 5%), "
                f"so the family refuses; feature std over the window "
                f"{float(np.nanstd(v.to_numpy(dtype=float))):.4g}; terminal std {flat}")
    peak = float(np.nanmax(np.abs(z[finite]))) if finite.any() else float("nan")
    if not np.isfinite(peak) or peak < entry_z:
        return (f"FORMULA_NO_THRESHOLD_CROSSING: max |z| {peak:.3f} < entry_z {entry_z} over "
                f"{int(finite.sum())} finite bars")
    return (f"SIGNALS_EXPECTED_BUT_NONE: max |z| {peak:.3f} >= entry_z {entry_z}; the session "
            f"filter or a modifier removed them")


def _residual(df: pd.DataFrame, params: dict[str, Any]) -> str:
    from mt5desk.factor_inputs import residual_floor
    from mt5desk.families import _h1

    factors = params.get("factors") or []
    if not factors:
        return "RESIDUAL_NO_FACTORS: the family was handed no factor frames"
    frame = _h1(df)[["close"]]
    for k, f in enumerate(factors):
        frame = frame.join(_h1(f)[["close"]].rename(columns={"close": f"x{k}"}), how="inner")
    rows = len(frame.dropna())
    floor = residual_floor(params)
    if rows < floor:
        return (f"RESIDUAL_FRAME_BELOW_FLOOR: the inner join holds {rows} rows < {floor} "
                f"(beta_win + 2*lookback)")
    return f"RESIDUAL_NO_THRESHOLD_CROSSING: {rows} joined rows, no |z| reached entry_z"


def zero_signal_cause(family: str, bars: Any, call_params: dict[str, Any], *,
                      n_signals: int) -> str:
    """One line naming why this replay holds no trade since SHADOW_START."""
    if n_signals > 0:
        return (f"SIGNALS_WITHOUT_TRADES: the family emitted {n_signals} signal(s) and the "
                f"backtest filled none after SHADOW_START (entry triggers or bar window)")
    if bars is None or len(bars) == 0:
        return "NO_BARS: the replay had no primary bars"
    p = dict(call_params or {})
    if family == "formula":
        return _formula(bars, p)
    if family in {"cross_asset_residual", "pca_residual"}:
        return _residual(bars, p)
    return f"FAMILY_EMITTED_NO_SIGNALS: {family} returned none on {len(bars)} bars"
