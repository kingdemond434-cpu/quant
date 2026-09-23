"""QuantConnect / LEAN adapter (WRAPPED) -- LEAN core is Apache-2.0 and its backtests run in
the LEAN docker engine, outside this sandbox. The adapter measures the `lean` CLI import
and donates the bundle in LEAN's hourly CSV shape as a DATASET (schema + row counts) so a
local LEAN run has its input; the platform's agents are reached by API where terms permit.
"""
from __future__ import annotations

from typing import Any

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "quantconnect_cloud"
CAPABILITY_FAMILY = "research_reliability"
LICENCE_EXPECTED = "Apache-2.0"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    lean = A.library("lean")
    if lean is None:
        return A.unmeasured(SYSTEM, bundle, "lean is not importable here (pip install "
                                            "lean==1.0.229; backtests need the LEAN docker engine)")
    datasets: list[dict[str, Any]] = []
    for f in bundle.frames("H1"):
        rows = [[f.time[i], f.open[i], f.high[i], f.low[i], f.close[i], f.volume[i]]
                for i in range(max(0, len(f) - 5), len(f))]
        datasets.append({"kind": "lean_hour_bars", "symbol": f.symbol, "n_rows": len(f),
                         "schema": ["time", "open", "high", "low", "close", "volume"],
                         "tail": rows, "resolution": "Hour",
                         "note": "LEAN reads <symbol>_hour_trade.csv under data/forex/..."})
    return A.packet(SYSTEM, bundle, trials=0, datasets=datasets, research_methods=[
        {"kind": "WRAPPED_ROUTE", "system": SYSTEM,
         "why": "backtests execute in the LEAN docker engine outside this sandbox; the engine's "
                "verdicts have no authority here (the gauntlet judges)"}])


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
