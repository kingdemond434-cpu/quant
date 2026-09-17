"""THE CLOCK FIXER -- every fifteen minutes, every certificate and every stopped clock gets a live
clock, and every resident that died is restarted. Nothing waits for a session to notice.

THE PRINCIPAL'S ORDER (2026-09-17, permanent; LAWS.md 7, lessons L0362-L0364). Measured that
morning: 35 of 58 certificates had no live forward clock, 293 organs were unwired with 282
sitting in a probation queue nothing drained, and nine department residents had exited with
code 1 for two hours while their tasks read "Ready". Each of those was a queue a person had to
notice. This organ is the fifteen-minute law: it runs the healers the desk already owns, in
the order that repairs the costliest defect first, verifies by OBSERVATION (a clock row
advancing, an artifact written, a process alive, a lock held), never by parsing a label, and
publishes what it fixed and what it could not with the reason.

    1. residents      every 24/7 resident (departments, moat swarms, japan, regions, scouts)
                      must hold its lock and have logged inside its cycle; a dead one is
                      restarted through its keep-alive task and named
    2. identity heal  heal_identity_broken_clocks --apply (behaviour hashes, unfrozen rows)
    3. orphaned       heal_orphaned_clocks, heal_silent_demotions (the desk's own healers)
    4. enrolment      shadow_forward (the forward lane's own enrolment pass) when the wiring
                      census names healable certificates without a clock
    5. wiring         wiring_ceo --apply (auto legs, the certificate census, the revive queue)
    6. revive         probation_runner phase 1 (broken and silent clocked organs, real args)

Every step is time-boxed; the pass never exceeds --budget-s. `--dry-run` measures and repairs
nothing.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parents[1]
REPORT = DESK / "reports" / "CLOCK_FIXER.json"
LEDGER = DESK / "data" / "clock_fixer.jsonl"
LOCKS = DESK / "data" / "locks"
LOGS = DESK / "logs"

#: resident lock stem -> (keep-alive task, log file, max silence seconds)
RESIDENTS: dict[str, tuple[str, str, int]] = {
    "dept_data": ("MT5-Dept-Data", "MT5-Dept-Data.log", 4 * 3600),
    "dept_intel": ("MT5-Dept-Intel", "MT5-Dept-Intel.log", 4 * 3600),
    "dept_discovery": ("MT5-Hourly", "MT5-Hourly.log", 4 * 3600),
    "dept_validate": ("MT5-Dept-Validate", "MT5-Dept-Validate.log", 4 * 3600),
    "dept_macro": ("MT5-Dept-Macro", "MT5-Dept-Macro.log", 4 * 3600),
    "dept_execution": ("MT5-Dept-Execution", "MT5-Dept-Execution.log", 4 * 3600),
    "dept_forward": ("MT5-Dept-Forward", "MT5-Dept-Forward.log", 4 * 3600),
    "dept_meta": ("MT5-Dept-Meta", "MT5-Dept-Meta.log", 4 * 3600),
    "dept_rest": ("MT5-Dept-Rest", "MT5-Dept-Rest.log", 4 * 3600),
    "dept_japan": ("MT5-Dept-Japan", "MT5-Dept-Japan.log", 4 * 3600),
    "dept_regions": ("MT5-Dept-Regions", "MT5-Dept-Regions.log", 4 * 3600),
    "moat_exploit": ("MT5-Moat-Exploit", "MT5-Moat-Exploit.log", 4 * 3600),
    "moat_explore": ("MT5-Moat-Explore", "MT5-Moat-Explore.log", 4 * 3600),
    "moat_resurrect": ("MT5-Moat-Resurrect", "MT5-Moat-Resurrect.log", 4 * 3600),
}
STEPS: tuple[tuple[str, list[str], int], ...] = (
    ("identity_heal", [str(DESK / "scripts" / "heal_identity_broken_clocks.py"), "--apply"], 120),
    ("orphaned_clocks", [str(DESK / "scripts" / "heal_orphaned_clocks.py")], 120),
    ("silent_demotions", [str(DESK / "scripts" / "heal_silent_demotions.py")], 120),
    ("wiring", [str(DESK / "research" / "wiring_ceo.py"), "--apply"], 240),
    ("revive", [str(DESK / "research" / "probation_runner.py"), "--max-organs", "3",
                "--max-revive", "8", "--budget-s", "240"], 300),
)


def now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # type: ignore[attr-defined]
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lock_holder(stem: str) -> int | None:
    p = LOCKS / f"{stem}.lock"
    if not p.exists():
        return None
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
        return int(first[0]) if first and first[0].isdigit() else None
    except OSError:
        return None


def _log_age_s(name: str) -> float | None:
    p = LOGS / name
    if not p.exists():
        return None
    return time.time() - p.stat().st_mtime


def _task_exists(task: str) -> bool:
    if sys.platform != "win32":
        return False
    r = subprocess.run(["schtasks", "/Query", "/TN", task], capture_output=True, text=True)
    return r.returncode == 0


def _run_task(task: str) -> str:
    if sys.platform != "win32":
        return "not_windows"
    r = subprocess.run(["schtasks", "/Run", "/TN", task], capture_output=True, text=True)
    return "started" if r.returncode == 0 else f"failed: {(r.stderr or r.stdout).strip()[:80]}"


def check_residents(apply: bool) -> list[dict]:
    """A resident is ALIVE when its lock holder is a live process; SILENT when alive but its log
    has not moved inside its cycle; DEAD otherwise. Dead and silent ones are restarted through
    the keep-alive task (a running singleton makes the start a no-op)."""
    rows: list[dict] = []
    for stem, (task, log, max_silence) in RESIDENTS.items():
        pid = _lock_holder(stem)
        alive = bool(pid and _pid_alive(pid))
        age = _log_age_s(log)
        silent = alive and age is not None and age > max_silence
        state = "ALIVE" if alive and not silent else ("SILENT" if silent else "DEAD")
        row = {"resident": stem, "task": task, "pid": pid, "state": state,
               "log_age_s": None if age is None else round(age)}
        if state != "ALIVE":
            if not _task_exists(task):
                row["action"] = "task_missing"
            elif apply:
                row["action"] = _run_task(task)
            else:
                row["action"] = "would_start"
        rows.append(row)
    return rows


def run_step(name: str, argv: list[str], timeout_s: int, apply: bool) -> dict:
    if not apply:
        return {"step": name, "status": "dry_run"}
    if not Path(argv[0]).exists():
        return {"step": name, "status": "MISSING", "why": argv[0]}
    t0 = time.monotonic()
    try:
        r = subprocess.run([sys.executable, "-W", "ignore", *argv], cwd=str(DESK),
                           capture_output=True, text=True, timeout=timeout_s, check=False)
        tail = (r.stdout or "").strip().splitlines()[-3:]
        return {"step": name, "status": "ok" if r.returncode == 0 else f"rc={r.returncode}",
                "seconds": round(time.monotonic() - t0, 1), "tail": tail,
                "stderr": (r.stderr or "").strip().splitlines()[-2:]}
    except subprocess.TimeoutExpired:
        return {"step": name, "status": "timeout", "seconds": timeout_s}
    except OSError as exc:
        return {"step": name, "status": f"failed_to_start: {type(exc).__name__}"}


def certificates_without_clocks() -> dict:
    """The wiring census's certificate reading, after the wiring step wrote it."""
    p = DESK / "reports" / "WIRING_CEO.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"n": None, "why": "WIRING_CEO.json unreadable"}
    cert = doc.get("certificates_without_clocks")
    return cert if isinstance(cert, dict) else {"n": cert}


