"""Failed Reaction Miner — hunts when markets refuse to react as expected.

The failure of an expected response itself becomes the signal.
Builds: Expected reaction → Failed reaction → Subsequent outcome factory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

FAIL_DIR = DATA_DIR / "failed_reactions"
FAIL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExpectedReaction:
    """What the market SHOULD do based on historical patterns."""
    event_type: str
    event_details: dict                        # surprise, direction, magnitude
    expected_moves: dict[str, float]           # symbol -> expected direction (+1/-1) * magnitude
    confidence: float                          # historical reliability
    regime: str                                # market regime when pattern holds


@dataclass
class ActualReaction:
    """What the market ACTUALLY did."""
    event_id: str
    event_type: str
    actual_moves: dict[str, float]             # symbol -> actual move (R or pips)
    timestamp: datetime
    window: str                                # "1m", "5m", "15m", "1h", "4h"


@dataclass
class FailedReaction:
    """A market that failed to react as expected."""
    event_id: str
    event_type: str
    regime: str
    expected: ExpectedReaction
    actual: ActualReaction
    disagreement_score: float                  # 0-1, how much actual deviated from expected
    failed_symbols: list[str]                  # symbols that failed
    failed_directions: dict[str, str]          # symbol -> "opposite" | "flat" | "weak"
    subsequent_outcome: dict | None = None     # what happened next (1h, 4h, 1d, 1w)


class FailedReactionMiner:
    """Mines failed reactions from event data."""

    def __init__(self):
        self.failures: list[FailedReaction] = []
        self.expected_patterns: dict[str, ExpectedReaction] = {}

    def load_expected_patterns(self, path: Path | None = None) -> None:
        """Load expected reaction patterns from historical analysis."""
        if path is None:
            path = FAIL_DIR / "expected_patterns.json"
        if not path.exists():
            self._build_default_patterns()
            return
        import json
        with open(path, "r") as f:
            data = json.load(f)
        for k, v in data.items():
            v["expected_moves"] = {sym: float(m) for sym, m in v["expected_moves"].items()}
            self.expected_patterns[k] = ExpectedReaction(**v)

    def _build_default_patterns(self) -> None:
        """Build default expected reaction patterns from literature."""
        self.expected_patterns = {
            "US_CPI_HOT": ExpectedReaction(
                event_type="US_CPI",
                event_details={"surprise": "positive", "threshold": 0.1},
                expected_moves={
                    "US10Y": 1.0, "US2Y": 1.0, "DXY": 1.0,
                    "XAUUSD": -1.0, "EURUSD": -1.0, "GBPUSD": -1.0,
                    "USDJPY": 1.0, "US500": -0.5,
                },
                confidence=0.75,
                regime="normal",
            ),
            "US_CPI_COLD": ExpectedReaction(
                event_type="US_CPI",
                event_details={"surprise": "negative", "threshold": -0.1},
                expected_moves={
                    "US10Y": -1.0, "US2Y": -1.0, "DXY": -1.0,
                    "XAUUSD": 1.0, "EURUSD": 1.0, "GBPUSD": 1.0,
                    "USDJPY": -1.0, "US500": 0.5,
                },
                confidence=0.75,
                regime="normal",
            ),
            "FOMC_HAWKISH": ExpectedReaction(
                event_type="FOMC",
                event_details={"surprise": "hawkish"},
                expected_moves={
                    "US2Y": 1.0, "US10Y": 1.0, "DXY": 1.0,
                    "XAUUSD": -1.0, "EURUSD": -1.0, "US500": -1.0,
                },
                confidence=0.8,
                regime="normal",
            ),
            "FOMC_DOVISH": ExpectedReaction(
                event_type="FOMC",
                event_details={"surprise": "dovish"},
                expected_moves={
                    "US2Y": -1.0, "US10Y": -1.0, "DXY": -1.0,
                    "XAUUSD": 1.0, "EURUSD": 1.0, "US500": 1.0,
                },
                confidence=0.8,
                regime="normal",
            ),
            "NFP_STRONG": ExpectedReaction(
                event_type="NFP",
                event_details={"surprise": "positive", "threshold": 50},
                expected_moves={
                    "US2Y": 1.0, "DXY": 1.0, "USDJPY": 1.0,
                    "XAUUSD": -1.0, "EURUSD": -1.0, "US500": 0.5,
                },
                confidence=0.7,
                regime="normal",
            ),
            "TRUMP_TARIFF": ExpectedReaction(
                event_type="TRUMP_POST",
                event_details={"domain": "tariff", "escalation": True},
                expected_moves={
                    "XAUUSD": 1.0, "USOIL": -1.0, "DXY": 1.0,
                    "USDCNH": 1.0, "US500": -1.0,
                },
                confidence=0.6,
                regime="risk_off",
            ),
            "TRUMP_FED_CRITICISM": ExpectedReaction(
                event_type="TRUMP_POST",
                event_details={"domain": "fed_criticism"},
                expected_moves={
                    "XAUUSD": 1.0, "DXY": -1.0, "US10Y": -1.0,
                    "US500": 1.0,
                },
                confidence=0.55,
                regime="policy_uncertainty",
            ),
        }

    def analyze_event(self, event_id: str, event_type: str, surprise_details: dict,
                      actual_moves: dict[str, float], window: str = "15m",
                      regime: str = "normal") -> FailedReaction | None:
        """Analyze an event for failed reactions."""
        # Find matching expected pattern
        expected_key = self._match_pattern(event_type, surprise_details)
        if not expected_key:
            return None

        expected = self.expected_patterns[expected_key]

        # Compare actual vs expected
        failed_symbols = []
        failed_directions = {}
        disagreements = []

        for symbol, expected_dir in expected.expected_moves.items():
            actual = actual_moves.get(symbol, 0.0)
            if actual == 0:
                continue

            actual_dir = 1 if actual > 0 else -1
            expected_dir = 1 if expected_dir > 0 else -1

            if actual_dir != expected_dir:
                # Opposite direction = hard failure
                failed_symbols.append(symbol)
                failed_directions[symbol] = "opposite"
                disagreements.append(1.0)
            elif abs(actual) < abs(expected_dir) * 0.3:
                # Weak reaction = soft failure
                failed_symbols.append(symbol)
                failed_directions[symbol] = "weak"
                disagreements.append(0.5)
            else:
                # Direction matches
                disagreements.append(0.0)

        if not failed_symbols:
            return None

        disagreement_score = np.mean(disagreements)

        failure = FailedReaction(
            event_id=event_id,
            event_type=event_type,
            regime=regime,
            expected=expected,
            actual=ActualReaction(
                event_id=event_id,
                event_type=event_type,
                actual_moves=actual_moves,
                timestamp=datetime.now(UTC),
                window=window,
            ),
            disagreement_score=disagreement_score,
            failed_symbols=failed_symbols,
            failed_directions=failed_directions,
        )
        self.failures.append(failure)
        return failure

    def _match_pattern(self, event_type: str, surprise: dict) -> str | None:
        """Match event to expected pattern key."""
        # Simple matching logic
        if event_type == "US_CPI":
            if surprise.get("surprise", 0) > 0.1:
                return "US_CPI_HOT"
            elif surprise.get("surprise", 0) < -0.1:
                return "US_CPI_COLD"
        elif event_type == "FOMC":
            if surprise.get("surprise") == "hawkish":
                return "FOMC_HAWKISH"
            elif surprise.get("surprise") == "dovish":
                return "FOMC_DOVISH"
        elif event_type == "NFP":
            if surprise.get("surprise", 0) > 50:
                return "NFP_STRONG"
        elif event_type == "TRUMP_POST":
            if surprise.get("domain") == "tariff" and surprise.get("escalation"):
                return "TRUMP_TARIFF"
            elif surprise.get("domain") == "fed_criticism":
                return "TRUMP_FED_CRITICISM"
        return None

    def record_subsequent_outcome(self, event_id: str, outcomes: dict) -> None:
        """Record what happened after the failed reaction."""
        for f in self.failures:
            if f.event_id == event_id:
                f.subsequent_outcome = outcomes
                break

    def generate_hypotheses(self, min_failures: int = 5) -> list[SideChannelHypothesis]:
        """Generate hypotheses from failed reaction patterns."""
        if len(self.failures) < min_failures:
            return []

        # Group by failure pattern
        patterns: dict[str, list[FailedReaction]] = {}
        for f in self.failures:
            key = f"{f.event_type}_{'_'.join(sorted(f.failed_symbols))}"
            if key not in patterns:
                patterns[key] = []
            patterns[key].append(f)

        hypotheses = []
        for pattern_key, failures in patterns.items():
            if len(failures) < min_failures:
                continue

            # Analyze subsequent outcomes
            outcomes = [f.subsequent_outcome for f in failures if f.subsequent_outcome]
            if not outcomes:
                continue

            # Check if failed reaction predicts reversal/continuation
            first_symbol = failures[0].failed_symbols[0]
            first_failed_dir = failures[0].failed_directions[first_symbol]

            # Simple: if market failed to fall, does it rally later?
            reversal_signals = 0
            for o in outcomes:
                move = o.get(first_symbol, 0)
                if first_failed_dir == "opposite":
                    # Expected down, stayed flat/up -> check if later falls
                    if move < 0:
                        reversal_signals += 1
                elif first_failed_dir == "weak":
                    # Expected strong, was weak -> check direction
                    expected_dir = 1 if failures[0].expected.expected_moves.get(first_symbol, 0) > 0 else -1
                    if move * expected_dir > 0:
                        reversal_signals += 1

            reversal_rate = reversal_signals / len(outcomes) if outcomes else 0

            if reversal_rate > 0.6:  # 60%+ reversal rate
                h = SideChannelHypothesis(
                    id=generate_id(),
                    axis=SideChannelAxis.EVENT,
                    source="failed_reaction_miner",
                    mechanism=f"Failed reaction pattern: {pattern_key}. "
                              f"When {first_symbol} fails to react as expected to {failures[0].event_type} "
                              f"({first_failed_dir}), it subsequently reverses {reversal_rate:.0%} of the time.",
                    symbols=[first_symbol] + [s for f in failures for s in f.failed_symbols],
                    timing={
                        "event_type": failures[0].event_type,
                        "trigger": "failed_reaction",
                        "window": failures[0].actual.window,
                        "regime": failures[0].regime,
                    },
                    falsifier=f"Reversal rate drops below 50% over 20+ occurrences",
                    expected_horizon="15m_to_4h",
                    capacity_estimate="small",
                    metadata={
                        "pattern": pattern_key,
                        "failed_symbol": first_symbol,
                        "reversal_rate": reversal_rate,
                        "sample_size": len(failures),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        """Save failures to disk."""
        import json
        data = {
            "failures": [{
                "event_id": f.event_id,
                "event_type": f.event_type,
                "regime": f.regime,
                "expected_key": f"{f.event_type}_{f.expected.event_details}",
                "actual_moves": f.actual.actual_moves,
                "disagreement_score": f.disagreement_score,
                "failed_symbols": f.failed_symbols,
                "failed_directions": f.failed_directions,
                "subsequent_outcome": f.subsequent_outcome,
            } for f in self.failures],
            "saved_at": datetime.now(UTC).isoformat(),
        }
        with open(FAIL_DIR / "failed_reactions.json", "w") as f:
            json.dump(data, f, indent=2)


def build_failed_reaction_dataset(events_data: list[dict]) -> pd.DataFrame:
    """Build a DataFrame of failed reactions for analysis."""
    rows = []
    miner = FailedReactionMiner()
    miner.load_expected_patterns()

    for ev in events_data:
        failure = miner.analyze_event(
            event_id=ev["event_id"],
            event_type=ev["event_type"],
            surprise_details=ev.get("surprise", {}),
            actual_moves=ev.get("actual_moves", {}),
            window=ev.get("window", "15m"),
            regime=ev.get("regime", "normal"),
        )
        if failure:
            rows.append({
                "event_id": failure.event_id,
                "event_type": failure.event_type,
                "regime": failure.regime,
                "disagreement_score": failure.disagreement_score,
                "failed_symbols": ",".join(failure.failed_symbols),
                "failed_directions": str(failure.failed_directions),
                "subsequent_outcome": str(failure.subsequent_outcome),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    miner = FailedReactionMiner()
    miner.load_expected_patterns()

    # Example: test with synthetic data
    test_events = [
        {
            "event_id": "CPI_2026_08_13",
            "event_type": "US_CPI",
            "surprise": {"surprise": 0.2},
            "actual_moves": {"XAUUSD": 0.1, "DXY": -0.05, "EURUSD": 0.08},  # Gold UP on hot CPI = FAILURE
            "window": "15m",
            "regime": "normal",
        },
        {
            "event_id": "FOMC_2026_07_31",
            "event_type": "FOMC",
            "surprise": {"surprise": "hawkish"},
            "actual_moves": {"XAUUSD": 0.05, "US500": 0.02},  # Gold/Equities UP on hawkish = FAILURE
            "window": "5m",
            "regime": "normal",
        },
    ]

    for ev in test_events:
        f = miner.analyze_event(**ev)
        if f:
            print(f"FAILURE: {f.event_id} - {f.failed_symbols} ({f.failed_directions})")

    hyps = miner.generate_hypotheses(min_failures=1)
    print(f"Generated {len(hyps)} failed reaction hypotheses")

    miner.save()