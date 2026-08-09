# SURVIVOR-YIELD + E[log W] EXPANSION — REPO AUDIT BEFORE BUILDING

Mandate §40: *"AUDIT THE CURRENT REPO FIRST. For every section classify ALREADY_BUILT / PARTIAL /
UNWIRED / BROKEN / UNDERUTILISED / GENUINELY_NEW. DO NOT rebuild duplicates."* Principal, same day:
*"I would not let this become another 40-module construction exercise."*

Audited 2026-08-09 against 502 source files. **Five modules built out of forty sections.** The rest
were already covered, and the audit below is the evidence for not building them — it exists so the
next session does not re-derive the same conclusion at the same cost.

## Built (GENUINELY_NEW after audit)

| § | Capability | Why nothing existing covered it |
|---|---|---|
| 1, 2 | `libs/portfolio/alpha_reserve_bank.py` | `champion_challenger.py` compares a PAIR on Sharpe/DD/PF; `capital_competition.py` re-derives allocation from forward evidence; `alpha_state.py` owns the evidence ladder; `strategy_pool.py` holds a flat bench. **None answers "if 50% died today, how much is replaceable without lowering the bar"** — there was no reserve ratio, no independence-deflated bench count, no replacement latency, and no switch test that charges switching cost, model uncertainty and lost option value. |
| 3 | `libs/portfolio/portfolio_monte_carlo.py` | `validation/bootstrap.py` has moving-block and stationary-block resampling but is SINGLE SERIES. `discovery/monte_carlo_survival.py` is single-strategy. `strategy_pool.sizing_drawdown` reshuffles per-strategy — **the exact defect §3 names**. Nothing drew one block of time and applied it across the book. |
| 8 | `libs/research/market_breadth.py` | `capacity_allocation.py` allocates within a known universe; `regime_diversification.py` scores regime spread; `data/universe.py` lists instruments. **None prices the marginal E[log W] of a NEW place to express an existing mechanism**, and none states the asymmetry that a parameter search adds zero independent occurrences. |
| 33–36, 21 | `libs/research/practitioner_corpus.py` | `video_intelligence.py` tracks CHANNELS. A practitioner's corpus spans a dozen channels plus podcasts, papers, filings and competition records, and **a channel can be exhausted while the person has an untouched decade**. Also new: the twelve extraction axes with process split from rules, and disagreement mining. |
| Alex Carter delta 1–2 | `libs/ops/agent_authority.py` | No capability ladder and no blast-radius budget existed anywhere. `execution/canary.py` and `execution/ramp_gate.py` gate ORDERS; nothing gated COMPONENTS. |

## Not built — ALREADY_BUILT or answering the same question

| § | Verdict | Where it already lives |
|---|---|---|
| 4 incubation distribution match | ALREADY_BUILT | `libs/research/anytime_valid.py` (e-processes), `validation/per_candidate.py`, `validation/reality_check.py` |
| 6 independent evidence confluence | ALREADY_BUILT | `libs/validation/effective_sample.py` (six deflators), `alpha_factory/independence.py`, `research/cohort_independence.py` |
| 13–15 float/turnover, exhaustion | PARTIAL, adjacent | `research/liquidation_mechanism.py`, `research/moat_microstructure.py`. Genuinely new work here needs DATA this clone cannot reach, not code. |
| 16–18 forced flow, equilibrium shift | ALREADY_BUILT | `research/liquidation_mechanism.py` classifies FORCED vs SUPPLY; the new `drawdown_rebound.py` (committed 51fa21a) classifies seven decline mechanisms |
| 22–23 chaser saturation, trend maturity | PARTIAL | `research/crowding_intelligence.py`, and the new `crowding_hazard.py` |
| 28 factor residualization | ALREADY_BUILT | `research/ic.py`, `alpha_factory/strategy_similarity_engine.py`, `research/collapse_detector.py` |
| 29 carry as state | ALREADY_BUILT | `research/cashcarry.py`, `execution/carry_accounting.py`, `research/funding_clock.py` |
| 30 weak-alpha aggregation | ALREADY_BUILT | `alpha_factory/combination_engine.py`, `research/fusion_search.py` |
| 31 common-unwind stress | **NOW COVERED** | by `portfolio_monte_carlo.stress_coactivation` + `dependence_blindness` |
| 37 cross-creator consensus | **NOW COVERED** | `practitioner_corpus.effective_independent_sources` |
| 5, 32 capital/collateral occupancy | PARTIAL — **honest residual, NOT built** | `strategy_pool.exposure_efficiency` measures return per unit time-in-market, which is the same idea at strategy level. CAPITAL_HOURS / MARGIN_HOURS / ELOG_PER_COLLATERAL_UNIT are **not built** and need a live book to mean anything. `portfolio_monte_carlo` now reports concurrent margin, which is the half that can be measured without one. |
| 7 right-tail preservation auditor | **NOT BUILT — ranked residual** | Nothing measures P&L from the top 1% of trades or what a trailing exit costs. Needs a trade ledger; this clone has none. Genuinely valuable and genuinely blocked. |
| 9–12, 19–20, 24–27 | NOT BUILT | Feature engineering that needs bars and book data. `mechanism_ontology.py` already refuses candidates without a falsifier, which is the gate these would enter through. |
| 38 translation compiler | ALREADY_BUILT | `autodiscovery/crypto_adapter.py` |
| 39 survivor yield | ALREADY_BUILT | `research/mine_conversion.py`, `alpha_factory/research_roi_engine.py` |

## The three the principal ranked, and where they stand

1. **ALPHA_RESERVE_BANK + incumbent/challenger** — built, tested, wired, VERIFIED_COMPLETE. Reports UNMEASURED because there is no live book. **The real finding is GAP row 107:** `near_survivor.py` has banked near-misses and nothing has ever been promoted to SHADOW_CHALLENGER, so the reserve ratio on the day a live book exists would be 0.00.
2. **DEPENDENCE_PRESERVING_PORTFOLIO_MONTE_CARLO** — built, tested, wired, VERIFIED_COMPLETE. `dependence_blindness` reads **2.93x on a constructed clone book and ~1.0 on an independent one**, so the discriminator works in both directions. Its value on the REAL book is UNMEASURED until `data/strategy_paths.json` exists.
3. **Parker's breadth** — built as `market_breadth.py`. The asymmetry is now stated in code: a parameter search adds zero independent occurrences and pays full multiplicity; a new market adds new draws. **Depth remains the default until candidate expressions are recorded**, which is exactly when depth is least likely to be right.

## What this audit refuses to claim

This is a repository audit, not a measurement of the desk. Every "ALREADY_BUILT" above means *a
module exists that answers this question* — it does **not** mean the capability has ever produced a
number on real data. `docs/research/COMPLETION_LEDGER.json` is the artifact that tracks that
distinction, and it currently reads 26/82 VERIFIED_COMPLETE (32%). The gap between "built" here and
"verified" there is the honest state.
