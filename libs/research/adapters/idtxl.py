"""IDTxl adapter -- multivariate transfer entropy over the bundle's return matrix (Gaussian
estimator, lags 1..3). Significant source->target links are MECHANISMS; the permutation
tests are the charged trials.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "idtxl"
CAPABILITY_FAMILY = "information_theory"
LICENCE_EXPECTED = "GPL-3.0"
MAX_SYMBOLS = 4
PERMS = 50


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    mte = A.library("idtxl.multivariate_te")
    dat = A.library("idtxl.data")
    if mte is None or dat is None:
        return A.unmeasured(SYSTEM, bundle, "idtxl is not importable here (git-only upstream "
                                            "pwollstadt/IDTxl; JIDT estimators need a JVM)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 400][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 1
    arr = np.column_stack([f.log_returns()[-n:] for f in frames]).T
    names = [f.symbol for f in frames]
    trials = len(names) * (len(names) - 1) * PERMS
    try:
        data = dat.Data(arr, dim_order="ps")
        settings = {"cmi_estimator": "JidtGaussianCMI", "max_lag_sources": 3,
                    "min_lag_sources": 1, "n_perm_max_stat": PERMS, "n_perm_min_stat": PERMS,
                    "n_perm_omnibus": PERMS, "n_perm_max_seq": PERMS, "verbose": False}
        res = mte.MultivariateTE().analyse_network(settings=settings, data=data)
        adj = res.get_adjacency_matrix(weights="max_te_lag", fdr=False)
        edges = np.asarray(adj.get_edge_list() if hasattr(adj, "get_edge_list") else [])
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=trials, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    mechs = [{"kind": "transfer_entropy_link", "source": names[int(e[0])],
              "target": names[int(e[1])], "lag_bars": int(e[2]),
              "mechanism": f"{names[int(e[0])]} transfers information to {names[int(e[1])]}"}
             for e in edges if len(e) >= 3]
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
