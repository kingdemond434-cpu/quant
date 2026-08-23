"""Acquire broker-native XAUUSD intraday bars for the screenshot scalp study.

This is deliberately data-only.  It refuses an account on which Python trading is allowed,
selects one symbol, and calls only the MT5 history API.  The output retains the broker's spread
column because a one-minute gold backtest without the contemporaneous spread is not evidence.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def _paged_rates(mt5, symbol: str, timeframe: int, bars: int):  # type: ignore[no-untyped-def]
    """Read backwards in 5k blocks, avoiding the terminal's native large-request crash."""
    pieces = []
    for offset in range(0, bars, 5_000):
        take = min(5_000, bars - offset)
        rates = mt5.copy_rates_from_pos(symbol, timeframe, offset, take)
        if rates is None or len(rates) == 0:
            break
        pieces.append(rates)
        if len(rates) < take:
            break
    if not pieces:
        return None
    # Offset zero is newest; canonical research order is oldest -> newest.
    import numpy as np

    return np.concatenate(list(reversed(pieces)))


def fetch(terminal: str, symbol: str, out_dir: Path, bars: int = 90_000) -> dict[str, int]:
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
            # 100k crash boundary and are paged in 5k blocks.
            for _ in range(15):
                rates = _paged_rates(mt5, symbol, timeframe, bars)
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
        terminal_info = mt5.terminal_info()
        (out_dir / "XAUUSD_scalp_source.json").write_text(json.dumps({
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_server": str(account.server),
            "source_company": str(terminal_info.company if terminal_info else ""),
            "account_trade_allowed": bool(account.trade_allowed),
            "symbol": symbol, "rows": result,
            "promotion_authority": "fusion" in str(account.server).lower(),
        }, indent=2), "utf-8")
        return result
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--bars", type=int, default=90_000)
    parser.add_argument("--out", type=Path, default=Path(__file__).parents[1] / "data" / "universe")
    args = parser.parse_args()
    result = fetch(args.terminal, args.symbol, args.out, args.bars)
    print(result)
    return 0 if all(result.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
