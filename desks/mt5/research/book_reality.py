"""What survives when the backtest's conveniences are removed, one at a time.

The year-by-year table says the five-sleeve book returns a 112% median with 9
positive years out of 9. NINE OUT OF NINE IS THE TELL. Books that good do not
exist, so the number is measuring something other than the edge, and the job is
to find out how much of it each convenience is worth.

Four are removed here, cumulatively, in the order of how confident I am that
they are real:

    COSTS. The engine charges a median spread and a commission. It does not
    charge slippage, and these are STOP-ENTRY breakouts, which slip in one
    direction by construction: the order fills when price is already moving
    through it. 2x and 3x cost multiples stand in for that.

    LOT GRANULARITY. The compounding assumes risk can be set to 1.033% exactly.
    At EUR2,177 with a EUR29.80 gold ticket, the available sizes are 1.37%,
    2.74%, 4.11% -- nothing between. The realised risk is whatever rounding
    lands on, which at small equity is a large relative error in both
    directions.

    CORRELATION IN THE DRAWDOWN. rho is +0.137 across the sample. Four of the
    five sleeves are gold and JPY crosses in the Asia session, which in a
    risk-off shock are one trade. The measured k_eff of 3.23 is an average over
    calm and stress, and it is wrong in exactly the week it is load-bearing.

    THE REGIME. 2022 and 2025 pay 352% and 429% and the other seven years pay a
    40-125% median. Those two are the BoJ policy-divergence year and the gold
    melt-up. A session-range breakout is a volatility harvester, so its best
    years are the high-volatility years -- and eight years is two of them.
"""
import json
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, "/workspace/quant/desks/mt5")
sys.path.insert(0, "/workspace/quant/desks/mt5/research")

import numpy as np                                              # noqa: E402
import pandas as pd                                             # noqa: E402

from mt5desk import families                                    # noqa: E402
from mt5desk.engine import Costs, run_backtest                  # noqa: E402
from run_hunt11 import WINDOWS                                  # noqa: E402
from book_sizing import FIVE, compound                          # noqa: E402

BASE = "/workspace/quant/desks/mt5"
META = json.loads(open(f"{BASE}/data/universe/universe.json").read())
_h1 = {}


def h1(s):
    if s not in _h1:
        _h1[s] = families._h1(pd.read_parquet(f"{BASE}/data/universe/{s}_H1.parquet"))
    return _h1[s]


def series(sym, win, mult):
    m = META[sym]
    base = 0.48 if sym == "XAUUSD" else max(
        m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05)
    cost = Costs(spread_per_lot=base * mult, commission_per_lot=3.50 * mult,
                 contract_oz=m["contract_size"])
    sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
    tr = run_backtest(h1(sym), sigs, cost).trades
    return pd.Series([t.r_multiple for t in tr],
                     index=pd.Index([t.entry_time.date() for t in tr])
                     ).groupby(level=0).sum()


def book(mult):
    sl = {k: series(*k.split("."), mult) for k in FIVE}
    days = sorted(set().union(*[set(v.index) for v in sl.values()]))
    yrs = (max(days) - min(days)).days / 365.25
    port = pd.DataFrame({k: v.reindex(days).fillna(0.0) for k, v in sl.items()},
                        index=days).sum(axis=1)
    n = sum(len(v) for v in sl.values())
    return port, yrs, sl


def yearly(port, q, shift):
    v = pd.Series(port.to_numpy(float) - shift,
                  index=pd.to_datetime(pd.Index(port.index)))
    return pd.Series({y: (float(np.cumprod(1 + q * c.to_numpy())[-1]) - 1)
                      for y, c in v.groupby(v.index.year)})


Q = 0.05 / 5          # 5% total heat over five legs, the middle setting
print("THE FIVE-SLEEVE BOOK AS EACH CONVENIENCE IS REMOVED")
print("all half-edge, 5% total heat (q=1.00%/leg), CAGR over 2018-2026\n")
print(f"{'scenario':<44}{'CAGR':>9}{'median yr':>11}{'worst yr':>10}"
      f"{'wDD':>8}{'+yrs':>7}")
print("-" * 89)

rows = []
for mult, name in ((1.0, "as backtested (median spread + commission)"),
                   (2.0, "2x costs — a first pass at stop-order slippage"),
                   (3.0, "3x costs — the desk's own stress gate")):
    port, yrs, _ = book(mult)
    d = 0.5 * port.mean()
    c, dd = compound(port, Q, yrs, shift=d)
    y = yearly(port, Q, d)
    rows.append((name, c, y, dd))
    print(f"{name:<44}{c * 100:>8.1f}%{y.median() * 100:>10.1f}%"
          f"{y.min() * 100:>9.1f}%{dd * 100:>7.1f}%{int((y > 0).sum())}/{len(y):<5}")

# --- the two carry years removed -------------------------------------------
port, yrs, _ = book(1.0)
d = 0.5 * port.mean()
idx = pd.to_datetime(pd.Index(port.index))
keep = port[~idx.year.isin([2022, 2025])]
ky = (max(keep.index) - min(keep.index)).days / 365.25
c, dd = compound(keep, Q, ky, shift=d)
y = yearly(keep, Q, d)
print(f"{'1x costs, WITHOUT 2022 and 2025':<44}{c * 100:>8.1f}%"
      f"{y.median() * 100:>10.1f}%{y.min() * 100:>9.1f}%{dd * 100:>7.1f}%"
      f"{int((y > 0).sum())}/{len(y):<5}")

# --- everything at once ------------------------------------------------------
port3, yrs3, _ = book(3.0)
d3 = 0.5 * port3.mean()
idx3 = pd.to_datetime(pd.Index(port3.index))
k3 = port3[~idx3.year.isin([2022, 2025])]
kk = (max(k3.index) - min(k3.index)).days / 365.25
c, dd = compound(k3, Q, kk, shift=d3)
y = yearly(k3, Q, d3)
print(f"{'3x costs AND without 2022/2025':<44}{c * 100:>8.1f}%"
      f"{y.median() * 100:>10.1f}%{y.min() * 100:>9.1f}%{dd * 100:>7.1f}%"
      f"{int((y > 0).sum())}/{len(y):<5}")

# --- lot granularity at the book's own minimum capital ----------------------
print()
print("LOT GRANULARITY — the sizes the venue actually sells, at EUR2,177")
print("-" * 89)
for k in FIVE:
    sym, win = k.split(".")
    m = META[sym]
    sigs = list(families.family_session_range_breakout(h1(sym), **WINDOWS[win]))
    base = 0.48 if sym == "XAUUSD" else max(
        m["median_spread_pts"] * m["tick_size"] * m["contract_size"], 0.05)
    tr = run_backtest(h1(sym), sigs, Costs(base, 3.50, m["contract_size"])).trades
    rec = [t for t in tr if t.entry_time.year >= 2025]
    e = np.median([abs(t.entry - t.stop) / m["tick_size"] * m["tick_value"] * 0.01
                   for t in rec])
    want = 0.01033 * 2177                      # policy risk in EUR at q=1.033%
    lots = max(1, round(want / e))
    print(f"  {k:<20} ticket EUR{e:>6.2f}  policy wants EUR{want:>6.2f}  "
          f"-> {lots} x 0.01 = EUR{lots * e:>6.2f}  "
          f"realised {lots * e / 2177:>5.2%} vs {want / 2177:.2%} "
          f"({lots * e / want - 1:+.0%})")
