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

5.  (2026-09-30) THE SAME DOCKET, THE SAME ORDER, THE BOX'S REAL FREE CORES. The judge rules on
    every CACHED cell of the docket it computes each sweep (ban set-aside, its eight-key sort,
    the novelty head, `allocate_by_yield`'s family trim) -- so a warmed cell outside that docket
    is a build nobody reads. `research/judge_docket_order.py` restates that docket from the
    sealed module's own helpers (drift-tested against the sealed source) and this job warms
    exactly it, NEVER-JUDGED FIRST: the sealed pre-warm walks the trimmed docket family by
    family, so it builds family A's re-judges before family B's first rulings; the warmer builds
    every family's backlog first and the sweep then finds those as hits.
    Workers are sized from psutil-measured idle cores and free memory, re-measured every
    `CAPACITY_EVERY_SEC` DURING a round (the sweep's gate phase is single-threaded and leaves most
    of the box idle for as long as it runs), and they run at IDLE priority so no miner, the
    terminal, the gateway or the judge's own pool ever loses a cycle to them. `WARM_WORKERS` is
    now a floor: the value `judging_throughput` used to publish machine-wide pinned this job to
    ONE worker. Cells are handed out in (symbol, chart) batches so the sealed builder's
    per-process frame and external-universe memos hit. `gate_room` stops warming at the number of
    cached cells the judge's last sweep says it can rule inside its task limit: a sweep killed at
    its limit publishes nothing.

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


#: The share of MEASURED free memory the warmer's pool may be sized into. Half, the same share the
#: sealed sweep takes of what it finds free (`HEADROOM_SHARE`): the other half stays for whoever is
#: admitted next, and `FLOOR_MB` still stands the whole job down mid-round if the box gets tight.
MEM_SHARE = float(os.environ.get("WARM_MEM_SHARE", "0.5"))

#: Cores the warmer leaves idle on top of what everything else was MEASURED to use. One, because a
#: one-second CPU sample can miss a burst; the workers also run at IDLE priority (see `_init`), so
#: even inside that margin any normal-priority process -- a miner, the terminal, the gateway, the
#: sealed judge's own workers -- preempts a warm worker outright. The warmer can only ever spend
#: cycles nothing else wanted.
RESERVE_CORES = float(os.environ.get("WARM_RESERVE_CORES", "1"))

#: How often, in seconds, the in-flight target is re-measured DURING a round. The box's free cores
#: move by the minute (the sealed sweep's pool builds for hours and then rules single-threaded for
#: its gate phase, leaving most cores idle), so a pool sized once per round is sized for a moment
#: that has passed.
CAPACITY_EVERY_SEC = float(os.environ.get("WARM_CAPACITY_EVERY_SEC", "15"))

#: Cells of one (symbol, chart) handed to ONE worker as one task. The sealed builder memoises its
#: frame (`_FRAME_CACHE`) and the external-feature universe (`edge_search.resolve_inputs`, two
#: entries deep) PER PROCESS, and the sealed file measured what interleaving costs: 14,060
#: `discovered` ext_ cells on 137 symbols rebuilt the same universe 13,923 redundant times when
#: their cells were not consecutive. A batch keeps a symbol's cells on one worker, so each worker
#: pays for a symbol's frame and universe once per batch instead of once per cell.
BATCH_CELLS = max(1, int(os.environ.get("WARM_BATCH_CELLS", "8")))
#: Cells looked ahead when grouping a batch -- a short window, so the judge's order is kept to
#: within a few hundred cells and nothing is moved across the backlog/re-judge boundary.
BATCH_WINDOW = 256


def _cpu_idle_cores(sample_s: float = 1.0) -> float | None:
    """Cores idle across the WHOLE box over `sample_s`, from psutil. None when unmeasurable."""
    try:
        import psutil
        pct = float(psutil.cpu_percent(interval=max(0.1, sample_s)))
    except Exception:
        return None
    cores = os.cpu_count() or 1
    return max(0.0, cores * (100.0 - pct) / 100.0)


def measure_capacity(sample_s: float = 1.0) -> dict:
    """THE BOX'S FREE CORES AND FREE MEMORY, measured with psutil on the machine this runs on.

    Returns `pool` (processes to start: the memory bound, never above cores - 1) and `inflight`
    (cells to keep building right now: the cores measured idle, less `RESERVE_CORES`). Both are
    floored at `HISTORIC_FLOOR` -- with IDLE-priority workers a floor of two costs nobody a cycle.

    `WARM_WORKERS` is a FLOOR, never a cap (2026-09-30). `research/judging_throughput.py` used to
    publish it machine-wide as `min(4, by_cores - judge_workers)`, which on the 18-core box read
    ONE whenever the judge held its fifteen: every warm round then ran one worker however idle the
    box was, including the whole of each sweep's single-threaded gate phase. A stale machine value
    can therefore no longer pin the warmer low; an operator who wants fewer sets `WARM_WORKERS_MAX`.
    """
    cores = os.cpu_count() or 1
    free: float | None
    try:
        from research.job_lock import free_mb
        free = free_mb()
    except Exception:
        free = None
    if free is None:
        try:
            import psutil
            free = float(psutil.virtual_memory().available) / 1048576.0
        except Exception:
            free = None
    by_mem = int((MEM_SHARE * float(free)) // NEED_MB) if free else HISTORIC_FLOOR
    pool = max(HISTORIC_FLOOR, min(max(1, cores - 1), by_mem))
    idle = _cpu_idle_cores(sample_s)
    inflight = (pool if idle is None
                else max(HISTORIC_FLOOR, min(pool, int(idle - RESERVE_CORES))))
    floor_env = os.environ.get("WARM_WORKERS")
    if floor_env:
        with contextlib.suppress(ValueError):
            want = max(1, int(float(floor_env)))
            pool, inflight = max(pool, want), max(inflight, want)
    cap_env = os.environ.get("WARM_WORKERS_MAX")
    if cap_env:
        with contextlib.suppress(ValueError):
            cap = max(1, int(float(cap_env)))
            pool, inflight = min(pool, cap), min(inflight, cap)
    return {"cores": cores, "free_mb": None if free is None else round(float(free)),
            "idle_cores": None if idle is None else round(idle, 2),
            "by_mem": by_mem, "pool": int(pool), "inflight": int(min(inflight, pool)),
            "basis": "psutil" if idle is not None else "UNMEASURED cpu: pool size, memory-bound"}


def _workers() -> int:
    """The pool size this box can hold right now (kept by name for callers and tests)."""
    return int(measure_capacity(sample_s=0.2)["pool"])


def retarget(running: int, pool: int, idle: float | None) -> int:
    """In-flight cells for the next interval: what is running now plus what is measured idle.

    Our own running workers sit in the measured BUSY share, so the target is
    `running + idle - reserve`, clamped to [HISTORIC_FLOOR, pool]. Unmeasured idle keeps the
    current count: never a jump on a number nobody read.
    """
    if idle is None:
        return max(HISTORIC_FLOOR, min(pool, running or HISTORIC_FLOOR))
    return max(HISTORIC_FLOOR, min(pool, int(running + idle - RESERVE_CORES)))


#: Set once per worker process by `_init`, so the universe registry is not pickled per cell.
_META: dict | None = None


def _lower_priority() -> str:
    """Run this process at IDLE priority: it may only take CPU nothing else wants.

    THE RULE THIS ENFORCES: never reduce a miner's throughput. Windows `IDLE_PRIORITY_CLASS`
    (POSIX nice 19) means every normal-priority process -- miners, the live terminal, the gateway,
    the sealed judge and its pool -- preempts a warm worker outright. Best effort; the outcome is
    returned so a box where it failed says so.
    """
    try:
        import psutil
        p = psutil.Process()
        if sys.platform == "win32":
            p.nice(psutil.IDLE_PRIORITY_CLASS)
        else:
            p.nice(19)
        return "idle"
    except Exception as exc:
        try:
            os.nice(19)  # type: ignore[attr-defined,unused-ignore]
            return "nice19"
        except Exception:
            return f"UNCHANGED ({type(exc).__name__})"


def _init(meta: dict) -> None:
    global _META
    _META = meta
    _lower_priority()


def _warm_one(spec: dict) -> tuple[str, str]:
    """Compute and cache ONE cell's 1x and 3x daily series. Returns (cache key, outcome).

    Runs in a worker process, so it must be importable at module level (Windows spawns rather
    than forks). Every function it calls comes from `external_gauntlet`, so the series it writes
    are the ones the sweep would have computed itself -- same identity, same key, same trim.

    `hit` when the key landed on disk after the parent last looked (the sealed sweep's own pool
    builds the same docket head): a stat, never a second build of a cell already built.
    """
    import external_gauntlet as G

    meta = _META or {}
    obj = None
    ckey = str(spec.get("ckey") or "")
    try:
        if ckey and (G.CACHE_DIR / f"{ckey}.npz").exists():
            return ckey, "hit"
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


def _warm_batch(specs: list[dict]) -> list[tuple[str, str]]:
    """Warm one (symbol, chart) batch in order on this worker; one outcome per cell."""
    return [_warm_one(sp) for sp in specs]


def batches(specs: list[dict], size: int = BATCH_CELLS,
            window: int = BATCH_WINDOW) -> list[list[dict]]:
    """Group cells by (symbol, chart) inside a short look-ahead window.

    A PARTITION: every cell lands in exactly one batch, in its window's first-appearance order,
    and a cell moves at most `window` places -- so the judge's order survives at the resolution
    that matters, and `backlog_first` output is batched tier by tier by the caller.
    """
    out: list[list[dict]] = []
    for w0 in range(0, len(specs), max(1, window)):
        groups: dict[tuple[str, str], list[dict]] = {}
        for sp in specs[w0:w0 + window]:
            groups.setdefault((str(sp.get("sym") or ""), str(sp.get("tf") or "H1")),
                              []).append(sp)
        for rows in groups.values():
            for i in range(0, len(rows), max(1, size)):
                out.append(rows[i:i + size])
    return out


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
    """The sweep's own eligible cells, derived the sweep's own way (`judge_docket_order`).

    Streaming read, the point-in-time ratchet, de-duplication, the row-level `timeframe` fold, the
    economic-prior partition WITH `meta` and the modifier preflight all mirror
    `external_gauntlet.main`; without `meta` the tradeability limb never runs and this job warms
    cells the sweep sets aside at gate 0. Each spec carries `tf`, its own chart.
    """
    import judge_docket_order as O

    eligible, census = O.sealed_docket(G, meta)
    print(f"docket {census['rows']} rows -> {census['cells']} cells -> {census['eligible']} "
          f"eligible ({census['rejected_at_prior']} rejected at the economic prior, "
          f"{census['modifier_refused']} conserved by the sealed modifier preflight, as the "
          f"sweep would)")
    return eligible


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


def never_judged_flags(G, specs: list[dict]) -> int:
    """Stamp each spec `_never_judged`, by the SEALED SWEEP'S OWN RULE, and return how many are.

    `external_gauntlet.main._is_new` sorts a cell first when its id is absent from the seen-cells
    record, or present there with no stages behind it (`_stamped_but_unjudged`). The same two
    readers are called (in `judge_docket_order.stamp_new`), never restated, so the warmer and the
    judge agree on which cells are the backlog. An unreadable record reads as EMPTY -- every cell
    looks new, which spends one rotation and never hides a cell (the sweep's own fail-open
    direction).
    """
    import judge_docket_order as O

    return O.stamp_new(G, specs)


def backlog_first(specs: list[dict]) -> list[dict]:
    """THE BACKLOG IS WARMED BEFORE ANY RE-JUDGE. A PERMUTATION -- same cells, same multiset.

    WHY, MEASURED 2026-09-30. The judge rules on what is WARM: a cached cell costs the sweep no
    build, so warmth decides what a sweep contains. `cell_priority` ranks by the measured rate at
    which a family reaches a certificate -- which is, by construction, a rate only JUDGED families
    have -- so its head was the already-judged cells of the families with the best record, re-
    warmed every data day, while the never-judged frontier (1,398,253 cells on the trading box,
    growing ~3,000 a day) ranked on the house prior behind them. Every one of those re-warms is a
    cell the sweep then re-judges at a superlinear gate cost (measured locally on the sealed
    `run_gauntlet`: 0.022 s/cell at 200 cached cells, 0.048 at 2,000, 0.058 at 5,000) for a
    verdict the ledger already holds -- `_append_gate_ledger` writes a row only when the terminal
    gate CHANGES.

    The sealed sweep already puts never-judged cells first (`_is_new` is its primary sort key);
    this makes the one process that decides warmth agree with it. `cell_priority`'s order is kept
    INSIDE each tier, so within the backlog the most promising cell is still warmed first, and a
    re-judge is delayed until the backlog is warm, never dropped.
    """
    return sorted(specs, key=lambda sp: 0 if sp.get("_never_judged", True) else 1)


def modifier_refusals(G, specs: list[dict]) -> tuple[list[dict], int]:
    """(buildable specs, count set aside) -- cells the SEALED preflight refuses before any build.

    `external_gauntlet.modifier_preflight` names a variant key it cannot apply honestly (a
    `conditioner` with no series behind it, a `residual` on a family that does not residualise).
    The sweep conserves those as NOT_RUN_MODIFIER without building them; this job used to send
    each one to a worker, watch it fail, and park it in the deferral ledger for six hours before
    failing it again. Measured on the committed docket 2026-09-30: 9,558 of 19,260 gate-0-eligible
    cells carry such a key. The sweep still records every one of them; this only stops a warm
    worker spending a slot to learn what the preflight already knows.
    """
    pre = getattr(G, "modifier_preflight", None)
    if pre is None:
        return specs, 0
    keep: list[dict] = []
    n = 0
    for sp in specs:
        try:
            why = pre(sp)
        except Exception:
            why = None
        if why:
            n += 1
        else:
            keep.append(sp)
    return keep, n


def fan_out(G, src_key: str, dst_keys: list[str]) -> int:
    """Copy one warmed cell's series file under the cache keys of its exact equivalents.

    ATOMIC per destination, as `cache_save` is: a temp file in the same directory, then
    `os.replace`, so a reader never sees a torn `.npz`. Returns how many destinations landed.
    """
    import shutil

    src = G.CACHE_DIR / f"{src_key}.npz"
    if not src.exists():
        return 0
    n = 0
    for k in dst_keys:
        if not k or k == src_key:
            continue
        dst = G.CACHE_DIR / f"{k}.npz"
        tmp = G.CACHE_DIR / f"{k}.{os.getpid()}.fan.tmp"
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
            n += 1
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink()
    return n


def plan_equivalents(G, keyed: list[dict], warm: set[str], order_: list[dict],
                     held: list[dict] | None = None
                     ) -> tuple[list[dict], dict[str, list[str]], int]:
    """Collapse exact spellings of one rule to ONE build, and serve the rest from its output.

    Returns (specs to send, {sent key: follower keys}, followers served from disk now).

    A follower is never judged by proxy: it gets its OWN cache entry holding its twin's series,
    and the sealed sweep judges it under its own id through every gate. What is shared is the
    build, and only across groups `cell_equivalence` proves identical (see that module). A group
    whose member is HELD in the deferral ledger (its build failed, bars unchanged) sends nothing
    this round: the twins would fail the identical build, and the held member is retried -- for
    the whole group -- the moment its bars move.
    """
    try:
        import cell_equivalence as E
    except Exception:
        return order_, {}, 0
    by_key = E.groups(keyed)
    group_of: dict[str, str] = {}
    for gk, members in by_key.items():
        for sp in members:
            group_of[str(sp.get("ckey") or "")] = gk
    served_now = 0
    followers: dict[str, list[str]] = {}
    chosen: dict[str, str] = {}
    send: list[dict] = []
    held_groups = {group_of.get(str(h.get("ckey") or "")) for h in (held or [])} - {None}
    for sp in order_:
        ck = str(sp.get("ckey") or "")
        gk = group_of.get(ck)
        members = by_key.get(gk or "", [sp])
        if len(members) <= 1:
            send.append(sp)
            continue
        if gk in held_groups:
            continue
        if gk in chosen:
            followers.setdefault(chosen[gk], []).append(ck)
            continue
        hot = next((str(m.get("ckey")) for m in members if str(m.get("ckey") or "") in warm), "")
        if hot:
            served_now += fan_out(G, hot, [ck])
            continue
        chosen[gk or ck] = ck
        send.append(sp)
    return send, followers, served_now


#: Share of the judge's measured post-build room the warmer may fill. A sweep that outgrows its
#: task's ExecutionTimeLimit is KILLED and publishes nothing, so this is the one bound on warming
#: that protects throughput rather than costing it; 0.8 because the gate phase is superlinear in
#: the cells it rules (measured on the sealed `run_gauntlet`: 0.022 s/cell at 200 cached cells,
#: 0.048 at 2,000, 0.058 at 5,000) and a linear extrapolation from a smaller sweep under-reads it.
GATE_SAFETY = float(os.environ.get("WARM_GATE_SAFETY", "0.8"))
JUDGING_THROUGHPUT = DESK / "reports" / "JUDGING_THROUGHPUT.json"
SEALED_FRESH_BUDGET_SEC = 2700.0


def gate_room(anatomy: dict | None = None) -> dict:
    """How many cached cells the judge's LAST sweep says it can rule inside its task limit.

    Post-build seconds per cell come from `judging_burndown.sweep_anatomy` (the judge's own order
    and report stamps, less its pre-warm seconds, per cell advanced); the room is
    `GATE_SAFETY x (task limit - build budget) / that`, the limit and budget read from
    `JUDGING_THROUGHPUT.json`. Any missing input is UNMEASURED and bounds nothing (L1.28a) -- the
    warmer then warms as it did before this guard existed.
    """
    if anatomy is None:
        try:
            import judging_burndown as JB
            anatomy = JB.sweep_anatomy()
        except Exception as exc:
            anatomy = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    dec = ((_read_json(JUDGING_THROUGHPUT, {}) or {}).get("decision") or {})
    limit = dec.get("task_time_limit_s")
    fresh = dec.get("fresh_budget_s") or float(
        os.environ.get("GAUNTLET_FRESH_BUDGET_SEC", SEALED_FRESH_BUDGET_SEC))
    base = {"status": "UNMEASURED", "cells": None, "task_limit_s": limit,
            "build_budget_s": fresh, "safety": GATE_SAFETY,
            "anatomy_status": anatomy.get("status")}
    per_cell = anatomy.get("post_build_s_per_cell")
    if anatomy.get("status") != "MEASURED" or not isinstance(per_cell, (int, float)) \
            or per_cell <= 0:
        return {**base, "why": str(anatomy.get("why") or "sweep anatomy UNMEASURED")}
    if not isinstance(limit, (int, float)) or float(limit) <= float(fresh):
        return {**base, "why": "judge task limit UNMEASURED (JUDGING_THROUGHPUT.json)"}
    room = int(GATE_SAFETY * (float(limit) - float(fresh)) / float(per_cell))
    return {**base, "status": "MEASURED", "cells": room, "post_build_s_per_cell": per_cell}


def run_round(G, meta: dict, priors, deadline: float) -> dict:
    """One pass over the JUDGE'S OWN next docket, backlog first. Returns the round's census."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    import judge_docket_order as O
    from research.job_lock import free_mb

    t0 = time.time()
    specs = docket_specs(G, meta)
    if not specs:
        return {"eligible": 0, "note": "no docket to warm"}
    # THE SAME DOCKET, IN THE SAME ORDER, THE SEALED SWEEP WILL READ. Cells the family trim leaves
    # out of this sweep are not warmed now: the next sweep would not look at them, and their key
    # may roll over with the data day before one does. They stay in the docket.
    keep, order_census = O.sealed_keep(G, specs)
    n_never = int(order_census["keep_never_judged"])
    keep = backlog_first(keep)
    ordered_by = "sealed docket order (judge_docket_order), backlog first"
    print(f"  order: {ordered_by} -- {order_census['keep']} of {len(specs)} eligible cell(s) in "
          f"the next sweep's docket, {n_never} of them never judged; "
          f"{order_census['outside_keep']} left to a later sweep by the family trim")

    keyed, stamps, no_bars = resolve_keys(G, keep)
    warm = on_disk_keys(G)
    cold = [sp for sp in keyed if sp["ckey"] not in warm]
    n_warm_already = len(keyed) - len(cold)
    share = (n_warm_already / len(keyed)) if keyed else 0.0
    never_cold = sum(1 for sp in cold if sp.get("_never_judged"))
    print(f"  keyed {len(keyed)} of {len(keep)} cell(s) ({no_bars} with no bars on their own "
          f"chart); {n_warm_already} already warm ({share:.1%}), {len(cold)} cold "
          f"({never_cold} of them never judged)")

    now = time.time()
    order_, held, rows = split_deferred(cold, stamps, now)
    order_ = backlog_first(order_)
    if held:
        print(f"  deferred: {len(held)} cell(s) held this round (build failed before, bars "
              f"unchanged, retry in under {RETRY_SEC / 3600:.0f}h) -- ages in "
              f"{DEFERRALS.name}, none dropped")
    n_before_eq = len(order_)
    order_, followers, served_now = plan_equivalents(G, keyed, warm, order_, held)
    n_followers = sum(len(v) for v in followers.values())
    if served_now or n_followers:
        print(f"  equivalents: {served_now} cell(s) served from a twin already warm, "
              f"{n_followers} more ride on a twin being built this round -- "
              f"{n_before_eq - len(order_)} build(s) saved; each is still judged under its own id")

    room = gate_room()
    n_room_held = 0
    if room.get("status") == "MEASURED":
        allow = max(0, int(room["cells"]) - n_warm_already - served_now)
        if len(order_) > allow:
            n_room_held = len(order_) - allow
            order_ = order_[:allow]
            print(f"  gate room: the last sweep ruled at {room['post_build_s_per_cell']}s a "
                  f"cell after its build; {room['cells']} cached cells fit its task limit, so "
                  f"{n_room_held} cold cell(s) wait for the next data day's room -- a sweep "
                  f"killed at its limit publishes nothing")

    counts = {"warmed": 0, "missing": 0, "failed": 0, "hit": 0}
    fanned = served_now
    never_warmed = 0
    stopped = ""
    cap = measure_capacity()
    pool_n, target = int(cap["pool"]), int(cap["inflight"])
    samples = [target]
    print(f"  capacity: {cap['cores']} cores, {cap['idle_cores']} idle, {cap['free_mb']}MB free "
          f"-> pool {pool_n}, {target} in flight at IDLE priority, {len(order_)} cold cell(s)")
    if order_:
        todo = batches(order_)
        by_key = {str(sp.get("ckey") or ""): sp for sp in order_}
        done_n = 0
        next_cap = time.time() + CAPACITY_EVERY_SEC
        with ProcessPoolExecutor(max_workers=max(1, pool_n), initializer=_init,
                                 initargs=(meta,)) as pool:
            pending: set = set()
            it = iter(todo)

            def _submit() -> bool:
                while True:
                    b = next(it, None)
                    if b is None:
                        return False
                    # The judge's own pool may have built these since the scan; a stat is free.
                    live = [sp for sp in b if not (G.CACHE_DIR / f"{sp['ckey']}.npz").exists()]
                    counts["hit"] += len(b) - len(live)
                    if live:
                        pending.add(pool.submit(_warm_batch, live))
                        return True

            while len(pending) < target and _submit():
                pass
            while pending:
                fin, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
                for f in fin:
                    pending.discard(f)
                    try:
                        res = f.result()
                    except Exception:
                        res = []
                    for ck, outcome in res:
                        done_n += 1
                        counts[outcome] = counts.get(outcome, 0) + 1
                        sp = by_key.get(ck) or {}
                        if outcome in ("warmed", "hit"):
                            rows.pop(ck, None)
                            if outcome == "warmed" and sp.get("_never_judged"):
                                never_warmed += 1
                            if followers.get(ck):
                                fanned += fan_out(G, ck, followers[ck])
                        elif ck:
                            prev = rows.get(ck) if isinstance(rows.get(ck), dict) else {}
                            rows[ck] = {
                                "first_failed_at": prev.get("first_failed_at", now),
                                "last_failed_at": time.time(),
                                "n_failures": int(prev.get("n_failures") or 0) + 1,
                                "bars": stamps.get(f"{sp.get('sym')}|{sp.get('tf')}", ""),
                                "sym": sp.get("sym"), "family": sp.get("family"),
                                "tf": sp.get("tf"), "why": outcome,
                            }
                        if done_n % REPORT_EVERY == 0:
                            rate = done_n / max(1e-9, time.time() - t0) * 60.0
                            print(f"  [{done_n}/{len(order_)}] warmed={counts['warmed']} "
                                  f"failed={counts['failed']} hit={counts['hit']} "
                                  f"{time.time() - t0:.0f}s {rate:.0f} cells/min "
                                  f"in-flight={target}", flush=True)
                # THE DEADLINE AND THE MEMORY FLOOR ARE CHECKED EVERY WAKE, never every N cells.
                if not stopped and time.time() > deadline:
                    stopped = "run budget spent; the next invocation resumes from the cache"
                if not stopped:
                    avail = free_mb()
                    if avail is not None and avail < FLOOR_MB:
                        stopped = (f"{avail}MB free, floor {FLOOR_MB}MB -- warming is optional "
                                   f"work and yields the box; progress is cached and resumable")
                if stopped:
                    for f in list(pending):
                        if f.cancel():
                            pending.discard(f)
                    continue
                if time.time() >= next_cap:
                    target = retarget(len(pending), pool_n, _cpu_idle_cores(1.0))
                    samples.append(target)
                    next_cap = time.time() + CAPACITY_EVERY_SEC
                while len(pending) < target and _submit():
                    pass
    if stopped:
        print(f"  STOPPED: {stopped}")

    census = publish_deferrals(rows, held, time.time(), {"held_sample": [
        {"sym": sp.get("sym"), "family": sp.get("family"), "tf": sp.get("tf")}
        for sp in held[:50]]})
    built = counts["warmed"] + counts["failed"] + counts["missing"]
    secs = max(1e-9, time.time() - t0)
    return {
        "eligible": len(specs), "keep": len(keep), "keyed": len(keyed), "no_bars": no_bars,
        "warm_before": n_warm_already, "warm_share_before": round(share, 4),
        "cold": len(cold), "sent": len(order_), "held": len(held),
        "warmed": counts["warmed"], "failed": counts["failed"], "missing": counts["missing"],
        "hit_since_scan": counts["hit"],
        # THE BACKLOG'S SHARE OF THIS ROUND, and the builds equivalence saved. These are what
        # `research/judging_burndown.py` reads as the warm side of the drain: a cell warmed here
        # is a cell the next sweep judges without spending its own build budget.
        "never_judged": n_never, "never_judged_cold": never_cold,
        "never_judged_warmed": never_warmed,
        "fanned_out": fanned, "equivalent_followers": n_followers,
        "modifier_refused_not_sent": 0,
        "order_census": order_census,
        "gate_room": room, "held_for_gate_room": n_room_held,
        "seconds": round(secs, 1),
        # BUILD ATTEMPTS per minute -- a `hit` is a stat, not a build, and is not counted.
        "cells_per_min": round(built / secs * 60.0, 1),
        "workers": pool_n, "inflight_samples": {"min": min(samples), "max": max(samples),
                                                "last": samples[-1], "n": len(samples)},
        "capacity": cap, "priority": "IDLE (workers)", "batch_cells": BATCH_CELLS,
        "ordered_by": ordered_by, "stopped": stopped,
        "deferral_census": {k: v for k, v in census.items() if k != "held_sample"},
    }


def main() -> int:
    # The parent too: reading and ordering a million-row docket is CPU a miner must never lose.
    print(f"  priority: {_lower_priority()}")
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
        # PUBLISHED EVERY ROUND, not once at exit: `judging_burndown` reads the last round as the
        # warm side of the drain, and a report written only after an hour is an hour stale.
        _write_json(REPORT, {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                             "budget_sec": BUDGET_SEC, "rounds": rounds, "in_progress": True})
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
