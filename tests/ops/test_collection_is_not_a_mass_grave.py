"""A test file that cannot be COLLECTED takes every test behind it down silently.

THE DEFECT THIS ENDS. When a branch unification keeps one lineage's tests and the other lineage's
code, the mismatch does not show up as N failures -- it shows up as ONE collection error, and
every guard test inside that module simply stops existing. The suite still reports a pass count,
the pass count is still large, and the number that moved is the one nobody reads. A guard test
that is never collected is indistinguishable, in every artifact this desk produces, from a guard
test that passed.

That is strictly worse than a failing test, because a failure is a verdict and an uncollected
module is a silence -- and L1.28a says absence is never a pass. Measured 2026-09-05: collection is
clean (0 errors over ~11,600 tests, 8s), so this fence lands at its floor and its job is to keep
it there rather than to report a backlog.

WHY A TEST RATHER THAN A CI STEP. CI already runs pytest, so a collection error there is visible
in the log -- but only to someone reading the log, and only on the run where it appears. As a
test, the mass grave becomes a NAMED FAILURE with the offending module in the message, it fails
the same job everything else fails, and it cannot be attributed to flakiness in an unrelated area.

    enforces docs/desk_lessons.jsonl L0173
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


def _collect(target: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         str(target)],
        cwd=str(cwd), capture_output=True, text=True, timeout=900,
    )


def _error_lines(out: str) -> list[str]:
    """Collection errors, as pytest names them in the short summary."""
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith("ERROR ")]


def test_every_test_module_in_the_repo_can_be_collected() -> None:
    """Zero collection errors. Not 'few', not 'the same as yesterday' -- zero.

    A ratchet would be wrong here. Every other backlog on this desk can be paid down gradually
    because the unpaid part is VISIBLE; an uncollectable module is not visible, so tolerating one
    means tolerating an unknown number of silently absent guards.
    """
    proc = _collect(_ROOT / "tests", _ROOT)
    errors = _error_lines(proc.stdout + proc.stderr)
    assert not errors, (
        "test module(s) cannot be collected, so every test inside them is silently absent from "
        "the suite rather than failing:\n  " + "\n  ".join(errors))
    assert proc.returncode == 0, (
        f"collection exited {proc.returncode} with no ERROR line, which means the failure is "
        f"somewhere this fence cannot name:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}")


def test_the_fence_can_actually_fail(tmp_path: Path) -> None:
    """L1.28a: a partition that cannot fail carries no information.

    If `_error_lines` ever stops matching pytest's summary format -- a version bump, a plugin that
    rewrites the short summary -- the test above turns into an unconditional pass and the mass
    grave reopens with a green tick over it. So the detector is pointed at a module that IS
    uncollectable, and must see it.
    """
    broken = tmp_path / "test_uncollectable.py"
    broken.write_text("import a_module_that_does_not_exist_anywhere  # noqa\n", "utf-8")
    proc = _collect(broken, tmp_path)
    assert _error_lines(proc.stdout + proc.stderr), (
        "a module importing a nonexistent package produced no ERROR line -- the detector no "
        f"longer matches pytest's output and the real fence above is now vacuous:\n{proc.stdout}")
