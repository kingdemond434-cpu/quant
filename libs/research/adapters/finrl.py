"""finrl adapter -- REBUILT: FinRL's single-asset trading environment and a policy-gradient agent
(REINFORCE over a linear-softmax policy), trained on the train span of each H1 frame and read
on the unseen holdout. The learned policy's weights say WHICH state the agent learned to act
on -- persistence or reversion, at which lookback -- and that reading is donated as an exact
family recipe.

THE ENVIRONMENT (FinRL's StockTradingEnv, reduced to one CFD): state = (momentum z at three
lookbacks, RSI distance from 50, realised-vol z); action in {short, flat, long}; reward = the
position times the next bar's log return minus the bundle's own spread on every change of
position. The agent is FinRL's simplest policy-gradient learner: a linear softmax over the state,
trained by REINFORCE with a running-mean baseline over episodes of contiguous bars, seeded.

WHY NOT THE UPSTREAM. `finrl==0.3.7` installs on the box and does not import
(sandbox_install_ledger: PERMANENTLY_UNAVAILABLE -- finrl.meta reaches stable-baselines3 and a
torch stack that does not load there). The method -- an RL agent in a trading environment --
needs neither; its output here is a hypothesis, never a size (LAWS 5h).
"""
from __future__ import annotations

import math
from typing import Any

from libs.research import adapter_kit as K
from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "finrl"
CAPABILITY_FAMILY = "rl_policy_search"
LICENCE_EXPECTED = "MIT"
MODULE = "finrl"
RUNS_WITHOUT_LIBRARY = True
CENSUS_CLASS = "b"
ROLE = "hypothesis generator (policy-gradient agent in a trading environment, rebuilt)"
LOOKBACKS: tuple[int, ...] = (6, 24, 72)
EPISODES = 40
EPISODE_LEN = 120
LR = 0.05


def states(a: dict[str, Any]) -> Any:
    import numpy as np
    c = a["c"]
    r = np.diff(np.log(np.maximum(c, 1e-12)), prepend=np.log(max(c[0], 1e-12)))
    vol = A.realised_vol(r, 48)
    cols = []
    for lb in LOOKBACKS:
        m = np.full(c.shape[0], np.nan)
        m[lb:] = np.log(c[lb:] / np.maximum(c[:-lb], 1e-12))
        cols.append(m / np.maximum(vol * math.sqrt(lb), 1e-9))
    cols.append((K.rsi(c, 14) - 50.0) / 25.0)
    cols.append(K.zscore(np.nan_to_num(vol), 240))
    x = np.column_stack(cols)
    return np.clip(np.nan_to_num(x), -4.0, 4.0), r


def train(x: Any, r: Any, lo: int, hi: int, cost: float, seed: int) -> Any:
    """REINFORCE on the [lo, hi) span. Weights shape (n_features + 1, 3)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    d = x.shape[1] + 1
    w = np.zeros((d, 3))
    base = 0.0
    for _ in range(EPISODES):
        if hi - lo <= EPISODE_LEN + 2:
            break
        s0 = int(rng.integers(lo, hi - EPISODE_LEN - 1))
        grads = np.zeros_like(w)
        prev, ret = 0, 0.0
        for t in range(s0, s0 + EPISODE_LEN):
            phi = np.append(x[t], 1.0)
            z = phi @ w
            p = np.exp(z - z.max())
            p /= p.sum()
            k = int(rng.choice(3, p=p))
            pos = k - 1
            rew = pos * float(r[t + 1]) - (cost if pos != prev else 0.0)
            ret += rew
            g = -np.outer(phi, p)
            g[:, k] += phi
            grads += g
            prev = pos
        base = 0.9 * base + 0.1 * ret
        w += LR * (ret - base) * grads / EPISODE_LEN * 100.0
    return w


def act(x: Any, w: Any) -> Any:
    import numpy as np
    z = np.column_stack([x, np.ones(x.shape[0])]) @ w
    return np.argmax(z, axis=1) - 1


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    import numpy as np
    fr = K.frames(bundle, limit=8)
    if not fr:
        return A.unmeasured(SYSTEM, bundle, "no H1 frame carries 300 bars")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    reps: list[dict[str, Any]] = []
    cands: list[dict[str, Any]] = []
    for i, f in enumerate(fr):
        if deadline.expired():
            break
        a = K.arrays(f)
        x, r = states(a)
        n = x.shape[0] - 1
        cut = K.split(n)
        cost = K.cost_frac(bundle, f.symbol, a["c"])
        w = train(x, r, 250, cut, cost, bundle.seed + i)
        trials += EPISODES
        pos = act(x, w).astype(float)
        fwd1 = np.append(r[1:], np.nan)
        ev_tr = K.evidence_turnover(pos, fwd1, cost, 250, cut)
        ev_ho = K.evidence_turnover(pos, fwd1, cost, cut, n)
        # the policy's long-minus-short preference per feature is what it learned to act on
        pref = w[:-1, 2] - w[:-1, 0]
        j = int(np.argmax(np.abs(pref[:len(LOOKBACKS)])))
        lb = LOOKBACKS[j]
        kind = "momentum" if pref[j] >= 0 else "reversion"
        reps.append({"kind": "policy_weights", "symbol": f.symbol,
                     "features": [f"mom_z_{lb_}" for lb_ in LOOKBACKS] + ["rsi_dist", "vol_z"],
                     "long_minus_short": [round(float(v), 4) for v in pref],
                     "train": ev_tr, "holdout": ev_ho})
        if ev_ho["n_active"] >= 20 and ev_ho["mean_net"] > 0:
            cands.append(K.donate(
                A, SYSTEM, kind, f.symbol,
                f"{f.symbol} H1: a FinRL-style policy-gradient agent trained on the first "
                f"{cut} bars learned to act on the {lb}-bar momentum z with long-minus-short "
                f"weight {pref[j]:+.3f} and kept a positive net mean on the holdout; a "
                f"{kind} hypothesis at that lookback",
                horizon_label=bundle.horizons[-1],
                ev={"lookback": lb, "train": ev_tr, "holdout": ev_ho}, window=lb,
                horizon=max(2, lb // 2)))
    methods = [K.upstream_row(SYSTEM, MODULE, "trading environment + REINFORCE policy agent",
                              "finrl installs on the box and does not import (stable-baselines3/"
                              "torch); the environment and agent are reproduced in numpy")]
    return A.packet(SYSTEM, bundle, trials=trials, representations=reps, candidates=cands,
                    research_methods=methods)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
