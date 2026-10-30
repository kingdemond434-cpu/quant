"""NO ACCOUNT GOES OPPOSITE ANOTHER, FTMO INCLUDED (zuck 2026-10-29, on the copy override).

The FTMO sleeve executor reads the Fusion and E8 books before it sends; this is the other way: the
Fusion gateway and the E8 executor read the FTMO book (`cross_account.ftmo_block`). Gold is left
to the gold direction lock, which already spans every declared gold lane.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
if str(_DESK) not in sys.path:
    sys.path.insert(0, str(_DESK))

from mt5desk import cross_account as xa  # noqa: E402

LOGIN, SERVER = "5550001", "FTMO-Server"


@pytest.fixture
def ftmo(_cross_account_books_in_tmp: Path) -> Path:
    """The FTMO account declared beside the tmp XACCT_DIR; returns data/ (XACCT_DIR's parent)."""
    data = xa.XACCT_DIR.parent
    (data / xa.FTMO_ACCOUNT_NAME).write_text(json.dumps({"login": LOGIN, "server": SERVER}))
    yield data
    for name in (xa.FTMO_ACCOUNT_NAME, xa.FTMO_EXECUTOR_ARMED_NAME):
        (data / name).unlink(missing_ok=True)


def _publish(book: dict, *, at: datetime | None = None) -> None:
    xa.publish("ftmo", book, source="test", key=xa.account_key(LOGIN, SERVER), now=at)


def test_no_ftmo_book_and_no_armed_executor_blocks_nothing(ftmo: Path) -> None:
    assert xa.ftmo_block("AUDNZD", "buy") is None


def test_the_opposite_side_of_an_ftmo_holding_is_refused(ftmo: Path) -> None:
    _publish({"AUDNZD": {"long": False, "short": True}})
    assert "ftmo holds or rests a short" in xa.ftmo_block("AUDNZD", "buy")
    assert xa.ftmo_block("AUDNZD.pro", "long")
    assert xa.ftmo_block("AUDNZD", "sell") is None              # the same side: the copy override
    assert xa.ftmo_block("EURUSD", "buy") is None


def test_gold_is_left_to_the_gold_direction_lock(ftmo: Path) -> None:
    _publish({"XAUUSD": {"long": True, "short": True}})
    assert xa.ftmo_block("XAUUSD", "sell_stop") is None
    assert xa.ftmo_block("GOLD", "buy") is None


def test_an_unreadable_symbol_is_not_taken_for_gold(ftmo: Path) -> None:
    (ftmo / xa.FTMO_EXECUTOR_ARMED_NAME).write_text("")
    assert xa.ftmo_block("??", "buy")                           # armed, no book: fail closed


@pytest.mark.parametrize("book", ["absent", "stale", "other_account"])
def test_an_armed_executor_without_a_fresh_book_of_its_account_fails_closed(
        ftmo: Path, book: str) -> None:
    (ftmo / xa.FTMO_EXECUTOR_ARMED_NAME).write_text("")
    if book == "stale":
        _publish({}, at=datetime.now(tz=UTC) - timedelta(hours=1))
    elif book == "other_account":                               # the terminal moved account
        _publish({})
        (ftmo / xa.FTMO_ACCOUNT_NAME).write_text(json.dumps({"login": "5550002",
                                                              "server": SERVER}))
    why = xa.ftmo_block("AUDNZD", "buy")
    assert why and "fail closed" in why


def test_unarmed_the_last_published_book_still_fences_whatever_its_age(ftmo: Path) -> None:
    _publish({"AUDNZD": {"long": True, "short": False}},
             at=datetime.now(tz=UTC) - timedelta(days=2))
    assert xa.ftmo_block("AUDNZD", "sell")
    assert xa.ftmo_block("AUDNZD", "buy") is None


def test_an_in_flight_ftmo_send_holds_both_sides(ftmo: Path) -> None:
    (ftmo / xa.FTMO_EXECUTOR_ARMED_NAME).write_text("")
    _publish({})
    xa.mark_inflight("ftmo", "NZDCAD")
    assert xa.ftmo_block("NZDCAD", "buy") and xa.ftmo_block("NZDCAD", "sell")


def test_the_pairing_of_fusion_and_e8_is_unchanged() -> None:
    assert xa.ACCOUNTS == ("fusion", "e8") and xa.other("e8") == "fusion"
    with pytest.raises(ValueError):
        xa.other("ftmo")


@pytest.mark.parametrize(("path", "calls"), [("mt5desk/gateway.py", 3),
                                             ("prop/e8_executor.py", 1)])
def test_every_fusion_and_e8_send_site_reads_the_ftmo_book(path: str, calls: int) -> None:
    """Every site that reads the other account's book for an opposite-side refusal reads FTMO's
    too: one per `opposite_block` against the E8 book (gateway) or the Fusion book (E8)."""
    src = (_DESK / path).read_text(encoding="utf-8")
    assert src.count("_xa.ftmo_block(") == calls
    other = "e8" if "gateway" in path else "fusion"
    assert src.count(f'account="{other}",') == calls
