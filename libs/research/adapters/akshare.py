"""akshare adapter -- import probe only. a DATA SURFACE, never a hypothesis source: its rows become
PIT axis series or nothing. While the upstream is absent the capability is carried by
libs/research/axis_screen.py + the desk's own MT5 universe collector."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "akshare"
CAPABILITY_FAMILY = "data_source"
LICENCE_EXPECTED = "MIT"
MODULE = "akshare"
HINT = "pip install akshare (no wheel pinned on this interpreter yet)"
PROBE_NAMES: tuple[str, ...] = (
    "stock_zh_a_hist",
    "futures_main_sina",
    "macro_china_cpi",
)
WHY = "a DATA SURFACE, never a hypothesis source: its rows become PIT axis series or nothing"
REBUILT_BY = "libs/research/axis_screen.py + the desk's own MT5 universe collector"


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
