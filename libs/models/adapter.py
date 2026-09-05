"""DoubleAdapt: move the data toward the model AND the model toward the data, and meta-learn
how far each should go from what adapted well last time.

    theta   = theta_slow + delta              MODEL adapter: SlowFast's fast ridge on the window
    x'      = a * x + b                       DATA adapter, per feature, from a meta-learned init
    y_hat   = [1, x'] . theta

Zhao et al.'s DoubleAdapt (KDD 2023) makes two moves a plain slow/fast split does not. First,
the recent window is TRANSFORMED before the model reads it: a per-feature affine map, fitted by
a few gradient steps on the recent labels against the adapted model, that finishes what the
shrunk delta could not -- a flipped sign, a halved scale -- feature by feature. A ridge delta
has ONE shrinkage for every feature; the data adapter is where "this feature's meaning keeps
moving, that one's does not" can be expressed. Second, nothing about how much to adapt is a
constant: the adapter's starting point (its per-feature gain), the slow weights and the fast
shrinkage are updated across ROLLING TASKS -- adapt on the first half of a span, score on the
second -- by the query loss AFTER adaptation, first-order MAML style. A meta-step that fires
only when the adapted model beat the unadapted one is what "toward what adapted well" means
here. The desk keeps every piece linear and small: the whole meta-loop is a few dozen ridge
solves.

`libs.regime.drift.SlowFast` is reused for the model adapter (its `adapt` IS the fast ridge on
the residuals), so a DoubleAdapt whose data adapter learns to stay at identity degrades to
SlowFast with a meta-chosen shrinkage, not to something new.

READ THE DRIFT, NOT JUST THE SCORE: `drift_report` says, per feature, how far the data adapter
had to move from identity to make the recent window fit. A feature that keeps needing a new
scale is a feature whose meaning is rotating; that is a research finding about the feature
before it is a modelling choice.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from libs.regime.drift import SlowFast


def _ridge(x: np.ndarray, y: np.ndarray, lam: float) -> np.ndarray:
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = xb.T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, xb.T @ y)
    return out


def _wridge(x: np.ndarray, y: np.ndarray, w: np.ndarray, lam: float) -> np.ndarray:
    """Row-weighted ridge, intercept unpenalised: the fast delta with a recency profile."""
    xb = np.column_stack([np.ones(x.shape[0]), x])
    a = (xb * w[:, None]).T @ xb + lam * np.eye(xb.shape[1])
    a[0, 0] -= lam
    out: np.ndarray = np.linalg.solve(a, (xb * w[:, None]).T @ y)
    return out


def _mse(pred: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((pred - y) ** 2))


class DoubleAdapt:
    """Model adapter (SlowFast fast delta) + data adapter (per-feature affine), meta-learned.

    `fit(x, y, window)` fits the slow ridge, then walks spans of two windows as tasks: adapt on
    the first window (exactly what `predict` is handed), score on the second against NOT
    adapting. Two things about the fast delta are chosen by the query loss over all tasks --
    how much to shrink it (`fast_grid`) and how far back it looks (`recency_grid`, a half-life
    as a fraction of the window; None = flat) -- because on a stream that turns, the rows just
    before the turn are the ones that mislead, and no shrinkage fixes that. On every task where
    adapting won, the slow weights and the adapter init take a first-order meta-step down the
    query loss. That step is deliberately SMALL (`meta_lr`): the first-order gradient says
    "adapt this feature harder" whenever the delta lagged a turn, and a per-feature gain that
    has grown to 1.2 amplifies the next lagged delta as faithfully as a good one -- measured,
    0.1 gave back everything the recency profile had won; 0.02 keeps it.
    `predict(x_recent, y_recent, x_next)` performs the same adaptation on the live window.
    Everything works in train-standardised feature units so the inner step size means the same
    thing on every feature.
    """

    #: Complexity tax in nats per prediction -- MUST equal `libs.models.zoo.TAX["double_adapt"]`.
    tax: float = 0.0025

    def __init__(self, lam_slow: float = 10.0,
                 fast_grid: tuple[float, ...] = (2.0, 10.0, 50.0),
                 recency_grid: tuple[float | None, ...] = (None, 0.5, 0.25),
                 inner_steps: int = 8, inner_lr: float = 0.1, inner_reg: float = 1.0,
                 meta_lr: float = 0.02, stride: int | None = None) -> None:
        self.lam_slow = lam_slow
        self.fast_grid = tuple(float(v) for v in fast_grid)
        self.recency_grid = tuple(None if v is None else float(v) for v in recency_grid)
        self.inner_steps = inner_steps
        self.inner_lr = inner_lr
        self.inner_reg = inner_reg
        self.meta_lr = meta_lr
        self.stride = stride
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.slow: np.ndarray | None = None
        self.a0: np.ndarray | None = None
        self.b0: np.ndarray | None = None
        self.lam_fast: float = self.fast_grid[len(self.fast_grid) // 2]
        self.recency: float | None = self.recency_grid[0]
        self.window: int = 0
        self.meta: dict[str, Any] = {}
        self._moves: list[np.ndarray] = []            # per adaptation: |a - 1| and |b|, (2, d)
        self._moves_from_init: list[np.ndarray] = []

    # ------------------------------------------------------------------------- helpers
    def _std(self, x: np.ndarray) -> np.ndarray:
        assert self.mu is not None and self.sd is not None
        out: np.ndarray = np.nan_to_num((np.asarray(x, dtype=float) - self.mu) / self.sd)
        return out

    @staticmethod
    def _apply(xs: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        out: np.ndarray = xs * a + b
        return out

    @staticmethod
    def _pred(xs: np.ndarray, theta: np.ndarray) -> np.ndarray:
        out: np.ndarray = theta[0] + xs @ theta[1:]
        return out

    def _inner(self, xs: np.ndarray, y: np.ndarray, theta: np.ndarray, a: np.ndarray,
               b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """A few gradient steps on the affine data adapter against the ADAPTED model's error,
        shrunk toward the init.

        d/da_j = 2 mean(r w_j x_j), d/db_j = 2 mean(r w_j): the adapter can only move a feature
        the model uses, which is why it is fitted after the fast delta -- against the slow
        weights alone a feature whose sign keeps flipping averages to w_j ~ 0 and is invisible.
        The shrinkage toward (a0, b0) is what stops two adapters from fitting one window twice.
        """
        w0, w = theta[0], theta[1:]
        a0, b0 = a.copy(), b.copy()
        a, b = a.copy(), b.copy()
        for _ in range(self.inner_steps):
            r = w0 + self._apply(xs, a, b) @ w - y
            ga = 2.0 * np.mean(r[:, None] * w[None, :] * xs, axis=0) + self.inner_reg * (a - a0)
            gb = 2.0 * np.mean(r[:, None] * w[None, :], axis=0) + self.inner_reg * (b - b0)
            a -= self.inner_lr * ga
            b -= self.inner_lr * gb
        return a, b

    def _fast(self, xs: np.ndarray, y: np.ndarray, theta: np.ndarray, lam: float,
              recency: float | None) -> SlowFast:
        """SlowFast carries theta and the delta; a recency profile only changes how the delta
        is weighted, so the flat case is SlowFast's own `adapt` and the weighted one fills the
        same slot with a row-weighted ridge on the same residuals."""
        n = xs.shape[0]
        sf = SlowFast(lam_slow=self.lam_slow, lam_fast=lam, recent=n)
        sf.slow = theta
        if recency is None:
            return sf.adapt(xs, y)
        half = max(recency * self.window, 1.0)
        w = 0.5 ** ((n - 1 - np.arange(n)) / half)
        sf.fast = _wridge(xs, y - self._pred(xs, theta), w, lam)
        return sf

    def _record(self, a: np.ndarray, b: np.ndarray) -> None:
        assert self.a0 is not None and self.b0 is not None
        self._moves.append(np.vstack([np.abs(a - 1.0), np.abs(b)]))
        self._moves_from_init.append(np.vstack([np.abs(a - self.a0), np.abs(b - self.b0)]))

    # ------------------------------------------------------------------------ meta-fit
    def fit(self, x: np.ndarray, y: np.ndarray, window: int = 120) -> DoubleAdapt:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        n, d = x.shape
        self.mu = np.nanmean(x, axis=0)
        sd = np.nanstd(x, axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        xs = self._std(x)
        self.window = int(max(8, min(window, n // 2)))
        self.slow = _ridge(xs, y, self.lam_slow)
        self.a0, self.b0 = np.ones(d), np.zeros(d)
        self._moves, self._moves_from_init = [], []
        stride = self.stride or max(1, self.window // 2)
        combos = [(lam, rec) for lam in self.fast_grid for rec in self.recency_grid]
        wins: dict[tuple[float, float | None], int] = dict.fromkeys(combos, 0)
        q_by: dict[tuple[float, float | None], list[float]] = {c: [] for c in combos}
        helped, tasks = 0, 0
        # A task spans two windows: adapt on the first half (exactly what `predict` is handed),
        # be judged on the second. The task must have the deployment's geometry or the
        # shrinkage it picks is tuned for a window the live adapter never sees.
        span = 2 * self.window
        for s in range(0, n - span + 1, stride):
            sup = slice(s, s + self.window)
            qry = slice(s + self.window, s + span)
            no_adapt = _mse(self._pred(xs[qry], self.slow), y[qry])
            best: tuple[float, tuple[float, float | None], np.ndarray, np.ndarray,
                        np.ndarray] | None = None
            for combo in combos:
                sf = self._fast(xs[sup], y[sup], self.slow, *combo)
                assert sf.fast is not None
                theta = self.slow + sf.fast
                a, b = self._inner(xs[sup], y[sup], theta, self.a0, self.b0)
                q = _mse(self._pred(self._apply(xs[qry], a, b), theta), y[qry])
                q_by[combo].append(q)
                if best is None or q < best[0]:
                    best = (q, combo, theta, a, b)
            assert best is not None
            q, combo, theta, a, b = best
            wins[combo] += 1
            tasks += 1
            self._record(a, b)
            if q < no_adapt:
                # First-order MAML: the query-loss gradient AT the adapted parameters, applied
                # to the slow weights and to the adapter init. It is ~0 when adaptation already
                # explains the query, so an init that adapts well is left alone.
                helped += 1
                xq = self._apply(xs[qry], a, b)
                r = self._pred(xq, theta) - y[qry]
                g_theta = 2.0 * np.mean(r[:, None] * np.column_stack([np.ones(r.size), xq]),
                                        axis=0)
                self.slow = self.slow - self.meta_lr * g_theta
                w = theta[1:]
                self.a0 = self.a0 - self.meta_lr * 2.0 * np.mean(
                    r[:, None] * w[None, :] * xs[qry], axis=0)
                self.b0 = self.b0 - self.meta_lr * 2.0 * np.mean(r[:, None] * w[None, :], axis=0)
        if tasks:
            mean_q = {c: float(np.mean(v)) for c, v in q_by.items() if v}
            self.lam_fast, self.recency = min(mean_q, key=lambda c: mean_q[c])
        self.meta = {"tasks": tasks, "helped": helped, "window": self.window, "stride": stride,
                     "lam_fast": self.lam_fast, "recency": self.recency,
                     "wins": {f"lam={k[0]},recency={k[1]}": v for k, v in wins.items()},
                     "init_scale": [round(float(v), 4) for v in self.a0],
                     "init_shift": [round(float(v), 4) for v in self.b0]}
        return self

    # ------------------------------------------------------------------------- predict
    def adapt(self, x_recent: np.ndarray, y_recent: np.ndarray) -> tuple[np.ndarray, np.ndarray,
                                                                          SlowFast]:
        """The live adaptation: fast delta on the window, then the data adapter from its init."""
        assert self.slow is not None and self.a0 is not None and self.b0 is not None, "fit first"
        xs = self._std(x_recent)
        y = np.asarray(y_recent, dtype=float)
        sf = self._fast(xs, y, self.slow, self.lam_fast, self.recency)
        assert sf.fast is not None
        a, b = self._inner(xs, y, self.slow + sf.fast, self.a0, self.b0)
        self._record(a, b)
        return a, b, sf

    def predict(self, x_recent: np.ndarray, y_recent: np.ndarray,
                x_next: np.ndarray) -> np.ndarray:
        a, b, sf = self.adapt(x_recent, y_recent)
        out: np.ndarray = np.asarray(sf.predict(self._apply(self._std(x_next), a, b)),
                                     dtype=float)
        return out

    # -------------------------------------------------------------------------- report
    def drift_report(self) -> dict[str, Any]:
        """How far the data adapter moved each feature: mean |a - 1| + |b| over adaptations.

        `from_identity` is the distance from "the recent window already looks like training";
        `from_init` is the distance from the meta-learned starting point, i.e. what was still
        surprising after the meta-loop had learned the usual move.
        """
        if not self._moves:
            return {"n": 0, "verdict": "UNMEASURED", "why": "no adaptation yet"}
        ident = np.mean(np.stack(self._moves), axis=0)            # (2, d)
        init = np.mean(np.stack(self._moves_from_init), axis=0)
        move = ident.sum(axis=0)
        order = np.argsort(move)[::-1]
        return {"n": len(self._moves), "window": self.window, "lam_fast": self.lam_fast,
                "recency": self.recency,
                "scale_move": [round(float(v), 4) for v in ident[0]],
                "shift_move": [round(float(v), 4) for v in ident[1]],
                "from_identity": [round(float(v), 4) for v in move],
                "from_init": [round(float(v), 4) for v in init.sum(axis=0)],
                "most_moved": int(order[0]), "least_moved": int(order[-1]),
                "ratio_max_min": round(float(move[order[0]] / max(move[order[-1]], 1e-9)), 3),
                "meta": self.meta}
