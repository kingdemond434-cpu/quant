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
key is the desk's ONE account key, `libs.ops.provenance.account_key` (publish_sync v5/v5c: a keyed
HMAC of "<login>@<server>" under the box key, login and server normalised inside it) -- this
module never hashes on its own (auditor key-join ruling, r7). Where that function cannot be
imported, or returns None (no box key, an unreadable login, a TradeLocker server that cannot be
read), the key is UNRESOLVABLE and the fence FAILS CLOSED: no book is published, and a declared
account whose key cannot be resolved refuses every book -- an unresolvable key never reads as
"the other account holds nothing". It is never the login itself, and no log line or
report prints it. Its VALUE is checked, not only its presence: it must be exactly
`sha256:<16 hex>` (`KEY_RE`), and when the box declares an account (Fusion's login in the
gitignored FUSION_LIVE_ACCOUNT.json; E8's key in the gitignored `E8_ACCOUNT_FILE`) a book of any
other key is refused by the reader and never written by the publisher.

A SEND UNDER THE LOCK IS BOUNDED (`bounded`, audit round 4): a TradeLocker call that hangs would
otherwise hold the lock, and fail every lane's new entries closed, for as long as it hangs. Past
`LOCKED_SEND_TIMEOUT_S` the caller gets `LockedCallTimeout`, the lock is released, and the call is
treated as a failed send that MAY STILL LAND -- the lane's own reconciliation (E8-Gold adopts a
failed send that landed) owns it from there.

Pure functions over readings, plus small atomic file helpers. Never sends anything.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import socket
import threading
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
#: Every account that publishes a book here. FTMO is a third, one-way peer (2026-10-29, zuck: no
#: account may go opposite another): it publishes its book and reads the other two, and the
#: Fusion and E8 lanes read it through `ftmo_block`. It is not in ACCOUNTS, whose pairing
#: (`other`) and gold direction lock stay as they were.
PEERS = ("fusion", "e8", "ftmo")
#: The FTMO account this box trades, declared by the principal (gitignored; login, server, ...),
#: and the FTMO sleeve executor's arm file: while it exists the FTMO book is a fence that fails
#: closed (absent or stale -> refused); without it, the last published book still fences. Both
#: live in data/, beside XACCT_DIR, and are resolved from it at call time, so a test that moves
#: XACCT_DIR (the conftest does, for every test) never reads the box's real declaration.
FTMO_ACCOUNT_NAME = "FTMO_LIVE_ACCOUNT.json"
FTMO_EXECUTOR_ARMED_NAME = "FTMO_EXECUTOR_ARMED"
#: Gold is fenced across every account by the gold direction lock (`gold_oco`), FTMO included
#: once declared in its lanes, so `ftmo_block` leaves it to that lock.
FTMO_FENCE_SKIPS = ("XAUUSD",)
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
#: The longest one send (or one publish) may run while it holds the placement lock.
LOCKED_SEND_TIMEOUT_S = 30.0
LOCKED_PUBLISH_TIMEOUT_S = 10.0
#: The only shape an account key has (`account_key`).
KEY_RE = re.compile(r"^sha256:[0-9a-f]{16}$")
#: The E8 account this box trades, declared by the operator as {"account_key": "sha256:..."}
#: (gitignored; the key is the one E8-Gold publishes in data/xacct/e8_book.json). Absent: the key
#: is format-checked only.
E8_ACCOUNT_FILE = _DESK / "data" / "E8_ACCOUNT.json"

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
    whole = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
    if whole in ALIASES:
        return ALIASES[whole]                         # `Gold`, `gold`, `Silver`: case never matters
    m = re.match(r"^(.*[A-Z0-9])[a-z]+$", raw)
    # A lower-case broker suffix is stripped only after a code of at least four characters:
    # `XAUUSDm` -> XAUUSD, `US30m` -> US30, but `Gold` is not `G` and `EURusd` is not `EUR`.
    if m and re.search(r"[A-Z]", m.group(1)) and len(re.sub(r"[^A-Za-z0-9]", "",
                                                             m.group(1))) >= 4:
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


