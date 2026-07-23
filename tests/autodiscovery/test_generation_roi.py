"""Tests for the generation-ROI falsification harness."""

from __future__ import annotations

import numpy as np

from libs.alpha_factory.hypothesis_novelty import PriorIdea
from libs.autodiscovery.generation_roi import Candidate, generation_roi

_RNG = np.random.default_rng(20260723)


def _null(n: int = 400) -> tuple[float, ...]:
    return tuple(float(x) for x in _RNG.normal(0.0, 0.01, n))


def _strong(n: int = 500) -> tuple[float, ...]:
    return tuple(float(x) for x in _RNG.normal(0.05, 0.05, n))  # ~1.0 per-period Sharpe


def _cand(cid: str, returns: tuple[float, ...], feat: str) -> Candidate:
    return Candidate(id=cid, statement=f"hypothesis {cid}", features=(feat,), returns=returns)


def test_null_batch_has_no_survivors() -> None:
    batch = [_cand(f"c{i}", _null(), f"f{i}") for i in range(8)]
    rep = generation_roi(batch, variance_of_sharpes=0.25)
    assert rep.backtested == 8
    assert rep.survivors == 0
    assert rep.cost_per_survivor == float("inf")


def test_deflation_bar_rises_with_trial_count() -> None:
    # Core claim: the DSR bar is higher when more has been searched (same candidates, same data).
    batch = [_cand(f"c{i}", _null(), f"f{i}") for i in range(5)]
    small = generation_roi(batch, variance_of_sharpes=0.25, n_trials_prior=0)
    large = generation_roi(batch, variance_of_sharpes=0.25, n_trials_prior=5000)
    assert large.deflated_bar_sr0 > small.deflated_bar_sr0


def test_same_edge_survives_a_small_search_but_not_a_huge_one() -> None:
    strong = [_cand("edge", _strong(), "unique_feature")]
    survives = generation_roi(strong, variance_of_sharpes=0.25, n_trials_prior=0)
    drowned = generation_roi(strong, variance_of_sharpes=0.25, n_trials_prior=100_000)
    assert survives.survivors == 1        # a real edge clears a small search
    assert drowned.survivors == 0         # the same edge fails once deflated by a huge search


def test_novelty_gate_screens_redundant_and_saves_cost() -> None:
    prior = PriorIdea(
        id="g1",
        statement="momentum strengthens in low volatility regimes",
        features=("momentum", "volatility_regime"),
    )
    batch = [
        _cand("dup", _null(), "momentum"),  # statement+features match the graveyard -> redundant
        _cand("new", _null(), "stablecoin_flow"),
    ]
    # make the duplicate genuinely match the prior's statement + features
    batch[0] = Candidate(
        id="dup",
        statement="momentum strengthens in low volatility regimes",
        features=("momentum", "volatility_regime"),
        returns=_null(),
    )
    rep = generation_roi(batch, variance_of_sharpes=0.25, priors=[prior], cost_per_backtest=2.0)
    assert rep.proposed == 2
    assert rep.screened_out_redundant == 1
    assert rep.backtested == 1
    assert rep.cost_saved_by_novelty_gate == 2.0
    assert rep.cost_backtests == 2.0


def test_empty_batch_is_well_defined() -> None:
    rep = generation_roi([], variance_of_sharpes=0.25)
    assert rep.proposed == 0
    assert rep.backtested == 0
    assert rep.survivor_rate == 0.0
    assert rep.cost_per_survivor == float("inf")
