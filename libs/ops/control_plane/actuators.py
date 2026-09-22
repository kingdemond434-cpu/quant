"""EVERY REPAIR GETS A POSTCONDITION, AND A RETURN CODE OF 0 IS NEVER PROOF.

The desk's healers all reported the same way: the subprocess exited zero, so the step is "ok".
Measured consequences, all of them real: `MT5-Gauntlet` restarted and immediately exited because
another instance held the lock -- rc=0, nothing repaired; `shadow_forward` "enrolled" while being
SIGKILLed at the same prefix every hour -- rc absent, backlog untouched; a wiring pass that wrote
its report from a cached census and changed nothing -- rc=0, defect intact. An exit code describes
the exit, not the world.

So an actuator here NEVER decides that it succeeded. The reconciler:

    1. runs the actuator,
    2. waits up to a DECLARED window (a restart gets 90 s -- the time a Windows task needs to
       start a python process, claim its singleton lock and write one heartbeat),
    3. proves the postcondition BY OBSERVATION -- a new live PID holding the lock and a watermark
       or lease that advanced; a certified identity that now has an accruing immutable clock; an
       owned output whose content hash moved and whose consumer acknowledged the new run,
    4. records REPAIRED only then.

A failed postcondition is a failed repair whatever the return code said, and a required repair
that times out makes the reconciler red and its process exit non-zero (fail-closed).

TESTABLE WITH FAKES. `run_actuator` takes an injectable `runner` and `sleeper`, so the chaos tests
drive every branch -- rc=0 with no lock taken, rc!=0 with the lock taken by an unrelated restart,
a window that expires -- without starting a process or waiting a second.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from libs.ops.control_plane import watermarks as wm

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
LOCKS = DESK / "data" / "locks"

#: A restart's proof window. Below this a healthy restart reads as failed; far above it, a wedged
#: box holds the fifteen-minute pass hostage.
RESTART_WINDOW_S = 90
#: How often the postcondition is re-checked inside the window.
POLL_S = 3

#: Verdicts an actuator run can carry. REPAIRED requires PROVED; nothing else does.
RESULTS: tuple[str, ...] = ("REPAIRED", "FAILED", "UNPROVEN", "DRY_RUN", "SKIPPED")


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        kernel32 = getattr(ctypes, "windll").kernel32      # noqa: B009 - absent off Windows
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def lock_holder(stem: str, locks: Path | None = None) -> int | None:
    p = (locks or LOCKS) / f"{stem}.lock"
    try:
        first = p.read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return None
    return int(first[0]) if first and first[0].isdigit() else None


def content_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


# ----------------------------------------------------------------------------- postconditions
@dataclass(frozen=True)
class Postcondition:
    """A fact about the WORLD that must be true for the repair to count.

    `check` returns (proved, why): True = observed, False = observed absent, None = UNMEASURED
    (the thing that would prove it does not exist here -- a finding, never a pass).
    """

    name: str
    check: Callable[[Mapping[str, Any]], tuple[bool | None, str]]


def _pc_new_live_lock_holder(ctx: Mapping[str, Any]) -> tuple[bool | None, str]:
    """A NEW pid holds the singleton lock and is alive. The restart's minimum proof."""
    stem = str(ctx.get("lock_stem") or "")
    if not stem:
        return None, "no lock stem declared for this component; liveness is UNMEASURED"
    locks = ctx.get("locks")
    pid = lock_holder(stem, Path(locks) if locks else None)
    before = ctx.get("pid_before")
    alive = ctx.get("pid_alive", pid_alive)(pid) if callable(ctx.get("pid_alive")) \
        else pid_alive(pid)
    if not pid:
        return False, f"{stem}.lock holds no pid after the restart window"
    if not alive:
        return False, f"{stem}.lock holds pid {pid}, which is not running"
    if before and pid == before:
        return False, (f"{stem}.lock still holds the SAME pid {pid} the repair was supposed to "
                       f"replace: the task started and the old process kept the slot")
    return True, f"{stem}.lock held by live pid {pid}"


