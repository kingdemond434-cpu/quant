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

from libs.hypmax.moat_mine import (  # noqa: E402
    MECHANISMS,
    coverage_report,
    extract_all,
)
from libs.hypmax.ontology import load_state, record_outcome, save_state  # noqa: E402

MOAT = ROOT / "data/moat"
COVERAGE = ROOT / "data/moat_coverage.json"
REPORT = ROOT / "data/moat_mine.json"
SERIES = ROOT / "data/moat_series.jsonl"
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
    # asked to drive to 100%.
    grid_results = [{"symbol": k.split("|")[0], "day": k.split("|")[1],
                     "mechanisms": {m: {"n": 1} for m in v.get("mechanisms", [])}}
                    for k, v in filled.items()]
    rep = coverage_report(grid_results, symbols, days)

    degenerate = [f"{r['symbol']}/{m}" for r in results for m, s in r["mechanisms"].items()
                  if int(s.get("n", 0)) > 0 and _dispersion(s) <= _DEGENERATE_CV]
    out = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "run": cov["runs"],
        "cells_mined_this_run": mined,
        "files_read": files_read,
        "seconds": round(time.time() - t0, 1),
        "symbols_on_disk": len(symbols),
        "days_on_disk": len(days),
        "cumulative_coverage": rep,
        "degenerate_series": degenerate[:20],
        "results": results[:40],
        "note": ("hole-first: every run spends its budget on cells NOBODY has measured before "
                 "re-measuring anything. That ordering is what converges on 100% exploration "
                 "instead of re-grinding the most convenient symbol forever."),
    }
    REPORT.write_text(json.dumps(out, indent=1, default=str), "utf-8")

    print(f"moat-mine run {cov['runs']}: {mined} cells, {files_read} files, "
          f"{out['seconds']}s | cumulative coverage {rep['coverage_pct']}% "
          f"({rep['cells_filled']}/{rep['cells_total']}) | holes {rep['holes']}")
    if rep["holes"]:
        print(f"  next targets: {', '.join(rep['next_targets'][:6])}")
    if degenerate:
        print(f"  DEGENERATE (zero dispersion, recorded as barren): {', '.join(degenerate[:6])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
