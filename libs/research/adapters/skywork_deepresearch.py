"""Skywork DeepResearchAgent capability route; rebuilt without third-party runtime authority."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "skywork_deepresearch"
CAPABILITY_FAMILY = "agent_evolution"
LICENCE_EXPECTED = "MIT"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/agent_research_challenger.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM, "mechanism":
        "versioned resource evolution with propose-assess-commit-rollback and optimizer memory",
        "rebuilt_by": REBUILT_BY},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
