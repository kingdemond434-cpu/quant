"""THE DRAWDOWN / REBOUND BOOK — a 15% fall is not one event, and treating it as one loses money.

TWO DECLINES OF IDENTICAL DEPTH CAN HAVE OPPOSITE FORWARD DISTRIBUTIONS::

    forced deleveraging   leveraged longs liquidated into a thin book. The selling is MECHANICAL,
                          it exhausts when the positions are gone, and the price overshoots what
                          any informed seller would have accepted. Frequently a rebound.

    news shock            genuinely new information about value. The selling is INFORMED, there is
                          no reason for it to exhaust at a particular price, and the "discount" is
                          the market's new estimate. Frequently not a rebound.

A rule that buys the dip cannot tell these apart, and it will be right often enough to keep
running and wrong exactly when the losses are large. So this book classifies the MECHANISM first
and estimates the rebound distribution conditional on it -- there is no universal buy-the-crash
rule here and none can be added, because `rebound_estimate` refuses to return one for an
unclassified event.

**WHY THE PRICE OPPORTUNITY AND THE EXECUTION OPPORTUNITY ARE SEPARATED.** Immediately after a
cascade the directional expectancy can be positive while the book is still a wreck: the spread is
wide, depth has not returned, and cross-venue prices disagree. Buying into that pays the rebound
away in slippage. `liquidity_recovery` prices the wait, so the decision is not merely WHETHER but
WHEN, and a few minutes of patience is a legitimate answer.

**THIS EXTENDS `libs/research/liquidation_mechanism.py` RATHER THAN REPLACING IT.** That module
answers one binary question -- is the reversion forced flow or supply -- with measured OI collapse,
funding extremity and liquidation burst. It is the strongest single input here and is consumed
directly. What it does not do is separate the six ways a decline can happen or estimate what comes
next, which is what a BOOK needs.

Classifies and estimates. Sizes nothing, buys nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "MECHANISMS",
    "MIN_EVENTS_FOR_A_DISTRIBUTION",
    "DeclineEvent",
    "ReboundEstimate",
    "classify",
    "liquidity_recovery",
    "rebound_estimate",
    "summarise",
]

#: The ways a decline can happen. MIXED_UNKNOWN is a real answer and the commonest honest one --
#: it is what an event looks like before the evidence separates it, and it earns no rebound
#: estimate at all.
MECHANISMS: tuple[str, ...] = (
    "ENDOGENOUS_LEVERAGE_BUILDUP",   # the market ate its own longs
    "EXOGENOUS_NEWS_SHOCK",          # new information about value
    "LIQUIDITY_WITHDRAWAL",          # makers left; price moved on little volume
    "CROSS_VENUE_DISLOCATION",       # one venue broke, not the asset
    "IDIOSYNCRATIC_ASSET_FAILURE",   # this token specifically
    "SYSTEMIC_RISK_OFF",             # everything down together
    "MIXED_UNKNOWN",
)

#: Below this many historical events OF THE SAME MECHANISM, a rebound distribution is a story
#: about a handful of crashes. Reported as UNMEASURED rather than as a thin estimate.
MIN_EVENTS_FOR_A_DISTRIBUTION: int = 20


@dataclass(frozen=True)
class DeclineEvent:
    """One decline, with the state that separates a cascade from a repricing.

    Every field defaults to the UNMEASURED value. The classifier requires positive evidence for
    every mechanism it names and falls to MIXED_UNKNOWN otherwise -- absence must never resolve to
    the tradeable answer, which here is the one that spends money.
    """

    event_id: str
    symbol: str = ""
    #: Depth of the fall, positive fraction (0.15 = -15%).
    depth: float = 0.0
    #: Minutes from the start of the decline to the low. Velocity separates a flush from a bleed.
    duration_minutes: float = 0.0
    #: Fraction of open interest cleared during the decline. THE SINGLE BEST CASCADE SIGNATURE:
    #: forced selling destroys OI, informed selling does not have to.
    oi_cleared_fraction: float = 0.0
    #: Liquidation notional over the window, and how concentrated it was in time.
    liquidation_notional: float = 0.0
    liquidation_velocity: float = 0.0
    #: Funding immediately before, annualised. Extreme positive funding means the longs were
    #: paying to be there, which is what a crowded leveraged position looks like from outside.
    funding_before: float = 0.0
    #: Spread and depth as a multiple of their normal level during the decline.
    spread_multiple: float = 1.0
    depth_multiple: float = 1.0
    #: The instrument's NORMAL spread in bps. Required to turn a spread MULTIPLE into a cost:
    #: 4x on a 2bp book and 4x on a 40bp book are the same multiple and twenty times the money.
    #: 0 = unmeasured, and the recovery cost is then reported as unpriceable rather than guessed.
    normal_spread_bps: float = 0.0
    #: Volume as a multiple of normal. A large fall on LOW volume is a liquidity event, not a
    #: repricing -- nobody transacted at the new level.
    volume_multiple: float = 1.0
    #: Largest cross-venue price divergence during the window, as a fraction.
    cross_venue_divergence: float = 0.0
    #: Fraction of the universe that fell together. 1.0 = everything.
    breadth_down: float = 0.0
    #: Was there a dated, timestamped news or protocol event inside the window?
    news_event: bool = False
    #: Stablecoin supply change over the window; a proxy for money leaving the system.
    stablecoin_flow: float = 0.0
    #: Verdict from libs/research/liquidation_mechanism.py when it has been run: FORCED | SUPPLY |
    #: empty for unrun. The strongest single input and deliberately not recomputed here.
    forced_flow_verdict: str = ""


@dataclass(frozen=True)
class ReboundEstimate:
    """What is expected AFTER, conditional on the mechanism. None everywhere = UNMEASURED."""

    mechanism: str
    p_rebound: float | None
    expected_bounce: float | None
    expected_max_adverse: float | None
    median_recovery_hours: float | None
    n_events: int
    why: str


def classify(e: DeclineEvent) -> tuple[str, str]:
    """(mechanism, why). MIXED_UNKNOWN when the evidence does not separate them.

    ORDER IS LOAD-BEARING. Cross-venue dislocation is tested first because it can masquerade as
    every other mechanism on the venue that broke, and systemic risk-off is tested before the
    idiosyncratic and endogenous cases because a market-wide fall makes every single-asset
    explanation look locally true.
    """
    if e.depth <= 0:
        return "MIXED_UNKNOWN", (f"{e.event_id}: no measured depth -- there is no "
                                 "decline to classify")

    if e.cross_venue_divergence >= 0.02 and e.breadth_down < 0.5:
        return "CROSS_VENUE_DISLOCATION", (
            f"{e.event_id}: {e.cross_venue_divergence:.1%} cross-venue divergence with only "
            f"{e.breadth_down:.0%} of the universe down. One venue moved, not the asset -- the "
            "opportunity here is the convergence, and it is an execution problem before it is a "
            "directional one")

    if e.breadth_down >= 0.8 and not e.news_event:
        return "SYSTEMIC_RISK_OFF", (
            f"{e.event_id}: {e.breadth_down:.0%} of the universe fell together with no dated "
            "event. A single-asset explanation would be locally true and globally wrong; whatever "
            "is happening is not about this symbol")

    if e.news_event and e.breadth_down < 0.5:
        return "EXOGENOUS_NEWS_SHOCK", (
            f"{e.event_id}: a dated event inside the window and only {e.breadth_down:.0%} breadth. "
            "The selling is INFORMED, so it has no reason to exhaust at a particular price and the "
            "discount may simply be the new estimate of value")

    forced = (e.oi_cleared_fraction >= 0.10 or e.forced_flow_verdict == "FORCED"
              or (e.liquidation_velocity > 0 and e.funding_before >= 0.20))
    if forced and e.volume_multiple >= 1.5:
        return "ENDOGENOUS_LEVERAGE_BUILDUP", (
            f"{e.event_id}: {e.oi_cleared_fraction:.0%} of open interest cleared on "
            f"{e.volume_multiple:.1f}x volume with funding {e.funding_before:+.0%} before"
            + (f", and liquidation_mechanism says {e.forced_flow_verdict}"
               if e.forced_flow_verdict else "")
            + ". The market ate its own longs: the selling is MECHANICAL and exhausts when the "
              "positions are gone")

    if e.volume_multiple <= 0.8 and (e.depth_multiple <= 0.5 or e.spread_multiple >= 2.0):
        return "LIQUIDITY_WITHDRAWAL", (
            f"{e.event_id}: {e.depth:.0%} fall on {e.volume_multiple:.1f}x volume with depth at "
            f"{e.depth_multiple:.1f}x and spread at {e.spread_multiple:.1f}x. Almost nobody "
            "transacted at the new level -- the makers left, and the price is where it is because "
            "there was nothing under it")

    if e.breadth_down <= 0.2 and e.depth >= 0.15:
        return "IDIOSYNCRATIC_ASSET_FAILURE", (
            f"{e.event_id}: {e.depth:.0%} fall while {1 - e.breadth_down:.0%} of the universe did "
            "not follow. Something is wrong with this asset specifically, and 'it is cheap now' "
            "assumes the thing that is wrong is temporary")

    return "MIXED_UNKNOWN", (
        f"{e.event_id}: the evidence does not separate the mechanisms "
        f"(depth {e.depth:.0%}, breadth {e.breadth_down:.0%}, OI cleared "
        f"{e.oi_cleared_fraction:.0%}, volume {e.volume_multiple:.1f}x). UNCLASSIFIED, and an "
        "unclassified decline earns no rebound estimate -- absence must not resolve to the answer "
        "that spends money")


def rebound_estimate(e: DeclineEvent,
                     history: dict[str, list[tuple[float, float, float]]]) -> ReboundEstimate:
    """Forward distribution conditional on the classified mechanism.

    `history` maps mechanism -> [(bounce_fraction, max_adverse_fraction, recovery_hours), ...]
    from PAST events of that mechanism. Nothing is assumed: an unclassified event and a mechanism
    with a thin history both return None everywhere, and the reason says which.

    THERE IS NO UNIVERSAL RULE HERE AND NONE CAN BE ADDED. The estimate is a lookup on measured
    history, so a mechanism this desk has never seen produces no number rather than an average of
    the ones it has.
    """
    mech, why = classify(e)
    if mech == "MIXED_UNKNOWN":
        return ReboundEstimate(mech, None, None, None, None, 0,
                               f"UNCLASSIFIED so no forward distribution applies. {why}")
    rows = history.get(mech) or []
    if len(rows) < MIN_EVENTS_FOR_A_DISTRIBUTION:
        return ReboundEstimate(
            mech, None, None, None, None, len(rows),
            f"{mech}: {len(rows)} historical event(s) against a floor of "
            f"{MIN_EVENTS_FOR_A_DISTRIBUTION}. UNMEASURED -- a rebound distribution over a handful "
            f"of crashes is a story about those crashes. {why}")
    bounces = sorted(r[0] for r in rows)
    adverse = sorted(r[1] for r in rows)
    hours = sorted(r[2] for r in rows)
    n = len(rows)
    p_up = sum(1 for b in bounces if b > 0) / n
    return ReboundEstimate(
        mechanism=mech,
        p_rebound=round(p_up, 4),
        expected_bounce=round(sum(bounces) / n, 5),
        # THE ADVERSE EXCURSION IS TAKEN AT THE 90TH PERCENTILE, NOT THE MEAN. The mean is what
        # happens; the tail is what ends the position before the rebound arrives, and a book sized
        # on the mean is stopped out of the trade it was right about.
        expected_max_adverse=round(adverse[min(n - 1, int(0.9 * n))], 5),
        median_recovery_hours=round(hours[n // 2], 2),
        n_events=n,
        why=(f"{mech}: over {n} past event(s), {p_up:.0%} rebounded, mean bounce "
             f"{sum(bounces) / n:+.1%}, 90th-percentile adverse excursion "
             f"{adverse[min(n - 1, int(0.9 * n))]:.1%}, median recovery "
             f"{hours[n // 2]:.1f}h. {why}"))


def liquidity_recovery(e: DeclineEvent, *, minutes_elapsed: float,
                       half_life_minutes: float = 20.0) -> tuple[float, str]:
    """Fraction of normal book quality restored, and whether waiting is worth it.

    SEPARATES THE PRICE OPPORTUNITY FROM THE EXECUTION OPPORTUNITY. Directional expectancy can be
    positive while the book is still a wreck, and buying into that pays the rebound away in
    slippage. The cost of impatience is estimated from the spread multiple, which is the part of
    the damage a taker actually pays.
    """
    if minutes_elapsed < 0 or half_life_minutes <= 0:
        return 0.0, "UNMEASURED -- needs elapsed minutes and a recovery half-life"
    damage = max(0.0, e.spread_multiple - 1.0)
    remaining = damage * 0.5 ** (minutes_elapsed / half_life_minutes)
    recovered = 1.0 - (remaining / damage if damage > 0 else 0.0)
    if e.normal_spread_bps <= 0:
        return recovered, (
            f"{recovered:.0%} of book quality restored {minutes_elapsed:g}min in, but the "
            "instrument's NORMAL spread is unmeasured so the cost of crossing now cannot be "
            "priced. A spread MULTIPLE is not a cost: 4x on a 2bp book and 4x on a 40bp book are "
            "the same multiple and twenty times the money")
    # Excess half-spread a taker pays right now, in bps. `remaining` is a multiple of the normal
    # spread, so it must be scaled by that spread before it means anything in money.
    cost_now_bps = remaining * e.normal_spread_bps * 0.5
    return recovered, (
        f"{recovered:.0%} of book quality restored {minutes_elapsed:g}min in; crossing NOW costs "
        f"about {cost_now_bps:.1f}bp of excess half-spread against a {e.normal_spread_bps:g}bp "
        "normal book. "
        + ("The book has recovered -- execution is no longer the binding constraint"
           if recovered >= 0.8 else
           f"Waiting one more half-life ({half_life_minutes:g}min) halves that. It can be "
           "economically correct to wait even when the directional expectancy is already "
           "positive, and a book that always crosses immediately pays the rebound away"))


def summarise(events: list[DeclineEvent],
              history: dict[str, list[tuple[float, float, float]]] | None = None
              ) -> dict[str, object]:
    """Report shape for `data/opportunity_books.json`."""
    if not events:
        return {"events": 0, "headline": (
            "no decline events recorded -- every drawdown on this desk is currently unclassified, "
            "so a forced-deleveraging flush and a fundamental repricing look identical")}
    hist = history or {}
    rows = []
    counts: dict[str, int] = {}
    for e in events:
        est = rebound_estimate(e, hist)
        counts[est.mechanism] = counts.get(est.mechanism, 0) + 1
        rows.append({
            "event_id": e.event_id, "symbol": e.symbol, "depth": e.depth,
            "mechanism": est.mechanism,
            "p_rebound": est.p_rebound,
            "expected_bounce": est.expected_bounce,
            "expected_max_adverse": est.expected_max_adverse,
            "median_recovery_hours": est.median_recovery_hours,
            "n_historical_events": est.n_events,
            "why": est.why,
        })
    tradeable = [r for r in rows if r["p_rebound"] is not None]
    unclassified = counts.get("MIXED_UNKNOWN", 0)
    return {
        "events": len(events),
        "counts_by_mechanism": counts,
        "rows": rows,
        "estimable": len(tradeable),
        "unclassified": unclassified,
        "headline": (
            f"{len(tradeable)} of {len(events)} decline(s) carry a mechanism-conditional rebound "
            f"distribution; {unclassified} are UNCLASSIFIED and earn none"
            if tradeable else
            f"0 of {len(events)} declines are estimable -- {unclassified} unclassified and the "
            f"rest lack {MIN_EVENTS_FOR_A_DISTRIBUTION}+ historical events of their mechanism. "
            "Every rebound expectation on this desk is currently UNMEASURED"),
        "note": ("There is no universal buy-the-crash rule in this module and none can be added: "
                 "an unclassified decline returns None everywhere. A 15% fall from forced "
                 "deleveraging and a 15% fall from new information have opposite forward "
                 "distributions, and a rule that cannot separate them is right often enough to "
                 "keep running and wrong exactly when the losses are large. Price opportunity and "
                 "EXECUTION opportunity are priced separately -- crossing into a wrecked book pays "
                 "the rebound away in slippage."),
    }
