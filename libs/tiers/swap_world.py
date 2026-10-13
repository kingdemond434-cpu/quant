"""THE PER-BAR SWAP / ROLLOVER STRESS WORLD (Tier S layer 16).

The sixteen synthetic worlds (`desks/mt5/research/synthetic_regimes.py`) transform the TAPE or the
round-trip cost. None of them touches the one cost that is charged PER NIGHT rather than per trade:
overnight financing. The engine charges it at baseline (`engine.Costs.swap_per_lot_per_night`, the
worse side of the registry's swap, one stamp per night at 21:00 UTC, Wednesday counted three), so a
certificate has never been asked what happens when the broker moves it -- and brokers do: swap
tables are re-priced with policy rates, the triple stamp is Wednesday for spot FX and Friday for
most CFDs (150 of 248 symbols on this desk's own contract tape), and the rollover hour prints the
widest spread of the day.

THE WORLD, applied to the SAME trades the certificate's replay produced (the trades are not
re-decided -- financing does not move a signal), walking each trade bar by bar from entry to exit:

    swap x3            every rollover stamp crossed is charged at three times the worse side
    triple stamp x2    BOTH Wednesday and Friday carry three nights (the venue's triple day is a
                       per-symbol fact the engine defaults; the stress takes the worse of the two)
    rollover spread    a leg (entry or exit) filled on a rollover-hour bar (21:00 or 22:00 UTC --
                       the stamp moves an hour with daylight time) pays the spread x6, i.e. five
                       extra half-spreads on that leg

The engine's own baseline financing is subtracted first, so nothing is charged twice. The result is
a list of R multiples the synthetic-regime organ scores like every other world; a trade that never
crosses a stamp and never fills on a rollover bar is untouched. ONLY A FAILURE IS A FINDING: this
world can only cost R, never add it.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import timedelta
from typing import Any

import pandas as pd

NAME = "swap_rollover_stress"
SWAP_MULT = 3.0
TRIPLE_WEEKDAYS: tuple[int, ...] = (2, 4)            # Wednesday and Friday
ROLLOVER_HOUR_UTC = 21
ROLLOVER_BAR_HOURS: tuple[int, ...] = (21, 22)
ROLLOVER_SPREAD_MULT = 6.0
WHAT = ("per-bar swap/rollover stress: each rollover stamp a trade holds through charged at 3x the "
        "worse-side swap with BOTH Wednesday and Friday triple, and a leg filled on a 21:00/22:00 "
        "UTC rollover bar pays the spread x6; the engine's baseline financing is subtracted first")


def _utc_naive(t: Any) -> pd.Timestamp:
    ts = pd.Timestamp(t)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def stressed_nights(entry: Any, exit_at: Any, *, hour: int = ROLLOVER_HOUR_UTC,
                    triple_weekdays: Sequence[int] = TRIPLE_WEEKDAYS) -> int:
    """Rollover stamps charged between entry and exit, walked day by day (half-open: a stamp at
    the entry instant is not charged, one at the exit instant is -- the engine's convention)."""
    a, b = _utc_naive(entry), _utc_naive(exit_at)
    if not b > a:
        return 0
    day = a.normalize()
    total = 0
    while day <= b:
        stamp = day + timedelta(hours=hour)
        if a < stamp <= b:
            total += 3 if stamp.weekday() in triple_weekdays else 1
        day += timedelta(days=1)
    return total


def baseline_nights(entry: Any, exit_at: Any) -> float:
    """The engine's own count (Wednesday triple, 21:00 UTC), or this module's Wednesday-only walk
    when the engine is not importable."""
    try:
        from mt5desk.engine import rollovers_between
        return float(rollovers_between(pd.Timestamp(entry), pd.Timestamp(exit_at)))
    except ImportError:
        return float(stressed_nights(entry, exit_at, triple_weekdays=(2,)))


def _on_rollover_bar(t: Any) -> bool:
    return _utc_naive(t).hour in ROLLOVER_BAR_HOURS


def stress_r(trades: Iterable[Any], *, swap_per_lot: float, spread_per_lot: float,
             contract: float, engine_charged_swap: bool = True,
             swap_per_lot_per_price: float = 0.0) -> tuple[list[float], int]:
    """(stressed R per trade, trades the world touched). A trade needs entry/exit times, entry,
    stop, r_multiple and units (the engine's `Trade`).

    `swap_per_lot_per_price` is the price-linked part of a night (swap_mode 5/6: an annual
    percent of notional, `engine.Costs.swap_per_lot_per_price`), charged at the trade's own
    entry price. Without it a mode-5 symbol's stress is a stress of nothing."""
    out: list[float] = []
    touched = 0
    contract = float(contract) or 1.0
    for t in trades:
        r = float(t.r_multiple)
        stop_dist = abs(float(t.entry) - float(t.stop))
        if stop_dist <= 0:
            out.append(r)
            continue
        units = float(getattr(t, "units", 1.0) or 1.0)
        nights = stressed_nights(t.entry_time, t.exit_time)
        base = baseline_nights(t.entry_time, t.exit_time) if engine_charged_swap else 0.0
        night = float(swap_per_lot) + float(swap_per_lot_per_price) * float(t.entry)
        extra_swap = max(0.0, SWAP_MULT * nights - base) * night
        legs = int(_on_rollover_bar(t.entry_time)) + int(_on_rollover_bar(t.exit_time))
        extra_spread = legs * (ROLLOVER_SPREAD_MULT - 1.0) * float(spread_per_lot) / 2.0
        charge = (extra_swap + extra_spread) / contract * units / stop_dist
        if charge > 0:
            touched += 1
        out.append(r - charge)
    return out, touched
