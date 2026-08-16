#!/usr/bin/env python3
import json

d = json.load(open('/home/quant/quant-platform/data/shadow_sleeves.json'))
print(f'Total: {len(d)}')
for s in d:
    print(f'  {s}')
