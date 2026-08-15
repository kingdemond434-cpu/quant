"""EFFECTIVE BREADTH -- pinned on the one substitution that makes every projection flattering.

The desk's return target is a Sharpe requirement (max growth = S^2/2), and the only controllable
route to a higher S is breadth: s*sqrt(k) for k INDEPENDENT sleeves. Every test here exists to stop
`k` being read off a count of strategies when what it means is a count of independent bets.
"""

from __future__ import annotations

import math

import pytest

from libs.research.breadth import (
    combined_sharpe,
    effective_breadth,
    growth_at,
    marginal_breadth,
    report,
    required_sharpe,
    sharpe_needed_for_monthly,
)


def test_A_MONTHLY_TARGET_IS_A_SHARPE_REQUIREMENT_NOT_AN_ASPIRATION() -> None:
    """7%/month is 125%/yr, which at the Kelly optimum needs S ~ 1.58. Naming the number is what
    turns "find ways" into a research requirement that can be checked against what is held."""
    need = sharpe_needed_for_monthly(0.07)
    assert need["annual"] == pytest.approx(1.07**12 - 1)
    assert need["required_sharpe"] == pytest.approx(1.58, abs=0.01)
    # and the inverse closes: the Sharpe named delivers the growth asked for
    assert growth_at(need["required_sharpe"]) == pytest.approx(need["annual"])


def test_GROWTH_AND_ITS_INVERSE_ARE_THE_SAME_ARITHMETIC() -> None:
    assert growth_at(1.0) == 0.5
    assert required_sharpe(0.5) == pytest.approx(1.0)
    assert growth_at(-2.0) == 0.0, "a negative Sharpe has no growth optimum to report"


def test_UNMEASURED_RHO_IS_NEVER_SILENTLY_INDEPENDENCE() -> None:
    """THE DEFECT THIS MODULE EXISTS FOR. Returning n when rho is unknown asserts the sleeves are
    independent, which multiplies the projected Sharpe by sqrt(n) while the book behaves like one
    position. UNMEASURED is a real answer (L1.28a) and it must survive the arithmetic."""
    assert effective_breadth(11, None) is None
    assert combined_sharpe(0.48, 11, None) is None
    assert effective_breadth(11, float("nan")) is None


def test_ONE_SLEEVE_IS_ONE_BET_WHATEVER_RHO_IS() -> None:
    """No pair exists to correlate, so this is arithmetic rather than an assumed default -- and
    checking rho first would have made a one-sleeve book report None and read as a defect."""
    assert effective_breadth(1, None) == 1.0
    assert effective_breadth(1, 0.9) == 1.0


def test_ELEVEN_CORRELATED_RULES_ARE_NOT_ELEVEN_BETS() -> None:
    """The live finding, in one assertion: the eleven discretionary rules are ~4 families, and at
    the correlation a family implies they compound like a book under two-wide. Every count of
    strategies the desk publishes hides exactly this."""
    assert effective_breadth(11, 0.0) == pytest.approx(11.0)
    assert effective_breadth(11, 0.8) == pytest.approx(11 / 9)
    assert effective_breadth(11, 1.0) == pytest.approx(1.0), "perfect correlation is one bet"
    assert effective_breadth(11, 0.8) < 2.0


def test_IMPOSSIBLE_CORRELATION_IS_REFUSED_NOT_REWARDED() -> None:
    """rho <= -1/(n-1) makes the correlation matrix non-PSD. The k_eff it implies is enormous, so
    the failure mode is a spectacular diversification result computed from broken data."""
    assert effective_breadth(11, -0.1) is None, "-1/(n-1) is exactly the singular point"
    assert effective_breadth(11, -0.5) is None
    # just inside the feasible region is fine, and large -- diversification is real, up to a limit
    k = effective_breadth(11, -0.09)
    assert k is not None and k > 100.0


