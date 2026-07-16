# System Review Document — Autonomous Solo Quant Trading Desk

**Purpose of this document:** complete technical and methodological description of this system,
written for external adversarial review by other AI models. Reviewers: your job is to find flaws,
blind spots, overfit reasoning, and structural risks. Nothing here is marketing — the "Known
Limitations" section is honest and the review questions at the end are genuine. State as of
2026-07-12.

**THIS IS A SECOND-ROUND REVIEW.** Round 1 (five independent models, 2026-07-12) produced four
consensus findings — naive IID t-stat on autocorrelated forward returns, no multiplicity
correction across the forward cohort, an over-fast discrete Kelly ladder, and ADL/basis tail
gaps — ALL of which were implemented the same day. This document describes the POST-FIX system.
Your job now: find what round 1 missed, and what the fixes themselves newly broke.

---

## 1. Executive summary

A fully autonomous systematic crypto trading desk built and operated by one principal (18, solo,
budget-constrained) plus an AI research officer (Claude, running a daily scheduled cycle at
maximum reasoning depth). The organization itself is software: research, validation, execution,
risk, governance, ops, and self-improvement all run as code + one daily AI session. Currently
trading Binance TESTNET capital (~$10k across two accounts) with a fully-armed automatic
live-deployment policy awaiting a one-time human setup (live account + trade-only keys + deposit).
Stack: Python 3.12, ~590 tracked files, JSON state + Markdown knowledge + Parquet data lake,
single Windows laptop (VPS migration scheduled July 2026).

Design philosophy in one line: **Tier-1 institutional process on Tier-4 resources — every decision
evidence-gated, every mistake paid for exactly once, aggression maximized strictly within
survival constraints.**

## 2. Deployed strategy: delta-neutral cash-and-carry (funding harvest)

- Long spot (Binance spot testnet) + short USDT-perp (Binance futures testnet), dollar-matched per
  name, on the top-10 positive-funding perps tradeable on both venues. Harvests the 8-hourly
  funding payments; the two legs cancel price risk.
- Funding-weighted capacity allocation with an iterative water-fill concentration cap (35% max per
  name). ~$4.5k target deployment (~80% of deployable, buffer retained for reconcile/slippage).
- Hysteresis: hold while funding stays positive (a prior rank-cutoff rule caused churn — 159
  closes/week, median hold 2.9h, fees ≈ entire funding harvest; root-caused and fixed 2026-07-08/10).
- Executor: persistent Python loop, 600s rebalance cadence, 60s heartbeat, single-instance lock,
  kill-switch file, live-reloadable config (data/cashcarry_config.json — params changeable without
  restart, built after a committed fix ran inert for 2 days because the process was never respawned).
- Backtest Sharpe ~2.1-2.6 (full history, net of ADV-tiered costs); forward shadow at day 15/90,
  forward Sharpe ~12 (noisy, early — expected to revert), Newey-West forward t-stat 2.53 (naive
  2.45). Realized book ≈ breakeven (+$1) with funding +$58 (~20.8% APR run-rate) and fees ≈ 0/day
  post-churn-fix; historical scars from hedge-drift incidents (documented), not strategy failure.

## 3. Candidate pipeline (all paper, zero capital until validated)

- **Perp long/short multi-sleeve** (momentum + trend + basis + taker-flow; funding sleeves dropped
  to decorrelate from deployed carry): backtest Sharpe ~0.85; forward day 8/90.
- **trend_30d** (directional TS-momentum, top-15 majors, 30d lookback, turnover-banded): passed the
  in-sample gauntlet (Sharpe ~1.4, PBO 0.079, RC p 0.005); forward day 8/90. Excluded from
  combined P&L until validated (own dashboard card + shadow only).
- **Regime-gated trend challenger** (same book, flat unless lagged |BTC 30d| ≥ 10%): built on
  principal instruction over an EV-gate REJECT (p_survive ~7% — regime-filtered trend is a known
  overfit trap); pre-registered champion/challenger, day 3/90; evidence decides.
- Recently tested and killed with the full gauntlet: KAMA-squeeze (TTM squeeze + Kaufman AMA,
  canonical params) — Sharpe 0.16, PBO 0.77; squeeze timing underperformed its own raw-KAMA baseline.

## 4. Validation methodology (the core of the system)

