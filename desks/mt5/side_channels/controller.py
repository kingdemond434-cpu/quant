"""Hourly Survivor Acquisition Controller.

Orchestrates the complete hourly cycle:
DISCOVER → ACQUIRE → EXTRACT → REVERSE-ENGINEER → TRANSLATE → DEDUPE → SCORE → 
CHEAP_FALSIFY → MUTATE → QUEUE → ATTRIBUTE → ADAPT BUDGET
"""

from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
import uuid

import numpy as np


# Import all miners (lazy loaded)
MINER_REGISTRY = {
    # Strategy sources
    "youtube": "survivor_acquisition.sources.strategy.youtube",
    "github_code": "survivor_acquisition.sources.strategy.github_code",
    "mql5_public": "survivor_acquisition.sources.strategy.mql5_public",
    "tradingview_public": "survivor_acquisition.sources.strategy.tradingview_public",
    "quantconnect": "survivor_acquisition.sources.strategy.quantconnect",
    "practitioner_blogs": "survivor_acquisition.sources.strategy.practitioner_blogs",
    
    # Track records
    "public_copy_leaderboards": "survivor_acquisition.sources.track_records.public_copy_leaderboards",
    "verified_track_records": "survivor_acquisition.sources.track_records.verified_track_records",
    "competition_results": "survivor_acquisition.sources.track_records.competition_results",
    
    # Institutional research
    "worldquant": "survivor_acquisition.sources.institutional_research.worldquant",
    "alpha101": "survivor_acquisition.sources.institutional_research.alpha101",
    "aqr": "survivor_acquisition.sources.institutional_research.aqr",
    "man_institute": "survivor_acquisition.sources.institutional_research.man_institute",
    "arxiv": "survivor_acquisition.sources.institutional_research.arxiv",
    "ssrn": "survivor_acquisition.sources.institutional_research.ssrn",
    "university_theses": "survivor_acquisition.sources.institutional_research.university_theses",
    
    # Events
    "trump_truth_social": "survivor_acquisition.sources.events.trump_truth_social",
    "central_banks": "survivor_acquisition.sources.events.central_banks",
    "treasury": "survivor_acquisition.sources.events.treasury",
    "government_notices": "survivor_acquisition.sources.events.government_notices",
    "sanctions": "survivor_acquisition.sources.events.sanctions",
    "energy_opec": "survivor_acquisition.sources.events.energy_opec",
    
    # Operational
    "exchange_circulars": "survivor_acquisition.sources.operational.exchange_circulars",
    "futures_rolls": "survivor_acquisition.sources.operational.futures_rolls",
    "fixing_calendars": "survivor_acquisition.sources.operational.fixing_calendars",
    "index_rebalances": "survivor_acquisition.sources.operational.index_rebalances",
    "option_expiries": "survivor_acquisition.sources.operational.option_expiries",
    "settlement_windows": "survivor_acquisition.sources.operational.settlement_windows",
    
    # Broker
    "fusion_spreads": "survivor_acquisition.sources.broker.fusion_spreads",
    "fusion_swaps": "survivor_acquisition.sources.broker.fusion_swaps",
    "slippage": "survivor_acquisition.sources.broker.slippage",
    "tick_activity": "survivor_acquisition.sources.broker.tick_activity",
    "session_anomalies": "survivor_acquisition.sources.broker.session_anomalies",
    
    # Weird data
    "shipping": "survivor_acquisition.sources.weird_data.shipping",
    "inventories": "survivor_acquisition.sources.weird_data.inventories",
    "warehouse_receipts": "survivor_acquisition.sources.weird_data.warehouse_receipts",
    "energy_load": "survivor_acquisition.sources.weird_data.energy_load",
    "commodity_flows": "survivor_acquisition.sources.weird_data.commodity_flows",
    "tenders": "survivor_acquisition.sources.weird_data.tenders",
    "unknown_unknowns": "survivor_acquisition.sources.weird_data.unknown_unknowns",
    
    # Regions
    "china_bilibili": "survivor_acquisition.regions.china.bilibili",
    "china_zhihu": "survivor_acquisition.regions.china.zhihu",
    "china_gitee": "survivor_acquisition.regions.china.gitee",
    "china_csdn": "survivor_acquisition.regions.china.csdn",
    "china_joinquant": "survivor_acquisition.regions.china.joinquant_public",
    "china_exchange_research": "survivor_acquisition.regions.china.exchange_research",
    "china_native_data": "survivor_acquisition.regions.china.native_data_sources",
    
    "japan_sources": "survivor_acquisition.regions.japan.sources",
    "korea_sources": "survivor_acquisition.regions.korea.sources",
    "russia_sources": "survivor_acquisition.regions.russia.sources",
    "brazil_sources": "survivor_acquisition.regions.brazil.sources",
    "india_sources": "survivor_acquisition.regions.india.sources",
    "mena_sources": "survivor_acquisition.regions.mena.sources",
    "turkey_sources": "survivor_acquisition.regions.turkey.sources",
    "europe_sources": "survivor_acquisition.regions.europe.sources",
    "latam_sources": "survivor_acquisition.regions.latam.sources",
}