def _pc_watermark_advanced(ctx: Mapping[str, Any]) -> tuple[bool | None, str]:
    """The component's work counter moved AFTER the repair. Liveness without progress is the
    exact failure this whole package exists for."""
    cid = str(ctx.get("component_id") or "")
    if not cid:
        return None, "no component id; progress is UNMEASURED"
    root = ctx.get("watermark_root")
    row = wm.read(cid, Path(root) if root else None)
    if row is None:
        return None, (f"{cid} has no watermark: nothing in it calls progress(), so a restart "
                      f"cannot be proven to have resumed work")
    before = ctx.get("watermark_before") or {}
    if str(row.get("at")) != str(before.get("at")) or \
            int(row.get("updates") or 0) > int(before.get("updates") or 0):
        return True, f"{cid} watermark advanced to {row.get('metric')}={row.get('value')}"
    return False, (f"{cid} watermark has not moved since the repair "
                   f"({row.get('metric')}={row.get('value')} at {row.get('at')})")


def _pc_output_changed(ctx: Mapping[str, Any]) -> tuple[bool | None, str]:
    """The repair's own declared output changed. A healer that writes the identical bytes it
    wrote before did not heal anything the reconciler had just observed as broken."""
    out = ctx.get("output")
    if not out:
        return None, "the actuator declares no output; its effect is UNMEASURED"
    p = Path(out)
    after = content_hash(p)
    if after is None:
        return False, f"{p.name} does not exist after the repair"
    before = ctx.get("output_hash_before")
    if before is None:
        return True, f"{p.name} now exists ({after})"
    if after != before:
        return True, f"{p.name} content changed {before} -> {after}"
    return False, f"{p.name} is byte-identical to before the repair ({after})"


def _pc_clock_accruing(ctx: Mapping[str, Any]) -> tuple[bool | None, str]:
    """The heal-forward-clock postcondition: the SAME certified identity now has an accruing
    immutable clock. Counted from the wiring census's own certificate reading, before and after,
    because that census is what names the healable identities in the first place."""
    reader = ctx.get("certificates_without_clocks")
    if not callable(reader):
        return None, "no certificate census available; forward healing is UNMEASURED"
    after = reader()
    before = ctx.get("certs_before")
    n_after = after.get("n") if isinstance(after, dict) else after
    n_before = before.get("n") if isinstance(before, dict) else before
    if n_after is None:
        return None, "the certificate census is unreadable; forward healing is UNMEASURED"
    if n_before is None:
        return (n_after == 0), f"{n_after} certificates still hold no clock"
    if n_after < n_before:
        return True, f"certificates without clocks fell {n_before} -> {n_after}"
    return False, (f"certificates without clocks did not fall ({n_before} -> {n_after}): the "
                   f"enrolment ran and no identity gained a clock")


NEW_LIVE_LOCK_HOLDER = Postcondition("new_live_lock_holder", _pc_new_live_lock_holder)
WATERMARK_ADVANCED = Postcondition("watermark_advanced", _pc_watermark_advanced)
OUTPUT_CHANGED = Postcondition("output_changed", _pc_output_changed)
CLOCK_ACCRUING = Postcondition("clock_accruing", _pc_clock_accruing)


# --------------------------------------------------------------------------------- actuators
@dataclass(frozen=True)
class Actuator:
    """One dumb repair action. It knows how to ACT and nothing about whether it worked."""

    name: str
    argv: tuple[str, ...]
    window_s: int = RESTART_WINDOW_S
    #: All postconditions must be PROVED (or the repair is not REPAIRED). An UNMEASURED one makes
    #: the whole run UNPROVEN, which for a required component is a failure, by design.
    postconditions: tuple[Postcondition, ...] = ()
    #: What the actuator owns, for `OUTPUT_CHANGED`.
    output: str | None = None
    #: The scheduler task it drives, when it drives one (Windows `schtasks /Run`).
    task: str | None = None
    lock_stem: str | None = None
    component_id: str | None = None
    timeout_s: int = 300
    cwd: str | None = None
    notes: str = ""
    context: Mapping[str, Any] = field(default_factory=dict)


