"""REJECTION THROUGHPUT, HOURLY: how many candidates the desk KILLS WITH CONFIDENCE per day.

WHY THIS IS A HEADLINE AND NOT A FOOTNOTE. A research desk that mints millions of cells is only
as fast as its ability to say "no" to them on evidence. A cell whose verdict is `UNKNOWN`, or that
never built, or that timed out, has not been rejected -- it has been postponed, and it will cost
another judge-second later. So the number that says whether the gauntlet is doing its job is not
rows per hour (`throughput_ledger`), and not first rulings per hour (`judging_burndown`), but
CONFIDENT KILLS: a REJECT whose terminal gate is a MEASURED gate statistic -- an in-sample
Sharpe, a deflated Sharpe, a PBO, an SPA p-value, CPCV / walk-forward OOS Sharpe, a stress-cost
expectancy, an expected value. Divided by what was judged, that is KILL CONFIDENCE: the share of
the judge's output that is a finished, evidence-backed answer.

WHAT COUNTS AS WHAT (the judge is sealed and nothing here re-judges; this reads its ledger):

    survivor          passed == True
    confident_kill    passed False and the terminal gate is in MEASURED_STAT_GATES; or a
                      fail-closed gate (lockbox, swap_cost) whose own stage says it measured
    unconfident       UNKNOWN / empty terminal gate; `NOT_RUN_*` downstream status (build or data
                      failure, build-budget deferral, timeout); a fail-closed gate with no proof
                      it measured (the ledger carries no stage detail, and those two gates FAIL
                      CLOSED on missing evidence, so absence of proof is not a kill); any gate
                      name this organ does not recognise
    screen_reject     terminal gate `economic_prior` / `symbol_eligibility`: a refusal on a fact
                      about the cell, not on a statistic. Not a confident kill, not a postponement.

    judged = survivors + confident_kills + unconfident + screen_rejects       (per day, per cell)

THE ROW IS NOT THE UNIT. The sealed judge appends a ledger row only when a cell's verdict CHANGES
(`external_gauntlet._append_gate_ledger`), so "judged per day" here means distinct cells whose
verdict was RECORDED that day, one per cell (its last row that day). `judging_burndown` owns the
backlog's first-ruling drain and its row classifier (`judging_burndown.classify`) is imported,
never re-spelled; this organ refines its `ruled` class into confident / screen / fail-closed.

STALE OR MISSING IS UNMEASURED, NEVER ZERO (L1.28a). An absent ledger, or one whose newest row is
older than STALE_H, publishes the headline as UNMEASURED with its reason. A day before the
ledger's first row or after its last is UNMEASURED; a day in between with no rows is a real zero.

PER CORE-HOUR, when the compute ledger has priced the judge: `compute_ledger.jsonl` rows whose run
name contains "gauntlet" give CPU-seconds per day; without them the rate is UNMEASURED.

PUBLISHED: `desks/mt5/reports/REJECTION_THROUGHPUT.json`. Clock: leg `rejection_throughput` in
`research/hourly_cycle.py` (department validate), right after `judging_burndown`. Read-only; it
throttles, caps and reorders nothing.

    python desks/mt5/research/rejection_throughput.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from judging_burndown import classify as _burndown_classify
except ImportError:                                            # pragma: no cover - import context
    from research.judging_burndown import classify as _burndown_classify  # type: ignore[no-redef]

GATE_LEDGER = DESK / "data" / "hypotheses" / "gate_verdict_ledger.jsonl"
COMPUTE_LEDGER = DESK / "data" / "compute_ledger.jsonl"
OUT = DESK / "reports" / "REJECTION_THROUGHPUT.json"
UNMEASURED = "UNMEASURED"

#: Gates whose failure IS a measured statistic (external_gauntlet's per-cell stage block, in
#: evaluation order). `pbo` and `reality_check_spa` are program-level statistics broadcast onto
#: every cell, still measured numbers.
MEASURED_STAT_GATES: frozenset[str] = frozenset({
    "in_sample_screen", "deflated_sharpe", "pbo", "reality_check_spa", "cpcv", "walk_forward",
    "stress_costs", "expected_value"})
#: Gates that FAIL CLOSED on missing evidence: `lockbox` refuses a held-out window under its day
#: floor (lockbox_sharpe None), `swap_cost` refuses an unpriced instrument (measured False).
FAIL_CLOSED_GATES: frozenset[str] = frozenset({"lockbox", "swap_cost"})
#: Gate 0: refusals on a fact about the cell, before any bar is read.
SCREEN_GATES: frozenset[str] = frozenset({"economic_prior", "symbol_eligibility"})

STALE_H = 48.0
HEADLINE_DAYS = 7
PER_DAY_DAYS = 14
Z95 = 1.959963984540054


def wilson(k: int, n: int, z: float = Z95) -> list[float] | None:
    """Wilson score interval for k successes in n trials; None when n == 0 (nothing to bound)."""
    if n <= 0:
        return None
    p = k / n
    den = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, centre - half), 6), round(min(1.0, centre + half), 6)]


def outcome(row: dict[str, Any]) -> tuple[str, str]:
    """(bucket, reason) for one ledger row. Bucket in survivor / confident_kill / unconfident /
    screen_reject. The first split is `judging_burndown.classify`, which owns ruled-vs-not."""
    kind = _burndown_classify(row)
    if kind == "not_run":
        return "unconfident", "not_run"
    if kind == "unknown":
        return "unconfident", "unknown_gate"
    if row.get("passed") is True:
        return "survivor", "passed"
    gate = str(row.get("terminal_gate") or "")
    if gate in MEASURED_STAT_GATES:
        return "confident_kill", gate
    if gate in SCREEN_GATES:
        return "screen_reject", gate
    if gate in FAIL_CLOSED_GATES:
        stage = (row.get("stages") or row.get("gates") or {}).get(gate)
        if isinstance(stage, dict):
            if gate == "lockbox" and stage.get("lockbox_sharpe") is not None:
                return "confident_kill", gate
            if gate == "swap_cost" and stage.get("measured") is True:
                return "confident_kill", gate
        return "unconfident", f"fail_closed_unproven:{gate}"
    return "unconfident", f"unrecognised_gate:{gate}"


def _day(at: str) -> str | None:
    try:
        return datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(UTC).date().isoformat()
    except (ValueError, AttributeError):
        return None


def read_ledger(path: Path | None = None) -> dict[str, Any]:
    """Stream the verdict ledger into per-day, per-cell last outcomes."""
    p = GATE_LEDGER if path is None else path
    if not p.exists():
        return {"status": UNMEASURED, "why": f"{p.name} absent: no verdict has been read, "
                                              "so no kill can be counted (absence is not zero)"}
    days: dict[str, dict[str, tuple[str, str]]] = {}
    first_at = last_at = ""
    rows = bad = 0
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    bad += 1
                    continue
                if not isinstance(row, dict):
                    bad += 1
                    continue
                at = str(row.get("at") or "")
                day = _day(at)
                cell = str(row.get("cell") or "")
                if day is None or not cell:
                    bad += 1
                    continue
                rows += 1
                first_at = at if not first_at or at < first_at else first_at
                last_at = at if at > last_at else last_at
                days.setdefault(day, {})[cell] = outcome(row)
    except OSError as exc:
        return {"status": UNMEASURED, "why": f"{type(exc).__name__}: {exc}"}
    if not rows:
        return {"status": UNMEASURED, "why": f"{p.name} holds no readable verdict row",
                "unreadable_rows": bad}
    return {"status": "MEASURED", "rows": rows, "unreadable_rows": bad, "first_at": first_at,
            "last_at": last_at, "days": days}


def core_hours_by_day(path: Path | None = None) -> dict[str, float]:
    """CPU-hours the judge spent per day, from the compute ledger's gauntlet rows."""
    p = COMPUTE_LEDGER if path is None else path
    out: dict[str, float] = {}
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict) or "gauntlet" not in str(row.get("run") or ""):
                    continue
                day = _day(str(row.get("at") or row.get("finished_at") or ""))
                try:
                    cpu = float(row.get("cpu_s") or 0.0)
                except (TypeError, ValueError):
                    continue
                if day and cpu > 0:
                    out[day] = out.get(day, 0.0) + cpu / 3600.0
    except OSError:
        return {}
    return out


