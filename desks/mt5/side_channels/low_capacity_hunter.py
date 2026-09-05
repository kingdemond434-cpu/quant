"""Low-Capacity Edge Hunter — exploits structural advantage of small size.

Giant funds don't care about edges with capacity < $1M.
You do.

Explicitly hunts:
- Low capacity
- High turnover
- Awkward instrument
- Odd time window
- Small market inefficiency
- Broker-specific anomaly
- Rare event
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

LOWCAP_DIR = DATA_DIR / "low_capacity_edges"
LOWCAP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CapacityEstimate:
    """Capacity estimate for a strategy."""
    strategy_id: str
    symbol: str
    avg_daily_volume: float                    # lots
    avg_spread_bps: float
    slippage_model: dict                       # size -> expected slippage
    max_size_before_impact: float              # lots
    max_daily_turnover: float                  # lots/day
    capacity_category: str                     # "micro", "small", "medium", "large", "institutional"
    broker_specific: bool = False


@dataclass
class LowCapSignal:
    """Signal from a low-capacity edge."""
    strategy_id: str
    symbol: str
    timestamp: datetime
    signal_type: str
    direction: int
    strength: float
    expected_horizon: str
    capacity_estimate: CapacityEstimate
    context: dict
    subsequent_outcome: dict | None = None


class LowCapacityHunter:
    """Hunts edges too small for institutions."""

    def __init__(self):
        self.capacity_estimates: dict[str, CapacityEstimate] = {}
        self.signals: list[LowCapSignal] = []

    def estimate_capacity(self, symbol: str, price_data: pd.DataFrame,
                           broker_data: dict | None = None) -> CapacityEstimate:
        """Estimate capacity for a symbol/strategy."""
        # Volume
        vol = price_data["tick_volume"].mean() if "tick_volume" in price_data.columns else 100
        daily_vol = vol * 24 * 60  # rough daily ticks

        # Spread
        spread_bps = (price_data["spread"].mean() / price_data["close"].mean()) * 10000 if "spread" in price_data.columns else 2.0

        # Slippage model (simplified)
        slippage_model = {
            0.01: spread_bps * 0.1,
            0.1: spread_bps * 0.3,
            1.0: spread_bps * 1.0,
            10.0: spread_bps * 3.0,
        }

        # Max size before impact (simplified: 1% of daily volume)
        max_size = daily_vol * 0.01

        # Broker-specific?
        broker_specific = broker_data is not None

        # Category
        if max_size < 10:
            cat = "micro"
        elif max_size < 100:
            cat = "small"
        elif max_size < 1000:
            cat = "medium"
        elif max_size < 10000:
            cat = "large"
        else:
            cat = "institutional"

        return CapacityEstimate(
            strategy_id=f"cap_{symbol}",
            symbol=symbol,
            avg_daily_volume=daily_vol,
            avg_spread_bps=spread_bps,
            slippage_model=slippage_model,
            max_size_before_impact=max_size,
            max_daily_turnover=daily_vol,
            capacity_category=cat,
            broker_specific=broker_specific,
        )

    def hunt_micro_edges(self, symbols: list[str],
                          price_data: dict[str, pd.DataFrame],
                          broker_data: dict | None = None) -> list[CapacityEstimate]:
        """Hunt for micro-capacity edges."""
        estimates = []
        for sym in symbols:
            if sym in price_data:
                est = self.estimate_capacity(sym, price_data[sym], broker_data)
                if est.capacity_category in ["micro", "small"]:
                    estimates.append(est)
                    self.capacity_estimates[sym] = est
        return estimates

    def hunt_awkward_instruments(self, symbols: list[str]) -> list[str]:
        """Find instruments institutions avoid."""
        awkward = []
        for sym in symbols:
            # Exotic crosses, minor pairs, CFD-only instruments
            if any(x in sym for x in ["ZAR", "TRY", "HUF", "PLN", "CZK", "RON", "BGN", "HRK"]):
                awkward.append(sym)
            # CFD-only indices
            if sym in ["US2000", "VIX", "US30", "USTEC", "EU50", "DE40", "FR40", "ES35"]:
                awkward.append(sym)
            # Commodities with physical delivery complexity
            if sym in ["XNGUSD", "XCUUSD", "XALUSD", "XPDUSD", "XPTUSD"]:
                awkward.append(sym)
        return awkward

    def hunt_odd_time_windows(self) -> list[dict]:
        """Time windows institutions ignore."""
        return [
            {"name": "sunday_open", "window": "22:00-23:00 UTC", "reason": "weekend gap resolution"},
            {"name": "tokyo_lunch", "window": "02:00-04:00 UTC", "reason": "liquidity vacuum"},
            {"name": "london_lunch", "window": "12:00-13:30 UTC", "reason": "desk rotation"},
            {"name": "ny_lunch", "window": "17:00-18:00 UTC", "reason": "volume dip"},
            {"name": "pre_comex", "window": "11:30-12:20 UTC", "reason": "pre-open positioning"},
            {"name": "post_ny_close", "window": "21:00-22:00 UTC", "reason": "MOC imbalance unwind"},
            {"name": "roll_week_wed", "window": "all_day", "reason": "calendar spread distortion"},
            {"name": "triple_swap_wed", "window": "22:00-23:00 UTC", "reason": "carry distortion"},
        ]

    def hunt_broker_anomalies(self, broker_data: dict) -> list[dict]:
        """Broker-specific anomalies institutions can't access."""
        anomalies = []
        # Freeze level changes
        # Stop level changes
        # Spread widening patterns
        # Execution latency patterns
        # Quote pause patterns
        # Requires broker_data collection
        return anomalies

    def hunt_rare_events(self) -> list[dict]:
        """Rare events institutions can't model."""
        return [
            {"name": "flash_crash_recovery", "frequency": "years", "edge": "liquidity provision"},
            {"name": "central_bank_surprise_intervention", "frequency": "years", "edge": "directional + vol"},
            {"name": "exchange_halt_circuit_breaker", "frequency": "months", "edge": "gap trading"},
            {"name": "symbol_rebranding_migration", "frequency": "years", "edge": "arb"},
            {"name": "contract_spec_change", "frequency": "years", "edge": "basis shift"},
        ]

    def generate_low_cap_signals(self, symbols: list[str],
                                  price_data: dict[str, pd.DataFrame]) -> list[LowCapSignal]:
        """Generate signals for low-capacity edges."""
        signals = []

        # Micro capacity edges
        estimates = self.hunt_micro_edges(symbols, price_data)
        for est in estimates:
            # Simple momentum signal for micro edge
            if est.symbol in price_data:
                df = price_data[est.symbol]
                ret_1h = df["close"].pct_change(60).iloc[-1] if len(df) > 60 else 0
                if abs(ret_1h) > 0.001:
                    signals.append(LowCapSignal(
                        strategy_id=f"micro_momentum_{est.symbol}",
                        symbol=est.symbol,
                        timestamp=datetime.now(UTC),
                        signal_type="micro_capacity_momentum",
                        direction=1 if ret_1h > 0 else -1,
                        strength=min(abs(ret_1h) * 100, 1.0),
                        expected_horizon="1h_to_4h",
                        capacity_estimate=est,
                        context={"momentum_1h": ret_1h, "capacity": est.capacity_category}
                    ))

        # Awkward instruments
        awkward = self.hunt_awkward_instruments(symbols)
        for sym in awkward:
            if sym in price_data:
                df = price_data[sym]
                # Simple mean reversion on awkward instruments
                ret_24h = df["close"].pct_change(24*60).iloc[-1] if len(df) > 24*60 else 0
                if abs(ret_24h) > 0.005:
                    signals.append(LowCapSignal(
                        strategy_id=f"awkward_reversion_{sym}",
                        symbol=sym,
                        timestamp=datetime.now(UTC),
                        signal_type="awkward_instrument_reversion",
                        direction=-1 if ret_24h > 0 else 1,
                        strength=0.6,
                        expected_horizon="4h_to_1d",
                        capacity_estimate=self.capacity_estimates.get(sym, CapacityEstimate(
                            strategy_id="", symbol=sym, avg_daily_volume=0, avg_spread_bps=0,
                            slippage_model={}, max_size_before_impact=1, max_daily_turnover=0,
                            capacity_category="micro"
                        )),
                        context={"ret_24h": ret_24h}
                    ))

        # Odd time windows
        now = datetime.now(UTC)
        odd_windows = self.hunt_odd_time_windows()
        for ow in odd_windows:
            # Check if we're in the window
            # Simplified: just flag the window
            signals.append(LowCapSignal(
                strategy_id=f"odd_window_{ow['name']}",
                symbol="ALL",
                timestamp=now,
                signal_type="odd_time_window",
                direction=0,  # No directional bias
                strength=0.5,
                expected_horizon=ow["window"],
                capacity_estimate=CapacityEstimate(
                    strategy_id="", symbol="ALL", avg_daily_volume=0, avg_spread_bps=0,
                    slippage_model={}, max_size_before_impact=0, max_daily_turnover=0,
                    capacity_category="micro"
                ),
                context=ow
            ))

        self.signals.extend(signals)
        return signals

    def record_outcome(self, signal: LowCapSignal, outcome: dict) -> None:
        signal.subsequent_outcome = outcome

    def generate_hypotheses(self, min_signals: int = 5) -> list[SideChannelHypothesis]:
        """Generate hypotheses from low-cap signals."""
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
                    axis=SideChannelAxis.MICROSTRUCTURE,
                    source="low_capacity_hunter",
                    mechanism=f"Low-capacity edge: {example.signal_type} on {example.symbol}. "
                              f"Capacity: {example.capacity_estimate.capacity_category} "
                              f"(max size {example.capacity_estimate.max_size_before_impact:.0f} lots). "
                              f"Too small for institutions. "
                              f"Avg return {np.mean(returns):.3f}R over {len(returns)} trades.",
                    symbols=[example.symbol] if example.symbol != "ALL" else [],
                    timing={
                        "signal_type": example.signal_type,
                        "capacity": example.capacity_estimate.capacity_category,
                    },
                    falsifier=f"Avg return drops below 0 over 30+ occurrences",
                    expected_horizon=example.expected_horizon,
                    capacity_estimate="micro",
                    metadata={
                        "signal_type": example.signal_type,
                        "symbol": example.symbol,
                        "capacity_category": example.capacity_estimate.capacity_category,
                        "max_size_lots": example.capacity_estimate.max_size_before_impact,
                        "avg_return_r": float(np.mean(returns)),
                        "sample_size": len(signals),
                    }
                )
                hypotheses.append(h)
                save_hypothesis(h)

        return hypotheses

    def save(self) -> None:
        import json
        with open(LOWCAP_DIR / "capacity_estimates.json", "w") as f:
            json.dump({k: {
                "symbol": v.symbol,
                "avg_daily_volume": v.avg_daily_volume,
                "avg_spread_bps": v.avg_spread_bps,
                "max_size_before_impact": v.max_size_before_impact,
                "capacity_category": v.capacity_category,
                "broker_specific": v.broker_specific,
            } for k, v in self.capacity_estimates.items()}, f, indent=2)

        with open(LOWCAP_DIR / "signals.json", "w") as f:
            json.dump([{
                "strategy_id": s.strategy_id,
                "symbol": s.symbol,
                "timestamp": s.timestamp.isoformat(),
                "signal_type": s.signal_type,
                "direction": s.direction,
                "strength": s.strength,
                "horizon": s.expected_horizon,
                "capacity_category": s.capacity_estimate.capacity_category,
                "context": s.context,
                "subsequent_outcome": s.subsequent_outcome,
            } for s in self.signals], f, indent=2, default=str)


