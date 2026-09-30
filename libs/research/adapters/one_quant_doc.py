"""Route for the independently rebuilt Chan structural-price documentation donor."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "one_quant_doc"
CAPABILITY_FAMILY = "representation_learning"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/chan_structure_lab.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": ("PIT-confirmed fractals, recursive legs, overlapping equilibrium zones, "
                      "structural momentum expenditure and cross-timeframe marginal context"),
        "rebuilt_by": REBUILT_BY,
        "rejected": ("upstream profitability claims, chart-finalized hindsight structures and "
                     "unlicensed implementation code")},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
