"""FTMO FOLLOWER -- one gold_asia order on the FTMO account, only in E8's filled direction.

WHAT IT DOES (coordinator 2026-10-21, URGENT). FTMO is an MT5 account on its own terminal
(`TERMINAL_PATH`, server FTMO-Server2, hedging). This lane never forms its own view of gold:
  1. it places NOTHING until E8's gold_asia has a first filled leg today, read from E8's own
     published state -- `reports/E8_GOLD.json` (fresh, status OK, the asia window holding a
     position), the shared direction state (`mt5desk.gold_oco`, first fill on E8) and E8's
     published gold state (that position still open, on that side). Anything unreadable, stale or
     torn places nothing and writes a reasoned row;
  2. then it places exactly ONE order for the day: a resting entry at E8's filled leg's own level
     with E8's own stop and target (so the same stop distance and the same RR) -- a stop order
     while the price is still short of the level, a limit order once it is through it, so FTMO's
     entry is E8's level, never a chase. Sized by the `ftmo` block's `gold_asia` fraction of
     `data/CERT_BOOK_LIVE.json` (absent, enabled false or void -> nothing) against the stop;
  3. it NEVER opens the opposite side: an FTMO gold position or order the other way, from any
     source, refuses the order and raises an alert; the gold OCO gate (lane "ftmo") also binds;
  4. a resting FTMO order is cancelled the moment E8 no longer shows a live filled asia trade
     (E8's twin cancelled without a fill, its position gone, its guard standing down, or its
     state unreadable), or when the asia window's session ends;
  5. exits mirror the E8 lane: the attached stop and target, E8's ratchet copied when E8 moves
     its stop (`ratchet_stop` on E8's position, applied only when it tightens and still rests),
     and the gold book's close hour (`CLOSE_HOUR`) closes the position.

FTMO'S RULES, enforced before any new order:
  * no new entry within GAP_GUARD_H of a market close (gold's daily close, 17:00 New York);
  * under 2,000 server requests a day: new risk stops at REQUEST_BUDGET trade requests per CET
    day, closes and cancels at REQUEST_HARD_CAP;
  * the 5% daily and 10% maximum loss, measured from the balance at midnight CET (re-derived from
    the deal history every pass): the order is refused when its risk, with E8's measured 24.13-pt
    stop slippage added to the stop distance, plus today's loss could reach 5% of the initial
    balance, or the equity after it could reach 90% of it.

ACCOUNT BINDING. `data/FTMO_LIVE_ACCOUNT.json` (gitignored, written by the principal's own step,
never committed): {"login", "server", "trade_mode", "initial_balance"}. The terminal's
account_info must match login, server and trade_mode, or the lane does nothing at all. The account
is named only by `gold_oco.oco_account_key` (the keyed HMAC); the login is never logged.

ARMING. Standby unless `data/FTMO_FOLLOWER_ARMED` exists (the principal creates it): an unarmed
pass logs and journals exactly what it would send and sends nothing.

SESSION. MetaTrader5.initialize attaches to the running FTMO terminal BY PATH, which only works in
the interactive desktop session: `main` refuses under SSH or in session 0 (a service). The task
`MT5-FTMO-Follower` (scripts/install_ftmo_follower_task.ps1) runs it every minute, Interactive.

    python prop/ftmo_follower.py           one pass, standby unless armed
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import gold_oco as _oco  # noqa: E402
from mt5desk import position_manager as _pm  # noqa: E402
from mt5desk.decision_core import (  # noqa: E402
    BRACKET_TTL_HOURS,
    CANCEL_HOUR,
    CLOSE_HOUR,
    window_end_hour,
)
from mt5desk.kelly_sizing import CERT_BOOK_FILE, load_cert_book  # noqa: E402

LANE = "ftmo"
SYMBOL = "XAUUSD"
WINDOW = "asia"
CERT_KEY = "gold_asia"
TERMINAL_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
TERMINAL_ENV = "QUANT_FTMO_TERMINAL"
ACCOUNT_FILE = DESK / "data" / "FTMO_LIVE_ACCOUNT.json"
ARMED_MARKER = DESK / "data" / "FTMO_FOLLOWER_ARMED"
STATE = DESK / "data" / "ftmo_follower_state.json"
OUT = DESK / "reports" / "FTMO_FOLLOWER.json"
INTENTS = DESK / "data" / "ftmo_follower_intents.jsonl"
LOG = DESK / "logs" / "ftmo_follower.log"
#: E8-Gold's pass report (prop/e8_gold.OUT), the first of the three readings this lane follows.
E8_REPORT = DESK / "reports" / "E8_GOLD.json"
#: E8-Gold passes every five minutes: two passes, the gold OCO's bound (MAX_STATE_AGE_S).
E8_REPORT_MAX_AGE_S = _oco.MAX_STATE_AGE_S
MAGIC = 341955
COMMENT = "FTgold_asia"
#: E8's measured stop slippage (2026-09-24: a buy stop filled 24.13 points through its level).
SLIP_ALLOWANCE_PTS = 24.13
DAILY_LOSS_FRAC = 0.05
MAX_LOSS_FRAC = 0.10
#: FTMO's trading day: midnight CET/CEST.
DAY_TZ = "Europe/Prague"
GAP_GUARD_H = 2.0
REQUEST_BUDGET = 1500
REQUEST_HARD_CAP = 1950
RAIL = "ftmo_follower"
#: Rows written once per reason per day (the lane passes every minute).
_LEG = {"long": "buy", "short": "sell"}


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    with contextlib.suppress(OSError):
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _record(row: dict[str, Any]) -> bool:
    try:
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
        return True
    except OSError as exc:
        log(f"INTENT JOURNAL WRITE FAILED ({type(exc).__name__}); row: {row.get('status')}")
        return False


# ------------------------------------------------------------------ pure decisions

def _iso(at: object) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(at))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo is not None else None


def follow_decision(e8_doc: Any, entry: dict[str, Any] | None, entry_why: str | None,
                    e8_lane: dict[str, Any] | None, lane_why: str, *, today: str,
                    now: datetime) -> tuple[str, dict[str, Any] | None, str]:
    """("follow", signal, why) when E8's gold_asia has a live filled leg today, else
    ("wait" | "stand_aside" | "unreadable", None, why). Pure.

    The signal is E8's filled leg: {"side", "price", "sl", "tp", "e8_position_id"}. Anything but
    "follow" means no new FTMO order, and any resting FTMO entry is cancelled."""
    if not isinstance(e8_doc, dict):
        return "unreadable", None, "E8's pass report (E8_GOLD.json) is absent or unreadable"
    at = _iso(e8_doc.get("at"))
    if at is None:
        return "unreadable", None, "E8's pass report carries no readable timestamp"
    age = (now - at).total_seconds()
    if not (-60.0 <= age <= E8_REPORT_MAX_AGE_S):
        return "unreadable", None, (f"E8's pass report is {age:.0f}s old (limit "
                                    f"{E8_REPORT_MAX_AGE_S:.0f}s); E8 is not running")
    if e8_doc.get("status") != "OK":
        return "unreadable", None, f"E8's last pass is {e8_doc.get('status')!r}, not OK"
    state = e8_doc.get("state")
    if not isinstance(state, dict) or not isinstance(state.get("windows"), dict):
        return "unreadable", None, "E8's pass report carries no window state (torn)"
    if str(state.get("date")) != str(today):
        return "unreadable", None, (f"E8's server day {state.get('date')!r} is not this "
                                    f"terminal's {today!r}")
    if entry_why is not None:
        return "unreadable", None, f"the gold direction state: {entry_why}"
    if e8_lane is None:
        return "unreadable", None, f"E8's published gold state: {lane_why}"
    gd = e8_doc.get("guard_decision")
    stood_down = bool(e8_doc.get("guard")) or (isinstance(gd, dict)
                                               and gd.get("may_open") is False)
    if stood_down:
        return "stand_aside", None, f"E8 stands down ({e8_doc.get('guard') or gd})"
    w = state["windows"].get(WINDOW)
    if not isinstance(w, dict):
        return "wait", None, "E8's gold_asia has not been placed today"
    if w.get("position_id") is None:
        return "wait", None, "E8's gold_asia has no filled leg yet"
    if entry is None or entry.get("first_fill_lane") != _oco.LEADER:
        return "wait", None, ("E8's asia fill has not set today's direction in the shared "
                              "direction state yet")
    side = _oco.side_of(entry.get("direction"))
    if side is None:
        return "unreadable", None, "the day's direction is unreadable"
    pid = str(w["position_id"])
    if not any(str(p.get("id")) == pid and _oco.side_of(p.get("side")) == side
               for p in e8_lane.get("positions") or []):
        return "stand_aside", None, (f"E8's asia position is no longer open on the {side} side; "
                                     f"nothing to follow")
    leg = (w.get("orders") or {}).get("buy_stop" if side == "long" else "sell_stop") or {}
    try:
        price, sl, tp = float(leg["price"]), float(leg["sl"]), float(leg["tp"])
    except (KeyError, TypeError, ValueError):
        return "unreadable", None, "E8's filled asia leg carries no readable price/stop/target"
    sign = 1.0 if side == "long" else -1.0
    if not (sign * (price - sl) > 0 and sign * (tp - price) > 0):
        return "unreadable", None, "E8's filled asia leg has its stop or target on the wrong side"
    return "follow", {"side": side, "price": price, "sl": sl, "tp": tp,
                      "e8_position_id": pid}, f"E8's gold_asia filled {side}"


def entry_order_kind(side: str, level: float, bid: float, ask: float) -> str:
    """The resting order that enters at `level`: a stop while the price is short of it, a limit
    once it is through (FTMO's entry is E8's level, never a chase)."""
    if side == "long":
        return "buy_stop" if ask < level else "buy_limit"
    return "sell_stop" if bid > level else "sell_limit"


def lot_for(frac: float, equity: float, dist: float, contract: float, *, vmin: float,
            vstep: float, vmax: float) -> float:
    """`frac` of equity at risk to the stop, floored to the volume step; 0 below the minimum."""
    if not (frac > 0 and equity > 0 and dist > 0 and contract > 0 and vstep > 0):
        return 0.0
    raw = frac * equity / (dist * contract)
    lot = int(raw / vstep + 1e-9) * vstep
    lot = min(lot, vmax) if vmax > 0 else lot
    return round(lot, 8) if lot >= vmin else 0.0


def trade_risk(lot: float, dist: float, contract: float) -> float:
    """Dollars at risk if the stop fills E8's measured slippage through its level."""
    return (float(dist) + SLIP_ALLOWANCE_PTS) * float(lot) * float(contract)


