"""Replay-shadow's research reach (ops/release/research_reach.py): the Auditor's six conditions.

1 non-vacuity (a slice that never reaches the change, an import-only line), 2 identical money,
3 superset (a key override, an existing value changed, a mutation), 4 lane sets, 5 scope,
6 the report names every file and how.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REL = ROOT / "ops" / "release"


def _load(name: str) -> Any:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REL / f"{name}.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rr = _load("research_reach")
rs = _load("replay_shadow")

BASE, HEAD = Path("/base"), Path("/head")
REG = "libs/research/alpha_clusters.py"
FN = "libs/research/claim_selection.py"

REG_SRC = '''"""doc"""
FAMILY_CLUSTER = {
    "a": "x",
    "b": "y",
    **dict.fromkeys(("c", "d"), "z"),
}
NAMES = frozenset({"a", "b"})
ORDER = ("a", "b")


def cluster(f):
    return FAMILY_CLUSTER.get(f)
'''

FN_SRC = """def pick(xs):
    out = []
    for x in xs:
        out.append(x)
    return out


TOP = 3
"""


def _reader(files: dict[Path, dict[str, str]]) -> Any:
    return lambda tree, path: files.get(tree, {}).get(path)


def _no_run(tree: Path, targets: list[str]) -> dict[str, Any]:
    raise AssertionError("an out-of-scope file must never reach the slice")


def _same(tree: Path, targets: list[str]) -> dict[str, Any]:
    """The slice deciding identically on both trees, tracing nothing."""
    assert targets == [], "a superset-proven file is never traced"
    return {"error": None, "doc": {"book": {"gold_asia": 0.01}}, "hits": {}}


def _reach(base: dict[str, str], head: dict[str, str], changed: list[str], **kw: Any) -> Any:
    read = _reader({BASE: base, HEAD: head})
    return rr.reach(BASE, HEAD, changed, changed, read, set(head), rs.ENTRY_POINTS,
                    canon=rs.canon, **kw)  # fmt: skip


# ------------------------------------------------------------------------ condition 3: superset
def test_a_new_dict_key_is_a_superset_and_excuses_only_that_knob() -> None:
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n')
    rep = _reach({REG: REG_SRC}, {REG: head}, [REG], run=_same)
    assert rep["covered"][REG] == {
        "how": "superset",
        "added": {"FAMILY_CLUSTER": ["'e'"]},
        "money_identical": True,
    }
    assert rep["excused_knobs"] == {REG: ["FAMILY_CLUSTER"]}
    assert rep["ran"], "a superset proof never stands alone: the slice runs (audit MF2)"


def test_a_pure_addition_that_flips_money_on_the_slice_is_unmeasured() -> None:
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n')

    def run(tree: Path, targets: list[str]) -> dict[str, Any]:
        book = {"gold_asia": 0.01} if tree == BASE else {"gold_asia": 0.01, "e_sleeve": 0.005}
        return {"error": None, "doc": {"book": book}, "hits": {}}

    rep = _reach({REG: REG_SRC}, {REG: head}, [REG], run=run)
    assert REG not in rep["covered"]
    assert "money outputs differ" in rep["unmeasured"][REG]
    assert rep["excused_knobs"] == {}
    assert any("decides differently on the slice on book" in p for p in rep["problems"])
    crash = _reach({REG: REG_SRC}, {REG: head}, [REG], run=lambda t, x: {"crash": "rc 1"})
    assert REG not in crash["covered"] and crash["excused_knobs"] == {}


def test_a_fromkeys_member_and_a_frozenset_member_and_an_appended_tuple_member() -> None:
    head = (
        REG_SRC.replace('("c", "d")', '("c", "d", "f")')
        .replace('{"a", "b"}', '{"a", "g", "b"}')
        .replace('("a", "b")\n', '("a", "b", "h")\n')
    )
    grown = rr.superset(REG, REG_SRC, head)
    assert grown == {"FAMILY_CLUSTER": ["'f'"], "NAMES": ["'g'"], "ORDER": ["'h'"]}


@pytest.mark.parametrize(
    ("change", "why"),
    [
        (('"b": "y",\n', '"b": "y",\n    "a": "w",\n'), "given twice"),  # a key override
        (('"b": "y",\n', '"b": "y",\n    "c": "w",\n'), "given twice"),  # overrides a fromkeys key
        (('"b": "y"', '"b": "Y"'), "value of existing key"),
        (('"z"),', '"Z"),'), "shared value"),
        (('("a", "b")\n', '("h", "a", "b")\n'), "only appending"),
        (('"b": "y",\n', '"b": "y",\n    "e": some_call(),\n'), "plain literal"),
        (('    "b": "y",\n', ""), "removed or reordered"),
        (("return FAMILY_CLUSTER.get(f)", "return FAMILY_CLUSTER.get(f, 'x')"), "not a registry"),
    ],
)
def test_anything_but_a_pure_addition_is_refused(change: tuple[str, str], why: str) -> None:
    head = REG_SRC.replace(*change)
    assert head != REG_SRC
    with pytest.raises(rr.NotSuperset, match=why):
        rr.superset(REG, REG_SRC, head)


def test_an_update_or_rebinding_anywhere_in_the_closure_refuses_the_superset() -> None:
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n')
    other = "desks/mt5/research/user.py"
    for mut in (
        "from libs.research.alpha_clusters import FAMILY_CLUSTER\nFAMILY_CLUSTER.update(e=1)\n",
        "import libs.research.alpha_clusters as ac\nac.FAMILY_CLUSTER['e'] = 'q'\n",
        "import libs.research.alpha_clusters as ac\nac.FAMILY_CLUSTER |= {'e': 'q'}\n",
    ):
        rep = _reach({REG: REG_SRC, other: mut}, {REG: head, other: mut}, [REG],
                     run=lambda t, x: {"crash": "no slice here"})  # fmt: skip
        assert REG not in rep["covered"], mut
        assert "changes FAMILY_CLUSTER" in rep["unmeasured"][REG]
    rebound = head + "FAMILY_CLUSTER = {**FAMILY_CLUSTER}\n"
    with pytest.raises(rr.NotSuperset):
        rr.superset(REG, REG_SRC + "FAMILY_CLUSTER = {**FAMILY_CLUSTER}\n", rebound + "X = 1\n")
    assert rr.mutations(head + "FAMILY_CLUSTER = {}\n", "FAMILY_CLUSTER", defining=True)


def test_a_changed_reader_of_the_registry_refuses_the_superset() -> None:
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n')
    reader = "desks/mt5/research/route.py"
    rep = _reach(
        {REG: REG_SRC, reader: "def f(k):\n    return k\n"},
        {REG: head, reader: "from libs.research.alpha_clusters import FAMILY_CLUSTER\n"
                            "def f(k):\n    return FAMILY_CLUSTER[k]\n"},
        [REG, reader],
        run=lambda t, x: {"crash": "no slice here"},
    )  # fmt: skip
    assert REG not in rep["covered"]
    assert "reads FAMILY_CLUSTER and changes in this PR" in rep["unmeasured"][REG]


def test_a_test_file_naming_the_registry_does_not_block_it() -> None:
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n')
    t = "desks/mt5/tests/test_clusters.py"
    rep = _reach({REG: REG_SRC}, {REG: head, t: "FAMILY_CLUSTER\n"}, [REG, t], run=_same)
    assert rep["covered"][REG]["how"] == "superset"


def test_a_deny_or_exclude_registry_is_never_a_superset() -> None:
    for name in ("NOT_SOURCED_HERE", "EXCLUDED_FAMILIES", "SKIPLIST", "RETIRED", "KILLED",
                 "BLOCKLIST", "DISABLED", "VETOES", "STOPLIST", "IGNORE"):  # fmt: skip
        src = f'{name} = {{"a": 1}}\n'
        with pytest.raises(rr.NotSuperset, match="deny or exclude"):
            rr.superset(REG, src, src.replace('"a": 1', '"a": 1, "b": 2'))


# --------------------------------------------------------------------- condition 4: lane sets
def test_lane_policy_sets_never_qualify_as_a_superset() -> None:
    up = "desks/mt5/research/universe_policy.py"
    src = 'CROSS_SECTIONAL_FAMILIES = frozenset({"a"})\n'
    with pytest.raises(rr.NotSuperset, match="lane policy"):
        rr.superset(up, src, src.replace('"a"', '"a", "b"'))
    for name in ("CROSS_SECTIONAL_FAMILIES", "SYMBOL_ROUTES", "LANE_OF", "CLASS_MEMBERS",
                 "LIVE_SLEEVES", "ALLOWED_PAIRS"):  # fmt: skip
        src = f'{name} = {{"a": 1}}\n'
        with pytest.raises(rr.NotSuperset, match="lane table"):
            rr.superset(REG, src, src.replace('"a": 1', '"a": 1, "b": 2'))
    for name in ("SYMBOLMAP", "PEERCLASSES", "MARKETMAP", "TICKERSET", "CCYGROUPS", "FXSET"):
        src = f'{name} = {{"a": 1}}\n'
        with pytest.raises(rr.NotSuperset, match="lane table"):
            rr.superset(REG, src, src.replace('"a": 1', '"a": 1, "b": 2'))
    src = 'FAMILY_GROUPS = {"a": 1}\n'
    for member in ("EURUSD", "XAUUSD", "US500", "GBPJPY.m"):
        with pytest.raises(rr.NotSuperset, match="symbol or asset class"):
            rr.superset(REG, src, src.replace('"a": 1', f'"a": 1, "{member}": 2'))


def test_universe_symbols_and_asset_classes_are_lane_members() -> None:
    uni = '{"AAPL": {"symbol": "AAPL", "asset_class": "Equities"}, "NVDA": {"symbol": "NVDA"},'
    uni += ' "XAUUSD": {"asset_class": "Commodities"}}'
    lanes = rr.lane_values([uni, None, "not json"])
    src = 'FAMILY_GROUPS = frozenset({"a"})\n'
    for member in ("AAPL", "nvda", "Equities", "commodities", "equity", "fx_usd", "metals",
                   "crypto", "aapl_momentum"):  # fmt: skip
        with pytest.raises(rr.NotSuperset, match="symbol or asset class"):
            rr.superset(REG, src, src.replace('"a"', f'"a", "{member}"'), lanes)
    assert rr.superset(REG, src, src.replace('"a"', '"a", "carry_rank"'), lanes)
    # the reach reads universe.json from both trees
    head = REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "AMZN": "w",\n')
    u2 = '{"AMZN": {"asset_class": "Equities"}}'
    rep = _reach({REG: REG_SRC}, {REG: head, rr.UNIVERSE_JSON: u2}, [REG], run=_run_with({REG: []}))
    assert REG not in rep["covered"] and "condition 4" in rep["unmeasured"][REG]


# ------------------------------------------------------------------------ condition 5: scope
@pytest.mark.parametrize(
    "path",
    [
        "desks/mt5/mt5desk/families_cross_sectional.py",
        "desks/mt5/prop/e8_gold.py",
        "libs/portfolio/robust_elog.py",
        "desks/mt5/research/pf_allocator.py",
        "desks/mt5/research/run_gateway_loop.py",
        "desks/mt5/research/heat_policy.py",
        "desks/mt5/research/chart_allocator.py",
        "libs/research/decision_core.py",
        "libs/research/sizing_table.py",
    ],
)
def test_out_of_scope_paths_never_qualify(path: str) -> None:
    src = 'FAMILY_CLUSTER = {"a": 1}\n'
    rep = _reach({path: src}, {path: src.replace('"a": 1', '"a": 1, "b": 2')}, [path],
                 run=_no_run)  # fmt: skip
    assert path not in rep["covered"]
    assert "condition 5" in rep["unmeasured"][path]


# -------------------------------------------------------------- condition 1 and 2: line trace
def _fn_change() -> tuple[str, str]:
    return FN_SRC, FN_SRC.replace("out.append(x)", "out.append(x * 1)")


def _run_with(hits: dict[str, list[int]], book: dict[str, float] | None = None) -> Any:
    def run(tree: Path, targets: list[str]) -> dict[str, Any]:
        b = {"gold_asia": 0.01} if tree == BASE or book is None else book
        return {"error": None, "doc": {"book": b, "heat": {"total": 0.05}},
                "hits": hits if tree == HEAD else {}}  # fmt: skip

    return run


def test_a_vacuous_slice_leaves_the_file_unmeasured() -> None:
    b, h = _fn_change()
    # the slice ran the function's first line but never the loop body that changed
    rep = _reach({FN: b}, {FN: h}, [FN], run=_run_with({FN: [2, 6]}))
    assert FN not in rep["covered"]
    assert "line 4 (changed): never executed on the slice" in rep["unmeasured"][FN]
    rep = _reach({FN: b}, {FN: h}, [FN], run=_run_with({}))
    assert FN not in rep["covered"]


def test_an_executed_change_with_identical_money_is_covered_by_the_trace() -> None:
    b, h = _fn_change()
    rep = _reach({FN: b}, {FN: h}, [FN], run=_run_with({FN: [2, 3, 4, 5]}))
    assert rep["covered"][FN]["how"] == "line_trace"
    assert rep["covered"][FN]["changed_lines"] == [4]
    assert rep["excused_knobs"] == {}  # a trace excuses no knob
    assert rep["problems"] == []


def test_different_money_on_the_slice_fails_and_covers_nothing() -> None:
    b, h = _fn_change()
    rep = _reach({FN: b}, {FN: h}, [FN], run=_run_with({FN: [2, 3, 4, 5]}, {"gold_asia": 0.02}))
    assert FN not in rep["covered"]
    assert any("decides differently on the slice on book" in p for p in rep["problems"])


def test_a_module_level_change_never_counts_as_executed() -> None:
    b = FN_SRC
    h = FN_SRC.replace("TOP = 3", "TOP = 3\nDEPTH = sorted([3, 1])")
    rep = _reach({FN: b}, {FN: h}, [FN], run=_run_with({FN: [1, 2, 3, 4, 5, 9]}))
    assert FN not in rep["covered"]
    assert "runs only at import" in rep["unmeasured"][FN]


def test_a_docstring_change_and_a_trailing_deletion_stay_unmeasured() -> None:
    b = 'def f():\n    """old"""\n    return 1\n'
    h = 'def f():\n    """new"""\n    return 1\n'
    assert "docstring" in "; ".join(rr.unexecuted(h, *rr.changed_lines(b, h), {1, 3}))
    b2, h2 = "def f():\n    a = 1\n    return a\nX = 1\n", "def f():\n    a = 1\n    return a\n"
    assert rr.unexecuted(h2, *rr.changed_lines(b2, h2), {2, 3})


def test_a_deletion_inside_a_function_counts_through_the_line_in_its_place() -> None:
    b = "def f(x):\n    x += 1\n    x += 2\n    return x\n"
    h = "def f(x):\n    x += 1\n    return x\n"
    added, stand_in = rr.changed_lines(b, h)
    assert added == set() and stand_in == {3}
    assert rr.unexecuted(h, added, stand_in, {2, 3}) == []
    assert rr.unexecuted(h, added, stand_in, {2})


def test_a_base_that_cannot_run_the_slice_measures_nothing() -> None:
    b, h = _fn_change()
    rep = _reach({FN: b}, {FN: h}, [FN], run=lambda t, x: {"crash": "rc 1"})
    assert FN not in rep["covered"] and "cannot run the slice" in rep["unmeasured"][FN]


# ----------------------------------------------------------- knobs: only the superset excuses
def test_knob_changes_excuse_only_the_names_the_superset_proved(tmp_path: Path) -> None:
    f = REG
    b, h = tmp_path / "b", tmp_path / "h"
    for t, src in (
        (b, REG_SRC),
        (
            h,
            REG_SRC.replace('"b": "y",\n', '"b": "y",\n    "e": "w",\n').replace(
                "ORDER = (", "ORDER = ('z', "
            ),
        ),
    ):
        (t / f).parent.mkdir(parents=True)
        (t / f).write_text(src)
    got = rs.knob_changes(b, h, [f], {f}, None, {f: ["FAMILY_CLUSTER"]})
    assert any("knob ORDER changed" in p for p in got)
    assert not any("FAMILY_CLUSTER" in p for p in got)
    assert any("FAMILY_CLUSTER" in p for p in rs.knob_changes(b, h, [f], {f}, None))


# -------------------------------------------------------------- the pinned slice, really run
def test_the_slice_is_pinned_by_hash() -> None:
    raw = (rr.SLICE / "SLICE.sha256").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == rr.SLICE_SHA256
    child = _load("research_child")
    assert child.slice_digest(rr.SLICE)[0] == rr.SLICE_SHA256
    assert "ops/release/research_slice/" in (REL / "protected_paths.txt").read_text() or any(
        ln.strip().rstrip("*") in ("ops/release/", "ops/release")
        for ln in (REL / "protected_paths.txt").read_text().splitlines()
    )


def test_the_allocator_on_the_slice_is_deterministic_and_traces_function_lines() -> None:
    target = "libs/research/experiment_ledger.py"
    a, b = rr.run_slice(ROOT, [target]), rr.run_slice(ROOT, [target])
    assert "crash" not in a and a["error"] is None, a.get("crash")
    assert rr.money(a["doc"], rs.canon) == rr.money(b["doc"], rs.canon)
    assert a["doc"]["book"], "the slice must solve a funded book"
    hits = set(a["hits"].get(target, []))
    assert hits
    import ast

    tree = ast.parse((ROOT / target).read_text("utf-8"))
    fn_lines = {
        x
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        for x in range(n.lineno, (n.end_lineno or n.lineno) + 1)
    }
    assert hits <= fn_lines, "a module-body line was recorded as executed"
