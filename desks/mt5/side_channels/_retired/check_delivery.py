#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/claude_survivor_delivery.json') as f:
    d = json.load(f)
print('Total survivors:', d.get('total_survivors'))
print('Summary:', d.get('summary'))