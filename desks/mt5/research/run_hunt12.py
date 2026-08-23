"""Hunt #12: prior-NY mechanism state sweep across the whole universe.

The Asia-gold decomposition (mech_split.py) showed the edge is carried by
prior-NY displacement quality: TREND_DAY +0.908R / NORMAL_DAY +0.459R /
RANGE_DAY dead / FAILED_BREAK strongly negative. This sweep tests the same
state across every symbol x session window in the universe.

For each symbol: classify each trading day by its prior NY session (13-22
UTC; for the JPY/Asia complex NY is the global stress window anyway) and
evaluate each session-window breakout family conditioned on the state.
Battery: n>60, deflated t>2 (family E[max]~1.5), PF>1.05, maxDD>-30R,
3-fold WF all>0, 2x stress.
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
UNI = BASE / "data" / "universe"
E_MAX = 1.5
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
STATES = ["TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK"]


def day_states(h1: pd.DataFrame) -> dict:
    ny = h1.between_time("13:00", "22:00")
    if ny.empty:
        return {}
    by = ny.assign(date=ny.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    by["rng"] = by["hi"] - by["lo"]
    by["rng_med"] = by["rng"].shift(1).rolling(20, min_periods=10).median()
    by["rng_prior"] = by["rng"].shift(1)
    day = h1.assign(date=h1.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    day["dhi"] = day["hi"].shift(1)
    day["dlo"] = day["lo"].shift(1)
    day["g2hi"] = day["hi"].shift(2)
    day["g2lo"] = day["lo"].shift(2)
    by = by.join(day[["dhi", "dlo", "g2hi", "g2lo"]])
    ny_prev = ny.assign(date=ny.index.date).groupby("date")["close"].last()
    out = {}
    for d, r in by.iterrows():
        med = r["rng_med"]
        if not med or pd.isna(med):
            out[d] = "NONE"
            continue
        rp = r["rng_prior"]
        if not rp or pd.isna(rp):
            out[d] = "NONE"
            continue
        st = "TREND_DAY" if rp > 1.5 * med else (
            "RANGE_DAY" if rp < 0.75 * med else "NORMAL_DAY")
        pd_close = ny_prev.get(d - pd.Timedelta(days=1))
        prev_hi, prev_lo = r["dhi"], r["dlo"]
        g2hi, g2lo = r["g2hi"], r["g2lo"]
        if pd_close is not None and prev_hi and prev_lo and g2hi and g2lo \
                and ((prev_hi > g2hi and pd_close < g2hi)
                     or (prev_lo < g2lo and pd_close > g2lo)):
            st = "FAILED_BREAK"
        out[d] = st
    return out


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


def battery(h1: pd.DataFrame, sigs: list, costs: Costs) -> dict:
    r = run_backtest(h1, sigs, costs).stats()
    r2 = run_backtest(h1, sigs, Costs(costs.spread_per_lot * 2,
                                      costs.commission_per_lot * 2,
                                      costs.contract_oz)).stats()
    wf = wf_oos(h1, sigs, costs)
    defl = r["t_stat"] - E_MAX
    gate = (r["n"] > 60 and defl > 2 and r["profit_factor"] > 1.05
            and r["max_dd_r"] > -30
            and len(wf) == 3 and all(w == w and w > 0 for w in wf)
            and r2["expectancy_r"] > 0 and r2["t_stat"] > 1.5)
    return dict(n=r["n"], exp=r["expectancy_r"], t=r["t_stat"], defl=defl,
                pf=r["profit_factor"], maxdd=r["max_dd_r"],
                exp_stress=r2["expectancy_r"], wf=wf, gate=bool(gate))


def main() -> None:
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    log = open(BASE / "logs" / "hunt12_console.txt", "w", encoding="utf-8")
    partial = BASE / "reports" / "hunt12_partial.json"
    done, results = [], []
    if partial.exists():
        try:
            saved = json.loads(partial.read_text(encoding="utf-8"))
            done = saved.get("done", [])
            results = list(saved.get("all", []))
        except Exception:
            pass

    def tprint(*a) -> None:
        msg = " ".join(str(x) for x in a)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    tprint(f"{'sym':>8} {'win':<10} {'state':<12} {'n':>5} {'exp':>7} "
           f"{'t':>5} {'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
    for sym in sorted(meta):
        if sym in done:
            continue
        h1 = pd.read_parquet(UNI / f"{sym}_H1.parquet")
        h1 = families._h1(h1)
        m = meta[sym]
        costs = Costs.from_symbol(m, mult=2.0)
        states = day_states(h1)
        for wname, wp in WINDOWS.items():
            sigs = families.family_session_range_breakout(h1, **wp)
            sdays = [pd.Timestamp(s.time).date() for s in sigs]
            for st_name in STATES:
                sub = [s for s, d in zip(sigs, sdays) if states.get(d) == st_name]
                if len(sub) < 60:
                    continue
                b = battery(h1, sub, costs)
                wfs = " ".join(f"{x:+.3f}" if x == x else "  nan" for x in b["wf"])
                tprint(f"{sym:>8} {wname:<10} {st_name:<12} {b['n']:5d} "
                       f"{b['exp']:+7.3f} {b['t']:5.2f} {b['defl']:5.2f} "
                       f"{b['pf']:5.2f} {b['maxdd']:7.1f} "
                       f"{'PASS' if b['gate'] else 'fail':>5}  WF[{wfs}]")
                results.append(dict(sym=sym, win=wname, state=st_name, **b))
        done.append(sym)
        partial.write_text(json.dumps({"done": done, "all": results}, indent=2,
                                      default=str), encoding="utf-8")
    (BASE / "reports" / "hunt12.json").write_text(
        json.dumps({"survivors": [r for r in results if r["gate"]],
                    "all": results,
                    "swept_at": datetime.now(timezone.utc).isoformat()},
                   indent=2, default=str), encoding="utf-8")
    tprint(f"\n{sum(1 for r in results if r['gate'])} survivors of "
           f"{len(results)} tests across {len(meta)} symbols")
    (BASE / "reports" / "DONE_hunt12").write_text(
        datetime.now(timezone.utc).isoformat(), encoding="utf-8")


if __name__ == "__main__":
    main()
