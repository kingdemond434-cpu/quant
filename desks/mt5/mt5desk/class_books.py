"""EVERY CROSS-SECTIONAL BOOK IN ONE PLACE: families, grids, targets and the classes each ranks.

Three modules each own a set of class-book families that load their own panel from `symbol`:

  mt5desk.families_cross_sectional   the class books over every primary peer class
  mt5desk.families_sector            the semiconductor sector book (`semis`)
  mt5desk.families_quantamental      point-in-time SEC fundamentals within `equity`

This module is the one door the seeding organ (`research/cross_sectional_breadth.py`), the family
registry (`families_orthogonal.ORTHOGONAL_FAMILIES`) and the lane pin
(`research.universe_policy.CROSS_SECTIONAL_FAMILIES`) read, so a book added in a fourth module is
registered, seeded and admitted by adding it here once.
"""
from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from mt5desk import families_cross_sectional as xs
from mt5desk import families_quantamental as qm
from mt5desk import families_sector as sector
from mt5desk import valuation_regime as vr
from mt5desk.families import Signal

#: The INDIRECT use of the fundamentals dataset: an operator over the class books above.
OPERATOR = "valuation_regime_conditioned"

FAMILIES: dict[str, Callable[..., list[Signal]]] = {
    **xs.CROSS_SECTIONAL_FAMILIES, **sector.SECTOR_FAMILIES, **qm.QUANTAMENTAL_FAMILIES,
    OPERATOR: vr.family_valuation_regime_conditioned}
PARAM_GRID: dict[str, dict[str, list]] = {**xs.PARAM_GRID, **sector.PARAM_GRID, **qm.PARAM_GRID}
TARGETS: dict[str, dict[str, str]] = {
    **xs.TARGETS, **sector.TARGETS, **qm.TARGETS,
    OPERATOR: {"cluster": "relative_value",
               "prior": "valuation predicts the premium a leg earns (Campbell & Shiller 1988; "
                        "value spread: Cohen, Polk & Vuolteenaho 2003): an existing class-book "
                        "leg conditioned on a lagged point-in-time valuation or quality regime"}}

#: Families scoped to named classes. A family absent here (the primary class books) runs on
#: every PRIMARY peer class and never on a sector book, whose members it would rank twice.
SCOPED: dict[str, tuple[str, ...]] = {**sector.FAMILY_CLASSES, **qm.FAMILY_CLASSES,
                                      OPERATOR: tuple(vr.REGIMES_FOR_CLASS)}
SECTOR_CLASSES = frozenset({sector.BOOK})

#: What each family reads, for `families_orthogonal.FAMILY_INPUTS`.
INPUTS: dict[str, tuple[str, str]] = {
    **dict.fromkeys(xs.CROSS_SECTIONAL_FAMILIES, (
        "the symbol's peer class (research.universe_policy.peer_class), read as of each "
        "decision bar from the bar store", "data/universe/*_H1.parquet")),
    **dict.fromkeys(sector.SECTOR_FAMILIES, (
        "the semis sector book (research.universe_policy.SECTOR_BOOKS, resolved against the "
        "registry) with the USDKRW Korea proxy leg, read as of each decision bar",
        "data/universe/*_H1.parquet")),
    OPERATOR: ("a class-book base cell's own signals, gated by a lagged valuation or quality "
               "regime of the equity class or the semis book from point-in-time SEC "
               "fundamentals (mt5desk/valuation_regime.py)",
               "data/universe/*_H1.parquet + data/lake/fundamentals/sec_pit.parquet"),
    **dict.fromkeys(qm.QUANTAMENTAL_FAMILIES, (
        "the equity class's closes as of each decision bar and every member's SEC fundamentals "
        "as ACCEPTED at or before it (research/sec_fundamentals.py)",
        "data/universe/*_H1.parquet + data/lake/fundamentals/sec_pit.parquet")),
}


def families_for(klass: str) -> dict[str, Callable[..., list[Signal]]]:
    """The families enumerated over the members of `klass`."""
    out = {}
    for name, fn in FAMILIES.items():
        scope = SCOPED.get(name)
        if scope is None:
            if klass not in SECTOR_CLASSES:
                out[name] = fn
        elif klass in scope:
            out[name] = fn
    return out


def _first(family: str) -> dict[str, Any]:
    spec = PARAM_GRID.get(family) or {}
    return {k: spec[k][0] for k in sorted(spec)}


def grid(family: str, klass: str | None = None) -> list[dict[str, Any]]:
    """The cells `family` is enumerated on over the members of `klass`.

    For the regime OPERATOR the grid depends on the class: every base family the class runs
    (at its first grid point, so the operator asks one new question per base, not the base's whole
    grid again) x every regime the class may read x both of that regime's states."""
    if family == OPERATOR:
        if klass is None:
            return []
        out = []
        for base in families_for(klass):
            if base == OPERATOR:
                continue
            for regime in vr.REGIMES_FOR_CLASS.get(klass, ()):
                for st in vr.REGIMES[regime][1]:
                    out.append({"base_family": base, "base_params": _first(base),
                                "regime": regime, "state": st})
        return out
    spec = PARAM_GRID.get(family) or {}
    keys = sorted(spec)
    return [dict(zip(keys, combo, strict=True))
            for combo in itertools.product(*(spec[k] for k in keys))]
