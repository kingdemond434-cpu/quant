"""The Kelly SURFACE of a book on the desk's sampled worlds, not one Kelly number.

    g(f) = E[ log(1 + f h'R) ]     for f on a grid from 0 to 2x the book

evaluated per world, so the surface carries what a point estimate cannot: the robust growth (the
lower tail of worlds), the drawdown distribution at each fraction, the probability of breaching
the principal's stated drawdown tolerance, and the probability of ruin (a world in which the
scaled book is wiped out). From those come the fractions that matter:

    f_opt       the fraction that maximises mean growth across worlds
    f_robust    the fraction that maximises the alpha-quantile of growth (the pessimist's Kelly)
    f_tail      the largest fraction at which P(drawdown > tolerance) <= alpha and P(ruin) = 0

`f_tail` is the ruin/stop-out constraint the objective carries -- the ONE constraint the growth
governance keeps -- expressed as a heat: `heat_tail_max = f_tail x total heat`. The allocator
sits below it because the worlds say so, never because a constant does; and when `f_tail` is
above the deployed book the surface says, in a number, how much more the evidence would bear.

`tolerance` is the principal's MAX_DRAWDOWN_TOLERANCE; `alpha` is the objective's own CVaR tail
fraction -- both already stated elsewhere, neither chosen here.

THE SURVIVAL ENVELOPE, AND WHY IT NOW BINDS (principal, 2026-09-07)

    "remove 30 heat cap fully so if growth optimum says 35-40 that's allowed aswell until it
     computes something diff the next few moments later"

`f_tail` was measured every pass and bound NOTHING. It reached `aggression.explain` as an AUDIT
input and the operative bar stayed `HEAT_HARD_CEILING = 0.30`, a constant recorded from one
world set on 2026-09-02. `envelope()` below turns the same rows into the bar itself:

    H_max = the highest SAMPLED heat at which every survival constraint still holds

    P(ruin) = 0                        no world in which the account is destroyed
    P(drawdown > tolerance) <= alpha   the principal's stated 35% tolerance, at the CVaR fraction
    margin use <= MAX_MARGIN_USE       the broker's own feasibility, when the box has measured it
    capacity(h) > 0                    a heat the market cannot absorb is not a heat

and NEVER past the highest heat the surface actually sampled. That last clause is what separates
this from removing the limit: a heat nobody simulated is not a heat anybody certified, so the
envelope grows by MEASURING further out, not by asserting further out. Absence is never
permission -- an unreadable or too-thin surface returns the recorded constant, unchanged.

WHAT THIS DELIBERATELY DOES NOT DO. It does not raise heat. It removes an ARBITRARY bound and
replaces it with an ECONOMIC one, which on a thin book is TIGHTER than 30% ever was: a book that
ruins in one sampled world at 22% is bounded at 21%, where the constant would have allowed 30%.
The bound moves every pass, in both directions, because it is a reading of the current
opportunity set rather than a memory of an old one.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

FRACTIONS: tuple[float, ...] = tuple(round(x, 2) for x in np.arange(0.0, 2.01, 0.1))

#: Account margin the book may consume before the broker's own feasibility binds. Declared here
#: because it is a BROKER fact, not a preference: past this a margin call liquidates positions
#: the desk chose to hold, which is the one failure no growth argument survives. Only applied
#: when the box has actually measured margin use -- an unmeasured margin never licenses heat.
MAX_MARGIN_USE = 0.50

#: Sampled heats an envelope needs before it may bind. Two points cannot show where a constraint
#: turns, and a bound read off two points is a bound read off noise.
MIN_ENVELOPE_ROWS = 3

MEASURED, UNMEASURED = "MEASURED", "UNMEASURED"


def _paths(port: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-world (growth/day, max drawdown fraction, ruined) for a (W, T) return path."""
    one_plus = 1.0 + port
    ruined = np.any(one_plus <= 1e-9, axis=1)
    safe = np.where(one_plus > 1e-9, one_plus, 1.0)
    logs = np.log(safe)
    growth = logs.mean(axis=1)
    cum = np.cumsum(logs, axis=1)
    peak = np.maximum.accumulate(np.concatenate([np.zeros((cum.shape[0], 1)), cum], axis=1),
                                 axis=1)[:, 1:]
    dd_log = np.max(peak - cum, axis=1)
    dd_frac = 1.0 - np.exp(-dd_log)
    dd_frac[ruined] = 1.0
    growth = np.where(ruined, -np.inf, growth)
    return growth, dd_frac, ruined


