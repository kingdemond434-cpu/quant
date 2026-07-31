"""R0142 calibration probe -- does the model's stated probability mean anything at all?

The whole discretionary sizer consumes one number. Checked 2026-07-31, the desk had ZERO resolved
forecasts: the most consequential input to the money path had never been scored on anything.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.run_calibration_probe import (MIN_FOR_VERDICT, UNINFORMATIVE_BRIER, build_questions,
                                           pose, resolve_due, verdict)


def _charts(tmp_path, price=100.0, n=3):
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/chart_context.json").write_text(json.dumps({"charts": {
        f"S{i}USDT": {"state": "OK", "timeframes": {"15m": {"state": "OK", "price": price + i}}}
        for i in range(n)}}))


def test_questions_are_only_posed_if_they_can_later_be_resolved(tmp_path):
    # A question that cannot be scored is not a test, it is decoration.
    assert build_questions(tmp_path) == []
    assert pose(tmp_path)["status"] == "NO-QUESTIONS"
    _charts(tmp_path)
    qs = build_questions(tmp_path, n=3)
    assert len(qs) == 3
    assert all(q["ref_price"] and q["horizon_h"] and q["symbol"] for q in qs)


def test_an_unparseable_or_out_of_range_answer_is_discarded(tmp_path):
    _charts(tmp_path)
    assert pose(tmp_path, ask=lambda _p: "I decline")["status"] == "NO-ANSWER"
    # probabilities outside (0,1) are dropped rather than clamped -- a clamp invents a forecast
    r = pose(tmp_path, ask=lambda _p: '{"q1": 1.5, "q2": 0.0, "q3": 0.61}')
    assert r["status"] == "POSED" and r["n"] == 1


def test_a_posed_question_is_logged_for_scoring(tmp_path, monkeypatch):
    _charts(tmp_path)
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    r = pose(tmp_path, ask=lambda _p: '{"q1": 0.61, "q2": 0.44, "q3": 0.55}')
    assert r["n"] == 3
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert len([k for k in logged if k.startswith("probe:")]) == 3


def test_a_question_whose_price_cannot_be_fetched_stays_open(tmp_path, monkeypatch):
    # UNRESOLVABLE must never be guessed into a score -- that would inject noise as evidence.
    _charts(tmp_path)
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    pose(tmp_path, ask=lambda _p: '{"q1": 0.61, "q2": 0.44, "q3": 0.55}')
    past = datetime.now(tz=UTC) + timedelta(hours=48)
    r = resolve_due(tmp_path, now=past, fetch=lambda *a, **k: ([], "venue down"))
    assert r["n_resolved"] == 0 and r["still_open"] == 3


def test_a_due_question_is_scored_from_real_bars(tmp_path, monkeypatch):
    _charts(tmp_path, price=100.0)
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    pose(tmp_path, ask=lambda _p: '{"q1": 0.61, "q2": 0.44, "q3": 0.55}')
    bars = [(0, 0, 0, 0, 999.0)]                       # closed far above every ref price
    r = resolve_due(tmp_path, now=datetime.now(tz=UTC) + timedelta(hours=48),
                    fetch=lambda *a, **k: (bars, "test"))
    assert r["n_resolved"] == 3 and r["still_open"] == 0
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert all(f["outcome"] == 1.0 for f in logged.values() if f.get("resolved"))


def test_no_verdict_before_the_sample_exists(monkeypatch):
    import scripts.run_calibration_probe as probe
    monkeypatch.setattr("libs.self_improvement.forecast_calibration.report",
                        lambda: {"n_resolved": 4, "brier": None})
    v = probe.verdict()
    assert v["state"] == "ACCUMULATING" and "must not read as one" in v["why"]


def test_an_uninformative_forecaster_says_remove_the_sizer(monkeypatch):
    # THE POINT. If p is noise, Kelly is not aggressive or conservative -- it is arbitrary, and
    # sizing on a meaningless number is strictly worse than not sizing on it.
    monkeypatch.setattr("libs.self_improvement.forecast_calibration.report",
                        lambda: {"n_resolved": MIN_FOR_VERDICT + 5, "brier": 0.26, "bias": 0.0})
    v = verdict()
    assert v["state"] == "UNINFORMATIVE" and "REMOVE the Kelly sizer" in v["why"]


def test_an_informative_forecaster_justifies_kelly(monkeypatch):
    monkeypatch.setattr("libs.self_improvement.forecast_calibration.report",
                        lambda: {"n_resolved": MIN_FOR_VERDICT + 5, "brier": 0.18, "bias": 0.03})
    v = verdict()
    assert v["state"] == "INFORMATIVE" and v["brier"] < UNINFORMATIVE_BRIER
