#!/usr/bin/env python3
"""EVERY SILENT ORGAN, BY NAME, AND A FENCE THAT TURNS RED ON A NEW ONE.

THE PRINCIPAL'S STANDING ORDER: eliminate silent research organs to 100%, every day.

WHY A PER-ORGAN LIST, NOT A NUMBER. The CRO noon pass of 2026-09-30 read "101 silent scheduled
failures (71 NOT_SCHEDULED)" off `tier1_scorecard`, which sums two counters: process_health's
FAILING+NOT_SCHEDULED and the hourly cycle's LEG_FAILED/TIMEOUT legs. A sum cannot be triaged --
nobody can act on 101 -- and it hid its own largest defect: the contract table held exactly 71
organs that day, and exactly 71 were NOT_SCHEDULED, because a scheduler read that returned
nothing was joined as "no organ is scheduled". Named rows would have shown the hourly cycle
itself on that list while it was writing the ledger the review read.

WHAT IT READS, both written by organs that already run:

    desks/mt5/reports/process_health.json   every scheduled task and contract (MT5-ProcessHealth)
    desks/mt5/data/sync_marker.json         every hourly-cycle leg's last outcome (MT5-Hourly)

A task row is SILENT when its verdict is NOT_SCHEDULED, FAILING, NO_ARTIFACT or STALE. A leg is
SILENT when it raised (LEG_FAILED), was killed at its cap (a `timeout_s` with no exit code, which
`_producer` returns WITHOUT a status field -- so the scorecard's status-only count missed every
one of them), or its script is MISSING.

THE FENCE. The previous reading is this organ's own artifact. An organ silent now and not silent
then is NEW; any NEW organ turns the status RED and the process exits 2, which the hourly cycle
records as a declared verdict (`verdict_exit=2`), not a crash. Silence that persists stays AMBER
with its streak counted, so a standing defect never goes quiet by becoming familiar. An organ
that recovers is listed under `cleared`.

UNMEASURED IS NEVER ZERO (L1.28a). A missing input is named; a process_health whose scheduler
could not be read contributes its artifact-clock verdicts only and says so.

    python scripts/check_silent_organs.py            # write the artifact, exit 2 on a new one
    python scripts/check_silent_organs.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT / "desks" / "mt5"
PROCESS_HEALTH = DESK / "reports" / "process_health.json"
SYNC_MARKER = DESK / "data" / "sync_marker.json"
OUT = DESK / "reports" / "SILENT_ORGANS.json"

SILENT_TASK_VERDICTS = frozenset({"NOT_SCHEDULED", "FAILING", "NO_ARTIFACT", "STALE"})
SILENT_LEG_STATUSES = frozenset({"LEG_FAILED", "TIMEOUT", "MISSING"})
#: Exit code for "a new organ went silent" -- declared in hourly_cycle.VERDICT_EXITS.
RED_EXIT = 2


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _age_min(path: Path, now: datetime) -> float | None:
    try:
        return round((now.timestamp() - path.stat().st_mtime) / 60.0, 1)
    except OSError:
        return None


def task_silences(doc: Any) -> list[dict[str, Any]]:
    """Silent rows of process_health, one per organ."""
    out: list[dict[str, Any]] = []
    for r in (doc.get("processes") if isinstance(doc, dict) else None) or []:
        if not isinstance(r, dict):
            continue
        verdict = str(r.get("verdict") or "")
        if verdict in SILENT_TASK_VERDICTS:
            out.append({"organ": str(r.get("name") or ""), "source": "task",
                        "verdict": verdict, "why": str(r.get("why") or "")[:240],
                        "artifact": r.get("artifact")})
    return out


def leg_verdict(leg: Any) -> tuple[str, str] | None:
    """(verdict, why) for a silent leg outcome, or None when the leg is not silent."""
    if not isinstance(leg, dict):
        return None
    status = str(leg.get("status") or "").upper()
    if leg.get("error"):
        return "LEG_FAILED", str(leg.get("error"))[:240]
    if status in SILENT_LEG_STATUSES:
        return status, str(leg.get("why") or leg.get("note") or "")[:240]
    if leg.get("timeout_s") and leg.get("exit_code") is None:
        return "TIMEOUT", (f"killed at its {leg.get('timeout_s')}s cap before it finished; "
                           "whatever it had not written is lost for the hour")
    return None


def leg_silences(marker: Any) -> list[dict[str, Any]]:
    """Silent legs of the last completed hourly pass, one per leg."""
    out: list[dict[str, Any]] = []
    if not isinstance(marker, dict):
        return out
    for name, leg in sorted(marker.items()):
        v = leg_verdict(leg)
        if v:
            out.append({"organ": f"leg:{name}", "source": "leg", "verdict": v[0], "why": v[1],
                        "artifact": None})
    return out


def build(*, health_path: Path | None = None, marker_path: Path | None = None,
          previous: Any = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    health_path = health_path or PROCESS_HEALTH
    marker_path = marker_path or SYNC_MARKER
    health, marker = _read(health_path), _read(marker_path)
    unmeasured: list[dict[str, str]] = []
    if not isinstance(health, dict):
        unmeasured.append({"what": "scheduled tasks and contracts",
                           "why": f"{health_path.name} is absent or unreadable -- "
                                  "ops/process_health.py has not run on this host"})
    elif isinstance(health.get("scheduler"), dict) and not health["scheduler"].get("read") \
            and not health["scheduler"].get("existence_only"):
        unmeasured.append({"what": "scheduling verdicts (NOT_SCHEDULED / FAILING)",
                           "why": "process_health could not read the scheduler: "
                                  + str(health["scheduler"].get("why") or "")})
    if not isinstance(marker, dict):
        unmeasured.append({"what": "hourly-cycle legs",
                           "why": f"{marker_path.name} is absent or unreadable -- the hourly "
                                  "cycle has not completed a pass on this host"})

    silent = task_silences(health) + leg_silences(marker)
    prev_rows = {}
    if isinstance(previous, dict):
        prev_rows = {str(r.get("organ")): r for r in previous.get("organs") or []
                     if isinstance(r, dict)}
    has_baseline = isinstance(previous, dict) and previous.get("status") != "UNMEASURED"
    stamp = now.isoformat(timespec="seconds")
    new: list[str] = []
    for row in silent:
        before = prev_rows.get(row["organ"])
        row["first_seen"] = (before or {}).get("first_seen") or stamp
        row["passes_silent"] = int((before or {}).get("passes_silent") or 0) + 1
        if has_baseline and before is None:
            new.append(row["organ"])
    now_names = {r["organ"] for r in silent}
    cleared = sorted(n for n in prev_rows if n not in now_names)

    by_verdict: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for r in silent:
        by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1

    if not isinstance(health, dict) and not isinstance(marker, dict):
        status = "UNMEASURED"
    elif new:
        status = "RED"
    elif silent:
        status = "AMBER"
    else:
        status = "GREEN"
    silent.sort(key=lambda r: (r["organ"] not in new, -r["passes_silent"], r["organ"]))
    return {
        "measured_at": stamp,
        "at": stamp,
        "status": status,
        # A count is only a count when every source was read; otherwise it is a floor.
        "n_silent": len(silent) if not unmeasured else None,
        "n_silent_floor": len(silent),
        "by_verdict": by_verdict,
        "by_source": by_source,
        "new_silent": sorted(new),
        "cleared": cleared,
        "baseline": "previous reading of this artifact" if has_baseline else
                    "none -- first reading; the next pass fences against this one",
        "inputs": {
            "process_health": {"path": str(health_path.relative_to(ROOT))
                               if health_path.is_relative_to(ROOT) else str(health_path),
                               "age_min": _age_min(health_path, now),
                               "at": health.get("at") if isinstance(health, dict) else None},
            "sync_marker": {"path": str(marker_path.relative_to(ROOT))
                            if marker_path.is_relative_to(ROOT) else str(marker_path),
                            "age_min": _age_min(marker_path, now),
                            "at": marker.get("last_cycle") if isinstance(marker, dict) else None},
        },
        "unmeasured": unmeasured,
        "organs": silent,
        "rule": ("an organ silent now and not silent in the previous reading is NEW and turns "
                 "the fence RED; persisting silence is AMBER with its streak; UNMEASURED is "
                 "never zero"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    doc = build(previous=_read(a.out))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    tmp = a.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    tmp.replace(a.out)
    if a.json:
        print(json.dumps(doc, indent=1))
    else:
        n = doc["n_silent"] if doc["n_silent"] is not None else f">={doc['n_silent_floor']}"
        print(f"silent organs: {n}  status {doc['status']}  new {len(doc['new_silent'])}  "
              f"cleared {len(doc['cleared'])}  {doc['by_verdict']}")
        for r in doc["organs"]:
            flag = "NEW " if r["organ"] in doc["new_silent"] else "    "
            print(f"  {flag}{r['verdict']:<14}{r['organ']:<44}x{r['passes_silent']:<4}"
                  f"{r['why'][:70]}")
        for u in doc["unmeasured"]:
            print(f"  UNMEASURED {u['what']}: {u['why']}")
        print(f"-> {a.out}")
    return RED_EXIT if doc["status"] == "RED" else 0


if __name__ == "__main__":
    sys.exit(main())
