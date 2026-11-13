"""Alpha Search adapter -- REBUILT: the five-agent OPPORTUNITY / CRITIQUE swarm, each critic a
deterministic test instead of an LLM. The SCOUT ranks every (mechanism kind, window) on the
train span; each of the top opportunities is then cross-examined by five critics, and only an
opportunity that survives all five is donated:

    cost critic        still positive at TWICE the bundle's spread
    stability critic   positive in both halves of the train span separately
    robustness critic  the neighbouring windows (x0.5, x2) are not both negative
    regime critic      positive in at least two of the three volatility terciles
    sample critic      at least MIN_ACTIVE active bars on the train span

The surviving opportunity is read once on the holdout (no critic saw it) and donated with the
five critiques attached. The gauntlet remains the judge; the swarm only filters what it is
offered.

WHY NOT THE UPSTREAM. No PyPI distribution (NO_DISTRIBUTION_PINNED) and its agents are LLMs.
The critique structure is the mechanism.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alpha_search"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "alpha_search"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (scout + five deterministic critics, rebuilt)"
HORIZON = 12
TOP = 4
MIN_ACTIVE = 40
SPECS: tuple[tuple[str, int], ...] = tuple((k, w) for k in (
    "momentum", "trend", "reversion", "band_reversion", "range_reversion", "pullback",
    "breakout", "squeeze", "volume") for w in (12, 24, 48))


def critiques(a: dict[str, Any], kind: str, w: int, cost: float, cut: int) -> dict[str, bool]:
    import numpy as np
    fwd = K.forward_return(a["c"], HORIZON)
    s = K.kind_signal(kind, a, w)
    half = cut // 2
    lc = np.log(np.maximum(a["c"], 1e-12))
    vol = K.rolling_std(np.diff(lc, prepend=lc[0]), 48)
    q = (np.nanquantile(vol[:cut], (1 / 3, 2 / 3)) if np.isfinite(vol[:cut]).any()
         else np.array([0.0, 0.0]))
    state = np.searchsorted(q, np.nan_to_num(vol))
    by_state = [K.evidence(np.where(state == k, s, 0.0), fwd, cost, 0, cut)["mean_net"] > 0
                for k in range(3)]
    neigh = [K.evidence(K.kind_signal(kind, a, max(3, int(w * m))), fwd, cost, 0, cut)
             ["mean_net"] for m in (0.5, 2.0)]
    return {"cost": K.evidence(s, fwd, 2 * cost, 0, cut)["mean_net"] > 0,
            "stability": (K.evidence(s, fwd, cost, 0, half)["mean_net"] > 0
                          and K.evidence(s, fwd, cost, half, cut)["mean_net"] > 0),
            "robustness": not all(x < 0 for x in neigh),
            "regime": sum(by_state) >= 2,
            "sample": K.evidence(s, fwd, cost, 0, cut)["n_active"] >= MIN_ACTIVE}


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
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
        scouted = K.score_kinds(a, SPECS, HORIZON, cost, cut)
        trials += len(SPECS)
        top = sorted((r for r in scouted if r["train"]["mean_net"] > 0),
                     key=lambda r: -r["train"]["t_ratio"])[:TOP]
        hearing = []
        for r in top:
            crit = critiques(a, r["kind"], r["window"], cost, cut)
            trials += 4
            hearing.append({"kind_": r["kind"], "window": r["window"], "critiques": crit,
                            "survives": all(crit.values()), "holdout": r["holdout"]})
        reps.append({"kind": "critique_swarm", "symbol": f.symbol, "hearing": hearing})
        for h in hearing:
            if h["survives"] and h["holdout"]["mean_net"] > 0:
                cands.append(K.donate(
                    A, SYSTEM, h["kind_"], f.symbol,
                    f"{f.symbol} H1: an Alpha-Search-style scout proposed {h['kind_']} at "
                    f"{h['window']} bars and it survived all five critics (double cost, split "
                    f"stability, neighbouring windows, volatility regimes, sample size) before "
                    f"holding on the unseen holdout", horizon_label=bundle.horizons[-1],
                    ev={"critiques": h["critiques"], "holdout": h["holdout"]},
                    window=int(h["window"]), horizon=HORIZON))
                break
    methods = [K.upstream_row(SYSTEM, MODULE, "opportunity scout + five-critic swarm",
                              "no distribution on the box and the agents are LLMs; each critic "
                              "is a deterministic test here")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
