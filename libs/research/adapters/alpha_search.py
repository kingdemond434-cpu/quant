"""Alpha Search adapter -- five-agent opportunity/critique swarm with data adapters and a
walk-forward harness. Worker and architecture donor only (its own changelog was still
fixing simulation and cost defects); the adapter measures importability and routes the
critique loop to the desk's own LLM-free organs.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alpha_search"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "alpha_search"
HINT = "no PyPI distribution resolved on 2026-09-22; pin the repository first"
PROBE_NAMES = ('agents', 'adapters', 'walkforward')
WHY = "the swarm is LLM-driven; the research path carries no LLM (critique = the gauntlet)"
REBUILT_BY = "desks/mt5/research/sandboxes/coevolution_cell.py + the ten-gate gauntlet"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lib = A.library(MODULE)
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, f"{MODULE} is not importable here: {HINT}")
    rows: list[dict[str, Any]] = [A.api_probe(SYSTEM, lib, PROBE_NAMES)]
    rows.append({"kind": "REBUILT_ROUTE", "system": SYSTEM, "why": WHY, "rebuilt_by": REBUILT_BY})
    return A.packet(SYSTEM, bundle, trials=0, research_methods=rows,
                    note="importable; the upstream loop is not driven from this adapter")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
