"""THE REGION MANDATE FRAMEWORK: the template every country department instantiates.

The fixture is a synthetic two-actor region -- because the assertions that matter are about the
SHAPE, and a test written against Japan's actual actors would pass for Japan and say nothing
about China. Every path is redirected into `tmp_path`: the registry is a throwaway file
(`registry.set_path`, `registry.BACKUP` monkeypatched so a real backup can never be restored over
it) and the broker universe is a three-symbol stub.

The tests that matter most are the REFUSALS. A mandate that validates with a blank falsifier, a
miner pointing at no domain, or capital authority is not a slightly weaker mandate -- it is a
department that would run and produce rows nobody can interpret or act on. And `disposition_of`
is tested on every branch, because section 23's rule is not "convert most things": it is that no
transformation may leave without one of seven dispositions, and the branch that quietly returns
GENERATED for a reason it does not recognise is exactly how a silent drop is born.
"""
from __future__ import annotations

import dataclasses
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from libs.moat import registry as R
from libs.research import region_mandate as RM

REGION = "japantest"

UNIVERSE = {
    "XAUUSD": {"asset_class": "Metals", "symbol": "XAUUSD"},
    "USDJPY": {"asset_class": "Forex Majors", "symbol": "USDJPY"},
    "APPLE": {"asset_class": "Equities", "symbol": "APPLE"},
}

ACTOR_A = RM.Actor(
    name="bank_treasury",
    holds="a yen funding book against dollar assets",
    forced_to=("roll the hedge at the month-end fixing",),
    when="the last business day of each month, 09:55 Tokyo",
    information=("hedge_ratio",),
    constraints=("mandated hedge ratio",),
    instruments=("USDJPY",),
    counterparties=("dealer fx desks",),
    observables=("fixing window volume",),
    impact="a directional print into the fix that reverses afterwards",
    persistence="the mandate is regulatory, so it does not learn",
    falsifier="no excess return into the fix across 36 month-ends",
)
ACTOR_B = RM.Actor(
    name="retail_margin_house",
    holds="leveraged long gold against yen",
    forced_to=("liquidate on a margin breach",),
    when="the Tokyo morning after a US close gap",
    information=("margin_utilisation",),
    constraints=("maintenance margin",),
    instruments=("XAUUSD",),
    counterparties=("the house's own hedging desk",),
    observables=("aggregate margin utilisation",),
    impact="forced selling that overshoots and mean-reverts",
    persistence="the constraint is contractual and survives the participants",
    falsifier="no overshoot conditional on a utilisation spike over 24 events",
)
DOMAIN_A = RM.Domain(id="fx_policy", title="policy and the currency",
                     objects=("the fixing window",), conditions=("month end",),
                     instruments=("USDJPY",), controls=("a random non-fixing window",))
DOMAIN_B = RM.Domain(id="retail_flow", title="leveraged retail flow",
                     objects=("margin utilisation",), conditions=("overnight gap",),
                     instruments=("XAUUSD",), controls=("a day with no utilisation spike",))
DATASET = RM.DatasetSpec(name="tokyo_margin", source="a domestic exchange",
                         coverage="2016->", frequency="daily", publication_lag_days=1.0,
                         revisions="none", licence="public", history_from="2016-01-01",
                         pit_feasible=True, assets=("XAUUSD",),
                         mechanism_families=("forced_liquidation", "fx_fixing_flow"),
                         how_to_fetch="the exchange's daily csv")
MINERS = (
    RM.MinerSpec(name="fix_miner", domain_ids=("fx_policy",), kind="mechanism",
                 entry="miners:fix_miner", cadence_s=3600.0),
    RM.MinerSpec(name="margin_miner", domain_ids=("retail_flow",), kind="mechanism",
                 entry="miners:margin_miner", cadence_s=3600.0),
    RM.MinerSpec(name="scout", domain_ids=("fx_policy", "retail_flow"), kind="scout",
                 entry="miners:scout", cadence_s=3600.0),
)


def mandate(**over: Any) -> RM.Mandate:
    base = RM.Mandate(
        region=REGION, mission="find what the region's actors are forced to do, and trade it",
        actors=(ACTOR_A, ACTOR_B), domains=(DOMAIN_A, DOMAIN_B),
        instruments=("XAUUSD", "USDJPY"), native_languages=("ja",),
        terminology={"fx_policy": ("実需", "仲値")}, source_classes=("regulator", "broker"),
        datasets=(DATASET,), miners=MINERS, controls_default=("a shuffled event calendar",))
    return dataclasses.replace(base, **over) if over else base


