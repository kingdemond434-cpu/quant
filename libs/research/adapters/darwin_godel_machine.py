"""Darwin Goedel Machine adapter -- an archive of self-modifying agents under empirical
selection. Rostered REBUILT: no upstream code runs here; the adapter measures whether the
public package imports and names the desk's archive-with-selection equivalent.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "darwin_godel_machine"
CAPABILITY_FAMILY = "agent_evolution"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "dgm"
HINT = "git-only (jennyzzt/dgm); pin the commit before provisioning"
PROBE_NAMES = ('archive', 'agent', 'evolve')
WHY = (
    "REBUILT by the roster: self-modifying agents need an LLM and production merge "
    "authority, both refused by the sandbox law"
)
REBUILT_BY = "desks/mt5/research/sandboxes/coevolution_cell.py (archive + selection, no self-merge)"


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
