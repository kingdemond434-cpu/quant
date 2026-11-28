"""kelly_sizing.CODE_BOOK_OPEN: the code-side opening laid over the box's CERT_BOOK_LIVE.json
(2026-11-18, D-20261118-001: E8 trades USDJPY session_range_breakout daily at 0.004).

Pinned: it lifts a 0.0 or absent key on a VALID block only, never lowers a positive file value,
never opens a void book, never touches another venue, and leaves the gold windows alone."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

from mt5desk import kelly_sizing as ks  # noqa: E402

KEY = "USDJPY_session_range_breakout_asia"


def _book(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "CERT_BOOK_LIVE.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_the_opening_is_the_principals_approved_target() -> None:
    assert ks.CODE_BOOK_OPEN == {"e8": {KEY: 0.004}, "ftmo": {KEY: 0.004}}


def test_a_file_zero_is_lifted(tmp_path: Path) -> None:
    p = _book(tmp_path, {"enabled": True, "e8": {"gold_asia": 0.006, KEY: 0.0}})
    assert ks.load_cert_book(p, "e8") == {"gold_asia": 0.006, KEY: 0.004}


def test_an_absent_key_is_added(tmp_path: Path) -> None:
    p = _book(tmp_path, {"enabled": True, "e8": {"gold_asia": 0.006}})
    assert ks.load_cert_book(p, "e8") == {"gold_asia": 0.006, KEY: 0.004}


def test_a_positive_file_value_wins(tmp_path: Path) -> None:
    p = _book(tmp_path, {"enabled": True, "e8": {KEY: 0.002}})
    assert ks.load_cert_book(p, "e8") == {KEY: 0.002}


@pytest.mark.parametrize("doc", [
    {"enabled": False, "e8": {KEY: 0.0}},
    {"enabled": True, "e8": {}},
    {"enabled": True, "e8": {KEY: "x"}},
    {"enabled": True, "e8": {KEY: 0.5}},
    {"enabled": True, "fusion": {"gold_asia": 0.0}},
])
def test_a_void_book_stays_void(tmp_path: Path, doc: dict) -> None:
    assert ks.load_cert_book(_book(tmp_path, doc), "e8") is None


def test_other_venues_and_gold_windows_are_untouched(tmp_path: Path) -> None:
    p = _book(tmp_path, {"enabled": True,
                         "e8": {"gold_asia": 0.006, "gold_london_am": 0.0, "gold_afternoon": 0.0},
                         "fusion": {KEY: 0.0}, "ftmo": {"gold_asia": 0.009}})
    e8 = ks.load_cert_book(p, "e8")
    assert e8 is not None and e8["gold_london_am"] == 0.0 and e8["gold_afternoon"] == 0.0
    assert ks.load_cert_book(p, "fusion") == {KEY: 0.0}
    assert ks.load_cert_book(p, "ftmo") == {"gold_asia": 0.009, KEY: 0.004}


def test_ftmo_still_needs_the_allocators_own_solve() -> None:
    """The FTMO opening is a ceiling: with no solved fraction for the key, nothing is sent."""
    from datetime import UTC, datetime
    from prop import ftmo_executor as fx
    now = datetime.now(tz=UTC)
    alloc = {"generated_at": now.isoformat(), "deployable": True,
             "specs": {KEY: {"symbol": "USDJPY"}}, "executable": {}}
    assert fx.book_sleeves(alloc, {KEY: 0.004}, now)[0] == []
    alloc["executable"] = {KEY: 0.002}
    assert fx.book_sleeves(alloc, {KEY: 0.004}, now)[0] == [(KEY, 0.002, {"symbol": "USDJPY"})]
    alloc["executable"] = {KEY: 0.01}
    assert fx.book_sleeves(alloc, {KEY: 0.004}, now)[0][0][1] == 0.004


def test_the_gold_windows_stay_pinned_in_code() -> None:
    """The gold-asia-only ORDER is reversed, but london_am and afternoon stay at 0 as evidence
    zeros (non-positive realised and replayed R) until their lift rule is met."""
    from mt5desk import decision_core as dc
    for venue in ("e8", "fusion"):
        assert dc.principal_zero("gold_london_am", venue)
        assert dc.principal_zero("gold_afternoon", venue)
        assert not dc.principal_zero("gold_asia", venue)
