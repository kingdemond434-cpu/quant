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
send and its publish. EVERY publish runs under it too, from a reading taken under it
(`publish_under_lock`), so a snapshot taken before another lane's send can never overwrite the
book that send produced (audit round 2, must-fix 2). A lock that cannot be taken within its wait
refuses the order (fail closed) and skips the publish (the book ages, and the reader fails closed
on age). The lock is OWNED: it carries a random token, is released only by its owner, and is
broken only when its holder is provably gone (`_holder_gone`) -- never merely because it is old,
which on POSIX let a second lane steal a live lock. Every wait sleeps and has a deadline, and a
break that the OS refuses (Windows WinError 5/32 on a file another process holds) is retried
until that deadline, never spun on. Stop management never takes this lock.

THE BOOKS NAME THEIR ACCOUNT, HASHED (`account_key`): a book of the wrong account is refused. The
key is a truncated SHA-256 of "<login>@<server>", never the login itself, and no log line or
report prints it.

Pure functions over readings, plus small atomic file helpers. Never sends anything.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import socket
import time
import uuid
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

#: How long a PUBLISH waits for the lock before skipping (the reader fails closed on age).
PUBLISH_WAIT_S = 2.0
#: A lock whose holder cannot be shown alive or dead (no pid, other host, no `psutil` on Windows)
#: is broken only past this age: a send under the lock takes seconds, so this is a dead holder.
LOCK_ABANDONED_S = 900.0
_POLL_S = 0.2

Exposure = dict[str, dict[str, bool]]

#: Broker names for one instrument that no suffix rule recovers.
ALIASES = {"GOLD": "XAUUSD", "SILVER": "XAGUSD"}
_CANON = re.compile(r"^[A-Z0-9]{3,12}$")


def norm(symbol: object) -> str:
    """One instrument, one name on both venues. `XAUUSD`, `XAUUSD+`, `XAUUSD.pro`, `XAUUSD_i`,
    `XAUUSD#`, `XAUUSDm` (a lower-case broker suffix after an upper-case code), `GOLD` and
    `xau/usd` are all XAUUSD. A name that does not reduce to a plain code is returned as "",
    which every caller treats as unreadable (fail closed)."""
    raw = re.split(r"[._#]", str(symbol or "").strip(), maxsplit=1)[0]
    m = re.match(r"^(.*[A-Z0-9])[a-z]+$", raw)
    if m and re.search(r"[A-Z]", m.group(1)):
        raw = m.group(1)
    s = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    s = ALIASES.get(s, s)
    return s if _CANON.match(s) else ""


def same_instrument(a: str, b: str) -> bool:
    """Equal, or one a code-prefix of the other (`XAUUSDX` vs `XAUUSD`): an unknown suffix is
    read as the same instrument, so a name this module does not know blocks rather than passes."""
    if not a or not b:
        return True
    return a == b or (min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a)))


def account_key(login: object, server: object) -> str:
    """A truncated SHA-256 of "<login>@<server>": names the account in a book without carrying
    the login. RAISES on an unreadable login or server: a book of an unnamed account is no
    book."""
    if login in (None, "") or isinstance(login, bool) or server in (None, ""):
        raise ValueError("the account's login or server is unreadable")
    return "sha256:" + hashlib.sha256(f"{login}@{server}".encode()).hexdigest()[:16]


def mt5_account_key(mt5: Any) -> str:
    acc = mt5.account_info()
    if acc is None:
        raise ValueError("the MT5 terminal did not answer account_info")
    return account_key(getattr(acc, "login", None), getattr(acc, "server", None))


def tradelocker_account_key(venue: Any) -> str:
    """The TradeLocker account: the SDK's account id, else the credentials' user on its server."""
    api = getattr(venue, "_raw_api", None)
    if api is None:
        try:
            api = venue._api
        except Exception:
            api = None
    server = None
    creds = getattr(venue, "_creds", None)
    if creds is not None:
        server = getattr(creds, "server", None)
    for attr in ("acc_id", "account_id", "acc_num"):
        v = getattr(api, attr, None)
        if v not in (None, "") and not isinstance(v, bool):
            return account_key(v, server or "tradelocker")
    if creds is not None and getattr(creds, "username", None):
        return account_key(creds.username, server or "tradelocker")
    raise ValueError("the TradeLocker venue names no account")


