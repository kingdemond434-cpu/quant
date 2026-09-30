"""PicoAgents capability route; rebuilt as deterministic orchestration contracts."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "picoagents"
CAPABILITY_FAMILY = "research_reliability"
LICENCE_EXPECTED = "Apache-2.0"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/agent_research_challenger.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": "termination algebra, step checkpoints, replayable optimization trace",
        "rebuilt_by": REBUILT_BY},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
