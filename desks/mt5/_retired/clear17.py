import sys, json, collections
sys.path.insert(0, "."); sys.path.insert(0, "research"); sys.path.insert(0, "../..")
import research.sleeve_registry as reg
from research.shadow_forward import _family_fn

REG = r"data\sleeve_registry.json"
STP = r"reports\shadow\shadow_state.json"
rows = json.load(open(REG))["sleeves"]
st = json.load(open(STP))
sl = st.get("sleeves") or st

cleared, kept = [], []
for k, v in sl.items():
    if not isinstance(v, dict) or v.get("status") != "IDENTITY_BROKEN":
        continue
    row = rows.get(k)
    if not row:
        kept.append((k, "not in registry")); continue
    if str(row.get("status") or "").upper() != "LIVE":
        kept.append((k, f"registry says {row.get('status')}")); continue
    ident = row["identity"]
    fn = _family_fn(ident.get("family"))
    if fn is None:
        kept.append((k, "family fn unresolvable")); continue
    if reg.behaviour_hash(fn) != ident.get("behaviour_hash"):
        kept.append((k, "behaviour GENUINELY differs -- correctly broken")); continue
    # Provably stale: the registry says LIVE and the running code's bytecode matches what the
    # clock froze. forward_start is untouched, so no day is credited that was not observed.
    v["status"] = "ACTIVE"
    v.pop("identity_drift", None)
    v.pop("identity_reason", None)
    v["stale_identity_cleared_at"] = "2026-09-04"
    cleared.append(k)

if cleared:
    json.dump(st, open(STP, "w"), indent=2)
print("  cleared (registry LIVE + behaviour matches):", len(cleared))
print("  kept broken (genuine or unverifiable):", len(kept))
for k, why in kept[:5]:
    print("     ", k[:44], "->", why)
print("  state now:", dict(collections.Counter(
    v.get("status") for v in sl.values() if isinstance(v, dict))))
