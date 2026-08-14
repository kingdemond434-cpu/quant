#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/perpdex_funding.jsonl') as f:
    lines = f.readlines()
print(f"Total rows: {len(lines)}")
for l in lines[-5:]:
    print(json.loads(l))