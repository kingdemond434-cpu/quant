"""FTMO SLEEVE EXECUTOR -- every non-gold sleeve the FTMO allocator sizes: signal -> size -> send.

WHY (coordinator 2026-10-29, on zuck's standing order to keep the FTMO allocator improving for pass
speed x pass probability). The allocator (research/prop_challenge_allocator.py) sizes every Tier S
certificate FTMO lists, but until this file only the gold copy had an executor, so every other
sized sleeve was published SIZED_NO_EXECUTOR and its J was missed growth. This is that executor.

WHAT IT TRADES. The keys the allocator laid into the `ftmo` block of data/CERT_BOOK_LIVE.json with
a positive fraction AND a certificate spec in reports/FTMO_ALLOCATOR.json `specs` -- both, or
nothing. Gold is never traded here (the follower is gold's one FTMO owner). FAIL CLOSED, ALWAYS A
ZERO: an allocator report that is absent, stale (`ALLOC_MAX_AGE_S`), not deployable, or a block
that load_cert_book voids, trades nothing new; open positions are still managed.

THE ORDER OF OPERATIONS IS THE RISK CONTROL (the E8 executor's, on the FTMO terminal):
  1. THE ACCOUNT. The terminal must be the account data/FTMO_LIVE_ACCOUNT.json declares
     (`ftmo_follower.bound_account`), or the lane does nothing at all.
  2. MANAGEMENT FIRST. Every position this lane opened (MAGIC) is closed when its certified time
     exit passes, or at once when the Fusion or E8 book shows the opposite side of its symbol. The
     FTMO book is then PUBLISHED (data/xacct/ftmo_book.json, every pass, under the lock): the
     gateway and the E8 executor refuse the opposite side of it (`cross_account.ftmo_block`).
  3. THE CLOCK. MT5 bars carry the server's wall clock; the certificates were judged on the
     broker clock (NY+7). The FTMO server's offset is measured off its own tick every pass and
     must equal that clock, or no signal is read (CLOCK_MISMATCH).
  4. ONE PASS PER SLEEVE, on the LAST CLOSED BAR, through the same reconstruction the E8 lane
     uses (`e8_executor._call_params`, the family, `certified_session_filter`, `family_bracket`),
     behind the same doors: banned family, principal exclusion, replication, the Tier S door.
  5. SIZE from the allocator's fraction of equity and the signal's own stop, in account currency
     (`order_calc_profit`), never a fixed lot; the follower's notional lot cap applies.
  6. FTMO'S RAILS ON THE WHOLE BOOK: the daily loss limit of the declared type (5% / 3%) from the
     CET-midnight balance and the 10% maximum loss, tested with every open position's and resting
     order's stop risk, this pass's committed risk and the new trade's (stop one spread wide). A
     position or order without a stop makes the book's risk unmeasurable and refuses new risk.
  7. THE OPPOSITE-SIDE FENCE, UNDER THE PLACEMENT LOCK: refused when the Fusion book or the E8
     book (`cross_account.read_book`, absent/stale -> refused) or this FTMO account itself holds
     or rests the other side of the symbol. Read and send run under the one lock every lane takes.
     A SAME-side holding on Fusion or E8 is sent: zuck extended the copy override to every sleeve
     (2026-10-29 15:27Z, `ALLOW_CROSS_FIRM_COPY`).
  8. SEND WITH THE STOP AND TARGET ATTACHED, once per (sleeve, bar): the state is marked and
     written atomically BEFORE the send, and this lane's MAGIC history on the symbol since the bar
     opened is checked too, so a torn state file can never send twice.

EVERY SLEEVE LEAVES A ROW. data/ftmo_exec_intents.jsonl gets one row per sleeve considered with its
status; every refusal by a rail is RAIL_BLOCKED with its rail and the risk it held back
(`missed_growth_risk_usd`) -- the missed-trade log. reports/FTMO_EXEC.json is the pass.

ARMING. Standby unless data/FTMO_EXECUTOR_ARMED exists: an unarmed pass does everything except
send, and logs WOULD_SEND. The allocator's own arm file (FTMO_ALLOCATOR_ARMED) decides whether the
book it reads is written at all.

SESSION. Like the follower, it attaches to the running FTMO terminal by path, which works only in
the interactive desktop session. Task `MT5-FTMO-Executor` (scripts/install_ftmo_executor_task.ps1)
runs it every 5 minutes.

    python prop/ftmo_executor.py           one pass, standby unless armed
"""
from __future__ import annotations

import contextlib
import json
import math
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prop import ftmo_follower as _fw  # noqa: E402

LANE = "ftmo"
TAG = "FX"
#: Distinct from the follower's 341955: each lane manages only what it opened.
MAGIC = 341956
ARMED_MARKER = DESK / "data" / "FTMO_EXECUTOR_ARMED"
ALLOCATOR = DESK / "reports" / "FTMO_ALLOCATOR.json"
STATE = DESK / "data" / "ftmo_executor_state.json"
OUT = DESK / "reports" / "FTMO_EXEC.json"
INTENTS = DESK / "data" / "ftmo_exec_intents.jsonl"
LOG = DESK / "logs" / "ftmo_executor.log"
#: The allocator runs hourly; a report older than this is not today's book.
ALLOC_MAX_AGE_S = 3 * 3600
#: Gold has one FTMO owner, the follower.
SKIP_SYMBOLS = frozenset({"XAUUSD"})
#: Hourly bars fetched per sleeve: the E8 executor's lookback.
LOOKBACK_BARS = 900
MIN_BARS = 60
#: FTMO allows 2,000 server requests a day across the account. The follower budgets 1,500 for
#: new risk; this lane's own counts are far below: new risk stops at REQUEST_BUDGET, closes at
#: REQUEST_HARD_CAP.
REQUEST_BUDGET = 200
#: Closes are never held back by this lane's own budget, only by FTMO's 2,000 (audit S3).
REQUEST_HARD_CAP = 1950
#: The reference tick (EURUSD) may trail the symbol's own forming bar by this much.
STALE_GRACE_S = 60.0
KEEP_TRADED = 400
TF_HOURS = {"M1": 1 / 60, "M5": 5 / 60, "M15": 0.25, "M30": 0.5, "H1": 1.0, "H4": 4.0,
            "D1": 24.0}
