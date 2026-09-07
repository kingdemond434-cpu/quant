"""Refresh every hourly producer that has gone past half its cadence, on its own clock.

    py -3 scripts/run_research_reports.py            # refresh what is due
    py -3 scripts/run_research_reports.py --report   # say what is due, run nothing

WHY THIS EXISTS, measured on the live board 2026-09-07. Eleven producers declare a 3600-second
cadence in `issue_board.CADENCE`, and every one of them is a LEG of `hourly_cycle.py`. That was
fine when the cycle took twenty minutes. It now has fifty-five legs, one of which is a backtest
with a forty-five-minute budget, so a pass regularly exceeds an hour -- and `issue_board` is
itself a leg of the same cycle, running BEFORE the four research reports it measures.

The arithmetic is then unavoidable: at measurement time those artifacts were written by the
PREVIOUS pass, so their age is one full cycle duration. Once a cycle exceeds `STALE_TOLERANCE`
(2.0) times the cadence, the board reports them STALLED on every single pass, forever, while the
producers are running perfectly well. Measured: issue_board last wrote 12:37 and had not run
again by 13:49 -- seventy-two minutes with no completed pass.

A board that cries stalled every hour is a board nobody reads, which is the failure L1.37 already
names, and the reports downstream of those artifacts really are running on hour-old inputs.

THE FIX IS A CLOCK, NOT A LOOSER THRESHOLD. Raising STALE_TOLERANCE would silence the symptom and
leave the artifacts just as old; the desk's standing rule is that no threshold is ever loosened to
make a red light go green. What was actually wrong is that an organ with an hourly cadence was
reachable only by finishing forty-seven other legs first -- and an organ that runs when a long
cycle reaches leg forty-eight is an organ that stops the first time an earlier leg is slow.

DRIVEN BY THE TABLE THAT DETECTS THE STALENESS, deliberately. `issue_board.CADENCE` is already the
single authority on what has a cadence and what refreshes it -- its own comment says a producer
absent from that table is a producer nothing can notice going quiet. Reading it here means the
detector and the refresher can never disagree, and a producer added to the table gets a clock in
the same edit rather than in a second one somebody forgets.

TWO GUARDS AGAINST DOUBLE WORK, and one honest residual:

  FRESHNESS  a producer whose artifact is younger than half its cadence is skipped. When the
             cycle's own leg has just written it there is nothing to do, so on a healthy box this
             task costs one stat() per producer and exits.
  LOCK       `exclusive_job` per producer name, so two copies of THIS runner cannot overlap.
  RESIDUAL   `hourly_cycle._producer` takes no lock, so a cycle leg and this runner can still
             collide. The window is small (the freshness guard closes most of it) and the outcome
             is benign: these producers rewrite their artifact wholesale rather than appending, so
             the loser's work is overwritten by an equally complete file. Making `_producer` take
             the lock would change the behaviour of all forty-odd legs at once, which is a larger
             change than this defect justifies and is not made here silently.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import issue_board, job_lock  # noqa: E402

#: Only producers on an hourly-or-faster cadence. The daily ones (miner_conversion, ceiling_audit)
#: belong to the daily cycle and giving them an hourly clock would be work nobody asked for.
MAX_CADENCE_S = 3600

#: Refresh once an artifact is past HALF its cadence. Not at the full cadence: the producer takes
#: time to run, so waiting for the deadline guarantees arriving after it. Half leaves room for a
#: slow pass and still means a healthy box skips almost every producer almost every hour.
REFRESH_AT = 0.5

#: Per-producer budget. Generous enough for the heaviest of these and far short of the hourly
#: trigger, so a hung producer cannot still be running when the next pass starts.
BUDGET_S = 600

REPORT = BASE / "reports" / "RESEARCH_REPORT_CLOCK.json"


def _artifact_path(rel: str) -> Path:
    """Resolve a CADENCE artifact, which may be desk-relative or repo-relative.

    The table mixes both -- `desks/mt5/reports/...` and `web/desk_state.json` -- because the
    producers do. Resolving against only one root would silently report every artifact under the
    other as missing, i.e. as maximally stale, and this task would then rerun those producers
    every hour forever.
    """
    for root in (REPO, BASE):
        candidate = root / rel
        if candidate.exists():
            return candidate
    return REPO / rel


def _script_path(rel: str) -> Path | None:
    for root in (BASE, REPO):
        candidate = root / rel
        if candidate.exists():
            return candidate
    return None


def due(now: datetime | None = None) -> list[dict[str, Any]]:
    """Producers past half their cadence, with the reason for each verdict.

    Returns every hourly producer, due or not, so `--report` can show what it decided rather than
    only what it will do. A task that prints nothing when it skips everything is indistinguishable
    from a task that did not run.
    """
    stamp = (now or datetime.now(tz=UTC)).timestamp()
    out: list[dict[str, Any]] = []
    for name, rel, cadence, producer in issue_board.CADENCE:
        if cadence > MAX_CADENCE_S or not producer:
            continue
        artifact = _artifact_path(rel)
        script = _script_path(producer)
        if script is None:
            out.append({"name": name, "due": False, "why": "MISSING",
                        "detail": f"{producer} exists under neither {BASE} nor {REPO}"})
            continue
        if not artifact.exists():
            out.append({"name": name, "due": True, "age_s": None, "cadence_s": cadence,
                        "producer": producer, "why": "artifact has never been written"})
            continue
        age = stamp - artifact.stat().st_mtime
        is_due = age > cadence * REFRESH_AT
        out.append({
            "name": name, "due": is_due, "age_s": round(age), "cadence_s": cadence,
            "producer": producer,
            "why": (f"{round(age)}s old, past {REFRESH_AT:g} x {cadence}s"
                    if is_due else
                    f"{round(age)}s old, within {REFRESH_AT:g} x {cadence}s -- the cycle has it"),
        })
    return out


def refresh(row: dict[str, Any]) -> dict[str, Any]:
    """Run one producer under its lock. A failure is reported, never raised.

    Same philosophy as `hourly_cycle._producer`: these are independent measurement organs, and one
    that crashes must not take the rest of the pass with it. A non-zero exit is frequently a
    VERDICT rather than a fault -- several of these exit non-zero while something they measure is
    unhealthy -- so the code is recorded and nothing is inferred from it here.
    """
    script = _script_path(row["producer"])
    if script is None:
        return {**row, "status": "MISSING"}
    with job_lock.exclusive_job(row["name"]) as acquired:
        if not acquired:
            return {**row, "status": "BUSY",
                    "detail": "another pass holds this producer's lock -- not re-run"}
        try:
            proc = subprocess.run(
                [sys.executable, "-u", "-W", "ignore", str(script)],
                capture_output=True, text=True, cwd=str(REPO),
                timeout=BUDGET_S, check=False,
            )
            return {**row, "status": "RAN", "exit_code": proc.returncode,
                    "tail": (proc.stdout or proc.stderr or "")[-300:]}
        except subprocess.TimeoutExpired:
            return {**row, "status": "TIMEOUT", "budget_s": BUDGET_S}
        except Exception as exc:                                        # noqa: BLE001
            return {**row, "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true",
                    help="say what is due and run nothing")
    args = ap.parse_args(argv)

    rows = due()
    pending = [r for r in rows if r.get("due")]
    results = [] if args.report else [refresh(r) for r in pending]

    payload = {
        "generated_utc": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "watched": len(rows),
        "due": len(pending),
        "ran": sum(1 for r in results if r.get("status") == "RAN"),
        "busy": sum(1 for r in results if r.get("status") == "BUSY"),
        "failed": sum(1 for r in results
                      if r.get("status") in {"TIMEOUT", "ERROR", "MISSING"}),
        "verdicts": rows,
        "results": results,
        "why": ("these producers declare an hourly cadence and are otherwise reachable only as "
                "legs of a 55-leg cycle that now exceeds an hour, so their freshness was a "
                "function of how long the cycle took rather than of their own clock"),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"research report clock: {len(rows)} watched, {len(pending)} due, "
          f"{payload['ran']} ran, {payload['busy']} busy, {payload['failed']} failed",
          flush=True)
    for r in results:
        print(f"  {r['status']:8} {r['name']:22} {r.get('why', '')}", flush=True)
    # ZERO EVEN WHEN A PRODUCER FAILED. The task's job is to give these organs a clock; a producer
    # that exits non-zero has been RUN, which is what this was missing. Its verdict is the issue
    # board's business, and a red task here would just add a second alarm for the same fact.
    return 0


if __name__ == "__main__":                                              # pragma: no cover
    raise SystemExit(main())
