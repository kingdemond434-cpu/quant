#!/usr/bin/env python3
import pandas as pd
df = pd.read_parquet('/home/quant/quant-platform/data/x_signals.parquet')
print('Rows:', len(df))
if len(df) > 0:
    latest = df.iloc[-1]
    print('Timestamp:', latest.get('timestamp'))
    print('Raw tweets:', latest.get('raw_count'))
    print('Symbols:', len(latest.get('symbols', {})))
    print('Narratives:', list(latest.get('narratives', {}).keys()))
    print('Top symbols:')
    for k, v in sorted(latest.get('symbols', {}).items(), key=lambda x: -x[1].get('score', 0))[:10]:
        print(f'  {k}: score={v.get("score",0):.3f} mentions={v.get("mentions",0)}')
    print('Top narratives:')
    for k, v in sorted(latest.get('narratives', {}).items(), key=lambda x: -x[1].get('score', 0))[:10]:
        print(f'  {k}: score={v.get("score",0):.3f} count={v.get("count",0)}')