def expected_key(account: str) -> str | None:
    """The key the box DECLARES for `account`, or None when it declares none. Only the Fusion
    live account is declared (decision_core.FUSION_ACCOUNT_FILE, gitignored)."""
    if account != "fusion":
        return None
    try:
        from mt5desk import decision_core as _dc
        login, _ = _dc.fusion_live_login()
        return account_key(login, _dc.FUSION_LIVE_SERVER) if login is not None else None
    except Exception:
        return None


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
            raise ValueError("a position or pending entry has no readable symbol (or one that "
                             "does not reduce to a plain instrument code)")
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

    TradeLocker carries a position's protective stop and target as separate resting orders. An
    order is protective ONLY when an open position names it (`stopLossId` / `takeProfitId` /
    `stopOrderId` / `takeProfitOrderId`) or it names an open position (`positionId`). Every other
    resting order is an ENTRY with its own side -- with or without a `stopLoss` (round 2 skipped
    an entry with no stopLoss, which failed open). Instruments are named through the venue's own
    catalogue; an instrument the catalogue cannot name RAISES, because an unnamed position could
    be on any symbol."""
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
    protective: set[str] = set()
    position_ids: set[str] = set()
    for p in positions:
        if p.get("id") is not None:
            position_ids.add(str(p.get("id")))
        for k in ("stopLossId", "takeProfitId", "stopOrderId", "takeProfitOrderId"):
            if p.get(k) not in (None, "", 0):
                protective.add(str(p.get(k)))
    for o in orders:
        if str(o.get("id")) in protective or (o.get("positionId") not in (None, "", 0)
                                              and str(o.get("positionId")) in position_ids):
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


def publish(account: str, exposure: Exposure, *, source: str, key: str,
            now: datetime | None = None) -> Path:
    """Write `account`'s book atomically. Raises on failure (the caller logs it).

    Call it UNDER `placement_lock`, from a reading taken under it (`publish_under_lock` does
    both): a book written from an older snapshot can erase another lane's fresh send."""
    if not (isinstance(key, str) and key.startswith("sha256:")):
        raise ValueError("a book must carry its account key")
    p = book_path(account)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"account": account, "account_key": key,
           "at": (now or datetime.now(tz=UTC)).isoformat(),
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


def mt5_book_checked(mt5: Any, account: str = "fusion") -> tuple[Exposure | None, str]:
    """(`account`'s book read LIVE from the terminal under `mt5`, why). None when it cannot be
    read, or when the terminal is on another account than the one this box declares."""
    try:
        book = mt5_exposure(mt5)
        key = mt5_account_key(mt5)
    except Exception as exc:
        return None, f"the {account} terminal book is unreadable ({type(exc).__name__}: {exc})"
    want = expected_key(account)
    if want is not None and key != want:
        return None, (f"the terminal is not on the declared {account} account; its book is "
                      f"not that account's")
    return book, f"{account} book read live"


def publish_mt5(mt5: Any, *, source: str, account: str = "fusion") -> Path:
    """Publish the book of the MT5 account under `mt5`, read NOW. Call under the lock."""
    return publish(account, mt5_exposure(mt5), source=source, key=mt5_account_key(mt5))


def publish_tradelocker(venue: Any, *, source: str) -> Path:
    """Publish the E8 book, read from TradeLocker NOW. Call under the lock."""
    return publish("e8", tradelocker_exposure(venue), source=source,
                   key=tradelocker_account_key(venue))


def publish_under_lock(fn: Any, *, holder: str, wait_s: float = PUBLISH_WAIT_S) -> str | None:
    """Take the lock (briefly), run `fn` -- a publish that reads fresh -- and release. Returns
    None, or why nothing was published. Never raises. A lock already held by this process is
    re-entered, so this is safe inside a placement."""
    try:
        with placement_lock(holder, wait_s=wait_s) as ok:
            if not ok:
                return "the placement lock is held elsewhere; not published (the book ages)"
            fn()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"[:200]
    return None


def read_book(account: str, *, now: datetime | None = None, max_age_s: float = MAX_AGE_S,
              expect_key: str | None = None) -> tuple[Exposure | None, str]:
    """(`account`'s published book, why). None when absent, unreadable, unstamped, stale, of no
    named account, or of another account than the one the box declares (`expected_key`)."""
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
        key = doc.get("account_key")
        if not (isinstance(key, str) and key.startswith("sha256:")):
            raise ValueError("the book names no account")
        book: Exposure = {}
        for k, v in symbols.items():
            sym = norm(k)
            if not sym:
                raise ValueError("the book carries a symbol that is not a plain code")
            book[sym] = {"long": bool(v.get("long")), "short": bool(v.get("short"))}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        return None, f"the {account} book is malformed ({type(exc).__name__}: {exc})"
    if not (-60.0 <= age <= max_age_s):
        return None, (f"the {account} book is {age:.0f}s old (limit {max_age_s:.0f}s); the "
                      f"{account} account's positions are unknown now")
    want = expect_key if expect_key is not None else expected_key(account)
    if want is not None and key != want:
        return None, (f"the {account} book is of another account than the one this box "
                      f"declares; its positions are not this account's")
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
    sym = norm(symbol)
    if not sym:
        return f"cross-account fence: unreadable order symbol {symbol!r}; fail closed"
    opposite = "short" if want == "long" else "long"
    for bsym, row in book.items():
        if same_instrument(bsym, sym) and row.get(opposite):
            return (f"cross-account fence: {account} holds or rests a {opposite} on {bsym}; "
                    f"a {want} on {sym} here would hedge the other account")
    return None