def _tally(cells: dict[str, tuple[str, str]]) -> dict[str, Any]:
    counts = {"survivor": 0, "confident_kill": 0, "unconfident": 0, "screen_reject": 0}
    reasons: dict[str, int] = {}
    for bucket, reason in cells.values():
        counts[bucket] += 1
        if bucket == "unconfident":
            reasons[reason] = reasons.get(reason, 0) + 1
    judged = sum(counts.values())
    return {"judged": judged, "confident_kills": counts["confident_kill"],
            "unconfident": counts["unconfident"], "survivors": counts["survivor"],
            "screen_rejects": counts["screen_reject"],
            "unconfident_by_reason": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
            "kill_confidence": (round(counts["confident_kill"] / judged, 6) if judged else None),
            "kill_confidence_wilson95": wilson(counts["confident_kill"], judged)}


def build(now: datetime | None = None, *, ledger: Path | None = None,
          compute: Path | None = None) -> dict[str, Any]:
    t = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {
        "at": t.isoformat(timespec="seconds"),
        "definitions": {
            "confident_kill": "passed False at a MEASURED gate statistic "
                              f"({', '.join(sorted(MEASURED_STAT_GATES))}), or at a fail-closed "
                              "gate whose own stage proves it measured",
            "unconfident": "UNKNOWN terminal gate, NOT_RUN_* (build/data failure, deferral, "
                           "timeout), fail-closed gate without proof of measurement, "
                           "unrecognised gate",
            "screen_reject": "gate-0 refusal on a fact (economic_prior, symbol_eligibility)",
            "judged": "distinct cells whose verdict the sealed judge RECORDED that UTC day "
                      "(it appends on change), one per cell",
            "kill_confidence": "confident_kills / judged, Wilson 95% interval"},
        "stale_after_h": STALE_H,
    }
    led = read_ledger(ledger)
    if led["status"] != "MEASURED":
        doc.update(status=UNMEASURED, why=led["why"], confident_kills_per_day=UNMEASURED,
                   kill_confidence=UNMEASURED, per_day=[])
        return doc
    last = datetime.fromisoformat(led["last_at"].replace("Z", "+00:00")).astimezone(UTC)
    age_h = round((t - last).total_seconds() / 3600.0, 2)
    first_day, last_day = _day(led["first_at"]), _day(led["last_at"])
    cores = core_hours_by_day(compute)
    per_day: list[dict[str, Any]] = []
    for i in range(PER_DAY_DAYS - 1, -1, -1):
        day = (t - timedelta(days=i)).date().isoformat()
        if first_day is None or last_day is None or day < first_day or day > last_day:
            per_day.append({"day": day, "status": UNMEASURED,
                            "why": "outside the ledger's recorded span"})
            continue
        row: dict[str, Any] = {"day": day, "status": "MEASURED",
                               "partial": day == t.date().isoformat(),
                               **_tally(led["days"].get(day, {}))}
        ch = cores.get(day)
        row["judge_core_hours"] = round(ch, 4) if ch else UNMEASURED
        row["confident_kills_per_core_hour"] = (round(row["confident_kills"] / ch, 3) if ch
                                                else UNMEASURED)
        per_day.append(row)
    doc.update(ledger={"rows": led["rows"], "unreadable_rows": led["unreadable_rows"],
                       "first_at": led["first_at"], "last_at": led["last_at"], "age_h": age_h},
               per_day=per_day)
    if age_h > STALE_H:
        doc.update(status=UNMEASURED, confident_kills_per_day=UNMEASURED,
                   kill_confidence=UNMEASURED,
                   why=f"verdict ledger's newest row is {age_h}h old (> {STALE_H}h): a stale "
                       "ledger is UNMEASURED, never a zero-kill day")
        return doc
    complete = [d for d in per_day if d["status"] == "MEASURED" and not d["partial"]]
    window = complete[-HEADLINE_DAYS:]
    if not window:
        today = [d for d in per_day if d["status"] == "MEASURED"]
        window = today[-1:]
    kills = sum(d["confident_kills"] for d in window)
    judged = sum(d["judged"] for d in window)
    ch = [d["judge_core_hours"] for d in window if isinstance(d["judge_core_hours"], float)]
    doc.update(
        status="MEASURED",
        headline_days=[d["day"] for d in window],
        headline_basis=("complete UTC days" if not window[-1]["partial"]
                        else "today only (partial): the ledger has no complete day yet"),
        confident_kills_per_day=round(kills / len(window), 2),
        judged_per_day=round(judged / len(window), 2),
        survivors_per_day=round(sum(d["survivors"] for d in window) / len(window), 2),
        unconfident_per_day=round(sum(d["unconfident"] for d in window) / len(window), 2),
        kill_confidence=(round(kills / judged, 6) if judged else UNMEASURED),
        kill_confidence_wilson95=wilson(kills, judged),
        confident_kills_per_core_hour=(
            round(kills / sum(ch), 3) if len(ch) == len(window) and sum(ch) > 0 else UNMEASURED))
    return doc


def write(doc: dict[str, Any], out: Path | None = None) -> Path:
    p = OUT if out is None else out
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".json.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = build()
    print(f"rejection throughput: {doc.get('status')} confident_kills/day="
          f"{doc.get('confident_kills_per_day')} kill_confidence={doc.get('kill_confidence')} "
          f"wilson95={doc.get('kill_confidence_wilson95')} "
          f"per_core_hour={doc.get('confident_kills_per_core_hour')}"
          + (f" -- {doc['why']}" if doc.get("why") else ""))
    if not a.dry_run:
        print(f"-> {write(doc)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
