import subprocess
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && PYTHONPATH=desks/mt5 /home/quant/quant-platform/.venv/bin/python -c 'from mt5desk.families import FAMILY_REGISTRY; [print(k, v.get(\"defaults\",{})) for k,v in FAMILY_REGISTRY.items()]'"],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:300])