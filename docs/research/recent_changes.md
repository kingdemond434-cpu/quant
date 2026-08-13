# Desk changes, last 24h (generated 2026-08-13T10:10:09Z)

165 commit(s). Patches truncated to 400 lines each -- a seat that receives
40k lines reviews none of them, and the design decision is almost always in the first
few hundred.


---

## 04f00226 merge live branch into L1.63 partition-power build

```diff
commit 04f0022606111c97e8c8750b6354b80a737f24df
Merge: 32e54830 d739bb95
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 10:08:46 2026 +0000

    merge live branch into L1.63 partition-power build

 backups/moat/manifest.json | 33 ++++++++++++++++-----------------
 docs/desk_lessons.jsonl    |  2 ++
 2 files changed, 18 insertions(+), 17 deletions(-)
```


---

## 32e54830 L1.63: the desk's robustness certificates have never been able to say NO
MISSING: nothing could ask whether the partition behind a "regime robust"
certificate is CAPABLE of returning False. Three wired gates implement one
rule -- split the returns, require net-positive in >=K groups -- and all three
partition by realized-vol terciles: regime_robust (blocks REGISTRY promotion),
sleeve_allocation min_regimes_positive (a sizing ceiling), check_promotion_gate
two_regimes (LIVE at 15% of book).

Every existing instrument reads the OUTCOME. check_fence_yield (L1.43) asks
whether a gate ever FIRED; check_gate_reachability (L1.49) whether it ever RAN;
gate_discrimination reads an accept/reject tally. None sees a gate that runs on
every candidate, is perfectly reachable, emits a row every time, and returns
True on all of them because its partition CANNOT PRODUCE A NEGATIVE GROUP --
neither dead nor mis-calibrated, but welded open by its choice of axis.

WHAT IT CAUGHT, first run: 4 of 4 partitions WELDED on 213 symbols x 2,384 days
(2020-02-03 -> 2026-08-13), carry = daily top-10 by trailing funding net of
6bps/turn. vol terciles 3/3 positive, funding 2/2, trend 2/2, breadth 3/3. Six
and a half years and not one axis could produce the failing group its
certificate claims to test for. Measured cause: daily cross-sectional selection
is itself the hedge -- unselected, market funding is non-positive on 40.6% of
days; after top-10 selection, 3.0%.

IT ALSO CAUGHT ITS OWN FALSIFIER. That script's first version made
finds_dead_state decisive, then measured a proxy non-positive on 3.0% of days,
so the criterion could not fire for EITHER axis and the verdict fell through to
a spread comparison answering a different question. It would have published a
graveyard-grade REFUTED from a test structurally incapable of returning anything
else. Hardened to report UNDERPOWERED, with the three instrument checks as
first-class output.

THIS REFUTES THE PROPOSAL THAT PRODUCED IT (R0604 REJECTED): the capability hunt
proposed wiring a funding-state axis into these gates. Its structural claims are
all true, but the funding axis is itself WELDED, so wiring it would add a second
gate certifying identically. The missing axis was never the defect; the rule was.

The repair is UPWARD (L1.49). This lifts nothing, sizes nothing, promotes
nothing, opens no gate and loosens no bar -- regime_robust behaves identically
before and after, and it has no vocabulary for turning a failing verdict into a
passing one.

Verdict label SOLO: the GPT-9 seat returned 402 Payment Required, so this is
single-family and uncorroborated (L1.33).

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 32e5483019016f110b3d7f2df9ea396ef0fc9497
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 10:07:36 2026 +0000

    L1.63: the desk's robustness certificates have never been able to say NO
    
    MISSING: nothing could ask whether the partition behind a "regime robust"
    certificate is CAPABLE of returning False. Three wired gates implement one
    rule -- split the returns, require net-positive in >=K groups -- and all three
    partition by realized-vol terciles: regime_robust (blocks REGISTRY promotion),
    sleeve_allocation min_regimes_positive (a sizing ceiling), check_promotion_gate
    two_regimes (LIVE at 15% of book).
    
    Every existing instrument reads the OUTCOME. check_fence_yield (L1.43) asks
    whether a gate ever FIRED; check_gate_reachability (L1.49) whether it ever RAN;
    gate_discrimination reads an accept/reject tally. None sees a gate that runs on
    every candidate, is perfectly reachable, emits a row every time, and returns
    True on all of them because its partition CANNOT PRODUCE A NEGATIVE GROUP --
    neither dead nor mis-calibrated, but welded open by its choice of axis.
    
    WHAT IT CAUGHT, first run: 4 of 4 partitions WELDED on 213 symbols x 2,384 days
    (2020-02-03 -> 2026-08-13), carry = daily top-10 by trailing funding net of
    6bps/turn. vol terciles 3/3 positive, funding 2/2, trend 2/2, breadth 3/3. Six
    and a half years and not one axis could produce the failing group its
    certificate claims to test for. Measured cause: daily cross-sectional selection
    is itself the hedge -- unselected, market funding is non-positive on 40.6% of
    days; after top-10 selection, 3.0%.
    
    IT ALSO CAUGHT ITS OWN FALSIFIER. That script's first version made
    finds_dead_state decisive, then measured a proxy non-positive on 3.0% of days,
    so the criterion could not fire for EITHER axis and the verdict fell through to
    a spread comparison answering a different question. It would have published a
    graveyard-grade REFUTED from a test structurally incapable of returning anything
    else. Hardened to report UNDERPOWERED, with the three instrument checks as
    first-class output.
    
    THIS REFUTES THE PROPOSAL THAT PRODUCED IT (R0604 REJECTED): the capability hunt
    proposed wiring a funding-state axis into these gates. Its structural claims are
    all true, but the funding axis is itself WELDED, so wiring it would add a second
    gate certifying identically. The missing axis was never the defect; the rule was.
    
    The repair is UPWARD (L1.49). This lifts nothing, sizes nothing, promotes
    nothing, opens no gate and loosens no bar -- regime_robust behaves identically
    before and after, and it has no vocabulary for turning a failing verdict into a
    passing one.
    
    Verdict label SOLO: the GPT-9 seat returned 402 Payment Required, so this is
    single-family and uncorroborated (L1.33).
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/CONSTITUTION.md                              |  62 +++++
 docs/research/capability_hunt/20260813_s0_hunt.md | 139 ++++++++++++
 docs/research/recommendation_ledger.json          |  36 +++
 libs/validation/partition_power.py                | 210 +++++++++++++++++
 ops/crontab.manifest                              |  10 +
 ops/principal_doctrine.txt                        |   2 +
 scripts/build_enforcement_matrix.py               |   4 +
 scripts/check_build_standard.py                   |   1 +
 scripts/check_partition_power.py                  | 225 ++++++++++++++++++
 scripts/falsify_funding_state_axis.py             | 264 ++++++++++++++++++++++
 tests/validation/test_partition_power.py          | 148 ++++++++++++
 11 files changed, 1101 insertions(+)

diff --git a/docs/CONSTITUTION.md b/docs/CONSTITUTION.md
index 2c0b8ca6..d0a77a9b 100644
--- a/docs/CONSTITUTION.md
+++ b/docs/CONSTITUTION.md
@@ -2703,3 +2703,65 @@ distinguishable from "this panel's power rests on an assumption nobody checked"
 on this desk until now, and only one of them is evidence.
 
 FENCED by `scripts/check_panel_breadth.py` over `libs/research/panel_breadth.py`.
+
+## L1.63 A ROBUSTNESS CERTIFICATE WHOSE PARTITION CANNOT FAIL IS A WELDED GATE
+
+Three wired gates certify that an edge is "regime robust", and all three implement one rule: split
+the return series into groups and require it to be net-positive in at least K of them.
+`libs/autodiscovery/regime.regime_robust` blocks REGISTRY promotion, `libs/risk/sleeve_allocation`
+min_regimes_positive sets a sizing ceiling, and `scripts/check_promotion_gate` two_regimes stands
+between a candidate and LIVE at 15% of book. **All three partition by realized-volatility terciles,
+and no instrument on this desk could ask whether that partition is capable of returning False.**
+
+**WHY EVERY EXISTING INSTRUMENT WAS BLIND, AND IT IS A THIRD BLINDNESS, NOT A REPEAT.** L1.43's
+`check_fence_yield` asks whether a gate ever FIRED. L1.49's `check_gate_reachability` asks whether
+a gate ever RAN, measured from the declaration site precisely because a gate that never ran emits
+no tally row. `gate_discrimination` reads a per-gate accept/reject histogram. Each of those reads
+the gate's OUTCOME. None can see the case where the gate runs on every candidate, is perfectly
+reachable, emits a row every time, and returns True on all of them **because the partition it uses
+cannot produce a negative group for the edge in front of it**. That gate is neither dead nor
+mis-calibrated; it is WELDED OPEN by its choice of axis, and an accept/reject tally cannot separate
+"passed because the edge is robust" from "passed because this partition was never able to fail".
+L1.49 said absence from a rejection tally is ambiguous; this is the same ambiguity at the far end,
+where a gate that rejects nothing looks identical to a bar being cleared honestly.
+
+**THE PROVING INSTANCE IS THIS LAW'S OWN FALSIFIER.** The capability hunt of 2026-08-13 proposed
+adding a funding-state axis to the robustness certificate, and its falsifier was run first, as the
+desk requires. That falsifier's FIRST version declared `finds_dead_state` its decisive criterion
+and then measured a carry proxy that is non-positive on 3.0% of days -- so the criterion could not
+fire for EITHER axis, and the verdict fell through to a spread comparison answering a different
+question. **It would have published REFUTED from a test structurally incapable of returning
+anything else**, and it was caught only by re-reading the instrument instead of its output. The
+identical defect, one level up, in the very run built to find it.
+
+**MEASURED THE DAY THIS WAS BUILT**, on 213 symbols x 2,384 days (2020-02-03 -> 2026-08-13) of the
+desk's own D1 funding panel, carry sleeve = daily top-10 by trailing funding net of 6bps/turn:
+vol terciles 3/3 groups positive; funding state 2/2; trend state 2/2; funding breadth 3/3.
+**Four axes, 6.5 years, and not one could produce the failing group its certificate claims to test
+for.** The measured reason is that daily cross-sectional selection is itself the hedge: unselected,
+the market's funding is non-positive on 40.6% of days; after top-10 selection, 3.0%. The
+certificate is not wrong -- it is EMPTY, and nothing here could say so. This also REFUTES the
+proposal that produced it: the missing axis was never the defect, the rule was.
+
+**OPERATIVE.** Every partition behind a robustness certificate is graded on the desk's own data via
+`libs/validation/partition_power.partition_power` -- DISCRIMINATING (some graded group came out
+non-positive, so a pass carries information), WELDED (every graded group positive, so the
+certificate would have passed anything), or UNMEASURED. **UNMEASURED and WELDED stay distinct**:
+"every group was positive" and "no group had enough observations to tell" are different claims and
+only one is evidence (L1.28a), so a partition below `MIN_GROUP_OBS` refuses to grade rather than
+manufacture a verdict. Unlabelled observations are counted, never silently dropped (L1.60).
+
+**THE REPAIR IS UPWARD, NEVER DOWNWARD (L1.49).** A WELDED reading never justifies deleting a gate,
+lowering a bar, or calling the gauntlet smaller. It justifies giving the certificate an axis able
+to produce a negative group, or recording out loud that it carries no information for this edge. A
+smaller gauntlet that runs is not an improvement on a larger one that does not.
+
+**ANTI-TIMIDITY READING (L1.28).** This is a MEASUREMENT duty and a SCOPE EXPANSION. It lifts
+nothing, sizes nothing, promotes nothing, opens no gate and loosens no statistical bar;
+`regime_robust`, `min_regimes_positive` and `two_regimes` behave identically before and after, and
+it moved not one recorded number by itself. It has no vocabulary for turning a failing verdict into
+a passing one. Its whole effect is to make "this edge survived a test that could have killed it"
+distinguishable from "this edge passed a test that has never killed anything" -- byte-identical on
+this desk until now, and only one of them is evidence.
+
+FENCED by `scripts/check_partition_power.py` over `libs/validation/partition_power.py`.
diff --git a/docs/research/capability_hunt/20260813_s0_hunt.md b/docs/research/capability_hunt/20260813_s0_hunt.md
new file mode 100644
index 00000000..f123cb99
--- /dev/null
+++ b/docs/research/capability_hunt/20260813_s0_hunt.md
@@ -0,0 +1,139 @@
+# Capability hunt 2026-08-13 s0 -- BUILDER record
+
+**Verdict label: SOLO.** The GPT-9 seat returned `HTTPError: HTTP Error 402: Payment Required`, so
+only the Claude family proposed. Nothing below is cross-family corroborated (L1.33): the delta
+between families is normally the finding, and there is no delta to read. Recorded as a dated,
+measured fact, not as agreement.
+
+## What the families proposed
+
+**Proposal A (Claude).** A funding-state library -- named, causal, backfilled, episode-counted
+regime series in funding/basis/OI space -- wired as a second axis into the three gates that issue
+"regime robust" certificates and set the sizing ceiling. Its argument: all three wired gates
+partition by realized-volatility terciles, so a promotion verdict prints `regime_robust=True` in a
+space that cannot see where the desk's only surviving edge actually dies.
+
+**Proposal B (GPT-9).** Unavailable (402 Payment Required).
+
+## Adjudication
+
+With one proposal there is no convergence signal, so Proposal A was judged on its own evidence --
+and it shipped its own falsifier with the instruction to run it first. That is what happened.
+
+**Its three STRUCTURAL claims are all TRUE, verified by reading the code, not by grep:**
+
+| Claim | Verified |
+|---|---|
+| `libs/autodiscovery/regime.regime_robust` partitions by vol terciles only | TRUE (`regime.py:17,40`) |
+| `libs/risk/sleeve_allocation` min_regimes_positive reads the same space | TRUE (`:95,191`) |
+| `scripts/check_promotion_gate` two_regimes reads `vol_regime` at entry | TRUE (`:191-196`) |
+| `libs/research/crypto_regime.regime_labels` computes a funding axis, wired into no gate | TRUE (only consumer is `run_crypto_portfolio.py`, not in cron) |
+| `data/state_conditional_candidates.json` has no producer | TRUE -- and it HAS a consumer (`run_wealth_report.py:74`). A phantom path. |
+
+**Its ECONOMIC premise is REFUTED.** Falsifier: `scripts/falsify_funding_state_axis.py`, on 213
+symbols x 2,384 days (2020-02-03 -> 2026-08-13) of the desk's own D1 funding panel; carry sleeve =
+daily top-10 by trailing funding, selection strictly causal, cost swept at 0/2/6 bps per turn.
+
+### The falsifier's first version was itself the defect it was hunting
+
+Its first run printed `REFUTED-vol-separates-at-least-as-well` and it was **wrong to print
+anything**. Three checks on the instrument, run before accepting its output:
+
+- **Q1** -- the proxy is non-positive on **3.0%** of days, so `finds_dead_state`, the criterion the
+  script itself declared decisive, could not fire for *either* axis. The verdict fell through to a
+  spread comparison answering a different question. A criterion that cannot fire carries zero
+  information (L1.43), and the instrument would have published a graveyard-grade refutation from it.
+- **Q2** -- `corr(rolling vol, carry) = +0.50`. The gate partitions a series by its own volatility;
+  on a funding-derived series that is partly a partition by `|funding|` itself, so the vol axis's
+  apparent win is partly tautological.
+- **Q3** -- the decisive one. Selected top-10: +7.61 bps, 3.0% of days non-positive. **Unselected:
+  +2.11 bps, 40.6% of days non-positive.** Daily cross-sectional selection re-introduces positive
+  funding even in a market-wide drought; the basket is *chosen* to be the richest 10 names.
+
+The script was hardened to refuse rather than grade: `UNDERPOWERED-no-axis-can-express-a-dead-state`
+is now its verdict at every cost rung, and the three instrument checks are first-class output.
+
+### What the corrected instrument found
+
+| axis | groups net-positive | can the certificate fail? |
+|---|---|---|
+| vol terciles (**WIRED**) | 3/3 | **no** |
+| funding state | 2/2 | **no** |
+| trend state | 2/2 | **no** |
+| funding breadth | 3/3 | **no** |
+
+Four axes, 6.5 years, net of 6 bps/turn, and **not one can produce the failing group its certificate
+claims to test for.** The missing axis was never the defect -- **the rule was.**
+
+## What I built
+
+**L1.63 -- A ROBUSTNESS CERTIFICATE WHOSE PARTITION CANNOT FAIL IS A WELDED GATE.**
+
+- `libs/validation/partition_power.py` -- grades any partition DISCRIMINATING / WELDED /
+  UNMEASURED. UNMEASURED and WELDED stay distinct: "every group was positive" and "no group had
+  enough observations to tell" are different claims and only one is evidence (L1.28a). Unlabelled
+  observations are counted, never silently dropped (L1.60).
+- `scripts/check_partition_power.py` -> `data/partition_power.json`. Exits 2 on WELDED/UNMEASURED,
+  declares `scanned=` at its exit site (L1.57), calls `guard()` (L1.42).
+- `scripts/falsify_funding_state_axis.py` -> `reports/falsify_funding_state_axis.json` -- the
+  evidence artifact, kept because a negative screen is a first-class deliverable (L1.17).
+- Law in `docs/CONSTITUTION.md` + `ops/principal_doctrine.txt`; mapping in
+  `build_enforcement_matrix.py` (**0 orphans**); `_GOVERNED` row in `check_build_standard.py`
+  (**83/83**); `ops/crontab.manifest` line with EVIDENCE + CONFIDENCE, **installed live** (drift
+  resolved) so it is a wired organ rather than inventory.
+- `tests/validation/test_partition_power.py` -- 13 tests, including the two that fail if the wiring
+  is removed: `summarise([])` must be UNMEASURED and never OK, and the roster must keep the WIRED
+  vol axis.
+
+### Why this and not the proposal
+
+No existing instrument can ask this question. `check_fence_yield` (L1.43) asks whether a gate ever
+FIRED; `check_gate_reachability` (L1.49) asks whether it ever RAN; `gate_discrimination` reads an
+accept/reject tally. **All three read the outcome.** None can see a gate that runs on every
+candidate, is perfectly reachable, emits a row every time, and returns True on all of them because
+its partition cannot produce a negative group -- neither dead nor mis-calibrated, but welded open by
+its choice of axis.
+
+## First run: a defect, which is the success condition
+
+```
+partition power (L1.63): WELDED -- 4 welded / 0 discriminating of 4 (213 symbols, 2384 days)
+  WELDED  vol_terciles_WIRED: 3/3 groups positive, can_fail=False
+  WELDED  funding_state:      2/2 groups positive, can_fail=False
+  WELDED  trend_state:        2/2 groups positive, can_fail=False
+  WELDED  funding_breadth:    3/3 groups positive, can_fail=False
+```
+
+The wired axis gates REGISTRY promotion, sleeve sizing, and LIVE at 15% of book. **The repair is
+UPWARD (L1.49)**: give the certificate an axis able to go negative, or record out loud that it
+carries no information for carry. A WELDED reading never justifies deleting a gate or lowering a
+bar -- a smaller gauntlet that runs is not an improvement on a larger one that does not.
+
+## What I refused, and why
+
+- **R0604 REJECTED** -- the funding-state library. Refuted by its own falsifier before a line was
+  written; wiring it would add a second gate certifying identically (zero information, L1.43).
+- **R0605 OPEN** -- the 4/4 WELDED finding itself, for upward repair.
+- **R0606 OPEN** -- the phantom path: `state_conditional_candidates.json` is read by
+  `run_wealth_report.py:74` and written by nothing, so the conditional-alpha branch (GAP row 105) is
+  unfeedable **by construction, not by neglect**.
+
+Deliberately **not** built: the state library, the breadth axis as a *gate* (it is welded too, so
+wiring it would repeat the error one axis over), and any change to `regime_robust`'s behaviour --
+this law lifts nothing, sizes nothing and promotes nothing.
+
+## Verification
+
+`ruff` clean; `python -m mypy` clean (630 files); 13/13 new tests; `build_enforcement_matrix` 0
+orphans, 84 principles / 102 fences; `check_build_standard` 83/83; `check_timidity_language` clean
+with L1.28 injected; `check_constitution_core` intact; `check_scheduler_manifest` no
+partition_power drift (36 pre-existing drift/dupe rows are unrelated and predate this run).
+
+## Next in this seam, unwritten
+
+(a) The desk's `two_regimes` gate reads `vol_regime` tags on *closed trades* -- a different and much
+smaller sample than the panel graded here, so its partition power is separately UNMEASURED and worth
+a run once fills exist. (b) If every axis is welded on a *selected* sleeve, the honest robustness
+question may not be "which state" but "what happens when selection breadth collapses" -- breadth is
+welded on 6.5y of history, but its LOW tercile still held 3.6% of names selectable, and the
+certificate has never been tested on a panel where the top-10 cannot be filled at all.
diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index c99515ca..bbc5031b 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -7623,6 +7623,42 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0604",
+   "source": "cycle",
+   "summary": "REFUSED (capability hunt 2026-08-13 s0): funding-state axis wired into regime_robust/sleeve_allocation/two_regimes. Refuted by its own pre-registered falsifier -- on 213 symbols x 2384 days the funding axis is WELDED (2/2 groups positive), so it would certify identically to the vol axis and add a second zero-information gate. Evidence: data/partition_power.json, reports/falsify_funding_state_axis.json.",
+   "roi_bps": null,
+   "raised": "2026-08-13T10:01:59.630805+00:00",
+   "status": "rejected",
+   "reason": "Refuted by its own pre-registered falsifier before a line was written. The proposal's three STRUCTURAL claims are all true (regime_robust/min_regimes_positive/two_regimes are vol-terciles-only; crypto_regime.regime_labels computes a funding axis wired into no gate; state_conditional_candidates.json has a consumer and no producer). Its ECONOMIC premise -- that carry dies in a funding state the vol axis cannot see -- is false on 213 symbols x 2384 days: the funding axis is itself WELDED (2/2 groups net-positive), so wiring it would add a second gate that certifies identically and carries zero information (L1.43 gate-optimality). The measured reason is that daily top-10 cross-sectional selection absorbs market-wide funding state (unselected 40.6pct of days non-positive vs 3.0pct selected). The general capability the falsifier revealed WAS built instead: L1.63 partition power.",
+   "commit": null,
+   "due": null,
+   "disposed": "2026-08-13T10:02:26.721698+00:00"
+  },
+  {
+   "id": "R0605",
+   "source": "cycle",
+   "summary": "L1.63 first run: ALL FOUR robustness partitions WELDED on the desk's only surviving edge -- vol terciles (WIRED: gates REGISTRY promotion, sleeve sizing, LIVE at 15pct of book) 3/3 positive, funding 2/2, trend 2/2, breadth 3/3 over 6.5y. Repair is UPWARD (L1.49): the certificate needs an axis able to go negative, or an explicit record that it carries no information for carry. Measured cause: daily top-10 selection is itself the hedge (unselected 40.6pct of days non-positive vs 3.0pct selected).",
+   "roi_bps": null,
+   "raised": "2026-08-13T10:02:06.836328+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0606",
+   "source": "cycle",
+   "summary": "PHANTOM PATH: data/state_conditional_candidates.json is READ by scripts/run_wealth_report.py:74 and written by NOTHING -- libs/validation/state_conditional.Preregistration is structurally unfeedable, so the conditional-alpha branch (GAP row 105) is unfed by construction, not by neglect.",
+   "roi_bps": null,
+   "raised": "2026-08-13T10:02:11.935142+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
diff --git a/libs/validation/partition_power.py b/libs/validation/partition_power.py
new file mode 100644
index 00000000..6a4fd73a
--- /dev/null
+++ b/libs/validation/partition_power.py
@@ -0,0 +1,210 @@
+"""PARTITION POWER (L1.63) -- can the partition behind a robustness certificate ever say NO?
+
+WHAT THIS ASKS THAT NOTHING ELSE ON THE DESK DOES. Three wired gates certify that an edge is
+"regime robust" -- ``libs/autodiscovery/regime.regime_robust`` (blocks REGISTRY promotion),
+``libs/risk/sleeve_allocation`` min_regimes_positive (a sizing ceiling), and
+``scripts/check_promotion_gate`` two_regimes (LIVE at 15% of book). All three implement the same
+rule: split the return series into groups and require it to be net-positive in at least K of them.
+
+Every existing instrument reads the OUTCOME of that rule. L1.43's ``check_fence_yield`` asks
+whether a gate ever fired. L1.49's ``check_gate_reachability`` asks whether a gate ever RAN.
+``gate_discrimination`` reads a per-gate accept/reject tally. NONE of them can see the case where
+the gate runs on every candidate, is perfectly reachable, and returns True every single time
+because THE PARTITION IT USES CANNOT PRODUCE A NEGATIVE GROUP for the edge in front of it. The
+gate is not mis-calibrated and it is not dead; it is WELDED OPEN by its own choice of axis, and a
+tally cannot distinguish "passed because the edge is robust" from "passed because this partition
+was never able to fail".
+
+THE PROVING INSTANCE IS THIS MODULE'S OWN FALSIFIER (capability hunt 2026-08-13 s0). The run was
+built to test whether the desk's vol-tercile partition can see the state where funding carry dies.
+Its FIRST version declared ``finds_dead_state`` the decisive criterion, then measured a carry proxy
+that is non-positive on 3.0% of days -- so the criterion could not fire for EITHER axis, and the
+verdict fell through to a spread comparison that answered a different question. The instrument
+would have published REFUTED from a test that was structurally incapable of returning anything
+else. That is the identical defect, one level up, and it was caught only because someone re-read
+the instrument rather than its output.
+
+MEASURED THE DAY THIS WAS BUILT, on 213 symbols x 2,384 days (2020-02-03 -> 2026-08-13) of the
+desk's own D1 funding panel, carry sleeve = daily top-10 by trailing funding, net of 6bps/turn:
+  vol terciles   : 3/3 groups positive  -> CANNOT FAIL
+  funding state  : 2/2 groups positive  -> CANNOT FAIL
+  funding breadth: 3/3 groups positive  -> CANNOT FAIL
+Three different axes, 6.5 years, and not one of them can produce the failing group its certificate
+claims to test for. The measured reason is that daily cross-sectional selection is itself the
+hedge: unselected, the market's funding is non-positive on 40.6% of days; after top-10 selection,
+3.0%. The certificate is not wrong -- it is EMPTY, and nothing on this desk could say so.
+
+WHAT THIS IS NOT. It is a MEASUREMENT duty and a SCOPE EXPANSION. It lifts nothing, sizes nothing,
+promotes nothing, opens no gate and loosens no statistical bar; it has no vocabulary for changing
+any verdict it reads, and ``regime_robust`` behaves identically before and after. A WELDED reading
+is never an argument to delete a gate -- L1.49's repair is UPWARD: make the partition capable of
+failing (add an axis that can go negative), or record out loud that the certificate carries no
+information for this edge. A smaller gauntlet that runs is not an improvement on a larger one that
+does not.
+
+UNMEASURED IS A REAL ANSWER (L1.28a). Below a usable group size the module refuses to grade rather
+than manufacture a verdict, because "every group was positive" and "no group had enough
+observations to tell" are different claims and only one of them is evidence.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+from typing import Any
+
+import numpy as np
+
+#: A group smaller than this cannot support a mean/t-stat worth grading, so it is reported as
+#: present-but-unusable rather than silently folded into the verdict (L1.60: skips are counted).
+MIN_GROUP_OBS = 30
+
+#: Below this many graded groups a partition is not a partition -- one group cannot discriminate.
+MIN_GROUPS = 2
+
+#: Label reserved for observations the partition could not place (warm-up, NaN, undefined).
+UNLABELLED = "__none__"
+
+
```


---

## d739bb95 moat: manifest for the stores committed in 083ac2dc
run_moat_backup.py regenerates the checksum manifest alongside the store copies;
committing the stores without it leaves the tracked mirror describing itself with
a stale digest set. Same run (09:34:59Z) as 083ac2dc.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit d739bb9540495be82474eda47f29d1657cbf9215
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:43:54 2026 +0000

    moat: manifest for the stores committed in 083ac2dc
    
    run_moat_backup.py regenerates the checksum manifest alongside the store copies;
    committing the stores without it leaves the tracked mirror describing itself with
    a stale digest set. Same run (09:34:59Z) as 083ac2dc.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 backups/moat/manifest.json | 33 ++++++++++++++++-----------------
 1 file changed, 16 insertions(+), 17 deletions(-)

diff --git a/backups/moat/manifest.json b/backups/moat/manifest.json
index 6e5d9f97..d59ea2d2 100644
--- a/backups/moat/manifest.json
+++ b/backups/moat/manifest.json
@@ -1,15 +1,14 @@
 {
-  "generated": "2026-08-13T04:18:11.306922+00:00",
+  "generated": "2026-08-13T09:34:59.293923+00:00",
   "law": "L1.23 -- survival first: the moat is capital in information form",
   "stores": {
     "execution_tape": {
       "status": "REPLICATED",
       "kind": "tree",
       "path": "data/moat/execution_tape",
-      "bytes": 279290,
+      "bytes": 139999,
       "sha256": {
         "cashcarry_trades.jsonl": "fafa517df2d73d5e01c9dc16524c8c01da88e2d0b5f2ac99c63e418f60fa2541",
-        "cashcarry_trades.jsonl.pre_decontam_20260813": "c9fa5d25d4450de149e5f776d73d50921aa14941b7e887b1f9e2dd44cd7f0436",
         "quarantine_test_contamination.jsonl": "58135c3618709c427b38dcbadc11d38ef5aeba52cc16613a61fb3dd361af02b3"
       }
     },
@@ -17,15 +16,15 @@
       "status": "REPLICATED",
       "kind": "sqlite",
       "path": "data/sor_research.sqlite",
-      "bytes": 51208192,
+      "bytes": 52285440,
       "sha256": {
-        "sor_research": "1e6991ebdde054e57c8065fd0aceca8271f2aa60e58421fc5733bd2fdf758c5d"
+        "sor_research": "b3487b815ddaf7a6607126cc15957fead134e3e21584f8679cb87fe8c1876836"
       },
       "table_rows": {
         "schema_migrations": 7,
         "snapshots": 0,
         "config_versions": 0,
-        "audit_log": 862,
+        "audit_log": 868,
         "trials_ledger": 0,
         "alpha_registry": 0,
         "risk_registry": 0,
@@ -36,14 +35,14 @@
         "alpha_cards": 0,
         "alpha_events": 0,
         "alpha_performance": 0,
-        "research_memory": 297,
+        "research_memory": 313,
         "metric_points": 0,
         "alerts": 0,
-        "research_candidates": 4493,
+        "research_candidates": 4574,
         "lab_checkpoint": 1,
-        "campaigns": 385,
-        "workers": 16,
-        "candidate_returns": 5388
+        "campaigns": 387,
+        "workers": 17,
+        "candidate_returns": 5550
       }
     },
     "alpha_registry": {
@@ -52,7 +51,7 @@
       "path": "data/alpha_registry.sqlite",
       "bytes": 598016,
       "sha256": {
-        "alpha_registry": "adb36f95d9b97b9ff9e070215a6a5a3c8fa3865908904dcd36665d0b5ce3cce9"
+        "alpha_registry": "dfb92432ca250e7d42c631abdd82cf7d59891bca8523ed70da69c87a464b887d"
       },
       "table_rows": {
         "schema_migrations": 7,
@@ -101,19 +100,19 @@
       "status": "REPLICATED",
       "kind": "file",
       "path": "docs/graveyard.md",
-      "bytes": 137415,
+      "bytes": 149129,
       "sha256": {
-        "graveyard.md": "4976b25920d94e1852b2b3e2f0e5d2b74a98a726fd2df4e39df09c8eff73ceed"
+        "graveyard.md": "f64db7251d259b8770e888876ea4bf102aaf36aa169ff0af7aab9a6b09ad7dbc"
       }
     }
   },
   "skipped_over_cap": [],
   "not_covered_bytes": {
-    "data/lake": 1436000479,
-    "data/moat": 18958099380
+    "data/lake": 1437829283,
+    "data/moat": 19185626733
   },
   "not_covered_note": "bulk lake/L2 need the Storage-Box/R2 principal decision -- measured here every run so the gap stays a number",
-  "disk_free_pct": 20.1,
+  "disk_free_pct": 16.91,
   "fuse_pct": 15.0,
   "restore_drill_passed": true,
   "absent_stores": [],
```


---

## 0433bc06 desk lesson L0162: ownership evidence is what makes a tmpfs entry safe to free
"Held by nothing" is not the fact that decides a deletion -- most pids are
unreadable here, and a live agent session holds no descriptor while the model is
thinking. What decides it is OWNERSHIP: a worktree this repo REGISTERED is a
checkout of a committed sha, so removing it destroys no unique work and `git
worktree remove` refuses it while dirty. A bare directory of identical size and
age carries none of that.

Graduated to tests/scripts/test_max_audit_checks.py, so it costs ~0 context and is
enforced mechanically rather than by recall.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 0433bc065843333ce607f858e47574578be1b6c1
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:42:24 2026 +0000

    desk lesson L0162: ownership evidence is what makes a tmpfs entry safe to free
    
    "Held by nothing" is not the fact that decides a deletion -- most pids are
    unreadable here, and a live agent session holds no descriptor while the model is
    thinking. What decides it is OWNERSHIP: a worktree this repo REGISTERED is a
    checkout of a committed sha, so removing it destroys no unique work and `git
    worktree remove` refuses it while dirty. A bare directory of identical size and
    age carries none of that.
    
    Graduated to tests/scripts/test_max_audit_checks.py, so it costs ~0 context and is
    enforced mechanically rather than by recall.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/desk_lessons.jsonl | 2 ++
 1 file changed, 2 insertions(+)

diff --git a/docs/desk_lessons.jsonl b/docs/desk_lessons.jsonl
index 04309c1b..41bf84e6 100644
--- a/docs/desk_lessons.jsonl
+++ b/docs/desk_lessons.jsonl
@@ -163,3 +163,5 @@
 {"id": "L0158", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Before assuming a region's LANGUAGE is the moat, measure whether that region's practitioners actually write in it: run a native-key repo search AND a developer-search by LOCATION, and compare against a sibling-language control. If the population exists but the native corpus does not, the language layer is the retail layer and the technical output is already inside the EN seat's ground -- re-aim the seat at what is native-language BY INSTITUTIONAL CONSTRUCTION (regulators, exchanges, courts, religious certification), which cannot migrate to English.", "evidence": "2026-08-13 GitHub, one instrument: AR arbitrage repos 1/0/0 and quant-trading 0 vs CN 1174 / RU 24 / KR 6; discriminator by location gave UAE 67 > Korea control 59. docs/research/search_operator_library.md OP-075", "tags": ["mining"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "a search-behaviour rule for digger seats; no code path to gate"}
 {"id": "L0159", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "When a MANDATED artifact stays empty, audit the instrument that would have written its rows BEFORE concluding the duty was skipped. A wrong error message and an absent finding are indistinguishable from the outside, and only one of them is a person's fault. Specifically: a retry loop that overwrites a single 'last error' variable reports the LAST endpoint's cause for EVERY failure -- so if the last endpoint is permanently dead, every failure of every cause wears its error.", "evidence": "video_locked_log.md sat at ZERO rows for weeks; measured cause was fetch_video_transcript.py surfacing api.piped.yt's NXDOMAIN in place of private.coffee's HTTP 500 LOGIN_REQUIRED bot-wall. Ledger R0592", "tags": ["ops"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "concerns how a human reads an empty artifact; not mechanically checkable"}
 {"id": "L0160", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Carry a desk lesson's SCOPE QUALIFIER, not just its conclusion. Before inheriting a recorded kill, check which side of its stated boundary your mechanism falls on.", "evidence": "The breadth lesson reads 'the crypto cross-section is 1.54 independent bets RAW and 29 market-neutral -- any DIRECTIONAL cross-sectional mechanism is hard-killed by narrow_breadth'. Citing the memorable number (1.54) without the qualifier (DIRECTIONAL) would have graveyarded STATISTICAL-ARBITRAGE, the desk's thinnest family at THIN n=1 of 14 -- a cointegration pair is long y / short beta*x, beta-neutral BY CONSTRUCTION, so it lands on the 29 side. The lesson argues FOR the family, not against it.", "tags": ["research-process"], "source": "BR frontier miner s3 2026-08-13", "accepted_uninjected": "no test can catch a human/LLM dropping a scope qualifier while quoting a prose lesson; it rides in the ledger"}
+{"id": "L0161", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "When mining any foreign venue, asset class or institution, extract its RATIOS, not its THRESHOLDS. A threshold is asset-class-bound and does not travel; a ratio of two like-measured quantities is dimensionless, so annualisation, cost base, return definition and periodicity all cancel and it travels intact. Corollary for source selection: a TRANSCRIPT or talk states thresholds, while an API, schema or config states the measurement NAMESPACE -- so when both exist, mine the API for what they MEASURE and treat the talk only as evidence of where they set bars.", "evidence": "libs/validation/brain_calibration.py imported BRAIN's Sharpe target 1.25, fitness bar 1.0 and self-correlation cap 0.7 from a webinar transcript, then spent 10 lines of its own docstring warning the numbers are US-equity-bound and 'COMPARABLE IN ORDER OF MAGNITUDE ONLY'. rocky-d/wqb (MIT) read 2026-08-13 shows the same platform exposes os.osISSharpeRatio, os.sharpe60/125/250/500, os.preCloseSharpeRatio and is.prodCorrelation -- dimensionless instruments the caveat does not touch. Desk grep: zero hits for the first two families, prodCorrelation absent, so the un-portable half was imported and the portable half was never seen.", "tags": ["mining"], "source": "BRAIN hunter s3 2026-08-13, OP-083", "accepted_uninjected": "This is a judgement about WHICH quantity to extract from a foreign source during mining. No test can inspect a miner's choice of what to carry home from an external artifact."}
+{"id": "L0162", "learned": "2026-08-13", "cost": "hygiene", "recurrence": 1, "lesson": "A tmpfs entry's OWNER is the fact that makes freeing it safe, and 'held by nothing' is not it. When /tmp is over its ceiling, the reclaimable class is the one carrying OWNERSHIP EVIDENCE: a git worktree this repo REGISTERED (git worktree list) is a checkout of a committed sha, so removing it destroys no unique work and 'git worktree remove' refuses it while dirty. A bare directory of the same size and age carries none of that and must not be touched. Match ownership by CONTAINMENT, not equality -- a lawgate checkout registers at <entry>/t while <entry> is what holds the RAM.", "evidence": "2026-08-13: /tmp at 838MB vs a 600MB ceiling. 150MB was /tmp/wt-head, a worktree THIS repo registered at 02:55 and abandoned; establishing that took git worktree list, a read of its .git pointer, a diff of its one dirty artifact and a holder scan -- four commands the fence could have done, having already computed size, age and holder. The other 179MB was 255 dead agent-session scratch dirs (oldest 188h) whose producer is the harness, not desk code, and which therefore stays a reported defect (R0603). Fence green after: 838 -> 415MB, MemAvailable 747 -> 1346MB. Commit 268c7f50.", "tags": [], "source": "session", "enforced_by": "tests/scripts/test_max_audit_checks.py::TestTmpfsHoldersNameTheirProducer::test_a_desk_owned_worktree_carries_its_reclaim_command"}
```


---

## 520237fb ledger: batch-3 dispositions R0431/R0459/R0460 + R0603 raised
R0431 implemented (1e61e63a) -- horizon sweep run; the caveat is REFUTED and the
  sizing-relevant half (gamma_boundary) moved 0.950 -> 0.817 over 1y -> 10y.
R0460 implemented (083ac2dc) -- lead-lag standing rule wired into the novelty
  corpus and verified to surface for the exact class it pre-kills.
R0459 scheduled (2026-08-24, the live R0193 lane) -- batch REORDERED by a
  precondition audit rather than parked: card 28's data leg is complete today
  (15-min bars ARE the quarter-hour grid) so it goes first; card 27 is BLOCKED
  because it is pre-registered at 5-min and the desk holds 15-min only, and
  rebuilding it at 15-min would be a silent construction substitution reported as
  a test of the registered hypothesis; card 29's openmarket backfill is a 52KB
  slice, not the full corpus.
R0603 raised -- tmpfs's dominant producer by COUNT is the agent harness (255 dead
  session dirs, 179MB, oldest 188h, nothing reaps it), and unlike every desk-side
  producer it carries no ownership evidence the desk can act on automatically.
  Needs a decision, not a discovery.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 520237fb9b8d3c127843a77f5fa5dd2939edd7fe
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:40:12 2026 +0000

    ledger: batch-3 dispositions R0431/R0459/R0460 + R0603 raised
    
    R0431 implemented (1e61e63a) -- horizon sweep run; the caveat is REFUTED and the
      sizing-relevant half (gamma_boundary) moved 0.950 -> 0.817 over 1y -> 10y.
    R0460 implemented (083ac2dc) -- lead-lag standing rule wired into the novelty
      corpus and verified to surface for the exact class it pre-kills.
    R0459 scheduled (2026-08-24, the live R0193 lane) -- batch REORDERED by a
      precondition audit rather than parked: card 28's data leg is complete today
      (15-min bars ARE the quarter-hour grid) so it goes first; card 27 is BLOCKED
      because it is pre-registered at 5-min and the desk holds 15-min only, and
      rebuilding it at 15-min would be a silent construction substitution reported as
      a test of the registered hypothesis; card 29's openmarket backfill is a 52KB
      slice, not the full corpus.
    R0603 raised -- tmpfs's dominant producer by COUNT is the agent harness (255 dead
      session dirs, 179MB, oldest 188h, nothing reaps it), and unlike every desk-side
      producer it carries no ownership evidence the desk can act on automatically.
      Needs a decision, not a discovery.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/recommendation_ledger.json | 32 ++++++++++++++++++++++----------
 1 file changed, 22 insertions(+), 10 deletions(-)

diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index cd367892..c99515ca 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -5554,11 +5554,11 @@
    "summary": "ABSORPTION COST IS HORIZON-DEPENDENT AND THE 1-YEAR FRAMING INVERTS ITS SIGN. Found by R0266's study (scripts/study_absorbing_kelly.py, docs/research/absorbing_kelly_study.json). Modelling absorption as the account FREEZING at the barrier -- correct for a venue minimum, since the money is still there -- floors terminal log-wealth at log(barrier) while the upside stays unbounded. Over a ONE-YEAR horizon that bounded downside makes E[logW] CONVEX in leverage once mu is uncertain: mu-dispersion pays like a call option, more spread puts more mass in the unbounded good tail while the bad tail is capped, and the measured optimum came out ABOVE full Kelly (f* 1.05 to 3.00). The first version of the study read that as 'the two shrinks double-count in 12/12 cells' and would have shipped a confident wrong number; it was caught only because a positive control and a no-barrier control were added. THE FIX IS THE HORIZON, NOT THE MODEL: this desk's objective is LIFETIME E[log W_T], and over a lifetime absorption forfeits ALL future compounding rather than settling at 0.2x book -- the very floor that creates the convexity is what a long horizon removes. WORK: re-run the study with multi-year horizons (or an explicit continuation value for the non-absorbed state) and confirm f*_joint falls below f*_absorbing as the horizon grows, which is the direction theory predicts. LOW PRIORITY and say so: the boundary shrink at the desk's real barrier measured <=10% (gamma_boundary 0.90-1.00 at the 00-on-k viability floor), an order of magnitude below the estimation shrink already applied, so nothing about deployed sizing turns on it. This row exists so the artifact's own caveat is tracked rather than living only in a docstring.",
    "roi_bps": 8.0,
    "raised": "2026-08-05T23:28:25.564804+00:00",
-   "status": "open",
+   "status": "implemented",
    "reason": null,
-   "commit": null,
+   "commit": "1e61e63a",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T09:32:54.185531+00:00"
   },
   {
    "id": "R0432",
@@ -5890,11 +5890,11 @@
    "summary": "litminer run6 cards 27-29 build batch (arXiv sweep, dues aligned w/ R0193 lane): (27) 5-min copula-state BTC-hedged alt spread Stage-A screen — FIRST test of the n=0 stat-arb family; funding-accrual falsifier FIRST (paper omitted it; hourly rung graveyard-killed at all costs w/ funding modeled); (28) quarter-hour clock-phase imbalance screen on own-clock recorder + funding-window conditioning; cheapest leg = execution hygiene (avoid executing ON marks, feeds 66bps program, no alpha claim; executor change = money-path, L1.38 window applies); (29) Polymarket-vs-Deribit binary wedge MEASUREMENT (both feeds free; OpenMarket CC-BY corpus = backfill; trading leg separately gated needs-legitimacy-review). Litminer freeze bars runner code — alpha org owns constructions. Cards carry pre-registered falsifiers + graveyard priors.",
    "roi_bps": 40.0,
    "raised": "2026-08-12T02:07:10.562976+00:00",
-   "status": "open",
-   "reason": null,
+   "status": "scheduled",
+   "reason": "SCHEDULED ON THE R0193 LANE (due 2026-08-24, live and draining -- two of three data legs landed 08-11), with the batch REORDERED by a precondition audit run today rather than by the card order. NOT PARKED: each card now names its own blocker, measured. (27) 5-min copula-state BTC-hedged alt spread -- BLOCKED ON DATA. The card is pre-registered at 5-MINUTE resolution; the desk holds data/bars/*.parquet at 15-MINUTE only, 45 symbols, zero 5-min files. Rebuilding it at 15-min to make it runnable would be a silent construction substitution -- exactly the garden-of-forking-paths the screen-on-discovery duty forbids ('LOG EVERY CONSTRUCTION YOU TRY'), and it would be reported as a test of the pre-registered hypothesis when it is a different one. Needs a 5-min bar pull first; the resolution is not negotiable downward without re-registering the card. (28) quarter-hour clock-phase imbalance -- DATA READY, BUILD FIRST. The 15-min bars ARE the quarter-hour grid the card needs, and the own-clock recorder tapes exist, so this is the only card of the three whose data leg is complete today; it moves to the head of the batch on that evidence. Its execution-hygiene leg (avoid executing ON marks) is a money-path change and stays behind the L1.38 change window. (29) Polymarket-vs-Deribit binary wedge -- PARTIAL. Deribit collection exists (collect_deribit_surface.py, deribit_surface.parquet) but data/openmarket holds only 52KB (lag_pairs_ms.parquet + market_meta.parquet), a slice rather than the full ms-paired CC-BY corpus, so the backfill leg is short. The trading leg stays behind the section-13 legitimacy review as the card itself states. NOT IMPLEMENTED HERE and saying so: three Stage-A screens through the audited harness with the mandated target/horizon sweep and DSR trial logging is a research campaign, and a rushed screen produces a phantom verdict, which is negative discovery (L1.6). The unblocking work is a 5-min bar pull for (27) and the openmarket corpus completion for (29).",
    "commit": null,
-   "due": null,
-   "disposed": null
+   "due": "2026-08-24",
+   "disposed": "2026-08-13T09:36:51.498451+00:00"
   },
   {
    "id": "R0460",
@@ -5902,11 +5902,11 @@
    "summary": "litminer run6 inbox G: adopt the lead-lag STANDING RULE — future cross-venue lead-lag proposals must use RAW TRADES w/ own-clock provenance (never marks/indices: arXiv 2608.09188 proves estimators on marks have power=size when venues cross-reference; R0117's aliasing kill was the shallower half) + Epps-correct sampling; OpenMarket ms-paired corpus (universe map 97) is the free compliant testbed. One-paragraph rule into the validation lane's checklist; pre-kills a whole class of future phantom proposals at zero cost.",
    "roi_bps": 15.0,
    "raised": "2026-08-12T02:07:14.014990+00:00",
-   "status": "open",
+   "status": "implemented",
    "reason": null,
-   "commit": null,
+   "commit": "083ac2dc",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T09:35:34.867531+00:00"
   },
   {
    "id": "R0461",
@@ -7611,6 +7611,18 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0603",
+   "source": "cycle",
+   "summary": "TMPFS'S DOMINANT PRODUCER BY COUNT IS THE AGENT HARNESS, AND NOTHING REAPS IT. Freeing host-tmpfs-bloated today reclaimed 255 dead agent-session scratch dirs under /tmp/claude-1000 (179MB), the oldest 188h and accumulating continuously since 2026-07-26 -- 316 dirs total. Every desk-side producer of tmpfs has a cleanup owner (run_law_gate reaps its own lawgate-head-* checkouts past 2h; pytest got tmp_path_retention_policy=failed in 513ba24), and this one has none because ITS PRODUCER IS NOT DESK CODE: the Claude Code harness writes each session's task outputs and tool results there and never removes them, so the occupancy R0407 closed keeps returning from outside the repo. max_audit's fence correctly reports rather than deletes (a watcher of a shared resource cannot safely free it) and now names desk-OWNED git worktrees with their reclaim command (268c7f50), but harness scratch carries no ownership evidence the desk can act on automatically. THE SAFE DISCRIMINATOR IS MEASURED AND CHEAP: cron seats run under 'timeout 3000' (50min), so a session dir untouched for >=24h cannot belong to a live session, and a live-holder fd/cwd scan confirmed only 2 of 316 were held. WHAT THIS NEEDS IS A DECISION, NOT A DISCOVERY: either a desk-side janitor with that 24h+no-holder rule (cheap, and the rule is already validated by today's reclaim), or an accepted recurring manual reclaim, or a harness-level retention setting if one exists. Left unfixed the fence will re-fire on a schedule set by agent-session volume, and the failure mode is the R0407 loop: low memory makes an OOM kill likelier, the kill orphans more scratch, the next run starts poorer.",
+   "roi_bps": 5.0,
+   "raised": "2026-08-13T09:37:13.822328+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
```


---

## 083ac2dc R0460: the lead-lag standing rule, wired where a future proposal actually meets it
THE ASK was "one paragraph into the validation lane's checklist". There is no such
checklist in the repo, and the desk's own lesson says why building one would have
been theatre: A CHECKLIST THAT FIRES ON RECALL IS NOT A CONTROL -- the adversarial
review rubric sat with ONE repo reference and was injected nowhere until it was
wired. So the rule went where proposals are actually screened: research memory ->
build_graveyard_priors -> data/graveyard_priors.json -> the novelty gate every new
hypothesis must clear.

THE RULE. Any cross-venue lead-lag or information-share construction must run on
RAW TRADES with own-clock provenance from the desk recorder -- never on mark or
index series -- and must address sampling synchronisation (Epps) explicitly.

TWO INDEPENDENT KILLS, and the desk's own is load-bearing:
  (1) MEASURED HERE (R0117): cross-venue quote lead-lag at own synchronised L2
      timestamps died on sampling-phase aliasing -- pollers at 8.28s and 4.32s
      share no trigger and the aliasing envelope EXCEEDS the sub-minute effect
      hunted (L1.46).
  (2) IDENTIFICATION: a perp mark is by construction f(index of peer venues), so
      two venues' marks share inputs and an estimator on them recovers the shared
      oracle construction rather than price discovery -- power equal to size.

THE CITATION IS MARKED ABSTRACT-GRADE AND UNVERIFIED BEYOND THE ABSTRACT
(arXiv:2608.09188, as recorded in docs/research/deep_sweep/20260812_litminer_arxiv.md),
because this desk has a shipped FABRICATED-CITATION finding and WebFetch on arXiv
PDFs is on record as silently fabricating numbers. The mechanism leg above is
verifiable from desk knowledge and the R0117 leg is our own measurement, so the
rule does not rest on the paper.

THE RULE IS LIVE, NOT HYPOTHETICAL: the desk already records Bybit markPrice
(run_recorder_bybit.py:223) and reads Binance premiumIndex marks
(crypto_source.py:178, binance_live.mark_prices), so the inadmissible series are
sitting in its own tapes and are the CONVENIENT ones to reach for.

VERIFIED WIRED, not assumed: probing the gate with the exact class this pre-kills
("cross-venue lead-lag on Binance and Bybit mark price series... information-share
estimators") returns this row as the NEAREST prior and surfaces its lesson.
Similarity 0.40 is below the 0.7 redundant threshold, so it SURFACES rather than
auto-rejects -- which is correct: the rule constrains the CONSTRUCTION, not the
question, and the same question run on raw trades is admissible. Reporting that
distinction rather than claiming a hard kill.

data/ is gitignored, so the row lives in the tracked backups/moat mirror --
refreshed here and verified to contain the row. Uncommitted output did not happen.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 083ac2dc92c149f3ac6c2ac7d3b7c45d352e4e1c
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:35:26 2026 +0000

    R0460: the lead-lag standing rule, wired where a future proposal actually meets it
    
    THE ASK was "one paragraph into the validation lane's checklist". There is no such
    checklist in the repo, and the desk's own lesson says why building one would have
    been theatre: A CHECKLIST THAT FIRES ON RECALL IS NOT A CONTROL -- the adversarial
    review rubric sat with ONE repo reference and was injected nowhere until it was
    wired. So the rule went where proposals are actually screened: research memory ->
    build_graveyard_priors -> data/graveyard_priors.json -> the novelty gate every new
    hypothesis must clear.
    
    THE RULE. Any cross-venue lead-lag or information-share construction must run on
    RAW TRADES with own-clock provenance from the desk recorder -- never on mark or
    index series -- and must address sampling synchronisation (Epps) explicitly.
    
    TWO INDEPENDENT KILLS, and the desk's own is load-bearing:
      (1) MEASURED HERE (R0117): cross-venue quote lead-lag at own synchronised L2
          timestamps died on sampling-phase aliasing -- pollers at 8.28s and 4.32s
          share no trigger and the aliasing envelope EXCEEDS the sub-minute effect
          hunted (L1.46).
      (2) IDENTIFICATION: a perp mark is by construction f(index of peer venues), so
          two venues' marks share inputs and an estimator on them recovers the shared
          oracle construction rather than price discovery -- power equal to size.
    
    THE CITATION IS MARKED ABSTRACT-GRADE AND UNVERIFIED BEYOND THE ABSTRACT
    (arXiv:2608.09188, as recorded in docs/research/deep_sweep/20260812_litminer_arxiv.md),
    because this desk has a shipped FABRICATED-CITATION finding and WebFetch on arXiv
    PDFs is on record as silently fabricating numbers. The mechanism leg above is
    verifiable from desk knowledge and the R0117 leg is our own measurement, so the
    rule does not rest on the paper.
    
    THE RULE IS LIVE, NOT HYPOTHETICAL: the desk already records Bybit markPrice
    (run_recorder_bybit.py:223) and reads Binance premiumIndex marks
    (crypto_source.py:178, binance_live.mark_prices), so the inadmissible series are
    sitting in its own tapes and are the CONVENIENT ones to reach for.
    
    VERIFIED WIRED, not assumed: probing the gate with the exact class this pre-kills
    ("cross-venue lead-lag on Binance and Bybit mark price series... information-share
    estimators") returns this row as the NEAREST prior and surfaces its lesson.
    Similarity 0.40 is below the 0.7 redundant threshold, so it SURFACES rather than
    auto-rejects -- which is correct: the rule constrains the CONSTRUCTION, not the
    question, and the same question run on raw trades is admissible. Reporting that
    distinction rather than claiming a hard kill.
    
    data/ is gitignored, so the row lives in the tracked backups/moat mirror --
    refreshed here and verified to contain the row. Uncommitted output did not happen.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 backups/moat/alpha_registry |  Bin 585728 -> 598016 bytes
 backups/moat/cost_model     | 1186 +++++++++++++++++++++----------------------
 backups/moat/graveyard      |  431 ++++++++++++++++
 backups/moat/sor_research   |  Bin 46465024 -> 52285440 bytes
 4 files changed, 1024 insertions(+), 593 deletions(-)

diff --git a/backups/moat/alpha_registry b/backups/moat/alpha_registry
index b6d4681c..c017bbfc 100644
Binary files a/backups/moat/alpha_registry and b/backups/moat/alpha_registry differ
diff --git a/backups/moat/cost_model b/backups/moat/cost_model
index d3db2c4c..b22dc5e9 100644
--- a/backups/moat/cost_model
+++ b/backups/moat/cost_model
@@ -189,92 +189,92 @@
   "ADAUSDT": {
    "spot_buy": {
     "100": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 2.891,
-     "p90_bps": 3.08
+     "median_bps": 2.876,
+     "p90_bps": 3.076
     },
     "250": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 2.891,
+     "median_bps": 2.879,
      "p90_bps": 3.08
     },
     "500": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 2.898,
-     "p90_bps": 3.089
+     "median_bps": 2.883,
+     "p90_bps": 3.084
     },
     "1000": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 2.911,
-     "p90_bps": 3.11
+     "median_bps": 2.891,
+     "p90_bps": 3.097
     },
     "2500": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 2.954,
-     "p90_bps": 3.811
+     "median_bps": 2.939,
+     "p90_bps": 3.766
     }
    },
    "fut_sell": {
     "100": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.892,
-     "p90_bps": 3.082
+     "median_bps": 2.879,
+     "p90_bps": 3.08
     },
     "250": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.892,
-     "p90_bps": 3.082
+     "median_bps": 2.879,
+     "p90_bps": 3.08
     },
     "500": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.892,
-     "p90_bps": 3.082
+     "median_bps": 2.879,
+     "p90_bps": 3.08
     },
     "1000": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.892,
-     "p90_bps": 3.082
+     "median_bps": 2.879,
+     "p90_bps": 3.08
     },
     "2500": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.893,
+     "median_bps": 2.88,
      "p90_bps": 3.082
     }
    },
    "pair": {
     "100": {
-     "pair_open_bps": 5.783,
-     "pair_roundtrip_bps": 11.566,
+     "pair_open_bps": 5.755,
+     "pair_roundtrip_bps": 11.51,
      "worst_exhausted_frac": 0.0
     },
     "250": {
-     "pair_open_bps": 5.783,
-     "pair_roundtrip_bps": 11.566,
+     "pair_open_bps": 5.758,
+     "pair_roundtrip_bps": 11.516,
      "worst_exhausted_frac": 0.0
     },
     "500": {
-     "pair_open_bps": 5.79,
-     "pair_roundtrip_bps": 11.58,
+     "pair_open_bps": 5.762,
+     "pair_roundtrip_bps": 11.524,
      "worst_exhausted_frac": 0.0
     },
     "1000": {
-     "pair_open_bps": 5.803,
-     "pair_roundtrip_bps": 11.606,
+     "pair_open_bps": 5.77,
+     "pair_roundtrip_bps": 11.54,
      "worst_exhausted_frac": 0.0
     },
     "2500": {
-     "pair_open_bps": 5.847,
-     "pair_roundtrip_bps": 11.694,
+     "pair_open_bps": 5.819,
+     "pair_roundtrip_bps": 11.638,
      "worst_exhausted_frac": 0.0
     }
    }
@@ -375,92 +375,92 @@
   "APTUSDT": {
    "spot_buy": {
     "100": {
-     "n": 440,
+     "n": 464,
      "exhausted_frac": 0.0,
-     "median_bps": 8.425,
-     "p90_bps": 8.811
+     "median_bps": 8.439,
+     "p90_bps": 8.842
     },
     "250": {
-     "n": 440,
+     "n": 464,
      "exhausted_frac": 0.0,
-     "median_bps": 8.425,
-     "p90_bps": 8.826
+     "median_bps": 8.439,
+     "p90_bps": 8.842
     },
     "500": {
-     "n": 440,
+     "n": 464,
      "exhausted_frac": 0.0,
-     "median_bps": 8.425,
-     "p90_bps": 8.826
+     "median_bps": 8.439,
+     "p90_bps": 8.842
     },
     "1000": {
-     "n": 440,
+     "n": 464,
      "exhausted_frac": 0.0,
-     "median_bps": 8.425,
-     "p90_bps": 8.842
+     "median_bps": 8.439,
+     "p90_bps": 8.873
     },
     "2500": {
-     "n": 440,
+     "n": 464,
      "exhausted_frac": 0.0,
-     "median_bps": 8.439,
+     "median_bps": 8.453,
      "p90_bps": 8.937
     }
    },
    "fut_sell": {
     "100": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.845,
+     "median_bps": 0.847,
      "p90_bps": 0.894
     },
     "250": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.85,
+     "median_bps": 0.851,
      "p90_bps": 1.545
     },
     "500": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.862,
+     "median_bps": 0.868,
      "p90_bps": 2.006
     },
     "1000": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 1.213,
-     "p90_bps": 2.283
+     "median_bps": 1.257,
+     "p90_bps": 2.292
     },
     "2500": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 2.084,
-     "p90_bps": 3.191
+     "median_bps": 2.12,
+     "p90_bps": 3.231
     }
    },
    "pair": {
     "100": {
-     "pair_open_bps": 9.27,
-     "pair_roundtrip_bps": 18.54,
+     "pair_open_bps": 9.286,
+     "pair_roundtrip_bps": 18.572,
      "worst_exhausted_frac": 0.0
     },
     "250": {
-     "pair_open_bps": 9.275,
-     "pair_roundtrip_bps": 18.55,
+     "pair_open_bps": 9.29,
+     "pair_roundtrip_bps": 18.58,
      "worst_exhausted_frac": 0.0
     },
     "500": {
-     "pair_open_bps": 9.287,
-     "pair_roundtrip_bps": 18.574,
+     "pair_open_bps": 9.307,
+     "pair_roundtrip_bps": 18.614,
      "worst_exhausted_frac": 0.0
     },
     "1000": {
-     "pair_open_bps": 9.638,
-     "pair_roundtrip_bps": 19.276,
+     "pair_open_bps": 9.696,
+     "pair_roundtrip_bps": 19.392,
      "worst_exhausted_frac": 0.0
     },
     "2500": {
-     "pair_open_bps": 10.523,
-     "pair_roundtrip_bps": 21.046,
+     "pair_open_bps": 10.573,
+     "pair_roundtrip_bps": 21.146,
      "worst_exhausted_frac": 0.0
     }
    }
@@ -468,92 +468,92 @@
   "ARBUSDT": {
    "spot_buy": {
     "100": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 6.27,
+     "median_bps": 6.285,
      "p90_bps": 6.439
     },
     "250": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 6.27,
+     "median_bps": 6.285,
      "p90_bps": 6.439
     },
     "500": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 6.27,
+     "median_bps": 6.285,
      "p90_bps": 6.439
     },
     "1000": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 6.277,
-     "p90_bps": 6.447
+     "median_bps": 6.285,
+     "p90_bps": 6.456
     },
     "2500": {
-     "n": 441,
+     "n": 465,
      "exhausted_frac": 0.0,
-     "median_bps": 6.325,
-     "p90_bps": 8.323
+     "median_bps": 6.333,
+     "p90_bps": 8.274
     }
    },
    "fut_sell": {
     "100": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.632,
-     "p90_bps": 0.661
+     "median_bps": 0.633,
+     "p90_bps": 0.675
     },
     "250": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.636,
+     "median_bps": 0.637,
      "p90_bps": 1.415
     },
     "500": {
-     "n": 442,
+     "n": 466,
      "exhausted_frac": 0.0,
-     "median_bps": 0.641,
-     "p90_bps": 1.675
+     "median_bps": 0.642,
+     "p90_bps": 1.695
     },
     "1000": {
-     "n": 442,
```


---

## 1e61e63a R0431: the horizon was not the fix -- the absorption MODEL is, and the sweep refutes the caveat
R0266's study published its own caveat and could not test it: modelling absorption
as the account FREEZING at the barrier floors terminal log-wealth at log(barrier)
while the upside stays unbounded, so mu-dispersion pays like a call option and
pushed f*_joint ABOVE full Kelly (1.05-3.00). The caveat claimed that was an
artifact of the ONE-YEAR horizon which a lifetime horizon would dissolve. R0431
asked for the multi-year run that would confirm it.

MEASURED OVER 1y/3y/10y AT THE DESK'S REAL BARRIER: the excess RISES.
  mean f*joint/f*abs   365d=2.07  1095d=2.29  3650d=2.50   (REFUTED)
THE MECHANISM: freezing floors terminal log-wealth at log(barrier) FOREVER while
surviving paths compound roughly linearly in T, so the gap the floor insures
against GROWS with the horizon and the call option becomes MORE valuable, not
less. Testing the row's actual claim needs the alternative it names in its own
parenthesis -- an explicit continuation value for the non-absorbed state -- so
that absorption forfeits the compounding the capital would otherwise have earned
rather than settling at log(0.2). f*_joint remains NOT EVIDENCE either way.

AND THE HALF THAT BEARS ON SIZING MOVED, which the row predicted was negligible.
gamma_boundary is never clipped and FALLS with the horizon exactly as theory says:
0.950 at 1y -> 0.817 at 10y. The base study's "<=10%" boundary shrink is a 1-YEAR
number and this desk's objective is lifetime E[log W_T], so the lifetime figure is
~15-20%, roughly double. The conclusion still holds -- the estimation shrink runs
0.058-0.721 in the same cells and continues to dominate, and _ruin_cap already
binds the same barrier from the constraint side -- but the margin is smaller than
the artifact previously stated. NOTHING HERE CHANGES A RAIL, A BAR OR A SIZER.

THE VERDICT IS BUILT FROM UNCLIPPED CELLS ONLY and publishes its denominator
(6/9 usable): f*_joint pins at the 3.00 grid edge in every S=0.75 cell, so its
ratio there is a LOWER BOUND, not a measurement, and averaging it in would let a
censored number drive the conclusion (L1.57). Scope is named, not silently capped:
the 0.50 barrier is a $100-book case the desk does not trade and 180d evidence has
a smaller artifact to dissolve.

A REAL DEFECT SURFACED ON THE WAY, AND THE SWEEP IS WHAT REACHED IT. `_argmax_f`
scored by log(cumprod(steps)); at 3,650 steps the no-barrier arm underflows to
EXACTLY 0.0, and log(0.0) is -inf -- not "very bad" but INFINITELY bad -- so ONE
underflowing path in 8,000 set that leverage's whole score to -inf and DELETED it
from the argmax for an arithmetic reason rather than an economic one. Measured at
seed 11: 0/64 paths at 365 and 1,095 days, 7/64 at 3,650. It was invisible because
the corruption lands on high-f grid points in an arm whose optimum sits at ~1.0x,
so it moved no published number and announced itself only as a RuntimeWarning
nobody reads. Fixed by summing logs (identical, cannot underflow); the absorbing
arm keeps cumprod and is provably immune, so gamma_boundary is unchanged bit for
bit. Three regressions pin it, one asserting the legacy arithmetic genuinely
breaks in that cell so the guard cannot lose its teeth.

Chunked the path draws (~64MB whatever the horizon): a 10y run at 8,000 paths is
~470MB across two arrays on a box whose OOM floor is 400MB free. Common random
numbers survive chunking -- every f is evaluated on the same chunk before the next
is drawn -- and at 365 days the 1y cells draw exactly the arrays they drew before,
so their numbers are unchanged.

Re-ran end to end before committing; the artifact is the current code's output.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 1e61e63a5896d08e1152a661e2147b87763e1d8e
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:32:38 2026 +0000

    R0431: the horizon was not the fix -- the absorption MODEL is, and the sweep refutes the caveat
    
    R0266's study published its own caveat and could not test it: modelling absorption
    as the account FREEZING at the barrier floors terminal log-wealth at log(barrier)
    while the upside stays unbounded, so mu-dispersion pays like a call option and
    pushed f*_joint ABOVE full Kelly (1.05-3.00). The caveat claimed that was an
    artifact of the ONE-YEAR horizon which a lifetime horizon would dissolve. R0431
    asked for the multi-year run that would confirm it.
    
    MEASURED OVER 1y/3y/10y AT THE DESK'S REAL BARRIER: the excess RISES.
      mean f*joint/f*abs   365d=2.07  1095d=2.29  3650d=2.50   (REFUTED)
    THE MECHANISM: freezing floors terminal log-wealth at log(barrier) FOREVER while
    surviving paths compound roughly linearly in T, so the gap the floor insures
    against GROWS with the horizon and the call option becomes MORE valuable, not
    less. Testing the row's actual claim needs the alternative it names in its own
    parenthesis -- an explicit continuation value for the non-absorbed state -- so
    that absorption forfeits the compounding the capital would otherwise have earned
    rather than settling at log(0.2). f*_joint remains NOT EVIDENCE either way.
    
    AND THE HALF THAT BEARS ON SIZING MOVED, which the row predicted was negligible.
    gamma_boundary is never clipped and FALLS with the horizon exactly as theory says:
    0.950 at 1y -> 0.817 at 10y. The base study's "<=10%" boundary shrink is a 1-YEAR
    number and this desk's objective is lifetime E[log W_T], so the lifetime figure is
    ~15-20%, roughly double. The conclusion still holds -- the estimation shrink runs
    0.058-0.721 in the same cells and continues to dominate, and _ruin_cap already
    binds the same barrier from the constraint side -- but the margin is smaller than
    the artifact previously stated. NOTHING HERE CHANGES A RAIL, A BAR OR A SIZER.
    
    THE VERDICT IS BUILT FROM UNCLIPPED CELLS ONLY and publishes its denominator
    (6/9 usable): f*_joint pins at the 3.00 grid edge in every S=0.75 cell, so its
    ratio there is a LOWER BOUND, not a measurement, and averaging it in would let a
    censored number drive the conclusion (L1.57). Scope is named, not silently capped:
    the 0.50 barrier is a $100-book case the desk does not trade and 180d evidence has
    a smaller artifact to dissolve.
    
    A REAL DEFECT SURFACED ON THE WAY, AND THE SWEEP IS WHAT REACHED IT. `_argmax_f`
    scored by log(cumprod(steps)); at 3,650 steps the no-barrier arm underflows to
    EXACTLY 0.0, and log(0.0) is -inf -- not "very bad" but INFINITELY bad -- so ONE
    underflowing path in 8,000 set that leverage's whole score to -inf and DELETED it
    from the argmax for an arithmetic reason rather than an economic one. Measured at
    seed 11: 0/64 paths at 365 and 1,095 days, 7/64 at 3,650. It was invisible because
    the corruption lands on high-f grid points in an arm whose optimum sits at ~1.0x,
    so it moved no published number and announced itself only as a RuntimeWarning
    nobody reads. Fixed by summing logs (identical, cannot underflow); the absorbing
    arm keeps cumprod and is provably immune, so gamma_boundary is unchanged bit for
    bit. Three regressions pin it, one asserting the legacy arithmetic genuinely
    breaks in that cell so the guard cannot lose its teeth.
    
    Chunked the path draws (~64MB whatever the horizon): a 10y run at 8,000 paths is
    ~470MB across two arrays on a box whose OOM floor is 400MB free. Common random
    numbers survive chunking -- every f is evaluated on the same chunk before the next
    is drawn -- and at 365 days the 1y cells draw exactly the arrays they drew before,
    so their numbers are unchanged.
    
    Re-ran end to end before committing; the artifact is the current code's output.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/absorbing_kelly_study.json        | 269 ++++++++++++++++++++++++
 scripts/study_absorbing_kelly.py                | 238 ++++++++++++++++++---
 tests/research/test_absorbing_kelly_numerics.py | 111 ++++++++++
 3 files changed, 588 insertions(+), 30 deletions(-)

diff --git a/docs/research/absorbing_kelly_study.json b/docs/research/absorbing_kelly_study.json
index 322d1981..f512e3d4 100644
--- a/docs/research/absorbing_kelly_study.json
+++ b/docs/research/absorbing_kelly_study.json
@@ -4,6 +4,263 @@
  "status": "MEASURED",
  "n_paths": 8000,
  "horizon_days": 365,
+ "r0431_horizon_sweep": {
+  "row": "R0431",
+  "question": "is f*_joint > 1 an artifact of the ONE-YEAR horizon, as the base study's own caveat claims? Over a lifetime absorption forfeits ALL future compounding rather than settling at 0.2x book, so the excess should fall as the horizon grows",
+  "horizons_days": [
+   365,
+   1095,
+   3650
+  ],
+  "barrier_frac_of_book": 0.2,
+  "evidence_width_days": 40.0,
+  "scope_note": "run at the desk's REAL barrier and the SHORT evidence width only -- the 0.50 barrier is a $100-book case the desk does not trade and 180d evidence has a smaller artifact to dissolve. Dropped deliberately and named here rather than silently capped",
+  "n_cells": 9,
+  "n_cells_usable_for_verdict": 6,
+  "n_cells_dropped_grid_edge": 3,
+  "positive_control_passed": "9/9",
+  "mean_joint_over_absorbing_by_horizon": {
+   "365": 2.0731,
+   "1095": 2.2941,
+   "3650": 2.5
+  },
+  "monotone_decreasing": false,
+  "verdict": "REFUTED (the excess RISES with horizon)",
+  "answer": "REFUTED. The base study's caveat claimed f*_joint > 1 is an artifact of the 1y horizon that a lifetime horizon would remove. Measured over 1y/3y/10y the excess RISES instead. THE MECHANISM: modelling absorption as FREEZING floors terminal log-wealth at log(barrier) FOREVER, while surviving paths compound roughly linearly in T -- so the gap the floor insures against GROWS with the horizon and the mu-dispersion call option becomes MORE valuable, not less. The horizon was never the fix; the ABSORPTION MODEL is. Testing the row's actual claim needs the alternative it names in its own parenthesis -- an explicit continuation value for the non-absorbed state, so that absorption forfeits the compounding the capital would otherwise have earned rather than settling at log(0.2). f*_joint remains NOT EVIDENCE either way, exactly as before.",
+  "gamma_boundary_by_horizon": {
+   "365": 0.95,
+   "1095": 0.8667,
+   "3650": 0.8167
+  },
+  "gamma_boundary_note": "THE HALF THAT ACTUALLY BEARS ON SIZING, and it moved. gamma_boundary is never clipped, and it FALLS with the horizon exactly as theory predicts: at the desk's real barrier it is ~0.95 at 1y but ~0.82 at 10y, so the boundary shrink over a LIFETIME is roughly 15-20%, about double the '<=10%' the base study measured at one year. The base study's headline figure is a 1-YEAR number and this desk's objective is lifetime E[log W_T]. The conclusion still holds -- the estimation shrink applies 0.058-0.721 in the same cells and continues to dominate, and _ruin_cap already binds the same barrier from the constraint side -- but the margin is smaller than the artifact previously stated.",
+  "cells": [
+   {
+    "sharpe_ann": 0.75,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 365,
+    "full_kelly_leverage": 1.963,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 1.0,
+    "f_star_joint": 3.0,
+    "f_star_uncertainty_only": 1.05,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": true,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 1.0,
+    "gamma_estimation": 0.058,
+    "composed_fraction": 0.058,
+    "composed_over_joint": 0.0193,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 0.28916,
+    "elogw_absorbing": 0.28787,
+    "elogw_joint": 1.59566,
+    "sharpe_se": 3.0219,
+    "joint_over_absorbing": 3.0
+   },
+   {
+    "sharpe_ann": 1.5,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 365,
+    "full_kelly_leverage": 3.926,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.95,
+    "f_star_joint": 2.25,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.95,
+    "gamma_estimation": 0.1973,
+    "composed_fraction": 0.1874,
+    "composed_over_joint": 0.0833,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 1.13727,
+    "elogw_absorbing": 1.09866,
+    "elogw_joint": 2.90034,
+    "sharpe_se": 3.0254,
+    "joint_over_absorbing": 2.3684
+   },
+   {
+    "sharpe_ann": 2.3,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 365,
+    "full_kelly_leverage": 6.019,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.9,
+    "f_star_joint": 1.6,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.9,
+    "gamma_estimation": 0.3653,
+    "composed_fraction": 0.3288,
+    "composed_over_joint": 0.2055,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 2.6485,
+    "elogw_absorbing": 2.47496,
+    "elogw_joint": 4.47125,
+    "sharpe_se": 3.0317,
+    "joint_over_absorbing": 1.7778
+   },
+   {
+    "sharpe_ann": 0.75,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 1095,
+    "full_kelly_leverage": 1.963,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.95,
+    "f_star_joint": 3.0,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": true,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.95,
+    "gamma_estimation": 0.058,
+    "composed_fraction": 0.0551,
+    "composed_over_joint": 0.0184,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 0.85647,
+    "elogw_absorbing": 0.83448,
+    "elogw_joint": 5.82851,
+    "sharpe_se": 3.0219,
+    "joint_over_absorbing": 3.1579
+   },
+   {
+    "sharpe_ann": 1.5,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 1095,
+    "full_kelly_leverage": 3.926,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.85,
+    "f_star_joint": 2.2,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.85,
+    "gamma_estimation": 0.1973,
+    "composed_fraction": 0.1677,
+    "composed_over_joint": 0.0762,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 3.39066,
+    "elogw_absorbing": 3.121,
+    "elogw_joint": 9.51948,
+    "sharpe_se": 3.0254,
+    "joint_over_absorbing": 2.5882
+   },
+   {
+    "sharpe_ann": 2.3,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 1095,
+    "full_kelly_leverage": 6.019,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.8,
+    "f_star_joint": 1.6,
+    "f_star_uncertainty_only": 0.95,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.8,
+    "gamma_estimation": 0.3653,
+    "composed_fraction": 0.2922,
+    "composed_over_joint": 0.1826,
+    "verdict": "BOUNDARY-SHRINK-MATERIAL",
+    "elogw_no_barrier": 7.91456,
+    "elogw_absorbing": 7.13677,
+    "elogw_joint": 13.9064,
+    "sharpe_se": 3.0317,
+    "joint_over_absorbing": 2.0
+   },
+   {
+    "sharpe_ann": 0.75,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 3650,
+    "full_kelly_leverage": 1.963,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.85,
+    "f_star_joint": 3.0,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": true,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.85,
+    "gamma_estimation": 0.058,
+    "composed_fraction": 0.0493,
+    "composed_over_joint": 0.0164,
+    "verdict": "BOUNDARY-SHRINK-REAL-BUT-SMALL",
+    "elogw_no_barrier": 2.80011,
+    "elogw_absorbing": 2.58733,
+    "elogw_joint": 20.99082,
+    "sharpe_se": 3.0219,
+    "joint_over_absorbing": 3.5294
+   },
+   {
+    "sharpe_ann": 1.5,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 3650,
+    "full_kelly_leverage": 3.926,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.8,
+    "f_star_joint": 2.35,
+    "f_star_uncertainty_only": 1.0,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.8,
+    "gamma_estimation": 0.1973,
+    "composed_fraction": 0.1578,
+    "composed_over_joint": 0.0672,
+    "verdict": "BOUNDARY-SHRINK-MATERIAL",
+    "elogw_no_barrier": 11.19331,
+    "elogw_absorbing": 9.96574,
+    "elogw_joint": 32.78553,
+    "sharpe_se": 3.0254,
+    "joint_over_absorbing": 2.9375
+   },
+   {
+    "sharpe_ann": 2.3,
+    "n_days": 40.0,
+    "barrier_frac_of_book": 0.2,
+    "horizon_days": 3650,
+    "full_kelly_leverage": 6.019,
+    "positive_control_ok": true,
+    "f_star_no_barrier": 1.0,
+    "f_star_absorbing": 0.8,
+    "f_star_joint": 1.65,
+    "f_star_uncertainty_only": 0.95,
+    "joint_cell_is_evidence": false,
+    "joint_cell_hit_grid_edge": false,
+    "joint_cell_note": "f_star_joint is NOT usable: freezing at the barrier floors terminal log-wealth at log(barrier) while the upside is unbounded, so mu dispersion pays like a call option and pushes the argmax above full Kelly. An artifact of the 1y horizon, which under-penalises absorption -- over a lifetime absorption forfeits all future compounding, not 0.8x of one year's book",
+    "gamma_boundary": 0.8,
+    "gamma_estimation": 0.3653,
+    "composed_fraction": 0.2922,
+    "composed_over_joint": 0.1771,
+    "verdict": "BOUNDARY-SHRINK-MATERIAL",
+    "elogw_no_barrier": 26.21598,
+    "elogw_absorbing": 23.25711,
+    "elogw_joint": 47.19051,
+    "sharpe_se": 3.0317,
+    "joint_over_absorbing": 2.0625
+   }
+  ]
+ },
  "barrier_note": "fraction of starting book at which the account can no longer execute economic round-trips at venue minimums ($200 viability floor / book)",
  "wired": false,
  "wired_note": "STUDY ONLY. No sizer, rail or bar is changed by this file.",
@@ -21,6 +278,7 @@
    "sharpe_ann": 0.75,
    "n_days": 40.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 1.963,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -44,6 +302,7 @@
    "sharpe_ann": 0.75,
    "n_days": 180.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 1.963,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -67,6 +326,7 @@
    "sharpe_ann": 1.5,
    "n_days": 40.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 3.926,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -90,6 +350,7 @@
    "sharpe_ann": 1.5,
    "n_days": 180.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 3.926,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -113,6 +374,7 @@
    "sharpe_ann": 2.3,
    "n_days": 40.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 6.019,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -136,6 +398,7 @@
    "sharpe_ann": 2.3,
    "n_days": 180.0,
    "barrier_frac_of_book": 0.2,
+   "horizon_days": 365,
    "full_kelly_leverage": 6.019,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -159,6 +422,7 @@
    "sharpe_ann": 0.75,
    "n_days": 40.0,
    "barrier_frac_of_book": 0.5,
+   "horizon_days": 365,
    "full_kelly_leverage": 1.963,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -182,6 +446,7 @@
    "sharpe_ann": 0.75,
    "n_days": 180.0,
    "barrier_frac_of_book": 0.5,
+   "horizon_days": 365,
    "full_kelly_leverage": 1.963,
    "positive_control_ok": true,
    "f_star_no_barrier": 1.0,
@@ -205,6 +470,7 @@
```


---

## 268c7f50 host-tmpfs-bloated: freed 423MB, and the fence now names the one producer it can
THE DEFECT AS HANDED: 684MB of tmpfs against a 600MB ceiling, MemAvailable 521MB.
Measured at pickup it had grown to 838MB with 747MB available.

RECLAIMED 838MB -> 415MB (MemAvailable 747 -> 1346MB), both by ownership evidence
and never blind:
  * 255 dead agent-session scratch dirs under /tmp/claude-1000 (179MB), every one
    >=24h old with no live holder. Cron seats run under `timeout 3000`, so a dir
    untouched for 24h cannot belong to a live session. The two live holders were
    identified by fd/cwd scan and skipped.
  * /tmp/wt-head (150MB) -- a worktree THIS REPO registered at 02:55 and abandoned,
    detached at a committed sha, no holder, its one dirty file a regenerated
    forensics artifact identical in kind to the main tree's. Removed via
    `git worktree remove` + prune, not rm -rf.

THE RECURRENCE, WHICH IS THE ACTUAL DEFECT. The note closes by telling the reader
that "age plus a known producer is the evidence to act on" and then supplies no
producer. Establishing that /tmp/wt-head was the desk's own took `git worktree
list`, a read of its .git pointer, a diff of its dirty artifact and a holder scan
-- four commands, done by hand, at the moment the box is short of memory. The
fence had already computed the size, the age and the holder and stopped one fact
short of the one that decides the deletion.

A registered worktree is ownership evidence a bare directory under a shared /tmp
does not carry: it is a checkout of a committed sha of this repo, and `git
worktree remove` refuses a dirty tree by itself, so the named command is the plain
one and never --force.

THE FENCE STILL DELETES NOTHING, deliberately and for the recorded reason: an
agent session's `git worktree add` (which CLAUDE.md prefers over `git stash`)
holds no descriptor while the model is thinking, so "no holder" cannot separate an
abandoned checkout from one between commands. Age plus ownership is evidence for a
human decision, not a licence to automate one.

Matching is by CONTAINMENT, not equality -- a lawgate checkout registers at
<entry>/t while the entry is what holds the RAM, so equality would silently
attribute nothing for the desk's most frequent producer. The attribution sentence
is conditional: printed unconditionally it appears on firings where nothing is
reclaimable, and its presence is the signal.

Fence verified GREEN on the live box after the reclaim. Four tests, one of which
runs against real git to prove the main checkout is never offered for reclaim.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 268c7f503986b3996ce7559a6b519d36d55f5a64
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:29:43 2026 +0000

    host-tmpfs-bloated: freed 423MB, and the fence now names the one producer it can
    
    THE DEFECT AS HANDED: 684MB of tmpfs against a 600MB ceiling, MemAvailable 521MB.
    Measured at pickup it had grown to 838MB with 747MB available.
    
    RECLAIMED 838MB -> 415MB (MemAvailable 747 -> 1346MB), both by ownership evidence
    and never blind:
      * 255 dead agent-session scratch dirs under /tmp/claude-1000 (179MB), every one
        >=24h old with no live holder. Cron seats run under `timeout 3000`, so a dir
        untouched for 24h cannot belong to a live session. The two live holders were
        identified by fd/cwd scan and skipped.
      * /tmp/wt-head (150MB) -- a worktree THIS REPO registered at 02:55 and abandoned,
        detached at a committed sha, no holder, its one dirty file a regenerated
        forensics artifact identical in kind to the main tree's. Removed via
        `git worktree remove` + prune, not rm -rf.
    
    THE RECURRENCE, WHICH IS THE ACTUAL DEFECT. The note closes by telling the reader
    that "age plus a known producer is the evidence to act on" and then supplies no
    producer. Establishing that /tmp/wt-head was the desk's own took `git worktree
    list`, a read of its .git pointer, a diff of its dirty artifact and a holder scan
    -- four commands, done by hand, at the moment the box is short of memory. The
    fence had already computed the size, the age and the holder and stopped one fact
    short of the one that decides the deletion.
    
    A registered worktree is ownership evidence a bare directory under a shared /tmp
    does not carry: it is a checkout of a committed sha of this repo, and `git
    worktree remove` refuses a dirty tree by itself, so the named command is the plain
    one and never --force.
    
    THE FENCE STILL DELETES NOTHING, deliberately and for the recorded reason: an
    agent session's `git worktree add` (which CLAUDE.md prefers over `git stash`)
    holds no descriptor while the model is thinking, so "no holder" cannot separate an
    abandoned checkout from one between commands. Age plus ownership is evidence for a
    human decision, not a licence to automate one.
    
    Matching is by CONTAINMENT, not equality -- a lawgate checkout registers at
    <entry>/t while the entry is what holds the RAM, so equality would silently
    attribute nothing for the desk's most frequent producer. The attribution sentence
    is conditional: printed unconditionally it appears on firings where nothing is
    reclaimable, and its presence is the signal.
    
    Fence verified GREEN on the live box after the reclaim. Four tests, one of which
    runs against real git to prove the main checkout is never offered for reclaim.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 scripts/max_audit.py                   | 72 +++++++++++++++++++++++++++++++++-
 tests/scripts/test_max_audit_checks.py | 57 +++++++++++++++++++++++++++
 2 files changed, 127 insertions(+), 2 deletions(-)

diff --git a/scripts/max_audit.py b/scripts/max_audit.py
index f7aeb744..14b5daf1 100755
--- a/scripts/max_audit.py
+++ b/scripts/max_audit.py
@@ -3804,6 +3804,54 @@ def check_host_memory_headroom(defects) -> None:
             f"{_tmpfs_holders_note()} {where}."))
 
 
+def _desk_owned_worktrees() -> dict[str, str]:
+    """Realpath -> registered path, for THIS repo's own git worktrees living outside the repo.
+
+    THE ONE PRODUCER THE NOTE ASKS FOR AND NEVER SUPPLIED. `_tmpfs_holders_note` closes by
+    telling the reader that "age plus a known producer is the evidence to act on" -- and then
+    names no producer, so the reader has to establish ownership by hand at the exact moment the
+    box is short of memory. Measured 2026-08-13: /tmp held 838MB against a 600MB ceiling, and
+    150MB of it was a detached checkout at /tmp/wt-head that THIS REPO had registered 6.5h
+    earlier and abandoned. Establishing that took `git worktree list`, a read of the entry's
+    `.git` pointer, a diff of its one dirty artifact against the main tree, and a holder scan.
+    The fence had already computed the size, the age and the holder, and stopped one fact short
+    of the one that actually decides the deletion.
+
+    A REGISTERED WORKTREE IS OWNERSHIP EVIDENCE, which is precisely what a bare directory under
+    a shared /tmp does not carry. It is a checkout of a COMMITTED sha of this repo, so reclaiming
+    it destroys no unique work unless the tree is dirty -- and `git worktree remove` refuses a
+    dirty tree by itself, which is why the command named below is the plain one and never
+    `--force`. The reader who needs `--force` is then making that call knowingly.
+
+    THE FENCE STILL DELETES NOTHING. Naming a reclaimable entry and reaping it are different
+    acts, and only the second can race a live sibling: an agent session's `git worktree add`
+    (which CLAUDE.md itself instructs, in preference to `git stash`) holds no descriptor while
+    the model is thinking, so "no holder" cannot distinguish an abandoned checkout from one
+    between commands. Age plus ownership is evidence for a HUMAN decision, not a licence to
+    automate one -- the same reason `libs/ops/host_resources` reports and does not reap.
+
+    Best-effort: a repo without git, or a git that errors, yields no attribution and the note
+    degrades to exactly what it printed before.
+    """
+    try:
+        r = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=ROOT,
+                           capture_output=True, text=True, timeout=30, check=False)
+    except (OSError, subprocess.SubprocessError):
+        return {}
+    if r.returncode != 0:
+        return {}
+    main = os.path.realpath(str(ROOT))
+    owned: dict[str, str] = {}
+    for line in r.stdout.splitlines():
+        if not line.startswith("worktree "):
+            continue
+        p = line.split(" ", 1)[1].strip()
+        rp = os.path.realpath(p)
+        if rp != main:                      # the main checkout is the desk, not its scratch
+            owned[rp] = p
+    return owned
+
+
 def _tmpfs_holders_note() -> str:
     """The largest /tmp entries with the one fact that makes freeing them a safe decision.
 
@@ -3824,14 +3872,34 @@ def _tmpfs_holders_note() -> str:
         return ""
     readable, total = fd_scan_coverage()
     seen = f"{readable}/{total} pids' descriptors readable" if total else "no pid table readable"
+    owned = _desk_owned_worktrees()
     parts = []
+    n_owned = 0
     for r in rows:
         holder = ("HELD by a live process" if r.held
                   else "held by nothing" if r.held is False else "holder UNKNOWN")
-        parts.append(f"{r.path} {r.mb}MB {r.age_h:.0f}h {holder}")
+        # A lawgate checkout registers at <entry>/t while the entry itself is what holds the RAM,
+        # so ownership is matched by CONTAINMENT, not equality: the reclaim command has to name
+        # the registered path and the size next to it is the whole subtree's.
+        target = os.path.realpath(r.path).rstrip("/")
+        mine = [reg for rp, reg in sorted(owned.items())
+                if rp == target or rp.startswith(target + "/")]
+        own = ""
+        if mine:
+            n_owned += 1
+            own = f" DESK-OWNED git worktree -- reclaim: git worktree remove {mine[0]}"
+        parts.append(f"{r.path} {r.mb}MB {r.age_h:.0f}h {holder}{own}")
+    # THE ATTRIBUTION SENTENCE IS CONDITIONAL, and that is not cosmetic. Printed unconditionally
+    # it appears on every firing including the ones where nothing is reclaimable, so the reader
+    # cannot tell from the message whether the desk owns any of the pile -- which is the single
+    # question it was added to answer. Its presence IS the signal.
+    tail = ("" if not n_owned else
+            f" {n_owned} of these are DESK-OWNED: this repo registered them, each is a checkout "
+            f"of a committed sha, and `git worktree remove` refuses one whose tree is dirty -- "
+            f"the one class the reader can free without first reconstructing where it came from.")
     return (f"Largest entries: {'; '.join(parts)}. Holder scan saw {seen}, so 'holder UNKNOWN' "
             f"means NOT CHECKABLE from here, never 'safe to delete' -- age plus a known producer "
-            f"is the evidence to act on.")
+            f"is the evidence to act on.{tail}")
 
 
 def check_test_suite_collectable(defects) -> None:
diff --git a/tests/scripts/test_max_audit_checks.py b/tests/scripts/test_max_audit_checks.py
index 03a6ede0..e68ecc1b 100644
--- a/tests/scripts/test_max_audit_checks.py
+++ b/tests/scripts/test_max_audit_checks.py
@@ -443,3 +443,60 @@ class TestHostMemoryHeadroom:
         m.check_host_memory_headroom(defects)
         assert [k for k, _ in defects] == ["host-memory-low"]
         assert "not a tmpfs" in dict(defects)["host-memory-low"]
+
+
+class TestTmpfsHoldersNameTheirProducer:
+    """The note told the reader that "age plus a known producer is the evidence to act on" and
+    then named no producer. Measured 2026-08-13: 150MB of the 838MB pile was a worktree THIS repo
+    had registered and abandoned, and proving that took four commands under memory pressure.
+    """
+
+    @staticmethod
+    def _rows(monkeypatch, entries) -> None:
+        import libs.ops.host_resources as hr
+
+        monkeypatch.setattr(hr, "tmpfs_top_holders", lambda *a, **k: entries)
+        monkeypatch.setattr(hr, "fd_scan_coverage", lambda *a, **k: (42, 175))
+
+    def test_a_desk_owned_worktree_carries_its_reclaim_command(self, monkeypatch) -> None:
+        """THE DISCRIMINATING ASSERTION: size, age and holder were all already printed, so a test
+        on those would pass against the old note. What was missing is WHOSE it is."""
+        from libs.ops.host_resources import TmpEntry
+
+        self._rows(monkeypatch, [TmpEntry(path="/tmp/wt-head", mb=150, age_h=6.5, held=False)])
+        monkeypatch.setattr(m, "_desk_owned_worktrees", lambda: {"/tmp/wt-head": "/tmp/wt-head"})
+        note = m._tmpfs_holders_note()
+        assert "DESK-OWNED" in note, note
+        assert "git worktree remove /tmp/wt-head" in note, note
+        assert "--force" not in note, "a dirty worktree must refuse, not be forced blind"
+
+    def test_ownership_matches_by_containment_not_equality(self, monkeypatch) -> None:
+        """A lawgate checkout registers at <entry>/t while the ENTRY is what holds the RAM. Equality
+        matching would silently attribute nothing for the desk's most frequent producer."""
+        from libs.ops.host_resources import TmpEntry
+
+        self._rows(monkeypatch, [TmpEntry(path="/tmp/lawgate-head-ab", mb=150, age_h=3.0,
+                                          held=None)])
+        monkeypatch.setattr(m, "_desk_owned_worktrees",
+                            lambda: {"/tmp/lawgate-head-ab/t": "/tmp/lawgate-head-ab/t"})
+        note = m._tmpfs_holders_note()
+        assert "git worktree remove /tmp/lawgate-head-ab/t" in note, note
+
+    def test_an_unowned_entry_is_not_claimed(self, monkeypatch) -> None:
+        """The failure that would matter: attributing a sibling's scratch to the desk invites the
+        reader to delete something this repo never allocated."""
+        from libs.ops.host_resources import TmpEntry
+
+        self._rows(monkeypatch, [TmpEntry(path="/tmp/somebody-else", mb=200, age_h=9.0,
+                                          held=None)])
+        monkeypatch.setattr(m, "_desk_owned_worktrees", lambda: {"/tmp/wt-head": "/tmp/wt-head"})
+        note = m._tmpfs_holders_note()
+        assert "DESK-OWNED" not in note, note
+        assert "holder UNKNOWN" in note, note
+
+    def test_the_main_checkout_is_never_offered_for_reclaim(self) -> None:
+        """Live, against real git: `git worktree list` names the repo itself first, and offering
+        `git worktree remove` on the desk's own checkout is the one attribution that must never
+        appear. Runs against the actual repo, so it also proves the parse works."""
+        owned = m._desk_owned_worktrees()
+        assert str(m.ROOT.resolve()) not in owned, owned
```


---

## 2020bba1 BRAIN hunter 08-13 s3: the desk imported BRAIN's thresholds and missed its ratios (OP-083/OP-084)
OP-083: brain_calibration.py was built from a WEBINAR TRANSCRIPT, which states THRESHOLDS.
rocky-d/wqb (MIT) is the platform's own API and states the MEASUREMENT NAMESPACE. Four BRAIN
metrics are dimensionless RATIOS of two like-measured quantities, so every convention difference
that module correctly warns about (annualisation, cost base, return definition, periodicity)
CANCELS -- os.osISSharpeRatio ABSENT, os.sharpe60/125/250/500 ABSENT, os.preCloseSharpe* PARTIAL
(phase_sensitivity covers funding binning, not decision-timestamp), is.prodCorrelation HALF (the
self-correlation cap was imported, the production half never was). The un-portable half was taken
and the portable half was never seen. Rule that generalises: a threshold is asset-class-bound and
does not travel; a ratio of two like-measured quantities is unit-free and travels intact.
-> R0601 (record forward evidence as a ratio and a ladder, in OBSERVATIONS not days per L1.48)
-> R0602 (candidate-vs-DEPLOYED correlation gate; cheapest while the denominator is 1)

OP-084: measured all 50 rows of a worked low-correlation portfolio -- 49 distinct data fields,
8 operator tokens, 48/50 single-operator expressions, median depth 1. Independence came from the
DATA, not the MATH, corroborating the desk's 129-mechanisms-all-price-derived-all-failed lesson
from a different market, institution and asset class. Re-ranks this organ's own brief: operators
are the low-yield axis, fields are the high-yield one. Separately: Sharpe min = median = 1.2500,
100% below 1.30, 26/50 exactly at the stated 1.25 target -- total threshold-hugging, and robust
to the source being untrustworthy (fabricated numbers were fabricated TO HUG THE BAR).

R0527 REJECTED -- this seat's own s2 row, premise refuted by controlled measurement. A proxy
relaying an upstream LOGIN_REQUIRED is not a proxy that is down; acting on R0527 would have sent
an engineer to replace four working proxies. Real defect already live as R0592. Retraction
written in place at the s2 note so no future session inherits the false claim.

Video: 0 fetched, 13 SOURCE-LOCKED. Answers BR s3's explicit ask for a blocked FRACTION on a real
target list: 15/16 = 93.75% over a controlled 16-video panel. Blocked at 5,269,269 views and at
5,374 views, passing only at ~1.6bn -- RU s3's "keyed to popularity" REFUTED, BR s3's "not
view-count-shaped" CONFIRMED. Channel-specificity dead too (two control channels blocked).
Cache residency is the sole surviving hypothesis, UNMEASURED as a cause.

s13 held: no credential held, sought or used; no call made to api.worldquantbrain.com; unlicensed
artifact mined as text with no formula or code copied. yt-dlp-with-cookies explicitly NOT proposed.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 2020bba176c354eb237e0deb15ccd921a11f7a3d
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:21:47 2026 +0000

    BRAIN hunter 08-13 s3: the desk imported BRAIN's thresholds and missed its ratios (OP-083/OP-084)
    
    OP-083: brain_calibration.py was built from a WEBINAR TRANSCRIPT, which states THRESHOLDS.
    rocky-d/wqb (MIT) is the platform's own API and states the MEASUREMENT NAMESPACE. Four BRAIN
    metrics are dimensionless RATIOS of two like-measured quantities, so every convention difference
    that module correctly warns about (annualisation, cost base, return definition, periodicity)
    CANCELS -- os.osISSharpeRatio ABSENT, os.sharpe60/125/250/500 ABSENT, os.preCloseSharpe* PARTIAL
    (phase_sensitivity covers funding binning, not decision-timestamp), is.prodCorrelation HALF (the
    self-correlation cap was imported, the production half never was). The un-portable half was taken
    and the portable half was never seen. Rule that generalises: a threshold is asset-class-bound and
    does not travel; a ratio of two like-measured quantities is unit-free and travels intact.
    -> R0601 (record forward evidence as a ratio and a ladder, in OBSERVATIONS not days per L1.48)
    -> R0602 (candidate-vs-DEPLOYED correlation gate; cheapest while the denominator is 1)
    
    OP-084: measured all 50 rows of a worked low-correlation portfolio -- 49 distinct data fields,
    8 operator tokens, 48/50 single-operator expressions, median depth 1. Independence came from the
    DATA, not the MATH, corroborating the desk's 129-mechanisms-all-price-derived-all-failed lesson
    from a different market, institution and asset class. Re-ranks this organ's own brief: operators
    are the low-yield axis, fields are the high-yield one. Separately: Sharpe min = median = 1.2500,
    100% below 1.30, 26/50 exactly at the stated 1.25 target -- total threshold-hugging, and robust
    to the source being untrustworthy (fabricated numbers were fabricated TO HUG THE BAR).
    
    R0527 REJECTED -- this seat's own s2 row, premise refuted by controlled measurement. A proxy
    relaying an upstream LOGIN_REQUIRED is not a proxy that is down; acting on R0527 would have sent
    an engineer to replace four working proxies. Real defect already live as R0592. Retraction
    written in place at the s2 note so no future session inherits the false claim.
    
    Video: 0 fetched, 13 SOURCE-LOCKED. Answers BR s3's explicit ask for a blocked FRACTION on a real
    target list: 15/16 = 93.75% over a controlled 16-video panel. Blocked at 5,269,269 views and at
    5,374 views, passing only at ~1.6bn -- RU s3's "keyed to popularity" REFUTED, BR s3's "not
    view-count-shaped" CONFIRMED. Channel-specificity dead too (two control channels blocked).
    Cache residency is the sole surviving hypothesis, UNMEASURED as a cause.
    
    s13 held: no credential held, sought or used; no call made to api.worldquantbrain.com; unlicensed
    artifact mined as text with no formula or code copied. yt-dlp-with-cookies explicitly NOT proposed.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/prospector_coverage.md     | 135 +++++++++++++++++++++++++++++++
 docs/research/recommendation_ledger.json |  32 +++++++-
 docs/research/search_operator_library.md | 119 +++++++++++++++++++++++++++
 docs/research/video_locked_log.md        |  46 +++++++++++
 4 files changed, 328 insertions(+), 4 deletions(-)

diff --git a/docs/research/prospector_coverage.md b/docs/research/prospector_coverage.md
index 27a1d21e..bd9f309a 100644
--- a/docs/research/prospector_coverage.md
+++ b/docs/research/prospector_coverage.md
@@ -5088,6 +5088,23 @@ dead, 148582 dead, 5 NP indices unarchived).
 
 **So the corpus is REACHABLE and our tool is DEAD, and `video_locked` would have been the wrong log.** L1.34 makes video first-class for *every* seat, so this outage is silently degrading all of them and each one that tries will mis-attribute a desk-side failure to a source-side wall — the desk's own lesson inverted ("a verdict about the HOST is not a verdict about the DESK"). **Ledgered R0527, scheduled 08-15** with the full diagnosis and a 4-step fix. **The official BRAIN lecture corpus therefore remains UNMINED and is not claimed as thin.**
 
+> **🔴 RETRACTED 2026-08-13 BY BRAIN HUNTER s3 — THIS PARAGRAPH IS WRONG IN BOTH HALVES, AND `video_locked` WAS THE RIGHT LOG AFTER ALL.**
+> Measured on the same endpoint s3 morning: **`api.piped.private.coffee` is UP** and serves
+> `dQw4w9WgXcQ` with 6 subtitle tracks (HTTP 200) *in the same minute* that 15 of 16 other videos
+> return HTTP 500. **s2 read a proxy faithfully RELAYING an upstream wall as a proxy that was
+> DOWN** — the 500 bodies carry YouTube's own `SignInConfirmNotBotException … LOGIN_REQUIRED`,
+> which is a *source* verdict, not a transport failure. And the corpus is **not** reachable: a
+> plain honest-UA GET of `www.youtube.com/watch?v=kuIfHJEsPkY` returns a **1,133,907-byte HOLLOW
+> 200** — empty `<title>`, **zero** `captionTracks`. s2 checked that `www.youtube.com` returned
+> 200 and never checked what was *in* the 200, which is the desk's own hollow-success lesson
+> arriving one level up from where it was written.
+> **R0527 REJECTED** (premise refuted; acting on it would have sent an engineer to replace four
+> working proxies). The real defect — per-instance error reporting, dropping the dead
+> `api.piped.yt` domain, classifying `LOGIN_REQUIRED` as PLATFORM-WALL — is correctly diagnosed
+> and live as **R0592**. The 13 lecture ids are now logged in `video_locked_log.md` with a
+> measured **93.75% blocked fraction** over a 16-video controlled panel. The corpus is
+> **SOURCE-WALLED, still UNMINED, and still not claimed as thin.**
+
 ### NEW VENUES (standing discovery obligation — the seed list is a floor)
 
 | venue | what lives there | how found | verdict |
@@ -5267,3 +5284,121 @@ reached.** Run closed cleanly 2026-08-13. Honest zeros recorded: 0 mechanisms ca
 methodological, and the watchlist is at 5/5 with nothing here earning a displacement), 0 video
 fetched, 0 primary-source solution writeups readable, private leaderboard UNRECOVERABLE with the
 falsifier named.
+
+---
+
+## BRAIN HUNTER — session 3 (2026-08-13, dedicated daily organ)
+
+**MINE GATE re-read live** (`scripts/mine_gate.py`, not the header alone): **BACKLOG-CLEAR**, 19/19
+carded finds disposed, mining authorised. **PRIOR STATE:** s2's 6-item next-ground chain inherited
+intact; R0437 (grouping-map consumer wiring) verified live and correctly SCHEDULED 08-18 — owed by
+the alpha org, not this seat.
+
+### THE FIRST THING THIS RUN DID WAS REFUTE ITS OWN PREVIOUS RUN
+
+**s2's video verdict was wrong and is now retracted in place** (see the red block at the s2 note
+above). s2 graded the desk fetcher **INERT DESK-WIDE** and ledgered R0527 on that premise. Measured
+this morning: `api.piped.private.coffee` **serves a video with 6 subtitle tracks in the same minute**
+that 15 of 16 others return HTTP 500 — and those 500 bodies carry **YouTube's own
+`SignInConfirmNotBotException … LOGIN_REQUIRED`**. **A proxy relaying an upstream wall is not a proxy
+that is down.** **R0527 REJECTED**; acting on it would have sent an engineer to replace four working
+proxies. The genuine defect is already live and better-diagnosed as **R0592** (BR seat).
+
+**The trigger was a sibling seat's memory, not a fence** — RU s3 recorded "the fetcher WORKS, the
+08-12 verdict was refuted on the first call". A capability graded from a **single-instant probe of N
+rotating endpoints** is a measurement with no repeat; ask *does the rotation succeed*, never *are all
+N up*.
+
+### VIDEO: 0 fetched, 13 SOURCE-LOCKED — and the blocked FRACTION is now measured
+
+**BR s3 left an explicit ask in `video_locked_log.md`: "measure the blocked FRACTION on a real target
+list, never assert a blocked CLASS." The BRAIN lecture corpus is that list** — one channel, one
+language, one publisher, **13 videos over a 45x view range**.
+
+**15/16 blocked = 93.75%.** Blocked at **5,269,269 views**; blocked at **5,374 views**; passing only
+at ~1.6bn. **RU s3's "keyed to video popularity" is REFUTED and BR s3's "not view-count-shaped" is
+CONFIRMED** — this panel reaches 10x higher up the view range than either seat's could, which is the
+only reason it separates the two stories. Channel-specificity was the next guess and is dead too (two
+non-WorldQuant control channels blocked). **Instance cache residency** is the sole surviving
+hypothesis and remains **UNMEASURED as a cause** — real answer, not a hedge (L1.28a). Full table and
+the §13 note on why `yt-dlp`-with-cookies is *not* proposed: `video_locked_log.md`.
+
+### GROUND OPENED, and the two-exhaustions rule applied
+
+- **`rocky-d/wqb` v0.2.5 (MIT, 272★)** — **EXHAUSTED at API-SURFACE level.** `wqb_urls.py`,
+  `__init__.py`, `filter_range.py` and the `filter_alphas_limited` / `simulate` / `check` paths of
+  `wqb_session.py` (43,330 B) read. **NOT claimed:** the async retry/concurrency machinery
+  (`retry`, `concurrent_*`), which is HTTP plumbing carrying no platform semantics. **Honest
+  limitation recorded so nobody re-opens it:** every enum (`Neutralization`, `NanHandling`,
+  `Pasteurization`, `UnitHandling`, `Region`, `Universe`) is aliased to **`Any`** — the library gives
+  the *namespace and exact API paths*, never the *value sets*.
+- **`CrisperX/50_WorldQuant_Alpha_Examples_for_Alphathon` (85★, NO LICENCE ⇒ all-rights-reserved)** —
+  **EXHAUSTED** (2 files, both read; `alpha50.csv` measured in full). Mechanism and aggregate
+  statistics extracted; **no formula or code copied into this repo.**
+- **§13 HELD, unchanged:** no credential was held, sought or used, and **no call was made to
+  `api.worldquantbrain.com`** — `wqb` is an authenticated client and this seat does not touch
+  authenticated surfaces. Reading the client's source is public; running it is not.
+
+### THE TWO FINDS
+
+**OP-083 — the desk imported BRAIN's THRESHOLDS (which do not port) and missed its RATIOS (which
+do).** `brain_calibration.py` was built from a *webinar transcript*, and a transcript states
+thresholds; an *API* states the measurement namespace. Four BRAIN metrics are **dimensionless ratios
+of two like-measured quantities**, so every convention difference that module correctly warns about
+(annualisation, cost base, return definition, periodicity) **cancels**: `os.osISSharpeRatio`
+(**ABSENT**), `os.sharpe60/125/250/500` (**ABSENT**), `os.preCloseSharpe*` (**PARTIAL** —
+`earnability.phase_sensitivity` covers funding-settlement binning, not decision-timestamp
+sensitivity), `is.prodCorrelation` (**HALF** — the self-correlation cap was imported, the production
+half was not). **The transferable rule, well past this platform: a threshold is asset-class-bound and
+does not travel; a ratio of two like-measured quantities is unit-free and travels intact.**
+**[§33: wired -> `search_operator_library.md` OP-083; ledgered R0601 + R0602]**
+
+**OP-084 — measured: the independence came from the DATA, not the MATH.** Over all 50 rows of a
+worked low-correlation portfolio: **49 distinct data fields, 8 operator tokens, 48/50
+single-operator expressions**, median expression depth **1**. Diversity of *expression* contributed
+essentially nothing; diversity of *underlying field* contributed everything. It corroborates the
+desk's most expensive lesson from a different market, institution and asset class (129 mechanisms,
+all price-derived, all failed). **This re-ranks this organ's own brief: operators are the low-yield
+axis, fields are the high-yield one.** Separately measured and robust to the source being
+untrustworthy: **Sharpe min = median = 1.2500, 100% below 1.30, 26/50 exactly at the platform's
+stated 1.25 target** — total threshold-hugging, and if the numbers were fabricated they were
+fabricated *to hug the bar*, which reveals the same selection norm either way.
+**[§33: wired -> `search_operator_library.md` OP-084]**
+
+### §33 DISPOSITIONS — every find routed in-run
+
+- BRAIN metric namespace / portable-ratio rule **[§33: wired -> `docs/research/search_operator_library.md` OP-083]**
+- 50-alpha population measurement **[§33: wired -> `docs/research/search_operator_library.md` OP-084]**
+- 13 source-locked lecture ids + 93.75% blocked fraction **[§33: wired -> `docs/research/video_locked_log.md`]**
+- s2's refuted video verdict **[§33: killed -> R0527 REJECTED, retraction written in place]**
+- `ts_zscore`, `ts_av_diff`, `ts_corr`, `group_rank` confirmed as real platform operators **[§33: screened -> OP-083 footer]**
+
+**NO card added to `prospector_watchlist.md`** (5/5 slots used; nothing here earns a displacement).
+**No new tradeable mechanism is claimed this run** — both finds are methodological, and OP-084's
+whole point is that the desk's binding constraint is field count, which is already carded and already
+has its consumer wiring owed at R0437.
+
+### NEXT UN-EXHAUSTED GROUND, in order, for session 4 (L1.35/L1.40 — named before closing)
+
+1. **The reimplementation/fork layer, 8 repos still untriaged** — s2's item 2, only CrisperX taken.
+   Hunt the **six operators the desk lacks**; `ts_zscore` is now confirmed real and in live use, so
+   it is the one with a demonstrated caller. `zhutoutoutousan/worldquant-miner` (**Apache-2.0**,
+   723★) is the licence-cleanest of them and its tree did not resolve on `main` — **check `master`**
+   (this seat has been caught by a wrong default branch twice now).
+2. **`yli188/WorldQuant_alpha101_code` (846★)** — the most-starred artifact on this entire ground and
+   **never opened by any session**. No licence, so mechanism-only.
+3. **BRAIN lecture corpus** — **re-grade the blocker: it is SOURCE-walled, not tool-blocked.** Do not
+   re-attempt through Piped; the only routes that could open it are authenticated egress (§13 bar,
+   see the video log) or a text mirror. **Hunt the text mirror first** — course transcripts,
+   community lecture notes, and the IQC webinar series are all candidate mirrors of the same content.
+4. **`jglazar/notes` tree walk** — carried unresolved from s2; both guessed paths 404'd, so walk the
+   tree via the API rather than guessing a third time.
+5. **IQC 2026 webinar series** — recurring weekly; establish whether materials are published outside
+   the login wall. **The standing argument for a daily organ: the platform keeps publishing.**
+6. **BRAIN community discussion of FAILED approaches** — s1 item 6, still the most neglected vein and
+   still the highest-yield bite either previous session took.
+
+**A NULL WAS NOT AVAILABLE THIS RUN and none is claimed.** Ground remains wide open: 8 untriaged
+repos, the most-starred artifact on the ground unopened, a source-walled official lecture corpus with
+its text-mirror route untried, and a recurring webinar series. **Seat-exhaustion is false here as
+everywhere.**
diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index 45bc3fc4..cd367892 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -6706,11 +6706,11 @@
    "summary": "VIDEO FETCHER IS INERT DESK-WIDE, and every miner seat is mis-attributing the failure to source walls. scripts/fetch_video_transcript.py reaches YouTube ONLY via 4 hardcoded Piped proxies (_PIPED, lines 27-31) and ALL FOUR are down as measured 2026-08-12: api.piped.private.coffee 500, pipedapi.kavin.rocks 502, pipedapi.adminforge.de 301 (redirect not followed), api.piped.yt 000 (DNS NXDOMAIN). Meanwhile www.youtube.com returns 200 from this box, so the source is NOT walled -- the DESK-SIDE TOOL is dead. THE DEFECT IS THE MIS-ATTRIBUTION, not the outage: L1.34 makes video first-class for EVERY seat and the coverage protocol says log video_locked only for a route TRIED AND FAILED, so every seat that tries will now correctly record a failure and INCORRECTLY infer the platform is walled -- a desk-tool outage wearing a source-wall costume, and the same class as the desk lesson 'a verdict about the HOST is not a verdict about the DESK'. It fails silently and permanently: Piped instances rotate constantly (the module comment says so) and nothing monitors them. FIX, in order of durability: (1) the script must distinguish ALL-PROXIES-DOWN from CAPTIONS-ABSENT in its exit message so a seat cannot mis-log it; (2) refresh the instance list AND follow redirects (adminforge returns 301, so it may be alive behind a moved path); (3) add a non-Piped fallback -- the legacy timedtext endpoint returns 200/size=0 and the ANDROID innertube client returns 400, both verified dead today, so the fallback needs to be a maintained library rather than another hardcoded host; (4) fence it: a video-route liveness check, since a rotating-proxy dependency with no monitor is guaranteed to rot again. Found by BRAIN hunter s2 while executing its owed video obligation (Learn2Quant lessons kuIfHJEsPkY / A3RNoYAz_9U, the official BRAIN lecture corpus, still unfetched).",
    "roi_bps": 45.0,
    "raised": "2026-08-12T20:55:11.671195+00:00",
-   "status": "scheduled",
-   "reason": "Owned by the ops/tooling org: the fix is in scripts/fetch_video_transcript.py and the BRAIN-hunter seat is research-frozen out of scripts/ and libs/. Tight due date (3d, not the usual window) deliberately: the diagnosis is complete and the first repair is a URL-list refresh plus following the 301, so the work is cheap -- while the cost accrues DAILY and SILENTLY across every miner seat, because L1.34 makes video first-class for all of them and each one that tries will mis-record a desk-tool outage as a source-side wall.",
+   "status": "rejected",
+   "reason": "PREMISE REFUTED BY CONTROLLED MEASUREMENT (BRAIN hunter s3, 2026-08-13). R0527 claimed 'all four Piped proxies are down, the source is NOT walled, the DESK-SIDE TOOL is dead'. Measured today on the same endpoint: api.piped.private.coffee serves dQw4w9WgXcQ with 6 subtitle tracks (HTTP 200) in the SAME MINUTE that 15 of 16 other videos return HTTP 500 carrying YouTube's own SignInConfirmNotBotException/LOGIN_REQUIRED. A 500 from the proxy RELAYING an upstream bot-wall is not a dead proxy -- s2 misread a faithfully-reported source wall as a desk-side outage, which is the desk lesson 'a verdict about the HOST is not a verdict about the DESK' inverted. Direct route confirms the wall is the source's: www.youtube.com/watch returns a 1,133,907-byte HOLLOW 200 with empty <title> and ZERO captionTracks. Acting on R0527 would have sent an engineer to replace four working proxies. The real defect -- per-instance error reporting, dropping the dead api.piped.yt domain, and classifying LOGIN_REQUIRED as PLATFORM-WALL rather than a local fault -- is already correctly diagnosed and live as R0592 (open). Superseded by R0592; no separate work owed.",
    "commit": null,
-   "due": "2026-08-15",
-   "disposed": "2026-08-12T20:56:05.961114+00:00"
+   "due": null,
+   "disposed": "2026-08-13T09:16:40.424513+00:00"
   },
   {
    "id": "R0528",
@@ -7587,6 +7587,30 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0601",
+   "source": "cycle",
+   "summary": "RECORD FORWARD EVIDENCE AS A RATIO AND A LADDER, NOT A SINGLE VERDICT (BRAIN hunter s3, OP-083). WorldQuant BRAIN exposes os.osISSharpeRatio (OOS Sharpe over IS Sharpe) and os.sharpe60/125/250/500 (OOS Sharpe re-measured at four horizons) as first-class queryable metrics; the desk has NEITHER (grep: zero hits for both families across libs/ and scripts/). data/forward_slots.json rows carry only name/kind/source/state -- the two Sharpes whose ratio measures this desk's OWN screen optimism are not persisted anywhere, so the quantity is UNMEASURED and therefore counts as zero (L1.28a). WHY IT PORTS WHERE THE THRESHOLDS DO NOT: brain_calibration.py correctly refuses to let BRAIN's 1.25 Sharpe target become a gate because it is US-equity/daily/dollar-neutral on their conventions -- but a RATIO of two like-measured Sharpes is dimensionless and every one of those conventions cancels. The desk imported the un-portable half and never saw the portable half. WHAT TO BUILD: persist screen (Stage-A) Sharpe and forward Sharpe per candidate, publish the ratio, and re-measure forward Sharpe at 4 cumulative points expressed in OBSERVATIONS not days (L1.48 -- a perp book funding 3x/day accrues evidence ~3x faster than the daily-rebalanced equity book those 60/125/250/500 day-counts came from; copying them as days imports an equity sampling convention as a law). PAYS INTO: L1.29 (the ratio's distribution across the desk's 434 screened candidates is a direct measurement of its own overfitting rate, which nothing currently measures), L1.19/L1.30 (a decay ladder detects an edge dying WHILE it is being confirmed; a single end-of-clock verdict cannot). NOT A BAR CHANGE: this adds no gate, moves no threshold and grants no promotion authority -- it is a measurement duty only.",
+   "roi_bps": 25.0,
+   "raised": "2026-08-13T09:19:18.670834+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0602",
+   "source": "cycle",
+   "summary": "THE DESK IMPORTED BRAIN'S selfCorrelation CAP AND MISSED ITS prodCorrelation GATE (BRAIN hunter s3, OP-083). BRAIN's alpha API exposes TWO distinct correlation gates: is.selfCorrelation (candidate vs your own prior alphas) and is.prodCorrelation (candidate vs the PRODUCTION book). libs/validation/brain_calibration.py imported only the first, as BRAIN_SELF_CORRELATION_CAP = 0.7; grep finds no candidate-vs-deployed correlation gate anywhere in libs/ or scripts/. THE TWO ASK DIFFERENT QUESTIONS AND ONLY ONE PROTECTS THE GROWTH ARGUMENT: selfCorrelation asks 'have I already tried this?', prodCorrelation asks 'does this duplicate what is ALREADY TAKING CAPITAL?' -- two correlated deployed sleeves draw down together, which is exactly what L1.18 (maximum INDEPENDENT compounding sources) exists to prevent. The desk has cohort_independence, effective_bets, panel_breadth and capacity_policy, but nothing that gates a candidate against the DEPLOYED book at promotion time. THE OBVIOUS OBJECTION IS BACKWARDS: the desk runs ~1 deployed sleeve so the gate looks near-vacuous today -- which is precisely why it is cheap now (denominator 1) and binding from the moment the second sleeve lands. Building it after the second sleeve means the first pair is admitted ungated, and that pair is the one that sets the book's correlation floor. CORROBORATED FROM OUTSIDE (OP-084): a measured 50-alpha low-correlation portfolio achieved independence through 49 DISTINCT DATA FIELDS with only 8 operator tokens and 48/50 single-operator expressions -- independence is bought with orthogonal SOURCES, so the gate must be paired with field-count growth, not with more transforms of price. Note the ordering constraint: this gate must read the deployed book at consumption time with a declared max age (L1.44), and must fail toward REFUSING a candidate when the book is unreadable, never toward admitting one.",
+   "roi_bps": 18.0,
+   "raised": "2026-08-13T09:19:34.236227+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
diff --git a/docs/research/search_operator_library.md b/docs/research/search_operator_library.md
index a607f4b3..7151103e 100644
--- a/docs/research/search_operator_library.md
+++ b/docs/research/search_operator_library.md
@@ -2565,3 +2565,122 @@ the *cause* is not: `Strategy001.py` sets `sell_profit_only = True` while `confi
 `false`, and **config overrides strategy** — so which was live is undeterminable from the repo. State
 the recomputed number as fact and the mechanism as a hypothesis with its falsifier. (The vendored OHLCV
 under `user_data/data/` makes that falsifier genuinely runnable, which is what EXECUTABLE tier means.)
+
+---
+
+## OP-083 — THE DESK IMPORTED BRAIN'S **THRESHOLDS** (which do not port) AND MISSED ITS **RATIOS** (which do)
+
+**SOURCE:** `rocky-d/wqb` v0.2.5 (**MIT**, 272★, `wqb/wqb_session.py` + `wqb/wqb_urls.py`), read as
+text 2026-08-13. **DERIVES-FROM:** independent of `libs/validation/brain_calibration.py`, which was
+built from a *webinar transcript* — different artifact, different author, no shared lineage.
+**§13:** MIT, read-only, mined as text. **No credential was held, sought or used, and no call was made
+to `api.worldquantbrain.com`** — the library is an authenticated client and this seat does not touch
+authenticated surfaces.
+
+**THE FIND IS A NEGATIVE SPACE, not a new operator.** `brain_calibration.py` already imports BRAIN's
+constants — fitness bar 1.0, Sharpe bar 1.0, Sharpe target 1.25, self-correlation cap 0.7, truncation
+band, recent-Sharpe floor, IS/OOS score weights. Its own docstring then spends ten lines warning that
+these are US-equity, daily-rebalanced, dollar-neutral numbers on the platform's own PnL and
+annualisation conventions, **"COMPARABLE IN ORDER OF MAGNITUDE ONLY"**, and that *"a reader who takes
+1.25 as a threshold has misused this module"*. That warning is correct.
+
+**But a transcript states THRESHOLDS and an API states the MEASUREMENT NAMESPACE, and the desk only
+ever had the transcript.** `filter_alphas_limited` enumerates the platform's queryable alpha metrics,
+and four of them are **dimensionless ratios of two quantities measured the same way** — so every
+convention difference the caveat warns about (annualisation, cost base, return definition,
+periodicity) **cancels in the numerator and denominator**. The un-portable half was imported; the
+portable half was never seen.
+
+| BRAIN metric (API name) | what it computes | crypto analogue | desk status |
+|---|---|---|---|
+| `os.osISSharpeRatio` | OOS Sharpe ÷ IS Sharpe — one number for *how much of the backtest survived contact with unseen data* | forward-clock Sharpe ÷ Stage-A screen Sharpe, per candidate | **ABSENT** (grep: no `os_is`/`oos_is`/`degradation` metric) |
+| `os.sharpe60/125/250/500` | OOS Sharpe re-measured at four horizons — a **decay ladder**, not one verdict | same ladder in **OBSERVATIONS, never days** (L1.48): a perp desk funding 3×/day accrues evidence ~3× faster than a daily-rebalanced equity book, so copying 60/125/250/500 as *days* would import an equity sampling convention as if it were a law | **ABSENT** (grep: zero hits) |
+| `os.preCloseSharpe`, `os.preCloseSharpeRatio` | Sharpe recomputed at pre-close vs at the close print — *does this edge only exist at the stamp?* | entry shifted off the UTC bar boundary / off the funding settlement stamp | **PARTIAL** — `earnability.phase_sensitivity` already tests *funding-settlement binning* (L1.47's instrument) and is well-built; it does **not** test *decision-timestamp* sensitivity, which is the different question |
+| `is.selfCorrelation` **vs** `is.prodCorrelation` | **two** correlation gates: against your own prior alphas, and against the **production book** | candidate vs desk's own screened pool; candidate vs **capital already deployed** | **HALF** — `BRAIN_SELF_CORRELATION_CAP = 0.7` imported; the **prod** half absent |
+
+**WHY THE `prodCorrelation` HALF IS THE ONE THAT MATTERS (L1.18).** `selfCorrelation` asks "have I
+already tried this?"; `prodCorrelation` asks **"does this duplicate what is already taking capital?"**
+Only the second one protects the geometric-growth argument, because two correlated deployed sleeves
+draw down together. The desk has `cohort_independence`, `effective_bets` and `panel_breadth`, but
+grep finds **no candidate-vs-deployed gate at promotion time**. The objection writes itself — the desk
+runs ~1 deployed sleeve, so the gate is near-vacuous today — and it is exactly backwards: **a gate is
+cheapest to build while its denominator is 1 and binding from the moment the second sleeve lands.**
+
+**THE TRANSFERABLE RULE, and it generalises past this platform (L1.34/L1.11a).** When mining any
+foreign venue, asset class or institution: **a threshold is asset-class-bound and does not travel; a
+ratio of two like-measured quantities is unit-free and travels intact.** Prefer the ratio every time.
+This is why an equities platform can still teach a perp desk something — the caveat that correctly
+blocks its *numbers* does not touch its *instruments*.
+
+**HONEST LIMITATION OF THE SOURCE.** Every enum in `wqb/__init__.py` (`Neutralization`, `NanHandling`,
+`Pasteurization`, `UnitHandling`, `Region`, `Universe`, …) is aliased to `Any`. The library gives the
+**parameter namespace and exact API paths, not the value sets** — so this find names *what the platform
+measures*, and cannot name *what values it accepts*. Recorded so the next seat does not re-open it
+expecting enums.
+
+**Also confirmed from the wild (see OP-084): `ts_zscore`, `ts_av_diff`, `ts_corr`, `group_rank` are
+real platform operators** — `ts_zscore` is one of the six this desk still lacks.
+
+---
+
+## OP-084 — MEASURED: THE INDEPENDENCE CAME FROM THE **DATA**, NOT THE **MATH** (49 fields, 8 operators, 48/50 single-operator)
+
+**SOURCE:** `CrisperX/50_WorldQuant_Alpha_Examples_for_Alphathon` (85★, **NO LICENCE ⇒
+all-rights-reserved**), `alpha50.csv`, 14,891 B, last pushed 2023-10-30. **DERIVES-FROM:** named as
+the specific prize in this organ's own s2 next-ground list; no other seat has touched it. **§13:**
+public repo, read in place; **aggregate statistics and mechanism extracted, no formula or code copied
+into this repo** — an unlicensed artifact is mineable as *text* and not reproducible as *content*.
+**CLAIMED-IS-NOT-VERIFIED:** the README is an advertisement for paid tutoring and every performance
+number is the author's own, unverified, on US equities. **What is measured below are properties of
+the FILE, which I computed myself, not claims about the market.**
+
+The repo's premise is the desk's own independence problem stated in the platform's terms: *50 alphas
+that can pass the mutual correlation test if submitted together.* The desk's version is L1.18 (maximum
+INDEPENDENT compounding sources) against a cross-section measured at **N_eff 1.54 raw / 29
+market-neutral**. So: how does a working practitioner actually manufacture 50 mutually-uncorrelated
+signals?
+
+**MEASURED OVER ALL 50 ROWS:**
+
+| quantity | measurement |
+|---|---|
+| distinct **data fields** | **49** (for 50 alphas; max reuse 3) |
+| distinct **operator tokens** | **8** — `rank` 30, `ts_mean` 18, `ts_zscore` 2, `sum`/`delay`/`group_rank`/`ts_av_diff`/`ts_corr` 1 each |
+| expression depth (paren count) | min 1, **median 1**, max 15 |
+| **single-operator alphas** | **48 / 50** |
+| neutralization | Subindustry 19, Market 17, Sector 8, Industry 4, **None 2** — i.e. **96% neutralized** |
+| universe | TOP200 27, TOP1000 12, TOP500 9, TOP3000 2 |
+| turnover | median **0.0205** (≈2%), max 0.212 |
+| decay | median 10, mean 19.6, max 95 |
+
+**THE MECHANISM: 48 of 50 are one operator applied to one field.** `rank(mdf_pva)`,
+`-rank(mdf_ite_q)`, `-rank(fnd6_newa1v1300_epspi)`. Diversity of *expression* contributes essentially
+nothing to passing the correlation test; **diversity of underlying field contributes everything.**
+Eight operators sufficed for fifty independent signals.
+
+**WHY THIS MATTERS HERE, AND IT IS A RE-RANKING OF THIS SEAT'S OWN BRIEF.** This organ exists partly
+to hunt operators, and the strongest evidence it has yet produced says **operators are the low-yield
+axis and fields are the high-yield one.** It independently corroborates the desk's single most
+expensive research lesson from a completely different market, institution and asset class: the
+2026-08-01 campaign ran **129 mechanisms, all price-derived, all directional, and all 129 failed** at
+max OOS Sharpe 0.100. Another *transform* of price cannot manufacture an independent bet — only
+another *source* can. **The desk's alpha-diversity law is a DATA-ACQUISITION problem wearing a
+modelling costume**, and that is now measured from outside rather than argued from inside.
+
+**THE THRESHOLD-HUGGING RESULT, and it survives the source being untrustworthy.** Sharpe: **min 1.2500,
+median 1.2500, max 1.2900**; 26 of 50 sit at *exactly* 1.25; **70% within [1.24, 1.26]; 100% below
+1.30.** The platform's stated submission target — already in this repo as
+`BRAIN_SHARPE_TARGET = 1.25` — is the **floor, the median and very nearly the maximum** of the
+accepted population. That is the signature of a search that stops the instant the bar is cleared.
+**And the finding does not depend on the numbers being real:** if they are honest, the accepted
+population is dominated by marginal candidates; if they are fabricated, the author fabricated them
+*to hug the threshold*, which reveals the same selection norm. Either way it is direct external
+evidence for the desk's own law that **throughput must come from screening more, never from passing
+more** — and a live demonstration of why L1.6 forbids importing that 1.25 as a gate (OP-083).
+
+**CRYPTO ANALOGUE / WHAT IT WOULD NEED.** The construction that ports is *one cheap transform over
+many orthogonal fields*, not *many clever transforms over price*. The desk's binding input is
+unchanged and this sharpens it: 96% of these alphas neutralize against a **grouping** (subindustry
+most often — the *finest* available), and `data/crypto_grouping_map.json` exists with its consumer
+wiring still owed at **R0437**. Field-count, not operator-count, is the axis to grow —
+routed to `data_axis_watchlist.md`.
diff --git a/docs/research/video_locked_log.md b/docs/research/video_locked_log.md
index 77728cbd..83d05f78 100644
--- a/docs/research/video_locked_log.md
+++ b/docs/research/video_locked_log.md
@@ -100,3 +100,49 @@ the **last** instance's error, and that instance is `api.piped.yt` — **a dead
 six fetch attempts surfaced `Name or service not known`, i.e. a platform bot-wall displayed as a local
 DNS fault. **Query `https://api.piped.private.coffee/streams/<id>` directly to get the true status**;
 the wrapper's error text is not evidence about the video.
+
+| 2026-08-13 | youtube | `kuIfHJEsPkY` · `A3RNoYAz_9U` · `40JActnyhkM` · `dpNuRCcxjwc` · `LC6whEo80T0` · `XqdcIayjAug` · `-iP5GFbF8NM` · `eTq8iPhL1Ys` · `nNOFUVfDg3Y` · `QjhqRrPQs2Q` · `fjc1M92MPSc` (Learn2Quant L1-L11, **official WorldQuant channel**) | the platform's own alpha-construction methodology course — metrics, neutralization, delay/decay, diversity, risk | official docs at `platform.worldquantbrain.com/learn` are login-walled (logged WALLED 08-12); the lecture corpus IS the public mirror of that material, and it is video-only |
+| 2026-08-13 | youtube | `mky_BnKKmM0` · `sVV8qsCSIg0` (Quantcepts: Sentiment Data / Types of Alpha Ideas) | data-category-specific alpha construction | as above |
+
+### 2026-08-13 — THE BLOCKED **FRACTION** ON A REAL TARGET LIST (BRAIN hunter s3)
+
+**This answers the ask BR s3 left directly above** ("measure the blocked FRACTION on a real target
+list rather than asserting a blocked CLASS"). The BRAIN lecture corpus is that list: **one channel,
+one language, one publisher, 13 videos, a 45x view range.**
+
+| panel | n | blocked | fraction |
+|---|---|---|---|
+| Learn2Quant + Quantcepts (official WorldQuant channel) | 13 | 13 | **100%** |
+| non-WorldQuant finance channels (controls) | 2 | 2 | 100% |
+| `dQw4w9WgXcQ` (cache-resident control) | 1 | 0 | 0% |
```


---

## c51606c7 BR miner 08-13 s3: ledger R0599-R0600 + desk lesson L0160 (carries sibling row R0598, not this seat's work)
L0160: carry a desk lesson's SCOPE QUALIFIER, not just its conclusion.
Citing the memorable number from the breadth lesson (1.54 independent bets)
without its qualifier (DIRECTIONAL) would have graveyarded the desk's
thinnest family; a cointegration pair is beta-neutral by construction and
lands on the 29 side, so that lesson argues FOR the family.

The ledger diff is append-only (36 insertions, 0 deletions) and includes
R0598 from a concurrent session in this shared worktree -- staged because
leaving it risks a cron snapshot sweeping these rows into an unrelated
commit (R0423, recorded 4x).

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit c51606c7e6d311de4c82b7440b68fa2afe31d4b9
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:03:35 2026 +0000

    BR miner 08-13 s3: ledger R0599-R0600 + desk lesson L0160 (carries sibling row R0598, not this seat's work)
    
    L0160: carry a desk lesson's SCOPE QUALIFIER, not just its conclusion.
    Citing the memorable number from the breadth lesson (1.54 independent bets)
    without its qualifier (DIRECTIONAL) would have graveyarded the desk's
    thinnest family; a cointegration pair is beta-neutral by construction and
    lands on the 29 side, so that lesson argues FOR the family.
    
    The ledger diff is append-only (36 insertions, 0 deletions) and includes
    R0598 from a concurrent session in this shared worktree -- staged because
    leaving it risks a cron snapshot sweeping these rows into an unrelated
    commit (R0423, recorded 4x).
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/desk_lessons.jsonl                  |  1 +
 docs/research/recommendation_ledger.json | 36 ++++++++++++++++++++++++++++++++
 2 files changed, 37 insertions(+)

diff --git a/docs/desk_lessons.jsonl b/docs/desk_lessons.jsonl
index 4c432222..04309c1b 100644
--- a/docs/desk_lessons.jsonl
+++ b/docs/desk_lessons.jsonl
@@ -162,3 +162,4 @@
 {"id": "L0157", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Record LLM consultation in DERIVES-FROM, and treat a post-2023 source with no citations as UNVERIFIABLE rather than independent. Split every mined page into an OBSERVATION layer (what they ran, held and lost -- uncontaminated) and an EXPLANATION layer (possibly model output); a convergence claim across two post-2023 pages must name the OBSERVATION they share, never the conclusion.", "evidence": "perp-screener.com/posts/btc-bot (2025-12-04): the entire greeks analysis is introduced as 'チャッピーの解説によると' (per ChatGPT) and the author twice tells readers to ask an LLM instead of him. Unlike an arXiv echo (GAP #85), an LLM echo leaves NO citation -- docs/research/search_operator_library.md OP-072", "tags": ["provenance"], "source": "JP frontier miner s4 2026-08-13", "accepted_uninjected": "No test can read a third-party web page's provenance; the enforcement is OP-072's per-region marker list applied at extraction time by every miner seat, plus recommendation R0591 to wire the DERIVES-FROM: NONE -> UNVERIFIABLE rule into libs/research/convergence.py where a test CAN then pin it."}
 {"id": "L0158", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Before assuming a region's LANGUAGE is the moat, measure whether that region's practitioners actually write in it: run a native-key repo search AND a developer-search by LOCATION, and compare against a sibling-language control. If the population exists but the native corpus does not, the language layer is the retail layer and the technical output is already inside the EN seat's ground -- re-aim the seat at what is native-language BY INSTITUTIONAL CONSTRUCTION (regulators, exchanges, courts, religious certification), which cannot migrate to English.", "evidence": "2026-08-13 GitHub, one instrument: AR arbitrage repos 1/0/0 and quant-trading 0 vs CN 1174 / RU 24 / KR 6; discriminator by location gave UAE 67 > Korea control 59. docs/research/search_operator_library.md OP-075", "tags": ["mining"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "a search-behaviour rule for digger seats; no code path to gate"}
 {"id": "L0159", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "When a MANDATED artifact stays empty, audit the instrument that would have written its rows BEFORE concluding the duty was skipped. A wrong error message and an absent finding are indistinguishable from the outside, and only one of them is a person's fault. Specifically: a retry loop that overwrites a single 'last error' variable reports the LAST endpoint's cause for EVERY failure -- so if the last endpoint is permanently dead, every failure of every cause wears its error.", "evidence": "video_locked_log.md sat at ZERO rows for weeks; measured cause was fetch_video_transcript.py surfacing api.piped.yt's NXDOMAIN in place of private.coffee's HTTP 500 LOGIN_REQUIRED bot-wall. Ledger R0592", "tags": ["ops"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "concerns how a human reads an empty artifact; not mechanically checkable"}
+{"id": "L0160", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Carry a desk lesson's SCOPE QUALIFIER, not just its conclusion. Before inheriting a recorded kill, check which side of its stated boundary your mechanism falls on.", "evidence": "The breadth lesson reads 'the crypto cross-section is 1.54 independent bets RAW and 29 market-neutral -- any DIRECTIONAL cross-sectional mechanism is hard-killed by narrow_breadth'. Citing the memorable number (1.54) without the qualifier (DIRECTIONAL) would have graveyarded STATISTICAL-ARBITRAGE, the desk's thinnest family at THIN n=1 of 14 -- a cointegration pair is long y / short beta*x, beta-neutral BY CONSTRUCTION, so it lands on the 29 side. The lesson argues FOR the family, not against it.", "tags": ["research-process"], "source": "BR frontier miner s3 2026-08-13", "accepted_uninjected": "no test can catch a human/LLM dropping a scope qualifier while quoting a prose lesson; it rides in the ledger"}
diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index fc147a45..45bc3fc4 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -7551,6 +7551,42 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0598",
+   "source": "cycle",
+   "summary": "RED TEST AT HEAD, AND IT IS THE SECOND ROT OF THE SAME HAND-MAINTAINED MIRROR IN 24 HOURS. tests/scripts/test_build_standard_contract.py::test_every_governed_organ_meets_the_shared_build_contract fails: set(check_build_standard._GOVERNED) has SIX entries the test's hardcoded GOVERNED literal lacks -- run_cadence.py (5e9db644), check_claim_consistency.py (54bf5a2b), check_citation_integrity.py, check_panel_breadth.py (757c2d79), collect_lending_risk_base_rates.py, run_fee_attribution.py (b3264133) -- all added 2026-08-12/13 by sibling sessions landing L1.61, L1.62, R0425 and R0371. NOT INTRODUCED BY THIS SEAT (no commit here touches check_build_standard.py or its test) and reported rather than silently absorbed. THE FILE PREDICTED ITS OWN FAILURE: its header records 'ROTTED AND RESYNCED 2026-08-12 ... this mirror had drifted to 42 entries against a _GOVERNED of 75 ... IF IT ROTS AGAIN, DERIVE IT INSTEAD OF RE-TYPING IT'. It rotted again the next day, so re-typing the six names is the fix that is already known not to hold. THE TRAP IN THE OBVIOUS DERIVATION, which is why this needs a decision rather than a patch: deriving GOVERNED from _GOVERNED makes the assertion set(_GOVERNED)==set(_GOVERNED), vacuously true, and DESTROYS the contract -- the exact L1.57 vacuous-pass shape, inside the fence built to detect it. The contract's real content is check_build_standard's own requirement that EACH GOVERNED ORGAN IS NAMED BY A TEST, so the honest derivation is over the TEST CORPUS (assert every _GOVERNED entry is named somewhere under tests/), which cannot go vacuous because its two sides have independent sources. PRIORITY: a red test at HEAD is a gate every future push must either fix or bypass, and a fence that is red on arrival gets switched off (L1.43); this one guards the build standard itself.",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:52:25.343456+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0599",
+   "source": "cycle",
+   "summary": "Any desk statarb work must use statsmodels.tsa.stattools.coint(), never adfuller() on OLS residuals: measured 17.97% vs 7.60% rejection on n=120 (BR miner s3, OP-077). STATISTICAL-ARBITRAGE is THIN n=1 of 14 for INSTRUMENT reasons -- the 1.54-independent-bets breadth kill applies to DIRECTIONAL cross-sectional mechanisms and a cointegration pair is beta-neutral by construction (lands on the 29 side).",
+   "roi_bps": null,
+   "raised": "2026-08-13T09:02:41.722384+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0600",
+   "source": "cycle",
+   "summary": "Build a point-in-time universe from git history of hardcoded ticker lists in public repos: answers the recorded 'exchangeInfo is a look-ahead in the UNIVERSE' gap. Measured 8.7% true USDT survivorship erasure over 2023-03 -> today, and separates RENAMES (MATIC->POL, RNDR->RENDER, TOMO->VIC -- continuing series) from DELISTINGS, which the desk currently has no artifact to distinguish. Cost: a directory of old repos and a diff. (universe map source 103)",
+   "roi_bps": null,
+   "raised": "2026-08-13T09:02:47.010621+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
```


---

## d68fab05 BR miner 08-13 s3: a live BR pairs screen refuted by measurement (17.97% vs its own nominal 5%)
Vido/zecontinha, Apache-2.0, live and broadcasting to Telegram, takes its
cointegration p-value from adfuller(OLS.resid) -- the Engle-Granger
critical-value error. Measured rather than asserted: 4,000 trials, two
independent random walks, n=120 (their broadcast window) -> 17.97%
rejections against nominal 5%; statsmodels.coint() gives 7.60%. -> OP-077,
graveyard zecontinha_eg_pairs_screen.

The family is NOT killed, and that is the consequential half: the desk's
breadth lesson hard-kills DIRECTIONAL cross-sectional mechanisms at 1.54
independent bets, but a cointegration pair is beta-neutral by construction
and lands on the 29 side. STATISTICAL-ARBITRAGE (THIN, n=1 of 14) is thin
for instrument reasons, not verdict reasons.

Also: fork tree EXHAUSTED as an honest null (8 listed, 6 live, 0 ahead, 2
tombstone 404s a walker would silently drop; ?path= rename-blind, 3 commits
reported vs 11 true) -> OP-078. A free point-in-time universe from git
history of a hardcoded ticker list -> universe source 103, honest number
8.7% USDT survivorship erasure (not the headline 25.8%: 40 of 55 absentees
are the BUSD wind-down) with 3 rebrands that a symbol diff misreads as
deaths. TCC graded precision-not-recall, correcting s2's prediction ->
OP-081. One TCC backtest recomputed +8.78% -> +5.87% from its own left-open
file -> OP-082. Video 1 fetched / 3 locked, refuting AR s2's same-day
'mega-viral only' boundary with a 13,297-view pass.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit d68fab05641852d7828e0582ec65baa5d7ea1640
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 09:01:46 2026 +0000

    BR miner 08-13 s3: a live BR pairs screen refuted by measurement (17.97% vs its own nominal 5%)
    
    Vido/zecontinha, Apache-2.0, live and broadcasting to Telegram, takes its
    cointegration p-value from adfuller(OLS.resid) -- the Engle-Granger
    critical-value error. Measured rather than asserted: 4,000 trials, two
    independent random walks, n=120 (their broadcast window) -> 17.97%
    rejections against nominal 5%; statsmodels.coint() gives 7.60%. -> OP-077,
    graveyard zecontinha_eg_pairs_screen.
    
    The family is NOT killed, and that is the consequential half: the desk's
    breadth lesson hard-kills DIRECTIONAL cross-sectional mechanisms at 1.54
    independent bets, but a cointegration pair is beta-neutral by construction
    and lands on the 29 side. STATISTICAL-ARBITRAGE (THIN, n=1 of 14) is thin
    for instrument reasons, not verdict reasons.
    
    Also: fork tree EXHAUSTED as an honest null (8 listed, 6 live, 0 ahead, 2
    tombstone 404s a walker would silently drop; ?path= rename-blind, 3 commits
    reported vs 11 true) -> OP-078. A free point-in-time universe from git
    history of a hardcoded ticker list -> universe source 103, honest number
    8.7% USDT survivorship erasure (not the headline 25.8%: 40 of 55 absentees
    are the BUSD wind-down) with 3 rebrands that a symbol diff misreads as
    deaths. TCC graded precision-not-recall, correcting s2's prediction ->
    OP-081. One TCC backtest recomputed +8.78% -> +5.87% from its own left-open
    file -> OP-082. Video 1 fetched / 3 locked, refuting AR s2's same-day
    'mega-viral only' boundary with a 13,297-view pass.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 data/data_universe_map.json              |  14 +-
 docs/graveyard.md                        |  61 +++++++
 docs/research/improvement_inbox.md       |  50 ++++++
 docs/research/prospector_coverage.md     | 296 ++++++++++++++++++++++++++++++-
 docs/research/search_operator_library.md | 232 +++++++++++++++++++++++-
 docs/research/video_locked_log.md        |  46 +++++
 6 files changed, 696 insertions(+), 3 deletions(-)

diff --git a/data/data_universe_map.json b/data/data_universe_map.json
index 0571155e..cc4644cc 100644
--- a/data/data_universe_map.json
+++ b/data/data_universe_map.json
@@ -1128,6 +1128,18 @@
    "decisive_test": "Point-in-time fee regime per symbol from Binance's announcement archive, then (a) test whether volume/volatility elasticity differs between promo-fee and normal-fee names, which is the practitioner's own diagnostic, and (b) re-run any live volume-based feature with promo-fee names excluded and compare. THE LOOK-AHEAD TRAP IS NAMED IN ADVANCE: today's fee schedule applied to history is a look-ahead in the CONDITIONING variable -- the same defect class as pct_circ_now (R0289) and the RFB vintage stack, and it fails toward a FALSE NULL, the direction no gate here catches.",
    "provenance": "SOURCE: gitan.dev (seekseek77), 'ビットコインbotterにとっての各マーケットの特徴', 2023 and 2024 editions. DERIVES-FROM: NONE (checked) -- the posts cite no paper, no repo and no other writeup; they are first-hand venue observation by an operator who trades them. Pre-2023 for the first edition and no LLM disclosure in either (OP-072 checked).",
    "residual_gap": "The practitioner's evidence is JP venues; the Binance analogue is ASSERTED here, not measured. The first task is to establish that a promo-fee cohort exists on the desk's own panel with a recoverable point-in-time history -- if the announcement archive does not support point-in-time reconstruction, this axis is UNMEASURABLE rather than dead, and must be recorded that way."
+  },
+  "103-pit-universe-from-repo-git-history": {
+   "source": "103-pit-universe-from-repo-git-history",
+   "url": "https://github.com/Vido/zecontinha (Apache-2.0) — file coint/binance_futures.py, 11 commits 2020-06-28 -> 2025-11-21 across TWO paths (pre/post a src/ move) | live control: https://fapi.binance.com/fapi/v1/exchangeInfo",
+   "provides": "A POINT-IN-TIME VENUE UNIVERSE, reconstructed for free from the git history of a hardcoded ticker list in a public repo. THE DESK GAP THIS ANSWERS IS ALREADY ON THE RECORD: 'exchangeInfo is a look-ahead in the UNIVERSE' (free-data-miner 2026-08-12) -- the live endpoint returns TODAY's symbol set and nothing else, so any backtest that builds its universe from it silently excludes every name that has since been removed. A stale hardcoded list is the inverse artifact: it is a DATED ATTESTATION that a set of symbols was tradeable when it was written, and git history turns one such file into a TIME SERIES of universes. MEASURED HERE (vintage -> names absent from live exchangeInfo, 865 symbols / 731 TRADING): 2020-06-28 n=25 -> 1 gone; 2023-03-07 n=213 -> 55 gone; 2023-12-05 n=202 -> 50; 2025-11-14 n=199 -> 48.",
+   "the_number_that_matters": "8.7% TRUE USDT-perp survivorship erasure, NOT the headline 25.8%. Of the 55 names in the 2023-03-07 vintage now absent, 40 are BUSD-quote pairs killed by the BUSD wind-down -- a QUOTE-CURRENCY retirement, not a delisting -- leaving 15 of 173 USDT names = 8.7%. AND 3 OF THOSE 15 ARE REBRANDS WITH A CONTINUING PRICE SERIES, confirmed against live exchangeInfo: MATICUSDT->POLUSDT (TRADING), RNDRUSDT->RENDERUSDT (TRADING), TOMOUSDT->VICUSDT (SETTLING). So ~6.9% genuine removal + ~1.7% rename. A RENAME AND A DELISTING ARE OPPOSITE EVENTS THAT LOOK IDENTICAL IN A SYMBOL-SET DIFF: treat a rename as a death and you book a phantom delisting; ignore it and you sever a live series.",
+   "how_to_use": "(1) As a SURVIVORSHIP CONTROL: any universe built from live exchangeInfo is missing ~7% of the 2023 USDT cross-section by construction, and the missing names are non-random (they died). (2) As a RENAME MAP: the diff between adjacent vintages proposes rename candidates that are then confirmed one call at a time against exchangeInfo status. (3) GENERALISES FLEET-WIDE AND COSTS NOTHING: every region has repos with hardcoded symbol/ticker lists, and every one of them is a dated universe snapshot its author never intended to publish. The older and DEADER the repo, the better the vintage -- this is the one axis where an abandoned repo beats a maintained one.",
+   "limits_stated_honestly": "This is an AUTHOR's universe, not the exchange's: it is a LOWER BOUND on what was listed (names in it existed) and says nothing about names the author omitted. It is evidence of EXISTENCE at a date, never of COMPLETENESS. Also: the obvious commits?path= query returns only 3 of the 11 commits because it is rename-blind (OP-078) -- query the pre-move path or mis-date the whole series.",
+   "cost": "free, keyless, public; §13 Apache-2.0 (permissive, redistribution allowed with attribution)",
+   "status": "MEASURED this run; no ingest built (research freeze). Candidate axis, not yet collected.",
+   "date": "2026-08-13",
+   "found_by": "BR frontier miner s3"
   }
  },
  "residual_gaps_unpurchasable": [
@@ -1161,4 +1173,4 @@
  "last_free_dig": "2026-07-22T23:21:50.541800+00:00",
  "overlap_corrected": "2026-07-22T23:46:26.342668+00:00",
  "last_genuine_dig": "2026-07-26 [T1-a] kaiko"
-}
+}
\ No newline at end of file
diff --git a/docs/graveyard.md b/docs/graveyard.md
index 08f84d94..6ee64be4 100644
--- a/docs/graveyard.md
+++ b/docs/graveyard.md
@@ -1185,3 +1185,64 @@ checks TARGET-distribution stationarity.** That is a live gap on this desk too a
 `improvement_inbox.md`, not left in the graveyard. (His own claim that his filter rescues a down-sloping base
 rule "thanks to property ②" is **unverified** — a practitioner assertion with no shared code or data, recorded
 as claimed, never as evidence.)
+
+---
+
+## `zecontinha_eg_pairs_screen` — REFUTED AT SOURCE, by measurement, before any desk compute was spent
+**Killed:** 2026-08-13, BR frontier miner s3. **Class:** STATISTICAL-ARBITRAGE (the desk's thinnest
+family — `data/strategy_coverage.json`: THIN, n=1 of 14). **Tier:** EXECUTABLE (code + params + a live
+deployment), which is why it could be settled in an afternoon rather than argued about.
+
+**SOURCE:** `github.com/Vido/zecontinha` (Apache-2.0, 14★, 8 forks listed / 6 live, active 2019→2026-02),
+live at `zecontinha.com.br`, broadcasting to the public PT-BR Telegram `@pythonfinancas`.
+**DERIVES-FROM:** Engle–Granger (1987) two-step, via the standard BR retail *"Long&Short"* pairs
+literature; no paper cited in-repo. The implementation is conventional, not novel — **which is the point:
+this kill is about the convention, not about one Brazilian hobbyist.**
+
+**THE PUBLISHED RULE, fully specified** (`src/bin/bot.py:select_pairs`): keep pairs with
+ADF `p < 0.05` **and** Hurst `< 0.3` **and** `|z| ≥ 2.0` at `periods=120`; rank by **lowest Hurst**;
+broadcast the top 3. Universe: a hardcoded 100-symbol Binance USDT-perp list → 4,950 pairs, each tested
+at **10 lookback windows** (`PERIODOS_CALCULO = range(60,260,20)`) = **49,500 tests per run**, with no
+multiplicity correction anywhere in the codebase.
+
+**THE KILL — MEASURED, not asserted** (4,000 trials, two *independent* random walks, n=120, seed 20260813):
+
+| gate as implemented | realised rejection rate under the null | nominal |
+|---|---|---|
+| `adfuller(sm.OLS(y, add_constant(x)).fit().resid)` | **17.97%** [16.8, 19.2] | 5% |
+| `statsmodels.tsa.stattools.coint(y, x)` (MacKinnon) | 7.60% [6.8, 8.4] | 5% |
+
+**The screen's 5% cointegration gate actually operates at 18% — 3.59× its own nominal size** (OP-077).
+The cause is textbook and unambiguous: ADF critical values do not apply to residuals of an *estimated*
+cointegrating vector, because OLS picked β to minimise exactly the variance the test then examines.
+Full published screen (ADF **and** |z|≥2) fires on **0.88%** of pure-noise pairs against 0.43% for the
+correctly-sized test → **≈44 spurious pairs per run at the broadcast window alone**, from which the bot
+publishes the 3 with the lowest Hurst — i.e. it ranks the survivors of a noise filter by a statistic
+(R/S Hurst at n=120) whose sampling error at that length is large. **Selection on noise, ranked by noise.**
+The null used is *independent* walks; co-moving perps make spurious residual stationarity more likely,
+so 17.97% is a **conservative floor**.
+
+**WHAT IS *NOT* KILLED, AND THIS MATTERS MORE THAN THE KILL** — I checked whether the desk's standing
+breadth objection applies here and **it does not**. The recorded desk lesson is *"the crypto cross-section
+is 1.54 independent bets RAW and 29 market-neutral … any **directional** cross-sectional mechanism is
+hard-killed by narrow_breadth before it starts — neutralise BTC beta or do not build it."* A cointegration
+pair is long *y* / short *βx*: **beta-neutral by construction**, so it lands on the **29** side, not the
+1.54 side. The breadth argument that ends every directional cross-sectional mechanism on this desk
+**is not an argument against this family** — it is closer to an argument *for* it. Routed to
+`improvement_inbox.md`; **no kill claimed**, and the family stays open.
+(Caveat recorded honestly: `reports/cross_section_breadth.json` is gitignored and **not readable from
+this checkout**, so the 1.54/29 figures are cited from the desk-lesson text, not re-verified here.)
+
+**WHAT SURVIVES THE KILL AND IS WORTH KEEPING:**
+1. **The correct instrument is one import away** — `coint()` vs `adfuller(resid)`. Any future desk
+   statarb work must use the former; this entry is the reason.
+2. **Half-life and Hurst as *descriptors*, not gates** — the repo computes an OU half-life
+   (`-ln2 / β` from Δs on lagged s) and publishes it beside every pair. Sound construction, wrong role:
+   it is a ranking input here, and ranking thousands of candidates by a noisy in-sample statistic is
+   the selection problem again.
+3. **A free control arm** (OP-080): the same channel broadcast a **uniform random draw** before
+   PR #30 (2025-11-06) and a screened selection after — a dated, public, timestamped random-selection
+   baseline for pair trading. Whoever tests a pairs screen here has the "does it beat a hat?" arm already.
+
+**COST OF THIS KILL: one afternoon of Monte Carlo, zero desk data, zero forward slots.** Pre-emptive
+falsification of a mined artifact is free graveyard material and this is what it looks like.
diff --git a/docs/research/improvement_inbox.md b/docs/research/improvement_inbox.md
index b777aeb7..14646b5e 100644
--- a/docs/research/improvement_inbox.md
+++ b/docs/research/improvement_inbox.md
@@ -2323,3 +2323,53 @@ from a seat with write access to `scripts/` settles it.
 EN crypto videos at 142k / 50k / 33k views wall identically to AR videos at 538k / 47k / 31k. Language is
 orthogonal; only a ~1.6bn-view control passed. Full table and the GAP #26 consequence in
 `docs/research/video_locked_log.md`.
+
+---
+
+## 2026-08-13 — BR frontier miner s3: STATISTICAL-ARBITRAGE is thin for INSTRUMENT reasons, not verdict reasons
+
+**THE OBSERVATION.** `data/strategy_coverage.json` reports STATISTICAL-ARBITRAGE as **THIN, n=1 of
+14** — the desk's least-worked family. Mining the BR corpus for it, I checked the standing objection
+that would justify leaving it there, and **it does not apply**.
+
+**THE DESK'S OWN BREADTH LESSON, READ CAREFULLY:** *"the crypto cross-section is 1.54 independent bets
+RAW and 29 market-neutral. Any **directional** cross-sectional mechanism is hard-killed by
+narrow_breadth before it starts — neutralise BTC beta or do not build it."* A cointegration pair is
+long *y* / short *βx*: **beta-neutral by construction.** It therefore lands on the **29** side of that
+measurement, not the 1.54 side. **The argument that ends every directional cross-sectional mechanism
+on this desk is not an argument against this family — it is closer to an argument for it.**
+*(Caveat: `reports/cross_section_breadth.json` is gitignored and unreadable from this checkout, so
+1.54/29 are cited from the desk-lesson text and were not re-verified here.)*
+
+**AND THE INSTRUMENT THE FAMILY NEEDS IS ONE IMPORT.** The refutation I filed today
+(`graveyard.md: zecontinha_eg_pairs_screen`, OP-077) measured a live public pairs screen rejecting
+**17.97%** of pure-noise pairs against its own nominal 5%, because it took p-values from
+`adfuller(OLS.resid)`. **Any desk statarb work must use `statsmodels.tsa.stattools.coint()`**, whose
+MacKinnon critical values are derived for residuals of an *estimated* cointegrating vector. Measured
+side by side on n=120: 17.97% vs 7.60%. Note also that the correct test is itself **7.6% at n=120**,
+not 5% — short windows are not exact even done right, which is worth knowing before anyone sets a bar.
+
+**A SECOND, ORTHOGONAL SELECTION STATISTIC, ARRIVING FROM TWO BR SOURCES:** rank candidate pairs by
+the **stability of the rolling hedge ratio** (`beta_rotation`), not by the in-sample ADF p-value. It
+appears as a code function in `Vido/zecontinha` (`analysis.py`, window=40) and as the stated primary
+criterion of a PT-BR practitioner (*"beta rotation mais estável"*, video `vaDLuXYDSJ8`). The argument
+is mechanical rather than statistical — **an unstable β means the cointegrating relationship is not
+structural** — which is exactly the property an in-sample p-value cannot see.
+**PROVENANCE, STATED SO IT CANNOT BE MISREAD AS CONVERGENCE:** both sources sit inside the **same BR
+retail "Long&Short quantitativo" teaching tradition. This is ONE ecosystem node, not two**, and under
+GAP #85 it elevates nothing. It is a lead of exactly singleton weight.
+
+**NOT PROPOSED FOR CAPITAL, AND NOT SCREENED.** This is a note that a thin family is thin for
+correctable instrument reasons. Under the two-stage law it would owe a pre-registered screen and then
+a forward clock; neither is claimed here.
+
+## 2026-08-13 — BR miner s3: a cheap point-in-time universe the desk does not build
+
+`exchangeInfo` returns **today's** symbol set, which the desk has already recorded as *"a look-ahead in
+the UNIVERSE"*. **Git history of hardcoded ticker lists in public repos is a free, dated substitute**
+(universe map source **103**). Measured on one repo: vintages at 2020-06-28 / 2023-03-07 / 2023-12-05 /
+2025-11-14, and **8.7% of the 2023 USDT-perp cross-section is absent from live exchangeInfo** — of
+which **3 names are rebrands with a continuing price series** (MATIC→POL, RNDR→RENDER, TOMO→VIC), not
+deaths. **A rename and a delisting are opposite events that look identical in a symbol-set diff**, and
+the desk currently has no artifact that distinguishes them. Cost to build: a directory of old repos and
+a diff. No ingest built (research freeze).
diff --git a/docs/research/prospector_coverage.md b/docs/research/prospector_coverage.md
index 6ab98275..27a1d21e 100644
--- a/docs/research/prospector_coverage.md
+++ b/docs/research/prospector_coverage.md
@@ -19,7 +19,7 @@ _Seeded 2026-07-18; every family unvisited -- the first run biases per the rotat
 | Records (contests/CTA) | 2026-07-25 | 1 | partial, via forum route: Bitcointalk "Automated Trading Contest" (topic 261086, CryptoTrader.org rounds #1-#5) mined as a contest RECORD — produced the in-sample-vs-forward natural experiment graveyard entry. Kaggle G-Research + Numerai post-mortems still untouched |
 | Non-English forums | 2026-07-26 | 2 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. **s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031 CDX-replay of a capped JSON API), Stage-A screened 4/4 cells → no promotable edge but the catalogued mechanism's SIGN and MAGNITUDE priors both falsified. New: OP-031, OP-032, CN lexicon.** Era-archaeology (banzhuan/8btc/ChainNode/Tieba) still UNSTARTED — first item next run. **s3 (2026-08-01): T1 instrument repair — the 7 supplied unverified slang terms negative-controlled, 0/7 survived, 6 with the real form named; +14 verified lexicon rows; OP-036 (evasion slang has a BIRTH DATE — 大饼 born of the 2017-09-04 "94" ban, so the search key is a function of the ERA, and our era ground straddles it), OP-037 (negative-control a supplied glossary), OP-038 (a JS wall on the HTML is not a wall on the API — unblocked the Gitee chain carried 3 sessions). CN OSS tranche: AlphaGPT paper + NOFX "3 mechanisms" both REFUTED, Vibe-Trading crypto layer weaker than ours (honest null). Screened `unlock_events.json` (24,201 events, 0 readers) 0/27 cells → UNMEASURABLE not dead, 2 measurement defects. VERIFIED on live API: a 123-event Binance delisting forced-close panel discarded by a `status=="TRADING"` filter (R0292). R0288–R0293. Era: 8btc thread-44638 mined to reply-depth, CN-side corroboration of the cross-venue-premium kill. DIASPORA ANSWERED: CN discussion migrated into paid/ID-gated enclosures — §13 puts it permanently out of reach, so the open CN layer worth mining is repos + era archives + platform 文库, NOT live community.** |
 | Non-English forums — **JP** | 2026-08-13 | 4 | **s4 (2026-08-13, JP frontier miner): THE DEEP-FOREST SELF-HOSTED TAIL OPENED — after 08-12 closed 62% of the mapped corpus, a UA-matrix probe over 10 hosts found **8/9 self-hosted botter blogs serve 200 to ClaudeBot and 4 have no robots.txt at all** → **OP-073** (an AI-crawler denylist is a PLATFORM product decision; re-scope the HOST COLUMN, never the region — the JP ground went from "thinning" to a fresh 20-entry queue across 12 open domains with one group-by). **zenn.dev sharpened the §13 finding into its worst form: robots.txt now returns 200 AND explicitly allows `*`, while the content path returns 403 — every standard §13 check comes back green and permissive over a closed ground.** **OP-072, the run's best find and fleet-wide: the post-2023 practitioner corpus is LLM-CONTAMINATED** — the mined options post's entire mechanism analysis is self-disclosed ChatGPT output (チャッピー), so practitioners in unrelated regions now converge because they queried the same weights, not because the world taught them; worse than the arXiv echo GAP #85 models (a paper echo leaves a citation, an LLM echo leaves nothing), fixed by per-region markers + an observation/explanation split + `NONE (checked)` made illegal post-2023 (→ UNVERIFIABLE), and it hands era-archaeology a new argument: **pre-2023 archives are structurally uncontaminated.** MINING: `blog_UKI`'s BitMEX spoofing **intervention** (not an observation) decomposes OFI → **the market-order take components dominate; the displayed book is not where the information is**, so `book imbalance` and `aggressor flow` may be ONE axis and the desk's L1.18 independence count too high by one (EV 0.0002 REJECT as a trade → routed to improvement_inbox as a feature-redundancy fact; the strategy is prohibited conduct and is not proposed). `pip_pip_pip_p` **corroborates the 08-01 richmanbtc kill from the opposite fee sign** (the rule-based core is down-sloping on Binance in every period since 2021, incl. the 2024-11/12 bull) + names a live desk gap: **the desk checks FEATURE-distribution stationarity, apparently never the TARGET's**. `gitan.dev`'s 2023↔2024 venue-survey **pair** (a free longitudinal diff) → **WS-013**: a 13-month +2% JP margin dislocation, a venue REPLACING an SFD divergence penalty with a funding rate, and its resting long-pays-short constant **numerically identical to Binance's 0.01%/8h interest component** — an independent venue corroborating this seat's 08-12 clamp census that the 1bp print is a copied CONVENTION. Graveyard ×1 (`rev_calendar_spread_iv_convergence`, refuted at source: vega-neg + theta-neg has no favourable regime; its transferable half is **a hedged leg with a contractual expiry un-hedges itself on a schedule** — a risk-rail event for any future dated-future-vs-perp basis trade). Universe source **102** (venue fee schedule as the conditioning variable for every volume feature; EV 0.0058 QUEUE, the session's only gate survivor of 4 scored). +8 OBSERVED JP lexicon rows (鞘/アビトラ/見せ板/お蔵入り/反面教師/チャッピー/限月/爆損). **Self-caught defect: my own 08-12 next-run queue was 40% dead on arrival** — titled "qiita-hosted", it named 3 zenn.dev entries I had ruled HARD STOP in the same note. Video: 0 fetched, 0 locked.** —  **s3 (2026-08-12, JP frontier miner): §13 REGRESSION — note.com + zenn.dev now serve 403 to ClaudeBot/GPTBot/CCBot/Bytespider AT THE CDN EDGE while BOTH robots.txt files are clean of any such rule (Googlebot/curl/SomeRandomBot get 200 ⇒ a curated AI-crawler denylist, not a WAF heuristic). HARD STOP, archives included; NOT routed around (Claude-User returns 200 and was deliberately not used). Closes 116/187 (62%) of the mapped botter corpus incl. all 3 planned targets; rollout DATED between 08-04 and 08-12 by this seat's own successful prior reads → **OP-052** (probe the CONTENT PATH with a UA matrix; robots.txt is necessary, not sufficient) + lesson **L0096** + **R0466** (a blocked ground and an exhausted ground are byte-identical to any fetch path that treats non-200 as no-content — a FALSE NULL that silently retires a region). **Past-due PI-vs-FR deferral RESOLVED** (`data/jp_funding_clamp_census.json`): clamp verified by positive control (BTC 49/60, DOGE 46/60); **41.6% of the owned 8h panel and 68.8% of the live 812-symbol cross-section sit on a censoring constant**, 74.9 bps of real premium dispersion hides inside one 56-name tie group — the root cause of the already-paid-for "42 perps at the 1bp floor" churn incident; censoring DECAYS 68.8%(2019)→10.7%(2026) ⇒ **backtest-integrity upgrade first, live-signal second**; EV 0.0193 QUEUE, novelty 0.726, NOT promoted (screen still owed). **L1.47 corroborated with a count → R0465: 426/812 (52.4%) of live perps settle on 4h, only 385 on the 8h that `held/8.0` assumes** ("many" is the majority); ranking damage honestly modest (Spearman 0.959). JP funding-settlement sandwich (qiita/lud-botter, DERIVES-FROM: NONE checked ⇒ genuine independent convergence with L1.47) **EV 0.0006 REJECT** as published — dead at source, venue changed settlement rules mid-operation — with the observation routed as execution-timing **EV 0.0087 QUEUE**; JP **Travel Rule 2023-06-01** era marker (domestic↔overseas arb killed by regulation, not competition). **マケデコ (`market-api`) NEW GROUND opened + mapped: 74 entries 2023–2025 (2021/22 = 404, series began 2023), JP EQUITIES not crypto, 74% on the closed hosts**; J-Quants axis catalogued-unverified (row 29). Video: 0 fetched, 0 locked.** — **s1 (2026-08-01, JP frontier miner, seat's first run).** §13: **5ch.net + all sister hosts REFUSE `ClaudeBot` by name** (Cloudflare-*managed* block → treat as a platform rollout, not a site decision; re-check on entry, never cache); note/qiita/zenn/GMO/bitbank clean. **bitFlyer axis CLOSED after 4 deferrals** — the "403/WAF/needs-a-human" record was a **tarpit**, the block is **per-hostname** (api+lightning serve 200 from the *same edge IP*), the "never archived" claim was a wrong CDX host+slug, and the ToS was then read: it retains rights in *"data such as transaction prices"* → **`restricted-by-licence`**, which pre-emptively killed `getchats`, `getfundingratehistory` and an archived keyless 15-min BTC/JPY series (2014-10→, Wayback-only) before any were carded. **Replacements found same run: GMO Coin free keyless tick tape (2018-09-05→, 28 spot + 12 margin, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank — both licence-unread, no ingest (R0309/R0310).** **richmanbtc lineage (the C62 "gem", unstarted 12 days) KILLED**: the edge is a bare ATR×0.5 limit, the ML adds ~nothing, and the maker fee was **zero-or-negative across the whole backtest** → a venue-subsidy harvest, dead on 3 venues. Salvaged 3 CC0 tools (p-mean order-sensitive decay bar — **published error-rate formula reproduced BROKEN**; time-adversarial feature screen; `publicGetExpiredFutures` for R0239). New: **OP-043/044/045** + OP-041 refinement. Era-archaeology (2017 bitFlyer-FX **SFD**, Mt.Gox 5ch) **UNSTARTED**; JP lexicon seeds still **unverified**. Next: **the 仮想通貨botter Qiita Advent Calendar 2021–2025, never touched.** |
-| Non-English forums — **BR** | 2026-08-12 | 2 | **s2 (2026-08-12) — THE NATIVE KEY WAS HIDING THE DESK'S ONLY NEVER-HUNTED FAMILY.** Cleared s1's 8-day-overdue ITEM 3. Measured, same corpus same minute: `pairs trading brasil` → **0 repos**, `cointegração` (native PT key) → **30**, essentially all genuine statarb, several crypto-native — so a seat querying the English term grades BR statistical arbitrage DEAD on a clean zero, and `strategy_coverage.json` reports **STATISTICAL-ARBITRAGE as the only never-hunted family (0/14)**. `long short` is unusable bare in PT-BR via **two independent collisions** (LSTM written out in full; C's `unsigned long/short`) — the vocabulary sibling of the RU ticker collision. **OP-054.** Depth on `mateusmartinelli/tcc` (crypto pairs trading; Gatev + Caldeira–Moura + Rad–Low–Faff): more rigorous than average (loads T-bills, computes excess returns) yet **three code/comment contradictions all in the config block** — cost 0.001 commented "0.05%" (**2×**, conservative), entry **1.5σ** commented "2σ as per paper" (**not** conservative), formation **90d** commented "252" — plus **zero funding accounting** and top-10 pairs from ~4,950 candidates at p<0.10 with **no multiplicity correction** (~495 expected false pairs). **OP-055.** Killed `pedhsm/systematic-research-framework`'s MCPT: it permutes **realised returns** and scores sharpe/cagr/vol, **all order-invariant** — verified by independent reimplementation, 500 perms × 4 series, **max−min = 1.1e-15**; FP non-associativity then makes the p-value a rounding-order hash (**winner p=0.978, catastrophe p=0.618**). A **wall, not a bar** → graveyard + **OP-056**. **The desk was already ahead** (`bar_permutation.py` permutes bars, with a measured `_TIE_RTOL` + add-one) ⇒ genuine cross-ecosystem convergence, **NO BUILD**. RFB: s1's *"decaying deadline"* was an inferred rate — census gives **23 dates, 12 live / 12 dead, clean boundary at 2023-03-02|2023-05-03, 4 with no capture at all**; **rate UNMEASURED** (two rival hypotheses, opposite urgency, falsifier recorded) and the series is **~4 months unpublished against a 13-month hiatus precedent**. BR lexicon opened (none existed); supplied seeds scored **0/3 as dark-forest keys**. Video: **0 fetched, 0 locked — not attempted**, named in next ground. Next: `Vido/zecontinha` fork tree + crypto subset, `TCC` as a structural key, PT-BR video, B3 (still unprobed), era-archaeology (still not started). |
+| Non-English forums — **BR** | 2026-08-13 | 3 | **s3 (2026-08-13) — THE MINED SYSTEM WAS REFUTED BY MEASUREMENT, AND THE FAMILY SURVIVED THE OBJECTION THAT SHOULD HAVE KILLED IT.** `Vido/zecontinha` (Apache-2.0, live at `zecontinha.com.br`, broadcasting to Telegram) takes its cointegration p-value from `adfuller(sm.OLS(y,x).fit().resid)` — the textbook Engle–Granger error — so I ran their exact window as a null instead of asserting it: **4,000 trials, two independent random walks, n=120 → 17.97% [16.8,19.2] rejections against its own nominal 5%; `statsmodels.coint()` gives 7.60%. 3.59× nominal.** Full published gate (ADF `p<.05` ∧ `|z|≥2`) fires on 0.88% of pure noise ⇒ **≈44 spurious pairs/run** over 4,950 pairs × **10 unrcorrected lookback windows (49,500 tests/run)**, from which the bot publishes the **3 lowest-Hurst** — noise filtered, then ranked by noise (**OP-077**, graveyard). **THE COMMENT LAYER PAID BEST:** nothing on the surface says what the maintainer says in PR #30 — *"`select_pair(n)` was just a silly function to **draw a pair**… **Telegram folks see it as recommendations. Which they are NOT!**"* — the selection step was `order_by('?')`, **random ordering**; and because the switch to a screened rule is **dated** (PR #30, 2025-11-06), the channel's public history is **a random-selection control arm followed by a screened one, timestamped** (**OP-080**). **THE FAMILY IS NOT KILLED, and that is the run's most consequential line:** the desk's breadth lesson hard-kills *directional* cross-sectional mechanisms at **1.54 independent bets**, but a cointegration pair is long *y* / short *βx* — **beta-neutral by construction**, so it lands on the **29** side. STATISTICAL-ARBITRAGE (THIN, n=1 of 14) is thin for **instrument** reasons, not verdict reasons → improvement_inbox, **no kill claimed**. **FORK TREE EXHAUSTED — HONEST NULL:** `forks_count:6`, `/forks` returns **8**, **zero ahead** by one commit; the 2 extras are **tombstone 404s** that any walker treating non-200 as "skip" silently drops (L1.60 attrition on a *mining* instrument), and `?path=` is **rename-blind** — 3 commits reported vs **11 true** (**OP-078**). **A FREE POINT-IN-TIME UNIVERSE (source 103):** git history of a hardcoded ticker list = dated universe vintages, answering the desk's own *"`exchangeInfo` is a look-ahead in the UNIVERSE"*; honest number **8.7% true USDT survivorship erasure, not the headline 25.8%** (40 of 55 absentees are the **BUSD wind-down**, a quote-currency retirement), and **3 of the 15 are rebrands with a continuing series** (MATIC→POL, RNDR→RENDER, TOMO→VIC) — **a rename and a delisting are opposite events that look identical in a symbol diff**. **s2's "RICH SEAM" prediction CORRECTED:** `TCC` is a **precision key, not a recall key** — `TCC bitcoin` 29 / `TCC trading` 18 but `TCC cointegração` **1** vs **30** for `cointegração` alone, so genre ∩ topic ≈ ∅ (**OP-081**, union never AND); `dissertação trading` = a measured **0**, and student repos are disproportionately **vendored framework forks** so counts overstate. One TCC repo mined to its result layer: headline **87.1% win rate / +8.78%** vs a **separate** left-open file holding **13 losers to 1 winner** ⇒ **true +5.87%, a 49.6% overstatement** (**OP-082**; mechanism `sell_profit_only` labelled a hypothesis because config and strategy contradict each other — the 4th OP-055 instance in this corpus). **VIDEO: 4 probed, 1 fetched, 3 locked — and the fetch REFUTES AR s2's same-day boundary:** a **13,297-view** PT-BR practitioner video passes while AR at 538k/234k/47k and EN at 142k/50k/33k fail, so *"mega-viral only"* is wrong; **3/3 persistent retries** kill the "temporarily blocked" reading too — it is a **stable per-video** property, **UNMEASURED** as to cause, and GAP #26 should measure the blocked **fraction**, not assert a **class**. R0592 still live: all 6 wrapper calls printed a **dead-domain DNS error** for a YouTube bot-wall. +5 BR lexicon rows (**prazo** = lookback window, **beta rotation** used untranslated inside PT, **enquadrado**, dissertação-negative). Venue found by reading repo code: **`@pythonfinancas`** Telegram. Next: the **`berlinguyinca` 30-strategy collection with vendored OHLCV beside it** (EXECUTABLE tier), the crypto-native Johansen/VECM subset, B3 (**unprobed after 3 sessions**), era-archaeology (**still not started**). || **s2 (2026-08-12) — THE NATIVE KEY WAS HIDING THE DESK'S ONLY NEVER-HUNTED FAMILY.** Cleared s1's 8-day-overdue ITEM 3. Measured, same corpus same minute: `pairs trading brasil` → **0 repos**, `cointegração` (native PT key) → **30**, essentially all genuine statarb, several crypto-native — so a seat querying the English term grades BR statistical arbitrage DEAD on a clean zero, and `strategy_coverage.json` reports **STATISTICAL-ARBITRAGE as the only never-hunted family (0/14)**. `long short` is unusable bare in PT-BR via **two independent collisions** (LSTM written out in full; C's `unsigned long/short`) — the vocabulary sibling of the RU ticker collision. **OP-054.** Depth on `mateusmartinelli/tcc` (crypto pairs trading; Gatev + Caldeira–Moura + Rad–Low–Faff): more rigorous than average (loads T-bills, computes excess returns) yet **three code/comment contradictions all in the config block** — cost 0.001 commented "0.05%" (**2×**, conservative), entry **1.5σ** commented "2σ as per paper" (**not** conservative), formation **90d** commented "252" — plus **zero funding accounting** and top-10 pairs from ~4,950 candidates at p<0.10 with **no multiplicity correction** (~495 expected false pairs). **OP-055.** Killed `pedhsm/systematic-research-framework`'s MCPT: it permutes **realised returns** and scores sharpe/cagr/vol, **all order-invariant** — verified by independent reimplementation, 500 perms × 4 series, **max−min = 1.1e-15**; FP non-associativity then makes the p-value a rounding-order hash (**winner p=0.978, catastrophe p=0.618**). A **wall, not a bar** → graveyard + **OP-056**. **The desk was already ahead** (`bar_permutation.py` permutes bars, with a measured `_TIE_RTOL` + add-one) ⇒ genuine cross-ecosystem convergence, **NO BUILD**. RFB: s1's *"decaying deadline"* was an inferred rate — census gives **23 dates, 12 live / 12 dead, clean boundary at 2023-03-02|2023-05-03, 4 with no capture at all**; **rate UNMEASURED** (two rival hypotheses, opposite urgency, falsifier recorded) and the series is **~4 months unpublished against a 13-month hiatus precedent**. BR lexicon opened (none existed); supplied seeds scored **0/3 as dark-forest keys**. Video: **0 fetched, 0 locked — not attempted**, named in next ground. Next: `Vido/zecontinha` fork tree + crypto subset, `TCC` as a structural key, PT-BR video, B3 (still unprobed), era-archaeology (still not started). |
 | _(BR s1 history)_ | 2026-08-01 | 1 | **s1 (2026-08-01, BR frontier miner, seat's first run).** **§13: the KR/JP by-name-block pattern does NOT generalise** — 18 hosts swept full-file over 17 AI-crawler tokens, **zero BR blocks**; the community layer (bastter, InfoMoney, MQL5-PT, Investing BR, bitcointalk, YouTube, Telegram) is **open**, so KR/JP was a property of *those* consumer portals, not a global rollout (OP-041 corrected). One **HARD STOP: `reddit.com` `Disallow: /`** to everyone — a *global* decision that bites BR hard (r/investimentos, r/farialimabets, r/BrasilBitcoin). **Pre-emptive graveyard check killed one third of my own brief before any searching:** the seat's era target "BR P2P premium" is already `mercado_br` **REJECTED** (graveyard:81) inside a family killed **5×** whose lone survivor (kimchi) was itself refuted 07-30 — no L1.16a enabling change exists, so the **seed list** is the defect. **THE FIND: RFB `criptoativos_dados_abertos`** — Brazil's **mandatory** national crypto-reporting panel (every domestic exchange reports **every** operation, no minimum; P2P + foreign venues >R$30k), free and keyless: **77 months Ago-2019→Dez-2025, 66 assets, 4,206 asset-months**; Dez-2025 = **3,544,986 taxpayers / R$43.1bn**; all-time **USDT R$1.004tn vs BTC R$269bn (3.7×)** ⇒ a **dollarization**, not speculation, mechanism. **Deliberately NOT screened** — n=77 monthly + 3.5mo lag vs a ~4,268-obs bar would manufacture a false null (L1.25); reported **UNDERPOWERED** with the cross-sectional enabling change named. **The depth layer was the prize: a FREE POINT-IN-TIME VINTAGE STACK** — RFB republishes monthly under a dated filename and **42/42 common months are revised** (worst Março-2023 **+40.9%**; a month **2.4y old** still moved), systematically upward, so backtesting today's file is a **+41% look-ahead in the CONDITIONING variable** (R0289 class — passes every return-series leak check, fails toward a FALSE POSITIVE). Proven recoverable: 23+ dates in CDX, and a **live-404 vintage restored intact** via `web.archive.org/<ts>id_/`. Read at all only by writing a **stdlib OLE2+BIFF8 reader** (no xlrd on this box) validated by the data's **own conservation law: 78/78 rows, residual 0.00e+00**. New **OP-046 / OP-047 / OP-035-BR**; R0316–R0318. Incidental: a **BR-only tokenized-RWA universe** in a government dataset (**MBPRK = tokenized *precatórios***, MBCONS, IMOB01, MCO2; **BRZ = 92.4M ops**, a payment rail). **ITEM 3 (PT-BR practitioner ground) explicitly DEFERRED to 08-04, not dropped.** Next: practitioner ground first, then **mirror the vintage stack before it decays**, B3, Pix fraud stats. |
 | Non-English forums — **AR** | 2026-08-13 | 2 | **s2 (2026-08-13) — THE SEAT IS RE-AIMED, on measurement.** (1) **`mql5.com/ar` DOES NOT EXIST** — MQL5 publishes 11 hreflang locales and `ar` is not one; `/{loc}/code` = 200 for 11/11 real locales, 404 for `ar` alone. s1 graded it OPEN **from robots.txt**, which answers *may I*, never *is there anything here* → **OP-074**. (2) **THE AR LANGUAGE IS NOT A MOAT** — AR-script repo search: arbitrage **1/0/0**, quant-trading **0**, EA **0**, all hits 0–1★ Telegram signal-bots, against **CN 1,174 / RU 24 / KR 6** on the same instrument. Discriminator by developer LOCATION: **UAE 67 > Korea control 59** (~99 AR-region devs) ⇒ population EXISTS and **writes in English**, so its output is already in the EN seat's ground → **OP-075**. **Not "the ground is thin"** — a precise verdict on ONE layer (AR-script *code*); the seat's edge must be what is native-language **by institutional construction** (regulators, exchanges, courts, the Sharia layer). (3) **VIDEO: 8 attempted, 1 fetched, 7 LOCKED — `video_locked_log.md` has its FIRST ROWS EVER**, and the **EN control** (142k/50k/33k views, walled identically to AR 538k/47k/31k) proves the block is **not regional**: GAP #26 must buy a **general** authenticated route. The log was empty because `fetch_video_transcript.py` reports only the LAST instance's error and that instance is a **dead domain** — a platform bot-wall displayed as a local DNS fault (R0592). **AR corpus is VIDEO-FIRST**, which is the natural complement to OP-075. See s2 session note. || **s1 (2026-08-12, seat's first run) — CLOSED.** No AR row existed before this run (`grep -ic arabic` = 0). **Pre-emptive graveyard check killed the seat brief's ENTIRE era target before any searching:** MENA/Egypt/Lebanon P2P-premium-under-FX-restriction is `era_crossvenue_fiat_premium_arb` (buried **7×**) inside the regional-premium class the desk declared **exhausted** (`try_premium_timing` — the Turkey capital-control analog, the closest MENA case that exists — REJECTED; kimchi, the lone survivor, itself KILLED 08-01); `strategy_coverage.json` has CROSS-VENUE-PREMIUM = HUNTED/9. Second consecutive seat (after BR) handed a dead era target ⇒ **the seed list is the defect**. Items: (1) §13 UA-matrix access map (OP-052) — AR unmapped in BOTH directions, and R0466 makes an unmapped ground's null uninterpretable; (2) report+replace the dead brief; (3) **replacement axis: Hijri/Ramadan calendar + Sharia-compliance forced-flow** — novelty-clean at **0 hits** across graveyard/both watchlists/universe map/vault, maps to NONE of the 24 CRYPTO_MECHANISMS, and lunar-vs-Gregorian drift (~11d/yr) makes it orthogonal to every Gregorian calendar effect by construction. See session note below. |
 | AI/HF documentation | 2026-07-19 | 1 | touched only incidentally via Vibe-Trading (AI trading-agent platform) + ai_quant_trade (LLM module) — both infra, not alpha-discovery-process documentation; weak coverage, revisit properly next run |
@@ -4069,6 +4069,300 @@ kill), `docs/research/data_axis_watchlist.md` (**entry 29 census update** correc
 claim), `docs/research/improvement_inbox.md`, `docs/research/recommendation_ledger.json`, and this
 coverage doc.
 
+### 2026-08-13 session 3 (BR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
+
+**RESUMING, NOT RESTARTING.** Read before searching: `source_backlog_next.py` (6 pending
+verification, 1 pending a legitimacy decision — **none BR**; the deferred queue holds exactly one
+BR row, RFB, dated **2026-09-05**, so it is not workable this cycle and the backlog does not
+redirect this seat), the BR region row, and my own s2 close, which left a **numbered, un-started
+next-ground queue of 6**. Nothing is past due: s2 deferred no dated item. So this run takes the
+top of its own queue in order.
+
+**ITEMS TAKEN THIS RUN (bounded per the completion contract; depth per item unbounded):**
+
+1. **`Vido/zecontinha` fork tree (6 forks, DIVERGED forks first) + the crypto-native subset of the
+   `cointegração` corpus** — s2's queue item 1. Aimed at **STATISTICAL-ARBITRAGE**, which
+   `data/strategy_coverage.json` still reports as the desk's **thinnest family (THIN, n=1 of 14)**
+   after s2's `mcpt_return_permutation` kill moved it off zero. L1.35: prefer a thin family over
+   deepening a worked one. Hunting **untested alphas** (L1.34 #6) and **process** alongside claims.
+
+2. **`TCC` as a structural search key** — s2's queue item 2. BR undergraduate/masters thesis code:
+   full replications, rigorous-looking, uniformly never out-of-sampled, and unread by the English
+   crowd. This is a **structural** key (a document-type, not a topic), so it is the kind of key
+   that transfers to every region with a named thesis genre — the operator-library half matters
+   more than any single repo it returns.
+
+3. **PT-BR video ground — explicitly owed by s2** ("named in the next ground so the omission cannot
+   read as coverage"), and it now doubles as a **third-region control**: AR s2 wrote the first-ever
+   rows into `video_locked_log.md` this same day and concluded the YouTube bot-wall is **not
+   regional** (EN controls at 142k/50k/33k views walled identically to AR at 538k/47k/31k), leaving
+   the boundary hypothesis *"blocked = all practitioner-scale video; passing = mega-viral only"*
+   resting on **one** passing observation (`dQw4w9WgXcQ`, ~1.6bn views). A PT-BR probe is the cheap
+   discriminator: a third language plus a different view-count band either sharpens that boundary
+   or refutes it, and GAP #26 buys on this log.
+
+**STANDING OPEN QUESTION (diaspora), carried unanswered from s1 and s2:** where did the BR crypto
+community go — local venues → Binance BRL → ? Named checkpoints remain unvisited.
+
+_(items resolve below as they close)_
+
+#### ITEM 1 — CLOSED, AND IT IS THE RUN'S FIND. The fork tree is a null; the CODE is a measured refutation; the COMMENT LAYER is the prize. [§33: killed -> docs/graveyard.md `zecontinha_eg_pairs_screen`]
+
+**THE FORK TREE — EXHAUSTED, AND IT IS AN HONEST NULL.** `forks_count: 6`, `/forks` returns **8**,
+and **not one fork is ahead by a single commit** (2 identical, 1 behind 10, 3 behind 144). The two
+extra entries — `yoshimorimori`, `igor110055` — are **HTTP 404 on both API and HTML**: tombstones of
+deleted accounts still served in the fork list. So the queue item that sent me here ("6 forks, diverged
+first") had **no diverged forks to find**, and "6 forks" was a popularity signal misread as a
+development signal. The null is worth as much as a find here because it retires the ground: **nobody
+needs to walk this fork tree again.** → **OP-078**, whose sharper half is that a tombstone 404 is
+byte-identical to a rate-limit or a network failure to any walker that treats non-200 as "skip" — the
+L1.60 denominator-attrition defect firing on a *mining* instrument (R0466's false null).
+
+**THE CODE — THE SCREEN IS REFUTED BY MEASUREMENT, NOT BY OBJECTION.** `coint_model()` fits
+`OLS(y ~ const + x)` and takes its p-value from `adfuller(resid)`. That is the textbook Engle–Granger
+error — ADF critical values do not apply to residuals of an *estimated* cointegrating vector, because
+OLS chose β to minimise the very variance the test examines — so I ran their exact window as a null
+instead of asserting it. **4,000 trials, two independent random walks, n=120 (their broadcast window):
+theirs rejects 17.97% [16.8, 19.2] against its own nominal 5%; `statsmodels.coint()` rejects 7.60%.
+3.59× nominal, 2.37× the correct test.** The full published gate (ADF `p<0.05` **and** `|z|≥2`) fires on
+0.88% of pure noise → **≈44 spurious pairs per run** on the 4,950-pair universe, at the broadcast
+window alone, before counting the **10 lookback windows** (`range(60,260,20)` = 49,500 tests/run) that
+carry no multiplicity correction anywhere in the codebase. The bot then publishes the **3 lowest-Hurst**
+survivors — ranking the output of a noise filter by an R/S statistic at n=120. → **OP-077**, graveyard.
+
+**THE COMMENT LAYER PAID BEST, EXACTLY AS THE DEPTH MANDATE PREDICTS.** Nothing on the surface — live
+site, Telegram channel, ADF/Hurst/half-life panel — says what the maintainer says in PR #30:
+
+> *"`select_pair(n)` was just a silly function to **draw a pair** … What ends up happening was **Telegram
+> folks see it as recommendations. Which they are NOT!**"* — Vido, 2025-10-21
+
+The selection step was `order_by('?')` — Django's **random ordering**. → **OP-080**. And because the
+switch to a screened selection is **dated and attributable** (PR #30, merged 2025-11-06; message
+template `v3`→`v4`), the channel's own public history contains **a random-pair baseline followed by a
+screened one on the same universe, timestamped** — a free control arm for the question "does a
+cointegration screen beat drawing a pair out of a hat", which is the question this family actually owes.
+
+**THE FAMILY IS *NOT* KILLED, AND I CHECKED THE OBJECTION THAT WOULD HAVE KILLED IT.** The desk's
+standing breadth lesson is *"1.54 independent bets RAW and 29 market-neutral … any **directional**
+cross-sectional mechanism is hard-killed by narrow_breadth"*. A cointegration pair is long *y* /
+short *βx* — **beta-neutral by construction**, so it lands on the **29** side. The argument that ends
+every directional cross-sectional mechanism here **does not apply to this family**, and is closer to an
+argument *for* it. That is the opposite of the conclusion I expected to write, and it is why
+STATISTICAL-ARBITRAGE being the desk's thinnest family (THIN, n=1 of 14) looks like neglect rather than
+a verdict. Routed to `improvement_inbox.md`; **no kill claimed.** *(Honest caveat:
+`reports/cross_section_breadth.json` is gitignored and unreadable from this checkout, so 1.54/29 are
+cited from the desk-lesson text, not re-verified.)*
+
+**THE DATA FIND — A FREE POINT-IN-TIME UNIVERSE, WHICH ANSWERS A RECORDED DESK GAP.** The repo's
+`BINANCE_FUTURES` list is hardcoded with a `# TODO` to automate it (PR #37, still open). That staleness
+is the asset: **git history turns one hardcoded ticker list into a time series of dated universes**, and
+the desk already recorded that *"`exchangeInfo` is a look-ahead in the UNIVERSE"* (free-data-miner
+2026-08-12) — the live endpoint only ever returns today's set. Vintages 2020-06-28 (n=25) / 2023-03-07
+(213) / 2023-12-05 (202) / 2025-11-14 (199) measured against live `fapi` exchangeInfo (865 symbols, 731
+TRADING). **And the honest number is not the headline one:** 55 of 213 absent = 25.8%, but **40 are
+BUSD-quote pairs killed by the BUSD wind-down** — a quote-currency retirement, not delistings — leaving
+**15 of 173 USDT names = 8.7% true survivorship erasure**, of which **3 are rebrands with a continuing
+series** (MATIC→POL, RNDR→RENDER both TRADING; TOMO→VIC SETTLING). **A rename and a delisting are
+opposite events that look identical in a symbol-set diff.** → universe map source **103**.
+*Self-correction recorded:* my first read of the current 100-symbol list was "frozen circa early 2021";
+the history says the opposite — it was **213 in 2023 and the author cut it to 100** in Nov 2025.
+
+**VENUE DISCOVERED BY READING REPO CODE (the mandated method):** **`@pythonfinancas`** ("Python e
+Finanças", `message_thread_id=9973`) — a public PT-BR Telegram, and it is in this seat's brief's ground
+list without any prior session having found it. Not carded as a data axis: its natural mechanism is
+retail signal-following, and it earns no card without a mechanism that is not already dead.
+
+**LEXICON / LANGUAGE — OP-079, and it refines the AR seat's OP-075 from the opposite direction.** The
+maintainer states an **English-only policy for a Brazilian project** (*"not just the lusophones"*) —
+in reply to a contributor asking, **in Portuguese**, which language to use. So the language boundary
+does not run around the repo, **it runs through it**: code and PR titles in English, the reasoning in
+Portuguese. The greppable residue is the identifiers the policy came too late to rename —
+`gera_pares`, `calcula_modelo`, `PERIODOS_CALCULO`, `ativo_x`/`ativo_y` — plus PT code comments
+(`# limpa o canvas`, `# TODO: descobrir qual é correto`). **Grep identifiers, not prose.**
+
+**PROCESS MANDATE — what the maintainer said he could not do, which is the shopping list:**
+`# TODO: This data does not require Binance Credentials` beside a `data.binance.vision` URL (he is
+paying an API-key cost for data that is free and bulk-downloadable); the daily-kline call is
+`get_historical_klines(..., KLINE_INTERVAL_1DAY, "1 year ago UTC")` under a comment reading *"fetch
+**weekly** klines **since it listed**"* — **a third OP-055 proving instance** (config comment
+contradicts config value) on a second repo, which is what promotes OP-055 from an anecdote about one
+thesis to a property of this corpus. And PR #35, 2025-11-15: *"Last week I deployed the changes in
+production… and lots of things broke"* — dates a data-quality discontinuity in the public feed, next to
+a commit literally titled *"Workaround on Low Quality Data"* (2025-11-14).
+
+#### ITEM 2 — CLOSED. The `TCC` key is REAL but NARROW, and it must never be ANDed with the native topical key. One repo taken to depth returned a **quantified** hidden-loser artifact. [§33: screened -> docs/research/search_operator_library.md OP-081]
+
+**GRADING THE STRUCTURAL KEY (measured, one instrument, same minute):**
+
+| query | repos | verdict |
+|---|---|---|
+| `TCC bitcoin` | **29** | the key works |
+| `TCC trading` | **18** | works |
+| `TCC criptomoedas` | **15** | works |
+| `TCC quantitativo` | 3 | mostly false hits (orçamentação, RAIS payroll) |
+| `TCC cointegração` | **1** | — against **30** for `cointegração` alone (s2) |
+| `dissertação trading` | **0** | the formal graduate word is **dead** as a repo label |
+| `"undergraduate thesis" trading` (EN control) | 8 | the EN genre word is weaker than the BR one |
+
+**THE VERDICT, AND IT CORRECTS THE QUEUE ITEM THAT SENT ME HERE.** s2 predicted `TCC` was a "RICH
+SEAM". It is a **precision key, not a recall key**: everything it returns really is thesis code, but
+intersecting it with the native topical key collapsed a 30-repo corpus to **1**. Structural keys and
+topical keys select on **different axes** — genre vs subject — so they must be **unioned, never
+ANDed**. And `dissertação` → 0 while `TCC` → 29 shows that within one country only *one* of several
+thesis words is actually used as a label: **test each genre word, never assume the formal one.** →
+**OP-081**, which is fleet-portable (JP 卒論, KR 졸업논문, CN 毕业设计, RU дипломная работа).
+
+**AND A COUNT-INFLATION CAVEAT I FOUND BY OPENING ONE:** `cadilhe/freqtrade_2020_tcc` is a **vendored
+fork of freqtrade itself** — 428 blobs, of which the student's own contribution is a handful of files
+under `user_data/`. The structural key's raw counts therefore **overstate** the corpus: a "TCC repo"
+is frequently an upstream framework with a thin layer on top. Grade by the non-upstream path count,
+not the repo count.
+
+**THE DEPTH FIND — A HIDDEN-LOSER ARTIFACT, AND THE ARITHMETIC IS UNAMBIGUOUS.** The repo ships a real
+backtest table (`user_data/backtest_results/`, Binance spot /BTC, 23 pairs, 5m):
+
+| report | trades | win | loss | win rate | tot profit | cum profit |
+|---|---|---|---|---|---|---|
+| **BACKTESTING REPORT** (the headline) | 411 | 358 | 53 | **87.1%** | **+8.78%** | +131.65% |
+| **LEFT OPEN TRADES** (a separate file) | 14 | **1** | **13** | 7.1% | **−2.91%** | −43.67% |
+| **combined (true)** | 425 | 359 | 66 | 84.5% | **+5.87%** | +87.98% |
+
+**The headline overstates total return by 49.6%** — positions still open when the backtest ended are
+reported in a *different file* and are **13:1 losers**, with an average duration of 4d23h against 1d0h
+for closed trades. This is the survivorship shape in miniature: the winners closed and got counted,
+the losers stayed open and got filed elsewhere. **This arithmetic needs no assumption and no rerun**,
+which is why it is the part I am asserting.
+
+**THE MECHANISM IS A HYPOTHESIS AND I AM LABELLING IT AS ONE.** `Strategy001.py` sets
+`sell_profit_only = True` (the sell signal fires **only** when the trade is in profit), with
+`stoploss = -0.10`; every left-open loser sits between −0.20% and −6.44%, i.e. **above the stop and
+below profit — structurally untouchable by either exit**. That explains the pattern exactly. But
+`config.binance.json` sets `sell_profit_only: false`, and **config overrides strategy in freqtrade** —
+while that same config declares `ticker_interval: "1h"` against a report filename of `..._5m2911`, so
+the config in the repo is probably *not* the one that produced the table. **Which setting was live is
+undeterminable from the repo**, so the mechanism stays a hypothesis with its falsifier named (rerun
+with `sell_profit_only` both ways on the vendored data, which is *also* in the repo —
+`user_data/data/binance/*.json`, 1m/5m/1h, so this is genuinely EXECUTABLE-tier). **This is the fourth
+config-vs-declaration contradiction this seat has found in the BR corpus (OP-055).**
+
+**COST ACCOUNTING (the BACKTEST MINER's required field):** neither config declares a `fee` key, so
+fees came from freqtrade's framework default rather than from anything stated in the repo. That is
+**not "no cost model"** — it is an **undeclared, inherited** one, which is a distinct and more
+insidious state than absence: a reader cannot tell what was charged without knowing the framework
+version's default. **Slippage, spread and impact are unmodelled** (limit orders assumed filled). These
+are **spot /BTC pairs, so funding does not apply** — worth saying explicitly, because the desk's
+standing WS-006 lesson is about perps and does not transfer here.
+
+**NOT THE STUDENT'S STRATEGY, WHICH RAISES THE STAKES:** `Strategy001.py` carries
+`author@: Gerald Lonlas, github@: freqtrade/freqtrade-strategies` — this is the **widely-copied
```


---

## f691810e ledger: R0457 + R0458 disposed implemented; R0595-R0597 raised for the halves not built
R0457 -> IMPLEMENTED (aee2bc86): list-order randomisation + permutation logging, wired
at the two sites where the desk counts LLM answers as evidence. Parts (b) protocol-block
diffing and (c) ForeSci temporal-cutoff generator backtest were NOT built and are R0597;
the remaining list-presenting organs are R0596. Splitting rather than claiming the row.

R0458 -> IMPLEMENTED (661acf24): measured null recorded, no desk change warranted
because every arm the benchmarks favour is the arm the desk already runs. Its one
unsatisfied half -- re-measure organ completion/decay after a model swap, which has zero
producers repo-wide -- is R0595.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit f691810e8eddb3b1edb0f7200256cf1f72734889
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:51:25 2026 +0000

    ledger: R0457 + R0458 disposed implemented; R0595-R0597 raised for the halves not built
    
    R0457 -> IMPLEMENTED (aee2bc86): list-order randomisation + permutation logging, wired
    at the two sites where the desk counts LLM answers as evidence. Parts (b) protocol-block
    diffing and (c) ForeSci temporal-cutoff generator backtest were NOT built and are R0597;
    the remaining list-presenting organs are R0596. Splitting rather than claiming the row.
    
    R0458 -> IMPLEMENTED (661acf24): measured null recorded, no desk change warranted
    because every arm the benchmarks favour is the arm the desk already runs. Its one
    unsatisfied half -- re-measure organ completion/decay after a model swap, which has zero
    producers repo-wide -- is R0595.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/recommendation_ledger.json | 52 +++++++++++++++++++++++++++-----
 1 file changed, 44 insertions(+), 8 deletions(-)

diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index e0508a70..fc147a45 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -5866,11 +5866,11 @@
    "summary": "litminer run6 inbox 2026-08-12 E (w7): generation-side quality — randomize+log candidate-list order in every list-presenting organ (measured 100% metric order-dependence; the 420 may have been menu-chosen), machine-checkable protocol block at generation diffed at gate (25% silent drift rate), ForeSci-style temporal-cutoff backtest of the GENERATION organ against own realized ledger + evidence-decision decoupling check. Sources: 2509.08713 appendix, 2606.00644.",
    "roi_bps": null,
    "raised": "2026-08-12T01:57:59.132942+00:00",
-   "status": "open",
-   "reason": null,
-   "commit": null,
+   "status": "implemented",
+   "reason": "PART (a) BUILT AND WIRED (aee2bc86); parts (b) and (c) split to R0597 and the remaining (a) coverage to R0596, so nothing here is closed by assertion. SHIPPED: libs/research/list_order.shuffled_with_log -- randomises a candidate list per call and LOGS the permutation plus its seed to data/list_order_log.jsonl. THE LOG IS THE POINT AND IT IS THE HALF THE DESK WAS MISSING: run_external_panel.py:538 already shuffles (GAP #72(4), correct diagnosis in its own comment) but is UNSEEDED AND UNLOGGED, so the permutation is unrecoverable and 'how order-sensitive is this desk?' has been unanswerable since it shipped -- a shuffle without a log de-biases the estimate and DESTROYS THE RESIDUAL. WIRED AT THE TWO SITES WHERE THE DESK COUNTS LLM ANSWERS AS EVIDENCE, which is where the row's 100%-ordering-dependence finding actually bites: (1) survivor_panel.BOTTLENECK_CLASSES -- a hardcoded tuple, so SAMPLE_LENGTH led the menu on every run this panel has ever done while run_survivor_panel.py:200 TALLIES bottleneck_votes ACROSS SEATS; an unshuffled tally cannot distinguish 'the seats agree' from 'the seats all read the same first line', on a panel whose question is WHY HAS NOTHING EVER SURVIVED. (2) run_llm_trader MECHANISMS/PARTICIPANTS -- the taxonomy exists so 'after N calls the desk can retire the families that never pay', and with FORCED_LIQUIDATION leading every call ever made the desk was on course to retire GOVERNANCE_CHANGE for being listed NINTH rather than for failing. Also shuffles round-two seat order, the same bias one level up (roster order is stable, so the same model was SEAT A every week while the prompt asks the reader to REFUTE and then DECIDE). Seeded from os.urandom not a clock, because two seats starting in the same second drawing one permutation would read as agreement -- the bias wearing a fix's clothes. NOT applied to ORDINAL menus (EVIDENCE_CLASSES weakest-to-strongest, prior turns oldest-to-newest) where order carries meaning, nor to ranked payloads where the rank is a real prior. 6 tests pin RECOVERABILITY rather than randomness, including one asserting the wired organs actually route through the logger; ruff + mypy(629 files) clean. run_conviction_trader.py is named in R0596 and deliberately NOT bundled: it is the only site that sizes.",
+   "commit": "aee2bc86",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T08:51:08.847973+00:00"
   },
   {
    "id": "R0458",
@@ -5878,11 +5878,11 @@
    "summary": "litminer run6 inbox 2026-08-12 F (w6): organ reliability + memory — measured null: memory products lose to BM25 (do not adopt Mem0/Zep-class), vault+files+BM25 is the evidence-favored design; supersession ledgering load-bearing (selective forgetting <=28% universally); compaction = cost knob (structural masking over LLM re-summarization); after ANY organ model swap re-measure the organ completion/decay curve (two-source: capability gains give only small reliability gains; <=19% meltdown-by-ambition) — directly relevant to the live llm-auto-upgrade branch. Sources: MemoryAgentBench ICLR26, LongMemEval-V2, 2605.18854, 2603.29231, 2602.16666.",
    "roi_bps": null,
    "raised": "2026-08-12T01:58:02.647430+00:00",
-   "status": "open",
-   "reason": null,
-   "commit": null,
+   "status": "implemented",
+   "reason": "RECORDED AS A MEASURED NULL, WHICH IS THIS ROW'S OWN EXPLICIT ASK ('carding this as a measured null so no future session re-opens it'). Two artifacts: research-memory row rm-20260813T083328-e3d8ea [method/rejected], and the tracked+injected copy in docs/institutional_knowledge.md (661acf24) carrying the numbers so a future session meets EVIDENCE rather than an opinion -- MemoryAgentBench (2507.05257, ICLR 2026, peer-reviewed, MIT code) accurate-retrieval Mem0 32.6 / Cognee 28.3 / Zep 37.5 / MIRIX 47.5 vs BM25 60.5; LongMemEval-V2 file-memory 72.5 vs RAG 48.5 at 115M tokens; 2605.18854 across 480 evals no condenser alters hypothesis quality while LLM-summary condensers cost +24-94% tokens. NO DESK CHANGE IS WARRANTED AND THAT IS THE FINDING, not an evasion: every arm the literature favours is the arm the desk already runs -- retrieval IS BM25 (libs/research/vault_index.py behind vault_search, the same index the MCP tool serves), memory IS files, and the desk does no LLM re-summarization compaction to remove. The binding constraint the benchmark names (selective forgetting, multi-hop consolidation <=28% for EVERY method) is already load-bearing law and was exercised this session: findings_ledger carries superseded_by F0004->F0020 and F0007->F0008, and track_findings.py:89 documents supersession as the legal exit that stops a refuted row rotting. THE ONE HALF NOT SATISFIED IS SPLIT RATHER THAN BURIED: 'after ANY organ model swap re-measure the organ completion/decay curve' has ZERO producers repo-wide (grep completion_rate/decay_curve/organ_completion across scripts/ and libs/) while scripts/model_upgrade.py gauntlets only single-shot CAPABILITY -- rowed as R0595 with the mechanism and the already-existing denominator (record_attempts, 95289be5) named. Claiming this row fully done would have hidden that.",
+   "commit": "661acf24",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T08:49:50.202703+00:00"
   },
   {
    "id": "R0459",
@@ -7515,6 +7515,42 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0595",
+   "source": "cycle",
+   "summary": "MODEL-SWAP RELIABILITY GAP (split from R0458(e), the one half of that row not already satisfied). scripts/model_upgrade.py gauntlets a candidate seat on CAPABILITY at swap time -- A LIVE (non-empty answer), C FORMAT (parseable finding rows), D HONESTY (says ABSENT about a file not in the payload), B CAPACITY (names the last file of a real full payload) -- and nothing anywhere measures the organ's COMPLETION/DECAY curve after the swap lands (grep for completion_rate/decay_curve/organ_completion across scripts/ and libs/ returns ZERO producers). The literature R0458 carries says these are different quantities and the gap is in the dangerous direction: capability gains buy only SMALL reliability gains, and up to 19% of failures are meltdown-by-ambition -- a MORE capable model attempts more ambitious work and completes its runs LESS reliably. So a candidate can pass all four probes, be adopted correctly on capability, and then quietly lower the seat's finished-run rate, which is the quantity the panel actually consumes. The four probes are single-shot and cannot see it by construction: reliability is a rate over runs, not a property of one answer. WORK: record the swap as a dated event and compare the seat's completed-run rate over the N runs before vs after, so an upgrade that trades reliability for capability is MEASURABLE rather than invisible. Note the desk already owns the denominator this needs -- build_audit_coverage.record_attempts (95289be5) counts every seat call whether it answers or dies, so the before/after rate is computable from an artifact that already exists. NOT a proposal to slow or block upgrades (L1.28c/L1.21a): model_upgrade.py's evidence-gated adoption is correct and stays; this only makes the post-swap direction observable, and UNMEASURED currently counts as zero (L1.28a).",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:36:47.468158+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0596",
+   "source": "cycle",
+   "summary": "COMPLETE THE LIST-ORDER COVERAGE (the rest of R0457(a); mechanism shipped aee2bc86, libs/research/list_order.shuffled_with_log). A full map of list-presenting organs found ~10 order-sensitive sites; three fields across two organs are wired. REMAINING TIER-1 (LLM picks exactly one item from a fixed-order menu): scripts/run_conviction_trader.py:1573 INSTRUMENTS (18 perps, BTCUSDT always first) -- HIGHEST real cost because it is the only one that SIZES, and its ENSEMBLE_N draws share the single positional prior so the ensemble cannot average out a bias every member holds; deliberately left for a change of its own rather than bundled. libs/research/cro_role.py:667-676 -- FIVE menus in one prompt (DELIVERABLES 13, GROWTH_LEVERS, KINDS, EVIDENCE_CLASSES, CONFIDENCE) x 12 recommendations, and cro_role.py:832 computes a mandate-COVERAGE SCORE directly off the fixed order. scripts/run_trade_review.py:285 _CAUSES (7 post-mortem labels, hard-validated at :286) which feed the sleeve playbook that feeds the conviction trader, so the bias compounds across organs. TIER-2: libs/research/hunt_frontier.py:265-270 -- shuffle BEFORE the [:limit] slice or truncation bias survives the shuffle. RETROFIT: run_external_panel.py:538 already shuffles but unseeded and unlogged, so its GAP #72(4) claim has never been measurable -- route it through the logger. DO NOT SHUFFLE ordinal menus (EVIDENCE_CLASSES is weakest-to-strongest, prior turns are oldest-to-newest) or ranked payloads (build_audit_coverage.py:393 is risk-class-first, a real prior -- shuffle WITHIN tier). ONCE >=200 rows accumulate in data/list_order_log.jsonl, run the reanalysis the log exists for: regress chosen-item on shown-POSITION to measure this desk's own ordering sensitivity, which is currently UNMEASURED and therefore zero (L1.28a).",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:50:23.714618+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0597",
+   "source": "cycle",
+   "summary": "THE OTHER TWO THIRDS OF R0457 (part (a), list-order, shipped aee2bc86; these two were NOT built and are split so they are not buried by that commit). (b) SILENT PROTOCOL DRIFT IS A GENERATION-SIDE DEFECT CLASS: arXiv 2509.08713 measured 5/20 AI-Scientist-v2 runs quietly subsampling or substituting synthetic data with no report of having done so -- a 25% silent-drift rate. Desk analog: a generation organ that quietly narrows universe or date-range emits hypotheses that LOOK testable but are not, and nothing compares what was PROMISED at generation with what was DELIVERED at gate. Build: attach a machine-checkable protocol block (universe, date range, n) at GENERATION time and DIFF it at gate time; a mismatch is a defect on the candidate, not a note. Note the desk already has the shape of this elsewhere -- axis_screen bakes its de-contamination gate in rather than trusting the caller -- so this is a known-good pattern applied one stage earlier. (c) TEMPORAL-CUTOFF BACKTEST OF THE GENERATION ORGAN (ForeSci, arXiv 2606.00644, CC-BY, 500 cutoff-aligned research-judgment tasks): score the generator by whether its pre-cutoff judgments TRANSFER, using the desk's own realized ledger as ground truth -- i.e. ask the generator to rank hypotheses as of date T using only pre-T information and compare against what the desk subsequently measured. This is the one instrument that could answer whether the 420/0 campaign was a generator failure or a screen failure, which L1.25's ordered diagnostic (instrument? search space? hypotheses?) currently answers only by elimination. Also carries an evidence-decision decoupling check: whether the organ's stated evidence actually drove its choice. PRIORITISE (b): it is far cheaper, it is a defect-CLOSER rather than a measurement, and 25% is a measured rate on systems of the same shape.",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:50:44.962362+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
```


---

## 661acf24 R0458: measured null -- commercial agent-memory products lose to BM25; do not adopt
Carded so no future session re-opens it. Research-memory row rm-20260813T083328-e3d8ea
[method/rejected] carries the numbers; this is the tracked, injected copy.

MemoryAgentBench (arXiv 2507.05257, ICLR 2026 -- peer-reviewed, MIT code, public data)
accurate-retrieval average: Mem0 32.6%, Cognee 28.3%, Zep 37.5%, MIRIX 47.5%, against
plain BM25 60.5%. LongMemEval-V2: file-reading/writing memory 72.5% vs embedding-RAG
48.5% over 115M-token histories. 2605.18854 (480 evals): across 8 condensation
strategies no condenser significantly alters hypothesis quality, while LLM-summary
condensers cost +24-94% tokens.

NO DESK CHANGE FOLLOWS, AND THAT IS THE FINDING. Every arm the benchmarks favour is the
arm the desk already runs: retrieval IS BM25 (libs/research/vault_index.py behind
vault_search, the same index the MCP tool serves), memory IS files (vault + MEMORY.md +
running notes), and compaction is therefore a COST knob the desk must not convert into
an LLM-summarization one.

The binding constraint is why supersession ledgering is load-bearing rather than
bureaucracy: multi-hop fact consolidation measured <=28% for EVERY method tested, so no
machine can be trusted to propagate a supersession through derived facts. A write that
invalidates a prior fact must NAME the row it supersedes. Exercised this session --
findings_ledger carries F0004->F0020 and F0007->F0008.

The one half NOT satisfied is split to R0595 rather than buried: 'after any organ model
swap re-measure the completion/decay curve' has zero producers repo-wide
(completion_rate/decay_curve/organ_completion) while model_upgrade.py gauntlets only
single-shot capability -- and the literature says capability gains buy only small
reliability gains, with up to 19% meltdown-by-ambition.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 661acf24ad6a4e99d3d7974abe5032cc3e5f7a0d
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:49:36 2026 +0000

    R0458: measured null -- commercial agent-memory products lose to BM25; do not adopt
    
    Carded so no future session re-opens it. Research-memory row rm-20260813T083328-e3d8ea
    [method/rejected] carries the numbers; this is the tracked, injected copy.
    
    MemoryAgentBench (arXiv 2507.05257, ICLR 2026 -- peer-reviewed, MIT code, public data)
    accurate-retrieval average: Mem0 32.6%, Cognee 28.3%, Zep 37.5%, MIRIX 47.5%, against
    plain BM25 60.5%. LongMemEval-V2: file-reading/writing memory 72.5% vs embedding-RAG
    48.5% over 115M-token histories. 2605.18854 (480 evals): across 8 condensation
    strategies no condenser significantly alters hypothesis quality, while LLM-summary
    condensers cost +24-94% tokens.
    
    NO DESK CHANGE FOLLOWS, AND THAT IS THE FINDING. Every arm the benchmarks favour is the
    arm the desk already runs: retrieval IS BM25 (libs/research/vault_index.py behind
    vault_search, the same index the MCP tool serves), memory IS files (vault + MEMORY.md +
    running notes), and compaction is therefore a COST knob the desk must not convert into
    an LLM-summarization one.
    
    The binding constraint is why supersession ledgering is load-bearing rather than
    bureaucracy: multi-hop fact consolidation measured <=28% for EVERY method tested, so no
    machine can be trusted to propagate a supersession through derived facts. A write that
    invalidates a prior fact must NAME the row it supersedes. Exercised this session --
    findings_ledger carries F0004->F0020 and F0007->F0008.
    
    The one half NOT satisfied is split to R0595 rather than buried: 'after any organ model
    swap re-measure the completion/decay curve' has zero producers repo-wide
    (completion_rate/decay_curve/organ_completion) while model_upgrade.py gauntlets only
    single-shot capability -- and the literature says capability gains buy only small
    reliability gains, with up to 19% meltdown-by-ambition.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/institutional_knowledge.md | 41 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 41 insertions(+)

diff --git a/docs/institutional_knowledge.md b/docs/institutional_knowledge.md
index d0a32585..2855a361 100644
--- a/docs/institutional_knowledge.md
+++ b/docs/institutional_knowledge.md
@@ -855,3 +855,44 @@ flat book.
 never share a source -- same family as L1.51's `_capital()`, where a ceiling and its own numerator
 shared one. And an alarm must name the cause its data supports, not the one its shape suggests:
 check the diagnosis is *possible* in the current state before asserting it.
+
+## Architecture decision -- 2026-08-13 (MEASURED NULL: commercial agent-memory products lose to BM25; do not adopt)
+
+Carded so no future session re-opens it (R0458; research-memory row
+`rm-20260813T083328-e3d8ea` [method/rejected]). **Do not adopt Mem0 / Letta / Zep / Cognee /
+MIRIX-class memory products.** This is not a taste call -- every arm the published benchmarks
+favour is the arm this desk already runs.
+
+**The numbers.** MemoryAgentBench (arXiv 2507.05257, ICLR 2026 -- peer-reviewed, MIT code, public
+data) accurate-retrieval average: Mem0 **32.6%**, Cognee 28.3%, Zep 37.5%, MIRIX 47.5%, against
+plain **BM25 60.5%**. LongMemEval-V2 (2605.12493): memory that reads and writes *files*
+(AgentRunbook-C) **72.5%** vs embedding-RAG **48.5%** over histories to 115M tokens. 2605.18854
+(480 evals, DiscoveryBench): across 8 condensation strategies *no condenser significantly alters
+hypothesis quality*, while LLM-summary condensers **cost +24-94% tokens**.
+
+**Why no desk change follows, and that is the finding rather than an evasion.** The desk's
+retrieval IS BM25 (`libs/research/vault_index.py` behind `scripts/vault_search.py`, the same index
+the `vault_search` MCP tool serves, so an organ and a session cannot disagree about what the vault
+says). The desk's memory IS files (Obsidian vault + `MEMORY.md` + running notes). Compaction is
+therefore a **cost** knob, not a quality one: prefer structural masking of stale tool outputs over
+LLM re-summarization, which the desk does not do and must not start.
+
+**The binding constraint is selective forgetting, and it is why supersession ledgering is
+load-bearing rather than bureaucracy.** Multi-hop fact consolidation measured **<=28% for every
+method tested** -- no machine can be trusted to propagate a supersession through derived facts. So
+a write that invalidates a prior fact must NAME the row it supersedes; an agent reading both rows
+cannot be assumed to resolve the conflict itself. The desk already encodes this
+(`findings_ledger.superseded_by`, e.g. F0004->F0020 and F0007->F0008; `track_findings.py:89`
+documents supersession as the legal exit that stops a refuted row rotting) -- the benchmark says
+keep paying for it.
+
+**The one half NOT satisfied, split rather than buried** (R0595): *after any organ model swap,
+re-measure the organ's completion/decay curve.* `scripts/model_upgrade.py` gauntlets a candidate on
+single-shot CAPABILITY (live / format / honesty / capacity) and nothing measures reliability over
+runs -- grep for `completion_rate`, `decay_curve`, `organ_completion` across `scripts/` and `libs/`
+returns **zero producers**. The gap points the dangerous way: capability gains buy only small
+reliability gains, and up to **19%** of failures are meltdown-by-ambition, where a *more* capable
+model attempts more and finishes less. A seat can pass all four probes, be adopted correctly, and
+quietly lower the finished-run rate the panel actually consumes. The denominator already exists --
+`build_audit_coverage.record_attempts` (95289be5) counts every seat call whether it answers or
+dies.
```


---

## aee2bc86 R0457: the desk tallies LLM answers off fixed-order menus, and logs no permutation
arXiv 2509.08713 ran a controlled protocol on two AI-scientist systems and measured
100% metric-ordering dependence -- whichever candidate was listed FIRST got chosen --
and 82.4% first-four-benchmark selection. This desk presents hardcoded menus to LLMs
and then counts the answers as evidence.

The two sites where that counting is load-bearing:

  survivor_panel.BOTTLENECK_CLASSES  SAMPLE_LENGTH has led the list on every run this
                                     panel has ever done, and run_survivor_panel.py
                                     TALLIES bottleneck_votes ACROSS SEATS. An
                                     unshuffled tally cannot tell 'the seats agree'
                                     from 'the seats all read the same first line' --
                                     on a panel whose question is WHY HAS NOTHING EVER
                                     SURVIVED.
  run_llm_trader.MECHANISMS          exists so that 'after N calls the desk can retire
                                     the families that never pay'. FORCED_LIQUIDATION
                                     led every call ever made, so the desk was on
                                     course to retire GOVERNANCE_CHANGE for being
                                     listed ninth rather than for failing to pay.

THE LOG IS THE POINT, NOT THE SHUFFLE. The desk already had one shuffle
(run_external_panel.py:538, GAP #72(4)) carrying the correct diagnosis in its own
comment. It is unseeded and writes nothing, so the permutation is unrecoverable and
'how order-sensitive are we?' has been unanswerable since it shipped. A shuffle without
a log de-biases the estimate and DESTROYS THE RESIDUAL. Every call here records the
permutation and its seed, so the sensitivity is a cheap reanalysis of logged runs
rather than a 20-call experiment nobody schedules (L1.28a).

Seeded from os.urandom, never a clock: two seats starting in the same second must not
draw the same permutation, because correlated randomisation reads as agreement and
would be the bias wearing a fix's clothes. Short lists are still logged -- a
denominator that quietly sheds members is L1.60, and 'this list was short' must not
read identically to 'this call site never ran'.

NOT applied to ordinal menus (EVIDENCE_CLASSES runs weakest-to-strongest, prior turns
run oldest-to-newest): shuffling those destroys information rather than bias.
run_conviction_trader.py's 18-instrument menu is the remaining Tier-1 site and is left
for a deliberate change of its own -- it is the one that sizes, and its ENSEMBLE_N
draws share the single positional prior, so an ensemble cannot average out a bias every
member holds.

6 tests, all pinning recoverability rather than randomness, incl. one asserting the
wired organs actually route through the logger.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit aee2bc86bc742dcfef5e4e228ab98b523a2f15b1
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:49:22 2026 +0000

    R0457: the desk tallies LLM answers off fixed-order menus, and logs no permutation
    
    arXiv 2509.08713 ran a controlled protocol on two AI-scientist systems and measured
    100% metric-ordering dependence -- whichever candidate was listed FIRST got chosen --
    and 82.4% first-four-benchmark selection. This desk presents hardcoded menus to LLMs
    and then counts the answers as evidence.
    
    The two sites where that counting is load-bearing:
    
      survivor_panel.BOTTLENECK_CLASSES  SAMPLE_LENGTH has led the list on every run this
                                         panel has ever done, and run_survivor_panel.py
                                         TALLIES bottleneck_votes ACROSS SEATS. An
                                         unshuffled tally cannot tell 'the seats agree'
                                         from 'the seats all read the same first line' --
                                         on a panel whose question is WHY HAS NOTHING EVER
                                         SURVIVED.
      run_llm_trader.MECHANISMS          exists so that 'after N calls the desk can retire
                                         the families that never pay'. FORCED_LIQUIDATION
                                         led every call ever made, so the desk was on
                                         course to retire GOVERNANCE_CHANGE for being
                                         listed ninth rather than for failing to pay.
    
    THE LOG IS THE POINT, NOT THE SHUFFLE. The desk already had one shuffle
    (run_external_panel.py:538, GAP #72(4)) carrying the correct diagnosis in its own
    comment. It is unseeded and writes nothing, so the permutation is unrecoverable and
    'how order-sensitive are we?' has been unanswerable since it shipped. A shuffle without
    a log de-biases the estimate and DESTROYS THE RESIDUAL. Every call here records the
    permutation and its seed, so the sensitivity is a cheap reanalysis of logged runs
    rather than a 20-call experiment nobody schedules (L1.28a).
    
    Seeded from os.urandom, never a clock: two seats starting in the same second must not
    draw the same permutation, because correlated randomisation reads as agreement and
    would be the bias wearing a fix's clothes. Short lists are still logged -- a
    denominator that quietly sheds members is L1.60, and 'this list was short' must not
    read identically to 'this call site never ran'.
    
    NOT applied to ordinal menus (EVIDENCE_CLASSES runs weakest-to-strongest, prior turns
    run oldest-to-newest): shuffling those destroys information rather than bias.
    run_conviction_trader.py's 18-instrument menu is the remaining Tier-1 site and is left
    for a deliberate change of its own -- it is the one that sizes, and its ENSEMBLE_N
    draws share the single positional prior, so an ensemble cannot average out a bias every
    member holds.
    
    6 tests, all pinning recoverability rather than randomness, incl. one asserting the
    wired organs actually route through the logger.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 libs/research/list_order.py       | 76 +++++++++++++++++++++++++++++++
 libs/research/survivor_panel.py   | 25 ++++++++--
 scripts/run_llm_trader.py         | 14 +++++-
 tests/research/test_list_order.py | 96 +++++++++++++++++++++++++++++++++++++++
 4 files changed, 206 insertions(+), 5 deletions(-)

diff --git a/libs/research/list_order.py b/libs/research/list_order.py
new file mode 100644
index 00000000..3708c777
--- /dev/null
+++ b/libs/research/list_order.py
@@ -0,0 +1,76 @@
+"""Randomise the order of a candidate list shown to an LLM, and LOG the permutation (R0457).
+
+THE MEASURED PROBLEM. arXiv 2509.08713 ("Hidden Pitfalls of AI Scientist Systems") ran a
+controlled protocol on two open-source AI-scientist systems and found selection is driven by
+POSITION, not merit: **100% metric-ordering dependence** (whichever metric was listed first got
+used, Tables 7-8) and Agent Laboratory picking the first four listed benchmarks 82.4% of the time.
+Ordering bias is one of the best-replicated LLM phenomena there is, and this desk presents fixed-
+order menus to LLMs and then TALLIES THE ANSWERS AS EVIDENCE.
+
+WHY THE LOG IS THE POINT, AND NOT THE SHUFFLE. The desk already had one shuffle --
+`run_external_panel.py:538`, added by GAP #72(4) with the correct diagnosis in its own comment
+("the CRO reads top-down, so the desk was imposing a position bias on ITSELF"). It is unseeded and
+writes nothing, so the permutation is unrecoverable and the desk STILL cannot answer "how
+order-sensitive are we?". A shuffle without a log converts a measurable bias into an unmeasurable
+one; it de-biases the estimate and destroys the residual. Every call here records the permutation
+and the seed, so ordering sensitivity becomes a cheap reanalysis of logged runs rather than a
+20-call experiment nobody schedules (L1.28a: unmeasured counts as zero).
+
+WHAT THIS IS NOT FOR. An ORDINAL menu carries meaning in its order -- `EVIDENCE_CLASSES` runs
+weakest-to-strongest, prior conversation turns run oldest-to-newest -- and shuffling it destroys
+information rather than bias. Use this only where the listed items are PEERS and the model is
+being asked to choose among them. Where a ranking is a real prior (risk-class-first review
+payloads), shuffle WITHIN a tier, never across.
+"""
+from __future__ import annotations
+
+import json
+import os
+from collections.abc import Sequence
+from datetime import UTC, datetime
+from pathlib import Path
+from typing import TypeVar
+
+import numpy as np
+
+_ROOT = Path(__file__).resolve().parent.parent.parent
+LOG = _ROOT / "data/list_order_log.jsonl"
+
+T = TypeVar("T")
+
+
+def shuffled_with_log(
+    items: Sequence[T], *, organ: str, field: str, seed: int | None = None,
+) -> tuple[list[T], list[int]]:
+    """Return (reordered items, permutation) and append the permutation to the log.
+
+    `permutation[i]` is the ORIGINAL index of the item now at position `i`, so a later reanalysis
+    can map any answer back to the position it was shown in without re-deriving anything.
+
+    `seed` is recorded whether supplied or drawn, which is what makes a run reproducible. Drawing
+    from `os.urandom` rather than a clock means two organs starting in the same second cannot share
+    a permutation -- correlated "randomisation" across seats would look like agreement and would be
+    the bias wearing a fix's clothes.
+
+    A ONE-ITEM LIST IS STILL LOGGED. It carries no bias, but dropping it would make the log's
+    denominator the count of lists that happened to be long enough, and a denominator that quietly
+    sheds members is the defect L1.60 exists for -- "this list was short" and "this call site never
+    ran" must not be byte-identical to a reader.
+    """
+    if seed is None:
+        seed = int.from_bytes(os.urandom(8), "big")
+    n = len(items)
+    perm = np.random.default_rng(seed).permutation(n).tolist() if n > 1 else list(range(n))
+
+    # Append-only, one line, flushed. NOT wrapped in a try/except: the shuffle has already happened
+    # by the time this runs, so swallowing a write failure would leave the desk holding a permuted
+    # list it can never map back -- strictly worse than the fixed order it replaced, and invisible.
+    # A failure here is a real defect and is allowed to say so (L1.41: no silent swallow).
+    LOG.parent.mkdir(parents=True, exist_ok=True)
+    with LOG.open("a", encoding="utf-8") as fh:
+        fh.write(json.dumps({
+            "ts": datetime.now(tz=UTC).isoformat(), "organ": organ, "field": field,
+            "n": n, "seed": seed, "permutation": perm,
+        }, sort_keys=True) + "\n")
+
+    return [items[i] for i in perm], perm
diff --git a/libs/research/survivor_panel.py b/libs/research/survivor_panel.py
index d7acd69f..279492a1 100644
--- a/libs/research/survivor_panel.py
+++ b/libs/research/survivor_panel.py
@@ -40,6 +40,7 @@ from pathlib import Path
 from typing import Any
 
 from libs.doctrine.constitution import OBJECTIVE_PREAMBLE
+from libs.research.list_order import shuffled_with_log
 
 __all__ = [
     "FORBIDDEN",
@@ -231,8 +232,19 @@ def _dossier_text(d: dict[str, Any]) -> str:
 
 
 def round_one_prompt(dossier: dict[str, Any]) -> tuple[str, str]:
-    """(system, user) for the independent round."""
-    classes = "\n".join(f"  {k} -- {v}" for k, v in BOTTLENECK_CLASSES)
+    """(system, user) for the independent round.
+
+    THE MENU IS SHUFFLED PER CALL (R0457). `BOTTLENECK_CLASSES` is a hardcoded tuple, so
+    `SAMPLE_LENGTH` led this list on every run this panel has ever done, and
+    `run_survivor_panel.py` TALLIES `bottleneck_votes` across seats -- a cross-seat vote count on a
+    fixed-order menu. arXiv 2509.08713 measured 100% metric-ordering dependence in exactly this
+    shape, so an unshuffled tally cannot distinguish "the seats agree" from "the seats all read the
+    same first line". The permutation is logged, which is what makes the sensitivity measurable
+    rather than merely removed.
+    """
+    ordered, _perm = shuffled_with_log(
+        BOTTLENECK_CLASSES, organ="survivor_panel", field="bottleneck_classes")
+    classes = "\n".join(f"  {k} -- {v}" for k, v in ordered)
     system = (
         OBJECTIVE_PREAMBLE + "\n"
         "You are a seat on a quantitative research desk's bottleneck panel. You are handed the "
@@ -286,8 +298,15 @@ def cross_examination_prompt(dossier: dict[str, Any],
         '"everyone_missed": "<=100 words>", '
         '"proposals": [{"action": "...", "bottleneck": "...", "rationale": "...", '
         '"testable_in_days": <number>}]}')
+    # SEAT ORDER IS SHUFFLED TOO (R0457), and it is the same bias one level up: `others` arrives in
+    # roster order, which is stable across runs, so the SAME model was SEAT A every week while this
+    # prompt asks the reader to REFUTE a specific claim and then DECIDE. Position 1 gets refuted or
+    # adopted disproportionately. `run_external_panel.py:538` already fixed exactly this for the
+    # CRO's inbox and the fix was never propagated here.
+    shuffled_others, _seat_perm = shuffled_with_log(
+        list(others), organ="survivor_panel", field="round_two_seat_order")
     blocks = "\n\n".join(f"--- SEAT {chr(65 + i)} ---\n{txt[:2600]}"
-                         for i, (_name, txt) in enumerate(others))
+                         for i, (_name, txt) in enumerate(shuffled_others))
     user = (f"THE DESK'S MEASURED STATE:\n{_dossier_text(dossier)}\n\n"
             f"THE OTHER SEATS SAID:\n{blocks}")
     return system, user
diff --git a/scripts/run_llm_trader.py b/scripts/run_llm_trader.py
index 11589569..feb32b2d 100644
--- a/scripts/run_llm_trader.py
+++ b/scripts/run_llm_trader.py
@@ -56,6 +56,7 @@ if str(_ROOT) not in sys.path:
     sys.path.insert(0, str(_ROOT))
 from libs.ops.lawful import guard as _law_guard  # noqa: E402
 from libs.research import liquidation_brief  # noqa: E402
+from libs.research.list_order import shuffled_with_log  # noqa: E402
 
 _BOOK = "data/llm_trader_book.jsonl"
 _STATE = "data/llm_trader.json"
@@ -566,10 +567,19 @@ def main() -> int:
                          if arm == "BLIND" else brief, indent=2))
         return 0
 
+    # BOTH TAXONOMIES ARE SHUFFLED PER CALL (R0457), and this is the site where the bias would do
+    # the most damage. MECHANISMS exists precisely so "which families produce alpha" becomes
+    # measurable "after N calls" -- but it is a hardcoded tuple, so FORCED_LIQUIDATION led the menu
+    # on every call ever made, and arXiv 2509.08713 measured 100% ordering dependence in this exact
+    # shape. A fixed-order menu means the desk would retire GOVERNANCE_CHANGE for being listed
+    # ninth rather than for failing to pay. The permutation is logged, so the ordering sensitivity
+    # of the surviving tally is a reanalysis rather than an experiment nobody runs.
+    mechs, _mp = shuffled_with_log(MECHANISMS, organ="llm_trader", field="mechanisms")
+    parts, _pp = shuffled_with_log(PARTICIPANTS, organ="llm_trader", field="participants")
     raw = _ask_claude(_CALL_BRIEF.format(brief=json.dumps(brief, indent=1)[:6000],
                                          lo=MIN_PROB, hi=MAX_PROB,
-                                         mechs=" | ".join(MECHANISMS),
-                                         parts=" | ".join(PARTICIPANTS)))
+                                         mechs=" | ".join(mechs),
+                                         parts=" | ".join(parts)))
     call = parse_call(raw)
     if call is not None:
         # The arm rides on the row so the eventual comparison is possible; it CANNOT be assigned
diff --git a/tests/research/test_list_order.py b/tests/research/test_list_order.py
new file mode 100644
index 00000000..14367ada
--- /dev/null
+++ b/tests/research/test_list_order.py
@@ -0,0 +1,96 @@
+"""R0457: a shuffle whose permutation is not recoverable de-biases the estimate and destroys the
+residual, so the tests here are mostly about the LOG rather than about the shuffle.
+
+The desk's pre-existing shuffle (`run_external_panel.py:538`) is unseeded and writes nothing, so
+"how order-sensitive is this desk?" has been unanswerable since it shipped. These pin the property
+that makes the answer cheap: every call is reconstructible from its own log row.
+"""
+from __future__ import annotations
+
+import json
+
+import pytest
+
+from libs.research import list_order
+
+
+@pytest.fixture(autouse=True)
+def _isolated_log(tmp_path, monkeypatch: pytest.MonkeyPatch):
+    """Never append to the live desk log from a test -- that is the L0-class defect where the
+    suite writes fixture rows into a real store."""
+    log = tmp_path / "list_order_log.jsonl"
+    monkeypatch.setattr(list_order, "LOG", log)
+    return log
+
+
+def _rows(log) -> list[dict]:
+    return [json.loads(line) for line in log.read_text("utf-8").splitlines()]
+
+
+def test_permutation_reconstructs_the_shown_order(_isolated_log) -> None:
+    """THE LOAD-BEARING PROPERTY. A later reanalysis must be able to map an answer back to the
+    POSITION it was shown in, using only the logged row."""
+    items = [f"CLASS_{i}" for i in range(10)]
+    shown, perm = list_order.shuffled_with_log(items, organ="t", field="f")
+
+    row = _rows(_isolated_log)[0]
+    assert [items[i] for i in row["permutation"]] == shown
+    assert perm == row["permutation"]
+    assert sorted(perm) == list(range(10)), "a permutation must not drop or duplicate a candidate"
+
+
+def test_seed_makes_the_call_reproducible(_isolated_log) -> None:
+    """The recorded seed must regenerate the exact order, or the log is a description rather than
+    a reconstruction."""
+    items = list("abcdefgh")
+    shown, _ = list_order.shuffled_with_log(items, organ="t", field="f")
+    seed = _rows(_isolated_log)[0]["seed"]
+
+    replayed, _ = list_order.shuffled_with_log(items, organ="t", field="f", seed=seed)
+    assert replayed == shown
+
+
+def test_no_candidate_is_lost_or_invented(_isolated_log) -> None:
+    """Ordering may change; membership may not. A shuffle that silently truncated would be a far
+    worse defect than the bias it fixes."""
+    items = list(range(25))
+    shown, _ = list_order.shuffled_with_log(items, organ="t", field="f")
+    assert sorted(shown) == items
+
+
+def test_short_lists_are_still_logged(_isolated_log) -> None:
+    """A one-item list carries no bias, but dropping its row would make the log's denominator the
+    count of lists that happened to be long enough -- "this list was short" and "this call site
+    never ran" must not read identically (L1.60)."""
+    list_order.shuffled_with_log(["only"], organ="t", field="short")
+    list_order.shuffled_with_log([], organ="t", field="empty")
+
+    rows = _rows(_isolated_log)
+    assert [r["n"] for r in rows] == [1, 0]
+    assert [r["permutation"] for r in rows] == [[0], []]
+
+
+def test_two_calls_in_the_same_instant_do_not_share_a_permutation(_isolated_log) -> None:
+    """Seeding from a clock would let seats started in the same second draw the SAME order --
+    correlated 'randomisation' reads as agreement and would be the bias wearing a fix's clothes."""
+    items = list(range(40))
+    a, _ = list_order.shuffled_with_log(items, organ="t", field="f")
+    b, _ = list_order.shuffled_with_log(items, organ="t", field="f")
+    assert a != b
+
+    seeds = [r["seed"] for r in _rows(_isolated_log)]
+    assert seeds[0] != seeds[1]
+
+
+def test_the_wired_organs_actually_call_it(_isolated_log) -> None:
+    """A helper nobody calls is unwired capability, which the desk treats as bloat. This asserts
+    the two survivor-panel sites really route through the logger."""
+    from libs.research import survivor_panel
+
+    survivor_panel.round_one_prompt({"state": "x"})
+    fields = {r["field"] for r in _rows(_isolated_log)}
+    assert "bottleneck_classes" in fields
+
+    survivor_panel.cross_examination_prompt({"state": "x"}, [("seat-a", "aa"), ("seat-b", "bb")])
+    fields = {r["field"] for r in _rows(_isolated_log)}
+    assert "round_two_seat_order" in fields
```


---

## b4dc4893 AR miner 08-13 s2 CLOSE: GCC institutional layer carded against a documented unmet need (OP-076)
ITEM 3 -- the layer OP-075 re-aimed the seat toward. 10 hosts enumerated,
honest UA, exact codes; every recorded claim re-verified first-hand.

CARDED: data_axis_watchlist #33 VARA (Dubai) [s33: deferred(2026-08-24)
tier:3], aligned to R0193's own due date because it is an INPUT to that build,
not a second clock. Carded ONLY because it serves a named FAILED need: card 24
(Auer-Claessens regulatory-event timeline) is graded 'the timeline dataset is
the owed build' and records a targeted search for a published event list that
failed. Verified: robots 200 with ZERO non-comment directives; register 200
with 51 VL/YY/MM/NNN refs (the ref encodes year/month); unlicensed-VASP
blacklist 200 with 38 dated rows 2023/04/12-2025/05/15. Each row carries its
own issue date, so one pull yields a point-in-time panel on the ENTRY side;
exits still need snapshots because a vanished row leaves no trace.
And the limits, which matter more: ONE jurisdiction (not a panel), mostly
ENTITY-level events where the taxonomy classifies NATIONAL POLICY, and no
plausible channel to BTC/ETH -- NO MECHANISM IS CLAIMED. Timeline material for
an existing build, not an axis.

NOT CARDED, deliberately (a source earns a card by serving a named need;
cataloguing while verification is the bottleneck is breadth-theater): Saudi
CMA open-data API (no auth, 2,156 dated private funds) -- real, free, ZERO
crypto content; api.bitoasis.net live AED trade tape -- natural mechanism is
graveyarded; ADGM sitemap 1,109 dated announcements with lastmod -- the
second-best artifact, named as next ground.
UNMEASURED kept distinct from EMPTY (WS-005): SCA (200 pages, 401 API), QFMA
(200 shells, 0 dates), rain.bh/cbb.gov.bh/saudiexchange.sa (403; last has no
apex DNS), coinmena (robots 200 carrying a Next.js error shell).

OP-076: permission and reachability are INDEPENDENT IN BOTH DIRECTIONS on one
host. bitoasis.net apex robots explicitly names ClaudeBot Allow: / -- the
FIRST positive by-name mention in the fleet's entire access map, every prior
one a refusal -- yet 403s every content path, while api.bitoasis.net 403s its
own robots.txt and serves a full JSON trade tape. The two errors are NOT
symmetric: inferring permission from reachability breaches s13; inferring
unreachability from refusal merely loses ground. Plus two false-200 classes
(robots.txt that is not text/plain; 200 pages whose data sits behind a 401).

Lessons L0158/L0159. Ledger R0594 (every regional seat should run the ~8-query
OP-075 probe against its own language-is-the-moat premise). Next ground named
and re-ordered institutional-first; s3 and s4 items 5-7 carried with reasons.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit b4dc489325104a75dde722b4069a58e7e8ad322d
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:34:20 2026 +0000

    AR miner 08-13 s2 CLOSE: GCC institutional layer carded against a documented unmet need (OP-076)
    
    ITEM 3 -- the layer OP-075 re-aimed the seat toward. 10 hosts enumerated,
    honest UA, exact codes; every recorded claim re-verified first-hand.
    
    CARDED: data_axis_watchlist #33 VARA (Dubai) [s33: deferred(2026-08-24)
    tier:3], aligned to R0193's own due date because it is an INPUT to that build,
    not a second clock. Carded ONLY because it serves a named FAILED need: card 24
    (Auer-Claessens regulatory-event timeline) is graded 'the timeline dataset is
    the owed build' and records a targeted search for a published event list that
    failed. Verified: robots 200 with ZERO non-comment directives; register 200
    with 51 VL/YY/MM/NNN refs (the ref encodes year/month); unlicensed-VASP
    blacklist 200 with 38 dated rows 2023/04/12-2025/05/15. Each row carries its
    own issue date, so one pull yields a point-in-time panel on the ENTRY side;
    exits still need snapshots because a vanished row leaves no trace.
    And the limits, which matter more: ONE jurisdiction (not a panel), mostly
    ENTITY-level events where the taxonomy classifies NATIONAL POLICY, and no
    plausible channel to BTC/ETH -- NO MECHANISM IS CLAIMED. Timeline material for
    an existing build, not an axis.
    
    NOT CARDED, deliberately (a source earns a card by serving a named need;
    cataloguing while verification is the bottleneck is breadth-theater): Saudi
    CMA open-data API (no auth, 2,156 dated private funds) -- real, free, ZERO
    crypto content; api.bitoasis.net live AED trade tape -- natural mechanism is
    graveyarded; ADGM sitemap 1,109 dated announcements with lastmod -- the
    second-best artifact, named as next ground.
    UNMEASURED kept distinct from EMPTY (WS-005): SCA (200 pages, 401 API), QFMA
    (200 shells, 0 dates), rain.bh/cbb.gov.bh/saudiexchange.sa (403; last has no
    apex DNS), coinmena (robots 200 carrying a Next.js error shell).
    
    OP-076: permission and reachability are INDEPENDENT IN BOTH DIRECTIONS on one
    host. bitoasis.net apex robots explicitly names ClaudeBot Allow: / -- the
    FIRST positive by-name mention in the fleet's entire access map, every prior
    one a refusal -- yet 403s every content path, while api.bitoasis.net 403s its
    own robots.txt and serves a full JSON trade tape. The two errors are NOT
    symmetric: inferring permission from reachability breaches s13; inferring
    unreachability from refusal merely loses ground. Plus two false-200 classes
    (robots.txt that is not text/plain; 200 pages whose data sits behind a 401).
    
    Lessons L0158/L0159. Ledger R0594 (every regional seat should run the ~8-query
    OP-075 probe against its own language-is-the-moat premise). Next ground named
    and re-ordered institutional-first; s3 and s4 items 5-7 carried with reasons.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/desk_lessons.jsonl                  |   2 +
 docs/research/data_axis_watchlist.md     |  62 +++++++++++++++++
 docs/research/prospector_coverage.md     | 112 ++++++++++++++++++++++++++++++-
 docs/research/recommendation_ledger.json |  12 ++++
 docs/research/search_operator_library.md |  48 +++++++++++++
 5 files changed, 235 insertions(+), 1 deletion(-)

diff --git a/docs/desk_lessons.jsonl b/docs/desk_lessons.jsonl
index 29b0040f..4c432222 100644
--- a/docs/desk_lessons.jsonl
+++ b/docs/desk_lessons.jsonl
@@ -160,3 +160,5 @@
 {"id": "L0155", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Give every ledger a REFUTED exit, separate from FIXED. Without one, a finding a later pass proves wrong has only two moves and both are bad: rot forever demanding work nobody should do, or be marked fixed -- a false claim that also credits the author with a hit it never earned, corrupting the very scorecard used to judge who to keep.", "evidence": "2026-08-13: F0004 (superseded by F0020, 'whose mechanism and number are WRONG') and F0007 (F0008 says 'which was WRONG and is superseded' in its own first clause) had both been accepted-and-unfixed past the 14d bar with no legal way to close them. track_findings had raised->fixed->verified only.", "tags": ["governance"], "source": "owed-work-batch5-20260813", "enforced_by": "tests/scripts/test_findings_supersede.py::TestSupersessionIsNotAFix::test_the_scorecard_does_not_credit_a_superseded_finding"}
 {"id": "L0156", "learned": "2026-08-13", "cost": "wasted", "recurrence": 1, "lesson": "Before building a denominator or any instrument, grep for one that already exists UNREAD. An existing measurement with no consumer looks identical to a missing measurement from the fence's side, and only one of them needs building.", "evidence": "2026-08-13: R0570 said 'nothing counts attempts' for panel seats. True per-seat -- but data/audit_coverage.json budget_history had recorded {blanked, of} per RUN for 28 runs the whole time: 70 of 148 seat-calls = a 47% aggregate blank rate that three organs (seat-chronic fence, check_free_roster, model_upgrade) all reasoned about seat health without ever reading. Rowed R0583.", "tags": ["research"], "source": "owed-work-batch5-20260813", "accepted_uninjected": "a judgement about how to read a proposal, not a property any test can assert"}
 {"id": "L0157", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Record LLM consultation in DERIVES-FROM, and treat a post-2023 source with no citations as UNVERIFIABLE rather than independent. Split every mined page into an OBSERVATION layer (what they ran, held and lost -- uncontaminated) and an EXPLANATION layer (possibly model output); a convergence claim across two post-2023 pages must name the OBSERVATION they share, never the conclusion.", "evidence": "perp-screener.com/posts/btc-bot (2025-12-04): the entire greeks analysis is introduced as 'チャッピーの解説によると' (per ChatGPT) and the author twice tells readers to ask an LLM instead of him. Unlike an arXiv echo (GAP #85), an LLM echo leaves NO citation -- docs/research/search_operator_library.md OP-072", "tags": ["provenance"], "source": "JP frontier miner s4 2026-08-13", "accepted_uninjected": "No test can read a third-party web page's provenance; the enforcement is OP-072's per-region marker list applied at extraction time by every miner seat, plus recommendation R0591 to wire the DERIVES-FROM: NONE -> UNVERIFIABLE rule into libs/research/convergence.py where a test CAN then pin it."}
+{"id": "L0158", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Before assuming a region's LANGUAGE is the moat, measure whether that region's practitioners actually write in it: run a native-key repo search AND a developer-search by LOCATION, and compare against a sibling-language control. If the population exists but the native corpus does not, the language layer is the retail layer and the technical output is already inside the EN seat's ground -- re-aim the seat at what is native-language BY INSTITUTIONAL CONSTRUCTION (regulators, exchanges, courts, religious certification), which cannot migrate to English.", "evidence": "2026-08-13 GitHub, one instrument: AR arbitrage repos 1/0/0 and quant-trading 0 vs CN 1174 / RU 24 / KR 6; discriminator by location gave UAE 67 > Korea control 59. docs/research/search_operator_library.md OP-075", "tags": ["mining"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "a search-behaviour rule for digger seats; no code path to gate"}
+{"id": "L0159", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "When a MANDATED artifact stays empty, audit the instrument that would have written its rows BEFORE concluding the duty was skipped. A wrong error message and an absent finding are indistinguishable from the outside, and only one of them is a person's fault. Specifically: a retry loop that overwrites a single 'last error' variable reports the LAST endpoint's cause for EVERY failure -- so if the last endpoint is permanently dead, every failure of every cause wears its error.", "evidence": "video_locked_log.md sat at ZERO rows for weeks; measured cause was fetch_video_transcript.py surfacing api.piped.yt's NXDOMAIN in place of private.coffee's HTTP 500 LOGIN_REQUIRED bot-wall. Ledger R0592", "tags": ["ops"], "source": "AR miner s2 2026-08-13", "accepted_uninjected": "concerns how a human reads an empty artifact; not mechanically checkable"}
diff --git a/docs/research/data_axis_watchlist.md b/docs/research/data_axis_watchlist.md
index 4685150e..c4c616b5 100644
--- a/docs/research/data_axis_watchlist.md
+++ b/docs/research/data_axis_watchlist.md
@@ -2731,3 +2731,65 @@ By **type**: MATRIX 2,828 · **VECTOR 1,387** · **GROUP 142** · UNIVERSE 6 ·
 **THE ACQUISITION IMPLICATION (L1.11, and it is the honest one):** the highest-yield categories are exactly the ones the desk cannot buy and must manufacture — on-chain fundamentals and forward-expectation series. **No purchase is proposed and none is needed**; every analogue above is public. **[§33: screened -> docs/research/search_operator_library.md `wq-brain-pipeline` + this card]** — screened, not wired: this is a reference axis (equities, un-ingestible), and its deliverable is the SHAPE it gives the crypto-side hunt, already routed.
 
 **RESIDUAL GAP, graded:** the 4,367-field *contents* (2.8MB JSON) were **not** pulled — no desk use for equity field IDs, and bulk-copying an unlicensed artifact is not defensible under §13. The category/type counts are the whole transferable payload. **Re-entry condition (L1.16a):** if the desk ever builds a fundamentals-shaped crypto surface, the GROUP-typed field list becomes worth enumerating as a taxonomy menu.
+
+### 33. VARA (Dubai) crypto regulatory-event stream — dated licence register + named unlicensed-VASP blacklist + enforcement notices — grade: **verified-reachable, PARTIAL input to the R0193 owed build (one jurisdiction, not the panel)** [§33: deferred(2026-08-24) tier:3]
+
+**WHY THIS IS CARDED AT ALL, AND IT IS NOT "a regulator publishes things".** Card 24
+(`Regulatory-event timeline, 5-class taxonomy, Auer–Claessens`) is graded *"event gate EXISTS; the
+timeline dataset is the owed build"*, and its note records a **targeted web search for a published
+Auer–Claessens event list that FAILED** — the desk needs a dated regulatory-event dataset, could not
+find one, and scheduled a reconstruction (**R0193, due 2026-08-24**). This card exists **because that
+build has a documented data hole**, not because a source was spotted.
+
+**VERIFIED FIRST-HAND THIS RUN (honest UA `ClaudeBot`, s13 gate passed — `vara.ae/robots.txt` 200 and
+contains ZERO non-comment directive lines, so nothing is disallowed and no agent is named):**
+| artifact | URL | HTTP | verified content |
+|---|---|---|---|
+| public register | `/en/licenses-and-register/public-register/` | **200** | **51 licence refs** `VL/YY/MM/NNN` — the ref itself encodes **year/month** (`VL/26/08/002`, `VL/26/07/002`…), server-rendered, plus per-row issue date, licence type, activities, status |
+| **unlicensed-VASP blacklist** | `/en/enforcement/unlicensed-vasps/` | **200** | **38 dated rows**, named entities, `YYYY/MM/DD`, spanning **2023/04/12 → 2025/05/15** |
+| enforcement + warning notices | `/en/enforcement/`, `/en/regulations/regulatory-notices/` | **200** | dated notices, split Enforcement / Warning |
+| sitemap | `/sitemap/sitemap-index.xml` → `/sitemap/sitemap-0.xml` | **200** | 311 URLs (**no `lastmod`** — so the sitemap dates nothing; the dates live in the page bodies) |
+
+**THE ONE GENUINELY NICE PROPERTY:** every register row carries **its own issue date**, so a *single*
+pull already yields a point-in-time panel on the **entry** side — no repeated capture needed to know
+when each licence was granted. **Exits/revocations still require snapshots**, because a row that
+disappears leaves no trace; that asymmetry is the collector's design constraint, not a nice-to-have.
+
+**HONEST LIMITS — stated because the card is worth less than it first looks and the next reader must
+not inherit my enthusiasm:**
+1. **ONE JURISDICTION.** Auer–Claessens is a multi-country policy panel; VARA is Dubai. This is *a*
+   column, never the table.
+2. **WRONG EVENT CLASS, mostly.** The 5-class taxonomy classifies **national policy** actions (bans,
+   restrictions, AML/CFT regimes). VARA's stream is dominated by **entity-level** licensing and
+   small-VASP enforcement. The classes overlap only partially, and pretending otherwise would
+   contaminate the panel with events of a different kind.
+3. **ALMOST CERTAINLY NOT DIRECTLY TRADEABLE.** A Dubai enforcement notice against a small unlicensed
+   VASP has no plausible channel to BTC/ETH on Binance. **No mechanism is claimed here**, and none
+   should be inferred: this is timeline *material* for a build that already exists, not an axis.
+4. **NOT A PREMIUM PLAY.** The obvious GCC-venue idea is graveyarded — `era_crossvenue_fiat_premium_arb`
+   is buried 7×, the class is declared exhausted, and kimchi (its lone survivor) was killed 2026-08-01.
+
+**DISPOSITION:** `deferred(2026-08-24)` — deliberately aligned to **R0193's own due date**, because this
+is an *input* to that build and dating it separately would just create a second clock for one piece of
+work. This is alignment, not a snooze: the consuming recommendation is live, dated and owned.
+
+**ALSO ENUMERATED, GRADED, AND DELIBERATELY NOT CARDED** (the desk's measured bottleneck is
+verification, not cataloguing — a source earns a card by serving a named need):
+- **Saudi CMA open-data API** (`opendataapi.cma.gov.sa`, OpenAPI 3.0.1, **no auth**): 2,156 private
+  funds **fully dated**, 382 public funds, 230 institutions. Real and free — but **equities/funds, zero
+  crypto or virtual-asset content**. No desk need it serves. *(Trap worth recording: `PublicFunds`
+  advertises the same date keys as `PrivateFunds` and they are **null in 382/382** — a consumer keyed
+  on "the API returns dates" passes silently and gets nothing.)*
+- **`api.bitoasis.net`** — live AED trade tape (`/v1/exchange/trades/BTC-AED` **200**, real `id/type/
+  price/amount/timestamp`). Collectible, but its natural mechanism is the graveyarded regional-premium
+  family, so it gets **no card without a mechanism that is not already dead**.
+- **ADGM** — `sitemap.xml` 200 with **1,109 dated announcement URLs carrying `lastmod`** (FSRA fines,
+  fraud alerts, licence cancellations). The **second-best** artifact in the set and the natural next
+  jurisdiction column if R0193 wants one; the index page is client-side-paginated and useless, the
+  sitemap is the route.
+- **UNMEASURED, and kept distinct from empty:** SCA/UAE CMA (pages **200**, register data behind a
+  **401** API), QFMA (**200** Handlebars shells, 0 dates, and **zero** occurrences of "virtual asset"/
+  "crypto"/"VASP"), `rain.bh` / `cbb.gov.bh` / `saudiexchange.sa` (**403** on every path; `saudiexchange.sa`
+  apex has **no DNS record at all**), `coinmena.com` (`robots.txt` returns **200 with a Next.js error
+  shell and zero directives**). None of these is "closed" and none is "empty" — they are unmeasured,
+  and a status-code-only crawl would have scored several of them as open and harvested nothing.
diff --git a/docs/research/prospector_coverage.md b/docs/research/prospector_coverage.md
index 92fd374f..6ab98275 100644
--- a/docs/research/prospector_coverage.md
+++ b/docs/research/prospector_coverage.md
@@ -4272,7 +4272,7 @@ in my brief and is **explicitly carried to the next run**, unstarted). Recording
 
 ---
 
-### 2026-08-13 session 2 (AR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
+### 2026-08-13 session 2 (AR frontier miner) — **CLOSED.** All 3 items resolved to depth; deliverables committed.
 
 **RESUMED, NOT RESTARTED.** Read first: (a) `source_backlog_next.py` — 6 pending verification,
 **none AR**, and all 6 are actively owned elsewhere (BRAIN hunter s1/s2 took the grouping map,
@@ -4426,6 +4426,116 @@ correctly declined to log a platform block. Routed to `improvement_inbox.md` (se
 `scripts/`); the RU s3 "fetcher is ALIVE" verdict stands — the rotation *does* work, on content the
 wall spares.
 
+**video: 8 fetched-attempts, 1 succeeded, 7 LOCKED** (explicit zero-or-count per the mandate, so the
+log stays unambiguous between "never hit" and "never tried": **hit, hard, and logged**).
+
+---
+
+#### DEPTH LINE (per the depth mandate — depth per lead, and what depth surfaced that the surface did not)
+
+| lead | depth reached | what the SURFACE said | what DEPTH said |
+|---|---|---|---|
+| `mql5.com/ar` | **EXHAUSTED** (locale enumeration + 12-locale sibling control) | s1: "OPEN, correct path not yet found" | **the locale does not exist**; 11/11 siblings 200, `ar` alone 404 |
+| AR GitHub code layer | **EXHAUSTED at term level** (7 native keys × 3 arbitrage variants, + 4-script control, + location discriminator) | "260 repos for `تداول` — looks like a ground" | 0–1★ signal-bots only; **arbitrage 1, quant-trading 0, EA 0**; the practitioners exist and write in English |
+| AR video corpus | **comments/reply layer NOT reached — blocked at transcript** | rich, mechanism-bearing, AR-native | **7/8 bot-walled**; and the EN control proved the wall is not regional |
+| Piped instance rotation | **EXHAUSTED** (all 4 probed individually, exact codes) | "all Piped instances failed — DNS error" | **4 instances, 4 distinct causes**; the reported one was the dead domain's |
+| `aaoifi.com` | **document-path resolved** (robots → content path → real PDF URL) | robots 200, allows `*`, no by-name refusal ⇒ **OPEN** | **the entire document corpus sits under the one Disallowed path** |
+
+**HONEST SELF-ASSESSMENT AGAINST THE BREADTH-THEATER TEST:** this run mined **zero reply chains and
+zero forum threads** — the `arabsgate.com` thread layer (s1's ground #3) is still unstarted, and the AR
+video comment layer was unreachable because the transcript was. What it did instead was **kill two
+grounds with controls and re-aim the seat**, which is the higher-value trade on this particular run
+*only because* the item-1 measurement invalidates the layer those threads sit in. **That excuse does
+not extend to `arabsgate`**, which is a forum in the retail layer OP-075 predicts is thin — and
+**a prediction is not a measurement**, so it stays on the list to be tested rather than assumed.
+
+**PROVENANCE (mandatory).** **SOURCE:** all findings are first-hand measurements taken this run
+(GitHub search API, MQL5 hreflang, Piped `/streams`, `aaoifi.com` robots + content path), not readings
+of anyone's writeup. **DERIVES-FROM: NONE (checked)** for OP-074/OP-075 — no paper, post or thread was
+consulted or reacted to; they come from probing the desk's own grounds. The one input from outside my
+own run is **RU miner s3's same-day video claim**, which I **contradict by control** rather than extend
+— recorded explicitly so `convergence.py` never books these two seats as independent agreement (GAP #85).
+
+**CRYPTO-MECHANISM VOCABULARY CHECK (mandated flag):** this run produced **no tradeable mechanism card**,
+so it maps to none of the 24 CRYPTO_MECHANISMS — correctly, not by omission. Its output is **access,
+instrument and seat-aiming**, which is the honest result when the measurement says the ground you were
+pointed at cannot hold an edge. **No card was invented to fill the slot**, and no source was added to
+`data_axis_watchlist.md`: the AR video corpus is real but currently **unreachable**, and carding an
+unverifiable source while the desk's measured bottleneck is verification is the breadth-theater the
+brief names as a defect. It is logged to `research_memory` as `pending` and to `video_locked_log.md`
+instead — routed, not catalogued.
+
+---
+
+#### ITEM 3 — GCC REGULATOR + EXCHANGE LAYER — **CLOSED. One card, against a documented unmet need.**
+
+Item 1's measurement promoted this from third to first: OP-075 says the AR seat's edge must be in what
+is Arabic-native **by institutional construction**. 10 hosts enumerated, honest UA, exact codes; every
+claim below that I record was **re-verified by me first-hand** rather than taken on report.
+
+**THE FIND — `VARA` (Dubai), carded as `data_axis_watchlist.md` #33 `[§33: deferred(2026-08-24) tier:3]`.**
+It is carded **only because it serves a named, failed need**: card 24 (Auer–Claessens regulatory-event
+timeline) is graded *"the timeline dataset is the owed build"* and records a **targeted search for a
+published event list that FAILED**, with the reconstruction scheduled as **R0193, due 2026-08-24**.
+Verified: `robots.txt` 200 with **zero non-comment directive lines** (§13 clean, no agent named);
+public register **200 with 51 `VL/YY/MM/NNN` refs** whose ref *encodes year/month*; **unlicensed-VASP
+blacklist 200 with 38 dated rows, 2023/04/12 → 2025/05/15**; enforcement + warning notices dated.
+Every register row carries its own issue date, so **one pull already yields a point-in-time panel on the
+entry side** — exits still need snapshots, because a vanished row leaves no trace.
+
+**AND THE LIMITS, WHICH MATTER MORE THAN THE FIND:** one jurisdiction (not a panel); mostly
+**entity-level** events where Auer–Claessens classifies **national policy**; and **no plausible channel
+to BTC/ETH on Binance — no mechanism is claimed and none should be inferred.** It is timeline *material*
+for an existing build, **not an axis**. The obvious GCC-venue idea is foreclosed anyway: the
+regional-premium family is buried 7× and kimchi was killed 08-01.
+
+**ENUMERATED, GRADED, DELIBERATELY NOT CARDED** — a source earns a card by serving a named need, and
+cataloguing while the desk's bottleneck is verification is the breadth-theater the brief forbids:
+**Saudi CMA open-data API** (no auth, 2,156 dated private funds) — real, free, and **zero crypto
+content**, so no desk need; **`api.bitoasis.net`** live AED trade tape (200 JSON, real fills) — its
+natural mechanism is graveyarded; **ADGM** sitemap with **1,109 dated announcements carrying `lastmod`**
+— the second-best artifact and the natural next column *if* R0193 wants one.
+
+**UNMEASURED, KEPT DISTINCT FROM EMPTY** (WS-005): SCA/UAE CMA (pages 200, data behind a **401**),
+QFMA (200 Handlebars shells, 0 dates, **zero** "virtual asset"/"crypto"/"VASP"), rain.bh · cbb.gov.bh ·
+saudiexchange.sa (403 everywhere; the last has **no apex DNS record**), coinmena.com (`robots.txt`
+**200 carrying a Next.js error shell and zero directives**).
+
+**THE ACCESS FINDING, ROUTED AS `OP-076`:** on `bitoasis.net`, **permission and reachability are
+independent in BOTH directions** — the apex robots **explicitly names `ClaudeBot` with `Allow: /`**
+(verified by me; the **first positive by-name mention in the fleet's entire access map**, where every
+prior one was a refusal) yet **403s every content path**, while `api.bitoasis.net` **403s its own
+robots.txt and serves a full JSON trade tape**. The two errors are **not symmetric**: inferring
+permission from reachability breaches §13; inferring unreachability from refusal merely loses ground.
+*(Note s1 read this same file on 08-12 as "ClaudeBot unnamed". Either a misread or a change inside 24h —
+either way, a policy read is a dated observation, never a standing fact.)*
+
+---
+
+#### NEXT UN-EXHAUSTED GROUND (named before closing, per L1.35/L1.40)
+
+**The list is re-ordered by OP-075: institutionally-native Arabic first, retail-language layers last.**
+
+1. **ADGM announcement corpus** — `sitemap.xml`, **1,109 dated URLs with `lastmod`**, verified 200 and
+   un-mined. The natural **second jurisdiction column** for R0193 and the highest-value unstarted item.
+2. **VARA notice BODIES** — this run mined the register/blacklist to row level; the **notice texts**
+   (enforcement + warning) are unread, and the reasons inside them are the classifiable content.
+3. **`arabsgate.com` thread layer** — still zero threads mined across two sessions. OP-075 *predicts*
+   it is thin retail, **and a prediction is not a measurement** — test it rather than inheriting it.
+4. **AR video comment layer** — the corpus is rich and mechanism-bearing but transcript-blocked; the
+   **comment trees are plain HTML and were never attempted**. Rank by mechanism-keyword density, never
+   by votes (the habr lesson). This is the cheapest route into a video-first corpus while GAP #26 is open.
+5. **Era-archaeology: STILL UNSTARTED** (carried from s1) — dead GCC/Levant venue layer, *not* the
+   P2P-premium layer, which is graveyarded.
+6. **`arabictrader.com` / `rain.bh` / `cbb.gov.bh` / `adgm.com` apex** — all 403 on robots.txt itself.
+   Under OP-076 these are **UNMEASURED, not closed**; re-probe to read policy (reading policy is not
+   routing around access control).
+7. **Sharia/fatwa layer — the mechanism s1 left alive.** s1 retired the annual-event *design*
+   (`unmeasurable_by_construction`, MDE 3–6× the observed effect, 28 episodes = 21 years) and named the
+   only rescue: **cross-sectional expansion (7 events × N assets), never waiting.** That test is unrun.
+   Note `aaoifi.com` is an **OP-074-addendum host**: robots-OPEN, but its entire document corpus sits
+   under the one `Disallow`ed path, so the standards themselves are **not harvestable**.
+
 ---
 
 ## BRAIN HUNTER — session 1 (2026-08-11, dedicated daily organ, first run)
diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index 52a0ab3e..e0508a70 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -7503,6 +7503,18 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0594",
+   "source": "deep_sweep",
+   "summary": "AR seat re-aimed on measurement (OP-075): the AR language is not a moat -- AR-script repo search returns arbitrage 1/0/0 and quant-trading 0 vs CN 1174/RU 24/KR 6, while AR-region devs mentioning trading number ~99 (UAE 67 > Korea control 59). Population exists and writes in English, so its output is already in the EN seat's ground. Recommend every regional seat run the same ~8-query probe (native-key repo search + developer-search by LOCATION + sibling-language control) to test whether its own language-is-the-moat premise holds, since every seat has been assuming it.",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:33:45.717624+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
diff --git a/docs/research/search_operator_library.md b/docs/research/search_operator_library.md
index 6b08be9b..9f83c1fc 100644
--- a/docs/research/search_operator_library.md
+++ b/docs/research/search_operator_library.md
@@ -2287,3 +2287,51 @@ document URL and re-check it against the disallow list *before* claiming a corpu
 `Allow: /` on the host and `Disallow:` on its media root is a **CLOSED corpus on an OPEN site**, and it
 is the single most common shape on the WordPress-hosted institutional web — regulators, standards
 bodies, central banks and exchanges are overwhelmingly WordPress.
+
+### OP-076 PERMISSION AND REACHABILITY ARE INDEPENDENT — IN BOTH DIRECTIONS, ON THE SAME HOST   [active]
+class: access / §13 posture
+origin: AR frontier miner s2 (2026-08-13), GCC exchange + regulator layer, honest UA `ClaudeBot`
+validated-gain: caught a host that **permits us by name and serves us nothing**, and a sibling host that
+**refuses its own robots.txt and serves a full JSON trade tape** — the same venue, opposite failures.
+
+**THE PROVING INSTANCE — one venue, `bitoasis.net`, measured the same minute:**
+| surface | robots.txt | content | reading |
+|---|---|---|---|
+| `bitoasis.net` | **200 — `User-agent: ClaudeBot` / `Allow: /`** (and `anthropic-ai` Allow; `CCBot` Disallow) | **403** on `/`, `/en/`, `/en/prices`, `/en_sitemap.xml`, `blog.` | **permitted and unreachable** |
+| `api.bitoasis.net` | **403 — the policy file itself is refused** | **200 JSON**, incl. a real trade tape (`id/type/price/amount/timestamp`) | **unstated and fully reachable** |
+
+**Neither surface's policy predicts its own reachability, and the two point opposite ways.** The
+edge/CDN layer and the policy layer are configured by different teams with different intents, and
+nothing reconciles them — so a seat that infers one from the other is wrong roughly half the time,
+in whichever direction it happens to guess.
+
+**THE §13 CONSEQUENCE, AND IT IS NOT SYMMETRIC.** These two errors are *not* equally bad and must not
+be traded off:
+- Inferring **permission from reachability** ("it served me, so I may") is the one that **breaches
+  §13**. A 200 is never an authorisation.
+- Inferring **unreachability from refusal** ("robots 403s, so the host is closed") merely **loses
+  ground** — here it would have cost a live venue tape.
+So: **read the policy where it is stated, and measure reachability separately — never substitute
+either for the other.** Where policy is genuinely unstated (a 403 or 404 on `robots.txt`), that is
+**UNMEASURED**, not permission, and the honest move is to record it as such.
+
+**AND TWO FALSE-200 CLASSES FOUND IN THE SAME SWEEP** (both extend OP-068 — a 200 that is not content):
+1. **`coinmena.com/robots.txt` → HTTP 200, `text/html`, a Next.js `__next_error__` shell, ZERO
+   directives.** A parser reading this as "permissive robots, no rules" gets the answer exactly
+   backwards: nothing is served at all. **A robots.txt that is not `text/plain` is not a robots.txt** —
+   check the content type before parsing a permission from it.
+2. **`sca.gov.ae` (now `uaecma.gov.ae`) open-data section → every page HTTP 200, every dataset behind
+   `POST /api/PublicApi/GetContentList` returning 401.** The 200s are real; the data is not retrievable
+   through them. A status-code-only crawl scores this host **open and productive** and harvests nothing.
+
+**THE RULE THAT COVERS ALL THREE:** a host has **three independent properties** — *stated policy*,
+*reachability*, and *whether the reachable thing is the payload* — and this desk had instruments for
+only the first two. Grade all three, and let **UNMEASURED** stand where you only measured some
+(L1.28a: absence must never resolve to a clean verdict).
+
+**FLEET NOTE — the positive half is worth carrying too:** `bitoasis.net` is the **first host in the
+fleet's whole access map to name `ClaudeBot` with `Allow: /`**. Every by-name mention found until now
+was a refusal (hawamer, 5ch, DCInside, EliteTrader, Gate). Per-agent policy is real and it cuts **both**
+ways, so re-probe rather than carrying a binary open/closed prior — and note that AR s1 read this same
+file on 2026-08-12 as *"ClaudeBot unnamed, falls to `*`"*. Either it misread or the file changed inside
+24h; **either way the lesson is the same — a policy read is a dated observation, not a standing fact.**
```


---

## 59b8548b AR miner 08-13 s2: OP-074 addendum -- on WordPress, Disallow: /wp-content/uploads/ closes the whole document corpus on an otherwise-OPEN site
Measured on aaoifi.com (the Islamic-finance standards body -- under OP-075
exactly the institutionally-native Arabic layer this seat should hunt).
robots.txt 200, User-agent: *, NO by-name refusal: any seat grades this OPEN.
Content path /shariaa-standards/ 200 and fully readable. But every document
link on it resolves under /wp-content/uploads/ -- which that same robots.txt
disallows. Site navigable, corpus not harvestable.

This bites the CAREFUL seat specifically: the WordPress boilerplate reads as
housekeeping (stop indexing media files), so it gets skimmed, and a seat that
grades OPEN from the preamble then harvests PDFs violates robots while
believing it is compliant -- the s13 gate failing silently in the one
direction it cannot self-report. Rule: grade the path the DOCUMENTS live on,
never the host; resolve one real document URL against the disallow list before
claiming a corpus is reachable. Regulators, standards bodies, central banks
and exchanges are overwhelmingly WordPress, so this shape is the common case
on the institutional web the seat was just re-aimed toward.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 59b8548b0e79add696e09be5bc4a5b165c586cb3
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:29:59 2026 +0000

    AR miner 08-13 s2: OP-074 addendum -- on WordPress, Disallow: /wp-content/uploads/ closes the whole document corpus on an otherwise-OPEN site
    
    Measured on aaoifi.com (the Islamic-finance standards body -- under OP-075
    exactly the institutionally-native Arabic layer this seat should hunt).
    robots.txt 200, User-agent: *, NO by-name refusal: any seat grades this OPEN.
    Content path /shariaa-standards/ 200 and fully readable. But every document
    link on it resolves under /wp-content/uploads/ -- which that same robots.txt
    disallows. Site navigable, corpus not harvestable.
    
    This bites the CAREFUL seat specifically: the WordPress boilerplate reads as
    housekeeping (stop indexing media files), so it gets skimmed, and a seat that
    grades OPEN from the preamble then harvests PDFs violates robots while
    believing it is compliant -- the s13 gate failing silently in the one
    direction it cannot self-report. Rule: grade the path the DOCUMENTS live on,
    never the host; resolve one real document URL against the disallow list before
    claiming a corpus is reachable. Regulators, standards bodies, central banks
    and exchanges are overwhelmingly WordPress, so this shape is the common case
    on the institutional web the seat was just re-aimed toward.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/search_operator_library.md | 26 ++++++++++++++++++++++++++
 1 file changed, 26 insertions(+)

diff --git a/docs/research/search_operator_library.md b/docs/research/search_operator_library.md
index f38b43f4..6b08be9b 100644
--- a/docs/research/search_operator_library.md
+++ b/docs/research/search_operator_library.md
@@ -2261,3 +2261,29 @@ _Search keys, not trivia. Counts are GitHub repo-search totals under the honest
 **THE LEXICON'S OWN LESSON (s2):** `أربيتراج` returns **0 GitHub repos and a full page of YouTube
 results**. A term's count is **per-surface**, and grading a term dead from one surface is the
 false-exhaustion mode OP-054 names. Record the surface beside the count, always.
+
+#### OP-074 ADDENDUM (AR miner s2, 2026-08-13): on WordPress, `Disallow: /wp-content/uploads/` DISALLOWS THE ENTIRE DOCUMENT CORPUS
+
+**MEASURED:** `aaoifi.com` (AAOIFI — the Islamic-finance standards body, and under **OP-075** exactly
+the institutionally-native Arabic layer an AR seat should hunt). `robots.txt` = **200**, `User-agent: *`,
+**no by-name refusal of any AI agent** — a host any seat would grade **OPEN**. Its disallow list is the
+stock WordPress boilerplate: `/wp-admin/`, `/wp-content/`, **`/wp-content/uploads/`**, `/uploads/`.
+
+Then the content path: `https://aaoifi.com/shariaa-standards/?lang=en` = **200**, fully readable — and
+**every single document link on it** resolves to `https://aaoifi.com/wp-content/uploads/YYYY/MM/*.pdf`.
+
+**THE POINT:** on WordPress, `/wp-content/uploads/` **is** the media store. A host that allows `*`
+everywhere *except* uploads has therefore **disallowed its whole PDF/document corpus** while presenting
+as open. The HTML is browsable; the standards, rulings, research papers and conference reports — the
+only part with research value — are not fetchable under §13.
+
+**WHY IT BITES PRECISELY THE CAREFUL SEAT:** the boilerplate exists to stop media-file indexing, not to
+protect a corpus, so it reads as housekeeping and gets skimmed. A seat that grades the host OPEN from
+the preamble and then harvests PDFs **is violating robots while believing it is compliant** — the
+§13 gate failing silently in the one direction the gate cannot self-report.
+
+**THE RULE:** grade the **path the documents actually live on**, never the host. Resolve one real
+document URL and re-check it against the disallow list *before* claiming a corpus is reachable.
+`Allow: /` on the host and `Disallow:` on its media root is a **CLOSED corpus on an OPEN site**, and it
+is the single most common shape on the WordPress-hosted institutional web — regulators, standards
+bodies, central banks and exchanges are overwhelmingly WordPress.
```


---

## 6395950f AR miner 08-13 s2: the AR language is not a moat (OP-075), mql5/ar never existed (OP-074), video_locked_log gets its first rows
ITEM 1 -- overturns my own s1 grade twice over.
(a) mql5.com/ar DOES NOT EXIST: MQL5 publishes 11 hreflang locales, ar is not
one; /{loc}/code = 200 for 11/11 real locales, 404 for ar alone. s1 graded it
OPEN from robots.txt and put it at #1 priority for this run. robots answers
'may I', never 'is there anything here' -> OP-074 (grade existence separately,
with a sibling control; a ground graded from robots alone is OPEN (existence
UNMEASURED), never bare OPEN).
(b) THE AR LANGUAGE IS NOT A MOAT -> OP-075. AR-script repo search: arbitrage
1/0/0, quant-trading 0, expert-advisor 0; every hit 0-1 stars, all Telegram
signal bots. Calibrated denominator on the same instrument: CN 1,174 / RU 24 /
KR 6. Two hypotheses survived that table and demanded opposite actions, so I
ran the discriminator by developer LOCATION instead of language: UAE 67 >
Korea control 59, ~99 AR-region devs mentioning trading. H1 (no population)
REFUTED, H2 (writes in English) CONFIRMED -- so their output is already in the
EN seat's ground and there is no language arbitrage to win. NOT 'the ground is
thin' (that is the R0466/WS-005 false null): a precise verdict on ONE layer,
which re-aims the seat at what is native-language BY INSTITUTIONAL
CONSTRUCTION -- regulators, exchanges, courts, the Sharia layer.

ITEM 2 -- video_locked_log.md has its FIRST ROWS EVER (8 attempted, 1 fetched,
7 locked), and the CONTROL is the deliverable. EN crypto videos at 142k/50k/33k
views bot-wall IDENTICALLY to AR at 538k/47k/31k; only a ~1.6bn-view control
passed. Language is ORTHOGONAL -- this refutes the English half of RU miner
s3's same-day 'works on popular English, fails on cold non-English'. Had I
logged only my AR rows the log would have argued for a REGIONAL proxy, the
wrong purchase on the one artifact whose whole job is deciding what to buy.
GAP #26 must price a GENERAL authenticated route; mechanism UNIDENTIFIED and
stated as such (boundary sits between 538k and 1.6bn views).
And why the log sat empty for weeks: NOT digger laziness but an INSTRUMENT
fault (R0592). fetch_video_transcript.py reports only the LAST instance's
error and that instance (api.piped.yt) is a dead domain, so a platform
bot-wall is displayed to every digger as a local DNS fault. Four instances,
four distinct causes: 500 LOGIN_REQUIRED / 502 / 301 / 000 NXDOMAIN.
AR corpus is VIDEO-FIRST -- the natural complement to OP-075: the AR technical
layer is absent from TEXT, not from the world.

Ledger R0592 (fetcher misreporting) + R0593 (GAP #26 buys general, not
regional). Blind-spot self: audit the INSTRUMENT before reading an empty
duty-artifact as non-compliance. Research-memory: 1 rejected mission, 1
pending dataset. Operator library +OP-074 +OP-075 + AR lexicon extended
(18 terms; per-surface counts, since 'arbitraj' is 0 on GitHub and abundant
on video).

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 6395950fc640f20c68c283a6237cb93dc84fe1cf
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:28:01 2026 +0000

    AR miner 08-13 s2: the AR language is not a moat (OP-075), mql5/ar never existed (OP-074), video_locked_log gets its first rows
    
    ITEM 1 -- overturns my own s1 grade twice over.
    (a) mql5.com/ar DOES NOT EXIST: MQL5 publishes 11 hreflang locales, ar is not
    one; /{loc}/code = 200 for 11/11 real locales, 404 for ar alone. s1 graded it
    OPEN from robots.txt and put it at #1 priority for this run. robots answers
    'may I', never 'is there anything here' -> OP-074 (grade existence separately,
    with a sibling control; a ground graded from robots alone is OPEN (existence
    UNMEASURED), never bare OPEN).
    (b) THE AR LANGUAGE IS NOT A MOAT -> OP-075. AR-script repo search: arbitrage
    1/0/0, quant-trading 0, expert-advisor 0; every hit 0-1 stars, all Telegram
    signal bots. Calibrated denominator on the same instrument: CN 1,174 / RU 24 /
    KR 6. Two hypotheses survived that table and demanded opposite actions, so I
    ran the discriminator by developer LOCATION instead of language: UAE 67 >
    Korea control 59, ~99 AR-region devs mentioning trading. H1 (no population)
    REFUTED, H2 (writes in English) CONFIRMED -- so their output is already in the
    EN seat's ground and there is no language arbitrage to win. NOT 'the ground is
    thin' (that is the R0466/WS-005 false null): a precise verdict on ONE layer,
    which re-aims the seat at what is native-language BY INSTITUTIONAL
    CONSTRUCTION -- regulators, exchanges, courts, the Sharia layer.
    
    ITEM 2 -- video_locked_log.md has its FIRST ROWS EVER (8 attempted, 1 fetched,
    7 locked), and the CONTROL is the deliverable. EN crypto videos at 142k/50k/33k
    views bot-wall IDENTICALLY to AR at 538k/47k/31k; only a ~1.6bn-view control
    passed. Language is ORTHOGONAL -- this refutes the English half of RU miner
    s3's same-day 'works on popular English, fails on cold non-English'. Had I
    logged only my AR rows the log would have argued for a REGIONAL proxy, the
    wrong purchase on the one artifact whose whole job is deciding what to buy.
    GAP #26 must price a GENERAL authenticated route; mechanism UNIDENTIFIED and
    stated as such (boundary sits between 538k and 1.6bn views).
    And why the log sat empty for weeks: NOT digger laziness but an INSTRUMENT
    fault (R0592). fetch_video_transcript.py reports only the LAST instance's
    error and that instance (api.piped.yt) is a dead domain, so a platform
    bot-wall is displayed to every digger as a local DNS fault. Four instances,
    four distinct causes: 500 LOGIN_REQUIRED / 502 / 301 / 000 NXDOMAIN.
    AR corpus is VIDEO-FIRST -- the natural complement to OP-075: the AR technical
    layer is absent from TEXT, not from the world.
    
    Ledger R0592 (fetcher misreporting) + R0593 (GAP #26 buys general, not
    regional). Blind-spot self: audit the INSTRUMENT before reading an empty
    duty-artifact as non-compliance. Research-memory: 1 rejected mission, 1
    pending dataset. Operator library +OP-074 +OP-075 + AR lexicon extended
    (18 terms; per-surface counts, since 'arbitraj' is 0 on GitHub and abundant
    on video).
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 docs/research/improvement_inbox.md       |  49 ++++++++++
 docs/research/prospector_coverage.md     | 158 ++++++++++++++++++++++++++++++-
 docs/research/recommendation_ledger.json |  24 +++++
 docs/research/search_operator_library.md | 121 +++++++++++++++++++++++
 docs/research/video_locked_log.md        |  49 ++++++++++
 5 files changed, 400 insertions(+), 1 deletion(-)

diff --git a/docs/research/improvement_inbox.md b/docs/research/improvement_inbox.md
index 392694a1..b777aeb7 100644
--- a/docs/research/improvement_inbox.md
+++ b/docs/research/improvement_inbox.md
@@ -2274,3 +2274,52 @@ is a graveyard-grade verdict issued on a target that changed underneath the spli
 target-side check — the seat is frozen out of that tree and a grep from a research seat proves a name exists,
 never that a code path runs (the desk's own most-repeated lesson). **The claim "the desk does not check
 target stationarity" is UNVERIFIED and is the first thing the implementing seat should falsify.**
+
+---
+
+## 2026-08-13 — AR frontier miner s2: the video-transcript fetcher misreports WHY it failed, and that is why the purchase-evidence log sat empty
+
+**SOURCE:** measured this run, honest UA, against `scripts/fetch_video_transcript.py` and the four Piped
+instances it rotates. Seat is research-frozen out of `scripts/`, so this is **PROPOSED, NOT BUILT**.
+
+**THE DEFECT.** `youtube()` loops the 4 instances and on each failure overwrites a single `last = <error>`
+string, finally raising `SystemExit(f"all Piped instances failed -- last: {last}")`. Only the **last**
+instance's error ever reaches the operator. Measured causes, same minute, same box, same video:
+
+| instance | HTTP | actual cause |
+|---|---|---|
+| `api.piped.private.coffee` | **500** | YouTube bot-wall: `SignInConfirmNotBotException … LOGIN_REQUIRED` |
+| `pipedapi.kavin.rocks` | **502** | instance-side gateway failure |
+| `pipedapi.adminforge.de` | **301** | API moved off-host (redirects to `adminforge.de/search?…`) |
+| `api.piped.yt` | **000** | **dead domain — DNS NXDOMAIN** |
+
+Four distinct causes demanding four different responses, collapsed into one message — and because the **dead
+domain is last in `_PIPED`**, every failure of every cause is reported as `URLError … Name or service not
+known`. **A platform bot-wall is displayed as a local DNS fault.**
+
+**WHY IT MATTERS BEYOND TIDINESS — it silently defeated a standing principal mandate.** `video_locked_log.md`
+is the *sole* evidence gate for GAP #26 (paid transcript/proxy unlock) and it had **zero rows** after weeks of
+daily digs across seven regions. The mandate text reads that emptiness as diggers skipping the duty. The
+measured cause is the instrument: a digger who hit the wall saw a message indicating a problem on **their own
+box**, not a platform refusal, and correctly declined to log a platform block. **The log was empty because the
+error message was wrong**, and an artifact whose only job is to justify a purchase was being fed a false
+premise. This is the desk's UNMEASURED-REPORTED-AS-OK class pointed at a *cause* field rather than a value.
+
+**PROPOSED FIX (three lines of behaviour, no new capability):**
+1. Collect **per-instance** `(host, http_code, cause)` and report **all** of them, never just the last.
+2. Drop `api.piped.yt` (dead domain) or move it last-but-report-separately, so a permanently-dead host stops
+   being the default explanation for every failure.
+3. Classify `LOGIN_REQUIRED` / `SignInConfirmNotBotException` explicitly as **PLATFORM-WALL** and say so in the
+   exit message, with a pointer to `video_locked_log.md` — the operator is at that moment holding exactly the
+   evidence the log exists to collect, and nothing tells them so.
+
+**VERIFICATION OWED BEFORE ANYONE ACTS:** I read `scripts/fetch_video_transcript.py` directly and measured all
+four endpoints with `curl`, so the instance table is first-hand. What I did **not** do is check whether any
+other organ consumes this exit string (a caller keying on the message text would change with it). One grep
+from a seat with write access to `scripts/` settles it.
+
+**RELATED, and it corrects a same-day sibling claim:** RU miner s3 (2026-08-13) recorded that video access
+*"works on popular English content and fails on cold non-English"*. The English half is **refuted by control**:
+EN crypto videos at 142k / 50k / 33k views wall identically to AR videos at 538k / 47k / 31k. Language is
+orthogonal; only a ~1.6bn-view control passed. Full table and the GAP #26 consequence in
+`docs/research/video_locked_log.md`.
diff --git a/docs/research/prospector_coverage.md b/docs/research/prospector_coverage.md
index 313031ed..92fd374f 100644
--- a/docs/research/prospector_coverage.md
+++ b/docs/research/prospector_coverage.md
@@ -21,7 +21,7 @@ _Seeded 2026-07-18; every family unvisited -- the first run biases per the rotat
 | Non-English forums — **JP** | 2026-08-13 | 4 | **s4 (2026-08-13, JP frontier miner): THE DEEP-FOREST SELF-HOSTED TAIL OPENED — after 08-12 closed 62% of the mapped corpus, a UA-matrix probe over 10 hosts found **8/9 self-hosted botter blogs serve 200 to ClaudeBot and 4 have no robots.txt at all** → **OP-073** (an AI-crawler denylist is a PLATFORM product decision; re-scope the HOST COLUMN, never the region — the JP ground went from "thinning" to a fresh 20-entry queue across 12 open domains with one group-by). **zenn.dev sharpened the §13 finding into its worst form: robots.txt now returns 200 AND explicitly allows `*`, while the content path returns 403 — every standard §13 check comes back green and permissive over a closed ground.** **OP-072, the run's best find and fleet-wide: the post-2023 practitioner corpus is LLM-CONTAMINATED** — the mined options post's entire mechanism analysis is self-disclosed ChatGPT output (チャッピー), so practitioners in unrelated regions now converge because they queried the same weights, not because the world taught them; worse than the arXiv echo GAP #85 models (a paper echo leaves a citation, an LLM echo leaves nothing), fixed by per-region markers + an observation/explanation split + `NONE (checked)` made illegal post-2023 (→ UNVERIFIABLE), and it hands era-archaeology a new argument: **pre-2023 archives are structurally uncontaminated.** MINING: `blog_UKI`'s BitMEX spoofing **intervention** (not an observation) decomposes OFI → **the market-order take components dominate; the displayed book is not where the information is**, so `book imbalance` and `aggressor flow` may be ONE axis and the desk's L1.18 independence count too high by one (EV 0.0002 REJECT as a trade → routed to improvement_inbox as a feature-redundancy fact; the strategy is prohibited conduct and is not proposed). `pip_pip_pip_p` **corroborates the 08-01 richmanbtc kill from the opposite fee sign** (the rule-based core is down-sloping on Binance in every period since 2021, incl. the 2024-11/12 bull) + names a live desk gap: **the desk checks FEATURE-distribution stationarity, apparently never the TARGET's**. `gitan.dev`'s 2023↔2024 venue-survey **pair** (a free longitudinal diff) → **WS-013**: a 13-month +2% JP margin dislocation, a venue REPLACING an SFD divergence penalty with a funding rate, and its resting long-pays-short constant **numerically identical to Binance's 0.01%/8h interest component** — an independent venue corroborating this seat's 08-12 clamp census that the 1bp print is a copied CONVENTION. Graveyard ×1 (`rev_calendar_spread_iv_convergence`, refuted at source: vega-neg + theta-neg has no favourable regime; its transferable half is **a hedged leg with a contractual expiry un-hedges itself on a schedule** — a risk-rail event for any future dated-future-vs-perp basis trade). Universe source **102** (venue fee schedule as the conditioning variable for every volume feature; EV 0.0058 QUEUE, the session's only gate survivor of 4 scored). +8 OBSERVED JP lexicon rows (鞘/アビトラ/見せ板/お蔵入り/反面教師/チャッピー/限月/爆損). **Self-caught defect: my own 08-12 next-run queue was 40% dead on arrival** — titled "qiita-hosted", it named 3 zenn.dev entries I had ruled HARD STOP in the same note. Video: 0 fetched, 0 locked.** —  **s3 (2026-08-12, JP frontier miner): §13 REGRESSION — note.com + zenn.dev now serve 403 to ClaudeBot/GPTBot/CCBot/Bytespider AT THE CDN EDGE while BOTH robots.txt files are clean of any such rule (Googlebot/curl/SomeRandomBot get 200 ⇒ a curated AI-crawler denylist, not a WAF heuristic). HARD STOP, archives included; NOT routed around (Claude-User returns 200 and was deliberately not used). Closes 116/187 (62%) of the mapped botter corpus incl. all 3 planned targets; rollout DATED between 08-04 and 08-12 by this seat's own successful prior reads → **OP-052** (probe the CONTENT PATH with a UA matrix; robots.txt is necessary, not sufficient) + lesson **L0096** + **R0466** (a blocked ground and an exhausted ground are byte-identical to any fetch path that treats non-200 as no-content — a FALSE NULL that silently retires a region). **Past-due PI-vs-FR deferral RESOLVED** (`data/jp_funding_clamp_census.json`): clamp verified by positive control (BTC 49/60, DOGE 46/60); **41.6% of the owned 8h panel and 68.8% of the live 812-symbol cross-section sit on a censoring constant**, 74.9 bps of real premium dispersion hides inside one 56-name tie group — the root cause of the already-paid-for "42 perps at the 1bp floor" churn incident; censoring DECAYS 68.8%(2019)→10.7%(2026) ⇒ **backtest-integrity upgrade first, live-signal second**; EV 0.0193 QUEUE, novelty 0.726, NOT promoted (screen still owed). **L1.47 corroborated with a count → R0465: 426/812 (52.4%) of live perps settle on 4h, only 385 on the 8h that `held/8.0` assumes** ("many" is the majority); ranking damage honestly modest (Spearman 0.959). JP funding-settlement sandwich (qiita/lud-botter, DERIVES-FROM: NONE checked ⇒ genuine independent convergence with L1.47) **EV 0.0006 REJECT** as published — dead at source, venue changed settlement rules mid-operation — with the observation routed as execution-timing **EV 0.0087 QUEUE**; JP **Travel Rule 2023-06-01** era marker (domestic↔overseas arb killed by regulation, not competition). **マケデコ (`market-api`) NEW GROUND opened + mapped: 74 entries 2023–2025 (2021/22 = 404, series began 2023), JP EQUITIES not crypto, 74% on the closed hosts**; J-Quants axis catalogued-unverified (row 29). Video: 0 fetched, 0 locked.** — **s1 (2026-08-01, JP frontier miner, seat's first run).** §13: **5ch.net + all sister hosts REFUSE `ClaudeBot` by name** (Cloudflare-*managed* block → treat as a platform rollout, not a site decision; re-check on entry, never cache); note/qiita/zenn/GMO/bitbank clean. **bitFlyer axis CLOSED after 4 deferrals** — the "403/WAF/needs-a-human" record was a **tarpit**, the block is **per-hostname** (api+lightning serve 200 from the *same edge IP*), the "never archived" claim was a wrong CDX host+slug, and the ToS was then read: it retains rights in *"data such as transaction prices"* → **`restricted-by-licence`**, which pre-emptively killed `getchats`, `getfundingratehistory` and an archived keyless 15-min BTC/JPY series (2014-10→, Wayback-only) before any were carded. **Replacements found same run: GMO Coin free keyless tick tape (2018-09-05→, 28 spot + 12 margin, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank — both licence-unread, no ingest (R0309/R0310).** **richmanbtc lineage (the C62 "gem", unstarted 12 days) KILLED**: the edge is a bare ATR×0.5 limit, the ML adds ~nothing, and the maker fee was **zero-or-negative across the whole backtest** → a venue-subsidy harvest, dead on 3 venues. Salvaged 3 CC0 tools (p-mean order-sensitive decay bar — **published error-rate formula reproduced BROKEN**; time-adversarial feature screen; `publicGetExpiredFutures` for R0239). New: **OP-043/044/045** + OP-041 refinement. Era-archaeology (2017 bitFlyer-FX **SFD**, Mt.Gox 5ch) **UNSTARTED**; JP lexicon seeds still **unverified**. Next: **the 仮想通貨botter Qiita Advent Calendar 2021–2025, never touched.** |
 | Non-English forums — **BR** | 2026-08-12 | 2 | **s2 (2026-08-12) — THE NATIVE KEY WAS HIDING THE DESK'S ONLY NEVER-HUNTED FAMILY.** Cleared s1's 8-day-overdue ITEM 3. Measured, same corpus same minute: `pairs trading brasil` → **0 repos**, `cointegração` (native PT key) → **30**, essentially all genuine statarb, several crypto-native — so a seat querying the English term grades BR statistical arbitrage DEAD on a clean zero, and `strategy_coverage.json` reports **STATISTICAL-ARBITRAGE as the only never-hunted family (0/14)**. `long short` is unusable bare in PT-BR via **two independent collisions** (LSTM written out in full; C's `unsigned long/short`) — the vocabulary sibling of the RU ticker collision. **OP-054.** Depth on `mateusmartinelli/tcc` (crypto pairs trading; Gatev + Caldeira–Moura + Rad–Low–Faff): more rigorous than average (loads T-bills, computes excess returns) yet **three code/comment contradictions all in the config block** — cost 0.001 commented "0.05%" (**2×**, conservative), entry **1.5σ** commented "2σ as per paper" (**not** conservative), formation **90d** commented "252" — plus **zero funding accounting** and top-10 pairs from ~4,950 candidates at p<0.10 with **no multiplicity correction** (~495 expected false pairs). **OP-055.** Killed `pedhsm/systematic-research-framework`'s MCPT: it permutes **realised returns** and scores sharpe/cagr/vol, **all order-invariant** — verified by independent reimplementation, 500 perms × 4 series, **max−min = 1.1e-15**; FP non-associativity then makes the p-value a rounding-order hash (**winner p=0.978, catastrophe p=0.618**). A **wall, not a bar** → graveyard + **OP-056**. **The desk was already ahead** (`bar_permutation.py` permutes bars, with a measured `_TIE_RTOL` + add-one) ⇒ genuine cross-ecosystem convergence, **NO BUILD**. RFB: s1's *"decaying deadline"* was an inferred rate — census gives **23 dates, 12 live / 12 dead, clean boundary at 2023-03-02|2023-05-03, 4 with no capture at all**; **rate UNMEASURED** (two rival hypotheses, opposite urgency, falsifier recorded) and the series is **~4 months unpublished against a 13-month hiatus precedent**. BR lexicon opened (none existed); supplied seeds scored **0/3 as dark-forest keys**. Video: **0 fetched, 0 locked — not attempted**, named in next ground. Next: `Vido/zecontinha` fork tree + crypto subset, `TCC` as a structural key, PT-BR video, B3 (still unprobed), era-archaeology (still not started). |
 | _(BR s1 history)_ | 2026-08-01 | 1 | **s1 (2026-08-01, BR frontier miner, seat's first run).** **§13: the KR/JP by-name-block pattern does NOT generalise** — 18 hosts swept full-file over 17 AI-crawler tokens, **zero BR blocks**; the community layer (bastter, InfoMoney, MQL5-PT, Investing BR, bitcointalk, YouTube, Telegram) is **open**, so KR/JP was a property of *those* consumer portals, not a global rollout (OP-041 corrected). One **HARD STOP: `reddit.com` `Disallow: /`** to everyone — a *global* decision that bites BR hard (r/investimentos, r/farialimabets, r/BrasilBitcoin). **Pre-emptive graveyard check killed one third of my own brief before any searching:** the seat's era target "BR P2P premium" is already `mercado_br` **REJECTED** (graveyard:81) inside a family killed **5×** whose lone survivor (kimchi) was itself refuted 07-30 — no L1.16a enabling change exists, so the **seed list** is the defect. **THE FIND: RFB `criptoativos_dados_abertos`** — Brazil's **mandatory** national crypto-reporting panel (every domestic exchange reports **every** operation, no minimum; P2P + foreign venues >R$30k), free and keyless: **77 months Ago-2019→Dez-2025, 66 assets, 4,206 asset-months**; Dez-2025 = **3,544,986 taxpayers / R$43.1bn**; all-time **USDT R$1.004tn vs BTC R$269bn (3.7×)** ⇒ a **dollarization**, not speculation, mechanism. **Deliberately NOT screened** — n=77 monthly + 3.5mo lag vs a ~4,268-obs bar would manufacture a false null (L1.25); reported **UNDERPOWERED** with the cross-sectional enabling change named. **The depth layer was the prize: a FREE POINT-IN-TIME VINTAGE STACK** — RFB republishes monthly under a dated filename and **42/42 common months are revised** (worst Março-2023 **+40.9%**; a month **2.4y old** still moved), systematically upward, so backtesting today's file is a **+41% look-ahead in the CONDITIONING variable** (R0289 class — passes every return-series leak check, fails toward a FALSE POSITIVE). Proven recoverable: 23+ dates in CDX, and a **live-404 vintage restored intact** via `web.archive.org/<ts>id_/`. Read at all only by writing a **stdlib OLE2+BIFF8 reader** (no xlrd on this box) validated by the data's **own conservation law: 78/78 rows, residual 0.00e+00**. New **OP-046 / OP-047 / OP-035-BR**; R0316–R0318. Incidental: a **BR-only tokenized-RWA universe** in a government dataset (**MBPRK = tokenized *precatórios***, MBCONS, IMOB01, MCO2; **BRZ = 92.4M ops**, a payment rail). **ITEM 3 (PT-BR practitioner ground) explicitly DEFERRED to 08-04, not dropped.** Next: practitioner ground first, then **mirror the vintage stack before it decays**, B3, Pix fraud stats. |
-| Non-English forums — **AR** | 2026-08-12 | 1 | **s1 (2026-08-12, AR frontier miner, seat's first run) — IN PROGRESS.** No AR row existed before this run (`grep -ic arabic` = 0). **Pre-emptive graveyard check killed the seat brief's ENTIRE era target before any searching:** MENA/Egypt/Lebanon P2P-premium-under-FX-restriction is `era_crossvenue_fiat_premium_arb` (buried **7×**) inside the regional-premium class the desk declared **exhausted** (`try_premium_timing` — the Turkey capital-control analog, the closest MENA case that exists — REJECTED; kimchi, the lone survivor, itself KILLED 08-01); `strategy_coverage.json` has CROSS-VENUE-PREMIUM = HUNTED/9. Second consecutive seat (after BR) handed a dead era target ⇒ **the seed list is the defect**. Items: (1) §13 UA-matrix access map (OP-052) — AR unmapped in BOTH directions, and R0466 makes an unmapped ground's null uninterpretable; (2) report+replace the dead brief; (3) **replacement axis: Hijri/Ramadan calendar + Sharia-compliance forced-flow** — novelty-clean at **0 hits** across graveyard/both watchlists/universe map/vault, maps to NONE of the 24 CRYPTO_MECHANISMS, and lunar-vs-Gregorian drift (~11d/yr) makes it orthogonal to every Gregorian calendar effect by construction. See session note below. |
+| Non-English forums — **AR** | 2026-08-13 | 2 | **s2 (2026-08-13) — THE SEAT IS RE-AIMED, on measurement.** (1) **`mql5.com/ar` DOES NOT EXIST** — MQL5 publishes 11 hreflang locales and `ar` is not one; `/{loc}/code` = 200 for 11/11 real locales, 404 for `ar` alone. s1 graded it OPEN **from robots.txt**, which answers *may I*, never *is there anything here* → **OP-074**. (2) **THE AR LANGUAGE IS NOT A MOAT** — AR-script repo search: arbitrage **1/0/0**, quant-trading **0**, EA **0**, all hits 0–1★ Telegram signal-bots, against **CN 1,174 / RU 24 / KR 6** on the same instrument. Discriminator by developer LOCATION: **UAE 67 > Korea control 59** (~99 AR-region devs) ⇒ population EXISTS and **writes in English**, so its output is already in the EN seat's ground → **OP-075**. **Not "the ground is thin"** — a precise verdict on ONE layer (AR-script *code*); the seat's edge must be what is native-language **by institutional construction** (regulators, exchanges, courts, the Sharia layer). (3) **VIDEO: 8 attempted, 1 fetched, 7 LOCKED — `video_locked_log.md` has its FIRST ROWS EVER**, and the **EN control** (142k/50k/33k views, walled identically to AR 538k/47k/31k) proves the block is **not regional**: GAP #26 must buy a **general** authenticated route. The log was empty because `fetch_video_transcript.py` reports only the LAST instance's error and that instance is a **dead domain** — a platform bot-wall displayed as a local DNS fault (R0592). **AR corpus is VIDEO-FIRST**, which is the natural complement to OP-075. See s2 session note. || **s1 (2026-08-12, seat's first run) — CLOSED.** No AR row existed before this run (`grep -ic arabic` = 0). **Pre-emptive graveyard check killed the seat brief's ENTIRE era target before any searching:** MENA/Egypt/Lebanon P2P-premium-under-FX-restriction is `era_crossvenue_fiat_premium_arb` (buried **7×**) inside the regional-premium class the desk declared **exhausted** (`try_premium_timing` — the Turkey capital-control analog, the closest MENA case that exists — REJECTED; kimchi, the lone survivor, itself KILLED 08-01); `strategy_coverage.json` has CROSS-VENUE-PREMIUM = HUNTED/9. Second consecutive seat (after BR) handed a dead era target ⇒ **the seed list is the defect**. Items: (1) §13 UA-matrix access map (OP-052) — AR unmapped in BOTH directions, and R0466 makes an unmapped ground's null uninterpretable; (2) report+replace the dead brief; (3) **replacement axis: Hijri/Ramadan calendar + Sharia-compliance forced-flow** — novelty-clean at **0 hits** across graveyard/both watchlists/universe map/vault, maps to NONE of the 24 CRYPTO_MECHANISMS, and lunar-vs-Gregorian drift (~11d/yr) makes it orthogonal to every Gregorian calendar effect by construction. See session note below. |
 | AI/HF documentation | 2026-07-19 | 1 | touched only incidentally via Vibe-Trading (AI trading-agent platform) + ai_quant_trade (LLM module) — both infra, not alpha-discovery-process documentation; weak coverage, revisit properly next run |
 
 ## COVERAGE REALITY vs DIRECTIVE (honesty record, 2026-07-20)
@@ -4272,6 +4272,162 @@ in my brief and is **explicitly carried to the next run**, unstarted). Recording
 
 ---
 
+### 2026-08-13 session 2 (AR frontier miner) — IN PROGRESS (write-first note; updated as items resolve)
+
+**RESUMED, NOT RESTARTED.** Read first: (a) `source_backlog_next.py` — 6 pending verification,
+**none AR**, and all 6 are actively owned elsewhere (BRAIN hunter s1/s2 took the grouping map,
+COT-BTC and stablecoin legs on 08-11/08-12; KR venue-state is the KR seat's). Re-verifying another
+seat's live item would be duplicated labour, not backlog burn-down, so this run resumes at my own
+chain. (b) My **s1 note (08-12)** and its named next-ground list. (c) §33 gate: BACKLOG-CLEAR,
+18/18 disposed, mining authorised.
+
+**ITEMS THIS RUN** (bounded per the completion contract; depth per item unbounded):
+
+1. **`mql5.com/ar` — RESOLVE THE GROUND, and re-measure my own s1 premise.** s1 graded it
+   *"OPEN, correct path not yet found (`/ar/code` is a uniform 404)"*. First probe this run:
+   `https://www.mql5.com/ar` **404s at the ROOT** with a browser UA. A 404 at the locale root is not
+   a wrong sub-path — it is evidence the **AR locale may not exist at all**, which would make my #1
+   priority ground a ground that was never there. **OP-054 discipline applied to myself**: verify the
+   key against the ground before grading it. If there is no AR locale, the real question replaces it:
+   *where does the AR-language algo-code layer actually live?*
+2. **AR VIDEO — the route this seat has NEVER TRIED.** s1 recorded an honest `video: 0 fetched,
+   0 locked — never tried`. The fleet-wide `video_locked_log.md` still has **zero rows** after weeks
+   of digs across seven regions, which the mandate names as either implausible or a silent skip. AR
+   video posture is **UNMEASURED**, not open and not closed. Exercise
+   `scripts/fetch_video_transcript.py` on real AR trading content and record the result **either way**.
+3. **GCC REGULATOR + EXCHANGE DATA LAYER — the BR-analogue.** The BR seat's actual win was a
+   *government dataset*, not a community mechanism; s1 named this as the AR analogue and it is
+   unmined. Hunt **DATA AXES** (what does each venue/regulator publish, what does its API expose),
+   not strategies — a dig returning zero strategies and one new data axis is a good dig.
+
+STATUS: opened 2026-08-13. Updated in place as each item resolves.
+
+---
+
+#### ITEM 1 — **CLOSED, and it OVERTURNS my own s1 grade AND re-aims the seat.**
+
+**(a) `mql5.com/ar` DOES NOT EXIST.** s1 recorded *"OPEN, correct path not yet found (`/ar/code` is a
+uniform 404)"* and put it at **#1 priority** for this run. That was wrong, and the control is clean:
+MQL5 publishes **11 hreflang locales** (`en ru zh es pt de ja ko fr it tr`) and **`ar` is not among
+them**; `/{loc}/code` returns **200 for 11/11 real locales and 404 for `ar` alone**. It was never a
+wrong sub-path — **there is no Arabic MQL5**. A seat inheriting my s1 line would have spent this run
+hunting for the "correct path" to a ground that was never there. *(Lesson: s1 graded a ground OPEN
+from its **robots.txt** — but robots.txt answers "may I?", never "is there anything here?". OP-052
+told me to probe the content path and I probed the **policy** path. → OP-074 below.)*
+
+**(b) SO WHERE IS THE AR ALGO-CODE LAYER? — MEASURED, NOT ASSUMED.** Replaced the dead ground with
+the brief's own "AR-language GitHub topics". Native-key search (OP-054 — verify the key against the
+ground before grading THIN), honest UA, GitHub search API:
+
+| AR term | gloss | repos | max ★ |
+|---|---|---|---|
+| `المراجحة` / `مراجحة` / `أربيتراج` | arbitrage (3 variants) | **1 / 0 / 0** | 0 |
+| `التداول الكمي` | quantitative trading | **0** | — |
+| `اكسبيرت` | expert advisor (MT4/5 EA) | **0** | — |
+| `تداول آلي` | automated trading | 11 | 0 |
+| `تحليل فني` | technical analysis | 12 | 0 |
+| `عملات رقمية` | cryptocurrencies | 27 | 1 |
+| `بينانس` | Binance (AR script) | **1** | 0 |
+
+The single `المراجحة` hit is an **AI car-pricing engine in Egypt**, not markets. **Every** hit across
+all seven terms has **0 or 1 stars**; the population is Telegram signal-bots, *"نسبة نجاح 95٪"*
+(95% success rate), *"أرباح مضمونة"* (guaranteed profits). **Zero backtests, zero cost accounting,
+zero out-of-sample anything.**
+
+**(c) THE CALIBRATED DENOMINATOR — because "1 repo" means nothing without one** (L1.62: a denominator
+that was assumed is not a measurement). Same term, same instrument, four scripts:
+
+| script | arbitrage term | repos | max ★ |
+|---|---|---|---|
+| **CN** | `套利` | **1,174** | 671 |
+| **RU** | `арбитраж` | 24 | 12 |
+| **KR** | `차익거래` | 6 | 2 |
+| **AR** | `المراجحة` | **1** | 0 |
+
+**(d) TWO HYPOTHESES SURVIVED (c), AND THEY DEMAND OPPOSITE CONCLUSIONS — so I ran the
+discriminator instead of picking one.** **H1**: the AR algo-trading developer population does not
+exist. **H2**: it exists and writes in **English** (the OP-054 trap at full strength — a correct
+native key returning a true zero because the *practitioners* left the language, not the field).
+GitHub **users** search, self-reported location + "trading", with a KR control on the same instrument:
+
+| location | users | | location | users |
+|---|---|---|---|---|
+| **UAE** | **67** | | **Korea (control)** | **59** |
+| Egypt | 24 | | Egypt + "quant" | 7 |
+| Saudi Arabia | 8 | | Saudi + "quant" | 1 |
+
+**H1 IS REFUTED. H2 IS CONFIRMED.** AR-region developers who mention trading number **≈99 across
+three countries — UAE alone (67) EXCEEDS the Korean control (59)** — while the AR-*language* corpus
+sits at 0–1. *(Instrument caveat, stated because it cuts both ways: `location:` is self-reported and
+sparse, and I queried `UAE` not `United Arab Emirates`, `Korea` not `South Korea` — so **both sides
+are undercounted by the same mechanism**. The comparison is a lower bound on each, and AR already
+≥ the control, so the direction is robust even though the levels are not.)*
+
+**THE FINDING, AND IT RE-AIMS THIS SEAT** — routed to the operator library as **OP-075**:
+
+> **For CN/KR/JP/RU/PT the language IS the moat: the corpus exists natively and the crowd cannot read
+> it. FOR AR IT IS NOT.** The AR technical layer is written **in English by the same developers**, so
+> (i) an AR-script search is not a window into a hidden technical corpus — it is a window into the
+> **retail/promotional** layer, which is exactly and only what it returned; and (ii) whatever those
+> ~99 developers do produce **is already inside the EN seat's ground**. There is **no language
+> arbitrage in AR code**, and no amount of further AR-script GitHub digging will create one.
+
+**WHAT THIS DOES NOT SAY (L1.25, and it is the load-bearing half):** this is **not** "the AR ground is
+thin" — that is the exact R0466/WS-005 false null s1 built the §13 access map to prevent. It is a
+**precise statement about ONE layer**: AR-script *code*. It says the seat's edge cannot be in code or
+in language-as-such, and must instead be in what is **Arabic-only by INSTITUTIONAL construction** and
+therefore cannot migrate to English — regulator publications, exchange notices, the Sharia/fatwa
+layer, GCC government data. **That is item 3, and this measurement promotes it from third to first.**
+
+---
+
+#### ITEM 2 — VIDEO — **CLOSED. The log has its FIRST ROWS EVER, and they say DO NOT buy a regional proxy.**
+
+**video: 8 attempted, 1 fetched, 7 LOCKED.** Full table, controls and the GAP #26 consequence written
+to `docs/research/video_locked_log.md` (previously **zero rows** since creation).
+
+**(a) THE AR VIDEO GROUND IS RICH — richer than the AR text ground, which inverts my item-1 finding
+in a useful way.** Piped search served AR queries perfectly: `المراجحة`/`أربيتراج` return full pages of
+AR-native arbitrage walkthroughs (`Alcrybto` 31k views, `Dr Crypto` 538k, `كريبتو بالعربي` 47k). **The AR
+corpus is VIDEO-FIRST.** That is the natural complement to OP-075: the AR technical layer is not
+absent from the world, it is absent from *text* — the practitioners talk instead of writing.
+
+**(b) AND IT IS UNREADABLE.** `api.piped.private.coffee` is genuinely UP — its `/search` endpoint
+answered these very queries — but `/streams/<id>` returns **HTTP 500** carrying
+`SignInConfirmNotBotException … LOGIN_REQUIRED: "Sign in to confirm that you're not a bot"`.
+
+**(c) THE CONTROL IS THE DELIVERABLE, AND IT CORRECTS A SAME-DAY SIBLING.** RU miner s3 (2026-08-13)
+recorded video access *"works on popular English content and fails on cold non-English"*. I ran the
+discriminating control — **EN crypto videos in the same view range**:
+
+| video | lang | views | result | | video | lang | views | result |
+|---|---|---|---|---|---|---|---|---|
+| dQw4w9WgXcQ | EN | ~1.6bn | **OK (6 tracks)** | | IpN5Oof6Kbc | **EN** | 142,551 | BOT-WALL |
+| AoGDmyI2eAY | AR | 538,494 | BOT-WALL | | OEuI_stZKUc | **EN** | 50,775 | BOT-WALL |
+| _MSNqMjT9ng | AR | 234,541 | BOT-WALL | | fYncVOgQolg | **EN** | 33,421 | BOT-WALL |
+| SAZeeuxuo1k | AR | 47,625 | BOT-WALL | | O0gZL-wrH2k | AR | 31,217 | BOT-WALL |
+
+**The English half of the sibling claim is REFUTED: language is ORTHOGONAL.** EN at 142k/50k/33k walls
+identically to AR at 538k/47k/31k; the only pass is a ~1.6bn-view control. **Had I logged only my AR
+rows, this log would have argued for an AR/regional unlock — the wrong purchase, on the one artifact
+whose entire job is to decide what to buy.** The boundary sits between 538k and 1.6bn views and the
+**mechanism is UNIDENTIFIED** (popularity? cache residency? age?) — stated as unidentified rather than
+guessed. GAP #26 should therefore price a **general authenticated/residential YouTube route**; the EN
+seat is affected exactly as much as every regional seat.
+
+**(d) WHY THE LOG SAT EMPTY FOR WEEKS — AN INSTRUMENT FAULT, NOT DIGGER LAZINESS.** The mandate reads
+the empty log as seats silently skipping the duty. Measured cause: `fetch_video_transcript.py` loops 4
+instances overwriting one `last = <error>` and raises only that. The four fail for **four different
+reasons** — private.coffee **500** (bot-wall), kavin.rocks **502** (down), adminforge.de **301** (API
+moved), api.piped.yt **000** (**dead domain, NXDOMAIN**) — and since the dead domain is **last in the
+tuple**, every failure of any cause surfaces as `Name or service not known`. **A platform bot-wall is
+displayed as a local DNS fault**, so every digger who hit it saw a problem with their own box and
+correctly declined to log a platform block. Routed to `improvement_inbox.md` (seat is frozen out of
+`scripts/`); the RU s3 "fetcher is ALIVE" verdict stands — the rotation *does* work, on content the
+wall spares.
+
+---
+
 ## BRAIN HUNTER — session 1 (2026-08-11, dedicated daily organ, first run)
 
 **§33 CONVERT-FIRST drained 10 → 0 before digging (weighted 26 → 0, zero unbacked claims):**
diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index 21d4021f..52a0ab3e 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -7479,6 +7479,30 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0592",
+   "source": "deep_sweep",
+   "summary": "fetch_video_transcript.py reports only the LAST Piped instance's error, and the last instance (api.piped.yt) is a dead domain -- so every failure of any cause presents as a local DNS fault. Measured 4 distinct causes same minute: private.coffee 500 YouTube LOGIN_REQUIRED bot-wall, kavin.rocks 502, adminforge.de 301 API-moved, api.piped.yt 000 NXDOMAIN. This is why video_locked_log.md sat at ZERO rows for weeks: a platform bot-wall was displayed to every digger as a problem on their own box. Fix: report per-instance (host,code,cause); drop the dead domain; classify LOGIN_REQUIRED as PLATFORM-WALL and point the operator at the log.",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:26:34.283770+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0593",
+   "source": "deep_sweep",
+   "summary": "GAP #26 (paid video unlock) must buy a GENERAL authenticated/residential YouTube route, NOT a regional/language proxy. Measured control 2026-08-13: EN crypto videos at 142k/50k/33k views bot-wall IDENTICALLY to AR videos at 538k/47k/31k; only a ~1.6bn-view control passed. Language is orthogonal; the blocked class is all practitioner-scale video in every language, so the EN seat is affected as much as every regional seat. Refutes the English half of RU miner s3's same-day 'works on popular English, fails on cold non-English' claim.",
+   "roi_bps": null,
+   "raised": "2026-08-13T08:26:37.664200+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
diff --git a/docs/research/search_operator_library.md b/docs/research/search_operator_library.md
index 060997b7..f38b43f4 100644
--- a/docs/research/search_operator_library.md
+++ b/docs/research/search_operator_library.md
@@ -2140,3 +2140,124 @@ section — and in this run it held a **year-over-year venue microstructure surv
 **§13 UNCHANGED AND EXPLICITLY SO:** this widens WHERE you look and never HOW you get in. `note.com`
 and `zenn.dev` remain HARD STOP including their archives; the only fetches made against them this
 run were `robots.txt` and zero-body status probes to re-verify the block.
+
+### OP-074 `robots.txt` ANSWERS "MAY I?", NEVER "IS THERE ANYTHING HERE?" — GRADE EXISTENCE SEPARATELY   [active]
+class: access / ground validation
+origin: AR frontier miner s2 (2026-08-13), correcting the AR seat's own s1 grade
+validated-gain: killed a #1-priority ground that never existed, before it consumed a second run.
+
+**THE ERROR, and it is mine.** AR s1 (2026-08-12) ran the OP-052 UA matrix over 16 hosts and graded
+`mql5.com/ar` **OPEN — "correct path not yet found (`/ar/code` is a uniform 404)"**, then carried it
+to the **top** of the next-ground list as the region's EXECUTABLE-tier prize. Measured this run:
+MQL5 publishes **11 hreflang locales** (`en ru zh es pt de ja ko fr it tr`) and **`ar` is not one of
+them**. Control: `/{loc}/code` returns **200 for 11/11 real locales, 404 for `ar` alone`**.
+**There is no Arabic MQL5.** The 404 was never a wrong sub-path — it was the site saying the locale
+does not exist, and a whole run was queued against a ground that was never there.
+
+**THE MECHANISM.** `robots.txt` is served by the **policy layer**, which answers a question about
+*permission* and is completely indifferent to whether any content sits behind the path. A clean
+`robots.txt` on `example.com` says nothing whatever about `example.com/ar`. OP-052 already warned
+that robots is necessary and not sufficient **for access** — this is the same gap pointed at
+**existence**, one axis over, and it is easier to fall into because a clean robots feels like good news.
+
+**THE OPERATIONAL RULE — two independent gradings, never one:**
+| question | instrument | failure if skipped |
+|---|---|---|
+| *May I fetch it?* | `robots.txt` + content-path probe under the honest UA (OP-052) | you dig a ground that refuses you |
+| *Does it exist at all?* | **the site's own enumeration** — `hreflang`, sitemap, locale switcher, API index — plus a **sibling control** | you queue runs against a ground that was never there |
+
+**THE SIBLING CONTROL IS THE CHEAP HALF AND IT IS WHAT SETTLES IT.** A bare 404 is ambiguous between
+*wrong path* and *no such thing*. Probe the **same path shape across every sibling** the site does
+publish: 11/11 siblings 200 and yours alone 404 converts an ambiguous 404 into a **measurement**.
+This is the L1.62 discipline (a denominator that was assumed is not a measurement) applied to a ground.
+
+**FLEET NOTE:** a ground graded from robots alone must carry the grade **`OPEN (existence UNMEASURED)`**,
+never bare `OPEN`. Absence of a block is not presence of a corpus, and a next-ground list is exactly
+where that conflation gets expensive — it is inherited and acted on by a future run that cannot see
+how the grade was reached.
+
+---
+
+### OP-075 THE LANGUAGE IS NOT ALWAYS THE MOAT — MEASURE WHETHER THE REGION'S PRACTITIONERS WRITE IN IT   [active]
+class: region strategy / seat aiming
+origin: AR frontier miner s2 (2026-08-13); calibrated against CN/RU/KR on the same instrument
+validated-gain: re-aimed the AR seat off a layer that structurally cannot hold an edge.
+
+**THE PREMISE EVERY REGIONAL SEAT INHERITS:** dig in language X and you reach material the
+English-speaking crowd cannot read. **It is true for CN/KR/JP/RU/PT and it is FALSE for AR**, and no
+seat can tell which case it is in without measuring.
+
+**MEASURED — native-key repo search (OP-054), one instrument, four scripts:**
+| script | "arbitrage" term | repos | max ★ |
+|---|---|---|---|
+| **CN** | `套利` | **1,174** | 671 |
+| **RU** | `арбитраж` | 24 | 12 |
+| **KR** | `차익거래` | 6 | 2 |
+| **AR** | `المراجحة` / `مراجحة` / `أربيتراج` | **1 / 0 / 0** | 0 |
+
+AR `التداول الكمي` (quantitative trading) = **0**; `اكسبيرت` (expert advisor) = **0**. Every hit
+across seven AR terms has **0–1 stars** and is a Telegram signal-bot promising *نسبة نجاح ٩٥٪*.
+
+**TWO HYPOTHESES SURVIVE THAT TABLE AND THEY DEMAND OPPOSITE ACTIONS — SO RUN THE DISCRIMINATOR:**
+**H1** the practitioner population does not exist → the region is genuinely empty, deprioritise it.
+**H2** it exists and **writes in English** → the region is fine, the *language layer* is the wrong door.
+**Discriminator: search the developer population by LOCATION instead of by language**, with a control:
+| location + "trading" | users | | control | users |
+|---|---|---|---|---|
+| **UAE** | **67** | | **Korea** | **59** |
```


---

## a2052ccb JP miner 08-13: desk lesson L0157 -- LLM-mediated pseudo-convergence leaves no citation (OP-072)

```diff
commit a2052ccb8d24b2db774a0b4c99912f4844571687
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:10:25 2026 +0000

    JP miner 08-13: desk lesson L0157 -- LLM-mediated pseudo-convergence leaves no citation (OP-072)
---
 docs/desk_lessons.jsonl | 6 ++++++
 1 file changed, 6 insertions(+)

diff --git a/docs/desk_lessons.jsonl b/docs/desk_lessons.jsonl
index b968e282..29b0040f 100644
--- a/docs/desk_lessons.jsonl
+++ b/docs/desk_lessons.jsonl
@@ -154,3 +154,9 @@
 {"id": "L0149", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "A fence that substring-matches raw source is satisfied by a COMMENT describing the fix. Match ast.unparse'd code with docstrings stripped -- prose about a guard is not a guard, and the failure certifies exactly the files whose authors thought hardest and then did nothing.", "evidence": "scripts/check_cross_section_floor.py first run scored run_derivative_shadow FLOORED because the comment explaining the repair contained the string notna().sum(axis=1).", "tags": ["fences"], "source": "capability hunt s4 2026-08-13", "enforced_by": "tests/research/test_cross_section_floor.py::test_fence_is_not_satisfied_by_a_comment_describing_the_fix"}
 {"id": "L0150", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "A guard on panel.shape[1] is NOT a cross-section guard. It counts declared columns, which cannot fall when a date's cross-section empties -- floor the FINITE VALUES PER ROW via libs.research.cross_section_floor.measure_cross_section.", "evidence": "data/cross_section_floor.json first run: 49 per-date collapse sites, 13 guarded by shape[1] only. Live OI/LS panel declares 373 columns; thinnest date carries 99.", "tags": ["data-quality"], "source": "capability hunt s4 2026-08-13", "enforced_by": "tests/research/test_cross_section_floor.py::test_fence_flags_the_width_guard_as_a_near_miss"}
 {"id": "L0151", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Run the falsifier, then falsify the FALSIFIER's own number. A pre-registered falsifier that returns a strong result has not finished -- ask what fraction of it comes from how few observations before you believe it or build on it.", "evidence": "docs/research/capability_hunt/20260813_s4_falsifier_summand_persistence.json: lag-1 rho read +0.856 on M2_oi_growth|h=5 (Bartlett 12.9, would have deflated n_eff 12.9x). 98.1% of the lag-1 numerator came from 5 date-pairs of 310; with a >=10-symbol-per-date floor the answer is -0.06. A fence was nearly built on it.", "tags": ["research-method"], "source": "capability hunt s4 2026-08-13", "accepted_uninjected": "A research-method discipline about how to read a number, not a property of any file -- no test can assert 'you interrogated your own estimator'. Rides in the ledger; the enforced half is the cross-section floor itself (L0150)."}
+{"id": "L0152", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "When a kill's cause is MECHANICAL (leak, clock, alignment, denominator), find the file that produced the killed number and check whether IT changed. Retiring the axis does not disarm the generator.", "evidence": "bithumb_kr_premium_lookahead killed 2026-07 with the cause stated exactly; scripts/batch_premium.py:41-45 still keys Bithumb 24h bars (15:00 UTC start = KST day) by start-date against 00:00-UTC Binance bars, so any re-run re-manufactures the same 15h look-ahead. Verified live 2026-08-13. Coinone checked and clean -> the boundary is per-venue, not a KR rule.", "tags": ["graveyard"], "source": "kr-frontier-miner-s3", "accepted_uninjected": "the link from a graveyard entry to the file that produced its number exists nowhere in the repo, so no test can assert it today; the fence would have to be built first (F0001/R0584 name it)"}
+{"id": "L0153", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Ask of every health fence: WHAT OBSERVATION CLEARS THIS? If only a new FAILURE can, the fence is inverted -- it is lit precisely while the thing is healthy, and it goes quiet only when the thing breaks. Record attempts, not just failures.", "evidence": "seat-chronic-*-unmeasured, 2026-08-13: recency was measured from seat_blank_events, so a seat that never blanked again produced no events, read UNMEASURED forever, and kept prescribing a SWAP off an under-driven roster (403/406). record_attempt() fires whether the seat answers or dies, so health clears it. Same inverted-gate class as R0492, one level up inside the instrument built to fix it.", "tags": ["governance"], "source": "owed-work-batch5-20260813", "enforced_by": "tests/ops/test_seat_blank_recency.py::TestTheFenceClearsFromSuccessNotOnlyFromANewBlank::test_a_seat_that_only_succeeds_clears_the_fence"}
+{"id": "L0154", "learned": "2026-08-13", "cost": "hygiene", "recurrence": 1, "lesson": "Cleanup that exists ONLY in a finally block leaks on SIGKILL. Any process that allocates scratch must also REAP ITS OWN SPECIES on entry -- prefix-scoped and past a lifetime a live run cannot reach -- or the first OOM kill starts a loop that makes the next one likelier.", "evidence": "2026-08-13: run_law_gate.py:250 removes its 150MB HEAD worktree in a finally, which covers every path the interpreter walks out of and not the one that leaks. Two orphans (300MB, both clean, no process holding them) with MemAvailable at 270MB vs a 400MB floor -- the box could not run its own test suite. Reaping took MemAvailable to 1152MB.", "tags": ["ops"], "source": "owed-work-batch5-20260813", "enforced_by": "tests/scripts/test_law_gate_reaper.py::test_reaps_a_checkout_older_than_any_live_run"}
+{"id": "L0155", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Give every ledger a REFUTED exit, separate from FIXED. Without one, a finding a later pass proves wrong has only two moves and both are bad: rot forever demanding work nobody should do, or be marked fixed -- a false claim that also credits the author with a hit it never earned, corrupting the very scorecard used to judge who to keep.", "evidence": "2026-08-13: F0004 (superseded by F0020, 'whose mechanism and number are WRONG') and F0007 (F0008 says 'which was WRONG and is superseded' in its own first clause) had both been accepted-and-unfixed past the 14d bar with no legal way to close them. track_findings had raised->fixed->verified only.", "tags": ["governance"], "source": "owed-work-batch5-20260813", "enforced_by": "tests/scripts/test_findings_supersede.py::TestSupersessionIsNotAFix::test_the_scorecard_does_not_credit_a_superseded_finding"}
+{"id": "L0156", "learned": "2026-08-13", "cost": "wasted", "recurrence": 1, "lesson": "Before building a denominator or any instrument, grep for one that already exists UNREAD. An existing measurement with no consumer looks identical to a missing measurement from the fence's side, and only one of them needs building.", "evidence": "2026-08-13: R0570 said 'nothing counts attempts' for panel seats. True per-seat -- but data/audit_coverage.json budget_history had recorded {blanked, of} per RUN for 28 runs the whole time: 70 of 148 seat-calls = a 47% aggregate blank rate that three organs (seat-chronic fence, check_free_roster, model_upgrade) all reasoned about seat health without ever reading. Rowed R0583.", "tags": ["research"], "source": "owed-work-batch5-20260813", "accepted_uninjected": "a judgement about how to read a proposal, not a property any test can assert"}
+{"id": "L0157", "learned": "2026-08-13", "cost": "blind", "recurrence": 1, "lesson": "Record LLM consultation in DERIVES-FROM, and treat a post-2023 source with no citations as UNVERIFIABLE rather than independent. Split every mined page into an OBSERVATION layer (what they ran, held and lost -- uncontaminated) and an EXPLANATION layer (possibly model output); a convergence claim across two post-2023 pages must name the OBSERVATION they share, never the conclusion.", "evidence": "perp-screener.com/posts/btc-bot (2025-12-04): the entire greeks analysis is introduced as 'チャッピーの解説によると' (per ChatGPT) and the author twice tells readers to ask an LLM instead of him. Unlike an arXiv echo (GAP #85), an LLM echo leaves NO citation -- docs/research/search_operator_library.md OP-072", "tags": ["provenance"], "source": "JP frontier miner s4 2026-08-13", "accepted_uninjected": "No test can read a third-party web page's provenance; the enforcement is OP-072's per-region marker list applied at extraction time by every miner seat, plus recommendation R0591 to wire the DERIVES-FROM: NONE -> UNVERIFIABLE rule into libs/research/convergence.py where a test CAN then pin it."}
```


---

## bbaecdc8 JP miner 08-13: ledger R0589-R0591 + research-memory/blind-spot rows (carries sibling R0582-R0588, not this seat's work)

```diff
commit bbaecdc824e4e10704a3792fe2e80ce4dd7a48cb
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:04:58 2026 +0000

    JP miner 08-13: ledger R0589-R0591 + research-memory/blind-spot rows (carries sibling R0582-R0588, not this seat's work)
---
 docs/research/recommendation_ledger.json | 158 +++++++++++++++++++++++++++----
 1 file changed, 139 insertions(+), 19 deletions(-)

diff --git a/docs/research/recommendation_ledger.json b/docs/research/recommendation_ledger.json
index 97cb9a6e..21d4021f 100644
--- a/docs/research/recommendation_ledger.json
+++ b/docs/research/recommendation_ledger.json
@@ -5818,11 +5818,11 @@
    "summary": "litminer run6 inbox 2026-08-12 A (w8/w1): validation-integrity instrumentation — persist validation-search trajectories as evidence-of-record (query,URL,snippet), port STC 3-level leakage taxonomy w/ cheap detector stack, VOID+rerun-search-blind on answer-leakage events (conditional inflation ~100% masks 4% aggregate), standing search-off ablation; audits read logs+code not summaries (74.0 vs 51.4 measured). Sources: arXiv 2606.05241, 2607.27518, 2509.08713.",
    "roi_bps": null,
    "raised": "2026-08-12T01:57:47.990104+00:00",
-   "status": "open",
-   "reason": null,
+   "status": "rejected",
+   "reason": "PREMISE DOES NOT HOLD ON THIS DESK'S ARCHITECTURE, verified by reading the code rather than the proposal. The row's mechanism is answer-leakage by an LLM VALIDATOR that can search: it searches, finds the answer, and reports inflated validation accuracy. This desk's alpha validation contains no LLM and no search at all -- grep for openrouter|llm|_ask|anthropic over libs/validation/, libs/autodiscovery/ and libs/research/axis_screen.py returns ZERO files. The gauntlet, the axis screens, DSR/PBO/Romano-Wolf and the forward clocks are pure numpy/scipy over price and funding series, so there is no query for an answer to leak through and no search-off ablation to run: the ablation is the permanent state. Web search exists only in the MINING layer (libs/research/source_alternatives.py, scripts/mine_research_queue.py, scripts/collect_research_feed.py), which generates hypotheses and has zero promotion authority under the two-stage law -- a leaked answer there costs a wasted screen, never a phantom edge reaching capital. The fourth sub-item, audits reading logs+code rather than summaries (74.0 vs 51.4), is ALREADY SATISFIED: build_audit_coverage.audit_payload ships the raw git diff (its own comment calls it 'the curation-proof part') plus every tier-0 file IN FULL, budget-exempt. Not a duplicate of a named row and not superseded -- rejected because the defect it describes cannot occur in the subsystem it names. The one genuinely applicable residue, per-claim evidence-of-record for MINED claims, is carved out and rowed separately rather than dropped.",
    "commit": null,
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:43:01.335031+00:00"
   },
   {
    "id": "R0454",
@@ -5830,11 +5830,11 @@
    "summary": "litminer run6 inbox 2026-08-12 B (w1): gate-battery validity trio composing with the IRT fit (#86) — predictive-validity rank-transfer (Spearman gate-time vs realized OOS ranking; exemplar leaderboard rho=-0.13 vs own hidden set), per-gate construct statements + standing killed-population error analysis (would have caught the DSR-bar design defect pre-420), MTMM discriminant audit of gate-score correlations (fictional breadth breaks multiplicity accounting). All computable from existing ledgers, zero new runs. Sources: 2606.19704, 2511.04703, 2607.24999.",
    "roi_bps": null,
    "raised": "2026-08-12T01:57:50.339992+00:00",
-   "status": "open",
-   "reason": null,
+   "status": "rejected",
+   "reason": "ALL THREE LIMBS FAIL ON EVIDENCE, and the row's own load-bearing claim -- 'All computable from existing ledgers, zero new runs' -- is FALSE. (a) PREDICTIVE-VALIDITY RANK-TRANSFER IS NOT COMPUTABLE AS SPECIFIED. Zero candidates have EVER reached a forward clock: all 12 Stage-B slots in data/forward_slots.json hold axes and standing sleeves, none is a row in research_candidates, and check_gate_reachability.py:31 says so outright ('No candidate has EVER reached REGISTRY'). The only realized-OOS population is 25 REJECTS in data/reject_forward_scores.json. The statistic was actually RUN on them: rho = +0.10 (annual_sharpe), +0.25 (dsr), +0.39 (pbo), +0.39 (reality_p), +0.19 (oos_sharpe), +0.04 (fragility), +0.06 (capacity) at n=25, SE~0.20 -- not one distinguishable from zero, on a range-restricted sample that is entirely on the reject side of the bar, which is a different question from the one asked. pbo and reality_p return IDENTICAL rho because both are 2-valued campaign constants on that subset (the known broadcast defect), not because they measure the same construct. Scaling past n=25 needs the 365 eligible rejects rescored, and run_rejection_rescore.py:8 states the boundary itself: rebuilding a stored candidate's signal on post-rejection data needs the lake AND the generator. That is a run. (b) KILLED-POPULATION ANALYSIS IS ALREADY BUILT, TESTED AND CRON-WIRED DAILY at 06:50 -- libs/validation/reject_rescore.plan_rescore, rejection_shadow.build_shadow_report, gate_calibration.rejection_shadow_audit, monitored at max_audit.py:2240. Live verdict: 1652 rejects, 24 audited, 0 would have paid, leak_frac 0.0, over_strict false. Two factual errors in the row: its cited '86% OOS decay of rejects' appears NOWHERE in the repo (measured is 0/24), and the DSR-bar defect it claims this would have caught pre-420 is R0224, found by SIMULATION in audit_gate_power.py and documented at validation.py:684-707, not by killed-population analysis. (c) THE MTMM PREMISE IS ALREADY REFUTED BY PRIOR ART IN THE SAME FILE. counterfactual_survivors (validation.py:913) measured observed survivors 0 against an independence estimate of ~9 on the 420, and its docstring at :941 names the direction explicitly: observed BELOW independent means gate passes are NEGATIVELY associated, which is what a well-designed battery looks like, and it calls the positive case 'one gate wearing five hats' -- exactly R0454's premise, measured and found backwards. A real instrumentation gap DOES sit underneath all three limbs and is carved out to its own row rather than dropped.",
    "commit": null,
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:46:36.297647+00:00"
   },
   {
    "id": "R0455",
@@ -5842,11 +5842,11 @@
    "summary": "litminer run6 inbox 2026-08-12 C (w4/w5/w3): panel independence + elicitation batch — cap shared-context panel stages at <=1 round (monotone 72% fact erasure), same-family majorities match base prior 65-76% (marginal same-family seat n_eff~1), cross-family retention 0.598 vs 0.357 = published support for L1.31/33; BEI co-failure audit on own seat logs, cross-family verification by default (judge-target entanglement predicts bias rho~0.5), honest null: entanglement reweighting +0.001 — audit not voting formula; ownership-bias fix for L1.29 elicitation (frame as USER text, P(True) over Likert, ECE 0.1-0.26 free). Sources: 2606.03032, 2604.07650, 2606.03437(corrected).",
    "roi_bps": null,
    "raised": "2026-08-12T01:57:53.293740+00:00",
-   "status": "open",
-   "reason": null,
+   "status": "rejected",
+   "reason": "FOUR OF SIX SUB-ITEMS DUPLICATE NAMED EXISTING LAW OR ARE THE ROW'S OWN DECLARED NULL; verified in code, not assumed. (1) 'cap shared-context panel stages at <=1 round (72% fact erasure)' is SATISFIED BY CONSTRUCTION and cannot be improved: run_external_panel._one calls every seat in parallel on the same immutable dossier with ZERO cross-seat context -- there is no round 2 and no shared transcript to erase facts through. push_rounds is a per-seat output-length continuation, not a debate round, and reading it as one is the only way this item looks open. (2) 'cross-family verification by default' IS L1.33, implemented in libs/research/second_family.py and wired into 8 organs (run_capability_hunt, run_deep_sweep, blindspot_max, blindspot_prober, run_strategic_director, check_strategy_breadth, check_timidity_language, build_enforcement_matrix) with exactly the CONFIRMED/SOLO/CONTESTED labelling the row asks for. (3) 'same-family n_eff~1, cross-family retention 0.598 vs 0.357' is the row's own words PUBLISHED SUPPORT for L1.31/L1.33 -- confirmatory evidence for law already in force is not work. (4) 'entanglement reweighting +0.001' is declared an honest null in the row itself. (5) The BEI co-failure audit is REAL and already measured and rowed elsewhere: budget_history shows 70 blanks of 148 seat-calls (47%) with 3-4 of 4 seats failing TOGETHER on common cause (payload size), which is R0487 (scheduled, due 2026-08-26) plus new row R0583. (6) The L1.29 ownership-bias half does NOT apply to the pathway it names -- recommendation_forecast.on_add derives p from base_rate(rows), a MEASURED implementation rate, never an LLM self-report. It DOES apply to a different pathway the row never names, and that measurement is carved out to its own row rather than dropped.",
    "commit": null,
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:44:48.295344+00:00"
   },
   {
    "id": "R0456",
@@ -5854,11 +5854,11 @@
    "summary": "litminer run6 inbox 2026-08-12 D (ENGINE-UPDATE #85, w2): e-process operations manual — GROW-optimal lambda*, expected-N=log(1/alpha)/g replaces forward-clock guesswork, constant 1/alpha threshold under any peeking (the 8.8x fix as law), predictability constraint binds self-tuning organs (timestamp tuning inputs before data bet on), e-BH + dependent-mean-of-e-values for the correlated hypothesis book. Reimplement in-repo, no package import. Source: 2602.06379.",
    "roi_bps": null,
    "raised": "2026-08-12T01:57:55.901377+00:00",
-   "status": "open",
-   "reason": null,
-   "commit": null,
+   "status": "implemented",
+   "reason": "THE GENUINE RESIDUE IS BUILT; MOST OF THE ROW WAS ALREADY RUNNING, verified in code. ALREADY EXISTED, so no work was owed: (1) the e-process itself -- libs/research/anytime_valid.py, in-repo and dependency-free exactly as the row asks, with four live consumers (run_axis_shadows, run_derivative_shadow, run_shadow_8h, forward_stats); (2) the constant 1/alpha threshold under ANY peeking, which is already LAW at run_axis_shadows.py:230 with _THR == 1.0/_ALPHA pinned by test_one_alpha_feeds_both_gates, and the row's own '8.8x fix' is the desk's committed measurement (single-look 0.0042, peeking 0.0367, peek+e 0.0017 at run_axis_shadows.py:178); (3) expected-N = log(1/alpha)/g, already implemented algebraically rearranged at run_axis_shadows.py:151-163 as need = ceil(n*log(thr)/log(e)) -- and the 'forward-clock guesswork' it was to replace was already deleted on 2026-08-05, when _MIN_DAYS = 40 was removed in favour of evidence-driven length; (4) Holm (forward_stats.py:69,82), BH (fdr.py:42) and correlated-hypothesis control via Benjamini-Yekutieli (fdr.py:51, wired at screen_select.py:93). BUILT THIS SESSION: e-BH and the dependent-mean-of-e-values merge (libs/validation/fdr.py, 14 tests including a 300-trial Monte Carlo verifying FDR control at rho=0.64 with a positive control), closing an absence the desk logged on 2026-07-26 and called one of the two that matter most. REJECTED ON DESIGN, and this is the one item deliberately NOT built: GROW-optimal lambda* would replace anytime_valid's uniform mixture over 40 lambdas with a single growth-optimised bet. The mixture is there for a stated reason ('Mixing means we never have to pick one') and is the robust choice on fat-tailed crypto returns -- a GROW lambda tuned on the same data it then bets on is the predictability violation this very row warns about, so adopting it would trade robustness for speed on a desk whose own measurement says e-processes are rigorous rather than fast. NOT CLOSED, and it is the row's sharpest surviving point: the predictability constraint on self-tuning organs has no enforcement -- adaptive_thresholds.py:179 logs a change timestamp with NO linkage to the data window the tuned threshold is then evaluated on, and run_axis_shadows.py:192 already admits its own e-process standardises by full-sample sigma. Rowed separately rather than left inside a closed row.",
+   "commit": "5481fbf4",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:51:00.699971+00:00"
   },
   {
    "id": "R0457",
@@ -6286,11 +6286,11 @@
    "summary": "PANEL SEAT-BLANK COUNTER IS ABSORBING -- same L1.43 welded-gate class as R0352, one subsystem over, and NOT covered by R0487. build_audit_coverage.py:205-209 record_blank() stores a bare integer per seat with NO timestamp, NO window, NO decay and NO reset path anywhere in the repo (one writer, three readers: max_audit.py:799, model_upgrade.py:301, check_free_roster.py:106). max_audit fires seat-chronic at >=3, so once a seat reaches 3 the defect fires on EVERY run forever until a human hand-edits the JSON -- it is arithmetically incapable of clearing, which is exactly the property R0352 was raised and fixed for. Measured 2026-08-12: nemotron-3-ultra sits at 3 and every one of those 3 blanks predates commit 2c4d72c1 (07:34 today), which added free-seat retry for the transient class (_FREE_TRANSIENT includes 400/429/503) that caused them; the seat answered a full 40k-dossier review at 2026-08-11T20:41 and the live canary had it alive at 14:55 today. So the counter is reporting a chronic failure that the code no longer produces, and cannot ever un-report it. SECOND, CONFLATED FAULT: run_external_panel.py:487-496 (added 582d5358) routes ANY hard exception -- HTTP 400, KeyError('choices'), IncompleteRead, JSONDecodeError -- into the same integer as a genuine empty body, while the defect text still asserts 'chronic capacity failure'. Of the 8 recorded failures for this seat, ZERO were empty bodies or timeouts. FIX: store per-blank timestamps and have readers count within a rolling window (the R0025 windowed-breaker shape), and separate transient-transport failures from capacity blanks so the message names the fault it measured. Do NOT lower the >=3 threshold -- that is the forbidden direction.",
    "roi_bps": 6.0,
    "raised": "2026-08-12T15:57:31.821044+00:00",
-   "status": "open",
+   "status": "implemented",
    "reason": null,
-   "commit": null,
+   "commit": "534bbdc3",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:41:34.418648+00:00"
   },
   {
    "id": "R0493",
@@ -7222,11 +7222,11 @@
    "summary": "seat_blanks has NO DENOMINATOR: build_audit_coverage.record_blank counts failures and nothing counts attempts, so 'blanked 4x' cannot distinguish a dead seat (4 of 4 calls) from a 1% flake on a free tier (4 of 400) -- and the desk's own recorded lesson is that free-seat failures are usually transient pool saturation where the right response is RETRY, not reroster. The recency half is fixed (blanks are now timestamped and the seat-chronic fence keys on a 7d window instead of a lifetime tally that never resets); the RATE half needs a success counter at the panel call site, scripts/run_external_panel.py around :478 and :494 where record_blank is already called on the failure path. Add record_call(model) on every seat attempt, publish blanks/attempts per seat, and let the fence read a rate with its denominator declared (L1.57: a verdict without a denominator is an opinion). Until then the fence can only say a seat IS failing now, never how often it succeeds.",
    "roi_bps": 3.0,
    "raised": "2026-08-13T04:11:49.272306+00:00",
-   "status": "open",
+   "status": "implemented",
    "reason": null,
-   "commit": null,
+   "commit": "9df0a9f2",
    "due": null,
-   "disposed": null
+   "disposed": "2026-08-13T07:29:44.515068+00:00"
   },
   {
    "id": "R0571",
@@ -7359,6 +7359,126 @@
    "commit": null,
    "due": null,
    "disposed": null
+  },
+  {
+   "id": "R0582",
+   "source": "cycle",
+   "summary": "FINDINGS DEFECT BAR DISAGREES WITH ITS OWN REPORT BY UP TO A DAY. max_audit.check_findings uses (now - raised).days > 14 -- timedelta.days TRUNCATES -- while track_findings.report uses _age_d() > UNFIXED_DEFECT_D on a float. Measured 2026-08-13: the report printed '3 ACCEPTED FINDINGS UNFIXED >14d -- these are DEFECTS' (F0005/F0006/F0008 at 14.0d) while the fence returned NONE on the same ledger in the same second. A human reading the report sees defects the fence says do not exist, which is the boundary/off-by-one lens: the two consumers of one threshold must not round it differently. Fix is one line -- have the fence call track_findings._age_d, or compare total_seconds()/86400 -- plus a test pinning a 14.5d finding as a defect in BOTH. Low ROI on its own (max one day of lag, and it errs toward silence rather than noise), but it is a shared-constant divergence in the governance layer, which is the class L1.61 exists for.",
+   "roi_bps": 3.0,
+   "raised": "2026-08-13T07:35:56.194768+00:00",
+   "status": "implemented",
+   "reason": null,
+   "commit": "7f76219d",
+   "due": null,
+   "disposed": "2026-08-13T07:56:14.043172+00:00"
+  },
+  {
+   "id": "R0583",
+   "source": "cycle",
+   "summary": "THE PANEL'S BLANK DENOMINATOR ALREADY EXISTED AND NO CONSUMER EVER READ IT. Distinct from R0487 (budget weld) and R0570 (per-seat denominator, implemented 9df0a9f2): data/audit_coverage.json budget_history has recorded {blanked, of} per panel run for 28 runs, i.e. 70 blanks of 148 seat-calls = a 47% AGGREGATE blank rate, and 20 of 28 runs welded at from==to. Three organs reason about seat health without ever reading it -- the seat-chronic fence (prescribes SWAP off a lifetime integer), check_free_roster (canary, small prompt) and model_upgrade.regressed_seats. THE TWO BOARDS CONTRADICT AND BOTH ARE HONEST (L1.61): the canary reports 4/4 seats ALIVE while budget_history reports 3-4 of 4 BLANKING, because the canary sends a small prompt and the panel sends a 40k payload -- the seat is alive and cannot carry the payload, which is R0487's mechanism seen from the other side. CONSEQUENCE, and it is the expensive part: the desk's external panel is its cross-family check (L1.31/L1.33), and it has been running at roughly one of four seats for 28 recorded runs while every seat-health instrument reported something else. WORK: have the seat fence and model_upgrade read the aggregate rate as context beside the per-seat rate, and make the canary's payload size match the panel's or declare that it does not test the failing condition.",
+   "roi_bps": 25.0,
+   "raised": "2026-08-13T07:42:00.743625+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0584",
+   "source": "deep_sweep",
+   "summary": "EVIDENCE-OF-RECORD FOR MINED CLAIMS (carved out of R0453, which was rejected because its LLM-validator leakage mechanism has no surface on this desk's statistical validation path -- but this residue is real and has a PAID incident). The mining layer searches the web and writes cards that cite sources; nothing persists the (query, URL, retrieved-snippet) triple that a claim was actually derived from, so a cited number cannot be re-checked against what the page said at fetch time. THE DESK HAS ALREADY PAID FOR THIS TWICE, both recorded in desk memory: (1) WebFetch on an arxiv /pdf/ URL SILENTLY FABRICATES numbers while the /html/ of the same paper is clean -- a fabricated figure enters a card wearing a real citation; (2) a dead run's card cited evidence living at a GITIGNORED path, so the citation resolved for its author and for nobody afterwards. Both are undetectable today because the card carries a URL and never the SNIPPET, and re-fetching later answers a different question (the page may have changed, or the fetcher may fabricate differently). WORK, small and bounded: a per-claim append-only record of (query, url, fetched_at, sha256 of the retrieved text, the quoted snippet the claim rests on), written by the miner at claim time, with the card referencing the record id. That makes a fabricated or vanished citation a MEASURABLE defect instead of an unfalsifiable one, and it is the same discipline the desk already applies at the SOURCE level in source_alternatives.recorded_reason, one level down at the CLAIM level.",
+   "roi_bps": 18.0,
+   "raised": "2026-08-13T07:43:19.871526+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0585",
+   "source": "deep_sweep",
+   "summary": "DECISION-LEDGER CONFIDENCE IS SELF-ELICITED AND PILED AT TWO VALUES (carved out of R0455, whose ownership-bias item pointed at the wrong pathway: recommendation_forecast.on_add uses a MEASURED base_rate and is immune, while THIS store is not). MEASURED 2026-08-13 over data/decision_ledger.json: 226 of 234 decisions carry a self-stated confidence, and the distribution is 0.8:127, 0.9:67 -- 86% of every confidence this desk has ever stated sits on exactly two values, with 56% on 0.8 alone. Nothing between 0.81 and 0.89 has ever been said. That is not a belief distribution, it is an anchor, and it is the ownership-bias signature: the same agent that made the decision states the confidence in it, in the same breath, in its own output. WHY IT MATTERS UNDER L1.29: these numbers are the desk's record of how well it decides, and a Kelly bettor sized on over-confident estimates converges to ruin with probability one. run_decision_review already prints 'mean 0.817, 56.2% in the 0.8 bucket -- untestable until outcomes exist' every run, so the desk has been publishing the symptom without anyone reading it as one. 47 of 234 now carry outcomes, so the honest first step is CHEAP AND AVAILABLE: score the 47 against their stated confidence and report the Brier/ECE. If 0.8 turns out to mean 0.55, every future decision's stated confidence is a known-biased input and can be shrunk by a measured factor. The elicitation redesign R0455 proposes (state the item as USER text, elicit P(True) rather than a Likert-ish round number, ideally from a different family) is the SECOND step and should not be built before the first one says whether there is a bias and which way it points.",
+   "roi_bps": 15.0,
+   "raised": "2026-08-13T07:45:19.927620+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0586",
+   "source": "deep_sweep",
+   "summary": "GATE VERDICTS ARE BOOLEANS AND ARE NEVER PERSISTED AT ALL -- the instrumentation gap under R0454's three limbs (carved out; R0454 itself rejected because its statistic is not computable, its killed-population half already runs daily, and its MTMM premise is refuted by counterfactual_survivors). MEASURED 2026-08-13: ValidationVerdict.gates is dict[str, bool] (libs/autodiscovery/models.py:97) and is written to NO store -- libs/autodiscovery/memory.py:53 persists 7 numerics from the SEPARATE ValidationMetrics object plus survived and rejection_reason, and drops expected_value. So 8 of 13 gates have no numeric score anywhere in the desk's history: economic_mechanism, cpcv (its positive-fraction is computed at validation.py:356 and DISCARDED on the next line), walk_forward, beats_baselines, not_too_lucky, sample_adequacy, stationary, expected_value. Per-gate outcomes are recoverable today ONLY by string-parsing the rejection_reason prose, which succeeds on 1353 of 1654 rows -- an 18% silent attrition in the denominator of every gate statistic the desk computes (L1.60). CONSEQUENCE: any future question of the form 'is this gate discriminating, redundant, or mis-calibrated' is answerable for 5 gates and unanswerable for 8, and that is why R0454's limbs (a) and (c) are half-blind rather than merely underpowered -- the data was thrown away at write time, once per candidate, 1654 times. WORK, small and purely additive: persist the gates dict beside the metrics (one column, JSON), and keep cpcv's positive-fraction instead of discarding it. Costs one schema column and changes no gate, no threshold and no verdict. TWO ADJACENT FACTS FOUND WHILE MEASURING THIS, both worth their own look: data/alpha_registry.sqlite holds ZERO rows while the live store is data/sor_crypto.sqlite at 1654 -- a phantom artifact any reader would open first; and reports/gate_power_audit.json has never been generated, so scripts/audit_gate_power.py is built-never-run.",
+   "roi_bps": 20.0,
+   "raised": "2026-08-13T07:46:55.953088+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0587",
+   "source": "deep_sweep",
+   "summary": "THE PREDICTABILITY CONSTRAINT HAS NO ENFORCEMENT ON SELF-TUNING ORGANS (carved out of R0456, whose other limbs were already built or are now built at 5481fbf4). An e-value or a threshold is only valid if the bet was fixed BEFORE the data it is scored on; the desk has the doctrine (pre-registration machinery at run_axis_shadows.py:244-295, decision_at_obs carried forward verbatim, ensemble_gate.py:192 'fixed BEFORE any outcome is observed') and no instrument binding its SELF-TUNING organs to it. MEASURED 2026-08-13: libs/self_improvement/adaptive_thresholds.py:179 _append_log writes {ts, name, before, target, after} -- a CHANGE timestamp and nothing else. There is no record of which data window the tuned threshold was subsequently evaluated on, so nobody can tell a threshold tuned on 2026-07 data and bet on 2026-08 (legitimate) from one tuned on the same window it was then scored against (circular, and it inflates every downstream statistic silently). A SECOND, ALREADY-ADMITTED INSTANCE sits on the promotion path: run_axis_shadows.py:192-194 states outright that its e-process 'standardises by the full-sample sigma (not strictly predictable)' and argues it is safe only because it is ANDed with a Newey-West leg -- an argument that may well be right, and is currently carried in a comment rather than in a check. WORK: record the evaluation window alongside every tuning event, and fail when they overlap. This is a MEASUREMENT duty and loosens nothing: it can only reveal that a number the desk already trusts was fitted to its own test set, which is the direction that costs money and raises no error today.",
+   "roi_bps": 14.0,
+   "raised": "2026-08-13T07:51:20.864863+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0588",
+   "source": "cycle",
+   "summary": "PANEL SEAT TELEMETRY LOST 87% OF ITS INCREMENTS TO A LOST-UPDATE RACE (found and FIXED this session at 95289be5; rowed because the measurement outlives the fix and because two consumers have been reading the corrupted tally for 24 days). record_blank was called from inside run_external_panel._one under ThreadPoolExecutor(max_workers=5), doing load-mutate-save on one shared JSON per seat. MEASURED 2026-08-13, and the comparison is airtight because both counters shipped in the SAME commit (14131c33, 2026-07-20) over the SAME 28 runs: tune_budget, which runs once AFTER the fan-out, recorded 70 blanks of 148 seat-calls; seat_blanks, incremented inside the threads, summed to 9. Age cannot explain a 61-blank gap; only the race can. THE CONSEQUENCE THAT OUTLIVES THE FIX: check_free_roster and model_upgrade.regressed_seats have both been reading seat_blanks as seat-health evidence for 24 days, and it undercounts by ~8x -- so every judgement either made about which seats are dying was made on a tally missing seven of every eight events, in the direction that makes a dying seat look healthy. Neither should be trusted on pre-2026-08-13 history; the honest read of the existing tally is a LOWER BOUND. WORTH CHECKING NEXT: this is a load-mutate-save pattern on a shared JSON, and data/audit_coverage.json also carries the coverage ledger that mark_audited writes -- a stale in-thread read could have overwritten coverage credit the same way, which would make the coverage ratchet (L1.50) understate too. Not measured here; the fix removes the mechanism going forward either way.",
+   "roi_bps": 12.0,
+   "raised": "2026-08-13T08:03:07.953726+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0589",
+   "source": "cycle",
+   "summary": "OFI decomposition test: split delta-bid/delta-ask into limit-inflow, cancellation and market-take components and regress forward return on each separately on the depth+trade tapes already held. Decides whether 'book imbalance' and 'aggressor-side trade intensity' are one axis or two -- if one, the desk's L1.18 independence count is too high by one. Source: JP miner s4, blog_UKI's failed spoofing INTERVENTION (the take components dominate). Both constructions are DSR-counted trials; UNMEASURED is a legal verdict.",
+   "roi_bps": 0.0,
+   "raised": "2026-08-13T08:04:25.771901+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0590",
+   "source": "cycle",
+   "summary": "Run the existing distribution-shift instrument against the screen TARGET series, per cell, and publish the verdict beside the IC. The desk checks FEATURE-distribution stationarity (richman score, dist_shift) and -- UNVERIFIED, and the first thing to falsify -- appears to have no target-side check; a target whose distribution moves between train and test is mis-specified in a way no feature-side check can see, failing to a false null in quiet regimes and a false positive in violent ones. Source: JP miner s4, qiita/pip_pip_pip_p.",
+   "roi_bps": 0.0,
+   "raised": "2026-08-13T08:04:42.405902+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
+  },
+  {
+   "id": "R0591",
+   "source": "cycle",
+   "summary": "OP-072 wiring: teach libs/research/convergence.py that post-2023 practitioner sources may be LLM-echoes. Two parts: (a) DERIVES-FROM: NONE (checked) must resolve to UNVERIFIABLE, not to independent, on post-2023 material; (b) a self-disclosed LLM-consultation marker (per-region list in the operator library) demotes a page's EXPLANATION layer to echo while leaving its OBSERVATION layer at full weight. Changes exactly one number -- how much a second agreeing source raises confidence. Rejects no source.",
+   "roi_bps": 0.0,
+   "raised": "2026-08-13T08:04:48.827727+00:00",
+   "status": "open",
+   "reason": null,
+   "commit": null,
+   "due": null,
+   "disposed": null
   }
  ]
 }
\ No newline at end of file
```


---

## 95289be5 panel seat telemetry loses 87% of its increments to a lost-update race
FOUND WHILE WIRING R0570'S DENOMINATOR, and it would have inherited the bug at
5x the frequency. record_blank was called from inside run_external_panel._one,
which runs under ThreadPoolExecutor(max_workers=5), and every call does
load() -> mutate -> save() on one shared JSON. Concurrent seats read the same
state and overwrite each other, and with 3-4 of 4 seats blanking together the
loss is the common case, not an occasional one.

THE TWO COUNTERS SETTLE IT, because they shipped in the SAME commit (14131c33,
2026-07-20) and have watched the SAME 28 runs:

  tune_budget   runs ONCE, after the fan-out    -> 70 blanks of 148 seat-calls
  seat_blanks   incremented inside the threads  ->  9

Same events, same window, 87% lost. Age cannot explain it; only the race can.
The old path also double-counted its own retry branch (record_blank, raise,
then record_blank again in the handler), so the surviving 9 were not even a
clean sample of what did land.

Both sets are derivable SERIALLY from what the executor returns -- a result
with no response key is a lost seat, whether it blanked twice or hard-errored
-- so nothing was ever gained by writing from the threads. record_attempts and
record_blanks now take the batch and write once, after the fan-out, beside
tune_budget and mark_audited which were always correct for exactly this reason.

This also drops N-1 redundant refresh() filesystem walks per panel run, and
removes the risk that a stale in-thread read overwrites the coverage ledger
that shares the file.

The AST test pins the property at the call site rather than trusting it.

Co-Authored-By: Claude <noreply@anthropic.com>

```diff
commit 95289be5e9e86b35a56bd8088ff59aa057f691d8
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:02:42 2026 +0000

    panel seat telemetry loses 87% of its increments to a lost-update race
    
    FOUND WHILE WIRING R0570'S DENOMINATOR, and it would have inherited the bug at
    5x the frequency. record_blank was called from inside run_external_panel._one,
    which runs under ThreadPoolExecutor(max_workers=5), and every call does
    load() -> mutate -> save() on one shared JSON. Concurrent seats read the same
    state and overwrite each other, and with 3-4 of 4 seats blanking together the
    loss is the common case, not an occasional one.
    
    THE TWO COUNTERS SETTLE IT, because they shipped in the SAME commit (14131c33,
    2026-07-20) and have watched the SAME 28 runs:
    
      tune_budget   runs ONCE, after the fan-out    -> 70 blanks of 148 seat-calls
      seat_blanks   incremented inside the threads  ->  9
    
    Same events, same window, 87% lost. Age cannot explain it; only the race can.
    The old path also double-counted its own retry branch (record_blank, raise,
    then record_blank again in the handler), so the surviving 9 were not even a
    clean sample of what did land.
    
    Both sets are derivable SERIALLY from what the executor returns -- a result
    with no response key is a lost seat, whether it blanked twice or hard-errored
    -- so nothing was ever gained by writing from the threads. record_attempts and
    record_blanks now take the batch and write once, after the fan-out, beside
    tune_budget and mark_audited which were always correct for exactly this reason.
    
    This also drops N-1 redundant refresh() filesystem walks per panel run, and
    removes the risk that a stale in-thread read overwrites the coverage ledger
    that shares the file.
    
    The AST test pins the property at the call site rather than trusting it.
    
    Co-Authored-By: Claude <noreply@anthropic.com>
---
 scripts/build_audit_coverage.py      | 78 +++++++++++++++++++++++-------------
 scripts/run_external_panel.py        | 43 ++++++++++----------
 tests/ops/test_seat_blank_recency.py | 46 +++++++++++++++------
 3 files changed, 105 insertions(+), 62 deletions(-)

diff --git a/scripts/build_audit_coverage.py b/scripts/build_audit_coverage.py
index 1c8fda33..5c55e4b7 100755
--- a/scripts/build_audit_coverage.py
+++ b/scripts/build_audit_coverage.py
@@ -22,6 +22,7 @@ from __future__ import annotations
 
 import json
 import subprocess
+from collections.abc import Iterable
 from datetime import UTC, datetime, timedelta
 from pathlib import Path
 
@@ -208,30 +209,6 @@ def tune_budget(blanked: int, total: int) -> int:
 _BLANK_EVENT_CAP = 400
 
 
-def record_blank(model: str) -> None:
-    """Per-seat blank tally -- turns a flaky seat into an evidence-backed swap decision.
-
-    THE TALLY ALONE COULD NOT SUPPORT THAT DECISION, WHICH IS WHY THE EVENTS EXIST.
-    `seat_blanks` is a LIFETIME counter that nothing anywhere resets or decays, so a seat that
-    blanked three times months ago and has answered every call since is permanently
-    indistinguishable from one that is dying right now. The fence keyed on it (`seat-chronic-*`)
-    therefore fires on every run forever once a seat crosses the threshold -- a gate that cannot
-    clear carries zero information, and its recommendation is to SWAP a seat that may be
-    perfectly healthy. Measured 2026-08-13: nemotron-3-super-120b had a lifetime 4 and the live
-    canary reported it alive and answering, 4/4 seats up.
-
-    The tally is KEPT and keeps incrementing -- `check_free_roster` and `model_upgrade` read it,
-    and it is honest as history. What is added is the timestamp, so a reader can ask "is this
-    seat failing NOW" instead of only "has it ever failed".
-    """
-    m = refresh(load())
-    m.setdefault("seat_blanks", {})[model] = int(m.get("seat_blanks", {}).get(model, 0)) + 1
-    events = m.setdefault("seat_blank_events", [])
-    events.append({"model": model, "ts": datetime.now(tz=UTC).isoformat()})
-    m["seat_blank_events"] = events[-_BLANK_EVENT_CAP:]
-    save(m)
-
-
 def recent_blanks(m: dict[str, object], *, window_days: int) -> dict[str, int] | None:
     """Blanks per seat inside `window_days`, or ``None`` when recency cannot be measured.
 
@@ -266,8 +243,52 @@ def recent_blanks(m: dict[str, object], *, window_days: int) -> dict[str, int] |
 _ATTEMPT_DAY_CAP = 30
 
 
-def record_attempt(model: str) -> None:
-    """One call to one seat. THE DENOMINATOR (R0570) that makes the blank tally a rate.
+def record_blanks(models: Iterable[str]) -> None:
+    """Every blank from ONE panel run, in ONE read-modify-write. NEVER call this per-thread.
+
+    WHAT THE TALLY IS FOR, AND WHY THE EVENTS SIT BESIDE IT. `seat_blanks` is a LIFETIME counter
+    that nothing anywhere resets or decays, so a seat that blanked three times months ago and has
+    answered every call since is permanently indistinguishable from one dying right now. The fence
+    keyed on it (`seat-chronic-*`) therefore fired forever once a seat crossed the threshold, and
+    its recommendation is to SWAP -- which costs a live seat off an under-driven roster. The tally
+    is KEPT and keeps incrementing (`check_free_roster` and `model_upgrade` read it, and it is
+    honest as history); the timestamped events are what let a reader ask "is this seat failing
+    NOW" instead of only "has it ever failed".
+
+    THE RACE THIS CLOSES, AND IT HAD ALREADY EATEN 87% OF THE TALLY. `record_blank` was called
+    from inside `run_external_panel._one`, which runs under a ThreadPoolExecutor(max_workers=5),
+    and every call does load() -> mutate -> save() on one shared JSON. Concurrent seats therefore
+    read the same state and overwrite each other, and with 3-4 of 4 seats blanking together the
+    losses are not occasional -- they are the common case.
+
+    MEASURED 2026-08-13, and the two counters settle it because they shipped in the SAME commit
+    (14131c33, 2026-07-20) and have watched the SAME 28 runs: `tune_budget` runs ONCE, AFTER the
+    fan-out, and recorded 70 blanks of 148 seat-calls. `seat_blanks`, incremented inside the
+    threads, sums to 9. Same events, same window, 87% lost. Age cannot explain it; only the race
+    can. The old path also double-counted the retry branch (record_blank, then raise, then
+    record_blank again in the handler), so the surviving 9 were not even a clean sample.
+
+    The blanked set is derivable SERIALLY from the results the executor returns -- a result
+    without a "response" key is a lost seat -- so nothing is gained by writing from the threads.
+    """
+    m = refresh(load())
+    tally = m.setdefault("seat_blanks", {})
+    events = m.setdefault("seat_blank_events", [])
+    now = datetime.now(tz=UTC).isoformat()
+    for model in models:
+        tally[model] = int(tally.get(model, 0)) + 1
+        events.append({"model": model, "ts": now})
+    m["seat_blank_events"] = events[-_BLANK_EVENT_CAP:]
+    save(m)
+
+
+def record_blank(model: str) -> None:
+    """One blank. Kept as the single-seat spelling of `record_blanks`."""
+    record_blanks([model])
+
+
+def record_attempts(models: Iterable[str]) -> None:
+    """Every seat asked in ONE panel run, in ONE read-modify-write. THE DENOMINATOR (R0570).
 
     "Blanked 4x" is not a measurement. Four failures out of four calls is a dead seat; four out of
     four hundred is a 1% flake on a free tier, and until now nothing counted the calls, so the two
@@ -291,8 +312,9 @@ def record_attempt(model: str) -> None:
     att = m.setdefault("seat_attempts", {})
     if not isinstance(att, dict):
         att = m["seat_attempts"] = {}
-    per = att.setdefault(model, {})
-    per[today.isoformat()] = int(per.get(today.isoformat(), 0)) + 1
+    for model in models:
+        per = att.setdefault(model, {})
+        per[today.isoformat()] = int(per.get(today.isoformat(), 0)) + 1
     cutoff = (today - timedelta(days=_ATTEMPT_DAY_CAP)).isoformat()
     for mdl in list(att):
         kept = {d: c for d, c in (att[mdl] or {}).items() if d >= cutoff}
diff --git a/scripts/run_external_panel.py b/scripts/run_external_panel.py
index 2079a341..9c4f5439 100755
--- a/scripts/run_external_panel.py
+++ b/scripts/run_external_panel.py
@@ -459,14 +459,6 @@ def main() -> None:
 
     def _one(pv: dict[str, Any]) -> dict[str, str]:
         name = pv.get("name", pv.get("model", "?"))
-        # THE DENOMINATOR (R0570). Exactly one attempt per seat per run, recorded BEFORE the call
-        # so a seat that dies mid-request still counts as having been asked -- otherwise the
-        # failures that matter most would be the ones missing from the denominator.
-        try:
-            from scripts.build_audit_coverage import record_attempt
-            record_attempt(pv.get("model", "?"))
-        except Exception:
-            pass
         try:
             txt, _stop = _ask_pushed(pv["base_url"], pv["key"], pv["model"],
                                      system, dossier)
@@ -482,11 +474,6 @@ def main() -> None:
                 txt, _stop = _ask_pushed(pv["base_url"], pv["key"], pv["model"],
                                          system, dossier)
                 if len(txt.strip()) < 50:
-                    try:
-                        from scripts.build_audit_coverage import record_blank
-                        record_blank(pv["model"])   # evidence for the next budget tune
-                    except Exception:
-                        pass
                     raise RuntimeError("blank response twice -- likely payload size; "
                                        "seat lost this run (recorded as an error, not a pass)")
             print(f"panel: {name} responded ({len(txt)} chars)")
@@ -494,20 +481,32 @@ def main() -> None:
         except Exception as e:                       # one dead provider never kills the panel
             print(f"panel: {name} FAILED {e!r}"[:150])
             # A HARD error is seat evidence exactly like a double-blank: until 2026-08-11 only
-            # the blank path called record_blank, so a seat dying with HTTP 400/404/KeyError
-            # left seat_blanks null and the seat-chronic fence + model_upgrade.regressed_seats
-            # were blind to the failure mode actually killing runs (measured: 4/4 free seats
-            # hard-erroring while seat_blanks stayed empty).
-            try:
-                from scripts.build_audit_coverage import record_blank
-                record_blank(pv.get("model", "?"))
-            except Exception:
-                pass
+            # the blank path was counted, so a seat dying with HTTP 400/404/KeyError left
+            # seat_blanks null and the seat-chronic fence + model_upgrade.regressed_seats were
+            # blind to the failure mode actually killing runs (measured: 4/4 free seats
+            # hard-erroring while seat_blanks stayed empty). Both paths land here, and a result
+            # with no "response" key is exactly the set recorded after the fan-out below.
             return {"provider": name, "model": pv.get("model", "?"), "error": repr(e)[:200]}
 
     from concurrent.futures import ThreadPoolExecutor
     with ThreadPoolExecutor(max_workers=5) as ex:    # parallel fan-out: panel completes in
         results = list(ex.map(_one, providers))      # ~one slowest-model time, not the sum
+
+    # SEAT TELEMETRY IS WRITTEN HERE, SERIALLY, AND NEVER FROM INSIDE THE THREADS. Each recorder
+    # does load() -> mutate -> save() on one shared JSON, so calling them per-seat under a
+    # max_workers=5 pool makes concurrent seats read the same state and overwrite each other.
+    # That is not theoretical: record_blank and tune_budget shipped in the SAME commit (14131c33)
+    # and have watched the SAME 28 runs, and tune_budget -- which runs once, here, after the
+    # fan-out -- recorded 70 blanks of 148 calls while seat_blanks, incremented inside the
+    # threads, summed to 9. Same events, same window, 87% lost to the race. The old path also
+    # double-counted its own retry branch. Both sets are derivable serially from `results`: a
+    # result carrying no "response" key is a lost seat, whether it blanked twice or hard-errored.
+    try:
+        from scripts.build_audit_coverage import record_attempts, record_blanks
+        record_attempts([p.get("model", "?") for p in providers])
+        record_blanks([r.get("model", "?") for r in results if "response" not in r])
+    except Exception as _e:                          # telemetry never kills the panel
+        print(f"panel: could not record seat telemetry ({_e!r})")
     with _LOG.open("a", encoding="utf-8") as f:
         for r in results:
             f.write(json.dumps({"ts": ts, "mission": mission, **r}) + "\n")
diff --git a/tests/ops/test_seat_blank_recency.py b/tests/ops/test_seat_blank_recency.py
index feda98cb..bf987ee0 100644
--- a/tests/ops/test_seat_blank_recency.py
+++ b/tests/ops/test_seat_blank_recency.py
@@ -145,34 +145,56 @@ class TestTheWriterIsActuallyWired:
     functions above would pass identically if `record_attempt` were never called by anything, so
     these drive the real store (redirected to tmp_path -- never the live ledger)."""
 
-    def test_record_attempt_round_trips_into_a_gradeable_denominator(self, tmp_path,
-                                                                     monkeypatch):
+    def test_record_attempts_round_trips_into_a_gradeable_denominator(self, tmp_path,
+                                                                      monkeypatch):
         from scripts import build_audit_coverage as bac
 
         monkeypatch.setattr(bac, "ROOT", tmp_path)
         monkeypatch.setattr(bac, "MANIFEST", tmp_path / "coverage.json")
         monkeypatch.setattr(bac, "_eligible", lambda: [])
 
-        for _ in range(ma.SEAT_MIN_ATTEMPTS):
-            bac.record_attempt(_SEAT)
+        bac.record_attempts([_SEAT] * ma.SEAT_MIN_ATTEMPTS)
 
         m = bac.load()
         assert recent_attempts(m, window_days=7) == {_SEAT: ma.SEAT_MIN_ATTEMPTS}
         m["seat_blanks"] = {_SEAT: 4}
         assert _seat_defects(m) == []                 # graded healthy off real recorded calls
 
-    def test_the_panel_records_an_attempt_for_every_seat_it_asks(self):
-        """The call site, by inspection: one `record_attempt` at the top of `_one`, before the
-        request, so a seat that dies mid-call still lands in its own denominator."""
+    def test_a_batch_of_blanks_is_one_write_and_loses_nothing(self, tmp_path, monkeypatch):
+        """THE RACE THIS REPLACES, in one assertion. Per-seat writes under a max_workers=5 pool
+        lost 87% of the tally (70 blanks recorded by tune_budget vs 9 by record_blank, same
+        commit, same 28 runs). A batch write cannot lose an increment to a sibling."""
+        from scripts import build_audit_coverage as bac
+
+        monkeypatch.setattr(bac, "ROOT", tmp_path)
+        monkeypatch.setattr(bac, "MANIFEST", tmp_path / "coverage.json")
+        monkeypatch.setattr(bac, "_eligible", lambda: [])
+
+        bac.record_blanks([_SEAT, _SEAT, _OTHER])
+
+        m = bac.load()
+        assert m["seat_blanks"] == {_SEAT: 2, _OTHER: 1}
+        assert len(m["seat_blank_events"]) == 3
+        assert recent_blanks(m, window_days=7) == {_SEAT: 2, _OTHER: 1}
+
+    def test_the_panel_never_writes_seat_telemetry_from_inside_a_thread(self):
+        """The property, enforced at the call site rather than trusted. `_one` runs under
+        ThreadPoolExecutor(max_workers=5); any recorder called from it races every sibling on one
+        shared JSON, which is how the 87% went missing."""
         import ast
         from pathlib import Path
 
         src = Path(ma.ROOT / "scripts/run_external_panel.py").read_text("utf-8")
-        fn = next(n for n in ast.walk(ast.parse(src))
+        tree = ast.parse(src)
+        fn = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_one")
-        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
-                 and getattr(n.func, "id", "") == "record_attempt"]
-        assert len(calls) == 1, "exactly one attempt per seat per run, or the rate is wrong"
+        inside = {getattr(n.func, "id", "") for n in ast.walk(fn) if isinstance(n, ast.Call)}
+        assert not (inside & {"record_blank", "record_blanks",
+                              "record_attempt", "record_attempts"}), \
+            "seat telemetry written inside the parallel fan-out -- the lost-update race"
+        # ...and it IS written, once, somewhere else in the module.
+        whole = {getattr(n.func, "id", "") for n in ast.walk(tree) if isinstance(n, ast.Call)}
+        assert {"record_attempts", "record_blanks"} <= whole, "the recorders lost their caller"
 
     def test_pruning_keeps_the_window_intact(self, tmp_path, monkeypatch):
         """The cap bounds growth; it must never evict a day the 7d window still needs."""
@@ -185,7 +207,7 @@ class TestTheWriterIsActuallyWired:
         recent = (datetime.now(tz=UTC).date() - timedelta(days=3)).isoformat()
         bac.save({"files": {}, "seat_attempts": {_SEAT: {old: 99, recent: 7}}})
 
-        bac.record_attempt(_SEAT)
+        bac.record_attempts([_SEAT])
 
         kept = bac.load()["seat_attempts"][_SEAT]
         assert old not in kept                        # bounded
```


---

## a1eaa5fc JP miner 08-13: finalize session note + JP region row (OP-072/073, WS-013, OFI decomposition, deep-forest tail opened)

```diff
commit a1eaa5fc8bf7c22cb1bfe7beab946d62c3b116ad
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:02:38 2026 +0000

    JP miner 08-13: finalize session note + JP region row (OP-072/073, WS-013, OFI decomposition, deep-forest tail opened)
---
 docs/research/prospector_coverage.md | 135 ++++++++++++++++++++++++++++++++++-
 1 file changed, 133 insertions(+), 2 deletions(-)

diff --git a/docs/research/prospector_coverage.md b/docs/research/prospector_coverage.md
index 2c2fbde3..313031ed 100644
--- a/docs/research/prospector_coverage.md
+++ b/docs/research/prospector_coverage.md
@@ -18,7 +18,7 @@ _Seeded 2026-07-18; every family unvisited -- the first run biases per the rotat
 | Academic (SSRN/arXiv) | never | 0 | untouched this session (RSRS is sell-side research, not SSRN/arXiv) — priority next run. **2026-08-01: touched only OBLIQUELY — the OLMAR paper (Li & Hoi ICML-2012 #168) was read THROUGH its forum thread, where its author answers questions the paper never addresses. Standing note: for any algorithm with a live practitioner community, the FORUM is a higher-yield read than the paper.** |
 | Records (contests/CTA) | 2026-07-25 | 1 | partial, via forum route: Bitcointalk "Automated Trading Contest" (topic 261086, CryptoTrader.org rounds #1-#5) mined as a contest RECORD — produced the in-sample-vs-forward natural experiment graveyard entry. Kaggle G-Research + Numerai post-mortems still untouched |
 | Non-English forums | 2026-07-26 | 2 | s1 (07-19): Chinese RSRS + funding-arb (CSDN/VeighNa/BigQuant/Zhihu/FMZ) + JP note.com — RSRS EV-killed, ML-funding-rate graveyard-matched. **s2 (07-26, CN frontier miner): axis #76 usdt-cny-otc-premium UN-PARKED — "no clean free API" REFUTED, 3 keyless routes, 591d history reconstructed (OP-031 CDX-replay of a capped JSON API), Stage-A screened 4/4 cells → no promotable edge but the catalogued mechanism's SIGN and MAGNITUDE priors both falsified. New: OP-031, OP-032, CN lexicon.** Era-archaeology (banzhuan/8btc/ChainNode/Tieba) still UNSTARTED — first item next run. **s3 (2026-08-01): T1 instrument repair — the 7 supplied unverified slang terms negative-controlled, 0/7 survived, 6 with the real form named; +14 verified lexicon rows; OP-036 (evasion slang has a BIRTH DATE — 大饼 born of the 2017-09-04 "94" ban, so the search key is a function of the ERA, and our era ground straddles it), OP-037 (negative-control a supplied glossary), OP-038 (a JS wall on the HTML is not a wall on the API — unblocked the Gitee chain carried 3 sessions). CN OSS tranche: AlphaGPT paper + NOFX "3 mechanisms" both REFUTED, Vibe-Trading crypto layer weaker than ours (honest null). Screened `unlock_events.json` (24,201 events, 0 readers) 0/27 cells → UNMEASURABLE not dead, 2 measurement defects. VERIFIED on live API: a 123-event Binance delisting forced-close panel discarded by a `status=="TRADING"` filter (R0292). R0288–R0293. Era: 8btc thread-44638 mined to reply-depth, CN-side corroboration of the cross-venue-premium kill. DIASPORA ANSWERED: CN discussion migrated into paid/ID-gated enclosures — §13 puts it permanently out of reach, so the open CN layer worth mining is repos + era archives + platform 文库, NOT live community.** |
-| Non-English forums — **JP** | 2026-08-12 | 3 | **s3 (2026-08-12, JP frontier miner): §13 REGRESSION — note.com + zenn.dev now serve 403 to ClaudeBot/GPTBot/CCBot/Bytespider AT THE CDN EDGE while BOTH robots.txt files are clean of any such rule (Googlebot/curl/SomeRandomBot get 200 ⇒ a curated AI-crawler denylist, not a WAF heuristic). HARD STOP, archives included; NOT routed around (Claude-User returns 200 and was deliberately not used). Closes 116/187 (62%) of the mapped botter corpus incl. all 3 planned targets; rollout DATED between 08-04 and 08-12 by this seat's own successful prior reads → **OP-052** (probe the CONTENT PATH with a UA matrix; robots.txt is necessary, not sufficient) + lesson **L0096** + **R0466** (a blocked ground and an exhausted ground are byte-identical to any fetch path that treats non-200 as no-content — a FALSE NULL that silently retires a region). **Past-due PI-vs-FR deferral RESOLVED** (`data/jp_funding_clamp_census.json`): clamp verified by positive control (BTC 49/60, DOGE 46/60); **41.6% of the owned 8h panel and 68.8% of the live 812-symbol cross-section sit on a censoring constant**, 74.9 bps of real premium dispersion hides inside one 56-name tie group — the root cause of the already-paid-for "42 perps at the 1bp floor" churn incident; censoring DECAYS 68.8%(2019)→10.7%(2026) ⇒ **backtest-integrity upgrade first, live-signal second**; EV 0.0193 QUEUE, novelty 0.726, NOT promoted (screen still owed). **L1.47 corroborated with a count → R0465: 426/812 (52.4%) of live perps settle on 4h, only 385 on the 8h that `held/8.0` assumes** ("many" is the majority); ranking damage honestly modest (Spearman 0.959). JP funding-settlement sandwich (qiita/lud-botter, DERIVES-FROM: NONE checked ⇒ genuine independent convergence with L1.47) **EV 0.0006 REJECT** as published — dead at source, venue changed settlement rules mid-operation — with the observation routed as execution-timing **EV 0.0087 QUEUE**; JP **Travel Rule 2023-06-01** era marker (domestic↔overseas arb killed by regulation, not competition). **マケデコ (`market-api`) NEW GROUND opened + mapped: 74 entries 2023–2025 (2021/22 = 404, series began 2023), JP EQUITIES not crypto, 74% on the closed hosts**; J-Quants axis catalogued-unverified (row 29). Video: 0 fetched, 0 locked.** — **s1 (2026-08-01, JP frontier miner, seat's first run).** §13: **5ch.net + all sister hosts REFUSE `ClaudeBot` by name** (Cloudflare-*managed* block → treat as a platform rollout, not a site decision; re-check on entry, never cache); note/qiita/zenn/GMO/bitbank clean. **bitFlyer axis CLOSED after 4 deferrals** — the "403/WAF/needs-a-human" record was a **tarpit**, the block is **per-hostname** (api+lightning serve 200 from the *same edge IP*), the "never archived" claim was a wrong CDX host+slug, and the ToS was then read: it retains rights in *"data such as transaction prices"* → **`restricted-by-licence`**, which pre-emptively killed `getchats`, `getfundingratehistory` and an archived keyless 15-min BTC/JPY series (2014-10→, Wayback-only) before any were carded. **Replacements found same run: GMO Coin free keyless tick tape (2018-09-05→, 28 spot + 12 margin, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank — both licence-unread, no ingest (R0309/R0310).** **richmanbtc lineage (the C62 "gem", unstarted 12 days) KILLED**: the edge is a bare ATR×0.5 limit, the ML adds ~nothing, and the maker fee was **zero-or-negative across the whole backtest** → a venue-subsidy harvest, dead on 3 venues. Salvaged 3 CC0 tools (p-mean order-sensitive decay bar — **published error-rate formula reproduced BROKEN**; time-adversarial feature screen; `publicGetExpiredFutures` for R0239). New: **OP-043/044/045** + OP-041 refinement. Era-archaeology (2017 bitFlyer-FX **SFD**, Mt.Gox 5ch) **UNSTARTED**; JP lexicon seeds still **unverified**. Next: **the 仮想通貨botter Qiita Advent Calendar 2021–2025, never touched.** |
+| Non-English forums — **JP** | 2026-08-13 | 4 | **s4 (2026-08-13, JP frontier miner): THE DEEP-FOREST SELF-HOSTED TAIL OPENED — after 08-12 closed 62% of the mapped corpus, a UA-matrix probe over 10 hosts found **8/9 self-hosted botter blogs serve 200 to ClaudeBot and 4 have no robots.txt at all** → **OP-073** (an AI-crawler denylist is a PLATFORM product decision; re-scope the HOST COLUMN, never the region — the JP ground went from "thinning" to a fresh 20-entry queue across 12 open domains with one group-by). **zenn.dev sharpened the §13 finding into its worst form: robots.txt now returns 200 AND explicitly allows `*`, while the content path returns 403 — every standard §13 check comes back green and permissive over a closed ground.** **OP-072, the run's best find and fleet-wide: the post-2023 practitioner corpus is LLM-CONTAMINATED** — the mined options post's entire mechanism analysis is self-disclosed ChatGPT output (チャッピー), so practitioners in unrelated regions now converge because they queried the same weights, not because the world taught them; worse than the arXiv echo GAP #85 models (a paper echo leaves a citation, an LLM echo leaves nothing), fixed by per-region markers + an observation/explanation split + `NONE (checked)` made illegal post-2023 (→ UNVERIFIABLE), and it hands era-archaeology a new argument: **pre-2023 archives are structurally uncontaminated.** MINING: `blog_UKI`'s BitMEX spoofing **intervention** (not an observation) decomposes OFI → **the market-order take components dominate; the displayed book is not where the information is**, so `book imbalance` and `aggressor flow` may be ONE axis and the desk's L1.18 independence count too high by one (EV 0.0002 REJECT as a trade → routed to improvement_inbox as a feature-redundancy fact; the strategy is prohibited conduct and is not proposed). `pip_pip_pip_p` **corroborates the 08-01 richmanbtc kill from the opposite fee sign** (the rule-based core is down-sloping on Binance in every period since 2021, incl. the 2024-11/12 bull) + names a live desk gap: **the desk checks FEATURE-distribution stationarity, apparently never the TARGET's**. `gitan.dev`'s 2023↔2024 venue-survey **pair** (a free longitudinal diff) → **WS-013**: a 13-month +2% JP margin dislocation, a venue REPLACING an SFD divergence penalty with a funding rate, and its resting long-pays-short constant **numerically identical to Binance's 0.01%/8h interest component** — an independent venue corroborating this seat's 08-12 clamp census that the 1bp print is a copied CONVENTION. Graveyard ×1 (`rev_calendar_spread_iv_convergence`, refuted at source: vega-neg + theta-neg has no favourable regime; its transferable half is **a hedged leg with a contractual expiry un-hedges itself on a schedule** — a risk-rail event for any future dated-future-vs-perp basis trade). Universe source **102** (venue fee schedule as the conditioning variable for every volume feature; EV 0.0058 QUEUE, the session's only gate survivor of 4 scored). +8 OBSERVED JP lexicon rows (鞘/アビトラ/見せ板/お蔵入り/反面教師/チャッピー/限月/爆損). **Self-caught defect: my own 08-12 next-run queue was 40% dead on arrival** — titled "qiita-hosted", it named 3 zenn.dev entries I had ruled HARD STOP in the same note. Video: 0 fetched, 0 locked.** —  **s3 (2026-08-12, JP frontier miner): §13 REGRESSION — note.com + zenn.dev now serve 403 to ClaudeBot/GPTBot/CCBot/Bytespider AT THE CDN EDGE while BOTH robots.txt files are clean of any such rule (Googlebot/curl/SomeRandomBot get 200 ⇒ a curated AI-crawler denylist, not a WAF heuristic). HARD STOP, archives included; NOT routed around (Claude-User returns 200 and was deliberately not used). Closes 116/187 (62%) of the mapped botter corpus incl. all 3 planned targets; rollout DATED between 08-04 and 08-12 by this seat's own successful prior reads → **OP-052** (probe the CONTENT PATH with a UA matrix; robots.txt is necessary, not sufficient) + lesson **L0096** + **R0466** (a blocked ground and an exhausted ground are byte-identical to any fetch path that treats non-200 as no-content — a FALSE NULL that silently retires a region). **Past-due PI-vs-FR deferral RESOLVED** (`data/jp_funding_clamp_census.json`): clamp verified by positive control (BTC 49/60, DOGE 46/60); **41.6% of the owned 8h panel and 68.8% of the live 812-symbol cross-section sit on a censoring constant**, 74.9 bps of real premium dispersion hides inside one 56-name tie group — the root cause of the already-paid-for "42 perps at the 1bp floor" churn incident; censoring DECAYS 68.8%(2019)→10.7%(2026) ⇒ **backtest-integrity upgrade first, live-signal second**; EV 0.0193 QUEUE, novelty 0.726, NOT promoted (screen still owed). **L1.47 corroborated with a count → R0465: 426/812 (52.4%) of live perps settle on 4h, only 385 on the 8h that `held/8.0` assumes** ("many" is the majority); ranking damage honestly modest (Spearman 0.959). JP funding-settlement sandwich (qiita/lud-botter, DERIVES-FROM: NONE checked ⇒ genuine independent convergence with L1.47) **EV 0.0006 REJECT** as published — dead at source, venue changed settlement rules mid-operation — with the observation routed as execution-timing **EV 0.0087 QUEUE**; JP **Travel Rule 2023-06-01** era marker (domestic↔overseas arb killed by regulation, not competition). **マケデコ (`market-api`) NEW GROUND opened + mapped: 74 entries 2023–2025 (2021/22 = 404, series began 2023), JP EQUITIES not crypto, 74% on the closed hosts**; J-Quants axis catalogued-unverified (row 29). Video: 0 fetched, 0 locked.** — **s1 (2026-08-01, JP frontier miner, seat's first run).** §13: **5ch.net + all sister hosts REFUSE `ClaudeBot` by name** (Cloudflare-*managed* block → treat as a platform rollout, not a site decision; re-check on entry, never cache); note/qiita/zenn/GMO/bitbank clean. **bitFlyer axis CLOSED after 4 deferrals** — the "403/WAF/needs-a-human" record was a **tarpit**, the block is **per-hostname** (api+lightning serve 200 from the *same edge IP*), the "never archived" claim was a wrong CDX host+slug, and the ToS was then read: it retains rights in *"data such as transaction prices"* → **`restricted-by-licence`**, which pre-emptively killed `getchats`, `getfundingratehistory` and an archived keyless 15-min BTC/JPY series (2014-10→, Wayback-only) before any were carded. **Replacements found same run: GMO Coin free keyless tick tape (2018-09-05→, 28 spot + 12 margin, JP-only MONA/XYM/FCR/NAC/WILD) and bitbank — both licence-unread, no ingest (R0309/R0310).** **richmanbtc lineage (the C62 "gem", unstarted 12 days) KILLED**: the edge is a bare ATR×0.5 limit, the ML adds ~nothing, and the maker fee was **zero-or-negative across the whole backtest** → a venue-subsidy harvest, dead on 3 venues. Salvaged 3 CC0 tools (p-mean order-sensitive decay bar — **published error-rate formula reproduced BROKEN**; time-adversarial feature screen; `publicGetExpiredFutures` for R0239). New: **OP-043/044/045** + OP-041 refinement. Era-archaeology (2017 bitFlyer-FX **SFD**, Mt.Gox 5ch) **UNSTARTED**; JP lexicon seeds still **unverified**. Next: **the 仮想通貨botter Qiita Advent Calendar 2021–2025, never touched.** |
 | Non-English forums — **BR** | 2026-08-12 | 2 | **s2 (2026-08-12) — THE NATIVE KEY WAS HIDING THE DESK'S ONLY NEVER-HUNTED FAMILY.** Cleared s1's 8-day-overdue ITEM 3. Measured, same corpus same minute: `pairs trading brasil` → **0 repos**, `cointegração` (native PT key) → **30**, essentially all genuine statarb, several crypto-native — so a seat querying the English term grades BR statistical arbitrage DEAD on a clean zero, and `strategy_coverage.json` reports **STATISTICAL-ARBITRAGE as the only never-hunted family (0/14)**. `long short` is unusable bare in PT-BR via **two independent collisions** (LSTM written out in full; C's `unsigned long/short`) — the vocabulary sibling of the RU ticker collision. **OP-054.** Depth on `mateusmartinelli/tcc` (crypto pairs trading; Gatev + Caldeira–Moura + Rad–Low–Faff): more rigorous than average (loads T-bills, computes excess returns) yet **three code/comment contradictions all in the config block** — cost 0.001 commented "0.05%" (**2×**, conservative), entry **1.5σ** commented "2σ as per paper" (**not** conservative), formation **90d** commented "252" — plus **zero funding accounting** and top-10 pairs from ~4,950 candidates at p<0.10 with **no multiplicity correction** (~495 expected false pairs). **OP-055.** Killed `pedhsm/systematic-research-framework`'s MCPT: it permutes **realised returns** and scores sharpe/cagr/vol, **all order-invariant** — verified by independent reimplementation, 500 perms × 4 series, **max−min = 1.1e-15**; FP non-associativity then makes the p-value a rounding-order hash (**winner p=0.978, catastrophe p=0.618**). A **wall, not a bar** → graveyard + **OP-056**. **The desk was already ahead** (`bar_permutation.py` permutes bars, with a measured `_TIE_RTOL` + add-one) ⇒ genuine cross-ecosystem convergence, **NO BUILD**. RFB: s1's *"decaying deadline"* was an inferred rate — census gives **23 dates, 12 live / 12 dead, clean boundary at 2023-03-02|2023-05-03, 4 with no capture at all**; **rate UNMEASURED** (two rival hypotheses, opposite urgency, falsifier recorded) and the series is **~4 months unpublished against a 13-month hiatus precedent**. BR lexicon opened (none existed); supplied seeds scored **0/3 as dark-forest keys**. Video: **0 fetched, 0 locked — not attempted**, named in next ground. Next: `Vido/zecontinha` fork tree + crypto subset, `TCC` as a structural key, PT-BR video, B3 (still unprobed), era-archaeology (still not started). |
 | _(BR s1 history)_ | 2026-08-01 | 1 | **s1 (2026-08-01, BR frontier miner, seat's first run).** **§13: the KR/JP by-name-block pattern does NOT generalise** — 18 hosts swept full-file over 17 AI-crawler tokens, **zero BR blocks**; the community layer (bastter, InfoMoney, MQL5-PT, Investing BR, bitcointalk, YouTube, Telegram) is **open**, so KR/JP was a property of *those* consumer portals, not a global rollout (OP-041 corrected). One **HARD STOP: `reddit.com` `Disallow: /`** to everyone — a *global* decision that bites BR hard (r/investimentos, r/farialimabets, r/BrasilBitcoin). **Pre-emptive graveyard check killed one third of my own brief before any searching:** the seat's era target "BR P2P premium" is already `mercado_br` **REJECTED** (graveyard:81) inside a family killed **5×** whose lone survivor (kimchi) was itself refuted 07-30 — no L1.16a enabling change exists, so the **seed list** is the defect. **THE FIND: RFB `criptoativos_dados_abertos`** — Brazil's **mandatory** national crypto-reporting panel (every domestic exchange reports **every** operation, no minimum; P2P + foreign venues >R$30k), free and keyless: **77 months Ago-2019→Dez-2025, 66 assets, 4,206 asset-months**; Dez-2025 = **3,544,986 taxpayers / R$43.1bn**; all-time **USDT R$1.004tn vs BTC R$269bn (3.7×)** ⇒ a **dollarization**, not speculation, mechanism. **Deliberately NOT screened** — n=77 monthly + 3.5mo lag vs a ~4,268-obs bar would manufacture a false null (L1.25); reported **UNDERPOWERED** with the cross-sectional enabling change named. **The depth layer was the prize: a FREE POINT-IN-TIME VINTAGE STACK** — RFB republishes monthly under a dated filename and **42/42 common months are revised** (worst Março-2023 **+40.9%**; a month **2.4y old** still moved), systematically upward, so backtesting today's file is a **+41% look-ahead in the CONDITIONING variable** (R0289 class — passes every return-series leak check, fails toward a FALSE POSITIVE). Proven recoverable: 23+ dates in CDX, and a **live-404 vintage restored intact** via `web.archive.org/<ts>id_/`. Read at all only by writing a **stdlib OLE2+BIFF8 reader** (no xlrd on this box) validated by the data's **own conservation law: 78/78 rows, residual 0.00e+00**. New **OP-046 / OP-047 / OP-035-BR**; R0316–R0318. Incidental: a **BR-only tokenized-RWA universe** in a government dataset (**MBPRK = tokenized *precatórios***, MBCONS, IMOB01, MCO2; **BRZ = 92.4M ops**, a payment rail). **ITEM 3 (PT-BR practitioner ground) explicitly DEFERRED to 08-04, not dropped.** Next: practitioner ground first, then **mirror the vintage stack before it decays**, B3, Pix fraud stats. |
 | Non-English forums — **AR** | 2026-08-12 | 1 | **s1 (2026-08-12, AR frontier miner, seat's first run) — IN PROGRESS.** No AR row existed before this run (`grep -ic arabic` = 0). **Pre-emptive graveyard check killed the seat brief's ENTIRE era target before any searching:** MENA/Egypt/Lebanon P2P-premium-under-FX-restriction is `era_crossvenue_fiat_premium_arb` (buried **7×**) inside the regional-premium class the desk declared **exhausted** (`try_premium_timing` — the Turkey capital-control analog, the closest MENA case that exists — REJECTED; kimchi, the lone survivor, itself KILLED 08-01); `strategy_coverage.json` has CROSS-VENUE-PREMIUM = HUNTED/9. Second consecutive seat (after BR) handed a dead era target ⇒ **the seed list is the defect**. Items: (1) §13 UA-matrix access map (OP-052) — AR unmapped in BOTH directions, and R0466 makes an unmapped ground's null uninterpretable; (2) report+replace the dead brief; (3) **replacement axis: Hijri/Ramadan calendar + Sharia-compliance forced-flow** — novelty-clean at **0 hits** across graveyard/both watchlists/universe map/vault, maps to NONE of the 24 CRYPTO_MECHANISMS, and lunar-vs-Gregorian drift (~11d/yr) makes it orthogonal to every Gregorian calendar effect by construction. See session note below. |
@@ -1404,7 +1404,138 @@ cheapest remaining binary-search extension.
 
 ## SESSION NOTES — JP frontier miner
 
-### 2026-08-13 session (JP frontier miner) — IN PROGRESS (write-first note; updated as each item resolves)
+### 2026-08-13 session (JP frontier miner) — COMPLETE (write-first note, finalized end of run)
+§33 STANDING TEST ("which artifact on disk is different because of what was mined?"):
+`docs/graveyard.md` (+2 entries), `docs/research/search_operator_library.md` (**+OP-072, +OP-073,
++8 OBSERVED JP lexicon rows**), `docs/research/improvement_inbox.md` (+2 engine items),
+`docs/research/weak_signal_registry.md` (**+WS-013**), `data/data_universe_map.json` (**+source
+102**), `docs/research/prospector_watchlist.md` (+4 gated candidates, 0 cards), this note. Not "none".
+
+**RESULTS.**
+0. **ACCESS PROBE → BLOCK PERSISTS, AND THE SHAPE SHARPENED INTO A WORSE FINDING.** `note.com` still
+   403s ClaudeBot on both robots.txt and content. **`zenn.dev` now serves `robots.txt` with a 200 —
+   and that robots.txt explicitly ALLOWS `*` on article paths while naming only
+   Bytespider/Megalodon/ia_archiver as denied — yet the content path returns
+   `403 {"message":"Please contact the site owner for access."}`.** On 08-12 note.com's robots
+   itself 403'd, which is at least a warning to a careful seat. **Here every §13 check a seat
+   normally runs comes back GREEN and PERMISSIVE while the ground is closed.** That is OP-052's
+   worst case realised: the published policy and the enforced policy now *contradict* each other,
+   and only a content-path probe can tell. HARD STOP upheld, archives included; no article body was
+   fetched from either host, and no alternate UA was used for content.
+1. **qiita survivors → BOTH READ TO FULL DEPTH; the better one is the run's best find and it is NOT a
+   trade.** `blog_UKI` (2021, 37 likes, **comment layer checked: 0**) documents an **intervention**:
+   he tried to manufacture OFI with spoofed BitMEX size to move bitFlyer, regression said ~$500k of
+   book change → ~¥100, ~$5k margin at 100× would do it — **and it failed.** His decomposition
+   explains why: of the six components of ΔBid−ΔAsk, **the market-order take components (3) and (6)
+   dominate the explanatory power**; the displayed book carries some but is not where the
+   information is. **Consequence here: `book imbalance` and `aggressor-side trade intensity` may be
+   ONE axis wearing two names, which would make the desk's L1.18 independence count too high by
+   one.** Decisive test runs on the depth+trade tapes already held. Scored honestly as a strategy —
+   **EV 0.0002 REJECT** (`high_turnover_no_maker`+`crowded_known`; an HFT-horizon OFI signal is DOA
+   for a latency-disadvantaged spread-taker) — so it is routed to `improvement_inbox.md` as a
+   feature-redundancy fact rather than carded. The strategy itself is prohibited market conduct and
+   is neither implementable nor proposed; what was extracted is *evidence about market structure
+   produced by an intervention*, which is precisely what L1.45 says observation cannot buy.
+   `pip_pip_pip_p` (2024, **comments: 0**) independently plots the richmanbtc rule-based core **on
+   Binance BTCUSDT: up only in 2021, down-sloping in every period since, including the 2024-11/12
+   bull** → **corroborates this seat's 08-01 kill from the opposite fee sign** (it printed where the
+   maker fee was ≤0, it fails where it is >0). Addendum written to the graveyard entry.
+2. **DEEP-FOREST SELF-HOSTED LAYER → OPENED, and it is WIDE OPEN (→ OP-073).** 8 of 9 self-hosted
+   blogs serve 200 to ClaudeBot; **4 of them have no robots.txt at all.** An AI-crawler denylist is a
+   *platform product decision*; an individual on their own WordPress has no legal function to write
+   one. **The JP ground went from "62% closed, thinning" to a fresh 20-entry queue across 12 open
+   domains with a single group-by on the `host` column** — which is why every corpus map must carry
+   one. Mined 3 of them to depth this run: `gitan.dev` (the 2023↔2024 venue-survey **pair** → WS-013
+   + universe source 102), `perp-screener.com` (→ graveyard), `blog.shidokamo.com` (era post-mortem,
+   below).
+
+**BEST FIND OF THE RUN, AND IT IS A PROCESS FINDING RATHER THAN A MECHANISM → OP-072.** The options
+post's entire greeks analysis is introduced as *"チャッピーの解説によると"* — **according to ChatGPT** —
+and the author twice tells readers to ask an LLM rather than him. **Since ~2023 the practitioner
+corpus has a second shared upstream that the provenance mandate does not model: the frontier LLMs.**
+A JP, a KR and a BR botter who each ask ChatGPT to explain their spread will agree *because they
+queried the same weights*, and `convergence.py` cannot distinguish that from the world teaching them
+the same thing. **It is strictly worse than the arXiv-echo case GAP #85 was built for: a paper echo
+leaves a citation, an LLM echo leaves nothing** unless the author volunteers it. OP-072 gives the
+per-region textual markers, splits every page into an **observation layer** (uncontaminated — what
+they ran, held and lost) and an **explanation layer** (possibly model output), and makes `NONE
+(checked)` illegal on post-2023 material — the honest value there is **UNVERIFIABLE**, because
+absence of disclosure is not evidence of absence (L1.28a). **It rejects no page and ranks no source
+lower**; it changes exactly one number, how much a second agreeing source raises confidence. And it
+hands the era mandate a new argument: **every archive that died before ~2023 is structurally
+uncontaminated**, so dead ground now buys a provenance guarantee no living-web source can offer.
+
+**DEPTH LINE (mandate report).** `gitan.dev`: **exhausted as a pair** — both editions read in full and
+diffed line-by-line, which is what produced all three WS-013 observations; the diff carries what
+neither post states (**a venue REPLACED an SFD-style divergence penalty with a funding rate**, and
+its resting long-pays-short constant is **numerically identical to Binance's 0.01%/8h interest
+component** — an independent venue corroborating this seat's own 08-12 clamp census that the 1bp
+print is a copied CONVENTION, not a measured cost). Comment layer: 1 comment, a pingback between the
+two posts — recorded as the zero it effectively is. `blog_UKI`: full body + the OFI decomposition +
+his cited 2018 note; **0 comments**. `pip_pip_pip_p`: full body; **0 comments**. `perp-screener`:
+full body incl. the greeks table and the reflection section; site has no comment layer.
+`blog.shidokamo.com`: read to code depth (57k chars, the bot source is inline) — surfaced what the
+title cannot: **DEX-CEX spreads of 4% caught 50+ times a day in the 2020 DeFi bubble (~¥2M/day), a
+bot whose threshold was ≥10% spread**, a **tried-and-abandoned front-running attempt** (*"全然儲かり
+ませんでした。撤退撤退！"*), the USDT/USDC **6-decimals-not-18** trap (*"間違うと死にます"*), an
+asymmetric-reliability observation (**the DEX leg fails on slippage; the CEX leg never once failed**),
+and the reason the trade was inventory-bound (transfers never automated, for fear of GOX). His
+mechanism story for why small spreads persist is a **rational-inattention** argument — nobody
+complains when a 50-minute job takes 52, and that is a 4% difference — which is the cleanest
+statement of §42's premise this seat has read anywhere. **Video: 0 fetched, 0 locked** (no video-only
+mechanism encountered; the explicit zero per the mandate).
+
+**PROACTIVE BATTERY.** #1 CONTINGENCY-BEFORE-FAILURE — the standing access re-probe is what turned a
+"closed ground" into OP-073's re-aim, for the second run in a row. #4 REGRESSION SWEEP — comparing
+today's zenn result against 08-12's is what upgraded the finding (robots 403 → robots 200-and-
+permissive is a *worse* state, and only the diff shows it). #9 SCOPE-THE-NEGATIVE — "62% of the JP
+corpus is closed" was a fact about *three hosts*, and the host column proved the *region* was never
+the thing that closed. **HONEST SELF-CAUGHT DEFECT, recorded before it was fixed:** my own 08-12
+next-run queue was titled "qiita-hosted" and named **five entries of which three were zenn.dev** —
+the host I had ruled HARD STOP four paragraphs earlier in the same note. **The queue was 40%
+dead-on-arrival and nothing but a host-column check caught it.** That is the L1.44/L1.55 shape in a
+prose artifact: a hand-off whose inputs changed underneath it between being written and being
+consumed. **Fix applied to the process, not just this instance: the next-run queue below is derived
+from the `host` column of the corpus map, and every entry carries its host.**
+
+**NEW VENUES FOUND (venue-discovery obligation — verdicts for the next seat).** `gitan.dev` **RICH**
+(C#/AWS/systematic-trading blog, 2022→live, ~monthly, the only known year-over-year JP venue survey;
+found via the calendar host column). `blog.shidokamo.com` **RICH** (DEX/CEX arb + serverless bots,
+long-form with inline code). `perp-screener.com` **THIN-BUT-OPEN** (2 posts only, but it is also a
+live *tool* — a perp screener with an Academy/Backtest section worth a separate look as a data
+surface). `tech.takibi.net` **OPEN-BUT-BROKEN LINKS** (`?p=` permalinks 404; needs an archive or
+sitemap route — do not record as dead). `coin-news.xyz` **SPA SHELL** (200 with a 114-byte body —
+OP-068's false-null class; needs the XHR route, not a re-fetch). `rarirure.rip`, `mirumi.me`,
+`yard.tips`, `pasokon.blog` **OPEN, unmined**. `agari.notion.site`, `colab.research.google.com`,
+`medium.com`, `kijitora-2018.hatenablog.com` unprobed.
+
+**DIASPORA (standing question).** The 08-12 answer stands and is now sharper: **the community did not
+move and the door did — but the door was only ever on three hosts.** The same writers are reachable
+today on their own domains, which is the *opposite* of a diaspora: platform withdrawal pushed the
+corpus toward self-hosting, where it is **more** durable and **less** governed by a crawler denylist.
+The open question for the next seat is whether that is a JP-specific artifact of Advent-Calendar
+culture (which rewards owning your own writeup) or a general fleet pattern.
+
+**NEXT RUN (in order; every entry carries its host, per the defect above).**
+(1) **Deep-forest queue, continued — all confirmed 200 to ClaudeBot this run:** `rarirure.rip`
+    「おれの脳筋BOTがやっと利益を出した話」(a bot that finally turned a profit — a *positive*
+    post-mortem, the rarer kind); `yard.tips` 「Trading Viewで人気の戦略からセンスを磨く」(popular
+    TradingView strategies — a crowding/positioning read, §L1.34 untested-alpha vein);
+    `blog.shidokamo.com` 「ビットコインをChat-GPTと一緒にトレードする」(**an OP-072 specimen: an
+    explicitly LLM-driven strategy — mine it as evidence about the contamination, not for the alpha**)
+    and 「初級botで裁量トレード」(discretionary, and discretionary mechanisms are in scope);
+    `mirumi.me` 「bot を書くためにつくって公開したもの」(published tooling → repo chain).
+(2) **`tech.takibi.net` archive route** — 3 calendar entries incl. a backtest tutorial and
+    「RustyBot」(one codebase from backtest → dry-run → live, a PROCESS find); permalinks are 404 so
+    this needs CDX/sitemap. **Do not let a broken permalink become "dead ground"** — that is exactly
+    the false-null class (OP-033/034/068/069) this fleet has now hit five times.
+(3) **`coin-news.xyz` XHR route** 「オンライン推定を用いたシステムトレード」(online/recursive
+    estimation — a genuinely under-represented family here).
+(4) **PI backfill + the construction-vs-construction screen** (carried from 08-12 item 2; still owed
+    by the funding-axis owner, not seat-blocking).
+(5) **J-Quants §13 licence read, due 2026-08-19**; `bitbank` legitimacy decision returns 08-19.
+(6) **Standing:** re-probe note.com/zenn.dev content path every run — one cheap probe, never a cached
+    verdict, and now with the knowledge that their robots.txt will lie to you.
 RESUME STEP 1 (backlog): `source_backlog_next.py --limit 6` → 6 pending technical verifications,
 **0 JP-owned**. The one with a JP component ("Foreign AI-quant RESEARCH SYSTEMS — VeighNa/vnpy.alpha,
 Qlib, **JP/KR equivalents**") had its CN half mined by the CN seat **today** (s8, 08-13); the JP half
```


---

## f4e535f8 JP miner 08-13: watchlist -- 4 candidates gated (1 QUEUE routed to axis, 3 REJECT), no new card, all trials counted

```diff
commit f4e535f8cba8483bc43cede10dd62ed94635ca72
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:00:50 2026 +0000

    JP miner 08-13: watchlist -- 4 candidates gated (1 QUEUE routed to axis, 3 REJECT), no new card, all trials counted
---
 docs/research/prospector_watchlist.md | 39 +++++++++++++++++++++++++++++++++++
 1 file changed, 39 insertions(+)

diff --git a/docs/research/prospector_watchlist.md b/docs/research/prospector_watchlist.md
index 03a053ee..9baccbd8 100644
--- a/docs/research/prospector_watchlist.md
+++ b/docs/research/prospector_watchlist.md
@@ -568,3 +568,42 @@ slots used.**
 **WATCHLIST (max 5): POC retest (hold), SFD cadence probe (hold), dvol_futures_basis_carry (hold),
 coinm_usdtm_basis_convexity_rv (hold), kr_rail_state_transition_global_leg (hold). 5/5 slots used
 — this session added NO card (one EV-reject, one measurement routed to the funding axis owner).**
+
+## 2026-08-13 — JP frontier miner s4 (deep-forest self-hosted layer): 4 candidates scored, 1 clears, 0 new cards
+
+All four were novelty-gated against the graveyard BEFORE scoring (universal duty; none redundant,
+nearest-prior similarity 0.149–0.189) and then run through the pre-registered EV gate with honest
+inputs. Verdicts, so the trials are counted rather than the survivor reported alone:
+
+| candidate | novelty | EV | p_survive | verdict | disposition |
+|---|---|---|---|---|---|
+| `venue_fee_volume_credibility` | 0.816 | **0.0058** | 0.24 | **QUEUE** | → universe-map source **102** (data-integrity axis, not a sleeve) |
+| `ofi_taker_component_dominance` | 0.851 | 0.0002 | 0.026 | REJECT (below thresh) | → `improvement_inbox.md` item 1 (feature-redundancy fact, not a trade) |
+| `option_flow_informedness` | 0.828 | 0.0002 | 0.060 | REJECT (below thresh) | → held below as an untested-alpha lead + vocabulary flag |
+| `rev_calendar_spread_iv_convergence` | 0.811 | 0.0000 | 0.013 | REJECT | → `docs/graveyard.md` (also refuted at source) |
+
+**NO NEW CARD. The watchlist stays at 5/5: POC retest (hold), SFD cadence probe (hold),
+`dvol_futures_basis_carry` (hold), `coinm_usdtm_basis_convexity_rv` (hold),
+`kr_rail_state_transition_global_leg` (hold).** The one gate survivor is a *conditioning variable*,
+not a sleeve, so it takes an axis row rather than a card slot — carding it would consume a scarce
+slot with something that can never be promoted on its own.
+
+**THE ONE LEAD HELD RATHER THAN DISCARDED — `option_flow_informedness`, flagged per the extraction
+mandate as mapping to NO entry in `CRYPTO_MECHANISMS`.** From `perp-screener.com/posts/btc-bot`
+(2025-12-04), stated as the author's reason for choosing options at all: *"「意志のある取引」が多いの
+では？"* — **option order flow carries more intent per unit notional than perp flow, because
+selecting a strike AND an expiry encodes direction, timing and magnitude simultaneously, whereas
+`BTCUSDT` gets bought on a vibe.** The desk's vocabulary has `options skew` and `derivatives
+positioning`, which are *state* variables; this is a claim about the **informedness of flow
+conditional on instrument complexity**, and it is a different quantity. Testable in principle (does
+option trade imbalance lead perp price by more than perp trade imbalance does?), and it **fails the
+EV gate today on `narrow_breadth`** — BTC/ETH options are ~2–3 independent bets — which is an honest
+rejection, not a hidden one. **Enabling change that would re-open it (L1.16a):** a materially wider
+liquid crypto option cross-section, or a construction that pools the option-flow signal across many
+perps rather than trading the options themselves. Held here, not carded, not screened.
+
+**PROVENANCE NOTE ON THE WHOLE SESSION (OP-072, new this run):** the options post's *mechanism
+analysis* is self-disclosed LLM output (*"チャッピーの解説によると"*), so it is **not** an independent
+practitioner node and must never be counted as convergence. Its *observations* — realised P&L, greeks
+snapshot, the expiry failure mode — stand. The other three sources are pre-2023 or carry no LLM
+disclosure, checked.
```


---

## cc7b8d89 JP miner 08-13: WS-013 -- 13-month JP margin dislocation + venue swaps SFD penalty for funding rate; independent venue corroborates the 1bp funding constant is a COPIED CONVENTION

```diff
commit cc7b8d8990fa59c117737481d1d5331ad891bc99
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 08:00:18 2026 +0000

    JP miner 08-13: WS-013 -- 13-month JP margin dislocation + venue swaps SFD penalty for funding rate; independent venue corroborates the 1bp funding constant is a COPIED CONVENTION
---
 docs/research/weak_signal_registry.md | 16 ++++++++++++++++
 1 file changed, 16 insertions(+)

diff --git a/docs/research/weak_signal_registry.md b/docs/research/weak_signal_registry.md
index 26b41c81..9646dd1a 100644
--- a/docs/research/weak_signal_registry.md
+++ b/docs/research/weak_signal_registry.md
@@ -385,3 +385,19 @@ honest qualifications (stated so a later reader cannot over-read this):
   - **NOT VERIFIED: that the top teams achieved positive forward correlation.** Prizes were awarded, which is not the same claim — the private leaderboard rows are unrecoverable (OP-068: XHR-loaded, never archived; the `publicleaderboarddata.zip` export returns a 200 + HTML shell). The named falsifier is the private LB score column; until it is in hand, "the space is non-empty at 15-min residualised" remains **unevidenced**, and this WS rests only on the DESIGN choice, which is a statement about G-Research's prior, not about the outcome.
 independence / DERIVES-FROM: the external half **DERIVES-FROM: NONE (checked)** — G-Research set this design in 2021-11 and the desk measured its panel breadth in 2026-08 from its own futclose panel; there is no citation path in either direction, and the desk's `panel_breadth.py` cites no external source. Genuine independent convergence on TARGET CONSTRUCTION (method), **not** on a mechanism — and per the provenance mandate convergence buys a **queue place, never a lower bar**.
 promotion-check: not a tradeable signal — a **target-construction** question with a cheap decisive test on data already held: re-run one `screen_moat` cell family with the target replaced by its cross-sectionally demeaned form, same horizons, same features, and compare the IC distributions. Both constructions are **DSR-counted trials** and the residualised cell must be logged as an ADDITIONAL trial, not swapped in silently (that would be the forking-path the screen-on-discovery duty names). Promote to hypothesis if the residualised IC distribution separates from the raw one; retire the question if it does not.
+
+### WS-013 a JP margin venue has run a +2% PERSISTENT dislocation from spot for 13 months, and the venue that fixed its predecessor by fee did it by REPLACING the penalty with a funding rate   [observations: 2 primary (same author, one year apart) + 1 internal]
+first-seen: 2026-08-13, JP frontier miner s4, `gitan.dev` 2023-12-05 and 2024-12-03 editions of the same venue survey.
+**why the pair is worth more than either post:** the same practitioner re-surveyed the same 12 venues exactly one year apart, so the diff is a **dated, primary-source venue-microstructure changelog** with no reconstruction and no vendor in between. Three of its deltas are signal.
+
+**(a) THE DISLOCATION.** 楽天ウォレット (Rakuten Wallet) margin: *"2023年11月頃から、他マーケットの現物価格と値段が乖離してきていて、+2%程度高くなっている"* — a ~+2% premium to other venues' spot appearing ~2023-11 and **still present at 2024-12**, i.e. **13 months and not closing**. The author's own read is a forward-looking risk, not a trade: *"昔のBitFlyerFXの様に、どんどん乖離が大きくなっていくようだと問題"* (a problem if it widens the way old bitFlyer FX did). Coincident and unremarked by him: the venue changed its fee schedule on **2023-12-01** to Taker **0%** / Maker **−0.01%** — a paid-to-quote structure — one month after the dislocation appears.
+
+**(b) THE MECHANISM SWAP, which is the part with transferable content.** bitFlyer's product went 2023 → 2024 from **FX with SFD** (a *penalty* levied when spot–derivative divergence exceeded 5%) to **Crypto CFD with a funding rate** (a *continuous transfer* between longs and shorts, 3×/day). A venue replaced a discrete divergence penalty with a continuous carry. And the resting balance the author reports is not market-clearing: *"大きな差が無い場合、ロングが0.010%、ショートに支払う"* — absent a large divergence, **long pays short a flat 0.010% per settlement, three times a day**, giving his working cost baseline of **long 0.07%/day vs short 0.01%/day** once the 0.04%/day position fee is added.
+**INTERNAL CONVERGENCE, AND IT IS NOT A COINCIDENCE OF ROUNDING:** 0.010% per settlement × 3/day is *numerically identical* to Binance's interest-rate component (0.01% per 8h). This seat measured on 2026-08-12 (`data/jp_funding_clamp_census.json`) that **41.6% of the owned 8h Binance panel and 68.8% of the live 812-symbol cross-section print a censoring constant**, the dominant one being `0.00010000`. **A second, unrelated venue hard-coding the same constant as its resting funding is evidence that the 1bp print is a COPIED CONVENTION rather than a measured cost of carry** — which is exactly what the clamp census concluded from the Binance side alone, now with an independent venue agreeing.
+
+**(c) THE UNEXPLAINED DISAPPEARANCE.** The 2023 edition states GMO leverage *"価格は現物価格の±0.5%の範囲で推移していることが多い"* — a quantified basis band. **The 2024 edition drops that sentence entirely** while keeping the rest of the GMO section. Either the band stopped holding or the author stopped tracking it, and the post does not say which. Logged because an unexplained disappearance from a maintained series is a question, not noise (per the extraction mandate: unexplained observations are the rawest material on a page).
+
+direction / mechanism candidate: a venue-designed asymmetric carry (short structurally cheaper) plus a negative maker fee is a **standing incentive to be short and to quote**, which is a candidate cause for a persistent one-sided premium — the same shape as the SFD-era bitFlyer premium the desk already graveyarded as `jp_sfd_boundary_game`. **Direction of causation is NOT established and the ordering is ambiguous**: the fee change (2023-12-01) *post-dates* the dislocation's appearance (~2023-11) by about a month, which is the wrong order for the fee to be the cause and is not remarked on by the author.
+honest qualifications: (1) **This desk does not trade JP venues and no JP venue axis is proposed.** The two JPY-premium families are already dead here — `jp regional premium` (bitbank IC −0.06, noise) and the wider cross-venue fiat-premium family killed 5× with kimchi, its lone survivor, itself refuted 2026-07-30 at full depth. **No L1.16a enabling change exists, so the premium itself is NOT re-opened.** (2) The +2% figure is a practitioner's eyeball estimate with no series behind it. (3) Volumes quoted are from venues the same author says report untrustworthy volume (see universe-map source 102) — **his own credibility caveat applies to his own table.**
+independence / DERIVES-FROM: **NONE (checked)** — neither edition cites anything; first-hand operator observation. Pre-2023 for edition one, no LLM-consultation marker in either (OP-072 checked). Genuine independent convergence with the desk's clamp census on the **constant**, not on the premium.
+promotion-check: **not a tradeable signal and not proposed as one.** Its value is (i) the funding-constant corroboration above, which strengthens an existing measured finding at zero cost, and (ii) a **structural prior worth carrying**: when a venue replaces a divergence *penalty* with a *carry*, the divergence stops being bounded by rule and starts being priced — so the venue's own mechanism change is a regime boundary for any basis series that spans it. Decisive test if ever wanted, on free public data: Rakuten Wallet vs GMO/Coincheck spot, daily, 2023-01→, testing whether the dislocation is (a) real, (b) dated to ~2023-11, and (c) still open. **Nobody should run it until a JP venue is tradeable here** — it is logged so the observation is not lost, per L1.28a.
```


---

## 599465cb JP miner 08-13: universe map 102 -- venue fee schedule as the conditioning variable for every volume feature (EV 0.0058 QUEUE, the session's only gate survivor)

```diff
commit 599465cb7cf60ea1dbd2227ff59f3bd7602e5575
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 07:59:37 2026 +0000

    JP miner 08-13: universe map 102 -- venue fee schedule as the conditioning variable for every volume feature (EV 0.0058 QUEUE, the session's only gate survivor)
---
 data/data_universe_map.json | 16 +++++++++++++++-
 1 file changed, 15 insertions(+), 1 deletion(-)

diff --git a/data/data_universe_map.json b/data/data_universe_map.json
index 77e8a367..0571155e 100644
--- a/data/data_universe_map.json
+++ b/data/data_universe_map.json
@@ -1114,6 +1114,20 @@
    ],
    "yield": "Reusable SHAPE, not the JP axis: test 'venue sells via API what its website gives away free' against every venue the desk pays or would pay for.",
    "added": "2026-08-12 free_data_alternatives_miner"
+  },
+  "102-venue-fee-schedule-volume-credibility": {
+   "source": "102-venue-fee-schedule-volume-credibility",
+   "url": "https://gitan.dev/?p=325 (2023-12-05) + https://gitan.dev/?p=365 (2024-12-03) | Binance fee schedule: https://www.binance.com/en/fee/schedule | Binance zero-fee/promotional campaigns: https://www.binance.com/en/support/announcement",
+   "provides": "A CONDITIONING VARIABLE FOR EVERY VOLUME-BASED FEATURE, not a price series. The mechanism, stated by a JP HFT practitioner surveying 12 venues two years running: where the taker fee is ZERO or the maker fee is NEGATIVE, wash trading is costless or profitable, so REPORTED VOLUME IS NOT A MEASUREMENT of economic activity. He gives dated evidence rather than suspicion: BtcBox volume was 'unnaturally constant regardless of price movement' until a REGIME BREAK at ~2024-05-01 after which it reads natural (~1 BTC/day); BitTrade volume 'disquieting since 2023-01, the same smell', with his own explanation -- 'fees are 0% so volume can be inflated without limit'. His diagnostic is itself the transferable artifact: NORMAL VENUES SHOW VOLUME RISING WITH VOLATILITY; a venue whose volume is flat across a large price move is reporting something other than trading.",
+   "desk_relevance": "DIRECT, and it is NOT about Japan. Binance runs ZERO-FEE PROMOTIONAL CAMPAIGNS on selected pairs (the BTC/TUSD and FDUSD families are the well-known cases) and tiered maker rebates at high VIP levels. Any cross-sectional feature built on volume, turnover, volume-share or a volume-normalised quantity across the desk's ~812-symbol perp panel is comparing promo-fee and normal-fee names as if the denominators were the same measurement. The fix is a per-symbol, POINT-IN-TIME fee-regime flag used as a conditioning variable or an exclusion -- not a new alpha, an integrity input to the ones that exist.",
+   "cost": "FREE (venue fee schedules + announcement archives are public; the JP survey is a public blog post)",
+   "status": "catalogued-unverified 2026-08-13 (JP frontier miner s4) -- NOT ingested, NOT screened",
+   "grade": "needs-verification",
+   "value": "MEDIUM-HIGH (data-integrity / conditioning; gates existing volume features rather than adding one)",
+   "ev_gate": "venue_fee_volume_credibility: EV 0.0058 p_survive 0.24 -> QUEUE (top-EV -> research); novelty 0.816, nearest graveyard prior sim 0.184. The ONLY one of this session's four scored candidates to clear the gate.",
+   "decisive_test": "Point-in-time fee regime per symbol from Binance's announcement archive, then (a) test whether volume/volatility elasticity differs between promo-fee and normal-fee names, which is the practitioner's own diagnostic, and (b) re-run any live volume-based feature with promo-fee names excluded and compare. THE LOOK-AHEAD TRAP IS NAMED IN ADVANCE: today's fee schedule applied to history is a look-ahead in the CONDITIONING variable -- the same defect class as pct_circ_now (R0289) and the RFB vintage stack, and it fails toward a FALSE NULL, the direction no gate here catches.",
+   "provenance": "SOURCE: gitan.dev (seekseek77), 'ビットコインbotterにとっての各マーケットの特徴', 2023 and 2024 editions. DERIVES-FROM: NONE (checked) -- the posts cite no paper, no repo and no other writeup; they are first-hand venue observation by an operator who trades them. Pre-2023 for the first edition and no LLM disclosure in either (OP-072 checked).",
+   "residual_gap": "The practitioner's evidence is JP venues; the Binance analogue is ASSERTED here, not measured. The first task is to establish that a promo-fee cohort exists on the desk's own panel with a recoverable point-in-time history -- if the announcement archive does not support point-in-time reconstruction, this axis is UNMEASURABLE rather than dead, and must be recorded that way."
   }
  },
  "residual_gaps_unpurchasable": [
@@ -1147,4 +1161,4 @@
  "last_free_dig": "2026-07-22T23:21:50.541800+00:00",
  "overlap_corrected": "2026-07-22T23:46:26.342668+00:00",
  "last_genuine_dig": "2026-07-26 [T1-a] kaiko"
-}
\ No newline at end of file
+}
```


---

## 17f597d9 JP miner 08-13: inbox -- OFI take-component dominance (book imbalance vs aggressor flow may be one axis) + target-distribution stationarity gap

```diff
commit 17f597d91092450e99d6127fe133505a4ae583ef
Author: Codex <codex@openai.local>
Date:   Thu Aug 13 07:58:33 2026 +0000

    JP miner 08-13: inbox -- OFI take-component dominance (book imbalance vs aggressor flow may be one axis) + target-distribution stationarity gap
---
 docs/research/improvement_inbox.md | 95 ++++++++++++++++++++++++++++++++++++++
 1 file changed, 95 insertions(+)

diff --git a/docs/research/improvement_inbox.md b/docs/research/improvement_inbox.md
index d5c606a7..392694a1 100644
--- a/docs/research/improvement_inbox.md
+++ b/docs/research/improvement_inbox.md
@@ -2179,3 +2179,98 @@ Their idiom is to simulate the trivial expression `rank(<candidate_field>)` firs
 1,387 of BRAIN's 4,367 fields are VECTOR-typed, with `vec_avg`/`vec_sum` as late reducers. The desk collapses multi-venue funding, per-level depth and per-venue OI to a scalar **at ingest**, which fixes the reduction before any hypothesis can choose it — mean vs sum vs dispersion vs max are different signals, and cross-venue *dispersion* is the one most obviously discarded. Routed as an engine idea (L1.34 §4), not a build order.
 
 **NOT APPLIED — BRAIN-hunter seat is research-frozen out of `scripts/` and `libs/`.** Items 1, 3 and the video-fetcher defect are ledgered so they are driven rather than filed here (this inbox does not drive work).
+
+## 2026-08-13 — JP frontier miner s4 (two engine items; the first is the run's best find and it is NOT a trade)
+
+### 1. BOOK IMBALANCE AND AGGRESSOR FLOW MAY BE ONE AXIS, NOT TWO — and a practitioner ran the intervention that separates them
+
+**SOURCE:** `qiita.com/blog_UKI/items/d01367ff01ffbd64c863`, 「仮想通貨ボット：BitMEXの板でスプーフィングを
+試みた話」, 2021-12-14 (仮想通貨botter Advent Calendar 2021 d15), 37 likes, **comment layer checked: 0
+comments**. **DERIVES-FROM:** 杉原 (the JP-language exposition of Cont/Kukanov/Stoikov order-flow imbalance)
++ the author's own 2018 note. Pre-2023, so **not** LLM-contaminated (OP-072).
+
+**WHAT HE DID, AND WHY IT OUTRANKS AN OBSERVATIONAL STUDY.** He built a bitFlyer HFT bot whose direction
+signal was **OFI computed from the BitMEX book** (chosen because "海外取引所のほうが価格が先行する" and
+because bitFlyer's ¥1 tick made its own book too thin to compute OFI from). He then asked whether he could
+*manufacture* the signal: regression said **~$500k of BitMEX book change moved bitFlyer ~¥100**, and since
+spoofed orders are never meant to fill, **~$5,000 of margin at 100× would suffice.** He built it and ran it.
+**It did not work — large passive orders on BitMEX did not move bitFlyer.**
+
+**THE DECOMPOSITION THAT EXPLAINS THE NULL — this is the transferable part.** Writing every quantity positive:
+```
+ΔBid = (1) new limit-buy inflow − (2) cancellation of resting buy limits − (3) market-SELL take
+ΔAsk = (4) new limit-sell inflow − (5) cancellation of resting sell limits − (6) market-BUY take
+OFI  = ΔBid − ΔAsk = (1−2−3) − (4−5−6)
+```
+His finding: **"このうち説明力として支配的なものは(3)と(6)の成行注文なのでした"** — components **(3) and
+(6), the MARKET orders, dominate the explanatory power.** The quote-side components (1)(2)(4)(5) do carry
+some, and combining them improves overall performance, **but the displayed book is not where the information
+is.** Hence the null: to move price you must actually cross, which is ordinary manipulation — taker fees plus
+an adversely-selected position, "旨味はありません".
+
+**WHY THIS MATTERS HERE, CONCRETELY.** The desk's crypto mechanism vocabulary lists **`book imbalance`** and
+**`order flow` / aggressor-side trade intensity** as separate entries, and L1.18 (ALPHA DIVERSITY) counts
+*independent* sources. If OFI's predictive content is mostly the take component, then a book-imbalance
+feature and a taker-flow feature are **substantially the same signal wearing two names** — two features, one
+bet, and a diversity count that is too high by one. That is the demeaning-floor lesson in a different
+costume: apparent independence that is an artefact of construction.
+
+**THE DECISIVE TEST IS CHEAP AND RUNS ON DATA THE DESK ALREADY HOLDS.** The depth tape and the trade tape are
+both recorded (they are the whole subject of L1.46 clock provenance). Decompose ΔBid/ΔAsk per interval into
+take (reconcilable against the trade tape by aggressor side) vs quote-side residual, then regress forward
+return on each **separately** and report the incremental R² of the quote-side component over the take
+component alone. **Both constructions are DSR-counted trials** and must be logged as such. Three outcomes,
+all useful: quote-side adds nothing → collapse the two axes into one and correct the diversity count;
+quote-side adds materially → the desk has a genuinely separate axis and now knows it; underpowered →
+UNMEASURED, and the honest answer is instrumentation.
+
+**NOT A TRADE, AND THE GATES SAY SO.** `ofi_taker_component_dominance`: **EV 0.0002 → REJECT**
+(`high_turnover_no_maker` + `crowded_known`), novelty 0.851. An HFT-horizon OFI signal is DOA for a
+latency-disadvantaged spread-taker at this equity, and the EV gate is right. **The value is as a
+FEATURE-REDUNDANCY fact and an execution-model input**, which is why it is filed here and not carded.
+
+**AND THE HARD LINE ON THE STRATEGY ITSELF:** spoofing is prohibited market conduct (JP FIEA; US CEA §6(c);
+every major venue's terms). Nothing here is implementable and nothing here is proposed. What is extracted is
+**evidence about market structure produced by an intervention** — the author's own conclusion was that the
+exercise's real purpose was *"BitMEXの板を参照するボットを殺すボットを作る"*, i.e. probing whether bots that
+read the book can be farmed.
+
+**THE VOCABULARY GAP THIS EXPOSES (flagged per the extraction mandate — a mechanism mapping to NONE of the
+desk's families is the interesting case).** His closing line — *"市場がボットで飽和すると、必ずボットを食い物
+にするボットが現れる"* ("when a market saturates with bots, a bot that preys on bots will inevitably appear")
+— is a **PREDATION / adversarial-counterparty** mechanism family. Every entry in `CRYPTO_MECHANISMS` describes
+*market state*; none asks **"is my own order pattern a farmable, recognisable signature?"** The desk has this
+lens for its own *process* (L1.32's "the adversary") but not as a *market* family. It is not idle: this desk's
+carry sleeve opens and closes on a schedule tied to funding phase and rank exit, which is precisely a
+recognisable signature. **L1.45's excitation design already randomises *how* the desk orders — so the desk has
+partially defended against a mechanism it has never named.** Naming it is free; measuring it is the open
+question.
+
+### 2. THE DESK CHECKS FEATURE-DISTRIBUTION STATIONARITY AND (APPARENTLY) NEVER CHECKS THE TARGET'S
+
+**SOURCE:** `qiita.com/pip_pip_pip_p/items/3b86e36ca536e99d26e0` (2024-12-07) — full provenance and the
+strategy-side corroboration in `docs/graveyard.md` under the `jp_mlbot_atr_limit_reversion` addendum.
+
+His observation, aimed at the most-copied ML-bot tutorial in the JP ecosystem: *"mlbotチュートリアルでは特徴量
+の分布が時間で変化しないことをチェックしていますが、似たようなことを目的変数に対して行うといいかもしれま
+せん"* — **the tutorial checks that the FEATURE distribution is time-invariant; nobody checks the TARGET's.**
+He ranks target-stationarity **② ≫ ③ simple > ④ strong**, second only to ① sufficient samples, in what makes
+a rule-based base layer usable under an ML meta-label filter.
+
+**WHY IT LANDS ON THIS DESK.** The desk carries the feature-side check (the `richman` non-stationarity score
+is in this seat's own standing brief) and `dist_shift` from capability-hunt s3 (2026-08-01, "only SHIFT may be
+wired — DRIFT is overpowered at large n"). Both are **feature-side**. A screen whose *target* distribution
+moves between train and test — forward-return vol regime, funding regime, the censoring share this seat
+measured on 2026-08-12 (68.8% → 10.7% from 2019 to 2026) — is mis-specified in a way no feature-side check
+can see, and it fails toward **a false null in a quiet regime and a false positive in a violent one**.
+
+**PROPOSED, NOT BUILT (seat is research-frozen out of `libs/` and `scripts/`):** run the existing
+distribution-shift instrument against the **target** series, per screen cell, and publish the verdict beside
+the IC. **UNMEASURED must stay a real answer** — if the shift statistic is underpowered on a cell's sample,
+it says so rather than certifying stationarity. Cost is small (the instrument exists); the failure it prevents
+is a graveyard-grade verdict issued on a target that changed underneath the split.
+
+**Verification owed before anyone acts on this:** I did **not** read `libs/` to confirm the desk lacks a
+target-side check — the seat is frozen out of that tree and a grep from a research seat proves a name exists,
+never that a code path runs (the desk's own most-repeated lesson). **The claim "the desk does not check
+target stationarity" is UNVERIFIED and is the first thing the implementing seat should falsify.**
```
