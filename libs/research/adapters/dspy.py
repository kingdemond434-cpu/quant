"""dspy adapter -- VERDICT: CANNOT WORK HERE, measured.

LLM-ONLY: DSPy optimises prompt programs and every evaluation of a candidate program is an LLM
call; the research path carries no LLM provider key, and there is no price computation in it to
rebuild.

The registry row (CENSUS_CLASS and friends) is read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'dspy'
CAPABILITY_FAMILY = 'prompt_optimization'
LICENCE_EXPECTED = 'MIT'
MODULE = 'dspy'
HINT = 'pip install dspy==3.3.1 in the sandbox venv'
CENSUS_CLASS = "c"
ROLE = "CANNOT WORK HERE"
VERDICT_REASON = (
    'LLM-ONLY: DSPy optimises prompt programs and every evaluation of a candidate program is '
    'an LLM call; the research path carries no LLM provider key, and there is no price '
    'computation in it to rebuild '
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
