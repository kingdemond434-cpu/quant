"""The soft mixture of experts, the contrastive market representation and the DoubleAdapt
adapter, each proven against the thing it claims to beat.

What is pinned:

  * on a two-regime stream (y = +x in A, y = -x in B, regime readable from a gating feature)
    SoftMoE beats a single ridge out of sample by a wide margin, its gates put > 0.8 of their
    mass on the right expert in each regime, and expert usage is a distribution;
  * the model's declared tax equals the zoo's entry, and the zoo runs both new models through
    walk_forward / compete like any other challenger;
  * on a series whose forward return depends on a hidden sign state written into the window,
    with rare spike-and-reverse bars owning the variance, the contrastive embedding forecasts
    the forward return better than PCA on the same rows and better than the raw last bars,
    and two augmented views of one window are nearer each other than a window is to a stranger;
  * on a stream whose linear relation rotates every 150 rows, DoubleAdapt's walk-forward MSE
    beats a static ridge and beats SlowFast alone, and the drift report moves the rotating
    features more than the stable one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from libs.models import zoo  # noqa: E402
from libs.models.adapter import DoubleAdapt  # noqa: E402
from libs.models.embedding import (  # noqa: E402
    ContrastiveEncoder,
    WindowPCA,
    representation_gain,
    windows_from_series,
)
from libs.models.router import SoftMoE  # noqa: E402
from libs.regime.drift import SlowFast  # noqa: E402


def _ridge(x: np.ndarray, y: np.ndarray, lam: float = 10.0) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = xb.T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    return np.linalg.solve(a, xb.T @ y)


def _mse(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


# --------------------------------------------------------------------------- soft moe
def _two_regimes(n: int = 2000, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray,
                                                       np.ndarray]:
    rng = np.random.default_rng(seed)
    g = rng.normal(size=(n, 1))                       # the gating feature; regime = its sign
    regime = g[:, 0] > 0
    x = rng.normal(size=(n, 3))
    y = np.where(regime, x[:, 0], -x[:, 0]) + 0.3 * rng.normal(size=n)
    return x, y, g, regime


def test_soft_moe_beats_ridge_and_its_gates_track_the_regime() -> None:
    x, y, g, regime = _two_regimes()
    tr, te = slice(0, 1400), slice(1400, None)
    moe = SoftMoE(n_experts=2).fit(x[tr], y[tr], g[tr])
    mse_moe = _mse(moe.predict(x[te], g[te]), y[te])
    beta = _ridge(x[tr], y[tr])
    mse_ridge = _mse(np.column_stack([np.ones(600), x[te]]) @ beta, y[te])
    assert mse_moe < 0.3 * mse_ridge, (mse_moe, mse_ridge)      # a wide margin, not a nudge
    # The expert with the positive slope on x0 is regime A's; the gate must send A there.
    k_a = int(np.argmax([w[1] for w in moe.experts]))
    gates = moe.gates(g[te])
    assert gates[regime[te], k_a].mean() > 0.8
    assert gates[~regime[te], 1 - k_a].mean() > 0.8
    usage = moe.expert_usage()
    assert usage.shape == (2,) and abs(usage.sum() - 1.0) < 1e-9 and (usage > 0.2).all()
    resp = moe.responsibilities(x[te], y[te], g[te])
    assert np.allclose(resp.sum(axis=1), 1.0)
    assert np.isfinite(moe.log_likelihood)
    # g defaults to x: still fits, still a distribution over experts.
    p_default = SoftMoE(n_experts=2, rounds=2).fit(x[tr], y[tr]).predict(x[te])
    assert p_default.shape == (600,) and np.isfinite(p_default).all()


def test_declared_taxes_match_the_zoo_and_the_zoo_runs_both_models() -> None:
    assert SoftMoE.tax == zoo.TAX["soft_moe"]
    assert DoubleAdapt.tax == zoo.TAX["double_adapt"]
    assert zoo.TAX["soft_moe"] > zoo.TAX["router"] > zoo.TAX["ridge_sign"]
    assert zoo.TAX["double_adapt"] >= zoo.TAX["mlp"]
    x, y, g, _ = _two_regimes(n=900, seed=3)
    y_sign = (y > 0).astype(float)
    res = zoo.compete(x, y_sign, models=("ridge_sign", "soft_moe", "double_adapt"), z=g)
    for name in ("ridge_sign", "soft_moe", "double_adapt"):
        r = res["results"][name]
        assert r["folds"] >= 3 and r["tax"] == zoo.TAX[name], r
        assert r["verdict"] in ("EARNS_ITS_PLACE", "TAXED_OUT")
        assert abs(r["net_gain"] - (r["gain"] - r["tax"])) < 1e-6
    # A regime-conditional sign is exactly what a gated mixture is for; ridge cannot see it.
    assert res["results"]["soft_moe"]["verdict"] == "EARNS_ITS_PLACE"
    assert res["winner"] == "soft_moe"


# ------------------------------------------------------------------------ contrastive
def _hidden_state_series(n: int = 3000, seed: int = 0, mu: float = 0.5, flip: int = 60,
                         spike_p: float = 0.03, spike: float = 8.0) -> tuple[np.ndarray,
                                                                             np.ndarray]:
    """Returns with a persistent hidden sign state (drift +-mu) and rare spike-and-reverse bars
    that own the variance but carry no forward information."""
    rng = np.random.default_rng(seed)
    s = np.ones(n)
    state = 1.0
    for t in range(n):
        if rng.random() < 1.0 / flip:
            state = -state
        s[t] = state
    r = mu * s + rng.normal(size=n)
    j = spike * rng.normal(size=n) * (rng.random(n) < spike_p)
    r = r + j - np.r_[0.0, j[:-1]]
    return r, s


def _windows_and_forward(window: int = 16, horizon: int = 4) -> tuple[np.ndarray, np.ndarray]:
    r, _ = _hidden_state_series()
    w = windows_from_series(r, window)
    n_w = w.shape[0] - horizon
    fwd = np.array([r[i + window: i + window + horizon].sum() for i in range(n_w)])
    return w[:n_w], fwd


def test_windows_from_series_are_causal_and_shaped() -> None:
    x = np.arange(40, dtype=float).reshape(20, 2)
    w = windows_from_series(x, 5)
    assert w.shape == (16, 5, 2)
    assert np.array_equal(w[-1], x[-5:]) and np.array_equal(w[0], x[:5])
    assert windows_from_series(np.arange(10.0), 4).shape == (7, 4, 1)


def test_contrastive_representation_beats_pca_and_the_raw_bars() -> None:
    w, fwd = _windows_and_forward()
    pca = representation_gain(w, fwd, encoder=WindowPCA(dim=4))
    con = representation_gain(w, fwd, encoder=ContrastiveEncoder(dim=4, steps=200))
    assert pca["folds"] == con["folds"] == 4
    # PCA's components are the spike shapes: no forecast value. The contrastive embedding
    # reads the drift the whole window carries, which the last bar alone cannot.
    assert con["embedding"] > 0.05
    assert con["embedding"] > pca["embedding"] + 0.05, (con["embedding"], pca["embedding"])
    assert con["gain"] > 0 and con["gain"] > pca["gain"]
    assert con["verdict"] == "ADMIT"
    assert all(f["embedding"] > f["raw"] for f in con["per_fold"])
    signed = representation_gain(w, fwd, encoder=ContrastiveEncoder(dim=4, steps=200),
                                 score="sign")
    assert signed["score"] == "sign" and signed["gain"] > 0


def test_two_views_of_one_window_are_closer_than_strangers() -> None:
    w, fwd = _windows_and_forward()
    enc = ContrastiveEncoder(dim=4, steps=200).fit(w)
    assert enc.w is not None and enc.w.shape == (16, 4)
    assert enc.loss_path[-1] < enc.loss_path[0]
    assert 0 < enc.alignment <= 1.0
    rng = np.random.default_rng(1)
    flat = enc._prepare(w[:500])
    v1 = enc.augment(flat, rng) @ enc.w
    v2 = enc.augment(flat, rng) @ enc.w
    v1 /= np.linalg.norm(v1, axis=1, keepdims=True)
    v2 /= np.linalg.norm(v2, axis=1, keepdims=True)
    pos = (v1 * v2).sum(axis=1)
    neg = (v1 * v2[rng.permutation(500)]).sum(axis=1)
    assert pos.mean() > neg.mean() + 0.3
    assert (pos > neg).mean() > 0.75
    z = enc.embed(w)
    assert z.shape == (w.shape[0], 4) and np.allclose(np.linalg.norm(z, axis=1), 1.0)
    stats = enc.nn_forward_stats(z[-1], z[:-1], fwd[:-1], k=10, exclude_last=3)
    assert stats["k"] == 10 and set(stats["forward"]) >= {"mean", "p10", "p90", "p_positive"}
    assert max(stats["indices"]) < w.shape[0] - 1 - 3


# ----------------------------------------------------------------------- double adapt
def _rotating_stream(n: int = 1800, seed: int = 0, period: int = 150,
                     noise: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """beta_0, beta_1 rotate by 120 degrees every `period` rows; beta_2 = 0.8 never moves."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, 3))
    phi = (np.arange(n) // period) * (2 * np.pi / 3)
    y = np.cos(phi) * x[:, 0] + np.sin(phi) * x[:, 1] + 0.8 * x[:, 2] \
        + noise * rng.normal(size=n)
    return x, y


def _walk_forward(window: int = 40, n_tr: int = 900, step: int = 30) -> tuple[float, float,
                                                                             float, DoubleAdapt]:
    x, y = _rotating_stream()
    beta = _ridge(x[:n_tr], y[:n_tr])
    sf = SlowFast(recent=window).fit(x[:n_tr], y[:n_tr])
    da = DoubleAdapt().fit(x[:n_tr], y[:n_tr], window=window)
    e_ridge, e_sf, e_da = [], [], []
    for t in range(n_tr, x.shape[0] - step + 1, step):
        xr, yr = x[t - window: t], y[t - window: t]
        xn, yn = x[t: t + step], y[t: t + step]
        e_ridge.append(_mse(np.column_stack([np.ones(step), xn]) @ beta, yn))
        sf.adapt(xr, yr)
        e_sf.append(_mse(sf.predict(xn), yn))
        e_da.append(_mse(da.predict(xr, yr, xn), yn))
    return float(np.mean(e_ridge)), float(np.mean(e_sf)), float(np.mean(e_da)), da


def test_double_adapt_beats_static_ridge_and_slowfast_alone() -> None:
    ridge, slowfast, double, da = _walk_forward()
    assert slowfast < ridge                                  # adapting at all helps
    assert double < 0.97 * slowfast, (double, slowfast)      # and adapting THIS way helps more
    assert double < 0.8 * ridge
    assert da.meta["tasks"] > 10 and da.meta["helped"] > da.meta["tasks"] // 2
    assert da.meta["lam_fast"] in da.fast_grid and da.meta["recency"] in da.recency_grid
    assert da.meta["recency"] is not None                    # a turning stream wants recency


def test_drift_report_moves_the_rotating_features_more_than_the_stable_one() -> None:
    _, _, _, da = _walk_forward()
    rep = da.drift_report()
    move = rep["from_identity"]
    assert rep["n"] == da.meta["tasks"] + 30 and len(move) == 3
    # Both rotating features move more than the stable one; the most-moved by a clear factor.
    assert min(move[0], move[1]) > 1.2 * move[2], move
    assert max(move[0], move[1]) > 1.8 * move[2], move
    assert rep["most_moved"] in (0, 1) and rep["least_moved"] == 2
    assert rep["ratio_max_min"] > 1.5
    assert len(rep["from_init"]) == 3 and all(v >= 0 for v in rep["from_init"])
    assert DoubleAdapt().drift_report()["verdict"] == "UNMEASURED"


def test_double_adapt_shapes_and_window_clamp() -> None:
    x, y = _rotating_stream(n=200, seed=2)
    da = DoubleAdapt().fit(x, y, window=500)                # asked for more than half the rows
    assert da.window == 100
    p = da.predict(x[-40:], y[-40:], x[-5:])
    assert p.shape == (5,) and np.isfinite(p).all()
    a, b, sf = da.adapt(x[-40:], y[-40:])
    assert a.shape == b.shape == (3,) and sf.fast is not None and sf.slow is not None
