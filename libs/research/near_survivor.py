"""THE NEAR-SURVIVOR BANK -- and the trial-accounting that stops it manufacturing survivors.

THE IDEA, WHICH IS A GOOD ONE (principal 2026-08-07). A candidate that dies is not worthless: HOW
it died names the next experiment. Strong signal killed by cost -> look for a slower version.
Works only in high volatility -> look for the volatility-conditioned version. Works on BTC and not
ETH -> the mechanism is asset-specific, or it is liquidity. Each failure mode is a lead, and a desk
that discards its near-misses throws away the most informative output of every experiment it runs.

**AND IT IS THE MOST EFFICIENT SURVIVOR-MANUFACTURING DEVICE THIS DESK COULD BUILD, IF THE TRIAL
ACCOUNTING IS WRONG.** Consider what a descendant actually is: a new test, on THE SAME DATA, chosen
BECAUSE the desk already saw the parent's result. That is the textbook definition of adaptive
selection -- L1.52's hard edge, in the one place where it feels most like diligence. Test 400
candidates, take the best near-miss, spawn 20 slower variants of it, and one will clear an
undeflated bar by construction. Nothing about that process is dishonest at any single step, which
is exactly why it needs to be counted rather than trusted.

SO THE RULE, AND IT IS THE WHOLE MODULE: **a descendant inherits its ancestry's ENTIRE trial
count.** Not the parent's alone -- the count of everything the desk searched to arrive at the
parent, plus every sibling spawned since. `family_trials()` computes it and `hurdle()` deflates on
it, so the twentieth variant of a near-miss faces a materially harder bar than the first
independent hypothesis did. That is not a penalty for diligence; it is the price of having looked.

WHAT A DESCENDANT MAY NOT DO. It may not be reported as an independent survivor, it may not enter
the independence count as a separate mechanism (it is by construction the same mechanism -- that is
why it was spawned), and it may not be used to argue the parent was right after all. A near-miss
that produces a clean descendant is ONE finding about ONE mechanism, however many formulas the
neighbourhood search emitted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "FAILURE_PLAYBOOK",
    "Descendant",
    "NearSurvivor",
    "family_trials",
    "hurdle",
    "next_experiments",
]

#: FAILURE MODE -> the specific experiments it licenses. The value of a near-miss is that it names
#: a DIRECTION, and a direction is far cheaper to search than the open space. Each entry is a
#: hypothesis to enumerate, never a fix to apply.
FAILURE_PLAYBOOK: dict[str, tuple[str, ...]] = {
    "cost": (
        "slower version: same signal, longer holding period, so the same edge pays the round trip "
        "fewer times",
        "maker-only execution: the cost that killed it is a taker cost; a resting-quote version "
        "pays a different one, and may pay none",
        "conditional trading: trade only the top decile of signal strength, so turnover falls "
        "faster than edge does",
        "LIQUIDITY CHECK FIRST -- WS-006 measured net-positive cells concentrating at spreads 48x "
        "tighter than the book. If the edge only survives in the tightest names, this is a "
        "liquidity finding wearing a signal's clothes, and no slower version will rescue it",
    ),
    "regime": (
        "explicitly regime-conditioned version, with the regime defined from TRAILING data only",
        "test whether the regime itself is the signal: a rule that trades only in high volatility "
        "may be a volatility-timing strategy the desk could hold directly",
        "check sample balance -- 'works in high vol' on 40 high-vol bars is a sample-size result",
    ),
    "asset": (
        "isolate the mechanism: what does the working asset have that the failing one lacks? "
        "Liquidity, listing age, holder base, funding regime, index membership",
        "cross-sectional version ranking across the universe rather than picking one symbol",
        "the honest null: one asset out of N clearing a bar is what N trials produce",
    ),
    "timing": (
        "event-window version anchored on the timestamp that mattered (funding settlement, "
        "expiry, listing, unlock)",
        "test whether the effect is the EVENT rather than the signal -- the calendar is a "
        "confound this desk has already named (libs/research/event_calendar.py)",
    ),
    "correlation": (
        "orthogonalise against the existing survivor and test the RESIDUAL -- if the residual "
        "carries nothing, this was the incumbent all along",
        "look for the complement: what does the incumbent fail at that this handles?",
    ),
    "decay": (
        "date the death: does the edge end at a venue change, a fee change, a listing, or a "
        "competitor's arrival? A dated death is a mechanism; an undated one is noise",
        "test the inverse -- an arbitraged edge often flips sign as the crowd front-runs it",
        "check whether a related feature replaced the original one",
    ),
    "sample": (
        "NOT A NEAR-MISS AT ALL. Too few observations is UNMEASURED, not a weak result (L1.28a), "
        "and spawning descendants from an unmeasured parent searches a neighbourhood chosen by "
        "noise. Acquire data or drop it.",
    ),
}


@dataclass(frozen=True)
class NearSurvivor:
    """A candidate that failed, recorded with the information that makes the failure useful."""

    mechanism: str
    failure_mode: str
    #: Trials searched to ARRIVE at this candidate -- the parent study's whole budget, not 1.
    ancestry_trials: int = 1
    detail: str = ""
    #: Descendants already spawned from this near-miss, by any researcher or organ.
    spawned: int = 0

    @property
    def is_spawnable(self) -> bool:
        """An UNMEASURED parent licenses nothing: its neighbourhood was chosen by noise."""
        return self.failure_mode != "sample"


@dataclass(frozen=True)
class Descendant:
    """One experiment spawned from a near-miss. Carries its ancestry, not a fresh slate."""

    parent: NearSurvivor
    experiment: str
    sibling_index: int = 0
    notes: tuple[str, ...] = field(default_factory=tuple)


def next_experiments(ns: NearSurvivor) -> list[Descendant]:
    """The experiments this failure mode licenses.

    RETURNS NOTHING FOR AN UNMEASURED PARENT, rather than a generic list. The playbook's `sample`
    entry exists to say so explicitly: a thin-sample failure is an inability to measure, and
    searching the neighbourhood of a number that was never measured is searching noise with extra
    steps.
    """
    plays = FAILURE_PLAYBOOK.get(ns.failure_mode, ())
    if not ns.is_spawnable:
        return []
    return [Descendant(ns, p, i) for i, p in enumerate(plays)]


def family_trials(ns: NearSurvivor, *, new: int = 1) -> int:
    """The trial count a descendant must be deflated on.

    ANCESTRY + SIBLINGS + THIS ONE. A descendant is a test on the SAME DATA, selected BECAUSE the
    desk saw the parent's result, so the search that produced the parent is part of this test's
    search. Deflating a descendant on `new` alone is the single most flattering accounting
    available to a research programme, and it is available precisely when the desk feels most
    diligent -- "we investigated the near-miss carefully" and "we spent 400 trials finding a
    candidate and then 20 more polishing it" describe the same afternoon.
    """
    return max(1, ns.ancestry_trials) + max(0, ns.spawned) + max(0, new)


def hurdle(ns: NearSurvivor, *, new: int = 1) -> float:
    """sqrt(2 ln N) at the FAMILY trial count.

    The twentieth variant of a near-miss faces a harder bar than the first independent hypothesis,
    and that is correct rather than unfair: by the twentieth, the desk has looked twenty times more.
    """
    return math.sqrt(2.0 * math.log(family_trials(ns, new=new)))


def report(ns: NearSurvivor, *, new: int = 1) -> str:
    """One block a human or an organ reads before spending the next experiment."""
    if not ns.is_spawnable:
        return (f"{ns.mechanism}: UNMEASURED ({ns.failure_mode}) -- spawns NOTHING. "
                f"{FAILURE_PLAYBOOK['sample'][0]}")
    plays = next_experiments(ns)
    n = family_trials(ns, new=new)
    return "\n".join([
        f"{ns.mechanism}: near-miss on {ns.failure_mode.upper()}. {ns.detail}".rstrip(),
        f"  family trial count {n} (ancestry {ns.ancestry_trials} + spawned {ns.spawned} + "
        f"{new}) -> hurdle |t| >= {hurdle(ns, new=new):.3f}",
        "  a descendant is NOT an independent survivor and NOT a separate mechanism: it was "
        "spawned because it is the same mechanism.",
        *(f"  [{d.sibling_index}] {d.experiment}" for d in plays),
    ])
