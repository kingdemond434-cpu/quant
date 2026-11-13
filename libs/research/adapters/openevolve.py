"""openevolve adapter -- ROUTED to the desk's rebuilt cell.

OpenEvolve's evaluator-driven program evolution (islands, an archive, an evaluator deciding) is
REBUILT LLM-free in `research/sandboxes/coevolution_cell.py`, which names openevolve in
UPSTREAM and runs on the sandbox runner's hourly clock. The upstream's mutation operator is an
LLM endpoint the research path does not carry, so the package is not driven.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'openevolve'
CAPABILITY_FAMILY = 'program_evolution'
LICENCE_EXPECTED = 'Apache-2.0'
MODULE = 'openevolve'
HINT = 'pip install openevolve==0.3.2 in the sandbox venv'
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
