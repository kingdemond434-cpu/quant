"""MQL5 Source Reputation Tracking — tracks ROI per MQL5 source/author.

Every MQL5 source accumulates a real track record:
  items_seen
  testable_mechanisms
  novel_mechanisms
  fast_screen_passes
  heavy_validation_passes
  shadow_survivors
  live_survivors
  incremental E[log W]
  research_cost (LLM tokens, compute, time)

The hunter learns which MQL5 authors/categories actually produce usable mechanisms
and autonomously redirects research capacity.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from collections import defaultdict

import numpy as np

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


@dataclass
class MQL5SourceMetrics:
    """Performance metrics for an MQL5 source."""
    source_id: str                              # e.g., "mql5_codebase_author_john"
    source_type: Literal["codebase", "articles", "signals", "forum"]
    author: str | None = None
    
    # Volume
    items_seen: int = 0
    testable_mechanisms: int = 0
    novel_mechanisms: int = 0
    
    # Pipeline
    fast_screen_passes: int = 0
    heavy_validation_passes: int = 0
    shadow_survivors: int = 0
    live_survivors: int = 0
    
    # Costs
    total_llm_tokens: int = 0
    total_llm_cost_usd: float = 0.0
    total_cpu_hours: float = 0.0
    total_wall_hours: float = 0.0
    total_data_cost_usd: float = 0.0
    
    # Returns
    incremental_elogw: float = 0.0
    
    # Quality
    avg_edge_bps: float = 0.0
    avg_orthogonality: float = 0.0
    avg_novelty: float = 0.0
    
    # Derived
    cost_per_hypothesis: float = 0.0
    cost_per_survivor: float = 0.0
    cost_per_elogw: float = 0.0
    hypotheses_per_token: float = 0.0
    hypotheses_per_cpu_hour: float = 0.0
    survivors_per_cpu_hour: float = 0.0
    elogw_per_usd: float = 0.0
    
    # Rolling windows
    recent_30d_roi: float = 0.0
    recent_7d_roi: float = 0.0
    
    # Timestamps
    first_seen: str | None = None
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    exploration_bonus: float = 1.0  # >1 encourages exploration
    
    def update_derived(self) -> None:
        """Recalculate derived metrics."""
        if self.items_seen > 0:
            self.cost_per_hypothesis = (self.total_llm_cost_usd + self.total_cpu_hours * 0.50) / max(self.testable_mechanisms, 1)
            self.hypotheses_per_token = self.testable_mechanisms / max(self.total_llm_tokens, 1)
            self.hypotheses_per_cpu_hour = self.testable_mechanisms / max(self.total_cpu_hours, 1e-6)
        
        if self.live_survivors > 0:
            self.cost_per_survivor = (self.total_llm_cost_usd + self.total_cpu_hours * 0.50) / self.live_survivors
            self.survivors_per_cpu_hour = self.live_survivors / max(self.total_cpu_hours, 1e-6)
        
        if self.incremental_elogw > 0:
            total_cost = self.total_llm_cost_usd + self.total_cpu_hours * 0.50
            self.cost_per_elogw = total_cost / self.incremental_elogw
            self.elogw_per_usd = self.incremental_elogw / max(total_cost, 1e-6)


@dataclass
class MQL5SourceReputation:
    """Reputation score for an MQL5 source."""
    source_id: str
    source_type: Literal["codebase", "articles", "signals", "forum"]
    author: str | None = None
    category: str | None = None  # e.g., "trend", "grid", "scalping", "news"
    
    # Reputation score (0-1)
    reputation_score: float = 0.5
    confidence: float = 0.0  # 0-1, how confident we are in the score
    
    # Performance
    total_hypotheses: int = 0
    unique_hypotheses: int = 0
    survivors: int = 0
    incremental_elogw: float = 0.0
    
    # ROI
    cost_per_hypothesis: float = 0.0
    cost_per_survivor: float = 0.0
    elogw_per_usd: float = 0.0
    hypotheses_per_cpu_hour: float = 0.0
    
    # Quality
    avg_edge_bps: float = 0.0
    avg_orthogonality: float = 0.0
    avg_novelty: float = 0.0
    
    # Exploration
    exploration_bonus: float = 1.0  # >1 encourages exploration
    
    # Timestamps
    first_seen: str | None = None
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    
    def update_reputation(self) -> None:
        """Update reputation score based on performance."""
        # Base score from ROI
        if self.elogw_per_usd > 0:
            self.reputation_score = min(1.0, self.elogw_per_usd * 10)
        
        # Adjust for volume
        if self.total_hypotheses > 10:
            self.confidence = min(1.0, self.total_hypotheses / 100)
        
        # Penalize zero ROI
        if self.elogw_per_usd <= 0 and self.total_hypotheses > 5:
            self.reputation_score *= 0.5


class MQL5ReputationTracker:
    """Tracks reputation and ROI for MQL5 sources."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.reputation_dir = base_path / "data" / "intelligence" / "mql5_reputation"
        self.reputation_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_file = self.reputation_dir / "source_metrics.json"
        self.reputation_file = self.reputation_dir / "source_reputation.json"
        self.history_file = self.reputation_dir / "reputation_history.jsonl"
        
        self.metrics: dict[str, MQL5SourceMetrics] = {}
        self.reputations: dict[str, MQL5SourceReputation] = {}
        self._load_state()
    
    def _load_state(self) -> None:
        if self.metrics_file.exists():
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                self.metrics[k] = MQL5SourceMetrics(**v)
        
        if self.reputation_file.exists():
            with open(self.reputation_file, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                self.reputations[k] = MQL5SourceReputation(**v)
    
    def _save_state(self) -> None:
        with open(self.metrics_file, "w") as f:
            json.dump({k: v.__dict__ for k, v in self.metrics.items()}, f, indent=2, default=str)
        
        with open(self.reputation_file, "w") as f:
            json.dump({k: v.__dict__ for k, v in self.reputations.items()}, f, indent=2, default=str)
    
    def _log_history(self, source_id: str, event: str, details: dict) -> None:
        with open(self.history_file, "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(UTC).isoformat(),
                "source_id": source_id,
                "event": event,
                "details": details,
            }) + "\n")
    
    def record_cost(self, source_id: str, source_type: str, 
                     llm_tokens: int = 0, llm_cost_usd: float = 0.0,
                     cpu_hours: float = 0.0, wall_hours: float = 0.0,
                     data_cost_usd: float = 0.0, author: str = "") -> None:
        """Record research cost for a source."""
        if source_id not in self.metrics:
            self.metrics[source_id] = MQL5SourceMetrics(
                source_id=source_id,
                source_type=source_type,
                author=author,
                first_seen=datetime.now(UTC).isoformat(),
            )
        
        m = self.metrics[source_id]
        m.total_llm_tokens += llm_tokens
        m.total_llm_cost_usd += llm_cost_usd
        m.total_cpu_hours += cpu_hours
        m.total_wall_hours += wall_hours
        m.total_data_cost_usd += data_cost_usd
        m.last_updated = datetime.now(UTC).isoformat()
        m.update_derived()
        
        self._log_history(source_id, "cost_recorded", {
            "llm_tokens": llm_tokens,
            "llm_cost_usd": llm_cost_usd,
            "cpu_hours": cpu_hours,
        })
    
    def record_output(self, source_id: str, source_type: str,
                       hypotheses: int = 0, unique: int = 0, 
                       cheap_passes: int = 0, heavy_passes: int = 0,
                       shadow: int = 0, live: int = 0,
                       incremental_elogw: float = 0.0,
                       avg_edge_bps: float = 0.0,
                       avg_orthogonality: float = 0.0,
                       avg_novelty: float = 0.0,
                       author: str = "") -> None:
        """Record research output for a source."""
        if source_id not in self.metrics:
            self.metrics[source_id] = MQL5SourceMetrics(
                source_id=source_id,
                source_type=source_type,
                author=author,
                first_seen=datetime.now(UTC).isoformat(),
            )
        
        m = self.metrics[source_id]
        m.testable_mechanisms += hypotheses
        m.unique_hypotheses = unique
        m.fast_screen_passes += cheap_passes
        m.heavy_validation_passes += heavy_passes
        m.shadow_survivors += shadow
        m.live_survivors += live
        m.incremental_elogw += incremental_elogw
        m.avg_edge_bps = ((m.avg_edge_bps * (m.live_survivors - live)) + 
                          avg_edge_bps * live) / max(m.live_survivors, 1)
        m.avg_orthogonality = ((m.avg_orthogonality * (m.live_survivors - live)) + 
                               avg_orthogonality * live) / max(m.live_survivors, 1)
        m.avg_novelty = ((m.avg_novelty * (m.live_survivors - live)) + 
                         avg_novelty * live) / max(m.live_survivors, 1)
        m.last_updated = datetime.now(UTC).isoformat()
        m.update_derived()
        
        # Update reputation
        self._update_reputation(source_id, source_type, author)
        
        self._log_history(source_id, "output_recorded", {
            "hypotheses": hypotheses,
            "unique": unique,
            "cheap_passes": cheap_passes,
            "heavy_passes": heavy_passes,
            "shadow": shadow,
            "live": live,
            "elogw": incremental_elogw,
        })
    
    def _update_reputation(self, source_id: str, source_type: str, author: str) -> None:
        if source_id not in self.metrics:
            return
        
        m = self.metrics[source_id]
        
        if source_id not in self.reputations:
            self.reputations[source_id] = MQL5SourceReputation(
                source_id=source_id,
                source_type=source_type,
                author=author,
            )
        
        r = self.reputations[source_id]
        r.total_hypotheses = m.testable_mechanisms
        r.unique_hypotheses = m.unique_hypotheses
        r.survivors = m.live_survivors
        r.incremental_elogw = m.incremental_elogw
        r.cost_per_hypothesis = m.cost_per_hypothesis
        r.cost_per_survivor = m.cost_per_survivor
        r.elogw_per_usd = m.elogw_per_usd
        r.hypotheses_per_cpu_hour = m.hypotheses_per_cpu_hour
        r.avg_edge_bps = m.avg_edge_bps
        r.avg_orthogonality = m.avg_orthogonality
        r.avg_novelty = m.avg_novelty
        r.last_updated = datetime.now(UTC).isoformat()
        r.update_reputation()
    
    def get_reputation(self, source_id: str) -> MQL5SourceReputation | None:
        return self.reputations.get(source_id)
    
    def get_all_reputations(self) -> dict[str, MQL5SourceReputation]:
        return self.reputations
    
    def get_leaderboard(self, metric: str = "elogw_per_usd", top_n: int = 20) -> list[dict]:
        """Get leaderboard of sources by metric."""
        valid = [r for r in self.reputations.values() if getattr(r, metric, 0) > 0]
        valid.sort(key=lambda x: getattr(x, metric, 0), reverse=True)
        
        return [
            {
                "rank": i + 1,
                "source_id": r.source_id,
                "source_type": r.source_type,
                "author": r.author,
                "category": r.category,
                "metric_value": getattr(r, metric),
                "reputation_score": r.reputation_score,
                "total_hypotheses": r.total_hypotheses,
                "survivors": r.survivors,
                "incremental_elogw": r.incremental_elogw,
            }
            for i, r in enumerate(valid[:top_n])
        ]
    
    def get_allocation(self, total_budget_usd: float = 1000.0,
                        strategy: str = "roi_proportional") -> dict[str, float]:
        """Compute budget allocation for next period."""
        positive = {k: v for k, v in self.reputations.items() if v.elogw_per_usd > 0}
        
        if not positive:
            return {}
        
        if strategy == "roi_proportional":
            total = sum(v.elogw_per_usd for v in positive.values())
            allocation = {k: (v.elogw_per_usd / total) * total_budget_usd for k, v in positive.items()}
        
        elif strategy == "thompson_sampling":
            allocation = {}
            for k, v in self.reputations.items():
                if v.total_hypotheses == 0:
                    allocation[k] = 50.0  # Explore new
                else:
                    alpha = 1 + v.survivors
                    beta = 1 + max(v.total_hypotheses - v.survivors, 0)
                    sample = np.random.beta(alpha, beta)
                    allocation[k] = sample
            
            total = sum(allocation.values())
            allocation = {k: v / total * total_budget_usd for k, v in allocation.items()}
        
        elif strategy == "epsilon_greedy":
            epsilon = 0.1
            best = max(self.reputations.items(), key=lambda x: x[1].elogw_per_usd)
            allocation = {k: 0 for k in self.reputations}
            allocation[best[0]] = (1 - epsilon) * total_budget_usd
            remaining = epsilon * total_budget_usd
            n = len(self.reputations) - 1
            for k in self.reputations:
                if k != best[0]:
                    allocation[k] = remaining / n
        
        else:  # equal
            n = len(self.reputations)
            allocation = {k: total_budget_usd / n for k in self.reputations}
        
        return allocation
    
    def get_source_budget_fraction(self, source_id: str) -> float:
        """Get budget fraction for a source based on reputation."""
        if source_id not in self.reputations:
            return 0.01  # Default small fraction for unknown
        
        r = self.reputations[source_id]
        # Base on reputation score and exploration bonus
        return max(0.005, r.reputation_score * r.exploration_bonus)
    
    def save_all(self) -> None:
        self._save_state()
    
    def generate_report(self) -> dict:
        """Generate full reputation report."""
        return {
            "total_sources": len(self.reputations),
            "total_hypotheses": sum(r.total_hypotheses for r in self.reputations.values()),
            "total_survivors": sum(r.survivors for r in self.reputations.values()),
            "total_elogw": sum(r.incremental_elogw for r in self.reputations.values()),
            "leaderboard": self.get_leaderboard("elogw_per_usd", 10),
            "by_type": {
                t: {
                    "count": sum(1 for r in self.reputations.values() if r.source_type == t),
                    "avg_reputation": np.mean([r.reputation_score for r in self.reputations.values() if r.source_type == t]) if any(r.source_type == t for r in self.reputations.values()) else 0,
                }
                for t in ["codebase", "articles", "signals", "forum"]
            },
            "allocation": self.get_allocation(1000.0),
        }


