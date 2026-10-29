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
  * the daily loss limit OF THE DECLARED ACCOUNT TYPE (v2, audit must-fix 9): 5% for a 2-Step
    account, 3% for a 1-Step (`ACCOUNT_TYPES`; an undeclared or unknown type binds nothing), and
    the 10% maximum loss, measured from the balance at midnight CET (re-derived from the deal
    history every pass): the order is refused when its risk, with E8's measured 24.13-pt stop
    slippage added to the stop distance, plus today's loss could reach the daily limit of the
    initial balance, or the equity after it could reach 90% of it.
  * THE LOT CAP (v2, audit must-fix 10): 0.009 of equity over a narrow E8 stop is a large lot,
    and FTMO flags a trade "much larger than usual". The lot is capped at MAX_NOTIONAL_X times
    equity in notional (lot x contract x price) and at the account file's optional "max_lot". A
    lot the cap clips is journalled as a RAIL_BLOCKED row under rail `ftmo_lot_cap` with the risk
    it held back -- its missed-growth line (research/missed_growth.published_ftmo_follower_lines).

ONCE PER E8 FILL, AND ONCE A DAY, WHATEVER THE STATE FILE SAYS (v2, audit must-fix 4). The
follow is keyed to E8's position id (`followed`, kept across days) AND to the FTMO account's own
MAGIC history: any MAGIC gold order or deal on today's server date (`history_spent`) means the
day is spent, so a lost or torn state file can never produce a second order; an unreadable
history places nothing. The state is marked BEFORE the send and written atomically (tmp, flush,
fsync, os.replace, retried on Windows' PermissionError).

A FILL AGAINST THE DAY'S DIRECTION is closed at once (gold_oco.positions_to_flatten), and an
account the keyed helper cannot name PAGES (gold_oco.page_identity).

ACCOUNT BINDING. `data/FTMO_LIVE_ACCOUNT.json` (gitignored, written by the principal's own step,
never committed): {"login", "server", "trade_mode", "initial_balance", "account_type"} with
account_type "2-step" or "1-step", and optionally "max_lot". The terminal's
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
import math
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cancel_pending as _cancel_req  # noqa: E402
from mt5desk import cross_account as _xa  # noqa: E402
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
#: THE PROP FILLS LEDGER (schema prop-fills-v1): every closed FTMO position, book "ftmo", so
#: FTMO is measured from its first trade. Written by THIS module (compose_fills / append_fills);
#: no prop/fills_ledger.py exists in any branch (checked 2026-10-28), and no E8 writer appends
#: here today -- the O_APPEND one-line writes keep a second writer safe if one is added.
PROP_LEDGER = DESK / "data" / "live_ledger_prop.jsonl"
PROP_SCHEMA = "prop-fills-v1"
#: The ledger's refusal list: a row carrying any of these is never written.
PROP_BANNED = ("account", "login", "username", "password", "acc_num", "account_id")
#: THE FEES (v2r fix 1): commission, swap and fee are READ from the position's MT5 deals (its
#: entry deal and every exit deal, summed per field) -- `fees_status` "MEASURED" when all three
#: are read off every deal, a measured 0.0 included. A field a deal truly does not carry is null,
#: never 0.0, and `fees_status` names which field and why (`fees_measured` lists the read ones).
PROP_FEE_FIELDS = (("commission", "commission"), ("swap", "swap"), ("fees", "fee"))
PROP_FEES_MEASURED = "MEASURED"
#: MT5 DEAL_REASON of a position's last exit deal: 0 CLIENT (desktop), 1 MOBILE, 2 WEB are a
#: person's hand close; 3 EXPERT is the desk's own close; 4 SL / 5 TP / 6 SO are the venue's.
EXIT_REASON = {0: "manual", 1: "manual", 2: "manual", 3: "close", 4: "stop", 5: "target",
               6: "stop_out"}
CLOSED_BY = {0: "manual", 1: "manual", 2: "manual", 3: "desk", 4: "venue", 5: "venue",
             6: "venue"}
#: How far back the deal history is read: a follow held over a weekend and closed by hand on
#: Monday still has its entry deal inside the window.
PROP_LOOKBACK = timedelta(days=7)
#: E8-Gold's pass report (prop/e8_gold.OUT), the first of the three readings this lane follows.
E8_REPORT = DESK / "reports" / "E8_GOLD.json"
#: E8'S STALENESS BOUND (v2r fix 2): one E8 pass plus its grace, DERIVED FROM E8'S CADENCE the
#: way r7 derives `decision_core.E8_GOLD_SEND_GRACE_MIN` (install_e8_tasks.ps1: first pass at
#: +1 min, `RepetitionInterval 5 min`, `LimitMinutes 4`; 10 = 1 + 5 + 4). A healthy E8 rewrites
#: its report and its gold state at least once per pass; the grace beyond the pass is the pass's
#: own run limit, 10 - 1 - 5 = 4 min. So the follower refuses to place on an E8 state older
#: than 300 + 240 = 540 s (it was the OCO's 600 s two-pass bound), and bills each refusal.
E8_PASS_S = 300.0
E8_FIRST_PASS_OFFSET_MIN = 1.0


def e8_stale_limit_s() -> tuple[float, str]:
    """(the age in seconds past which E8's report or gold state is stale, its derivation). The
    grace is read at call time from `decision_core.E8_GOLD_SEND_GRACE_MIN` (gateway re-exports
    it); when that is unreadable the grace is 0 and the bound is one bare pass (fail closed:
    a tighter bound refuses, never places)."""
    try:
        from mt5desk import decision_core as _dc
        grace_min = float(_dc.E8_GOLD_SEND_GRACE_MIN) - E8_FIRST_PASS_OFFSET_MIN \
            - E8_PASS_S / 60.0
        if not math.isfinite(grace_min) or grace_min < 0.0:
            raise ValueError(grace_min)
    except Exception:
        return E8_PASS_S, "one E8 pass (300s); E8_GOLD_SEND_GRACE_MIN unreadable, no grace"
    return E8_PASS_S + grace_min * 60.0, (
        f"one E8 pass (300s) + its {grace_min:g}-min run limit (E8_GOLD_SEND_GRACE_MIN "
        f"{E8_FIRST_PASS_OFFSET_MIN:g} + 5 + {grace_min:g})")

MAGIC = 341955
COMMENT = "FTgold_asia"
#: E8's measured stop slippage (2026-09-24: a buy stop filled 24.13 points through its level).
SLIP_ALLOWANCE_PTS = 24.13
DAILY_LOSS_FRAC = 0.05
MAX_LOSS_FRAC = 0.10
#: FTMO's daily loss limit by account type (audit v2 must-fix 9): 2-Step 5%, 1-Step 3%.
ACCOUNT_TYPES = {"2-step": 0.05, "1-step": 0.03}
#: THE LOT CAP (audit v2 must-fix 10): notional (lot x contract x price) at most this many
#: times equity. At 100k equity, gold at 4,000 and 100 oz a lot that is 1.25 lots -- 0.009 of
#: equity reaches it only on a stop under 7.2 points. The cap's clip is billed (LOT_CAP_RAIL).
MAX_NOTIONAL_X = 5.0
LOT_CAP_RAIL = "ftmo_lot_cap"
#: E8 position ids followed, kept this many (they span days: once per E8 fill, ever).
FOLLOWED_KEEP = 60
_WRITE_TRIES = 10
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
    ("wait" | "stand_aside" | "e8_stale" | "unreadable", None, why). Pure. "e8_stale": E8's
    report or gold state is older than `e8_stale_limit_s` (one pass + its grace) -- refused and
    billed, never followed.

    The signal is E8's filled leg: {"side", "price", "sl", "tp", "e8_position_id"}. Anything but
    "follow" means no new FTMO order, and any resting FTMO entry is cancelled."""
    if not isinstance(e8_doc, dict):
        return "unreadable", None, "E8's pass report (E8_GOLD.json) is absent or unreadable"
    at = _iso(e8_doc.get("at"))
    if at is None:
        return "unreadable", None, "E8's pass report carries no readable timestamp"
    age = (now - at).total_seconds()
    limit, basis = e8_stale_limit_s()
    if age < -60.0:
        return "unreadable", None, f"E8's pass report is stamped {-age:.0f}s in the future"
    if age > limit:
        return "e8_stale", None, (f"E8's pass report is {age:.0f}s old (limit {limit:.0f}s: "
                                  f"{basis}); E8 is not running, nothing is followed")
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
        if " old (limit " in str(lane_why):                 # gold_oco.read_lane's age refusal
            return "e8_stale", None, (f"E8's published gold state: {lane_why} (bound: "
                                      f"{e8_stale_limit_s()[1]})")
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


def lot_cap(equity: float, price: float, contract: float, *, vstep: float,
            declared: object = None) -> tuple[float, str]:
    """(the largest lot the follower may send, why). Pure. MAX_NOTIONAL_X x equity in notional,
    floored to the volume step, and never above a declared `max_lot`. 0.0 when unreadable."""
    if not (equity > 0 and price > 0 and contract > 0 and vstep > 0):
        return 0.0, "the notional cap is unmeasurable (equity, price or contract unreadable)"
    cap = int(MAX_NOTIONAL_X * equity / (price * contract) / vstep + 1e-9) * vstep
    why = f"{MAX_NOTIONAL_X:g}x equity in notional = {cap:.2f} lot"
    try:
        dl = float(declared) if declared not in (None, "") else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        dl = None
    if dl is not None and dl > 0 and dl < cap:
        cap, why = dl, f"the account file's max_lot {dl:g}"
    return round(cap, 8), why


def trade_risk(lot: float, dist: float, contract: float) -> float:
    """Dollars at risk if the stop fills E8's measured slippage through its level."""
    return (float(dist) + SLIP_ALLOWANCE_PTS) * float(lot) * float(contract)


def loss_guard(initial: float, day_start_balance: float, equity: float,
               new_risk: float, *, daily_frac: float = DAILY_LOSS_FRAC) -> tuple[bool, str]:
    """FTMO's daily (`daily_frac`: 5% 2-Step, 3% 1-Step) and 10% maximum loss: may `new_risk`
    be added now?"""
    daily = daily_frac * initial
    today_loss = max(0.0, day_start_balance - equity)
    floor = initial * (1.0 - MAX_LOSS_FRAC)
    why = (f"today's loss {today_loss:,.2f} + this trade {new_risk:,.2f} (stop + "
           f"{SLIP_ALLOWANCE_PTS} pt slip) against the {daily_frac:.0%} daily limit "
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


#: How far a tick may sit from a whole-hour server offset to be read as the server clock: the
#: box clock's skew plus the tick's age. A single tick cannot tell a stale tick from a skewed
#: clock (a 70-minute-old tick on UTC+3 reads exactly like a 10-minute-old one on UTC+2), so only
#: a FRESH tick is read at all; a quiet market or gold's daily break refuses, billed by the caller.
TICK_SKEW_S = 300.0


def server_offset_from_tick(server_epoch: float, now: datetime) -> int:
    """The server's UTC offset in hours, read off a tick's time (MT5 stamps server wall time as
    if it were UTC). RAISES ValueError when the tick cannot be the server clock: none, more than
    TICK_SKEW_S off a whole hour (stale, or the box clock off), or outside UTC+0..+4."""
    if not server_epoch:
        raise ValueError("no tick to read the server clock from")
    lag = float(server_epoch) - now.timestamp()
    off = round(lag / 3600.0)
    if not 0 <= off <= 4 or abs(lag - off * 3600.0) > TICK_SKEW_S:
        raise ValueError(f"a tick {lag / 3600.0:+.2f}h off the box clock is not the server "
                         f"clock (not within {TICK_SKEW_S:.0f}s of a whole-hour offset)")
    return off


def day_start_balance(mt5: Any, balance: float, since: datetime, now: datetime, *,
                      server_epoch: float | None = None) -> float:
    """The balance at FTMO's midnight: today's balance less every deal's result since then.
    RAISES when it cannot be measured (the guard then refuses): an unreadable deal history, a
    deal with no readable time, or a server clock that cannot be read off a live tick.

    ON THE SERVER CLOCK (audit MF4, 2026-10-29). MT5 stamps a deal with the server's wall clock
    as if it were UTC, and the API reads its datetime window the same way, so a window in real UTC
    was shifted by the server offset: it counted the last two or three hours of the previous CET
    day as today's and DROPPED the last two or three hours of today's deals (the most recent
    losses, the ones the daily-loss rail most needs). The query is wide (a day each side) and
    each deal is kept when its own server stamp is at or after CET midnight on the server clock.

    THE OFFSET IS MEASURED, NEVER ASSUMED (audit 2026-10-29): read off `server_epoch` (a live
    tick's time, the caller's own) or, absent, this account's XAUUSD tick. FTMO's server is not
    asserted to be NY+7: on an EET server the two differ for a week each spring and autumn, and a
    loss in the first CET hour then fell out of today. A tick that cannot be the server clock
    (`server_offset_from_tick`) RAISES. A deal with no readable time RAISES too: counted as
    today's, a profit or a deposit among them would understate today's loss."""
    if server_epoch is None:
        tick = mt5.symbol_info_tick(SYMBOL)
        server_epoch = float(getattr(tick, "time", 0) or 0) if tick is not None else 0.0
    try:
        off = server_offset_from_tick(float(server_epoch or 0.0), now)
    except ValueError as exc:
        raise ValueError(f"the server clock is unreadable ({exc}); today's start is "
                         f"unmeasurable") from exc
    deals = mt5.history_deals_get(since - timedelta(days=1), now + timedelta(days=1))
    if deals is None:
        raise ValueError("the deal history is unreadable")
    start = since.timestamp() + off * 3600.0
    moved = 0.0
    for d in deals:
        ts = getattr(d, "time", None)
        if not isinstance(ts, (int, float)) or isinstance(ts, bool) or ts <= 0:
            raise ValueError(f"a deal ({getattr(d, 'ticket', '?')}) has no readable time")
        if ts < start:
            continue
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


def history_spent(mt5: Any, today: str, now: datetime) -> tuple[bool | None, str]:
    """(spent, why): has this account ANY MAGIC gold order or deal dated `today` on the server
    clock (`gold_oco.trading_date`, as every lane dates its day)? None when the history cannot
    be read -- the caller then places nothing. The window queried is wide (two days back, one
    ahead: the API's datetime reading of server time is not trusted) and filtered by each row's
    own server timestamp."""
    since, until = now - timedelta(days=2), now + timedelta(days=1)
    orders = mt5.history_orders_get(since, until)
    deals = mt5.history_deals_get(since, until)
    if orders is None or deals is None:
        return None, "the FTMO order/deal history is unreadable"
    for kind, rows, field in (("order", orders, "time_setup"), ("deal", deals, "time")):
        for r in rows:
            if int(getattr(r, "magic", 0) or 0) != MAGIC:
                continue
            if _xa.norm(getattr(r, "symbol", "")) != _xa.norm(SYMBOL):
                continue
            ts = getattr(r, field, None)
            if not isinstance(ts, (int, float)) or isinstance(ts, bool) or ts <= 0:
                return True, f"a MAGIC gold {kind} with an unreadable time (counted as today's)"
            if _oco.trading_date(float(ts)) == today:
                return True, f"a MAGIC gold {kind} is already on today's ({today}) history"
    return False, "no MAGIC gold order or deal today"


# ------------------------------------------------------------------ the prop fills ledger

def _iso_epoch(ts: object) -> str | None:
    if not isinstance(ts, (int, float)) or isinstance(ts, bool) or ts <= 0:
        return None
    return datetime.fromtimestamp(float(ts), tz=UTC).isoformat(timespec="seconds")


def deal_fees(deals: list[Any]) -> tuple[dict[str, float | None], list[str], str]:
    """({row field: sum or None}, the measured row fields, fees_status) over a position's MT5
    deals. A field is the sum of the deals' own values when EVERY deal carries a number for it
    (a measured 0.0 is a measurement); else None -- the deal lacks it -- and the status names
    the field and the deal count. Pure."""
    out: dict[str, float | None] = {}
    measured: list[str] = []
    missing: list[str] = []
    for field, attr in PROP_FEE_FIELDS:
        vals = [getattr(d, attr, None) for d in deals]
        if deals and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                         and math.isfinite(float(v)) for v in vals):
            out[field] = round(sum(float(v) for v in vals), 2)
            measured.append(field)
        else:
            n = sum(1 for v in vals if not (isinstance(v, (int, float))
                                            and not isinstance(v, bool)))
            out[field] = None
            missing.append(f"{attr} ({n} of {len(deals)} deals carry no number)")
    if not missing:
        return out, measured, PROP_FEES_MEASURED
    return out, measured, ("PARTIAL: " if measured else "UNMEASURED: ") + (
        "the MT5 deal history lacks " + ", ".join(missing) + "; null, never 0.0")


def compose_fills(deals: Any, orders: Any, open_ids: set[int], *, account_key: str | None,
                  contract: float | None, recorded_at: str) -> list[dict[str, Any]]:
    """prop-fills-v1 rows (the schema's field names; there is no prop/fills_ledger.py module --
    this writer IS the ledger's FTMO side) for every CLOSED FTMO position this lane opened: an
    entry deal (DEAL_ENTRY_IN) under MAGIC and at least one exit deal (OUT / OUT_BY) on its
    position id, the position no longer open. Pure. Nothing is invented: an unpriced or
    still-open position is not written.

    A MANUAL OR EXTERNAL CLOSE COUNTS (2026-10-28, FTMO 111616773). zuck closed that position by
    hand in the terminal; MT5 stamps a hand close's exit deal with magic 0, and the old filter
    kept MAGIC deals only, so the position had an entry and no exit and was never written --
    no price, no P&L. The position is ours by its ENTRY deal; every exit deal on it is read,
    whatever its magic, and `closed_by` says who closed it (deal reason)."""
    by_pos: dict[int, list[Any]] = {}
    ours: set[int] = set()
    for d in deals or []:
        if _xa.norm(getattr(d, "symbol", "")) != _xa.norm(SYMBOL):
            continue
        pid = int(getattr(d, "position_id", 0) or 0)
        if not pid:
            continue
        by_pos.setdefault(pid, []).append(d)
        if int(getattr(d, "magic", 0) or 0) == MAGIC and int(getattr(d, "entry", -1)) == 0:
            ours.add(pid)
    by_pos = {pid: ds for pid, ds in by_pos.items() if pid in ours}
    sent = {int(getattr(o, "ticket", 0) or 0): o for o in orders or []}
    rows: list[dict[str, Any]] = []
    for pid, ds in sorted(by_pos.items()):
        if pid in open_ids:
            continue
        ins = [d for d in ds if int(getattr(d, "entry", -1)) == 0]
        outs = [d for d in ds if int(getattr(d, "entry", -1)) in (1, 3)]
        ins = [d for d in ins if int(getattr(d, "magic", 0) or 0) == MAGIC]
        if not ins or not outs:
            continue
        e = min(ins, key=lambda d: float(getattr(d, "time", 0) or 0))
        dirn = 1 if int(getattr(e, "type", -1)) == 0 else -1 if int(getattr(e, "type", -1)) == 1 \
            else 0
        try:
            entry_px = float(e.price)
            q_tot = sum(float(d.volume) for d in outs)
            exit_px = sum(float(d.price) * float(d.volume) for d in outs) / q_tot
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            continue
        if dirn == 0 or not (entry_px > 0 and exit_px > 0):
            continue
        last = max(outs, key=lambda d: float(getattr(d, "time", 0) or 0))
        o = sent.get(int(getattr(e, "order", 0) or 0))
        sl = float(getattr(o, "sl", 0.0) or 0.0) or None if o is not None else None
        tp = float(getattr(o, "tp", 0.0) or 0.0) or None if o is not None else None
        dist = abs(entry_px - sl) if sl else None
        volume = float(getattr(e, "volume", 0.0) or 0.0)
        pl = [getattr(d, "profit", None) for d in outs]
        fees, fees_measured, fees_status = deal_fees([e, *outs])
        pl_quote = (round(sum(float(x) for x in pl), 2)
                    if all(isinstance(x, (int, float)) for x in pl) else None)
        rows.append({
            "schema": PROP_SCHEMA, "book": LANE, "venue": "mt5", "lane": "ftmo_follower",
            "provenance": "ftmo_follower:mt5_deal_history", "recorded_at": recorded_at,
            "time": _iso_epoch(getattr(last, "time", None)), "sleeve": CERT_KEY,
            "symbol": SYMBOL, "entry_side": 0 if dirn == 1 else 1, "side": 1 if dirn == 1 else 0,
            "entry_time": _iso_epoch(getattr(e, "time", None)),
            "exit_time": _iso_epoch(getattr(last, "time", None)),
            "timestamp_basis": "mt5_server_epoch", "venue_clock_skew_ms": None,
            "entry_time_box_utc": None, "entry_price": entry_px,
            "intended_entry": (float(getattr(o, "price_open", 0.0) or 0.0) or None
                               if o is not None else None),
            "sl": sl, "tp": tp, "volume": volume, "fill_price": round(exit_px, 6),
            "exit_reason": EXIT_REASON.get(int(getattr(last, "reason", -1)), "close"),
            "closed_by": CLOSED_BY.get(int(getattr(last, "reason", -1)), "unknown"),
            "exit_magic": sorted({int(getattr(d, "magic", 0) or 0) for d in outs}),
            "exit_order_type": None,
            "r_multiple": (round(dirn * (exit_px - entry_px) / dist, 4) if dist else None),
            "r_basis": "price: side x (exit - entry) / |entry - sent stop|, gross of fees",
            "r_unreconstructible": not dist,
            "risk_quote": (round(dist * volume * contract, 6) if dist and contract else None),
            "pl_quote": pl_quote,
            "quote_ccy": "USD", "pl_basis": "the MT5 exit deals' profit, gross of fees",
            **fees, "fees_status": fees_status, "fees_measured": fees_measured,
            "fees_basis": "sum over the position's entry and exit MT5 deals",
            "pl_net_quote": (round(pl_quote + sum(v for v in fees.values() if v is not None), 2)
                             if pl_quote is not None and fees_status == PROP_FEES_MEASURED
                             else None),
            "position_id": pid, "entry_order": int(getattr(e, "order", 0) or 0) or None,
            "close_order": int(getattr(last, "order", 0) or 0) or None,
            "n_exit_orders": len(outs), "server": "FTMO", "account_kind": "prop",
            "account_key": account_key,
            "account_key_status": "keyed (gold_oco.oco_account_key)" if account_key
            else "UNMEASURED: no keyed account key"})
    return rows


def append_fills(rows: list[dict[str, Any]], path: Path | None = None) -> int:
    """Append rows the ledger does not hold, deduped by "ftmo:" + position id. TWO WRITERS (E8
    appends here too): each row is ONE os.write of one whole line on an O_APPEND descriptor, so
    the OS places every line at the end in one piece and no writer can interleave into or
    overwrite another's. Refuses any row carrying a login-shaped field (the ledger's
    rule). Returns how many were written; RAISES OSError / ValueError."""
    path = Path(path or PROP_LEDGER)
    for r in rows:
        for banned in PROP_BANNED:
            if banned in r:
                raise ValueError(f"refusing a prop ledger row carrying {banned!r}")
        read = r.get("fees_measured") if isinstance(r.get("fees_measured"), list) else []
        for field, _attr in PROP_FEE_FIELDS:
            if r.get(field) is not None and field not in read:
                raise ValueError(f"a prop ledger {field} not read off the MT5 deal is null "
                                 "with fees_status, never 0.0 or a guess")
    have: set[str] = set()
    if path.exists():
        for ln in path.read_text("utf-8", errors="replace").splitlines():
            with contextlib.suppress(ValueError):
                d = json.loads(ln)
                if isinstance(d, dict):
                    have.add(f"{d.get('book')}:{d.get('position_id')}")
    new = [r for r in rows if f"ftmo:{r.get('position_id')}" not in have]
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0),
                 0o644)
    try:
        for r in new:
            os.write(fd, (json.dumps(r, default=str, sort_keys=True) + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return len(new)


def record_fills(mt5: Any, key: str | None, open_ids: set[int], now: datetime) -> dict[str, Any]:
    """Write every closed FTMO position to the prop fills ledger. NEVER RAISES: a ledger that
    cannot be written costs a row, never an order."""
    try:
        since, until = now - PROP_LOOKBACK, now + timedelta(days=1)
        deals = mt5.history_deals_get(since, until)
        orders = mt5.history_orders_get(since, until)
        if deals is None or orders is None:
            return {"written": 0, "why": "the deal/order history is unreadable"}
        info = mt5.symbol_info(SYMBOL)
        contract = float(getattr(info, "trade_contract_size", 0.0) or 0.0) or None
        rows = compose_fills(deals, orders, open_ids, account_key=key, contract=contract,
                             recorded_at=now.isoformat(timespec="seconds"))
        return {"written": append_fills(rows), "closed_seen": len(rows)}
    except Exception as exc:
        return {"written": 0, "why": f"{type(exc).__name__}: {exc}"[:160]}


# ------------------------------------------------------------------ the account

def account_snapshot(mt5: Any, now: datetime) -> dict[str, Any]:
    """FTMO's equity, balance and floating P&L as the terminal reports them this pass, for the
    state file (2026-10-28: FTMO equity was in no state file at all). No login or server: the
    account is named by its key elsewhere. A field the terminal does not give is null, never 0."""
    out: dict[str, Any] = {"at": now.isoformat(timespec="seconds")}
    try:
        acc = mt5.account_info()
    except Exception as exc:
        acc = None
        out["why"] = f"account_info raised {type(exc).__name__}"
    for f in ("equity", "balance", "profit", "margin", "margin_free"):
        v = getattr(acc, f, None) if acc is not None else None
        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))
        out[f] = round(float(v), 2) if ok else None
    out["currency"] = getattr(acc, "currency", None) if acc is not None else None
    if acc is None and "why" not in out:
        out["why"] = "the FTMO terminal did not answer account_info"
    return out


def _carry_day_start(prev: Any, snap: dict[str, Any], cet: str) -> dict[str, Any]:
    """`snap` plus FTMO's day anchor: the first equity and balance read on each CET day (FTMO's
    daily loss is measured from the day's start), kept across passes."""
    prev = prev if isinstance(prev, dict) else {}
    out = dict(snap)
    if prev.get("cet_day") == cet and prev.get("day_start_equity") is not None:
        out["day_start_equity"] = prev["day_start_equity"]
        out["day_start_balance"] = prev.get("day_start_balance")
        out["day_start_at"] = prev.get("day_start_at")
    else:
        out["day_start_equity"] = snap.get("equity")
        out["day_start_balance"] = snap.get("balance")
        out["day_start_at"] = snap.get("at") if snap.get("equity") is not None else None
    out["cet_day"] = cet if out["day_start_equity"] is not None else None
    return out


def _canon(login: object) -> object:
    """Fusion r6's one login type (cross_account.norm_login): the terminal's int and the
    declaration's string name one account."""
    return None if login in (None, "") else _xa.norm_login(login)


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
    acct_type = str(doc.get("account_type") or "").strip().lower()
    if acct_type not in ACCOUNT_TYPES:
        return None, {}, ("data/FTMO_LIVE_ACCOUNT.json must declare account_type \"2-step\" or "
                          "\"1-step\" (FTMO's daily loss limit is 5% or 3% by type)")
    acc = mt5.account_info()
    if acc is None:
        return None, {}, "the FTMO terminal did not answer account_info"
    if _canon(getattr(acc, "login", None)) != _canon(doc["login"]) \
            or str(getattr(acc, "server", "")).strip() != str(doc["server"]).strip():
        return None, {}, ("the terminal is on another account than data/FTMO_LIVE_ACCOUNT.json "
                          "declares; nothing is done")
    if int(getattr(acc, "trade_mode", -1)) != want_mode:
        return None, {}, (f"the terminal's trade_mode {getattr(acc, 'trade_mode', None)!r} is not "
                          f"the declared {want_mode}; nothing is done")
    try:
        key = _oco.oco_account_key(getattr(acc, "login", None), getattr(acc, "server", None))
    except _oco.IdentityUnavailable as exc:
        return None, {}, f"gold OCO identity: {exc}"
    return key, {"initial_balance": initial, "trade_mode": want_mode, "account_type": acct_type,
                 "daily_loss_frac": ACCOUNT_TYPES[acct_type],
                 "max_lot": doc.get("max_lot")}, "account bound"


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


def order_risk_usd(mt5: Any, order: Any) -> float | None:
    """The account-currency risk of a resting MAGIC entry to its stop: volume x |price - sl| x
    the contract size. None when any of them is unreadable (the bill is then UNPRICED, never 0)."""
    try:
        vol = float(getattr(order, "volume_current", None) or getattr(order, "volume_initial"))
        dist = abs(float(order.price_open) - float(order.sl))
        contract = float(mt5.symbol_info(SYMBOL).trade_contract_size)
    except (AttributeError, TypeError, ValueError):
        return None
    risk = vol * dist * contract
    return round(risk, 2) if math.isfinite(risk) and risk > 0 and float(order.sl) > 0 else None


def _bill_cancel(mt5: Any, doc: dict[str, Any], st: dict[str, Any], order: Any, *, reason: str,
                 why: str, today: str, now: datetime) -> None:
    """One RAIL_BLOCKED row for a cancelled resting entry, once per window per trading day
    (`st["logged"]["cancel/<window>"]`), billed at the order's own risk -- the pass's planned
    risk when the order's levels cannot be read. Never raises (a trading loop calls it)."""
    try:
        seen = st.setdefault("logged", {})
        slot = f"cancel/{WINDOW}"
        if seen.get(slot) == today:
            return
        usd = order_risk_usd(mt5, order)
        if usd is None:
            usd = doc.get("planned_usd")
        seen[slot] = today
        _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
                 "status": "RAIL_BLOCKED", "rail": RAIL, "reason": reason,
                 "why": f"resting order {int(order.ticket)} cancelled: {why}",
                 "order_id": int(order.ticket),
                 "missed_growth_risk_usd": None if usd is None else round(float(usd), 2)})
        doc.setdefault("billed_cancels", []).append(int(order.ticket))
    except Exception as exc:
        log(f"[{WINDOW}] the cancel bill was not written ({type(exc).__name__}: {exc})")


