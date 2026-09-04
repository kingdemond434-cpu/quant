import os
import subprocess
r = subprocess.run(
    ["ssh", os.environ.get("QUANT_VPS", "quant@VPS_HOST_REDACTED"),
     '/home/quant/quant-platform/.venv/bin/python -c \'import json; d=json.load(open("/home/quant/quant-platform/desks/mt5/reports/universal_gates_external.json")); print("Survivors:", d["survivors_passing_all"]); print("PBO:", d["program_level"]["pbo"]); print("SPA p:", d["program_level"]["spa_p"]); print("Verdicts:", len(d["verdicts"])); [print(("PASS" if v["passed"] else "FAIL"), v["cell"][:80], "n="+str(v["days"])) for v in d["verdicts"][:30]]\''],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:300])