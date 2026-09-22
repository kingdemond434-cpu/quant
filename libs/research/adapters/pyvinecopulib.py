"""pyvinecopulib adapter -- a vine copula over the bundle's returns -> tail-dependence states.

One vine is fitted over the aligned H1 returns with a five-family bivariate set; the charged
trials are the bivariate fits the selection performed (pairs x families). The desk receives the
first-tree pair copulas (family, Kendall tau, parameters) and the fit's log-likelihood -- a
dependence representation, never a portfolio.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "pyvinecopulib"
FAMILY_NAMES: tuple[str, ...] = ("gaussian", "student", "clayton", "gumbel", "frank")


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pv = A.library("pyvinecopulib")
    if pv is None:
        return A.unmeasured(SYSTEM, bundle, "pyvinecopulib is not importable here")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 300][:6]
    if len(frames) < 3:
        return A.unmeasured(SYSTEM, bundle, "fewer than three H1 frames with 300+ bars")
    n = min(len(f) for f in frames) - 1
    R = np.column_stack([f.log_returns()[-n:] for f in frames])
    d = R.shape[1]
    trials = (d * (d - 1) // 2) * len(FAMILY_NAMES)
    try:
        u = pv.to_pseudo_obs(R)
        fams = [getattr(pv.BicopFamily, name) for name in FAMILY_NAMES]
        controls = pv.FitControlsVinecop(family_set=fams)
        cop = (pv.Vinecop.from_data(u, controls=controls) if hasattr(pv.Vinecop, "from_data")
               else pv.Vinecop(data=u, controls=controls))
        pcs = cop.pair_copulas
        tree1 = []
        for pc in list(pcs[0]) if pcs else []:
            tree1.append({"family": str(getattr(pc.family, "name", pc.family)),
                          "tau": float(pc.tau),
                          "parameters": np.asarray(pc.parameters, dtype=float).reshape(-1)})
        loglik = float(cop.loglik(u))
        order = [frames[int(i) - 1].symbol for i in np.asarray(cop.order).reshape(-1)]
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=trials, representations=[
            {"kind": "UNMEASURED", "symbols": [f.symbol for f in frames],
             "why": f"{type(exc).__name__}: {exc}"[:200]}])
    tail = [t for t in tree1 if t["family"] in ("clayton", "gumbel", "student")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=[
        {"kind": "tail_dependence_state", "timeframe": "H1", "n_obs": int(n),
         "symbols": [f.symbol for f in frames], "vine_order": order,
         "families_considered": list(FAMILY_NAMES), "tree1": tree1,
         "n_tail_families_tree1": len(tail), "loglik": loglik,
         "representation": "which pairs the vine joins with tail-dependent families is a "
                           "dependence state; a Clayton pair marks joint-downside clustering"}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
