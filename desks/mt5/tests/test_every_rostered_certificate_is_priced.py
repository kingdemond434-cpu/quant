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
