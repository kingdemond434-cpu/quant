"""Self-contained Gaussian HMM (diagonal emissions) -- no external HMM dependency.

Implements Baum-Welch EM (fit), Viterbi (most-likely path), and the online forward filter
(P(state_t | x_1..t)) in log-space via scipy.special.logsumexp. hmmlearn is not installed and a
small, audited implementation is preferable to a heavy dependency for a 2-3 state market regime.
"""

from __future__ import annotations

import numpy as np
from scipy.special import logsumexp


class GaussianHMM:
    """Diagonal-covariance Gaussian Hidden Markov Model fit by EM."""

    def __init__(self, n_states: int = 3, *, n_iter: int = 60, seed: int = 0,
                 reg: float = 1e-4) -> None:
        self.k = n_states
        self.n_iter = n_iter
        self.seed = seed
        self.reg = reg
        self.startprob: np.ndarray = np.full(n_states, 1.0 / n_states)
        self.transmat: np.ndarray = np.full((n_states, n_states), 1.0 / n_states)
        self.means: np.ndarray = np.zeros((n_states, 1))
        self.vars: np.ndarray = np.ones((n_states, 1))

    def _log_emission(self, x: np.ndarray) -> np.ndarray:
        n = x.shape[0]
        le = np.empty((n, self.k))
        for j in range(self.k):
            diff = x - self.means[j]
            le[:, j] = -0.5 * (np.sum(diff * diff / self.vars[j], axis=1)
                               + np.sum(np.log(2.0 * np.pi * self.vars[j])))
        return le

    def _init(self, x: np.ndarray) -> None:
        rng = np.random.RandomState(self.seed)
        n = x.shape[0]
        idx = rng.choice(n, self.k, replace=False)
        self.means = x[idx].astype("float64").copy()
        self.vars = np.tile(x.var(axis=0) + self.reg, (self.k, 1))
        self.startprob = np.full(self.k, 1.0 / self.k)
        self.transmat = np.full((self.k, self.k), 1.0 / self.k)

    def _forward_backward(self, le: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_beta = np.zeros((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        for t in range(n - 2, -1, -1):
            log_beta[t] = logsumexp(lt + le[t + 1][None, :] + log_beta[t + 1][None, :], axis=1)
        return log_alpha, log_beta

    def fit(self, x: np.ndarray) -> GaussianHMM:
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        self._init(x)
        n = x.shape[0]
        lt = np.log(self.transmat + 1e-300)
        for _ in range(self.n_iter):
            le = self._log_emission(x)
            log_alpha, log_beta = self._forward_backward(le)
            log_gamma = log_alpha + log_beta
            log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
            gamma = np.exp(log_gamma)
            lt = np.log(self.transmat + 1e-300)
            log_xi = (log_alpha[:-1, :, None] + lt[None, :, :]
                      + le[1:, None, :] + log_beta[1:, None, :])
            log_xi -= logsumexp(log_xi.reshape(n - 1, -1), axis=1)[:, None, None]
            xi = np.exp(log_xi)
            self.startprob = gamma[0] / (gamma[0].sum() + 1e-12)
            denom = xi.sum(axis=0).sum(axis=1, keepdims=True) + 1e-12
            self.transmat = xi.sum(axis=0) / denom
            for j in range(self.k):
                w = gamma[:, j]
                sw = w.sum() + 1e-9
                self.means[j] = (w[:, None] * x).sum(axis=0) / sw
                diff = x - self.means[j]
                self.vars[j] = (w[:, None] * diff * diff).sum(axis=0) / sw + self.reg
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Viterbi most-likely state path."""
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        le = self._log_emission(x)
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        delta = np.empty((n, self.k))
        psi = np.zeros((n, self.k), dtype="int64")
        delta[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            m = delta[t - 1][:, None] + lt
            psi[t] = np.argmax(m, axis=0)
            delta[t] = le[t] + np.max(m, axis=0)
        states = np.empty(n, dtype="int64")
        states[-1] = int(np.argmax(delta[-1]))
        for t in range(n - 2, -1, -1):
            states[t] = psi[t + 1, states[t + 1]]
        return states

    def filter_posterior(self, x: np.ndarray) -> np.ndarray:
        """Online forward posterior P(state_t | x_1..t), normalised per t -- the Bayesian filter."""
        x = np.asarray(x, dtype="float64")
        if x.ndim == 1:
            x = x[:, None]
        le = self._log_emission(x)
        n = le.shape[0]
        lt = np.log(self.transmat + 1e-300)
        log_alpha = np.empty((n, self.k))
        log_alpha[0] = np.log(self.startprob + 1e-300) + le[0]
        for t in range(1, n):
            log_alpha[t] = le[t] + logsumexp(log_alpha[t - 1][:, None] + lt, axis=0)
        post = np.exp(log_alpha - logsumexp(log_alpha, axis=1, keepdims=True))
        return np.asarray(post, dtype="float64")
