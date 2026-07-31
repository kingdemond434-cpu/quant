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

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)

_STEPS = [
    ("lint (ruff)", [_PY, "-m", "ruff", "check", "scripts", "libs", "tests"]),
    # WHOLE TREE (2026-07-25): was 4 named files + tests/execution = ~147 of ~1099 tests, leaving
    # tests/risk (the ruin path) and tests/validation (the anti-false-positive path) ungated, and
    # every newly-shipped test ungated by default. GAP 31's stated blocker -- duplicate basenames
    # breaking collection -- EXPIRED once pyproject set --import-mode=importlib: the tree collects
    # and was run 100% GREEN this session (only optional-dep skips), so gating it is proven safe.
    ("tests (pytest)", [_PY, "-m", "pytest", "tests/", "-q"]),
    ("stress harness", [_PY, "scripts/run_stress.py"]),
]


_LOCK = _ROOT / "data/.ci_run.lock"


def _acquire() -> object | None:
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
        # and would have shipped an unvetted commit (found 2026-07-31, R0144). --fail-on-lock
        # returns 3: "could not gate", which a deployer must treat as not-green and retry.
        if fail_on_lock:
            print("CI: another run holds the lock -- cannot gate this tree state (rc 3)")
            return 3
        print("CI: another run holds the lock -- skipping (marker left untouched)")
        return 0
    failed: list[str] = []
    for label, cmd in _STEPS:
        r = subprocess.run(cmd, cwd=str(_ROOT), capture_output=True, text=True, check=False)
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
