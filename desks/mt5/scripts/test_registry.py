import subprocess

code = r"""
import sys
sys.path.insert(0, "/home/quant/quant-platform/desks/mt5")
from mt5desk.families import FAMILY_REGISTRY, get_all_family_names
names = get_all_family_names()
print(f"Registry: {len(names)} families")
for n in names:
    entry = FAMILY_REGISTRY[n]
    grid = entry.get("param_grid", {})
    print(f"  {n}: {len(grid)} sweep params, tags={entry.get('tags', [])}")
"""

proc = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "cat > /tmp/test_reg.py << 'PYEOF'\n" + code + "\nPYEOF"],
    capture_output=True, text=True, timeout=10
)
proc2 = subprocess.run(
    ["ssh", "quant@95.216.191.70",
     "/home/quant/quant-platform/.venv/bin/python /tmp/test_reg.py 2>&1"],
    capture_output=True, text=True, timeout=30
)
print(proc2.stdout)
if proc2.stderr:
    print("ERR:", proc2.stderr[:1000])
