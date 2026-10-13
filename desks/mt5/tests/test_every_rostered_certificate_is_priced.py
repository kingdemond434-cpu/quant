"""Every STANDBY or LIVE certificate is priced under its own name (2026-10-13).

THE DEFECT: `certified_evidence` priced ONE certificate per (symbol, family, window), so 14
rostered XAUUSD variants (other timeframes and parameter sets of the same cell) either borrowed
the first certificate's reading through the promoter's `sym|family|selector` join or joined
nothing at all, and sat at STANDBY unpriced for ~13 days.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pa = pytest.importorskip("pf_allocator")
pr = pytest.importorskip("promoter")


def _fake_gauntlet(calls: list) -> types.ModuleType:
    eg = types.ModuleType("external_gauntlet")

    def build_cell(sym, fam, params, meta):
        calls.append((sym, fam, params))
        return {"df": params, "sigs": [1], "costs": 0}

    def daily_series(df, sigs, costs):
        return pd.Series([0.1 * (1 + len(calls)), -0.05, 0.2],
                         index=pd.date_range("2026-01-01", periods=3))

    eg.build_cell, eg.daily_series = build_cell, daily_series
    return eg


SRB = "external.XAUUSD.session_range_breakout"
CAR = "external.XAUUSD@M15.cross_asset_residual.p=e95ea804f8e3f059"
CAR_KEY = ("XAUUSD.cross_asset_residual.asia@M15#beta_win=240_entry_z=2.0_factor_symbols="
           "['NZDUSD', 'USDHUF']_lookback=240_side_mode=revert_ttl_bars=8")


def _desk(tmp_path, monkeypatch, calls: list) -> None:
    """The real shapes: survivors keyed by the `external.` id with a bare `cell`, the roster
    citing that id, and the forward clocks' table carrying the spec in its key."""
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    (tmp_path / "data" / "universe" / "universe.json").write_text("{}", "utf-8")
    roster = [
        {"name": "xauusd_session_range_breakout_asia_5_wb_12", "status": "STANDBY",
         "certificate": {"cell": f"{SRB}.rr=1.5_wb=12"}},
        {"name": "xauusd_session_range_breakout_asia_0_wb_12", "status": "STANDBY",
         "certificate": {"cell": f"{SRB}.rr=2.0_wb=12"}},
        {"name": "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059", "status": "STANDBY",
         "certificate": {"cell": CAR}},
        {"name": "xauusd_macro_conditional_asia_p_1", "status": "STANDBY",
         "certificate": {"cell": "external.XAUUSD@M5.macro_conditional.p=1"}},
        {"name": "xauusd_range_reversion_asia_p_2", "status": "STANDBY",
         "certificate": {"cell": "external.XAUUSD@M5.range_reversion.p=2"}},
        {"name": "audchf_live_twin", "status": "LIVE",
         "certificate": {"cell": f"{SRB}.rr=1.5_wb=12"}},
    ]
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")
    (tmp_path / "reports" / "CERTIFICATE_CLOCK_LAW.json").write_text(json.dumps({"rows": [
        {"certificate": CAR, "key": CAR_KEY, "status": "ACTIVE"},
        {"certificate": "external.XAUUSD@M5.macro_conditional.p=1", "key": "x#a=1",
         "status": "KILL"},
        {"certificate": "external.XAUUSD@M5.range_reversion.p=2", "key": "y",
         "status": "BLOCKED_NO_BARS"}]}), "utf-8")
    survivors = tmp_path / "survivors.json"
    survivors.write_text(json.dumps({"survivors": {
        f"{SRB}.rr=1.5_wb=12": {"cell": "XAUUSD.session_range_breakout.rr=1.5_wb=12",
                                 "shadow_spec": {"symbol": "XAUUSD", "selector": "asia",
                                                 "family": "session_range_breakout",
                                                 "params": {"rr": 1.5, "wait_bars": 12}}},
        f"{SRB}.rr=2.0_wb=12": {"cell": "XAUUSD.session_range_breakout.rr=2.0_wb=12",
                                 "shadow_spec": {"symbol": "XAUUSD", "selector": "asia",
                                                 "family": "session_range_breakout",
                                                 "params": {"rr": 2.0, "wait_bars": 12}}},
    }}), "utf-8")
    import research.portfolio_gap as pg
    monkeypatch.setattr(pg, "SURVIVORS", survivors)
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setattr(pa, "CLOCK_LAW", tmp_path / "reports" / "CERTIFICATE_CLOCK_LAW.json")
    monkeypatch.setitem(sys.modules, "external_gauntlet", _fake_gauntlet(calls))


