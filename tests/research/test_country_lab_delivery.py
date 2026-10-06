"""Country studies must retain controls, honest absence and durable research provenance."""
from __future__ import annotations

import json
from types import SimpleNamespace

import numpy as np
import pytest

from libs.moat import registry as R
from libs.research import country_lab as L


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "BACKUP", tmp_path / "no_backup")
    previous = R.path()
    R.set_path(tmp_path / "registry.sqlite")
    connection = R.connect()
    monkeypatch.setattr(L, "desk_module", lambda name: None)
    monkeypatch.setattr(L, "universe", lambda: {
        "USDJPY": {"asset_class": "fx"}, "EURUSD": {"asset_class": "fx"},
        "US500": {"asset_class": "index"}, "GER40": {"asset_class": "index"}})
    yield connection
    connection.close()
    R.set_path(previous)


def pack(**kwargs):
    return L.CountryPack(code="jp", name="Japan", region_command="asia", currency="JPY",
                         executable_instruments=("USDJPY",), **kwargs)


def tape(symbol="USDJPY", days=100):
    times = np.arange(np.datetime64("2025-01-01T00"),
                      np.datetime64("2025-01-01T00") + np.timedelta64(days * 24, "h"),
                      np.timedelta64(1, "h"))
    hours = np.arange(times.size) % 24
    increments = np.where((hours >= 7) & (hours < 15), .003, -.0001)
    close = 100 * np.exp(np.cumsum(increments))
    return L.Bars(symbol, "H1", times.astype("datetime64[ns]"), close,
                  volume=np.ones(times.size), spread=np.ones(times.size))


def test_every_generic_miner_names_absent_inputs_without_inventing_success(rig):
    ctx = L.LabCtx("jp", conn=rig, dry_run=True, bars_loader=lambda *args: None)
    doc = L.run_lab(pack(), ctx, budget_s=60)
    assert len(doc["miners"]) == 15
    assert not any(row["outcome"] == L.FAILED for row in doc["miners"])
    assert all(row["outcome"] == L.UNMEASURED for row in doc["miners"])
    assert doc["domestic"] == 0
    assert len(doc["unmeasured"]) >= 10
    assert ctx.miner == ""


def test_real_session_study_records_controlled_card_with_country_provenance(rig):
    p = pack(session_windows=(L.SessionWindow("local", "07:00", "15:00"),))
    ctx = L.LabCtx("jp", region_command="asia", miner="session_microstructure", conn=rig,
                   bars_loader=lambda symbol, timeframe: tape(symbol))
    result = L.generic_session_microstructure(p, ctx)
    assert result["outcome"] == L.OK
    assert result["discoveries"] == 1
    assert result["readings"][0]["abs_ratio"] > 1.2
    row = R.discoveries(limit=10, conn=rig)[0]
    assert row["generator"] == "jp:session_microstructure"
    assert row["source_id"].startswith("jp:")
    assert json.loads(row["payload_json"])["country"] == "jp"
    assert "outside the window" in json.loads(row["payload_json"])["reading"]["controls"][0]


def test_event_study_uses_distinct_dates_and_matched_controls():
    bars = tape(days=100)
    dates = np.arange(np.datetime64("2025-01-01"), np.datetime64("2025-04-01"),
                      np.timedelta64(7, "D"))
    measured = L.event_effect(bars, dates, n_perm=40,
                             eras={"all": np.ones(len(bars), dtype=bool),
                                   "empty": np.zeros(len(bars), dtype=bool)})
    assert measured["verdict"] == "MEASURED"
    assert measured["n_event_days"] == len(dates)
    assert measured["p_perm"] >= round(1 / 41, 6)
    assert measured["eras"]["empty"]["diff"] is None
    poor = L.event_effect(bars, dates[:1])
    assert poor["verdict"] == "POORLY_MEASURED"
    assert "distinct event" in poor["why"]
    no_control = L.event_effect(bars, np.unique(L.bar_days(bars)))
    assert "control" in no_control["why"]
    no_event = L.event_effect(bars, np.array([], dtype="datetime64[D]"))
    assert no_event["n_events"] == 0
    assert L.event_effect(tape(days=1), dates)["verdict"] == "POORLY_MEASURED"


