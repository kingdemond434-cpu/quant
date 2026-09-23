"""Quantifact adapter -- PAT-inspired point-in-time evidence with research plans and
contracts. No distribution or repository is pinned yet: the adapter measures
importability and names the desk organs that already carry the workflow.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantifact"
CAPABILITY_FAMILY = "research_reliability"
LICENCE_EXPECTED = "UNVERIFIED"
MODULE = "quantifact"
HINT = "no PyPI distribution resolved on 2026-09-22; pin the repository first"
PROBE_NAMES = ('plan', 'evidence', 'contract', 'cache')
WHY = (
    "no pinned upstream: the PIT plan/evidence/contract workflow is the desk's own research "
    "OS"
)
REBUILT_BY = "desks/mt5/research/standing_questions.py, data_scout.py, ingestion ledger"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lib = A.library(MODULE)
    if lib is None:
        return A.unmeasured(SYSTEM, bundle, f"{MODULE} is not importable here: {HINT}")
    rows: list[dict[str, Any]] = [A.api_probe(SYSTEM, lib, PROBE_NAMES)]
    rows.append({"kind": "REBUILT_ROUTE", "system": SYSTEM, "why": WHY, "rebuilt_by": REBUILT_BY})
    return A.packet(SYSTEM, bundle, trials=0, research_methods=rows,
                    note="importable; the upstream loop is not driven from this adapter")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
