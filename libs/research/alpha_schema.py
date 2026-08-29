"""A coordinate system for MECHANISMS, so search can be aimed instead of sprayed.

WHY THIS EXISTS

Measured on this desk 2026-08-29: of 12,523 docket cells, 10,612 (85%) are `discovered` --
statistical price-shape primitives -- and every one of the 816 cells terminal-rejected at the
economic prior came from that family, with the verdict "no economic cause is encoded by this
price-shape primitive". The desk spends the large majority of its research compute manufacturing
exactly what its own first gate exists to destroy.

That is not a tuning problem. A formula search explores the space of EXPRESSIONS; the gate asks a
question about the space of CAUSES, and nothing connects the two. So the generator cannot aim at
what the gate rewards even in principle, and its hit rate is whatever chance provides.

WHAT THIS CHANGES

A candidate is addressed by where it sits in a mechanism space rather than by what its formula
looks like:

    EVENT x CONTEXT x QUALITY x DIRECTION x HORIZON

    EVENT      what happened in the world (a fixing, a liquidation, an inventory shock)
    CONTEXT    the state it happened in (Asia session, thin liquidity, post-event)
    QUALITY    what was abnormal about it (magnitude, persistence, failed continuation)
    DIRECTION  the response being claimed (continuation, reversal, vol expansion)
    HORIZON    the clock the claim lives on (5m .. daily)

Every EVENT in the registry carries a PAYER -- the counterparty whose behaviour funds the edge --
because an edge with no payer is a pattern, and the economic prior is the gate that knows the
difference. A coordinate therefore arrives with its mechanism already named, which is why
candidates generated this way pass gate 1 by construction rather than by luck.

WHAT IT MAKES MEASURABLE

  * COVERAGE -- which regions this desk has actually searched. "Exhausted" is a claim that needs
    per-axis evidence (L1.51), and until now there was no axis to be evidenced against.
  * YIELD -- which regions produced cells that survived, so budget follows the map rather than
    the loudest generator.
  * ABSENCE -- regions never visited at all. On a desk whose binding constraint is orthogonality
    (n_eff ~5.5 across 23 certificates), an unvisited region is worth more than another variant
    of a crowded one.

DELIBERATELY NOT A GENERATOR AND NOT A GATE. It defines and scores the space. What proposes
candidates inside a region and what judges them are separate organs, and keeping them separate is
what stops a search that can see the scoreboard from learning to game it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------------- the axes

#: EVENTS carry their PAYER. This is the whole reason the schema exists: an event with no
#: identifiable counterparty is a chart pattern, and `economic_prior` rejects it correctly.
#: `evidence` cites why the mechanism is believed to exist at all -- public research or this
#: desk's own tape -- so a reviewer can attack the claim rather than the formula.
EVENTS: dict[str, dict[str, str]] = {
    "fx_fixing_flow": {
        "payer": "benchmark-tracking customers whose FX demand is predictable in time",
        "mechanism": ("dealers pre-hedge a known fixing demand, pushing price into the fix; the "
                      "pressure relaxes once the demand clears"),
        "evidence": ("Krohn & Muller, Journal of Finance 2024, V-shaped reversal around Tokyo "
                     "and European fixes across G9; reversal times track the fixing clock rather "
                     "than equity opens or macro releases"),
        "falsifier": ("the effect does not align with the fixing clock, or survives equally at "
                      "randomly chosen pseudo-fix times"),
    },
    "forced_liquidation": {
        "payer": "leveraged directional traders closed out by margin rules, not by choice",
        "mechanism": ("forced size crosses a thin book and overshoots fair value; price recovers "
                      "once the forced flow is exhausted"),
        "evidence": "this desk's own liquidation tape and the crypto desk's carry work",
        "falsifier": "the effect disappears when the liquidation variable is shuffled",
    },
    "carry_rollover": {
        "payer": "the holder of the negative-carry leg, who pays to hold it",
        "mechanism": ("a rate differential is paid daily to the long side of the higher-yielding "
                      "leg; a return stream with no directional thesis"),
        "evidence": ("venue-recorded swap terms; measured on this desk 2026-08-28 across 32 "
                     "cells once the swap reader was repaired"),
        "falsifier": "the edge does not scale with the recorded swap differential",
    },
    "inventory_shock": {
        "payer": "a dealer holding unwanted inventory who must offload it",
        "mechanism": "temporary price concession to move risk, reversing as inventory normalises",
        "evidence": "market-microstructure inventory models; spread and depth on this desk's tape",
        "falsifier": "the concession does not scale with observed depth or spread widening",
    },
    "macro_release": {
        "payer": "traders repricing on scheduled information, and those caught positioned wrong",
        "mechanism": "a scheduled information shock forces repositioning at a known clock time",
        "evidence": "the desk's economic calendar vintages",
        "falsifier": "the effect is present equally on non-release days at the same clock time",
    },
    "session_handover": {
        "payer": "participants who must transfer risk across a liquidity discontinuity",
        "mechanism": ("liquidity and participant mix change discretely at session boundaries, so "
                      "risk transferred across them is priced differently"),
        "evidence": "this desk's session families and its measured per-hour spread surface",
        "falsifier": "the effect does not move when the session boundary moves (DST, holidays)",
    },
    "volatility_shock": {
        "payer": "holders of short-gamma exposure who must hedge into the move",
        "mechanism": "a volatility jump forces mechanical hedging that amplifies then decays",
        "evidence": "realised-volatility structure on this desk's own bars",
        "falsifier": "the effect does not scale with the size of the volatility jump",
    },
    "cross_market_lead": {
        "payer": "participants in the slower venue who have not yet repriced",
        "mechanism": "information arrives in one market first and propagates with a lag",
        "evidence": "cross-asset residual families already on this desk",
        "falsifier": "the lead/lag reverses or vanishes out of sample",
    },
}

CONTEXTS: tuple[str, ...] = (
    "asia_session", "london_session", "ny_session", "session_overlap",
    "high_volatility", "low_volatility", "thin_liquidity", "wide_spread",
    "trending", "ranging", "pre_event", "post_event", "month_end", "holiday_thin",
)

QUALITIES: tuple[str, ...] = (
    "abnormal_magnitude", "persistence", "acceleration", "order_imbalance",
    "failed_continuation", "dispersion", "exhaustion", "gap",
)

DIRECTIONS: tuple[str, ...] = (
    "continuation", "reversal", "relative_value", "vol_expansion", "vol_compression",
)

HORIZONS: tuple[str, ...] = ("5m", "15m", "1h", "4h", "1d")


@dataclass(frozen=True)
class Coordinate:
    """One addressable region of mechanism space."""

    event: str
    context: str
    quality: str
    direction: str
    horizon: str

    def key(self) -> str:
        return f"{self.event}|{self.context}|{self.quality}|{self.direction}|{self.horizon}"

    @property
    def payer(self) -> str:
        return EVENTS.get(self.event, {}).get("payer", "UNKNOWN")

    @property
    def mechanism(self) -> str:
        return EVENTS.get(self.event, {}).get("mechanism", "")

    @property
    def falsifier(self) -> str:
        return EVENTS.get(self.event, {}).get("falsifier", "")

    def is_named(self) -> bool:
        """True when this coordinate carries a real payer -- what `economic_prior` asks for."""
        return self.event in EVENTS


def space_size() -> int:
    return len(EVENTS) * len(CONTEXTS) * len(QUALITIES) * len(DIRECTIONS) * len(HORIZONS)


def enumerate_space() -> list[Coordinate]:
    """Every addressable region. Small enough to hold, large enough to be worth aiming at."""
    return [
        Coordinate(e, c, q, d, h)
        for e in EVENTS
        for c in CONTEXTS
        for q in QUALITIES
        for d in DIRECTIONS
        for h in HORIZONS
    ]


@dataclass(frozen=True)
class RegionStat:
    coordinate: str
    searched: int = 0
    survived: int = 0
    branches: int = 0

    @property
    def yield_rate(self) -> float:
        return (self.survived / self.searched) if self.searched else 0.0


@dataclass(frozen=True)
class CoverageReport:
    space: int
    visited: int
    unvisited: int
    productive: list[str] = field(default_factory=list)
    barren: list[str] = field(default_factory=list)
    never_tried: list[str] = field(default_factory=list)
    note: str = ""


def coverage(stats: dict[str, RegionStat], *, top: int = 10) -> CoverageReport:
    """Where the desk has searched, where that paid, and what it has never touched.

    UNVISITED IS THE HEADLINE. A region nobody has tried is not a gap in a report, it is the only
    place a genuinely uncorrelated edge can still come from -- and on a book already at n_eff ~5.5
    that is worth more than another variant of a region already mined.
    """
    total = space_size()
    all_keys = {c.key() for c in enumerate_space()}
    visited = {k for k, s in stats.items() if s.searched > 0}
    productive = sorted(
        (s for s in stats.values() if s.searched >= 5 and s.survived > 0),
        key=lambda s: (-s.yield_rate, -s.survived),
    )
    barren = sorted(
        (s for s in stats.values() if s.searched >= 20 and s.survived == 0),
        key=lambda s: -s.searched,
    )
    never = sorted(all_keys - visited)
    return CoverageReport(
        space=total,
        visited=len(visited),
        unvisited=total - len(visited),
        productive=[s.coordinate for s in productive[:top]],
        barren=[s.coordinate for s in barren[:top]],
        never_tried=never[:top],
        note=(f"{len(visited)} of {total} mechanism regions searched; "
              f"{len(productive)} productive, {len(barren)} barren after >=20 attempts, "
              f"{total - len(visited)} never tried"),
    )


def describe(coord: Coordinate) -> dict[str, Any]:
    """The hypothesis skeleton for a region -- what a proposer must fill in and a reviewer attack.

    Returns the MECHANISM, never a formula. What signal expresses it is the compiler's problem;
    keeping the two apart is what stops a generator from dressing a price-shape primitive in the
    language of a cause it does not implement.
    """
    return {
        "coordinate": coord.key(),
        "event": coord.event,
        "payer": coord.payer,
        "mechanism": coord.mechanism,
        "context": coord.context,
        "quality": coord.quality,
        "direction": coord.direction,
        "horizon": coord.horizon,
        "falsifier": coord.falsifier,
        "evidence": EVENTS.get(coord.event, {}).get("evidence", ""),
        "economic_prior_ready": coord.is_named(),
    }
