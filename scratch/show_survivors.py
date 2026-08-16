#!/usr/bin/env python3
import json
with open('/home/quant/quant-platform/data/claude_survivor_delivery.json') as f:
    d = json.load(f)
for s in d['top_survivors']:
    print(f"{s['rank']:2d} | {s['source']:30s} | {str(s['family']):15s} | {str(s['subtype']):30s} | {str(s['symbol']):10s} | Q={s['quality_score']:.1f} | {s['verdict']}")