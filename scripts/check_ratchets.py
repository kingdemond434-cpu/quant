"""RATCHET FENCE -- constitution L1.0 / L2.0 made mechanical (principal order 2026-07-29).

L1.0: no measurable property of this desk is allowed to sit still. Today's value is the permanent
FLOOR; the standing target is 100%; the GAP between them is the work queue. The proving instance is
test strength -- measured for the first time at 55% on 2026-07-29 and closed to 90% the same
session. That is the required tempo, not a highlight.

A law with no fence is prose (L2.2), so this is the fence. It reads every committed floor artifact,
reports each metric as `value (floor, distance-to-100%)`, and FAILS when:
  * a metric fell below its recorded floor          -> a regression, the thing ratchets forbid
  * a metric's artifact is missing or stale         -> unmeasured is a defect, not a pass
  * a NEW metric appears with no floor recorded     -> a number without a floor is a defect

FLOORS ONLY RISE. `--ratchet` records improvements (and only improvements) into
data/ratchet_floors.json; nothing here can ever lower a floor, because lowering a floor to match a
regression is the denominator trick §34 forbids one level up. A metric is never retired to avoid a
falling number: retirement needs a written reason in the register.

WHAT IS DELIBERATELY NOT HERE: thresholds for what is "good". This fence measures direction and
distance, never quality -- quality bars live in the gates that own them and are not touched by it.

    python scripts/check_ratchets.py [--json] [--ratchet] [--report-only]
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
_FLOORS = _ROOT / "data/ratchet_floors.json"
_OUT = _ROOT / "data/ratchet_report.json"


def _j(path: Path) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _age_h(path: Path) -> float | None:
    try:
        return (time.time() - path.stat().st_mtime) / 3600.0
    except OSError:
        return None


# metric -> (artifact, extractor, max_staleness_hours, proving command)
# Every entry states the command that proves it, per L2.4: a claim without its command is not a
# measurement. max_age None = no staleness requirement (a floor artifact that only changes when the
# underlying work does).
def _mutation_targets(d: Any) -> dict[str, float]:
    """Per-target kill rates. PER-TARGET IS THE CORRECT SHAPE, and the first version got it wrong:
    a single `min()` across targets meant MEASURING A NEW FILE looked like a REGRESSION (staging
    entered at 83.3% and dragged the aggregate down from stepwise's 90%). A fence that fires when
    the desk measures MORE trains everyone to ignore it -- the opposite of L1.0. Each target now
    carries its own floor, and the aggregate below is a coverage number, not a min."""
    if not isinstance(d, dict):
        return {}
    out: dict[str, float] = {}
    for t in d.get("targets", []):
        if (isinstance(t, dict) and isinstance(t.get("kill_rate"), (int, float))
                and t.get("total")):
            out[str(t.get("target"))] = float(t["kill_rate"])
    return out


def _mutation_at_bar(d: Any) -> float | None:
    """Share of MEASURED targets meeting the v8 8.2 bar -- itself a ratchet toward 100%."""
    rates = _mutation_targets(d)
    if not rates:
        return None
    return sum(1 for v in rates.values() if v >= 0.90) / len(rates)


def _findings_coverage(d: Any) -> float | None:
    if not isinstance(d, dict):
        return None
    for k in ("coverage", "coverage_pct", "best_coverage"):
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v) / (100.0 if float(v) > 1.0 else 1.0)
    return None


def _miner_productive(d: Any) -> float | None:
    if not isinstance(d, dict):
        return None
    seats = d.get("seats")
    if not isinstance(seats, dict) or not seats:
        return None
    ok = sum(1 for r in seats.values() if isinstance(r, dict) and r.get("status") == "ok")
    return ok / len(seats)


def _mypy_clean(d: Any) -> float | None:
    """Share of scripts with ZERO strict errors -- rises as tranches land."""
    if not isinstance(d, dict):
        return None
    per = d.get("per_file")
    if not isinstance(per, dict) or not per:
        return None
    clean = sum(1 for v in per.values() if isinstance(v, (int, float)) and int(v) == 0)
    return clean / len(per)


def _alert_delivery(path: Path) -> float | None:
    try:
        lines = path.read_text("utf-8").splitlines()[-500:]
    except OSError:
        return None
    floor = time.time() - 24 * 3600
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not row.get("ok"):
            continue
        ts = str(row.get("ts", ""))
        try:
            if datetime.fromisoformat(ts).timestamp() >= floor:
                return 1.0
        except ValueError:
            continue
    return 0.0


_METRICS: dict[str, tuple[str, Callable[[Any], float | None], float | None, str]] = {
    "test_strength_targets_at_bar": (
        "data/mutation_score.json", _mutation_at_bar, None,
        "python scripts/run_mutation.py"),
    "findings_coverage": (
        "docs/research/findings_coverage_record.json", _findings_coverage, None,
        "python scripts/max_audit.py (check_findings_tracked)"),
    "miner_seats_productive": (
        "data/miner_runway.json", _miner_productive, 48.0,
        "python scripts/check_miner_runway.py --json --report-only"),
    "scripts_mypy_clean": (
        "data/mypy_ratchet.json", _mypy_clean, None,
        "python scripts/check_mypy_ratchet.py"),
}
# Artifacts read as raw files rather than parsed JSON documents.
_FILE_METRICS: dict[str, tuple[str, Callable[[Path], float | None], float | None, str]] = {
    "pager_delivered_24h": (
        "data/alert_delivery.jsonl", _alert_delivery, None,
        "python scripts/run_alert_canary.py"),
}


def evaluate() -> dict[str, Any]:
    floors = _j(_FLOORS) or {}
    rows: list[dict[str, Any]] = []

    def _row(name: str, artifact: str, value: float | None, age: float | None,
             max_age: float | None, cmd: str) -> dict[str, Any]:
        floor = floors.get(name, {}).get("value") if isinstance(floors.get(name), dict) else None
        stale = (max_age is not None and age is not None and age > max_age)
        if value is None:
            status = "UNMEASURED"            # never a pass: unmeasured is a defect (L1.0a)
        elif floor is None:
            status = "NO-FLOOR"              # a number without a floor is a defect
        elif value + 1e-9 < float(floor):
            status = "REGRESSION"
        elif stale:
            status = "STALE"
        elif value >= 0.999:
            status = "AT-100"
        else:
            status = "OK"
        return {"metric": name, "artifact": artifact, "value": value,
                "floor": floor, "distance_to_100": (None if value is None
                                                    else round(1.0 - value, 4)),
                "age_h": None if age is None else round(age, 1),
                "max_age_h": max_age, "status": status, "proving_command": cmd}

    for name, (rel, fn, max_age, cmd) in _METRICS.items():
        path = _ROOT / rel
        rows.append(_row(name, rel, fn(_j(path)), _age_h(path), max_age, cmd))
    for name, (rel, ffn, max_age, cmd) in _FILE_METRICS.items():
        path = _ROOT / rel
        rows.append(_row(name, rel, ffn(path), _age_h(path), max_age, cmd))
    # DYNAMIC per-target mutation rows: a metric is born with its own floor the day it is first
    # measured (L2.0), so newly measured files enter as NO-FLOOR -> floored, never as regressions.
    mut_path = _ROOT / "data/mutation_score.json"
    for target, rate in sorted(_mutation_targets(_j(mut_path)).items()):
        rows.append(_row(f"test_strength::{target}", "data/mutation_score.json", rate,
                         _age_h(mut_path), None,
                         f"python scripts/run_mutation.py --target {target}"))

    bad = [r for r in rows if r["status"] in ("REGRESSION", "STALE", "NO-FLOOR", "UNMEASURED")]
    # THE WORK QUEUE (L1.0c): measured metrics ranked by how far they sit from 100%.
    queue = sorted((r for r in rows if isinstance(r["distance_to_100"], float)
                    and r["distance_to_100"] > 0.001),
                   key=lambda r: -float(r["distance_to_100"]))
    return {"checked": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "law": "L1.0 universal ratchet -- today's value is the floor, 100% is the target, "
                   "the gap is the work queue",
            "rows": rows, "n_bad": len(bad),
            "work_queue": [{"metric": r["metric"], "value": r["value"],
                            "distance_to_100": r["distance_to_100"]} for r in queue]}


def ratchet_up(report: dict[str, Any]) -> dict[str, Any]:
    """Record IMPROVEMENTS only. This function cannot lower a floor -- by construction, because a
    floor lowered to match a regression is exactly the failure the ratchet exists to prevent."""
    floors = _j(_FLOORS) or {}
    raised: list[str] = []
    for r in report["rows"]:
        v = r["value"]
        if not isinstance(v, (int, float)):
            continue
        cur = floors.get(r["metric"], {}).get("value") if isinstance(
            floors.get(r["metric"]), dict) else None
        if cur is None or float(v) > float(cur) + 1e-9:
            floors[r["metric"]] = {"value": round(float(v), 6),
                                   "recorded": report["checked"],
                                   "artifact": r["artifact"],
                                   "proving_command": r["proving_command"]}
            raised.append(f"{r['metric']} -> {float(v):.4f}"
                          + ("" if cur is None else f" (was {float(cur):.4f})"))
    _FLOORS.parent.mkdir(parents=True, exist_ok=True)
    _FLOORS.write_text(json.dumps(floors, indent=2, sort_keys=True), "utf-8")
    return {"raised": raised, "n_floors": len(floors)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ratchet", action="store_true",
                    help="record improvements as the new floors (never lowers one)")
    ap.add_argument("--report-only", action="store_true", help="always exit 0")
    args = ap.parse_args()

    rep = evaluate()
    if args.ratchet:
        rep["ratchet"] = ratchet_up(rep)
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(rep, indent=2), "utf-8")

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(f"ratchets | {rep['n_bad']} defect(s) | "
              f"{len(rep['work_queue'])} metric(s) below 100%")
        for r in rep["rows"]:
            val = "n/a" if r["value"] is None else f"{float(r['value']):.1%}"
            flr = "none" if r["floor"] is None else f"{float(r['floor']):.1%}"
            dist = "" if r["distance_to_100"] is None else f" gap {float(r['distance_to_100']):.1%}"
            print(f"  {r['status']:11} {r['metric']:30} {val:>7} (floor {flr}{dist})")
        if rep["work_queue"]:
            top = rep["work_queue"][0]
            print(f"  -> largest gap: {top['metric']} at {float(top['value']):.1%}, "
                  f"{float(top['distance_to_100']):.1%} from 100%")
        for line in rep.get("ratchet", {}).get("raised", []):
            print(f"  FLOOR RAISED {line}")
    return 0 if args.report_only else (1 if rep["n_bad"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