@dataclass
class MinerConfig:
    """Configuration for a single miner."""
    name: str
    module: str
    enabled: bool = True
    budget_fraction: float = 0.0          # fraction of hourly budget
    max_items_per_hour: int = 50
    priority: int = 1                     # 1=highest
    region: str = "global"
    language: str = "en"
    requires_translation: bool = False
    cheap_falsify: bool = True
    mutation_budget: int = 3              # variants per hypothesis
    cooldown_hours: int = 0               # prevent hammering same source


@dataclass
class HourlyBudget:
    """Budget allocation for the hour."""
    total_llm_calls: int = 200
    total_compute_seconds: int = 1800
    total_data_usd: float = 10.0
    miner_allocations: dict[str, dict] = field(default_factory=dict)
    
    def allocate(self, miner_name: str, fraction: float) -> dict:
        return {
            "llm_calls": int(self.total_llm_calls * fraction),
            "compute_seconds": int(self.total_compute_seconds * fraction),
            "data_usd": self.total_data_usd * fraction,
        }


@dataclass
class SourceReputation:
    """Tracks source performance for adaptive allocation."""
    source_id: str
    source_type: str
    region: str
    
    items_seen: int = 0
    testable_mechanisms: int = 0
    novel_mechanisms: int = 0
    fast_screen_pass: int = 0
    heavy_validation_pass: int = 0
    shadow_candidates: int = 0
    live_survivors: int = 0
    
    incremental_elogw: float = 0.0
    total_research_cost_usd: float = 0.0
    total_research_cost_hours: float = 0.0
    
    # Rolling metrics
    recent_survivor_rate: float = 0.0     # last 30 days
    recent_roi: float = 0.0               # E[log W] / cost
    
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    exploration_bonus: float = 1.0        # >1 encourages exploration


