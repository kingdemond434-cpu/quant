"""Autonomous research-lab models — families, market series, hypotheses, verdicts, candidates.

The lab tests pre-declared, economically-grounded hypotheses (each carries its mechanism, edge
source, and expected failure modes BEFORE testing) and records every outcome. Reuses the
validation layer's ``MechanismType``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from libs.core.time import to_iso8601, utcnow
from libs.validation.economic_prior import MechanismType


class Family(StrEnum):
    TREND = "trend"
    MOMENTUM = "momentum"
    BREAKOUT = "breakout"
    VOLATILITY_EXPANSION = "volatility_expansion"
    VOLATILITY_COMPRESSION = "volatility_compression"
    MEAN_REVERSION = "mean_reversion"
    SESSION = "session"
    CROSS_ASSET = "cross_asset"
    CARRY = "carry"
    REGIME_TRANSITION = "regime_transition"
    LIQUIDITY = "liquidity"
    RISK_PREMIA = "risk_premia"


class CandidateStatus(StrEnum):
    CANDIDATE = "candidate"
    VALIDATION = "validation"
    REJECTED = "rejected"
    SHADOW = "shadow"
    PAPER = "paper"
    REGISTRY = "registry"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class MarketSeries:
    """Columnar OHLC(+volume/hour/reference) view for backtesting a hypothesis."""

    close: np.ndarray
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray | None = None
    hour: np.ndarray | None = None       # bar hour-of-day (server time), for session effects
    ref_close: np.ndarray | None = None  # a second instrument, for cross-asset relationships
    funding: np.ndarray | None = None    # per-bar perp funding rate (Level-3), for crypto signals

    def __len__(self) -> int:
        return len(self.close)


class Hypothesis(BaseModel):
    """A pre-declared, economically-grounded hypothesis (mechanism stated before testing)."""

    model_config = ConfigDict(frozen=True)

    family: Family
    subtype: str
    symbol: str
    params: dict[str, float]
    mechanism: MechanismType
    edge_source: str
    failure_modes: list[str] = Field(default_factory=list)


class ValidationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    annual_sharpe: float = 0.0
    expected_value: float = 0.0
    oos_sharpe: float = 0.0
    dsr: float = 0.0
    pbo: float = 0.0
    reality_p: float = 1.0
    capacity_usd: float = 0.0
    fragility: float = 0.0


class ValidationVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    survived: bool
    gates: dict[str, bool]
    rejection_reason: str
    metrics: ValidationMetrics


class CandidateRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    created_at: str
    updated_at: str
    campaign_id: str
    family: str
    subtype: str
    symbol: str
    params: dict[str, float]
    content_hash: str
    status: CandidateStatus
    mechanism: str
    metrics: ValidationMetrics
    survived: bool
    rejection_reason: str | None


class CycleResult(BaseModel):
    """The outcome of one autonomous lab cycle (recommend-only; never allocates real capital)."""

    model_config = ConfigDict(frozen=True)

    campaign_id: str
    generated: int = 0
    tested: int = 0
    skipped_duplicate: int = 0
    # Screened out by the graveyard novelty gate BEFORE any backtest compute. Counted apart from
    # skipped_duplicate because they are a different claim: a duplicate is provably the same
    # hypothesis, a redundant one is a re-proposal of a mechanism already killed elsewhere.
    skipped_redundant: int = 0
    survivors: int = 0
    rejected: int = 0
    promoted_to_shadow: int = 0
    promoted_to_paper: int = 0
    promoted_to_registry: int = 0
    generated_at: str = Field(default_factory=lambda: to_iso8601(utcnow()))
