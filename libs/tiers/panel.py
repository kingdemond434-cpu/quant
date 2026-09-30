"""Timestamp-aligned OHLC frames from the desk's bar lake (`desks/mt5/data/universe/*_H1.parquet`).

Shared by the S05 program evolution and the S06 correlation-cluster axis. Read-only. Unlike a
tail-aligned return array, frames here keep their DatetimeIndex, so a correlation between an FX
pair (24x5) and a 24x7 instrument is computed on the hours both actually traded.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import numpy as np


def load_frames(universe: Path, symbols: Iterable[str] | None = None, *, bars: int = 3000,
                eligible: Callable[[str], bool] | None = None, max_symbols: int = 60,
                min_bars: int = 500) -> dict[str, Any]:
    """{symbol: DataFrame(open, high, low, close, ...)} -- the newest `bars` of each."""
    import pandas as pd
    out: dict[str, Any] = {}
    if not universe.exists():
        return out
    want = None if symbols is None else {str(s) for s in symbols}
    files = sorted(universe.glob("*_H1.parquet"), key=lambda p: -p.stat().st_size)
    for p in files:
        sym = p.name[: -len("_H1.parquet")]
        if want is not None and sym not in want:
            continue
        if eligible is not None and not eligible(sym):
            continue
        try:
            df = pd.read_parquet(p)
        except Exception:
            continue
        if not {"open", "high", "low", "close"} <= set(df.columns):
            continue
        df = df.tail(bars)
        c = pd.to_numeric(df["close"], errors="coerce")
        df = df[np.isfinite(c) & (c > 0)]
        if len(df) < min_bars:
            continue
        out[sym] = df
        if len(out) >= max_symbols:
            break
    return out


def log_returns(frames: dict[str, Any]) -> Any:
    """Timestamp-aligned H1 log returns, one column per symbol (NaN where a symbol had no bar)."""
    import pandas as pd
    cols = {s: np.log(f["close"].astype(float)).diff() for s, f in frames.items()}
    return pd.DataFrame(cols).sort_index().iloc[1:] if cols else pd.DataFrame()
