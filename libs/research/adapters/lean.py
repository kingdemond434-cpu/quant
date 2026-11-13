"""lean adapter -- ROUTED.

INDEPENDENT VERIFIER: LEAN's gap-aware fill semantics replayed on certified cells

an execution/backtest parity REFERENCE. LEAN's bar fill model -- a stop that the bar OPENS
through fills at the open (worse than the stop), a limit the open gaps through fills at the open
(better) -- is rebuilt in `libs/validation/engine_replicas.py` and replayed over every promoted
certificate's replica signals by the hourly leg `engine_replicas`, which publishes per
certificate how much of its R the desk's contract engine owes to filling gapped stops at the stop
price (`reports/ENGINE_REPLICAS.json`). The CLI drives a .NET engine under docker that the box
does not run, so the semantics are what is reproduced.
"""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = 'lean'
CAPABILITY_FAMILY = 'replay_parity'
LICENCE_EXPECTED = 'Apache-2.0'
MODULE = 'lean'
HINT = 'pip install lean (the CLI); the engine itself is .NET and runs under docker'
CENSUS_CLASS = "b"
ROLE = "INDEPENDENT VERIFIER: LEAN's gap-aware fill semantics replayed on certified cells"
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
