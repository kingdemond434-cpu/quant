"""Clear IDENTITY_BROKEN rows the registry and verify() both say are intact.

Conservative by construction: a row is only cleared when the registry -- which sleeve_registry
calls the only authority on sleeve identity -- reads LIVE for that exact key AND verify() returns
no drift for the identity rebuilt from the family currently on disk. forward_start is never
touched, so no day is credited that was not observed.
"""
import json, sys, os, shutil
from datetime import datetime, timezone
sys.path.insert(0, ".")
sys.path.insert(0, "research")
import sleeve_registry as reg

STATE = os.path.join("reports", "shadow", "shadow_state.json")
rows = json.load(open(os.path.join("data", "sleeve_registry.json")))["sleeves"]
state = json.load(open(STATE))

fams = {}
try:
    from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES
    fams.update(ORTHOGONAL_FAMILIES)
except Exception as e:
    print("  WARN orthogonal families unavailable:", e)

broken = [k for k, v in state.items() if isinstance(v, dict)
          and str(v.get("status") or "").upper() == "IDENTITY_BROKEN"]
print(f"  IDENTITY_BROKEN before: {len(broken)}")

cleared, kept = [], []
for k in broken:
    row = rows.get(k)
    if not row or str(row.get("status") or "").upper() != "LIVE":
        kept.append((k, "registry not LIVE")); continue
    stored = row.get("identity") or {}
    fam = stored.get("family")
    fn = fams.get(fam)
    if fn is None:
        kept.append((k, f"family {fam} not importable")); continue
    ident = dict(stored)
    ident["code_hash"] = reg.code_hash(fn)
    ident["behaviour_hash"] = reg.behaviour_hash(fn)
    try:
        drift = reg.verify(k, ident)
    except Exception as exc:
        kept.append((k, f"verify error {type(exc).__name__}")); continue
    if drift:
        kept.append((k, f"real drift {drift}")); continue
    st = state[k]
    st["status"] = "ACTIVE"
    st.pop("identity_drift", None)
    st.pop("identity_reason", None)
    st["identity_state_repaired_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    st["identity_state_repaired_why"] = ("registry read LIVE and verify() found no drift: the "
                                         "state row was the stale record, not the identity")
    cleared.append(k)

for k, why in kept:
    print(f"    KEPT    {k[:52]:54s} {why}")
print(f"  cleared: {len(cleared)}  kept: {len(kept)}")

if cleared and "--apply" in sys.argv:
    shutil.copy2(STATE, STATE + ".pre_identity_repair")
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, STATE)
    print(f"  APPLIED -- backup at {STATE}.pre_identity_repair")
else:
    print("  DRY RUN (pass --apply to write)")
