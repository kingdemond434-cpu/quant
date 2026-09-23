import subprocess

r = subprocess.run(["ssh", "quant@95.216.191.70",
    "cd /home/quant/quant-platform/desks/mt5 && "
    "PYTHONPATH=/home/quant/quant-platform/desks/mt5:/home/quant/quant-platform/desks/mt5/research "
    ".venv/bin/python research/growth_now.py 2>&1"],
    capture_output=True, text=True, timeout=120)
print(r.stdout[-4000:])
if r.stderr:
    print("STDERR:", r.stderr[-1000:])
