import json
from pathlib import Path

log = Path("/home/quant/quant-platform/desks/mt5/logs/shadow.log")
lines = log.read_text("utf-8").split("\n")

# Get the most recent shadow run with sleeve results
recent = []
for l in lines:
    if "shadow" in l and ("ACTIVE" in l or "n=" in l) and "cumR" in l:
        recent.append(l.strip())

# Get last occurrence of each sleeve
seen = {}
for l in recent:
    # Extract sleeve name
    for prefix in ["XAUUSD", "USDJPY", "CADJPY", "EURJPY", "GBPJPY", "AUDNZD"]:
        if prefix in l:
            key = l.split(":")[0].strip() if ":" in l else prefix
            # Get window
            for w in ["asia", "london_am", "afternoon", "london_close"]:
                if w in l:
                    key = prefix + "." + w
                    break
            seen[key] = l
            break

print("=== CURRENT FORWARD SHADOW ===")
for k in sorted(seen):
    print("  " + seen[k])

# Also check admission state
state_file = Path("/home/quant/quant-platform/desks/mt5/reports/shadow/qquant_shadow_state.json")
if state_file.exists():
    state = json.loads(state_file.read_text("utf-8"))
    print("\n=== QQUANT SHADOW STATE ===")
    for k, v in state.items():
        if isinstance(v, dict) and "n" in v:
            print("  " + k + ": n=" + str(v.get("n")) + " status=" + str(v.get("status", "?")))
