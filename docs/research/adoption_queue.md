# Adoption Queue — deferred tooling (build nothing until the trigger fires)

Tier-2 and deferred Tier-1 items from the REPO EXTRACTION DIRECTIVE (see `docs/REPO_EXTRACTION.md`).
Each is a METHOD to own when its precondition exists — not a dependency to add now. Re-check on the
monthly prospector sweep.

| Item | Source | Method to own | TRIGGER (precondition) | Reuse if wired |
|---|---|---|---|---|
| Factor scoring | alphalens / alphalens-reloaded | factor IC, decay-by-horizon, quantile spreads, turnover | **first validated candidate exists to score** | `libs/research/ic.py`, `information_value.py` |
| Portfolio construction | PyPortfolioOpt + riskparity.py | HRP, risk-parity, Ledoit-Wolf shrinkage, constrained optimisation | **≥2 uncorrelated validated alphas to allocate between** | orphaned `libs/portfolio/{hrp,optimize,covariance,risk_parity}` — wire these, don't re-import |
| Feature factory | tsfresh | automated TS feature extraction | **feature factory operational AND trials ledger counting live** (never a blind sweep — every feature is a DSR trial) | `libs/features/registry.py`, `pit.py`; DSR in `libs/validation/dsr.py` |
| Fractional differentiation | mlfinlab (AFML ch. 5) | stationarity-preserving memory-preserving transform | **a supervised / stationary-feature alpha enters the pipeline** | `libs/features/` |
| Dollar / volume bars | mlfinlab (AFML ch. 2) | information-driven bar sampling | **a bar-sampled (non-time-bar) alpha enters the pipeline** | `libs/data/` |
| Structural sim/live dedup | nautilus_trader | one code path for backtest + live weights | **operator approves a `_book` refactor + full backtest re-run** (see parity finding) | `libs/research/crypto_sleeves.py` |

Rules: extract the method (owned, small) not the dependency; pin versions; vet licences; log to the
complexity budget with what it replaced/prevented; every screened feature counts in the trials
ledger under explicit DSR accounting.
