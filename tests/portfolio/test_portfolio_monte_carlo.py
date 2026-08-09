"""THE TEST THAT DECIDES WHETHER THIS MODULE IS WORTH HAVING.

If `dependence_blindness` cannot tell a book of five identical strategies from a book of five
independent ones, then the synchronized resampling is not preserving anything and this is an
expensive way to re-run the Monte Carlo the desk already had. `test_CLONES_ARE_CAUGHT` and
`test_INDEPENDENT_BOOK_VINDICATES_THE_CHEAP_METHOD` are that discriminator, in both directions --
a metric that only ever fires is as useless as one that never does.

Every series here is seeded and constructed, never a sine wave: a fixture with accidental structure
would make an honest module look broken or a broken one look honest, and that has already cost this
desk a session once.
"""

from __future__ import annotations

import random

import numpy as np
import pytest

from libs.portfolio.portfolio_monte_carlo import (
    MIN_COMMON_MARKS,
    StrategyPath,
    dependence_blindness,
    portfolio_monte_carlo,
    stress_coactivation,
    summarise,
)

N = 250
DRAWS = 400


def _noise(seed: int, n: int = N, scale: float = 0.02) -> tuple[float, ...]:
    r = random.Random(seed)
    return tuple(r.gauss(0.0005, scale) for _ in range(n))


def _independent_book(k: int = 5) -> list[StrategyPath]:
    return [StrategyPath(strategy_id=f"i{j}", returns=_noise(1000 + j), weight=1.0 / k)
            for j in range(k)]


def _clone_book(k: int = 5) -> list[StrategyPath]:
    """One return series wearing five names -- the crypto book under stress."""
    shared = _noise(7)
    return [StrategyPath(strategy_id=f"c{j}", returns=shared, weight=1.0 / k) for j in range(k)]


class TestGuards:
    def test_empty_book_is_none(self) -> None:
        assert portfolio_monte_carlo([]) is None

    def test_RAGGED_PATHS_ARE_REFUSED_NOT_TRUNCATED(self) -> None:
        """Truncating to the shortest would silently discard the longest strategy's history."""
        paths = [StrategyPath(strategy_id="a", returns=_noise(1)),
                 StrategyPath(strategy_id="b", returns=_noise(2, n=N - 10))]
        assert portfolio_monte_carlo(paths) is None
        r = summarise(paths)
        assert r["measured"] is False
        assert "RAGGED" in str(r["headline"])
        assert "truncation" in str(r["headline"])

    def test_short_history_is_refused(self) -> None:
        short = [StrategyPath(strategy_id="a", returns=_noise(1, n=MIN_COMMON_MARKS - 1),
                              weight=1.0)]
        assert portfolio_monte_carlo(short) is None
        r = summarise(short)
        assert r["measured"] is False
        assert "same fortnight repeated" in str(r["headline"])

    def test_draws_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="draws"):
            portfolio_monte_carlo(_independent_book(), draws=0)

    def test_block_must_be_at_least_one(self) -> None:
        with pytest.raises(ValueError, match="mean_block"):
            portfolio_monte_carlo(_independent_book(), mean_block=0.5)

    def test_A_TOTAL_LOSS_DOES_NOT_POISON_THE_SUMMARY(self) -> None:
        """A -100% period would make log(0) eat every statistic. It must report ruin instead."""
        wipe = list(_noise(3))
        wipe[100] = -1.0
        paths = [StrategyPath(strategy_id="w", returns=tuple(wipe), weight=1.0)]
        res = portfolio_monte_carlo(paths, draws=DRAWS)
        assert res is not None
        assert np.isfinite(res.tail_portfolio_elog)
        assert np.isfinite(res.median_portfolio_elog)
        assert res.mc_ruin_probability > 0.0


class TestDependenceBlindness:
    def test_CLONES_ARE_CAUGHT(self) -> None:
        """THE POINT OF THE MODULE. Five copies of one strategy have no diversification, and
        independently shuffling them invents some. The ratio must say so."""
        blind = dependence_blindness(_clone_book(), draws=DRAWS)
        assert blind is not None
        assert blind > 1.3, (
            "per-strategy shuffling of five identical strategies must understate the joint "
            f"drawdown badly; got {blind}")

    def test_INDEPENDENT_BOOK_VINDICATES_THE_CHEAP_METHOD(self) -> None:
        """The other direction, and equally necessary: a metric that always fires measures nothing."""
        blind = dependence_blindness(_independent_book(), draws=DRAWS)
        assert blind is not None
        assert blind < 1.3, f"an independent book must not be flagged as dependence-blind; {blind}"

    def test_clones_score_higher_than_independents(self) -> None:
        c = dependence_blindness(_clone_book(), draws=DRAWS)
        i = dependence_blindness(_independent_book(), draws=DRAWS)
        assert c is not None and i is not None and c > i

    def test_single_strategy_has_no_dependence_to_be_blind_to(self) -> None:
        one = [StrategyPath(strategy_id="a", returns=_noise(1), weight=1.0)]
        assert dependence_blindness(one) is None

    def test_ragged_and_short_return_none(self) -> None:
        assert dependence_blindness([StrategyPath(strategy_id="a", returns=_noise(1)),
                                     StrategyPath(strategy_id="b",
                                                  returns=_noise(2, n=10))]) is None
        assert dependence_blindness([
            StrategyPath(strategy_id="a", returns=_noise(1, n=10)),
            StrategyPath(strategy_id="b", returns=_noise(2, n=10))]) is None

    def test_a_flat_book_gives_no_ratio_rather_than_a_divide_by_zero(self) -> None:
        flat = [StrategyPath(strategy_id=f"f{j}", returns=tuple([0.0] * N), weight=0.5)
                for j in range(2)]
        assert dependence_blindness(flat, draws=50) is None