def account_key(login: object, server: object) -> str | None:
    """The account's key, from the desk's ONE key function `libs.ops.provenance.account_key`
    (which normalises the login and strips the server itself), or None -- UNRESOLVABLE, and every
    caller fails closed on it. None when provenance cannot be imported (a tree without
    publish_sync v5), when it returns None (no box key, an unreadable login), raises, or returns
    anything but `sha256:<16 hex>`. There is NO local hash to fall back to: two functions that
    hash one account two ways are how keys stop joining (auditor key-join ruling, r7)."""
    prov = _provenance()
    if prov is None:
        return None
    try:
        key = prov.account_key(login, server, create=False)
    except Exception:
        return None
    return key if valid_key(key) else None


def _provenance() -> Any:
    """`libs.ops.provenance`, imported at call time (so a box that gains it needs no restart of
    this module's importers' logic), or None when it is not importable."""
    try:
        from libs.ops import provenance as prov
    except Exception:
        return None
    return prov if callable(getattr(prov, "account_key", None)) else None


def norm_login(login: object) -> str:
    """ONE LOGIN TYPE AT EVERY CALL (auditor, r6): an int, an integral float and a digit string
    are the same account (`7000001`, `7000001.0`, `" 7000001 "` -> "7000001"); a username keeps
    its own text, stripped. Every `account_key` caller -- the terminal's int login, the box's
    declared login, the TradeLocker acc_id -- therefore names one account one way."""
    if isinstance(login, int) and not isinstance(login, bool):
        return str(login)
    if isinstance(login, float) and login.is_integer():
        return str(int(login))
    text = str(login).strip()
    return str(int(text)) if text.isdigit() else text


def mt5_identity(mt5: Any) -> tuple[object, object]:
    """(login, server) of the MT5 account under `mt5`. RAISES when the terminal does not answer.
    The pair is an INPUT to a key function only: never store, log or print it."""
    acc = mt5.account_info()
    if acc is None:
        raise ValueError("the MT5 terminal did not answer account_info")
    return getattr(acc, "login", None), getattr(acc, "server", None)


def mt5_account_key(mt5: Any) -> str:
    """The MT5 terminal's account key. RAISES when it is unresolvable (every caller fails closed
    on the exception: no book is read as this account's, none is published)."""
    acc = mt5.account_info()
    if acc is None:
        raise ValueError("the MT5 terminal did not answer account_info")
    key = account_key(getattr(acc, "login", None), getattr(acc, "server", None))
    if key is None:
        raise ValueError("the MT5 account key is unresolvable (libs.ops.provenance absent, no "
                         "box key, or an unreadable login); fail closed")
    return key


#: Why an E8 key is unresolvable (the statuses of bracket v5.1's `prop/e8_evidence`).
TL_OK, TL_LOGIN_UNREADABLE, TL_SERVER_UNREADABLE, TL_KEY_UNAVAILABLE = (
    "OK", "LOGIN_UNREADABLE", "SERVER_UNREADABLE", "KEY_UNAVAILABLE")
#: The alert a missing E8 server or login opens in the desk's alert ledger
#: (`libs.ops.alert_ledger.AlertLedger`, the path bracket v5.1's e8_evidence pages through).
TL_ALERT_ID = "xacct_e8_account_key_unresolvable"
ALERT_LEDGER_ENV = "E8_ALERT_LEDGER"
ALERT_LEDGER = _DESK.parent.parent / "data" / "alert_ledger.json"


def _tl_api(venue: Any) -> Any:
    api = getattr(venue, "_raw_api", None)
    if api is not None:
        return api
    try:
        return venue._api
    except Exception:
        return None


