"""The timestamp-overlap reading: bets counted by WHEN sleeves are in the market.

AUDIT P5 (2026-09-08): six of the ten dependency channels existed and "event/timestamp overlap"
was not one of them -- the exposure readings price every sleeve as if it were always on, so two
same-mechanism sleeves that take turns (one fires in Asia, one in London) read as one bet.

What is pinned:

  * N sleeves that never hold a position at the same minute count N; N copies of one clock
    count 1; a row whose exit equals its entry still occupied its bar; a corrupt exit stamp is
    capped at a week;
  * the reading is MEASURED beside the four readings, INFORMATIONAL, and NEVER in the headline
    minimum -- `effective.readings` is the same four names it was, whatever this reading says;
  * `would_raise_headline_to` is stated, not applied;
  * the history row carries `n_eff_time`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.research import alpha_clusters as ac  # noqa: E402
from research import alpha_breadth as ab  # noqa: E402


def _write_ledger(d: Path, sleeve: str, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / f"ledger_{sleeve}.json").write_text(json.dumps(rows), "utf-8")


def _row(day: int, hour: int, r: float = 0.5, hold_h: int = 1, side: int = 1) -> dict:
    end_h = hour + hold_h
    return {"entry_time": f"2026-08-{day:02d}T{hour:02d}:00:00+00:00",
            "exit_time": f"2026-08-{day:02d}T{end_h:02d}:00:00+00:00",
            "side": side, "r_multiple": r, "reason": "target"}


@pytest.fixture
def led(tmp_path, monkeypatch) -> Path:
    d = tmp_path / "ledgers"
    monkeypatch.setattr(ab, "LEDGER_DIRS", (d,))
    return d


# ------------------------------------------------------------------------------- the measure
def test_sleeves_that_take_turns_count_as_many_bets_and_copies_count_as_one(led) -> None:
    _write_ledger(led, "AUDCHF_overnight_gap_decay_asia", [_row(d, 1) for d in range(1, 6)])
    _write_ledger(led, "GBPZAR_overnight_gap_decay_asia", [_row(d, 13) for d in range(1, 6)])
    labels = {s: ac.classify_sleeve(s) for s in ("AUDCHF_overnight_gap_decay_asia",
                                                  "GBPZAR_overnight_gap_decay_asia")}
    assert len(set(labels.values())) == 1, "the fixture must be one declared mechanism"
    o = ab.timestamp_overlap(ab.trading_minutes(), labels)
    assert o["status"] == "MEASURED" and o["n_eff"] == pytest.approx(2.0)
    assert o["n_pairs"] == 1 and o["n_disjoint_pairs"] == 1 and o["mean_jaccard"] == 0.0
    assert o["same_mechanism"]["n_pairs"] == 1
    assert o["same_mechanism"]["n_disjoint_pairs"] == 1
    assert o["same_mechanism"]["disjoint_pairs"][0][2] == labels["AUDCHF_overnight_gap_decay_asia"]
    assert o["informational"] is True and o["in_headline"] is False
    assert "never lowers the headline" in o["rule"]
    # the same clock twice is one bet
    _write_ledger(led, "GBPZAR_overnight_gap_decay_asia", [_row(d, 1) for d in range(1, 6)])
    o = ab.timestamp_overlap(ab.trading_minutes(), labels)
    assert o["n_eff"] == pytest.approx(1.0) and o["most_overlapping"][0][2] == 1.0


def test_a_row_with_exit_equal_to_entry_occupies_one_bar(led) -> None:
    """Every overnight_gap_decay row on the tree stamps exit == entry. It held the bar."""
    same = {"entry_time": "2026-08-17 01:00:00+00:00", "exit_time": "2026-08-17 01:00:00+00:00",
            "side": 1, "r_multiple": 0.5}
    _write_ledger(led, "A_x", [same])
    _write_ledger(led, "B_x", [{**same, "entry_time": "2026-08-17 01:30:00+00:00",
                                "exit_time": "2026-08-17 01:30:00+00:00"}])
    mins = ab.trading_minutes()
    assert len(mins["A_x"]) == ab.MIN_TRADE_SPAN_MIN == 60
    o = ab.timestamp_overlap(mins)
    assert o["most_overlapping"][0][2] == pytest.approx(30 / 90, abs=1e-3)   # 30 shared of 90


def test_a_corrupt_exit_stamp_is_capped_at_a_week_and_no_exit_is_one_bar(led) -> None:
    _write_ledger(led, "A_x", [{"entry_time": "2026-08-01T00:00:00+00:00",
                                "exit_time": "2027-08-01T00:00:00+00:00", "side": 1,
                                "r_multiple": 0.1}])
    _write_ledger(led, "B_x", [{"opened_at": "2026-08-01T00:00:00+00:00", "direction": 1,
                                "r": 0.1}])
    mins = ab.trading_minutes()
    assert len(mins["A_x"]) == ab.MAX_TRADE_SPAN_MIN == 7 * 24 * 60
    assert len(mins["B_x"]) == 60


def test_one_sleeve_or_none_is_unmeasured_never_a_number(led) -> None:
    assert ab.timestamp_overlap({})["status"] == "UNMEASURED"
    _write_ledger(led, "A_x", [_row(1, 9)])
    o = ab.timestamp_overlap(ab.trading_minutes())
    assert o["status"] == "UNMEASURED" and o["n_eff"] is None and "needs two" in o["why"]
    # an unparseable time is skipped, not a crash
    _write_ledger(led, "B_x", [{"entry_time": "not a time", "side": 1, "r_multiple": 0.1}])
    assert "B_x" not in ab.trading_minutes()


# ------------------------------------------------------------------------------- the artifact
def test_the_reading_sits_beside_the_four_and_the_headline_rule_is_untouched(
        led, tmp_path, monkeypatch) -> None:
    _write_ledger(led, "AUDCHF_overnight_gap_decay_asia", [_row(d, 1) for d in range(1, 6)])
    _write_ledger(led, "GBPZAR_overnight_gap_decay_asia", [_row(d, 13) for d in range(1, 6)])
    monkeypatch.setattr(ab, "UNIVERSE", tmp_path / "no_universe")
    monkeypatch.setattr(ab, "CANON", tmp_path / "absent_canon.json")
    monkeypatch.setattr(ab, "OUT", tmp_path / "EFFECTIVE_BREADTH.json")
    monkeypatch.setattr(ab, "HISTORY", tmp_path / "effective_breadth.jsonl")
    doc = ab.run(write_queue=False)
    names = [r["name"] for r in doc["effective"]["readings"]]
    assert "timestamp_overlap" not in names, "the reading must never enter the headline minimum"
    assert doc["effective"]["status"] == "UNMEASURED"        # no bars, no 20-day overlap
    o = doc["timestamp_overlap"]
    assert o["status"] == "MEASURED" and o["n_eff"] == pytest.approx(2.0)
    assert o["headline_unchanged"] is True and o["informational"] is True
    assert o["would_raise_headline_to"] is None, "nothing to raise when the headline is unmeasured"
    assert "INFORMATIONAL" in o["rule"] and "allocator consumes it" in o["rule"]
    assert json.loads((tmp_path / "EFFECTIVE_BREADTH.json").read_text("utf-8"))[
        "timestamp_overlap"]["n_eff"] == pytest.approx(2.0)
    (row,) = ab.history()
    assert row["n_eff_time"] == pytest.approx(2.0) and row["effective_breadth"] is None


def test_would_raise_is_stated_not_applied_when_a_headline_exists(monkeypatch, tmp_path) -> None:
    """With a measured headline below the overlap reading, the artifact SAYS what the headline
    would become and leaves the headline exactly where the minimum rule put it."""
    from libs.research.effective_breadth import Reading

    def fake_headline(readings, n_nominal):
        return {"n_nominal": n_nominal, "effective_breadth": 1.324, "status": "MEASURED",
                "binding_reading": "exposure_systematic",
                "readings": [r.as_dict() for r in readings], "unmeasured": []}
    monkeypatch.setattr(ab, "headline", fake_headline)
    monkeypatch.setattr(ab, "OUT", tmp_path / "EFFECTIVE_BREADTH.json")
    monkeypatch.setattr(ab, "HISTORY", tmp_path / "effective_breadth.jsonl")
    monkeypatch.setattr(ab, "book_exposure", lambda: {
        "exposure": {}, "kept": [], "dropped": {}, "n_sleeves_total": 2,
        "n_sleeves_measured": 0, "measured_share_of_sleeves": 0.0})
    monkeypatch.setattr(ab, "realised_breadth", lambda s: Reading(
        "realised_returns", "UNMEASURED", None, 2, 0, "fixture"))
    monkeypatch.setattr(ab, "trading_minutes", lambda: {"a": set(range(0, 60)),
                                                        "b": set(range(600, 660))})
    monkeypatch.setattr(ab, "cluster_view", lambda: {
        "traded": {"occupied": [], "n_occupied": 0, "n_unclassified": 0, "counts": {},
                   "largest_cluster_share": 0.0, "empty_detail": []},
        "certified": {"occupied": [], "n_unclassified": 0, "counts": {}},
        "traded_labels": {}, "certified_labels": {}, "occupied_either": [],
        "empty_in_both": []})
    doc = ab.run(write_queue=False)
    assert doc["effective"]["effective_breadth"] == 1.324           # untouched
    assert doc["timestamp_overlap"]["n_eff"] == pytest.approx(2.0)
    assert doc["timestamp_overlap"]["would_raise_headline_to"] == pytest.approx(2.0)
    assert doc["timestamp_overlap"]["headline_unchanged"] is True
