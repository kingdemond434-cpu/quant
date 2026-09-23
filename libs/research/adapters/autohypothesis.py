"""autohypothesis adapter -- import probe only. an independent mutation laboratory: worth
measuring, never authoritative. While the upstream is absent the capability is carried by
libs/research/alpha_genome.py + the hypothesis compiler."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "autohypothesis"
CAPABILITY_FAMILY = "evolutionary_search"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "autohypothesis"
HINT = "no wheel resolved on 2026-09-23; pin the repository first"
PROBE_NAMES: tuple[str, ...] = (
    "mutate",
    "Hypothesis",
    "run",
)
WHY = "an independent mutation laboratory: worth measuring, never authoritative"
REBUILT_BY = "libs/research/alpha_genome.py + the hypothesis compiler"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """Measure the upstream if it is here; name it, with its install task, if it is not."""
    lib = A.library(MODULE)
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, MODULE + " is not importable here: " + HINT)
    rows: list[dict[str, Any]] = [A.api_probe(SYSTEM, lib, PROBE_NAMES)]
    rows.append({"kind": "REBUILT_ROUTE", "system": SYSTEM, "why": WHY, "rebuilt_by": REBUILT_BY})
    return A.packet(SYSTEM, bundle, trials=0, research_methods=rows,
                    note="importable; the upstream loop is not driven from this adapter")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
