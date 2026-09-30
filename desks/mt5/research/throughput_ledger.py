"""THE DESK'S OWN THROUGHPUT, MEASURED HOURLY: how many cells it can mint and judge per day.

WHY THIS ORGAN EXISTS. On 2026-09-23 the canonical write door ran at FOUR ROWS PER SECOND and
no artifact in the desk said so. Four rows a second is 345,600 rows a day at a 100% duty cycle,
so the principal's target -- millions of breadth cells minted and judged per day -- was
arithmetically unreachable, and the only visible symptom was a donation that took forty minutes.
A throughput ceiling is the one defect that leaves nothing failing behind it: every row lands,
every gate passes, the desk simply does a decimal place less work per hour than anyone believes.

So the rate itself is an artifact now. Two numbers per stage, and the difference between them is
the point:

  CAPACITY  -- rows per second the stage reaches WHILE IT RUNS, from instrumented samples
               (`libs/ops/throughput.record`). This is what an engineering fix moves.
  OBSERVED  -- rows per day the desk ACTUALLY put through the stage, counted from the registry's
               own created_at timestamps. This is capacity times duty cycle.

A stage whose observed rate is far under its capacity is not slow; it is idle, and that is a
scheduling answer, not a database one. A stage whose capacity is under the target is a real
ceiling and gets named as one.

NOTHING HERE CAPS, DEFERS OR QUEUES ANYTHING. It counts rows, counts seconds, divides, and
writes a report. It is read-only against the registry.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.ops import throughput  # noqa: E402

REGISTRY = ROOT / "data" / "alpha_registry.sqlite"
REPORT = DESK / "reports" / "THROUGHPUT.json"
COVERAGE = DESK / "reports" / "BACKTEST_COVERAGE.json"
#: One row per judged cell, with its timestamp -- the judge's own rate substrate. Read, never
#: written: the judge is sealed and this organ only counts what it already left behind.
GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
GAUNTLET_REPORT = DESK / "reports" / "universal_gates_external.json"

#: The principal's target, written here so the report answers the question it was asked rather
#: than leaving the arithmetic to the reader. It is a TARGET, never a cap: nothing in this file
#: or anywhere downstream mints or judges less because of it.
TARGET_CELLS_PER_DAY = 1_000_000

#: Hours of registry history the OBSERVED rate is counted over. A day, so one idle hour or one
#: large donation does not decide the number.
OBSERVED_WINDOW_H = 24


def _ro_conn() -> sqlite3.Connection | None:
    """Read-only. This organ must never be able to write the canonical registry."""
    if not REGISTRY.exists():
        return None
    try:
        c = sqlite3.connect(f"file:{REGISTRY}?mode=ro", uri=True, timeout=30)
    except sqlite3.Error:
        return None
    c.row_factory = sqlite3.Row
    return c


def _count_since(c: sqlite3.Connection, table: str, column: str, cut: str) -> int | None:
    try:
        row = c.execute(f'SELECT COUNT(*) n FROM "{table}" WHERE {column} >= ?',  # noqa: S608
                        (cut,)).fetchone()
    except sqlite3.Error:
        return None
    return int(row["n"]) if row is not None else None


def _ledger_rows_since(cut: str) -> int | None:
    """Verdicts the judge appended since `cut`. None when the ledger cannot be read -- which is
    UNMEASURED, and never a zero."""
    if not GATE_LEDGER.exists():
        return None
    n = 0
    try:
        with GATE_LEDGER.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    at = str(json.loads(line).get("at") or "")
                except ValueError:
                    continue
                if at >= cut:
                    n += 1
    except OSError:
        return None
    return n


def observed(window_h: int = OBSERVED_WINDOW_H) -> dict[str, Any]:
    """What the desk actually put through each stage, from the registry's own timestamps."""
    c = _ro_conn()
    if c is None:
        return {"status": "UNMEASURED", "why": f"{REGISTRY} is not readable from here"}
    cut = (datetime.now(tz=UTC) - timedelta(hours=window_h)).isoformat(timespec="seconds")
    try:
        counts = {
            "minted_cells": _count_since(c, "research_candidates", "created_at", cut),
            "discoveries": _count_since(c, "discoveries", "created_at", cut),
            "trials": _count_since(c, "trials_ledger", "created_at", cut),
        }
        # JUDGED IS COUNTED FROM THE JUDGE'S OWN LEDGER, not from a candidate status. The
        # gauntlet appends one verdict row per judged cell but does not flip
        # research_candidates.status, so the status query reported 2,584 judged in a day the
        # verdict ledger recorded 98,863 for -- a 38x undercount of the desk's own output,
        # read off the wrong table. The status count stays alongside it, named for what it is.
        try:
            counts["cells_marked_judged_in_registry"] = int(c.execute(
                "SELECT COUNT(*) n FROM research_candidates WHERE status IN "
                "('judged','survived','retired') AND updated_at >= ?", (cut,)).fetchone()["n"])
        except sqlite3.Error:
            counts["cells_marked_judged_in_registry"] = None
        counts["judged_cells"] = _ledger_rows_since(cut)
        totals = {t: int(c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])  # noqa: S608
                  for t in ("research_candidates", "discoveries", "trials_ledger")}
    finally:
        c.close()
    per_day = {k: (None if v is None else int(v * 24 / window_h)) for k, v in counts.items()}
    return {"status": "MEASURED", "window_h": window_h, "counts": counts,
            "rows_per_day": per_day, "cumulative": totals,
            "rule": "observed = capacity x duty cycle; a stage far under its capacity is IDLE, "
                    "which is a scheduling answer and not a storage one"}


