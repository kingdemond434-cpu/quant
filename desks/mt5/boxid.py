import sys, json
sys.path.insert(0, ".")
sys.path.insert(0, "research")
import sleeve_registry as reg
from mt5desk.families_orthogonal import ORTHOGONAL_FAMILIES as F
fn = F["overnight_gap_decay"]
rows = json.load(open("data/sleeve_registry.json"))["sleeves"]
for k in ["USDZAR.overnight_gap_decay.asia", "CADCHF.overnight_gap_decay.asia"]:
    st = rows.get(k, {}).get("identity", {})
    print("KEY", k)
    print("  stored code ", st.get("code_hash"), " current ", reg.code_hash(fn))
    print("  stored behav", st.get("behaviour_hash"), " current ", reg.behaviour_hash(fn))
    ident = dict(st)
    ident["code_hash"] = reg.code_hash(fn)
    ident["behaviour_hash"] = reg.behaviour_hash(fn)
    try:
        print("  verify ->", reg.verify(k, ident))
    except Exception as e:
        print("  verify ERR", type(e).__name__, e)
print("python", sys.version.split()[0])
