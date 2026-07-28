"""THE universe definition -- one number, one place.

`list_liquid_perps(top_n=...)` was called at 30, 70, 80, 100, 120 across the codebase (12 call
sites at 120, a source default of 100, and singletons at everything else). Nothing crashed,
because each screen fetches its own universe live -- which is exactly what made the drift
invisible.

WHY IT IS A DEFECT ANYWAY. Cross-sectional results computed over different breadths are NOT
COMPARABLE: a rank signal's IC over the top 30 names and over the top 120 are different
experiments on different populations, and the desk pools them as if they were one. Worse, the
multiplicity accounting in the Two-Stage Discovery Law counts trials, not populations, so two
screens at different breadths look like two trials of the same test when they are not. And no
one could answer "what is the desk's universe?" with a single number.

RESEARCH vs TRADEABLE is a real distinction and is preserved here rather than flattened:

    RESEARCH_TOP_N   wide -- cross-sectional power comes from breadth; ingestion is cheap
    TRADEABLE_TOP_N  narrow -- realistic fills, capacity and cost live at the liquid end

A screen picks the one matching its claim and says which. Anything else is a deliberate,
argued exception -- not a default that drifted.
"""

from __future__ import annotations

# Cross-sectional research breadth. 120 is the de-facto standard already: 12 of the screens use
# it, so this ratifies observed practice rather than imposing a new number that would silently
# change existing results.
RESEARCH_TOP_N = 120

# Tradeable breadth. Deliberately narrower: capacity, slippage and MIN_NOTIONAL bite well before
# rank 120, and a "validated" edge that only exists in illiquid names is a measurement artifact.
TRADEABLE_TOP_N = 40

# Microstructure recording breadth -- bounded by the recorder's request budget, not by research
# appetite. Kept here so the moat's breadth is visible alongside the others instead of buried.
RECORDED_TOP_N = 20

__all__ = ["RECORDED_TOP_N", "RESEARCH_TOP_N", "TRADEABLE_TOP_N", "describe"]


def describe() -> str:
    return (f"research={RESEARCH_TOP_N} tradeable={TRADEABLE_TOP_N} "
            f"recorded={RECORDED_TOP_N} (libs/data/universe.py is the single source)")