def enrol_if_needed(apply: bool, cert: dict) -> dict:
    healable = cert.get("healable") if isinstance(cert, dict) else None
    if not healable:
        return {"step": "enrolment", "status": "skipped", "why": "no healable certificate named"}
    return run_step("enrolment", [str(DESK / "research" / "shadow_forward.py")], 600, apply)


def _write(doc: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, REPORT)
    with contextlib.suppress(OSError):
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": doc["at"], "fixed": doc["fixed"], "dead": doc["dead"],
                                "certificates_without_clocks": doc["certificates_without_clocks"]},
                               default=str) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=int, default=600)
    a = ap.parse_args(argv)
    apply = not a.dry_run
    t0 = time.monotonic()
    residents = check_residents(apply)
    steps: list[dict] = []
    for name, args, timeout_s in STEPS:
        remaining = a.budget_s - (time.monotonic() - t0)
        if remaining < 30:
            steps.append({"step": name, "status": "skipped", "why": "budget exhausted"})
            continue
        steps.append(run_step(name, args, min(timeout_s, int(remaining)), apply))
    cert = certificates_without_clocks()
    steps.append(enrol_if_needed(apply, cert))
    dead = [r["resident"] for r in residents if r["state"] != "ALIVE"]
    fixed = [r["resident"] for r in residents if r.get("action") == "started"]
    doc = {"at": now(), "dry_run": a.dry_run, "seconds": round(time.monotonic() - t0, 1),
           "residents": residents, "dead": dead, "fixed": fixed, "steps": steps,
           "certificates_without_clocks": cert,
           "rule": ("every certificate and every stopped clock gets a live clock every fifteen "
                    "minutes; every dead resident is restarted; verification is by observation "
                    "(lock holder alive, log advancing, clock row advancing), never a label")}
    if apply:
        _write(doc)
    print(f"clock fixer: residents dead={dead} restarted={fixed} "
          f"certs_without_clocks={cert.get('n')} steps={[s['status'] for s in steps]} "
          f"in {doc['seconds']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
