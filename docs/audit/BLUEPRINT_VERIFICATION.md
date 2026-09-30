# Blueprint verification matrix

Independent check of every blueprint the principal gave on 2026-09-29, verified against the code rather than the builders' ledgers.
**Re-scored 2026-09-30 ~10:40Z under the principal's strict definition of DONE**, against the live branch `claude/llm-auto-upgrade-verify-gcjac3` at `6c8a71a4` (after #69). The Tier S and hardening sections (B1, B2, C) were last re-verified at ~12:05Z against LIVE `02057ffa` and PR #55 at `a0de5855`; each of their rows carries two mark sets, LIVE and "#55 as if merged".
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

**C on LIVE.** The evaluator seal on LIVE was re-signed by a human commit (3167eb6f) and the law gate now passes at `02057ffa`, but no CI run on LIVE has completed green since the strict re-score began, so C still fails. The first re-score (10:40Z) recorded CI run 36701520415 on `6c8a71a4` failing on the seal and the MT5 desk suite.

## Headline (strict)

| Blueprint | Items | DONE | PARTIAL | MISSING (branch-only) | MISSING | EXCLUDED | TIME-BOUND |
|---|---|---|---|---|---|---|---|
| Audit: critical sequence, named defects, 10/10 acceptance table | 43 | 0 | 27 | 10 | 3 | 1 | 2 |
| Audit: 20 implementation items + pipeline chain | 21 | 0 | 20 | 0 | 0 | 0 | 1 |
| Tier S: 15-layer table + sections 1–15 | 30 | 0 | 30 | 0 | 0 | 0 | 0 |
| Tier S: sections 16–30 + final loop | 16 | 0 | 16 | 0 | 0 | 0 | 0 |
| 16 hardening + depth priorities + admission rule | 28 | 0 | 15 | 12 | 1 | 0 | 0 |
| **Total** | **138** | **0** | **108** | **22** | **4** | **1** | **3** |

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

### 2026-09-30 12:05Z: Tier S batch 6 (PR #55 at `a0de5855`, LIVE at `02057ffa`)

The builder fixed the control-arm leak, sent exchange ZERO/EXIT/DEFER to the allocator as a 0 tilt, made alpha_rank bind both ways, added box-evidence digests, made the ledger checker refuse a DONE the box has not attested, stopped organ ERROR counting as attestation, added a review of rows already LIVE, and moved layers back from DONE. Strict result:

| Section | On LIVE | If #55 merged as-is |
|---|---|---|
| B1 (30) | 0 DONE, 30 PARTIAL | 0 DONE, 30 PARTIAL |
| B2 (16) | 0 DONE, 16 PARTIAL | 0 DONE, 16 PARTIAL (best: T27 at 6/7) |
| C (28) | 0 DONE, 15 PARTIAL, 12 MISSING (branch-only), 1 MISSING | 0 DONE, 24 PARTIAL, 2 MISSING (branch-only), 2 MISSING |

Verified: the ledger no longer grades itself (it now reads 0 DONE / 33 BUILT / 11 PARTIAL / 2 BLOCKED and rejects any unattested DONE); the control arm reads exactly 1.0; an exact exchange 0 reaches the allocator.

Still failing:

- **Seal.** LIVE is now clean (gauntlet re-signed, 3167eb6f). #55 still changes `promoter.py` and `rails.py` unsigned, so merging it turns a green law gate red with 2 breaches.
- **Merge conflict.** #55 no longer merges cleanly: `judge_coverage.py` conflicts with LIVE #77.
- **No artifacts.** No Tier S output or `box_evidence.json` exists on any ref or the box, so every row fails R and no layer can be attested.
- **Door still fails open one level up.** A raising check now withholds, but `promoter.tier_s_block` still returns None on an import error, and a stale or absent verdict file withholds nothing.
- **Live-row review is inert.** It writes `live_door.json`, which nothing reads.
- **The new gateway fault drill (S42) fails its own test** in a clean worktree (child process cannot import `libs`); the two gateway defects it found are unfixed.
- **Tilts between 0 and 0.5 are still floored to 0.5**; only an exact 0 escapes.

LIVE since `846ce9de`: #84, #86 and the seal re-sign landed (DP7 and DP9 move to PARTIAL; DP11 moves from TIME-BOUND to PARTIAL because #84 found forward ledgers frozen for 7 days). No fresh `research_budget.json`, breadth or judging artifact was committed. #52 and #53 remain unmerged.

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

