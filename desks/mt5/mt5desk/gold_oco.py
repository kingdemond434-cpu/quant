"""THE CROSS-ACCOUNT GOLD DIRECTION LOCK (OCO): one gold direction a day, on every account.

WHY (coordinator ruling, 2026-10-21). The box trades gold on more than one account: E8 through
TradeLocker (`prop/e8_gold.py`, all three windows), Fusion through the MT5 gateway (gold_asia), and
later FTMO through a second MT5 terminal. `cross_account` already refuses a leg opposite the OTHER
account's open or resting book, but it knows two accounts, it has no notion of the DAY's direction,
and nothing cancelled a leg resting on one account once another account had filled the other way.

THE RULE.
  1. The FIRST gold leg filled on ANY account sets that trading day's direction (`claim_fill`,
     a read-modify-write under the one placement lock, so two lanes cannot both claim it).
  2. Once set, every opposite resting gold leg on every account is cancelled (`legs_to_cancel`,
     run by each lane on its own legs every pass) and no new opposite gold leg is placed (`gate`).
  3. Nothing opens against an open gold position on another account, whatever its date: `gate`
     reads every other lane's published positions AND resting entries (a resting stop counts with
     its own side, as in `cross_account`), so a long carried across midnight still blocks a short.
  4. FAIL CLOSED. Before any gold leg, the lane reads the direction state and every other declared
     lane's published gold state. Absent, unreadable, torn (digest mismatch, bad shape, a side it
     cannot read) or older than MAX_STATE_AGE_S -> no leg; the caller writes a RAIL_BLOCKED row
     under RAIL with its missed-growth line.
  5. IDENTITY is `oco_account_key`, the ONE helper: the keyed-HMAC `provenance.account_key`
     (publish_sync v5). Absent, unkeyed, or answering the plain sha256 of login@server (which
     reverses in under a second) -> IdentityUnavailable -> no gold leg. No login is ever stored.
  6. FALLBACK MODE (default for every non-E8 lane): the lane places NOTHING until E8 has a first
     fill that day, then only E8's direction. Full OCO mode (any lane may lead) is taken only when
     `data/GOLD_OCO_MODE.json` says `"oco"` for the lane AND every declared lane's fresh state
     carries this PROTOCOL -- i.e. every lane is running code that honours the lock.
  7. ONE DIRECTION A DAY ON EVERY ACCOUNT, E8 INCLUDED (v2; supersedes v1's rule 8, which let
     E8's own two legs keep their behaviour on a day E8 set). On the first fill anywhere, every
     opposite resting gold leg is cancelled the pass it is seen -- E8's own twin among them -- no
     new opposite leg is placed, and a fill that lands against the direction anyway (a whipsaw
     inside one pass) is FLATTENED at once (`positions_to_flatten`). A blind lock cancels every
     resting gold leg (`cancel_plan`), and an account that cannot be named PAGES
     (`page_identity`), as well as placing nothing.

THE STALENESS BOUND, MAX_STATE_AGE_S = 600 s. The slowest lane is E8-Gold, one pass every five
minutes (the gateway passes every minute). Two E8 passes tolerate one late or lock-skipped pass;
a state two passes old means the lane is not running, and its account's positions are unknown.
It is tighter than `cross_account.MAX_AGE_S` (900 s, three passes) because this gate also decides
direction, and a fill on a silent lane is exactly what it would miss.

TRADING DATE. Both lanes date the day by the MT5 server clock exactly as they already do
(`tick.time` read as a UTC-labelled epoch, `.date()`; TradeLocker's `openDate` is the same broker
clock). `trading_date` and `ms_trading_date` are that convention, in one place.

SWITCHING THE MODE (box-local, gitignored `desks/mt5/data/GOLD_OCO_MODE.json`):
    {"lanes": ["e8", "fusion"], "modes": {"fusion": "fallback"}}     # the default, same as absent
    {"lanes": ["e8", "fusion"], "modes": {"fusion": "oco"}}          # full OCO for Fusion
    {"lanes": ["e8", "fusion", "ftmo"], "modes": {"fusion": "oco", "ftmo": "fallback"}}
A lane must be in "lanes" to place gold at all, and every listed lane must be publishing fresh
state or NO lane places gold: declare FTMO only once its terminal lane runs.

Never sends anything. State lives under `cross_account.XACCT_DIR` (gitignored data/xacct/).
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mt5desk import cross_account as _xa

_DESK = Path(__file__).resolve().parent.parent
#: The on-disk protocol. A lane state without it is a lane not running this code.
PROTOCOL = 1
#: E8 leads: in fallback mode every other lane copies E8's first fill.
LEADER = "e8"
KNOWN_LANES = ("e8", "fusion", "ftmo")
DEFAULT_LANES = ("e8", "fusion")
#: Two E8-Gold passes (5 min each); see the module docstring.
MAX_STATE_AGE_S = 600.0
#: The mode switch (gitignored, box-local). Absent -> every non-E8 lane in fallback.
MODE_FILE = _DESK / "data" / "GOLD_OCO_MODE.json"
#: The rail every refusal is billed under (fusion_book_rails / the E8 intents journal).
RAIL = "gold_oco_direction_lock"
#: Which lane an MT5 gateway process is. Absent -> "fusion"; any other value must be a known
#: non-leader lane or the gateway places no gold (`gateway_lane` returns None).
LANE_ENV = "QUANT_GOLD_LANE"
SYMBOL = "XAUUSD"
#: Trading days kept in the direction file.
KEEP_DAYS = 7
#: How long a claim or a cancellation note waits for the placement lock.
CLAIM_WAIT_S = 5.0
_WRITE_TRIES = 10


class IdentityUnavailable(ValueError):
    """The account cannot be named by a keyed account key. No gold leg is placed."""


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    why: str
    mode: str = ""


# ------------------------------------------------------------------ identity: ONE helper

def oco_account_key(login: object, server: object) -> str:
    """THE ONE IDENTITY HELPER: the keyed-HMAC account key of `login@server`.

    It IS `cross_account.account_key` (Fusion r7), which delegates to the desk's one key function
    `libs.ops.provenance.account_key(login, server, create=False)` -- that function normalises
    the login and strips the server itself (publish_sync v5c/v5d) -- so the OCO key, the fence's
    book key, the evidence key and the FTMO prop-ledger key are one value. A READER: it never
    creates the box key. No hashing happens here.

    r7's `account_key` answers None when it cannot name the account; this helper RAISES
    IdentityUnavailable instead -- and the caller places no gold leg and writes a reasoned row.
    The checks below only explain WHY (for the row and the page); they compute no key. The
    exception text never carries the login."""
    if server is None or str(server).strip() == "":
        raise IdentityUnavailable("the account's server is unreadable")
    key = _xa.account_key(login, server)
    if key is not None:
        return str(key)
    prov = _xa._provenance()
    if prov is None:
        raise IdentityUnavailable("the keyed-HMAC provenance.account_key has not landed")
    canon = None
    with contextlib.suppress(Exception):
        canon = prov.norm_login(login)
    if canon is None:
        raise IdentityUnavailable("the account's login is unreadable (or is a username, not a "
                                  "numeric login)")
    raise IdentityUnavailable("the box-held HMAC account key is absent or short (or the helper "
                              "did not answer a sha256:<16 hex> key); accounts cannot be named")


#: The identity alert (audit v2 must-fix 8): a missing or unkeyed HMAC key stops every gold leg
#: on the account, so it is PAGED through the desk's alert path (libs.ops.alert_channels, the
#: AlertLedger), not only logged -- login_fence's idiom: on a change, again every REPAGE_H while
#: it stands, once on recovery. `ALERT_ROOT` is the repository root (tests point it at a tmp dir).
ALERT_ID = "gold_oco_identity_unavailable"
ALERT_ROOT = _DESK.parent.parent
PAGE_STATE_REL = "desks/mt5/logs/gold_oco_identity_alert.json"
REPAGE_H = 6.0
#: The pager: (title, body) -> result. Tests set it; None -> `provenance._page` when the tree
#: carries it (publish_sync v5e, on this base), else alert_channels.send_all under ALERT_ROOT.
PAGER: Callable[[str, str], dict[str, Any]] | None = None


def _provenance_page() -> Callable[..., dict[str, Any]] | None:
    """publish_sync's `provenance._page(aid, status, sig, title, body) -> dict`, or None.

    v5e (on this base) SENDS and records its dedup state only for a DELIVERED page, atomically.
    v5f (local branch claude/publish-sync-v5f) keeps the signature and becomes ENQUEUE-ONLY: it
    writes one outbox row, returns `sent` False and a `queued` field, and `deliver_pending`
    (MT5-BoxHeartbeat) sends it off the order path. This module needs no change for v5f: it
    reports what `_page` answered (`queued` included)."""
    root = str(Path(ALERT_ROOT))
    try:
        import sys as _sys
        if root not in _sys.path:
            _sys.path.insert(0, root)
        from libs.ops import provenance
    except Exception:
        return None
    fn = getattr(provenance, "_page", None)
    return fn if callable(fn) else None


def _save_page_state(path: Path, state: dict[str, Any]) -> None:
    """The local dedup state, ATOMICALLY (tmp beside it, fsync, os.replace -- retried while
    Windows holds the destination open). RAISES OSError when it cannot land."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(state, sort_keys=True))
        fh.flush()
        os.fsync(fh.fileno())
    for attempt in range(_WRITE_TRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _WRITE_TRIES - 1:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise
            time.sleep(0.05)


def page_identity(lane: str, why: str | None, *,
                  now: datetime | None = None) -> dict[str, Any]:
    """Page that `lane`'s account cannot be named (why set), or that it can again (why None).

    Never raises (a trading loop calls it): a failure is returned as {"sent": False, "error"}.
    The page names the lane and the reason only -- `IdentityUnavailable` never carries a login.

    THE PAGE IS RECORDED ONLY WHEN IT WAS DELIVERED (v2s, audit v2r SF-1; login_fence's and
    v5e's rule): a send whose `delivered` is 0, absent or falsy writes no dedup state, so the
    next pass re-sends instead of muting the alert for REPAGE_H. The state is written
    atomically. In production (no test PAGER) delivery and dedup are `provenance._page`'s --
    v5e's sender today, v5f's enqueue-only outbox once v5f lands (`queued` is then reported)."""
    root = Path(ALERT_ROOT)
    now = now or datetime.now(tz=UTC)
    path = root / PAGE_STATE_REL
    out: dict[str, Any] = {"sent": False}
    try:
        import sys as _sys
        if str(root) not in _sys.path:
            _sys.path.insert(0, str(root))
        from libs.ops.alert_ledger import AlertLedger
        ledger = AlertLedger(root / "data" / "alert_ledger.json")
        alert_id = f"{ALERT_ID}:{lane}"
        if why is not None:
            ledger.observe(alert_id, f"gold OCO {lane}: {why}"[:600], scope="RUNTIME")
            ledger.save()
            status, sig = "OPEN", why
            title = f"GOLD OCO: {lane} places NO gold -- its account cannot be named"
            body = (f"{why}\nEvery gold leg on the {lane} account is refused until the box-held "
                    f"HMAC account key (data/secrets/account_key.hmac) answers again.")
        else:
            alert = ledger.alerts.get(alert_id)
            if alert is not None and alert.open:
                ledger.verify(alert_id, still_firing=False)
                ledger.save()
            status, sig = "OK", "recovered"
            title = f"GOLD OCO: {lane} account named again"
            body = f"the {lane} account is keyed again; gold legs are gated as usual"
        prov_page = None if PAGER is not None else _provenance_page()
        if prov_page is not None:
            res = prov_page(alert_id, status, sig, title, body[:1500])
            res = res if isinstance(res, dict) else {}
            return {"sent": bool(res.get("sent")), "queued": res.get("queued"),
                    "reason": res.get("reason") or ("recovered" if status == "OK" else "paged"),
                    "armed": res.get("armed"), "delivered": res.get("delivered"),
                    "via": "provenance._page"}
        # THE LOCAL PATH (a test PAGER, or a tree without provenance._page): v5e's rules here.
        try:
            prev_all = json.loads(path.read_text("utf-8"))
            prev_all = prev_all if isinstance(prev_all, dict) else {}
        except (OSError, ValueError):
            prev_all = {}
        prev = prev_all.get(lane) if isinstance(prev_all.get(lane), dict) else {}
        last = None
        with contextlib.suppress(TypeError, ValueError):
            last = datetime.fromisoformat(str(prev.get("paged_at")))
        if status == "OPEN":
            if prev.get("why") != why:
                reason = "changed"
            elif last is None or (now - last).total_seconds() / 3600.0 >= REPAGE_H:
                reason = f"still standing after {REPAGE_H:g}h"
            else:
                return {"sent": False, "reason": "deduplicated"}
        elif prev.get("why"):
            reason = "recovered"
        else:
            return {"sent": False, "reason": "OK: nothing to page"}
        if PAGER is not None:
            res = PAGER(title, body[:1500])
        else:
            from libs.ops import alert_channels
            res = alert_channels.send_all(title, body[:1500],
                                          config=root / "data/secrets/alert_channels.json",
                                          ledger=root / "data/alert_delivery.jsonl")
        res = res if isinstance(res, dict) else {}
        out = {"sent": bool(res.get("delivered")), "reason": reason, "armed": res.get("armed"),
               "delivered": res.get("delivered")}
        if not res.get("delivered"):
            out["reason"] = f"{reason}: undelivered, re-sent next pass (nothing recorded)"
            return out
        prev_all[lane] = {"why": why, "paged_at": now.isoformat(timespec="seconds")}
        _save_page_state(path, prev_all)
    except Exception as exc:
        out = {"sent": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return out


def mt5_oco_key(mt5: Any) -> str:
    """The keyed account key of the MT5 account under `mt5`."""
    try:
        login, server = _xa.mt5_identity(mt5)
    except Exception as exc:
        raise IdentityUnavailable(f"the MT5 terminal names no account "
                                  f"({type(exc).__name__})") from None
    return oco_account_key(login, server)


def tradelocker_oco_key(venue: Any) -> str:
    """The keyed account key of the TradeLocker account under `venue`: EXACTLY bracket guard
    v5.1's evidence key (r7's `cross_account.tradelocker_key_status`: TLAPI account_id/acc_id and
    `_credentials["server"]`, handed to `provenance.account_key`; a missing login or server
    pages). RAISES IdentityUnavailable naming the status (never the login) when it is None."""
    try:
        key, status = _xa.tradelocker_key_status(venue)
    except Exception as exc:
        raise IdentityUnavailable(f"the TradeLocker venue cannot be named "
                                  f"({type(exc).__name__})") from None
    if key is None:
        why = {_xa.TL_LOGIN_UNREADABLE: "it names no account id",
               _xa.TL_SERVER_UNREADABLE: "it names no server in _credentials",
               _xa.TL_KEY_UNAVAILABLE: "the box-held HMAC account key did not answer"}.get(
                   status, "unresolvable")
        raise IdentityUnavailable(f"the TradeLocker venue cannot be named: {why} ({status})")
    return str(key)


def gateway_lane() -> str | None:
    """The lane an MT5 gateway process trades gold for: "fusion" unless `QUANT_GOLD_LANE` names
    another non-leader lane; None (no gold placed) when it names anything else."""
    lane = os.environ.get(LANE_ENV, "fusion").strip().lower()
    return lane if lane in KNOWN_LANES and lane != LEADER else None


# ------------------------------------------------------------------ pure helpers

def side_of(side: object) -> str | None:
    """"long" / "short" from any of the desk's spellings, else None."""
    s = str(side if side is not None else "").strip().lower()
    if s in ("long", "buy", "buy_stop", "buy_limit", "1"):
        return "long"
    if s in ("short", "sell", "sell_stop", "sell_limit", "-1"):
        return "short"
    return None


def opposite(side: str) -> str:
    return "short" if side == "long" else "long"


def trading_date(server_epoch_s: float) -> str:
    """The trading date of an MT5 server-clock epoch, as both lanes already date their day."""
    return datetime.fromtimestamp(float(server_epoch_s), tz=UTC).date().isoformat()


def ms_trading_date(ms: object) -> str | None:
    """The trading date of a broker-clock epoch in ms (TradeLocker `openDate`), or None."""
    try:
        v = int(ms)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    return trading_date(v / 1000.0) if v > 0 else None


def legs_to_cancel(lane: str, entry: dict[str, Any] | None,
                   own_legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The lane's OWN resting gold legs the day's direction cancels. Pure.

    None when no direction is set. On every lane -- the leader included (v2 growth upgrade,
    audit must-fix 4: E8's twin was left to E8's own five-minute twin cancel, so a whipsaw could
    fill both legs) -- every resting leg against the day's direction is cancelled the pass the
    direction is seen, the first fill's own twin among them. A leg whose side cannot be read is
    cancelled: it is not provably the day's direction."""
    if not entry or side_of(entry.get("direction")) is None:
        return []
    d = side_of(entry.get("direction"))
    return [leg for leg in own_legs if side_of(leg.get("side")) != d]


def cancel_plan(lane: str, entry: dict[str, Any] | None, why: str | None,
                own_legs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """(the lane's own resting gold legs to cancel now, why). Pure.

    BLIND IS CANCEL-ALL (audit v2 must-fix 7): when the direction state cannot be read (`why`
    set), no leg is provably on the day's side, so EVERY resting gold leg on the lane's book is
    cancelled -- a resting stop is a fill the lock can no longer veto. Otherwise
    `legs_to_cancel`."""
    if why is not None:
        return list(own_legs), f"the gold direction state is unreadable ({why}); every resting " \
                               f"gold leg is cancelled"
    d = (entry or {}).get("direction")
    return legs_to_cancel(lane, entry, own_legs), (
        f"today's gold direction is {d} (first fill on {(entry or {}).get('first_fill_lane')})")


def positions_to_flatten(entry: dict[str, Any] | None, own_positions: list[dict[str, Any]],
                         *, date: str) -> list[dict[str, Any]]:
    """The lane's OWN gold positions OPENED TODAY against the day's direction. Pure.

    A FILL AGAINST THE DIRECTION IS FLATTENED AT ONCE (audit v2 must-fix 6): logging the
    conflict is not enough, the account then carries a position the lock exists to prevent. A
    position carried from an earlier day is not touched (it predates the day's direction; it still
    blocks the other side through `gate`). A position whose open date cannot be read counts as
    today's (the cautious reading for a position that IS open on the wrong side)."""
    d = side_of((entry or {}).get("direction"))
    if d is None:
        return []
    out = []
    for p in own_positions:
        opened = p.get("opened_date")
        if opened not in (None, "") and str(opened) != str(date):
            continue
        if side_of(p.get("side")) != d:
            out.append(p)
    return out


# ------------------------------------------------------------------ files

def _dir() -> Path:
    return Path(_xa.XACCT_DIR)


def direction_path() -> Path:
    return _dir() / "gold_direction.json"


def lane_path(lane: str) -> Path:
    if lane not in KNOWN_LANES:
        raise ValueError(f"unknown gold lane {lane!r}")
    return _dir() / f"gold_{lane}.json"


def _digest(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _write(path: Path, body: dict[str, Any]) -> Path:
    """Atomic: a sealed copy to a tmp file, then os.replace, retried on PermissionError (Windows
    refuses a replace while a reader holds the destination open)."""
    doc = {**body, "digest": _digest(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, default=str), encoding="utf-8")
    for attempt in range(_WRITE_TRIES):
        try:
            os.replace(tmp, path)
            return path
        except PermissionError:
            if attempt == _WRITE_TRIES - 1:
                with contextlib.suppress(OSError):
                    tmp.unlink()
                raise
            time.sleep(0.1)
    return path


def _read_sealed(path: Path) -> dict[str, Any]:
    """The body of a sealed file. RAISES FileNotFoundError when absent and ValueError when torn
    (unparseable, not an object, or a digest that does not match its body)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"unreadable ({type(exc).__name__})") from None
    if not isinstance(doc, dict):
        raise ValueError("not an object")
    digest = doc.pop("digest", None)
    if digest != _digest(doc):
        raise ValueError("torn: its digest does not match its body")
    return doc


# ------------------------------------------------------------------ the mode switch

def _mode_doc() -> tuple[dict[str, Any], str]:
    try:
        doc = json.loads(MODE_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}, "no mode file: the default (fallback for every non-E8 lane)"
    except (OSError, ValueError) as exc:
        return {"_unreadable": True}, (f"the mode file is unreadable ({type(exc).__name__}): "
                                       f"fallback")
    if not isinstance(doc, dict):
        return {"_unreadable": True}, "the mode file is not an object: fallback"
    return doc, "mode file read"


def declared_lanes(doc: dict[str, Any] | None = None) -> tuple[str, ...]:
    """The lanes that trade gold. Always holds the leader; unknown names are ignored."""
    doc = _mode_doc()[0] if doc is None else doc
    raw = doc.get("lanes")
    if not isinstance(raw, list):
        return DEFAULT_LANES
    lanes = [str(x).strip().lower() for x in raw if str(x).strip().lower() in KNOWN_LANES]
    if LEADER not in lanes:
        lanes.insert(0, LEADER)
    return tuple(dict.fromkeys(lanes))


def configured_mode(lane: str, doc: dict[str, Any] | None = None) -> str:
    """"leader" for E8; "oco" only when the mode file says so for this lane; else "fallback"."""
    if lane == LEADER:
        return "leader"
    doc = _mode_doc()[0] if doc is None else doc
    modes = doc.get("modes") if isinstance(doc.get("modes"), dict) else {}
    return "oco" if str((modes or {}).get(lane, "")).strip().lower() == "oco" else "fallback"


# ------------------------------------------------------------------ lane state

def _row(row: dict[str, Any], kind: str) -> dict[str, Any]:
    side = side_of(row.get("side"))
    if side is None:
        raise ValueError(f"a gold {kind} has an unreadable side")
    out = {"side": side, "id": None if row.get("id") is None else str(row.get("id"))}
    if kind == "position":
        out["opened_date"] = row.get("opened_date")
    return out


def publish_lane(lane: str, key: str, *, positions: list[dict[str, Any]],
                 orders: list[dict[str, Any]], date: str,
                 now: datetime | None = None) -> Path:
    """Write `lane`'s gold state: every open XAU position and resting XAU ENTRY on its account.
    A row whose side cannot be read publishes the state as unreadable, so the other lanes fail
    closed at once instead of waiting for it to age. RAISES on a bad key or a failed write."""
    if lane not in KNOWN_LANES:
        raise ValueError(f"unknown gold lane {lane!r}")
    if not _xa.valid_key(key):
        raise ValueError("a gold lane state must carry a valid account key")
    body: dict[str, Any] = {"lane": lane, "account_key": key, "protocol": PROTOCOL,
                            "at": (now or datetime.now(tz=UTC)).isoformat(),
                            "trading_date": str(date), "symbol": SYMBOL, "readable": True}
    try:
        body["positions"] = [_row(p, "position") for p in positions]
        body["orders"] = [_row(o, "order") for o in orders]
    except ValueError as exc:
        body.update({"readable": False, "why": str(exc), "positions": [], "orders": []})
    return _write(lane_path(lane), body)


def read_lane(lane: str, *, now: datetime | None = None,
              max_age_s: float = MAX_STATE_AGE_S) -> tuple[dict[str, Any] | None, str]:
    """(`lane`'s gold state, why), or (None, why) when absent, torn, unreadable or stale."""
    try:
        doc = _read_sealed(lane_path(lane))
    except FileNotFoundError:
        return None, f"the {lane} gold state is absent"
    except ValueError as exc:
        return None, f"the {lane} gold state is {exc}"
    try:
        if doc.get("lane") != lane:
            raise ValueError("it names another lane")
        if not _xa.valid_key(doc.get("account_key")):
            raise ValueError("it names no account key")
        if not doc.get("readable"):
            raise ValueError(f"its lane could not read its own book ({doc.get('why')})")
        at = datetime.fromisoformat(str(doc["at"]))
        if at.tzinfo is None:
            raise ValueError("its timestamp is naive")
        for kind in ("positions", "orders"):
            rows = doc[kind]
            if not isinstance(rows, list) or any(side_of((r or {}).get("side")) is None
                                                 for r in rows):
                raise ValueError(f"its {kind} are not readable rows")
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"the {lane} gold state is torn ({exc})"
    age = ((now or datetime.now(tz=UTC)) - at).total_seconds()
    if not (-60.0 <= age <= max_age_s):
        return None, (f"the {lane} gold state is {age:.0f}s old (limit {max_age_s:.0f}s); that "
                      f"account's gold positions are unknown now")
    return doc, f"{lane} gold state {age:.0f}s old"


# ------------------------------------------------------------------ the direction state

def read_directions() -> tuple[dict[str, Any] | None, str]:
    """({date: entry}, why). An ABSENT file is no direction yet ({}); a torn one is None."""
    try:
        doc = _read_sealed(direction_path())
    except FileNotFoundError:
        return {}, "no direction state yet"
    except ValueError as exc:
        return None, f"the gold direction state is {exc}"
    days = doc.get("days")
    if not isinstance(days, dict):
        return None, "the gold direction state is torn (no days)"
    for d, e in days.items():
        if not isinstance(e, dict) or e.get("date") != d or side_of(e.get("direction")) is None \
                or not _xa.valid_key(e.get("first_fill_account_key")) \
                or not isinstance(e.get("legs_cancelled"), list):
            return None, f"the gold direction state is torn (day {d!r})"
    return days, "direction state read"


def day_entry(date: str) -> tuple[dict[str, Any] | None, str | None]:
    """(today's entry or None, None) -- or (None, why) when the state cannot be read."""
    days, why = read_directions()
    if days is None:
        return None, why
    return days.get(str(date)), None


def _save_days(days: dict[str, Any], today: str) -> None:
    try:
        cutoff = (datetime.fromisoformat(today) - timedelta(days=KEEP_DAYS)).date().isoformat()
    except ValueError:
        cutoff = ""
    kept = {d: e for d, e in days.items() if d >= cutoff}
    _write(direction_path(), {"protocol": PROTOCOL, "days": kept})


def claim_fill(lane: str, key: str, side: object, *, date: str, filled_at: str | None = None,
               holder: str = "gold_oco", wait_s: float = CLAIM_WAIT_S) -> dict[str, Any]:
    """Claim the day's direction for a fill on `lane`. Under the one placement lock, so exactly
    one claim per day wins. Returns {"ok", "won", "direction", "first_fill_lane", "conflict",
    "why"}: ok False when the lock was not taken or the state is unreadable (retry next pass); a
    claim AGAINST the day's direction is recorded in `conflicts` and returned conflict=True."""
    want = side_of(side)
    out: dict[str, Any] = {"ok": False, "won": False, "direction": None,
                           "first_fill_lane": None, "conflict": False, "why": ""}
    if want is None or lane not in KNOWN_LANES or not _xa.valid_key(key):
        out["why"] = "unreadable side, lane or account key; nothing claimed"
        return out
    try:
        with _xa.placement_lock(f"{holder}:claim", wait_s=wait_s) as locked:
            if not locked:
                out["why"] = "the placement lock is held elsewhere; the claim waits a pass"
                return out
            days, why = read_directions()
            if days is None:
                out["why"] = f"{why}; nothing claimed"
                return out
            at = filled_at or datetime.now(tz=UTC).isoformat(timespec="seconds")
            entry = days.get(str(date))
            if entry is None:
                entry = {"date": str(date), "direction": want, "first_fill_account_key": key,
                         "first_fill_lane": lane, "first_fill_at": at,
                         "claimed_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                         "legs_cancelled": [], "conflicts": []}
                days[str(date)] = entry
                _save_days(days, str(date))
                out.update({"ok": True, "won": True})
            elif side_of(entry.get("direction")) == want:
                out["ok"] = True
            else:
                seen = entry.setdefault("conflicts", [])
                if not any(c.get("lane") == lane and c.get("account_key") == key
                           and c.get("side") == want for c in seen):
                    seen.append({"lane": lane, "account_key": key, "side": want, "at": at})
                    _save_days(days, str(date))
                out.update({"ok": True, "conflict": True})
            out.update({"direction": entry.get("direction"),
                        "first_fill_lane": entry.get("first_fill_lane"),
                        "why": f"{date}: {entry.get('direction')} set by "
                               f"{entry.get('first_fill_lane')}"})
    except Exception as exc:
        out.update({"ok": False, "why": f"claim failed ({type(exc).__name__}: {exc})"[:200]})
    return out


def note_cancelled(date: str, lane: str, key: str, order_id: object, side: object, *,
                   holder: str = "gold_oco", wait_s: float = CLAIM_WAIT_S) -> bool:
    """Record a leg the direction lock cancelled in the day's `legs_cancelled`. Never raises."""
    try:
        with _xa.placement_lock(f"{holder}:note", wait_s=wait_s) as locked:
            if not locked:
                return False
            days, _why = read_directions()
            if days is None or str(date) not in days:
                return False
            legs = days[str(date)].setdefault("legs_cancelled", [])
            oid = None if order_id is None else str(order_id)
            if not any(leg.get("lane") == lane and leg.get("order_id") == oid for leg in legs):
                legs.append({"lane": lane, "account_key": key, "order_id": oid,
                             "side": side_of(side),
                             "at": datetime.now(tz=UTC).isoformat(timespec="seconds")})
                _save_days(days, str(date))
            return True
    except Exception:
        return False


def observe_fills(lane: str, key: str, positions: list[dict[str, Any]], *, date: str,
                  holder: str = "gold_oco") -> list[dict[str, Any]]:
    """Claim the day's direction from the lane's own open gold positions opened today. A position
    whose open date cannot be read is treated as today's (it claims toward a position that IS
    open, the cautious error). Positions carried from an earlier day claim nothing; they still
    block the opposite side through `gate`'s rule 3."""
    out: list[dict[str, Any]] = []
    for p in positions:
        opened = p.get("opened_date")
        if opened not in (None, "") and str(opened) != str(date):
            continue
        res = claim_fill(lane, key, p.get("side"), date=date,
                         filled_at=p.get("opened_at") or None, holder=holder)
        out.append({"position_id": p.get("id"), **res})
        if res.get("ok") and (res.get("won") or res.get("direction")):
            # One claim settles the day; later positions only add conflicts if they oppose it.
            continue
    return out


# ------------------------------------------------------------------ the gate

def _key_join_refusal(lane: str, key: object) -> str | None:
    """Why `lane`'s account key does not JOIN, or None. A key that cannot be resolved, or that
    differs from the key the box declares for that account (`cross_account.expected_key`: Fusion
    from its declared live login, E8 from E8_ACCOUNT.json), is never read as "that account holds
    nothing" (auditor key-join ruling): the gate fails closed on it. A lane with no declaration
    (FTMO; or none on this box) is checked for shape only."""
    if not _xa.valid_key(key):
        return f"the {lane} account key is unresolvable"
    try:
        want = _xa.expected_key(lane) if lane in _xa.ACCOUNTS else None
    except Exception as exc:
        return f"the {lane} declared account key is unreadable ({type(exc).__name__})"
    if want is None:
        return None
    if not _xa.valid_key(want):
        return f"the {lane} account declaration is invalid ({want})"
    if want != key:
        return (f"the {lane} gold state's account key does not join the key the box declares "
                f"for that account (a pin under another key: re-declare it)")
    return None


def gate(lane: str | None, side: object, *, key: str | None, date: str,
         now: datetime | None = None) -> Verdict:
    """May `lane` place a gold leg of `side` today? FAILS CLOSED on anything it cannot read."""
    want = side_of(side)
    if lane is None or lane not in KNOWN_LANES:
        return Verdict(False, f"gold OCO: {lane!r} is not a known gold lane; fail closed")
    if want is None:
        return Verdict(False, f"gold OCO: unreadable leg side {side!r}; fail closed")
    if not _xa.valid_key(key):
        return Verdict(False, "gold OCO: this lane's account cannot be named by a keyed account "
                              "key; fail closed")
    doc, mode_why = _mode_doc()
    lanes = declared_lanes(doc)
    if lane not in lanes:
        return Verdict(False, f"gold OCO: lane {lane} is not declared in GOLD_OCO_MODE.json "
                              f"lanes {list(lanes)}; fail closed")
    entry, dwhy = day_entry(date)
    if dwhy is not None:
        return Verdict(False, f"gold OCO: {dwhy}; fail closed")
    jwhy = _key_join_refusal(lane, key)
    if jwhy:
        return Verdict(False, f"gold OCO: {jwhy}; fail closed")
    states: dict[str, dict[str, Any]] = {}
    for other in lanes:
        if other == lane:
            continue
        st, why = read_lane(other, now=now)
        if st is None:
            return Verdict(False, f"gold OCO: {why}; fail closed")
        jwhy = _key_join_refusal(other, st.get("account_key"))
        if jwhy is None and st.get("account_key") == key:
            jwhy = (f"the {other} gold state carries THIS lane's account key: two lanes on one "
                    f"account cannot be read as two books")
        if jwhy:
            return Verdict(False, f"gold OCO: {jwhy}; fail closed")
        states[other] = st
    mode = configured_mode(lane, doc)
    if mode == "oco" and any(int(st.get("protocol") or 0) != PROTOCOL for st in states.values()):
        mode = "fallback"           # full OCO is not proven while any lane runs older code
    against = opposite(want)
    for other, st in states.items():
        if any(side_of(p.get("side")) == against for p in st.get("positions") or []):
            return Verdict(False, f"gold OCO: {other} holds an open gold {against}; a {want} "
                                  f"here would open against it", mode)
        if any(side_of(o.get("side")) == against for o in st.get("orders") or []):
            return Verdict(False, f"gold OCO: {other} rests a gold {against} entry; a {want} "
                                  f"here could fill against it", mode)
    if entry is not None:
        d, first = side_of(entry.get("direction")), entry.get("first_fill_lane")
        if mode == "fallback" and first != LEADER:
            return Verdict(False, f"gold OCO fallback: {date}'s direction was set by {first}, "
                                  f"and fallback copies only E8's first fill", mode)
        if want != d:
            return Verdict(False, f"gold OCO: {date}'s direction is {d} (first fill on "
                                  f"{first}); no {want} gold leg on any account today", mode)
        return Verdict(True, f"gold OCO: {date}'s direction is {d}; this leg agrees", mode)
    if mode == "fallback":
        return Verdict(False, f"gold OCO fallback: no E8 fill yet on {date}; this lane places "
                              f"nothing until E8's first fill sets the direction ({mode_why})",
                       mode)
    return Verdict(True, f"gold OCO: no direction yet on {date}; {mode} mode", mode)


# ------------------------------------------------------------------ venue readers

def mt5_gold_rows(mt5: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(positions, entries) of XAU on the MT5 account under `mt5`, every magic (the ACCOUNT's
    book, not one lane's). RAISES when the terminal does not answer."""
    positions = mt5.positions_get()
    orders = mt5.orders_get()
    if positions is None or orders is None:
        raise ValueError("the MT5 terminal did not answer positions_get/orders_get")
    pos: list[dict[str, Any]] = []
    for p in positions:
        if _xa.norm(getattr(p, "symbol", "")) != SYMBOL:
            continue
        t = int(getattr(p, "type", -1))
        ts = getattr(p, "time", None)
        pos.append({"id": getattr(p, "ticket", None),
                    "side": "long" if t == 0 else "short" if t == 1 else None,
                    "opened_date": trading_date(ts) if isinstance(ts, (int, float))
                    and not isinstance(ts, bool) and ts > 0 else None})
    ords: list[dict[str, Any]] = []
    for o in orders:
        if _xa.norm(getattr(o, "symbol", "")) != SYMBOL:
            continue
        t = int(getattr(o, "type", -1))
        if t == 8:
            continue
        ords.append({"id": getattr(o, "ticket", None),
                     "side": "long" if t in (0, 2, 4, 6) else "short" if t in (1, 3, 5, 7)
                     else None})
    return pos, ords


def tradelocker_gold_rows(positions: list[dict[str, Any]], orders: list[dict[str, Any]],
                          instrument_id: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(positions, entries) of XAU on the TradeLocker account; protective stops and targets are
    not entries (`cross_account.tradelocker_entry_orders`). Pure."""
    def gold(r: dict[str, Any]) -> bool:
        iid: Any = r.get("tradableInstrumentId") or r.get("instrumentId")
        try:
            return iid is not None and int(iid) == int(instrument_id) and bool(instrument_id)
        except (TypeError, ValueError):
            return False
    pos = [{"id": p.get("id"), "side": p.get("side"),
            "opened_date": ms_trading_date(p.get("openDate"))} for p in positions if gold(p)]
    entries = _xa.tradelocker_entry_orders(positions, orders)
    # A row with no instrument field cannot be told apart from gold: it counts (fail closed).
    ords = [{"id": o.get("id"), "side": o.get("side")} for o in entries
            if gold(o) or (o.get("tradableInstrumentId") is None
                           and o.get("instrumentId") is None)]
    return pos, ords


def sync_lane(lane: str, key: str, rows: Callable[[], tuple[list[dict[str, Any]],
                                                          list[dict[str, Any]]]],
              *, date: str, holder: str) -> dict[str, Any]:
    """Publish `lane`'s gold state from a reading taken UNDER the placement lock, then claim the
    day's direction from its fills. Never raises; returns what happened."""
    out: dict[str, Any] = {"lane": lane, "published": False, "claims": []}
    try:
        with _xa.placement_lock(f"{holder}:gold_oco", wait_s=_xa.PUBLISH_WAIT_S) as locked:
            if not locked:
                out["why"] = "the placement lock is held elsewhere; not published (it ages)"
                return out
            positions, orders = rows()
            publish_lane(lane, key, positions=positions, orders=orders, date=date)
            out["published"] = True
            out["claims"] = observe_fills(lane, key, positions, date=date, holder=holder)
    except Exception as exc:
        out["why"] = f"{type(exc).__name__}: {exc}"[:200]
    return out
