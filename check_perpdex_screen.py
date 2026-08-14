#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/reports/axis_screens/perpdex_funding.json'))
print(list(d.keys()))
for k, v in d.items():
    print(f"{k}: {type(v)}")