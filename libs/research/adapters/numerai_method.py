"""Numerai-method adapter (REBUILT, numpy only) -- the METHOD applied to the desk's own PIT
data: several INDEPENDENT ridge models on disjoint feature subsets, per-era (weekly) rank
correlation with the next-24h return, feature neutralisation of each prediction, a
meta-model as the rank average, and each model's CONTRIBUTION (correlation of its
meta-orthogonalised prediction with the target). Contributions are research methods; the
meta-model's last-era ranking is a representation. The tournament's data is never used.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "numerai_method"
CAPABILITY_FAMILY = "portfolio_research"
LICENCE_EXPECTED = "N/A (method only)"
RUNS_WITHOUT_LIBRARY = True
MAX_SYMBOLS = 8
N_MODELS = 3
RIDGE = 1.0
NEUTRALISE = 0.5


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 600][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    X_all, y_all, era_all, sym_all = [], [], [], []
    for f in frames:
        X, y24, eras = A.lagged_design(f, target_bars=24, era_bars=120)
        X_all.append(X)
        y_all.append(y24)
        era_all.append(eras)
        sym_all.append(np.full(X.shape[0], f.symbol))
    X = np.vstack(X_all)
    y = np.concatenate(y_all)
    era = np.concatenate(era_all)
    sym = np.concatenate(sym_all)
    n_feat = X.shape[1]
    subsets = [tuple(range(i, n_feat, N_MODELS)) for i in range(N_MODELS)]
    cut_era = int(np.percentile(era, 60))
    train, test = era <= cut_era, era > cut_era
    preds: dict[str, Any] = {}
    trials = 0
    for k, cols in enumerate(subsets):
        trials += 1
        Xk = X[:, list(cols)]
        A_ = Xk[train]
        w = np.linalg.solve(A_.T @ A_ + RIDGE * np.eye(A_.shape[1]), A_.T @ y[train])
        p = Xk @ w
        # feature neutralisation: remove the part of the prediction explained by ALL features
        beta = np.linalg.lstsq(X, p, rcond=None)[0]
        preds[f"model_{k}"] = p - NEUTRALISE * (X @ beta)

    def rank(v: Any) -> Any:
        return np.argsort(np.argsort(v)).astype(float) / max(v.shape[0] - 1, 1)

    def era_corr(p: Any) -> list[float]:
        out: list[float] = []
        for e in np.unique(era[test]):
            m = test & (era == e)
            if m.sum() >= 20 and np.std(p[m]) > 0 and np.std(y[m]) > 0:
                out.append(float(np.corrcoef(rank(p[m]), rank(y[m]))[0, 1]))
        return out

    meta = np.mean([rank(p) for p in preds.values()], axis=0)
    rows: list[dict[str, Any]] = []
    for name, p in preds.items():
        cs = era_corr(p)
        # contribution: the model's prediction orthogonalised to the meta-model, per era
        contrib: list[float] = []
        for e in np.unique(era[test]):
            m = test & (era == e)
            if m.sum() < 20:
                continue
            pm, mm = rank(p[m]) - 0.5, rank(meta[m]) - 0.5
            resid = pm - (np.dot(pm, mm) / max(np.dot(mm, mm), 1e-12)) * mm
            if np.std(resid) > 0 and np.std(y[m]) > 0:
                contrib.append(float(np.corrcoef(resid, rank(y[m]))[0, 1]))
        rows.append({"kind": "numerai_contribution", "model": name, "features": list(subsets[
            int(name.split("_")[1])]), "eras_oos": len(cs),
            "corr_mean": float(np.mean(cs)) if cs else None,
            "corr_sharpe": (float(np.mean(cs)) / max(float(np.std(cs)), 1e-12)
                            if len(cs) > 1 else None),
            "mmc_mean": float(np.mean(contrib)) if contrib else None,
            "neutralisation": NEUTRALISE, "method": "independent ridge models, per-era rank "
                                                    "correlation, feature neutralisation, "
                                                    "meta-model contribution"})
    last = era == era.max()
    ranking = {str(s): float(v) for s, v in zip(sym[last], meta[last], strict=True)}
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=rows, representations=[
        {"kind": "meta_model_ranking", "era": int(era.max()), "ranking": ranking,
         "representation": "the meta-model's cross-sectional rank this era; a state, not a "
                           "signal, until the gauntlet says otherwise"}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