- **In-sample gauntlet, every candidate:** combinatorially purged cross-validation (CPCV),
  deflated Sharpe ratio, White Reality Check / SPA on stationary block bootstrap
  (autocorrelation-preserving; i.i.d. bootstrap explicitly banned), probability of backtest
  overfitting (PBO), expected-value, capacity, cost (ADV-tiered per-name), fragility checks.
- **Forward validation:** frozen-spec shadow with a fixed shadow-start; composition change =
  honest clock reset. No re-tuning to pass, ever.
- **Adaptive promotion windows (statistics corrected 2026-07-12 after the first external
  adversarial review):** fast-track at ≥40 forward days requires (a) NEWEY-WEST corrected forward
  t-stat ≥ its bar (the naive √(d/365) scaling assumed IID returns and inflated significance on
  autocorrelated carry streams), (b) forward ≥ 0.5× backtest, AND (c) ≥1 regime event inside the
  window (aggregate funding-inversion or basis-dislocation day — 40 calm days test a market mood,
  not an edge). Multiplicity: carry is the pre-registered PRIMARY hypothesis (frozen before any
  cohort existed) at the plain 1.65 bar; later candidates carry a Holm step-down correction across
  the active cohort (best of 4 needs ≥2.24). Standard 90 days otherwise; 40-day absolute floor.
- **Pre-registration:** hypotheses declare economics, params, success metric, and kill condition
  before testing. Positive IC alone never promotes (documented lesson: IC can live mid-distribution
  while the tradeable extremes lose).
- Anti-overfitting culture enforced in priors: a fat backtest Sharpe is treated as a red flag
  (a 9.84-Sharpe candidate was correctly killed by DSR).

## 5. Risk framework

- Objective function: maximize E[log wealth] (geometric growth) subject to survival constraints.
- **Shrunk-Kelly continuous sizing (v4, 2026-07-12, replaced the discrete time-ladder):** deployed
  fraction of Kelly = S²/(S²+SE²) (Lo-2002 standard error, pooled shadow+live forward days) — the
  fraction that maximizes E[log wealth] under estimation error. Naive full Kelly on an estimated
  edge is an overbet that compounds slower; the shrink authorizes MORE than the old ½-Kelly start
  wherever evidence is strong (a day-40 fast-track starts ~0.73× Kelly) and rises continuously
  where the old engine capped at 0.5× forever. No rungs; any discrete jump beyond the formula
  requires ≥30 live days.
- **Asymmetric demotion:** same-day drop to 0.25× Kelly on live DD > 2× model expectation OR
  implementation shortfall > 50% of edge OR root-caused persistent decay; second trigger retires
  to shadow. PLUS a live-specific trigger that does not trust the pre-live edge estimate: live
  30-day realized Sharpe < 0.5× forward-shadow Sharpe → 0.25× regardless of execution cleanliness
  (the first 90 live days re-validate the edge estimate itself).
- **Isolated dead-man's switch (Tier-3 never-touch):** an independent process — no LLM, no config
  reads, no shared code — polls combined two-venue equity every minute; 5 consecutive readings
  below 65% of high-water → kill file + reduce-only flatten + spot liquidation + page, latching
  until a human clears it. Survives LLM error, config corruption, and main-executor bugs.
- **Survival rails:** account-wide ruin-flatten at 35% loss; DD-pause (pause new opens, never
  realize losses) at 15%; 35% concentration cap; ruin-probability ≤ 2% caps total leverage
  (endogenous, currently 5.7×; actual leverage floored at 1× until validation confidence > 0).
- **Rail autonomy tiers:** DD-pause self-adjustable within 10–25% on evidence (Tier 1); moderate
  moves default-approve after a 72h human veto window (Tier 2); removing any kill switch or
  ruin-flatten beyond 45% requires explicit human yes forever (Tier 3). No rail proposal permitted
  within 7 days of a drawdown (governance freeze).
- **Black-swan library:** 12 named crisis scenarios (FTX collapse, LUNA depeg, COVID crash, 2021
  deleveraging cascade, funding-inversion quarter, exchange outage mid-hedge, fee doubling,
  prolonged chop, etc.); promoted alphas are sized so no single scenario is fatal.
