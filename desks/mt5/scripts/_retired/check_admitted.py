import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5/reports/shadow")

# shadow_state
sf = base / "shadow_state.json"
if sf.exists():
    s = json.loads(sf.read_text("utf-8"))
    print("=== SHADOW STATE ===")
    print("Admitted: " + str(len(s.get("admitted", {}))))
    for k, v in s.get("admitted", {}).items():
        print("  A " + k)
    print("Quarantined: " + str(len(s.get("quarantined", {}))))
    for k, v in list(s.get("quarantined", {}).items())[:5]:
        print("  Q " + k + ": " + str(v.get("reason", "?"))[:100])

# qquant_shadow_state
qq = base / "qquant_shadow_state.json"
if qq.exists():
    q = json.loads(qq.read_text("utf-8"))
    print("\n=== QQUANT SHADOW STATE ===")
    print("Admitted: " + str(len(q.get("admitted", {}))))
    for k, v in q.get("admitted", {}).items():
        print("  A " + k)
    print("Quarantined: " + str(len(q.get("quarantined", {}))))

# quarantine
qf = base / "shadow_quarantine.json"
if qf.exists():
    q = json.loads(qf.read_text("utf-8"))
    print("\n=== QUARANTINE ===")
    if isinstance(q, dict):
        for k, v in list(q.items())[:10]:
            print("  Q " + k + ": " + str(v)[:100])
    elif isinstance(q, list):
        for item in q[:10]:
            print("  Q " + str(item)[:100])
