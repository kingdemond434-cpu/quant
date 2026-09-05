import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")

# Read the qquant_shadow source to understand admission
qq = base / "research" / "qquant_shadow.py"
lines = qq.read_text("utf-8").split("\n")
for i, line in enumerate(lines[:120]):
    print(str(i+1).rjust(4) + ": " + line)
