"""Fetch H1 history for the MT5 research universe (2018 -> now) and cache it.

Per-symbol cost model recorded (contract size, tick value, median spread).
Run with the VIG terminal logged in.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mt5desk.config import terminal_path

TERMINAL = terminal_path()
OUT = Path(r"C:\Users\dell\mt5-research\data\universe")
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = [
    "XAUUSD", "XAGUSD", "WTI", "BRENT", "USOIL",
    "US500", "US30", "USTEC", "NAS100", "SPX500",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY", "GBPJPY",
    "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP",
    "EURCHF", "AUDJPY", "CADJPY", "NZDJPY", "CHFJPY",
    "BTCUSD", "ETHUSD",
]

START = datetime(2018, 1, 1, tzinfo=timezone.utc)


def main() -> None:
    if mt5.terminal_info() is None:
        if not mt5.initialize(path=TERMINAL):
            print(f"initialize failed: {mt5.last_error()}")
            return
    print(f"terminal: {mt5.terminal_info().name} | account {mt5.account_info().login}")

    summary = {}
    for sym in CANDIDATES:
        info = mt5.symbol_info(sym)
        if info is None:
            print(f"{sym:8s} not offered")
            continue
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_H1, START, datetime.now(timezone.utc))
        if rates is None or len(rates) < 1000:
            print(f"{sym:8s} insufficient history ({0 if rates is None else len(rates)} bars)")
            continue
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time").sort_index()
        df = df[["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
        df.to_parquet(OUT / f"{sym}_H1.parquet")
        med_spread = float(df["spread"].median())
        summary[sym] = {
            "bars": len(df),
            "first": str(df.index.min()),
            "last": str(df.index.max()),
            "contract_size": float(info.trade_contract_size),
            "tick_size": float(info.trade_tick_size),
            "tick_value": float(info.trade_tick_value),
            "min_volume": float(info.volume_min),
            "volume_step": float(info.volume_step),
            "median_spread_pts": med_spread,
        }
        print(f"{sym:8s} {len(df):6d} bars {df.index.min().date()} -> {df.index.max().date()} "
              f"contract={info.trade_contract_size} spread_med={med_spread:.1f}pts")
    (OUT / "universe.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n{len(summary)} symbols cached -> {OUT}")


if __name__ == "__main__":
    main()