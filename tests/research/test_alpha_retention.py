"""BEHAVIORAL tests for operational alpha retention.

The property that matters: infrastructure work gets a NUMBER, in the same units as everything else
competing for the day, and only RECURRING loss counts as recoverable. Crediting a fix with edge it
can never earn back is how a plausible backlog outranks the research it was built to protect.
"""

from __future__ import annotations

import pytest

from libs.research.alpha_retention import (
    LOSS_CAUSES,
    MIN_DAYS_FOR_A_RATIO,
    LossEvent,
    RetentionRecord,
    alpha_retention_ratio,
    decompose,
    recoverable_ratio,
    summarise,
)


def _rec(**kw) -> RetentionRecord:
    base: dict[str, object] = {"strategy_id": "S1", "live_days": 60.0,
                               "expected_bps": 200.0, "realised_bps": 110.0, "losses": ()}
    base.update(kw)
    return RetentionRecord(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------- the ratio

def test_the_shortfall_is_measured_against_the_validated_expectation() -> None:
    ratio, why = alpha_retention_ratio(_rec())
    assert ratio == pytest.approx(0.55)
    assert "retained 55%" in why
    assert "appears on no P&L statement" in why


def test_a_short_live_record_is_unmeasured_not_a_ratio() -> None:
    ratio, why = alpha_retention_ratio(_rec(live_days=3.0))
    assert ratio is None
    assert "describes an incident, not an operation" in why


def test_no_validated_expectation_means_no_ratio() -> None:
    ratio, why = alpha_retention_ratio(_rec(expected_bps=0.0))
    assert ratio is None
    assert "no validated expectation recorded" in why


def test_beating_the_expectation_is_flagged_rather_than_celebrated() -> None:
    """Above 100% is either luck or a validation that understated the edge. Both deserve a look."""
    ratio, why = alpha_retention_ratio(_rec(realised_bps=260.0))
    assert ratio is not None and ratio > 1.0
    assert "not good news on its own" in why


# ----------------------------------------------------------------------- the decomposition

def test_an_unknown_loss_cause_cannot_be_recorded() -> None:
    """An unlisted cause is either a missing entry or it is the EDGE being wrong, which is a
    research finding and belongs in the kill audit rather than here."""
    with pytest.raises(ValueError, match="unknown loss cause"):
        LossEvent("VIBES", 10.0)
    assert "SCHEDULER_MISS" in LOSS_CAUSES and "MISSED_FILL" in LOSS_CAUSES


def test_losses_aggregate_by_cause_across_strategies() -> None:
    a = _rec(strategy_id="A", losses=(LossEvent("SLIPPAGE_EXCESS", 10.0, fix_cost_hours=1.0),))
    b = _rec(strategy_id="B", losses=(LossEvent("SLIPPAGE_EXCESS", 30.0, fix_cost_hours=3.0),
                                      LossEvent("STALE_DATA", 5.0)))
    table = decompose([a, b])
    assert table["SLIPPAGE_EXCESS"]["lost_bps"] == pytest.approx(40.0)
    assert table["SLIPPAGE_EXCESS"]["events"] == 2
    assert next(iter(table)) == "SLIPPAGE_EXCESS", "the table must lead with the largest loss"


# ------------------------------------------------------- infrastructure gets a number

def test_recoverable_ratio_is_bps_per_engineering_hour() -> None:
    r = _rec(losses=(LossEvent("SCHEDULER_MISS", 40.0, recurring=True, fix_cost_hours=2.0),))
    ratio, why = recoverable_ratio("SCHEDULER_MISS", decompose([r]))
    assert ratio == pytest.approx(20.0)
    assert "bp per engineering hour" in why
    assert "comparable with any research item" in why


def test_a_one_off_incident_is_not_recoverable_value() -> None:
    """Crediting a fix with edge it can never earn back is how an infrastructure backlog outranks
    the research it exists to protect."""
    r = _rec(losses=(LossEvent("PROVIDER_OUTAGE", 500.0, recurring=False, fix_cost_hours=1.0),))
    ratio, _ = recoverable_ratio("PROVIDER_OUTAGE", decompose([r]))
    assert ratio == pytest.approx(0.0), "a spent one-off was scored as recoverable"


def test_an_unestimated_fix_cannot_be_ranked_and_says_why() -> None:
    r = _rec(losses=(LossEvent("MODEL_ERROR", 60.0, recurring=True, fix_cost_hours=0.0),))
    ratio, why = recoverable_ratio("MODEL_ERROR", decompose([r]))
    assert ratio is None
    assert "UNMEASURED" in why
    assert "never gets scheduled" in why


def test_an_unrecorded_cause_returns_none() -> None:
    ratio, why = recoverable_ratio("VENUE_OUTAGE", decompose([_rec()]))
    assert ratio is None
    assert "no recorded events" in why


# ------------------------------------------------------------------------------ report

def test_the_report_ranks_causes_by_recoverable_value_not_by_size() -> None:
    """A 500bp loss that costs 100h to fix must lose to a 40bp loss that costs 1h."""
    r = _rec(losses=(
        LossEvent("STALE_DATA", 500.0, recurring=True, fix_cost_hours=100.0),   # 5 bp/h
        LossEvent("SCHEDULER_MISS", 40.0, recurring=True, fix_cost_hours=1.0),  # 40 bp/h
    ))
    rep = summarise([r])
    ranked = rep["loss_by_cause"]
    assert isinstance(ranked, list)
    assert ranked[0]["cause"] == "SCHEDULER_MISS"
    assert ranked[0]["RECOVERABLE_BPS_PER_HOUR"] == pytest.approx(40.0)


def test_the_worst_retention_is_named() -> None:
    good = _rec(strategy_id="good", realised_bps=190.0)
    bad = _rec(strategy_id="bad", realised_bps=20.0)
    rep = summarise([good, bad])
    assert rep["worst_retention"] == "bad"
    assert "worst retains 10%" in str(rep["headline"])


def test_the_note_forbids_inferring_the_counterfactual_from_the_market() -> None:
    rep = summarise([_rec()])
    assert "never what the market did afterwards" in str(rep["note"])
    assert "every quiet week look like an outage" in str(rep["note"])


def test_an_empty_ledger_says_shortfalls_read_as_bad_research() -> None:
    rep = summarise([])
    assert "UNMEASURED" in str(rep["headline"])
    assert "research having been wrong" in str(rep["headline"])


def test_the_days_floor_is_not_silently_tiny() -> None:
    assert MIN_DAYS_FOR_A_RATIO >= 14
