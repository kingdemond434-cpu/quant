"""THE FIFTEEN PHENOMENA A BOOK CAN EARN FROM, and which of them this desk actually occupies.

WHY A DECLARED TAXONOMY AND NOT ANOTHER CLUSTERING. `desks/mt5/research/alpha_genome.py` already
clusters certificates by their STRUCTURE -- same mechanism class, same direction bias, same entry
clock, a shared currency leg -- and it is the right tool for catching a duplicate wearing a new
name. It cannot answer the question the principal asked, because it derives its clusters FROM THE
BOOK: a desk holding fifty session-breakout sleeves and nothing else gets a tidy one-cluster
genome and no hint that thirteen other ways of making money exist. A clustering can only ever
name the ground the desk already stands on. Naming the EMPTY ground needs a list written from
outside the book, and that is what this is.

    "The target shape is 8-15 genuinely independent alpha clusters. Classify the existing book
     into those clusters and report which are empty. An empty cluster is a research target, and
     naming it is most of the value here."                          -- the principal, 2026-09-05

WHAT MAKES TWO CLUSTERS DIFFERENT. Not the instrument, not the timeframe, not the indicator: the
PAYER. Each cluster below names who is on the other side and why they are there -- a rebalancing
fund that must trade at a fixing, a dealer who must hedge an option, a carry investor paid to hold
risk, a stop cascade that must liquidate. Two edges that take money from the same payer for the
same reason lose money on the same day, whatever their code looks like. That is the only
definition of independence that survives a drawdown, and it is why this list is written in terms
of mechanisms rather than of signals.

CLASSIFICATION IS DECLARED, NEVER INFERRED. A family absent from `FAMILY_CLUSTER` is
`UNCLASSIFIED`, and UNCLASSIFIED is reported as its own bucket rather than being distributed over
the real ones. The temptation is to guess -- "discovered" edges are probably mean reversion, so
put them there -- and the cost of guessing is precisely the number this module exists to protect:
a cluster looks occupied, no research goes to it, and the occupancy was an assumption. An
unclassified sleeve is evidence that the desk does not know what phenomenon it is monetising,
which is a finding and not a gap to paper over.

NOTHING HERE SIZES, GATES OR PROMOTES ANYTHING. It maps a name to a phenomenon and counts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

__all__ = [
    "CLUSTERS",
    "FAMILY_CLUSTER",
    "SESSION_SELECTORS",
    "TARGET_MAX",
    "TARGET_MIN",
    "UNCLASSIFIED",
    "AlphaCluster",
    "classify_family",
    "classify_sleeve",
    "cluster_of",
    "occupancy",
]

#: The bucket for a family this module has never been told about. NOT a residual dump for
#: everything hard to place -- it is the statement "the desk cannot name this edge's payer".
UNCLASSIFIED = "UNCLASSIFIED"

#: The band the principal named. Below TARGET_MIN the book is too narrow for leverage to be the
#: lever; above TARGET_MAX the marginal cluster is more likely a relabelling than a new payer.
TARGET_MIN = 8
TARGET_MAX = 15


@dataclass(frozen=True)
class AlphaCluster:
    """One phenomenon, named by who pays and why they cannot stop."""

    key: str
    title: str
    #: The counterparty and their constraint. This is the field that makes two clusters different.
    payer: str
    #: What a hunter would go and look for. Concrete enough to become a research task.
    hunt: str


#: THE FIFTEEN. Ordered as the principal listed them, because the order is his and reordering a
#: declared list makes diffs lie about what changed.
CLUSTERS: tuple[AlphaCluster, ...] = (
    AlphaCluster(
        "session_liquidity", "Session and liquidity structure",
        "Participants whose clock forces them to trade -- desks handing over between Tokyo, "
        "London and New York, and the liquidity vacuum between them.",
        "Range compression and expansion around session boundaries, the first hour after a "
        "centre opens, the hour a centre goes home, and the depth that leaves with it."),
    AlphaCluster(
        "cross_asset_lead_lag", "Cross-asset lead / lag",
        "Slow updaters. One market prices news before another that shares the same driver, "
        "because its participants watch a different screen.",
        "A driver that moves first (rates, oil, the index future) against an instrument that "
        "prices it late; the edge is the lag, measured in bars, not the correlation."),
    AlphaCluster(
        "macro_rates", "Macro and rates",
        "Investors paid to hold macro risk -- carry, real-yield and terms-of-trade exposure "
        "that someone must be compensated to warehouse.",
        "Rate and real-yield differentials, central-bank path repricing, commodity terms of "
        "trade, and the currencies that must absorb them."),
    AlphaCluster(
        "event_surprise", "Scheduled-event surprise",
        "Anyone who must be positioned before a release and cannot wait for the number.",
        "The distribution of the move CONDITIONAL on surprise sign and size at a scheduled "
        "release, and the reversal or continuation that follows it."),
    AlphaCluster(
        "relative_value", "Relative value and residual",
        "Arbitrage capacity that is finite. A cross is its two legs up to the cross spread, and "
        "the residual is flow specific to the cross rather than to either currency.",
        "Triangles, cointegrated pairs, PCA residuals against the driver basket -- the residual "
        "series, never the level."),
    AlphaCluster(
        "fixing_roll_calendar", "Fixing, roll and calendar",
        "Mandated traders: an index that must rebalance, a fund that must mark at a fixing, a "
        "future that must roll, a month that must end.",
        "The WMR and ECB fixings, futures roll windows, month and quarter end, index rebalance "
        "dates -- flow that is scheduled and price-insensitive."),
    AlphaCluster(
        "volatility_transition", "Volatility regime transition",
        "Anyone sized for the volatility that just ended. A regime change forces them to "
        "re-size at the worst moment.",
        "Compression that precedes expansion, expansion that mean-reverts, and the change point "
        "itself -- traded as a state, not as a level."),
    AlphaCluster(
        "trend", "Trend and momentum",
        "Slow reallocators who move capital over weeks, and the risk premium for holding a "
        "position through the drawdowns that make trend uncomfortable.",
        "Persistent drift at horizons the book does not already hold, across the whole "
        "Fusion universe rather than one instrument."),
    AlphaCluster(
        "mean_reversion", "Mean reversion and liquidity provision",
        "Impatient liquidity takers. Someone paid the spread and pushed price away from value, "
        "and is willing to pay again to get out.",
        "Overshoot after a shock, gap decay, failed breakouts, and the half-life of the return "
        "to value."),
    AlphaCluster(
        "positioning_flow", "Positioning and crowding",
        "Crowded holders. A position everyone holds must be unwound into a market with nobody "
        "left to sell to.",
        "COT and futures open interest, retail positioning, swap and financing skew -- the "
        "state of who is already on."),
    AlphaCluster(
        "options_implied", "Options-implied state",
        "Dealers who are short gamma and must hedge into the move, and the risk premium in "
        "implied against realised volatility.",
        "Implied-realised spread, skew, gamma exposure at strikes, and the pinning or "
        "acceleration each implies for the underlying."),
    AlphaCluster(
        "execution_entry", "Execution and entry alpha",
        "The desk's own past self. Money made or lost between the decision and the fill is a "
        "P&L source with no market view at all.",
        "Passive against aggressive entry, the queue, the pullback that would have been filled, "
        "and the markout curve of the desk's own orders."),
    AlphaCluster(
        "news_reaction", "Unscheduled news reaction",
        "Everyone who has to reprice on an unscheduled headline, in the minutes before the "
        "market agrees what it means.",
        "Central-bank tone, geopolitical and policy headlines -- the reaction function, not the "
        "sentiment score."),
    AlphaCluster(
        "cross_sectional_fx", "Cross-sectional selection",
        "Whoever is on the other side of the spread between the strongest and weakest member of "
        "a basket, when the basket itself is not the bet.",
        "Rank instruments on a characteristic and trade the spread, with the common factor "
        "demeaned out so the basket direction is not the trade."),
    AlphaCluster(
        "crisis_drawdown", "Crisis and drawdown alpha",
        "Forced deleveraging. Stops, margin calls and risk limits liquidate into a market that "
        "already has no bid, and the liquidation itself is the opportunity.",
        "Mechanisms with POSITIVE expectancy specifically inside the book's own worst periods. "
        "Standalone Sharpe is not the bar here -- the bar is the sign, in that state."),
)

#: key -> cluster, built once. A tuple keeps the declared order; this makes lookup cheap.
_BY_KEY: dict[str, AlphaCluster] = {c.key: c for c in CLUSTERS}

#: FAMILY -> CLUSTER. Every family the desk's registries name, mapped to the phenomenon it
#: monetises. Written out rather than pattern-matched, so adding a family is a decision somebody
#: makes rather than a regex accident. Keys are matched case-insensitively as SUBSTRINGS of a
#: sleeve label by `classify_sleeve`, longest key first, so `m15_anti_breakout` cannot be
#: swallowed by `breakout`.
FAMILY_CLUSTER: dict[str, str] = {
    # -- session and liquidity structure
    "session_range_breakout": "session_liquidity",
    "level_breakout": "session_liquidity",
    "dav_range_filter_adx": "session_liquidity",
    "liquidity_regime": "session_liquidity",
    "orderflow_imbalance": "session_liquidity",
    "spread_state": "session_liquidity",
    "clock_transition": "session_liquidity",
    # -- cross-asset lead / lag
    "cross_asset_lead_lag": "cross_asset_lead_lag",
    "lead_lag": "cross_asset_lead_lag",
    # -- macro and rates
    "carry": "macro_rates",
    "macro_conditional": "macro_rates",
    "rates_conditional": "macro_rates",
    # -- scheduled-event surprise
    "event_reaction": "event_surprise",
    "event_surprise": "event_surprise",
    # -- relative value and residual
    "relative_value": "relative_value",
    "cross_asset_residual": "relative_value",
    "pca_residual": "relative_value",
    "correlation_regime": "relative_value",
    "triangle": "relative_value",
    "rv_triangle": "relative_value",
    # -- fixing, roll and calendar
    "dow_effect": "fixing_roll_calendar",
    "turn_of_month": "fixing_roll_calendar",
    "calendar_month": "fixing_roll_calendar",
    "monday_gap": "fixing_roll_calendar",
    "fixing": "fixing_roll_calendar",
    "roll": "fixing_roll_calendar",
    # -- volatility regime transition
    "vol_transition": "volatility_transition",
    "vol_mean_reversion": "volatility_transition",
    "momentum_volgate": "volatility_transition",
    "regime_transition": "volatility_transition",
    # -- trend
    "asia_momentum": "trend",
    "london_close_momentum": "trend",
    "multi_speed_trend": "trend",
    "trend": "trend",
    # -- mean reversion and liquidity provision
    "overnight_gap_decay": "mean_reversion",
    "failed_breakout": "mean_reversion",
    "fair_value_gap": "mean_reversion",
    "m15_anti_breakout": "mean_reversion",
    "m15_anti_momentum": "mean_reversion",
    "m5_anti_breakout": "mean_reversion",
    "m5_anti_momentum": "mean_reversion",
    "anti_breakout": "mean_reversion",
    "anti_momentum": "mean_reversion",
    # -- positioning and crowding
    "cot_positioning": "positioning_flow",
    "positioning": "positioning_flow",
    "crowding": "positioning_flow",
    # -- options-implied state
    "implied_vol": "options_implied",
    "gamma_exposure": "options_implied",
    # -- execution and entry alpha
    "entry_alpha": "execution_entry",
    "execution_alpha": "execution_entry",
    # -- unscheduled news reaction
    "cb_tone": "news_reaction",
    "news_reaction": "news_reaction",
    # -- cross-sectional selection
    "cross_sectional": "cross_sectional_fx",
    "style_premia": "cross_sectional_fx",
    "rank_ic": "cross_sectional_fx",
    # -- crisis and drawdown alpha
    "drawdown_conditional": "crisis_drawdown",
    "crisis_only": "crisis_drawdown",
    "tail_alpha": "crisis_drawdown",
}

#: FAMILY_CLUSTER keys, longest first. `m15_anti_breakout` must win over `anti_breakout`, which
#: must win over nothing at all -- a shorter key matching first would misfile the sleeve into a
#: cluster whose payer is different, which is the one error this module cannot tolerate.
_KEYS_BY_LENGTH: tuple[str, ...] = tuple(sorted(FAMILY_CLUSTER, key=len, reverse=True))

#: SESSION WORDS THAT ARE SOMETIMES A FAMILY AND SOMETIMES A SELECTOR, and the whole reason
#: `classify_sleeve` is not a plain substring search.
#:
#: `USDJPY_asia` IS the Asia session-range family: the session is the mechanism, and the cluster
#: is session/liquidity structure. `EURGBP_discovered_asia` is a family called `discovered` that
#: happens to TRADE in Asia, and its phenomenon is unknown. A substring search cannot tell those
#: apart and would file the second one as session structure -- a cluster would read as occupied
#: on the strength of a timestamp, no research would go to it, and the occupancy would be an
#: assumption. So a selector wins ONLY when nothing else is left in the label.
SESSION_SELECTORS: frozenset[str] = frozenset({
    "asia", "tokyo", "london", "am", "pm", "afternoon", "morning", "ny", "newyork",
    "overlap", "overnight", "close", "open", "session",
})

#: Instrument and provenance tokens that carry no mechanism: the symbol, the metal or index
#: prefix, the hunt file a certificate came from. Dropped before the selector fallback so that
#: `XAUUSD_afternoon` reduces to `{afternoon}` and not to `{xauusd, afternoon}`.
_NOISE_TOKENS: frozenset[str] = frozenset({
    "xau", "xag", "xpt", "xpd", "xcu", "btc", "eth", "usd", "eur", "gbp", "jpy", "chf", "cad",
    "aud", "nzd", "sek", "nok", "dkk", "pln", "czk", "huf", "try", "zar", "mxn", "sgd", "hkd",
    "cnh", "external", "qquant", "json", "scalp", "ledger", "shadow", "long", "short", "side",
})

#: Condition tags a sleeve label carries to name the STATE it was certified in, not its
#: mechanism. `CADJPY_london_am_NORMAL_DAY` is the london_am family on normal days.
_CONDITION_TOKENS: frozenset[str] = frozenset({
    "normal", "day", "failed", "break", "macro", "fav", "adverse", "quiet", "event",
})


def classify_family(family: str) -> str:
    """The cluster a DECLARED family belongs to, or UNCLASSIFIED. Exact match only.

    Exact, because a family name is a registry key and the registry either knows it or does not.
    `classify_sleeve` is the label form, for names that carry a symbol, a selector and a condition
    around the family; keeping the two apart stops a registry lookup succeeding on a prefix.
    """
    key = str(family).strip().lower()
    if key in FAMILY_CLUSTER:
        return FAMILY_CLUSTER[key]
    if key and all(tok in SESSION_SELECTORS for tok in _tokens(key)):
        return "session_liquidity"
    return UNCLASSIFIED


def _tokens(label: str) -> list[str]:
    """Lowercase alphanumeric tokens of a label, split on every separator this desk uses."""
    out: list[str] = []
    cur: list[str] = []
    for ch in str(label).lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def classify_sleeve(sleeve: str) -> str:
    """The cluster a SLEEVE LABEL belongs to. Declared family first; the session only as a last
    resort; UNCLASSIFIED whenever neither applies.

    Sleeve labels on this desk are `SYMBOL_family_selector` (`GBPZAR_overnight_gap_decay_asia`),
    `xau_m15_anti_momentum`, or a qquant cell path. The family is in there but is not delimited
    consistently, so the family match is by substring, LONGEST KEY FIRST -- which is what stops
    `..._m15_anti_breakout_...` being read as a session breakout.

    The session fallback fires only when every remaining token is a selector, an instrument or a
    condition. That is the difference between "the Asia session IS this sleeve's mechanism" and
    "this sleeve's mechanism is unnamed and it trades in Asia", and getting it wrong would make an
    empty cluster look occupied. A label matching neither is UNCLASSIFIED, never the nearest
    cluster: a sleeve whose phenomenon the desk cannot name is a finding about the desk.
    """
    low = str(sleeve).strip().lower()
    if not low:
        return UNCLASSIFIED
    for key in _KEYS_BY_LENGTH:
        if key in low:
            return FAMILY_CLUSTER[key]
    rest = [t for t in _tokens(low)
            if t not in _NOISE_TOKENS and t not in _CONDITION_TOKENS
            and not t.isdigit() and not (len(t) == 6 and t.isalpha()
                                         and t[:3] in _NOISE_TOKENS and t[3:] in _NOISE_TOKENS)]
    if rest and all(t in SESSION_SELECTORS for t in rest):
        return "session_liquidity"
    return UNCLASSIFIED


def occupancy(labels: Iterable[str], weights: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Which clusters the book occupies, which are empty, and how lopsided the occupancy is.

    ``labels`` is one cluster key per sleeve (repeat a key for every sleeve in it).
    ``weights`` optionally maps a cluster key to the share of book risk it carries; absent, every
    sleeve counts one. A cluster with sleeves in it is OCCUPIED however small its weight -- the
    weighted view is reported beside the count, never instead of it, because "we have a crisis
    sleeve at 0.4% of heat" and "we have no crisis sleeve" are different sentences and only the
    first can be scaled.

    EMPTY IS THE OUTPUT. `empty` is the research agenda, in the principal's own framing: the
    marginal sleeve of an unoccupied cluster buys more breadth than the eleventh sleeve of an
    occupied one, because k_eff = n/(1+(n-1)rho) is concave in n at any rho above zero.
    """
    counts: dict[str, int] = {c.key: 0 for c in CLUSTERS}
    counts[UNCLASSIFIED] = 0
    for label in labels:
        key = str(label)
        counts[key] = counts.get(key, 0) + 1
    occupied = [c.key for c in CLUSTERS if counts.get(c.key, 0) > 0]
    empty = [c.key for c in CLUSTERS if counts.get(c.key, 0) == 0]
    n_sleeves = sum(counts.values())
    largest = max((counts.get(c.key, 0) for c in CLUSTERS), default=0)
    w = {k: float(v) for k, v in (weights or {}).items()}
    return {
        "n_clusters_declared": len(CLUSTERS),
        "n_occupied": len(occupied),
        "n_empty": len(empty),
        "n_sleeves": n_sleeves,
        "n_unclassified": counts.get(UNCLASSIFIED, 0),
        "counts": {k: v for k, v in counts.items() if v > 0},
        "occupied": occupied,
        "empty": empty,
        "weights": w,
        "largest_cluster_share": (largest / n_sleeves) if n_sleeves else 0.0,
        "target_band": [TARGET_MIN, TARGET_MAX],
        "meets_target": TARGET_MIN <= len(occupied) <= TARGET_MAX,
        "empty_detail": [
            {"cluster": c.key, "title": c.title, "payer": c.payer, "hunt": c.hunt}
            for c in CLUSTERS if counts.get(c.key, 0) == 0
        ],
        "why": (
            f"{len(occupied)} of {len(CLUSTERS)} declared phenomena occupied by {n_sleeves} "
            f"sleeves; {counts.get(UNCLASSIFIED, 0)} sleeve(s) monetise a phenomenon the desk "
            "cannot name. Occupancy is a COUNT of distinct payers, not a claim that the occupied "
            "ones are independent of each other -- that is measured separately, from returns and "
            "from exposures, and is always the smaller number"),
    }


def cluster_of(key: str) -> AlphaCluster | None:
    """The declared cluster record for a key, or None for UNCLASSIFIED and for anything unknown."""
    return _BY_KEY.get(str(key))
