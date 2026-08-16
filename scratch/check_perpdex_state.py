#!/usr/bin/env python3
import json

d = json.load(open('/home/quant/quant-platform/data/perpdex_funding_aster_BTCUSDT_level_rate_8h_shadow_state.json'))
print(list(d.keys()))
for k, v in d.items():
    print(f"{k}: {v}")
