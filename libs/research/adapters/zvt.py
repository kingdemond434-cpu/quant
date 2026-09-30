"""zvt adapter -- import probe only. a framework, not a mechanism: its recorders target China
A-shares (the event lane). While the upstream is absent the capability is carried by the desk's
own universe registry and recorders."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "zvt"
CAPABILITY_FAMILY = "data_tooling"
LICENCE_EXPECTED = "MIT"
MODULE = "zvt"
HINT = "pip install zvt; a full framework with its own database bootstrap"
PROBE_NAMES: tuple[str, ...] = (
    "init_log",
    "Stock",
    "__version__",
)
WHY = "a framework, not a mechanism: its recorders target China A-shares (the event lane)"
REBUILT_BY = "the desk's own universe registry and recorders"


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
