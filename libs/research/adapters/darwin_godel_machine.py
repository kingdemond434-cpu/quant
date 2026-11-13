"""darwin_godel_machine adapter -- ROUTED to the desk's rebuilt cell.

The Darwin Goedel Machine's archive with performance-and-novelty parent selection is REBUILT in
`research/sandboxes/coevolution_cell.py` (archive + selection, no self-merge into production
code) on the sandbox runner's hourly clock. Self-modification of the agent's own code needs an
LLM and a production merge, which no research process here may do.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'darwin_godel_machine'
CAPABILITY_FAMILY = 'agent_evolution'
LICENCE_EXPECTED = 'Apache-2.0'
MODULE = 'dgm'
HINT = 'git-only (jennyzzt/dgm); pin the commit before provisioning'
CENSUS_CLASS = "b"
ROLE = "research engine, rebuilt as cell:coevolution_cell"
CONTRACTS: tuple[str, ...] = ()
CLOCK = "hourly_cycle:sandbox_runner"
ROUTED_TO = 'sandbox:cell:coevolution_cell'
VERDICT_REASON = ""


def why() -> str:
    """The registry row as one sentence: where this system's work happens, or why it cannot."""
    return "ROUTED: " + ROLE + " (generator " + ROUTED_TO + ") on " + CLOCK


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """Never a silent probe: the packet names the route or the measured verdict."""
    if A.library(MODULE) is None:
        return A.unmeasured(SYSTEM, bundle, MODULE + " is not importable here: " + HINT + ". "
                            + why())
    return A.unmeasured(SYSTEM, bundle, why())


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
