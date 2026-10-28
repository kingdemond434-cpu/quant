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

6.  (2026-10-28) THE WARMER STALLED AT ~0 CELLS AND NEVER FINISHED A RUN. Box read: rounds of
    12, 11, 2 and 2 cells in 5,465 s, 8,379 s, 53,364 s and 90,255 s, each ending "STOPPED: run
    budget spent", the log silent after a docket header, the 07:00 trigger writing nothing. The
    causes, each fixed here (reports/judge/CACHEWARM_STALL_2026-10-28.md):
    a. The PARENT dropped itself to IDLE, so its single-threaded docket pass ran only on Windows'
       anti-starvation boost on a box the BELOW_NORMAL miners hold at ~100%. It now runs at
       EQUAL (BELOW_NORMAL, the miners' and the judge's class, never above); workers stay IDLE
       unless `WARM_EQUAL_WORKERS` opts some into EQUAL.
    b. The deadline bound only the build loop, so a docket pass longer than the budget still
       opened a pool, sent a first wave, and then waited on it without limit. The budget now
       binds every phase, a drain is capped at `DRAIN_SEC` (workers terminated after), and a
       watchdog hard-stops the process `BUDGET_SEC + GRACE_SEC` after it STARTED.
    c. Nothing guaranteed an exit inside the hourly trigger, so a run outlived the scheduler's
       limit and the next triggers were refused or wrote nothing. Every run now ends with a
       `CacheWarm END` line and a WARM_GAUNTLET.json carrying its status (DONE, HARD_STOP,
       NOT_ADMITTED, CRASHED), and while it runs the report carries its live phase and age.
    d. Each round re-decided all 1.65M rows through the sealed partition. A docket memo, stamped
       with the partition's inputs and a TTL, now re-decides only new cells -- same list, order
       and census.
    e. Memory: workers were sized on an unmeasured 900MB. Each worker now reports its high-water
       RSS; the pool is sized on the p75 of those, 4,500MB until the first is measured.

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
import threading
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

#: PER-WORKER MEMORY NEED, DERIVED FROM MEASUREMENT (2026-10-28). This was a flat 900MB, the
#: same figure the parent declared to admission at the foot of this file, and neither was ever
#: measured: `job_lock` records only the PARENT's high-water RSS, whose p75 on the trading box
#: reads 4,442MB (peak 4,454MB) -- the million-row docket, not a cell. The judge's own pre-warm
#: pool, running this same sealed builder, measured 1.8-2.1GB private per worker (box diag
#: 2026-10-20). So each worker now returns its own high-water RSS with every batch, the p75 of
#: the last `WORKER_PEAK_HISTORY` is kept in `WORKER_PEAKS`, and the pool is sized on it. Until a
#: worker has been measured, the default is the conservative 4,500MB (near the one measured
#: figure this job has), never 900. `WARM_NEED_MB` still overrides.
DEFAULT_WORKER_NEED_MB = 4500.0
#: Box-local and gitignored (`**/reports/*`). NOT under `data/.job_locks/`: the miner maintenance
#: sweep treats every non-`.peaks.json` file there as a lock and deletes one with no live pid.
WARM_STATE = DESK / "reports" / "warm_cache_state"
WORKER_PEAKS = WARM_STATE / "worker_peaks.json"
WORKER_PEAK_HISTORY = 64
#: The parent's own declared need when it has no measured run: the box's measured p75.
DEFAULT_PARENT_NEED_MB = 4500


def _p75(vals: list[float]) -> float:
    ordered = sorted(vals)
    return float(ordered[min(len(ordered) - 1, int(0.75 * len(ordered)))])


