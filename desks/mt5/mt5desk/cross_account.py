"""THE CROSS-ACCOUNT OPPOSITE-SIDE FENCE: Fusion and E8 never hold opposite sides of one symbol.

WHY (audit HOLD on fusion_book_go_live 50ef074f9, 2026-10-20). The box trades two accounts on the
same instruments: the Fusion MT5 account (the gateway) and the E8 prop account (TradeLocker,
`prop/e8_gold.py` for the gold windows and `prop/e8_executor.py` for the certified non-gold book).
Each lane already refuses to hedge ITSELF (`OPPOSING_LEG`, `self_hedge_prevented`), but neither
saw the other account, so Fusion could hold the asia long while E8's london_am bracket filled
short: two spreads, two margin legs, and a combined book whose net exposure is smaller than either
account's risk.

THE RULE, NO WAIVER. An order is refused when its side is opposite an OPEN or PENDING position of
the OTHER account on the same symbol. A pending entry counts with its own side (a resting buy stop
is long), so a two-sided bracket resting on one account blocks both legs on the other until one
leg fills and the sibling is cancelled. FAILS CLOSED: a book that cannot be read, is older than
`MAX_AGE_S`, or does not cover the symbol refuses the order.

HOW EACH LANE SEES THE OTHER.
  * E8-Gold attaches to the Fusion MT5 terminal every pass (it reads its bars there), so it reads
    Fusion's book LIVE (`mt5_exposure`) and publishes it, and it publishes the E8 book it reads
    from TradeLocker.
  * The gateway publishes the Fusion book every pass and after each send, and reads the E8 book
    from the file (it has no TradeLocker session).
  * The E8 executor (no terminal) publishes the E8 book and reads the Fusion book from the file.

THE PLACEMENT LOCK closes the race between the two clocks: read-the-other, send, and publish-own
run under one exclusive lock file, so a lane never reads the other's book between the other's
send and its publish. A lock that cannot be taken within `LOCK_WAIT_S` refuses the order (fail
closed); a lock older than `LOCK_STALE_S` is a crashed holder and is broken.

Pure functions over readings, plus small atomic file helpers. Never sends anything.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parent.parent
#: Where both accounts' books and the placement lock live (state paths, box-only).
XACCT_DIR = _DESK / "data" / "xacct"
ACCOUNTS = ("fusion", "e8")
#: A book older than this is not the other account's book now. E8-Gold publishes every five
#: minutes and the gateway every pass, so three missed E8 cycles is the limit.
MAX_AGE_S = 900.0
#: How long a lane waits for the other to finish a send, and when a held lock is a dead holder.
LOCK_WAIT_S = 20.0
LOCK_STALE_S = 120.0

Exposure = dict[str, dict[str, bool]]


def norm(symbol: object) -> str:
    """`XAUUSD`, `XAUUSD+`, `XAUUSD.pro` and `xau/usd` are one instrument on both venues."""
    s = str(symbol or "").upper().split(".")[0]
    return re.sub(r"[^A-Z0-9]", "", s)


def book_path(account: str) -> Path:
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    return XACCT_DIR / f"{account}_book.json"


def other(account: str) -> str:
    if account not in ACCOUNTS:
        raise ValueError(f"unknown account {account!r}")
    return "e8" if account == "fusion" else "fusion"


def exposure_from_rows(rows: Iterable[tuple[object, object]]) -> Exposure:
    """{symbol: {"long": bool, "short": bool}} from (symbol, side) rows.

    `side` is "long"/"buy" or "short"/"sell". Anything else RAISES: a position or entry whose side
    cannot be read is not a flat book, and the caller fails closed on it."""
    out: Exposure = {}
    for symbol, side in rows:
        sym = norm(symbol)
        if not sym:
            raise ValueError("a position or pending entry has no readable symbol")
        s = str(side or "").strip().lower()
        if s in ("long", "buy"):
            key = "long"
        elif s in ("short", "sell"):
            key = "short"
        else:
            raise ValueError(f"{sym}: a position or pending entry has an unreadable side {side!r}")
        row = out.setdefault(sym, {"long": False, "short": False})
        row[key] = True
    return out


def mt5_exposure(mt5: Any) -> Exposure:
    """Every open position and every resting order on the MT5 account under this terminal.

    MT5 attaches a position's stop and target to the position itself, so every resting order is
    an entry. `positions_get()` / `orders_get()` answering None is an unreadable book (raises)."""
    positions = mt5.positions_get()
    orders = mt5.orders_get()
    if positions is None or orders is None:
        raise ValueError("the MT5 terminal did not answer positions_get/orders_get")
    rows: list[tuple[object, object]] = []
    for p in positions:
        t = int(p.type)
        rows.append((p.symbol, "long" if t == 0 else "short" if t == 1 else None))
    for o in orders:
        t = int(o.type)
        # ORDER_TYPE_BUY=0 SELL=1 BUY_LIMIT=2 SELL_LIMIT=3 BUY_STOP=4 SELL_STOP=5
        # BUY_STOP_LIMIT=6 SELL_STOP_LIMIT=7; CLOSE_BY=8 is not an entry.
        if t == 8:
            continue
        rows.append((o.symbol, "long" if t in (0, 2, 4, 6) else "short" if t in (1, 3, 5, 7)
                     else None))
    return exposure_from_rows(rows)


def tradelocker_exposure(venue: Any, positions: list[dict[str, Any]] | None = None,
                         orders: list[dict[str, Any]] | None = None) -> Exposure:
    """Every open position and every resting ENTRY on the TradeLocker account.

    TradeLocker carries a position's protective stop and target as separate resting orders with no
    stopLoss of their own; an entry carries one (`e8_executor.outstanding_stop_risk` reads them the
    same way). Instruments are named through the venue's own catalogue; an instrument the
    catalogue cannot name RAISES, because an unnamed position could be on any symbol."""
    iid_to_sym = {int(v): str(k) for k, v in (getattr(venue, "_by_key", {}) or {}).items()}
    if positions is None:
        positions = venue.positions()
    if orders is None:
        orders = venue.orders()
    if positions is None or orders is None:
        raise ValueError("the TradeLocker venue did not answer positions/orders")

    def name(row: dict[str, Any]) -> str:
        iid = row.get("tradableInstrumentId") or row.get("instrumentId")
        sym = iid_to_sym.get(int(iid)) if iid is not None else None
        if not sym:
            raise ValueError(f"instrument {iid!r} is not in the venue catalogue")
        return sym

    rows: list[tuple[object, object]] = [(name(p), p.get("side")) for p in positions]
    for o in orders:
        sl = o.get("stopLoss")
        if not (isinstance(sl, (int, float)) and not isinstance(sl, bool) and float(sl) > 0):
            continue                                    # a protective stop/target, not an entry
        rows.append((name(o), o.get("side")))
    return exposure_from_rows(rows)


def merge(a: Exposure, b: Exposure) -> Exposure:
    out: Exposure = {k: dict(v) for k, v in a.items()}
    for k, v in b.items():
        row = out.setdefault(k, {"long": False, "short": False})
        row["long"] = row["long"] or bool(v.get("long"))
        row["short"] = row["short"] or bool(v.get("short"))
    return out


def publish(account: str, exposure: Exposure, *, source: str,
            now: datetime | None = None) -> Path:
    """Write `account`'s book atomically. Raises on failure (the caller logs it)."""
    p = book_path(account)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"account": account, "at": (now or datetime.now(tz=UTC)).isoformat(),
           "source": source, "covers": "all", "symbols": exposure}
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    for attempt in range(10):
        try:
            os.replace(tmp, p)
            break
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.1)
    return p


