"""The shared Hawkes module: exact likelihood, parameter recovery (scipy and fallback), PIT
intensity, time-rescaling goodness of fit and Ogata simulation. Synthetic only."""
from __future__ import annotations

import math

import numpy as np
import pytest

from libs.models.classical_baselines import HawkesIntensity
from libs.quant_models import hawkes as h


def _brute_loglik(p: h.HawkesParams, t: np.ndarray, k: np.ndarray, t_end: float) -> float:
    ll = 0.0
    for i in range(t.size):
        lam = p.mu[k[i]] + sum(p.alpha[k[i], k[j]] * math.exp(-p.beta * (t[i] - t[j]))
                               for j in range(i))
        ll += math.log(lam)
    comp = p.mu.sum() * t_end + sum(p.alpha[:, k[j]].sum() / p.beta
                                    * (1 - math.exp(-p.beta * (t_end - t[j])))
                                    for j in range(t.size))
    return float(ll - comp)


def test_loglik_matches_brute_force() -> None:
    p = h.HawkesParams(np.array([0.3, 0.2]), np.array([[0.4, 0.1], [0.2, 0.3]]), 1.3)
    t, k = h.simulate(p, 60.0, seed=3)
    assert t.size > 10
    assert h.log_likelihood(p, t, 60.0, k) == pytest.approx(_brute_loglik(p, t, k, 60.0),
                                                           rel=1e-10)


@pytest.mark.parametrize("use_scipy", [True, False])
def test_univariate_recovery(use_scipy: bool) -> None:
    true = h.HawkesParams.univariate(0.5, 0.8, 1.2)
    t, _ = h.simulate(true, 3000.0, seed=1)
    f = h.fit(t, t0=0.0, t_end=3000.0, use_scipy=use_scipy)
    assert isinstance(f, h.HawkesFit)
    assert f.params.branching_ratio == pytest.approx(true.branching_ratio, abs=0.07)
    assert f.params.beta == pytest.approx(1.2, rel=0.2)
    assert f.params.mu[0] == pytest.approx(0.5, rel=0.15)
    assert f.lr_stat > 50
    assert f.loglik == pytest.approx(h.log_likelihood(f.params, t, 3000.0), rel=1e-9)


def test_scipy_and_fallback_agree_multivariate() -> None:
    true = h.HawkesParams(np.array([0.2, 0.3]), np.array([[0.5, 0.3], [0.0, 0.6]]), 1.5)
    t, k = h.simulate(true, 2500.0, seed=2)
    a = h.fit(t, marks=k, t0=0.0, t_end=2500.0)
    b = h.fit(t, marks=k, t0=0.0, t_end=2500.0, use_scipy=False)
    assert isinstance(a, h.HawkesFit) and isinstance(b, h.HawkesFit)
    assert a.loglik == pytest.approx(b.loglik, abs=0.05)
    np.testing.assert_allclose(a.params.alpha, true.alpha, atol=0.15)
    assert a.params.beta == pytest.approx(1.5, rel=0.2)
    assert a.params.branching_ratio < 1.0


def test_poisson_has_no_branching() -> None:
    rng = np.random.default_rng(5)
    t = np.sort(rng.uniform(0, 2000, 1500))
    f = h.fit(t, t0=0.0, t_end=2000.0)
    assert isinstance(f, h.HawkesFit)
    assert f.params.branching_ratio < 0.08
    assert f.lr_stat < 10


def test_intensity_uses_only_strictly_prior_events() -> None:
    p = h.HawkesParams.univariate(0.1, 1.0, 2.0)
    t = np.array([1.0, 2.0, 5.0])
    lam = h.intensity_at(p, t, [1.0, 1.0 + 1e-12, 5.0, 6.0])[:, 0]
    assert lam[0] == pytest.approx(0.1)
    assert lam[1] == pytest.approx(1.1, rel=1e-6)
    expect5 = 0.1 + math.exp(-2 * 4) + math.exp(-2 * 3)
    assert lam[2] == pytest.approx(expect5)
    # appending a FUTURE event never changes a past value
    lam2 = h.intensity_at(p, np.append(t, 5.5), [1.0, 5.0])[:, 0]
    assert lam2[1] == pytest.approx(lam[2])


def test_goodness_of_fit_accepts_truth_and_rejects_poisson() -> None:
    true = h.HawkesParams.univariate(0.4, 1.0, 1.4)
    t, _ = h.simulate(true, 2000.0, seed=9)
    good = h.goodness_of_fit(true, t)
    bad = h.goodness_of_fit(h.HawkesParams.univariate(t.size / 2000.0, 0.0, 1.0), t)
    assert good["ks_p"] > 0.01
    assert bad["ks_p"] < 1e-6
    res = h.time_rescaling_residuals(true, t)[0]
    assert res.mean() == pytest.approx(1.0, abs=0.08)


def test_too_few_events_is_unmeasured() -> None:
    out = h.fit([1.0, 2.0], min_events=10)
    assert isinstance(out, dict) and out["status"] == "UNMEASURED"


def test_classical_baseline_delegates() -> None:
    m = HawkesIntensity().fit([0.0, 1.0, 1.5, 3.0, 3.2, 6.0])
    assert m.state["verdict"] == "MEASURED"
    assert m.state["method"] in ("lbfgsb_analytic_gradient", "em_profile_golden")
