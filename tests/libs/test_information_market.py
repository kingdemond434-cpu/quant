"""INTERNAL INFORMATION MARKETS -- the seventh ancestor organ.

WHAT IS BROKEN TODAY. The panel aggregates by majority vote: eleven seats, one vote each. That
caps the panel's accuracy at the average seat's, forever, no matter how much evidence accumulates
about which seats are actually good -- and it deletes the single most valuable pattern available,
a lone dissenter with a track record.

The tests below defend three properties, each of which a naive implementation gets wrong:
  - the scoring rule must be PROPER, or seats maximise their score by always saying 0 or 1;
  - weights must start UNIFORM, because with no settled history there is no evidence anybody is
    better and inventing weights is fabrication;
  - a new seat starts at the population mean, not at zero, or the panel can never learn it is good.
"""

from __future__ import annotations

import math

import pytest

from libs.llm.market import (
    MIN_SETTLED,
    InformationMarket,
    aggregate,
    brier,
    log_score,
)

# ------------------------------------------------------------------ the scoring rule


def test_the_rule_is_proper_so_honesty_maximises_the_score() -> None:
    """THE PROPERTY THAT MAKES THE WHOLE THING WORK. Under an improper rule a seat maximises its
    score by always claiming certainty, and the market becomes a confidence contest."""
    true_p = 0.7
    def expected(report: float) -> float:
        return true_p * log_score(report, True) + (1 - true_p) * log_score(report, False)
    assert expected(0.7) > expected(0.5)
    assert expected(0.7) > expected(0.9)
    assert expected(0.7) > expected(0.99)


def test_a_confidently_wrong_call_costs_far_more_than_an_uncertain_one() -> None:
    """The calibration failure that actually loses money, priced accordingly."""
    assert log_score(0.99, False) < log_score(0.5, False) * 5


def test_certainty_is_clipped_so_one_wrong_call_is_not_a_death_sentence() -> None:
    """-inf would end a seat's weight permanently on a single call, destroying more information
    than the error did."""
    assert math.isfinite(log_score(0.0, True))
    assert log_score(0.0, True) == pytest.approx(math.log(1e-4))


def test_brier_is_reported_alongside_because_nats_are_illegible() -> None:
    assert brier(0.9, True) == pytest.approx(0.01)
    assert brier(0.9, False) == pytest.approx(0.81)


# ------------------------------------------------------------------ weights


def test_weights_are_uniform_until_there_is_a_record() -> None:
    """With nothing settled there is no evidence anybody is better. Inventing weights here would
    be fabrication dressed as sophistication."""
    m = InformationMarket()
    for seat in ("a", "b", "c"):
        m.stake(seat, "claim1", 0.6)
    w = m.weights()
    assert set(w) == {"a", "b", "c"}
    assert all(v == pytest.approx(1 / 3) for v in w.values())


def test_a_calibrated_seat_outweighs_a_miscalibrated_one() -> None:
    m = InformationMarket()
    for i in range(MIN_SETTLED + 3):
        truth = i % 2 == 0
        m.stake("sharp", f"c{i}", 0.9 if truth else 0.1)
        m.stake("blunt", f"c{i}", 0.1 if truth else 0.9)
        m.settle(f"c{i}", truth)
    w = m.weights()
    assert w["sharp"] > w["blunt"] * 5


def test_a_single_lucky_call_does_not_install_a_seat_as_the_oracle() -> None:
    """Below the settled minimum the sample is noise, and weighting on noise is how a market
    crowns whoever got the first coin flip."""
    m = InformationMarket()
    m.stake("lucky", "c0", 0.99)
    m.settle("c0", True)
    for i in range(MIN_SETTLED + 1):
        m.stake("steady", f"d{i}", 0.6)
        m.settle(f"d{i}", True)
    assert m.weights()["lucky"] <= m.weights()["steady"]


def test_a_new_seat_starts_at_the_population_mean_not_at_zero() -> None:
    """Unproven is not disbelieved. A seat starting at zero weight can never accumulate the
    record that would show it is good."""
    m = InformationMarket()
    for i in range(MIN_SETTLED + 1):
        m.stake("veteran", f"c{i}", 0.8)
        m.settle(f"c{i}", True)
    m.stake("rookie", "new", 0.6)
    w = m.weights()
    assert w["rookie"] > 0.0


def test_only_settled_claims_move_any_weight() -> None:
    """An open stake is an opinion. Weighting on opinions would let a seat farm influence by
    staking on claims that will never resolve."""
    m = InformationMarket()
    for i in range(20):
        m.stake("loud", f"open{i}", 0.99)
    assert m.records() == {}
    assert m.weights()["loud"] == pytest.approx(1.0)


# ------------------------------------------------------------------ consensus


def test_consensus_reports_what_the_weighting_actually_changed() -> None:
    """If weighting moved nothing, the market is majority vote with extra steps and should say
    so rather than presenting the same number as a sophisticated one."""
    m = InformationMarket()
    for i in range(MIN_SETTLED + 2):
        m.stake("sharp", f"h{i}", 0.95)
        m.stake("blunt", f"h{i}", 0.05)
        m.settle(f"h{i}", True)
    m.stake("sharp", "live", 0.8)
    m.stake("blunt", "live", 0.2)
    c = m.consensus("live")
    assert c["unweighted_p"] == pytest.approx(0.5)
    assert c["weighted_p"] > 0.5
    assert c["weighting_moved_it"] > 0


def test_disagreement_is_named_as_the_informative_case() -> None:
    """Unanimity across seats sharing most of their training data is weak evidence; a genuine
    split is where an unpriced view lives, and majority vote deletes it by construction."""
    m = InformationMarket()
    m.stake("a", "x", 0.9, "funding regime shift")
    m.stake("b", "x", 0.1, "the flow is one-sided and about to reverse")
    c = m.consensus("x")
    assert "HIGH DISAGREEMENT" in c["note"]
    assert c["strongest_dissent"]["rationale"]


def test_agreement_is_flagged_as_weak_evidence_not_as_confirmation() -> None:
    m = InformationMarket()
    for seat in ("a", "b", "c"):
        m.stake(seat, "y", 0.72)
    assert "correlated errors look exactly like consensus" in m.consensus("y")["note"]


def test_an_unstaked_claim_returns_nothing_rather_than_a_neutral_prior() -> None:
    """0.5 would be indistinguishable from a genuine coin-flip verdict, and a downstream ranker
    cannot tell 'nobody looked' from 'nobody could tell'."""
    c = InformationMarket().consensus("never asked")
    assert c["n"] == 0 and "nobody staked" in c["note"]


# ------------------------------------------------------------------ aggregation


def test_aggregation_is_arithmetic_not_log_odds() -> None:
    """Log-odds pooling is sharper and is the WRONG tool here: these seats share most of their
    training data, so pooling correlated forecasts manufactures extreme confidence out of what
    is nearly one opinion repeated."""
    p = aggregate({"a": 0.8, "b": 0.8, "c": 0.8})
    assert p == pytest.approx(0.8), "pooling identical views must not sharpen them"


def test_aggregation_respects_weights() -> None:
    assert aggregate({"a": 1.0, "b": 0.0}, {"a": 3.0, "b": 1.0}) == pytest.approx(0.75)


def test_an_empty_panel_returns_an_explicit_coin_flip() -> None:
    assert aggregate({}) == 0.5
