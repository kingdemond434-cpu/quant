"""A mixture of specialists with soft routing: no hard regime boundary.

    mu(x, z) = sum_k p(k | z) mu_k(x)

Microsoft's TRA routes observations to several predictors by learned pattern; the desk's
version is small and auditable: experts are ridge regressions on the features x, the gate is a
multinomial logistic on the state features z, and the two are fitted by a few rounds of
responsibility-weighted refitting from a k-means start on z. The prediction is the
probability-weighted blend, so a bar that is 60% "London trend" and 40% "high vol" gets 60/40 of
those experts rather than a coin-flip label.

Compared, never assumed: `libs.models.zoo` scores the router against a single ridge on the same
walk-forward folds, with its own complexity tax.
"""
from __future__ import annotations

import numpy as np


def _softmax(a: np.ndarray) -> np.ndarray:
    a = a - a.max(axis=1, keepdims=True)
    e = np.exp(a)
    out: np.ndarray = e / e.sum(axis=1, keepdims=True)
    return out


def _ridge(x: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = (xb * w[:, None]).T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, (xb * w[:, None]).T @ y)
    return out


class ExpertRouter:
    def __init__(self, n_experts: int = 3, lam: float = 5.0, rounds: int = 4,
                 seed: int = 0) -> None:
        self.k = n_experts
        self.lam = lam
        self.rounds = rounds
        self.seed = seed
        self.experts: list[np.ndarray] = []
        self.gate: np.ndarray | None = None
        self.centres: np.ndarray | None = None

    def _kmeans(self, z: np.ndarray) -> np.ndarray:
        rng = np.random.default_rng(self.seed)
        c = z[rng.choice(z.shape[0], self.k, replace=False)]
        for _ in range(20):
            d = ((z[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
            lab = d.argmin(axis=1)
            for j in range(self.k):
                if (lab == j).any():
                    c[j] = z[lab == j].mean(axis=0)
        self.centres = c
        out: np.ndarray = np.asarray(lab)
        return out

    def _gate_fit(self, z: np.ndarray, resp: np.ndarray) -> np.ndarray:
        """Multinomial logistic by a few gradient steps on the responsibilities."""
        zb = np.column_stack([np.ones(z.shape[0]), z])
        w = np.zeros((zb.shape[1], self.k))
        for _ in range(200):
            p = _softmax(zb @ w)
            grad = zb.T @ (p - resp) / z.shape[0] + 1e-3 * w
            w -= 0.5 * grad
        return w

    def fit(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> ExpertRouter:
        lab = self._kmeans(z)
        resp = np.eye(self.k)[lab]
        for _ in range(self.rounds):
            self.experts = [_ridge(x, y, resp[:, j] + 1e-3, self.lam) for j in range(self.k)]
            self.gate = self._gate_fit(z, resp)
            preds = self._expert_preds(x)
            err = (preds - y[:, None]) ** 2
            lik = np.exp(-err / (2 * max(float(err.mean()), 1e-9)))
            resp = _softmax(np.log(np.clip(self._gate_probs(z) * lik, 1e-12, None)))
        return self

    def _expert_preds(self, x: np.ndarray) -> np.ndarray:
        xb = np.column_stack([np.ones(x.shape[0]), x])
        out: np.ndarray = np.column_stack([xb @ w for w in self.experts])
        return out

    def _gate_probs(self, z: np.ndarray) -> np.ndarray:
        assert self.gate is not None
        zb = np.column_stack([np.ones(z.shape[0]), z])
        return _softmax(np.asarray(zb @ self.gate, dtype=float))

    def predict(self, x: np.ndarray, z: np.ndarray) -> np.ndarray:
        p = self._gate_probs(z)
        out: np.ndarray = np.asarray((p * self._expert_preds(x)).sum(axis=1), dtype=float)
        return out

    def responsibilities(self, z: np.ndarray) -> np.ndarray:
        return self._gate_probs(z)
