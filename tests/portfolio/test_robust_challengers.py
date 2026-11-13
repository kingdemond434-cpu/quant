"""Shadow challengers (ALLOC-10/16/20/21): DRO log-growth book, disagreement shrink, release
plans, no-trade band calibration and selection/sizing/cost attribution."""
from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio import robust_challengers as rc


def _r(mus, n=500, seed=0, sd=1.0):
    rng = np.random.default_rng(seed)
    return np.array(mus) + rng.normal(0, sd, (n, len(mus)))


def test_max_log_book_is_on_the_simplex_and_prefers_the_better_sleeve() -> None:
    h = rc.max_log_book(_r([0.10, 0.0]), 0.2)
    assert h.sum() == pytest.approx(0.2) and (h >= 0).all() and h[0] > h[1]


def test_dro_book_is_more_cautious_than_nominal_about_thin_evidence() -> None:
    long_ = _r([0.08, 0.08], n=2000, seed=1)
    thin = np.vstack([long_[:, :1].T, np.r_[long_[:60, 1], np.zeros(1940)]]).T
    res = rc.dro_book(thin, 0.2)
    assert res["status"] == "MEASURED"
    assert res["growth_worst_case"] <= res["growth_nominal"] + 1e-12
    assert res["worst_mean"][0] < thin[:, 0].mean()


def test_disagreement_only_shrinks_and_agreement_shrinks_nothing() -> None:
    same = rc.disagreement_shrink({"a": 0.05, "b": 0.05, "c": 0.05}, 0.02)
    assert same["shrink_factor"] == pytest.approx(1.0)
    split = rc.disagreement_shrink({"a": 0.10, "b": -0.05}, 0.02)
    assert 0 < split["shrink_factor"] < 1 and split["sign_agreement"] is False
    assert rc.disagreement_shrink({"a": 0.1}, 0.02)["status"] == "UNMEASURED"


def test_release_plans_follow_the_jump_to_diffusion_ratio() -> None:
    calm = rc.release_decision(0.05, 1.0, 0.0, 12.0)
    assert calm["best"] == "HOLD_THROUGH"
    jumpy = rc.release_decision(0.05, 1.0, 5.0, 12.0)
    assert jumpy["best"] == "FLAT_BEFORE"
    costly = rc.release_decision(0.05, 1.0, 5.0, 12.0, cost=0.05)
    assert costly["best"] == "WAIT" and costly["plans"]["WAIT"] == 0.0


def test_release_jump_var_reads_release_days() -> None:
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, 400)
    m = np.zeros(400, dtype=bool)
    m[::20] = True
    x[m] *= 3.0
    jv = rc.release_jump_var(x, m)
    assert jv["status"] == "MEASURED" and jv["jump_var"] > 2.0


def test_no_trade_band_finds_a_band_when_costs_bite() -> None:
    rng = np.random.default_rng(3)
    r = _r([0.05, 0.05], n=300, seed=4)
    base = np.array([0.1, 0.1])
    targets = base + rng.normal(0, 0.01, (300, 2))           # noise around a stable book
    cheap = rc.no_trade_band(r, targets, 0.0, [0.0, 0.05, 0.2])
    dear = rc.no_trade_band(r, targets, 0.5, [0.0, 0.05, 0.2])
    assert dear["best_band"] > 0.0
    assert dear["curve"]["0.2"]["n_rebalances"] < dear["curve"]["0"]["n_rebalances"]
    assert cheap["status"] == "MEASURED"


def test_rolling_targets_are_causal() -> None:
    r = _r([0.1, 0.0], n=120, seed=5)
    a = rc.rolling_targets(r, 0.2)
    r2 = r.copy()
    r2[100:] = -5.0                                          # the future changes...
    b = rc.rolling_targets(r2, 0.2)
    assert np.allclose(a[:101], b[:101])                     # ...the past targets do not


def test_attribution_splits_selection_sizing_cost() -> None:
    r = _r([0.2, 0.0, -0.2], n=400, seed=6, sd=0.5)
    names = ["good", "flat", "bad"]
    res = rc.attribution(r, names, {"good": 0.15, "flat": 0.05}, names, cost_r=0.06,
                         prev={"good": 0.10})
    assert res["status"] == "MEASURED"
    assert res["selection"] > 0                              # dropping `bad` was right
    assert res["sizing"] > 0                                 # leaning on `good` was right
    assert res["cost"] < 0 and res["turnover"] == pytest.approx(0.10)
    assert res["net_vs_baseline"] == pytest.approx(res["selection"] + res["sizing"]
                                                   + res["cost"])
