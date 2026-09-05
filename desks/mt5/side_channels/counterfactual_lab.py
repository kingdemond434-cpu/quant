"""Live Counterfactual Laboratory — records alternative executions for every signal.

For every live/shadow signal, records what would have happened under:
- market order immediately
- stop order (current default)
- pullback limit
- wait 1m / 5m / 15m
- partial + runner
- tighter/wider stop
- re-entry after stop
- no-trade control

Builds proprietary dataset answering HOW each edge should actually be harvested.
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
class ExecutionPolicy:
    """An execution policy variant."""
    name: str
    entry_type: Literal["market", "stop", "limit_pullback", "delayed", "partial"]
    entry_params: dict                            # e.g., {"pullback_pct": 0.3, "delay_min": 5}
    stop_type: Literal["atr", "fixed", "trail", "none"]
    stop_params: dict                             # e.g., {"atr_mult": 1.5}
    trail_params: dict | None = None              # e.g., {"atr_mult": 0.5}
    re_entry: bool = False
    re_entry_params: dict | None = None
    position_scaling: Literal["full", "half", "quarter", "pyramid"] = "full"
    max_hold_bars: int | None = None


# Canonical execution policies to test
CANONICAL_POLICIES = [
    ExecutionPolicy(
        name="market_immediate",
        entry_type="market",
        entry_params={},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="stop_order_default",
        entry_type="stop",
        entry_params={"breakout_buffer": 0.0},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="pullback_limit_30",
        entry_type="limit_pullback",
        entry_params={"pullback_pct": 0.3, "limit_buffer_pips": 2},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="pullback_limit_50",
        entry_type="limit_pullback",
        entry_params={"pullback_pct": 0.5, "limit_buffer_pips": 2},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="delayed_1m",
        entry_type="delayed",
        entry_params={"delay_min": 1, "confirmation": "close_above_signal"},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="delayed_5m",
        entry_type="delayed",
        entry_params={"delay_min": 5, "confirmation": "close_above_signal"},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="delayed_15m",
        entry_type="delayed",
        entry_params={"delay_min": 15, "confirmation": "close_above_signal"},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
    ),
    ExecutionPolicy(
        name="partial_half_runner",
        entry_type="partial",
        entry_params={"first_leg_pct": 0.5, "second_leg_trigger": "1R_profit"},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
        trail_params={"atr_mult": 0.5},
    ),
    ExecutionPolicy(
        name="tighter_stop_1x",
        entry_type="stop",
        entry_params={"breakout_buffer": 0.0},
        stop_type="atr",
        stop_params={"atr_mult": 1.0},
    ),
    ExecutionPolicy(
        name="wider_stop_2x",
        entry_type="stop",
        entry_params={"breakout_buffer": 0.0},
        stop_type="atr",
        stop_params={"atr_mult": 2.0},
    ),
    ExecutionPolicy(
        name="reentry_after_stop",
        entry_type="stop",
        entry_params={"breakout_buffer": 0.0},
        stop_type="atr",
        stop_params={"atr_mult": 1.5},
        re_entry=True,
        re_entry_params={"max_reentries": 2, "cooldown_bars": 3},
    ),
    ExecutionPolicy(
        name="no_trade_control",
        entry_type="market",
        entry_params={},
        stop_type="none",
        stop_params={},
    ),
]


@dataclass
class SignalRecord:
    """A signal with its counterfactual outcomes."""
    signal_id: str
    strategy_id: str
    symbol: str
    timestamp: datetime
    signal_direction: int                       # +1 long, -1 short
    signal_strength: float
    signal_price: float                         # price at signal generation
    market_state: dict                          # spread, vol, session, regime, etc.
    canonical_outcomes: dict[str, dict]         # policy_name -> outcome
    best_policy: str | None = None
    worst_policy: str | None = None
    policy_spread_bps: float = 0.0              # best - worst in bps
    metadata: dict = field(default_factory=dict)


@dataclass
class CounterfactualOutcome:
    """Outcome of one execution policy."""
    policy_name: str
    filled: bool
    fill_price: float | None = None
    fill_time: datetime | None = None
    exit_price: float | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None              # "tp", "sl", "trail", "time", "reentry", "no_fill"
    r_multiple: float = 0.0
    max_favorable: float = 0.0                  # MFE in R
    max_adverse: float = 0.0                    # MAE in R
    time_to_fill: float | None = None           # seconds
    time_to_exit: float | None = None           # seconds
    slippage_bps: float = 0.0
    commission_bps: float = 0.0
    partial_fills: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class CounterfactualLab:
    """Runs counterfactual execution simulation for every signal."""
    
    def __init__(self, base_path: Path, policies: list[ExecutionPolicy] = None):
        self.base_path = base_path
        self.policies = policies or CANONICAL_POLICIES
        self.lab_dir = base_path / "data" / "counterfactual_lab"
        self.lab_dir.mkdir(parents=True, exist_ok=True)
        
        self.signals_file = self.lab_dir / "signals.jsonl"
        self.outcomes_file = self.lab_dir / "outcomes.jsonl"
        self.analytics_file = self.lab_dir / "analytics.json"
        
        self.signals_buffer: list[SignalRecord] = []
        self.max_buffer = 1000
    
    def record_signal(self, signal: dict, market_state: dict) -> str:
        """Record a new signal for counterfactual evaluation."""
        signal_id = f"SIG-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{hashlib.md5(json.dumps(signal).encode()).hexdigest()[:6]}"
        
        # Extract signal info
        record = SignalRecord(
            signal_id=signal_id,
            strategy_id=signal.get("strategy_id", "unknown"),
            symbol=signal.get("symbol", "UNKNOWN"),
            timestamp=datetime.now(UTC),
            signal_direction=signal.get("direction", 0),
            signal_strength=signal.get("strength", 1.0),
            signal_price=signal.get("price", 0.0),
            market_state=market_state,
            canonical_outcomes={},
        )
        
        self.signals_buffer.append(record)
        
        # Flush if buffer full
        if len(self.signals_buffer) >= self.max_buffer:
            self._flush_buffer()
        
        return signal_id
    
    def evaluate_counterfactuals(self, signal_id: str, 
                                  price_data: pd.DataFrame,
                                  signal_info: dict) -> dict[str, CounterfactualOutcome]:
        """Run all counterfactual policies for a signal."""
        outcomes = {}
        
        for policy in self.policies:
            outcome = self._simulate_policy(policy, price_data, signal_info)
            outcomes[policy.name] = outcome
        
        return outcomes
    
    def _simulate_policy(self, policy: ExecutionPolicy, 
                          price_data: pd.DataFrame,
                          signal_info: dict) -> CounterfactualOutcome:
        """Simulate one execution policy on historical price data."""
        signal_time = signal_info.get("timestamp", price_data.index[0])
        direction = signal_info.get("direction", 1)
        signal_price = signal_info.get("price", price_data["close"].iloc[0])
        
        # Find signal bar index
        try:
            idx = price_data.index.get_loc(signal_time)
        except KeyError:
            # Nearest
            idx = price_data.index.get_indexer([signal_time], method="nearest")[0]
        
        if idx >= len(price_data) - 1:
            return CounterfactualOutcome(
                policy_name=policy.name,
                filled=False,
                metadata={"error": "signal at end of data"},
            )
        
        # Simulate based on entry type
        if policy.entry_type == "market":
            return self._simulate_market(policy, price_data, idx, direction, signal_price)
        elif policy.entry_type == "stop":
            return self._simulate_stop(policy, price_data, idx, direction, signal_price)
        elif policy.entry_type == "limit_pullback":
            return self._simulate_limit_pullback(policy, price_data, idx, direction, signal_price)
        elif policy.entry_type == "delayed":
            return self._simulate_delayed(policy, price_data, idx, direction, signal_price)
        elif policy.entry_type == "partial":
            return self._simulate_partial(policy, price_data, idx, direction, signal_price)
        else:
            return CounterfactualOutcome(policy_name=policy.name, filled=False)
    
    def _simulate_market(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                          idx: int, direction: int, signal_price: float) -> CounterfactualOutcome:
        """Market order - fills at next open."""
        if idx + 1 >= len(price_data):
            return CounterfactualOutcome(policy_name=policy.name, filled=False)
        
        fill_price = price_data["open"].iloc[idx + 1]
        fill_time = price_data.index[idx + 1]
        
        # Apply slippage (half spread)
        spread = price_data["spread"].iloc[idx + 1] if "spread" in price_data.columns else 0
        slippage = spread / 2 * direction
        fill_price += slippage
        
        return self._run_trade_from_fill(policy, price_data, idx + 1, direction, fill_price, fill_time, signal_price)
    
    def _simulate_stop(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                        idx: int, direction: int, signal_price: float) -> CounterfactualOutcome:
        """Stop order - triggers when price breaks signal level."""
        # Find first bar where high/low breaks signal price
        for i in range(idx + 1, len(price_data)):
            high = price_data["high"].iloc[i]
            low = price_data["low"].iloc[i]
            
            if direction > 0 and high >= signal_price:
                # Long stop triggered
                fill_price = max(signal_price, price_data["open"].iloc[i])
                fill_time = price_data.index[i]
                return self._run_trade_from_fill(policy, price_data, i, direction, fill_price, fill_time, signal_price)
            elif direction < 0 and low <= signal_price:
                # Short stop triggered
                fill_price = min(signal_price, price_data["open"].iloc[i])
                fill_time = price_data.index[i]
                return self._run_trade_from_fill(policy, price_data, i, direction, fill_price, fill_time, signal_price)
        
        return CounterfactualOutcome(policy_name=policy.name, filled=False, metadata={"reason": "stop_never_triggered"})
    
    def _simulate_limit_pullback(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                                  idx: int, direction: int, signal_price: float) -> CounterfactualOutcome:
        """Limit order at pullback level."""
        pullback_pct = policy.entry_params.get("pullback_pct", 0.5)
        buffer_pips = policy.entry_params.get("limit_buffer_pips", 2)
        
        # Calculate pullback level
        if direction > 0:
            limit_price = signal_price * (1 - pullback_pct * 0.01)  # Simplified
        else:
            limit_price = signal_price * (1 + pullback_pct * 0.01)
        
        # Add buffer
        if direction > 0:
            limit_price -= buffer_pips * 0.0001
        else:
            limit_price += buffer_pips * 0.0001
        
        # Find fill
        for i in range(idx + 1, len(price_data)):
            low = price_data["low"].iloc[i]
            high = price_data["high"].iloc[i]
            
            if direction > 0 and low <= limit_price:
                fill_price = max(limit_price, price_data["open"].iloc[i])
                fill_time = price_data.index[i]
                return self._run_trade_from_fill(policy, price_data, i, direction, fill_price, fill_time, signal_price)
            elif direction < 0 and high >= limit_price:
                fill_price = min(limit_price, price_data["open"].iloc[i])
                fill_time = price_data.index[i]
                return self._run_trade_from_fill(policy, price_data, i, direction, fill_price, fill_time, signal_price)
        
        return CounterfactualOutcome(policy_name=policy.name, filled=False, metadata={"reason": "limit_never_filled"})
    
    def _simulate_delayed(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                           idx: int, direction: int, signal_price: float) -> CounterfactualOutcome:
        """Delayed entry with confirmation."""
        delay_min = policy.entry_params.get("delay_min", 5)
        confirmation = policy.entry_params.get("confirmation", "close_above_signal")
        
        # Calculate delay in bars (assuming H1 data)
        delay_bars = delay_min // 60
        if delay_bars == 0:
            delay_bars = 1
        
        fill_idx = idx + delay_bars
        if fill_idx >= len(price_data):
            return CounterfactualOutcome(policy_name=policy.name, filled=False)
        
        # Check confirmation
        if confirmation == "close_above_signal":
            if direction > 0 and price_data["close"].iloc[fill_idx] < signal_price:
                return CounterfactualOutcome(policy_name=policy.name, filled=False, metadata={"reason": "confirmation_failed"})
            if direction < 0 and price_data["close"].iloc[fill_idx] > signal_price:
                return CounterfactualOutcome(policy_name=policy.name, filled=False, metadata={"reason": "confirmation_failed"})
        
        fill_price = price_data["open"].iloc[fill_idx]
        fill_time = price_data.index[fill_idx]
        
        return self._run_trade_from_fill(policy, price_data, fill_idx, direction, fill_price, fill_time, signal_price)
    
    def _simulate_partial(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                           idx: int, direction: int, signal_price: float) -> CounterfactualOutcome:
        """Partial entry with runner."""
        first_leg = policy.entry_params.get("first_leg_pct", 0.5)
        second_trigger = policy.entry_params.get("second_leg_trigger", "1R_profit")
        
        # First leg - market order
        if idx + 1 >= len(price_data):
            return CounterfactualOutcome(policy_name=policy.name, filled=False)
        
        fill_price = price_data["open"].iloc[idx + 1]
        fill_time = price_data.index[idx + 1]
        
        # Run first leg
        result = self._run_trade_from_fill(policy, price_data, idx + 1, direction, fill_price, fill_time, signal_price)
        result.metadata["first_leg_pct"] = first_leg
        result.metadata["second_trigger"] = second_trigger
        result.policy_name = policy.name
        
        return result
    
    def _run_trade_from_fill(self, policy: ExecutionPolicy, price_data: pd.DataFrame,
                              fill_idx: int, direction: int, fill_price: float,
                              fill_time: datetime, signal_price: float) -> CounterfactualOutcome:
        """Run trade management from fill to exit."""
        # Calculate stop
        atr_mult = policy.stop_params.get("atr_mult", 1.5)
        atr = self._compute_atr(price_data, fill_idx)
        stop_dist = atr * atr_mult
        
        if direction > 0:
            stop_price = fill_price - stop_dist
        else:
            stop_price = fill_price + stop_dist
        
        # Trail parameters
        trail_dist = None
        if policy.trail_params:
            trail_atr_mult = policy.trail_params.get("atr_mult", 0.5)
            trail_dist = atr * trail_atr_mult
        
        # Run forward
        max_fav = 0.0
        max_adv = 0.0
        exit_price = fill_price
        exit_time = fill_time
        exit_reason = "time"
        reentries = 0
        max_reentries = policy.re_entry_params.get("max_reentries", 2) if policy.re_entry else 0
        cooldown = policy.re_entry_params.get("cooldown_bars", 3) if policy.re_entry else 0
        last_exit_idx = fill_idx
        
        for i in range(fill_idx + 1, len(price_data)):
            high = price_data["high"].iloc[i]
            low = price_data["low"].iloc[i]
            close = price_data["close"].iloc[i]
            
            if direction > 0:
                # Long
                fav = (high - fill_price) / (fill_price - stop_price) if fill_price != stop_price else 0
                adv = (fill_price - low) / (fill_price - stop_price) if fill_price != stop_price else 0
                
                # Check stop
                if low <= stop_price:
                    exit_price = stop_price
                    exit_time = price_data.index[i]
                    exit_reason = "sl"
                    break
                
                # Check trail
                if trail_dist and high > fill_price:
                    new_stop = high - trail_dist
                    if new_stop > stop_price:
                        stop_price = new_stop
                
                max_fav = max(max_fav, fav)
                max_adv = max(max_adv, adv)
                
            else:
                # Short
                fav = (fill_price - low) / (stop_price - fill_price) if stop_price != fill_price else 0
                adv = (high - fill_price) / (stop_price - fill_price) if stop_price != fill_price else 0
                
                if high >= stop_price:
                    exit_price = stop_price
                    exit_time = price_data.index[i]
                    exit_reason = "sl"
                    break
                
                if trail_dist and low < fill_price:
                    new_stop = low + trail_dist
                    if new_stop < stop_price:
                        stop_price = new_stop
                
                max_fav = max(max_fav, fav)
                max_adv = max(max_adv, adv)
            
            # Time-based exit
            if policy.max_hold_bars and (i - fill_idx) >= policy.max_hold_bars:
                exit_price = close
                exit_time = price_data.index[i]
                exit_reason = "time"
                break
            
            # Re-entry logic
            if policy.re_entry and exit_reason == "sl" and reentries < max_reentries:
                if (i - last_exit_idx) >= cooldown:
                    # Re-enter in same direction
                    reentries += 1
                    last_exit_idx = i
                    fill_idx = i
                    fill_price = price_data["open"].iloc[i + 1] if i + 1 < len(price_data) else close
                    fill_time = price_data.index[i + 1] if i + 1 < len(price_data) else price_data.index[i]
                    stop_price = fill_price - stop_dist if direction > 0 else fill_price + stop_dist
                    continue
        
        # Calculate R multiple
        if direction > 0:
            r_multiple = (exit_price - fill_price) / (fill_price - stop_price) if fill_price != stop_price else 0
        else:
            r_multiple = (fill_price - exit_price) / (stop_price - fill_price) if stop_price != fill_price else 0
        
        # Slippage and commission
        slippage_bps = 0  # Would compute from actual fills
        commission_bps = 3.5  # Typical round-trip
        
        return CounterfactualOutcome(
            policy_name=policy.name,
            filled=True,
            fill_price=fill_price,
            fill_time=fill_time,
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
            r_multiple=r_multiple,
            max_favorable=max_fav,
            max_adverse=max_adv,
            time_to_fill=(fill_time - price_data.index[fill_idx]).total_seconds() / 60,
            time_to_exit=(exit_time - fill_time).total_seconds() / 60 if exit_time else None,
            slippage_bps=slippage_bps,
            commission_bps=commission_bps,
            metadata={"direction": direction, "stop_price": stop_price, "trail_dist": trail_dist},
        )
    
    def _compute_atr(self, price_data: pd.DataFrame, idx: int, period: int = 14) -> float:
        """Compute ATR at index."""
        if idx < period:
            return 0.001  # Default
        
        high = price_data["high"].iloc[idx-period:idx]
        low = price_data["low"].iloc[idx-period:idx]
        close = price_data["close"].iloc[idx-period:idx]
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return float(tr.iloc[-period:].mean())
    
    def finalize_signal(self, signal_id: str, outcomes: dict[str, CounterfactualOutcome]) -> None:
        """Finalize a signal with its counterfactual outcomes."""
        # Find signal in buffer
        signal = None
        for s in self.signals_buffer:
            if s.signal_id == signal_id:
                signal = s
                break
        
        if not signal:
            return
        
        signal.canonical_outcomes = {
            name: {
                "filled": o.filled,
                "fill_price": o.fill_price,
                "exit_price": o.exit_price,
                "r_multiple": o.r_multiple,
                "max_favorable": o.max_favorable,
                "max_adverse": o.max_adverse,
                "exit_reason": o.exit_reason,
                "slippage_bps": o.slippage_bps,
            }
            for name, o in outcomes.items()
        }
        
        # Find best and worst policies
        filled_outcomes = {k: v for k, v in outcomes.items() if v.filled}
        if filled_outcomes:
            signal.best_policy = max(filled_outcomes.keys(), key=lambda k: filled_outcomes[k].r_multiple)
            signal.worst_policy = min(filled_outcomes.keys(), key=lambda k: filled_outcomes[k].r_multiple)
            signal.policy_spread_bps = (filled_outcomes[signal.best_policy].r_multiple - 
                                         filled_outcomes[signal.worst_policy].r_multiple) * 10000
        
        # Save signal
        self._save_signal(signal)
        self.signals_buffer.remove(signal)
    
    def _save_signal(self, signal: SignalRecord) -> None:
        """Save signal to disk."""
        with open(self.signals_file, "a") as f:
            f.write(json.dumps({
                "signal_id": signal.signal_id,
                "strategy_id": signal.strategy_id,
                "symbol": signal.symbol,
                "timestamp": signal.timestamp.isoformat(),
                "direction": signal.signal_direction,
                "strength": signal.signal_strength,
                "signal_price": signal.signal_price,
                "market_state": signal.market_state,
                "canonical_outcomes": signal.canonical_outcomes,
                "best_policy": signal.best_policy,
                "worst_policy": signal.worst_policy,
                "policy_spread_bps": signal.policy_spread_bps,
            }) + "\n")
    
    def _flush_buffer(self) -> None:
        """Flush buffer to disk."""
        for signal in self.signals_buffer:
            self._save_signal(signal)
        self.signals_buffer.clear()
    
    def compute_policy_analytics(self, min_signals: int = 50) -> dict:
        """Compute analytics across all signals."""
        # Load all signals
        signals = []
        if self.signals_file.exists():
            with open(self.signals_file, "r") as f:
                for line in f:
                    signals.append(json.loads(line))
        
        if len(signals) < min_signals:
            return {"error": f"Insufficient signals: {len(signals)} < {min_signals}"}
        
        # Aggregate by policy
        policy_stats = {}
        for s in signals:
            for policy, outcome in s.get("canonical_outcomes", {}).items():
                if policy not in policy_stats:
                    policy_stats[policy] = {"r_multiples": [], "filled": 0, "total": 0}
                
                policy_stats[policy]["total"] += 1
                if outcome.get("filled", False):
                    policy_stats[policy]["filled"] += 1
                    policy_stats[policy]["r_multiples"].append(outcome.get("r_multiple", 0))
        
        # Compute stats
        analytics = {}
        for policy, stats in policy_stats.items():
            if stats["r_multiples"]:
                r = np.array(stats["r_multiples"])
                analytics[policy] = {
                    "fill_rate": stats["filled"] / stats["total"],
                    "avg_r": float(np.mean(r)),
                    "sharpe": float(np.mean(r) / (np.std(r) + 1e-12)) if len(r) > 1 else 0,
                    "win_rate": float(np.mean(r > 0)),
                    "avg_max_favorable": 0,  # Would need full outcomes
                    "avg_max_adverse": 0,
                    "n_signals": stats["total"],
                    "n_filled": stats["filled"],
                }
        
        # Find best policy overall
        if analytics:
            best = max(analytics.items(), key=lambda x: x[1]["avg_r"])
            analytics["_best_policy"] = best[0]
            analytics["_worst_policy"] = min(analytics.items(), key=lambda x: x[1]["avg_r"])[0]
        
        # Save analytics
        with open(self.analytics_file, "w") as f:
            json.dump(analytics, f, indent=2, default=str)
        
        return analytics


def hashlib_md5(data: str) -> str:
    return hashlib.md5(data.encode()).hexdigest()


import hashlib


def run_counterfactual_analysis(base_path: Path, symbol: str = "XAUUSD", 
                                 lookback_days: int = 30) -> dict:
    """Run counterfactual analysis on historical signals."""
    lab = CounterfactualLab(base_path)
    
    # Load historical signals from shadow ledger
    shadow_dir = base_path / "desks" / "mt5" / "reports" / "shadow"
    ledger_files = list(shadow_dir.glob(f"ledger_{symbol}_*.json"))
    
    all_signals = []
    for f in ledger_files:
        with open(f, "r") as f:
            trades = json.load(f)
        for t in trades:
            all_signals.append({
                "signal_id": t.get("entry_time", ""),
                "strategy_id": f.name,
                "symbol": symbol,
                "timestamp": t["entry_time"],
                "direction": 1 if t["side"] == "LONG" else -1,
                "strength": 1.0,
                "price": t["entry"],
            })
    
    # Filter to lookback
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    recent_signals = [s for s in all_signals 
                      if datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00")) >= cutoff]
    
    print(f"Running counterfactuals on {len(recent_signals)} signals...")
    
    # Load price data
    price_path = base_path / "desks" / "mt5" / "data" / "universe" / f"{symbol}_H1.parquet"
    price_data = pd.read_parquet(price_path)
    
    # Run counterfactuals
    results = {}
    for i, sig in enumerate(recent_signals):
        if i % 50 == 0:
            print(f"  {i}/{len(recent_signals)}")
        
        outcomes = lab.evaluate_counterfactuals(sig["signal_id"], price_data, sig)
        results[sig["signal_id"]] = {
            "signal": sig,
            "outcomes": {k: v.__dict__ for k, v in outcomes.items()},
        }
    
    # Save results
    out_file = lab.lab_dir / f"counterfactual_{symbol}_{lookback_days}d.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    # Compute analytics
    analytics = lab.compute_policy_analytics()
    
    print(f"\nPolicy Analytics:")
    for policy, stats in analytics.items():
        if policy.startswith("_"):
            continue
        print(f"  {policy}: fill={stats['fill_rate']:.2%}, avg_R={stats['avg_r']:.3f}, "
              f"Sharpe={stats['sharpe']:.2f}, win={stats['win_rate']:.2%}")
    
    if "_best_policy" in analytics:
        print(f"\nBest policy: {analytics['_best_policy']}")
        print(f"Worst policy: {analytics['_worst_policy']}")
    
    return analytics


if __name__ == "__main__":
    base = Path("/home/quant/quant-platform")
    run_counterfactual_analysis(base, "XAUUSD", 30)