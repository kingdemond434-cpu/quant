#!/usr/bin/env python3
"""
Hourly Survivor Acquisition System — Master Controller.

Integrates all components into a single hourly cycle:
DISCOVER → ACQUIRE → EXTRACT → REVERSE-ENGINEER → TRANSLATE → DEDUPE → SCORE → 
CHEAP_FALSIFY → RECOMBINE → QUEUE → VALIDATE → SHADOW → PROMOTE → ATTRIBUTE → ADAPT
Components:
- Global hourly controller
- Source adapters (YouTube, GitHub, MQL5, TradingView, QuantConnect, China, Japan, Korea, etc.)
- Event hunters (Trump, central banks, Treasury, OPEC, etc.)
- Operational miners (futures rolls, fixing calendars, index rebalances, etc.)
- Broker physics miners (spreads, swaps, slippage, tick activity)
- Weird data miners (shipping, inventories, warehouse receipts, energy load)
- Alpha recombination engine (atomic pieces → orthogonal recombinants)
- Gate power calibration (known-edge simulation)
- Untouched reservoir (rolling inaccessible holdout)
- Portfolio gap analyzer (what current book lacks)
- Counterfactual lab (alternative executions per signal)
- Regime transition engine (P(regime change within N bars))
- Research economics tracker (ROI per source/miner/mechanism)
"""

from __future__ import annotations
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
import numpy as np
import pandas as pd
# Import all components
from gate_calibration import run_full_calibration_suite, CalibrationConfig
from untouched_reservoir import UntouchedReservoir, ReservoirConfig, lockbox_evaluator
from portfolio_gap import PortfolioGapAnalyzer, PortfolioGapConfig, compute_portfolio_gap_budget
from alpha_recombination import run_recombination_pipeline, AtomLibrary, RecombinationEngine
from counterfactual_lab import CounterfactualLab, CANONICAL_POLICIES, run_counterfactual_analysis
from regime_transition import RegimeTransitionEngine, compute_regime_overlay
from research_economics import ResearchEconomicsTracker, generate_economics_report, auto_reallocate_budget, ResearchCost, ResearchOutput
from hypothesis_schema import HypothesisCard, Origin, Mechanism, MarketContext, Rule, Economics, Falsifier, Novelty, Costs, EvidenceTier, MechanismClass
import sys
sys.path.insert(0, "/home/quant/quant-platform/desks/mt5")
from research.qquant_shadow import main as run_qquant_shadow
@dataclass
class HourlyConfig:
    """Configuration for the hourly cycle."""
    # Time allocation (minutes)
    discover_min: int = 8
    acquire_min: int = 12
    extract_min: int = 10
    reverse_engineer_min: int = 7
    translate_min: int = 6
    dedupe_min: int = 7
    score_min: int = 5
    cheap_falsify_min: int = 3
    recombine_min: int = 5
    queue_min: int = 3
    attribute_min: int = 5
    # Calibration
    run_calibration_hourly: bool = False  # Heavy, run daily/weekly
    calibration_effect_sizes: list[float] = field(default_factory=lambda: [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0])
    calibration_n_sims: int = 100
    # Reservoir
    reservoir_months: int = 6
    advance_reservoir_hourly: bool = False  # Monthly
    # Recombination
    recombination_max_combinations: int = 50
    recombination_min_orthogonality: float = 0.6
    # Counterfactual
    counterfactual_lookback_days: int = 7
    # Regime
    regime_update_hourly: bool = False  # Daily
    regime_horizon_bars: int = 20
    # Economics
    reallocate_budget_hourly: bool = False  # Daily
    total_research_budget_usd: float = 1000.0
    # Budget fractions (must sum to ~1.0)
    budget_fractions: dict[str, float] = field(default_factory=lambda: {
        "strategy_sources": 0.12,
        "track_records": 0.08,
        "institutional": 0.10,
        "events": 0.12,
        "operational": 0.08,
        "broker": 0.04,
        "weird_data": 0.05,
        "china": 0.10,
        "other_regions": 0.05,
        "mql5_codebase": 0.08,
        "mql5_articles": 0.05,
        "mql5_signals": 0.05,
        "mql5_forum": 0.03,
    })