if __name__ == "__main__":
    hunter = LowCapacityHunter()

    # Test with synthetic data
    dates = pd.date_range("2026-01-01", periods=10000, freq="1min", tz=UTC)
    np.random.seed(42)
    base = np.cumsum(np.random.randn(10000) * 0.0001)

    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "USDCAD", "USDNOK", "USDTRY", "US30", "USTEC", "XNGUSD"]
    price_data = {}
    for sym in symbols:
        price_data[sym] = pd.DataFrame({
            "open": 100 + np.cumsum(np.random.randn(10000) * 0.0002),
            "high": 0, "low": 0, "close": 0,
            "tick_volume": np.random.randint(50, 500, 10000),
            "spread": np.abs(np.random.randn(10000) * 0.5) + 1.0,
        }, index=dates)
        price_data[sym]["high"] = price_data[sym]["open"] + np.abs(np.random.randn(10000) * 0.5)
        price_data[sym]["low"] = price_data[sym]["open"] - np.abs(np.random.randn(10000) * 0.5)
        price_data[sym]["close"] = price_data[sym]["open"] + np.random.randn(10000) * 0.3

    estimates = hunter.hunt_micro_edges(symbols, price_data)
    print(f"Found {len(estimates)} micro-capacity edges:")
    for e in estimates:
        print(f"  {e.symbol}: {e.capacity_category}, max_size={e.max_size_before_impact:.0f} lots")

    awkward = hunter.hunt_awkward_instruments(symbols)
    print(f"\nAwkward instruments: {awkward}")

    signals = hunter.generate_low_cap_signals(symbols, price_data)
    print(f"\nGenerated {len(signals)} low-cap signals")

    hyps = hunter.generate_hypotheses(min_signals=1)
    print(f"Generated {len(hyps)} low-cap hypotheses")