def worker_need_mb() -> tuple[float, str]:
    """(MB one warm worker is sized on, why). Override, else measured p75, else the default."""
    env = os.environ.get("WARM_NEED_MB")
    if env:
        with contextlib.suppress(ValueError):
            v = float(env)
            if v > 0:
                return v, "WARM_NEED_MB override"
    doc = _read_json(WORKER_PEAKS, {})
    raw = doc.get("peaks") if isinstance(doc, dict) else None
    peaks = [float(v) for v in (raw if isinstance(raw, list) else [])
             if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    if peaks:
        return _p75(peaks), f"p75 of {len(peaks)} measured worker peak(s) ({WORKER_PEAKS.name})"
    return DEFAULT_WORKER_NEED_MB, ("no worker measured yet: conservative default near the "
                                    "parent's measured 4,442MB p75, never the unmeasured 900MB")


def record_worker_peaks(new_peaks: list[int]) -> None:
    """Append this round's measured worker high-water marks to the receipt. Best effort."""
    vals = [int(v) for v in new_peaks if isinstance(v, int) and v > 0]
    if not vals:
        return
    doc = _read_json(WORKER_PEAKS, {})
    raw = doc.get("peaks") if isinstance(doc, dict) else None
    old = [int(v) for v in (raw if isinstance(raw, list) else [])
           if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
    rows = (old + vals)[-WORKER_PEAK_HISTORY:]
    _write_json(WORKER_PEAKS, {"peaks": rows, "p75_mb": _p75([float(v) for v in rows]),
                               "max_mb": max(rows), "n": len(rows),
                               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                               "what": "high-water RSS of warm_gauntlet_cache WORKER processes"})


def parent_need_mb() -> int:
    """What the parent declares to admission: its measured p75 when it has runs, else the default.

    `job_lock.measured_need_mb` already corrects a declaration UP to the measured p75; declaring
    the measured figure here keeps the log and the admission saying the same number.
    """
    try:
        from research.job_lock import observed_peaks
    except ModuleNotFoundError:
        from job_lock import observed_peaks  # type: ignore[no-redef]
    try:
        peaks = observed_peaks("warm_gauntlet_cache")
    except Exception:
        peaks = []
    return int(_p75([float(v) for v in peaks])) if peaks else DEFAULT_PARENT_NEED_MB


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
    need, need_why = worker_need_mb()
    by_mem = int((MEM_SHARE * float(free)) // need) if free else HISTORIC_FLOOR
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
            "by_mem": by_mem, "need_mb_per_worker": round(need), "need_basis": need_why,
            "pool": int(pool), "inflight": int(min(inflight, pool)),
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


#: The two priority classes this job uses, and the only two it may ever use.
#:   IDLE   Windows IDLE_PRIORITY_CLASS / POSIX nice 19: runs only on cycles nothing else wants.
#:   EQUAL  Windows BELOW_NORMAL_PRIORITY_CLASS / POSIX nice 10: the class the miners, the judge's
#:          sweep and every scheduled desk task (Task Scheduler Priority 7) run at -- EQUAL to the
#:          miners, never above them (principal, 2026-10-20: "the judge gets NO CPU priority above
#:          the miners; EQUAL is fine"; scripts/judge_priority.py measures and enforces it for the
#:          judge). Nothing here ever sets NORMAL or higher.
IDLE = "idle"
EQUAL = "equal"

#: THE PARENT RUNS AT EQUAL (2026-10-28), and this is the change that un-stalls the job. The
#: parent's serial phases -- streaming a 1.65M-row docket twice, the sealed partition, the sealed
#: order, keying, a directory scan -- are single-threaded orchestration the judge's own sweep
#: parent performs at BELOW_NORMAL every sweep. At IDLE on a box the BELOW_NORMAL miners hold at
#: ~100%, Windows runs an IDLE thread only on its anti-starvation boost, so those phases took
#: hours, the run budget was spent before a single cell was submitted, and every round ended
#: "STOPPED: run budget spent" with 2-12 cells. `WARM_PARENT_PRIORITY=idle` restores the old class.
PARENT_PRIORITY = (os.environ.get("WARM_PARENT_PRIORITY") or EQUAL).strip().lower()

#: Workers that build at EQUAL priority, the rest at IDLE. DEFAULT 0: every worker stays IDLE, so
#: the BUILD lane spends only cycles no miner wants -- the standing rule that mining is never cut or
#: slowed. Raising it is the principal's call, not a session's: on an oversubscribed box each EQUAL
#: worker takes about one runnable thread's share (18 cores / ~60 runnable threads ~= 0.3 core)
#: from the miners, which buys roughly 0.3 / 4.0 core-s per warmed cell ~= 6,500 warmed cells a
#: day per worker (PREWARM_CEILING_2026-10-27 §2, INFERRED). It is a guaranteed floor, filled
#: before the IDLE lane, and capped by the measured memory pool like every other worker.
def _env_count(name: str, default: int = 0) -> int:
    """A non-negative integer from the environment; anything unparsable reads as `default`.

    Read at import, i.e. before `CacheWarm START`: a typo in the task action must never crash
    the job before it can say so (audit of 6ea07bdf2)."""
    raw = os.environ.get(name)
    try:
        v = float(str(raw).strip()) if raw not in (None, "") else float(default)
        if v != v or v in (float("inf"), float("-inf")):
            return default
        return max(0, int(v))
    except (TypeError, ValueError):
        return default


EQUAL_WORKERS = _env_count("WARM_EQUAL_WORKERS", 0)


def _set_priority(mode: str) -> str:
    """Put THIS process at IDLE or EQUAL. Never above EQUAL. Returns what it did, for the log.

    On Windows `nice()` sets the class outright, so EQUAL both lowers a process started at NORMAL
    (a manual run from a shell) and lifts one that inherited IDLE. On POSIX an unprivileged process
    can only raise its nice value, so EQUAL there never lowers a niceness it cannot restore.
    """
    want_idle = str(mode).lower() == IDLE
    try:
        import psutil
        p = psutil.Process()
        if sys.platform == "win32":
            p.nice(psutil.IDLE_PRIORITY_CLASS if want_idle
                   else psutil.BELOW_NORMAL_PRIORITY_CLASS)
            return "IDLE" if want_idle else "BELOW_NORMAL (equal to the miners, never above)"
        want = 19 if want_idle else 10
        cur = int(p.nice())
        if cur < want:
            p.nice(want)
            cur = want
        note = "" if cur == want else f" (wanted {want}; cannot raise unprivileged)"
        return f"nice {cur}{note}"
    except Exception as exc:
        try:
            os.nice(19 if want_idle else 10)  # type: ignore[attr-defined,unused-ignore]
            return "nice19" if want_idle else "nice10"
        except Exception:
            return f"UNCHANGED ({type(exc).__name__})"


def _lower_priority() -> str:
    """Run this process at IDLE priority: it may only take CPU nothing else wants.

    Kept by name: the IDLE lane's workers call it. Every normal- and below-normal-priority process
    -- miners, the live terminal, the gateway, the sealed judge and its pool -- preempts an IDLE
    worker outright.
    """
    out = _set_priority(IDLE)
    return "idle" if out == "IDLE" or out.startswith("nice 19") else out


def _init(meta: dict) -> None:
    global _META
    _META = meta
    _lower_priority()


def _init_equal(meta: dict) -> None:
    """Initializer for the EQUAL lane's workers (only when `WARM_EQUAL_WORKERS` > 0)."""
    global _META
    _META = meta
    _set_priority(EQUAL)


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
        from mt5desk.legacy_family_inputs import input_preflight
        why = input_preflight(spec.get("family"), spec.get("params"))
        if why:
            return ckey, "failed|" + why
        tf = str(spec.get("tf") or "H1")
        frame = G._bars_for(spec["sym"], tf)
        if frame is None or len(frame) == 0:
            return ckey, f"missing|no {tf} bars for {spec['sym']}"
        obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if not obj:
            return ckey, "failed|" + str(G.LAST_BUILD_FAILURE or "build_cell returned no cell")[:240]
        last_day = frame.index[-1].normalize()
        ds1 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
        costs3 = G.costs_for(spec["sym"], meta, mult=G.COST_SCENARIO)
        ds3 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], costs3), last_day)
        if ds1 is None or ds3 is None:
            return ckey, "failed|daily cost series unavailable"
        G.cache_save(ckey, ds1, ds3)
        return ckey, "warmed"
    except Exception as exc:
        return ckey, f"failed|{type(exc).__name__}: {str(exc)[:200]}"
    finally:
        if obj is not None:
            obj["sigs"] = None
            obj["df"] = None


