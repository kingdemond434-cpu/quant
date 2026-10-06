"""The survivor-acquisition controllers (root `hourly_controller.py`, the VPS unit's entry point,
and its canonical copy in side_channels/): UNMEASURED stays UNMEASURED in the cycle log, and every
function the controller calls is bound. Both files import heavy, path-pinned components at module
scope, so they are read as source rather than imported."""
from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
FILES = (_ROOT / "hourly_controller.py",
         _ROOT / "desks" / "mt5" / "side_channels" / "hourly_controller.py")


def _phase_count(path: Path) -> Any:
    tree = ast.parse(path.read_text("utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "phase_count")
    ns: dict[str, Any] = {"UNMEASURED": "UNMEASURED"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
    return ns["phase_count"]


def test_unmeasured_phases_are_never_counted_as_zero() -> None:
    for path in FILES:
        count = _phase_count(path)
        phases = {"queue": {"status": "UNMEASURED", "why": "not here"},
                  "extract": {"hypotheses": 7},
                  "discover": {"error": "boom", "hypotheses": 0}}
        assert count(phases, "queue", "queued") == "UNMEASURED", path
        assert count(phases, "extract", "hypotheses") == 7, path
        assert count(phases, "missing", "x") == "UNMEASURED", path
        assert count(phases, "discover", "hypotheses") == "UNMEASURED", path
        src = path.read_text("utf-8")
        assert '.get("queue", {}).get("queued", 0)' not in src, path
        assert '"hypotheses_queued": UNMEASURED' in src, path


def _bound_names(tree: ast.Module) -> set[str]:
    names = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            if not isinstance(node, ast.ClassDef):
                a = node.args
                names |= {x.arg for x in a.args + a.kwonlyargs + a.posonlyargs}
                names |= {x.arg for x in (a.vararg, a.kwarg) if x is not None}
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def test_every_called_function_is_bound() -> None:
    """`run_calibration` was called with no import in the root controller (its import fell out
    with the path shim), a NameError on the first cycle with calibration on."""
    for path in FILES:
        tree = ast.parse(path.read_text("utf-8"))
        bound = _bound_names(tree)
        unbound = sorted({n.func.id for n in ast.walk(tree)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                          and n.func.id not in bound})
        assert unbound == [], f"{path.name}: {unbound}"
    root_src = FILES[0].read_text("utf-8")
    assert "run_calibration," in root_src.split("from gate_calibration import", 1)[1].split("\n")[0]
