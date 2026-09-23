import json
d = json.load(open(r"data\hypotheses\orthogonal_candidates.json"))
print("swept_at:", d.get("swept_at"), " symbols:", d.get("symbols"))
print("families_ran:", d.get("families_ran"))
for k in ("input_gaps", "family_errors", "untestable_by_family"):
    v = d.get(k)
    print("==", k, "(%s)" % type(v).__name__)
    if isinstance(v, dict):
        for fam, why in list(v.items())[:12]:
            print("   %-24s %s" % (fam, str(why)[:150]))
    elif isinstance(v, list):
        for x in v[:12]:
            print("   ", str(x)[:170])
    else:
        print("   ", str(v)[:200])
print("note:", str(d.get("untestable_note"))[:200])
