#!/usr/bin/env python3
from pathlib import Path
import json
root = Path('/home/quant/quant-platform')
f = root / 'data/scheduler_manifest_report.json'
print('exists:', f.exists())
if f.exists():
    d = json.loads(f.read_text())
    print('checks:', json.dumps(d.get('checks', []), indent=2)[:2000])