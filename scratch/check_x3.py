#!/usr/bin/env python3
import pandas as pd
df = pd.read_parquet('/home/quant/quant-platform/data/x_signals.parquet')
print('Rows:', len(df))
if len(df) > 0:
    latest = df.iloc[-1]
    print('Timestamp:', latest.get('timestamp'))
    print('Raw tweets:', latest.get('raw_count'))
    print('Symbols:', list(latest.get('symbols', {}).keys())[:20])
    print('Narratives:', list(latest.get('narratives', {}).keys()))
    print('Accounts checked:', latest.get('accounts_checked'))