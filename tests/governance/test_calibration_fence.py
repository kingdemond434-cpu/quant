"""L1.29 calibration fence -- the desk scores its own confidence, or its confidence is fiction."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.self_improvement import forecast_calibration as fc


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "_LOG", tmp_path / "forecast_log.json")
    return tmp_path


def test_overdue_flags_ungraded_predictions(store):
    past = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    fc.log_forecast("alpha:x", 0.7, "alpha_survival", resolve_by=past, claim="x survives 30d")
    fc.log_forecast("alpha:y", 0.6, "alpha_survival",
                    resolve_by=(datetime.now(tz=UTC) + timedelta(days=9)).isoformat())
    od = fc.overdue()
    assert [o["key"] for o in od] == ["alpha:x"]      # future deadline is not overdue


def test_resolved_forecast_is_never_overdue(store):
    past = (datetime.now(tz=UTC) - timedelta(days=2)).isoformat()
    fc.log_forecast("k", 0.8, "alpha_survival", resolve_by=past)
    fc.resolve("k", outcome=True)
    assert fc.overdue() == []


def test_shrinkage_withheld_below_five_outcomes(store):
    fc.log_forecast("a", 0.9, "eng")
    fc.resolve("a", outcome=False)
    adj = fc.calibrated_confidence(0.9)
    assert adj["applied"] is False
    assert adj["adjusted"] == 0.9                    # noise-based correction is worse than none
    assert "insufficient" in adj["why"]


def test_overconfident_desk_gets_shrunk(store):
    # Five forecasts at p=0.9 that all FAILED -> bias +0.9, wildly over-confident.
    for i in range(5):
        fc.log_forecast(f"f{i}", 0.9, "alpha_survival")
        fc.resolve(f"f{i}", outcome=False)
    rep = fc.report()
    assert rep["bias_label"] == "over-confident"
    adj = fc.calibrated_confidence(0.8)
    assert adj["applied"] is True
    assert adj["adjusted"] < 0.8                     # the loop is CLOSED, not merely reported
    assert adj["adjusted"] >= 0.0                    # and clamped


def test_underconfident_desk_gets_raised(store):
    for i in range(5):
        fc.log_forecast(f"g{i}", 0.2, "alpha_survival")
        fc.resolve(f"g{i}", outcome=True)
    assert fc.report()["bias_label"] == "under-confident"
    adj = fc.calibrated_confidence(0.5)
    assert adj["adjusted"] > 0.5                     # timid confidence is corrected UPWARD too


def test_zero_forecasts_is_unforecasting_not_ok(store):
    import importlib
    cc = importlib.import_module("scripts.check_calibration")
    rep = cc.build_report()
    assert rep["status"] == "UNFORECASTING"           # never "OK" -- unmeasured counts as zero


def test_law_and_wiring_present():
    const = " ".join(Path("docs/CONSTITUTION.md").read_text("utf-8").replace("**", "").split())
    assert "L1.29 THE DESK SCORES ITS OWN CONFIDENCE" in const
    assert "L1.29" in Path("ops/principal_doctrine.txt").read_text("utf-8")
    assert '"L1.29"' in Path("scripts/build_enforcement_matrix.py").read_text("utf-8")
    assert "check_calibration.py" in Path("ops/crontab.manifest").read_text("utf-8")
    assert "calibration_debt" in Path("scripts/run_max_push.py").read_text("utf-8")