#: Tokens this process holds now (re-entry) and tokens it released but could not unlink.
_HELD: dict[str, int] = {}
_RELEASED: set[str] = set()
#: After a lock wait that ran out, every wait in this process is 0 for this long: a stuck lock
#: costs one wait per pass, not one per sleeve or window (stop management is never delayed by
#: more than that one wait, and never takes the lock at all).
MISS_COOLDOWN_S = 60.0
_MISSED_AT: list[float] = []
_HOST = socket.gethostname()


def _pid_alive(pid: int) -> bool | None:
    """True / False when this host can tell, None when it cannot. NEVER `os.kill(pid, 0)` on
    Windows: there it calls TerminateProcess."""
    try:
        import psutil
        return bool(psutil.pid_exists(int(pid)))
    except Exception:
        pass
    if os.name == "nt":
        return None
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, OverflowError):
        return None
    return True


def _read_lock(path: Path) -> dict[str, Any] | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except (OSError, ValueError):
        return None


def _holder_gone(doc: dict[str, Any] | None, age_s: float) -> bool:
    """A lock may be broken ONLY when its holder is provably gone: this process released it
    (and its unlink failed), or the holder's pid on this host is dead, or -- when nothing can be
    proven -- it is older than `LOCK_ABANDONED_S`. A live holder is never broken, however old."""
    if doc is None:
        return age_s > LOCK_STALE_S                    # torn/unreadable: a creator that died
    if str(doc.get("token") or "") in _RELEASED:
        return True
    if doc.get("host") == _HOST and isinstance(doc.get("pid"), int):
        alive = _pid_alive(int(doc["pid"]))
        if alive is False:
            return True
        if alive is True:
            return False
    return age_s > LOCK_ABANDONED_S


@contextlib.contextmanager
def placement_lock(holder: str, *, wait_s: float = LOCK_WAIT_S,
                   stale_s: float = LOCK_STALE_S) -> Iterator[bool]:
    """Exclusive cross-process lock for read-other / send / publish-own. Yields whether it was
    taken; the caller refuses the order (or skips the publish) when it was not.

    Re-entrant within one process. Every wait sleeps `_POLL_S` and ends at `wait_s`. The file
    is closed as soon as it is written, so no handle of ours ever blocks another process's
    break on Windows; ownership is the token inside it, and release unlinks only our own token.
    `stale_s` is kept for callers; the break rule is `_holder_gone`."""
    del stale_s
    path = XACCT_DIR / "placement.lock"
    key = str(path)
    if _HELD.get(key):
        _HELD[key] += 1
        try:
            yield True
        finally:
            _HELD[key] -= 1
        return
    token = uuid.uuid4().hex
    if _MISSED_AT and time.monotonic() - _MISSED_AT[-1] < MISS_COOLDOWN_S:
        wait_s = 0.0
    deadline = time.monotonic() + max(0.0, wait_s)
    taken = False
    with contextlib.suppress(OSError):
        XACCT_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps({"holder": holder, "pid": os.getpid(), "host": _HOST,
                                         "token": token,
                                         "at": datetime.now(tz=UTC).isoformat()}).encode())
            finally:
                os.close(fd)
            taken = True
            break
        except FileExistsError:
            _try_break(path)
        except OSError:
            pass                                       # Windows: the file is mid-delete
        if time.monotonic() >= deadline:
            break
        time.sleep(_POLL_S)
    if taken:
        _HELD[key] = 1
    else:
        _MISSED_AT[:] = [time.monotonic()]
    try:
        yield taken
    finally:
        if taken:
            _HELD.pop(key, None)
            _release(path, token)


def _try_break(path: Path) -> None:
    """Break the lock at `path` if its holder is gone. Never raises; an OS refusal waits."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return
    doc = _read_lock(path)
    if not _holder_gone(doc, age):
        return
    stale_token = str((doc or {}).get("token") or "")
    moved = path.with_name(f"{path.name}.broken.{uuid.uuid4().hex}")
    try:
        os.replace(path, moved)                        # Windows: WinError 5/32 while held open
    except OSError:
        return
    # A fresh lock taken between our read and our move would now be in `moved`: put it back.
    got = _read_lock(moved)
    if stale_token and got is not None and str(got.get("token") or "") != stale_token:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, json.dumps(got).encode())
            finally:
                os.close(fd)
        except OSError:
            pass
    with contextlib.suppress(OSError):
        moved.unlink()


def _release(path: Path, token: str) -> None:
    """Unlink the lock only when it is still OURS. A refused unlink (Windows) leaves it for the
    next acquirer, which breaks it because the token is in `_RELEASED`."""
    doc = _read_lock(path)
    if doc is None or str(doc.get("token") or "") != token:
        return
    for _ in range(5):
        try:
            path.unlink()
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.05)
    _RELEASED.add(token)
