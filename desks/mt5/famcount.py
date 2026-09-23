import json, collections, os
TARGETS = ("carry","relative_value","cross_asset_residual","vol_transition",
           "liquidity_regime","event_reaction","cot_positioning","macro_conditional")
def fams(obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("family", "fam") and isinstance(v, str):
                out[v] += 1
            else:
                fams(v, out)
    elif isinstance(obj, list):
        for v in obj[:20000]:
            fams(v, out)

for rel in (r"data\hypotheses\external_backtest_results.json",
            r"data\hypotheses\mined_targets.json",
            r"data\hypotheses\edge_search_results.json"):
    if not os.path.exists(rel):
        print(rel, "ABSENT"); continue
    try:
        d = json.load(open(rel))
    except Exception as e:
        print(rel, "unreadable", type(e).__name__); continue
    c = collections.Counter()
    fams(d, c)
    print("==", rel, "-> families seen:", len(c))
    for k, v in c.most_common(8):
        mark = "  <== TARGET" if k in TARGETS else ""
        print("    %-28s %6d%s" % (k, v, mark))
    hit = [t for t in TARGETS if c.get(t)]
    print("    breadth targets present:", hit or "NONE")
