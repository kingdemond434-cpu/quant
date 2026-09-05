"""Precompute the sweep's per-cell series in BOUNDED batches, so the sweep itself stays cheap.

WHY THIS EXISTS

The gauntlet's memory cost is not a function of how many cells it judges -- it is a function of
how many it must COMPUTE. A cached cell is carried as `{"df": None, "sigs": None}` plus two short
daily series; an uncached one holds a full H1 frame reference and its entire signal list, and
some families emit ~28,000 signals for a single symbol.

That distinction decided tonight's arithmetic. A 460-cell sweep peaked around 2.4GB on a box with
8GB shared with the live MT5 terminal. The docket then grew to 6,270 cells -- correct and wanted,
it is what the bond backfill and the carry repair were for -- and roughly 4,400 of those are
uncached. Scaled naively that sweep does not fit, and the failure mode is the ugly one already
measured tonight: not a crash, but a box thrashing so hard that a process burns 3,447 CPU-seconds
producing nothing while every liveness check reports it healthy.

WHAT THIS DOES INSTEAD

Exactly what the gauntlet does to fill its cache -- same cell identity, same key, same series,
same trim to the last complete day -- but ACROSS SEVERAL PROCESSES, releasing each cell before
starting the next, and stopping when the box gets tight. Afterwards the real sweep finds its
cells cached and runs in the cheap regime that was measured working: "Cell cache: 460/460
loaded, 0 to compute".

Parallel because the measurement demanded it. After 6.6 hours the sweep had cached 2,597 cells of
~6,270 and was still adding about 160 an hour -- another 22 hours -- while using 0.84 of the
box's 4 cores. Cell series are independent and deterministic, so three workers do the same work
in a third of the time, and the fourth core stays free for the sweep and the terminal.

WHAT IT DELIBERATELY DOES NOT DO

No gates, no verdicts, no report, no trial charge, and it never touches UNIVERSAL_SURVIVORS.json.
It is a COMPUTE cache and nothing else, which is why it is safe to run beside the sweep: nothing
it writes can change a verdict, only how long that verdict takes to reach. Every function it
calls is imported from external_gauntlet rather than reimplemented, so a change to how a series
is built cannot silently drift from what this warms.
"""
from __future__ import annotations

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
#: produces verdicts has to.
# Raised, and now measured against the BINDING constraint (min of physical and commit) rather
# than physical alone -- which read 2,705MB free on a box with 234MB of usable virtual memory.
FLOOR_MB = 2500

#: Report progress this often. Cheap, and it makes the log a live progress signal rather than a
#: single line at exit -- the blind spot that cost 87 minutes tonight.
REPORT_EVERY = 25

#: WORKERS. The desk box has 4 cores and the sweep uses 0.84 of one -- measured 2026-08-28, after
#: 6.6 hours it had cached 2,597 cells of ~6,270 and was still adding roughly 160 an hour, which
#: is another 22 hours of wall-clock for work that three idle cores could have absorbed. Cell
#: series are INDEPENDENT and deterministic, so this parallelises exactly: each worker computes
#: whole cells and writes them to the same content-addressed cache the sweep reads.
#: Three, not four: one core stays for the sweep itself and the live terminal. A warmer that
#: starves the thing it is trying to help is not help.
# TWO, not three. Under Windows spawn each worker is a FULL re-import of pandas, numpy and the
# gauntlet module, and each reserves commit accordingly. Measured 2026-08-29: three workers held
# 12.9GB of COMMIT between them -- with working sets of 8-23MB, entirely paged out -- and
# exhausted a 12,756MB page file, after which nothing on the box could allocate at all and the
# sweep died importing pandas. The cores were never the scarce resource here; commit was.
WORKERS = int(os.environ.get("WARM_WORKERS", "2"))

#: Warm from the END of the eligible list backwards. The sweep walks it forwards, so the two meet
#: in the middle instead of recomputing the same cells in the same order. The cache makes overlap
#: harmless but not free, and this makes it rare.
REVERSE = True


#: Set once per worker process by `_init`, so the universe registry is not pickled per cell.
_META: dict | None = None


def _init(meta: dict) -> None:
    global _META
    _META = meta


