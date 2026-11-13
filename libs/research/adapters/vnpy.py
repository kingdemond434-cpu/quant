"""vnpy adapter -- VERDICT: CANNOT WORK HERE, measured.

an execution framework, not a research engine. UNINSTALLABLE + NON-MT5: no distribution for the
box interpreter/platform at vnpy==4.4.0 (sandbox_install_ledger PERMANENTLY_UNAVAILABLE), and
it is an execution framework for CN/IB gateways; this desk executes only through MT5/Fusion

The verdict is this module's registry row (CENSUS_CLASS / VERDICT_REASON), read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`; the sandbox packet
carries the same reason, so the runner records UNMEASURED with a name rather than a silent probe.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'vnpy'
CAPABILITY_FAMILY = 'execution_engine'
LICENCE_EXPECTED = 'MIT'
MODULE = 'vnpy'
HINT = 'pip install vnpy; the event engine pulls Qt and broker gateways'
CENSUS_CLASS = "c"
ROLE = 'CANNOT WORK HERE'
VERDICT_REASON = (
    'UNINSTALLABLE + NON-MT5: no distribution for the box interpreter/platform at vnpy==4.4.0'
    ' (sandbox_install_ledger PERMANENTLY_UNAVAILABLE), and it is an execution framework for '
    'CN/IB gateways; this desk executes only through MT5/Fusion '
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
