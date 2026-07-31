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
            "falsifier": "open interest does not fall after the spec change",
            # required since the 2026-07-31 hardening: a call must name its mechanism FAMILY
            # (so families can be retired on evidence) and WHO is forced to transact.
            "mechanism_class": "COLLATERAL_CHANGE",
            "forced_participant": "LEVERAGED_SHORTS"}
    base.update(kw)
    return base


def test_a_good_call_is_accepted():
    ok, why = validate_call(_call())
    assert ok and why == "accepted"


def test_pass_is_first_class_but_must_be_justified():
    # Superseded by the 2026-07-31 hardening: PASS is still first-class, but a BARE pass is now
    # refused, because scoring calibration alone rewards passing on everything.
    ok, why = validate_call({"action": "PASS", "pass_reason": "nothing requiring prose to read"})
    assert ok and "scored" in why


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


# --- external-critique hardening (2026-07-31) --------------------------------------------------

def _full(**kw):
    # kw must be able to OVERRIDE the defaults -- passing them positionally duplicated the
    # keyword and raised TypeError, which read as a validator failure rather than a helper bug.
    base = {"mechanism_class": "COLLATERAL_CHANGE", "forced_participant": "LEVERAGED_SHORTS"}
    base.update(kw)
    return _call(**base)


def test_pass_must_justify_itself():
    """THE PASS-OPTIMISATION TRAP: a model that passes on everything earns a perfect calibration
    score and contributes nothing. Scoring calibration alone creates an incentive to pass."""
    from scripts.run_llm_trader import validate_call
    ok, why = validate_call({"action": "PASS"})
    assert not ok and "farms a clean Brier score" in why
    ok, why = validate_call({"action": "PASS", "pass_reason": "already priced by the open"})
    assert ok and "scored" in why


def test_mechanism_must_come_from_the_controlled_taxonomy():
    # Free text cannot be AGGREGATED, so weak mechanism families never get retired.
    from scripts.run_llm_trader import MECHANISMS, validate_call
    assert validate_call(_full())[0]
    ok, why = validate_call(_full(mechanism_class="something novel"))
    assert not ok and "unmeasurable" in why
    assert "FORCED_LIQUIDATION" in MECHANISMS and len(MECHANISMS) >= 8


def test_a_call_with_nobody_forced_is_a_view_not_a_mechanism():
    from scripts.run_llm_trader import validate_call
    ok, why = validate_call(_full(forced_participant="NOBODY_FORCED"))
    assert not ok and "that is a VIEW" in why


def test_forced_participant_is_required_and_enumerated():
    from scripts.run_llm_trader import PARTICIPANTS, validate_call
    assert "MARKET_MAKERS" in PARTICIPANTS and "LEVERAGED_LONGS" in PARTICIPANTS
    ok, _ = validate_call(_full(forced_participant="whoever"))
    assert not ok


def test_brief_asks_for_compressibility():
    # If a simple IF-THEN rule reproduces the call, the desk should replace the LLM with code.
    from scripts.run_llm_trader import _CALL_BRIEF
    b = " ".join(_CALL_BRIEF.split())
    assert "compressible" in b
    assert "replace you with" in b
    assert "passed_on" in b and "pass_reason" in b
