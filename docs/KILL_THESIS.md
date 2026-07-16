# Kill-Thesis & Deployment Bar (pre-committed)

This document is written **before** results so the bar cannot move after them. It encodes the
investment-committee decision: optimize for *net-of-cost* deployable alpha and long-term geometric
growth, never for appearance. Finding zero survivors is acceptable. Finding a false survivor is not.

The opportunity-cost benchmark for all capital is **low-cost factor/index ETFs**. Any active
research must beat that *net of cost and net of the value of one's own time* to be rational.

## Deployable bar (a candidate must clear ALL, net of real cost)

| Gate | Threshold |
|---|---|
| Net-of-cost annualized Sharpe | >= 0.7 (using calibrated per-symbol MT5 cost, not a flat fee) |
| Cross-campaign deflated DSR | significant at p < 0.05 on **cumulative** trials across all campaigns |
| Probability of Backtest Overfitting (PBO) | < 0.5 |
| Walk-forward | PASS |
| Regime robustness | net-positive in >= 2 distinct regimes |
| Capacity | >= deployable capital, with <= 30% edge erosion under execution-gap stress |
| Economic mechanism | declared, with failure modes, before testing |

A candidate that clears the bar earns **REGISTRY** (eligible for human review) and, only on explicit
human approval, **tiny** real capital. Real capital is never allocated automatically.

## Kill criteria (stop active research; move capital to factor ETFs)

- After a full 90-day cycle: **zero** candidates clear the deployable bar in the chosen niche
  **and** the net-of-cost re-run of all prior work is negative **and** (if attempted) a second niche
  also yields zero.
- OR calibrated round-turn cost **structurally exceeds** the plausible gross edge for the instrument
  class (the venue is adversarial) — stop trading that venue/instrument regardless of signal.

## Pivot criteria (one switch allowed inside a cycle)

- Niche A clears nothing net, but execution-gap and cost are acceptable -> switch to niche B.
- Cost is the binding killer -> pivot venue/instrument (e.g., lower-cost futures) before abandoning.

## Continuation / double-down criteria

- >= 1 candidate clears the full deployable bar **and** holds positive net-of-cost in tiny live for
  the test window -> scale via the existing Kelly-fraction governance gate; continue research in
  that niche only.

## What success is measured by

Validated survivors; survivor persistence; shadow/paper survival; portfolio diversification benefit;
long-term geometric growth. **Not** backtests run, strategies generated, or backtest CAGR.

## Active shadow candidate — cross-sectional crypto funding (pre-committed rule)

The cross-sectional liquid-perp funding strategy (frozen: lookback=7, q=0.2, band=0.02) reached
~0.96 net-of-cost Sharpe and passed 8/9 gates, failing only White's Reality Check (data-snooping
significance). It is in **forward shadow (zero capital)**, run daily by `scripts/run_shadow_forward.py`.
Decision is resolved FORWARD, never by re-tuning:

- **Accumulate** until >= 90 trading days of forward out-of-sample evidence.
- **Promote to TINY live** (human approval + governance gate) only if, at >= 90 days, the forward
  Sharpe is >= 0.5 AND >= half the backtest Sharpe AND a re-run of the full gauntlet (now including
  the live data) clears Reality Check.
- **Kill** if forward Sharpe goes negative, or live materially underperforms backtest (overfit/decay).
- Never tune the frozen parameters to pass a gate. The frozen variant is the only one tracked.

## Active shadow candidate — MT5 cross-asset combo (pre-committed rule)

Architecture (user-set): research globally, **execute natively on MT5 (sole venue)**. The Python
brain builds the most robust MT5-executable book — an equal-risk combo of cross-asset **trend**
(lookback=100) + cross-sectional **momentum** (lookback=120), frozen — over the 30-instrument
multi-asset lake, net of per-asset-class cost. It reached ~0.62 net-of-cost Sharpe and passes 7/9
gates, failing **PBO + fragility** (so it is NOT deployable). `scripts/run_crossasset_shadow.py`
tracks it in **forward shadow (zero capital)** and emits today's target portfolio to
`data/target_portfolio.json` — the artifact the rebalancer + `EABridge` + `QuantPlatformExecutor.mq5`
would execute. The EA only executes an **approved** target; capital is never allocated automatically.

- **Accumulate** >= 90 trading days of forward OOS evidence.
- **Promote to TINY live** (human approval + governance gate) only if, at >= 90 days, the forward
  Sharpe is >= 0.5 AND >= half the backtest Sharpe AND a full gauntlet re-run (now including the live
  data) clears **both** PBO and fragility.
- **Kill** if forward Sharpe goes negative, or live materially underperforms backtest.
- Never tune the frozen parameters to pass a gate. Note this premium is also sold cheaply as a
  managed-futures ETF (DBMF/KMLM) — deploy only if it beats that net-of-cost benchmark.
