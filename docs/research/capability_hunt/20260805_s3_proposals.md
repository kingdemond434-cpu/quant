# CAPABILITY HUNT PROPOSALS 20260805 slot 3

LENS: FASTER PROMOTION -- what shortens the path from screen-hit to sized-capital without lowering a bar: an evidence accelerant (8h panels, event-density), a paper-sleeve auto-spawn, a resurrection-queue consumer. Time-to-alpha is a growth term.

## A -- Claude family

Three claims verified with fresh reads. The sweep confirms the finding, **corrects one thing I overstated**, and changes the proposal's design.

## Correction to what I wrote

I said the standing clocks have "no completion criterion anywhere in code." **Partially wrong.** Each runner does carry one in its own `_verdict()` — `run_crypto_shadow.py:84-91`, `run_crossasset_shadow.py:80-87`, `run_trend_shadow.py:61-68`, `run_trend_regime_shadow.py:65-67`, `run_shadow_forward.py:71-78` all emit `ACCUMULATING ({days}/90+ days)`. But the literal `90+` is an open-ended **floor, not an expiry**, and what happens past it is worse than nothing: four of those scripts codify the exact opposite of futility stopping, verbatim —

> `"WEAK forward -> continue shadow, do not deploy"`

So the state files are birth certificates (that part holds — `slot_registry.py:62` calls them exactly that, and `shadow_start` is never converted to an age; `:175-177` uses it only to format a display string), and the rule for a clock that is going nowhere is *continue indefinitely*. My claim was directionally right and factually loose. The corrected version is stronger.

## The finding that changes the design

I proposed splitting `MAX_FORWARD_SLOTS` into `HOLM_M` and `SLOT_SEATS`. **They are already decoupled — five different values are in production right now, disagreeing, on what `slot_registry.py:6` calls "the single most load-bearing integer on the desk's only path from research to capital," with zero test coverage** (`grep -rln "slot_registry\|forward_slots" tests/` → 0 files):

| # | Site | Value in production |
|---|---|---|
| 1 | `run_axis_shadows.py:114` `holm_bar(len(_AXES))` | **m=3, bar 2.128** — what the live axis clocks are *actually* judged against |
| 2 | `slot_registry` / `forward_slots.json` | **m=12, bar 2.638** — what the desk believes |
| 3 | `run_alerts.py:344-350` | `len([]) + hardcoded 6` → `6 > 12` is **always False**; `slot_budget_exceeded` is structurally unreachable — and its six are different sleeves by name than the registry's six |
| 4 | `meta_research_review.py:207-208` | `forward_slots_in_use: 0, slots_free: 12` — reports **12 free slots** while the registry reports 0, and feeds `record_desk_metrics.py:95` plus the bottleneck evidence |
| 5 | `run_cashcarry_shadow.py:126-128` | Holm-**EXEMPT** (judged alone), yet occupies a seat and is counted inside the 12 |

Two more: `concurrent_m()` — the function whose entire purpose is feeding the true `m` to the bar — has **zero callers** (`libs/research/slot_registry.py:219`, the definition, is the only hit). And `slot_registry.py:160`, the one documented exit from the cohort, filters on `verdict == "RETIRED"` — **nothing in the repo ever writes that string**. It is a dead branch; the single real retirement was done by deleting a key from the `_AXES` dict.

**Ordering constraint this imposes:** consolidation onto `concurrent_m()` must land *before* the futility instrument, not after. Conditional power computed against a 2.128 bar that should be 2.638 would authorize kills on clocks that were still viable — a powered instrument pointed at a corrupted input is worse than no instrument. Revised cost: ~7h, of which step 0 (~2h) is independently valuable and is the higher-priority half.

## The single best repair on the path

`"FAILING FORWARD -> kill candidate"` is written by **five** scripts (`run_crypto_shadow.py:88`, `run_crossasset_shadow.py:84`, `run_shadow_forward.py:75`, `run_trend_shadow.py:65`, `run_trend_regime_shadow.py:69`) and **read by nothing** — greps for the string return writers only. The desk wrote the kill verdict and never wired the killer. That is not a missing capability; it is an inert one, and it is the cheapest possible first cut of everything above.

