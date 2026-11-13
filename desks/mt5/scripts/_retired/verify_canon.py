import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")

# Verify canon
canon = json.loads((base / "data" / "UNIVERSAL_SURVIVORS.canon.json").read_text("utf-8"))
reports = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))

print("CANON: n=" + str(canon["n"]))
for k, v in canon["survivors"].items():
    spec = v.get("shadow_spec", {})
    print("  " + k)
    print("    sym=" + str(spec.get("symbol")) + " selector=" + str(spec.get("selector")) + " family=" + str(spec.get("family")))

print("\nREPORTS: n=" + str(reports["n"]))
for k, v in reports["survivors"].items():
    spec = v.get("shadow_spec", {})
    has_spec = "shadow_spec" in v
    print("  " + k + " shadow_spec=" + str(has_spec))

# Check shadow_forward SLEEVES
sf = (base / "research" / "shadow_forward.py").read_text("utf-8")
print("\nshadow_forward.py SLEEVES entries with asia:")
for line in sf.split("\n"):
    if "asia" in line and ("XAUUSD" in line or "USDJPY" in line or "CADJPY" in line or "GBPJPY" in line or "EURJPY" in line):
        print("  " + line.strip())
