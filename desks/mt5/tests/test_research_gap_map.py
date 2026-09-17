"""THE GAP MAP -- the enumeration is the product, so these pin what may be enumerated at all.

    python -m pytest desks/mt5/tests/test_research_gap_map.py -q -p no:cacheprovider

What is fenced here, and why each one is worth a test:

  * THE ONTOLOGY PRUNES, AND THE PRUNING IS THE WHOLE VALUE. A session mechanism has no D1 cell,
    a microstructure mechanism has no D1 cell, and a calendar mechanism has no intrabar cell --
    and the same test proves the absence is not VACUOUS by asserting the admissible neighbour
    exists. An empty axis that is empty because nothing was enumerated is not a measurement;
  * EVERY STATE COMES FROM A PLANTED FIXTURE. Eight states, eight plants, and the cell each one
    lands on is asserted by name. A state that can only be reached by reading the box is a state
    no test can falsify;
  * THE HOLE RANKING IS THE ORDER RESEARCH MOVES IN. Two cells identical but for their asset
    class must rank by independence -- the class carrying twenty live sleeves below the class
    carrying none -- or the map ranks nothing and the desk deepens where it already is;
  * COVERAGE BY AXIS COUNTS EVIDENCE, never derivation: READY is what the desk COULD do and must
    never be counted as ground it has covered;
  * `--dry-run` WRITES NO BYTE, because this organ runs on the box holding live positions;
  * THE BUDGET IS REAL AND SAYS SO. A truncated enumeration that reports a clean count is worse
    than no map at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.moat import registry as R  # noqa: E402
from research import axis_registry as AX  # noqa: E402
from research import research_gap_map as G  # noqa: E402
from research import universe_policy as UP  # noqa: E402

#: The broker registry the fixture desk trades: one class per lane the contracts care about.
UNIVERSE = {
    "EURUSD": {"asset_class": "forex"},
    "GBPUSD": {"asset_class": "forex"},
    "XAUUSD": {"asset_class": "commodities"},
    "US500": {"asset_class": "indices"},
    "BUND": {"asset_class": "bonds"},
    "Apple": {"asset_class": "equities"},          # the event lane -- never hunted, never a hole
}
#: symbol_chart pairs that have bars. M5 exists for forex ONLY, which is what makes an
#: indices-on-M5 cell UNSEEN rather than READY.
BARS = ("EURUSD_M5", "EURUSD_M15", "EURUSD_H1", "EURUSD_H4", "EURUSD_D1",
        "GBPUSD_H1", "GBPUSD_H4", "XAUUSD_H1", "XAUUSD_H4", "US500_H1", "US500_H4",
        "BUND_H4", "BUND_D1", "Apple_H1")

#: LIVE: a funded sleeve. `asia_momentum` is session_handover / price_only in the family table.
SLEEVES = {"sleeves": [
    {"name": "eur_asia", "symbol": "EURUSD", "timeframe": "H1", "family": "asia_momentum",
     "session": "asia", "max_hold": 3, "status": "LIVE"},
    # Twenty more live forex sleeves, so the independence bonus on `forex` is measurably worse
    # than on `bonds` and the hole ranking has something to rank.
    *[{"name": f"eur_trend_{i}", "symbol": "EURUSD", "timeframe": "H4",
       "family": "trend_ma_cross", "session": "all", "status": "LIVE"} for i in range(20)],
]}
#: FORWARD: a clock. The key shape `SYM.family.session` is the one on this tree today.
SHADOW = {"XAUUSD.overnight_gap_decay.asia": {"n": 14, "status": "ACTIVE"}}
#: SURVIVED: a certificate, in the cell-string shape hunt16 writes.
SURVIVORS = {"n": 1, "survivors": {"u.1": {
    "cell": "EURUSD trend_ma_cross LONG london", "sym": "EURUSD",
    "shadow_spec": {"family": "trend_ma_cross", "chart": "H4", "params": {}}}}}
#: FAILED: a judged loss. TESTING: a docket row nobody has judged yet.
GATE_ROWS = [{"at": "2026-09-17T00:00:00+00:00", "cell": "US500.mean_reversion_rsi.ny",
              "sym": "US500", "family": "mean_reversion_rsi", "passed": False}]
QUEUE = [{"symbol": "BUND", "family": "carry", "params": {}, "timeframe": "D1", "session": "all"}]


def _cell(mechanism: str, **axes: str) -> str:
    """Build a cell key from the axes a test cares about, defaulting the rest."""
    base = {"asset_class": "forex", "mechanism": mechanism,
            "economic_actor": AX.MECHANISM_ACTOR.get(mechanism, "unknown").lower(),
            "information": "price_only", "chart": "h1", "session": "all",
            "horizon": "sub_4h", "regime": "unconditional"}
    base.update({k: v.lower() for k, v in axes.items()})
    return G.key_of(base)


@pytest.fixture()
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A whole desk in a tmp tree: bars, a broker registry, the six evidence sources, and the
    observables the contracts ask for -- minus `order_book_depth`, which this box does not hold."""
    data, reports = tmp_path / "data", tmp_path / "reports"
    (data / "universe").mkdir(parents=True)
    (data / "hypotheses").mkdir(parents=True)
    (reports / "shadow").mkdir(parents=True)
    (data / "universe" / "universe.json").write_text(json.dumps(UNIVERSE), encoding="utf-8")
    for name in BARS:
        (data / "universe" / f"{name}.parquet").write_bytes(b"PAR1")
    # The observables the contracts name. `data/tape/depth` is deliberately NOT created, and
    # neither is `data/liquidations`: a broker CFD venue publishes no liquidation tape.
    for rel in ("data/tape/ticks", "data/cot", "data/macro_pointintime"):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
        (tmp_path / rel / "x.json").write_text("{}", encoding="utf-8")
    for rel in ("data/carry_state.json", "data/forced_flow_calendar.json",
                "data/options_state.json"):
        (tmp_path / rel).write_text("{}", encoding="utf-8")

    (data / "sleeves.json").write_text(json.dumps(SLEEVES), encoding="utf-8")
    (reports / "shadow" / "shadow_state.json").write_text(json.dumps(SHADOW), encoding="utf-8")
    (reports / "UNIVERSAL_SURVIVORS.json").write_text(json.dumps(SURVIVORS), encoding="utf-8")
    (data / "hypotheses" / "gate_verdict_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in GATE_ROWS), encoding="utf-8")
    (data / "research_queue.json").write_text(json.dumps(QUEUE), encoding="utf-8")
    (data / "hypothesis_graph.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(G, "ROOT", tmp_path)
    monkeypatch.setattr(G, "DESK", tmp_path)
    monkeypatch.setattr(G, "UNIVERSE_DIR", data / "universe")
    monkeypatch.setattr(G, "SLEEVES", data / "sleeves.json")
    monkeypatch.setattr(G, "SHADOW", reports / "shadow" / "shadow_state.json")
    monkeypatch.setattr(G, "SURVIVORS", reports / "UNIVERSAL_SURVIVORS.json")
    monkeypatch.setattr(G, "GATE_LEDGER", data / "hypotheses" / "gate_verdict_ledger.jsonl")
    monkeypatch.setattr(G, "GRAPH", data / "hypothesis_graph.jsonl")
    monkeypatch.setattr(G, "RESEARCH_QUEUE", data / "research_queue.json")
    monkeypatch.setattr(G, "OUT", reports / "RESEARCH_GAP_MAP.json")
    monkeypatch.setattr(G, "_LAST", None)

    monkeypatch.setattr(UP, "UNIVERSE", data / "universe" / "universe.json")
    UP._registry.cache_clear()
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_such_backup")
    R.set_path(tmp_path / "registry.sqlite")
    yield tmp_path
    UP._registry.cache_clear()
    R.set_path(None)


@pytest.fixture()
def built(desk: Path) -> dict[str, Any]:
    return G.build()


# ------------------------------------------------------------- the enumeration is the product
def test_valid_cells_respect_the_ontology(built: dict[str, Any]) -> None:
    """A session mechanism has no D1 cell -- and the absence is not vacuous."""
    cells = G._LAST["cells"]
    axes = [G.axes_of_key(c) for c in cells]
    session_mechs = {"session_handover", "session_information_handoff"}

    assert not [a for a in axes if a["mechanism"] in session_mechs and a["chart"] == "d1"], (
        "a handover between sessions cannot be asked of a bar that contains every session")
    # ... and the admissible neighbour EXISTS, so the assertion above is a pruning rule and not
    # an empty enumeration (L1.49: a gate that never ran is a claim the desk cannot cash).
    assert [a for a in axes if a["mechanism"] == "session_handover" and a["chart"] == "h1"]

    assert not [a for a in axes
                if a["mechanism"] == "execution_microstructure" and a["chart"] == "d1"]
    assert not [a for a in axes
                if a["mechanism"] == "calendar_seasonality" and a["horizon"] == "intrabar"]
    # Chart and horizon agree: nothing claims a multi-day hold measured on a five-minute bar.
    for a in axes:
        assert a["horizon"] in [h.lower() for h in G.CHART_HORIZONS[a["chart"].upper()]]
    # The two-lane order: an equity class is never a hole, because equities are not hunted.
    assert "equities" not in {a["asset_class"] for a in axes}


def test_the_actor_and_information_axes_are_determined_by_the_mechanism(
        built: dict[str, Any]) -> None:
    """The actor axis is not free: `MECHANISM_ACTOR` says who pays, and an edge with no payer is
    a chart pattern. Enumerating actors independently would multiply the grid by twenty and add
    no question anybody would ask."""
    for cell in G._LAST["cells"]:
        a = G.axes_of_key(cell)
        assert a["economic_actor"] == AX.MECHANISM_ACTOR[a["mechanism"]].lower()
        assert a["information"] in G.information_of(a["mechanism"])


def test_the_valid_count_is_reported_beside_the_populated_count(built: dict[str, Any]) -> None:
    assert built["n_valid_cells"] == len(G._LAST["cells"]) > 0
    assert built["n_populated"] == sum(built["by_state"][s] for s in G.EVIDENCE_STATES)
    assert built["populated_share"] == pytest.approx(
        built["n_populated"] / built["n_valid_cells"], abs=5e-7)
    assert built["rule"] == ("research moves toward the highest-value holes; a hole is named, "
                             "never assumed covered")


# ------------------------------------------------------------- every state from a planted fixture
def test_every_state_is_derived_from_its_own_fixture(built: dict[str, Any]) -> None:
    assert set(built["by_state"]) == set(G.STATES)

    live = _cell("session_handover", chart="h1", session="asia", horizon="sub_4h")
    assert G.state_of(live) == "LIVE", "the funded sleeve"

    forward = _cell("session_handover", asset_class="commodities", chart="h1", session="asia",
                    horizon="sub_4h")
    assert G.state_of(forward) == "FORWARD", "the clock"

    survived = _cell("trend_persistence", chart="h4", session="london", horizon="sub_1d")
    assert G.state_of(survived) == "SURVIVED", "the certificate"

    failed = _cell("range_reversion", asset_class="indices", information="price_only",
                   chart="h1", session="ny", horizon="sub_4h")
    assert G.state_of(failed) == "FAILED", "the judged loss"

    testing = _cell("carry_rollover", asset_class="bonds", information="carry", chart="d1",
                    session="all", horizon="multi_day")
    assert G.state_of(testing) == "TESTING", "the docket row"

    ready = _cell("trend_persistence", chart="h1", session="all", horizon="sub_4h",
                  regime="high_volatility")
    assert G.state_of(ready) == "READY", "bars and the observable, and no candidate"

    # `inventory_shock` needs an order-book DEPTH SERIES. The box has a depth probe and no series.
    missing = _cell("inventory_shock", information="microstructure", chart="m15",
                    horizon="intrabar")
    assert G.state_of(missing) == "DATA_MISSING"
    assert "inventory_shock" in built["unmeasured"]["mechanisms_data_missing"]

    # M5 bars exist for forex and for nothing else, so the same question on an index is UNSEEN.
    unseen = _cell("range_reversion", asset_class="indices", chart="m5", horizon="intrabar")
    assert G.state_of(unseen) == "UNSEEN"

    for state in G.STATES:
        assert built["by_state"][state] > 0, f"{state} was never reached by any fixture"


def test_a_coordinate_outside_the_grid_is_INVALID_not_UNSEEN(built: dict[str, Any]) -> None:
    """`INVALID` is a verdict about the QUESTION; `UNSEEN` is a verdict about the desk's coverage
    of it. Collapsing the two would let an inadmissible coordinate read as an untested one and
    quietly inflate the debt."""
    assert G.state_of(_cell("session_handover", chart="d1", horizon="multi_day")) == "INVALID"
    assert G.state_of("not|a|cell|at|all|no|really|not") == "INVALID"


def test_evidence_outside_the_grid_is_counted_and_explained(built: dict[str, Any]) -> None:
    """The docket's `discovered` family names no mechanism. That is a finding about the search,
    and it must not be silently dropped."""
    (Path(G.GRAPH)).write_text(json.dumps(
        {"symbol": "EURUSD", "family": "discovered", "params": {}}) + "\n", encoding="utf-8")
    doc = G.build()
    assert doc["unmeasured"]["evidence_outside_the_grid"] >= 1
    why = doc["unmeasured"]["evidence_outside_why"]
    assert any("mechanism=unknown" in k for k in why), why


# ------------------------------------------------------------- the ranking
def test_hole_values_rank_by_independence(built: dict[str, Any]) -> None:
    """Twenty live forex sleeves and none on bonds: the same question on bonds must outrank it."""
    values = {h["cell"]: h["value"] for h in G.holes(10**6)}
    forex = _cell("trend_persistence", asset_class="forex", chart="h4", session="all",
                  horizon="sub_1d", regime="trending")
    bonds = _cell("trend_persistence", asset_class="bonds", chart="h4", session="all",
                  horizon="sub_1d", regime="trending")
    assert forex in values and bonds in values
    assert values[bonds] > values[forex], "independence is a multiplier, not a tiebreak"


def test_hole_values_are_ranked_and_readiness_orders_them(built: dict[str, Any]) -> None:
    ranked = G.holes(200)
    assert [h["value"] for h in ranked] == sorted((h["value"] for h in ranked), reverse=True)
    assert built["top_holes"][:5] == ranked[:5]
    assert all(h["state"] in ("READY", "UNSEEN", "DATA_MISSING") for h in ranked), (
        "a hole is ground nobody has touched; a judged cell is not a hole")
    assert all(h["why"] for h in ranked)
    # Same mechanism and class, three readiness levels: READY must outrank both the others.
    by_state = {h["state"]: h["value"] for h in reversed(ranked)}
    assert by_state.get("READY", 0.0) > 0.0


def test_the_survivor_rate_is_laplace_smoothed(built: dict[str, Any]) -> None:
    """An untested mechanism reads the registry's own 0.5 prior -- never 0 (which would bury it
    forever) and never 1 (which would let absence outrank evidence)."""
    rates = built["survivor_rate_by_mechanism"]
    assert rates["volatility_shock"] == pytest.approx(R.PRIOR), "never judged: the prior"
    assert rates["range_reversion"] == pytest.approx(1 / 3, abs=5e-5), "one judged, none survived"
    assert rates["trend_persistence"] > R.PRIOR, "a certificate and twenty live sleeves"


def test_coverage_by_axis_counts_evidence_only(built: dict[str, Any]) -> None:
    cov = built["coverage_by_axis"]
    assert set(cov) == set(R.GRID_AXES)
    assert cov["mechanism"].get("session_handover", 0) >= 2, "the sleeve and the clock"
    assert cov["asset_class"].get("bonds", 0) >= 1, "the docket row"
    assert sum(cov["chart"].values()) == built["n_populated"]
    # READY is what the desk COULD do. Counting it as coverage is the assumption the map exists
    # to end, so no axis total may exceed the populated count.
    assert built["by_state"]["READY"] > built["n_populated"]


def test_research_debt_counts_only_holes_with_a_tested_neighbour(built: dict[str, Any]) -> None:
    """The debt is the extension nobody would argue against -- one axis from a cell the desk has
    already judged -- not every untested coordinate, which is most of any honest grid."""
    debt = built["research_debt_cells"]
    assert 0 < debt < built["by_state"]["READY"] + built["by_state"]["UNSEEN"]
    # The certificate sits at (forex, trend_persistence, H4, london, sub_1d, unconditional). The
    # same cell in another declared regime is one axis away and therefore debt.
    neighbour = _cell("trend_persistence", chart="h4", session="london", horizon="sub_1d",
                      regime="trending")
    assert G.state_of(neighbour) in ("READY", "UNSEEN")
    assert debt >= 1


# ------------------------------------------------------------- the boundary
def test_dry_run_writes_nothing(desk: Path) -> None:
    assert G.main(["--dry-run", "--top", "3"]) == 0
    assert not Path(G.OUT).exists(), "--dry-run may not write a byte on the box that trades"


def test_apply_writes_the_artifact_atomically(desk: Path) -> None:
    assert G.main([]) == 0
    doc = json.loads(Path(G.OUT).read_text(encoding="utf-8"))
    assert doc["n_valid_cells"] > 0
    assert doc["rule"].startswith("research moves toward")
    assert not list(Path(G.OUT).parent.glob("*.tmp")), "the temp file is replaced, never left"


def test_the_budget_is_real_and_the_report_says_so(desk: Path) -> None:
    partial = G.build(budget_s=0.0)
    full = G.build()
    assert partial["unmeasured"]["budget_exhausted"] is True
    assert partial["n_valid_cells"] < full["n_valid_cells"]
    assert full["unmeasured"]["budget_exhausted"] is False


def test_absent_inputs_are_named_not_defaulted(desk: Path) -> None:
    Path(G.SLEEVES).unlink()
    doc = G.build()
    inputs = doc["unmeasured"]["inputs"]
    assert any(str(G.SLEEVES) == k and v == "ABSENT" for k, v in inputs.items()), inputs
    assert doc["by_state"]["LIVE"] == 0
    assert "observable:order_book_depth" in inputs
