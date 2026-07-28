# SUBSYSTEM TRIAGE — every proposed component, 2026-07-27

Principal: *"queue ones blocked, other system will build; do the buildable now; don't skip any — build now, queue, or reject completely."*

Verdicts are **BUILT** (exists, verified), **BUILD** (ready, unblocked, spec below), **QUEUE**
(blocked — blocker named), **REJECT** (with reason). No item is omitted.

---

## BUILT — exists and verified today

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

---

## BUILD — unblocked, specified, next session (~1–2h total)

| # | Component | Spec | Why now |
|---|---|---|---|
| 17 | **Information Advantage / Data Moat Score** | `uniqueness × replication_difficulty × persistence ÷ cost`, scored per dataset in `feature_library.py`. Moat=high, funding=low, on-chain/attention=low. | Stops research spend on crowded data. ~40 lines. |
| 18 | **Failure-Pattern Filter** | Mine 249 closes + cost model for characteristics predicting losses (`high funding × low liquidity × micro-cap`). Extends the existing bleed denylist. | Would have flagged COOKIEUSDT pre-emptively. Data exists. |
| 19 | **Research Throughput / Alpha Factory Metrics / Quality Score** | Read `experiment_registry.jsonl`: experiments/week, time-to-verdict, kill rate, survival, **Validated Alpha Discovery Rate** (north star). | One reader over existing data. Currently 0.00 and unmeasured over time. |
| 20 | **Alpha Blind-Spot / Coverage Map** | Coverage % per mechanism (already computed) × information-advantage score → "low coverage, high value" ranking. | Directs the next construction test. |
| 21 | **Alpha Transfer Pipeline** | Formalise `discovery → OOS → paper → small capital → scale → monitor → replace` as explicit gate states on each alpha record. | A discovery that never reaches capital has zero value; currently undefined. |

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
| 39 | Information Gain Engine **(exists but DEAD)** | `info_bits` constant 0.2345 across all 810 rows — repair the writer first |
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
| 67 | Intelligent Data Acquisition scoring |

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
4. Sept 1 forward verdict — the first chance for the north star to leave 0.00
