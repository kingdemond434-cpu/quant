import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")

# Read authority
certs = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
print("=== CERTIFIED (all 10 gates PASS) ===")
print("n=" + str(certs["n"]))
for k, v in certs["survivors"].items():
    spec = v.get("shadow_spec", {})
    gates = v.get("gates", {})
    all_pass = all(g.get("passed", False) for g in gates.values()) if gates else False
    print("  " + k)
    print("    sym=" + str(spec.get("symbol")) + " selector=" + str(spec.get("selector")) + " all_ten_pass=" + str(all_pass))

# Check what shadow_forward actually runs
print("\n=== SHADOW FORWARD SLEEVES ===")
sf = (base / "research" / "shadow_forward.py").read_text("utf-8")
for line in sf.split("\n"):
    if "SLEEVES" in line and "[" in line:
        continue
    if ("asia" in line or "afternoon" in line or "london" in line) and "(" in line and "#" not in line[:2]:
        print("  " + line.strip())

# Check what shadow_admission authorizes
print("\n=== SHADOW ADMISSION AUTHORIZED ===")
import sys
sys.path.insert(0, str(base / "research"))
from shadow_admission import authorized_specs
auth = authorized_specs(base)
for s in sorted(auth):
    print("  " + str(s))
