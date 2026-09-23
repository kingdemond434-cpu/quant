"""Swap Table Miner — mines alpha from broker swap/rollover data.

Almost nobody treats this as a serious alpha dataset.
Archives daily: long swap, short swap, triple-swap schedule, changes,
symbol, interest-rate differential, price trend, volatility.

Hunts: carry+momentum, carry reversal, swap regime changes predicting
positioning, abnormal roll-day behavior, trades where directional edge
and carry align, holding-period optimization around rollover.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

SWAP_DIR = DATA_DIR / "swap_table"
SWAP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SwapSnapshot:
    """Daily swap rates for all symbols."""
    date: datetime
    symbol: str
    long_swap: float                           # points
    short_swap: float                          # points
    long_swap_annual: float                    # annualized %
    short_swap_annual: float                   # annualized %
    triple_swap: bool                          # Wednesday triple
    ir_differential: float                     # interest rate diff (est)
    price: float                               # current price
    trend: str                                 # "up", "down", "flat"
    volatility: float                          # recent vol
    metadata: dict = field(default_factory=dict)


@dataclass
class SwapSignal:
    """Alpha signal from swap data."""
    date: datetime
    symbol: str
    signal_type: str                           # "carry_momentum", "carry_reversal", "regime_change", "roll_anomaly"
    direction: int                             # +1 long, -1 short
    strength: float
    carry_bps: float                           # daily carry in bps
    expected_holding_days: int
    context: dict
    subsequent_outcome: dict | None = None


class SwapTableCollector:
    """Collects swap data from MT5."""

    def __init__(self, mt5_terminal_path: str | None = None):
        self.mt5_path = mt5_terminal_path
        self.snapshots: list[SwapSnapshot] = []

    def collect_daily_swaps(self, symbols: list[str]) -> list[SwapSnapshot]:
        """Collect swap rates for all symbols."""
        try:
            import MetaTrader5 as mt5
        except ImportError:
            return []

        if not mt5.initialize(path=self.mt5_path):
            return []

        snapshots = []
        try:
            for symbol in symbols:
                info = mt5.symbol_info(symbol)
                if not info:
                    continue

                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    continue

                long_swap = info.swap_long
                short_swap = info.swap_short

                # Annualize (swap points per day * 365 / price * contract_size)
                contract_size = info.trade_contract_size
                price = (tick.ask + tick.bid) / 2

                long_annual = (long_swap * 365 * contract_size) / (price * contract_size) * 100 if price > 0 else 0
                short_annual = (short_swap * 365 * contract_size) / (price * contract_size) * 100 if price > 0 else 0

                # Check if Wednesday (triple swap)
                is_wed = datetime.now(UTC).weekday() == 2

                # Estimate IR differential from swap
                # Simplified: swap ≈ IR_diff / 365 * contract_size
                ir_diff = (long_swap - short_swap) / 2 * 365 / 10000  # Rough estimate

                # Trend
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 20)
                if rates is not None and len(rates) > 10:
                    df = pd.DataFrame(rates)
                    df["close"] = df["close"]
                    sma_short = df["close"].rolling(5).mean().iloc[-1]
                    sma_long = df["close"].rolling(20).mean().iloc[-1]
                    trend = "up" if sma_short > sma_long * 1.005 else ("down" if sma_short < sma_long * 0.995 else "flat")
                    vol = df["close"].pct_change().std() * np.sqrt(252)
                else:
                    trend = "flat"
                    vol = 0

                snap = SwapSnapshot(
                    date=datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0),
                    symbol=symbol,
                    long_swap=long_swap,
                    short_swap=short_swap,
                    long_swap_annual=long_annual,
                    short_swap_annual=short_annual,
                    triple_swap=is_wed,
                    ir_differential=ir_diff,
                    price=price,
                    trend=trend,
                    volatility=vol,
                    metadata={"contract_size": contract_size}
                )
                snapshots.append(snap)
                self.snapshots.append(snap)

            return snapshots

        finally:
            mt5.shutdown()

    def load_history(self, path: Path | None = None) -> None:
        """Load historical swap data."""
        if path is None:
            path = SWAP_DIR / "swap_history.json"
        if not path.exists():
            return
        import json
        with open(path, "r") as f:
            data = json.load(f)
        for d in data:
            d["date"] = datetime.fromisoformat(d["date"])
            self.snapshots.append(SwapSnapshot(**d))


class SwapTableAnalyzer:
    """Analyzes swap table for alpha signals."""

    def __init__(self):
        self.collector = SwapTableCollector()
        self.signals: list[SwapSignal] = []

    def detect_carry_momentum(self, symbol: str, lookback_days: int = 30) -> list[SwapSignal]:
        """Carry + momentum alignment: earn carry in direction of trend."""
        signals = []
        sym_snaps = [s for s in self.collector.snapshots if s.symbol == symbol]
        if len(sym_snaps) < lookback_days:
            return signals

        df = pd.DataFrame([{
            "date": s.date,
            "long_swap": s.long_swap,
            "short_swap": s.short_swap,
            "long_annual": s.long_swap_annual,
            "short_annual": s.short_swap_annual,
            "price": s.price,
            "trend": s.trend,
            "vol": s.volatility,
        } for s in sym_snaps[-lookback_days:]])

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]

            # Carry in trend direction
            if row["trend"] == "up" and row["long_swap"] > 0:
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="carry_momentum",
                    direction=1,
                    strength=min(row["long_swap_annual"] / 10, 1.0),
                    carry_bps=row["long_swap_annual"] / 365 * 10000,
                    expected_holding_days=5,
                    context={"trend": "up", "carry_annual": row["long_swap_annual"]}
                ))
            elif row["trend"] == "down" and row["short_swap"] > 0:
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="carry_momentum",
                    direction=-1,
                    strength=min(row["short_swap_annual"] / 10, 1.0),
                    carry_bps=row["short_swap_annual"] / 365 * 10000,
                    expected_holding_days=5,
                    context={"trend": "down", "carry_annual": row["short_swap_annual"]}
                ))

        return signals

    def detect_carry_reversal(self, symbol: str, lookback_days: int = 60) -> list[SwapSignal]:
        """Carry reversal: swap flips but price hasn't adjusted yet."""
        signals = []
        sym_snaps = [s for s in self.collector.snapshots if s.symbol == symbol]
        if len(sym_snaps) < lookback_days:
            return signals

        df = pd.DataFrame([{
            "date": s.date,
            "long_swap": s.long_swap,
            "short_swap": s.short_swap,
            "price": s.price,
        } for s in sym_snaps[-lookback_days:]])

        # Detect swap sign change
        df["long_swap_change"] = df["long_swap"].diff()
        df["short_swap_change"] = df["short_swap"].diff()

        for i in range(1, len(df)):
            row = df.iloc[i]

            # Long swap turned negative (was positive)
            if row["long_swap"] <= 0 and df.iloc[i-1]["long_swap"] > 0:
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="carry_reversal",
                    direction=-1,  # Short if long carry gone
                    strength=0.7,
                    carry_bps=0,
                    expected_holding_days=10,
                    context={"long_swap_was": df.iloc[i-1]["long_swap"], "now": row["long_swap"]}
                ))

            # Short swap turned negative
            if row["short_swap"] <= 0 and df.iloc[i-1]["short_swap"] > 0:
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="carry_reversal",
                    direction=1,  # Long if short carry gone
                    strength=0.7,
                    carry_bps=0,
                    expected_holding_days=10,
                    context={"short_swap_was": df.iloc[i-1]["short_swap"], "now": row["short_swap"]}
                ))

        return signals

    def detect_swap_regime_change(self, symbol: str, window: int = 20) -> list[SwapSignal]:
        """Swap regime change: structural shift in swap levels."""
        signals = []
        sym_snaps = [s for s in self.collector.snapshots if s.symbol == symbol]
        if len(sym_snaps) < window * 2:
            return signals

        df = pd.DataFrame([{
            "date": s.date,
            "long_swap": s.long_swap,
            "short_swap": s.short_swap,
        } for s in sym_snaps])

        df["long_ma"] = df["long_swap"].rolling(window).mean()
        df["short_ma"] = df["short_swap"].rolling(window).mean()
        df["long_std"] = df["long_swap"].rolling(window).std()
        df["short_std"] = df["short_swap"].rolling(window).std()

        for i in range(window, len(df)):
            row = df.iloc[i]
            if pd.isna(row["long_ma"]):
                continue

            # Regime change: swap moves >2 std from rolling mean
            if abs(row["long_swap"] - row["long_ma"]) > 2 * row["long_std"]:
                direction = 1 if row["long_swap"] > row["long_ma"] else -1
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="swap_regime_change",
                    direction=direction,
                    strength=min(abs(row["long_swap"] - row["long_ma"]) / (row["long_std"] + 1e-12) / 3, 1.0),
                    carry_bps=0,
                    expected_holding_days=20,
                    context={
                        "long_swap": row["long_swap"],
                        "long_ma": row["long_ma"],
                        "z_score": (row["long_swap"] - row["long_ma"]) / (row["long_std"] + 1e-12),
                    }
                ))

            if abs(row["short_swap"] - row["short_ma"]) > 2 * row["short_std"]:
                direction = -1 if row["short_swap"] > row["short_ma"] else 1
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="swap_regime_change",
                    direction=direction,
                    strength=min(abs(row["short_swap"] - row["short_ma"]) / (row["short_std"] + 1e-12) / 3, 1.0),
                    carry_bps=0,
                    expected_holding_days=20,
                    context={
                        "short_swap": row["short_swap"],
                        "short_ma": row["short_ma"],
                        "z_score": (row["short_swap"] - row["short_ma"]) / (row["short_std"] + 1e-12),
                    }
                ))

        return signals

    def detect_roll_anomaly(self, symbol: str) -> list[SwapSignal]:
        """Abnormal roll-day behavior (Wednesday triple swap)."""
        signals = []
        sym_snaps = [s for s in self.collector.snapshots if s.symbol == symbol]
        if len(sym_snaps) < 10:
            return signals

        df = pd.DataFrame([{
            "date": s.date,
            "long_swap": s.long_swap,
            "short_swap": s.short_swap,
            "triple_swap": s.triple_swap,
        } for s in sym_snaps])

        # Wednesday anomalies
        wed_df = df[df["triple_swap"]]
        for _, row in wed_df.iterrows():
            # Check if triple swap is abnormally large/small
            normal_long = df[~df["triple_swap"]]["long_swap"].mean()
            normal_short = df[~df["triple_swap"]]["short_swap"].mean()

            if row["long_swap"] > normal_long * 3.5:  # More than 3.5x normal
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="roll_anomaly",
                    direction=1,
                    strength=0.8,
                    carry_bps=row["long_swap"] / 365 * 10000,
                    expected_holding_days=1,
                    context={"anomaly": "excessive_triple_long", "ratio": row["long_swap"] / normal_long}
                ))

            if row["short_swap"] > normal_short * 3.5:
                signals.append(SwapSignal(
                    date=row["date"],
                    symbol=symbol,
                    signal_type="roll_anomaly",
                    direction=-1,
                    strength=0.8,
                    carry_bps=row["short_swap"] / 365 * 10000,
                    expected_holding_days=1,
                    context={"anomaly": "excessive_triple_short", "ratio": row["short_swap"] / normal_short}
                ))

        return signals

    def generate_all_signals(self, symbols: list[str]) -> list[SwapSignal]:
        """Generate all swap signals for symbols."""
        all_signals = []
        for sym in symbols:
            all_signals.extend(self.detect_carry_momentum(sym))
            all_signals.extend(self.detect_carry_reversal(sym))
            all_signals.extend(self.detect_swap_regime_change(sym))
            all_signals.extend(self.detect_roll_anomaly(sym))
        self.signals = all_signals
        return all_signals

    def record_outcome(self, signal: SwapSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 15) -> list[SideChannelHypothesis]:
        """Generate hypotheses from swap signals."""
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

            # Check if signals have positive expectancy
            returns = []
            for o in outcomes:
                if "return_bps" in o:
                    returns.append(o["return_bps"])

            if returns and np.mean(returns) > 0:
                example = signals[0]
                h = SideChannelHypothesis(
                    id=generate_id(),
                    axis=SideChannelAxis.SEASONALITY,
                    source="swap_table_miner",
                    mechanism=f"Swap signal: {example.signal_type} on {example.symbol}. "
                              f"Avg return {np.mean(returns):.1f} bps over {len(returns)} occurrences. "
                              f"Carry: {example.carry_bps:.1f} bps/day.",
                    symbols=[example.symbol],
                    timing={
                        "signal_type": example.signal_type,
                        "carry_bps": example.carry_bps,
                        "holding_days": example.expected_holding_days,
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=f"{example.expected_holding_days}d",
                    capacity_estimate="small",
                    metadata={
                        "signal_type": example.signal_type,
                        "symbol": example.symbol,
                        "avg_return_bps": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(SWAP_DIR / "swap_history.json", "w") as f:
            json.dump([{
                "date": s.date.isoformat(),
                "symbol": s.symbol,
                "long_swap": s.long_swap,
                "short_swap": s.short_swap,
                "long_swap_annual": s.long_swap_annual,
                "short_swap_annual": s.short_swap_annual,
                "triple_swap": s.triple_swap,
                "ir_differential": s.ir_differential,
                "price": s.price,
                "trend": s.trend,
                "volatility": s.volatility,
            } for s in self.collector.snapshots], f, indent=2, default=str)

        with open(SWAP_DIR / "signals.json", "w") as f:
            json.dump([{
                "date": s.date.isoformat(),
                "symbol": s.symbol,
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "carry_bps": s.carry_bps,
                "holding_days": s.expected_holding_days,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    # Test with synthetic data
    collector = SwapTableCollector()
    dates = pd.date_range("2026-01-01", periods=100, freq="D", tz=UTC)

    for i, d in enumerate(dates):
        collector.snapshots.append(SwapSnapshot(
            date=d, symbol="USDCAD",
            long_swap=1.5 + np.sin(i/10) * 0.5,
            short_swap=-2.0 + np.cos(i/10) * 0.5,
            long_swap_annual=5.0, short_swap_annual=-6.0,
            triple_swap=(d.weekday() == 2),
            ir_differential=1.5, price=1.35,
            trend="up" if i % 20 < 10 else "down", volatility=0.15
        ))

    analyzer = SwapTableAnalyzer()
    analyzer.collector = collector
    signals = analyzer.generate_all_signals(["USDCAD"])
    print(f"Generated {len(signals)} swap signals")

    hyps = analyzer.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} swap hypotheses")