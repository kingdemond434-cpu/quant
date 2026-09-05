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

# main() has called these since the E_MAX correction and never imported them, so
# the script has been dead at line 174 -- a NameError two statements into main(),
# AFTER the module imports cleanly. A collection gate cannot see that and neither
# can a smoke import; only running it does.
from mt5desk.multiplicity import deflation, sweep_size  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
UNI = BASE / "data" / "universe"
# MULTIPLICITY, SIZED TO THE SWEEP THAT IS ACTUALLY RUN. This was `E_MAX = 1.5`, a constant
# copied from hunt11's "E[max of 9 iid normals]" -- but this sweep tests symbols x 4 windows x 4
# states, which was 352 cells on the 22-symbol universe and grows with every symbol added. The
# honest bar for 352 cells is E[max t] = 2.93, so the gate demanded t > 3.5 where it should have
# demanded t > 4.9. Re-judging hunt12's own output at its own sweep size takes 9 survivors to 3.
#
# Left as a module-level default ONLY so importers that call battery() directly keep working;
# main() overrides it with the real grid size before sweeping. See mt5desk.multiplicity.
E_MAX = 1.5
WINDOWS = {
    "asia": dict(range_start=7, wait_bars=12, rr=2.0, ttl_bars=12),
    "london_am": dict(range_start=10, range_end=13, signal_at=13, wait_bars=8, rr=2.0, ttl_bars=12),
    "ny_open": dict(range_start=13, range_end=14, signal_at=14, wait_bars=12, rr=2.0, ttl_bars=12),
    "afternoon": dict(range_start=14, range_end=17, signal_at=17, wait_bars=8, rr=2.0, ttl_bars=12),
}
STATES = ["TREND_DAY", "NORMAL_DAY", "RANGE_DAY", "FAILED_BREAK"]


def day_states(h1: pd.DataFrame) -> dict:
    """Each calendar day labelled from the most recent COMPLETED prior NY session.

    CAUSALITY: the label for day D derives only from sessions strictly before D (the original
    same-day join gated an 07:00 asia signal with data through 22:00 the same day -- gold asia
    TREND_DAY t=11.34 fell to 2.79 corrected; `_day_states_same_day` below reproduces that
    artifact and must never gate a trade).

    AVAILABILITY: iterate the BAR CALENDAR, not the labelled days -- this distinction is
    load-bearing. Keying the result on days that have their OWN completed NY session is fine on
    a finished history and WRONG the moment this runs live: at 07:00 UTC today's 13:00-22:00
    block does not exist yet, so today would carry no label and `gateway.state_allows` /
    `run_family_sleeves` would refuse every state-conditioned sleeve forever -- a silent live
    suppressor that replay cannot see. The state a morning signal needs was fully observable at
    22:00 yesterday and is available from then on.

    LEVELS: prior-day breakout levels come from NY-session days only -- a 2-bar Sunday stub is
    not a level (L1.68); using it as "yesterday's high" manufactured FAILED_BREAKs on Mondays.

    A day with no completed prior session is OMITTED: "no observation" is not a state and must
    never be tradeable as one (consumers treat absence as refusal).
    """
    ny = h1.between_time("13:00", "22:00")
    if ny.empty:
        return {}
    by = ny.assign(date=ny.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    by["rng"] = by["hi"] - by["lo"]
    by["rng_med"] = by["rng"].rolling(20, min_periods=10).median()
    day = h1.assign(date=h1.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    day = day.reindex(by.index)                # NY-session days only: stubs are not levels
    day["prev_hi"] = day["hi"].shift(1)
    day["prev_lo"] = day["lo"].shift(1)
    ny_close = ny.assign(date=ny.index.date).groupby("date")["close"].last()
    labels: dict = {}
    for y, r in by.iterrows():
        med = r["rng_med"]
        if not med or pd.isna(med):
            continue
        st = "TREND_DAY" if r["rng"] > 1.5 * med else (
            "RANGE_DAY" if r["rng"] < 0.75 * med else "NORMAL_DAY")
        ph, pl = day.at[y, "prev_hi"], day.at[y, "prev_lo"]
        yc = ny_close.get(y)
        if (yc is not None and ph and pl and not pd.isna(ph) and not pd.isna(pl)
                and ((day.at[y, "hi"] > ph and yc < ph)
                     or (day.at[y, "lo"] < pl and yc > pl))):
            st = "FAILED_BREAK"
        labels[y] = st
    if not labels:
        return {}
    labelled = sorted(labels)
    out: dict = {}
    prev_label = None
    li = 0
    for d in sorted({ts.date() for ts in h1.index}):
        while li < len(labelled) and labelled[li] < d:
            prev_label = labels[labelled[li]]
            li += 1
        if prev_label is not None:
            out[d] = prev_label
    return out


def _day_states_same_day(h1: pd.DataFrame) -> dict:
    """The original same-day labelling. LOOKAHEAD -- for reproducing artifacts only.

    Day D's label was computed from D's OWN 13:00-22:00 UTC session and then used to filter D's
    own earlier signals (asia fires 07:00). It produced the desk's headline artifact (gold asia
    TREND_DAY +0.908R t=11.34, falling to +0.191R t=2.79 when corrected) and hunt12's AUDCAD
    survivor cluster (all five fail their own gate corrected). Kept, and kept private, solely so
    those historical claims can be reproduced and shown to be artifacts. It must never gate a
    trade; `day_states` above is the causal join (labels from D-1/D-2 aggregates only), pinned
    by tests/test_day_states_lookahead.py.
    """
    ny = h1.between_time("13:00", "22:00")
    if ny.empty:
        return {}
    by = ny.assign(date=ny.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    by["rng"] = by["hi"] - by["lo"]
    by["rng_med"] = by["rng"].shift(1).rolling(20, min_periods=10).median()
    day = h1.assign(date=h1.index.date).groupby("date").agg(hi=("high", "max"), lo=("low", "min"))
    day["dhi"] = day["hi"].shift(1)
    day["dlo"] = day["lo"].shift(1)
    by = by.join(day[["dhi", "dlo"]])
    out = {}
    for d, r in by.iterrows():
        med = r["rng_med"]
        if not med or pd.isna(med):
            out[d] = "NONE"
            continue
        st = "TREND_DAY" if r["rng"] > 1.5 * med else (
            "RANGE_DAY" if r["rng"] < 0.75 * med else "NORMAL_DAY")
        dhi, dlo = r["dhi"], r["dlo"]
        if dhi and dlo and (r["hi"] > dhi or r["lo"] < dlo):
            nyc = ny[ny.index.date == d]
            if len(nyc) and ((nyc["close"].iloc[-1] < dhi and r["hi"] > dhi)
                             or (nyc["close"].iloc[-1] > dlo and r["lo"] < dlo)):
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
    # DERIVE, NEVER REBUILD: a positional rebuild drops `quote_per_account` back to 1.0 and
    # un-does the account-currency conversion, so the 2x stress landed BELOW the baseline on
    # every JPY cross (measured 2026-08-27). Commission is contractual and does not widen.
    r2 = run_backtest(h1, sigs, costs.stressed(2.0)).stats()
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
    global E_MAX
    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    # SIZE THE CORRECTION TO THE FULL GRID BEFORE SWEEPING A SINGLE CELL. The denominator is
    # every hypothesis the machine will look at -- including the ones that fail instantly --
    # because counting only what passed is how a multiplicity correction gets quietly disarmed.
    E_MAX = deflation(sweep_size(len(meta), len(WINDOWS), len(STATES)))
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
