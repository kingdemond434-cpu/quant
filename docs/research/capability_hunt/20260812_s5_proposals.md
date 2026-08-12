# CAPABILITY HUNT PROPOSALS 20260812 slot 5

LENS: SILENT-EXCEPT -- find an except/try that swallows a failure and lets the caller proceed as if it succeeded. A swallowed order error once stranded ~$2,150 of real inventory.

## A -- Claude family

Agent's sweep confirms the proposal's sibling finding with live instances. I verified its top three claims directly and **corrected one it overstated**:

## Verified live instances of the attrition denominator (brainstorm item #1)

**CONFIRMED — `scripts/check_coverage_floors.py:139-148`. This is the sharpest one, and it is on the money path.**
```python
for rel in MONEY_PATH:
    s = files.get(rel, {}).get("summary")
    if not s: continue          # <- file absent from coverage.json leaves BOTH sides
    stmts += ...; covered += ...
return {"money_path_pct": round(100.0 * covered / stmts, 2) ...}
```
`MONEY_PATH` has **5 entries** (I verified by importing it — my own memory said 7 and was wrong). A money-path module that stops appearing in the coverage report — renamed, its test file deleted, or the run dying before it imports — drops out of numerator *and* denominator. **`money_path_pct` then RISES while 20% of the money path goes dark**, and per `docs/research/COVERAGE_RATCHET.json` (L1.50) the floor ratchets up behind it and never comes down. The floor at session start is 89.44%. `coverage.json` is absent from the tree right now, so I cannot report current membership — that is genuinely UNMEASURED, not clean.

**CONFIRMED — `scripts/check_llm_routing.py:78`** (`except SyntaxError: continue` after the file is already known to reference the roster) → `routed_fraction = routed_n / len(organs)` → decides `BACKLOG` vs `OK` *and* is passed as `fence_exit(scanned=n_organs)`. An organ that stops parsing raises the fraction and can flip the fence green.

**CONFIRMED — `scripts/check_input_provenance.py:156-164`** — an artifact that becomes corrupt exits `examinable`, so `coverage = declared/len(examinable)` can carry PARTIAL → **OK**. Only the all-zero case is guarded. That is the L1.55 fence being defeated by the L1.55 failure mode.

**CONFIRMED — `scripts/check_calendar_gates.py:87-91`** — `n += 1` sits *after* the handler, so an unreadable file is dropped from the violation scan *and* from the `scanned=` denominator that L1.57 built to reveal exactly that.

**CONFIRMED, AND IT IS THE `benchmark_returns` LESSON REPEATED VERBATIM — `libs/research/axis_screen.target_horizon_sweep`.** Its skip accounting is *exemplary*: `attempted` incremented before every guard, `n_trials`/`n_screened`/`n_skipped` all published, invariant asserted in tests. And `grep -rn target_horizon_sweep --include=*.py .` returns **only the definition and its own test file — zero production callers.** The desk's UNIVERSAL DUTY ("every target-horizon cell is a DSR-counted trial") has a correct implementation that no live path can reach, so the honest denominator never arrives at `deflated_sharpe_ratio`. Desk lesson L0003: *"Walk the import graph. A one-hop grep proves a name exists somewhere, never that the code path runs."*

**PARTIALLY WRONG, corrected — `scripts/check_mypy_ratchet.py`.** The agent claimed the ratchet floor rises on attrition. `counts.pop(f)` at `:88-90` and `clean_fraction = len(clean)/max(len(counts),1)` at `:124` are real and survivor-biased **in the human-facing report**. But `--rebaseline` builds `merged = dict(base_per)` first, so an already-baselined file that becomes uncheckable **stays** in the denominator at its old count, and `check_ratchets._mypy_clean` reads that baseline's `per_file`. The ratchet is protected. The residual real defect is narrower: **a file uncheckable on its first ever run never enters `base_per`, so it is permanently absent from the denominator with nothing reporting it.**

## What this changes about the proposal

The agent also disproved my working assumption that nothing counts swallows: **L2.4's "EVERY DISCARD IS COUNTED" is live practice** in ~10 modules (`collect_funding_cross_section.py:78-113` is the canonical case with the reasoning in-line; `libs/research/extractor_invariants.py:242-245` is the model — a `SyntaxError` becomes an `Extractor(..., ("unparseable",), False)` row that stays in the denominator).

So the gap is **not** that the desk lacks the practice. It is that the practice is **unenforced**: the only fence is `check_build_standard._has_silent_swallow`, which matches `except: pass` and nothing else — and **every instance above uses `continue` or `return <default>`**. That sharpens my proposal rather than weakening it: handler yield measures the *rate* nobody can see, and brainstorm items #1 and #3 (attempted-vs-scanned reconciliation, and widening the AST detector past `pass`) now have **five confirmed live instances**, three of which move a fence verdict or a ratchet floor. I would row #3 first — it is a ~1h AST change against a fence that already exists, and it catches four of the five.

Nothing was modified; this run was read-only as instructed.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 402: Payment Required. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
