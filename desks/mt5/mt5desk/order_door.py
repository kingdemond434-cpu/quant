"""ONE DOOR FOR MONEY: every order, close, cancel and stop move the desk sends goes through here.

WHY (the lost 25-Sep lane, rebuilt 2026-09-30). The gateway reached the venue through ten bare
`mt5.order_send` call sites and the prop lanes through five more TradeLocker writes, each with its
own idea of what to check, what to log and what to do when the call raised. Nine of those sites
place or move a STOP, and five of the nine shared nothing with the others. So the one question a
money audit asks first -- "what did the desk try to send, what did the venue say, and did anything
fail silently?" -- had no single answer anywhere on the desk.

WHAT THE DOOR DOES, per attempt, in this order:

  1. CLASSIFY the request: `open` (new risk: a DEAL without a position, a PENDING), `close`
     (DEAL on a position, CLOSE_BY), `stop` (SLTP), `cancel` (REMOVE), `modify` (a pending
     MODIFY). Only `open` is new risk.
  2. DUPLICATE GUARD. An `open` whose previous identical attempt ended IN DOUBT (the send raised,
     timed out or returned None, so the venue may or may not hold the order) is not sent again
     until the venue has been asked. If the venue shows the in-doubt order landed (a resting
     order, an open position or an entry deal under the same magic and comment, placed after the
     in-doubt attempt), this attempt is refused as a duplicate. If the venue shows nothing, the
     key is cleared and the order goes. The in-doubt record is a FILE, because the gateway is a
     process per pass: a restart is the ordinary case, not the exotic one.
  3. PRE-SEND CHECK: `order_check` against the broker. An `open` the broker explicitly rejects
     is refused and never sent -- the broker would refuse the send with the same code, so this
     costs no trade the venue would have taken. A risk-REDUCING action (close, stop, cancel) is
     NEVER blocked by the check: a pre-check that is wrong about a close would leave exposure
     unmanaged, which is strictly worse than a loud failed send. A check that is unavailable,
     returns None or raises is recorded UNMEASURED and the send proceeds on its own answer.
  4. SEND, exactly once. The door never retries: a requote, a rejection, a timeout and a
     disconnect are all reported to the caller as they happened, and a retry is the caller's
     decision on the next pass, made against the venue's state. An exception from `order_send`
     is logged and RE-RAISED, never swallowed.
  5. VALIDATE the answer: the retcode, the filled volume against the requested one (a partial
     or an over-fill is named), the fill price on a market deal (a DONE deal at price 0 is
     named), and a ticket on a placed order. Validation never rewrites the answer; the caller
     gets the venue's own result object, so every existing reader of `res.retcode` is unchanged.
  6. LEDGER: one JSONL row per attempt in `data/order_door_ledger.jsonl` -- request, class,
     check verdict, retcode, validation verdict, latency, caller. A ledger write that fails is
     logged; it never costs the order.

HOW IT IS WIRED. `guard(mt5_module)` returns a proxy whose `order_send` IS `send`, and every
other attribute is the module's own. `gateway.py` binds `mt5 = order_door.guard(MetaTrader5)`,
so each of its call sites goes through the door by construction and a new call site cannot
bypass it by accident; `tests/test_order_door_chaos.py` fences that statically. The TradeLocker
lanes (`prop/e8_executor.py`, `prop/e8_gold.py`) wrap their venue with `guard_venue`, whose
place / place_stop / modify_stop / close / cancel / close_all go through `venue_act`.

WHAT IT NEVER DOES. It never changes a size, a price, a stop or a target; it never adds a veto
on new risk the broker itself would have accepted; it never blocks a close, a stop move or a
cancel. It adds correctness only -- the principal's standing order is that the desk never
reduces its aggressiveness.

`restart_reconcile` is the startup half: before anything new is placed on a pass it reads the
venue's own positions and orders under this desk's magic, resolves the in-doubt keys against
them, and restores a stop on any own position that is holding without one (from the stop the
intent ledger recorded at placement, and only when that level still rests on the right side of
the market). Its row goes to the same ledger.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# MT5's documented constants, used when the module in hand (a fake, an old build) lacks one.
_ACTION_DEFAULTS = {"TRADE_ACTION_DEAL": 1, "TRADE_ACTION_PENDING": 5, "TRADE_ACTION_SLTP": 6,
                    "TRADE_ACTION_MODIFY": 7, "TRADE_ACTION_REMOVE": 8,
                    "TRADE_ACTION_CLOSE_BY": 10}
RETCODE_PLACED = 10008
RETCODE_DONE = 10009
RETCODE_DONE_PARTIAL = 10010
SUCCESS = frozenset({RETCODE_PLACED, RETCODE_DONE, RETCODE_DONE_PARTIAL})
#: `order_check` answers 0 for a request it would accept (MqlTradeCheckResult); some builds
#: answer with the send-side success codes. Anything else is the broker saying no.
CHECK_OK = frozenset({0}) | SUCCESS
RETCODE_NAMES = {10004: "requote", 10006: "reject", 10007: "cancelled_by_client",
                 10008: "placed", 10009: "done", 10010: "done_partial", 10012: "timeout",
                 10013: "invalid_request", 10014: "invalid_volume", 10015: "invalid_price",
                 10016: "invalid_stops", 10018: "market_closed", 10019: "no_money",
                 10020: "price_changed", 10021: "price_off", 10024: "too_many_requests",
                 10027: "autotrading_disabled", 10031: "no_connection"}

OPEN, CLOSE, STOP, CANCEL, MODIFY, UNKNOWN = "open", "close", "stop", "cancel", "modify", "unknown"
RISK_REDUCING = frozenset({CLOSE, STOP, CANCEL})

#: How long an in-doubt attempt keeps guarding an identical resend. Long enough to cover the next
#: pass of every lane that could resend the same order (the gateway runs every few minutes, and a
#: resend is the NEXT pass's retry); short enough that a scalp add-on of the same size an hour
#: later is judged by the lane's own logic, not by an old timeout.
IN_DOUBT_TTL = timedelta(minutes=45)

LEDGER_NAME = "order_door_ledger.jsonl"
IN_DOUBT_NAME = "order_door_in_doubt.json"


class DoorRefused(SimpleNamespace):
    """The answer the door gives in place of a send it refused. Shaped like `OrderSendResult`
    (retcode, comment, order, deal, volume, price) so every caller that reads a venue result
    reads this the same way, plus `door_refused=True` and the `door_reason`.

    A refused `open` carries the BROKER'S OWN check retcode when the broker said no, so the
    gateway's rejection diagnostics and its escalation counter see the code the send would have
    returned. A duplicate refusal carries retcode None: nothing was sent and nothing was
    rejected, which is the truth."""


# ------------------------------------------------------------------ paths and the log sink
def _data_dir() -> Path:
    override = os.environ.get("MT5_ORDER_DOOR_DIR")
    if override:
        return Path(override)
    try:
        from mt5desk.config import desk_root
        return desk_root() / "data"
    except Exception:                                   # pragma: no cover - import path only
        return Path(__file__).resolve().parents[1] / "data"


def ledger_path() -> Path:
    return _data_dir() / LEDGER_NAME


def in_doubt_path() -> Path:
    return _data_dir() / IN_DOUBT_NAME


def _default_log(msg: str) -> None:
    print(f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} ORDER-DOOR {msg}",
          file=sys.stderr)


def _emit(log: Callable[[str], None] | None, msg: str) -> None:
    """Log through the caller's sink; a sink that itself fails falls back to stderr, so a
    broken log file can never make a money line disappear."""
    try:
        (log or _default_log)(msg)
    except Exception:
        _default_log(msg)


def _jsonable(v: Any) -> Any:
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    return str(v)


def append_ledger(row: Mapping[str, Any], *, log: Callable[[str], None] | None = None) -> bool:
    """Append one row. Returns False (and says so, loudly) when the write failed; never raises,
    because on the money path a lost ledger row is cheaper than a lost order."""
    try:
        p = ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_jsonable(dict(row)), sort_keys=True) + "\n")
        return True
    except Exception as exc:
        _emit(log, f"LEDGER WRITE FAILED ({type(exc).__name__}: {exc}); attempt "
                   f"{row.get('kind')} {row.get('symbol')} retcode={row.get('retcode')} "
                   f"is recorded in this log line only")
        return False


def read_ledger(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or ledger_path()
    out: list[dict[str, Any]] = []
    try:
        for ln in p.read_text("utf-8").splitlines():
            with contextlib.suppress(ValueError):
                out.append(json.loads(ln))
    except OSError:
        return []
    return out


# ------------------------------------------------------------------ classification
def _const(mt5: Any, name: str) -> int:
    v = getattr(mt5, name, None)
    return int(v) if isinstance(v, int) else _ACTION_DEFAULTS[name]


def classify(mt5: Any, request: Mapping[str, Any]) -> str:
    """Which kind of money action a request is. Pure over the request and the module's enums."""
    action = request.get("action")
    if action == _const(mt5, "TRADE_ACTION_DEAL"):
        return CLOSE if request.get("position") else OPEN
    if action == _const(mt5, "TRADE_ACTION_PENDING"):
        return OPEN
    if action == _const(mt5, "TRADE_ACTION_SLTP"):
        return STOP
    if action == _const(mt5, "TRADE_ACTION_REMOVE"):
        return CANCEL
    if action == _const(mt5, "TRADE_ACTION_CLOSE_BY"):
        return CLOSE
    if action == _const(mt5, "TRADE_ACTION_MODIFY"):
        return MODIFY
    return UNKNOWN


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def dedupe_key(request: Mapping[str, Any]) -> str:
    """The identity of an `open` for the duplicate guard: the same symbol, magic, comment, order
    type and volume -- and, for a resting order, the same trigger price. A market order's price
    moves between passes and is deliberately not part of it."""
    parts = [str(request.get("symbol") or ""), str(request.get("magic") or ""),
             str(request.get("comment") or ""), str(request.get("type") or ""),
             f"{_num(request.get('volume')) or 0.0:.8g}"]
    if request.get("action") == _ACTION_DEFAULTS["TRADE_ACTION_PENDING"]:
        parts.append(f"{_num(request.get('price')) or 0.0:.8g}")
    return "|".join(parts)


