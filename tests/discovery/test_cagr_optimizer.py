"""THE CAGR OPTIMIZER -- that it scales DOWN to survive, and never up to look better.

Zero coverage until 2026-08-16 despite five test files naming it: every one referenced it as a
STRING in a path or manifest check, so it was mentioned everywhere and executed nowhere. The
module sizes an allocation and caps leverage, which makes "never actually run" the wrong property
for it to have had.

What matters here is the direction of every adjustment. An optimiser that scales UP when a
constraint binds is not a slower version of one that scales down -- it is the opposite instrument.
"""

from __future__ import annotations

import numpy as np
import pytest

from libs.discovery.cagr_optimizer import optimize_allocation
from libs.discovery.errors import DiscoveryError


def _rets(n: int, vol: float, *, mu: float = 0.0005, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(mu, vol, n)


class TestItRefusesRatherThanGuesses:
    def test_no_alphas_is_an_error_not_an_empty_allocation(self) -> None:
        with pytest.raises(DiscoveryError):
            optimize_allocation({})

    def test_too_few_observations_is_refused(self) -> None:
        # Nine points cannot support a covariance, a Kelly estimate or a survival simulation.
        with pytest.raises(DiscoveryError, match="10"):
            optimize_allocation({"a": _rets(9, 0.01)})

    def test_unequal_lengths_align_to_the_SHORTEST(self) -> None:
        # Padding the short series would invent observations; truncating the long one is the only
        # honest join, and the result must still be a valid allocation.
        out = optimize_allocation({"a": _rets(200, 0.01, seed=1),
                                   "b": _rets(50, 0.01, seed=2)}, n_sims=100)
        assert set(out.weights) == {"a", "b"}


class TestLeverageIsBoundedAbove:
    def test_leverage_never_exceeds_the_cap(self) -> None:
        for cap in (0.25, 1.0, 2.0):
            out = optimize_allocation({"a": _rets(400, 0.005, mu=0.01, seed=3)},
                                      leverage_cap=cap, n_sims=100)
            assert out.leverage <= cap + 1e-9, "a cap the optimiser can exceed is not a cap"

    def test_leverage_is_never_negative(self) -> None:
        # A negative allocation is a SHORT of the whole book, which this function has no mandate
        # to open and no stop behind.
        out = optimize_allocation({"a": _rets(300, 0.02, mu=-0.02, seed=4)}, n_sims=100)
        assert out.leverage >= 0.0

    def test_the_weights_do_NOT_sum_to_leverage_and_that_is_the_documented_truth(self) -> None:
        """THE FIELD COMMENT CLAIMED THEY DID, UNTIL 2026-08-16, AND THEY NEVER HAVE.

        `build_portfolio` returns a RISK BUDGET summing to less than one (0.2 apiece on a
        two-alpha book, so 0.4), which this module multiplies by `leverage`. Deployed gross is
        therefore `sum(base_weights) * leverage`. A caller sizing from `leverage` deploys 2.5x the
        weights; one sizing from the weights deploys 40% of the advertised leverage. Both readings
        were defensible from the old comment, which is what made it worse than none.
        """
        out = optimize_allocation({"a": _rets(300, 0.01, seed=5), "b": _rets(300, 0.01, seed=6)},
                                  n_sims=100)
        gross = sum(out.weights.values())
        assert gross < out.leverage, (
            "if these ever coincide the risk budget now sums to one, and the comment on "
            "CAGROptimization.weights must be revisited rather than left describing the old shape")
        assert gross == pytest.approx(0.4 * out.leverage, rel=1e-6), (
            "deployed gross is the risk budget TIMES leverage; any other relationship means "
            "build_portfolio changed and every caller's sizing moved with it")


class TestItScalesDownToSurvive:
    def test_a_violent_series_gets_LESS_leverage_than_a_calm_one(self) -> None:
        calm = optimize_allocation({"a": _rets(400, 0.004, seed=7)}, n_sims=200)
        wild = optimize_allocation({"a": _rets(400, 0.060, seed=7)}, n_sims=200)
        assert wild.leverage <= calm.leverage, (
            "the drawdown constraint must bind DOWNWARD -- an optimiser that levers into "
            "volatility is the opposite instrument to the one described")

    def test_a_tighter_drawdown_limit_never_raises_leverage(self) -> None:
        loose = optimize_allocation({"a": _rets(400, 0.03, seed=8)}, dd_limit=0.40, n_sims=200)
        tight = optimize_allocation({"a": _rets(400, 0.03, seed=8)}, dd_limit=0.05, n_sims=200)
        assert tight.leverage <= loose.leverage + 1e-9

    def test_passed_is_False_when_the_drawdown_bound_cannot_be_met(self) -> None:
        # Eight halvings is a finite budget. When it runs out the answer must be a REFUSAL, not a
        # quietly-returned allocation that failed its own constraint.
        out = optimize_allocation({"a": _rets(400, 0.15, seed=9)}, dd_limit=0.001,
                                  survival_min=0.999, n_sims=200)
        assert out.passed == (out.survival_probability >= 0.999
                              and out.worst_case_drawdown < 0.001)

    def test_bool_reflects_passed(self) -> None:
        out = optimize_allocation({"a": _rets(300, 0.01, seed=10)}, n_sims=100)
        assert bool(out) is out.passed


class TestDiversificationIsRewarded:
    def test_uncorrelated_alphas_carry_more_total_weight_than_duplicates(self) -> None:
        base = _rets(400, 0.01, seed=11)
        dup = optimize_allocation({"a": base, "b": base.copy()}, n_sims=200)
        indep = optimize_allocation({"a": base, "b": _rets(400, 0.01, seed=12)}, n_sims=200)
        assert sum(indep.weights.values()) >= sum(dup.weights.values()) - 1e-9, (
            "two copies of one alpha must not be sized like two independent ones -- that is the "
            "whole reason the allocator is correlation-aware")


class TestItIsReproducible:
    def test_the_same_seed_gives_the_same_allocation(self) -> None:
        # The survival step is a simulation. An allocation that moves between identical runs
        # cannot be audited after the fact.
        kw = {"n_sims": 200, "seed": 42}
        a = optimize_allocation({"x": _rets(300, 0.01, seed=13)}, **kw)   # type: ignore[arg-type]
        b = optimize_allocation({"x": _rets(300, 0.01, seed=13)}, **kw)   # type: ignore[arg-type]
        assert a.leverage == b.leverage
        assert a.worst_case_drawdown == b.worst_case_drawdown

    def test_the_result_is_frozen(self) -> None:
        out = optimize_allocation({"a": _rets(300, 0.01, seed=14)}, n_sims=100)
        with pytest.raises(Exception, match=r"frozen|Instance|immutable"):
            out.leverage = 99.0        # type: ignore[misc]
