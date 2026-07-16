"""Local CI gate -- lint + tests + stress, in one command. Free (no cloud, no cost).

Runs ruff (lint) and the test suite, then the stress harness. Non-zero exit if anything fails, so
it can gate a commit or a deploy. This is the always-available substitute for hosted CI: correctness
of the survival-critical logic (hedge reconcile, risk controls, sizing, leverage) is checked
mechanically, not by hand.

    python scripts/run_ci.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)

_STEPS = [
    ("lint (ruff)", [_PY, "-m", "ruff", "check", "scripts", "libs", "tests"]),
    ("tests (pytest)", [_PY, "-m", "pytest", "tests/test_hedge_and_risk.py",
                        "tests/test_root_cause.py", "tests/test_alpha_economics.py",
                        "tests/test_review_fixes.py", "-q"]),
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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
