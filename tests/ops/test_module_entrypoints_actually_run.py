"""Having a `main()` is not evidence that it runs.

MEASURED 2026-09-10. `libs/research_os/brain_ab.py` was written on 2026-08-30, ends in
`if __name__ == "__main__": raise SystemExit(main())`, and that line had NEVER ONCE EXECUTED. Run
as a script, `sys.path[0]` is the script's own directory, so the repo root is absent and
`from libs.research_os import store` inside `report()` raises ModuleNotFoundError before a single
number is computed. It was unwired, and underneath the wiring it was unrunnable.

That is a distinct defect from the one the wiring audit finds, and it hides inside it: the audit
asks "does anything call this?", and a module can pass a future audit -- someone adds a caller --
while still failing on the first line of work. The two together are how a desk ends up with a
scheduled leg that has been exiting non-zero since the day it was added.

WHY THIS IS A TEST AND NOT A REVIEW NOTE. Every module here is dispatched BY PATH:
`hourly_cycle._producer(name, "libs/x/y.py")` resolves the string against the repo root and runs
it. `-m` would have worked; the path form is what the cycle actually uses, and it is the form that
was broken. So the test runs them the way the desk runs them.

DELIBERATELY NOT EVERY MODULE WITH A `main()`. Only the ones a cycle leg dispatches, because those
are the ones whose failure is silent -- a non-zero exit becomes a leg result nobody reads. A
module nothing calls yet is the wiring audit's business, not this file's.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

#: (module path, why it is dispatched). Each is invoked by path from a cycle leg, so each must be
#: runnable by path. Add a row here when a leg starts dispatching a new one.
DISPATCHED: tuple[tuple[str, str], ...] = (
    ("libs/ops/wiring_audit.py", "hourly_cycle:wiring_audit -- censuses what nothing calls"),
    ("libs/research_os/brain_ab.py", "hourly_cycle:brain_ab -- did a change to the search help"),
)


@pytest.mark.parametrize(("rel", "why"), DISPATCHED)
def test_a_dispatched_module_runs_the_way_the_cycle_runs_it(rel: str, why: str) -> None:
    """Exit 0, invoked by PATH from the repo root -- exactly `_producer`'s call shape."""
    target = _ROOT / rel
    assert target.exists(), f"{rel} is dispatched by a leg and does not exist"
    r = subprocess.run([sys.executable, "-u", "-W", "ignore", str(target)],
                       cwd=str(_ROOT), capture_output=True, text=True, timeout=300, check=False)
    assert r.returncode == 0, (
        f"{rel} exits {r.returncode} when run the way its leg runs it ({why}).\n"
        f"stderr tail: {r.stderr.strip()[-600:]}")


@pytest.mark.parametrize(("rel", "why"), DISPATCHED)
def test_it_is_importable_as_a_module_too(rel: str, why: str) -> None:
    """The other spelling. A module that works by path and not by `-m` breaks the moment someone
    schedules it the other way, and both forms exist in this repo's shell surface."""
    mod = rel[: -len(".py")].replace("/", ".")
    r = subprocess.run([sys.executable, "-c", f"import {mod}"],
                       cwd=str(_ROOT), capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, f"import {mod} fails: {r.stderr.strip()[-400:]}"


def test_the_brain_ab_entrypoint_reports_underpowered_rather_than_no_difference() -> None:
    """THE REASON IT WAS WORTH REPAIRING RATHER THAN DELETING.

    The metric anyone would name -- forward survivors -- is 0/0 and has been for the desk's whole
    history. An A/B on a metric that is identically zero returns "no difference" forever while
    looking rigorous, which is worse than not running: it manufactures evidence of no effect out
    of an absence of data. This harness says UNDERPOWERED instead, and says why.
    """
    r = subprocess.run([sys.executable, "-u", "-W", "ignore",
                        str(_ROOT / "libs/research_os/brain_ab.py")],
                       cwd=str(_ROOT), capture_output=True, text=True, timeout=300, check=False)
    assert r.returncode == 0
    out = r.stdout
    assert "UNDERPOWERED" in out
    assert "Not a null result" in out, (
        "an empty experiment was reported as a null result, which is the one failure mode this "
        "harness exists to avoid")
    assert "LEADING rung, not money" in out, "a leading-rung caveat was dropped"
