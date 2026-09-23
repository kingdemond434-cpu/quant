# Pre-registration — intraday rotation/continuation on Binance USD-M perps

> **ARCHIVED 2026-09-05 — the retired crypto-exchange era.** This document is a HISTORICAL
> RECORD, not a live mandate. The desk's traded and hunted universe is the MT5/Fusion Markets
> book (principal order 2026-08-18); the crypto-exchange desk this study belonged to was
> retired that day. Nothing here authorizes hunting, screening or scoring a crypto-exchange
> universe. Kept because the protocol and the measured negative transfer; the venue does not.
> See `docs/research/archive_crypto_era/README.md`.

**Written 2026-08-04, BEFORE any bar of crypto data was downloaded for this study and before any
backtest code existed.** Source: the principal's discretionary XAUUSD intraday book (11 trades,
5 days, 0.1 lots, M5/M15, net +933.72 EUR, 10 winners, largest win 470.56 = 50.4% of P&L, single
loss −27.68, manual early exits) plus the principal's full research spec, which this file pins
verbatim. **n=11 is a hypothesis, not an edge**: a 91% hit rate over 11 trades is consistent with
anything from a 55% true edge to a lucky trending week. The build's objective is to FALSIFY; a
rigorous negative is a successful output.

## Fixed before first run — the full grid

- **Universe**: BTCUSDT, ETHUSDT, SOLUSDT USD-M perps. Data: Binance Vision monthly 5m klines
  (build), 1m for fill verification of the top-2 configs, monthly funding-rate archive. ≥3 years.
- **Regime per bar (5m)**: ATR(20) realized vol + efficiency ratio ER(48) = |close−close[−48]| /
  Σ|Δclose|. RANGE: ER < 0.25. TREND: ER > 0.45. Else TRANSITION. Regimes are TESTED SEPARATELY,
  never pooled.
- **Rotation entries (RANGE only)**: rolling N-bar high/low, N ∈ {24, 48, 96}. Long: price in
  lower quartile of the N-range AND rejection bar (close in upper third of bar's own range).
  Short: mirror. **Location filter**: reject unless distance to opposing boundary ≥ 2× distance
  to stop.
- **Continuation entries (TREND, post-breakout)**: close beyond N-range boundary with bar range
  > 1.5× ATR(20); enter on FIRST pullback (limit at the broken boundary); cancel if unfilled
  within K ∈ {6, 12, 24} bars; count and report unfilled-runaway losses.
- **Stops**: beyond the defining swing + 0.25× ATR(20) buffer. Hard time stop M ∈ {24, 48, 96}
  bars.
- **Exit variants, each reported separately**: (a) fixed R ∈ {1.5, 2, 3}; (b) opposing range
  boundary; (c) source-mimicking: 50% off at 0.75R, trail remainder on 5m swings.
- **Costs**: taker 4 bps on market legs (entries on rejection closes, stop exits), maker 2 bps
  on limit fills (continuation entries, boundary targets), plus 1 bp slippage on taker legs.
  Funding applied whenever a position is open at 00:00/08:00/16:00 UTC, from the historical
  archive.
- **Sizing is UNDER TEST, not assumed** (and the desk's R0143 fence stands regardless: whatever
  this sweep says, live size is owned by fractional-Kelly, and the principal's 3–5% ask is
  evaluated, not adopted). Sweep risk-per-trade ∈ {0.25%, 0.5%, 1%, 2%, 3%, 5%}; report per
  level, on stationary-bootstrap resamples of the OOS trade sequence (≥2,000 paths): median
  terminal equity, median and 95th-pct max drawdown, P(DD > 50%), P(equity < 20% start),
  longest losing streak and its implied DD, and the half-Kelly fraction with CI, stating
  explicitly whether 3–5% sits inside it. The arithmetic is fixed now: at 4% risk, a 10-loss
  streak = −33.5%, a 20-loss streak = −55.6%.
- **Validation, non-negotiable**: walk-forward 6-month train / 2-month test, rolled; OOS only is
  reported. Parameter plateaus reported, never peaks. Regime buckets 2023 / 2024 / 2025-26
  reported separately. No expectancy quoted below 200 OOS trades; win-rate CI stated. Nulls:
  (i) random entries with identical exit/sizing machinery, (ii) buy-and-hold. Deflated Sharpe
  over the full count of configurations tested (declared: 3N × 5 exits × 3M rotation +
  3N × 3K × 5 exits × 3M continuation, × 3 symbols = 540; any later addition raises the count,
  never resets it).
- **UTC-hour bucketing**: edge-by-hour reported (crypto has no session; concentration is a
  finding, not an assumption). Funding-extreme standalone signal noted as a SEPARATE hypothesis,
  not folded into this one.

## Deployment gate (verbatim, fixed now)

No live capital unless ALL hold: >200 OOS trades; positive expectancy in all three regime
buckets; parameter plateau not peak; deflated Sharpe > 1.0 after costs; max DD at proposed
sizing < 25% at the 95th percentile of bootstrap paths. Otherwise: paper trading, minimum 100
further trades.

## Declared in advance — what a "confirming" result must survive

If the backtest returns ~90% win rate matching the source book, that is evidence of a BUG
(lookahead in the boundary calculation or optimistic limit fills), checked before being believed.
The expected honest outcome is a modest RANGE edge that decays after fees and a rare-firing
continuation edge. The single-loss profile of the source book is specifically suspected of being
survivable-only-at-n=11: small average wins with manual exits is the shape where one uncontrolled
loss erases twenty winners.
