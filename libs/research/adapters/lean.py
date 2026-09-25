"""lean adapter -- import probe only. an execution/backtest parity REFERENCE; the desk's own fill
model is the subject. While the upstream is absent the capability is carried by
desks/mt5/research/shadow_forward.py + matched_fills."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "lean"
CAPABILITY_FAMILY = "replay_parity"
LICENCE_EXPECTED = "Apache-2.0"
MODULE = "lean"
HINT = "pip install lean (the CLI); the engine itself is .NET and runs under docker"
PROBE_NAMES: tuple[str, ...] = (
    "main",
    "commands",
    "__version__",
)
WHY = "an execution/backtest parity REFERENCE; the desk's own fill model is the subject"
REBUILT_BY = "desks/mt5/research/shadow_forward.py + matched_fills"


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
