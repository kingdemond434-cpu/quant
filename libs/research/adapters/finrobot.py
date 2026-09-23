"""finrobot adapter -- import probe only. LLM-driven analyst agents; the desk's acquisition organs
carry no LLM. While the upstream is absent the capability is carried by
desks/mt5/research/world_frontier.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "finrobot"
CAPABILITY_FAMILY = "information_acquisition"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "finrobot"
HINT = "pip install finrobot; the agents need an LLM key the sandbox does not carry"
PROBE_NAMES: tuple[str, ...] = (
    "agents",
    "data_source",
    "toolkits",
)
WHY = "LLM-driven analyst agents; the desk's acquisition organs carry no LLM"
REBUILT_BY = "desks/mt5/research/world_frontier.py"


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
