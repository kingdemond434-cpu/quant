"""The Aggression Governor: why the deployed heat is what it is, in components, every pass.

NOT A SAFETY GOVERNOR. The desk's heat is resolved by `heat_policy.resolve`: the principal's
floor (20%), growth free above it to the catastrophe ceiling (30%), and only the ruin layer
below. This module does not add a lever on top of that -- it AUDITS it, so that a book which
sits at the floor while the evidence would bear more is a finding with a number rather than a
quiet default. The multiplier it reports,

    A_t = deployed heat / floor           in [0, ceiling/floor]

is decomposed into the things a growth governor is supposed to weigh:

    opportunity_quality   what growth wanted (free optimum / floor)
    evidence_strength     how much of the funded book has traded out of sample (readiness)
    effective_breadth     independent bets in the funded book, from its own correlations
    model_agreement       the allocator beat its baselines on these worlds (the proof)
    tail_safety           the Kelly surface's ruin / drawdown-tolerance constraint at the book
    execution_quality     realised vs modelled cost, when the box has measured it
    margin_headroom       account margin, when the box has measured it

and the verdict is one of:

    AT_FLOOR              free optimum at or below the floor: the mandate is what deploys
    GROWTH_ABOVE_FLOOR    growth wanted more and got it, inside the ceiling and the tail bound
    CEILING_BOUND         growth wanted more than the catastrophe ceiling allows
    TAIL_BOUND            the Kelly surface would not bear the free optimum
    UNUSED_UPSIDE         growth wanted more, the tail would bear it, the book got less --
                          a defect to fix, never a preference

Under the growth governance, UNUSED_UPSIDE is the one verdict that must not persist: it means
some rail between the optimum and the book is costing forward E[log W] without proving itself.
`missed_growth` reads it.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

AT_FLOOR, GROWTH_ABOVE_FLOOR, CEILING_BOUND, TAIL_BOUND, UNUSED_UPSIDE = (
    "AT_FLOOR", "GROWTH_ABOVE_FLOOR", "CEILING_BOUND", "TAIL_BOUND", "UNUSED_UPSIDE")


def effective_breadth(ev: Sequence[Any], book: Mapping[str, float]) -> float | None:
    """Independent bets in the funded book: 1 / sum_ij w_i w_j rho_ij on common history."""
    names = [e.name for e in ev if float(book.get(e.name, 0.0)) > 1e-6]
    if len(names) < 2:
        return float(len(names)) if names else None
    by = {e.name: e for e in ev}
    obs = min(int(by[n].daily_r.size) for n in names)
    if obs < 20:
        return None
    m = np.stack([by[n].daily_r[-obs:] for n in names], axis=1)
    sd = m.std(axis=0)
    if not np.all(sd > 0):
        return None
    c = np.corrcoef(m, rowvar=False)
    w = np.array([float(book[n]) for n in names])
    w = w / w.sum()
    denom = float(w @ c @ w)
    return float(1.0 / denom) if denom > 0 else None


def explain(*, floor: float, ceiling: float, total_heat: float, free_optimum: float,
            readiness: float, proof_passed: bool, surface: Mapping[str, Any] | None,
            book: Mapping[str, float], ev: Sequence[Any],
            execution_quality: float | None = None,
            margin_headroom: float | None = None) -> dict[str, Any]:
    a = float(total_heat / floor) if floor > 0 else 0.0
    breadth = effective_breadth(ev, book)
    s = surface or {}
    tail_max = float(s.get("heat_tail_max", float("nan")))
    at_book = s.get("at_book") or {}
    tail_ok = (bool(at_book) and at_book.get("p_ruin", 1.0) == 0.0
               and at_book.get("p_dd_over_tolerance", 1.0) <= float(s.get("alpha", 0.0)))
    gaps: dict[str, str] = {}
    if execution_quality is None:
        gaps["execution_quality"] = "no live fills measured on this host"
    if margin_headroom is None:
        gaps["margin_headroom"] = "no account margin reading on this host"
    if not s:
        gaps["tail_safety"] = "Kelly surface not computed"

    if free_optimum <= floor + 1e-6:
        verdict = AT_FLOOR
    elif total_heat >= min(free_optimum, ceiling) - 1e-4:
        verdict = CEILING_BOUND if free_optimum > ceiling + 1e-6 else GROWTH_ABOVE_FLOOR
    elif np.isfinite(tail_max) and total_heat >= tail_max - 1e-4:
        verdict = TAIL_BOUND
    else:
        verdict = UNUSED_UPSIDE
    room = (min(free_optimum, ceiling, tail_max if np.isfinite(tail_max) else ceiling)
            - total_heat)
    return {
        "A": round(a, 4), "floor": floor, "ceiling": ceiling,
        "deployed_heat": round(float(total_heat), 6),
        "components": {
            "opportunity_quality": round(float(free_optimum / floor), 4) if floor else None,
            "evidence_strength": round(float(readiness), 4),
            "effective_breadth": (round(breadth, 3) if breadth is not None else None),
            "model_agreement": bool(proof_passed),
            "tail_safety": {"ok_at_book": tail_ok, "heat_tail_max": (round(tail_max, 6)
                                                                   if np.isfinite(tail_max)
                                                                   else None),
                            "p_ruin_at_book": at_book.get("p_ruin"),
                            "p_dd_over_tolerance_at_book": at_book.get("p_dd_over_tolerance")},
            "execution_quality": execution_quality, "margin_headroom": margin_headroom,
        },
        "verdict": verdict,
        "unused_upside_heat": round(max(0.0, float(room)), 6) if verdict == UNUSED_UPSIDE else 0.0,
        "gaps": gaps,
        "rule": ("A = deployed / floor; the floor is the principal's 20% and growth is free above "
                 "it to the 30% ceiling; only the ruin/tolerance bound (f_tail) may sit between "
                 "the free optimum and the book, and UNUSED_UPSIDE names anything else that does"),
    }
