"""ONE SHAPE EVERY DETECTOR EMITS, so the ranker stops being a gatekeeper on discovery.

`run_max_push` merges every "not yet at 100%" source into one queue via a bespoke `_from_*` reader
per artifact. Adding the tenth made the cost visible: a detector written today cannot influence
tomorrow's priorities until somebody edits the ranker. That is the desk's recurring defect --
capability that cannot reach a decision -- with the ranker itself as the bottleneck.
"""

from __future__ import annotations

import json

import pytest

from libs.research.gap_contract import (
    KNOWN_SOURCES,
    Gap,
    load_published,
    publish,
    to_queue_rows,
)


def _gap(**kw) -> Gap:
    base = {"aspect": "a::b", "source": "conversion_debt", "current": 0.5, "ceiling": 1.0,
            "detail": "d", "action": "do the thing", "artifact": "data/x.json"}
    return Gap(**{**base, **kw})


def test_A_DETECTOR_MAY_NOT_MINT_A_SOURCE_CLASS() -> None:
    """A detector that could mint a class could mint a WEIGHT, and the honesty of the ranking is
    that every weight is argued in one visible place."""
    with pytest.raises(ValueError, match="may not mint a source class"):
        _gap(source="my_new_important_thing")


def test_EVERY_KNOWN_SOURCE_IS_ACCEPTED() -> None:
    for s in KNOWN_SOURCES:
        assert _gap(source=s).source == s


def test_A_ROW_WITH_NO_ACTION_IS_REFUSED() -> None:
    """A row nobody can act on is a complaint, and the queue exists to be worked."""
    with pytest.raises(ValueError, match="no action"):
        _gap(action="   ")


def test_UNMEASURED_IS_THE_MAXIMUM_GAP_NOT_ZERO() -> None:
    """L1.28a at the queue's input. An aspect at 60% is a known quantity being worked; an aspect
    with no number is an unknown being ignored, and that is where the expensive defects live."""
    g = _gap(current=None)
    assert g.measured is False
    assert g.gap_fraction == 1.0
    assert _gap(current=0.6).gap_fraction == pytest.approx(0.4)


def test_A_COMPLETE_ASPECT_HAS_ZERO_GAP_AND_STILL_APPEARS() -> None:
    """It must stay in the queue so the anti-complacency escalation can count it among the
    aspects that ARE at ceiling -- an all-green board is the signal, not the silence."""
    assert _gap(current=1.0).gap_fraction == 0.0


def test_A_GAP_ABOVE_CEILING_CLAMPS_RATHER_THAN_GOING_NEGATIVE() -> None:
    assert _gap(current=1.4).gap_fraction == 0.0


def test_PUBLISH_THEN_LOAD_ROUND_TRIPS(tmp_path) -> None:
    publish("t", [_gap(aspect="x::y"), _gap(aspect="x::z", current=None)], directory=tmp_path)
    rows = load_published(directory=tmp_path)
    assert {r.aspect for r in rows} == {"x::y", "x::z"}
    assert [r.measured for r in sorted(rows, key=lambda r: r.aspect)] == [True, False]


def test_PUBLISH_OVERWRITES_BECAUSE_THE_QUEUE_RANKS_TODAY(tmp_path) -> None:
    """An append-only log would rank a closed gap forever."""
    publish("t", [_gap(aspect="old::gap")], directory=tmp_path)
    publish("t", [_gap(aspect="new::gap")], directory=tmp_path)
    assert [r.aspect for r in load_published(directory=tmp_path)] == ["new::gap"]


def test_AN_EMPTY_PUBLISH_WRITES_A_FILE_RATHER_THAN_DELETING_ONE(tmp_path) -> None:
    """'This detector ran and found nothing' and 'this detector has never run' are different
    facts, and only the file's presence distinguishes them."""
    p = publish("t", [], directory=tmp_path)
    assert p.exists() and json.loads(p.read_text())["gaps"] == []
    assert load_published(directory=tmp_path) == []


def test_A_MALFORMED_ROW_IS_SKIPPED_NOT_GUESSED_AT(tmp_path) -> None:
    """Skipping is right here and wrong in publish: an unparseable row has no aspect it could
    name, so there is nothing to report as unmeasured."""
    (tmp_path / "bad.json").write_text(
        json.dumps({"gaps": [{"aspect": "ok::row", "source": "open_defect", "current": 0.1,
                              "ceiling": 1.0, "action": "act"},
                             {"aspect": "no_source"},
                             {"aspect": "bad::src", "source": "invented", "action": "act"},
                             "not a dict"]}), "utf-8")
    assert [r.aspect for r in load_published(directory=tmp_path)] == ["ok::row"]


def test_UNREADABLE_JSON_DOES_NOT_KILL_THE_SCAN(tmp_path) -> None:
    (tmp_path / "broken.json").write_text("{not json", "utf-8")
    publish("good", [_gap(aspect="still::here")], directory=tmp_path)
    assert [r.aspect for r in load_published(directory=tmp_path)] == ["still::here"]


def test_AN_ABSENT_DIRECTORY_IS_EMPTY_NOT_AN_ERROR(tmp_path) -> None:
    assert load_published(directory=tmp_path / "nope") == []


def test_SCORING_STAYS_IN_THE_QUEUE() -> None:
    """Two rankers that can disagree is worse than a bespoke reader per source, which is at least
    wrong in one place. This module renders through the queue's own builder and computes nothing.
    """
    seen: list[tuple] = []

    def fake_item(*args):
        seen.append(args)
        return {"aspect": args[0]}

    out = to_queue_rows([_gap(aspect="q::r")], fake_item)
    assert out == [{"aspect": "q::r"}]
    assert seen[0][:2] == ("q::r", "conversion_debt")
    assert "score" not in str(out)
