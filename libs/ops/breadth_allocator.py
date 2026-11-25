"""One breadth allocator for every producer, miner and generator.

Decides WHICH candidate cells go to the judge first so the book spreads across
symbol x timeframe x mechanism family instead of piling into one corner.
It never deletes a candidate and never touches a certification gate: it only
orders and selects within a budget; everything not selected is returned as
deferred with a reason, and every cell the judge later runs is still a
charged trial.

Priority of a candidate =
    base_score                   (producer's own score, default 1)
  x orthogonality                (1 - |corr to existing book|; near-copies
                                  at or above dup_corr go to the back)
  x cost_viability               (exotics: real spread+commission vs the
                                  timeframe's cost budget; above it -> 0)
  x scarcity                     (1 / (1 + cell coverage)), so empty grid
                                  cells win over crowded ones
Selection is greedy by priority under share caps per cell, symbol, family and
timeframe, after a quota pass that gives each under-covered cell at least
`quota_per_empty_cell` picks.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from math import ceil, inf
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # numpy stays a lazy import at run time
    import numpy as np
    import numpy.typing as npt

# Round-trip cost budget in basis points of price by timeframe: a strategy on a
# slower timeframe carries a larger per-trade move, so it tolerates wider costs.
DEFAULT_COST_BUDGET_BPS: dict[str, float] = {
    "M1": 1.0, "M5": 2.0, "M15": 4.0, "M30": 6.0,
    "H1": 10.0, "H4": 20.0, "D1": 40.0, "W1": 80.0,
}


@dataclass(frozen=True)
class Candidate:
    cell_id: str
    symbol: str
    timeframe: str
    family: str
    producer: str = ""
    base_score: float = 1.0
    corr_to_book: float | None = None  # max |corr| of its returns to the live book
    cost_bps: float | None = None  # round-trip spread+commission, bps of price
    # True when base_score came from looking at performance (e.g. novelty()
    # marginal). Ranking on performance is a search: every such candidate is a
    # charged trial whether or not it is selected (Audit MF-1, 0015).
    performance_scored: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.symbol, self.timeframe, self.family)


@dataclass
class Limits:
    budget: int
    cell_share: float = 0.02
    symbol_share: float = 0.10
    family_share: float = 0.15
    timeframe_share: float = 0.30
    quota_per_empty_cell: int = 1
    dup_corr: float = 0.90
    cost_budget_bps: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_COST_BUDGET_BPS)
    )

    def cap(self, share: float, distinct: int = 1) -> int:
        """Share cap, never tighter than an even split over the values that
        exist: with only 3 symbols on offer a 10% symbol cap would idle 70%
        of the budget, so the even split (budget / 3) wins."""
        even = ceil(self.budget / max(1, distinct))
        return max(1, ceil(share * self.budget), even)


@dataclass
class Decision:
    selected: list[Candidate]
    deferred: list[tuple[Candidate, str]]
    priority: dict[str, float]
    # Trials to charge to the deflation count: every selected cell plus every
    # performance-scored candidate, selected or not. Callers MUST charge these.
    charged: list[Candidate] = field(default_factory=list)


def orthogonality(c: Candidate, dup_corr: float) -> float:
    if c.corr_to_book is None:
        return 1.0
    rho = min(1.0, abs(c.corr_to_book))
    if rho >= dup_corr:
        return 0.0
    return 1.0 - rho


def cost_viability(c: Candidate, budgets: Mapping[str, float]) -> float:
    if c.cost_bps is None:
        return 1.0
    limit = budgets.get(c.timeframe.upper(), inf)
    if limit == inf:
        return 1.0
    if c.cost_bps >= limit:
        return 0.0
    return 1.0 - c.cost_bps / limit


def allocate(
    candidates: Iterable[Candidate],
    limits: Limits,
    coverage: Mapping[tuple[str, str, str], int] | None = None,
) -> Decision:
    """coverage: judged-or-certified count per (symbol, timeframe, family) so far."""
    cov = Counter(dict(coverage or {}))
    cands = list(candidates)
    prio: dict[str, float] = {}
    for c in cands:
        prio[c.cell_id] = (
            max(0.0, c.base_score)
            * orthogonality(c, limits.dup_corr)
            * cost_viability(c, limits.cost_budget_bps)
            / (1.0 + cov[c.key])
        )

    live = [c for c in cands if prio[c.cell_id] > 0]

    def n_distinct(attr: str) -> int:
        return len({getattr(c, attr) for c in live})

    caps = {
        "cell": limits.cap(limits.cell_share, n_distinct("key")),
        "symbol": limits.cap(limits.symbol_share, n_distinct("symbol")),
        "family": limits.cap(limits.family_share, n_distinct("family")),
        "timeframe": limits.cap(limits.timeframe_share, n_distinct("timeframe")),
    }
    used: dict[str, Counter[str | tuple[str, str, str]]] = {k: Counter() for k in caps}
    selected: list[Candidate] = []
    taken: set[str] = set()

    def blocked(c: Candidate) -> str | None:
        dims: dict[str, str | tuple[str, str, str]] = {
            "cell": c.key, "symbol": c.symbol, "family": c.family, "timeframe": c.timeframe}
        for dim, val in dims.items():
            if used[dim][val] >= caps[dim]:
                return f"{dim}_cap"
        return None

    def take(c: Candidate) -> None:
        selected.append(c)
        taken.add(c.cell_id)
        used["cell"][c.key] += 1
        used["symbol"][c.symbol] += 1
        used["family"][c.family] += 1
        used["timeframe"][c.timeframe] += 1

    ranked = sorted(cands, key=lambda c: (-prio[c.cell_id], c.cell_id))
    # Quota pass: under-covered cells first, best candidate of each.
    if limits.quota_per_empty_cell > 0:
        for c in ranked:
            if len(selected) >= limits.budget:
                break
            if prio[c.cell_id] <= 0 or cov[c.key] > 0:
                continue
            if used["cell"][c.key] >= limits.quota_per_empty_cell:
                continue
            if blocked(c) is None:
                take(c)
    # Main pass by priority under caps.
    for c in ranked:
        if len(selected) >= limits.budget:
            break
        if c.cell_id in taken or prio[c.cell_id] <= 0:
            continue
        if blocked(c) is None:
            take(c)

    deferred: list[tuple[Candidate, str]] = []
    for c in ranked:
        if c.cell_id in taken:
            continue
        if orthogonality(c, limits.dup_corr) == 0.0:
            why = "near_duplicate_of_book"
        elif cost_viability(c, limits.cost_budget_bps) == 0.0:
            why = "cost_exceeds_timeframe_budget"
        elif len(selected) >= limits.budget:
            why = blocked(c) or "budget"
        else:
            why = blocked(c) or "zero_priority"
        deferred.append((c, why))
    charged = list(selected) + [
        c for c in ranked if c.performance_scored and c.cell_id not in taken
    ]
    return Decision(
        selected=selected, deferred=deferred, priority=prio, charged=charged
    )


def coverage_report(keys: Iterable[tuple[str, str, str]]) -> dict[str, Any]:
    """Spread metrics for the coverage map: per dimension the share of the top
    value and the effective number of values (1 / Herfindahl)."""
    ks = list(keys)
    out: dict[str, Any] = {"n": len(ks)}
    if not ks:
        return out
    dims = {"symbol": 0, "timeframe": 1, "family": 2}
    for dim, i in dims.items():
        cnt = Counter(k[i] for k in ks)
        shares = [v / len(ks) for v in cnt.values()]
        hhi = sum(s * s for s in shares)
        out[dim] = {
            "distinct": len(cnt),
            "top": cnt.most_common(1)[0][0],
            "top_share": round(max(shares), 4),
            "effective_n": round(1.0 / hhi, 2),
        }
    cells = Counter(ks)
    out["cells"] = {
        "distinct": len(cells),
        "top_share": round(cells.most_common(1)[0][1] / len(ks), 4),
    }
    return out


# --- Evolution: the controller tunes itself from measured results ----------
# Target metric: new ORTHOGONAL certified edges per judged trial. Each pass the
# caller records, per grid cell, trials judged and orthogonal edges certified.


def yield_multipliers(
    stats: Mapping[tuple[str, str, str], tuple[int, int]],
    prior_edges: float = 1.0,
    prior_trials: float = 200.0,
    floor: float = 0.25,
) -> dict[tuple[str, str, str], float]:
    """Per cell (trials, orthogonal_edges) -> multiplier for base_score.

    Beta-style shrinkage toward the pooled rate, relative to that rate, with a
    floor so a cell is never starved of exploration. Cells never tried are 1.0.
    """
    tot_t = sum(t for t, _ in stats.values())
    tot_e = sum(e for _, e in stats.values())
    pooled = (tot_e + prior_edges) / (tot_t + prior_trials)
    out = {}
    for key, (t, e) in stats.items():
        rate = (e + pooled * prior_trials) / (t + prior_trials)
        out[key] = max(floor, rate / pooled) if pooled > 0 else 1.0
    return out


def evolve_limits(limits: Limits,
                  history: list[dict[str, Any]]) -> tuple[Limits, list[str]]:
    """Adjust caps and quotas from recent passes; returns (new limits, journal).

    history rows: {"effective_n_cells": float, "orth_edges": int, "trials": int,
                   "edges_from_empty": int, "trials_from_empty": int}.
    Rules (bounded, one step per call, every change journalled):
    - empty cells out-yield the rest -> raise quota_per_empty_cell (max 5);
      they under-yield -> lower it (min 1, never 0: exploration stays).
    - edges per trial falling while spread (effective_n) is flat or falling ->
      tighten cell_share (min 0.005) to force spread.
    - edges per trial rising -> keep; record it.
    dup_corr and the cost budgets are not tuned here: they protect
    independence and fills and only change through Audit.
    """
    journal: list[str] = []
    if len(history) < 2:
        return limits, ["insufficient history"]
    new = Limits(**{**limits.__dict__})
    last, prev = history[-1], history[-2]

    def rate(e: int, t: int) -> float:
        return e / t if t else 0.0

    r_empty = rate(last.get("edges_from_empty", 0), last.get("trials_from_empty", 0))
    rest_e = last.get("orth_edges", 0) - last.get("edges_from_empty", 0)
    rest_t = last.get("trials", 0) - last.get("trials_from_empty", 0)
    r_rest = rate(rest_e, rest_t)
    if last.get("trials_from_empty", 0) and r_empty > r_rest:
        new.quota_per_empty_cell = min(5, limits.quota_per_empty_cell + 1)
    elif last.get("trials_from_empty", 0) and r_empty < 0.5 * r_rest:
        new.quota_per_empty_cell = max(1, limits.quota_per_empty_cell - 1)
    if new.quota_per_empty_cell != limits.quota_per_empty_cell:
        journal.append(
            f"quota_per_empty_cell {limits.quota_per_empty_cell}"
            f"->{new.quota_per_empty_cell} (empty {r_empty:.4f} vs rest {r_rest:.4f})"
        )

    r_now = rate(last.get("orth_edges", 0), last.get("trials", 0))
    r_prev = rate(prev.get("orth_edges", 0), prev.get("trials", 0))
    spread_flat = last.get("effective_n_cells", 0) <= prev.get("effective_n_cells", 0)
    if r_now < r_prev and spread_flat:
        new.cell_share = max(0.005, round(limits.cell_share * 0.8, 4))
        journal.append(
            f"cell_share {limits.cell_share}->{new.cell_share} "
            f"(edge rate {r_prev:.4f}->{r_now:.4f}, spread not rising)"
        )
    if not journal:
        journal.append(f"no change (edge rate {r_prev:.4f}->{r_now:.4f})")
    return new, journal


# --- Institutional novelty: residualise, hard pool-correlation reject, -----
# --- and score by marginal contribution to the book (appraisal ratio). -----
# WorldQuant-style: a new alpha is refused at submission when its correlation
# to the existing pool is too high, and is valued by what it adds to the
# combined book, not by its standalone Sharpe. Adding an asset to a book with
# max Sharpe SR_b gives SR_new^2 = SR_b^2 + AR^2, where AR is the appraisal
# ratio (alpha / residual sd) of the candidate regressed on the book.

HARD_POOL_CORR = 0.70


def residualise(returns: npt.ArrayLike, factors: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """OLS residual of a return series on common factors (T x K), with intercept
    kept in the residual so alpha is not removed."""
    import numpy as np

    y = np.asarray(returns, dtype=float)
    f = np.asarray(factors, dtype=float)
    if f.ndim == 1:
        f = f[:, None]
    x = np.column_stack([np.ones(len(y)), f])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid: npt.NDArray[np.float64] = y - x[:, 1:] @ beta[1:]
    return resid


def max_pool_corr(residual: npt.ArrayLike, pool_residuals: Iterable[npt.ArrayLike]) -> float:
    """Max |corr| of a residual series to any residual series in the pool."""
    import numpy as np

    r = np.asarray(residual, dtype=float)
    best = 0.0
    for p in pool_residuals:
        q = np.asarray(p, dtype=float)
        if r.std() == 0 or q.std() == 0:
            continue
        best = max(best, abs(float(np.corrcoef(r, q)[0, 1])))
    return best


def appraisal_ratio(candidate: npt.ArrayLike, book: npt.ArrayLike) -> float:
    """Per-period appraisal ratio of candidate vs the book's return series."""
    import numpy as np

    y = np.asarray(candidate, dtype=float)
    b = np.asarray(book, dtype=float)
    x = np.column_stack([np.ones(len(y)), b])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    sd = float(resid.std(ddof=2)) if len(y) > 2 else 0.0
    return float(beta[0] / sd) if sd > 0 else 0.0


