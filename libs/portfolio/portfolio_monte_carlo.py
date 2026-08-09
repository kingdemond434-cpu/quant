"""DEPENDENCE-PRESERVING PORTFOLIO MONTE CARLO — the event that kills a book is the joint one.

THE DEFECT THIS REMOVES, and this desk currently HAS it. `libs/discovery/monte_carlo_survival.py`
reshuffles ONE strategy's trades, and `libs/portfolio/strategy_pool.sizing_drawdown` sizes each
member off its own reshuffled tail. Both are correct for the question they ask. Neither asks the
question that decides whether a multi-strategy book survives:

    WHAT HAPPENS ON THE DAY THEY ALL LOSE AT ONCE?

**INDEPENDENTLY SHUFFLING EACH STRATEGY DESTROYS THE ONLY THING WORTH MEASURING.** Give twenty
strategies their own random orderings and their bad days scatter across the calendar; the portfolio
path smooths into something that never happened, and the resulting drawdown estimate is not
conservative, it is fiction in the flattering direction. The diversification the simulation reports
is diversification the simulation manufactured.

So every draw here resamples **one block of TIME** and applies that same block to EVERY strategy at
once. Whatever was true on those days -- the shared regime, the common factor, the simultaneous
margin call, the correlated deleveraging, the fact that basis and momentum and alt-beta all belong
to one crowded trade when funding reverses -- travels intact into the resampled path, because the
days travel together. Cross-sectional dependence is not modelled. It is never broken.

**AND THE GAP IS REPORTED, NOT ASSUMED.** `dependence_blindness` runs the wrong method deliberately
and divides: it is the factor by which per-strategy shuffling understates portfolio drawdown on
THIS book. On a genuinely uncorrelated book it is ~1.0 and the naive method was fine. On a crypto
book where everything is one leverage trade wearing five names, it is not, and the number says by
how much.

**CO-ACTIVATION IS A SEPARATE FINDING FROM CORRELATION.** Two strategies can have low return
correlation and still be in the market at the same instant, consuming margin at the same instant,
and needing liquidity at the same instant. `stress_coactivation` measures the joint ACTIVE state in
the worst decile of portfolio days, because margin does not care that the returns were uncorrelated.

Reads paths, returns numbers. Sizes nothing and vetoes nothing -- `libs/risk/` owns the limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from libs.validation.bootstrap import stationary_block_indices

__all__ = [
    "MIN_COMMON_MARKS",
    "PortfolioMCResult",
    "StrategyPath",
    "dependence_blindness",
    "portfolio_monte_carlo",
    "stress_coactivation",
    "summarise",
]

#: Below this many aligned marks a resampled tail describes the window, not the book. Blocks make
#: it worse: a 20-day block drawn from 40 marks is the same fortnight twice.
MIN_COMMON_MARKS: int = 60


@dataclass(frozen=True)
class StrategyPath:
    """One strategy's history ON A COMMON CLOCK with every other path in the book.

    THE COMMON CLOCK IS THE WHOLE POINT. Index i must be the same calendar instant across every
    path, because the entire method rests on drawing index i once and applying it everywhere. Two
    series that merely have the same LENGTH are not aligned, and a caller who passes those gets a
    confident simulation of a portfolio that never existed. `portfolio_monte_carlo` refuses ragged
    input; it cannot detect misalignment at equal length, so that stays the caller's contract.
    """

    strategy_id: str
    #: Simple per-period returns on the common clock.
    returns: tuple[float, ...] = field(default_factory=tuple)
    #: In-market flag per period. Empty = inferred from a non-zero return, which UNDERSTATES
    #: activity for a strategy that was flat while holding, so pass it when it is known.
    active: tuple[bool, ...] = field(default_factory=tuple)
    #: Margin consumed per period as a fraction of portfolio equity. Empty = UNMEASURED, and the
    #: concurrent-margin distribution then reports absence rather than zero.
    margin: tuple[float, ...] = field(default_factory=tuple)
    #: Capital weight in the book.
    weight: float = 1.0

    @property
    def n(self) -> int:
        return len(self.returns)

    def active_mask(self) -> np.ndarray:
        if self.active:
            return np.asarray(self.active, dtype=bool)
        return np.asarray(np.asarray(self.returns, dtype=float) != 0.0, dtype=bool)


@dataclass(frozen=True)
class PortfolioMCResult:
    """Everything the joint simulation can say. Nones are UNMEASURED, never zero."""

    draws: int
    marks: int
    strategies: int
    mc_drawdown_p50: float
    mc_drawdown_p95: float
    mc_drawdown_p99: float
    mc_ruin_probability: float
    tail_portfolio_elog: float
    median_portfolio_elog: float
    concurrent_margin_p95: float | None
    concurrent_margin_max: float | None
    dependence_blindness: float | None
    why: str


def _max_drawdown(equity: np.ndarray) -> np.ndarray:
    """Max fractional drawdown per row of an (draws, marks) equity matrix."""
    peaks = np.maximum.accumulate(equity, axis=1)
    # Equity is built from (1+r) products and floored below, so peaks are strictly positive and
    # the division cannot raise -- which matters here because filterwarnings=error makes a
    # RuntimeWarning a test failure rather than a silent NaN.
    return np.asarray(np.max(1.0 - equity / peaks, axis=1), dtype=float)


def _weighted_matrix(paths: list[StrategyPath]) -> np.ndarray:
    """(marks,) portfolio returns from weighted per-strategy returns."""
    w = np.asarray([p.weight for p in paths], dtype=float)
    r = np.asarray([p.returns for p in paths], dtype=float)
    return np.asarray(w @ r, dtype=float)


def _equity(sampled: np.ndarray) -> np.ndarray:
    """Compound (draws, marks) returns, floored just above -1 so a path cannot go non-positive.

    A -100% period ends the book in reality; here it would produce log(0) and poison every summary
    statistic downstream. Flooring names the loss as total rather than propagating a NaN, and the
    ruin probability -- which is the number that actually matters at that point -- still fires.
    """
    return np.cumprod(1.0 + np.maximum(sampled, -0.999999), axis=1)


def portfolio_monte_carlo(paths: list[StrategyPath], *, draws: int = 2000,
                          mean_block: float = 5.0, ruin_drawdown: float = 0.5,
                          seed: int = 12345) -> PortfolioMCResult | None:
    """Synchronized block resampling across the whole book. None when it cannot be run honestly.

    ONE BLOCK OF TIME PER DRAW, APPLIED TO EVERY STRATEGY. That single choice is the difference
    between this and the per-strategy Monte Carlo the desk already had: the days travel together,
    so the shared regime, the common factor and the simultaneous margin call travel with them.
    """
    if not paths:
        return None
    n = paths[0].n
    if any(p.n != n for p in paths):
        return None
    if n < MIN_COMMON_MARKS:
        return None
    if draws < 1:
        raise ValueError("draws must be >= 1")
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")

    rng = np.random.default_rng(seed)
    port = _weighted_matrix(paths)
    margins = [np.asarray(p.margin, dtype=float) for p in paths if len(p.margin) == n]
    margin_total = (np.sum(margins, axis=0) if margins else None)

    idx = np.stack([stationary_block_indices(n, mean_block, rng) for _ in range(draws)])
    sampled = port[idx]
    equity = _equity(sampled)
    dds = _max_drawdown(equity)
    finals = equity[:, -1]
    logs = np.log(finals)

    p50, p95, p99 = (float(np.percentile(dds, q)) for q in (50, 95, 99))
    ruin = float(np.mean(dds >= ruin_drawdown))
    tail_cut = float(np.percentile(logs, 5))
    tail = float(np.mean(logs[logs <= tail_cut])) if np.any(logs <= tail_cut) else float(logs.min())
    median = float(np.median(logs))

    cm_p95 = cm_max = None
    if margin_total is not None:
        cm = margin_total[idx]
        cm_p95 = float(np.percentile(cm, 95))
        cm_max = float(np.max(cm))

    blind = dependence_blindness(paths, draws=draws, mean_block=mean_block, seed=seed)
    return PortfolioMCResult(
        draws=draws, marks=n, strategies=len(paths),
        mc_drawdown_p50=p50, mc_drawdown_p95=p95, mc_drawdown_p99=p99,
        mc_ruin_probability=ruin, tail_portfolio_elog=tail, median_portfolio_elog=median,
        concurrent_margin_p95=cm_p95, concurrent_margin_max=cm_max,
        dependence_blindness=blind,
        why=(f"{draws} synchronized block draws over {n} common marks, {len(paths)} strategies, "
             f"mean block {mean_block:g}. Portfolio drawdown p95 {p95:.1%}, p99 {p99:.1%}; "
             f"P(drawdown >= {ruin_drawdown:.0%}) = {ruin:.1%}. Median terminal log growth "
             f"{median:+.4f}, worst-5% mean {tail:+.4f}. One block of TIME is drawn per draw and "
             "applied to every strategy, so whatever was jointly true on those days survives the "
             "resampling"))


def dependence_blindness(paths: list[StrategyPath], *, draws: int = 2000,
                         mean_block: float = 5.0, seed: int = 12345) -> float | None:
    """How much per-strategy shuffling UNDERSTATES portfolio drawdown. None below two strategies.

    Runs the wrong method on purpose. Each strategy gets its OWN independent block draw, which is
    exactly what a desk does when it Monte-Carlos its strategies one at a time and adds the
    results up. The ratio synchronized/independent is the diversification the naive method
    invented.

    1.0 means the book really is independent and the cheap method was fine. Above 1.0 means the
    per-strategy tails are being added as if the bad days never coincide -- and in crypto, where
    basis, momentum, alt-beta and liquidation risk collapse into one factor under stress, they do.
    """
    if len(paths) < 2:
        return None
    n = paths[0].n
    if any(p.n != n for p in paths) or n < MIN_COMMON_MARKS:
        return None
    w = np.asarray([p.weight for p in paths], dtype=float)
    r = np.asarray([p.returns for p in paths], dtype=float)

    rng = np.random.default_rng(seed)
    shared = np.stack([stationary_block_indices(n, mean_block, rng) for _ in range(draws)])
    sync = _max_drawdown(_equity((w @ r)[shared]))

    rng2 = np.random.default_rng(seed + 1)
    indep = np.zeros((draws, n), dtype=float)
    for k in range(len(paths)):
        own = np.stack([stationary_block_indices(n, mean_block, rng2) for _ in range(draws)])
        indep += w[k] * r[k][own]
    naive = _max_drawdown(_equity(indep))

    s95, n95 = float(np.percentile(sync, 95)), float(np.percentile(naive, 95))
    if n95 <= 1e-9:
        return None
    return s95 / n95


def stress_coactivation(paths: list[StrategyPath], *,
                        worst_decile: bool = True) -> tuple[float | None, str]:
    """Share of the book simultaneously ACTIVE on the worst portfolio days.

    MARKET-NEUTRAL IS NOT LIQUIDATION-NEUTRAL, and low return correlation is not the same claim as
    low simultaneous exposure. Two strategies whose returns barely correlate can still both be in
    the market, both consuming margin and both needing to exit, on precisely the day liquidity is
    gone. This measures that directly rather than inferring it from a covariance.
    """
    if len(paths) < 2:
        return None, "fewer than two strategies -- co-activation is not yet a question"
    n = paths[0].n
    if any(p.n != n for p in paths):
        return None, ("paths are ragged, so there is no common clock and 'the same day' has no "
                      "meaning. UNMEASURED, and the alignment is the caller's contract")
    if n == 0:
        return None, "no marks recorded -- co-activation is UNMEASURED"
    port = _weighted_matrix(paths)
    masks = np.stack([p.active_mask() for p in paths])
    if worst_decile:
        cut = float(np.percentile(port, 10))
        sel = port <= cut
    else:
        sel = np.ones(n, dtype=bool)
    if not np.any(sel):
        return None, "no days selected -- co-activation is UNMEASURED"
    stress_rate = float(np.mean(masks[:, sel]))
    base_rate = float(np.mean(masks))
    lift = (stress_rate / base_rate) if base_rate > 1e-9 else None
    return stress_rate, (
        f"{stress_rate:.0%} of the book is simultaneously in the market on the worst decile of "
        f"portfolio days, against {base_rate:.0%} on an average day"
        + (f" -- a lift of {lift:.2f}x" if lift is not None else "")
        + (". Exposure CONCENTRATES into the bad days: the strategies are finding the same state, "
           "and margin does not care that their returns were uncorrelated"
           if lift is not None and lift > 1.1 else
           ". Exposure does not concentrate into the bad days, which is the good case and is worth "
           "having measured rather than assumed"))


def summarise(paths: list[StrategyPath], *, draws: int = 2000, mean_block: float = 5.0,
              ruin_drawdown: float = 0.5, seed: int = 12345) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not paths:
        return {"measured": False, "headline": (
            "no strategy paths recorded -- portfolio drawdown, ruin and margin concurrency are "
            "UNMEASURED. Per-strategy Monte Carlo cannot answer them: it is the joint event that "
            "kills a book, and independent shuffling is precisely what destroys it")}
    n0 = paths[0].n
    if any(p.n != n0 for p in paths):
        return {"measured": False, "strategies": len(paths), "headline": (
            "paths are RAGGED -- lengths " + str(sorted({p.n for p in paths})) + ". Synchronized "
            "resampling needs a common clock, because the entire method is drawing one day and "
            "applying it everywhere. Refused rather than aligned by truncation, which would "
            "silently discard the earliest history of the longest-running strategy")}
    if n0 < MIN_COMMON_MARKS:
        return {"measured": False, "strategies": len(paths), "marks": n0, "headline": (
            f"{n0} common mark(s) against a floor of {MIN_COMMON_MARKS}. A block drawn from a "
            "window this short is the same fortnight repeated, and the tail it produces describes "
            "the window rather than the book")}
    res = portfolio_monte_carlo(paths, draws=draws, mean_block=mean_block,
                                ruin_drawdown=ruin_drawdown, seed=seed)
    if res is None:
        return {"measured": False, "strategies": len(paths), "headline": (
            "portfolio Monte Carlo could not be run on these paths -- UNMEASURED")}
    coact, cwhy = stress_coactivation(paths)
    blind = res.dependence_blindness
    return {
        "measured": True,
        "strategies": res.strategies,
        "marks": res.marks,
        "draws": res.draws,
        "PORTFOLIO_MC_DRAWDOWN": {"p50": round(res.mc_drawdown_p50, 5),
                                  "p95": round(res.mc_drawdown_p95, 5),
                                  "p99": round(res.mc_drawdown_p99, 5)},
        "PORTFOLIO_MC_RUIN": round(res.mc_ruin_probability, 5),
        "TAIL_PORTFOLIO_ELOG": round(res.tail_portfolio_elog, 6),
        "median_portfolio_elog": round(res.median_portfolio_elog, 6),
        "CONCURRENT_MARGIN": ({"p95": round(res.concurrent_margin_p95, 5),
                               "max": round(res.concurrent_margin_max, 5)}
                              if res.concurrent_margin_p95 is not None
                              and res.concurrent_margin_max is not None else None),
        "concurrent_margin_note": ("" if res.concurrent_margin_p95 is not None else
                                   "no per-period margin recorded on any path, so concurrent "
                                   "margin is UNMEASURED rather than zero -- and margin "
                                   "concurrency is the mechanism by which uncorrelated strategies "
                                   "die together"),
        "STRESS_COACTIVATION": None if coact is None else round(coact, 4),
        "stress_coactivation_note": cwhy,
        "DEPENDENCE_BLINDNESS": None if blind is None else round(blind, 4),
        "dependence_blindness_note": (
            "fewer than two strategies, so there is no dependence to be blind to"
            if blind is None else
            f"per-strategy independent shuffling reports a p95 drawdown {blind:.2f}x SMALLER than "
            "the synchronized truth on this book"
            if blind > 1.05 else
            f"per-strategy shuffling and synchronized resampling agree within {abs(blind - 1):.0%} "
            "-- this book really is close to independent, and the cheap method was not lying"),
        "why": res.why,
        "headline": (
            f"portfolio p95 drawdown {res.mc_drawdown_p95:.1%}, p99 {res.mc_drawdown_p99:.1%}, "
            f"P(ruin) {res.mc_ruin_probability:.1%} over {res.strategies} strategies"
            + (f"; per-strategy shuffling understates the p95 by {blind:.2f}x"
               if blind is not None and blind > 1.05 else "")),
        "note": ("Every draw resamples ONE block of time and applies it to EVERY strategy, so "
                 "cross-strategy correlation, common regime, tail dependence and margin "
                 "concurrency are never broken rather than modelled. Independently shuffling each "
                 "strategy manufactures diversification that does not exist, and "
                 "DEPENDENCE_BLINDNESS measures exactly how much of it this book was being sold."),
    }