def restart_resident(component_id: str, task: str, lock_stem: str,
                     window_s: int = RESTART_WINDOW_S) -> Actuator:
    """Restart a 24/7 resident through its keep-alive task. A running singleton makes the start a
    no-op, so this is safe to fire at a component that turns out to be healthy."""
    return Actuator(
        name=f"restart:{component_id}",
        argv=("schtasks", "/Run", "/TN", task),
        window_s=window_s,
        postconditions=(NEW_LIVE_LOCK_HOLDER, WATERMARK_ADVANCED),
        task=task, lock_stem=lock_stem, component_id=component_id,
        notes=("proof is a NEW live pid holding the singleton lock and a watermark that moved; "
               "schtasks returning 0 only means the scheduler accepted the request"))


def script_actuator(name: str, script: Path | str, args: Sequence[str] = (), *,
                    output: str | None = None, window_s: int = 120, timeout_s: int = 300,
                    component_id: str | None = None,
                    postconditions: Sequence[Postcondition] | None = None) -> Actuator:
    return Actuator(
        name=name,
        argv=(sys.executable, "-W", "ignore", str(script), *[str(a) for a in args]),
        window_s=window_s, timeout_s=timeout_s, output=output, component_id=component_id,
        postconditions=tuple(postconditions if postconditions is not None else (OUTPUT_CHANGED,)),
        cwd=str(DESK))


def desk_actuators(desk: Path | None = None) -> dict[str, Actuator]:
    """The repairs this desk already owns, wrapped so each one must prove itself.

    These are exactly the clock fixer's old STEPS -- it had them in the right order and with the
    right time boxes, and judged every one of them by its return code.
    """
    d = desk or DESK
    return {
        "identity_heal": script_actuator(
            "identity_heal", d / "scripts" / "heal_identity_broken_clocks.py", ("--apply",),
            output=str(d / "reports" / "IDENTITY_HEAL.json"), window_s=120, timeout_s=120),
        "orphaned_clocks": script_actuator(
            "orphaned_clocks", d / "scripts" / "heal_orphaned_clocks.py", (),
            output=str(d / "reports" / "ORPHANED_CLOCKS.json"), window_s=120, timeout_s=120),
        "silent_demotions": script_actuator(
            "silent_demotions", d / "scripts" / "heal_silent_demotions.py", (),
            output=str(d / "reports" / "SILENT_DEMOTIONS.json"), window_s=120, timeout_s=120),
        "wiring": script_actuator(
            "wiring", d / "research" / "wiring_ceo.py", ("--apply",),
            output=str(d / "reports" / "WIRING_CEO.json"), window_s=240, timeout_s=240,
            component_id="leg:wiring_audit"),
        "revive": script_actuator(
            "revive", d / "research" / "probation_runner.py",
            ("--max-organs", "3", "--max-revive", "8", "--budget-s", "240"),
            output=str(d / "reports" / "PROBATION.json"), window_s=300, timeout_s=300),
        "enrolment": Actuator(
            name="enrolment",
            argv=(sys.executable, "-W", "ignore", str(d / "research" / "shadow_forward.py")),
            window_s=600, timeout_s=600, cwd=str(d),
            postconditions=(CLOCK_ACCRUING,),
            component_id="leg:enrol_clocks",
            notes=("the postcondition is the certificate census FALLING, not shadow_forward's "
                   "exit code: the enrolment pass has exited zero while being killed partway "
                   "through the same prefix every hour")),
    }


