# Blueprint verification matrix

Independent check of every blueprint the principal gave on 2026-09-29, verified against the code rather than the builders' ledgers.
**Re-scored 2026-09-30 ~10:40Z under the principal's strict definition of DONE**, against the live branch `claude/llm-auto-upgrade-verify-gcjac3` at `6c8a71a4` (after #69).
The earlier scoring (4 criteria, at `adaba442`) is in git history and summarised in the re-verification log.

## Verdict rules (strict, principal 2026-09-30)

**DONE** means all seven hold, on the live branch:

| Mark | Criterion | Fails when |
|---|---|---|
| I | Implemented | the code is not on LIVE |
| W | Wired | no schedule leg, box task or money-path caller reaches it |
| A | Authoritative | its output decides nothing (advisory, shadow, report-only) |
| T | Tested | no test on LIVE exercises it |
| R | Artifact-producing | it writes no committed or box artifact, or none has ever been produced |
| D | Deployed | it lives only on a feature branch or open PR (the box pulls LIVE only) |
| C | Consistent | committed state contradicts it, it grades itself, or CI/law gate on LIVE is red |

- **PARTIAL**: some of the seven hold.
- **MISSING (branch-only)**: nothing on LIVE; the fix exists only on an unmerged branch.
- **MISSING**: nothing implements it anywhere.
- **EXCLUDED**: multi-venue or second-broker work, which the principal excluded.
- **TIME-BOUND**: only elapsed time can deliver it; the accumulating machinery is scored on the seven.

**Red CI on LIVE fails C for every row.** CI run 36701520415 on `6c8a71a4` failed: the LAW GATE reports an immutable-evaluator breach (`external_gauntlet.py` hashes to `cccb6ff6…` on LIVE against `baa3071c…` in the 09-29 signed manifest, changed by 7379cbf), and the MT5 desk suite fails. Until LIVE is green, no row can be DONE.

## Headline (strict)

| Blueprint | Items | DONE | PARTIAL | MISSING (branch-only) | MISSING | EXCLUDED | TIME-BOUND |
|---|---|---|---|---|---|---|---|
| Audit: critical sequence, named defects, 10/10 acceptance table | 43 | 0 | 27 | 10 | 3 | 1 | 2 |
| Audit: 20 implementation items + pipeline chain | 21 | 0 | 20 | 0 | 0 | 0 | 1 |
| Tier S: 15-layer table + sections 1–15 | 30 | 0 | 30 | 0 | 0 | 0 | 0 |
| Tier S: sections 16–30 + final loop | 16 | 0 | 16 | 0 | 0 | 0 | 0 |
| 16 hardening + depth priorities + admission rule | 28 | 0 | 25 | 0 | 2 | 0 | 1 |
| **Total** | **138** | **0** | **118** | **10** | **5** | **1** | **4** |

**Bottom line: 0 of 138 rows meet the strict definition.** The previous two DONEs fell:

- **D10** (evaluator drift check): 7379cbf changed `external_gauntlet.py` after the 09-29 signing, so the check it passes on is now a live breach.
- **DP5** (independent breadth): the last breadth reading is 09-16 and the dashboard 09-22, so its artifact is stale.
- **D13** (shadow.log opened per write) is correct code but cannot be DONE while CI on LIVE is red.

What stops rows reaching DONE, in order of how many rows each blocks:

1. **Red CI on LIVE** (every row): re-sign the evaluator for 7379cbf or revert it, and fix the MT5 desk suite.
2. **Nothing Tier S is on LIVE** (46 rows): PR #55 is 21 ahead and 172 behind, and merging alone reaches I, T and D only. Its only money-path authority is a withhold-only promotion door; the exchange, execution capture, constitution values and FREEZE reach no sizing or allocator code.
3. **#52 true lockbox and #53 allocator sovereignty are unmerged** (10 rows MISSING branch-only, several more PARTIAL). LIVE still sets gate 9 to the walk-forward OOS Sharpe and floors zero allocations to the venue minimum.
4. **Committed state contradicts the rules**: 40 LIVE sleeves, 24 of them banned `discovered`, 31 admission UNMEASURED, 40/40 no cost basis, 58/58 lockbox == WF OOS in `UNIVERSAL_SURVIVORS.json`, 474 certificate-truth divergences, and `certificate_truth --apply` has never run.
5. **Organs are wired but have no authority**: cost surfaces, constrained book (`FEEDS_LIVE=False`), placebo audit, identity chain, experimental budget, replication; `research_budget.json` is `authoritative:false`.
6. **Artifacts stale or never produced**: `markout.json` 09-08 with 0 matched fills, breadth 09-16, `merge_report.json` 09-23 with 55,811 of 57,538 cells unjudged, no committed JUDGING_RATE, COST_SURFACES, CERTIFICATE_TRUTH or PRODUCTIVITY_CENSUS.
7. **No fix anywhere** for: UNMEASURED-marginal and non-significant override sleeves keeping risk (CS5, D7, D9), removing dormant components (DP2), permanently green CI (DP9). The DSR variance is still the constant 0.014863, and `master` does not contain LIVE.

## Routing

- **Institutional truth discipline fixes:** items CS*, D*, AC*, I*, P1, DP2–DP4, DP6–DP10, and cross-cutting gaps 1–3, 8, 9 and 10.
- **Tier S research institution build:** items L*, T*, LOOP, H*, ADM, and cross-cutting gaps 4–7.
- No item fell outside both threads' scope.


## Re-verification log

### 2026-09-30 10:40Z: strict re-score of all 138 rows at `6c8a71a4`

The principal's audit of 7379cbf asked for DONE = implemented, wired, authoritative, tested, artifact-producing, deployed and consistent. All five sections were re-scored against LIVE at `6c8a71a4`. Result: 0 DONE, 118 PARTIAL, 10 MISSING (branch-only), 5 MISSING, 1 EXCLUDED, 4 TIME-BOUND. The per-row seven-criterion marks replace the old section tables below.

### 2026-09-30 00:30Z: Tier S batch 2 (PR #55 at `03fdd97b`)

Checked in the code. `test_tier_s_organs.py`, `tests/tiers` and `test_cycle_pricing.py` pass in a clean worktree. `check_tier_s_program.py` passes and reports 17 DONE, 22 PARTIAL, 6 BLOCKED_ON_USER and 1 BLOCKED_ON_BOX.

| Gap | Now | Evidence |
|---|---|---|
| Compute pricing could cut a leg to 0.6x (the never-reduce-mining rule) | **Fixed** | `cycle_pricing.py` sets `FLOOR = 1.00`, and a test pins it |
| `grammar.json` had no reader (T22, H14) | **Fixed** | `grammar_bias.bias()` is read by `expression_factory.py:90`, `alpha_evolution.mutate/random_expr` and `alpha_grammar` |
| Broken-relationship residuals relabelled `range_reversion` | **Fixed** | `tier_s.py:2036` emits `cross_asset_residual` on the target; info and network hits emit `lead_lag` |
| Cross-science hits collapsed onto existing families (H13) | **Fixed** | They drain through `expression_factory` as `cross_science:<lab>`, with conversion counted per lab |
| `falsify_first` gene ignored | **Fixed** | The `falsify_order` allele now ranks which candidates a genome spends rows on (`tier_s.py:1120`), and a test proves the ranking changes |
| `SELF_MODEL_DOCKET` unread (T29) | **Fixed** | `implementer._self_model_rows` feeds intake |
| `matched_fills_10` resolver could never resolve (T20) | **Fixed** | The resolver falls back to `live_mean_r`, which the evidence builder now writes (`tier_s.py:1430`) |
| REJECTED contracts had no consequence (ADM) | **Partly fixed** | Covered in the first bullet below |
| Six new hourly legs had no contract | **Fixed** | Contracted in `tier_s_program.json`, and the checker passes |

Still short:

- **Admission teeth are thin.** `AUTHORITY.json` is written every hour. A REJECTED verdict now suspends steering, but only two organs have a consumer that checks `suspended()`: `market` in `cycle_pricing` and `grammar` in `grammar_bias`. An organ is suspended only when *every* layer it owns is REJECTED. The baseline is the layer's own earliest readings, not a control arm.
- **No money-path authority (Priority 1).** The builder reports these as blocked by the permission filter:
  - the promoter honouring FREEZE;
  - `pf_allocator` clearing the exchange;
  - online FDR gating certificates;
  - a replication MISMATCH blocking promotion;
  - money-path code reading the constitution;
  - `may()` callers.
- **Self-grading is unchanged.**
  - Traps and the Red Queen still run against the reference validator, and traps are not blind.
  - Architecture adoption is still judged on the training suite.
  - Formal conformance is still a keyword grep.
  - The meta-benchmark still has 132 cases.
- **Scope gaps remain.**
  - The world model is price-only.
  - MAP-Elites now keys on 12 axes (was 5; not re-audited).
  - Ancestry is single-parent.
  - Rank is descriptor-only.
  - Execution capture never reaches `pf_allocator`.
  - The digital twin is not a shadow desk.
  - Chaos never kills processes.
  - Lineage is post-hoc.
- **Not live.** Still PR-only: CI is not green, and there is no box artifact.

Row verdicts for T20, T22, T29, H13, H14 and ADM stay PARTIAL until #55 is merged and a box run is evidenced. Their wiring gaps above are closed.

### 2026-09-30 00:45Z: Tier S batch 3, self-grading (PR #55 at `d5bb50d6`)

Checked in the code. The organ and kernel tests pass. I ran `tier_s.production_immune()` myself in a clean worktree.

| Gap | Now | Evidence |
|---|---|---|
| Traps and Red Queen scored a toy validator | **Fixed** | `production_immune` hands blind, hash-named dockets to the real `run_gauntlet` certifier. The Red Queen uses the same path. |
| Meta-benchmark had 132 cases, not thousands | **Fixed** | `traps.py` has 17 kinds × 150 = 2,550 sealed cases, with new placebos (information delay, timestamp scramble, sign reversal, spread perturbation, label randomisation) and 4 positive controls. 4 fill, universe, factor and stale-price kinds cannot be expressed to the certifier and are counted apart. |
| Test invention used only the toy validator | **Fixed** | `test_invention.invent_from` now learns from the cases that fooled the production certifier. |
| Architecture adoption judged on the training suite | **Fixed** | Validator challengers are re-scored on the sealed suite before adoption (`REJECTED_ON_SEALED` otherwise). |
| Traps not injected blind into the live research stream | **Open** | The builder says it waits on a promoter trap registry. |
| Formal conformance is a keyword grep | **Open** | Not touched in this batch. |
| FREEZE and `power_alarm` have no consumer | **Open** | Nothing outside `tier_s.py` reads either. |

**New critical finding (reproduced):** the production certifier has **zero power**. It judged 2,100 expressible cases and rejected every trap (immune score 1.0). It also rejected all 600 genuine positive controls (power 0.0), including the strong AR(0.25) edge.

For the genuine controls, `deflated_sharpe` is the only failing gate on 351 of 600, and it fails on all 600. The cause is the constant variance of Sharpes, 0.014863, against a measured value near 0.0008. Until the DSR variance is measured rather than fixed, no new genuine edge can pass the ten gates. This belongs to the institutional thread's DSR item (CS1/I3). #52 still carries the constant in `effective_trials.py:309` and `gate_policy.py:84`.

### 2026-09-30 00:55Z: Institutional engineering batch (PR #64 at `3bf0886c`)

Checked in the code. The four new test files pass (24 tests) in a clean worktree.

| Gap | Now | Evidence |
|---|---|---|
| Cost surfaces were spread × hour only (I7, CS2) | **Built, unconsumed** | `cost_surfaces.py` builds instrument × session × size × vol × direction × order-type surfaces from real fills and runs as an hourly leg. No sizing, admission or gauntlet code reads `COST_SURFACES.json`; the organ itself lists its unadopted consumers. Latency and adverse selection are not surfaced. With 0 matched fills, the surfaces have no data yet. |
| MT5-FrontierAudit had no installer and swallowed failures | **Fixed** | `run_frontier_audit.cmd` exits 1 when any organ fails. `install_frontier_audit_task.ps1` is idempotent, and `Adopt-And-Seal.ps1` registers the task if it is missing. |
| `shadow_forward.py` opened shadow.log at import | **Fixed** | The log is opened per write, and a test covers it. |
| Judging capacity: no measured drain (I8, DP4) | **Partly fixed** | `JUDGING_RATE.json` publishes verdicts/hour, the backlog, the creation rate and the time to drain. Judge workers come from measured free cores and are applied through the env file the gauntlet launchers read. There is no box reading yet, so the drain is unproven. |
| 14 hourly legs with no layer | **Fixed** | `libs/research/layers.py` |

Still short:

- **The softened gate is still there.** Commit `3bf0886c` carries the "box-state fences read UNMEASURED off the box" change. Off the box, `check_certificate_truth.py` now exits 0 while the 474 divergences stay unmigrated.
- **Cost surfaces need a consumer.** Admission and sizing must read them, and latency and adverse selection must be added.
- **The judging drain needs evidence.** One box reading of `JUDGING_RATE.json` with creation ≤ judging is required.
- **Not live.** The PR is not merged and CI is not green.

### 2026-09-30 01:10Z: Tier S batch 4 (PR #55 at `ab404034`)

Checked in the code. The organ, kernel and pricing tests pass (80). `check_tier_s_program.py` reports 20 DONE, 22 PARTIAL, 3 BLOCKED_ON_USER and 1 BLOCKED_ON_BOX.

