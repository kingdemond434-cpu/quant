"""USDX, BUILT FROM THE SIX FUSION MAJORS THE ICE FORMULA NAMES -- a factor, never a trade.

Fusion does not quote the dollar index, yet the miners name `USDX` as a residual factor and the
country packs name it as a transmission target. Measured on the trading box 2026-09-29: 36
forward clocks sat BLOCKED_INPUTS_UNAVAILABLE on "factor bars unavailable for ['USDX']", and every
cross_asset_residual cell on a dollar factor failed to build, for want of a file.

The ICE definition is a fixed geometric basket of six USD crosses, all of which Fusion quotes:

    USDX = 50.14348112 * EURUSD^-0.576 * USDJPY^0.136 * GBPUSD^-0.119
                       * USDCAD^0.091  * USDSEK^0.042 * USDCHF^0.036

WHAT IT IS AND IS NOT. Open and close are exact (the formula applied to the legs' opens and
closes). High and low are NOT: a basket's extreme is not the product of its legs' extremes, so
they are written as max/min(open, close) and the file says so in `synthetic`. That is right for a
factor, which reads closes; it would be wrong for anything that trades USDX off its range, and
nothing can: tradeability comes from the broker registry, where USDX does not exist.

POINT IN TIME. Bars are joined on their exact timestamps (inner join), never forward-filled, so
a USDX bar exists only where every leg printed that bar. All six legs are required: a partial
basket is a different index, and a missing leg means no file rather than a wrong one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
UNIVERSE = BASE / "data" / "universe"
TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")
#: The artifact this organ is attested by: the H1 series every factor consumer reads first.
ARTIFACT = UNIVERSE / "USDX_H1.parquet"
CONSTANT = 50.14348112
WEIGHTS = {"EURUSD": -0.576, "USDJPY": 0.136, "GBPUSD": -0.119, "USDCAD": 0.091,
           "USDSEK": 0.042, "USDCHF": 0.036}


def _leg(sym: str, tf: str, root: Path) -> pd.DataFrame | None:
    p = root / f"{sym}_{tf}.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "time" in df.columns:
        df = df.set_index("time")
    df.index = pd.to_datetime(df.index, utc=True)
    return df[["open", "close"]].astype(float)


def build(tf: str, root: Path = UNIVERSE) -> pd.DataFrame | None:
    """The USDX bars for `tf`, or None when any leg is absent or the join is empty."""
    legs = {s: _leg(s, tf, root) for s in WEIGHTS}
    if any(v is None or v.empty for v in legs.values()):
        return None
    idx = None
    for v in legs.values():
        idx = v.index if idx is None else idx.intersection(v.index)
    if idx is None or len(idx) == 0:
        return None
    out = {}
    for col in ("open", "close"):
        log = np.log(CONSTANT) + sum(w * np.log(legs[s].loc[idx, col].to_numpy())
                                     for s, w in WEIGHTS.items())
        out[col] = np.exp(log)
    frame = pd.DataFrame(out, index=idx).sort_index()
    frame["high"] = frame[["open", "close"]].max(axis=1)
    frame["low"] = frame[["open", "close"]].min(axis=1)
    frame["tick_volume"] = 0
    frame["spread"] = 0
    frame["real_volume"] = 0
    frame.index.name = "time"
    frame = frame[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
    frame.attrs["synthetic"] = "ICE USDX formula over six Fusion legs; high/low = max/min(o,c)"
    return frame


def main(root: Path = UNIVERSE) -> int:
    for tf in TIMEFRAMES:
        frame = build(tf, root)
        if frame is None:
            missing = [s for s in WEIGHTS if not (root / f"{s}_{tf}.parquet").exists()]
            print(f"USDX {tf}: not built -- missing leg(s) {missing or 'none (empty join)'}")
            continue
        frame.to_parquet(root / f"USDX_{tf}.parquet")
        print(f"USDX {tf}: {len(frame)} bars {frame.index.min()} -> {frame.index.max()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