@pytest.fixture
def reg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    R.set_path(tmp_path / "alpha_registry.sqlite")
    uni = tmp_path / "universe.json"
    uni.write_text(json.dumps(UNIVERSE), encoding="utf-8")
    monkeypatch.setattr(RM, "UNIVERSE_JSON", uni)
    conn = R.connect()
    try:
        yield conn
    finally:
        conn.close()
        R.set_path(None)


# --------------------------------------------------------------------------- the vocabularies
def test_the_vocabularies_are_the_sizes_the_mandate_declares():
    assert len(RM.OPERATORS) == 14
    assert len(RM.DISPOSITIONS) == 7
    assert len(RM.FAILURE_CLASSES_REGION) == 10
    assert len(RM.REQUIREMENTS) == 25
    assert len(RM.FRONTIER_STATES) == 9
    assert len(RM.PIT_FIELDS) == 6
    assert len(RM.LOOP_STEPS) == 20
    assert len(RM.OBJECTIVE_TERMS) == 7
    assert len(RM.MINIMISE_TERMS) == 5
    assert len(RM.ACTOR_FIELDS) == 11


def test_every_region_failure_class_maps_onto_the_registry_vocabulary():
    assert set(RM.FAILURE_TO_REGISTRY) == set(RM.FAILURE_CLASSES_REGION)
    assert set(RM.FAILURE_TO_REGISTRY.values()) == set(R.FAILURE_CLASSES)


def test_the_loop_is_twenty_named_steps_and_the_order_is_the_contract():
    assert RM.LOOP_STEPS.index("compile_cells") == 11
    assert RM.LOOP_STEPS.index("ingest_verdicts") < RM.LOOP_STEPS.index("update_priors")
    assert RM.LOOP_STEPS.index("update_priors") < RM.LOOP_STEPS.index("create_descendants")


# --------------------------------------------------------------------------- validation
def test_a_complete_mandate_validates(reg):
    assert RM.validate(mandate()) == []


def test_an_actor_missing_one_of_its_eleven_fields_is_refused(reg):
    blind = dataclasses.replace(ACTOR_A, falsifier="")
    problems = RM.validate(mandate(actors=(blind, ACTOR_B)))
    assert any("bank_treasury" in p and "falsifier" in p for p in problems)


def test_a_miner_naming_an_unknown_domain_is_refused(reg):
    lost = RM.MinerSpec(name="ghost", domain_ids=("no_such_domain",), kind="mechanism",
                        entry="miners:ghost")
    problems = RM.validate(mandate(miners=(*MINERS, lost)))
    assert any("ghost" in p and "no_such_domain" in p for p in problems)


def test_capital_authority_is_refused_outright(reg):
    problems = RM.validate(mandate(capital_authority=True))
    assert any("capital_authority" in p and RM.TERMINAL_OUTPUT in p for p in problems)


def test_a_domain_without_negative_controls_is_refused(reg):
    bare = dataclasses.replace(DOMAIN_A, controls=())
    problems = RM.validate(mandate(domains=(bare, DOMAIN_B), controls_default=()))
    assert any("fx_policy" in p and "negative control" in p for p in problems)


def test_a_shortened_loop_is_refused(reg):
    problems = RM.validate(mandate(loop_steps=RM.LOOP_STEPS[:5]))
    assert any("loop_steps" in p for p in problems)


def test_an_equity_instrument_is_refused_and_an_unknown_one_is_named(reg):
    problems = RM.validate(mandate(instruments=("XAUUSD", "APPLE", "NOSUCH")))
    assert any("APPLE" in p and "equity" in p for p in problems)
    assert any("NOSUCH" in p and "universe" in p for p in problems)


