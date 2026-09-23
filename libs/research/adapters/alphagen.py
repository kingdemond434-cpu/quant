"""AlphaGen adapter -- RL/GP formulaic-alpha pools. Git-only upstream (RL-MLDM/alphagen)
whose pool trainer needs its qlib data backend; here the adapter measures whether the
package imports, names its expression grammar, and routes the LLM-free formula search to
the desk's coevolution cell, which evolves formulaic factors on the bundle's own bars.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "alphagen"
CAPABILITY_FAMILY = "evolutionary_search"
LICENCE_EXPECTED = "MIT"
MODULE = "alphagen"
HINT = "provision github:RL-MLDM/alphagen at a pinned commit"
PROBE_NAMES = ('data', 'models', 'rl', 'utils')
WHY = "the pool trainer needs a qlib data backend the sandbox does not carry"
REBUILT_BY = "desks/mt5/research/sandboxes/coevolution_cell.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lib = A.library(MODULE)
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, f"{MODULE} is not importable here: {HINT}")
    rows: list[dict[str, Any]] = [A.api_probe(SYSTEM, lib, PROBE_NAMES)]
    rows.append({"kind": "REBUILT_ROUTE", "system": SYSTEM, "why": WHY, "rebuilt_by": REBUILT_BY})
    return A.packet(SYSTEM, bundle, trials=0, research_methods=rows,
                    note="importable; the upstream loop is not driven from this adapter")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