def loss_guard(initial: float, day_start_balance: float, equity: float,
               new_risk: float) -> tuple[bool, str]:
    """FTMO's 5% daily and 10% maximum loss: may `new_risk` be added now?"""
    daily = DAILY_LOSS_FRAC * initial
    today_loss = max(0.0, day_start_balance - equity)
    floor = initial * (1.0 - MAX_LOSS_FRAC)
    why = (f"today's loss {today_loss:,.2f} + this trade {new_risk:,.2f} (stop + "
           f"{SLIP_ALLOWANCE_PTS} pt slip) against the {DAILY_LOSS_FRAC:.0%} daily limit "
           f"{daily:,.2f}; equity {equity:,.2f} - risk against the {MAX_LOSS_FRAC:.0%} floor "
           f"{floor:,.2f}")
    if today_loss + new_risk >= daily:
        return False, f"daily loss: {why}"
    if equity - new_risk <= floor:
        return False, f"max loss: {why}"
    return True, why


def near_market_close(now: datetime, hours: float = GAP_GUARD_H) -> bool:
    """Within `hours` before gold's daily close (17:00 New York, Friday's being the weekend)."""
    from zoneinfo import ZoneInfo
    ny = now.astimezone(ZoneInfo("America/New_York"))
    close = ny.replace(hour=17, minute=0, second=0, microsecond=0)
    if close <= ny:
        close += timedelta(days=1)
    return (close - ny).total_seconds() <= hours * 3600.0


