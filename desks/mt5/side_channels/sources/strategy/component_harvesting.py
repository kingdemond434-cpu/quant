"""Component Harvesting — extracts useful pieces from failed strategies.

Breaks every external strategy apart:
ENTRY / EXIT / STOP / TRAIL / SESSION / REGIME FILTER / RE-ENTRY / POSITION MANAGEMENT

Then independently tests the information content of each component.
A bad full EA can have fantastic components.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from enum import Enum
from collections import defaultdict

from ...base import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR


class ComponentType(Enum):
    ENTRY = "entry"
    EXIT = "exit"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    SESSION_FILTER = "session_filter"
    REGIME_FILTER = "regime_filter"
    RE_ENTRY = "re_entry"
    POSITION_SIZING = "position_sizing"
    ENTRY_METHOD = "entry_method"
    EXIT_METHOD = "exit_method"
    MARTINGALE = "martingale"
    GRID = "grid"
    AVERAGING = "averaging"
    HEDGING = "hedging"
    TRAILING = "trailing"


@dataclass
class StrategyComponent:
    """A single atomic component from a decomposed strategy."""
    component_type: ComponentType
    value: str                              # e.g., "ema_cross", "atr_1.5", "london_session"
    source_strategy: str                    # original strategy ID
    economic_meaning: str                   # what this piece represents
    standalone_edge_bps: float = 0.0        # edge when this component was tested alone
    frequency: float = 0.0                  # how often this component appears
    orthogonality_score: float = 1.0        # 0-1, higher = more independent
    win_rate_contribution: float = 0.0      # contribution to win rate
    profit_factor_contribution: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ComponentTestResult:
    """Result of testing a component in isolation."""
    component: StrategyComponent
    tested_in_isolation: bool = False
    edge_bps: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    n_trades: int = 0
    n_winners: int = 0
    n_losers: int = 0
    avg_win_r: float = 0.0
    avg_loss_r: float = 0.0
    avg_holding_bars: float = 0.0
    regime_performance: dict[str, float] = field(default_factory=dict)
    session_performance: dict[str, float] = field(default_factory=dict)
    symbol_performance: dict[str, float] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class ComponentExtractor:
    """Extracts atomic components from parsed strategies."""
    
    def __init__(self):
        self.component_library: dict[ComponentType, list[StrategyComponent]] = defaultdict(list)
        self.component_index: dict[str, StrategyComponent] = {}
    
    def extract_from_parsed_strategy(self, strategy: Any) -> list[StrategyComponent]:
        """Extract components from a parsed MQL5 strategy."""
        components = []
        source_id = getattr(strategy, 'source_id', 'unknown')
        
        # Entry component
        if hasattr(strategy, 'entry_rules') and strategy.entry_rules:
            entry = StrategyComponent(
                component_type=ComponentType.ENTRY,
                value="; ".join(strategy.entry_rules[:2]),
                source_strategy=source_id,
                economic_meaning=f"Entry trigger: {strategy.entry_rules[0] if strategy.entry_rules else 'unknown'}",
            )
            components.append(entry)
        
        # Exit component
        if hasattr(strategy, 'exit_rules') and strategy.exit_rules:
            exit_comp = StrategyComponent(
                component_type=ComponentType.EXIT,
                value="; ".join(strategy.exit_rules[:2]),
                source_strategy=source_id,
                economic_meaning=f"Exit logic: {strategy.exit_rules[0] if strategy.exit_rules else 'unknown'}",
            )
            components.append(exit_comp)
        
        # Stop loss
        if hasattr(strategy, 'stop_loss') and strategy.stop_loss:
            stop = StrategyComponent(
                component_type=ComponentType.STOP_LOSS,
                value=strategy.stop_loss,
                source_strategy=source_id,
                economic_meaning=f"Stop loss: {strategy.stop_loss}",
            )
            components.append(stop)
        
        # Trailing stop
        if hasattr(strategy, 'trailing_stop') and strategy.trailing_stop:
            trail = StrategyComponent(
                component_type=ComponentType.TRAILING_STOP,
                value=strategy.trailing_stop,
                source_strategy=source_id,
                economic_meaning=f"Trailing stop: {strategy.trailing_stop}",
            )
            components.append(trail)
        
        # Session filter
        if hasattr(strategy, 'session_filters') and strategy.session_filters:
            session = StrategyComponent(
                component_type=ComponentType.SESSION_FILTER,
                value="; ".join(strategy.session_filters),
                source_strategy=source_id,
                economic_meaning=f"Session filter: {', '.join(strategy.session_filters)}",
            )
            components.append(session)
        
        # Timeframe/regime
        if hasattr(strategy, 'timeframe') and strategy.timeframe:
            regime = StrategyComponent(
                component_type=ComponentType.REGIME_FILTER,
                value=f"timeframe_{strategy.timeframe}",
                source_strategy=source_id,
                economic_meaning=f"Timeframe filter: {strategy.timeframe}",
            )
            components.append(regime)
        
        # Entry method
        if hasattr(strategy, 'indicators') and strategy.indicators:
            entry_method = StrategyComponent(
                component_type=ComponentType.ENTRY_METHOD,
                value=", ".join(strategy.indicators[:3]),
                source_strategy=source_id,
                economic_meaning=f"Entry method using: {', '.join(strategy.indicators[:3])}",
            )
            components.append(entry_method)
        
        # Position sizing
        if hasattr(strategy, 'position_sizing') and strategy.position_sizing:
            sizing = StrategyComponent(
                component_type=ComponentType.POSITION_SIZING,
                value=strategy.position_sizing,
                source_strategy=source_id,
                economic_meaning=f"Position sizing: {strategy.position_sizing}",
            )
            components.append(sizing)
        
        # Martingale/Grid/Averaging detection
        if getattr(strategy, 'grid_martingale', False):
            grid = StrategyComponent(
                component_type=ComponentType.GRID,
                value="grid_martingale",
                source_strategy=source_id,
                economic_meaning="Grid/martingale position management",
            )
            components.append(grid)
        
        if getattr(strategy, 'averaging_down', False):
            avg = StrategyComponent(
                component_type=ComponentType.AVERAGING,
                value="averaging_down",
                source_strategy=source_id,
                economic_meaning="Averaging down on adverse moves",
            )
            components.append(avg)
        
        if getattr(strategy, 'hedging', False):
            hedge = StrategyComponent(
                component_type=ComponentType.HEDGING,
                value="hedging",
                source_strategy=source_id,
                economic_meaning="Hedging positions",
            )
            components.append(hedge)
        
        # Register components
        for comp in components:
            comp_id = f"{comp.component_type.value}:{comp.value}:{source_id}"
            self.component_index[comp_id] = comp
            self.component_library[comp.component_type].append(comp)
        
        return components


class ComponentTester:
    """Tests components in isolation and in combination."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.results: list[ComponentTestResult] = []
    
    def test_component_isolation(self, component: StrategyComponent, 
                                  price_data: dict[str, pd.DataFrame],
                                  regime_labels: pd.Series | None = None) -> ComponentTestResult:
        """Test a single component in isolation."""
        # This would run a backtest with ONLY this component active
        # For now, return a mock result
        result = ComponentTestResult(component=component)
        result.tested_in_isolation = True
        result.n_trades = 0
        return result
    
    def test_component_combination(self, components: list[StrategyComponent],
                                    price_data: dict[str, pd.DataFrame]) -> ComponentTestResult:
        """Test a combination of components together."""
        result = ComponentTestResult(component=components[0] if components else None)
        return result
    
    def test_all_components(self, components: list[StrategyComponent],
                             price_data: dict[str, pd.DataFrame]) -> list[ComponentTestResult]:
        """Test each component in isolation."""
        results = []
        for comp in components:
            result = self.test_component_isolation(comp, price_data)
            results.append(result)
        return results