def tradelocker_identity(venue: Any) -> tuple[Any, str | None, str]:
    """(login, server, status) of the E8 account, by EXACTLY bracket v5.1's `e8_evidence` rule,
    so an OCO book, an evidence row and a stop exit key one account one way:

      * login: TLAPI `account_id`, else `acc_id` (None, "", "0" and bools skipped), as the SDK
        holds it (`provenance.account_key` normalises it). NEVER `acc_num`: it is the account's
        index on the user (1, 2, ...), not its id.
      * server: `api._credentials["server"]` (TLAPI 0.56.2 keeps {"username", "password",
        "server"}; only the server is read). NEVER `api.server` (TLAPI has none: it reads None),
        never the venue's `_creds.server`, never a "tradelocker" default.

    Never raises."""
    try:
        api = _tl_api(venue)
        login = None
        for attr in ("account_id", "acc_id"):
            v = getattr(api, attr, None)
            if v is None or isinstance(v, bool) or str(v).strip() in ("", "0"):
                continue
            login = v
            break
        creds = getattr(api, "_credentials", None)
        server = creds.get("server") if isinstance(creds, dict) else None
        server = server.strip() if isinstance(server, str) and server.strip() else None
    except Exception:
        return None, None, TL_LOGIN_UNREADABLE
    if login is None:
        return None, server, TL_LOGIN_UNREADABLE
    if server is None:
        return login, None, TL_SERVER_UNREADABLE
    return login, server, TL_OK


#: The alert each account's key opens while it cannot be resolved or does not join its
#: declaration (`page_key`), and closes once it does again (`clear_key_alert`) -- v5.1's idiom.
KEY_ALERT_IDS = {"e8": TL_ALERT_ID, "fusion": "xacct_fusion_account_key_unresolvable"}
#: Why a key pages (beside the TL_* statuses): the declaration itself is invalid or unresolvable
#: (the `invalid:` sentinel), or the venue's key is another account's than the declared one.
KEY_DECLARATION_INVALID, KEY_MISMATCH = "DECLARATION_INVALID", "KEY_MISMATCH"


def _alert_ledger_path() -> Path:
    return Path(os.environ.get(ALERT_LEDGER_ENV) or ALERT_LEDGER)


def key_alert_id(account: str, source: str) -> str:
    """The alert ONE CHECK owns for `account` (r7.2, audit r7.1 SF-2): each check opens and
    closes only its own, so a fresh-but-old book read by the gateway can never close the alert
    the venue's own key check opened (the flap r7.1 had)."""
    return f"{KEY_ALERT_IDS.get(account, f'xacct_{account}_account_key_unresolvable')}.{source}"


def _send(aid: str, status: str, sig: str, title: str, body: str) -> dict[str, Any]:
    """Page through publish_sync's helper `libs.ops.provenance._page`. Under v5f (a446bcc0,
    which lands with or before r7.x, never after) it ONLY ENQUEUES to the provenance outbox and
    returns at once: `deliver_pending` (BoxHeartbeat, ProcessHealth) sends it to the armed
    channels later, deduplicated, repaged while it stands, one recovery page -- so no sender,
    hung or raising, ever runs on the order path or under placement_lock. On a tree without the
    helper: not sent, and the reason says so. Never raises."""
    try:
        from libs.ops import provenance
        helper = getattr(provenance, "_page", None)
        if not callable(helper):
            return {"sent": False, "reason": "no paging helper (publish_sync v5e absent)"}
        res = helper(aid, status, sig, title, body)
        return res if isinstance(res, dict) else {"sent": False}
    except Exception as exc:
        return {"sent": False, "reason": f"page failed ({type(exc).__name__})"}


def page_key(account: str, status: str, *, source: str = "venue_key") -> str | None:
    """Open `account`'s key alert for the check `source` in the desk's alert ledger AND page it
    (r7.2, audit r7.1 MUST-FIX 2: the ledger alone reached nobody) through `_send` -> v5f's
    enqueue-only `provenance._page` (delivered off the order path). Statuses: UNRESOLVABLE (no login, no server, KEY_UNAVAILABLE),
    UNDECLARED (no E8_ACCOUNT.json: the `e8_account_undeclared` rail), DECLARATION_INVALID (the
    `invalid:` sentinel) or KEY_MISMATCH. Names no value. "OPEN" or None. Never raises."""
    aid = key_alert_id(account, source)
    rail = " (rail e8_account_undeclared: no new E8 gold risk)" if account == "e8" else ""
    msg = (f"[cross_account] {account} account key, check {source}: {status}{rail}; the "
           f"cross-account fence fails closed (no new gold leg against a key that does not "
           f"resolve or join its declaration)")
    opened = None
    try:
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(_alert_ledger_path())
        ledger.observe(aid, msg, scope="RUNTIME")
        ledger.save()
        opened = "OPEN"
    except Exception:
        opened = None
    _send(aid, "OPEN", status, f"E8/FUSION ACCOUNT KEY: {account} {status}", msg)
    return opened


