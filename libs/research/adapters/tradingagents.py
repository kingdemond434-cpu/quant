"""tradingagents adapter -- REBUILT: TradingAgents' bull/bear researcher DEBATE and its risk
manager, with the LLM speakers replaced by evidence. The BULL researcher builds the strongest
LONG case on the opening span (the long legs of every mechanism kind, scored); the BEAR
researcher builds the strongest SHORT case the same way. In the DEBATE each side's case is
cross-examined on a rebuttal span neither built on; the RISK MANAGER then rejects a surviving
case whose rebuttal drawdown exceeds twice its mean gain. The judge's pick is read once more on
the final holdout and, when it holds, donated as an exact recipe naming the side that won.

WHY NOT THE UPSTREAM. Its analysts and debaters are LLM agents and its data layer needs a
FinnHub key (sandbox_install_ledger: REJECTED_WITH_EVIDENCE). The STRUCTURE -- adversarial
cases built separately, cross-examined out of sample, vetoed by a risk reader -- is the
transferable mechanism, and here it is decided by numbers.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tradingagents"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "tradingagents"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (bull/bear debate decided by rebuttal evidence, rebuilt)"
HORIZON = 12
SPECS: tuple[tuple[str, int], ...] = (("momentum", 12), ("momentum", 48), ("trend", 50),
                                      ("reversion", 14), ("band_reversion", 20),
                                      ("pullback", 50), ("breakout", 24), ("squeeze", 20))


def side_case(a: dict[str, Any], fwd: Any, side: int, lo: int, hi: int, cost: float
              ) -> list[dict[str, Any]]:
    import numpy as np
    out = []
    for kind, w in SPECS:
        s = K.kind_signal(kind, a, w)
        s = np.where(s * side > 0, s, 0.0)
        out.append({"kind_": kind, "window": w, "signal": s,
                    **K.evidence(s, fwd, cost, lo, hi)})
    return sorted(out, key=lambda r: -r["t_ratio"])


def drawdown(s: Any, fwd: Any, cost: float, lo: int, hi: int) -> float:
    import numpy as np
    seg = s[lo:hi] * np.nan_to_num(fwd[lo:hi]) - cost * (s[lo:hi] != 0)
    eq = np.cumsum(seg)
    return float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size else 0.0


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
        b1, b2 = int(n * 0.5), int(n * 0.75)
        fwd = K.forward_return(a["c"], HORIZON)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        transcript: list[dict[str, Any]] = []
        finalists = []
        for side, who in ((1, "bull"), (-1, "bear")):
            case = side_case(a, fwd, side, 0, b1, cost)[0]
            trials += len(SPECS)
            reb = K.evidence(case["signal"], fwd, cost, b1, b2)
            dd = drawdown(case["signal"], fwd, cost, b1, b2)
            vetoed = reb["mean_net"] <= 0 or dd > 2.0 * max(reb["mean_net"] * reb["n_active"],
                                                             1e-12)
            transcript.append({"speaker": who, "case": case["kind_"], "window": case["window"],
                               "opening_t": round(case["t_ratio"], 3),
                               "rebuttal": reb, "rebuttal_drawdown": round(dd, 6),
                               "risk_manager_rejects": bool(vetoed)})
            if not vetoed:
                finalists.append((reb["t_ratio"], who, case))
        reps.append({"kind": "debate_transcript", "symbol": f.symbol, "rounds": transcript})
        if not finalists:
            continue
        _, who, case = max(finalists, key=lambda x: x[0])
        ho = K.evidence(case["signal"], fwd, cost, b2, n)
        if ho["mean_net"] <= 0 or ho["n_active"] < 10:
            continue
        cands.append(K.donate(
            A, SYSTEM, case["kind_"], f.symbol,
            f"{f.symbol} H1: in a TradingAgents-style debate the {who} case "
            f"({case['kind_']}, {case['window']} bars) survived cross-examination on an unseen "
            f"rebuttal span and the risk reader, and held on the final holdout",
            horizon_label=bundle.horizons[-1],
            ev={"winner": who, "holdout": ho, "transcript": transcript},
            window=case["window"], horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "bull/bear researcher debate + risk manager",
                              "the debaters are LLM agents and the data layer needs a FinnHub "
                              "key; evidence decides the debate instead")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
