"""THE NEAR-SURVIVOR BANK -- the tests are about trial accounting, because that is what makes it
safe rather than dangerous.

Mining a failure for its next experiment is a genuinely good idea. It is also, if counted wrongly,
the most efficient survivor-manufacturing device this desk could build: a descendant is a new test,
on the SAME data, chosen BECAUSE the desk saw the parent's result. Test 400, take the best
near-miss, spawn 20 slower variants, and one clears an undeflated bar by construction -- with no
single step that looks dishonest, which is exactly why it must be counted rather than trusted.
"""

from __future__ import annotations

import math

from libs.research.near_survivor import (
    FAILURE_PLAYBOOK,
    NearSurvivor,
    family_trials,
    hurdle,
    next_experiments,
    report,
)


def _ns(mode: str = "cost", ancestry: int = 400, spawned: int = 0) -> NearSurvivor:
    return NearSurvivor("M_FUNDING", mode, ancestry_trials=ancestry, spawned=spawned)


# ------------------------------------------------------------------ trial accounting


def test_A_DESCENDANT_INHERITS_THE_WHOLE_ANCESTRY_NOT_A_FRESH_SLATE() -> None:
    """The single most flattering accounting available to a research programme, and it is available
    precisely when the desk feels most diligent: 'we investigated the near-miss carefully' and 'we
    spent 400 trials finding a candidate and then polished it' describe the same afternoon."""
    assert family_trials(_ns(ancestry=400), new=1) == 401
    assert family_trials(_ns(ancestry=400, spawned=19), new=1) == 420


def test_THE_HURDLE_RISES_WITH_EVERY_SIBLING_ALREADY_SPAWNED() -> None:
    """By the twentieth variant the desk has looked twenty times more, so the twentieth faces a
    harder bar than the first. That is correct rather than unfair."""
    first = hurdle(_ns(ancestry=400, spawned=0))
    twentieth = hurdle(_ns(ancestry=400, spawned=19))
    assert twentieth > first
    assert first == math.sqrt(2 * math.log(401))


def test_DEFLATING_ON_THE_NEW_TRIAL_ALONE_WOULD_BE_A_MUCH_WEAKER_BAR() -> None:
    """The error this module exists to prevent, stated as a number so the size of it is visible."""
    honest = hurdle(_ns(ancestry=400, spawned=19))
    naive = math.sqrt(2 * math.log(1 + 1))
    assert honest > naive * 1.5, (
        f"family deflation {honest:.2f} vs naive {naive:.2f} -- if these were close, the "
        "accounting would not be doing any work")


def test_THE_FAMILY_COUNT_NEVER_DROPS_BELOW_ONE() -> None:
    """Defensive: a zero or negative ancestry would make log() explode or go negative, and the
    hurdle is the one number that must never come out accidentally small."""
    assert family_trials(NearSurvivor("M", "cost", ancestry_trials=0), new=0) >= 1
    assert hurdle(NearSurvivor("M", "cost", ancestry_trials=0), new=0) >= 0.0


# --------------------------------------------------------------------- the playbook


def test_EVERY_FAILURE_MODE_NAMES_CONCRETE_NEXT_EXPERIMENTS() -> None:
    """The value of a near-miss is that it names a DIRECTION, and a direction is far cheaper to
    search than the open space."""
    for mode, plays in FAILURE_PLAYBOOK.items():
        assert plays, f"{mode} licenses nothing"
        assert all(len(p) > 20 for p in plays), f"{mode} has a play too vague to act on"


def test_A_COST_FAILURE_SENDS_THE_DESK_TO_LIQUIDITY_BEFORE_A_SLOWER_VERSION() -> None:
    """WS-006 measured net-positive cells concentrating at spreads 48x tighter than the book. If an
    edge only survives in the tightest names, no slower version rescues it -- it was never a signal
    finding. Chasing the slower version first spends a cycle on the wrong hypothesis."""
    plays = [d.experiment for d in next_experiments(_ns("cost"))]
    assert any("WS-006" in p and "48x" in p for p in plays)
    assert any("slower version" in p for p in plays)


def test_AN_UNMEASURED_PARENT_SPAWNS_NOTHING() -> None:
    """A thin-sample failure is an inability to measure (L1.28a), not a weak result. Searching the
    neighbourhood of a number that was never measured is searching noise with extra steps."""
    thin = _ns("sample")
    assert not thin.is_spawnable
    assert next_experiments(thin) == []
    assert "spawns NOTHING" in report(thin)


def test_AN_UNKNOWN_FAILURE_MODE_LICENSES_NOTHING_RATHER_THAN_GUESSING() -> None:
    assert next_experiments(_ns("something_nobody_classified")) == []


def test_THE_REGIME_PLAY_INCLUDES_ITS_OWN_NULL() -> None:
    """'Works in high vol' on 40 high-vol bars is a sample-size result, and the regime arm is where
    that is easiest to miss because conditioning always shrinks the sample."""
    plays = [d.experiment for d in next_experiments(_ns("regime"))]
    assert any("sample-size result" in p for p in plays)


def test_THE_ASSET_PLAY_CARRIES_THE_HONEST_NULL() -> None:
    """One asset out of N clearing a bar is exactly what N trials produce, and 'it works on BTC' is
    the most seductive form of that."""
    plays = [d.experiment for d in next_experiments(_ns("asset"))]
    assert any("what N trials produce" in p for p in plays)


# ------------------------------------------------------------------------- reporting


def test_THE_REPORT_STATES_THAT_A_DESCENDANT_IS_NOT_A_NEW_MECHANISM() -> None:
    """A descendant was spawned BECAUSE it is the same mechanism. Counting it as an independent
    survivor would inflate the one number L1.52(a) says may be called a discovery."""
    text = report(_ns("correlation", ancestry=120, spawned=3))
    assert "NOT an independent survivor" in text and "NOT a separate mechanism" in text
    assert "family trial count 124" in text
    assert "hurdle |t| >=" in text


def test_THE_REPORT_SHOWS_ITS_ARITHMETIC() -> None:
    """A hurdle nobody can re-derive is a number to be argued with rather than checked."""
    text = report(_ns("decay", ancestry=50, spawned=2), new=1)
    assert "ancestry 50 + spawned 2 + 1" in text
