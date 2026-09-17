# THE TIER-2 BLUEPRINT — from effective breadth 4.879 to a breadth machine

**Governance class: §36 CADENCED.** Producer: this document is refreshed at each phase gate below.
Staleness floor: 30d while any phase is OPEN; TERMINAL once Phase 5 closes or is abandoned by
named decision. Classified on arrival per `ARTIFACT_GOVERNANCE.md` — a blueprint that is not
itself governed is the miner problem in miniature.

**Scope.** This is the build plan for a Tier-2 *research and trading machine*. It is not a plan to
become a Tier-2 *firm*: that has a capital prerequisite (capacity constraints only bite at scale)
which no amount of engineering substitutes for. The machinery is the part the desk controls, and
it is worth building on its own terms — an operation with Tier-2 machinery and €607 is one
funding event away from a Tier-2 business, while the reverse is not true.

---

## Part 0 — What Tier 2 means, in one equation

Grinold's Fundamental Law:

```
IR  ≈  IC × √BR
```

Information ratio is skill per bet times the square root of the number of *independent* bets.
Tier 2 firms are not smarter per bet than this desk. AHL and AQR run ICs that would embarrass a
good discretionary trader — 0.02 to 0.05. They reach IR 1.0–1.8 because BR is in the hundreds.

**The desk's own instrument, `alpha_breadth.py`, published the number on 2026-09-12:**

```
n_nominal 56  →  effective_breadth 4.879   (headline = MIN of readings)
n_clusters_occupied 4   |   n_clusters_empty 11
```

√4.879 = 2.21. √200 = 14.1. **That factor of 6.4 is the entire distance between this desk and
Tier 2**, and it is not reachable by improving IC — the gauntlet already protects IC better than
most institutions. Every machine below exists to raise BR.

The concavity is the whole reason this is tractable. With `k_eff = n/(1+(n-1)ρ)`, the twelfth
correlated sleeve buys almost nothing and the first uncorrelated one buys the most. The desk
already wrote that sentence into `alpha_breadth.py`. This document is what follows from taking it
seriously.

**Target shape:** 10–13 of 15 clusters occupied, nominal 200–400 sleeves, effective breadth
40–80, per-sleeve risk 0.10–0.40% of equity, portfolio vol targeted rather than per-trade sized.

---

## Part I — The finding that reorders the work

**This corrects the first-pass audit recommendation.** That pass said *"expand the data axis —
nothing else competes."* Measured against the actual cluster taxonomy, that is wrong as a
*first* move. Auditing all 15 clusters in `libs/research/alpha_clusters.py` against the data
already on disk (22 symbols × H1/M15, COT TFF + disaggregated, FRED fetchers, broker swap
records, event calendar, GC futures with contract volume):

| # | Cluster | Data requirement | Status on data **already held** |
|---|---|---|---|
| 1 | `session_liquidity` | intraday bars | **OCCUPIED** — all 4 gold sleeves live here |
| 9 | `mean_reversion` | intraday bars | **OCCUPIED** — `xau_m15_anti_breakout` |
| 5 | `relative_value` | ≥3 correlated pairs | **UNBLOCKED** — 19 FX pairs; triangles/cointegration/PCA residuals computable today |
| 14 | `cross_sectional_fx` | a basket to rank | **UNBLOCKED** — 19 pairs is exactly the right universe |
| 8 | `trend` | long history, many markets | **UNBLOCKED** — 8yr × 22 symbols; the classic CTA edge, never tested here |
| 7 | `volatility_transition` | intraday bars | **UNBLOCKED** — compression→expansion needs nothing new |
| 6 | `fixing_roll_calendar` | timestamps + calendar | **UNBLOCKED** — WMR/ECB fixings, month/quarter end are known times |
| 15 | `crisis_drawdown` | book history | **UNBLOCKED** — conditional sign test, not standalone Sharpe |
| 10 | `positioning_flow` | COT / OI | **PARTIAL** — COT held; tested on *gold only* (t≤0.8, graveyard). Untested across 19 FX. |
| 3 | `macro_rates` | rate differentials | **PARTIAL** — `fetch_fred.py` + `broker_swaps` give carry; never assembled |
| 4 | `event_surprise` | actual vs **consensus** | **PARTIAL** — calendar held, consensus missing |
| 13 | `news_reaction` | headline feed | **PARTIAL** — BIS speech tone + CB intelligence exist |
| 2 | `cross_asset_lead_lag` | a *leader* market | **BLOCKED** — no rates/oil/index futures (GC bars are a start) |
| 11 | `options_implied` | vol surface | **BLOCKED** — no options feed |
| 12 | `execution_entry` | own markouts | **BLOCKED BY OUR OWN BUG** — markouts 0/52 |

