#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/quant/quant-platform')
from libs.research.screen_conversion import canonical_row, is_scored_row
from pathlib import Path
import json

doc = json.load(open('/home/quant/quant-platform/reports/axis_screens/perpdex_funding.json'))
screen_outputs = doc.get('screen_outputs', [])
print(f"screen_outputs: {len(screen_outputs)} rows")
for i, raw in enumerate(screen_outputs):
    if is_scored_row(raw):
        cell = canonical_row(raw, i)
        print(f"Row {i}: scored=True, name={cell.get('name')}, ic={cell.get('ic')}, verdict={cell.get('verdict')}")
    else:
        print(f"Row {i}: scored=False, keys={list(raw.keys())}")

# Test matching
trial = "perpdex_funding::aster_BTCUSDT_level_rate::8h"
print(f"\nLooking for trial: {trial}")
for i, raw in enumerate(screen_outputs):
    if is_scored_row(raw):
        cell = canonical_row(raw, i)
        if str(cell.get("name")) == trial:
            print(f"MATCH at row {i}: {cell.get('name')}")