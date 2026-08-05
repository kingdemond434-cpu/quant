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