# ------------------------------------------------------------------ in-doubt memory
def load_in_doubt() -> dict[str, dict[str, Any]]:
    try:
        doc = json.loads(in_doubt_path().read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): v for k, v in (doc or {}).items() if isinstance(v, dict)}


def save_in_doubt(doc: Mapping[str, Any], *, log: Callable[[str], None] | None = None) -> bool:
    try:
        p = in_doubt_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(_jsonable(dict(doc)), indent=1, sort_keys=True), "utf-8")
        tmp.replace(p)
        return True
    except Exception as exc:
        _emit(log, f"IN-DOUBT FILE WRITE FAILED ({type(exc).__name__}: {exc}); the duplicate "
                   f"guard holds this attempt in memory only")
        return False


def _prune(doc: dict[str, dict[str, Any]], now: datetime) -> dict[str, dict[str, Any]]:
    keep: dict[str, dict[str, Any]] = {}
    for k, v in doc.items():
        try:
            at = datetime.fromisoformat(str(v.get("at")))
        except ValueError:
            continue
        if now - at <= IN_DOUBT_TTL:
            keep[k] = v
    return keep


_MEMORY_IN_DOUBT: dict[str, dict[str, Any]] = {}


def _in_doubt_now(now: datetime) -> dict[str, dict[str, Any]]:
    doc = {**load_in_doubt(), **_MEMORY_IN_DOUBT}
    return _prune(doc, now)


