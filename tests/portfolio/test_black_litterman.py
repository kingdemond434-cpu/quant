"""Black-Litterman challengers (D15) and the allocation perturbation test."""
from __future__ import annotations

import numpy as np
import pytest

from libs.portfolio import black_litterman as bl
from libs.portfolio import perturbation as pt
from libs.portfolio.robust_elog import SleeveEvidence


def _ev(n_obs: int = 400, seed: int = 3) -> list[SleeveEvidence]:
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.3, n_obs)
    mus = (0.04, 0.02, 0.0, -0.01)
    out = []
    for i, mu in enumerate(mus):
        r = mu + 0.5 * common + rng.normal(0, 0.6, n_obs)
        out.append(SleeveEvidence(name=f"s{i}", daily_r=r, n_trials=1 + 50 * i))
    return out


def _labels(n_obs: int) -> list[str]:
    return ["calm" if (d // 40) % 2 == 0 else "stress" for d in range(n_obs)]


def test_no_views_returns_the_prior_and_the_prior_is_the_reference_book_efficient() -> None:
    ev = _ev()
    m, _names, _obs = bl._matrix(ev)
    cov = bl._cov(m)
    w = np.array([0.4, 0.3, 0.2, 0.1])
    pi, delta = bl.equilibrium_prior(m, cov, w)
    assert delta >= 0
    assert np.allclose(pi, delta * cov @ (w / w.sum()))
    assert np.allclose(bl.posterior(pi, cov, 1 / 400, bl.Views.empty(4)), pi)


def test_confident_views_pull_the_posterior_toward_the_sample_and_trials_weaken_them() -> None:
    ev = _ev()
    m, _n, obs = bl._matrix(ev)
    cov = bl._cov(m)
    pi = np.zeros(4)
    c = bl.certified_views(ev, m)
    post = bl.posterior(pi, cov, 1 / obs, c)
    # The posterior moves from the zero prior toward the sample means, never past them.
    sample = m.mean(axis=0)
    assert np.all(np.sign(post[:2]) == np.sign(sample[:2]))
    # Omega grows with ln(n_trials): sleeve 3 was searched for hardest and is believed least.
    assert c.omega[3] / (m[:, 3].var(ddof=1) / obs) > c.omega[0] / (m[:, 0].var(ddof=1) / obs)


def test_world_state_views_use_the_regime_mix_and_the_shuffle_keeps_the_numbers() -> None:
    ev = _ev()
    m, _n, obs = bl._matrix(ev)
    v = bl.regime_views(ev, m, _labels(obs), {"calm": 0.8, "stress": 0.2})
    assert v.Q.size == 4 and np.all(v.omega > 0)
    lab = np.array(_labels(obs))
    want = 0.8 * m[lab == "calm", 0].mean() + 0.2 * m[lab == "stress", 0].mean()
    assert v.Q[0] == pytest.approx(want)
    g = bl.shuffled(v)
    assert sorted(g.Q) == pytest.approx(sorted(v.Q)) and not np.allclose(g.Q, v.Q)
    # No regime information -> no views, never invented ones.
    assert bl.regime_views(ev, m, [], {"calm": 1.0}).Q.size == 0


def test_macro_views_need_an_effective_sample() -> None:
    ev = _ev()
    m, _n, obs = bl._matrix(ev)
    w = np.zeros(obs)
    w[-5:] = 1.0                                   # n_eff 5 < MIN_STATE_DAYS: no view
    thin = [SleeveEvidence(name=e.name, daily_r=e.daily_r, macro_w=w) for e in ev]
    assert bl.macro_views(thin, m).Q.size == 0
    wide = [SleeveEvidence(name=e.name, daily_r=e.daily_r, macro_w=np.ones(obs)) for e in ev]
    v = bl.macro_views(wide, m)
    assert v.Q.size == 4 and v.Q[0] == pytest.approx(m[:, 0].mean())


def test_shift_moves_only_the_location() -> None:
    ev = _ev()
    _m, _n, obs = bl._matrix(ev)
    target = np.array([0.1, 0.2, 0.3, 0.4])
    sh = bl.shifted(ev, target, obs)
    for e, s, t in zip(ev, sh, target, strict=True):
        assert s.daily_r[-obs:].mean() == pytest.approx(t)
        assert s.daily_r.std() == pytest.approx(e.daily_r.std())


def test_all_seven_arms_are_built_at_the_same_total() -> None:
    ev = _ev()
    _m, _n, obs = bl._matrix(ev)

    def solve(e):
        mu = np.array([max(float(x.daily_r.mean()), 0.0) for x in e])
        w = mu / mu.sum() if mu.sum() > 0 else np.ones(len(e)) / len(e)
        return {x.name: 0.2 * float(v) for x, v in zip(e, w, strict=True)}

    books, b = bl.arm_books(ev, 0.2, solve, regime_labels=_labels(obs),
                            regime_probs={"calm": 0.6, "stress": 0.4})
    assert set(books) == set(bl.ARMS)
    for arm, book in books.items():
        assert sum(book.values()) == pytest.approx(0.2, abs=1e-6), arm
        assert all(v >= -1e-12 for v in book.values()), arm
    assert b.n_views["D"] >= 4


def test_book_metrics_on_a_known_path() -> None:
    r = np.array([[0.1, 0.0], [-0.05, 0.0], [0.02, 0.0]])
    m = bl.book_metrics({"a": 0.5, "b": 0.0}, r, ["a", "b"], prev={"a": 0.25, "b": 0.25})
    assert m["log_growth"] == pytest.approx(float(np.log1p(r[:, 0] * 0.5).sum()))
    assert m["turnover"] == pytest.approx(0.5) and m["hhi"] == pytest.approx(1.0)
    assert m["max_drawdown_log"] == pytest.approx(-np.log1p(-0.025))
    ruin = bl.book_metrics({"a": 1.0}, np.array([[-1.5]]), ["a"])
    assert ruin["log_growth"] == float("-inf")


def test_perturbation_measures_instability_against_the_reseed_null() -> None:
    ev = _ev()

    def stable(e, ctx):
        return {x.name: 0.05 for x in e}

    def jumpy(e, ctx):
        mu = [float(x.daily_r.mean()) for x in e]
        k = int(np.argmax(mu))
        return {x.name: (0.2 if i == k else 0.0) for i, x in enumerate(e)}

    out = pt.measure(ev, {"A_allocator": jumpy, "F_mvo": stable}, draws=4,
                     regime_probs=(("calm", 0.7), ("stress", 0.3)), bounds={"s0": 0.1})
    a, f = out["books"]["A_allocator"], out["books"]["F_mvo"]
    assert f["instability"] == 0.0 and f["reseed_null"] == 0.0
    assert set(a["per_class"]) >= {"mu", "covariance", "correlation", "health", "costs",
                                   "probabilities", "capacity"}
    assert a["instability_excess"] >= f["instability_excess"]
    assert out["authority"]["enforced"] is False


def test_distance_is_a_share_of_the_book() -> None:
    assert pt.distance({"a": 0.1}, {"a": 0.1}) == 0.0
    assert pt.distance({"a": 0.1}, {"b": 0.1}) == pytest.approx(1.0)
    assert pt.distance({"a": 0.1, "b": 0.1}, {"a": 0.2}) == pytest.approx(0.5)
