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

THE RECONCILER OWNS HEALTH NOW (principal 2026-09-17, LAWS.md 7). This organ is no longer the
authority on whether anything is well; it is the fifteen-minute APPLY PASS of the desired-state
control plane. `libs/ops/control_plane/reconciler.py` computes desired minus observed for every
component in `desks/mt5/ops/components.py`, assigns the state, and plans the work; the steps above
are its ACTUATORS, each of which must now prove a postcondition by observation before anything is
recorded as repaired. `RESIDENTS` is derived from the specs rather than written here, and `main()`
exits non-zero when a required repair did not prove itself -- so the task cannot report success
over a repair that did not take.
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

def _load_residents() -> dict[str, tuple[str, str, int]]:
    """resident lock stem -> (keep-alive task, log file, max silence seconds), FROM THE SPECS.

    THIS MAP USED TO LIVE HERE AS A LITERAL, and it was one of four registries of the same
    machine (this one, `moat_swarms.TASK_NAMES`, `forests.FOREST_TASKS`, `box_tasks.manifest`),
    each true about a different subset and each edited by hand when a department, a forest or a
    swarm was added. It is now derived from `desks/mt5/ops/components.residents()`, which derives
    it from the departments, the forest federation and the swarm table -- so a new resident
    arrives here the moment it arrives anywhere, and `scripts/check_component_registry.py` fails
    the gate if these two ever disagree again.

    THE SILENCE WINDOW IS DERIVED TOO. It was a flat four hours for every resident: almost no
    margin for a department whose pass may legitimately run three hours, and eight times too long
    for a moat swarm whose pass is capped at thirty-two minutes, so a dead swarm sat unnoticed
    for most of a shift. `specs.derive_max_silence(cadence, that family's own pass ceiling)`
    gives 14400s to MT5-Hourly, 11400s to the ten-minute keep-alive departments and 2520s to the
    swarms.

    The fallback is the empty dict rather than a stale copy: a clock fixer that cannot read
    desired state must report that it cannot, not repair against a guess.
    """
    try:
        import importlib.util
        path = DESK / "ops" / "components.py"
        spec = importlib.util.spec_from_file_location("_cf_components", path)
        if spec is None or spec.loader is None:
            return {}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return dict(mod.residents())
    except Exception as exc:                                    # pragma: no cover - import guard
        print(f"clock fixer: component registry UNREADABLE ({type(exc).__name__}: {exc}); "
              f"no resident is judged this pass", flush=True)
        return {}


RESIDENTS: dict[str, tuple[str, str, int]] = _load_residents()

#: The healers, in the order that repairs the costliest defect first. They are ACTUATORS now:
#: `libs/ops/control_plane/actuators.py` runs each one and then PROVES its postcondition by
#: observation, because every one of them has exited zero while repairing nothing.
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


#: What the lock file says about its owner. The states are the point: "I cannot read it" and
#: "nobody holds it" are OPPOSITE facts and this organ read them as the same one until
#: 2026-09-17, when every one of twenty-two healthy residents was reported DEAD and "restarted"
#: every fifteen minutes. The residents hold a WINDOWS BYTE-RANGE LOCK on byte 0 of their own
#: lock file (`department_resident.claim_singleton` -> `msvcrt.locking`), so reading that byte
#: raises PermissionError WHILE THE PROCESS IS ALIVE. An unreadable lock is therefore the
#: strongest evidence of life this organ has, not evidence of death.
LOCK_HELD = "HELD"          # a live process holds the byte-range lock (read refused)
LOCK_PID = "PID"            # readable, carries a pid to check
LOCK_STALE = "STALE"        # readable and carries no pid: the writer died before writing
LOCK_FREE = "FREE"          # no lock file at all


def _lock_state(stem: str) -> tuple[str, int | None]:
    """(state, pid). See LOCK_HELD above -- an unreadable lock is a held lock."""
    p = LOCKS / f"{stem}.lock"
    if not p.exists():
        return LOCK_FREE, None
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
    except PermissionError:
        return LOCK_HELD, None
    except OSError:
        return LOCK_HELD, None
    if first and first[0].isdigit():
        return LOCK_PID, int(first[0])
    return LOCK_STALE, None


def _lock_holder(stem: str) -> int | None:
    """The pid in the lock file when it is readable; None otherwise (see `_lock_state`)."""
    return _lock_state(stem)[1]


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
    """A resident is ALIVE when it HOLDS its singleton lock -- proven either by the lock file
    refusing to be read (the byte-range lock is held, which only a live process can do) or by a
    readable pid that is a live process. SILENT when alive but its log has not moved inside its
    cycle; DEAD otherwise. Dead and silent ones are restarted through
    the keep-alive task (a running singleton makes the start a no-op)."""
    rows: list[dict] = []
    for stem, (task, log, max_silence) in RESIDENTS.items():
        lock_state, pid = _lock_state(stem)
        alive = lock_state == LOCK_HELD or bool(pid and _pid_alive(pid))
        age = _log_age_s(log)
        silent = alive and age is not None and age > max_silence
        state = "ALIVE" if alive and not silent else ("SILENT" if silent else "DEAD")
        row = {"resident": stem, "task": task, "pid": pid, "state": state,
               "lock": lock_state, "log_age_s": None if age is None else round(age)}
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