@pytest.mark.parametrize("roll,expected", [("previous", "2025-01-03"),
                                          ("next", "2025-01-06"), ("none", None)])
def test_settlement_calendar_moves_off_own_closures(roll, expected):
    p = pack(holidays_rule=L.HolidayRule(weekly_closed=(5, 6)))
    dates = L.settlement_days(L.SettlementRule(days=(5,), roll=roll), p,
                             np.datetime64("2025-01-01"), np.datetime64("2025-01-10"))
    assert dates.astype(str).tolist() == ([] if expected is None else [expected])


@pytest.mark.parametrize("rule,expected", [
    (L.SettlementRule(kind="month_end", roll="none"), ["2025-01-31"]),
    (L.SettlementRule(kind="quarter_end"), []),
    (L.SettlementRule(kind="fiscal_year_end"), ["2025-01-31"]),
    (L.SettlementRule(kind="fiscal_quarter_end"), ["2025-01-31"]),
    (L.SettlementRule(kind="week_of_month", weekday=0, week_of_month=2), ["2025-01-13"]),
    (L.SettlementRule(kind="unknown"), []),
])
def test_calendar_rules_have_independent_expected_dates(rule, expected):
    p = pack(fiscal_year_end="01-31", holidays_rule=L.HolidayRule(weekly_closed=()))
    dates = L.settlement_days(rule, p, np.datetime64("2025-01-01"),
                             np.datetime64("2025-01-31"))
    assert dates.astype(str).tolist() == expected


def test_loader_failures_are_cached_named_and_do_not_manufacture_series():
    calls = []
    def unavailable(*args):
        calls.append(args)
        raise OSError("private fixture absent")
    ctx = L.LabCtx("jp", bars_loader=unavailable, series_loader=unavailable)
    assert ctx.bars("usdjpy") is None
    assert ctx.bars("USDJPY") is None
    assert ctx.series("policy_rate") is None
    assert ctx.series("policy_rate") is None
    assert ctx.series("") is None
    assert len(calls) == 2
    assert len(ctx.unmeasured) == 2
    assert all("private fixture absent" in reason for reason in ctx.unmeasured)


def test_price_kernel_never_zero_fills_unavailable_future_observations():
    close = np.array([100., 110., 0., np.nan, 121.])
    assert L.log_returns(close).tolist() == pytest.approx([0, np.log(1.1), 0, 0, 0])
    forward = L.forward_returns(close)
    assert forward[0] == pytest.approx(np.log(1.1))
    assert np.isnan(forward[1:]).all()
    assert np.isnan(L.forward_returns(close, 10)).all()
    assert L.permutation_p(1, np.array([])) == 1
    assert L.permutation_p(np.nan, np.array([1.])) == 1
    assert L.corr_with_null(np.ones(40), np.ones(40), n_perm=20)["p_perm"] == 1
    assert L.corr_with_null(np.ones(2), np.ones(2))["verdict"] == "POORLY_MEASURED"


def test_failure_descendants_require_a_justified_operator(rig, monkeypatch):
    monkeypatch.setattr(R, "candidates", lambda **kwargs: [
        {"id": "wrong", "symbol": "USDJPY", "failure_class": "wrong_direction"},
        {"id": "barren", "symbol": "USDJPY", "failure_class": "no_edge"},
        {"id": "foreign", "symbol": "AUDNZD", "failure_class": "cost_killed"}])
    ctx = L.LabCtx("jp", miner="failure", conn=rig)
    result = L.generic_failure(pack(), ctx)
    assert result["judged_rows"] == 2
    assert result["barren"] == 1
    assert result["discoveries"] == 1
    row = R.discoveries(limit=10, conn=rig)[0]
    assert json.loads(row["payload_json"])["operator"] == "INVERSE"
    assert json.loads(row["payload_json"])["parent"] == "wrong"


