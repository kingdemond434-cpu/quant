"""tradingagents adapter -- import probe only. fundamentals/news/sentiment debate over an LLM; this
desk debates with gates. While the upstream is absent the capability is carried by
libs/research/arena.py + the ten gates."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tradingagents"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "tradingagents"
HINT = "pip install tradingagents; the debate needs an LLM key"
PROBE_NAMES: tuple[str, ...] = (
    "graph",
    "agents",
    "default_config",
)
WHY = "fundamentals/news/sentiment debate over an LLM; this desk debates with gates"
REBUILT_BY = "libs/research/arena.py + the ten gates"


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
