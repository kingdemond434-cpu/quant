"""Every `families.<name>` a desk module calls exists in the canonical library (2026-10-29).

MT5-Daily's first step, `weekly_hunt_refresh`, imports run_hunt7..12. run_hunt7 named
`families.family7_spread_state_avoidance` and `families.family4_comex_settlement_effect`, and
run_hunt8 the `family2_cot_*` names, at import time -- none of which mt5desk/families.py has
carried since its 2026-08-27 restoration (the COT and COMEX families were renamed with identical
signatures; family7 is gone). The step died with AttributeError every run (box 09:19Z), and the
weekly sweep never advanced. The library is the registry; a caller naming a family it does not
hold is the side that is wrong, and this fence finds every such caller before the box does.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for p in (str(_DESK), str(_DESK.parent.parent)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import families  # noqa: E402

SKIP_PARTS = {"_retired", "tests", "__pycache__"}


def _binds_library(tree: ast.Module) -> bool:
    imported = any(isinstance(n, ast.ImportFrom) and n.module == "mt5desk"
                   and any(a.name == "families" and a.asname is None for a in n.names)
                   for n in ast.walk(tree))
    rebound = any(isinstance(n, ast.Name) and n.id == "families" and isinstance(n.ctx, ast.Store)
                  for n in ast.walk(tree))
    return imported and not rebound


def test_every_family_a_desk_module_names_is_in_the_library():
    missing: dict[str, list[str]] = {}
    for f in sorted(_DESK.rglob("*.py")):
        if SKIP_PARTS & set(f.relative_to(_DESK).parts):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if not _binds_library(tree):
            continue
        bad = sorted({n.attr for n in ast.walk(tree)
                      if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
                      and n.value.id == "families" and not hasattr(families, n.attr)})
        if bad:
            missing[str(f.relative_to(_DESK))] = bad
    assert not missing, f"callers naming families the library does not hold: {missing}"


def test_the_weekly_hunt_refresh_modules_are_scanned():
    for name in ("run_hunt7", "run_hunt8", "run_hunt9", "run_hunt10", "run_hunt12"):
        tree = ast.parse((_DESK / "research" / f"{name}.py").read_text(encoding="utf-8"))
        assert _binds_library(tree), name