def test_custom_miner_failure_is_named_and_context_is_restored(rig):
    def broken(p, ctx):
        raise ValueError("bad research input")
    ctx = L.LabCtx("jp", miner="original", conn=rig, dry_run=True)
    result = L.run_lab(pack(), ctx, budget_s=60, extra={"broken": broken})
    row = next(row for row in result["miners"] if row["miner"] == "custom:broken")
    assert row["outcome"] == L.FAILED
    assert "bad research input" in row["why"]
    assert ctx.miner == "original"


def test_residual_delegation_filters_country_and_preserves_original_row(rig, monkeypatch):
    module = SimpleNamespace(residual_inputs=lambda: {
        "measured": [{"sym": "USDJPY", "residual": 2}, {"sym": "AUDNZD", "residual": 8}]})
    monkeypatch.setattr(L, "desk_module", lambda name: module)
    ctx = L.LabCtx("jp", miner="residual", conn=rig)
    result = L.generic_residual(pack(), ctx)
    assert result["rows"] == 1
    assert json.loads(R.discoveries(limit=10, conn=rig)[0]["payload_json"])["row"]["residual"] == 2


def test_budgeted_run_never_calls_miners_after_deadline(rig):
    ctx = L.LabCtx("jp", conn=rig, dry_run=True)
    result = L.run_lab(pack(), ctx, budget_s=0)
    assert all(row["outcome"] == L.SKIPPED for row in result["miners"])


def test_real_miner_budget_keeps_cold_ground_and_fixed_costs():
    result = L.miner_budgets(["calendar", "cold", "warm"], 90,
                            [{"generator": "jp:warm", "generated": 10,
                              "independent_survivors": 10}], "jp:", fixed=("calendar",))
    assert sum(row["weight"] for row in result.values()) == pytest.approx(1, abs=2e-6)
    assert result["cold"]["weight"] > 0
    assert result["calendar"]["fixed"]
    assert result["warm"]["budget_s"] > result["cold"]["budget_s"]
    assert L.miner_budgets([], 90, [], "jp:") == {}


def test_measured_miner_cards_reach_registry_with_causal_and_pit_requirements(rig, monkeypatch):
    # Unit-test the measurement-to-card boundary with controlled measurement results.
    # Separate tests above exercise the actual event, null and price kernels.
    reading = {"verdict": "MEASURED", "significant": True, "abs_ratio": 1.5,
               "diff": .1, "p_perm": .01, "corr": .8, "n": 100,
               "controls": ["matched dates", "circular block null"]}
    monkeypatch.setattr(L, "event_effect", lambda *args, **kwargs: dict(reading))
    monkeypatch.setattr(L, "corr_with_null", lambda *args, **kwargs: dict(reading))
    monkeypatch.setattr(L, "window_effect", lambda *args, **kwargs: dict(reading))
    dates = tuple(f"2025-01-{day:02d}" for day in (6, 13, 20, 27))
    series = L.DataSeries("known", np.arange(np.datetime64("2025-01-01"),
                                            np.datetime64("2025-04-11")), np.arange(100.))
    monkeypatch.setattr(L, "cot_series", lambda key: series)
    p = pack(
        central_bank=L.CentralBank("BOJ", "inflation_targeter", dates,
                                  policy_rate_series="domestic", expected_rate_series="expected"),
        release_classes=(L.ReleaseClass("CPI", dates=dates, source="official"),),
        settlement_conventions=(L.SettlementRule("settle", days=(5, 10)),),
        fixing_conventions=(L.Fixing("fix", "09:00"),),
        holidays_rule=L.HolidayRule(dates=("2025-01-13",)),
        session_windows=(L.SessionWindow("cash", "07:00", "15:00"),),
        exchanges=(L.Exchange("local", ("US500",), expiry_dates=dates,
                              open_utc="07:00", close_utc="15:00"),),
        cot_currency="JPY", institutional_flow_sources=("public pension",),
        native_languages=("ja",), terminology={"flows": ("決済",)},
        series={"policy_rate": "domestic", "foreign_policy_rate": "foreign",
                "exports": "exports"},
        policy_eras=(L.Era("current", "2025-01-01", "2025-04-10"),),
    )
    ctx = L.LabCtx("jp", conn=rig, bars_loader=lambda symbol, timeframe: tape(symbol),
                   series_loader=lambda name: series)
    report = L.run_lab(p, ctx, budget_s=120)
    assert not any(row["outcome"] == L.FAILED for row in report["miners"])
    assert report["domestic"] >= 12
    rows = R.discoveries(limit=100, conn=rig)
    measured = [row for row in rows if "scout" not in row["generator"]]
    assert all(row["generator"].startswith("jp:") for row in rows)
    assert all(row["created_at"] for row in rows)
    assert all(row["actor"] and row["constraint_text"] and row["falsifier"]
               for row in measured)
    assert all(json.loads(row["pit_requirements_json"]) for row in measured)
    assert report["transmission_seeds"]


