"""The vocabulary proposer (N9 item 12): it learns only words the field uses, reads them only as
the evidence says, and the frontier estimate reads them only as a last resort.

Every input is a planted row; every path is redirected into `tmp_path`. The family table is the
desk's real one, so the known words below are words it really places (`momentum` ->
trend_persistence, `carry` -> carry_rollover) and the unknown ones are words it really does not.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research"), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import unseen_frontier as uf  # noqa: E402
import vocabulary_proposer as vp  # noqa: E402

TREND = uf.CLASS_MECHANISM["momentum"]
CARRY = uf.classify_family("carry")


@pytest.fixture
def desk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, rel in (("CLAIMS", "data/deep_forest_claims.jsonl"),
                      ("DEEP_FOREST", "reports/DEEP_FOREST.json"),
                      ("INTELLIGENCE", "data/intelligence"),
                      ("GRAPH", "data/hypothesis_graph.jsonl"),
                      ("AXIS_REPORT", "reports/AXIS_REGISTRY.json"),
                      ("OUT_REPORT", "reports/UNSEEN_FRONTIER.json"),
                      ("OUT_HISTORY", "data/unseen_frontier_history.jsonl"),
                      ("ALIASES", "data/vocabulary_aliases.json")):
        monkeypatch.setattr(uf, name, tmp_path / rel)
    monkeypatch.setattr(uf, "asset_class_of", lambda s: uf.UNKNOWN)
    monkeypatch.setattr(uf, "_LEARNT", None)
    monkeypatch.setattr(vp, "REPORT", tmp_path / "reports" / "VOCABULARY_PROPOSALS.json")
    monkeypatch.setattr(vp, "ALIASES", tmp_path / "data" / "vocabulary_aliases.json")
    return tmp_path


def _row(labels: list[str], kinds: set[str], ground: str, symbols: Any = None) -> vp.Row:
    return vp.Row(labels, frozenset(kinds), ground, symbols)


def _spread(labels: list[str], kinds: set[str], n: int, grounds: int) -> list[vp.Row]:
    return [_row(labels, kinds, f"en|g{i % grounds}", ["EURUSD"]) for i in range(n)]


def _placed_background() -> list[vp.Row]:
    """Rows the desk CAN place, so kinds carry a meaning: lookback/breakout_high belong to trend,
    swap_points/rate_diff to carry, horizon to both (so it votes for neither)."""
    return (_spread(["momentum"], {"lookback", "breakout_high", "horizon"}, 60, 4)
            + _spread(["carry"], {"swap_points", "rate_diff", "horizon"}, 60, 4))


def _judge(rows: list[vp.Row]) -> dict[str, dict[str, Any]]:
    rep = vp.build(rows)
    return {w["word"]: w for w in rep["words"]}


def test_a_word_that_travels_with_a_known_label_becomes_its_alias(desk: Path) -> None:
    rows = _placed_background() + _spread(["forced_liquidation", "momentum"], {"lookback"}, 30, 5)
    w = _judge(rows)["forced_liquidation"]
    assert w["verdict"] == "ALIAS" and w["mechanism"] == TREND
    assert w["colabel"]["top"] == TREND and w["colabel"]["n"] == 30


def test_a_word_alone_is_read_by_the_kinds_its_rows_carry(desk: Path) -> None:
    rows = _placed_background() + _spread(["tom_next_roll"], {"swap_points", "rate_diff"}, 25, 3)
    w = _judge(rows)["tom_next_roll"]
    assert w["verdict"] == "ALIAS" and w["mechanism"] == CARRY
    assert w["colabel"]["n"] == 0 and w["kind_vote"]["top"] == CARRY
    assert w["n_unplaced_rows"] == 25


def test_a_kind_every_mechanism_shares_votes_for_none(desk: Path) -> None:
    rows = _placed_background() + _spread(["horizon_only_word"], {"horizon"}, 25, 3)
    w = _judge(rows)["horizon_only_word"]
    assert w["kind_vote"]["top"] is None
    assert w["verdict"] == "PROPOSED_MECHANISM" and w["mechanism"] == "proposed:horizon_only_word"


def test_disagreeing_readings_propose_rather_than_alias(desk: Path) -> None:
    rows = (_placed_background()
            + _spread(["basis_squeeze", "momentum"], {"swap_points", "rate_diff"}, 30, 4))
    w = _judge(rows)["basis_squeeze"]
    assert w["colabel"]["top"] == TREND and w["kind_vote"]["top"] == CARRY
    assert w["verdict"] == "PROPOSED_MECHANISM"


def test_one_grounds_jargon_or_a_rare_word_is_counted_not_learnt(desk: Path) -> None:
    rows = (_placed_background()
            + _spread(["one_forum_word"], {"swap_points"}, 50, 1)
            + _spread(["rare_word"], {"swap_points"}, vp.MIN_ROWS - 1, 5))
    rep = vp.build(rows)
    words = {w["word"]: w for w in rep["words"]}
    assert words["one_forum_word"]["verdict"] == "BELOW_FLOOR"
    assert words["rare_word"]["verdict"] == "BELOW_FLOOR"
    assert "one_forum_word" not in rep["aliases"] and "one_forum_word" not in rep["proposed"]


def test_numbers_generic_labels_and_unlabelled_rows_are_refused_and_counted(desk: Path) -> None:
    rows = (_spread(["2024"], {"x"}, 30, 5) + _spread(["strategy"], {"x"}, 30, 5)
            + [_row([], {"x"}, "en|g0")] * 7)
    rep = vp.build(rows)
    assert rep["words_unplaced"] == 0
    assert rep["labels_refused"] == 60 and rep["rows_without_label"] == 7


def test_known_words_are_never_proposed(desk: Path) -> None:
    rep = vp.build(_placed_background())
    assert rep["words_unplaced"] == 0 and rep["aliases"] == {} and rep["proposed"] == {}


def test_write_publishes_the_report_and_the_word_file(desk: Path) -> None:
    rows = _placed_background() + _spread(["forced_liquidation", "momentum"], {"lookback"}, 30, 5)
    vp.write(vp.build(rows))
    words = json.loads(vp.ALIASES.read_text("utf-8"))
    assert words["aliases"] == {"forced_liquidation": TREND} and words["proposed"] == {}
    assert json.loads(vp.REPORT.read_text("utf-8"))["verdicts"] == {"ALIAS": 1}


def test_the_frontier_reads_learnt_words_last_and_only_then(desk: Path) -> None:
    assert uf.mechanism_of(family="forced_liquidation") == uf.UNKNOWN     # nothing learnt yet
    vp.ALIASES.parent.mkdir(parents=True, exist_ok=True)
    vp.ALIASES.write_text(json.dumps({"aliases": {"forced_liquidation": TREND,
                                                  "momentum": CARRY},
                                      "proposed": {"basis_squeeze": "proposed:basis_squeeze"}}))
    uf._LEARNT = None
    assert uf.mechanism_of(family="forced_liquidation") == TREND
    assert uf.mechanism_of(tags=["basis_squeeze"]) == "proposed:basis_squeeze"
    assert uf.mechanism_of(tags=["momentum"]) == TREND        # the desk's own table wins
    assert uf.mechanism_of(family="never_seen") == uf.UNKNOWN


def test_an_unreadable_word_file_changes_nothing(desk: Path) -> None:
    vp.ALIASES.parent.mkdir(parents=True, exist_ok=True)
    vp.ALIASES.write_text("{not json")
    assert uf.learnt_words() == {}


def test_the_full_read_goes_through_the_frontiers_own_grounds(desk: Path) -> None:
    seat = uf.INTELLIGENCE / "seat"
    seat.mkdir(parents=True)
    disc = [{"family": "momentum", "mechanism_tags": ["forced_liquidation"],
             "params": {"lookback": 20}, "source": f"s{i % 4}", "lang": "en",
             "symbols": ["EURUSD"]} for i in range(25)]
    (seat / "discoveries_1.json").write_text(json.dumps({"discoveries": disc}))
    rep = vp.build()
    assert rep["rows_read"]["discovery_rows"] == 25
    assert rep["aliases"] == {"forced_liquidation": TREND}
    assert rep["inputs"][uf.INTELLIGENCE.name] == "READ(1/1)"
    assert Counter(rep["verdicts"]) == Counter({"ALIAS": 1})
