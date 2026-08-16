#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/scheduler_manifest_report.json') as f:
    d = json.load(f)
print(json.dumps(d.get('checks', []), indent=2)[:2000])