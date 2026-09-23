"""The twelve miners: what each one yields, what each one refuses, and why refusing is an answer.

Every input here is synthetic. The point of these tests is not that a miner produces children --
it is that each of the twelve produces its OWN dimension independently, that a refusal carries a
reason instead of an empty list, and that the two economic rules the desk cares most about hold:
a session-window mechanism never reaches D1, and a single-name equity never reaches anything.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import transformation_miners as TM  # noqa: E402

#: A synthetic instrument registry: three hypothesis-lane classes and one event-lane class, so a
#: test can prove the two-lane order without importing the real universe.
INSTRUMENTS: dict[str, list[str]] = {
    "forex": ["EURUSD", "GBPUSD", "USDJPY"],
    "commodities": ["XAUUSD", "XAGUSD"],
    "indices": ["US500", "GER40"],
    "equities": ["APPLE", "AMAZON"],
}
FAMILIES = frozenset({"asia_momentum", "session_range_breakout", "level_breakout",
                      "cross_asset_residual", "carry"})
DEFAULTS: dict[str, dict[str, Any]] = {
    "asia_momentum": {"rr": 1.8, "ttl_bars": 12, "side_mode": "follow", "label": "not numeric"},
    "level_breakout": {"rr": 2.0, "wb": 8},
}

PARENT: dict[str, Any] = {
    "discovery_id": "disc_fixture",
    "mechanism_id": "session_handover",
    "family": "asia_momentum",
    "symbol": "XAUUSD",
    "asset_class": "commodities",
    "chart": "H1",
    "session": "asia",
    "regime": "unconditional",
    "params": {"rr": 1.8, "ttl_bars": 12},
    "information": "price_only",
    "horizon": "sub_4h",
    "economic_actor": "cross_session_risk_transferor",
    "side": "follow",
}


@pytest.fixture
def ctx() -> TM.Context:
    return TM.Context(
        instruments={k: list(v) for k, v in INSTRUMENTS.items() if k != "equities"},
        families=FAMILIES, defaults={k: dict(v) for k, v in DEFAULTS.items()},
        macro_states={"policy": ["carry_differential_high", "carry_differential_low"]},
        bars_available=lambda _s, _c: True,
        lane_ok=lambda s: s not in INSTRUMENTS["equities"], max_per_miner=20)


def _why(ctx: TM.Context, miner: str) -> str:
    return " ".join(n["why"] for n in ctx.notes if n["miner"] == miner)


# --------------------------------------------------------------------------- economics
def test_a_bar_longer_than_half_the_session_window_cannot_express_that_session():
    assert TM.chart_admits_session("H4", "asia") is True          # 240 x 2 == the 8h window
    assert TM.chart_admits_session("D1", "asia") is False
    assert TM.chart_admits_session("D1", "london") is False
    assert TM.chart_admits_session("D1", "all") is True           # unconditional: no window


def test_a_session_mechanism_is_never_compatible_with_d1():
    contract = TM.CONTRACTS["session_handover"]
    ok, why = TM.compatible(contract, chart="D1", session="asia")
    assert ok is False
    assert "D1" in why
    assert TM.compatible(contract, chart="H1", session="asia")[0] is True


def test_a_flow_contract_that_names_its_legs_refuses_a_cross_carrying_neither():
    month_end = TM.CONTRACTS["calendar_seasonality"]
    assert TM.currency_ok(month_end, "USDJPY") is True
    assert TM.currency_ok(month_end, "AUDNZD") is False
    assert TM.currency_ok(TM.CONTRACTS["trend_persistence"], "AUDNZD") is True


def test_every_contract_declares_a_falsifier_and_registers_into_the_ontology():
    assert all(c.falsifier for c in TM.CONTRACTS.values())
    ont = TM.register_contracts()
    assert set(TM.CONTRACTS) <= set(ont)


# --------------------------------------------------------------------------- the twelve
def test_asset_transfer_stays_in_the_class_and_never_touches_an_equity(ctx):
    kids = TM.mine_asset_transfer(PARENT, ctx)
    assert {k["symbol"] for k in kids} == {"XAGUSD"}
    assert all(k["transformation"] == "asset_transfer" and k["axis"] == "symbol" for k in kids)
    assert all(k["parent_discovery_ids"] == ["disc_fixture"] and k["why"] for k in kids)


def test_asset_transfer_records_a_reason_when_the_class_has_no_peer(ctx):
    ctx.instruments = {"commodities": ["XAUUSD"]}
    assert TM.mine_asset_transfer(PARENT, ctx) == []
    assert "no other hypothesis-lane instrument" in _why(ctx, "asset_transfer")


def test_horizon_moves_one_step_each_way_and_the_contract_prunes_the_rest(ctx):
    kids = TM.mine_horizon(PARENT, ctx)
    assert {k["chart"] for k in kids} == {"M15", "H4"}
    assert all(k["axis"] == "chart" for k in kids)
    assert {k["horizon"] for k in kids} == {"intrabar", "sub_1d"}


def test_horizon_never_proposes_d1_for_a_session_mechanism(ctx):
    kids = TM.mine_horizon({**PARENT, "chart": "H4"}, ctx)
    assert "D1" not in {k["chart"] for k in kids}
    assert "D1" in _why(ctx, "horizon")


def test_session_moves_to_the_adjacent_window_and_refuses_all_for_a_session_claim(ctx):
    kids = TM.mine_session(PARENT, ctx)
    assert {k["session"] for k in kids} == {"london"}
    assert "not a all-session claim" in _why(ctx, "session")


def test_session_offers_the_unconditional_control_where_the_contract_allows_it(ctx):
    parent = {**PARENT, "mechanism_id": "trend_persistence", "session": "london"}
    kids = TM.mine_session(parent, ctx)
    assert {"asia", "ny", "all"} == {k["session"] for k in kids}


def test_regime_proposes_both_sides_of_both_pairs(ctx):
    kids = TM.mine_regime(PARENT, ctx)
    assert {k["regime"] for k in kids} == set(TM.REGIME_LADDER)
    assert all(k["params"]["regime"] == k["regime"] for k in kids)


def test_residual_proposes_each_factor_leg_that_applies(ctx):
    kids = TM.mine_residual(PARENT, ctx)
    assert {k["params"]["residual"] for k in kids} == {"usd", "gold", "equity"}
    assert all(k["information"] == "cross_asset" for k in kids)
    assert all(k["params"]["residual_tag"] == "residual" for k in kids)


def test_residual_drops_the_dollar_leg_on_an_instrument_that_has_none(ctx):
    kids = TM.mine_residual({**PARENT, "symbol": "US500"}, ctx)
    assert "usd" not in {k["params"]["residual"] for k in kids}


def test_interaction_crosses_every_other_information_axis(ctx):
    kids = TM.mine_interaction(PARENT, ctx)
    got = {k["information"] for k in kids}
    assert "price_only" not in got
    assert got == set(TM.INFORMATION_AXES) - {"price_only"}
    assert all(k["params"]["conditioner"] == k["information"] for k in kids)


def test_inverse_is_refused_where_the_mechanism_is_directional(ctx):
    assert TM.mine_inverse(PARENT, ctx) == []
    assert "directional by construction" in _why(ctx, "inverse")


def test_inverse_is_minted_where_the_ontology_declares_symmetry(ctx):
    parent = {**PARENT, "mechanism_id": "range_reversion", "side": "revert"}
    kids = TM.mine_inverse(parent, ctx)
    assert [k["side"] for k in kids] == ["follow"]
    assert kids[0]["params"]["side_mode"] == "follow"
    assert kids[0]["axis"] == "side"


def test_inverse_on_an_uninterpreted_parent_says_symmetry_needs_an_economics(ctx):
    assert TM.mine_inverse({**PARENT, "mechanism_id": "unknown"}, ctx) == []
    assert "symmetry is a claim about economics" in _why(ctx, "inverse")


def test_execution_proposes_the_other_three_expressions(ctx):
    kids = TM.mine_execution(PARENT, ctx)
    assert len(kids) == 3
    got = {(k["entry_timing"], k["execution"]) for k in kids}
    assert ("instant", "market") not in got
    assert got == set(TM.EXECUTION_VARIANTS) - {("instant", "market")}


def test_cross_asset_takes_one_instrument_per_other_class_and_no_equity(ctx):
    kids = TM.mine_cross_asset(PARENT, ctx)
    assert {k["symbol"] for k in kids} == {"EURUSD", "US500"}
    assert {k["asset_class"] for k in kids} == {"forex", "indices"}
    assert not ({k["symbol"] for k in kids} & set(INSTRUMENTS["equities"]))


def test_cross_asset_respects_a_contract_that_names_its_classes(ctx):
    kids = TM.mine_cross_asset({**PARENT, "mechanism_id": "carry_rollover"}, ctx)
    assert {k["asset_class"] for k in kids} == {"forex"}
    assert "does not act on it" in _why(ctx, "cross_asset")


def test_macro_condition_uses_the_axis_files_the_desk_holds(ctx):
    kids = TM.mine_macro_condition(PARENT, ctx)
    assert {k["params"]["macro_state"] for k in kids} == {"carry_differential_high",
                                                          "carry_differential_low"}
    assert all(k["information"] == "macro" and k["regime"].startswith("policy:") for k in kids)


def test_macro_condition_with_no_axis_file_is_unmeasured_not_empty(ctx):
    ctx.macro_states = {}
    assert TM.mine_macro_condition(PARENT, ctx) == []
    assert "UNMEASURED" in _why(ctx, "macro_condition")


def test_parameter_neighborhood_halves_and_doubles_every_numeric_default(ctx):
    kids = TM.mine_parameter_neighborhood(PARENT, ctx)
    moved = {(k["axis"], tuple(sorted(k["params"].items()))) for k in kids}
    assert len(kids) == 4
    assert all(a == "params" for a, _ in moved)
    rr = sorted(k["params"]["rr"] for k in kids if k["params"]["rr"] != 1.8)
    ttl = sorted(k["params"]["ttl_bars"] for k in kids if k["params"]["ttl_bars"] != 12)
    assert rr == [0.9, 3.6] and ttl == [6, 24]


def test_parameter_neighborhood_with_no_numeric_param_is_unmeasured(ctx):
    kids = TM.mine_parameter_neighborhood({**PARENT, "family": "nosuch", "params": {}}, ctx)
    assert kids == []
    assert "UNMEASURED" in _why(ctx, "parameter_neighborhood")


# --------------------------------------------------------------------------- resurrection
def test_failure_resurrection_stops_the_branch_on_redundant(ctx):
    assert TM.mine_failure_resurrection({**PARENT, "failure_class": "redundant"}, ctx) == []
    why = _why(ctx, "failure_resurrection")
    assert "STOP" in why and "multiplicity budget" in why


def test_failure_resurrection_lowers_the_prior_and_mints_nothing_on_no_edge(ctx):
    assert TM.mine_failure_resurrection({**PARENT, "failure_class": "no_edge"}, ctx) == []
    assert ctx.priors and ctx.priors[0]["mechanism_id"] == "session_handover"
    assert ctx.priors[0]["direction"] == "down"


def test_failure_resurrection_routes_each_named_cause_to_its_enabling_change(ctx):
    cost = TM.mine_failure_resurrection({**PARENT, "failure_class": "cost_killed"}, ctx)
    assert cost and all(k["resurrection_route"] == "execution" for k in cost)
    assert all(k["params"]["cost_aware"] is True for k in cost)
    assert all(k["transformation"] == "failure_resurrection" for k in cost)

    asset = TM.mine_failure_resurrection({**PARENT, "failure_class": "wrong_asset"}, ctx)
    assert {k["symbol"] for k in asset} == {"XAGUSD"}

    horizon = TM.mine_failure_resurrection({**PARENT, "failure_class": "wrong_horizon"}, ctx)
    assert {k["chart"] for k in horizon} == {"M15", "H4"}

    regime = TM.mine_failure_resurrection({**PARENT, "failure_class": "regime_specific"}, ctx)
    assert {k["regime"] for k in regime} == set(TM.REGIME_LADDER)

    direction = TM.mine_failure_resurrection(
        {**PARENT, "mechanism_id": "range_reversion", "failure_class": "wrong_direction"}, ctx)
    assert [k["side"] for k in direction] == ["revert"]


def test_failure_resurrection_without_a_failure_class_says_nothing_died(ctx):
    assert TM.mine_failure_resurrection(PARENT, ctx) == []
    assert "nothing died here" in _why(ctx, "failure_resurrection")


def test_an_unrouted_failure_class_is_counted_never_guessed(ctx):
    assert TM.mine_failure_resurrection({**PARENT, "failure_class": "sunspots"}, ctx) == []
    assert "no declared route" in _why(ctx, "failure_resurrection")


# --------------------------------------------------------------------------- run_all
def test_run_all_gives_every_miner_the_same_parent_independently(ctx):
    out = TM.run_all(PARENT, ctx)
    assert set(out) == set(TM.MINERS)
    assert len(TM.MINERS) == 12
    # The dimensions that must not be suppressed by a neighbour returning nothing.
    for miner in ("asset_transfer", "horizon", "session", "regime", "residual", "interaction",
                  "execution", "cross_asset", "macro_condition", "parameter_neighborhood"):
        assert out[miner], miner
    assert out["inverse"] == [] and out["failure_resurrection"] == []


def test_run_all_records_what_the_compute_budget_left_behind(ctx):
    ctx.max_per_miner = 2
    out = TM.run_all(PARENT, ctx)
    assert all(len(rows) <= 2 for rows in out.values())
    assert ctx.truncated
    assert all(t["n"] > 0 and "owed, not refused" in t["why"] for t in ctx.truncated)


def test_a_raising_miner_is_a_note_not_a_dead_run(ctx, monkeypatch):
    def boom(_parent, _ctx):
        raise RuntimeError("synthetic")

    monkeypatch.setitem(TM.MINERS, "regime", boom)
    out = TM.run_all(PARENT, ctx)
    assert out["regime"] == []
    assert "miner raised RuntimeError" in _why(ctx, "regime")
    assert out["horizon"]


def test_no_miner_ever_yields_an_equity(ctx):
    ctx.instruments = {**ctx.instruments, "equities": list(INSTRUMENTS["equities"])}
    out = TM.run_all(PARENT, ctx)
    produced = {k.get("symbol") for rows in out.values() for k in rows}
    assert not (produced & set(INSTRUMENTS["equities"]))
