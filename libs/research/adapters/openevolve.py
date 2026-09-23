"""OpenEvolve adapter -- AlphaEvolve-style evolution of code with islands and MAP-Elites
dimensions. Upstream is LLM-driven and the research path carries no LLM, so the adapter
measures importability and routes the evaluator-driven loop to the coevolution cell.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "openevolve"
CAPABILITY_FAMILY = "program_evolution"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "openevolve"
HINT = "pip install openevolve==0.3.2 in the sandbox venv"
PROBE_NAMES = ('OpenEvolve', 'config', 'database', 'evaluator')
WHY = "needs an LLM endpoint; the research path carries none (brief: no LLM/API dependency)"
REBUILT_BY = "desks/mt5/research/sandboxes/coevolution_cell.py (evaluator-driven, LLM-free)"


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
