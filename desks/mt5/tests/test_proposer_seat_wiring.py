"""THE PROPOSER SEAT IS WIRED, AND EVERY FACTORY STILL RUNS WITHOUT IT.

Two properties, and the second is the one that costs something to get wrong. A seat that is
wired but not clocked is a defect the desk has a law about (III.16, UNWIRED OR IDLE IS A DEFECT);
a seat whose absence BREAKS a factory is worse -- it would take five working generators down on
every box with no credential, which is every build box, every CI runner and every fresh clone,
because `data/secrets/**` never leaves the trading box.

So the wiring is asserted against the registries that own it (the hourly cycle's leg table, the
layer registry, the law gate's fence battery) and the optional path is asserted against the call
sites themselves: each one is inside a guard, and with the seat switched off each returns the
neutral value its factory then uses -- an unchanged option list, no skeleton, no name.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import proposer_seat as ps  # noqa: E402

HOURLY = _DESK / "research" / "hourly_cycle.py"
LAYERS = _ROOT / "libs" / "research" / "layers.py"
LAW_GATE = _ROOT / "scripts" / "run_law_gate.py"

#: factory module -> the call it must make, and the name it must import behind a guard.
CALL_SITES: dict[str, str] = {
    "research/expression_factory.py": "proposer_seat",
    "research/math_lab.py": "names_for",
    "research/physics_lab.py": "names_for",
    "research/factor_model_coevolution.py": "order_hint",
    "research/model_search.py": "order_hint",
}


def _src(rel: str) -> str:
    return (_DESK / rel).read_text("utf-8")


# ------------------------------------------------------------------------------- the clock
def test_the_leg_exists_with_once_and_a_budget() -> None:
    src = HOURLY.read_text("utf-8")
    assert re.search(
        r'_costed\(\s*"proposer_seat",\s*lambda: _producer\(\s*\n?\s*"proposer_seat",\s*'
        r'"libs/research/proposer_seat\.py",\s*"--once",\s*"--budget-s",\s*"300"\)\)', src), \
        "the proposer_seat leg is not registered in the hourly cycle with --once/--budget-s"
    assert '"proposer_seat": prs' in src, "the leg's result never reaches the cycle's results"


def test_the_kimi_hunter_finally_has_a_clock_on_this_box() -> None:
    """Its only clock was a VPS timer, which is why the box's kimi seat was 240h stale."""
    src = HOURLY.read_text("utf-8")
    assert '_producer("kimi_hunt", "scripts/kimi_hunter.py")' in src
    assert '"kimi_hunt": kh' in src
    assert (_ROOT / "scripts" / "kimi_hunter.py").exists()


def test_both_new_legs_are_in_the_intel_department() -> None:
    """Read from the SOURCE, not by import: importing the cycle pulls the whole research tree."""
    src = HOURLY.read_text("utf-8")
    table = src[src.index("LEG_DEPARTMENT: dict[str, str] = {"):]
    intel = re.search(r"dict\.fromkeys\(\((.*?)\),\s*\n?\s*\"intel\"\)", table, re.S)
    assert intel is not None, "the intel department tuple is not where this test looks"
    names = set(re.findall(r'"([^"]+)"', intel.group(1)))
    assert {"proposer_seat", "kimi_hunt"} <= names


def test_both_new_legs_declare_a_layer() -> None:
    from libs.research import layers
    assert layers.LEG_LAYER["proposer_seat"] == "information"
    assert layers.LEG_LAYER["kimi_hunt"] == "information"


def test_the_seat_health_fence_is_registered_in_the_law_gate() -> None:
    assert '("check_seat_health.py", ())' in LAW_GATE.read_text("utf-8")
    assert (_ROOT / "scripts" / "check_seat_health.py").exists()


def test_the_artifact_path_is_where_the_leg_says_it_is() -> None:
    assert ps.REPORT == _DESK / "reports" / "PROPOSER_SEAT.json"


