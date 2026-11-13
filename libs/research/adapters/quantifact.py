"""quantifact adapter -- VERDICT: CANNOT WORK HERE, measured.

UNINSTALLABLE + NO MECHANISM: no distribution resolvable on the box (NO_DISTRIBUTION_PINNED),
and what it contributes is a research-workflow pattern (PIT plan, evidence, contract, cache)
the desk already runs as standing_questions.py, data_scout.py and the ingestion ledger; it has
no price mechanism to donate cells from.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'quantifact'
CAPABILITY_FAMILY = 'research_reliability'
LICENCE_EXPECTED = 'UNVERIFIED'
MODULE = 'quantifact'
HINT = 'no PyPI distribution resolved on 2026-09-22; pin the repository first'
CENSUS_CLASS = "c"
ROLE = "CANNOT WORK HERE"
VERDICT_REASON = (
    'UNINSTALLABLE + NO MECHANISM: no distribution resolvable on the box '
    '(NO_DISTRIBUTION_PINNED), and what it contributes is a research-workflow pattern (PIT '
    'plan, evidence, contract, cache) the desk already runs as standing_questions.py, '
    'data_scout.py and the ingestion ledger; it has no price mechanism to donate cells from '
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