**Six clusters are fully unblocked on data already sitting in `desks/mt5/universe/`.** Four more
are partially unblocked. Only two are genuinely gated on data the desk does not own — and the
twelfth is gated on a telemetry defect we created ourselves.

So the binding constraint is not the data axis. **It is that every research hour for six months
has been aimed at cluster #1.** Four live sleeves and the deepest hunts (hunt6→hunt12, the
pyramiding sweep, the runner-exit sweep, the NY-open probe) all live inside `session_liquidity`.
The desk has been drilling one hole deeper instead of drilling new holes.

Universe expansion still matters — it is Phase 3 — but it is not what unlocks the next tripling
of breadth. **Aiming is.**

---

## Part II — The eight machines

Most of this is already written. The repo's own `REPO_MAP.md` says 227 of 302 `libs/` modules are
orphaned; the audit sampled them and found real implementations — Ledoit-Wolf shrinkage toward a
constant-correlation target, `B F B' + diag` factor risk, gap-aware portfolio heat, PIT as-of
joins with offline/online parity. They are correct kernels, thin (60–140 lines each), and
unintegrated. The Tier-2 build is **≈65% wiring, ≈35% net-new**.

### M1 — Cluster Supply Engine `[AIM — mostly exists]`

The generator currently proposes into whatever the bandit's arms favour, and the arms have
converged on cluster #1 because that is where the wins were. That is textbook exploitation
collapse.

- Make `cluster_of()` a **first-class arm** in `libs.research.bandit.SOURCE_ARM`, not a
  post-hoc label. Empty clusters get a floor allocation that exploitation cannot take.
- `alpha_breadth.py` already writes empty clusters into the deepening queue. Make that queue
  **binding on the generator's next batch**, not advisory.
- Add a **marginal-breadth prior** to hypothesis ranking: score a candidate by its expected
  contribution to `k_eff`, not its standalone t-stat. A t=2.6 sleeve in an empty cluster beats a
  t=4.0 sleeve in `session_liquidity`, and the current ranking says the opposite.

*Exists:* `alpha_clusters.py`, `alpha_breadth.py`, `bandit.py`, `research_departments.py`.
*Net-new:* the floor, the binding queue, the marginal-breadth term.

### M2 — Feature Store with point-in-time discipline `[WIRE]`

- Wire `libs/features/{registry,pit,definition,labels,builtin}.py` — currently orphaned.
- One definition compiles to both the offline table and the online vector. `pit.py` already
  guarantees this by construction; nothing consumes it.
