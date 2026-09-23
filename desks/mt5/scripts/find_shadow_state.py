import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")
# Find any shadow state files
for p in base.rglob("*shadow*state*"):
    if "__pycache__" in str(p):
        continue
    print(str(p))

for p in base.rglob("*quarantine*"):
    if "__pycache__" in str(p):
        continue
    print(str(p))

# Check shadow forward admitted/quarantined list
sf = base / "data" / "shadow"
if sf.exists():
    for p in sf.iterdir():
        print(str(p))
