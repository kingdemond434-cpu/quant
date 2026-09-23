import sys, json
sys.path.insert(0, "."); sys.path.insert(0, "research"); sys.path.insert(0, "../..")
import research.sleeve_registry as reg
from research.shadow_forward import _family_fn

d = json.load(open(r"data\sleeve_registry.json"))["sleeves"]
key = "XAUUSD.asia"
row = d.get(key)
if row is None:
    key = list(d)[0]; row = d[key]
ident = row["identity"]
fam = ident.get("family")
fn = _family_fn(fam)
print("key:", key, "family:", fam, "fn resolved:", fn is not None)
if fn is not None:
    cur_code = reg.code_hash(fn)
    cur_beh = reg.behaviour_hash(fn)
    print("  frozen code_hash :", ident.get("code_hash"))
    print("  current code_hash:", cur_code)
    print("  frozen behaviour :", ident.get("behaviour_hash"))
    print("  current behaviour:", cur_beh)
    print("  behaviour equal  :", ident.get("behaviour_hash") == cur_beh)
    probe = dict(ident)
    probe["code_hash"] = cur_code
    probe["behaviour_hash"] = cur_beh
    print("  verify(probe)    :", reg.verify(key, probe))
print("  registry status  :", row.get("status"))
