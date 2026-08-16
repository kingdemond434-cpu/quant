#!/usr/bin/env python3
import sys

sys.path.insert(0, '/home/quant/quant-platform')
from libs.research.slot_registry import derive_slots

d = derive_slots()
print(f'm_concurrent: {d.get("m_concurrent")}')
print(f'm_upper: {d.get("m_upper")}')
print(f'cap: {d.get("cap")}')
print(f'complete: {d.get("complete")}')
print(f'over_cap: {d.get("over_cap")}')
print(f'idle_slots: {d.get("idle_slots")}')
for s in d.get('slots', []):
    print(f'  {s.get("name")}: {s}')
