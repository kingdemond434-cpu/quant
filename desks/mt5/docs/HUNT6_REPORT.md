# HUNT #6 — Session-Range-Breakout Across the MT5 Universe

Date: 2026-08-16. Gate battery: t>2, n>60, PF>1.05, maxDD>-30R, 3-fold WF OOS all folds > 0,
2x cost stress (spread+commission, slippage, vol 1.3x). Fixed deployed params — **no per-symbol
optimization** (multiple-testing honest). Costs from `data/universe/universe.json` (median spread
x tick x contract, commission $3.5/lot, XAUUSD live spread 0.48 override).

## Universe (19 symbols, H1 2018→2026)
XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, EURJPY, GBPJPY, AUDUSD, USDCAD, USDCHF, NZDUSD,
EURGBP, EURCHF, AUDJPY, CADJPY, NZDJPY, CHFJPY, BTCUSD, ETHUSD. (No WTI/BRENT/indices on this
Vantage account.)

## Verdict
**80 tests (4 windows x 2 variants x 19 symbols) → 10 survivors (5 unique symbol-windows).**
Survivors split 100% into two families: **JPY crosses** (asia + london_am) and **XAUUSD**
(asia + london_am + afternoon). ny_open and afternoon are dead outside JPY crosses; XAGUSD,
BTCUSD, ETHUSD, EURUSD, GBPUSD, AUD*, CHFJPY fail (cost or WF or stress).

| sleeve | n | exp (R) | t | PF | maxDD (R) | WF OOS folds | stress exp (R) |
|---|---|---|---|---|---|---|---|
| XAUUSD.asia | 2094 | +0.212 | 8.40 | 1.54 | -21.0 | +0.206 +0.162 +0.272 | +0.202 |
| XAUUSD.london_am | 2075 | +0.153 | 5.88 | 1.35 | -22.8 | +0.151 +0.102 +0.205 | +0.142 |
| XAUUSD.afternoon | 1559 | +0.096 | 4.53 | 1.35 | -14.0 | +0.052 +0.083 +0.152 | +0.088 |
| USDJPY.asia | 2100 | +0.159 | 7.49 | 1.50 | -14.1 | +0.136 +0.190 +0.150 | +0.120 |
| USDJPY.london_am | 2108 | +0.114 | 4.80 | 1.28 | -17.5 | +0.075 +0.187 +0.078 | +0.060 |
| CADJPY.asia | 2136 | +0.163 | 7.29 | 1.46 | -11.3 | +0.159 +0.201 +0.127 | +0.113 |
| EURJPY.asia | 2141 | +0.142 | 6.49 | 1.40 | -13.0 | +0.108 +0.201 +0.117 | +0.109 |
| EURJPY.london_am | 2068 | +0.079 | 3.79 | 1.23 | -20.8 | +0.053 +0.115 +0.069 | +0.043 |
| GBPJPY.asia | 2163 | +0.121 | 5.29 | 1.31 | -22.8 | +0.094 +0.143 +0.128 | +0.094 |
| GBPJPY.london_am | 2053 | +0.084 | 4.02 | 1.24 | -23.7 | +0.089 +0.088 +0.074 | +0.058 |

Spread-gate variant (trades only when spread < 1.25x median) passes alongside base on all 10;
never rescues a failing window. Fail-fast rows (t<1.8, no WF) dominate the rejects.

## Multiple-testing honesty
80 correlated tests (one mechanism family) — 10 passes is far above any false-discovery rate
consistent with WF all-folds-positive + 2x-cost-stress survival, but the family shares the
"session range breakout" mechanism, so treat the family as ONE hypothesis with many instrument
expressions. Forward proof (shadow → live) is still required before capital.

## Portfolio study (equal 1-lot per sleeve, daily-R)
- Gold sleeves vs JPY crosses: corr ≤ 0.06 — near-orthogonal.
- JPY-cross asia windows mutually corr 0.17–0.39 (shared JPY risk factor); london_am corr
  0.12–0.31 within the pair cluster.
- **Combined 10 sleeves: mean daily R +1.223, daily t = 13.60, PF 2.10, maxDD −49.8R over 8.6
  years (~2,235 trading days), ~447R/yr per 1-lot sleeve set, ~2,400 trades/yr total.**
- The −49.8R combined drawdown is ~2.2x the worst single sleeve: JPY risk factor concentration
  (asia cluster) is the dominant tail driver — the sizing problem for the extended book must be
  solved at portfolio level, not sleeve level.

## Decisions
1. **Gold book (armed live, Monday) stays as-is.** XAUUSD windows here corroborate the mechanism
   (same params family) but the armed sleeves use hunt5-validated params and sizing.
2. **JPY-cross sleeves enter shadow-forward validation** (paper trades recorded daily, 50 trades
   or 14 days, no live capital), then portfolio-level sizing study (block bootstrap with the
   full correlation matrix) before any live lot.
3. Combined-book sizing and the JPY-factor tail are the next study (see HUNT6_FORWARD.md when
   written).
4. BTCUSD/ETHUSD/XAGUSD: no authority to trade with the deployed mechanism at current costs.

## Files
- `reports/hunt6.json` — machine-readable survivors + all tests.
- `research/run_hunt6.py` — reproducible, checkpoint/resume, `--force SYM1,SYM2` rerun.
- `research/portfolio_hunt6.py` — correlation + combined stats.
- `data/universe/*_H1.parquet`, `data/universe/universe.json` — raw material.