def _busiest_hour(hours: dict[str, int]) -> dict[str, Any]:
    """DEMONSTRATED CAPACITY: the most this stage has ever done in one real clock hour.

    Not a synthetic benchmark and not a hope. The desk did this, on this hardware, with this
    code, in an hour that actually happened -- so it is the floor of what the stage can do, and
    an honest ceiling estimate is the number it has already hit rather than one it has not."""
    if not hours:
        return {"status": "UNMEASURED", "why": "no timestamped rows to count"}
    top = max(hours.items(), key=lambda kv: kv[1])
    recent = sorted(hours.items())[-24:]
    return {"status": "MEASURED", "best_hour": top[0], "best_hour_rows": top[1],
            "rows_per_s": round(top[1] / 3600.0, 3),
            "rows_per_day_at_100pct": top[1] * 24,
            "last_24_clock_hours_rows": sum(n for _h, n in recent),
            "hours_with_any_rows": len(hours)}


def mint_stage() -> dict[str, Any]:
    """How fast the desk mints cells, from the registry's own created_at stamps."""
    c = _ro_conn()
    if c is None:
        return {"status": "UNMEASURED", "why": f"{REGISTRY} is not readable from here"}
    try:
        hours = {str(r["h"]): int(r["n"]) for r in c.execute(
            "SELECT substr(created_at,1,13) h, COUNT(*) n FROM research_candidates "
            "WHERE created_at IS NOT NULL GROUP BY h")}
    except sqlite3.Error as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    finally:
        c.close()
    return _busiest_hour(hours)


def judged_stage() -> dict[str, Any]:
    """How fast the JUDGE judges, counted from the verdict ledger it appends to.

    The judge's logic is sealed and nothing here touches it. This counts its output rows by the
    hour they were stamped, which is a measurement of the judge and never an opinion about it."""
    if not GATE_LEDGER.exists():
        return {"status": "UNMEASURED",
                "why": f"{GATE_LEDGER.name} has never been written; absence is not zero"}
    hours: dict[str, int] = {}
    n = 0
    try:
        with GATE_LEDGER.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    at = str(json.loads(line).get("at") or "")
                except ValueError:
                    continue
                if len(at) >= 13:
                    hours[at[:13]] = hours.get(at[:13], 0) + 1
                    n += 1
    except OSError as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    out = _busiest_hour(hours)
    out["verdicts_in_ledger"] = n
    try:
        d = json.loads(GAUNTLET_REPORT.read_text("utf-8-sig"))
        out["last_sweep"] = {k: d.get(k) for k in
                             ("swept_at", "n_cells", "n_judged", "n_unmeasured", "workers",
                              "n_cells_deferred_build_budget", "memory_budget_mb")}
    except (OSError, ValueError):
        out["last_sweep"] = None
    return out