class HourlyController:
    """Main controller for hourly survivor acquisition."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.data_path = base_path / "data" / "intelligence"
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        # State files
        self.source_state_file = self.data_path / "source_state.json"
        self.raw_items_file = self.data_path / "raw_items.jsonl"
        self.mechanisms_file = self.data_path / "mechanisms.jsonl"
        self.hypothesis_cards_file = self.data_path / "hypothesis_cards.jsonl"
        self.source_reputation_file = self.data_path / "source_reputation.json"
        self.translation_gaps_file = self.data_path / "translation_gaps.json"
        self.research_queue_file = base_path / "desks" / "mt5" / "data" / "research_queue.json"
        
        # Load state
        self.source_reputations: dict[str, SourceReputation] = {}
        self.miner_configs: dict[str, MinerConfig] = {}
        self.budget = HourlyBudget()
        
        self._load_state()
        self._initialize_miner_configs()
        
        # Cycle tracking
        self.cycle_count = 0
        self.cycle_start_time: datetime | None = None
        
    def _load_state(self) -> None:
        """Load persistent state."""
        if self.source_reputation_file.exists():
            with open(self.source_reputation_file, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                self.source_reputations[k] = SourceReputation(**v)
        
        if self.research_queue_file.exists():
            with open(self.research_queue_file, "r") as f:
                pass  # Just verify it exists
    
    def _save_state(self) -> None:
        """Save persistent state."""
        with open(self.source_reputation_file, "w") as f:
            json.dump({k: v.__dict__ for k, v in self.source_reputations.items()}, 
                      f, indent=2, default=str)
    
    def _initialize_miner_configs(self) -> None:
        """Initialize miner configurations with budget fractions."""
        # Budget allocation (should sum to ~1.0)
        allocations = {
            # Core strategy sources
            "youtube": 0.10,
            "github_code": 0.08,
            "mql5_public": 0.08,
            "tradingview_public": 0.05,
            "quantconnect": 0.05,
            "practitioner_blogs": 0.04,
            
            # Track records
            "public_copy_leaderboards": 0.06,
            "verified_track_records": 0.04,
            "competition_results": 0.03,
            
            # Institutional
            "worldquant": 0.05,
            "alpha101": 0.03,
            "aqr": 0.03,
            "man_institute": 0.02,
            "arxiv": 0.03,
            "ssrn": 0.02,
            "university_theses": 0.02,
            
            # Events
            "trump_truth_social": 0.04,
            "central_banks": 0.03,
            "treasury": 0.02,
            "government_notices": 0.02,
            "sanctions": 0.02,
            "energy_opec": 0.02,
            
            # Operational
            "exchange_circulars": 0.02,
            "futures_rolls": 0.03,
            "fixing_calendars": 0.02,
            "index_rebalances": 0.03,
            "option_expiries": 0.02,
            "settlement_windows": 0.01,
            
            # Broker
            "fusion_spreads": 0.02,
            "fusion_swaps": 0.02,
            "slippage": 0.02,
            "tick_activity": 0.01,
            "session_anomalies": 0.01,
            
            # Weird data
            "shipping": 0.01,
            "inventories": 0.01,
            "warehouse_receipts": 0.02,
            "energy_load": 0.01,
            "commodity_flows": 0.01,
            "tenders": 0.01,
            "unknown_unknowns": 0.03,
            
            # Chinese lane (major)
            "china_bilibili": 0.02,
            "china_zhihu": 0.02,
            "china_gitee": 0.02,
            "china_csdn": 0.02,
            "china_joinquant": 0.02,
            "china_exchange_research": 0.03,
            "china_native_data": 0.02,
            
            # Other regions
            "japan_sources": 0.015,
            "korea_sources": 0.015,
            "russia_sources": 0.01,
            "brazil_sources": 0.01,
            "india_sources": 0.01,
            "mena_sources": 0.01,
            "turkey_sources": 0.01,
            "europe_sources": 0.01,
            "latam_sources": 0.01,
        }
        
        for name, fraction in allocations.items():
            module = MINER_REGISTRY.get(name, f"survivor_acquisition.sources.{name}")
            config = MinerConfig(
                name=name,
                module=module,
                enabled=True,
                budget_fraction=fraction,
                max_items_per_hour=50 if fraction > 0.02 else 20,
                priority=1 if fraction > 0.03 else 2,
                region=self._get_region(name),
                language=self._get_language(name),
                requires_translation=name.startswith("china_") or name.startswith("japan_") or name.startswith("korea_") or name.startswith("russia_"),
            )
            self.miner_configs[name] = config
        
        # Validate budget sums to ~1.0
        total = sum(allocations.values())
        print(f"Total budget allocation: {total:.3f}")
    
    def _get_region(self, name: str) -> str:
        if name.startswith("china_"): return "china"
        if name.startswith("japan_"): return "japan"
        if name.startswith("korea_"): return "korea"
        if name.startswith("russia_"): return "russia"
        if name.startswith("brazil_"): return "brazil"
        if name.startswith("india_"): return "india"
        if name.startswith("mena_"): return "mena"
        if name.startswith("turkey_"): return "turkey"
        if name.startswith("europe_"): return "europe"
        if name.startswith("latam_"): return "latam"
        if name in ["trump_truth_social", "central_banks", "treasury", "government_notices", "sanctions", "energy_opec"]: return "us"
        if name in ["fusion_spreads", "fusion_swaps", "slippage", "tick_activity", "session_anomalies"]: return "broker"
        return "global"
    
    def _get_language(self, name: str) -> str:
        if name.startswith("china_"): return "zh"
        if name.startswith("japan_"): return "ja"
        if name.startswith("korea_"): return "ko"
        if name.startswith("russia_"): return "ru"
        if name.startswith("brazil_"): return "pt"
        if name.startswith("india_"): return "hi"
        if name.startswith("mena_"): return "ar"
        if name.startswith("turkey_"): return "tr"
        if name.startswith("europe_"): return "de"
        if name.startswith("latam_"): return "es"
        return "en"
    
    def run_hourly_cycle(self) -> dict:
        """Execute one complete hourly cycle."""
        self.cycle_count += 1
        self.cycle_start_time = datetime.now(UTC)
        cycle_id = f"cycle_{self.cycle_count:06d}_{self.cycle_start_time.strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n{'='*60}")
        print(f"HOURLY CYCLE {self.cycle_count} STARTED: {cycle_id}")
        print(f"{'='*60}")
        
        results = {
            "cycle_id": cycle_id,
            "start_time": self.cycle_start_time.isoformat(),
            "phases": {},
            "hypotheses_generated": 0,
            "hypotheses_queued": 0,
            "budget_used": {},
            "errors": [],
        }
        
        try:
            # Phase 1: DISCOVER (00-08 min)
            results["phases"]["discover"] = self._phase_discover()
            
            # Phase 2: ACQUIRE (08-20 min)
            results["phases"]["acquire"] = self._phase_acquire()
            
            # Phase 3: EXTRACT (20-30 min)
            results["phases"]["extract"] = self._phase_extract()
            
            # Phase 4: REVERSE-ENGINEER (30-37 min)
            results["phases"]["reverse_engineer"] = self._phase_reverse_engineer()
            
            # Phase 5: TRANSLATE (37-43 min)
            results["phases"]["translate"] = self._phase_translate()
            
            # Phase 6: DEDUPE (43-50 min)
            results["phases"]["dedupe"] = self._phase_dedupe()
            
            # Phase 7: SCORE (50-55 min)
            results["phases"]["score"] = self._phase_score()
            
            # Phase 8: CHEAP FALSIFY (55-58 min)
            results["phases"]["cheap_falsify"] = self._phase_cheap_falsify()
            
            # Phase 9: MUTATE (58-60 min)
            results["phases"]["mutate"] = self._phase_mutate()
            
            # Phase 10: QUEUE
            results["phases"]["queue"] = self._phase_queue()
            
            # Phase 11: ATTRIBUTE & ADAPT
            results["phases"]["attribute"] = self._phase_attribute()
            
            results["hypotheses_generated"] = results["phases"]["extract"].get("hypotheses", 0)
            results["hypotheses_queued"] = results["phases"]["queue"].get("queued", 0)
            
        except Exception as e:
            results["errors"].append({
                "phase": "controller",
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            print(f"CYCLE ERROR: {e}")
        
        results["end_time"] = datetime.now(UTC).isoformat()
        results["duration_seconds"] = (datetime.now(UTC) - self.cycle_start_time).total_seconds()
        
        # Save state
        self._save_state()
        
        # Log cycle summary
        self._log_cycle(results)
        
        print(f"\nCYCLE COMPLETE: {results['hypotheses_generated']} hypotheses, {results['hypotheses_queued']} queued")
        print(f"Duration: {results['duration_seconds']:.1f}s")
        
        return results
    
    def _phase_discover(self) -> dict:
        """Phase 1: Find new/changed material since last sweep."""
        print("\n[00-08] DISCOVER: Finding new sources...")
        start = time.time()
        
        discoveries = {}
        for name, config in self.miner_configs.items():
            if not config.enabled:
                continue
            
            try:
                # Each miner implements a discover() method
                module = __import__(config.module, fromlist=["discover"])
                discover_fn = getattr(module, "discover", None)
                if discover_fn:
                    items = discover_fn(config, self.source_reputations.get(config.name))
                    discoveries[name] = len(items) if items else 0
                    
                    # Update source reputation
                    self._update_reputation(config.name, items_seen=len(items) if items else 0)
                    
            except Exception as e:
                print(f"  {name}: discover failed - {e}")
                discoveries[name] = 0
        
        return {"discoveries": discoveries, "duration_seconds": time.time() - start}
    
    def _phase_acquire(self) -> dict:
        """Phase 2: Retrieve evidence (transcripts, code, papers, data)."""
        print("\n[08-20] ACQUIRE: Retrieving evidence...")
        start = time.time()
        
        acquired = {}
        for name, config in self.miner_configs.items():
            if not config.enabled:
                continue
            if config.budget_fraction < 0.01:  # Skip tiny budgets
                continue
                
            try:
                module = __import__(config.module, fromlist=["acquire"])
                acquire_fn = getattr(module, "acquire", None)
                if acquire_fn:
                    budget = self.budget.allocate(name, config.budget_fraction)
                    items = acquire_fn(config, budget)
                    acquired[name] = len(items) if items else 0
                    
                    # Log raw items
                    if items:
                        with open(self.raw_items_file, "a") as f:
                            for item in items:
                                item["miner"] = name
                                item["acquired_at"] = datetime.now(UTC).isoformat()
                                f.write(json.dumps(item) + "\n")
                                
            except Exception as e:
                print(f"  {name}: acquire failed - {e}")
                acquired[name] = 0
        
        return {"acquired": acquired, "duration_seconds": time.time() - start}
    
    def _phase_extract(self) -> dict:
        """Phase 3: Convert to structured observations."""
        print("\n[20-30] EXTRACT: Converting to structured observations...")
        start = time.time()
        
        hypotheses_count = 0
        for name, config in self.miner_configs.items():
            if not config.enabled:
                continue
                
            try:
                module = __import__(config.module, fromlist=["extract"])
                extract_fn = getattr(module, "extract", None)
                if extract_fn:
                    items = self._load_raw_items(name)
                    if items:
                        hypotheses = extract_fn(config, items)
                        hypotheses_count += len(hypotheses) if hypotheses else 0
                        
                        # Save mechanisms
                        if hypotheses:
                            with open(self.mechanisms_file, "a") as f:
                                for h in hypotheses:
                                    h["extracted_by"] = name
                                    h["extracted_at"] = datetime.now(UTC).isoformat()
                                    f.write(json.dumps(h) + "\n")
                                    
            except Exception as e:
                print(f"  {name}: extract failed - {e}")
        
        return {"hypotheses": hypotheses_count, "duration_seconds": time.time() - start}
    
    def _phase_reverse_engineer(self) -> dict:
        """Phase 4: Infer testable mechanisms from public records."""
        print("\n[30-37] REVERSE-ENGINEER: Inferring mechanisms...")
        start = time.time()
        
        # Load extracted mechanisms
        mechanisms = self._load_mechanisms()
        
        # Run reverse engineering extractors
        from survivor_acquisition.extractors import (
            transcript_to_rules,
            code_to_rules,
            paper_to_mechanism,
            leaderboard_behavior,
            event_to_shock,
            dataset_to_features,
        )
        
        refined = 0
        for mech in mechanisms:
            try:
                extractor = self._select_extractor(mech)
                if extractor:
                    hypothesis = extractor(mech)
                    if hypothesis:
                        refined += 1
            except Exception as e:
                print(f"  Reverse-engineer failed: {e}")
        
        return {"refined": refined, "duration_seconds": time.time() - start}
    
    def _phase_translate(self) -> dict:
        """Phase 5: Convert foreign/non-MT5 ideas into MT5 hypotheses."""
        print("\n[37-43] TRANSLATE: Converting to MT5 hypotheses...")
        start = time.time()
        
        # Use hypothesis compiler and translator
        from survivor_acquisition.hypothesis import compiler, translator_mt5
        
        raw_mechanisms = self._load_mechanisms()
        cards = 0
        
        for mech in raw_mechanisms:
            try:
                card = compiler.compile_mechanism(mech)
                if card:
                    card = translator_mt5.translate_to_mt5(card)
                    if card:
                        card.save(self.data_path / "hypotheses" / f"{card.id}.yaml")
                        cards += 1
            except Exception as e:
                print(f"  Translate failed: {e}")
        
        return {"cards_created": cards, "duration_seconds": time.time() - start}
    
    def _phase_dedupe(self) -> dict:
        """Phase 6: Compare against existing hypotheses, graveyard, live strategies."""
        print("\n[43-50] DEDUPE: Checking against registry...")
        start = time.time()
        
        from survivor_acquisition.hypothesis import dedupe
        
        new_cards = list((self.data_path / "hypotheses").glob("H-*.yaml"))
        unique = 0
        duplicates = 0
        
        for card_path in new_cards:
            try:
                card = HypothesisCard.load(card_path)
                is_dup, match = dedupe.check(card)
                if is_dup:
                    duplicates += 1
                    card_path.unlink()  # Remove duplicate
                else:
                    unique += 1
            except Exception as e:
                print(f"  Dedup failed for {card_path}: {e}")
        
        return {"unique": unique, "duplicates": duplicates, "duration_seconds": time.time() - start}
    
    def _phase_score(self) -> dict:
        """Phase 7: Score by novelty, economics, independence, capacity, etc."""
        print("\n[50-55] SCORE: Ranking by expected research value...")
        start = time.time()
        
        from survivor_acquisition.intelligence import novelty, orthogonality, portfolio_gap
        
        scored = 0
        for card_path in (self.data_path / "hypotheses").glob("H-*.yaml"):
            try:
                card = HypothesisCard.load(card_path)
                
                # Novelty
                card.novelty = novelty.assess(card)
                
                # Orthogonality
                card.economics.orthogonality_score = orthogonality.assess(card)
                
                # Portfolio gap
                portfolio_boost = portfolio_gap.assess(card)
                
                # Composite score
                score = self._compute_composite_score(card)
                
                # Save score
                card.metadata["composite_score"] = score
                card.save(card_path)
                scored += 1
                
            except Exception as e:
                print(f"  Score failed: {e}")
        
        return {"scored": scored, "duration_seconds": time.time() - start}
    
    def _compute_composite_score(self, card: HypothesisCard) -> float:
        """Compute composite research value score."""
        # Score = Edge × Novelty × Orthogonality × PortfolioGap × Capacity × EvidenceQuality
        edge = min(card.economics.expected_edge_bps_per_trade / 10, 1.0)  # 10bps = 1.0
        novelty = 1.0 - card.novelty.similarity
        ortho = card.economics.orthogonality_score
        portfolio_gap = portfolio_gap.assess(card)
        capacity = min(card.economics.expected_capacity_lots / 100, 1.0)
        evidence = {"primary_public": 1.0, "secondary_public": 0.8, 
                    "code_derived": 0.9, "practitioner_claim": 0.6}.get(
                        card.origin.evidence_tier.value, 0.5)
        
        return edge * novelty * ortho * portfolio_gap * capacity * evidence
    
    def _phase_cheap_falsify(self) -> dict:
        """Phase 8: Basic economics, timing/leakage, costs, minimum sample, placebo."""
        print("\n[55-58] CHEAP FALSIFY: Killing weak ideas...")
        start = time.time()
        
        from survivor_acquisition.screening import cheap_falsifier, leakage, costs, placebo, mt5_feasibility
        
        killed = 0
        passed = 0
        
        for card_path in (self.data_path / "hypotheses").glob("H-*.yaml"):
            try:
                card = HypothesisCard.load(card_path)
                
                # Run all cheap falsifiers
                if not cheap_falsifier.check(card):
                    card_path.unlink()
                    killed += 1
                    continue
                
                if not leakage.check(card):
                    card_path.unlink()
                    killed += 1
                    continue
                
                if not costs.check(card):
                    card_path.unlink()
                    killed += 1
                    continue
                
                if not placebo.check(card):
                    card_path.unlink()
                    killed += 1
                    continue
                
                if not mt5_feasibility.check(card):
                    card_path.unlink()
                    killed += 1
                    continue
                
                passed += 1
                
            except Exception as e:
                print(f"  Falsify failed: {e}")
        
        return {"passed": passed, "killed": killed, "duration_seconds": time.time() - start}
    
    def _phase_mutate(self) -> dict:
        """Phase 9: Generate mechanism-defensible variants."""
        print("\n[58-60] MUTATE: Intelligent variants...")
        start = time.time()
        
        from survivor_acquisition.hypothesis import mutation
        
        mutated = 0
        for card_path in (self.data_path / "hypotheses").glob("H-*.yaml"):
            try:
                card = HypothesisCard.load(card_path)
                config = self.miner_configs.get("default", MinerConfig(name="default", module=""))
                config.mutation_budget = 3
                
                variants = mutation.generate_variants(card, config)
                for var in variants:
                    var.save(self.data_path / "hypotheses" / f"{var.id}.yaml")
                    mutated += 1
                    
            except Exception as e:
                print(f"  Mutate failed: {e}")
        
        return {"mutated": mutated, "duration_seconds": time.time() - start}
    
    def _phase_queue(self) -> dict:
        """Phase 10: Push best cards to research_queue."""
        print("\n[QUEUE] Pushing to research queue...")
        start = time.time()
        
        # Load research queue
        queue = []
        if self.research_queue_file.exists():
            with open(self.research_queue_file, "r") as f:
                queue = json.load(f)
        
        queued = 0
        for card_path in (self.data_path / "hypotheses").glob("H-*.yaml"):
            try:
                card = HypothesisCard.load(card_path)
                score = card.metadata.get("composite_score", 0)
                
                if score > 0.3:  # Threshold for queueing
                    entry = {
                        "id": card.id,
                        "card_path": str(card_path),
                        "score": score,
                        "priority": int(score * 100),
                        "mechanism": card.mechanism.mechanism_class.value,
                        "symbols": card.market.symbols,
                        "session": card.market.session,
                        "added_at": datetime.now(UTC).isoformat(),
                        "source": card.origin.source_type,
                        "region": card.origin.region,
                    }
                    queue.append(entry)
                    queued += 1
                    
            except Exception as e:
                print(f"  Queue failed: {e}")
        
        # Sort by priority
        queue.sort(key=lambda x: -x["priority"])
        
        # Keep top N
        queue = queue[:500]
        
        # Save queue
        self.research_queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.research_queue_file, "w") as f:
            json.dump(queue, f, indent=2)
        
        return {"queued": queued, "queue_size": len(queue), "duration_seconds": time.time() - start}
    
    def _phase_attribute(self) -> dict:
        """Phase 11: Attribute survivors to sources, adapt budget."""
        print("\n[ATTRIBUTE] Attributing & adapting budget...")
        start = time.time()
        
        # Update source reputations based on outcomes
        self._update_source_reputations()
        
        # Reallocate budget for next cycle
        self._reallocate_budget()
        
        return {"reputations_updated": len(self.source_reputations), "duration_seconds": time.time() - start}
    
    def _update_reputation(self, source_name: str, **kwargs) -> None:
        """Update source reputation with new metrics."""
        if source_name not in self.source_reputations:
            self.source_reputations[source_name] = SourceReputation(
                source_id=source_name,
                source_type=self.miner_configs[source_name].module.split(".")[-1] if source_name in self.miner_configs else "unknown",
                region=self._get_region(source_name),
            )
        
        rep = self.source_reputations[source_name]
        for k, v in kwargs.items():
            if hasattr(rep, k):
                setattr(rep, k, getattr(rep, k) + v)
        
        rep.last_updated = datetime.now(UTC).isoformat()
    
    def _update_source_reputations(self) -> None:
        """Update reputations based on validation outcomes."""
        # This would be called with actual outcomes from validation/shadow
        pass
    
    def _reallocate_budget(self) -> None:
        """Reallocate budget based on source ROI."""
        # Compute ROI for each source
        for name, rep in self.source_reputations.items():
            if rep.total_research_cost_usd > 0:
                rep.recent_roi = rep.incremental_elogw / rep.total_research_cost_usd
            else:
                rep.recent_roi = 0.0
        
        # Sort by ROI
        sorted_sources = sorted(
            self.source_reputations.items(),
            key=lambda x: x[1].recent_roi,
            reverse=True
        )
        
        # Boost top performers, decay bottom
        # (Implementation would adjust miner_configs budget_fraction)
        pass
    
    def _load_raw_items(self, miner_name: str) -> list:
        """Load raw items for a miner."""
        items = []
        if self.raw_items_file.exists():
            with open(self.raw_items_file, "r") as f:
                for line in f:
                    item = json.loads(line)
                    if item.get("miner") == miner_name:
                        items.append(item)
        return items
    
    def _load_mechanisms(self) -> list:
        """Load extracted mechanisms."""
        mechanisms = []
        if self.mechanisms_file.exists():
            with open(self.mechanisms_file, "r") as f:
                for line in f:
                    mechanisms.append(json.loads(line))
        return mechanisms
    
    def _select_extractor(self, mech: dict):
        """Select appropriate extractor for mechanism."""
        source = mech.get("source_type", "")
        if "transcript" in source or "video" in source:
            from survivor_acquisition.extractors import transcript_to_rules
            return transcript_to_rules.extract
        elif "code" in source or "github" in source:
            from survivor_acquisition.extractors import code_to_rules
            return code_to_rules.extract
        elif "paper" in source or "arxiv" in source:
            from survivor_acquisition.extractors import paper_to_mechanism
            return paper_to_mechanism.extract
        elif "leaderboard" in source:
            from survivor_acquisition.extractors import leaderboard_behavior
            return leaderboard_behavior.extract
        elif "event" in source:
            from survivor_acquisition.extractors import event_to_shock
            return event_to_shock.extract
        elif "dataset" in source:
            from survivor_acquisition.extractors import dataset_to_features
            return dataset_to_features.extract
        return None
    
    def _log_cycle(self, results: dict) -> None:
        """Log cycle summary."""
        log_file = self.base_path / "logs" / "survivor_acquisition_cycles.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(results) + "\n")


def run_forever(base_path: Path, interval_minutes: int = 60) -> None:
    """Run controller forever with specified interval."""
    controller = HourlyController(base_path)
    
    print(f"Starting Hourly Survivor Acquisition Controller")
    print(f"Interval: {interval_minutes} minutes")
    print(f"Base path: {base_path}")
    
    while True:
        try:
            controller.run_hourly_cycle()
        except KeyboardInterrupt:
            print("\nShutdown requested")
            break
        except Exception as e:
            print(f"Cycle error: {e}")
            traceback.print_exc()
        
        # Sleep until next hour
        elapsed = (datetime.now(UTC) - controller.cycle_start_time).total_seconds() if controller.cycle_start_time else 0
        sleep_time = max(0, interval_minutes * 60 - elapsed)
        print(f"Sleeping {sleep_time:.0f}s until next cycle...")
        time.sleep(sleep_time)


if __name__ == "__main__":
    import sys
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/quant/quant-platform")
    run_forever(base)