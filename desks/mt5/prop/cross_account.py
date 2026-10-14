"""CROSS-ACCOUNT HEDGE GUARD -- an E8 entry never opens against the Fusion book.

E8's rules treat OPPOSITE trades on the same symbol across any two accounts the trader holds
as banned hedging, and that includes the Fusion account (E8 payout-limits review, 2026-10-13).
A breach can void the account and its payouts, so it is a venue rule the desk obeys, not a
risk preference: one skipped E8 entry costs one trade, one breach costs the account.

WHAT IT DOES. Before an E8 lane opens anything it asks `refusal(symbol, side, fusion)`, where
`fusion` is Fusion's open book as `{SYMBOL: {+1, -1}}` from `fusion_book`. An entry whose side
is opposite to a side Fusion holds on the same symbol is refused, with the reason. An agreeing
entry passes, so the guard never stops the two accounts trading the same direction together.

WHERE FUSION'S BOOK COMES FROM, best first:
  1. the terminal on this box (`mt5.positions_get`), read in the same pass. That terminal is the
     Fusion account: it is the one the gateway trades through (`mt5desk.config.terminal_path`).
  2. `data/account_positions.json` (ops/publish_account_state.py, task MT5-AccountState, every
     15 minutes) for a lane that holds no terminal handle, accepted while it is younger than
     two publisher periods.

AN UNREADABLE BOOK IS NOT A FLAT BOOK. `fusion_book` returns None when neither source answers,
and `refusal` then refuses every entry with that reason (fail closed), because a guard that
disappears whenever its input does is no guard on the day the input fails.

NOT COVERED HERE: the Fusion gateway opening against an open E8 position, and a resting E8
entry order filling after Fusion has opened the other way. `e8_gold` cancels its own resting
legs that oppose Fusion each pass (see `opposing_resting`); the gateway side needs a money-path
change of its own.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
POSITIONS_FILE = DESK / "data" / "account_positions.json"

#: MT5-AccountState's period (desks/mt5/ops/box_tasks.manifest: "every 15 minutes").
PUBLISHER_PERIOD_S = 15 * 60
#: Two periods: one missed run is tolerated, a second means the publisher has stopped.
MAX_FILE_AGE_S = 2 * PUBLISHER_PERIOD_S

#: The bracket order types each side of the book opposes (desk convention: +1 long, -1 short).
_SIDE_OF = {"buy": 1, "sell": -1, "buy_stop": 1, "sell_stop": -1,
            "buy_limit": 1, "sell_limit": -1, "long": 1, "short": -1}


def norm_symbol(symbol: Any) -> str:
    """One name across venues: upper case, letters and digits only ("XAU/USD" -> "XAUUSD")."""
    return re.sub(r"[^A-Z0-9]", "", str(symbol or "").upper())


def side_of(side: Any) -> int | None:
    """+1 / -1 for a side or an order type; None for anything this guard cannot read."""
    if isinstance(side, int | float) and side in (1, -1):
        return int(side)
    return _SIDE_OF.get(str(side or "").strip().lower())


def _add(book: dict[str, set[int]], symbol: Any, side: int | None) -> bool:
    sym = norm_symbol(symbol)
    if not sym or side is None:
        return False
    book.setdefault(sym, set()).add(side)
    return True


def book_from_terminal(mt5: Any) -> dict[str, set[int]] | None:
    """Fusion's open sides per symbol, read from the terminal now; None when it will not say."""
    try:
        rows = mt5.positions_get()
    except Exception:
        return None
    if rows is None:
        return None
    book: dict[str, set[int]] = {}
    for p in rows:
        kind = getattr(p, "type", None)
        side = None if kind is None else (1 if int(kind) == 0 else -1 if int(kind) == 1 else None)
        if not _add(book, getattr(p, "symbol", None), side):
            return None      # a position whose side or symbol is unreadable: not a flat book
    return book


def book_from_file(path: Path = POSITIONS_FILE, *, now: datetime | None = None,
                   max_age_s: float = MAX_FILE_AGE_S) -> dict[str, set[int]] | None:
    """Fusion's open sides per symbol from the publisher's file; None if absent, unreadable or
    older than `max_age_s`."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        at = datetime.fromisoformat(str(doc["updated_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    age = ((now or datetime.now(tz=UTC)) - at).total_seconds()
    if not (0 <= age <= max_age_s):
        return None
    book: dict[str, set[int]] = {}
    for p in doc.get("positions") or []:
        if not isinstance(p, dict) or not _add(book, p.get("symbol"), side_of(p.get("side"))):
            return None
    return book


def fusion_book(mt5: Any = None, *, path: Path = POSITIONS_FILE,
                now: datetime | None = None) -> tuple[dict[str, set[int]] | None, str]:
    """(book, source). The terminal when a handle is given and it answers, else the file."""
    if mt5 is not None:
        book = book_from_terminal(mt5)
        if book is not None:
            return book, "terminal"
    book = book_from_file(path, now=now)
    if book is not None:
        return book, "account_positions.json"
    return None, "UNREADABLE"


def refusal(symbol: Any, side: Any, fusion: dict[str, set[int]] | None,
            source: str = "") -> str | None:
    """Why an E8 entry on `symbol` with `side` must not be sent, or None when it may be."""
    s = side_of(side)
    if fusion is None:
        return ("CROSS_ACCOUNT_UNREAD: Fusion's open book could not be read "
                f"({source or 'no source'}), so an E8 entry cannot be shown not to hedge it")
    if s is None:
        return f"CROSS_ACCOUNT_UNREAD: the entry side {side!r} is unreadable"
    held = fusion.get(norm_symbol(symbol)) or set()
    if -s in held:
        return (f"CROSS_ACCOUNT_HEDGE: Fusion holds {'short' if s == 1 else 'long'} "
                f"{norm_symbol(symbol)}; an E8 {'long' if s == 1 else 'short'} on the same "
                "symbol is opposite-account hedging, which E8 bans")
    return None


def opposing_resting(legs: dict[str, dict], symbol: Any,
                     fusion: dict[str, set[int]] | None) -> list[tuple[str, int]]:
    """Resting entry legs ({order_type: {"id": ...}}) that would open against Fusion if filled.
    An unreadable book cancels nothing here: cancelling on no information is its own harm, and
    new placements are already refused on it."""
    if fusion is None:
        return []
    out: list[tuple[str, int]] = []
    for kind, leg in (legs or {}).items():
        oid = (leg or {}).get("id")
        if oid is not None and refusal(symbol, kind, fusion) is not None:
            out.append((kind, int(oid)))
    return out