#: 10010 is a partial fill: a live position, counted as sent (audit MF3).
OK_CODES = (10008, 10009, 10010)
#: PRINCIPAL OVERRIDE (zuck 2026-10-29 15:27:18Z, "extend copy override to all"): FTMO bans
#: copied or coordinated trades across firms; zuck extended his gold copy consent to every sleeve.
#: A sleeve the Fusion or E8 book holds on the SAME side is therefore sent. The OPPOSITE-side
#: fence is not part of the override and always applies. False restores the same-side refusal
#: (`cross_firm_copy`), the revert path, without touching anything else.
ALLOW_CROSS_FIRM_COPY = True
#: The order comment carries the certified hold, so the time exit is read off the position
#: itself and survives a lost state file, a crash after the send or a partial fill (audit MF3).
_COMMENT_RE = re.compile(r"^FX(\d+)(M1|M5|M15|M30|H1|H4|D1)\|")


def log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}\n")
    except OSError:
        pass


def _record(row: dict[str, Any], now: datetime, armed: bool) -> None:
    try:
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": now.isoformat(timespec="seconds"), "lane": LANE,
                                 "armed": armed, **row}, default=str) + "\n")
    except OSError as exc:
        log(f"intent row not written ({exc})")


#: The gold copy's keys in the ftmo block: the follower trades them, never this lane.
_FOLLOWER_KEYS = frozenset({"gold_asia"})
#: The rail a whole pass's veto is journalled under (audit SF3: Rule 1 needs a line for it).
PASS_RAIL = "ftmo_executor_pass"


def _veto(doc: dict[str, Any], now: datetime, armed: bool,
          sleeves: list[str] | None = None) -> None:
    """One intent row for a pass that traded nothing new as a whole (account, snapshot, clock,
    book): unpriced, so the bill counts it without inventing a dollar figure."""
    _record({"status": doc.get("status"), "rail": PASS_RAIL, "why": doc.get("why"),
             "sleeve": ",".join(sleeves or []) or None}, now, armed)


# ------------------------------------------------------------------ pure helpers

def book_sleeves(alloc: Any, cert: dict[str, float] | None, now: datetime
                 ) -> tuple[list[tuple[str, float, dict[str, Any]]], str]:
    """([(key, equity fraction, spec)], why). Empty with the reason unless the allocator's report
    is fresh and deployable and the `ftmo` block funds the key. Pure."""
    if not isinstance(alloc, dict):
        return [], "reports/FTMO_ALLOCATOR.json is absent or unreadable"
    try:
        at = datetime.fromisoformat(str(alloc["generated_at"]))
        if at.tzinfo is None:
            raise ValueError("naive timestamp")
        age = (now - at).total_seconds()
    except (KeyError, TypeError, ValueError) as exc:
        return [], f"the allocator report has no readable generated_at ({exc})"
    if not -60.0 <= age <= ALLOC_MAX_AGE_S:
        return [], f"the allocator report is {age:.0f}s old (limit {ALLOC_MAX_AGE_S}s)"
    if alloc.get("deployable") is not True:
        return [], f"the allocator report is not deployable ({alloc.get('status')})"
    if not cert:
        return [], "the ftmo block of CERT_BOOK_LIVE.json is absent, disabled or void"
    raw = alloc.get("specs")
    specs: dict[str, Any] = raw if isinstance(raw, dict) else {}
    raw_x = alloc.get("executable")
    solved: dict[str, Any] = raw_x if isinstance(raw_x, dict) else {}
    out = []
    for key, frac in sorted(cert.items()):
        spec = specs.get(key)
        # THE SMALLER OF THE BLOCK AND THIS PASS'S SOLVE (audit MF1): a deployable report is not
        # an applied one (unarmed, or apply_book refused), so a stale block never outsizes it.
        got = solved.get(key)
        if not isinstance(got, (int, float)) or isinstance(got, bool) \
                or not math.isfinite(float(got)) or not math.isfinite(float(frac)):
            continue                                 # a NaN never reads as "no limit" (min)
        frac = min(float(frac), float(got))
        if not (frac > 0) or not isinstance(spec, dict):
            continue
        if str(spec.get("symbol") or "").upper() in SKIP_SYMBOLS:
            continue
        out.append((key, frac, spec))
    return out, f"{len(out)} funded non-gold sleeve(s) with a spec"


def comment_for(col: str, ttl_bars: object, tf: str) -> str:
    """The order comment: the certified hold and the chart, then the sleeve (MT5 keeps 31)."""
    ttl = int(ttl_bars) if isinstance(ttl_bars, (int, float)) and ttl_bars > 0 else 0
    return f"FX{ttl}{tf}|{col}"[:31]


def exit_epoch(position: Any) -> float | None:
    """When this lane's position reaches its certified time exit (server clock), read off the
    position's own open time and comment. None: no time exit (stop and target only)."""
    m = _COMMENT_RE.match(str(getattr(position, "comment", "") or ""))
    opened = getattr(position, "time", None)
    if m is None or not isinstance(opened, (int, float)) or isinstance(opened, bool):
        return None
    ttl = int(m.group(1))
    return float(opened) + ttl * TF_HOURS[m.group(2)] * 3600 if ttl > 0 else None


