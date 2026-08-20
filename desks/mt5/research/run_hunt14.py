"""Hunt #12's grid again, with the stall-tightening exit instead of the flat one.

The five surviving sleeves were found while every candidate wore a fixed target
and a fixed stop. The exit has since changed, and an exit is not post-processing
-- it decides which trades are winners, so it decides which CELLS survive.
Re-judging the old survivor list under a new exit would be reading yesterday's
answer to today's question, so the grid is swept again from scratch.

WHAT IS DELIBERATELY IDENTICAL TO HUNT 12

The universe, the four windows, the four prior-NY states, the cost model, and
every clause of the battery: n > 60, deflated t > 2, PF > 1.05, maxDD > -30R,
three-fold walk-forward all positive, and survival at 2x spread. The
multiplicity correction is sized to the whole grid BEFORE any cell is swept,
exactly as hunt12 does it, because counting only the cells that passed is how a
correction gets quietly disarmed.

THE ONE CHANGE, AND WHY IT IS NOT FREE

Every candidate now carries bank_frac=0, runner_trail_k=4, trail_tighten_k=1,
trail_stall_bars=3. That exit was selected on OTHER data -- 22 instruments of
pullback entries -- so it is not fitted to this grid. But it is one more thing
this sweep shares with a previous search, and a survivor here has passed a
slightly warmer test than a genuinely cold one.

A CELL THAT PASSES HERE AND FAILED IN HUNT 12 IS NOT AUTOMATICALLY NEW EDGE. It
may be a marginal cell rescued by a luckier exit. So every cell is printed
alongside its own hunt12 t-statistic, and the summary separates survivors that
hunt12 also found from ones that are new -- and names the ones that USED to pass
and no longer do, which is the number most likely to be quietly dropped.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mt5desk import families                                     # noqa: E402
from mt5desk.engine import Costs                                 # noqa: E402
from mt5desk.multiplicity import deflation, sweep_size           # noqa: E402
import run_hunt12 as h12                                         # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
OUT = BASE / "reports" / "hunt14.json"

EXIT = dict(bank_frac=0.0, runner_trail_k=4.0, trail_tighten_k=1.0,
            trail_stall_bars=3)


def with_exit(sigs):
    out = []
    for s in sigs:
        s2 = type(s)(**{**s.__dict__})
        for k, v in EXIT.items():
            setattr(s2, k, v)
        out.append(s2)
    return out


def main() -> int:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    h12.E_MAX = deflation(sweep_size(len(meta), len(h12.WINDOWS),
                                     len(h12.STATES)))
    print(f"HUNT 14 — hunt12's grid, stall-tightening exit")
    print(f"{len(meta)} symbols x {len(h12.WINDOWS)} windows x "
          f"{len(h12.STATES)} states, E[max t] = {h12.E_MAX:.2f}, "
          f"gate needs deflated t > 2\n")

    old = {}
    p12 = BASE / "reports" / "hunt12.json"
    if p12.exists():
        for r in json.loads(p12.read_text("utf-8")).get("all", []):
            old[(r["sym"], r["win"], r["state"])] = r
    print(f"hunt12 record loaded: {len(old)} cells, "
          f"{sum(1 for r in old.values() if r.get('gate'))} survivors\n")

    print(f"{'sym':>8} {'win':<10} {'state':<12} {'n':>5} {'exp':>7} "
          f"{'t':>5} {'defl':>5} {'PF':>5} {'GATE':>5} {'h12 t':>7}")
    results = []
    for sym in sorted(meta):
        h1 = families._h1(pd.read_parquet(UNI / f"{sym}_H1.parquet"))
        m = meta[sym]
        costs = Costs(
            spread_per_lot=0.48 if sym == "XAUUSD" else max(
                m["median_spread_pts"] * m["tick_size"] * m["contract_size"],
                0.05),
            commission_per_lot=3.50, contract_oz=m["contract_size"])
        states = h12.day_states(h1)
        for wname, wp in h12.WINDOWS.items():
            sigs = families.family_session_range_breakout(h1, **wp)
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
            for st in h12.STATES:
                sub = [s for s, d in zip(sigs, sdays) if states.get(d) == st]
                if len(sub) < 60:
                    continue
                b = h12.battery(h1, with_exit(sub), costs)
                prev = old.get((sym, wname, st)) or {}
                results.append(dict(sym=sym, win=wname, state=st,
                                    hunt12_t=prev.get("t"),
                                    hunt12_gate=prev.get("gate"), **b))
                if b["gate"] or prev.get("gate"):
                    pt = prev.get("t")
                    print(f"{sym:>8} {wname:<10} {st:<12} {b['n']:5d} "
                          f"{b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} "
                          f"{b['pf']:5.2f} "
                          f"{'PASS' if b['gate'] else 'fail':>5} "
                          f"{(pt if pt is not None else float('nan')):7.2f}")

    surv = [r for r in results if r["gate"]]
    kept = [r for r in surv if r.get("hunt12_gate")]
    new = [r for r in surv if not r.get("hunt12_gate")]
    lost = [r for r in results if r.get("hunt12_gate") and not r["gate"]]
    print(f"\n{len(surv)} survivors of {len(results)} cells")
    print(f"  {len(kept)} also survived hunt12 — the same book")
    print(f"  {len(new)} NEW under this exit")
    print(f"  {len(lost)} passed hunt12 and fail now")
    for r in new:
        print(f"    NEW  {r['sym']}.{r['win']}.{r['state']}  "
              f"t {r['t']:.2f} (hunt12 {r['hunt12_t']})")
    for r in lost:
        print(f"    LOST {r['sym']}.{r['win']}.{r['state']}  "
              f"t {r['t']:.2f} (hunt12 {r['hunt12_t']})")
    OUT.write_text(json.dumps(
        {"exit": EXIT, "e_max": h12.E_MAX, "survivors": surv, "all": results,
         "swept_at": datetime.now(timezone.utc).isoformat()},
        indent=2, default=str), "utf-8")
    print(f"\nwritten: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
