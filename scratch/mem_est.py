#!/usr/bin/env python3
import os

os.chdir("/home/quant/quant-platform")
from libs.autodiscovery.crypto_adapter import _MIN_BARS, _read_frames, crypto_symbols
from libs.data.timeframe import Timeframe

syms = crypto_symbols(Timeframe.D1)
frames = _read_frames(syms, Timeframe.D1, "data/lake")
eligible = [s for s in syms if len(frames[s]) >= _MIN_BARS]
print(f"total D1 symbols: {len(syms)}, eligible (>= {_MIN_BARS} bars): {len(eligible)}")

tot_bytes = 0
for s in eligible:
    tot_bytes += frames[s].memory_usage(deep=True).sum()
print(f"all frames combined: {tot_bytes/1e6:.1f} MB pandas memory")
print(f"~{tot_bytes/1e6/len(eligible):.1f} MB per symbol")
print(f"at cap 60: ~{tot_bytes/1e6/len(eligible)*60:.1f} MB")
print(f"at cap 100: ~{tot_bytes/1e6/len(eligible)*100:.1f} MB")
print(f"at cap 285: ~{tot_bytes/1e6:.1f} MB")
