# BLIND-SPOT AUDIT — exhaustive maximization sweep

Executed 2026-07-23 in response to "exhaust everything and every blind spot; maximise every area."
Method: for each area of the desk, cross-check the codebase against the current public frontier
(repos, datasets, online quant resources) and the desk's own coverage docs, then classify every
candidate improvement as **COVERED**, **CORRECTLY-DEFERRED** (a real thing, gated on a precondition),
or **GENUINE GAP** (actionable now).

## Headline (honest)

**The sweep's dominant result is that the frontier is already swept.** Every concrete "you forgot X"
hypothesis tested during this audit resolved to COVERED or CORRECTLY-DEFERRED:

- Options / vol surface? Built — `collect_deribit_surface.py`, `run_options_vrp_backtest.py`,
  `deribit.fetch_dvol` + skew interpolation.
- Reproducible/pinned deploy env? Built — `requirements-vps.txt` / `requirements-deploy.txt` pin
  exact versions (`numpy==2.4.6`, `pandas==2.3.3`, `pyarrow==24.0.0`).
- OSS engine frontier (nautilus / qlib / Lean / hummingbot / freqtrade)? Benchmarked
  dimension-by-dimension in `docs/research/oss_benchmark.md`, with the correct verdict (rent the
  chassis only if an intraday edge validates; the governance layer is the un-replicable asset).
- Free data axes (Korean/JP venues, AWS Public Blockchain Data, stablecoin mint/burn, on-chain
  labels, MEV `eth-labels`)? Swept + graded in `data_axis_watchlist.md`.
- AI-as-oracle agent swarms (Vibe-Trading, ai-hedge-fund)? Correctly REJECTED by constitution.
- Deep-RL (FinRL / TradeMaster)? Correctly REJECTED (overfitting surface).

**The binding constraint is not idea-supply or tooling — it is calendar-time data accumulation and a
validated forward edge** (the desk's own `research_state.json` and `GAP_ANALYSIS.md` say exactly
this). Neither can be engineered away by adding repos, datasets, or features. Piling on more is
negative-EV by the desk's own complexity budget. This audit therefore does **not** recommend a long
adoption list; it recommends protecting the data clock and holding the validation bar.

## Per-area map

| Area | Status | Evidence / note |
|---|---|---|
| Validation / anti-overfitting | **COVERED — best-in-class** | DSR+PBO+CPCV+SPA+RC+lockbox+revalidation; no public peer matches it |
| Research governance | **COVERED — no public equivalent** | EV gate, decision ledger, graveyard priors, negative-knowledge registry, forecast calibration |
| Risk governance | **COVERED** | E[log] objective, endogenous Kelly/ruin caps, pure-stdlib deadman rail, kill switches |
| Data sources (free) | **COVERED + ongoing** | `data_axis_watchlist.md` graded sweeps; forward clocks on OI/LS/liq/stablecoin |
| Options / vol surface | **COVERED** | Deribit surface + DVOL + VRP backtest already built |
| Execution engine | **CORRECTLY-DEFERRED** | REST 10-min cadence is adequate for carry; nautilus/Lean chassis gated on a validated intraday edge |
| Alpha breadth | **CONSTRAINT (un-engineerable now)** | ~7 funding-correlated sleeves; more breadth needs forward DATA, not more generation compute |
| Validated forward edge | **CONSTRAINT (un-engineerable)** | 0 survivors; only calendar time resolves this |
| Backtest fill realism | **GAP → CLOSED this session** | queue-position + latency maker fill (`libs/backtest/queue_fill.py`) |
| Live↔backtest parity | **GAP → FLAGGED this session** | inverse-vol lag divergence (`_book` vs `latest_weights`); guard test added, reconcile is operator's call |
| CI / pre-merge gate | **GAP → CLOSED this session** | `.github/workflows/ci.yml`; the tree's `ruff`/`mypy` were red on arrival, now green |
| Baseline benchmarking | **GAP → CLOSED this session** | naive-baseline scorecard (`libs/validation/baselines.py`) |

## The only genuine residuals (small, honest)

Everything else is covered or a real constraint. What actually remains, ranked:

1. **Reconcile the live↔backtest signal/vol timing** (found this session; refined on closer look).
   The inverse-vol shift is NOT a bug — `_book` lags vol because it applies weights same-bar, while
   `latest_weights` applies them to the next (forward) bar; that's the same rule in two conventions.
   The genuine residual is narrower: `latest_weights` reads the **signal** at `iloc[-2]` but
   inverse-vol at `iloc[-1]` — a one-bar signal/vol offset the aligned `_book` doesn't have. The
   correct fix direction depends on whether the lake's last D1 bar is complete or forming at runtime
   (if complete, the signal is one bar stale; if forming, the vol wrongly uses a partial bar), which
   is a runtime fact not visible in code. Because closing it moves live positions and the direction
   is genuinely ambiguous, it is **not auto-changed** (profit-preservation). Current behavior is now
   pinned by a characterization test (`test_live_backtest_parity.py`) so it cannot drift silently;
   the operator should confirm the bar-completeness semantics and backtest the aligned variant.
2. **Wire the orphaned Research OS** (`libs/store/*` reproducibility + experiment registry) **only if
   sleeve count crosses the documented >5–10-survivor trigger.** Until then, flat JSON state is the
   correct, cheaper choice (per `GAP_ANALYSIS.md`) — not a gap, a deliberate deferral.
3. **Property/mutation testing on the risk path** — already a *known* required gate for the GAP-19
   circuit breaker; not a blind spot, a tracked precondition.

## What "maximise everything" correctly does NOT mean here

- Not more hypothesis-generation compute over the same price/derivative data (10/11 mechanisms
  already graveyarded; the meta-learner gates `price_only` at 0.30).
- Not migrating to nautilus/Lean at a 10-min cadence (rewrite risk + weeks of effort for zero growth).
- Not agent-swarm / LLM-oracle trade selection (banned by constitution — AI is engineer + adversary).
- Not deep-RL (overfitting, uninterpretable).
- Not adopting Tier-2 tooling (alphalens / PyPortfolioOpt / tsfresh) before its precondition — those
  are queued with triggers in `docs/research/adoption_queue.md`; building them now adds code that
  prevents nothing.

**Standing conclusion:** the desk is comprehensively built and honestly governed. The frontier that
remains is time (forward data maturing on the clocks) and edge (something surviving the gauntlet
forward) — both bought with patience, not code. The right maximisation is to keep the flywheel alive,
protect the data clocks, and refuse to spend the complexity budget on anything that does not clear
the bar it sets.