- CI-enforced stress harness: Monte Carlo path proof that ruin-capped sizing preserves growth
  (+0.226 g) while over-betting destroys it (−0.225 g). Runs on every code change.

## 6. Execution layer

- Maker-first on both legs (LIMIT_MAKER spot / GTX futures) with taker fallback; ~halves fee drag.
- **Hedge reconcile guard** (runs every rebalance): covers orphan futures positions, re-hedges
  missing short legs, buys spot-leg deficits, trims excess shorts hiding inside tracked names.
  Order path: market-first → post-only limit at the near touch on PERCENT_PRICE rejects (thin-book
  orphans were previously stranded forever by market-only covers; incident-driven fix).
- **ADL awareness (2026-07-12 review fix):** if the venue force-closed a short leg (liquidation /
  auto-deleveraging during a squeeze), the reconcile flattens the SPOT leg instead of re-shorting
  into the squeeze that took it, with a 24h re-entry cooldown.
- **Basis-blowout stop (2026-07-12 review fix):** the pair is delta-neutral to price, not to
  basis; a >3% instantaneous perp premium over spot (squeeze/dislocation territory, vs normal
  basis of a few bps) exits the pair and stands down 24h. Never fires in calm markets.
- Two-venue symmetric P&L accounting: realized spot P&L derived from exchange ground truth
  (deduped trade-log basis minus venue futures REALIZED_PNL) rather than a local accumulator —
  built after a one-sided accumulator fabricated a phantom −$394 loss on a ~breakeven book.
- Venue history endpoints paginated past caps (income endpoint truncation silently understated all
  aggregates; incident-driven fix).
- Queued next (top of ROI backlog): per-fill TCA log (decision-price vs fill-price, time-to-fill,
  maker/taker outcome) + funding-deadline-aware maker patience. Target: execution cost < 15% of
  gross funding.
- Deliberately rejected with pre-registered revisit triggers: HFT/latency strategies (structural:
  colocation physics, adverse selection, fee tiers), C++/Rust rewrite (iteration-velocity tax for
  ~0.003% loop-time gain at 600s cadence), event-driven engine (adopt nautilus_trader patterns IF
  a validated intraday edge ever appears).

## 7. Data layer

- All free/keyless: Binance fapi (klines, funding, OI, long/short, taker flow, premium), Binance
  spot (basis), Bybit public WebSocket (liquidations — switched from Binance mainnet WS after
  discovering a silent geo-block that completed handshakes but delivered zero frames for 14 days
  while heartbeats stayed green; fix included a second "time since last real payload" liveness
  signal), public Ethereum JSON-RPC (keyless ERC-20 balanceOf on labelled exchange wallets →
  stablecoin exchange-reserve netflow), Deribit public (DVOL, vol surface), Hyperliquid (cross-venue
  funding, 205 matched perps), alternative.me (Fear&Greed), CoinGecko (dominance).
- Forward archives accruing daily (30d-capped venue endpoints archived to build deep history):
  OI/long-short (~day 15/40), stablecoin flows, liquidations, Deribit surface, market breadth.
- data_registry.json: 20 sources tiered (free/keyed/view-only/paid), EV-gated integration policy
  ("never integrate a source because it exists"), quarterly re-verification.
- Paid data policy: one-off pulls only when live capital justifies (~$600 Tardis derivatives tick
  history + ~$800 one-month on-chain history subscription-then-cancel); a vendor-agnostic CSV
  loader + full-gauntlet backtest harness is pre-built and smoke-tested so the subscription clock
  only runs during download.

## 8. Research & discovery engine

- **Alpha Economics EV gate** (libs/research/alpha_economics.py): every idea scored BEFORE effort —
  EV = P(survive)·ΔSharpe·breadth^0.5·capacity^0.25·orthogonality ÷ (effort·maintenance), where
  P(survive) starts at the desk's honest base rate (15%) and is multiplied by meta-learned priors
  from its own graveyard (funding_family ×2.0; price_only ×0.30; narrow_breadth ×0.25;
  crowded_known ×0.35; no_economic_mechanism = hard kill). Only QUEUE verdicts get researched.
  Track record: pre-scored the KAMA-squeeze at 1.6% survival; gauntlet confirmed (PBO 0.77).
