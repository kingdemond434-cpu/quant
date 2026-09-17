"""THE COVERAGE ALGEBRA -- the ladders, the sparse store, EVIG, covered() and the ratchet.

    python -m pytest tests/research/test_coverage.py -q -p no:cacheprovider

What is fenced here, and why each is worth a test:

  * THE AXES AND LADDERS ARE LAW (LAWS 5f), in that exact order, with the ten source classes.
    A reordered axis silently invalidates every stored coordinate, and a renamed state silently
    invalidates every verdict;
  * THE LADDER IS MONOTONE AND THE TWO DOWN-MOVES NEED NAMED EVIDENCE. A cell nobody judged
    cannot be failed by silence, and a live cell cannot decay because a file went missing;
  * THE STORE IS SPARSE. The full product of ten axes is astronomically large, so `holes` must
    enumerate a PROJECTION and say when it truncated;
  * EVERY EVIG FACTOR IS IN THE BREAKDOWN, and each moves the score in the direction it claims;
  * `covered()` REFUSES FIVE OBVIOUS SOURCES -- the principal's rule, as a test;
  * THE RATCHET NEVER LOWERS A FLOOR, and reports what sits below one;
  * THE THREE NAMED FRONTIER ROWS of the specification are constructible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import coverage as C  # noqa: E402


# ------------------------------------------------------------------------------- the law's shapes
def test_the_axes_and_ladders_are_exactly_the_law() -> None:
    assert C.WORLD_AXES == ("country", "sector", "information_type", "mechanism",
                            "representation", "asset", "session", "regime", "horizon",
                            "execution")
    assert C.FOREST_AXES == ("country", "language", "source_class", "sector", "mechanism",
                             "asset_transmission", "freshness", "accessibility")
    assert C.WORLD_LADDER == ("UNOBSERVED", "SOURCE_HUNT", "INGESTED", "REPRESENTED",
                              "CANDIDATES", "TESTING", "FAILED", "FORWARD", "CERTIFIED", "LIVE",
                              "DECAYED")
    assert C.FOREST_LADDER == ("UNSEEN", "SOURCE_HUNT", "DISCOVERED", "VERIFIED", "INGESTED",
                               "REPRESENTED", "CANDIDATES", "TESTED", "FORWARD", "LIVE", "FAILED")
    assert C.SOURCE_LAYERS == ("official", "institutional", "academic", "practitioner",
                               "retail_ecology", "app_ecosystem", "media", "archive",
                               "physical_economy", "source_graph")
    assert len(C.SOURCE_LAYERS) == 10


def test_failed_and_forward_share_a_rung_and_decayed_sits_above_live() -> None:
    w = C.WORLD_LADDER_SPEC
    assert w.rank("FAILED") == w.rank("FORWARD"), "two states on the same rung, as the law says"
    assert w.rank("DECAYED") > w.rank("LIVE")
    assert w.down_moves["DECAYED"] == frozenset({"FORWARD", "CERTIFIED", "LIVE"})
    assert w.down_moves["FAILED"] == frozenset({"TESTING", "FORWARD", "CERTIFIED"})
    f = C.FOREST_LADDER_SPEC
    assert f.rank("LIVE") == f.rank("FAILED"), "LIVE/FAILED is the forest's shared final rung"
    # the positive path skips the down-moves
    assert w.next_state("TESTING") == "FORWARD" and w.next_state("CANDIDATES") == "TESTING"
    assert f.next_state("TESTED") == "FORWARD"


def test_a_cell_refuses_the_wrong_number_of_coordinates_and_an_unknown_state() -> None:
    with pytest.raises(ValueError, match="10 coordinates"):
        C.Cell(C.WORLD, ("kr", "semiconductors"), "UNOBSERVED")
    with pytest.raises(ValueError, match="not a state"):
        C.Cell(C.FOREST, tuple(["x"] * 8), "CERTIFIED")       # a world state, not a forest one
    with pytest.raises(ValueError, match="unknown tensor"):
        C.axes_of("galaxy")


# -------------------------------------------------------------------------------- monotone ladder
def _cell(state: str = "UNOBSERVED") -> C.Cell:
    return C.Cell(C.WORLD, ("kr", "semiconductors", "supply_chain", "cross_market_lead",
                            "surprise", "USDJPY", "asia", "unconditional", "1d", "market"),
                  state)


def test_advance_goes_up_and_never_silently_down() -> None:
    cell = _cell()
    cell = C.advance(cell, "INGESTED", {"source": "bars", "why": "on the box"})
    cell = C.advance(cell, "CANDIDATES", {"source": "registry"})
    assert cell.state == "CANDIDATES"
    back = C.advance(cell, "INGESTED", {"source": "bars again"})
    assert back.state == "CANDIDATES", "a lower rung records evidence and never demotes"
    assert "INGESTED" in back.evidence and len(back.evidence["INGESTED"]) == 2


def test_the_two_down_moves_need_named_evidence_and_a_lawful_origin() -> None:
    testing = C.advance(_cell(), "TESTING", {"source": "docket", "why": "queued"})
    with pytest.raises(ValueError, match="NAMED evidence"):
        C.advance(testing, "FAILED", {"source": "ledger"})          # a why is missing
    with pytest.raises(ValueError, match="NAMED evidence"):
        C.advance(testing, "FAILED", None)
    failed = C.advance(testing, "FAILED", {"source": "gate_ledger", "why": "cost_killed"})
    assert failed.state == "FAILED" and failed.evidence["path"][-1] == "FAILED"
    # DECAYED is not reachable from a cell that was never forward/certified/live
    with pytest.raises(ValueError, match="reachable only from"):
        C.advance(failed, "DECAYED", {"source": "retirement", "why": "decayed"})
    live = C.advance(C.advance(testing, "FORWARD", {"source": "clock"}), "LIVE",
                     {"source": "sleeves"})
    gone = C.advance(live, "DECAYED", {"source": "sleeves.json", "why": "sleeve RETIRED"})
    assert gone.state == "DECAYED"


def test_failed_may_still_become_forward_because_that_is_progress() -> None:
    """FAILED and FORWARD share a rung: a cell that later earns a clock moves, and the reverse
    is a down-move that still needs named evidence."""
    testing = C.advance(_cell(), "TESTING", {"source": "docket", "why": "queued"})
    failed = C.advance(testing, "FAILED", {"source": "gate", "why": "cost"})
    forward = C.advance(failed, "FORWARD", {"source": "clock"})
    assert forward.state == "FORWARD"
    with pytest.raises(ValueError, match="NAMED evidence"):
        C.advance(forward, "FAILED", {"source": "gate"})


# --------------------------------------------------------------------------------- sparse storage
def _world() -> C.Tensor:
    return C.Tensor(C.WORLD, vocabulary={
        "country": ["id", "kr", "ru"], "sector": ["metals_mining", "semiconductors"],
        "asset": ["AUDUSD", "USDJPY", "EURUSD"], "session": ["asia", "london"],
        "information_type": ["customs", "supply_chain", "market_data"],
        "mechanism": ["cross_market_lead", "carry_rollover"],
        "representation": ["level", "surprise"], "regime": ["unconditional", "risk_off"],
        "horizon": ["1d"], "execution": ["market"]})


def test_only_touched_cells_are_stored_and_absence_reads_as_the_floor() -> None:
    t = _world()
    assert len(t) == 0, "the full product is astronomical; an empty tensor stores nothing"
    t.observe({"country": "kr", "asset": "USDJPY", "session": "asia"}, "INGESTED",
              {"source": "bars"})
    assert len(t) == 1
    assert t.get({"country": "id", "asset": "AUDUSD"}) is None
    holes = t.holes(("country", "asset"), 99)
    assert ("id", "AUDUSD") in {h.coordinates for h in holes}, "an absent cell is a hole"
    assert t.last_scan["covered"] == 1 and t.last_scan["truncated"] is False


def test_holes_respect_the_bar_the_axes_and_the_budget() -> None:
    t = _world()
    t.observe({"country": "kr", "asset": "USDJPY"}, "CANDIDATES", {"source": "registry"})
    at_floor = {h.coordinates for h in t.holes(("country", "asset"), 99)}
    assert ("kr", "USDJPY") not in at_floor
    below_live = {h.coordinates for h in t.holes(("country", "asset"), 99,
                                                 at_or_below="CERTIFIED")}
    assert ("kr", "USDJPY") in below_live, "a CANDIDATES cell is still a hole below CERTIFIED"
    truncated = t.holes(("country", "asset", "session"), 5, max_enumerate=4)
    assert t.last_scan["truncated"] is True and len(truncated) <= 5
    assert t.last_scan["enumerated"] == 4, "a truncated scan says so rather than reporting clean"
    with pytest.raises(ValueError, match="not axes"):
        t.holes(("planet",), 3)
    with pytest.raises(ValueError, match="repeats an axis"):
        t.holes(("country", "country"), 3)


def test_marginals_project_and_keep_the_best_state() -> None:
    t = _world()
    t.observe({"country": "kr", "asset": "USDJPY", "session": "asia"}, "INGESTED", {"s": 1})
    t.observe({"country": "kr", "asset": "USDJPY", "session": "london"}, "CANDIDATES", {"s": 1})
    m = t.marginals(("country", "asset"))
    row = m[("kr", "USDJPY")]
    assert row["n"] == 2 and row["best"] == "CANDIDATES"
    assert row["states"] == {"INGESTED": 1, "CANDIDATES": 1}


def test_json_round_trip_is_exact() -> None:
    t = _world()
    t.observe({"country": "ru", "asset": "EURUSD"}, "TESTING", {"source": "docket", "why": "q"})
    t.frontier({"country": "id", "asset": "AUDUSD"})
    doc = json.loads(json.dumps(t.to_json(), default=str))
    back = C.Tensor.from_json(doc)
    assert back.to_json() == t.to_json()
    assert back.get({"country": "ru", "asset": "EURUSD"}).state == "TESTING"
    cell = t.get({"country": "ru", "asset": "EURUSD"})
    assert C.Cell.from_json(cell.to_json()) == cell


# ------------------------------------------------------------------------------------------- EVIG
def test_every_evig_factor_is_in_the_breakdown_and_moves_the_score_its_own_way() -> None:
    t = _world()
    t.observe({"country": "kr", "asset": "USDJPY", "session": "asia"}, "CERTIFIED",
              {"source": "cert"})
    t.observe({"country": "kr", "asset": "EURUSD", "session": "asia"}, "FAILED",
              {"source": "gate", "why": "cost"})
    hole = C.Cell(C.WORLD, t.coordinates({"country": "kr", "asset": "AUDUSD",
                                          "session": "asia"}), "UNOBSERVED")
    br = C.evig_breakdown(hole, t.cells(), axes=("country", "asset", "session"),
                          reach=t.reachability())
    for key in ("prior_p_edge", "reachability", "novelty", "capacity", "cost", "evig",
                "judged_neighbours", "unreachable_axes", "nearest_tested_distance"):
        assert key in br, key
    assert br["judged_neighbours"] == {"positive": 1, "negative": 1, "n_neighbours": 2}
    assert br["prior_p_edge"] == pytest.approx(1.5 / 3.0)
    assert br["capacity_basis"].startswith("UNMEASURED"), "an unmeasured factor takes the prior"
    assert br["evig"] == pytest.approx(br["prior_p_edge"] * br["reachability"] * br["novelty"]
                                       * br["capacity"] / br["cost"], rel=1e-3)
    richer = C.evig(hole, t.cells(), axes=("country", "asset", "session"), reach=t.reachability(),
                    capacity=1.0)
    assert richer > br["evig"], "more capacity is more value"
    dearer = C.evig(hole, t.cells(), axes=("country", "asset", "session"), reach=t.reachability(),
                    cost=100.0)
    assert dearer < br["evig"], "a dearer next rung is less value per unit of compute"


def test_novelty_falls_as_a_hole_sits_closer_to_tested_ground() -> None:
    t = _world()
    t.observe({"country": "kr", "asset": "USDJPY", "session": "asia"}, "TESTING", {"s": 1})
    axes = ("country", "asset", "session")
    near = C.Cell(C.WORLD, t.coordinates({"country": "kr", "asset": "USDJPY",
                                          "session": "london"}), "UNOBSERVED")
    far = C.Cell(C.WORLD, t.coordinates({"country": "ru", "asset": "EURUSD",
                                         "session": "london"}), "UNOBSERVED")
    n_near = C.evig_breakdown(near, t.cells(), axes=axes, reach=t.reachability())
    n_far = C.evig_breakdown(far, t.cells(), axes=axes, reach=t.reachability())
    assert n_near["nearest_tested_distance"] == 1 and n_far["nearest_tested_distance"] == 3
    assert n_far["novelty"] > n_near["novelty"]


def test_reachability_counts_axis_components_with_data_somewhere() -> None:
    t = _world()
    t.observe({"country": "kr", "asset": "USDJPY"}, "INGESTED", {"s": 1})
    t.observe({"country": "ru", "asset": "EURUSD"}, "SOURCE_HUNT", {"s": 1})
    reach = t.reachability()
    assert reach["country"]["kr"] is True and reach["asset"]["USDJPY"] is True
    assert reach["country"]["ru"] is False, "a source hunt is not yet ingested data"
    hole = C.Cell(C.WORLD, t.coordinates({"country": "kr", "asset": "EURUSD"}), "UNOBSERVED")
    br = C.evig_breakdown(hole, t.cells(), axes=("country", "asset"), reach=reach)
    assert br["unreachable_axes"] == ["asset"] and br["reach_fraction"] == pytest.approx(0.5)
    assert br["reachability"] >= C.REACH_FLOOR, "an unreachable cell ranks low, never vanishes"


def test_the_prior_is_one_half_with_no_judged_neighbour_and_never_zero_or_one() -> None:
    t = _world()
    hole = C.Cell(C.WORLD, t.coordinates({"country": "id", "asset": "AUDUSD"}), "UNOBSERVED")
    assert C.evig_breakdown(hole, [])["prior_p_edge"] == pytest.approx(C.PRIOR)
    wins = [C.Cell(C.WORLD, t.coordinates({"country": "id", "asset": a}), "LIVE")
            for a in ("USDJPY", "EURUSD")]
    br = C.evig_breakdown(hole, wins, axes=("country", "asset"))
    assert 0.0 < br["prior_p_edge"] < 1.0, "Laplace smoothing: never a certainty from two rows"


# -------------------------------------------------------------------------------- country coverage
def _inventory(**layers: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    inv: dict[str, list[dict[str, object]]] = {k: [] for k in C.SOURCE_LAYERS}
    inv["UNTAGGED"] = []
    inv.update(layers)
    return inv


def test_covered_refuses_five_obvious_sources() -> None:
    """THE PRINCIPAL'S RULE, AS A TEST. Five verified sources in five layers, and a healthy
    discovery rate, is MAPPING -- not coverage."""
    five = _inventory(**{layer: [{"id": f"{layer}-1", "verified": True}]
                         for layer in C.SOURCE_LAYERS[:5]})
    verdict = C.covered("id", five, {"measured": True, "per_day": 2.0})
    assert verdict["state"] == "MAPPING" and verdict["covered"] is False
    assert verdict["condition_layers"]["met"] is False
    assert set(verdict["condition_layers"]["unmapped"]) == set(C.SOURCE_LAYERS[5:])
    assert verdict["condition_discovery"]["met"] is True, "the second condition held; the first "\
                                                          "is what refused it"


def test_covered_needs_both_conditions_and_names_which_one_failed() -> None:
    every = _inventory(**{layer: [{"id": f"{layer}-1", "verified": True}]
                          for layer in C.SOURCE_LAYERS})
    assert C.covered("kr", every, {"measured": True, "per_day": 0.5})["state"] == "COVERED"
    stalled = C.covered("kr", every, {"measured": True, "per_day": 0.0})
    assert stalled["state"] == "STALLED" and stalled["covered"] is False
    assert stalled["condition_layers"]["met"] is True
    unmeasured = C.covered("kr", every, {"measured": False, "why": "registry unreachable"})
    assert unmeasured["state"] == "UNMEASURED", "absence never resolves to a clean verdict"
    assert "registry unreachable" in unmeasured["why"]
    assert C.covered("kr", every, None)["state"] == "UNMEASURED"


def test_a_declared_absence_with_a_reason_maps_a_layer_and_a_bare_root_does_not() -> None:
    inv = _inventory(**{layer: [{"id": f"{layer}-1", "verified": True}]
                        for layer in C.SOURCE_LAYERS[:9]})
    inv["source_graph"] = [{"id": "absent:source_graph",
                            "absent_reason": "no citation graph exists for this market"}]
    assert C.covered("xx", inv, 1.0)["state"] == "COVERED"
    inv["source_graph"] = [{"id": "typed-root", "verified": False}]
    later = C.covered("xx", inv, 1.0)
    assert later["state"] == "MAPPING"
    assert later["condition_layers"]["declared_unverified"] == ["source_graph"], \
        "a root somebody typed is not a source until something fetched it"


# ----------------------------------------------------------------------------------- the ratchet
def test_a_floor_never_goes_down_and_a_reading_below_it_is_reported() -> None:
    first = C.ratchet(None, {"world_cells": 10.0, "countries_covered": 2.0})
    assert first["floors"] == {"countries_covered": 2.0, "world_cells": 10.0}
    up = C.ratchet(first["floors"], {"world_cells": 25.0, "countries_covered": 2.0})
    assert up["floors"]["world_cells"] == 25.0 and up["raised"] == ["world_cells"]
    down = C.ratchet(up["floors"], {"world_cells": 3.0, "countries_covered": 2.0})
    assert down["floors"]["world_cells"] == 25.0, "floors ratchet UP only (L1.50)"
    assert down["below_floor"]["world_cells"] == {"floor": 25.0, "current": 3.0}
    vanished = C.ratchet(up["floors"], {"countries_covered": 2.0})
    assert vanished["floors"]["world_cells"] == 25.0, \
        "a measurement that stopped is not a floor that dropped"
    assert C.ratchet(2.0, 1.0)["floors"] == {"value": 2.0}
    assert C.ratchet({"a": "not a number"}, {"a": 1.0})["floors"] == {"a": 1.0}


# ------------------------------------------------------------- the three named frontier rows
def test_the_named_example_cells_are_constructible_and_start_at_the_floor() -> None:
    """The specification's own sentences, as coordinates. If these cannot be built, the tensor
    cannot express the question the law says it must make explicit."""
    cells = {c.evidence["label"]: c for c in C.example_cells()}
    assert set(cells) == {"indonesia_nickel_china_cycle_aud_asia_risk_off",
                          "korea_semiconductor_supply_chain_jpy_asia",
                          "russia_energy_shipping_brent_eurusd",
                          "russia_energy_shipping_local_sources"}
    indonesia = cells["indonesia_nickel_china_cycle_aud_asia_risk_off"]
    assert "Indonesia nickel" in indonesia.evidence["story"]
    assert indonesia.tensor == C.WORLD and indonesia.state == "UNOBSERVED"
    v = indonesia.values()
    assert (v["country"], v["sector"], v["asset"], v["session"], v["regime"]) == \
        ("id", "metals_mining", "AUDUSD", "asia", "risk_off")
    korea = cells["korea_semiconductor_supply_chain_jpy_asia"]
    kv = korea.values()
    assert (kv["country"], kv["sector"], kv["information_type"], kv["asset"], kv["session"]) == \
        ("kr", "semiconductors", "supply_chain", "USDJPY", "asia")
    russia = [c for k, c in cells.items() if k.startswith("russia_energy_shipping")]
    assert {c.tensor for c in russia} == {C.WORLD, C.FOREST}, \
        "the Russian example is a world cell AND the forest ground that would feed it"
    forest = next(c for c in russia if c.tensor == C.FOREST)
    fv = forest.values()
    assert fv["source_class"] == "physical_economy" and fv["language"] == "ru"
    assert fv["asset_transmission"] == "XBRUSD"
    world_ru = next(c for c in russia if c.tensor == C.WORLD)
    assert world_ru.values()["asset"] == "EURUSD"


def test_the_named_rows_land_in_a_tensor_and_are_enumerated_as_holes() -> None:
    t = C.Tensor(C.WORLD, vocabulary={"country": ["id", "kr", "ru"],
                                      "sector": ["metals_mining", "semiconductors"],
                                      "asset": ["AUDUSD", "USDJPY", "EURUSD"]})
    for cell in C.example_cells():
        if cell.tensor == C.WORLD:
            t.frontier(cell.coordinates)
    assert len(t) == 3
    holes = t.holes(("country", "sector", "asset"), 99)
    assert ("id", "metals_mining", "AUDUSD") in {h.coordinates for h in holes}
    top = holes[0]
    assert top.state == "UNOBSERVED" and top.breakdown["next_state"] == "SOURCE_HUNT"
    assert top.to_json()["values"]["country"] in ("id", "kr", "ru")
