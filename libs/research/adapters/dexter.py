"""dexter adapter -- VERDICT: CANNOT WORK HERE, measured.

an LLM-driven research agent. UNINSTALLABLE + LLM-ONLY: no distribution resolvable on the box
interpreter (sandbox_install_ledger NO_DISTRIBUTION_PINNED) and the agent's every step is an
LLM call over a keyed financial-data API; it has no deterministic price mechanism to rebuild

The verdict is this module's registry row (CENSUS_CLASS / VERDICT_REASON), read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`; the sandbox packet
carries the same reason, so the runner records UNMEASURED with a name rather than a silent probe.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'dexter'
CAPABILITY_FAMILY = 'information_acquisition'
LICENCE_EXPECTED = 'UNVERIFIED'
MODULE = 'dexter'
HINT = 'no wheel resolved on 2026-09-23; pin the repository first'
CENSUS_CLASS = "c"
ROLE = 'CANNOT WORK HERE'
VERDICT_REASON = (
    'UNINSTALLABLE + LLM-ONLY: no distribution resolvable on the box interpreter '
    "(sandbox_install_ledger NO_DISTRIBUTION_PINNED) and the agent's every step is an LLM "
    'call over a keyed financial-data API; it has no deterministic price mechanism to rebuild'
    ' '
)
CONTRACTS: tuple[str, ...] = ()
CLOCK = ""


def why() -> str:
    """The registry row as one sentence: where this system's work happens, or why it cannot."""
    return "CANNOT_WORK_HERE: " + VERDICT_REASON


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """Never a silent probe: the packet names the route or the measured verdict."""
    if A.library(MODULE) is None:
        return A.unmeasured(SYSTEM, bundle, MODULE + " is not importable here: " + HINT + ". "
                            + why())
    return A.unmeasured(SYSTEM, bundle, why())


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
