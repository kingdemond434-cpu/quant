"""R0142 calibration probe -- does the model's stated probability mean anything at all?

The whole discretionary sizer consumes one number. Checked 2026-07-31, the desk had ZERO resolved
forecasts: the most consequential input to the money path had never been scored on anything.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from scripts.run_calibration_probe import (
    MIN_FOR_VERDICT,
    UNINFORMATIVE_BRIER,
    build_questions,
    pose,
    resolve_due,
    verdict,
)


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


def test_a_test_root_never_reaches_the_live_calibration_store(tmp_path, monkeypatch):
    """R0254. THE TEST SUITE WAS THE EXTRA CALLER, and this is the test that catches it.

    `pose()` honoured its `root` for the questions file and logged the forecast through the
    calibration module's global path, so the case above -- which passes no monkeypatch, because
    it is asserting parsing, not storage -- wrote one fabricated row into the desk's live L1.29
    store on every single run. Measured on 2026-08-05 before the fix: 68 such rows, and ALL 44
    forecasts holding the calibration fence OVERDUE were this exact fixture (S2USDT @ 102.0,
    p=0.61 -- `_charts` names symbols `S{i}USDT` at price `100.0 + i`, and 0.61 is the literal
    two lines up). They can never be graded: no venue lists S2USDT, so `resolve_due` correctly
    refuses to guess and they sit past-due forever, pinning red the one fence that exists to
    detect the desk being confidently wrong.

    The assertion is deliberately about the DEFAULT store rather than about this one test: what
    failed was not a missing monkeypatch, it was isolation that depended on every future caller
    remembering one.
    """
    import libs.self_improvement.forecast_calibration as fc
    live = tmp_path / "live_store.json"
    monkeypatch.setattr(fc, "_LOG", live)
    _charts(tmp_path)
    r = pose(tmp_path, ask=lambda _p: '{"q1": 0.61, "q2": 0.44, "q3": 0.55}')
    assert r["n"] == 3 and not r.get("calibration_log_error")
    assert not live.exists(), f"pose() wrote to the module-global store: {live.read_text()}"
    logged = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert len([k for k in logged if k.startswith("probe:")]) == 3


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


# ---- retiring a question the world cannot answer, without handing the desk an escape hatch ----
#
# R0394. "UNRESOLVABLE stays open, never guessed" is right about the OUTCOME and was the wrong
# TERMINUS: with no terminal state the row is retried forever, ages past its deadline, and holds
# the L1.29 fence OVERDUE until a human edits the store by hand -- which is exactly what the 44
# S2USDT rows did. A fence that can never go green gets ignored, and this is the fence that
# detects the desk being confidently wrong. Delisting reaches the same weld with nobody at fault.


def _posed(tmp_path, monkeypatch):
    _charts(tmp_path)
    import libs.self_improvement.forecast_calibration as fc
    monkeypatch.setattr(fc, "_LOG", tmp_path / "data/forecast_log.json")
    pose(tmp_path, ask=lambda _p: '{"q1": 0.61, "q2": 0.44, "q3": 0.55}')
    return fc


def _dead_venue(*a, **k):
    return ([], "venue down")


def test_a_sustained_outage_past_the_grace_finally_retires_the_question(tmp_path, monkeypatch):
    """The weld broken. Three separate runs, all unpriceable, all well past the deadline."""
    fc = _posed(tmp_path, monkeypatch)
    late = datetime.now(tz=UTC) + timedelta(hours=72)
    for _ in range(2):
        assert resolve_due(tmp_path, now=late, fetch=_dead_venue)["n_voided"] == 0
    r = resolve_due(tmp_path, now=late, fetch=_dead_venue)
    assert r["n_voided"] == 3 and r["still_open"] == 0
    assert fc.overdue() == [], "the fence can now go green honestly"


def test_a_BRIEF_outage_never_retires_a_real_forecast(tmp_path, monkeypatch):
    """The risk this state creates, and the reason for two independent conditions. If a venue
    blip could void a forecast, the desk would have an escape hatch from grading itself -- the
    exact opposite of what L1.29 is for."""
    _posed(tmp_path, monkeypatch)
    late = datetime.now(tz=UTC) + timedelta(hours=72)
    r = resolve_due(tmp_path, now=late, fetch=_dead_venue)
    assert r["n_voided"] == 0 and r["still_open"] == 3


def test_attempts_alone_do_not_retire_a_question_inside_the_grace(tmp_path, monkeypatch):
    """The other half of the conjunction: a busy cron must not burn through the attempt budget in
    the first hour after a deadline, when the venue may simply be lagging."""
    _posed(tmp_path, monkeypatch)
    just_due = datetime.now(tz=UTC) + timedelta(hours=25)   # past the 24h horizon, inside grace
    for _ in range(5):
        r = resolve_due(tmp_path, now=just_due, fetch=_dead_venue)
    assert r["n_voided"] == 0 and r["still_open"] == 3


def test_the_attempt_count_SURVIVES_A_RESTART(tmp_path, monkeypatch):
    """Each resolve_due call is a separate process. An in-memory counter would reset every run and
    the row would never reach the threshold -- retried forever, which is the bug."""
    _posed(tmp_path, monkeypatch)
    late = datetime.now(tz=UTC) + timedelta(hours=72)
    resolve_due(tmp_path, now=late, fetch=_dead_venue)
    rows = [json.loads(ln) for ln in
            (tmp_path / "data/calibration_probe.jsonl").read_text().splitlines() if ln.strip()]
    assert all(r["resolve_attempts"] == 1 for r in rows)


def test_a_retired_question_is_NOT_scored_either_way(tmp_path, monkeypatch):
    """The whole point. A fabricated outcome here would flow through report()'s bias into
    calibrated_confidence and out into Kelly leverage."""
    fc = _posed(tmp_path, monkeypatch)
    late = datetime.now(tz=UTC) + timedelta(hours=72)
    for _ in range(3):
        resolve_due(tmp_path, now=late, fetch=_dead_venue)
    store = json.loads((tmp_path / "data/forecast_log.json").read_text())["forecasts"]
    assert store and all(r.get("voided") and "outcome" not in r for r in store.values())
    assert fc.report()["n_excluded"]["voided"] == 3


def test_a_question_that_becomes_priceable_again_is_GRADED_not_retired(tmp_path, monkeypatch):
    """Retirement must lose to real evidence whenever real evidence shows up, right up to the
    last attempt -- otherwise the desk quietly stops grading names that merely went quiet."""
    _posed(tmp_path, monkeypatch)
    late = datetime.now(tz=UTC) + timedelta(hours=72)
    for _ in range(2):
        resolve_due(tmp_path, now=late, fetch=_dead_venue)
    bars = [(0, 0, 0, 0, 999.0)]                          # closed far above every ref price
    r = resolve_due(tmp_path, now=late, fetch=lambda *a, **k: (bars, "test"))
    assert r["n_resolved"] == 3 and r["n_voided"] == 0
