#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/scheduler_manifest_report.json') as f:
    d = json.load(f)
print('checks:', len(d.get('checks', [])))
print('all_pass:', d.get('all_pass'))
print('keys:', list(d.keys()))