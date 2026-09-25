"""fingpt adapter -- import probe only. financial NLP over LLM weights; the research path carries
no LLM. While the upstream is absent the capability is carried by the desk's own text organs
(deep_forest_miner.py) on registered grounds."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "fingpt"
CAPABILITY_FAMILY = "financial_nlp"
LICENCE_EXPECTED = "MIT"
MODULE = "fingpt"
HINT = "git-only (AI4Finance-Foundation/FinGPT); it needs model weights and a torch stack"
PROBE_NAMES: tuple[str, ...] = (
    "benchmark",
    "models",
    "utils",
)
WHY = "financial NLP over LLM weights; the research path carries no LLM"
REBUILT_BY = "the desk's own text organs (deep_forest_miner.py) on registered grounds"


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