def test_the_universe_check_is_skipped_when_the_registry_is_not_on_this_box(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(RM, "UNIVERSE_JSON", tmp_path / "absent.json")
    res = RM.resolve_instruments(mandate())
    assert res["measured"] is False
    assert res["universe"] == "ABSENT"
    assert RM.validate(mandate()) == []


# --------------------------------------------------------------------------- identity
def test_tag_is_the_prefix_every_region_row_carries():
    assert RM.tag(mandate()) == f"{REGION}:"


@pytest.mark.parametrize("row,why", [
    ({"generator": f"{REGION}:fix_miner"}, "prefix:generator"),
    ({"source_id": f"{REGION}:nikkei"}, "prefix:source_id"),
    ({"payload_json": json.dumps({"region": REGION})}, "payload_json.region"),
    ({"symbol": "XAUUSD"}, "symbol"),
    ({"assets_json": json.dumps(["USDJPY"])}, "assets"),
])
def test_is_region_row_names_the_criterion_that_matched(row, why):
    m = mandate()
    assert RM.is_region_row(m, row) is True
    assert RM.region_match(m, row) == why


def test_another_regions_row_is_not_this_regions():
    m = mandate()
    assert RM.is_region_row(m, {"generator": "china:forum_miner", "symbol": "EURUSD"}) is False
    assert RM.region_match(m, {"generator": "china:forum_miner"}) is None


# --------------------------------------------------------------------------- dispositions
@pytest.mark.parametrize("reason,state,expect", [
    ("economic:no_instrument", "BLOCKED", "ECONOMICALLY_INVALID"),
    ("economic:two_lane_mandate", "BLOCKED", "ECONOMICALLY_INVALID"),
    ("data:no_bars (XAUUSD_H1.parquet)", "BLOCKED", "DATA_BLOCKED"),
    ("data:pit_unknown (no knowable_at)", "BLOCKED", "PIT_BLOCKED"),
    ("data:ok (PIT_SAFE)", "COMPILED", "GENERATED"),
    ("novelty:exact_twin_already_enqueued", "BLOCKED", "DUPLICATE"),
    ("novelty:redundant_in_novelty_gate (k)", "BLOCKED", "DUPLICATE"),
    ("novelty:new (cell)", "QUEUED", "GENERATED"),
    ("cost:round_trip_exceeds_the_mean_edge", "BLOCKED", "COST_BLOCKED"),
    ("the cell was already tested last quarter", "BLOCKED", "ALREADY_TESTED"),
    (None, "TESTED", "ALREADY_TESTED"),
    (None, "QUEUED", "GENERATED"),
    ("", "COMPILED", "GENERATED"),
])
def test_disposition_of_every_blocked_reason(reason, state, expect):
    assert RM.disposition_of(reason, state) == expect


def test_an_unrecognised_reason_is_a_refusal_not_a_pass():
    # The one mapping this function may never make: "I do not know why it stopped, so call it
    # produced". A reason existing at all means the child did not leave.
    got = RM.disposition_of("some vocabulary nobody has written yet", "BLOCKED")
    assert got in RM.DISPOSITIONS
    assert got not in RM.PRODUCTIVE_DISPOSITIONS


def test_every_disposition_is_reachable():
    seen = {RM.disposition_of(r, s) for r, s in [
        ("data:ok (PIT_SAFE)", "COMPILED"), ("novelty:twin", "BLOCKED"),
        ("economic:no_family", "BLOCKED"), ("data:no_bars", "BLOCKED"),
        ("data:pit_unknown", "BLOCKED"), ("cost:too_wide", "BLOCKED"), (None, "TESTED")]}
    assert seen == set(RM.DISPOSITIONS)


# --------------------------------------------------------------------------- requirements
def _complete_candidate() -> dict[str, Any]:
    return {req: f"value-for-{req}" for req in RM.REQUIREMENTS}


def test_a_complete_candidate_is_missing_nothing():
    assert RM.candidate_complete(_complete_candidate()) == []


def test_candidate_complete_lists_exactly_what_is_missing():
    c = _complete_candidate()
    del c["falsifier"]
    del c["negative_control"]
    c["capacity"] = ""
    assert sorted(RM.candidate_complete(c)) == ["capacity", "falsifier", "negative_control"]


def test_an_empty_candidate_owes_all_twenty_five():
    assert len(RM.candidate_complete({})) == 25


def test_a_requirement_satisfied_under_the_deskss_own_spelling_counts():
    row = {"id": "cand_1", "discovery_id": "disc_1", "source_id": "japantest:src",
           "constraint_text": "maintenance margin", "params_json": {"a": 1},
           "exact_rules": "buy the close, exit at the fix", "search_count": 3,
           "expected_capacity": 1e6, "required_data_json": ["bars"], "family": "carry"}
    missing = RM.candidate_complete(row)
    for satisfied in ("candidate_id", "parent_discovery", "canonical_source", "constraint",
                      "parameters", "exact_entry", "exact_exit", "search_count_lineage",
                      "capacity", "required_data", "trial_family"):
        assert satisfied not in missing


# --------------------------------------------------------------------------- the boundaries
@pytest.mark.parametrize("knob", ["pit_lag_days", "trial_count_cap", "holdout_peek",
                                  "gauntlet_threshold", "forward_clock_days", "cost_assumption",
                                  "source_provenance_relabel"])
def test_assert_boundaries_refuses_a_knob_that_names_a_boundary(knob):
    with pytest.raises(RM.BoundaryBreach) as exc:
        RM.assert_boundaries({knob: 1})
    assert knob in str(exc.value)


def test_assert_boundaries_refuses_a_boundary_named_in_a_value_not_only_a_key():
    with pytest.raises(RM.BoundaryBreach):
        RM.assert_boundaries({"note": "relax the point in time rule for the fixing dataset"})


def test_assert_boundaries_admits_the_knobs_a_region_may_actually_move():
    RM.assert_boundaries({"miner_budget_floor": 0.05, "cold_share": 0.10,
                          "capacity_probe": True, "sessions": ["tokyo", "london"]})


# --------------------------------------------------------------------------- registers
def _plant_discovery(conn: sqlite3.Connection, mech: str, *, source: str = "src_a",
                     assets: list[str] | None = None, state: str = "COMPILED",
                     reason: str | None = None, **counters: int) -> str:
    did, _created = R.record_discovery(
        source_id=f"{REGION}:{source}", source_type="claim", mechanism=mech, origin="EXTERNAL",
        generator=f"{REGION}:fix_miner", assets=assets or ["USDJPY"],
        sessions=["tokyo"], horizons=["intraday"], regimes=["unconditional"],
        actor="bank_treasury", constraint="mandated hedge ratio", information="hedge_ratio",
        payload={"region": REGION, "language": "ja"}, conn=conn)
    R.set_discovery_state(did, state, reason=reason, conn=conn, **counters)
    return did


def test_the_nine_registers_are_counted_off_planted_rows(reg):
    _plant_discovery(reg, "fx_fixing_flow", possible_cells=10, generated_cells=6,
                     compiled_cells=4, queued_cells=3, tested_cells=1, blocked_cells=2)
    _plant_discovery(reg, "forced_liquidation", assets=["XAUUSD"], state="BLOCKED",
                     reason="data:no_bars (XAUUSD_M5.parquet)", possible_cells=5,
                     generated_cells=0, blocked_cells=5)
    regs = RM.conversion_registers(mandate(), conn=reg)
    prefix = REGION.upper()
    assert regs[f"{prefix}_DISCOVERIES"] == 2
    assert regs[f"{prefix}_INTERPRETED"] == 1          # the blocked one never reached a mechanism
    assert regs[f"{prefix}_MECHANISMS"] == 2
    assert regs[f"{prefix}_VALID_CELLS"] == 6
    assert regs[f"{prefix}_COMPILED"] == 4
    assert regs[f"{prefix}_QUEUED"] == 3
    assert regs[f"{prefix}_TESTED"] == 1
    assert regs[f"{prefix}_BLOCKED"] == 7
    assert regs[f"{prefix}_UNEXPLAINED_DEBT"] == 2     # 10 - 6 - 2, and it must go to zero
    assert regs["detail"]["blocked_by_disposition"] == {"DATA_BLOCKED": 1}


def test_another_regions_discovery_is_not_counted(reg):
    R.record_discovery(source_id="china:forum", source_type="claim", mechanism="whatever",
                       origin="EXTERNAL", generator="china:forum_miner", assets=["EURUSD"],
                       conn=reg)
    regs = RM.conversion_registers(mandate(), conn=reg)
    assert regs[f"{REGION.upper()}_DISCOVERIES"] == 0


def test_the_registers_say_which_criterion_filtered_them(reg):
    _plant_discovery(reg, "fx_fixing_flow")
    regs = RM.conversion_registers(mandate(), conn=reg)
    assert regs["detail"]["matched_by"] == {"prefix:generator": 1}


# --------------------------------------------------------------------------- the frontier
def test_the_frontier_is_actor_driven_and_every_cell_carries_a_state(reg):
    front = RM.frontier(mandate(), conn=reg)
    # two actors, one instrument each, one constraint, one information axis, two mechanisms,
    # and the closed session x horizon x regime tail.
    expected = 2 * 1 * 1 * 1 * 2 * len(RM.SESSIONS) * len(RM.HORIZONS) * len(RM.REGIMES)
    assert front["n_cells"] == expected
    assert sum(front["by_state"].values()) == expected
    assert front["by_state"]["UNSEEN"] == expected
    assert set(front["by_state"]) == set(RM.FRONTIER_STATES)


def test_planted_evidence_lands_on_the_map_and_the_strongest_claim_wins(reg):
    m = mandate()
    live = {"asset": "USDJPY", "actor": "bank_treasury", "constraint": "mandated hedge ratio",
            "mechanism": "fx_fixing_flow", "information": "hedge_ratio", "session": "tokyo",
            "horizon": "intraday", "regime": "unconditional"}
    front = RM.frontier(m, conn=reg, evidence={"LIVE": [live], "SURVIVED": [RM.cell_key(live)]})
    assert front["by_state"]["LIVE"] == 1
    assert front["by_state"]["SURVIVED"] == 0        # LIVE outranks it on the same cell
    assert front["n_populated"] == 1


def test_a_discovery_marks_its_cell_and_a_data_blocked_one_says_so(reg):
    _plant_discovery(reg, "fx_fixing_flow")
    _plant_discovery(reg, "forced_liquidation", assets=["XAUUSD"], source="src_b",
                     state="BLOCKED", reason="data:no_bars (XAUUSD_M5.parquet)")
    front = RM.frontier(mandate(), conn=reg)
    assert front["by_state"]["DISCOVERED"] == 1
    # the XAUUSD row names bank_treasury, which does not hold XAUUSD -- so it is COUNTED outside
    # the grid rather than quietly widening an axis.
    assert front["by_state"]["DATA_BLOCKED"] + front["unmeasured"]["evidence_outside_the_grid"] >= 1


def test_evidence_the_mandate_never_declared_is_counted_outside_the_grid(reg):
    m = mandate()
    front = RM.frontier(m, conn=reg, evidence={"LIVE": [{"asset": "USDJPY", "actor": "nobody"}]})
    assert front["unmeasured"]["evidence_outside_the_grid"] == 1
    assert front["by_state"]["LIVE"] == 0


def test_the_holes_are_ranked_and_a_crowded_axis_ranks_below_an_empty_one(reg):
    m = mandate()
    live = {"asset": "USDJPY", "actor": "bank_treasury", "constraint": "mandated hedge ratio",
            "mechanism": "fx_fixing_flow", "information": "hedge_ratio", "session": "tokyo",
            "horizon": "intraday", "regime": "unconditional"}
    front = RM.frontier(m, conn=reg, evidence={"LIVE": [live]})
    holes = RM.top_holes(front, 10)
    assert holes, "a region with 143 empty cells owes 143 holes"
    values = [h["value"] for h in holes]
    assert values == sorted(values, reverse=True)
    # USDJPY now carries a populated cell and XAUUSD does not, so the untouched asset leads --
    # which is the whole defence against fifty near-identical cells on one symbol.
    assert holes[0]["axes"]["asset"] == "xauusd"
    assert "populated sibling" in holes[0]["why"]


def test_the_mechanism_vocabulary_comes_from_the_datasets_and_what_was_discovered(reg):
    _plant_discovery(reg, "policy_meeting_drift")
    front = RM.frontier(mandate(), conn=reg)
    assert "forced_liquidation" in front["mechanism_vocabulary"]
    assert "policy_meeting_drift" in front["mechanism_vocabulary"]


# --------------------------------------------------------------------------- saturation
def _age(conn: sqlite3.Connection, discovery_id: str, days: float) -> None:
    when = (datetime.now(tz=UTC) - timedelta(days=days)).isoformat(timespec="seconds")
    conn.execute("UPDATE discoveries SET created_at=? WHERE discovery_id=?", (when, discovery_id))
    conn.commit()


def test_saturation_is_unmeasured_when_nothing_was_ever_mined(reg):
    sat = RM.saturation(mandate(), conn=reg)
    assert set(sat["axes"]) == set(RM.SATURATION_AXES)
    assert {v["verdict"] for v in sat["axes"].values()} == {"UNMEASURED"}


def test_a_source_axis_that_stopped_yielding_new_sources_reads_saturated(reg):
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"earlier_mech_{i}", source=f"src_{i}"), 10)
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"recent_mech_{i}", source="src_0"), 1)
    sat = RM.saturation(mandate(), conn=reg)
    assert sat["axes"]["source"]["verdict"] == "saturated"
    assert sat["axes"]["source"]["new_recent"] == 0