def _mark_in_doubt(key: str, request: Mapping[str, Any], why: str, now: datetime,
                   log: Callable[[str], None] | None) -> None:
    rec = {"at": now.isoformat(timespec="seconds"), "symbol": request.get("symbol"),
           "comment": request.get("comment"), "magic": request.get("magic"),
           "type": request.get("type"), "volume": request.get("volume"),
           "price": request.get("price"), "why": why}
    _MEMORY_IN_DOUBT[key] = rec
    doc = _prune(load_in_doubt(), now)
    doc[key] = rec
    if save_in_doubt(doc, log=log):
        _MEMORY_IN_DOUBT.pop(key, None)


def _clear_in_doubt(key: str, log: Callable[[str], None] | None) -> None:
    _MEMORY_IN_DOUBT.pop(key, None)
    doc = load_in_doubt()
    if key in doc:
        doc.pop(key)
        save_in_doubt(doc, log=log)


def _epoch(v: Any) -> float | None:
    f = _num(v)
    return f if f is not None and f > 0 else None


def venue_evidence(mt5: Any, rec: Mapping[str, Any]) -> tuple[str | None, bool]:
    """(what the venue shows for an in-doubt attempt, whether the venue could be read at all).

    Asks three things under the attempt's own magic and comment, each for something created at
    or after the attempt: a resting order, an open position, an entry deal. The venue's clock
    and the desk's differ by the broker offset, so the time test is relaxed by a day on the
    lower side -- an in-doubt key only lives `IN_DOUBT_TTL`, and a same-comment order older than
    that is not the attempt in question but is still no reason to send a second copy.
    """
    symbol = str(rec.get("symbol") or "")
    comment = str(rec.get("comment") or "")
    magic = rec.get("magic")
    try:
        since = datetime.fromisoformat(str(rec.get("at"))) - timedelta(days=1)
    except ValueError:
        since = datetime.now(tz=UTC) - timedelta(days=1)

    def _own(x: Any) -> bool:
        if comment and str(getattr(x, "comment", "") or "") != comment:
            return False
        return magic is None or int(getattr(x, "magic", magic) or 0) == int(magic)

    readable = False
    try:
        got = mt5.orders_get(symbol=symbol)
        readable = readable or got is not None
        for o in (got or ()):
            if _own(o):
                return f"resting order {getattr(o, 'ticket', '?')} under {comment!r}", True
    except Exception:
        pass
    try:
        got = mt5.positions_get(symbol=symbol)
        readable = readable or got is not None
        for p in (got or ()):
            if _own(p):
                t = _epoch(getattr(p, "time", None))
                if t is None or t >= since.timestamp():
                    return f"open position {getattr(p, 'ticket', '?')} under {comment!r}", True
    except Exception:
        pass
    try:
        got = mt5.history_deals_get(since, datetime.now(tz=UTC) + timedelta(days=1))
        readable = readable or got is not None
        entry_in = int(getattr(mt5, "DEAL_ENTRY_IN", 0) or 0)
        for d in (got or ()):
            if str(getattr(d, "symbol", symbol) or symbol) != symbol or not _own(d):
                continue
            if int(getattr(d, "entry", entry_in)) != entry_in:
                continue
            return f"entry deal {getattr(d, 'ticket', '?')} under {comment!r}", True
    except Exception:
        pass
    return None, readable


