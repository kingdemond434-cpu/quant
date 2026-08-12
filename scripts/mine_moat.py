#!/usr/bin/env python3
"""THE DEDICATED MOAT MINER -- maximum cadence, hole-first, coverage as the product.

WHY A DEDICATED ORGAN AND NOT ANOTHER CADENCE STEP. The desk's own information-advantage ranking
puts self-recorded order books at 1.03 and the next-best source at 0.37. It is the ONLY asset here
that cannot be bought, scraped or replicated: a competitor can point a recorder at Bybit tomorrow,
but they cannot have OUR snapshots from last month, and the archive only grows. That asset sat at
0.4% exploitation with ZERO mechanisms tested while every other organ on this desk was maximised.
moat_audit.py validates the mine; run_cost_model.py reads a slice of it for one purpose. Nothing
EXTRACTS from it. This does, every cycle, forever.

HOLE-FIRST SCHEDULING IS THE WHOLE DESIGN. Coverage is persisted across runs in
data/moat_coverage.json, so each run mines the (venue, symbol, day, mechanism) cells NOBODY HAS
EVER MEASURED before it re-measures anything -- which is what makes repeated max-cadence runs
converge on 100% exploration instead of re-grinding the same convenient BTCUSDT hour forever.
When the holes are gone the budget rolls onto the STALEST covered cells, so the grid never stops
refreshing. Breadth (every venue x symbol) and depth (every mechanism x day) are the same loop.

WHAT COUNTS AS COVERED, AND THE RULE IS STRICT. A cell is covered only when a mechanism produced
at least one FINITE observation there. A run that touched a cell and measured nothing leaves it
open. Otherwise "100%" would mean "we ran everywhere" rather than "we measured everywhere", and
the frontier would retire ground nobody ever actually looked at -- the difference between "mined
and empty" and "never looked", which demand opposite responses.

NO PROMOTION AUTHORITY. This measures and records. Nothing here can pre-register a mechanism,
promote a hypothesis or move a gate; survivors go to the funnel like everything else. A degenerate
series (zero dispersion) is recorded as a FAILED attempt against the ontology region it came from,
because a constant is not a signal -- and that failure is the update that turns unexplored ground
into known-barren ground.

Read-only over data/moat. Writes only its own artifacts. No network, no keys, no order paths.
"""
from __future__ import annotations

import contextlib
import gzip
import json
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.doctrine.allocate import meta_learning_rate  # noqa: E402
from libs.hypmax.moat_mine import (  # noqa: E402
    MECHANISMS,
    coverage_report,
    extract_all,
)
from libs.hypmax.ontology import load_state, record_outcome, save_state  # noqa: E402
from libs.ops.disk import days_to_pause, tape_bytes  # noqa: E402

MOAT = ROOT / "data/moat"
COVERAGE = ROOT / "data/moat_coverage.json"
REPORT = ROOT / "data/moat_mine.json"
SERIES = ROOT / "data/moat_series.jsonl"
#: Coverage percentage over time, one line per run. THE ARTIFACT THAT MAKES P26 CHECKABLE: the
#: breach is the gap NOT CLOSING, and "closing" is invisible in any single snapshot -- 1.2% today
#: is a triumph after 0.5% yesterday and a scandal after 1.2% for a week. Kept separate from
#: moat_series.jsonl, which records per-cell measurements rather than the chase.
HISTORY = ROOT / "data/moat_coverage_history.jsonl"
ONTOLOGY_STATE = ROOT / "data/ontology_state.json"

#: Files read per run. Max cadence means "runs constantly", not "reads 4.4GB every time" -- an
#: organ that takes an hour gets switched off the first time it delays the cycle, and an organ
#: that is switched off has zero coverage. Budgeted work every cycle beats heroic work never.
FILE_BUDGET = int(os.environ.get("MOAT_FILE_BUDGET") or 60)
WALL_BUDGET_S = 240.0
ROWS_PER_FILE = 4000          # depth rows are ~10% of a mixed file; this is a deep sample

