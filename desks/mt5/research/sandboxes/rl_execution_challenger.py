"""RL EXECUTION CHALLENGER (sandbox only; never live) -- a tabular Q-learning policy over the
execution twin's own empirical fill/slippage distributions, and a QUBO order-slicing schedule
solved by simulated annealing, both as CHALLENGERS to the execution twin's baseline.

The twin (`research/execution_twin.py`) keeps `data/execution_twin_cases.jsonl`: every live
intent joined to its outcome (session, order type, spread, vol, filled, slippage). This cell
reads those cases READ-ONLY, buckets them into states (session x spread x vol), and learns a
policy over {market, pending_stop, passive_limit, wait_one_bar} whose rewards are SAMPLED from
the measured outcomes per state -- a missed passive fill costs the measured adverse move, a
market order costs the measured slippage. The learned policy's expected cost per state is set
beside the twin's baseline (what the desk actually did in that state), and the difference is
the only thing that leaves: a research method row, with n, never an order and never a change to
the gateway's algorithm. The QUBO challenger encodes child-order sizes in binary, prices
impact (quadratic in slice size) against timing risk (variance of what is left) from the
bundle's own realised vol, and anneals; its schedule is compared with uniform TWAP.

With no case file the RL leg is UNMEASURED by name and the QUBO leg still runs on the bars.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

from . import CellContext, system_id

CELL = "rl_execution_challenger"
SYSTEM = system_id(CELL)
CAPABILITY_FAMILY = "execution_engine"
UPSTREAM = ("ray", "openspiel")
FALLBACK = "tabular Q-learning over the twin's empirical outcomes + simulated-annealing QUBO"
CASES = "execution_twin_cases.jsonl"
ACTIONS = ("market", "pending_stop", "passive_limit", "wait_one_bar")
SESSIONS = ("asia", "london", "ny", "other")
EPISODES = 3000
MIN_CASES = 20
SLICES, BITS, ANNEAL_STEPS = 6, 3, 4000


def _bucket(v: float | None, cut: float) -> str:
    if v is None or not math.isfinite(v):
        return "unknown"
    return "high" if v > cut else "low"


def load_cases(ctx: CellContext) -> list[dict[str, Any]]:
    p = ctx.data / CASES
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with p.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return rows


def q_learning(cases: list[dict[str, Any]], *, seed: int) -> dict[str, Any]:
    """States from the cases; rewards sampled from each state's measured outcomes."""
    import numpy as np
    rng = np.random.default_rng(seed)
    spreads = [float(c["spread_frac"]) for c in cases if isinstance(c.get("spread_frac"),
                                                                    (int, float))]
    vols = [float(c["vol_frac"]) for c in cases if isinstance(c.get("vol_frac"), (int, float))]
    s_cut = float(np.median(spreads)) if spreads else 0.0
    v_cut = float(np.median(vols)) if vols else 0.0
    by_state: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    baseline: dict[str, list[float]] = defaultdict(list)
    for c in cases:
        session = str(c.get("session") or "other")
        session = session if session in SESSIONS else "other"
        state = f"{session}|spread_{_bucket(c.get('spread_frac'), s_cut)}|" \
                f"vol_{_bucket(c.get('vol_frac'), v_cut)}"
        otype = str(c.get("order_type") or c.get("algo") or "market")
        action = ("pending_stop" if "stop" in otype else "passive_limit" if "limit" in otype
                  else "market")
        filled = c.get("filled")
        slip = c.get("actual_slip_frac")
        vol = c.get("vol_frac") if isinstance(c.get("vol_frac"), (int, float)) else v_cut
        if filled is None or c.get("rejected"):
            continue
        cost = (float(slip) if isinstance(slip, (int, float)) else 0.0) if filled \
            else float(vol or 0.0)  # a miss costs the measured adverse move
        by_state[state][action].append(cost)
        baseline[state].append(cost)
    if not by_state:
        return {"status": "UNMEASURED", "why": "no resolved, unrejected cases"}
    states = sorted(by_state)
    Q = np.zeros((len(states), len(ACTIONS)))
    counts = np.zeros_like(Q)
    eps, lr = 0.2, 0.1
    for _ in range(EPISODES):
        si = int(rng.integers(len(states)))
        ai = int(rng.integers(len(ACTIONS))) if rng.random() < eps else int(np.argmax(Q[si]))
        pool = by_state[states[si]].get(ACTIONS[ai])
        if pool:
            reward = -float(rng.choice(pool))
        elif ACTIONS[ai] == "wait_one_bar":
            # waiting pays the measured vol as timing risk half the time, nothing otherwise
            reward = -float(rng.choice(baseline[states[si]])) * 0.5
        else:
            reward = -float(np.mean(baseline[states[si]]))  # no evidence: the state's mean
        Q[si, ai] += lr * (reward - Q[si, ai])
        counts[si, ai] += 1
    policy: dict[str, dict[str, Any]] = {}
    for i, s in enumerate(states):
        best = int(np.argmax(Q[i]))
        policy[s] = {"action": ACTIONS[best], "expected_cost_frac": float(-Q[i, best]),
                     "baseline_cost_frac": float(np.mean(baseline[s])),
                     "n_cases": len(baseline[s]), "actions_with_evidence": sorted(by_state[s])}
    gain = float(np.mean([p["baseline_cost_frac"] - p["expected_cost_frac"]
                          for p in policy.values()]))
    return {"status": "MEASURED", "states": len(states), "episodes": EPISODES, "policy": policy,
            "mean_cost_reduction_frac": gain, "n_cases": sum(len(v) for v in baseline.values())}


