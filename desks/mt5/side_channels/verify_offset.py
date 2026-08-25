#!/usr/bin/env python3
from libs.autodiscovery.crypto_adapter import load_universe
from libs.data.timeframe import Timeframe

for off in (0, 3):
    syms, prov = load_universe(Timeframe.D1, limit=2, offset=off, min_bars=100)
    print(f"offset={off}: {syms}")
for s in ["BTCUSDT", "SOLUSDT"]:
    ms = prov(s)
    print(s, "cot:", ms.cot_spec_share is not None, "| bars:", len(ms))