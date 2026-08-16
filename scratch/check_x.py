#!/usr/bin/env python3
import pandas as pd
df = pd.read_parquet('/home/quant/quant-platform/data/x_signals.parquet')
print(df.iloc[-1].to_dict())