"""Daily archiver for Binance derivative metrics that are 30-day-capped (no deep history).

Open interest, global long/short account ratio, and taker buy/sell ratio cannot be backtested (the
API only serves ~30 days), so we snapshot them daily and accumulate our OWN history -- a future
alpha factory. Each run appends today's reading per liquid perp to data/crypto_metrics.parquet.
Schedule daily; every run adds information advantage.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.crypto_source import (
    fetch_long_short_ratio,
    fetch_open_interest,
    fetch_taker_ratio,
    list_liquid_perps,
)

_LOG = Path("data/crypto_metrics.parquet")


def main() -> None:
    ts = datetime.now(tz=UTC)
    rows: list[dict[str, object]] = []
    for sym in list_liquid_perps(top_n=100):
        try:
            oi = fetch_open_interest(sym)
            ls = fetch_long_short_ratio(sym)
            tk = fetch_taker_ratio(sym)
        except Exception:  # transient; skip this symbol today
            continue
        rows.append({
            "ts": ts, "symbol": sym, "open_interest": oi,
            "ls_ratio": float(ls["ls_ratio"].iloc[-1]) if not ls.empty else float("nan"),
            "taker_ratio": float(tk["taker_ratio"].iloc[-1]) if not tk.empty else float("nan"),
        })
    if not rows:
        raise SystemExit("no metrics captured (network?)")
    snap = pd.DataFrame(rows)
    if _LOG.exists():
        snap = pd.concat([pd.read_parquet(_LOG), snap], ignore_index=True)
    _LOG.parent.mkdir(parents=True, exist_ok=True)
    snap.to_parquet(_LOG)
    days = snap["ts"].dt.date.nunique()
    print(f"archived {len(rows)} symbols @ {ts.date()} -> {_LOG} "
          f"({len(snap)} rows, {days} distinct days)")


if __name__ == "__main__":
    main()
