#!/usr/bin/env python3
from libs.research.paper_sleeves import parse_screen_verdicts
from libs.research.slot_registry import derive_slots
from pathlib import Path

r = parse_screen_verdicts(Path('/home/quant/quant-platform/reports/axis_screens'))
cohort = derive_slots()

perpdex = [c for c in r['candidates'] if 'perpdex' in c.name.lower() or c.mechanism == 'perpdex_funding']
print("Perpdex candidates:")
for c in perpdex:
    print(f"  {c.name}")
    print(f"    root: {c.root}")
    print(f"    axis: {c.axis}")
    print(f"    verdict: {c.verdict}")
    print(f"    ic_t: {c.ic_t}, ic: {c.ic}")
    print()

# Check standing names
standing_names = set()
for s in cohort.get('slots', []):
    if isinstance(s, dict) and s.get('name'):
        standing_names.add(s['name'])

print("Standing names that might match perpdex:")
for name in standing_names:
    if 'perpdex' in name.lower():
        print(f"  {name}")

# Check perpdex roots against standing
for c in perpdex:
    if c.root in standing_names or c.name in standing_names:
        print(f"DUPED: {c.name} (root: {c.root}) matches standing")
    else:
        print(f"FRESH: {c.name} (root: {c.root})")