- **Hypothesis quota:** ≥3 new hypotheses EV-scored per daily cycle (zero generation = defect;
  zero survivors = normal). Six generator sources rotated: alpha-map missing branches, nightly
  arXiv q-fin feed, reverse-engineering known desk styles, component recombination, maturing data
  clocks (each new dataset owes ≥2 pre-registered hypotheses on arrival), and the autodiscovery
  factory (12 signal generators + orchestrator + crypto adapter — the adapter was built
  autonomously by the daily cycle itself on 2026-07-11).
- **Nightly literature ingestion:** arXiv q-fin (TR/PM/ST) auto-fetched, deduped, appended to a
  vault inbox; the cycle triages each paper (economic intuition → orthogonality → EV score →
  distill into topic note or one-line graveyard rejection), then clears the inbox.
- **Graveyard / do_not_repeat:** 15+ falsified hypotheses with verdicts, failure-taxonomy tags
  (crowded / no_breadth / overfit / no_economics / wrong_sign / regime_artifact / costs_killed),
  and lessons; identical hypotheses are never re-tested; patterns feed back into EV priors.

## 9. Governance engines (all persistent code/JSON, not prose)

- **Root Cause Engine** (daily): classifies every P&L deviation into expected_variance /
  execution_issue / infrastructure_bug / model_assumption_violation / alpha_decay / regime_shift
  with a confidence distribution. Hard rule: NEVER modify strategy from realized PnL alone;
  expected variance → do nothing; only evidenced execution/infra (conf ≥ 0.5) or statistically
  persistent root-caused decay may trigger autonomous change. Tracks expected-vs-actual (tracking
  error) and the implementation-shortfall chain (expected bps → after-fees → realized).
- **Growth Audit** (daily, the anti-conservatism engine): flags every gap between
  evidence-AUTHORIZED size and DEPLOYED size (capital utilization, leverage vs growth-optimal,
  live-path readiness, promotion latency). Each gap must be justified by exactly one of
  {evidence-not-yet / survival constraint / one-time human act}; anything else is a CONSERVATISM
  DEFECT, treated with the urgency of a risk breach: closed same-cycle or ledger-justified.
  Doctrine: at equal EV, prefer briefly-too-aggressive-within-ruin-caps over persistently-too-small.
- **Decision Ledger** (17 entries): every significant decision pre-logged with hypothesis,
  expected benefit/cost, confidence, assumptions, success metric, and reversal condition; matured
  entries scored monthly (correct/wrong/unclear + which assumption failed) so decision QUALITY
  compounds. Governance freeze: no policy modified immediately after losses.
- **Executive structure:** six mandates (CRO/CIO/Risk/CTO/CDO/CEO) worn as hats by one daily loop
  (separate agents rejected under the rule that a new executive must beat assigning the duty to an
  existing one). KPIs per hat in executive_kpis.json, honest measurements only.
- **Tier-convergence scorecard:** per-dimension gap analysis vs Tier-1/2 firms with named
  aspirational references (RenTec = signal breadth; Citadel/Millennium = risk/allocation;
  Jane Street = execution; AQR/AHL = research hygiene) AND crypto-native mirrors
  (Wintermute/GSR/QCP; growth-path: Folkvang/Tyr/early-Alameda) AND anti-benchmarks (Alameda '22,
  3AC — monthly question: "which of their fatal habits could be creeping into us?"). Structural
  gaps (latency, headcount, $B capital) explicitly marked never-chase.
- **OSS engineering benchmark** (monthly): vs nautilus_trader, qlib, hummingbot, freqtrade —
  adopt patterns that clear the EV gate, never wholesale migration; standing verdict documented.
