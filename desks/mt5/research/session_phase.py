"""Which session phase a timestamp falls in, and a sleeve's returns inside the current one.

WHAT THIS EXISTS FOR. `pf_allocator` solves the book from daily series and regime probabilities.
Measured 2026-09-03 it contained ZERO references to hour-of-day or session phase, so 08:00 London
open and 22:00 thin-liquidity roll were the same observation to it and produced the same
allocation from identical inputs. An edge that lives in the London expansion and dies in the roll
carried one mean into every hour of the day.

This module supplies the missing half: the phase label for now, and each sleeve's own realised R
inside that phase, which `robust_elog._posterior_mu` shrinks as the narrowest level of the
hierarchy it already runs (state -> sleeve -> family -> no edge).

IT DECIDES NOTHING. No capital, no eligibility, no veto. It reports what the sleeve did at this
hour and hands that to the optimiser that was already the desk's only allocation authority.

STAMP-HOURS, NOT UTC. The desk measured its own feed (mt5desk/families.py `_h1`, 2026-08-29):
"7-16 broker EET is 04:00-13:00 UTC in summer -- it opens three hours before London does and
closes three hours before it does." The broker offset is therefore an explicit argument with no
default. A wrong constant here does not raise; it silently mislabels every hour, which is worse
than failing, and it would mislabel it in the direction of a confident wrong conditional mean.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

import numpy as np

#: Session phases in broker stamp-hours as [start, end) over a 24h clock. Deliberately finer than
#: the desk's asia/london_am/afternoon sleeve names: the London OPEN expansion and the London MID
#: grind are one label in a sleeve name and two different worlds for a breakout. Whole hours only
#: -- a finer grid buys resolution the evidence cannot support, and the k=40 shrinkage in
#: `_posterior_mu` would discard it anyway.
PHASES: tuple[tuple[str, int, int], ...] = (
    ("ASIA_OPEN", 0, 2),
    ("ASIA_MID", 2, 5),
    ("ASIA_CLOSE", 5, 7),
    ("LONDON_OPEN", 7, 9),
    ("LONDON_MID", 9, 12),
    ("LONDON_NY_OVERLAP", 12, 15),
    ("NY_MID", 15, 18),
    ("NY_CLOSE", 18, 20),
    ("ROLL_THIN", 20, 24),
)


def phase_for_hour(stamp_hour: int) -> str:
    """The phase containing this broker stamp-hour. Total over 0-23 by construction."""
    h = int(stamp_hour) % 24
    for name, start, end in PHASES:
        if start <= h < end:
            return name
    raise ValueError(f"no phase covers stamp-hour {h}; PHASES no longer tiles 0-23")


def phase_at(ts: datetime, *, broker_utc_offset_h: int) -> str:
    """The phase for a UTC instant, on the broker's stamp clock.

    The offset is REQUIRED and has no default, because the desk's own feed is not on UTC and a
    guessed constant mislabels every bucket without ever raising.
    """
    return phase_for_hour((ts.hour + int(broker_utc_offset_h)) % 24)


def _entry_hour(row: Mapping) -> int | None:
    """Broker stamp-hour of a ledger row's entry, or None when it cannot be read.

    None rather than a fallback hour: a row whose time cannot be parsed must be DROPPED from the
    conditional bucket, not quietly assigned to midnight, which would build a phantom edge at
    whatever hour the parser failed toward.
    """
    for key in ("entry_time", "time", "ts"):
        raw = row.get(key)
        if raw is None:
            continue
        text = str(raw)
        # "2026-08-18 08:00:00+00:00" and the ISO 'T' form both appear in this desk's ledgers.
        for sep in (" ", "T"):
            if sep in text:
                clock = text.split(sep, 1)[1]
                if len(clock) >= 2 and clock[:2].isdigit():
                    return int(clock[:2])
    return None


def returns_in_phase(rows: Iterable[Mapping], phase: str, *,
                     broker_utc_offset_h: int,
                     value_key: str = "r_multiple") -> np.ndarray:
    """This sleeve's realised R for trades ENTERED in `phase`.

    Entry time, not exit: the allocation question is "what is this sleeve worth if it opens a
    position now", and the hour it happened to close in is not something the desk knows at
    decision time. Using exit hour would leak the future into the conditional mean.
    """
    out: list[float] = []
    for row in rows:
        hour = _entry_hour(row)
        if hour is None:
            continue
        if phase_for_hour((hour + int(broker_utc_offset_h)) % 24) != phase:
            continue
        try:
            out.append(float(row.get(value_key)))
        except (TypeError, ValueError):
            continue
    return np.asarray(out, dtype=float)
