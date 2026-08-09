"""BEHAVIORAL tests for effective sample size.

The headline case is the one the cross-lab review actually raised: a 30-day rolling feature
computed daily contains far fewer independent observations than its row count claims, and t scales
as sqrt(n), so the inflation lands directly on every significance decision.
"""

from __future__ import annotations

import math

import pytest

from libs.validation.effective_sample import (
    DEFLATORS,
    SampleGeometry,
    cross_dependence_deflator,
    effective_n,
    inflation_factor,
    overlap_deflator,
    serial_deflator,
    summarise,
    t_correction,
)

# ------------------------------------------------------------------- window overlap

def test_a_daily_stepped_thirty_day_window_keeps_a_thirtieth_of_its_rows() -> None:
    """THE ORIGINAL FINDING, as arithmetic."""
    g = SampleGeometry(rows=365, window_length=30, step=1)
    assert overlap_deflator(30, 1) == pytest.approx(1 / 30)
    assert effective_n(g) == pytest.approx(365 / 30, abs=0.01)
    assert inflation_factor(g) == pytest.approx(30.0, abs=0.01)


def test_non_overlapping_windows_lose_nothing() -> None:
    g = SampleGeometry(rows=365, window_length=30, step=30)
    assert overlap_deflator(30, 30) == 1.0
    assert effective_n(g) == pytest.approx(365.0)


def test_a_step_larger_than_the_window_cannot_credit_extra_observations() -> None:
    assert overlap_deflator(10, 50) == 1.0


# --------------------------------------------------------------------- the other five

def test_positive_autocorrelation_deflates_and_negative_does_not_inflate() -> None:
    """Crediting negative autocorrelation would let a mean-reverting series claim more evidence
    than it has rows -- an inflation in the one direction nobody would question."""
    assert serial_deflator(0.0) == pytest.approx(1.0)
    assert serial_deflator(0.5) == pytest.approx(1 / 3)
    assert serial_deflator(-0.9) == pytest.approx(1.0), "negative rho was credited"


def test_perfectly_correlated_series_are_one_series_wearing_several_tickers() -> None:
    assert cross_dependence_deflator(5, 1.0) == pytest.approx(0.2)
    assert cross_dependence_deflator(5, 0.0) == pytest.approx(1.0)
    assert cross_dependence_deflator(1, 1.0) == 1.0


def test_the_event_cap_is_hard_and_applies_last() -> None:
    """500 fills inside one liquidation cascade are ONE observation of one cascade, and no amount
    of serial independence within the event makes the event happen twice."""
    g = SampleGeometry(rows=500, distinct_events=1)
    assert effective_n(g) == pytest.approx(1.0)


def test_single_regime_evidence_is_halved() -> None:
    one = SampleGeometry(rows=1000, distinct_regimes=1)
    many = SampleGeometry(rows=1000, distinct_regimes=4)
    assert effective_n(one) == pytest.approx(500.0)
    assert effective_n(many) == pytest.approx(1000.0)


def test_the_deflators_compound_rather_than_compete() -> None:
    g = SampleGeometry(rows=1000, window_length=10, step=1, autocorrelation=0.5,
                       distinct_regimes=1)
    # 1000 * (1/10) * (1/3) * 0.5
    assert effective_n(g) == pytest.approx(1000 * 0.1 * (1 / 3) * 0.5, rel=1e-6)


def test_effective_n_never_exceeds_the_row_count() -> None:
    for kw in ({}, {"autocorrelation": -0.99}, {"n_assets": 20, "mean_asset_rho": 0.0},
               {"window_length": 1, "step": 99}):
        g = SampleGeometry(rows=100, **kw)  # type: ignore[arg-type]
        assert effective_n(g) <= 100.0 + 1e-9, kw


# ------------------------------------------------------------------ unmeasured is inert

def test_an_unmeasured_geometry_deflates_nothing_and_says_so() -> None:
    """Guessing downward on absent information would kill candidates for being unmeasured. The
    optimistic default is correct ONLY because the report names every inert deflator."""
    g = SampleGeometry(rows=500)
    assert effective_n(g) == pytest.approx(500.0)
    assert g.measured_deflators == ()
    _, why = t_correction(4.0, g)
    assert "LOWER" in why and "inert" in why


def test_measured_deflators_lists_only_what_was_actually_supplied() -> None:
    g = SampleGeometry(rows=100, window_length=5, step=1, distinct_regimes=3)
    assert set(g.measured_deflators) == {"WINDOW_OVERLAP", "REGIME_CONCENTRATION"}
    assert set(DEFLATORS) - set(g.measured_deflators)


# --------------------------------------------------------------------- the t correction

def test_the_t_statistic_is_corrected_by_the_square_root_of_the_deflation() -> None:
    """This is where the inflation actually costs money: a t of 4.2 that survives a 5.24 hurdle
    on a raw count may not survive on the effective one."""
    g = SampleGeometry(rows=400, window_length=4, step=1)      # 4x inflation
    corrected, why = t_correction(4.0, g)
    assert corrected is not None
    assert corrected == pytest.approx(4.0 / math.sqrt(4.0))
    assert "4.0x inflation" in why or "inflation" in why


def test_a_zero_effective_sample_yields_no_t_rather_than_a_zero() -> None:
    corrected, why = t_correction(9.0, SampleGeometry(rows=0))
    assert corrected is None
    assert "undefined" in why


# ------------------------------------------------------------------------------ report

def test_the_report_leads_with_the_worst_inflation() -> None:
    rep = summarise({
        "clean": SampleGeometry(rows=500, window_length=1, step=1, distinct_regimes=4),
        "terrible": SampleGeometry(rows=500, window_length=60, step=1, autocorrelation=0.8,
                                   distinct_regimes=1),
    })
    rows = rep["rows"]
    assert isinstance(rows, list)
    assert rows[0]["sample"] == "terrible"
    assert "overstates its evidence" in str(rep["headline"])


def test_the_note_refuses_the_naive_subsampling_fix() -> None:
    rep = summarise({"x": SampleGeometry(rows=100, window_length=10, step=1)})
    assert "worth LESS, not worthless" in str(rep["note"])
    assert "deflates the COUNT" in str(rep["note"])


def test_an_empty_report_says_every_n_is_a_raw_row_count() -> None:
    rep = summarise({})
    assert "UNMEASURED" in str(rep["headline"])
    assert "raw row count" in str(rep["headline"])
