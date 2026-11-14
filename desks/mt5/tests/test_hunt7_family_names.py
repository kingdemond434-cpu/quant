"""run_hunt7 and run_hunt8 resolve their families by name, so a missing one never kills the weekly chain."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import families  # noqa: E402


def _names(module: str = "run_hunt7", table: str = "GLOBAL_FAMILY_NAMES"
           ) -> list[tuple[str, str, dict]]:
    tree = ast.parse((DESK / "research" / f"{module}.py").read_text("utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == table:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{table} not found in {module}")


def test_no_family_is_bound_as_an_attribute_at_import() -> None:
    src = (DESK / "research" / "run_hunt7.py").read_text("utf-8")
    assert "families.family7_spread_state_avoidance" not in src
    assert "families.family4_comex_settlement_effect" not in src


def test_every_named_family_resolves_or_is_reported_missing() -> None:
    rows = _names()
    present = [a for _, a, _ in rows if hasattr(families, a)]
    assert "family_comex_settlement" in present                  # the rename is mapped
    assert len(present) >= 7
    missing = sorted({lbl for lbl, a, _ in rows if not hasattr(families, a)})
    assert missing == ["spread_state_avoidance"]                 # dropped and named
    src = (DESK / "research" / "run_hunt7.py").read_text("utf-8")
    assert '"missing_families": MISSING_FAMILIES' in src


def test_verify_refactor_names_only_live_families() -> None:
    src = (DESK / "side_channels" / "verify_refactor.py").read_text("utf-8")
    for attr in ast.walk(ast.parse(src)):
        if isinstance(attr, ast.Attribute) and isinstance(attr.value, ast.Name) \
                and attr.value.id == "families":
            assert hasattr(families, attr.attr), attr.attr


def test_run_hunt8_cot_families_all_resolve() -> None:
    rows = _names("run_hunt8", "COT_FAMILY_NAMES")
    assert len(rows) == 4 and all(hasattr(families, a) for _, a, _ in rows)
    assert "families.family2_" not in (DESK / "research" / "run_hunt8.py").read_text("utf-8")


def test_the_daily_steps_flags_never_reach_the_hunts_argv() -> None:
    for mod in ("run_hunt7", "run_hunt8"):
        src = (DESK / "research" / f"{mod}.py").read_text("utf-8")
        assert "sys.argv[1]" not in src and "sys.argv[2]" not in src, mod
        assert "main(sys.argv[1:])" in src and "args = list(argv) if argv is not None else []" in src
