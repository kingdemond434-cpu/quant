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

import datetime as dt
import decimal
import enum
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "replay_shadow", ROOT / "ops/release/replay_shadow.py"
)
assert _spec is not None and _spec.loader is not None
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)
_cspec = importlib.util.spec_from_file_location(
    "replay_child", ROOT / "ops/release/replay_child.py"
)
assert _cspec is not None and _cspec.loader is not None
rc = importlib.util.module_from_spec(_cspec)
_cspec.loader.exec_module(rc)

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


def _fam(body: str, tail: str = "") -> str:
    return (
        "import types\n\n\n"
        "def family_steady(df):\n"
        f"{body}\n\n\n"
        "def family_boom(df):\n"
        "    raise ValueError('boom')\n\n\n"
        "def family_needs_peer(df, peer):\n"
        "    return []\n\n\n"
        "ALL = {'steady': family_steady, 'boom': family_boom, 'needs_peer': family_needs_peer}\n"
        f"{tail}"
    )


STEADY = (
    "    t = df.index[-2]\n"
    "    return [types.SimpleNamespace(time=t, side=1, stop=1.0, target=2.0, ttl_bars=6)]"
)
FLIPPED = STEADY.replace("side=1", "side=-1")


def _tree(root: Path, fam_body: str, clusters: str = "{'steady': 'trend'}", tail: str = "") -> Path:
    for d in ("desks/mt5/mt5desk", "libs/research"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for init in ("desks/mt5/mt5desk/__init__.py", "libs/__init__.py", "libs/research/__init__.py"):
        (root / init).write_text("", "utf-8")
    (root / "desks/mt5/mt5desk/families.py").write_text(TOY_FAMILIES, "utf-8")
    (root / "desks/mt5/mt5desk/family_inputs.py").write_text(TOY_INPUTS, "utf-8")
    (root / FAM).write_text(_fam(fam_body, tail), "utf-8")
    (root / "libs/research/bandit.py").write_text(
        TOY_BANDIT.replace("{CLUSTERS}", clusters), "utf-8"
    )
    return root


def _child_leg(tree: Path, timeout: float = 5.0, pre: str = "") -> dict[str, Any]:
    """The real child's families_leg on `tree`, in a fresh process (as the harness runs it)."""
    code = (
        "import json, sys\n"
        f"sys.path[:0] = [{str(ROOT / 'ops/release')!r}, {str(tree)!r}, "
        f"{str(tree / 'desks/mt5')!r}]\n"
        "import replay_child as rc\n"
        f"rc.FAMILY_TIMEOUT_S = {timeout!r}\n"
        f"{pre}"
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
    problems, _rb, _rh, _x = rs.families_diff(b, h, "s", str(base), str(head))
    assert problems == ["s: families leg: steady decides differently"]
    # the same tree twice agrees: deterministic, seeded
    same, rb, _rh, _x = rs.families_diff(b, _child_leg(base), "s", str(base), str(base))
    assert same == []
    assert _at(base, "family_steady") in rb[FAM]
    assert _at(base, "family_boom") not in rb[FAM]  # a call that raised adds nothing


def test_a_raise_reads_unmeasured_never_matches(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", STEADY)
    # change ONLY the family that raises: no clean call ran it, so the file stays UNMEASURED
    src = (head / FAM).read_text("utf-8").replace("raise ValueError('boom')", "raise KeyError")
    (head / FAM).write_text(src, "utf-8")
    b, h = _child_leg(base), _child_leg(head)
    problems, rb, rh, _x = rs.families_diff(b, h, "s", str(base), str(head))
    assert problems == []  # it raised on both: not a failure, and not a match either
    assert not rs.families_measured(base, head, FAM, rb, rh)
    # while a change to the family that ran cleanly on both IS measured
    (head / FAM).write_text(_fam("    _same = 0\n" + STEADY), "utf-8")
    h2 = _child_leg(head)
    _p, rb, rh, _x = rs.families_diff(b, h2, "s", str(base), str(head))
    assert rs.families_measured(base, head, FAM, rb, rh)


def test_a_head_that_raises_where_the_base_ran_fails(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", "    raise RuntimeError('broken')")
    problems, _rb, _rh, _x = rs.families_diff(
        _child_leg(base), _child_leg(head), "s", str(base), str(head)
    )
    assert problems == ["s: families leg: steady raises on the PR (RuntimeError)"]


def test_a_moved_alpha_cluster_fails(tmp_path: Path) -> None:
    base = _tree(tmp_path / "base", STEADY)
    head = _tree(tmp_path / "head", STEADY, clusters="{'steady': 'carry'}")
    problems, _rb, _rh, _x = rs.families_diff(
        _child_leg(base), _child_leg(head), "s", str(base), str(head)
    )
    assert problems == ["s: alpha cluster of steady moves: base trend PR carry"]


def _at(tree: Path, qualname: str, f: str = FAM) -> str:
    """`qualname@first line`, as the profiler and `families_measured` spell a unit."""
    return f"{qualname}@{rs._units((tree / f).read_text('utf-8'))[(qualname, 0)][1]}"


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
    rep = _compare(tmp_path / "a", monkeypatch, ["family_steady@4"], ["family_steady@4"])
    assert unmeasured not in rep["problems"]
    rep = _compare(tmp_path / "b", monkeypatch, ["family_steady@4"], [])
    assert unmeasured in rep["problems"]
    assert rep["verdict"] == "FAIL"


def test_the_ftmo_stub_stays_beside_the_leg() -> None:
    child = (ROOT / "ops/release/replay_child.py").read_text("utf-8")
    assert '(families, "get_family_func", lambda f: family)' in child
    assert "def families_leg(" in child
    grid = rs.scenarios()
    assert any(sc.get("families") for sc in grid)
    assert all(not sc.get("families") for sc in grid if not sc["id"].endswith("/flat"))


# ---- Auditor HOLD on #1363 (MF1, MF2, MF3, SF1, SF2): one negative pin per case ----

MF1_CASES = {
    "def_in_if_and_try": (
        "if True:\n"
        "    def hidden(df):\n"
        "        return 1\n"
        "try:\n"
        "    import _no_such_module_\n"
        "except ImportError:\n"
        "    def fallback(df):\n"
        "        return 1\n"
    ),
    "nested_class_method": (
        "class Outer:\n    class Inner:\n        def method(self):\n            return 1\n"
    ),
    "module_and_class_lambda": ("pick = lambda d: 1\nclass Holder:\n    grab = lambda self: 1\n"),
}


@pytest.mark.parametrize("case", sorted(MF1_CASES))
def test_mf1_a_changed_unit_imported_but_never_called_reads_unmeasured(
    tmp_path: Path, case: str
) -> None:
    tail = MF1_CASES[case]
    base = _tree(tmp_path / "base", STEADY, tail=tail)
    b = _child_leg(base)
    assert b["out"]["steady"]["n"] == 1
    # every occurrence of `1` in the tail becomes `2`, one unit at a time: each change alone,
    # imported on both trees (the module body ran) and never called, must stay UNMEASURED
    n_units = tail.count("1\n")
    assert n_units >= 1
    for i in range(n_units):
        parts = tail.split("1\n")
        changed = "1\n".join(parts[: i + 1]) + "2\n" + "1\n".join(parts[i + 1 :])
        head = _tree(tmp_path / f"head{i}", STEADY, tail=changed)
        h = _child_leg(head)
        problems, rb, rh, _x = rs.families_diff(b, h, "s", str(base), str(head))
        assert problems == []
        assert any(q.startswith("<module>@") for q in rh[FAM])  # the file WAS imported
        assert not rs.families_measured(base, head, FAM, rb, rh), (case, i)


def test_mf1_units_are_named_as_the_profiler_names_them() -> None:
    src = (
        "import functools\n"
        "if True:\n"
        "    def a():\n"
        "        f = lambda: 1\n"
        "        return f\n"
        "class C:\n"
        "    g = lambda self: 1\n"
        "    class D:\n"
        "        @functools.lru_cache\n"
        "        def m(self):\n"
        "            def inner():\n"
        "                return 1\n"
        "            return inner\n"
        "h = lambda: 2\n"
    )
    seen: set[str] = set()

    def walk(co: Any) -> None:
        seen.add(f"{co.co_qualname}@{co.co_firstlineno}")
        for c in co.co_consts:
            if hasattr(c, "co_qualname"):
                walk(c)

    walk(compile(src, "x.py", "exec"))
    named = {f"{q}@{line}" for (q, _k), (_d, line) in rs._units(src).items()}
    assert named == seen


def _helper_tree(root: Path, hang_b: bool) -> Path:
    _tree(root, STEADY, clusters="{'a': 'trend', 'b': 'trend'}")
    hang = "    if who == 'b':\n        while True:\n            pass\n" if hang_b else ""
    (root / "desks/mt5/mt5desk/fam_helper.py").write_text(
        f"def helper(df, who):\n{hang}    return int(len(df))\n", "utf-8"
    )
    (root / FAM).write_text(
        "import types\n\n\n"
        "def family_a(df):\n"
        "    from mt5desk.fam_helper import helper\n"
        "    return [helper(df, 'a')]\n\n\n"
        "def family_b(df):\n"
        "    from mt5desk.fam_helper import helper\n"
        "    return [helper(df, 'b')]\n\n\n"
        "ALL = {'a': family_a, 'b': family_b}\n",
        "utf-8",
    )
    return root


def test_mf2_a_shared_helper_that_hangs_one_family_is_never_measured_through_another(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    helper = "desks/mt5/mt5desk/fam_helper.py"
    base = _helper_tree(tmp_path / "base", hang_b=False)
    head = _helper_tree(tmp_path / "head", hang_b=True)
    b, h = _child_leg(base, timeout=0.5), _child_leg(head, timeout=0.5)
    assert "n" in b["out"]["b"] and "timeout" in h["out"]["b"]
    assert b["out"]["a"] == h["out"]["a"]  # family a ran the helper cleanly on both trees
    problems, rb, rh, excluded = rs.families_diff(b, h, "s", str(base), str(head))
    assert problems == []
    assert helper in excluded and FAM in excluded
    # the helper's changed unit DID run cleanly on both (via a): only MF2 keeps it unmeasured
    assert rs.families_measured(base, head, helper, rb, rh)
    step = {"hour": 7.0, "doc": {}, "intents": [{"a": 1}], "error": None, "ftmo": {}}
    legs = {"base": b, "head": h}
    monkeypatch.setattr(
        rs,
        "run_tree",
        lambda tree, sc: {"steps": [step], "imported": [], "families": legs[tree.name]},
    )
    monkeypatch.delenv(rs.DECLARED_ENV, raising=False)
    rep = rs.compare(base, head, [helper], [{"id": "s", "hours": [7.0], "families": True}])
    assert (
        f"UNMEASURED money-path change (the replay never imported it): {helper}"
        in (rep["problems"])
    )
    assert rep["verdict"] == "FAIL"
    # the other direction (base hangs, head runs) excludes the same reach
    _p, _rb, _rh, excluded = rs.families_diff(h, b, "s", str(head), str(base))
    assert helper in excluded


class _Colour(enum.Enum):
    RED = "red"


def test_mf3_plain_has_an_exact_form_or_raises() -> None:
    assert rc._plain(dt.datetime(2026, 11, 18, 7, 30)) == "2026-11-18T07:30:00"
    assert rc._plain(dt.date(2026, 11, 18)) == "2026-11-18"
    assert rc._plain(np.array([[1, 2], [3, 4]])) == [[1, 2], [3, 4]]
    assert rc._plain(_Colour.RED) == "red"
    assert rc._plain(decimal.Decimal("1.10")) == "1.10"
    assert rc._plain({3, 1, 2}) == [1, 2, 3]
    assert rc._plain(frozenset({"b", "a"})) == ["a", "b"]
    # two different values never share a form
    assert rc._plain(dt.date(2026, 11, 18)) != rc._plain(dt.date(2026, 11, 19))
    assert rc._plain(decimal.Decimal("1.1")) != rc._plain(decimal.Decimal("1.2"))

    class Opaque:
        pass

    with pytest.raises(rc._Unplain):
        rc._plain(Opaque())
    with pytest.raises(rc._Unplain):
        rc._plain([1, {"x": object()}])


def test_mf3_a_family_returning_an_opaque_value_reads_error(tmp_path: Path) -> None:
    tree = _tree(tmp_path / "t", "    return [object()]")
    leg = _child_leg(tree)
    assert leg["out"]["steady"] == {"error": "_Unplain"}
    assert not any(q.startswith("family_steady@") for q in leg["ran"].get(str(tree / FAM), []))


def test_sf1_an_alarm_landing_at_the_disarm_reads_timeout_and_the_leg_finishes(
    tmp_path: Path,
) -> None:
    # the alarm is simulated landing AFTER the family's body, inside the first disarm: the
    # per-family guard must catch it, record a timeout and carry on to the next family
    pre = (
        "import signal\n"
        "_real = signal.setitimer\n"
        "_fired = []\n"
        "def _late(which, secs, *a):\n"
        "    if secs == 0 and not _fired:\n"
        "        _fired.append(1)\n"
        "        _real(which, 0)\n"
        "        raise rc._FamilyTimeout\n"
        "    return _real(which, secs, *a)\n"
        "signal.setitimer = _late\n"
    )
    leg = _child_leg(_tree(tmp_path / "t", STEADY), pre=pre)
    assert leg["out"]["boom"] == {"timeout": 5.0}  # the first family's disarm took the alarm
    assert leg["out"]["steady"]["n"] == 1  # and the leg went on
    assert leg["clusters"]["steady"] == "trend"


def test_sf2_a_bandit_that_hangs_reads_error_timeout(tmp_path: Path) -> None:
    tree = _tree(tmp_path / "t", STEADY)
    (tree / "libs/research/bandit.py").write_text(
        "def _cluster_of(row):\n"
        "    if row.get('family') == 'steady':\n"
        "        while True:\n"
        "            pass\n"
        "    return None\n",
        "utf-8",
    )
    leg = _child_leg(tree, timeout=0.5)
    assert leg["clusters"]["steady"] == "error:timeout"
    assert leg["out"]["steady"]["n"] == 1
