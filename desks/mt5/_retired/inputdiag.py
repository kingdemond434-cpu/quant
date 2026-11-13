import sys, os
sys.path.insert(0, "."); sys.path.insert(0, "research"); sys.path.insert(0, "../..")
import research.orthogonal_sweep as osw

print("--- declared input paths present on THIS box? ---")
for p in ("data/tape/contract_terms", "data/cot", "data/macro_state.json",
          "data/intelligence/ff_calendar_vintage", "data/tape/ticks"):
    print("   %-42s %s" % (p, "present" if os.path.exists(p.replace("/", os.sep)) else "ABSENT"))

sym = "EURUSD"
df = osw._bars(sym)
print("--- loaders on %s (bars=%s) ---" % (sym, None if df is None else len(df)))
if df is not None:
    try:
        spread, flow = osw._tape_series(sym, df.index)
        print("   spread_series:", "None" if spread is None else "len %d" % len(spread))
        print("   flow:         ", "None" if flow is None else "len %d" % len(flow))
    except Exception as e:
        print("   tape ERROR:", type(e).__name__, str(e)[:90])
    for name, fn in (("macro", lambda: osw._macro_series(df.index)),
                     ("cot", lambda: osw._cot_frame(sym)),
                     ("events", lambda: osw._event_index())):
        try:
            v = fn()
            print("   %-13s %s" % (name + ":", "None" if v is None else "len %d" % len(v)))
        except Exception as e:
            print("   %-13s ERROR %s %s" % (name + ":", type(e).__name__, str(e)[:80]))
