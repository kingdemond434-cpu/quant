"""THE AUDITOR OF SOMEONE ELSE'S CLAIM MUST CATCH THE MECHANISM, NOT THE MARKETING.

A martingale and a genuine edge can produce the same headline return over a short sample. They do
not produce the same TRADE LIST, and these tests pin the separation on synthetic sequences where
the true mechanism is known by construction -- which is the only way to check a detector of this
kind, because on real data the answer is exactly what is in dispute.

The negative controls matter more than the positives here. A module that shouts RISK-LOADED at
everything protects nobody: it would have flagged the desk's own fixed-size strategies, and the
first time it was right nobody would be listening.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.errors import ValidationError
from libs.validation.track_record import (
    ESCALATION_FLAG,
    TrackRecordAudit,
    audit_trades,
    compound,
    years_to_significance,
)


def _martingale(n: int = 400, seed: int = 0, base: float = 1.0, mult: float = 2.0,
                p_win: float = 0.70):
    """A textbook martingale: even-money bets at base size, doubling after every loss.

    This is the generator whose equity curve looks like the ones being advertised -- high win
    rate, near-straight line -- and whose risk is entirely in the streak.

    THE FIXTURE MUST BE PROFITABLE IN SAMPLE, which the first version was not: it paid 0.5x on a
    win against a 1x loss, making it negative-EV and therefore easy to reject on the headline
    numbers alone. That is the case nobody needs a detector for. A doubling rule at even money
    with a favourable in-sample win rate produces exactly the record that gets believed -- rising
    equity, high win rate, and an unsampled tail -- so that is what has to be caught.
    """
    rng = np.random.default_rng(seed)
    pnl, size = [], []
    cur = base
    for _ in range(n):
        size.append(cur)
        if rng.random() < p_win:
            pnl.append(1.0 * cur)
            cur = base                                # reset after a win
        else:
            pnl.append(-1.0 * cur)
            cur *= mult                               # double down
    return np.array(pnl), np.array(size)


def _fixed_size_edge(n: int = 400, seed: int = 1):
    """A real, modest edge traded at CONSTANT size -- the negative control."""
    rng = np.random.default_rng(seed)
    pnl = rng.normal(0.04, 1.0, n)
    return pnl, np.ones(n)


# ------------------------------------------------------------------ arithmetic

def test_compound_states_the_claims_own_consequence() -> None:
    """5%/week is not 'very good'; it is 12x a year. The number is the argument."""
    assert compound(0.05, 52) == pytest.approx(12.64, rel=0.01)
    assert compound(0.35, 12) == pytest.approx(36.64, rel=0.01)


def test_years_to_significance_is_the_number_that_settles_short_records() -> None:
    """At SR 1.0 it takes 4 years to reach t=2. A three-month sample supports no skill claim at
    all, however good the return looks."""
    assert years_to_significance(1.0) == pytest.approx(4.0)
    assert years_to_significance(2.0) == pytest.approx(1.0)
    assert years_to_significance(0.0) == float("inf")
    assert years_to_significance(-1.0) == float("inf"), "more data never rescues a negative edge"


# --------------------------------------------------------------- the positives

def test_a_martingale_is_caught() -> None:
    pnl, size = _martingale()
    a = audit_trades(pnl, size, starting_equity=1000.0)
    assert a.verdict == "RISK-LOADED"
    assert a.escalation_ratio >= ESCALATION_FLAG
    assert any("SIZE ESCALATES" in r for r in a.reasons)


def test_the_martingale_looks_good_on_the_headline_numbers() -> None:
    """THE POINT OF THE MODULE, AS A TEST. If the headline numbers exposed it, nobody would need
    this -- so the fixture must be one that PASSES a naive review and fails the sizing audit."""
    pnl, size = _martingale()
    a = audit_trades(pnl, size, starting_equity=1000.0)
    assert a.win_rate > 0.55, "high win rate is the advertised feature"
    assert a.total_pnl > 0, "and the sample is profitable, which is why it gets believed"
    assert a.verdict == "RISK-LOADED"


def test_size_growing_with_loss_depth_is_reported_separately() -> None:
    """Escalation-after-a-loss and escalation-with-DEPTH are different rules. A system that adds
    one increment after any loss trips the first; only recovery-doubling trips the second."""
    pnl, size = _martingale()
    a = audit_trades(pnl, size, starting_equity=1000.0)
    assert a.loss_depth_slope > 0.25
    assert any("SIZE GROWS WITH LOSS DEPTH" in r for r in a.reasons)


def test_ruin_fires_when_the_sample_actually_contains_the_tail() -> None:
    """With a low enough win rate the doubling rule DOES produce deep runs inside the sample, and
    then the resampled orderings find ruin. This is the case the bootstrap can speak to."""
    pnl, size = _martingale(n=600, p_win=0.45, mult=2.0, seed=3)
    a = audit_trades(pnl, size, starting_equity=abs(pnl.min()) * 3, n_boot=400)
    assert a.ruin_probability > 0.0
    assert a.deepest_loss_streak > 5


def test_a_zero_ruin_probability_is_published_as_a_lower_bound() -> None:
    """THE MOST DANGEROUS NUMBER IN THE MODULE, AND IT WAS FOUND BY A FAILING TEST OF MY OWN.

    The bootstrap resamples OBSERVED trades, so it reorders the sample but can never invent a loss
    deeper than any that occurred. On a doubling rule with a 70% in-sample win rate it returned
    ruin = 0.000 -- maximally reassuring about precisely the strategy this module exists to catch,
    because the rule's tail is not in the sample to be resampled.

    Reporting that unqualified would be this desk's own recurring failure: reading "not measured"
    as "measured and fine". Under an established escalation rule the figure must therefore be
    marked a lower bound, and must never buy a clean verdict.
    """
    pnl, size = _martingale()
    a = audit_trades(pnl, size, starting_equity=1000.0, n_boot=400)
    assert a.ruin_probability == 0.0, "the fixture's tail is genuinely outside the sample"
    assert a.ruin_is_lower_bound
    assert a.verdict == "RISK-LOADED", "a number it cannot measure must not clear the record"
    assert any("LOWER BOUND" in r for r in a.reasons)


def test_a_deep_sample_does_not_get_the_lower_bound_caveat() -> None:
    """The caveat must be earned by a SHORT streak history, not stamped on every escalating rule --
    otherwise it becomes noise and stops carrying information."""
    pnl, size = _martingale(n=600, p_win=0.45, mult=2.0, seed=3)
    a = audit_trades(pnl, size, starting_equity=abs(pnl.min()) * 3, n_boot=200)
    assert not a.ruin_is_lower_bound


# --------------------------------------------------------------- the negatives

def test_a_fixed_size_edge_is_not_flagged() -> None:
    """THE CONTROL THAT MATTERS MOST. A module that shouts at everything protects nobody."""
    pnl, size = _fixed_size_edge()
    a = audit_trades(pnl, size, starting_equity=1000.0, n_boot=500)
    assert a.verdict == "NO-RISK-LOADING-FOUND"
    assert a.escalation_ratio == pytest.approx(1.0, abs=1e-9)


def test_a_clean_verdict_refuses_to_claim_edge() -> None:
    """Absence of one failure mode is not presence of skill, and the report must say so in the
    same breath -- otherwise a clean verdict gets quoted as an endorsement."""
    pnl, size = _fixed_size_edge()
    a = audit_trades(pnl, size, starting_equity=1000.0, n_boot=200)
    assert any("NOT a finding of edge" in r for r in a.reasons)


def test_an_equity_curve_without_sizes_is_undecidable_not_clean() -> None:
    """The information simply is not in a curve. Defaulting to clean would turn 'I cannot check'
    into 'I checked and it is fine' -- the exact inversion this desk keeps finding in itself."""
    pnl, _ = _martingale()
    a = audit_trades(pnl, None, starting_equity=1000.0, n_boot=200)
    assert a.verdict in {"UNDECIDABLE", "RISK-LOADED"}
    assert any("NO SIZE COLUMN" in r for r in a.reasons)
    assert np.isnan(a.escalation_ratio)


def test_undecidable_when_the_curve_alone_shows_no_ruin() -> None:
    pnl, _ = _fixed_size_edge()
    a = audit_trades(pnl, None, starting_equity=1000.0, n_boot=200)
    assert a.verdict == "UNDECIDABLE", "no sizes means the mechanism question is refused"


# ------------------------------------------------------------------- hygiene

def test_missing_data_is_refused_rather_than_zero_filled() -> None:
    """A gap in someone's record is not a flat trade, and treating it as one flatters them."""
    with pytest.raises(ValidationError, match="non-finite"):
        audit_trades(np.array([1.0, np.nan, 2.0]), np.ones(3))