Two documents also assert the mechanism exists: `docs/research/TWO_STAGE_DISCOVERY_LAW.md:44` — *"slots recycle as clocks resolve (~40-90d)"* — against 0 deaths in 90 days; and `docs/CONSTITUTION.md:293` — *"forward slots are fed daily from the resurrection queue"* — with no code implementing it and `scripts/run_resurrection.py` specified at `STRUCTURAL_EDGE_IDEAS.md:68` and never built.

**Novelty holds, and sharpens.** `docs/GAP_REGISTER.md` has zero rows on forward-slot occupancy, queue wait, or promotion latency (every `slot` hit there means *engineering* slot). The one piece of prior art — `deep_sweep/20260726_alpha-discovery.md:376-379` — had the right formula and applied only the vacancy term: *"Clock throughput = occupancy × time… the desk wastes 17-50% of the exact resource it names as binding."* The symmetric failure is named as a cost at `slot_registry.py:213-215` and then explicitly routed away from ("a cost to fix upstream, never by shrinking m"), with no instrument built. And `GAP_REGISTER.md:271` row 25 — a prior faster-clock-resolution attempt **retired as refuted** — was success-side graduation only; the futility boundary was never tested, so this does not re-litigate a graveyard entry. Fittingly, `libs/research/anytime_valid.py:88` already has the hook: `days_to_graduation` returns `None` when the clock never crosses, and no caller acts on `None`. The futility boundary is literally the branch nobody consumes.

## Brainstorm, continued (31→)

31. **Wire the five inert `FAILING FORWARD -> kill` verdicts to an actual reader** — one consumer, five clocks, no new statistics. — **S** — ledger.
32. **Consolidate all five cohort-integer sites onto `concurrent_m()`** (zero callers today); add the first test in `tests/` for the registry. — **S** — ledger + fence.
33. **`meta_research_review` is diagnosing a 12-slot idleness defect that does not exist** while the real one is invisible to it — and its output feeds `record_desk_metrics` and the bottleneck evidence, so the desk's bottleneck ranking is computed from a two-source-of-truth violation. — **S** — fence.
34. **`slot_budget_exceeded` can never fire** (`6 > 12`) — a guard on the fixed-for-life bar with an unreachable failure state, the same class as the substring-whitelist fences already cut at `TIER1_BENCHMARK.md` research_governance. — **A** — fence.
35. **`slot_registry.py:160`'s `RETIRED` filter is unreachable** — nothing writes the string. Either wire a writer or delete the branch; an exit path that cannot be taken is worse than an acknowledged absence. — **A** — ledger.
36. **Two docs assert mechanisms that do not exist** (`TWO_STAGE_DISCOVERY_LAW.md:44` slot recycling, `CONSTITUTION.md:293` daily resurrection feed). A law that describes absent machinery is a fence that cannot fire, and both are load-bearing on the promotion path. — **S** — constitution + fence.
37. **Cashcarry is Holm-exempt but seat-occupying** — it consumes the scarce resource without paying the multiplicity it imposes on its neighbours, which is the exact inverse of the desk's stated fail-safe direction. Decide: pay the bar or vacate the seat. — **A** — ledger.
38. **`anytime_valid.days_to_graduation → None` is an unconsumed futility signal already on disk** — the cheapest possible pilot of the deep proposal, zero new math. — **S** — ledger.
39. **`run_alerts`'s hardcoded `_standing = 6` names six different sleeves than `_STANDING_STATES`** (carry/perp_ls/oi_div/ls_contrarian/liq_reversal/stables vs cashcarry/crossasset/crypto_combined/trend_30d/trend_regime/legacy_shadow) — two rosters diverged without either noticing. — **A** — fence.
40. **Zero tests on the promotion path.** The desk's most load-bearing integer, five disagreeing values, no test. Mutation-test the registry before trusting any repair to it. — **S** — test suite.

Next I would generate on the execution-side growth terms I flagged earlier — maker-first routing measured vs modelled, fee-tier laddering, funding-payment sweep timing, the BNB fee-asset auto-policy — then venue breadth/counterparty (the unbuilt Bybit second-venue spec, withdrawal drills), then the adversary lens on the −51.74bps carry execution gap.

Still read-only; nothing modified.


## B -- GPT-9 family (independent)

(GPT-9 seat unavailable: HTTPError: HTTP Error 400: Bad Request. This run is SINGLE-FAMILY -- treat its proposal as unconfirmed by an independent family, and note that in the record.)
