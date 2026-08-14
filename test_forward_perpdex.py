#!/usr/bin/env python3
import sys
sys.path.insert(0, '/home/quant/quant-platform')
from pathlib import Path
import json

_ROOT = Path("/home/quant/quant-platform")

# Simulate the forward runner's logic for perpdex
name = "perpdex_funding::aster_BTCUSDT_level_rate::8h"
state = json.load(open(_ROOT / "data" / f"{name}_shadow_state.json"))
print(f"State loaded: shadow_start={state.get('shadow_start')}")
print(f"  artifact={state.get('origin_artifact')}")
print(f"  key={state.get('origin_key')}")
print(f"  trial={state.get('trial')}")

from libs.research.screen_conversion import canonical_row, is_scored_row
from libs.research.screen_conversion import canonical_row as _canonical_row, is_scored_row as _is_scored_row

def _load(path: Path) -> any | None:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None

def _find_cell(root: Path, artifact: str, key: str, trial: str) -> dict[str, any] | None:
    doc = _load(root / artifact) if artifact else None
    if not isinstance(doc, dict):
        return None
    rows = doc.get(key)
    if not isinstance(rows, list):
        return None
    for i, raw in enumerate(rows):
        if not is_scored_row(raw):
            continue
        cell = canonical_row(raw, i)
        if str(cell.get("name")) == trial:
            return cell
    return None

# Test _find_cell
cell = _find_cell(_ROOT, "reports/axis_screens/perpdex_funding.json", "screen_outputs", "perpdex_funding::aster_BTCUSDT_level_rate::8h")
if cell:
    print(f"FOUND: ic={cell.get('ic')}, n_eff={cell.get('n_eff')}, verdict={cell.get('verdict')}")
else:
    print("NOT FOUND")