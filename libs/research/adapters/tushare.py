"""tushare adapter -- import probe only. a DATA SURFACE for the China axis; single names are never
hunted (two-lane law). While the upstream is absent the capability is carried by
libs/research/axis_screen.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tushare"
CAPABILITY_FAMILY = "data_source"
LICENCE_EXPECTED = "BSD-3-Clause"
MODULE = "tushare"
HINT = "pip install tushare; the free tier needs a token the sandbox does not carry"
PROBE_NAMES: tuple[str, ...] = (
    "pro_api",
    "get_hist_data",
    "__version__",
)
WHY = "a DATA SURFACE for the China axis; single names are never hunted (two-lane law)"
REBUILT_BY = "libs/research/axis_screen.py"


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
