"""Dashboard API -- read-only FastAPI over the existing platform artifacts.

Run:  uvicorn api.main:app --reload --port 8000
Serves JSON for the six dashboards; CORS is open to the Next.js dev server (localhost:3000).
Changes no backend logic and never writes to the system-of-record.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import adapters
from api.contracts import (
    ExecutionDashboard,
    MonitoringDashboard,
    Orchestration,
    Overview,
    PortfolioDashboard,
    ResearchDashboard,
    RiskDashboard,
)

app = FastAPI(title="Quant Platform Dashboard API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "db_present": adapters.db.research_db_path() is not None}


@app.get("/api/overview", response_model=Overview, tags=["overview"])
def get_overview() -> Overview:
    return adapters.overview()


@app.get("/api/research", response_model=ResearchDashboard, tags=["research"])
def get_research() -> ResearchDashboard:
    return adapters.research()


@app.get("/api/portfolio", response_model=PortfolioDashboard, tags=["portfolio"])
def get_portfolio() -> PortfolioDashboard:
    return adapters.portfolio()


@app.get("/api/risk", response_model=RiskDashboard, tags=["risk"])
def get_risk() -> RiskDashboard:
    return adapters.risk()


@app.get("/api/execution", response_model=ExecutionDashboard, tags=["execution"])
def get_execution() -> ExecutionDashboard:
    return adapters.execution()


@app.get("/api/monitoring", response_model=MonitoringDashboard, tags=["monitoring"])
def get_monitoring() -> MonitoringDashboard:
    return adapters.monitoring()


@app.get("/api/orchestration", response_model=Orchestration, tags=["orchestration"])
def get_orchestration() -> Orchestration:
    return adapters.orchestration()
