import json
import sys
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")
sys.path.insert(0, str(base / "research"))
sys.path.insert(0, str(base))

from shadow_admission import authorized_specs

auth = authorized_specs(base)
print("Authorized by shadow_admission: " + str(len(auth)))
for s in sorted(auth):
    print("  " + str(s))

# Check promoter
from promoter import main as promo_main
import inspect
src = inspect.getsource(promo_main)
# Look for where it reads survivors
for i, line in enumerate(src.split("\n")):
    if "UNIVERSAL" in line or "surviv" in line.lower() or "shadow_spec" in line or "certif" in line.lower():
        print("promoter L" + str(i) + ": " + line.strip()[:120])
