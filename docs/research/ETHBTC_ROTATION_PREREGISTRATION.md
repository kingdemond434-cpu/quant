# ETH/BTC ROTATION — PRE-REGISTRATION (2026-08-07)

**Status: PRE-REGISTERED, NOT RUN.** Kill criteria and trial budget are fixed *below* before any
data is touched. Queued BEHIND the failed-breakout study — the desk has 16,200 pre-registered
trials at zero executed, and adding a candidate while that queue is idle is widening the funnel
mouth instead of pushing anything through it.

## Provenance, stated plainly

A backtest posted to r/CryptoTradingBot: *"ETH/BTC dynamic rotation bot — machine-learning entry
signals + regime/crash filters, rotating exposure between ETH and BTC perpetuals."* Reported
2023-09-23 → 2026-07-12 (2.8y), $500 → $3,774: win rate 42.2%, 275 trades, profit factor 2.2,
total return +655%, CAGR +105.6%, **Sharpe 2.17**, max drawdown −28.0%, avg win/loss +5.46%/−1.81%,
0.052% cost per side.

**This is a claim from an anonymous source with no code and no data. It is a HYPOTHESIS, not a
result**, and it enters the funnel exactly like anything else. Nothing here adopts it.

## What was verified before writing this, and what it changes

The arithmetic is internally consistent — recomputed implied profit factor **2.20** against a
claimed 2.2, implied CAGR **105.8%** against a claimed 105.6%. That is worth stating because it is
unusual, and because it means the disagreement below is NOT about honesty.

**The disagreement is about sample size, and it is decisive.** A Sharpe of 2.17 measured over 2.8
years carries SE ≈ 1.095 (Lo 2002), so **t ≈ 1.98** and the 95% interval on the Sharpe is
**[0.02, 4.32]** — an interval that effectively touches zero on ONE trial. Under any realistic
search:

| configurations tried | √(2 ln N) hurdle | verdict |
|---|---|---|
| 1 | 1.96 | passes, barely |
| 10 | 2.15 | **FAILS** |
| 50 | 2.80 | **FAILS** |
| 200 | 3.26 | **FAILS** |

An "ML entry + regime filter + crash filter" construction is not arrived at in one attempt. **It
fails at ten.**

**Costs are NOT the objection**, and saying so matters because it is the easy objection and it is
wrong here: at 3× the modelled cost the strategy still shows +1.05%/trade expectancy. The 0.052%
per side does imply ~0.2bp of slippage, which is optimistic, but the result is robust to it. The
sample is what fails, not the fees.

## THE TEST, and why this one is worth running at all

The backtest **begins 2023-09-23**. ETH/BTC perpetual history runs years earlier. The single
highest-information experiment available is therefore free:

> **Run the same rule set on 2019-09-01 → 2023-09-22 — the ~4 years the posted backtest omits.**

That window is genuine out-of-sample with respect to the author's search, it is keyless public data
(Binance USD-M `fapi`, no credential), and it spans regimes the reported window does not: the 2020
crash, the 2021 mania, and the 2022 bear including LUNA and FTX. A regime-filtered rotation that
worked 2023-2026 and dies 2019-2023 is curve-fit. One that survives both is worth a real look.

**HONEST LIMIT ON WHAT THIS CAN PROVE.** The exact ML entry rule is NOT published, so this cannot
replicate the strategy — it tests the FAMILY: ETH/BTC relative-strength rotation with a regime
filter. A null result kills the family as specified here; it does not prove the author's specific
model is worthless. Recorded now so the conclusion cannot be widened after the fact.

## Kill criteria — BINDING, fixed before the run

| # | Criterion | Kills if |
|---|---|---|
| K1 | Deflated significance | t < √(2 ln N) on the shared budget below |
| K2 | Sign stability | OOS Sharpe < 0 in the 2019-2023 window |
| K3 | Regime dependence | edge concentrated in one regime: >70% of PnL from a single one of {2020 crash, 2021 mania, 2022 bear, 2023+ recovery} |
| K4 | Cost sensitivity | expectancy turns negative at 3× modelled cost (20bp round trip) |
| K5 | Turnover realism | implied trade count needs >5× the posted 275/2.8y rate to reach the claimed return |
| K6 | Negative control | a RANDOM rotation schedule, matched on trade count and holding period, scores within 1 SE of the rule |
| K7 | Buy-and-hold control | the rule does not beat simply holding the better of ETH or BTC, net of cost, on the same window |
| K8 | Sample floor | fewer than 100 trades in the OOS window → **UNMEASURED**, never "no edge" (L1.28a) |

**K7 is the one most likely to fire and the one most often skipped.** 2020-2021 was a period in
which holding either asset returned multiples; a rotation rule can post a spectacular CAGR and
still have destroyed value against the trivial alternative. A strategy that does not beat
buy-and-hold is not an edge, it is a costlier way to be long.

**K6 exists because the desk's harness must be able to fail.** If a random schedule scores like the
rule, the finding is about the window, not the signal.

## Trial budget

| axis | values |
|---|---|
| lookback | 7, 14, 30, 60 bars |
| rebalance | 4h, 1d |
| regime filter | none, vol-percentile, trend |
| cost | 10bp, 20bp, 30bp round trip |
| **nominal trials** | 4 × 2 × 3 × 3 = **72** |

**These 72 JOIN the existing shared deflation budget of 16,560, taking it to 16,632.** The hurdle
moves √(2 ln 16560) = 4.408 → √(2 ln 16632) = 4.410. Recorded because the three registered studies
share one deflation: an axis added anywhere makes the bar harder everywhere, and a budget updated
only where the axis was added is not shared.

## Authority

**NONE.** Stage A. This pre-registers nothing beyond a measurement, promotes nothing, sizes
nothing, and trades nothing. A survivor here earns a place in the queue, not capital.
