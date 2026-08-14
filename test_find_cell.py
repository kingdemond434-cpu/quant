#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/quant/quant-platform')
from libs.research.screen_conversion import canonical_row, is_scored_row
from pathlib import Path
import json

_ROOT = Path("/home/quant/quant-platform")

# Test _find_cell logic for perpdex
artifact = "reports/axis_screens/perpdex_funding.json"
key = "screen_outputs"
trial = "perpdex_funding::aster_BTCUSDT_level_rate::8h"

doc = json.load(open(_ROOT / artifact))
rows = doc.get(key)
print(f"rows type: {type(rows)}, len: {len(rows) if isinstance(rows, list) else 'N/A'}")

from libs.research.screen_conversion import canonical_row, is_scored_row

for i, raw in enumerate(rows):
    if is_scored_row(raw):
        cell = canonical_row(raw, i)
        if str(cell.get("name")) == trial:
            print(f"MATCH at row {i}: {cell.get('name')}")
            print(f"  ic: {cell.get('ic')}")
            print(f"  n_eff: {cell.get('n_eff')}")
            print(f"  verdict: {cell.get('verdict')}")
            break
else:
    print("NO MATCH")