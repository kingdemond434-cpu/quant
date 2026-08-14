#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/web/autodiscovery_crypto.json'))
print(list(d.keys()))
for k, v in d.items():
    print(f"{k}: {type(v)}")
if "cycles" in d:
    print(f"cycles: {len(d['cycles'])}")
    if d["cycles"]:
        last = d["cycles"][-1]
        print(f"last cycle keys: {list(last.keys())}")
        if "survivors" in last:
            print(f"survivors: {len(last['survivors'])}")
        if "tested" in last:
            print(f"tested: {last['tested']}")
        if "rejected" in last:
            print(f"rejected: {last['rejected']}")