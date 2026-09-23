"""Tigramite adapter -- PCMCI lagged causal graphs over the bundle's return matrix. Every
(cause, effect, lag) tested is a charged trial; the links below alpha are donated as
MECHANISMS (who leads whom, at which lag), never as signals.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tigramite"
CAPABILITY_FAMILY = "causal_discovery"
LICENCE_EXPECTED = "GPL-3.0"
MAX_SYMBOLS = 5
TAU_MAX = 3
ALPHA = 0.01


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pp = A.library("tigramite.data_processing")
    pcmci_mod = A.library("tigramite.pcmci")
    parcorr = A.library("tigramite.independence_tests.parcorr")
    if pp is None or pcmci_mod is None or parcorr is None:
        return A.unmeasured(SYSTEM, bundle, "tigramite is not importable here (pip install "
                                            "tigramite==5.2.10.1)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 400][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 1
    data = np.column_stack([f.log_returns()[-n:] for f in frames])
    names = [f.symbol for f in frames]
    trials = len(names) * len(names) * TAU_MAX
    try:
        df = pp.DataFrame(data, var_names=names)
        pc = pcmci_mod.PCMCI(dataframe=df, cond_ind_test=parcorr.ParCorr(), verbosity=0)
        res = pc.run_pcmci(tau_max=TAU_MAX, pc_alpha=ALPHA)
        p = np.asarray(res["p_matrix"], dtype=float)
        v = np.asarray(res["val_matrix"], dtype=float)
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=trials, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    mechs: list[dict[str, Any]] = []
    for i, cause in enumerate(names):
        for j, effect in enumerate(names):
            for tau in range(1, TAU_MAX + 1):
                if p[i, j, tau] < ALPHA and i != j:
                    mechs.append({"kind": "lagged_link", "cause": cause, "effect": effect,
                                  "lag_bars": tau, "partial_corr": float(v[i, j, tau]),
                                  "p": float(p[i, j, tau]), "method": "PCMCI/ParCorr",
                                  "mechanism": f"{cause} leads {effect} by {tau} H1 bars"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs,
                    note=f"{len(mechs)} links below alpha={ALPHA} over {len(names)} symbols")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
