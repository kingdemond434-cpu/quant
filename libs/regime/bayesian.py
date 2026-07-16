"""Online Bayesian regime filter -- recursive posterior update, one observation at a time.

Given a fitted HMM's transition matrix + diagonal-Gaussian emissions, this maintains a live belief
P(regime_t | x_1..t) that updates incrementally as each new bar arrives:

    prior_t     = transmat.T @ posterior_{t-1}         (predict step)
    posterior_t ~ prior_t * emission_likelihood(x_t)   (update step)

This is the production hook: the executor can feed the latest bar and get an immediate regime +
confidence without refitting. Confidence = max posterior mass (how sure we are of the state).
"""

from __future__ import annotations

import numpy as np


class BayesianRegimeFilter:
    def __init__(self, transmat: np.ndarray, means: np.ndarray, variances: np.ndarray,
                 startprob: np.ndarray) -> None:
        self.transmat = np.asarray(transmat, dtype="float64")
        self.means = np.asarray(means, dtype="float64")
        self.vars = np.asarray(variances, dtype="float64")
        self.posterior = np.asarray(startprob, dtype="float64").copy()
        self.k = self.transmat.shape[0]

    def _emission(self, x: np.ndarray) -> np.ndarray:
        out = np.empty(self.k)
        for j in range(self.k):
            diff = x - self.means[j]
            log_p = -0.5 * (np.sum(diff * diff / self.vars[j])
                            + np.sum(np.log(2.0 * np.pi * self.vars[j])))
            out[j] = log_p
        out = np.exp(out - out.max())          # stabilise before normalising
        return np.asarray(out, dtype="float64")

    def update(self, x: np.ndarray) -> tuple[int, float]:
        """Push one observation; return (most-likely regime index, confidence = max posterior)."""
        x = np.asarray(x, dtype="float64")
        prior = self.transmat.T @ self.posterior
        post = prior * self._emission(x)
        s = post.sum()
        self.posterior = post / s if s > 0 else np.full(self.k, 1.0 / self.k)
        return int(np.argmax(self.posterior)), float(self.posterior.max())
