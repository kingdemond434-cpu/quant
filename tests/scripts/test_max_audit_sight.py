"""THE AUDITOR MUST NOT BE BLIND.

max_audit fences every check: a check that raises is caught and reported as one
`sweep-broken-<label>` defect line rather than crashing the sweep. That fence is correct --
one broken check must not cost the other 54 -- but it has a failure mode that is worse than a
crash, because it is quiet.

Ten of the 55 checks import `libs.*` lazily inside their bodies. `scripts/max_audit.py` did not
put ROOT on sys.path, so under its ONLY real invocation (`python3 scripts/max_audit.py`, where
sys.path[0] is scripts/) every one of them raised ModuleNotFoundError and was fenced. The report
still printed, still said "live defects: 24", and looked healthy. 18% of the desk's own auditor
was dark -- including BOTH mining checks and the entire §35 findings family -- and turning the
lights back on immediately surfaced 7 defects that had been invisible.

This is the fail-open class the desk's own history lists first: the ambiguous branch (a check that
could not run) resolved to "no defect found" rather than "coverage is a lie". These tests are the
regression bar, and they run against the SCRIPT-INVOCATION path specifically, because that is the
path that was broken while every test and REPL invocation stayed green.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts/max_audit.py"


def _deferred_imports() -> list[str]:
    """Every `libs.*`/`scripts.*` module imported INSIDE a function body of max_audit.

    Function-local imports are the ones the module-level smoke test cannot see: max_audit imports
    cleanly at module scope and only explodes when a check actually runs, which is exactly why
    this went unnoticed.
    """
    tree = ast.parse(AUDIT.read_text("utf-8"))
    mods: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods.add(node.module)
            elif isinstance(node, ast.Import):
                mods.update(a.name for a in node.names)
    return sorted(m for m in mods if m.split(".")[0] in {"libs", "scripts"})


def _run_as_script(code: str) -> subprocess.CompletedProcess:
    """Execute `code` under the sys.path max_audit really gets when run as a script.

    Emulated by running with cwd=scripts/ and sys.path[0]=scripts/ -- NOT by importing the
    package from the repo root, which is the invocation that always worked and therefore proved
    nothing.
    """
    return subprocess.run([sys.executable, "-c", code], cwd=str(ROOT / "scripts"),
                          capture_output=True, text=True, timeout=120, check=False)


def test_root_is_on_path_under_script_invocation() -> None:
    """The one-line root cause: ROOT must be importable before any check runs."""
    r = _run_as_script(
        "import runpy,sys;"
        "m=runpy.run_path('max_audit.py', run_name='not_main');"
        "print('libs' if str(m['ROOT']) in sys.path else 'MISSING')"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip() == "libs", (
        "max_audit does not put ROOT on sys.path when run as a script -- every function-local "
        f"`import libs.*` will be fenced into a sweep-broken defect.\n{r.stderr[-1500:]}"
    )


@pytest.mark.parametrize("module", _deferred_imports())
def test_deferred_import_resolves_under_script_invocation(module: str) -> None:
    """Each function-local dependency must import under the script's real sys.path.

    Parametrised per module so a regression names the module that went dark instead of reporting
    a single opaque failure.
    """
    r = _run_as_script(
        "import runpy;runpy.run_path('max_audit.py', run_name='not_main');"
        f"import {module};print('ok')"
    )
    assert r.returncode == 0 and r.stdout.strip() == "ok", (
        f"{module} is imported inside a max_audit check but does not resolve under script "
        f"invocation -- that check is BLIND and its absence reads as 'no defect'.\n"
        f"{r.stderr[-1500:]}"
    )


def test_every_registered_check_runs_without_raising() -> None:
    """No check may be blind. Ports the fence's own condition into a hard assertion.

    The fence keeps a broken check from costing the sweep; this keeps a broken check from being
    quietly acceptable. A defect the auditor cannot see is not a defect the auditor found.
    """
    r = _run_as_script(
        "import runpy;m=runpy.run_path('max_audit.py', run_name='not_main');"
        "bad=[]\n"
        "for name,fn in m['CHECKS']:\n"
        "    try: fn([])\n"
        "    except Exception as e: bad.append(f'{name}: {type(e).__name__}: {e}')\n"
        "print('BLIND=' + str(len(bad)));print(chr(10).join(bad))"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    # SEARCH FOR THE MARKER, never assume it is line one. This assertion used to read
    # `splitlines()[0]` and passed only because no check happened to print anything -- and that
    # was itself an accident of the environment: `check_dependency_drift` prints a one-line note
    # for MINOR drift and appends a silent defect for MAJOR drift, so the test was green in a
    # container whose pandas was a major version away from production and red the moment the
    # container was corrected to production's pins. A test that depends on which lines other
    # code prints is measuring the wrong thing.
    marker = next((ln for ln in r.stdout.splitlines() if ln.startswith("BLIND=")), None)
    assert marker is not None, f"no BLIND= marker in output:\n{r.stdout[-2000:]}"
    assert marker == "BLIND=0", (
        f"max_audit checks failed to run under script invocation -- coverage is overstated by "
        f"exactly this many checks.\n{r.stdout[-2000:]}"
    )


def test_fence_still_catches_a_genuinely_broken_check() -> None:
    """The fence itself must keep working -- the fix is a path fix, not a fence removal.

    Deleting the fence would make one bad check cost the other 54. The correct state is: the
    fence exists, AND nothing is currently in it.
    """
    r = _run_as_script(
        "import runpy;m=runpy.run_path('max_audit.py', run_name='not_main');"
        "d=[]\n"
        "def boom(_): raise RuntimeError('synthetic')\n"
        "m['_fenced'](boom, d, 'synthetic-check')\n"
        "print(d[0][0]);print('synthetic' in d[0][1])"
    )
    assert r.returncode == 0, r.stderr[-2000:]
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "sweep-broken-synthetic-check"
    assert lines[1] == "True", "the fence must report WHY a check broke, not merely that it did"
