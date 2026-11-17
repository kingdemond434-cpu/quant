import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")

# Check what gate_policy looks like in the original file
# The canon had n=1 before - let me check git history or the report
reports = base / "reports" / "UNIVERSAL_SURVIVORS.json"
d = json.loads(reports.read_text("utf-8"))
print("Top-level keys: " + str(list(d.keys())))
print("Has gate_policy: " + str("gate_policy" in d))
if "gate_policy" in d:
    print("gate_policy: " + str(d["gate_policy"]))

# Check what qquant_shadow reads
qq = base / "research" / "qquant_shadow.py"
lines = qq.read_text("utf-8").split("\n")
for i, line in enumerate(lines):
    if "UNIVERSAL_SURVIVORS" in line or "certs" in line or "gate_policy" in line:
        print("L" + str(i+1) + ": " + line.rstrip()[:120])

# Check gate_policy from gate_spec
spec = json.loads((base / "policy" / "gate_spec.yaml").read_text("utf-8")) if (base / "policy" / "gate_spec.yaml").exists() else None
if spec is None:
    import yaml
    spec = yaml.safe_load((base / "policy" / "gate_spec.yaml").read_text("utf-8"))
print("\ngate_spec version: " + str(spec.get("version")))
