"""The replay-shadow signal leg (ops/release/replay_shadow.py, replay_child.py --signals).

The leg turns a changed family-path file from UNMEASURED into measured only when every statement
the PR changed actually ran inside a family call that traded on the base and decided the same on
the PR. These tests hold the rail to that on toy trees whose one family has a branch the grid
always takes and a branch it never takes:

- an order-changing edit in the branch the grid takes is CAUGHT as a divergence;
- an order-changing edit in the branch the grid never takes stays UNMEASURED;
- a comment-only edit and an equivalent rewrite of executed code are measured and agree;
- the integration in `compare` removes only the files the leg measured.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "_rs_signal_leg", ROOT / "ops" / "release" / "replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
sys.modules["_rs_signal_leg"] = rs
_spec.loader.exec_module(rs)

FAMILY = "desks/mt5/mt5desk/family_toy.py"

TOY_FAMILY = '''"""A toy family: trades every up-close; a second branch no frame can reach."""


def family_toy(df, *, k=2.0, side=1):
    out = []
    closes = df["close"].tolist()
    for i in range(20, len(closes)):
        if closes[i] > closes[i - 1]:
            px = closes[i]
            out.append({"time": str(df.index[i]), "side": side, "stop": px - k, "target": px + k})
        elif closes[i] < -1e9:
            out.append({"time": str(df.index[i]), "side": -side, "stop": 0.0, "target": 0.0})
    return out
'''

TOY_SUPPORT = {
    "desks/mt5/mt5desk/__init__.py": "",
    "desks/mt5/mt5desk/families.py": (
        "from mt5desk.family_toy import family_toy\n\n\n"
        "def live_family_names():\n    return ['toy']\n\n\n"
        "def get_family_func(name):\n    return family_toy if name == 'toy' else None\n\n\n"
        "def get_param_grid(name):\n    return {'k': [2.0, 3.0]}\n"
    ),
    "desks/mt5/mt5desk/executables.py": (
        "def hunt16_families():\n    return {}\n\n\n"
        "def resolve_family(name):\n"
        "    from mt5desk import families\n\n"
        "    return families.get_family_func(name)\n"
    ),
    "desks/mt5/mt5desk/family_call.py": (
        "def signals(fn, bars, *, side, params=None):\n"
        "    return list(fn(bars, side=side, **(params or {})))\n\n\n"
        "def hunt16_signals(fn, bars, side):\n    return list(fn(bars, side))\n"
    ),
}


def _tree(root: Path, family_src: str) -> Path:
    for rel, text in {**TOY_SUPPORT, FAMILY: family_src}.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
    return root


def _leg(tmp_path: Path, head_src: str) -> tuple[list[str], set[str], dict[str, str]]:
    base = _tree(tmp_path / "base", TOY_FAMILY)
    head = _tree(tmp_path / "head", head_src)
    sb, sh = rs.run_signals(base, [FAMILY]), rs.run_signals(head, [FAMILY])
    assert "crash" not in sb, sb
    assert "crash" not in sh, sh
    problems, agreed = rs.signal_problems(sb, sh)
    measured, why = rs.signal_measured(base, head, [FAMILY], sb, sh, agreed)
    return problems, measured, why


def test_an_order_changing_edit_the_grid_reaches_is_caught(tmp_path: Path) -> None:
    head = TOY_FAMILY.replace('"stop": px - k,', '"stop": px - 2 * k,')
    assert head != TOY_FAMILY
    problems, _measured, _why = _leg(tmp_path, head)
    assert problems, "a wider stop on every traded signal must read as a divergence"
    assert all(p.startswith("signal leg: toy|") for p in problems)
    assert any("stop" in p for p in problems)


def test_an_order_changing_edit_the_grid_never_reaches_stays_unmeasured(tmp_path: Path) -> None:
    head = TOY_FAMILY.replace('"stop": 0.0, "target": 0.0', '"stop": 1.0, "target": 0.0')
    assert head != TOY_FAMILY
    problems, measured, why = _leg(tmp_path, head)
    assert not problems  # nothing the grid ran differs...
    assert FAMILY not in measured  # ...and that is exactly why it is not a measurement
    assert "never ran" in why[FAMILY]


def test_a_comment_only_edit_is_measured(tmp_path: Path) -> None:
    head = TOY_FAMILY.replace("    out = []\n", "    out = []  # signals\n    # a note\n")
    problems, measured, why = _leg(tmp_path, head)
    assert not problems
    assert measured == {FAMILY}, why


def test_an_equivalent_rewrite_of_executed_code_is_measured(tmp_path: Path) -> None:
    head = TOY_FAMILY.replace('"target": px + k}', '"target": k + px}')
    assert head != TOY_FAMILY
    problems, measured, why = _leg(tmp_path, head)
    assert not problems
    assert measured == {FAMILY}, why


def test_a_removed_statement_must_have_run_on_the_base(tmp_path: Path) -> None:
    # the unreachable branch removed: its statements never ran on the base, so not measured
    head = TOY_FAMILY.replace(
        '        elif closes[i] < -1e9:\n            out.append({"time": str(df.index[i]), '
        '"side": -side, "stop": 0.0, "target": 0.0})\n',
        "",
    )
    assert head != TOY_FAMILY
    problems, measured, why = _leg(tmp_path, head)
    assert not problems
    assert FAMILY not in measured
    assert "base" in why[FAMILY]


def test_a_new_family_file_is_never_measured_by_its_own_calls(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", TOY_FAMILY)
    head = _tree(tmp_path / "head", TOY_FAMILY)
    new = "desks/mt5/mt5desk/family_new.py"
    (head / new).write_text("def family_new(df, *, side=1):\n    return []\n", "utf-8")
    sb, sh = rs.run_signals(base, [new]), rs.run_signals(head, [new])
    problems, agreed = rs.signal_problems(sb, sh)
    measured, why = rs.signal_measured(base, head, [new], sb, sh, agreed)
    assert not problems
    assert new not in measured and why[new] == "the signal leg never imported it"


def test_compare_removes_only_what_the_signal_leg_measured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through `compare`: the scenario legs are faked (they need the E8 book); the
    signal leg runs for real on the toy trees."""
    base = _tree(tmp_path / "base", TOY_FAMILY)
    head = _tree(tmp_path / "head", TOY_FAMILY.replace('"target": px + k}', '"target": k + px}'))
    other = "desks/mt5/mt5desk/untouched_by_families.py"
    (base / other).write_text("X_RAIL = 1\n\ndef f():\n    return 1\n", "utf-8")
    (head / other).write_text("X_RAIL = 1\n\ndef f():\n    return 2\n", "utf-8")

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        return {"steps": [{"hour": 1.0, "intents": [{"side": 1}], "doc": {}}], "imported": []}

    monkeypatch.setattr(rs, "run_tree", fake)
    rep = rs.compare(base, head, [FAMILY, other], grid=[{"id": "toy", "hours": [1.0]}])
    unmeasured = [p for p in rep["problems"] if p.startswith("UNMEASURED money-path change")]
    assert unmeasured == [
        f"UNMEASURED money-path change (the replay never imported it): {other}"
    ], rep["problems"]
    assert rep["signal_leg"]["measured"] == [FAMILY]
    assert other in rep["signal_leg"]["unmeasured"]
    assert rep["verdict"] == "FAIL"


