"""kronos adapter -- import probe only. a market foundation model: representations only, never a
forecast with authority. While the upstream is absent the capability is carried by
libs/research/adapters/chronos2.py, timesfm.py and moment.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "kronos"
CAPABILITY_FAMILY = "foundation_model"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "kronos"
HINT = "no wheel resolved on 2026-09-23; weights would come from a local cache only"
PROBE_NAMES: tuple[str, ...] = (
    "Kronos",
    "predict",
    "__version__",
)
WHY = "a market foundation model: representations only, never a forecast with authority"
REBUILT_BY = "libs/research/adapters/chronos2.py, timesfm.py and moment.py"


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
