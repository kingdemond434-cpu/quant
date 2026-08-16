#!/usr/bin/env python3
from pathlib import Path
import json
root = Path('/home/quant/quant-platform')
f = root / 'data/scheduler_manifest_report.json'
print('exists:', f.exists())
if f.exists():
    d = json.loads(f.read_text())
    print('checks type:', type(d.get('checks')))
    print('checks keys:', list(d.get('checks', {}).keys()))
    print('all_pass:', d.get('all_pass'))