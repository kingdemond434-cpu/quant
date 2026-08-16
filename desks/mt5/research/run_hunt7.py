"""Hunt #7: standing universe sweep of every cost-free mechanism family.

19+3 symbols x {asia_momentum, momentum_volgate, monday_gap, london_close_momentum,
spread_state_avoidance, dow_effect (negative control), comex_settlement, session_range_breakout
x 4 windows + spread_gate twin}. Fixed params per family (no per-symbol optimization).

Gate battery identical to hunt6: t>2, n>60, PF>1.05, maxDD>-30R, 3-fold WF OOS all folds > 0,
2x cost stress (exp>0, t>1.5). Checkpoint/resume via hunt7_partial.json, --force for reruns.

Standing schedule: runs automatically weekly (Monday 23:00 UTC) via run_gateway_loop.py after
the universe fetch refreshes the H1 cache.
"""

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
LOG = open(BASE / "logs" / "hunt7_console.txt", "w", encoding="utf-8")

BREAKOUT_WINDOWS = [
    ("asia", dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12)),
    ("london_am", dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12)),
    ("ny_open", dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12)),
    ("afternoon", dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12)),
]

GLOBAL_FAMILIES = [
    ("asia_momentum", families.family_asia_momentum, dict()),
    ("momentum_volgate", families.family_momentum_volgate, dict()),
    ("monday_gap", families.family_monday_gap, dict(mode="momentum")),
    ("monday_gap_fade", families.family_monday_gap, dict(mode="fade")),
    ("london_close_momentum", families.family_london_close_momentum, dict()),
    ("spread_state_avoidance", families.family7_spread_state_avoidance, dict()),
    ("dow_effect", families.family_dow_effect, dict()),  # negative control
    ("comex_settlement", families.family4_comex_settlement_effect, dict()),
]


def tprint(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))

    def per_symbol_costs(sym: str) -> Costs:
        m = meta[sym]
        spread = 0.48 if sym == "XAUUSD" else (
            m["median_spread_pts"] * m["tick_size"] * m["contract_size"])
        return Costs(spread_per_lot=max(spread, 0.05),
                     commission_per_lot=3.50, contract_oz=m["contract_size"])

    def wf_oos(h1: pd.DataFrame, sigs: list, costs: Costs) -> list[float]:
        idx_ns = h1.index.to_numpy().astype("datetime64[ns]").astype("int64")
        sig_ns = np.array([pd.Timestamp(s.time).value for s in sigs], dtype="int64")
        sig_locs = np.searchsorted(idx_ns, sig_ns)
        n = len(h1)
        fold = n // 3
        exps = []
        for k in range(3):
            o0, o1 = k * fold, (k + 1) * fold if k < 2 else n
            sub = h1.iloc[o0:o1]
            sub_sigs = [s for s, sl in zip(sigs, sig_locs) if o0 <= sl < o1]
            r = run_backtest(sub, sub_sigs, costs)
            if r.n < 20:
                exps.append(np.nan)
            else:
                rs = np.array([t.r_multiple for t in r.trades])
                exps.append(float(rs.mean()))
        return exps

    def test_one(sym: str, label: str, sigs: list, costs: Costs) -> dict | None:
        if not sigs:
            return None
        res = run_backtest(h1, sigs, costs)
        st = res.stats()
        if st["n"] < 30:
            return None
        if st["t_stat"] < 1.8:
            tprint(f"{sym:>8} {label:<22} {st['n']:5d} {st['expectancy_r']:7.3f} "
                   f"{st['t_stat']:5.2f} {st['profit_factor']:5.2f} {st['max_dd_r']:7.1f} "
                   f"[fail-fast] {'fail':>5}")
            return dict(sym=sym, family=label, **st, wf_oos=[], gate=False,
                        exp_stressed=0.0, t_stressed=0.0)
        wf = wf_oos(h1, sigs, costs)
        wf_ok = len(wf) == 3 and all(w == w and w > 0 for w in wf)
        c2 = Costs(spread_per_lot=costs.spread_per_lot * 2,
                   commission_per_lot=costs.commission_per_lot * 2,
                   contract_oz=costs.contract_oz)
        st2 = run_backtest(h1, sigs, c2).stats()
        stress_ok = st2["expectancy_r"] > 0 and st2["t_stat"] > 1.5
        gate = (st["t_stat"] > 2 and st["n"] > 60 and st["profit_factor"] > 1.05
                and st["max_dd_r"] > -30 and wf_ok and stress_ok)
        wfs = " ".join(f"{w:+.3f}" if w == w else "   nan" for w in wf)
        tprint(f"{sym:>8} {label:<22} {st['n']:5d} {st['expectancy_r']:7.3f} "
               f"{st['t_stat']:5.2f} {st['profit_factor']:5.2f} {st['max_dd_r']:7.1f} "
               f"[{wfs}] {'PASS' if gate else 'fail':>5}")
        return dict(sym=sym, family=label, **st, wf_oos=wf, gate=bool(gate),
                    exp_stressed=st2["expectancy_r"], t_stressed=st2["t_stat"])

    partial = BASE / "reports" / "hunt7_partial.json"
    done = []
    results = []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            done = []
    tprint(f"{'sym':>8} {'family':<22} {'n':>5} {'exp_R':>7} {'t':>5} "
           f"{'PF':>5} {'maxDD_R':>7} {'WF(oos)':>16} {'GATE':>5}")
    remaining = [s for s in sorted(meta) if s not in done]
    import sys as _sys
    if len(_sys.argv) > 2:
        remaining = [s for s in _sys.argv[2].split(",") if s in meta]
    limit = int(_sys.argv[1]) if len(_sys.argv) > 1 else len(remaining)
    for sym in remaining[:limit]:
        if sym in done and not (_sys.argv[2] if len(_sys.argv) > 2 else ""):
            tprint(f"{sym:>8} (resumed - already done)")
            continue
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        h1 = families._h1(h1)
        costs = per_symbol_costs(sym)
        for label, fn, params in GLOBAL_FAMILIES:
            r = test_one(sym, label, fn(h1, **params), costs)
            if r:
                results.append(r)
        for wlabel, p in BREAKOUT_WINDOWS:
            for vlabel, v in [("base", {}), ("spread_gate", {"spread_gate": True})]:
                r = test_one(sym, f"breakout.{wlabel}.{vlabel}",
                             families.family_session_range_breakout(h1, **{**p, **v}), costs)
                if r:
                    results.append(r)
        done.append(sym)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")

    surv = [r for r in results if r["gate"]]
    (BASE / "reports" / "hunt7.json").write_text(
        json.dumps({"survivors": surv, "all": results, "swept_at":
                    pd.Timestamp.utcnow().isoformat()}, indent=2, default=str),
        encoding="utf-8")
    tprint(f"\n{len(surv)} survivors of {len(results)} tests across {len(meta)} symbols")
    for r in surv:
        tprint(f"  PASS {r['sym']} {r['family']}: exp={r['expectancy_r']:.3f}R "
               f"t={r['t_stat']:.2f} PF={r['profit_factor']:.2f} maxDD={r['max_dd_r']:.1f}R "
               f"stress={r['exp_stressed']:.3f}R")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.write(traceback.format_exc())
        LOG.flush()
        raise