"""Economic Constraint Graph — mines constraints that force behavior.

Nodes: Fed, banks, dealers, CTAs, pensions, ETF APs, hedgers, retail, option dealers, exchanges, brokers, funds
Edges: must hedge, must rebalance, must liquidate, must roll, must benchmark, must settle, must quote, must meet margin, must replicate index

Automatically generates hypotheses:
IF constraint C strengthens AND observable O confirms AND instrument X historically bears that flow
THEN test X over horizons H1...Hn
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

CONSTRAINT_DIR = DATA_DIR / "economic_constraint_graph"
CONSTRAINT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EconomicNode:
    """A participant in the economic system."""
    name: str
    category: str                              # "central_bank", "bank", "dealer", "fund", "corporate", "retail", "exchange", "broker"
    constraints: list[str]                     # constraints this node faces
    observables: list[str]                     # how we detect their activity
    instruments_affected: list[str]            # symbols they move
    size_estimate: str                         # "tiny", "small", "medium", "large", "systemic"


@dataclass
class ConstraintEdge:
    """A constraint forcing behavior between nodes."""
    source: str                                # node applying constraint
    target: str                                # node forced to act
    constraint_type: str                       # "must_hedge", "must_rebalance", "must_liquidate", "must_roll", "must_benchmark", "must_settle", "must_quote", "must_meet_margin", "must_replicate_index"
    strength: float                            # 0-1
    timing: dict                               # when it applies
    observables: list[str]                     # how to detect
    instruments_affected: list[str]            # affected symbols
    direction: str                             # "buy", "sell", "both", "delta_neutral"
    metadata: dict = field(default_factory=dict)


@dataclass
class ConstraintSignal:
    """Signal from constraint activation."""
    constraint_name: str
    source_node: str
    target_node: str
    symbol: str
    timestamp: datetime
    expected_direction: int
    strength: float
    horizon: str
    context: dict
    subsequent_outcome: dict | None = None


# Economic nodes
ECONOMIC_NODES = {
    "Fed": EconomicNode(
        name="Fed", category="central_bank",
        constraints=["price_stability", "full_employment", "financial_stability"],
        observables=["FOMC_statement", "minutes", "balance_sheet", "speeches", "dot_plot"],
        instruments_affected=["DXY", "US10Y", "US2Y", "XAUUSD", "EURUSD", "USDJPY", "US500"],
        size_estimate="systemic",
    ),
    "ECB": EconomicNode(
        name="ECB", category="central_bank",
        constraints=["price_stability", "financial_stability"],
        observables=["ECB_statement", "accounts", "balance_sheet", "TLTRO", "PEPP"],
        instruments_affected=["EURUSD", "EURGBP", "DE10Y", "EU50", "XAUUSD"],
        size_estimate="systemic",
    ),
    "BOJ": EconomicNode(
        name="BOJ", category="central_bank",
        constraints=["yield_curve_control", "price_stability"],
        observables=["BOJ_statement", "outlook_report", "ETF_purchases", "yield_curve"],
        instruments_affected=["USDJPY", "EURJPY", "JP225", "JP10Y"],
        size_estimate="systemic",
    ),
    "BOE": EconomicNode(
        name="BOE", category="central_bank",
        constraints=["inflation_target", "financial_stability"],
        observables=["MPC_minutes", "inflation_report", "financial_stability_report"],
        instruments_affected=["GBPUSD", "GBPJPY", "UK10Y", "UK100"],
        size_estimate="large",
    ),
    "Banks": EconomicNode(
        name="Banks", category="bank",
        constraints=["capital_adequacy", "liquidity_coverage", "leverage_ratio", "NSFR"],
        observables=["H.4.1", "call_reports", "repo_rates", "CDS_spreads", "deposit_rates"],
        instruments_affected=["DXY", "US10Y", "repo", "swaps", "bank_equities"],
        size_estimate="systemic",
    ),
    "Dealers": EconomicNode(
        name="Dealers", category="dealer",
        constraints=["market_making_obligation", "inventory_limits", "VaR_limits", "gamma_exposure"],
        observables=["OI_changes", "gamma_exposure", "skew", "bid_ask_spread", "inventory"],
        instruments_affected=["options", "underlying_equities", "index_futures", "VIX"],
        size_estimate="large",
    ),
    "CTAs": EconomicNode(
        name="CTAs", category="fund",
        constraints=["trend_following_rules", "volatility_targeting", "position_limits"],
        observables=["CFTC_COT", "managed_futures_index", "breakout_levels", "moving_averages"],
        instruments_affected=["futures", "FX", "commodities", "equity_indices"],
        size_estimate="large",
    ),
    "Pensions": EconomicNode(
        name="Pensions", category="fund",
        constraints=["liability_matching", "duration_targeting", "regulatory_funding_ratio"],
        observables=["LDI_flows", "swap_spreads", "long_bond_demand", "funding_ratio"],
        instruments_affected=["US30Y", "US10Y", "EU30Y", "UK30Y", "swaps", "corporate_bonds"],
        size_estimate="large",
    ),
    "ETF_APs": EconomicNode(
        name="ETF_APs", category="fund",
        constraints=["creation_redemption_arbitrage", "tracking_error_minimization"],
        observables=["ETF_flows", "premium_discount", "creation_units", "basket_composition"],
        instruments_affected=["SPY", "GLD", "QQQ", "IWM", "EEM", "underlying_baskets"],
        size_estimate="large",
    ),
    "Hedgers_Corporate": EconomicNode(
        name="Hedgers_Corporate", category="corporate",
        constraints=["FX_exposure_hedging", "commodity_input_hedging", "accounting_hedge_accounting"],
        observables=["month_end_flows", "WM_fix", "quarter_end_rebalancing", "earnings_calls"],
        instruments_affected=["ALL_FX", "commodities", "XAUUSD"],
        size_estimate="medium",
    ),
    "Hedgers_Commodity": EconomicNode(
        name="Hedgers_Commodity", category="corporate",
        constraints=["revenue_locking", "budget_certainty", "credit_facility_covenants"],
        observables=["futures_OI", "producer_hedging_pressure", "crack_spreads", "inventory"],
        instruments_affected=["USOIL", "XAUUSD", "XAGUSD", "COPPER", "CORN", "WHEAT", "NG"],
        size_estimate="medium",
    ),
    "Retail": EconomicNode(
        name="Retail", category="retail",
        constraints=["behavioral_biases", "leverage_limits", "margin_calls"],
        observables=["retail_sentiment", "broker_positioning", "CFD_positioning", "social_media"],
        instruments_affected=["ALL_CFD", "meme_stocks", "crypto", "high_beta"],
        size_estimate="medium",
    ),
    "Option_Dealers": EconomicNode(
        name="Option_Dealers", category="dealer",
        constraints=["delta_hedging", "gamma_scalping", "vega_risk", "pin_risk"],
        observables=["GEX", "OI_by_strike", "max_pain", "skew", "term_structure"],
        instruments_affected=["underlying_equities", "index_futures", "VIX", "SPY", "QQQ"],
        size_estimate="large",
    ),
    "Exchanges": EconomicNode(
        name="Exchanges", category="exchange",
        constraints=["settlement_cycles", "margin_methodology", "circuit_breakers", "contract_specs"],
        observables=["margin_changes", "contract_specs", "settlement_calendar", "holiday_calendar"],
        instruments_affected=["ALL_FUTURES", "options", "listed_products"],
        size_estimate="systemic",
    ),
    "Brokers": EconomicNode(
        name="Brokers", category="broker",
        constraints=["client_margin", "hedging_policy", "internalization", "PFOF"],
        observables=["spread_changes", "stop_levels", "freeze_levels", "execution_quality", "slippage"],
        instruments_affected=["ALL_CFD", "ALL_FX", "ALL_FUTURES"],
        size_estimate="medium",
    ),
    "Risk_Parity": EconomicNode(
        name="Risk_Parity", category="fund",
        constraints=["equal_risk_allocation", "vol_targeting", "leverage_adjustment"],
        observables=["bond_equity_correlation", "vol_target_breach", "leverage_changes"],
        instruments_affected=["bonds", "equities", "commodities", "FX"],
        size_estimate="large",
    ),
    "Vol_Control": EconomicNode(
        name="Vol_Control", category="fund",
        constraints=["volatility_target", "deleveraging_on_spike", "releveraging_on_calm"],
        observables=["VIX_term_structure", "realized_vol", "equity_vol", "allocation_shifts"],
        instruments_affected=["equities", "VIX", "bonds", "gold"],
        size_estimate="large",
    ),
}

# Constraint edges
CONSTRAINT_EDGES = [
    ConstraintEdge(
        source="Fed", target="Banks",
        constraint_type="must_meet_margin",
        strength=0.9,
        timing={"trigger": "policy_rate_change", "frequency": "FOMC"},
        observables=["Fed_funds_rate", "discount_window", "repo_operations"],
        instruments_affected=["DXY", "US2Y", "repo"],
        direction="both",
    ),
    ConstraintEdge(
        source="Fed", target="Dealers",
        constraint_type="must_hedge",
        strength=0.8,
        timing={"trigger": "QE_QT", "frequency": "balance_sheet_change"},
        observables=["balance_sheet", "SOFR", "repo"],
        instruments_affected=["DXY", "US10Y", "swaps"],
        direction="both",
    ),
    ConstraintEdge(
        source="Fed", target="Risk_Parity",
        constraint_type="must_rebalance",
        strength=0.7,
        timing={"trigger": "vol_regime_change", "frequency": "continuous"},
        observables=["vol_target", "leverage"],
        instruments_affected=["bonds", "equities", "commodities"],
        direction="both",
    ),
    ConstraintEdge(
        source="ECB", target="Banks",
        constraint_type="must_meet_margin",
        strength=0.9,
        timing={"trigger": "deposit_rate", "frequency": "ECB_meeting"},
        observables=["deposit_rate", "TLTRO", "PEPP"],
        instruments_affected=["EURUSD", "DE10Y", "EUR_swaps"],
        direction="both",
    ),
    ConstraintEdge(
        source="Dealers", target="Option_Dealers",
        constraint_type="must_hedge",
        strength=0.95,
        timing={"trigger": "OI_change", "frequency": "continuous"},
        observables=["delta", "gamma", "OI"],
        instruments_affected=["SPY", "QQQ", "VIX", "SPX"],
        direction="delta_neutral",
    ),
    ConstraintEdge(
        source="CTAs", target="Exchanges",
        constraint_type="must_roll",
        strength=0.9,
        timing={"trigger": "expiry", "frequency": "monthly_quarterly"},
        observables=["calendar_spread", "OI_shift", "volume"],
        instruments_affected=["CL", "GC", "ES", "NQ", "6E", "6J"],
        direction="roll",
    ),
    ConstraintEdge(
        source="ETF_APs", target="Exchanges",
        constraint_type="must_replicate_index",
        strength=0.95,
        timing={"trigger": "index_rebalance", "frequency": "quarterly"},
        observables=["rebalance_announcement", "creation_redemption", "premium_discount"],
        instruments_affected=["SP500_constituents", "SPY", "GLD", "QQQ"],
        direction="rebalance",
    ),
    ConstraintEdge(
        source="Pensions", target="Banks",
        constraint_type="must_hedge",
        strength=0.8,
        timing={"trigger": "month_end", "frequency": "monthly"},
        observables=["LDI_flows", "swap_spreads", "month_end"],
        instruments_affected=["US30Y", "US10Y", "swaps"],
        direction="receive_fixed",
    ),
    ConstraintEdge(
        source="Hedgers_Corporate", target="Brokers",
        constraint_type="must_hedge",
        strength=0.7,
        timing={"trigger": "month_end_quarter_end", "frequency": "monthly_quarterly"},
        observables=["WM_fix", "quarter_end", "corporate_earnings"],
        instruments_affected=["ALL_FX", "EURUSD", "GBPUSD", "USDJPY"],
        direction="hedge",
    ),
    ConstraintEdge(
        source="Hedgers_Commodity", target="Exchanges",
        constraint_type="must_roll",
        strength=0.8,
        timing={"trigger": "expiry", "frequency": "monthly"},
        observables=["calendar_spread", "inventory", "crack_spread"],
        instruments_affected=["CL", "GC", "NG", "HG", "ZC", "ZW"],
        direction="roll",
    ),
    ConstraintEdge(
        source="Risk_Parity", target="Vol_Control",
        constraint_type="must_rebalance",
        strength=0.7,
        timing={"trigger": "vol_spike", "frequency": "continuous"},
        observables=["VIX", "realized_vol", "correlation"],
        instruments_affected=["equities", "bonds", "commodities"],
        direction="delever",
    ),
    ConstraintEdge(
        source="Vol_Control", target="CTAs",
        constraint_type="must_rebalance",
        strength=0.7,
        timing={"trigger": "vol_regime", "frequency": "daily_EOD"},
        observables=["VIX", "vol_target"],
        instruments_affected=["equities", "futures"],
        direction="delever_long_vol",
    ),
    ConstraintEdge(
        source="Brokers", target="Retail",
        constraint_type="must_meet_margin",
        strength=0.9,
        timing={"trigger": "margin_call", "frequency": "stress_events"},
        observables=["margin_level", "equity", "liquidation"],
        instruments_affected=["ALL_CFD", "ALL_FX"],
        direction="sell",
    ),
    ConstraintEdge(
        source="Exchanges", target="ALL",
        constraint_type="must_settle",
        strength=1.0,
        timing={"trigger": "settlement_cycle", "frequency": "T+1_T+2"},
        observables=["settlement_date", "margin_cycle"],
        instruments_affected=["ALL_FUTURES", "options"],
        direction="settle",
    ),
    ConstraintEdge(
        source="Central_Banks", target="Hedgers_Corporate",
        constraint_type="must_benchmark",
        strength=0.6,
        timing={"trigger": "FX_reserve_management", "frequency": "continuous"},
        observables=["FX_reserves", "intervention"],
        instruments_affected=["DXY", "EURUSD", "USDJPY", "CNY"],
        direction="policy",
    ),
]


class EconomicConstraintGraph:
    """Graph of economic constraints generating hypotheses."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes = ECONOMIC_NODES
        self.edges = CONSTRAINT_EDGES
        self.signals: list[ConstraintSignal] = []
        self._build_graph()

    def _build_graph(self) -> None:
        """Build the constraint graph."""
        for name, node in self.nodes.items():
            self.graph.add_node(name, **node.__dict__)

        for edge in self.edges:
            self.graph.add_edge(edge.source, edge.target, **edge.__dict__)

    def find_constraint_paths(self, source: str, target: str, max_depth: int = 3) -> list[list[str]]:
        """Find all constraint paths between nodes."""
        try:
            return list(nx.all_simple_paths(self.graph, source, target, cutoff=max_depth))
        except nx.NetworkXNoPath:
            return []

    def get_constraints_for_instrument(self, symbol: str) -> list[ConstraintEdge]:
        """Get all constraints affecting an instrument."""
        result = []
        for edge in self.edges:
            if "ALL" in edge.instruments_affected or symbol in edge.instruments_affected:
                result.append(edge)
        return result

    def get_constraints_for_node(self, node_name: str) -> list[ConstraintEdge]:
        """Get all constraints where node is source or target."""
        result = []
        for edge in self.edges:
            if edge.source == node_name or edge.target == node_name:
                result.append(edge)
        return result

    def generate_hypotheses_from_constraints(self, symbol: str,
                                              observables: dict[str, Any]) -> list[SideChannelHypothesis]:
        """Generate hypotheses from constraint graph for a symbol."""
        hypotheses = []
        constraints = self.get_constraints_for_instrument(symbol)

        for edge in constraints:
            # Check if constraint is active based on observables
            active = self._check_constraint_active(edge, observables)
            if not active:
                continue

            # Generate hypothesis
            h = SideChannelHypothesis(
                id=generate_id(),
                axis=SideChannelAxis.FLOW,
                source="economic_constraint_graph",
                mechanism=f"Constraint: {edge.source} → {edge.target} ({edge.constraint_type}). "
                          f"When {edge.source} {edge.constraint_type.replace('_', ' ')}, "
                          f"{edge.target} forced to {edge.direction} {symbol}. "
                          f"Strength: {edge.strength:.1f}. Timing: {edge.timing}.",
                symbols=[symbol],
                timing={
                    "constraint": f"{edge.source}_{edge.constraint_type}",
                    "timing": edge.timing,
                    "strength": edge.strength,
                },
                falsifier=f"Constraint activation doesn't produce expected flow over 20+ occurrences",
                expected_horizon="intraday_to_1d",
                capacity_estimate="institutional" if edge.strength > 0.8 else "small",
                metadata={
                    "source": edge.source,
                    "target": edge.target,
                    "constraint_type": edge.constraint_type,
                    "strength": edge.strength,
                    "direction": edge.direction,
                    "instruments": edge.instruments_affected,
                }
            )
            hypotheses.append(h)
            save_hypothesis(h)

        return hypotheses

    def _check_constraint_active(self, edge: ConstraintEdge, observables: dict) -> bool:
        """Check if a constraint is currently active."""
        # Simplified: check if any observable is present and recent
        for obs in edge.observables:
            if obs in observables:
                val = observables[obs]
                if isinstance(val, dict) and val.get("active", False):
                    return True
                if isinstance(val, (int, float)) and abs(val) > 0.5:
                    return True
        return False

    def simulate_constraint_cascade(self, initial_shock: str,
                                     affected_symbols: list[str]) -> list[ConstraintSignal]:
        """Simulate cascade of constraints from an initial shock."""
        signals = []

        # Find all paths from shocked node
        for target in self.nodes:
            if target == initial_shock:
                continue
            paths = self.find_constraint_paths(initial_shock, target)
            for path in paths:
                # Each edge in path transmits the shock
                for i in range(len(path) - 1):
                    source, tgt = path[i], path[i+1]
                    edge_data = self.graph.get_edge_data(source, tgt)
                    if edge_data:
                        for sym in affected_symbols:
                            if sym in edge_data.get("instruments_affected", []) or "ALL" in edge_data.get("instruments_affected", []):
                                signals.append(ConstraintSignal(
                                    constraint_name=f"{source}_{edge_data.get('constraint_type')}",
                                    source_node=source,
                                    target_node=tgt,
                                    symbol=sym,
                                    timestamp=datetime.now(UTC),
                                    expected_direction=1 if edge_data.get("direction") in ["buy", "both"] else -1,
                                    strength=edge_data.get("strength", 0.5),
                                    horizon="intraday_to_1d",
                                    context={"path": path, "initial_shock": initial_shock},
                                ))

        return signals

    def generate_all_hypotheses(self, symbols: list[str],
                                 observables: dict[str, Any]) -> list[SideChannelHypothesis]:
        """Generate all constraint-based hypotheses."""
        all_hypotheses = []
        for sym in symbols:
            all_hypotheses.extend(self.generate_hypotheses_from_constraints(sym, observables))
        return all_hypotheses

    def save(self) -> None:
        import json
        # Save graph as adjacency list
        graph_data = nx.node_link_data(self.graph)
        with open(CONSTRAINT_DIR / "constraint_graph.json", "w") as f:
            json.dump(graph_data, f, indent=2)

        # Save edges separately
        with open(CONSTRAINT_DIR / "constraint_edges.json", "w") as f:
            json.dump([{
                "source": e.source,
                "target": e.target,
                "constraint_type": e.constraint_type,
                "strength": e.strength,
                "timing": e.timing,
                "observables": e.observables,
                "instruments": e.instruments_affected,
                "direction": e.direction,
            } for e in self.edges], f, indent=2)


if __name__ == "__main__":
    graph = EconomicConstraintGraph()

    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")

    # Test: constraints for XAUUSD
    gold_constraints = graph.get_constraints_for_instrument("XAUUSD")
    print(f"\nConstraints affecting XAUUSD: {len(gold_constraints)}")
    for e in gold_constraints:
        print(f"  {e.source} → {e.target} [{e.constraint_type}] strength={e.strength}")

    # Test: paths from Fed to CTAs
    paths = graph.find_constraint_paths("Fed", "CTAs")
    print(f"\nPaths Fed → CTAs: {len(paths)}")
    for p in paths[:3]:
        print(f"  {' → '.join(p)}")

    # Generate hypotheses
    observables = {
        "FOMC_statement": {"active": True},
        "balance_sheet": {"active": True},
        "vol_target": {"active": True, "value": 0.8},
    }
    hyps = graph.generate_hypotheses_from_constraints("XAUUSD", observables)
    print(f"\nGenerated {len(hyps)} constraint hypotheses for XAUUSD")

    # Simulate shock cascade
    cascade = graph.simulate_constraint_cascade("Fed", ["XAUUSD", "EURUSD", "US500"])
    print(f"\nFed shock cascade signals: {len(cascade)}")