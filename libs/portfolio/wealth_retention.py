"""ANTI-ROUND-TRIP — the difference between generating returns and keeping them.

THE FAILURE MODE THIS EXISTS TO DEFEAT, stated plainly because every other module on this desk is
built to find edge and none of them is built to notice that the edge was given back::

    RETURN GENERATION  !=  WEALTH COMPOUNDING

A path that goes 1x -> 30x -> 1x has a magnificent maximum, an impressive arithmetic mean, a
publishable win rate, and a realised log-growth of ZERO. Every metric this desk keeps except the
last one calls that a success. The public record of the operator this spec benchmarks against is
exactly this shape -- large accounts built and returned to zero, more than once -- and it is not
a discipline failure that a better trader avoids. It is the arithmetic of the geometric mean
applied to an exposure policy that never asked how much of the ACCUMULATED stack was at risk.

**NO ARBITRARY PROFIT-LOCK RULE LIVES HERE, AND THE ABSENCE IS DELIBERATE.** "After +100%, halve
the risk" is a number somebody picked; it fires on a path that is still compounding and stays
silent on one that is not. What this module computes instead is whether the MARGINAL unit of risky
capital still raises forward E[log W] once the uncertainty in the edge and the option value of
retained capital are priced. When it does, aggression is correct and this module says so. When it
does not, cash wins the allocator on its own merits rather than by a rule.

THE ASYMMETRY THAT DRIVES EVERYTHING HERE. A 50% loss needs a 100% gain to undo; an 80% loss needs
400%. Recovery cost is convex in drawdown while the gain that produced the drawdown was linear, so
the same edge does not buy back what it lost. That is why `maximum_giveback` and
`round_trip_ratio` are first-class numbers and `peak_return` is not reported at all.

WHAT THIS DOES NOT DO. It does not size, it does not trade, and it cannot veto. It publishes
metrics and a marginal-exposure verdict for the allocator to read. A module that both measured
wealth-at-risk and enforced a cap would be the arbitrary rule wearing a measurement's clothes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MIN_PATH_FOR_A_VERDICT",
    "NavPath",
    "RiskyProposal",
    "drawdown_series",
    "gain_retention_ratio",
    "kelly_fraction",
    "marginal_verdict",
    "maximum_giveback",
    "realized_log_growth",
    "reserve_option_value",
    "round_trip_ratio",
    "summarise",
    "wealth_at_risk",
]

#: Below this many NAV marks, every retention number is a description of a path, not an estimate
#: of a process. Reported as UNMEASURED rather than as a small-sample figure -- the small-sample
#: worship this spec forbids is exactly what a 9-point "gain retention ratio" would be.
MIN_PATH_FOR_A_VERDICT: int = 30


@dataclass(frozen=True)
class NavPath:
    """The realised wealth path, net of everything, with external flows separated out.

    **DEPOSITS AND WITHDRAWALS ARE NOT RETURNS** and conflating them is the single easiest way to
    manufacture a good-looking equity curve. `flows[i]` is the external capital added (positive) or
    removed (negative) immediately BEFORE `nav[i]` is observed, so growth is measured on the
    capital that was actually working.
    """

    nav: tuple[float, ...]
    flows: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.flows and len(self.flows) != len(self.nav):
            raise ValueError("flows must align 1:1 with nav marks")

    @property
    def measured(self) -> bool:
        return len(self.nav) >= MIN_PATH_FOR_A_VERDICT and all(v > 0 for v in self.nav)

    @property
    def flow_adjusted_returns(self) -> tuple[float, ...]:
        """Per-period simple returns with external flows removed.

        r_t = nav_t / (nav_{t-1} + flow_t) - 1. A deposit therefore contributes zero return on the
        step that receives it, which is the only treatment under which a funded account and a
        compounding account can be compared at all.
        """
        n = len(self.nav)
        if n < 2:
            return ()
        flows = self.flows or (0.0,) * n
        out = []
        for i in range(1, n):
            base = self.nav[i - 1] + flows[i]
            out.append(self.nav[i] / base - 1.0 if base > 0 else 0.0)
        return tuple(out)


@dataclass(frozen=True)
class RiskyProposal:
    """One candidate marginal allocation, with its uncertainty carried rather than dropped.

    `edge_sigma` is the thing that makes this different from a Kelly calculator. A point estimate
    of edge sized full-Kelly is the classic route from a 30x to a zero: the estimate is wrong by
    more than the sizing assumed, and the geometric penalty for overbetting is unbounded while the
    penalty for underbetting is bounded by the forgone growth.
    """

    name: str
    #: Expected per-period log-return contribution per unit of capital allocated. Net of costs.
    edge: float
    #: Posterior standard deviation of that edge estimate. 0 = UNMEASURED, never "certain".
    edge_sigma: float
    #: Per-period return variance of the strategy itself.
    variance: float
    #: Worst plausible single-period loss as a fraction of capital allocated (tail scenario).
    tail_loss: float = 0.0
    #: Effective independent observations behind `edge`. Feeds the shrinkage.
    effective_n: float = 0.0

    @property
    def measured(self) -> bool:
        return self.variance > 0 and self.edge_sigma > 0 and self.effective_n > 0


def drawdown_series(nav: tuple[float, ...]) -> tuple[float, ...]:
    """Fractional drawdown from the running high-water mark at each mark."""
    out: list[float] = []
    peak = float("-inf")
    for v in nav:
        peak = max(peak, v)
        out.append(0.0 if peak <= 0 else (peak - v) / peak)
    return tuple(out)


def realized_log_growth(path: NavPath) -> float | None:
    """Total realised log growth of working capital, flows removed. THE OBJECTIVE, not a proxy.

    None when the path is too short to mean anything. Zero is a legitimate answer and is exactly
    what a full round trip produces -- which is the point of reporting this instead of peak NAV.
    """
    if len(path.nav) < 2:
        return None
    total = 0.0
    for r in path.flow_adjusted_returns:
        if r <= -1.0:
            return float("-inf")   # ruin is not a small number, it is an absorbing state
        total += math.log1p(r)
    return total


def maximum_giveback(nav: tuple[float, ...]) -> float | None:
    """Largest peak-to-trough fraction ever surrendered. None when the path never rose.

    Deliberately NOT "current drawdown": the question this answers is how much of an accumulated
    stack this process has historically been willing to hand back, which is a property of the
    policy rather than of today.
    """
    if len(nav) < 2:
        return None
    dd = drawdown_series(nav)
    return max(dd) if dd else None


def gain_retention_ratio(path: NavPath) -> float | None:
    """Fraction of the best gain ever reached that is still owned. 1.0 = nothing given back.

    Measured against the flow-adjusted peak so a withdrawal is not scored as a giveback and a
    deposit does not manufacture a new high-water mark.
    """
    nav = path.nav
    if len(nav) < 2 or nav[0] <= 0:
        return None
    flows = path.flows or (0.0,) * len(nav)
    # Working-capital index: what one unit at t0 would be worth, flows removed.
    idx = [1.0]
    for r in path.flow_adjusted_returns:
        idx.append(idx[-1] * (1.0 + r))
    peak_gain = max(idx) - 1.0
    final_gain = idx[-1] - 1.0
    del flows
    if peak_gain <= 0:
        return None            # never gained: retention of a gain that never existed is undefined
    return final_gain / peak_gain


def round_trip_ratio(path: NavPath) -> float | None:
    """How far back toward the STARTING stack the process has travelled from its peak.

    0.0 = still at the high-water mark. 1.0 = a completed round trip, the whole gain returned.
    Above 1.0 = the process is now below where it started, having first been well above it.

    This is the number the benchmarked operator's public record maximises, and it is the number
    a Sharpe ratio, a win rate and an arithmetic CAGR all decline to report.
    """
    nav = path.nav
    if len(nav) < 2:
        return None
    idx = [1.0]
    for r in path.flow_adjusted_returns:
        idx.append(idx[-1] * (1.0 + r))
    peak = max(idx)
    if peak <= 1.0:
        return None            # never above the start: there is no round trip to measure
    return (peak - idx[-1]) / (peak - 1.0)


def wealth_at_risk(nav_now: float, risky_fraction: float, tail_loss: float) -> float:
    """Absolute accumulated wealth exposed to the modelled tail. The §4 headline number.

    Reported in currency rather than as a percentage on purpose: "18% at risk" reads the same at
    every wealth level, and the whole anti-round-trip argument is that it should not.
    """
    return max(0.0, nav_now) * max(0.0, risky_fraction) * max(0.0, min(1.0, tail_loss))


def kelly_fraction(p: RiskyProposal) -> float | None:
    """UNCERTAINTY-SHRUNK growth-optimal fraction. None when the inputs are unmeasured.

    f* = edge / variance is the textbook answer and it is the one that produces round trips,
    because it treats a noisy edge estimate as a known constant. The estimate carries `edge_sigma`,
    so the shrinkage below is not conservatism -- it is the same formula applied to the posterior
    rather than to the point estimate::

        f = max(0, edge - k*sigma) / (variance + sigma^2)

    The `k*sigma` haircut prices estimation error in the numerator; the `sigma^2` in the
    denominator prices it as additional variance. Both are needed: an edge known to +/-100% of its
    own size is not the same bet as one known to +/-5%, and only the second term notices.

    Never returns above 1.0. Levering a single estimate past full capital is how the asymmetry in
    the module docstring gets paid.
    """
    if not p.measured:
        return None
    shrunk = p.edge - p.edge_sigma
    if shrunk <= 0:
        return 0.0
    f = shrunk / (p.variance + p.edge_sigma ** 2)
    return float(max(0.0, min(1.0, f)))


def reserve_option_value(*, opportunity_arrival_rate: float, expected_dislocation_edge: float,
                         horizon_periods: float) -> float:
    """Per-unit value of holding capital back, in expected log terms. §5.

    Cash is not idle capital earning zero -- it is a call on every dislocation that has not
    happened yet, and this desk's own drawdown/rebound book is the thing that would exercise it.
    Pricing it at zero is what forces full investment and guarantees there is nothing left to
    deploy on the day the opportunity set is best.

    Deliberately crude and deliberately conservative: expected number of dislocations over the
    horizon, times the edge each is expected to carry, log-transformed. Refined estimates belong to
    the drawdown book once it has measured a rebound distribution; a zero here would be a much
    larger error than a rough positive number.
    """
    if opportunity_arrival_rate <= 0 or expected_dislocation_edge <= 0 or horizon_periods <= 0:
        return 0.0
    expected_events = opportunity_arrival_rate * horizon_periods
    return float(expected_events * math.log1p(expected_dislocation_edge))


def marginal_verdict(p: RiskyProposal, *, current_risky_fraction: float,
                     reserve_value: float = 0.0) -> tuple[str, str]:
    """(verdict, why) for the NEXT unit of capital. DEPLOY | HOLD | REDUCE | UNMEASURED.

    THE QUESTION IS ALWAYS MARGINAL, never "is this strategy good". A strategy can be genuinely
    profitable and still be the wrong home for the next euro, because the allocator's alternative
    is not zero -- it is retained capital with the option value above, and every other engine
    competing at the same time.
    """
    if not p.measured:
        return "UNMEASURED", (
            f"{p.name} carries no posterior width or no variance, so the marginal unit cannot be "
            "priced. An unmeasured edge sized as if measured is the exact mechanism that turns a "
            "large account into its starting balance -- absence is not a green light")
    f = kelly_fraction(p)
    assert f is not None
    if f <= 0.0:
        return "REDUCE", (
            f"{p.name}: edge {p.edge:.4f} does not survive its own posterior width "
            f"{p.edge_sigma:.4f}, so the growth-optimal fraction is zero. Capital here is being "
            "sized against estimation noise")
    headroom = f - max(0.0, current_risky_fraction)
    marginal_log = p.edge - 0.5 * p.variance * max(0.0, current_risky_fraction)
    if marginal_log <= reserve_value:
        return "HOLD", (
            f"{p.name}: marginal log contribution {marginal_log:.5f} does not beat the option "
            f"value of retained capital {reserve_value:.5f}. Cash wins this comparison on its own "
            "merits, not by a profit-locking rule")
    if headroom <= 0:
        return "REDUCE", (
            f"{p.name}: already at {current_risky_fraction:.1%} against a shrunk growth-optimal "
            f"{f:.1%}. Past this point additional exposure LOWERS expected log wealth -- the "
            "overbetting penalty is unbounded while the underbetting cost is not")
    return "DEPLOY", (
        f"{p.name}: shrunk growth-optimal {f:.1%} against current {current_risky_fraction:.1%}, "
        f"marginal log contribution {marginal_log:.5f} > reserve option value {reserve_value:.5f}. "
        "Aggression is correct here and the arithmetic says so")


def summarise(path: NavPath, *, proposals: tuple[RiskyProposal, ...] = (),
              current_risky_fraction: float = 0.0,
              reserve_value: float = 0.0) -> dict[str, object]:
    """Report shape for `data/wealth_retention.json`. Measures; decides nothing."""
    if not path.measured:
        return {
            "measured": False,
            "nav_marks": len(path.nav),
            "headline": (
                f"UNMEASURED -- {len(path.nav)} NAV mark(s) against a floor of "
                f"{MIN_PATH_FOR_A_VERDICT}. Retention is a property of a PATH, and a handful of "
                "marks describes an episode. This is not 'no round-trip risk detected'; it is "
                "the desk having no idea, which is the state that precedes every round trip"),
        }
    nav = path.nav
    g = realized_log_growth(path)
    dd = drawdown_series(nav)
    verdicts = [(p.name, *marginal_verdict(p, current_risky_fraction=current_risky_fraction,
                                           reserve_value=reserve_value)) for p in proposals]
    war = sum(wealth_at_risk(nav[-1], current_risky_fraction, p.tail_loss) for p in proposals)
    rt = round_trip_ratio(path)
    grr = gain_retention_ratio(path)
    return {
        "measured": True,
        "nav_marks": len(nav),
        "REALIZED_LOG_GROWTH": None if g is None else round(g, 6),
        "GAIN_RETENTION_RATIO": None if grr is None else round(grr, 4),
        "ROUND_TRIP_RATIO": None if rt is None else round(rt, 4),
        "MAXIMUM_GIVEBACK": round(max(dd), 4) if dd else None,
        "current_drawdown": round(dd[-1], 4) if dd else None,
        "PEAK_WEALTH_AT_RISK": round(war, 2),
        "high_water_mark": round(max(nav), 2),
        "nav_now": round(nav[-1], 2),
        "reserve_option_value": round(reserve_value, 6),
        "marginal_verdicts": [{"name": n, "verdict": v, "why": w} for n, v, w in verdicts],
        "headline": _headline(g, rt, grr, dd, verdicts),
        "note": ("No profit-locking rule is applied and none exists in this module. Exposure is "
                 "judged by whether the MARGINAL unit still raises forward E[log W] once posterior "
                 "width and the option value of retained capital are priced. Large past gains "
                 "grant no risk privilege and impose no risk penalty -- they are simply not an "
                 "input to a forward marginal decision."),
    }


def _headline(g: float | None, rt: float | None, grr: float | None,
              dd: tuple[float, ...], verdicts: list[tuple[str, str, str]]) -> str:
    if g == float("-inf"):
        return ("RUIN on the realised path: a period return of -100% is an absorbing state, and "
                "no subsequent edge recovers from it. Every other number here is decoration")
    reduce_n = sum(1 for _, v, _ in verdicts if v == "REDUCE")
    parts = []
    if g is not None:
        parts.append(f"realised log growth {g:+.4f}")
    if rt is not None and rt >= 0.5:
        parts.append(f"ROUND-TRIP {rt:.0%} of the peak gain surrendered")
    elif grr is not None:
        parts.append(f"gain retention {grr:.0%}")
    if dd:
        parts.append(f"worst giveback {max(dd):.0%}")
    if reduce_n:
        parts.append(f"{reduce_n} proposal(s) sized past their shrunk growth-optimal fraction")
    return "; ".join(parts) if parts else "path measured, no retention signal"
