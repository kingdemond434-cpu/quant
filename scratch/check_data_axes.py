#!/usr/bin/env python3
import pyarrow.parquet as pq

# Check crypto columns
f = pq.ParquetFile('/home/quant/quant-platform/data/lake/bronze/crypto/BTCUSDT/D1/year=2026/month=8/part-0.parquet')
print('BTCUSDT D1 columns:', f.schema.names)

# Check binance_metrics
import os

for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/binance_metrics'):
    for f_name in files:
        if f_name.endswith('.parquet'):
            pf = pq.ParquetFile(os.path.join(root, f_name))
            print('binance_metrics columns:', pf.schema.names)
            break
    break

# Check oi_ls_daily
for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily'):
    for f_name in files:
        if f_name.endswith('.parquet'):
            pf = pq.ParquetFile(os.path.join(root, f_name))
            print('oi_ls_daily columns:', pf.schema.names)
            break
    break

# Check perpdex funding
import json

with open('/home/quant/quant-platform/data/perpdex_funding.jsonl') as f:
    line = f.readline()
    print('perpdex_funding keys:', list(json.loads(line).keys()))
