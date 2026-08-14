#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/data/claude_survivor_delivery.json'))
print(json.dumps(d, indent=2))