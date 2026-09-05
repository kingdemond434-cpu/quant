import json, os
from pathlib import Path

base = Path("/home/quant/quant-platform")
reports = base / "desks" / "mt5" / "reports"

# Check holds
for name in ["HOLD_universal", "HOLD_qquant_gates", "HOLD_allocation", "HOLD_merge", "HOLD_qquant"]:
    p = base / "data" / name
    if p.exists():
        print("HOLD SET: " + name + " = " + p.read_text().strip()[:200])
    else:
        p2 = reports / name
        if p2.exists():
            print("HOLD SET: " + name + " = " + p2.read_text().strip()[:200])
        else:
            print("HOLD CLEAR: " + name)

# Check canonical survivor file
canon = base / "desks" / "mt5" / "data" / "UNIVERSAL_SURVIVORS.canon.json"
if canon.exists():
    d = json.loads(canon.read_text("utf-8"))
    print("\nCANON file: n=" + str(d.get("n", "?")))
    for k in d.get("survivors", {}):
        print("  " + k)

# Check all UNIVERSAL_SURVIVORS files
for p in base.rglob("UNIVERSAL_SURVIVORS*"):
    if "__pycache__" in str(p):
        continue
    try:
        d = json.loads(p.read_text("utf-8"))
        print("\n" + str(p) + ": n=" + str(d.get("n", "?")))
    except Exception:
        print("\n" + str(p) + ": UNREADABLE")

# Check vps_authority
state = reports / "UNIVERSAL_STATE_VERIFY.json"
if state.exists():
    s = json.loads(state.read_text("utf-8"))
    print("\nUNIVERSAL_STATE_VERIFY vps_authority=" + str(s.get("vps_authority")))