def clock_ok(tick_epoch: float, now: datetime) -> tuple[bool, str]:
    """Is the FTMO server on the certificates' broker clock (NY+7)? Its offset is read off its
    own tick: MT5 stamps server wall time as if it were UTC."""
    from prop.e8_guard import server_offset_hours
    want = server_offset_hours(now)
    try:
        got = _fw.server_offset_from_tick(float(tick_epoch), now)
    except ValueError as exc:
        return False, f"the FTMO server clock is unreadable: {exc}"
    if got != want:
        return False, (f"the FTMO server runs at UTC{got:+d}, the certificates' broker clock at "
                       f"UTC{want:+d}: an hour-branching family would read the wrong bars")
    return True, f"server UTC{got:+d} = broker clock"


def lot_for_loss(frac: float, equity: float, loss_per_lot: float, *, vmin: float, vstep: float,
                 vmax: float) -> float:
    """`frac` of equity lost at the stop, floored to the volume step; 0 below the minimum."""
    if not (frac > 0 and equity > 0 and loss_per_lot > 0 and vstep > 0):
        return 0.0
    lot = int(frac * equity / loss_per_lot / vstep + 1e-9) * vstep
    lot = min(lot, vmax) if vmax > 0 else lot
    return round(lot, 8) if lot >= vmin else 0.0


def filling_mode(mt5: Any, info: Any) -> int:
    """The fill policy the symbol allows (bit 1 FOK, bit 2 IOC), else RETURN."""
    fm = int(getattr(info, "filling_mode", 0) or 0)
    if fm & 1:
        return int(mt5.ORDER_FILLING_FOK)
    if fm & 2:
        return int(mt5.ORDER_FILLING_IOC)
    return int(mt5.ORDER_FILLING_RETURN)


# ------------------------------------------------------------------ venue reads

def frame(mt5: Any, sym: str, tf: str) -> Any:
    """The terminal's bars on the sleeve's own chart, server-clock indexed, or None."""
    import pandas as pd
    code = getattr(mt5, f"TIMEFRAME_{tf}", None) if tf in TF_HOURS else None
    if code is None:
        return None
    rates = mt5.copy_rates_from_pos(sym, code, 0, LOOKBACK_BARS)
    if rates is None or len(rates) == 0:
        return None
    df = pd.DataFrame(rates)
    df.index = pd.to_datetime(df["time"], unit="s", utc=True)
    df.index.name = "time"
    df = df.drop(columns=["time"])
    df.attrs["strategy_clock"] = "broker_wall_time/FTMO_server"
    return df.sort_index()


def loss_per_lot(mt5: Any, sym: str, side: str, entry: float, stop: float) -> float | None:
    """Account-currency loss of one lot from `entry` to `stop`, the terminal's own arithmetic."""
    typ = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
    try:
        p = mt5.order_calc_profit(typ, sym, 1.0, float(entry), float(stop))
    except Exception:
        return None
    if not isinstance(p, (int, float)) or isinstance(p, bool) or not math.isfinite(p):
        return None
    return -float(p) if p < 0 else None


def book_stop_risk(mt5: Any, positions: list[Any], orders: list[Any]) -> tuple[float | None, str]:
    """Account-currency loss if every open position and resting entry hits its stop. None when
    any of them has no stop or cannot be priced: the book's risk is then unknown."""
    total = 0.0
    for kind, rows in (("position", positions), ("order", orders)):
        for x in rows:
            sl = float(getattr(x, "sl", 0.0) or 0.0)
            if sl <= 0:
                return None, f"{kind} {getattr(x, 'ticket', '?')} on {x.symbol} carries no stop"
            t = int(getattr(x, "type", -1))
            side = "buy" if t in (0, 2, 4, 6) else "sell" if t in (1, 3, 5, 7) else None
            vol = float(getattr(x, "volume", None) or getattr(x, "volume_current", 0.0) or 0.0)
            if side is None or vol <= 0:
                return None, f"{kind} {getattr(x, 'ticket', '?')} is unreadable"
            lpl = loss_per_lot(mt5, x.symbol, side, float(x.price_open), sl)
            # a stop already past the entry (locked profit) risks nothing; None from a
            # profitable stop is that case, an unpriceable one is caught by the probe below
            if lpl is None:
                probe = mt5.order_calc_profit(
                    mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL, x.symbol,
                    1.0, float(x.price_open), sl)
                if not isinstance(probe, (int, float)) or isinstance(probe, bool):
                    return None, f"{kind} {getattr(x, 'ticket', '?')} cannot be priced"
                continue
            total += lpl * vol
    return total, f"{len(positions)} position(s), {len(orders)} order(s) to their stops"


def history_since(mt5: Any, sym: str, since_epoch: float, now: datetime) -> bool | None:
    """Has this lane (MAGIC) any order or deal on `sym` stamped at or after `since_epoch`
    (server clock)? None when the history cannot be read."""
    a, b = now - timedelta(days=3), now + timedelta(days=1)
    orders, deals = mt5.history_orders_get(a, b), mt5.history_deals_get(a, b)
    if orders is None or deals is None:
        return None
    for rows, field in ((orders, "time_setup"), (deals, "time")):
        for r in rows:
            if int(getattr(r, "magic", 0) or 0) != MAGIC:
                continue
            if str(getattr(r, "symbol", "")).upper() != sym.upper():
                continue
            ts = getattr(r, field, None)
            if not isinstance(ts, (int, float)) or ts >= since_epoch:
                return True
    return False


def _side_of(t: int) -> str | None:
    return "buy" if t in (0, 2, 4, 6) else "sell" if t in (1, 3, 5, 7) else None


# ------------------------------------------------------------------ the pass

