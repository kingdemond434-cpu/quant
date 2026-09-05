#!/usr/bin/env python3
import pandas as pd
df = pd.read_parquet('/home/quant/quant-platform/data/x_signals.parquet')
latest = df.iloc[-1]
print('Timestamp:', latest.get('timestamp'))
print('Raw tweets:', latest.get('raw_count'))
print('Symbols:')
syms = latest.get('symbols', {}) or {}
for k, v in sorted(syms.items(), key=lambda x: -(x[1] or {}).get('engagement', 0))[:12]:
    v = v or {}
    print(f'  {k}: mentions={v.get("mentions",0)} engagement={v.get("engagement",0)} score={v.get("score",0):.3f}')
print('Narratives:')
narrs = latest.get('narratives', {}) or {}
for k, v in sorted(narrs.items(), key=lambda x: -(x[1] or {}).get('count', 0)):
    v = v or {}
    print(f'  {k}: count={v.get("count",0)} engagement={v.get("engagement",0)}')