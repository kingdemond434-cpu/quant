"""Enrich the liquid perp lake with funding + taker-flow + perp-spot basis (free, full history).

Re-fetches the top-N liquid USDT perps with daily_enriched (adds ``taker_buy_frac`` and ``basis``
columns alongside ``funding``), so the crypto portfolio engine can build the basis-carry and
taker-flow sleeves. One-time + daily-refreshable. Network-heavy (perp + spot klines per symbol).

    python scripts/ingest_crypto_enriched.py --top 80
"""

from __future__ import annotations

import argparse

from libs.data.crypto_source import daily_enriched, list_liquid_perps
from libs.data.instruments import AssetClass, InstrumentSpec, register_instrument
from libs.data.lake import Layer, ParquetLake
from libs.data.timeframe import Timeframe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=80)
    ap.add_argument("--start", default="2019-01-01")
    args = ap.parse_args()

    lake = ParquetLake("data/lake")
    universe = list_liquid_perps(top_n=args.top)
    print(f"enriching {len(universe)} liquid perps (funding + taker_buy_frac + basis)...")
    ok = 0
    for i, sym in enumerate(universe, 1):
        try:
            bars = daily_enriched(sym, start=args.start)
        except Exception as e:  # skip transient symbol failures
            print(f"  {sym} FAIL {e!r}"[:90])
            continue
        if bars.empty or len(bars) < 250:
            continue
        register_instrument(InstrumentSpec(symbol=sym, asset_class=AssetClass.CRYPTO,
                                           description=sym))
        lake.write_bars(Layer.BRONZE, sym, Timeframe.D1, bars)
        ok += 1
        if i % 20 == 0:
            print(f"  [{i}/{len(universe)}] {sym} bars={len(bars)} "
                  f"basis~{bars['basis'].tail(30).mean():.4f}")
    print(f"\nenriched {ok}/{len(universe)} perps with basis + taker flow")


if __name__ == "__main__":
    main()
