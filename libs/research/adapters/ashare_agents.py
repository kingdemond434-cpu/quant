"""ashare_agents adapter -- REJECTED_WITH_EVIDENCE for direct execution: no distribution, and forum
scraping is access-gated (public/licensed sources only). Every module tried is named with its
import result, so the refusal is a measurement rather than an absence. Cover:
desks/mt5/research/deep_forest_miner.py, which mines REGISTERED grounds only."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ashare_agents"
CAPABILITY_FAMILY = "data_source"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
#: Module names tried, in order, before this seed reads REJECTED_WITH_EVIDENCE for DIRECT
#: execution. If any of them ever appears here, the adapter MEASURES it instead of refusing.
CANDIDATE_MODULES: tuple[str, ...] = (
    "ashare_agents",
    "ashare",
)
TRIED: tuple[str, ...] = (
    "pip: no distribution named ashare-agents resolved on 2026-09-23",
    "import: absent on this interpreter",
    "its inputs are forum scrapes (Sina, East Money) from pages not registered machine_use_allowed",
)
WHY = "no distribution, and forum scraping is access-gated (public/licensed sources only)"
COVER = "desks/mt5/research/deep_forest_miner.py, which mines REGISTERED grounds only"


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
