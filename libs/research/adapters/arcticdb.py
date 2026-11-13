"""arcticdb adapter -- VERDICT: CANNOT WORK HERE, measured.

a STORE, not a researcher. LICENCE: BUSL-1.1 (source-available, not open source); production
use beyond its Additional Use Grant needs a commercial licence, and it is a STORE, not a source
or an engine -- the desk's PIT parquet lake already holds what it would

The verdict is this module's registry row (CENSUS_CLASS / VERDICT_REASON), read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`; the sandbox packet
carries the same reason, so the runner records UNMEASURED with a name rather than a silent probe.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'arcticdb'
CAPABILITY_FAMILY = 'data_tooling'
LICENCE_EXPECTED = 'BUSL-1.1'
MODULE = 'arcticdb'
HINT = 'pip install arcticdb; BUSL-1.1 is source-available, so DIRECT use stays licence-gated'
CENSUS_CLASS = "c"
ROLE = 'CANNOT WORK HERE'
VERDICT_REASON = (
    'LICENCE: BUSL-1.1 (source-available, not open source); production use beyond its '
    'Additional Use Grant needs a commercial licence, and it is a STORE, not a source or an '
    "engine -- the desk's PIT parquet lake already holds what it would "
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
