"""RAISE THE DESK'S DATA CEILING: take every bar the venue will serve, and refuse the fake ones.

THE CEILING WAS OURS, IN FOUR PLACES, AND NOTHING EVER RE-DEEPENED A FILE (measured 2026-09-24).

Every parquet in `data/universe/` held roughly the same ROW COUNT, so the finer the chart the
shorter the calendar it covered -- three months of M1, sixteen of M5 -- and a fast mechanism
could never reach the trading days the deflated-Sharpe hurdle needs. That looked like a broker
limit. It was not. Measured on the live Fusion terminal, per symbol, per timeframe:

  * `scripts/download_all_symbols.py` asks `TIMEFRAME_DEPTH` (M15 80k, M30 60k, H1 50k, D1 10k)
    in ONE positional call, and it SKIPS any (symbol, timeframe) whose file already exists. So
    the depth of every series is frozen forever at whatever the producer that first created it
    happened to ask for, and nothing in the desk ever widens it again. `refresh_tail` only ever
    appends the NEW end.
  * `research/expand_universe.py` asks `_WANT` (M15 60k, M30 40k, D1 5k).
  * `research/fetch_universe.py` asks `INTRADAY_TIMEFRAMES` (M15 60k, M30 40k) and pins H1 to
    `START = 2018-01-01`.
  * the TERMINAL itself caps the chart cache at `TERMINAL_MAXBARS` -- `common.ini [Charts]
    MaxBars=100000` on this box. M1 and M5 stop at exactly 100,000 on EVERY symbol measured and
    never once on a venue end, so those two charts are bounded by a client-side setting and by
    nothing else. Raising it needs a terminal restart, which is not this organ's to take.

What Fusion actually serves, measured (EURUSD): M30 85,712 bars to 1997-10-10, H1 49,198 to
1997-10-10, H4 16,793 to 1997-10-10, D1 7,789 to 1997-10-10. Against that the desk held M30
40,136 (2023-07-04), D1 2,268 (2018-01-02). M15 serves 100,000 to 2022-09-19 against 60,272 held.

AND THE DEEP END IS NOT WHAT IT LOOKS LIKE, WHICH IS WHY THIS ORGAN HAS A FLOOR.
Before ~2019 this venue has only DAILY bars, and MetaTrader renders them on every chart as ONE
BAR PER CALENDAR DAY. EURUSD's M30, H1, H4 and D1 series all report ~260 bars a year from 1997
to 2018 -- the same 260 bars, four times. Splicing that onto an intraday series would not be
extra history, it would be a decade of daily bars wearing an M30 label, and it is the single
easiest way to manufacture an edge that cannot exist. `dense_frontier` finds where a chart
reaches its own recent density and this organ never reaches behind it.

TWO RULES MAKE THIS SAFE TO RUN BESIDE A LIVE TERMINAL:

  * PREPEND ONLY. A bar the file already holds is never rewritten, so nothing the judge has
    already read can change under it and this organ can never fight `refresh_tail` over the live
    end. A killed run loses exactly the symbol it was mid-way through, and the next run resumes.
  * `universe_registry.publish_frame`. Frames are written to a temp file and `os.replace`d, and a
    destination held open by a reader is a reported miss, never a torn file -- `fetch_universe`
    wrote frames straight onto the destination once and a read landing mid-rewrite raised
    `ArrowInvalid` out of the judge's `main()`, killing 19 passes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mt5desk.config import desk_root
from mt5desk.universe_registry import TIMEFRAMES, publish_frame

UNIVERSE = desk_root() / "data" / "universe"
REPORT = UNIVERSE / "venue_history_depth.json"
CURSOR = UNIVERSE / "deepen_cursor.json"

#: Columns a bar frame must carry for the desk to read it. A fetch missing one of these is
#: recorded and skipped rather than published half-shaped.
BAR_COLUMNS = ("open", "high", "low", "close", "tick_volume", "spread", "real_volume")

#: Most bars one `copy_rates_*` call will serve. Above it the terminal returns None with
#: `(-2, 'Terminal: Invalid params')` -- no exception, no partial result, and a shape that reads
#: exactly like "this venue has no history", which is the wrong conclusion to draw from it.
MAX_BARS_PER_CALL = 50_000

#: Ceiling on chunks per (symbol, timeframe). At 50,000 a chunk this reaches 500,000 bars, five
#: times the terminal's current cache cap, so it binds only if MaxBars is raised a long way.
MAX_CHUNKS = 10

#: Minutes of market time one bar spans. Used only to report calendar reach.
TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}

#: A month whose bar count falls below this share of the symbol's OWN recent daily density is
#: before the venue's real intraday history and is refused. Half is deliberately loose: it must
#: separate ~1 bar/day from ~48 bars/day, not police a quiet August.
DENSE_RATIO = 0.5

#: Windows (UTC) in which this organ does not touch the terminal at all. The gold book places at
#: 04:00, 10:00 and 14:00 UTC and a history pull that starves the terminal at that instant is a
#: real cost, not a theoretical one.
BLACKOUTS = ((3, 40, 4, 20), (9, 45, 10, 15), (13, 45, 14, 15))


def in_blackout(now: datetime) -> str:
    """The placement window `now` falls in, or "" when the terminal is ours to ask."""
    mins = now.hour * 60 + now.minute
    for h0, m0, h1, m1 in BLACKOUTS:
        if h0 * 60 + m0 <= mins < h1 * 60 + m1:
            return f"{h0:02d}:{m0:02d}-{h1:02d}:{m1:02d}Z"
    return ""


def dense_frontier(days: Counter[date], tf: str) -> date | None:
    """The first calendar day from which `tf` runs at its OWN recent density, unbroken.

    THE REFERENCE IS THE SYMBOL'S OWN RECENT DENSITY, never a nominal bars-per-day. A US share
    CFD trades 6.5 hours and an FX cross 24, so one constant would call every equity chart
    sparse and refuse history that is perfectly real. The median over the last 60 active days is
    what the chart looks like when it is working.

    Returns None when the whole series is dense -- the common case for a symbol the venue only
    began quoting after it had real intraday data to serve.
    """
    if tf == "D1" or not days:
        return None
    ordered = sorted(days)
    recent = sorted(days[d] for d in ordered[-60:])
    ref = recent[len(recent) // 2] if recent else 0
    if ref <= 1:
        return None                       # a chart with one bar a day everywhere: nothing to cut
    per_month: Counter[tuple[int, int]] = Counter()
    days_month: Counter[tuple[int, int]] = Counter()
    for d in ordered:
        per_month[(d.year, d.month)] += days[d]
        days_month[(d.year, d.month)] += 1
    months = sorted(per_month)
    last_sparse = -1
    for i, m in enumerate(months[:-1]):    # the newest month is partial by construction
        if per_month[m] < DENSE_RATIO * days_month[m] * ref:
            last_sparse = i
    if last_sparse < 0:
        return None
    if last_sparse + 1 >= len(months):
        return ordered[-1]                 # every complete month is sparse: keep nothing older
    y, mo = months[last_sparse + 1]
    return date(y, mo, 1)


def walk_back(mt5: Any, sym: str, code: Any, cap: int) -> tuple[Any, str]:
    """Every bar the terminal will serve for one chart, oldest-first, walking backward in chunks.

    Returns the structured array and WHY the walk stopped, which is the whole measurement:
    "venue-end" means Fusion has no more, "MAXBARS" means the terminal's chart cache refused to
    hold more and the limit is OURS.

    THE TWO ARE EASY TO CONFUSE AND THE CONFUSION IS THE POINT OF THIS ORGAN. A chart pinned at
    the cache cap reports its last request as empty, which reads exactly like a venue that ran
    out -- so a walk that lands within a chunk-anchor of the cap is named MAXBARS whatever the
    last call did. Chunks also overlap by exactly the bar they are anchored at, so the rows are
    deduplicated on time before anything counts them.
    """
    import numpy as np
    first = mt5.copy_rates_from_pos(sym, code, 0, min(cap, MAX_BARS_PER_CALL))
    if first is None or len(first) == 0:
        return None, f"no-data {mt5.last_error()}"
    chunks = [first]
    have = len(first)
    oldest = int(first[0]["time"])
    stop = "chunk-ceiling"
    for _ in range(MAX_CHUNKS - 1):
        if have >= cap:
            stop = "MAXBARS"
            break
        older = mt5.copy_rates_from(sym, code, datetime.fromtimestamp(oldest, UTC),
                                    min(cap - have, MAX_BARS_PER_CALL))
        if older is None or len(older) == 0:
            stop = "venue-end"
            break
        new_oldest = int(older[0]["time"])
        if new_oldest >= oldest:
            stop = "venue-end"             # no progress: the venue's history ends here
            break
        chunks.append(older)
        have += len(older)
        oldest = new_oldest
    rows = np.concatenate(chunks[::-1]) if len(chunks) > 1 else chunks[0]
    _, keep = np.unique(rows["time"], return_index=True)
    rows = rows[keep]
    if len(rows) >= cap - MAX_CHUNKS:
        stop = "MAXBARS"
    return rows, stop


def _read_existing(path: Path) -> Any:
    """The frame on disk, or None. Never raises: a torn or absent file means "nothing to keep"."""
    import pandas as pd
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception as exc:
        print(f"    {path.name}: unreadable ({type(exc).__name__}); leaving it alone", flush=True)
        return None
    if not isinstance(df.index, pd.DatetimeIndex) or df.empty:
        return None
    return df


def _file_rows(path: Path) -> int:
    """Row count from the parquet footer alone -- no column is read, no frame is built."""
    import pyarrow.parquet as pq
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)  # type: ignore[no-untyped-call]
    except Exception:
        return 0


def deepen_one(mt5: Any, sym: str, tf: str, *, dry_run: bool) -> dict[str, Any]:
    """Measure what the venue serves for one chart and PREPEND whatever the file is missing."""
    import pandas as pd

    code = getattr(mt5, f"TIMEFRAME_{tf}", None)
    if code is None:
        return {"status": "TIMEFRAME_UNKNOWN_TO_TERMINAL"}
    cap = int(getattr(mt5.terminal_info(), "maxbars", 100_000) or 100_000)
    path = UNIVERSE / f"{sym}_{tf}.parquet"

    # THE FREE SKIP, AND IT IS THE TWO EXPENSIVE CHARTS IT SKIPS. A chart already holding at
    # least `cap` bars cannot gain one: the cache serves the most recent `cap` bars, so a longer
    # file ending at the same place necessarily starts at or before the cache's oldest bar.
    # M1 and M5 hold ~100,000 rows on nearly every symbol and are precisely the two charts whose
    # first walk forces the terminal to rebuild a timeseries from its .hcc history -- the whole
    # cost of the first sweep. The footer answers without reading a single column.
    #
    # IT IS ALSO SELF-CORRECTING RATHER THAN PERMANENT: raise MaxBars and `cap` rises with it, so
    # the same file stops qualifying and is walked again on the next pass. A skip that could
    # outlive its reason would have quietly pinned the store at the cap it was written under.
    held = _file_rows(path)
    if held >= cap:
        return {"status": "AT_FLOOR", "file_rows": held, "cap": cap,
                "how": "file already holds >= TERMINAL_MAXBARS bars, so the cache cannot "
                       "serve an older one; no terminal call made",
                "measured_at": datetime.now(UTC).isoformat(timespec="seconds")}

    rows, stop = walk_back(mt5, sym, code, cap)
    if rows is None or len(rows) == 0:
        return {"status": "NO_DATA", "stop": stop}

    times = pd.to_datetime(rows["time"], unit="s", utc=True)
    served_first = times[0]
    frontier = dense_frontier(Counter(t.date() for t in times), tf)
    floor = (pd.Timestamp(frontier, tz="UTC") if frontier is not None
             else pd.Timestamp(served_first))
    out: dict[str, Any] = {
        "served": len(rows), "stop": stop,
        "venue_first": str(served_first)[:19], "venue_last": str(times[-1])[:19],
        "dense_first": str(floor)[:19],
        "dense_served": int((times >= floor).sum()),
        "bounded_by": "OURS (terminal MaxBars)" if stop == "MAXBARS" else "VENUE",
        "measured_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    existing = _read_existing(path)
    if existing is None:
        out["status"] = "NO_FILE"          # download_all_symbols owns first creation
        return out
    file_first = existing.index.min()
    out |= {"file_rows": len(existing), "file_first": str(file_first)[:19]}
    # TWO COMPLETELY DIFFERENT THINGS LIVE BEHIND THE FLOOR, AND ONE NAME FOR BOTH IS A LIE.
    #
    # A file may reach behind `floor` because its head is DAILY-DERIVED -- the venue's daily bars
    # rendered one per intraday bar, which EURUSD_H4 carries 5,973 of, 36% of that series.
    # Measured, reported, and NOT acted on here: trimming a series the judge has already read is
    # a separate decision from widening it, and this organ only ever adds.
    #
    # Or it may reach behind because the desk ARCHIVED bars the terminal's 100,000-bar chart
    # cache has since rolled past -- EURUSD_M1 holds 4,270 such rows. Those are the desk's own
    # store already outrunning the cache, which is the opposite of a defect, and prepend-only is
    # what keeps them. Naming that "daily-derived" would have reported the store's best property
    # as contamination. The two are told apart by whether a frontier was DETECTED at all.
    if file_first < floor:
        behind = int((existing.index < floor).sum())
        out["daily_derived_head_rows" if frontier is not None
            else "rows_behind_cache_window"] = behind

    want = times < file_first
    want &= times >= floor
    n_new = int(want.sum())
    if n_new == 0:
        out["status"] = "AT_FLOOR"
        return out
    out["would_prepend"] = n_new
    if dry_run:
        out["status"] = "DRY_RUN"
        return out

    # FROM THE STRUCTURED ARRAY, NOT A LIST OF ITS RECORDS. `pd.DataFrame(list_of_np_void)` builds
    # a frame with a RangeIndex and NO column names, so the very next line raised KeyError('time')
    # -- caught by `test_deepen_prepends_and_never_rewrites_a_bar_it_found`, which is why the
    # fake terminal in that test serves real MT5 record dtypes rather than tidy dicts.
    add = pd.DataFrame(rows[want])
    add["time"] = pd.to_datetime(add["time"], unit="s", utc=True)
    add = add.set_index("time").sort_index()
    missing = [c for c in existing.columns if c not in add.columns]
    if missing:
        out["status"] = f"COLUMNS_MISSING:{','.join(missing)}"
        return out
    add = add[list(existing.columns)].astype(existing.dtypes.to_dict())
    add.index.name = existing.index.name
    merged = pd.concat([add, existing])
    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
    if len(merged) < len(existing):
        out["status"] = "REFUSED_SHRINK"   # unreachable by construction; asserted anyway
        return out
    out["status"] = "DEEPENED" if publish_frame(merged, path) else "PUBLISH_BLOCKED"
    out["rows_after"] = len(merged)
    out["first_after"] = str(merged.index.min())[:19]
    return out


def _publish_json(path: Path, doc: dict[str, Any]) -> None:
    """Write a state file beside its destination and rename, so no reader sees half of one.

    The same rule `publish_frame` applies to the bar frames, for the same reason: these two are
    read by the next pass to decide what it may skip, and a truncated cursor would hand it a
    verdict that was never measured.
    """
    import os
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _fresh(entry: Any, hours: float) -> bool:
    """True when a cursor row was measured recently enough to trust its AT_FLOOR verdict."""
    if not isinstance(entry, dict) or entry.get("status") not in {"AT_FLOOR", "NO_FILE"}:
        return False
    try:
        at = datetime.fromisoformat(str(entry.get("measured_at")))
    except ValueError:
        return False
    return datetime.now(UTC) - at < timedelta(hours=hours)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="", help="comma list; default every file on disk")
    ap.add_argument("--timeframes", default=",".join(TIMEFRAMES))
    ap.add_argument("--budget-s", type=float, default=1500.0)
    ap.add_argument("--recheck-hours", type=float, default=20.0)
    ap.add_argument("--sleep-s", type=float, default=0.15, help="pause between symbols")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ignore-blackout", action="store_true")
    args = ap.parse_args(argv)

    started = time.monotonic()
    now = datetime.now(UTC)
    window = in_blackout(now)
    if window and not args.ignore_blackout:
        print(f"standing down: {now:%H:%M}Z is inside the {window} placement window")
        return 0

    import MetaTrader5 as mt5
    if mt5.terminal_info() is None and not mt5.initialize():
        print(f"initialize failed: {mt5.last_error()}")
        return 1
    ti = mt5.terminal_info()
    print(f"terminal: {ti.name} build {ti.build} | TERMINAL_MAXBARS={ti.maxbars}")

    tfs = [t.strip().upper() for t in args.timeframes.split(",") if t.strip()]
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = sorted({p.stem.rsplit("_", 1)[0] for p in UNIVERSE.glob("*.parquet")
                          if "_" in p.stem and p.stem.rsplit("_", 1)[1] in TF_MINUTES})
    cursor = _load(CURSOR)
    report = _load(REPORT)
    report["terminal_maxbars"] = int(ti.maxbars)
    report["measured_at"] = now.isoformat(timespec="seconds")
    rows: dict[str, Any] = report.setdefault("symbols", {})

    # WHAT IS MOST BEHIND GOES FIRST. A budget that expires part-way must not re-walk the same
    # alphabetical prefix every run -- that is the exact failure `_collection_order` was written
    # for in `expand_universe`, and a cursor without an ordering only records it.
    def behind(sym: str) -> tuple[int, str]:
        done = sum(1 for tf in tfs if _fresh((cursor.get(sym) or {}).get(tf),
                                             args.recheck_hours))
        return (done, sym)

    symbols.sort(key=behind)
    print(f"{len(symbols)} symbol(s) x {len(tfs)} chart(s); budget {args.budget_s:.0f}s"
          + (" [DRY RUN]" if args.dry_run else ""))

    added = 0
    touched = 0
    stood_down = ""
    for sym in symbols:
        if time.monotonic() - started > args.budget_s:
            stood_down = "budget"
            break
        w = in_blackout(datetime.now(UTC))
        if w and not args.ignore_blackout:
            stood_down = f"blackout {w}"
            break
        sym_cur = cursor.setdefault(sym, {})
        sym_row = rows.setdefault(sym, {})
        did = []
        for tf in tfs:
            if _fresh(sym_cur.get(tf), args.recheck_hours):
                continue
            res = deepen_one(mt5, sym, tf, dry_run=args.dry_run)
            sym_cur[tf] = res
            sym_row[tf] = res
            status = res.get("status")
            if status in {"DEEPENED", "DRY_RUN"}:
                # A DRY RUN HAS NO `rows_after`, so subtracting `file_rows` from a missing key
                # reported EVERY chart as a large NEGATIVE gain -- "-311,067 bar(s) added" on the
                # first pass, which is the sort of summary line nobody reads twice and everybody
                # believes. The published count is the one the run can actually cash.
                n = (int(res["rows_after"]) - int(res["file_rows"]) if status == "DEEPENED"
                     else int(res.get("would_prepend", 0)))
                added += n
                did.append(f"{tf}+{n:,}")
        if did:
            touched += 1
            print(f"  {sym:14s} {' '.join(did)}", flush=True)
        # CHECKPOINT, BECAUSE A CURSOR WRITTEN ONLY AT THE END IS NOT A CURSOR. A run killed by
        # the task scheduler's time limit, a reboot or a Ctrl-C would otherwise lose every
        # verdict it had measured and re-walk the whole store from the terminal next time -- the
        # bars are already safe on disk, but the measurement that says so is what makes the next
        # pass cheap. Both files are published atomically, so a kill mid-checkpoint leaves the
        # previous cursor whole rather than a truncated one.
        #
        # EVERY FIVE, NOT EVERY TWENTY, because the first sweep is exactly when a kill is likely
        # and exactly when the verdicts are most expensive to re-earn: measured on the box, the
        # first pass was terminated by its 30-minute limit having deepened 18 symbols, two short
        # of a checkpoint, and lost all 18 verdicts. The write is a few kilobytes of JSON.
        if touched and touched % 5 == 0:
            _publish_json(CURSOR, cursor)
            _publish_json(REPORT, report)

    report["stood_down"] = stood_down
    report["note"] = ("`bounded_by` OURS means the terminal's chart cache (common.ini [Charts] "
                      "MaxBars) refused more, not the broker. `dense_first` is where the chart "
                      "reaches its own recent density; everything older is the venue's daily "
                      "bars rendered one per day on an intraday chart, and is never taken.")
    _publish_json(CURSOR, cursor)
    _publish_json(REPORT, report)
    print(f"\n{touched} symbol(s) deepened, {added:,} bar(s) added"
          + (f"; stood down on {stood_down}" if stood_down else "; swept the whole store")
          + f" -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