def cet_day(now: datetime) -> tuple[str, datetime]:
    """(FTMO's trading date, its midnight in UTC)."""
    from zoneinfo import ZoneInfo
    local = now.astimezone(ZoneInfo(DAY_TZ))
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return local.date().isoformat(), midnight.astimezone(UTC)


def day_start_balance(mt5: Any, balance: float, since: datetime, now: datetime) -> float:
    """The balance at FTMO's midnight: today's balance less every deal's result since then.
    RAISES when the deal history cannot be read (the guard then refuses)."""
    deals = mt5.history_deals_get(since, now + timedelta(minutes=5))
    if deals is None:
        raise ValueError("the deal history is unreadable")
    moved = 0.0
    for d in deals:
        for k in ("profit", "commission", "swap", "fee"):
            v = getattr(d, k, 0.0)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                moved += float(v)
    return float(balance) - moved


def mirrored_stop(e8_doc: dict[str, Any], e8_position_id: str, side: str,
                  current: float | None) -> float | None:
    """The tightest stop E8 has acknowledged for its asia position in its last pass, if it is
    tighter than `current`. Pure."""
    sign = 1.0 if side == "long" else -1.0
    best = current
    for a in e8_doc.get("actions") or []:
        if a.get("act") != "ratchet_stop" or not a.get("ok") or a.get("shadow"):
            continue
        if str(a.get("position_id")) != str(e8_position_id):
            continue
        try:
            stop = float(a["after"])
        except (KeyError, TypeError, ValueError):
            continue
        if best is None or sign * (stop - best) > 0:
            best = stop
    return best if best is not None and best != current else None