def _reserve(st: dict[str, Any], cet: str, *, essential: bool = False) -> None:
    """Count one trade request against today's cap, or RAISE at the cap."""
    used = int((st.setdefault("requests", {})).get(cet) or 0)
    cap = REQUEST_HARD_CAP if essential else REQUEST_BUDGET
    if used >= cap:
        raise RuntimeError(f"{used} trade requests today (this lane's cap {cap})")
    st["requests"] = {cet: used + 1}


def _send(mt5: Any, st: dict[str, Any], req: dict[str, Any], *, cet: str,
          essential: bool = False) -> Any:
    _reserve(st, cet, essential=essential)
    return mt5.order_send(req)


def _close(mt5: Any, st: dict[str, Any], p: Any, *, cet: str, armed: bool, why: str
           ) -> dict[str, Any]:
    side = _side_of(int(getattr(p, "type", -1)))
    act: dict[str, Any] = {"act": "close", "position": int(p.ticket), "symbol": p.symbol,
                           "why": why, "ok": False}
    if not armed:
        act["shadow"] = True
        return act
    try:
        tk = mt5.symbol_info_tick(p.symbol)
        info = mt5.symbol_info(p.symbol)
        res = _send(mt5, st, {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": float(p.volume),
            "position": int(p.ticket),
            "type": mt5.ORDER_TYPE_SELL if side == "buy" else mt5.ORDER_TYPE_BUY,
            "price": float(tk.bid if side == "buy" else tk.ask), "deviation": 20,
            "magic": MAGIC, "comment": str(getattr(p, "comment", "") or TAG)[:31],
            "type_filling": filling_mode(mt5, info)}, cet=cet, essential=True)
        act["ok"] = getattr(res, "retcode", None) in OK_CODES
        act["retcode"] = getattr(res, "retcode", None)
    except Exception as exc:
        act["why"] += f"; FAILED {type(exc).__name__}: {exc}"[:200]
    return act


def manage(mt5: Any, st: dict[str, Any], doc: dict[str, Any], own: list[Any], *, cet: str,
           armed: bool, now: datetime, server_epoch: float) -> None:
    """Time exits and the both-ways opposite rule for this lane's open positions."""
    from mt5desk import cross_account as _xa
    books = {a: _xa.read_book(a, now=now) for a in ("fusion", "e8")}
    for p in own:
        side = _side_of(int(getattr(p, "type", -1)))
        why = None
        for acct, (book, bwhy) in books.items():
            if book is None:
                doc.setdefault("manage_unmeasured", []).append(
                    f"{p.symbol}: the {acct} book is unreadable ({bwhy})")
                continue
            if _xa.opposite_block(book, p.symbol, side, account=acct) is not None:
                why = f"the {acct} account now holds the opposite side of {p.symbol}"
        due = exit_epoch(p)
        if due is None:
            # THE HOLD KEPT AT THE SEND (audit 2026-10-29): a broker that rewrote or cut the
            # comment leaves the exit in the state, by ticket.
            hold = (st.get("holds") or {}).get(str(int(p.ticket)))
            if isinstance(hold, dict) and isinstance(hold.get("exit"), (int, float)):
                due = float(hold["exit"])
        cm = _COMMENT_RE.match(str(getattr(p, "comment", "") or ""))
        if due is None and cm is not None and cm.group(1) == "0":
            # FX0: certified with no time exit at all; recorded, so it is not taken for a
            # position this lane never looked at
            doc.setdefault("manage_stop_target_only", []).append(f"{p.symbol} #{p.ticket}")
        elif due is None or not server_epoch:
            # NEVER SILENT: a position whose time exit cannot be read, or a pass with no server
            # clock, is reported and paged every pass it lasts; its stop and target still stand.
            what = ("no server clock this pass" if due is not None
                    else f"no readable time exit (comment {getattr(p, 'comment', None)!r}, "
                         f"no hold kept for ticket {p.ticket})")
            doc.setdefault("manage_unmeasured", []).append(f"{p.symbol} #{p.ticket}: {what}")
            doc["alerts"].append(f"FTMO {p.symbol} #{p.ticket}: time exit unmanaged ({what})")
        elif why is None and server_epoch >= due:
            why = "the certified time exit has passed"
        if why is None:
            continue
        act = _close(mt5, st, p, cet=cet, armed=armed, why=why)
        if "opposite" in why:
            doc["alerts"].append(f"FTMO {p.symbol} {side} closed: {why}")
        doc["actions"].append(act)
        _record({"status": "CLOSE", **act}, now, armed)


