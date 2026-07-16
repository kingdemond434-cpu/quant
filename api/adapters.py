"""Build API contract objects from existing artifacts (read-only). No engine logic, no writes."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from api import db
from api.contracts import (
    AlertRow,
    CorrCell,
    ExecutionDashboard,
    ExposureItem,
    FamilyRank,
    FunnelStage,
    HeatCell,
    HistBin,
    KellyItem,
    Kpi,
    MonitoringDashboard,
    Orchestration,
    Overview,
    PortfolioDashboard,
    RejectionItem,
    ResearchDashboard,
    RiskDashboard,
    RiskLimit,
    WorkerInfo,
)

_FUNNEL_ORDER = ["candidate", "validation", "rejected", "shadow", "paper", "registry", "archived"]
# Static risk-framework limits mirrored from libs/risk/config.py defaults (display only).
_RISK_LIMITS = [
    ("Portfolio heat", 0.20), ("Per-position heat", 0.05), ("Max avg correlation", 0.70),
    ("CVaR / equity", 0.10), ("Kelly cap (half)", 0.50),
]


def _candidates() -> list[dict[str, Any]]:
    return db.query("SELECT * FROM research_candidates")


def _hist(values: list[float], lo: float, hi: float, bins: int = 5) -> list[HistBin]:
    step = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        if v is None:
            continue
        idx = min(bins - 1, max(0, int((v - lo) / step))) if step > 0 else 0
        counts[idx] += 1
    return [
        HistBin(bucket=f"{lo + i * step:.2f}-{lo + (i + 1) * step:.2f}", count=c)
        for i, c in enumerate(counts)
    ]


def overview() -> Overview:
    rows = _candidates()
    total = len(rows)
    survivors = sum(1 for r in rows if r.get("status") == "registry")
    campaigns = len({r.get("campaign_id") for r in rows if r.get("campaign_id")})
    dsrs = [float(r["dsr"]) for r in rows if r.get("dsr") is not None]
    alpha_score = round(min(100.0, max(0.0, (max(dsrs) if dsrs else 0.0) * 100.0)), 1)
    vel = db.query(
        "SELECT COUNT(*) AS n FROM research_candidates WHERE created_at >= datetime('now','-1 day')"
    )
    velocity = float(vel[0]["n"]) if vel else 0.0
    return Overview(
        alpha_score=alpha_score, survivors=survivors, active_campaigns=campaigns,
        live_pnl=0.0, risk_utilization=0.0, research_velocity=velocity, live=False,
        kpis=[
            Kpi(label="Candidates tested", value=total, hint="all-time"),
            Kpi(label="Best DSR", value=round(max(dsrs), 3) if dsrs else 0.0,
                hint="deflated Sharpe prob."),
            Kpi(label="Survivors", value=survivors, hint="net-of-cost, REGISTRY"),
        ],
    )


def research() -> ResearchDashboard:
    rows = _candidates()
    status_counts = Counter(r.get("status", "candidate") for r in rows)
    funnel = [FunnelStage(stage=s, count=status_counts.get(s, 0)) for s in _FUNNEL_ORDER]

    fam: dict[str, dict[str, Any]] = defaultdict(lambda: {"tested": 0, "surv": 0, "dsr": []})
    for r in rows:
        f = fam[r.get("family", "?")]
        f["tested"] += 1
        if r.get("status") == "registry":
            f["surv"] += 1
        if r.get("dsr") is not None:
            f["dsr"].append(float(r["dsr"]))
    families = sorted(
        (
            FamilyRank(
                family=name, tested=d["tested"], survivors=d["surv"],
                survivor_rate=round(d["surv"] / d["tested"], 4) if d["tested"] else 0.0,
                avg_dsr=round(sum(d["dsr"]) / len(d["dsr"]), 3) if d["dsr"] else 0.0,
            )
            for name, d in fam.items()
        ),
        key=lambda x: (x.survivor_rate, x.avg_dsr), reverse=True,
    )

    # Rejections: prefer the engine's failure report; fall back to parsing rejection_reason.
    report = db.read_report("research_lake", "failure_analysis_report") or db.read_report(
        "autodiscovery", "failure_analysis_report"
    )
    if report and isinstance(report.get("rejection_by_gate"), dict):
        rejections = [RejectionItem(gate=g, count=int(c))
                      for g, c in report["rejection_by_gate"].items()]
    else:
        gates: Counter[str] = Counter()
        for r in rows:
            reason = (r.get("rejection_reason") or "").replace("failed:", "")
            for g in (x.strip() for x in reason.split(",") if x.strip()):
                gates[g] += 1
        rejections = [RejectionItem(gate=g, count=c) for g, c in gates.most_common()]

    heat: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"n": 0, "dsr": 0.0})
    for r in rows:
        key = (r.get("family", "?"), r.get("symbol", "?"))
        heat[key]["n"] += 1
        heat[key]["dsr"] = max(heat[key]["dsr"], float(r.get("dsr") or 0.0))
    heatmap = [HeatCell(family=k[0], symbol=k[1], tested=v["n"], best_dsr=round(v["dsr"], 3))
               for k, v in heat.items()]

    return ResearchDashboard(
        funnel=funnel, families=families,
        dsr_distribution=_hist([float(r["dsr"]) for r in rows if r.get("dsr") is not None], 0, 1),
        pbo_distribution=_hist([float(r["pbo"]) for r in rows if r.get("pbo") is not None], 0, 1),
        rejections=sorted(rejections, key=lambda x: x.count, reverse=True),
        heatmap=heatmap, total_tested=len(rows),
        survivors=sum(1 for r in rows if r.get("status") == "registry"),
    )


def portfolio() -> PortfolioDashboard:
    # No live book (0 survivors): honest empty curves rather than fabricated performance.
    exposure: list[ExposureItem] = []
    kelly: list[KellyItem] = []
    corr: list[CorrCell] = []
    return PortfolioDashboard(
        equity_curve=[], drawdown=[], exposure=exposure, correlation=corr, kelly=kelly, live=False
    )


def risk() -> RiskDashboard:
    return RiskDashboard(
        var_95=0.0, expected_shortfall=0.0,
        limits=[RiskLimit(name=n, used=0.0, limit=lim) for n, lim in _RISK_LIMITS],
        kill_switch_active=False, kill_reason="", live=False,
    )


def execution() -> ExecutionDashboard:
    return ExecutionDashboard(
        mt5_connected=False, server="", orders=[], fills=0,
        avg_slippage_bps=0.0, avg_latency_ms=0.0, live=False,
    )


def orchestration() -> Orchestration:
    """Live 24/7 daemon state: campaign queue depth + worker heartbeats (read-only)."""
    rows = db.query("SELECT status, COUNT(*) AS n FROM campaigns GROUP BY status") \
        if db.table_exists("campaigns") else []
    c = {r["status"]: int(r["n"]) for r in rows}
    wrows = db.query(
        "SELECT worker_id, status, current_campaign, campaigns_done, last_seen "
        "FROM workers ORDER BY worker_id"
    ) if db.table_exists("workers") else []
    workers = [
        WorkerInfo(worker_id=str(w["worker_id"]), status=str(w["status"]),
                   current_campaign=str(w.get("current_campaign") or ""),
                   campaigns_done=int(w["campaigns_done"]), last_seen=str(w["last_seen"]))
        for w in wrows
    ]
    return Orchestration(
        queued=c.get("queued", 0), leased=c.get("leased", 0), done=c.get("done", 0),
        failed=c.get("failed", 0), depth=c.get("queued", 0) + c.get("leased", 0),
        workers=workers, running=any(w.status == "running" for w in workers),
    )


def monitoring() -> MonitoringDashboard:
    alerts_rows = db.query("SELECT * FROM alerts ORDER BY rowid DESC LIMIT 50") \
        if db.table_exists("alerts") else []
    alerts = [
        AlertRow(ts=str(a.get("created_at", a.get("ts", ""))),
                 severity=str(a.get("severity", "info")),
                 message=str(a.get("message", a.get("detail", ""))))
        for a in alerts_rows
    ]
    audit_n = db.query("SELECT COUNT(*) AS n FROM audit_log") if db.table_exists("audit_log") \
        else []
    cp = (
        db.query("SELECT value FROM lab_checkpoint WHERE key='last_campaign'")
        if db.table_exists("lab_checkpoint")
        else []
    )
    return MonitoringDashboard(
        schema_version=db.schema_version(),
        audit_chain_ok=db.table_exists("audit_log"),
        audit_entries=int(audit_n[0]["n"]) if audit_n else 0,
        db_present=db.research_db_path() is not None,
        alerts=alerts,
        last_campaign=str(cp[0]["value"]) if cp else "",
        campaign_runtime_s=0.0,
    )
