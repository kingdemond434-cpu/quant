"""L1.49 WEAK IS NOT DEAD -- the law that a candidate failing standalone significance is not
thereby refuted, and that its evidence must survive the verdict.

WHY THIS SUITE EXISTS AS A CHANGE-DETECTOR RATHER THAN A UNIT TEST. The defect it guards was
invisible for the desk's entire history precisely because nothing looked: every candidate's
return series was computed, validated on in memory, and then dropped, while only scalar metrics
reached the store. Nothing failed. No alarm fired. 420+ hypotheses were tested and their
evidence destroyed, which made the principal's own stated architecture -- many weak,
uncorrelated edges combined -- unenforceable retroactively, because there was nothing left to
combine.

A law that lives only in docs/CONSTITUTION.md is a law that the next refactor deletes by
accident. These tests pin the three clauses that can regress silently:

  1. the arithmetic that makes weakness survivable and redundancy fatal;
  2. the constitutional text itself, so the clause cannot be quietly dropped;
  3. the ranking axis -- marginal contribution, not standalone strength.

The RETENTION clause (persisting rejected candidates' series) is enforced separately in the
autodiscovery suite, next to the store that must do the persisting.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.research.cohort_independence import effective_bets

_ROOT = Path(__file__).resolve().parents[2]
_CONSTITUTION = _ROOT / "docs" / "CONSTITUTION.md"


class TestTheArithmeticThatMakesWeaknessSurvivable:
    """s*sqrt(N_eff) is the whole argument. If this arithmetic is wrong the law is wrong."""

    def test_weak_components_reach_a_strong_portfolio_when_independent(self) -> None:
        """The capability the desk was missing: Sharpe-0.2 parts, Sharpe-2.0 whole."""
        n_eff = effective_bets(100, 0.0)
        assert 0.2 * n_eff**0.5 == pytest.approx(2.0, abs=1e-9)

    def test_redundancy_not_weakness_is_the_disqualifier(self) -> None:
        """Same 100 components, correlated: the stack collapses. This is why the law forbids
        ranking weak candidates by standalone strength -- strength is not the axis."""
        independent = effective_bets(100, 0.0)
        redundant = effective_bets(100, 0.348)
        assert redundant < independent / 30, (
            "at the desk's measured rho the same 100 components must NOT stack")

    def test_correlation_caps_the_stack_absolutely(self) -> None:
        """N_eff -> 1/rho as N -> inf: adding candidates to a correlated pile is bookkeeping,
        not diversification. Pinned because it is the number that decides whether the whole
        weak-edge architecture is viable on this desk at all."""
        rho = 0.348
        ceiling = 1.0 / rho
        assert effective_bets(1_000_000, rho) == pytest.approx(ceiling, rel=1e-3)
        for n in (10, 100, 1000, 100_000):
            assert effective_bets(n, rho) <= ceiling + 1e-9
        assert ceiling**0.5 == pytest.approx(1.696, abs=0.01)  # the 1.70x multiple, no more

    def test_the_orthogonality_a_weak_stack_requires(self) -> None:
        """Portfolio Sharpe 2.0 from Sharpe-0.2 components needs rho <= 0.01. This is the
        Medallion condition, and it is a statement about SIMILARITY, not about strength."""
        need_n_eff = (2.0 / 0.2) ** 2
        assert need_n_eff == pytest.approx(100.0)
        assert effective_bets(100, 0.01) >= 0.5 * need_n_eff, (
            "at rho=0.01 a hundred weak edges must still buy most of the sqrt(N) benefit")
        assert effective_bets(100, 0.10) < 0.15 * need_n_eff, (
            "at rho=0.10 that same hundred must NOT -- the bar is orthogonality, not count")


class TestMarginalContributionIsTheRankingAxis:
    """Clause 2: a weak-but-orthogonal candidate outranks a strong-but-redundant one. A ranking
    that inverts this is in breach, and inverting it is the natural thing to do by accident,
    because standalone Sharpe is the number that is always to hand."""

    def _portfolio_sharpe(self, sharpes: list[float], rho: float) -> float:
        n = len(sharpes)
        if n == 0:
            return 0.0
        mean_s = float(np.mean(sharpes))
        return mean_s * effective_bets(n, rho) ** 0.5

    def test_weak_and_orthogonal_beats_strong_and_redundant(self) -> None:
        base = [0.4, 0.4, 0.4]
        # candidate A: weaker standalone, uncorrelated with the book
        with_weak_orthogonal = self._portfolio_sharpe([*base, 0.2], rho=0.02)
        # candidate B: stronger standalone, but the same trade the book already holds
        with_strong_redundant = self._portfolio_sharpe([*base, 0.8], rho=0.60)
        assert with_weak_orthogonal > with_strong_redundant, (
            "L1.49: marginal contribution, not standalone Sharpe -- the weak orthogonal "
            "candidate must win, which is exactly the ranking the old gate inverted")


class TestTheLawItselfCannotBeQuietlyDropped:
    """A constitutional clause that no test reads is a clause the next edit deletes for free."""

    def test_l1_49_is_present_and_names_its_load_bearing_duties(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "L1.49" in src and "WEAK IS NOT DEAD" in src
        # the three duties, matched on their load-bearing phrases rather than exact prose
        assert "Its evidence is retained" in src, "the retention duty was dropped"
        assert "MARGINAL CONTRIBUTION" in src, "the ranking-axis duty was dropped"
        assert "FAILED-ON-MERIT" in src and "UNDERPOWERED" in src, (
            "the three-state rejection distinction was dropped -- collapsing them is what "
            "made this flaw invisible")

    def test_the_anti_loophole_clause_survives(self) -> None:
        """The clause most likely to be softened, because softening it is convenient: this law
        must never become a route to admit noise individually to capital."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "NOT A ROUTE TO ADMIT NOISE" in src
        assert "pre-registered" in src, "the pre-registration requirement was dropped"
        assert "Nothing here\nlowers a bar" in src or "lowers a bar" in src


