import os
import subprocess
r = subprocess.run(
    ["ssh", os.environ.get("QUANT_VPS", "quant@VPS_HOST_REDACTED"),
     "ls /home/quant/quant-platform/desks/mt5/data/universe/*_H1.parquet 2>/dev/null | wc -l; "
     "cat /home/quant/quant-platform/desks/mt5/data/universe/universe.json | .venv/bin/python -c 'import json,sys; d=json.load(sys.stdin); cats={}; [cats.setdefault(v.get(\"category\",\"?\"),[]).append(k) for k,v in d.items()]; print(f\"{len(d)} symbols\"); [print(f\"  {c}: {len(v)}\") for c,v in sorted(cats.items())]'"],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])
