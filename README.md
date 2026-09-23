# quant-platform

**An autonomous quantitative research and trading desk that trades the MT5 / Fusion Markets
universe through a single broker connection.**

## Read this first — what this desk trades, and what it does not

- **The universe is MT5/Fusion Markets, and only that:** FX majors, crosses and exotics; gold
  (XAUUSD) and silver and the other metals; equity indices; energy; soft commodities; US share
  CFDs; and the crypto CFDs Fusion itself lists. One broker connection, one book.
- **The live desk is `desks/mt5/`.** That directory is the money path: `desks/mt5/mt5desk/`
  executes (gateway, risk units, heat budget), `desks/mt5/research/` discovers and validates, and
  `desks/mt5/reports/` is where gate outputs, shadow ledgers and allocation decisions land. If you
  are looking for the code that can move real money, it is `desks/mt5/mt5desk/gateway.py`.
- **The crypto-exchange desk that used to live in this repository was RETIRED on 2026-08-18** by
  standing principal order. No Binance, Bybit, OKX, Deribit or Hyperliquid venue is traded,
  hunted, screened or scored, and none may be again. Crypto reference data is admissible only
  where a specific reading informs a Fusion-executable MT5 instrument — never as a universe of
  its own.
- **The crypto era's records are kept on purpose, and they are archived, not active.**
  `docs/graveyard.md`, `docs/institutional_knowledge.md`, `docs/research/negative_knowledge.md`,
  `docs/research/blind_rediscovery_log.md`, `docs/research/deep_sweep/`, `docs/audit_shards/` and
  `docs/research/archive_crypto_era/` are the record of what was tried and what failed. They are
  the most valuable thing in this repository. Read them as a lab notebook from a discontinued
  programme: the protocols and the measured negatives transfer, the venues do not.

> If a file anywhere in this repository reads as a live mandate to hunt a crypto exchange, it is
> stale and it is a defect — the mandate in `CLAUDE.md` and `docs/LAWS.md` overrides it.

One codebase, multiple run modes (`research` / `trade` / `ops`), embedded stores
(SQLite for ACID state, Parquet/DuckDB for analytics). No microservices.

## What the desk is optimising

    max E[log W]   after costs, slippage, uncertainty, correlation, tails, capacity and turnover

That is the whole objective function — not Sharpe, not a smooth equity curve, not "avoid losing
trades". Drawdown enters only through future geometric wealth and survivability. Two bounds sit
on it, and they are asymmetric on purpose:

- **A 20% gross-heat floor is a STANDING MANDATE** — capital is at work 24/7, and the floor does
  not ramp with readiness. Its growth cost is *measured every pass*, never assumed:
  `heat_policy.heat_accounting` writes what the floor gave up, per day and per year, whenever the
  floor was the binding constraint.
- **There is no fixed ceiling.** The old 30% cap was removed on 2026-09-05 by principal order.
  The bound above the floor is read off the measured growth curve each pass
  (`desks/mt5/research/heat_policy.measured_ceiling`) and moves both ways — above 30% when new
  edges support it, below 30% when the opportunity set is thin. It is never set past the last
  heat actually sampled, never past the point where growth turns over, and an unreadable curve
  falls back to the recorded constant: absence is never permission.

`docs/GROWTH_GOVERNANCE.md` is the binding statement of all of this.

## What this actually is

This is a production-grade quantitative desk running on MetaTrader 5 (Fusion Markets) with:

- **Autonomous research pipeline**: hypothesis generation → statistical gauntlet (10 gates) → forward shadow → promotion → live trading
- **Statistical rigor**: DSR, PBO/CSCV, SPA, CPCV, walk-forward, cost stress, genuine lockbox holdout
- **Forward evidence architecture**: source-provenanced bars, no-data distinction, proxy authority separation
- **Risk engineering**: per-symbol risk units, floor-aware lot sizing, forward authority ramp (CANARY states), and a heat budget bounded by a ceiling *measured from the growth curve* rather than decreed (see the objective below)
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
| `options_desk.py` | Options intelligence (IV/RV, skew, term structure) on the MT5 book's underlyings |
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

**Start here, in this order:**

1. `docs/LAWS.md` — canonical law. Where a doc and a law disagree, the law wins.
2. `docs/GROWTH_GOVERNANCE.md` — the risk mandate: the objective, the 20% floor, the measured
   ceiling, and what every rail costs in growth.
3. `docs/UNIVERSAL_PROMOTION_PROTOCOL.md` — binding promotion rules
   (`desks/mt5/UNIVERSAL_PROMOTION_PROTOCOL.md` for the MT5-specific ones).
4. `CLAUDE.md` / `AGENTS.md` — agent orientation and governance.

**The desk's memory — read this before concluding anything is unexplored.** These are the record
of what was tried and what failed, and they are deliberately preserved rather than tidied away:

- `docs/graveyard.md` — every retired hypothesis and why it died.
- `docs/institutional_knowledge.md`, `docs/desk_lessons.jsonl` — the lessons, dated.
- `docs/research/negative_knowledge.md` — measured negatives; the most reusable asset here.
- `docs/research/blind_rediscovery_log.md` — what the desk re-derived independently.
- `docs/research/deep_sweep/`, `docs/research/capability_hunt/`, `docs/audit_shards/` — the
  discovery logs.
- `docs/research/archive_crypto_era/` — the retired crypto-exchange desk's own specs, kept as a
  lab notebook from a discontinued programme. Read the protocols and the measured negatives;
  the venues are out of scope and may not be hunted again.

A reviewer should treat a claim that something is untried as false until checked against these.