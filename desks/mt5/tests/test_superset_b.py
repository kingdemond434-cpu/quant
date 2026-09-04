"""Portfolio superset: challengers, the multi-period planner, latent factors and the four heats,
forecast discipline.

What is pinned:

  * every challenger is long-only and sums to the requested heat; the contest now carries them
    and the dynamic book must beat the best of them;
  * the multi-period planner returns a path whose first step respects the floor and the cap,
    and trade value is growth gained minus turnover cost;
  * the four heats order correctly (independent sleeves: effective << nominal; one latent
    factor: effective ~ nominal), tail dependence is 1 on identical series and drift flags a
    correlation regime change;
  * forecast normalisation puts every signal on the same scale, correlated agreement earns no
    multiplier, and the buffer holds inside the band.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.portfolio import challengers, forecast, latent_factors, multiperiod_worlds  # noqa: E402
from libs.portfolio.allocator_proof import contest  # noqa: E402
from libs.portfolio.robust_elog import SleeveEvidence, WorldConfig, sample_worlds  # noqa: E402


def _evidence(n: int = 5, seed: int = 0, common: float = 0.0) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    f = rng.normal(0, 0.3, 500)
    out = []
    for i in range(n):
        r = 0.02 + common * f + np.sqrt(1 - common ** 2) * rng.normal(0, 0.3, 500)
        out.append(SleeveEvidence(name=f"s{i}", daily_r=r, family=f"f{i}", forward_days=100))
    return out


def test_every_challenger_is_long_only_at_the_requested_heat() -> None:
    ev = _evidence()
    books = challengers.all_books(ev, 0.20)
    assert set(books) == set(challengers.CHALLENGERS)
    for name, b in books.items():
        assert sum(b.values()) == pytest.approx(0.20, abs=1e-9), name
        assert all(v >= 0 for v in b.values()), name


def test_the_contest_carries_the_bench_and_scores_them() -> None:
    ev = _evidence(seed=2)
    cfg = WorldConfig(n_worlds=16, n_rows=64, seed=2)
    worlds = sample_worlds(ev, cfg)
    out = contest(ev, {e.name: 0.04 for e in ev}, cfg=cfg, worlds=worlds)
    assert {"hrp", "kelly", "min_variance", "multiperiod"} <= set(out["books"])
    assert all(k in out["scores"] for k in out["books"])


def test_multiperiod_plan_respects_floor_and_cap_and_values_a_trade() -> None:
    ev = _evidence(seed=3)
    cfg = WorldConfig(n_worlds=16, n_rows=96, seed=3)
    worlds = sample_worlds(ev, cfg)
    mp = multiperiod_worlds.plan(worlds, {}, horizon=3, target=0.20, cap=0.30, cost_r=0.06)
    assert mp["horizon"] == 3 and len(mp["path_total_heat"]) == 3
    assert all(0.20 - 1e-3 <= h <= 0.30 + 1e-9 for h in mp["path_total_heat"])
    assert sum(mp["h_now"].values()) == pytest.approx(mp["path_total_heat"][0], abs=1e-6)
    tv = multiperiod_worlds.trade_value(worlds, {e.name: 0.04 for e in ev},
                                        {e.name: 0.04 for e in ev})
    assert tv["turnover"] == 0.0 and tv["trade_value"] == pytest.approx(0.0)
    tv2 = multiperiod_worlds.trade_value(worlds, {e.name: 0.04 for e in ev},
                                         {"s0": 0.20}, cost_r=0.06)
    assert tv2["turnover"] > 0 and tv2["cost"] == pytest.approx(0.06 * tv2["turnover"])


def test_four_heats_see_the_latent_factor() -> None:
    book = {f"s{i}": 0.04 for i in range(5)}
    indep = latent_factors.effective(_evidence(common=0.0, seed=4), book)
    one_bet = latent_factors.effective(_evidence(common=0.95, seed=4), book)
    assert indep["nominal"] == pytest.approx(0.20) and one_bet["nominal"] == pytest.approx(0.20)
    assert indep["effective"] < 0.12 < 0.17 < one_bet["effective"] <= 0.20 + 1e-6
    assert indep["n_eff"]["covariance"] > 3.5 and one_bet["n_eff"]["factor"] < 1.5
    assert one_bet["factor_explained"] > indep["factor_explained"]
    m = np.column_stack([np.linspace(-1, 1, 300)] * 2)
    assert latent_factors.tail_dependence(m)[0, 1] == pytest.approx(1.0, abs=0.05)


def test_drift_flags_a_correlation_regime_change() -> None:
    rng = np.random.default_rng(5)
    f = rng.normal(0, 1, 400)
    calm = np.column_stack([rng.normal(0, 1, 400) for _ in range(4)])
    stressed = np.column_stack([0.95 * f[-40:] + 0.3 * rng.normal(0, 1, 40) for _ in range(4)])
    m = np.vstack([calm[:-40], stressed])
    assert latent_factors.drift(m, recent=40)["verdict"] == "STRUCTURE_SHIFTED"
    assert latent_factors.drift(calm, recent=40)["verdict"] == "STABLE"


def test_forecast_discipline() -> None:
    rng = np.random.default_rng(6)
    raw = rng.normal(0, 5.0, 2000)
    f = forecast.normalise(raw)
    assert abs(np.nanmean(np.abs(f[500:])) - forecast.TARGET_ABS) < 2.0
    assert np.nanmax(np.abs(f)) <= forecast.CAP
    rho_same = np.ones((3, 3))
    rho_ind = np.eye(3)
    w = np.ones(3)
    assert forecast.diversification_multiplier(rho_same, w) == pytest.approx(1.0)
    assert forecast.diversification_multiplier(rho_ind, w) == pytest.approx(np.sqrt(3))
    assert forecast.buffer(1.0, 1.05, band=0.10) == (1.0, False)
    pos, traded = forecast.buffer(1.0, 1.5, band=0.10)
    assert traded and 1.0 < pos < 1.5
