"""DSPy adapter -- program-level optimisation of prompts and demonstrations (MIPROv2, GEPA).
Prompt optimisation needs an LLM and the research path carries none: the adapter measures
importability and records the route.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "dspy"
CAPABILITY_FAMILY = "prompt_optimization"
LICENCE_EXPECTED = "MIT"
MODULE = "dspy"
HINT = "pip install dspy==3.3.1 in the sandbox venv"
PROBE_NAMES = ('Module', 'Predict', 'MIPROv2', 'GEPA')
WHY = "prompt optimisation needs an LLM; the research path carries none"
REBUILT_BY = "no desk equivalent by design (LLM-free research path)"


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
