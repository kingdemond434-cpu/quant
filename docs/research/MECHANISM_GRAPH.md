# MECHANISM GRAPH — the research-organisation layer (principal 2026-07-27)

**Not a strategy. Not an alpha. A research accelerator.** It consumes zero alpha-testing budget and
changes only *what questions get asked*.

## The shift

| Old question | New question |
|---|---|
| "Can I find another indicator?" | "How many INDEPENDENT ways can I observe the same economic process?" |

A feature that dies tells you nothing about the world. A **mechanism** that dies tells you the whole
family is dead; a mechanism that survives tells you every remaining observable on that chain is worth
building. That is why mechanisms transfer across datasets and indicators do not.

## Rule (binding)

Every hypothesis entering the EV gate must name its **mechanism node**. A hypothesis that cannot name
one is a curve-fit and is rejected before it consumes a forward slot. This is the cheapest possible
filter and it costs no compute.

---

## M1 — LIQUIDITY EXPANSION (the desk's most-covered chain)

    capital enters crypto -> stablecoins minted -> exchange balances rise -> funding changes
      -> perp positioning shifts -> altcoin rotation -> volatility expands

| Node | Observable | Desk status |
|---|---|---|
| capital entry | ETF flows | COVERED (`ingest_etfs`) |
| stablecoin mint | total supply | **LIVE CLOCK** (`stablecoin_supply_momentum`) |
| exchange balances | on-chain reserves | COVERED (`stablecoin_flows`) |
| funding | perp funding | COVERED (carry book, the desk's only real edge) |
| positioning | OI / long-short | **LIVE CLOCK** (`oi_divergence`, `ls_contrarian`, Aug 7) |
| rotation | breadth / dominance | COVERED (`free_signals`, `market_breadth`) |
| vol expansion | Deribit surface, liquidations | COVERED |

**Read:** 7/7 nodes observed — this chain is saturated. New observables here are marginal.
The value is now in *joint* tests along the chain (does node N lead node N+1?), not new sensors.

## M2 — REGIONAL CAPITAL CONTROL (the only chain that ever produced a survivor)

    local capital trapped -> local venue premium -> arbitrage constrained by FX/controls
      -> premium persists and mean-reverts

| Node | Observable | Status |
|---|---|---|
| KR controls | Upbit kimchi premium | **LIVE CLOCK** (flagged `ic_exceeds_contemporaneous`) |
| CN controls | USDT/CNY P2P premium | **LIVE CLOCK** (z warming up) |
| TR / JP / BR | tested | DEAD (arbitraged or timing artifacts) |

**Read:** the mechanism is REAL but venue-specific — it needs *strict* capital controls. Only KR/CN
qualify. Do not test more regional premiums without a capital-control argument first.

## M3 — PARTICIPANT BEHAVIOUR (tested to exhaustion 2026-07-27)

    skilled participants act -> their flow/positioning moves -> price follows

| Node | Result |
|---|---|
| skill persistence | REFUTED (rho -0.019, n=1400, powered) |
| elite positioning | REFUTED (t +0.15) |
| elite order flow | REFUTED (unstable + contemporaneous) |
| **risk-discipline persistence** | **CONFIRMED (t +7.63) — but manager-selection, not market signal** |

**Read:** the *market-signal* branch is dead. The *risk* branch is real but unusable by this desk
(we allocate to no external managers). Mechanism closed unless the desk ever allocates externally.

## M4 — INFORMATION DIFFUSION (untested at the right speed — THE OPEN CHAIN)

    researcher/dev -> code -> regional forums (CN/KR/JP/RU) -> aggregators -> retail -> price

| Node | Observable | Status |
|---|---|---|
| dev activity | commits, contributors | REFUTED at cross-sectional monthly (t <2) |
| attention | multilingual Wikipedia pageviews | **KILLED AT DAILY ONLY -> horizon-search candidate** |
| aggregate interest | search trends | untested |

**Read:** diffusion is INHERENTLY SLOW — days-to-weeks. Every test so far used a 1-day horizon,
which is the wrong clock for the mechanism. This is the single strongest argument for the horizon
search, and the reason `multilingual_wikipedia_attention` sits on the resurrection shortlist.

## M5 — REFLEXIVITY / FEEDBACK (genuinely uncovered)

    price move -> leverage responds -> liquidations -> forced flow -> larger price move

| Node | Observable | Status |
|---|---|---|
| leverage response | OI change vs price change | partially (OI live) |
| liquidation cascade | liquidation stream | COLLECTING (29k events) |
| feedback strength | ??? | **UNBUILT — the real gap** |

**Read:** the desk *collects* every input to this chain but has never modelled the LOOP. The
testable question is not "do liquidations predict price" (tested, weak) but "is the feedback
coefficient rising?" — a regime property, not a signal. Cheapest genuinely-new mechanism available.

---

## Coverage verdict

- **M1 saturated** — stop adding sensors, start testing links.
- **M2 real but venue-limited** — no more premiums without a controls argument.
- **M3 closed** — refuted at power.
- **M4 open and mis-tested** — wrong horizon, not wrong idea. → horizon search.
- **M5 open and unbuilt** — inputs already on disk. → best new-mechanism candidate.

## How this feeds the pipeline

    mechanism node -> observable -> hypothesis -> EV gate -> Stage-A screen -> forward clock -> Stage-B

Unchanged pipeline. The graph only decides *which* hypotheses are worth generating, and makes
"we already observe this process 7 ways" visible before someone builds an 8th sensor.

---

# ADDENDUM 2026-08-05 — the binding rule was being broken inside the generator library

The rule above says every hypothesis must **name its mechanism node**, and that a hypothesis which
cannot is a curve-fit. The autodiscovery lab appeared to satisfy it: every generator carries a
`Family` label, and twelve families read as twelve mechanisms. They are not. Two instruments
measured the gap on the desk's own tape.

**`scripts/measure_cross_mechanism_corr.py`** — 21 symbols × 2,037 aligned bars, all 21 generator
specs at every variant, net of costs:

| pair | declared families | measured ρ |
|---|---|---|
| `shock_fade` vs `zscore_fade` | `liquidity` vs `mean_reversion` | **+0.953** |
| `time_series_mom` vs `vwap_trend` | `momentum` vs `trend` | **+0.955** |

Different families, one trade. The library is two blocs — continuation and fade — correlated
within and anti-correlated across, so the near-zero *mean* off-diagonal ρ (+0.005) is cancellation,
not independence. The participation ratio reads **N_eff = 4.08**, ceiling **2.02×**, against the
~100 effective bets Sharpe 2.0 from Sharpe-0.2 components would need.

**`scripts/run_mechanism_census.py`** — the 44-candidate maximum-power campaign resolves to **four**
economic classes: `price_continuation` 20, `liquidity_provision_immediacy` 19,
`relative_value_convergence` 4, `market_risk_premium` 1. Effective classes **2.787**, diversity
**0.139**. Eleven declared families, four payers.

## The call: `Family` is NOT renamed, because it is a gate input

`Family` is the pre-registered **search-budget partition**, and moving a spec between families is a
gate change rather than a rename:

| consumer | what the family string does there |
|---|---|
| `orchestrator._family_trials` | the DSR trial wall is per-family — moving one spec re-prices the bar for every other spec in the donor and receiving family |
| `orchestrator._fam_sharpes` | the Sharpe **dispersion sample** fed to `deflated_sharpe_ratio` is the family's own column set |
| `memory.content_hash` | `family+subtype+symbol+params` — every persisted candidate's dedup identity, and the key behind `store.family_counts()` |
| `prioritization.prioritize` | orders the campaign by `FAMILY_PRIORITY` |
| `planned_hypotheses(families=…)` | selects the generation universe; `scripts/smoke_orchestration.py` asks for carry/cross_asset/momentum **by name** |

Relabelling `drift_proxy` from `carry` to `momentum` would have emptied `Family.CARRY`, added a
column to the momentum DSR dispersion sample and shifted the momentum trial wall — changing how a
gate treats candidates *other than the one relabelled*. So the labels stand and the two axes are
separated instead: **a family names the feature construction and the error budget it is charged to;
it never names the payer.** `libs/research/mechanism_census.CONSTRUCTION_CLASS` is the single
authority for the payer, and `libs/autodiscovery/generators.py` now defers to it in code
(`census_class`, `mechanism_class_counts`, `FAMILY_MECHANISM_DIVERGENCE`).

## CARRY COVERAGE: none until `funding_carry`, and the obstacle was a return path

For the entire life of this library `Family.CARRY` held exactly one generator, and it was not
carry. `drift_proxy` is `momentum_positions(lookback=200)` on OHLC bars — no funding rate, no swap
rate, no basis anywhere in its inputs, which is why the census files it under `price_continuation`.
The single `carry`-family row in the 44-candidate campaign was a momentum test, and that has not
changed: `drift_proxy` is still not carry and still carries its divergence entry.

A true carry test is `derivative_carry_basis`: the leveraged long who pays funding every interval
to hold exposure he will not fund with cash. **`funding_carry` is now that test.** The data was
never the obstacle — `MarketSeries.funding` has been populated by the crypto adapter throughout,
and was read by exactly one generator: the *fade* (`funding_stress_reversal`). What was missing was
a RETURN PATH. `net_returns` computes `position × spot_return`, which is the P&L of a directional
bet and the wrong P&L of a delta-neutral carry, whose legs cancel and whose entire return is
accrual. Scoring a carry through the price path would have measured spot direction and filed the
answer under `derivative_carry_basis` — `drift_proxy`'s error committed a second time, with better
inputs. `carry_returns`, the `delta_neutral` spec flag and `returns_for` exist for that reason, and
a test fences every scoring call site against reaching for `net_returns` directly.

Scoped precisely, because the opposite overstatement is just as bad: the desk **also** holds real
`derivative_carry_basis` evidence elsewhere — funding/basis screen artifacts and a live
cash-and-carry book, which the census reads and marks TESTED-DEEP. The gap was always about the
generator campaign, the run whose "44 mechanisms" figure was being quoted.

Worth stating in the same breath: `derivative_carry_basis` scores **0.30 orthogonality**, among the
lowest on the board, precisely because it *is* the desk's existing live family. Closing this hole
adds return and coverage. It does not add diversification and it does not move `k_eff`.

## Corrected counts — the full 21-spec library

| census class | specs |
|---|---|
| `price_continuation` | **11** — `ma_cross`, `time_series_mom`, `donchian`, `squeeze_breakout`, `vol_trend`, `session_open_mom`, `drift_proxy`, `vol_onset_trend`, `vwap_trend`, `ict_fvg_follow`, `ict_mss_follow` |
| `liquidity_provision_immediacy` | **6** — `zscore_fade`, `shock_fade`, `wyckoff_spring`, `vwap_reversion`, `supply_demand_retest`, `ict_sweep_reversal` |
| `relative_value_convergence` | **2** — `inverse_reference`, `intermarket_difference` |
| `positioning_crowding_unwind` | **1** — `funding_stress_reversal` (the only spec drawing on non-price data) |
| `market_risk_premium` | **1** — `persistent_long` |

**21 specs, 12 families, 5 mechanisms.** The campaign is four, because `session_open_mom` and
`funding_stress_reversal` never ran on that tape (no intraday clock, no funding series).

## What changed, and what did not

Labels and docs only — no signal logic, no parameters, no gate, no threshold, no verdict.
`drift_proxy`'s declared prior moved `RISK_PREMIUM → BEHAVIORAL` (it shares an implementation with
`time_series_mom`), its `edge_source`/`failure_modes` now say plainly that it is momentum and not
carry, and its implementing function was renamed `_carry` → `_drift_proxy`. `MechanismType` carries
no gate — `validation.validate` reads only `bool(hypothesis.failure_modes)` from the hypothesis and
`content_hash` excludes the mechanism value — so that correction is free of behavioural effect.
`funding_stress_reversal` records its true class in its failure modes. Both keep their family.

## The fence

`tests/autodiscovery/test_generator_taxonomy_fence.py` — every generator must be classified by the
census or it cannot ship; the computed family/mechanism divergence set must match the register in
`generators.py` **exactly** (a new mislabel fails unrecorded, a fixed one fails stale); a
`RISK_PREMIUM` prior is admissible only where the census's payer is actually shedding a risk; the
two ρ > 0.95 cross-family pairs must stay inside one census class; and the zero-carry claim is
asserted **both ways**, so it must be removed the day a real carry generator ships. A legitimate new
family passes and a mislabel fails — both directions proved on synthetic specs, not asserted.
