# RD-Agent Deep Audit — what to take for hypothesis generation & alpha discovery

Deep audit of microsoft/RD-Agent (LLM autonomous evolving R&D agents; top of MLE-Bench; the
R&D-Agent-Quant variant reports ~2× ARR with ~70% fewer factors) against this desk's discovery
machinery. Goal: take the genuinely-better methods, skip what we already own, and refuse what is
negative-EV or violates the constitution. Executed 2026-07-23.

## RD-Agent's method (the concrete loop)

Propose a **hypothesis** (idea + rationale + expected effect) → design an **experiment** → implement
it as code → execute to get **feedback** (metric vs the current SOTA) → **update the trace + SOTA**
and condition the next proposal on it. Its distinctive edge over a naive generator is that each
proposal is **trace-conditioned**: it builds on the best-so-far and does not re-propose ideas close
to ones already tried and failed. Factor mining and model evolution are separate but co-optimized,
and every iteration is scored against a **standard benchmark**.

## Dimension-by-dimension vs this desk

| RD-Agent capability | This desk's equivalent | Status |
|---|---|---|
| Hypothesis representation (idea + rationale + expected effect) | `alpha_factory/models.Hypothesis` (statement, features, expected_edge, rationale) | **Owned** (orphaned) |
| Durable experiment trace + structured failure causes | `alpha_factory/research_memory` (append-only, failure_cause/lessons/metrics) + live `negative_knowledge.md`, `graveyard.md`, `decision_ledger` | **Owned** (memory orphaned; flat-JSON trace LIVE) |
| Feedback → next proposal conditioning (category-level) | `hypothesis_engine` (priors from `research_memory.success_rate`) | **Owned** (orphaned) |
| Expected-vs-realized calibration | `self_improvement/forecast_calibration` (Brier, applied as shrinkage) | **Owned — LIVE** |
| SOTA / champion-relative proposal | `signal_engine/champion_challenger` | **Owned** (orphaned) |
| Post-compute redundancy / duplication check | `alpha_factory/strategy_similarity_engine` (returns/factor/feature space) | **Owned** (orphaned) |
| Benchmark scoring of each candidate | `validation/reality_check` (SPA/RC) + new `validation/baselines` (naive-baseline scorecard) | **Owned** (RC orphaned; baselines added this session) |
| Concept/idea evolution + ROI ranking | `alpha_factory/{concept_evolution_engine,idea_ranking_engine,research_roi_engine}` | **Owned** (orphaned) |
| **Pre-compute** trace-conditioning (screen a candidate vs the graveyard BEFORE spending compute) | — none (similarity engine needs a returns series; hypothesis_engine uses only category priors) | **GAP → CLOSED this session** |

## The one genuine gap, and why it's the right one to close

Almost the entire RD-Agent loop is already built here (mostly orphaned by the documented decision
that flat-JSON state is correct at 2 sleeves). The single method RD-Agent has that this desk lacked
in a usable form is **pre-compute trace-conditioning**: screening a proposed hypothesis against the
record of already-failed ideas *before* paying to backtest it. Everything the desk owns either
de-dupes after compute (`strategy_similarity_engine` needs returns) or conditions only at the
category level (`hypothesis_engine`).

This is precisely the desk's stated objection to automated generation (`GAP_ANALYSIS.md`: "a
generator pointed at the SAME data would mostly re-discover already-graveyarded failure modes at real
compute cost"). So closing it is not "more generation" — it is the guard that makes any generation,
*and the live frontier-miner/prospector digging*, spend compute only on genuinely novel hypotheses.

**Implemented:** `libs/alpha_factory/hypothesis_novelty.py` — `hypothesis_novelty(statement,
features, priors, redundant_threshold)` returns a novelty score, the nearest prior failure (with its
lesson), and a redundancy flag. Deterministic set/token similarity (features dominate, since they
encode the mechanism); advisory, never a hard block; no AI-oracle. ~90 lines + 7 tests. It prevents
redundant backtests and trials-ledger charges — it replaces/prevents more than it adds.

**How to use it live (no new generator needed):** in the frontier-miner / prospector digging path,
before queuing a candidate for the gauntlet, build `PriorIdea`s from the graveyard (failed
`research_memory` rows, or the flat `graveyard.md`) and call `hypothesis_novelty`; deprioritize
`is_redundant` candidates and route compute to the high-novelty ones — especially the new-data-axis
hypotheses that are the actual binding constraint.

## What this audit deliberately did NOT do (and why)

- **Did not wire a large LLM hypothesis generator.** More generation compute over the same
  price/derivative data is negative-EV by the desk's own analysis (10/11 mechanisms graveyarded;
  meta-learner gates `price_only` at 0.30). The novelty gate makes generation cheaper; it does not
  argue for more of it.
- **Did not resurrect the orphaned `alpha_factory`/`signal_engine` engines.** They are deferred by a
  documented decision (flat JSON is correct until >5–10 validated survivors); adding orphaned code
  violates the complexity budget.
- **Did not adopt RD-Agent's AI-as-oracle trade selection.** The constitution allows AI as engineer
  and adversary, never as the trade-deciding oracle — the novelty gate is deterministic, not a model
  making calls.

## Verdict

RD-Agent is the right thing to study, and this desk has independently built ~90% of its loop. The
real, downside-free win was the one missing piece — pre-compute novelty screening — which is also
the exact guard that neutralizes the desk's standing objection to automated discovery. It is now
owned and tested. The binding constraint on alpha discovery remains new data axes and forward
validation time, not generation cleverness — and this gate spends the scarce compute where it counts.
