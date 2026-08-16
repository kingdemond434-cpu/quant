#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/web/autodiscovery_crypto.json') as f:
    d = json.load(f)
print('Pilot:', d.get('pilot'))
print('Mechanism classes:', d.get('mechanism_class_counts'))
print('Survivors:', d.get('survivors'))