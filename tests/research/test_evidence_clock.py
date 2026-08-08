"""CALENDAR TIME IS NOT EVIDENCE, AND TREATING IT AS EVIDENCE COSTS MONEY.

A strategy trading 500 times in five days accumulates more usable forward evidence than one
trading 8 times in three months; waiting the same interval for both is simultaneously too slow for
the first and too fast for the second. The clock counts EFFECTIVE INDEPENDENT observations, which
is the only version of the count that cannot be gamed by a busy afternoon.
"""

from __future__ import annotations

import pytest

from libs.research.evidence_clock import (
    MIN_EFFECTIVE,
    EvidenceState,
    annualised_information_rate,
    effective_n,
    regime_penalty,
    sufficiency,
    waiting_cost,
)


def _s(**kw) -> EvidenceState:
    base = {"raw_observations": 1000, "distinct_regimes": 3, "distinct_symbols": 1}
    return EvidenceState(**{**base, **kw})


def test_EFFECTIVE_N_NEVER_EXCEEDS_THE_RAW_COUNT() -> None:
    for kw in ({}, {"autocorrelation": -0.9}, {"distinct_symbols": 20, "cross_symbol_rho": 0.0},
               {"distinct_regimes": 9}):
        st = _s(**kw)
        assert effective_n(st) <= st.raw_observations + 1e-9


def test_NEGATIVE_AUTOCORRELATION_EARNS_NO_BONUS() -> None:
    """Crediting it would let a mean-reverting strategy claim MORE evidence than it has trades --
    an inflation in the one direction nobody would question."""
    assert effective_n(_s(autocorrelation=-0.8)) == pytest.approx(
        effective_n(_s(autocorrelation=0.0)))


def test_SERIAL_CORRELATION_DEFLATES_THE_COUNT() -> None:
    assert effective_n(_s(autocorrelation=0.8)) < effective_n(_s(autocorrelation=0.0)) / 5


def test_FIVE_HUNDRED_FILLS_IN_ONE_EVENT_ARE_ONE_OBSERVATION() -> None:
    """THE DEFLATOR THAT MATTERS MOST, and the one a trade count hides completely. No amount of
    serial independence within an event makes the event happen twice."""
    st = _s(raw_observations=500, distinct_events=1, distinct_regimes=3)
    assert effective_n(st) <= 1.0


def test_ONE_REGIME_IS_EVIDENCE_ABOUT_ONE_REGIME() -> None:
    assert regime_penalty(1) < regime_penalty(2) < regime_penalty(3)
    assert regime_penalty(0) == regime_penalty(1), "unmeasured is treated as concentrated"


def test_CORRELATED_SYMBOLS_DO_NOT_MULTIPLY_EVIDENCE() -> None:
    """At rho=1 the cohort is one instrument wearing several tickers."""
    indep = effective_n(_s(distinct_symbols=10, cross_symbol_rho=0.0))
    same = effective_n(_s(distinct_symbols=10, cross_symbol_rho=1.0))
    assert same < indep / 5


def test_AN_UNINSTRUMENTED_RECORD_IS_UNMEASURED_NOT_INSUFFICIENT() -> None:
    """An absence of measurement is never an absence of edge, and never a reason to wait a fixed
    interval -- the action is to start the record."""
    v, why = sufficiency(_s(measured=False), required=100)
    assert v == "UNMEASURED"
    assert "start the record" in why


def test_A_HIGH_INFORMATION_STRATEGY_CLEARS_QUICKLY() -> None:
    """The acceleration half: elapsed time does not enter the calculation."""
    v, why = sufficiency(_s(raw_observations=2000, distinct_events=900, distinct_regimes=3),
                         required=200)
    assert v == "SUFFICIENT"
    assert "Elapsed time did not enter this calculation" in why


def test_A_BURST_OF_CORRELATED_FILLS_DOES_NOT_CLEAR() -> None:
    """The symmetric half. A rule that only sped things up would be a lowered bar with a
    stopwatch."""
    v, _ = sufficiency(_s(raw_observations=5000, autocorrelation=0.95, distinct_events=3,
                          distinct_regimes=1), required=200)
    assert v == "ACCUMULATING"


def test_BELOW_THE_FLOOR_THE_GAP_ITSELF_IS_THE_FINDING() -> None:
    v, why = sufficiency(_s(raw_observations=400, distinct_events=2), required=10)
    assert v == "ACCUMULATING"
    assert f"{MIN_EFFECTIVE:.0f} floor" in why
    assert "gap between the two numbers IS the finding" in why


def test_WAITING_HAS_A_PRICE_AND_IT_IS_COMPUTED() -> None:
    """Until this is computed the spend is invisible, so caution always looks free and speed
    always looks reckless."""
    cost, why = waiting_cost(expected_edge_bps=2.0, effective_rate_per_day=20.0, days_waited=15.0)
    assert cost == pytest.approx(600.0)
    assert "what the delay COST" in why
    assert "not an argument that it was wrong" in why


def test_NO_WAITING_COST_WHEN_THE_EDGE_IS_NOT_POSITIVE() -> None:
    cost, why = waiting_cost(expected_edge_bps=-1.0, effective_rate_per_day=20.0, days_waited=10)
    assert cost == 0.0 and "caution is free here" in why


def test_INFORMATION_RATE_IS_NONE_WHEN_UNMEASURABLE() -> None:
    """This is what makes the track ENDOGENOUS to the strategy rather than a category assigned."""
    assert annualised_information_rate(_s(measured=False), 10) is None
    assert annualised_information_rate(_s(), 0) is None
    rate = annualised_information_rate(_s(raw_observations=600, distinct_events=300), 3.0)
    assert rate is not None and rate > 1.0


def test_CALENDAR_DAYS_CANNOT_ENTER_ANY_CALCULATION() -> None:
    """The property exists so a caller can REPORT elapsed time without any code path being able
    to promote on it."""
    assert _s().calendar_days == 0.0
    from pathlib import Path
    src = Path("libs/research/evidence_clock.py").read_text("utf-8")
    body = src.split("def effective_n")[1].split("def sufficiency")[0]
    assert "calendar" not in body.lower()
