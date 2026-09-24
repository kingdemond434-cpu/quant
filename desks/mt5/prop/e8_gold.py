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
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk.decision_core import (  # noqa: E402
    ATR_N,
    BRACKET_TTL_HOURS,
    CANCEL_HOUR,
    CLOSE_HOUR,
    GOLD_WINDOWS,
    MIN_RATCHET_IMPROVEMENT_R,
    atr_last,
    bracket_from_bars,
    h1_frame,
)
from mt5desk import position_manager as _pm  # noqa: E402

SYMBOL = "XAUUSD"
#: Per-trade risk on the prop account, as a fraction of equity (docs/PROP_FIRM_E8.md).
RISK_FRAC = 0.005
STATE = DESK / "data" / "e8_gold_state.json"
OUT = DESK / "reports" / "E8_GOLD.json"
INTENTS = DESK / "data" / "e8_gold_intents.jsonl"
ARMED_MARKER = DESK / "data" / "E8_GOLD_ARMED"
GUARD = DESK / "data" / "e8_guard_state.json"
LOG = DESK / "logs" / "e8_gold.log"
TAG = "E8gold"


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
        if hour >= CANCEL_HOUR:
            acts.extend({"act": "eod_cancel", "window": name, "order_id": oid} for oid in resting)
        elif hour - placed_hour >= BRACKET_TTL_HOURS:
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


def trail_decision(position: dict, window: dict, bars: Any, current_stop: float
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
                       extreme=extreme, atr=atr, side=side, bars_since_extreme=stalled)


# ------------------------------------------------------------------ the pass

def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default


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
    from prop.e8_executor import _quantise, lot_for_risk

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

    state = _read_json(STATE, {})
    if state.get("date") != today:
        carried = {n: w for n, w in (state.get("windows") or {}).items()
                   if w.get("position_id") is not None and not w.get("closed")}
        state = {"date": today, "windows": {}, "carried": carried}
    acct = venue.account()
    equity = float(acct.get("equity") or acct.get("balance") or 0.0)
    risk_usd = equity * RISK_FRAC
    doc.update({"equity": equity, "risk_usd": round(risk_usd, 2)})
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
    if xau_positions and due_now:
        # TradeLocker can hold opposite XAU positions.  A second two-sided bracket while one
        # window is live can therefore fill against it, paying two spreads/margin legs for a
        # book whose net exposure is smaller or zero.  Defer, do not mark the window placed: if
        # the earlier trade exits while this window remains valid, the next pass may still act.
        for due in due_now:
            why = (f"earlier XAU position(s) still open: "
                   f"{', '.join(str(p.get('id')) for p in xau_positions)}; deferred to prevent "
                   f"self-hedging")
            doc["skipped"].append({"window": due["window"], "why": why})
            log(f"[{due['window']}] DEFERRED: {why}")
        due_now = []
    for due in due_now:
        name, spec = due["window"], due["spec"]
        legs: dict[str, dict] = {}
        for side in ("buy_stop", "sell_stop"):
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
                   "sizing": basis, "armed": bool(armed)}
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
                log(f"[{name}] REJECTED {side}: {row['why']}")
            _record(row)
        state["windows"][name] = {"placed_at": now.isoformat(timespec="seconds"),
                                  "placed_hour": hour, "hi": due["hi"], "lo": due["lo"],
                                  "orders": legs, "position_id": None, "shadow": not armed}
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
    try:
        hist = venue._api.get_all_orders(history=True, lookback_period="2D")
        rows = hist.to_dict("records") if hasattr(hist, "to_dict") else list(hist)
        for o in rows:
            if str(o.get("status") or "").lower() == "filled" and o.get("positionId"):
                filled[int(o["id"])] = int(o["positionId"])
    except Exception as exc:
        doc["history_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]
    try:
        venue_positions = venue.positions()
        xau_positions = gold_positions(venue_positions, iid)
        position_ids = {int(p["id"]) for p in xau_positions}
    except Exception as exc:
        xau_positions = []
        position_ids = set()
        doc["positions_unreadable"] = f"{type(exc).__name__}: {exc}"[:160]

    # The Fusion gold book and this E8 port are the same bracket strategy.  Both therefore use
    # the same measured stop ratchet.  Until this block existed E8 left every winner at its
    # opening stop until the fixed target or close hour, recreating the exact giveback path fixed
    # in Fusion.  Broker stop orders are re-read on every pass; local state advances only after
    # the venue acknowledges the PATCH.
    order_by_id = {int(o["id"]): o for o in open_orders if o.get("id") is not None}
    for p in xau_positions:
        mapped = _window_for_position(state, int(p["id"]))
        stop_order = order_by_id.get(int(p.get("stopLossId") or 0))
        current_stop = float((stop_order or {}).get("stopPrice") or 0.0)
        if mapped is None or not (current_stop > 0):
            continue
        name, w = mapped
        decision = trail_decision(p, w, df, current_stop)
        if decision is None or not decision.moves \
                or decision.improvement_r < MIN_RATCHET_IMPROVEMENT_R:
            continue
        action = {"act": "ratchet_stop", "window": name, "position_id": int(p["id"]),
                  "before": current_stop, "after": float(decision.new_stop),
                  "improvement_r": round(decision.improvement_r, 6), "ok": False}
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--armed", action="store_true", help="arm this pass regardless of the marker")
    args = ap.parse_args(argv)
    armed = bool(args.armed or ARMED_MARKER.exists())
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            log(f"MT5 initialize failed: {mt5.last_error()}")
            return 1
    except Exception as exc:
        log(f"MetaTrader5 unavailable ({type(exc).__name__}: {exc})")
        return 1
    try:
        from prop.tradelocker_venue import TradeLockerVenue, load_credentials
        venue = TradeLockerVenue(creds=load_credentials()).connect()
    except Exception as exc:
        log(f"venue unavailable ({type(exc).__name__}: {exc})")
        return 1
    doc = run(venue, mt5, armed=armed)
    log(f"e8 gold: {'ARMED' if armed else 'SHADOW'} hour={doc.get('hour')} "
        f"equity={doc.get('equity')} placed={len(doc.get('placed') or [])} "
        f"actions={len(doc.get('actions') or [])} skipped={len(doc.get('skipped') or [])} "
        f"status={doc.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
