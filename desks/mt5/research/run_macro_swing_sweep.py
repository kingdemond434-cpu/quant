"""Is macro an edge BY ITSELF, and does swing length pay for the spread?

    python research/run_macro_swing_sweep.py

TWO CLAIMS, ONE SWEEP, AND THEY ARE SEPARABLE IN THE OUTPUT

  1. MACRO AS EDGE. `family_macro_swing` has no price trigger. The macro
     series turning is the whole thesis. Every previous macro run on this
     desk conditioned a price entry, which can only ever answer "does macro
     help this family" -- never "is macro itself worth trading".

  2. LONGER HOLDS AMORTISE COST. The cost argument is arithmetic: one spread
     crossing over a 10-day hold is a tenth the drag of the same crossing
     over a 1-day hold. So hold length is swept explicitly -- 1, 5, 10 and 20
     trading days -- and the cost drag is REPORTED PER CELL rather than
     assumed away. If the claim is right, t should climb with hold length.
     That is a directional prediction the sweep can falsify.

WHAT WOULD MAKE THIS WRONG, STATED BEFORE THE RUN

If t is flat or falling across hold length, the cost-amortisation argument
does not survive on this data and should be dropped rather than re-explained.
Writing that here, before seeing the numbers, is what stops the result being
reinterpreted after the fact.

POINT-IN-TIME. `family_macro_swing` lags every macro series by one day before
joining, because FRED publishes daily market series the following morning.
Joining on the reference date reads a number nobody had -- a small systematic
look-ahead, which is the profile most likely to survive a naive split and
then fail live.

STAGE A. Ranking only, screening bar t >= 1.96, per TWO_STAGE_DISCOVERY_LAW.
Nothing here promotes anything; promotion needs forward evidence in a slot.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from mt5desk import families, macro_regime  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
SCREEN_BAR = 1.96

#: symbol -> (macro column, sign, economic reason).
#: sign=-1: a FALLING series is the bullish state for this symbol.
DRIVER = {
    "XAUUSD": ("REAL_YIELD_10Y", -1, "zero-coupon: real yield IS the carry cost"),
    "XAGUSD": ("REAL_YIELD_10Y", -1, "same carry logic, higher beta"),
    "GBPUSD": ("DXY", -1, "USD-quoted: a weaker dollar lifts the pair"),
    "AUDUSD": ("DXY", -1, "USD-quoted commodity currency"),
    "NZDUSD": ("DXY", -1, "USD-quoted, risk-sensitive"),
    "USDJPY": ("DGS10", +1, "the classic carry driver: higher US 10y lifts USDJPY"),
    "BTCUSD": ("VIX", -1, "trades as a risk asset, not as digital gold"),
    "ETHUSD": ("VIX", -1, "trades as a risk asset"),
}

#: trading days -> H1 bars (24h sessions). The claim under test is that t
#: RISES along this axis.
HOLDS = {"1d": 24, "5d": 120, "10d": 240, "20d": 480}


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    hist = macro_regime.load_history()
    if hist is None:
        print("MACRO HISTORY ABSENT -- UNMEASURED, not a clean result.")
        return 2

    print("Macro-as-edge swing sweep. STAGE A ranking, screening bar "
          f"t >= {SCREEN_BAR}\n"
          "PREDICTION UNDER TEST: t rises with hold length (cost amortisation).\n")

    rows = []
    for sym, (col, sign, why) in DRIVER.items():
        p = UNI / f"{sym}_H1.parquet"
        if not p.exists() or sym not in meta or col not in hist.columns:
            continue
        h1 = pd.read_parquet(p)
        costs = Costs.from_symbol(meta[sym], mult=2.0)
        series = hist[col]

        for hold_name, hold_bars in HOLDS.items():
            sigs = families.family_macro_swing(
                h1, series, hold_bars=hold_bars, sign=sign)
            res = run_backtest(h1, sigs, costs)
            trades = res.trades
            n = len(trades)
            if n < 20:
                rows.append({"symbol": sym, "driver": col, "hold": hold_name,
                             "n": n, "t": float("nan"), "exp": float("nan"),
                             "why": why})
                continue
            r = np.array([t.r_multiple for t in trades])
            t_stat = float(r.mean() / (r.std(ddof=1) / np.sqrt(n)))
            rows.append({"symbol": sym, "driver": col, "hold": hold_name,
                         "n": n, "t": t_stat, "exp": float(r.mean()), "why": why})

    print(f"{'symbol':<8} {'driver':<16} {'hold':>5} {'n':>5} {'exp R':>9} {'t':>7}")
    for r in rows:
        td = f"{r['t']:7.2f}" if r["t"] == r["t"] else "    n/a"
        ed = f"{r['exp']:+9.4f}" if r["exp"] == r["exp"] else "      n/a"
        print(f"{r['symbol']:<8} {r['driver']:<16} {r['hold']:>5} {r['n']:5d} {ed} {td}")

    # The directional test: within each symbol, does t rise with hold length?
    print("\nDOES t RISE WITH HOLD LENGTH? (the cost-amortisation claim)")
    order = list(HOLDS)
    rising = flat = 0
    for sym in DRIVER:
        ts = [next((r["t"] for r in rows if r["symbol"] == sym and r["hold"] == h),
                   float("nan")) for h in order]
        good = [t for t in ts if t == t]
        if len(good) < 2:
            continue
        verdict = "RISES" if good[-1] > good[0] else "does not rise"
        rising += verdict == "RISES"
        flat += verdict != "RISES"
        disp = "  ".join(f"{h}={t:+.2f}" if t == t else f"{h}=n/a"
                         for h, t in zip(order, ts))
        print(f"  {sym:<8} {disp}   -> {verdict}")
    print(f"\n  {rising} symbol(s) rise with hold length, {flat} do not.")

    ranked = [r for r in rows if r["t"] == r["t"] and r["t"] >= SCREEN_BAR]
    print(f"\n{len(ranked)} cell(s) clear the screening bar t >= {SCREEN_BAR} "
          f"-- RANKED CANDIDATES for a forward slot, not survivors.")
    for r in ranked:
        print(f"  RANKED  {r['symbol']} {r['driver']} hold={r['hold']} "
              f"n={r['n']} t={r['t']:.2f} exp={r['exp']:+.4f}")

    out = BASE / "reports" / "macro_swing_sweep.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"screen_bar": SCREEN_BAR, "rows": rows}, indent=2,
                              default=str), encoding="utf-8")
    print(f"\n-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
