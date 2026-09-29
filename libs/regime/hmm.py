"""Self-contained Gaussian HMM (diagonal emissions) -- no external HMM dependency.

Implements Baum-Welch EM (fit), Viterbi (most-likely path), and the online forward filter
(P(state_t | x_1..t)) in log-space via `logsumexp` below (scipy's algorithm, bit-identical).
hmmlearn is not installed and a small, audited implementation is preferable to a heavy
dependency for a 2-3 state market regime.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def logsumexp(a: np.ndarray, axis: int = 0, keepdims: bool = False) -> Any:
    """`scipy.special.logsumexp` for a real float64 array, BIT-IDENTICAL, without its dispatch.

    WHY THIS EXISTS (measured 2026-09-29, `desks/mt5/tests/test_judging_speed_equivalence.py`).
    The forward-backward recursion calls logsumexp once per bar per EM iteration on a (k, k)
    array. scipy 1.17 routes every call through the array-API layer (namespace detection, dtype
    promotion, `at[].set` emulation, `isdtype` checks), which cost ~180 us per call against a few
    microseconds of arithmetic -- 82% of the sealed gauntlet's build time on a docket sample,
    because every `regime_transition` cell (and every `exit_operated` cell wrapping one) fits
    60-iteration HMMs over thousands of days.

    This is scipy's own algorithm, operation for operation and in the same order, for the only
    case this module uses (real float64, no `b`, no `return_sign`): the same max-shift, the same
    exclusion of the arg-max elements from the shifted sum, the same `log1p(s) + log(m) + max`,
    and the same fallback to `log(sum(exp(a)))` where that is non-finite. The test pins it
    bit-for-bit against scipy on random inputs including -inf, +inf and NaN rows.
    """
    a = np.asarray(a, dtype="float64")
    if a.ndim == 0:
        a = a.reshape(1)
    if np.isfinite(a).all():
        # THE ALL-FINITE CASE, which is every call the recursion makes on a well-posed model: the
        # same operations as below with the branches that cannot fire removed. With every element
        # finite the max is finite, at least one element equals it (m >= 1), the shifted sum is
        # >= 0 (so the sign is +1, `s < -1` is false and `s == 0` gives the same 0 as `s / m`),
        # and the only way out is non-finite is an overflow at the top of the float range --
        # which drops through to the general path, so that case is answered identically too.
        a_max = np.maximum.reduce(a, axis=axis, keepdims=True)
        i_max = a == a_max
        m = np.add.reduce(i_max.astype(a.dtype), axis=axis, keepdims=True, dtype=a.dtype)
        s = np.add.reduce(np.exp(np.where(i_max, -np.inf, a) - a_max), axis=axis,
                          keepdims=True, dtype=a.dtype) / m
        out = np.log1p(s) + np.log(m) + a_max
        if np.isfinite(out).all():
            if not keepdims:
                out = np.squeeze(out, axis=axis)
            return out[()] if out.ndim == 0 else out
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        out_inf = np.log(np.sum(np.exp(a), axis=axis, keepdims=True))
        a_max = np.max(a, axis=axis, keepdims=True)
        i_max = a == a_max
        shifted = a.copy()
        shifted[i_max] = -np.inf
        m = np.sum(i_max.astype(a.dtype), axis=axis, keepdims=True, dtype=a.dtype)
        s = np.sum(np.exp(shifted - a_max), axis=axis, keepdims=True, dtype=a.dtype)
        s = np.where(s == 0, s, s / m)
        sgn = np.sign(s + 1) * np.sign(m)
        s = np.where(s < -1, -s - 2, s)
        m = np.abs(m)
        out = np.log1p(s) + np.log(m) + a_max
        out[sgn < 0] = np.nan
    out = np.where(np.isfinite(out), out, out_inf)
    if not keepdims:
        out = np.squeeze(out, axis=axis)
    return out[()] if out.ndim == 0 else out


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
