"""THE STRATEGY POOL — a bench of validated algos, and the arithmetic for who plays.

EXTRACTED FROM AN EXTERNAL PRACTITIONER CORPUS (Chart Fanatics / Naoufel, 2026-02-08) and kept
because two of its ideas survive contact with this desk's standards. The strategies in that
interview do not: one is the published Connors RSI(2) system, the other is a Thursday calendar
anomaly whose stated mechanism does not explain why Thursday. What survives is PROCESS.

**IDEA ONE: TIME IN MARKET IS A COST, AND THIS DESK WAS NOT CHARGING IT.**

    strategy A   +20%/yr, exposed 100% of the time
    strategy B   +20%/yr, exposed 10% of the time

Identical on every metric this desk currently computes. B is enormously better and for two
independent reasons. Its capital is uncommitted 90% of the time, so the SAME euro can fund other
strategies -- B's true contribution is 20% plus whatever the freed capital earns elsewhere. And it
is absent from the market during 90% of the windows in which a gap, a halt or a cascade could
happen, so its tail exposure is a tenth of A's for the same return.

`exposure_efficiency` makes that comparable. It is not a preference for trading less: a strategy
exposed 100% of the time earning 200% still wins. It is a refusal to treat two returns as equal
when one of them monopolises the capital that produced it.

**IDEA TWO: SIZE OFF THE RESHUFFLED DRAWDOWN, NOT THE BACKTEST DRAWDOWN.**

A backtest drawdown is ONE realisation of the trade sequence. Reshuffle the same trades and the
worst run of losses clusters differently; in the interview's own example a $13k backtest drawdown
became $34k at the 95th percentile -- 2.6x. Sizing off the smaller number is sizing off the luckiest
ordering the strategy happened to have, and it is the reason a system that "never drew down more
than 15%" takes 40% live.

`libs/discovery/monte_carlo_survival.py` already computes that distribution. What did not exist was
anything that USES it as the sizing input and as the retirement trigger, which is what this module
adds.

**THE RETIREMENT TRIGGER IS DERIVED, NOT PICKED.** The interview uses "1.5x the backtest drawdown,
then switch it off". That constant is exactly the kind of number this desk refuses: it fires early
on a strategy with a fat reshuffled tail and late on one with a tight one. Here the trigger IS the
reshuffled distribution -- a live drawdown past the 95th percentile of what the trade sequence can
produce is evidence the strategy has changed, and past the 99th it is nearly conclusive. Same idea,
no invented constant.

Ranks and reports. Promotes nothing, retires nothing, sizes nothing -- the allocator owns all three.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = [
    "MIN_LIVE_OBS_FOR_A_SWAP",
    "POOL_STATES",
    "PoolMember",
    "degradation_verdict",
    "exposure_efficiency",
    "sizing_drawdown",
    "summarise",
    "swap_candidates",
]

#: Where a validated strategy can sit. INCUBATING is the bench -- running on simulation money
#: against live data, accruing exactly the forward record that makes a later swap defensible.
POOL_STATES: tuple[str, ...] = ("LIVE", "REDUCED", "INCUBATING", "DORMANT", "RETIRED")

#: A swap on fewer live observations than this is a reaction to noise. The whole reason a bench
#: exists is to avoid swapping on a bad fortnight, so the floor has to bite on the LIVE side.
MIN_LIVE_OBS_FOR_A_SWAP: int = 30


@dataclass(frozen=True)
class PoolMember:
    """One validated strategy, live or on the bench, with the numbers a swap decision needs."""

    strategy_id: str
    state: str = "INCUBATING"
    #: Expected annual log return. 0 = UNMEASURED.
    annual_log_return: float = 0.0
    #: Fraction of the time the strategy holds a position. THE FIELD THIS DESK DID NOT HAVE.
    #: 0 = unmeasured, and efficiency is then UNMEASURED rather than infinite.
    market_exposure_fraction: float = 0.0
    #: Worst drawdown in the ORIGINAL backtest ordering. Reported, never used for sizing.
    backtest_max_drawdown: float = 0.0
    #: 95th and 99th percentile drawdown from reshuffling the trade sequence. THE SIZING INPUTS.
    mc_drawdown_p95: float = 0.0
    mc_drawdown_p99: float = 0.0
    #: Longest run of consecutive losses across the reshuffles. Pre-committing to survive this is
    #: what stops a correct strategy being switched off during the run it was always going to have.
    mc_max_consecutive_losses: int = 0
    #: Realised drawdown since going live, and how many live observations back it.
    live_drawdown: float = 0.0
    live_observations: int = 0
    #: Realised annual log return while live, for the incumbent-vs-bench comparison.
    live_annual_log_return: float = 0.0
    #: Mean absolute correlation to the rest of the LIVE roster. A bench member that duplicates a
    #: live one is not a replacement, it is the same bet with a new name.
    correlation_to_live: float = 0.0

    def __post_init__(self) -> None:
        if self.state not in POOL_STATES:
            raise ValueError(f"state must be one of {POOL_STATES}")

    @property
    def measured(self) -> bool:
        return self.annual_log_return != 0.0 and self.market_exposure_fraction > 0


def exposure_efficiency(m: PoolMember) -> tuple[float | None, str]:
    """Log return per unit of time spent holding risk. None when exposure is unmeasured.

    NOT a preference for trading less. A strategy exposed 100% of the time earning 200% beats one
    exposed 10% earning 20%, and this ranks it that way. What it refuses is treating two identical
    returns as equal when one of them monopolises the capital that produced it and sits in the
    market through ten times as many windows in which something can go wrong.
    """
    if m.market_exposure_fraction <= 0:
        return None, (
            f"{m.strategy_id}: market exposure UNMEASURED, so its return cannot be compared "
            "against one that holds risk for a tenth of the time. Two strategies at +20% are not "
            "the same strategy if one of them is flat 90% of the year")
    e = m.market_exposure_fraction
    eff = m.annual_log_return / e
    return eff, (
        f"{m.strategy_id}: {m.annual_log_return:+.1%} log return at {e:.0%} time-in-market "
        f"=> {eff:+.1%} per unit of exposure. The other {1 - e:.0%} of the time that capital is "
        "free to fund something else, and the strategy is absent from every window in which a gap "
        "or a cascade could reach it")


def sizing_drawdown(m: PoolMember) -> tuple[float | None, str]:
    """The drawdown a position should be sized against. The RESHUFFLED tail, never the backtest.

    A backtest drawdown is one realisation of a trade ordering. The same trades in a different
    sequence cluster their losses differently, and the difference is routinely 2-3x. Sizing off the
    backtest number is sizing off the luckiest ordering the strategy happened to have.
    """
    if m.mc_drawdown_p95 <= 0:
        return None, (
            f"{m.strategy_id}: no reshuffled drawdown distribution, so the only number available "
            f"is the backtest {m.backtest_max_drawdown:.0%} -- ONE ordering of the trades, and "
            "systematically the optimistic one. UNMEASURED: run "
            "libs/discovery/monte_carlo_survival.py before sizing this")
    ratio = (m.mc_drawdown_p95 / m.backtest_max_drawdown
             if m.backtest_max_drawdown > 0 else float("inf"))
    return m.mc_drawdown_p95, (
        f"{m.strategy_id}: size against {m.mc_drawdown_p95:.0%} (95th percentile of reshuffled "
        f"orderings), not {m.backtest_max_drawdown:.0%} (the observed sequence)"
        + (f" -- a factor of {ratio:.1f}" if math.isfinite(ratio) else "")
        + ". The backtest ordering is one draw and it is the one that happened to be survivable")


def degradation_verdict(m: PoolMember) -> tuple[str, str]:
    """(HEALTHY | WITHIN_EXPECTATION | DEGRADED | BROKEN | UNMEASURED, why).

    THE TRIGGER IS THE DISTRIBUTION, NOT A CONSTANT. "Switch it off past 1.5x the backtest
    drawdown" fires early on a strategy with a fat reshuffled tail and late on one with a tight
    tail, because the multiplier knows nothing about the shape. A live drawdown past the 95th
    percentile of what this trade sequence can produce is evidence something changed; past the 99th
    it is close to conclusive. Same instinct, no invented number.
    """
    if m.mc_drawdown_p95 <= 0:
        return "UNMEASURED", (
            f"{m.strategy_id}: no reshuffled distribution, so a live drawdown of "
            f"{m.live_drawdown:.0%} cannot be judged. Without it, every retirement decision is a "
            "reaction to a number with no reference point")
    if m.live_observations < MIN_LIVE_OBS_FOR_A_SWAP:
        return "WITHIN_EXPECTATION", (
            f"{m.strategy_id}: {m.live_observations} live observation(s) against a floor of "
            f"{MIN_LIVE_OBS_FOR_A_SWAP}. Too early to call anything -- and the reshuffles say this "
            f"strategy can lose {m.mc_max_consecutive_losses} in a row, which is exactly the run "
            "that gets a correct strategy switched off")
    if m.live_drawdown >= (m.mc_drawdown_p99 or m.mc_drawdown_p95 * 1.3):
        return "BROKEN", (
            f"{m.strategy_id}: live drawdown {m.live_drawdown:.0%} is past the 99th percentile of "
            f"its own reshuffled orderings ({m.mc_drawdown_p99:.0%}). Either the mechanism stopped "
            "working or the backtest was wrong; both are reasons to stop, and neither is bad luck")
    if m.live_drawdown >= m.mc_drawdown_p95:
        return "DEGRADED", (
            f"{m.strategy_id}: live drawdown {m.live_drawdown:.0%} exceeds the 95th percentile of "
            f"reshuffled orderings ({m.mc_drawdown_p95:.0%}). Not conclusive -- one strategy in "
            "twenty should reach here honestly -- but it is where the bench earns its keep")
    return "HEALTHY", (
        f"{m.strategy_id}: live drawdown {m.live_drawdown:.0%} inside the reshuffled 95th "
        f"percentile {m.mc_drawdown_p95:.0%} over {m.live_observations} observations")


def swap_candidates(pool: list[PoolMember]) -> list[dict[str, object]]:
    """Bench members that would improve the roster, paired with the incumbent they would replace.

    TWO GUARDS, AND BOTH MATTER. A bench member must beat the incumbent on exposure efficiency --
    otherwise the swap buys a return at a higher capital cost -- and it must not simply duplicate
    something already live, because replacing a correlated strategy with its twin changes the name
    on the position and nothing else.
    """
    live = [m for m in pool if m.state in ("LIVE", "REDUCED")]
    bench = [m for m in pool if m.state == "INCUBATING"]
    out: list[dict[str, object]] = []
    for inc in live:
        verdict, why = degradation_verdict(inc)
        if verdict not in ("DEGRADED", "BROKEN"):
            continue
        inc_eff, _ = exposure_efficiency(inc)
        best, best_eff = None, inc_eff
        for b in bench:
            eff, _ = exposure_efficiency(b)
            if eff is None or b.correlation_to_live >= 0.7:
                continue
            if best_eff is None or eff > best_eff:
                best, best_eff = b, eff
        out.append({
            "incumbent": inc.strategy_id, "verdict": verdict, "why": why,
            "incumbent_exposure_efficiency": None if inc_eff is None else round(inc_eff, 4),
            "replacement": None if best is None else best.strategy_id,
            "replacement_exposure_efficiency": None if best_eff is None else round(best_eff, 4),
            "replacement_correlation_to_live": None if best is None else best.correlation_to_live,
            "action": ("SWAP" if best is not None else
                       "RETIRE_WITHOUT_REPLACEMENT" if verdict == "BROKEN" else "REDUCE"),
            "note": ("" if best is not None else
                     "no bench member both beats it on exposure efficiency and is uncorrelated "
                     "with the live roster -- replacing a strategy with its twin changes the name "
                     "on the position and nothing else"),
        })
    return out


def summarise(pool: list[PoolMember]) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not pool:
        return {"members": 0, "headline": (
            "no strategy pool -- there is no bench, so a degrading live strategy can only be "
            "switched OFF rather than replaced, and the capital it was using goes idle")}
    rows = []
    for m in pool:
        eff, ewhy = exposure_efficiency(m)
        size_dd, swhy = sizing_drawdown(m)
        verdict, vwhy = degradation_verdict(m)
        rows.append({
            "strategy_id": m.strategy_id, "state": m.state,
            "exposure_efficiency": None if eff is None else round(eff, 4),
            "exposure_note": ewhy,
            "sizing_drawdown": None if size_dd is None else round(size_dd, 4),
            "sizing_note": swhy,
            "health": verdict, "health_why": vwhy,
        })
    rows.sort(key=lambda r: -(float(str(r["exposure_efficiency"]))
                              if r["exposure_efficiency"] is not None else -1e18))
    swaps = swap_candidates(pool)
    bench = sum(1 for m in pool if m.state == "INCUBATING")
    live = sum(1 for m in pool if m.state in ("LIVE", "REDUCED"))
    unsized = [r["strategy_id"] for r in rows if r["sizing_drawdown"] is None]
    return {
        "members": len(pool), "live": live, "incubating": bench,
        "rows": rows, "swap_candidates": swaps,
        "sized_on_backtest_only": unsized,
        "headline": (
            f"{live} live, {bench} on the bench; {len(swaps)} swap decision(s) pending"
            + (f". {len(unsized)} strategy(ies) have NO reshuffled drawdown and can only be sized "
               f"off a single trade ordering: {unsized[:3]}" if unsized else "")),
        "note": ("Exposure efficiency is return per unit of TIME IN MARKET, not a preference for "
                 "trading less -- 200% at full exposure still beats 20% at a tenth. Sizing and "
                 "retirement both key off the RESHUFFLED drawdown distribution rather than the "
                 "backtest ordering or any fixed multiple of it: a multiplier fires early on a "
                 "fat tail and late on a tight one because it knows nothing about the shape."),
    }
