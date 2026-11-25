# USDJPY session_range_breakout (asia): cost-aware variant study, pre-registration

Written 2026-10-20, committed BEFORE any variant below was run. Research only: no sizing,
sleeves.json, book or clock is touched by this study, and no existing clock is re-dated.

## Question

Why is `USDJPY_session_range_breakout_asia` flat on the forward (reported -0.095R over 20
trades; the box's `shadow_state.json` reads n=21, exp_r -0.020 / -0.049 / -0.030 for
rr 1.5 / 2.0 / 2.5), and can a small, pre-registered, cost-aware variant make it pass the
Tier S bar on costed data?

## Data (fixed now)

- Bars: `desks/mt5/data/universe/USDJPY_H1.parquet` (Fusion H1, broker clock), used from
  2018-01-01 to 2026-08-16 inclusive (the clock's SHADOW_START is 2026-08-16).
- In-sample / selection window: 2018-01-01 .. 2023-12-31.
- Backtest holdout: 2024-01-01 .. 2026-08-16. Never used to choose.
- Local post-start window: 2026-08-17 .. 2026-09-16 (end of local bars). Reported only.
- Box forward (2026-09-18 .. 2026-10-19, n=20/21): out-of-sample check only. It is never used
  to choose a variant, a parameter, a k or a cost.

## Cost model (fixed now)

Engine `Costs.from_symbol(meta, spread_pts=X, commission_per_lot=2.00)` (Fusion's measured per-side
commission, `libs.portfolio.fusion_cost.COMMISSION_PER_LOT_PER_SIDE`), swap from the registry.

| Arm | Spread pts charged per round trip | Extra adverse entry/exit slip | Role |
|---|---|---|---|
| ZERO (the defect) | 0 (engine floor 0.05 JPY/lot) | 0 | reproduces the uncosted certificate |
| BENCH | 5.4 (third-party Fusion USDJPY average, `data/free_data/forexbenchmark_fusion_spreads_20260830.json`) | 0 | sensitivity |
| PRIMARY | 13 (`cost_surface.json` USDJPY p50 at broker hours 1-23; the value the #389/#391 fix writes) | 0 | selection and the Tier S verdict |
| PRIMARY+SLIP | 13 | 5 pts (0.5 pip; USDJPY markout is UNMEASURED, no fills exist) | realism check |
| STRESS | 26 (2x primary) | 5 | must stay > 0 |

## Variants (five trials; N = 5 is the Tier S bar's fixed N, never raised or lowered)

All are parameters the family already exposes, so the box's canonical gauntlet can rebuild them
exactly with `external_gauntlet.build_cell`. Session = asia (range_start 7, ttl 12, atr_n 20).

| id | params | why (written before results) |
|---|---|---|
| V0 | rr=2.0, wait_bars=12 | the clock's own spec (`USDJPY.asia`), re-costed. Counts as a trial |
| V1 | rr=2.0, wait_bars=12, spread_gate=True | spread filter: skip a signal whose bar spread exceeds its rolling 96-bar median (k=1). Expected to be near-inert on H1 history, whose spread is near-constant within a year |
| V2 | rr=2.0, wait_bars=8 | entry timing: the trigger must fire within 8 bars, cutting the late (broker 15:00+) fills |
| V3 | rr=2.0, wait_bars=12, vol_filter="high" | vol-regime gate: only when ATR(20) is above its 200-bar median; a wider stop makes a fixed spread a smaller fraction of 1R |
| V4 | rr=2.5, wait_bars=12 | rr choice: the desk's own earlier growth-maximum pick (live_sleeve_policy `why_this_rr`) |

## Selection rule (fixed now)

1. Choose the variant with the highest per-trade Sharpe in the IN-SAMPLE window under PRIMARY.
2. It is a Tier S candidate only if ALL hold:
   - canonical DSR >= 0.95 on the full 2018-01-01..2026-08-16 PRIMARY series, with
     `libs.validation.dsr.deflated_sharpe_ratio(n_trials=5, variance_of_sharpes=1/(T-1))`,
     T = number of observations, computed on the per-trade R series; the daily-summed series is
     reported beside it;
   - holdout mean R > 0 under PRIMARY;
   - full-sample mean R > 0 under STRESS.
3. Every variant's DSR is reported, so a reader can see the others failing or passing too.
4. The box forward is then read once as an out-of-sample check: is the forward mean inside the
   chosen variant's own predicted 95% band for n trades?

## Noise test (fixed now)

From the PRIMARY holdout per-trade R distribution of V0: the 95% band for a mean of n=20 trades
(normal approx. and a 20,000-draw bootstrap), and P(mean of 20 <= -0.095R). The gap is called
"explained by noise" if -0.095R lies inside the 95% bootstrap band.

## Also run (report-only, no authority)

`external_gauntlet.run_gauntlet` on the five cells (built by `build_cell` with the PRIMARY-window
bars), read for its gate verdicts only. Nothing it returns is written as a certificate.
