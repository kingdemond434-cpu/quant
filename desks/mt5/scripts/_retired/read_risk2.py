import subprocess

# Get the rest of gateway_config_fallback and growth_now
for f in ["/home/quant/quant-platform/desks/mt5/mt5desk/gateway_config_fallback.py",
          "/home/quant/quant-platform/desks/mt5/research/growth_now.py"]:
    print("=" * 60)
    print(f.split("/")[-1])
    print("=" * 60)
    r = subprocess.run(["ssh", "quant@95.216.191.70", "sed -n '80,200p' " + f],
                       capture_output=True, text=True, timeout=30)
    print(r.stdout[:3000])
    print()

# Also get growth_now.json if it exists
r = subprocess.run(["ssh", "quant@95.216.191.70",
                    "cat /home/quant/quant-platform/desks/mt5/reports/growth_now.json 2>/dev/null | head -60"],
                   capture_output=True, text=True, timeout=30)
if r.stdout.strip():
    print("=" * 60)
    print("growth_now.json")
    print("=" * 60)
    print(r.stdout[:3000])