def test_COMBINED_SHARPE_IS_THE_ONLY_MULTIPLIER_THE_DESK_CONTROLS() -> None:
    """s*sqrt(k_eff). Leverage cannot raise it -- past Kelly more leverage LOWERS growth -- and a
    better single edge is a hope. Breadth is the lever."""
    assert combined_sharpe(0.5, 4, 0.0) == pytest.approx(1.0)
    assert combined_sharpe(0.5, 11, 0.8) == pytest.approx(0.5 * math.sqrt(11 / 9))


def test_MARGINAL_BREADTH_RANKS_WHERE_RESEARCH_SHOULD_GO() -> None:
    """THE ASYMMETRY THAT DECIDES THE NEXT BUILD. A twelfth sleeve correlated 0.8 to a book of
    eleven adds ~0.002 effective bets; the FIRST uncorrelated one adds ~0.22 -- two orders of
    magnitude, for the same effort. That is the whole argument for building the tape-reading pair
    ahead of another price-structure variant."""
    same = marginal_breadth(11, 0.8, 0.8)
    orthogonal = marginal_breadth(11, 0.8, 0.0)
    assert same["k_before"] == pytest.approx(11 / 9)
    assert orthogonal["delta_k"] > 50 * same["delta_k"]
    assert orthogonal["sharpe_multiplier"] > same["sharpe_multiplier"] > 1.0
    # a NEGATIVELY correlated candidate is better still, and the ranking must show it
    hedging = marginal_breadth(11, 0.8, -0.2)
    assert hedging["delta_k"] > orthogonal["delta_k"]


def test_MARGINAL_BREADTH_REFUSES_A_NON_PSD_STRUCTURE() -> None:
    with pytest.raises(ValueError, match="positive semi-definite"):
        marginal_breadth(11, -0.5, 0.0)


def test_THE_REPORT_PUBLISHES_THE_WHOLE_RHO_CURVE_NOT_A_POINT() -> None:
    """A point estimate on a number this load-bearing invites the reader to forget it was
    estimated. With rho unmeasured the headline must be None and the curve must still be there --
    absence of a measurement is not absence of a question."""
    r = report({f"h{i}": 0.48 for i in range(1, 12)}, None, target_monthly=0.07)
    assert r["n_sleeves"] == 11
    assert r["rho_state"] == "UNMEASURED"
    assert r["effective_breadth"] is None and r["combined_sharpe"] is None
    assert r["annual_growth"] is None
    assert [row["rho"] for row in r["rho_curve"]] == [0.0, 0.2, 0.4, 0.6, 0.8]
    assert r["rho_curve"][0]["k_eff"] == pytest.approx(11.0)
    assert r["rho_curve"][-1]["k_eff"] == pytest.approx(11 / 9)
    assert "UNMEASURED" in str(r["why"])


def test_THE_REPORT_PRICES_THE_TARGET_IN_SLEEVES() -> None:
    """"We need 7% a month" becomes "we need N uncorrelated sleeves at today's quality". At s=0.48
    that is ~11 -- which is why the queue that rations seats is the binding constraint and not the
    sizing code."""
    r = report({f"h{i}": 0.48 for i in range(1, 12)}, 0.8, target_monthly=0.07)
    assert r["rho_state"] == "MEASURED"
    assert r["sleeves_needed_at_rho_0"] == math.ceil((1.5825 / 0.48) ** 2)
    assert r["effective_breadth"] == pytest.approx(1.22, abs=0.01)
    assert r["combined_sharpe"] is not None and r["combined_sharpe"] < 0.6


def test_AN_EMPTY_BOOK_HAS_NO_BREADTH_TO_REPORT() -> None:
    r = report({}, None)
    assert r["n_sleeves"] == 0 and r["mean_sleeve_sharpe"] == 0.0
    assert r["sleeves_needed_at_rho_0"] is None
    assert r["effective_breadth"] == 0.0, "no bets held -- not one, and not unmeasured"
