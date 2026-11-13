"""alphaquanter adapter -- REBUILT: AlphaQuanter's agentic RL loop -- an agent that learns WHICH
TOOL to consult in which market state -- as tabular Q-learning. The state is the tape's regime
(trend efficiency tercile x volatility tercile, both trailing); the actions are the desk's
mechanism readers ("tools": momentum, trend, RSI reversion, band reversion, breakout, squeeze,
abstain); the reward is the chosen tool's net next-HORIZON return. The Q-table is learned on
the train span, epsilon-greedy and seeded, then frozen and read on the holdout. The tool the
frozen policy chooses most often in the CURRENT state, when the policy's holdout evidence is
positive, is donated as an exact recipe.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED)
and its tool calls are made by an LLM the research path does not carry. Learning a tool-choice
policy over states is the mechanism; Q-learning is its plainest faithful form.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alphaquanter"
CAPABILITY_FAMILY = "rl_policy_search"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "alphaquanter"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (Q-learned tool choice per regime, rebuilt)"
HORIZON = 12
TOOLS: tuple[tuple[str, int], ...] = (("momentum", 24), ("trend", 50), ("reversion", 14),
                                      ("band_reversion", 20), ("breakout", 24),
                                      ("squeeze", 20))
EPOCHS = 3
ALPHA = 0.1
EPS = 0.2


def regime(a: dict[str, Any], cut: int) -> Any:
    """State id 0..8 = 3 x efficiency tercile + vol tercile, terciles from the train span."""
    import numpy as np
    c = a["c"]
    lc = np.log(np.maximum(c, 1e-12))
    r = np.abs(np.diff(lc, prepend=lc[0]))
    n = c.shape[0]
    eff = np.full(n, np.nan)
    eff[48:] = np.abs(lc[48:] - lc[:-48]) / np.maximum(
        np.convolve(r, np.ones(48), "full")[:n][48:], 1e-12)
    vol = K.rolling_std(r, 48)
    qe = np.nanquantile(eff[:cut], (1 / 3, 2 / 3)) if np.isfinite(eff[:cut]).any() else (0, 0)
    qv = np.nanquantile(vol[:cut], (1 / 3, 2 / 3)) if np.isfinite(vol[:cut]).any() else (0, 0)
    return (3 * np.searchsorted(qe, np.nan_to_num(eff)) +
            np.searchsorted(qv, np.nan_to_num(vol))).astype(int)


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    rng = np.random.default_rng(bundle.seed + 5)
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
        fwd = np.nan_to_num(K.forward_return(a["c"], HORIZON))
        st = regime(a, cut)
        sig = np.array([K.kind_signal(k, a, w) for k, w in TOOLS])        # (tools, n)
        reward = sig * fwd - cost * (sig != 0)
        q = np.zeros((9, len(TOOLS) + 1))                                  # +1 = abstain
        for _ in range(EPOCHS):
            for t in range(60, cut - HORIZON, HORIZON):
                s = int(st[t])
                act = int(rng.integers(q.shape[1])) if rng.random() < EPS else int(np.argmax(q[s]))
                rew = 0.0 if act == len(TOOLS) else float(reward[act, t])
                q[s, act] += ALPHA * (rew * 1e3 - q[s, act])
        trials += len(TOOLS) * 9
        policy = np.argmax(q, axis=1)
        chosen = np.array([0.0 if policy[st[t]] == len(TOOLS) else sig[policy[st[t]], t]
                           for t in range(n)])
        ho = K.evidence(chosen, fwd, cost, cut, n)
        now_state = int(st[-1])
        tool = int(policy[now_state])
        reps.append({"kind": "tool_choice_policy", "symbol": f.symbol,
                     "policy": {str(s): ("abstain" if p == len(TOOLS) else TOOLS[p][0])
                                for s, p in enumerate(policy)},
                     "current_state": now_state, "holdout": ho})
        if tool < len(TOOLS) and ho["mean_net"] > 0 and ho["n_active"] >= 20:
            kind, w = TOOLS[tool]
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: an AlphaQuanter-style Q-learned tool policy (9 regime states x "
                f"7 tools, learned on {cut} bars) kept a positive net mean on the holdout and "
                f"chooses the {kind} reader in the tape's current state",
                horizon_label=bundle.horizons[-1],
                ev={"state": now_state, "holdout": ho}, window=w, horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "agentic RL over tool calls (which reader, which "
                              "state)", "no distribution on the box and the tool caller is an "
                              "LLM; Q-learning over readers stands for it")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
