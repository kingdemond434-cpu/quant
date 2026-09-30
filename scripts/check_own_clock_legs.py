"""EVERY LEG TAKEN OFF THE CYCLE'S PLAN MUST HAVE A CLOCK THAT ACTUALLY RUNS IT.

`hourly_cycle.OWN_CLOCK_LEGS` names the legs that run on their own scheduled task instead of
inside a pass. That is a real cure for a leg whose work does not fit a bounded window -- and it
is also the single easiest way to turn a leg off by accident and never notice, because a leg
outside the plan is SKIPPED_BY_PLAN, which writes no ledger row and therefore raises no alarm.
UNWIRED OR IDLE IS A DEFECT (III.16), and "it has its own task" is a claim the desk has to be
able to cash.

So this checker asserts, for every name in `OWN_CLOCK_LEGS`:

  1. a task in `OWN_CLOCK_TASKS` is declared for it, and
  2. on Windows, that task EXISTS in the box's scheduler and is Ready or Running, and
  3. the artifact the leg produces is on disk, with its age reported.

ON A NON-WINDOWS HOST (the VPS, CI) there is no scheduler to ask, so the task check is
UNMEASURED and reported as UNMEASURED -- never as a pass (L1.28a). The declaration check and the
artifact check still run everywhere.

    python scripts/check_own_clock_legs.py            # human
    python scripts/check_own_clock_legs.py --json     # machine
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"

#: leg -> (scheduled task name, the artifact that proves it ran)
OWN_CLOCK_TASKS: dict[str, tuple[str, str]] = {
    "state_vector": ("MT5-StateVector", "data/state_vector.json"),
    "external_gauntlet": ("MT5-Gauntlet", "reports/UNIVERSAL_SURVIVORS.json"),
}


def own_clock_legs() -> set[str]:
    """`OWN_CLOCK_LEGS` read from the cycle's source, never a second copy of the list."""
    import ast

    src = DESK / "research" / "hourly_cycle.py"
    try:
        tree = ast.parse(src.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        targets = [node.target] if isinstance(node, ast.AnnAssign) else list(node.targets)
        if not any(isinstance(t, ast.Name) and t.id == "OWN_CLOCK_LEGS" for t in targets):
            continue
        try:
            call = node.value
            if isinstance(call, ast.Call) and call.args:
                return {str(v) for v in ast.literal_eval(call.args[0])}
        except (ValueError, TypeError, SyntaxError):
            return set()
    return set()


def task_state(task: str) -> tuple[str, str]:
    """(status, why) for one scheduled task. UNMEASURED where there is no scheduler to ask."""
    if sys.platform != "win32":
        return "UNMEASURED", "not Windows: this host has no Task Scheduler to ask"
    try:
        proc = subprocess.run(["schtasks", "/query", "/tn", task, "/fo", "list"],
                              capture_output=True, text=True, errors="replace",
                              timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return "UNMEASURED", f"schtasks did not answer: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return "MISSING", f"no scheduled task named {task!r} on this box"
    status = ""
    for line in (proc.stdout or "").splitlines():
        if line.lower().startswith("status:"):
            status = line.split(":", 1)[1].strip()
    if status.lower() in ("ready", "running"):
        return "OK", f"{task} is {status}"
    return "STOPPED", f"{task} status is {status or 'unreadable'}"


def check() -> dict[str, Any]:
    legs = own_clock_legs()
    rows: list[dict[str, Any]] = []
    for leg in sorted(legs):
        row: dict[str, Any] = {"leg": leg}
        declared = OWN_CLOCK_TASKS.get(leg)
        if declared is None:
            row.update(status="UNDECLARED", why=(
                f"{leg} was taken off every cycle plan and no task is declared for it here, so "
                "nothing in this repository can say what runs it"))
            rows.append(row)
            continue
        task, artifact = declared
        row["task"] = task
        row["artifact"] = artifact
        status, why = task_state(task)
        row["status"] = status
        row["why"] = why
        path = DESK / artifact
        if path.exists():
            row["artifact_age_h"] = round((time.time() - path.stat().st_mtime) / 3600.0, 2)
        else:
            row["artifact_age_h"] = None
            row["artifact_why"] = f"{artifact} is absent: UNMEASURED, not a zero"
        rows.append(row)
    bad = [r for r in rows if r["status"] in ("UNDECLARED", "MISSING", "STOPPED")]
    return {"legs": rows, "n": len(rows), "failing": len(bad),
            "ok": not bad,
            "why": ("every own-clock leg has a task that exists and is armed"
                    if not bad else
                    "; ".join(f"{r['leg']}: {r['why']}" for r in bad))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    rec = check()
    if args.json:
        print(json.dumps(rec, indent=1))
    else:
        for row in rec["legs"]:
            age = row.get("artifact_age_h")
            age_s = f"{age:.2f}h" if isinstance(age, (int, float)) else "ABSENT"
            print(f"{row['status']:10s} {row['leg']:20s} task={row.get('task', '-'):18s} "
                  f"artifact={age_s:>9s}  {row['why']}")
        print(f"\n{rec['n']} own-clock leg(s), {rec['failing']} failing: {rec['why']}")
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
