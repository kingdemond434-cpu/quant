"""alphagen adapter -- ROUTED to the desk's rebuilt cell.

AlphaGen's formulaic-alpha pool search is REBUILT as the desk's own cell
`research/sandboxes/coevolution_cell.py` (numpy factor grammar x model zoo, alternating co-
evolution, walk-forward; it names alphagen in UPSTREAM). That cell runs on the sandbox runner's
hourly clock and donates through the same exit; its cells are this adapter's cells. The
upstream pool trainer needs a qlib data backend and a pinned git commit, neither of which the
box carries.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'alphagen'
CAPABILITY_FAMILY = 'evolutionary_search'
LICENCE_EXPECTED = 'MIT'
MODULE = 'alphagen'
HINT = 'provision github:RL-MLDM/alphagen at a pinned commit'
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
