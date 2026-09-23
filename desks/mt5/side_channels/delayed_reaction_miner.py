"""Delayed Reaction / Information Half-Life Miner.

Standard research asks: What happened after event X?
Instead test RESPONSE CURVES across time horizons:

For every event:
  0-1m, 1-5m, 5-15m, 15-60m, 1-4h, next session, next day

Some information may be:
- instantly incorporated
- initially misinterpreted
- partially incorporated
- reversed
- slowly diffused

Discovers which event classes have which propagation curves.
Builds an INFORMATION HALF-LIFE MODEL.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

DELAY_DIR = DATA_DIR / "delayed_reactions"
DELAY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EventResponseCurve:
    """Response curve for one event across time horizons."""
    event_id: str
    event_type: str
    symbol: str
    horizons: dict[str, float]                  # horizon -> cumulative return
    half_life_minutes: float | None = None      # time for 50% of total move
    peak_horizon: str | None = None             # horizon of max move
    final_direction: int | None = None          # direction at longest horizon
    mispriced_horizons: list[str] = field(default_factory=list)


@dataclass
class DelayedSignal:
    """Signal from delayed reaction pattern."""
    event_id: str
    event_type: str
    symbol: str
    signal_type: str                            # "slow_diffusion", "reversal", "misinterpretation", "partial_incorp"
    direction: int
    strength: float
    entry_horizon: str                          # when to enter
    exit_horizon: str                           # when to exit
    context: dict
    subsequent_outcome: dict | None = None


# Standard horizons to test
HORIZONS = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
    "2d": timedelta(days=2),
    "5d": timedelta(days=5),
}


class DelayedReactionCollector:
    """Collects event response curves."""

    def __init__(self):
        self.curves: list[EventResponseCurve] = []

    def build_response_curve(self, event_id: str, event_type: str, symbol: str,
                              event_time: datetime, price_data: pd.DataFrame) -> EventResponseCurve | None:
        """Build response curve for one event-symbol pair."""
        horizons = {}

        for name, delta in HORIZONS.items():
            target_time = event_time + delta
            # Find closest price
            mask = price_data.index >= target_time
            if not mask.any():
                horizons[name] = np.nan
                continue
            idx = mask.argmax()
            if idx >= len(price_data):
                horizons[name] = np.nan
                continue

            entry_price = price_data["open"].iloc[0]  # event time open
            target_price = price_data["close"].iloc[idx]
            ret = (target_price - entry_price) / entry_price
            horizons[name] = ret

        # Remove NaN
        valid = {k: v for k, v in horizons.items() if not np.isnan(v)}
        if len(valid) < 3:
            return None

        # Compute half-life
        total_move = list(valid.values())[-1]
        half_life = None
        for name, val in valid.items():
            if abs(val) >= abs(total_move) * 0.5:
                half_life = HORIZONS[name].total_seconds() / 60
                break

        # Peak horizon
        peak_horizon = max(valid, key=lambda k: abs(valid[k]))

        # Final direction
        final_dir = 1 if total_move > 0 else (-1 if total_move < 0 else 0)

        # Mispriced horizons: where direction differs from final
        mispriced = []
        for name, val in valid.items():
            dir_at_h = 1 if val > 0 else (-1 if val < 0 else 0)
            if dir_at_h != 0 and dir_at_h != final_dir:
                mispriced.append(name)

        curve = EventResponseCurve(
            event_id=event_id,
            event_type=event_type,
            symbol=symbol,
            horizons=valid,
            half_life_minutes=half_life,
            peak_horizon=peak_horizon,
            final_direction=final_dir,
            mispriced_horizons=mispriced,
        )
        self.curves.append(curve)
        return curve

    def build_curves_for_event(self, event_id: str, event_type: str, event_time: datetime,
                                symbols: list[str], price_data: dict[str, pd.DataFrame]) -> list[EventResponseCurve]:
        """Build curves for all symbols for one event."""
        curves = []
        for sym in symbols:
            if sym in price_data:
                curve = self.build_response_curve(event_id, event_type, sym, event_time, price_data[sym])
                if curve:
                    curves.append(curve)
        return curves


class DelayedReactionAnalyzer:
    """Analyzes delayed reactions for alpha."""

    def __init__(self):
        self.collector = DelayedReactionCollector()
        self.signals: list = []

    @dataclass
    class DelayedSignal:
        event_id: str
        event_type: str
        symbol: str
        signal_type: str
        direction: int
        strength: float
        entry_horizon: str
        exit_horizon: str
        context: dict
        subsequent_outcome: dict | None = None

    def detect_slow_diffusion(self, curve: EventResponseCurve) -> list:
        """Information diffuses slowly: small early move, large later move."""
        signals = []
        if curve.final_direction == 0:
            return signals

        early = curve.horizons.get("5m", 0)
        late = curve.horizons.get("4h", 0)

        if abs(late) > abs(early) * 3 and abs(late) > 0:
            # Slow diffusion: late move 3x early
            signals.append(self.DelayedSignal(
                event_id=curve.event_id,
                event_type=curve.event_type,
                symbol=curve.symbol,
                signal_type="slow_diffusion",
                direction=curve.final_direction,
                strength=min(abs(late / early) / 5, 1.0) if early != 0 else 0.8,
                entry_horizon="15m",
                exit_horizon="4h",
                context={"early_move": early, "late_move": late, "ratio": late/early if early != 0 else 999}
            ))

        return signals

    def detect_initial_misinterpretation(self, curve: EventResponseCurve) -> list:
        """Market initially moves wrong way, then reverses."""
        signals = []
        if curve.final_direction == 0:
            return signals

        early = curve.horizons.get("5m", 0)
        early_dir = 1 if early > 0 else (-1 if early < 0 else 0)

        if early_dir != 0 and early_dir != curve.final_direction:
            # Initial move was opposite to final
            signals.append(self.DelayedSignal(
                event_id=curve.event_id,
                event_type=curve.event_type,
                symbol=curve.symbol,
                signal_type="initial_misinterpretation",
                direction=curve.final_direction,
                strength=0.8,
                entry_horizon="15m",
                exit_horizon="4h",
                context={"early_move": early, "early_dir": early_dir, "final_dir": curve.final_direction}
            ))

        return signals

    def detect_partial_incorporation(self, curve: EventResponseCurve) -> list:
        """Move happens in steps: 50% at 15m, another 30% at 1h, rest later."""
        signals = []
        if curve.final_direction == 0:
            return signals

        moves = {k: v for k, v in curve.horizons.items() if v != 0}
        if len(moves) < 4:
            return signals

        # Check for step-wise incorporation
        steps = []
        prev = 0
        for name in ["5m", "15m", "30m", "1h", "4h"]:
            if name in moves:
                step = moves[name] - prev
                if abs(step) > abs(moves[name]) * 0.2:  # Meaningful step
                    steps.append((name, step))
                prev = moves[name]

        if len(steps) >= 3:
            signals.append(self.DelayedSignal(
                event_id=curve.event_id,
                event_type=curve.event_type,
                symbol=curve.symbol,
                signal_type="partial_incorporation",
                direction=curve.final_direction,
                strength=0.7,
                entry_horizon=steps[1][0] if len(steps) > 1 else "15m",
                exit_horizon="4h",
                context={"steps": steps}
            ))

        return signals

    def detect_reversal_after_peak(self, curve: EventResponseCurve) -> list:
        """Move peaks early then reverses."""
        signals = []
        if not curve.peak_horizon or curve.peak_horizon in ["4h", "1d", "2d", "5d"]:
            return signals

        peak_val = curve.horizons.get(curve.peak_horizon, 0)
        final_val = list(curve.horizons.values())[-1]

        if abs(final_val) < abs(peak_val) * 0.5 and peak_val * final_val > 0:
            # Reversed more than 50% from peak
            signals.append(self.DelayedSignal(
                event_id=curve.event_id,
                event_type=curve.event_type,
                symbol=curve.symbol,
                signal_type="reversal_after_peak",
                direction=-curve.final_direction,  # Trade the reversal
                strength=0.75,
                entry_horizon=curve.peak_horizon,
                exit_horizon="4h",
                context={"peak_horizon": curve.peak_horizon, "peak_val": peak_val, "final_val": final_val}
            ))

        return signals

    def generate_all_signals(self, curves: list[EventResponseCurve]) -> list:
        """Generate all delayed reaction signals."""
        all_signals = []
        for curve in curves:
            all_signals.extend(self.detect_slow_diffusion(curve))
            all_signals.extend(self.detect_initial_misinterpretation(curve))
            all_signals.extend(self.detect_partial_incorporation(curve))
            all_signals.extend(self.detect_reversal_after_peak(curve))

        self.signals = all_signals
        return all_signals

    def record_outcome(self, signal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 8) -> list[SideChannelHypothesis]:
        """Generate hypotheses from delayed reaction signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.signal_type}_{s.event_type}_{s.symbol}"
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
                    axis=SideChannelAxis.MICROSTRUCTURE,
                    source="delayed_reaction_miner",
                    mechanism=f"Delayed reaction: {example.signal_type} for {example.event_type} on {example.symbol}. "
                              f"Information half-life creates exploitable delay. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} events.",
                    symbols=[example.symbol],
                    timing={
                        "event_type": example.event_type,
                        "signal_type": example.signal_type,
                        "entry": example.entry_horizon,
                        "exit": example.exit_horizon,
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=f"{example.entry_horizon}_to_{example.exit_horizon}",
                    capacity_estimate="micro",
                    metadata={
                        "event_type": example.event_type,
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
        with open(DELAY_DIR / "curves.json", "w") as f:
            json.dump([{
                "event_id": c.event_id,
                "event_type": c.event_type,
                "symbol": c.symbol,
                "horizons": c.horizons,
                "half_life_minutes": c.half_life_minutes,
                "peak_horizon": c.peak_horizon,
                "final_direction": c.final_direction,
                "mispriced_horizons": c.mispriced_horizons,
            } for c in self.collector.curves], f, indent=2, default=str)

        with open(DELAY_DIR / "signals.json", "w") as f:
            json.dump([{
                "event_id": s.event_id,
                "event_type": s.event_type,
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "entry_horizon": s.entry_horizon,
                "exit_horizon": s.exit_horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    collector = DelayedReactionCollector()

    # Create synthetic price data
    dates = pd.date_range("2026-01-01 12:30", periods=500, freq="1min", tz=UTC)
    base = np.cumsum(np.random.randn(500) * 0.0001)

    # Event at t=0: sudden move then slow diffusion
    event_time = dates[0]
    price_data = pd.DataFrame({
        "open": 2000 + base * 10,
        "high": 2000 + base * 10 + np.abs(np.random.randn(500) * 0.5),
        "low": 2000 + base * 10 - np.abs(np.random.randn(500) * 0.5),
        "close": 2000 + base * 10 + np.random.randn(500) * 0.3,
    }, index=dates)

    curve = collector.build_response_curve("CPI_2026_01", "US_CPI", "XAUUSD", event_time, price_data)
    if curve:
        print(f"Curve built: half_life={curve.half_life_minutes:.1f}min, peak={curve.peak_horizon}")

    analyzer = DelayedReactionAnalyzer()
    analyzer.collector = collector
    signals = analyzer.generate_all_signals([curve] if curve else [])
    print(f"Generated {len(signals)} delayed reaction signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} delayed reaction hypotheses")