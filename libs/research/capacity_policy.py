"""THE desk's capacity policy: one leaf module, one definition of what capacity is worth.

Capacity is judged as SUFFICIENCY for the book actually deployed, never as magnitude. That single
rule has to hold in the survival gate, in both rank scorers, in acceptance and in the audit --
which is exactly why they now all call in here instead of each carrying their own dollar constant.

WHY A LEAF. Five copies of this policy existed and they disagreed; fixing the gate in isolation on
2026-07-26 left the other four intact, so the exclusion simply moved to where it was harder to
see. This module therefore imports NOTHING from libs beyond a lazy, exception-guarded read of the
ThresholdBook -- so nothing can ever be "too circular to import the real policy" and be tempted to
re-inline its own copy. That constraint is load-bearing, not stylistic; keep it.

The survival gate was fixed on 2026-07-26 to stop hard-rejecting sub-$100k edges (capacity is a
ratio to deployed equity, not a dollar figure). That removed a categorical EXCLUSION. It did not
give the niche PARITY, because four separate scorers still rewarded bigger capacity monotonically:

    libs/discovery/objective.py     capacity_term = min(1, cap/1e6)          -> 1.9x rank penalty
    libs/research/alpha_economics.py capacity_f   = min(cap/1e6, 5)**0.25    -> 3.2x EV penalty
    libs/discovery/factory.py       capacity_pass = cap >= 1e5          -> the flat floor, again
    libs/alpha_factory/capacity_intelligence.py  scalability = cap/reference -> monotone in size

So a $50k-capacity listing dislocation could pass the gate and still lose every ranking to a
fund-shaped idea it beats on every dimension that pays. Being ALLOWED into the niche while being
SCORED out of it is not parity -- it is the same exclusion moved one layer down, where it is
harder to see. This module is the single scorer all four now share.

THE ECONOMICS. Capacity is worth exactly what it lets you deploy and not one dollar more. Once an
edge absorbs several multiples of the equity you have, additional capacity buys you NOTHING you
can spend -- a $200k edge and a $200M edge are identical to a $50k book. Rewarding the $200M edge
is not caution, it is preferring an option you cannot exercise. The score is therefore:

    ramp to sufficiency  ->  FLAT (parity)  ->  bounded crowding discount

The flat region IS the parity: above the headroom requirement, size stops being a tiebreaker and
the edge is judged on Sharpe, orthogonality and persistence like everything else.

THE TILT, AND WHY IT IS BOUNDED. Above fund-scale the discount is a PRIOR ON CROWDING, not a
preference for being small: an edge that absorbs eight figures is one a fund can also trade, so it
has been arbitraged by better-resourced desks and its persistence prior is genuinely worse. That
is the same reasoning as the ``crowded_known`` prior in alpha_economics. It is clamped at
``_CROWD_FLOOR`` and never reaches zero, because an unbounded tilt would simply be the original
bug mirrored -- excluding large edges by score instead of small ones. A great big edge still wins;
it just no longer wins ON SIZE.
"""

from __future__ import annotations

import math
from pathlib import Path

__all__ = ["DEFAULT_BOOK_USD", "DEFAULT_SLEEVES", "capacity_band", "capacity_fit",
           "capacity_required", "niche_share", "sleeve_equity"]

#: CAPACITY IS A RATIO, NOT A DOLLAR FIGURE (2026-07-26). The gate was a flat $100,000 floor, which
#: hard-rejected every edge too small to absorb six figures -- i.e. exactly the capacity-bound
#: niche `docs/research/PROSPECTOR_SPEC.md` calls "this desk's ONE structural advantage" (the edges
#: a fund abandoned for being too small). A perfect $20k-capacity listing dislocation failed the
#: gate on capacity alone, whatever its DSR. The gate's real job is to stop the desk being a large
#: share of its OWN edge's capacity -- a ratio to deployed equity, which protects a $5k book and a
#: $5M book alike. Both bounds live in the ThresholdBook: bounded and evidence-adjustable, never
#: hand-edited.
_CAPACITY_FALLBACK_MULT = 4.0        # need 4x headroom over what is actually deployed
_CAPACITY_FALLBACK_FLOOR = 2_000.0   # below this it is a rounding error at any book size
#: ABSOLUTE capacity above which institutional competition is assumed. Deliberately NOT a multiple
#: of our own requirement: whether an edge is crowded is a fact about the market, not about how
#: much money we happen to have. Keying it to our book would say a $5m edge is "crowded" at $50k
#: and "uncrowded" at $5m, which is backwards -- the same edge, the same competitors.
_CROWD_START_USD = 10_000_000.0
#: Floor on the crowding discount. A fund-scale edge is discounted, never excluded.
_CROWD_FLOOR = 0.75
#: Book size assumed when the caller does not say. NOT a fund's number -- see §39.
DEFAULT_BOOK_USD = 50_000.0
#: NO SINGLE EDGE GETS THE WHOLE BOOK. Judging every candidate against the full $50k silently
#: assumes an all-in one-strategy desk -- the opposite of how this one runs -- and inflates the
#: requirement by the sleeve count, pushing genuinely tradeable small edges back into "unfillable".
#: That is the flat-$100k-floor bug in miniature, so the divisor is explicit rather than implied.
DEFAULT_SLEEVES = 8

