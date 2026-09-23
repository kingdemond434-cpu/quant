import subprocess

files = [
    "/home/quant/quant-platform/desks/mt5/mt5desk/sizing.py",
    "/home/quant/quant-platform/desks/mt5/mt5desk/gateway_config_fallback.py",
]
for f in files:
    r = subprocess.run(["ssh", "quant@95.216.191.70", "cat " + f],
                       capture_output=True, text=True, timeout=30)
    print("=" * 60)
    print(f.split("/")[-1])
    print("=" * 60)
    print(r.stdout[:4000])
    print()
