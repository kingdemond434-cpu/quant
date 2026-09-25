"""qlib adapter -- import probe only. a factor/model laboratory whose benchmark data is China
A-share (the event lane). While the upstream is absent the capability is carried by
libs/research/adapters/featuretools.py + the desk's own feature compiler."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "qlib"
CAPABILITY_FAMILY = "representation_learning"
LICENCE_EXPECTED = "MIT"
MODULE = "qlib"
HINT = ("pip install pyqlib; it needs a provider_uri data directory the sandbox does not "
    "carry")
PROBE_NAMES: tuple[str, ...] = (
    "init",
    "workflow",
    "contrib",
)
WHY = "a factor/model laboratory whose benchmark data is China A-share (the event lane)"
REBUILT_BY = "libs/research/adapters/featuretools.py + the desk's own feature compiler"


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
