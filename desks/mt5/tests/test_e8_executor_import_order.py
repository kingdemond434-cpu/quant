"""numpy must load at e8_executor import time, never after the broker session is open.

Under a commit-charge spike `import pandas` fails ("The paging file is too small for this
operation to complete"). Imported lazily inside a function that runs after
`TradeLockerVenue().connect()`, that failure was swallowed and a sleeve was silently skipped with a
live session open (measured on the box 2026-11-04). At module top the same failure kills the
process before connect(), which is visible and leaves no half-used session.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "prop" / "e8_executor.py"
_NUMERIC = {"pandas", "numpy"}


def _imported(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {a.name.split(".")[0] for a in node.names}
    if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        return {node.module.split(".")[0]}
    return set()


def test_pandas_is_imported_at_module_top() -> None:
    tree = ast.parse(SRC.read_text("utf-8"))
    top = set().union(*(_imported(n) for n in tree.body))
    assert "pandas" in top, "e8_executor must import pandas at module level"


def test_no_function_imports_pandas_or_numpy_lazily() -> None:
    tree = ast.parse(SRC.read_text("utf-8"))
    lazy = []
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
            for n in ast.walk(fn):
                hit = _imported(n) & _NUMERIC
                if hit:
                    lazy.append(f"{fn.name}:{n.lineno} imports {sorted(hit)}")
    assert not lazy, "lazy numeric import(s) can fail after the broker session opens: " + "; ".join(lazy)
