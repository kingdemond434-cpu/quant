"""Local CI gate -- lint + tests + stress, in one command. Free (no cloud, no cost).

Runs ruff (lint) and the test suite, then the stress harness. Non-zero exit if anything fails, so
it can gate a commit or a deploy. This is the always-available substitute for hosted CI: correctness
of the survival-critical logic (hedge reconcile, risk controls, sizing, leverage) is checked
mechanically, not by hand.

NOTE (2026-07-18): the pytest step names specific files/dirs rather than the whole `tests/` tree
-- a full-tree collection currently fails on pre-existing duplicate test-module basenames across
directories (e.g. two unrelated `test_regime.py`, two unrelated `test_registry.py`; see GAP
register). `tests/execution/` (the risk-path/execution directory, incl. the live connector +
stage machine) was added to the gate 2026-07-18 since that code must never silently go untested;
other directories (risk/, portfolio/, features/, regime/, ...) are NOT yet gated here -- a real
open gap, tracked separately, not fixed by this comment.

    python scripts/run_ci.py
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)

# EVERY STEP IS WALL-CLOCK BOUNDED (2026-08-05). subprocess.run had no timeout, and on this gate
# that is not merely a slow run -- it is the gate silently switching itself off, permanently:
#
#   a step blocks (a network-bound test on a filtered-egress box does exactly this)
#     -> this process never exits, so it never releases the flock it holds
#     -> every later run_ci finds the lock taken and returns 0, "skipping", by design
#     -> .ci_last_run.json is never rewritten, so it stays frozen at its last value
#     -> max_audit only raises on `ok is False`, and a FROZEN marker is never false
#     -> the desk reports its safety gate GREEN, with nothing running behind it, indefinitely.
#
# That is the 2026-07-22 incident (81h of undetected red) through a different door, and the fix
# applied then -- surface a red marker -- cannot catch it, because this failure never produces a
# red marker. It produces a stale green one. Hence three independent repairs: bound the steps so
# a hang becomes a named FAIL here; keep writing the marker on that path so it goes red; and make
# max_audit treat a STALE marker as a defect in its own right (fail-closed -- unknown must never
# read as "no breach"). Any one alone leaves the hole open.
#
# Budgets are per-step and generous -- a ruin rail, not a performance target. They are sized off
# observed runtimes with a wide margin, so tripping one means "wedged", never "busy today".
#
# THE INNER BOUND MUST FIRE BEFORE THE OUTER ONE. daily_research_cycle.py runs this script under
# its own per-step timeout, and if that outer bound wins the race the process is killed from the
# outside: no [HUNG] line, no red marker written, nothing named -- which is the stale-green
# failure again, merely relocated. So the invariant is sum(_STEPS budgets) < the cycle's ci_gate
# budget, with the outer kept only as the backstop for what a Python-level timeout cannot catch
# (this interpreter itself wedging). tests/ops/test_ci_gate_timeouts.py asserts the ordering
# across both files, because it is exactly the kind of coupling that survives one edit and dies
# on the next -- the two numbers live in different files and nothing else relates them.
_STEPS = [
    ("lint (ruff)", [_PY, "-m", "ruff", "check", "scripts", "libs", "tests"], 300),
    # WHOLE TREE (2026-07-25): was 4 named files + tests/execution = ~147 of ~1099 tests, leaving
    # tests/risk (the ruin path) and tests/validation (the anti-false-positive path) ungated, and
    # every newly-shipped test ungated by default. GAP 31's stated blocker -- duplicate basenames
    # breaking collection -- EXPIRED once pyproject set --import-mode=importlib: the tree collects
    # and was run 100% GREEN this session (only optional-dep skips), so gating it is proven safe.
    ("tests (pytest)", [_PY, "-m", "pytest", "tests/", "-q"], 1800),
    # TYPES (2026-07-25): mypy --strict was configured in pyproject and run by NOBODY -- the
    # strictest tool in the repo was not in the gate, so nothing stopped a type regression
    # landing. Added the same day scripts/ entered its `files` list, because a type gate that
    # covers the money path but is never executed is not a gate.
    ("types (mypy)", [_PY, "-m", "mypy"], 600),
    ("stress harness", [_PY, "scripts/run_stress.py"], 600),
]
#: Worst-case wall clock if every step wedges. Read by the cycle-budget invariant test rather
#: than recomputed there, so the two cannot drift apart silently.
STEP_BUDGET_TOTAL_S = sum(b for _, _, b in _STEPS)  # 3300s


_LOCK = _ROOT / "data/.ci_run.lock"


def _acquire() -> IO[str] | None:
    """Take the CI lock, or return None if another run already holds it.

    Non-blocking on purpose: a second concurrent gate tests the same tree, so it adds no
    information while doubling peak RAM on a 3.8 GiB box with no swap -- where the OOM-killer's
    victim could be the dead-man rail. Declining beats queueing.
    """
    _LOCK.parent.mkdir(parents=True, exist_ok=True)
    fh = _LOCK.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None
    return fh


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    fail_on_lock = "--fail-on-lock" in args
    _fh = _acquire()
    if _fh is None:
        # Another gate is mid-run on the same tree. For an ORGAN's routine gate, exit 0 and DO
        # NOT touch the marker: non-zero would fail its cycle for the non-error of someone else
        # already checking, and writing the marker here IS the last-writer-wins race.
        # For a DEPLOY decision that exit 0 is a lie -- pull_deploy read "skipped" as "green"
        # and would have shipped an unvetted commit (found 2026-07-31, R0145). --fail-on-lock
        # returns 3: "could not gate", which a deployer must treat as not-green and retry.
        if fail_on_lock:
            print("CI: another run holds the lock -- cannot gate this tree state (rc 3)")
            return 3
        print("CI: another run holds the lock -- skipping (marker left untouched)")
        return 0
    # RELEASE THE LOCK ON EVERY EXIT PATH. The handle was previously left open and reclaimed only
    # by process teardown -- invisible in production, but it meant this function could not be
    # called twice in one interpreter, which is why the gate's own failure paths had never been
    # executed by a test. A gate whose error handling has never run is a gate with an untested
    # ruin rail; closing the handle here is what made the [HUNG] path testable at all.
    try:
        return _run_steps()
    finally:
        _fh.close()


def _run_steps() -> int:
    failed: list[str] = []
    for label, cmd, budget in _STEPS:
        try:
            r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True,
                               check=False, timeout=budget)
        except subprocess.TimeoutExpired:
            # A HANG IS A FAILURE, NOT A SLOW PASS. Naming it distinctly from an ordinary red
            # matters: "wedged" and "broken" have different first moves, and the operator who
            # reads this line should not have to guess which one they are looking at.
            print(f"[HUNG] {label}: exceeded {budget}s budget -- killed and counted as FAILED")
            failed.append(f"{label} (HUNG >{budget}s)")
            continue
        ok = r.returncode == 0
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {tail[0][:120]}")
        if not ok:
            failed.append(label)
    print("CI:", "ALL GREEN" if not failed else f"FAILED -> {failed}")
    # Freshest-truth CI status marker (2026-07-23): a red desk-wide gate sat undetected 81h
    # because the brain cycle that runs run_ci was quota-dead; max_audit now surfaces this
    # marker so a red gate always enters the escalation path. Additive; never affects the gate.
    with contextlib.suppress(OSError):
        (_ROOT / "data/.ci_last_run.json").write_text(
            json.dumps({"ok": not failed, "ts": datetime.now(tz=UTC).isoformat(),
                        "failed": failed}), "utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
