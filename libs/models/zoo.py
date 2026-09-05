"""The model zoo: challengers for one prediction problem, each charged a complexity tax.

QuantMind runs thirteen model types with Optuna and stacking; Qlib exposes LightGBM, GRU, TFT,
TRA, HIST and more. The desk copies the CONTEST, not the roster: for a given (features, target)
every model in the zoo is fitted walk-forward and scored by out-of-sample log score against the
base-rate forecast, and a model keeps its place only if its gain clears its own tax:

    gain(M) = logscore_M - logscore_baseline - tax(M)       per prediction, nats

The tax is declared per architecture (compute, instability, latency, degrees of freedom) so a
Transformer-class model has to beat ridge by MORE than a ridge has to beat the base rate. If
LightGBM-class boosting beats an MLP after tax, the desk uses the boosting; if ridge beats
everything, the desk uses ridge. Nothing here is ever the live decision-maker; the winner is a
CANDIDATE conditioning model for a family or the router, which the gauntlet then judges.

TARGET: the sign of the forward return over `horizon` bars (a probability), which is what a
sizing posterior needs. Everything is sklearn or numpy; nothing needs a GPU.
"""
from __future__ import annotations

from typing import Any

import numpy as np

#: Declared tax in nats per prediction. Ridge/logistic are the reference: zero tax.
#: soft_moe sits above the router: same K experts and gate, plus a noise variance per expert
#: and a temperature, and an EM fit that can settle on a different partition per fold -- more
#: freedom and more fold-to-fold instability than the router's sharpened k-means.
#: double_adapt is priced with the MLP: it refits on every prediction from the last `window`
#: labelled rows, so it carries the MLP's instability AND a latency cost the others do not --
#: the recent labels must exist before it can predict, which at horizon h means h bars stale.
TAX: dict[str, float] = {"logistic": 0.0, "ridge_sign": 0.0, "hist_gb": 0.0015,
                         "mlp": 0.0025, "router": 0.0015, "soft_moe": 0.002,
                         "double_adapt": 0.0025}
MIN_ROWS = 300
#: Rows the adaptive model adapts on at prediction time; clamped to half the train fold.
ADAPT_WINDOW = 120


def _squash(raw: np.ndarray) -> np.ndarray:
    """A +-1 regression read as a probability; clipped so a confident model cannot overflow."""
    out: np.ndarray = 1.0 / (1.0 + np.exp(-np.clip(4.0 * raw, -50.0, 50.0)))
    return out