# ------------------------------------------------------------------ the account

def _canon(login: object) -> object:
    return _oco._canon_login(login)


def bound_account(mt5: Any) -> tuple[str | None, dict[str, Any], str]:
    """(keyed account key, the declaration, why). Key None -> the lane does nothing at all."""
    try:
        doc = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, {}, "data/FTMO_LIVE_ACCOUNT.json is absent: no account is declared"
    except (OSError, ValueError) as exc:
        return None, {}, f"data/FTMO_LIVE_ACCOUNT.json is unreadable ({type(exc).__name__})"
    if not isinstance(doc, dict) or any(doc.get(k) in (None, "") for k in
                                        ("login", "server", "trade_mode", "initial_balance")):
        return None, {}, ("data/FTMO_LIVE_ACCOUNT.json must carry login, server, trade_mode and "
                          "initial_balance")
    try:
        initial = float(doc["initial_balance"])
        want_mode = int(doc["trade_mode"])
    except (TypeError, ValueError):
        return None, {}, "data/FTMO_LIVE_ACCOUNT.json carries an unreadable trade_mode/balance"
    acc = mt5.account_info()
    if acc is None:
        return None, {}, "the FTMO terminal did not answer account_info"
    if _canon(getattr(acc, "login", None)) != _canon(doc["login"]) \
            or str(getattr(acc, "server", "")) != str(doc["server"]):
        return None, {}, ("the terminal is on another account than data/FTMO_LIVE_ACCOUNT.json "
                          "declares; nothing is done")
    if int(getattr(acc, "trade_mode", -1)) != want_mode:
        return None, {}, (f"the terminal's trade_mode {getattr(acc, 'trade_mode', None)!r} is not "
                          f"the declared {want_mode}; nothing is done")
    try:
        key = _oco.oco_account_key(getattr(acc, "login", None), getattr(acc, "server", None))
    except _oco.IdentityUnavailable as exc:
        return None, {}, f"gold OCO identity: {exc}"
    return key, {"initial_balance": initial, "trade_mode": want_mode}, "account bound"


# ------------------------------------------------------------------ the pass

def _read_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _side_of_type(t: int) -> str | None:
    return "long" if t in (0, 2, 4, 6) else "short" if t in (1, 3, 5, 7) else None


