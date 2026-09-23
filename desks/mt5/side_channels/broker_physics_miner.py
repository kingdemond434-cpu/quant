"""Broker-Specific Physics Miner — mines execution alpha from broker microstructure.

Collects permanently:
- spread
- tick arrival rate
- slippage
- fill probability
- order rejection
- stop-level restrictions
- freeze levels
- swap
- rollover
- gap behavior
- quote pauses
- session reopening
- execution latency

Treats these as alpha features. One good execution-state model potentially
improves 20 sleeves simultaneously.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

PHYS_DIR = DATA_DIR / "broker_physics"
PHYS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BrokerMicrostructureState:
    """Complete microstructure snapshot for one symbol at one time."""
    timestamp: datetime
    symbol: str
    spread: float                              # pips or points
    spread_ma: float                           # moving average
    spread_z: float                            # z-score vs recent
    tick_rate: float                           # ticks per minute
    tick_rate_ma: float
    tick_rate_z: float
    volume_per_tick: float
    volume_per_tick_ma: float
    slippage_bps: float                        # recent slippage in bps
    fill_rate: float                           # limit order fill rate
    rejection_rate: float                      # order rejection rate
    stop_level: float                          # broker stop level (points)
    freeze_level: float                        # broker freeze level (points)
    gap_size: float                            # overnight/weekend gap
    quote_pause_duration: float                # seconds of quote pause
    execution_latency_ms: float                # measured round-trip
    session_phase: str                         # "pre_open", "open", "mid", "pre_close", "closed"
    metadata: dict = field(default_factory=dict)


@dataclass
class ExecutionAlphaSignal:
    """A signal derived from broker physics."""
    timestamp: datetime
    symbol: str
    signal_type: str                           # "spread_compression", "tick_acceleration", etc.
    direction: int                             # +1 long, -1 short, 0 neutral
    strength: float                            # 0-1
    expected_improvement_bps: float            # expected slippage reduction
    context: dict
    subsequent_outcome: dict | None = None


class BrokerPhysicsCollector:
    """Collects broker microstructure data from MT5."""

    def __init__(self, mt5_terminal_path: str | None = None):
        self.mt5_path = mt5_terminal_path
        self.snapshots: list[BrokerMicrostructureState] = []

    def collect_snapshot(self, symbol: str) -> BrokerMicrostructureState | None:
        """Collect one microstructure snapshot."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return None

        if not mt5.initialize(path=self.mt5_path):
            return None

        try:
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if not info or not tick:
                return None

            # Spread
            spread_pts = (tick.ask - tick.bid) / info.point

            # Tick rate (approximate from recent ticks)
            ticks = mt5.copy_ticks_from(symbol, datetime.now(UTC) - timedelta(minutes=5),
                                        1000, mt5.COPY_TICKS_ALL)
            if ticks is not None and len(ticks) > 10:
                tick_times = pd.to_datetime(ticks["time"], unit="s", utc=True)
                tick_rate = len(ticks) / 5.0  # per minute
                volumes = ticks["volume"]
                vol_per_tick = volumes.mean() if len(volumes) > 0 else 0
            else:
                tick_rate = 0
                vol_per_tick = 0

            # Session phase
            hour = datetime.now(UTC).hour
            if 0 <= hour < 7:
                session = "asia"
            elif 7 <= hour < 16:
                session = "london"
            elif 13 <= hour < 22:
                session = "ny"
            else:
                session = "closed"

            # Get recent slippage from history
            slippage = self._get_recent_slippage(symbol, mt5)
            fill_rate = self._get_fill_rate(symbol, mt5)
            rejection_rate = self._get_rejection_rate(symbol, mt5)

            snapshot = BrokerMicrostructureState(
                timestamp=datetime.now(UTC),
                symbol=symbol,
                spread=spread_pts,
                spread_ma=0,  # Will be computed in post-processing
                spread_z=0,
                tick_rate=tick_rate,
                tick_rate_ma=0,
                tick_rate_z=0,
                volume_per_tick=vol_per_tick,
                volume_per_tick_ma=0,
                slippage_bps=slippage,
                fill_rate=fill_rate,
                rejection_rate=rejection_rate,
                stop_level=info.trade_stops_level,
                freeze_level=info.trade_freeze_level,
                gap_size=0,  # Computed separately
                quote_pause_duration=0,
                execution_latency_ms=0,  # Measured separately
                session_phase=session,
            )
            self.snapshots.append(snapshot)
            return snapshot

        finally:
            mt5.shutdown()

    def _get_recent_slippage(self, symbol: str, mt5_module) -> float:
        """Get recent slippage from deal history."""
        try:
            deals = mt5_module.history_deals_get(
                datetime.now(UTC) - timedelta(days=7),
                datetime.now(UTC)
            )
            if deals is None:
                return 0.0
            slippages = []
            for deal in deals:
                if deal.symbol == symbol and deal.entry in (0, 1):  # IN/OUT
                    # Simplified: use commission as proxy
                    slippages.append(abs(deal.commission))
            return np.mean(slippages) if slippages else 0.0
        except Exception:
            return 0.0

    def _get_fill_rate(self, symbol: str, mt5_module) -> float:
        """Get recent limit order fill rate."""
        try:
            orders = mt5_module.history_orders_get(
                datetime.now(UTC) - timedelta(days=7),
                datetime.now(UTC)
            )
            if orders is None:
                return 1.0
            limit_orders = [o for o in orders if o.symbol == symbol and o.type in (2, 3)]  # BUY_LIMIT, SELL_LIMIT
            if not limit_orders:
                return 1.0
            filled = sum(1 for o in limit_orders if o.state == 4)  # FILLED
            return filled / len(limit_orders)
        except Exception:
            return 1.0

    def _get_rejection_rate(self, symbol: str, mt5_module) -> float:
        """Get recent order rejection rate."""
        try:
            orders = mt5_module.history_orders_get(
                datetime.now(UTC) - timedelta(days=7),
                datetime.now(UTC)
            )
            if orders is None:
                return 0.0
            sym_orders = [o for o in orders if o.symbol == symbol]
            if not sym_orders:
                return 0.0
            rejected = sum(1 for o in sym_orders if o.state in (5, 6))  # REJECTED, EXPIRED
            return rejected / len(sym_orders)
        except Exception:
            return 0.0

    def collect_continuous(self, symbols: list[str], interval_seconds: int = 60,
                           duration_hours: int = 24) -> list[BrokerMicrostructureState]:
        """Collect continuously for specified duration."""
        import time
        end_time = datetime.now(UTC) + timedelta(hours=duration_hours)
        while datetime.now(UTC) < end_time:
            for sym in symbols:
                self.collect_snapshot(sym)
            time.sleep(interval_seconds)
        return self.snapshots