def clear_key_alert(account: str, *, source: str = "venue_key") -> str | None:
    """Close the alert THIS check (`source`) opened, once the same check resolves AND joins
    again, and page the recovery once. Reads the ledger only when it exists; "FIXED" or None."""
    aid = key_alert_id(account, source)
    try:
        path = _alert_ledger_path()
        if not path.exists():
            return None
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(path)
        alert = ledger.alerts.get(aid)
        if alert is None or not alert.open:
            return None
        ledger.verify(aid, still_firing=False)
        ledger.save()
    except Exception:
        return None
    _send(aid, "OK", "recovered", f"E8/FUSION ACCOUNT KEY: {account} OK again ({source})",
          f"[cross_account] {account} account key, check {source}: resolves and joins again")
    return "FIXED"


def _page_unresolvable(status: str) -> str | None:
    """The E8 venue's own key cannot be resolved (`tradelocker_key_status`): page it."""
    return page_key("e8", status, source="venue_key")


def key_joins(account: str, key: object, want: str | None, *, source: str) -> bool:
    """Does `key` join `account`'s declaration `want`? Pages (for check `source`) when it does
    not -- unresolvable key, `invalid:` declaration, mismatch -- and closes that check's own
    alert when it does. An undeclared account (`want` None) with a resolvable key is not paged
    here: E8-Gold refuses new E8 gold risk on it itself (`e8_account_check`)."""
    if not valid_key(key):
        page_key(account, TL_KEY_UNAVAILABLE, source=source)
        return False
    if want is not None and str(want).startswith("invalid:"):
        page_key(account, KEY_DECLARATION_INVALID, source=source)
        return False
    if want is not None and key != want:
        page_key(account, KEY_MISMATCH, source=source)
        return False
    if want is not None:
        clear_key_alert(account, source=source)
    return True


def tradelocker_key_status(venue: Any) -> tuple[str | None, str]:
    """(the E8 account key or None, status). The key is
    `libs.ops.provenance.account_key(login, server, create=False)` on `tradelocker_identity`'s
    login and server; a missing login or server PAGES and is None (fail closed). Never raises."""
    login, server, status = tradelocker_identity(venue)
    if status != TL_OK:
        _page_unresolvable(status)
        return None, status
    prov = _provenance()
    key = None
    if prov is not None:
        try:
            key = prov.account_key(login, server, create=False)
        except Exception:
            key = None
    if not valid_key(key):
        _page_unresolvable(TL_KEY_UNAVAILABLE)          # r7.1: KEY_UNAVAILABLE pages too
        return None, TL_KEY_UNAVAILABLE
    clear_key_alert("e8", source="venue_key")           # the same check that opened it
    return key, TL_OK


def tradelocker_account_key(venue: Any) -> str | None:
    """The E8 (TradeLocker) account key, or None -- UNRESOLVABLE, and every caller fails closed
    (`publish` refuses a None key, so the E8 book ages and its reader refuses it)."""
    return tradelocker_key_status(venue)[0]


def valid_key(key: object) -> bool:
    return isinstance(key, str) and bool(KEY_RE.match(key))


