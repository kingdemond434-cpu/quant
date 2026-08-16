#!/usr/bin/env python3
import os

import pandas as pd

saved = 0
for f in os.listdir('/home/quant/quant-platform/data/bars'):
    if f.endswith('.parquet'):
        p = f'/home/quant/quant-platform/data/bars/{f}'
        sz = os.path.getsize(p)
        df = pd.read_parquet(p)
        df.to_parquet(p, compression='zstd', compression_level=3)
        nsz = os.path.getsize(p)
        saved += sz - nsz
        print(f'{f}: {sz/1024/1024:.1f}MB -> {nsz/1024/1024:.1f}MB ({100*(sz-nsz)/sz:.0f}% saved)')

print(f'Total saved: {saved/1024/1024:.1f}MB')
