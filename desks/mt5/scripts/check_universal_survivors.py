"""Check what passed all 10 gates."""
import json

# Existing universal survivors
with open("/home/quant/quant-platform/desks/mt5/reports/UNIVERSAL_SURVIVORS.json") as f:
    data = json.load(f)

print(f"=== UNIVERSAL SURVIVORS (all 10 gates): {data['n']} ===\n")
for name, info in data["survivors"].items():
    gates = info["gates"]
    all_pass = all(g.get("passed", False) for g in gates.values())
    status = "PASS ALL 10" if all_pass else "PARTIAL"
    print(f"  {status}: {name}")
    print(f"    sym={info['sym']}, days={info['days']}")
    for gname, gval in gates.items():
        ps = "PASS" if gval.get("passed") else "FAIL"
        extra = ""
        if "dsr" in gval:
            extra = f" dsr={gval['dsr']}"
        elif "pbo" in gval:
            extra = f" pbo={gval['pbo']}"
        elif "p_value" in gval:
            extra = f" p={gval['p_value']}"
        elif "sharpe" in gval:
            extra = f" sr={gval['sharpe']}"
        elif "message" in gval:
            extra = f" {gval['message']}"
        print(f"      {ps} {gname}{extra}")
    print()

# Also check canon
with open("/home/quant/quant-platform/desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json") as f:
    canon = json.load(f)
print(f"Canon file: {len(canon)} entries")
for k in list(canon.keys())[:5]:
    print(f"  {k}")
