"""OpenSpiel adapter -- the execution game as a matrix game solved by CFR: the desk chooses
market vs passive, the counterparty is informed or uninformed, payoffs are the bundle's own
spread and realised vol. The equilibrium mix is a research method about WHEN passive
execution is worth its adverse selection; nothing here places an order.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "openspiel"
CAPABILITY_FAMILY = "game_theory"
LICENCE_EXPECTED = "Apache-2.0"
MAX_SYMBOLS = 4
ITERS = 200


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    ps = A.library("pyspiel")
    cfr = A.library("open_spiel.python.algorithms.cfr")
    if ps is None or cfr is None:
        return A.unmeasured(SYSTEM, bundle, "open_spiel is not importable here (pip install "
                                            "open_spiel==2.0.2)")
    import numpy as np
    deadline = A.Deadline(bundle.compute_budget_s)
    trials = 0
    rows: list[dict[str, Any]] = []
    for f in bundle.frames("H1")[:MAX_SYMBOLS]:
        if deadline.expired() or len(f) < 200:
            continue
        cost = bundle.cost_pts(f.symbol)
        tick = bundle.costs[f.symbol].tick_size if f.symbol in bundle.costs else 0.0
        px = float(f.close[-1])
        spread = (cost * tick / px) if np.isfinite(cost) and px > 0 else 1e-4
        vol = float(np.std(f.log_returns()[-200:]))
        # row = desk (market, passive); col = flow (informed, uninformed); payoff in return units
        row_pay = [[-spread, -spread], [-vol, spread / 2.0]]
        col_pay = [[spread, 0.0], [vol, -spread / 2.0]]
        trials += 1
        try:
            game = ps.create_matrix_game("exec", "Execution", ["market", "passive"],
                                         ["informed", "uninformed"], row_pay, col_pay)
            solver = cfr.CFRSolver(game)
            for _ in range(ITERS):
                solver.evaluate_and_update_policy()
            root = game.new_initial_state()
            probs = solver.average_policy().action_probabilities(root, 0)
            mix = {game.action_to_string(0, a): float(p) for a, p in probs.items()}
        except Exception as exc:
            rows.append({"kind": "UNMEASURED", "symbol": f.symbol,
                         "why": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        rows.append({"kind": "equilibrium_evidence", "symbol": f.symbol, "spread_frac": spread,
                     "vol_h1": vol, "desk_mix": mix, "iterations": ITERS,
                     "method": "CFR on a 2x2 execution game",
                     "authority": "none: a challenger's view for the execution twin"})
    return A.packet(SYSTEM, bundle, trials=trials, research_methods=rows)


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