def test_an_axis_still_finding_new_values_reads_unsaturated(reg):
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"earlier_mech_{i}", source="src_0"), 10)
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"recent_mech_{i}", source=f"fresh_{i}"), 1)
    sat = RM.saturation(mandate(), conn=reg)
    assert sat["axes"]["source"]["verdict"] == "unsaturated"


def test_too_few_recent_rows_reads_poorly_measured_never_saturated(reg):
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"earlier_mech_{i}", source=f"src_{i}"), 10)
    _age(reg, _plant_discovery(reg, "one_recent", source="src_0"), 1)
    sat = RM.saturation(mandate(), conn=reg)
    assert sat["axes"]["source"]["verdict"] == "poorly_measured"


def test_an_axis_whose_recent_rows_are_all_data_blocked_reads_data_blocked(reg):
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"earlier_mech_{i}", source=f"src_{i}"), 10)
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"recent_mech_{i}", source="src_0", state="BLOCKED",
                                   reason="data:no_bars (USDJPY_M5.parquet)"), 1)
    sat = RM.saturation(mandate(), conn=reg)
    assert sat["axes"]["source"]["verdict"] == "data_blocked"


def test_every_saturation_verdict_is_in_the_declared_vocabulary(reg):
    for i in range(6):
        _age(reg, _plant_discovery(reg, f"m_{i}", source=f"src_{i}"), 1)
    sat = RM.saturation(mandate(), conn=reg)
    assert {v["verdict"] for v in sat["axes"].values()} <= set(RM.SATURATION_VERDICTS)


