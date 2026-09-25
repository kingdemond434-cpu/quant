"""arcticdb adapter -- import probe only. a STORE, not a researcher: the desk's parquet universe
already holds the bars. While the upstream is absent the capability is carried by
desks/mt5/data/universe/*.parquet + libs/ops/release.py state discipline."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "arcticdb"
CAPABILITY_FAMILY = "data_tooling"
LICENCE_EXPECTED = "BUSL-1.1"
MODULE = "arcticdb"
HINT = ("pip install arcticdb; BUSL-1.1 is source-available, so DIRECT use stays "
    "licence-gated")
PROBE_NAMES: tuple[str, ...] = (
    "Arctic",
    "LibraryOptions",
    "__version__",
)
WHY = "a STORE, not a researcher: the desk's parquet universe already holds the bars"
REBUILT_BY = "desks/mt5/data/universe/*.parquet + libs/ops/release.py state discipline"


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
