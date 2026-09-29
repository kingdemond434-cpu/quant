"""awesome_prediction_market_tools capability route.

Rebuilt in the prediction-market donor cell (MT5 research), never as venue execution.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "awesome_prediction_market_tools"
CAPABILITY_FAMILY = "artifact_search"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/prediction_market_donor.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": "delta-scanned public source frontier, never evidence",
        "rebuilt_by": REBUILT_BY},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