def track_mql5_cost(source_id: str, source_type: str, tokens: int, cost_usd: float,
                     tracker: MQL5ReputationTracker) -> None:
    """Convenience function to track LLM call."""
    tracker.record_cost(source_id, source_type, llm_tokens=tokens, llm_cost_usd=cost_usd)


def track_mql5_compute(source_id: str, source_type: str, cpu_hours: float, wall_hours: float,
                        tracker: MQL5ReputationTracker) -> None:
    """Convenience function to track compute."""
    tracker.record_cost(source_id, source_type, cpu_hours=cpu_hours, wall_hours=wall_hours)


def track_mql5_output(source_id: str, source_type: str,
                       hypotheses: int = 0, unique: int = 0, cheap: int = 0,
                       heavy: int = 0, shadow: int = 0, live: int = 0,
                       elogw: float = 0.0, tracker: MQL5ReputationTracker = None) -> None:
    """Convenience function to track output."""
    if tracker:
        tracker.record_output(source_id, source_type, hypotheses, unique, cheap, heavy, shadow, live, elogw)


def generate_mql5_economics_report(tracker: MQL5ReputationTracker) -> dict:
    """Generate full economics report."""
    return tracker.generate_report()


def auto_reallocate_mql5_budget(tracker: MQL5ReputationTracker, 
                                 total_budget: float = 1000.0) -> dict:
    """Automatically reallocate MQL5 budget based on ROI."""
    allocation = tracker.get_allocation(total_budget, "roi_proportional")
    
    # Log reallocation
    with open(Path("data/intelligence/mql5_reputation/reallocations.jsonl"), "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "allocation": allocation,
        }) + "\n")
    
    return allocation


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    tracker = MQL5ReputationTracker(base)
    
    # Simulate some data
    sources = [
        ("mql5_codebase_author_john", "codebase", 50, 10, 8, 3, 2, 0.005),
        ("mql5_codebase_author_mary", "codebase", 30, 8, 6, 2, 1, 0.003),
        ("mql5_articles_author_bob", "articles", 20, 5, 4, 2, 1, 0.002),
        ("mql5_signals_trader_alex", "signals", 10, 2, 1, 1, 1, 0.01),
        ("mql5_forum_author_chris", "forum", 15, 3, 2, 1, 0, 0.0),
    ]
    
    for sid, stype, cost, hyp, unique, cheap, live, elogw in sources:
        tracker.record_cost(sid, stype, llm_cost_usd=cost*0.01, cpu_hours=cost*0.1)
        tracker.record_output(sid, stype, hyp, unique, cheap, 0, 0, live, elogw)
    
    tracker.save_all()
    
    report = tracker.generate_report()
    print(json.dumps(report, indent=2, default=str))
    
    allocation = tracker.get_allocation(1000.0)
    print("\nBudget Allocation:")
    for k, v in sorted(allocation.items(), key=lambda x: -x[1])[:10]:
        print(f"  {k}: ${v:.2f}")