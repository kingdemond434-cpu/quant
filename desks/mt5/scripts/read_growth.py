import subprocess, json

# Get growth_now.json
r = subprocess.run(["ssh", "quant@95.216.191.70",
                    "cat /home/quant/quant-platform/desks/mt5/reports/growth_now.json 2>/dev/null"],
                   capture_output=True, text=True, timeout=30)
if r.stdout.strip():
    data = json.loads(r.stdout)
    print(json.dumps(data, indent=2))
else:
    print("growth_now.json not found, running it now...")
    r2 = subprocess.run(["ssh", "quant@95.216.191.70",
                         "cd /home/quant/quant-platform && .venv/bin/python -m research.growth_now 2>&1"],
                        capture_output=True, text=True, timeout=120)
    print(r2.stdout[-3000:])
