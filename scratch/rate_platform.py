#!/usr/bin/env python3
import json

with open('/home/quant/quant-platform/data/CAPABILITY_RATCHET.json') as f:
    d = json.load(f)
aspects = d.get('aspects', {})
vals = [v for v in aspects.values() if isinstance(v, (int, float))]
print(f"MEAN: {sum(vals)/len(vals):.2f}/10")
print(f"AT-CEILING (10/10): {[k for k,v in aspects.items() if v == 10.0]}")
print(f"UNMEASURED/MISSING: {[k for k,v in aspects.items() if v == '--' or isinstance(v, str)]}")
print(f"FELL: {[k for k in d.get('fell', [])]}")
print(f"BINDING CONSTRAINT: {d.get('binding_constraint', 'unknown')}")
