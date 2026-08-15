#!/usr/bin/env python3
import os
os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.crypto_adapter import load_universe
from libs.data.timeframe import Timeframe

s0, _ = load_universe(Timeframe.D1, limit=5, offset=0)
s60, _ = load_universe(Timeframe.D1, limit=5, offset=60)
s120, _ = load_universe(Timeframe.D1, limit=5, offset=120)
s295, _ = load_universe(Timeframe.D1, limit=10, offset=295)
print("offset 0   :", s0)
print("offset 60  :", s60)
print("offset 120 :", s120)
print("offset 295 :", s295)
assert s0 and s60 and s120 and s295, "slices must be non-empty"
assert not set(s0) & set(s60), "slices must not overlap"
print("OK: chunked slices work")