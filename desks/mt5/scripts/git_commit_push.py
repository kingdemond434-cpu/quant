import subprocess
r = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && "
     "git add desks/mt5/mt5desk/families.py desks/mt5/side_channels/convert_to_hypotheses.py desks/mt5/side_channels/full_pipeline.py desks/mt5/data/universe/universe.json 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
if r.stderr:
    print("ERR:", r.stderr[:300])

r2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && "
     "git commit -m 'zero-hardcode families registry + 197-symbol universe' 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(r2.stdout)
if r2.stderr:
    print("ERR:", r2.stderr[:300])

r3 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cd /home/quant/quant-platform && "
     "git push origin desk-sync-clean 2>&1"],
    capture_output=True, text=True, timeout=60
)
print(r3.stdout)
if r3.stderr:
    print("ERR:", r3.stderr[:300])