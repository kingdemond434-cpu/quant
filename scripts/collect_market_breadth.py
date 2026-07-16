"""Daily market-breadth archiver: % of liquid perps above their 20/50-day MA + making 20-day highs.

Two uses: (1) a regime/breadth gate for trend sleeves (breadth confirms participation), (2) its own
forward dataset. Appends to data/market_breadth.parquet. Rides the executor flywheel (once/UTC-day).
Only the last ~70 daily bars per symbol are pulled, so it is cheap.

    python scripts/collect_market_breadth.py
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from libs.data.crypto_source import fetch_klines, list_liquid_perps

_LOG = Path("data/market_breadth.parquet")


def main() -> None:
    start_ms = int((time.time() - 70 * 86400) * 1000)
    above20 = above50 = newhigh = n = 0
    for sym in list_liquid_perps(top_n=80):
        try:
            df = fetch_klines(sym, interval="1d", start_ms=start_ms)
        except Exception:
            continue
        if df.empty or "close" not in df:
            continue
        c = df["close"].astype(float).to_numpy()
        if len(c) < 51:
            continue
        n += 1
        above20 += int(c[-1] > float(np.mean(c[-20:])))
        above50 += int(c[-1] > float(np.mean(c[-50:])))
        newhigh += int(c[-1] >= float(np.max(c[-20:])))
    if n == 0:
        raise SystemExit("no breadth captured (network?)")
    row = {"ts": datetime.now(tz=UTC), "n": n,
           "pct_above_20dma": round(100 * above20 / n, 1),
           "pct_above_50dma": round(100 * above50 / n, 1),
           "pct_new_20d_high": round(100 * newhigh / n, 1)}
    snap = pd.DataFrame([row])
    if _LOG.exists():
        snap = pd.concat([pd.read_parquet(_LOG), snap], ignore_index=True)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    snap.to_parquet(_LOG)
    print(f"breadth @ {row['ts'].date()}: >20DMA {row['pct_above_20dma']}% "
          f">50DMA {row['pct_above_50dma']}% new-high {row['pct_new_20d_high']}% (n={n})")


if __name__ == "__main__":
    main()
