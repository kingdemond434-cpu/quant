"""What one lot of an instrument actually risks, in the account's own currency.

THE CONSTANT THAT STOOD IN FOR EVERY INSTRUMENT ON THE DESK

`gateway.auto_lot`, `realised_q`, `promoted_lot` and `MIN_LOT_RISK_EUR` all priced a stop the
same way::

    risk_eur = stop_distance * CONTRACT_OZ * FX_EUR      # 100 * 0.92 = 92

That is gold's contract size multiplied by a frozen EUR/USD constant, and it was applied to
whatever symbol the sleeve happened to name. Measured against the venue's own tick economics in
``universe.json``, the true EUR risked per one price unit per lot spans five orders of magnitude:

    symbol      true EUR/price-unit/lot     gateway assumed     error
    BTCUSD                   0.86                    92          107x OVER-charged
    XAUUSD                  86.41                    92          1.065x over-charged
    CADJPY                 542.40                    92          5.90x UNDER-charged
    EURUSD              86,413.99                    92            939x UNDER-charged

Two different failures live in that table and they point opposite ways. On gold -- the only book
that has ever been armed -- the desk charged itself 6.5% MORE risk than it was taking, so it
sized 6.5% small and the heat cap admitted fewer legs than the budget bought. On every FX cross
the promoter can promote, it charged 5.9x to 939x LESS than the truth, which is the direction
that ends an account.

WHY THIS MODULE EXISTS RATHER THAN A FIXED CONSTANT

The conversion was never unknown. ``research/book_sizing.py`` names the exact error in its
docstring -- "min_lot * contract_size * stop_distance is correct only when the quote currency is
the account currency. On the JPY crosses it returns yen and reads them as euros" -- and then
implements the right one, ``(stop_distance / tick_size) * tick_value * lot``, as a local closure.
``research/swap_exposure.py`` and ``research/book_reality.py`` each re-implement it inline. Three
correct copies in the research half, none of them importable, and the money path kept the
constant. A conversion that is written down three times and shared zero times is not a shared
capability; it is three chances to fix one of them and leave the other two authoritative.

So there is exactly one implementation here and every caller imports it.

WHY LIVE ``symbol_info`` BEATS THE SNAPSHOT, AND WHY THE SNAPSHOT IS STILL KEPT

``tick_value`` is an FX-dependent quantity: it is what the venue will actually credit the account
for one tick, converted to the account currency at today's rate. ``universe.json`` holds a
snapshot taken when the universe was last fetched, so it ages exactly as ``FX_EUR = 0.92`` aged.
At trade time the gateway already holds a live ``mt5.symbol_info`` for the symbol it is about to
size, so that is preferred and the snapshot is the fallback -- with its age reported, never
silently.

UNMEASURABLE IS A REFUSAL, NOT A DEFAULT (L1.28a)

A symbol with no tick economics raises :class:`RiskUnitUnmeasured`. It does NOT fall back to
gold's constants, because that fallback is the defect this module was written to delete: it
would return a plausible number for an instrument nobody has measured, and the caller cannot
tell that from a measurement. The gateway's own precedent is the one to follow -- when
``stop_distance`` is unusable it logs "refusing to size from the house average" and skips the
sleeve rather than guessing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "RiskUnit",
    "RiskUnitUnmeasured",
    "eur_per_price_unit",
    "load_units",
    "lot_for_risk",
    "realised_risk_eur",
    "risk_per_lot",
    "unit_for",
]


class RiskUnitUnmeasured(Exception):
    """Raised when an instrument's EUR-per-lot risk cannot be measured.

    Deliberately an exception and not a sentinel value. A caller that forgets to check a
    sentinel sizes a position from it; a caller that forgets to catch this one does not trade.
    """


@runtime_checkable
class SymbolInfoLike(Protocol):
    """The subset of a live MT5 ``symbol_info`` this module reads (kept tiny for testing)."""

    trade_tick_size: float
    trade_tick_value: float
    volume_min: float
    volume_step: float


@dataclass(frozen=True)
class RiskUnit:
    """One instrument's tick economics, in the ACCOUNT currency, with its provenance.

    ``source`` is ``"live"`` for a terminal ``symbol_info`` and ``"universe"`` for the on-disk
    snapshot. ``as_of`` is the snapshot's own last-bar timestamp, empty for live. Both travel
    with the number so a stale conversion is arguable rather than invisible (L1.55).
    """

    symbol: str
    tick_size: float
    tick_value: float
    min_volume: float
    volume_step: float
    source: str
    as_of: str = ""

    @property
    def eur_per_price_unit(self) -> float:
        """EUR risked per 1.0 of price movement, per 1.0 lot.

        This is the single number the gateway's ``CONTRACT_OZ * FX_EUR`` was standing in for.
        """
        return float(self.tick_value) / float(self.tick_size)

    @property
    def measured(self) -> bool:
        return self.tick_size > 0 and self.tick_value > 0


def _usable(unit: RiskUnit) -> RiskUnit:
    if not unit.measured:
        raise RiskUnitUnmeasured(
            f"{unit.symbol}: tick_size={unit.tick_size} tick_value={unit.tick_value} "
            f"(source={unit.source}) -- cannot price a stop in account currency. "
            f"Refusing to size from another instrument's constants."
        )
    return unit


def _universe_path() -> Path:
    from mt5desk.config import desk_root

    return desk_root() / "data" / "universe" / "universe.json"


_CACHE: dict[str, RiskUnit] | None = None


def load_units(path: Path | None = None, *, refresh: bool = False) -> dict[str, RiskUnit]:
    """Every instrument's tick economics from the ``universe.json`` snapshot.

    Read once and cached: this is on the trade loop. ``refresh=True`` re-reads, which is what a
    fence wants and what a long-lived daemon needs after the universe is re-fetched (L1.66 -- a
    module-scope read would freeze these values for the life of the process).
    """
    global _CACHE
    if _CACHE is not None and not refresh and path is None:
        return _CACHE
    p = path or _universe_path()
    try:
        raw: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RiskUnitUnmeasured(f"universe snapshot unreadable at {p}: {exc}") from exc
    units = {
        sym: RiskUnit(
            symbol=sym,
            tick_size=float(m.get("tick_size", 0) or 0),
            tick_value=float(m.get("tick_value", 0) or 0),
            min_volume=float(m.get("min_volume", 0) or 0) or 0.01,
            volume_step=float(m.get("volume_step", 0) or 0) or 0.01,
            source="universe",
            as_of=str(m.get("last", "")),
        )
        for sym, m in raw.items()
    }
    if path is None:
        _CACHE = units
    return units


def unit_for(symbol: str, info: SymbolInfoLike | None = None) -> RiskUnit:
    """The instrument's tick economics: LIVE ``symbol_info`` if given, else the snapshot.

    Raises :class:`RiskUnitUnmeasured` when neither can price the symbol -- including when the
    symbol is simply absent from the snapshot, which is the case a hardcoded constant answers
    confidently and wrongly.
    """
    if info is not None:
        live = RiskUnit(
            symbol=symbol,
            tick_size=float(getattr(info, "trade_tick_size", 0) or 0),
            tick_value=float(getattr(info, "trade_tick_value", 0) or 0),
            min_volume=float(getattr(info, "volume_min", 0) or 0) or 0.01,
            volume_step=float(getattr(info, "volume_step", 0) or 0) or 0.01,
            source="live",
        )
        if live.measured:
            return live
        # A live handle that cannot price itself falls through to the snapshot rather than
        # failing outright -- but it never falls through to another instrument's constants.
    units = load_units()
    if symbol not in units:
        raise RiskUnitUnmeasured(
            f"{symbol}: absent from the universe snapshot and no usable live symbol_info. "
            f"Known: {len(units)} symbols."
        )
    return _usable(units[symbol])


def eur_per_price_unit(symbol: str, info: SymbolInfoLike | None = None) -> float:
    """EUR risked per 1.0 price unit per 1.0 lot for `symbol`."""
    return _usable(unit_for(symbol, info)).eur_per_price_unit


def risk_per_lot(symbol: str, stop_distance: float,
                 info: SymbolInfoLike | None = None) -> float:
    """EUR put at risk by ONE lot of `symbol` stopped `stop_distance` price units away.

    ``stop_distance`` is in the symbol's own quote price units -- dollars per ounce on XAUUSD,
    yen per unit on a JPY cross -- which is exactly what ``gateway.stop_distance(spec)`` returns
    from the live bracket. The whole point of this function is that those units are NOT
    comparable across instruments until they pass through the venue's tick value.
    """
    d = float(stop_distance)
    if not (d > 0):
        raise RiskUnitUnmeasured(
            f"{symbol}: stop_distance={stop_distance!r} is not positive; "
            f"refusing to size from the house average"
        )
    return d * eur_per_price_unit(symbol, info)


def lot_for_risk(symbol: str, stop_distance: float, risk_eur: float,
                 info: SymbolInfoLike | None = None,
                 *, cap: float = 5.0) -> float:
    """The largest lot of `symbol` whose stop-out costs no more than `risk_eur`.

    SNAPPED DOWN to the venue's volume step, never up, and floored at ``min_volume`` -- the same
    two decisions ``gateway._lot_steps`` and ``auto_lot`` already make and for the same reasons.
    Rounding up re-introduces the overshoot the step function exists to prevent; the floor is
    kept so a small account can still trade and compound out of the range where the floor binds.

    THE FLOOR CAN EXCEED ``risk_eur`` AND THAT IS REPORTED, NOT HIDDEN. Ask
    :func:`realised_risk_eur` what the returned lot actually risks -- for a small account on an
    expensive instrument it is more than the budget, and a policy number the venue silently
    overrides is not a policy.
    """
    unit = _usable(unit_for(symbol, info))
    per_lot = risk_per_lot(symbol, stop_distance, info)
    step = unit.volume_step if unit.volume_step > 0 else 0.01
    raw = float(risk_eur) / per_lot if per_lot > 0 else 0.0
    stepped = int(raw / step + 1e-9) * step
    return float(min(max(stepped, unit.min_volume), cap))


def realised_risk_eur(symbol: str, stop_distance: float, lot: float,
                      info: SymbolInfoLike | None = None) -> float:
    """What `lot` of `symbol` ACTUALLY risks -- after the venue's floor and grain.

    Not the budget that was asked for. The gap between the two is the whole reason
    ``gateway.realised_q`` exists, and it is largest at the smallest accounts, which is exactly
    when it is least visible on a statement.
    """
    return float(lot) * risk_per_lot(symbol, stop_distance, info)


def snapshot_age_days(units: dict[str, RiskUnit] | None = None,
                      now: datetime | None = None) -> float | None:
    """Age in days of the newest bar in the snapshot, or None when undatable.

    ``tick_value`` carries an FX rate, so it ages. None is a REAL answer here (L1.28a): an
    undatable snapshot must not read as a fresh one.
    """
    us = units if units is not None else load_units()
    stamps = [u.as_of for u in us.values() if u.as_of]
    if not stamps:
        return None
    try:
        newest = max(datetime.fromisoformat(s) for s in stamps)
    except ValueError:
        return None
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    return ((now or datetime.now(tz=UTC)) - newest).total_seconds() / 86400.0
