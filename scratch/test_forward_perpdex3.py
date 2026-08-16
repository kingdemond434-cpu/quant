#!/usr/bin/env python3
import sys

sys.path.insert(0, '/home/quant/quant-platform')
import json
from pathlib import Path

_ROOT = Path("/home/quant/quant-platform")

# Test _find_cell logic for perpdex
artifact = "reports/axis_screens/perpdex_funding.json"
key = "screen_outputs"
trial = "perpdex_funding::aster_BTCUSDT_level_rate::8h"

doc = json.load(open(_ROOT / artifact))
rows = doc.get(key)
print("rows type: {}, len: {}".format(type(rows), len(rows) if isinstance(rows, list) else 'N/A'))

from libs.research.screen_conversion import canonical_row, is_scored_row


def _load(path):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return None

def _find_cell(root, artifact, key, trial):
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
    print("FOUND: ic={}, n_eff={}, verdict={}".format(cell.get('ic'), cell.get('n_eff'), cell.get('verdict')))
else:
    print("NOT FOUND")

# Now test the forward observation logic
from libs.research.slot_admission import forward_resolution_days

baseline = {"ic": -0.0383, "n_eff": 5364.0, "horizon_days": 0.333333}
cell = {"ic": -0.0383, "n_eff": 5364.0, "horizon_days": 0.333333}

n_now = float(cell.get("n_eff") or cell.get("n") or 0.0)
ic_now = cell.get("ic")
n_0 = float(baseline.get("n_eff") or 0.0)
ic_0 = baseline.get("ic")
horizon = float(baseline.get("horizon_days") or cell.get("horizon_days") or 0.0)

print("n_now:", n_now)
print("ic_now:", ic_now)
print("n_0:", n_0)
print("ic_0:", ic_0)
print("horizon:", horizon)

if isinstance(ic_now, (int, float)) and horizon > 0:
    days, needed, bar_z = forward_resolution_days(float(ic_now), horizon, m=15)
    print("days:", days, "needed:", needed, "bar_z:", bar_z)

    if days > 3650.0:
        print("UNAFFORDABLE (>3650 days)")
    else:
        print("AFFORDABLE")

    added = n_now - float(baseline.get("n_eff") or 0.0)
    print("added:", added)

    if added <= 0:
        print("NO-EVIDENCE (added <= 0)")
    else:
        if isinstance(ic_now, (int, float)) and isinstance(baseline.get("ic"), (int, float)) and added > 0:
            ic_forward = (float(n_now) * float(ic_now) - float(baseline.get("n_eff") or 0.0) * float(baseline.get("ic"))) / added
            print("ic_forward_estimate:", ic_forward)
        print("ACCRUING")