def _send(mt5: Any, st: dict[str, Any], req: dict[str, Any], *, cet: str,
          essential: bool = False) -> Any:
    """One trade request, counted against FTMO's daily request limit. RAISES past the budget."""
    used = int((st.setdefault("requests", {})).get(cet) or 0)
    cap = REQUEST_HARD_CAP if essential else REQUEST_BUDGET
    if used >= cap:
        raise RuntimeError(f"{used} trade requests today (cap {cap} under FTMO's 2,000)")
    st["requests"] = {cet: used + 1}
    return mt5.order_send(req)


def _skip(doc: dict[str, Any], st: dict[str, Any], reason: str, why: str, *, today: str,
          now: datetime, missed_usd: float | None = None, alert: bool = False) -> None:
    doc["skipped"].append({"reason": reason, "why": why})
    if alert:
        doc["alerts"].append(why)
    log(f"{'ALERT ' if alert else ''}[{WINDOW}] not placed ({reason}): {why}")
    seen = st.setdefault("logged", {})
    if seen.get(reason) != today:
        seen[reason] = today
        _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
                 "status": "RAIL_BLOCKED" if reason != "wait" else "SKIPPED", "rail": RAIL,
                 "reason": reason, "why": why,
                 "missed_growth_risk_usd": None if missed_usd is None else round(missed_usd, 2)})