# ------------------------------------------------------------------ validation
def validate(kind: str, request: Mapping[str, Any], res: Any) -> tuple[str, list[str]]:
    """(verdict, notes) for the venue's answer. Pure. Never raises, never rewrites `res`.

    Verdicts: `ok`, `partial`, `rejected`, `no_result`, `anomaly`. `notes` name every mismatch
    found, so a DONE whose volume or price does not match the request is visible as such."""
    if res is None:
        return "no_result", ["order_send returned None: the venue's state is IN DOUBT"]
    rc = getattr(res, "retcode", None)
    notes: list[str] = []
    if rc not in SUCCESS:
        return "rejected", [f"retcode {rc} ({RETCODE_NAMES.get(rc, 'unnamed')})"]
    verdict = "partial" if rc == RETCODE_DONE_PARTIAL else "ok"
    want = _num(request.get("volume"))
    got = _num(getattr(res, "volume", None))
    if kind in (OPEN, CLOSE) and want is not None and got is not None and got > 0:
        if got < want - 1e-9:
            verdict = "partial"
            notes.append(f"filled {got:g} of {want:g} requested")
        elif got > want + 1e-9:
            verdict = "anomaly"
            notes.append(f"filled {got:g}, MORE than the {want:g} requested")
    is_deal = request.get("action") == _ACTION_DEFAULTS["TRADE_ACTION_DEAL"]
    if is_deal and rc == RETCODE_DONE:
        px = _num(getattr(res, "price", None))
        if px is None or px <= 0:
            verdict = "anomaly"
            notes.append("a DONE market deal reported no fill price")
        else:
            asked = _num(request.get("price"))
            if asked:
                notes.append(f"fill {px:.8g} vs asked {asked:.8g} "
                             f"(slippage {px - asked:+.8g})")
    if kind == OPEN and rc in (RETCODE_PLACED, RETCODE_DONE) \
            and not int(_num(getattr(res, "order", None)) or 0) \
            and not int(_num(getattr(res, "deal", None)) or 0):
        verdict = "anomaly"
        notes.append("accepted but carries neither an order nor a deal ticket")
    return verdict, notes


