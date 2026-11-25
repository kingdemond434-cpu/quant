"""ZERO LIVE ON A MARKET DAY PAGES (prop/zero_live_page.py, pass rule I2 2026-11-25)."""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import zero_live_page as z  # noqa: E402

WED = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)


def _w(p: Path, doc: Any) -> Path:
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


@pytest.fixture
def books(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(z, "E8_BOOK", tmp_path / "E8_BOOK.json")
    monkeypatch.setattr(z, "FTMO_BOOK", tmp_path / "FTMO_ALLOCATOR.json")
    monkeypatch.setattr(z, "SLEEVES", tmp_path / "sleeves.json")
    monkeypatch.setattr(z, "PAUSE", tmp_path / "GATEWAY_PAUSED")
    return tmp_path


def _live(t: Path, at: datetime = WED) -> None:
    _w(t / "E8_BOOK.json", {"generated_utc": at.isoformat(), "sleeves": [{"symbol": "USDJPY"}]})
    _w(t / "FTMO_ALLOCATOR.json", {"generated_at": at.isoformat(), "deployable": True,
                                   "executable": {"USDJPY_x": 0.002}})
    _w(t / "sleeves.json", {"sleeves": [{"status": "LIVE"}]})


@pytest.mark.parametrize("when, open_", [
    (datetime(2026, 11, 25, 3, tzinfo=UTC), True),     # Wednesday
    (datetime(2026, 11, 28, 12, tzinfo=UTC), False),   # Saturday
    (datetime(2026, 11, 29, 21, tzinfo=UTC), False),   # Sunday before the open
    (datetime(2026, 11, 29, 22, tzinfo=UTC), True),    # Sunday open
    (datetime(2026, 11, 27, 22, tzinfo=UTC), False),   # Friday close
])
def test_market_day(when: datetime, open_: bool) -> None:
    assert z.market_day(when) is open_


def test_every_account_live_is_ok(books: Path) -> None:
    _live(books)
    doc = z.assess(WED)
    assert doc["status"] == "OK" and not doc["page"] and doc["not_trading"] == []


def test_an_empty_e8_book_pages_with_its_stops(books: Path) -> None:
    _live(books)
    _w(books / "E8_BOOK.json", {"generated_utc": WED.isoformat(), "sleeves": [],
                                "n_certified": 19, "n_tradeable": 5,
                                "blocked_by_integrity": [{"why": "PRINCIPAL_ZERO"}] * 3,
                                "stress": {"cuts": [{}, {}]}})
    doc = z.assess(WED)
    assert doc["page"] and doc["not_trading"] == ["e8"]
    stops = " ".join(doc["accounts"]["e8"]["stops"])
    assert "PRINCIPAL_ZERO (x3)" in stops and "stress cap cut 2" in stops


def test_a_stale_or_unreadable_book_is_unmeasured_and_pages(books: Path) -> None:
    _live(books, at=WED - timedelta(hours=7))
    _w(books / "sleeves.json", {"sleeves": [{"status": "LIVE"}]})
    doc = z.assess(WED)
    assert doc["accounts"]["e8"]["status"] == z.UNMEASURED
    assert doc["accounts"]["ftmo"]["status"] == z.UNMEASURED
    assert doc["page"] and doc["not_trading"] == ["e8", "ftmo"]


def test_an_undeployable_ftmo_book_is_zero(books: Path) -> None:
    _live(books)
    _w(books / "FTMO_ALLOCATOR.json", {"generated_at": WED.isoformat(), "deployable": False,
                                       "executable": {"a": 0.002}, "status": "OK",
                                       "phases": {"phase1": {"status": "VALIDATION_FAILED"}}})
    doc = z.assess(WED)
    assert doc["accounts"]["ftmo"]["status"] == z.ZERO
    assert any("VALIDATION_FAILED" in s for s in doc["accounts"]["ftmo"]["stops"])


def test_a_paused_unfunded_fusion_is_reported_never_paged(books: Path) -> None:
    _live(books)
    _w(books / "sleeves.json", {"sleeves": [{"status": "STANDBY"}]})
    (books / "GATEWAY_PAUSED").write_text("", encoding="utf-8")
    doc = z.assess(WED)
    assert doc["accounts"]["fusion"]["status"] == z.PAUSED and not doc["page"]


def test_nothing_pages_on_a_closed_market(books: Path) -> None:
    doc = z.assess(datetime(2026, 11, 28, 12, tzinfo=UTC))
    assert doc["status"] == "CLOSED" and not doc["page"] and doc["not_trading"]


def test_the_page_goes_through_provenance(books: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from libs.ops import provenance
    sent: list[tuple[str, ...]] = []
    monkeypatch.setattr(provenance, "_page",
                        lambda *a: sent.append(a) or {"sent": False, "queued": True})
    _w(books / "E8_BOOK.json", {"generated_utc": WED.isoformat(), "sleeves": []})
    doc = z.assess(WED)
    res = z._send(doc)
    assert res["queued"] and sent[0][0] == z.ALERT_ID and sent[0][1] == "OPEN"
    assert "e8" in sent[0][3]