| Gap | Now | Evidence |
|---|---|---|
| Verifiers had no promotion authority (replication, FDR, FREEZE) | **Fixed on the promotion door** | `promoter.tier_s_block` runs beside `blind_review_veto` in both lanes (`promote_generic`, `main`). A replication MISMATCH, online FDR over budget, or a production-judged immune DROP withholds a new live row. Each block is ledgered and billed as rail `tier_s_evidence_block` via `missed_growth`. It fails open when the module errors, and a toy-validator FREEZE carries no authority. |
| Firewall `may()` had no callers | **Fixed** | `promotion_authority` checks every read and write through `firewall.may("promoter", …)`. |
| Admission baseline was the layer's own history | **Fixed** | `control_arm.py` holds out a hash-assigned 20% control arm, compared with Welch's t. `cycle_pricing` holds control legs out of the market's steering. |
| Suspension applied to two consumers only | **Fixed** | `suspended()` is now checked at every steering consumer: market, grammar, self_model, failure_memory, red_queen, topology, genomes, predictions, frontier, online_fdr, immune and twin. |
| World model was price-only | **Partly fixed** | `world_macro.py` adds rates, credit, vol, dollar, inflation, liquidity, carry and CFTC positioning as daily nodes through the factory's own field catalogue. Flows are UNMEASURED because no dataset exists. |
| Ancestry was single-parent; rank was descriptor-only | **Fixed (lineage)** | `hypothesis_graph` has multi-parent lineage, and ancestry novelty now prices compute. |
| Formal conformance was a keyword grep | **Fixed** | `conformance.py` parses the gateway's syntax tree, and the power alarm and conformance findings reach the implementer. |

Still short:

- **Allocator side of the money path.**
  - `pf_allocator` does not clear the Opportunity Exchange.
  - Money-path code does not read the constitution's thresholds.
  - Execution capture does not reach `pf_allocator`.
- **Traps are not injected blind into the live stream** (waiting on a promoter trap registry).
- **Remaining scope gaps:**
  - The digital twin is not a shadow desk.
  - Chaos never kills processes.
  - Trade lineage is still rebuilt after the fact rather than stamped at order time.
  - There is no flows dataset.
- **The certifier has zero power** (see batch 3). The new promotion door only ever withholds, so no new certificate reaches it until the DSR variance is fixed.
- **Not live.** Not merged, CI not green, and no box run evidenced.

### 2026-09-30 03:20Z: institutional rows on the live branch after #65 (merge `36f91d63`)

#65 landed #54, #57, #58, #60, #61, #62 and #64. #52 (lockbox) and #53 (allocator sovereignty) are **not** on the live branch.

What I checked:

- **Tests.** The test files of 16 new or changed organs (106 tests) pass on a clean worktree of the live branch.
- **Fences.** `check_certificate_truth`, `check_productivity_census` and `check_birth_properties` all exit 0 off the box.
- **Wiring.** I found each organ's scheduler and every caller of its output.

**Moved forward (code landed, scheduled, tested):**

| Item | Organ | Authority |
|---|---|---|
| I1 research identity | `identity_chain.py` + `libs/research/trade_identity.py` (hourly) | Report: it audits the chain, and fills are not yet stamped with it |
| I9 / CS9 effective breadth | `libs/research/independence_graph.py` + `alpha_rank.py` (hourly) | Feeds `factory_contracts` → research budget |
| I11 factory contracts | `factory_contracts.py` (hourly) | **Consumed** by `cycle_pricing` (compute) |
| I15 independent verifier | `independent_verifier.py` + `libs/validation/independent_replica.py` (FrontierAudit, daily) | Report |
| I16 placebo / adversarial | `placebo_audit.py` (hourly) | Report: no consumer |
| I17 live attribution posterior | `live_calibration_posterior.py` (hourly) | **Consumed** by `credit_assignment` and `bandit` (research priors) |
| I20 forward evidence | `forward_evidence_tracker.py` (hourly) | Report (TIME-BOUND) |
| I6 risk as constraints inside E[log W] | `libs/portfolio/constrained_elog.py` + `constrained_book.py` (hourly) | **Shadow**: `FEEDS_LIVE = False`, and nothing on the money path reads it |
| I18 experimental sleeve | `experimental_budget.py` (hourly) | **Shadow**: the separated book is computed, but the overrides still sit in the institutional book |
| I19 redundancy / DR | `ops_redundancy.py` (hourly) + `dr_drill.py` (daily) | Report: no standby or failover; `dr_drill.py` has no test |
| I7 cost surfaces | `cost_surfaces.py` (hourly) | Report: no consumer |
| I8 judging | `JUDGING_RATE.json` + measured workers | Wired; drain unproven on the box |
| I14 CI | Local law gate 38/38; root failures 166→14, desk failures 146→57 | Not fully green |

**Unchanged on the live branch:**

- **CS1/I2.** `external_gauntlet.py:2500` still writes `lockbox_sharpe = wf_oos`, because #52 has not merged.
- **CS1/I3.** The DSR variance is still the constant 0.014863 (`effective_trials.py:309`, `gate_policy.py:84`). The certifier has zero power (batch 3). The audit ledger now *measures* this cost (`833c18a4`) but does not fix it.
- **CS3/I5.** The min-lot and gold floors still override a zero allocation, because #53 has not merged.
- **CS4/I4.**
  - The "restore the fences" commits landed, but off the box `check_certificate_truth` still exits 0 with `SNAPSHOT`. That is 474 fatal divergences: 48 banned certificates, 45 banned clocks and 357 unbacked clocks.
  - The hourly leg never runs `--apply`, and nothing in the repo runs `--require-state` for this fence. So the migration is still a manual one-off, and nothing enforces it.
  - The committed `sleeves.json` still has 40 LIVE rows, 24 of them banned `discovered`.
- **CS5/D7.** UNMEASURED marginal admission still keeps capital. No change.
- **CS10/I10.** `research_budget.json` still has `authoritative: false`.
- **D15.** No master sync mechanism.

**Principal conflict to surface:** I6 and CS7 ask for margin and survival constraints to sit above aggressiveness preferences. CLAUDE.md records P1 and P13 as REFUSED under the never-reduce-aggressiveness order, and `constrained_book` is held as a shadow for that reason. The 2026-09-29 blueprint explicitly asks for the opposite, so this is the principal's call, not a builder's.

## Cross-cutting gaps as of `adaba442` (still open unless the headline above says otherwise)

