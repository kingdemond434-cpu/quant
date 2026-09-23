"""tsfresh adapter -- a feature universe over return windows -> FDR-filtered relevance
representations.

Windows of 48 H1 returns (stride 24) are the ids; the target is the sign of the following
24-bar return. tsfresh's EfficientFCParameters universe is extracted once per symbol and its
relevance table (Benjamini-Yekutieli, fdr_level 0.05) is the honest trial count: every feature
tested is charged, relevant or not. The desk receives the relevant features by name.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tsfresh"
WINDOW, STRIDE, POST, MAX_WINDOWS, MAX_SYMBOLS, FDR = 48, 24, 24, 30, 4, 0.05


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    tsf = A.library("tsfresh")
    fe = A.library("tsfresh.feature_extraction")
    rel = A.library("tsfresh.feature_selection.relevance")
    pd = A.library("pandas")
    if tsf is None or fe is None or rel is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "tsfresh (or pandas) is not importable here")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired():
            break
        r = f.log_returns()
        rows: list[dict[str, float]] = []
        labels: list[int] = []
        wid = 0
        start = max(0, r.shape[0] - (MAX_WINDOWS * STRIDE + WINDOW + POST))
        for a in range(start, r.shape[0] - WINDOW - POST, STRIDE):
            seg = r[a:a + WINDOW]
            rows.extend({"id": wid, "time": k, "value": float(v)} for k, v in enumerate(seg))
            labels.append(int(np.sum(r[a + WINDOW:a + WINDOW + POST]) > 0))
            wid += 1
        if wid < 12 or len(set(labels)) < 2:
            continue
        try:
            X = tsf.extract_features(pd.DataFrame(rows), column_id="id", column_sort="time",
                                     column_value="value",
                                     default_fc_parameters=fe.EfficientFCParameters(),
                                     n_jobs=0, disable_progressbar=True)
            X = X.replace([np.inf, -np.inf], np.nan).dropna(axis=1)
            y = pd.Series(labels, index=X.index)
            table = rel.calculate_relevance_table(X, y, ml_task="classification",
                                                  fdr_level=FDR, n_jobs=0)
        except Exception as exc:
            reps.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        trials += len(table)
        relevant = table[table["relevant"]].sort_values("p_value").head(15)
        reps.append({"kind": "feature_relevance", "symbol": f.symbol, "timeframe": f.timeframe,
                     "window_bars": WINDOW, "n_windows": wid, "target":
                     f"sign of the next {POST}-bar return", "n_features_tested": len(table),
                     "n_relevant_fdr": int(table["relevant"].sum()), "fdr_level": FDR,
                     "relevant": [{"feature": str(a), "p_value": float(b)} for a, b in
                                  zip(relevant["feature"], relevant["p_value"], strict=True)],
                     "representation": "features that survive FDR are representation "
                                       "candidates for the forge; none is a signal yet"})
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