def surface(worlds: Any, book: Mapping[str, float], *, tolerance: float, alpha: float,
            fractions: tuple[float, ...] = FRACTIONS) -> dict[str, Any]:
    names = tuple(worlds.names)
    h = np.array([float(book.get(n, 0.0)) for n in names], dtype=np.float32)
    total = float(h.sum())
    if total <= 0 or worlds.r.size == 0:
        return {"total_heat": total, "rows": [], "note": "empty book"}
    port = np.einsum("wtn,n->wt", worlds.r, h, optimize=True).astype(np.float64)
    rows = []
    for f in fractions:
        g, dd, ruined = _paths(f * port)
        fin = g[np.isfinite(g)]
        q = float(np.quantile(fin, alpha)) if fin.size else float("-inf")
        rows.append({"f": float(f), "heat": round(f * total, 6),
                     "mean_growth": (float(fin.mean()) if fin.size else float("-inf")),
                     "robust_growth": q,
                     "worst_decile_growth": (float(np.quantile(fin, 0.1)) if fin.size
                                             else float("-inf")),
                     "p_ruin": float(ruined.mean()),
                     "p_dd_over_tolerance": float((dd > tolerance).mean()),
                     "dd_median": float(np.median(dd)), "dd_p90": float(np.quantile(dd, 0.9))})
    _derivatives(rows)
    finite = [r for r in rows if np.isfinite(r["mean_growth"])]
    f_opt = max(finite, key=lambda r: r["mean_growth"])["f"] if finite else 0.0
    f_robust = max(finite, key=lambda r: r["robust_growth"])["f"] if finite else 0.0
    ok = [r["f"] for r in rows if r["p_ruin"] == 0.0 and r["p_dd_over_tolerance"] <= alpha]
    f_tail = max(ok) if ok else 0.0
    return {"total_heat": round(total, 6), "tolerance": tolerance, "alpha": alpha,
            "f_opt": f_opt, "f_robust": f_robust, "f_tail": f_tail,
            "heat_opt": round(f_opt * total, 6), "heat_robust": round(f_robust * total, 6),
            "heat_tail_max": round(f_tail * total, 6),
            "heat_sampled_max": round(max((r["heat"] for r in rows), default=0.0), 6),
            "at_book": next((r for r in rows if abs(r["f"] - 1.0) < 1e-9), None),
            "rows": rows}


def _derivatives(rows: list[dict[str, Any]]) -> None:
    """Attach dG/dH and d2G/dH2 to each row, in place, by central difference on the heat grid.

    THE NUMBER THE PRINCIPAL ASKED FOR (2026-09-07): "The critical number is dE[logW]/dH. Keep
    adding risk while this remains positive. Stop where it is zero. That is the true growth peak."

    Central differences on an unevenly spaced grid, because the heat grid IS uneven -- the
    fraction grid is uniform in f but a caller may hand any grid, and a one-sided difference at
    the peak reports the slope of the wrong side. Endpoints get the one-sided difference they can
    have. A row whose neighbours are non-finite (a ruined world set) gets None rather than a
    fabricated slope: an infinite growth difference is not a derivative.
    """
    pts = [(float(r["heat"]), float(r["mean_growth"])) for r in rows]
    n = len(pts)
    for i, r in enumerate(rows):
        r["dG_dH"] = None
        r["d2G_dH2"] = None
        if n < 2:
            continue
        lo, hi = max(0, i - 1), min(n - 1, i + 1)
        (h0, g0), (h1, g1) = pts[lo], pts[hi]
        if hi != lo and math.isfinite(g0) and math.isfinite(g1) and h1 > h0:
            r["dG_dH"] = round((g1 - g0) / (h1 - h0), 8)
        if 0 < i < n - 1:
            (hc, gc) = pts[i]
            if all(math.isfinite(g) for g in (g0, gc, g1)) and h1 > hc > h0:
                # Uneven-grid second difference: 2*(g0*(h1-hc) - gc*(h1-h0) + g1*(hc-h0))
                #                                / ((h1-h0)*(hc-h0)*(h1-hc))
                den = (h1 - h0) * (hc - h0) * (h1 - hc)
                if den > 0:
                    num = 2.0 * (g0 * (h1 - hc) - gc * (h1 - h0) + g1 * (hc - h0))
                    r["d2G_dH2"] = round(num / den, 8)


