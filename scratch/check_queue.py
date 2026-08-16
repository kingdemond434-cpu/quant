#!/usr/bin/env python3
import json

d = json.load(open('/home/quant/quant-platform/data/paper_sleeve_queue.json'))
print('Queued:', len(d.get('queued', [])))
for q in d.get('queued', []):
    if 'perpdex' in q.get('name', '').lower():
        print(f"  {q['name']}")