def _check(mt5: Any, request: Mapping[str, Any]) -> tuple[str, int | None, str]:
    """(verdict, retcode, comment) of `order_check`: `pass`, `reject` or `unmeasured`."""
    fn = getattr(mt5, "order_check", None)
    if not callable(fn):
        return "unmeasured", None, "order_check unavailable on this module"
    try:
        chk = fn(dict(request))
    except Exception as exc:
        return "unmeasured", None, f"order_check raised {type(exc).__name__}: {exc}"
    if chk is None:
        err = None
        with contextlib.suppress(Exception):
            err = mt5.last_error()
        return "unmeasured", None, f"order_check returned None (last_error={err!r})"
    rc = getattr(chk, "retcode", None)
    comment = str(getattr(chk, "comment", "") or "")
    try:
        rc_i = int(rc) if rc is not None else None
    except (TypeError, ValueError):
        rc_i = None
    if rc_i in CHECK_OK:
        return "pass", rc_i, comment
    return "reject", rc_i, comment


# ------------------------------------------------------------------ THE door
def send(mt5: Any, request: Mapping[str, Any], *, caller: str = "",
         log: Callable[[str], None] | None = None,
         now: Callable[[], datetime] | None = None) -> Any:
    """The one function every MT5 order_send on this desk goes through. See the module doc.

    Returns the venue's own result (or a `DoorRefused`). Raises exactly what `order_send`
    raised, after logging it and marking the attempt in doubt."""
    clock = now or (lambda: datetime.now(tz=UTC))
    req = dict(request)
    kind = classify(mt5, req)
    t_now = clock()
    row: dict[str, Any] = {"at": t_now.isoformat(timespec="seconds"), "caller": caller,
                           "kind": kind, "symbol": req.get("symbol"),
                           "comment": req.get("comment"), "request": req}
    where = f"[{caller or 'door'}] {kind} {req.get('symbol') or ''} {req.get('comment') or ''}"

    if kind == OPEN and not (_num(req.get("sl")) or 0.0) > 0:
        # NOT a veto: recorded so a naked entry can never be invisible. Every lane on this desk
        # sends its stop with the order; one that does not is a defect to find, loudly.
        row["no_stop"] = True
        _emit(log, f"{where}: WARNING opening order carries no stop (sl={req.get('sl')!r})")

    key = dedupe_key(req) if kind == OPEN else ""
    if key:
        held = _in_doubt_now(t_now).get(key)
        if held is not None:
            seen, readable = venue_evidence(mt5, held)
            row["in_doubt_since"] = held.get("at")
            if seen:
                row.update({"door": "refused", "reason": "duplicate_of_in_doubt",
                            "evidence": seen, "retcode": None})
                _emit(log, f"{where}: REFUSED -- an identical attempt at {held.get('at')} ended "
                           f"in doubt and the venue shows it landed ({seen}); not sent twice")
                append_ledger(row, log=log)
                return DoorRefused(retcode=None, comment=f"order_door: duplicate ({seen})",
                                   order=0, deal=0, volume=0.0, price=0.0, door_refused=True,
                                   door_reason="duplicate_of_in_doubt")
            if not readable:
                row.update({"door": "refused", "reason": "in_doubt_venue_unreadable",
                            "retcode": None})
                _emit(log, f"{where}: REFUSED -- an identical attempt at {held.get('at')} is in "
                           f"doubt and the venue could not be read to settle it")
                append_ledger(row, log=log)
                return DoorRefused(retcode=None,
                                   comment="order_door: in doubt, venue unreadable",
                                   order=0, deal=0, volume=0.0, price=0.0, door_refused=True,
                                   door_reason="in_doubt_venue_unreadable")
            _clear_in_doubt(key, log)
            row["in_doubt_resolved"] = "venue shows nothing; the earlier attempt did not land"

    verdict, crc, ccomment = _check(mt5, req)
    row.update({"check": verdict, "check_retcode": crc, "check_comment": ccomment})
    if verdict == "reject" and kind == OPEN:
        row.update({"door": "refused", "reason": "broker_check_rejected", "retcode": crc})
        _emit(log, f"{where}: REFUSED by the broker's order_check: retcode {crc} "
                   f"({RETCODE_NAMES.get(crc or 0, 'unnamed')}) {ccomment}")
        append_ledger(row, log=log)
        return DoorRefused(retcode=crc, comment=f"order_check: {ccomment}", order=0, deal=0,
                           volume=0.0, price=0.0, door_refused=True,
                           door_reason="broker_check_rejected")
    if verdict == "reject":
        _emit(log, f"{where}: order_check says retcode {crc} ({ccomment}); a {kind} is never "
                   f"blocked by a pre-check, sending")

    t0 = time.perf_counter()
    try:
        res = mt5.order_send(req)
    except BaseException as exc:
        row.update({"door": "sent", "outcome": "exception",
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3)})
        if key:
            _mark_in_doubt(key, req, f"order_send raised {type(exc).__name__}", t_now, log)
            row["in_doubt"] = True
        _emit(log, f"{where}: order_send RAISED {type(exc).__name__}: {exc} -- the venue's "
                   f"state is IN DOUBT; not retried, propagated")
        append_ledger(row, log=log)
        raise
    row["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
    vverdict, notes = validate(kind, req, res)
    rc = getattr(res, "retcode", None) if res is not None else None
    row.update({"door": "sent", "retcode": rc,
                "retcode_name": RETCODE_NAMES.get(rc or 0),
                "venue_comment": (str(getattr(res, "comment", "") or "")
                                  if res is not None else None),
                "order": getattr(res, "order", None) if res is not None else None,
                "deal": getattr(res, "deal", None) if res is not None else None,
                "fill_volume": getattr(res, "volume", None) if res is not None else None,
                "fill_price": getattr(res, "price", None) if res is not None else None,
                "validation": vverdict, "notes": notes})
    if res is None:
        err = None
        with contextlib.suppress(Exception):
            err = mt5.last_error()
        row["last_error"] = err
        if key:
            _mark_in_doubt(key, req, f"order_send returned None (last_error={err!r})", t_now,
                           log)
            row["in_doubt"] = True
        _emit(log, f"{where}: order_send returned None (last_error={err!r}) -- IN DOUBT, "
                   f"not retried")
    elif vverdict != "ok":
        _emit(log, f"{where}: {vverdict.upper()} -- {'; '.join(notes)}")
    append_ledger(row, log=log)
    return res


class GuardedMT5:
    """The MetaTrader5 module with `order_send` routed through `send`. Every other attribute is
    the module's own, read live, so a constant or a reader behaves exactly as before."""

    __slots__ = ("_door_caller", "_door_log", "_door_raw")

    def __init__(self, raw: Any, caller: str, log: Callable[[str], None] | None) -> None:
        object.__setattr__(self, "_door_raw", raw)
        object.__setattr__(self, "_door_caller", caller)
        object.__setattr__(self, "_door_log", log)

    def __getattr__(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_door_raw"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_door_raw"), name, value)

    def __delattr__(self, name: str) -> None:
        delattr(object.__getattribute__(self, "_door_raw"), name)

    def order_send(self, request: Mapping[str, Any]) -> Any:
        raw = object.__getattribute__(self, "_door_raw")
        return send(raw, request, caller=object.__getattribute__(self, "_door_caller"),
                    log=object.__getattribute__(self, "_door_log"))

    @property
    def door_raw(self) -> Any:
        return object.__getattribute__(self, "_door_raw")


