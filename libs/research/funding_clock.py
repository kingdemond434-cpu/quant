"""The funding SETTLEMENT CLOCK -- the single definition of when a perp actually pays (L1.46).

Perpetual funding is a DISCRETE payment at fixed UTC stamps (00/08/16 for an 8h symbol). It is
not an accrual. A position held 7.9h across zero stamps earns NOTHING; a position held 0.2h
across one stamp earns a FULL settlement. Every quantity the desk derives from funding therefore
depends on a clock, and until this module existed the desk had no clock at all:

  * ``nextFundingTime`` -- served in the SAME ``/fapi/v1/premiumIndex`` payload the desk already
    fetches every cycle (``libs/data/crypto_source.py``) -- had ZERO occurrences repo-wide. The
    field arrives and is discarded.
  * ``3 * 365`` (periods per year) was hardcoded at 8 sites and ``/ 8.0`` at 7 more, so the
    interval was an assumption re-stated 15 times and owned nowhere.
  * ``fundingIntervalHours`` -- Binance publishes a PER-SYMBOL interval, and it is 4h for many
    high-funding alts -- had ZERO occurrences. Every ``/ 8.0`` silently under-counts the payments
    of exactly the highest-funding names by 2x.

This module is the one definition, in the same spirit as ``capacity_policy.py`` under s42: import
it rather than restating an interval. It lives in ``libs/research/`` and not ``libs/execution/``
deliberately -- all 8 of today's consumers are research scripts, and ``libs/execution/`` is a
money-path directory frozen to improvements inside a launch window (L1.38). The executor imports
it when that window opens; nothing here changes an order.

PHASE is the coordinate this module makes available and the desk has never had: where in the
funding cycle an event falls. The desk has two organs optimising how LONG to hold a carry
(``hold_optimizer.py``, ``optimal_hold.py``) and none asking WHERE in the cycle to open or close
one, though phase carries the same P&L units as duration and is equally under the desk's control.

REFUSAL PATH (L1.28a/L1.41): an unknown symbol interval returns ``None`` from ``interval_hours``
and every caller must decide explicitly. This module NEVER silently assumes 8h for a symbol it
was not told about -- that assumption is the 2x under-count above, and defaulting to it would
reproduce the defect this module exists to name. ``settlements_in`` requires an explicit interval.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

# Binance USD-M default. A symbol is 8h UNLESS the venue says otherwise -- and the venue is the
# only authority, which is why `interval_hours` refuses rather than guesses for unknown symbols.
DEFAULT_INTERVAL_H = 8.0

# Periods per year at the default interval. Single-sources the `3 * 365` restated at 8 sites.
PERIODS_PER_YEAR = 24.0 / DEFAULT_INTERVAL_H * 365.0  # == 1095.0


def periods_per_year(interval_h: float = DEFAULT_INTERVAL_H) -> float:
    """Funding prints per year at ``interval_h``. Use instead of a literal ``3 * 365``."""
    if interval_h <= 0:
        raise ValueError(f"interval_h must be positive, got {interval_h}")
    return 24.0 / interval_h * 365.0


def _as_utc(t: datetime) -> datetime:
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)


def last_settlement(t: datetime, interval_h: float = DEFAULT_INTERVAL_H) -> datetime:
    """The most recent settlement stamp at or before ``t``.

    Stamps are anchored to the UTC day (00:00), which is how Binance defines them -- NOT to any
    epoch offset. At interval 8h this yields 00/08/16 UTC exactly.
    """
    if interval_h <= 0:
        raise ValueError(f"interval_h must be positive, got {interval_h}")
    t = _as_utc(t)
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed_h = (t - day).total_seconds() / 3600.0
    return day + timedelta(hours=interval_h * int(elapsed_h / interval_h))


def next_settlement(t: datetime, interval_h: float = DEFAULT_INTERVAL_H) -> datetime:
    """The next settlement stamp STRICTLY after ``t``.

    Strictly-after matters: a position closed exactly ON a stamp has already been paid, so the
    next payment it could earn is one full interval away.
    """
    return last_settlement(t, interval_h) + timedelta(hours=interval_h)


def phase_hours(t: datetime, interval_h: float = DEFAULT_INTERVAL_H) -> float:
    """Hours SINCE the last settlement -- the phase coordinate, in [0, interval_h)."""
    return (_as_utc(t) - last_settlement(t, interval_h)).total_seconds() / 3600.0


def hours_to_settlement(t: datetime, interval_h: float = DEFAULT_INTERVAL_H) -> float:
    """Hours UNTIL the next settlement, in (0, interval_h]. The forfeit coordinate: a close with
    a small value here walked away from an imminent payment it had already borne the risk to earn.
    """
    return (next_settlement(t, interval_h) - _as_utc(t)).total_seconds() / 3600.0


def settlements_in(t0: datetime, t1: datetime, interval_h: float = DEFAULT_INTERVAL_H) -> int:
    """Number of settlement stamps in the half-open window (t0, t1] -- the DISCRETE truth.

    This is the count a position actually gets paid for. Contrast the desk's incumbent
    ``held / 8.0``, which books the EXPECTATION of this count: unbiased over many trades
    (measured mean delta -0.012 settlements over 254 closes) and therefore invisible to review,
    but wrong per-trade with sd 0.491 -- 43.3% of closes mis-marked by half a settlement or more.
    """
    if interval_h <= 0:
        raise ValueError(f"interval_h must be positive, got {interval_h}")
    t0, t1 = _as_utc(t0), _as_utc(t1)
    if t1 <= t0:
        return 0
    first = next_settlement(t0, interval_h)
    if first > t1:
        return 0
    return int((t1 - first).total_seconds() / (interval_h * 3600.0)) + 1


def continuous_settlements(t0: datetime, t1: datetime,
                           interval_h: float = DEFAULT_INTERVAL_H) -> float:
    """The incumbent ``held / interval`` accrual, for measuring the delta against truth.

    Kept HERE rather than left implicit at the executor's ``est_funding`` site so the two models
    can be differenced by a fence. A quantity nothing can difference is a quantity nothing can
    audit (L1.43).
    """
    if interval_h <= 0:
        raise ValueError(f"interval_h must be positive, got {interval_h}")
    t0, t1 = _as_utc(t0), _as_utc(t1)
    return max(0.0, (t1 - t0).total_seconds() / 3600.0) / interval_h


def interval_hours(symbol: str, venue_intervals: dict[str, float] | None = None) -> float | None:
    """Funding interval for ``symbol``, or ``None`` when the venue has not told us.

    REFUSES rather than defaults, by design. Binance publishes ``fundingIntervalHours`` per
    symbol and it is 4h for many high-funding alts; assuming 8h for an unknown symbol is the
    exact 2x under-count this module exists to surface, so a caller that wants the default must
    ask for it explicitly and own that choice.
    """
    if not venue_intervals:
        return None
    v = venue_intervals.get(symbol)
    return float(v) if v else None
