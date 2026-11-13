"""openbb adapter -- ROUTED.

DATA SOURCE: OpenBB's keyless OECD provider (composite leading indicators)

a federation of data providers, reached for axes, never for a verdict. The keyless OECD
provider OpenBB wraps (`openbb-oecd`: composite leading indicators) is fetched DIRECTLY from the
OECD SDMX REST endpoint by `desks/mt5/research/adapter_data.py` with an honest User-Agent and the
host's robots.txt, written PIT-stamped to `data/lake/series/oecd_cli.parquet`, served by DataHub
contract `oecd.cli` and minted into exogenous_conditioner cells on the MT5 instruments each
economy informs. The package itself is not imported into a desk process: AGPL-3.0 and a heavy
dependency tree, for an endpoint that needs neither.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'openbb'
CAPABILITY_FAMILY = 'data_source'
LICENCE_EXPECTED = 'AGPL-3.0'
MODULE = 'openbb'
HINT = 'pip install openbb; a large dependency tree, provisioned only when the pass may fetch'
CENSUS_CLASS = "a"
ROLE = "DATA SOURCE: OpenBB's keyless OECD provider (composite leading indicators)"
CONTRACTS: tuple[str, ...] = ('oecd.cli',)
CLOCK = 'hourly_cycle:adapter_data'
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
