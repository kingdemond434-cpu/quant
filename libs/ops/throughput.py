"""PER-STAGE THROUGHPUT, MEASURED ON A CLOCK AND RATCHETED UP.

THE NUMBER THAT MADE THIS FILE. On 2026-09-23 the desk's canonical write door
(`proposer_common._record_in_registry`) was measured at FOUR ROWS PER SECOND: a 10,005-row
donation was still writing forty minutes later, and four rows a second is 345,600 rows a day at
a 100% duty cycle, so the principal's target of millions of breadth cells minted and judged per
day was arithmetically out of reach and nothing in the desk said so. Two causes, both invisible
because no organ published a rate: `discoveries.content_hash` had no index (a 231.9 ms table
scan on every write) and every row paid three WAL commits.

The lesson is not either defect. It is that a throughput ceiling is the one kind of defect that
leaves no failing artifact -- every row still lands, every gate still passes, the desk simply
does less per hour than anyone believes. So the rate itself becomes an artifact here, per stage,
with a high-water mark that only ever rises. A stage that slows down fails a fence instead of
quietly costing the desk a decimal place.

THIS NEVER CAPS ANYTHING. It counts rows and seconds and divides. No stage is throttled, no row
is deferred, nothing is queued: `record()` appends one line and returns.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
SAMPLES: Path = DESK / "data" / "throughput_samples.jsonl"
REPORT: Path = DESK / "reports" / "THROUGHPUT.json"

#: The chain, in the order a cell travels it. A stage with no sample is UNMEASURED, which is a
#: verdict and never a zero (L1.28a).
STAGES: tuple[str, ...] = ("mint", "registry_write", "compile", "judge")

#: A measured rate may fall this far below the stage's high-water mark before it is a
#: REGRESSION. Generous on purpose: the fence exists to catch a 24x fall like the missing index,
#: not to flap on a noisy sample. Throughput is a ratchet -- the mark itself only ever rises.
REGRESSION_TOLERANCE = 0.5
#: Samples smaller than this measure process startup, not throughput, so they set no mark.
MIN_ROWS_FOR_MARK = 50
#: The window the published rate is computed over.
WINDOW_HOURS = 24.0


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def record(stage: str, rows: int, seconds: float, detail: dict[str, Any] | None = None) -> None:
    """Append one measured (rows, seconds) sample. NEVER raises and never blocks the caller:
    a measurement that can break the organ it measures is worse than no measurement."""
    try:
        if rows <= 0 or seconds <= 0:
            return
        line = json.dumps({"at": _now(), "stage": str(stage), "rows": int(rows),
                           "seconds": round(float(seconds), 4),
                           "rows_per_s": round(rows / seconds, 2),
                           "pid": os.getpid(), "detail": detail or {}}, default=str)
        SAMPLES.parent.mkdir(parents=True, exist_ok=True)
        with SAMPLES.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        # LOUD, NOT SILENT (2026-09-23 swallowed-write audit). Still never raises and still never
        # blocks the caller, exactly as the docstring promises -- it just stops being the ninth
        # place where a sample that never landed is indistinguishable from a sample not taken.
        print(f"throughput: sample for {stage!r} NOT written ({type(exc).__name__}: {exc})",
              flush=True)
        return


@contextmanager
def measured(stage: str, rows: int, detail: dict[str, Any] | None = None) -> Iterator[None]:
    """Time a block and record it as `stage`. The row count is what the caller is about to do."""
    t0 = time.perf_counter()
    try:
        yield
    finally:
        record(stage, rows, time.perf_counter() - t0, detail)


def samples(window_hours: float = WINDOW_HOURS,
            path: Path | None = None) -> list[dict[str, Any]]:
    """Every sample inside the window. An unreadable line is skipped, never fatal."""
    src = path or SAMPLES
    if not src.exists():
        return []
    cut = datetime.now(tz=UTC) - timedelta(hours=window_hours)
    out: list[dict[str, Any]] = []
    for raw in src.read_text("utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
            at = datetime.fromisoformat(str(row["at"]))
        except (ValueError, KeyError, TypeError):
            continue
        if at >= cut:
            out.append(row)
    return out


def _stage_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_rows = sum(int(r.get("rows") or 0) for r in rows)
    total_s = sum(float(r.get("seconds") or 0.0) for r in rows)
    rates = [float(r["rows_per_s"]) for r in rows if r.get("rows_per_s")]
    big = [float(r["rows_per_s"]) for r in rows
           if r.get("rows_per_s") and int(r.get("rows") or 0) >= MIN_ROWS_FOR_MARK]
    if total_s <= 0:
        return {"status": "UNMEASURED", "why": "no sample carried a positive duration"}
    rate = total_rows / total_s
    return {"status": "MEASURED", "n_samples": len(rows), "rows": total_rows,
            "seconds": round(total_s, 2), "rows_per_s": round(rate, 2),
            "median_sample_rows_per_s": round(statistics.median(rates), 2) if rates else None,
            "best_sample_rows_per_s": round(max(big), 2) if big else None,
            "rows_per_day_at_100pct": int(rate * 86400)}


def summarise(window_hours: float = WINDOW_HOURS, path: Path | None = None) -> dict[str, Any]:
    """Per-stage measured rate over the window, and which stage binds the chain."""
    rows = samples(window_hours, path)
    by: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by.setdefault(str(r.get("stage") or "unknown"), []).append(r)
    stages: dict[str, Any] = {}
    for st in (*STAGES, *sorted(set(by) - set(STAGES))):
        stages[st] = (_stage_stats(by[st]) if by.get(st)
                      else {"status": "UNMEASURED",
                            "why": f"no {st} sample inside {window_hours}h"})
    measured_rates = {k: v["rows_per_day_at_100pct"] for k, v in stages.items()
                      if v.get("status") == "MEASURED"}
    binding = min(measured_rates, key=lambda k: measured_rates[k]) if measured_rates else None
    return {"at": _now(), "window_hours": window_hours, "stages": stages,
            "binding_stage": binding,
            "chain_rows_per_day": measured_rates.get(binding) if binding else None,
            "unmeasured_stages": [k for k, v in stages.items()
                                  if v.get("status") != "MEASURED"],
            "rule": "the chain runs at its slowest MEASURED stage; an UNMEASURED stage is a "
                    "verdict, not a zero, and the chain rate below is an UPPER bound while one "
                    "remains"}


def _previous(report: Path) -> dict[str, Any]:
    try:
        return dict(json.loads(report.read_text("utf-8-sig")))
    except (OSError, ValueError, TypeError):
        return {}


def publish(window_hours: float = WINDOW_HOURS, path: Path | None = None,
            report: Path | None = None) -> dict[str, Any]:
    """Write THROUGHPUT.json: the per-stage rate, the ratchet high-water mark and the verdict.

    The mark is carried forward from the last report and raised, never lowered. A stage whose
    measured rate falls more than REGRESSION_TOLERANCE below its mark is a REGRESSION and
    `scripts/check_throughput_ratchet.py` exits 1 on it."""
    out = report or REPORT
    doc = summarise(window_hours, path)
    prev_marks = dict(_previous(out).get("high_water_rows_per_s") or {})
    marks: dict[str, float] = {k: float(v) for k, v in prev_marks.items()
                               if isinstance(v, (int, float))}
    regressions: list[dict[str, Any]] = []
    for st, s in doc["stages"].items():
        if s.get("status") != "MEASURED":
            continue
        best = s.get("best_sample_rows_per_s")
        if best is None:
            continue
        mark = marks.get(st)
        if mark is None or best > mark:
            marks[st] = float(best)
            continue
        if best < mark * (1.0 - REGRESSION_TOLERANCE):
            regressions.append({"stage": st, "high_water_rows_per_s": mark,
                                "measured_rows_per_s": best,
                                "factor": round(mark / best, 2) if best else None})
    doc["high_water_rows_per_s"] = {k: round(v, 2) for k, v in sorted(marks.items())}
    doc["regressions"] = regressions
    doc["verdict"] = ("REGRESSION" if regressions
                      else ("MEASURED" if doc["binding_stage"] else "UNMEASURED"))
    doc["ratchet"] = ("throughput only goes up: the high-water mark is never lowered, and a "
                      "stage more than "
                      f"{int(REGRESSION_TOLERANCE * 100)}% below its mark fails the fence")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc
