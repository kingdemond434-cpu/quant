"""E8 GOLD WINDOWS -- the desk's gold book, on the prop account.

PRINCIPAL 2026-09-16: "replace E8's book with the gold sleeves we use now". The evidence was
one-sided. Live on the MT5 account the gold windows were the only mechanism with a record
(gold_asia 9 trades +117 EUR, gold_london_am 7 trades +52, gold_afternoon 5 trades +10, 67%
wins, mean +0.36R) while E8 had lost most of its 911 USD on the `discovered` forex sleeves that
are now banned, and its remaining forex certificates had no live proof either way.

WHAT THIS IS. The MT5 gateway's bracket lane, on TradeLocker: at each window's signal hour the
day's range is read from the same XAUUSD H1 bars the gateway reads (the terminal on this box;
server clock, exactly as `decision_core.GOLD_WINDOWS` is written), `bracket_from_bars` builds
the same buy-stop/sell-stop pair with the same ATR-floored stop and the same RR target, and the
pair is sent as two resting stop orders with their stop and target attached. One fill cancels
the other leg (OCO); an unfilled pair is cancelled after BRACKET_TTL_HOURS; positions are closed
at CLOSE_HOUR and any resting leg cancelled at CANCEL_HOUR -- the gold book's own end of day.

WINDOWS RUN IN PARALLEL, AND ONLY THE OPPOSING LEG STANDS DOWN. While an XAU position is open,
the due window still places the leg that AGREES with it and skips only the one that would trade
against it (`book_direction` / `OPPOSING_LEG`); an unreadable position side defers the whole
bracket, as does an unreadable position book. The measurement behind that rule, and the cost of
deferring both legs instead, is recorded at the placement block in `run`.

SIZED FOR THIS ACCOUNT, NOT COPIED FROM THE OTHER. E8 risks RISK_FRAC of equity per trade
(`docs/PROP_FIRM_E8.md`: 0.50%) against the leg's own stop distance, through the E8 executor's
`lot_for_risk`, which reads the venue's own contract size.

SHADOW UNLESS data/E8_GOLD_ARMED EXISTS. Unarmed passes log the exact orders they would send.
The daily guard `e8_guard_state.json` (written by the E8 executor) stands new placements down
when it says so; management of what is already open never stands down.

    python prop/e8_gold.py            one pass, shadow unless armed
    python prop/e8_gold.py --armed    one pass, armed for this pass only
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import position_manager as _pm  # noqa: E402
from mt5desk.decision_core import (  # noqa: E402
    ATR_N,
    BRACKET_TTL_HOURS,
    CANCEL_HOUR,
    CLOSE_HOUR,
    GOLD_WINDOWS,
    OPPOSING_LEG,
    atr_last,
    book_direction,
    bracket_from_bars,
    h1_frame,
    window_end_hour,
    window_session_ended,
)
from mt5desk.kelly_sizing import load_kelly_survival  # noqa: E402

SYMBOL = "XAUUSD"
#: Per-trade risk on the prop account, as a fraction of equity (docs/PROP_FIRM_E8.md).
RISK_FRAC = 0.005
#: The survival-constrained growth solve (research/kelly_survival.py; principal 2026-09-30:
#: "maximum aggressiveness within survival"). Its `e8` block names each window's risk fraction:
#: the fastest median pass whose P(floor) + P(daily breach) stays under EPS_STOP. Absent, stale
#: or not OK -> every window keeps RISK_FRAC, exactly as before the solve existed.
KELLY_FILE = DESK / "reports" / "KELLY_SURVIVAL.json"
STATE = DESK / "data" / "e8_gold_state.json"
OUT = DESK / "reports" / "E8_GOLD.json"
INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
ARMED_MARKER = DESK / "data" / "E8_GOLD_ARMED"
GUARD = DESK / "data" / "e8_guard_state.json"
LOG = DESK / "logs" / "e8_gold.log"
TAG = "E8gold"
#: XAUUSD's price grid, used only when the terminal cannot state `trade_tick_size`.
STOP_STEP = 0.01
# A LEG THE VENUE DROPPED IS RETRIED, NOT FORGOTTEN (2026-09-30). TradeLocker answered a send with
# an HTML page on 2026-09-17, 09-22 and 09-28; the pass recorded REJECTED, wrote the window as
# placed, and `plan` never looked at it again, so each of those days traded half a bracket. A
# failed leg now rides in its window's `failed` block and is re-sent on each 5-minute pass while
# its session is open, its twin has not filled and the level is still ahead of the price.
MAX_LEG_RETRIES = 12
# How close a resting venue order must sit to a failed leg's level to be that leg: the send that
# "failed" may have reached the venue before the reply broke, and sending again would double it.
LEG_MATCH_TOL = 0.05
#: How far BEFORE the failed send an order's own timestamp may sit and still be that send. The
#: venue stamps orders on the broker clock (UTC+2/+3), so a real UTC send time sits up to three
#: hours earlier than the stamp of the order it created; anything older is some other order.
LEG_MATCH_WINDOW_MS = 10 * 60 * 1000
XAU_OZ_PER_LOT = 100.0  # fallback for a leg journalled before risk_usd was kept on it
#: With no own order to measure the venue clock against, the send-time bound widens to this: a
#: box clock that runs fast must not hide a send that landed. The other fields (instrument, qty,
#: side, level, not a journal id) still have to agree, and a fill older than this still cannot.
UNMEASURED_SKEW_MS = 24 * 3600 * 1000
#: The growth-governance rail the unowned-position block is billed under (libs/portfolio/rails).
UNOWNED_BLOCK_RAIL = "e8_unowned_position_block"
# Terminal reconnection (2026-09-30: ~70 min of "No IPC connection" in one day). Each attempt
# drops the dead IPC handle and re-attaches; the waits are seconds inside a 5-minute pass.
MT5_RETRY_WAITS_S = (0.0, 2.0, 5.0, 15.0, 30.0)


def log(msg: str) -> None:
    line = f"{datetime.now(tz=UTC).isoformat(timespec='seconds')} {msg}"
    print(line)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ pure decisions

def window_risk(name: str, kelly: dict[str, float] | None) -> tuple[float, str]:
    """(risk fraction of equity for window `name`, where it came from). Pure.

    The solve's number when it holds one for this window -- 0 means the window stands aside
    because every size it could send lowers the pass rate or breaks survival -- else RISK_FRAC.
    """
    if kelly is not None and name in kelly:
        return float(kelly[name]), "kelly_survival"
    return RISK_FRAC, "policy RISK_FRAC"


def plan(df: Any, hour: float, state: dict, *, tick_size: float = 0.01,
         stops_level: int = 0) -> list[dict]:
    """Windows due NOW: not yet placed today, at or past their signal hour, before the cancel
    hour, with a formed range. Each entry carries the bracket spec exactly as the gateway
    would send it. Pure: bars, clock and state in, decisions out."""
    out: list[dict] = []
    windows = state.get("windows") or {}
    for name, sig_hour, rng in GOLD_WINDOWS:
        if name in windows:
            continue
        if hour < float(sig_hour) or hour >= CANCEL_HOUR:
            continue
        if window_session_ended(name, hour):
            # A late pass (restart, IPC outage) must not send a bracket off a range its own
            # session already left: 2026-09-21 all three windows went out at 20:29 server in one
            # pass, and 2026-09-24 a 3h-late london_am sat on the afternoon's level and both
            # stopped in the same second (-950 USD). See decision_core.window_session_ended.
            continue
        built = bracket_from_bars(df, rng, sig_hour, tick_size, stops_level)
        if built is None:
            continue
        hi, lo, spec = built
        out.append({"window": name, "hi": hi, "lo": lo, "spec": spec, "sig_hour": sig_hour})
    return out


def leg_is_legal(side: str, price: float, bid: float, ask: float) -> tuple[bool, str]:
    """A buy stop must rest above the ask and a sell stop below the bid, or the venue would
    fill it at market on arrival -- a different trade from the certified breakout."""
    if side == "buy_stop" and price <= ask:
        return False, f"buy stop {price:.2f} is at or below the ask {ask:.2f}"
    if side == "sell_stop" and price >= bid:
        return False, f"sell stop {price:.2f} is at or above the bid {bid:.2f}"
    return True, ""


def retry_decisions(state: dict, hour: float, bid: float, ask: float, filled: dict[int, int],
                    blocked: str | None = None) -> list[dict]:
    """What to do with each leg the venue failed to take: {"act": "retry"|"abandon"|"hold"}.

    A leg is re-sent only while the certified trade still exists: its window's session is open
    (the same `window_session_ended` rule placement uses), the day is before the cancel hour, the
    other leg of the bracket has not filled (the OCO would cancel it at once), and the level is
    still AHEAD of the price -- a buy stop at or below the ask means the breakout already went
    without us, and sending it now would be a market fill, a different trade. A leg that would
    trade against an open position is held, never abandoned: the book may be flat next pass.
    Pure, so the rules are testable without a venue.
    """
    out: list[dict] = []
    for name, w in (state.get("windows") or {}).items():
        failed = w.get("failed") or {}
        if not failed or name.startswith("carried:"):
            continue
        twin_filled = w.get("position_id") is not None or any(
            leg.get("id") is not None and int(leg["id"]) in filled
            for leg in (w.get("orders") or {}).values())
        for side, leg in failed.items():
            base = {"window": name, "side": side, "leg": leg}
            if twin_filled:
                out.append({**base, "act": "abandon", "why": "the other leg filled"})
            elif hour >= CANCEL_HOUR or window_session_ended(name, hour):
                out.append({**base, "act": "abandon", "why": "the window's session is over"})
            elif int(leg.get("attempts") or 0) >= MAX_LEG_RETRIES:
                out.append({**base, "act": "abandon",
                            "why": f"{MAX_LEG_RETRIES} sends failed"})
            elif side == blocked:
                out.append({**base, "act": "hold",
                            "why": "would trade against an open XAU position"})
            else:
                legal, why = leg_is_legal(side, float(leg["price"]), float(bid), float(ask))
                out.append({**base, "act": "retry"} if legal else
                           {**base, "act": "abandon", "why": f"price already through: {why}"})
    return out


def _order_ms(o: dict) -> int | None:
    for k in ("createdDate", "created", "lastModified", "openDate", "time"):
        v = o.get(k)
        try:
            if v is not None and int(v) > 0:
                return int(v)
        except (TypeError, ValueError):
            continue
    return None


def _iso_ms(at: Any) -> int:
    """Milliseconds since the epoch of an ISO stamp; an unreadable stamp reads as NOW-FAR-FUTURE
    so nothing older can match it (fail closed: no adoption without a known send time)."""
    try:
        return int(datetime.fromisoformat(str(at)).timestamp() * 1000)
    except (TypeError, ValueError):
        return 2**62


def venue_clock_skew_ms(journal: list[dict], rows: list[dict]) -> int | None:
    """How far the venue's order stamps run ahead of this box's clock, in ms, measured on the
    lane's OWN sends: each SENT journal row's box time against the venue's stamp on that order.
    The median, so one late-acknowledged send cannot move it. None when no own order is visible.

    WHY (audit 2026-09-30): the send-time bound compared the box clock with the venue's stamp,
    so a box running 15 minutes fast refused a send that had landed and sent it again. Measured
    this way the offset carries the box's skew AND whatever epoch the venue stamps in.
    """
    stamp = {int(o["id"]): ms for o in rows if o.get("id") is not None
             and (ms := _order_ms(o)) is not None}
    diffs = sorted(stamp[int(r["order_id"])] - _iso_ms(r.get("at")) for r in journal
                   if r.get("status") == "SENT" and r.get("order_id") is not None
                   and int(r["order_id"]) in stamp and _iso_ms(r.get("at")) < 2**62)
    return diffs[len(diffs) // 2] if diffs else None


def matching_resting_order(orders: list[dict], side: str, price: float, known_ids: set[int],
                           *, lot: float, instrument_id: int, since_ms: int) -> int | None:
    """The id of a venue order that IS this leg, if the failed send landed anyway.

    EVERY FIELD MUST AGREE, because a wrong match is worse than none (audit 2026-09-30: matching
    on side and level alone adopted a 40-hour-old 7-lot fill on ANOTHER instrument as this leg,
    and management then cancelled the live twin). So an order matches only when it is on this
    instrument, on this side, at this trigger level within LEG_MATCH_TOL, for this quantity, was
    created no earlier than LEG_MATCH_WINDOW_MS before the failed send, and is not an id the lane
    already owns -- today's legs AND every id in the intents journal, so yesterday's own leg
    cannot come back as today's after the rollover empties the windows. A row missing any of
    those fields does not match.
    """
    want = "buy" if side == "buy_stop" else "sell"
    for o in orders:
        oid = o.get("id")
        if oid is None or int(oid) in known_ids:
            continue
        if str(o.get("side") or "").lower() != want:
            continue
        try:
            if int(o.get("tradableInstrumentId") or 0) != int(instrument_id) or not instrument_id:
                continue
            qty = o.get("qty", o.get("quantity"))
            if qty is None or abs(float(qty) - float(lot)) > max(0.005, 0.01 * float(lot)):
                continue
            level = o.get("stopPrice") or o.get("price")
            if level is None or abs(float(level) - float(price)) > LEG_MATCH_TOL:
                continue
        except (TypeError, ValueError):
            continue
        made = _order_ms(o)
        if made is None or made < since_ms - LEG_MATCH_WINDOW_MS:
            continue
        return int(oid)
    return None


def position_since_failure(positions: list[dict], side: str, first_at: Any, state: dict,
                           filled: dict[int, int]) -> bool:
    """Is there an open XAU position on this leg's side, opened at or after the failed send, that
    no window or carried row owns and no order of ours opened? Such a position may be the
    "failed" send itself, filled; sending again would double it. Unknown open time counts."""
    want = "buy" if side == "buy_stop" else "sell"
    rows = [w for bucket in ("windows", "carried") for w in (state.get(bucket) or {}).values()]
    owned = {int(w["position_id"]) for w in rows if w.get("position_id") is not None}
    # Positions opened by orders this lane KNOWS it sent; any other fill may be the lost send.
    known = {int(leg["id"]) for w in rows for leg in (w.get("orders") or {}).values()
             if leg.get("id") is not None}
    ours = {int(pid) for oid, pid in filled.items() if int(oid) in known}
    try:
        since_ms = int(datetime.fromisoformat(str(first_at)).timestamp() * 1000)
    except (TypeError, ValueError):
        since_ms = 0
    for p in positions:
        if str(p.get("side") or "").lower() != want:
            continue
        pid = int(p.get("id") or 0)
        if pid in owned or pid in ours:
            continue
        opened = int(p.get("openDate") or 0)
        if opened == 0 or opened >= since_ms:
            return True
    return False


def manage_actions(state: dict, hour: float, open_ids: set[int],
                   filled: dict[int, int], position_ids: set[int]) -> list[dict]:
    """What to do with today's windows, given the venue's resting order ids (`open_ids`), the
    map of filled order id -> position id (`filled`) and the XAUUSD position ids still open.

    Actions: {"act": "record_position"|"oco_cancel"|"ttl_cancel"|"close"|"eod_cancel", ...}.
    Pure, so the OCO and end-of-day rules are testable without a venue.
    """
    acts: list[dict] = []
    for name, w in (state.get("windows") or {}).items():
        legs = w.get("orders") or {}
        ids = {side: int(o["id"]) for side, o in legs.items() if o.get("id")}
        pos = w.get("position_id")
        if pos is None:
            for side, oid in ids.items():
                if oid in filled:
                    pos = int(filled[oid])
                    acts.append({"act": "record_position", "window": name, "side": side,
                                 "order_id": oid, "position_id": pos})
                    break
        if pos is not None:
            for side, oid in ids.items():
                if oid in open_ids and (oid not in filled):
                    acts.append({"act": "oco_cancel", "window": name, "side": side,
                                 "order_id": oid})
            if hour >= CLOSE_HOUR and int(pos) in position_ids:
                acts.append({"act": "close", "window": name, "position_id": int(pos)})
            continue
        resting = [oid for oid in ids.values() if oid in open_ids]
        if not resting:
            continue
        placed_hour = float(w.get("placed_hour") or 0.0)
        # THE BRACKET DIES WITH ITS SESSION, as the Fusion gateway's `bracket_deadline` has it.
        # A flat 6h TTL kept a london_am leg resting four hours into the afternoon, where it sat
        # beside the afternoon's own leg at almost the same level (2026-09-24: 4250.93 and
        # 4252.19, both filled at 15:01Z, both stopped). The flat TTL stays as the fallback for a
        # window the table does not know.
        end = window_end_hour(name)
        if hour >= CANCEL_HOUR:
            acts.extend({"act": "eod_cancel", "window": name, "order_id": oid} for oid in resting)
        elif (end is not None and hour >= end) or hour - placed_hour >= BRACKET_TTL_HOURS:
            acts.extend({"act": "ttl_cancel", "window": name, "order_id": oid} for oid in resting)
    return acts


def gold_positions(rows: list[dict], instrument_id: int) -> list[dict]:
    """The venue's open XAU positions, with no guess from comments or local state."""
    return [p for p in rows
            if int(p.get("tradableInstrumentId") or 0) == int(instrument_id)]


def _window_for_position(state: dict, position_id: int) -> tuple[str, dict] | None:
    for name, row in {**(state.get("carried") or {}), **(state.get("windows") or {})}.items():
        if row.get("position_id") is not None and int(row["position_id"]) == int(position_id):
            return str(name), row
    return None


def rollover_state(state: dict, today: str) -> dict:
    """The state a new server day starts from: no windows, every still-open position carried.

    THE ROLLOVER LOST POSITIONS (2026-09-29). It carried only yesterday's WINDOWS that had a
    recorded `position_id`, so (1) a position carried INTO yesterday was dropped at the next
    rollover, and (2) a leg that filled after the last pass of the day -- its `position_id` not
    yet recorded -- was dropped outright. Either way the ratchet, the break-even floor and the
    close hour stopped managing a live position. (1) is fixed here: every open carried row rides
    forward. (2) is fixed by `readopt_positions`, which re-derives ownership from the venue.
    """
    if state.get("date") == today:
        return state
    old_date = str(state.get("date") or "")
    carried = {n: w for n, w in (state.get("carried") or {}).items()
               if w.get("position_id") is not None and not w.get("closed")}
    for n, w in (state.get("windows") or {}).items():
        if n.startswith("carried:") or w.get("closed") or w.get("position_id") is None:
            continue
        carried[f"{old_date}/{n}" if n in carried else n] = w
    return {"date": today, "windows": {}, "carried": carried}