#: mechanism -> the ontology question its evidence bears on. A measurement that updates no
#: frontier region is a number in a file; this is what makes mining move the search space.
_QUESTION = {
    "withdrawal_rate": "EXEC.2",          # where is liquidity HIDDEN
    "replenishment_halflife": "EXEC.2",
    "book_slope": "EXEC.3",               # where is queue priority exploitable
    "imbalance": "STRUCT.1",
    "microprice_gap": "STRUCT.1",
    "effective_spread": "EXEC.9",         # which execution costs remain UNMODELLED
    "resting_stability": "EXEC.3",
}

#: A series whose dispersion is below this carries no information no matter how many observations
#: back it: a constant cannot separate two states of the world. Recorded as a FAILED attempt --
#: negative knowledge, which is the update that turns unexplored ground into known-barren ground.
_DEGENERATE_CV = 1e-6


def _cells_on_disk() -> dict[tuple[str, str], list[Path]]:
    """(venue/symbol, day) -> hourly files. Both recorder layouts live under data/moat/<venue>/."""
    out: dict[tuple[str, str], list[Path]] = defaultdict(list)
    if not MOAT.exists():
        return out
    for venue in sorted(p for p in MOAT.iterdir() if p.is_dir()):
        for symdir in sorted(p for p in venue.iterdir() if p.is_dir()):
            for f in symdir.glob("*.jsonl.gz"):
                day = f.stem.split("_")[0]
                if len(day) == 8 and day.isdigit():
                    out[(f"{venue.name}/{symdir.name}", day)].append(f)
    return out


