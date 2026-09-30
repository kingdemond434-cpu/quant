"""Keep the judge's docket WARM, continuously, in the order that most likely produces a verdict.

WHY THIS EXISTS

The gauntlet's memory cost is not a function of how many cells it judges -- it is a function of
how many it must COMPUTE. A cached cell is carried as `{"df": None, "sigs": None}` plus two short
daily series; an uncached one holds a full frame reference and its entire signal list, and some
families emit ~28,000 signals for a single symbol.

THE LOSS THIS FILE NOW ATTACKS, MEASURED 2026-09-24 ON THE TRADING BOX

A sweep writes verdicts only at the END of its build. Its clock fires every five minutes with
fifteen workers and that changes nothing, because the build is the bottleneck: the sweep's own
pre-warm and its build loop share ONE deadline, so when the docket outgrows the budget the warm
consumes the whole of it and the gate phase judges only what was already cached. Four consecutive
sweeps in `logs/MT5-Gauntlet.log`:

    PRE-WARM: 15 worker(s) warmed 29113 cell(s) in 4008s (23775 already cached, 73758 failed ...)
    PRE-WARM: 15 worker(s) warmed   439 cell(s) in 1205s (52451 already cached, 73756 failed ...)
    PRE-WARM: 15 worker(s) warmed     0 cell(s) in 1108s (52890 already cached, 73756 failed ...)
    PRE-WARM: 15 worker(s) warmed     0 cell(s) in 1195s (52890 already cached, 73756 failed ...)

Eighteen minutes of a forty-five minute budget, twice, WARMING NOTHING: 52,890 cells re-checked
through a worker round-trip only to answer HIT, and 73,756 cells re-attempted only to fail the
same build they failed on the previous pass. That is the single largest remaining throughput loss
and it is entirely outside the judge -- it is about what the judge is FED and how WARM it is.

So this job, which runs BETWEEN sweeps and can spend as long as it likes, now does the expensive
part: it resolves cells that are already warm WITHOUT a worker (one directory scan, one cache-key
computation in the parent), it defers cells whose build has failed instead of re-failing them
every pass, and it warms the rest in the order most likely to produce a verdict.

WHAT CHANGED, AND WHY EACH CHANGE IS A CORRECTION RATHER THAN A PREFERENCE

1.  WORKERS CAME FROM `WARM_WORKERS=2`, A NUMBER SIZED FOR A DIFFERENT MACHINE. Its own comment
    says so: "The desk box has 4 cores and the sweep uses 0.84 of one", and then "TWO, not three
    ... three workers held 12.9GB of COMMIT ... and exhausted a 12,756MB page file". Both
    measurements are real and both are about a 4-core, 8GB box with a 12.7GB page file. The
    machine running the judge today has 18 cores and 96GB, and `external_gauntlet` already runs
    FIFTEEN workers of the identical `_warm_one` on it every sweep. Measured on the 2-worker
    warmer the same day: 57 cells/min against a 552,194-cell eligible list -- 6.7 DAYS for one
    pass, on a docket whose cache keys roll over with the data day.
    The count is now `external_gauntlet.WORKERS`: the judge's own arithmetic, derived on the box
    the code is running on, so there is ONE builder of this number and a small box still
    collapses to the small number it always had. `WARM_WORKERS` still overrides both.

2.  IT WARMED THE WRONG KEY FOR EVERY NON-H1 CELL. It called `_h1_for(sym)` for the data day and
    `_cache_key(sym, family, params, day)` with no timeframe. `_cache_key` resolves the missing
    timeframe correctly through `timeframe_of`, so the DIGEST was right -- but the `last_day` fed
    into it came from the symbol's H1 frame rather than the cell's own chart. An M15 frame that
    ends on a different day than H1 therefore got warmed under a key the sweep never looks up:
    the cell was built, the series were correct, and the sweep rebuilt it anyway. Intraday cells
    sort FIRST in the sweep's order (`_tf_rank`), so this was wasted on the highest-priority half
    of the docket. Now `_bars_for(sym, tf)`, exactly as `_warm_one` does.

3.  ITS ELIGIBLE SET WAS WIDER THAN THE SWEEP'S. `partition_at_economic_prior(specs)` was called
    without `meta`, so the tradeability limb never ran and it spent build budget on cells the
    sweep sets aside at gate 0. And its de-duplication omitted the row-level `timeframe` fold
    that `main` performs, so one docket row could collapse into the wrong cell. Both now mirror
    `main`.

4.  ORDER WAS `REVERSE = True` -- the docket backwards, so the warmer and the sweep "meet in the
    middle". That was a sensible answer to a 6,270-cell docket. Against 552,194 cells neither end
    matters: what matters is WHICH cells, and the answer comes from `research.cell_priority`,
    which ranks by the measured rate at which a family and chart reach a certificate or the
    forward-cure route, and breaks near-ties toward ground the desk has judged least. That module
    ORDERS and never rejects; every cell stays in the queue.

WHAT IT DELIBERATELY DOES NOT DO

No gates, no verdicts, no report, no trial charge, and it never touches UNIVERSAL_SURVIVORS.json.
It is a COMPUTE cache and nothing else, which is why it is safe to run beside the sweep: nothing
it writes can change a verdict, only how long that verdict takes to reach. Every function it calls
to build a series is imported from `external_gauntlet` rather than reimplemented, so a change to
how a series is built cannot silently drift from what this warms.

AND NOTHING HERE IS A CAP. The deferral ledger does not REFUSE a cell -- it records that this
cell's build failed, publishes how long it has been failing, and retries it the moment its bars
change or `RETRY_SEC` elapses, whichever comes first. A cell is never dropped; it is scheduled.
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DESK = BASE / "desks" / "mt5"
sys.path.insert(0, str(DESK))
sys.path.insert(0, str(DESK / "research"))
sys.path.insert(0, str(DESK / "scripts"))

#: Stop warming below this much free memory. Higher than the sweep's own admission floor on
#: purpose: this job is entirely optional, so it should yield the box long before anything that
#: produces verdicts has to. Measured against the BINDING constraint (min of physical and commit)
#: rather than physical alone -- which read 2,705MB free on a box with 234MB of usable virtual
#: memory. This is a YIELD, never a cap on the judge: the sweep's own budget is untouched.
FLOOR_MB = int(os.environ.get("WARM_FLOOR_MB", "2500"))

#: Report progress this often. Cheap, and it makes the log a live progress signal rather than a
#: single line at exit -- the blind spot that cost 87 minutes on 2026-08-28.
REPORT_EVERY = 250

#: How long one invocation runs before returning, so the hourly trigger can never overlap itself
#: and a docket that grew this hour is picked up at the start of the next round rather than at
#: the end of a multi-day walk. Inside this budget the job LOOPS: finish a round, re-read the
#: docket, go again. That is what makes the docket warm CONTINUOUSLY rather than once a week.
BUDGET_SEC = float(os.environ.get("WARM_BUDGET_SEC", "3300"))

#: How long a cell whose build FAILED waits before it is tried again, when its bars have not
#: changed in the meantime. Changed bars retry it immediately regardless -- a missing parquet
#: that arrives is exactly the event that makes the build succeed, and waiting out a timer after
#: it lands would be the queue this desk forbids.
RETRY_SEC = float(os.environ.get("WARM_RETRY_SEC", str(6 * 3600)))

#: Where the deferral ages are published. Nothing is queued invisibly (LAWS): a cell this pass
#: does not send is named here with the age of its first failure.
DEFERRALS = DESK / "data" / "hypotheses" / "warm_deferrals.json"
#: Cached `last_day` per (symbol, chart), keyed by the parquet's own (mtime_ns, size) so a pass
#: re-reads only the frames that actually changed.
LASTDAY = DESK / "data" / "hypotheses" / "warm_last_day.json"
REPORT = DESK / "reports" / "WARM_GAUNTLET.json"


#: The count this file shipped with for a year, and the one it may never fall below. Two workers
#: was measured safe on a FOUR-core, 8GB box with a 12,756MB page file; any box that can run this
#: job at all can run two, so a momentary memory reading can slow the warmer down and can never
#: stop it dead. Without this floor the derivation below is a single point of failure.
HISTORIC_FLOOR = 2

#: THIS JOB'S OWN declared memory need, per worker -- the same 900MB it is admitted on at the
#: foot of this file. One cell plus the bounded frame cache, released on return.
NEED_MB = float(os.environ.get("WARM_NEED_MB", "900"))


def _workers() -> int:
    """The judge's own arithmetic, RE-MEASURED at the start of each round.

    ONE BUILDER FOR THIS NUMBER, and it is `external_gauntlet`: the cores this box has, the cores
    the live terminal is owed (`SESSION_RESERVED_CORES`), the weekend maximum, its measured memory
    budget and its per-worker figure. Every input below is read from that module; none is invented
    here. What this does NOT inherit is the judge's TIMING.

    WHY THE TIMING MATTERS, MEASURED 2026-09-24. `external_gauntlet.WORKERS` is evaluated once, at
    module import, from `MEMORY_BUDGET_MB`, which is itself evaluated once at import from
    `free_mb()` -- the MINIMUM of free physical memory and free COMMIT. On a box shared with a
    dozen other research processes that reading swings hard: measured minutes apart, `free_mb()`
    read 46,785MB (budget 11,520MB, fifteen workers) and, at the instant this job happened to
    start, low enough that the budget fell to its 1,200MB declaration -- 1200 // 768 == ONE
    worker, pinned for the whole life of a process that then ran for hours on an eighteen-core
    box. The log line reads `1 worker(s)` and nothing about it looks like a fault.

    So the CORE bound is the judge's, re-read each round, and the MEMORY bound is this job's own
    `NEED_MB` rather than the sweep's `PER_WORKER_MB`. That is not a second builder: they are
    bounds on two different shapes, and the sweep's own comment says its 768 is "headroom over
    that shape, not a measured peak". A sweep worker lives inside a process that also holds the
    whole docket's verdicts; a warm worker holds ONE cell and releases it on return, and this
    job's declared admission need is the 900MB already written into `exclusive_job` at the foot
    of this file. Using the sweep's figure here made the warmer inherit a bound that is not about
    it, and on a crowded box that bound reads ONE.

    Memory safety does not rest on this estimate. `FLOOR_MB` is checked against live free memory
    every `REPORT_EVERY` cells DURING the round and stands the whole job down when the box gets
    tight -- a measurement, not a guess, and the reason a generous start is safe.
    """
    override = os.environ.get("WARM_WORKERS")
    if override:
        return max(1, int(float(override)))
    try:
        import external_gauntlet as G
        from research.job_lock import free_mb
        cores = os.cpu_count() or 1
        by_cores = cores if G.market_closed() else cores - G.SESSION_RESERVED_CORES
        free = free_mb()
        by_mem = int(free // NEED_MB) if free else by_cores
        return max(HISTORIC_FLOOR, min(by_cores, by_mem))
    except Exception:
        # An unreadable judge leaves the historic figure, never unlimited and never zero.
        return HISTORIC_FLOOR


#: Set once per worker process by `_init`, so the universe registry is not pickled per cell.
_META: dict | None = None


def _init(meta: dict) -> None:
    global _META
    _META = meta


def _warm_one(spec: dict) -> tuple[str, str]:
    """Compute and cache ONE cell's 1x and 3x daily series. Returns a one-word outcome.

    Runs in a worker process, so it must be importable at module level (Windows spawns rather
    than forks). Every function it calls comes from `external_gauntlet`, so the series it writes
    are the ones the sweep would have computed itself -- same identity, same key, same trim.

    The parent has already resolved this cell's chart, its data day and its cache key and has
    already established that the key is NOT on disk, so this function no longer spends a process
    round-trip answering "already cached".
    """
    import external_gauntlet as G

    meta = _META or {}
    obj = None
    ckey = str(spec.get("ckey") or "")
    try:
        tf = str(spec.get("tf") or "H1")
        frame = G._bars_for(spec["sym"], tf)
        if frame is None or len(frame) == 0:
            return ckey, "missing"
        obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if not obj:
            return ckey, "failed"
        last_day = frame.index[-1].normalize()
        ds1 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
        costs3 = G.costs_for(spec["sym"], meta, mult=G.COST_SCENARIO)
        ds3 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], costs3), last_day)
        if ds1 is None or ds3 is None:
            return ckey, "failed"
        G.cache_save(ckey, ds1, ds3)
        return ckey, "warmed"
    except Exception:
        return ckey, "failed"
    finally:
        if obj is not None:
            obj["sigs"] = None
            obj["df"] = None


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def _write_json(path: Path, doc) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:
        print(f"  {path.name} NOT written ({type(exc).__name__}: {exc})")


def docket_specs(G, meta: dict) -> list[dict]:
    """The sweep's own cells, derived the sweep's own way.

    De-duplication, the row-level `timeframe` fold and the economic-prior partition all mirror
    `external_gauntlet.main` exactly, INCLUDING `meta` -- without it the tradeability limb never
    runs and this job warms cells the sweep sets aside at gate 0.
    """
    surv_file = G.HYP / "external_survivors.json"
    if not surv_file.exists():
        return []
    survivors = _read_json(surv_file, [])
    if not isinstance(survivors, list):
        return []
    cells: dict[str, dict] = {}
    for h in survivors:
        if not isinstance(h, dict):
            continue
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        params = dict(h.get("params") or {})
        # THE ROW-LEVEL TIMEFRAME FOLD, as `main` does it: a row that names its chart outside
        # params must not collapse into the H1 cell of the same name.
        row_tf = str(h.get("timeframe") or "").upper()
        if row_tf and row_tf != "H1" and not params.get("timeframe"):
            params["timeframe"] = row_tf
        key = f"{sym}.{fam}.{json.dumps(params, sort_keys=True)}"
        cells.setdefault(key, {"sym": sym, "family": fam, "params": params,
                               "mechanism_status": h.get("mechanism_status"),
                               "mechanism_note": h.get("mechanism_note")})
    eligible, rejected = G.partition_at_economic_prior(list(cells.values()), meta)
    print(f"docket {len(survivors)} rows -> {len(cells)} cells -> {len(eligible)} eligible "
          f"({len(rejected)} rejected at the economic prior, as the sweep would)")
    for sp in eligible:
        sp["tf"] = G.timeframe_of(sp.get("params"), str(sp.get("family") or ""))
    return list(eligible)


def resolve_keys(G, specs: list[dict]) -> tuple[list[dict], dict[str, str], int]:
    """Stamp each spec with its cache key, IN THE PARENT.

    This is the whole point of the rewrite. The data day is a property of a (symbol, chart) pair,
    not of a cell, so 552,194 cells need at most a few hundred frame reads to key -- against the
    552,194 worker round-trips the previous shape spent, 52,890 of which answered HIT and were
    thrown away. The answers are cached against each parquet's own (mtime_ns, size), so a pass
    that follows a pass re-reads only the charts that actually moved.

    Returns (specs that could be keyed, {sym|tf: parquet stamp}, count that had no bars).
    """
    cached = _read_json(LASTDAY, {})
    if not isinstance(cached, dict):
        cached = {}
    stamps: dict[str, str] = {}
    out: list[dict] = []
    no_bars = 0
    for sp in specs:
        sym, tf = str(sp.get("sym") or ""), str(sp.get("tf") or "H1")
        bk = f"{sym}|{tf}"
        if bk not in stamps:
            pq = G.UNI / f"{sym}_{tf}.parquet"
            try:
                st = pq.stat()
                stamp = f"{st.st_mtime_ns}:{st.st_size}"
            except OSError:
                stamp = ""
            stamps[bk] = stamp
            if stamp and cached.get(bk, {}).get("stamp") != stamp:
                frame = G._bars_for(sym, tf)
                day = (str(frame.index[-1].normalize().date())
                       if frame is not None and len(frame) else "")
                cached[bk] = {"stamp": stamp, "day": day}
        row = cached.get(bk) or {}
        day = str(row.get("day") or "") if stamps[bk] else ""
        if not day:
            no_bars += 1
            continue
        sp["day"] = day
        sp["ckey"] = G._cache_key(sp["sym"], sp["family"], sp["params"] or {}, day, sp["tf"])
        out.append(sp)
    _write_json(LASTDAY, cached)
    # The frames were read for ONE timestamp each; holding them costs memory the pool needs.
    with contextlib.suppress(Exception):
        G._FRAME_CACHE.clear()
    return out, stamps, no_bars


def on_disk_keys(G) -> set[str]:
    """Every cache key already on disk, from ONE directory scan.

    404,055 entries scan in under a second, against 0.13 worker-seconds each to answer the same
    question through a process boundary.
    """
    keys: set[str] = set()
    try:
        with os.scandir(G.CACHE_DIR) as it:
            for e in it:
                if e.name.endswith(".npz"):
                    keys.add(e.name[:-4])
    except OSError:
        pass
    return keys


def split_deferred(specs: list[dict], stamps: dict[str, str],
                   now: float) -> tuple[list[dict], list[dict], dict]:
    """Separate cells whose build is KNOWN to fail from cells worth sending.

    NOTHING IS DROPPED AND NOTHING IS QUEUED INVISIBLY. A deferred cell is retried the moment its
    bars change -- a missing parquet arriving is exactly the event that makes its build succeed --
    and otherwise after `RETRY_SEC`. Its first-failure time is published in
    `data/hypotheses/warm_deferrals.json`, so its age is a number anyone can read rather than a
    silence. `due` cells go at the FRONT of the round: they are the oldest unresolved work.
    """
    led = _read_json(DEFERRALS, {})
    rows = led.get("rows") if isinstance(led, dict) else None
    if not isinstance(rows, dict):
        rows = {}
    due: list[dict] = []
    send: list[dict] = []
    held: list[dict] = []
    for sp in specs:
        rec = rows.get(str(sp.get("ckey") or ""))
        if not isinstance(rec, dict):
            send.append(sp)
            continue
        bk = f"{sp.get('sym')}|{sp.get('tf')}"
        bars_moved = str(rec.get("bars") or "") != stamps.get(bk, "")
        aged_out = (now - float(rec.get("last_failed_at") or 0.0)) >= RETRY_SEC
        if bars_moved or aged_out:
            sp["_retry_of"] = rec
            due.append(sp)
        else:
            held.append(sp)
    return due + send, held, rows


def publish_deferrals(rows: dict, held: list[dict], now: float, extra: dict) -> dict:
    """Write the deferral ledger and return its census, ages included."""
    ages = sorted(((now - float(r.get("first_failed_at") or now)) / 3600.0)
                  for r in rows.values() if isinstance(r, dict))
    census = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "n_deferred": len(rows),
        "n_held_this_pass": len(held),
        "oldest_hours": round(ages[-1], 2) if ages else 0.0,
        "median_hours": round(ages[len(ages) // 2], 2) if ages else 0.0,
        "rule": ("NOTHING IS DROPPED. A cell lands here only when its BUILD failed; it is retried "
                 "the moment its bars change, and in any case after WARM_RETRY_SEC. Retries go "
                 "FIRST in the next round."),
        "retry_sec": RETRY_SEC,
    }
    census.update(extra)
    _write_json(DEFERRALS, {**census, "rows": rows})
    return census


def run_round(G, meta: dict, priors, deadline: float) -> dict:
    """One full pass over the docket. Returns the round's census."""
    from research.job_lock import free_mb

    t0 = time.time()
    specs = docket_specs(G, meta)
    if not specs:
        return {"eligible": 0, "note": "no docket to warm"}

    try:
        import cell_priority as CP
        specs = CP.order(specs, priors)
        ordered_by = "cell_priority"
    except Exception as exc:
        ordered_by = f"UNORDERED ({type(exc).__name__}: {exc})"
        print(f"  cell priority unavailable ({exc}); warming in docket order")
    print(f"  order: {ordered_by}")

    keyed, stamps, no_bars = resolve_keys(G, specs)
    warm = on_disk_keys(G)
    cold = [sp for sp in keyed if sp["ckey"] not in warm]
    n_warm_already = len(keyed) - len(cold)
    share = (n_warm_already / len(keyed)) if keyed else 0.0
    print(f"  keyed {len(keyed)} of {len(specs)} cell(s) ({no_bars} with no bars on their own "
          f"chart); {n_warm_already} already warm ({share:.1%}), {len(cold)} cold")

    now = time.time()
    order_, held, rows = split_deferred(cold, stamps, now)
    if held:
        print(f"  deferred: {len(held)} cell(s) held this round (build failed before, bars "
              f"unchanged, retry in under {RETRY_SEC / 3600:.0f}h) -- ages in "
              f"{DEFERRALS.name}, none dropped")

    counts = {"warmed": 0, "missing": 0, "failed": 0}
    stopped = ""
    workers = _workers()
    print(f"  {workers} worker(s) on {len(order_)} cold cell(s)")
    if order_:
        by_key = {str(sp.get("ckey") or ""): sp for sp in order_}
        with Pool(processes=max(1, workers), initializer=_init, initargs=(meta,)) as pool:
            # UNORDERED, and the key comes back WITH the outcome. `imap` would have yielded in
            # submission order, so one pathological cell stalls the result stream -- and with it
            # both the deadline check and the memory check, which is the shape of stall this
            # desk has already paid for twice (a process burning CPU while every liveness check
            # reports it healthy). The workers were never the thing that had to be ordered.
            it = pool.imap_unordered(_warm_one, order_, chunksize=1)
            for i, (ck, outcome) in enumerate(it, 1):
                counts[outcome] = counts.get(outcome, 0) + 1
                sp = by_key.get(ck) or {}
                if outcome == "warmed":
                    rows.pop(ck, None)
                elif ck:
                    prev = rows.get(ck) if isinstance(rows.get(ck), dict) else {}
                    rows[ck] = {
                        "first_failed_at": prev.get("first_failed_at", now),
                        "last_failed_at": time.time(),
                        "n_failures": int(prev.get("n_failures") or 0) + 1,
                        "bars": stamps.get(f"{sp.get('sym')}|{sp.get('tf')}", ""),
                        "sym": sp.get("sym"), "family": sp.get("family"), "tf": sp.get("tf"),
                        "why": outcome,
                    }
                # THE DEADLINE IS CHECKED EVERY RESULT, not every REPORT_EVERY. `time.time()` is
                # free next to a cell build, and a budget that is only consulted once every 250
                # cells is not a budget on a pass that slows down.
                if time.time() > deadline:
                    stopped = "run budget spent; the next invocation resumes from the cache"
                    pool.terminate()
                    break
                if i % REPORT_EVERY:
                    continue
                avail = free_mb()
                if avail is not None and avail < FLOOR_MB:
                    stopped = (f"{avail}MB free, floor {FLOOR_MB}MB -- warming is optional work "
                               f"and yields the box; progress is cached and resumable")
                    pool.terminate()
                    break
                rate = i / max(1e-9, time.time() - t0) * 60.0
                print(f"  [{i}/{len(order_)}] warmed={counts['warmed']} "
                      f"failed={counts['failed']} missing={counts['missing']} "
                      f"{time.time() - t0:.0f}s {rate:.0f} cells/min free={avail}MB",
                      flush=True)
    if stopped:
        print(f"  STOPPED: {stopped}")

    census = publish_deferrals(rows, held, time.time(), {"held_sample": [
        {"sym": sp.get("sym"), "family": sp.get("family"), "tf": sp.get("tf")}
        for sp in held[:50]]})
    return {
        "eligible": len(specs), "keyed": len(keyed), "no_bars": no_bars,
        "warm_before": n_warm_already, "warm_share_before": round(share, 4),
        "cold": len(cold), "sent": len(order_), "held": len(held),
        "warmed": counts["warmed"], "failed": counts["failed"], "missing": counts["missing"],
        "seconds": round(time.time() - t0, 1),
        "cells_per_min": round(sum(counts.values()) / max(1e-9, time.time() - t0) * 60.0, 1),
        "workers": workers, "ordered_by": ordered_by, "stopped": stopped,
        "deferral_census": {k: v for k, v in census.items() if k != "held_sample"},
    }