def own_entry_orders(journal: list[dict], state: dict) -> dict[int, dict]:
    """Every entry order THIS lane sent, by venue order id -> its leg (window, side, levels).

    TradeLocker has no magic number and this adapter sends no comment, so the desk's own mark
    on the venue is the order id it was handed at the send. Read from the intents journal (which
    survives the rollover and a lost state file) and from the state's own legs.
    """
    own: dict[int, dict] = {}
    for row in journal:
        if row.get("status") == "SENT" and row.get("order_id") is not None:
            own[int(row["order_id"])] = {k: row.get(k) for k in
                                         ("window", "side", "price", "sl", "tp", "lot")}
    for bucket in ("carried", "windows"):
        for name, w in (state.get(bucket) or {}).items():
            for side, leg in (w.get("orders") or {}).items():
                if leg.get("id") is not None:
                    own.setdefault(int(leg["id"]), {"window": name, "side": side,
                                                    **{k: leg.get(k) for k in
                                                       ("price", "sl", "tp", "lot")}})
    return own


def _today_leg_ids(state: dict) -> set[int]:
    return {int(leg["id"]) for n, w in (state.get("windows") or {}).items()
            if not n.startswith("carried:")
            for leg in (w.get("orders") or {}).values() if leg.get("id") is not None}