- Every feature carries: source, vintage, publication lag, revision policy. **A feature without a
  publication lag is a lookahead waiting to happen** — this is defect #1 from the promotion
  protocol (the NY-session label that hadn't happened yet), and a feature store is the structural
  fix that makes it unrepeatable rather than remembered.

### M3 — Signal Factory `[WIRE — the ceiling is already lifted]`

`libs/research_os/dsl.py` measured the bottleneck exactly: **236 queued proposals refused for
capabilities the desk could not express** (`cross_sectional_rank`, `multi_leg_spread`,
`term_structure`, `order_flow_data`). The DSL — JSON trees, allowlisted ops, no `exec`, no
`eval` — was the correct answer and is built.

- Run the 236 refused proposals back through the DSL. That backlog is the cheapest breadth on the
  board and it is already queued.
- Add combinatorial generation over `(cluster × instrument × horizon × conditioning state)`. The
  gauntlet's multiplicity machinery already prices the search honestly — which means **generating
  more is nearly free statistically**, because the Holm bar grows as √log(m) while the candidate
  count grows linearly. The desk is currently paying a multiplicity correction it isn't using.
- `mutation.py` + `surrogate.py` give cheap pre-screening before the expensive gauntlet.

### M4 — Cross-sectional portfolio backtester `[WIRE + EXTEND]`

Today's backtests are per-sleeve, per-instrument, in R multiples. Tier 2 backtests a **portfolio**:
a universe, a rank, a weight vector, a rebalance, a cost model, a vol target.

- `libs/backtest/cross_engine.py` and `portfolio.py` exist. Promote them to the default path.
- Output must be a **return stream in account currency**, not R. R is unaggregatable across
  instruments with different tick values — defect #5 in the promotion protocol was a units error
  of exactly this family, and it nearly deleted the JPY crosses where the edges live.
- Every candidate produces a daily return vector on a common calendar, so correlations against the
  live book are computable **before** promotion rather than after.

### M5 — The Gauntlet, at throughput `[HAVE — this is the strong part]`

CPCV with purge+embargo, PBO/CSCV verified against the naive reference, DSR fed by the trials
ledger, Hansen SPA, lockbox, positive/negative controls, per-family Holm/BH bars. This is genuinely
top-decile and needs no methodological work.

- Scale it: parallel evaluation, surrogate pre-screen, the vectorised PBO path already landed.
- Keep family bars per **cluster**, so a crowded cluster is penalised and an empty one is not.
- **Do not tighten the gates.** They already exceed the information content of the data feeding
  them. Marginal effort on gate quality now has negative expected value.

### M6 — Portfolio construction and risk `[WIRE — the biggest orphaned asset]`

This is where breadth converts into IR, and it is almost entirely written and entirely unwired.

- `libs/portfolio/factor_model.py` — ShrinkageCovariance + FactorRiskModel. Wire it.
- `libs/portfolio/{optimize,hrp,multiperiod,constraints,rebalance}.py` — the optimiser set.
- `libs/risk/{heat,tail,drawdown,correlation,factor_caps,risk_budget,vol_target}.py` — 14 modules,
  "~all of Phase 6 exists" per REPO_MAP, orphaned.
- **Replace fixed-fractional per-trade sizing with portfolio vol targeting.** Current: 5.5% risk
  per trade, `P_DD_gt_50_pct = 0.41`. Target: 10–15% annualised portfolio vol, per-sleeve risk
  0.10–0.40%, correlation-aware. This is not a risk-aversion preference — **it is required by the
  growth objective.** Betting past Kelly reduces long-run growth, and a 50% drawdown requires a
  100% gain to recover. At P=0.41 the current sizing is more likely than not to spend the
  compounding period climbing out of a hole.
- Feed `timestamp_overlap` (already computed, deliberately held out of the headline) into the
  allocator, at which point it legitimately earns leverage that the return-correlation readings
  alone do not support.

### M7 — Execution and TCA `[FIX, then BUILD]`

Cluster #12 (`execution_entry`) is a real P&L source with no market view at all, and it is blocked
by our own instrumentation.

- **Fix the 19% reject rate.** 10 of 52 records are `retcode 10015 / invalid_price` on pending
  stops — almost certainly stops-level/freeze-level violations. Every forward statistic collected
  before this is fixed is corrupted by non-random order loss.
- **Gate on `predicted_p_fill`.** It emitted `8.9e-267` and `2.0e-120` and the orders went out
  anyway. An uncalibrated model in the live path that nothing reads is worse than no model.
- **Refuse to trade on a stale allocator.** `"no allocator book: pf_allocation.json is 115 min
  stale"` appears in live fill records. Staleness must veto, not annotate.
- Build markout curves (1s/5s/30s/5m), slippage attribution, and a cost model **fitted from the
  desk's own fills** rather than assumed from median spread.
- Then: passive-vs-aggressive entry, queue position, TWAP/POV instead of naked stops.

### M8 — The measurement loop `[BUILD — this is the open circuit]`

The most expensive defect in the repo. `realized_r` 7/52, `markout_5m_r` 0/52, `mae_r` 0/52,
`mfe_r` 0/52, `exit_reason` 0/52, `commission_r` 0/52.

Without realized R the desk cannot measure decay, cannot measure capacity, cannot compare live to
backtest, and cannot ever retire a sleeve on evidence. **The promotion protocol terminates in an
unmeasurable state** — WS-005 at the end of the pipeline instead of the start.

- Close deal → exit → realized R, in account currency, joined to the decision that caused it.
- Live-vs-backtest divergence alarm: when realized distribution departs the modelled one beyond a
  pre-registered bound, the sleeve is flagged automatically.
- Attribution: P&L decomposed by cluster, instrument, session, and **execution vs signal**.

---

## Part III — Additional machinery (net-new, no current equivalent)

1. **Factor risk model for the actual universe.** USD/EUR/JPY/commodity-currency factors, a
   metals factor, a vol factor, a carry factor. Every sleeve gets exposures; the optimiser caps
   factor risk rather than instrument risk. *Without this, 200 sleeves will silently be one bet.*
2. **Meta-labeling.** A second model on *whether to take* the primary signal (López de Prado).
   Raises precision without touching the primary's already-validated edge — one of the few ways
   left to raise IC rather than BR.
3. **Capacity model per sleeve.** Expected slippage as a function of size and ADV. Institutional
   strategies are defined by knowing where they stop scaling; this is also what makes the book
   fundable.
4. **Ensemble / combination layer.** Signals combine into one target position per instrument
   before the optimiser, so 40 sleeves on EURUSD net rather than 40 separate orders.
5. **Crowding and decay monitor.** Half-life estimation, live IC tracking, automatic retirement on
   pre-registered decay criteria. `libs/signal_engine/{decay,crowding}.py` exist, orphaned.
6. **Regime as a conditioning factor, not a filter.** `libs/regime/` (HMM/GMM/Bayesian) exists.
   Condition sizing on regime probability rather than hard-gating entries.
7. **Anytime-valid monitoring.** `libs/research/anytime_valid.py` exists — e-values/confidence
   sequences let a live sleeve be monitored continuously without the peeking penalty that makes
   fixed-n tests invalid under repeated looks. Directly relevant with 12 forward slots.
8. **Research allocator on the measured shadow price.** `research_departments.py` already names
   the binding resource (compute / forward slots / data / statistical sample). Make it *spend*
   against that, and add forward-slot expansion as a purchasable resource — with 69 enrolled and
   12 slots, the principal's own words apply: *"reality is the bottleneck."*

---

## Part IV — Sequencing, with gates

Each phase has a kill/advance gate. No phase starts before the prior one's gate is measured.

**Phase 0 — Stop the bleeding (2 weeks).**
Fix reject rate; gate `predicted_p_fill`; staleness vetoes; close the realized-R loop; repoint the
coverage ratchet and mypy at `desks/mt5/mt5desk/gateway.py`; refresh the stale
`MT5_DESK_STATE.json` (it still says Vantage/€633.89 while `account_state.json` says
Fusion/€607.68 — defect #8, live, in the desk's own headline file).
*Gate:* realized R populated on ≥95% of closed intents; reject rate <2%.

**Phase 1 — Aim the generator (4 weeks).**
M1 + M3. Cluster floors, binding deepening queue, marginal-breadth ranking, the 236 refused
proposals through the DSL.
*Gate:* ≥3 previously-empty clusters have candidates through the gauntlet.

**Phase 2 — Portfolio machine (6 weeks).**
M4 + M6. Cross-sectional backtester as default; wire the optimiser and risk modules; switch to
portfolio vol targeting.
*Gate:* `effective_breadth ≥ 12` and `P(DD>50%) < 0.10` on the modelled book.

**Phase 3 — Universe and data axes (8 weeks, parallel with 2).**
Indices, energy, rates, softs, share CFDs — the universe the MT5 mandate already claims and the
disk does not hold. M15/M5 across the whole universe. Event consensus. This unblocks clusters
2, 3, 4, 13.
*Gate:* ≥80 instruments × ≥3 timeframes in the lake, PIT-clean.

**Phase 4 — Execution alpha (6 weeks).**
M7 in full. Markouts, TCA, cost model fitted from own fills, execution algos. Unblocks cluster 12.
*Gate:* measured markout curve; modelled vs realised cost within 20%.

**Phase 5 — Scale and capacity (ongoing).**
Part III items 1–8. Factor model, meta-labeling, capacity, ensemble, decay.
*Gate:* `effective_breadth ≥ 40`, ≥10/15 clusters occupied, capacity curve published per sleeve.

---

## Part V — Governance corrections (do these regardless)

1. **The coverage ratchet guards dead code.** `money_path_files` on the live branch is five Binance
   modules that can never execute again under the standing crypto ban. The 3,944-line
   `gateway.py` that sends real orders is not tracked. Repoint it.
2. **`desks/` is outside mypy.** `files = ["libs", "app", "migrations", …]`. `strict = true` runs
   over research code and skips the money path entirely.
3. **Add a breadth ratchet.** `effective_breadth` gets a floor that ratchets up only, exactly like
   the coverage floor. It is now the desk's primary objective and should be defended like one.
4. **Add an occupancy gate to promotion.** A candidate in an already-occupied cluster must clear a
   *higher* bar than one in an empty cluster. Encode the concavity of `k_eff` into the protocol
   rather than leaving it to judgment.

---

## What this does not fix

Capital. At €607.68 the book cannot express 200 sleeves at 0.2% risk — minimum lot sizes bind long
before the weights do. The machinery is worth building anyway: it is the asset, it is what makes
the track record legible to an allocator, and it is the part that does not arrive by luck. But the
blueprint should be honest that Phase 5's gate is reachable in research and **not** in the live
book at current equity.

Also unfixed: the SR 2.34 question. A durable net-of-cost Sharpe of 2.34 from session-range
breakout — a mechanism in every retail trading book since the 1990s — on free H1 gold data, is on
its face implausible. The desk's own law covers it: *"Implausible abundance is a bug report."*
Forward is the only thing that settles it, and forward is currently **n = 1 fill**.

---

## ERRATUM — 2026-09-17: the universe claim in this document's first revision was WRONG

**What the first revision said:** "22 symbols, one timeframe, 8yr of H1"; "you hold NO indices,
energy, softs or share CFDs"; and a Phase 3 costing eight weeks to "ingest the universe the MT5
mandate already claims."

**What is actually on disk.** The first revision read `desks/mt5/universe/` — the legacy
research universe, 23 symbols — and never opened `desks/mt5/data/universe/`, which holds
`universe.canon.json`: **251 symbols with full instrument metadata** (asset class, contract size,
tick value, swap long/short, median spread, bar count, provenance stamps). `bar_coverage_skips.json`
records the ingest: **attempted 259, written 247, skipped 12.**

| Asset class | Symbols |
|---|---|
| Equities | 103 |
| Forex Exotics | 57 |
| Forex | 29 |
| Indices | 16 |
| Crypto | 14 |
| Commodities | 12 |
| Soft Commodity | 11 |
| Bonds | 3 |
| Energy | 3 |
| unset | 3 |

Timeframes: **H1 + H4 + D1** on 248 of 251, not one. Median history **23,077 bars**.

The 12 skips are measured, not missing work: WTI, BRENT, USOIL, USTEC and SPX500 are recorded
`NOT_OFFERED — the broker does not quote this symbol on this account`. US index and oil exposure
is a Fusion account limitation, not a research gap.

**Consequences.**

1. **Phase 3 as written is deleted.** The universe expansion it proposed is substantially already
   done. What remains of it is narrow: fill the M15/M5 axis (currently H1/H4/D1), and source
   event consensus. Neither is eight weeks.
2. **The factor-rank ceiling in the first revision was computed on the wrong universe.** Measured
   on the real one: 86 FX pairs span **27 currencies**, hard rank **26**, participation rank
   **12.81** — against the ~7 the first revision claimed. Adding 103 equities (market + sector),
   16 indices (regional), 12 commodities, 11 softs and 3 bonds, the realistic count of independent
   directions is **35–50**. That is an estimate, not a measurement: it needs the returns matrix,
   and computing it is the first job of the factor model in M6.
3. **Cluster blocking is almost entirely relieved.** The first revision called
   `cross_asset_lead_lag` BLOCKED for want of a leader market; with 16 indices, 3 bonds, 3 energy
   and 12 commodities on disk, it is unblocked. `macro_rates` is unblocked — `universe.canon.json`
   carries `swap_long`/`swap_short` per symbol, which is carry, measured, per instrument.
   **Thirteen of fifteen clusters are now computable on data already held.** Only
   `options_implied` (no vol feed) and `execution_entry` (blocked by our own markout defect)
   remain.
4. **The demotion of `trend` is withdrawn.** It rested on trend consuming factor rank the book
   already holds — true across 22 FX pairs, false across 251 instruments in 9 asset classes.
   Cross-asset trend is the canonical diversifying CTA edge and should sit in the first wave.

**What this does NOT change, and what it strengthens.** Every Phase 0 finding stands untouched:
`realized_r` 7/52, markouts 0/52, a 19% reject rate, `predicted_p_fill` at 1e-267, the coverage
ratchet guarding five retired Binance modules, `desks/` outside mypy. And the central thesis of
Part I is now far stronger than when it was argued from scarcity: **247 instruments across nine
asset classes on three timeframes are on disk, and the live book is four session-breakout sleeves
on one metal, with measured effective breadth 4.879.** The first revision reached "the constraint
is aiming, not data" while still believing the data was thin. It is not thin. The desk has
ingested a genuine multi-asset universe and is researching roughly 1.6% of it.

Headroom within data already held is therefore not the 1.4x the first revision's ceiling implied.
It is **on the order of 7–10x**, and none of it is gated on an ingest.
