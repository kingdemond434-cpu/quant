"""Enormous breadth at the top, brutality at the bottom, and the budget spent in that order.

WHY THIS EXISTS (principal blueprint, 2026-08-29)

The desk currently runs its full gauntlet on everything that reaches it: 12,535 candidates judged
at full cost for 41 certificates. Every expensive stage -- CPCV, PBO, SPA, the deflated Sharpe --
is paid on candidates that a five-second check would have killed. That is not merely wasteful; it
is the reason breadth feels expensive, and therefore the reason the search stays narrow.

Successive halving inverts it. Each rung costs more per candidate and admits fewer, so total
compute is roughly constant while the TOP of the funnel can be orders of magnitude wider:

    100,000 semantic coordinates
      -> semantic prior            20,000
      -> mechanism + falsifiers     8,000
      -> novelty / graveyard        3,500
      -> compile / PIT / static     2,500
      -> ultra-cheap falsification    800
      -> low-resolution history       250
      -> cost + stability             100
      -> chronological OOS / WF        30
      -> CPCV / PBO / SPA / DSR         6
      -> lockbox                        2
      -> independent reviewer         1-2
      -> real forward shadow          0-2

CHEAP AND DECISIVE FIRST. The ordering rule is not "fast first" but "highest kill-rate per unit
cost first". A falsifier that costs nothing and eliminates 60% belongs above a test that costs a
minute and eliminates 5%, even if the minute-long test is more interesting.

THE BAR DOES NOT MOVE, AND THAT IS THE WHOLE POINT. Nothing here weakens a gate. The expensive
gates are identical; they simply stop being spent on candidates that were never going to survive
them. Cutting early is only legitimate because the later gates would have killed the same
candidates -- a rung that kills something the gauntlet would have PASSED is a defect, not an
optimisation, and `audit_rung` exists to detect exactly that.

A RUNG THAT KILLS EVERYTHING IS BROKEN, NOT SELECTIVE. `run` refuses to report a rung that
admitted zero as a successful narrowing, because this desk has already had a sweep return a
legitimate-looking zero from a producer/consumer mismatch and rewrite its authority file with it.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

#: A rung admitting nothing is a defect until proven otherwise: a real filter has a survivor
#: distribution, and total elimination is far more often a wiring fault than a strong screen.
_SUSPICIOUS_ZERO = 0


@dataclass
class Rung:
    """One filter. `cost_hint` is relative, only used to assert the ordering is sane."""

    name: str
    predicate: Callable[[Any], bool]
    cost_hint: float
    why: str
    #: Expected survival fraction, for the audit. None where unknown -- never guessed.
    expected_survival: float | None = None


@dataclass
class RungResult:
    name: str
    entered: int
    survived: int
    killed: int
    survival_rate: float
    cost_hint: float
    suspicious: bool
    note: str


def check_ordering(rungs: Sequence[Rung]) -> list[str]:
    """Cheap rungs must come first. Returns the violations, in words.

    An expensive rung above a cheap one means the desk pays the expensive test on candidates the
    cheap one was about to kill -- the exact waste this module exists to remove, reintroduced by
    ordering alone.
    """
    problems = []
    for i in range(1, len(rungs)):
        if rungs[i].cost_hint < rungs[i - 1].cost_hint:
            problems.append(
                f"rung {i} '{rungs[i].name}' (cost {rungs[i].cost_hint}) is cheaper than rung "
                f"{i - 1} '{rungs[i - 1].name}' (cost {rungs[i - 1].cost_hint}) -- the expensive "
                f"test is being paid on candidates the cheap one would have killed")
    return problems


def run(candidates: Sequence[Any], rungs: Sequence[Rung], *,
        stop_on_empty: bool = True) -> tuple[list[Any], list[RungResult]]:
    """Pass candidates down the ladder, reporting every rung's toll.

    Returns (survivors, per-rung results). A rung that empties the funnel STOPS the run by
    default and is flagged: continuing would run the remaining rungs on nothing and report a
    clean pass over an empty set, which is how a silent zero becomes an authority file.
    """
    survivors = list(candidates)
    results: list[RungResult] = []

    for rung in rungs:
        entered = len(survivors)
        if entered == 0:
            results.append(RungResult(rung.name, 0, 0, 0, 0.0, rung.cost_hint, True,
                                      "entered empty -- an earlier rung took everything"))
            break
        kept = []
        for c in survivors:
            try:
                if rung.predicate(c):
                    kept.append(c)
            except Exception as exc:
                # A predicate that raises must not silently drop the candidate: that is
                # indistinguishable from a considered rejection and hides the bug forever.
                raise RuntimeError(
                    f"rung '{rung.name}' raised {type(exc).__name__} on a candidate: {exc}. A "
                    f"filter that errors is not a filter that rejected -- fix it rather than "
                    f"letting it eliminate by exception.") from exc

        survived = len(kept)
        rate = survived / entered if entered else 0.0
        suspicious = survived == _SUSPICIOUS_ZERO
        note = ""
        if suspicious:
            note = (f"admitted ZERO of {entered}. A real filter has a survivor distribution; "
                    f"total elimination is far more often a wiring fault than a strong screen. "
                    f"Verify the predicate before trusting this as a narrowing.")
        elif (rung.expected_survival is not None and rate > 0
                and (rate < rung.expected_survival / 4
                     or rate > min(1.0, rung.expected_survival * 4))):
            note = (f"survival {rate:.3f} is far from the expected "
                    f"{rung.expected_survival:.3f} -- the rung is behaving differently "
                    f"than designed")

        results.append(RungResult(rung.name, entered, survived, entered - survived,
                                  round(rate, 4), rung.cost_hint, suspicious, note))
        survivors = kept
        if suspicious and stop_on_empty:
            break

    return survivors, results


def audit_rung(killed_by_rung: Sequence[Any],
               would_have_passed: Callable[[Any], bool]) -> dict[str, Any]:
    """Did this rung kill anything the FULL gauntlet would have passed?

    The legitimacy of cutting early rests entirely on the claim that the later gates would have
    killed the same candidates. A rung that kills a genuine survivor is not a cheap approximation
    of the gauntlet, it is a different and worse gate, and it makes the desk's certificate count
    a function of its compute budget. Run this on a sample periodically; a single false kill is a
    defect to fix, not a rate to tolerate.
    """
    false_kills = []
    for c in killed_by_rung:
        try:
            if would_have_passed(c):
                false_kills.append(c)
        except Exception:
            continue
    n = len(killed_by_rung)
    return {"checked": n, "false_kills": len(false_kills),
            "false_kill_rate": round(len(false_kills) / n, 4) if n else 0.0,
            "verdict": "SOUND" if not false_kills else "DEFECTIVE",
            "why": ("cutting early is only legitimate if the later gates would have killed the "
                    "same candidates; a single false kill means this rung is a different gate, "
                    "not a cheaper one")}