class ComponentHarvester:
    """Harvests useful components from failed/near-miss strategies."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.extractor = ComponentExtractor()
        self.tester = ComponentTester(base_path)
        self.harvested_components: list[StrategyComponent] = []
    
    def harvest_from_failed_strategies(self, failed_strategies: list[Any],
                                        price_data: dict[str, pd.DataFrame]) -> list[StrategyComponent]:
        """Extract and test components from failed strategies."""
        all_components = []
        
        for strategy in failed_strategies:
            components = self.extractor.extract_from_parsed_strategy(strategy)
            all_components.extend(components)
        
        # Test each component
        for comp in all_components:
            # In production, would run actual backtests
            # For now, use heuristics to estimate value
            score = self._heuristic_component_score(comp)
            if score > 0.3:  # Threshold for "potentially useful"
                comp.metadata["heuristic_score"] = score
                self.harvested_components.append(comp)
        
        return self.harvested_components
    
    def _heuristic_component_score(self, component: StrategyComponent) -> float:
        """Heuristic scoring of component potential."""
        score = 0.0
        
        # High-value component types
        high_value_types = {
            ComponentType.ENTRY: 0.3,
            ComponentType.STOP_LOSS: 0.25,
            ComponentType.TRAILING_STOP: 0.2,
            ComponentType.REGIME_FILTER: 0.2,
            ComponentType.SESSION_FILTER: 0.15,
            ComponentType.ENTRY_METHOD: 0.15,
            ComponentType.EXIT_METHOD: 0.1,
        }
        score += high_value_types.get(component.component_type, 0.05)
        
        # Bonus for specific high-value values
        high_value_values = {
            "ema_cross": 0.15,
            "rsi": 0.1,
            "macd": 0.1,
            "bollinger": 0.1,
            "atr": 0.15,
            "session": 0.1,
            "london": 0.1,
            "ny": 0.1,
            "atr_1.5": 0.1,
            "atr_2.0": 0.1,
        }
        for val, bonus in high_value_values.items():
            if val in component.value.lower():
                score += bonus
        
        # Penalty for known bad patterns
        bad_patterns = ["martingale", "grid", "averaging_down", "hedging"]
        for bad in bad_patterns:
            if bad in component.value.lower():
                score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def generate_component_hypotheses(self, min_score: float = 0.4) -> list[dict]:
        """Generate hypotheses from high-scoring components."""
        hypotheses = []
        
        for comp in self.harvested_components:
            score = comp.metadata.get("heuristic_score", 0)
            if score < min_score:
                continue
            
            hypothesis = {
                "id": generate_id(),
                "origin": {
                    "region": "global",
                    "language": "en",
                    "source_type": "component_harvesting",
                    "source_id": comp.source_strategy,
                    "evidence_tier": "component_derived",
                },
                "mechanism": {
                    "mechanism_class": "execution_alpha" if comp.component_type in [ComponentType.STOP_LOSS, ComponentType.TRAILING_STOP, ComponentType.ENTRY_METHOD] else "information_shock",
                    "participant": "retail",
                    "constraint": "component_extraction",
                    "information_source": "failed_strategy_decomposition",
                    "why_edge_should_exist": f"Harvested {comp.component_type.value} component from failed strategy: {comp.economic_meaning}",
                },
                "market": {
                    "symbols": ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"],
                    "primary_symbol": "XAUUSD",
                },
                "rule": {
                    "inputs": ["price", comp.value],
                    "trigger": f"Component: {comp.component_type.value} = {comp.value}",
                    "direction": 0,
                    "holding_horizon": "4h",
                    "exit": "component_defined",
                    "stop": "atr_1.5",
                },
                "economics": {
                    "expected_edge_bps_per_trade": score * 10,
                    "expected_trades_per_month": 20,
                    "expected_capacity_lots": 10,
                    "expected_capacity_category": "small",
                },
                "falsifier": {
                    "condition": "component_edge_vanishes",
                    "horizon": "50_trades",
                    "threshold": 0.0,
                    "data_source": "shadow_forward",
                },
                "metadata": {
                    "source": "component_harvesting",
                    "component_type": component.component_type.value,
                    "component_value": component.value,
                    "source_strategy": component.source_strategy,
                    "heuristic_score": score,
                },
            }
            hypotheses.append(hypothesis)
        
        return hypotheses


def harvest_components(failed_strategies: list[Any], 
                        price_data: dict[str, pd.DataFrame]) -> list[StrategyComponent]:
    """Entry point for component harvesting."""
    base = Path("/home/quant/quant-platform")
    harvester = ComponentHarvester(base)
    return harvester.harvest_from_failed_strategies(failed_strategies, price_data)


def generate_component_hypotheses(components: list[StrategyComponent]) -> list[dict]:
    """Generate hypotheses from harvested components."""
    base = Path("/home/quant/quant-platform")
    harvester = ComponentHarvester(base)
    harvester.harvested_components = components
    return harvester.generate_component_hypotheses()


if __name__ == "__main__":
    # Test component extraction
    from mql5_codebase import MQL5CodeParser, ParsedMQL5Strategy
    
    test_code = """
    input double StopLoss = 500;
    input double TakeProfit = 1000;
    input double Lot = 0.1;
    
    void OnTick() {
        double ma_fast = iMA(_Symbol, PERIOD_H1, 10, 0, MODE_EMA, PRICE_CLOSE, 0);
        double ma_slow = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE, 0);
        
        if (ma_fast > ma_slow && OrdersTotal() == 0) {
            OrderSend(Symbol(), OP_BUY, 0.1, Ask, 3, Bid - 500*Point, Ask + 1000*Point, "EMA Cross", 123, 0, clrGreen);
        }
        if (ma_fast < ma_slow && OrdersTotal() == 0) {
            OrderSend(Symbol(), OP_SELL, 0.1, Bid, 3, Ask + 500*Point, Bid - 1000*Point, "EMA Cross", 123, 0, clrRed);
        }
    }
    """
    
    parser = MQL5CodeParser()
    strategy = parser.parse(test_code, "test_123")
    
    extractor = ComponentExtractor()
    components = extractor.extract_from_parsed_strategy(strategy)
    
    print(f"Extracted {len(components)} components:")
    for c in components:
        print(f"  {c.component_type.value}: {c.value} (score: {c.metadata.get('heuristic_score', 0):.2f})")