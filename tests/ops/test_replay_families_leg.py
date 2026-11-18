"""The families leg of replay-shadow (Governance on #1038 and #1241, 2026-11-18).

The FTMO leg stubs `families.get_family_func`, so the family code the money path reaches lazily
was never run and every change to it read UNMEASURED. The families leg runs every live family
through the executor's own input door on the scenario's bars, beside the stub, and asks the bandit
for each family's alpha cluster. These pins hold Governance's conditions: the REAL family code
runs (a deliberately changed family output reads DIVERGED, end to end through the child), a
family that raises or times out reads UNMEASURED and never MATCHES, a head that raises where the
base ran FAILS, a moved alpha cluster FAILS, and a changed function counts as measured only when a
clean call ran it on both trees.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

FAM = "desks/mt5/mt5desk/fam_toy.py"

TOY_FAMILIES = """
FAMILY_REGISTRY = {}


def live_family_names():
    from mt5desk import fam_toy
    return sorted(fam_toy.ALL)


def get_family_func(name):
    from mt5desk import fam_toy
    return fam_toy.ALL.get(name)
"""
TOY_INPUTS = """
def resolve(sym, family, params, h1):
    return ({}, "ok") if family != "needs_peer" else (None, "no peer_symbol on the candidate")
"""
TOY_BANDIT = """
def _cluster_of(row):
    return {CLUSTERS}.get(row.get("family"))
"""


def _fam(body: str) -> str:
    return (
        "import types\n\n\n"
        "def family_steady(df):\n"
        f"{body}\n\n\n"
        "def family_boom(df):\n"
        "    raise ValueError('boom')\n\n\n"
        "def family_needs_peer(df, peer):\n"
        "    return []\n\n\n"
        "ALL = {'steady': family_steady, 'boom': family_boom, 'needs_peer': family_needs_peer}\n"
    )


STEADY = (
    "    t = df.index[-2]\n"
    "    return [types.SimpleNamespace(time=t, side=1, stop=1.0, target=2.0, ttl_bars=6)]"
)
FLIPPED = STEADY.replace("side=1", "side=-1")


def _tree(root: Path, fam_body: str, clusters: str = "{'steady': 'trend'}") -> Path:
    for d in ("desks/mt5/mt5desk", "libs/research"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for init in ("desks/mt5/mt5desk/__init__.py", "libs/__init__.py", "libs/research/__init__.py"):
        (root / init).write_text("", "utf-8")
    (root / "desks/mt5/mt5desk/families.py").write_text(TOY_FAMILIES, "utf-8")
    (root / "desks/mt5/mt5desk/family_inputs.py").write_text(TOY_INPUTS, "utf-8")
    (root / FAM).write_text(_fam(fam_body), "utf-8")
    (root / "libs/research/bandit.py").write_text(
        TOY_BANDIT.replace("{CLUSTERS}", clusters), "utf-8"
    )
    return root


def _child_leg(tree: Path) -> dict[str, Any]:
    """The real child's families_leg on `tree`, in a fresh process (as the harness runs it)."""
    code = (
        "import json, sys\n"
        f"sys.path[:0] = [{str(ROOT / 'ops/release')!r}, {str(tree)!r}, "
        f"{str(tree / 'desks/mt5')!r}]\n"
        "import replay_child as rc\n"
        "from pathlib import Path\n"
        "sc = {'day': '2026-10-13', 'shape': 'up_break', 'seed': 3}\n"
        f"print(json.dumps(rc.families_leg(Path({str(tree)!r}), sc)))\n"
    )
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return dict(json.loads(p.stdout.strip().splitlines()[-1]))


