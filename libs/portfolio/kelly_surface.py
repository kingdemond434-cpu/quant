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
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

FRACTIONS: tuple[float, ...] = tuple(round(x, 2) for x in np.arange(0.0, 2.01, 0.1))


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
    finite = [r for r in rows if np.isfinite(r["mean_growth"])]
    f_opt = max(finite, key=lambda r: r["mean_growth"])["f"] if finite else 0.0
    f_robust = max(finite, key=lambda r: r["robust_growth"])["f"] if finite else 0.0
    ok = [r["f"] for r in rows if r["p_ruin"] == 0.0 and r["p_dd_over_tolerance"] <= alpha]
    f_tail = max(ok) if ok else 0.0
    return {"total_heat": round(total, 6), "tolerance": tolerance, "alpha": alpha,
            "f_opt": f_opt, "f_robust": f_robust, "f_tail": f_tail,
            "heat_opt": round(f_opt * total, 6), "heat_robust": round(f_robust * total, 6),
            "heat_tail_max": round(f_tail * total, 6),
            "at_book": next((r for r in rows if abs(r["f"] - 1.0) < 1e-9), None),
            "rows": rows}
