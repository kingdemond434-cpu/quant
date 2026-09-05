import os
import subprocess
r = subprocess.run(
    ["ssh", os.environ.get("QUANT_VPS", "quant@VPS_HOST_REDACTED"),
     '/home/quant/quant-platform/.venv/bin/python -c \'import json; d=json.load(open("/home/quant/quant-platform/desks/mt5/data/universe/universe.json")); cats={}; [cats.setdefault(v.get("category","?"),[]).append(k) for k,v in d.items()]; print(len(d),"symbols"); [print("  "+c+": "+str(len(v))) for c,v in sorted(cats.items())]\''],
    capture_output=True, text=True, timeout=30
)
print(r.stdout.strip())
if r.stderr:
    print("ERR:", r.stderr[:300])