def run_reconciler(apply: bool, budget_s: float) -> dict:
    """The RECONCILER is the authority now; this organ is its fifteen-minute apply pass.

    Health is no longer decided here. `libs/ops/control_plane/reconciler.py` computes desired vs
    observed for every component, assigns the state, plans the work and runs each actuator with a
    postcondition -- and this file supplies the actuators. A failure to load it is reported and
    does not stop the healers below: a control plane that takes the healers down with it when it
    cannot import is strictly worse than the healers alone.
    """
    try:
        sys.path.insert(0, str(ROOT))
        import importlib.util

        from libs.ops.control_plane import reconciler as rc
        path = DESK / "ops" / "components.py"
        spec = importlib.util.spec_from_file_location("_cf_components_rc", path)
        if spec is None or spec.loader is None:
            return {"status": "MISSING", "why": f"{path} not loadable"}
        comp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(comp)
        doc = rc.reconcile(registry=comp.registry(ROOT), root=ROOT, apply=apply,
                           budget_s=budget_s, census=comp.census(ROOT))
        if apply:
            rc.write(doc, DESK / "reports" / "CONTROL_PLANE.json", ROOT)
        return doc
    except Exception as exc:
        return {"status": "FAILED", "why": f"{type(exc).__name__}: {exc}"}


def run_actuated_steps(apply: bool, budget_s: float, t0: float) -> list[dict]:
    """The healers, each PROVING its postcondition. A return code of 0 is never proof."""
    try:
        sys.path.insert(0, str(ROOT))
        from libs.ops.control_plane import actuators as ac
    except Exception as exc:                                    # pragma: no cover - import guard
        return [{"step": "actuators", "status": "UNAVAILABLE",
                 "why": f"{type(exc).__name__}: {exc}"}]
    table = ac.desk_actuators(DESK)
    out: list[dict] = []
    for name, _args, timeout_s in STEPS:
        remaining = budget_s - (time.monotonic() - t0)
        if remaining < 30:
            out.append({"step": name, "status": "skipped", "why": "budget exhausted"})
            continue
        a = table.get(name)
        if a is None:
            out.append({"step": name, "status": "MISSING", "why": "no actuator declared"})
            continue
        rec = ac.run_actuator(a, apply=apply)
        out.append({"step": name, "status": rec["result"].lower(), "repaired": rec.get("repaired"),
                    "seconds": rec.get("seconds"), "rc": rec.get("rc"),
                    "proofs": rec.get("proofs"), "why": rec.get("why"),
                    "budget_s": min(timeout_s, int(remaining))})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--budget-s", type=int, default=600)
    a = ap.parse_args(argv)
    apply = not a.dry_run
    t0 = time.monotonic()
    # THE RECONCILER IS TIME-BOXED LIKE EVERY OTHER STEP: half the budget, never more than five
    # minutes, and skipped by name when the budget cannot hold it -- the rule the healers below
    # have always run under.
    if a.budget_s >= 30:
        control = run_reconciler(apply, min(float(a.budget_s) / 2.0, 300.0))
    else:
        control = {"status": "skipped", "why": "budget exhausted"}
    reconciled = isinstance(control, dict) and "invariants" in control
    # WHO RESTARTS A DEAD RESIDENT. When the reconciler ran, it already did -- with a
    # postcondition (a NEW live pid holding the lock and a moving watermark), which is strictly
    # more than this organ's own fire-and-forget `schtasks /Run`. So the census below only ACTS
    # when the reconciler could not: a control plane that fails to import must not leave the
    # residents unrestarted, and one that succeeded must not restart them twice.
    residents = check_residents(apply and not reconciled)
    steps = run_actuated_steps(apply, float(a.budget_s), t0)
    cert = certificates_without_clocks()
    steps.append(enrol_if_needed(apply, cert))
    dead = [r["resident"] for r in residents if r["state"] != "ALIVE"]
    fixed = [r["resident"] for r in residents if r.get("action") == "started"]
    if reconciled:
        fixed += [str(r.get("component_id")) for r in (control.get("repairs") or [])
                  if r.get("repaired")]
    failed_required = list(control.get("failed_required_repairs") or []) if isinstance(
        control, dict) else []
    failed_steps = [s["step"] for s in steps if s.get("status") == "failed"]
    doc = {"at": now(), "dry_run": a.dry_run, "seconds": round(time.monotonic() - t0, 1),
           "residents": residents, "dead": dead, "fixed": fixed, "steps": steps,
           "certificates_without_clocks": cert,
           "control_plane": {
               "DESK_CLOSED_AND_HEALTHY": control.get("DESK_CLOSED_AND_HEALTHY")
               if isinstance(control, dict) else None,
               "first_broken_invariant": control.get("first_broken_invariant")
               if isinstance(control, dict) else None,
               "epoch_id": control.get("epoch_id") if isinstance(control, dict) else None,
               "states": control.get("states") if isinstance(control, dict) else None,
               "planned": len(control.get("plan") or []) if isinstance(control, dict) else None,
               "repairs": control.get("repairs") if isinstance(control, dict) else None,
               "status": control.get("status") if isinstance(control, dict) else None,
               "why": control.get("why") if isinstance(control, dict) else None},
           "failed_required_repairs": failed_required,
           "failed_steps": failed_steps,
           "rule": ("the reconciler owns health: desired state minus observed state is the "
                    "repair plan, every repair proves a postcondition by observation, and a "
                    "return code of zero is never proof; this organ is its apply pass")}
    if apply:
        _write(doc)
    print(f"clock fixer: residents dead={dead} restarted={fixed} "
          f"certs_without_clocks={cert.get('n')} steps={[s['status'] for s in steps]} "
          f"closed_and_healthy={doc['control_plane']['DESK_CLOSED_AND_HEALTHY']} "
          f"in {doc['seconds']}s", flush=True)
    if failed_required or failed_steps:
        print(f"clock fixer: FAILED repairs required={failed_required} steps={failed_steps}",
              file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
