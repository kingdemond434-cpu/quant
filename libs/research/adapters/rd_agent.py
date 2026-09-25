"""rd_agent adapter -- import probe only. factor/model co-evolution driven by an LLM; the mechanism
is rebuilt without one. While the upstream is absent the capability is carried by
desks/mt5/research/sandboxes/coevolution_cell.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "rd_agent"
CAPABILITY_FAMILY = "factor_model_coevolution"
LICENCE_EXPECTED = "MIT"
MODULE = "rdagent"
HINT = "pip install rdagent; the loop is LLM-driven and needs a key"
PROBE_NAMES: tuple[str, ...] = (
    "app",
    "core",
    "scenarios",
)
WHY = "factor/model co-evolution driven by an LLM; the mechanism is rebuilt without one"
REBUILT_BY = "desks/mt5/research/sandboxes/coevolution_cell.py"


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
