#!/usr/bin/env python3
from libs.research.paper_sleeves import parse_screen_verdicts
from pathlib import Path
r = parse_screen_verdicts(Path('/home/quant/quant-platform/reports/axis_screens'))
print(r['status'])
print(f"Candidates: {len(r['candidates'])}")
for c in r['candidates']:
    print(f"  {c.name}: {c.verdict} ({c.mechanism})")