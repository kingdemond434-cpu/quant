"""A mixture of specialists with soft routing: no hard regime boundary.

    mu(x, z) = sum_k p(k | z) mu_k(x)

Microsoft's TRA routes observations to several predictors by learned pattern; the desk's
version is small and auditable: experts are ridge regressions on the features x, the gate is a
multinomial logistic on the state features z, and the two are fitted by a few rounds of
responsibility-weighted refitting from a k-means start on z. The prediction is the
probability-weighted blend, so a bar that is 60% "London trend" and 40% "high vol" gets 60/40 of
those experts rather than a coin-flip label.

Two routers live here. `ExpertRouter` is the original: responsibilities are sharpened toward a
label each round (one pooled error scale, so it behaves like a soft k-means on the residuals).
`SoftMoE` is the proper mixture: each expert carries its own noise variance, the E-step is the
exact posterior p(k | x, y, g) = gate_k(g) N(y | expert_k(x), sigma_k^2) / sum, and the gate is
a temperature-controlled softmax, so the blend is a likelihood-weighted average rather than a
vote. The difference matters when regimes overlap: a bar the gate is unsure about is weighted by
which expert actually explains it, not by which centroid it is nearest to.

Compared, never assumed: `libs.models.zoo` scores both routers against a single ridge on the
same walk-forward folds, each with its own complexity tax.
"""
from __future__ import annotations

import numpy as np


def _softmax(a: np.ndarray) -> np.ndarray:
    a = a - a.max(axis=1, keepdims=True)
    e = np.exp(a)
    out: np.ndarray = e / e.sum(axis=1, keepdims=True)
    return out


def _log_softmax(a: np.ndarray) -> np.ndarray:
    """Row-wise log-softmax in log space: no exp overflow, no log(0) on a confident gate."""
    a = a - a.max(axis=1, keepdims=True)
    out: np.ndarray = a - np.log(np.exp(a).sum(axis=1, keepdims=True))
    return out


def _ridge(x: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = (xb * w[:, None]).T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, (xb * w[:, None]).T @ y)
    return out


