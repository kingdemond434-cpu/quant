#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/spot_momentum.json') as f:
    d = json.load(f)
print('strategy:', d.get('strategy'))
print('symbols:', len(d.get('universe', [])))
print('weights:', len(d.get('target_weights', {})))
print('sharpe_excess:', d.get('sharpe_excess'))
print('n_days:', d.get('n_days'))
print('weights:')
for k, v in sorted(d.get('target_weights', {}).items(), key=lambda x: -x[1]):
    print(f'  {k}: {v:.4f}')