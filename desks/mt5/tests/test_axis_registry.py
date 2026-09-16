"""The information-axis registry: what it records, what it refuses to guess, what it proposes.

Every input here is synthetic and every path is redirected into `tmp_path`. The organ reads six
real artifacts on the box and all six may be absent, partial or stale, so the tests that matter
most are the ones that prove an absent input produces a COUNT rather than a crash or a clean
verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import axis_registry as ar  # noqa: E402

#: A synthetic broker registry: two hypothesis-lane classes and one event-lane class, so a test
#: can prove the two-lane order without importing the real universe.
_CLASSES = {"EURUSD": "forex", "GBPUSD": "forex", "XAUUSD": "commodities", "XAGUSD": "commodities",
            "USDJPY": "forex", "APPLE": "equities"}
_FAMILIES = frozenset({"session_range_breakout", "carry", "overnight_gap_decay",
                       "mean_reversion_rsi"})


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """The organ pointed at an empty synthetic tree, with its two policy shims stubbed."""
    paths = {"EXTERNAL_SURVIVORS": tmp_path / "data" / "hypotheses" / "external_survivors.json",
             "GATE_LEDGER": tmp_path / "data" / "hypotheses" / "gate_verdict_ledger.jsonl",
             "RESEARCH_QUEUE": tmp_path / "data" / "research_queue.json",
             "UNIVERSAL_SURVIVORS": tmp_path / "reports" / "UNIVERSAL_SURVIVORS.json",
             "SHADOW_STATE": tmp_path / "reports" / "shadow" / "shadow_state.json",
             "SLEEVES": tmp_path / "data" / "sleeves.json",
             "UNIVERSE": tmp_path / "data" / "universe" / "universe.json",
             "OUT_REPORT": tmp_path / "reports" / "AXIS_REGISTRY.json",
             "OUT_CELLS": tmp_path / "data" / "axis_registry.jsonl",
             "INTAKE": tmp_path / "data" / "intelligence" / "axis_registry"}
    for name, path in paths.items():
        monkeypatch.setattr(ar, name, path)
    monkeypatch.setattr(ar, "asset_class_of", lambda s: _CLASSES.get(str(s).upper(), ar.UNKNOWN))
    monkeypatch.setattr(ar, "may_hypothesise",
                        lambda s: _CLASSES.get(str(s).upper()) in ("forex", "commodities"))
    monkeypatch.setattr(ar, "registered_families", lambda: _FAMILIES)
    monkeypatch.setattr(ar, "compiler_vocab", frozenset)
    monkeypatch.setattr(ar, "_banned", lambda f: False)
    _write(paths["UNIVERSE"], {"EURUSD": {"asset_class": "Forex", "bars": 90},
                               "GBPUSD": {"asset_class": "Forex", "bars": 80},
                               "XAUUSD": {"asset_class": "Commodities", "bars": 70},
                               "XAGUSD": {"asset_class": "Commodities", "bars": 60},
                               "APPLE": {"asset_class": "Equities", "bars": 999}})
    return paths


# ------------------------------------------------------------------ state precedence
def test_the_strongest_source_wins_whatever_order_the_sources_are_read_in(desk):
    """One cell described by four sources keeps LIVE, and keeps every source that named it."""
    spec = {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia"}
    _write(desk["EXTERNAL_SURVIVORS"], [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                         "params": {"session": "asia"}}])
    _write(desk["UNIVERSAL_SURVIVORS"], {"survivors": {"k": {"shadow_spec": spec}}})
    _write(desk["SHADOW_STATE"], {"XAUUSD.session_range_breakout.asia": {"status": "ACTIVE",
                                                                        "n": 14}})
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                          "session": "asia", "status": "LIVE"}]})
    cells = ar.collect_cells({})
    assert len(cells) == 1, "the four sources describe ONE ten-axis coordinate"
    row = next(iter(cells.values()))
    assert row["state"] == "LIVE"
    assert sorted(row["sources"]) == ["UNIVERSAL_SURVIVORS", "external_survivors", "shadow_state",
                                      "sleeves"]


def test_a_weaker_source_read_last_never_demotes_a_cell(desk):
    """A docket row (UNMEASURED) read after a certificate must not overwrite it."""
    axes = ar.axis_cell("EURUSD", "carry")
    cells: dict[str, dict] = {}
    ar._add(cells, axes, "CERTIFIED", "UNIVERSAL_SURVIVORS")
    ar._add(cells, axes, "UNMEASURED", "external_survivors")
    ar._add(cells, axes, "MEASURED_FAIL", "gate_verdict_ledger")
    assert next(iter(cells.values()))["state"] == "CERTIFIED"
    ar._add(cells, axes, "LIVE", "sleeves")
    assert next(iter(cells.values()))["state"] == "LIVE"


def test_a_forward_clock_that_never_ran_is_not_forward_evidence(desk):
    """REFUSED and BLOCKED clocks produced no observation; calling them FORWARD would read as
    evidence the desk never collected."""
    _write(desk["SHADOW_STATE"], {
        "EURUSD.carry.asia": {"status": "REFUSED_BY_UNIVERSE_POLICY"},
        "GBPUSD.carry.asia": {"status": "ACTIVE", "n": 3},
        "XAUUSD.carry.asia": {"status": "RETIRED_ORPHAN", "n": 8}})
    states = {r["instrument"]: r["state"] for r in ar.collect_cells({}).values()}
    assert states == {"EURUSD": "MEASURED_FAIL", "GBPUSD": "FORWARD", "XAUUSD": "FORWARD"}


def test_the_queue_and_the_ledger_carry_their_own_verdicts(desk):
    _write(desk["RESEARCH_QUEUE"], [
        {"symbol": "EURUSD", "family": "carry", "status": "GAUNTLET_REJECTED"},
        {"symbol": "GBPUSD", "family": "carry", "status": "QUEUED_CANONICAL_GAUNTLET"}])
    _write(desk["GATE_LEDGER"], None)
    desk["GATE_LEDGER"].write_text(
        json.dumps({"cell": "XAUUSD.carry.p=abc", "sym": "XAUUSD", "family": "carry",
                    "passed": True}) + "\n"
        + "{not json}\n\n"
        + json.dumps({"cell": "XAGUSD.carry.p=def", "sym": "XAGUSD", "family": "carry",
                      "passed": False}) + "\n", encoding="utf-8")
    states = {r["instrument"]: r["state"] for r in ar.collect_cells({}).values()}
    assert states == {"EURUSD": "MEASURED_FAIL", "GBPUSD": "UNMEASURED",
                      "XAUUSD": "CERTIFIED", "XAGUSD": "MEASURED_FAIL"}


# ------------------------------------------------------------------ unknown counting
def test_an_unmapped_family_is_unknown_on_every_axis_it_governs_and_is_counted(desk):
    axes = ar.axis_cell("NOTREAL", "a_family_nobody_registered", {}, "Z9", "narnia")
    assert axes["mechanism"] == ar.UNKNOWN
    assert axes["information_source"] == ar.UNKNOWN
    assert axes["economic_actor"] == ar.UNKNOWN
    assert axes["execution_style"] == ar.UNKNOWN
    assert axes["asset_class"] == ar.UNKNOWN          # not in the broker registry
    assert axes["chart"] == ar.UNKNOWN                # an unreadable timeframe, not a default
    assert axes["session"] == ar.UNKNOWN              # an unmapped session token
    assert axes["horizon"] == ar.UNKNOWN              # no chart and no declared hold
    cells: dict[str, dict] = {}
    ar._add(cells, axes, "UNMEASURED", "external_survivors")
    ar._add(cells, ar.axis_cell("EURUSD", "carry"), "UNMEASURED", "external_survivors")
    counts = ar.unknown_counts(cells)
    assert counts["mechanism"] == 1 and counts["economic_actor"] == 1
    assert counts["chart"] == 1 and counts["session"] == 1 and counts["asset_class"] == 1
    assert counts["instrument"] == 0, "NOTREAL is an instrument name, just not a priced one"


def test_a_known_family_is_never_unknown_and_every_registered_family_is_mapped():
    """The table is the desk's promise that it has not guessed. A registered family missing from
    it would be counted UNKNOWN forever and nobody would look."""
    mech, info, style = ar.classify_family("session_range_breakout")
    assert (mech, info, style) == ("breakout_liquidity", "price_only", "stop")
    assert ar.MECHANISM_ACTOR[mech] == "stop_loss_holder"
    missing = ar.registered_families() - set(ar.FAMILY_TABLE)
    assert missing == set(), f"registered families with no mechanism mapping: {sorted(missing)}"


def test_a_missing_chart_is_h1_because_that_is_what_the_docket_means_by_bare(desk):
    assert ar.normalise_chart(None) == "H1" and ar.normalise_chart("") == "H1"
    assert ar.normalise_chart("m15") == "M15" and ar.normalise_chart("4h") == "H4"
    assert ar.normalise_chart("W1") == ar.UNKNOWN
    assert ar.normalise_session(None) == "all" and ar.normalise_session("continuous") == "all"
    assert ar.normalise_session("london_am") == "london"
    assert ar.normalise_session("afternoon") == "ny"
    assert ar.normalise_session("overlap") == "overlap"
    assert ar.normalise_session("nonsense") == ar.UNKNOWN


def test_the_horizon_bucket_reads_the_hold_against_the_chart():
    assert ar.horizon_of("M5", {"max_hold": 1}) == "intrabar"
    assert ar.horizon_of("M5", {"max_hold": 9}) == "sub_4h"
    assert ar.horizon_of("H1", {"hold_bars": 6}) == "sub_1d"
    assert ar.horizon_of("H1", {"hold_days": 3}) == "multi_day"
    assert ar.horizon_of("D1", {}) == "multi_day"
    assert ar.horizon_of("M15", {}) == "intrabar"
    assert ar.horizon_of(ar.UNKNOWN, {}) == ar.UNKNOWN
    # A presence FLAG is not a bar count: `horizon: True` from a clock key must not become 1 bar.
    assert ar.horizon_of("D1", {"horizon": True}) == "multi_day"


def test_regime_and_execution_style_fall_back_to_the_family_not_to_a_guess():
    assert ar.regime_of({}) == "unconditional"
    assert ar.regime_of({"band": [0.9, 1.0]}) == "band_conditional"
    assert ar.regime_of({}, "NORMAL_DAY") == "normal_day"
    assert ar.regime_of({}, "continuous") == "unconditional"
    assert ar.execution_style_of("scalp_market", "carry") == "market"
    assert ar.execution_style_of(None, "session_range_breakout") == "stop"
    assert ar.execution_style_of(None, "who_knows") == ar.UNKNOWN


# ------------------------------------------------------------------ the clock keys
def test_a_parameter_fingerprint_is_not_a_regime():
    """Measured 2026-09-16: reading `p=44136fa355b3678a` as a regime gave 1,569 distinct regimes
    for 5,361 cells -- one value per cell, which is an axis that measures nothing."""
    out = ar.parse_shadow_key("USDMXN.overnight_gap_decay.p=44136fa355b3678a")
    assert out["family"] == "overnight_gap_decay"
    assert out["regime"] is None
    assert out["param_names"] == ["p"]


def test_the_four_clock_key_shapes_the_desk_actually_writes():
    assert ar.parse_shadow_key("XAUUSD.asia#rr=1.5_wait_bars=8") == {
        "symbol": "XAUUSD", "family": "", "session": "asia", "regime": None,
        "param_names": ["rr", "wait_bars"]}
    assert ar.parse_shadow_key("GBPMXN.overnight_gap_decay.asia")["family"] == \
        "overnight_gap_decay"
    third = ar.parse_shadow_key("EURJPY.asia.NORMAL_DAY")
    assert third["session"] == "asia" and third["regime"] == "NORMAL_DAY" and not third["family"]
    fourth = ar.parse_shadow_key("EURILS.relative_value.continuous#peer_symbol=EURUSD")
    assert fourth["param_names"] == ["peer_symbol"], "a name with an underscore is not a value"
    assert ar.parse_shadow_key("")["symbol"] == ""


# ------------------------------------------------------------------ the tensor
def test_occupancy_counts_every_named_pair_by_state(desk):
    cells: dict[str, dict] = {}
    ar._add(cells, ar.axis_cell("EURUSD", "carry"), "LIVE", "sleeves")
    ar._add(cells, ar.axis_cell("GBPUSD", "carry"), "MEASURED_FAIL", "research_queue")
    ar._add(cells, ar.axis_cell("XAUUSD", "session_range_breakout", {"session": "asia"}),
            "CERTIFIED", "UNIVERSAL_SURVIVORS")
    occ = ar.occupancy(cells)
    assert set(occ) == {"asset_classxmechanism", "chartxsession",
                        "mechanismxinformation_source", "asset_classxinformation_source"}
    assert occ["asset_classxmechanism"]["forex|carry_rollover"] == {"LIVE": 1,
                                                                   "MEASURED_FAIL": 1}
    assert occ["asset_classxmechanism"]["commodities|breakout_liquidity"] == {"CERTIFIED": 1}
    assert occ["chartxsession"]["H1|all"] == {"LIVE": 1, "MEASURED_FAIL": 1}
    assert occ["chartxsession"]["H1|asia"] == {"CERTIFIED": 1}
    assert occ["mechanismxinformation_source"]["carry_rollover|carry"] == {"LIVE": 1,
                                                                           "MEASURED_FAIL": 1}
    assert ar.axis_counts(cells)["asset_class"] == {"forex": 2, "commodities": 1}


# ------------------------------------------------------------------ the frontier
def test_empty_regions_are_unoccupied_ranked_and_capped(desk):
    cells: dict[str, dict] = {}
    ar._add(cells, ar.axis_cell("EURUSD", "carry"), "LIVE", "sleeves")
    ar._add(cells, ar.axis_cell("GBPUSD", "session_range_breakout"), "MEASURED_FAIL",
            "research_queue")
    model, source = ar.fit_prior(cells)
    assert source.endswith("surrogate.py") and model["n"] == 2
    regions = ar.empty_regions(cells, model, _FAMILIES, limit=12)
    occupied = {ar.region_key(r) for r in cells.values()}
    assert 0 < len(regions) <= 12
    assert not [r for r in regions if r["coordinate"] in occupied]
    assert [r["rank_score"] for r in regions] == sorted(
        (r["rank_score"] for r in regions), reverse=True)
    # The LIVE cell's own axis values transfer: a carry region scores above a breakout one that
    # shares its chart and session, because the only difference is the axis that paid.
    best = {r["coordinate"]: r["predicted"] for r in
            ar.empty_regions(cells, model, _FAMILIES, limit=500)}
    assert best["commodities|carry_rollover|carry|H1|asia"] > \
        best["commodities|breakout_liquidity|price_only|H1|asia"]


def test_the_candidate_space_excludes_the_event_lane_and_sessions_d1_cannot_run(desk):
    regions = ar.candidate_regions({}, _FAMILIES)
    assert regions, "a registry with two hypothesis-lane classes must produce candidates"
    assert not [r for r in regions if r[0] == "equities"], "the event lane is never hunted"
    assert not [r for r in regions if r[3] == "D1" and r[4] != "all"], "D1 carries no session"
    assert not [r for r in regions if r[1] == ar.UNKNOWN], "an unnamed mechanism is not a target"


def test_an_unimportable_surrogate_is_unmeasured_not_a_zero_verdict(desk, monkeypatch):
    """A prior the desk cannot fit is UNMEASURED. Returning 0.0 as a verdict would read as
    "known bad" for every region and quietly freeze the frontier at whatever sorted first."""
    monkeypatch.setitem(sys.modules, "libs.research_os", None)
    model, source = ar.fit_prior({})
    assert source == ar.UNKNOWN and "UNMEASURED" in model["why"]
    flat = ar.score_region(model, "a|b|c|d|e")
    assert flat["rank_score"] == 0.0 and flat["coordinate"] == "a|b|c|d|e"


# ------------------------------------------------------------------ proposals
def _cells_with_one_live(family: str = "carry") -> dict[str, dict]:
    cells: dict[str, dict] = {}
    ar._add(cells, ar.axis_cell("EURUSD", family, {"session": "asia"}), "LIVE", "sleeves")
    return cells


def test_proposals_only_ever_name_a_family_that_exists(desk, monkeypatch):
    cells = _cells_with_one_live()
    model, _ = ar.fit_prior(cells)
    regions = ar.empty_regions(cells, model, _FAMILIES, limit=40)
    picked = ar.select(cells, model, regions, max_proposals=30)
    rows = [p for mode, _ in ar.SHARES for p in picked[mode]]
    assert rows, "the synthetic tree has unoccupied regions a registered family implements"
    assert {p["family"] for p in rows} <= _FAMILIES
    assert not {p["family"] for p in rows} & ar.NOT_A_FAMILY

    # With NO family importable there is nothing to propose, and the report says so rather than
    # emitting a row naming a constructor that does not exist.
    monkeypatch.setattr(ar, "registered_families", frozenset)
    report, _cells, proposals = ar.build()
    assert proposals == [] and "no registered family" in report["why_no_proposals"]


def test_a_region_whose_family_is_unregistered_yields_no_proposal(desk, monkeypatch):
    """`mean_reversion_rsi` is registered here and `dav_range_filter_adx` is not, though both
    implement range_reversion|price_only|limit. Dropping the registered one must silence the
    region entirely rather than fall through to the historic name."""
    region = {"asset_class": "forex", "mechanism": "range_reversion",
              "information_source": "price_only", "chart": "H1", "session": "all"}
    kwargs: dict[str, Any] = {"mode": "global_explore", "why": "w",
                              "prefer": frozenset(), "by_class": {"forex": ["EURUSD"]},
                              "rank_score": 1.0}
    assert ar._proposal(region, families=_FAMILIES, **kwargs)["family"] == "mean_reversion_rsi"
    assert ar._proposal(region, families=frozenset({"carry"}), **kwargs) is None


def test_proposals_stay_in_the_hypothesis_lane_and_name_a_runnable_session(desk):
    equity = {"asset_class": "equities", "mechanism": "carry_rollover",
              "information_source": "carry", "chart": "H1", "session": "all"}
    assert ar._proposal(equity, "global_explore", "w", _FAMILIES, frozenset(),
                        {"equities": ["APPLE"]}, 1.0) is None, "equities are never hunted"
    overlap = {"asset_class": "forex", "mechanism": "carry_rollover",
               "information_source": "carry", "chart": "H1", "session": "overlap"}
    assert ar._proposal(overlap, "global_explore", "w", _FAMILIES, frozenset(),
                        {"forex": ["EURUSD"]}, 1.0) is None, "no window exists for overlap"


def test_the_three_selectors_share_one_budget_and_every_row_is_shaped_for_the_intake(desk):
    cells = _cells_with_one_live()
    model, _ = ar.fit_prior(cells)
    regions = ar.empty_regions(cells, model, _FAMILIES, limit=200)
    picked = ar.select(cells, model, regions, max_proposals=10)
    rows = [p for mode, _ in ar.SHARES for p in picked[mode]]
    assert len(rows) <= 10
    assert {p["selector_mode"] for p in rows} <= {"global_explore", "learned_exploit",
                                                  "local_mutate"}
    coords = [ar.region_key(p["axis_cell"]) for p in rows]
    assert len(coords) == len(set(coords)), "one region is proposed once, by one arm"
    for p in rows:
        assert p["kind"] == "hypothesis" and p["source"] == "axis_registry"
        assert p["symbols"] and all(ar.may_hypothesise(s) for s in p["symbols"])
        assert set(p["axis_cell"]) == set(ar.AXES)
        assert p["why"].split(":")[0] in ("UNOCCUPIED", "LEARNED", "MUTATION")
        assert p["params"].get("timeframe", p["timeframe"]) == p["timeframe"]
    assert ar.select(cells, model, regions, max_proposals=0) == {
        "global_explore": [], "learned_exploit": [], "local_mutate": []}


def test_the_mutation_arm_moves_exactly_one_axis_off_a_cell_that_already_works(desk):
    cells = _cells_with_one_live()
    live = next(iter(cells.values()))
    model, _ = ar.fit_prior(cells)
    picked = ar.select(cells, model, [], max_proposals=20)
    assert picked["global_explore"] == [] and picked["learned_exploit"] == []
    assert picked["local_mutate"], "an empty region list must not silence the mutation arm"
    for p in picked["local_mutate"]:
        moved = [a for a in ar.REGION_AXES if p["axis_cell"][a] != live[a]]
        assert moved in (["chart"], ["session"]), f"{moved} is not a one-axis mutation"
        assert "MUTATION" in p["why"] and live["instrument"] in p["why"]


# ------------------------------------------------------------------ tolerance and the CLI
def test_every_input_may_be_absent_and_the_report_says_so_rather_than_crashing(desk):
    report, cells, proposals = ar.build()
    assert cells == {} and report["n_cells"] == 0
    assert report["by_state"] == dict.fromkeys(ar.STATES, 0)
    assert set(report["inputs"].values()) == {"ABSENT"}, report["inputs"]
    assert report["inputs"]["external_survivors.json"] == "ABSENT"
    assert report["unknown_counts"] == dict.fromkeys(ar.AXES, 0)
    assert report["rule"] and report["empty_regions"], "no cells means the WHOLE space is empty"
    assert isinstance(proposals, list)


def test_an_unreadable_or_oversized_input_is_named_not_silently_skipped(desk, monkeypatch):
    desk["EXTERNAL_SURVIVORS"].parent.mkdir(parents=True, exist_ok=True)
    desk["EXTERNAL_SURVIVORS"].write_text("{", encoding="utf-8")       # 1 byte, still not JSON
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "EURUSD", "family": "carry",
                                          "status": "LIVE"}]})
    monkeypatch.setattr(ar, "MAX_INPUT_BYTES", 10)
    note: dict[str, str] = {}
    ar.collect_cells(note)
    assert note["external_survivors.json"].startswith("UNREADABLE")
    assert note["sleeves.json"].startswith("TOO_LARGE")


def test_a_utf8_bom_input_still_reads(desk):
    desk["SLEEVES"].parent.mkdir(parents=True, exist_ok=True)
    desk["SLEEVES"].write_text(json.dumps({"sleeves": [{"symbol": "EURUSD", "family": "carry",
                                                        "status": "LIVE"}]}), encoding="utf-8-sig")
    cells = ar.collect_cells({})
    assert [r["state"] for r in cells.values()] == ["LIVE"]


def test_the_cli_dry_run_prints_six_lines_and_writes_nothing(desk, capsys):
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                          "session": "asia", "status": "LIVE"}]})
    assert ar.main(["--dry-run"]) == 0
    lines = capsys.readouterr().out.strip().split("\n")
    assert len(lines) == 6, lines
    assert lines[0].startswith("AXIS REGISTRY") and "sleeves.json=READ" in lines[0]
    assert "cells 1 on 10 axes" in lines[1] and "LIVE=1" in lines[1]
    assert "DRY RUN" in lines[5]
    assert not desk["OUT_REPORT"].exists() and not desk["OUT_CELLS"].exists()
    assert not desk["INTAKE"].exists()


def test_a_real_run_writes_the_report_the_ledger_and_the_intake_donation(desk, capsys):
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "session_range_breakout",
                                          "session": "asia", "status": "LIVE"}]})
    assert ar.main(["--max-proposals", "4"]) == 0
    report = json.loads(desk["OUT_REPORT"].read_text(encoding="utf-8-sig"))
    assert report["n_cells"] == 1 and report["by_state"]["LIVE"] == 1
    assert set(report) >= {"at", "n_cells", "by_state", "axes", "occupancy", "empty_regions",
                           "unknown_counts", "selection", "rule"}
    rows = [json.loads(line) for line in
            desk["OUT_CELLS"].read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and set(rows[0]) == {"cell_id", "state", "sources", *ar.AXES}
    donations = sorted(desk["INTAKE"].glob("discoveries_*.json"))
    assert len(donations) == 1
    proposals = json.loads(donations[0].read_text(encoding="utf-8"))
    assert 0 < len(proposals) <= 4
    assert all(p["family"] in _FAMILIES for p in proposals)
    assert not list(desk["INTAKE"].glob("*.tmp")), "an atomic write leaves no temp file behind"
    assert len(capsys.readouterr().out.strip().split("\n")) == 6


def test_the_donation_is_capped_at_sixty_however_large_the_flag(desk):
    """The ceiling lives in `build`, not in the CLI: an organ whose bound can be argued away by a
    flag has no bound. One run may donate 60 rows to the intake and not one more."""
    _write(desk["SLEEVES"], {"sleeves": [{"symbol": "XAUUSD", "family": "carry",
                                          "status": "LIVE"}]})
    _report, _cells, proposals = ar.build(max_proposals=100_000)
    assert len(proposals) <= ar.MAX_PROPOSALS
    _report, _cells, four = ar.build(max_proposals=4)
    assert len(four) <= 4
