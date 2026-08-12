"""R0312: the order-sensitive decay bar, and the numerical failure it exists to avoid.

The simulated null is the load-bearing test here. A combination statistic whose null distribution
is asserted rather than checked is exactly the "confidently wrong" class L1.29 exists for: it
would produce error rates that look like probabilities, feed a decay verdict, and be wrong in a
direction nobody could see. So irwin_hall_cdf is validated against Monte Carlo, and the float
implementation it replaces is kept here as a regression fixture showing why.
"""
from __future__ import annotations

import random
from math import comb, factorial, floor

import pytest

from libs.research.order_sensitive_decay import (
    DECAYING,
    STABLE,
    STRENGTHENING,
    UNDERPOWERED,
    decay_verdict,
    irwin_hall_cdf,
    mean_p_error_rate,
)


def _float_cdf(x: float, n: int) -> float:
    """The naive float implementation -- kept ONLY to prove why the exact one is required."""
    return sum((-1) ** k * comb(n, k) * (x - k) ** n for k in range(floor(x) + 1)) / factorial(n)


class TestIrwinHallAgainstASimulatedNull:
    @pytest.mark.parametrize("n", [2, 5, 12, 30])
    def test_cdf_matches_monte_carlo(self, n: int) -> None:
        """The null is CHECKED, not asserted. 40k draws gives ~0.005 resolution."""
        rng = random.Random(20260812 + n)
        draws = sorted(sum(rng.random() for _ in range(n)) for _ in range(40_000))
        for q in (0.1, 0.25, 0.5, 0.75, 0.9):
            x = draws[int(q * len(draws))]
            assert irwin_hall_cdf(x, n) == pytest.approx(q, abs=0.01)

    def test_it_is_a_proper_cdf(self) -> None:
        prev = -1.0
        for x10 in range(0, 121):
            v = irwin_hall_cdf(x10 / 10, 12)
            assert 0.0 <= v <= 1.0
            assert v >= prev - 1e-12, "a CDF may not decrease"
            prev = v

    def test_boundaries(self) -> None:
        assert irwin_hall_cdf(0.0, 7) == 0.0
        assert irwin_hall_cdf(7.0, 7) == 1.0
        assert irwin_hall_cdf(-4.0, 7) == 0.0     # domain-guarded, not extrapolated
        assert irwin_hall_cdf(99.0, 7) == 1.0

    def test_symmetry_about_the_mean(self) -> None:
        """sum of n uniforms is symmetric about n/2."""
        for n in (3, 8, 21):
            assert irwin_hall_cdf(n / 2, n) == pytest.approx(0.5, abs=1e-9)

    def test_rejects_a_degenerate_n(self) -> None:
        with pytest.raises(ValueError, match="n must be"):
            irwin_hall_cdf(1.0, 0)


class TestTheFloatImplementationDiverges:
    """The measured reason this module computes in rationals (R0312's actual defect)."""

    @pytest.mark.parametrize("n,floor_bound", [(50, -100.0), (80, -1e6)])
    def test_float_returns_impossible_probabilities_at_large_n(
            self, n: int, floor_bound: float) -> None:
        naive = _float_cdf(0.8 * n, n)
        assert naive < floor_bound, "the divergence this module exists to avoid has gone away"
        assert irwin_hall_cdf(0.8 * n, n) == pytest.approx(1.0, abs=1e-9)

    def test_they_agree_where_float_is_still_safe(self) -> None:
        """Small n is fine -- which is why the bug survived: it looks correct where it is tested."""
        for n in (3, 5, 10):
            assert irwin_hall_cdf(0.8 * n, n) == pytest.approx(_float_cdf(0.8 * n, n), abs=1e-9)

    def test_the_rows_specific_claim_does_not_reproduce(self) -> None:
        """R0312 recorded "returns 8.53 at p_mean=0.8/N=5". It does not, either way it is computed.

        Locked so the ledger's number is not quietly inherited as fact by the next reader: the
        defect class is real, the cited figure is not the evidence for it.
        """
        assert irwin_hall_cdf(4.0, 5) == pytest.approx(0.991667, abs=1e-6)
        assert _float_cdf(4.0, 5) == pytest.approx(0.991667, abs=1e-6)


class TestMeanP:
    def test_uniform_pvalues_give_a_middling_error_rate(self) -> None:
        assert mean_p_error_rate([0.5] * 9) == pytest.approx(0.5, abs=1e-9)

    def test_strong_agreement_across_periods_reads_small(self) -> None:
        assert mean_p_error_rate([0.01] * 6) < 1e-8

    def test_uniformly_bad_periods_read_large(self) -> None:
        assert mean_p_error_rate([0.97] * 6) > 0.999

    def test_refuses_values_that_are_not_pvalues(self) -> None:
        with pytest.raises(ValueError, match=r"\[0,1\]"):
            mean_p_error_rate([0.2, 1.4])

    def test_refuses_an_empty_record(self) -> None:
        with pytest.raises(ValueError, match="no p-values"):
            mean_p_error_rate([])


class TestDecayVerdictIsOrderSensitive:
    def test_the_same_multiset_in_two_orders_gives_opposite_verdicts(self) -> None:
        """The property DSR/PSR structurally cannot have: shuffle-variance.

        Identical distribution, reversed sequence, opposite conclusions -- and only one of them
        describes an edge worth capital.
        """
        good_then_bad = [0.01, 0.02, 0.03, 0.9, 0.95, 0.97]
        bad_then_good = list(reversed(good_then_bad))
        assert decay_verdict(good_then_bad)["verdict"] == DECAYING
        assert decay_verdict(bad_then_good)["verdict"] == STRENGTHENING

    def test_an_even_record_reads_stable(self) -> None:
        assert decay_verdict([0.3] * 8)["verdict"] == STABLE

    def test_both_halves_are_reported_not_a_collapsed_score(self) -> None:
        r = decay_verdict([0.01, 0.02, 0.9, 0.95])
        assert r["error_rate_early"] < r["error_rate_late"]
        assert r["n_early"] == 2 and r["n_late"] == 2

    def test_refuses_below_the_pre_registered_minimum(self) -> None:
        r = decay_verdict([0.1, 0.9])
        assert r["verdict"] == UNDERPOWERED
        assert "pre-registered minimum" in r["why"]

    def test_never_produces_an_empty_half(self) -> None:
        """A split that emptied one side would combine zero p-values and raise."""
        for n in range(4, 30):
            r = decay_verdict([0.5] * n)
            assert r["n_early"] >= 1 and r["n_late"] >= 1

    def test_a_null_record_does_not_systematically_read_decaying(self) -> None:
        """The bar must not manufacture decay out of noise -- it would retire live edges.

        Under the null the two halves are exchangeable, so DECAYING and STRENGTHENING must be
        roughly equally likely.
        """
        rng = random.Random(20260812)
        n_decay = sum(decay_verdict([rng.random() for _ in range(8)])["verdict"] == DECAYING
                      for _ in range(2000))
        assert 850 <= n_decay <= 1150, f"asymmetric under the null: {n_decay}/2000"