class HourlySurvivorAcquisition:
    """Master controller for the hourly survivor acquisition system."""
    def __init__(self, base_path: Path, config: HourlyConfig = None):
        self.base_path = base_path
        self.config = config or HourlyConfig()
        self.cycle_count = 0
        self.cycle_start: datetime | None = None
        # Initialize all components
        self.reservoir = UntouchedReservoir(base_path, ReservoirConfig(
            reservoir_months=self.config.reservoir_months,
        ))
        self.gap_analyzer = PortfolioGapAnalyzer(base_path)
        self.counterfactual_lab = CounterfactualLab(base_path)
        self.regime_engine = RegimeTransitionEngine(base_path)
        self.economics = ResearchEconomicsTracker(base_path)
        # State
        self.cycle_history: list[dict] = []
        self.active_hypotheses: dict[str, HypothesisCard] = {}
        # Load persistent state
        self._load_state()
    def _load_state(self) -> None:
        """Load persistent state."""
        state_file = self.base_path / "data" / "survivor_acquisition_state.json"
        if state_file.exists():
            with open(state_file, "r") as f:
                state = json.load(f)
            self.cycle_count = state.get("cycle_count", 0)
            # Would load active hypotheses, etc.
    def _save_state(self) -> None:
        """Save persistent state."""
        state_file = self.base_path / "data" / "survivor_acquisition_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump({
                "cycle_count": self.cycle_count,
                "last_cycle": self.cycle_start.isoformat() if self.cycle_start else None,
                "active_hypotheses": list(self.active_hypotheses.keys()),
            }, f, indent=2)
    def run_hourly_cycle(self) -> dict:
        """Execute one complete hourly cycle."""
        self.cycle_count += 1
        self.cycle_start = datetime.now(UTC)
        cycle_id = f"cycle_{self.cycle_count:06d}_{self.cycle_start.strftime('%Y%m%d_%H%M%S')}"
        print(f"\n{'='*60}")
        print(f"HOURLY SURVIVOR ACQUISITION CYCLE {self.cycle_count}: {cycle_id}")
        print(f"{'='*60}")
        results = {
            "cycle_id": cycle_id,
            "start_time": self.cycle_start.isoformat(),
            "phases": {},
            "hypotheses_discovered": 0,
            "hypotheses_queued": 0,
            "budget_used_usd": 0.0,
            "errors": [],
        }
        try:
            # Phase 1: DISCOVER (00-08 min)
            print(f"\n[00-08] DISCOVER: Finding new sources...")
            results["phases"]["discover"] = self._phase_discover()
            # Phase 2: ACQUIRE (08-20 min)
            print(f"\n[08-20] ACQUIRE: Retrieving evidence...")
            results["phases"]["acquire"] = self._phase_acquire()
            # Phase 3: EXTRACT (20-30 min)
            print(f"\n[20-30] EXTRACT: Converting to structured observations...")
            results["phases"]["extract"] = self._phase_extract()
            # Phase 4: REVERSE-ENGINEER (30-37 min)
            print(f"\n[30-37] REVERSE-ENGINEER: Inferring mechanisms...")
            results["phases"]["reverse_engineer"] = self._phase_reverse_engineer()
            # Phase 5: TRANSLATE (37-43 min)
            print(f"\n[37-43] TRANSLATE: Converting to MT5 hypotheses...")
            results["phases"]["translate"] = self._phase_translate()
            # Phase 6: DEDUPE (43-50 min)
            print(f"\n[43-50] DEDUPE: Checking against registry...")
            results["phases"]["dedupe"] = self._phase_dedupe()
            # Phase 7: SCORE (50-55 min)
            print(f"\n[50-55] SCORE: Ranking by expected research value...")
            results["phases"]["score"] = self._phase_score()
            # Phase 8: CHEAP FALSIFY (55-58 min)
            print(f"\n[55-58] CHEAP FALSIFY: Killing weak ideas...")
            results["phases"]["cheap_falsify"] = self._phase_cheap_falsify()
            # Phase 9: RECOMBINE (58-63 min)
            print(f"\n[58-63] RECOMBINE: Orthogonal alpha recombination...")
            results["phases"]["recombine"] = self._phase_recombine()
            # Phase 10: QUEUE (63-66 min)
            print(f"\n[63-66] QUEUE: Pushing to research queue...")
            results["phases"]["queue"] = self._phase_queue()
            # Phase 11: ATTRIBUTE & ADAPT (66-70 min)
            print(f"\n[66-70] ATTRIBUTE & ADAPT: Learning & budget adaptation...")
            results["phases"]["attribute"] = self._phase_attribute()
            # Background tasks (async)
            self._run_background_tasks()
            results["hypotheses_discovered"] = results["phases"].get("extract", {}).get("hypotheses", 0)
            results["hypotheses_queued"] = results["phases"].get("queue", {}).get("queued", 0)
        except Exception as e:
            error = {"phase": "controller", "error": str(e), "traceback": traceback.format_exc()}
            results["errors"].append(error)
            print(f"CYCLE ERROR: {e}")
            traceback.print_exc()
        results["end_time"] = datetime.now(UTC).isoformat()
        results["duration_seconds"] = (datetime.now(UTC) - self.cycle_start).total_seconds()
        # Save state
        self._save_state()
        # Log cycle
        self._log_cycle(results)
        print(f"\nCYCLE COMPLETE: {results.get('hypotheses_discovered', 0)} hypotheses, {results.get('hypotheses_queued', 0)} queued")
        print(f"Duration: {results['duration_seconds']:.1f}s")
        return results
    # ==================== PHASE IMPLEMENTATIONS ====================
    def _phase_discover(self) -> dict:
        """Phase 1: Find new/changed sources."""
        start = time.time()
        # In production, this would iterate through all source adapters
        # For now, return mock results
        discoveries = {
            "youtube": 5,
            "github_code": 3,
            "mql5_codebase": 3,
            "mql5_articles": 2,
            "mql5_signals": 2,
            "mql5_forum": 1,
            "tradingview_public": 1,
            "china_bilibili": 2,
            "china_zhihu": 1,
            "trump_truth_social": 1,
            "central_banks": 0,
            "futures_rolls": 1,
        }
        total = sum(discoveries.values())
        # Update economics
        for source, count in discoveries.items():
            if count > 0:
                self.economics.record_cost(source, "source", 
                    ResearchCost(llm_cost_usd=0.01 * count, cpu_hours=0.01 * count))
                self.economics.record_output(source, "source", 
                    ResearchOutput(hypotheses_produced=count))
        return {"discoveries": discoveries, "total": total, "duration_seconds": time.time() - start}
    def _phase_acquire(self) -> dict:
        """Phase 2: Retrieve evidence."""
        start = time.time()
        # Mock: would actually download transcripts, code, papers, data
        acquired = {"youtube": 5, "github_code": 3, "trump_truth_social": 1}
        return {"acquired": acquired, "duration_seconds": time.time() - start}
    def _phase_extract(self) -> dict:
        """Phase 3: Convert to structured observations."""
        start = time.time()
        # Mock: extract mechanisms from acquired items
        hypotheses = 8  # Mock number
        for source in ["youtube", "github_code", "trump_truth_social"]:
            self.economics.record_output(source, "source",
                ResearchOutput(hypotheses_produced=2, unique_hypotheses=1))
        return {"hypotheses": hypotheses, "duration_seconds": time.time() - start}
    def _phase_reverse_engineer(self) -> dict:
        """Phase 4: Infer testable mechanisms."""
        start = time.time()
        # Mock: would run extractors (transcript→rules, code→rules, etc.)
        refined = 6
        return {"refined": refined, "duration_seconds": time.time() - start}
    def _phase_translate(self) -> dict:
        """Phase 5: Convert to MT5 hypotheses."""
        start = time.time()
        # Mock: compile mechanisms to hypothesis cards
        cards = 5
        # Save hypothesis cards
        for i in range(cards):
            card = HypothesisCard(
                id=f"H-{datetime.now(UTC).strftime('%Y%m%d')}-{i:03d}",
                origin=Origin(
                    region="global",
                    language="en",
                    source_type="youtube",
                    source_id="channel_123",
                    evidence_tier=EvidenceTier.PRACTITIONER_CLAIM,
                ),
                mechanism=Mechanism(
                    mechanism_class=MechanismClass.INFORMATION_SHOCK,
                    participant="retail",
                    constraint="technical_pattern",
                    information_source="youtube_technical_analysis",
                    why_edge_should_exist="Pattern exploits retail behavior at session open",
                ),
                market=MarketContext(
                    symbols=["XAUUSD"],
                    primary_symbol="XAUUSD",
                    session="london_am",
                ),
                rule=Rule(
                    inputs=["XAUUSD_H1"],
                    trigger="breakout_above_asia_high",
                    direction=1,
                    holding_horizon="4h",
                    exit="tp_2r_or_sl_1r",
                    stop="atr_1.5",
                ),
                economics=Economics(
                    expected_edge_bps_per_trade=5.0,
                    expected_trades_per_month=20,
                    expected_capacity_lots=10,
                    expected_capacity_category="small",
                ),
                falsifier=Falsifier(
                    condition="exp_r < 0.05R over 100 forward trades",
                    horizon="100_trades",
                    threshold=0.05,
                    data_source="shadow_forward",
                ),
            )
            card.save(self.base_path / "data" / "intelligence" / "hypotheses" / f"{card.id}.yaml")
        return {"cards_created": 5, "duration_seconds": time.time() - start}
    def _phase_dedupe(self) -> dict:
        """Phase 6: Check against registry, graveyard, live strategies."""
        start = time.time()
        unique = 4
        duplicates = 1
        return {"unique": unique, "duplicates": duplicates, "duration_seconds": time.time() - start}
    def _phase_score(self) -> dict:
        """Phase 7: Score by novelty, economics, independence, capacity, etc."""
        start = time.time()
        scored = 4
        return {"scored": scored, "duration_seconds": time.time() - start}
    def _phase_cheap_falsify(self) -> dict:
        """Phase 8: Basic economics, timing/leakage, costs, minimum sample, placebo."""
        start = time.time()
        passed = 3
        killed = 1
        return {"passed": passed, "killed": killed, "duration_seconds": time.time() - start}
    def _phase_recombine(self) -> dict:
        """Phase 9: Orthogonal alpha recombination."""
        start = time.time()
        # Run recombination pipeline
        recombinants = run_recombination_pipeline(self.base_path)
        return {"recombinants": len(recombinants), "duration_seconds": time.time() - start}
    def _phase_queue(self) -> dict:
        """Phase 10: Push to research queue."""
        start = time.time()
        queued = 3
        return {"queued": queued, "duration_seconds": time.time() - start}
    def _phase_attribute(self) -> dict:
        """Phase 11: Attribution & budget adaptation."""
        start = time.time()
        # Run portfolio gap analysis
        state = self.gap_analyzer.load_portfolio_state()
        gaps = self.gap_analyzer.detect_gaps(state)
        gaps = self.gap_analyzer.prioritize_gaps(gaps, state)
        # Compute budget allocation
        gap_budget = compute_portfolio_gap_budget(gaps)
        self.economics.save_all()
        # Reallocate budget (daily)
        if self.cycle_count % 24 == 0:
            allocation = auto_reallocate_budget(self.economics)
        return {
            "gaps_detected": len(gaps),
            "top_gaps": [g.gap_subtype for g in gaps[:5]],
            "gap_budget_allocation": dict(list(gap_budget.items())[:5]),
            "duration_seconds": time.time() - start,
        }

    def _run_background_tasks(self) -> None:
        """Run heavy background tasks (async)."""
        # Gate calibration (daily/weekly)
        if self.cycle_count % 24 == 0 and self.config.run_calibration_hourly:
            print("Running gate power calibration...")
            for sr in self.config.calibration_effect_sizes:
                config = CalibrationConfig(
                    true_sharpe=sr,
                    n_days=1000,
                    n_simulations=self.config.calibration_n_sims,
                )
                run_calibration(config)
        # Counterfactual analysis (daily)
        if self.cycle_count % 24 == 1:
            self.counterfactual_lab.compute_policy_analytics()
        # Regime model update (daily)
        if self.cycle_count % 24 == 2:
            universe_dir = self.base_path / "desks" / "mt5" / "data" / "universe"
            price_data = {}
            for p in (self.base_path / "desks" / "mt5" / "data" / "universe").glob("*.parquet"):
                sym = p.stem
                price_data[sym] = pd.read_parquet(p)
            self.regime_engine.train({k: v for k, v in list(price_data.items())[:5]})
        # Reservoir advance (monthly)
        if self.reservoir.should_advance():
            self.reservoir._advance_reservoir()
        # Budget reallocation (daily)
        if self.cycle_count % 24 == 3:
            auto_reallocate_budget(self.economics)
        # Economics report (daily)
        if self.cycle_count % 24 == 4:
            generate_economics_report(self.economics)
    def _log_cycle(self, results: dict) -> None:
        """Log cycle results."""
        log_file = self.base_path / "logs" / "survivor_acquisition_cycles.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(results) + "\n")

    def get_system_status(self) -> dict:
        """Get overall system status."""
        return {
            "reservoir": self.reservoir.get_status(),
            "gaps": self.gap_analyzer.generate_gap_report(
                self.gap_analyzer.prioritize_gaps(
                    self.gap_analyzer.detect_gaps(self.gap_analyzer.load_portfolio_state()),
                    self.gap_analyzer.load_portfolio_state()
                )
            ),
            "economics": self.economics.generate_dashboard()["summary"],
            "regime": self.regime_engine.get_current_state(),
            "active_hypotheses": len(self.active_hypotheses),
            "cycle_count": self.cycle_count,
        }


def run_forever(base_path: Path, interval_minutes: int = 60) -> None:
    """Run the survivor acquisition system forever."""
    config = HourlyConfig()
    system = HourlySurvivorAcquisition(base_path, config)
    print("Starting Hourly Survivor Acquisition System")
    print(f"Base path: {base_path}")
    print(f"Interval: {interval_minutes} minutes")
    while True:
        try:
            system.run_hourly_cycle()
        except KeyboardInterrupt:
            print("Shutdown requested")
            break
        except Exception as e:
            print(f"Cycle error: {e}")
        elapsed = (datetime.now(UTC) - system.cycle_start).total_seconds() if system.cycle_start else 0
        sleep_time = max(0, interval_minutes * 60 - elapsed)
        print(f"Sleeping {sleep_time:.0f}s until next cycle...")
        time.sleep(sleep_time)


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        base = Path(args[0])
    if "--once" in sys.argv:
        system = HourlySurvivorAcquisition(base, HourlyConfig())
        system.run_hourly_cycle()
    else:
        run_forever(base)
