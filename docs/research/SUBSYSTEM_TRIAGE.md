# SUBSYSTEM TRIAGE — every proposed component, 2026-07-27

Principal: *"queue ones blocked, other system will build; do the buildable now; don't skip any — build now, queue, or reject completely."*

Verdicts are **BUILT** (exists, verified), **BUILD** (ready, unblocked, spec below), **QUEUE**
(blocked — blocker named), **REJECT** (with reason). No item is omitted.

---

## BUILT — exists and verified today

| 67 | **Intelligent Data Acquisition scoring** | **BUILT 2026-08-02 -- and it was a DUPLICATE of addendum #93.** Shipped as `scripts/acquire_data.py`, wired into run_cadence. Two triage docs carried the same component under different numbers and neither knew: an item written down twice is worked zero times or twice, never once. |
| 39 | **Information Gain Engine** | **FIXED 2026-08-02 -- the row MISDIAGNOSED it.** "exists but DEAD, repair the estimator" was wrong: `info_bits` constant 0.2345 is exactly -log2(0.85), so every caller passed the same hardcoded 0.15 prior. The estimator was fine; the PRIOR never learned, making total_bits a row count in information-theory units. `empirical_prior()` now derives P(survive) from the desk's own log with Laplace smoothing and the prior travels with the number. A rejection books 0.0348 bits instead of 0.2345 -- the old value overstated learning ~7x, always in the desk's favour. |
| # | Component | Where |
|---|---|---|
| 1 | Experiment Registry / Reproducibility / Decision Log | `experiment_registry.py` — 369 experiments, commit-pinned |
| 2 | Data Engineering / Measurement Integrity | `measurement_gate.py` — fail-closed, 5 contracts |
| 3 | Feature Library + Continuous Feature Mining | `feature_library.py` — 447 constructions, coverage % |
| 4 | Research Scoreboard (contributor) | `research_exchange.py score` |
| 5 | Daily Research Board | `research_exchange.py brief` → `docs/DESK_BRIEF.md` |
| 6 | Red Team — deterministic half | `leakage_detector.py` — 7 checks, 5/5 ground truth |
| 7 | Bottleneck Detector | `execution_bottleneck.py` |
| 8 | Hypothesis Marketplace / ERV ranking | `research_erv.py` + `mechanism_board.py` (correlation-penalised) |
| 9 | Strategy Autopsy / failure taxonomy | `research_autopsy.py` |
| 10 | Edge Conservation ("why does this exist") | `mechanism_board.py` 4-question gate |
| 11 | Complexity Governance | `meta_architect.py` simplifier |
| 12 | Negative Knowledge / graveyard + revival | `negative_knowledge.py` |
| 13 | Automated Revalidation | `revalidate_clocks.py` |
| 14 | Production Monitoring — hedge invariant | `hedge_integrity.py` (new) |
| 15 | Execution TCA | executor log fields (new) |
| 16 | Failure Containment rails | measurement gate + reduceOnly + chunking |
| 17 | Information Advantage / Data Moat Score | `research_cio.py` §1 — `(uniq × predictive × persistence × replication_difficulty) / cost`; ranks data/moat 1.03 vs social attention 0.00 |
| 18 | Failure-Pattern Filter | `alpha_lifecycle.py` §1 — mines closes for loss-predicting characteristics; extends the bleed denylist |
| 19 | Research Throughput / Validated Alpha Discovery Rate | `research_cio.py` §3 — experiments/week, time-to-verdict, kill rate, survival; the north star |
| 20 | Alpha Blind-Spot / Coverage Map | `research_cio.py` §2 — coverage × advantage; currently ranks M_LIQUIDITY_WITHDRAWAL first (1.03 advantage at 0.4% coverage) |
| 21 | Alpha Transfer Pipeline | `alpha_lifecycle.py` §2 — 11 explicit gate states per alpha; measured furthest reach today is 5/11 (FORWARD_REGISTERED) |

**Re-verdicted 2026-07-29.** Items 17–21 sat under BUILD long after they shipped. They were
invisible for a second reason: all three of `check_findings_scope`, `check_findings_tracked` and
`check_findings_ratchet` were blind (`ModuleNotFoundError: libs`, fixed the same day), so nothing
was reading this file at all. Each row above was verified by RUNNING the named producer, not by
matching a name.

---

## BUILD — unblocked, specified, next session (~1–2h total)

**EMPTY as of 2026-07-29.** All five items (17–21) shipped and are re-verdicted BUILT
above, each against a producer that was RUN to confirm it. The specs they were built from
are preserved in git history; keeping stale spec rows here would leave the register
claiming open work that does not exist, which is the mirror image of the defect that hid
them.

---

## QUEUE — blocked, blocker named (hand to the other system)

