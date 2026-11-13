"""akshare adapter -- ROUTED.

DATA SOURCE: AKShare's public upstreams (Eastmoney index klines, Sina futures klines)

a DATA SURFACE, never a hypothesis source. Its rows reach the desk through the free-stack
hunter's `akshare` source row (`desks/mt5/data/free_stack_sources.json`; the package when it is
importable, its public upstreams fetched directly otherwise), land PIT-stamped in
`data/lake/series/fs_akshare.parquet`, are served by DataHub contract `cnmkt.akshare`
(`libs/data/datahub_adapters.py`) and become exogenous_conditioner / alt_series cells through
`free_stack_proposer` -> the gauntlet. Over a bar bundle there is nothing for it to run, so the
sandbox packet says so by name.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'akshare'
CAPABILITY_FAMILY = 'data_source'
LICENCE_EXPECTED = 'MIT'
MODULE = 'akshare'
HINT = 'pip install akshare (no wheel pinned on this interpreter yet)'
CENSUS_CLASS = "a"
ROLE = "DATA SOURCE: AKShare's public upstreams (Eastmoney index klines, Sina futures klines)"
CONTRACTS: tuple[str, ...] = ('cnmkt.akshare',)
CLOCK = 'hourly_cycle:free_stack_hunt'
VERDICT_REASON = ""


def why() -> str:
    """The registry row as one sentence: where this system's work happens, or why it cannot."""
    via = (" as DataHub contract(s) " + ", ".join(CONTRACTS)) if CONTRACTS else ""
    return "ROUTED: " + ROLE + " -- runs on " + CLOCK + via + "; nothing to run over a bar bundle"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """Never a silent probe: the packet names the route or the measured verdict."""
    if A.library(MODULE) is None:
        return A.unmeasured(SYSTEM, bundle, MODULE + " is not importable here: " + HINT + ". "
                            + why())
    return A.unmeasured(SYSTEM, bundle, why())


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