def _read(files: list[Path], cap: int) -> list[dict]:
    """Parse up to `cap` rows across a day's hourly files. A corrupt line is skipped, never
    guessed at: a fabricated book is worse than a missing one because it cannot be detected
    downstream."""
    rows: list[dict] = []
    for f in sorted(files):
        try:
            with gzip.open(f, "rt", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                    if len(rows) >= cap:
                        return rows
        except OSError:
            continue
    return rows


def _load_coverage() -> dict:
    try:
        return json.loads(COVERAGE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"filled": {}, "runs": 0}


def _schedule(cells: dict, cov: dict) -> list[tuple[tuple[str, str], list[Path]]]:
    """HOLES FIRST, then the stalest. This ordering IS the convergence to 100%.

    Ranked by how many of the seven mechanisms a cell still owes, so a cell measured on two
    mechanisms outranks one measured on six, and a virgin cell outranks both. Without this the
    miner re-grinds whichever symbol sorts first and coverage plateaus at the width of one run.
    """
    filled = cov.get("filled", {})
    scored = []
    for key, files in cells.items():
        ck = f"{key[0]}|{key[1]}"
        have = set(filled.get(ck, {}).get("mechanisms", []))
        owed = len(MECHANISMS) - len(have & set(MECHANISMS))
        last = float(filled.get(ck, {}).get("t", 0.0))
        scored.append((-owed, last, key, files))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [(k, f) for _, _, k, f in scored]


def _dispersion(summary: dict) -> float:
    """Coefficient of variation, guarded. Scalars have no dispersion by construction and are
    judged on being finite at all."""
    if "value" in summary:
        return 1.0
    mean, std = abs(float(summary.get("mean", 0.0))), float(summary.get("std", 0.0))
    return std / max(mean, 1e-12) if mean > 0 else (1.0 if std > 0 else 0.0)


def _tape_from_cells(cells: dict[tuple[str, str], list[Path]]) -> tuple[int, int]:
    """Tape size from the file list the scheduler already built -- no second directory walk.

    Counts exactly the MINEABLE tape (files the scheduler recognises) rather than everything under
    data/moat, which is the more useful denominator anyway: a stray file the miner cannot read is
    not archive growth.
    """
    total = files = 0
    for paths in cells.values():
        for p in paths:
            try:
                total += p.stat().st_size
            except OSError:
                continue
            files += 1
    return total, files


def closure(rep: dict, run: int, tape_stats: tuple[int, int] | None = None) -> dict:
    """THE RATE, NOT ONLY THE LEVEL (P18) -- and it is what makes P26 checkable at all.

    The constitution says under-exploration is a breach and that the breach is the gap NOT
    CLOSING. Those two states are indistinguishable in a snapshot: 1.2% coverage is a triumph the
    day after 0.5% and a scandal after a week at 1.2%. So coverage is appended every run and the
    slope is measured over the recorded history with its own standard error, exactly as the
    allocator measures instrumentation closure.

    TWO SERIES, NOT ONE, AND THE SECOND IS THE SUBTLE ONE. The grid GROWS every second the
    recorders run, so cells_filled can climb hard while coverage_pct stands still or falls. Those
    are opposite diagnoses -- "nobody is mining" is neglect and the desk's own fault, while
    "mining slower than recording" is a throughput shortfall whose fix is more miner, not more
    attention -- and trending only the percentage would report the second as the first and send
    the desk chasing a motivation problem it does not have.

    The ETA is deliberately derived from the PERCENTAGE slope rather than the cell slope, because
    the percentage already nets out grid growth. An ETA computed from cells filled per run would
    quietly assume a frozen archive and promise a date that recording pushes back every day.
    """
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    # ONE WALK, NOT TWO. main() has already enumerated every tape file to build the schedule, so
    # re-walking the archive here doubled the cost of the one operation that grows without bound
    # by design -- 0.3s today at 23k files, 2.3s at the 190k this rate reaches in three months,
    # every pass, forever. The caller passes what it already knows; the fallback keeps this
    # function callable on its own, which is what its tests exercise.
    tape, files = tape_stats if tape_stats is not None else tape_bytes(MOAT)
    row = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "run": run,
        "coverage_pct": float(rep.get("coverage_pct", 0.0)),
        "cells_filled": int(rep.get("cells_filled", 0)),
        "cells_total": int(rep.get("cells_total", 0)),
        "holes": int(rep.get("holes", 0)),
        # THE DENOMINATOR'S SOURCE, RECORDED ALONGSIDE THE RATIO. Coverage is filled/total, and
        # total only grows while the recorders write. If they pause -- on disk, on a rate cap, on
        # a crash -- the denominator freezes and coverage races to 100% while the asset stops
        # accumulating. Without this field that reads as the finish line.
        "tape_bytes": tape,
        "tape_files": files,
    }
    with HISTORY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")

    hist: list[dict] = []
    try:
        hist = [json.loads(x) for x in HISTORY.read_text("utf-8").strip().splitlines() if x][-200:]
    except (OSError, json.JSONDecodeError, ValueError):
        hist = [row]

    pct_rate = meta_learning_rate([float(h.get("coverage_pct", 0.0)) for h in hist])
    cell_rate = meta_learning_rate([float(h.get("cells_filled", 0)) for h in hist])

    # Wall clock per run, measured rather than assumed -- the cadence floor and the continuous
    # loop differ by orders of magnitude and an ETA in "runs" is unusable to a human either way.
    span_s = 0.0
    if len(hist) >= 2:
        with contextlib.suppress(ValueError, TypeError):
            t_first = datetime.fromisoformat(str(hist[0]["ts"]))
            t_last = datetime.fromisoformat(str(hist[-1]["ts"]))
            span_s = max(0.0, (t_last - t_first).total_seconds()) / max(1, len(hist) - 1)

    pct = row["coverage_pct"]
    eta_runs = eta_hours = None
    if pct_rate.get("improving") and float(pct_rate.get("rate", 0.0)) > 0:
        eta_runs = round((100.0 - pct) / float(pct_rate["rate"]), 1)
        if span_s > 0:
            eta_hours = round(eta_runs * span_s / 3600.0, 1)

    # IS THE ASSET STILL GROWING? Checked BEFORE any verdict about coverage, because a frozen
    # tape invalidates every one of them. Over the recorded span rather than run-to-run: the
    # recorders flush on their own schedule, so a single pass can legitimately see no change.
    tape_growth = 0
    if len(hist) >= 2:
        tape_growth = int(hist[-1].get("tape_bytes", 0)) - int(hist[0].get("tape_bytes", 0))
    bytes_per_day = ((tape_growth / (span_s * max(1, len(hist) - 1))) * 86400.0
                     if span_s > 0 and tape_growth > 0 else 0.0)
    disk = days_to_pause(bytes_per_day)
    recording_stopped = (len(hist) >= 4 and tape_growth <= 0 and row["tape_bytes"] > 0)

    if recording_stopped:
        # THE FALSE WIN, REFUSED. Coverage still rises here -- the miner keeps closing holes in a
        # grid that has stopped growing -- and reporting that as CLOSING would hand the desk a
        # green number for the exact event that ends the asset. The verdict is about the tape.
        return {
            "state": "RECORDING-STOPPED",
            "why": (f"the tape has not grown in {len(hist)} runs ({row['tape_files']} files, "
                    f"{row['tape_bytes'] / 1e9:.2f} GB, unchanged). Coverage may still be rising "
                    "-- the miner is closing holes in a FROZEN grid -- and that is not progress, "
                    "it is the denominator dying. Check the recorders before reading any coverage "
                    f"number: {disk.get('note', '')}"),
            "coverage_pct": pct,
            "coverage_is_meaningful": False,
            "pct_per_run": pct_rate,
            "cells_per_run": cell_rate,
            "tape_bytes": row["tape_bytes"],
            "tape_growth_bytes": tape_growth,
            "disk": disk,
            "seconds_per_run": round(span_s, 1),
            "runs_to_100": None,
            "hours_to_100": None,
            "eta_note": "no ETA is offered while the grid is frozen -- it would be a fake date.",
        }

    if pct >= 100.0:
        state, why = "COMPLETE-FOR-THIS-GRID", (
            "every cell of the CURRENT grid is measured. The grid grows every second the recorders "
            "run, so this is arrival at the next constraint, not a finish line (P20).")
    elif pct_rate.get("improving"):
        state, why = "CLOSING", (
            f"coverage is rising {pct_rate['rate']:.3f} pp/run (se {pct_rate['se']:.3f}, "
            f"n={pct_rate['n']}) -- work in progress, not a breach.")
    elif cell_rate.get("improving"):
        state, why = "OUTPACED-BY-RECORDING", (
            f"cells measured are rising {cell_rate['rate']:.2f}/run but coverage is NOT -- the "
            "miner is working and the grid is growing faster than it mines. This is a throughput "
            "shortfall, not neglect: the fix is more miner (lower --interval, more parallel "
            "passes, more files per run), never more attention.")
    elif pct_rate.get("state") == "INSUFFICIENT-HISTORY":
        state, why = "UNKNOWN", (
            f"only {pct_rate['n']} recorded run(s) -- a rate from fewer than 3 points is a slope "
            "through noise. The number is not yet a finding either way.")
    else:
        state, why = "STANDING-STILL", (
            f"coverage is not distinguishable from flat over {pct_rate.get('n', 0)} runs and "
            "neither is the cell count. This is the P26 breach in its pure form: edge the desk "
            "has already paid to record and is declining to collect.")

    return {
        "state": state,
        "why": why,
        "coverage_pct": pct,
        "coverage_is_meaningful": True,
        "pct_per_run": pct_rate,
        "cells_per_run": cell_rate,
        "tape_bytes": row["tape_bytes"],
        "tape_growth_bytes": tape_growth,
        # WHEN THE TAPE STOPS, not whether there is space. Carried in the miner's artifact
        # because this is the organ that reads the archive every pass -- it is the cheapest place
        # on the desk to notice that the archive has a deadline.
        "disk": disk,
        "seconds_per_run": round(span_s, 1),
        "runs_to_100": eta_runs,
        "hours_to_100": eta_hours,
        "eta_note": (
            "derived from the PERCENTAGE slope, which already nets out grid growth. An ETA from "
            "cells-per-run would assume a frozen archive and promise a date that recording pushes "
            "back every day."),
    }


