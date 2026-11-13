import sys, json, collections
sys.path.insert(0, "."); sys.path.insert(0, "research")
import research.sleeve_registry as reg
from mt5desk import families
d = json.load(open(r"data\sleeve_registry.json"))["sleeves"]
match = diff = nofn = 0
examples = []
for k, row in d.items():
    fam = row["identity"].get("family"); fb = row["identity"].get("behaviour_hash")
    fn = getattr(families, "family_" + str(fam), None) or getattr(families, str(fam), None)
    if fn is None:
        nofn += 1; continue
    cur = reg.behaviour_hash(fn)
    if cur == fb:
        match += 1
    else:
        diff += 1
        if len(examples) < 3:
            examples.append((k[:44], fam, str(fb)[:12], str(cur)[:12]))
print("frozen behaviour == current:", match, " DIFFERS:", diff, " family fn not found:", nofn)
for e in examples:
    print("   ", e)
