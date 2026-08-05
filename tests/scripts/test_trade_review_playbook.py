"""file_lesson against BOTH playbook record shapes (stub-deaths defect, 2026-08-05).

THE BUG. The reviewer wrote lessons as ``{key, text, ...}`` but the playbook is also populated by
an IMPORTER that writes ``{lesson, origin, imported_from, ...}`` -- carrying neither ``key`` nor
``text``. file_lesson indexed both fields directly, so the first loop iteration raised
``KeyError: 'key'`` and killed the organ. Every one of the 4 records in data/trading_playbook.json
is the imported shape, which is exactly why the playbook had sat at those 4 lessons and never
grew: the review died before it could file anything, every day, silently.

Proved here rather than by a live run because run_trade_review calls the brain, and the brain is
currently out of credits -- a test that can only pass when a paid API is up is not a regression
test. These run offline and deterministically.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.run_trade_review import file_lesson

_IMPORTED = {"at": "2026-07-01T00:00:00Z", "authority": "SEED", "imported_from": "institutional",
             "lesson": "Never size into a thin book at the open.", "origin": "import",
             "status": "PROVISIONAL", "support": 1, "trades": ["t0"]}

_NATIVE = {"key": "never size into a thin book at the open.", "status": "PROVISIONAL",
           "text": "Never size into a thin book at the open.", "support": 1, "trades": ["t0"],
           "first_seen_at_trade": 1, "last_seen_at_trade": 1}


def _pb(*lessons: dict[str, Any]) -> dict[str, Any]:
    return {"lessons": [dict(x) for x in lessons]}


def test_an_imported_record_does_not_raise_keyerror() -> None:
    """THE REGRESSION. Before the fix this raised KeyError: 'key' and killed the daily organ."""
    pb = _pb(_IMPORTED)
    out = file_lesson(pb, {"lesson": "Something completely unrelated about funding."}, "t1", 5)
    assert out["action"] == "new"
    assert len(pb["lessons"]) == 2


@pytest.mark.parametrize("shape", [_IMPORTED, _NATIVE], ids=["imported", "native"])
def test_a_matching_lesson_is_reinforced_in_either_shape(shape: dict[str, Any]) -> None:
    """Dedupe must work across both shapes, or the same lesson is filed twice forever."""
    pb = _pb(shape)
    out = file_lesson(pb, {"lesson": "Never size into a thin book at the open."}, "t1", 5)
    assert out["action"] == "reinforced"
    assert out["support"] == 2
    assert len(pb["lessons"]) == 1, "a duplicate must not be appended"


def test_contradiction_retires_an_imported_lesson_and_names_it() -> None:
    """The RETIRED path also read lv['text']; an imported record would have crashed it too."""
    pb = _pb(_IMPORTED)
    out = file_lesson(pb, {"lesson": "Never size into a thin book at the open.",
                           "contradicts": True}, "t9", 7)
    assert out["action"] == "retired"
    assert out["lesson"] == _IMPORTED["lesson"], "the retired lesson must be reported, not blank"
    assert pb["lessons"][0]["status"] == "RETIRED"
    assert "t9" in pb["lessons"][0]["contradicted_by"]


def test_promotion_still_fires_from_an_imported_record() -> None:
    from scripts.run_trade_review import N_SUPPORT
    pb = _pb({**_IMPORTED, "support": N_SUPPORT - 1})
    out = file_lesson(pb, {"lesson": "Never size into a thin book at the open."}, "t2", 9)
    assert out["action"] == "promoted"
    assert pb["lessons"][0]["status"] == "SUPPORTED"


def test_a_record_missing_support_or_trades_does_not_crash() -> None:
    """Fail-soft on partial records: a malformed row must not take the whole review down again."""
    pb = _pb({"lesson": "Never size into a thin book at the open.", "status": "PROVISIONAL"})
    out = file_lesson(pb, {"lesson": "Never size into a thin book at the open."}, "t3", 4)
    assert out["action"] in {"reinforced", "promoted"}
    assert pb["lessons"][0]["trades"] == ["t3"]


def test_an_empty_or_none_lesson_is_still_refused() -> None:
    """The pre-existing guard must survive the fix -- superstition is worse than an empty book."""
    for txt in ("", "   ", "NONE -- nothing transferable"):
        assert file_lesson(_pb(_IMPORTED), {"lesson": txt}, "t1", 5)["action"] == "no-lesson"


def test_the_live_playbook_is_the_shape_this_fix_exists_for() -> None:
    """PINS THE FIELD REALITY: if the importer ever starts writing `key`, this test says so."""
    import json
    from pathlib import Path
    pb_path = Path(__file__).resolve().parents[2] / "data/trading_playbook.json"
    if not pb_path.exists():
        pytest.skip("no playbook on this host")
    lessons = json.loads(pb_path.read_text("utf-8")).get("lessons", [])
    if not lessons:
        pytest.skip("playbook empty")
    assert any("key" not in lv for lv in lessons), (
        "no keyless record left -- if the importer now writes `key`, simplify file_lesson")
