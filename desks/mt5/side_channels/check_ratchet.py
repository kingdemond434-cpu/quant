#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/CAPABILITY_RATCHET.json') as f:
    d = json.load(f)
print('Status:', d.get('status'))
print('Mean:', d.get('measured_mean'))
print('Binding:', d.get('binding_constraint'))
print('Unmeasured:', d.get('n_unmeasured'))
print('FELL:', len(d.get('defects', [])))