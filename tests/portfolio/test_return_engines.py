"""BEHAVIORAL tests for return-engine attribution and effective independence.

The named cases from the specification: carry/beta/selection attribution works, root + subnet
exposures collapse into one ecosystem factor, and business revenue cannot enter the basis at all.
"""

from __future__ import annotations

import pytest

from libs.portfolio.return_engines import (
    ENGINES,
    MAX_HEALTHY_RESIDUAL_SHARE,
    EngineReturn,
    attribute,
    beta_share,
    effective_engine_count,
    hidden_beta,
    summarise,
)


def _series(seed: int, n: int = 200, common: float = 0.0) -> tuple[float, ...]:
    """Pseudo-returns with a tunable common factor, SEEDED so the test cannot flake.

    A seeded PRNG rather than phase-shifted sines: sine waves at different phases are strongly
    correlated, which made the first draft of this helper produce rho=0.6 between series that
    were supposed to be independent -- a test fixture that would have condemned the module for
    the fixture's own defect.
    """
    import random
    rng = random.Random(seed)
    mkt = random.Random(9_999)
    out = []
    for _ in range(n):
        out.append(common * mkt.gauss(0.0, 0.01) + (1.0 - common) * rng.gauss(0.0, 0.01))
    return tuple(out)


# ------------------------------------------------------------------------ §53 attribution

def test_carry_beta_and_selection_are_attributed_separately() -> None:
    rows = [
        EngineReturn("PROTOCOL_CARRY", 4_000.0),
        EngineReturn("PROTOCOL_TOKEN_BETA", 9_000.0),
        EngineReturn("MOMENTUM_SELECTION", 2_000.0),
        EngineReturn("COST", -1_500.0),
        EngineReturn("FUNDING", -500.0),
    ]
    att = attribute(rows, gross_pnl=13_000.0)
    assert att["by_engine"]["PROTOCOL_CARRY"] == 4_000.0
    assert att["by_engine"]["PROTOCOL_TOKEN_BETA"] == 9_000.0
    assert att["by_engine"]["RESIDUAL"] == pytest.approx(0.0)
    assert att["independently_reconciled"] is True


def test_an_unexplained_majority_is_reported_as_a_missing_engine() -> None:
    """A large residual is the FINDING. Letting it sit in a table looking like rounding is how an
    attribution model with a hole in it gets cited as an explanation."""
    rows = [EngineReturn("INDEPENDENT_ALPHA", 1_000.0)]
    att = attribute(rows, gross_pnl=10_000.0)
    assert att["residual_share"] > MAX_HEALTHY_RESIDUAL_SHARE
    assert "an engine is missing" in str(att["finding"])


def test_summing_the_parts_to_define_the_whole_is_flagged_as_uninformative() -> None:
    att = attribute([EngineReturn("INDEPENDENT_ALPHA", 500.0)])
    assert att["independently_reconciled"] is False
    assert "carries no information" in str(att["finding"])


def test_business_revenue_cannot_enter_the_basis() -> None:
    """§53. Not a discipline rule: there is no engine to put it in, so construction raises."""
    with pytest.raises(ValueError, match="unknown return engine"):
        EngineReturn("BUSINESS_REVENUE", 50_000.0)
    with pytest.raises(ValueError, match="self-issued token marks"):
        EngineReturn("SELF_ISSUED_TOKEN", 1_000_000.0)


def test_the_basis_is_closed_and_complete() -> None:
    assert "RESIDUAL" in ENGINES and "BETA_REGIME" in ENGINES and "EXECUTION" in ENGINES
    assert len(set(ENGINES)) == len(ENGINES)


# ------------------------------------------------------------------------- beta honesty

def test_beta_is_a_first_class_engine_not_a_disqualification() -> None:
    rows = [EngineReturn("BETA_REGIME", 8_000.0), EngineReturn("INDEPENDENT_ALPHA", 2_000.0)]
    share, why = beta_share(rows)
    assert share == pytest.approx(0.8)
    assert "not a criticism" in why
    assert "allowed to compete for capital" in why


def test_an_alpha_engine_that_behaves_like_the_market_is_named() -> None:
    rows = [EngineReturn("INDEPENDENT_ALPHA", 5_000.0, market_beta=0.92, r2_market=0.81)]
    found = hidden_beta(rows)
    assert len(found) == 1
    assert "declared independent, behaves as directional exposure" in found[0]


def test_a_declared_beta_engine_is_not_reported_as_hidden_beta() -> None:
    rows = [EngineReturn("BETA_REGIME", 5_000.0, market_beta=1.0, r2_market=0.99)]
    assert hidden_beta(rows) == []


def test_beta_share_is_undefined_not_zero_when_there_are_no_gains() -> None:
    share, why = beta_share([EngineReturn("INDEPENDENT_ALPHA", -100.0)])
    assert share is None
    assert "undefined, not zero" in why


# --------------------------------------------------------- §58 effective independence

def test_five_uncorrelated_engines_are_five_bets() -> None:
    rows = [EngineReturn(e, 100.0, returns=_series(i, common=0.0))
            for i, e in enumerate(("INDEPENDENT_ALPHA", "MOMENTUM_SELECTION", "REBOUND_TIMING",
                                   "PARTICIPANT_FLOW", "EXECUTION"))]
    n_eff, why = effective_engine_count(rows)
    assert n_eff is not None and n_eff > 3.0, why


def test_root_plus_subnet_exposures_collapse_into_one_ecosystem_factor() -> None:
    """THE NAMED CASE. A root token and its subnets look like diversification and share one
    factor. The nominal count is what a dashboard would print; the effective count is the truth."""
    rows = [EngineReturn(e, 100.0, returns=_series(i, common=0.97))
            for i, e in enumerate(("PROTOCOL_TOKEN_BETA", "PROTOCOL_CARRY", "MOMENTUM_SELECTION",
                                   "INDEPENDENT_ALPHA", "REBOUND_TIMING"))]
    n_eff, why = effective_engine_count(rows)
    assert n_eff is not None
    assert n_eff < 2.0, f"five near-identical engines reported {n_eff} independent bets: {why}"
    assert "one bet placed several times" in why


def test_independence_is_unmeasured_without_series_and_says_so() -> None:
    rows = [EngineReturn("INDEPENDENT_ALPHA", 100.0), EngineReturn("BETA_REGIME", 100.0)]
    n_eff, why = effective_engine_count(rows)
    assert n_eff is None
    assert "UNMEASURED" in why
    assert "nothing here supports treating it as a count of BETS" in why


# ------------------------------------------------------------------------------ report

def test_the_report_leads_with_the_finding_not_the_table() -> None:
    rows = [EngineReturn("INDEPENDENT_ALPHA", 5_000.0, returns=_series(1, common=0.98),
                         market_beta=0.9, r2_market=0.9),
            EngineReturn("BETA_REGIME", 5_000.0, returns=_series(2, common=0.98))]
    rep = summarise(rows, gross_pnl=10_000.0)
    assert "behave as market beta" in str(rep["headline"])
    assert rep["effective_engine_count"] is not None
    assert rep["nominal_engine_count"] == 2


def test_an_empty_book_says_every_euro_is_unexplained() -> None:
    rep = summarise([])
    assert "UNMEASURED" in str(rep["headline"])
    assert "beta gets reported as alpha" in str(rep["headline"])
