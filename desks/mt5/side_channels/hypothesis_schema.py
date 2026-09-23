"""Canonical Hypothesis Schema — the single research object all miners produce."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from enum import Enum
import json
import uuid


class MechanismClass(Enum):
    """Independent economic mechanism classes."""
    FORCED_FLOW = "forced_flow"
    INFORMATION_SHOCK = "information_shock"
    INVENTORY_IMBALANCE = "inventory_imbalance"
    CROWDING_UNWIND = "crowding_unwind"
    SLOW_DIFFUSION = "slow_diffusion"
    MECHANICAL_REBALANCE = "mechanical_rebalance"
    RELATIVE_VALUE = "relative_value"
    EXECUTION_ALPHA = "execution_alpha"
    CARRY_REGIME = "carry_regime"
    REGIME_TRANSITION = "regime_transition"
    UNKNOWN = "unknown"


class EvidenceTier(Enum):
    """Evidence quality tiers."""
    PRIMARY_PUBLIC = "primary_public"           # direct observation, official source
    SECONDARY_PUBLIC = "secondary_public"       # reported, aggregated
    PRACTITIONER_CLAIM = "practitioner_claim"   # blog, video, forum
    CODE_DERIVED = "code_derived"               # extracted from public code
    LEADERBOARD_BEHAVIOR = "leaderboard_behavior"  # inferred from public track record
    TRANSLATION_GAP = "translation_gap"         # foreign concept not in English corpus
    UNKNOWN_UNKNOWN = "unknown_unknown"         # new data category


class HypothesisStatus(Enum):
    DISCOVERED = "discovered"
    CHEAP_SCREENED = "cheap_screened"
    HEAVY_QUEUED = "heavy_queued"
    VALIDATING = "validating"
    SHADOW = "shadow"
    PROMOTION_CANDIDATE = "promotion_candidate"
    LIVE_CANARY = "live_canary"
    LIVE_FULL = "live_full"
    RETIRED = "retired"
    REJECTED = "rejected"


@dataclass
class Origin:
    """Where this hypothesis came from."""
    region: str                           # "china", "japan", "global", "us", etc.
    language: str                         # "en", "zh", "ja", "ko", "ru", "pt", "es", "ar"
    source_type: str                      # "youtube", "github", "bilibli", "arxiv", "leaderboard", "event", "broker", etc.
    source_id: str                        # specific channel, repo, account, URL
    source_url: str | None = None
    evidence_tier: EvidenceTier = EvidenceTier.PRACTITIONER_CLAIM
    collected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    collector_version: str = "1.0"
    metadata: dict = field(default_factory=dict)


@dataclass
class Mechanism:
    """The economic mechanism driving the edge."""
    mechanism_class: MechanismClass
    participant: str                      # who is forced/informed (e.g., "ETF_AP", "option_dealer", "commodity_hedger")
    constraint: str                       # what forces them (e.g., "must_rebalance", "delta_hedge", "margin_call")
    information_source: str               # where the info originates (e.g., "warehouse_receipts", "fixing_window", "trump_post")
    why_edge_should_exist: str            # plain English rationale
    information_propagation: str | None = None  # how it reaches the tradable instrument
    persistence: str | None = None        # how long the edge should last
    kill_conditions: list[str] = field(default_factory=list)  # what would invalidate


@dataclass
class MarketContext:
    """Market specification for the hypothesis."""
    symbols: list[str]                    # MT5/Fusion symbols (e.g., ["XAUUSD", "USDCAD"])
    primary_symbol: str
    timeframe: str = "H1"
    session: str | None = None            # "asia", "london_am", "ny_open", "afternoon", "all"
    regime_required: list[str] = field(default_factory=list)  # e.g., ["trend", "high_vol"]
    regime_excluded: list[str] = field(default_factory=list)


@dataclass
class Rule:
    """Exact executable trading rule."""
    inputs: list[str]                     # required data inputs
    trigger: str                          # exact entry condition
    direction: Literal[1, -1, 0]          # +1 long, -1 short, 0 neutral/both
    holding_horizon: str                  # e.g., "15m", "1h", "4h", "1d"
    exit: str                             # exact exit condition
    stop: str | None = None               # stop loss
    trail: str | None = None              # trailing stop
    re_entry: str | None = None           # re-entry rule
    position_scaling: str | None = None   # scaling logic
    max_positions: int = 1
    filters: dict = field(default_factory=dict)  # additional filters


@dataclass
class Economics:
    """Economic rationale and risk assessment."""
    expected_edge_bps_per_trade: float
    expected_trades_per_month: int
    expected_capacity_lots: float
    expected_capacity_category: Literal["micro", "small", "medium", "large", "institutional"]
    correlation_with_existing: dict[str, float] = field(default_factory=dict)  # family -> correlation
    orthogonality_score: float = 1.0      # 0-1, higher = more independent
    execution_risk: str = "normal"        # "low", "normal", "high"
    leakage_risk: str = "low"             # "low", "medium", "high"


@dataclass
class Falsifier:
    """What would disprove this hypothesis."""
    condition: str
    horizon: str                          # e.g., "50_trades", "3_months"
    threshold: float                      # e.g., "exp_r < 0.05R"
    data_source: str                      # where to get the evidence


@dataclass
class Novelty:
    """Novelty assessment."""
    nearest_existing_family: str | None = None
    similarity: float = 1.0               # 0-1, lower = more novel
    translation_gap: bool = False
    translation_gap_details: str | None = None
    unknown_unknown: bool = False


@dataclass
class Costs:
    """Research and execution cost estimates."""
    research_cost_usd: float = 0.0
    research_cost_hours: float = 0.0
    data_cost_usd_monthly: float = 0.0
    execution_cost_bps_per_trade: float = 0.0


@dataclass
class HypothesisCard:
    """The canonical hypothesis card — all miners output this."""
    # Identity
    id: str = field(default_factory=lambda: f"H-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}")
    version: int = 1
    parent_id: str | None = None          # for mutations
    
    # Origin
    origin: Origin = field(default_factory=Origin)
    
    # Core
    mechanism: Mechanism = field(default_factory=Mechanism)
    market: MarketContext = field(default_factory=MarketContext)
    rule: Rule = field(default_factory=Rule)
    
    # Economics & Risk
    economics: Economics = field(default_factory=Economics)
    falsifier: Falsifier = field(default_factory=Falsifier)
    novelty: Novelty = field(default_factory=Novelty)
    costs: Costs = field(default_factory=Costs)
    
    # Status & Pipeline
    status: HypothesisStatus = HypothesisStatus.DISCOVERED
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    
    # Attribution & Learning
    source_attribution: dict = field(default_factory=dict)  # source -> contribution
    miner_attribution: dict = field(default_factory=dict)   # miner -> contribution
    validation_history: list[dict] = field(default_factory=list)
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict with enum handling."""
        d = asdict(self)
        # Convert enums to values
        d["origin"]["evidence_tier"] = self.origin.evidence_tier.value
        d["mechanism"]["mechanism_class"] = self.mechanism.mechanism_class.value
        d["status"] = self.status.value
        d["economics"]["expected_capacity_category"] = self.economics.expected_capacity_category
        return d

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        import yaml
        return yaml.dump(self.to_dict(), sort_keys=False, allow_unicode=True)

    @classmethod
    def from_dict(cls, d: dict) -> "HypothesisCard":
        """Deserialize from dict."""
        # Handle nested enums
        if "origin" in d and "evidence_tier" in d["origin"]:
            d["origin"]["evidence_tier"] = EvidenceTier(d["origin"]["evidence_tier"])
        if "mechanism" in d and "mechanism_class" in d["mechanism"]:
            d["mechanism"]["mechanism_class"] = MechanismClass(d["mechanism"]["mechanism_class"])
        if "status" in d:
            d["status"] = HypothesisStatus(d["status"])
        if "economics" in d and "expected_capacity_category" in d["economics"]:
            d["economics"]["expected_capacity_category"] = d["economics"]["expected_capacity_category"]
        
        # Convert nested dataclasses
        d["origin"] = Origin(**d.get("origin", {}))
        d["mechanism"] = Mechanism(**d.get("mechanism", {}))
        d["market"] = MarketContext(**d.get("market", {}))
        d["rule"] = Rule(**d.get("rule", {}))
        d["economics"] = Economics(**d.get("economics", {}))
        d["falsifier"] = Falsifier(**d.get("falsifier", {}))
        d["novelty"] = Novelty(**d.get("novelty", {}))
        d["costs"] = Costs(**d.get("costs", {}))
        
        return cls(**d)

    def save(self, path: Path) -> None:
        """Save to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "HypothesisCard":
        """Load from YAML file."""
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            d = yaml.safe_load(f)
        return cls.from_dict(d)


# Example hypothesis card
EXAMPLE_HYPOTHESIS = HypothesisCard(
    id="H-20260824-ABC123",
    origin=Origin(
        region="china",
        language="zh",
        source_type="exchange_research",
        source_id="shfe_warehouse_reports",
        source_url="https://www.shfe.com.cn/warehouse/",
        evidence_tier=EvidenceTier.PRIMARY_PUBLIC,
    ),
    mechanism=Mechanism(
        mechanism_class=MechanismClass.FORCED_FLOW,
        participant="commodity_hedgers",
        constraint="must_hedge_revenue_per_budget",
        information_source="SHFE_daily_warehouse_receipts",
        why_edge_should_exist="Chinese commodity producers must hedge per budget cycle, creating predictable futures selling pressure at month-end that spills to FX via USD/CNY",
        information_propagation="warehouse_receipts -> futures_basis -> CNY_spot -> XAUUSD/USDCNH",
        persistence="monthly_cycle",
        kill_conditions=["policy_change_hedge_accounting", "SHFE_delisting"],
    ),
    market=MarketContext(
        symbols=["XAUUSD", "USDCNH", "XAGUSD"],
        primary_symbol="XAUUSD",
        timeframe="H1",
        session="london_am",
        regime_required=["normal", "trend"],
        regime_excluded=["crisis"],
    ),
    rule=Rule(
        inputs=["SHFE_warehouse_receipts_daily", "USDCNH_H1", "XAUUSD_H1"],
        trigger="warehouse_receipts_increase > 2std AND USDCNH > 20d_ma",
        direction=-1,  # short gold
        holding_horizon="4h",
        exit="warehouse_receipts_decrease OR 4h_timeout",
        stop="1.5x_ATR_14",
        trail="0.5x_ATR_14",
        re_entry="if_receipts_still_increasing_next_session",
        filters={"min_receipts_change_pct": 5.0, "max_spread_bps": 20},
    ),
    economics=Economics(
        expected_edge_bps_per_trade=8.5,
        expected_trades_per_month=12,
        expected_capacity_lots=50,
        expected_capacity_category="small",
        correlation_with_existing={"breakout": 0.12, "trend": 0.08},
        orthogonality_score=0.92,
    ),
    falsifier=Falsifier(
        condition="exp_r < 0.05R over 100 forward trades",
        horizon="100_trades",
        threshold=0.05,
        data_source="shadow_forward",
    ),
    novelty=Novelty(
        nearest_existing_family="carry_trend",
        similarity=0.18,
        translation_gap=True,
        translation_gap_details="Chinese warehouse receipts not in English research corpus",
    ),
    costs=Costs(
        research_cost_usd=50.0,
        research_cost_hours=2.0,
        data_cost_usd_monthly=0.0,
        execution_cost_bps_per_trade=1.2,
    ),
    tags=["china", "commodity", "forced_flow", "warehouse_receipts", "translation_gap"],
)


if __name__ == "__main__":
    import yaml
    print("Example Hypothesis Card:")
    print(EXAMPLE_HYPOTHESIS.to_yaml())
    
    # Test round-trip
    reloaded = HypothesisCard.from_dict(json.loads(json.dumps(EXAMPLE_HYPOTHESIS.to_dict())))
    print(f"\nReloaded ID: {reloaded.id}")
    print(f"Mechanism: {reloaded.mechanism.mechanism_class.value}")
    print(f"Status: {reloaded.status.value}")