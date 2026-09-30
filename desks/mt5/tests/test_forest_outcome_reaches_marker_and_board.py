"""A FOREST RED MUST REACH THE SYNC MARKER AND THE ISSUE BOARD (PR #158 audit, item 1).

`hourly_cycle.main` bound `fat` to the forest_attempts leg and later re-bound `fat` to
fill_attribution, so `sync_marker.json["forest_attempts"]` carried fill_attribution's result and a
forest RED reached no surface. Five more leg names had the same collision on LIVE (rc, pal, exa,
imp, apr). This pins both ends:

  1. every name the sync marker records is bound by exactly ONE `_costed(...)` call in `main`,
     and `forest_attempts` is bound by `_costed("forest_attempts", ...)` itself;
  2. a marker carrying a RED forest_attempts result becomes a `fence:forest_attempts` issue.
"""
from __future__ import annotations

import ast
import collections
import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import issue_board as ib  # noqa: E402

_CYCLE = _DESK / "research" / "hourly_cycle.py"


def _main_fn() -> ast.FunctionDef:
    tree = ast.parse(_CYCLE.read_text("utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")


def _costed_bindings(main: ast.FunctionDef) -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    for n in ast.walk(main):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Call)
                and getattr(n.value.func, "id", None) == "_costed"
                and n.value.args and isinstance(n.value.args[0], ast.Constant)):
            out[n.targets[0].id].append(str(n.value.args[0].value))
    return out


def _marker_dict(main: ast.FunctionDef) -> dict[str, str]:
    """The key -> variable map of the dict literal holding "forest_attempts" (the sync marker)."""
    for n in ast.walk(main):
        if isinstance(n, ast.Dict):
            keys = [k.value for k in n.keys if isinstance(k, ast.Constant)]
            if "forest_attempts" in keys and "fill_attribution" in keys:
                return {k.value: v.id for k, v in zip(n.keys, n.values, strict=True)
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Name)}
    raise AssertionError("no sync-marker dict carrying forest_attempts in hourly_cycle.main")


def test_no_leg_result_is_overwritten_before_the_marker_records_it() -> None:
    main = _main_fn()
    bound = _costed_bindings(main)
    marker = _marker_dict(main)
    rebound = {var: legs for var, legs in bound.items()
               if len(legs) > 1 and var in marker.values()}
    assert not rebound, f"a marker variable is bound by more than one leg: {rebound}"
    assert bound[marker["forest_attempts"]] == ["forest_attempts"]
    assert bound[marker["fill_attribution"]] == ["fill_attribution"]
    assert marker["forest_attempts"] != marker["fill_attribution"]


def _write_marker(root: Path, legs: dict[str, object]) -> None:
    p = root / "desks" / "mt5" / "data" / "sync_marker.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"last_cycle": "2026-09-30T12:00:00+00:00", **legs}), "utf-8")


def test_a_red_forest_fence_reaches_the_issue_board(tmp_path: Path) -> None:
    _write_marker(tmp_path, {
        "forest_attempts": {"exit_code": 1, "tail": "forest attempts: RED never_attempted=12"},
        "fill_attribution": {"exit_code": 0},
    })
    issues = {i.key: i for i in ib.red_fence_legs(tmp_path)}
    assert "fence:forest_attempts" in issues
    assert "RED" in issues["fence:forest_attempts"].detail
    assert not issues["fence:forest_attempts"].auto
    assert "fence:forest_attempts" in {i.key for i in ib.collect(tmp_path)}


def test_a_green_or_absent_forest_fence_raises_nothing(tmp_path: Path) -> None:
    assert ib.red_fence_legs(tmp_path) == []          # no marker: the cycle's absence is elsewhere
    _write_marker(tmp_path, {"forest_attempts": {"exit_code": 0},
                             "fill_attribution": {"exit_code": 1}})
    assert ib.red_fence_legs(tmp_path) == []          # fill_attribution is not a fence leg