_STORE = Path(__file__).resolve().parents[2] / "data/adaptive_thresholds.json"


def _tunable(name: str, fallback: float) -> float:
    """Bounded, evidence-adjustable value -- falls back to the constant if anything is wrong.

    Deliberately lazy and exception-guarded: this module must stay importable from anywhere in the
    dependency graph, so a broken or missing store degrades to the documented default instead of
    taking the capacity policy (and therefore every gate that reads it) down with it.
    """
    try:
        from libs.self_improvement.adaptive_thresholds import ThresholdBook
        return ThresholdBook(_STORE).get(name)
    except Exception:
        return fallback


def sleeve_equity(book_usd: float, n_sleeves: int = 1) -> float:
    """Equity a SINGLE edge is actually filled with -- the book split across concurrent sleeves."""
    return max(0.0, float(book_usd)) / max(1, int(n_sleeves))


def capacity_required(deployed_equity_usd: float, n_sleeves: int = 1) -> float:
    """Minimum absorbable capacity for a candidate, given what the desk actually deploys.

    ``n_sleeves`` defaults to 1, which reads ``deployed_equity_usd`` as the equity going into THIS
    one edge -- correct for the per-candidate gates, which already know their own allocation. Pass
    the sleeve count when handing it a whole-book figure instead.
    """
    equity = sleeve_equity(deployed_equity_usd, n_sleeves)
    mult = _tunable("capacity_headroom_mult", _CAPACITY_FALLBACK_MULT)
    floor = _tunable("capacity_abs_floor_usd", _CAPACITY_FALLBACK_FLOOR)
    return max(floor, mult * equity)


def capacity_fit(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                 n_sleeves: int = 1) -> float:
    """Score capacity in [0, 1] by SUFFICIENCY for this book -- flat above the requirement.

    Below the §39 headroom requirement the score ramps linearly: an edge you would be half of is
    worth roughly half as much as one you would be a comfortable slice of. At the requirement it
    reaches 1.0 and STAYS there -- that flat region is the parity the niche was missing. Far above
    it a bounded crowding discount applies, floored so that large edges are ranked lower on size
    alone but never scored out.
    """
    cap = max(0.0, float(capacity_usd))
    required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required <= 0.0:
        return 1.0
    ratio = cap / required
    if ratio < 1.0:
        return round(max(0.0, ratio), 6)
    crowd_start = max(1.0, _tunable("capacity_crowd_start_usd", _CROWD_START_USD))
    floor = min(1.0, max(0.0, _tunable("capacity_crowd_floor", _CROWD_FLOOR)))
    if cap <= crowd_start:
        return 1.0
    # Log-scaled so the discount deepens slowly with each order of magnitude past fund-scale,
    # rather than falling off a cliff at an arbitrary dollar line.
    decades = math.log10(cap / crowd_start)
    return round(max(floor, 1.0 - (1.0 - floor) * min(1.0, decades / 2.0)), 6)


def capacity_band(capacity_usd: float, deployed_equity_usd: float = DEFAULT_BOOK_USD,
                  n_sleeves: int = 1) -> str:
    """Human-readable bucket, for audit output and dossiers rather than for arithmetic."""
    cap = max(0.0, float(capacity_usd))
    required = capacity_required(max(0.0, float(deployed_equity_usd)), n_sleeves)
    if required > 0 and cap < required:
        return "UNFILLABLE"          # you would be too large a share of your own edge
    if cap <= _CROWD_START_USD:
        return "NICHE"               # the desk's structural advantage: too small to interest funds
    if cap <= 10.0 * _CROWD_START_USD:
        return "SCALABLE"
    return "FUND-SCALE"              # a fund can trade this too -- assume it already does


def niche_share(capacities: list[float], deployed_equity_usd: float = DEFAULT_BOOK_USD,
                n_sleeves: int = DEFAULT_SLEEVES) -> float:
    """Share of a candidate population sitting in the NICHE band -- the §39 hunt measurement.

    Defaults to the sleeve count because this one takes a whole-BOOK figure: it judges a funnel,
    not a single allocation.
    """
    caps = [c for c in capacities if c > 0]
    if not caps:
        return 0.0
    n = sum(1 for c in caps if capacity_band(c, deployed_equity_usd, n_sleeves) == "NICHE")
    return round(n / len(caps), 4)
