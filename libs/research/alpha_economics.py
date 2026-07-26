"""Alpha Economics Engine -- score research ideas by EXPECTED VALUE *before* spending effort.

Maximises expected log-growth per research-hour, not the number of alphas explored. Every candidate
is scored PRE-research; only ideas above the EV threshold enter the queue, the rest are rejected
immediately and their killing pattern recorded so the same class is never re-tried. This is the
"should we build this?" gate that runs before "can we build this?".

    EV = P(survive) * dSharpe * breadth_f * capacity_f * orthogonality / (effort_h * maintenance)

P(survive) starts from the desk's honest base rate (near-zero survivors historically) and is moved
by META-LEARNED PRIORS distilled from our own graveyard -- the patterns that repeatedly kill or save
ideas. These priors are the compounding asset: every resolved hypothesis sharpens them and cuts
future wasted research. Pure/stdlib, offline, deterministic -> testable + cheap to run each cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.research.capacity_policy import DEFAULT_BOOK_USD, DEFAULT_SLEEVES, capacity_fit

# Meta-learned priors (multiplicative on P(survive)), distilled from the desk's resolved outcomes.
# Each is an economic pattern, not a fitted parameter -- update ONLY when the graveyard teaches a
# new durable lesson. See docs/institutional_knowledge.md for the evidence behind each.
_PRIORS: dict[str, float] = {
    "price_only": 0.30,          # momentum/reversal/lowvol on price alone -> mostly die net-of-cost
    "narrow_breadth": 0.25,      # breadth < ~5 starves IR even w/ positive IC (VRP)
    "high_turnover_no_maker": 0.50,  # turnover cost kills thin edges without maker execution
    "no_economic_mechanism": 0.20,   # data-mined w/ no risk-premium story -> overfit, won't persist
    "funding_family": 2.0,       # funding/carry is the lone repeat survivor -> real risk premium
    "new_orthogonal_data": 1.6,  # a genuinely NEW free data axis raises odds (most of edge is data)
    "crowded_known": 0.35,       # published/crowded -> decayed before we arrive
}
_BASE_P = 0.15                   # honest base rate: most rigorously-tested candidates fail
_EV_THRESHOLD = 0.05            # below this, reject immediately (not worth the research-hours)


@dataclass
class Idea:
    """A research candidate, described BEFORE any backtest (so the gate is pre-registered)."""
    name: str
    est_sharpe: float = 0.5      # honest prior on standalone Sharpe contribution (be conservative)
    breadth: int = 20            # number of independent bets/assets the signal spans
    # Rough $ the edge absorbs before decay. Defaulted to bare sufficiency for this book, NOT to
    # the old $1m: an unestimated idea is not a fund-scale idea, and a seven-figure default
    # silently assumed every unmeasured candidate was one.
    capacity_usd: float = 200_000.0
    book_usd: float = DEFAULT_BOOK_USD   # WHOLE book; sleeved below, since one idea is one sleeve
    n_sleeves: int = DEFAULT_SLEEVES
    orthogonality: float = 0.5   # 0..1 correlation-complement to book (1 = fully new)
    effort_h: float = 8.0        # engineering hours to test it properly
    maintenance: float = 1.0     # ongoing upkeep multiplier (1 = light, >1 = heavy)
    tags: list[str] = field(default_factory=list)   # which _PRIORS apply (economic descriptors)


def p_survive(idea: Idea) -> float:
    """Base survival rate moved by every meta-learned prior whose tag the idea carries."""
    p = _BASE_P
    for t in idea.tags:
        p *= _PRIORS.get(t, 1.0)
    return round(min(max(p, 0.0), 0.95), 4)


def ev_score(idea: Idea) -> dict[str, Any]:
    """Expected-value score + a pre-research verdict. Higher EV = more log-growth per hour."""
    p = p_survive(idea)
    breadth_f = min(idea.breadth / 20.0, 3.0) ** 0.5           # IR ~ IC*sqrt(breadth); diminishing
    # §39 PARITY. This was `min(cap/1e6, 5)**0.25`, monotone in raw size: a $50k-capacity edge was
    # scored 0.47 and a $5M one 1.50, a 3.2x EV penalty on precisely the capacity-bound niche
    # PROSPECTOR_SPEC calls this desk's one structural advantage. Capacity you cannot fill is not
    # EV -- so it now scores as sufficiency for `book_usd` and is FLAT once sufficient.
    capacity_f = capacity_fit(idea.capacity_usd, idea.book_usd, idea.n_sleeves)
    denom = max(idea.effort_h, 0.5) * max(idea.maintenance, 0.5)
    ev = (p * max(idea.est_sharpe, 0.0) * breadth_f * capacity_f
          * max(idea.orthogonality, 0.0) / denom)
    ev = round(ev, 4)
    # hard economic kills -> reject regardless of EV arithmetic (the graveyard's clearest lessons)
    hard_kill = ("no_economic_mechanism" in idea.tags) or \
                ("price_only" in idea.tags and "narrow_breadth" in idea.tags)
    verdict = ("REJECT (hard economic kill)" if hard_kill
               else "REJECT (EV below thresh)" if ev < _EV_THRESHOLD
               else "QUEUE (top-EV -> research)")
    return {"name": idea.name, "ev": ev, "p_survive": p, "breadth_f": round(breadth_f, 3),
            "verdict": verdict, "tags": list(idea.tags)}


def rank(ideas: list[Idea]) -> list[dict[str, Any]]:
    """Score a batch and rank by EV desc -> the research queue. Only 'QUEUE' verdicts should run."""
    return sorted((ev_score(i) for i in ideas), key=lambda s: -float(s["ev"]))
