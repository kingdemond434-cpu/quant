import json, collections
d = json.load(open(r"data\hypotheses\orthogonal_candidates.json"))
print("top-level type:", type(d).__name__, "keys:" , list(d)[:8] if isinstance(d, dict) else len(d))
rows = d.get("candidates") if isinstance(d, dict) else d
if isinstance(rows, dict):
    rows = list(rows.values())
if not isinstance(rows, list):
    for k in ("rows", "cells", "items"):
        if isinstance(d.get(k), list):
            rows = d[k]; break
print("rows:", len(rows) if isinstance(rows, list) else "n/a")
if isinstance(rows, list) and rows:
    c = collections.Counter(str((r or {}).get("family", "?")) for r in rows if isinstance(r, dict))
    for k, v in c.most_common(12):
        print("   %-26s %5d" % (k, v))
    print("  sample row keys:", list(rows[0])[:12])
if isinstance(d, dict) and "testability" in json.dumps(d)[:2000]:
    print("  (artifact carries testability reporting)")
