import subprocess
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && PYTHONPATH=desks/mt5 .venv/bin/python -c 'from mt5desk.families import FAMILY_REGISTRY; print(\"OK:\", len(FAMILY_REGISTRY), \"families\")' 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:500])
