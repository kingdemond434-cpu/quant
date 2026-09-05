"""Which certified families the gateway can trade, resolved in ONE place.

WHY THIS FILE EXISTS (2026-09-05). The canon held 66 certificates; 65 were `external.*` cells in
orthogonal families (overnight_gap_decay, carry, macro_conditional ...). The promoter's main lane
promoted only session-range breakouts on the four gold windows and skipped every other family with
a bare `continue`, and the gateway's family executor resolved families through `run_hunt16.FAMILIES`
alone -- fourteen `dav_*` families. So a certificate could pass ten gates, run a forward clock to
maturity, read PROMOTION CANDIDATE, and never reach capital, with no line anywhere saying why.
The principal's order is universal: "all promotion candidates get into the live account
immediately, no waiting, no permission, fully automatically, always".

The resolution order is the forward engine's own (`shadow_forward._family_fn`), so the executor
trades exactly the constructor the clock replayed: hunt16's FAMILIES first (the executor's
original population), then `mt5desk.families.family_<name>`, then the orthogonal registry.

`gateway_can_execute` is the honest boundary. Today the gateway's family executor runs the
hunt16 population and the gold brackets; the promoter asks this function before writing a
`family_market` row, and a certificate whose family resolves here but is not yet executable is
recorded on its clock as `executor_gap` -- a named wiring defect, never a LIVE row the gateway
cannot trade (which the allocator would fund and the book would silently hold as air). When the
universal executor lands, this function widens and the promoter promotes those rows on its next
run without any other change.
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: Families the gateway's family executor runs today. Widened by the universal executor; the
#: promoter and the health report read it, so a widening is visible the run it happens.
GATEWAY_FAMILY_POPULATIONS: tuple[str, ...] = ("hunt16",)

#: CHARTS the gateway's family executor runs. THE FAMILY EXECUTOR LEARNED THE LADDER 2026-09-05,
#: so this is now the full sweep ladder and `executor_gap` no longer fires on a timeframe.
#:
#: WHY THIS CONSTANT EXISTED FOR A DAY. When the sweep gained M1..D1, every `family_market` path
#: in `gateway.py` still called `copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 400)`
#: unconditionally. A certificate is enrolment, so a matured M5 candidate would have been promoted
#: to a `family_market` row and had its signals computed FROM HOURLY BARS -- a live position in a
#: strategy nobody certified, under the name of one that was, with every artifact agreeing. This
#: tuple kept those rows out of the book while that was true, which was the honest state and not
#: the destination.
#:
#: WHAT CLOSED IT. `gateway._family_chart` resolves the chart from the certificate's own params
#: (absent means H1, the desk-wide spelling, so no existing row changes), scales the bar count so
#: every chart is handed the same MARKET TIME rather than the same bar count, and refuses BY NAME
#: when a timeframe has no MT5 chart on the box rather than falling back to hourly.
#: `decision_core.family_bar_due` gained the matching entry rule: the signal bar must START the
#: signal hour, so a sleeve certified to take one entry a day takes one on M5 and M1 too instead
#: of twelve or sixty. H1 is byte-identical through both changes.
#:
#: The boundary itself is NOT deleted, and that matters: `gateway_can_execute` still refuses a
#: chart absent from this tuple, so the day someone adds an eighth timeframe to the sweep it is
#: `executor_gap` -- a named wiring defect on the clock -- until the executor is shown to run it.
#: The scalp lane keeps its own executor (`scalp_exec`, `exec="scalp_market"`), unaffected.
GATEWAY_FAMILY_TIMEFRAMES: tuple[str, ...] = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def hunt16_families() -> dict[str, Callable[..., Any]]:
    try:
        from run_hunt16 import FAMILIES
        return dict(FAMILIES)
    except Exception:
        return {}


def resolve_family(fam: str) -> Callable[..., Any] | None:
    """The one constructor for `fam`, in the forward engine's own order; None when no code on
    this tree answers to the name (a certificate for such a family is an orphan, not a sleeve)."""
    fn = hunt16_families().get(fam)
    if fn is not None:
        return fn
    try:
        from mt5desk import families
        fn = getattr(families, f"family_{fam}", None)
        if fn is not None:
            return fn
    except Exception:
        pass
    try:
        from mt5desk import families_orthogonal as fo
        return fo.ORTHOGONAL_FAMILIES.get(fam)
    except Exception:
        return None


def population_of(fam: str) -> str | None:
    """Which population a family belongs to: 'hunt16', 'families', 'orthogonal', or None."""
    if fam in hunt16_families():
        return "hunt16"
    try:
        from mt5desk import families
        if getattr(families, f"family_{fam}", None) is not None:
            return "families"
    except Exception:
        pass
    try:
        from mt5desk import families_orthogonal as fo
        if fam in fo.ORTHOGONAL_FAMILIES:
            return "orthogonal"
    except Exception:
        pass
    return None


def gateway_can_execute(fam: str, timeframe: str = "H1") -> bool:
    """Can the gateway's family executor trade `fam` on `timeframe` today?

    The boundary the promoter respects. `timeframe` defaults to H1 -- the chart every certificate
    written before the ladder was hunted on -- so no existing caller or row changes.
    """
    return executor_gap(fam, timeframe) is None


def executor_gap(fam: str, timeframe: str = "H1") -> str | None:
    """Why `fam` on `timeframe` cannot be traded yet, or None when it can."""
    pop = population_of(fam)
    if pop is None:
        return f"no constructor for family {fam!r} on this tree"
    if pop not in GATEWAY_FAMILY_POPULATIONS:
        return (f"family {fam!r} lives in the {pop!r} population, which the gateway's family "
                f"executor does not run yet (populations: {', '.join(GATEWAY_FAMILY_POPULATIONS)})")
    tf = str(timeframe or "H1").upper()
    if tf not in GATEWAY_FAMILY_TIMEFRAMES:
        return (f"certificate is on the {tf} chart and the gateway's family executor runs "
                f"{'/'.join(GATEWAY_FAMILY_TIMEFRAMES)} "
                f"(gateway._family_chart resolves the chart from the certificate's own params). "
                f"Trading it would compute this sleeve's signals from a chart it was never "
                f"certified on -- a different strategy under a certified name")
    return None
