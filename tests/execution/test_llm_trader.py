"""R0122 LLM discretionary sleeve -- paper only, mechanism-gated, self-scoring."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_llm_trader import (MAX_PROB, MIN_PROB, build_brief, parse_call, record_call,
                                    validate_call)


def _call(**kw):
    base = {"action": "CALL", "symbol": "BTCUSDT", "direction": "LONG", "horizon_hours": 8,
            "probability": 0.62,
            "mechanism": "the venue raised the contract's maintenance margin, so leveraged "
                         "shorts must post collateral or close, forcing buying into the change",
            "falsifier": "open interest does not fall after the spec change"}
    base.update(kw)
    return base


def test_a_good_call_is_accepted():
    ok, why = validate_call(_call())
    assert ok and why == "accepted"


def test_pass_is_first_class():
    ok, why = validate_call({"action": "PASS"})
    assert ok and "no edge" in why


def test_chart_pattern_is_refused_as_a_mechanism():
    # The 420/0 lesson enforced at write time: a pattern is not a mechanism.
    ok, why = validate_call(_call(mechanism="clean breakout above resistance with strong volume"))
    assert not ok and "PATTERN" in why


def test_missing_falsifier_refused():
    ok, why = validate_call(_call(falsifier="no"))
    assert not ok and "falsifier" in why


def test_probability_bounds_enforced():
    for p in (0.30, 0.99):
        ok, why = validate_call(_call(probability=p))
        assert not ok and "probability" in why
    assert validate_call(_call(probability=MIN_PROB))[0]
    assert validate_call(_call(probability=MAX_PROB))[0]


def test_thin_mechanism_refused():
    ok, why = validate_call(_call(mechanism="funding is high"))
    assert not ok and "mechanism" in why


def test_call_is_logged_as_a_scored_forecast(tmp_path, monkeypatch):
    # The whole point: every call is a pre-registered forecast the calibration fence scores.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    row = record_call(tmp_path, _call())
    assert row["paper"] is True and "resolve_by" in row
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert any(k.startswith("llm_trader:") for k in logged)
    entry = next(v for k, v in logged.items() if k.startswith("llm_trader:"))
    assert entry["p"] == 0.62 and entry["resolve_by"]      # scored, with a deadline


def test_brief_reports_absent_feeds_rather_than_empty(tmp_path):
    b = build_brief(tmp_path)
    assert all(v == "ABSENT on this host" for v in b["sources"].values())


def test_parse_tolerates_prose_around_json():
    assert parse_call('Sure!\n{"action": "PASS"}\nDone')["action"] == "PASS"
    assert parse_call("no json here") is None


def test_it_places_no_orders_and_imports_no_connector():
    src = Path("scripts/run_llm_trader.py").read_text("utf-8")
    for banned in ("binance_live", "place_order", "place_market", "place_post_only",
                   "flatten_all", "cancel_all"):
        assert banned not in src
    assert "PAPER ONLY" in src
