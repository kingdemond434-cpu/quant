# Intraday rotation/continuation on Binance perps — MEASURED, and the answer is NO-GO

**2026-08-04. Pre-registration**: `INTRADAY_ROTATION_PREREGISTRATION.md` (committed before data).
**Data**: Binance USD-M perps, real venue archive (data.binance.vision), 315,648 five-minute bars
× BTCUSDT/ETHUSDT/SOLUSDT, 2023-08→2026-07, full funding history. **Protocol**: 6m/2m rolling
walk-forward, 42 window-symbol selections over a 540-config grid, OOS only. Engine passed its
no-lookahead future-shuffle probe and pessimistic-fill tests BEFORE the run.

## Verdict against the pre-registered deployment gate: **NO-GO, both strategies**

| | rotation (RANGE) | continuation (TREND) |
|---|---|---|
| OOS trades | 25,036 | 565 |
| expectancy (net, R) | **−0.445** | **−0.018** |
| win rate (95% CI) | 23.9% (23.4–24.5) | 40.4% (36.4–44.5) |
| ann. Sharpe after costs | −20.8 | −0.20 |
| deflated-Sharpe prob (540 cfgs) | 0.000 | 0.0004 |
| positive in every year bucket | no (all negative) | no (2025 +0.047, 2024/2026 negative) |
| beats random-entry null | yes: −0.44 vs −0.88 | yes: −0.02 vs −0.88 |
| half-Kelly risk fraction | 0 [0, 0] | 0 [0, 0] |

## The three findings that matter

**1. The structure carries real information — and costs destroy it anyway.** Both strategies
beat the random-entry null by huge margins (+0.44R and +0.86R per trade): the location filter,
rejection bars and breakout-pullback logic are NOT noise. But the median 5m stop distance is
0.13% of price while round-trip costs (taker+maker+slippage+funding) are ~0.11% — **costs alone
consume ≈1.1R per trade** (measured: gross rotation expectancy −0.04R ≈ fair coin, net −0.44R).
The gold book's economics do not port: XAUUSD spread on the source's account is ~0.006% of price
— roughly 20× cheaper *relative to the same stop distance*. This is the spec's own prediction
("a 37-unit median win dies on costs") measured to the decimal.

**2. The 3–5% sizing ask is ruin-certain, measured.** On the ~breakeven continuation strategy —
the *better* one — bootstrap at the requested sizing gives: at 3%: P(DD>50%) = 94%, P(ruin) =
22%; at 5%: P(DD>50%) = 100%, P(ruin) = 70%. On rotation, ruin probability is 1.00 at every
size including 0.25%. The measured half-Kelly for both is **zero** (no positive edge → the
correct size is no size), and 3–5% sits outside its CI of [0,0]. The source book's +933.72 in
five days at this sizing is the lucky branch of a distribution whose median is account
destruction. R0143's fence is not policy caution; it is this table.

**3. The source book's fill problem, quantified.** 32% of continuation signals (269 of 834)
never filled their pullback limit and were cancelled — the "unfilled limit in a runaway move"
failure the trader described is about a third of all signals, and the moves that run away
without you are disproportionately the winners.

## Reasons this may be spurious (required section — 6 points)

1. **Venue substitution**: tested on Binance perp data per spec, but the desk would execute on
   OKX; fee tiers and book depth differ (direction: OKX taker similar — conclusion robust).
2. **Intrabar path unknown at 5m**: stop-first tie-break is deliberately pessimistic; a 1m
   event-driven verification of the top configs (pre-registered) would move results *up*
   slightly — nowhere near +0.45R.
3. **Regime classifier granularity**: ER thresholds (0.25/0.45) were fixed a priori, not tuned;
   a different classifier could shift the RANGE/TREND split. The cost arithmetic is
   classifier-independent.
4. **Selection inside the walk-forward**: best-on-train per window is itself a selection; the
   540-config deflation covers the grid but not the protocol's own single selection rule.
   Direction: flatters, and the result is still negative.
5. **Null construction**: random entries share exits but not entry-bar volatility conditioning;
   a vol-matched null would be slightly harsher on the "beats null" claim.
6. **2023 warm-up excluded by the first train window**: year buckets start 2024; the 2023 range
   regime — the friendliest for rotation — is under-represented in OOS. It is fully represented
   in train windows, where rotation also lost.

## What survives, and the one follow-up worth its cost

The *shape* survives; the *timeframe* dies. Continuation at ~breakeven net, with a train-side
plateau (N24–48 / K24 / M96 / r3-boundary all ≈ +0.077R — a plateau, not a peak) and +0.86R over
null, says the entry logic is real and everything is being eaten by cost-per-R at 5m scale.
The registered follow-up (NEW trial count, added to the multiplicity ledger, never merged into
this one): **the identical pre-registered logic at 15m/1h boundaries**, where stops are 3–8×
wider and cost-in-R falls to ~0.15–0.35R — plus maker-only entries. That is also exactly where
it meets the desk's existing pre-registered H2/H9 (breakout + ORB) in the main campaign, tested
at the full bar with everything else.

**Per the gate: no live capital, and no paper-trading of a negative-expectancy config either —
the paper-trade clause applies to a strategy that MISSES the gate narrowly, not one that fails
it in sign.** Plots: `reports/intraday_rotation{_rotation,_continuation}.png`; full numbers:
`reports/intraday_rotation.json`.