1. **Nothing is merged or green.**
   - The lockbox, lifetime trials, fail-closed costs (#52), allocator sovereignty (#53), judging speed (#57), CI (#58) and all of Tier S (#55) are PR-only.
   - #52 and #53 each rewrite `IMMUTABLE_MANIFEST.json`, so they will conflict.
2. **The committed state has not been migrated.** Every branch still has:
   - 58/58 certificates where lockbox Sharpe equals walk-forward OOS Sharpe;
   - 40/40 LIVE sleeves marked "no cost basis";
   - 24 banned `discovered` sleeves still LIVE;
   - 31 LIVE sleeves with UNMEASURED marginal admission, still holding risk;
   - 7 principal overrides.
   Also, `check_certificate_truth.py` exits 2 on the live branch with 474 fatal divergences.
3. **CI is turned green by softening the gates, not by fixing what they check.** #52–#58 make the productivity-census and certificate-truth fences pass as UNMEASURED/SNAPSHOT off the box. That hides the divergence the gate exists to catch.
4. **Tier S has no authority.** Nothing it writes reaches sizing, admission, certificates or orders; its own docstring says so.
   - The FREEZE verdict is unconsumed, and it already reads FREEZE at 0.898 against a 0.9 floor.
   - The Opportunity Exchange is never read by `pf_allocator`.
   - Online FDR does not gate anything, even though 24% of certificates are over budget.
   - Replication MISMATCH blocks nothing.
   - The constitution and the firewall's `may()` have no callers.
   The only real consumers are compute pricing (weight 0.15) and the hypothesis compiler.
5. **Tier S claims consumers that do not exist.**
   - No code in `expression_factory` reads `grammar.json`.
   - The genome's `falsify_first` gene is ignored.
   - `SELF_MODEL_DOCKET` is not the docket the implementer reads.
   - Broken-relationship residuals are relabelled `range_reversion`.
   - Cross-science hits are mapped back onto existing families.
6. **Several Tier S checks grade themselves.**
   - Planted traps and the Red Queen score a re-implemented toy validator, not the production gauntlet.
   - Architecture adoption compares the challenger's score on its training suite with the incumbent's sealed score.
   - The formal "conformance" check is a keyword grep.
   - The meta-benchmark has 132 synthetic cases, not thousands.
   - The review panel's `matched_fills_10` resolver can never resolve.
7. **The admission rule has no teeth.** It checks that a contract exists. A REJECTED verdict has no consequence, the metrics count activity rather than gain against a baseline, and six new hourly legs in #55 carry no contract.
8. **"0 DORMANT" (#54) is mostly a relabel.** The old DORMANT tags were detector misses on legs that already ran. Only two organs were newly wired, 52 rows are still PARTIAL, and MT5-FrontierAudit has no installer and ends with `exit /b 0`.
9. **The judging debt is not being drained.**
   - 55,811 of 57,538 docket cells are unjudged.
   - The last committed dashboard shows 0 verdicts/day.
   - About 1,032 new hypotheses/day are created, so the debt is growing.
   - #57 speeds up cell builds but shows no measured drain.
10. **Validation defects not fixed in any branch:**
    - The DSR variance is still the constant 0.014863.
    - `research_budget.json` is still `authoritative: false`.
    - The lockbox runs in-process; `LockboxService.evaluate(frozen)` has no caller in the certificate path.
    - #53's sovereignty can be switched off with a file.
    - There is no budgeted experimental sleeve for principal trades.
    - The research identity lacks data hash, PIT cutoff, code commit, cost version and seed, and fills still join by sleeve name.
    - Cost surfaces are spread×hour only.
    - There is no standby or failover, and backups are unencrypted.
    - master is about 240 commits behind the deployed branch.

## A1 — Audit critical sequence (CS), named defects (D), 10/10 acceptance table (AC)

LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `6c8a71a4`. The merges on LIVE are #50, #51, #56, #59, #63, #65 (which carries #54, #57, #58, #60, #61, #62 and #64), #69 and #66 (to master). #52 (true lockbox), #53 (allocator sovereignty) and #55 (Tier S) are **not** on LIVE: LIVE has no `libs/tiers/`.

Checked on LIVE:

- **CI.** The ci run 36701520415 on `6c8a71a4` concluded **failure**.
- **Evaluator drift.** `IMMUTABLE_MANIFEST.json` was signed at 2026-09-29T23:15Z. It records `external_gauntlet.py` = `baa3071c220e9ce2`, but the LIVE file hashes to `cccb6ff611845474` (changed in 7379cbf). The other 17 sealed files match.
- **Committed state.** `sleeves.json` has 40 LIVE rows: 24 of them `discovered` (banned), 31 with admission `UNMEASURED` at 0.005882, 40/40 with `artifact.ok` false, and 7 with `principal_override`. `UNIVERSAL_SURVIVORS.json` shows 58/58 with lockbox == WF OOS (swept 2026-09-16).

Mark columns (I W A T R D C): Implemented, Wired, Authoritative, Tested, aRtifact, Deployed on LIVE, Consistent.

### Critical sequence

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| CS1 | True reserved lockbox; re-certify every survivor | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `scripts/external_gauntlet.py:2526-2527` gate 9 = `lockbox_sharpe: round(wf_oos,4)`; `reports/UNIVERSAL_SURVIVORS.json` 58/58 lockbox==WF | Merge #52 (audit-p0-true-lockbox). Re-sign the manifest. Box re-certifies every survivor under v3, and a committed v3 canon follows | INST |
| CS2 | Unmeasured costs fail closed (swap, instrument execution) | PARTIAL | ✓✓✗✓✗✓✗ | `external_gauntlet.py:2571` swap_cost except → `passed: True, UNMEASURED` (fails OPEN). `research/cost_surfaces.py` is an hourly leg (`hourly_cycle.py:849`), tested by `test_cost_surfaces.py`, and nothing reads `COST_SURFACES.json` | Fail-closed swap/cost (#52/#53 not merged). A consumer of the cost surfaces in admission/sizing. A committed surfaces artifact. Surfaces from fills (0 matched) | INST |
| CS3 | Allocator sovereignty: zero→no order; below-min→skip | MISSING (branch-only) | ✗✗✗✗✗✗✗ | No `allocator_sovereign` or `implementable_lot` on LIVE. `mt5desk/decision_core.py:329` floors at `min_lot()` | Merge #53. Drop the file-switch revert. Box evidence of a zero allocation giving no order | INST |
| CS4 | Certificate-truth migration; banned discovered physically absent | PARTIAL | ✓✓✗✓✗✓✗ | `research/certificate_truth.py` hourly `--once` (`hourly_cycle.py:3965`), never `--apply`. The box fence `run_law_gate.py:449 --require-state` runs via `install_law_gate_task.ps1` rotation. `test_certificate_truth.py` | Run `--apply` (a manual one-off). Commit `CERTIFICATE_TRUTH.json`. Committed stores still hold 24 banned LIVE sleeves and 44/58 survivor rows naming `discovered` | INST |
| CS5 | No LIVE sleeve with UNMEASURED marginal indefinitely | MISSING | ✗✗✗✗✗✗✗ | `research/promoter.py:1331` "not a refusal … risk already held" is kept. 31/40 LIVE rows are UNMEASURED | A time bound or quarantine rule in the promoter, a test, and a committed demotion | INST |
| CS6 | Law gate + MT5 money-path CI green on clean machine | PARTIAL | ✓✓✗✓✗✓✗ | `.github/workflows/ci.yml:52,60,68` (law gate, bug-class ruff, money-path). Run 36701520415 @6c8a71a4 **failure**. #69 merged on red | Green CI. Make CI actually block merges. Fix the evaluator drift (D10) | INST |
| CS7 | Margin/survival above aggressiveness | PARTIAL | ✓✓✗✓✗✓✗ | `research/pf_allocator.py:3508` margin clause armed only if `data/MARGIN_CLAUSE_ENABLED` exists, which is absent on LIVE. `test_margin_use_reaches_the_envelope.py`. The gateway heat check is a tripwire (`gateway.py:4044/4212`) | Arm it by default (#53, principal conflict with P13 REFUSED). A binding gateway gate. An artifact showing the clause bind | INST |
| CS8 | Attack the 55k judging backlog, not the generator | PARTIAL | ✓✓✓✓✗✓✗ | `mt5desk/build_memo.py` (#57) is used by `family_exit_operated.py`. `research/judging_throughput.py` is an hourly leg (`hourly_cycle.py:961`) that sets judge workers. Tests: `test_judging_speed_equivalence.py`, `test_judging_rate.py` | `JUDGING_RATE.json` is not committed. `merge_report.json` (2026-09-23) still shows 55,811 unjudged against capacity 500. No drain evidence | INST |
| CS9 | Measure effective independent breadth | PARTIAL | ✓✓✗✓✓✓✗ | `research/alpha_breadth.py` hourly (`hourly_cycle.py:859`) and `libs/research/independence_graph.py` feed `factory_contracts` → `cycle_pricing` (compute only). `test_alpha_breadth_factory.py`, `test_independence_graph.py`. `data/effective_breadth.jsonl` last row 2026-09-16, eff 2.057 of 160 | Breadth does not reach sizing or admission. The artifact is 2 weeks stale. No tail-dependence or ancestry axes on LIVE (topology is #55-only) | TS / INST |
| CS10 | Research-budget allocation authoritative | PARTIAL | ✓✓✗✓✓✓✗ | `hourly_cycle.py:500` `cycle_pricing.applied_budget`, `:510` `research_budget.budget_s`. `tests/alpha_factory/test_research_budget.py`, `test_cycle_pricing.py`. `data/research_budget.json` (2026-09-23) `"authoritative": false` | Prices must actually move leg seconds, with `authoritative: true` and evidence | TS |
| CS11 | Independent broker/data/execution domain | EXCLUDED | ––––––– | — | Multi-venue excluded by user | — |
| CS12 | Accumulate untouched forward/live evidence | TIME-BOUND | ✓✓✗✓✓✓✗ | `research/shadow_forward.py` (box task). `forward_evidence_tracker.py` is an hourly leg (`hourly_cycle.py:879`), tested by `test_forward_evidence_tracker.py`. `forward_verdict` is committed per row in `sleeves.json` | The forward verdict does not gate LIVE: the `xau_m5_anti_breakout_overlap` override is LIVE with `significant:false`. `FORWARD_EVIDENCE` is not committed | INST |

### Named defects

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| D1 | lockbox_sharpe = wf_oos (58/58 certs equal) | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `external_gauntlet.py:2527`. `UNIVERSAL_SURVIVORS.json` 58/58 equal | Same as CS1 | INST |
| D2 | Fixed DSR n_trials=597 / var 0.014863 | PARTIAL | ✗✓✓✓✓✓✗ | `policy/gate_spec.yaml:70` `fixed_variance_of_sharpes: 0.014863`, read by `research/effective_trials.py:129`. `test_effective_trials.py`, and `test_the_trial_charge_is_fixed_and_never_taxes_breadth.py` pins the constant. Survivors: 37×597, 20×203, 1×3001 | A measured variance of Sharpes (the certifier has 0 power, per batch 3). Lifetime/correlated trial count (#52 branch-only) | INST |
| D3 | swap UNMEASURED → passed | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `external_gauntlet.py:2571` `passed: True, measured: False` | Merge the #52 fail-closed basis. A broker-measured swap | INST |
| D4 | sleeves.json 40 LIVE all artifact.ok=false "no cost basis" | MISSING (branch-only) | ✗✗✗✗✗✗✗ | 40/40 LIVE `artifact.ok` false in committed `data/sleeves.json`. No `cost_basis_of` on LIVE | Merge #53. The box demotes, and a committed `sleeves.json` shows it | INST |
| D5 | decision_core min-lot on zero allocation + gold minimum floor | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `decision_core.py:329` `floor = min_lot()`. The gold floor is kept | Same as CS3 | INST |
| D6 | Banned 'discovered' still in sleeves/certificates/clocks | PARTIAL | ✓✓✓✓✗✓✗ | `promoter.py:569` `retire_banned` is called at `:1851`. `data/banned_families.json` bans `discovered`. `test_family_policy.py:64-115` | The committed `sleeves.json` still has 24 LIVE `discovered` rows (no `restored_at`). The certs and clocks are unmigrated. A `family_parole` escape exists | INST |
| D7 | 31 LIVE with UNMEASURED marginal admission | MISSING | ✗✗✗✗✗✗✗ | 31/40 LIVE `admission.status: UNMEASURED` at 0.005882. `promoter.py:1331` keeps the risk | Same as CS5 | INST |
| D8 | 7 principal overrides | PARTIAL | ✓✓✗✓✗✓✗ | `research/experimental_budget.py` hourly leg (`hourly_cycle.py:878`), `test_experimental_budget.py`. `SEPARATE_EXPERIMENTAL_BOOK = False` (docstring l.28) | Separated book not fed. Budget UNDECLARED (no `data/experimental_budget.json`). No committed `experimental_ledger.jsonl` or `EXPERIMENTAL_BUDGET.json`. 7 overrides still LIVE | INST |
| D9 | Non-significant forward verdict LIVE under override | MISSING | ✗✗✗✗✗✗✗ | `sleeves.json`: `xau_m5_anti_breakout_overlap` LIVE, `seq_lower_bound −0.343`, `significant:false`, `principal_override` set | Any rule that retires or quarantines a non-significant override | INST |
| D10 | Law gate: immutable-evaluator drift | PARTIAL (regressed from DONE) | ✓✓✓✓✓✓✗ | `scripts/check_immutable_evaluator.py` is in the law battery (`run_law_gate.py:162`, CI `ci.yml:52`), tested by `test_check_immutable_evaluator_wall.py`. The committed manifest records `external_gauntlet.py` = `baa3071c…`, but LIVE hashes to `cccb6ff6…` (changed in 7379cbf after the 09-29 23:15Z signing). CI failed @6c8a71a4 | The principal re-signs the manifest, or 7379cbf's judge change is reverted | INST |
| D11 | Law gate: productivity-census evidence | PARTIAL | ✓✓✓✓✗✓✗ | `scripts/check_productivity_census.py` at `run_law_gate.py:187` (portable, UNMEASURED passes) and `:454` (`--require-state`, box) | `reports/PRODUCTIVITY_CENSUS.json` is not committed on LIVE. The off-box pass is a relaxation | INST |
| D12 | Law gate: certificate-truth | PARTIAL | ✓✓✓✓✗✓✗ | `scripts/check_certificate_truth.py:69` SNAPSHOT early return rc0 off-box. Box `--require-state` at `run_law_gate.py:449` | The 474 fatal divergences remain in the committed stores. No committed `CERTIFICATE_TRUTH.json` | INST |
| D13 | shadow.log test-collection failure | PARTIAL (red CI on LIVE) | ✓✓✓✓✓✓✗ | `research/shadow_forward.py:41,396` opens the log per write, not at import (#64 via #65). `test_shadow_forward_log_lazy.py`. The box log `logs/shadow.log` | — (the CI red is from D10, not this) | INST |
| D14 | Ruff/MyPy excluding desks/mt5 | PARTIAL | ✓✓✓✗✗✓✗ | `pyproject.toml:120` exclude includes `desks/mt5`. `ci.yml:60` and `ops/gates.sh:69` run bug-class ruff (E9,F63,F7,F82) on desks/mt5 | Full ruff and mypy over desks/mt5. No test pins the scope. CI is red | INST |
| D15 | master vs deployment branch divergence (241 commits) | PARTIAL | ✓✗✗✗✗✓✗ | #66 `116573b46` "Make master carry the tree the desk deploys" is a one-off (master `cbc4ebde4`). LIVE is already 22 commits past master (4489 behind by history) | A recurring sync job or release-promotion rule, plus its test and artifact | INST |
| D16 | Research-budget allocator authoritative:false | PARTIAL | ✓✓✗✓✓✓✗ | Same as CS10 | Same as CS10 | TS |

### 10/10 acceptance conditions

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| AC1 | Every cert has truly independent dev/OOS/lockbox | MISSING (branch-only) | ✗✗✗✗✗✗✗ | See CS1/D1 | A v3 lockbox on LIVE and re-certified certs | INST |
| AC2 | Every trial ever contributes to selection-bias accounting | PARTIAL | ✗✓✓✓✓✓✗ | See D2. `online_fdr` is absent on LIVE (#55) | Lifetime/correlated trial ledger feeding DSR. Online FDR gating admission. A measured variance | INST/TS |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `libs/tiers/bitemporal.py` is not on LIVE (#55 unmerged) | Merge the PIT audit, make it gate the data certs use, and render verdicts | TS |
| AC4 | Spread+commission+swap+slippage+impact+latency from reality | PARTIAL | ✓✓✗✓✓✓✗ | `mt5desk/markout.py` hourly (`hourly_cycle.py:855`), `test_markout.py`. `reports/markout.json` at 2026-09-08 has `usable:false`, `n_matched 0`. `fill_surface.py`, `cost_surfaces.py` | The costs do not reach the capital gate (see CS2). No impact/latency. Swap fails open. The artifact is 3 weeks stale | INST |
| AC5 | One sovereign optimizer; 0 exposure = 0 position | MISSING (branch-only) | ✗✗✗✗✗✗✗ | See CS3. 7 overrides bypass | Merge #53. Put the overrides into a separate budget | INST |
| AC6 | Ruin/margin/corr/tail constraints not overridable downstream | PARTIAL | ✓✓✗✓✗✓✗ | See CS7. `constrained_book.py` hourly, `FEEDS_LIVE = False` (`hourly_cycle.py:4879`) | Feed the constrained book live. Arm the margin clause. Make the gateway gate binding (principal conflict) | INST |
| AC7 | Signal→decision→order→fill→markout measured | PARTIAL | ✓✓✗✓✓✓✗ | `mt5desk/gateway.py:888` `_record_decision` with `intent_id` (`:957`). `data/order_intents.jsonl` is committed. `identity_chain.py` hourly (`hourly_cycle.py:851`) is report-only | The markout join is at 0 matched. Nothing decides on the chain | INST/TS |
| AC8 | Many independent mechanisms, not clones | PARTIAL | ✓✓✗✓✓✓✗ | See CS9. Eff breadth 2.06/160. 24 LIVE rows are one banned family | Breadth is measured, not achieved, and does not steer capital | TS |
| AC9 | Discovery ≤ validation capacity; negligible backlog | PARTIAL | ✓✓✓✓✗✓✗ | See CS8 | A committed drain reading with creation ≤ judging | INST |
| AC10 | Green deterministic CI/release on clean hardware | PARTIAL | ✓✓✗✓✗✓✗ | See CS6/D10/D14. CI failure @6c8a71a4 | A green run. CI blocks merges | INST |
| AC11 | One source of truth for cert, clock, sleeve, allocation | PARTIAL | ✓✓✗✓✗✓✗ | See CS4/D12 | Run the migration. Zero fatal divergences in committed stores | INST |
| AC12 | Long forward/live history with attribution and drift | TIME-BOUND | ✓✓✓✗✗✓✗ | `research/drift_monitor.py` in `daily_cycle.py:377`, read by the `pf_allocator.py:3251` crisis overlay (`reports/DRIFT.json`). `shadow_forward`, `forward_verdict` | No drift_monitor test. `DRIFT.json` is not committed. The non-significant override stays LIVE (D9) | INST |
| AC13 | Research methods compete experimentally | MISSING (branch-only) | ✗✗✗✗✗✗✗ | `red_queen`, `meta_benchmark`, `researcher_market` are absent on LIVE (#55) | Merge Tier S. Adoption must be authoritative, not "always PROPOSE" | TS |
| AC14 | Second machine/data/broker; recovery tested | PARTIAL (broker part EXCLUDED) | ✓✓✗✓✗✓✗ | `libs/ops/backup.py` (`tests/ops/test_moat_backup.py`). `scripts/dr_drill.py` via `ops/run_frontier_audit.cmd` (no test). `ops_redundancy.py` hourly (`hourly_cycle.py:879`), `test_ops_redundancy.py` | No committed restore-drill artifact. No standby or failover. No dr_drill test | INST |
| AC15 | Reproduce any trade/cert from hashes alone | PARTIAL | ✓✓✗✓✗✓✗ | `libs/research/trade_identity.py` + `tests/research/test_trade_identity.py`. `identity_chain.py` hourly audit | Fills are not stamped with the identity. There is no end-to-end experiment_id and no committed chain artifact | TS |

Counts: DONE 0 / PARTIAL 27 (D13 held back by red CI) / MISSING 13 (10 branch-only) / EXCLUDED 1 / TIME-BOUND 2 (43 rows; AC14 counted PARTIAL, with its broker part excluded)

### Top gaps

- **The three P0 money-path fixes are not on LIVE.** The true lockbox (#52), allocator sovereignty (#53) and cost fail-closed are missing, so 10 rows are MISSING only because their fix is off LIVE: CS1, CS3, D1, D3, D4, D5, AC1 and AC5, plus AC3 and AC13 via #55.
- **LIVE CI is red at 6c8a71a4.** `external_gauntlet.py` was edited in 7379cbf after the 09-29 manifest signing. That turns D10 from DONE into PARTIAL. #69 merged on red, so CI does not block.
- **Committed state contradicts the rules.** It has 24 banned `discovered` LIVE, 31 UNMEASURED-marginal LIVE, 40/40 with no cost basis, 58/58 lockbox==WF and 474 cert-truth divergences. The migration (`certificate_truth --apply`) has never been run or committed.
- **No rule removes UNMEASURED-marginal or non-significant override sleeves** (CS5, D7, D9). The experimental book is a shadow (`SEPARATE_EXPERIMENTAL_BOOK = False`) with an UNDECLARED budget.
- **The report organs from #65 run but decide nothing.** Cost surfaces, the constrained book (`FEEDS_LIVE=False`), the identity chain, placebo and experimental budget have no money-path consumer. `research_budget.json` stays `authoritative:false`, and the margin clause is opt-in (file absent).
- **Key artifacts are stale or uncommitted.** `markout.json` (09-08, 0 matched), `effective_breadth.jsonl` (09-16), `merge_report.json` (09-23, 55,811 unjudged / 500), and no committed `JUDGING_RATE`, `COST_SURFACES`, `CERTIFICATE_TRUTH` or `PRODUCTIVITY_CENSUS`. The DSR variance is still the fixed 0.014863.

## A2 — Audit 20 implementation items (I) and pipeline chain (P1)

Checked against LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `6c8a71a4` (2026-09-30). Read-only, using `git show` / `git grep` / GitHub Actions.

Facts that hold across the section, all measured on LIVE:
- **CI is red at the LIVE head.** Run 36701520415 on `6c8a71a4` failed. The `quality` job's LAW GATE failed 38 fences with `check_immutable_evaluator.py` BREACH: `desks/mt5/scripts/external_gauntlet.py` changed since signing (`baa3071c…` → `cccb6ff6…`), from commit `7379cbf7`. The `mt5-money-path` suite also failed. The `seal` job was skipped. Criterion C fails for every gauntlet-dependent item.
- **sleeves.json** (`desks/mt5/data/sleeves.json`): 66 rows, 40 LIVE and 26 STANDBY.
  - 24 of the LIVE rows are banned `discovered` rows.
  - 31 LIVE rows have `admission.status = UNMEASURED` (9 LIVE).
  - All 40 LIVE rows have `artifact.ok = false` ("no cost basis").
  - 40 of 40 LIVE rows have `delta_elogw_per_day = null`.
- **Gate 9 restates walk-forward.** `external_gauntlet.py:2526-2527` still sets `lockbox_sharpe = round(wf_oos, 4)`. The DSR variance is still the constant 0.014863 (`effective_trials.py:309`; `gate_policy.py:36` FIXED_VARIANCE_OF_SHARPES), and the canon records `variance_basis: fixed_variance_of_sharpes(0.014863)`.
- **Research budget is not authoritative.** `desks/mt5/data/research_budget.json:17` reads `"authoritative": false`, generated 2026-09-23, with "every leg ran on its base budget".
- **Judging backlog.** `desks/mt5/data/hypotheses/merge_report.json:111` reads `unjudged_total: 55811`. The 57,538 denominator is not in any committed file I found.
- **Branch-only fixes.** Lockbox (#52) is only on `origin/claude/audit-p0-true-lockbox`: `gate_policy.carve_lockbox` and `test_canonical_reserved_lockbox.py`. Sovereignty (#53) is only on `origin/claude/audit-p0-allocator-sovereignty`: `allocator_sovereign`, `test_allocator_sovereignty.py`. Neither has a hit on LIVE. The latest merges on LIVE are #69, #63, #65, #51, #56, #59 and #50.
- **No organ artifacts are committed.** `desks/mt5/reports/` on LIVE holds none of the new organ artifacts: IDENTITY_CHAIN, EXPERIMENT_LEDGER, CERTIFICATE_TRUTH, COST_SURFACES, JUDGING_RATE, FACTORY_CONTRACTS, REPLICATION, PLACEBO, LIVE_CALIBRATION, CONSTRAINED_BOOK, EXPERIMENTAL_BUDGET, OPS_REDUNDANCY and FORWARD_EVIDENCE are all absent. The gitignore keeps `data/*` out, and no box reading is evidenced. So R = ✗ unless a committed file is named.

Marks: I Implemented, W Wired, A Authoritative, T Tested, R Artifact, D Deployed, C Consistent.

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| I1 | One immutable research identity, raw data to live P&L | PARTIAL | ✓✓✗✓✗✓✗ | `research/identity_chain.py` and `libs/research/trade_identity.py`, run hourly from `hourly_cycle.py:851` and `:4833` (appends `data/identity_chain.jsonl`, gitignored). Tests: `test_identity_chain.py`, `tests/research/test_trade_identity.py`. `frontier_identity.cell_id` has no data/PIT/code/cost/seed hash | Stamp fills and orders with the id at order time. Add data, PIT, code, cost-model and seed hashes. Make promotion and attribution join on the id rather than the sleeve name. Commit or evidence the chain artifact | Unowned |
| I2 | True lockbox, sole certification path, separate process/store | PARTIAL | ✗✗✗✓✗✗✗ | LIVE `external_gauntlet.py:2526-2527` sets `lockbox_sharpe = wf_oos`; `:1779` only counts the restatement. `libs/research/lockbox.LockboxService` is called only by `scripts/check_promotion_readiness.py:100,155`, which is not a certifier. The fix exists only on the `audit-p0-true-lockbox` branch (#52) | Merge #52, then move the lockbox to a separate process and store with one reserved block. Re-certify, commit the re-certification, and make the CI law gate green (the external_gauntlet seal breach is currently red) | Truth-fixes |
| I3 | Lifetime global trial ledger feeding DSR/PBO/SPA | PARTIAL | ✓✓✗✓✗✓✗ | `libs/research/experiment_ledger.py`. Callers: `external_gauntlet.py:1821` (reported beside the charge, never sets the bar) and `pf_allocator.py:746` (trial counts, tightening only). Tests only indirect (`test_gauntlet_annotations.py`). DSR variance fixed at 0.014863 (`effective_trials.py:309`), so the certifier has zero power | Lifetime count must set the DSR/PBO/SPA charge. Measure the variance instead of fixing it. Add a correlated-trial adjustment. Add a dedicated test. Commit EXPERIMENT_LEDGER. Fix the CI red | Truth-fixes |
| I4 | Sovereign certificate store; check_certificate_truth permanently green | PARTIAL | ✓✓✗✓✗✓✗ | `research/certificate_truth.py`, run hourly (`hourly_cycle.py:960`, budget `:1773`). Consumer: `sleeve_registry.py:326`. Test: `test_certificate_truth.py`. Committed `sleeves.json` has 40 LIVE rows, 24 of them banned `discovered`, and 474 divergences (re-verification log). Off-box the fence exits 0 as SNAPSHOT | Run `--apply` on a schedule and `--require-state` in the gate. Migrate the stores until 0 banned and 0 unbacked rows. Commit CERTIFICATE_TRUTH.json | Truth-fixes |
| I5 | Allocator sovereignty: zero stays zero, below-min is zero; principal sleeve separate | PARTIAL | ✗✗✗✗✗✗✗ | LIVE `decision_core.py:309` `venue_min_lot`; `promoted_lot` and `gold_book_lot` still floor at 0.01 (`:326`, `:470-523`). `allocator_sovereign` exists only on `audit-p0-allocator-sovereignty` (#53: decision_core, gateway, sizing, `test_allocator_sovereignty.py`). 31 LIVE rows UNMEASURED and 40/40 `delta_elogw` null still hold capital | Merge #53, remove the file-switch reversibility, and budget a separate principal sleeve. Needs the principal's call against the never-reduce order | Truth-fixes |
| I6 | Risk as hard constraints inside E[log W] | PARTIAL | ✓✓✗✓✗✓✓ | `libs/portfolio/robust_elog.py`, called by `pf_allocator.py:61` (CVaR as a penalty). `constrained_elog.py` and `research/constrained_book.py` run hourly (`hourly_cycle.py:878`, `:4879`) with `FEEDS_LIVE = False` (shadow). Tests: `tests/portfolio/test_robust_elog*.py`, `test_constrained_book.py` | Needs the principal's decision on P1/P13 (REFUSED per CLAUDE.md). The constrained solve must feed pf_allocator. Add max-ruin, margin, liquidity and concentration as in-solve constraints. Commit the artifact | Unowned |
| I7 | Cost truth before capital; multi-dimension cost surfaces | PARTIAL | ✓✓✗✓✗✓✗ | `research/cost_surface.py` (symbol×hour spread) is read by `external_gauntlet.py:261,639` and `pf_allocator.py:768`; that part is authoritative, but spread only. `cost_surfaces.py` (6-D) runs hourly (`hourly_cycle.py:849,984`) and has no consumer; COST_SURFACES is read only by itself. Test: `test_cost_surfaces.py`. All 40 LIVE rows have `artifact.ok = false`, "no cost basis" | Admission and sizing must read the 6-D surfaces. Add latency and adverse-selection surfaces. Needs matched_fills > 0. Fail closed on a missing cost basis, which LIVE rows currently violate | Truth-fixes |
| I8 | Judging throughput ≥ creation; cheap gates first | PARTIAL | ✓✓✓✓✓✓✗ | `research/judging_throughput.py`, run hourly (`hourly_cycle.py:961`); it sizes gauntlet workers (authoritative on compute). Tests: `test_judging_throughput.py`, `test_judging_rate.py`, `test_judging_speed_equivalence.py`. Committed `data/hypotheses/merge_report.json:111` shows `unjudged_total: 55811` | Needs a box JUDGING_RATE reading showing judging ≥ creation, and the backlog drained. CI is red on external_gauntlet (`7379cbf` "maximize gauntlet throughput" broke the seal) | Truth-fixes |
| I9 | Effective breadth via independence graph; north star = independent alpha rank | PARTIAL | ✓✓✗✓✗✓✓ | `libs/research/independence_graph.py` and `research/alpha_rank.py`, run hourly (`hourly_cycle.py:843,1023`); the only consumer is `factory_contracts` → `cycle_pricing` (research compute). Test: `tests/research/test_independence_graph.py` (alpha_rank only via `test_research_loop_tier1.py`) | Rank must steer promotion and allocation, not only research seconds. Add execution and causal edges. Commit the artifact | Tier S |
| I10 | Closed-loop world discovery map + per-source info value | PARTIAL | ✓✓✗✓✗✓✓ | `research/information_value.py --apply` runs on FrontierAudit (`ops/run_frontier_audit.cmd:64`). `libs/research/source_roi.py` and the country packs have tests (`test_information_value.py`, `test_source_roi.py`). `research_budget.json` says `authoritative: false` | One six-axis map. Measured per-source information value that demotes dead sources and moves budget, which requires research_budget to become authoritative | Unowned |
| I11 | Factories measured on 7 metrics; compute reallocated | PARTIAL | ✓✓✗✓✗✓✗ | `research/factory_contracts.py`, run hourly (`hourly_cycle.py:843`). Consumer: `cycle_pricing.py:293`, weighted 0.15 (`:384`), through `applied_budget` at `hourly_cycle.py:500`. `research_budget.json` says "no price moved a leg's seconds". Tests: `test_cycle_pricing.py`, `test_research_loop_tier1.py` | Full 7-metric contract per factory. An evidenced reallocation, with authoritative set to true. Commit FACTORY_CONTRACTS | Truth-fixes / Tier S |
| I12 | Research self-improvement as experiment | PARTIAL | ✓✓✗✓✗✓✓ | `libs/research/search_populations.py`, called from `alpha_evolution.py:79`. Test: `tests/research/test_search_populations.py`. researcher_market, meta_benchmark and twin are not on LIVE (#55 unmerged) | One scored tournament across researcher types, a randomized budget holdout, a link to realized P&L, and adoption with authority | Tier S |
| I13 | Small pure components, typed contracts, property tests | PARTIAL | ✓–✗✓✗✓✗ | `decision_core.py` has been extracted. The monoliths remain (hourly_cycle, pf_allocator, gateway, external_gauntlet). Property tests are few. The CI money-path suite fails on `6c8a71a4` | Split the monoliths, add typed producer/consumer interfaces, separate gateway I/O from decisions, and get CI green | Unowned |
| I14 | Production-grade CI; signed artifacts; prod accepts only green | PARTIAL | ✓✓✗✓✗✓✗ | `.github/workflows/ci.yml` (law gate, ruff, mypy, pytest, money-path, seal); `libs/ops/release_signing.py` (`tests/ops/test_release_signing.py`). LIVE head run 36701520415 is a **failure**: LAW GATE BREACH on external_gauntlet.py plus a money-path suite failure, and seal was skipped. The box adopts regardless (Adopt-And-Seal is not CI-gated) | CI green, with parity, migration and repro steps. The box must refuse a release without a green CI hash | Truth-fixes |
| I15 | Independent implementation verifier | PARTIAL | ✓✓✗✓✗✓✓ | `research/replication_civilization.py`, run hourly (`hourly_cycle.py:3845`), and `independent_verifier.py` on FrontierAudit (`run_frontier_audit.cmd:114`). Tests: `test_replication_civilization.py`, `test_independent_replica.py`. `promoter.py` has no replication/quarantine read (the tier_s_block is #55, unmerged) | A MISMATCH must block promotion on LIVE. Trade-level and timestamp-level comparison. Commit REPLICATION.json | Tier S |
| I16 | Continuous placebo/adversarial tests with audit-recall | PARTIAL | ✓✓✗✓✗✓✗ | `research/adversary.py` (`hourly_cycle.py:2658`) and `placebo_audit.py` (`:963`, `:4581`). Tests: `tests/research/test_adversary.py`, `test_placebo_audit.py`. PLACEBO_AUDIT has no consumer outside `layers.py`. Batch 3 found the certifier rejects 600/600 positive controls | The recall result must gate the certifier (a FREEZE honoured by the promoter). Power > 0, which needs the DSR variance fixed. Commit the artifact | Tier S |
| I17 | Live attribution as final judge; overstating priors downweighted | PARTIAL | ✓✓✓✓✗✓✓ | `live_calibration_posterior.py`, run hourly (`hourly_cycle.py:878`), consumed by `credit_assignment.py:183` and `libs/research/bandit.py:970` (research priors, which is authority over research only). `allocator_attribution.py` runs in `daily_cycle.py:386`. Tests: `test_live_calibration_posterior.py`, `test_allocator_attribution.py` | Close the loop into pf_allocator sizing, meaning predicted-vs-realized slippage and marginal contribution. Needs matched fills > 0. Commit the artifact | Tier S |
| I18 | Human experimentation in a separate budgeted sleeve | PARTIAL | ✓✓✗✓✗✓✗ | `research/experimental_budget.py`, run hourly (`hourly_cycle.py:878,4880`); shadow, overrides still in the institutional book. `libs/execution/discretionary_sleeve.py` has no caller. Test: `test_experimental_budget.py`. `sleeves.json` has 40 LIVE rows with `principal_override` blocks in-book | Actually split the budget and ledger in the money path. Move the override rows out of the institutional book | Unowned |
| I19 | Operational redundancy (second broker EXCLUDED) | PARTIAL | ✓✓✗✗✗✓✗ | `ops_redundancy.py` runs hourly (`hourly_cycle.py:879`; `test_ops_redundancy.py`). `dr_drill.py` runs on FrontierAudit (`run_frontier_audit.cmd:118`) with no test. `run_restore_drill.py` via `ops/quant-restore-drill.service` (VPS), no test. The moat backup timer is unencrypted | Hot or warm standby, failover, drills on real box state, dr_drill tests, encrypted backups, and a committed drill artifact. Broker part: EXCLUDED | Tier S (chaos) / Unowned |
| I20 | Let time complete: forward/live evidence | TIME-BOUND | ✓✓✗✓✗✓✗ | `forward_evidence_tracker.py`, run hourly (`hourly_cycle.py:879,4883`); `test_forward_evidence_tracker.py`. Forward clocks and decay/calibration run. Consistency fails: 13 unbacked-clock LIVE book rows and 31 UNMEASURED LIVE rows | Time, plus a committed tracker artifact and clocks that are backed by certificates | n/a |
| P1 | Pipeline with no bypass arrow | PARTIAL | ✓✓✗✓✗✓✗ | See the arrow table. Four arrows are bypassed on LIVE: lockbox, forward clock, allocator, multiplicity. Two are advisory: cost and PIT audit. CI is red | Close every bypass (#52, #53, certificate migration, cost fail-closed) and get CI green | Both |

### P1 arrows (the existing section lists these as bullets, not rows, so they are not counted)

| Arrow | Strict status on LIVE | Key evidence / gap |
|---|---|---|
| World data → PIT lake | PARTIAL | lake_pit plus the check_pit ratchet in CI, but CI is red; the bitemporal audit is PR-only |
| PIT lake → representation factory | PARTIAL | Runs on FrontierAudit; miners are not forced to consume it |
| → Hypothesis swarms | PARTIAL (exists) | Miners and populations run; no committed yield artifact |
| → Lifetime multiplicity ledger | BYPASSED | `external_gauntlet.py:1821` reports it beside the bar |
| → Cheap falsification | Authoritative | pre_filter / fast_admission |
| → CPCV/PBO/SPA/DSR | Authoritative but powerless | DSR variance fixed at 0.014863; 0/600 positive controls pass |
| → Sealed true lockbox | BYPASSED | `external_gauntlet.py:2526-2527` gate 9 = WF OOS |
| → Forward clock | BYPASSED | 24 banned + unbacked LIVE rows in `sleeves.json` |
| → Live cost calibration | Advisory | matched_fills = 0; 40/40 LIVE rows have `artifact.ok = false` "no cost basis" |
| → Sovereign E[log W] allocator | BYPASSED | Min-lot and gold floors; 31 UNMEASURED LIVE rows keep capital; #53 unmerged |
| → Execution → fills | PARTIAL | The fill surface falls back to a spread prior |
| → Attribution | PARTIAL | Joins by sleeve name |
| → Posterior update | PARTIAL | Research priors only; no allocator loop |
| → Research credit → search | PARTIAL | cycle_pricing weights factory_contracts at 0.15; research_budget is `authoritative: false` |

Counts: DONE 0 / PARTIAL 20 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 1 (21 rows: I1–I20 + P1; the I19 second-broker sub-part is EXCLUDED, the row is PARTIAL)

### Top gaps

- **CI is red at the LIVE head `6c8a71a4`.** The LAW GATE fails with an immutable-evaluator BREACH on `external_gauntlet.py`, introduced by `7379cbf`, and the money-path suite fails. No item touching the gauntlet or CI can be Consistent, and seal is skipped.
- **Lockbox (#52) and allocator sovereignty (#53) exist only on feature branches.** LIVE still sets gate 9 to the WF OOS and still floors zero allocations to the venue minimum, so I2 and I5 fail criteria I, D and C.
- **The certifier has no power, and the lifetime ledger is not in the charge.** DSR variance is a constant 0.014863, and `experiment_ledger` is only "reported beside" the bar.
- **Committed state contradicts the rules.** `sleeves.json` has 40 LIVE rows: 24 banned `discovered`, 31 UNMEASURED admission, and 40 with `artifact.ok = false` "no cost basis". No scheduled `--apply` migration runs.
- **Most organs are wired but have no authority.** cost_surfaces, placebo_audit, identity_chain, constrained_book, experimental_budget and replication have no money-path or promotion consumer. `research_budget.json` is `authoritative: false`.
- **Artifacts are almost never committed or box-evidenced.** None of the organ outputs sits in `desks/mt5/reports/` on LIVE. The only committed judging evidence (`merge_report.json`) still shows 55,811 unjudged.

## B1 — Tier S 15-layer table (L) and sections 1–15 (T)

Checked against LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `6c8a71a4`. TIERS = `origin/claude/tier-s-institution` @ `ab404034` (PR #55: 21 ahead, 172 behind, unmerged).

**Facts behind every row:**
- None of `libs/tiers/*`, `desks/mt5/research/tier_s.py`, `docs/research/tier_s_*.json`, `scripts/check_tier_s_program.py`, `tests/tiers/*` or `test_tier_s_organs.py` is on LIVE. LIVE `hourly_cycle.py` has no `tier_s` leg, and LIVE `promoter.py` has no `tier_s_block`.
- So every row fails D (deployed) for its Tier S part.
- The ✓ marks below are for the LIVE analogue named in Evidence. They cover only part of each row's wording.

**Box evidence:**
- LIVE commits no Tier S report and almost no `desks/mt5/reports/*`: only 20 files, none of them from these organs.
- The committed `docs/research/runtime_state.json` (02:52Z) comes from a non-trading cloud host. It shows `alpha_rank`, `factory_contracts`, `placebo_audit`, `axis_registry`, `alpha_evolution` and `identity_chain` as NEVER there. No box run can be evidenced from the repo.
- R therefore gets ✓ only where a committed artifact exists. It gets ✗ where the only claim is a box artifact that cannot be seen.

**TIERS ledger claim:**
- `tier_s_program.json` has 46 rows. S01–S15 map one-to-one to T1–T15.
- For T1–T15 the ledger claims DONE for S07, S08, S10, S11, S13 and S14. S01 is BLOCKED_ON_USER. The rest are PARTIAL.
- Its DONE means "runs hourly + writes artifact + research-side wording". That is weaker than strict DONE: no deploy, no money-path authority, no box artifact.

**TIERS authority that does exist:**
- `promoter.tier_s_block` (promoter.py:1569) calls `promotion_authority.block`. It withholds a new LIVE row on a replication MISMATCH, online FDR over budget, or a production-judged immune DROP, and it runs `firewall.may`.
- `cycle_pricing` reads `researcher_prices.json` at weight 0.15.
- Tier S hypothesis rows reach `miner_candidate_compiler`.
- Everything else is report or shadow. The door only withholds, and the certifier has zero power while the DSR variance stays at the constant 0.014863 (batch 3).

**Merge caveat:** TIERS is 172 commits behind. `hourly_cycle.py`, `promoter.py` and `cycle_pricing.py` all diverged, so a merge needs conflict resolution plus one box run before any row can reach R/C.

Legend: I Implemented, W Wired, A Authoritative, T Tested, R Artifact, D Deployed, C Consistent (each judged on LIVE).

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE vs TIERS: file, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| L1 | Truth Kernel: immutable constitution controls everything | PARTIAL | ✗ ✓ ✓ ✓ ✗ ✗ ✗ | **LIVE:** `ops/principal_doctrine.txt` + `check_constitution_core.py` (law gate); `libs/research/immutable_rails.py` fences proposals (test_immutable_rails); `certificate_truth` hourly + fence. **TIERS:** `truth_kernel.py` + `tier_s_constitution.json`, read only by tier_s (S01 BLOCKED_ON_USER). | See T1. No gate reads the constitution's numbers. `check_certificate_truth` is softened to SNAPSHOT off-box (474 divergences). | Tier S build |
| L2 | World Data OS: PIT/bitemporal + provenance + reliability | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `libs/research/data_registry.py` (test), `acquire_datasets` hourly (test), `pit_audit.py` (not a leg). **TIERS:** `bitemporal.py`, organ_data_os (audit only). | See T2. No bitemporal store is used by any data path. | Tier S build |
| L3 | World Model: causal/economic knowledge graph | PARTIAL | ✓ ✓ ✗ ✓ ✓ ✓ ✗ | **LIVE:** `world_causal_graph.py` (hourly `_producer`, tests ×2), committed `data/world_causal_graph.json` (generated 2026-09-08, 0 admitted edges); `cross_asset_graph` hourly. **TIERS:** `world_edges.py` + `world_macro.py`. | Rates/credit/flows/positioning nodes are only on TIERS, and flows are UNMEASURED. It decides nothing. Committed artifact is 3 weeks stale with 0 admitted edges. | Tier S build |
| L4 | Researcher Civilization: hundreds of heterogeneous processes | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** ~40 producers; `live_calibration_posterior` hourly (per-producer κ, test) feeds bandit priors. **TIERS:** epistemology labels in organ_market. | See T4. No new epistemologies and no enforced blinding. | Tier S build |
| L5 | Hypothesis Ecology: competing/evolving mechanism populations | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `libs/research/hypothesis_graph.py` (tests), `alpha_evolution` hourly (bandit budget), `alpha_lineage` hourly (test). **TIERS:** QD/genomes/theory emit compiler rows. | Populations are picks over a fixed family vocabulary. No evolving mechanisms, no authority. | Tier S build |
| L6 | Research-Program Evolution | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** `research_evolution.py` (test) via meta_rnd. **TIERS:** 10-gene genome (S05 PARTIAL, S07 claimed DONE). | See T5/T7. Programs, schedulers and pipelines are not evolved. PR-only. | Tier S build |
| L7 | Adversarial Science: researchers vs destroyers co-evolve | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | **LIVE:** `adversary_evolution.py --apply` in `run_frontier_audit.cmd:100` (daily MT5-FrontierAudit), no test. **TIERS:** `red_queen.py` on the production gauntlet (batch 3). | See T9. Not per-researcher, no test on LIVE, no authority. | Tier S build |
| L8 | Universal Validation: anti-selection/anti-leakage | PARTIAL | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | **LIVE:** universal gate/`external_gauntlet` decides certificates; `effective_trials` hourly (test). **#52** (lockbox, lifetime trials) unmerged. **TIERS:** online FDR + immune + replication on the promoter door. | DSR variance is still the constant 0.014863 (zero power). Lockbox Sharpe equals WF OOS. Online FDR and immune are TIERS-only. | Both threads |
| L9 | Alpha Topology: true independent dimensions | PARTIAL | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | **LIVE:** `alpha_rank.py` + `libs/research/independence_graph.py` (8 channels, test_independence_graph), hourly leg; ALPHA_RANK → `factory_contracts` → `cycle_pricing` (weight 0.15, compute). **TIERS:** `topology.rank_report`. | See T15. No committed or evidenced ALPHA_RANK.json; runtime_state says NEVER. The DP5 breadth reading is a week old. Compute-only authority. | Tier S build |
| L10 | Portfolio Intelligence: posterior E[log W] | PARTIAL | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | **LIVE:** `pf_allocator` (money path, gateway deploys fractions); `constrained_book` hourly but `FEEDS_LIVE=False`. **TIERS:** opportunity_exchange is shadow (S25 BLOCKED_ON_USER). | Min-lot/gold floors override a zero allocation (#53 unmerged). UNMEASURED admission keeps capital. The exchange does not steer the allocator. | Other slices |
| L11 | Execution Intelligence: learned implementation optimum | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | **LIVE:** `execution_science.py --apply` in `run_frontier_audit.cmd:65` (daily; the old matrix said unscheduled), no test. **TIERS:** schedules it hourly (S23 claimed DONE). | Report only. Nothing is learned into execution, `cost_surfaces` is unconsumed, and there are 0 matched fills. | Other slices |
| L12 | Live Reality Engine: backtest reconciled to reality | PARTIAL | ✓ ✓ ✗ ✓ ✓ ✓ ✗ | **LIVE:** `forward_reconcile` (test, committed `data/forward_reconcile.json`), `fill_attribution` hourly. **TIERS:** prediction_accounting (accounted_share 0). | Not authoritative over sizing or promotion. Live evidence n is tiny. | Other slices |
| L13 | Meta-Science: which methods create edge | PARTIAL | ✓ ✓ ✓ ✗ ✗ ✓ ✗ | **LIVE:** `factory_contracts` (per-producer yield → cycle_pricing, compute), `credit_assignment` → bandit; no tests for either. **TIERS:** organ_market P(pass)/FDR/validated_per_cpu_h. | Per-method attribution is crude, untested and unevidenced. `research_budget.json` is `authoritative:false`. | Tier S build |
| L14 | Architecture Evolution: system proposes self-improvements | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `implementer` + `research_evolution` (test), fenced by immutable_rails. **TIERS:** twin/self_model; research challengers adopt, money path is PROPOSE only (S30 BLOCKED_ON_USER). | Money-path challengers are never adopted. Twin and self_model are PR-only. | Other slices |
| L15 | Operational Kernel: reproducible, redundant, deterministic | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | **LIVE:** `state_replay_audit` hourly (test), `ops_redundancy` hourly, `dr_drill` daily (no test). **TIERS:** replay/chaos (S42 BLOCKED_ON_BOX). | No standby or failover, backups unencrypted, chaos never kills processes. Report only. | Other slices |
| T1 | Truth Kernel: agents cannot change PIT/trials/cost/lockbox/cert/capital/provenance/repro rules; content-addressed raw→fill; reconstruct any trade | PARTIAL | ✗ ✓ ✓ ✓ ✗ ✗ ✗ | **LIVE:** `check_constitution_core.py` (law gate), `immutable_rails` (test), `identity_chain` + `libs/research/trade_identity.py` hourly (tests; report, fills not stamped), `state_replay_audit` hourly. **TIERS:** `truth_kernel.py` Journal/seal, tier_s.py:434; constitution read by no gate (S01 BLOCKED_ON_USER); tests in tests/tiers. | Merge #55, then: bind the constitution's values in gauntlet/promoter/allocator; stamp lineage inline at order time (2.8% reconstructible); add size/order rationale; stop ratification relying on git-author heuristics. | Tier S build |
| T2 | World Data OS: bitemporal, per-datapoint provenance/revisions/latency/licence/reliability; acquisition by info-gain per € | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `data_registry` (test), `acquire_datasets` hourly (test), `pit_audit.py` not a leg. **TIERS:** `bitemporal.py` BitemporalStore (used by no data path), organ_data_os audits 3 JSONLs (pit_share 0.0); test bitemporal_as_of (S02 PARTIAL). | Merging is not enough. A real bitemporal store must sit on the data path, with a per-datapoint provenance/licence store, the acquisition ranking fed to `acquire_datasets`, and real € costs. | Tier S build |
| T3 | World model: rates→FX→…→flows graphs, regional; stable/state-dependent/decaying/false; hypotheses from broken edges | PARTIAL | ✓ ✓ ✗ ✓ ✓ ✓ ✗ | **LIVE:** `world_causal_graph.py` hourly, 2 tests, committed json (2026-09-08, 90 nodes, 0 admitted); `cross_asset_graph` hourly. **TIERS:** `world_edges.py` classify + `world_macro.py` daily macro/CFTC nodes; broken edges emit `cross_asset_residual` rows (S03 PARTIAL). | Classify LIVE's own world_causal_graph edges. Flows dataset and regional graphs are missing. Nothing decides on it. Needs a fresh box artifact with admitted edges. | Tier S build |
| T4 | Researcher civilization with ~25 epistemologies incl. non-LLM; some blind to others | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** existing producers + `live_calibration_posterior` (test) → bandit. **TIERS:** organ_market labels producers by name; independent_discoveries = 0 (S04 PARTIAL). | New researcher types. **Enforced blinding** (a firewall role that stops cohorts reading each other). A measured independent-discovery count > 0. | Tier S build |
| T5 | AlphaEvolve-for-alpha: LLM + evaluators evolving code, grammars, portfolio/regime/execution/scheduler programs; fitness = validated independent alpha per compute | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | **LIVE:** `alpha_evolution` hourly (formula evolution, bandit budget, no dedicated test; its evolved recipe reaches the docket). **TIERS:** `evolution.py` step/fitness, organ_genomes, grammar read by `expression_factory.py:90` via grammar_bias (S05 PARTIAL). | No LLM-in-loop program evolution. Portfolio, regime, execution, model-architecture and scheduler programs are not evolved. Fitness is not validated alpha per compute on LIVE. | Tier S build |
| T6 | MAP-Elites over 12 descriptor axes | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | **LIVE:** `research_diversity_archive.py` + `libs/research/diversity_archive.py`, reached hourly via `experiment_spine` (hourly_cycle:3809); `axis_registry` hourly (test). No archive test. **TIERS:** evolution.Archive, organ_qd on 12 axes (batch 2, not re-audited), probes to the compiler (S06 PARTIAL: capacity and corr-cluster axes missing). | Capacity and corr-cluster axes. A research program per cell. The archive steers nothing with authority. Test and box artifact on LIVE. | Tier S build |
| T7 | Evolve researcher genomes; fitness = validated independent info / compute with penalties | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** none (research_evolution tunes research params, not researcher genomes). **TIERS:** RESEARCHER_GENES (10), `falsify_order` now used (tier_s.py:1120), organ tests; ledger S07 **claims DONE** but best_fitness was 0 on the cloud run. | Merge. Add prompt-architecture and model-family genes. Tighten fitness attribution (credits any later verdict). Evidence a box run with fitness > 0. | Tier S build |
| T8 | Researcher market: posteriors, bandits/Bayesian allocation, deteriorating lose compute | PARTIAL | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | **LIVE:** `cycle_pricing` (test, FLOOR 1.00) applies budgets from `factory_contracts` (0.15) + bandit (`libs/research/bandit.py`, tests); `research_budget.json` authoritative:false. **TIERS:** `researcher_market.allocate` (Thompson + MILP) → `researcher_prices.json`, read by cycle_pricing at 0.15 (S08 claimed DONE); MILP per-researcher budgets unused. | Merge. Use the per-researcher MILP budgets, not only the per-leg max price. Add € cost and a portfolio-contribution term. Replace the heuristic P(cheap). Needs a box artifact. | Tier S build |
| T9 | Red Queen per-researcher adversary (15 attack kinds), counter-agent, co-evolve | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | **LIVE:** `adversary_evolution.py` daily in FrontierAudit (one run_gauntlet per generation), no test, no consumer with authority. **TIERS:** `red_queen.py` now attacks the production `run_gauntlet` (batch 3), tier_s.py:702 (S09 PARTIAL). | Attacks attributed per researcher. Hidden-factor, overlap, false-causality and corporate-action attack kinds. A winning defender changes the real gates. Tests. | Tier S build |
| T10 | Planted traps (blind), immune score, FREEZE production when traps accepted | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | **LIVE:** `placebo_audit.py` hourly (hourly_cycle:4581, test_placebo_audit), report, no consumer. **TIERS:** `traps.py` 17 kinds × 150 on the production certifier; `promoter.tier_s_block` honours a production immune DROP (S10 claimed DONE). Toy FREEZE has no authority. | Merge #55. Inject traps blind into the live research stream (needs a promoter trap registry). The certifier rejects 600/600 genuine controls (power 0), so immune = 1.0 is vacuous until the DSR variance is measured. | Tier S build |
| T11 | Adaptive multiplicity: lifetime genealogy + online FDR / sequential / e-values | PARTIAL | ✗ ✓ ✓ ✓ ✗ ✗ ✗ | **LIVE:** `effective_trials` hourly (test; read by external_gauntlet) with the DSR constant; no online FDR or e-values. **TIERS:** `online_fdr.py` LORD++/e-LOND; over budget blocks at `promoter.tier_s_block` (S11 claimed DONE); lifetime trials only in #52. | Merge #55 and #52. Use real survivor p-values (proxies today). Add an anytime-valid sequential test on forward evidence. Evidence the 24% over-budget share on the box. | Tier S build (+ #52) |
| T12 | Epistemic firewall, physically isolated roles | PARTIAL | ✗ ✓ ✓ ✓ ✗ ✗ ✗ | **LIVE:** `moneypath_precommit_guard.py` (pre-commit), `check_immutable_evaluator` wall (test), IMMUTABLE_MANIFEST. Policy and hooks, not role isolation. **TIERS:** `firewall.py` AST audit + ratchet; `may()` is called only by `promotion_authority` (S12 PARTIAL). | No process, OS or permission isolation. Developer→evaluator and lockbox-accepts-frozen-only are not enforced. Ratchet breach is not in the law gate. 1 violation on the run. | Tier S build |
| T13 | Negative knowledge: typed causes, graph, retrieval for new candidates, "explored N times" → move on | PARTIAL | ✓ ✓ ✓ ✗ ✗ ✓ ✗ | **LIVE:** `negative_knowledge.py --apply` (trained P(survive) model) daily in `run_frontier_audit.cmd:53`, read by `gauntlet_backpressure`, `graveyard_resurrection`, `scout_roster`; no test found. **TIERS:** `failure_memory.py` 15 causes/theorems (S13 claimed DONE, 0 theorems on the run); retrieval steers only tier_s's own rows. | Typed causes beyond the terminal gate. A graph, not equivalence classes. Other generators read failure memory. Tests and a box artifact on LIVE. | Tier S build |
| T14 | Ancestry graph: code/feature/hypothesis/data ancestry + P&L/tail similarity; derived not counted fresh | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | **LIVE:** `libs/research/hypothesis_graph.py` (tests), `lineage_dag.py`, `alpha_lineage` hourly (test); `independence_graph` has a feature-ancestry channel. **TIERS:** multi-parent lineage (batch 4), `topology.effective_discoveries` (S14 claimed DONE), ancestry novelty prices compute. | Code and data ancestry. P&L/tail similarity in novelty. Effective discoveries must discount counts, gates or budgets on LIVE (reported only). | Tier S build |
| T15 | Effective Independent Alpha Rank (PnL, eigen, nonlinear, tail, DD, ancestry, exposure, overlap, mechanism, regime); scheduler searches orthogonal | PARTIAL (closest to DONE) | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | **LIVE:** `alpha_rank.py` + `independence_graph.py` (8 channels incl. tail, factor exposure, feature ancestry, timestamp overlap, mechanism, execution, regime; test_independence_graph) hourly leg; ALPHA_RANK per producer → `factory_contracts` → `cycle_pricing` (0.15, compute). **TIERS:** `topology.rank_report` (descriptor headline 8.44), `_emit_orthogonal` rows (S15 PARTIAL). | Evidence one box ALPHA_RANK.json: none committed, runtime_state NEVER, DP5's 2.06 is a week old. Orthogonal search only through a 0.15 compute weight. Drawdown-coincidence channel. Reconcile the two rank organs (LIVE alpha_rank vs TIERS topology). | Tier S build |

**Counts:** DONE 0 / PARTIAL 30 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (30 rows)

### Top gaps
- **#55 is unmerged and 172 commits behind LIVE.** No Tier S code, test, ledger or promoter door exists on LIVE, so every row fails D. The merge conflicts in `hourly_cycle.py`, `promoter.py` and `cycle_pricing.py`.
- **Merging would not reach strict DONE for any row.**
  - TIERS' only money-path authority is a withhold-only promotion door (FDR, replication, immune).
  - Constitution values, the exchange, execution capture and FREEZE-from-toy reach no sizing or allocator code.
  - The certifier has zero power (DSR constant 0.014863), so the door never sees a genuine candidate.
- **No box artifact is evidenced for any Tier S organ or its LIVE analogues.** `alpha_rank`, `placebo_audit`, `factory_contracts` and `identity_chain` read NEVER in runtime_state. R needs one adopted box run committed or published.
- **The ledger's six research-side DONEs for T1–T15 (S07, S08, S10, S11, S13, S14) fail the strict test.** They are not deployed, and T7 fitness 0, T13 0 theorems and T4 0 independent discoveries show the organs are not yet producing.
- **Scope still short on LIVE and TIERS alike:**
  - no enforced blinding (T4);
  - no bitemporal store on the data path (T2);
  - no flows or regional world graphs (T3);
  - no OS-level role isolation (T12);
  - no inline trade lineage (T1);
  - traps not blind in the live stream (T10).
- **Several LIVE analogues lack tests or authority:**
  - `adversary_evolution`, `negative_knowledge`, `alpha_evolution`, `factory_contracts` and `research_diversity_archive` have no tests;
  - `placebo_audit` and `execution_science` are report-only.
  - Wiring `alpha_rank` (T15/L9) to a box artifact and a stronger scheduler weight is the cheapest path to a first strict DONE.

## B2 — Tier S sections 16–30 (T) and final loop

LIVE = origin/claude/llm-auto-upgrade-verify-gcjac3 @ 6c8a71a4. TIERS = origin/claude/tier-s-institution @ ab404034 (PR #55, unmerged; merge-base adaba442).
Marks are for LIVE, in order: I Implemented, W Wired, A Authoritative, T Tested, R Artifact, D Deployed, C Consistent. A mark is ✓ only when the criterion holds for the item as asked. If only a fragment holds on LIVE, the mark is ✗ and the Evidence cell says which fragment.

Facts that apply to every row:
- LIVE has **no** `libs/tiers/*`, `desks/mt5/research/tier_s.py`, `tests/tiers`, `test_tier_s_organs.py` or `check_tier_s_program.py`. All of them exist only on TIERS.
- The TIERS `tier_s` leg has never run on a box. `reports/**` is gitignored, so there is no committed Tier S artifact.
- Batch 3 found that the production certifier has zero power: the DSR variance is the constant 0.014863. So any Tier S door that withholds promotion only ever withholds.

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE vs TIERS) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| T16 | Counterfactual World Lab | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `synthetic_regimes.py` (11 worlds, hourly leg hourly_cycle:3352), `libs/research/counterfactual_world.py` (leg :4667) and `digital_twin.py` ABC-SMC (leg :4522). Tests: test_synthetic_regimes, test_counterfactual_world. No committed artifact. No promotion, sizing or admission code reads them (only digital_twin, layers and path_refs reference synthetic_regimes). **TIERS:** adds 5 worlds (16 in all) and `tier_s.organ_worlds`, which joins them per certificate for the review panel. That is still report-only. | Swap, market-closure and correlation-break worlds. An agent-based market. Causal counterfactuals joined to survivors. A consumer that turns a break flag into a task or a block. A committed artifact. Merging alone does not fix this. | Tier S build |
| T17 | Alpha Theory Compiler | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing. **TIERS:** `libs/tiers/theory.py` (7 slots, compile_mechanism, compose). `tier_s.organ_theory` emits recipes to `data/intelligence/tier_s/`, which `miner_candidate_compiler` reads. That is a real consumer, but only on TIERS. | Merge #55. Compose execution mechanism C. Require complete theories. Add tests for compile and compose. Replace family-table templates with real causal slots. Produce a box artifact. | Tier S build |
| T18 | Theory↔Evidence graph | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing. **TIERS:** `theory.TheoryGraph` (Beta posterior weighted live 3 / forward 2 / backtest 1, competing explanations, statuses) with test_theory_posterior_weights_live_over_backtest. Its only consumer is composition. | Merge #55. Add jurisdiction and regime dimensions. Make status gate something real (research priority or promotion). Produce a box artifact. | Tier S build |
| T19 | Heterogeneous non-LLM intelligence | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** the mathlab department (engines.py: SINDy, ABC, sympy-guarded formal maths, JAX-guarded differentiable; hourly legs via FOREST_DEPARTMENTS / expression_factory :3892), causal_discovery.py, alpha_evolution (leg :3187). Tests: test_mathlab_* and test_expression_factory. No committed `data/mathlab` artifact. Output is research input only. **TIERS:** `cross_science.py` (Kalman, spectral, TE, LV, recurrence, centrality, MCMC), which drains through expression_factory as `cross_science:<lab>`. No test. | A SAT/SMT solver or theorem prover. Guaranteed sympy/JAX on the box. A cross_science test. A committed artifact. A measured survivor contribution that decides budget. | Tier S build |
| T20 | AI peer review panels | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** only `blind_reviewer.py` (a separate organ: hourly :3342, veto in the promoter), not an 8-reviewer panel. **TIERS:** `review_panel.py` (8 rule-based reviewers, typed challenges). The `matched_fills_10` resolver is fixed (batch 2). `organ_review` writes REVIEW_PANEL_ROWS.json. No promoter or gate reads it. No tests. | Merge #55. Make the reviewers independently instantiated, not fixed if-rules. Make challenges trigger experiments. Make a panel verdict gate promotion. Add tests. Produce an artifact. | Tier S build |
| T21 | Auto-invent new tests | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing. **TIERS:** `test_invention.invent_from` learns from traps that fooled the production certifier (batch 3). Ratification is through `truth_kernel.constitution_status`. `tier_s_ratifications.jsonl` is empty. No test. | Merge #55. Mine real live-vs-backtest failures, redundant gates and predictable losses. Ratify and enact at least one gate. Add a test. Produce an artifact. The zero-power certifier (DSR constant) undermines the benchmark. | Tier S build |
| T22 | Auto-invent research grammars | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** fixed DSLs (`libs/research/alpha_grammar.py`, `mathlab/grammar.py`) used by the hourly expression_factory and alpha_evolution legs. Nothing on LIVE learns a grammar. **TIERS:** organ_grammar writes `data/tier_s/grammar.json`, and `grammar_bias.bias()` is read by expression_factory:90, alpha_evolution and alpha_grammar (batch 2 fix). That consumer is real but TIERS-only. | Merge #55. Evolve new representation classes (state machines, event sequences, panel/cross-sectional operators). Add a grammar-organ test. Produce a box artifact. | Tier S build |
| T23 | Execution as autonomous science | PARTIAL | ✗ ✓ ✗ ✗ ✗ ✗ ✗ | **LIVE:** `execution_science.py` separates frictionless from costed runs. Its caller is `ops/run_frontier_audit.cmd:65` (the MT5-FrontierAudit box task; installer and fail-loud exit from #64). It is not an hourly leg. LIVE also has latency, impact and feed-clock labs (hourly). There is no execution_science test and no committed artifact. pf_allocator does not read it. **TIERS:** hourly leg with --apply. Its drag feeds only the shadow-exchange friction. | pf_allocator must optimise expected capture. Add slicing, spread prediction, adverse selection and urgency. Recalibrate on live fills (matched_fills = 0). Add a test. Produce an artifact. Merging alone does not fix this. | Tier S build |
| T24 | No-trade first-class | PARTIAL | ✗ ✓ ✓ ✓ ✓ ✗ ✗ | **LIVE:** `pf_allocator.no_trade` (:1537) and its binding (:1627) are on the money path (PF_ALLOCATOR_ARMED), with test_no_trade_binds and `pf_forecast_log.jsonl` committed. But only the zero/hold part exists, and #53 is not on LIVE, so min-lot and gold floors still override a zero allocation (CS3). **TIERS:** `opportunity_exchange.ACTIONS` has all 7 actions, in shadow only. | Merge #53. Add DEFER and ALT_EXPRESSION to the live allocator. Put opportunity cost in the edge test. Test the action universe. | Tier S build (#55) / Institutional (#53) |
| T25 | Opportunity Exchange | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing. The authoritative allocator is pf_allocator, which knows no exchange. **TIERS:** `opportunity_exchange.clear` via organ_exchange writes `exchange_book.json` and registers an allocator challenger. Nothing outside tier_s reads it. Bids are hollow (flat capacity 0.05, identity correlation, tail/decay/liquidity unset). | Merge #55. Make pf_allocator clear the exchange. Give bids real inputs. Add a clearing test beyond heat. Produce an artifact. Merging alone does not fix this. | Tier S build |
| T26 | Live prediction-accounting | PARTIAL | ✗ ✓ ✗ ✓ ✗ ✗ ✗ | **LIVE:** `forecast_contract.py` belief register (Brier/MAE/CRPS; hourly leg :4574), test_forecast_contract_and_league. Its only readers are the issue board and the ceiling check, so it has no authority. No committed forecast-contract artifact (`data/forecast_log.json` is a different organ). **TIERS:** `prediction_accounting.py` (CRPS, PIT, coverage, pre-outcome lock; tested). organ_predictions logs one forecast per LIVE group from the tier_s posterior. | Fill exp_hold, slippage, MAE/MFE, vol, factor exposure and correlation. Forecasts per model. Calibration must drive researcher fitness or sizing. Produce an artifact. | Tier S build |
| T27 | Live reality outranks backtests | PARTIAL | ✗ ✓ ✓ ✓ ✓ ✗ ✗ | **LIVE:** `pf_allocator._posterior_mu` ranks live over forward over backtest, is authoritative, and writes `pf_forecast_log.jsonl`. That is the "outranks" half. The "penalise exaggerating factories" half is absent on LIVE. **TIERS:** `prediction_accounting.honesty` goes to organ_market, then researcher_prices, then `cycle_pricing:320` (0.15 weight, floor 1.00 after batch 2) and exchange bids (shadow). | Merge #55. Route the factory honesty penalty into admission and pf_allocator priors for new discoveries. The live sample is tiny (the time-bound part), but the missing wiring is work, not time. | Tier S build |
| T28 | Digital twin (shadow desk) and rollback | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** `digital_twin.py` is an ABC world simulator, not a shadow desk. `scripts/rollback_guard.py` has checkpoint/evaluate/revert, but no scheduled caller was found (git_snapshot only mentions it). **TIERS:** `twin.evaluate` (paired after registration; tested), organ_twin, and `rollback.py` plus `tier_s --rollback-to`. It is untested, needs a human push, and LIVE_MANIFEST has 1 SHA, so it returns available=False. | Run a shadow copy of the desk on new code versions against production data. Controlled promotion from it. A tested one-op rollback with ≥2 sealed SHAs. Produce an artifact. Merging alone does not fix this. | Tier S build |
| T29 | Self-model | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing equivalent (implementer reads CEO_DOCKET only). **TIERS:** `self_model.inventory/rank` writes SELF_MODEL_DOCKET.json, and `implementer._self_model_rows` feeds intake (batch 2 fix). Test: test_self_model_ranks_deficiencies. | Merge #55. Cover data gaps, weak disciplines, compute/capital bottlenecks and validation queues. Measure p_fix and cost, not hand constants. Produce a box artifact. | Tier S build |
| T30 | Architecture evolution | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | **LIVE:** nothing. **TIERS:** self_model SEALED_METRICS/regression. Red Queen validator challengers are re-scored on the sealed suite before adoption (batch 3). The truth_kernel constitution needs ratification (tested). The adopted config is not used by the real gauntlet. | Merge #55. Propose DBs, agents, libs, sources, search algorithms and refactors. A BLOCKED regression must stop release adoption (Adopt-And-Seal). Produce an artifact. | Tier S build |
| LOOP | Closed research→capital loop inside a Truth Kernel | PARTIAL | ✗ ✓ ✗ ✗ ✗ ✗ ✗ | **LIVE:** many nodes run hourly (world, mathlab, forecast_contract, cycle_pricing, promoter and the pf_allocator money path). Missing on LIVE: lockbox (#52), exchange, researcher market, theory, self-model and truth kernel. `check_certificate_truth` still has 474 unmigrated divergences (CS4). **TIERS:** adds the market→cycle_pricing link, the hypothesis→compiler link and the `promoter.tier_s_block` door (withhold-only; fails open). | Merge #52, #53 and #55. The exchange and execution capture must be read by pf_allocator. The Truth Kernel must gate the money path. Fix the DSR constant so the loop can pass anything. Produce box artifacts for every node. | Tier S build / Institutional (#52) |

Counts: DONE 0 / PARTIAL 16 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (16 rows). T27 has a time-bound component (live sample size), but it also has missing wiring, so it is scored PARTIAL.

### Top gaps
- **Nothing Tier S is on LIVE.** `libs/tiers`, `tier_s.py` and their tests are PR #55 only. For 8 of 16 rows (T17, T18, T20, T21, T25, T28-shadow, T29, T30) LIVE has zero of the seven criteria. Merging #55 moves them to I, T and D, not to DONE.
- **No authority even after the merge.** pf_allocator does not clear the Opportunity Exchange or read execution capture (T23, T25, LOOP). The factory honesty penalty only reaches compute pricing (T27). The review panel, theory status and invented tests gate nothing (T18, T20, T21).
- **Zero artifacts.** The tier_s leg never ran on a box and `reports/**` is gitignored. LIVE's related organs (synthetic_regimes, execution_science, forecast_contract, mathlab) also have no committed output. Every row fails R except the pf_allocator rows (T24, T27).
- **The certifier has zero power** (DSR variance constant 0.014863). Every withholding door (tier_s_block, invented tests, Red Queen) is untestable against genuine edges until CS1/I3 is fixed.
- **#53 is not on LIVE**, so the live no-trade path is overridden by the min-lot and gold floors (T24).
- **Scope holes that need new work, not a merge:** no shadow desk (T28), no SAT/SMT (T19), no agent-based or swap/closure worlds (T16), no evolving representation classes (T22), and architecture evolution is limited to validator configs (T30).

## C — 16 hardening items (H), depth priorities (DP), admission rule (ADM)

Checked 2026-09-30 against LIVE `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `6c8a71a4`. Marks: I=Implemented, W=Wired, A=Authoritative, T=Tested, R=aRtifact (fresh, committed/box), D=Deployed on LIVE, C=Consistent (CI/law gate not failing, not self-graded).

Shared facts:
- **Tier S (`libs/tiers/*`, `desks/mt5/research/tier_s.py`) is not on LIVE.** `origin/claude/tier-s-institution` is 21 commits ahead and unmerged (PR #55). Every H mark that rests on #55 fails I, W, T, R and D on LIVE.
- **CI on LIVE is red.** At 6c8a71a4, run 36701520415 failed both the `quality` job's "LAW GATE" step and the `mt5-money-path` job's "MT5 desk suite" step, and every later step was skipped. So C is ✗ for every row. The previous push (7379cbf) was cancelled.
- The #52 lockbox and #53 allocator-sovereignty branches are not merged (5 and 3 commits ahead). `origin/master` does not contain LIVE: 22 LIVE commits are missing from it.
- **Committed artifacts are stale.** `RESEARCH_DASHBOARD.md` was generated 09-22. `effective_breadth.jsonl` was last read 09-16 (2.057). `merge_report.json` is from 09-23. `research_budget.json` is from 09-23 and says `authoritative:false`: "no price moved a leg's seconds". `reports/*` are gitignored, so there is no committed REPLICATION, FRONTIER_MAP, CYCLE_PRICING or JUDGING_RATE.

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| H1 | Formal verification of money path | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/formal.py`, `conformance.py`, `tests/tiers/test_money_path_specs.py`: all on #55 only. None on LIVE. | Merge #55. Proofs must cover the real gateway, recovery and state-machine code, not an abstract model. A failed proof must block release. Needs a committed proof artifact and green CI. | Tier S |
| H2 | Independent evaluator civilization | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `scripts/check_immutable_evaluator.py` runs in `run_law_gate.py:162` and is tested (`tests/scripts/test_check_immutable_evaluator_wall.py`). `firewall.may()` and `review_panel` exist on #55 only. | The runtime firewall (`may()` in promoter) is not on LIVE. There are no separate reward signals, hidden data or a distinct stack. The law gate that runs it is failing. | Tier S |
| H3 | Architecture evolution, sealed suites | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/twin.py` and `organ_twin` are on #55 only. The sealed-suite re-score landed only in #55 batch 3. | Not on LIVE. Only a toy `ValidatorConfig` evolves. Adoption does not change the real gauntlet, scheduler, solver or execution. | Tier S |
| H4 | Immutable meta-benchmark, thousands of cases | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `meta_benchmark.py` and `traps.py` (2,550 sealed cases after batch 3) are on #55 only. The certifier had 0.0 power on 600 genuine controls. | Not on LIVE. Not a release gate. FREEZE is unconsumed on LIVE. No real historical or software-fault episodes. DSR variance is the constant 0.014863 (`effective_trials.py:309`). | Tier S |
| H5 | Active information acquisition (EVOI) | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE hourly legs: `data_acquisition_scientist` (`hourly_cycle.py:3864`), `value_of_data` (`:3356`) and `evig_acquisition` (`:3298`). Tests: `test_data_acquisition_scientist.py`, `test_value_of_data.py`, `tests/libs/test_evig_manufacture.py`. | Output is advisory: nothing buys or acquires data on its value. No pricing of timestamps, depth or history quality. No committed fresh artifact. The #55 calibration loop is unmerged. | Tier S |
| H6 | Research-search frontier estimator | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `research/frontier_map.py:61` writes `reports/FRONTIER_MAP.json` (gitignored) on the daily FrontierAudit task, with 5 tests referencing it. The Chao1/Good-Turing `frontier.py` is on #55 only. | No consumer, so no budget reads it. No committed artifact. Species are coarse labels. | Tier S |
| H7 | Epistemic uncertainty engine, 5 levels | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/epistemic.py` and `EPISTEMIC.json` are on #55 only. | Not on LIVE. Labels have no consumer. It covers about 60 certificates, not every key quantity. | Tier S |
| H8 | Cross-engine independent replication | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `research/replication_civilization.py` is an hourly leg (`hourly_cycle.py:3845`) with `test_replication_civilization.py`. It writes `reports/REPLICATION.json` and `data/replication_civilization/quarantine.json`. `replication_verdict` has no reader except `libs/moat/registry.py:153` (schema) and `build_zentech_state.py:1133` (display). | A MISMATCH does not block promotion on LIVE; `promoter.tier_s_block` is #55 only. It is not a second engine or stack. No committed REPLICATION artifact. | Tier S |
| H9 | Counterfactual failure search, architecture level | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `formal.ablations()`, Red Queen and traps are on #55 only. | Not on LIVE. No automated search over worlds where the factory, allocator or world model gives false confidence, where agents correlate, or where selection bias creeps in. | Tier S |
| H10 | Compute OS (CPU/GPU/RAM/net/tokens) | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `hourly_cycle.py:499` calls `cycle_pricing.applied_budget`. Leg ordering is at `:1247`. The pricing leg is at `:4760`. Test: `test_cycle_pricing.py`. `FLOOR, CEIL = 1.00, 2.00` (`cycle_pricing.py:81`). | `research_budget.json` records that no price moved a leg's seconds, so it has had no effect in practice. Only CPU seconds are priced: no GPU, RAM, storage, network or LLM tokens. `CYCLE_PRICING.json` is not committed. | Tier S |
| H11 | Global state replay at any second | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/replay.py` is on #55 only. It compares key sets. | Not on LIVE. No market, model-version or budget state. Fill reconstructibility is 0.028. | Tier S |
| H12 | Continual recovery / chaos experiments | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `scripts/run_restore_drill.py` is on `ops/quant-restore-drill.timer` (Sun 06:25). There is also `desks/mt5/scripts/dr_drill.py` and `test_control_plane_chaos.py`. `chaos.py` is on #55 only. | No real-process kills, MT5 disconnects, feed delays or VPS-loss drills. No test covers `run_restore_drill` or `dr_drill`. No standby or failover. Backups are unencrypted. No committed drill artifact. | Tier S |
| H13 | Mechanism discovery from non-finance fields | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/cross_science.py` is on #55 only. Its drain through `expression_factory` as `cross_science:<lab>` is also #55-only. | Not on LIVE. No box evidence of any conversion. | Tier S |
| H14 | Automated abstraction discovery | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `evolution.abstractions` and `grammar_bias` are on #55 only. The `expression_factory.py:90` reader is on #55 as well. | Not on LIVE. 0 primitives learned in the run. No committed `grammar.json`. | Tier S |
| H15 | Scientific memory compression | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `scripts/negative_knowledge.py` runs in daily_cycle and writes `docs/research/negative_knowledge.md` (last touched in bulk commit 09-28). 9 tests reference it. `failure_memory.py` is on #55 only. | No theorem, equivalence-class or mechanism-map layer on LIVE. Researchers do not consume it as authority. No freshness proof for the artifact. | Tier S |
| H16 | Human–machine separation of powers | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `truth_kernel.py` and `tier_s_constitution.json` are on #55 only. LIVE has only `ops/principal_doctrine.txt` plus `check_constitution_core.py`, which are outside this item's build. | Not on LIVE. Money-path code does not read the constitution. Ratification is spoofable by omitting trailers. The ratification ledger is empty. | Tier S |
| ADM | Subsystem admission rule (8 gains) | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `libs/tiers/contracts.py`, `control_arm.py`, `check_tier_s_program.py` and `AUTHORITY.json` are on #55 only. LIVE `run_law_gate.py:153` runs `check_tier5_audit.py`, which checks the ledger, not admission. | Not on LIVE. A REJECTED verdict only suspends steering on #55; nothing is disabled or removed. No committed admission verdicts. The rule does not apply to LIVE organs. | Tier S |
| DP1 | Finish/wire everything | PARTIAL | ✓ ✓ ✗ ✓ ✓ ✓ ✗ | LIVE `docs/research/tier5_audit.json` (updated 09-29): 216 EXISTS+WIRED+LIVE, 52 PARTIAL, 3 REFUSED, 1 DUPLICATIVE. `check_tier5_audit.py` runs in the law gate (`run_law_gate.py:153`), with `tests/scripts/test_check_tier5_audit.py`. | 52 PARTIAL remain, and "LIVE" means scheduled, not authoritative. The ledger is self-graded; the 0-DORMANT result was mostly a relabel. `run_scientist_tournament.cmd` ends `exit /b 0`. The law gate is red. | Institutional |
| DP2 | Remove dormant/partial components | MISSING | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | Nothing on LIVE removes components. 52 PARTIAL and 1 DUPLICATIVE remain in `tier5_audit.json`. | A removal or retirement pass with a ledger of what was deleted. | Institutional / Tier S |
| DP3 | Repair the validation defects | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | LIVE still has the variance constant 0.014863 (`effective_trials.py:309`, `gate_policy.py:84`). The #52 reserved lockbox, lifetime trials and fail-closed costs are unmerged. | Merge #52 (resolve its `IMMUTABLE_MANIFEST.json` conflict with #53). Measure the DSR variance. Migrate the 58 lockbox==wf_oos certificates. Get CI green. | Institutional |
| DP4 | Clear the judging backlog | PARTIAL | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | LIVE `judging_throughput` leg (`hourly_cycle.py:4290`) sizes workers from measured cores. Tests: `test_judging_rate.py`, `test_judging_throughput.py`, `test_judging_speed_equivalence.py`. `merge_report.json` (09-23) shows 57,538 docket, about 55,811 unjudged. The dashboard (09-22) shows 0 verdicts/day against 1,028 cells/day created. | No committed `JUDGING_RATE.json` or box reading showing judging ≥ creation. No measured drain; the backlog is growing. Commit 7379cbf ("maximize gauntlet throughput") was not verified by CI. | Institutional |
| DP5 | Measure actual independent breadth | PARTIAL (was DONE) | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | LIVE `libs/research/independence_graph.py`, `alpha_rank` leg (`hourly_cycle.py:4930`) and `research_dashboard` leg (`:4946`), with `tests/research/test_independence_graph.py`. Output feeds `factory_contracts`, which feeds `cycle_pricing`. | Artifact is stale: the last `effective_breadth.jsonl` reading is 09-16 (2.057) and the dashboard is 09-22 (2.057 of 58). A fresh committed reading is needed. CI is red. | Institutional |
| DP6 | Research-budget allocation sovereign | PARTIAL | ✓ ✓ ✗ ✓ ✗ ✓ ✗ | LIVE `hourly_cycle.py:499` (`cycle_pricing.applied_budget`) and `:509` (`research_budget.budget_s`), with `test_cycle_pricing.py`. | `research_budget.json` says `authoritative:false`: "no leg has asked the bandit… no price moved a leg's seconds". It covers hourly legs only; residents and tasks are excluded. meta_controller input is up to a day old. | Institutional |
| DP7 | Allocator sovereign | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | `origin/claude/audit-p0-allocator-sovereignty` (#53) is unmerged. LIVE min-lot and gold floors still override a zero allocation. | Merge #53, remove the file-based off-switch, get green CI and show a box pass sized by the allocator. | Institutional |
| DP8 | Cost truth mandatory | PARTIAL | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | #52 fail-closed costs and #53 `test_live_rows_need_a_cost_basis.py` are unmerged. On LIVE, 40/40 LIVE sleeves have no cost basis. | Merge both, migrate `sleeves.json`, get green CI. | Institutional |
| DP9 | CI permanently green | MISSING | ✗ ✗ ✗ ✗ ✗ ✗ ✗ | LIVE 6c8a71a4 CI run 36701520415 failed LAW GATE and the MT5 desk suite. Earlier runs on LIVE are failure or cancelled. | One green run on LIVE, then kept green. Required checks on the branch. | Institutional |
| DP10 | Recursive research competition | PARTIAL | ✓ ✓ ✗ ✗ ✗ ✓ ✗ | LIVE `ops/run_scientist_tournament.cmd` runs `scientist_tournament.py --apply` daily (no installer) and swallows failures with `exit /b 0`. No test references `scientist_tournament`. The researcher market is on #55 only. | Winners gain no authority beyond compute share. No tests, no committed artifact, 0 independent discoveries. | Tier S |
| DP11 | Accumulate untouched forward/live evidence | TIME-BOUND (machinery runs) | ✓ ✓ ✓ ✓ ✗ ✓ ✗ | LIVE `enrol_clocks` leg (`hourly_cycle.py:4393`) with `test_enrolment_ceiling.py` and `test_enrolment_drops_are_named.py`. `data/forward_clock_floor.json`. Dashboard: forward 26, live 40. | Only time. Also needed: a fresh committed forward/live snapshot (dashboard is 09-22) and green CI. | Institutional |

Counts: DONE 0 / PARTIAL 25 / MISSING 2 / EXCLUDED 0 / TIME-BOUND 1 (28 rows)

### Top gaps
- **Nothing is DONE under strict rules.** CI on LIVE 6c8a71a4 fails the LAW GATE and the MT5 desk suite, so criterion 7 fails for every row.
- **Tier S (PR #55) is unmerged.** That leaves 10 of the 16 H rows (H1, H3, H4, H7, H9, H11, H13, H14, H16, ADM) and the admission rule with nothing on LIVE.
- **DP5 falls from DONE to PARTIAL.** The breadth artifact is stale: the last reading is 09-16 and the dashboard is 09-22.
- **Budget is not sovereign.** `research_budget.json` is `authoritative:false` and records that no price moved any leg's seconds, which undercuts H10 and DP6.
- **The judging backlog is not being drained.** About 55,811 of 57,538 cells are unjudged, and the last dashboard shows 0 verdicts/day against about 1,028 created/day. No committed `JUDGING_RATE`.
- **#52 and #53 are unmerged** (DP3, DP7, DP8). The DSR variance constant is still on LIVE. `master` does not contain LIVE (no release promotion). There is no standby or failover, and backups are unencrypted (H12).
