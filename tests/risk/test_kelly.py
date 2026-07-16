"""Kelly sizing tests — fractional, Bayesian, adaptive, with the hard 0.5 cap."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from libs.risk.errors import RiskError
from libs.risk.kelly import (
    AlphaStage,
    adaptive_kelly_fraction,
    calculate_bayesian_kelly,
    calculate_kelly,
)


def test_calculate_kelly() -> None:
    assert calculate_kelly(0.02, 0.04) == pytest.approx(0.5)
    with pytest.raises(RiskError):
        calculate_kelly(0.02, 0.0)


def test_bayesian_kelly_haircut_and_floor() -> None:
    naive = calculate_kelly(0.02, 0.04)
    haircut = calculate_bayesian_kelly(0.02, 0.005, 0.04, z=1.0)
    assert haircut < naive
    # huge uncertainty -> lower bound negative -> floored at 0 (no anti-betting)
    assert calculate_bayesian_kelly(0.01, 1.0, 0.04, z=2.0) == 0.0


def test_new_alpha_capped_at_third_kelly() -> None:
    scaling = adaptive_kelly_fraction(
        AlphaStage.NEW, track_record=500, live_vs_backtest=1.0, regime_stability=1.0, ci_lower=0.1
    )
    assert scaling.recommended_lambda <= 1 / 3 + 1e-9  # base/standard is third-Kelly


def test_validated_and_proven_caps() -> None:
    validated = adaptive_kelly_fraction(
        AlphaStage.VALIDATED, track_record=500, live_vs_backtest=1.0,
        regime_stability=1.0, ci_lower=0.1, current_lambda=0.40,
    )
    assert validated.target_lambda <= 0.42 + 1e-9
    proven = adaptive_kelly_fraction(
        AlphaStage.PROVEN, track_record=500, live_vs_backtest=1.0,
        regime_stability=1.0, ci_lower=0.1, current_lambda=0.50,
    )
    assert proven.target_lambda <= 0.50 + 1e-9       # half-Kelly only when fully earned


def test_no_evidence_collapses_to_third_kelly() -> None:
    scaling = adaptive_kelly_fraction(
        AlphaStage.PROVEN, track_record=500, live_vs_backtest=1.0,
        regime_stability=1.0, ci_lower=-0.01,  # negative lower bound -> no evidence
    )
    assert scaling.target_lambda == pytest.approx(1 / 3)  # falls back to the base


def test_scaling_up_is_gradual() -> None:
    scaling = adaptive_kelly_fraction(
        AlphaStage.PROVEN, track_record=500, live_vs_backtest=1.0,
        regime_stability=1.0, ci_lower=0.1, current_lambda=0.25,
    )
    assert scaling.recommended_lambda <= 0.25 + 0.02 + 1e-9  # at most one max_up_step


def test_scaling_down_is_immediate() -> None:
    scaling = adaptive_kelly_fraction(
        AlphaStage.NEW, track_record=0, live_vs_backtest=0.1,
        regime_stability=0.1, ci_lower=-1.0, current_lambda=0.50,
    )
    assert scaling.recommended_lambda == pytest.approx(scaling.target_lambda)
    assert scaling.recommended_lambda < 0.50


@given(
    track=st.integers(min_value=0, max_value=5000),
    lvb=st.floats(min_value=0.0, max_value=3.0),
    regime=st.floats(min_value=0.0, max_value=1.0),
    ci=st.floats(min_value=-1.0, max_value=1.0),
    current=st.floats(min_value=0.0, max_value=0.5),
    stage=st.sampled_from(list(AlphaStage)),
)
def test_never_exceeds_half_kelly(
    track: int, lvb: float, regime: float, ci: float, current: float, stage: AlphaStage
) -> None:
    scaling = adaptive_kelly_fraction(
        stage, track_record=track, live_vs_backtest=lvb, regime_stability=regime,
        ci_lower=ci, current_lambda=current,
    )
    assert 0.0 <= scaling.recommended_lambda <= 0.50
    assert 0.0 <= scaling.target_lambda <= 0.50
