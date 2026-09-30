# Blueprint verification matrix

Independent check of every blueprint the principal gave on 2026-09-29, verified against the code rather than the builders' ledgers.
**Re-scored 2026-09-30 ~10:40Z under the principal's strict definition of DONE**, against the live branch `claude/llm-auto-upgrade-verify-gcjac3` at `6c8a71a4` (after #69). The Tier S and hardening sections (B1, B2, C) were re-verified at ~11:40Z against LIVE `846ce9de` and PR #55 at `ed496c64`; each of their rows carries two mark sets, LIVE and "#55 as if merged".
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
| 16 hardening + depth priorities + admission rule | 28 | 0 | 12 | 13 | 2 | 0 | 1 |
| **Total** | **138** | **0** | **105** | **23** | **5** | **1** | **4** |

**Bottom line: 0 of 138 rows meet the strict definition.** The previous two DONEs fell:

- **D10** (evaluator drift check): 7379cbf changed `external_gauntlet.py` after the 09-29 signing, so the check it passes on is now a live breach.
- **DP5** (independent breadth): the last breadth reading is 09-16 and the dashboard 09-22, so its artifact is stale.
- **D13** (shadow.log opened per write) is correct code but cannot be DONE while CI on LIVE is red.

What stops rows reaching DONE, in order of how many rows each blocks:

1. **Red CI on LIVE** (every row): re-sign the evaluator for 7379cbf or revert it, and fix the MT5 desk suite.
2. **Nothing Tier S is on LIVE** (46 rows plus 10 H/ADM rows): PR #55 (at `ed496c64`, 54 ahead and 32 behind, merges clean) would still reach 0 DONE, because it adds two seal breaches (`promoter.py`, `rails.py`) and no Tier S artifact exists anywhere. Its only money-path authority is a withhold-only promotion door; the exchange, execution capture, constitution values and FREEZE reach no sizing or allocator code.
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

### 2026-09-30 11:40Z: Tier S batch 5 (PR #55 at `ed496c64`, LIVE at `846ce9de`)

The builder reported 42/46 layers DONE, with the promotion door, exchange tilt, authoritative research budget, alpha_rank leg budgets and k_eff judge ordering in place. Re-scored under the strict seven criteria:

| Section | On LIVE | If #55 merged as-is |
|---|---|---|
| B1 (30) | 0 DONE, 30 PARTIAL | 0 DONE, 30 PARTIAL |
| B2 (16) | 0 DONE, 16 PARTIAL | 0 DONE, 16 PARTIAL (best: T27 at 6/7) |
| C (28) | 0 DONE, 12 PARTIAL, 13 MISSING (branch-only), 2 MISSING, 1 TIME-BOUND | 0 DONE, 22 PARTIAL, 3 MISSING (branch-only), 2 MISSING, 1 TIME-BOUND |

Why no row reaches 7/7 even with #55 merged:

- **Seal (C).** #55 edits `promoter.py` and `rails.py`, both sealed judge files, without re-signing. Merging turns LIVE's one evaluator breach (`external_gauntlet.py`) into three.
- **Artifacts (R).** No Tier S artifact exists on any ref or the box: `reports/tier_s/*` is gitignored, the leg has never run on the box, and the 416 s run was measured in the cloud checkout.
- **Self-graded ledger.** "42/46 DONE" uses the ledger's own research-side definition, and `check_tier_s_program.py` checks the ledger against itself.
- **Budget.** The committed `research_budget.json` is still `authoritative:false` (09-23); no applied reading exists.
- **Door fails open.** `promoter.tier_s_block` catches every exception and returns None, so an import or firewall error silently removes all six withholds; it never touches rows already LIVE.
- **Control-arm leak.** In `allocator_tilts.build` the held-out sleeve measured 0.923 because renormalisation and capture apply to it.
- **Still pending on the desktop, on no ref:** the rails/promoter re-sign, the constitution-driven gauntlet, S12 firewall checks and FREEZE-to-allocator.

LIVE moved 32 commits since `6c8a71a4` (CRO docs, tests, release signing) with no change to a scored organ. A new committed box reading, `TIER1_BREADTH_REVIEW.json`, shows k_eff 2.526 and judging at 5,266/day against 8,303/day created, with a 1.40M backlog still growing.

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