# --------------------------------------------------------------------------- ROI and dashboard
def test_source_roi_is_paid_in_independent_survivors_per_compute_hour(reg):
    reg.execute("INSERT INTO source_yield(source_id, leads, claims, mechanisms, candidates, "
                "donated, judged, survivors, independent_survivors, compute_s, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f"{REGION}:nikkei", 100, 90, 12, 40, 40, 20, 3, 2, 7200.0, RM._now()))
    reg.execute("INSERT INTO source_yield(source_id, leads, claims, mechanisms, candidates, "
                "donated, judged, survivors, independent_survivors, compute_s, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f"{REGION}:blog", 500, 400, 1, 2, 2, 1, 0, 0, 0.0, RM._now()))
    reg.execute("INSERT INTO source_yield(source_id, leads, claims, mechanisms, candidates, "
                "donated, judged, survivors, independent_survivors, compute_s, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("china:weibo", 900, 900, 90, 90, 90, 90, 9, 9, 100.0, RM._now()))
    reg.commit()
    roi = RM.roi_by_source(mandate(), conn=reg)
    assert roi["n_sources"] == 2, "another region's source is not this region's ROI"
    top = roi["sources"][0]
    assert top["source_id"] == f"{REGION}:nikkei"
    assert top["independent_survivors_per_compute_hour"] == 1.0
    assert any("blog" in u and "compute_s" in u for u in roi["unmeasured"])


def test_research_roi_names_every_unmeasured_term(reg):
    rroi = RM.research_roi(mandate(), conn=reg)
    assert rroi["research_roi"] is None
    assert any("orthogonal gauntlet value" in u for u in rroi["unmeasured"])
    assert any(u.startswith("compute:") for u in rroi["unmeasured"])


def test_the_dashboard_carries_every_declared_field(reg):
    _plant_discovery(reg, "fx_fixing_flow", possible_cells=4, generated_cells=4, compiled_cells=2)
    doc = RM.dashboard(mandate(), conn=reg)
    assert set(RM.DASHBOARD_FIELDS) <= set(doc)
    assert doc["capital_authority"] is False
    assert doc["terminal_output"] == RM.TERMINAL_OUTPUT
    assert doc["valid_cells"] == 4
    assert isinstance(doc["frontier_by_state"], dict)
    assert isinstance(doc["unmeasured"], list)


def test_the_dashboard_passes_extra_through_without_overwriting_a_measurement(reg):
    doc = RM.dashboard(mandate(), conn=reg, extra={"pass": 7, "region": "SHOULD NOT WIN"})
    assert doc["pass"] == 7
    assert doc["region"] == REGION
