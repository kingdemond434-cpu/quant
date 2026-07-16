"""API contracts -- the response schemas the frontend consumes (mirrored in lib/types.ts).

Every field is presentation data derived from existing artifacts. ``live`` flags mark panels that
require a live trading session; they are False until real execution data exists (honest by design).
"""

from __future__ import annotations

from pydantic import BaseModel


class Kpi(BaseModel):
    label: str
    value: float
    unit: str = ""
    hint: str = ""


class Overview(BaseModel):
    alpha_score: float            # 0..100 best validated candidate quality
    survivors: int                # REGISTRY-eligible
    active_campaigns: int
    live_pnl: float               # 0.0 until live (live flag below)
    risk_utilization: float       # 0..1
    research_velocity: float      # candidates tested / day (recent)
    live: bool
    kpis: list[Kpi] = []


class FunnelStage(BaseModel):
    stage: str
    count: int


class FamilyRank(BaseModel):
    family: str
    tested: int
    survivors: int
    survivor_rate: float
    avg_dsr: float


class HistBin(BaseModel):
    bucket: str
    count: int


class HeatCell(BaseModel):
    family: str
    symbol: str
    tested: int
    best_dsr: float


class RejectionItem(BaseModel):
    gate: str
    count: int


class ResearchDashboard(BaseModel):
    funnel: list[FunnelStage]
    families: list[FamilyRank]
    dsr_distribution: list[HistBin]
    pbo_distribution: list[HistBin]
    rejections: list[RejectionItem]
    heatmap: list[HeatCell]
    total_tested: int
    survivors: int


class Point(BaseModel):
    t: str
    v: float


class ExposureItem(BaseModel):
    name: str
    weight: float


class CorrCell(BaseModel):
    a: str
    b: str
    rho: float


class KellyItem(BaseModel):
    name: str
    fraction: float


class PortfolioDashboard(BaseModel):
    equity_curve: list[Point]
    drawdown: list[Point]
    exposure: list[ExposureItem]
    correlation: list[CorrCell]
    kelly: list[KellyItem]
    live: bool


class RiskLimit(BaseModel):
    name: str
    used: float
    limit: float


class RiskDashboard(BaseModel):
    var_95: float
    expected_shortfall: float
    limits: list[RiskLimit]
    kill_switch_active: bool
    kill_reason: str
    live: bool


class OrderRow(BaseModel):
    ts: str
    symbol: str
    side: str
    qty: float
    status: str


class ExecutionDashboard(BaseModel):
    mt5_connected: bool
    server: str
    orders: list[OrderRow]
    fills: int
    avg_slippage_bps: float
    avg_latency_ms: float
    live: bool


class AlertRow(BaseModel):
    ts: str
    severity: str
    message: str


class MonitoringDashboard(BaseModel):
    schema_version: int
    audit_chain_ok: bool
    audit_entries: int
    db_present: bool
    alerts: list[AlertRow]
    last_campaign: str
    campaign_runtime_s: float


class WorkerInfo(BaseModel):
    worker_id: str
    status: str
    current_campaign: str
    campaigns_done: int
    last_seen: str


class Orchestration(BaseModel):
    queued: int
    leased: int
    done: int
    failed: int
    depth: int
    workers: list[WorkerInfo] = []
    running: bool