def _log_score(p: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _standardise(x_train: np.ndarray, x_test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.nanmean(x_train, axis=0)
    sd = np.nanstd(x_train, axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    a = np.nan_to_num((x_train - mu) / sd)
    b = np.nan_to_num((x_test - mu) / sd)
    return a, b


def _fit_predict(name: str, xtr: np.ndarray, ytr: np.ndarray, xte: np.ndarray,
                 ztr: np.ndarray | None = None, zte: np.ndarray | None = None) -> np.ndarray:
    if name == "logistic":
        from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
        m = LogisticRegression(C=0.5, max_iter=500)
        m.fit(xtr, ytr)
        return np.asarray(m.predict_proba(xte)[:, 1], dtype=float)
    if name == "ridge_sign":
        from sklearn.linear_model import Ridge
        m = Ridge(alpha=10.0)
        m.fit(xtr, 2 * ytr - 1)
        raw = np.asarray(m.predict(xte), dtype=float)
        return 1.0 / (1.0 + np.exp(-4.0 * raw))
    if name == "hist_gb":
        from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=120, learning_rate=0.05,
                                           l2_regularization=1.0, random_state=0)
        m.fit(xtr, ytr)
        return np.asarray(m.predict_proba(xte)[:, 1], dtype=float)
    if name == "mlp":
        from sklearn.neural_network import MLPClassifier  # type: ignore[import-untyped]
        m = MLPClassifier(hidden_layer_sizes=(16, 8), alpha=1e-2, max_iter=300,
                          random_state=0)
        m.fit(xtr, ytr)
        return np.asarray(m.predict_proba(xte)[:, 1], dtype=float)
    if name == "router":
        from libs.models.router import ExpertRouter
        z_tr = ztr if ztr is not None else xtr
        z_te = zte if zte is not None else xte
        r = ExpertRouter(n_experts=3).fit(xtr, 2 * ytr - 1, z_tr)
        raw = r.predict(xte, z_te)
        return 1.0 / (1.0 + np.exp(-4.0 * raw))
    if name == "soft_moe":
        from libs.models.router import SoftMoE
        g_tr = ztr if ztr is not None else xtr
        g_te = zte if zte is not None else xte
        moe = SoftMoE(n_experts=3).fit(xtr, 2 * ytr - 1, g_tr)
        return _squash(moe.predict(xte, g_te))
    if name == "double_adapt":
        from libs.models.adapter import DoubleAdapt
        w = int(min(ADAPT_WINDOW, xtr.shape[0] // 2))
        da = DoubleAdapt().fit(xtr, 2 * ytr - 1, window=w)
        return _squash(da.predict(xtr[-w:], 2 * ytr[-w:] - 1, xte))
    raise KeyError(name)


def walk_forward(name: str, x: np.ndarray, y: np.ndarray, *, n_folds: int = 5,
                 z: np.ndarray | None = None) -> dict[str, Any]:
    """Expanding-window folds; the score is the mean OOS log score across them."""
    n = x.shape[0]
    if n < MIN_ROWS:
        return {"model": name, "n": n, "verdict": "UNMEASURED", "why": f"need {MIN_ROWS} rows"}
    edges = np.linspace(n // 3, n, n_folds + 1).astype(int)
    scores, base, briers = [], [], []
    for i in range(n_folds):
        a, b = edges[i], edges[i + 1]
        xtr, xte = _standardise(x[:a], x[a:b])
        ytr, yte = y[:a], y[a:b]
        if yte.size < 10 or ytr.std() == 0:
            continue
        p0 = float(ytr.mean())
        try:
            p = _fit_predict(name, xtr, ytr, xte, None if z is None else z[:a],
                             None if z is None else z[a:b])
        except Exception as exc:
            return {"model": name, "n": n, "verdict": "FAILED",
                    "why": f"{type(exc).__name__}: {exc}"}
        scores.append(_log_score(p, yte))
        base.append(_log_score(np.full(yte.size, p0), yte))
        briers.append(float(np.mean((p - yte) ** 2)))
    if not scores:
        return {"model": name, "n": n, "verdict": "UNMEASURED", "why": "no scorable fold"}
    gain = float(np.mean(scores) - np.mean(base))
    net = gain - TAX.get(name, 0.0)
    return {"model": name, "n": n, "folds": len(scores),
            "log_score": round(float(np.mean(scores)), 6),
            "baseline": round(float(np.mean(base)), 6), "gain": round(gain, 6),
            "tax": TAX.get(name, 0.0), "net_gain": round(net, 6),
            "brier": round(float(np.mean(briers)), 6),
            "verdict": "EARNS_ITS_PLACE" if net > 0 else "TAXED_OUT"}


def compete(x: np.ndarray, y: np.ndarray, *, models: tuple[str, ...] = tuple(TAX),
            z: np.ndarray | None = None) -> dict[str, Any]:
    """Every model on the same folds; the winner is the best NET gain, and only if positive."""
    res = {m: walk_forward(m, x, y, z=z) for m in models}
    scored = {m: r for m, r in res.items() if r.get("net_gain") is not None}
    winner = max(scored, key=lambda m: scored[m]["net_gain"]) if scored else None
    return {"results": res, "winner": (winner if winner and scored[winner]["net_gain"] > 0
                                       else None),
            "rule": "winner = argmax net gain (OOS log score - baseline - tax), only if > 0"}