- **External adversarial review (quarterly, standing since 2026-07-12):** the dossier you are
  reading is regenerated and sent to ≥2 independent frontier models; every finding is triaged
  through the EV gate and its verdict logged. Complemented monthly by an internal fresh-context
  red-team (artifacts only, no design rationale: enumerate and attack every statistical
  assumption, ask of each guard "what venue event makes this do the wrong thing," write the
  desk's post-mortem dated 12 months ahead).
- **EV-gate audit ledger:** every EV verdict is logged at decision time and scored when evidence
  lands (QUEUE→falsified = false positive; override→validated = false negative); prior
  multipliers recalibrate only at n≥50 scored verdicts.
- **Never-certify-completeness rule (honesty mandate):** "is everything maxed?" is never answered
  "yes" — only "all KNOWN improvements are implemented AND undiscovered-defect risk remains,
  hunted on schedule." Completeness assurances to the principal are logged as scored forecasts.
- **Deferral discipline:** ending a cycle by recommending (rather than doing) its own top action
  requires naming survival-risk or unresolved uncertainty; "long session" is never sufficient.
  Risk-classify the EDIT, not the FILE.
- **6-point cycle contract** at the top of the CRO prompt (read-first, growth audit, quota,
  implement-don't-defer, never-touch list, record everything); every cycle report must explicitly
  confirm each point — compliance is auditable, drift is visible same-day.

## 10. Self-improvement & memory

- Daily CRO cycle (scheduled 08:01, Opus 4.8, maximum reasoning): loads all state cold, runs CI
  gate, refreshes pipelines, identifies the single largest bottleneck, implements the single
  highest-ROI action, recurses until no positive-EV task remains. Demonstrated autonomy: built the
  autodiscovery crypto adapter unprompted the first morning it topped the queue.
- Monthly governance (~every 30 cycles): growth attribution, rolling post-mortems (Sharpe/
  shortfall/turnover/tracking error), kill committee (actively tries to destroy the portfolio),
  complexity/entropy budget (delete 3-5% of code earning nothing; 227 orphaned legacy modules are
  scheduled for the first purge), decision-ledger scoring, self-improving governance (policies
  themselves graded and strengthened/retired), memory compression.
- **Memory architecture (tiered, constant-size working set):** knowledge lives in Markdown
  (institutional_knowledge.md — operational lessons; graveyard.md; playbooks/; research/ topic
  notes; monthly_reviews/), measurable state in JSON (ledger, KPIs, registries, policies), raw
  data in Parquet. Monthly distillation: aged lessons compress into numeric priors and one-line
  rules; raw detail archives to a grep-able docs/archive/ (never deleted, never read by default).
  Rationale: attention dilution is the one aging disease of an LLM-run org — uncompressed memory
  is lossy at read time (empirically observed: a documented lesson was missed in a long file);
  compression is lossy at write time but curated and reversible. Vault is Obsidian-compatible
  (HOME.md index, wikilinks, auto-generated daily desk_digest.md).
- Calibration: Brier-scored forecast records (currently 0.072, bias −0.198 = under-confident).

## 11. Infrastructure & operations

- Single Windows laptop (acknowledged single point of failure; ~$5/mo Linux VPS migration
  scheduled before 2026-08-05, ahead of any live capital).
- Self-healing watchdog (Task Scheduler, every 3 min): TCP-probes the dashboard, checks executor/
  listener/tunnel heartbeats, respawns anything stale, refreshes leverage + combined feeds +
  health + alerts, spawns the daily research chain once per 24h. Idempotent; single-instance
  locks prevent double-booking.
- CI gate (ruff lint + pytest (42 targeted tests on survival paths: hedge reconcile invariants,
  allocation caps, risk controls, EV gate, root-cause, NW/Holm statistics, Kelly shrinkage,
  dead-man trigger logic) + Monte Carlo stress harness) — mandatory before and after every
  change; the test suite has caught real money bugs (water-fill cap leak).
- Rollback guard: pre-change checkpoints of the full code surface (last 20 retained), evaluate/
  revert commands; triggers on CI regression, stale heartbeats, new errors, hedge drift — never
  on PnL (market-confounded).
- **Pager** (ntfy.sh push to principal's phone, deduped 6h): fires only on critical conditions —
  dead heartbeat >30min, stuck kill-switch >1h, high-confidence root-cause finding, unresolved
  conservatism defect, data-health alerts.
- Dashboards: local + ngrok public URL + Netlify mirror; cards for combined book, real book (pure
  carry, never blended with paper), each candidate, 3× levered SIMULATION (clearly labelled,
  teaches leverage-amplifies-noise), risk, leverage, data clocks, health.
- Known environment quirks documented (venv stub→worker PID pairing on this machine; S4U session
  kill boundaries; Binance mainnet WS geo-block).

## 12. Live deployment policy (armed, awaiting one-time human setup)

- Prerequisites (human, once): live exchange account, TRADE-ONLY withdrawal-disabled API keys,
  deposit of principal's choosing, explicit "connect it." VPS PRECONDITION (2026-07-12): the live
  connector is enabled only after the VPS migration has run stable ≥7 days — real capital never
  depends on a laptop staying open.
- Then fully autonomous: any sleeve completing its adaptive validation window with all gates
  (corrected forward significance, testnet execution stability where executable, positive marginal
  contribution, correlation utility, black-swan-survivable sizing, Kelly authorization)
  auto-deploys at its shrunk-Kelly fraction and ramps continuously with pooled evidence. No
  per-sleeve approvals.
- Carry-decay contingency: if the deployed carry's 30-day forward Sharpe drops below 1.0 before
  any candidate validates, live size drops to 0.25× Kelly and the research budget concentrates on
  the funding-decay predictor and data-clock hypotheses — the desk never rides a decaying lone
  edge at full size while waiting for successors.
- Testnet slots recycle: promotion-to-live or retirement frees the account for the next candidate
  the same cycle.
- Forever-human hard stops: deposits/withdrawals/transfers, API key creation/rotation, financial
  obligations, Tier-3 rail changes. The futures connector is hard-pinned to testnet until the
  human setup exists — nothing can touch real money before it.

## 13. Current state (2026-07-11)

- Carry forward shadow: day 15/90; NW forward t-stat 2.53 (naive 2.45), forward Sharpe 12.11 vs
  backtest 2.14; regime events observed in-window: 0 (fast-track needs ≥1 by day 40 — the desk
  accepts that a calm window honestly pushes promotion to the 90-day standard track).
- Realized book ≈ breakeven (+$1 net) with funding +$58 (~20.8% APR run-rate), 226 closed
  trades, 53% winrate, ~zero daily fees post-churn-fix; historical drift scars documented.
- Candidates: perp L/S day 8/90 (−$17), trend day 8/90 (−$45), regime challenger day 3/90.
  Data clocks: OI/LS ~16/40, stablecoin flows accruing, liquidations (Bybit) accruing.
- Dead-man switch live: high-water $15.7k, fire line ~$10.2k, 0 breaches.
- Growth audit: 0 conservatism defects. CI: all green (42 tests). Queued backlog, ROI order:
  live-connector pre-build (behind interlocks), funding-decay predictor (pre-registered, the one
  alpha idea from review round 1 that survived EV triage), per-fill TCA.
- First-inversion probation: ADOPTED (principal initially declined, reversed same day after
  seeing the quantified cost ~1-1.5% of NAV once). Live carry runs at half its authorized
  fraction until one funding-inversion episode is survived (episode DD ≤ 2× model) or 60 live
  days pass — mechanical (`kelly_shrink.first_inversion_cap`, unit-tested), self-expiring.
- Honest composite self-assessment on record: "world-class machine, elite process, unranked
  fighter" — 9/10 as a solo systematic desk with the missing point held by the absence of live
  track record, which no engineering can mint.

## 14. Known limitations (honest — reviewers should probe these)

1. **Zero live track record.** Everything statistical is testnet/paper. Testnet fills are
   optimistic; real-market slippage/fees are unproven for this exact stack.
2. **Single edge dependence.** Funding carry is the only near-validated edge; funding compresses
   secularly as the trade crowds. Candidates are unproven and directional ones may be bull-flattered.
3. **Single machine** until the VPS migration; the desk dies with the laptop today.
4. **AI compliance is probabilistic — decomposed by severity (2026-07-12), because the aggregate
   rate hides what matters:** money-touching / rail actions: 0 violations to date, and now backed
   by the isolated dead-man switch that survives LLM error entirely; process-mandate compliance
   (mandatory reads, implement-don't-defer): ~95%, with the three documented lapses all in this
   class (skipped reading once; venv-stub misdiagnosis; one deferral); informational/reporting:
   noisy but self-correcting at the next cycle. Mitigations: cycle contract with attestation,
   pager, audits, deferral discipline — the residual risk is concentrated in the class that wastes
   hours, not the class that loses money.
5. **Engineering depth is deliberately thin** (42 tests vs thousands in elite systems; Python
   scripts; REST polling). Judged sufficient at 600s cadence; a genuine gap at higher frequency.
6. **Counterparty concentration:** effectively one venue (Binance). An FTX-class failure is fatal
   to deployed capital regardless of strategy correctness; policy mitigations are sizing and
   withdrawal-disabled keys, not diversification (yet).
7. **Small-sample governance:** most policies are days old; the self-improvement loops have run
   once or twice, not through a full market cycle. Scar tissue is thin by construction.
8. **Prompt/policy surface has grown large** (~300 lines); attention dilution is a live risk;
   monthly compression is scheduled but not yet exercised.
9. **Principal key-person risk — the largest structural risk (added 2026-07-12 on external-review
   consensus).** One 18-year-old principal owns every forever-human action (deposits, keys, Tier-3
   approvals) and the budget. Illness, exams, loss of interest, or an unpaid API bill degrades the
   desk to hold-and-harvest with rails active — survivable but frozen. No engineering fixes this.
10. **AI key-person risk.** The CRO is one vendor's model. API changes, price increases, or
    extended outages break the research loop (not the executors or rails, which run without it).
    Documented fallback: rails + watchdog + pager keep running; no new deployments until restored.

## 15. Suggested review questions for external AIs

These target the ROUND-1 FIXES themselves — the highest-value review now is auditing the repairs:

1. **NW t-stat implementation:** Bartlett-weighted autocorrelation factor over min(10, n/5) lags,
   clamped to [1, 5], computed on nonzero daily forward returns, effective-N = N/factor. Any
   residual inflation, mis-specification, or perverse case? Is the ≥1 clamp (never award more
   significance than IID) the right one-sided conservatism?
2. **Multiplicity design:** Holm step-down across the concurrently-monitored candidate cohort,
   with the deployed carry EXEMPT as the pre-registered primary hypothesis (its shadow froze
   before any cohort existed). Is the primary-endpoint exemption legitimate here, and is
   "concurrently monitored" the right family definition?
3. **Regime-event gate:** fast-track requires ≥1 in-window event, where inversion-day = even the
   top-20 funding names average ≤0, and basis-dislocation-day = |panel-mean basis| > 3σ of its
   backtest distribution. Currently 0 events in 15 calm forward days. Too strict, too loose, or
   the wrong events entirely for certifying a carry edge?
4. **Shrunk-Kelly:** fraction = S²/(S²+SE²) with Lo-2002 SE, pooled over shadow+live forward
   days. Should the SE itself be autocorrelation-adjusted? Is pooling testnet-shadow days with
   live days into one evidence count legitimate, or should live days carry more weight?
5. **First-inversion probation (now ADOPTED):** live carry at 0.5× authorized fraction until one
   funding-inversion episode is survived (episode = ≥1 day of negative aggregate realized
   funding; survived = episode DD ≤ 2× model expectation) or 60 live days, whichever first.
   Audit the design: is 0.5× the right cap level, 60 days the right expiry, and is the
   episode/survival definition gameable or too weak (e.g., a one-day shallow inversion
   "certifying" the book for a six-week deep one)?
6. **Dead-man switch:** independent process, equity = futures margin + spot value of assets with
   a live futures short + USDT delta-from-first-poll-baseline; fires on 5 consecutive minutes
   below 65% of high-water; latches until a human clears state. Construct false-fire and
   missed-fire scenarios (e.g., composition changes, baseline drift, venue read asymmetries).
7. **ADL heuristic:** a missing short leg PLUS any venue force-order on that symbol within 2h →
   sell the spot leg + 24h cooldown; otherwise re-short the deficit. What does this get wrong
   (partial ADL, force order on an unrelated position of the same symbol, window staleness)?
8. **Root-cause "unknown_novel":** when no failure bucket reaches 0.35 confidence, the verdict is
   pause-and-page instead of best-guess classification. Right threshold? Right response?
9. **The round-2 meta-question:** where does the largest remaining statistical or operational
   leak live NOW — what did round 1 miss entirely, and did any of the round-1 fixes introduce a
   new failure mode of its own?
10. Is any part of this document internally inconsistent with any other part, and does any fix
    contradict the desk's stated objective (maximize E[log wealth] subject to survival)?

---

*Document generated 2026-07-12 (round-2 revision) by the desk's AI. All numbers verified against
live feeds at
generation time. The graveyard, ledger, and knowledge base referenced herein are real files in
the repository and can be provided for deeper audit.*
