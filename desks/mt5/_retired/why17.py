import sys, json, collections
sys.path.insert(0, "."); sys.path.insert(0, "research"); sys.path.insert(0, "../..")
import research.sleeve_registry as reg
from research.shadow_forward import _family_fn

d = json.load(open(r"data\sleeve_registry.json"))["sleeves"]
st = json.load(open(r"reports\shadow\shadow_state.json"))
sl = st.get("sleeves") or st
broken = [k for k, v in sl.items()
          if isinstance(v, dict) and v.get("status") == "IDENTITY_BROKEN"]
print("  still broken:", len(broken))
genuine = stale = nofn = 0
fams = collections.Counter()
for k in broken:
    row = d.get(k)
    if not row:
        nofn += 1; continue
    ident = row["identity"]; fam = ident.get("family")
    fams[fam] += 1
    fn = _family_fn(fam)
    if fn is None:
        nofn += 1; continue
    cur = reg.behaviour_hash(fn)
    if cur == ident.get("behaviour_hash"):
        stale += 1
    else:
        genuine += 1
print("  GENUINE logic change (correctly broken):", genuine)
print("  behaviour matches (should have cleared):", stale)
print("  family fn unresolvable:", nofn)
print("  families:", dict(fams))
