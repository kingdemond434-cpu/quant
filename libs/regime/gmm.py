"""GMM regime model -- thin wrapper over sklearn's GaussianMixture (already a dependency).

Unlike the HMM, the GMM ignores temporal persistence (no transition matrix); it clusters the feature
space into regimes. Used as an independent second opinion -- when the HMM and GMM agree on the
current regime, confidence is high; when they disagree, the engine flags it.
"""

from __future__ import annotations

import numpy as np
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]


def fit_gmm(x: np.ndarray, *, n_states: int = 3, seed: int = 0) -> GaussianMixture:
    gm = GaussianMixture(n_components=n_states, covariance_type="diag",
                         random_state=seed, n_init=3, reg_covar=1e-4)
    gm.fit(np.asarray(x, dtype="float64"))
    return gm


def gmm_posteriors(gm: GaussianMixture, x: np.ndarray) -> np.ndarray:
    """Per-observation soft regime membership P(state | x_t)."""
    return np.asarray(gm.predict_proba(np.asarray(x, dtype="float64")), dtype="float64")
