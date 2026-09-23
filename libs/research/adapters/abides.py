"""ABIDES adapter -- an agent-based exchange with explicit latency (abides-jpmc-public). The
reference RMSC04 configuration is run once at the bundle's seed; the simulated L1 book is
donated as a DATASET (a world to test execution against) and its spread/imbalance
statistics as a representation. Nothing here is market data.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "abides"
CAPABILITY_FAMILY = "market_simulation"
LICENCE_EXPECTED = "BSD-3-Clause"
END_TIME = "10:30:00"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    core = A.library("abides_core.abides")
    cfgs = A.library("abides_markets.configs.rmsc04")
    if core is None or cfgs is None:
        return A.unmeasured(SYSTEM, bundle, "abides_core/abides_markets are not importable here "
                                            "(git-only upstream abides-sim/abides-jpmc-public)")
    import numpy as np
    try:
        cfg = cfgs.build_config(seed=bundle.seed, end_time=END_TIME)
        end_state = core.run(cfg)
        exchange = end_state["agents"][0]
        book = next(iter(exchange.order_books.values()))
        l1 = book.get_L1_snapshots()
        bids = np.asarray(l1["best_bids"], dtype=float)
        asks = np.asarray(l1["best_asks"], dtype=float)
    except Exception as exc:
        return A.packet(SYSTEM, bundle, trials=1, research_methods=[
            {"kind": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"[:200]}])
    n = int(min(bids.shape[0], asks.shape[0]))
    spread = (asks[:n, 1] - bids[:n, 1]) if n and bids.ndim == 2 else np.asarray([])
    ds = {"kind": "simulated_l1_book", "config": "rmsc04", "seed": bundle.seed,
          "n_snapshots": n, "fields": ["time", "best_bid", "best_ask", "bid_size", "ask_size"],
          "world": "agent-based, explicit latency; a test bed for execution challengers"}
    rep = {"kind": "simulated_microstructure", "spread_mean": float(spread.mean()) if spread.size
           else None, "spread_p90": float(np.percentile(spread, 90)) if spread.size else None,
           "representation": "how a book behaves under latency and agent mix; compare with the "
                             "desk's own tape before believing any of it"}
    return A.packet(SYSTEM, bundle, trials=1, datasets=[ds], representations=[rep])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