def main() -> int:
    t0 = time.time()
    cells = _cells_on_disk()
    cov = _load_coverage()
    filled: dict = cov.get("filled", {})

    if not cells:
        # HONEST EMPTY, LOUDLY. The recorders write to data/moat and data/ is not in git, so a
        # fresh checkout has no mine. Reporting 0.0% coverage with the reason named is the
        # correct output; inventing cells or exiting 0 in silence is how a dark organ passes
        # for a working one for six weeks.
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({
            "ts": datetime.now(tz=UTC).isoformat(),
            "state": "NO MINE ON DISK",
            # BLOCKED, not "waiting": the fix is a named process that must run elsewhere, and
            # nothing this organ can do closes it.
            "hole_tier": "BLOCKED",
            "hole_fix": ("start run_recorder.py / run_recorder_spot.py / run_recorder_bybit.py. "
                         "No mining action closes this -- every unrecorded second is permanently "
                         "unbuyable, so the blocker is the recorders and nothing else."),
            "cycles_open": 0,
            "next_ceiling": ("record anything at all; then close the resulting holes hole-first; "
                             "then note the grid GROWS every day the recorders run"),
            "coverage_pct": 0.0,
            "reason": f"{MOAT} absent or empty -- the recorders have written nothing here. "
                      "Coverage is 0.0% and that is a measurement, not a failure of this run.",
            "next": "start run_recorder.py / run_recorder_spot.py / run_recorder_bybit.py; "
                    "every unrecorded second is permanently unbuyable at any price",
        }, indent=1), "utf-8")
        print("moat-mine: NO MINE ON DISK -- data/moat empty. coverage 0.0%. "
              "recorders are the blocker, not this miner.")
        return 0

    order = _schedule(cells, cov)
    symbols = sorted({k[0] for k in cells})
    days = sorted({k[1] for k in cells})

    results, mined = [], 0
    files_read = 0
    for (sym, day), files in order:
        if files_read >= FILE_BUDGET or time.time() - t0 > WALL_BUDGET_S:
            break
        take = files[: max(1, FILE_BUDGET - files_read)]
        rows = _read(take, ROWS_PER_FILE)
        files_read += len(take)
        r = extract_all(sym, rows) | {"day": day, "files": len(take)}
        results.append(r)
        mined += 1

        ck = f"{sym}|{day}"
        cell = filled.setdefault(ck, {"mechanisms": [], "t": 0.0})
        for mech, s in r["mechanisms"].items():
            if int(s.get("n", 0)) > 0 and mech not in cell["mechanisms"]:
                cell["mechanisms"].append(mech)
        cell["t"] = time.time()

    # ---- ontology update: every mechanism measured is an attempt on the region it bears on.
    state = load_state(ONTOLOGY_STATE)
    for r in results:
        for mech, s in r["mechanisms"].items():
            q = _QUESTION.get(mech)
            if not q or int(s.get("n", 0)) == 0:
                continue
            record_outcome(state, q, survived=_dispersion(s) > _DEGENERATE_CV)
    save_state(ONTOLOGY_STATE, state)

    # ---- append the measured series summaries. Append-only: the moat's value is that it
    # accumulates, and a file that gets overwritten each run has no history to accumulate.
    SERIES.parent.mkdir(parents=True, exist_ok=True)
    with SERIES.open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({"ts": datetime.now(tz=UTC).isoformat(), **r},
                                separators=(",", ":")) + "\n")

    cov["filled"], cov["runs"] = filled, int(cov.get("runs", 0)) + 1
    COVERAGE.write_text(json.dumps(cov, indent=1), "utf-8")

    # Cumulative coverage across every run ever, not just this one -- the number the principal
    # asked to drive to 100%. The universe is the cells that EXIST on tape (pairs=), not the
    # symbols x days cartesian product: measured 2026-08-12, the product manufactured 11,004
    # phantom holes for (symbol, day) pairs never recorded, pinning coverage at 53.05%
    # STANDING-STILL while every real cell was 7/7 measured. Phantoms remain published in the
    # report as phantom_pairs_excluded -- visible, never counted as unmined edge.
    grid_results = [{"symbol": k.split("|")[0], "day": k.split("|")[1],
                     "mechanisms": {m: {"n": 1} for m in v.get("mechanisms", [])}}
                    for k, v in filled.items()]
    rep = coverage_report(grid_results, symbols, days, pairs=list(cells.keys()))

    degenerate = [f"{r['symbol']}/{m}" for r in results for m, s in r["mechanisms"].items()
                  if int(s.get("n", 0)) > 0 and _dispersion(s) <= _DEGENERATE_CV]
    closing = closure(rep, int(cov["runs"]), tape_stats=_tape_from_cells(cells))
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "run": cov["runs"],
        "cells_mined_this_run": mined,
        "files_read": files_read,
        "seconds": round(time.time() - t0, 1),
        "symbols_on_disk": len(symbols),
        "days_on_disk": len(days),
        "cumulative_coverage": rep,
        # P18/P26. The level alone cannot say whether the gap is closing, and the breach is the
        # gap NOT closing -- so the rate ships in the artifact rather than being reconstructed by
        # whoever reads it, and check_under_exploration decides on THIS field.
        "closure": closing,
        "degenerate_series": degenerate[:20],
        "results": results[:40],
        # P20, ZERO CEILING. 100% coverage of the current grid is not completion -- it is arrival
        # at the next constraint, and naming it here is what stops this organ going quiet on the
        # day it turns green. The archive grows every second the recorders run, so the grid it is
        # measured against grows too.
        # P25, DETECT IMPLIES REPAIR. A hole is a defect in coverage, not a status line: it is
        # PATCH_READY because the miner itself closes it on a later run, and the age counter is
        # what stops a permanently-unreachable cell reading as a fresh finding every morning.
        "hole_tier": ("PATCH_READY" if rep["holes"] else "NONE"),
        "hole_fix": ("this miner closes these itself, hole-first, on subsequent runs -- no other "
                     "action is required unless a cell's age stops falling, which means its files "
                     "are unreadable rather than unmined"
                     if rep["holes"] else ""),
        "cycles_open": cov.get("runs", 0),
        "next_ceiling": (
            "close the remaining holes; then note that the grid itself GROWS every day the "
            "recorders run, so 100% is a moving target rather than a finish line; then raise "
            "resolution -- more mechanisms per cell and finer time buckets -- because the seven "
            "reconstructions here are the first seven, not the last."),
        "note": ("hole-first: every run spends its budget on cells NOBODY has measured before "
                 "re-measuring anything. That ordering is what converges on 100% exploration "
                 "instead of re-grinding the most convenient symbol forever."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"moat-mine run {cov['runs']}: {mined} cells, {files_read} files, "
          f"{out['seconds']}s | cumulative coverage {rep['coverage_pct']}% "
          f"({rep['cells_filled']}/{rep['cells_total']}) | holes {rep['holes']}")
    eta = ("" if closing["hours_to_100"] is None
           else f" | ETA 100% ~{closing['hours_to_100']}h ({closing['runs_to_100']} runs)")
    print(f"  closure {closing['state']}{eta}")
    if closing["state"] in ("STANDING-STILL", "OUTPACED-BY-RECORDING", "RECORDING-STOPPED"):
        print(f"  {closing['why']}")
    _disk = closing.get("disk", {})
    if _disk.get("state") in ("URGENT", "PAUSED"):
        print(f"  DISK {_disk['state']}: {_disk['note']}")
    if rep["holes"]:
        print(f"  next targets: {', '.join(rep['next_targets'][:6])}")
    if degenerate:
        print(f"  DEGENERATE (zero dispersion, recorded as barren): {', '.join(degenerate[:6])}")
    return 0


