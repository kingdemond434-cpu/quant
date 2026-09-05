import subprocess
from pathlib import Path

files = [
    "/home/quant/quant-platform/desks/mt5/mt5desk/risk_units.py",
    "/home/quant/quant-platform/desks/mt5/research/portfolio_projection.py",
    "/home/quant/quant-platform/desks/mt5/research/growth_now.py",
    "/home/quant/quant-platform/desks/mt5/research/sizing_study.py",
    "/home/quant/quant-platform/desks/mt5/mt5desk/gateway_config_fallback.py",
]

for f in files:
    print("=" * 60)
    print("FILE: " + f.split("/")[-1])
    print("=" * 60)
    r = subprocess.run(["ssh", "quant@95.216.191.70", "head -80 " + f],
                       capture_output=True, text=True, timeout=30)
    print(r.stdout[:3000])
    print()
