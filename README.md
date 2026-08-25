# quant-platform

**Autonomous MT5 Quantitative Research & Trading Desk**

One codebase, multiple run modes (`research` / `trade` / `ops`), embedded stores
(SQLite for ACID state, Parquet/DuckDB for analytics). No microservices.

## What this actually is

This is a production-grade quantitative desk running on MetaTrader 5 (Fusion Markets) with:

- **Autonomous research pipeline**: hypothesis generation → statistical gauntlet (10 gates) → forward shadow → promotion → live trading
- **Statistical rigor**: DSR, PBO/CSCV, SPA, CPCV, walk-forward, cost stress, genuine lockbox holdout
- **Forward evidence architecture**: source-provenanced bars, no-data distinction, proxy authority separation
- **Risk engineering**: per-symbol risk units, floor-aware lot sizing, forward authority ramp (CANARY states), heat budget scaled by measured k_eff
- **AI governance**: vault memory, law gates, promotion protocol, supervisor, registry, constitutional fences
- **Multi-brain deployment**: VPS + local development, Git-based state transport (code branch + mt5-state branch)

## Architecture

```
desks/mt5/
├── pipeline/           # Core research pipeline (discover → validate → shadow → promote → allocate)
├── research/           # Research modules (hunts, gates, shadow, promoter, supervisor, etc.)
├── mt5desk/            # Live execution (gateway, engine, risk_units, config)
├── data/               # Universe data, parquet caches, runtime state
├── reports/            # Gate outputs, shadow ledgers, allocation decisions
└── logs/               # Structured logs for audit
```

## Key Systems

| System | Purpose |
|--------|---------|
| `universal_gate.py` | 10-gate gauntlet (economic_prior → in_sample → DSR → PBO → SPA → CPCV → WF → stress_costs → lockbox → EV) |
| `shadow_forward.py` | Forward replay on venue-native bars, source-stamped, no-data vs quiet-market distinction |
| `promoter.py` | Auto-promotion from shadow; forward evidence cures historical power deficiencies |
| `gateway.py` | Live MT5 execution, risk-unit sizing, CANARY ramp, heat budget |
| `research_supervisor.py` | Self-healing watchdog for research processes |
| `macro_desk.py` | Macro regime state (FRED, CPI, yields, DXY) |
| `options_desk.py` | Deribit options intelligence (IV/RV, skew, term) |
| `meta_desk.py` | Cross-asset impact network, participant inference, drawdown forecaster |

## Run Modes

```bash
# Research (VPS or local)
python -m desks.mt5.research.run_hunt12
python -m desks.mt5.research.universal_gate
python -m desks.mt5.research.shadow_forward
python -m desks.mt5.research.promoter

# Live execution (VPS only, MT5 terminal required)
python -m desks.mt5.mt5desk.gateway

# Supervisor (keeps research processes alive)
python -m desks.mt5.research.research_supervisor
```

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux
pip install -e ".[dev]"

ruff check .
mypy
pytest
```

## Configuration

Layered YAML + environment variables (`QP_` prefix). Secrets via `QP_SECRET_` prefix only.

## Branches

- `master` / `desk-sync-clean` — code, configs, durable decisions
- `mt5-state` — orphan branch for runtime telemetry (shadow_health, gateway_state, sleeves, regime_state)

## Documentation

- `UNIVERSAL_PROMOTION_PROTOCOL.md` — binding promotion rules
- `CLAUDE.md` — AI agent orientation & vault search
- `AGENTS.md` — agent governance
- `desks/mt5/UNIVERSAL_PROMOTION_PROTOCOL.md` — MT5-specific promotion rules