def _warm_batch(specs: list[dict]) -> dict:
    """Warm one (symbol, chart) batch in order on this worker; one outcome per cell.

    Returns {"res": [(key, outcome), ...], "pid": worker pid, "peak_mb": its high-water RSS}, so the
    parent sizes the next pool on what a worker MEASURED, not on a declaration.
    """
    res = [_warm_one(sp) for sp in specs]
    peak = None
    with contextlib.suppress(Exception):
        try:
            from research.job_lock import peak_rss_mb
        except ModuleNotFoundError:
            from job_lock import peak_rss_mb  # type: ignore[no-redef]
        peak = peak_rss_mb()
    return {"res": res, "pid": os.getpid(), "peak_mb": peak}


def _batch_outcomes(result) -> tuple[list[tuple[str, str]], int | None, int | None]:
    """(outcomes, worker pid, worker peak MB) from either result shape (old list, or dict)."""
    if isinstance(result, dict):
        res = result.get("res") or []
        pid = result.get("pid")
        peak = result.get("peak_mb")
        return (list(res), pid if isinstance(pid, int) else None,
                peak if isinstance(peak, int) and peak > 0 else None)
    return list(result or []), None, None


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
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except Exception as exc:
        print(f"  {path.name} NOT written ({type(exc).__name__}: {exc})")


#: THE DOCKET MEMO (2026-10-28). The sealed partition and modifier preflight decide each cell's
#: eligibility from the cell alone plus a handful of inputs (the universe registry, which charts
#: have parquets, the family and gate code). Re-deciding 1.65M cells every round -- loading an
#: intraday frame for each non-H1 one -- was the serial pass that ran for hours at IDLE. The memo
#: keeps each cell's outcome under a STAMP of those inputs and for at most `DOCKET_MEMO_TTL_SEC`,
#: so a round re-decides only the cells minted since the last one. It lives in `WARM_STATE`
#: (gitignored, box-local). A stale memo can change which cells are WARMED, never a verdict: the
#: judge reads none of it and builds and gates every cell itself.
DOCKET_MEMO = WARM_STATE / "docket_memo.json"
#: Where a run that was not admitted records why (it never writes REPORT).
NOT_ADMITTED = WARM_STATE / "last_not_admitted.json"
DOCKET_MEMO_TTL_SEC = float(os.environ.get("WARM_DOCKET_MEMO_TTL_SEC", str(6 * 3600)))
#: Outcomes that asked the live terminal (a chart with no parquet) are re-decided after this.
DOCKET_MEMO_LIVE_TTL_SEC = float(os.environ.get("WARM_DOCKET_MEMO_LIVE_TTL_SEC", "3600"))


def docket_memo_stamp(G) -> str:
    """A digest of every input the sealed partition and preflight read besides the cell itself."""
    import hashlib

    parts: list[str] = []
    uni = getattr(G, "UNI", None)
    files = [Path(uni) / "universe.json"] if uni is not None else []
    g_file = getattr(G, "__file__", None)
    if g_file:
        files.append(Path(g_file))
    files += [DESK / "mt5desk" / n for n in ("legacy_family_inputs.py", "family_inputs.py",
                                             "families.py", "families_orthogonal.py",
                                             "cell_modifiers.py")]
    # economic_prior and cell_id; the live-terminal chart route (`_live_frame` -> h1_source ->
    # mt5_session); and this module. Terminal AVAILABILITY is not a file: outcomes that depended
    # on it carry their own short TTL inside the memo (judge_docket_order.LIVE_MARK).
    files += [DESK / "research" / n for n in ("frontier_identity.py", "h1_source.py",
                                              "mt5_session.py", "judge_docket_order.py")]
    parts.append(f"platform:{os.name}")
    for f in files:
        try:
            st = f.stat()
            parts.append(f"{f.name}:{st.st_mtime_ns}:{st.st_size}")
        except OSError:
            parts.append(f"{f.name}:absent")
    if uni is not None:
        try:
            names = sorted(e.name for e in os.scandir(uni) if e.name.endswith(".parquet"))
        except OSError:
            names = []
        parts.append("parquets:" + hashlib.sha1("\n".join(names).encode()).hexdigest())
    return hashlib.sha1("|".join(parts).encode()).hexdigest()


def load_docket_memo(G, now: float | None = None) -> tuple[dict, dict]:
    """(memo rows to reuse, its census). Empty when the stamp moved, it aged out or unreadable."""
    now = time.time() if now is None else now
    stamp = docket_memo_stamp(G)
    doc = _read_json(DOCKET_MEMO, {})
    rows = doc.get("rows") if isinstance(doc, dict) else None
    born = float(doc.get("born") or 0.0) if isinstance(doc, dict) else 0.0
    if not isinstance(rows, dict) or not rows:
        return {}, {"stamp": stamp, "born": now, "reused": 0, "why": "no memo yet"}
    if doc.get("stamp") != stamp:
        return {}, {"stamp": stamp, "born": now, "reused": 0,
                    "why": "inputs changed (registry, parquets or code): every cell re-decided"}
    if now - born >= DOCKET_MEMO_TTL_SEC:
        return {}, {"stamp": stamp, "born": now, "reused": 0,
                    "why": f"memo older than {DOCKET_MEMO_TTL_SEC / 3600:.0f}h: re-decided"}
    return dict(rows), {"stamp": stamp, "born": born, "reused": len(rows), "why": "reused"}


def save_docket_memo(memo: dict, info: dict) -> None:
    """Write the memo compactly (no indent: it holds one short entry per docket cell)."""
    doc = {"stamp": info.get("stamp"), "born": info.get("born"),
           "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n": len(memo),
           "rows": memo}
    try:
        DOCKET_MEMO.parent.mkdir(parents=True, exist_ok=True)
        tmp = DOCKET_MEMO.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, DOCKET_MEMO)
    except Exception as exc:
        print(f"  {DOCKET_MEMO.name} NOT written ({type(exc).__name__}: {exc})")


