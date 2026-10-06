"""Observable adapters must use real inputs and expose only previously knowable values."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from libs.research_os.adapters import fetched_data as F
from libs.research_os.adapters import owned_data as O


@pytest.fixture
def estate(tmp_path, monkeypatch):
    desk = tmp_path / "desks/mt5"
    for directory in ("data/cot", "data/universe", "data/observables"):
        (desk / directory).mkdir(parents=True)
    monkeypatch.setattr(O, "ROOT", tmp_path)
    monkeypatch.setattr(O, "DESK", desk)
    monkeypatch.setattr(F, "ROOT", tmp_path)
    monkeypatch.setattr(F, "OBS", desk / "data/observables")
    return desk


def bars(periods=80):
    return pd.DataFrame({"close": np.linspace(100, 120, periods)},
                        index=pd.date_range("2026-01-01", periods=periods, freq="h", tz="UTC"))


def write_json(path, document):
    path.write_text(json.dumps(document))


@pytest.mark.parametrize("adapter", [O.CotPositioningAdapter, O.CarryAdapter,
                                     O.CrossAssetAdapter, F.ImpliedVolAdapter,
                                     F.GammaExposureAdapter, F.MacroCalendarAdapter])
def test_absent_observable_never_becomes_a_price_proxy(estate, adapter):
    result = adapter().measure({"symbol": "USDJPY"}, bars())
    assert result.status == "UNAVAILABLE"
    assert result.series is None
    assert result.notes


@pytest.mark.parametrize("sides,expected,confidence", [
    ({"long": {"swap_money_per_lot_night": 3}, "short": {"swap": -1}}, 2., 1.),
    ({"long": {"swap": 3}}, 3., .7),
    ({"short": {"carry_per_lot_night": -2}}, 2., .7),
])
def test_carry_snapshot_cannot_be_broadcast_before_its_receipt(estate, sides, expected, confidence):
    receipt = "2026-01-01T12:00:00Z"
    write_json(estate / "data/carry_state.json", {
        "generated_at": receipt, "symbols": {"USDJPY": sides}})
    adapter = O.CarryAdapter()
    result = adapter.measure({"symbol": "USDJPY"}, bars())
    assert result.status == "VALIDATED_PROXY"
    assert result.confidence == confidence
    assert result.series.iloc[:12].isna().all()
    assert result.series.iloc[12:].eq(expected).all()
    assert adapter.compatibility({"symbol": "USDJPY"}) == confidence


@pytest.mark.parametrize("document", [
    {"symbols": {"USDJPY": {"long": {"swap": 3}}}},
    {"generated_at": "bad", "symbols": {"USDJPY": {"long": {"swap": 3}}}},
    {"generated_at": "2027-01-01", "symbols": {"USDJPY": {"long": {"swap": 3}}}},
    {"generated_at": "2026-01-01", "symbols": {"USDJPY": {"long": {"wrong": 3}}}},
    [],
])
def test_unstamped_future_or_unpriced_carry_is_unavailable(estate, document):
    write_json(estate / "data/carry_state.json", document)
    assert O.CarryAdapter().measure({"symbol": "USDJPY"}, bars()).status == "UNAVAILABLE"


def test_cot_reports_are_not_visible_on_reference_date(estate):
    dates = pd.date_range("2025-12-30", periods=10, freq="7D")
    for name, offset in (("usd", 5), ("jpy", 0)):
        pd.DataFrame({"report_date": dates, "noncomm_positions_long_all":
                      np.arange(10) * 10 + offset, "noncomm_positions_short_all": [0] * 10,
                      "open_interest_all": [1000] * 10}).to_parquet(
                          estate / f"data/cot/{name}.parquet")
    b = pd.DataFrame({"close": 100}, index=pd.date_range("2025-12-30", periods=80,
                                                       freq="D", tz="UTC"))
    adapter = O.CotPositioningAdapter()
    result = adapter.measure({"symbol": "USDJPY"}, b)
    assert result.status == "DIRECT"
    assert result.pit_safe
    assert result.series.loc[:"2026-01-02"].isna().all()
    assert adapter.compatibility({"symbol": "USDJPY"}) == 1
    assert adapter.pit_check(result.series, b)[0]
    (estate / "data/cot/jpy.parquet").unlink()
    assert adapter.compatibility({"symbol": "USDJPY"}) == .7
    assert adapter.measure({"symbol": "USDJPY"}, b).status == "VALIDATED_PROXY"


def test_unreadable_cot_is_named_as_acquisition_work(estate):
    (estate / "data/cot/usd.parquet").write_text("not parquet")
    pd.DataFrame({"wrong": [1]}).to_parquet(estate / "data/cot/jpy.parquet")
    result = O.CotPositioningAdapter().measure({"symbol": "USDJPY"}, bars())
    assert result.status == "UNAVAILABLE"
    assert "unreadable" in result.notes
    assert "no report_date" in result.notes


def test_cross_asset_is_strictly_lagged_and_requires_a_different_instrument(estate):
    b = bars()
    peer = pd.DataFrame({"close": [100., 110., 121., 133.1]},
                        index=pd.date_range("2026-01-01", periods=4, freq="h"))
    peer.to_parquet(estate / "data/universe/XAUUSD_H1.parquet")
    adapter = O.CrossAssetAdapter()
    result = adapter.measure({"symbol": "USDJPY", "peer_symbol": "XAUUSD"}, b)
    assert result.status == "DIRECT"
    assert result.series.iloc[:2].isna().all()
    assert result.series.iloc[2] == pytest.approx(.1)
    assert adapter.measure({"symbol": "USDJPY"}, b).status == "VALIDATED_PROXY"
    assert adapter.compatibility({"peer": "XAUUSD"}) == 1
    assert adapter.compatibility({}) == .6
    for spec in ({"peer": "USDJPY"}, {"peer": "XAUUSD", "lead_bars": 0},
                 {"peer": "absent"}):
        assert adapter.measure({"symbol": "USDJPY", **spec}, b).status == "UNAVAILABLE"
    (estate / "data/universe/XAUUSD_H1.parquet").write_text("invalid")
    assert adapter.measure({"symbol": "USDJPY", "peer": "XAUUSD"}, b).status == "UNAVAILABLE"


def test_vix_close_is_not_knowable_at_its_own_daily_open(estate):
    path = estate / "data/observables/cboe_vix_history.json"
    write_json(path, {"series": [{"date": "2026-01-01", "close": 15},
                                  {"date": "2026-01-02", "close": 90}]})
    adapter = F.ImpliedVolAdapter()
    result = adapter.measure({}, bars())
    assert result.status == "DIRECT"
    assert result.series.iloc[:24].isna().all()
    assert result.series.iloc[24:48].eq(15).all()
    assert adapter.compatibility({}) == 1
    write_json(path, {"series": []})
    assert adapter.measure({}, bars()).status == "UNAVAILABLE"
    path.write_text("invalid")
    assert adapter.measure({}, bars()).status == "UNAVAILABLE"


def test_gamma_requires_real_forward_history_and_respects_fetch_time(estate):
    path = estate / "data/observables/cboe_spx_options.jsonl"
    rows = [{"fetched_at": stamp.isoformat(), "net_gex": i}
            for i, stamp in enumerate(pd.date_range("2026-01-02", periods=30, freq="h", tz="UTC"))]
    adapter = F.GammaExposureAdapter()
    path.write_text("invalid\n\n" + json.dumps(rows[0]))
    assert adapter.compatibility({}) == pytest.approx(1 / 30)
    assert adapter.measure({}, bars()).status == "UNAVAILABLE"
    path.write_text("\n".join(map(json.dumps, rows)))
    result = adapter.measure({}, bars())
    assert result.status == "DIRECT"
    assert result.series.iloc[:24].isna().all()
    assert result.series.iloc[24] == 0
    assert result.series.iloc[25] == 1
    assert adapter.pit_check(result.series, bars())[0]


def test_macro_calendar_does_not_fire_before_scheduled_event(estate):
    path = estate / "data/observables/fomc_calendar.json"
    write_json(path, {"raw": [{"type": "FOMC", "month": "2026-01", "days": "1-2"},
                               {"type": "Speech", "month": "2026-01", "days": "1"},
                               {"type": "Stat", "month": "bad", "days": "bad"},
                               {"type": "FOMC"}]})
    adapter = F.MacroCalendarAdapter()
    result = adapter.measure({"event_window_bars": 4}, bars())
    assert result.status == "DIRECT"
    assert result.series.iloc[:43].isna().all()
    assert result.series.iloc[43:48].eq(1).all()
    assert result.series.iloc[48:].eq(0).all()
    assert adapter.compatibility({}) == 0  # one scheduled event is not historical breadth
    write_json(path, {"raw": []})
    assert adapter.measure({}, bars()).status == "UNAVAILABLE"
