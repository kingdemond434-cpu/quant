import subprocess
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && git status --short 2>&1"],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:300])