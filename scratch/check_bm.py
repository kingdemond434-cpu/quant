#!/usr/bin/env python3
import glob

import pyarrow.parquet as pq

files = glob.glob('/home/quant/quant-platform/data/lake/bronze/binance_metrics/BTCUSDT/**/*.parquet', recursive=True)
if files:
    pf = pq.ParquetFile(files[0])
    print('binance_metrics columns:', pf.schema.names)
