#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, '/home/quant/quant-platform')
from libs.research.slot_registry import derive_slots

d = derive_slots()
for s in d.get('slots', []):
    if 'perpdex' in str(s).lower():
        print(json.dumps(s, indent=2))
