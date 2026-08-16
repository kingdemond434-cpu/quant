"""Hunt #6: session-range-breakout across the MT5 universe (19 symbols).

Fixed deployed params (no per-symbol optimization - multiple-testing honest):
4 windows x {baseline, spread_gate} x 19 symbols. Gate: t>2, n>60, PF>1.05,
maxDD>-30R, 3-fold WF OOS all folds positive, 2x cost stress survives.

Costs: per-symbol from universe.json (median spread x tick x contract),
commission 3.5/lot, XAUUSD overridden to the measured live spread 0.48.
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
LOG = open(BASE / "logs" / "hunt6_console.txt", "w", encoding="utf-8")


def tprint(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def main() -> None:
    UNI = BASE / "data" / "universe"
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))

    WINDOWS = [
        ("asia", dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12)),
        ("london_am", dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12)),
        ("ny_open", dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12)),
        ("afternoon", dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12)),
    ]

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

    results = []
    partial = BASE / "reports" / "hunt6_partial.json"
    done = []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            done = []
    tprint(f"{'sym':>8} {'window':>9} {'variant':>12} {'n':>5} {'exp_R':>7} {'t':>5} "
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
        for wlabel, p in WINDOWS:
            for vlabel, v in [("base", {}), ("spread_gate", {"spread_gate": True})]:
                sigs = families.family_session_range_breakout(h1, **{**p, **v})
                if not sigs:
                    continue
                costs = per_symbol_costs(sym)
                res = run_backtest(h1, sigs, costs)
                st = res.stats()
                if st["n"] < 30:
                    continue
                if st["t_stat"] < 1.8:  # fail fast: cannot reach t>2 even with WF
                    tprint(f"{sym:>8} {wlabel:>9} {vlabel:>12} {st['n']:5d} "
                           f"{st['expectancy_r']:7.3f} {st['t_stat']:5.2f} {st['profit_factor']:5.2f} "
                           f"{st['max_dd_r']:7.1f} [fail-fast] {'fail':>5}")
                    results.append(dict(sym=sym, window=wlabel, variant=vlabel, **st,
                                        wf_oos=[], gate=False, exp_stressed=0.0, t_stressed=0.0,
                                        costs=dict(spread=costs.spread_per_lot,
                                                   commission=costs.commission_per_lot)))
                    continue
                wf = wf_oos(h1, sigs, costs)
                wf_ok = len(wf) == 3 and all(w == w and w > 0 for w in wf)
                c2 = Costs(spread_per_lot=costs.spread_per_lot * 2,
                           commission_per_lot=costs.commission_per_lot * 2,
                           contract_oz=costs.contract_oz)
                res2 = run_backtest(h1, sigs, c2)
                st2 = res2.stats()
                stress_ok = st2["expectancy_r"] > 0 and st2["t_stat"] > 1.5
                gate = (st["t_stat"] > 2 and st["n"] > 60 and st["profit_factor"] > 1.05
                        and st["max_dd_r"] > -30 and wf_ok and stress_ok)
                wfs = " ".join(f"{w:+.3f}" if w == w else "   nan" for w in wf)
                results.append(dict(sym=sym, window=wlabel, variant=vlabel, **st,
                                    wf_oos=wf, gate=bool(gate),
                                    exp_stressed=st2["expectancy_r"],
                                    t_stressed=st2["t_stat"],
costs=dict(spread=costs.spread_per_lot,
                                                commission=costs.commission_per_lot)))
                tprint(f"{sym:>8} {wlabel:>9} {vlabel:>12} {st['n']:5d} "
                       f"{st['expectancy_r']:7.3f} {st['t_stat']:5.2f} {st['profit_factor']:5.2f} "
                       f"{st['max_dd_r']:7.1f} [{wfs}] {'PASS' if gate else 'fail':>5}")
        done.append(sym)
        (BASE / "reports" / "hunt6_partial.json").write_text(
            json.dumps({"done": done, "all": results}, indent=2, default=str),
            encoding="utf-8")

    surv = [r for r in results if r["gate"]]
    (BASE / "reports" / "hunt6.json").write_text(
        json.dumps({"survivors": surv, "all": results}, indent=2, default=str),
        encoding="utf-8")
    tprint(f"\n{len(surv)} survivors of {len(results)} tests across {len(meta)} symbols")
    for r in surv:
        tprint(f"  PASS {r['sym']} {r['window']} {r['variant']}: exp={r['expectancy_r']:.3f}R "
               f"t={r['t_stat']:.2f} PF={r['profit_factor']:.2f} maxDD={r['max_dd_r']:.1f}R "
               f"stress={r['exp_stressed']:.3f}R")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.write(traceback.format_exc())
        LOG.flush()
        raise