def test_parquet_loader_is_private_and_refuses_invalid_estate(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(L, "BARS_DIR", tmp_path)
    assert L.default_bars_loader("USDJPY") is None
    target = tmp_path / "USDJPY_H1.parquet"
    target.write_text("invalid")
    assert L.default_bars_loader("USDJPY") is None
    pd.DataFrame({"wrong": [1]}).to_parquet(target)
    assert L.default_bars_loader("USDJPY") is None
    index = pd.date_range("2025-01-01", periods=3, freq="h", tz="Europe/Berlin")
    pd.DataFrame({"close": [100., 101., 102.], "high": [101., 102., 103.],
                  "tick_volume": [3, 4, 5]}, index=index).to_parquet(target)
    loaded = L.default_bars_loader("usdjpy")
    assert loaded.symbol == "USDJPY"
    assert loaded.times[0] == np.datetime64("2024-12-31T23:00:00")
    assert loaded.volume.tolist() == [3, 4, 5]
    assert loaded.low is None


def test_cot_loader_uses_publication_clock_not_reference_date(tmp_path, monkeypatch):
    path = tmp_path / "cot.json"
    monkeypatch.setattr(L, "COT_JSON", path)
    assert L.cot_series("USDJPY") is None
    path.write_text(json.dumps({"rows": [
        {"symbol": "USDJPY", "knowable_at": "2025-01-10", "as_of": "2025-01-07",
         "net_pct_oi": 2},
        {"symbol": "USDJPY", "knowable_at": "invalid", "net_pct_oi": 999},
        {"symbol": "AUDNZD", "knowable_at": "2025-01-01", "net_pct_oi": 100}]}))
    series = L.cot_series("usdjpy")
    assert series.dates.astype(str).tolist() == ["2025-01-10"]
    assert series.values.tolist() == [2]


def test_custom_declaration_cannot_pass_as_measured_evidence(rig):
    p = pack(
        domains=({"id": "flow", "title": "forced flow", "objects": ("dated releases",),
                  "controls": ("matched non-event days",)},),
        custom_miners=("absent_country_module:flow",),
        custom_miner_specs=({"entry": "absent_country_module:flow", "name": "flow",
                             "domain_ids": ("flow",), "kind": "event"},))
    functions, problems = L.load_custom_miners(p)
    assert "DECLARED_SPEC_ADAPTER" in problems[0]
    ctx = L.LabCtx("jp", conn=rig, miner="custom:flow")
    result = functions["custom:flow"](p, ctx)
    assert result["discoveries"] == 1
    payload = json.loads(R.discoveries(limit=10, conn=rig)[0]["payload_json"])
    assert payload["status"] == "HYPOTHESIS_ONLY_NOT_MEASURED"
    assert payload["implementation"] == "DECLARED_SPEC_ADAPTER"
    assert "publication" in json.loads(
        R.discoveries(limit=10, conn=rig)[0]["pit_requirements_json"])[0]


def test_normalized_pack_copy_retains_lossless_miner_declaration():
    from dataclasses import replace

    spec = {"entry": "absent_country_module:flow", "name": "flow", "domain_ids": ("flow",),
            "kind": "event", "negative_controls": ("matched days",)}
    original = pack(custom_miners=(spec,))
    copied = replace(original, name="Same country, revised label")
    assert copied.custom_miner_specs == original.custom_miner_specs
    assert copied.custom_miner_specs[0]["negative_controls"] == ("matched days",)
    assert copied.custom_miners == ("absent_country_module:flow",)
    assert copied.miner_domains["flow"] == ("flow",)