def _warm_one(spec: dict) -> str:
    """Compute and cache ONE cell's 1x and 3x daily series. Returns a one-word outcome.

    Runs in a worker process, so it must be importable at module level (Windows spawns rather
    than forks). Every function it calls comes from external_gauntlet, so the series it writes
    are the ones the sweep would have computed itself -- same identity, same key, same trim.
    """
    import external_gauntlet as G

    meta = _META or {}
    obj = None
    try:
        frame = G._h1_for(spec["sym"])
        if frame is None or len(frame) == 0:
            return "missing"
        last_day = frame.index[-1].normalize()
        ckey = G._cache_key(spec["sym"], spec["family"], spec["params"] or {},
                            str(last_day.date()))
        if G.cache_load(ckey) is not None:
            return "already"
        obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
        if not obj:
            return "failed"
        ds1 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
        costs3 = G.costs_for(spec["sym"], meta, mult=G.COST_SCENARIO)
        ds3 = G._series_trim_partial(
            G.daily_series(obj["df"], obj["sigs"], costs3), last_day)
        if ds1 is None or ds3 is None:
            return "failed"
        G.cache_save(ckey, ds1, ds3)
        return "warmed"
    except Exception:
        return "failed"
    finally:
        if obj is not None:
            obj["sigs"] = None
            obj["df"] = None


def main() -> int:
    import external_gauntlet as G
    from research.job_lock import free_mb

    meta = json.loads((G.UNI / "universe.json").read_text("utf-8"))
    surv_file = G.HYP / "external_survivors.json"
    if not surv_file.exists():
        print("no docket to warm")
        return 0
    survivors = json.loads(surv_file.read_text("utf-8"))

    # Identical de-duplication to the sweep's: same key, so the same set of cells.
    cells: dict[str, dict] = {}
    for h in survivors:
        sym, fam = h.get("symbol"), h.get("family")
        if not sym or not fam:
            continue
        key = f"{sym}.{fam}.{json.dumps(h.get('params', {}), sort_keys=True)}"
        cells.setdefault(key, {
            "sym": sym, "family": fam, "params": h.get("params", {}),
            "mechanism_status": h.get("mechanism_status"),
            "mechanism_note": h.get("mechanism_note"),
        })

    eligible, rejected = G.partition_at_economic_prior(list(cells.values()))
    print(f"docket {len(survivors)} rows -> {len(cells)} cells -> {len(eligible)} eligible "
          f"({len(rejected)} rejected at the economic prior, as the sweep would)")

    order = list(reversed(eligible)) if REVERSE else list(eligible)
    counts = {"warmed": 0, "already": 0, "missing": 0, "failed": 0}
    t0 = time.time()
    stopped = False

    # chunksize=1 so a worker cannot sit on a queue of cells while the pool is being shut down,
    # and so the memory check below can act promptly.
    with Pool(processes=max(1, WORKERS), initializer=_init, initargs=(meta,)) as pool:
        it = pool.imap_unordered(_warm_one, order, chunksize=1)
        for i, outcome in enumerate(it, 1):
            counts[outcome] = counts.get(outcome, 0) + 1
            if i % REPORT_EVERY:
                continue
            avail = free_mb()
            if avail is not None and avail < FLOOR_MB:
                print(f"STOPPING at {i}/{len(order)}: {avail}MB free, floor is {FLOOR_MB}MB. "
                      f"Warming is optional work and yields the box; the next run resumes from "
                      f"what is already cached.")
                pool.terminate()
                stopped = True
                break
            rate = i / max(1e-9, time.time() - t0) * 60.0
            print(f"  [{i}/{len(order)}] warmed={counts['warmed']} "
                  f"cached_already={counts['already']} missing_bars={counts['missing']} "
                  f"failed={counts['failed']} {time.time() - t0:.0f}s "
                  f"{rate:.0f} cells/min free={avail}MB")

    warmed, already = counts["warmed"], counts["already"]
    missing, failed = counts["missing"], counts["failed"]
    if stopped:
        print("  (stopped early on the memory floor -- progress is cached and resumable)")
    print(f"warmed {warmed} cell(s) in {time.time() - t0:.0f}s "
          f"(already cached {already}, missing bars {missing}, failed {failed}); "
          f"the next sweep loads these instead of computing them")
    return 0


def _cli_main() -> int:
    try:
        from research.job_lock import exclusive_job
    except ModuleNotFoundError:
        from job_lock import exclusive_job

    # Modest: cells are released as they are warmed, so the working set is one cell plus the
    # bounded H1 frame cache -- not the whole docket.
    with exclusive_job("warm_gauntlet_cache", need_mb=900) as acquired:
        return main() if acquired else 75


if __name__ == "__main__":
    raise SystemExit(_cli_main())