def test_a_changed_family_output_reads_diverged_through_the_real_child(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", FLIPPED)
    b, h = _child_leg(base), _child_leg(head)
    assert b["out"]["steady"]["n"] == 1  # the real family ran, not a stub
    assert b["out"]["boom"] == {"error": "ValueError"}
    assert "unresolved" in b["out"]["needs_peer"]
    problems, _rb, _rh = rs.families_diff(b, h, "s", str(base), str(head))
    assert problems == ["s: families leg: steady decides differently"]
    # the same tree twice agrees: deterministic, seeded
    same, rb, _rh = rs.families_diff(b, _child_leg(base), "s", str(base), str(base))
    assert same == []
    assert "family_steady" in rb[FAM]
    assert "family_boom" not in rb[FAM]  # a call that raised adds nothing


def test_a_raise_reads_unmeasured_never_matches(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", STEADY)
    # change ONLY the family that raises: no clean call ran it, so the file stays UNMEASURED
    src = (head / FAM).read_text("utf-8").replace("raise ValueError('boom')", "raise KeyError")
    (head / FAM).write_text(src, "utf-8")
    b, h = _child_leg(base), _child_leg(head)
    problems, rb, rh = rs.families_diff(b, h, "s", str(base), str(head))
    assert problems == []  # it raised on both: not a failure, and not a match either
    assert not rs.families_measured(base, head, FAM, rb, rh)
    # while a change to the family that ran cleanly on both IS measured
    (head / FAM).write_text(_fam("    _same = 0\n" + STEADY), "utf-8")
    h2 = _child_leg(head)
    _p, rb, rh = rs.families_diff(b, h2, "s", str(base), str(head))
    assert rs.families_measured(base, head, FAM, rb, rh)


def test_a_head_that_raises_where_the_base_ran_fails(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", "    raise RuntimeError('broken')")
    problems, _rb, _rh = rs.families_diff(
        _child_leg(base), _child_leg(head), "s", str(base), str(head)
    )
    assert problems == ["s: families leg: steady raises on the PR (RuntimeError)"]


def test_a_moved_alpha_cluster_fails(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", STEADY, clusters="{'steady': 'carry'}")
    problems, _rb, _rh = rs.families_diff(
        _child_leg(base), _child_leg(head), "s", str(base), str(head)
    )
    assert problems == ["s: alpha cluster of steady moves: base trend PR carry"]


def _leg(ran: dict[str, list[str]], out: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "out": out if out is not None else {"steady": {"n": 1, "sha": "x"}},
        "files": {},
        "clusters": {"steady": "trend"},
        "reached": [],
        "ran": ran,
    }


def _compare(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, base_ran: list[str], head_ran: list[str]
) -> dict[str, Any]:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", FLIPPED)
    rans = {"base": base_ran, "head": head_ran}
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}

    def fake(tree: Path, sc: dict[str, Any]) -> dict[str, Any]:
        f = str((tree / FAM).resolve())
        return {"steps": [step], "imported": [], "families": _leg({f: rans[tree.name]})}

    monkeypatch.setattr(rs, "run_tree", fake)
    monkeypatch.delenv(rs.DECLARED_ENV, raising=False)
    return rs.compare(base, head, [FAM], [{"id": "s", "hours": [7.0], "families": True}])


def test_the_harness_counts_a_change_only_where_a_clean_call_ran_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unmeasured = f"UNMEASURED money-path change (the replay never imported it): {FAM}"
    rep = _compare(tmp_path / "a", monkeypatch, ["family_steady"], ["family_steady"])
    assert unmeasured not in rep["problems"]
    rep = _compare(tmp_path / "b", monkeypatch, ["family_steady"], [])
    assert unmeasured in rep["problems"]
    assert rep["verdict"] == "FAIL"


def test_the_ftmo_stub_stays_beside_the_leg() -> None:
    child = (ROOT / "ops/release/replay_child.py").read_text("utf-8")
    assert '(families, "get_family_func", lambda f: family)' in child
    assert "def families_leg(" in child
    grid = rs.scenarios()
    assert any(sc.get("families") for sc in grid)
    assert all(not sc.get("families") for sc in grid if not sc["id"].endswith("/flat"))