def loop(interval_s: float = 0.0) -> int:
    """RUN FOREVER. The dedicated 24/7 miner, not a cadence step.

    WHY BOTH EXIST. The cadence call guarantees the miner runs at all -- it is the floor. This
    loop is the CEILING: it mines continuously, so coverage converges in hours rather than in as
    many days as there are cadence cycles. Under-exploration of owned data is a constitutional
    breach (P26), and "we mine it once a day" is under-exploration when the archive grows every
    second and nothing but wall-clock stops the miner going faster.

    Each pass is budgeted exactly as the single-shot run is, so a long loop can never monopolise
    the box; `interval_s` is a courtesy gap for disk, not a throttle on exploration. Zero means
    back-to-back, which is the correct default: the constraint that should bind is I/O, never a
    number somebody picked.

    Exits only on interrupt. A crash in one pass is logged and the loop continues -- a miner that
    dies on one unreadable file has stopped exploring, which is the failure it exists to prevent.
    """
    passes, t_start = 0, time.time()
    print(f"moat-miner: CONTINUOUS mode, interval {interval_s}s (0 = back-to-back)")
    while True:
        passes += 1
        try:
            main()
        except KeyboardInterrupt:
            break
        except Exception as e:                     # one bad pass must never end the exploration
            print(f"moat-miner: pass {passes} failed ({type(e).__name__}: {e}) -- continuing")
        if interval_s > 0:
            time.sleep(interval_s)
    print(f"moat-miner: stopped after {passes} pass(es), "
          f"{(time.time() - t_start) / 3600:.1f}h")
    return 0


if __name__ == "__main__":
    if "--loop" in sys.argv:
        _iv = 0.0
        if "--interval" in sys.argv:
            _iv = float(sys.argv[sys.argv.index("--interval") + 1])
        raise SystemExit(loop(_iv))
    raise SystemExit(main())
