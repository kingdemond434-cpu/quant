"""Archived Quantrade route; only desk-owned research patterns are executed."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantrade"
CAPABILITY_FAMILY = "research_reproduction"
LICENCE_EXPECTED = "LGPL-3.0"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/quantrade_challenger.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": ("directional inversion, volatility-conditioned activation, excursion "
                      "research and portfolio-versus-champion comparison"),
        "rebuilt_by": REBUILT_BY,
        "rejected": "deprecated website, MT4/WebDAV stack, private strategies and raw rankings"},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