class TestPortfolioMonteCarlo:
    def test_shape_and_ordering_of_the_drawdown_quantiles(self) -> None:
        res = portfolio_monte_carlo(_independent_book(), draws=DRAWS)
        assert res is not None
        assert 0.0 <= res.mc_drawdown_p50 <= res.mc_drawdown_p95 <= res.mc_drawdown_p99 <= 1.0
        assert 0.0 <= res.mc_ruin_probability <= 1.0
        assert res.strategies == 5 and res.marks == N and res.draws == DRAWS

    def test_TAIL_ELOG_IS_BELOW_THE_MEDIAN(self) -> None:
        """The worst 5% of paths must not read better than the middle, or the tail is mislabelled."""
        res = portfolio_monte_carlo(_independent_book(), draws=DRAWS)
        assert res is not None
        assert res.tail_portfolio_elog <= res.median_portfolio_elog

    def test_the_same_seed_reproduces(self) -> None:
        a = portfolio_monte_carlo(_independent_book(), draws=200, seed=99)
        b = portfolio_monte_carlo(_independent_book(), draws=200, seed=99)
        assert a is not None and b is not None
        assert a.mc_drawdown_p95 == b.mc_drawdown_p95

    def test_margin_is_unmeasured_rather_than_zero_when_absent(self) -> None:
        res = portfolio_monte_carlo(_independent_book(), draws=200)
        assert res is not None
        assert res.concurrent_margin_p95 is None

    def test_concurrent_margin_is_summed_across_the_book(self) -> None:
        paths = [StrategyPath(strategy_id=f"m{j}", returns=_noise(50 + j),
                              margin=tuple([0.2] * N), weight=0.5) for j in range(2)]
        res = portfolio_monte_carlo(paths, draws=200)
        assert res is not None
        assert res.concurrent_margin_p95 == pytest.approx(0.4, abs=1e-6)
        assert res.concurrent_margin_max == pytest.approx(0.4, abs=1e-6)


class TestStressCoactivation:
    def test_needs_two_strategies(self) -> None:
        c, why = stress_coactivation([StrategyPath(strategy_id="a", returns=_noise(1))])
        assert c is None
        assert "not yet a question" in why

    def test_ragged_has_no_common_clock(self) -> None:
        c, why = stress_coactivation([StrategyPath(strategy_id="a", returns=_noise(1)),
                                      StrategyPath(strategy_id="b", returns=_noise(2, n=20))])
        assert c is None
        assert "no common clock" in why

    def test_empty_paths_are_unmeasured(self) -> None:
        c, why = stress_coactivation([StrategyPath(strategy_id="a"),
                                      StrategyPath(strategy_id="b")])
        assert c is None
        assert "UNMEASURED" in why

    def test_MARKET_NEUTRAL_IS_NOT_LIQUIDATION_NEUTRAL(self) -> None:
        """Both strategies are active ONLY on the worst days. Return correlation never sees it;
        margin does."""
        rng = random.Random(11)
        base = [rng.gauss(0.0, 0.01) for _ in range(N)]
        worst = sorted(range(N), key=lambda i: base[i])[:N // 10]
        act = tuple(i in set(worst) for i in range(N))
        paths = [StrategyPath(strategy_id=f"s{j}", returns=tuple(base), active=act, weight=0.5)
                 for j in range(2)]
        rate, why = stress_coactivation(paths)
        assert rate is not None and rate > 0.9
        assert "Exposure CONCENTRATES into the bad days" in why

    def test_an_always_on_book_does_not_concentrate(self) -> None:
        paths = [StrategyPath(strategy_id=f"s{j}", returns=_noise(300 + j),
                              active=tuple([True] * N), weight=0.5) for j in range(2)]
        rate, why = stress_coactivation(paths)
        assert rate == pytest.approx(1.0)
        assert "does not concentrate" in why

    def test_whole_sample_mode(self) -> None:
        rate, _ = stress_coactivation(_independent_book(), worst_decile=False)
        assert rate is not None and 0.0 <= rate <= 1.0


class TestSummarise:
    def test_empty_book_names_why_per_strategy_mc_cannot_answer_it(self) -> None:
        r = summarise([])
        assert r["measured"] is False
        assert "independent shuffling is precisely what destroys it" in str(r["headline"])

    def test_full_report_on_a_clone_book_flags_the_blindness(self) -> None:
        r = summarise(_clone_book(), draws=DRAWS)
        assert r["measured"] is True
        assert r["DEPENDENCE_BLINDNESS"] is not None
        assert "understates" in str(r["dependence_blindness_note"])
        assert "understates the p95" in str(r["headline"])
        assert set(r["PORTFOLIO_MC_DRAWDOWN"]) == {"p50", "p95", "p99"}   # type: ignore[arg-type]

    def test_independent_book_reports_agreement(self) -> None:
        r = summarise(_independent_book(), draws=DRAWS)
        assert r["measured"] is True
        assert "was not lying" in str(r["dependence_blindness_note"])

    def test_missing_margin_is_named_as_the_mechanism_it_hides(self) -> None:
        r = summarise(_independent_book(), draws=200)
        assert r["CONCURRENT_MARGIN"] is None
        assert "uncorrelated strategies die together" in str(r["concurrent_margin_note"])

    def test_single_strategy_has_no_blindness_field(self) -> None:
        r = summarise([StrategyPath(strategy_id="a", returns=_noise(1), weight=1.0)], draws=200)
        assert r["measured"] is True
        assert r["DEPENDENCE_BLINDNESS"] is None
        assert "no dependence to be blind to" in str(r["dependence_blindness_note"])
