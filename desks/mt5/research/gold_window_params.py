"""THE GOLD WINDOW BRACKET'S TRADED PARAMETERS, read from `mt5desk.decision_core` -- one reader.

    from gold_window_params import traded_params
    traded_params("asia")   # {"rr": 2.0, "atr_n": 20, "sig_hour": 7, "rng": None, ...}

WHY A SHARED READER (2026-10-20). Two research organs need "what the gateway trades for this gold
window" and must not each keep a copy: the replication lane (`replication_civilization`'s
`gold_window_bracket` rule, which rebuilds the live fills) and the certificate-lineage work on
`claude/live-window-cert-lineage` (`research/cert_lineage.traded_params`, which joins a window to
the canon by the parameters it trades). That branch has not landed, so this module is the shared
helper; its `rr` and `trigger_life_h1_bars` keys mean exactly what cert_lineage's do, and
cert_lineage can import this instead of reading decision_core itself.

WHAT IS READ, NEVER WRITTEN HERE. `RR`, `ATR_N`, `GOLD_WINDOWS` (signal hour and range window),
`window_end_hour` (the bracket's life: the next window's signal hour, or CLOSE_HOUR for the last)
and `CLOSE_HOUR` (the gold book's force-close) are decision_core's own names. Three numbers live
as LITERALS inside decision_core's functions and have no name to read; they are restated below
with the line they come from, and the replication test pins each against
`decision_core.bracket_from_bars` on synthetic bars, so a change there fails the test instead of
drifting silently:

    GOLD_ATR_FLOOR        bracket_from_bars: `max(a, 5.0)`
    MIN_TICK              bracket_spec:      `tick = max(tick, 0.01)`
    STOPS_LEVEL_DEFAULT   gateway.resolve_bracket: `trade_stops_level or 20`
    GATEWAY_H1_BARS       gateway.resolve_bracket: `copy_rates_from_pos(..., 0, 400)`

An empty dict means decision_core could not be read: a caller must treat that as UNMEASURED, never
substitute its own numbers.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]

#: Literals inside decision_core / gateway functions (see the module docstring); restated, pinned.
GOLD_ATR_FLOOR = 5.0
MIN_TICK = 0.01
STOPS_LEVEL_DEFAULT = 20
GATEWAY_H1_BARS = 400
#: The bracket's SL widening factor on ATR (bracket_spec: `dist = max(1.2 * a, span)`).
ATR_MULT = 1.2


def windows() -> tuple[str, ...]:
    """The gold windows decision_core places, in its own order; () when it cannot be read."""
    dc = _dc()
    return tuple(str(w[0]) for w in dc.GOLD_WINDOWS) if dc is not None else ()


def _dc() -> Any:
    if str(DESK) not in sys.path:
        sys.path.insert(0, str(DESK))
    try:
        from mt5desk import decision_core as dc
    except Exception:
        return None
    return dc


def traded_params(window: str | None) -> dict[str, Any]:
    """Everything the gateway's bracket for `window` is built from, read from decision_core.

    Keys: rr, atr_n, sig_hour, rng ((start, end) or None = hours before sig_hour), window_end
    (server hour the trigger dies), close_hour, trigger_life_h1_bars (window_end - sig_hour, the
    key cert_lineage publishes), plus the restated literals atr_floor, min_tick,
    stops_level_default, gateway_h1_bars and atr_mult. {} when decision_core is unreadable or
    the window is not one it places.
    """
    dc = _dc()
    if dc is None:
        return {}
    row = next((w for w in dc.GOLD_WINDOWS if w[0] == window), None)
    if row is None:
        return {}
    sig = float(row[1])
    end = dc.window_end_hour(window)
    if end is None:
        return {}
    rng = tuple(int(x) for x in row[2]) if row[2] is not None else None
    return {"rr": float(dc.RR), "atr_n": int(dc.ATR_N), "sig_hour": int(sig), "rng": rng,
            "window_end": float(end), "close_hour": float(dc.CLOSE_HOUR),
            "trigger_life_h1_bars": float(end) - sig, "atr_floor": GOLD_ATR_FLOOR,
            "min_tick": MIN_TICK, "stops_level_default": STOPS_LEVEL_DEFAULT,
            "gateway_h1_bars": GATEWAY_H1_BARS, "atr_mult": ATR_MULT}
