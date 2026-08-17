"""Hunt #11: formalize hunt10 conditioning gates into deployable candidates.

The three winning free-proxy gates (macro_stress_hi, session_expanding,
jpy_breadth_strong) are evaluated with the FULL battery here:
  per-window breakdown (which windows carry the improvement),
  full-sample battery (n>60, deflated t>2, PF>1.05, maxDD>-30R,
  3-fold WF OOS all>0, 2x cost stress),
  family-level deflated t (9 gate tests in the hunt10 family,
  E[max_9 Z] ~ 1.49),
  AND-combination of the three gates.

These are conditioning upgrades to an already-validated book, not new
signal families. Deployment only after the same evidence standards.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
COSTS = Costs(spread_per_lot=0.48, commission_per_lot=3.50, contract_oz=100)
STRESS = Costs(spread_per_lot=0.96, commission_per_lot=7.00, contract_oz=100)
E_MAX_9 = 1.49  # E[max of 9 iid standard normals] - gate family size

GATES = {
    "macro_stress_hi": lambda st: st["gold_macro_stress"] > 0.5,
    "session_expanding": lambda st: st["session_range_z"] > 0.0,
    "jpy_breadth_strong": lambda st: st["jpy_cross_breadth"] > 0.7,
    "all_three": lambda st: ((st["gold_macro_stress"] > 0.5)
                             & (st["session_range_z"] > 0.0)
                             & (st["jpy_cross_breadth"] > 0.7)),
}


def wf_oos(h1: pd.DataFrame, sigs: list, costs: Costs) -> list[float]:
    idx_ns = h1.index.to_numpy().astype("datetime64[ns]").astype("int64")
    sig_ns = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
    sig_locs = np.searchsorted(idx_ns, sig_ns)
    n = len(h1)
    fold = n // 3
    out = []
    for k in range(3):
        o0, o1 = k * fold, (k + 1) * fold if k < 2 else n
        sub_sigs = [s for s, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
        r = run_backtest(h1.iloc[o0:o1], sub_sigs, costs)
        if r.n < 20:
            out.append(np.nan)
        else:
            out.append(float(np.mean([t.r_multiple for t in r.trades])))
    return out


def battery(h1: pd.DataFrame, sigs: list) -> dict:
    r = run_backtest(h1, sigs, COSTS).stats()
    r2 = run_backtest(h1, sigs, STRESS).stats()
    wf = wf_oos(h1, sigs, COSTS)
    defl_t = r["t_stat"] - E_MAX_9
    gate = (r["n"] > 60 and defl_t > 2 and r["profit_factor"] > 1.05
            and r["max_dd_r"] > -30
            and len(wf) == 3 and all(w == w and w > 0 for w in wf)
            and r2["expectancy_r"] > 0 and r2["t_stat"] > 1.5)
    return dict(n=r["n"], exp=r["expectancy_r"], t=r["t_stat"],
                defl_t=defl_t, pf=r["profit_factor"], maxdd=r["max_dd_r"],
                exp_stress=r2["expectancy_r"], wf=wf, gate=bool(gate))


def main() -> None:
    h1 = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
    h1 = families._h1(h1)
    st = pd.read_parquet(BASE / "data" / "states" / "free_states.parquet").reindex(h1.index)

    win_sigs = {w: families.family_session_range_breakout(h1, **p)
                for w, p in WINDOWS.items()}
    out = {"swept_at": datetime.now(timezone.utc).isoformat(),
           "family": "hunt10_gate_family", "E_max_9": E_MAX_9,
           "gates": {}, "windows": {}}
    for gname, gfn in GATES.items():
        m = gfn(st).to_numpy() if hasattr(gfn(st), "to_numpy") else np.asarray(gfn(st))
        m = m.astype(bool)
        kept = {w: [s for s in sigs if m[st.index.get_loc(s.time)]]
                for w, sigs in win_sigs.items()}
        all_sigs = [s for v in kept.values() for s in v]
        b = battery(h1, all_sigs)
        out["gates"][gname] = b
        per_win = {}
        for w, sigs in kept.items():
            per_win[w] = battery(h1, sigs)
        out["windows"][gname] = per_win
        wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
        print(f"{gname:<20} n={b['n']:5d} exp={b['exp']:+.3f} t={b['t']:5.2f} "
              f"defl_t={b['defl_t']:5.2f} PF={b['pf']:5.2f} "
              f"maxDD={b['maxdd']:7.1f} stress={b['exp_stress']:+.3f} "
              f"WF[{wfs}] {'PASS' if b['gate'] else 'fail'}")
        for w, wb in per_win.items():
            print(f"    {w:<10} n={wb['n']:4d} exp={wb['exp']:+.3f} "
                  f"t={wb['t']:5.2f} PF={wb['pf']:5.2f}")
    (BASE / "reports" / "hunt11.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()