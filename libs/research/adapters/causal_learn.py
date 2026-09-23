"""causal-learn adapter -- the PC algorithm (Fisher-z) over contemporaneous returns and their
first lags. Directed edges are donated as MECHANISMS; the CI tests are the charged trials.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "causal_learn"
CAPABILITY_FAMILY = "causal_discovery"
LICENCE_EXPECTED = "MIT"
MAX_SYMBOLS = 4
ALPHA = 0.01


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    pcmod = A.library("causallearn.search.ConstraintBased.PC")
    if pcmod is None:
        return A.unmeasured(SYSTEM, bundle, "causal-learn is not importable here (pip install "
                                            "causal-learn==0.1.4.8)")
    import numpy as np
    frames = [f for f in bundle.frames("H1") if len(f) > 400][:MAX_SYMBOLS]
    if len(frames) < 2:
        return A.unmeasured(SYSTEM, bundle, "fewer than two H1 frames long enough")
    n = min(len(f) for f in frames) - 2
    cols, names = [], []
    for f in frames:
        r = f.log_returns()
        cols.append(r[-n:])
        names.append(f.symbol)
        cols.append(r[-n - 1:-1])
        names.append(f"{f.symbol}[-1]")
    data = np.column_stack(cols)
    trials = len(names) * (len(names) - 1) // 2
    try:
        cg = pcmod.pc(data, alpha=ALPHA, indep_test="fisherz", show_progress=False)
        g = np.asarray(cg.G.graph)
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=trials, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    mechs: list[dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(len(names)):
            if g[j, i] == 1 and g[i, j] == -1:
                mechs.append({"kind": "directed_edge", "cause": names[i], "effect": names[j],
                              "method": "PC/fisherz", "alpha": ALPHA,
                              "mechanism": f"{names[i]} -> {names[j]} in the PC skeleton"})
    return A.packet(SYSTEM, bundle, trials=trials, mechanisms=mechs)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
