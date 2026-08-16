# RV TRIANGLE — AUDCAD/AUDNZD/NZDCAD Relative-Value Study (Verdict: NO AUTHORITY)

Date: 2026-08-16. Data: M15 2022-08→2026-08 (100k bars, server cap), H1 2018→2026.
Mechanism reconstructed from the public RAZOR/Deux family disclosures: mean reversion of the
cross-rate residual r = ln(AUDCAD) − ln(AUDNZD) − ln(NZDCAD), basket fair-value exit,
stop-based risk, no grid/martingale. Fixed params: σ window 480 bars, entry |z|, exit 0,
stop 2.5σ, TTL 192 bars, no entries 21:00–22:00 UTC, 3 legs × 1 lot, costs = live spreads
(AUDCAD 16 / AUDNZD 15 / NZDCAD 17 pts) + $3.5/lot commission + 0.2x slippage.

## Verdict table (all gates: t>2, n>60, PF>1.05, maxDD>-30R, WF all folds >0, 2x-cost stress)

| config | n | exp R | t | PF | win | maxDD R | WF folds | 2x stress |
|---|---|---|---|---|---|---|---|---|
| M15 z=2.0 | 1167 | **-0.770** | -15.7 | 0.25 | 34% | -918 | all <0 | -2.64R t=-40 |
| M15 z=3.0 | 689 | **-0.397** | -7.5 | 0.43 | 45% | -328 | -0.96 -0.35 +0.11 | -2.22R t=-29 |
| H1 z=2.0 | 489 | **-1.012** | -13.2 | 0.15 | 26% | -541 | all <0 | -3.05R t=-26 |
| H1 z=3.0 | 120 | **-0.564** | -3.0 | 0.40 | 47% | -98 | -1.63 -0.54 +0.47 | -2.53R t=-10 |

**Verdict: no configuration passes; the residual mean reversion does not clear this account's
costs (3-leg basket: ~$70-105 round trip per trade vs ~1σ reversion ≈ $40-80 gross).**
H1 residual reversion is negative even gross (the triangle is not stationary at H1 scale here).

## Known structural issues (next iterations, if ever)
- Entry side: stop_usd sign check currently drops all zi<0 (long-AC) trades — must be fixed
  (abs/hedged risk) before any further testing.
- σ-collapse extremes (z up to ±14) produce instant-stop losses — a structural-break filter is
  mandatory, not optional.
- The mechanism's economics only clear at ECN-class costs (RAW/ECN spreads ~1-3 pts, no
  commission double-charge). **Re-test ONLY if such an account becomes available** — per the
  RAZOR lesson (execution costs matter) and the pay-only-if-proven data principle.
- First exploratory run showed a positive result that was NOT reproducible after code hardening
  (suspect stale intermediate state). **Discarded per discipline: only reproducible,
  deterministic results are admissible.**

## Status
Family hypothesis CONDITIONAL-FAILED on Vantage standard-account costs. Recorded in the
graveyard. No capital, no shadow-forward. The false-breakout and regime-gated XAUUSD sleeves
remain the gold-desk research priorities; scalp lab (MICRO_ALPHA_LAB) proceeds separately.

## Files
- `research/rv_triangle.py` (argv: tf entry_z), `research/fetch_triangle.py`,
  `data/universe/{AUDCAD,AUDNZD,NZDCAD}_{H1,M15}.parquet`, `reports/rv_triangle.json`.