#!/usr/bin/env python3
import json

d = json.load(open('/home/quant/quant-platform/reports/axis_screens/perpdex_funding.json'))
print("screen_interesting:")
for item in d.get('screen_interesting', []):
    print(f"  {json.dumps(item)}")
print("\nscreen_outputs (first 3):")
for item in d.get('screen_outputs', [])[:3]:
    print(f"  {json.dumps(item)}")
print("\nverdict_summary:")
print(json.dumps(d.get('verdict_summary'), indent=2))
