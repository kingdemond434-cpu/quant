"""Hunt #8: COT-conditioned positioning sweep.

Families: cot_net_fade, cot_change_fade, cot_change_momentum, cot_comm_follow
on every symbol with a mapped CFTC contract (14 symbols). Weekly cadence,
Monday-open entries. Same gate battery as hunt7: t>2, n>60, PF>1.05,
maxDD>-30R, 3-fold WF OOS all > 0, 2x cost stress. Multiplicity-corrected
survivors annotated by research/multiplicity.py.

Standing schedule: runs with hunt7 (Monday 23:00 UTC) after universe refresh.
"""

import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk import data, families  # noqa: E402
from mt5desk.engine import Costs, run_backtest  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
LOG = open(BASE / "logs" / "hunt8_console.txt", "w", encoding="utf-8")

COT_FAMILIES = [
    ("cot_net_fade", families.family2_cot_net_fade, dict()),
    ("cot_change_fade", families.family2_cot_change_fade, dict()),
    ("cot_change_momentum", families.family2_cot_change_momentum, dict()),
    ("cot_comm_follow", families.family2_cot_comm_follow, dict()),
]


def tprint(*a) -> None:
    msg = " ".join(str(x) for x in a)
    print(msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    symbols = [s for s in sorted(meta) if s in data._SYMBOL_SLUG
               and (data._COT / f"{data._SYMBOL_SLUG[s]}.parquet").exists()]

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

    partial = BASE / "reports" / "hunt8_partial.json"
    done = []
    results = []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            done = []
    tprint(f"{'sym':>8} {'family':<20} {'n':>5} {'exp_R':>7} {'t':>5} "
           f"{'PF':>5} {'maxDD_R':>7} {'WF(oos)':>16} {'GATE':>5}")
    remaining = [s for s in symbols if s not in done]
    import sys as _sys
    if len(_sys.argv) > 2:
        remaining = [s for s in _sys.argv[2].split(",") if s in symbols]
    limit = int(_sys.argv[1]) if len(_sys.argv) > 1 else len(remaining)
    for sym in remaining[:limit]:
        if sym in done and not (_sys.argv[2] if len(_sys.argv) > 2 else ""):
            tprint(f"{sym:>8} (resumed - already done)")
            continue
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        h1 = families._h1(h1)
        cot = data.load_cot(sym)
        costs = per_symbol_costs(sym)
        for label, fn, params in COT_FAMILIES:
            sigs = fn(h1, cot, **params)
            if not sigs:
                tprint(f"{sym:>8} {label:<20} (no signals)")
                continue
            res = run_backtest(h1, sigs, costs)
            st = res.stats()
            if st["n"] < 30:
                tprint(f"{sym:>8} {label:<20} n={st['n']} <30 skipped")
                continue
            if st["t_stat"] < 1.8:
                tprint(f"{sym:>8} {label:<20} {st['n']:5d} {st['expectancy_r']:7.3f} "
                       f"{st['t_stat']:5.2f} {st['profit_factor']:5.2f} "
                       f"{st['max_dd_r']:7.1f} [fail-fast] {'fail':>5}")
                results.append(dict(sym=sym, family=label, **st, wf_oos=[], gate=False,
                                    exp_stressed=0.0, t_stressed=0.0))
                continue
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
            tprint(f"{sym:>8} {label:<20} {st['n']:5d} {st['expectancy_r']:7.3f} "
                   f"{st['t_stat']:5.2f} {st['profit_factor']:5.2f} "
                   f"{st['max_dd_r']:7.1f} [{wfs}] {'PASS' if gate else 'fail':>5}")
            results.append(dict(sym=sym, family=label, **st, wf_oos=wf,
                                gate=bool(gate), exp_stressed=st2["expectancy_r"],
                                t_stressed=st2["t_stat"]))
        done.append(sym)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")

    (BASE / "reports" / "hunt8.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]],
                    "all": results,
                    "swept_at": pd.Timestamp.now("UTC").isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of "
           f"{len(results)} tests across {len(symbols)} symbols")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.write(traceback.format_exc())
        LOG.flush()
        raise