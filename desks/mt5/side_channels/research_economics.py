"""Research Economics Dashboard — tracks ROI per mechanism, source, miner.

Every research mechanism gets:
  € / LLM tokens
  CPU hours
  wall-clock hours
  hypotheses produced
  unique hypotheses
  cheap-screen passes
  full-gate passes
  shadow survivors
  live survivors
  incremental E[log W]

The machine learns where survivors actually come from and autonomously
redirects research capacity.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd


@dataclass
class ResearchCost:
    """Cost of a research operation."""
    llm_tokens: int = 0
    llm_cost_usd: float = 0.0
    cpu_hours: float = 0.0
    wall_clock_hours: float = 0.0
    data_cost_usd: float = 0.0
    human_hours: float = 0.0
    
    def total_usd(self, cpu_rate: float = 0.50, human_rate: float = 50.0) -> float:
        return (self.llm_cost_usd + self.cpu_hours * cpu_rate + 
                self.data_cost_usd + self.human_hours * human_rate)


@dataclass
class ResearchOutput:
    """Output of a research operation."""
    hypotheses_produced: int = 0
    unique_hypotheses: int = 0
    cheap_screen_passes: int = 0
    heavy_gate_passes: int = 0
    shadow_survivors: int = 0
    live_survivors: int = 0
    incremental_elogw: float = 0.0
    
    # Quality metrics
    avg_edge_bps: float = 0.0
    avg_orthogonality: float = 0.0
    avg_novelty: float = 0.0


@dataclass
class ResearchROI:
    """ROI metrics for a research unit."""
    unit_id: str
    unit_type: Literal["source", "miner", "mechanism", "region", "mechanism_class"]
    
    # Costs
    total_cost_usd: float = 0.0
    total_llm_tokens: int = 0
    total_cpu_hours: float = 0.0
    total_wall_hours: float = 0.0
    
    # Outputs
    total_hypotheses: int = 0
    total_unique: int = 0
    total_cheap_passes: int = 0
    total_heavy_passes: int = 0
    total_shadow: int = 0
    total_live: int = 0
    total_incremental_elogw: float = 0.0
    
    # Derived
    cost_per_hypothesis: float = 0.0
    cost_per_unique: float = 0.0
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
    
    def update_derived(self) -> None:
        """Recalculate derived metrics."""
        if self.total_hypotheses > 0:
            self.cost_per_hypothesis = self.total_cost_usd / self.total_hypotheses
            self.hypotheses_per_token = self.total_hypotheses / max(self.total_llm_tokens, 1)
            self.hypotheses_per_cpu_hour = self.total_hypotheses / max(self.total_cpu_hours, 1e-6)
        
        if self.total_unique > 0:
            self.cost_per_unique = self.total_cost_usd / self.total_unique
        
        if self.total_live > 0:
            self.cost_per_survivor = self.total_cost_usd / self.total_live
            self.survivors_per_cpu_hour = self.total_live / max(self.total_cpu_hours, 1e-6)
        
        if self.total_incremental_elogw > 0:
            self.cost_per_elogw = self.total_cost_usd / self.total_incremental_elogw
            self.elogw_per_usd = self.total_incremental_elogw / max(self.total_cost_usd, 1e-6)


class ResearchEconomicsTracker:
    """Tracks research economics across all units."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.econ_dir = base_path / "data" / "research_economics"
        self.econ_dir.mkdir(parents=True, exist_ok=True)
        
        self.roi_file = self.econ_dir / "research_roi.json"
        self.costs_file = self.econ_dir / "research_costs.jsonl"
        self.outputs_file = self.econ_dir / "research_outputs.jsonl"
        self.allocation_file = self.econ_dir / "budget_allocation.json"
        
        self.roi: dict[str, ResearchROI] = {}
        self._load_roi()
    
    def _load_roi(self) -> None:
        if self.roi_file.exists():
            with open(self.roi_file, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                self.roi[k] = ResearchROI(**v)
    
    def _save_roi(self) -> None:
        with open(self.roi_file, "w") as f:
            json.dump({k: v.__dict__ for k, v in self.roi.items()}, f, indent=2, default=str)
    
    def record_cost(self, unit_id: str, unit_type: str, cost: ResearchCost) -> None:
        """Record research cost for a unit."""
        if unit_id not in self.roi:
            self.roi[unit_id] = ResearchROI(unit_id=unit_id, unit_type=unit_type)
            self.roi[unit_id].first_seen = datetime.now(UTC).isoformat()
        
        roi = self.roi[unit_id]
        roi.total_cost_usd += cost.total_usd()
        roi.total_llm_tokens += cost.llm_tokens
        roi.total_cpu_hours += cost.cpu_hours
        roi.total_wall_hours += cost.wall_clock_hours
        roi.last_updated = datetime.now(UTC).isoformat()
        roi.update_derived()
        
        # Log cost
        with open(self.costs_file, "a") as f:
            f.write(json.dumps({
                "unit_id": unit_id,
                "unit_type": unit_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "llm_tokens": cost.llm_tokens,
                "llm_cost_usd": cost.llm_cost_usd,
                "cpu_hours": cost.cpu_hours,
                "wall_clock_hours": cost.wall_clock_hours,
                "data_cost_usd": cost.data_cost_usd,
                "human_hours": cost.human_hours,
                "total_usd": cost.total_usd(),
            }) + "\n")
    
    def record_output(self, unit_id: str, unit_type: str, output: ResearchOutput) -> None:
        """Record research output for a unit."""
        if unit_id not in self.roi:
            self.roi[unit_id] = ResearchROI(unit_id=unit_id, unit_type=unit_type)
            self.roi[unit_id].first_seen = datetime.now(UTC).isoformat()
        
        roi = self.roi[unit_id]
        roi.total_hypotheses += output.hypotheses_produced
        roi.total_unique += output.unique_hypotheses
        roi.total_cheap_passes += output.cheap_screen_passes
        roi.total_heavy_passes += output.heavy_gate_passes
        roi.total_shadow += output.shadow_survivors
        roi.total_live += output.live_survivors
        roi.total_incremental_elogw += output.incremental_elogw
        roi.last_updated = datetime.now(UTC).isoformat()
        roi.update_derived()
        
        # Log output
        with open(self.outputs_file, "a") as f:
            f.write(json.dumps({
                "unit_id": unit_id,
                "unit_type": unit_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "hypotheses_produced": output.hypotheses_produced,
                "unique_hypotheses": output.unique_hypotheses,
                "cheap_screen_passes": output.cheap_screen_passes,
                "heavy_gate_passes": output.heavy_gate_passes,
                "shadow_survivors": output.shadow_survivors,
                "live_survivors": output.live_survivors,
                "incremental_elogw": output.incremental_elogw,
            }) + "\n")
    
    def get_roi(self, unit_id: str) -> ResearchROI | None:
        return self.roi.get(unit_id)
    
    def get_all_roi(self) -> dict[str, ResearchROI]:
        return self.roi
    
    def get_leaderboard(self, metric: str = "elogw_per_usd", top_n: int = 20) -> list[dict]:
        """Get leaderboard of research units by metric."""
        valid = [r for r in self.roi.values() if getattr(r, metric, 0) > 0]
        valid.sort(key=lambda x: getattr(x, metric, 0), reverse=True)
        
        return [
            {
                "rank": i + 1,
                "unit_id": r.unit_id,
                "unit_type": r.unit_type,
                "metric_value": getattr(r, metric),
                "total_cost_usd": r.total_cost_usd,
                "total_live": r.total_live,
                "total_incremental_elogw": r.total_incremental_elogw,
            }
            for i, r in enumerate(valid[:top_n])
        ]
    
    def compute_allocation(self, total_budget_usd: float = 1000.0,
                            strategy: str = "roi_proportional") -> dict[str, float]:
        """Compute budget allocation for next period."""
        # Filter to units with positive ROI
        positive = {k: v for k, v in self.roi.items() 
                    if v.elogw_per_usd > 0 and v.total_live > 0}
        
        if not positive:
            return {}
        
        if strategy == "roi_proportional":
            # Allocate proportionally to E[log W] per USD
            total_elogw_per_usd = sum(v.elogw_per_usd for v in self.roi.values() if v.elogw_per_usd > 0)
            allocation = {}
            for k, v in self.roi.items():
                if v.elogw_per_usd > 0:
                    allocation[v.unit_id] = (v.elogw_per_usd / sum(u.elogw_per_usd for u in self.roi.values() if u.elogw_per_usd > 0)) * 1000
        
        elif strategy == "thompson_sampling":
            # Thompson sampling for exploration/exploitation
            allocation = {}
            for k, v in self.roi.items():
                if v.total_cost_usd == 0:
                    allocation[v.unit_id] = 100  # Explore new
                else:
                    # Sample from Beta(1+successes, 1+failures)
                    alpha = 1 + v.total_live
                    beta = 1 + max(v.total_cost_usd - v.total_live * 100, 0)  # rough
                    sample = np.random.beta(alpha, beta)
                    allocation[v.unit_id] = sample
            
            # Normalize
            total = sum(allocation.values())
            allocation = {k: v / total * 1000 for k, v in allocation.items()}
        
        else:  # equal
            n = len(self.roi)
            allocation = {k: 1000.0 / n for k in self.roi}
        
        # Save allocation
        with open(self.allocation_file, "w") as f:
            json.dump({
                "strategy": strategy,
                "total_budget_usd": total_budget_usd,
                "allocation": allocation,
                "computed_at": datetime.now(UTC).isoformat(),
            }, f, indent=2)
        
        return allocation
    
    def generate_dashboard(self) -> dict:
        """Generate full dashboard data."""
        # Leaderboards
        leaderboards = {
            "elogw_per_usd": self.get_leaderboard("elogw_per_usd"),
            "survivors_per_cpu_hour": self.get_leaderboard("survivors_per_cpu_hour"),
            "hypotheses_per_cpu_hour": self.get_leaderboard("hypotheses_per_cpu_hour"),
            "cost_per_survivor": self.get_leaderboard("cost_per_survivor"),
        }
        
        # By type
        by_type = {}
        for r in self.roi.values():
            t = r.unit_type
            if t not in by_type:
                by_type[t] = {"count": 0, "total_cost": 0, "total_live": 0, "total_elogw": 0}
            by_type[t]["count"] += 1
            by_type[t]["total_cost"] += r.total_cost_usd
            by_type[t]["total_live"] += r.total_live
            by_type[t]["total_elogw"] += r.total_incremental_elogw
        
        # Aggregate totals
        total_cost = sum(r.total_cost_usd for r in self.roi.values())
        total_live = sum(r.total_live for r in self.roi.values())
        total_elogw = sum(r.total_incremental_elogw for r in self.roi.values())
        
        return {
            "summary": {
                "total_units": len(self.roi),
                "total_cost_usd": total_cost,
                "total_live_survivors": sum(r.total_live for r in self.roi.values()),
                "total_incremental_elogw": sum(r.total_incremental_elogw for r in self.roi.values()),
                "overall_elogw_per_usd": sum(r.total_incremental_elogw for r in self.roi.values()) / max(sum(r.total_cost_usd for r in self.roi.values()), 1),
            },
            "leaderboards": leaderboards,
            "by_type": by_type,
            "unit_details": {k: v.__dict__ for k, v in self.roi.items()},
        }
    
    def export_for_budget_allocation(self, total_budget: float = 1000.0) -> dict:
        """Export budget allocation for next cycle."""
        allocation = self.compute_allocation(strategy="roi_proportional")
        
        # Add constraints
        constrained = {}
        for unit_id, amount in allocation.items():
            if unit_id in self.roi:
                roi = self.roi[unit_id]
                # Minimum for exploration
                min_alloc = 10.0 if roi.total_cost_usd < 10 else 0
                # Maximum cap
                max_alloc = roi.total_cost_usd * 3 if roi.total_cost_usd > 0 else 500
                constrained[roi.unit_id] = max(min_alloc, min(roi.elogw_per_usd * 1000, max_alloc))
        
        # Normalize
        total = sum(allocation.values())
        if total > 0:
            allocation = {k: v / total * 1000 for k, v in allocation.items()}
        
        return {
            "allocation": allocation,
            "strategy": "roi_proportional",
            "computed_at": datetime.now(UTC).isoformat(),
        }
    
    def save_all(self) -> None:
        """Save all state."""
        self._save_roi()


def track_llm_call(unit_id: str, unit_type: str, tokens: int, cost_usd: float, 
                    tracker: ResearchEconomicsTracker) -> None:
    """Convenience function to track LLM call."""
    tracker.record_cost(unit_id, unit_type, ResearchCost(
        llm_tokens=tokens,
        llm_cost_usd=cost_usd,
    ))


def track_compute(unit_id: str, unit_type: str, cpu_hours: float, wall_hours: float,
                   tracker: ResearchEconomicsTracker) -> None:
    """Convenience function to track compute."""
    tracker.record_cost(unit_id, unit_type, ResearchCost(
        cpu_hours=cpu_hours,
        wall_clock_hours=wall_hours,
    ))


def track_output(unit_id: str, unit_type: str, 
                  hypotheses: int = 0, unique: int = 0, cheap: int = 0,
                  heavy: int = 0, shadow: int = 0, live: int = 0,
                  elogw: float = 0.0, tracker: ResearchEconomicsTracker = None) -> None:
    """Convenience function to track output."""
    if tracker:
        tracker.record_output(unit_id, unit_type, ResearchOutput(
            hypotheses_produced=hypotheses,
            unique_hypotheses=unique,
            cheap_screen_passes=cheap,
            heavy_gate_passes=heavy,
            shadow_survivors=shadow,
            live_survivors=live,
            incremental_elogw=live * 0.001,  # Approximate
        ))


def generate_economics_report(tracker: ResearchEconomicsTracker) -> dict:
    """Generate full economics report."""
    dashboard = tracker.generate_dashboard()
    
    # Add recommendations
    recommendations = []
    
    # Check for units with zero ROI
    zero_roi = [k for k, v in tracker.roi.items() if v.elogw_per_usd == 0 and v.total_cost_usd > 10]
    if zero_roi:
        zero = [(k, tracker.roi[k].total_cost_usd) for k in zero_roi]
        recommendations.append({
            "type": "zero_roi",
            "message": f"{len(zero_roi)} units with >$10 cost but zero ROI",
            "units": zero,
            "action": "consider pausing or reducing budget",
        })
    
    # Check for high performers
    top = tracker.get_leaderboard("elogw_per_usd", 5)
    if top:
        recommendations.append({
            "type": "top_performers",
            "message": f"Top performer: {top[0]['unit_id']} with {top[0]['metric_value']:.4f} E[log W]/USD",
            "units": top[:3],
            "action": "consider increasing budget for top performers",
        })
    
    # Check for units needing exploration
    unexplored = [k for k, v in tracker.get_all_roi().items() if v.total_cost_usd < 5]
    if unexplored:
        recommendations.append({
            "type": "explore",
            "message": f"{len(unexplored)} units with <$5 cost - good for exploration",
            "units": unexplored[:10],
            "action": "allocate exploration budget",
        })
    
    return {
        "report_generated": datetime.now(UTC).isoformat(),
        "dashboard": tracker.generate_dashboard(),
        "recommendations": recommendations,
    }


def auto_reallocate_budget(tracker: ResearchEconomicsTracker, 
                            total_budget: float = 1000.0) -> dict:
    """Automatically reallocate budget based on ROI."""
    allocation = tracker.export_for_budget_allocation(total_budget)
    
    # Log reallocation
    with open(Path("data/research_economics/reallocations.jsonl"), "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "allocation": allocation["allocation"],
        }) + "\n")
    
    return allocation


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    tracker = ResearchEconomicsTracker(base)
    
    # Simulate some data
    sources = [
        ("youtube", "source", 50, 2, 10, 2, 1, 0.001),
        ("github_code", "source", 30, 5, 8, 3, 1, 0.002),
        ("china_bilibili", "source", 20, 3, 6, 2, 2, 0.005),
        ("china_zhihu", "source", 15, 2, 4, 1, 1, 0.003),
        ("github_code", "source", 10, 1, 2, 1, 0, 0.0),
    ]
    
    for unit_id, utype, cost, hyp, unique, cheap, live, elogw in sources:
        tracker.record_cost(unit_id, "source", ResearchCost(llm_cost_usd=cost, cpu_hours=cost*0.1))
        tracker.record_output(unit_id, "source", ResearchOutput(
            hypotheses_produced=hyp, unique_hypotheses=unique,
            cheap_screen_passes=cheap, live_survivors=live,
            incremental_elogw=elogw,
        ))
    
    tracker.save_all()
    
    # Generate report
    report = generate_economics_report(tracker)
    print(json.dumps(report, indent=2, default=str))