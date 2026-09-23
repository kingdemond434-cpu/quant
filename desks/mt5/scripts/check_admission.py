import json
import sys
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")
sys.path.insert(0, str(base / "research"))

from shadow_admission import authorized_specs, partition_work

# Get authorized specs
auth = authorized_specs(base)
print("Authorized specs: " + str(len(auth)))
for s in sorted(auth):
    print("  " + str(s))

# What the shadow forward declares
from shadow_forward import SLEEVES, UNIVERSE_SLEEVES
declared = [(s, w, c, "session_range_breakout", False) for s, w, c in SLEEVES]
for s, f in UNIVERSE_SLEEVES:
    declared.append((s, None, None, f, True))

print("\nDeclared: " + str(len(declared)))
admitted, blocked = partition_work(declared)
print("Admitted: " + str(len(admitted)))
for s in admitted:
    print("  A " + str(s))
print("Blocked: " + str(len(blocked)))
for s in blocked:
    print("  B " + str(s))
