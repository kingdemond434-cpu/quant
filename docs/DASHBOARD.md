# Quant Desk — Dashboard

A production-grade, read-only quantitative research dashboard for the existing Python platform.
**No backend logic is changed.** A thin FastAPI layer reads the existing SQLite system-of-record
and the JSON reports the engines already emit; the Next.js app renders them.

## Architecture

```
MT5 / engines  ──writes──►  SQLite (system-of-record) + reports/*.json
                                     │  (read-only)
                                     ▼
                            api/  (FastAPI adapters)  ──HTTP/JSON──►  frontend/ (Next.js)
```

## File structure

```
api/                         # read-only presentation API (Python)
  main.py                    # FastAPI app + routes (one per dashboard)
  adapters.py                # builds contract objects from DB + reports
  contracts.py               # Pydantic response schemas (API contract)
  db.py                      # read-only sqlite (mode=ro) + report readers
  requirements.txt
frontend/                    # Next.js 14 (App Router) + TS + Tailwind + Recharts
  app/
    layout.tsx               # shell: sidebar nav + grid background
    page.tsx                 # 1. Executive Overview
    research/page.tsx        # 2. Research (funnel, heatmap, DSR/PBO, rejections)
    portfolio/page.tsx       # 3. Portfolio (equity, exposure, corr, Kelly, drawdown)
    risk/page.tsx            # 4. Risk (VaR, ES, limits, kill-switch)
    execution/page.tsx       # 5. Execution (MT5, orders, fills, slippage, latency)
    monitoring/page.tsx      # 6. Monitoring (DB health, audit chain, alerts, campaigns)
    globals.css              # dark institutional theme
  components/
    nav.tsx                  # sidebar
    ui.tsx                   # Card / Badge / Table primitives (shadcn-style)
    widgets.tsx              # StatCard, Panel, Recharts wrappers, Heatmap, LimitBar, EmptyLive
  lib/
    api.ts                   # typed fetch + usePoll() real-time hook
    types.ts                 # TS mirror of api/contracts.py
    utils.ts                 # cn() + formatters
  tailwind.config.ts, tsconfig.json, package.json, ...
```

## Run

```bash
# 1) API (from repo root, in the platform venv)
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000          # http://localhost:8000/docs

# 2) Frontend
cd frontend
cp .env.local.example .env.local                    # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                                          # http://localhost:3000
```

## API contracts (GET, JSON)

| Endpoint | Returns | Source |
|---|---|---|
| `/api/overview` | `Overview` | `research_candidates` + reports |
| `/api/research` | `ResearchDashboard` | `research_candidates` + `failure_analysis_report` |
| `/api/portfolio` | `PortfolioDashboard` | live book (empty until survivors funded) |
| `/api/risk` | `RiskDashboard` | risk-framework limits; utilization 0 with no live book |
| `/api/execution` | `ExecutionDashboard` | MT5/EA telemetry (empty until live) |
| `/api/monitoring` | `MonitoringDashboard` | schema version, audit log, alerts, checkpoint |

Schemas are defined once in `api/contracts.py` and mirrored in `frontend/lib/types.ts`.

## Honesty by design

Panels that need a live trading session (Portfolio, Execution, parts of Risk) render explicit
**“no live data”** states rather than fabricated curves — there are currently **0 net-of-cost
survivors**, so there is no book to show. Research/Monitoring render **real** data from the
research runs. Real capital is never allocated automatically.

## Real-time

Every page uses `usePoll(path, intervalMs)` (default 4–5 s, `cache: "no-store"`). Swap to SSE or
WebSockets later by replacing the hook; the components are agnostic.