def _skip(doc: dict[str, Any], st: dict[str, Any], reason: str, why: str, *, today: str,
          now: datetime, missed_usd: float | None = None, alert: bool = False,
          rail: str = RAIL) -> None:
    """A refused (RAIL_BLOCKED) or waiting (SKIPPED) pass, journalled once per reason per day.
    A refusal bills the risk it held back: `missed_usd`, else the pass's planned risk
    (`doc["planned_usd"]`: the ftmo fraction x equity) -- None only when that is unreadable,
    and missed_growth then counts it unpriced (audit v2 must-fix 5)."""
    if missed_usd is None and reason not in ("wait", "already_followed"):
        missed_usd = doc.get("planned_usd")
    doc["skipped"].append({"reason": reason, "why": why})
    if alert:
        doc["alerts"].append(why)
    log(f"{'ALERT ' if alert else ''}[{WINDOW}] not placed ({reason}): {why}")
    seen = st.setdefault("logged", {})
    if seen.get(reason) != today:
        seen[reason] = today
        _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
                 "status": ("SKIPPED" if reason in ("wait", "already_followed")
                            else "RAIL_BLOCKED"), "rail": rail,
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
        if why.startswith("gold OCO identity"):
            doc["alerts"].append(why)
            doc["page"] = _oco.page_identity(LANE, why)
        _write_out(doc, None)
        return doc
    _oco.page_identity(LANE, None)
    doc["account"] = account_snapshot(mt5, now)
    # MARKET WATCH IS TERMINAL STATE (2026-10-22). The armed follower read NO_TICK every pass
    # because XAUUSD was not in the FTMO terminal's Market Watch, and a terminal reset drops it
    # again. Selecting the symbol is idempotent and places nothing.
    select = getattr(mt5, "symbol_select", None)
    if callable(select) and not select(SYMBOL, True):
        log(f"symbol_select({SYMBOL}) refused; the tick read below decides")
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
    if STATE.exists() and not isinstance(st, dict):
        # A torn state is survivable: the history check below is the once-a-day authority.
        doc["state_unreadable"] = "ftmo_follower_state.json is torn; the MAGIC history decides"
    st = st if isinstance(st, dict) else {}
    if st.get("date") != today:
        st = {"date": today, "windows": {}, "requests": st.get("requests") or {},
              "logged": {}, "followed": st.get("followed") or {}, "account": st.get("account")}
    st.setdefault("followed", {})
    st["account"] = _carry_day_start(st.get("account"), doc["account"], cet)
    doc["account"] = st["account"]
    doc.update({"server_time": srv.isoformat(), "hour": round(hour, 3), "trading_date": today})

    # This account's gold state for every other lane, and the claim of any fill here.
    sync = _oco.sync_lane(LANE, key, lambda: _oco.mt5_gold_rows(mt5), date=today,
                          holder="ftmo_follower")
    doc["gold_oco"] = {"published": sync.get("published"), "why": sync.get("why")}

    e8_doc = _read_json(E8_REPORT)
    entry, entry_why = _oco.day_entry(today)
    e8_lane, lane_why = _oco.read_lane("e8", max_age_s=e8_stale_limit_s()[0])
    action, sig, fwhy = follow_decision(e8_doc, entry, entry_why, e8_lane, lane_why,
                                        today=today, now=now)
    doc["follow"] = {"action": action, "why": fwhy, "signal": sig}
    doc["planned_usd"] = _planned_usd(mt5)

    positions = mt5.positions_get(symbol=SYMBOL)
    orders = mt5.orders_get(symbol=SYMBOL)
    book_ok = positions is not None and orders is not None
    positions, orders = list(positions or []), list(orders or [])
    own_pos = [p for p in positions if int(getattr(p, "magic", 0) or 0) == MAGIC]
    own_ord = [o for o in orders if int(getattr(o, "magic", 0) or 0) == MAGIC]

    # ---------------------------------------------------------------- management (armed only)
    w = st["windows"].get(WINDOW) or {}
    end = window_end_hour(WINDOW)
    # A REMOVED OR PAUSED LANE WITHDRAWS ITS RESTING ENTRIES (2026-10-28, ticket 111616773):
    # ftmo was taken out of GOLD_OCO_MODE's lanes at 07:06Z, the gate placed nothing more, and
    # the SELL LIMIT already resting filled before its 10:00Z self-cancel -- the cross-firm copy
    # of E8's short that the removal was meant to stop. So the lane's own state is checked
    # FIRST, and its removal is sent even when unarmed (a cancel opens nothing).
    # Only a positive reading withdraws: an unreadable mode file keeps the orders and says
    # UNMEASURED (v14 audit MF1).
    withdraw, unmeasured = _cancel_req.withdraw_check(LANE, armed)
    if unmeasured is not None:
        doc["withdraw_unmeasured"] = unmeasured
        log(f"[{WINDOW}] lane withdraw UNMEASURED: {unmeasured}")
    if withdraw is not None and own_ord:
        doc["withdrawn"] = withdraw
    for o in own_ord:
        why_cancel = None
        if withdraw is not None:
            why_cancel = withdraw
        elif action != "follow":
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
        if armed or withdraw is not None:
            try:
                res = _send(mt5, st, {"action": mt5.TRADE_ACTION_REMOVE, "order": int(o.ticket),
                                      "magic": MAGIC, "comment": COMMENT}, cet=cet,
                            essential=True)
                act["ok"] = getattr(res, "retcode", None) in (10008, 10009)
                if act["ok"] and withdraw is not None:
                    # GONE IS CONFIRMED (v14 audit): the venue must no longer hold the order.
                    still = mt5.orders_get(symbol=SYMBOL)
                    act["ok"] = still is not None and not any(
                        int(getattr(x, "ticket", -1)) == int(o.ticket) for x in still)
                    if not act["ok"]:
                        act["why"] += "; done retcode but the order is still listed (or unread)"
            except Exception as exc:
                act["why"] += f"; FAILED {type(exc).__name__}: {exc}"[:160]
        else:
            act["shadow"] = True
        log(f"[{WINDOW}] cancel resting order {o.ticket}: {act['why']} -> {act.get('ok')}")
        doc["actions"].append(act)
        if act["ok"] and withdraw is not None:
            # billed per order (not once a day): each withdrawn entry is risk the lane held back
            try:
                usd = order_risk_usd(mt5, o)
            except Exception:
                usd = None
            if usd is None:
                usd = doc.get("planned_usd")
            _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
                     "status": "RAIL_BLOCKED", "rail": RAIL, "reason": _cancel_req.WITHDRAWN,
                     "why": f"resting order {int(o.ticket)} cancelled: {withdraw}",
                     "order_id": int(o.ticket),
                     "missed_growth_risk_usd": None if usd is None else round(float(usd), 2)})
        elif act["ok"] and why_cancel != "the asia window's session is over":
            # THE CANCEL IS A REFUSAL TOO (OCO v2s, audit v2r MF-B): an entry withdrawn because
            # E8's state is stale, unreadable or no longer shows the fill (or the order is
            # against E8's direction) is risk the lane held back. The "one order" step below
            # writes nothing while an own order or position exists, so the bill is written HERE:
            # one RAIL_BLOCKED row per window per day, carrying the cancelled order's own risk.
            _bill_cancel(mt5, doc, st, o, reason=("cancel_" + action if action != "follow"
                                                  else "cancel_against_direction"),
                         why=why_cancel, today=today, now=now)
    # THE DESK'S OWN LEVER (mt5desk.cancel_pending, 2026-10-28): a resting order of this lane
    # that data/CANCEL_PENDING.json asks to withdraw is removed here, never by a person in the
    # terminal. Only this lane's MAGIC orders are candidates; nothing is opened or closed.
    gone = {a["order"] for a in doc["actions"] if a.get("act") == "cancel" and a.get("ok")}
    # each order's own setup time bounds an `all` request (v7 audit MF6)
    todo, notes = _cancel_req.due(
        LANE, {int(o.ticket): _cancel_req.server_time_utc(getattr(o, "time_setup", None))
               for o in own_ord if int(o.ticket) not in gone}, now=now)
    by_ticket = {int(o.ticket): o for o in own_ord}
    if notes:
        doc["cancel_request_notes"] = notes
    for c in todo:
        act = {"act": "cancel_requested", "order": c["ticket"], "why": c["why"], "ok": False}
        if armed:
            try:
                res = _send(mt5, st, {"action": mt5.TRADE_ACTION_REMOVE, "order": c["ticket"],
                                      "magic": MAGIC, "comment": COMMENT}, cet=cet,
                            essential=True)
                act["ok"] = getattr(res, "retcode", None) in (10008, 10009)
            except Exception as exc:
                act["why"] += f"; FAILED {type(exc).__name__}: {exc}"[:160]
            _cancel_req.record(LANE, c["request"], c["ticket"], act["ok"], now=now)
            if act["ok"]:  # a withdrawn entry is a refusal too (Rule 1), billed per order
                try:
                    usd = order_risk_usd(mt5, by_ticket[c["ticket"]])
                except Exception:
                    usd = None
                if usd is None:
                    usd = doc.get("planned_usd")
                _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW,
                         "lane": LANE, "status": "RAIL_BLOCKED", "rail": RAIL,
                         "reason": _cancel_req.RAIL, "why": c["why"], "order_id": c["ticket"],
                         "missed_growth_risk_usd": None if usd is None else round(float(usd), 2)})
        else:
            act["shadow"] = True
        log(f"[{WINDOW}] requested cancel of resting order {c['ticket']}: {act['why']} -> "
            f"{act.get('ok')}")
        doc["actions"].append(act)
    # A FILL AGAINST THE DAY'S DIRECTION IS CLOSED AT ONCE (gold_oco v2, must-fix 6).
    _rows = [{"p": p, "id": int(p.ticket),
              "side": "long" if int(getattr(p, "type", -1)) == 0 else "short",
              "opened_date": _oco.trading_date(float(p.time))
              if isinstance(getattr(p, "time", None), (int, float)) else None}
             for p in own_pos]
    _flat = {r["id"] for r in _oco.positions_to_flatten(entry if entry_why is None else None,
                                                        _rows, date=today)}
    for p in own_pos:
        side = "long" if int(getattr(p, "type", -1)) == 0 else "short"
        if int(p.ticket) in _flat or hour >= CLOSE_HOUR:
            act = {"act": "close", "position": int(p.ticket), "ok": False,
                   "why": ("it is against today's gold direction (flattened at once)"
                           if int(p.ticket) in _flat else "the gold book's close hour")}
            if int(p.ticket) in _flat:
                doc["alerts"].append(f"FTMO gold {side} position against today's direction: "
                                     f"flattened")
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

    # ---------------------------------------------------------------- the fills ledger
    doc["fills_ledger"] = record_fills(mt5, key, {int(p.ticket) for p in positions}, now)
    if doc["fills_ledger"].get("written"):
        log(f"prop fills ledger: {doc['fills_ledger']['written']} closed FTMO position(s)")

    # ---------------------------------------------------------------- the one order
    placed_today = WINDOW in st["windows"]
    if placed_today or own_ord or own_pos:
        pass
    elif action != "follow" or sig is None:
        _skip(doc, st, "wait" if action == "wait" else action, fwhy, today=today, now=now)
    elif str(sig["e8_position_id"]) in st["followed"]:
        pid_s = str(sig["e8_position_id"])
        _skip(doc, st, "already_followed",
              f"E8 position {pid_s} was already followed ({st['followed'][pid_s]})",
              today=today, now=now)
    elif (spent := history_spent(mt5, today, now))[0] is not False:
        _skip(doc, st, "history_unreadable" if spent[0] is None else "already_followed",
              spent[1], today=today, now=now)
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
    # THE ADOPTER'S HOLD (libs/ops/new_risk_hold): no new follow while a failed release is rolled
    # back and not yet proved healthy. Management of an open follow ran before this call.
    from libs.ops import new_risk_hold as _nrh
    if (_hold := _nrh.reason()) is not None:
        _skip(doc, st, "adopt_hold", _hold, today=today, now=now, alert=True)
        return
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
    # THE DECISION AND THE SEND ARE ONE, UNDER THE PLACEMENT LOCK (OCO v2s, audit v2r SF-2):
    # the gate, its live re-read of every lane, the sizing and the send run while no other lane
    # can place or publish -- so in "oco" mode no other account's fill can land between this
    # lane's reading and its order. The lane's own book is re-read and republished under it too.
    with _xa.placement_lock(f"ftmo_follower:{WINDOW}") as locked:
        if not locked:
            _skip(doc, st, "gold_oco", "gold OCO: the placement lock is held by another lane; "
                                       "fail closed (retried next pass)", today=today, now=now)
            return
        _place_locked(mt5, st, doc, sig, key=key, decl=decl, armed=armed, today=today, now=now,
                      hour=hour, cet=cet, cet_midnight=cet_midnight, tick=tick)


