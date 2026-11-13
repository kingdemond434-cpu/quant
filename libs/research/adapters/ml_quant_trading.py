"""ml_quant_trading adapter -- REBUILT: multi-factor ML with the two bias corrections the
upstream is about -- PURGED, EMBARGOED k-fold cross-validation (no training row whose label
window overlaps a test row, and an embargo after each test fold) and a ridge model whose
penalty is chosen by that CV, not by in-sample fit. What the fitted coefficients load on says
which mechanism the frame rewards; that is donated as an exact recipe.

FEATURES: log returns over 1, 3, 6, 12, 24 and 48 bars, the realised-vol ratio (24/96), RSI
distance from 50 and the close's position in its 48-bar range -- all known at bar t. TARGET: the
next HORIZON bars' log return. Ridge penalties (0.1, 1, 10, 100) are each a charged trial.

WHY NOT THE UPSTREAM. No distribution was resolvable on the box's interpreter (ledger:
NO_DISTRIBUTION_PINNED); the repository is a notebook collection. The method -- purged CV on a
factor design -- is the transferable part and needs numpy only.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ml_quant_trading"
CAPABILITY_FAMILY = "representation_learning"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "ml_quant_trading"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (purged-CV ridge on a factor design, rebuilt)"
HORIZON = 12
FOLDS = 5
PENALTIES: tuple[float, ...] = (0.1, 1.0, 10.0, 100.0)
RET_LAGS: tuple[int, ...] = (1, 3, 6, 12, 24, 48)
FEATURES: tuple[str, ...] = (*(f"ret_{k}" for k in RET_LAGS), "vol_ratio", "rsi_dist",
                             "range_pos")


def design(a: dict[str, Any]) -> tuple[Any, Any]:
    import numpy as np
    c = a["c"]
    n = c.shape[0]
    lc = np.log(np.maximum(c, 1e-12))
    cols = []
    for k in RET_LAGS:
        x = np.full(n, np.nan)
        x[k:] = lc[k:] - lc[:-k]
        cols.append(x)
    r = np.diff(lc, prepend=lc[0])
    cols.append(K.rolling_std(r, 24) / np.maximum(K.rolling_std(r, 96), 1e-12))
    cols.append((K.rsi(c, 14) - 50.0) / 50.0)
    hi, lo = K.rolling_max(a["h"], 48), K.rolling_min(a["l"], 48)
    cols.append((c - lo) / np.maximum(hi - lo, 1e-12) - 0.5)
    return np.column_stack(cols), K.forward_return(c, HORIZON)


def purged_folds(n: int, k: int, horizon: int) -> list[tuple[Any, Any]]:
    """Contiguous test folds; training rows whose label window [t, t+h] touches a test row are
    PURGED and the `horizon` rows after each test fold are EMBARGOED."""
    import numpy as np
    edges = np.linspace(0, n, k + 1).astype(int)
    out = []
    for i in range(k):
        lo, hi = int(edges[i]), int(edges[i + 1])
        test = np.arange(lo, hi)
        train = np.ones(n, dtype=bool)
        train[max(0, lo - horizon):min(n, hi + horizon)] = False
        out.append((np.where(train)[0], test))
    return out


def ridge(X: Any, y: Any, lam: float) -> Any:
    import numpy as np
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    beta = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return beta, mu, sd


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for f in fr:
        if deadline.expired():
            break
        X, y = design(K.arrays(f))
        ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
        X, y = X[ok], y[ok]
        if X.shape[0] < 300:
            continue
        cv: dict[float, float] = {}
        for lam in PENALTIES:
            trials += 1
            preds = np.full(y.shape[0], np.nan)
            for tr, te in purged_folds(X.shape[0], FOLDS, HORIZON):
                beta, mu, sd = ridge(X[tr], y[tr], lam)
                preds[te] = ((X[te] - mu) / sd) @ beta
            cv[lam] = K.rank_ic(preds, y)
        lam = max(cv, key=lambda k: cv[k])
        beta, _, _ = ridge(X, y, lam)
        j = int(np.argmax(np.abs(beta[:len(RET_LAGS)])))
        lag = RET_LAGS[j]
        reps.append({"kind": "purged_cv_ridge", "symbol": f.symbol, "horizon_bars": HORIZON,
                     "cv_rank_ic_by_penalty": {str(k): round(v, 5) for k, v in cv.items()},
                     "penalty": lam, "coefficients": dict(zip(FEATURES,
                                                               (round(float(b), 6)
                                                                for b in beta), strict=True))})
        if cv[lam] > 0.02:
            kind = "momentum" if beta[j] > 0 else "reversion"
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: a ridge model chosen by purged, embargoed {FOLDS}-fold CV "
                f"(out-of-fold rank IC {cv[lam]:+.3f}) loads most on the {lag}-bar return with "
                f"sign {np.sign(beta[j]):+.0f}; a {kind} hypothesis at that lookback",
                horizon_label=bundle.horizons[-1],
                ev={"cv_rank_ic": cv[lam], "penalty": lam, "lag": lag,
                    "coefficient": float(beta[j])}, window=max(3, lag), horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "purged/embargoed k-fold CV over a ridge factor "
                              "model", "no distribution resolvable on the box interpreter; the "
                              "method is reproduced in numpy")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