def guard(mt5: Any, *, caller: str = "gateway",
          log: Callable[[str], None] | None = None) -> Any:
    """`mt5` with every `order_send` going through the door. Idempotent."""
    if isinstance(mt5, GuardedMT5):
        return mt5
    return GuardedMT5(mt5, caller, log)


def is_guarded(mt5: Any) -> bool:
    return isinstance(mt5, GuardedMT5)


# ------------------------------------------------------------------ the TradeLocker lanes
VENUE_WRITES = {"place": OPEN, "place_stop": OPEN, "modify_stop": STOP, "close": CLOSE,
                "cancel": CANCEL, "close_all": CLOSE}


def venue_act(action: str, fn: Callable[..., Any], *args: Any, caller: str = "",
              log: Callable[[str], None] | None = None, **kwargs: Any) -> Any:
    """One non-MT5 venue write (TradeLocker), through the same ledger. Calls `fn` exactly once.

    A raise is logged and RE-RAISED. A False acknowledgement (cancel / close / modify_stop
    answer a bool) is logged as `not_acknowledged` and returned as it came -- the caller decides
    what a refusal means, and now it cannot be silent."""
    kind = VENUE_WRITES.get(action, UNKNOWN)
    row: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "caller": caller, "venue": "tradelocker", "kind": kind,
                           "action": action, "args": list(args), "kwargs": dict(kwargs)}
    where = f"[{caller or 'door'}] {action}{tuple(args)!r}"
    if action in ("place", "place_stop") and not (_num(kwargs.get("stop")) or 0.0) > 0:
        row["no_stop"] = True
        _emit(log, f"{where}: WARNING opening order carries no stop")
    t0 = time.perf_counter()
    try:
        out = fn(*args, **kwargs)
    except BaseException as exc:
        row.update({"outcome": "exception", "error": f"{type(exc).__name__}: {exc}"[:300],
                    "latency_ms": round((time.perf_counter() - t0) * 1000.0, 3)})
        _emit(log, f"{where}: RAISED {type(exc).__name__}: {exc}; not retried, propagated")
        append_ledger(row, log=log)
        raise
    row["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 3)
    if out is False or out is None:
        row["outcome"] = "not_acknowledged"
        _emit(log, f"{where}: the venue did NOT acknowledge ({out!r})")
    else:
        row["outcome"] = "acknowledged"
        row["result"] = out if isinstance(out, (int, float, str, bool)) else str(out)
    append_ledger(row, log=log)
    return out


class GuardedVenue:
    """A TradeLocker venue whose writes go through `venue_act`; reads are the venue's own."""

    def __init__(self, raw: Any, caller: str, log: Callable[[str], None] | None) -> None:
        self.__dict__["_door_raw"] = raw
        self.__dict__["_door_caller"] = caller
        self.__dict__["_door_log"] = log

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self.__dict__["_door_raw"], name)
        if name in VENUE_WRITES and callable(attr):
            def _through(*args: Any, **kwargs: Any) -> Any:
                return venue_act(name, attr, *args, caller=self.__dict__["_door_caller"],
                                 log=self.__dict__["_door_log"], **kwargs)
            return _through
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self.__dict__["_door_raw"], name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self.__dict__["_door_raw"], name)


