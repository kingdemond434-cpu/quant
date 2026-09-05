"""THE COMPUTE ALLOCATOR'S DENOMINATOR: what every research run actually cost.

    "Your compute should be allocated just like capital ... ComputeValue_j = P(success_j) *
     E[dElog_j] * InformationGain_j / GPUhours_j"                    -- the principal, 2026-09-05

WHY THE DENOMINATOR FIRST, AND ONLY THE DENOMINATOR. `libs.ops.allocators` reports COMPUTE as the
stack's weakest link and says why: nothing decides it. Compute is spent first-come-first-served by
whatever the scheduler fires -- the hourly cycle takes what it takes, the deepening worker drains
in value-of-information order INSIDE its own queue but never against a competing use, and the
sweep runs because it is 07:15. That is not a bad ranking; it is no ranking.

And it CANNOT be fixed by writing the ranking formula, because the formula divides by hours and
this desk has never recorded an hour. Every run's cost was unknown, so `value per hour` had no
denominator, so a compute allocator was arithmetic nobody could evaluate. Shipping the formula
against an absent denominator would produce a confident ordering of made-up numbers -- worse than
the arrival order it replaced, because it would look principled.

So this module records COST and nothing else, and `rank` reads back what accumulates. A run's
cost is wall clock and CPU time, which are free to measure and impossible to argue with. Once
runs have been costed, the numerator (did this run produce a survivor, and what did the survivor
earn) is already in RESEARCH_PNL and the hypothesis graph, and the ranking is a join rather than
a research programme.

APPEND-ONLY, AND CHEAP ENOUGH TO ALWAYS BE ON. One line per run, opened and closed, so a run that
crashes still leaves its cost -- a crashed run that consumed forty minutes consumed forty minutes,
and pretending otherwise would make the expensive failures invisible, which is precisely the
population a compute allocator most needs to see.

NOT GPU-HOURS, because this desk has no GPU. The unit is the one it actually spends: wall-clock
seconds on a box whose real constraint is that six resident pythons hold 3.1 GB of 8.4 GB and the
hourly cycle must finish inside its hour. Naming the unit it has rather than the unit the
reference architecture has is the difference between a ledger and a costume.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "desks" / "mt5" / "data" / "compute_ledger.jsonl"

#: Runs older than this are still in the file (append-only) but out of the ranking window: a
#: value-per-hour estimate from a run whose code no longer exists prices a different program.
#: Thirty days is the shortest window that still holds several passes of every weekly organ.
WINDOW_DAYS = 30


@dataclass
class Run:
    """One costed unit of research work, open until `close` is called."""

    name: str
    kind: str
    started: float
    cpu_started: float
    meta: dict[str, Any]


def _cpu_seconds() -> float:
    """CPU consumed by this process and its children. `os.times` is stdlib and never raises."""
    t = os.times()
    return float(t.user + t.system + t.children_user + t.children_system)


def _append(row: dict[str, Any]) -> None:
    """One line, best effort. A ledger write must never take down the work it is measuring."""
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass


def open_run(name: str, kind: str = "research", **meta: Any) -> Run:
    return Run(name=name, kind=kind, started=time.monotonic(),
               cpu_started=_cpu_seconds(), meta=dict(meta))


def close_run(run: Run, *, outcome: str = "ok", **result: Any) -> dict[str, Any]:
    """Record what the run cost and what it produced. `outcome` is free text the caller owns."""
    row = {
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "run": run.name, "kind": run.kind, "outcome": str(outcome),
        "wall_s": round(time.monotonic() - run.started, 3),
        "cpu_s": round(_cpu_seconds() - run.cpu_started, 3),
        **run.meta, **result,
    }
    _append(row)
    return row


@contextmanager
def costed(name: str, kind: str = "research", **meta: Any) -> Iterator[dict[str, Any]]:
    """Cost one block of work, whatever happens inside it.

        with costed("deepen", kind="seat") as r:
            r["decided"] = worker.main([])

    A RAISING BLOCK STILL RECORDS, with `outcome` naming the exception. An expensive failure is
    the single most valuable row in a compute ledger and the easiest one to lose.
    """
    run = open_run(name, kind, **meta)
    result: dict[str, Any] = {}
    try:
        yield result
    except BaseException as exc:
        close_run(run, outcome=f"{type(exc).__name__}: {exc}"[:200], **result)
        raise
    close_run(run, outcome=str(result.pop("outcome", "ok")), **result)


def rows(window_days: int = WINDOW_DAYS, path: Path | None = None) -> list[dict[str, Any]]:
    """Costed runs inside the window, newest last. A missing ledger is an empty list, not a zero:
    the caller must be able to tell "nothing has been costed" from "everything cost nothing"."""
    p = LEDGER if path is None else path
    if not p.exists():
        return []
    cut = time.time() - window_days * 86400.0
    out: list[dict[str, Any]] = []
    try:
        text = p.read_text("utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            stamp = datetime.fromisoformat(str(row.get("at"))).timestamp()
        except (ValueError, TypeError):
            continue
        if stamp >= cut:
            out.append(row)
    return out


def cost_by_run(window_days: int = WINDOW_DAYS,
                path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Hours each named run has consumed in the window, and how often it failed.

    THE FAILURE RATE RIDES WITH THE COST because they are the same decision. A run that costs
    forty minutes and fails a third of the time is not a forty-minute run; its expected cost per
    useful pass is sixty, and a ranking that used the raw number would fund it too generously.
    """
    agg: dict[str, dict[str, Any]] = {}
    for row in rows(window_days, path):
        name = str(row.get("run") or "?")
        a = agg.setdefault(name, {"runs": 0, "wall_s": 0.0, "cpu_s": 0.0, "failures": 0,
                                  "kind": str(row.get("kind") or "")})
        a["runs"] += 1
        a["wall_s"] += float(row.get("wall_s") or 0.0)
        a["cpu_s"] += float(row.get("cpu_s") or 0.0)
        if str(row.get("outcome") or "ok") != "ok":
            a["failures"] += 1
    for a in agg.values():
        a["mean_wall_s"] = round(a["wall_s"] / a["runs"], 2) if a["runs"] else None
        a["failure_rate"] = round(a["failures"] / a["runs"], 4) if a["runs"] else None
        a["hours"] = round(a["wall_s"] / 3600.0, 4)
    return agg