def run(mt5: Any, *, armed: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """One pass against the FTMO terminal under `mt5` (already attached)."""
    from mt5desk import order_door as _door
    mt5 = _door.guard(mt5, caller="ftmo_executor", log=log)
    now = now or datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "armed": bool(armed),
                           "lane": LANE, "sleeves": [], "actions": [], "alerts": []}
    key, decl, why = _fw.bound_account(mt5)
    if key is None:
        doc.update(status="ACCOUNT_REFUSED", why=why)
        _veto(doc, now, armed)
        _write_out(doc, None)
        return doc
    st = _fw._read_json(STATE)
    st = st if isinstance(st, dict) else {}
    st.setdefault("traded", {})
    cet, cet_midnight = _fw.cet_day(now)
    positions, orders = mt5.positions_get(), mt5.orders_get()
    if positions is None or orders is None:
        doc.update(status="NO_BROKER_SNAPSHOT", why="the terminal did not answer positions/orders")
        _veto(doc, now, armed)
        _write_out(doc, st)
        return doc
    positions, orders = list(positions), list(orders)
    own = [p for p in positions if int(getattr(p, "magic", 0) or 0) == MAGIC]
    ref = mt5.symbol_info_tick("EURUSD")
    server_epoch = float(getattr(ref, "time", 0) or 0) if ref is not None else 0.0
    try:
        manage(mt5, st, doc, own, cet=cet, armed=armed, now=now, server_epoch=server_epoch)
    except Exception as exc:                        # management never takes the pass down
        doc["manage_error"] = f"{type(exc).__name__}: {exc}"[:200]
    # THE FTMO BOOK, FOR THE OTHER LANES' FENCE (zuck 2026-10-29: no account opposite another).
    # Published every pass, armed or not, from a reading taken under the lock; a failure is
    # recorded and the readers fail closed on its age while this lane is armed.
    from mt5desk import cross_account as _xa
    doc["book_published"] = _xa.publish_under_lock(
        lambda: _xa.publish_mt5(mt5, source="ftmo_executor", account="ftmo"),
        holder="ftmo_executor:pass") or "ok"

    from mt5desk.kelly_sizing import CERT_BOOK_FILE, load_cert_book
    cert = load_cert_book(CERT_BOOK_FILE, "ftmo")
    sleeves, bwhy = book_sleeves(_fw._read_json(ALLOCATOR), cert, now)
    doc["book"] = {"why": bwhy, "keys": [k for k, _, _ in sleeves]}
    if not sleeves:
        doc.update(status="NO_BOOK", why=bwhy)
        # billed only when the block funds a non-gold key it could not trade: an empty block is
        # the allocator's own zero, not a veto here
        funded = sorted(k for k, v in (cert or {}).items()
                        if isinstance(v, (int, float)) and v > 0 and k not in _FOLLOWER_KEYS)
        if funded:
            _veto(doc, now, armed, sleeves=funded)
        _write_out(doc, st)
        return doc
    if not server_epoch:
        doc.update(status="NO_TICK", why="no EURUSD tick to read the server clock from")
        _veto(doc, now, armed, sleeves=[k for k, _, _ in sleeves])
        _write_out(doc, st)
        return doc
    ok, cwhy = clock_ok(server_epoch, now)
    doc["clock"] = cwhy
    if not ok:
        doc.update(status="CLOCK_MISMATCH", why=cwhy)
        _veto(doc, now, armed, sleeves=[k for k, _, _ in sleeves])
        _write_out(doc, st)
        return doc
    _entries(mt5, st, doc, sleeves, decl=decl, armed=armed, now=now, cet=cet,
             cet_midnight=cet_midnight, positions=positions, orders=orders,
             server_epoch=server_epoch)
    doc.setdefault("status", "OK")
    _write_out(doc, st)
    return doc