Checked 2026-09-30 ~11:30Z. LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `846ce9de`. TIERS = `origin/claude/tier-s-institution` @ `ed496c64` (PR #55, unmerged, 54 ahead / 32 behind; `git merge-tree` merges clean onto LIVE).

**Facts behind every row (checked in the code, not the ledger):**
- **LIVE still carries no Tier S code.** No `libs/tiers/*`, no `tier_s.py`, no `tier_s` leg, no `promoter.tier_s_block`. The 32 LIVE-only commits are CRO procedure docs, the release-signing seal (#68) and a CRO ledger row. So LIVE marks are for the LIVE analogues, unchanged from the 6c8a71a4 score.
- **CI on LIVE is still red.** Run 36706441916 on `9c465f8d` failed: the LAW GATE step failed, and so did the MT5 desk suite. The run on `846ce9de` is still in progress. So C is ✗ on LIVE for every row.
- **PR #55 CI has no completed result.** Every run on the branch in the last hour ended `cancelled`, superseded by the next push. The run on head `ed496c64` is in progress.
- **Merging #55 adds two law-gate breaches.** I ran `scripts/check_immutable_evaluator.py` in a clean worktree at `ed496c64`. It reports 3 breaches:
  - `external_gauntlet.py` (inherited from LIVE);
  - `promoter.py` (`52d6f4b4` → `1041a40e`);
  - `libs/portfolio/rails.py` (`e832bd4c` → `e01e6027`).

  This is the builder's pending "rails/promoter re-sign". So C is ✗ in the #55 score for every row.
- **Tier S tests pass.** 215 tests pass in a clean worktree: `test_tier_s_{organs,door,adversarial,breadth,evolution,measurement,world}`, `tests/tiers`, `test_cycle_pricing` and `test_research_budget`. `check_tier_s_program.py` reports 42 DONE, 2 PARTIAL and 2 BLOCKED_ON_USER.
- **No Tier S artifact is committed on either ref.**
  - Not one `desks/mt5/reports/tier_s/*.json` exists, and there is no TIER_S.json.
  - `docs/research/runtime_state.json` on TIERS has no `tier_s`, `alpha_rank`, `research_bandit` or `placebo_audit` organ.
  - The committed `desks/mt5/data/research_budget.json` on both refs is dated 2026-09-23 and says `"authoritative": false`.
  - The "416 s full hourly run" exists only in the message of commit ed496c64. So R is ✗ in both scores for every row.
- **Authority that #55 really adds (code-verified):**
  1. **Promotion door.** `promoter.tier_s_block` (promoter.py:1569) is called on the main lane (:1965) and the qquant lane (:1820). It calls `promotion_authority.block`, which checks in order: constitution loosened without ratification, replication MISMATCH, online FDR over budget, review panel HIGH failure / theory REFUTED (`door_verdicts.json`), and a production immune DROP. It is withhold-only.
     - It **fails open**: `tier_s_block` wraps the call in `except Exception: return None`.
     - Every file read goes through `firewall.may(...)`, which raises `FirewallError` on a denial. So a firewall denial silently disables the whole door.
  2. **Allocator tilt.** `pf_allocator.apply_allocator_evidence` multiplies in `tier_s_factors` from `data/tier_s/allocator_tilts.json` (exchange × capture, bounded 0.5–2.0, 1.0 when the file is stale or absent). Each factor is heat-neutral. Their clipped product is not re-normalised. Capture reads 1.0 while there are 0 matched fills.
  3. **Compute pricing.** `cycle_pricing` weights are meta_controller 0.40, **alpha_rank 0.25**, research_bandit 0.20, and researcher_market / factory_contracts / evig 0.15 each. The weights change leg budgets. FLOOR is 1.0, so pricing never cuts a leg.
  4. **Bandit leg.** `research_bandit` is a core hourly leg (hourly_cycle.py:846, :3247) and now calls `publish()`.
  5. **Judge docket order.** `judge_coverage` orders the docket by `docket_keff`. It only reorders; the floor and the row set are untouched.

  The exchange, capture and FREEZE have no other money-path reach: FREEZE does not reach the allocator, the constitution does not reach the gauntlet (S01 pending), and `firewall.may` has no call site at the money-path gates (S12 pending).

Marks order: I W A T R D C. The #55 score is as if merged as-is, so D is ✓ there.

| ID | Item | Verdict | Marks | Evidence on #55 (file:line, caller, test, artifact) | Still missing | Owner |
|---|---|---|---|---|---|---|
| L1 | Truth Kernel: immutable constitution controls everything | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `libs/tiers/truth_kernel.py` + `docs/research/tier_s_constitution.json`. `promotion_authority._constitution` withholds new LIVE rows when the rule set in force loosens the sealed one without ratification (4f3b456). Leg `tier_s`. Test: test_tier_s_organs. No committed TRUTH_KERNEL.json. | The gauntlet does not read `cert.dsr_threshold`, `gates_required` or `lockbox.min_fraction` from the constitution (S01 BLOCKED_ON_USER). The door only detects a *changed* rule set; it does not bind the values. Needs a box artifact, a re-sign of promoter/rails, and green CI. | Tier S build |
| L2 | World Data OS: PIT/bitemporal + provenance + reliability | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `libs/tiers/bitemporal.py` and `data_os.py`, used only by `tier_s.py` and `acquisition_resolution.py`. Test: test_tier_s_world. | No data path reads the bitemporal store. It decides nothing. No DATA_OS.json. | Tier S build |
| L3 | World Model: causal/economic knowledge graph | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | `world_edges.py`, `world_macro.py`, `graph_edges.py`. Broken edges become compiler hypothesis rows. Test: test_tier_s_world. The only committed artifact is LIVE's `data/world_causal_graph.json` (09-08, 0 admitted edges). | It decides nothing: it only generates hypotheses. The artifact is stale. There is no flows or regional graph. | Tier S build |
| L4 | Researcher Civilization: hundreds of heterogeneous processes | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `researcher_market.py` publishes `researcher_prices.json`, which `cycle_pricing._researcher_prices` reads (cycle_pricing.py:287, weight 0.15) as a compute budget. `blinding.audit` (tier_s.py:2412). Test: test_tier_s_adversarial. | Blinding is a static audit, not enforcement. No new non-LLM researcher processes beyond the tier_s labs. No MARKET.json artifact. | Tier S build |
| L5 | Hypothesis Ecology: competing/evolving mechanism populations | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | QD, genomes and theory emit rows to `data/intelligence/tier_s/` for the compiler. Tests: test_tier_s_evolution and test_tier_s_organs. | The populations decide nothing: they are picks over the family vocabulary. No artifact. | Tier S build |
| L6 | Research-Program Evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `libs/tiers/program_evolution.py` evolves portfolio, execution, regime, scheduler and search-policy programs (6085d78), inside the `tier_s` leg. Test: test_tier_s_evolution. | The evolved programs are challengers and report only. None replaces a running scheduler or pipeline. No GENOMES.json. | Tier S build |
| L7 | Adversarial Science: researchers vs destroyers co-evolve | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `red_queen.py` attacks the production `run_gauntlet` and attributes attacks per researcher, with 3 new attack kinds (12ec9d2). Test: test_tier_s_adversarial. | A winning defender never changes the production gates: `red_queen` is read only by tier_s, authority, review_panel and self_model. No RED_QUEEN.json. | Tier S build |
| L8 | Universal Validation: anti-selection/anti-leakage | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: universal gate / `external_gauntlet`. #55 adds FDR, immune, replication, review and theory to the door (promotion_authority.py `block`). Tests: test_tier_s_door and test_tier_s_organs. | The DSR variance is still constant, so the certifier has zero power. #52 lockbox is unmerged. The door fails open. The evaluator breach must be re-signed. | Both threads |
| L9 | Alpha Topology: true independent dimensions | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `factory_contracts.leg_alpha_rank` feeds `cycle_pricing` at weight 0.25 (9b4ab6a, cycle_pricing.py:434). `docket_keff` orders the judge docket (judge_coverage.py:743). Tests: test_cycle_pricing and test_tier_s_breadth. | No ALPHA_RANK.json, TOPOLOGY.json or DOCKET_KEFF_ORDER.json is committed or evidenced. Authority is compute ordering only. Two rank organs are still unreconciled. | Tier S build |
| L10 | Portfolio Intelligence: posterior E[log W] | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `pf_allocator.py:2094` reads `tier_s_factors`, which read `data/tier_s/allocator_tilts.json`. The exchange tilt is heat-neutral and bounded 0.5–2.0 (7508c3f). Test: test_tier_s_organs. | The clipped product of the two factors is not re-normalised to heat-neutral. No allocator_tilts.json has been seen. #53 floors are still unmerged. UNMEASURED admission keeps capital. | Other slices |
| L11 | Execution Intelligence: learned implementation optimum | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `capture_raw` in `libs/tiers/allocator_tilts.py` tilts the allocator by measured capture. `execution_science` leg runs hourly. Test: test_tier_s_organs. | With 0 matched fills, capture reads 1.0, so the tilt is inert. Nothing learns the execution method itself. `cost_surfaces` is unconsumed. No EXECUTION_SCIENCE.json. | Other slices |
| L12 | Live Reality Engine: backtest reconciled to reality | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | `door_evidence.py`: THEORY_REFUTED on forward, live or replication evidence withholds promotion (9c97a12). Prediction accounting runs in tier_s. Test: test_tier_s_door. `data/forward_reconcile.json` is committed on LIVE. | Live evidence withholds only; it does not size. accounted_share is about 0, n is tiny. Needs green CI and a re-sign. | Other slices |
| L13 | Meta-Science: which methods create edge | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `research_bandit` is an hourly core leg calling `publish()` (565963706). The researcher market and factory_contracts price legs. Tests: test_research_budget and test_cycle_pricing. | The committed `research_budget.json` still says `authoritative:false` (09-23). No box RESEARCH_BANDIT.json shows the authority stamp. | Tier S build |
| L14 | Architecture Evolution: system proposes self-improvements | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | twin and self_model run in tier_s. Research challengers adopt. Test: tests/tiers. | Money-path challengers are PROPOSE only (S30 BLOCKED_ON_USER). No TWIN.json. | Other slices |
| L15 | Operational Kernel: reproducible, redundant, deterministic | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | replay and chaos in tier_s; `chaos.process_kill_drill` runs on a temp copy. Test: tests/tiers. | Report only. No standby or failover. The gateway has not been tested in a sandbox (S42 PARTIAL). | Other slices |
| T1 | Truth Kernel: agents cannot change PIT/trials/cost/lockbox/cert/capital/provenance/repro rules; content-addressed raw→fill; reconstruct any trade | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | Journal and seal in `truth_kernel.py`. The constitution-change detector sits at the door (`promotion_authority._constitution`). Test: test_tier_s_organs (door sandbox a37bd50). | The constitution's values are not bound in the gauntlet or the allocator. There is no inline order-time lineage. The ledger holds S01 at BLOCKED_ON_USER itself. | Tier S build |
| T2 | World Data OS: bitemporal, per-datapoint provenance/revisions/latency/licence/reliability; acquisition by info-gain per € | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `bitemporal.py`, `data_os.py`, `acquisition_resolution.py` (gate-yield acquisition, 1ff0ab5). Test: test_tier_s_world. | No data path uses the store. The acquisition ranking does not feed `acquire_datasets`. No € costs. The ledger claims S02 DONE. | Tier S build |
| T3 | World model: rates→FX→…→flows graphs, regional; stable/state-dependent/decaying/false; hypotheses from broken edges | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | `world_edges` classifies edges. Listed edges go into WORLD_SCIENCE.json (d2f8854). Residual rows reach the compiler. Test: test_tier_s_world. | Flows and regional graphs are missing. It decides nothing. The LIVE artifact is stale with 0 admitted edges. | Tier S build |
| T4 | Researcher civilization with ~25 epistemologies incl. non-LLM; some blind to others | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | Seat blinding via `blinding.audit` (tier_s.py:2412) and a firewall seat table. Test: test_tier_s_adversarial. | Blinding is audited, not enforced: nothing stops a cohort reading another. The independent-discovery count is not evidenced above 0. The ledger claims S04 DONE. | Tier S build |
| T5 | AlphaEvolve-for-alpha: LLM + evaluators evolving code, grammars, portfolio/regime/execution/scheduler programs; fitness = validated independent alpha per compute | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `evolution.py` and `program_evolution.py`. The grammar is read by `expression_factory.py:90`. Test: test_tier_s_evolution. | There is no LLM-in-the-loop code evolution. Evolved programs are report or challenger only. No GENOMES.json. | Tier S build |
| T6 | MAP-Elites over 12 descriptor axes | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `qd_axes.py` adds the capacity and correlation-cluster axes (dc99578). `research_diversity_archive`. Test: test_tier_s_evolution. | The archive steers nothing with authority. No QD.json. | Tier S build |
| T7 | Evolve researcher genomes; fitness = validated independent info / compute with penalties | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | RESEARCHER_GENES in `evolution.py`. The `falsify_order` allele ranks candidates. Test: test_tier_s_evolution. | Genomes steer only tier_s's own rows. There is no evidence of fitness above 0 on any box (the last cloud run showed 0). The ledger claims S07 DONE. | Tier S build |
| T8 | Researcher market: posteriors, bandits/Bayesian allocation, deteriorating lose compute | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `researcher_market.allocate` writes `researcher_prices.json`, read by cycle_pricing at weight 0.15. The `research_bandit` hourly leg feeds weight 0.20. Tests: test_cycle_pricing and tests/tiers. | The per-researcher MILP budgets go unused (only per-leg price). With FLOOR 1.0, a deteriorating researcher never *loses* compute below base. No artifact. `research_budget.json` is authoritative:false. | Tier S build |
| T9 | Red Queen per-researcher adversary (15 attack kinds), counter-agent, co-evolve | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | Per-researcher attribution and 3 new attack kinds (12ec9d2). Validator genomes compete (S33). Test: test_tier_s_adversarial. | A winning defender does not change the real gates. No RED_QUEEN.json. The ledger claims S09 DONE. | Tier S build |
| T10 | Planted traps (blind), immune score, FREEZE production when traps accepted | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `promotion_authority._freeze` withholds on a fresh production DROP. `traps.py` and `meta_benchmark.py`. Test: test_tier_s_organs. | FREEZE does not reach the allocator (freeze-to-allocator is pending). Traps are not injected blind into the live stream. Immune = 1.0 is vacuous while certifier power is 0. No IMMUNE.json. | Tier S build |
| T11 | Adaptive multiplicity: lifetime genealogy + online FDR / sequential / e-values | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `online_fdr.py` LORD++/e-LOND. `_fdr` withholds when a row is `over_budget` in ONLINE_FDR_ROWS.json. Test: test_tier_s_door and test_tier_s_organs. | Lifetime trials are only in #52, which is unmerged. p-values are proxies. There is no anytime-valid forward test. No ONLINE_FDR_ROWS.json. | Tier S build (+ #52) |
| T12 | Epistemic firewall, physically isolated roles | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `firewall.py` has developer and lockbox roles in its static table (6b0c708). `may()` is called only in promotion_authority, blinding and tier_s. Test: test_tier_s_adversarial. | There are no runtime `may()` / `lockbox_accepts` calls at the gates (S12 pending). There is no OS or process isolation. A denial raises inside `tier_s_block`'s `except Exception`, so it **disables** the door instead of blocking. | Tier S build |
| T13 | Negative knowledge: typed causes, graph, retrieval for new candidates, "explored N times" → move on | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `failure_memory.py` (15 causes and theorems) is read only by tier_s and authority. LIVE's `negative_knowledge` is read by `gauntlet_backpressure` (which carries the A). Test: tests/tiers. | Other generators do not read failure_memory (meta_desk only names the string). There is no evidence of more than 0 theorems. No FAILURE_MEMORY.json. The ledger claims S13 DONE. | Tier S build |
| T14 | Ancestry graph: code/feature/hypothesis/data ancestry + P&L/tail similarity; derived not counted fresh | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `topology.effective_discoveries`. The ancestry channel feeds alpha_rank, which reaches cycle_pricing at weight 0.25. Test: test_tier_s_measurement. | Only compute is discounted, not counts or gates. There is no code or data ancestry. No TOPOLOGY.json. | Tier S build |
| T15 | Effective Independent Alpha Rank (PnL, eigen, nonlinear, tail, DD, ancestry, exposure, overlap, mechanism, regime); scheduler searches orthogonal | PARTIAL (closest to DONE) | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `alpha_rank` prices legs directly at weight 0.25 (cycle_pricing.py:434). The judge docket is ordered by marginal k_eff (`docket_keff.py`, judge_coverage.py:743). Drawdown is in topology (S15). Tests: test_cycle_pricing and test_tier_s_breadth. | A box ALPHA_RANK.json and DOCKET_KEFF_ORDER.json. Green CI and a promoter/rails re-sign. The rank organs are still two (alpha_rank vs topology). | Tier S build |

Counts on LIVE: DONE 0 / PARTIAL 30 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (30 rows)
Counts if #55 merged: DONE 0 / PARTIAL 30 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (30 rows). Every row fails R, because no Tier S artifact is committed or evidenced. Every row fails C: CI has not completed on #55, and the evaluator has 3 breaches at `ed496c64`.

### Ledger claims that fail
- **"42/46 DONE" means something weaker than strict DONE.** The ledger's own definition of DONE is "runs hourly + writes artifact + research-side wording". Yet not one of the 42 claimed artifacts (`desks/mt5/reports/tier_s/*.json`) is committed, and TIERS `runtime_state.json` has no `tier_s` organ.
- **"Research_bandit publishes an authoritative budget hourly": the code is real, the evidence is not.** The leg exists (hourly_cycle.py:3247) and calls `publish()`. But the committed `desks/mt5/data/research_budget.json` on TIERS still says `"authoritative": false` (09-23).
- **S02 DONE fails.** `BitemporalStore` is used by no data path, only `tier_s.py`, `data_os.py` and `acquisition_resolution.py`.
- **S04 DONE fails.** Blinding is `blinding.audit(...)`, a static report. No cohort is stopped from reading another.
- **S09 and S13 DONE fail.** The Red Queen's winning defender changes no production gate. `failure_memory` is read by no generator outside tier_s.
- **S10 and S11 DONE are withhold-only, and the door fails open.** `tier_s_block` swallows every exception, including the `FirewallError` that `firewall.may` raises inside `block`. FREEZE-to-allocator is still pending.
- **The tier_s rows claim DONE while TIERS breaches the immutable evaluator.** `check_immutable_evaluator.py` at `ed496c64` finds 3 breaches (`promoter.py`, `rails.py`, `external_gauntlet.py`). Merging makes the LAW GATE red for two new reasons.
- **"416 s full hourly run" is unevidenced.** It appears only in commit message ed496c64 and has no committed artifact. No CI run on #55 has completed: all were cancelled, and the head run is in progress.

### Top gaps
- **Re-sign `promoter.py` and `rails.py` (and resolve `external_gauntlet.py`), then get one completed green CI run on #55 and on LIVE.** Until then C fails on all 30 rows, merged or not.
- **Produce and commit (or publish) one box run of the `tier_s` leg.** It should include TIER_S.json, TOPOLOGY/ALPHA_RANK, ONLINE_FDR_ROWS, IMMUNE, `allocator_tilts.json` and an `authoritative: true` `research_budget.json`. R fails everywhere without it, and this is the single change that could move rows L9, L10, L13, T8, T11 and T15 to DONE after merge.
- **Make the door fail closed, or at least loud.** Today the broad `except Exception: return None` in `promoter.tier_s_block` lets any import or firewall error remove all six withholds silently.
- **Authority is still missing where the rows ask for it:**
  - the constitution's values are not bound in the gauntlet (S01);
  - there are no runtime firewall checks at the gates (S12);
  - FREEZE does not reach the allocator;
  - the Red Queen defender does not reach the production gates;
  - blinding is not enforced;
  - the bitemporal store is not on the data path.
- **Execution-capture authority is structurally present but inert.** With 0 matched fills every capture factor is 1.0. Only the exchange tilt can move capital today.
- **Merge #55 (it merges clean onto `846ce9de`).** The LIVE branch has no Tier S code at all, so every row fails D and most fail I on LIVE.

## B2 — Tier S sections 16–30 (T) and final loop

LIVE = origin/claude/llm-auto-upgrade-verify-gcjac3 @ 846ce9de. TIERS = origin/claude/tier-s-institution @ ed496c64 (PR #55, **draft**, unmerged, 54 ahead / 32 behind LIVE, base 6c8a71a4).
Marks: I W A T R D C, in that order. "#55" is scored as if #55 were merged unchanged.

Checks run for this re-score:
- **LIVE has no Tier S code.** `git ls-tree` shows no `libs/tiers`, no `tier_s.py` and no Tier S tests. The 32 commits since 6c8a71a4 are CRO-cycle documents, the release seal and the blueprint re-score.
- **CI on LIVE is red.** PR #82 (latest LIVE merge): `quality` failed and `mt5-money-path` failed. #55's own CI was still in progress at read time.
- **#55 fails C on its own terms.** `check_immutable_evaluator.py` in a detached #55 worktree reports 3 breaches: `external_gauntlet.py` (inherited from LIVE), plus `promoter.py` and `libs/portfolio/rails.py`, both new from #55. The PR body admits these are unsigned. So no row can reach 7/7 on merge.
- **Tier S tests pass.** 7 Tier S desk test files + `tests/tiers` all passed in the worktree. `check_tier_s_program.py` prints "DONE 42; PARTIAL 2; BLOCKED_ON_USER 2" (a self-check of its own ledger).
- **No Tier S artifact is committed on #55.** No `desks/mt5/data/tier_s/*`, and `reports/**` is gitignored. The box pulls LIVE only, so `tier_s` has never run there. Every Tier S R is ✗.
- **The tilt reaches the gateway's book (verified).** `tier_s.organ_exchange` → `_allocator_tilts` → `data/tier_s/allocator_tilts.json` → `allocator_evidence.tier_s_factors` (fresh ≤ 6 h) → `pf_allocator.apply_allocator_evidence` (factor `sf`, pf_allocator.py:2099–2120, called at :3312 before the solve) → `reports/pf_allocation.json`. The gateway reads that file, and `data/PF_ALLOCATOR_ARMED` is committed on LIVE. The path holds. But `tier_s` is a non-core "meta" leg under leg rotation with a 1,500 s cap, so a deferred pass beyond 6 h makes the tilt silently neutral.
- **The tilt is not cleanly heat-neutral, and the control arm leaks.** `allocator_tilts.build` sets a held-out sleeve's raw factor to 1.0 and then renormalises every sleeve by the heat-weighted mean. With A=0.15, B=0, C held out (live 0.05 each), I measured C's tilt at **0.923, not 1.0**. The capture factor also applies to held-out sleeves. The product ex×cap (clipped) is not mean-1, and it is multiplied with six other factors and clipped again.
- **FREEZE does not reach the allocator (confirmed pending).** `promotion_authority._freeze` withholds new LIVE rows only. `allocator_tilts.py`, `tier_s._allocator_tilts` and `tier_s_factors` never read `PROMOTION_FREEZE.json`.
- **The door fails open.** `promoter.tier_s_block` catches every exception and returns None. Any import or firewall error withholds nothing.
- **The DSR variance is still the constant 0.014863** on #55 (`effective_trials.py:309`), so every withhold-only door is untestable against genuine edges.

| ID | Item | Verdict | Marks | Evidence on #55 | Still missing | Owner |
|---|---|---|---|---|---|---|
| T16 | Counterfactual World Lab | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | `synthetic_regimes.py` now has the swap world (`swap_world.NAME`) and `correlations_to_one`. `organ_worlds` joins worlds per certificate. Tests: `test_tier_s_world` (swap world ×4). The only authority is indirect: the panel's `stress_x5_positive` resolver can withhold. | Market-closure world. Agent-based market. Causal counterfactuals joined to survivors. A break flag that blocks or queues work. A committed artifact. | Tier S build |
| T17 | Alpha Theory Compiler | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `libs/tiers/theory.py` (7 slots). `compile_mechanism` is tested in `test_tier_s_kernels`. Recipes go to `data/intelligence/tier_s/`, which the compiler reads (hourly `tier_s` leg). | Composition untested (no test calls `compose`). Output is candidate input only, with no authority. Needs a box artifact, a merge, and C (re-sign). | Tier S build |
| T18 | Theory↔Evidence graph | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `door_evidence.oos_posterior` (forward/live/replication only, MIN_OOS=10) → `THEORY_REFUTED` withholds a new LIVE row through `promotion_authority._panel_and_theory`. `theory_context` adds jurisdiction and regime. Tests: `test_tier_s_door::test_theory_ignores_backtest_and_needs_min_oos`, `test_theory_posterior_weights_live_over_backtest`. | Withhold-only and fail-open. With MIN_OOS=10 per family the door rarely binds. No `door_verdicts.json` has been produced. C fails (promoter unsigned). | Tier S build |
| T19 | Heterogeneous non-LLM intelligence | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | `cross_science.py` (Kalman, spectral, TE, LV, recurrence, MCMC) is now tested (`test_tier_s_measurement`, `test_tier_s_organs::test_science_rows_test_each_hit_as_its_own_mechanism`). It drains through expression_factory. | No SAT/SMT solver or theorem prover. The output is research input only, with no budget authority. No committed artifact. | Tier S build |
| T20 | AI peer review panels | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `review_panel.py` (8 rule reviewers, typed challenges). A HIGH `forward_n_40` or `stress_x5_positive` failure → `REVIEW_PANEL_FAILED` withholds a new LIVE row (`door_evidence.review_failed`). Tests: `test_tier_s_door`, `test_tier_s_adversarial::test_the_panel_carries_the_conflict_flag`. | Reviewers are fixed if-rules, not independent instances. Challenges do not spawn experiments. Withhold-only and fail-open. No artifact. C fails. | Tier S build |
| T21 | Auto-invent new tests | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `test_invention` is confirmed on a second (real-episode) suite, with a redundancy matrix. Tests: `test_labelled_real_suite_invents_a_gate_that_holds_on_both_halves`, `test_invent_from_needs_cases`. | `tier_s_ratifications.jsonl` is empty (0 bytes), so no invented gate is enacted: no authority. The DSR constant makes the benchmark powerless. No artifact. | Tier S build |
| T22 | Auto-invent research grammars | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | `grammar_bias.bias()` is read by expression_factory, alpha_evolution and alpha_grammar (sampling weights learned from winners). Test: `test_grammar_round_trip_and_learned_bias`. | It reweights a fixed DSL and invents no representation class (state machines, event sequences, cross-sectional operators). Sampling bias is not budget authority. No artifact. | Tier S build |
| T23 | Execution as autonomous science | PARTIAL | LIVE: ✗✓✗✗✗✗✗ / #55: ✗✓✓✗✗✓✗ | `execution_science` is an hourly leg (`--apply`). Execution capture (live R / forward exp_r, shrunk n/(n+20)) reaches `pf_allocator` as a posterior tilt, verified end to end. | No test of `execution_science.py`. With `matched_fills` = 0, capture is 1.0 in practice. No slicing, spread prediction, adverse selection or urgency. No `EXECUTION_SCIENCE.json` committed. | Tier S build |
| T24 | No-trade first-class | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✗✓✓✓✓✓✗ | Unchanged on LIVE (`pf_allocator.no_trade`, `pf_forecast_log.jsonl`). On #55 the exchange's DEFER/0-weight reaches the allocator only as a tilt floored at 0.5 (`exchange_raw` clip, KAPPA 0.5 → ≥0.75 before renormalising). It can never make zero. | #53 (min-lot and gold floors still override a zero). DEFER and ALT_EXPRESSION in the live allocator. Opportunity cost in the edge test. | Tier S build / Institutional (#53) |
| T25 | Opportunity Exchange | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `opportunity_exchange.clear` → `allocator_tilts.json` → `tier_s_factors` → `pf_allocator` (factor `sf`) → `pf_allocation.json`, which the ARMED gateway reads. Tests: `test_allocator_tilts_are_heat_neutral_two_sided_and_hold_out`, `test_allocator_reads_tier_s_tilts_fresh_only`, `test_exchange_fills_the_heat_floor...`. | The control arm leaks: the held-out sleeve measured 0.923, not 1.0. The tilt is silently neutral if the rotated `tier_s` leg misses 6 h. No box artifact. C fails (rails.py and promoter unsigned). | Tier S build |
| T26 | Live prediction-accounting | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✓✓✗✓✗ | `prediction_accounting` now forecasts mae_r, mfe_r, hold_h and slip_r prequentially (tests in `test_tier_s_measurement`). Honesty feeds researcher prices → `cycle_pricing` (compute) and the exchange bid μ (tier_s:3006) → allocator tilt. | No vol, factor-exposure or correlation forecasts. No per-model forecasts. No artifact. C fails. | Tier S build |
| T27 | Live reality outranks backtests | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✓✓✓✓✓✓✗ | The LIVE half is unchanged (`_posterior_mu`, `pf_forecast_log.jsonl`). The factory-honesty penalty now reaches `cycle_pricing` (via researcher_prices) and existing sleeves' exchange bids → pf_allocator tilt. | No test covers the honesty channel. The penalty does not reach admission or priors for NEW discoveries. The live sample is small (time-bound part). Only C blocks 7/7: CI and law-gate breaches. | Tier S build |
| T28 | Digital twin (shadow desk) and rollback | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✗✓✗✓✗ | `twin.evaluate` (paired, registered-after-only) is tested. `organ_twin` runs hourly. `rollback.py` / `tier_s --rollback-to --apply-rollback` exists. | No shadow copy of the desk on new code versions. Rollback is untested (no test references `rollback`) and needs a human command. No controlled promotion from the twin. No artifact. | Tier S build |
| T29 | Self-model | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `self_model` inventory now includes operational rows. `SELF_MODEL_DOCKET` reaches `implementer._self_model_rows`. Tests: `test_self_model_ranks_deficiencies`, `test_self_model_docket_reaches_the_implementer`, `test_operational_inventory_rows_and_unmeasured`. | Implementer intake is not budget, sizing or promotion, so no authority. p_fix and cost are hand constants. No box artifact. | Tier S build |
| T30 | Architecture evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✗✓✗✓✗ | Red Queen registers architecture, scheduling and search-policy challengers (`test_red_queen_registers_architecture_challengers`). Research challengers adopt automatically. The builder's own ledger marks it BLOCKED_ON_USER. | Money-path challenger adoption is refused. A BLOCKED regression does not stop Adopt-And-Seal. No proposals for DBs, sources or refactors. No artifact. | Tier S build |
| LOOP | Closed research→capital loop inside a Truth Kernel | PARTIAL | LIVE: ✗✓✗✗✗✗✗ / #55: ✗✓✗✗✗✓✗ | Adds hypothesis→compiler, market→cycle_pricing, alpha_rank→cycle_pricing (0.25), an hourly research_bandit (CORE leg, runs before alpha_evolution), exchange and capture → pf_allocator tilt, and a 6-verdict withhold door (constitution, replication, FDR, panel, OOS theory, FREEZE). | #52 lockbox and #53 are not merged. FREEZE does not reach the allocator (patch "prepared", not on any ref). The door fails open. DSR constant 0.014863. S01 constitution-driven gauntlet and S12 runtime firewall are not done. No end-to-end loop test. No box artifact for any node. Evaluator and rails re-sign needed. | Tier S build / Institutional (#52, #53) |

Counts on LIVE: DONE 0 / PARTIAL 16 / MISSING (branch-only) 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (16 rows)
Counts if #55 merged: DONE 0 / PARTIAL 16 / MISSING 0 (16 rows). Best is T27 at 6/7; T18, T20 and T25 are at 5/7. C fails everywhere: 2 new immutable-evaluator breaches, red CI on the base, and a self-graded ledger.

### Ledger claims that fail
- **All 42 DONEs are self-graded.** The ledger's own `statuses.DONE` means "meets the wording **on the research side**", and `check_tier_s_program.py` validates the ledger against itself. Every `artifact` it cites is under the gitignored `reports/tier_s/`, and none exists on any ref.
- **S25 DONE** ("Opportunity exchange… (shadow)"). The tilt does reach pf_allocator, but the "held-out control arm" is contaminated: the held-out sleeve measured 0.923, because renormalisation and capture both apply to it. "Heat-neutral" holds only for each factor before the product and the second clip.
- **S23 DONE.** The only file listed is `execution_science.py`, which has no test and no committed report. Capture is 1.0 while matched_fills = 0. None of slicing, spread prediction, adverse selection or urgency exists.
- **S24 DONE** ("No-trade as a first-class action"). The exchange's DEFER reaches the live book only as a tilt floored at 0.5, so it cannot produce a zero. LIVE's min-lot and gold floors (#53 unmerged) override zeros anyway.
- **S28 DONE** ("one-op rollback"). `rollback.py` has no test, needs a human `--apply-rollback`, and there is no shadow desk.
- **S21 DONE.** `tier_s_ratifications.jsonl` is 0 bytes, so no invented test has ever gated anything.
- **S16 DONE** ("sixteen stress worlds"). No market-closure world, no agent-based market, and no consumer that acts on a break.
- **PR claim that the door "withholds on … immune freeze".** True for new rows only. It fails open on any exception (`promoter.tier_s_block` catches everything and returns None), and FREEZE reaches no sizing code, as the PR itself admits ("patch prepared").

### Top gaps
- **Merging #55 still reaches 0 DONE.** It adds two immutable-evaluator breaches (`promoter.py`, `rails.py`) on top of LIVE's `external_gauntlet.py` breach, and LIVE CI (#82) is red on `quality` and `mt5-money-path`.
- **Zero artifacts.** The `tier_s` leg has never run on the box (the box pulls LIVE only), `reports/**` is gitignored, and no `data/tier_s/*` is committed. Every Tier S row fails R.
- **Authority is real but narrow.** It is one sizing channel (the exchange and capture tilt, bounded [0.5, 2], neutral when stale for more than 6 h under leg rotation) plus a withhold-only, fail-open door. Theory, test invention, twin, self-model and architecture evolution decide nothing.
- **FREEZE→allocator and the rails/promoter re-sign exist only on the desktop.** They are not on any ref, so they cannot be scored.
- **The control-arm leak in `allocator_tilts.build`** makes the exchange's own attribution unmeasurable. The fix: pin held-out sleeves to 1.0 after renormalising, and exclude them from capture.
- **The DSR constant 0.014863 and unmerged #52/#53** still cap LOOP, T24 and every withholding door, whatever #55 does.

## C — 16 hardening items (H), depth priorities (DP), admission rule (ADM)

Re-scored 2026-09-30 ~11:40Z. LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `846ce9de`. #55 = `origin/claude/tier-s-institution` @ `ed496c64` (unmerged; merge base `6c8a71a4`; 54 ahead / 32 behind; `git merge-tree` merges it into LIVE with no conflicts).
Marks are in the order I W A T R D C. "#55" means scored as if #55 were merged into LIVE as-is. So D is ✓ wherever #55 code exists, and R is ✓ only when a committed or box artifact exists today.

**What changed since 6c8a71a4.** LIVE moved 32 commits:
- CRO-cycle docs and tests (#70–#82) and release signing (#68, `libs/ops/release.py`, `ops/release_authority.py`), plus `refresh_tail.py`.
- A committed box reading, `desks/mt5/reports/TIER1_BREADTH_REVIEW.json` (09-30 11:45Z, source `BOX`). It gives k_eff 2.526 on 453 nominal, with 6 of 15 clusters empty. It reports 5,266 judged/day against 8,303 created/day, and the `judging_throughput` leg times out every pass. The backlog is 1,398,727 and growing, with the oldest item 773.9 h old. 837/837 certificates are enrolled.
- No change to any C-row organ. #52 and #53 are still unmerged. The DSR variance constant 0.014863 is still at `effective_trials.py:309` on both refs.

**CI and seal.**
- LIVE CI: the latest completed run 36706441916 on `9c465f8d` FAILED. The LAW GATE log reads `BREACH desks/mt5/scripts/external_gauntlet.py: changed since signing (baa3071c220e9ce2 -> cccb6ff611845474)`, and the MT5 desk suite also fails. The run on `846ce9de` (36707947135) was still in progress when checked.
- Seal on LIVE: the sha256 of `external_gauntlet.py` is `cccb6ff61184547…` against `baa3071c220e9ce2` in `desks/mt5/data/IMMUTABLE_MANIFEST.json` (signed 09-29T23:15 by zuck). That is 1 breach out of 18 frozen files.
- Seal on #55: running `scripts/check_immutable_evaluator.py` in a clean #55 worktree reports 3 breaches. They are `external_gauntlet.py`, `desks/mt5/research/promoter.py` (`52d6f4b4…` → `1041a40e…`) and `libs/portfolio/rails.py` (`e832bd4c…` → `e01e6027…`). The manifest was not re-signed. So merging #55 as-is makes the law gate worse, and C is ✗ for every row on both scores.
- #55 tests: the Tier S suites pass in the isolated worktree. They are `tests/tiers`, `desks/mt5/tests/test_tier_s_{door,organs,adversarial,breadth,evolution,measurement,world}.py` and `test_cycle_pricing.py`. The #55 CI checks were still in progress.

**#55 Tier S artifacts.** They are all written to `desks/mt5/reports/tier_s/*` (gitignored) and `desks/mt5/data/tier_s/*` (not in the tree). None is committed, none exists on the box (the box pulls LIVE), and the 416 s run was "measured in the cloud checkout" (hourly_cycle comment). So R is ✗ for every Tier S organ. `docs/research/tier_s_ratifications.jsonl` is empty. `docs/research/research_budget.json` on #55 is still the 09-23 file with `authoritative:false`.

**Verdict classes.** Rows with nothing on LIVE whose fix sits on an unmerged branch are now classed MISSING (branch-only), as the verdict rules require. The 10:40Z pass had them as PARTIAL.

| ID | Item | Verdict | Marks | Evidence | Still missing | Owner |
|---|---|---|---|---|---|---|
| H1 | Formal verification of money path | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `libs/tiers/formal.py` (BFS model check of an abstract order protocol) and `conformance.py` (AST check of gateway send sites) run inside the `tier_s` leg (`tier_s.py:2505-2550`). Tests: `tests/tiers/test_money_path_specs.py`. Nothing reads `FORMAL.json`, and neither `release_authority.py` imports them. | A failed proof or conformance check must block release or seal. Needs a committed proof artifact and green CI. | Tier S |
| H2 | Independent evaluator civilization | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: `check_immutable_evaluator.py` runs in the law gate and is the check now failing CI. #55: the review panel's HIGH failure withholds a new LIVE row (`promotion_authority._panel_and_theory` → `promoter.tier_s_block`, `promoter.py` +1820/+1965). `firewall.may()` is called only inside `promotion_authority`. S12 is self-reported PARTIAL. | No separate stack or hidden data. There are no runtime firewall calls at `universal_gate` or `external_gauntlet`, because those are signed files. The door fails open on a stale or unimportable verdict. It is not tested on a box artifact. | Tier S |
| H3 | Architecture evolution, sealed suites | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `libs/tiers/twin.py` plus `tier_s.py:3285-3351`: validator challengers are re-scored on the sealed suite and marked ADOPTED. The adopted object is a `meta_benchmark.ValidatorConfig` genome, not the real gauntlet. Money-path challengers are "a PROPOSAL the principal must accept" (S30 BLOCKED_ON_USER). | Adoption must change the real gauntlet, scheduler, solver or execution. | Tier S |
| H4 | Immutable meta-benchmark, thousands of cases | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `meta_benchmark.py`, `traps.py`, `real_episodes.py`. `PROMOTION_FREEZE.json` is consumed at the door (`promotion_authority._freeze`), but only for a production-judge DROP ("fell"). An absolute floor is report-only. | Not a release gate. FREEZE does not reach the allocator (still pending on the desktop). The DSR variance is still the constant. No committed immune score. | Tier S |
| H5 | Active information acquisition (EVOI) | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | LIVE: legs `data_acquisition_scientist`, `value_of_data` and `evig_acquisition` with their tests. #55 adds `acquisition_resolution.py`, which calibrates predictions on arrival. | Nothing buys or acquires data on its value. No pricing of timestamp, depth or history quality. No fresh artifact. | Tier S |
| H6 | Research-search frontier estimator | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: `frontier_map.py` (report). #55: Chao1/Good-Turing `frontier.py`. Its `grounds.unseen` gives a factor of 1+share on researcher prices (`tier_s.py:2356-2370`). `researcher_prices.json` feeds `cycle_pricing._researcher_prices` (weight 0.15), and that feeds `applied_budget` leg seconds. | The factor can only raise a price (FLOOR 1.0). The price came from the prior hour and fails open. No committed artifact. | Tier S |
| H7 | Epistemic uncertainty engine, 5 levels | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `libs/tiers/epistemic.py`, run by the `tier_s` leg. `EPISTEMIC.json` has no reader anywhere in #55 outside tests. | A consumer that refuses to act on "not enough evidence". Coverage of every key quantity. | Tier S |
| H8 | Cross-engine independent replication | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: `replication_civilization.py` hourly leg with its test; its verdict has no decision reader. #55: `promotion_authority._replication` withholds a new LIVE row on MISMATCH/DISAGREE/FAIL. | It is not a second engine or stack. No committed `REPLICATION.json`. Holds already LIVE are untouched. | Tier S |
| H9 | Counterfactual failure search, architecture level | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `formal.ablations()` (protocol knob ablations), `failure_worlds.py`, `red_queen.py`. Report-only. | No search over factory, allocator or world-model false confidence, agent correlation or selection bias that changes anything. | Tier S |
| H10 | Compute OS (CPU/GPU/RAM/net/tokens) | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE `hourly_cycle.py:499` `applied_budget`. The committed `research_budget.json` (09-23) says `authoritative:false`. #55 runs `research_bandit.main()` hourly before the spending legs and adds alpha_rank (0.25) and researcher_market (0.15) weights. `applied_budget` sets real leg timeouts. | CPU seconds only; no GPU, RAM, network or tokens. The factor range is 1.0–2.0, so it lengthens or reorders legs and never cuts one. No committed `CYCLE_PRICING` or `research_budget` with `authoritative:true`. | Tier S |
| H11 | Global state replay at any second | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `libs/tiers/replay.py`: ledgers are re-derived from streams. `REPLAY.json` has no reader. | Market, model-version and budget state. Fill reconstructibility. A consumer. | Tier S |
| H12 | Continual recovery / chaos experiments | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | LIVE `run_restore_drill.py` (weekly timer), `dr_drill.py`, `test_control_plane_chaos.py`. #55 `chaos.py` runs drills on copies, and its own ledger marks S42 PARTIAL. | No real process kill, MT5 disconnect or VPS-loss drill. No standby or failover. Backups are unencrypted. No committed drill artifact. | Tier S |
| H13 | Mechanism discovery from non-finance fields | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `cross_science.py` and `science_labs.py`. The rows are drained by `expression_factory.py:1729-1785` as `cross_science:<lab>` cells for the compiler. | No box evidence of any conversion to a judged or certified cell. | Tier S |
| H14 | Automated abstraction discovery | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `evolution.abstractions`. `grammar_bias.bias` is read by `expression_factory.py:90` from `data/tier_s/grammar.json`. | No committed `grammar.json`. The last recorded run learned 0 primitives. | Tier S |
| H15 | Scientific memory compression | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | LIVE `negative_knowledge.py` (daily). #55 `failure_memory.py`; `tier_s._explored` orders only tier_s's own emitted rows ("ORDER, NEVER A FILTER"). | Researchers do not consume it as authority. No theorem or mechanism-map layer reaches another organ. No fresh artifact. | Tier S |
| H16 | Human–machine separation of powers | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `truth_kernel.py` and `tier_s_constitution.json`. `promotion_authority._constitution` withholds new LIVE rows while an unratified loosening stands. | The gauntlet does not read the constitution (S01 BLOCKED_ON_USER). The ratification ledger is empty. Rails and promoter are not re-signed. | Tier S |
| ADM | Subsystem admission rule (8 gains) | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `contracts.py` and `control_arm.py` produce ADMITTED/REJECTED/UNMEASURED hourly. `authority.suspended()` removes a REJECTED Tier S organ's steering (cycle_pricing, door, frontier). `check_tier_s_program.py` is added to the law gate (`run_law_gate.py:154`) and passes: 42 DONE / 2 PARTIAL / 2 BLOCKED. | It applies to Tier S organs only, not LIVE organs. Nothing is removed. No committed admission verdicts (`AUTHORITY.json`). | Tier S |
| DP1 | Finish/wire everything | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | LIVE `tier5_audit.json` (216 / 52 PARTIAL / 3 / 1) is checked by the law gate. #55 adds `tier_s_program.json` at 42/46 DONE. That figure is self-graded: every DONE cites a gitignored report path. | The 52 PARTIAL. Box TIER1 review: 101 silent scheduled failures and 71 NOT_SCHEDULED. The law gate is red. | Institutional |
| DP2 | Remove dormant/partial components | MISSING | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Nothing on LIVE deletes a component. #55 deletes no file (`--diff-filter=D` is empty) and only suspends authority. | A retirement pass with a deletion ledger. | Institutional / Tier S |
| DP3 | Repair the validation defects | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | The variance constant 0.014863 is still at `effective_trials.py:309` and `gate_policy.py:84` on both refs. The #52 lockbox, lifetime trials and fail-closed costs are unmerged. #55's online FDR at the door covers none of the named defects. | Merge #52 and resolve its manifest conflict with #53. Measure the variance. Migrate the lockbox==wf_oos certificates. Get CI green. | Institutional |
| DP4 | Clear the judging backlog | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | LIVE `judging_throughput` leg with its tests. The box `JUDGING_RATE` (06:40Z) is cited in the committed `TIER1_BREADTH_REVIEW.json`: 5,266/day judged against 8,303/day created, backlog 1,398,727 (+474), oldest 773.9 h. #55 adds `docket_keff.py`, which orders the docket by marginal k_eff (`judge_coverage.keff_stamp`, `use_keff=True`). | Judging is below creation and the backlog grows, so C fails on outcome as well as CI. The `judging_throughput` leg times out. `GAUNTLET_BACKPRESSURE` has been stale since 09-25. | Institutional |
| DP5 | Measure actual independent breadth | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | LIVE `independence_graph.py` and the `alpha_rank` leg. There is now a fresh committed box reading: k_eff 2.526 on 453 nominal, 9/15 clusters occupied (`TIER1_BREADTH_REVIEW.json` 09-30). The committed `effective_breadth.jsonl` still ends 09-16 at 2.057. | Green CI. Append the reading to the committed breadth log so the two agree. | Institutional |
| DP6 | Research-budget allocation sovereign | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: the committed `research_budget.json` says `authoritative:false`. #55: the bandit publishes hourly (`research_bandit.publish`), and the `cycle_pricing` weights (meta 0.40, alpha_rank 0.25, bandit 0.20, and others) set leg seconds. | No measured reading shows authority: the committed file is still `false`. Hourly legs only; residents and tasks are excluded. Factors are ≥1.0 only. | Institutional |
| DP7 | Allocator sovereign | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | #53 is unmerged. #55 only adds a heat-neutral `tier_s_factor` tilt in `pf_allocator.py`. The min-lot and gold floors still override a zero allocation. | Merge #53. Show a box pass sized by the allocator. Green CI. | Institutional |
| DP8 | Cost truth mandatory | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | The #52 fail-closed costs and #53 `test_live_rows_need_a_cost_basis.py` are unmerged. #55 does not touch it. | Merge both, migrate `sleeves.json`, green CI. | Institutional |
| DP9 | CI permanently green | MISSING | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Run 36706441916 (`9c465f8d`) failed the LAW GATE (gauntlet seal) and the MT5 desk suite. Every other push since 6c8a71a4 was cancelled. #55 would add 2 more seal breaches (promoter, rails). | One green run on LIVE. A re-signed manifest. Required checks. | Institutional |
| DP10 | Recursive research competition | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | LIVE `run_scientist_tournament.cmd` ends `exit /b 0` and is untested. #55 `researcher_market.py` uses Thompson sampling plus a MILP and has a held-out control arm; it is tested in the tier_s suites. | Winners gain only compute share. 0 independent discoveries on record. No committed artifact. | Tier S |
| DP11 | Accumulate untouched forward/live evidence | TIME-BOUND (machinery runs) | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | LIVE `enrol_clocks` leg with its tests. Committed box reading: 837/837 certificates enrolled, and 21 LIVE / 6 STANDBY sleeves (`TIER1_BREADTH_REVIEW.json`). | Time. Green CI. The cert→clock latency is UNMEASURED. | Institutional |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `bitemporal.py` and `data_os.py` run a point-in-time audit inside `tier_s`. `DATA_OS.json` is read only by `acquisition_resolution`, and no certificate or data gate reads it. | The audit must gate the data that certificates use. A rendered, committed verdict. | TS |
| AC13 | Research methods compete experimentally | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | #55 `red_queen`, `meta_benchmark`, `researcher_market` and `twin`. Adoption is automatic only for toy validator genomes and compute prices; money-path adoption is "PROPOSAL" (S30 BLOCKED_ON_USER). | Winning methods must take over real judging or execution. A committed arena artifact. | TS |

Counts on LIVE: DONE 0 / PARTIAL 12 / MISSING (branch-only) 13 / MISSING 2 / EXCLUDED 0 / TIME-BOUND 1 (28 rows). The 10:40Z pass had PARTIAL 25 / MISSING 2 / TIME-BOUND 1; the difference is the reclassification above, not a regression.
Counts if #55 merged: DONE 0 / PARTIAL 22 / MISSING (branch-only) 3 (DP3, DP7, DP8) / MISSING 2 (DP2, DP9) / EXCLUDED 0 / TIME-BOUND 1 (28 rows). Only DP4, DP5 and DP11 would reach 6/7, failing on C alone. Ten rows (H2, H4, H6, H8, H10, H13, H14, H16, ADM, DP6) would reach 5/7, failing on R and C. None reaches 7/7.
AC3 and AC13: MISSING (branch-only) on LIVE. PARTIAL if #55 merged, not DONE on merge.

Seal: LIVE breach (1/18: external_gauntlet.py cccb6ff6… vs baa3071c…), #55 breach (3/18: + promoter.py, rails.py)

### Ledger claims that fail
1. "Tier S 42/46 DONE" (`tier_s_program.json`). Every DONE row cites a `desks/mt5/reports/tier_s/*.json` artifact that is gitignored, not on the box, and never committed. The ledger grades itself, and `check_tier_s_program.py` checks the ledger, not the artifacts.
2. "research_bandit publishes an AUTHORITATIVE budget hourly." The leg exists on #55 only. The only committed `research_budget.json` (09-23) says `authoritative:false` on both refs, and no applied reading exists.
3. "alpha_rank sets leg budgets." It is one 0.25-weighted input to a 1.0–2.0x factor, so it can lengthen or reorder a leg and never shorten one. It runs only on #55.
4. "The promotion door withholds on constitution, replication, FDR, review panel, OOS theory, immune freeze." True in code on #55. But the door sits in `promoter.py` and its rail in `rails.py`, both sealed judge files the builder changed without re-signing. So merging it breaks the law gate. It also fails open when a file is absent or stale, or an import fails, and it never touches rows already LIVE.
5. "Judge queue ordered by k_eff contribution." Implemented on #55 only. The committed box reading shows judging at 5,266/day against 8,303/day created and a growing backlog of 1,398,727, so ordering is not the binding constraint.
6. "A full hourly tier_s run took 416 s with no errors." The `hourly_cycle.py` comment itself says this was measured in the cloud checkout, not on the box. No run log or artifact is committed.
7. S31 "Formal verification DONE". Nothing reads `FORMAL.json` and it does not gate release. S37 (epistemic) and S41 (replay) are DONE with no consumer.
8. S30 and S33 "architecture evolution DONE". The adopted object is a `meta_benchmark.ValidatorConfig` genome, not the production gauntlet.

### Top gaps
1. **The seal is breached on both refs.** Re-sign `IMMUTABLE_MANIFEST.json` for `external_gauntlet.py` (LIVE) and for `promoter.py` and `rails.py` (#55) with a human commit before or with the merge. Otherwise #55 turns one breach into three and DP9 and every C mark stay red.
2. **#55 is unmerged.** 10 H/ADM rows plus AC3 and AC13 have nothing on LIVE. The merge is conflict-free (`merge-tree`), so the only blocker is the seal.
3. **No Tier S artifact exists anywhere a verifier can read.** `reports/tier_s/*` and `data/tier_s/*` need committing, or a box-run reading after the merge. Until then R is ✗ on all 46 layers.
4. **Judging is below creation on the box.** 5,266 vs 8,303/day, the backlog is 1.40M and growing, `judging_throughput` times out, and `GAUNTLET_BACKPRESSURE` has been stale since 09-25. The fixes were refused by the desktop classifier.
5. **Budget authority is unproven.** The committed `research_budget.json` is still `authoritative:false` from 09-23. After the merge, an applied `CYCLE_PRICING` or `research_budget` reading with `authoritative:true` from the box is needed.
6. **#52 and #53 are still unmerged** (DP3, DP7, DP8). The DSR variance constant is live, and the allocator floors still override zero.