def test_standby_certificates_are_priced_on_their_own_verified_specs(tmp_path,
                                                                      monkeypatch) -> None:
    calls: list = []
    _desk(tmp_path, monkeypatch, calls)
    out, acct = pa.certified_evidence()
    # The cell-named column is the rr=1.5 certificate; its STANDBY row keeps that join (no
    # second column of one bet), the LIVE twin is never re-keyed, and the rr=2.0 variant and
    # the clock-specced M15 certificate are priced under their own names.
    assert set(out) == {"XAUUSD_session_range_breakout_asia",
                        "xauusd_session_range_breakout_asia_0_wb_12",
                        "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059"}
    car = next(p for s, f, p in calls if f == "cross_asset_residual")
    assert car["factor_symbols"] == ["NZDUSD", "USDHUF"] and car["timeframe"] == "M15"
    assert acct["identity"]["xauusd_session_range_breakout_asia_0_wb_12"] == (
        "XAUUSD", "session_range_breakout")
    assert set(acct["rostered_zero"]) == {"xauusd_macro_conditional_asia_p_1"}
    assert "BLOCKED_NO_BARS" in acct["rostered_unmeasured"]["xauusd_range_reversion_asia_p_2"]
    # The promoter's raw-name join reaches the variant's own reading first.
    view = {"candidates": {"xauusd_session_range_breakout_asia_0_wb_12": {"name": "x"}}}
    row, why = pr.admission_of(view, "xauusd_session_range_breakout_asia_0_wb_12", "XAUUSD",
                               "session_range_breakout", "asia")
    assert row is not None and "0_wb_12" in why


def test_a_spec_that_does_not_rebuild_the_certificate_id_is_unmeasured(tmp_path,
                                                                       monkeypatch) -> None:
    calls: list = []
    _desk(tmp_path, monkeypatch, calls)
    law = tmp_path / "reports" / "CERTIFICATE_CLOCK_LAW.json"
    law.write_text(law.read_text("utf-8").replace("entry_z=2.0", "entry_z=9.9"), "utf-8")
    out, acct = pa.certified_evidence()
    name = "xauusd_cross_asset_residual_asia_p_e95ea804f8e3f059"
    assert name not in out and "no recoverable spec" in acct["rostered_unmeasured"][name]


def test_the_identity_reaches_the_evidence_as_the_certificates_symbol_and_family() -> None:
    daily = pd.DataFrame({"xauusd_session_range_breakout_asia_0_wb_12": [0.1, -0.1, 0.2]},
                         index=pd.date_range("2026-01-01", periods=3).date)
    ev = pa.sleeve_evidence(daily, {}, {}, identity={
        "xauusd_session_range_breakout_asia_0_wb_12": ("XAUUSD", "session_range_breakout")})
    assert (ev[0].symbol, ev[0].family) == ("XAUUSD", "session_range_breakout")


def test_a_priced_standby_sleeve_the_solve_zeroes_gets_a_recorded_zero(tmp_path,
                                                                       monkeypatch) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "s_live", "status": "LIVE"}, {"name": "s_standby", "status": "STANDBY"},
        {"name": "s_retired", "status": "RETIRED"}]}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    ev = [types.SimpleNamespace(name=n) for n in ("s_live", "s_standby", "s_retired")]
    assert set(pa.zeroed_live(ev, {})) == {"s_live", "s_standby"}
    z = pa.zeroed_live([], {}, recorded={"killed": "its forward clock reached KILL"})
    assert z == {"killed": "its forward clock reached KILL"}


