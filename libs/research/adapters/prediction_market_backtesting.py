"""prediction_market_backtesting capability route.

Rebuilt in the prediction-market donor cell (MT5 research), never as venue execution.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "prediction_market_backtesting"
CAPABILITY_FAMILY = "replay_parity"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/prediction_market_donor.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": "event replay and experiment contracts; foreign engine not required",
        "rebuilt_by": REBUILT_BY},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
