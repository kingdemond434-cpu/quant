"""Ensemble Disagreement Miner — mines disagreement between strategies.

When models disagree, the entropy itself predicts:
- volatility
- chop
- breakout probability
- false-break probability

Uses H = -Σ p_i log(p_i) or simpler disagreement scores.
Not necessarily as direction, but as: sizing, strategy selection, vol forecast, execution mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

DISAGREE_DIR = DATA_DIR / "ensemble_disagreement"
DISAGREE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelPrediction:
    """One model's prediction for a symbol/time."""
    model_id: str
    symbol: str
    timestamp: datetime
    direction: int                             # +1 long, -1 short, 0 neutral
    confidence: float                          # 0-1
    expected_horizon: str
    metadata: dict = field(default_factory=dict)


@dataclass
class EnsembleState:
    """Ensemble state at one point in time."""
    timestamp: datetime
    symbol: str
    predictions: list[ModelPrediction]
    entropy: float                             # disagreement measure
    majority_direction: int                    # weighted majority
    agreement_ratio: float                     # fraction agreeing with majority
    minority_count: int
    context: dict = field(default_factory=dict)


@dataclass
class DisagreementSignal:
    """Signal from ensemble disagreement."""
    timestamp: datetime
    symbol: str
    signal_type: str                           # "high_entropy", "split_vote", "polarized", "consensus"
    direction: int                             # trade direction if any
    strength: float
    expected_horizon: str
    context: dict
    subsequent_outcome: dict | None = None


class EnsembleCollector:
    """Collects predictions from multiple models."""

    def __init__(self):
        self.predictions: list[ModelPrediction] = []

    def add_prediction(self, pred: ModelPrediction) -> None:
        self.predictions.append(pred)

    def load_from_shadow(self, shadow_state: dict) -> None:
        """Load predictions from shadow state."""
        # shadow_state has per-sleeve predictions
        pass

    def load_from_promoter(self, promoter_signals: list[dict]) -> None:
        """Load from promoter candidates."""
        for s in promoter_signals:
            pred = ModelPrediction(
                model_id=s.get("model", "promoter"),
                symbol=s.get("symbol", "UNKNOWN"),
                timestamp=datetime.fromisoformat(s.get("timestamp", datetime.now(UTC).isoformat())),
                direction=s.get("direction", 0),
                confidence=s.get("confidence", 0.5),
                expected_horizon=s.get("horizon", "1d"),
            )
            self.predictions.append(pred)