def test_the_seat_accepts_the_legs_own_arguments() -> None:
    """A leg that passes flags the organ rejects is a leg that fails every hour in silence."""
    with pytest.raises(SystemExit) as exc:
        ps.main(["--once", "--budget-s", "300", "--help"])
    assert exc.value.code == 0


# --------------------------------------------------------------- the factories, unchanged
@pytest.mark.parametrize("rel,needle", sorted(CALL_SITES.items()))
def test_each_factory_calls_the_seat(rel: str, needle: str) -> None:
    src = _src(rel)
    assert "from libs.research import proposer_seat" in src, f"{rel} never reaches the seat"
    assert needle in src, f"{rel} does not make the {needle} call"


@pytest.mark.parametrize("rel", sorted(CALL_SITES))
def test_every_seat_call_site_is_inside_a_guard(rel: str) -> None:
    """An unguarded import would crash the factory on any box without the module or a panel."""
    tree = ast.parse(_src(rel))
    guarded = 0
    unguarded = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "libs.research" or not any(
                a.name == "proposer_seat" for a in node.names):
            continue
        inside = any(isinstance(p, ast.Try) and _contains(p.body, node)
                     for p in ast.walk(tree))
        guarded += int(inside)
        unguarded += int(not inside)
    assert guarded >= 1, f"{rel} has no guarded seat import"
    assert unguarded == 0, f"{rel} imports the seat outside a try/except"


def _contains(body: list[ast.stmt], target: ast.AST) -> bool:
    return any(node is target for stmt in body for node in ast.walk(stmt))


def test_with_the_seat_off_every_call_returns_its_neutral_value(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact values the five factories then use: unchanged options, no skeleton, no name."""
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")
    options = ["linear", "boosting", "neural"]
    assert ps.order_hint("model_search", options, question="q")[0] == options
    assert ps.order_hint("factor_model_coevolution", options, question="q")[0] == options
    assert ps.names_for("math_lab", [{"key": "k"}]) == {}
    assert ps.names_for("physics_lab", [{"key": "k"}]) == {}
    assert ps.take("expression_factory") == []


def test_the_expression_factorys_drain_falls_through_to_the_random_draw(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """`invent()` must reach `ag.random_expr` whenever the seat supplies nothing."""
    src = _src("research/expression_factory.py")
    start = src.index("    def invent(self)")
    body = src[start:src.index("    def _seat_skeleton", start)]
    assert "self._seat_skeleton(terms)" in body
    assert "ag.random_expr(" in body, "the random invention path was removed"
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")
    assert ps.take("expression_factory", limit=1) == []


def test_a_seeded_cell_is_marked_so_its_conversion_can_be_measured() -> None:
    src = _src("research/expression_factory.py")
    assert '"proposer_seat", self.lake.worlds[sym].asset_class' in src, \
        "a seat-seeded invention must be distinguishable from a random one"
    assert '"seat_seeded_inventions": self.seat_cells' in src


def test_the_labs_attach_a_candidate_name_and_never_an_interpretation() -> None:
    for rel in ("research/math_lab.py", "research/physics_lab.py"):
        src = _src(rel)
        start = src.index("from libs.research import proposer_seat as _ps")
        block = src[start - 800:start + 1200]
        assert "notes.append" in block, f"{rel} must attach the proposal to notes"
        assert "interpretation.status =" not in block, f"{rel} may not set a status"
        assert "CANDIDATE mechanism" in block


def test_no_factory_lets_the_seat_add_an_option() -> None:
    """order_hint is a reorder. The property is in the library, asserted here for the callers."""
    assert "never adds" in (ps.order_hint.__doc__ or "").lower()
    for rel in ("research/model_search.py", "research/factor_model_coevolution.py"):
        src = _src(rel)
        assert "order_hint(" in src
        assert "+ seat" not in src and "seat_extra" not in src