def _entries(mt5: Any, st: dict[str, Any], doc: dict[str, Any],
             sleeves: list[tuple[str, float, dict[str, Any]]], *, decl: dict[str, Any],
             armed: bool, now: datetime, cet: str, cet_midnight: datetime,
             positions: list[Any], orders: list[Any], server_epoch: float) -> None:
    from mt5desk.decision_core import family_bracket, signal_with_levels
    from mt5desk.families import get_family_func
    from mt5desk.family_call import (
        certified_session_filter,
        signal_reference_price,
        spread_blocks_entry,
    )
    from mt5desk.kelly_sizing import CERT_BOOK_FILE

    from libs.ops import new_risk_hold as _nrh
    from prop import e8_executor as _e8
    acc = mt5.account_info()
    try:
        equity, balance = float(acc.equity), float(acc.balance)
    except (AttributeError, TypeError, ValueError):
        doc.update(status="ACCOUNT_UNREADABLE", why="equity/balance unreadable")
        _veto(doc, now, armed, sleeves=[k for k, _, _ in sleeves])
        return
    risk_now, rwhy = book_stop_risk(mt5, positions, orders)
    doc["book_stop_risk"] = {"usd": None if risk_now is None else round(risk_now, 2),
                             "why": rwhy}
    try:
        start = _fw.day_start_balance(mt5, balance, cet_midnight, now,
                                      server_epoch=server_epoch)
    except Exception as exc:
        start, doc["day_start_error"] = None, f"{type(exc).__name__}: {exc}"[:160]
    try:
        exclusions = json.loads(CERT_BOOK_FILE.read_text(encoding="utf-8"))["excluded"]
        from admission_integrity import REPLICATED, IntegrityGate

        from libs.tiers import promotion_authority
        integrity = IntegrityGate.load()
        authority = None
    except Exception as exc:
        exclusions, integrity = {}, None
        authority = f"certificate authority unavailable ({type(exc).__name__}: {exc})"[:200]
    committed = 0.0
    held_syms = {str(p.symbol).upper() for p in positions} | {
        str(o.symbol).upper() for o in orders}
    _e8._INPUT_CACHE.clear()
    _e8._LAST_INPUT_REFUSAL.clear()

    for col, frac, spec in sleeves:
        sym, fam = str(spec["symbol"]).upper(), str(spec["family"])
        tf = str((spec.get("params") or {}).get("timeframe") or "H1").upper()
        want_usd = round(frac * equity, 2)
        row: dict[str, Any] = {"sleeve": col, "symbol": sym, "family": fam, "timeframe": tf,
                               "risk_frac": frac, "certificate": spec.get("key")}

        def done(status: str, why: str, *, rail: str | None = None, missed: bool = False,
                 row: dict[str, Any] = row, want_usd: float = want_usd) -> None:
            row.update(status=status, why=why)
            if rail:
                row["rail"] = rail
            if missed:
                row["missed_growth_risk_usd"] = row.get("risk_usd", want_usd)
            doc["sleeves"].append(row)
            _record(row, now, armed)

        if authority:
            done("NO_ENTRY_AUTHORITY", authority, rail="ftmo_executor", missed=True)
            continue
        if _e8._family_banned(fam):
            done("BANNED_FAMILY", _e8._ban_reason(fam))
            continue
        if col in exclusions:
            done("PRINCIPAL_EXCLUDED", str(exclusions[col]))
            continue
        if integrity.alarm.get("blocks"):
            done("CERTIFIER_ALARM", str(integrity.alarm.get("why")), rail="certifier_alarm",
                 missed=True)
            continue
        verdict, vwhy = integrity.replication(str(spec.get("key") or ""),
                                              str(spec.get("fingerprint") or ""))
        if verdict != REPLICATED:
            done("UNREPLICATED", f"{verdict}: {vwhy}", rail="replication", missed=True)
            continue
        try:
            tier = promotion_authority.block(str(spec.get("key") or ""))
        except Exception as exc:
            tier = f"Tier S door error ({type(exc).__name__}: {exc})"
        if tier:
            done("TIER_S_BLOCKED", str(tier), rail="tier_s_door", missed=True)
            continue
        func = get_family_func(fam)
        if func is None:
            done("NO_FAMILY", f"{fam} is not a registered family on this tree")
            continue
        if sym in held_syms:
            done("ALREADY_OPEN", f"the account already holds or rests {sym}")
            continue
        with_select = getattr(mt5, "symbol_select", None)
        if callable(with_select):
            with_select(sym, True)
        bars = frame(mt5, sym, tf)
        if bars is None or len(bars) < MIN_BARS:
            done("NO_BARS", f"{tf} history unavailable or short "
                            f"({0 if bars is None else len(bars)})")
            continue
        closed = _e8._last_closed(bars)
        last_bar = closed.index[-1]
        tf_s = TF_HOURS[tf] * 3600
        # THE BAR MUST BE THIS HOUR'S (audit MF2): the forming bar -- read off the frame, so a
        # Monday D1 or the first bar after a gap is not taken for a stall -- opened within one
        # bar of the server's clock (a minute's grace for a reference tick that lags it), or the
        # feed has stopped and the "last closed bar" is history.
        forming_open = (float(bars.index[-1].timestamp()) if len(bars) > len(closed)
                        else float(last_bar.timestamp()) + tf_s)
        if not -STALE_GRACE_S <= server_epoch - forming_open < tf_s:
            done("STALE_BARS", f"the last closed {tf} bar {last_bar} is not the latest one on the "
                               f"server clock; the feed is behind", rail="ftmo_stale_bars",
                 missed=True)
            continue
        slot = f"{col}|{last_bar.isoformat()}"
        if slot in st["traded"]:
            done("ALREADY_TRADED", f"this sleeve already sent on bar {last_bar}")
            continue
        params = _e8._call_params(spec, sym, closed)
        if params is None:
            done("NO_INPUTS", _e8._LAST_INPUT_REFUSAL.get(sym, "inputs could not be rebuilt"))
            continue
        try:
            sigs = func(bars, **params) if params else func(bars)
            sigs = certified_session_filter(list(sigs or []), spec)
        except Exception as exc:
            done("SIGNAL_ERROR", f"{type(exc).__name__}: {str(exc)[:140]}")
            continue
        fresh = [g for g in sigs if getattr(g, "time", None) == last_bar]
        if not fresh:
            row["n_signals_in_window"] = len(sigs)
            done("NO_SIGNAL", f"no signal on the last closed bar {last_bar}")
            continue
        g = fresh[-1]
        side = "buy" if int(g.side) > 0 else "sell"
        tick = mt5.symbol_info_tick(sym)
        info = mt5.symbol_info(sym)
        if tick is None or info is None:
            done("NO_QUOTE", f"no tick/symbol info for {sym}")
            continue
        bid, ask = float(tick.bid), float(tick.ask)
        sgn = 1 if side == "buy" else -1
        try:
            _ref = signal_reference_price(fam, bars, g)
            _e, stop, target, _d, note, drift, verdict = family_bracket(g, sgn, bid, ask, _ref)
            row["entry_drift"], row["entry_drift_note"] = drift, note
            if verdict == "stale":
                done("QUOTE_SPREAD" if spread_blocks_entry(g, sgn, bid, ask) else "STALE_SIGNAL",
                     note)
                continue
            if verdict == "re_anchored":
                g = signal_with_levels(g, stop, target)
        except Exception as exc:
            # UNMEASURED never resolves to a send (audit S1).
            done("UNMEASURED_BRACKET", f"the entry geometry is unmeasurable "
                                       f"({type(exc).__name__}: {exc})"[:200],
                 rail="ftmo_executor", missed=True)
            continue
        entry = ask if side == "buy" else bid
        stop_dist = abs(entry - float(g.stop))
        spread = ask - bid
        row.update(side=side, entry_ref=entry, stop=float(g.stop), target=float(g.target),
                   spread=spread, bar=str(last_bar))
        if not stop_dist > 0:
            done("UNSIZEABLE", "the stop is at the entry")
            continue
        if spread / stop_dist > _e8.MAX_SPREAD_FRAC_OF_STOP:
            done("SPREAD_TOO_WIDE", f"spread {spread:.6g} is {spread / stop_dist:.1%} of the "
                                    f"stop, over {_e8.MAX_SPREAD_FRAC_OF_STOP:.0%}",
                 rail="ftmo_spread_fence", missed=True)
            continue
        lpl = loss_per_lot(mt5, sym, side, entry, float(g.stop))
        if lpl is None:
            done("UNPRICED", f"the terminal cannot price a lot of {sym} to its stop",
                 rail="ftmo_executor", missed=True)
            continue
        try:
            vmin, vstep = float(info.volume_min), float(info.volume_step)
            vmax = float(getattr(info, "volume_max", 0.0) or 0.0)
            contract = float(info.trade_contract_size)
        except (AttributeError, TypeError, ValueError):
            done("UNSIZEABLE", "volume limits unreadable")
            continue
        lot = lot_for_loss(frac, equity, lpl, vmin=vmin, vstep=vstep, vmax=vmax)
        if not lot > 0:
            done("UNSIZEABLE", f"{frac:g} of equity at a {stop_dist:.6g} stop is below the "
                               f"{vmin:g} lot minimum", rail="venue_min_lot", missed=True)
            continue
        # the follower's notional cap, in account currency: lot x contract x price x (account
        # currency per quote unit, read off the terminal's own P&L arithmetic)
        point = float(getattr(info, "point", 0) or 0)
        per_unit = loss_per_lot(mt5, sym, "buy", entry, entry - point) if point > 0 else None
        if not per_unit or not contract > 0:
            # an unmeasurable cap is never skipped (audit MF5)
            done("RAIL_BLOCKED", "the notional lot cap is unmeasurable (point, contract or the "
                                 "terminal's P&L arithmetic unreadable)", rail=_fw.LOT_CAP_RAIL,
                 missed=True)
            continue
        px_acct = entry * per_unit / (point * contract)
        cap, cap_why = _fw.lot_cap(equity, px_acct, contract, vstep=vstep,
                                   declared=decl.get("max_lot"))
        if lot > cap:
            row["lot_uncapped"], row["lot_cap_why"] = lot, cap_why
            if cap < vmin:
                done("RAIL_BLOCKED", f"the lot cap ({cap_why}) is below the minimum lot",
                     rail=_fw.LOT_CAP_RAIL, missed=True)
                continue
            # billed even when the trimmed order is SENT (audit SF2)
            row.update(missed_growth_risk_usd=round((lot - cap) * lpl, 2),
                       rail=_fw.LOT_CAP_RAIL, trimmed=True)
            lot = cap
        # the stop one spread wide: FTMO's daily limit counts the fill, not the level
        slip_lpl = loss_per_lot(mt5, sym, side, entry,
                                float(g.stop) - sgn * spread) or lpl
        risk = lot * slip_lpl
        row.update(lot=lot, risk_usd=round(lot * lpl, 2), risk_usd_with_slip=round(risk, 2))
        if risk_now is None or start is None:
            done("RAIL_BLOCKED", f"the book's stop risk or today's start is unmeasurable "
                                 f"({rwhy if risk_now is None else doc.get('day_start_error')})",
                 rail="ftmo_loss_guard", missed=True)
            continue
        ok, gwhy = _fw.loss_guard(float(decl["initial_balance"]), start, equity,
                                  risk_now + committed + risk,
                                  daily_frac=float(decl.get("daily_loss_frac")
                                                   or _fw.DAILY_LOSS_FRAC))
        row["loss_guard"] = gwhy
        if not ok:
            done("RAIL_BLOCKED", gwhy, rail="ftmo_loss_guard", missed=True)
            continue
        if _fw.near_market_close(now):
            done("RAIL_BLOCKED", f"within {_fw.GAP_GUARD_H:g}h of the daily close (FTMO: no gap "
                                 f"trading)", rail="ftmo_gap_guard", missed=True)
            continue
        if (hold := _nrh.reason()) is not None:
            done("RAIL_BLOCKED", hold, rail="adopt_new_risk_hold", missed=True)
            continue
        # since the FORMING bar opened: an order sent for the previous bar never blocks this one
        spent = history_since(mt5, sym, forming_open, now)
        if spent is not False:
            done("ALREADY_TRADED" if spent else "RAIL_BLOCKED",
                 "this lane already has an order/deal on the symbol in this bar"
                 if spent else "the FTMO history is unreadable", rail=None if spent else
                 "ftmo_executor", missed=spent is None)
            continue
        comment = comment_for(col, getattr(g, "ttl_bars", None), tf)
        if not armed:
            row["status"], row["why"] = "WOULD_SEND", "standby: FTMO_EXECUTOR_ARMED absent"
            committed += risk
            doc["sleeves"].append(row)
            _record(row, now, armed)
            continue
        guard = {"initial": float(decl["initial_balance"]), "start": start,
                 "daily_frac": float(decl.get("daily_loss_frac") or _fw.DAILY_LOSS_FRAC),
                 "committed": committed, "risk": risk}
        _send_locked(mt5, st, doc, row, now=now, cet=cet, sym=sym, side=side, lot=lot,
                     g=g, info=info, slot=slot, comment=comment, col=col, guard=guard,
                     server_epoch=server_epoch)
        if row.get("status") == "SENT":
            committed += risk
            held_syms.add(sym)


