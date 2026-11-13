"""quantrocket adapter -- VERDICT: CANNOT WORK HERE, measured.

LICENCE: QuantRocket is a commercial, licensed installation (Proprietary); the client package
only talks to a licensed deployment the desk does not hold, and its data is the vendor's
subscription feed.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'quantrocket'
CAPABILITY_FAMILY = 'data_tooling'
LICENCE_EXPECTED = 'Proprietary'
MODULE = 'quantrocket'
HINT = "pip install quantrocket-client==2.11.0.0; a licensed installation is the principal's act"
CENSUS_CLASS = "c"
ROLE = "CANNOT WORK HERE"
VERDICT_REASON = (
    'LICENCE: QuantRocket is a commercial, licensed installation (Proprietary); the client '
    'package only talks to a licensed deployment the desk does not hold, and its data is the '
    "vendor's subscription feed "
)
CONTRACTS: tuple[str, ...] = ()
CLOCK = ""
ROUTED_TO = ""


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
