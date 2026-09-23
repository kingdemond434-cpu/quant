"""Hunt #12: prior-NY mechanism state sweep across the hypothesis lane.

The Asia-gold decomposition (mech_split.py) showed the edge is carried by
prior-NY displacement quality: TREND_DAY +0.908R / NORMAL_DAY +0.459R /
RANGE_DAY dead / FAILED_BREAK strongly negative. This sweep tests the same
state across every symbol x session window in the universe.

For each symbol: classify each trading day by its prior NY session (13-22
UTC; for the JPY/Asia complex NY is the global stress window anyway) and
evaluate each session-window breakout family conditioned on the state.
Battery: n>60, deflated t>2 (family E[max]~1.5), PF>1.05, maxDD>-30R,
3-fold WF all>0, 2x stress.

THIS SWEEP IS AN INPUT TO THE MONEY PATH, WHICH IS NOT OBVIOUS FROM HERE. Its artifact
`reports/hunt12_partial.json` is the survivor list `portfolio_projection.load_h12_survivors`
reads, and `pf_allocator` -- the growth-maximising sizer every sleeve's heat comes from --
assembles its evidence through that projection. So an absent hunt12 report is not a missing
research report: it is the allocator refusing to solve, on every pass, for want of an input.

    MEASURED 2026-09-10, on a checkout of the same code the box runs:

        $ python desks/mt5/research/pf_allocator.py --mode normal
        REFUSING to project a portfolio without .../reports/hunt12_partial.json
        exit 1

    `data/PF_ALLOCATOR_ARMED` has been present since 2026-09-04 and
    `reports/pf_allocation.json` has never existed. The allocator leg was added to the hourly
    cycle, it is armed, and everything downstream is wired to consume it -- and it refused every
    single pass, because THIS sweep had exactly one scheduler: `research_supervisor`, keyed on a
    one-shot `reports/DONE_hunt12` marker, on a worker the cycle's own comments record as dead or
    stalled. One-shot means the artifact is produced once, ever, or never. It was never.

    That is why every sleeve on this desk sizes off `ramped_fraction` -- the authority ramp, a
    function of how many trades a sleeve has closed, which contains no estimate of growth at all.

SO IT IS ROUTED BY LANE AND IT IS RESUMABLE, and those two facts are what let it hold a clock.
Routing drops the single-name equities the principal's 2026-09-06 standing order says are never
hunted for statistical hypotheses (145 of 251 symbols are in the hypothesis lane today), which
is both the mandate and the difference between a sweep that fits in an hourly budget and one
that does not. `done` carries across passes, so a 12-minute leg advances the sweep and the next
hour finishes it rather than restarting it.

AND THE ARTIFACT SAYS WHETHER IT IS FINISHED. A resumable sweep read by a portfolio builder is
the silent-truncation defect wearing a new hat: 85 symbols of 145, loaded as if they were the
book, would be exactly the GOLD-ONLY failure `load_h12_survivors` already refuses. `complete` is
written on every pass and the loader refuses a False.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

from research import universe_policy  # noqa: E402

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

#: When the carried sweep is old enough to be worth re-running from scratch. A week of H1 bars is
#: about 120 rows against the ~54,000 each symbol carries -- two tenths of one percent -- so an
#: hourly re-sweep would burn the box to re-derive the same numbers. The clock exists so the
#: artifact cannot go stale forever, not because the answer moves within a day.
MAX_AGE_H = 168.0

PARTIAL_REL = "reports/hunt12_partial.json"


def routed_universe(meta: dict) -> tuple[list[str], dict[str, list[str]]]:
    """The symbols this sweep may look at, and what it set aside, by lane.

    THE EQUITIES ARE NOT DROPPED TO MAKE THE SWEEP FASTER. They are dropped because the
    principal's standing order of 2026-09-06 says a single name's edge is sought in the event
    lane -- news, financial reports, earnings reaction -- and never by fitting a session-range
    breakout across its own scheduled disclosures. That this also takes 251 symbols to 145 and
    brings the sweep inside an hourly budget is a consequence, not the reason.

    IT ALSO REPAIRS THE MULTIPLICITY DENOMINATOR RATHER THAN LOOSENING IT. `E_MAX` is sized to
    the cells the machine ACTUALLY LOOKS AT, which is this module's own stated rule; sweeping
    251 symbols charged every FX and metals cell for 106 equity columns that should never have
    been tested. Measured: 4,016 cells -> 2,320, E[max t] 3.621 -> 3.476. The bar moves by 0.145
    of a t, so nobody can mistake this for a hunt for survivors -- the mandate is the point and
    the arithmetic barely moves.
    """
    split = universe_policy.split(meta)
    return split[universe_policy.HYPOTHESIS], split


def _carried(partial: Path, routed: list[str], now: datetime,
             max_age_h: float) -> tuple[list[str], list[dict], str]:
    """Resume the sweep on disk, or start fresh, and say which and why.

    THREE THINGS INVALIDATE A CARRIED SWEEP, and all three are the same failure: results judged
    against a grid that is no longer the grid being run.

      * age             past `max_age_h` the bars have moved enough to be worth re-deriving
      * a changed lane  a partial written before routing carries equity cells judged at the old
                        E_MAX, and merging them into a routed sweep produces one artifact holding
                        two different multiplicity corrections
      * unreadable      absent or corrupt is a fresh start, never a silent empty book
    """
    if not partial.exists():
        return [], [], "no carried sweep"
    try:
        saved = json.loads(partial.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], "carried sweep unreadable"
    stamp = saved.get("started_at") or saved.get("at") or saved.get("swept_at")
    try:
        age_h = (now - datetime.fromisoformat(str(stamp))).total_seconds() / 3600.0
    except (TypeError, ValueError):
        age_h = None
    if age_h is not None and age_h > max_age_h:
        return [], [], f"carried sweep is {age_h:.0f}h old (max {max_age_h:.0f}h)"
    carried_routed = saved.get("routed")
    if carried_routed is not None and sorted(carried_routed) != sorted(routed):
        return [], [], ("the routed universe changed since the carried sweep "
                        f"({len(carried_routed)} symbols -> {len(routed)})")
    if carried_routed is None:
        return [], [], "the carried sweep predates lane routing, so it holds unrouted cells"
    done = [s for s in (saved.get("done") or []) if s in set(routed)]
    results = [r for r in (saved.get("all") or []) if isinstance(r, dict)]
    return done, results, f"resumed at {len(done)}/{len(routed)}"


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


def _write_atomic(path: Path, doc: dict[str, Any]) -> None:
    """Replace, never truncate-then-write.

    THIS SWEEP IS NOW STOPPED BY A TIMEOUT ON PURPOSE, so a write interrupted halfway is a
    routine event rather than a freak one -- and a half-written `hunt12_partial.json` does not
    read as absent to the loader downstream, it raises JSONDecodeError from inside
    `portfolio_projection`, which is the one failure mode a careful refusal was written to avoid.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    global E_MAX
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-age-h", type=float, default=MAX_AGE_H,
                    help="re-sweep from scratch when the carried sweep is older than this")
    ap.add_argument("--deadline-s", type=float, default=0.0,
                    help="stop cleanly between symbols after this many seconds (0 = no limit)")
    args = ap.parse_args(argv)

    now = datetime.now(UTC)
    t0 = time.monotonic()
    no_bars: list[str] = []

    meta = json.loads((UNI / "universe.json").read_text(encoding="utf-8"))
    routed, split = routed_universe(meta)
    # SIZE THE CORRECTION TO THE GRID THAT IS ACTUALLY SWEPT. The denominator is every hypothesis
    # the machine will look at -- including the ones that fail instantly -- because counting only
    # what passed is how a multiplicity correction gets quietly disarmed. It is the ROUTED
    # universe because the event-lane symbols are not looked at: charging FX and metals for
    # columns nobody tests is the same error in the other direction.
    E_MAX = deflation(sweep_size(len(routed), len(WINDOWS), len(STATES)))

    partial = BASE / Path(*PARTIAL_REL.split("/"))
    partial.parent.mkdir(parents=True, exist_ok=True)
    (BASE / "logs").mkdir(parents=True, exist_ok=True)
    done, results, why = _carried(partial, routed, now, args.max_age_h)
    started_at = now.isoformat()
    if done:
        with suppress(OSError, ValueError, KeyError, TypeError):
            started_at = str(json.loads(partial.read_text("utf-8"))["started_at"])

    def snapshot(stopped: str | None = None) -> dict[str, Any]:
        return {
            "done": done, "all": results,
            # THE ARTIFACT SAYS WHETHER IT IS FINISHED, and the loader refuses a False. A
            # resumable sweep read by a portfolio builder is the silent-truncation defect wearing
            # a new hat: 85 symbols of 145 loaded as the whole book is exactly the GOLD-ONLY
            # failure `load_h12_survivors` already refuses.
            "complete": len(done) >= len(routed),
            "routed": routed, "n_routed": len(routed),
            "set_aside": {k: v for k, v in split.items()
                          if k != universe_policy.HYPOTHESIS},
            "e_max": float(E_MAX),
            "sweep_cells": int(sweep_size(len(routed), len(WINDOWS), len(STATES))),
            "policy": "desks/mt5/research/universe_policy.py",
            "started_at": started_at, "at": datetime.now(UTC).isoformat(),
            "resume": why, "stopped": stopped,
            "skipped_no_bars": no_bars,
        }

    with open(BASE / "logs" / "hunt12_console.txt", "a", encoding="utf-8") as log:
        def tprint(*a) -> None:
            msg = " ".join(str(x) for x in a)
            print(msg, flush=True)
            log.write(msg + "\n")
            log.flush()

        tprint(f"hunt12: {len(routed)} hypothesis-lane symbols of {len(meta)} "
               f"({len(split[universe_policy.EVENT])} event lane, "
               f"{len(split[universe_policy.UNCLASSIFIED])} unclassified), "
               f"E_MAX {E_MAX:.3f}; {why}")
        tprint(f"{'sym':>8} {'win':<10} {'state':<12} {'n':>5} {'exp':>7} "
               f"{'t':>5} {'defl':>5} {'PF':>5} {'maxDD':>7} {'GATE':>5}")
        stopped = None
        for sym in routed:
            if sym in done:
                continue
            if args.deadline_s and (time.monotonic() - t0) > args.deadline_s:
                # STOP BETWEEN SYMBOLS RATHER THAN BE KILLED INSIDE ONE. The hourly leg's budget
                # is 720s; a SIGKILL mid-symbol loses that symbol's work and can land in the
                # middle of a write. Stopping cleanly is what makes the resume trustworthy.
                stopped = f"deadline {args.deadline_s:.0f}s reached at {len(done)}/{len(routed)}"
                tprint(f"\n{stopped}")
                break
            bars = UNI / f"{sym}_H1.parquet"
            if not bars.exists():
                # ONE MISSING PARQUET MUST NOT TAKE THE SWEEP DOWN. Unguarded, this raised and
                # lost every symbol's work after it -- on a job that now holds a clock, that is
                # an outage rather than a gap. Named in the artifact, never silently skipped.
                no_bars.append(sym)
                done.append(sym)
                continue
            h1 = families._h1(pd.read_parquet(bars))
            costs = Costs.from_symbol(meta[sym], mult=2.0)
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
            _write_atomic(partial, snapshot(stopped))
        doc = snapshot(stopped)
        _write_atomic(partial, doc)

        if doc["complete"]:
            _write_atomic(BASE / "reports" / "hunt12.json",
                          {"survivors": [r for r in results if r.get("gate")],
                           "all": results, "e_max": float(E_MAX),
                           "routed": routed, "set_aside": doc["set_aside"],
                           "swept_at": datetime.now(UTC).isoformat()})
            (BASE / "reports" / "DONE_hunt12").write_text(
                datetime.now(UTC).isoformat(), encoding="utf-8")
        tprint(f"\n{sum(1 for r in results if r.get('gate'))} survivors of "
               f"{len(results)} tests across {len(done)}/{len(routed)} symbols "
               f"({'complete' if doc['complete'] else 'INCOMPLETE'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
