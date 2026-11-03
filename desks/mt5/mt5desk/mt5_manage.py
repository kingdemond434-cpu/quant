"""ONE STOP-MANAGEMENT DECISION FOR EVERY MT5 ACCOUNT (Fusion gateway, FTMO, every prop account).

The Fusion gateway keeps its own inline copy (`gateway.manage_open_positions`, unchanged here);
`tests/test_mechanism_parity.py` drives both on the same terminals and fails if they ever decide
differently, so the copy cannot drift.

WHY (zuck 2026-11-03 19:58Z: "ftmo fusion etc must always have same mechanisms ... all must be
just as same as each other"). Until this module the Fusion gateway ratcheted every open position
(`gateway.manage_open_positions`: the chandelier trail plus the costed break-even floor), while
the FTMO gold follower only COPIED E8's acknowledged stop moves (`ftmo_follower.mirrored_stop`)
and the FTMO sleeve executor ran no stop management at all. Measured on the box 2026-11-03:
the follower's log held 0 `ratchet_stop` actions since FTMO went live on 2026-10-22.

THE RULE IS THE GATEWAY'S, step for step:
  * a fixed-bracket certificate (a family sleeve with no `trail_k`) gets the break-even FLOOR
    only, read off M1 so a fast winner is protected on its first completed minute -- never the
    trail (2026-09-16: trailing a fixed-bracket certificate is a lookalike strategy);
  * everything else (the gold book, a sleeve whose signal carried a trail) gets
    `position_manager.ratchet`: the H1 chandelier plus the floor;
  * a move is sent only if it tightens by one venue stop step and still RESTS as a stop on the
    right side of the market (`position_manager.stop_rests_at_venue`).
The firm's own rules (FTMO's daily/max loss) bound entries and sizes elsewhere; nothing here
ever loosens a stop, so no firm rule can be breached by it.

Pure apart from the reads it is handed (`mt5` is any object with the MetaTrader5 API).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Any

import pandas as pd
from mt5desk import decision_core as _dc
from mt5desk import position_manager as _pm

# NO TUNABLE LIVES HERE. Every number is the one the Fusion gateway already uses, read from its
# owner: the ATR length from `decision_core`, the break-even floor's commission from
# `libs.portfolio.fusion_cost` (a venue with a lower commission gets a floor a little further
# into profit than its exact break-even: more protection, never less).


@dataclass(frozen=True)
class StopMove:
    """What one pass decides for one position: `new_stop` is None when nothing is sent."""
    new_stop: float | None
    why: str
    breakeven_floor: bool = False
    decision: Any = None


def rates_since(mt5: Any, symbol: str, timeframe: int, opened_at: int, count: int
                ) -> pd.DataFrame:
    """Terminal bars from the position's containing bar, in broker-clock space (positional read,
    filtered on the bar's own server time: no UTC/server offset enters)."""
    raw = mt5.copy_rates_from_pos(symbol, timeframe, 0, int(count))
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    bars = pd.DataFrame(raw)
    if "time" not in bars:
        return pd.DataFrame()
    ts = sorted({int(x) for x in bars["time"]})
    step = min((b - a for a, b in pairwise(ts) if b > a), default=60)
    start = int(opened_at) - (int(opened_at) % max(1, step))
    return bars[bars["time"].astype("int64") >= start].reset_index(drop=True)


def round_trip_per_price_unit(info: Any) -> float | None:
    """The round-trip commission in PRICE units (the venue's tick value / tick size converts),
    or None when the venue reports a degenerate tick value (the floor then waits, never guesses)."""
    import libs.portfolio.fusion_cost as _fc  # as the gateway reads it: at use, not at import

    tick_value = float(getattr(info, "trade_tick_value", 0.0) or 0.0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    if not (tick_value > 0 and tick_size > 0):
        return None
    return (2.0 * float(_fc.COMMISSION_PER_LOT_PER_SIDE)) / (tick_value / tick_size)


def original_stop_distance(store: dict[str, Any], ticket: int, price_open: float,
                           sl: float) -> tuple[float | None, bool]:
    """(the stop distance the position was OPENED with, captured_now). Captured on first sight and
    remembered in `store` (the lane's own state), because once the stop moves `sl` no longer
    encodes the initial risk. No stop -> None: no denominator is ever invented."""
    if not sl:
        return None, False
    key = str(int(ticket))
    if key not in store:
        dist = abs(float(price_open) - float(sl))
        if not dist > 0:
            return None, False
        store[key] = dist
        return dist, True
    return float(store[key]), False


def stop_move(mt5: Any, p: Any, info: Any, *, original_dist: float, floor_only: bool
              ) -> StopMove:
    """The stop this pass moves position `p` to, or why not. Exactly the gateway's sequence."""
    symbol = str(p.symbol)
    side = 1 if int(p.type) == int(getattr(mt5, "POSITION_TYPE_BUY", 0)) else -1
    h1 = int(getattr(mt5, "TIMEFRAME_H1", 16385))
    timeframe = int(getattr(mt5, "TIMEFRAME_M1", h1)) if floor_only else h1
    bars = rates_since(mt5, symbol, timeframe, int(p.time), 2000)
    minimum = 1 if floor_only else 2
    if len(bars) < minimum:
        return StopMove(None, f"fewer than {minimum} {'M1' if floor_only else 'H1'} bars since "
                              f"entry; too early to locate an extreme")
    atr = 0.0
    if not floor_only:
        raw = mt5.copy_rates_from_pos(symbol, h1, 0, 400)
        if raw is None or len(raw) < _dc.ATR_N + 1:
            return StopMove(None, "ATR unavailable")
        atr = _dc.atr_last(pd.DataFrame(raw))
        if not atr > 0:
            return StopMove(None, "ATR non-positive")
    extreme, stall = _pm.extreme_and_stall(highs=[float(x) for x in bars["high"]],
                                           lows=[float(x) for x in bars["low"]], side=side)
    cost = round_trip_per_price_unit(info)
    spread = float(getattr(info, "spread", 0) or 0) * float(getattr(info, "point", 0.0) or 0.0)
    decision = _pm.ratchet(entry=float(p.price_open), current_stop=float(p.sl),
                           stop_distance=float(original_dist), extreme=extreme, atr=atr,
                           side=side, bars_since_extreme=stall, cost_per_unit=cost,
                           spread=spread, floor_only=floor_only)
    if not decision.moves:
        return StopMove(None, str(decision.reason), decision=decision)
    step = (float(getattr(info, "trade_tick_size", 0.0) or 0.0)
            or float(getattr(info, "point", 0.0) or 0.0))
    if not _pm.tightens_by_min_step(side=side, new_stop=float(decision.new_stop),
                                    current_stop=float(p.sl), step=step):
        return StopMove(None, f"move {float(p.sl):.5f} -> {float(decision.new_stop):.5f} is "
                              f"under one venue stop step ({step:g})", decision=decision)
    stops_level = int(getattr(info, "trade_stops_level", 0) or 0)
    tick_size = float(getattr(info, "trade_tick_size", 0.0) or 0.0)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return StopMove(None, "no quote this pass; a stop is never sent blind", decision=decision)
    rests, why = _pm.stop_rests_at_venue(
        stop=float(decision.new_stop), side=side, bid=float(tick.bid), ask=float(tick.ask),
        min_distance=(stops_level * tick_size if stops_level and tick_size else 0.0))
    if not rests:
        return StopMove(None, why, decision=decision)
    return StopMove(float(decision.new_stop), str(decision.reason),
                    breakeven_floor=bool(decision.breakeven_floor), decision=decision)
