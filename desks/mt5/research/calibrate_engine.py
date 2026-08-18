"""Point the known-answer probes at the real engine, and prove they bite.

The value of a calibration harness is entirely in whether it catches the bug it
was written for. So this does two runs:

    the engine as it stands now, with Costs.from_symbol
    the engine as it was, with the hardcoded 0.48 that charged gold three
    percent of its spread

If the second does not fail loudly, the harness is decoration.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, "/home/user/Aurum")

from golddesk.calibration import run_all                       # noqa: E402
from mt5desk.engine import Costs, Signal, run_backtest         # noqa: E402

META = json.loads((BASE / "data" / "universe" / "universe.json").read_text("utf-8"))

#: The probe instrument. Gold, because gold is where the bug was.
SYM = "XAUUSD"
STOP = 10.0                       # dollars per ounce, the probe's fixed stop


def _frame(bars):
    idx = pd.date_range("2020-01-01", periods=len(bars), freq="h", tz="UTC")
    return pd.DataFrame(bars, index=idx)


def _signals(df, entries=None):
    """Long every bar at a fixed stop, or the planted entries when given."""
    if entries is not None:
        return [Signal(time=df.index[e["i"]], side=1, stop=e["stop"],
                       target=e["target"], ttl_bars=3, tag="probe")
                for e in entries if e["i"] < len(df) - 2]
    return [Signal(time=t, side=1, stop=float(df["open"].iloc[i]) - STOP,
                   target=float(df["open"].iloc[i]) + 2 * STOP,
                   ttl_bars=3, tag="probe")
            for i, t in enumerate(df.index[:-2])]


def make_engine(spread_per_lot: float, label: str) -> dict:
    m = META[SYM]
    cs = m["contract_size"]

    def costs(mult=1.0):
        return Costs(spread_per_lot=spread_per_lot * mult,
                     commission_per_lot=3.50, contract_oz=cs)

    def no_edge(bars, mult=1.0):
        df = _frame(bars)
        res = run_backtest(df, _signals(df), costs(mult))
        rs = [t.r_multiple for t in res.trades]
        return float(np.mean(rs)) if rs else 0.0

    def no_edge_with_stop(bars, mult=1.0):
        """Expectancy AND the realised mean stop distance.

        The engine enters at the next bar's open, so |entry - stop| is not the
        distance the signal asked for. Returning the realised figure lets the
        probe divide by what actually happened rather than by what was intended.
        """
        df = _frame(bars)
        res = run_backtest(df, _signals(df), costs(mult))
        if not res.trades:
            return 0.0, 0.0
        rs = [t.r_multiple for t in res.trades]
        ds = [abs(t.entry - t.stop) for t in res.trades]
        return float(np.mean(rs)), float(np.mean(ds))

    def planted(bars, entries):
        df = _frame(bars)
        # zero cost: this probe measures whether a planted EDGE is recovered,
        # and leaving cost in would confound the two questions.
        res = run_backtest(df, _signals(df, entries),
                           Costs(1e-9, 0.0, cs))
        rs = [t.r_multiple for t in res.trades]
        return float(np.mean(rs)) if rs else 0.0

    # GROUND TRUTH, taken from the instrument and NOT from what this adapter
    # configured. The first version of this harness took the expected cost from
    # `spread_per_lot`, so in the buggy configuration both sides of the
    # comparison were wrong together and the probe certified a 33x error at
    # 0.64x. A known-answer test has to get its answer from outside the thing
    # under test.
    truth = (m["median_spread_pts"] * m["tick_size"] * cs + 2 * 3.50) / cs
    return {"no_edge": no_edge, "no_edge_with_stop": no_edge_with_stop,
            "planted": planted, "truth_cost_per_unit": truth,
            "stop": STOP, "planted_r": 0.20, "label": label}


def main() -> int:
    m = META[SYM]
    correct = m["median_spread_pts"] * m["tick_size"] * m["contract_size"]
    print(f"CALIBRATING THE REAL ENGINE on {SYM}\n")
    print(f"  correct spread_per_lot  {correct:>8.2f}   "
          f"(={m['median_spread_pts']} pts x {m['tick_size']} x "
          f"{m['contract_size']:.0f})")
    print(f"  the old hardcoded value     0.48   "
          f"({0.48 / correct:.4f}x of it)\n")

    ok = True
    for spread, label in ((correct, "CURRENT: Costs.from_symbol"),
                          (0.48, "THE OLD BUG: hardcoded 0.48")):
        print("=" * 78)
        print(label)
        print("=" * 78)
        rep = run_all(make_engine(spread, label))
        print(rep.render())
        if label.startswith("CURRENT") and not rep.passed:
            ok = False
        if label.startswith("THE OLD") and rep.passed:
            print("  THE HARNESS DID NOT CATCH THE KNOWN BUG. A calibration "
                  "suite that passes a\n  defect it was written for is worse "
                  "than none, because it certifies.\n")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
