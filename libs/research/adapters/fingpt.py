"""fingpt adapter -- VERDICT: CANNOT WORK HERE, measured.

financial NLP over LLM weights. UNINSTALLABLE: git-only with no distribution resolvable on the
box (NO_DISTRIBUTION_PINNED) and it needs LLM weights plus a torch stack the research path does
not carry; the mechanism is the model itself, so nothing remains to rebuild in numpy

The verdict is this module's registry row (CENSUS_CLASS / VERDICT_REASON), read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`; the sandbox packet
carries the same reason, so the runner records UNMEASURED with a name rather than a silent probe.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'fingpt'
CAPABILITY_FAMILY = 'financial_nlp'
LICENCE_EXPECTED = 'MIT'
MODULE = 'fingpt'
HINT = 'git-only (AI4Finance-Foundation/FinGPT); it needs model weights and a torch stack'
CENSUS_CLASS = "c"
ROLE = 'CANNOT WORK HERE'
VERDICT_REASON = (
    'UNINSTALLABLE: git-only with no distribution resolvable on the box '
    '(NO_DISTRIBUTION_PINNED) and it needs LLM weights plus a torch stack the research path '
    'does not carry; the mechanism is the model itself, so nothing remains to rebuild in '
    'numpy '
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
