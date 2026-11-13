"""autohedge adapter -- REBUILT: AutoHedge's four-stage swarm pipeline -- DIRECTOR (sets the
thesis), QUANT (tests it), RISK (reviews the tail), EXECUTION (prices the entry) -- with each
stage a deterministic reader instead of an LLM agent. The director proposes one thesis per
mechanism kind from the 240-bar regime (trend strength and vol state); the quant scores every
thesis on the train span; the risk stage measures each survivor's expected shortfall (worst 5%
of its per-bar outcomes) and keeps only theses whose mean gain is not a small fraction of the
tail they carry; the execution stage charges the bundle's own spread at every entry. The thesis
that reaches the end of the pipeline AND holds on the holdout is donated as an exact recipe.

WHY NOT THE UPSTREAM. `autohedge` needs an LLM provider key through `swarms`
(sandbox_install_ledger: REJECTED_WITH_EVIDENCE). The orchestration -- each stage able to stop
the thesis the previous one passed it -- is the transferable part.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "autohedge"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "MIT"
MODULE = "autohedge"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (director/quant/risk/execution pipeline, rebuilt)"
HORIZON = 12
TAIL_RATIO_MIN = 0.02


def director(a: dict[str, Any], cut: int) -> list[tuple[str, int]]:
    """Theses from the train-span regime: a trending, calm tape asks persistence questions; a
    choppy or volatile one asks reversion questions. Both are always asked once."""
    import numpy as np
    c = a["c"][:cut]
    lc = np.log(np.maximum(c, 1e-12))
    r = np.diff(lc)
    eff = abs(lc[-1] - lc[0]) / max(float(np.sum(np.abs(r))), 1e-12)
    trending = eff > 0.1
    base = [("momentum", 24), ("reversion", 14)]
    more = ([("trend", 50), ("breakout", 24), ("pullback", 50)] if trending else
            [("band_reversion", 20), ("range_reversion", 30), ("squeeze", 20)])
    return base + more


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
        a = K.arrays(f)
        n = a["c"].shape[0]
        cut = K.split(n)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        fwd = K.forward_return(a["c"], HORIZON)
        theses = director(a, cut)
        trials += len(theses)
        stages: list[dict[str, Any]] = []
        finalists = []
        for kind, w in theses:
            s = K.kind_signal(kind, a, w)
            q = K.evidence(s, fwd, cost, 0, cut)
            row: dict[str, Any] = {"thesis": kind, "window": w, "quant": q}
            if q["mean_net"] <= 0:
                row["stopped_at"] = "quant"
                stages.append(row)
                continue
            seg = s[:cut] * np.nan_to_num(fwd[:cut]) - cost * (s[:cut] != 0)
            seg = seg[s[:cut] != 0]
            es = float(-np.mean(np.sort(seg)[:max(1, seg.shape[0] // 20)])) if seg.size else 0.0
            row["expected_shortfall"] = round(es, 6)
            if es > 0 and q["mean_net"] / es < TAIL_RATIO_MIN:
                row["stopped_at"] = "risk"
                stages.append(row)
                continue
            ho = K.evidence(s, fwd, cost, cut, n)
            row["holdout"] = ho
            row["stopped_at"] = "none" if ho["mean_net"] > 0 else "holdout"
            stages.append(row)
            if ho["mean_net"] > 0 and ho["n_active"] >= 10:
                finalists.append((ho["t_ratio"], kind, w, row))
        reps.append({"kind": "swarm_pipeline", "symbol": f.symbol, "stages": stages})
        if finalists:
            _, kind, w, row = max(finalists, key=lambda x: x[0])
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: an AutoHedge-style director/quant/risk/execution pipeline "
                f"carried the {kind} thesis ({w} bars) past the quant's train test and the risk "
                f"stage's expected-shortfall review, net of spread, onto a positive holdout",
                horizon_label=bundle.horizons[-1], ev=row, window=w, horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "director -> quant -> risk -> execution swarm",
                              "the swarm needs an LLM provider key through swarms; each stage "
                              "is a deterministic reader here")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
