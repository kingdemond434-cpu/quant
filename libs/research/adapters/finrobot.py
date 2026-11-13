"""finrobot adapter -- VERDICT: CANNOT WORK HERE, measured.

LLM-driven analyst agents. LLM-KEY + TERMS: the agents cannot import or step without an LLM
provider key (sandbox_install_ledger REJECTED_WITH_EVIDENCE: OPENAI_API_KEY / config_api_keys
at import and every step), and its analyst tools read keyed vendors (FMP, Finnhub, SEC); there
is no deterministic price mechanism to rebuild

The verdict is this module's registry row (CENSUS_CLASS / VERDICT_REASON), read hourly by
`desks/mt5/research/adapter_census.py` into `reports/ADAPTER_CENSUS.json`; the sandbox packet
carries the same reason, so the runner records UNMEASURED with a name rather than a silent probe.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'finrobot'
CAPABILITY_FAMILY = 'information_acquisition'
LICENCE_EXPECTED = 'Apache-2.0'
MODULE = 'finrobot'
HINT = 'pip install finrobot; the agents need an LLM key the sandbox does not carry'
CENSUS_CLASS = "c"
ROLE = 'CANNOT WORK HERE'
VERDICT_REASON = (
    'LLM-KEY + TERMS: the agents cannot import or step without an LLM provider key '
    '(sandbox_install_ledger REJECTED_WITH_EVIDENCE: OPENAI_API_KEY / config_api_keys at '
    'import and every step), and its analyst tools read keyed vendors (FMP, Finnhub, SEC); '
    'there is no deterministic price mechanism to rebuild '
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