def docket_specs(G, meta: dict) -> list[dict]:
    """The sweep's own eligible cells, derived the sweep's own way (`judge_docket_order`).

    Streaming read, the point-in-time ratchet, de-duplication, the row-level `timeframe` fold, the
    economic-prior partition WITH `meta` and the modifier preflight all mirror
    `external_gauntlet.main`; without `meta` the tradeability limb never runs and this job warms
    cells the sweep sets aside at gate 0. Each spec carries `tf`, its own chart. Cells whose
    outcome the docket memo already holds skip the partition and preflight (same list, same order).
    """
    import judge_docket_order as O

    memo, info = load_docket_memo(G)
    eligible, census = O.sealed_docket(G, meta, memo=memo, live_ttl_s=DOCKET_MEMO_LIVE_TTL_SEC)
    if census.get("memo_new") or info.get("reused") != len(memo):
        save_docket_memo(memo, info)
    print(f"docket {census['rows']} rows -> {census['cells']} cells -> {census['eligible']} "
          f"eligible ({census['rejected_at_prior']} rejected at the economic prior, "
          f"{census['modifier_refused']} conserved by the sealed modifier preflight, as the "
          f"sweep would); memo: {census.get('memo_hits', 0)} reused, "
          f"{census.get('memo_new', 0)} decided now ({info.get('why')})", flush=True)
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


def capture_failed_spec(spec: dict, observed_at: float) -> dict:
    """Freeze worker inputs at result collection; this is not source provenance."""
    import hashlib

    required = ("sym", "family", "tf", "params")
    if not all(k in spec for k in required):
        return {"source_spec_capture_error": "UNMEASURED: worker specification unavailable"}
    identity = {k: spec[k] for k in (*required, "day") if k in spec}
    try:
        encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        return {"source_spec_capture_error": f"INVALID: {type(exc).__name__}: {exc}"}
    return {"source_spec": json.loads(encoded),
            "source_spec_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "source_spec_observed_at": observed_at,
            "source_spec_clock_basis": "build-result collection only; not publication or preregistration"}