def expected_key(account: str) -> str | None:
    """The key the box DECLARES for `account`, or None when it declares none: Fusion from its live
    login (decision_core.FUSION_ACCOUNT_FILE), E8 from `E8_ACCOUNT_FILE` (both gitignored). An E8
    declaration that is present but not a valid key is an INVALID sentinel, so every E8 book is
    refused rather than the check silently skipped."""
    if account == "e8":
        try:
            doc = json.loads(E8_ACCOUNT_FILE.read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return "invalid:unreadable E8 declaration"
        key = doc.get("account_key") if isinstance(doc, dict) else None
        return key if valid_key(key) else "invalid:E8 declaration carries no valid account_key"
    if account == "ftmo":
        try:
            doc = json.loads((XACCT_DIR.parent / FTMO_ACCOUNT_NAME).read_text(
                encoding="utf-8-sig"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            return "invalid:unreadable FTMO declaration"
        if not isinstance(doc, dict) or doc.get("login") in (None, "") \
                or doc.get("server") in (None, ""):
            return "invalid:the FTMO declaration carries no login and server"
        return account_key(doc["login"], doc["server"]) or \
            "invalid:the declared FTMO login's key is unresolvable (libs.ops.provenance or box key)"
    if account != "fusion":
        return None
    try:
        from mt5desk import decision_core as _dc
        login, _ = _dc.fusion_live_login()
    except Exception:
        return None
    if login is None:
        return None
    # A DECLARED login whose key cannot be resolved is an INVALID sentinel, never "undeclared":
    # None here would skip the key check and let any book read as Fusion's (r7 key-join ruling).
    return account_key(login, _dc.FUSION_LIVE_SERVER) or \
        "invalid:the declared Fusion login's key is unresolvable (libs.ops.provenance or box key)"


def book_path(account: str) -> Path:
    if account not in PEERS:
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
    # Upper-cased here: a catalogue that spells `Gold` or `xauUsd` names the same instrument, and
    # an unnamed row makes the whole book unreadable (audit round 4: E8's names are UNMEASURED).
    iid_to_sym = {int(v): str(k).strip().upper()
                  for k, v in (getattr(venue, "_by_key", {}) or {}).items()}
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
    rows += [(name(o), o.get("side")) for o in tradelocker_entry_orders(positions, orders)]
    return exposure_from_rows(rows)


def tradelocker_entry_orders(positions: list[dict[str, Any]],
                             orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The resting ENTRY orders among `orders`: every order that is not an open position's
    protective stop or target (see `tradelocker_exposure` for the rule). Pure."""
    protective: set[str] = set()
    position_ids: set[str] = set()
    for p in positions:
        if p.get("id") is not None:
            position_ids.add(str(p.get("id")))
        for k in ("stopLossId", "takeProfitId", "stopOrderId", "takeProfitOrderId"):
            if p.get(k) not in (None, "", 0):
                protective.add(str(p.get(k)))
    return [o for o in orders
            if not (str(o.get("id")) in protective
                    or (o.get("positionId") not in (None, "", 0)
                        and str(o.get("positionId")) in position_ids))]


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
    both): a book written from an older snapshot can erase another lane's fresh send. A thread
    whose bounded call timed out (`_ABANDONED`) is refused: its lock is gone."""
    if threading.get_ident() in _ABANDONED:
        raise RuntimeError("this publish's bounded call timed out; its lock is released, so it "
                           "may not write")
    want = expected_key(account) if account in PEERS else None
    if not key_joins(account, key, want, source="publish"):
        if not valid_key(key):
            raise ValueError("a book must carry a valid account key (an unresolvable key "
                             "publishes nothing; the reader then fails closed on age)")
        raise ValueError(f"the {account} venue is not on the account this box declares; "
                         f"its book is not published as {account}'s")
    p = book_path(account)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {"account": account, "account_key": key,
           "at": (now or datetime.now(tz=UTC)).isoformat(),
           "source": source, "covers": "all", "symbols": exposure}
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    if threading.get_ident() in _ABANDONED:            # timed out while it was reading
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise RuntimeError("this publish's bounded call timed out; not written")
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
    except Exception as exc:
        return None, f"the {account} terminal book is unreadable ({type(exc).__name__}: {exc})"
    try:
        key = mt5_account_key(mt5)
    except Exception as exc:
        page_key(account, TL_KEY_UNAVAILABLE, source="terminal_book")
        return None, f"the {account} terminal book is unreadable ({type(exc).__name__}: {exc})"
    want = expected_key(account)
    if not key_joins(account, key, want, source="terminal_book"):
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
            bounded(fn, timeout_s=LOCKED_PUBLISH_TIMEOUT_S, what=f"{holder} publish")
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
        if not valid_key(key):
            raise ValueError("the book names no account (account_key is not sha256:<16 hex>)")
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
    if not key_joins(account, key, want, source="read_book"):
        return None, (f"the {account} book is of another account than the one this box "
                      f"declares; its positions are not this account's")
    try:
        held = inflight(account, now=now)
    except (OSError, ValueError, TypeError) as exc:
        return None, (f"the {account} in-flight file is unreadable ({type(exc).__name__}); its "
                      f"pending sends are unknown")
    for sym in held:
        book[sym] = {"long": True, "short": True}
    tail = f"; {len(held)} symbol(s) held by an in-flight send" if held else ""
    return book, f"{account} book {age:.0f}s old{tail}"


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


def ftmo_block(symbol: object, side: object, *, now: datetime | None = None) -> str | None:
    """Why an order of `side` on `symbol` on Fusion or E8 may NOT be sent against the FTMO book,
    or None (2026-10-29: no account goes opposite another; FTMO's executor fences the other way).

    Gold is the gold direction lock's (`FTMO_FENCE_SKIPS`). While the FTMO executor is ARMED its
    book must be fresh, or this fails closed exactly as the E8 book does. Unarmed, it trades
    nothing new, so its LAST published book (whatever its age) still fences what it may hold;
    no book at all, or a book of another account, then blocks nothing: the lane never ran."""
    sym = norm(symbol)
    if sym and any(same_instrument(sym, g) for g in FTMO_FENCE_SKIPS):
        return None
    if (XACCT_DIR.parent / FTMO_EXECUTOR_ARMED_NAME).exists():
        book, why = read_book("ftmo", now=now)
        return opposite_block(book, symbol, side, account="ftmo", why_absent=why)
    book, _ = read_book("ftmo", now=now, max_age_s=float("inf"))
    return None if book is None else opposite_block(book, symbol, side, account="ftmo")


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


def _proc_started(pid: int) -> float | None:
    """The process's start time (`psutil.Process.create_time`), or None when it cannot be read.
    With the pid it names ONE process: a pid reused by another process has another start."""
    try:
        import psutil
        return round(float(psutil.Process(int(pid)).create_time()), 3)
    except Exception:
        return None


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
            # A LIVE pid is the holder only if it is the SAME process (audit round 4): the lock
            # records the holder's start time, and a pid reused by another process has another.
            # A mismatch is unprovable, not "alive" -- it falls to the abandoned age below,
            # never to "held forever". No recorded start (an older lock): alive, as before.
            rec = doc.get("started")
            if not isinstance(rec, (int, float)) or isinstance(rec, bool):
                return False
            now_started = _proc_started(int(doc["pid"]))
            if now_started is None or abs(now_started - float(rec)) <= 1.0:
                return False
    # abs(): a backward clock jump puts the lock's mtime in the future, and a negative age must
    # not keep a dead holder's lock forever.
    return abs(age_s) > LOCK_ABANDONED_S


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
                try:
                    os.write(fd, json.dumps({"holder": holder, "pid": os.getpid(),
                                             "host": _HOST, "token": token,
                                             "started": _proc_started(os.getpid()),
                                             "at": datetime.now(tz=UTC).isoformat()}).encode())
                finally:
                    os.close(fd)
            except OSError:
                # A WRITE THAT FAILED LEAVES NO ORPHAN (audit round 4): the file is ours (O_EXCL),
                # and an empty one would block every lane until LOCK_STALE_S.
                with contextlib.suppress(OSError):
                    path.unlink()
                raise
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


class LockedCallTimeout(TimeoutError):
    """A call made under the placement lock did not return in time. It MAY STILL LAND."""


#: Thread idents whose bounded call timed out: a publish they reach later must not write (it would
#: land outside the lock, from a read older than whatever the lock's next holder published).
_ABANDONED: set[int] = set()


def inflight_path(account: str) -> Path:
    if account not in PEERS:
        raise ValueError(f"unknown account {account!r}")
    return XACCT_DIR / f"{account}_inflight.json"


def mark_inflight(account: str, symbol: object, *, now: datetime | None = None,
                  hold_s: float = MAX_AGE_S) -> None:
    """Record that a send on `account`/`symbol` is IN FLIGHT and MAY LAND: until `hold_s` has
    passed, `read_book(account)` reports BOTH sides of that symbol as held, so the other account
    cannot take the opposite side of an order its book does not show yet (audit r5 should-fix).

    RAISES when the hold cannot be written (audit r6 should-fix 4, r7 must-fix 4): `bounded`
    writes it BEFORE the send and does not send without it, so a failure is never silent."""
    sym = norm(symbol)
    if not sym:
        raise ValueError(f"no in-flight hold for an unreadable symbol {symbol!r}")
    p = inflight_path(account)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc = doc if isinstance(doc, dict) else {}
    except FileNotFoundError:
        doc = {}
    except ValueError:
        doc = {}                                  # a torn hold file is rewritten, holding more
    until = (now or datetime.now(tz=UTC)).timestamp() + float(hold_s)
    doc[sym] = max(float(doc.get(sym) or 0.0), until)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def clear_inflight(account: str, symbol: object) -> bool:
    """Drop the hold `bounded` wrote for a send that RETURNED. False (the hold stays, failing
    closed until it expires) when the file cannot be rewritten."""
    sym = norm(symbol)
    try:
        p = inflight_path(account)
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or sym not in doc:
            return True
        doc.pop(sym, None)
        tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False


def inflight(account: str, *, now: datetime | None = None) -> set[str]:
    """Symbols on `account` with a timed-out send that may still land (see `mark_inflight`).
    An unreadable file blocks NOTHING here but is reported by `read_book` as no book."""
    p = inflight_path(account)
    if not p.exists():
        return set()
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("the in-flight file is not an object")
    t = (now or datetime.now(tz=UTC)).timestamp()
    return {str(k) for k, v in doc.items() if float(v) > t}


def bounded(fn: Any, *, timeout_s: float | None = None, what: str = "send",
            account: str | None = None, symbol: object = None) -> Any:
    """`fn()`, or `LockedCallTimeout` when it has not returned within `timeout_s` (default
    `LOCKED_SEND_TIMEOUT_S`, read at call time).

    Run in a daemon thread so the caller -- and the lock it holds -- is released on time. The
    thread is NOT killed (Python cannot), so a timed-out send may still reach the venue: the
    caller treats it as a failed send whose outcome is unknown, never as "not sent". An exception
    `fn` raises is re-raised here unchanged.

    `account` and `symbol` (a send): the symbol is marked IN FLIGHT on that account BEFORE the
    send starts (`mark_inflight`, for the timeout plus a minute); if that hold cannot be written
    this RAISES and nothing is sent (r7 must-fix 4: no send without a hold). A send that returns
    clears it; one that times out extends it to `MAX_AGE_S`, so the caller's lock is released
    only with the other account's readers seeing both sides held. A timed-out thread can never
    publish (`_ABANDONED`)."""
    box: dict[str, Any] = {}
    limit = float(LOCKED_SEND_TIMEOUT_S if timeout_s is None else timeout_s)
    held = account is not None and symbol is not None
    if held:
        mark_inflight(account, symbol, hold_s=limit + 60.0)   # raises: no send without a hold

    def run() -> None:
        try:
            box["v"] = fn()
        except BaseException as exc:                 # re-raised in the caller's thread
            box["e"] = exc
        finally:
            _ABANDONED.discard(threading.get_ident())

    t = threading.Thread(target=run, name=f"xacct-bounded:{what}"[:60], daemon=True)
    t.start()
    t.join(max(0.0, limit))
    if t.is_alive():
        if t.ident is not None:
            _ABANDONED.add(t.ident)
        if held:
            with contextlib.suppress(Exception):  # the pre-send hold stands if this fails
                mark_inflight(account, symbol)
        raise LockedCallTimeout(f"{what} did not return within {limit:g}s under the placement "
                                f"lock; it may still land")
    if "e" in box:
        # A send that RAISED may still have reached the venue: its short pre-send hold stands.
        raise box["e"]
    if held:
        clear_inflight(account, symbol)
    return box.get("v")


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
