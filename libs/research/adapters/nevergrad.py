"""Nevergrad adapter -- derivative-free search over a Bollinger reversion family -> descendants.

`mean_reversion_bollinger` parameters (window, k) are searched with OnePlusOne under a fixed
ask budget; every objective call is counted and charged. The recommendation and the best few
asks leave as descendant candidates with their parameters as evidence.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "nevergrad"
BUDGET, MAX_SYMBOLS, KEEP = 40, 3, 3


def bollinger_objective(frame: A.BarFrame, window: int, k: float, cost_pts: float,
                        tick: float) -> dict[str, float]:
    """Cost-charged Bollinger reversion: short above +k sigma, long below -k sigma, flat at the
    mean. Evidence fields only."""
    import numpy as np
    c = np.asarray(frame.close, dtype=float)
    window = int(max(5, window))
    if c.shape[0] <= window + 5:
        return {"objective_return": 0.0, "objective_drawdown": 0.0, "n_trades": 0.0}
    ma = np.convolve(c, np.ones(window) / window, mode="valid")
    sd = np.array([c[i:i + window].std() for i in range(c.shape[0] - window + 1)])
    px = c[window - 1:]
    z = (px - ma) / np.maximum(sd, 1e-12)
    pos = np.zeros(px.shape[0])
    cur = 0.0
    for i in range(px.shape[0]):
        if z[i] > k:
            cur = -1.0
        elif z[i] < -k:
            cur = 1.0
        elif (cur > 0 and z[i] >= 0) or (cur < 0 and z[i] <= 0):
            cur = 0.0
        pos[i] = cur
    rets = np.diff(np.log(np.maximum(px, 1e-12)))
    flips = np.abs(np.diff(pos)) > 0
    cost = (cost_pts * tick / np.maximum(px[1:], 1e-12)) if np.isfinite(cost_pts) else 0.0
    pnl = pos[:-1] * rets - flips * cost
    eq = np.cumsum(pnl)
    return {"objective_return": float(eq[-1]) if eq.size else 0.0,
            "objective_drawdown": float(np.max(np.maximum.accumulate(eq) - eq)) if eq.size
            else 0.0, "n_trades": float(flips.sum())}


def _objective(f: A.BarFrame, cost: float, tick: float,
               seen: list[tuple[float, int, float, dict[str, float]]]) -> Any:
    def objective(window: int, k: float) -> float:
        ev = bollinger_objective(f, int(window), float(k), cost, tick)
        seen.append((-ev["objective_return"], int(window), float(k), ev))
        return -ev["objective_return"] + 0.5 * ev["objective_drawdown"]
    return objective


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    ng = A.library("nevergrad")
    if ng is None:
        return A.unmeasured(SYSTEM, bundle, "nevergrad is not importable in this environment")
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    cands: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 300:
            continue
        cost, tick = bundle.cost_pts(f.symbol), (bundle.costs[f.symbol].tick_size
                                                 if f.symbol in bundle.costs else 0.0)
        seen: list[tuple[float, int, float, dict[str, float]]] = []
        try:
            param = ng.p.Instrumentation(
                window=ng.p.Scalar(lower=10, upper=60).set_integer_casting(),
                k=ng.p.Scalar(lower=1.0, upper=3.0))
            param.random_state.seed(bundle.seed)
            optimizer = ng.optimizers.OnePlusOne(parametrization=param, budget=BUDGET)
            optimizer.minimize(_objective(f, cost, tick, seen))
        except Exception as exc:
            trials += len(seen)
            cands.append(A.candidate(
                "mean_reversion_bollinger", [f.symbol],
                f"UNMEASURED: nevergrad raised {type(exc).__name__} on {f.symbol}",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"why": f"{type(exc).__name__}: {exc}"[:200]}))
            continue
        trials += len(seen)
        for loss, window, k, ev in sorted(seen, key=lambda t: t[0])[:KEEP]:
            cands.append(A.candidate(
                "mean_reversion_bollinger", [f.symbol],
                f"{f.symbol} H1 mean_reversion_bollinger descendant from nevergrad OnePlusOne "
                f"({BUDGET} asks): window {window} k {k:.2f}, cost-charged objective return "
                f"{-loss:+.4f} in the bundle window (in-sample; the gauntlet judges)",
                horizon=bundle.horizons[0], source=SYSTEM,
                evidence={"parameters": {"window": window, "k": round(k, 3)},
                          "objective_return": ev["objective_return"],
                          "objective_drawdown": ev["objective_drawdown"],
                          "n_trades": ev["n_trades"], "n_evaluated": len(seen)}))
    return A.packet(SYSTEM, bundle, trials=trials, candidates=cands)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
