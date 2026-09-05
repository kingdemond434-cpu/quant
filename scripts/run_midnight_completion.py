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
from zoneinfo import ZoneInfo

try:
    import resource
except ImportError:  # pragma: no cover - Windows development host
    resource = None

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "data" / "intelligence" / "midnight_completion.json"
CHECKPOINT = ROOT / "data" / "intelligence" / "midnight_completion_checkpoint.json"
TERMINAL_PREFIXES = ("RETIRED", "KILL", "QUARANTIN", "DEAD", "REJECT", "PROMOTED")


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    timeout_seconds: int
    accepted_returncodes: frozenset[int] = frozenset({0})
    diagnostic: bool = False
    catch_up: bool = False


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    cpu_seconds: float | None = None


def canonical_stages(python: str = sys.executable) -> tuple[Stage, ...]:
    """Dependency order only; each command remains the authority for its own stage."""
    return (
        Stage("canonical_external_pipeline",
              ("systemctl", "--user", "start", "quant-external-pipeline.service"), 7_500,
              catch_up=True),
        Stage("external_queue_projection", (python, "scripts/promote_external_to_queue.py"), 300),
        Stage("external_queue_reconciliation",
              (python, "scripts/reconcile_external_queue.py"), 300),
        Stage("certificate_projection", (python, "scripts/build_gauntlet_survivors.py"), 300),
        Stage("fusion_state_pull",
              ("systemctl", "--user", "start", "quant-desk-pull.service"), 900),
        Stage("forward_identity_reconciliation",
              (python, "desks/mt5/research/forward_reconcile.py"), 1_800),
        Stage("forward_clock_reconciliation", (python, "scripts/check_forward_clock.py"), 300),
        Stage("forward_lane_heal", (python, "scripts/heal_forward_lane.py"), 900),
        Stage("zero_capital_shadow_forward",
              ("systemctl", "--user", "start", "shadow-forward.service"), 1_800),
        Stage("mechanism_independence",
              (python, "desks/mt5/research/portfolio_evidence.py"), 600),
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
    before_cpu = _cpu_usage(command, root)
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True,
                                timeout=timeout, check=False)
        after_cpu = _cpu_usage(command, root)
        used = max(0.0, after_cpu - before_cpu) if None not in (before_cpu, after_cpu) else None
        return CommandResult(result.returncode, result.stdout or "", result.stderr or "", used)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(124, str(exc.stdout or ""), f"timeout after {timeout}s")
    except OSError as exc:
        return CommandResult(127, "", str(exc))


def _cpu_usage(command: tuple[str, ...], root: Path) -> float | None:
    """CPU seconds for a systemd service or this process's children."""
    if command[:3] == ("systemctl", "--user", "start") and len(command) > 3:
        try:
            measured = subprocess.run(
                ("systemctl", "--user", "show", command[3], "-p", "CPUUsageNSec", "--value"),
                cwd=root, text=True, capture_output=True, timeout=30, check=False,
            )
            return float(measured.stdout.strip() or 0) / 1_000_000_000
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None
    if resource is None:
        return None
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return float(usage.ru_utime + usage.ru_stime)


def _external_outstanding(root: Path) -> int | None:
    report = _read(root / "desks" / "mt5" / "reports" / "universal_gates_external.json", None)
    if not isinstance(report, dict):
        return None
    discovered = report.get("n_cells_discovered")
    verdicts = report.get("verdicts")
    if not isinstance(discovered, int) or not isinstance(verdicts, list):
        return None
    named = {str(row.get("cell")) for row in verdicts
             if isinstance(row, dict) and row.get("cell")}
    deferred = sum(
        isinstance(row, dict) and "DEFERRED" in str(row.get("downstream_status") or "")
        for row in verdicts
    )
    return int(deferred + max(0, discovered - len(named)))


