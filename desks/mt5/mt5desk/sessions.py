"""Is this symbol's trade session open for NEW risk right now? (principal, 2026-10-06)

WHY A PER-SYMBOL ANSWER. The gateway decided "is the market open" from ONE quote: XAUUSD's tick
age in `main` (older than 1800 s = "market closed", the pass idles). That is right for the
desk's clock and wrong for every other instrument on it. Index CFDs, energies and exotic crosses
keep their own sessions and their own breaks; a symbol whose session has closed, or which the
broker has switched to close-only, would receive an order the venue then rejects (retcode
10018 MARKET_CLOSED, 10044 CLOSE_ONLY) -- a rejection that counts against the placement-health
pause -- or, worse, accept a pending stop that sits through the reopen gap.

WHAT THE MetaTrader5 PYTHON API EXPOSES, AND WHAT IT DOES NOT. MQL5 has
`SymbolInfoSessionTrade(symbol, day, index, from, to)`; the Python package does not carry it
(it exposes `symbol_info`, `symbol_info_tick`, `copy_*`, `order_*`, `positions_*`,
`history_*`). So the session is read from the two facts the Python API does return:

  1. `symbol_info(symbol).trade_mode` -- the broker's own permission, per the MQL5
     ENUM_SYMBOL_TRADE_MODE: 0 DISABLED, 1 LONGONLY, 2 SHORTONLY, 3 CLOSEONLY, 4 FULL.
     DISABLED and CLOSEONLY refuse every new position; LONGONLY refuses a short and SHORTONLY a
     long. A TWO-SIDED order (a session bracket, side None) is refused under a one-sided mode,
     because one of its two legs could not be opened.
  2. `symbol_info_tick(symbol).time` -- the last quote, in broker server seconds. A session
     that has closed stops quoting; the age past `STALE_TICK_S` is the same rule `main` already
     applies to XAUUSD, now applied to the symbol actually being traded. The broker clock's
     recorded UTC offset (`data/broker_clock.json`, `research/session_phase.py`'s second tier)
     converts the server stamp to UTC; unreadable, the offset is 0 -- the same assumption
     `main`'s own staleness test makes, so this is never looser than the pass gate.

ABSENCE IS REPORTED, NOT REFUSED -- AND THIS IS A DELIBERATE EXCEPTION TO "UNMEASURED IS NOT A
LICENCE". A field the terminal does not return (a build without `trade_mode`, a tick with no
`time`) is UNMEASURED, said in `why`, and does not refuse: the pass-level `new_risk_gate` has
already refused a disconnected or unread terminal, so what is left is a CONNECTED terminal that
omits one field, and the venue itself still refuses an order into a closed session. Refusing on
an absent field would let a terminal build halt every lane on a desk whose sessions are open.
`external_gauntlet.symbol_is_tradeable` takes the same position on the registry's
`tradeable` flag ("Absent flag = permitted").

READ ONLY. Never sends, never raises; management of open positions never asks.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: ENUM_SYMBOL_TRADE_MODE, published in the MQL5 reference (SymbolInfoInteger,
#: SYMBOL_TRADE_MODE): an external fact of the venue's protocol, not a desk decision.
TRADE_MODE_DISABLED, TRADE_MODE_LONGONLY, TRADE_MODE_SHORTONLY, TRADE_MODE_CLOSEONLY, \
    TRADE_MODE_FULL = 0, 1, 2, 3, 4
#: A quote older than this means the symbol's session is not trading. The value is the gateway's
#: own `main` rule (`age_sec > 1800` -> "market closed"), so the per-symbol gate and the pass gate
#: agree on what "closed" means; at the desk's one-pass-per-minute cadence it is 30 consecutive
#: passes with no quote, which a liquid session never produces.
STALE_TICK_S = 1800.0


def recorded_utc_offset_h(base: Path | None) -> float:
    """The broker clock's recorded offset (server - UTC, hours), or 0.0 when unreadable."""
    if base is None:
        return 0.0
    try:
        doc = json.loads((Path(base) / "data" / "broker_clock.json").read_text("utf-8"))
        off = float(doc["utc_offset_hours"])
        return off if abs(off) <= 14.0 else 0.0
    except (OSError, ValueError, KeyError, TypeError):
        return 0.0


def _opt_int(obj: object, name: str) -> int | None:
    v = getattr(obj, name, None)
    if isinstance(v, bool) or v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def symbol_session(mt5: Any, symbol: str, *, side: int | None = None,
                   now_utc: datetime | None = None, utc_offset_h: float = 0.0
                   ) -> dict[str, Any]:
    """{"open": bool, "why": str, "trade_mode": int|None, "tick_age_s": float|None,
    "measured": [fields read]} for opening NEW risk on `symbol` (`side` +1/-1, None = both)."""
    out: dict[str, Any] = {"symbol": symbol, "open": True, "why": "session open",
                           "trade_mode": None, "tick_age_s": None, "measured": []}
    unmeasured: list[str] = []
    try:
        info = mt5.symbol_info(symbol)
    except Exception as exc:                                   # never raises past here
        info = None
        unmeasured.append(f"symbol_info raised {type(exc).__name__}")
    mode = _opt_int(info, "trade_mode") if info is not None else None
    out["trade_mode"] = mode
    if mode is None:
        unmeasured.append("trade_mode")
    else:
        out["measured"].append("trade_mode")
        refuse = None
        if mode == TRADE_MODE_DISABLED:
            refuse = "trade_mode DISABLED: the broker allows no trading on this symbol"
        elif mode == TRADE_MODE_CLOSEONLY:
            refuse = "trade_mode CLOSEONLY: the broker accepts exits only"
        elif mode == TRADE_MODE_LONGONLY and (side is None or side < 0):
            refuse = "trade_mode LONGONLY: a short (or a two-sided bracket) cannot be opened"
        elif mode == TRADE_MODE_SHORTONLY and (side is None or side > 0):
            refuse = "trade_mode SHORTONLY: a long (or a two-sided bracket) cannot be opened"
        if refuse:
            out.update(open=False, why=f"{symbol} {refuse}")
            return out
    try:
        tick = mt5.symbol_info_tick(symbol)
    except Exception as exc:
        tick = None
        unmeasured.append(f"symbol_info_tick raised {type(exc).__name__}")
    t = getattr(tick, "time", None) if tick is not None else None
    if isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0:
        now = (now_utc or datetime.now(tz=UTC)).timestamp()
        age = now - (float(t) - float(utc_offset_h) * 3600.0)
        out["tick_age_s"] = round(age, 1)
        out["measured"].append("tick_time")
        if age > STALE_TICK_S:
            out.update(open=False,
                       why=(f"{symbol} session closed: last quote {age / 60:.0f} min old "
                            f"(> {STALE_TICK_S / 60:.0f} min)"))
            return out
    else:
        unmeasured.append("tick time")
    if unmeasured:
        out["why"] = f"session open (UNMEASURED: {', '.join(unmeasured)}; venue is the backstop)"
    return out
