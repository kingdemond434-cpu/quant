"""Tests for the probabilistic regime engine (HMM / GMM / Bayesian filter)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from libs.regime.engine import RegimeEngine
from libs.regime.features import regime_features
from libs.regime.gmm import fit_gmm, gmm_posteriors
from libs.regime.hmm import GaussianHMM


def _two_regime_series(seed: int = 0) -> pd.Series:
    rng = np.random.RandomState(seed)
    calm_bull = rng.normal(0.0012, 0.005, 200)     # low vol, positive drift
    vol_bear = rng.normal(-0.002, 0.03, 200)       # high vol, negative drift
    ret = np.concatenate([calm_bull, vol_bear])
    return pd.Series(100.0 * np.cumprod(1.0 + ret))


def test_hmm_separates_the_two_regimes() -> None:
    x, _ = regime_features(_two_regime_series(), vol_window=20)
    hmm = GaussianHMM(n_states=2, seed=1).fit(x)
    states = hmm.predict(x)
    first_half = np.bincount(states[:200], minlength=2).argmax()
    second_half = np.bincount(states[220:], minlength=2).argmax()
    assert first_half != second_half          # calm and volatile halves get different states


def test_hmm_posterior_normalised() -> None:
    x, _ = regime_features(_two_regime_series(), vol_window=20)
    post = GaussianHMM(n_states=3, seed=0).fit(x).filter_posterior(x)
    assert np.allclose(post.sum(axis=1), 1.0)
    assert (post >= -1e-9).all()


def test_engine_current_has_bounded_multiplier() -> None:
    eng = RegimeEngine(n_states=3, seed=0).fit(_two_regime_series())
    cur = eng.current()
    assert "/" in str(cur["regime"])
    assert 0.0 <= float(cur["confidence"]) <= 1.0
    assert 0.2 <= float(cur["leverage_multiplier"]) <= 1.0
    assert cur["trend"] in ("bull", "bear")
    assert cur["vol_tier"] in ("low_vol", "mid_vol", "high_vol")


def test_high_vol_regime_gets_lower_leverage() -> None:
    eng = RegimeEngine(n_states=3, seed=0).fit(_two_regime_series())
    levs = {c["vol_tier"]: c["leverage_multiplier"] for c in eng.hmm_char.values()}
    if "high_vol" in levs and "low_vol" in levs:
        assert float(levs["high_vol"]) <= float(levs["low_vol"])   # de-risk in high vol


def test_bayesian_filter_updates() -> None:
    x, _ = regime_features(_two_regime_series(), vol_window=20)
    eng = RegimeEngine(n_states=3, seed=0).fit(_two_regime_series())
    filt = eng.make_filter()
    reg, conf = filt.update(x[-1])
    assert 0 <= reg < 3
    assert 0.0 <= conf <= 1.0


def test_gmm_posteriors_sum_to_one() -> None:
    x, _ = regime_features(_two_regime_series(), vol_window=20)
    gm = fit_gmm(x, n_states=3, seed=0)
    p = gmm_posteriors(gm, x)
    assert np.allclose(p.sum(axis=1), 1.0)
