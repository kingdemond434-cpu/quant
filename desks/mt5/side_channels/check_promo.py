#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/promotion_gate.json') as f:
    d = json.load(f)
print('Rung:', d.get('granted_rung'))
print('Closed trades:', d.get('n_closed'))
print('Criteria:')
for k, v in d.get('criteria', {}).items():
    print(f'  {k}: {v.get("state")} - {v.get("why", "")[:80]}')