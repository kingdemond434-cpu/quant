import json, statistics
st = json.load(open(r"reports\shadow\shadow_state.json"))
sl = st.get("sleeves") or st
act = [v for v in sl.values() if isinstance(v, dict) and v.get("status") == "ACTIVE"]
withn = [v for v in act if (v.get("n") or 0) > 0]
n_tot = sum(v.get("n", 0) or 0 for v in act)
days = [v.get("days_active") or 0 for v in withn]
exps = [v.get("exp_r") or 0.0 for v in withn]
print("  ACTIVE sleeves:", len(act), " with trades:", len(withn), " total trades:", n_tot)
if withn:
    md = statistics.median(days) or 1
    print(f"  median days_active: {md}   max: {max(days)}")
    print(f"  expectancy: mean {statistics.mean(exps):+.3f}R  median {statistics.median(exps):+.3f}R")
    print(f"  positive sleeves: {sum(1 for e in exps if e > 0)}/{len(exps)}")
    rate = n_tot / max(1, len(act)) / max(1, md)
    print(f"  trade rate: {rate:.2f} trades/sleeve/day  ->  book {rate*len(act):.1f} trades/day")
    for risk in (0.0018, 0.005, 0.007):
        daily = rate * len(act) * statistics.mean(exps) * risk
        print(f"   at {risk*100:.2f}%/trade risk: {daily*100:+.3f}%/day  "
              f"-> {( (1+daily)**252 - 1)*100:+,.0f}%/yr (naive compounding)")
