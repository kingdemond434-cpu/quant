"""Acquire broker-native XAUUSD intraday bars for the screenshot scalp study.

This is deliberately data-only.  It refuses an account on which Python trading is allowed,
selects one symbol, and calls only the MT5 history API.  The output retains the broker's spread
column because a one-minute gold backtest without the contemporaneous spread is not evidence.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd


def fetch(terminal: str, symbol: str, out_dir: Path, bars: int = 30_000) -> dict[str, int]:
    import MetaTrader5 as mt5

    if not mt5.initialize(path=terminal, timeout=15_000):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        account = mt5.account_info()
        if account is None:
            raise RuntimeError("MT5 account unavailable")
        if bool(account.trade_allowed):
            raise RuntimeError("refusing history job: account permits trading")
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"cannot select {symbol}: {mt5.last_error()}")
        frames = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
        }
        result: dict[str, int] = {}
        out_dir.mkdir(parents=True, exist_ok=True)
        for label, timeframe in frames.items():
            rates = None
            # Bounded retries let a cold terminal cache warm. Requests stay below MT5's native
            # 100k crash boundary; thirty thousand bars is 20 trading days on M1 and over a year
            # on M15, enough for a first falsification without destabilising the terminal.
            for _ in range(15):
                rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
                if rates is not None and len(rates):
                    break
                time.sleep(1.0)
            if rates is None or len(rates) == 0:
                result[label] = 0
                continue
            frame = pd.DataFrame(rates)
            frame.index = pd.to_datetime(frame.pop("time"), unit="s", utc=True)
            frame.index.name = "timestamp"
            frame.to_parquet(out_dir / f"XAUUSD_{label}.parquet")
            result[label] = len(frame)
        return result
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--bars", type=int, default=30_000)
    parser.add_argument("--out", type=Path, default=Path(__file__).parents[1] / "data" / "universe")
    args = parser.parse_args()
    result = fetch(args.terminal, args.symbol, args.out, args.bars)
    print(result)
    return 0 if all(result.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
