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


def main() -> int:
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
