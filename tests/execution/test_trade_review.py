"""R0139 trade review -- the discretionary desk's learning loop, on Binance perps.

The playbook must be a body of EVIDENCE, not a pile of opinions: nothing reaches the trader on one
observation, contradiction retires a lesson permanently, and an untested belief goes stale.
"""
from __future__ import annotations

import json

from scripts.run_trade_review import (
    _CAUSES,
    MAX_BRIEF_LESSONS,
    N_SUPPORT,
    STALE_AFTER,
    age_playbook,
    brief_lessons,
    closed_trades,
    file_lesson,
    load_playbook,
    review_one,
)


def _pb():
    return {"lessons": [], "reviewed_keys": []}


def _lesson(text="on PAXG in contracting vol a level with under 3 touches fails a 30h horizon"):
    return {"lesson": text, "lesson_falsifier": "such a level holds 3 times running",
            "applies_when": "PAXG, contracting vol", "cause": "LEVEL-WRONG"}


def test_one_observation_never_reaches_the_trader():
    # A single lucky trade must not be able to rewrite the method.
    pb = _pb()
    file_lesson(pb, _lesson(), "t1", 1)
    assert pb["lessons"][0]["status"] == "PROVISIONAL"
    assert brief_lessons(pb) == []


def test_a_lesson_is_promoted_only_on_independent_agreement():
    pb = _pb()
    for i in range(N_SUPPORT - 1):
        file_lesson(pb, _lesson(), f"t{i}", i)
        assert brief_lessons(pb) == []
    r = file_lesson(pb, _lesson(), "tN", N_SUPPORT)
    assert r["action"] == "promoted" and pb["lessons"][0]["status"] == "SUPPORTED"
    assert len(brief_lessons(pb)) == 1


def test_contradiction_retires_a_lesson_and_the_contradiction_is_recorded():
    # A retired lesson must not be able to quietly return next week.
    pb = _pb()
    for i in range(N_SUPPORT):
        file_lesson(pb, _lesson(), f"t{i}", i)
    assert pb["lessons"][0]["status"] == "SUPPORTED"
    r = file_lesson(pb, {**_lesson(), "contradicts": True}, "tX", N_SUPPORT + 1)
    assert r["action"] == "retired"
    assert pb["lessons"][0]["status"] == "RETIRED"
    assert "tX" in pb["lessons"][0]["contradicted_by"]
    assert brief_lessons(pb) == []


def test_an_untested_belief_goes_stale():
    pb = _pb()
    for i in range(N_SUPPORT):
        file_lesson(pb, _lesson(), f"t{i}", 10)
    assert pb["lessons"][0]["status"] == "SUPPORTED"
    assert age_playbook(pb, 10 + STALE_AFTER) == []            # still inside the window
    staled = age_playbook(pb, 10 + STALE_AFTER + 1)
    assert staled and pb["lessons"][0]["status"] == "STALE"
    assert brief_lessons(pb) == []


def test_a_review_that_found_nothing_files_nothing():
    # A review manufacturing a lesson from every trade fills the playbook with superstition, and
    # superstition in the brief is worse than an empty playbook.
    pb = _pb()
    r = file_lesson(pb, {"lesson": "NONE -- single-instance noise, no transferable rule"}, "t1", 1)
    assert r["action"] == "no-lesson" and pb["lessons"] == []
    assert file_lesson(pb, {"lesson": ""}, "t2", 2)["action"] == "no-lesson"


def test_the_brief_is_bounded_and_ranked_by_evidence():
    pb = _pb()
    for n in range(MAX_BRIEF_LESSONS + 5):
        for i in range(N_SUPPORT + (n % 3)):
            file_lesson(pb, _lesson(f"lesson number {n} about a situation"), f"t{n}-{i}", n)
    out = brief_lessons(pb)
    assert len(out) == MAX_BRIEF_LESSONS
    assert out == sorted(out, key=lambda lv: -lv["evidence_trades"])


def test_a_malformed_review_is_discarded_not_filed():
    assert review_one({}, {}, ask=lambda _p: "the model refused") is None
    assert review_one({}, {}, ask=lambda _p: '{"cause": "MADE-UP", "lesson": "x"}') is None
    good = '{"cause": "NOISE-STOP", "lesson": "x", "what_happened": "y"}'
    assert review_one({}, {}, ask=lambda _p: good)["cause"] == "NOISE-STOP"


def test_causes_distinguish_being_wrong_from_being_unlucky():
    # A desk that cannot tell RIGHT-AND-UNLUCKY from WRONG will "fix" a working process.
    assert "UNLUCKY" in _CAUSES and "THESIS-WRONG" in _CAUSES
    assert "NOISE-STOP" in _CAUSES and "RIGHT-BUT-TRUNCATED" in _CAUSES


def test_nothing_to_review_is_stated_as_unmeasured_learning(tmp_path):
    assert closed_trades(tmp_path) == []
    assert load_playbook(tmp_path)["lessons"] == []


def test_only_unreviewed_closed_trades_are_returned(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/conviction_book.jsonl").write_text(
        json.dumps({"at": "A", "symbol": "BTCUSDT"}) + "\n"
        + json.dumps({"at": "B", "symbol": "ETHUSDT"}) + "\n")
    (tmp_path / "data/paper_book_pnl.json").write_text(json.dumps(
        {"marks": [{"key": "A", "closed": True}, {"key": "B", "closed": True}]}))
    (tmp_path / "data/trading_playbook.json").write_text(json.dumps(
        {"lessons": [], "reviewed_keys": ["A"]}))
    got = closed_trades(tmp_path)
    assert [r["at"] for r, _ in got] == ["B"]