def test_a_versioned_gold_bracket_records_zero_as_a_copy_of_its_base(tmp_path,
                                                                     monkeypatch) -> None:
    """gold_asia_v2..v4 trade identically to gold_asia (the roster carries no rr): one bet,
    priced once. The copy gets a recorded zero instead of 'never priced'."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "gold_asia", "status": "LIVE"}, {"name": "gold_asia_v2", "status": "STANDBY"},
        {"name": "gold_london_am_v3", "status": "STANDBY"}]}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    ev = [types.SimpleNamespace(name="gold_asia")]
    z = pa.zeroed_live(ev, {"gold_asia": 0.08})
    assert set(z) == {"gold_asia_v2"} and "same signal as gold_asia" in z["gold_asia_v2"]


# ------------------------------------------------------------- audit #346 follow-ups (10-13)
def test_a_live_versioned_gold_row_is_never_zeroed_by_the_name_rule(tmp_path,
                                                                     monkeypatch) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "gold_asia", "status": "LIVE"}, {"name": "gold_asia_v2", "status": "LIVE"}]}),
        "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    ev = [types.SimpleNamespace(name="gold_asia")]
    assert "gold_asia_v2" not in pa.zeroed_live(ev, {"gold_asia": 0.08})


def test_a_fill_hour_replay_is_not_charged_the_cost_bias_again(monkeypatch) -> None:
    import numpy as np
    idx = pd.date_range("2025-01-01", periods=60)
    daily = pd.DataFrame({"EURZAR_x_asia": np.random.default_rng(0).normal(0, 1, 60)},
                         index=idx)
    monkeypatch.setattr(pa, "_execution_costs", lambda names: {
        "sleeves": {"EURZAR_x_asia": {"cost_bias_r": 0.18, "cost_r": 0.05}},
        "summary": {"n_measured": 1, "n_sleeves": 1, "n_undercharged": 1,
                    "worst_undercharge": None}})
    charged = pa.sleeve_evidence(daily, {}, {})
    once = pa.sleeve_evidence(daily, {}, {},
                              cost_basis={"EURZAR_x_asia": "fill_hour_01_spread"})
    assert charged[0].cost_bias_r == 0.18 and once[0].cost_bias_r == 0.0


def _cost_frame(name: str):
    import numpy as np
    idx = pd.date_range("2025-01-01", periods=60)
    return pd.DataFrame({name: np.random.default_rng(0).normal(0, 1, 60)}, index=idx)


def _costs(monkeypatch, name: str) -> None:
    monkeypatch.setattr(pa, "_execution_costs", lambda names: {
        "sleeves": {name: {"cost_bias_r": 0.18, "cost_r": 0.05}},
        "summary": {"n_measured": 1, "n_sleeves": 1, "n_undercharged": 1,
                    "worst_undercharge": None}})


def test_a_pooled_or_empty_cost_basis_keeps_the_cost_bias(monkeypatch) -> None:
    daily = _cost_frame("EURZAR_x_asia")
    _costs(monkeypatch, "EURZAR_x_asia")
    for basis in ({"EURZAR_x_asia": "pooled_spread"}, {"EURZAR_x_asia": ""}, {}, None):
        ev = pa.sleeve_evidence(daily, {}, {}, cost_basis=basis)
        assert ev[0].cost_bias_r == 0.18, basis


def test_the_cost_basis_is_dropped_where_the_backtest_series_wins_alignment() -> None:
    daily = _cost_frame("EURZAR_x_asia")
    short = pd.Series([0.1, 0.2], index=pd.date_range("2025-01-01", periods=2).date)
    longer = pd.Series([0.1] * 90, index=pd.date_range("2024-01-01", periods=90).date)
    basis = {"EURZAR_x_asia": "fill_hour_01_spread", "NEW_y": "fill_hour_02_spread"}
    assert pa.cost_basis_after_align(daily, {"EURZAR_x_asia": short, "NEW_y": short},
                                     basis) == {"NEW_y": "fill_hour_02_spread"}
    assert pa.cost_basis_after_align(daily, {"EURZAR_x_asia": longer}, basis) == {
        "EURZAR_x_asia": "fill_hour_01_spread"}


def test_gold_names_resolve_to_the_gold_bars_with_no_identity_and_no_legs() -> None:
    daily = _cost_frame("gold_asia")
    ev = pa.sleeve_evidence(daily, {}, {})
    # Unchanged by the identity change: no identity row, so the name's own token stands.
    assert ev[0].symbol == "gold" and tuple(ev[0].inputs) == ("bars:GOLD",)


def test_an_early_library_failure_publishes_unmeasured_not_an_empty_map() -> None:
    v = pa._book_unmeasured({"refused": {"import": "ModuleNotFoundError: eg"}})
    assert v["verdict"] == "UNMEASURED" and "import" in v["why"]
    assert pa._book_unmeasured({"rostered_unmeasured": {}}) == {}


def test_cost_basis_is_unmeasured_when_the_roster_was_never_walked() -> None:
    """Audit #370 v2: an early exit publishes UNMEASURED, never a clean {}."""
    v = pa._cost_basis_published({"refused": {"universe": "unreadable"}})
    assert v["verdict"] == "UNMEASURED" and "universe" in v["why"]
    walked = {"rostered_unmeasured": {}, "cost_basis": {"a": "fill_hour_01_spread"}}
    assert pa._cost_basis_published(walked) == {"a": "fill_hour_01_spread"}
    assert pa._cost_basis_published({"rostered_unmeasured": {}}) == {}