def main() -> int:
    import external_gauntlet as G

    meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    try:
        import cell_priority as CP
        priors = CP.measure_priors(BASE)
        print(f"  priors: {priors.n_judged} judged, {priors.n_cured} on the forward-cure route, "
              f"{priors.n_passed} ten-gate pass(es); sources {priors.sources}")
    except Exception as exc:
        print(f"  priors UNMEASURED ({type(exc).__name__}: {exc})")
        priors = None

    deadline = time.time() + BUDGET_SEC
    rounds: list[dict] = []
    while time.time() < deadline:
        r = run_round(G, meta, priors, deadline)
        rounds.append(r)
        if not r.get("eligible"):
            break
        # A round that warmed nothing and held nothing new has converged: the docket is warm to
        # the extent this box can make it, so sleep the rest of the budget out rather than
        # re-scanning a quarter of a million keys in a tight loop.
        if not r.get("sent"):
            print("  round sent nothing -- the docket is as warm as its bars allow")
            break
    last = rounds[-1] if rounds else {}
    try:
        import cell_priority as CP
        if priors is not None:
            CP.publish([], [], priors, BASE, extra={"consumer": "warm_gauntlet_cache",
                                                    "last_round": last})
    except Exception:
        pass
    _write_json(REPORT, {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "budget_sec": BUDGET_SEC, "rounds": rounds,
        "note": ("Warmth is what decides which cells a bounded sweep can reach: an uncached cell "
                 "costs the sweep ~22s of its build budget and a cached one costs it nothing. "
                 "This job holds no authority over any verdict."),
    })
    if last:
        print(f"warmed {last.get('warmed')} cell(s) in {last.get('seconds')}s at "
              f"{last.get('cells_per_min')} cells/min with {last.get('workers')} worker(s); "
              f"docket was {last.get('warm_share_before', 0):.1%} warm at the start of the round")
    return 0


def _cli_main() -> int:
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:
        from job_lock import exclusive_job

    # Modest: cells are released as they are warmed, so the working set is one cell plus the
    # bounded frame cache -- not the whole docket.
    with exclusive_job("warm_gauntlet_cache", need_mb=900) as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