class TestL150UnexploitedIsADefect:
    """L1.50, pinned the same way L1.49 is: a constitutional clause no test reads is a clause
    the next edit deletes for free.

    The five clauses are matched on their load-bearing phrases rather than exact prose, so a
    sharper rewrite passes while a silent removal fails -- the prompt-ratchet principle applied
    to the constitution itself.
    """

    def test_l1_50_is_present_with_all_five_clauses(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "L1.50" in src and "UNEXPLOITED ASSET IS A DEFECT" in src
        assert "UNDER-EXPLOITATION IS A DEFECT" in src, "clause 1 (utilisation) dropped"
        assert "THE QUEUE IS THE DEFECT" in src, "clause 2 (conversion) dropped"
        assert "NOTHING IS HARDCODED" in src, "clause 3 (no checklist) dropped"
        assert "NO CEILINGS" in src, "clause 4 dropped"
        assert "E[log W]" in src, "clause 5 -- the growth-objective justification -- dropped"

    def test_the_checklist_clause_keeps_its_teeth(self) -> None:
        """The clause most likely to be softened into a suggestion, because it is the one that
        makes an organ's own judgement mandatory rather than optional."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "FAILED" in src and "checklist" in src.lower()
        assert "floor" in src.lower() and "ceiling" in src.lower()

    def test_the_moat_arithmetic_that_motivates_clause_1(self) -> None:
        """An unread tape is not merely untidy: the moat accrues only in calendar time, so the
        loss is unrecoverable rather than deferred. Pinned so the motivating measurement stays
        attached to the rule it justifies."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "1,065" in src, "the measured under-utilisation was dropped from the law"
        assert "calendar time" in src


class TestL152AndL153TheStandingOrdersOf20260805:
    """The two laws the principal issued on 2026-08-05, pinned the same way L1.49 and L1.50 are:
    matched on load-bearing phrases rather than exact prose, so a sharper rewrite passes while a
    silent removal fails.

    Both encode the same underlying failure from opposite ends, which is why they are pinned
    together. A gauge that improves when the desk does LESS of the thing the gauge exists to
    encourage is not a measurement -- it is an incentive pointing the wrong way. L1.52 is that
    failure in the exploration budget (the meta-check that could not fire while the apparatus it
    judges was broken); L1.53 is it in the conversion ratio (a denominator nobody guarded).
    """

    def test_l1_52_is_present_with_its_operative_clauses(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "L1.52" in src and "UNKNOWN-UNKNOWN HUNT IS RESOURCED" in src
        assert "WHAT\nDOES THE ABSENCE OF MY INPUT LOOK LIKE?" in src or \
               "ABSENCE OF MY INPUT LOOK LIKE" in src, (
            "the general rule -- absence must not look like health -- was dropped")
        assert "PRINCIPAL-FOUND IS THE FAILURE SIGNAL" in src, (
            "the origin-accounting duty was dropped")
        assert "never throttled to fund extraction" in src, (
            "the clause protecting the hunt from repair-mode was dropped")

    def test_the_anti_inflation_clause_on_the_desks_own_metric_survives(self) -> None:
        """The clause most likely to be softened, because softening it is convenient to whoever
        is keeping the score: self-sufficiency is the one number the desk grades itself on."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "governance breach" in src and "bookkeeping preference" in src

    def test_l1_53_is_present_with_both_halves(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "L1.53" in src and "NEVER MET BY SHRINKING ITS DENOMINATOR" in src
        assert "ACQUISITION IS NEVER CUT TO MEET EXTRACTION" in src
        assert "CONVERT FASTER" in src and "find harder" in src.lower(), (
            "the two required moves must stay distinguishable -- they are opposite instructions")

    def test_the_two_failures_may_not_be_merged(self) -> None:
        """Merging them is the natural simplification and it re-opens the exact hole: one number
        holding both lets a halved finding rate read as an improved ratio."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "NEVER merged into one number" in src

    def test_the_generalisation_beyond_the_ledger_survives(self) -> None:
        """The clause that makes L1.53 worth more than one fence: the same trap exists in every
        coverage, utilisation, kill-rate and breadth figure the desk reports."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "its denominator is a first-class measurement" in src
        for gauge in ("coverage", "utilisation", "mutation kill rate"):
            assert gauge in src, f"the {gauge} generalisation was dropped"

    def test_both_laws_are_enforced_rather_than_prose(self) -> None:
        """A law with no fence is decoration, and the enforcement matrix fails the build on one.
        Pinned here too so the MAP cannot be quietly emptied while the matrix still passes on a
        keyword hit."""
        src = (_ROOT / "scripts" / "build_enforcement_matrix.py").read_text("utf-8")
        assert '"L1.52"' in src and "check_self_sufficiency" in src
        assert '"L1.53"' in src and "scripts/check_conversion.py" in src

    def test_the_measured_instances_stay_attached_to_the_rules(self) -> None:
        """A law that keeps its proving number is a law the next reader can falsify. Strip the
        measurement and it degrades into an opinion nobody can argue with."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "341 raised against 157" in src, "L1.53's proving measurement was dropped"
        assert "did not exist at all" in src, "L1.52's proving instance was dropped"


class TestL154NoGivingUp:
    """L1.54, pinned like its siblings. The clause most likely to be softened is clause 2 --
    because every OTHER clause makes the desk try harder, and clause 2 is the one that stops
    'try harder' from quietly becoming 'accept less'."""

    def test_l1_54_is_present_with_its_operative_clauses(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "L1.54" in src and "NO GIVING UP" in src
        assert "A CHAIN, NEVER A SINGLE NAME" in src
        assert "PARTIAL WORK IS KEPT" in src
        assert "A BLOCKED ATTEMPT LEAVES EVIDENCE" in src
        assert "BEFORE THE OUTAGE, NOT AFTER" in src

    def test_it_is_not_a_licence_to_fabricate(self) -> None:
        """The reading that would invert the law: 'never give up' as permission to report an
        unavailable thing as available. It is bounded explicitly and the bound must survive."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "It is NOT a licence to fabricate" in src
        assert "unknown reads as unknown" in src

    def test_degradation_is_never_leniency(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "DEGRADATION IS NEVER LENIENCY" in src
        assert "buys ATTEMPTS" in src, (
            "the distinction between more tries and a lower bar is the whole safety of this law")

    def test_blocked_names_a_route_not_a_source(self) -> None:
        """The clause with the most historical evidence behind it: 412 meant unsigned, 403 meant
        a bot-filtered User-Agent, and each cost the desk a corpus until someone re-read it."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "BLOCKED\" NAMES A ROUTE, NOT A SOURCE" in src or "NAMES A ROUTE" in src
        assert "412" in src and "403" in src
        assert "A recorded death with no such statement is not a measurement" in src

    def test_the_proving_measurement_stays_attached(self) -> None:
        src = _CONSTITUTION.read_text("utf-8")
        assert "56 firings a week" in src or "56 times a week" in src, (
            "strip the number and the law degrades into an opinion nobody can falsify")

    def test_the_law_is_enforced_rather_than_prose(self) -> None:
        src = (_ROOT / "scripts" / "build_enforcement_matrix.py").read_text("utf-8")
        assert '"L1.54"' in src and "scripts/kimi_hunter.py" in src

    def test_the_scope_is_desk_wide_not_routing_only(self) -> None:
        """The law was WRITTEN against a routing failure, and the narrow reading -- "this is about
        model fallbacks" -- is the one a future reader reaches for, because the proving instance is
        a model chain. The principal widened it explicitly: it binds every organ, sweep, screen,
        miner, hunter, panel, audit and cycle."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "SCOPE: EVERYWHERE, WITHOUT EXCEPTION" in src
        assert "NOT limited to routing" in src
        for organ in ("miner", "hunter", "panel", "audit", "screen"):
            assert organ in src.split("SCOPE: EVERYWHERE")[1][:1400], (
                f"the scope clause stopped naming {organ}")

    def test_the_only_legitimate_stop_requires_an_enumeration(self) -> None:
        """Without this the law is unfalsifiable in the wrong direction: anyone can claim they
        tried everything. The enumeration is what makes 'genuinely none' checkable, and it is the
        clause that would be softened first because producing it is work."""
        src = _CONSTITUTION.read_text("utf-8")
        assert "ENUMERATED" in src
        assert "laziness wearing a verdict" in src