def guard_venue(venue: Any, *, caller: str,
                log: Callable[[str], None] | None = None) -> Any:
    if isinstance(venue, GuardedVenue):
        return venue
    return GuardedVenue(venue, caller, log)


# ------------------------------------------------------------------ restart reconciliation
def _intended_stops(intents: Iterable[Mapping[str, Any]]) -> dict[int, float]:
    """Order ticket -> the stop recorded at placement. An MT5 position's ticket is the ticket of
    the order that opened it, which is the ticket the intent row carries."""
    out: dict[int, float] = {}
    for r in intents:
        try:
            t = int(r.get("ticket") or 0)
            sl = float(r.get("sl") or 0.0)
        except (TypeError, ValueError):
            continue
        if t and sl > 0 and math.isfinite(sl):
            out[t] = sl
    return out


def restart_reconcile(mt5: Any, *, magic: int, armed: bool,
                      intents: Iterable[Mapping[str, Any]] = (),
                      log: Callable[[str], None] | None = None,
                      caller: str = "restart_reconcile") -> dict[str, Any]:
    """Reconcile the venue with the desk BEFORE anything new is placed on a pass.

    1. Read this desk's own open positions and resting orders (by magic) -- so a pass that
       starts over a held position knows it holds one.
    2. Settle every in-doubt key against the venue: landed keys stay (the next identical send is
       refused as a duplicate), keys the venue shows nothing for are cleared.
    3. A position held with NO stop has had its stop orphaned (a restart between the fill and a
       modification, a broker that dropped it). Its stop is restored from the intent ledger's
       placement row -- the level the desk certified the trade with -- through the door, and
       only when that level still rests on the protective side of the market; otherwise the
       position is named loudly and left for management. Shadow when unarmed.

    Never raises: an unreadable venue is recorded as UNMEASURED and the pass goes on to the
    gateway's own venue-reading guards.
    """
    rep: dict[str, Any] = {"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                           "caller": caller, "kind": "restart_reconcile", "magic": magic,
                           "armed": bool(armed)}
    try:
        pos = [p for p in (mt5.positions_get() or ())
               if int(getattr(p, "magic", 0) or 0) == int(magic)]
        orders = [o for o in (mt5.orders_get() or ())
                  if int(getattr(o, "magic", 0) or 0) == int(magic)]
    except Exception as exc:
        rep.update({"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]})
        _emit(log, f"RESTART RECONCILE: venue unreadable ({rep['why']}); UNMEASURED")
        append_ledger(rep, log=log)
        return rep
    rep["positions"] = [{"ticket": getattr(p, "ticket", None), "symbol": getattr(p, "symbol", None),
                         "comment": getattr(p, "comment", None),
                         "volume": getattr(p, "volume", None), "sl": getattr(p, "sl", None)}
                        for p in pos]
    rep["orders"] = [{"ticket": getattr(o, "ticket", None), "symbol": getattr(o, "symbol", None),
                      "comment": getattr(o, "comment", None)} for o in orders]
    t_now = datetime.now(tz=UTC)
    settled: list[dict[str, Any]] = []
    for key, rec in _in_doubt_now(t_now).items():
        seen, readable = venue_evidence(mt5, rec)
        if seen:
            settled.append({"key": key, "landed": seen})
        elif readable:
            _clear_in_doubt(key, log)
            settled.append({"key": key, "landed": None, "cleared": True})
        else:
            settled.append({"key": key, "landed": None, "unreadable": True})
    rep["in_doubt"] = settled
    stops = _intended_stops(intents)
    buy = getattr(mt5, "POSITION_TYPE_BUY", 0)
    restored: list[dict[str, Any]] = []
    for p in pos:
        if (_num(getattr(p, "sl", 0.0)) or 0.0) > 0:
            continue
        ticket = int(getattr(p, "ticket", 0) or 0)
        symbol = str(getattr(p, "symbol", "") or "")
        want = stops.get(ticket)
        item: dict[str, Any] = {"ticket": ticket, "symbol": symbol, "intended_sl": want}
        if want is None:
            item["action"] = "none: no placement stop recorded for this ticket"
            _emit(log, f"RESTART RECONCILE: position {ticket} {symbol} is held WITH NO STOP and "
                       f"no placement stop is on record; management must protect it")
            restored.append(item)
            continue
        tick = None
        with contextlib.suppress(Exception):
            tick = mt5.symbol_info_tick(symbol)
        is_buy = getattr(p, "type", None) == buy
        rests = tick is not None and (
            (is_buy and want < float(getattr(tick, "bid", 0.0) or 0.0)) or
            (not is_buy and want > float(getattr(tick, "ask", 0.0) or 0.0)))
        if not rests:
            item["action"] = ("none: the placement stop no longer rests on the protective side "
                              "of the market (or no quote); a stop there would be a market exit")
            _emit(log, f"RESTART RECONCILE: position {ticket} {symbol} has no stop; recorded "
                       f"stop {want} does not rest at the venue now -- left for management")
            restored.append(item)
            continue
        if not armed:
            item["action"] = "shadow: would restore the placement stop"
            _emit(log, f"RESTART RECONCILE: SHADOW would restore stop {want} on {ticket}")
            restored.append(item)
            continue
        req = {"action": _const(mt5, "TRADE_ACTION_SLTP"), "symbol": symbol, "position": ticket,
               "sl": float(want), "tp": float(getattr(p, "tp", 0.0) or 0.0), "magic": int(magic)}
        try:
            res = send(mt5, req, caller=caller, log=log)
            item["action"] = "restored"
            item["retcode"] = getattr(res, "retcode", None) if res is not None else None
        except Exception as exc:
            item["action"] = "restore_raised"
            item["error"] = f"{type(exc).__name__}: {exc}"[:200]
        restored.append(item)
    rep["stopless"] = restored
    rep["verdict"] = "OK"
    _emit(log, f"RESTART RECONCILE: {len(pos)} own position(s), {len(orders)} resting order(s), "
               f"{len(settled)} in-doubt key(s) settled, {len(restored)} stopless position(s)")
    append_ledger(rep, log=log)
    return rep