def novelty(
    candidate_returns: npt.ArrayLike,
    *,
    factors: npt.ArrayLike | None = None,
    pool_residuals: Iterable[npt.ArrayLike] = (),
    book_returns: npt.ArrayLike | None = None,
    hard_corr: float = HARD_POOL_CORR,
) -> dict[str, Any]:
    """Intake novelty verdict for one candidate with a return history.

    Returns {"reject", "pool_corr", "marginal", "charge"}. reject is
    a hard intake refusal (not judged, not a charged trial) when the factor
    residual correlates >= hard_corr with any pooled residual. marginal is the
    appraisal ratio vs the book (>= 0), to use as Candidate.base_score.
    charge is True whenever marginal was computed from performance: build the
    Candidate with performance_scored=True so allocate() charges it even when
    it is not selected. A pool-correlation refusal alone is not charged.
    """
    res = (
        residualise(candidate_returns, factors)
        if factors is not None
        else candidate_returns
    )
    pc = max_pool_corr(res, pool_residuals)
    marginal = (
        max(0.0, appraisal_ratio(candidate_returns, book_returns))
        if book_returns is not None
        else 1.0
    )
    return {
        "reject": pc >= hard_corr,
        "pool_corr": pc,
        "marginal": marginal,
        "charge": book_returns is not None,
    }
