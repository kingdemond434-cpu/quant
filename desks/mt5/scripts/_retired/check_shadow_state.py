import json
from pathlib import Path

# Check shadow state
state_file = Path("/home/quant/quant-platform/desks/mt5/data/shadow/shadow_state.json")
if state_file.exists():
    state = json.loads(state_file.read_text("utf-8"))
    print("Shadow state:")
    print("  admitted=" + str(len(state.get("admitted", {}))))
    print("  quarantined=" + str(len(state.get("quarantined", {}))))
    for k, v in state.get("quarantined", {}).items():
        reason = v.get("reason", v.get("gate_reason", "unknown"))
        print("  Q " + k + ": " + str(reason)[:120])
    for k, v in state.get("admitted", {}).items():
        print("  A " + k + ": exp=" + str(v.get("exp_r", "?")) + "R n=" + str(v.get("n", "?")))
else:
    print("No shadow_state.json")

# Also check qquant shadow state
qq = Path("/home/quant/quant-platform/desks/mt5/data/shadow/qquant_shadow_state.json")
if qq.exists():
    q = json.loads(qq.read_text("utf-8"))
    print("\nQQUANT shadow state:")
    print("  admitted=" + str(len(q.get("admitted", {}))))
    print("  quarantined=" + str(len(q.get("quarantined", {}))))
    for k, v in q.get("admitted", {}).items():
        print("  A " + k)
else:
    print("\nNo qquant_shadow_state.json")