class EnsembleDisagreementAnalyzer:
    """Analyzes ensemble disagreement for alpha."""

    def __init__(self):
        self.collector = EnsembleCollector()
        self.ensemble_states: list[EnsembleState] = []
        self.signals: list[DisagreementSignal] = []

    def compute_ensemble_state(self, timestamp: datetime, symbol: str,
                                window_minutes: int = 60) -> EnsembleState | None:
        """Compute ensemble state for a symbol at a timestamp."""
        # Get predictions within window
        window_start = timestamp - timedelta(minutes=window_minutes)
        preds = [p for p in self.collector.predictions
                 if p.symbol == symbol and window_start <= p.timestamp <= timestamp]

        if len(preds) < 3:
            return None

        # Compute weighted directions
        directions = []
        weights = []
        for p in preds:
            directions.append(p.direction)
            weights.append(p.confidence)

        # Weighted majority
        weighted_votes = {1: 0, -1: 0, 0: 0}
        for d, w in zip(directions, weights):
            weighted_votes[d] += w

        majority_dir = max(weighted_votes, key=weighted_votes.get)
        total_weight = sum(weights)
        agreement = weighted_votes[majority_dir] / total_weight if total_weight > 0 else 0

        # Entropy
        probs = [v / total_weight for v in weighted_votes.values() if v > 0]
        entropy = -sum(p * np.log(p) for p in probs) if probs else 0

        # Minority count
        minority = sum(1 for d in directions if d != majority_dir)

        state = EnsembleState(
            timestamp=timestamp,
            symbol=symbol,
            predictions=preds,
            entropy=entropy,
            majority_direction=majority_dir,
            agreement_ratio=agreement,
            minority_count=minority,
            context={
                "n_models": len(preds),
                "weighted_votes": weighted_votes,
            }
        )
        self.ensemble_states.append(state)
        return state

    def detect_high_entropy(self, state: EnsembleState, entropy_threshold: float = 1.0) -> list[DisagreementSignal]:
        """High entropy = maximum disagreement = potential vol/vol expansion."""
        signals = []
        if state.entropy > entropy_threshold:
            signals.append(DisagreementSignal(
                timestamp=state.timestamp,
                symbol=state.symbol,
                signal_type="high_entropy",
                direction=0,  # No directional bias
                strength=min(state.entropy / 2, 1.0),
                expected_horizon="1h_to_4h",
                context={
                    "entropy": state.entropy,
                    "agreement": state.agreement_ratio,
                    "minority": state.minority_count,
                    "n_models": state.context["n_models"],
                }
            ))
        return signals

    def detect_split_vote(self, state: EnsembleState, split_threshold: float = 0.4) -> list[DisagreementSignal]:
        """Near 50/50 split = chop/range likely."""
        signals = []
        if state.majority_direction == 0:
            return signals

        # Check if minority is substantial
        minority_weight = state.context["weighted_votes"].get(-state.majority_direction, 0)
        total = sum(state.context["weighted_votes"].values())
        minority_ratio = minority_weight / total if total > 0 else 0

        if minority_ratio > split_threshold:
            signals.append(DisagreementSignal(
                timestamp=state.timestamp,
                symbol=state.symbol,
                signal_type="split_vote",
                direction=0,
                strength=minority_ratio,
                expected_horizon="session",
                context={
                    "majority": state.majority_direction,
                    "minority_ratio": minority_ratio,
                    "entropy": state.entropy,
                }
            ))
        return signals

    def detect_polarized(self, state: EnsembleState, polar_threshold: float = 0.8) -> list[DisagreementSignal]:
        """Strong consensus but with one strong dissenter = potential trap."""
        signals = []
        if state.agreement_ratio > polar_threshold and state.minority_count >= 1:
            # Find the dissenter
            dissenter = None
            for p in state.predictions:
                if p.direction != state.majority_direction:
                    dissenter = p
                    break

            if dissenter and dissenter.confidence > 0.7:
                signals.append(DisagreementSignal(
                    timestamp=state.timestamp,
                    symbol=state.symbol,
                    signal_type="polarized",
                    direction=-state.majority_direction,  # Fade the consensus
                    strength=0.7,
                    expected_horizon="1h_to_4h",
                    context={
                        "consensus": state.majority_direction,
                        "dissenter": dissenter.model_id,
                        "dissenter_confidence": dissenter.confidence,
                    }
                ))
        return signals

    def detect_consensus_strength(self, state: EnsembleState, consensus_threshold: float = 0.9) -> list[DisagreementSignal]:
        """Very high agreement = strong trend, but watch for crowding."""
        signals = []
        if state.agreement_ratio > consensus_threshold and state.entropy < 0.3:
            signals.append(DisagreementSignal(
                timestamp=state.timestamp,
                symbol=state.symbol,
                signal_type="strong_consensus",
                direction=state.majority_direction,
                strength=state.agreement_ratio,
                expected_horizon="4h_to_1d",
                context={
                    "entropy": state.entropy,
                    "agreement": state.agreement_ratio,
                }
            ))
        return signals

    def generate_all_signals(self) -> list[DisagreementSignal]:
        """Generate signals from all ensemble states."""
        all_signals = []
        for state in self.ensemble_states:
            all_signals.extend(self.detect_high_entropy(state))
            all_signals.extend(self.detect_split_vote(state))
            all_signals.extend(self.detect_polarized(state))
            all_signals.extend(self.detect_consensus_strength(state))

        self.signals = all_signals
        return all_signals

    def record_outcome(self, signal: DisagreementSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 10) -> list[SideChannelHypothesis]:
        """Generate hypotheses from disagreement signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.signal_type}_{s.symbol}"
            groups[key].append(s)

        hypotheses = []
        for key, signals in groups.items():
            if len(signals) < min_signals:
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
                    axis=SideChannelAxis.POSITIONING,
                    source="ensemble_disagreement",
                    mechanism=f"Ensemble disagreement signal: {example.signal_type} on {example.symbol}. "
                              f"Disagreement entropy predicts {example.signal_type.replace('_', ' ')}. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} occurrences.",
                    symbols=[example.symbol],
                    timing={
                        "signal_type": example.signal_type,
                        "entropy": example.context.get("entropy", 0),
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="micro",
                    metadata={
                        "signal_type": example.signal_type,
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
        with open(DISAGREE_DIR / "ensemble_states.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "entropy": s.entropy,
                "majority": s.majority_direction,
                "agreement": s.agreement_ratio,
                "minority_count": s.minority_count,
            } for s in self.ensemble_states], f, indent=2, default=str)

        with open(DISAGREE_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    collector = EnsembleCollector()

    # Synthetic test
    for i in range(100):
        timestamp = datetime.now(UTC) - timedelta(minutes=i*10)
        for model in ["trend", "mean_revert", "macro", "options", "cross_asset"]:
            collector.add_prediction(ModelPrediction(
                model_id=model,
                symbol="XAUUSD",
                timestamp=timestamp,
                direction=np.random.choice([1, -1, 0], p=[0.4, 0.4, 0.2]),
                confidence=np.random.uniform(0.3, 0.9),
                expected_horizon="1d",
            ))

    analyzer = EnsembleDisagreementAnalyzer()
    analyzer.collector = collector

    # Compute states
    for i in range(10):
        ts = datetime.now(UTC) - timedelta(hours=i)
        analyzer.compute_ensemble_state(ts, "XAUUSD")

    signals = analyzer.generate_all_signals()
    print(f"Generated {len(signals)} disagreement signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} disagreement hypotheses")