# Pre-registration — the new mechanism families entering the pooled campaign

**Written 2026-08-04, before any of these generators ran on market data.** This is the content
expansion the 2026-08-04 pooled measurement demanded: the incumbent 20 mechanisms are measured
edge-free at daily frequency, so the marginal hour goes to NEW families — the pre-registered
discretionary set (H3/H6/H7/H8) plus the intraday timeframe escalation. The multiplicity ledger
grows accordingly and is declared here; it never resets.

## A. New daily-campaign generator families (grid fixed now)

| family | mechanism claim | params |
|---|---|---|
| `wyckoff_spring` | a failed break below (above) an N-bar range that closes back inside is absorption by informed buyers (sellers); continuation follows the failure direction | window ∈ {20, 40}, hold ∈ {5, 10} |
| `vwap_reversion` | stretched deviation from rolling VWAP mean-reverts (inventory pressure) | window ∈ {20, 50}, z ∈ {1.5, 2.5} |
| `vwap_trend` | the side of VWAP is the side of institutional inventory; follow it | window ∈ {20, 50} |
| `supply_demand_retest` | the base before an impulsive departure (range > k×ATR) holds unfilled orders; first retest continues the departure | k ∈ {1.5, 2.0}, hold ∈ {5, 10} |
| `ict_fvg_follow` | an unfilled three-bar imbalance (`libs/ict.fair_value_gap`) marks displacement; follow it | hold ∈ {3, 8} |
| `ict_sweep_reversal` | a raid through equal highs/lows that closes back (`libs/ict.liquidity_sweep`) is engineered liquidity; fade it | confirm ∈ {2, 3}, hold ∈ {5, 10} |
| `ict_mss_follow` | a market-structure shift (`libs/ict.market_structure_shift`) starts the new leg; follow it | confirm ∈ {2, 3}, hold ∈ {10, 20} |

All enter `libs/autodiscovery/generators.GENERATORS`, so they flow through the IDENTICAL
per-symbol + pooled campaign as every incumbent: same gates, same α, same per-candidate
Romano-Wolf/CSCV, pooled-by-mechanism certification view. **New trial count**: 7 families × their
variants × 10 symbols added to the campaign's n_trials; the pooled view adds one hypothesis per
mechanism-variant. Nothing about the incumbents' recorded results changes.

**Volume becomes REAL in the same change**: the campaign fetch now carries OKX's actual volume
column instead of the flat 1e9 placeholder, because VWAP mechanisms on constant volume are an
SMA in costume. This changes no incumbent mechanism (none of the 20 reads volume).

## B. Intraday continuation re-test at 15m and 1h (the registered follow-up from
INTRADAY_ROTATION_RESULT.md)

Identical pre-registered logic and grid AS ALREADY FIXED (N/K/M in BARS, exit variants, costs,
walk-forward 6m/2m, nulls, 540-config deflation per timeframe) — only the bar interval changes:
Binance Vision 15m and 1h archives, same three symbols, same engine that passed its no-lookahead
probes. Predicted mechanism: cost-in-R falls from ~1.1R (5m) to ~0.15–0.35R as stops widen 3–8×.
Each timeframe is its OWN trial set (counted separately in the deflation, declared now); results
are never pooled across timeframes post hoc.

## C. Deferred, with the blocker named (desk convention: NOT-BUILT is recorded, never silent)

- **H9 opening-range breakout**: needs an intraday session-anchored harness extension (UTC-day
  opening range on 15m bars with volume confirmation). Deferred behind the 15m re-test result —
  if continuation at 15m clears costs, ORB shares its economics and gets built next; if it does
  not, ORB dies of the same arithmetic without being built. That conditional IS the decision.
- **H4 volume profile / H5 order flow**: blocked on the moat L2/trades tape (operator: VPS
  bringup). No public OHLCV substitute exists that would test the actual mechanism.

## The standing rule, restated

These are hypotheses. The expected outcome for most is death — on this desk a measured death
retires search space and is paid for once. Any survivor must clear the pooled gauntlet at α=0.05
with everything above declared. No result from this batch may be quoted without its trial count.
