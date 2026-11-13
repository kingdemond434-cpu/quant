"""nautilus adapter -- ROUTED.

INDEPENDENT VERIFIER: Nautilus adaptive bar-path ordering replayed on certified cells

deterministic replay semantics as a parity reference, never an executor here. Nautilus
replays a bar as four prices -- open, then the NEARER of high and low, then the other, then
close -- so a bar that touches both stop and target resolves by path, where the desk's contract
engine always lets the stop win. `libs/validation/engine_replicas.py` rebuilds that ordering and
the hourly leg `engine_replicas` replays every promoted certificate through it, publishing how
much R the stop-first tie-break costs or flatters (`reports/ENGINE_REPLICAS.json`). The compiled
rust engine is not driven in a desk process: the rebuild needs only numpy and the semantics are
the part a verifier needs.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'nautilus'
CAPABILITY_FAMILY = 'replay_parity'
LICENCE_EXPECTED = 'LGPL-3.0'
MODULE = 'nautilus_trader'
HINT = 'pip install nautilus_trader; a compiled rust core, so wheel availability is measured'
CENSUS_CLASS = "b"
ROLE = 'INDEPENDENT VERIFIER: Nautilus adaptive bar-path ordering replayed on certified cells'
CONTRACTS: tuple[str, ...] = ()
CLOCK = 'hourly_cycle:engine_replicas'
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
