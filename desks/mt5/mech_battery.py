"""Per-window, per-state battery on the gold book.

THIS SCRIPT COMPUTED ITS OWN DAY STATES INLINE, SAME-DAY, AND THAT WAS A LOOKAHEAD.

It labelled day D from D's own 13:00-22:00 NY session and then filtered D's own
signals. The asia window fires at 07:00 UTC, so every asia trade was gated by
data from fifteen hours in its own future. `run_hunt12.day_states` had already
found and fixed exactly this, and eleven callers picked the fix up -- but this
file was not one of them, because it reimplemented the labelling instead of
importing it. Two implementations of one definition, and the wrong one is the
one that wrote MECHANISM_REPORT_ASIA_GOLD.md.

WHAT IT COST, and it is the whole headline of that report:

    asia TREND_DAY     +0.908R defl_t 9.85   ->   +0.191R defl_t 1.30
    asia FAILED_BREAK  -0.257R defl_t -8.29  ->   +0.158R defl_t 2.16   (sign inverts)
    asia NORMAL_DAY    +0.459R defl_t 9.56   ->   +0.256R defl_t 4.59

Corrected, asia's four states pay +0.191 / +0.256 / +0.210 / +0.158 against an
unconditional base of +0.212R. THAT IS A FLAT LINE. Prior-NY displacement does
not discriminate, the "PF 4.29 at a quarter of the drawdown" headline was an
artifact, and the conditioning upgrade it recommended buys nothing while costing
sample.

It now imports the shared function, so this cannot drift again.
"""
import json
import sys

sys.path.insert(0, "research")
sys.path.insert(0, ".")

import pandas as pd

from mt5desk import families
from research.run_hunt11 import WINDOWS, battery
from research.run_hunt12 import day_states

h1 = families._h1(pd.read_parquet("data/universe/XAUUSD_H1.parquet"))
states = day_states(h1)          # CORRECTED prior-day join. Never same-day.

res = {}
for win in ("asia", "london_am", "afternoon"):
    sigs = families.family_session_range_breakout(h1, **WINDOWS[win])
    sdays = [pd.Timestamp(s.time).date() for s in sigs]
    b = battery(h1, sigs)
    res[f"{win}.ALL"] = b
    print(f"{win:<11}{'ALL (base)':<13} n={b['n']:5d} exp={b['exp']:+.3f} "
          f"defl={b['defl_t']:5.2f} PF={b['pf']:5.2f} maxDD={b['maxdd']:7.1f} "
          f"{'PASS' if b['gate'] else 'fail'}")
    for name in ("TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK"):
        sub = [s for s, d in zip(sigs, sdays) if states.get(d) == name]
        if len(sub) < 30:
            continue
        b = battery(h1, sub)
        res[f"{win}.{name}"] = b
        print(f"{'':<11}{name:<13} n={b['n']:5d} exp={b['exp']:+.3f} "
              f"defl={b['defl_t']:5.2f} PF={b['pf']:5.2f} maxDD={b['maxdd']:7.1f} "
              f"{'PASS' if b['gate'] else 'fail'}")
    print()

json.dump(res, open("reports/mech_battery.json", "w"), indent=2, default=str)
print("The conditioned cells sit on top of their own unconditional base. Where "
      "they do not separate from it, the state is a label and not a mechanism.")
