"""The cert book's door removes ONLY zero pins a principal order releases, through an organ."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import cert_book_door as door  # noqa: E402

BOOK = {"enabled": True, "rule": "a key not named keeps the allocator's fraction",
        "fusion_by": "principal zuck, BOOKS_PATCH v5", "e8_by": "principal zuck 2026-10-20",
        "fusion": {"gold_london_am": 0.0, "gold_afternoon": 0.0, "AUDCHF_x": 0.0},
        "e8": {"gold_asia": 0.006, "gold_london_am": 0.0, "gold_afternoon": 0.0},
        "ftmo": {"gold_asia": 0.0033}}
ORDER = {"id": "D-20261111-071", "title": "All accounts trade everything: the gold-asia-only pin"}


def _desk(tmp: Path, journal: list[dict] | None, book: dict | None = BOOK) -> dict[str, Path]:
    p = {"book": tmp / "CERT_BOOK_LIVE.json", "journal": tmp / "decision_journal.jsonl",
         "report": tmp / "reports" / "CERT_BOOK_DOOR.json",
         "switch": tmp / "GOLD_ASIA_ONLY_ENABLED",
         "backups": tmp / "reports" / "cert_book_door_backups"}
    if book is not None:
        p["book"].write_text(json.dumps(book), "utf-8")
    if journal is not None:
        p["journal"].write_text("".join(json.dumps(r) + "\n" for r in journal), "utf-8")
    return p


def _run(p: dict[str, Path], e8_open: bool = False) -> dict:
    return door.run(p["book"], p["journal"], p["report"], p["switch"], p["backups"],
                    e8_door=lambda: e8_open)


def test_the_order_releases_fusion_zero_pins_and_reports_e8_as_needing_a_size(
        tmp_path: Path) -> None:
    p = _desk(tmp_path, [ORDER])
    doc = _run(p)
    assert doc["status"] == "RELEASED"
    assert sorted((r["venue"], r["key"]) for r in doc["removed"]) == [
        ("fusion", "gold_afternoon"), ("fusion", "gold_london_am")]
    assert sorted(r["key"] for r in doc["needs_size"] if r["venue"] == "e8") == [
        "gold_afternoon", "gold_london_am"]
    book = json.loads(p["book"].read_text("utf-8"))
    assert book["fusion"] == {"AUDCHF_x": 0.0}                       # unrelated pin untouched
    assert book["e8"] == BOOK["e8"] and book["ftmo"] == BOOK["ftmo"]  # E8 is NOT touched
    assert "released_by research/cert_book_door.py" in book["fusion_by"]
    assert book["e8_by"] == BOOK["e8_by"] and book["rule"] == BOOK["rule"]
    # the backup lives with the report, never beside the book in data/
    assert next(f.name for f in p["backups"].iterdir()).startswith("CERT_BOOK_LIVE.json.bak_door_")
    assert not any(f.name.startswith("CERT_BOOK_LIVE.json.bak") for f in tmp_path.iterdir())
    again = _run(p)                                                   # idempotent
    assert again["status"] == "NEEDS_SIZE" and len(again["history"]) == 1


def test_e8_zeros_are_released_only_while_its_absent_key_door_is_open(tmp_path: Path) -> None:
    """#958 (Max-growth) makes e8_gold read an absent key as the allocator's fraction behind
    `absent_key_door_open()`; only while that answers True may the door delete the e8 zeros."""
    p = _desk(tmp_path, [ORDER])
    doc = _run(p, e8_open=True)
    assert sorted((r["venue"], r["key"]) for r in doc["removed"]) == [
        ("e8", "gold_afternoon"), ("e8", "gold_london_am"),
        ("fusion", "gold_afternoon"), ("fusion", "gold_london_am")]
    assert not doc.get("needs_size")
    book = json.loads(p["book"].read_text("utf-8"))
    assert book["e8"] == {"gold_asia": 0.006}                        # a SIZE is never touched
    assert "released_by research/cert_book_door.py" in book["e8_by"]
    # shut (or a tree without #958): E8 waits, reported, untouched
    q = _desk(tmp_path / "shut", [ORDER]) if (tmp_path / "shut").mkdir() is None else None
    assert q is not None
    shut = _run(q, e8_open=False)
    assert {r["venue"] for r in shut["removed"]} == {"fusion"}
    assert json.loads(q["book"].read_text("utf-8"))["e8"] == BOOK["e8"]
    assert door.e8_absent_key_door_open() in (True, False)           # never raises


def test_it_fails_closed_every_way(tmp_path: Path) -> None:
    impostor = {"id": "D-20261111-071", "title": "some other decision minted with the same id"}
    for i, (journal, book, switch, want) in enumerate((
            ([impostor], BOOK, False, "NO_CHANGE"),        # right id, wrong order
            ([], BOOK, False, "NO_CHANGE"),                # no order at all
            (None, BOOK, False, "UNMEASURED"),             # journal unreadable
            ([ORDER], None, False, "UNMEASURED"),          # book unreadable
            ([ORDER], {**BOOK, "enabled": False}, False, "NO_CHANGE"),
            ([ORDER], BOOK, True, "HELD"))):               # the principal's revert switch
        d = tmp_path / f"case{i}"
        d.mkdir()
        p = _desk(d, journal, book)
        if switch:
            p["switch"].write_text("", "utf-8")
        before = p["book"].read_text("utf-8") if p["book"].exists() else None
        assert _run(p)["status"] == want
        assert (p["book"].read_text("utf-8") if p["book"].exists() else None) == before


def test_the_real_fusion_sizing_reads_the_allocator_fraction_after_the_door(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#956 audit M1: run the door, then the gateway's own `allocator_book`, and assert what it
    would send -- through the REAL switch, never a patched constant. With #954 on the tree the
    gold-asia-only pin is `decision_core.GOLD_ASIA_ONLY_FILE`: absent, the released windows take
    the allocator's fraction; present, they send 0 whatever the cert book says. Without #954 the
    code pin binds and both read 0 -- the door alone never opens a window the code still pins."""
    pytest.importorskip("MetaTrader5")
    from mt5desk import decision_core as dc
    from mt5desk import gateway as gw
    from mt5desk import kelly_sizing
    p = _desk(tmp_path, [ORDER])
    alloc = {"gold_london_am": 0.031, "gold_afternoon": 0.012, "AUDCHF_x": 0.02}
    monkeypatch.setattr(gw, "_allocator_book", lambda: (dict(alloc), "fixture"))
    monkeypatch.setattr(kelly_sizing, "CERT_BOOK_FILE", p["book"])
    switch = tmp_path / "GOLD_ASIA_ONLY_ENABLED"
    has_switch = hasattr(dc, "GOLD_ASIA_ONLY_FILE")
    if has_switch:
        monkeypatch.setattr(dc, "GOLD_ASIA_ONLY_FILE", switch)
    before, _ = gw.allocator_book()
    assert before["gold_london_am"] == 0.0 and before["gold_afternoon"] == 0.0
    assert _run(p)["status"] == "RELEASED"
    after, _ = gw.allocator_book()
    assert after["AUDCHF_x"] == 0.0                                  # its pin stands
    if not has_switch:
        # pre-#954: the code pin binds; the door released the book, the gateway still sends 0
        assert after["gold_london_am"] == 0.0 and after["gold_afternoon"] == 0.0
        return
    assert after["gold_london_am"] == 0.031 and after["gold_afternoon"] == 0.012
    switch.write_text("", "utf-8")                                   # the principal's revert
    still, _ = gw.allocator_book()
    assert still["gold_london_am"] == 0.0 and still["gold_afternoon"] == 0.0


def test_it_runs_on_the_hourly_clock_and_writes_no_number() -> None:
    hc = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"cert_book_door", "research/cert_book_door.py"))' in hc
    src = (_DESK / "research" / "cert_book_door.py").read_text(encoding="utf-8")
    assert "del block[key]" in src
    assert not re.search(r"block\[key\]\s*=[^=]", src), "the door never writes a number"
