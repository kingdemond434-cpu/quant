"""vnpy adapter -- import probe only. an execution framework, not a research engine; this desk
trades through MT5 only. While the upstream is absent the capability is carried by
desks/mt5/gateway.py + research/promoter.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "vnpy"
CAPABILITY_FAMILY = "execution_engine"
LICENCE_EXPECTED = "MIT"
MODULE = "vnpy"
HINT = "pip install vnpy; the event engine pulls Qt and broker gateways"
PROBE_NAMES: tuple[str, ...] = (
    "event",
    "trader",
    "__version__",
)
WHY = "an execution framework, not a research engine; this desk trades through MT5 only"
REBUILT_BY = "desks/mt5/gateway.py + research/promoter.py"


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
