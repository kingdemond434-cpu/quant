#!/usr/bin/env python3
import os, sys
os.chdir("/home/quant/quant-platform")
import pyarrow.parquet as pq
import glob

files = sorted(glob.glob("data/lake/bronze/crypto/BTCUSDT/D1/**/*.parquet", recursive=True))
print(f"cwd={os.getcwd()} found {len(files)} parquet files for BTCUSDT D1")
if files:
    f = files[-1]
    print("latest file:", f)
    pf = pq.ParquetFile(f)
    print("rows:", pf.metadata.num_rows)
    print("schema:")
    print(pf.schema_arrow)

from libs.autodiscovery.crypto_adapter import crypto_symbols
from libs.data.timeframe import Timeframe
syms = crypto_symbols(Timeframe.D1)
print(f"\ncrypto_symbols(D1) -> {len(syms)} symbols")
print(syms[:10])
syms8 = crypto_symbols(Timeframe.H8)
print(f"crypto_symbols(H8) -> {len(syms8)} symbols")