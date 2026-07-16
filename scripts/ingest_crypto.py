"""Ingest crypto perp daily OHLCV + funding (Level-3) into the Parquet lake.

The funding rate rides along as an extra column on the canonical bar frame, so the existing lake
stores it unchanged. This is the highest-information, free, solo-accessible data we ranked top.

    python scripts/ingest_crypto.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from libs.data.crypto_source import bars_with_funding, list_liquid_perps, list_perp_symbols
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe

_INTERVAL_TF = {"1d": Timeframe.D1, "8h": Timeframe.H8}

_UNIVERSE = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
)
_OUT = Path("reports/crypto_coverage.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default=",".join(_UNIVERSE))
    parser.add_argument("--universe", choices=("list", "all", "liquid"), default="list",
                        help="'all'=every USDT perp; 'liquid'=top-N by 24h volume (tradeable)")
    parser.add_argument("--max-symbols", type=int, default=0, help="0 = no cap")
    parser.add_argument("--start", default="2019-01-01")
    parser.add_argument("--base", default="data/lake")
    parser.add_argument("--interval", choices=("1d", "8h"), default="1d")
    args = parser.parse_args()
    if args.universe == "liquid":
        symbols = list_liquid_perps(top_n=args.max_symbols or 100)
    elif args.universe == "all":
        symbols = list_perp_symbols()
    else:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    if args.max_symbols:
        symbols = symbols[: args.max_symbols]
    timeframe = _INTERVAL_TF[args.interval]
    print(f"universe: {len(symbols)} perps, interval={args.interval}")

    lake = ParquetLake(args.base)
    coverage: list[dict[str, object]] = []
    for i, sym in enumerate(symbols, 1):
        register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass.CRYPTO,
                                           description=f"{sym} perp"))
        try:
            df = bars_with_funding(sym, interval=args.interval, start=args.start)
        except Exception as exc:  # network/symbol issue -> record and continue
            print(f"  [{i}/{len(symbols)}] {sym} FAILED: {exc}")
            coverage.append({"symbol": sym, "bars": 0, "error": str(exc)[:80]})
            continue
        if df.empty or len(df) < 250:
            print(f"  [{i}/{len(symbols)}] {sym} insufficient ({0 if df.empty else len(df)})")
            coverage.append({"symbol": sym, "bars": 0 if df.empty else len(df)})
            continue
        lake.write_bars(Layer.BRONZE, sym, timeframe, df)
        fmean = float(df["funding"].mean())
        coverage.append({"symbol": sym, "bars": len(df),
                         "first": str(df["timestamp"].iloc[0].date()),
                         "last": str(df["timestamp"].iloc[-1].date()),
                         "avg_daily_funding": round(fmean, 6)})
        print(f"  [{i}/{len(symbols)}] {sym}: {len(df)} bars "
              f"{df['timestamp'].iloc[0].date()}..{df['timestamp'].iloc[-1].date()} "
              f"avg_funding={fmean:.5f}")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(coverage, indent=2), "utf-8")
    ok = [c for c in coverage if c.get("bars", 0)]
    print(f"\nCRYPTO INGEST COMPLETE -> {_OUT}  ({len(ok)}/{len(symbols)} symbols with data)")


if __name__ == "__main__":
    main()
