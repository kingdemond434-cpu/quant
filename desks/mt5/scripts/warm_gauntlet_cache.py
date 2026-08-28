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
same trim to the last complete day -- but one cell at a time, releasing each before starting the
next, and stopping when the box gets tight. Afterwards the real sweep finds its cells cached and
runs in the cheap regime that was measured working: "Cell cache: 460/460 loaded, 0 to compute".

WHAT IT DELIBERATELY DOES NOT DO

No gates, no verdicts, no report, no trial charge, and it never touches UNIVERSAL_SURVIVORS.json.
It is a COMPUTE cache and nothing else, which is why it is safe to run beside the sweep: nothing
it writes can change a verdict, only how long that verdict takes to reach. Every function it
calls is imported from external_gauntlet rather than reimplemented, so a change to how a series
is built cannot silently drift from what this warms.
"""
from __future__ import annotations

import json
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
#: produces verdicts has to.
FLOOR_MB = 1200

#: Report progress this often. Cheap, and it makes the log a live progress signal rather than a
#: single line at exit -- the blind spot that cost 87 minutes tonight.
REPORT_EVERY = 25


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

    warmed = missing = failed = already = 0
    t0 = time.time()
    for i, spec in enumerate(eligible):
        if i % REPORT_EVERY == 0:
            avail = free_mb()
            if avail is not None and avail < FLOOR_MB:
                print(f"STOPPING at {i}/{len(eligible)}: {avail}MB free, floor is {FLOOR_MB}MB. "
                      f"Warming is optional work and yields the box; the next run resumes from "
                      f"what is already cached.")
                break
            if i:
                print(f"  [{i}/{len(eligible)}] warmed={warmed} cached_already={already} "
                      f"missing_bars={missing} failed={failed} "
                      f"{time.time() - t0:.0f}s free={avail}MB")

        frame = G._h1_for(spec["sym"])
        if frame is None or len(frame) == 0:
            missing += 1
            continue
        last_day = frame.index[-1].normalize()
        ckey = G._cache_key(spec["sym"], spec["family"], spec["params"] or {},
                            str(last_day.date()))
        if G.cache_load(ckey) is not None:
            already += 1
            continue

        obj = None
        try:
            obj = G.build_cell(spec["sym"], spec["family"], spec["params"], meta)
            if not obj:
                failed += 1
                continue
            ds1 = G._series_trim_partial(
                G.daily_series(obj["df"], obj["sigs"], obj["costs"]), last_day)
            costs3 = G.costs_for(spec["sym"], meta, mult=G.COST_SCENARIO)
            ds3 = G._series_trim_partial(
                G.daily_series(obj["df"], obj["sigs"], costs3), last_day)
            if ds1 is None or ds3 is None:
                failed += 1
                continue
            G.cache_save(ckey, ds1, ds3)
            warmed += 1
        except Exception as exc:
            failed += 1
            print(f"  FAIL {spec['sym']}.{spec['family']}: {type(exc).__name__}: {str(exc)[:110]}")
        finally:
            # RELEASE BEFORE THE NEXT CELL. This is the entire point: the signal list is the
            # expensive object, and holding 4,400 of them at once is what does not fit.
            if obj is not None:
                obj["sigs"] = None
                obj["df"] = None
            del obj

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
