import json
path = "/home/quant/quant-platform/desks/mt5/reports/UNIVERSAL_SURVIVORS.json"
d = json.load(open(path))
print("n=" + str(d["n"]))
for k in d["survivors"]:
    s = d["survivors"][k]
    has_spec = "shadow_spec" in s
    print("  " + k + " shadow_spec=" + str(has_spec))
