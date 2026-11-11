"""ALLOC-19/26: acceptance properties of the incumbent solver (`robust_elog.optimise`).

Each property is checked on synthetic sleeves where the right answer is known. Where the world
sampler's Monte Carlo noise matters (clones), the property is checked as an average over seeds
with the measured noise band, because a single seed's answer is not the solver's answer.
"""
from __future__ import annotations

import numpy as np

from libs.portfolio import robust_elog as re

CAP = 0.6


def _ev(mus, n=750, seed=1):
    rng = np.random.default_rng(seed)
    base = rng.normal(0, 1, (n, len(mus)))
    return [re.SleeveEvidence(name=f"s{i}", daily_r=mu + base[:, i], symbol=f"SYM{i}",
                              family=f"f{i}", forward_days=250, live_days=250)
            for i, mu in enumerate(mus)]


def _cfg(seed=0):
    return re.WorldConfig(n_worlds=64, n_rows=256, seed=seed)


def test_identical_inputs_give_identical_decisions() -> None:
    a = re.optimise(_ev([0.08, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    b = re.optimise(_ev([0.08, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    assert a.heat == b.heat


def test_small_noise_does_not_cause_gratuitous_turnover() -> None:
    ev = _ev([0.08, 0.06, 0.04])
    a = re.optimise(ev, hard_cap=CAP, cfg=_cfg())
    rng = np.random.default_rng(9)
    noisy = [re.SleeveEvidence(name=e.name, daily_r=e.daily_r + rng.normal(0, 0.01, e.daily_r.size),
                               symbol=e.symbol, family=e.family, forward_days=250, live_days=250)
             for e in ev]
    b = re.optimise(noisy, hard_cap=CAP, cfg=_cfg())
    turnover = sum(abs(b.heat[k] - a.heat[k]) for k in a.heat)
    assert turnover <= 0.10 * max(a.total_heat, 1e-9)


def test_exposure_rises_when_opportunity_improves() -> None:
    a = re.optimise(_ev([0.08, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    b = re.optimise(_ev([0.12, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    assert b.heat["s0"] > a.heat["s0"]


def test_exposure_falls_when_opportunity_deteriorates() -> None:
    a = re.optimise(_ev([0.12, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    b = re.optimise(_ev([0.02, 0.06, 0.04]), hard_cap=CAP, cfg=_cfg())
    assert b.heat["s0"] < a.heat["s0"]


def test_no_trade_when_nothing_is_positive() -> None:
    d = re.optimise(_ev([-0.05, -0.06, -0.04]), hard_cap=CAP, cfg=_cfg())
    assert d.total_heat < 1e-6


def test_hedges_are_evaluated_jointly() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0, 1, 750)
    a = re.SleeveEvidence(name="a", daily_r=0.05 + x, symbol="A", family="fa",
                          forward_days=250, live_days=250)
    b = re.SleeveEvidence(name="b", daily_r=0.05 - 0.9 * x + 0.44 * rng.normal(0, 1, 750),
                          symbol="B", family="fb", forward_days=250, live_days=250)
    alone = re.optimise([a], hard_cap=CAP, cfg=_cfg())
    pair = re.optimise([a, b], hard_cap=CAP, cfg=_cfg())
    assert pair.total_heat > alone.total_heat + 0.01


def test_a_clone_adds_nothing_beyond_world_sampling_noise() -> None:
    ev = _ev([0.15, 0.10])
    clone = re.SleeveEvidence(name="s0c", daily_r=ev[0].daily_r.copy(), symbol="SYM0",
                              family="f0", forward_days=250, live_days=250)
    g1, g2, h1, h2 = [], [], [], []
    for seed in range(3):
        cfg = re.WorldConfig(seed=seed)
        f = re.optimise(ev, hard_cap=CAP, cfg=cfg)
        g = re.optimise([*ev, clone], hard_cap=CAP, cfg=cfg)
        g1.append(f.robust_score)
        g2.append(g.robust_score)
        h1.append(f.heat["s0"])
        h2.append(g.heat["s0"] + g.heat["s0c"])
    # Measured 2026-11-11: seed-to-seed spread of the robust score is ~1.5e-4 and of s0's heat
    # ~0.004 on this pair; a clone must not move the mean beyond twice that band.
    assert abs(np.mean(g2) - np.mean(g1)) < 3e-4
    assert abs(np.mean(h2) - np.mean(h1)) < 0.01