def _resource_state(root: Path) -> dict[str, object]:
    available = None
    try:
        for line in Path("/proc/meminfo").read_text("utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                available = round(int(line.split()[1]) / 1024, 1)
                break
    except OSError:
        pass
    try:
        service = (root / "ops" / "quant-external-pipeline.service").read_text(
            "utf-8", errors="ignore"
        )
    except OSError:
        service = ""
    memory_max = next((line.split("=", 1)[1] for line in service.splitlines()
                       if line.startswith("MemoryMax=")), None)
    return {
        "mem_available_mb": available,
        "external_pipeline_memory_max": memory_max,
        "collision_control": ("systemd uses one quant-external-pipeline.service instance; hourly "
                              "and midnight starts cannot duplicate the heavy worker"),
        "remote_control": "desk-box job locks and per-stage timeouts remain authoritative",
    }


def _cycle_id() -> str:
    return datetime.now(ZoneInfo("Europe/Dublin")).date().isoformat()


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
    checkpoint_path = root / CHECKPOINT.relative_to(ROOT)
    checkpoint = _read(checkpoint_path, {})
    cycle = _cycle_id()
    if not isinstance(checkpoint, dict) or checkpoint.get("cycle") != cycle:
        checkpoint = {"schema_version": 1, "cycle": cycle, "stages": {}}
    results: list[dict[str, object]] = []
    hard_failures: list[str] = []
    deferred_stages: list[str] = []
    findings: list[str] = []
    for stage in stages:
        stage_before = snapshot(root)
        tick = time.monotonic()
        passes: list[dict[str, object]] = []
        prior_outstanding: int | None = None
        while True:
            checkpoint["updated_at"] = datetime.now(UTC).isoformat()
            checkpoint["stages"][stage.name] = {
                "status": "RUNNING", "started_at": checkpoint["updated_at"],
                "command": list(stage.command), "passes_completed": len(passes),
            }
            _write_atomic(checkpoint_path, checkpoint)
            result = runner(stage.command, stage.timeout_seconds, root)
            outstanding = _external_outstanding(root) if stage.catch_up else None
            passes.append({"returncode": result.returncode, "cpu_seconds": result.cpu_seconds,
                           "outstanding_after": outstanding})
            if result.returncode not in stage.accepted_returncodes or not stage.catch_up:
                break
            if outstanding is None:
                result = CommandResult(
                    76, result.stdout,
                    "canonical catch-up produced no readable conservation report",
                    result.cpu_seconds,
                )
                break
            if not outstanding:
                break
            if prior_outstanding is not None and outstanding >= prior_outstanding:
                result = CommandResult(
                    75, result.stdout,
                    f"canonical catch-up made no progress: {outstanding} cells remain",
                    result.cpu_seconds,
                )
                break
            prior_outstanding = outstanding
        # A catch-up service can have completed cleanly while its remote, single-writer worker
        # is still alive.  A second immediate invocation then observes the same deferred census
        # and produces this sentinel.  That is not a broken pipeline: calling it one used to
        # ask the controller to contend with the worker that the resource fence deliberately
        # kept serial.  Keep the debt loud and the cycle incomplete, but distinguish it from a
        # failed command so the repair path can wait for the live owner rather than duplicate it.
        resource_deferred = (
            stage.catch_up
            and result.returncode == 75
            and result.stderr.startswith("canonical catch-up made no progress:")
        )
        accepted = result.returncode in stage.accepted_returncodes or resource_deferred
        if resource_deferred:
            deferred_stages.append(stage.name)
        elif not accepted:
            hard_failures.append(stage.name)
        elif stage.diagnostic and result.returncode != 0:
            findings.append(stage.name)
        stage_after = snapshot(root)
        stage_row = {
            "name": stage.name,
            "command": list(stage.command),
            "returncode": result.returncode,
            "accepted": accepted,
            "deferred_resource": resource_deferred,
            "diagnostic_finding": stage.diagnostic and result.returncode != 0,
            "duration_seconds": round(time.monotonic() - tick, 3),
            "cpu_seconds": (round(sum(float(row.get("cpu_seconds") or 0.0)
                                      for row in passes), 6)
                            if any(row.get("cpu_seconds") is not None for row in passes) else None),
            "certificate_delta": (int(stage_after["universal_certificates"])
                                  - int(stage_before["universal_certificates"])),
            "passes": passes,
            "stdout_tail": result.stdout[-2_000:],
            "stderr_tail": result.stderr[-2_000:],
        }
        results.append(stage_row)
        checkpoint["updated_at"] = datetime.now(UTC).isoformat()
        checkpoint["stages"][stage.name] = {
            "status": ("DEFERRED_RESOURCE" if resource_deferred
                       else "DONE" if accepted else "FAILED"),
            "finished_at": checkpoint["updated_at"],
            "returncode": result.returncode,
            "passes_completed": len(passes),
        }
        _write_atomic(checkpoint_path, checkpoint)
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
        "deferred_stages": deferred_stages,
        "diagnostic_findings": findings,
        "needs_controller": bool(hard_failures or deferred_stages or findings),
        "complete": not hard_failures and not deferred_stages,
        "resource_execution": _resource_state(root),
        "checkpoint": str(checkpoint_path.relative_to(root)),
    }
    _write_atomic(output or root / OUT.relative_to(ROOT), report)
    from scripts.build_midnight_operations_report import build as build_morning_report
    morning = build_morning_report(root, report)
    report["morning_report"] = str(
        (root / "data" / "intelligence" / "midnight_morning_report.json").relative_to(root)
    )
    report["candidate_conservation"] = morning["candidate_conservation"]
    if morning["candidate_conservation"]["lost"]:
        report["needs_controller"] = True
        report["complete"] = False
        findings.append("candidate_conservation")
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
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
