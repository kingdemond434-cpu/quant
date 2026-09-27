"""Public gold-bot route; mechanisms rebuilt, upstream execution deliberately not imported."""
from __future__ import annotations

from libs.research import adapters as A
from libs.research.external_federation import ExternalResearchPacket

SYSTEM = "ai_gold_trading_bot"
CAPABILITY_FAMILY = "research_reproduction"
LICENCE_EXPECTED = "UNVERIFIED"
RUNS_WITHOUT_LIBRARY = True
REBUILT_BY = "desks/mt5/research/sandboxes/gold_public_mechanisms.py"


def run(bundle: A.ResearchBundle) -> ExternalResearchPacket:
    return A.packet(SYSTEM, bundle, trials=0, research_methods=({
        "kind": "REBUILT_ROUTE", "system": SYSTEM,
        "mechanism": ("trend-filtered MACD continuation, failed-breakout wick rejection and "
                      "OHLCV failed-auction proxy; confluence tested only as an ablation"),
        "rebuilt_by": REBUILT_BY,
        "rejected": ("hand-coded confidence, 6-10.8% risk, synthetic observations and "
                     "live-failure-to-simulation fallback")},))


if __name__ == "__main__":
    raise SystemExit(A.cli(run, SYSTEM))