def _send_locked(mt5: Any, st: dict[str, Any], doc: dict[str, Any], row: dict[str, Any], *,
                 now: datetime, cet: str, sym: str, side: str, lot: float, g: Any, info: Any,
                 slot: str, comment: str, col: str, guard: dict[str, Any],
                 server_epoch: float = 0.0) -> None:
    """The fences, the loss re-check and the send, as one, under the placement lock every lane
    takes (audit S4: the follower cannot add risk between this lane's reading and its send)."""
    from mt5desk import cross_account as _xa
    with _xa.placement_lock(f"ftmo_executor:{col}") as locked:
        why = None if locked else ("cross-account fence: the placement lock is held by another "
                                   "lane; fail closed (retried next pass)")
        rail = "cross_account_opposite"
        if why is None:
            for acct in ("fusion", "e8"):
                book, bwhy = _xa.read_book(acct, now=now)
                why = _xa.opposite_block(book, sym, side, account=acct, why_absent=bwhy)
                if why:
                    break
                same = "long" if side == "buy" else "short"
                if not ALLOW_CROSS_FIRM_COPY and book is not None and any(
                        _xa.same_instrument(b, sym) and r.get(same) for b, r in book.items()):
                    rail = "cross_firm_copy"
                    why = (f"cross-firm copy: the {acct} account holds the same {same} on {sym}; "
                           f"the cross-firm copy override is switched off")
                    break
        if why is None:
            live_p, live_o = mt5.positions_get(), mt5.orders_get()
            if live_p is None or live_o is None:
                why = "the FTMO book is unreadable under the lock; fail closed"
            else:
                mine = [x for x in [*live_p, *live_o] if str(x.symbol).upper() == sym]
                if [x for x in mine if _side_of(int(getattr(x, "type", -1))) not in (None, side)]:
                    why = f"this FTMO account holds or rests the other side of {sym}"
                elif mine:
                    why = f"this FTMO account already holds or rests {sym}"
                else:
                    risk_now, rwhy = book_stop_risk(mt5, list(live_p), list(live_o))
                    acc = mt5.account_info()
                    eq = float(getattr(acc, "equity", 0.0) or 0.0)
                    if risk_now is None or not eq > 0:
                        why, rail = f"the book's risk is unmeasurable under the lock ({rwhy})", \
                            "ftmo_loss_guard"
                    else:
                        ok, gwhy = _fw.loss_guard(guard["initial"], guard["start"], eq,
                                                  risk_now + guard["risk"],
                                                  daily_frac=guard["daily_frac"])
                        if not ok:
                            why, rail = gwhy, "ftmo_loss_guard"
        if why is not None:
            row.update(status="RAIL_BLOCKED", rail=rail, why=why,
                       missed_growth_risk_usd=row.get("risk_usd"))
            doc["sleeves"].append(row)
            _record(row, now, True)
            return
        try:
            _reserve(st, cet)                          # counted before the write-ahead (SF6)
        except RuntimeError as exc:
            row.update(status="REJECTED", why=str(exc))
            doc["sleeves"].append(row)
            _record(row, now, True)
            return
        # WRITE-AHEAD: the (sleeve, bar) is spent before the send, so a lost reply or a crash
        # can never send it twice.
        st["traded"][slot] = now.isoformat(timespec="seconds")
        if len(st["traded"]) > KEEP_TRADED:
            st["traded"] = dict(sorted(st["traded"].items(), key=lambda kv: str(kv[1]))
                                [-KEEP_TRADED:])
        try:
            _fw._atomic_write(STATE, json.dumps(st, indent=1, default=str))
        except OSError as exc:
            row.update(status="REJECTED", why=f"state write-ahead failed ({exc}); not sent")
            doc["sleeves"].append(row)
            _record(row, now, True)
            return
        tick = mt5.symbol_info_tick(sym)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(lot),
               "type": mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL,
               "price": float(tick.ask if side == "buy" else tick.bid),
               "sl": float(g.stop), "tp": float(g.target), "deviation": 20, "magic": MAGIC,
               "comment": comment, "type_time": mt5.ORDER_TIME_GTC,
               "type_filling": filling_mode(mt5, info)}
        t0 = time.perf_counter()
        try:
            # BOUNDED UNDER THE LOCK, as the E8 executor's send: a hung call raises and is
            # recorded REJECTED (it may still have landed: the MAGIC history then holds the bar).
            # The symbol is held IN FLIGHT on the FTMO book first, so the gateway and the E8
            # executor see both sides held until the send returns (or its hold expires).
            res = _xa.bounded(lambda: mt5.order_send(req),
                              what=f"ftmo_executor:{sym} send", account="ftmo", symbol=sym)
        except Exception as exc:
            row.update(status="REJECTED", why=f"{type(exc).__name__}: {exc}"[:200])
            doc["sleeves"].append(row)
            _record(row, now, True)
            return
        finally:
            with contextlib.suppress(Exception):     # the readers fail closed on its age
                _xa.bounded(lambda: _xa.publish_mt5(mt5, source="ftmo_executor", account="ftmo"),
                            timeout_s=_xa.LOCKED_PUBLISH_TIMEOUT_S,
                            what="ftmo_executor publish")
        code = getattr(res, "retcode", None)
        m = _COMMENT_RE.match(comment)
        if code in OK_CODES and m is not None and int(m.group(1)) > 0 and server_epoch:
            # the time exit kept by ticket too, for a broker that rewrites the comment (MF3)
            holds = st.setdefault("holds", {})
            holds[str(getattr(res, "order", ""))] = {
                "exit": server_epoch + int(m.group(1)) * TF_HOURS[m.group(2)] * 3600,
                "sleeve": col}
            if len(holds) > KEEP_TRADED:
                st["holds"] = dict(list(holds.items())[-KEEP_TRADED:])
        row.update(status="SENT" if code in OK_CODES else "REJECTED", retcode=code,
                   order_id=getattr(res, "order", None),
                   latency_send_to_ack_ms=round((time.perf_counter() - t0) * 1000.0, 3))
        doc["sleeves"].append(row)
        _record(row, now, True)
        log(f"[{col}] {row['status']} {side} {lot} {sym} sl {g.stop} tp {g.target} -> {code}")


def _write_out(doc: dict[str, Any], st: dict[str, Any] | None) -> None:
    try:
        if st is not None:
            _fw._atomic_write(STATE, json.dumps(st, indent=1, default=str))
        _fw._atomic_write(OUT, json.dumps(doc, indent=1, default=str))
    except OSError as exc:
        log(f"state/report write failed: {exc}")


def main(argv: list[str] | None = None) -> int:
    del argv
    ok, why = _fw.interactive_session()
    if not ok:
        log(f"not run: {why}")
        return 1
    armed = ARMED_MARKER.exists()
    try:
        import os

        import MetaTrader5 as mt5
        path = os.environ.get(_fw.TERMINAL_ENV) or _fw.TERMINAL_PATH
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
    sent = sum(1 for r in doc.get("sleeves", []) if r.get("status") in ("SENT", "WOULD_SEND"))
    log(f"ftmo executor: {'ARMED' if armed else 'STANDBY'} status={doc.get('status')} "
        f"sleeves={len(doc.get('sleeves', []))} sent_or_would={sent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
