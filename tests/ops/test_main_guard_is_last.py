"""Nothing a script needs may be defined AFTER its `if __name__ == "__main__":` guard.

MEASURED 2026-10-29 (MT5-ContractTerms rc 1). `desks/mt5/mt5desk/tape.py` defined its error
helper `_explain` below `raise SystemExit(main())`. Imported, the module is whole; run as
`python -m mt5desk.tape`, main() executes when the guard is reached -- before the interpreter has
seen the def -- so the one branch that explains WHY the terminal would not attach died with
`NameError: name '_explain' is not defined`. Every test that imported the module passed, and
ruff's undefined-name rule cannot see it, because the name IS defined at module level; it is the
execution ORDER that is wrong.

The same sweep found scripts/max_audit.py with ten checks (survivor-pipeline .. recursion-rule)
appended to CHECKS below its guard: run as a script, none of them ever ran.

THE RULE. Once a module reaches its `__main__` guard, nothing after it may be a def, a class, an
import or an assignment -- the shapes main() could depend on. `_retired/` trees are exempt (they
run nowhere).

KNOWN OFFENDERS, LEFT FOR THEIR OWN PR. scripts/max_audit.py and
data/brain_hunter_s57_streakiness.py have the shape too. Moving their guards changes what they
run (max_audit gains ten checks it has never executed), so it ships separately. The list may only
shrink: an entry that no longer has the shape fails here until it is removed.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SHAPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign,
           ast.AugAssign, ast.Import, ast.ImportFrom)
_SKIP_PARTS = {".git", ".venv", "venv", "node_modules", "_retired", "__pycache__"}
KNOWN_OFFENDERS = frozenset({"scripts/max_audit.py", "data/brain_hunter_s57_streakiness.py"})


def _python_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.py"], capture_output=True,
                             text=True, timeout=60, check=True).stdout.split()
        paths = [ROOT / p for p in out]
    except (OSError, subprocess.SubprocessError):
        paths = list(ROOT.rglob("*.py"))
    return [p for p in paths if p.is_file() and not (_SKIP_PARTS & set(p.parts))]


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    sides = [node.test.left, *node.test.comparators]
    return (any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
            and any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides))


def after_guard(source: str) -> list[tuple[int, str]]:
    """(line, what) for every definition that follows a module-level `__main__` guard."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    seen = False
    late: list[tuple[int, str]] = []
    for node in tree.body:
        if _is_main_guard(node):
            seen = True
            continue
        if seen and isinstance(node, _SHAPES):
            late.append((node.lineno, getattr(node, "name", type(node).__name__)))
    return late


def test_the_rule_catches_the_measured_shape() -> None:
    src = ("def main():\n    return _explain(1)\n\n"
           "if __name__ == '__main__':\n    raise SystemExit(main())\n\n"
           "def _explain(e):\n    return str(e)\n")
    assert after_guard(src) == [(7, "_explain")]
    assert after_guard("def main():\n    pass\n\nif __name__ == '__main__':\n    main()\n") == []


def test_no_tracked_module_defines_anything_after_its_main_guard() -> None:
    bad = []
    for path in _python_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in KNOWN_OFFENDERS:
            continue
        for line, what in after_guard(path.read_text("utf-8", errors="replace")):
            bad.append(f"{rel}:{line} {what}")
    assert not bad, ("defined after the `__main__` guard, so missing when run as a script "
                     "(move the guard to the end of the file):\n  " + "\n  ".join(bad))


def test_known_offenders_only_shrink() -> None:
    """An exemption whose file is gone or no longer has the shape must be deleted."""
    stale = sorted(rel for rel in KNOWN_OFFENDERS
                   if not (ROOT / rel).is_file()
                   or not after_guard((ROOT / rel).read_text("utf-8", errors="replace")))
    assert not stale, f"remove from KNOWN_OFFENDERS, the shape is gone: {stale}"