def rank(value_by_run: dict[str, float] | None = None, window_days: int = WINDOW_DAYS,
         path: Path | None = None) -> dict[str, Any]:
    """Value per hour, for the runs the caller can price. Refuses rather than guessing.

    `value_by_run` is `run name -> expected dE[log W] per day the run's output carries`, supplied
    by whoever knows -- RESEARCH_PNL for a research arm, the rent ledger for an organ. This module
    does not compute it and must not: inventing a numerator to sit over a real denominator is how
    a compute allocator becomes a confident ordering of made-up numbers.

    A run with cost and no value is UNPRICED and listed as such; a run with value and no cost is
    UNCOSTED and listed as such. Both are actionable and neither is a ranking position.
    """
    costs = cost_by_run(window_days, path)
    vals = dict(value_by_run or {})
    ranked: list[dict[str, Any]] = []
    unpriced, uncosted = [], []
    for name, c in costs.items():
        if name not in vals or not c["hours"]:
            unpriced.append(name)
            continue
        ranked.append({"run": name, "value_per_hour": round(vals[name] / c["hours"], 8),
                       "value": vals[name], "hours": c["hours"], "runs": c["runs"],
                       "failure_rate": c["failure_rate"]})
    uncosted = sorted(set(vals) - set(costs))
    ranked.sort(key=lambda r: -r["value_per_hour"])
    return {
        "window_days": window_days,
        "costed_runs": len(costs), "total_hours": round(
            sum(c["hours"] for c in costs.values()), 4),
        "ranked": ranked,
        "unpriced": sorted(unpriced),
        "uncosted": uncosted,
        "why": ("" if costs else
                f"nothing has been costed: {LEDGER.name} is absent or empty, so there is no "
                f"denominator and no compute ranking is possible yet -- which is the honest "
                f"state, not a zero"),
    }
