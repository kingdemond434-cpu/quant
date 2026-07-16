# quant-platform

Solo Python → MT5 quantitative trading platform — **Architecture v1.0**.

One codebase, three run modes (`research` / `trade` / `ops`), two embedded stores
(SQLite for ACID state, Parquet/DuckDB for analytics). No microservices.

## Stage 1 — Core infrastructure (this stage)

The spine every later stage imports and never redefines:

- `pyproject.toml` — dependencies + tooling (ruff, mypy, pytest).
- `libs/core/config.py` — Pydantic settings, layered YAML + environment-variable support, config hashing.
- `libs/core/logging.py` — structured JSON logging with correlation ids + secret redaction.
- `libs/core/time.py` — UTC-only timestamp utilities (naive datetimes are rejected).
- `libs/core/reproducibility.py` — reproducibility stamps (git hash, UTC timestamp, seed, config hash, snapshot id) and verification.
- `config/` — layered configuration (`base`, `dev`, `live`, `test`) + reserved placeholders.
- `tests/core/` — full test suite for the above.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -e ".[dev]"

ruff check .
mypy
pytest
```

## Configuration precedence (highest first)

1. Explicit `overrides=` passed to `load_settings(...)`
2. Environment variables (`QP_` prefix, `__` nested delimiter, e.g. `QP_LOGGING__LEVEL=DEBUG`)
3. `config/<environment>.yaml`
4. `config/base.yaml`

Environment is selected by `QP_ENV` (default `dev`).
Secrets are read only from the secrets provider (env prefix `QP_SECRET_`), never from config files or logs.
