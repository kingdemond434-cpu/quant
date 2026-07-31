"""R0125 conviction sleeve -- aggression uncapped, ruin capped, and paper-only."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.run_conviction_trader import (MAX_LEVERAGE, MAX_RISK_PER_TRADE, kelly_leverage,
                                           record, validate)


def _t(**kw):
    base = {"action": "TRADE", "symbol": "PAXGUSDT", "direction": "SHORT", "probability": 0.63,
            "expected_move_pct": 4.0, "stop_pct": 2.0, "horizon_hours": 12,
            "driver": "DXY strength and overbought gold into a known resistance shelf",
            "falsifier": "gold breaks and holds above the shelf on rising volume"}
    base.update(kw)
    return base


def test_a_real_edge_produces_real_leverage():
    # The whole point: an honest 60%+ call with a tight stop is meant to be BIG (the screenshot's
    # ~8x), not shrunk to nothing.
    s = kelly_leverage(0.63, 4.0 / 2.0, 2.0)
    assert s["leverage"] > 2.0                     # genuinely aggressive
    assert s["capped_by"] in ("kelly", "max_leverage", "max_risk")


def test_leverage_is_hard_capped():
    # Aggression uncapped, RUIN capped -- a wildly confident call cannot exceed the ceiling.
    s = kelly_leverage(0.90, 10.0 / 0.5, 0.5)
    assert s["leverage"] <= MAX_LEVERAGE
    assert s["risk_fraction"] <= MAX_RISK_PER_TRADE


def test_no_edge_means_no_size():
    s = kelly_leverage(0.50, 1.0, 2.0)             # coin flip, no edge
    assert s["leverage"] == 0.0 and s["capped_by"] == "no-edge"


def test_a_trade_with_no_stop_is_refused():
    # The rail the manual account lacked (L1.23).
    ok, why = validate(_t(stop_pct=100.0))
    assert not ok and "real stop" in why


def test_negative_ev_reward_risk_refused():
    ok, why = validate(_t(expected_move_pct=1.0, stop_pct=2.0))   # risking 2 to make 1
    assert not ok and "reward:risk" in why


def test_overconfidence_bound():
    ok, why = validate(_t(probability=0.97))
    assert not ok and "probability" in why


def test_good_trade_accepted_and_sized_and_scored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    row = record(tmp_path, _t())
    assert row["paper"] is True and row["sizing"]["leverage"] > 0
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert any(k.startswith("conviction:") for k in logged)     # scored like everything else


def test_pass_must_justify():
    assert not validate({"action": "PASS"})[0]
    assert validate({"action": "PASS", "pass_reason": "no directional edge, chop"})[0]


def test_places_no_orders():
    src = Path("scripts/run_conviction_trader.py").read_text("utf-8")
    for banned in ("binance_live", "place_order", "place_market", "place_post_only"):
        assert banned not in src
    assert "PAPER ONLY" in src