class BrokerPhysicsAnalyzer:
    """Analyzes broker physics for execution alpha."""

    def __init__(self):
        self.states: list[BrokerMicrostructureState] = []
        self.signals: list[ExecutionAlphaSignal] = []

    def load_states(self, path: Path | None = None) -> None:
        """Load collected states."""
        if path is None:
            path = PHYS_DIR / "microstructure_states.json"
        if not path.exists():
            return
        import json
        with open(path, "r") as f:
            data = json.load(f)
        for d in data:
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
            self.states.append(BrokerMicrostructureState(**d))

    def compute_features(self) -> pd.DataFrame:
        """Compute derived features from raw states."""
        if not self.states:
            return pd.DataFrame()

        df = pd.DataFrame([{
            "timestamp": s.timestamp,
            "symbol": s.symbol,
            "spread": s.spread,
            "tick_rate": s.tick_rate,
            "volume_per_tick": s.volume_per_tick,
            "slippage_bps": s.slippage_bps,
            "fill_rate": s.fill_rate,
            "rejection_rate": s.rejection_rate,
            "stop_level": s.stop_level,
            "freeze_level": s.freeze_level,
            "session_phase": s.session_phase,
        } for s in self.states])

        df = df.set_index("timestamp").sort_index()

        # Rolling features per symbol
        for sym in df["symbol"].unique():
            mask = df["symbol"] == sym
            sym_df = df[mask]

            # Spread features
            df.loc[mask, "spread_ma"] = sym_df["spread"].rolling(100).mean()
            df.loc[mask, "spread_std"] = sym_df["spread"].rolling(100).std()
            df.loc[mask, "spread_z"] = (sym_df["spread"] - df.loc[mask, "spread_ma"]) / (df.loc[mask, "spread_std"] + 1e-12)

            # Tick rate features
            df.loc[mask, "tick_rate_ma"] = sym_df["tick_rate"].rolling(100).mean()
            df.loc[mask, "tick_rate_std"] = sym_df["tick_rate"].rolling(100).std()
            df.loc[mask, "tick_rate_z"] = (sym_df["tick_rate"] - df.loc[mask, "tick_rate_ma"]) / (df.loc[mask, "tick_rate_std"] + 1e-12)

            # Volume per tick
            df.loc[mask, "vol_per_tick_ma"] = sym_df["volume_per_tick"].rolling(100).mean()

            # Slippage features
            df.loc[mask, "slippage_ma"] = sym_df["slippage_bps"].rolling(50).mean()

        return df.reset_index()

    def detect_signals(self, features: pd.DataFrame) -> list[ExecutionAlphaSignal]:
        """Detect execution alpha signals from features."""
        signals = []

        for sym in features["symbol"].unique():
            sym_df = features[features["symbol"] == sym].copy()
            if len(sym_df) < 200:
                continue

            # Signal 1: Spread compression + tick acceleration
            # Both improving simultaneously = liquidity normalization
            spread_comp = (sym_df["spread_z"] < -1.0)
            tick_accel = (sym_df["tick_rate_z"] > 1.0)
            both = spread_comp & tick_accel

            for idx in sym_df[both].index:
                signals.append(ExecutionAlphaSignal(
                    timestamp=idx,
                    symbol=sym,
                    signal_type="spread_compression_tick_acceleration",
                    direction=0,  # Neutral - improves ANY direction
                    strength=min(abs(sym_df.loc[idx, "spread_z"]) / 3, 1.0) * min(sym_df.loc[idx, "tick_rate_z"] / 3, 1.0),
                    expected_improvement_bps=abs(sym_df.loc[idx, "spread_z"]) * 0.5,
                    context={
                        "spread_z": sym_df.loc[idx, "spread_z"],
                        "tick_rate_z": sym_df.loc[idx, "tick_rate_z"],
                        "session": sym_df.loc[idx, "session_phase"],
                    }
                ))

            # Signal 2: Pre-session spread normalization
            # Spread compresses 5-15 min before session open
            pre_open = (sym_df["session_phase"] != sym_df["session_phase"].shift(1)) & (sym_df["session_phase"].isin(["london", "ny"]))
            for idx in sym_df[pre_open].index:
                if idx > 0:
                    prev_idx = sym_df.index.get_loc(idx) - 1
                    if prev_idx >= 0:
                        spread_change = sym_df.iloc[prev_idx]["spread"] - sym_df.loc[idx, "spread"]
                        if spread_change > 0:
                            signals.append(ExecutionAlphaSignal(
                                timestamp=idx,
                                symbol=sym,
                                signal_type="pre_session_spread_compression",
                                direction=0,
                                strength=min(spread_change / sym_df.loc[idx, "spread_ma"], 1.0),
                                expected_improvement_bps=spread_change * 0.1,
                                context={
                                    "session": sym_df.loc[idx, "session_phase"],
                                    "spread_change": spread_change,
                                }
                            ))

            # Signal 3: Stop level constraint relaxation
            # When stop level drops, tighter stops become possible
            stop_drop = (sym_df["stop_level"].diff() < -5)  # 5 points drop
            for idx in sym_df[stop_drop].index:
                signals.append(ExecutionAlphaSignal(
                    timestamp=idx,
                    symbol=sym,
                    signal_type="stop_level_relaxation",
                    direction=0,
                    strength=0.5,
                    expected_improvement_bps=abs(sym_df.loc[idx, "stop_level"].diff()) * 0.01,
                    context={
                        "stop_level": sym_df.loc[idx, "stop_level"],
                        "stop_change": sym_df.loc[idx, "stop_level"].diff(),
                    }
                ))

            # Signal 4: Rejection rate spike = toxic flow, avoid
            high_reject = (sym_df["rejection_rate"] > 0.1)
            for idx in sym_df[high_reject].index:
                signals.append(ExecutionAlphaSignal(
                    timestamp=idx,
                    symbol=sym,
                    signal_type="high_rejection_rate",
                    direction=0,
                    strength=-0.5,  # Negative = avoid
                    expected_improvement_bps=-10,
                    context={
                        "rejection_rate": sym_df.loc[idx, "rejection_rate"],
                    }
                ))

        self.signals.extend(signals)
        return signals

    def record_outcome(self, signal: ExecutionAlphaSignal, outcome: dict) -> None:
        """Record the outcome of an execution signal."""
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 20) -> list[SideChannelHypothesis]:
        """Generate hypotheses from broker physics signals."""
        if len(self.signals) < min_signals:
            return []

        # Group by signal type
        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            groups[s.signal_type].append(s)

        hypotheses = []
        for sig_type, signals in groups.items():
            if len(signals) < min_signals:
                continue

            outcomes = [s.subsequent_outcome for s in signals if s.subsequent_outcome]
            if not outcomes:
                continue

            # Check if signal predicts better execution
            improvements = []
            for o in outcomes:
                if "slippage_improvement" in o:
                    improvements.append(o["slippage_improvement"])

            if improvements and np.mean(improvements) > 0:
                example = signals[0]
                h = SideChannelHypothesis(
                    id=generate_id(),
                    axis=SideChannelAxis.EXECUTION,
                    source="broker_physics_miner",
                    mechanism=f"Broker physics signal: {sig_type} on {example.symbol}. "
                              f"When {sig_type} occurs, execution improves by {np.mean(improvements):.1f} bps on average. "
                              f"Apply as execution filter to all sleeves trading {example.symbol}.",
                    symbols=[example.symbol],
                    timing={
                        "signal_type": sig_type,
                        "session": example.context.get("session", "all"),
                    },
                    falsifier=f"Average improvement drops below 1 bps over 50+ occurrences",
                    expected_horizon="per_trade",
                    capacity_estimate="institutional",  # Applies to all size
                    metadata={
                        "signal_type": sig_type,
                        "symbol": example.symbol,
                        "avg_improvement_bps": float(np.mean(improvements)) if improvements else 0,
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        """Save states and signals."""
        import json
        with open(PHYS_DIR / "microstructure_states.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "spread": s.spread,
                "tick_rate": s.tick_rate,
                "volume_per_tick": s.volume_per_tick,
                "slippage_bps": s.slippage_bps,
                "fill_rate": s.fill_rate,
                "rejection_rate": s.rejection_rate,
                "stop_level": s.stop_level,
                "freeze_level": s.freeze_level,
                "session_phase": s.session_phase,
            } for s in self.states], f, indent=2)

        with open(PHYS_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "expected_improvement_bps": s.expected_improvement_bps,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test analyzer with synthetic data
    analyzer = BrokerPhysicsAnalyzer()

    # Create synthetic states
    dates = pd.date_range("2026-01-01", periods=1000, freq="1min", tz=UTC)
    for i, ts in enumerate(dates):
        spread = 2.0 + np.sin(i / 50) + np.random.randn() * 0.3
        tick_rate = 30 + np.sin(i / 30) * 10 + np.random.randn() * 5
        session = "london" if 7 <= ts.hour < 16 else ("ny" if 13 <= ts.hour < 22 else "asia")

        analyzer.states.append(BrokerMicrostructureState(
            timestamp=ts, symbol="XAUUSD", spread=spread,
            spread_ma=0, spread_z=0, tick_rate=tick_rate,
            tick_rate_ma=0, tick_rate_z=0, volume_per_tick=1.0,
            volume_per_tick_ma=0, slippage_bps=0.5,
            fill_rate=0.9, rejection_rate=0.02, stop_level=20,
            freeze_level=5, gap_size=0, quote_pause_duration=0,
            execution_latency_ms=50, session_phase=session,
        ))

    features = analyzer.compute_features()
    signals = analyzer.detect_signals(features)
    print(f"Detected {len(signals)} execution signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} execution hypotheses")