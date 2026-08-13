"""R0312: the order-sensitive decay bar, and the numerical failure it exists to avoid.

The simulated null is the load-bearing test here. A combination statistic whose null distribution
is asserted rather than checked is exactly the "confidently wrong" class L1.29 exists for: it
would produce error rates that look like probabilities, feed a decay verdict, and be wrong in a
direction nobody could see. So irwin_hall_cdf is validated against Monte Carlo, and the float
implementation it replaces is kept here as a regression fixture showing why.
"""
from __future__ import annotations

import collections
import random
from math import comb, factorial, floor

import pytest

from libs.research.order_sensitive_decay import (
    _NULL_BAND,
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
        assert n_decay <= 1150, f"asymmetric under the null: {n_decay}/2000"

    def test_a_null_record_mostly_reads_STABLE_not_a_direction(self) -> None:
        """R0467: symmetry was asserted, REFUSAL never was, and only refusal was the point.

        The sibling test above passed throughout on a verdict that called a direction on 100% of
        null records -- a fair coin is still a coin. Measured before the band: DECAYING 10,045 /
        STRENGTHENING 9,955 / STABLE 0 over 20,000 records. This pins the property whose absence
        that test could not see.
        """
        rng = random.Random(20260813)
        mix = collections.Counter(
            decay_verdict([rng.random() for _ in range(14)])["verdict"] for _ in range(2000))
        assert mix[STABLE] >= 1800, f"the null must mostly read STABLE, got {dict(mix)}"
        directional = mix[DECAYING] + mix[STRENGTHENING]
        assert directional <= 160, f"false-direction rate above the 5% design: {directional}/2000"

    def test_the_band_is_the_closed_form_not_a_tuned_number(self) -> None:
        # Each half's error rate is Uniform(0,1) under the null (probability integral transform)
        # and the halves are independent, so the difference is triangular: P(|D|>t) = (1-t)^2.
        assert pytest.approx(1.0 - 0.05**0.5) == _NULL_BAND
        assert decay_verdict([0.5] * 8)["null_band"] == pytest.approx(_NULL_BAND, abs=1e-6)

    def test_a_gap_inside_the_band_is_reported_but_not_called(self) -> None:
        """The live row that raised R0467: two halves at ~0.32 and ~0.35 read DECAYING."""
        r = decay_verdict([0.5894, 0.0883, 0.2715, 0.0164, 0.6407, 0.7252, 0.7997,
                           0.7674, 0.5722, 0.2233, 0.4788, 0.3266, 0.2632, 0.5755])
        assert r["verdict"] == STABLE
        assert 0.0 < abs(r["diff"]) < _NULL_BAND     # the evidence is still published
        # Both halves sit near a third, i.e. both say "nothing here" (0.5 is pure null). The old
        # code called a DIRECTION off the ~0.036 gap between them. Not pinned to more precision
        # than the inputs carry: these p-values are the published 4dp curve, so an exact-value
        # assertion here would pin a rounding artifact rather than the behaviour.
        assert 0.30 < r["error_rate_early"] < 0.36
        assert 0.30 < r["error_rate_late"] < 0.40
        assert r["error_rate_late"] > r["error_rate_early"]
