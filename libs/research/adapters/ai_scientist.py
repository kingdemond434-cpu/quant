"""AI Scientist v2 adapter -- idea -> experiment -> interpretation -> review. Upstream is
LLM-driven; the adapter measures importability and routes the loop to the desk's
hypothesis -> gauntlet -> falsifier -> negative-knowledge machinery.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ai_scientist"
CAPABILITY_FAMILY = "automated_science"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "ai_scientist"
HINT = "git-only (SakanaAI/AI-Scientist-v2); pin the commit before provisioning"
PROBE_NAMES = ('ai_scientist', 'treesearch', 'perform_experiments')
WHY = "needs an LLM endpoint; the research path carries none"
REBUILT_BY = "miner_candidate_compiler -> external_gauntlet -> falsifier_run -> negative knowledge"


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