def run(mt5: Any, *, armed: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """One pass against the FTMO terminal under `mt5` (already attached)."""
    from mt5desk import order_door as _door
    # ONE DOOR FOR MONEY: every order_send goes through the order door's ledger.
    mt5 = _door.guard(mt5, caller="ftmo_follower", log=log)
    now = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "armed": bool(armed),
                           "lane": LANE, "symbol": SYMBOL, "placed": [], "actions": [],
                           "skipped": [], "alerts": []}
    key, decl, why = bound_account(mt5)
    if key is None:
        doc.update({"status": "ACCOUNT_REFUSED", "why": why})
        log(f"account refused: {why}")
        _write_out(doc, None)
        return doc
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        doc["status"] = "NO_TICK"
        _write_out(doc, None)
        return doc
    today = _oco.trading_date(int(tick.time))
    srv = datetime.fromtimestamp(int(tick.time), tz=UTC)
    hour = srv.hour + srv.minute / 60.0
    cet, cet_midnight = cet_day(now)
    st = _read_json(STATE)
    st = st if isinstance(st, dict) else {}
    if st.get("date") != today:
        st = {"date": today, "windows": {}, "requests": st.get("requests") or {},
              "logged": {}}
    doc.update({"server_time": srv.isoformat(), "hour": round(hour, 3), "trading_date": today})

    # This account's gold state for every other lane, and the claim of any fill here.
    sync = _oco.sync_lane(LANE, key, lambda: _oco.mt5_gold_rows(mt5), date=today,
                          holder="ftmo_follower")
    doc["gold_oco"] = {"published": sync.get("published"), "why": sync.get("why")}

    e8_doc = _read_json(E8_REPORT)
    entry, entry_why = _oco.day_entry(today)
    e8_lane, lane_why = _oco.read_lane("e8")
    action, sig, fwhy = follow_decision(e8_doc, entry, entry_why, e8_lane, lane_why,
                                        today=today, now=now)
    doc["follow"] = {"action": action, "why": fwhy, "signal": sig}

    positions = mt5.positions_get(symbol=SYMBOL)
    orders = mt5.orders_get(symbol=SYMBOL)
    book_ok = positions is not None and orders is not None
    positions, orders = list(positions or []), list(orders or [])
    own_pos = [p for p in positions if int(getattr(p, "magic", 0) or 0) == MAGIC]
    own_ord = [o for o in orders if int(getattr(o, "magic", 0) or 0) == MAGIC]

    # ---------------------------------------------------------------- management (armed only)
    w = st["windows"].get(WINDOW) or {}
    end = window_end_hour(WINDOW)
    for o in own_ord:
        why_cancel = None
        if action != "follow":
            why_cancel = f"E8 shows no live filled asia trade now ({fwhy})"
        elif hour >= CANCEL_HOUR or (end is not None and hour >= end) or \
                hour - float(w.get("placed_hour") or hour) >= BRACKET_TTL_HOURS:
            why_cancel = "the asia window's session is over"
        elif sig is not None and _side_of_type(int(getattr(o, "type", -1))) != sig["side"]:
            why_cancel = "it is against E8's direction"
        if why_cancel is None:
            continue
        act: dict[str, Any] = {"act": "cancel", "order": int(o.ticket), "why": why_cancel,
                               "ok": False}
        if armed:
            try:
                res = _send(mt5, st, {"action": mt5.TRADE_ACTION_REMOVE, "order": int(o.ticket),
                                      "magic": MAGIC, "comment": COMMENT}, cet=cet,
                            essential=True)
                act["ok"] = getattr(res, "retcode", None) in (10008, 10009)
            except Exception as exc:
                act["why"] += f"; FAILED {type(exc).__name__}: {exc}"[:160]
        else:
            act["shadow"] = True
        log(f"[{WINDOW}] cancel resting order {o.ticket}: {act['why']} -> {act.get('ok')}")
        doc["actions"].append(act)
    for p in own_pos:
        side = "long" if int(getattr(p, "type", -1)) == 0 else "short"
        if hour >= CLOSE_HOUR:
            act = {"act": "close", "position": int(p.ticket), "ok": False,
                   "why": "the gold book's close hour"}
            if armed:
                tk = mt5.symbol_info_tick(SYMBOL)
                try:
                    res = _send(mt5, st, {
                        "action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL,
                        "volume": float(p.volume), "position": int(p.ticket),
                        "type": mt5.ORDER_TYPE_SELL if side == "long" else mt5.ORDER_TYPE_BUY,
                        "price": float(tk.bid if side == "long" else tk.ask),
                        "deviation": 20, "magic": MAGIC, "comment": COMMENT,
                        "type_filling": mt5.ORDER_FILLING_IOC}, cet=cet, essential=True)
                    act["ok"] = getattr(res, "retcode", None) in (10008, 10009)
                except Exception as exc:
                    act["why"] += f"; FAILED {type(exc).__name__}: {exc}"[:160]
            else:
                act["shadow"] = True
            doc["actions"].append(act)
            continue
        e8_pid = (sig or {}).get("e8_position_id") or w.get("e8_position_id")
        if not isinstance(e8_doc, dict) or not e8_pid:
            continue
        cur = float(getattr(p, "sl", 0.0) or 0.0) or None
        new = mirrored_stop(e8_doc, str(e8_pid), side, cur)
        if new is None or cur is None:
            continue
        sgn: Any = 1 if side == "long" else -1
        rests, rwhy = _pm.stop_rests_at_venue(stop=new, side=sgn, bid=float(tick.bid),
                                              ask=float(tick.ask))
        act = {"act": "ratchet_stop", "position": int(p.ticket), "before": cur, "after": new,
               "ok": False}
        if not rests:
            act["why"] = rwhy
        elif armed:
            try:
                res = _send(mt5, st, {"action": mt5.TRADE_ACTION_SLTP, "symbol": SYMBOL,
                                      "position": int(p.ticket), "sl": new,
                                      "tp": float(getattr(p, "tp", 0.0) or 0.0),
                                      "magic": MAGIC}, cet=cet)
                act["ok"] = getattr(res, "retcode", None) in (10008, 10009)
            except Exception as exc:
                act["why"] = f"{type(exc).__name__}: {exc}"[:160]
        else:
            act["shadow"] = True
        doc["actions"].append(act)

    # ---------------------------------------------------------------- the one order
    placed_today = WINDOW in st["windows"]
    if placed_today or own_ord or own_pos:
        pass
    elif action != "follow" or sig is None:
        _skip(doc, st, "wait" if action == "wait" else action, fwhy, today=today, now=now)
    else:
        _place(mt5, st, doc, sig, key=key, decl=decl, armed=armed, today=today, now=now,
               hour=hour, cet=cet, cet_midnight=cet_midnight, book_ok=book_ok,
               positions=positions, orders=orders, tick=tick, e8_doc=e8_doc)
    doc.setdefault("status", "OK")
    _write_out(doc, st)
    return doc