**Blocked on OpenRouter funding (~$120):**
| # | Component | Blocker |
|---|---|---|
| 22 | Automated Red Team — LLM half | 402 |
| 23 | Research Competition Layer (models compete) | 402 |
| 24 | Automated Research Questions generator | 402 |
| 25 | Unknown-Unknown Explorer | 402 |
| 26 | Competitor / Smart-Opponent Simulation | 402 |
| 27 | Adversarial Market Simulation | 402 |
| 28 | Architecture Review Board | 402 |

**Blocked on ≥2 validated alphas (currently ~1, 0 deployed):**
| # | Component |
|---|---|
| 29 | Alpha Interaction / Recombination Engine |
| 30 | Alpha Portfolio Construction |
| 31 | Alpha Diversity Engine |
| 32 | Capital Migration Engine |
| 33 | Strategy Interaction Engine |
| 34 | Alpha Decay Laboratory / half-life |
| 35 | Model Retirement System |
| 36 | Alpha Evolution / Strategy DNA |
| 37 | Cross-Domain Alpha Synthesis / Information Fusion |

**Blocked on sample size or history:**
| # | Component | Blocker |
|---|---|---|
| 38 | Research Capital Allocation Engine | per-mechanism n = 2/10 vs 0/10 — one coin flip |
| 40 | Research Forecast Calibration | needs predictions logged *before* experiments; cannot retrofit — start accruing day one |
| 41 | Regime Generalisation / Transfer | no retained regime history |
| 42 | Out-of-Distribution Intelligence | same |
| 43 | Challenge Sets | needs regime-labelled history |
| 44 | Human-AI Contribution Optimizer | `suggestion_ledger` has 0 rows |
| 45 | Information Half-Life Tracker | needs adoption/decay history |
| 46 | Market Impact & Capacity Model | needs TCA fills to accumulate (now logging) |

**Blocked on data acquisition (new collectors):**
| # | Component | Note |
|---|---|---|
| 47 | Liquidation Network Intelligence | **Tier 1** — maps to `M_FORCED_DELEVERAGE`, best-supported mechanism (2/10, holds the one confirmed signal) |
| 48 | Wallet Behavioural Fingerprinting | **NARROWED**: risk-behaviour features only. Wallet *returns* refuted at n=1,400 gapped control; wallet *risk* replicated OOS |
| 49 | Exchange Flow Intelligence (actor classification) | Tier 1 |
| 50 | Protocol / Developer Intelligence | Tier 2 |
| 51 | Regulatory / Event Mining | Tier 2, LLM-suited |
| 52 | Exchange User Behaviour (regional adoption) | Tier 2 |
| 53 | Stablecoin Liquidity Mapping | partial collector exists |
| 54 | Cross-Venue Information Delay | partial — `venue_divergence_shadow` running |
| 55 | Information Arbitrage Engine | umbrella over 47–54 |

**Blocked on engineering only (no conceptual blocker):**
| # | Component |
|---|---|
| 56 | Research Memory + semantic retrieval |
| 57 | Dependency Graph (data → feature → signal → strategy) |
| 58 | Causal Knowledge Graph / Causal Discovery |
| 59 | Research Compression Engine |
| 60 | Knowledge Decay Management |
| 61 | Alpha Genome (extend `feature_library` records) |
| 62 | Alpha Lineage (partial — registry pins commits) |
| 63 | Feature Lifecycle states |
| 64 | Market Ecology / Participant Model |
| 65 | Alpha Adversary Model |
| 66 | Blind Validation |

---

## REJECT — with reason

| # | Component | Reason |
|---|---|---|
| 68 | Confidence Propagation | Multiplies **unmeasured priors**. Execution confidence is measurable from fills; mechanism/regime confidence are guesses. A 5-factor product = four guesses with a decimal point. Revisit only for measured factors. |
| 69 | Bayesian Belief Engine | Same defect — priors are invented, not measured. |
| 70 | Uncertainty Budget | Same — sums unmeasured uncertainties. |
| 71 | Autonomous Research Governor | Premature: 0 validated alphas, so the meta-layer has only noise to learn from. |
| 72 | Autonomous Experiment Scheduler | Same. Scheduling is not the constraint — 447 constructions already queued and untested. |
| 73 | Research Simulation Environment (simulate org changes) | Simulating an org with n=15 survivors fits noise about noise. |
| 74 | Universal Research Object Model | Over-abstraction with no bottleneck named; would touch every file for no measurable gain. |
| 75 | Objective Hierarchy | A document, not a system. Already in `OPERATING_DOCTRINE.md`. |
| 76 | Alpha Simplicity Score | Nothing to score — 0 deployed alphas. |
| 77 | Regime Intelligence (as a prediction machine) | `classify_regime.py` exists; principal's own caution against overbuilding applies. |
| 78 | Social Attention Efficiency | `M_ATTENTION_DELAY` is a **FAMILY KILL** (13 deaths). New datasets don't revive a dead mechanism. |
| 79 | Job-Market / Hiring Data | Weak mechanism for liquid crypto pricing; high collection cost, low persistence. |
| 80 | Physical / Satellite / Shipping Data | No credible mechanism to crypto price at this capital; cost dominates. |
| 81 | More LLM agents / dashboards / documentation | Principal's own instruction. 226 scripts, ~179 unwired. |