def readopt_positions(state: dict, filled: dict[int, int], position_ids: set[int],
                      own: dict[int, dict]) -> list[dict]:
    """Adopt into `state["carried"]` every open XAU position one of OUR entry orders opened
    that no window maps. Mutates `state`; returns one `readopt` action per adoption.

    Today's own legs are excluded: a fill this pass is recorded on its window by
    `manage_actions`, and adopting it twice would schedule two closes for one position.
    """
    today = _today_leg_ids(state)
    by_pos: dict[int, int] = {}
    for oid, pid in filled.items():
        if oid in own and oid not in today:
            by_pos.setdefault(int(pid), int(oid))
    acts: list[dict] = []
    for pid in sorted(position_ids):
        if _window_for_position(state, pid) is not None or pid not in by_pos:
            continue
        oid = by_pos[pid]
        leg = own[oid]
        key = f"readopted:{pid}"
        state.setdefault("carried", {})[key] = {
            "window": leg.get("window"), "readopted": True, "position_id": pid,
            "orders": {str(leg.get("side")): {"id": oid, **{k: leg.get(k) for k in
                                                            ("price", "sl", "tp", "lot")}}}}
        acts.append({"act": "readopt", "window": key, "position_id": pid, "order_id": oid})
    return acts


def stale_entry_orders(state: dict, open_ids: set[int], own: dict[int, dict]) -> list[int]:
    """Our own entry orders still resting at the venue that no window of TODAY owns.

    GTC LEGS OUTLIVED THE DAY (2026-09-29). Cancellation (OCO, TTL, end of day) walks today's
    windows only, and the rollover empties them -- so a GTC leg left resting across midnight was
    never cancelled again and could fill a day later, outside any window, unmanaged. Only ids
    this lane itself sent qualify: the venue's protective stop/target orders and anything a
    human placed are never touched.
    """
    today = _today_leg_ids(state)
    return sorted(oid for oid in open_ids if oid in own and oid not in today)


def trail_decision(position: dict, window: dict, bars: Any, current_stop: float,
                   *, cost_per_unit: float = 0.0, spread: float = 0.0
                   ) -> _pm.RatchetDecision | None:
    """The same H1 stop ratchet the Fusion gold gateway runs, pure for tests.

    TradeLocker and Fusion timestamps are both broker-clock epochs.  Filtering the already-read
    positional bar history against ``openDate`` therefore avoids the UTC/server offset bug that
    disabled Fusion management for whole trades.
    """
    import pandas as pd
    side = 1 if str(position.get("side") or "").lower() == "buy" else -1
    leg_name = "buy_stop" if side == 1 else "sell_stop"
    leg = (window.get("orders") or {}).get(leg_name) or {}
    entry = float(position.get("avgPrice") or leg.get("price") or 0.0)
    original_sl = float(leg.get("sl") or 0.0)
    dist = abs(entry - original_sl)
    opened_ms = int(position.get("openDate") or 0)
    if not (entry > 0 and current_stop > 0 and dist > 0 and opened_ms > 0):
        return None
    opened = pd.Timestamp(opened_ms, unit="ms", tz="UTC").floor("h")
    since = bars[bars.index >= opened]
    if len(since) < 2 or len(bars) < ATR_N + 1:
        return None
    atr = atr_last(bars)
    if not (atr > 0):
        return None
    extreme, stalled = _pm.extreme_and_stall(
        highs=[float(x) for x in since["high"]],
        lows=[float(x) for x in since["low"]], side=side)
    return _pm.ratchet(entry=entry, current_stop=float(current_stop), stop_distance=dist,
                       extreme=extreme, atr=atr, side=side, bars_since_extreme=stalled,
                       cost_per_unit=float(cost_per_unit), spread=max(0.0, float(spread)))


# ------------------------------------------------------------------ the pass

def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


def _journal_rows(limit: int = 5000) -> list[dict]:
    """The last `limit` rows of the intents journal; unreadable -> none (no adoption, no cancel)."""
    try:
        lines = INTENTS.read_text(encoding="utf-8").splitlines()[-limit:]
    except OSError:
        return []
    rows: list[dict] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _record(row: dict[str, Any]) -> None:
    try:
        INTENTS.parent.mkdir(parents=True, exist_ok=True)
        with INTENTS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except OSError:
        pass


