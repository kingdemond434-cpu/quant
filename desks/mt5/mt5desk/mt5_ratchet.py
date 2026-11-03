"""ONE STOP RATCHET FOR EVERY METATRADER ACCOUNT: the gateway's position management, callable.

WHY (zuck 2026-11-03 19:58Z, standing rule: "ftmo fusion etc must always have same mechanisms
all etc as other accounts"). Fusion's gateway (`gateway.manage_open_positions`) and E8's gold
lane (`prop/e8_gold.trail_decision`) run the chandelier trail and the costed break-even floor
from `position_manager` on their own positions every pass. FTMO did not: its gold copy only
MIRRORED stops E8 had acknowledged (`ftmo_follower.mirrored_stop`), which never fired, and its
sleeve executor ran time exits and the opposite-side rule but never moved a stop. An FTMO winner
could therefore round-trip to its opening stop -- the exact giveback the 2026-09-24 order forbids
on every account.

WHAT THIS IS. The gateway's per-position decision, step for step, with the terminal passed in
instead of imported, so any lane attached to any MetaTrader terminal runs the same mechanism:

  1. R is the ORIGINAL stop distance, captured once per ticket in `store` (the gateway's
     `orig_stop_dist`), never the live, already-moved stop.
  2. Bars since the position's containing bar, on the broker clock: H1 for the trail, M1 for a
     floor-only (fixed-bracket) position, so a fast winner is floored on its first minute.
  3. ATR(ATR_N) on 400 H1 bars, only when the trail runs (a floor never reads it).
  4. `position_manager.ratchet`: chandelier k=4 (k=1 once stalled) composed with the break-even
     floor at 0.85R net of the round-trip cost and the short leg's spread; never loosens.
  5. One venue stop step is the improvement floor (`tightens_by_min_step`).
  6. The level must still be a STOP when it arrives (`stop_rests_at_venue`, with the symbol's
     `trade_stops_level` folded in).

It decides; it never sends. Each lane sends through its own budgeted, logged door, so the
request caps, arming and shadow behaviour each lane already has are unchanged.

THE ONE INPUT THAT DIFFERS BY FIRM IS THE COMMISSION, and it is read rather than assumed: the
position's own entry deal (`history_deals_get(position=...)`) gives the account's commission per
lot per side. When that is unreadable or zero the fallback `FALLBACK_COMMISSION_PER_SIDE` is
used. It is set deliberately ABOVE every rate measured on this desk (Fusion 2.00/lot/side), because
overstating the cost only lifts the break-even floor further into profit and arms it a little
later; understating it would let a "break-even" exit book a small loss on every scratch.

`tests/ops/test_account_parity.py` runs this and the gateway's own `manage_open_positions` on the
same terminal and asserts the same stop is sent, so the two cannot drift apart silently.
"""
from __future__ import annotations

from collections.abc import Callable, MutableMapping
from itertools import pairwise
from typing import Any

from mt5desk import position_manager as _pm

#: The gateway's ATR window (`decision_core.ATR_N`), read lazily so this module stays importable
#: without pandas on hosts that only lint it.
H1_ATR_BARS = 400
SINCE_BARS = 2000
#: Account currency per lot per side, used only when the position's own deals do not say.
FALLBACK_COMMISSION_PER_SIDE = 3.50


def original_stop_distance(store: MutableMapping[str, Any], ticket: int, price_open: float,
                           sl: float, log: Callable[[str], None] | None = None) -> float | None:
    """The stop distance the position was OPENED with, captured on first sight (the gateway's
    `_original_stop_distance`). None for a position without a stop: nothing is invented."""
    if not sl:
        return None
    key = str(int(ticket))
    if key not in store:
        dist = abs(float(price_open) - float(sl))
        if dist <= 0:
            return None
        store[key] = dist
        if log:
            log(f"MANAGE capture: ticket {ticket} initial stop distance {dist:.5f}")
    return float(store[key])


def prune(store: MutableMapping[str, Any], live_tickets: set[int]) -> None:
    """Drop the captured distance of every ticket the venue no longer reports."""
    for k in [k for k in store if k not in {str(int(t)) for t in live_tickets}]:
        store.pop(k, None)


def commission_per_side(mt5: Any, ticket: int) -> tuple[float, str]:
    """(account currency per lot per side, where it came from) for this position."""
    try:
        deals = mt5.history_deals_get(position=int(ticket)) or []
    except Exception as exc:                         # broad: any terminal failure, named below
        return FALLBACK_COMMISSION_PER_SIDE, f"fallback (deal read failed: {type(exc).__name__})"
    for d in deals:
        if int(getattr(d, "entry", -1)) != 0:        # DEAL_ENTRY_IN
            continue
        vol = float(getattr(d, "volume", 0.0) or 0.0)
        com = abs(float(getattr(d, "commission", 0.0) or 0.0))
        if vol > 0 and com > 0:
            return com / vol, "measured on the position's entry deal"
    return FALLBACK_COMMISSION_PER_SIDE, "fallback (no commission on the entry deal)"


