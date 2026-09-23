"""ai_hedge_fund adapter -- import probe only. an analyst-role swarm over an LLM; the research path
carries none. While the upstream is absent the capability is carried by the ten-gate gauntlet is
the desk's adversary."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ai_hedge_fund"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "MIT"
MODULE = "ai_hedge_fund"
HINT = "git-only (virattt/ai-hedge-fund); pin the commit first"
PROBE_NAMES: tuple[str, ...] = (
    "agents",
    "graph",
    "tools",
)
WHY = "an analyst-role swarm over an LLM; the research path carries none"
REBUILT_BY = "the ten-gate gauntlet is the desk's adversary"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """Measure the upstream if it is here; name it, with its install task, if it is not."""
    lib = A.library(MODULE)
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, MODULE + " is not importable here: " + HINT)
    rows: list[dict[str, Any]] = [A.api_probe(SYSTEM, lib, PROBE_NAMES)]
    rows.append({"kind": "REBUILT_ROUTE", "system": SYSTEM, "why": WHY, "rebuilt_by": REBUILT_BY})
    return A.packet(SYSTEM, bundle, trials=0, research_methods=rows,
                    note="importable; the upstream loop is not driven from this adapter")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
