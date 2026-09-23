import sys, json
sys.path.insert(0, r"research"); sys.path.insert(0, ".")
import pandas as pd
from mt5desk import families
from research.run_hunt11 import battery, WINDOWS

h1 = pd.read_parquet("data/universe/XAUUSD_H1.parquet")
h1 = families._h1(h1)
ny = h1.between_time("13:00", "22:00")
ny_by_day = ny.assign(date=ny.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
ny_by_day["rng"] = ny_by_day["hi"] - ny_by_day["lo"]
ny_by_day["rng_med"] = ny_by_day["rng"].shift(1).rolling(20, min_periods=10).median()
day = h1.assign(date=h1.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
day["dhi"] = day["hi"].shift(1)
day["dlo"] = day["lo"].shift(1)
ny_by_day = ny_by_day.join(day[["dhi", "dlo"]])
states = {}
for d, r in ny_by_day.iterrows():
    med = r["rng_med"]
    if not med or pd.isna(med):
        states[d] = "NONE"
        continue
    st = "TREND_DAY" if r["rng"] > 1.5 * med else ("RANGE_DAY" if r["rng"] < 0.75 * med else "NORMAL_DAY")
    dhi, dlo = r["dhi"], r["dlo"]
    if dhi and dlo and (r["hi"] > dhi or r["lo"] < dlo):
        nyc = ny[ny.index.date == d]
        if len(nyc) and ((nyc["close"].iloc[-1] < dhi and r["hi"] > dhi) or (nyc["close"].iloc[-1] > dlo and r["lo"] < dlo)):
            st = "FAILED_BREAK"
    states[d] = st

sigs = families.family_session_range_breakout(h1, **WINDOWS["asia"])
sdays = [pd.Timestamp(s.time).date() for s in sigs]
res = {}
for name in ["TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK"]:
    sub = [s for s, d in zip(sigs, sdays) if states.get(d) == name]
    b = battery(h1, sub)
    res[name] = b
    wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
    print(f"{name:<12} n={b['n']:5d} exp={b['exp']:+.3f} t={b['t']:5.2f} "
          f"defl={b['defl_t']:5.2f} PF={b['pf']:5.2f} maxDD={b['maxdd']:7.1f} "
          f"stress={b['exp_stress']:+.3f} WF[{wfs}] {'PASS' if b['gate'] else 'fail'}")
json.dump(res, open("reports/mech_battery.json", "w"), indent=2, default=str)