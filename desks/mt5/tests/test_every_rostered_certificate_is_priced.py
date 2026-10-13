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
        calls.append(params)
        return None if params.get("tf") == "broken" else {"df": params, "sigs": [1], "costs": 0}

    def daily_series(df, sigs, costs):
        ser = pd.Series([0.1 * (1 + len(calls)), -0.05, 0.2],
                        index=pd.date_range("2026-01-01", periods=3))
        return ser

    eg.build_cell, eg.daily_series = build_cell, daily_series
    return eg


def test_rostered_variants_are_priced_under_their_own_names(tmp_path, monkeypatch) -> None:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text("{}", "utf-8")
    roster = [
        {"name": "xauusd_macro_conditional_asia_p_aaa", "status": "STANDBY",
         "certificate": {"cell": "external.XAUUSD@M5.macro_conditional.p=aaa"}},
        {"name": "xauusd_macro_conditional_asia_p_bbb", "status": "STANDBY",
         "certificate": {"cell": "external.XAUUSD@M5.macro_conditional.p=bbb"}},
        {"name": "xauusd_macro_conditional_asia_p_ccc", "status": "RETIRED",
         "certificate": {"cell": "external.XAUUSD@M5.macro_conditional.p=ccc"}},
    ]
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    calls: list = []
    monkeypatch.setitem(sys.modules, "external_gauntlet", _fake_gauntlet(calls))
    import research.portfolio_gap as pg
    survivors = [{"symbol": "XAUUSD", "family": "macro_conditional", "window": "asia",
                  "cell": f"external.XAUUSD@M5.macro_conditional.p={h}", "params": {"tf": h}}
                 for h in ("aaa", "bbb", "ccc")]
    monkeypatch.setattr(pg, "load_survivors", lambda: survivors)
    out, acct = pa.certified_evidence()
    assert set(out) == {"XAUUSD_macro_conditional_asia", "xauusd_macro_conditional_asia_p_aaa",
                        "xauusd_macro_conditional_asia_p_bbb"}
    assert {"tf": "bbb"} in calls and {"tf": "ccc"} not in calls[1:]   # retired: not replayed
    assert acct["rostered_unpriced"] == []
    # The promoter's raw-name join reaches the variant's own reading first.
    view = {"candidates": {"xauusd_macro_conditional_asia_p_bbb": {"name": "x"}}}
    row, why = pr.admission_of(view, "xauusd_macro_conditional_asia_p_bbb", "XAUUSD",
                               "macro_conditional", "asia")
    assert row is not None and "p_bbb" in why


def test_a_rostered_certificate_that_cannot_be_replayed_is_named(tmp_path,
                                                                monkeypatch) -> None:
    (tmp_path / "data" / "universe").mkdir(parents=True)
    (tmp_path / "data" / "universe" / "universe.json").write_text("{}", "utf-8")
    roster = [{"name": "xauusd_range_reversion_asia_p_zzz", "status": "STANDBY",
               "certificate": {"cell": "external.XAUUSD@M5.range_reversion.p=zzz"}}]
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": roster}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    monkeypatch.setitem(sys.modules, "external_gauntlet", _fake_gauntlet([]))
    import research.portfolio_gap as pg
    monkeypatch.setattr(pg, "load_survivors", lambda: [
        {"symbol": "XAUUSD", "family": "range_reversion", "window": "asia",
         "cell": "external.XAUUSD@M5.range_reversion.p=zzz", "params": {"tf": "broken"}}])
    out, acct = pa.certified_evidence()
    assert out == {}
    assert acct["rostered_unpriced"] == ["xauusd_range_reversion_asia_p_zzz"]


def test_a_priced_standby_sleeve_the_solve_zeroes_gets_a_recorded_zero(tmp_path,
                                                                       monkeypatch) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sleeves.json").write_text(json.dumps({"sleeves": [
        {"name": "s_live", "status": "LIVE"}, {"name": "s_standby", "status": "STANDBY"},
        {"name": "s_retired", "status": "RETIRED"}]}), "utf-8")
    monkeypatch.setattr(pa, "BASE", tmp_path)
    ev = [types.SimpleNamespace(name=n) for n in ("s_live", "s_standby", "s_retired")]
    assert set(pa.zeroed_live(ev, {})) == {"s_live", "s_standby"}
