"""Market Opening Micro-Events Atlas — mines session transition dynamics.

Creates opening transition atlas for every geographically relevant session:
- Tokyo → London
- London → NY
- Cash equity open
- COMEX open
- Futures reopen
- Sunday open
- Post-roll reopen
- Holiday reopen

Measures: spread compression, tick rate, direction, wick asymmetry,
gap, previous-session inventory, volatility release.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

OPEN_DIR = DATA_DIR / "opening_atlas"
OPEN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class OpeningTransition:
    """One market opening transition event."""
    timestamp: datetime
    transition_name: str                       # "tokyo_to_london", "london_to_ny", "sunday_open", etc.
    symbol: str
    pre_open_spread: float
    open_spread: float
    spread_compression: float                  # pre_open / open
    pre_open_tick_rate: float
    open_tick_rate: float
    tick_acceleration: float                   # open / pre_open
    gap: float                                 # open - prev_close
    gap_atr_ratio: float                       # gap / ATR
    first_minute_direction: int                # +1 up, -1 down, 0 flat
    first_5min_direction: int
    first_15min_direction: int
    wick_asymmetry: float                      # (high-open)/(open-low) - 1
    volume_surge: float                        # volume / avg_volume
    prev_session_range: float
    prev_session_close: float
    metadata: dict = field(default_factory=dict)


@dataclass
class OpeningSignal:
    """Alpha signal from opening transition."""
    timestamp: datetime
    symbol: str
    transition_name: str
    signal_type: str
    direction: int
    strength: float
    expected_horizon: str
    context: dict
    subsequent_outcome: dict | None = None


# Session transition definitions
SESSION_TRANSITIONS = {
    "sunday_open": {
        "time_utc": time(22, 0),  # Sunday 22:00 UTC (Monday 00:00 Sydney)
        "symbols": ["ALL"],
        "description": "Weekly open after weekend gap",
    },
    "tokyo_open": {
        "time_utc": time(0, 0),
        "symbols": ["USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "CADJPY", "CHFJPY", "XAUUSD", "JP225"],
        "description": "Tokyo cash session open",
    },
    "london_open": {
        "time_utc": time(7, 0),
        "symbols": ["EURUSD", "GBPUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD", "EU50", "UK100", "DE40", "XAGUSD"],
        "description": "London cash session open",
    },
    "ny_open": {
        "time_utc": time(13, 0),
        "symbols": ["ALL_US", "US500", "US30", "USTEC", "USOIL", "XAUUSD", "USDCAD", "USDCHF", "DXY"],
        "description": "New York cash session open",
    },
    "comex_open": {
        "time_utc": time(12, 20),
        "symbols": ["XAUUSD", "XAGUSD", "USOIL", "COPPER"],
        "description": "COMEX futures open",
    },
    "futures_reopen": {
        "time_utc": time(22, 0),
        "symbols": ["ALL_FUTURES", "US500", "US30", "USTEC", "EU50", "DE40"],
        "description": "Globex/CME futures reopen",
    },
    "london_close": {
        "time_utc": time(16, 0),
        "symbols": ["EURUSD", "GBPUSD", "EURGBP", "EU50", "UK100", "XAUUSD"],
        "description": "London cash close / NY afternoon",
    },
    "ny_close": {
        "time_utc": time(21, 0),
        "symbols": ["ALL_US", "US500", "XAUUSD", "USOIL", "DXY"],
        "description": "NY cash close",
    },
    "weekend_close": {
        "time_utc": time(21, 0),
        "symbols": ["ALL"],
        "description": "Friday NY close → weekend",
    },
}


class OpeningAtlasCollector:
    """Collects opening transition data from price feeds."""

    def __init__(self):
        self.transitions: list[OpeningTransition] = []

    def collect_transition(self, symbol: str, transition_name: str,
                            price_data: pd.DataFrame,
                            lookback_minutes: int = 30) -> OpeningTransition | None:
        """Collect one opening transition from price data."""
        if transition_name not in SESSION_TRANSITIONS:
            return None

        trans_info = SESSION_TRANSITIONS[transition_name]
        trans_time = trans_info["time_utc"]

        # Find the transition timestamp in data
        # We need data around the transition time
        dates = price_data.index
        target_date = dates[-1].date()
        target_ts = datetime.combine(target_date, trans_time, tzinfo=UTC)

        # Get data around transition
        mask = (dates >= target_ts - timedelta(minutes=lookback_minutes)) & \
               (dates <= target_ts + timedelta(minutes=30))
        window = price_data[mask]
        if len(window) < 20:
            return None

        # Pre-open window (15 min before)
        pre_mask = (window.index >= target_ts - timedelta(minutes=15)) & \
                   (window.index < target_ts)
        pre_open = window[pre_mask]

        # Open window (first 15 min)
        open_mask = (window.index >= target_ts) & \
                    (window.index <= target_ts + timedelta(minutes=15))
        open_window = window[open_mask]

        if len(pre_open) < 5 or len(open_window) < 5:
            return None

        # Metrics
        pre_spread = (pre_open["high"] - pre_open["low"]).mean() if len(pre_open) > 0 else 0
        open_spread = (open_window["high"] - open_window["low"]).mean() if len(open_window) > 0 else 0
        spread_compression = pre_spread / open_spread if open_spread > 0 else 0

        # Tick rate (approximate from bar count)
        pre_tick_rate = len(pre_open) / 15 if len(pre_open) > 0 else 0
        open_tick_rate = len(open_window) / 15 if len(open_window) > 0 else 0
        tick_acceleration = open_tick_rate / pre_tick_rate if pre_tick_rate > 0 else 0

        # Gap
        prev_close = window[window.index < target_ts]["close"].iloc[-1] if len(window[window.index < target_ts]) > 0 else 0
        open_price = open_window["open"].iloc[0] if len(open_window) > 0 else 0
        gap = open_price - prev_close if prev_close > 0 else 0

        # ATR
        atr_window = price_data[price_data.index < target_ts].tail(14)
        atr = (atr_window["high"] - atr_window["low"]).mean() if len(atr_window) > 0 else 0
        gap_atr_ratio = gap / atr if atr > 0 else 0

        # Direction
        first_minute = open_window.head(1)
        first_5min = open_window.head(5)
        first_15min = open_window.head(15)

        first_min_dir = 0
        if len(first_minute) > 0:
            first_min_dir = 1 if first_minute["close"].iloc[0] > first_minute["open"].iloc[0] else (-1 if first_minute["close"].iloc[0] < first_minute["open"].iloc[0] else 0)

        first_5_dir = 0
        if len(first_5min) > 0:
            first_5_dir = 1 if first_5min["close"].iloc[-1] > first_5min["open"].iloc[0] else (-1 if first_5min["close"].iloc[-1] < first_5min["open"].iloc[0] else 0)

        first_15_dir = 0
        if len(first_15min) > 0:
            first_15_dir = 1 if first_15min["close"].iloc[-1] > first_15min["open"].iloc[0] else (-1 if first_15min["close"].iloc[-1] < first_15min["open"].iloc[0] else 0)

        # Wick asymmetry
        wick_asym = 0
        if len(open_window) > 0:
            up_wicks = (open_window["high"] - open_window[["open", "close"]].max(axis=1)).sum()
            down_wicks = (open_window[["open", "close"]].min(axis=1) - open_window["low"]).sum()
            if down_wicks > 0:
                wick_asym = up_wicks / down_wicks - 1

        # Volume surge
        pre_vol = pre_open["tick_volume"].mean() if "tick_volume" in pre_open.columns and len(pre_open) > 0 else 0
        open_vol = open_window["tick_volume"].mean() if "tick_volume" in open_window.columns and len(open_window) > 0 else 0
        volume_surge = open_vol / pre_vol if pre_vol > 0 else 0

        # Prev session range
        prev_session = price_data[price_data.index < target_ts].tail(100)
        prev_range = (prev_session["high"].max() - prev_session["low"].min()) if len(prev_session) > 0 else 0

        return OpeningTransition(
            timestamp=target_ts,
            transition_name=transition_name,
            symbol=symbol,
            pre_open_spread=pre_spread,
            open_spread=open_spread,
            spread_compression=spread_compression,
            pre_open_tick_rate=pre_tick_rate,
            open_tick_rate=open_tick_rate,
            tick_acceleration=tick_acceleration,
            gap=gap,
            gap_atr_ratio=gap_atr_ratio,
            first_minute_direction=first_min_dir,
            first_5min_direction=first_5_dir,
            first_15min_direction=first_15_dir,
            wick_asymmetry=wick_asym,
            volume_surge=volume_surge,
            prev_session_range=prev_range,
            prev_session_close=prev_close,
            metadata={
                "transition": transition_name,
                "description": trans_info["description"],
            }
        )

    def collect_all_transitions(self, symbols: list[str],
                                 price_data: dict[str, pd.DataFrame]) -> list[OpeningTransition]:
        """Collect all transitions for all symbols."""
        all_transitions = []
        for trans_name in SESSION_TRANSITIONS:
            trans_info = SESSION_TRANSITIONS[trans_name]
            trans_symbols = trans_info["symbols"]
            if "ALL" in trans_symbols:
                target_symbols = symbols
            else:
                target_symbols = [s for s in symbols if s in trans_symbols]

            for sym in target_symbols:
                if sym in price_data:
                    trans = self.collect_transition(sym, trans_name, price_data[sym])
                    if trans:
                        self.transitions.append(trans)
                        all_transitions.append(trans)
        return all_transitions


class OpeningAtlasAnalyzer:
    """Analyzes opening transitions for alpha."""

    def __init__(self):
        self.transitions: list[OpeningTransition] = []
        self.signals: list[OpeningSignal] = []

    def add_transitions(self, transitions: list[OpeningTransition]) -> None:
        self.transitions.extend(transitions)

    def detect_gap_fade(self, symbol: str) -> list[OpeningSignal]:
        """Gap fade: gap in one direction, then reversal."""
        signals = []
        sym_trans = [t for t in self.transitions if t.symbol == symbol and abs(t.gap_atr_ratio) > 0.5]

        for t in sym_trans:
            # Gap up but first minute down, or gap down but first minute up
            if t.gap > 0 and t.first_minute_direction == -1:
                signals.append(OpeningSignal(
                    timestamp=t.timestamp,
                    symbol=symbol,
                    transition_name=t.transition_name,
                    signal_type="gap_fade",
                    direction=-1,
                    strength=min(abs(t.gap_atr_ratio), 1.0),
                    expected_horizon="15m_to_1h",
                    context={"gap_atr": t.gap_atr_ratio, "first_min": t.first_minute_direction}
                ))
            elif t.gap < 0 and t.first_minute_direction == 1:
                signals.append(OpeningSignal(
                    timestamp=t.timestamp,
                    symbol=symbol,
                    transition_name=t.transition_name,
                    signal_type="gap_fade",
                    direction=1,
                    strength=min(abs(t.gap_atr_ratio), 1.0),
                    expected_horizon="15m_to_1h",
                    context={"gap_atr": t.gap_atr_ratio, "first_min": t.first_minute_direction}
                ))

        return signals

    def detect_volatility_release(self, symbol: str) -> list[OpeningSignal]:
        """Volatility release: tight pre-open, then expansion."""
        signals = []
        sym_trans = [t for t in self.transitions if t.symbol == symbol and t.tick_acceleration > 2.0]

        for t in sym_trans:
            signals.append(OpeningSignal(
                timestamp=t.timestamp,
                symbol=symbol,
                transition_name=t.transition_name,
                signal_type="volatility_release",
                direction=t.first_5min_direction,
                strength=min(t.tick_acceleration / 5, 1.0),
                expected_horizon="5m_to_30m",
                context={"tick_accel": t.tick_acceleration, "spread_comp": t.spread_compression}
            ))

        return signals

    def detect_momentum_continuation(self, symbol: str) -> list[OpeningSignal]:
        """First 5min direction continues for 15min+."""
        signals = []
        sym_trans = [t for t in self.transitions if t.symbol == symbol]

        for t in sym_trans:
            if t.first_5min_direction == t.first_15min_direction != 0:
                signals.append(OpeningSignal(
                    timestamp=t.timestamp,
                    symbol=symbol,
                    transition_name=t.transition_name,
                    signal_type="momentum_continuation",
                    direction=t.first_5min_direction,
                    strength=0.7,
                    expected_horizon="15m_to_2h",
                    context={"first_5": t.first_5min_direction, "first_15": t.first_15min_direction}
                ))

        return signals

    def detect_wick_rejection(self, symbol: str) -> list[OpeningSignal]:
        """Wick asymmetry signals rejection."""
        signals = []
        sym_trans = [t for t in self.transitions if t.symbol == symbol and abs(t.wick_asymmetry) > 0.5]

        for t in sym_trans:
            # Long upper wick = rejection of highs
            if t.wick_asymmetry > 0.5 and t.first_5min_direction <= 0:
                signals.append(OpeningSignal(
                    timestamp=t.timestamp,
                    symbol=symbol,
                    transition_name=t.transition_name,
                    signal_type="wick_rejection",
                    direction=-1,
                    strength=min(t.wick_asymmetry / 2, 1.0),
                    expected_horizon="15m_to_1h",
                    context={"wick_asym": t.wick_asymmetry}
                ))
            # Long lower wick = rejection of lows
            elif t.wick_asymmetry < -0.5 and t.first_5min_direction >= 0:
                signals.append(OpeningSignal(
                    timestamp=t.timestamp,
                    symbol=symbol,
                    transition_name=t.transition_name,
                    signal_type="wick_rejection",
                    direction=1,
                    strength=min(abs(t.wick_asymmetry) / 2, 1.0),
                    expected_horizon="15m_to_1h",
                    context={"wick_asym": t.wick_asymmetry}
                ))

        return signals

    def generate_all_signals(self) -> list[OpeningSignal]:
        """Generate all opening signals."""
        all_signals = []
        symbols = set(t.symbol for t in self.transitions)

        for sym in symbols:
            all_signals.extend(self.detect_gap_fade(sym))
            all_signals.extend(self.detect_volatility_release(sym))
            all_signals.extend(self.detect_momentum_continuation(sym))
            all_signals.extend(self.detect_wick_rejection(sym))

        self.signals = all_signals
        return all_signals

    def record_outcome(self, signal: OpeningSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 10) -> list[SideChannelHypothesis]:
        """Generate hypotheses from opening signals."""
        if len(self.signals) < min_signals:
            return []

        from collections import defaultdict
        groups = defaultdict(list)
        for s in self.signals:
            key = f"{s.signal_type}_{s.transition_name}_{s.symbol}"
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
                    source="opening_atlas",
                    mechanism=f"Opening transition signal: {example.signal_type} at {example.transition_name} "
                              f"on {example.symbol}. Avg return {np.mean(returns):.3f}R over {len(returns)} occurrences.",
                    symbols=[example.symbol],
                    timing={
                        "transition": example.transition_name,
                        "signal_type": example.signal_type,
                        "session": example.transition_name,
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="micro",
                    metadata={
                        "transition": example.transition_name,
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
        with open(OPEN_DIR / "transitions.json", "w") as f:
            json.dump([{
                "timestamp": t.timestamp.isoformat(),
                "transition": t.transition_name,
                "symbol": t.symbol,
                "spread_compression": t.spread_compression,
                "tick_acceleration": t.tick_acceleration,
                "gap": t.gap,
                "gap_atr_ratio": t.gap_atr_ratio,
                "first_min_dir": t.first_minute_direction,
                "first_5min_dir": t.first_5min_direction,
                "first_15min_dir": t.first_15min_direction,
                "wick_asymmetry": t.wick_asymmetry,
                "volume_surge": t.volume_surge,
            } for t in self.transitions], f, indent=2, default=str)

        with open(OPEN_DIR / "signals.json", "w") as f:
            json.dump([{
                "timestamp": s.timestamp.isoformat(),
                "symbol": s.symbol,
                "transition": s.transition_name,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    dates = pd.date_range("2026-01-01", periods=10000, freq="1min", tz=UTC)
    prices = pd.DataFrame({
        "open": 2000 + np.cumsum(np.random.randn(10000) * 0.1),
        "high": 0, "low": 0, "close": 0, "tick_volume": np.random.randint(10, 100, 10000)
    }, index=dates)
    prices["high"] = prices["open"] + np.abs(np.random.randn(10000) * 0.5)
    prices["low"] = prices["open"] - np.abs(np.random.randn(10000) * 0.5)
    prices["close"] = prices["open"] + np.random.randn(10000) * 0.3

    collector = OpeningAtlasCollector()
    collector.collect_all_transitions(["XAUUSD"], {"XAUUSD": prices})

    analyzer = OpeningAtlasAnalyzer()
    analyzer.add_transitions(collector.transitions)
    signals = analyzer.generate_all_signals()
    print(f"Detected {len(signals)} opening signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} opening hypotheses")