import json
from pathlib import Path

base = Path("/home/quant/quant-platform/desks/mt5")

# Full quarantine dump
qf = base / "reports" / "shadow" / "shadow_quarantine.json"
q = json.loads(qf.read_text("utf-8"))
candidates = q.get("candidates", {})
print("Quarantined candidates: " + str(len(candidates)))
for k, v in candidates.items():
    print("  " + k + ": n=" + str(v.get("n", 0)) + " reason=" + str(v.get("reason", "?")))

# Check qquant_shadow admission logic
qq = base / "research" / "qquant_shadow.py"
text = qq.read_text("utf-8")
# Find the admission check
for i, line in enumerate(text.split("\n")):
    if "all_ten_pass" in line or "gate" in line.lower() or "admit" in line.lower():
        print("  L" + str(i+1) + ": " + line.strip()[:120])