Checked 2026-09-30 ~11:55Z.
- LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `02057ffa`.
- TIERS = `origin/claude/tier-s-institution` @ `a0de5855` (PR #55, draft, 61 ahead / 55 behind).
- The PR head has since moved to `6ea40135`. That commit only adds `box_evidence.json` and `live_door.json` to the box's `sync_shadow_to_git.ps1`. It is not scored, and it changes no mark: the box runs LIVE, and LIVE has no `tier_s` leg to write either file.

**Facts behind every row (checked in the code, not the ledger):**
- **LIVE still carries no Tier S code.** There is no `libs/tiers/*` and no `tier_s.py`. The 23 LIVE commits since `846ce9de` touch `hourly_cycle.py` and `judge_coverage.py`, and nothing that is Tier S. LIVE marks are for the LIVE analogues and are unchanged from v2.
- **#55 no longer merges clean.** `git merge-tree` onto `02057ffa` conflicts in `desks/mt5/research/judge_coverage.py`, and GitHub reports `mergeable_state: dirty`. The "#55" scores below assume that conflict is resolved. D ✓ there is hypothetical.
- **Evaluator seal:**
  - **LIVE `02057ffa`:** OK, 0 breaches. `external_gauntlet.py` was re-signed on LIVE in 3167eb6f.
  - **TIERS `a0de5855`:** 3 breaches:
    - `external_gauntlet.py` (`baa3071c`→`cccb6ff6`, inherited from before the LIVE re-sign);
    - `promoter.py` (`52d6f4b4`→`1041a40e`);
    - `rails.py` (`e832bd4c`→`e01e6027`).
  - **Merge tree (LIVE + #55):** 2 breaches, `promoter.py` and `rails.py`. Merging #55 takes the LIVE law gate from green to red.
- **CI:**
  - **#55:** the run on `a0de5855` (36710482326) is in progress, and every earlier run on the branch was cancelled. There is no completed result: unknown.
  - **LIVE:** the run on `02057ffa` (36710180868) is in progress, and the intervening runs were cancelled. The last completed LIVE result I know of (9c465f8d) was a failure. Unknown, last known red.
- **Tests:** I ran the Tier S suite in a clean worktree at `a0de5855` (tier_s_* ×8, gateway_drill, cycle_pricing, research_budget, tests/tiers; 224 tests). **1 FAILS:** `test_tier_s_gateway_drill::test_the_real_gateway_runs_in_a_temp_root_against_the_double`.
  - The drill child process cannot import `libs`: `place_exc: ModuleNotFoundError: No module named 'libs'`, with sends 1 against 2 expected.
  - The drill adds `desk` to `sys.path` but not the repo root. So the S42 drill measures its own import error, not the gateway.
- **The checker is green on its own terms.** `check_tier_s_program.py` exits clean with BUILT 33, PARTIAL 11 and BLOCKED_ON_USER 2. It now reports **0 DONE**, which agrees with this score.
- **No Tier S artifact exists on any ref.**
  - No `data/tier_s/box_evidence.json` is on any remote branch.
  - No TIER_S / ALPHA_RANK / ONLINE_FDR_ROWS / IMMUNE / allocator_tilts / live_door file is committed on either ref.
  - `reports/*` is gitignored, so the only route to git is the box-evidence digest, and that is written only by the `tier_s` leg, which the box does not run.
  - R is ✗ in both scores for every row.

Marks order: I W A T R D C. "#55" means as if merged, with the judge_coverage conflict assumed resolved.

| ID | Item | Verdict | Marks | Evidence on #55 (file:line, caller, test, artifact) | Still missing | Owner |
|---|---|---|---|---|---|---|
| L1 | Truth Kernel: immutable constitution controls everything | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `truth_kernel.py` and `tier_s_constitution.json`. `promotion_authority._constitution` withholds a new LIVE row. The door now fails closed inside `block()` (7fe3fb5). Test: test_tier_s_door. | The gauntlet does not read the constitution's thresholds (S01 BLOCKED_ON_USER). No box artifact. The seal has 2 breaches after merge. CI unknown. | Tier S build |
| L2 | World Data OS: PIT/bitemporal + provenance + reliability | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `bitemporal.py` and `data_os.py`, called only from tier_s and acquisition_resolution. Test: test_tier_s_world. | No data path reads the store. It decides nothing. No artifact. | Tier S build |
| L3 | World Model: causal/economic knowledge graph | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | `world_edges`, `world_macro` and `graph_edges` turn broken edges into compiler rows. LIVE `data/world_causal_graph.json` (09-08, 0 admitted edges). | It only generates hypotheses. The artifact is stale. There is no flows or regional graph. | Tier S build |
| L4 | Researcher Civilization: hundreds of heterogeneous processes | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `researcher_prices.json` → `cycle_pricing` (weight 0.15). `blinding.audit`. Test: test_tier_s_adversarial. | Blinding is an audit, not enforcement. No new non-LLM processes. No artifact. | Tier S build |
| L5 | Hypothesis Ecology: competing/evolving mechanism populations | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | QD, genomes and theory rows go to `data/intelligence/tier_s/`. Tests: test_tier_s_evolution and test_tier_s_organs. | The populations decide nothing. No artifact. | Tier S build |
| L6 | Research-Program Evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `program_evolution.py` inside the tier_s leg. Test: test_tier_s_evolution. | Evolved programs are challengers and report only. No artifact. | Tier S build |
| L7 | Adversarial Science: researchers vs destroyers co-evolve | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `red_queen.py` attacks the production `run_gauntlet` and attributes attacks per researcher. Test: test_tier_s_adversarial. | A winning defender changes no production gate. No artifact. | Tier S build |
| L8 | Universal Validation: anti-selection/anti-leakage | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `promotion_authority.block` (:175) runs 5 checks plus freeze. Any check that raises → `DOOR_ERROR` withhold (7fe3fb5). `review_live` (a0de585). Test: test_tier_s_door. | **Still fails open one level up.** `promoter.tier_s_block` (promoter.py:1575-1582) keeps `except Exception: return None`, so an import error or path error drops all the checks. `live_door.json` has no consumer: `promoter.py` is sealed and the consumer is deferred. DSR has zero power. #52 is unmerged. There is no seal re-sign. | Both threads |
| L9 | Alpha Topology: true independent dimensions | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `alpha_rank` → `cycle_pricing` at weight 0.25. It is now two-sided inside the 1.0 floor: the bottom quartile loses its boost and the top quartile is raised to its own boost (09e7bc8, cycle_pricing.py:481-498). `docket_keff` orders the judge docket. Tests: test_cycle_pricing and test_tier_s_breadth. | No ALPHA_RANK/TOPOLOGY artifact, committed or digested. Two rank organs, still unreconciled. | Tier S build |
| L10 | Portfolio Intelligence: posterior E[log W] | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `tier_s_factors` goes down to 0.0. `pf_allocator` (:2123) sets tilt 0 when sf ≤ 0. Control-arm sleeves are pinned to exactly 1.0 and excluded from normalisation (652d81c). Test: test_tier_s_organs. | Only an exact 0 escapes the allocator's `TILT_LO` clamp: 0 < sf·others < 0.5 is still floored at 0.5. The clipped ex×cap product is not re-normalised. No allocator_tilts.json exists anywhere. #53 is unmerged. | Other slices |
| L11 | Execution Intelligence: learned implementation optimum | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `capture_raw` tilt, with the control arm now excluded from capture. `execution_science` leg. Test: test_tier_s_organs. | With 0 matched fills, capture is 1.0 and inert. The method itself is not learned. No artifact. | Other slices |
| L12 | Live Reality Engine: backtest reconciled to reality | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | THEORY_REFUTED on forward/live evidence withholds. `review_live` computes the same verdict over rows already LIVE → `data/tier_s/live_door.json`. `data/forward_reconcile.json` is committed on LIVE. | The live-book review reaches no retirement: the promoter consumer is not written. Withhold-only, n is tiny. Seal and CI. | Other slices |
| L13 | Meta-Science: which methods create edge | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `research_bandit` hourly leg with `publish()`. Priced legs. Tests: test_research_budget and test_cycle_pricing. | The committed `research_budget.json` is still `authoritative:false` (09-23). The box-evidence digest of it does not exist. | Tier S build |
| L14 | Architecture Evolution: system proposes self-improvements | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | twin and self_model in tier_s. Test: tests/tiers. | Money-path challengers are PROPOSE only (S30 BLOCKED_ON_USER). No artifact. | Other slices |
| L15 | Operational Kernel: reproducible, redundant, deterministic | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✗✗✓✗ | `gateway_drill.campaign()` is called from `organ_chaos` (tier_s.py:2589, 578963e). `process_kill_drill`. | **The T mark regressed to ✗.** `test_tier_s_gateway_drill` FAILS in a clean worktree: the child process cannot import `libs`, so the drill records its own ModuleNotFoundError as a gateway NO_CRASH breach. No standby or failover. Report only. | Other slices |
| T1 | Truth Kernel: agents cannot change PIT/trials/cost/lockbox/cert/capital/provenance/repro rules; content-addressed raw→fill; reconstruct any trade | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | Journal and seal. Constitution-change withhold at the door, now fail-closed inside `block`. | The values are not bound in the gauntlet or allocator (S01). No order-time lineage. No artifact. | Tier S build |
| T2 | World Data OS: bitemporal, per-datapoint provenance/revisions/latency/licence/reliability; acquisition by info-gain per € | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `bitemporal.py`, `data_os.py`, `acquisition_resolution.py`. Test: test_tier_s_world. | Not on the data path. Does not feed `acquire_datasets`. No € costs. | Tier S build |
| T3 | World model: rates→FX→…→flows graphs, regional; stable/state-dependent/decaying/false; hypotheses from broken edges | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | `world_edges` classification. Residual rows go to the compiler. | No flows or regional graph. It decides nothing. The artifact is stale. | Tier S build |
| T4 | Researcher civilization with ~25 epistemologies incl. non-LLM; some blind to others | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `blinding.audit` and the firewall seat table. | Blinding is audited, not enforced. No independent-discovery evidence. | Tier S build |
| T5 | AlphaEvolve-for-alpha: LLM + evaluators evolving code, grammars, portfolio/regime/execution/scheduler programs; fitness = validated independent alpha per compute | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `evolution.py` and `program_evolution.py`. `expression_factory` reads the grammar. | No LLM-in-loop code evolution. Challengers only. No artifact. | Tier S build |
| T6 | MAP-Elites over 12 descriptor axes | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | `qd_axes.py` and `research_diversity_archive`. | The archive steers nothing. No artifact. | Tier S build |
| T7 | Evolve researcher genomes; fitness = validated independent info / compute with penalties | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | RESEARCHER_GENES and the `falsify_order` allele. | Steers only tier_s's own rows. No evidence that fitness is above 0. | Tier S build |
| T8 | Researcher market: posteriors, bandits/Bayesian allocation, deteriorating lose compute | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `researcher_prices.json` (0.15) and `research_bandit` (0.20) → cycle_pricing. The alpha-rank bottom quartile now withdraws a boost. | FLOOR 1.0 means no leg or researcher ever loses compute below base. The per-researcher MILP is unused. The budget file is authoritative:false. No artifact. | Tier S build |
| T9 | Red Queen per-researcher adversary (15 attack kinds), counter-agent, co-evolve | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | Per-researcher attribution and validator genomes. | The defender does not reach the real gates. No artifact. | Tier S build |
| T10 | Planted traps (blind), immune score, FREEZE production when traps accepted | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `_freeze` is now inside the fail-closed loop of `block`, and `review_live` applies it to the live book. | FREEZE does not reach the allocator (the patch is still "prepared"). The live review has no consumer. Traps are not injected blind. No IMMUNE artifact. | Tier S build |
| T11 | Adaptive multiplicity: lifetime genealogy + online FDR / sequential / e-values | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | `online_fdr.py`. `_fdr` withholds `over_budget` rows, now fail-closed. | #52 lifetime trials are unmerged. p-values are proxies. No ONLINE_FDR_ROWS artifact. | Tier S build (+ #52) |
| T12 | Epistemic firewall, physically isolated roles | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | A `FirewallError` inside `block` now withholds (DOOR_ERROR) instead of disabling the door. | No runtime `may()` at `universal_gate` / `external_gauntlet` (S12). No OS isolation. A failure to import the door in the promoter still silently disables it. | Tier S build |
| T13 | Negative knowledge: typed causes, graph, retrieval for new candidates, "explored N times" → move on | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | `failure_memory.py` (tier_s and authority). LIVE `negative_knowledge` → `gauntlet_backpressure`. | Generators outside tier_s do not read failure_memory. No artifact. | Tier S build |
| T14 | Ancestry graph: code/feature/hypothesis/data ancestry + P&L/tail similarity; derived not counted fresh | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | `topology.effective_discoveries` → alpha_rank → cycle_pricing (0.25, now two-sided). | Discounts compute only. No code or data ancestry. No artifact. | Tier S build |
| T15 | Effective Independent Alpha Rank (PnL, eigen, nonlinear, tail, DD, ancestry, exposure, overlap, mechanism, regime); scheduler searches orthogonal | PARTIAL (closest to DONE) | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | alpha_rank binds both ways inside the floor (09e7bc8, test_cycle_pricing). docket_keff orders the docket. | An ALPHA_RANK artifact from the box. The seal re-sign and a green CI. Two rank organs. | Tier S build |

Counts on LIVE: DONE 0 / PARTIAL 30 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (30 rows)
Counts if #55 merged: DONE 0 / PARTIAL 30 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (30 rows). All 30 fail R (no artifact on any ref) and C (2 seal breaches after merge, CI unknown). L15 now also fails T.

Seal at a0de5855: 3 breaches on TIERS (`promoter.py` 52d6f4b4→1041a40e, `libs/portfolio/rails.py` e832bd4c→e01e6027, `external_gauntlet.py` baa3071c→cccb6ff6). There are 2 after merging onto LIVE (promoter, rails); LIVE `02057ffa` itself is clean (0). CI on a0de5855: in progress, unknown.

### Claims verified / failed
- **VERIFIED, partly: the door fails closed.** `promotion_authority.block` catches per check and returns `DOOR_ERROR`, and the freeze check is now inside the loop too. **FAILED one level up:** `promoter.tier_s_block` still has `except Exception: return None` (promoter.py:1581), so an import failure fails open. The fix cannot land without touching the sealed file.
- **VERIFIED as code, UNCASHED as evidence: DONE only on the box's attestation.** `check_tier_s_program` refuses DONE without `box_evidence.attested()` from `vmi3571445`, and now reports 0 DONE and 33 BUILT. No `box_evidence.json` exists on any ref. The box runs LIVE, which has no `tier_s` leg, so no attestation can exist before merge.
- **VERIFIED: box_evidence digests the named outputs.** TIER_S, ALPHA_RANK, ONLINE_FDR_ROWS, IMMUNE, allocator_tilts (verbatim), research_budget, door_verdicts and CONTRACTS are all in `PUBLISHED`. The sync that carries them is in 6ea40135, after the scored head.
- **VERIFIED: the checker fails a cited artifact that has no writer** (`writes()`). The check is weak: it passes when the file name merely appears as a string in any cited `.py`.
- **VERIFIED: an organ ERROR never attests** (`layer_evidence`: `status == "ERROR"` → ok False).
- **VERIFIED: the control arm reads exactly 1.0, and exchange ZERO/EXIT/DEFER reaches the allocator as 0.** `pf_allocator` gets tilt 0 only when sf ≤ 0. Any non-zero Tier S factor below 0.5 is still clamped up to `TILT_LO` 0.5.
- **VERIFIED: alpha_rank binds both ways,** but only as boost removal (bottom quartile) and boost raise (top quartile). No leg drops below base.
- **VERIFIED as code, NO CONSUMER: the door reviews rows already LIVE.** `review_live` writes `live_door.json`, and nothing reads it. The promoter's retirement consumer is deferred to a "desktop batch" because `promoter.py` is sealed.
- **FAILED: the S42 real-gateway drill.** It is wired into `organ_chaos`, but its own test fails in a clean worktree: the child process has no repo root on `sys.path`, so it hits `ModuleNotFoundError: libs`. It is not a real gateway measurement.
- **VERIFIED: ten layers moved back to PARTIAL.** The ledger holds 11 PARTIAL, 33 BUILT and 2 BLOCKED_ON_USER, with 0 DONE.

### Top gaps
- **Re-sign `promoter.py` and `rails.py`, and fix the promoter wrapper's `except Exception: return None` in the same signed edit.** Merging today turns LIVE's clean seal into 2 breaches, and the door still fails open on an import error.
- **Resolve the `judge_coverage.py` conflict.** #55 is `dirty` against `02057ffa`, and its CI on a0de5855 has not completed.
- **Merge, then get one box run of the `tier_s` leg with the 6ea40135 sync committing `box_evidence.json`.** Until then R fails on all 30 rows and the checker can never admit DONE.
- **Fix `gateway_drill`'s child `sys.path` so it includes the repo root.** Today S42 measures its own import error.
- **Give the verdicts a consumer where they would act:** `live_door.json` → promoter retirement, FREEZE → allocator, constitution → gauntlet (S01), runtime firewall at the gates (S12).
- **Stop the allocator clamping small Tier S factors up to 0.5** (only an exact 0 escapes it), and re-normalise the ex×cap product so it is heat-neutral.

## B2 — Tier S sections 16–30 (T) and final loop

LIVE = origin/claude/llm-auto-upgrade-verify-gcjac3 @ 02057ffa. TIERS = origin/claude/tier-s-institution @ a0de5855 (PR #55, **draft**, unmerged, 61 ahead / 55 behind LIVE). GitHub reports `mergeable_state: dirty`: a trial merge in a scratch worktree conflicts in `desks/mt5/research/judge_coverage.py`.
Marks: I W A T R D C, in that order. "#55" is scored as if #55 were merged unchanged, with the conflict resolved.
Baseline: B2_v2 (TIERS @ ed496c64). New since then: 7 commits (578963e8 … a0de5855).

Checks run for this re-score:
- **LIVE still has no Tier S code.** `git ls-tree` on LIVE shows no `libs/tiers`, no `tier_s.py` and no Tier S tests. `#52` and `#53` are still not merged.
- **LIVE's seal is now clean.** `check_immutable_evaluator.py` on LIVE reports `OK`, because `external_gauntlet.py` was re-signed in 3167eb6f. LIVE CI: the run on 02057ffa was still in progress when I read it. The head of the PR merged just before it (#89) failed `quality` and `mt5-money-path`.
- **#55's seal: 3 breaches at a0de5855, and 2 if merged.** At a0de5855 the breaches are `desks/mt5/scripts/external_gauntlet.py` (the branch predates LIVE's re-sign), `desks/mt5/research/promoter.py` (52d6f4b4… → 1041a40e…) and `libs/portfolio/rails.py` (e832bd4c… → e01e6027…). A trial merge with LIVE, checked by `check_immutable_evaluator.py`, keeps 2: promoter.py and rails.py are still unsigned. So C fails on every row.
- **Tests.** Tier S desk tests, `test_cycle_pricing` and `tests/tiers`: 195 collected, **1 failure**, `test_tier_s_gateway_drill::test_the_real_gateway_runs_in_a_temp_root_against_the_double`. The drill's child process raises `ModuleNotFoundError: No module named 'libs'` (a `NO_CRASH` breach, sends 1 of 2). It passes only when the caller's PYTHONPATH already holds the repo root, and `gateway_drill.run_fault` never sets that itself.
- **The ledger no longer claims DONE.** `check_tier_s_program.py` prints "BLOCKED_ON_USER 2; BUILT 33; PARTIAL 11", with 0 DONE. DONE now requires `data/tier_s/box_evidence.json` written on host `vmi3571445`. **Verified** in the checker and its tests: cloud-host evidence is refused, an organ ERROR never attests, and a cited artifact with no writer fails. The attestation checks only that the artifact is fresh and that its contract is not REJECTED. It does not check the seal or CI.
- **Still no Tier S artifact anywhere.** No branch holds `desks/mt5/data/tier_s/*`, `reports/**` is gitignored, and the box pulls LIVE, which has no `tier_s` leg. Every R is ✗.
- **Control arm: fixed (verified).** `heat_neutral(held=…)` pins held-out sleeves to exactly 1.0, excludes them from normalisation, and skips them for capture. `test_control_arm_reads_exactly_one_and_the_exchange_can_clear_to_zero` covers it.
- **ZERO/EXIT/DEFER → 0: partly true.**
  - It survives `allocator_tilts` (lo = 0), `tier_s_factors` (TIER_S_TILT_LO = 0) and `pf_allocator` (sf ≤ 0 forces tilt = 0 after the 0.5 clip).
  - But the tilt only moves the sleeve's **mean** to `mean − |mean|`, which is 0 for a positive mean. Its dispersion stays in the worlds, so the solve can still fund it as a hedge. I measured this with the real `apply_allocator_evidence` + `optimise`: a sleeve at 0.06 heat went to **0.0004** at target 0.20, not 0.
  - The larger leak is the fallback. `allocator_proof.contest` builds `equal_weight` / `inverse_vol` / `risk_parity` over **every** `ev` name, zeroed sleeve included. `gateway.allocator_book` sizes from that `book_fallback` whenever the proof is stale or failing (82% of passes, measured 2026-09-15), and `book_zeroed` only zeroes names the fallback does not fund. So an exchange zero is re-funded at the baseline's weight on those passes.
  - A factor in (0, 0.5) is still raised to the 0.5 `TILT_LO` floor.
- **The door fails closed only inside `block()`.** `promotion_authority.block` now returns `DOOR_ERROR` on any check exception (verified by test). But `promoter.tier_s_block` (promoter.py:1575–1582) still wraps the import and the call in `except Exception: return None`, and its own docstring says "An unimportable module withholds nothing". So the promoter's side still fails open on an import or path error.
- **"Door reviews rows already LIVE" is a report only.** `review_live` → `data/tier_s/live_door.json`, and its declared consumer is "promoter.py automatic retirement (desktop batch: promoter.py is sealed)". `git grep live_door` finds no reader, so it has no authority over a LIVE row.
- **alpha_rank binds both ways (verified in code and test).** `cycle_pricing.ALPHA_VETO = 0.25`: the bottom quartile is capped at 1.0x, and the top quartile gets at least its own rank's boost, inside FLOOR 1.0 / CEIL 2.0. That is compute authority only.
- **Unchanged:** FREEZE still reaches no sizing code (no FREEZE read in allocator_tilts / allocator_evidence / pf_allocator). The DSR variance is still the constant 0.014863 (`effective_trials.py:309`). `tier_s` is still a rotated "meta" leg (cap 1,500 s), with a 6 h staleness limit that makes it neutral.

| ID | Item | Verdict | Marks | Evidence on #55 | Still missing | Owner |
|---|---|---|---|---|---|---|
| T16 | Counterfactual World Lab | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged: swap world and `correlations_to_one`, `organ_worlds`. Ledger S16 is now PARTIAL, which agrees with this verdict. | Market-closure and agent-based worlds; a break flag that acts; an artifact; C (seal). | Tier S build |
| T17 | Alpha Theory Compiler | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged: `libs/tiers/theory.py`, recipes to `data/intelligence/tier_s/`. Ledger S17 is BUILT (not DONE). | `compose` untested; no authority; no box artifact; C. | Tier S build |
| T18 | Theory↔Evidence graph | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `THEORY_REFUTED` withholds a new LIVE row. `block()` now fails closed internally (DOOR_ERROR). | The promoter's wrapper still fails open (`except Exception: return None`). `live_door.json` has no reader. MIN_OOS=10 rarely binds. No artifact. C (promoter unsigned). | Tier S build |
| T19 | Heterogeneous non-LLM intelligence | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged (`cross_science.py`, tested). | No SAT/SMT solver or prover; no authority; no artifact; C. | Tier S build |
| T20 | AI peer review panels | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `REVIEW_PANEL_FAILED` withholds a new row. Fails closed inside `block()`. | Fixed if-rule reviewers; challenges spawn no experiments; the promoter's wrapper fails open; the live-row review has no consumer; no artifact; C. | Tier S build |
| T21 | Auto-invent new tests | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. Ledger S21 moved to PARTIAL, which agrees. | Ratifications are still empty, so no enacted gate. DSR constant; no artifact; C. | Tier S build |
| T22 | Auto-invent research grammars | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged (`grammar_bias.bias()` reweights the DSL). | No new representation class; no budget authority; no artifact; C. | Tier S build |
| T23 | Execution as autonomous science | PARTIAL | LIVE: ✗✓✗✗✗✗✗ / #55: ✗✓✓✗✗✓✗ | Capture tilt reaches pf_allocator; held-out sleeves are now excluded from capture. Ledger S23 is now PARTIAL, which agrees. | Still no test of `execution_science.py`; matched_fills = 0, so capture is 1.0; no slicing, spread, adverse-selection or urgency model; no report; C. | Tier S build |
| T24 | No-trade first-class | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✗✓✓✓✓✓✗ | An exchange ZERO now reaches `pf_allocator` as tilt 0 (no longer floored at 0.5). The mean goes to 0 and the dynamic solve gives about 0 (0.0004 measured). | The zero is a zero **mean**, not a zero weight, so hedge value can still fund it. The baseline `book_fallback` (equal_weight etc. over every name) re-funds it on stale/failed-proof passes. Factors in (0, 0.5) are still floored at 0.5. #53 (min-lot/gold floors) unmerged; C. | Tier S build / Institutional (#53) |
| T25 | Opportunity Exchange | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | Control arm now exactly 1.0 (verified, tested). exchange → `allocator_tilts.json` → `tier_s_factors` → `pf_allocator` → `pf_allocation.json` holds. | The ZERO→book leak through the fallback (see T24). Neutral if the rotated leg misses 6 h. FREEZE does not reach it. No box artifact. C (rails.py and promoter unsigned). | Tier S build |
| T26 | Live prediction-accounting | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✓✓✗✓✗ | Unchanged. | No vol, factor or correlation forecasts; no per-model forecasts; no artifact; C. | Tier S build |
| T27 | Live reality outranks backtests | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✓✓✓✓✓✓✗ | Unchanged. The honesty penalty reaches cycle_pricing and the exchange bids; alpha_rank now also binds cycle_pricing two-sided. | No test of the honesty channel; no reach into admission/priors for new discoveries. C: 2 seal breaches if merged, and LIVE CI not green. | Tier S build |
| T28 | Digital twin (shadow desk) and rollback | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged. Ledger S28 is now PARTIAL, which agrees. | Still no rollback test; human `--apply-rollback`; no shadow desk; no artifact; C. | Tier S build |
| T29 | Self-model | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. The S42 gateway drill adds a `gateway_drill` block to `organ_chaos`, but its test fails here (child `ModuleNotFoundError: libs`). | No authority; hand-set p_fix and cost; no box artifact; C. | Tier S build |
| T30 | Architecture evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged. The ledger still says BLOCKED_ON_USER. | Money-path adoption refused; no regression stop on Adopt-And-Seal; no artifact. | Tier S build |
| LOOP | Closed research→capital loop inside a Truth Kernel | PARTIAL | LIVE: ✗✓✗✗✗✗✗ / #55: ✗✓✗✗✗✓✗ | Adds, since v2: `block()` fails closed internally, alpha_rank binds compute both ways, the control arm is clean, and an exchange zero reaches pf_allocator. | The promoter's wrapper still fails open. FREEZE does not reach the allocator. The fallback re-funds exchange zeros. `live_door.json` has no reader. DSR constant 0.014863. #52/#53 unmerged. No end-to-end loop test. No artifact on any node. promoter/rails re-sign needed; #55 does not merge cleanly. | Tier S build / Institutional (#52, #53) |

Counts on LIVE: DONE 0 / PARTIAL 16 / MISSING (branch-only) 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (16 rows)
Counts if #55 merged: DONE 0 / PARTIAL 16 / MISSING 0 (16 rows). Best is still T27 at 6/7; T18, T20 and T25 are at 5/7. No row gained a mark. The fixes close v2 defects inside marks that were already ✓ (A on T25/T24), and R and C still fail on every row.
Seal at a0de5855: 3 breaches (external_gauntlet.py stale vs LIVE's re-sign, promoter.py, rails.py). 2 breaches if merged into LIVE (promoter.py, rails.py). LIVE @ 02057ffa alone: OK.

### Claims verified / failed
1. **VERIFIED:** "DONE only on box attestation". The ledger now reads 0 DONE (BUILT 33 / PARTIAL 11 / BLOCKED 2). The checker refuses non-`vmi3571445` evidence, and tests cover it.
2. **VERIFIED:** "checker fails when a cited artifact has no writer", and "organ ERROR never attests" (`layer_evidence` gives ok=False on status ERROR). Tested.
3. **VERIFIED:** "exchange control arm exactly 1.0". Held-out sleeves are pinned after normalisation and excluded from capture.
4. **PARTLY FAILED:** "ZERO/EXIT/DEFER reach the allocator as a 0". It reaches `pf_allocator` as tilt 0, past the 0.5 clip. But it zeroes the mean, not the weight (0.0004 residual measured), and the baseline fallback (equal_weight/inverse_vol/risk_parity over all names, which the gateway reads via `book_fallback`) re-funds it. So the 0 does not reliably reach the gateway's book.
5. **PARTLY FAILED:** "door fails closed". True inside `promotion_authority.block`. False at the promoter: `promoter.tier_s_block` still does `except Exception: return None` ("An unimportable module withholds nothing").
6. **FAILED as authority:** "door reviews rows already LIVE". It only writes `live_door.json`, and nothing reads it (its declared consumer is sealed promoter.py, "desktop batch").
7. **VERIFIED:** "alpha_rank binds both ways": bottom-quartile cap at 1.0x, top-quartile raise, inside the 1.0x floor. Compute only.
8. **FAILED here:** "S42 real gateway under a faulty MT5 double". The test fails in a clean env because the child cannot import `libs` (`NO_CRASH` breach). It passes only with PYTHONPATH=repo root, and `run_fault` does not set it.
9. **VERIFIED:** "box_evidence digests" (`digest` heads, n_rows, over_budget) are tested. No `box_evidence.json` exists on any ref.
10. **CONFIRMED STILL OPEN:** promoter.py and rails.py remain unsigned. FREEZE → allocator is still unwired. The DSR constant is unchanged. #55 now conflicts with LIVE (judge_coverage.py).

### Top gaps
- **Seal:** re-sign `promoter.py` and `rails.py` (2 breaches if merged), rebase #55 onto LIVE (conflict in judge_coverage.py, and it lacks LIVE's external_gauntlet re-sign), and get CI green on both.
- **Zero artifacts:** nothing Tier S has run on the box. Every R is ✗ until #55 is on LIVE, the box adopts it, and `box_evidence.json` from `vmi3571445` is committed.
- **Make an exchange zero a zero weight:** drop zero-tilted sleeves from `ev` (or from `book_fallback`'s names and the baselines) instead of zeroing their mean. Also pass them through `book_zeroed` so the gateway's fallback cannot re-fund them.
- **Close the promoter-side fail-open:** `tier_s_block`'s bare `except: return None` must withhold. Give `live_door.json` a reader in the promoter's retirement path; this needs a sealed edit and a re-sign.
- **Fix the gateway drill's child import path** (set PYTHONPATH/cwd to the repo root in `run_fault`), or S42's drill will report NO_CRASH breaches on any host that does not pre-set it.
- **Still uncashed:** FREEZE → allocator, the DSR constant 0.014863, #52/#53, and tests for `execution_science` and `rollback`.

## C — 16 hardening items (H), depth priorities (DP), admission rule (ADM)

Re-scored 2026-09-30 ~11:55Z. LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `02057ffa`. #55 = `origin/claude/tier-s-institution` @ `a0de5855` (unmerged; merge base `6c8a71a4`; 61 ahead / 55 behind).
Marks are in the order I W A T R D C. "#55" means scored as if #55 were merged into LIVE as-is. So D is ✓ wherever #55 code exists, and R is ✓ only when a committed or box artifact exists today.

**The merge is no longer conflict-free.** `git merge-tree --write-tree LIVE #55` now reports `CONFLICT (content): desks/mt5/research/judge_coverage.py`. LIVE #77 (judge drain) and #55 `docket_keff` both edit the docket order. v2 recorded this merge as clean.

**New #55 commits since ed496c64** (7, all by Claude, 11:32–11:44Z):
- `578963e8` adds S42 `libs/tiers/gateway_drill.py`. It runs the real `gateway.py` under a faulty MT5 double in a temp root, hourly inside `tier_s`. It found 2 gateway defects and left them unfixed: `place_bracket` lets an `order_send` exception escape, and with no quote both legs are sent without the legality check.
- `7fe3fb53` and `eed56168` make `promotion_authority.block` fail closed: a check that raises withholds with `DOOR_ERROR`. `box_evidence.py` was added, and `check_tier_s_program` now allows DONE only when the trading box (`vmi3571445`) attests it.
- `652d81cd` pins the control arm to exactly 1.0 and lets a zero exchange factor reach `pf_allocator` as a zero tilt. This is heat-neutral.
- `09e7bc81`: cycle_pricing alpha rank now withdraws a boost for the bottom quartile. It is still floored at 1.0x.
- `a6aab6e1`: `box_evidence.json` digests the named outputs, and the checker fails a layer whose artifact has no writer.
- `a0de5855`: `review_live` runs the door over the LIVE book and publishes `data/tier_s/live_door.json`. **It has no reader.** The promoter consumer is "sealed and goes to the desktop batch", and `promoter.py`/`rails.py` are byte-identical to ed496c64.
- The ledger `tier_s_program.json` now reads **0 DONE / 33 BUILT / 11 PARTIAL / 2 BLOCKED_ON_USER**, and `check_tier_s_program.py` passes. The self-grading of DONE is gone.
- `desks/mt5/data/tier_s/box_evidence.json` is not gitignored and sits under a `STATE_PREFIXES` path, so a box sync would commit it. None exists today on any ref.

**LIVE changes since 846ce9de** (#77, #84, #86, #88, #89, #91 plus the re-sign `3167eb6f`, 29 files):
- The external_gauntlet seal was re-signed by a human (kingdemond434-cpu, 12:36+01:00).
- #77 parks dead or unbuildable cells and fences the judge drain.
- #84 adds a cert→forward meter with `ENGINE_SILENT`. Its code comment records that on the box on 09-30, forward ledgers had not moved in 7 days while every clock read ACTIVE.
- #86 stops `heal_silent_demotions` from lifting the promoter's zero-heat STANDBY rows.
- #88 sets self-stop floors so discovery legs stop killing themselves at the cap.
- #89 adds alt-data fetch.
- No new artifact was committed on LIVE: no fresh `research_budget.json`, breadth log or judging reading. `research_budget.json` is still the 09-23 file with `authoritative:false` on both refs. #52 (`audit-p0-true-lockbox`) and #53 (`audit-p0-allocator-sovereignty`) are still unmerged, and 0.014863 is still at `effective_trials.py:309`.

**CI and seal.**
- Seal on LIVE, computed by sha256 against `IMMUTABLE_MANIFEST.json` (signed 09-30T11:35:54 by zuck): **0/18 breaches**.
- Seal on the #55 tip, via `scripts/check_immutable_evaluator.py` in a clean worktree: **3/18 breaches**. These are `external_gauntlet.py`, `promoter.py` (`52d6f4b4`→`1041a40e`) and `rails.py` (`e832bd4c`→`e01e6027`). #55 carries the old manifest.
- Seal on the #55-merged tree (merge-tree `a84789b0`): **2/18 breaches** (promoter.py, rails.py). The builder still has not re-signed its two sealed judge edits.
- LIVE CI run 36710180868 on `02057ffa` was in progress. LAW GATE ✓, ruff ✓, mypy ✓; Laws, Tests and the MT5 desk suite were still running.
- Every LIVE run since 846ce9de was cancelled. The last completed run, on `9c465f8d`, was red. So there is still no completed green run: UNMEASURED, not green.
- #55 CI was queued or in progress.
- #55 tests in the isolated worktree: `test_tier_s_door`, `test_tier_s_organs`, `test_cycle_pricing` and `tests/tiers` pass. **`test_tier_s_gateway_drill.py::test_the_real_gateway_runs_in_a_temp_root_against_the_double` FAILS**: `obs["sends"] == 2` read 1.

**#55 Tier S artifacts.** There are still none on any ref or on the box. `reports/tier_s/*` is gitignored, and `data/tier_s/*` (including `box_evidence.json`, `live_door.json` and `grammar.json`) does not exist in any tree. R is ✗ for every Tier S organ.

| ID | Item | Verdict | Marks | Evidence | Still missing | Owner |
|---|---|---|---|---|---|---|
| H1 | Formal verification of money path | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✗✗✓✗ | #55 `formal.py` and `conformance.py` in the `tier_s` leg. New: `gateway_drill.py` exercises the real gateway and found 2 unfixed send-path defects. Nothing reads `FORMAL.json` or the drill result, and `release_authority.py` imports neither. The drill's own test fails in a clean worktree. | A failed proof, conformance check or drill must block release or seal. The two defects the drill found must be fixed. A committed artifact and green CI. | Tier S |
| H2 | Independent evaluator civilization | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: `check_immutable_evaluator.py` in the law gate now passes (0/18) and blocked the 9c465f8d run, so A is ✓. #55: the door now fails closed when a check raises (`DOOR_ERROR`). But `promoter.tier_s_block` still catches an import failure and returns None, which fails open. A stale or absent verdict file still withholds nothing. `firewall.may()` is called only inside `promotion_authority`. | No separate stack or hidden data. The door still fails open on an unimportable module or a stale/absent file. It is not run against a box artifact. | Tier S |
| H3 | Architecture evolution, sealed suites | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. `twin.py` adopts a `meta_benchmark.ValidatorConfig` genome. S30 is BLOCKED_ON_USER and S33 PARTIAL on the ledger's own reading. | Adoption must change the real gauntlet, scheduler, solver or execution. | Tier S |
| H4 | Immutable meta-benchmark, thousands of cases | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `PROMOTION_FREEZE` is consumed at the door on a production DROP only. A freeze from a stale file withholds nothing. | Not a release gate. No FREEZE reaches the allocator. The DSR constant is still live. No committed immune score. | Tier S |
| H5 | Active information acquisition (EVOI) | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. LIVE #89 adds a polite fetch and `ALT_DATA_YIELD.json` (a fetch yield, not a value-of-information buy). | Nothing buys or acquires data on its value. No fresh artifact. | Tier S |
| H6 | Research-search frontier estimator | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `grounds.unseen` feeds researcher prices, which feed `cycle_pricing`. | Floored at 1.0 and read from the prior hour. No committed artifact. | Tier S |
| H7 | Epistemic uncertainty engine, 5 levels | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. `EPISTEMIC.json` has no reader. | A consumer that refuses to act on "not enough evidence". | Tier S |
| H8 | Cross-engine independent replication | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | #55 withholds a new LIVE row on MISMATCH. New: `review_live` computes holds for rows already LIVE into `live_door.json`, but nothing reads it (the promoter consumer is deferred). | A second engine. A committed `REPLICATION.json`. A reader for `live_door.json`. | Tier S |
| H9 | Counterfactual failure search, architecture level | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. Report-only. | A search that changes the factory, allocator or world model. | Tier S |
| H10 | Compute OS (CPU/GPU/RAM/net/tokens) | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | #55 `09e7bc81`: the bottom alpha-rank quartile loses its boost, so pricing binds both ways but never below base. LIVE #88 exports the cap to the child (`QUANT_LEG_BUDGET_S`). | CPU seconds only. No leg is ever cut below base. No committed `CYCLE_PRICING` or `research_budget` with `authoritative:true`. | Tier S |
| H11 | Global state replay at any second | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. `REPLAY.json` has no reader. | Market, model and budget state. A consumer. | Tier S |
| H12 | Continual recovery / chaos experiments | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✗✗✓✗ | LIVE: restore drill (weekly), `dr_drill.py`. #55: S42 `gateway_drill` runs the real gateway under 7 faults in a sandbox, hourly. Its own test fails (sends 1 ≠ 2), so T is ✗ on #55. Its findings are not fixed and gate nothing. | No real process kill, MT5 disconnect or VPS-loss drill. No failover. No committed drill artifact. | Tier S |
| H13 | Mechanism discovery from non-finance fields | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `cross_science:<lab>` cells are drained by `expression_factory`. | Box evidence of a judged or certified conversion. | Tier S |
| H14 | Automated abstraction discovery | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `grammar_bias` is read from `data/tier_s/grammar.json`. | No `grammar.json` on any ref. The last recorded run learned 0 primitives. | Tier S |
| H15 | Scientific memory compression | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. | Researchers do not consume it as authority. No fresh artifact. | Tier S |
| H16 | Human–machine separation of powers | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `_constitution` withholds new rows. A human did re-sign the gauntlet on LIVE, but #55's own sealed edits (promoter, rails) are still unsigned. | The gauntlet reads no constitution (S01 BLOCKED_ON_USER). The ratification ledger is empty. promoter and rails need re-signing. | Tier S |
| ADM | Subsystem admission rule (8 gains) | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | #55 `contracts.py` and `control_arm.py`. The control arm is now pinned at 1.0 (`652d81cd`). `authority.suspended()` exists. `check_tier_s_program.py` in the law gate passes (33 BUILT / 11 PARTIAL / 2 BLOCKED). | Tier S organs only. Nothing is removed. No committed `AUTHORITY.json` or box attestation. | Tier S |
| DP1 | Finish/wire everything | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | LIVE `tier5_audit.json` in the law gate. #55: the ledger no longer self-grades. DONE requires box attestation (`box_evidence.attested`, host `vmi3571445`), and 0 layers are DONE. A is ✓ on #55 because the checker now fails an unattested DONE. | 44 layers are BUILT or PARTIAL with no attestation. The 52 PARTIAL in tier5. No completed green CI. | Institutional |
| DP2 | Remove dormant/partial components | MISSING | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Neither ref deletes a component. | A retirement pass with a deletion ledger. | Institutional / Tier S |
| DP3 | Repair the validation defects | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | 0.014863 is still at `effective_trials.py:309` and `gate_policy.py:84`. `audit-p0-true-lockbox` (#52) is not an ancestor of LIVE. | Merge #52, measure the variance, migrate the lockbox==wf_oos certificates. | Institutional |
| DP4 | Clear the judging backlog | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | LIVE #77 parks dead or unbuildable cells, fetches missing charts and fences the drain (`judge_coverage.py` +281, `check_judge_coverage.py`). #88 sets self-stop floors for timed-out legs. The only committed reading is still the 09-30 `TIER1_BREADTH_REVIEW.json`: 5,266 judged/day against 8,303 created, backlog 1,398,727 and growing. #55's `docket_keff` now CONFLICTS with #77 in `judge_coverage.py`. | A box reading after #77 showing judged ≥ created and the backlog shrinking. Resolve the #55 conflict. Green CI. | Institutional |
| DP5 | Measure actual independent breadth | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | Unchanged. k_eff 2.526 on 453 nominal (09-30 review). The committed `effective_breadth.jsonl` still ends 09-16 at 2.057. | Append the reading so the two agree. Green CI. | Institutional |
| DP6 | Research-budget allocation sovereign | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | #55: alpha rank now also withdraws boosts. The only committed `research_budget.json` (09-23) says `authoritative:false`. `box_evidence` would digest `research_budget` with its `authoritative` flag, but no box evidence exists. | An applied box reading with `authoritative:true`. Residents and tasks are still excluded. Nothing goes below 1.0x. | Institutional |
| DP7 | Allocator sovereign | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | New on LIVE: #86 stops `heal_silent_demotions` from lifting the promoter's zero-heat STANDBY rows back to LIVE (`test_standby_flap.py`), so an allocator zero now survives the healer. #55 `652d81cd`: a zero Tier S exchange factor reaches `pf_allocator` as a zero tilt. `audit-p0-allocator-sovereignty` (#53) is still unmerged, and the min-lot and gold floors still override a zero. | Merge #53. Show a box pass sized by the allocator. Green CI. | Institutional |
| DP8 | Cost truth mandatory | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Unchanged. #52 and #53 are unmerged. | Merge both, migrate `sleeves.json`. | Institutional |
| DP9 | CI permanently green | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | LIVE: the gauntlet was re-signed by a human (`3167eb6f`). The seal is 0/18, and the LAW GATE step passed on `02057ffa` (run 36710180868, still in progress). Every other run since 846ce9de was cancelled, and the last completed run was red. #55 merged would put 2 breaches (promoter, rails) back into the law gate and has a failing test, so it is MISSING on the #55 score. | One completed green run on LIVE. Re-sign promoter and rails before #55 merges. Required checks. | Institutional |
| DP10 | Recursive research competition | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. | Winners gain only compute share. 0 independent discoveries. No committed artifact. | Tier S |
| DP11 | Accumulate untouched forward/live evidence | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | Downgraded from TIME-BOUND. #84's own comment in `forward_enrolment.py` says: "Measured on the box 2026-09-30: forward ledgers had not moved in 7 days while every clock still read ACTIVE". So "machinery runs" was false, and the 837/837 enrolment counted stalled clocks. `ENGINE_SILENT` detection and repair are now merged. There is no reading since. | A box census after #84 with `n_silent` 0 and ledgers advancing. The cert→clock latency. Green CI. Then time. | Institutional |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. The ledger itself now marks S02 PARTIAL ("bitemporal store on a real research data path … being built"). | The audit must gate certificate data. A committed verdict. | TS |
| AC13 | Research methods compete experimentally | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. The winner is a toy genome or a compute price. Money-path adoption is still a PROPOSAL. | Winning methods must take over real judging or execution. A committed arena artifact. | TS |

Counts on LIVE: DONE 0 / PARTIAL 15 / MISSING (branch-only) 12 / MISSING 1 / EXCLUDED 0 / TIME-BOUND 0 (28 rows). Against v2: DP7 and DP9 moved up to PARTIAL (LIVE #86 and the human re-sign), and DP11 moved down from TIME-BOUND to PARTIAL (the forward engine was silent for 7 days).
Counts if #55 merged: DONE 0 / PARTIAL 24 / MISSING (branch-only) 2 (DP3, DP8) / MISSING 2 (DP2, DP9) / EXCLUDED 0 / TIME-BOUND 0 (28 rows). The merge now needs manual resolution of `judge_coverage.py`. No row reaches 7/7. DP4 and DP5 are 6/7 and fail on C only.
AC3 and AC13: MISSING (branch-only) on LIVE. PARTIAL if #55 merged.

Seal: LIVE clean (0/18, gauntlet re-signed 09-30T11:35 by a human commit 3167eb6f). #55 tip breach (3/18: external_gauntlet, promoter, rails). #55-merged tree breach (2/18: promoter.py 52d6f4b4→1041a40e, rails.py e832bd4c→e01e6027).

LIVE changes since 846ce9de: #77/#84/#86/#88/#89/#91 merged plus a human re-sign of external_gauntlet (seal now 0/18). No new committed artifact (no research_budget, breadth or judging reading). #52 and #53 are still unmerged. CI on 02057ffa is in progress with the LAW GATE passed, and there is no completed green run.

### Claims verified / failed
1. VERIFIED: "The door fails closed." `block()` returns `DOOR_ERROR` when a check raises. FAILED in part: `promoter.tier_s_block` still returns None on an import failure, and a stale or absent verdict file still withholds nothing.
2. VERIFIED: "A layer is DONE only on the trading box's attestation." The ledger is 0 DONE / 33 BUILT, and the checker rejects an unattested DONE. This retires the v2 self-grading failure. No attestation exists yet.
3. FAILED: "The door reviews rows already LIVE." `live_door.json` is computed but read by nothing. `promoter.py` is unchanged, and its consumer is deferred to the "desktop batch".
4. FAILED: "S42: the real gateway under a faulty MT5 double" works. Its own test fails in a clean #55 worktree (sends 1 vs 2), and the 2 gateway defects it found are unfixed.
5. VERIFIED: "A ZERO reaches the allocator as zero" (tilt level, heat-neutral). It does not beat the min-lot and gold floors, and #53 is unmerged.
6. VERIFIED: "Alpha rank binds both ways." It withdraws boosts but never goes below 1.0x base, so no leg is ever cut.
7. FAILED: box evidence. "box_evidence carries the named outputs … so they reach git through the box's sync." No `box_evidence.json` exists, and the box pulls LIVE, which does not contain #55.
8. FAILED (from v2, still open): promoter and rails are still unsigned on #55. Merging reintroduces 2 law-gate breaches onto a LIVE that is now clean.

### Top gaps
1. **Re-sign `promoter.py` and `rails.py`** in `IMMUTABLE_MANIFEST.json` with a human commit before #55 merges. LIVE's seal is now clean, and #55 would break it again (0 → 2).
2. **Resolve the new `judge_coverage.py` merge conflict** (#55 `docket_keff` vs LIVE #77), and fix the failing `test_tier_s_gateway_drill.py` so #55's CI can be green.
3. **Get the first box attestation.** Merge #55, let the box run `tier_s`, and commit `data/tier_s/box_evidence.json`. Until then R is ✗ on all 46 layers and on every H/ADM row.
4. **Close the door's remaining fail-open paths.** Handle an import failure in `promoter.tier_s_block` and a stale or absent verdict file. Add a promoter reader for `live_door.json` (sealed, so it needs the re-sign in gap 1).
5. **Forward evidence was stalled for 7 days on the box** (#84). A post-#84 census with `n_silent` 0 is needed before DP11 can count time. Judging still has no reading after #77 (5,266 judged vs 8,303 created per day).
6. **#52 and #53 are still unmerged** (DP3, DP7, DP8). The DSR constant is live, and the floors override an allocator zero. No authoritative `research_budget.json` has been committed.

