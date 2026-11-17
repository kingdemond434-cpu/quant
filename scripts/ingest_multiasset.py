"""Targeted multi-asset D1 ingest for the cross-asset edge search (warm-terminal fast path).

Pulls a CURATED liquid cross-asset universe (FX majors/crosses, metals, energy, equity indices,
crypto CFDs) via ``copy_rates_range`` -- which is fast for symbols the terminal already cached and
returns nothing quickly for cold ones (no long retry budget wasted). Writes the canonical Bronze
bar frame into the existing ParquetLake so the cross-asset research reads it like any other source.

This is the honest MT5 data-breadth lever: land every asset class the demo broker actually has, so a
diversified cross-asset portfolio can be tested -- not just FX (which already returned 0 survivors).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.schema import BAR_COLUMNS
from libs.data.timeframe import Timeframe

# Curated liquid cross-asset universe. (symbol, asset_class) -- cold ones simply land 0 and skip.
_UNIVERSE: dict[AssetClass, tuple[str, ...]] = {
    AssetClass.FX: (
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "EURJPY", "GBPJPY", "EURGBP", "AUDJPY",
    ),
    AssetClass.METAL: (
        "XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD",
    ),
    AssetClass.ENERGY: (
        "XTIUSD", "XBRUSD", "XNGUSD",
    ),
    AssetClass.INDEX: (
        "US500", "US30", "NAS100", "US2000", "GER40", "UK100", "JPN225", "EU50",
    ),
    AssetClass.CRYPTO: (
        "BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD", "BCHUSD", "ADAUSD", "DOTUSD", "SOLUSD",
    ),
}
_OUT = Path("reports/multiasset_coverage.json")


def _to_canonical(rates) -> pd.DataFrame:  # type: ignore[no-untyped-def]
    df = pd.DataFrame(rates)
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df["time"], unit="s", utc=True),
            "open": df["open"].astype("float64"),
            "high": df["high"].astype("float64"),
            "low": df["low"].astype("float64"),
            "close": df["close"].astype("float64"),
            "volume": df["tick_volume"].astype("float64"),
        }
    )[list(BAR_COLUMNS)]


def main(argv: list[str] | None = None) -> None:
    import MetaTrader5 as mt5

    # PINNED (2026-11-11): the box runs Fusion and FTMO side by side, and a pathless
    # `initialize()` took whichever terminal the bridge saw first. Attach by path (default: the
    # MT5 desk's terminal_path.txt), never launch from Session 0, refuse a foreign server.
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--terminal", default=None, help="terminal64.exe (default: the desk's)")
    ap.add_argument("--expected-prefix", default=None,
                    help="server prefix the account must carry (default: the desk's)")
    args = ap.parse_args(argv)
    desk = Path(__file__).resolve().parents[1] / "desks" / "mt5"
    if str(desk) not in sys.path:
        sys.path.insert(0, str(desk))
    from mt5desk.config import terminal_path
    from research.mt5_session import attach_or_initialize, venue_refusal

    path = args.terminal or terminal_path()
    if not attach_or_initialize(mt5, path=path, timeout=15000):
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    venue = {"expected_prefix": args.expected_prefix} if args.expected_prefix else {}
    why = venue_refusal(mt5, path, **venue)
    if why is not None:
        mt5.shutdown()
        raise SystemExit(f"refusing to run: wrong venue ({why})")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mt5.shutdown()
        raise SystemExit("refusing to run: not connected to a DEMO account")
    print(f"connected: server={acct.server}")

    lake = ParquetLake("data/lake")
    start = datetime(2008, 1, 1, tzinfo=UTC)
    now = datetime.now(tz=UTC)
    coverage: list[dict[str, object]] = []

    for ac, syms in _UNIVERSE.items():
        for name in syms:
            mt5.symbol_select(name, True)
            mt5.symbol_info_tick(name)
            time.sleep(0.1)
            rates = mt5.copy_rates_range(name, mt5.TIMEFRAME_D1, start, now)
            n = 0 if rates is None else len(rates)
            print(f"  {name:8} {ac.value:8} {n:5} bars", flush=True)
            if n == 0:
                coverage.append({"symbol": name, "asset_class": ac.value, "bars": 0})
                continue
            register_instrument(
                InstrumentSpec(symbol=name, asset_class=ac, description=name)
            )
            frame = _to_canonical(rates)
            lake.write_bars(Layer.BRONZE, name, Timeframe.D1, frame)
            coverage.append({
                "symbol": name, "asset_class": ac.value, "bars": len(frame),
                "first": str(frame["timestamp"].iloc[0].date()),
                "last": str(frame["timestamp"].iloc[-1].date()),
            })
    mt5.shutdown()

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(coverage, indent=2), "utf-8")
    got = [c for c in coverage if c["bars"]]
    by_class: dict[str, int] = {}
    for c in got:
        by_class[str(c["asset_class"])] = by_class.get(str(c["asset_class"]), 0) + 1
    total = sum(len(v) for v in _UNIVERSE.values())
    print(f"\nlanded {len(got)}/{total} symbols; by class: {by_class}")
    for c in sorted(got, key=lambda c: int(c["bars"]), reverse=True):  # type: ignore[arg-type]
        print(f"  {c['symbol']:8} {c['asset_class']:8} {c['bars']:5} bars  "
              f"{c['first']} -> {c['last']}")


if __name__ == "__main__":
    main()
