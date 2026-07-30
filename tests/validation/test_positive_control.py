"""Tests for the gauntlet's positive/negative controls (R0017).

The invariant under test is the one whose silent violation cost the desk an audit: a "known-good"
control must have its target sample Sharpe BY CONSTRUCTION. The old construction was correct in
expectation and useless in practice -- at T=310 the standard error of an annualised Sharpe is 1.085,
so a fixed-seed draw with true SR +0.5 realised -2.32 and every gate rejected it correctly.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.validation.errors import ValidationError
from libs.validation.positive_control import (
    PPY,
    certify_gauntlet,
    exact_sharpe_series,
    null_cohort,
)


def _sample_ann_sharpe(x: np.ndarray) -> float:
    return float(x.mean() / x.std(ddof=1) * np.sqrt(PPY))


class TestExactSharpeSeries:
    @pytest.mark.parametrize("target", [0.0, 0.5, 1.0, 3.0, 7.0, 20.0, -1.5])
    @pytest.mark.parametrize("n_obs", [310, 800])
    def test_sample_sharpe_equals_target_exactly(self, target: float, n_obs: int) -> None:
        """The whole point: no sampling error in the DEFINITION of a good candidate."""
        for seed in range(8):
            s = exact_sharpe_series(target, n_obs, rng=np.random.default_rng(seed))
            assert _sample_ann_sharpe(s) == pytest.approx(target, abs=1e-9)

    def test_holds_at_the_length_that_broke_the_old_probe(self) -> None:
        """T=310 is where SE(SR)=1.085 -- the regime that made the old control meaningless."""
        assert np.sqrt(PPY / 310) == pytest.approx(1.085, abs=0.005)
        for seed in range(40):
            s = exact_sharpe_series(0.5, 310, rng=np.random.default_rng(seed))
            assert _sample_ann_sharpe(s) == pytest.approx(0.5, abs=1e-9)
            assert _sample_ann_sharpe(s) > 0.0  # the old construction went NEGATIVE here

    def test_old_construction_really_was_that_noisy(self) -> None:
        """Regression witness: documents why the fix was needed, not just that it works.

        Reproduces the previous probe's construction and shows a positive true Sharpe realising
        negative. If this ever stops holding, the SE argument above has changed and the control's
        design rationale must be re-derived.
        """
        sd = 0.40 / np.sqrt(PPY)
        realised = []
        for seed in range(40):
            rng = np.random.default_rng(seed)
            z = rng.standard_t(6, size=310) / np.sqrt(6 / 4.0)
            old = 0.5 * sd / np.sqrt(PPY) + sd * z  # the exact old formula
            realised.append(_sample_ann_sharpe(old))
        realised_arr = np.array(realised)
        assert realised_arr.std(ddof=1) > 0.7  # sampling noise dominates the signal
        assert (realised_arr < 0.0).any()  # a "good" control realising an edge of the wrong sign

    def test_preserves_fat_tails_and_scale(self) -> None:
        s = exact_sharpe_series(1.0, 4000, rng=np.random.default_rng(3))
        ann_vol = s.std(ddof=1) * np.sqrt(PPY)
        assert ann_vol == pytest.approx(0.40, rel=0.01)
        z = (s - s.mean()) / s.std(ddof=1)
        assert float(np.mean(z**4)) > 3.5  # kurtosis above the Gaussian 3.0 -> fat tails survived

    def test_rejects_degenerate_input(self) -> None:
        rng = np.random.default_rng(0)
        with pytest.raises(ValidationError):
            exact_sharpe_series(1.0, 2, rng=rng)
        with pytest.raises(ValidationError):
            exact_sharpe_series(1.0, 100, rng=rng, ann_vol=0.0)
        with pytest.raises(ValidationError):
            exact_sharpe_series(1.0, 100, rng=rng, df=2)


class TestNullCohort:
    def test_is_NOT_standardised(self) -> None:
        """The deliberate asymmetry. Pinning null columns collapses the DSR deflation benchmark.

        Nulls must keep their natural cross-sectional Sharpe dispersion: at n_obs bars that spread
        is ~sqrt(PPY/n_obs) annualised. A standardised cohort would show ~0.
        """
        m = null_cohort(60, 400, rng=np.random.default_rng(11))
        sharpes = np.array([_sample_ann_sharpe(c) for c in m.T])
        assert sharpes.std(ddof=1) > 0.5 * np.sqrt(PPY / 400)
        assert m.shape == (400, 60)

    def test_has_no_edge_on_average(self) -> None:
        m = null_cohort(200, 600, rng=np.random.default_rng(12))
        sharpes = np.array([_sample_ann_sharpe(c) for c in m.T])
        assert abs(sharpes.mean()) < 3.0 * sharpes.std(ddof=1) / np.sqrt(len(sharpes))

    def test_rejects_degenerate_input(self) -> None:
        with pytest.raises(ValidationError):
            null_cohort(0, 100, rng=np.random.default_rng(0))


class TestCertifyGauntlet:
    def test_reports_not_certified_when_nothing_can_pass(self) -> None:
        """A welded-shut gate must be NAMED as such, with its sole blocker attributed."""
        rep = certify_gauntlet(
            lambda _r, _s: (False, ["dsr"]), n_obs=310, targets=(1.0, 5.0), n_seeds=3,
        )
        assert not rep.certified
        assert rep.min_passing_sharpe is None
        assert rep.blocking_gates == {"dsr": 6}
        assert "uninterpretable" in rep.verdict

    def test_reports_not_certified_when_nulls_leak(self) -> None:
        rep = certify_gauntlet(
            lambda _r, _s: (True, []), n_obs=310, targets=(1.0,), n_seeds=4,
        )
        assert not rep.certified
        assert rep.null_false_pass_rate == 1.0
        assert "leaks phantom edges" in rep.verdict

    def test_certifies_a_gate_that_discriminates_on_sharpe(self) -> None:
        """A sane gate: admits realised Sharpe >= 2, rejects the rest. Must come back CERTIFIED."""
        rep = certify_gauntlet(
            lambda _r, s: (s >= 2.0, [] if s >= 2.0 else ["dsr"]),
            n_obs=310, targets=(0.5, 1.0, 3.0, 5.0), n_seeds=5,
        )
        assert rep.certified
        assert rep.min_passing_sharpe == 3.0
        assert rep.pass_rate_by_sharpe == {"0.5": 0.0, "1": 0.0, "3": 1.0, "5": 1.0}
        assert rep.null_false_pass_rate == 0.0

    def test_uses_independent_seeds_per_replication(self) -> None:
        """The other half of the R0017 lesson: one reused draw yields a smooth, wrong answer."""
        seen: list[float] = []

        def _spy(r: np.ndarray, _s: float) -> tuple[bool, list[str]]:
            seen.append(float(r[0]))
            return False, ["dsr"]

        certify_gauntlet(_spy, n_obs=310, targets=(1.0,), n_seeds=6)
        assert len(set(seen)) == len(seen)  # every replication is a distinct draw
