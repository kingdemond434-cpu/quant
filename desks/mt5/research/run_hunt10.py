"""Hunt #10: paid-vs-free ablation on the armed gold book.

Framework (MANDATE_FREE_DATA_SUPREMACY §8): A) base strategy; B) base +
free-proxy state gate. Measures deltas in n/exp/PF/maxDD/stress OOS on the
ALREADY-VALIDATED gold book. Gated subsets are evidence for conditioning
upgrades, NOT re-validation of the signal itself.

PIT: states activate at COT publication (report_date+6d) or next H1 bar after
FRED value date; gates use only state available at signal time.
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

GATES = {
    "base": lambda st: np.ones(len(st), dtype=bool),
    "macro_stress_hi": lambda st: st["gold_macro_stress"] > 0.5,
    "macro_stress_lo": lambda st: st["gold_macro_stress"] < -0.5,
    "physical_paper_extreme": lambda st: (st["gold_physical_paper"] > 0.8) | (st["gold_physical_paper"] < 0.2),
    "real_yield_extreme": lambda st: st["gold_real_yield_z"].abs() > 1.0,
    "risk_off": lambda st: st["gold_risk_off_z"] > 0.0,
    "jpy_am_lm_extreme": lambda st: (st["jpy_tff_am_minus_lm_pct"] > 0.8) | (st["jpy_tff_am_minus_lm_pct"] < 0.2),
    "jpy_breadth_weak": lambda st: st["jpy_cross_breadth"] < 0.3,
    "jpy_breadth_strong": lambda st: st["jpy_cross_breadth"] > 0.7,
    "session_expanding": lambda st: st["session_range_z"] > 0.0,
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


def main() -> None:
    h1 = pd.read_parquet(BASE / "data" / "universe" / "XAUUSD_H1.parquet")
    h1 = families._h1(h1)
    st = pd.read_parquet(BASE / "data" / "states" / "free_states.parquet").reindex(h1.index)

    win_sigs = {w: families.family_session_range_breakout(h1, **p)
                for w, p in WINDOWS.items()}

    def eval_sigs(sigs: list) -> dict:
        res = run_backtest(h1, sigs, COSTS)
        sts = res.stats()
        res2 = run_backtest(h1, sigs, STRESS)
        sts2 = res2.stats()
        wf = wf_oos(h1, sigs, COSTS)
        return dict(n=sts["n"], exp_r=sts["expectancy_r"], t=sts["t_stat"],
                    pf=sts["profit_factor"], maxdd=sts["max_dd_r"],
                    exp_stress=sts2["expectancy_r"], t_stress=sts2["t_stat"],
                    wf=wf)

    rows = {}
    for gname, gfn in GATES.items():
        m = gfn(st)
        mask = m.to_numpy() if hasattr(m, "to_numpy") else np.asarray(m)
        mask = mask.astype(bool)
        kept = {w: [s for s in sigs if mask[st.index.get_loc(s.time)]]
                for w, sigs in win_sigs.items()}
        n_all = sum(len(v) for v in kept.values())
        if n_all < 60:
            rows[gname] = dict(n=0)
            print(f"{gname:<22} n={n_all:5d} (insufficient)")
            continue
        base = eval_sigs([s for v in kept.values() for s in v])
        rows[gname] = base
        d = base
        wfs = " ".join(f"{w:+.3f}" if w == w else "  nan" for w in d["wf"])
        print(f"{gname:<22} n={d['n']:5d} exp={d['exp_r']:+.3f} t={d['t']:5.2f} "
              f"PF={d['pf']:5.2f} maxDD={d['maxdd']:7.1f}R stress={d['exp_stress']:+.3f} "
              f"WF[{wfs}]")

    base = rows["base"]
    print("\ndelta vs base:")
    for gname in GATES:
        if gname == "base" or rows[gname]["n"] == 0:
            continue
        d = rows[gname]
        print(f"  {gname:<22} dn={d['n']-base['n']:+6d}  dexp={d['exp_r']-base['exp_r']:+.4f} "
              f"  dt={d['t']-base['t']:+.2f}  dPF={d['pf']-base['pf']:+.3f}")

    (BASE / "reports" / "hunt10.json").write_text(
        json.dumps({"swept_at": datetime.now(timezone.utc).isoformat(),
                    "base": rows["base"], "gates": rows}, indent=2, default=str),
        encoding="utf-8")


if __name__ == "__main__":
    main()