def test_mismatched_size_column_is_refused() -> None:
    with pytest.raises(ValidationError, match="rows"):
        audit_trades(np.ones(10), np.ones(9))


def test_negative_size_is_refused() -> None:
    """Direction belongs in the P&L sign. A negative 'size' would silently invert every sizing
    statistic in the module."""
    with pytest.raises(ValidationError, match="negative position size"):
        audit_trades(np.ones(5), np.array([1.0, -1.0, 1.0, 1.0, 1.0]))


def test_two_trades_is_the_floor() -> None:
    with pytest.raises(ValidationError, match="at least 2"):
        audit_trades(np.array([1.0]), np.array([1.0]))


def test_audit_is_frozen_so_a_verdict_cannot_be_edited_after_the_fact() -> None:
    pnl, size = _fixed_size_edge()
    a = audit_trades(pnl, size, n_boot=100)
    assert isinstance(a, TrackRecordAudit)
    with pytest.raises((AttributeError, TypeError)):
        a.verdict = "NO-RISK-LOADING-FOUND"        # type: ignore[misc]


def test_absent_starting_equity_is_generous_so_ruin_is_a_lower_bound() -> None:
    """The stand-in makes the account look as large as gross winnings, which UNDERSTATES ruin.
    Erring toward the claimant is the right direction for a number used to doubt them."""
    pnl, size = _martingale()
    with_anchor = audit_trades(pnl, size, starting_equity=100.0, n_boot=300)
    without = audit_trades(pnl, size, n_boot=300)
    assert without.ruin_probability <= with_anchor.ruin_probability + 1e-9
