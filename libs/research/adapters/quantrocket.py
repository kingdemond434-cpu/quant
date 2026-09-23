"""QuantRocket adapter (WRAPPED, API only) -- a COMMERCIAL market substrate reached through
a licensed installation's API, never vendored. The scrubbed sandbox environment carries
no HOUSTON_URL by design, so the adapter measures the client import and records that no
licensed installation is configured.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantrocket"
CAPABILITY_FAMILY = "data_tooling"
LICENCE_EXPECTED = "Proprietary"
MODULE = "quantrocket"
HINT = (
    "pip install quantrocket-client==2.11.0.0; a licensed installation is the principal's "
    "act"
)
PROBE_NAMES = ('history', 'fundamental', 'master', 'zipline')
WHY = "WRAPPED: API of a licensed installation only; none is configured in the sandbox"
REBUILT_BY = "the desk's own MT5 universe collector (mt5desk.universe)"


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