@pytest.mark.parametrize(
    ("old", "new", "want"),
    [
        ("x = 1\n", "x = 1  # why\n", {(1, 1)}),  # a code line's comment is still that line
        ("x = 1\n", "# only prose\nx = 1\n", set()),
        ('def f():\n    """a"""\n    return 1\n', 'def f():\n    """b"""\n    return 1\n', set()),
        ("def f(a):\n    return a\n", "def f(a, b=2):\n    return a\n", {(2, 2)}),
        ("if a:\n    b()\n", "if c:\n    b()\n", {(1, 1)}),
        ("y = (1,\n     2)\n", "y = (1,\n     3)\n", {(1, 2)}),
    ],
)
def test_changed_statements(old: str, new: str, want: set[tuple[int, int]]) -> None:
    assert rs.changed_statements(old, new) == want


def test_signal_problems_compares_outcomes() -> None:
    ok = {"digest": "a", "n": 2, "first": [{"stop": 1.0}]}
    quiet = {"digest": "q", "n": 0, "first": []}
    b = {
        "calls": {
            "same": ok,
            "moved": ok,
            "quiet": quiet,
            "slow_base": {"timeout": True},
            "slow_pr": ok,
            "raises": {"error": "KeyError"},
        }
    }
    h = {
        "calls": {
            "same": ok,
            "moved": {"digest": "b", "n": 2, "first": [{"stop": 2.0}]},
            "quiet": quiet,
            "slow_base": ok,
            "slow_pr": {"timeout": True},
            "raises": {"error": "KeyError", "detail": "different words"},
        }
    }
    problems, agreed = rs.signal_problems(b, h)
    assert agreed == {"same"}  # only a call that TRADED on the base and agreed measures lines
    text = "\n".join(problems)
    assert "moved: the PR decides differently: #0 stop 1.0 -> 2.0" in text
    assert "slow_pr: the PR's tree timed out" in text
    assert "slow_base" not in text and "raises" not in text and "quiet" not in text
