# MUTATION BASELINE — the v8 8.2 bar, measured for the first time (gap #53, 2026-07-29)

Four risk-path register rows (#2 connector, #49 client-order-id, #37 reconciler, #19 divergence
guard) cite ">=90% mutants killed" as their gate. **It had never been measured once.** 1199+ tests
demonstrably EXECUTE code; nothing showed they CONSTRAIN it. This is the first measurement.

Runner: `scripts/run_mutation.py` (self-contained AST harness — deterministic, dependency-free,
re-runs identically on the VPS; mutmut 3.6.0 is installed and remains the documented path for a
long whole-tree run). Artifact: `data/mutation_score.json`.

## Result — `libs/validation/stepwise.py` (the pending-ruling gate fix)

| pass | killed | survived | kill rate | vs 90% bar |
|---|---:|---:|---:|---|
| before (13 existing tests) | 22 | 18 | **55.0%** | BELOW |
| after (+12 strength tests) | 36 | 4 | **90.0%** | **PASS** |

Reproduce:

    python scripts/run_mutation.py --target libs/validation/stepwise.py \
        --tests tests/validation/test_stepwise.py tests/validation/test_stepwise_strength.py \
        --budget-s 450

## The finding that mattered more than the number

Reading the 18 survivors split them into two categories that a bare score hides:

**EQUIVALENT MUTANTS — the output genuinely cannot see them.** CSCV PBO is a **rank** statistic,
so any rank-preserving change to the Sharpe formula is unobservable in the verdict. Verified
directly, not assumed: `(n-1) → (n+1)` in the variance denominator and `s**2 → s**3` both leave
every block's candidate ordering identical. No assertion on `candidate_pbo` can ever kill those.
Same for the chunk-size constants at line 128 — chunking is a memory knob that **must not** change
a verdict, so a mutant that changes it is correct-by-construction unkillable (and there is now a
test asserting exactly that invariance).

**REAL GAPS — the suite could see them and never looked.** Every boundary in the input validator
survived: `shape[1] < 2 → <= 2`, `n_splits < 2 → <= 2`, `n_obs < n_splits → <=`. The existing tests
asserted that ILLEGAL inputs raise; nothing asserted that the **smallest legal input is accepted**.
A gate that silently rejects its own boundary case shrinks the campaign it can judge — and this
gate is the one that decides which candidates reach a forward clock. Also unpinned: model
immutability, and the sufficient-statistic Sharpe's actual VALUES (an optimisation of a formula
nothing else checked).

`tests/validation/test_stepwise_strength.py` closes all of those. **Of the 4 mutants still alive,
all 4 are in the equivalent class**, so the kill rate on OBSERVABLE mutants is 100%.

## What this changes about how the desk reads test counts

A kill rate is not a quality score — it is a **map of what the suite pins**. The honest reporting
rule adopted here: every published score names its survivors and classifies each as equivalent (with
the argument) or a real gap (with the test that now kills it). A score quoted without its survivor
list is the same defect as a coverage percentage quoted without its denominator.

## Owed next (targets and their blockers, so nothing is silently dropped)

- `libs/execution/staging.py` (tests/execution/test_staging.py) — S0/S1/S2 money path. Runner is
  wired for it in `_DEFAULT_TARGETS`; needs its own budgeted run (~8 min).
- `libs/risk/gate.py` (tests/risk/test_gate.py) — same.
- `libs/execution/binance_live.py` (tests/execution/test_binance_live.py) — same; this is the
  #2 connector file whose bar is the 07-31 gate.
- `libs/execution/retry.py` — **has no dedicated test module at all.** That is the finding, not a
  runner limitation: it scores ERROR by design rather than being skipped. Owed: a test module
  before its mutants can be measured.
- The SECOND HALF of the v8 8.2 bar is a second-model-family fuzz/breaker report
  (`scripts/deep_review.py`, 13 seats) — a PANEL task, not achievable by the same model, and
  currently blocked on the OpenRouter top-up (register #89). Mutation testing does not substitute
  for it and this file does not claim it does.
