"""Run the MT5 evidence-pipeline self-heal and publish its measured result.

This is deliberately separate from :mod:`desk_self_heal`: the audit module is kept incapable of
process launch or file mutation by an AST fence.  This thin actuator may only re-run the existing
producer task named by that audit.  It cannot promote, size, arm, edit a gate, or place an order.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import desk_self_heal as heal

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
REPORT = DESK / "reports" / "DESK_SELF_HEAL.json"
#: THE BOUND (principal 2026-11-19: restart stalled lanes "within bounds"). A task this actuator
#: re-runs is re-run at most once per RERUN_MIN_GAP_S and RERUN_MAX_PER_DAY times a day; past
#: that the fault is reported as unrepaired, because a re-run that has not cured it four times
#: is a code defect, and hammering the scheduler hides it.
RERUN_LEDGER = DESK / "data" / "self_heal_reruns.json"
RERUN_MIN_GAP_S = 2 * 3600
RERUN_MAX_PER_DAY = 4


def rerun_allowed(ledger: dict[str, Any], task: str, now: datetime) -> tuple[bool, str]:
    stamps = []
    for x in ledger.get(task) or []:
        try:
            t = datetime.fromisoformat(str(x))
        except ValueError:
            continue
        stamps.append(t if t.tzinfo else t.replace(tzinfo=UTC))
    day = [t for t in stamps if (now - t).total_seconds() < 86400]
    if len(day) >= RERUN_MAX_PER_DAY:
        return False, f"{task} re-run {len(day)}x in 24h (cap {RERUN_MAX_PER_DAY})"
    if day and (now - max(day)).total_seconds() < RERUN_MIN_GAP_S:
        return False, f"{task} re-run at {max(day).isoformat(timespec='seconds')}, inside the gap"
    return True, "due"


def _load_ledger(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(ledger, indent=1) + "\n", "utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


#: END+RUN (Audit 11-20 conditions): a research task whose lane is HUNG (output older than
#: HUNG_FACTOR x its limit) while the scheduler still reads it Running is ended with
#: `schtasks /End` on that task only -- never a pid or image kill -- and then run again. Same
#: bounds as a re-run; every End is logged under END_KEY in the ledger. A live task can never be
#: ended: research_task() refuses anything executor-, follower-, gateway-, release- or
#: account-shaped, and only built-in research tasks or research prefixes qualify.
END_KEY = "_ends"
END_SETTLE_S = 15


def _task_running(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Query", "/TN", name, "/FO", "CSV", "/NH"],
                              capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and '"Running"' in proc.stdout


def _end_task(name: str) -> bool:
    if not heal.research_task(name) or os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/End", "/TN", name], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode == 0:
        import time
        time.sleep(END_SETTLE_S)
    return proc.returncode == 0


def _run_task(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        proc = subprocess.run(["schtasks", "/Run", "/TN", name], capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def run(*, root: Path = ROOT, apply: bool = False,
        out: Path = REPORT, ledger_path: Path = RERUN_LEDGER,
        run_task: Any = None, now: datetime | None = None,
        task_running: Any = None, end_task: Any = None) -> dict[str, Any]:
    t_now = now or datetime.now(tz=UTC)
    findings = heal.audit(root, t_now)
    ledger = _load_ledger(ledger_path)
    bounded: list[dict[str, str]] = []
    launch = run_task or _run_task
    is_running = task_running or _task_running
    end = end_task or _end_task
    ran_this_pass: set[str] = set()
    hung = {f.task for f in findings
            if not f.ok and f.hung and f.task and heal.research_task(f.task)}
    ended: list[dict[str, Any]] = []

    def _bounded_run(task: str) -> bool:
        # Two faults owned by one task (cadence and judge stall both -> MT5-Gauntlet) are one run.
        if task in ran_this_pass:
            return True
        ok, why = rerun_allowed(ledger, task, t_now)
        if not ok:
            bounded.append({"task": task, "why": why})
            return False
        ran_this_pass.add(task)
        ledger[task] = [*[str(x) for x in (ledger.get(task) or [])][-10:],
                        t_now.isoformat(timespec="seconds")]
        if task in hung and heal.research_task(task) and is_running(task):
            ok_end = bool(end(task))
            row = {"task": task, "at": t_now.isoformat(timespec="seconds"), "ended": ok_end}
            ended.append(row)
            ledger[END_KEY] = [*(ledger.get(END_KEY) or [])[-50:], row]
            if not ok_end:
                return False
        return bool(launch(task))

    remedies, escalations = heal.plan(findings, run_task=_bounded_run if apply else None)
    outcomes: list[tuple[str, bool]] = []
    if apply:
        for remedy in remedies:
            outcomes.append((remedy.action, bool(remedy.apply())))
        _save_ledger(ledger_path, ledger)
    doc = {
        "at": t_now.isoformat(timespec="seconds"),
        "status": "OK" if all(f.ok for f in findings) else "DEGRADED",
        "applied": apply,
        "findings": [{"check": f.check, "ok": f.ok, "detail": f.detail,
                      "fixable": f.fixable} for f in findings],
        "repairs": [{"action": action, "ok": ok} for action, ok in outcomes],
        "unrepaired": [{"check": f.check, "detail": f.detail} for f in escalations],
        "bounded": bounded,
        "ended": ended,
        "bounds": {"min_gap_s": RERUN_MIN_GAP_S, "max_per_day": RERUN_MAX_PER_DAY},
        "boundary": ("research evidence producers may be re-run; promotion, capital, gates, "
                     "deadman state and orders are outside this actuator"),
    }
    # MONEYPATH_CRASH ALERTS (principal 2026-11-24 18:14Z): each failing money-path organ lands
    # on the event log as a PLUMBING_DEFECT with its root cause, the surface the alert relay to
    # Claude reads. Only on an applied pass, so a dry run never pages; the writer never raises.
    alerts = [f for f in findings if not f.ok and f.check.startswith("moneypath ")]
    doc["moneypath_alerts"] = [{"organ": f.check, "detail": f.detail} for f in alerts]
    if apply and alerts:
        try:
            import sys as _sys
            if str(root) not in _sys.path:
                _sys.path.insert(0, str(root))
            from libs.ops import events as _ev
            for f in alerts:
                _ev.emit("PLUMBING_DEFECT", root / "desks" / "mt5" / "data" / "events.jsonl",
                     organ=f.check, defect="MONEYPATH_CRASH",
                         detail=f.detail[:600], producer="desk_self_heal", priority=2)
        except Exception as exc:  # the report still names every alert
            doc["moneypath_alert_error"] = f"{type(exc).__name__}: {exc}"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str) + "\n", "utf-8")
    os.replace(tmp, out)
    return doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, default=REPORT)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    doc = run(root=args.root, apply=args.apply, out=args.out)
    print(f"desk self-heal: {doc['status']}; repairs={len(doc['repairs'])}; "
          f"unrepaired={len(doc['unrepaired'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
