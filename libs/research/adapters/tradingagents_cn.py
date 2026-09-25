"""tradingagents_cn adapter -- REJECTED_WITH_EVIDENCE for direct execution: a fork of an LLM swarm
with no wheel; the base is probed by adapters/tradingagents.py. Every module tried is named with
its import result, so the refusal is a measurement rather than an absence. Cover:
libs/research/adapters/tradingagents.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "tradingagents_cn"
CAPABILITY_FAMILY = "multi_agent_debate"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
#: Module names tried, in order, before this seed reads REJECTED_WITH_EVIDENCE for DIRECT
#: execution. If any of them ever appears here, the adapter MEASURES it instead of refusing.
CANDIDATE_MODULES: tuple[str, ...] = (
    "tradingagents_cn",
    "tradingagents",
)
TRIED: tuple[str, ...] = (
    "pip: no distribution named tradingagents-cn resolved on 2026-09-23",
    "import: the CN fork is absent; the upstream probe covers the base project",
    "the fork adds domestic model providers, all of them LLM APIs",
)
WHY = "a fork of an LLM swarm with no wheel; the base is probed by adapters/tradingagents.py"
COVER = "libs/research/adapters/tradingagents.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    """The refusal is a MEASUREMENT: every module tried by name with its import result, the
    reason direct execution is impossible here, and the organ that carries the capability
    instead. Never a crash and never a silent absence."""
    attempts: list[dict[str, Any]] = []
    for name in CANDIDATE_MODULES:
        lib = A.library(name)
        attempts.append({"module": name, "importable": lib is not None,
                         "version": str(getattr(lib, "__version__", "") or "") if lib else ""})
    live = [a for a in attempts if a["importable"]]
    if live:
        found = A.library(str(live[0]["module"]))
        return A.packet(SYSTEM, bundle, trials=0,
                        research_methods=[A.api_probe(SYSTEM, found, ("__name__",))],
                        note="the upstream appeared here: probed instead of refused")
    return A.packet(SYSTEM, bundle, trials=0, research_methods=[
        {"kind": "REJECTED_WITH_EVIDENCE", "system": SYSTEM, "why": WHY, "tried": list(TRIED),
         "import_attempts": attempts, "cover": COVER,
         "measurement": "what was tried, by name, on this interpreter"}],
        note="REJECTED_WITH_EVIDENCE for direct execution; the cover is named")


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