def _place_locked(mt5: Any, st: dict[str, Any], doc: dict[str, Any], sig: dict[str, Any], *,
                  key: str, decl: dict[str, Any], armed: bool, today: str, now: datetime,
                  hour: float, cet: str, cet_midnight: datetime, tick: Any) -> None:
    """`_place`'s decision and send. Called ONLY under `cross_account.placement_lock`."""
    side = sig["side"]
    live_pos, live_ord = mt5.positions_get(symbol=SYMBOL), mt5.orders_get(symbol=SYMBOL)
    if live_pos is None or live_ord is None:
        _skip(doc, st, "book_unreadable", "the FTMO terminal did not answer positions/orders "
                                          "under the placement lock", today=today, now=now)
        return
    against = [int(getattr(x, "ticket", 0) or 0) for x in [*live_pos, *live_ord]
               if _side_of_type(int(getattr(x, "type", -1))) not in (None, side)]
    if against:
        _skip(doc, st, "opposite_exposure", (f"FTMO holds or rests gold against E8's {side} "
                                             f"({against}); this lane never opens the other way"),
              today=today, now=now, alert=True)
        return
    resync = _oco.sync_lane(LANE, key, lambda: _oco.mt5_gold_rows(mt5), date=today,
                            holder="ftmo_follower:place")
    if not resync.get("published"):
        _skip(doc, st, "gold_oco", f"gold OCO: this lane's gold state was not republished under "
                                   f"the lock ({resync.get('why')}); fail closed",
              today=today, now=now)
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
    cap, cap_why = lot_cap(equity, float(sig["price"]), contract, vstep=vstep,
                           declared=decl.get("max_lot"))
    if lot > cap:
        clipped_usd = (lot - cap) * dist * contract
        capped = cap if cap >= vmin else 0.0
        _record({"at": now.isoformat(timespec="seconds"), "window": WINDOW, "lane": LANE,
                 "status": "RAIL_BLOCKED", "rail": LOT_CAP_RAIL, "reason": "lot_cap",
                 "why": f"lot {lot:g} clipped to {capped:g} ({cap_why}) at a {dist:.2f} stop",
                 "lot_uncapped": lot, "lot": capped,
                 "missed_growth_risk_usd": round(want_usd if not capped > 0 else clipped_usd,
                                                 2)})
        log(f"[{WINDOW}] lot cap: {lot:g} -> {capped:g} ({cap_why})")
        doc["lot_cap"] = {"uncapped": lot, "lot": capped, "why": cap_why}
        if not capped > 0:
            _skip(doc, st, "lot_cap", f"the lot cap ({cap_why}) is below the minimum lot",
                  today=today, now=now, missed_usd=want_usd, rail=LOT_CAP_RAIL)
            return
        lot = capped
    risk = trade_risk(lot, dist, contract)
    try:
        start = day_start_balance(mt5, balance, cet_midnight, now,
                                  server_epoch=float(tick.time))
    except Exception as exc:
        _skip(doc, st, "loss_guard", f"today's starting balance is unmeasurable ({exc})",
              today=today, now=now, missed_usd=want_usd)
        return
    ok, gwhy = loss_guard(float(decl["initial_balance"]), start, equity, risk,
                          daily_frac=float(decl.get("daily_loss_frac") or DAILY_LOSS_FRAC))
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
    # WRITE-AHEAD: the follow is marked spent, and the state written atomically, BEFORE the send,
    # so a crash or a lost reply can never send a second order for this E8 fill.
    st["followed"][str(sig["e8_position_id"])] = row["at"]
    if len(st["followed"]) > FOLLOWED_KEEP:
        st["followed"] = dict(sorted(st["followed"].items(), key=lambda kv: str(kv[1]))
                              [-FOLLOWED_KEEP:])
    st["windows"][WINDOW] = {"placed_at": row["at"], "placed_hour": hour, "side": side,
                             "kind": kind, "order_id": None, "lot": lot,
                             "e8_position_id": sig["e8_position_id"], "status": "SENDING"}
    try:
        _atomic_write(STATE, json.dumps(st, indent=1, default=str))
    except OSError as exc:
        row.update({"status": "REJECTED", "why": f"state write-ahead failed ({exc}); not sent"})
        _record(row)
        log(f"[{WINDOW}] NOT SENT: {row['why']}")
        return
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
    # The resting order is in this lane's published gold state before the lock is released.
    after = _oco.sync_lane(LANE, key, lambda: _oco.mt5_gold_rows(mt5), date=today,
                           holder="ftmo_follower:sent")
    doc["gold_oco"]["republished_after_send"] = bool(after.get("published"))


def _atomic_write(path: Path, text: str) -> None:
    """tmp beside `path`, flush, fsync, os.replace -- retried on PermissionError, which Windows
    raises while a reader holds the destination open. RAISES OSError when it cannot land."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
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
            time.sleep(0.1)


def _planned_usd(mt5: Any) -> float | None:
    """The pass's planned risk: the ftmo block's gold_asia fraction x equity, or None."""
    try:
        frac = float((load_cert_book(CERT_BOOK_FILE, "ftmo") or {}).get(CERT_KEY) or 0.0)
        equity = float(mt5.account_info().equity)
    except Exception:
        return None
    return round(frac * equity, 2) if frac > 0 and equity > 0 else None


def _write_out(doc: dict[str, Any], st: dict[str, Any] | None) -> None:
    try:
        if st is not None:
            _atomic_write(STATE, json.dumps(st, indent=1, default=str))
            doc["state"] = st
        _atomic_write(OUT, json.dumps(doc, indent=1, default=str))
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
