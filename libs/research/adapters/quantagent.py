"""quantagent adapter -- REBUILT: QuantAgent's specialist agents for short-horizon trading with
their vision/LLM reading replaced by the geometry it describes. The PATTERN agent finds double
tops and double bottoms (two swing extremes within 0.5 ATR of each other, a neckline between
them) and reads the neckline break; the TREND agent fits a regression channel and reads the
close's position in it (riding the slope vs fading the band); the DECISION agent takes the two
when they agree. Each agent's reading is scored on train and holdout; the agent that carried
evidence onto the holdout is donated as an exact recipe -- a neckline break as level_breakout
at its modal hour, a channel ride as trend_ma_cross, a channel fade as range_reversion.

WHY NOT THE UPSTREAM. No distribution resolvable on the box (ledger: NO_DISTRIBUTION_PINNED)
and its agents read rendered charts through an LLM. The patterns they are asked to see are
deterministic definitions.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantagent"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "quantagent"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (pattern / trend / decision agents, rebuilt)"
HORIZON = 8
SWING = 5
LOOK = 60
CHANNEL = 48


def pattern_signal(a: dict[str, Any]) -> Any:
    """+1 on the bar a double bottom's neckline breaks up, -1 on a double top's break down."""
    import numpy as np
    h, lo, c = a["h"], a["l"], a["c"]
    n = c.shape[0]
    at = np.nan_to_num(K.atr(h, lo, c, 20))
    sig = np.zeros(n)
    lows, highs = [], []
    for i in range(SWING, n):
        j = i - SWING   # a swing point is confirmed SWING bars after it, never before
        if j >= SWING:
            if lo[j] == np.min(lo[j - SWING:j + SWING + 1]):
                lows.append(j)
            if h[j] == np.max(h[j - SWING:j + SWING + 1]):
                highs.append(j)
        lw = [k for k in lows if i - LOOK <= k < i]
        if len(lw) >= 2 and abs(lo[lw[-1]] - lo[lw[-2]]) <= 0.5 * at[i]:
            neck = float(np.max(h[lw[-2]:lw[-1] + 1]))
            if c[i] > neck >= c[i - 1]:
                sig[i] = 1.0
        hg = [k for k in highs if i - LOOK <= k < i]
        if len(hg) >= 2 and abs(h[hg[-1]] - h[hg[-2]]) <= 0.5 * at[i]:
            neck = float(np.min(lo[hg[-2]:hg[-1] + 1]))
            if c[i] < neck <= c[i - 1]:
                sig[i] = -1.0
    return sig


def channel(a: dict[str, Any]) -> tuple[Any, Any]:
    """(ride, fade): ride the regression slope when the close is inside the channel's middle,
    fade the band when it closes beyond 2 residual sigmas."""
    import numpy as np
    c = a["c"]
    n = c.shape[0]
    t = np.arange(CHANNEL, dtype=float)
    tc = t - t.mean()
    ride, fade = np.zeros(n), np.zeros(n)
    for i in range(CHANNEL - 1, n):
        y = c[i - CHANNEL + 1:i + 1]
        b = float(np.dot(tc, y - y.mean()) / np.dot(tc, tc))
        res = y - (y.mean() + b * tc)
        sd = float(res.std())
        if sd <= 0:
            continue
        z = res[-1] / sd
        if abs(z) < 1.0:
            ride[i] = np.sign(b)
        elif abs(z) > 2.0:
            fade[i] = -np.sign(z)
    return ride, fade


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
        fwd = K.forward_return(a["c"], HORIZON)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        pat = pattern_signal(a)
        ride, fade = channel(a)
        decision = np.where((pat != 0) & (np.sign(pat) == np.sign(ride + fade)), pat, 0.0)
        agents = {"pattern": pat, "trend_ride": ride, "trend_fade": fade, "decision": decision}
        trials += len(agents)
        table = {k: {"train": K.evidence(v, fwd, cost, 0, cut),
                     "holdout": K.evidence(v, fwd, cost, cut, n)} for k, v in agents.items()}
        reps.append({"kind": "specialist_agents", "symbol": f.symbol, "agents": table,
                     "pattern_events": int(np.sum(pat != 0))})
        ok = [(t["holdout"]["t_ratio"], k) for k, t in table.items()
              if t["train"]["mean_net"] > 0 and t["holdout"]["mean_net"] > 0
              and t["holdout"]["n_active"] >= 8]
        if not ok:
            continue
        _, who = max(ok)
        if who in ("pattern", "decision"):
            hrs = Counter(int(a["hour"][i]) for i in np.where(agents[who] != 0)[0])
            hour = hrs.most_common(1)[0][0] if hrs else 7
            kind, w = "breakout", 12
        elif who == "trend_ride":
            kind, w, hour = "trend", CHANNEL, 7
        else:
            kind, w, hour = "range_reversion", CHANNEL, 7
        cands.append(K.donate(
            A, SYSTEM, kind, f.symbol,
            f"{f.symbol} H1: QuantAgent's {who} agent (double top/bottom necklines and a "
            f"{CHANNEL}-bar regression channel) carried positive net evidence from train onto "
            f"the holdout; a {kind} hypothesis", horizon_label=bundle.horizons[0],
            ev={"agent": who, **table[who]}, window=w, horizon=HORIZON, hour=hour))
    methods = [K.upstream_row(SYSTEM, MODULE, "pattern / trend / decision specialist agents",
                              "no distribution resolvable on the box; its agents read chart "
                              "images through an LLM, here the geometry is computed")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
