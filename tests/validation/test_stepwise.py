"""Tests for the per-candidate multiplicity gates (CSCV rank-consistency + Romano-Wolf).

These gates REPLACE two campaign constants that vetoed (or waved through) every candidate in a
batch identically.  The tests that matter are therefore the calibration ones: a known-null
campaign must not manufacture survivors, and a known-good candidate must be reachable.  Anything
that admits nulls here is a phantom-edge leak straight into the forward clocks.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.errors import ValidationError
from libs.validation.pbo import probability_backtest_overfitting
from libs.validation.stepwise import cscv_candidate_pbo, romano_wolf_stepdown

_PPY = 365.0
_SD = 0.40 / np.sqrt(_PPY)  # ~40% annualised vol, a realistic levered crypto sleeve


def _stream(true_ann_sharpe: float, n_obs: int, rng: np.random.Generator) -> np.ndarray:
    """Fat-tailed (Student-t df=6) daily net returns with a KNOWN true annual Sharpe."""
    z = rng.standard_t(6, size=n_obs)
    z /= np.sqrt(6.0 / 4.0)  # unit variance
    return true_ann_sharpe * _SD / np.sqrt(_PPY) + _SD * z


def _campaign(n_null: int, goods: list[float], n_obs: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    cols = [_stream(0.0, n_obs, rng) for _ in range(n_null)]
    cols += [_stream(s, n_obs, rng) for s in goods]
    return np.column_stack(cols)


class TestCSCVCandidatePBO:
    def test_null_candidates_centre_on_one_half(self) -> None:
        """A no-skill strategy has no reason to sit above or below the OOS median: PBO ~ 0.5."""
        m = _campaign(30, [], 800, seed=1)
        cand = np.array(cscv_candidate_pbo(m).candidate_pbo)
        assert 0.40 < cand.mean() < 0.60

    def test_strong_edge_is_rank_consistent(self) -> None:
        """A genuine edge holds its relative standing across every split -> PBO near 0."""
        m = _campaign(30, [3.0], 800, seed=2)
        cand = cscv_candidate_pbo(m).candidate_pbo
        assert cand[-1] < 0.10

    def test_is_candidate_aware_not_a_campaign_constant(self) -> None:
        """The defect being fixed: the old statistic was identical for every candidate."""
        m = _campaign(30, [3.0], 800, seed=3)
        cand = cscv_candidate_pbo(m).candidate_pbo
        assert len(set(np.round(cand, 6))) > 1

    def test_campaign_pbo_matches_the_classic_implementation(self) -> None:
        """The vectorised pass must reproduce the reference PBO it is derived from."""
        m = _campaign(12, [2.0], 400, seed=4)
        mine = cscv_candidate_pbo(m, n_splits=8).campaign_pbo
        ref = probability_backtest_overfitting(m, n_splits=8).pbo
        assert mine == pytest.approx(ref, abs=1e-12)

    def test_rejects_degenerate_input(self) -> None:
        with pytest.raises(ValidationError):
            cscv_candidate_pbo(np.zeros((100, 1)))
        with pytest.raises(ValidationError):
            cscv_candidate_pbo(np.zeros((100, 3)), n_splits=7)
        with pytest.raises(ValidationError):
            cscv_candidate_pbo(np.zeros((4, 3)), n_splits=8)


class TestRomanoWolfStepdown:
    def test_all_null_campaign_yields_almost_no_rejections(self) -> None:
        """THE PHANTOM-EDGE TEST: pure noise must not produce significant candidates."""
        for seed in (11, 12, 13):
            m = _campaign(40, [], 800, seed=seed)
            rej = np.array(romano_wolf_stepdown(m, n_boot=400).rejected)
            assert rej.sum() <= 2, f"seed {seed}: {rej.sum()}/40 false rejections"

    def test_strong_edge_is_detected(self) -> None:
        m = _campaign(40, [4.0], 800, seed=14)
        res = romano_wolf_stepdown(m, n_boot=400)
        assert res.rejected[-1] is True
        assert res.adjusted_p[-1] < 0.05

    def test_is_candidate_aware_not_a_campaign_constant(self) -> None:
        """A winner is rejected-as-significant while its noise peers are not."""
        m = _campaign(40, [4.0], 800, seed=15)
        rej = romano_wolf_stepdown(m, n_boot=400).rejected
        assert rej[-1] and not all(rej[:-1])

    def test_adjusted_p_is_monotone_in_the_statistic(self) -> None:
        """Stepdown p-values must not invert against the test statistic."""
        m = _campaign(25, [3.0, 1.0], 800, seed=16)
        res = romano_wolf_stepdown(m, n_boot=300)
        order = np.argsort(-np.array(res.t_stat))
        p_sorted = np.array(res.adjusted_p)[order]
        assert np.all(np.diff(p_sorted) >= -1e-12)

    def test_zero_variance_strategy_cannot_be_significant(self) -> None:
        rng = np.random.default_rng(17)
        m = np.column_stack([_stream(0.0, 400, rng) for _ in range(5)] + [np.zeros(400)])
        res = romano_wolf_stepdown(m, n_boot=200)
        assert res.rejected[-1] is False

    def test_rejects_degenerate_input(self) -> None:
        with pytest.raises(ValidationError):
            romano_wolf_stepdown(np.zeros(100))
        with pytest.raises(ValidationError):
            romano_wolf_stepdown(np.zeros((100, 2)), alpha=0.0)


class TestGateWiring:
    """The end-to-end property: per-candidate gates must discriminate WITHIN one campaign."""

    def test_validate_separates_winner_from_noise_in_the_same_batch(self) -> None:
        from libs.autodiscovery.models import Family, Hypothesis
        from libs.autodiscovery.validation import campaign_gate_stats, validate
        from libs.validation.economic_prior import MechanismType

        m = _campaign(20, [5.0], 600, seed=21)
        gates = campaign_gate_stats(m)
        assert gates is not None
        hyp = Hypothesis(
            family=Family.CARRY, subtype="t", symbol="BTCUSDT", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source="t", failure_modes=["t"],
        )
        sharpes = np.array([c.mean() / c.std(ddof=1) for c in m.T])

        def _gate(col: int, name: str) -> bool:
            v = validate(
                m[:, col], hypothesis=hyp, periods_per_year=365.0, n_trials=m.shape[1],
                sharpe_estimates=sharpes,
                returns_matrix=m, campaign=gates, column=col,
            )
            return bool(v.gates[name])

        # The winner clears both; the noise columns do not all clear them (the old code gave
        # every column the identical verdict, which is the bug this asserts against).
        assert _gate(m.shape[1] - 1, "pbo") and _gate(m.shape[1] - 1, "reality_check")
        assert not all(_gate(c, "reality_check") for c in range(20))

    def test_legacy_path_is_unchanged_when_no_campaign_supplied(self) -> None:
        """Unmigrated call sites must keep their exact prior behaviour."""
        from libs.autodiscovery.models import Family, Hypothesis
        from libs.autodiscovery.validation import campaign_pbo_rc, validate
        from libs.validation.economic_prior import MechanismType

        m = _campaign(8, [], 500, seed=22)
        pbo, rc = campaign_pbo_rc(m)
        hyp = Hypothesis(
            family=Family.CARRY, subtype="t", symbol="BTCUSDT", params={},
            mechanism=MechanismType.RISK_PREMIUM, edge_source="t", failure_modes=["t"],
        )
        sharpes = np.array([c.mean() / c.std(ddof=1) for c in m.T])
        v = validate(
            m[:, 0], hypothesis=hyp, periods_per_year=365.0, n_trials=8,
            sharpe_estimates=sharpes,
            returns_matrix=m, pbo=pbo, rc=rc,
        )
        assert v.gates["pbo"] is (pbo is not None and not pbo.overfit)
        assert v.gates["reality_check"] is (rc is not None and rc.significant_at_5pct)