def qubo_slicing(vol: float, spread: float, *, seed: int) -> dict[str, Any]:
    """Child-order sizes q_k (units of 1/2^BITS of the parent) over SLICES bars minimising
    impact sum(q_k^2) + timing risk vol^2 * sum(remaining_k^2) + spread * sum(q_k), with the
    total pinned by a penalty. Binary encoding -> QUBO -> simulated annealing (numpy)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = SLICES * BITS
    unit = 1.0 / (2 ** BITS - 1)

    def sizes(x: Any) -> Any:
        return np.asarray([sum(int(x[k * BITS + b]) * (2 ** b) for b in range(BITS)) * unit
                           for k in range(SLICES)])

    def energy(x: Any) -> float:
        q = sizes(x)
        remaining = 1.0 - np.cumsum(q)
        pen = 25.0 * (q.sum() - 1.0) ** 2
        return float(np.sum(q * q) + (vol ** 2) * 1e4 * np.sum(remaining ** 2)
                     + spread * np.sum(q) + pen)

    x = rng.integers(0, 2, n)
    e = energy(x)
    best, best_e = x.copy(), e
    for step in range(ANNEAL_STEPS):
        t = 1.0 * (1.0 - step / ANNEAL_STEPS) + 1e-3
        i = int(rng.integers(n))
        x[i] ^= 1
        e2 = energy(x)
        if e2 <= e or rng.random() < math.exp(-(e2 - e) / t):
            e = e2
            if e < best_e:
                best, best_e = x.copy(), e
        else:
            x[i] ^= 1
    twap = np.full(SLICES, 1.0 / SLICES)
    twap_bits = np.zeros(n, dtype=int)
    q_best = sizes(best)
    remaining = 1.0 - np.cumsum(twap)
    e_twap = float(np.sum(twap * twap) + (vol ** 2) * 1e4 * np.sum(remaining ** 2)
                   + spread * np.sum(twap))
    _ = twap_bits
    return {"schedule": [round(float(v), 4) for v in q_best], "filled_share": float(q_best.sum()),
            "objective": best_e, "twap_objective": e_twap,
            "vs_twap": (e_twap - best_e) / max(abs(e_twap), 1e-12), "slices": SLICES,
            "bits": BITS, "steps": ANNEAL_STEPS}


def run(bundle: A.ResearchBundle, ctx: CellContext) -> ExternalResearchPacket:
    import numpy as np
    rows: list[dict[str, Any]] = []
    trials = 0
    cases = load_cases(ctx)
    if len(cases) < MIN_CASES:
        rows.append({"kind": "UNMEASURED", "leg": "rl_policy",
                     "why": f"{len(cases)} execution twin cases under {ctx.data / CASES} "
                            f"(need {MIN_CASES}); the twin must record more live intents"})
    else:
        trials += EPISODES
        res = q_learning(cases, seed=bundle.seed)
        rows.append({"kind": "execution_challenger", "leg": "rl_policy", **res,
                     "actions": list(ACTIONS),
                     "authority": "none: a challenger to the execution twin, sandbox only, "
                                  "never live; the gateway's algorithm is unchanged"})
    for f in bundle.frames("H1")[:3]:
        if len(f) < 100:
            continue
        trials += 1
        vol = float(np.std(f.log_returns()[-100:]))
        cost = bundle.cost_pts(f.symbol)
        tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
        px = float(f.close[-1])
        spread = (cost * tick / px) if np.isfinite(cost) and px > 0 else 1e-4
        rows.append({"kind": "qubo_slicing_challenger", "leg": "qubo", "symbol": f.symbol,
                     "vol_h1": vol, "spread_frac": spread,
                     **qubo_slicing(vol, spread, seed=bundle.seed),
                     "authority": "none: a schedule challenger for the execution twin; the "
                                  "annealer is a challenger only, never the router"})
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=rows,
                    note=f"{len(cases)} twin cases; QUBO on {min(3, len(bundle.frames('H1')))} "
                         f"frames")
