"""The market digital twin: a planted world is recovered from its own tape, a posterior that
reproduces returns and nothing else is named RETURNS_ONLY, and a rule's robustness is the
posterior's verdict -- mean reversion lives in a reverting world and dies in a trending one.

EVERY TAPE HERE IS SIMULATED FROM A KNOWN WORLD, because that is the only way to know what the
inference should find. The three load-bearing tests are the three claims the organ makes on the
desk: that the posterior covers the truth (credible intervals contain the planted parameters),
that the predictive checks catch a world that matches returns but not the microstructure, and
that robustness across posterior worlds discriminates a rule's habitat from its graveyard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from libs.research import digital_twin as dt  # noqa: E402

N_BARS, SUB = 300, 3
TOD = (np.arange(N_BARS) % 24) / 24.0
#: A quiet FX-like base world; each test moves a few reaction strengths off it.
BASE: dict[str, float] = {p.name: (p.lo + p.hi) / 2 for p in dt.PARAMS}
BASE.update(fundamental_vol=3e-4, base_intensity=30.0, hawkes_alpha=0.3, hawkes_decay=0.3,
            cancel_rate=0.3, latency_mean=1.0, latency_cv=0.5, impact_coef=1.0,
            impact_exponent=0.6, mm_spread_base=2e-5, mm_depth=50.0, mm_inventory_aversion=0.2,
            trend_strength=0.0, revert_strength=0.0, hedger_gamma=0.0, liquidator_strength=0.3,
            liquidation_threshold=3.0, retail_noise=1.0, passive_amp=0.2, season_amp=0.3,
            season_phase=0.6, jump_rate=0.003, jump_scale=4.0)


def world(**kw: float) -> np.ndarray:
    d = dict(BASE)
    d.update(kw)
    return np.array([[d[n] for n in dt.PARAM_NAMES]])


def degenerate(theta: np.ndarray, observed: np.ndarray | None = None) -> dt.Posterior:
    return dt.Posterior.from_particles(np.repeat(theta, 8, axis=0), n_bars=N_BARS,
                                       steps_per_bar=SUB, observed=observed)


def test_planted_world_is_recovered_within_posterior_credible_intervals() -> None:
    rng = np.random.default_rng(11)
    planted = dict(BASE, fundamental_vol=3e-4, trend_strength=0.3, revert_strength=1.5,
                   mm_spread_base=1e-4, jump_rate=0.005)
    obs = dt.summarise(dt.simulate(world(**planted), N_BARS, SUB, TOD, rng))[0]
    free = ("fundamental_vol", "trend_strength", "revert_strength", "mm_spread_base", "jump_rate")
    prior = dt.Prior(fixed={k: v for k, v in planted.items() if k not in free})
    assert set(prior.free) == set(free)
    post = dt.infer(obs, prior, n_bars=N_BARS, steps_per_bar=SUB, tod=TOD, rng=rng,
                    n_particles=128, n_rounds=2)
    assert post.n >= 24 and post.n_simulations >= 128 and len(post.eps_history) >= 2
    assert post.eps_history[-1] <= post.eps_history[0]
    for name in free:
        assert post.contains(name, planted[name], 0.95), (name, post.credible_interval(name, 0.95))

    def width(name: str) -> float:
        lo, hi = post.credible_interval(name, 0.9)
        spec = next(p for p in dt.PARAMS if p.name == name)
        return float((np.log(hi) - np.log(lo)) / (np.log(spec.hi) - np.log(spec.lo)))

    # the scale parameters are identified: the posterior is narrower than the prior
    assert min(width("fundamental_vol"), width("mm_spread_base")) < 0.9
    # a fixed parameter never moves
    lo, hi = post.credible_interval("hawkes_alpha", 0.9)
    assert lo == pytest.approx(planted["hawkes_alpha"]) and hi == pytest.approx(lo)
    # the posterior's own generator passes its predictive checks and survives the store
    check = dt.ppc(post, obs, tod=TOD, rng=rng, n_draws=48)
    score = dt.calibration_score(check)
    assert score.score is not None and score.score >= 0.7 and score.n_measured == len(dt.STATS)
    back = dt.Posterior.from_dict(json.loads(json.dumps(post.to_dict())))
    assert back.n == post.n and back.mean() == pytest.approx(post.mean())
    # particles are stored to eight decimals, so the round trip is exact to that precision
    assert back.credible_interval("jump_rate") == pytest.approx(
        post.credible_interval("jump_rate"), rel=1e-4)


def test_ppc_fails_a_returns_only_match_and_names_the_statistic() -> None:
    rng = np.random.default_rng(3)
    a = world()
    b = world(mm_spread_base=BASE["mm_spread_base"] * 20.0)   # same mid dynamics, wider quotes
    obs = dt.summarise(dt.simulate(a, N_BARS, SUB, TOD, rng))[0]
    check_b = dt.ppc(degenerate(b, obs), obs, tod=TOD, rng=rng, n_draws=48)
    assert check_b.verdict.startswith("RETURNS_ONLY") and not check_b.realistic
    assert "spread_log_mean" in check_b.failing
    assert check_b.groups["returns"] == "PASS" and check_b.groups["spread"].startswith("FAIL")
    score_b = dt.calibration_score(check_b)
    assert score_b.worst_statistic == "spread_log_mean" and score_b.max_abs_z is not None
    assert score_b.max_abs_z > dt.PPC_Z and score_b.score is not None and score_b.score < 1.0
    check_a = dt.ppc(degenerate(a, obs), obs, tod=TOD, rng=rng, n_draws=48)
    assert check_a.verdict == "REALISTIC" and check_a.realistic and check_a.failing == []
    assert dt.calibration_score(check_a).score == 1.0
    # a tape with no sided quotes cannot be REALISTIC, only REALISTIC_PARTIAL, and says which
    # groups it could not measure
    partial = obs.copy()
    for k, grp in enumerate(dt.STAT_GROUPS):
        if grp in ("spread", "impact", "cancellation"):
            partial[k] = np.nan
    check_p = dt.ppc(degenerate(a, partial), partial, tod=TOD, rng=rng, n_draws=48)
    assert check_p.verdict == "REALISTIC_PARTIAL"
    assert set(check_p.unmeasured_groups) == {"spread", "impact", "cancellation"}
    assert dt.calibration_score(check_p).n_unmeasured == 9


def test_mean_reversion_is_robust_in_a_reverting_posterior_and_fragile_in_a_trending_one() -> None:
    rng = np.random.default_rng(5)
    reverting = degenerate(world(revert_strength=3.0, mm_inventory_aversion=1.0, hedger_gamma=1.0,
                                 impact_coef=1.5))
    trending = degenerate(world(trend_strength=3.0, hedger_gamma=-1.0, impact_coef=1.5))
    fade, follow = dt.mean_reversion_rule(3), dt.momentum_rule(5)
    rb = dt.robustness(fade, reverting, 24, tod=TOD, rng=rng)
    assert rb.verdict == "ROBUST" and rb.p_positive >= 0.75 and rb.quantiles["q25"] > 0
    rb = dt.robustness(fade, trending, 24, tod=TOD, rng=rng)
    assert rb.verdict == "FRAGILE" and rb.p_positive < 0.5 and rb.n_worlds == 24
    assert dt.robustness(follow, trending, 24, tod=TOD, rng=rng).verdict == "ROBUST"
    assert dt.robustness(follow, reverting, 24, tod=TOD, rng=rng).p_positive < 0.5
    # the mechanism-plausibility test agrees with the rule
    mech = dt.mean_reversion_mechanism()
    assert dt.mechanism_plausibility(mech, reverting, 24, tod=TOD, rng=rng).verdict == "CAN_EXIST"
    assert dt.mechanism_plausibility(mech, trending, 24, tod=TOD, rng=rng).verdict == "CANNOT_EXIST"
    # and the pre-registration states the expected effect and the sample the power needs
    pre = dt.preregister(mech, reverting, 24, tod=TOD, rng=rng)
    assert pre.verdict == "CAN_EXIST" and pre.expected_effect is not None
    assert pre.expected_effect > 0 and pre.n_events_for_power is not None
    assert pre.n_events_for_power >= 1 and pre.windows_for_power is not None
    assert pre.windows_for_power > 0 and pre.effect_ci90 is not None
    assert pre.effect_ci90[0] <= pre.expected_effect <= pre.effect_ci90[1]
    # counterfactual execution cost under the posterior: paired worlds, so cost is cost
    cheap = dt.execution_cost(lambda _m: fade, reverting, 24, tod=TOD, rng=rng)
    assert cheap.n_worlds == 24 and cheap.cost_mean >= 0
    assert cheap.p_positive_at["0x"] >= cheap.p_positive_at["1x"] >= cheap.p_positive_at["2x"]
    assert cheap.verdict in {"COST_ROBUST", "COST_FRAGILE"}
    costly = degenerate(world(revert_strength=3.0, mm_inventory_aversion=1.0, hedger_gamma=1.0,
                              impact_coef=1.5, mm_spread_base=1e-3))
    dear = dt.execution_cost(lambda _m: fade, costly, 24, tod=TOD, rng=rng)
    assert dear.cost_share > cheap.cost_share and dear.cost_mean > cheap.cost_mean
    assert dear.verdict in {"COST_KILLED", "COST_FRAGILE", "NO_EDGE_BEFORE_COST"}


def test_unmeasured_fields_stay_nan_and_capacity_derives_from_memory() -> None:
    rng = np.random.default_rng(9)
    bars = dt.simulate(world(), N_BARS, SUB, TOD, rng, attribution=True)
    mix = dt.participant_mix(bars)
    assert mix is not None and abs(sum(mix.values()) - 1.0) < 1e-3 and mix["retail"] > 0
    # a real tape without sided quotes: spread, flow and flicker are UNMEASURED, never zero
    win = dt.tape_window(bars.open[0], bars.high[0], bars.low[0], bars.close[0], bars.volume[0],
                         TOD, steps_per_bar=SUB)
    s = dt.summarise(win)[0]
    for name, grp in dt.STATS:
        v = s[dt.STAT_NAMES.index(name)]
        if grp in ("spread", "impact", "cancellation"):
            assert np.isnan(v), name
        else:
            assert np.isfinite(v), name
    with pytest.raises(ValueError):
        dt.infer(np.full(len(dt.STATS), np.nan), dt.Prior(), n_bars=N_BARS, steps_per_bar=SUB,
                 tod=TOD, rng=rng)
    # worlds per batch are DERIVED from measured free memory: floor when unreadable or scarce,
    # ceiling when abundant, monotone between
    assert dt.capacity(None, 720, 4) == 64
    assert dt.capacity(60_000_000, 720, 4) == 64
    mid = dt.capacity(600_000_000, 720, 4)
    assert 64 < mid < 512
    assert dt.capacity(8_000_000_000, 720, 4) == 512
    assert dt.capacity(600_000_000, 1440, 4) < mid
