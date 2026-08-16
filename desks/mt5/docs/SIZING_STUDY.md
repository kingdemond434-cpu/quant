# SIZING STUDY — XAUUSD 4-Sleeve Breakout Book

Study date: 2026-08-16. Method: block bootstrap (25-trade blocks = ~1 month,
preserving streaks and cross-sleeve clustering on the merged chronological
trade stream), 30,000 simulated one-year paths per lot, fixed-fractional
sizing, costs already inside the per-trade R stream.

Input: combined costed book n=2,812, exp +0.127R, t=6.82, PF 1.37,
maxDD -18.5R, 331 trades/yr dense, worst single R -1.05, 99th pct |R| = 2.00.

Cross-sleeve daily-R correlation (Pearson):
asia-london 0.19, asia-ny 0.14, asia-afternoon 0.10, london-ny 0.50,
ny-afternoon 0.40, london-afternoon 0.24. Correlated sleeves -> drawdowns
concentrate in london/ny/afternoon cluster; block bootstrap captures this.

## Sizing curve (base edge, 633.89 EUR, dist ~19.1 USD/oz)

| lot | risk/trade | medCAGR | 5pct wealth | P(DD>30%) | P(DD>50%) | P(DD>70%) | P(ruin) |
|-----|-----------|---------|-------------|-----------|-----------|-----------|---------|
| 0.005 | 1.4% | 76% | 1.136 | 0.01 | 0.00 | 0.00 | 0.0000 |
| 0.010 | 2.8% | 191% | 1.218 | 0.33 | 0.02 | 0.00 | 0.0000 |
| 0.013 | 3.5% | 266% | 1.235 | 0.62 | 0.06 | 0.00 | 0.0000 |
| 0.015 | 4.2% | 353% | 1.235 | 0.79 | 0.15 | 0.01 | 0.0000 |
| **0.020** | **5.5%** | **566%** | **1.185** | **0.95** | **0.41** | **0.05** | **0.0000** |
| 0.030 | 8.3% | 1113% | 0.924 | 1.00 | 0.86 | 0.32 | 0.0002 |
| 0.040 | 11.1% | 1710% | 0.672 | 1.00 | 0.98 | 0.69 | 0.0095 |
| 0.050 | 13.9% | 2313% | 0.599 | 1.00 | 1.00 | 0.88 | 0.0507 |
| 0.060 | 16.6% | 2963% | 0.560 | 1.00 | 1.00 | 0.96 | 0.1308 |

Kelly full f* = 0.131 risk/trade = 0.047 lot (13.1%/trade).

## Stress: edge halved (mean x0.5), vol x1.3

| lot | risk/trade | medCAGR | 5pct wealth | P(DD>30%) | P(DD>50%) | P(DD>70%) | P(ruin) |
|-----|-----------|---------|-------------|-----------|-----------|-----------|---------|
| 0.010 | 2.8% | 73% | 0.980 | 0.11 | 0.00 | 0.00 | 0.0000 |
| 0.015 | 4.2% | 119% | 0.936 | 0.45 | 0.04 | 0.00 | 0.0000 |
| **0.020** | **5.5%** | **170%** | **0.873** | **0.77** | **0.15** | **0.01** | **0.0000** |
| 0.030 | 8.3% | 282% | 0.707 | 0.97 | 0.53 | 0.10 | 0.0000 |
| 0.040 | 11.1% | 390% | 0.524 | 1.00 | 0.83 | 0.31 | 0.0008 |

## Verdict (MANDATE_NET_COMPOUNDING lens)

Maximize robust geometric growth subject to negligible ruin probability.

- **0.02 lot per sleeve (q = 5.5%, ~0.37 Kelly) is the selection.** Base
  medCAGR ~566%, stress medCAGR ~170%, P(ruin) = 0.0000 at every lot <= 0.02,
  5th-percentile year -13% even under halved-edge stress. This is the highest
  sizing with P(ruin) ~ 0 that also survives stress with a positive 5th-pct
  wealth path. Kelly-full (0.047) is NOT taken: P(ruin) 5.1% at 0.05 and a
  5th-pct wealth of 0.60 violate the mandate's ruin clause.
- 0.01 lot (previous deployment) leaves ~3x median growth on the table; the
  mandate explicitly forbids under-sizing out of drawdown discomfort.
- P(DD>50%) = 41% at 0.02 is accepted per mandate: DD != ruin, P(ruin) ~ 0.
- Margin headroom: stop-out only if equity falls below margin
  (margin = 0.45q x equity ~ 2.5% at q=5.5%) - never binding before ruin;
  per-trade SL bounds every loss at ~-1.2R, worst observed -1.05R.
- Gap exposure: worst single R -1.05; SL can gap through on extreme news but
  H1 XAUUSD gaps are small; 99th pct |R| = 2.00. No swap/interest (Islamic
  account), broker daily pause 21:00-22:00 UTC respected by gateway.

## Deployment rule

Gateway sizes each bracket at q = 5.5% of CURRENT equity (auto-lot,
rounded to 0.01, floor 0.01), re-evaluated every gateway cycle - fixed-
fractional by construction. As equity grows, lots scale automatically
(e.g., ~0.32 lots at 10k EUR). Sizing study rerun when equity or edge
changes materially (or after 50 live trades).

## Reference

- research/sizing_study.py (rerun: PYTHONPATH=C:\Users\dell\mt5-research
  python research\sizing_study.py)
- MANDATE_NET_COMPOUNDING.md (binding human mandate)