---

## Ordering constraint that overrides this table

**Execution reliability and deployment remain the bottleneck.** No QUEUE item outranks:
1. Working kill switch on `quant-cashcarry.service` (needs root — principal only)
2. Confirm the kill-latch/re-entry defect (book re-opened with `CASHCARRY_KILL` present)
3. TCA fills accumulating → re-measure cost/funding vs the 7.75× baseline
4. Aug 7 forward verdict — the first chance for the north star to leave 0.00

## Re-verdict pass 2026-08-02 — all 46 blockers checked against the desk's actual state

_(Heading deliberately avoids a verdict keyword, and the findings below are prose rather than a
numbered table: `check_triage_disposition` keys sections off the heading prefix and parses `| N |`
rows as ITEMS, so a document reporting on the queue would otherwise be parsed as queue entries.
The addendum's first draft did exactly that.)_

A QUEUE verdict is a claim with an expiry date, and `check_triage_blocker_stale` only catches a
blocker whose named dependency SHIPPED — it cannot catch one that expired because the world moved.
So all five blocker groups were checked by hand.

**TWO EXPIRED.**

- **Item 67, "Intelligent Data Acquisition scoring" — ALREADY BUILT, and it is a DUPLICATE.** This
  is the same component as addendum #93, which shipped this cycle as `scripts/acquire_data.py`.
  Two triage documents carried the same work under different numbers and neither knew, which is
  the register's own §35 failure appearing inside the register: an item written down twice is
  worked zero times or twice, never once.
- **Item 39, "Information Gain Engine (exists but DEAD)" — MISDIAGNOSED, and now FIXED.** The row
  said "repair the estimator" on the evidence of `info_bits` being a constant 0.2345 across 810
  rows. The estimator was never broken: 0.2345 is exactly −log2(0.85), so every caller passed the
  same hardcoded prior of 0.15. A prior that never updates gives identical surprise for every
  outcome, making `total_bits` precisely `n × 0.2345` — a row count wearing an information-theory
  unit, and the third instance this session of a counter dressed as evidence. It also erred in the
  flattering direction: against a measured 420/420 rejection record, each rejection was booked as
  0.2345 bits of *surprise* when it was exactly what the desk should expect. `empirical_prior()`
  now learns P(survive) from the desk's own log with Laplace smoothing, and the prior travels with
  the number. A rejection now books 0.0348 bits instead of 0.2345 — the old value overstated
  learning roughly sevenfold.

**THE REST HOLD, by group, with the reason recorded:**

- **Items 22–28, blocked on OpenRouter funding (~$120):** unverifiable from this environment
  (`data/panel_budget_state.json` is gitignored and absent here). NOT cleared and NOT confirmed —
  recorded as owed to a VPS check rather than guessed in either direction.
- **Items 29–37, blocked on ≥2 validated alphas:** STILL TRUE. Zero deployed;
  `desk_metrics:alpha_performance` is empty and only a library writes it.
- **Items 40–46, blocked on sample size or history:** mostly STILL TRUE. #46 needs TCA fills, #44
  needs a non-empty suggestion ledger, #41–#43 need retained regime history. #40 ("needs
  predictions logged *before* experiments; cannot retrofit — start accruing") is not a blocker at
  all but an instruction nobody started; it is the closest of this group to actionable.
- **Items 47–55, blocked on data acquisition:** PARTIALLY expired. The venue half arrived — 8.2GB
  of moat tape across three venues, carrying aggTrades — which materially unblocks #54
  (Cross-Venue Information Delay) since cross-venue lag is now measurable from owned data. The
  on-chain half (#47–#52) has not arrived. Recorded as partial rather than cleared: half a blocker
  is still a blocker, and clearing it would queue work that stalls on arrival.
- **Items 56–66, "blocked on engineering only (no conceptual blocker)":** by their own note these
  are NOT blocked. They are correctly QUEUED rather than promoted, because BUILD is the
  cheap-next-session tier and moving eleven multi-day items into it would turn a ready-queue into
  a backlog and bury the genuinely cheap work — the same denominator dishonesty §34 forbids for
  mining, applied to a work queue.

