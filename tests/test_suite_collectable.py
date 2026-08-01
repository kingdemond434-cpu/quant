"""THE SUITE MUST BE COLLECTABLE. A test file that kills the collector runs no tests -- anywhere.

WHY THIS FENCE EXISTS, AND WHY IT IS A FENCE RATHER THAN A THIRD FIX. Three times in one day the
desk shipped a "test" that was really a SCRIPT: module-level work ending in `raise SystemExit`.
pytest imports every matching file during COLLECTION, so that SystemExit escapes into the
collector and pytest aborts the entire session with INTERNALERROR and exit code 3 -- not 1. Zero
tests run, from any file, including every unrelated one.

  * 2026-08-01 16:44Z, commit 0240cfa: tests/test_gate0_soak.py found and converted. The lesson
    was written down (L0057/R0337, "a red pytest leg can mean zero tests ran"), the ONE instance
    was repaired, and no fence was built.
  * Minutes later, commit 6c81187 shipped tests/test_marginal_admission.py in the same shape.
  * The very next commit, ba19f22, shipped tests/test_sleeve_allocation.py in the same shape.

So the class reappeared TWICE within fifteen minutes of being diagnosed, by an author who had just
written the lesson. That is the desk's standing evidence for the adjacency rule: one instance is
never one instance, and a lesson recorded without a mechanism is a wish. This file is the
mechanism.

WHY EXIT 3 IS THE DANGEROUS PART. Exit 1 means tests failed and someone investigates the failures.
Exit 3 means the collector died -- and a reader who sees "pytest red" reasonably assumes the
former, fixes whatever else looks wrong, and never learns that the suite has not executed at all.
Repairing collection on 2026-08-01 immediately revealed five real failures that had been
structurally invisible. A silent safety net is worse than a missing one, because it is trusted.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT. It parses each test module's AST and rejects
module-level statements that can terminate the interpreter at import: a bare `raise SystemExit`,
`sys.exit(...)`, `exit(...)`, or `os._exit(...)`. It does NOT execute anything and does NOT try to
judge whether a module is slow, heavy, or has import side effects -- static, cheap, and aimed at
exactly the one shape that has actually bitten. Inside a function body these calls are fine (a
test may assert that a CLI exits), so only module level is inspected.

REFUSAL PATH (L1.41 condition 1): a file that cannot be parsed is reported as UNPARSEABLE and
FAILS, never skipped. "I could not check it" must not read as "it is fine" -- that is the
unmeasured-reported-as-OK defect this desk keeps paying for, and it would be especially absurd
here, in the fence whose whole subject is a checker that reported success while doing nothing.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

#: Calls that terminate the interpreter when evaluated at import time.
_FATAL_CALLS = {"exit", "quit"}
_FATAL_ATTRS = {("sys", "exit"), ("os", "_exit")}


def _test_modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("test_*.py") if "__pycache__" not in p.parts)


#: Nodes whose BODIES do not execute at import -- a `def` statement binds a name, it does not run
#: the function. Descending into them is what made the first draft of this fence flag
#: `def test_cli_exits(): raise SystemExit(0)`, a perfectly legitimate test. Its own negative
#: control caught that, which is the argument for having negative controls at all: a fence tuned
#: only on true positives is indistinguishable from one that flags everything.
_NO_IMPORT_TIME_BODY = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def _executes_at_import(node: ast.AST):
    """Yield every node reachable at IMPORT time, pruning bodies that only run when called.

    Class bodies DO execute at import, so ClassDef is not pruned -- only its methods are, and
    those are FunctionDefs the pruning already covers. Decorators and default arguments also run
    at import, so they are walked even on a pruned def.
    """
    if isinstance(node, _NO_IMPORT_TIME_BODY):
        for dec in getattr(node, "decorator_list", []):
            yield from _executes_at_import(dec)
        args = getattr(node, "args", None)
        for default in list(getattr(args, "defaults", [])) + list(getattr(args, "kw_defaults", [])):
            if default is not None:
                yield from _executes_at_import(default)
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from _executes_at_import(child)


def _fatal_at_module_level(tree: ast.Module) -> list[str]:
    """Module-level statements that can end the process during collection."""
    bad: list[str] = []
    for node in tree.body:                       # module level ONLY -- never descend into defs
        for sub in _executes_at_import(node):
            if isinstance(sub, ast.Raise):
                exc = sub.exc
                name = None
                if isinstance(exc, ast.Name):
                    name = exc.id
                elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    name = exc.func.id
                if name == "SystemExit":
                    bad.append(f"line {sub.lineno}: raise SystemExit at module level")
            elif isinstance(sub, ast.Call):
                fn = sub.func
                if isinstance(fn, ast.Name) and fn.id in _FATAL_CALLS:
                    bad.append(f"line {sub.lineno}: {fn.id}() at module level")
                elif (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)
                        and (fn.value.id, fn.attr) in _FATAL_ATTRS):
                    bad.append(f"line {sub.lineno}: {fn.value.id}.{fn.attr}() at module level")
    return bad


@pytest.mark.parametrize("path", _test_modules(), ids=lambda p: p.relative_to(TESTS).as_posix())
def test_module_cannot_kill_the_collector(path: Path) -> None:
    """No test module may terminate the interpreter while pytest is importing it."""
    src = path.read_text("utf-8", errors="replace")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError as e:                     # UNPARSEABLE is a failure, never a skip
        pytest.fail(f"{path.relative_to(ROOT)} is UNPARSEABLE ({e}) -- a file pytest cannot "
                    "import cannot be asserted safe, and unchecked must never read as clean")
    bad = _fatal_at_module_level(tree)
    assert not bad, (
        f"{path.relative_to(ROOT)} terminates the interpreter at import: {'; '.join(bad)}. "
        "pytest evaluates module level during COLLECTION, so this aborts the whole session "
        "(INTERNALERROR, exit 3) and NO test runs anywhere -- see this file's docstring for the "
        "three times it has happened. Convert the script to test functions.")


def test_the_fence_actually_sees_the_suite() -> None:
    """A fence that enumerates nothing passes vacuously -- the welded-gate failure (L1.43).

    This is the assertion that would have caught a broken glob, a moved tests/ root, or a
    parametrize list that silently became empty. Without it the file above could go green while
    checking zero modules, which is the exact shape of defect it exists to prevent.
    """
    mods = _test_modules()
    assert len(mods) > 100, f"only {len(mods)} test modules discovered -- the glob is broken"
    assert (TESTS / "test_marginal_admission.py") in mods, "known module missing from the sweep"


def test_the_detector_fires_on_the_shape_it_was_built_for() -> None:
    """POSITIVE CONTROL. A detector never shown to fire has only had its silence observed.

    Each of these is a shape that actually shipped on this desk (the first is verbatim the line
    that killed collection three times today); the negative cases guard against a detector so
    broad it flags legitimate files and gets switched off for crying wolf.
    """
    fires = [
        "raise SystemExit(1 if fails else 0)",
        "raise SystemExit",
        "import sys\nsys.exit(0)",
        "import os\nos._exit(1)",
        "exit(1)",
        "if fails:\n    raise SystemExit(1)",          # nested in module-level control flow
    ]
    for src in fires:
        assert _fatal_at_module_level(ast.parse(src)), f"detector blind to: {src!r}"

    quiet = [
        "def test_cli_exits():\n    raise SystemExit(0)",     # inside a function -- legitimate
        "def main():\n    sys.exit(1)",
        "import pytest\n\ndef test_x():\n    assert True",
        "class T:\n    def run(self):\n        exit(1)",
    ]
    for src in quiet:
        assert not _fatal_at_module_level(ast.parse(src)), f"false positive on: {src!r}"