def _default_runner(argv: Sequence[str], timeout_s: int, cwd: str | None) -> dict[str, Any]:
    try:
        r = subprocess.run(list(argv), capture_output=True, text=True, timeout=timeout_s,
                           cwd=cwd, check=False)
        return {"rc": r.returncode, "tail": (r.stdout or r.stderr or "").strip()[-200:]}
    except subprocess.TimeoutExpired:
        return {"rc": None, "tail": f"timed out after {timeout_s}s", "timeout": True}
    except OSError as exc:
        return {"rc": None, "tail": f"{type(exc).__name__}: {exc}", "failed_to_start": True}


def run_actuator(act: Actuator, ctx: Mapping[str, Any] | None = None, *, apply: bool = True,
                 runner: Callable[[Sequence[str], int, str | None], dict[str, Any]] | None = None,
                 sleeper: Callable[[float], None] | None = None,
                 clock: Callable[[], float] | None = None) -> dict[str, Any]:
    """Run one actuator and PROVE its postcondition by observation. Returns the repair record.

    `result` is REPAIRED only when every postcondition proved. UNPROVEN means the action ran and
    the world does not show the effect (including "nothing here can measure the effect", which is
    UNMEASURED and therefore not a pass). FAILED means the action itself could not run.
    """
    context: dict[str, Any] = {**dict(act.context), **dict(ctx or {})}
    context.setdefault("component_id", act.component_id)
    context.setdefault("lock_stem", act.lock_stem)
    context.setdefault("output", act.output)
    if act.output and "output_hash_before" not in context:
        context["output_hash_before"] = content_hash(Path(act.output))
    if act.lock_stem and "pid_before" not in context:
        context["pid_before"] = lock_holder(act.lock_stem,
                                            Path(context["locks"]) if context.get("locks")
                                            else None)
    if act.component_id and "watermark_before" not in context:
        root = context.get("watermark_root")
        context["watermark_before"] = wm.read(act.component_id, Path(root) if root else None) or {}

    base = {"actuator": act.name, "argv": list(act.argv), "window_s": act.window_s,
            "at": _now(), "postconditions": [p.name for p in act.postconditions]}
    if not apply:
        return {**base, "result": "DRY_RUN", "repaired": False,
                "why": "dry run: measured, repaired nothing"}
    if not act.postconditions:
        return {**base, "result": "UNPROVEN", "repaired": False,
                "why": (f"{act.name} declares no postcondition, so no repair it performs can be "
                        f"proven; a return code is not proof")}

    run = runner or _default_runner
    tick = clock or time.monotonic
    nap = sleeper or time.sleep
    t0 = tick()
    outcome = run(act.argv, act.timeout_s, act.cwd)
    proofs: list[dict[str, Any]] = []
    while True:
        proofs = []
        for pc in act.postconditions:
            ok, why = pc.check(context)
            proofs.append({"postcondition": pc.name, "proved": ok, "why": why})
        if all(p["proved"] is True for p in proofs):
            break
        if tick() - t0 >= act.window_s:
            break
        nap(POLL_S)

    proved = all(p["proved"] is True for p in proofs)
    unmeasured = [p["postcondition"] for p in proofs if p["proved"] is None]
    rc = outcome.get("rc")
    record = {**base, "rc": rc, "tail": outcome.get("tail"),
              "seconds": round(tick() - t0, 1), "proofs": proofs,
              "unmeasured_postconditions": unmeasured}
    if proved:
        return {**record, "result": "REPAIRED", "repaired": True, "why": ""}
    if outcome.get("failed_to_start"):
        return {**record, "result": "FAILED", "repaired": False,
                "why": f"{act.name} could not start: {outcome.get('tail')}"}
    if outcome.get("timeout"):
        return {**record, "result": "FAILED", "repaired": False,
                "why": f"{act.name} exceeded its {act.timeout_s}s timeout"}
    first = next((p for p in proofs if p["proved"] is not True), None)
    return {**record, "result": "UNPROVEN", "repaired": False,
            "why": (f"{act.name} returned rc={rc} and its postcondition did not hold: "
                    f"{first['why'] if first else 'unknown'}")}
