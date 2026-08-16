#!/usr/bin/env python3
import os

import pyarrow.parquet as pq

for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/binance_metrics'):
    for f_name in files:
        if f_name.endswith('.parquet'):
            pf = pq.ParquetFile(os.path.join(root, f_name))
            print('binance_metrics columns:', pf.schema.names)
            break
    break

for root, dirs, files in os.walk('/home/quant/quant-platform/data/lake/bronze/oi_ls_daily'):
    for f_name in files:
        if f_name.endswith('.parquet'):
            pf = pq.ParquetFile(os.path.join(root, f_name))
            print('oi_ls_daily columns:', pf.schema.names)
            break
    break
