"""nexquant adapter -- REBUILT: deterministic EXPLORE/EXPLOIT search. Arms are (mechanism kind,
window); the train span is cut into consecutive blocks and an upper-confidence-bound (UCB1)
bandit pulls one arm per block, rewarded by that arm's net evidence on the block. Compute goes
where evidence accumulates instead of being spread over a grid, which is the upstream's point:
a throughput donor. After the train span the most-pulled arm (the bandit's exploitation
choice, not the best single block) is read on the holdout and donated when it holds.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED).
UCB over arms on walk-forward blocks is the mechanism.
"""
from __future__ import annotations

import math
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "nexquant"
CAPABILITY_FAMILY = "evolutionary_search"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "nexquant"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (UCB1 bandit over mechanism arms on walk-forward blocks)"
HORIZON = 12
BLOCK = 48
ARMS: tuple[tuple[str, int], ...] = tuple((k, w) for k in ("momentum", "trend", "reversion",
                                                           "band_reversion", "breakout",
                                                           "squeeze", "pullback")
                                          for w in (12, 48))


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
        fwd = np.nan_to_num(K.forward_return(a["c"], HORIZON))
        sig = [K.kind_signal(k, a, w) for k, w in ARMS]
        pulls = np.zeros(len(ARMS))
        total = np.zeros(len(ARMS))
        blocks = list(range(100, cut - HORIZON - BLOCK, BLOCK))
        for b, lo in enumerate(blocks, start=1):
            if b <= len(ARMS):
                arm = b - 1
            else:
                ucb = total / np.maximum(pulls, 1) + 1e-3 * np.sqrt(2 * math.log(b) /
                                                                    np.maximum(pulls, 1))
                arm = int(np.argmax(ucb))
            s = sig[arm][lo:lo + BLOCK]
            rew = float(np.sum(s * fwd[lo:lo + BLOCK] - cost * (s != 0)))
            pulls[arm] += 1
            total[arm] += rew
            trials += 1
        top = int(np.argmax(pulls))
        kind, w = ARMS[top]
        ho = K.evidence(sig[top], fwd, cost, cut, n)
        reps.append({"kind": "ucb_bandit", "symbol": f.symbol, "blocks": len(blocks),
                     "pulls": {f"{k}:{ww}": int(p) for (k, ww), p in zip(ARMS, pulls,
                                                                         strict=True)},
                     "exploited": f"{kind}:{w}", "holdout": ho})
        if ho["mean_net"] > 0 and ho["n_active"] >= 20 and pulls[top] > 1:
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: a NexQuant-style UCB1 bandit over {len(ARMS)} mechanism arms "
                f"exploited {kind} at {w} bars ({int(pulls[top])} of {len(blocks)} walk-forward "
                f"blocks) and that arm held on the holdout", horizon_label=bundle.horizons[-1],
                ev={"pulls": int(pulls[top]), "blocks": len(blocks), "holdout": ho},
                window=w, horizon=HORIZON))
    methods = [K.upstream_row(SYSTEM, MODULE, "explore/exploit UCB search over arms",
                              "no distribution resolvable on the box; UCB1 is reproduced")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
