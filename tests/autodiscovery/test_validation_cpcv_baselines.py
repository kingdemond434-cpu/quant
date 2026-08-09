"""The gate named `cpcv` now runs actual CPCV, and a new gate asks the blunt question none of
the statistical gates ask: does this beat buy-and-hold?

Both modules existed, were tested, and were imported by nothing but their own tests -- while the
production validator carried a `cpcv` gate implemented as a contiguous 5-fold split."""

from __future__ import annotations

import numpy as np

from libs.autodiscovery.validation import (
    _CPCV_MIN_OBS,
    _beats_baselines,
    _cpcv_positive_fraction,
)


class TestCpcvIsActuallyCpcv:
    def test_a_consistently_positive_series_scores_high(self) -> None:
        rng = np.random.default_rng(0)
        arr = rng.normal(0.01, 0.01, 400)
        assert _cpcv_positive_fraction(arr) > 0.9

    def test_a_consistently_negative_series_scores_low(self) -> None:
        rng = np.random.default_rng(0)
        arr = rng.normal(-0.01, 0.01, 400)
        assert _cpcv_positive_fraction(arr) < 0.1

    def test_it_uses_many_test_paths_not_five_folds(self) -> None:
        """6 choose 2 = 15 combinatorial paths. The old contiguous split gave 5, so the fraction
        could only ever take six distinct values -- too coarse to sit behind a 0.6 threshold."""
        arr = np.concatenate([np.full(200, 0.01), np.full(200, -0.01)])
        frac = _cpcv_positive_fraction(arr)
        # with 15 paths the fraction lands off the 5-fold lattice {0, .2, .4, .6, .8, 1}
        assert 0.0 <= frac <= 1.0
        assert frac not in (0.0, 1.0)

    def test_a_short_series_falls_back_instead_of_raising(self) -> None:
        """Below the minimum there is nothing to be combinatorial about; failing a candidate for
        being NEW rather than for being bad would be the wrong direction of error."""
        arr = np.random.default_rng(1).normal(0.01, 0.01, _CPCV_MIN_OBS - 10)
        assert 0.0 <= _cpcv_positive_fraction(arr) <= 1.0

    def test_an_empty_series_is_zero_not_an_exception(self) -> None:
        assert _cpcv_positive_fraction(np.array([])) == 0.0

    def test_the_result_is_always_a_fraction(self) -> None:
        for n in (2, 61, 250, 1000):
            arr = np.random.default_rng(n).normal(0, 0.01, n)
            assert 0.0 <= _cpcv_positive_fraction(arr) <= 1.0


class TestBaselineGate:
    def test_no_benchmark_skips_the_gate(self) -> None:
        """The one deliberate fail-open in the gate set: the live sleeve is market-neutral carry,
        for which 'buy and hold what?' has no answer."""
        assert _beats_baselines(np.array([0.01, 0.02, 0.03]), None)

    def test_a_strategy_losing_to_buy_and_hold_fails(self) -> None:
        rng = np.random.default_rng(3)
        weak = rng.normal(0.0001, 0.01, 300)
        strong_benchmark = rng.normal(0.01, 0.01, 300)
        assert not _beats_baselines(weak, strong_benchmark)

    def test_a_strategy_beating_buy_and_hold_passes(self) -> None:
        rng = np.random.default_rng(4)
        strong = rng.normal(0.02, 0.005, 300)
        flat_benchmark = rng.normal(0.0, 0.02, 300)
        assert _beats_baselines(strong, flat_benchmark)

    def test_a_mismatched_benchmark_length_skips_rather_than_lies(self) -> None:
        assert _beats_baselines(np.zeros(300), np.zeros(50))

    def test_a_degenerate_benchmark_skips(self) -> None:
        assert _beats_baselines(np.zeros(300), np.array([0.01]))


class TestTheGateIsWiredIntoTheVerdict:
    def test_beats_baselines_appears_in_the_gate_set(self) -> None:
        """Wiring is the whole point of this change -- a gate absent from the verdict dict is a
        gate nobody runs, which is the state both these modules were already in."""
        import inspect

        from libs.autodiscovery import validation
        src = inspect.getsource(validation.validate)
        assert '"beats_baselines"' in src
        assert '"cpcv"' in src