def round_trip_per_price_unit(info: Any, per_side: float) -> float | None:
    """Round-trip commission in PRICE units (the gateway's `_round_trip_per_price_unit`)."""
    tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    if not (tick_value > 0 and tick_size > 0):
        return None
    return (2.0 * float(per_side)) / (tick_value / tick_size)


def _rates_since(mt5: Any, symbol: str, timeframe: int, opened_at: int) -> Any:
    import pandas as pd
    raw = mt5.copy_rates_from_pos(symbol, timeframe, 0, SINCE_BARS)
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    bars = pd.DataFrame(raw)
    if "time" not in bars:
        return pd.DataFrame()
    ts = sorted({int(x) for x in bars["time"]})
    step = min((b - a for a, b in pairwise(ts) if b > a), default=60)
    start = int(opened_at) - (int(opened_at) % max(1, step))
    return bars[bars["time"].astype("int64") >= start].reset_index(drop=True)


def wanted_stop(mt5: Any, p: Any, *, store: MutableMapping[str, Any], floor_only: bool,
                per_side: float | None = None,
                log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """The stop the shared mechanism wants on position `p` this pass, or why none.

    Returns {"ticket", "symbol", "side", "act": "MOVE" | "HOLD" | "SKIP", "why", and for MOVE
    "new_stop", "breakeven_floor"}. Pure apart from the terminal reads; never sends.
    """
    import pandas as pd
    from mt5desk.decision_core import ATR_N, atr_last

    symbol = str(p.symbol)
    side: Any = 1 if int(p.type) == int(getattr(mt5, "POSITION_TYPE_BUY", 0)) else -1
    out: dict[str, Any] = {"ticket": int(p.ticket), "symbol": symbol, "side": side}

    def done(act: str, why: str, **kw: Any) -> dict[str, Any]:
        out.update(act=act, why=why, **kw)
        return out

    info = mt5.symbol_info(symbol)
    if info is None:
        return done("SKIP", "no symbol_info")
    dist = original_stop_distance(store, int(p.ticket), float(p.price_open),
                                  float(getattr(p, "sl", 0.0) or 0.0), log)
    if dist is None:
        return done("SKIP", "no stop on the position; nothing to ratchet against and none invented")
    tf_m1 = getattr(mt5, "TIMEFRAME_M1", mt5.TIMEFRAME_H1)
    timeframe = tf_m1 if floor_only else mt5.TIMEFRAME_H1
    bars = _rates_since(mt5, symbol, timeframe, int(p.time))
    minimum = 1 if floor_only else 2
    if len(bars) < minimum:
        return done("SKIP", f"fewer than {minimum} {'M1' if floor_only else 'H1'} bars since "
                            f"entry; too early to locate an extreme")
    atr = 0.0
    if not floor_only:
        h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, H1_ATR_BARS)
        if h1 is None or len(h1) < ATR_N + 1:
            return done("SKIP", "ATR unavailable")
        atr = atr_last(pd.DataFrame(h1))
        if not atr > 0:
            return done("SKIP", "ATR non-positive")
    extreme, stall = _pm.extreme_and_stall(
        highs=[float(x) for x in bars["high"]], lows=[float(x) for x in bars["low"]], side=side)
    if per_side is None:
        per_side, src = commission_per_side(mt5, int(p.ticket))
        out["commission_source"] = src
    cost_unit = round_trip_per_price_unit(info, per_side)
    spread_price = (float(getattr(info, "spread", 0) or 0)
                    * float(getattr(info, "point", 0.0) or 0.0))
    decision = _pm.ratchet(
        entry=float(p.price_open), current_stop=float(p.sl), stop_distance=dist,
        extreme=extreme, atr=atr, side=side, bars_since_extreme=stall,
        cost_per_unit=cost_unit, spread=spread_price, floor_only=floor_only)
    if not decision.moves:
        return done("HOLD", decision.reason)
    step = (float(getattr(info, "trade_tick_size", 0.0) or 0.0)
            or float(getattr(info, "point", 0.0) or 0.0))
    if not _pm.tightens_by_min_step(side=side, new_stop=float(decision.new_stop),
                                    current_stop=float(p.sl), step=step):
        return done("HOLD", f"move {float(p.sl):.5f} -> {float(decision.new_stop):.5f} is under "
                            f"one venue stop step ({step:g})")
    stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None:
        rests, why_rest = _pm.stop_rests_at_venue(
            stop=float(decision.new_stop), side=side, bid=float(tick.bid), ask=float(tick.ask),
            min_distance=(stops_level * tick_size if stops_level and tick_size else 0.0))
        if not rests:
            return done("HOLD", why_rest)
    return done("MOVE", decision.reason, new_stop=float(decision.new_stop),
                breakeven_floor=bool(decision.breakeven_floor))
