#!/usr/bin/env python3
import json
from datetime import UTC, datetime

# Create shadow state for existing perpdex clock
state = {
    "shadow_start": "2026-08-13T10:00:00.000000+00:00",  # Approximate when perpdex screen started
    "origin": "run_paper_sleeve_spawner (R0102): auto-spawned PAPER sleeve from perpdex_funding; accrues forward evidence only, never touches capital (L1.6)",
    "axis": "perpdex_funding (R0100 axis 5 -- access-segmented venue funding cohort)",
    "trial": "perpdex_funding::aster_BTCUSDT_level_rate::8h",
    "screen_report": "reports/axis_screens/perpdex_funding.json",
    "screen_verdict": "SCREEN-INTERESTING",
    "source_kind": "axis_screen",
    "pnl_artifact": "",
    "pnl_key": "",
    "baseline_window_end": "2026-08-13T10:00:00.000000+00:00",
    "baseline": {
        "n_eff": 5364.0,
        "ic": -0.0383,
        "horizon_days": 0.3333333333333333,
        "captured_at_spawn": True
    },
    "origin_artifact": "reports/axis_screens/perpdex_funding.json",
    "origin_key": "screen_outputs",
    "mechanism": "perpdex_funding"
}

with open('/home/quant/quant-platform/data/perpdex_funding::aster_BTCUSDT_level_rate::8h_shadow_state.json', 'w') as f:
    json.dump(state, f, indent=1)
    f.write('\n')

print("Created shadow state file")