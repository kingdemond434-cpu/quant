"""tushare adapter -- ROUTED: DATA SOURCE: TuShare Pro index_daily / shibor (token-gated).

a DATA SURFACE for the China axis (single names are never hunted: two-lane law). Its rows
reach the desk through the free-stack hunter's `tushare` row, which reads TUSHARE_TOKEN from the
box environment (the desk's key list) and reports NEEDS_CREDENTIAL, never a zero, when it is not
set; the series is `data/lake/series/fs_tushare.parquet`, served by DataHub contract
`cnmkt.tushare` and minted into cells by `free_stack_proposer`. Whether it actually flows is a
MEASUREMENT the census reads from `reports/FREE_STACK_YIELD.json`.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'tushare'
CAPABILITY_FAMILY = 'data_source'
LICENCE_EXPECTED = 'BSD-3-Clause'
MODULE = 'tushare'
HINT = 'pip install tushare; the free tier needs a token the sandbox does not carry'
CENSUS_CLASS = "a"
ROLE = 'DATA SOURCE: TuShare Pro index_daily / shibor (token-gated)'
CONTRACTS: tuple[str, ...] = ('cnmkt.tushare',)
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