def judge_stage() -> dict[str, Any]:
    """The judge's own rate, from the artifact the gauntlet writes. Never from its logic, which
    is sealed: this reads `cells_run` and `elapsed_s` and divides."""
    if not COVERAGE.exists():
        return {"status": "UNMEASURED", "why": "reports/BACKTEST_COVERAGE.json has never landed"}
    try:
        d = json.loads(COVERAGE.read_text("utf-8-sig"))
    except (OSError, ValueError) as exc:
        return {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    run = d.get("cells_run")
    el = d.get("elapsed_s")
    age_h = round((datetime.now(tz=UTC).timestamp() - COVERAGE.stat().st_mtime) / 3600, 1)
    out: dict[str, Any] = {"measured_at": d.get("measured_at"), "artifact_age_h": age_h,
                           "cells_submitted": d.get("cells_submitted"), "cells_run": run,
                           "cells_produced_result": d.get("cells_produced_result"),
                           "workers": d.get("workers"), "budget_min": d.get("budget_min"),
                           "held": d.get("held"), "held_no_bars": d.get("held_no_bars")}
    if not isinstance(run, (int, float)) or not isinstance(el, (int, float)) or el <= 0:
        out["status"] = "UNMEASURED"
        out["why"] = (f"the gauntlet's last pass reports cells_run={run!r} in elapsed_s={el!r}: "
                      "a rate cannot be divided out of it, and absence is not zero")
        return out
    out["status"] = "MEASURED"
    out["cells_per_s"] = round(float(run) / float(el), 3)
    out["cells_per_day_at_100pct"] = int(float(run) / float(el) * 86400)
    return out


def build(window_h: int = OBSERVED_WINDOW_H) -> dict[str, Any]:
    """Publish THROUGHPUT.json: capacity per stage (ratcheted), observed per stage, verdict."""
    doc = throughput.publish(window_hours=float(window_h), report=REPORT)
    doc["observed"] = observed(window_h)
    # A stage measured from the desk's own artifacts beats one measured from nothing: `mint` and
    # `judge` publish timestamped rows already, so their capacity is DEMONSTRATED (the best real
    # clock hour) rather than left UNMEASURED waiting for instrumentation nobody added.
    for name, fn in (("mint", mint_stage), ("judge", judged_stage)):
        got = fn()
        if got.get("status") == "MEASURED" or doc["stages"].get(name, {}).get(
                "status") != "MEASURED":
            merged = {**doc["stages"].get(name, {}), **got}
            if merged.get("status") == "MEASURED":
                # The placeholder's "no sample inside 24h" must not survive onto a stage that
                # IS measured: a reason for an absence, printed beside the number that fills
                # it, reads as a caveat on a figure that does not have one.
                merged.pop("why", None)
            doc["stages"][name] = merged
    doc["stages"]["judge"] = {**doc["stages"].get("judge", {}), "gauntlet": judge_stage()}
    caps = {k: v.get("rows_per_day_at_100pct") or v.get("cells_per_day_at_100pct")
            for k, v in doc["stages"].items() if v.get("status") == "MEASURED"}
    caps = {k: v for k, v in caps.items() if isinstance(v, int)}
    doc["capacity_rows_per_day"] = caps
    doc["binding_stage"] = min(caps, key=lambda k: caps[k]) if caps else None
    doc["chain_rows_per_day"] = caps.get(doc["binding_stage"]) if doc["binding_stage"] else None
    doc["target_cells_per_day"] = TARGET_CELLS_PER_DAY
    if doc["chain_rows_per_day"] is None:
        doc["target_verdict"] = "UNMEASURED"
        doc["shortfall_factor"] = None
    else:
        reach = doc["chain_rows_per_day"] >= TARGET_CELLS_PER_DAY
        doc["target_verdict"] = "REACHABLE" if reach else "SHORT"
        doc["shortfall_factor"] = (None if reach else
                                   round(TARGET_CELLS_PER_DAY / max(1, doc["chain_rows_per_day"]),
                                         2))
    doc["unmeasured_stages"] = [k for k, v in doc["stages"].items()
                                if v.get("status") != "MEASURED"]
    doc["note"] = ("capacity is what a stage reaches while it runs; observed is what the desk "
                   "actually put through it. An UNMEASURED stage makes chain_rows_per_day an "
                   "UPPER bound, never a clean verdict.")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    return doc


def main() -> int:
    doc = build()
    print(json.dumps({k: doc.get(k) for k in
                      ("at", "verdict", "binding_stage", "chain_rows_per_day",
                       "capacity_rows_per_day", "target_verdict", "shortfall_factor",
                       "unmeasured_stages", "regressions")}, indent=1, default=str), flush=True)
    obs = doc.get("observed") or {}
    if obs.get("status") == "MEASURED":
        print(f"observed/day: {obs.get('rows_per_day')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
