# Pre-registration — empirical-Bayes shrinkage strength for the sleeve posterior

**Written 2026-11-03, before the box's sleeve evidence was run through the harness.** The only
runs before this document were on synthetic books (below). The bars are fixed here and copied
verbatim into `desks/mt5/research/eb_shrinkage_oos.py`; moving one after the box run is a
description of the run, not a test.

## The change under test

`libs/portfolio/robust_elog._posterior_mu` pools sleeve → family → asset class → zero by
`n / (n + k)` with k fixed (60 / 120 / 240). The candidate (`libs/portfolio/eb_shrinkage.py`)
replaces the sleeve and family k with the positive-part James-Stein estimate per group,
`k_i = s_i² / tau²_g`, `tau²_g = max(0, Σ(m − m̄)² / (g − 3) − mean(se²))`, **clipped to
[0.25 × fixed k, 1e6]**: two-sided, as GROWTH GOVERNANCE requires of every capital modifier, so
a family of alike members is pooled harder and a family whose members measurably differ is
pooled less. Each sleeve's sd is pooled toward its family (30 pseudo-df). The posterior standard
error never narrows: it uses `max(s_raw, s_pooled)` and today's fixed-k widening, so precision
is never overstated. Groups under four members keep the fixed k. The asset-class level is
unchanged (too few classes to estimate a spread).

Fixed estimator constants (not risk limits; Auditor 2026-11-03): MIN_GROUP = 4, NU0 = 30,
K_MIN_RATIO = 0.25, K_MAX = 1e6. Survival rails (heat ceiling, CVaR objective, ruin guard,
firm caps) are untouched.

All three account books (E8 `pf_allocator`, Fusion `kelly_survival`, FTMO/prop
`prop_challenge_allocator`) read the same `sample_worlds` posterior, so one arm moves them
together. Off (the default), the posterior is bit-for-bit today's.

## Test (walk-forward, the allocator's own evidence)

Assembled exactly as `pf_allocator.run` does. Six expanding-window origins spread over the second
half of the book's calendar; at each, every sleeve is truncated to the days before the origin,
forward/live counts are zeroed and state/macro inputs cleared (no look-ahead), and the next
126 days are held out. Sleeves need ≥ 60 training days; scoring needs ≥ 20 held-out days.

- **P1 predictive.** Day-weighted squared error of each mode's posterior mean against the
  realised held-out mean. PASS iff EB wins **≥ 50 %** of folds **and** the pooled MSE ratio
  EB / fixed is **≤ 1.00**.
- **P2 growth.** Each mode's book is solved as production solves it: `optimise` free up to the
  0.30 ceiling (128 worlds × 256 rows, seed 20261103), and a book below the 0.20 floor scaled up
  to it (pf_allocator's proportional floor fill), so the posterior moves total heat as well as
  the split. Realised mean log(1 + h·r) on the held-out days. PASS iff the summed fold growth of
  EB **≥** fixed **and** EB's worst fold **≥** fixed's worst fold.

**Arm iff P1 and P2 both pass.** `pf_allocator.py --eb-oos --eb-arm-on-pass` (harness `eb_shrinkage_oos.py`) places
`desks/mt5/data/EB_SHRINKAGE_ARMED` only then and writes `reports/EB_SHRINKAGE_OOS.json`
either way. A FAIL leaves the desk on the fixed k; the result is journalled and the row stays
OPEN with the measured numbers. No gate, cap or survival rail moves in either outcome.

## What the synthetic runs already showed (disclosed, not evidence)

Three families × five sleeves, 450 days, sd 1, 40–200 seeds, the two-sided estimator above:

- Against the TRUE means, EB cuts posterior MSE by ~30 % and wins 99 % of seeds.
- Books solved as production solves them (free to 0.30, proportional fill to the 0.20 floor),
  true expected log growth: EB **+7 %** when within-family true dispersion is 0, **+3 %** at
  0.02, **−1.7 %** at 0.05 (≈ one standard error) and −0.3 % at 0.10. So the result depends on
  how alike the members of a real family are, which is exactly what the box run measures.
- `optimise(target=0.20)` far above the free optimum returns a uniform book and would make the
  two modes tie; that is why the floor is a proportional fill, as in production.
- The fold-vs-realised P1 score is unbiased but noisy (held-out noise dominates on a 15-sleeve
  book); the box book is ~10× wider, which is what makes P1 informative there.

Amended 2026-11-03 before any box run, on the Auditor's HOLD (two-sided k; P2 as production).
