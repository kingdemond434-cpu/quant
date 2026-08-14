#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/data/leverage_target.json'))
print('leverage:', d.get('leverage'))
print('confidence:', d.get('confidence'))
print('active:', d.get('active'))
print('gated_leverage:', d.get('gated_leverage'))
print('notional_per_leg:', d.get('notional_per_leg'))
print('growth_optimal:', d.get('growth_optimal'))
print('clean_since:', d.get('clean_since'))
print('plausibility_rail_fired:', d.get('plausibility_rail_fired'))