def _place(mt5: Any, st: dict[str, Any], doc: dict[str, Any], sig: dict[str, Any], *,
           key: str,
           decl: dict[str, Any], armed: bool, today: str, now: datetime, hour: float, cet: str,
           cet_midnight: datetime, book_ok: bool, positions: list[Any], orders: list[Any],
           tick: Any,
           e8_doc: Any) -> None:
    side = sig["side"]
    if not book_ok:
        _skip(doc, st, "book_unreadable", "the FTMO terminal did not answer positions/orders",
              today=today, now=now)
        return
    # NEVER THE OPPOSITE SIDE: any gold position or order the other way, from ANY source.
    against = [int(getattr(x, "ticket", 0) or 0) for x in [*positions, *orders]
               if _side_of_type(int(getattr(x, "type", -1))) not in (None, side)]
    if against:
        _skip(doc, st, "opposite_exposure", (f"FTMO holds or rests gold against E8's {side} "
                                             f"({against}); this lane never opens the other way"),
              today=today, now=now, alert=True)
        return
    end = window_end_hour(WINDOW)
    if hour >= CANCEL_HOUR or (end is not None and hour >= end):
        _skip(doc, st, "session_over", "the asia window's session is over", today=today, now=now)
        return
    if near_market_close(now):
        _skip(doc, st, "gap_guard", f"within {GAP_GUARD_H:g}h of gold's market close (FTMO: no "
                                    f"gap trading)", today=today, now=now)
        return
    v = _oco.gate(LANE, side, key=key, date=today)
    if not v.allowed:
        _skip(doc, st, "gold_oco", v.why, today=today, now=now)
        return
    book = load_cert_book(CERT_BOOK_FILE, "ftmo")
    frac = (book or {}).get(CERT_KEY)
    if not frac or not frac > 0:
        _skip(doc, st, "cert_void", ("the ftmo block of CERT_BOOK_LIVE.json is absent, disabled, "
                                     "void or funds gold_asia at 0"), today=today, now=now)
        return
    acc = mt5.account_info()
    info = mt5.symbol_info(SYMBOL)
    try:
        equity, balance = float(acc.equity), float(acc.balance)
        contract = float(info.trade_contract_size)
        vmin, vstep = float(info.volume_min), float(info.volume_step)
        vmax = float(getattr(info, "volume_max", 0.0) or 0.0)
    except (AttributeError, TypeError, ValueError):
        _skip(doc, st, "account_unreadable", "equity, balance or the contract is unreadable",
              today=today, now=now)
        return
    dist = abs(float(sig["price"]) - float(sig["sl"]))
    want_usd = float(frac) * equity
    lot = lot_for(float(frac), equity, dist, contract, vmin=vmin, vstep=vstep, vmax=vmax)
    if not lot > 0:
        _skip(doc, st, "unsizeable", f"{frac:.4f} of equity at a {dist:.2f} stop is below the "
                                     f"minimum lot", today=today, now=now, missed_usd=want_usd)
        return
    risk = trade_risk(lot, dist, contract)
    try:
        start = day_start_balance(mt5, balance, cet_midnight, now)
    except Exception as exc:
        _skip(doc, st, "loss_guard", f"today's starting balance is unmeasurable ({exc})",
              today=today, now=now, missed_usd=want_usd)
        return
    ok, gwhy = loss_guard(float(decl["initial_balance"]), start, equity, risk)
    doc["loss_guard"] = gwhy
    if not ok:
        _skip(doc, st, "loss_guard", gwhy, today=today, now=now, missed_usd=want_usd)
        return
    kind = entry_order_kind(side, float(sig["price"]), float(tick.bid), float(tick.ask))
    row = {"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
           "side": side, "kind": kind, "price": sig["price"], "sl": sig["sl"], "tp": sig["tp"],
           "lot": lot, "risk_frac": frac, "risk_usd_with_slip": round(risk, 2),
           "e8_position_id": sig["e8_position_id"], "armed": bool(armed)}
    if not armed:
        row["status"] = "WOULD_PLACE"
        _record(row)
        doc["placed"].append({**row, "shadow": True})
        log(f"[{WINDOW}] STANDBY would place {kind} {lot} {SYMBOL} @ {sig['price']:.2f} sl "
            f"{sig['sl']:.2f} tp {sig['tp']:.2f}")
        return
    types = {"buy_stop": mt5.ORDER_TYPE_BUY_STOP, "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
             "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT, "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT}
    req = {"action": mt5.TRADE_ACTION_PENDING, "symbol": SYMBOL, "volume": lot,
           "type": types[kind], "price": float(sig["price"]), "sl": float(sig["sl"]),
           "tp": float(sig["tp"]), "deviation": 20, "magic": MAGIC, "comment": COMMENT,
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_RETURN}
    try:
        res = _send(mt5, st, req, cet=cet)
    except Exception as exc:
        row.update({"status": "REJECTED", "why": f"{type(exc).__name__}: {exc}"[:200]})
        _record(row)
        log(f"[{WINDOW}] REJECTED: {row['why']}")
        return
    code = getattr(res, "retcode", None)
    row.update({"status": "SENT" if code in (10008, 10009) else "REJECTED", "retcode": code,
                "order_id": getattr(res, "order", None)})
    _record(row)
    # ONE ORDER A DAY: the window is spent once a send was attempted, whatever the venue said.
    st["windows"][WINDOW] = {"placed_at": row["at"], "placed_hour": hour, "side": side,
                             "kind": kind, "order_id": row["order_id"], "lot": lot,
                             "e8_position_id": sig["e8_position_id"], "status": row["status"]}
    doc["placed"].append(row)
    log(f"[{WINDOW}] {row['status']} {kind} {lot} {SYMBOL} @ {sig['price']:.2f} -> {code}")


