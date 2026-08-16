#!/usr/bin/env python3
import glob

import pyarrow.parquet as pq

# binance_metrics
files = glob.glob('/home/quant/quant-platform/data/lake/bronze/binance_metrics/BTCUSDT/**/*.parquet', recursive=True)
if files:
    pf = pq.ParquetFile(files[0])
    print('binance_metrics BTCUSDT columns:', pf.schema.names)

# oi_ls_daily
files = glob.glob('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily/BTCUSDT.jsonl')
if files:
    with open(files[0]) as f:
        import json
        line = f.readline()
        print('oi_ls_daily keys:', list(json.loads(line).keys()))

# perpdex
with open('/home/quant/quant-platform/data/perpdex_funding.jsonl') as f:
    line = f.readline()
    import json
    print('perpdex_funding keys:', list(json.loads(line).keys()))

# liquidations
import pandas as pd

liq = pd.read_parquet('/home/quant/quant-platform/data/liquidations.parquet')
print('liquidations columns:', list(liq.columns))
print('liquidations shape:', liq.shape)

# hyperliquid funding
hl = pd.read_parquet('/home/quant/quant-platform/data/hyperliquid_funding.parquet')
print('hyperliquid_funding columns:', list(hl.columns))
print('hyperliquid_funding shape:', hl.shape)
