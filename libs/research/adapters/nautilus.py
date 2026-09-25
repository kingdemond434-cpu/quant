"""nautilus adapter -- import probe only. deterministic replay semantics as a parity reference,
never an executor here. While the upstream is absent the capability is carried by
desks/mt5/research/shadow_forward.py."""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "nautilus"
CAPABILITY_FAMILY = "replay_parity"
LICENCE_EXPECTED = "LGPL-3.0"
MODULE = "nautilus_trader"
HINT = "pip install nautilus_trader; a compiled rust core, so wheel availability is measured"
PROBE_NAMES: tuple[str, ...] = (
    "model",
    "backtest",
    "__version__",
)
WHY = "deterministic replay semantics as a parity reference, never an executor here"
REBUILT_BY = "desks/mt5/research/shadow_forward.py"


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