def _write_out(doc: dict[str, Any], st: dict[str, Any] | None) -> None:
    try:
        if st is not None:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(st, indent=1, default=str), encoding="utf-8")
            doc["state"] = st
        OUT.parent.mkdir(parents=True, exist_ok=True)
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, OUT)
    except OSError as exc:
        log(f"state/report write failed: {exc}")


# ------------------------------------------------------------------ entrypoint

def interactive_session() -> tuple[bool, str]:
    """MetaTrader5 attaches to a running terminal only from the desktop session that runs it."""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT"):
        return False, "an SSH session cannot attach to the FTMO terminal"
    if os.name != "nt":
        return False, "not the Windows trading box"
    try:
        import ctypes
        sid = ctypes.c_ulong(0)
        ok = ctypes.windll.kernel32.ProcessIdToSessionId(  # type: ignore[attr-defined]
            os.getpid(), ctypes.byref(sid))
    except Exception as exc:
        return False, f"the session id is unreadable ({type(exc).__name__})"
    if not ok or sid.value == 0:
        return False, "session 0 is a service session; the FTMO terminal is not attachable"
    return True, "interactive session"


def main(argv: list[str] | None = None) -> int:
    del argv
    ok, why = interactive_session()
    if not ok:
        log(f"not run: {why}")
        return 1
    armed = ARMED_MARKER.exists()
    try:
        import MetaTrader5 as mt5
        path = os.environ.get(TERMINAL_ENV) or TERMINAL_PATH
        # Attach to the RUNNING FTMO terminal by path: no login or password is ever passed.
        if not mt5.initialize(path=path, timeout=15000):
            log(f"FTMO terminal unavailable: {mt5.last_error()}")
            return 1
    except Exception as exc:
        log(f"MetaTrader5 unavailable ({type(exc).__name__}: {exc})")
        return 1
    try:
        doc = run(mt5, armed=armed)
    finally:
        mt5.shutdown()
    log(f"ftmo follower: {'ARMED' if armed else 'STANDBY'} status={doc.get('status')} "
        f"follow={(doc.get('follow') or {}).get('action')} placed={len(doc['placed'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
