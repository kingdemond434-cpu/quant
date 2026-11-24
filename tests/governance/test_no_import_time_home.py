"""No module may call ``Path.home()`` at import time.

The box CI job runs with a whitelisted environment that has no USERPROFILE/HOMEDRIVE/HOMEPATH.
On Windows, Python 3.14's ``Path.home()`` then raises ``RuntimeError: Could not determine home
directory``. Six module-level calls (scripts/max_audit.py alone accounted for 34 of them) broke
test collection in 38 files on every forge PR from 11-20, so nothing could merge. A module-level
home lookup must use ``Path(os.path.expanduser("~"))``, which degrades to ``~`` and never raises,
or move into a function.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _is_path_home(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "home" and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "Path" and not node.args)


def _main_guard(stmt: ast.stmt) -> bool:
    return (isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Compare)
            and isinstance(stmt.test.left, ast.Name) and stmt.test.left.id == "__name__")


_DEFERRED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _import_time_hits(tree: ast.Module) -> list[int]:
    hits: list[int] = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, _DEFERRED):
            if isinstance(node, ast.ClassDef):  # a class body runs at import; its methods don't
                for item in node.body:
                    walk(item)
                for d in node.decorator_list:
                    walk(d)
            else:
                for d in getattr(node, "decorator_list", []):
                    walk(d)
                args = getattr(node, "args", None)
                if args is not None:
                    for default in [*args.defaults, *args.kw_defaults]:
                        if default is not None:
                            walk(default)
            return
        if _is_path_home(node):
            hits.append(node.lineno)
        for child in ast.iter_child_nodes(node):
            walk(child)

    for stmt in tree.body:
        if not _main_guard(stmt):
            walk(stmt)
    return hits


def _tracked_py() -> list[Path]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.py"], capture_output=True,
                         text=True, check=True).stdout.split()
    return [ROOT / p for p in out if (ROOT / p).is_file()]


def test_no_module_calls_path_home_at_import() -> None:
    bad = []
    for p in _tracked_py():
        try:
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        bad += [f"{p.relative_to(ROOT).as_posix()}:{n}" for n in _import_time_hits(tree)]
    assert not bad, "import-time Path.home() breaks box CI collection: " + ", ".join(bad)


def test_the_checker_sees_module_level_and_ignores_function_bodies() -> None:
    src = ("from pathlib import Path\nA = Path.home() / 'x'\n"
           "def f(): return Path.home()\n"
           "class C:\n    B = Path.home()\n    def m(self): return Path.home()\n"
           "if __name__ == '__main__':\n    Path.home()\n")
    assert _import_time_hits(ast.parse(src)) == [2, 5]
