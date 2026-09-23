"""pgmpy adapter -- a small dynamic Bayesian network over regime states -> mechanism packets.

States per bar: the realised-vol tercile and the sign of 24-bar momentum; the 2-TBN edges are
vol_t -> vol_t1 and trend_t -> vol_t1, fitted by maximum likelihood (one charged trial per
symbol). The desk receives the transition CPD and the persistence it implies -- a mechanism
hypothesis about regime dynamics, never a state forecast.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pgmpy"
WINDOW = 24


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    models = A.library("pgmpy.models")
    est = A.library("pgmpy.estimators")
    pd = A.library("pandas")
    if models is None or est is None or pd is None:
        return A.unmeasured(SYSTEM, bundle, "pgmpy (or pandas) is not importable here")
    import numpy as np
    Model = getattr(models, "DiscreteBayesianNetwork", None) or getattr(models,
                                                                         "BayesianNetwork", None)
    if Model is None:
        return A.unmeasured(SYSTEM, bundle, "pgmpy exposes no discrete Bayesian network class")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    mechs: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        if deadline.expired():
            break
        r = f.log_returns()
        if r.shape[0] < 300:
            continue
        vol = A.realised_vol(r, WINDOW)
        lp = np.log(np.maximum(np.asarray(f.close, float), 1e-12))[1:]
        mom = np.concatenate([np.full(WINDOW, np.nan), lp[WINDOW:] - lp[:-WINDOW]])
        ok = ~(np.isnan(vol) | np.isnan(mom))
        v, m = vol[ok], mom[ok]
        q1, q2 = np.quantile(v, [1 / 3, 2 / 3])
        vt = np.where(v <= q1, 0, np.where(v <= q2, 1, 2))
        tt = (m > 0).astype(int)
        df = pd.DataFrame({"vol_t": vt[:-1], "trend_t": tt[:-1], "vol_t1": vt[1:]})
        trials += 1
        try:
            model = Model([("vol_t", "vol_t1"), ("trend_t", "vol_t1")])
            model.fit(df, estimator=est.MaximumLikelihoodEstimator)
            cpd = model.get_cpds("vol_t1")
            values = np.asarray(cpd.values, dtype=float)
            evidence = [str(e) for e in cpd.variables[1:]]
        except Exception as exc:
            mechs.append({"kind": "UNMEASURED", "symbol": f.symbol,
                          "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        table = values.reshape(values.shape[0], -1)
        stay = float(np.mean([table[k, k] for k in range(min(3, table.shape[0]))
                              if k < table.shape[1]])) if table.size else float("nan")
        mechs.append({"kind": "dbn_transition", "symbol": f.symbol, "timeframe": f.timeframe,
                      "states": {"vol": ["low", "mid", "high"], "trend": ["down", "up"]},
                      "edges": [["vol_t", "vol_t1"], ["trend_t", "vol_t1"]],
                      "cpd_variable": "vol_t1", "cpd_evidence": evidence,
                      "cpd_values": table, "n_obs": len(df),
                      "diagonal_persistence": stay,
                      "mechanism": "regime persistence conditioned on trend sign; test whether "
                                   "the implied next-tercile probability is informative"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
