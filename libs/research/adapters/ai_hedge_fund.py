"""ai_hedge_fund adapter -- REBUILT: the deterministic TECHNICAL ANALYST of virattt/ai-hedge-fund
(its `technicals` agent is code, not a prompt): five strategy readings combined by fixed weights
into one signal -- trend (EMA 8/21/55 alignment), mean reversion (50-bar z-score with Bollinger
position), momentum (three lookbacks), volatility regime (realised-vol z) and statistical
arbitrage (the Hurst exponent: H < 0.5 favours reversion, H > 0.5 persistence). Weights are the
upstream's: 0.25 / 0.20 / 0.25 / 0.15 / 0.15.

The ensemble is read on the train span and the holdout. Each component's holdout evidence is
reported, and the component that carried the ensemble -- largest weight x holdout t-ratio,
after a positive train reading -- is donated as an exact recipe; the Hurst reading picks
reversion or persistence for the stat-arb leg.

WHY NOT THE UPSTREAM. Git-only (no distribution on the box) and its OTHER analysts (valuation,
sentiment, fundamentals, the portfolio manager) are LLM prompts the research path does not
carry. The technical analyst is the part that is a computation over prices.
"""
from __future__ import annotations

import math
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ai_hedge_fund"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "MIT"
MODULE = "ai_hedge_fund"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (technical-analyst ensemble, rebuilt)"
WEIGHTS = {"trend": 0.25, "mean_reversion": 0.20, "momentum": 0.25, "volatility": 0.15,
           "stat_arb": 0.15}
HORIZON = 12


def hurst(r: Any) -> float:
    """Rescaled-range Hurst exponent over the finite returns (0.5 when too short)."""
    import numpy as np
    r = r[np.isfinite(r)]
    if r.shape[0] < 256:
        return 0.5
    sizes, rs = [], []
    for m in (16, 32, 64, 128):
        k = r.shape[0] // m
        vals = []
        for j in range(k):
            seg = r[j * m:(j + 1) * m]
            z = np.cumsum(seg - seg.mean())
            s = float(seg.std())
            if s > 0:
                vals.append((float(z.max() - z.min())) / s)
        if vals:
            sizes.append(math.log(m))
            rs.append(math.log(float(np.mean(vals))))
    if len(sizes) < 2:
        return 0.5
    return float(np.polyfit(sizes, rs, 1)[0])


def components(a: dict[str, Any], h_train: float) -> dict[str, Any]:
    import numpy as np
    c = a["c"]
    e8, e21, e55 = K.ema(c, 8), K.ema(c, 21), K.ema(c, 55)
    trend = np.where((e8 > e21) & (e21 > e55), 1.0, np.where((e8 < e21) & (e21 < e55), -1.0, 0))
    z = K.zscore(c, 50)
    mr = np.where(z < -2, 1.0, np.where(z > 2, -1.0, 0.0))
    lc = np.log(np.maximum(c, 1e-12))
    mom = np.zeros(c.shape[0])
    for lb, w in ((24, 0.4), (72, 0.3), (144, 0.3)):
        m = np.zeros(c.shape[0])
        m[lb:] = lc[lb:] - lc[:-lb]
        mom += w * np.sign(m)
    mom = np.sign(mom)
    r = np.diff(lc, prepend=lc[0])
    vz = K.zscore(np.nan_to_num(K.rolling_std(r, 24)), 240)
    # low volatility regime -> lean with the 24-bar move; high -> fade it
    m24 = np.zeros(c.shape[0])
    m24[24:] = lc[24:] - lc[:-24]
    vol = np.where(vz < -0.8, np.sign(m24), np.where(vz > 1.2, -np.sign(m24), 0.0))
    arb = -np.sign(np.nan_to_num(z)) if h_train < 0.5 else np.sign(m24)
    return {"trend": trend, "mean_reversion": mr, "momentum": mom, "volatility": vol,
            "stat_arb": np.nan_to_num(arb)}


KIND = {"trend": ("trend", 55), "mean_reversion": ("band_reversion", 50),
        "momentum": ("momentum", 24), "volatility": ("squeeze", 24)}


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
        lc = np.log(np.maximum(a["c"], 1e-12))
        h = hurst(np.diff(lc[:cut]))
        comp = components(a, h)
        fwd = K.forward_return(a["c"], HORIZON)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        ens = np.sign(sum(WEIGHTS[k] * v for k, v in comp.items()))
        trials += len(comp) + 1
        table = {k: {"train": K.evidence(v, fwd, cost, 0, cut),
                     "holdout": K.evidence(v, fwd, cost, cut, n)} for k, v in comp.items()}
        ens_ev = {"train": K.evidence(ens, fwd, cost, 0, cut),
                  "holdout": K.evidence(ens, fwd, cost, cut, n)}
        reps.append({"kind": "technical_analyst_ensemble", "symbol": f.symbol,
                     "hurst_train": round(h, 4), "weights": WEIGHTS, "components": table,
                     "ensemble": ens_ev})
        carried = [(WEIGHTS[k] * t["holdout"]["t_ratio"], k) for k, t in table.items()
                   if t["train"]["mean_net"] > 0 and t["holdout"]["n_active"] >= 20]
        if not carried or ens_ev["holdout"]["mean_net"] <= 0:
            continue
        score, comp_name = max(carried)
        if score <= 0:
            continue
        kind, w = KIND.get(comp_name, ("band_reversion" if h < 0.5 else "momentum", 50))
        cands.append(K.donate(
            A, SYSTEM, kind, f.symbol,
            f"{f.symbol} H1: ai-hedge-fund's technical analyst (five weighted readings, Hurst "
            f"{h:.2f} on the train span) kept a positive net mean on the holdout, carried by "
            f"its {comp_name} leg; a {kind} hypothesis", horizon_label=bundle.horizons[-1],
            ev={"component": comp_name, "hurst_train": h, "ensemble": ens_ev,
                "component_evidence": table[comp_name]}, window=w, horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "technical-analyst agent: five weighted strategy "
                              "readings", "git-only upstream whose other analysts are LLM "
                              "prompts; the deterministic technicals agent is reproduced")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