def read_book(account: str, *, now: datetime | None = None,
              max_age_s: float = MAX_AGE_S) -> tuple[Exposure | None, str]:
    """(`account`'s published book, why). None when absent, unreadable, unstamped or stale."""
    p = book_path(account)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"the {account} book is absent or unreadable ({type(exc).__name__})"
    try:
        at = datetime.fromisoformat(str(doc["at"]))
        if at.tzinfo is None:
            raise ValueError("naive timestamp")
        age = ((now or datetime.now(tz=UTC)) - at).total_seconds()
        symbols = doc["symbols"]
        if doc.get("account") != account or doc.get("covers") != "all" \
                or not isinstance(symbols, dict):
            raise ValueError("not a full book of this account")
        book: Exposure = {norm(k): {"long": bool(v.get("long")), "short": bool(v.get("short"))}
                          for k, v in symbols.items()}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return None, f"the {account} book is malformed ({type(exc).__name__}: {exc})"
    if not (-60.0 <= age <= max_age_s):
        return None, (f"the {account} book is {age:.0f}s old (limit {max_age_s:.0f}s); the "
                      f"{account} account's positions are unknown now")
    return book, f"{account} book {age:.0f}s old"


def opposite_block(book: Exposure | None, symbol: object, side: object, *,
                   account: str, why_absent: str = "") -> str | None:
    """Why an order of `side` on `symbol` may NOT be sent against `account`'s book, or None.

    `side` is "long"/"buy"/"buy_stop"/1 or "short"/"sell"/"sell_stop"/-1."""
    if book is None:
        absent = why_absent or f"the {account} book is unreadable"
        return f"cross-account fence: {absent}; fail closed"
    s = str(side).strip().lower()
    if s in ("long", "buy", "buy_stop", "buy_limit", "1"):
        want = "long"
    elif s in ("short", "sell", "sell_stop", "sell_limit", "-1"):
        want = "short"
    else:
        return f"cross-account fence: unreadable order side {side!r}; fail closed"
    row = book.get(norm(symbol)) or {}
    opposite = "short" if want == "long" else "long"
    if row.get(opposite):
        return (f"cross-account fence: {account} holds or rests a {opposite} on {norm(symbol)}; "
                f"a {want} here would hedge the other account")
    return None


@contextlib.contextmanager
def placement_lock(holder: str, *, wait_s: float = LOCK_WAIT_S,
                   stale_s: float = LOCK_STALE_S) -> Iterator[bool]:
    """Exclusive cross-process lock for read-other / send / publish-own. Yields whether it was
    taken; the caller refuses the order when it was not."""
    XACCT_DIR.mkdir(parents=True, exist_ok=True)
    path = XACCT_DIR / "placement.lock"
    deadline = time.monotonic() + max(0.0, wait_s)
    fd: int | None = None
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, json.dumps({"holder": holder, "pid": os.getpid(),
                                     "at": datetime.now(tz=UTC).isoformat()}).encode())
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > stale_s:
                    path.unlink()
                    continue
            except OSError:
                continue
            if time.monotonic() >= deadline:
                break
            time.sleep(0.2)
    try:
        yield fd is not None
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
            with contextlib.suppress(OSError):
                path.unlink()