def publish_deferrals(rows: dict, held: list[dict], now: float, extra: dict) -> dict:
    """Write the deferral ledger and return its census, ages included."""
    from collections import Counter

    ages = sorted(((now - float(r.get("first_failed_at") or now)) / 3600.0)
                  for r in rows.values() if isinstance(r, dict))
    reasons = Counter(str(r.get("why") or "UNMEASURED") for r in rows.values()
                      if isinstance(r, dict))
    census = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "n_deferred": len(rows),
        "n_held_this_pass": len(held),
        "n_with_frozen_spec": sum(isinstance(r, dict) and "source_spec" in r
                                  for r in rows.values()),
        "n_without_frozen_spec": sum(not isinstance(r, dict) or "source_spec" not in r
                                     for r in rows.values()),
        "oldest_hours": round(ages[-1], 2) if ages else 0.0,
        "median_hours": round(ages[len(ages) // 2], 2) if ages else 0.0,
        "top_build_failures": dict(reasons.most_common(12)),
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
    if isinstance(limit, (int, float)) and not isinstance(limit, bool) and limit == 0:
        return {**base, "status": "MEASURED_UNLIMITED",
                "why": "scheduler ExecutionTimeLimit=PT0S; no task-deadline gate-room ceiling; build deadline, measured capacity and memory floor still apply"}
    per_cell = anatomy.get("post_build_s_per_cell")
    if anatomy.get("status") != "MEASURED" or not isinstance(per_cell, (int, float)) \
            or per_cell <= 0:
        return {**base, "why": str(anatomy.get("why") or "sweep anatomy UNMEASURED")}
    if not isinstance(limit, (int, float)) or float(limit) <= float(fresh):
        return {**base, "why": "judge task limit UNMEASURED (JUDGING_THROUGHPUT.json)"}
    room = int(GATE_SAFETY * (float(limit) - float(fresh)) / float(per_cell))
    return {**base, "status": "MEASURED", "cells": room, "post_build_s_per_cell": per_cell}


#: Once the budget is spent, how long in-flight batches may finish before their workers are
#: TERMINATED. The old code waited on them without bound: a batch of eight cells on a starved
#: IDLE worker took the 14.8h and 25h "rounds" the box logged. A terminated worker loses only its
#: unfinished cells -- `cache_save` writes a temp file and renames it, so nothing torn is left --
#: and the next run resumes from the cache.
DRAIN_SEC = float(os.environ.get("WARM_DRAIN_SEC", "90"))

#: The HARD STOP: `BUDGET_SEC + GRACE_SEC` after the process STARTED (admission wait included),
#: a watchdog thread writes WARM_GAUNTLET.json and the completion line, terminates this job's own
#: workers and exits -- whatever the main thread is doing (a serial phase, a hung frame read, a
#: drain). 3300 + 240 = 3540s keeps every run inside its hourly trigger, so `IgnoreNew` never has
#: to refuse the next one and no run ever outlives the scheduler's ExecutionTimeLimit to become an
#: orphan holding the log open.
GRACE_SEC = float(os.environ.get("WARM_GRACE_SEC", "240"))

#: How often the watchdog republishes the in-progress report (phase, its age, rounds so far), so a
#: run sitting in a long phase is VISIBLE as that phase rather than as a stale file.
HEARTBEAT_SEC = float(os.environ.get("WARM_HEARTBEAT_SEC", "60"))

#: Live run state, read by the watchdog. Only the main thread writes it.
_STATE: dict = {"phase": "init", "phase_since": time.time(), "rounds": [], "start": None,
                "deadline": None, "hard_stop": None, "status": "RUNNING"}


def _close_pool(pool, kill: bool, join_s: float = 10.0) -> int:
    """Shut a warm pool down; with `kill`, TERMINATE its workers first. Returns how many died.

    v1.1 (audit of 6ea07bdf2): the worker processes are SNAPSHOTTED BEFORE any shutdown call.
    `shutdown(wait=False)` drops the executor's `_processes` reference, so the old order --
    shutdown, then terminate whatever `_processes` held -- terminated nothing: two of two hung
    workers survived on 3.11 and 3.14, the parent lingered until their batch ended, and the
    watchdog then overwrote DONE with HARD_STOP. Now: snapshot, terminate, join, kill what is
    left, and only then shut down.
    """
    shut = getattr(pool, "shutdown", None)
    if shut is None:
        return 0
    if not kill:
        shut(wait=True)
        return 0
    procs = [pr for pr in list((getattr(pool, "_processes", None) or {}).values())
             if pr is not None]
    for pr in procs:
        with contextlib.suppress(Exception):
            pr.terminate()
    end = time.time() + max(0.0, join_s)
    for pr in procs:
        with contextlib.suppress(Exception):
            pr.join(max(0.0, end - time.time()))
    for pr in procs:
        with contextlib.suppress(Exception):
            if pr.is_alive():
                pr.kill()
                pr.join(2.0)
    with contextlib.suppress(Exception):
        shut(wait=False, cancel_futures=True)
    dead = 0
    for pr in procs:
        with contextlib.suppress(Exception):
            dead += int(not pr.is_alive())
    return dead


def _phase(name: str, **info) -> None:
    """Enter a phase: stamp it in the live state and print it, so the log shows where time goes."""
    now = time.time()
    prev, since = _STATE.get("phase"), float(_STATE.get("phase_since") or now)
    _STATE.update({"phase": name, "phase_since": now, "phase_info": info})
    extra = " ".join(f"{k}={v}" for k, v in info.items())
    print(f"  [{time.strftime('%H:%M:%S')}] phase {name} (after {prev} {now - since:.0f}s)"
          + (f" {extra}" if extra else ""), flush=True)


def _report_doc(status: str, **extra) -> dict:
    now = time.time()
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "status": status, "in_progress": status == "RUNNING", "pid": os.getpid(),
            "budget_sec": BUDGET_SEC, "grace_sec": GRACE_SEC,
            "started_at": _STATE.get("start"), "deadline": _STATE.get("deadline"),
            "hard_stop": _STATE.get("hard_stop"),
            "phase": _STATE.get("phase"),
            "phase_age_s": round(now - float(_STATE.get("phase_since") or now), 1),
            "phase_info": _STATE.get("phase_info"),
            "parent_priority": _STATE.get("parent_priority"),
            "equal_workers": EQUAL_WORKERS,
            "orphan_tmp_sweep": _STATE.get("orphan_tmp_sweep"),
            **_rounds_view(), **extra}


#: How many of the PREVIOUS run's rounds the report carries until this run's first round lands.
CARRY_ROUNDS = 3


def _rounds_view() -> dict:
    """`rounds` for the report: this run's, or -- until its first round lands -- the previous
    run's last rounds, labelled. v1.1: the heartbeat published `rounds: []` within 60 s of every
    start, so `judging_burndown.warm_side()` read UNMEASURED for most of each run."""
    cur = list(_STATE.get("rounds") or [])
    if cur:
        return {"rounds": cur, "rounds_source": "this run"}
    prev = list(_STATE.get("prev_rounds") or [])
    return {"rounds": prev, "rounds_source": ("previous run (carried until this run's first round "
                                              "lands)" if prev else "none yet")}


def _load_prev_rounds() -> None:
    doc = _read_json(REPORT, {})
    rounds = doc.get("rounds") if isinstance(doc, dict) else None
    _STATE["prev_rounds"] = ([r for r in rounds if isinstance(r, dict)][-CARRY_ROUNDS:]
                             if isinstance(rounds, list) else [])


#: Serialises every write of REPORT and every status transition, so a heartbeat that read
#: RUNNING can never land after DONE (v1.1: 5 of 30 widened-window runs ended RUNNING).
_REPORT_LOCK = threading.Lock()
FINAL = ("DONE", "HARD_STOP", "CRASHED")


def _publish(status: str, **extra) -> bool:
    """Write REPORT under the lock. RUNNING is written only while the run is RUNNING and
    admitted; a final status is written once, and nothing is written after it."""
    with _REPORT_LOCK:
        if not _STATE.get("admitted"):
            return False
        cur = _STATE.get("status")
        if cur in FINAL:
            return False
        if status == "RUNNING" and cur != "RUNNING":
            return False
        if status != "RUNNING":
            _STATE["status"] = status
        _write_json(REPORT, _report_doc(status, **extra))
        return True


def run_round(G, meta: dict, priors, deadline: float) -> dict:
    """One pass over the JUDGE'S OWN next docket, backlog first. Returns the round's census."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait

    import judge_docket_order as O
    from research.job_lock import free_mb

    t0 = time.time()
    phase_s: dict[str, float] = {}

    def _mark(name: str, **info) -> None:
        cur = str(_STATE.get("phase") or "")
        if cur:
            phase_s[cur] = round(phase_s.get(cur, 0.0)
                                 + time.time() - float(_STATE.get("phase_since") or time.time()), 1)
        _phase(name, **info)

    _mark("docket_load")
    specs = docket_specs(G, meta)
    if not specs:
        return {"eligible": 0, "note": "no docket to warm"}
    # THE SAME DOCKET, IN THE SAME ORDER, THE SEALED SWEEP WILL READ. Cells the family trim leaves
    # out of this sweep are not warmed now: the next sweep would not look at them, and their key
    # may roll over with the data day before one does. They stay in the docket.
    _mark("sealed_order", eligible=len(specs))
    keep, order_census = O.sealed_keep(G, specs)
    n_never = int(order_census["keep_never_judged"])
    keep = backlog_first(keep)
    ordered_by = "sealed docket order (judge_docket_order), backlog first"
    print(f"  order: {ordered_by} -- {order_census['keep']} of {len(specs)} eligible cell(s) in "
          f"the next sweep's docket, {n_never} of them never judged; "
          f"{order_census['outside_keep']} left to a later sweep by the family trim")

    _mark("keying", keep=len(keep))
    keyed, stamps, no_bars = resolve_keys(G, keep)
    _mark("cache_scan")
    warm = on_disk_keys(G)
    cold = [sp for sp in keyed if sp["ckey"] not in warm]
    n_warm_already = len(keyed) - len(cold)
    share = (n_warm_already / len(keyed)) if keyed else 0.0
    never_cold = sum(1 for sp in cold if sp.get("_never_judged"))
    print(f"  keyed {len(keyed)} of {len(keep)} cell(s) ({no_bars} with no bars on their own "
          f"chart); {n_warm_already} already warm ({share:.1%}), {len(cold)} cold "
          f"({never_cold} of them never judged)")

    _mark("plan", cold=len(cold))
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
    abandoned = 0
    worker_peaks: dict[int, int] = {}
    by_lane = {EQUAL: 0, IDLE: 0}
    cap = measure_capacity()
    pool_n, target = int(cap["pool"]), int(cap["inflight"])
    samples = [target]
    n_eq = min(EQUAL_WORKERS, pool_n)
    n_idle = pool_n - n_eq
    print(f"  capacity: {cap['cores']} cores, {cap['idle_cores']} idle, {cap['free_mb']}MB free, "
          f"{cap.get('need_mb_per_worker')}MB per worker ({cap.get('need_basis')}) "
          f"-> pool {pool_n} ({n_eq} at EQUAL, {n_idle} at IDLE), {target} in flight, "
          f"{len(order_)} cold cell(s)", flush=True)
    # THE BUDGET BINDS THE SERIAL PHASES TOO. The old round checked its deadline only inside the
    # build loop, so when the docket pass alone outlasted the budget it still opened a pool, sent
    # a first wave, found the deadline gone at the first wake and then waited on that wave.
    if order_ and time.time() > deadline:
        stopped = (f"run budget spent before the build phase -- the serial phases took "
                   f"{time.time() - t0:.0f}s; nothing was submitted")
    if order_ and not stopped:
        _mark("build", cells=len(order_), pool=pool_n, inflight=target)
        todo = batches(order_)
        by_key = {str(sp.get("ckey") or ""): sp for sp in order_}
        done_n = 0
        next_cap = time.time() + CAPACITY_EVERY_SEC
        pools: dict[str, object] = {}
        if n_eq:
            pools[EQUAL] = ProcessPoolExecutor(max_workers=n_eq, initializer=_init_equal,
                                               initargs=(meta,))
        if n_idle > 0:
            pools[IDLE] = ProcessPoolExecutor(max_workers=max(1, n_idle), initializer=_init,
                                              initargs=(meta,))
        pending: dict = {}           # future -> (lane, cells in the batch)
        it = iter(todo)
        drain_until: float | None = None
        kill = False

        def _lane_load(lane: str) -> int:
            return sum(1 for v in pending.values() if v[0] == lane)

        def _submit() -> bool:
            # EQUAL lane first (its workers are the guaranteed floor), then IDLE up to target.
            if EQUAL in pools and _lane_load(EQUAL) < n_eq:
                lane = EQUAL
            elif IDLE in pools and _lane_load(IDLE) < max(0, target - (n_eq if EQUAL in pools
                                                                       else 0)):
                lane = IDLE
            else:
                return False
            while True:
                b = next(it, None)
                if b is None:
                    return False
                # The judge's own pool may have built these since the scan; a stat is free.
                live = [sp for sp in b if not (G.CACHE_DIR / f"{sp['ckey']}.npz").exists()]
                counts["hit"] += len(b) - len(live)
                if live:
                    fut = pools[lane].submit(_warm_batch, live)  # type: ignore[attr-defined]
                    pending[fut] = (lane, len(live))
                    return True

        try:
            while _submit():
                pass
            while pending:
                fin, _ = wait(set(pending), timeout=5, return_when=FIRST_COMPLETED)
                for f in fin:
                    lane, _n = pending.pop(f)
                    try:
                        res, wpid, wpeak = _batch_outcomes(f.result())
                    except Exception:
                        res, wpid, wpeak = [], None, None
                    if wpid is not None and wpeak:
                        worker_peaks[wpid] = max(worker_peaks.get(wpid, 0), wpeak)
                    for ck, outcome in res:
                        state, _, reason = outcome.partition("|")
                        done_n += 1
                        counts[state] = counts.get(state, 0) + 1
                        if state == "warmed":
                            by_lane[lane] = by_lane.get(lane, 0) + 1
                        sp = by_key.get(ck) or {}
                        if state in ("warmed", "hit"):
                            rows.pop(ck, None)
                            if state == "warmed" and sp.get("_never_judged"):
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
                                "tf": sp.get("tf"), "why": reason or state,
                                **capture_failed_spec(sp, time.time()),
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
                mem_stop = False
                if not stopped:
                    avail = free_mb()
                    if avail is not None and avail < FLOOR_MB:
                        mem_stop = True
                        stopped = (f"{avail}MB free, floor {FLOOR_MB}MB -- warming is optional "
                                   f"work and yields the box; progress is cached and resumable")
                if stopped:
                    if drain_until is None:
                        # A MEMORY stop frees the workers NOW: the box is short of exactly what
                        # they hold. A budget stop lets in-flight batches finish for DRAIN_SEC.
                        drain_until = time.time() + (0.0 if mem_stop else DRAIN_SEC)
                        _mark("drain", in_flight=len(pending), drain_s=DRAIN_SEC)
                    for f in list(pending):
                        if f.cancel():
                            pending.pop(f, None)
                    if pending and time.time() >= drain_until:
                        abandoned = sum(n for _lane, n in pending.values())
                        kill = True
                        break
                    continue
                if time.time() >= next_cap:
                    target = retarget(len(pending), pool_n, _cpu_idle_cores(1.0))
                    samples.append(target)
                    next_cap = time.time() + CAPACITY_EVERY_SEC
                while _submit():
                    pass
        finally:
            for ex in pools.values():
                _close_pool(ex, kill=kill or bool(pending))
    if stopped:
        print(f"  STOPPED: {stopped}" + (f" ({abandoned} in-flight cell(s) abandoned after a "
                                          f"{DRAIN_SEC:.0f}s drain; their workers were "
                                          f"terminated)" if abandoned else ""), flush=True)
    if worker_peaks:
        with contextlib.suppress(Exception):
            record_worker_peaks(list(worker_peaks.values()))
    _mark("publish")

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
        "phase_seconds": phase_s,
        "warmed_by_lane": by_lane, "abandoned_in_flight": abandoned,
        "worker_peak_mb": sorted(worker_peaks.values()),
        # BUILD ATTEMPTS per minute -- a `hit` is a stat, not a build, and is not counted.
        "cells_per_min": round(built / secs * 60.0, 1),
        "workers": pool_n, "inflight_samples": {"min": min(samples), "max": max(samples),
                                                "last": samples[-1], "n": len(samples)},
        "capacity": cap,
        "priority": {"parent": _STATE.get("parent_priority"), "equal_workers": n_eq,
                     "idle_workers": n_idle},
        "batch_cells": BATCH_CELLS,
        "ordered_by": ordered_by, "stopped": stopped,
        "deferral_census": {k: v for k, v in census.items() if k != "held_sample"},
    }


#: An orphan temp file is swept only once it is at least this old. A live `cache_save` writes and
#: renames its temp in milliseconds, so an hour-old one belongs to a writer that died.
ORPHAN_TMP_MIN_AGE_SEC = float(os.environ.get("WARM_ORPHAN_TMP_MIN_AGE_SEC", "3600"))


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return bool(psutil.pid_exists(pid))
    except Exception:
        return True          # unknowable reads as alive: never delete a file a writer may hold


def sweep_orphan_tmps(dirs: list[Path], now: float | None = None,
                      min_age_s: float | None = None) -> dict:
    """Delete `*.tmp` files left by killed writers, from the warmer side (the gauntlet is sealed).

    A file is removed only when it is older than `min_age_s` AND no pid named in its name is
    alive (`{key}.{pid}.tmp`, `{key}.{pid}.fan.tmp`, `<report>.{pid}.{tid}.tmp`,
    `docket_memo.{pid}.tmp`). The audit's 300 SIGKILLs during `cache_save` left 296 of them.
    Only `*.tmp` is ever touched -- never an `.npz` or `.json`.
    """
    now = time.time() if now is None else now
    min_age = ORPHAN_TMP_MIN_AGE_SEC if min_age_s is None else min_age_s
    out = {"scanned": 0, "removed": 0, "young": 0, "live_writer": 0, "errors": 0}
    me = os.getpid()
    for d in dirs:
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                if not e.name.endswith(".tmp"):
                    continue
                out["scanned"] += 1
                try:
                    if now - e.stat().st_mtime < min_age:
                        out["young"] += 1
                        continue
                except OSError:
                    out["errors"] += 1
                    continue
                pids = [int(x) for x in e.name.split(".")[1:-1] if x.isdigit()]
                if any(pid == me or _pid_alive(pid) for pid in pids if 0 < pid < 1 << 22):
                    out["live_writer"] += 1
                    continue
                try:
                    os.unlink(e.path)
                    out["removed"] += 1
                except OSError:
                    out["errors"] += 1
    return out


_NOTE = ("Warmth is what decides which cells a bounded sweep can reach: an uncached cell costs "
         "the sweep ~22s of its build budget and a cached one costs it nothing. This job holds no "
         "authority over any verdict.")


def _kill_own_workers() -> int:
    """Terminate every descendant of THIS process (its warm workers). Returns how many."""
    n = 0
    try:
        import psutil
        for child in psutil.Process().children(recursive=True):
            with contextlib.suppress(Exception):
                child.kill()
                n += 1
    except Exception:
        pass
    return n


#: Exit code of a hard stop (a run still working at start + budget + grace): non-zero, so the
#: scheduler's last result and process_health see it.
HARD_STOP_RC = 3


def _hard_stop() -> None:
    """The watchdog's exit: publish, print the completion line, kill our workers, leave."""
    phase = _STATE.get("phase")
    age = time.time() - float(_STATE.get("phase_since") or time.time())
    killed = _kill_own_workers()
    # A run that already published a FINAL status (DONE) and merely lingers keeps it: the hard
    # stop then only reaps and exits with the run's own rc. Otherwise the report (when this run
    # owns it -- admitted, never a duplicate or one still waiting) says HARD_STOP and the exit
    # code is non-zero, so the scheduler's last result shows it too.
    already = _STATE.get("status") in FINAL
    wrote = False
    with contextlib.suppress(Exception):
        wrote = _publish(
            "HARD_STOP", killed_workers=killed, blas_single_thread=dict(_BLAS), note=_NOTE,
            why=(f"still in phase {phase!r} ({age:.0f}s) at the hard stop, "
                 f"{BUDGET_SEC:.0f}s budget + {GRACE_SEC:.0f}s grace after start"))
    rc = int(_STATE.get("rc") or 0) if already else HARD_STOP_RC
    status = str(_STATE.get("status")) if already else "HARD_STOP"
    with contextlib.suppress(Exception):
        try:
            from research.job_lock import peak_rss_mb, record_peak
        except ModuleNotFoundError:
            from job_lock import peak_rss_mb, record_peak  # type: ignore[no-redef]
        hwm = peak_rss_mb()
        if hwm:
            record_peak("warm_gauntlet_cache", hwm)
    print(f"CacheWarm END status={status} rc={rc} phase={phase} phase_age={age:.0f}s "
          f"elapsed={time.time() - float(_STATE.get('start') or time.time()):.0f}s "
          f"killed_workers={killed} report={'written' if wrote else 'kept'} -- the next "
          f"trigger resumes from the cache", flush=True)
    with contextlib.suppress(Exception):
        sys.stdout.flush()
    os._exit(rc)


def _watchdog() -> None:
    """Heartbeat the in-progress report and enforce the hard stop. Daemon thread."""
    while True:
        hard = float(_STATE.get("hard_stop") or 0.0)
        now = time.time()
        if hard and now >= hard:
            _hard_stop()
            return
        time.sleep(max(1.0, min(HEARTBEAT_SEC, (hard - now) if hard else HEARTBEAT_SEC)))
        if not (hard and time.time() >= hard):
            with contextlib.suppress(Exception):
                _publish("RUNNING")


def start_watchdog(start: float) -> None:
    """Arm the deadline and the hard stop from the process START (admission wait included)."""
    _STATE.update({"start": start, "deadline": start + BUDGET_SEC, "phase": "admission",
                   "phase_since": start, "hard_stop": start + BUDGET_SEC + GRACE_SEC,
                   "status": "RUNNING", "admitted": False})
    threading.Thread(target=_watchdog, name="warm-watchdog", daemon=True).start()


def main() -> int:
    _load_prev_rounds()
    _STATE["admitted"] = True
    # THE PARENT RUNS AT EQUAL, NEVER ABOVE (see PARENT_PRIORITY). It was IDLE, and on a box the
    # miners hold at ~100% its single-threaded docket pass then took longer than the whole budget.
    _STATE["parent_priority"] = _set_priority(PARENT_PRIORITY)
    print(f"  priority: parent {_STATE['parent_priority']}; workers: {EQUAL_WORKERS} at EQUAL, "
          f"the rest at IDLE", flush=True)
    _phase("import")
    import external_gauntlet as G

    meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    _phase("sweep_tmp")
    swept = sweep_orphan_tmps([Path(G.CACHE_DIR), WARM_STATE, REPORT.parent])
    _STATE["orphan_tmp_sweep"] = swept
    print(f"  orphan temp files: {swept}", flush=True)
    _phase("priors")
    try:
        import cell_priority as CP
        priors = CP.measure_priors(BASE)
        print(f"  priors: {priors.n_judged} judged, {priors.n_cured} on the forward-cure route, "
              f"{priors.n_passed} ten-gate pass(es); sources {priors.sources}")
    except Exception as exc:
        print(f"  priors UNMEASURED ({type(exc).__name__}: {exc})")
        priors = None

    deadline = float(_STATE.get("deadline") or (time.time() + BUDGET_SEC))
    rounds: list[dict] = _STATE["rounds"]
    while time.time() < deadline:
        r = run_round(G, meta, priors, deadline)
        rounds.append(r)
        # PUBLISHED EVERY ROUND, not once at exit: `judging_burndown` reads the last round as the
        # warm side of the drain, and a report written only after an hour is an hour stale.
        _publish("RUNNING")
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
    _STATE["rc"] = 0
    _phase("done")
    _publish("DONE", blas_single_thread=dict(_BLAS), note=_NOTE)
    if last:
        print(f"warmed {last.get('warmed')} cell(s) in {last.get('seconds')}s at "
              f"{last.get('cells_per_min')} cells/min with {last.get('workers')} worker(s); "
              f"docket was {last.get('warm_share_before', 0):.1%} warm at the start of the round")
    return 0


#: The BLAS thread decision this process took before numpy loaded (see `_apply_blas_switch`).
_BLAS: dict = {}


def _apply_blas_switch() -> dict:
    """THE SAME BUILD ENVIRONMENT AS THE JUDGE'S PRE-WARM POOL (research/blas_threads.py).

    This job fills the series cache the judge reads, with the judge's own `_warm_one`, and
    `_cache_key` does not carry a BLAS thread count -- so a cell built here at one thread count
    and a cell built by the sweep's pre-warm pool at another would share a key. The switch is
    therefore decided by the ONE function the judge's launcher uses (`blas_threads.apply`, via
    `judging_throughput.apply_env`), here, before `external_gauntlet` imports numpy, and the
    workers this job spawns inherit it. Off, or a proof that does not hold, adds nothing.
    """
    try:
        from research import blas_threads
        applied = blas_threads.apply(os.environ)
        st = blas_threads.status()
        return {"applied": applied, "active": st.get("active"), "why": st.get("why"),
                "in_force": st.get("in_force")}
    except Exception as exc:
        return {"applied": {}, "active": False,
                "why": f"UNMEASURED: switch unreadable ({type(exc).__name__}: {exc})"[:300]}


def _cli_main() -> int:
    # BEFORE ANY IMPORT THAT LOADS NUMPY: BLAS reads its thread count once, at load.
    _BLAS.update(_apply_blas_switch())
    print(f"  blas threads: {'single (proof holds)' if _BLAS.get('active') else 'default'} -- "
          f"{str(_BLAS.get('why'))[:160]}")
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:
        from job_lock import exclusive_job

    # THE CLOCK STARTS NOW, before admission may wait up to 12 minutes, so budget + grace bound
    # the whole process and a run can never outlive its hourly trigger.
    start = time.time()
    start_watchdog(start)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start))
    print(f"CacheWarm START pid={os.getpid()} at {stamp} budget={BUDGET_SEC:.0f}s "
          f"hard_stop=+{BUDGET_SEC + GRACE_SEC:.0f}s", flush=True)
    rc, status = 1, "CRASHED"
    try:
        # The parent's need is what it MEASURED (p75 of its own runs: the docket, ~4.4GB on the
        # trading box), never the unmeasured 900MB it used to declare.
        with exclusive_job("warm_gauntlet_cache", need_mb=parent_need_mb()) as acquired:
            if acquired:
                rc = main()
                status = "DONE" if rc == 0 else f"rc={rc}"
            else:
                rc, status = 75, not_admitted_status()
        return rc
    finally:
        _STATE["rc"] = rc
        if status == "CRASHED":
            with contextlib.suppress(Exception):
                _publish("CRASHED", note=_NOTE)
        print(f"CacheWarm END status={status} rc={rc} "
              f"elapsed={time.time() - start:.0f}s phase={_STATE.get('phase')}", flush=True)


def not_admitted_status() -> str:
    """Why admission said no, and the report it leaves -- never clobbering a live instance's."""
    # v1.1: a run that was not admitted NEVER writes WARM_GAUNTLET.json. Checking the lock and
    # then writing was a race (another instance can take the lock in between); the report belongs
    # to the instance that holds it. The refusal is recorded beside it instead.
    lock = DESK / "data" / ".job_locks" / "warm_gauntlet_cache.json"
    holder = _read_json(lock, {})
    status = (f"REFUSED_DUPLICATE (lock held by pid {holder.get('pid')})"
              if isinstance(holder, dict) and holder.get("pid") else "NOT_ADMITTED")
    with contextlib.suppress(Exception):
        _write_json(NOT_ADMITTED, {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                   "pid": os.getpid(), "status": status,
                                   "why": "see the admission line in MT5-CacheWarm.log"})
    return status


if __name__ == "__main__":
    raise SystemExit(_cli_main())
