#!/usr/bin/env python3
import json
d = json.load(open('/home/quant/quant-platform/data/secrets/binance_live_spot.json'))
print('keys:', list(d.keys()))