def envelope(rows: Sequence[Mapping[str, Any]], *, alpha: float, fallback: float,
             margin_use: Mapping[float, float] | None = None,
             capacity_max: float | None = None,
             max_margin_use: float = MAX_MARGIN_USE,
             min_rows: int = MIN_ENVELOPE_ROWS) -> dict[str, Any]:
    """The highest heat the SURVIVAL constraints still allow, and which one binds.

    This is the bar that replaces `HEAT_HARD_CEILING` as the operative ceiling. It is not a
    preference and it contains no aesthetic number: every clause is a fact about survival or
    feasibility, in the principal's own list --

        P(broker liquidation) < eps      -> `p_ruin == 0` on the sampled worlds
        P(DD > D_max) < eps              -> `p_dd_over_tolerance <= alpha`
        margin usage < M_max             -> `margin_use[h] <= max_margin_use`, when measured
        capacity(h) > 0                  -> `h <= capacity_max`, when measured
        1 + h'r > 0 in every world       -> `p_ruin == 0` again, which is what ruin means here

    THE CONTIGUITY RULE, and it is the difference between a bound and a cherry-pick. The ceiling
    is the top of the UNBROKEN feasible run starting at the lowest sampled heat -- not the highest
    feasible row anywhere on the grid. A surface that is feasible at 10%, infeasible at 15% and
    feasible again at 40% is telling you the 40% reading is noise (or that the grid straddles a
    regime the sampler resolved badly); taking 40% from it would size into the gap. Taking 10%
    cannot.

    ABSENCE IS NEVER PERMISSION. Fewer than `min_rows` sampled heats, no feasible row at all, or
    a non-finite grid returns `fallback` with status UNMEASURED. The fallback is the recorded
    constant, so a monitoring failure holds the desk exactly where the old law held it and never
    one basis point above.

    Returns the ceiling, its status, the binding constraint's name, and every clause's own bound
    so the artifact can be read as an argument rather than an assertion.
    """
    clean = [r for r in rows
             if isinstance(r, Mapping) and isinstance(r.get("heat"), (int, float))
             and math.isfinite(float(r["heat"])) and float(r["heat"]) > 0.0]
    clean.sort(key=lambda r: float(r["heat"]))
    if len(clean) < int(min_rows):
        return {"ceiling": float(fallback), "status": UNMEASURED, "binding": "fallback",
                "n_rows": len(clean), "sampled_max": None,
                "why": (f"{len(clean)} sampled heat(s) on the survival surface, below the "
                        f"{min_rows} floor -- holding the recorded {fallback:.0%} bound. "
                        "Absence is not permission.")}

    mu = {round(float(k), 6): float(v) for k, v in (margin_use or {}).items()}

    def _clauses(r: Mapping[str, Any]) -> list[str]:
        """Every survival clause this heat FAILS, named. Empty means feasible."""
        bad: list[str] = []
        p_ruin = r.get("p_ruin")
        if not isinstance(p_ruin, (int, float)) or float(p_ruin) > 0.0:
            bad.append("p_ruin")
        p_dd = r.get("p_dd_over_tolerance")
        if not isinstance(p_dd, (int, float)) or float(p_dd) > float(alpha) + 1e-12:
            bad.append("p_dd_over_tolerance")
        m = mu.get(round(float(r["heat"]), 6))
        if m is not None and m > float(max_margin_use) + 1e-12:
            bad.append("margin_use")
        if capacity_max is not None and float(r["heat"]) > float(capacity_max) + 1e-12:
            bad.append("capacity")
        return bad

    feasible: list[Mapping[str, Any]] = []
    stopped_by: list[str] = []
    for r in clean:
        bad = _clauses(r)
        if bad:
            stopped_by = bad
            break
        feasible.append(r)

    sampled_max = float(clean[-1]["heat"])
    if not feasible:
        first_bad = _clauses(clean[0])
        return {"ceiling": float(fallback), "status": UNMEASURED, "binding": "fallback",
                "n_rows": len(clean), "sampled_max": round(sampled_max, 6),
                "failed_at_lowest": first_bad,
                "why": (f"the lowest sampled heat ({float(clean[0]['heat']):.2%}) already "
                        f"violates {', '.join(first_bad)} -- the surface cannot bound anything, "
                        f"so the recorded {fallback:.0%} constant stands. A surface that refuses "
                        "its own smallest book is a measurement failure, not a licence.")}

    ceiling = float(feasible[-1]["heat"])
    at_edge = ceiling >= sampled_max - 1e-12
    binding = "measurement_edge" if at_edge else (stopped_by[0] if stopped_by else "survival")
    why = (f"survival ceiling {ceiling:.2%}: every clause holds up to it "
           f"(P(ruin)=0, P(DD>tolerance)<={alpha:.0%}"
           + (", margin" if mu else "") + (", capacity" if capacity_max is not None else "")
           + ")")
    why += (f" and that is the HIGHEST heat the surface sampled -- the bound is the edge of the "
            f"measurement, not of the opportunity; sample further out to earn more."
            if at_edge else
            f", and {', '.join(stopped_by)} fails at the next sampled heat.")
    return {"ceiling": ceiling, "status": MEASURED, "binding": binding,
            "n_rows": len(clean), "n_feasible": len(feasible),
            "sampled_max": round(sampled_max, 6), "stopped_by": stopped_by,
            "alpha": float(alpha), "max_margin_use": float(max_margin_use),
            "capacity_max": (None if capacity_max is None else float(capacity_max)),
            "fallback": float(fallback), "why": why}
