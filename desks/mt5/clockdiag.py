import sys, json, collections
sys.path.insert(0, "."); sys.path.insert(0, "research")
import research.sleeve_registry as reg

mods = {}
for m in ("families", "families_orthogonal", "families_edge_queue", "family_generic"):
    try:
        mods[m] = __import__("mt5desk." + m, fromlist=[m])
    except Exception as e:
        mods[m] = None
        print("  (module %s unavailable: %s)" % (m, type(e).__name__))

def find(fam):
    for name, mod in mods.items():
        if mod is None:
            continue
        for cand in ("family_" + str(fam), str(fam)):
            fn = getattr(mod, cand, None)
            if callable(fn):
                return name, fn
    return None, None

d = json.load(open(r"data\sleeve_registry.json"))["sleeves"]
st = json.load(open(r"reports\shadow\shadow_state.json"))
sl = st.get("sleeves") or st
res = collections.Counter()
unresolved = collections.Counter()
for k, row in d.items():
    ident = row["identity"]; fam = ident.get("family"); fb = ident.get("behaviour_hash")
    state = (sl.get(k) or {}).get("status", "?")
    where, fn = find(fam)
    if fn is None:
        res["family_fn_MISSING"] += 1
        unresolved[fam] += 1
        continue
    cur = reg.behaviour_hash(fn)
    res["behaviour_MATCH" if cur == fb else "behaviour_DIFFERS"] += 1
print("  registry rows:", len(d))
for k, v in res.most_common():
    print("   ", k, v)
print("  families with no resolvable function:", dict(unresolved))
