"""Incremental tail refresh for cached MT5 universe parquets.

Fetches only recent bars per symbol, appends new CLOSED bars to the
existing parquet, dedupes by timestamp, saves in-place.
Run on the Windows box where MetaTrader5 is available.
"""

import sys
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import terminal_path

TERMINAL = terminal_path()
OUT = Path(r"C:\Users\dell\mt5-research\data\universe")
N_BARS = 200


def refresh_symbol(sym: str) -> str:
    pq = OUT / f"{sym}_H1.parquet"
    if not pq.exists():
        return "no-cache"
    old = pd.read_parquet(pq)
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, N_BARS)
    if rates is None or len(rates) < 2:
        return f"fetch-fail({mt5.last_error()})"
    new = pd.DataFrame(rates)
    new["time"] = pd.to_datetime(new["time"], unit="s", utc=True)
    new = new.set_index("time").sort_index()
    # drop the still-forming bar
    new = new.iloc[:-1]
    new = new[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
    combined = pd.concat([old, new])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    added = len(combined) - len(old)
    combined.to_parquet(pq)
    return f"+{added} bars (last {combined.index.max()})"


def main() -> None:
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=TERMINAL):
            print(f"initialize failed: {mt5.last_error()}")
            sys.exit(1)
    results = []
    for pq in sorted(OUT.glob("*_H1.parquet")):
        sym = pq.stem.replace("_H1", "")
        try:
            status = refresh_symbol(sym)
        except Exception as e:
            status = f"error:{e}"
        results.append(f"{sym:8s} {status}")
        print(results[-1], flush=True)
    ok = sum(1 for r in results if r.split(None, 1)[1].startswith("+"))
    print(f"\n{ok}/{len(results)} symbols refreshed")
    mt5.shutdown()


if __name__ == "__main__":
    main()
