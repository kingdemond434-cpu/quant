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


_SOON = (datetime.now(tz=UTC) + timedelta(days=30)).isoformat()


def test_overconfident_desk_gets_shrunk(store):
    # Five PRE-REGISTERED forecasts at p=0.9 that all FAILED -> bias +0.9, wildly over-confident.
    for i in range(5):
        fc.log_forecast(f"f{i}", 0.9, "alpha_survival", resolve_by=_SOON, claim=f"claim {i}")
        fc.resolve(f"f{i}", outcome=False)
    rep = fc.report()
    assert rep["bias_label"] == "over-confident"
    adj = fc.calibrated_confidence(0.8)
    assert adj["applied"] is True
    assert adj["adjusted"] < 0.8                     # the loop is CLOSED, not merely reported
    assert adj["adjusted"] >= 0.0                    # and clamped


def test_underconfident_desk_gets_raised(store):
    for i in range(5):
        fc.log_forecast(f"g{i}", 0.2, "alpha_survival", resolve_by=_SOON, claim=f"g claim {i}")
        fc.resolve(f"g{i}", outcome=True)
    assert fc.report()["bias_label"] == "under-confident"
    adj = fc.calibrated_confidence(0.5)
    assert adj["adjusted"] > 0.5                     # timid confidence is corrected UPWARD too


def test_retrospective_self_assessment_is_not_scoreable(store):
    """L1.29(a): a probability without a pre-committed resolve_by was graded AFTER the fact.

    The live store held 30 such rows -- all kind=engineering, ALL outcome=1.0, resolved a median
    of 18ms after being logged. Scoring them inverted the measured bias from +0.176 (over) to
    -0.146 (under), and run_conviction_trader fed that straight into kelly_leverage."""
    for i in range(30):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")     # no resolve_by == not a forecast
        fc.resolve(f"eng:{i}", outcome=True)
    rep = fc.report()
    assert rep["n_resolved"] == 0
    assert rep["n_excluded"]["retrospective"] == 30
    assert rep["bias"] is None                              # nothing scoreable -> no correction
    assert fc.calibrated_confidence(0.44)["applied"] is False


def test_duplicate_claims_count_once(store):
    """A re-asked question is not a second observation. The probe organ re-logged one identical
    S2USDT claim 17 times in 14h at a frozen threshold; all resolve on the same print, so scoring
    them as 17 would clear the n>=5 noise gate on arithmetically ONE coin flip."""
    for i in range(17):
        fc.log_forecast(f"probe:{i}", 0.61, "calibration_probe", resolve_by=_SOON,
                        claim="Will S2USDT trade ABOVE 102.0 in 24 hours' time?")
        fc.resolve(f"probe:{i}", outcome=True)
    rep = fc.report()
    assert rep["n_resolved"] == 1                           # 17 copies == 1 observation
    assert rep["n_excluded"]["duplicate_claim"] == 16
    assert rep["bias"] is None                              # 1 < 5 -> correction still withheld


def test_inverted_bias_does_not_manufacture_edge(store):
    """The end-to-end regression: retrospective rows must never flip the SIGN of the correction.

    30 instant self-graded TRUEs alongside 5 genuine pre-registered forecasts that mostly missed.
    Pooling everything reports 'under-confident' and RAISES probabilities; only the pre-registered
    subset is scoreable, which reports 'over-confident' and shrinks them."""
    for i in range(30):
        fc.log_forecast(f"eng:{i}", 0.9, "engineering")
        fc.resolve(f"eng:{i}", outcome=True)
    for i, out in enumerate([False, False, False, True, False]):
        fc.log_forecast(f"real:{i}", 0.6, "market_direction", resolve_by=_SOON,
                        claim=f"real claim {i}")
        fc.resolve(f"real:{i}", outcome=out)
    rep = fc.report()
    assert rep["n_resolved"] == 5
    assert rep["bias"] > 0 and rep["bias_label"] == "over-confident"
    # a marginal call must be pushed AWAY from the edge boundary, never across it
    assert fc.calibrated_confidence(0.44)["adjusted"] < 0.44


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
