#!/usr/bin/env python3
from pathlib import Path

p = Path("/home/quant/quant-platform/libs/research/mechanism_census.py")
src = p.read_text()

old = '''    "funding_stress_reversal": "positioning_crowding_unwind",'''
new = '''    "funding_stress_reversal": "positioning_crowding_unwind",
    # Same payer as funding_stress_reversal -- the crowded levered book -- measured from the
    # CFTC COT weekly positioning print rather than the venue funding print. Two meters of one
    # mechanism, not two mechanisms; the census says so and the divergence register agrees.
    "cot_positioning_reversal": "positioning_crowding_unwind",'''
if old not in src:
    print("census anchor not found")
    raise SystemExit(2)
src = src.replace(old, new)
p.write_text(src)
print("Patched mechanism_census.py")