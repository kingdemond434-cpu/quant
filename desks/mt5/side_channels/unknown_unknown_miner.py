"""Unknown-Unknown Miner — finds observable variables never seen before.

Scores candidate sources on:
Novelty × EconomicMechanism × Accessibility × History × MT5Relevance

Requirement: NOT another transformation of OHLC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

UNKNOWN_DIR = DATA_DIR / "unknown_unknown"
UNKNOWN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UnknownCandidate:
    """A candidate unknown data source."""
    name: str
    description: str
    access_method: str                           # "API", "scraping", "manual", "vendor"
    economic_mechanism: str                      # why it should matter
    accessibility_score: float                   # 0-1
    history_years: float                         # available history
    mt5_relevance: float                         # 0-1, how many MT5 symbols affected
    novelty_score: float                         # 0-1, not in existing features
    composite_score: float = 0.0
    status: str = "candidate"                    # "candidate", "testing", "validated", "rejected"
    test_results: dict = field(default_factory=dict)


@dataclass
class UnknownSignal:
    """Signal from a validated unknown source."""
    source_name: str
    symbol: str
    timestamp: datetime
    signal_type: str
    direction: int
    strength: float
    expected_horizon: str
    context: dict
    subsequent_outcome: dict | None = None


# Catalog of potential unknown sources
UNKNOWN_CATALOG = [
    UnknownCandidate(
        name="refinery_turnaround_schedule",
        description="Planned/unplanned refinery maintenance from EIA/DOE",
        access_method="API (EIA)",
        economic_mechanism="Supply disruption → crack spreads → oil products → USD/CAD, NOK",
        accessibility_score=0.9,
        history_years=10,
        mt5_relevance=0.8,
        novelty_score=0.9,
    ),
    UnknownCandidate(
        name="port_congestion_index",
        description="Global port wait times from MarineTraffic/Freos",
        access_method="scraping/API",
        economic_mechanism="Shipping delays → commodity delivery → physical markets → FX of exporters",
        accessibility_score=0.6,
        history_years=5,
        mt5_relevance=0.7,
        novelty_score=0.85,
    ),
    UnknownCandidate(
        name="electricity_load_curves",
        description="Real-time grid load from ISO/RTO (ERCOT, CAISO, PJM, etc.)",
        access_method="API (public)",
        economic_mechanism="Power demand → natgas/coal → energy equities → USD, CAD, AUD",
        accessibility_score=0.8,
        history_years=15,
        mt5_relevance=0.6,
        novelty_score=0.9,
    ),
    UnknownCandidate(
        name="commodity_inventories_LME_COMEX",
        description="Exchange warehouse stocks with daily updates",
        access_method="API (LME/COMEX)",
        economic_mechanism="Inventory draw/build → futures basis → physical arbitrage",
        accessibility_score=0.9,
        history_years=20,
        mt5_relevance=0.8,
        novelty_score=0.7,
    ),
    UnknownCandidate(
        name="shipping_rates_BDI_FFA",
        description="Baltic Dry Index, Forward Freight Agreements",
        access_method="vendor/Bloomberg",
        economic_mechanism="Shipping cost → commodity landed cost → emerging market FX",
        accessibility_score=0.7,
        history_years=30,
        mt5_relevance=0.7,
        novelty_score=0.6,
    ),
    UnknownCandidate(
        name="government_tender_calendars",
        description="Public procurement schedules (US SAM.gov, EU TED, etc.)",
        access_method="API/scraping",
        economic_mechanism="Fiscal impulse timing → sector equities → sector FX sensitivity",
        accessibility_score=0.5,
        history_years=10,
        mt5_relevance=0.5,
        novelty_score=0.95,
    ),
    UnknownCandidate(
        name="crop_condition_reports",
        description="USDA NASS weekly crop progress, WASDE",
        access_method="API (USDA)",
        economic_mechanism="Yield expectations → ag futures → AUD, CAD, NZD, BRL",
        accessibility_score=0.9,
        history_years=30,
        mt5_relevance=0.7,
        novelty_score=0.6,
    ),
    UnknownCandidate(
        name="weather_anomalies_NOAA",
        description="Temperature anomalies, hurricane tracks, drought indices",
        access_method="API (NOAA)",
        economic_mechanism="Energy demand, ag yields, insurance → utilities, commodities, CAT bonds",
        accessibility_score=0.9,
        history_years=50,
        mt5_relevance=0.6,
        novelty_score=0.7,
    ),
    UnknownCandidate(
        name="central_bank_balance_sheet_operations",
        description="Fed H.4.1, ECB weekly financial statement, BOJ tankan",
        access_method="API (public)",
        economic_mechanism="Liquidity injection/drain → repo rates, term premia, risk appetite",
        accessibility_score=0.9,
        history_years=20,
        mt5_relevance=0.9,
        novelty_score=0.5,
    ),
    UnknownCandidate(
        name="treasury_cash_balance_TGA",
        description="Treasury General Account at Fed",
        access_method="API (Treasury Direct)",
        economic_mechanism="Fiscal liquidity → repo market, bill yields, bank reserves",
        accessibility_score=0.9,
        history_years=20,
        mt5_relevance=0.8,
        novelty_score=0.6,
    ),
    UnknownCandidate(
        name="corporate_buyback_blackout_periods",
        description="Insider trading windows, 10b-18 plans, blackout calendars",
        access_method="SEC filings (EDGAR)",
        economic_mechanism="Corporate demand removal → equity vol, index support levels",
        accessibility_score=0.6,
        history_years=10,
        mt5_relevance=0.7,
        novelty_score=0.8,
    ),
    UnknownCandidate(
        name="options_expiration_concentration",
        description="OI by strike, gamma exposure (GEX), max pain",
        access_method="OPRA/CBOE data",
        economic_mechanism="Dealer hedging flows → pin risk, vol suppression/expansion",
        accessibility_score=0.7,
        history_years=15,
        mt5_relevance=0.8,
        novelty_score=0.5,
    ),
    UnknownCandidate(
        name="holiday_settlement_anomalies",
        description="Global holiday calendars with settlement adjustments",
        access_method="calendar compilation",
        economic_mechanism="T+2 mismatch → FX swap basis, funding stress",
        accessibility_score=0.8,
        history_years=10,
        mt5_relevance=0.9,
        novelty_score=0.85,
    ),
    UnknownCandidate(
        name="etf_creation_redemption_data",
        description="Daily ETF flows, creation units, premium/discount",
        access_method="ETF provider websites, Bloomberg",
        economic_mechanism="AP arbitrage → underlying basket pressure, sector rotation",
        accessibility_score=0.7,
        history_years=10,
        mt5_relevance=0.8,
        novelty_score=0.6,
    ),
    UnknownCandidate(
        name="short_sale_restriction_data",
        description="Reg SHO threshold lists, SSR triggers, borrow rates",
        access_method="FINRA/NASDAQ",
        economic_mechanism="Short squeeze potential, borrowing cost → equity vol, factor returns",
        accessibility_score=0.6,
        history_years=10,
        mt5_relevance=0.7,
        novelty_score=0.7,
    ),
]


class UnknownUnknownMiner:
    """Discovers and validates unknown data sources."""

    def __init__(self):
        self.candidates: list[UnknownCandidate] = UNKNOWN_CATALOG.copy()
        self.validated: list[UnknownCandidate] = []

    def score_candidates(self) -> list[UnknownCandidate]:
        """Score all candidates on composite metric."""
        for c in self.candidates:
            c.composite_score = (
                c.novelty_score * 0.30 +
                c.accessibility_score * 0.20 +
                min(c.history_years / 20, 1.0) * 0.15 +
                c.mt5_relevance * 0.25 +
                (1 if "mechanism" in c.economic_mechanism.lower() else 0) * 0.10
            )
        # Sort by score
        self.candidates.sort(key=lambda x: -x.composite_score)
        return self.candidates

    def get_top_candidates(self, n: int = 5) -> list[UnknownCandidate]:
        """Get top N candidates for testing."""
        self.score_candidates()
        return self.candidates[:n]

    def validate_candidate(self, candidate: UnknownCandidate,
                            test_data: pd.DataFrame,
                            symbols: list[str]) -> UnknownCandidate:
        """Test a candidate against historical data."""
        # This would run actual backtests in production
        # For now, simulate validation
        candidate.status = "testing"

        # Simple test: does the data have predictive power?
        # In reality, you'd merge with price data and run regressions
        candidate.test_results = {
            "tested_symbols": symbols,
            "data_points": len(test_data),
            "date_range": f"{test_data.index.min()} to {test_data.index.max()}",
            "predictive_power": "pending",  # Would be actual metric
        }

        # Simulate result
        if candidate.composite_score > 0.6:
            candidate.status = "validated"
            self.validated.append(candidate)
        else:
            candidate.status = "rejected"

        return candidate

    def generate_hypotheses_from_validated(self) -> list[SideChannelHypothesis]:
        """Generate hypotheses from validated unknown sources."""
        hypotheses = []

        for c in self.validated:
            if c.status != "validated":
                continue

            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis(c.economic_mechanism.split("→")[0].strip().lower().replace(" ", "_")),
                source="unknown_unknown_miner",
                mechanism=f"Novel data source: {c.name}. {c.description}. "
                          f"Mechanism: {c.economic_mechanism}. "
                          f"Composite score: {c.composite_score:.3f}. "
                          f"Novelty: {c.novelty_score:.2f}, Access: {c.accessibility_score:.2f}, "
                          f"MT5 relevance: {c.mt5_relevance:.2f}.",
                symbols=[],  # Would be determined by testing
                timing={
                    "source": c.name,
                    "access": c.access_method,
                },
                falsifier=f"Predictive power drops below random over 50+ tests",
                expected_horizon="1d_to_1w",
                capacity_estimate="small",
                metadata={
                    "source": c.name,
                    "composite_score": c.composite_score,
                    "novelty": c.novelty_score,
                    "accessibility": c.accessibility_score,
                    "mt5_relevance": c.mt5_relevance,
                    "economic_mechanism": c.economic_mechanism,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(UNKNOWN_DIR / "candidates.json", "w") as f:
            json.dump([{
                "name": c.name,
                "description": c.description,
                "access_method": c.access_method,
                "economic_mechanism": c.economic_mechanism,
                "accessibility": c.accessibility_score,
                "history_years": c.history_years,
                "mt5_relevance": c.mt5_relevance,
                "novelty": c.novelty_score,
                "composite_score": c.composite_score,
                "status": c.status,
            } for c in self.candidates], f, indent=2)

        with open(UNKNOWN_DIR / "validated.json", "w") as f:
            json.dump([{
                "name": c.name,
                "composite_score": c.composite_score,
                "test_results": c.test_results,
            } for c in self.validated], f, indent=2)


if __name__ == "__main__":
    miner = UnknownUnknownMiner()

    print("Top Unknown Candidates:")
    for c in miner.get_top_candidates(10):
        print(f"  {c.name}: score={c.composite_score:.3f} "
              f"(novelty={c.novelty_score:.2f}, access={c.accessibility_score:.2f}, "
              f"mt5_rel={c.mt5_relevance:.2f})")
        print(f"    Mechanism: {c.economic_mechanism}")
        print(f"    Access: {c.access_method}")

    hyps = miner.generate_hypotheses_from_validated()
    print(f"\nGenerated {len(hyps)} unknown-unknown hypotheses")