def _kmeans(z: np.ndarray, k: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Plain Lloyd k-means from a seeded random start; returns (labels, centres).

    Shared by both routers so they start from the SAME partition of the state space: a
    difference in their out-of-sample score is then about the routing rule, not the seed.
    """
    rng = np.random.default_rng(seed)
    c = z[rng.choice(z.shape[0], k, replace=False)]
    lab = np.zeros(z.shape[0], dtype=int)
    for _ in range(20):
        d = ((z[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1)
        for j in range(k):
            if (lab == j).any():
                c[j] = z[lab == j].mean(axis=0)
    return np.asarray(lab), c


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
        lab, self.centres = _kmeans(z, self.k, self.seed)
        return lab

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


class SoftMoE:
    """K ridge experts under a softmax gate with temperature, fitted by EM.

        p(y | x, g) = sum_k gate_k(g) N(y | expert_k(x), sigma_k^2)
        gate(g)     = softmax(W^T [1, g] / tau)

    E-step: r_ik = gate_k(g_i) N(y_i | expert_k(x_i), sigma_k^2) / sum_j (...), computed in log
    space. M-step: a responsibility-weighted ridge per expert, a per-expert residual variance
    (shrunk toward the pooled one, so an expert that grabs three rows cannot declare itself
    noiseless and win every posterior), and a few gradient steps of the multinomial logit gate
    on the responsibilities, warm-started from the previous round.

    WHY A TEMPERATURE: tau < 1 sharpens the gate toward hard routing, tau > 1 blends. The desk
    keeps it a declared parameter rather than a learned one because it is the one knob that
    changes how the model FAILS -- a hard gate misroutes a whole bar, a soft one dilutes every
    expert -- and that choice belongs in the contest, not in the optimiser.

    `expert_usage` is the load-balance diagnostic: mean gate mass per expert on the training
    rows. A mixture whose usage is (0.98, 0.01, 0.01) is a ridge with extra parameters and
    should be taxed out; the zoo reports it so the reader can see why.
    """

    #: Complexity tax in nats per prediction -- MUST equal `libs.models.zoo.TAX["soft_moe"]`;
    #: a test pins the two together so the declaration cannot drift from the contest.
    tax: float = 0.002

    def __init__(self, n_experts: int = 3, lam: float = 5.0, tau: float = 1.0,
                 rounds: int = 6, gate_steps: int = 150, gate_lr: float = 0.5,
                 seed: int = 0) -> None:
        self.k = n_experts
        self.lam = lam
        self.tau = max(float(tau), 1e-3)
        self.rounds = rounds
        self.gate_steps = gate_steps
        self.gate_lr = gate_lr
        self.seed = seed
        self.experts: list[np.ndarray] = []
        self.sigma2: np.ndarray | None = None
        self.gate: np.ndarray | None = None
        self.g_mu: np.ndarray | None = None
        self.g_sd: np.ndarray | None = None
        self.log_likelihood: float = float("nan")
        self._usage: np.ndarray | None = None

    # ----------------------------------------------------------------- gating features
    @staticmethod
    def _as_2d(g: np.ndarray) -> np.ndarray:
        g = np.asarray(g, dtype=float)
        return g.reshape(g.shape[0], -1) if g.ndim == 1 else g

    def _gz(self, g: np.ndarray) -> np.ndarray:
        """Gating features standardised by the training moments, with an intercept column.

        The gate is fitted by plain gradient steps, whose step size only makes sense on
        unit-scale inputs; standardising here means a raw regime score and a z-scored one route
        identically.
        """
        assert self.g_mu is not None and self.g_sd is not None
        gs = np.nan_to_num((self._as_2d(g) - self.g_mu) / self.g_sd)
        return np.column_stack([np.ones(gs.shape[0]), gs])

    def _gate_logits(self, gb: np.ndarray) -> np.ndarray:
        assert self.gate is not None
        out: np.ndarray = np.asarray(gb @ self.gate, dtype=float) / self.tau
        return out

    def _gate_fit(self, gb: np.ndarray, resp: np.ndarray, w: np.ndarray) -> np.ndarray:
        """Multinomial logit on the responsibilities; cross-entropy gradient through tau."""
        n = gb.shape[0]
        for _ in range(self.gate_steps):
            p = _softmax(gb @ w / self.tau)
            grad = gb.T @ (p - resp) / (n * self.tau) + 1e-3 * w
            w = w - self.gate_lr * grad
        return w

    # ------------------------------------------------------------------------ experts
    def _expert_preds(self, x: np.ndarray) -> np.ndarray:
        xb = np.column_stack([np.ones(x.shape[0]), x])
        out: np.ndarray = np.column_stack([xb @ w for w in self.experts])
        return out

    # ------------------------------------------------------------------------------ EM
    def fit(self, x: np.ndarray, y: np.ndarray, g: np.ndarray | None = None) -> SoftMoE:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        graw = self._as_2d(x if g is None else g)
        self.g_mu = graw.mean(axis=0)
        sd = graw.std(axis=0)
        self.g_sd = np.where(sd > 0, sd, 1.0)
        gb = self._gz(graw)
        lab, _ = _kmeans(gb[:, 1:], self.k, self.seed)
        resp = np.eye(self.k)[lab]
        w = np.zeros((gb.shape[1], self.k))
        pooled_floor = max(float(np.var(y)) * 1e-4, 1e-12)
        for _ in range(self.rounds):
            # M-step: experts, their noise scales, then the gate.
            wts = resp + 1e-3
            self.experts = [_ridge(x, y, wts[:, j], self.lam) for j in range(self.k)]
            err2 = (self._expert_preds(x) - y[:, None]) ** 2
            pooled = max(float((wts * err2).sum() / wts.sum()), pooled_floor)
            n0 = 2.0                                  # pseudo-rows of the pooled variance
            self.sigma2 = ((wts * err2).sum(axis=0) + n0 * pooled) / (wts.sum(axis=0) + n0)
            self.sigma2 = np.maximum(self.sigma2, pooled_floor)
            w = self._gate_fit(gb, resp, w)
            self.gate = w
            # E-step: exact posterior over experts, in log space.
            log_lik = -0.5 * np.log(2 * np.pi * self.sigma2)[None, :] \
                - err2 / (2 * self.sigma2[None, :])
            logp = _log_softmax(self._gate_logits(gb)) + log_lik
            resp = _softmax(logp)
            m = logp.max(axis=1, keepdims=True)
            self.log_likelihood = float(np.mean(m[:, 0] + np.log(np.exp(logp - m).sum(axis=1))))
        self._usage = self.gates(graw).mean(axis=0)
        return self

    # ------------------------------------------------------------------------- reading
    def gates(self, g: np.ndarray) -> np.ndarray:
        """p(k | g): the routing probabilities, one row per observation."""
        return _softmax(self._gate_logits(self._gz(g)))

    def predict(self, x: np.ndarray, g: np.ndarray | None = None) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        p = self.gates(x if g is None else g)
        out: np.ndarray = np.asarray((p * self._expert_preds(x)).sum(axis=1), dtype=float)
        return out

    def expert_usage(self) -> np.ndarray:
        """Mean gate mass per expert on the training rows (sums to 1): the load-balance read."""
        assert self._usage is not None, "fit first"
        return self._usage

    def responsibilities(self, x: np.ndarray, y: np.ndarray,
                         g: np.ndarray | None = None) -> np.ndarray:
        """The posterior p(k | x, y, g) for labelled rows -- which expert explained each bar."""
        assert self.sigma2 is not None
        x = np.asarray(x, dtype=float)
        err2 = (self._expert_preds(x) - np.asarray(y, dtype=float)[:, None]) ** 2
        log_lik = -0.5 * np.log(2 * np.pi * self.sigma2)[None, :] \
            - err2 / (2 * self.sigma2[None, :])
        return _softmax(_log_softmax(self._gate_logits(self._gz(x if g is None else g)))
                        + log_lik)
