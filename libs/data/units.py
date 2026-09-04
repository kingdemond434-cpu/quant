"""Typed quantities: no untyped number crosses the research boundary.

THE DEFECT CLASS. Vibe-Trading's public bug log records gold priced with FX pip and lot
conventions; this desk's own history records a JPY cross sized from gold's dollar stop, a
0.01-lot floor read as a per-trade fraction, and a spread charged in points where the cost model
expected price. Every one of those is a number that travelled without its unit. At 20-30% heat
a unit error is not a rounding problem.

    Quantity(value, unit, currency=None, tz=None, source=None)

is the only thing a DataHub contract may hand out for a physical measurement. Arithmetic is
deliberately narrow: same-unit add/sub, scalar mul/div, and explicit `convert` through the
declared table. Anything else raises, which is the point. `reconcile` compares the same
quantity from two sources and says whether they agree inside a tolerance -- the cross-source
check the hub runs on every overlapping feed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

#: Unit vocabulary. Adding one is a declaration; a string outside it is refused.
UNITS: frozenset[str] = frozenset({
    "price", "points", "pips", "bp", "percent", "fraction", "ratio", "usd", "eur", "lots",
    "contracts", "ticks", "count", "seconds", "hours", "days", "bars", "log_return",
    "r_multiple", "sigma", "usd_per_oz", "price_per_unit",
})

#: Declared conversions (from, to) -> factor, for the dimensionless family only. Price-space
#: conversions (points <-> price) need the instrument's tick size and go through `to_price`.
_FACTORS: dict[tuple[str, str], float] = {
    ("percent", "fraction"): 0.01, ("fraction", "percent"): 100.0,
    ("bp", "fraction"): 1e-4, ("fraction", "bp"): 1e4,
    ("bp", "percent"): 1e-2, ("percent", "bp"): 1e2,
    ("hours", "seconds"): 3600.0, ("seconds", "hours"): 1 / 3600.0,
    ("days", "hours"): 24.0, ("hours", "days"): 1 / 24.0,
}


class UnitError(ValueError):
    pass


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    currency: str | None = None
    tz: str | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.unit not in UNITS:
            raise UnitError(f"unknown unit {self.unit!r}; declare it in libs.data.units.UNITS")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise UnitError(f"value must be a number, got {type(self.value).__name__}")

    def _same(self, other: Quantity, op: str) -> None:
        if self.unit != other.unit:
            raise UnitError(f"{op}: {self.unit} vs {other.unit}")
        if (self.currency or other.currency) and self.currency != other.currency:
            raise UnitError(f"{op}: currency {self.currency} vs {other.currency}")

    def __add__(self, other: Quantity) -> Quantity:
        self._same(other, "add")
        return Quantity(self.value + other.value, self.unit, self.currency, self.tz, self.source)

    def __sub__(self, other: Quantity) -> Quantity:
        self._same(other, "sub")
        return Quantity(self.value - other.value, self.unit, self.currency, self.tz, self.source)

    def scale(self, k: float) -> Quantity:
        return Quantity(self.value * float(k), self.unit, self.currency, self.tz, self.source)

    def convert(self, to: str) -> Quantity:
        if to == self.unit:
            return self
        f = _FACTORS.get((self.unit, to))
        if f is None:
            raise UnitError(f"no declared conversion {self.unit} -> {to}")
        return Quantity(self.value * f, to, self.currency, self.tz, self.source)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "currency": self.currency,
                "tz": self.tz, "source": self.source}


def to_price(points: Quantity, tick_size: float) -> Quantity:
    """Points (or pips) to price units for one instrument. Needs the instrument's tick."""
    if points.unit not in ("points", "pips"):
        raise UnitError(f"to_price expects points/pips, got {points.unit}")
    if not (tick_size > 0):
        raise UnitError("tick_size must be positive")
    mult = tick_size * (10.0 if points.unit == "pips" else 1.0)
    return Quantity(points.value * mult, "price", points.currency, points.tz, points.source)


def reconcile(a: Quantity, b: Quantity, *, rel_tol: float = 1e-3,
              abs_tol: float = 0.0) -> dict[str, Any]:
    """Do two sources agree on the same quantity? Units must match; the verdict is a number."""
    if a.unit != b.unit:
        return {"agree": False, "why": f"unit mismatch {a.unit} vs {b.unit}"}
    if (a.currency or b.currency) and a.currency != b.currency:
        return {"agree": False, "why": f"currency mismatch {a.currency} vs {b.currency}"}
    diff = abs(a.value - b.value)
    scale = max(abs(a.value), abs(b.value), 1e-12)
    ok = math.isclose(a.value, b.value, rel_tol=rel_tol, abs_tol=abs_tol)
    return {"agree": bool(ok), "abs_diff": diff, "rel_diff": diff / scale,
            "sources": [a.source, b.source]}
