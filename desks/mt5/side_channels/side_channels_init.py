"""Side-Channel Alpha Factory — Market Side-Channel Atlas.

Core concept: Hunt information created by market machinery, not price charts.

Axes:
  FLOW           - forced participant behavior, institutional flows
  EVENT          - scheduled/unexpected events, policy shocks
  RELATIVE_VALUE - synthetic prices, cross-asset residuals
  LIQUIDITY      - broker physics, spread/tick/latency microstructure
  EXECUTION      - fill quality, slippage, stop behavior
  SEASONALITY    - operational calendars, settlement, rolls
  POSITIONING    - crowding, revision regimes, disagreement
  MACRO          - policy repricing, revision vectors
  MICROSTRUCTURE - timestamp leadership, information propagation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "side_channels" / "data"
ATLAS_DIR = BASE / "side_channels" / "atlas"
HYPOTHESIS_DIR = BASE / "side_channels" / "hypotheses"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ATLAS_DIR.mkdir(parents=True, exist_ok=True)
HYPOTHESIS_DIR.mkdir(parents=True, exist_ok=True)


class SideChannelAxis(Enum):
    """Independent information axes for alpha generation."""
    FLOW = "flow"
    EVENT = "event"
    RELATIVE_VALUE = "relative_value"
    LIQUIDITY = "liquidity"
    EXECUTION = "execution"
    SEASONALITY = "seasonality"
    POSITIONING = "positioning"
    MACRO = "macro"
    MICROSTRUCTURE = "microstructure"


@dataclass
class SideChannelHypothesis:
    """A hypothesis generated from a side-channel source."""
    id: str                              # SC-XXXXXX
    axis: SideChannelAxis
    source: str                          # e.g., "operational_calendar", "leadership_atlas"
    mechanism: str                       # economic rationale
    symbols: list[str]                   # affected instruments
    timing: dict                         # when edge is active
    falsifier: str                       # what would disprove
    expected_horizon: str                # 1m, 5m, 15m, 1h, 4h, 1d, etc.
    capacity_estimate: str               # "institutional" | "small" | "micro"
    status: str = "DISCOVERED"           # DISCOVERED | VALIDATED | SHADOW | PROMOTED | RETIRED
    metadata: dict = field(default_factory=dict)


@dataclass
class InformationLead:
    """Leadership relationship between instruments."""
    leader: str
    follower: str
    event_type: str
    regime: str
    lag_seconds: float
    confidence: float
    sample_size: int
    last_updated: str


@dataclass
class FailedReaction:
    """A market that failed to react as expected."""
    event_id: str
    event_type: str
    expected_reaction: dict              # {symbol: expected_direction}
    actual_reaction: dict                # {symbol: actual_direction}
    disagreement_score: float
    subsequent_outcome: dict | None = None


@dataclass
class SyntheticResidual:
    """Residual between actual and synthetic/fair price."""
    symbol: str
    synthetic_model: str                 # e.g., "fx_triangle", "metals_model"
    residual: float
    z_score: float
    timestamp: str
    regime: str


def generate_id(prefix: str = "SC") -> str:
    """Generate unique side-channel hypothesis ID."""
    existing = list(HYPOTHESIS_DIR.glob(f"{prefix}-*.yaml"))
    return f"{prefix}-{len(existing)+1:06d}"


def save_hypothesis(h: SideChannelHypothesis) -> Path:
    """Save hypothesis to YAML."""
    import yaml
    path = HYPOTHESIS_DIR / f"{h.id}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(h.__dict__, f, sort_keys=False)
    return path


def load_hypotheses() -> list[SideChannelHypothesis]:
    """Load all side-channel hypotheses."""
    import yaml
    hypotheses = []
    for path in HYPOTHESIS_DIR.glob("SC-*.yaml"):
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        data["axis"] = SideChannelAxis(data["axis"])
        hypotheses.append(SideChannelHypothesis(**data))
    return hypotheses


# Mechanism matrix — the "Alpha Periodic Table"
MECHANISM_MATRIX = {
    "forced_buyer": {
        "flow": "ETF AP creation, index tracker rebalance, pension mandate",
        "event": "index rebalance announcement, inclusion/exclusion",
        "relative_value": "ETF vs basket arbitrage, synthetic replication error",
        "liquidity": "creation basket liquidity premium",
        "execution": "market-on-close imbalances",
        "seasonality": "quarter-end, month-end, rebalance dates",
        "positioning": "short gamma dealers forced to buy",
        "macro": "inflow-driven momentum",
        "microstructure": "quote stuffing on creation basket",
    },
    "forced_seller": {
        "flow": "margin liquidation, fund redemption, CTA stop-loss cascade",
        "event": "margin call, risk limit breach, VaR shock",
        "relative_value": "fire-sale discount to fair value",
        "liquidity": "spread widening, depth evaporation",
        "execution": "slippage on forced market orders",
        "seasonality": "quarter-end risk reduction, year-end tax loss",
        "positioning": "crowded long unwind",
        "macro": "risk-off repricing",
        "microstructure": "toxic order flow signature",
    },
    "information_shock": {
        "flow": "news-driven order flow, algorithmic reaction",
        "event": "CPI, NFP, Fed, geopolitical, earnings, Trump post",
        "relative_value": "cross-asset repricing speed differential",
        "liquidity": "quote withdrawal, spread explosion",
        "execution": "latency arb, stale quote fills",
        "seasonality": "scheduled releases, unscheduled policy",
        "positioning": "surprise vs positioning alignment",
        "macro": "policy repricing vector",
        "microstructure": "leadership atlas activation",
    },
    "inventory_imbalance": {
        "flow": "dealer inventory skew, market maker gamma",
        "event": "large block trade, options expiry pin",
        "relative_value": "forward vs spot dislocation",
        "liquidity": "one-sided depth, quote asymmetry",
        "execution": "internalization vs exchange routing",
        "seasonality": "expiry weeks, roll periods",
        "positioning": "gamma exposure sign flip",
        "macro": "carry regime dependent",
        "microstructure": "tick rule imbalance",
    },
    "crowding_unwind": {
        "flow": "systematic strategy correlation, factor crowding",
        "event": "factor drawdown, regime change",
        "relative_value": "factor long-short reversal",
        "liquidity": "coordinated exit, liquidity vacuum",
        "execution": "slippage correlation across sleeves",
        "seasonality": "factor rotation calendar",
        "positioning": "z-score of factor positioning",
        "macro": "regime-dependent factor correlation",
        "microstructure": "cross-strategy execution overlap",
    },
    "slow_diffusion": {
        "flow": "retail/herd delayed reaction, information trickle",
        "event": "revision, guidance change, underfollowed news",
        "relative_value": "cross-market convergence delay",
        "liquidity": "gradual depth improvement",
        "execution": "improving fills over diffusion window",
        "seasonality": "post-earnings drift, post-revision",
        "positioning": "smart money vs dumb money divergence",
        "macro": "expectations anchoring",
        "microstructure": "information half-life curve",
    },
    "mechanical_rebalance": {
        "flow": "index rebalance, ETF rebalance, risk parity rebalance",
        "event": "scheduled rebalance dates, methodology changes",
        "relative_value": "rebalance basket vs index spread",
        "liquidity": "predictable volume surge",
        "execution": "MOC, VWAP, TWAP participation",
        "seasonality": "fixed calendar, quarterly/monthly",
        "positioning": "front-running rebalance flows",
        "macro": "index methodology changes",
        "microstructure": "quote behavior pre-post rebalance",
    },
}

# Empty cells = research targets
RESEARCH_TARGETS = [
    (mech, axis)
    for mech, axes in MECHANISM_MATRIX.items()
    for axis in SideChannelAxis
    if axis.value not in axes or axes.get(axis.value, "") == ""
]


def get_research_targets() -> list[tuple[str, SideChannelAxis]]:
    """Return empty mechanism-axis pairs as research targets."""
    return RESEARCH_TARGETS


__all__ = [
    "SideChannelAxis",
    "SideChannelHypothesis",
    "InformationLead",
    "FailedReaction",
    "SyntheticResidual",
    "generate_id",
    "save_hypothesis",
    "load_hypotheses",
    "MECHANISM_MATRIX",
    "RESEARCH_TARGETS",
    "get_research_targets",
]