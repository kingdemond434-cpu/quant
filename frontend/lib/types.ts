// Mirrors api/contracts.py. Keep in sync with the backend response models.

export interface Kpi { label: string; value: number; unit: string; hint: string; }

export interface Overview {
  alpha_score: number;
  survivors: number;
  active_campaigns: number;
  live_pnl: number;
  risk_utilization: number;
  research_velocity: number;
  live: boolean;
  kpis: Kpi[];
}

export interface FunnelStage { stage: string; count: number; }
export interface FamilyRank {
  family: string; tested: number; survivors: number; survivor_rate: number; avg_dsr: number;
}
export interface HistBin { bucket: string; count: number; }
export interface HeatCell { family: string; symbol: string; tested: number; best_dsr: number; }
export interface RejectionItem { gate: string; count: number; }

export interface ResearchDashboard {
  funnel: FunnelStage[];
  families: FamilyRank[];
  dsr_distribution: HistBin[];
  pbo_distribution: HistBin[];
  rejections: RejectionItem[];
  heatmap: HeatCell[];
  total_tested: number;
  survivors: number;
}

export interface Point { t: string; v: number; }
export interface ExposureItem { name: string; weight: number; }
export interface CorrCell { a: string; b: string; rho: number; }
export interface KellyItem { name: string; fraction: number; }
export interface PortfolioDashboard {
  equity_curve: Point[]; drawdown: Point[]; exposure: ExposureItem[];
  correlation: CorrCell[]; kelly: KellyItem[]; live: boolean;
}

export interface RiskLimit { name: string; used: number; limit: number; }
export interface RiskDashboard {
  var_95: number; expected_shortfall: number; limits: RiskLimit[];
  kill_switch_active: boolean; kill_reason: string; live: boolean;
}

export interface OrderRow { ts: string; symbol: string; side: string; qty: number; status: string; }
export interface ExecutionDashboard {
  mt5_connected: boolean; server: string; orders: OrderRow[];
  fills: number; avg_slippage_bps: number; avg_latency_ms: number; live: boolean;
}

export interface AlertRow { ts: string; severity: string; message: string; }
export interface MonitoringDashboard {
  schema_version: number; audit_chain_ok: boolean; audit_entries: number;
  db_present: boolean; alerts: AlertRow[]; last_campaign: string; campaign_runtime_s: number;
}
