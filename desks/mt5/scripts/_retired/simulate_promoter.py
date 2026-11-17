import json
import sys
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")
sys.path.insert(0, str(base / "research"))
sys.path.insert(0, str(base))

# Simulate what promoter does
from gate_policy import all_ten_pass, is_exact_policy

certs = json.loads((base / "reports" / "UNIVERSAL_SURVIVORS.json").read_text("utf-8"))
policy_valid = is_exact_policy(certs.get("gate_policy"))
print("Policy valid: " + str(policy_valid))

rows = certs.get("survivors", {})
for key, cert in rows.items():
    gates = cert.get("gates")
    has_gates = all_ten_pass(gates) if gates else False
    has_spec = "shadow_spec" in cert
    print("  " + key + " all_ten_pass=" + str(has_gates) + " has_shadow_spec=" + str(has_spec))
    if has_gates and has_spec:
        spec = cert["shadow_spec"]
        print("    -> PROMOTION CANDIDATE: " + spec.get("symbol") + " " + spec.get("selector"))
