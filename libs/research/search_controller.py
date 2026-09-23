"""Two populations, six actions, and a rule that AI never picks a number.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

Three frontier ideas that this desk needs for the same measured reason, and one rule that stops
the most expensive failure mode.

  ALPHAMASTER -- SEPARATE THE POPULATIONS. One chain maximises diversity, another maximises
      quality, and neither is allowed to consume the other's budget. A single population always
      collapses: refinement produces reliable small gains, exploration produces mostly failures,
      so any shared budget drains toward refinement within a few rounds. Measured here:
      `session_range_breakout` holds 20 of 41 certificates and the book carries n_eff ~5.5. That
      is what a collapsed search looks like from the outside.

  AGONALPHA -- UCB OVER ARTIFACTS, PENDING-AWARE. Budget goes to the branch with the best
      upper confidence bound, and work already IN FLIGHT counts against a branch's allocation.
      Without pending-awareness a parallel controller launches ten agents at the same branch
      because none of them has returned yet -- ten trials spent answering one question.

  FACTORENGINE -- AI CHOOSES LOGIC, AN OPTIMISER CHOOSES NUMBERS. The model may say "this effect
      is short-lived"; it may not say `window = 37`. `propose_parameter_grid` turns a qualitative
      claim into a preregistered grid, and `plateau_check` demands the winner sit on a PLATEAU
      rather than a spike -- a parameter that only works at one value is a fitted artefact, and
      the desk cannot tell the difference from the point estimate alone.

THE SIX ACTIONS. Every iteration chooses one: EXPLORE a new region, EXPLOIT a strong one, MUTATE
one economically meaningful dimension, CROSSOVER two lineages, FALSIFY a promising idea, or
ACQUIRE data. ACQUIRE is the one most systems lack and the one this desk most needs: another
10,000 OHLC tests on ground already mined is worth less than obtaining fixing timestamps, and a
controller with no way to express that will keep mining regardless.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

#: The six research operations. FALSIFY and ACQUIRE are the two that a search optimising for
#: discoveries will never choose on its own, and both are reserved explicitly below.
ACTIONS = ("EXPLORE", "EXPLOIT", "MUTATE", "CROSSOVER", "FALSIFY", "ACQUIRE")

#: Minimum share of budget reserved for EXPLORE. A hard floor rather than a preference, for the
#: same reason the funnel allocator has one: exploitation always wins a fair contest, and a
#: search that narrows toward whatever certified last manufactures correlation.
EXPLORE_FLOOR = 0.35

#: Minimum share reserved for FALSIFY. Spending compute trying to KILL a promising idea has
#: negative expected discoveries and positive expected truth, so nothing that maximises
#: discoveries will ever fund it voluntarily. This desk certified 41 candidates and forward-tested
#: none of them successfully; a reserved falsification budget is what stops that recurring.
FALSIFY_FLOOR = 0.10

#: UCB exploration constant. sqrt(2) is the standard choice for a reward normalised to [0, 1].
UCB_C = math.sqrt(2.0)


@dataclass
class Branch:
    """A research branch under consideration -- a region, lineage, or mechanism."""

    key: str
    attempts: int = 0
    successes: int = 0
    #: Trials launched and not yet returned. Counted as attempts by `ucb` so a parallel
    #: controller cannot pile ten agents onto one unanswered question.
    pending: int = 0
    population: str = "EXPLORE"          # EXPLORE | REFINE
    saturation: float = 0.0              # 0 = fresh ground, 1 = exhausted
    last_novel_at: str = ""

    def reward(self) -> float:
        eff = self.attempts + self.pending
        return (self.successes / eff) if eff else 0.0


def ucb(branch: Branch, total_attempts: int) -> float:
    """Upper confidence bound, counting PENDING work against the branch.

    A branch with three trials in flight has effectively been chosen three times already, even
    though none has reported. Ignoring that is how a parallel search spends its whole round on
    one question -- and the more parallel the desk gets, the worse the waste.
    """
    eff = branch.attempts + branch.pending
    if eff == 0:
        return float("inf")              # never chosen: must be tried before it can be judged
    exploit = branch.reward()
    explore = UCB_C * math.sqrt(math.log(max(total_attempts, 2)) / eff)
    # Saturated ground is worth less even when it still scores: the desk has 2,097 units of
    # ground and 7.3 candidates per unit, which is what saturation without a penalty produces.
    return (exploit + explore) * (1.0 - 0.5 * min(max(branch.saturation, 0.0), 1.0))


def choose_action(branches: list[Branch], *, seed: int,
                  data_gap_value: float = 0.0) -> tuple[str, str]:
    """Pick the next research operation, honouring the reserved floors.

    `data_gap_value` is the estimated information value of acquiring a MISSING dataset, on the
    same 0-1 scale as a branch reward. When it beats the best branch, the right move is to obtain
    the data rather than to run another backtest against ground the desk has already exhausted --
    and a controller with no ACQUIRE action would simply keep mining.
    """
    rng = random.Random(seed)  # noqa: S311 -- research sampling, not crypto
    if not branches:
        return "EXPLORE", "no branches under consideration; there is nothing to exploit yet"

    total = sum(b.attempts for b in branches)
    best = max(branches, key=lambda b: ucb(b, total))
    best_score = ucb(best, total)

    # AN UNVISITED BRANCH OUTRANKS ACQUIRING DATA, and that ordering is deliberate: a branch
    # nobody has tried costs one trial to learn about, while a dataset costs money and time. The
    # consequence is that ACQUIRE cannot fire while any branch remains unvisited, which is correct
    # but easy to mistake for the action being unreachable -- it becomes available as soon as the
    # obvious cheap questions have been asked.
    if data_gap_value > 0 and best_score != float("inf") and data_gap_value > best_score:
        return "ACQUIRE", (f"a missing dataset scores {data_gap_value:.3f} against the best "
                           f"branch's {best_score:.3f} -- more tests on mined ground are worth "
                           f"less than the data the desk does not have")

    roll = rng.random()
    if roll < FALSIFY_FLOOR:
        return "FALSIFY", (f"reserved falsification budget ({FALSIFY_FLOOR:.0%}): spending "
                           f"compute trying to KILL a promising idea has negative expected "
                           f"discoveries and positive expected truth, so nothing that maximises "
                           f"discoveries funds it voluntarily")
    if roll < FALSIFY_FLOOR + EXPLORE_FLOOR:
        return "EXPLORE", (f"reserved exploration floor ({EXPLORE_FLOOR:.0%}): exploitation wins "
                           f"every fair contest, and a search that narrows toward whatever "
                           f"certified last manufactures correlation")

    if best.population == "REFINE" and best.attempts >= 3:
        return ("MUTATE", f"branch {best.key} is refinable (reward {best.reward():.3f}); change "
                          f"ONE economically meaningful dimension, not the whole candidate")
    fertile = [b for b in branches if b.reward() > 0 and b.key != best.key]
    if len(fertile) >= 2 and roll > 0.9:
        return "CROSSOVER", (f"two fertile lineages available ({fertile[0].key}, "
                             f"{fertile[1].key}); combine compatible conditions")
    return "EXPLOIT", f"branch {best.key} has the best upper confidence bound ({best_score:.3f})"


def split_budget(branches: list[Branch], budget: int, *, seed: int) -> dict[str, int]:
    """Allocate trials across the two populations, then within each.

    THE POPULATIONS DO NOT COMPETE. Each gets a fixed share and allocates internally. Letting
    them bid against each other guarantees REFINE wins -- its rewards are reliable and immediate,
    while EXPLORE's are rare and delayed -- and that is the collapse this whole module prevents.
    """
    rng = random.Random(seed)  # noqa: S311 -- research sampling, not crypto
    explore = [b for b in branches if b.population == "EXPLORE"]
    refine = [b for b in branches if b.population == "REFINE"]
    out: dict[str, int] = {}

    explore_budget = int(budget * EXPLORE_FLOOR)
    refine_budget = budget - explore_budget
    for pool, pool_budget in ((explore, explore_budget), (refine, refine_budget)):
        if not pool:
            continue
        total = sum(b.attempts for b in pool)
        scores = []
        for b in pool:
            u = ucb(b, total)
            # An unvisited branch has infinite UCB, which cannot be normalised; give it the
            # highest finite weight so it is tried without swallowing the entire pool.
            scores.append((b.key, 10.0 if u == float("inf") else max(u, 1e-6)))
        s = sum(v for _, v in scores)
        for key, v in scores:
            out[key] = out.get(key, 0) + int(pool_budget * v / s)
    # Round-off goes to ONE randomly chosen EXPLORE branch rather than the largest, which would
    # quietly re-concentrate the very budget this function exists to spread.
    #
    # `rng.choice` is called ONCE and bound. A first version called it twice -- reading one
    # branch's current value and writing the sum to a DIFFERENT branch -- which handed out 1,297
    # trials from a budget of 1,000. A budget function that over-allocates is worse than one that
    # under-allocates: the excess is silently spent on whichever branch won the second coin flip.
    spent = sum(out.values())
    if spent < budget and explore:
        lucky = rng.choice(explore).key
        out[lucky] = out.get(lucky, 0) + (budget - spent)
    assert sum(out.values()) <= budget, (
        f"allocated {sum(out.values())} of a {budget} budget -- a controller that hands out more "
        f"than it has is spending trials nobody authorised")
    return out


#: Qualitative claim -> a preregistered grid. The AI supplies the LEFT side only.
_HORIZON_GRIDS: dict[str, tuple[int, ...]] = {
    "very_short_lived": (1, 2, 3, 5, 8),
    "short_lived": (5, 10, 15, 20, 30),
    "medium": (20, 30, 45, 60, 90),
    "persistent": (60, 90, 120, 180, 250),
}


def propose_parameter_grid(qualitative: str) -> tuple[tuple[int, ...], str]:
    """Turn 'this effect is short-lived' into a grid. The model never names a number.

    An unrecognised description returns an EMPTY grid rather than a default. Silently substituting
    a plausible range would let a vague claim reach a backtest wearing a precision it never had.
    """
    grid = _HORIZON_GRIDS.get(qualitative)
    if not grid:
        return (), (f"{qualitative!r} is not a recognised horizon claim. Say one of "
                    f"{sorted(_HORIZON_GRIDS)}; an unrecognised description gets no grid rather "
                    f"than a plausible-looking default.")
    return grid, (f"preregistered grid for a {qualitative} effect; the optimiser searches these "
                  f"and the validator decides truth")


def plateau_check(results: dict[int, float], *, min_neighbours: int = 2) -> tuple[bool, str]:
    """Does the best parameter sit on a PLATEAU, or is it a spike?

    A spike is the signature of a fitted parameter: it works at 37 and fails at 30 and 45, which
    means the 37 was chosen by the data rather than by the mechanism. Requiring neighbours to hold
    up is the cheapest overfitting test available and it costs nothing beyond the sweep already
    run.
    """
    if len(results) < 3:
        return False, (f"only {len(results)} parameter value(s) tested -- a plateau cannot be "
                       f"established, and a single value is a point estimate, not evidence of "
                       f"stability")
    ordered = sorted(results)
    best = max(results, key=lambda k: results[k])
    i = ordered.index(best)
    peak = results[best]
    if peak <= 0:
        return False, f"best value {best} scores {peak:.4f}; nothing to stand on"

    neighbours = [results[ordered[j]] for j in (i - 1, i + 1) if 0 <= j < len(ordered)]
    if len(neighbours) < min_neighbours:
        return False, (f"best value {best} sits at the EDGE of the tested grid, so its "
                       f"neighbourhood is unmeasured on one side -- extend the grid rather than "
                       f"assuming the peak is interior")
    holding = [v for v in neighbours if v >= 0.5 * peak]
    if len(holding) < min_neighbours:
        return False, (f"best value {best} scores {peak:.4f} while its neighbours score "
                       f"{[round(v, 4) for v in neighbours]} -- a SPIKE, not a plateau. A "
                       f"parameter that works at one value and fails on either side was chosen "
                       f"by the data, not by the mechanism.")
    return True, (f"best value {best} ({peak:.4f}) sits on a plateau; neighbours "
                  f"{[round(v, 4) for v in neighbours]} hold above half the peak")
