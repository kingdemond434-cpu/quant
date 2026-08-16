# MANDATE_MECHANISM_RE — Reverse-Engineered Mechanism Portfolio

Status: BINDING research program. Source: public records of top/failed MT5 systems
(RAZOR, Deux ex machina, MagicGW, Gold Reaper, MQL5 rankings). **Steal the alpha, reject the
leverage** — triple-digit backtests mean nothing unless they survive real costs, WF OOS,
perturbation, Monte Carlo, regime splits, unseen forward clocks, and much lower leverage.

## Program
1. **RV triangle (AUDCAD/AUDNZD/NZDCAD, M15)** — first verdict: FAILS on Vantage standard-account
   costs (docs/RV_TRIANGLE_VERDICT.md). Re-test only under ECN-class costs. Fix side/stop bugs
   if revisited. Basket exit at residual fair value; capped aggregate AUD/NZD/CAD exposure.
2. **XAUUSD false-breakout sleeve (Gold Reaper-style)** — detect structure/liquidity breaks,
   classify genuine displacement (range/volume expansion, follow-through) vs wick/sweep/reclaim,
   enter only confirmed rejection or continuation. ~10 trades/week, ~4h holds. Regime gated.
3. **Volatility breakout/trend continuation** for regimes where mean reversion must be disabled.
4. **Session-specific FX effects** (gold desk windows generalize to JPY crosses — hunt6).
5. **Cross-sectional relative strength/carry/value**.
6. **Event/news sleeves** (strong-news filters: FOMC/NFP).
7. **Execution/microstructure alpha**.

## Adaptive machinery (MagicGW/Deux insights, bounded)
- Opportunity-quality score: stay flat unless regime + vol + structure + cost + edge align
  ("do not force trades"; long inactivity is a feature).
- Additional entries spaced FARTHER apart as volatility/DD rise; sized from a bounded risk
  budget — never uncapped martingale/grid.
- Basket-level exits; partial profit-lock with runner only while continuation expectancy > 0.
- Caps: total currency exposure, max simultaneous legs, max add-ons, max basket loss, daily DD,
  account DD, equity kill switch.
- Capital scales only from validated forward expectancy and volatility; champion/challenger
  rotation; capital decays when edge deteriorates, restored only on new evidence.
- Continuous per-symbol/per-regime net expectancy, SR, PF, MAE/MFE, recovery time, slippage
  sensitivity, capacity; allocation to strongest net geometric-growth contribution.

## Trade-path mining
Download/reconstruct every available trade record of ranked systems (entry/exit time, symbol,
direction, hold, simultaneous positions, entry spacing, size progression, MAE/MFE, spread,
session, vol, news proximity). Cluster into setup families; infer entry logic (z-extremes,
dislocations, sweeps, session extremes, divergence, exhaustion, MA displacement, prior-day
levels, vol shocks); infer add-on formula from spacing/lot changes; infer exits (basket price,
residual normalization, ATR, fixed money, time); infer when they deliberately DON'T trade.
Each reconstructed mechanism competes out-of-sample. MQL5 warns historical stats do not
guarantee future profitability — the gate system is the arbiter.

## Target
Several genuinely independent positive-expectancy sleeves combining to >100% portfolio CAGR
full-cycle with controlled drawdown — not one fragile 200% EA, not leverage-driven prints.