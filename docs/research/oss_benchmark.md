# OSS engineering benchmark — us vs the best public codebases

_Maintained by the monthly governance review (see SKILL). First edition 2026-07-11. Rule: extract
PATTERNS worth adopting (EV-gated), never wholesale migration. Companion: [[institutional_knowledge]]._

## The comparison set
- **nautilus_trader** — Rust-core event-driven trading platform, Python API; the best-engineered
  public execution/backtest engine.
- **qlib (Microsoft)** — ML alpha-research platform: factor zoo, walk-forward, point-in-time data.
- **hummingbot** — multi-venue market-making execution client.
- **freqtrade** — retail bot framework; big community, hyperopt culture.

## Dimension-by-dimension (honest, no home-team bias)

| Dimension | Winner | Detail |
|---|---|---|
| Execution engine | **nautilus, decisively** | event-driven, nanosecond clocks, typed order state machine, OMS, live/backtest parity. Ours: REST polling at 10-min cadence — *adequate for carry, outclassed for anything intraday* |
| Backtest fidelity | **nautilus** | tick/L2 replay vs our daily bars. Matters only if an intraday edge ever validates |
| Multi-venue abstraction | **nautilus / hummingbot** | clean adapter pattern, many venues. Ours: 2 bespoke testnet connectors |
| Code quality / tests | **nautilus** | thousands of tests, typed domain model, CI/CD at library grade vs our ~25 targeted tests + ruff/CI. Multi-year multi-contributor vs solo-weeks |
| Performance | **nautilus** (Rust) | irrelevant at our cadence — a 10-min loop doesn't need microseconds |
| ML research tooling | **qlib** | factor zoo + PIT data handling. Also an overfitting factory without our gauntlet |
| **Validation / anti-overfitting** | **US, decisively** | CPCV + DSR + PBO + Reality-Check + frozen forward shadows + pre-registration. **None of the four have ANY of this** — freqtrade's hyperopt is institutionalized curve-fitting |
| **Research governance** | **US — no public equivalent** | EV gate, decision ledger, graveyard w/ meta-learned priors, root-cause engine, deferral discipline |
| **Autonomous operation** | **US — no public equivalent** | self-healing watchdog, daily AI research cycle, self-improving governance, knowledge compounding. All four are tools a human must drive |
| **Honesty/accounting machinery** | **US** | two-venue symmetric realized P&L, income pagination, phantom-loss detection, growth audit. The others hand you primitives and let you lie to yourself |
| Risk governance | **US** | E[log] objective, endogenous Kelly/ruin caps, black-swan sizing, kill switches as governance. Others: basic per-trade stops at best |
| Strategy content | **US** | they ship empty engines; we ship a validated-track candidate + pipeline |

## The verdict
They built better **chassis**. We built a better **driver, rulebook, and self-driving system** —
with an engine that is exactly good enough for its cadence. The rarest asset here is ours: the
honesty/validation/governance layer has no public equivalent in any of these projects, and it is
the layer that decides whether a trading system survives. Theirs is replaceable (it's public);
ours is not (it's the accumulated discipline).

## Adoption candidates (EV-gated; revisit monthly)
1. **More executor-path tests** (nautilus's test culture) — cheap, positive EV, queue-able anytime.
2. **Typed order-state handling** — adopt ONLY if intraday execution ever validates.
3. **Adapter pattern for venues** — adopt WHEN a second execution venue clears the EV gate.
4. **qlib-style PIT discipline** — largely already honored (lagged signals, no look-ahead); audit on each new dataset.
5. **Wholesale migration to nautilus** — REJECTED at current cadence: rewrite risk + weeks of effort
   for zero growth at 10-min rebalances. Standing revisit trigger: a validated intraday edge.

## Standing conclusion
Never trade the governance layer for engine polish. If we ever go intraday, rent their chassis
(adapter) — never their empty rulebook.
