#!/usr/bin/env python3
"""Finish the canonical MT5 research front-half before the midnight reasoner runs.

This is deliberately an orchestrator, not another gauntlet, certifier, forward engine, or
promotion authority.  It asks the existing systemd services and projections to complete work
left by any earlier controller, records every result, and leaves capital authority untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "intelligence" / "midnight_completion.json"
TERMINAL_PREFIXES = ("RETIRED", "KILL", "QUARANTIN", "DEAD", "REJECT", "PROMOTED")


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    accepted_returncodes: frozenset[int] = frozenset({0})
    diagnostic: bool = False


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def canonical_stages(python: str = sys.executable) -> tuple[Stage, ...]:
    """Dependency order only; each command remains the authority for its own stage."""
    return (
        Stage("canonical_external_pipeline",
              ("systemctl", "--user", "start", "quant-external-pipeline.service"), 7_500),
        Stage("external_queue_projection", (python, "scripts/promote_external_to_queue.py"), 300),
        Stage("external_queue_reconciliation",
              (python, "scripts/reconcile_external_queue.py"), 300),
        Stage("certificate_projection", (python, "scripts/build_gauntlet_survivors.py"), 300),
        Stage("forward_lane_heal", (python, "scripts/heal_forward_lane.py"), 900),
        Stage("zero_capital_shadow_forward",
              ("systemctl", "--user", "start", "shadow-forward.service"), 1_800),
        Stage("same_day_fence", (python, "scripts/check_sameday_pipeline.py"), 300,
              frozenset({0, 1}), True),
        Stage("certificate_yield_fence", (python, "scripts/check_cert_yield.py"), 300,
              frozenset({0, 1, 2}), True),
        Stage("forward_clock_fence", (python, "scripts/check_forward_clock_ratchet.py"), 300,
              frozenset({0, 1, 2}), True),
    )


def _read(path: Path, default):
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _survivor_count(doc: object) -> int:
    if not isinstance(doc, dict):
        return 0
    rows = doc.get("survivors", doc)
    return len(rows) if isinstance(rows, (dict, list)) else 0


def _forward_count(shadow: Path) -> int:
    keys: set[str] = set()
    for path in shadow.glob("*shadow_state.json"):
        doc = _read(path, {})
        if not isinstance(doc, dict):
            continue
        rows = list(doc.items())
        if isinstance(doc.get("sleeves"), dict):
            rows.extend(doc["sleeves"].items())
        for key, row in rows:
            if not isinstance(row, dict) or "status" not in row:
                continue
            status = str(row.get("status") or "").upper()
            if not status.startswith(TERMINAL_PREFIXES):
                keys.add(str(key))
    return len(keys)


def snapshot(root: Path) -> dict[str, object]:
    desk = root / "desks" / "mt5"
    queue = _read(desk / "data" / "research_queue.json", [])
    statuses: dict[str, int] = {}
    if isinstance(queue, list):
        for row in queue:
            if isinstance(row, dict):
                status = str(row.get("status") or "UNKNOWN")
                statuses[status] = statuses.get(status, 0) + 1
    docket = _read(desk / "data" / "hypotheses" / "external_survivors.json", [])
    if isinstance(docket, dict):
        docket = docket.get("survivors", [])
    return {
        "queue_total": len(queue) if isinstance(queue, list) else 0,
        "queue_by_status": dict(sorted(statuses.items())),
        "external_screen_survivors": len(docket) if isinstance(docket, list) else 0,
        "universal_certificates": _survivor_count(
            _read(desk / "reports" / "UNIVERSAL_SURVIVORS.json", {})
        ),
        "active_forward_clocks": _forward_count(desk / "reports" / "shadow"),
    }


def _run(command: tuple[str, ...], timeout: int, root: Path) -> CommandResult:
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True,
                                timeout=timeout, check=False)
        return CommandResult(result.returncode, result.stdout or "", result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return CommandResult(124, str(exc.stdout or ""), f"timeout after {timeout}s")
    except OSError as exc:
        return CommandResult(127, "", str(exc))


def _write_atomic(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     delete=False) as handle:
        json.dump(value, handle, indent=1, sort_keys=True)
        temporary = Path(handle.name)
    os.replace(temporary, path)


Runner = Callable[[tuple[str, ...], int, Path], CommandResult]


def execute(root: Path, stages: Iterable[Stage], runner: Runner = _run,
            output: Path | None = None) -> dict[str, object]:
    started = datetime.now(UTC)
    before = snapshot(root)
    results: list[dict[str, object]] = []
    hard_failures: list[str] = []
    findings: list[str] = []
    for stage in stages:
        tick = time.monotonic()
        result = runner(stage.command, stage.timeout_seconds, root)
        accepted = result.returncode in stage.accepted_returncodes
        if not accepted:
            hard_failures.append(stage.name)
        elif stage.diagnostic and result.returncode != 0:
            findings.append(stage.name)
        results.append({
            "name": stage.name,
            "command": list(stage.command),
            "returncode": result.returncode,
            "accepted": accepted,
            "diagnostic_finding": stage.diagnostic and result.returncode != 0,
            "duration_seconds": round(time.monotonic() - tick, 3),
            "stdout_tail": result.stdout[-2_000:],
            "stderr_tail": result.stderr[-2_000:],
        })
    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "started_at": started.isoformat(),
        "authority": (
            "ORCHESTRATION_ONLY; no gate, certificate, promotion, sizing or order authority"
        ),
        "before": before,
        "after": snapshot(root),
        "stages": results,
        "hard_failures": hard_failures,
        "diagnostic_findings": findings,
        "needs_controller": bool(hard_failures or findings),
        "complete": not hard_failures,
    }
    _write_atomic(output or root / OUT.relative_to(ROOT), report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--plan", action="store_true",
                        help="print the canonical completion plan without running it")
    args = parser.parse_args()
    stages = canonical_stages(os.environ.get("PYTHON", sys.executable))
    if args.plan:
        print(json.dumps({"snapshot": snapshot(args.root.resolve()),
                          "stages": [{"name": s.name, "command": list(s.command)}
                                     for s in stages]}, indent=1))
        return 0
    report = execute(args.root.resolve(), stages)
    print(json.dumps({"complete": report["complete"],
                      "needs_controller": report["needs_controller"],
                      "hard_failures": report["hard_failures"],
                      "diagnostic_findings": report["diagnostic_findings"],
                      "before": report["before"], "after": report["after"]}, indent=1))
    return 1 if report["hard_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