def run(venue: Any, mt5: Any, *, armed: bool = False) -> dict[str, Any]:
    """One pass. `venue` is a connected TradeLockerVenue; `mt5` the MetaTrader5 module (bars
    and the server clock, read exactly as the gateway reads them)."""
    from prop.e8_executor import E8_ROUND_TRIP_PER_PRICE_UNIT, _quantise, lot_for_risk

    now = datetime.now(tz=UTC)
    doc: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "armed": bool(armed),
                           "symbol": SYMBOL, "placed": [], "actions": [], "skipped": []}
    tick = mt5.symbol_info_tick(SYMBOL)
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_H1, 0, 400)
    if tick is None or rates is None or len(rates) < 60:
        doc["status"] = "NO_BARS"
        log("no XAUUSD tick or bars from the terminal; nothing decided")
        return doc
    import pandas as pd
    df = h1_frame(rates)
    tnow = pd.Timestamp(int(tick.time), unit="s", tz="UTC")
    hour = float(tnow.hour + tnow.minute / 60.0)
    today = str(tnow.date())
    doc.update({"server_time": tnow.isoformat(), "hour": round(hour, 3)})

    state = rollover_state(_read_json(STATE, {}), today)
    acct = venue.account()
    equity = float(acct.get("equity") or acct.get("balance") or 0.0)
    risk_usd = equity * RISK_FRAC
    kelly = load_kelly_survival(KELLY_FILE, "e8")
    doc.update({"equity": equity, "risk_usd": round(risk_usd, 2),
                "sizing_source": "kelly_survival" if kelly is not None else "policy RISK_FRAC",
                "kelly_risk": kelly})
    guard = _read_json(GUARD, {})
    stood_down = bool(guard.get("stood_down"))
    if stood_down:
        doc["guard"] = "stood down: no new placements this pass"
        log("guard stood down; managing open exposure only")

    bid, ask = venue.quote(SYMBOL)
    try:
        iid = venue.instrument_id(SYMBOL)
        venue_positions = venue.positions()
        xau_positions = gold_positions(venue_positions, iid)
    except Exception as exc:
        # An unreadable position book must fail CLOSED for new placements.  Otherwise the one
        # check intended to prevent a second/opposite XAU leg disappears precisely when the API
        # is unhealthy.
        iid, venue_positions, xau_positions = 0, [], []
        stood_down = True
        doc["positions_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
        log("position book unreadable; no new E8 gold placement this pass")
    # -------------------------------------------------------------- placements
    due_now = [] if stood_down else plan(df, hour, state)
    # THE SELF-HEDGE RULE IS PER LEG, NOT PER BRACKET (principal, 2026-09-24).
    #
    # TradeLocker can hold opposite XAU positions, so a second two-sided bracket placed while one
    # window is live can fill AGAINST it: two spreads and two margin legs for a book whose net
    # exposure is smaller or zero.  That cost is real and the opposing leg still carries it.  What
    # was wrong was throwing away the harmless half with it -- the same-direction leg only adds to
    # a position the desk already wants, and deferring the whole bracket SERIALISES three windows
    # that are only +0.180 correlated, which is most of a month of pass time on a prop clock.
    #
    # MEASURED on this account's own record before the change, off the box's XAUUSD bars, over
    # 2026-09-17..24 (six trading days, the three windows, the live ratchet, E8's spread):
    #   * 4 recorded deferrals (09-22 afternoon, 09-23 london_am, 09-23 afternoon, 09-24
    #     london_am).  3 of the 4 would have filled; ALL THREE were SAME-DIRECTION, none opposing.
    #     +257.13 USD against the -16.20 the deferred-and-replaced versions actually made.
    #   * over the three days the deferral actually bound, +703 -> +976 USD, which is 43 -> 31 days
    #     to the 10,000 target -- the principal's modelled 45 -> 34, reproduced.
    #   * the only OPPOSING fill anywhere in the sample (09-21 london_am buy into an open short)
    #     lost the full -1.000R, -480.74 USD: the single worst trade of the run, and the whole
    #     difference between skipping the opposing leg and removing the check outright.
    # So the opposing leg is skipped and the agreeing leg is placed.  Per-trade risk is unchanged.
    direction = book_direction(xau_positions)
    blocked = OPPOSING_LEG.get(direction) if direction is not None else None
    if direction is None and due_now:
        # A side this code could not read is NOT a flat book.  Defer wholesale, and do not mark
        # the window placed: if the earlier trade exits while this window remains valid, the next
        # pass may still act.
        for due in due_now:
            why = (f"open XAU position(s) with an unreadable side: "
                   f"{', '.join(str(p.get('id')) for p in xau_positions)}; deferred to prevent "
                   f"self-hedging")
            doc["skipped"].append({"window": due["window"], "why": why})
            log(f"[{due['window']}] DEFERRED: {why}")
        due_now = []
    for due in due_now:
        name, spec = due["window"], due["spec"]
        frac, frac_src = window_risk(name, kelly)
        if not frac > 0:
            doc["skipped"].append({"window": name, "why": (
                "stands aside: the survival-constrained growth solve "
                "(reports/KELLY_SURVIVAL.json) funds this window at 0 risk")})
            continue
        risk_usd = equity * frac
        legs: dict[str, dict] = {}
        failed: dict[str, dict] = {}
        for side in ("buy_stop", "sell_stop"):
            if side == blocked:
                why = (f"open XAU position(s) {', '.join(str(p.get('id')) for p in xau_positions)}"
                       f" already lean {'long' if direction == 1 else 'short'}; this leg would "
                       f"trade against them, so it is skipped and the agreeing leg is placed")
                doc["skipped"].append({"window": name, "side": side, "why": why})
                log(f"[{name}] {side} skipped: {why}")
                continue
            s = spec[side]
            dist = abs(float(s["price"]) - float(s["sl"]))
            legal, why = leg_is_legal(side, float(s["price"]), float(bid), float(ask))
            if not legal:
                doc["skipped"].append({"window": name, "side": side, "why": why})
                log(f"[{name}] {side} not available: {why}")
                continue
            lot, basis = lot_for_risk(venue, SYMBOL, dist, risk_usd)
            lot = _quantise(lot, venue, SYMBOL)
            row = {"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
                   "price": float(s["price"]), "sl": float(s["sl"]), "tp": float(s["tp"]),
                   "lot": lot, "stop_dist": round(dist, 2), "risk_usd": round(risk_usd, 2),
                   "sizing": basis, "risk_frac": frac, "risk_source": frac_src,
                   "armed": bool(armed)}
            if not (lot > 0):
                row["status"] = "UNSIZEABLE"
                doc["skipped"].append(row)
                _record(row)
                continue
            if not armed:
                row["status"] = "WOULD_PLACE"
                log(f"[{name}] SHADOW would place {side} {lot} {SYMBOL} @ {s['price']:.2f} "
                    f"sl {s['sl']:.2f} tp {s['tp']:.2f} (risk {risk_usd:.0f} USD)")
                _record(row)
                legs[side] = {"id": None, **{k: row[k] for k in ("price", "sl", "tp", "lot")}}
                continue
            try:
                oid = venue.place_stop(SYMBOL, "buy" if side == "buy_stop" else "sell", lot,
                                       price=float(s["price"]), stop=float(s["sl"]),
                                       take_profit=float(s["tp"]))
                row.update({"status": "SENT", "order_id": oid})
                legs[side] = {"id": oid, **{k: row[k] for k in ("price", "sl", "tp", "lot")}}
                log(f"[{name}] PLACED {side} {lot} {SYMBOL} @ {s['price']:.2f} sl {s['sl']:.2f} "
                    f"tp {s['tp']:.2f} -> order {oid}")
            except Exception as exc:
                row.update({"status": "REJECTED", "why": f"{type(exc).__name__}: {exc}"[:200]})
                log(f"[{name}] REJECTED {side}: {row['why']} (will retry while the window holds)")
                failed[side] = {**{k: row[k] for k in ("price", "sl", "tp", "lot", "risk_usd")},
                                "attempts": 1, "why": row["why"],
                                "first_at": row["at"]}
            _record(row)
        state["windows"][name] = {"placed_at": now.isoformat(timespec="seconds"),
                                  "placed_hour": hour, "hi": due["hi"], "lo": due["lo"],
                                  "orders": legs, "position_id": None, "shadow": not armed}
        if failed:
            state["windows"][name]["failed"] = failed
        doc["placed"].append({"window": name, "legs": legs})

    # -------------------------------------------------------------- management
    try:
        open_orders = venue.orders(SYMBOL)
        open_ids = {int(o.get("id")) for o in open_orders if o.get("id") is not None}
    except Exception as exc:
        open_orders = []
        open_ids = set()
        doc["orders_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
    filled: dict[int, int] = {}
    hist_rows: list[dict] = []
    try:
        hist = venue._api.get_all_orders(history=True, lookback_period="2D")
        hist_rows = hist.to_dict("records") if hasattr(hist, "to_dict") else list(hist)
        for o in hist_rows:
            if str(o.get("status") or "").lower() == "filled" and o.get("positionId"):
                filled[int(o["id"])] = int(o["positionId"])
    except Exception as exc:
        doc["history_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
    positions_ok = True
    try:
        venue_positions = venue.positions()
        xau_positions = gold_positions(venue_positions, iid)
        position_ids = {int(p["id"]) for p in xau_positions}
    except Exception as exc:
        positions_ok = False
        xau_positions = []
        position_ids = set()
        doc["positions_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]

    # -------------------------------------------------------------- dropped legs
    if any(w.get("failed") for w in (state.get("windows") or {}).values()):
        _retry_failed_legs(venue, state, doc, hour=hour, now=now, open_orders=open_orders,
                           orders_ok="orders_unreadable" not in doc, filled=filled,
                           xau_positions=xau_positions, positions_ok=positions_ok,
                           stood_down=stood_down, armed=armed, hist_rows=hist_rows,
                           history_ok="history_unreadable" not in doc, instrument_id=iid)
        open_ids = {int(o.get("id")) for o in open_orders if o.get("id") is not None}

    # OUR OWN ORDERS AND POSITIONS, RE-DERIVED FROM THE VENUE EVERY PASS -- so a rollover (or a
    # lost state file) can neither orphan a position from management nor leave a GTC leg resting.
    own = own_entry_orders(_journal_rows(), state)
    if positions_ok and iid:
        for act in readopt_positions(state, filled, position_ids, own):
            log(f"[{act['window']}] RE-ADOPTED position {act['position_id']} "
                f"(opened by our order {act['order_id']})")
            act["ok"] = True
            doc["actions"].append(act)
        state["carried"] = {n: w for n, w in (state.get("carried") or {}).items()
                            if int(w.get("position_id") or 0) in position_ids}
    for oid in stale_entry_orders(state, open_ids, own):
        act = {"act": "stale_cancel", "window": str(own[oid].get("window")), "order_id": oid}
        try:
            act["ok"] = bool(venue.cancel(int(oid)))
            log(f"[{act['window']}] stale_cancel: our GTC entry order {oid} outlived its day; "
                f"cancelled")
        except Exception as exc:
            act["ok"] = False
            act["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{act['window']}] stale_cancel FAILED: {act['why']}")
        doc["actions"].append(act)

    # The Fusion gold book and this E8 port are the same bracket strategy.  Both therefore use
    # the same measured stop ratchet.  Until this block existed E8 left every winner at its
    # opening stop until the fixed target or close hour, recreating the exact giveback path fixed
    # in Fusion.  Broker stop orders are re-read on every pass; local state advances only after
    # the venue acknowledges the PATCH.
    order_by_id = {int(o["id"]): o for o in open_orders if o.get("id") is not None}
    _info = getattr(mt5, "symbol_info", lambda _s: None)(SYMBOL)
    stop_step = float(getattr(_info, "trade_tick_size", 0.0) or 0.0) or STOP_STEP
    for p in xau_positions:
        mapped = _window_for_position(state, int(p["id"]))
        stop_order = order_by_id.get(int(p.get("stopLossId") or 0))
        current_stop = float((stop_order or {}).get("stopPrice") or 0.0)
        if mapped is None or not (current_stop > 0):
            continue
        name, w = mapped
        decision = trail_decision(
            p, w, df, current_stop,
            cost_per_unit=E8_ROUND_TRIP_PER_PRICE_UNIT,
            spread=max(0.0, float(ask) - float(bid)))
        # ANY TIGHTENING THE VENUE CAN REPRESENT IS SENT (2026-09-29), trail or break-even; the
        # 0.05R floor skipped real protection to save a request that costs no spread.
        if decision is None or not decision.moves or not _pm.tightens_by_min_step(
                side=1 if str(p.get("side") or "").lower() == "buy" else -1,
                new_stop=float(decision.new_stop), current_stop=current_stop, step=stop_step):
            continue
        action = {"act": "ratchet_stop", "window": name, "position_id": int(p["id"]),
                  "before": current_stop, "after": float(decision.new_stop),
                  "improvement_r": round(decision.improvement_r, 6), "ok": False}
        # THE LEVEL MUST STILL BE A STOP WHEN IT ARRIVES, and on this venue that is not free.
        # Measured here on 2026-09-24: the first ratchet this lane ever sent moved position
        # 360287970193246861's stop from 4303.25 to 4259.78 while the market was at 4283.5.  The
        # venue took the modification, the buy stop was already through its trigger, and it
        # filled at market -- 4283.91, 24.13 points and 386.08 USD worse than the level the desk
        # had just proven protected more.  `ratchet` cannot see that: it compares the candidate
        # to the current stop, never to the market.  MetaTrader rejects such a request; this
        # venue executes it, so the check has to happen before the send.
        #
        # `bid`/`ask` are this pass's quote, read seconds earlier at the top of `run`.  Re-quoting
        # per position would be a second venue call per pass on an API that has already returned
        # 429 to this lane today, and a quote a few seconds stale can only make this refuse a
        # borderline level -- which leaves the account's existing stop in place, the safe error.
        _side = 1 if str(p.get("side") or "").lower() == "buy" else -1
        _rests, _why_rest = _pm.stop_rests_at_venue(
            stop=float(decision.new_stop), side=_side, bid=float(bid), ask=float(ask))
        if not _rests:
            action["act"] = "ratchet_refused"
            action["why"] = _why_rest
            log(f"[{name}] stop ratchet REFUSED: {_why_rest}")
            doc["actions"].append(action)
            continue
        try:
            if armed or not w.get("shadow", False):
                action["ok"] = bool(venue.modify_stop(int(p["id"]), float(decision.new_stop)))
            else:
                action["ok"] = True
                action["shadow"] = True
            if action["ok"]:
                log(f"[{name}] {'SHADOW would ratchet' if action.get('shadow') else 'RATCHET'} "
                    f"position {p['id']} stop {current_stop:.2f} -> "
                    f"{float(decision.new_stop):.2f}; {decision.reason}")
            else:
                action["why"] = "venue did not acknowledge the stop modification"
                log(f"[{name}] stop ratchet NOT acknowledged; broker state remains authoritative")
        except Exception as exc:
            action["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{name}] stop ratchet FAILED: {action['why']}")
        doc["actions"].append(action)
    # Positions carried from a previous day are closed at the close hour like today's.
    for name, w in list((state.get("carried") or {}).items()):
        state["windows"].setdefault(f"carried:{name}",
                                    {"orders": {}, "position_id": w.get("position_id")})
    for act in manage_actions(state, hour, open_ids, filled, position_ids):
        w = state["windows"].get(act["window"]) or {}
        kind = act["act"]
        try:
            if kind == "record_position":
                w["position_id"] = act["position_id"]
                log(f"[{act['window']}] {act['side']} filled -> position {act['position_id']}")
            elif kind in ("oco_cancel", "ttl_cancel", "eod_cancel"):
                if armed or not w.get("shadow", False):
                    venue.cancel(int(act["order_id"]))
                log(f"[{act['window']}] {kind}: order {act['order_id']} cancelled")
            elif kind == "close":
                if armed or not w.get("shadow", False):
                    venue.close(int(act["position_id"]))
                w["closed"] = True
                log(f"[{act['window']}] CLOSE position {act['position_id']} at the close hour")
            act["ok"] = True
        except Exception as exc:
            act["ok"] = False
            act["why"] = f"{type(exc).__name__}: {exc}"[:160]
            log(f"[{act['window']}] {kind} FAILED: {act['why']}")
        doc["actions"].append(act)
    state["windows"] = {n: w for n, w in state["windows"].items() if not n.startswith("carried:")}

    doc.setdefault("status", "OK")
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1, default=str), encoding="utf-8")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        doc["state"] = state
        OUT.write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    except OSError as exc:
        log(f"state/report write failed: {exc}")
    return doc


def _retry_failed_legs(venue: Any, state: dict, doc: dict, *, hour: float, now: datetime,
                       open_orders: list[dict], orders_ok: bool, filled: dict[int, int],
                       xau_positions: list[dict], positions_ok: bool, stood_down: bool,
                       armed: bool, hist_rows: list[dict], history_ok: bool,
                       instrument_id: int) -> None:
    """Re-send the legs `retry_decisions` says still belong to a live window. Mutates `state`,
    appends to `doc["actions"]` and to `open_orders` (so the rest of the pass sees the new leg).

    Fails CLOSED: nothing is re-sent on a disarmed pass, with the order book, the order history
    or the position book unreadable (a duplicate or a self-hedge is worse than a missing leg), or
    while the guard stands down. A send that errored may still have LANDED -- resting, or already
    filled and closed back to the level -- so before any re-send the leg is looked for as a
    resting order, then as a filled order in the history, then as a position on its side opened
    since the failed send.
    """
    blind = [why for why, bad in (("the pass is disarmed", not armed),
                                  ("the guard stands down", stood_down),
                                  ("the order book is unreadable", not orders_ok),
                                  ("the position book is unreadable", not positions_ok),
                                  ("the order history is unreadable", not history_ok),
                                  ("the gold instrument id is unknown", not instrument_id))
             if bad]
    if blind:
        waiting = [f"{n}/{side}" for n, w in (state.get("windows") or {}).items()
                   for side in (w.get("failed") or {})]
        doc["retry_skipped"] = {"why": blind, "legs": waiting}
        log(f"dropped legs {waiting} not re-sent this pass: {'; '.join(blind)}")
        return
    try:
        bid, ask = venue.quote(SYMBOL)
    except Exception as exc:
        doc["retry_quote_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
        return
    direction = book_direction(xau_positions)
    if direction is None:
        return
    blocked = OPPOSING_LEG.get(direction)
    known = {int(leg["id"]) for bucket in ("windows", "carried")
             for w in (state.get(bucket) or {}).values()
             for leg in (w.get("orders") or {}).values() if leg.get("id") is not None}
    # Every id the intents journal says this lane sent -- yesterday's legs included, which have
    # left the state at the rollover but still sit in the venue's two-day history.
    journal = _journal_rows()
    known |= set(own_entry_orders(journal, state))
    skew = venue_clock_skew_ms(journal, [*open_orders, *hist_rows])
    try:
        venue_min = float(venue.min_lot(SYMBOL))
    except Exception:
        venue_min = 0.0
    for dec in retry_decisions(state, hour, float(bid), float(ask), filled, blocked):
        name, side, leg = dec["window"], dec["side"], dec["leg"]
        w = state["windows"][name]
        act = {"act": f"leg_{dec['act']}", "window": name, "side": side,
               "attempts": int(leg.get("attempts") or 0)}
        if dec["act"] == "hold":
            continue
        if dec["act"] == "abandon":
            w["failed"].pop(side, None)
            w.setdefault("abandoned", {})[side] = {**leg, "why": dec["why"]}
            act["why"] = dec["why"]
            log(f"[{name}] {side} dropped leg abandoned: {dec['why']}")
            doc["actions"].append(act)
            continue
        levels = {k: leg[k] for k in ("price", "sl", "tp", "lot")}
        done = [o for o in hist_rows if str(o.get("status") or "").lower() == "filled"]
        # The send time on the VENUE's clock, and the size the venue actually sends (the adapter
        # floors every lot at the venue minimum), so neither a skewed box nor a small lot can
        # hide a send that landed.
        sent_at = _iso_ms(leg.get("first_at"))
        since = sent_at + skew if skew is not None else sent_at - UNMEASURED_SKEW_MS
        oid = None
        for book in (open_orders, done):
            oid = oid or matching_resting_order(book, side, float(leg["price"]), known,
                                                lot=max(float(leg["lot"]), venue_min),
                                                instrument_id=int(instrument_id),
                                                since_ms=since)
        if oid is None and position_since_failure(xau_positions, side, leg.get("first_at"),
                                                  state, filled):
            why = ("a position on this side opened after the failed send and no window owns it: "
                   "it may be that send, so the leg is not sent again")
            # MISSED GROWTH (GROWTH_GOVERNANCE Rule 1): if that position is NOT our send, this
            # veto forgoes the leg's whole certified risk. Record what it costs every time.
            missed = leg.get("risk_usd")
            if missed is None:
                stop = abs(float(leg["price"]) - float(leg["sl"]))
                missed = float(leg["lot"]) * stop * XAU_OZ_PER_LOT
            w["failed"].pop(side, None)
            w.setdefault("abandoned", {})[side] = {**leg, "why": why}
            doc["actions"].append({**act, "act": "leg_abandon", "why": why,
                                   "rail": UNOWNED_BLOCK_RAIL,
                                   "missed_growth_risk_usd": round(float(missed), 2)})
            _record({"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
                     **levels, "status": "RAIL_BLOCKED", "rail": UNOWNED_BLOCK_RAIL,
                     "missed_growth_risk_usd": round(float(missed), 2),
                     "retry_of": leg.get("first_at")})
            log(f"[{name}] {side} dropped leg abandoned: {why}; MISSED GROWTH "
                f"({UNOWNED_BLOCK_RAIL}): the leg's {float(missed):.0f} USD of certified risk "
                "is not deployed")
            continue
        row = {"at": now.isoformat(timespec="seconds"), "window": name, "side": side,
               **levels, "armed": True, "retry_of": leg.get("first_at")}
        if oid is not None:
            row.update({"status": "SENT", "order_id": oid, "adopted": True})
            log(f"[{name}] {side} the failed send had landed: adopted order {oid}")
        else:
            try:
                oid = venue.place_stop(SYMBOL, "buy" if side == "buy_stop" else "sell",
                                       float(leg["lot"]), price=float(leg["price"]),
                                       stop=float(leg["sl"]), take_profit=float(leg["tp"]))
                row.update({"status": "SENT", "order_id": oid})
                log(f"[{name}] RE-PLACED {side} {leg['lot']} {SYMBOL} @ {leg['price']:.2f} "
                    f"-> order {oid} (attempt {int(leg.get('attempts') or 0) + 1})")
            except Exception as exc:
                leg["attempts"] = int(leg.get("attempts") or 0) + 1
                leg["why"] = f"{type(exc).__name__}: {exc}"[:200]
                row.update({"status": "REJECTED", "why": leg["why"]})
                act.update({"ok": False, "why": leg["why"]})
                log(f"[{name}] {side} retry REJECTED: {leg['why']}")
                _record(row)
                doc["actions"].append(act)
                continue
        _record(row)
        w.setdefault("orders", {})[side] = {"id": int(oid), **levels}
        w["failed"].pop(side, None)
        known.add(int(oid))
        open_orders.append({"id": int(oid), "side": "buy" if side == "buy_stop" else "sell",
                            "stopPrice": float(leg["price"])})
        act.update({"ok": True, "order_id": int(oid), "adopted": bool(row.get("adopted"))})
        doc["actions"].append(act)
    for w in (state.get("windows") or {}).values():
        if "failed" in w and not w["failed"]:
            del w["failed"]


def connect_terminal(mt5: Any, attach: Any, path: str, *,
                     waits: tuple[float, ...] = MT5_RETRY_WAITS_S,
                     sleep: Any = None) -> tuple[bool, int]:
    """Attach to the terminal, re-initialising it on failure, until it answers a gold tick.

    NO IPC CONNECTION COST ~70 MINUTES ON 2026-09-30. The pass tried `attach_or_initialize`
    once and, on a dead IPC handle, gave up for five minutes -- then did the same again, so a
    terminal that had merely dropped its pipe stayed "unavailable" until something else reset
    it. `terminal_info()` can also answer on a handle whose data calls fail, so success here
    means a real XAUUSD tick, not a handshake. Between attempts the stale handle is shut down so
    `initialize` builds a fresh one. Returns (connected, attempts used).
    """
    pause = sleep or time.sleep
    for n, wait in enumerate(waits, start=1):
        if wait > 0:
            pause(wait)
        try:
            if attach(mt5, path=path, timeout=15000) and mt5.symbol_info_tick(SYMBOL) is not None:
                return True, n
        except Exception as exc:
            log(f"MT5 attach attempt {n} raised {type(exc).__name__}: {exc}")
        log(f"MT5 attach attempt {n}/{len(waits)} failed: {mt5.last_error()}")
        with contextlib.suppress(Exception):
            mt5.shutdown()
    return False, len(waits)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--armed", action="store_true", help="arm this pass regardless of the marker")
    args = ap.parse_args(argv)
    armed = bool(args.armed or ARMED_MARKER.exists())
    try:
        import MetaTrader5 as mt5
        from mt5desk.config import terminal_path
        from research.mt5_session import attach_or_initialize
        ok, _tries = connect_terminal(mt5, attach_or_initialize, terminal_path())
        if not ok:
            log(f"MT5 unavailable after {_tries} attempts: {mt5.last_error()}")
            _failed_pass("MT5_UNAVAILABLE", armed=armed)
            return 1
    except Exception as exc:
        log(f"MetaTrader5 unavailable ({type(exc).__name__}: {exc})")
        _failed_pass("MT5_UNAVAILABLE", armed=armed)
        return 1
    try:
        from prop.tradelocker_venue import TradeLockerVenue, load_credentials
        venue = TradeLockerVenue(creds=load_credentials()).connect()
    except Exception as exc:
        log(f"venue unavailable ({type(exc).__name__}: {exc})")
        _failed_pass("VENUE_UNAVAILABLE", armed=armed)
        mt5.shutdown()
        return 1
    try:
        doc = run(venue, mt5, armed=armed)
        if doc.get("status") == "NO_BARS":
            # The pipe can die between the attach and the first data call. NO_BARS returns
            # before any state is touched, so one reconnect and a second pass are safe.
            ok, _tries = connect_terminal(mt5, attach_or_initialize, terminal_path(),
                                          waits=MT5_RETRY_WAITS_S[1:])
            if ok:
                doc = run(venue, mt5, armed=armed)
    finally:
        mt5.shutdown()
    log(f"e8 gold: {'ARMED' if armed else 'SHADOW'} hour={doc.get('hour')} "
        f"equity={doc.get('equity')} placed={len(doc.get('placed') or [])} "
        f"actions={len(doc.get('actions') or [])} skipped={len(doc.get('skipped') or [])} "
        f"status={doc.get('status')}")
    return 0


def _failed_pass(status: str, *, armed: bool) -> None:
    """Publish connection failure without altering durable window/order state."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix(".tmp")
    temporary.write_text(json.dumps({"at": datetime.now(UTC).isoformat(),
                                     "status": status, "armed": armed,
                                     "placed": [], "actions": [], "skipped": [],
                                     "why": "connection failed; no placement evaluated"}), "utf-8")
    temporary.replace(OUT)


if __name__ == "__main__":
    raise SystemExit(main())
