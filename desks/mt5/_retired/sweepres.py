import json, os, time
p = r"data\hypotheses\orthogonal_candidates.json"
print("  mtime:", time.strftime("%H:%M:%S", time.localtime(os.path.getmtime(p))))
d = json.load(open(p))
print("  keys:", list(d))
for k in ("candidates", "hypotheses", "cells"):
    v = d.get(k)
    if isinstance(v, list):
        print(f"  {k}: {len(v)}")
        pooled = [x for x in v if isinstance(x, dict) and x.get("pooled")]
        print(f"    of which POOLED: {len(pooled)}")
        for x in pooled[:4]:
            print(f"      {x.get('family'):24s} days={x.get('trade_days')} "
                  f"trades={x.get('trades')} exp={x.get('exp_r'):+.3f}R "
                  f"members={len(x.get('members') or [])}")
        for x in v[:3]:
            if not x.get("pooled"):
                print(f"      cell {x.get('family')}/{x.get('symbol')} exp={x.get('exp_r')}")
print("  symbols swept:", d.get("symbols"))
print("  families_ran:", sum((d.get("families_ran") or {}).values()) if isinstance(d.get("families_ran"), dict) else d.get("families_ran"))
