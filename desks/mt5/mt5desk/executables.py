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


def gateway_can_execute(fam: str) -> bool:
    """Can the gateway's family executor trade `fam` today? The boundary the promoter respects."""
    pop = population_of(fam)
    return pop is not None and pop in GATEWAY_FAMILY_POPULATIONS


def executor_gap(fam: str) -> str | None:
    """Why `fam` cannot be traded yet, or None when it can."""
    pop = population_of(fam)
    if pop is None:
        return f"no constructor for family {fam!r} on this tree"
    if pop not in GATEWAY_FAMILY_POPULATIONS:
        return (f"family {fam!r} lives in the {pop!r} population, which the gateway's family "
                f"executor does not run yet (populations: {', '.join(GATEWAY_FAMILY_POPULATIONS)})")
    return None
