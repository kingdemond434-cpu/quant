"""Return gap-guard -- neutralize bad-print / data-error spikes before research or sizing.

A single corrupt CFD tick (or a price gap across a data hole) shows up as an implausible one-bar
return that can masquerade as a -33% day and dominate drawdown/leverage/fragility math.
``guard_close`` caps each instrument's per-bar LOG return at an asset-plausible bound and rebuilds
the path, so genuine moves survive but artifacts don't. The cap is point-wise (no look-ahead); the
cumsum only reconstructs the level. Real extremes (a true -15% crypto crash) are kept; only moves
beyond the bound (which for FX/indices are almost always data errors) are clipped.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Plausible max single-day absolute return by asset class (moves beyond this are treated as errors).
DEFAULT_CAPS: dict[str, float] = {
    "fx": 0.10, "metal": 0.15, "energy": 0.25, "index": 0.15, "crypto": 0.50, "equity": 0.20,
}


def guard_close(close: pd.DataFrame, caps: dict[str, float]) -> pd.DataFrame:
    """Return a copy of ``close`` with artifact spikes removed (per-symbol daily-return cap)."""
    cols: dict[str, pd.Series] = {}
    for col in close.columns:
        s = close[col].dropna()
        if len(s) < 2:
            cols[col] = close[col]
            continue
        lr = np.log(s).diff()
        cap = float(np.log1p(caps.get(col, 0.5)))
        rebuilt = np.exp(np.log(s.iloc[0]) + lr.clip(-cap, cap).fillna(0.0).cumsum())
        cols[col] = rebuilt.reindex(close.index)
    return pd.DataFrame(cols, index=close.index)
