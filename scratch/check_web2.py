#!/usr/bin/env python3
import json

d = json.load(open('/home/quant/quant-platform/web/autodiscovery_crypto.json'))
print("cumulative_tested:", d.get('cumulative_tested'))
print("cumulative_survivors:", d.get('cumulative_survivors'))
print("survivors count:", len(d.get('survivors', [])))
for s in d.get('survivors', [])[:5]:
    print(f"  {s.get('family','?')}/{s.get('subtype','?')} on {s.get('symbol','?')} | status={s.get('status','?')} | validated={s.get('validation_status','?')}")
if 'this_cycle' in d:
    tc = d['this_cycle']
    print(f"\nThis cycle: tested={tc.get('tested')}, survivors={tc.get('survivors')}, rejected={tc.get('rejected')}")
