"""The cert book's door removes ONLY zero pins a principal order releases, through an organ."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import cert_book_door as door  # noqa: E402

BOOK = {"enabled": True, "rule": "a key not named keeps the allocator's fraction",
        "fusion": {"gold_london_am": 0.0, "gold_afternoon": 0.0, "AUDCHF_x": 0.0},
        "e8": {"gold_asia": 0.006, "gold_london_am": 0.0, "gold_afternoon": 0.004},
        "ftmo": {"gold_asia": 0.0033}}
ORDER = {"id": "D-20261111-071", "title": "All accounts trade everything: the gold-asia-only pin"}


def _desk(tmp: Path, journal: list[dict] | None, book: dict | None = BOOK) -> dict[str, Path]:
    p = {"book": tmp / "CERT_BOOK_LIVE.json", "journal": tmp / "decision_journal.jsonl",
         "report": tmp / "CERT_BOOK_DOOR.json", "switch": tmp / "GOLD_ASIA_ONLY_ENABLED"}
    if book is not None:
        p["book"].write_text(json.dumps(book), "utf-8")
    if journal is not None:
        p["journal"].write_text("".join(json.dumps(r) + "\n" for r in journal), "utf-8")
    return p


def _run(p: dict[str, Path]) -> dict:
    return door.run(p["book"], p["journal"], p["report"], p["switch"])


def test_the_order_releases_exactly_its_zero_pins_and_nothing_else(tmp_path: Path) -> None:
    p = _desk(tmp_path, [ORDER])
    doc = _run(p)
    assert doc["status"] == "RELEASED" and len(doc["removed"]) == 3
    book = json.loads(p["book"].read_text("utf-8"))
    assert book["fusion"] == {"AUDCHF_x": 0.0}                      # unrelated pin untouched
    assert book["e8"] == {"gold_asia": 0.006, "gold_afternoon": 0.004}   # a SIZE is never touched
    assert book["ftmo"] == BOOK["ftmo"] and book["rule"] == BOOK["rule"]
    assert any(f.name.startswith("CERT_BOOK_LIVE.json.bak_door_") for f in tmp_path.iterdir())
    again = _run(p)                                                  # idempotent
    assert again["status"] == "NO_CHANGE" and len(again["history"]) == 1


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


def test_it_runs_on_the_hourly_clock_and_writes_no_number() -> None:
    hc = (_DESK / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert '"cert_book_door", "research/cert_book_door.py"))' in hc
    src = (_DESK / "research" / "cert_book_door.py").read_text(encoding="utf-8")
    assert "del block[key]" in src
    assert not re.search(r"block\[key\]\s*=[^=]", src), "the door never writes a number"
