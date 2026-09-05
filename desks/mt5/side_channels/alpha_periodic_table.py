"""Alpha Periodic Table / Mechanism Matrix.

Every candidate gets coordinates:
WHO caused it? WHY must they act? WHAT information changes?
WHEN is the edge active? WHERE does the information appear first?
HOW does it reach the tradable instrument? HOW LONG does it persist?
WHAT kills it?

Maintains a matrix with empty cells as research targets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import SideChannelAxis, SideChannelHypothesis, generate_id, save_hypothesis, DATA_DIR

PERIODIC_DIR = DATA_DIR / "alpha_periodic_table"
PERIODIC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MechanismCell:
    """One cell in the mechanism matrix."""
    mechanism: str
    axis: SideChannelAxis
    status: str                              # "discovered", "validated", "hunting", "empty", "dead"
    hypothesis_id: str | None = None
    evidence_strength: float = 0.0
    sample_size: int = 0
    avg_return: float = 0.0
    falsifier_status: str = "untested"
    metadata: dict = field(default_factory=dict)


@dataclass
class AlphaElement:
    """A discovered alpha with full coordinates."""
    hypothesis_id: str
    who: str                                 # forced participant
    why: str                                 # constraint/mechanism
    what: str                                # information change
    when: str                                # timing/regime
    where: str                               # first appearance
    how: str                                 # propagation path
    how_long: str                            # persistence
    what_kills: str                          # falsifier
    axis: SideChannelAxis
    symbols: list[str]
    evidence: dict
    coordinates: dict                        # all 8 coordinates


# The Mechanism Matrix (from earlier analysis)
MECHANISMS = [
    "forced_buyer", "forced_seller", "information_shock",
    "inventory_imbalance", "crowding_unwind", "slow_diffusion",
    "mechanical_rebalance",
]

AXES = [
    SideChannelAxis.FLOW,
    SideChannelAxis.EVENT,
    SideChannelAxis.RELATIVE_VALUE,
    SideChannelAxis.LIQUIDITY,
    SideChannelAxis.EXECUTION,
    SideChannelAxis.SEASONALITY,
    SideChannelAxis.POSITIONING,
    SideChannelAxis.MACRO,
    SideChannelAxis.MICROSTRUCTURE,
]


class AlphaPeriodicTable:
    """The Alpha Periodic Table — mechanism × axis matrix."""

    def __init__(self):
        self.cells: dict[tuple, MechanismCell] = {}
        self.elements: list[AlphaElement] = []
        self._initialize_matrix()

    def _initialize_matrix(self) -> None:
        """Initialize all mechanism × axis cells as empty."""
        for mech in MECHANISMS:
            for axis in AXES:
                self.cells[(mech, axis)] = MechanismCell(
                    mechanism=mech,
                    axis=axis,
                    status="empty",
                )

        # Pre-fill known cells from earlier analysis
        known_cells = {
            ("forced_buyer", SideChannelAxis.FLOW): "ETF AP creation, index tracker rebalance, pension mandate",
            ("forced_buyer", SideChannelAxis.EVENT): "index rebalance announcement, inclusion/exclusion",
            ("forced_buyer", SideChannelAxis.RELATIVE_VALUE): "ETF vs basket arbitrage, synthetic replication error",
            ("forced_buyer", SideChannelAxis.LIQUIDITY): "creation basket liquidity premium",
            ("forced_buyer", SideChannelAxis.EXECUTION): "market-on-close imbalances",
            ("forced_buyer", SideChannelAxis.SEASONALITY): "quarter-end, month-end, rebalance dates",
            ("forced_buyer", SideChannelAxis.POSITIONING): "short gamma dealers forced to buy",
            ("forced_buyer", SideChannelAxis.MACRO): "inflow-driven momentum",
            ("forced_buyer", SideChannelAxis.MICROSTRUCTURE): "quote stuffing on creation basket",

            ("forced_seller", SideChannelAxis.FLOW): "margin liquidation, fund redemption, CTA stop-loss cascade",
            ("forced_seller", SideChannelAxis.EVENT): "margin call, risk limit breach, VaR shock",
            ("forced_seller", SideChannelAxis.RELATIVE_VALUE): "fire-sale discount to fair value",
            ("forced_seller", SideChannelAxis.LIQUIDITY): "spread widening, depth evaporation",
            ("forced_seller", SideChannelAxis.EXECUTION): "slippage on forced market orders",
            ("forced_seller", SideChannelAxis.SEASONALITY): "quarter-end risk reduction, year-end tax loss",
            ("forced_seller", SideChannelAxis.POSITIONING): "crowded long unwind",
            ("forced_seller", SideChannelAxis.MACRO): "risk-off repricing",
            ("forced_seller", SideChannelAxis.MICROSTRUCTURE): "toxic order flow signature",

            ("information_shock", SideChannelAxis.FLOW): "news-driven order flow, algorithmic reaction",
            ("information_shock", SideChannelAxis.EVENT): "CPI, NFP, Fed, geopolitical, earnings, Trump post",
            ("information_shock", SideChannelAxis.RELATIVE_VALUE): "cross-asset repricing speed differential",
            ("information_shock", SideChannelAxis.LIQUIDITY): "quote withdrawal, spread explosion",
            ("information_shock", SideChannelAxis.EXECUTION): "latency arb, stale quote fills",
            ("information_shock", SideChannelAxis.SEASONALITY): "scheduled releases, unscheduled policy",
            ("information_shock", SideChannelAxis.POSITIONING): "surprise vs positioning alignment",
            ("information_shock", SideChannelAxis.MACRO): "policy repricing vector",
            ("information_shock", SideChannelAxis.MICROSTRUCTURE): "leadership atlas activation",

            ("inventory_imbalance", SideChannelAxis.FLOW): "dealer inventory skew, market maker gamma",
            ("inventory_imbalance", SideChannelAxis.EVENT): "large block trade, options expiry pin",
            ("inventory_imbalance", SideChannelAxis.RELATIVE_VALUE): "forward vs spot dislocation",
            ("inventory_imbalance", SideChannelAxis.LIQUIDITY): "one-sided depth, quote asymmetry",
            ("inventory_imbalance", SideChannelAxis.EXECUTION): "internalization vs exchange routing",
            ("inventory_imbalance", SideChannelAxis.SEASONALITY): "expiry weeks, roll periods",
            ("inventory_imbalance", SideChannelAxis.POSITIONING): "gamma exposure sign flip",
            ("inventory_imbalance", SideChannelAxis.MACRO): "carry regime dependent",
            ("inventory_imbalance", SideChannelAxis.MICROSTRUCTURE): "tick rule imbalance",

            ("crowding_unwind", SideChannelAxis.FLOW): "systematic strategy correlation, factor crowding",
            ("crowding_unwind", SideChannelAxis.EVENT): "factor drawdown, regime change",
            ("crowding_unwind", SideChannelAxis.RELATIVE_VALUE): "factor long-short reversal",
            ("crowding_unwind", SideChannelAxis.LIQUIDITY): "coordinated exit, liquidity vacuum",
            ("crowding_unwind", SideChannelAxis.EXECUTION): "slippage correlation across sleeves",
            ("crowding_unwind", SideChannelAxis.SEASONALITY): "factor rotation calendar",
            ("crowding_unwind", SideChannelAxis.POSITIONING): "z-score of factor positioning",
            ("crowding_unwind", SideChannelAxis.MACRO): "regime-dependent factor correlation",
            ("crowding_unwind", SideChannelAxis.MICROSTRUCTURE): "cross-strategy execution overlap",

            ("slow_diffusion", SideChannelAxis.FLOW): "retail/herd delayed reaction, information trickle",
            ("slow_diffusion", SideChannelAxis.EVENT): "revision, guidance change, underfollowed news",
            ("slow_diffusion", SideChannelAxis.RELATIVE_VALUE): "cross-market convergence delay",
            ("slow_diffusion", SideChannelAxis.LIQUIDITY): "gradual depth improvement",
            ("slow_diffusion", SideChannelAxis.EXECUTION): "improving fills over diffusion window",
            ("slow_diffusion", SideChannelAxis.SEASONALITY): "post-earnings drift, post-revision",
            ("slow_diffusion", SideChannelAxis.POSITIONING): "smart money vs dumb money divergence",
            ("slow_diffusion", SideChannelAxis.MACRO): "expectations anchoring",
            ("slow_diffusion", SideChannelAxis.MICROSTRUCTURE): "information half-life curve",

            ("mechanical_rebalance", SideChannelAxis.FLOW): "index rebalance, ETF rebalance, risk parity rebalance",
            ("mechanical_rebalance", SideChannelAxis.EVENT): "scheduled rebalance dates, methodology changes",
            ("mechanical_rebalance", SideChannelAxis.RELATIVE_VALUE): "rebalance basket vs index spread",
            ("mechanical_rebalance", SideChannelAxis.LIQUIDITY): "predictable volume surge",
            ("mechanical_rebalance", SideChannelAxis.EXECUTION): "MOC, VWAP, TWAP participation",
            ("mechanical_rebalance", SideChannelAxis.SEASONALITY): "fixed calendar, quarterly/monthly",
            ("mechanical_rebalance", SideChannelAxis.POSITIONING): "front-running rebalance flows",
            ("mechanical_rebalance", SideChannelAxis.MACRO): "index methodology changes",
            ("mechanical_rebalance", SideChannelAxis.MICROSTRUCTURE): "quote behavior pre-post rebalance",
        }

        for (mech, axis), desc in known_cells.items():
            self.cells[(mech, axis)].status = "discovered"
            self.cells[(mech, axis)].evidence_strength = 0.5
            self.cells[(mech, axis)].metadata = {"description": desc}

    def get_research_targets(self) -> list[tuple[str, SideChannelAxis]]:
        """Return empty cells as research targets."""
        return [(mech, axis) for (mech, axis), cell in self.cells.items()
                if cell.status == "empty"]

    def get_discovered(self) -> list[tuple[str, SideChannelAxis]]:
        """Return discovered cells."""
        return [(mech, axis) for (mech, axis), cell in self.cells.items()
                if cell.status == "discovered"]

    def update_cell(self, mechanism: str, axis: SideChannelAxis,
                    hypothesis_id: str, evidence: dict) -> None:
        """Update cell with hypothesis evidence."""
        if (mechanism, axis) not in self.cells:
            return
        cell = self.cells[(mechanism, axis)]
        cell.status = "validated"
        cell.hypothesis_id = hypothesis_id
        cell.evidence_strength = evidence.get("strength", 0.5)
        cell.sample_size = evidence.get("sample_size", 0)
        cell.avg_return = evidence.get("avg_return", 0.0)
        cell.falsifier_status = "active"
        cell.metadata["evidence"] = evidence

    def register_element(self, hypothesis_id: str, coordinates: dict) -> AlphaElement:
        """Register a discovered alpha with full 8 coordinates."""
        element = AlphaElement(
            hypothesis_id=hypothesis_id,
            who=coordinates.get("who", ""),
            why=coordinates.get("why", ""),
            what=coordinates.get("what", ""),
            when=coordinates.get("when", ""),
            where=coordinates.get("where", ""),
            how=coordinates.get("how", ""),
            how_long=coordinates.get("how_long", ""),
            what_kills=coordinates.get("what_kills", ""),
            axis=SideChannelAxis(coordinates.get("axis", "event")),
            symbols=coordinates.get("symbols", []),
            evidence=coordinates.get("evidence", {}),
            coordinates=coordinates,
        )
        self.elements.append(element)

        # Update corresponding cell
        mech = coordinates.get("mechanism", "")
        axis = SideChannelAxis(coordinates.get("axis", "event"))
        if (mech, axis) in self.cells:
            self.update_cell(mech, axis, hypothesis_id, coordinates.get("evidence", {}))

        return element

    def get_research_priorities(self, top_n: int = 20) -> list[tuple[str, SideChannelAxis, str]]:
        """Prioritize empty cells by potential."""
        empty = self.get_research_targets()
        # Prioritize: FLOW × MACRO, EVENT × MICROSTRUCTURE, etc.
        priority_order = [
            (SideChannelAxis.FLOW, SideChannelAxis.MACRO),
            (SideChannelAxis.EVENT, SideChannelAxis.MICROSTRUCTURE),
            (SideChannelAxis.FLOW, SideChannelAxis.EXECUTION),
            (SideChannelAxis.RELATIVE_VALUE, SideChannelAxis.LIQUIDITY),
            (SideChannelAxis.POSITIONING, SideChannelAxis.SEASONALITY),
        ]

        scored = []
        for mech, axis in empty:
            score = 0
            for i, (ax1, ax2) in enumerate(priority_order):
                if axis == ax1 or axis == ax2:
                    score += 10 - i
            if mech in ["forced_buyer", "forced_seller", "information_shock"]:
                score += 5
            scored.append((mech, axis, score))

        scored.sort(key=lambda x: -x[2])
        return [(m, a, "HIGH" if s >= 15 else "MEDIUM" if s >= 10 else "LOW") for m, a, s in scored[:top_n]]

    def to_dataframe(self) -> pd.DataFrame:
        """Export matrix as DataFrame."""
        rows = []
        for (mech, axis), cell in self.cells.items():
            rows.append({
                "mechanism": mech,
                "axis": axis.value,
                "status": cell.status,
                "hypothesis_id": cell.hypothesis_id or "",
                "evidence_strength": cell.evidence_strength,
                "sample_size": cell.sample_size,
                "avg_return": cell.avg_return,
                "falsifier_status": cell.falsifier_status,
                "description": cell.metadata.get("description", ""),
            })
        return pd.DataFrame(rows)

    def save(self) -> None:
        df = self.to_dataframe()
        df.to_csv(PERIODIC_DIR / "mechanism_matrix.csv", index=False)

        import json
        with open(PERIODIC_DIR / "elements.json", "w") as f:
            json.dump([{
                "hypothesis_id": e.hypothesis_id,
                "who": e.who,
                "why": e.why,
                "what": e.what,
                "when": e.when,
                "where": e.where,
                "how": e.how,
                "how_long": e.how_long,
                "what_kills": e.what_kills,
                "axis": e.axis.value,
                "symbols": e.symbols,
                "evidence": e.evidence,
                "coordinates": e.coordinates,
            } for e in self.elements], f, indent=2, default=str)


def register_hypothesis_in_table(hypothesis: SideChannelHypothesis, table: AlphaPeriodicTable) -> None:
    """Register a hypothesis in the periodic table with full coordinates."""
    coords = {
        "who": hypothesis.metadata.get("who", "unknown"),
        "why": hypothesis.metadata.get("why", hypothesis.mechanism),
        "what": hypothesis.metadata.get("what", hypothesis.source),
        "when": hypothesis.metadata.get("when", str(hypothesis.timing)),
        "where": hypothesis.metadata.get("where", "unknown"),
        "how": hypothesis.metadata.get("how", "unknown"),
        "how_long": hypothesis.metadata.get("how_long", hypothesis.expected_horizon),
        "what_kills": hypothesis.falsifier,
        "axis": hypothesis.metadata.get("axis", hypothesis.metadata.get("signal_axis", "event")),
        "symbols": hypothesis.symbols,
        "evidence": hypothesis.metadata,
        "mechanism": hypothesis.metadata.get("mechanism", "unknown"),
    }
    table.register_element(hypothesis.id, coords)


if __name__ == "__main__":
    table = AlphaPeriodicTable()

    print("Research Targets (empty cells):")
    for mech, axis in table.get_research_targets()[:20]:
        print(f"  {mech} × {axis.value}")

    print("\nDiscovered Cells:")
    for mech, axis in table.get_discovered():
        cell = table.cells[(mech, axis)]
        print(f"  {mech} × {axis.value}: {cell.metadata.get('description', '')[:60]}")

    print("\nResearch Priorities:")
    for mech, axis, priority in table.get_research_priorities(15):
        print(f"  {mech} × {axis.value}: {priority}")

    df = table.to_dataframe()
    print(f"\nMatrix shape: {df.shape}")
    print(f"Empty: {(df['status'] == 'empty').sum()}")
    print(f"Discovered: {(df['status'] == 'discovered').sum()}")