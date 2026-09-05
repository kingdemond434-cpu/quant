"""Failure Mining / Negative Alpha Inversion Miner.

Turns every loser into another dataset:
- What systematically distinguishes failures from successes?
- Negative strategies become: inverted alpha, veto, crowding detector, regime classifier
- Bad strategies can contain good information
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

FAIL_DIR = DATA_DIR / "failure_mining"
FAIL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StrategyOutcome:
    """One occurrence of a strategy signal."""
    strategy_id: str
    strategy_name: str
    symbol: str
    timestamp: datetime
    signal_direction: int                      # +1 long, -1 short, 0 flat
    signal_strength: float
    market_state: dict                         # regime, vol, session, cross-asset, macro
    execution_state: dict                      # spread, slippage, fill_rate
    outcome_r: float                           # R multiple result
    metadata: dict = field(default_factory=dict)


@dataclass
class FailurePattern:
    """A pattern that distinguishes failures from successes."""
    strategy_id: str
    pattern_name: str
    condition: dict                            # market state conditions
    success_rate: float
    failure_rate: float
    avg_success_r: float
    avg_failure_r: float
    sample_success: int
    sample_failure: int
    p_value: float


class FailureMiningCollector:
    """Collects strategy outcomes for failure mining."""

    def __init__(self):
        self.outcomes: list[StrategyOutcome] = []

    def add_outcome(self, outcome: StrategyOutcome) -> None:
        self.outcomes.append(outcome)

    def load_from_shadow_ledger(self, shadow_ledger: pd.DataFrame) -> None:
        """Load outcomes from shadow forward ledger."""
        # shadow_ledger columns: entry_time, symbol, side, r_multiple, etc.
        for _, row in shadow_ledger.iterrows():
            outcome = StrategyOutcome(
                strategy_id=row.get("strategy_id", "unknown"),
                strategy_name=row.get("strategy_name", "unknown"),
                symbol=row["symbol"],
                timestamp=pd.Timestamp(row["entry_time"]).to_pydatetime(),
                signal_direction=1 if row["side"] == "LONG" else -1,
                signal_strength=row.get("signal_strength", 1.0),
                market_state=row.get("market_state", {}),
                execution_state=row.get("execution_state", {}),
                outcome_r=row["r_multiple"],
            )
            self.outcomes.append(outcome)

    def load_from_live_ledger(self, live_ledger: pd.DataFrame) -> None:
        """Load outcomes from live trading ledger."""
        for _, row in live_ledger.iterrows():
            outcome = StrategyOutcome(
                strategy_id=row.get("strategy_id", "live"),
                strategy_name=row.get("sleeve", "live"),
                symbol=row["symbol"],
                timestamp=pd.Timestamp(row["entry_time"]).to_pydatetime(),
                signal_direction=1 if row["side"] == "BUY" else -1,
                signal_strength=1.0,
                market_state=row.get("market_state", {}),
                execution_state=row.get("execution_state", {}),
                outcome_r=row["r_multiple"],
            )
            self.outcomes.append(outcome)


class FailureMiningAnalyzer:
    """Analyzes failures for alpha."""

    def __init__(self):
        self.collector = FailureMiningCollector()
        self.patterns: list[FailurePattern] = []
        self.inverted_signals: list = []

    @dataclass
    class InvertedSignal:
        strategy_id: str
        symbol: str
        timestamp: datetime
        original_direction: int
        inverted_direction: int
        confidence: float
        context: dict
        subsequent_outcome: dict | None = None

    def analyze_strategy(self, strategy_id: str) -> list[FailurePattern]:
        """Analyze one strategy for failure patterns."""
        strat_outcomes = [o for o in self.collector.outcomes if o.strategy_id == strategy_id]
        if len(strat_outcomes) < 50:
            return []

        # Define market state features to test
        features = [
            "regime", "volatility", "session", "trend", "spread",
            "tick_rate", "cross_asset_beta", "macro_state",
            "hour", "day_of_week", "month",
        ]

        patterns = []

        for feat in features:
            # Group by feature value
            grouped = {}
            for o in strat_outcomes:
                val = o.market_state.get(feat) or o.execution_state.get(feat)
                if val is None:
                    continue
                key = str(val)
                if key not in grouped:
                    grouped[key] = {"success": [], "failure": []}
                if o.outcome_r > 0:
                    grouped[key]["success"].append(o.outcome_r)
                else:
                    grouped[key]["failure"].append(o.outcome_r)

            # Test each value
            for key, groups in grouped.items():
                s = groups["success"]
                f = groups["failure"]
                if len(s) < 10 or len(f) < 10:
                    continue

                avg_s = np.mean(s)
                avg_f = np.mean(f)
                sr = len(s) / (len(s) + len(f))

                # Significant difference?
                from scipy import stats
                if len(s) > 1 and len(f) > 1:
                    t_stat, p_val = stats.ttest_ind(s, f, equal_var=False)
                else:
                    p_val = 1.0

                if p_val < 0.05 and avg_s > 0 and avg_f < 0:
                    patterns.append(FailurePattern(
                        strategy_id=strategy_id,
                        pattern_name=f"{feat}={key}",
                        condition={feat: key},
                        success_rate=sr,
                        failure_rate=1 - sr,
                        avg_success_r=avg_s,
                        avg_failure_r=avg_f,
                        sample_success=len(s),
                        sample_failure=len(f),
                        p_value=p_val,
                    ))

        self.patterns.extend(patterns)
        return patterns

    def generate_inverted_signals(self, strategy_id: str, min_edge: float = 0.1) -> list:
        """Generate inverted signals from consistently negative strategies."""
        strat_outcomes = [o for o in self.collector.outcomes if o.strategy_id == strategy_id]
        if len(strat_outcomes) < 100:
            return []

        avg_r = np.mean([o.outcome_r for o in strat_outcomes])
        if avg_r >= -min_edge:
            return []  # Not consistently negative enough

        # Strategy is consistently negative -> invert it
        inverted = []
        for o in strat_outcomes[-50:]:  # Recent occurrences
            inverted.append(self.InvertedSignal(
                strategy_id=strategy_id,
                symbol=o.symbol,
                timestamp=o.timestamp,
                original_direction=o.signal_direction,
                inverted_direction=-o.signal_direction,
                confidence=min(abs(avg_r) * 2, 0.8),
                context={
                    "strategy_avg_r": avg_r,
                    "market_state": o.market_state,
                    "execution_state": o.execution_state,
                }
            ))

        self.inverted_signals.extend(inverted)
        return inverted

    def generate_veto_signals(self, strategy_id: str, failure_threshold: float = -0.2) -> list:
        """Generate veto signals: when to NOT trade based on failure patterns."""
        veto_signals = []

        for pattern in self.patterns:
            if pattern.strategy_id != strategy_id:
                continue
            if pattern.avg_failure_r < failure_threshold and pattern.failure_rate > 0.6:
                # This condition predicts failure -> veto
                veto_signals.append({
                    "strategy_id": strategy_id,
                    "veto_condition": pattern.condition,
                    "failure_rate": pattern.failure_rate,
                    "avg_failure_r": pattern.avg_failure_r,
                    "confidence": pattern.failure_rate,
                })

        return veto_signals

    def generate_crowding_detector(self, strategy_id: str) -> dict | None:
        """Use strategy failures as crowding detector."""
        strat_outcomes = [o for o in self.collector.outcomes if o.strategy_id == strategy_id]
        if len(strat_outcomes) < 30:
            return None

        # Recent failure rate spike = crowding
        recent = strat_outcomes[-20:]
        failure_rate = sum(1 for o in recent if o.outcome_r < 0) / len(recent)

        if failure_rate > 0.65:
            return {
                "type": "crowding_detector",
                "strategy_id": strategy_id,
                "current_failure_rate": failure_rate,
                "signal": "reduce_size" if failure_rate > 0.65 else "veto" if failure_rate > 0.8 else "normal",
                "confidence": min(failure_rate * 1.5, 1.0),
            }
        return None

    def generate_regime_classifier(self, strategy_id: str) -> dict | None:
        """Use strategy performance as regime classifier."""
        strat_outcomes = [o for o in self.collector.outcomes if o.strategy_id == strategy_id]
        if len(strat_outcomes) < 50:
            return None

        # Group by regime
        regime_perf = {}
        for o in strat_outcomes:
            regime = o.market_state.get("regime", "unknown")
            if regime not in regime_perf:
                regime_perf[regime] = []
            regime_perf[regime].append(o.outcome_r)

        # Find regimes where strategy works/fails
        good_regimes = []
        bad_regimes = []
        for regime, outcomes in regime_perf.items():
            if len(outcomes) < 10:
                continue
            avg = np.mean(outcomes)
            if avg > 0.05:
                good_regimes.append(regime)
            elif avg < -0.05:
                bad_regimes.append(regime)

        return {
            "type": "regime_classifier",
            "strategy_id": strategy_id,
            "good_regimes": good_regimes,
            "bad_regimes": bad_regimes,
        }

    def record_outcome(self, signal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_patterns: int = 3) -> list[SideChannelHypothesis]:
        """Generate hypotheses from failure mining."""
        if len(self.patterns) < min_patterns:
            return []

        hypotheses = []

        # Pattern-based hypotheses
        for pattern in self.patterns:
            if pattern.p_value > 0.05:
                continue

            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.POSITIONING,
                source="failure_mining",
                mechanism=f"Failure pattern: {pattern.pattern_name} for {pattern.strategy_id}. "
                          f"Success rate {pattern.success_rate:.1%} (avg +{pattern.avg_success_r:.3f}R) "
                          f"vs failure rate {pattern.failure_rate:.1%} (avg {pattern.avg_failure_r:.3f}R). "
                          f"Trade only when condition met, invert otherwise.",
                symbols=[],  # Strategy-specific
                timing={
                    "strategy_id": pattern.strategy_id,
                    "condition": pattern.condition,
                },
                falsifier=f"Pattern p-value rises above 0.1 over 50+ occurrences",
                expected_horizon="per_trade",
                capacity_estimate="small",
                metadata={
                    "strategy_id": pattern.strategy_id,
                    "pattern": pattern.pattern_name,
                    "p_value": pattern.p_value,
                    "success_rate": pattern.success_rate,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        # Inverted strategy hypotheses
        for signal in self.inverted_signals[-10:]:
            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.POSITIONING,
                source="failure_mining",
                mechanism=f"Inverted alpha: {signal.strategy_id} consistently loses "
                          f"(avg {signal.context.get('strategy_avg_r', 0):.3f}R). "
                          f"Inverting signals produces positive expectancy.",
                symbols=[signal.symbol],
                timing={
                    "strategy_id": signal.strategy_id,
                    "inversion": True,
                },
                falsifier=f"Original strategy becomes profitable (avg R > 0) over 100+ trades",
                expected_horizon="per_trade",
                capacity_estimate="small",
                metadata={
                    "strategy_id": signal.strategy_id,
                    "original_avg_r": signal.context.get("strategy_avg_r"),
                    "inversion": True,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(FAIL_DIR / "outcomes.json", "w") as f:
            json.dump([{
                "strategy_id": o.strategy_id,
                "strategy_name": o.strategy_name,
                "symbol": o.symbol,
                "timestamp": o.timestamp.isoformat(),
                "direction": o.signal_direction,
                "strength": o.signal_strength,
                "market_state": o.market_state,
                "execution_state": o.execution_state,
                "outcome_r": o.outcome_r,
            } for o in self.collector.outcomes], f, indent=2, default=str)

        with open(FAIL_DIR / "patterns.json", "w") as f:
            json.dump([{
                "strategy_id": p.strategy_id,
                "pattern_name": p.pattern_name,
                "condition": p.condition,
                "success_rate": p.success_rate,
                "failure_rate": p.failure_rate,
                "avg_success_r": p.avg_success_r,
                "avg_failure_r": p.avg_failure_r,
                "sample_success": p.sample_success,
                "sample_failure": p.sample_failure,
                "p_value": p.p_value,
            } for p in self.patterns], f, indent=2, default=str)

        with open(FAIL_DIR / "inverted_signals.json", "w") as f:
            json.dump([{
                "strategy_id": s.strategy_id,
                "symbol": s.symbol,
                "timestamp": s.timestamp.isoformat(),
                "original_direction": s.original_direction,
                "inverted_direction": s.inverted_direction,
                "confidence": s.confidence,
                "context": s.context,
            } for s in self.inverted_signals], f, indent=2, default=str)


if __name__ == "__main__":
    collector = FailureMiningCollector()

    # Synthetic test data
    for i in range(200):
        collector.add_outcome(StrategyOutcome(
            strategy_id="test_strat",
            strategy_name="test",
            symbol="XAUUSD",
            timestamp=datetime.now(UTC) - timedelta(days=i),
            signal_direction=1 if i % 2 == 0 else -1,
            signal_strength=1.0,
            market_state={"regime": "trend" if i % 3 == 0 else "range", "volatility": "high" if i % 4 == 0 else "low"},
            execution_state={},
            outcome_r=np.random.randn() * 1.5 - 0.3,  # Slightly negative
        ))

    analyzer = FailureMiningAnalyzer()
    analyzer.collector = collector
    patterns = analyzer.analyze_strategy("test_strat")
    print(f"Found {len(patterns)} failure patterns")

    inverted = analyzer.generate_inverted_signals("test_strat", min_edge=0.1)
    print(f"Generated {len(inverted)} inverted signals")

    hyps = analyzer.generate_hypotheses(min_patterns=1)
    print(f"Generated {len(hyps)} failure mining hypotheses")