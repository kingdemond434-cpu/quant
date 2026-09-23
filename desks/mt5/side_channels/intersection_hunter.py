"""Intersection Hunter — hunts MECHANISTICALLY DIFFERENT axes intersecting.

Creates independent state axes:
FLOW, MACRO, MICROSTRUCTURE, VOLATILITY, POSITIONING, CARRY,
CROSS-ASSET, EVENT, LIQUIDITY, EXECUTION, SEASONALITY

Tests interactions between DIFFERENT axes, not correlated indicators.
Example:
  macro surprise × gold cross-asset residual × low dealer-liquidity × failed first reaction
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

INTERSECT_DIR = DATA_DIR / "intersection_hunter"
INTERSECT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AxisSignal:
    """A signal from one independent axis."""
    axis: SideChannelAxis
    symbol: str
    timestamp: datetime
    signal_type: str
    direction: int
    strength: float
    metadata: dict


@dataclass
class IntersectionSignal:
    """Signal from multiple axes intersecting."""
    timestamp: datetime
    symbol: str
    axes_involved: list[SideChannelAxis]
    axis_signals: list[str]
    combined_direction: int
    combined_strength: float
    interaction_type: str                          # "reinforcement", "divergence", "filter"
    expected_horizon: str
    context: dict
    subsequent_outcome: dict | None = None


class IntersectionHunter:
    """Hunts intersections of independent axes."""

    def __init__(self):
        self.axis_signals: dict[SideChannelAxis, list[AxisSignal]] = {axis: [] for axis in SideChannelAxis}
        self.intersections: list[IntersectionSignal] = []

    def add_axis_signal(self, signal: AxisSignal) -> None:
        self.axis_signals[signal.axis].append(signal)

    def load_from_miners(self, miner_results: dict[str, list]) -> None:
        """Load signals from all miners, mapping to axes."""
        axis_map = {
            "operational_calendar": SideChannelAxis.SEASONALITY,
            "leadership_atlas": SideChannelAxis.MICROSTRUCTURE,
            "failed_reaction": SideChannelAxis.EVENT,
            "negative_space": SideChannelAxis.MICROSTRUCTURE,
            "synthetic_residual": SideChannelAxis.RELATIVE_VALUE,
            "broker_physics": SideChannelAxis.EXECUTION,
            "swap_table": SideChannelAxis.SEASONALITY,
            "opening_atlas": SideChannelAxis.MICROSTRUCTURE,
            "forced_participant": SideChannelAxis.FLOW,
            "macro_revision": SideChannelAxis.MACRO,
            "language_change": SideChannelAxis.EVENT,
            "delayed_reaction": SideChannelAxis.MICROSTRUCTURE,
            "failure_mining": SideChannelAxis.POSITIONING,
            "ensemble_disagreement": SideChannelAxis.POSITIONING,
        }

        for miner_name, signals in miner_results.items():
            axis = axis_map.get(miner_name)
            if axis is None:
                continue
            for sig in signals:
                self.axis_signals[axis].append(AxisSignal(
                    axis=axis,
                    symbol=sig.get("symbol", "UNKNOWN"),
                    timestamp=sig.get("timestamp", datetime.now(UTC)),
                    signal_type=f"{miner_name}_{sig.get('signal_type', 'signal')}",
                    direction=sig.get("direction", 0),
                    strength=sig.get("strength", 0.5),
                    metadata=sig.get("context", {}),
                ))

    def find_intersections(self, timestamp: datetime, symbol: str,
                            window_minutes: int = 60,
                            min_axes: int = 2) -> list[IntersectionSignal]:
        """Find intersecting signals at a timestamp."""
        intersections = []

        # Collect recent signals per axis
        axis_recent = {}
        for axis in SideChannelAxis:
            recent = [s for s in self.axis_signals[axis]
                      if s.symbol == symbol
                      and s.timestamp >= timestamp - timedelta(minutes=window_minutes)
                      and s.timestamp <= timestamp]
            if recent:
                axis_recent[axis] = recent

        # Find combinations of axes with signals
        axes_with_signals = list(axis_recent.keys())
        if len(axes_with_signals) < min_axes:
            return []

        # Check pairs, triples, etc.
        from itertools import combinations
        for r in range(min_axes, min(4, len(axes_with_signals) + 1)):
            for axis_combo in combinations(axes_with_signals, r):
                # Check if directions align
                signals = [axis_recent[ax][0] for ax in axis_combo]  # Take most recent per axis
                directions = [s.direction for s in signals]
                strengths = [s.strength for s in signals]

                # Alignment check
                non_zero = [d for d in directions if d != 0]
                if not non_zero:
                    continue

                aligned = all(d == non_zero[0] for d in non_zero)
                if aligned:
                    # Reinforcement: multiple axes agree
                    combined_dir = non_zero[0]
                    combined_str = np.mean(strengths) * (1 + 0.2 * (len(axis_combo) - 2))
                    intersections.append(IntersectionSignal(
                        timestamp=timestamp,
                        symbol=symbol,
                        axes_involved=list(axis_combo),
                        axis_signals=[s.signal_type for s in signals],
                        combined_direction=combined_dir,
                        combined_strength=min(combined_str, 1.0),
                        interaction_type="reinforcement",
                        expected_horizon="1h_to_4h",
                        context={"axes": [ax.value for ax in axis_combo], "directions": directions}
                    ))
                else:
                    # Divergence: axes disagree
                    # Can be a filter signal
                    pos = [s for s in signals if s.direction > 0]
                    neg = [s for s in signals if s.direction < 0]
                    if pos and neg:
                        intersections.append(IntersectionSignal(
                            timestamp=timestamp,
                            symbol=symbol,
                            axes_involved=list(axis_combo),
                            axis_signals=[s.signal_type for s in signals],
                            combined_direction=0,
                            combined_strength=np.mean([s.strength for s in signals]),
                            interaction_type="divergence",
                            expected_horizon="session",
                            context={"axes": [ax.value for ax in axis_combo], "conflict": True}
                        ))

        self.intersections.extend(intersections)
        return intersections

    def find_filter_intersections(self, symbol: str, timestamp: datetime) -> list[IntersectionSignal]:
        """One axis filters another (e.g., macro regime filters technical signal)."""
        filters = []

        # Macro regime filters technical
        macro_signals = self.axis_signals.get(SideChannelAxis.MACRO, [])
        tech_signals = self.axis_signals.get(SideChannelAxis.MICROSTRUCTURE, [])

        recent_macro = [s for s in macro_signals if s.symbol == symbol and s.timestamp <= timestamp]
        recent_tech = [s for s in tech_signals if s.symbol == symbol and s.timestamp <= timestamp]

        if recent_macro and recent_tech:
            macro = recent_macro[-1]
            tech = recent_tech[-1]

            # Macro regime as filter
            if macro.metadata.get("regime") == "risk_off" and tech.direction > 0:
                # Risk-off macro, but technical says long -> filter
                return [IntersectionSignal(
                    timestamp=timestamp,
                    symbol=symbol,
                    axes_involved=[SideChannelAxis.MACRO, SideChannelAxis.MICROSTRUCTURE],
                    axis_signals=[macro.signal_type, tech.signal_type],
                    combined_direction=0,
                    combined_strength=0.8,
                    interaction_type="filter",
                    expected_horizon="session",
                    context={"filter": "macro_risk_off", "vetoed_signal": tech.signal_type}
                )]

        return []

    def generate_all_intersections(self) -> list[IntersectionSignal]:
        """Scan all timestamps and symbols for intersections."""
        all_intersections = []

        # Get all timestamps and symbols with signals
        all_times = set()
        all_symbols = set()
        for axis in SideChannelAxis:
            for s in self.axis_signals[axis]:
                all_times.add(s.timestamp)
                all_symbols.add(s.symbol)

        for ts in sorted(all_times):
            for sym in all_symbols:
                all_intersections.extend(self.find_intersections(ts, sym))
                all_intersections.extend(self.find_filter_intersections(sym, ts))

        self.intersections = all_intersections
        return all_intersections

    def record_outcome(self, signal: IntersectionSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_intersections: int = 8) -> list[SideChannelHypothesis]:
        """Generate hypotheses from intersections."""
        if len(self.intersections) < min_intersections:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.intersections:
            key = f"{s.interaction_type}_{'_'.join(sorted([ax.value for ax in s.axes_involved]))}_{s.symbol}"
            groups[key].append(s)

        hypotheses = []
        for key, signals in groups.items():
            if len(signals) < min_intersections:
                continue

            outcomes = [s.subsequent_outcome for s in signals if s.subsequent_outcome]
            if not outcomes:
                continue

            returns = []
            for o in outcomes:
                if "return_r" in o:
                    returns.append(o["return_r"])

            if returns and np.mean(returns) > 0:
                example = signals[0]
                h = SideChannelHypothesis(
                    id=generate_id(),
                    axis=SideChannelAxis.RELATIVE_VALUE,  # Multi-axis
                    source="intersection_hunter",
                    mechanism=f"Intersection: {example.interaction_type} of "
                              f"{', '.join([ax.value for ax in example.axes_involved])} "
                              f"on {example.symbol}. Multi-axis reinforcement/divergence. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} intersections.",
                    symbols=[example.symbol],
                    timing={
                        "interaction": example.interaction_type,
                        "axes": [ax.value for ax in example.axes_involved],
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="micro",
                    metadata={
                        "interaction": example.interaction_type,
                        "axes": [ax.value for ax in example.axes_involved],
                        "symbol": example.symbol,
                        "avg_return_r": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(INTERSECT_DIR / "axis_signals.json", "w") as f:
            json.dump({ax.value: [{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
            } for s in signals] for ax, signals in self.axis_signals.items()}, f, indent=2, default=str)

        with open(INTERSECT_DIR / "intersections.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "axes": [ax.value for ax in s.axes_involved],
                "axis_signals": s.axis_signals,
                "direction": s.combined_direction,
                "strength": s.combined_strength,
                "interaction": s.interaction_type,
                "horizon": s.expected_horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.intersections], f, indent=2, default=str)


if __name__ == "__main__":
    hunter = IntersectionHunter()

    # Test with synthetic signals
    for axis in [SideChannelAxis.MACRO, SideChannelAxis.MICROSTRUCTURE, SideChannelAxis.FLOW]:
        for i in range(10):
            hunter.add_axis_signal(AxisSignal(
                axis=axis,
                symbol="XAUUSD",
                timestamp=datetime.now(UTC) - timedelta(hours=i),
                signal_type=f"{axis.value}_signal",
                direction=np.random.choice([1, -1]),
                strength=np.random.uniform(0.5, 1.0),
                metadata={"test": True},
            ))

    intersections = hunter.generate_all_intersections()
    print(f"Found {len(intersections)} intersections")

    hyps = hunter.generate_hypotheses(min_intersections=1)
    print(f"Generated {len(hyps)} intersection hypotheses")