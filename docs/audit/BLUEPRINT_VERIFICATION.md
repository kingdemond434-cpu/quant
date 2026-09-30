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

**C on LIVE.** Two seals disagree on LIVE. `check_immutable_evaluator.py` passes (0 of 18), but the quantbench QB-002 corpus (`desks/mt5/data/quantbench/corpus.jsonl`, pinned 09-28 in 0ba716ab) was never re-pinned after the manifest re-signs (adaba442, 3167eb6f), so `test_quantbench` fails. `external_gauntlet.py` genuinely changed (0f483139, 7379cbf7, e7eace79). `allocator_proof.py` and `state_admission.py` differ only by line endings: their CRLF hashes equal the pins, so QB-002 fails on every LF checkout, CI included. No CI run on LIVE has completed green since the strict re-score began, so C fails on every row.

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

1. **Red CI on LIVE** (every row): re-pin the QB-002 corpus to the signed manifest with line-ending-normalised hashes, and fix the five failing MT5 desk test files.
2. **Nothing Tier S is on LIVE** (46 rows plus 10 H/ADM rows): PR #55 (at `25e14650`; it conflicts with LIVE in the two runtime_state files) would still reach 0 DONE, because it adds two seal breaches (`promoter.py`, `rails.py`) and no Tier S artifact exists anywhere. Its only money-path authority is a withhold-only promotion door; the exchange, execution capture, constitution values and FREEZE reach no sizing or allocator code.
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

### 2026-09-30 12:55Z: Tier S batch 7 (PR #55 at `25e14650`, LIVE at `69da0158`)

The builder merged live, fixed the gateway drill import and the allocator clamp, made the door fail closed on missing, stale or malformed files, added a live-sleeve review, and built S02, S04, S09, S13, S16, S21, S23, S28, S31 and S33. Strict result: **still 0 of 138**, and every section count is unchanged (B1 30 PARTIAL, B2 16 PARTIAL, C 15 PARTIAL / 12 branch-only / 1 MISSING on LIVE).

Verified: 304 of 306 Tier S tests pass (the 2 failures are pandas-3-only; all pass on the pinned 2.3.3). The gateway drill passes. Tilts below 0.5 now reach the allocator. `block()` withholds on absent, stale or malformed input. The ledger reads 43 BUILT / 1 PARTIAL / 2 BLOCKED with 0 DONE claimed. The new builds' call sites are real. #55 gains A on L2, L7, T2, T4, T9 and T21, I on T16 and T28, and T on L15 and T23.

Claims that failed:

- **"No conflicts."** #55 conflicts with LIVE `69da0158` in `docs/research/RUNTIME_STATE.md` and `runtime_state.json`; the clean merge was onto an older LIVE.
- **"Only rails.py left."** Both `promoter.py` and `rails.py` are still unsigned; CI's law-gate log prints only the first breach.
- **"Door reviews live sleeves."** `live_door.json` still has no reader.
- **Import-error fail-open.** `promoter.tier_s_block` (promoter.py:1581) still ends `except Exception: return None`.

New findings:

- **LIVE's seal is split** (see "C on LIVE" above). This corrects the batch-6 entry, which called LIVE's seal clean; the drift was already present at `02057ffa`. It also corrects the batch-6 relay, which guessed #88 or #89 moved the files: no commit since 3167eb6f touches them.
- **Five LIVE test files fail** (`test_scalp_promotion`, `test_event_surprise`, `test_macro_regime`, `test_certificate_single_writer`, `test_universe_producers_merge`), moving T to ✗ on H2, H5, DP1, DP7, DP9 and DP11.
- **Post-merge risk:** with the door failing closed on stale input and `tier_s` a rotated leg capped at 1,500 s, every new LIVE row is withheld until the first box pass and after any 6-hour gap.
- **No box artifact** exists anywhere. The committed cloud run (5527887b, `docs/research/tier_s_runs/`) says `counts_toward_done: false`, so R fails on every row.

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

Checked 2026-09-30 ~13:30Z. LIVE = `origin/claude/llm-auto-upgrade-verify-gcjac3` @ `69da0158` (origin has since moved to `7b69c6ff`, +1 scalp test file, no Tier S). TIERS = `origin/claude/tier-s-institution` @ `25e14650` (PR #55, draft; GitHub's PR head is already `b3620bb5` = +2 commits: door-input-missing fails the leg loudly, test import fix — not scored, changes no mark).

**Facts (measured, not taken from the builder):**
- **Merge: claim "no conflicts" is STALE.** `ae7f6263` merged LIVE @ f54f0155 clean, but LIVE has moved 13 commits since. `git merge-tree` onto `69da0158` (and onto `7b69c6ff`, and PR head `b3620bb5` onto `7b69c6ff`) CONFLICTS in `docs/research/RUNTIME_STATE.md` and `docs/research/runtime_state.json` (derived attestation docs — trivial, but GitHub reports `mergeable_state: dirty`). 83 ahead / 13 behind.
- **Seal: claim "only rails.py left" is FALSE.** `check_immutable_evaluator.py`:
  - TIERS `25e14650`: **2 breaches** — `promoter.py` (52d6f4b4→1041a40e) and `rails.py` (e832bd4c→e01e6027). `external_gauntlet.py` breach is gone (inherited LIVE re-sign).
  - Merge tree (LIVE 69da0158 + TIERS, built and checked): **same 2 breaches**.
  - LIVE `69da0158`: OK, 0 breaches; `check_immutable_rails`: seal HELD. (TIERS: rails "seal BROKEN".)
  - PR #55 CI run 36714627280 (`quality`): **FAILED** on the law gate. Its log prints only the first breach line (rails.py), which is likely why the builder saw one; the promoter breach is real.
- **QB-002 drift on LIVE confirmed.** Corpus `desks/mt5/data/quantbench/corpus.jsonl` QB-002 pins 4 sha256s; on LIVE 69da0158 three differ: `external_gauntlet.py` (expects 17f8a409…, is e8389c82…), `allocator_proof.py` (bb2cb3a5… vs 09f8f0b9…), `state_admission.py` (ae7a8aec… vs 1fc3e487…). `promoter.py` matches on LIVE; on TIERS it also drifts (4/4). The evaluator seal and the quantbench corpus disagree — C ✗ on LIVE regardless of Tier S.
- **Tests (TIERS worktree, `-p no:cacheprovider`):** 16 tier_s_* files + test_cycle_pricing + tests/tiers + test_research_budget + test_bandit_authority_and_freeze = **306 tests: 304 pass, 2 FAIL** under this container's pandas 3.0.6: `test_tier_s_closure_agent_worlds::{test_both_families_…, test_a_sleeve_is_measured_…}` — `synthetic_regimes._scale_col` writes into a read-only CoW array (`ValueError: output array is read-only`). Re-run under the pinned `pandas==2.3.3` (pyproject `<3`, CI installs 2.3.3): **9/9 pass**. So T ✓ at the pin; the S16 code breaks on pandas 3.
- **Gateway drill fix: VERIFIED.** `test_tier_s_gateway_drill` passes (2/2); child gets repo root on PYTHONPATH (2c8f80c4).
- **Allocator clamp fix: VERIFIED.** `pf_allocator.py:2123`: when `sf < TILT_LO` the tilt is `clamp(other factors)·sf`, so 0<sf<0.5 is applied under the floor; test in test_tier_s_organs passes.
- **Door fail-closed: VERIFIED inside `block()`, FAILS OPEN one level up.** Missing/stale(>6h)/malformed `door_verdicts.json` etc. → `DoorReadError` → `DOOR_ERROR` withhold (7de6ccca). But `promoter.tier_s_block` (promoter.py:1575-1582) still `except Exception: return None` — an import error drops every check. Side effect: after merge, until the box runs the `tier_s` leg, every new LIVE row is withheld as DOOR_ERROR (absent verdicts).
- **`live_door.json` has NO consumer.** Only writer `promotion_authority.review_live` and `sync_shadow_to_git.ps1:387` mention it; the cloud copy literally says `"consumer": "… desktop batch: promoter.py is sealed"`.
- **Artifacts:** no `desks/mt5/data/tier_s/*` (incl. `box_evidence.json`) on either ref. 5527887b committed a cloud pass under `docs/research/tier_s_runs/2026-09-30_cloud/` (TIER_S, allocator_tilts, box_evidence, door_verdicts, live_door, 30 organs incl. IMMUNE, ONLINE_FDR_ROWS, TOPOLOGY; no ALPHA_RANK). Its `box_evidence.json` says `host: vm`, `counts_toward_done: false`. Cloud outputs ⇒ R ✗ strict (partial at most) on every row.
- **LIVE carries no Tier S code:** no `libs/tiers/*`, no `tier_s.py`, no `tier_s` leg in `hourly_cycle.py`. LIVE marks unchanged from v3.
- **Checker:** `check_tier_s_program.py` rc 0 — **BUILT 43 / PARTIAL 1 (S12) / BLOCKED_ON_USER 2 (S01, S30)**, 0 DONE. Claim matches.
- **Batch-7 builds spot-checked (real call sites on #55):** S02 `run_edges_macro_fusion_sweep.pit_conditioned` reads `BitemporalStore.latest_known`; S13 `breadth_sweep.order_by_failure_memory`; S04 runtime blinding strips outcome fields in `miner_candidate_compiler`/`proposer_common`/`deepseek_cycle`; S09/S21 `prejudge_screen` tags cells in `run_external_backtest` and `merge_hypotheses` demotes flagged rows within family (reorder only, nothing removed); S33 `gauntlet_arena`; S23 `execution_science` report; S28 `shadow_desk`/`rollback`; S31 `check_formal_claim` fence in law gate; S16 closure/agent worlds.

Marks order: I W A T R D C. "#55" = as if merged (runtime_state conflict assumed resolved; D hypothetical). T ✓ on #55 is at the pinned pandas 2.3.3.

| ID | Item | Verdict | Marks | Evidence on #55 | Still missing | Owner |
|---|---|---|---|---|---|---|
| L1 | Truth Kernel | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | truth_kernel, constitution; door withholds loosened constitution, fail-closed in block | S01 blocked (gauntlet ignores constitution); promoter wrapper fails open; 2 seal breaches; box R | Tier S build |
| L2 | World Data OS | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | **A new:** macro-fusion sweep conditions signals via `BitemporalStore.latest_known` (S02) | One sweep only; no provenance/reliability on the main data path; box R | Tier S build |
| L3 | World Model | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | world_edges → compiler rows | Hypothesis generation only; stale graph; no flows/regional | Tier S build |
| L4 | Researcher Civilization | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | researcher_prices → cycle_pricing; runtime blinding now strips outcomes (S04) | No new non-LLM processes; box R | Tier S build |
| L5 | Hypothesis Ecology | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | QD/genomes/theory rows to intelligence/tier_s | Populations decide nothing | Tier S build |
| L6 | Research-Program Evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | program_evolution in tier_s leg | Challengers report only | Tier S build |
| L7 | Adversarial Science | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | **A new:** adopted defenders flag cells in run_external_backtest; merge_hypotheses demotes them in-family; S33 genomes judged on real gauntlet verdicts | Reorder-only (no gate changes); box R | Tier S build |
| L8 | Universal Validation | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | block() fails closed on missing/stale/malformed inputs | promoter.py:1581 fails open; live_door no consumer; seal; #52 | Both threads |
| L9 | Alpha Topology | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | alpha_rank two-sided in cycle_pricing; docket_keff | No ALPHA_RANK artifact even from cloud; two rank organs | Tier S build |
| L10 | Portfolio Intelligence | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | **Clamp fixed:** sf<0.5 applied under floor (pf_allocator:2123) | allocator_tilts only from cloud; ex×cap not renormalised; FREEZE→allocator unrouted; #53 | Other slices |
| L11 | Execution Intelligence | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | S23 report splits signal alpha / execution drag | 0 matched fills → inert; not learned | Other slices |
| L12 | Live Reality Engine | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | THEORY_REFUTED withholds; review_live → live_door.json; forward_reconcile.json on LIVE | live_door reaches no retirement | Other slices |
| L13 | Meta-Science | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | research_bandit leg publish() | Committed research_budget.json still authoritative:false | Tier S build |
| L14 | Architecture Evolution | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | twin, self_model, shadow_desk sandbox, rollback tested (S28) | S30 blocked; propose-only | Other slices |
| L15 | Operational Kernel | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | **T restored:** gateway drill test passes; drill in organ_chaos | Report only; no standby/failover | Other slices |
| T1 | Truth Kernel spec | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | journal, seal, constitution withhold | S01; no order-time lineage | Tier S build |
| T2 | World Data OS spec | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | PIT reads in macro sweep | Not on acquire_datasets; no € costs | Tier S build |
| T3 | World model graphs | PARTIAL | LIVE: ✓✓✗✓✓✓✗ / #55: ✓✓✗✓✓✓✗ | world_edges classification | No flows/regional; decides nothing | Tier S build |
| T4 | Researcher civilization + blinding | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | **A new:** runtime blinding strips held-out/lockbox fields, ledger blinding_runtime.jsonl | No independent-discovery evidence | Tier S build |
| T5 | AlphaEvolve-for-alpha | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | evolution, program_evolution | No LLM-in-loop code evolution | Tier S build |
| T6 | MAP-Elites 12 axes | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓✗✓✗ | qd_axes | Steers nothing | Tier S build |
| T7 | Researcher genomes | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | RESEARCHER_GENES | Steers tier_s rows only | Tier S build |
| T8 | Researcher market | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | prices 0.15 + bandit 0.20 → cycle_pricing | FLOOR 1.0: nothing loses compute below base | Tier S build |
| T9 | Red Queen per researcher | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | **A new:** prejudge_screen demotion; gauntlet_arena | Demote-only, never at the sealed gate | Tier S build |
| T10 | Planted traps / FREEZE | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | _freeze in fail-closed block; review_live | FREEZE not in allocator; live review unconsumed | Tier S build |
| T11 | Adaptive multiplicity | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✓✓✗✓✗ | online_fdr withholds over_budget | #52 unmerged; proxy p-values | Tier S (+#52) |
| T12 | Epistemic firewall | PARTIAL | LIVE: ✗✓✓✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | firewall.may in door reads | S12 PARTIAL: no runtime may() at the gates; wrapper fails open | Tier S build |
| T13 | Negative knowledge | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✓✗✓✗ | **breadth_sweep now reads failure_memory** (S13) | Other generators still don't; reorder only | Tier S build |
| T14 | Ancestry graph | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | effective_discoveries → alpha_rank | No code/data ancestry | Tier S build |
| T15 | Effective Independent Alpha Rank | PARTIAL | LIVE: ✓✓✓✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | alpha_rank two-sided; docket_keff | Box ALPHA_RANK; seal; CI green | Tier S build |

Counts LIVE: DONE 0 / PARTIAL 30 / MISSING-branch 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0.
Counts #55 if merged: DONE 0 / PARTIAL 30 / MISSING-branch 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0. All 30 fail R (cloud-only) and C (2 seal breaches, law-gate CI red, merge dirty). Movement vs v3: A gained on L2, L7, T2, T4, T9; T regained on L15.

### Remaining gaps
1. Re-sign BOTH `promoter.py` and `rails.py` (not just rails) and, in the same signed edit, make `promoter.tier_s_block` fail closed on import error — CI `quality` is red on the law gate.
2. Resolve the `RUNTIME_STATE.md` / `runtime_state.json` conflicts (#55 dirty against LIVE 69da0158/7b69c6ff).
3. Merge, then one box run of the `tier_s` leg with the sync committing `desks/mt5/data/tier_s/box_evidence.json` from vmi3571445; cloud outputs don't count. Until then the fail-closed door withholds every new LIVE row as DOOR_ERROR.
4. Give `live_door.json` a consumer (promoter retirement), route FREEZE into allocator tilts, S01 constitution → gauntlet, S12 runtime firewall at the gates.
5. Fix `synthetic_regimes._scale_col` for pandas 3 CoW (2 S16 tests fail on 3.0.6), or keep the `<3` pin enforced everywhere.
6. Reconcile QB-002: LIVE's quantbench corpus pins stale hashes for external_gauntlet, allocator_proof, state_admission (and promoter after merge) while the evaluator seal passes.
7. Produce an ALPHA_RANK artifact (absent even from the cloud run); drop FLOOR 1.0 so legs/researchers can lose compute; re-normalise ex×cap.
8. Execution intelligence stays inert until matched fills > 0.

## B2 — Tier S sections 16–30 (T) and final loop

LIVE = claude/llm-auto-upgrade-verify-gcjac3 @ 69da0158. TIERS = claude/tier-s-institution @ 25e14650 (PR #55, draft, unmerged; 83 ahead / 13 behind LIVE).
Marks: I W A T R D C, in that order. "#55" is scored as if #55 were merged unchanged, with the conflicts resolved.
Baseline: B2_v3 (TIERS @ a0de5855 / LIVE @ 02057ffa). New since then: 20 TIERS commits (27ee1360 … 25e14650), the batch-7 builds.
Note: the PR head has since moved to b3620bb5 (2 more commits, including "a door input missing past two hours fails the leg loudly"). **They are not scored here.** CI on b3620bb5: `quality` **failure**, `mt5-money-path` queued.

### Facts (checked at these refs)
- **LIVE still has no Tier S code.** LIVE has no `libs/tiers`, no `tier_s` leg and no Tier S tests. Its 13 new commits are cross-sectional breadth and fetch fencing. **Correction to v3:** LIVE's `execution_science.py` has no scheduler reference (grep across .py/.ps1/.sh/.json finds none), so T23's LIVE W mark is now ✗.
- **Merge: conflicts.** `git merge-tree 69da0158 25e14650` conflicts in `docs/research/runtime_state.json` and `RUNTIME_STATE.md`. Both are derived files. The `judge_coverage.py` conflict from v3 is gone.
- **Seal: still 2 breaches, at the ref and on the trial-merged tree.** `check_immutable_evaluator.py` flags `promoter.py` (52d6f4b4… → 1041a40e…) and `rails.py` (e832bd4c… → e01e6027…). The stale external_gauntlet breach from v3 is gone. LIVE alone is OK. So **C ✗ on every row.**
- **Tests pass under the production pandas pin, and 2 fail under pandas 3.** Tier S desk tests, `test_cycle_pricing*` and `tests/tiers`: 272 tests.
  - **All pass under pandas 2.3.3**, the pin in pyproject/requirements-vps (run in a scratch venv).
  - Under this container's pandas 3.0.6, 2 fail: `test_tier_s_closure_agent_worlds` (×2). The cause is `synthetic_regimes._scale_col` writing in place into `np.asarray(df[col])`, which is read-only under copy-on-write. The world then reads UNMEASURED; it fails safe, but it is fragile.
  - The S42 gateway drill now passes with PYTHONPATH unset (v3 defect fixed, 2c8f80c4).
- **Ledger:** `check_tier_s_program.py` prints "BUILT 43; PARTIAL 1; BLOCKED_ON_USER 2" and exits 0. It claims no DONE. `check_formal_claim.py` exits 0.
- **Still no box artifact.**
  - The `docs/research/tier_s_runs/2026-09-30_cloud/` bundle (5527887b) says itself that it is not box evidence (host `vm`, `counts_toward_done: false`).
  - It was also produced **before** the batch-7 builds. Its `TEST_INVENTION.json` still says "adoption … only by principal ratification", and `WORLDS.json` has 0 worlds measured.
  - `sync_shadow_to_git.ps1` now lists `data/tier_s/box_evidence.json` and `live_door.json`, but only on the branch. Every R is ✗.
- **"Allocator applies a Tier S factor below 0.5": VERIFIED.**
  - `pf_allocator.apply_allocator_evidence`: if `sf < TILT_LO`, then tilt = clip(other factors) × sf, which is 0 for sf = 0.
  - Unchanged: the tilt zeroes the sleeve's **mean**, not its weight.
  - Also unchanged: `allocator_proof.contest` still builds equal_weight / inverse_vol / risk_parity over **every** name, and `gateway.book_from_allocation` falls back to that `book_fallback`. So an exchange zero is still re-funded on stale or failing proof passes.
- **"Door fails closed": TRUE inside `block()`, but the promoter still fails open.**
  - `promotion_authority._required` now turns an absent, stale (>6 h), torn or non-object verdict file into `DOOR_ERROR` (withhold), and so does a damaged constitution or ratifications file.
  - But `promoter.tier_s_block` (promoter.py:1575–1582) still does `except Exception: return None` ("An unimportable module withholds nothing"), so an import or path fault still fails open.
  - **New risk if merged:** `tier_s` is still a rotated "meta" leg (cap 1,500 s). The first adoption, before any tier_s pass, or any 6 h gap, now withholds **every** new LIVE row as DOOR_ERROR. This is billed as a rail, but it is a growth block that no evidence backs.
- **"Door reviews live sleeves": still a report only.** `git grep live_door` finds a writer (`promotion_authority.LIVE_DOOR`) and the sync script, and no reader. It has no authority over a LIVE row.
- **Unchanged:** FREEZE reaches no sizing code. The DSR variance is still the constant 0.014863 (`effective_trials.py:309`). The honesty channel (T27) still has no test naming it. `theory.compose` is still untested.

| ID | Item | Verdict | Marks | Evidence on #55 | Still missing | Owner |
|---|---|---|---|---|---|---|
| T16 | Counterfactual World Lab | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✓✓✗✓✗✓✗ | `closure_worlds.py` (3 closure worlds) and `agent_worlds.py` (ecologies) are built into `synthetic_regimes` (a scheduled leg). `organ_worlds` joins them per certificate into `worlds_by_certificate.json`. Tests pass on pandas 2.3.3. **I gained.** | The flags (`dies_on_market_closure`, `halt_fragile`, …) reach `ev["stress"]["flags"]`, but `review_panel` reads only `stress.exp_x5`, so no break flag acts (A ✗). Fails under pandas 3 (read-only array). No artifact; C. | Tier S build |
| T17 | Alpha Theory Compiler | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | Unchanged. | `compose` untested; no authority; no artifact; C. | Tier S build |
| T18 | Theory↔Evidence graph | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `THEORY_REFUTED` withholds a new LIVE row. `block()` now also withholds on absent or stale door inputs. | The promoter wrapper still fails open. `live_door.json` has no reader. The stale-input withhold rides a rotated leg (growth-block risk). No artifact. C. | Tier S build |
| T19 | Heterogeneous non-LLM intelligence | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged. | No solver or prover; no authority; no artifact; C. | Tier S build |
| T20 | AI peer review panels | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `REVIEW_PANEL_FAILED` withholds a new row, and the panel file must now be fresh. | Fixed if-rule reviewers; world flags go unread; the promoter wrapper fails open; the live-row review has no consumer; no artifact; C. | Tier S build |
| T21 | Auto-invent new tests | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | `_ratify_invented`: a gate that survives the sealed suite (seed 5150) is appended to `test_ratifications.jsonl` and adopted into `PREJUDGE_RULES.json`. `run_external_backtest.prejudge_verdict` tags candidates, and `merge_hypotheses` demotes flagged rows within their family. Consumers verified by grep. **I and A gained** (A is research-ordering authority only). | No ratified rule on any ref (the cloud run predates this code). Demotion only reorders, and removes nothing. DSR constant; no artifact; C. | Tier S build |
| T22 | Auto-invent research grammars | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged. | No new representation class; no budget authority; no artifact; C. | Tier S build |
| T23 | Execution as autonomous science | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✓✓✗✓✗ | `execution_science` is its own leg on the branch and writes `EXECUTION_SCIENCE.json` every run (UNMEASURED with its reason). `split_fills` separates signal alpha from drag. Like-for-like drag reaches the exchange bids in `tier_s.py:3334`, and capture reaches pf_allocator. `test_tier_s_execution_science` passes. **T gained.** LIVE W corrected to ✗ (unscheduled there). | `split_fills` is a "hook", so live fills do not recalibrate; matched_fills = 0; no slicing, urgency or adverse-selection model; no artifact; C. | Tier S build |
| T24 | No-trade first-class | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✗✓✓✓✓✓✗ | A factor in (0, 0.5) is now applied below the floor (verified). ZERO gives tilt 0. | The zero is still a zero mean, not a zero weight, and the `book_fallback` baselines (over every name) re-fund it. #53 unmerged; C. | Tier S build / Institutional (#53) |
| T25 | Opportunity Exchange | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓✗✓✗ | The chain holds, now with execution drag in the bids. The control arm is still exactly 1.0. | The ZERO→book leak through the fallback. Neutral if the rotated leg misses 6 h. FREEZE does not reach it. No box artifact; C. | Tier S build |
| T26 | Live prediction-accounting | PARTIAL | LIVE: ✗✓✗✓✗✗✗ / #55: ✗✓✓✓✗✓✗ | Unchanged. | No vol, factor or correlation forecasts, and none per model; no artifact; C. | Tier S build |
| T27 | Live reality outranks backtests | PARTIAL | LIVE: ✗✓✓✓✓✗✗ / #55: ✓✓✓✓✓✓✗ | Unchanged. | No test names the honesty channel; no reach into admission for new discoveries. C: 2 seal breaches if merged. | Tier S build |
| T28 | Digital twin (shadow desk) and rollback | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | `shadow_desk.py` replays the candidate code and config challengers beside the sealed release in a sandbox (terminal touches refused), written to `reports/TWIN.json`. `tests/tiers/test_rollback.py` tests the one-commit rollback on a throwaway repo. **I gained.** | Nothing reads the TWIN verdicts: they gate no adoption, and only a `twin` bool reaches `worlds_by_certificate`. Rollback is still a human `--apply-rollback`, and Adopt-And-Seal has no regression stop. No artifact; C. | Tier S build |
| T29 | Self-model | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓✗✓✗ | The gateway drill test is now green in a clean env (child import fixed). | No authority; hand-set p_fix and cost; no artifact; C. | Tier S build |
| T30 | Architecture evolution | PARTIAL | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✓✗✓✗✓✗ | Unchanged. The ledger still says BLOCKED_ON_USER. The Adopt-And-Seal diff is release signing only. | Money-path adoption refused; no regression stop; no artifact. | Tier S build |
| LOOP | Closed research→capital loop inside a Truth Kernel | PARTIAL | LIVE: ✗✓✗✗✗✗✗ / #55: ✗✓✗✗✗✓✗ | Adds, since v3: an allocator factor below 0.5, stale door inputs that withhold, ratified tests that reorder the docket, execution drag in the bids, and the shadow desk. | The promoter wrapper fails open. FREEZE does not reach the allocator. The fallback re-funds exchange zeros. `live_door.json` and `TWIN.json` have no reader. DSR constant. #52/#53 unmerged. No end-to-end loop test. No box artifact. promoter/rails unsigned. Merge conflicts (runtime_state). CI red on the newer head. | Tier S build / Institutional |

Counts on LIVE: DONE 0 / PARTIAL 16 / MISSING (branch-only) 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (16 rows).
Counts if #55 merged: DONE 0 / PARTIAL 16 (16 rows).
- **Marks gained (#55):** T16 I, T21 I+A, T23 T, T28 I.
- **Mark lost (LIVE):** T23 W, a correction.
- **Best rows:** T27 is still best at 6/7. T18, T20, T21 and T25 are at 5/7.
- **No row can reach DONE:** R and C fail on every row.

### Remaining gaps
1. **Seal:** re-sign `promoter.py` and `rails.py` (2 breaches on the trial merge). Resolve the `runtime_state.json`/`RUNTIME_STATE.md` conflict. Make CI green: `quality` fails on the PR's current head, b3620bb5.
2. **Zero box artifacts:** every R is ✗ until #55 is on LIVE, the box adopts it, a tier_s pass runs there, and `box_evidence.json` from `vmi3571445` is committed. The cloud bundle predates batch 7 and does not count.
3. **Promoter fail-open:** `tier_s_block`'s `except Exception: return None` still discards the door's new fail-closed behaviour on any import or path error (sealed edit plus re-sign).
4. **Door stale-input withhold vs the rotated leg:** once merged, every new LIVE row is withheld until the first tier_s pass on the box, and again after any 6 h gap in the rotated, 1,500 s-capped leg. Either make `tier_s` a non-rotated leg, or measure that rail's missed growth before adoption.
5. **Exchange zero ≠ zero weight:** drop zero-tilted sleeves from `ev` and the baselines, or pass them through `book_zeroed`. The fallback still re-funds them.
6. **Unread outputs:** `live_door.json` (no reader), `TWIN.json` shadow verdicts (gate nothing), and closure/agent world flags (the review panel reads only `exp_x5`).
7. **pandas-3 fragility:** `synthetic_regimes._scale_col` writes into a read-only array. It passes under the 2.3.3 pin, but the new worlds would go UNMEASURED on any pandas-3 host.
8. **Still uncashed:** FREEZE → allocator; the DSR constant 0.014863; live-fill recalibration (`split_fills` is a hook, matched_fills = 0); automatic rollback / regression stop; #52/#53; tests for `theory.compose` and the honesty channel.

## C — 16 hardening items (H), depth priorities (DP), admission rule (ADM)

Re-scored 2026-09-30 ~12:30Z. LIVE = `claude/llm-auto-upgrade-verify-gcjac3` @ `69da0158` (was `02057ffa`, 15 commits). #55 = `claude/tier-s-institution` @ `25e14650`. A newer #55 head, `b3620bb5`, exists and was not scored.
Marks are in the order I W A T R D C. "#55" means scored as if #55 were merged into LIVE as-is. R counts a committed artifact from any host. A cloud artifact is marked R✓(cloud), which is not box evidence.

**LIVE changes since 02057ffa** (29 files, +3142/−1366):
- #85 adds cross-sectional class books. The hourly leg `cross_sectional_breadth` seeds class-book cells into `proposer_common.donate` and writes `reports/CROSS_SECTIONAL_BREADTH.json`, which is not committed. Share CFDs may now mint hypotheses in six class-book families (the amended two-lane order).
- `7117aa51` makes clock recovery prove and finish its repairs. `clock_fixer.enrol_if_needed` now runs enrolment on any gap in the scalar census, the control-plane apply pass heartbeats itself, and actuator windows are clipped to the remaining budget.
- `8dc29efa` fences scheduled fetches from detached git maintenance (`Adopt-Release.ps1`, `intel_ship_adopt.ps1`).
- #95 is a docs matrix. `runtime_state.json` was re-attested.
- **No new committed artifact for any C row.** There is no research_budget, breadth, judging, forward-census or drill reading. #52 and #53 are still unmerged.
- Touches: DP5 and DP10 (#85 adds breadth sources, not a measurement), DP11 and H12 (clock recovery), DP1 (wiring). No verdict moves.

**Seal. LIVE is now internally INCONSISTENT: two seals disagree.**
- `scripts/check_immutable_evaluator.py` on LIVE 69da0158 reports **OK, 0/18**. `IMMUTABLE_MANIFEST.json` pins the gauntlet at `e8389c82`, from the human re-sign `3167eb6f`.
- `desks/mt5/tests/test_quantbench.py::test_no_historical_defect_has_returned` **FAILS locally on LIVE**, reproducing the #95 CI job. Its QB-002 corpus row (`data/quantbench/corpus.jsonl`, written in `0ba716ab` on 09-28) is a second, hand-kept sha256 list, and nobody updated it when the manifest was re-signed (`adaba442` 09-29, `3167eb6f` 09-30).
- **No commit in `3167eb6f..69da0158` touches any of the three files.** The drift predates both LIVE heads, so v3's "C clean on LIVE" was already wrong at 02057ffa.
- Per file:
  - `external_gauntlet.py`: a real content drift. The pin `17f8a409` matches no LF or CRLF blob in the last 40 revisions. The file moved in `0f483139` (09-29), `7379cbf7` and `e7eace79` (09-30, all Codex), and the second two were human-reviewed in `3167eb6f`. The corpus was never re-pinned.
  - `allocator_proof.py` and `state_admission.py`: **line-ending only**. Their CRLF hashes equal the pins exactly (`bb2cb3a5`, `ae7a8aec`). The pins were computed on a Windows (CRLF) checkout, so QB-002 fails on every LF checkout, CI included, and would pass on the box. The probe is platform-dependent.
  - `promoter.py`: matches its pin.
- Result: C ✗ on LIVE for every row whose C depends on the tree being self-consistent, which is all of them. Fix: re-pin QB-002 from the manifest (or have the probe read it) and hash normalised line endings.
- On #55 @ 25e14650, `check_immutable_evaluator.py` reports **2/18 breaches**: `promoter.py` (`52d6f4b4`→`1041a40e`) and `rails.py` (`e832bd4c`→`e01e6027`). The gauntlet breach is gone because #55 merged LIVE. QB-002 fails on #55 too.
- The merge-tree of LIVE with 25e14650 no longer conflicts in `judge_coverage.py`. It conflicts only in `docs/research/RUNTIME_STATE.md` and `runtime_state.json`, both derived.

**CI.**
- The LIVE run on 69da0158 (36714241201) is **queued**.
- Run 36710180868 on 02057ffa completed **cancelled**. v3 recorded it as in progress.
- There is still no completed green run on LIVE: UNMEASURED.
- The #55 run on 25e14650 (36714360579) was cancelled.

**Other failing tests on LIVE**, run locally at 69da0158. All 5 files reproduce the failure:
- `test_scalp_promotion` (4 tests: go-live, the forward clock as certificate, the retired scalp sleeve, STANDBY→LIVE on two readings). Bears on DP11 and DP7, so T is ✗.
- `test_event_surprise::test_the_registered_grounds_file…`, because `event_consensus_sources.json` is absent. Bears on H5 and AC3.
- `test_macro_regime::test_load_history_adds_real_yield`. Bears on H5 and AC3 (data truth).
- `test_certificate_single_writer::test_external_gauntlet_recovers_only_exact_gate_archive_rows`. Bears on H2 and DP3 (the sealed judge's archive recovery).
- `test_universe_producers_merge` (2 tests: a refresh drops symbols, an unreadable registry rebuilds). Bears on DP1 and AC3.
- Also `test_quantbench`, which bears on H2, H4 and DP9.
- Unrelated PR #67 (`05357b2d`) carries UNMEASURED-skip ports for event_surprise and macro_regime. They are not on LIVE.

**#55 since a0de5855** (merged LIVE twice):
- The door withholds on an absent or stale verdict (`7de6ccca`) and fails closed on damaged input (`27ee1360`). `promoter.tier_s_block` still returns None on an import failure (`except Exception: return None`).
- The gateway drill test now passes (`2c8f80c4`).
- S02, S13 and S31 got consumers (`fa1a3e70`): bitemporal PIT reads in the macro sweep, failure memory ordering `breadth_sweep`, and a `check_formal_claim.py --require-state` law-gate fence. It reads UNMEASURED here, 0/6 invariants gateway-backed, rc 0 without state. MODEL_ONLY passes.
- S33 genomes compete on the real gauntlet's verdicts (`bfda4521`).
- S04, S09 and S21 act on real paths (`a7f6b520`): blinding, a prejudge screen, Red Queen and test ratification.
- The box sync now publishes box_evidence and live_door (`6ea40135`).
- **One cloud run was committed** (`docs/research/tier_s_runs/2026-09-30_cloud/`, 30 organ JSONs). Its own ABOUT says "NOT box evidence", host `vm`, `counts_toward_done:false`.
- The ledger reads 43 BUILT / 1 PARTIAL / 2 BLOCKED_ON_USER / 0 DONE, and the checker passes.

| ID | Item | Verdict | Marks | Evidence | Still missing | Owner |
|---|---|---|---|---|---|---|
| H1 | Formal verification of money path | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | #55: `check_formal_claim.py --require-state` is in the law gate and fails on VIOLATED, a regression or (on the box) UNMEASURED. MODEL_ONLY passes, and today the gateway backs 0/6. The drill test is green. The cloud `FORMAL.json` is committed. | A VERIFIED claim, meaning the gateway backs every invariant. The drill's 2 send-path defects must be fixed. Box FORMAL.json. The seal (2 breaches). | Tier S |
| H2 | Independent evaluator civilization | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✗R✓(cloud)✓✗ | LIVE: the manifest seal is 0/18, but QB-002 disagrees (C ✗). `test_certificate_single_writer` (gauntlet archive recovery) and `test_quantbench` fail (T ✗). #55: absent or stale verdicts now withhold. | Reconcile the two seals. The promoter import path still fails open. No separate stack. | Tier S |
| H3 | Architecture evolution, sealed suites | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | #55 S33: genomes are judged against the real gauntlet's verdicts (`gauntlet_arena.py`). Adoption is still not applied to the gauntlet. | Adoption must change the real gauntlet, scheduler or execution. | Tier S |
| H4 | Immutable meta-benchmark, thousands of cases | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✗R✓(cloud)✓✗ | Unchanged. The quantbench corpus's own sealed-file case (QB-002) is stale on both refs, so the benchmark fails its own tree. | Re-pin QB-002. A release gate. A committed immune score from the box. | Tier S |
| H5 | Active information acquisition (EVOI) | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✗R✓(cloud)✓✗ | T ✗ on LIVE: `test_event_surprise` fails (missing `event_consensus_sources.json`) and so does `test_macro_regime` real yield. | A value-driven data buy. Green data tests. | Tier S |
| H6 | Research-search frontier estimator | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | Unchanged. A cloud `FRONTIER.json` exists on #55. | Floored at 1.0. No box artifact. | Tier S |
| H7 | Epistemic uncertainty engine, 5 levels | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | A cloud `EPISTEMIC.json` exists. It still has no acting reader. | A consumer that refuses on "not enough evidence". | Tier S |
| H8 | Cross-engine independent replication | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | #55 has a cloud `live_door.json`, and the box sync now publishes it. The promoter still does not read it. | A second engine. A reader for `live_door.json`. | Tier S |
| H9 | Counterfactual failure search, architecture level | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | Unchanged. Report-only. | A search that changes the factory or allocator. | Tier S |
| H10 | Compute OS | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. | CPU seconds only. No leg is cut below base. No authoritative budget. | Tier S |
| H11 | Global state replay at any second | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | A cloud `REPLAY.json` exists. It has no reader. | Market, model and budget state. A consumer. | Tier S |
| H12 | Continual recovery / chaos experiments | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | LIVE `7117aa51`: the clock fixer finishes enrolment on any census gap and heartbeats the control plane. A new chaos test was added (`test_control_plane_chaos`). #55: the drill test is green now (T ✓). A cloud `CHAOS.json` exists. | No real kill, disconnect or VPS-loss drill. The drill gates nothing. No box artifact. | Tier S |
| H13 | Mechanism discovery from non-finance fields | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | Unchanged. | A judged or certified conversion on the box. | Tier S |
| H14 | Automated abstraction discovery | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | A cloud `GRAMMAR.json` exists. `data/tier_s/grammar.json`, the path `grammar_bias` reads, still exists on no ref. | Grammar at the consumed path. Learned primitives > 0. | Tier S |
| H15 | Scientific memory compression | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✗✓✗✓✗ | #55: failure memory now orders `breadth_sweep` (an ordering, not authority). | Researchers do not consume it as authority. | Tier S |
| H16 | Human–machine separation of powers | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | Unchanged. promoter and rails are still unsigned on #55. | S01 is BLOCKED_ON_USER. Re-sign promoter and rails. | Tier S |
| ADM | Subsystem admission rule (8 gains) | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✓✓R✓(cloud)✓✗ | The ledger reads 43 BUILT / 1 PARTIAL / 2 BLOCKED and the checker passes. The cloud `CONTRACTS.json` exists. | Nothing is removed. No box attestation. | Tier S |
| DP1 | Finish/wire everything | PARTIAL | LIVE: ✓✓✗✗✓✓✗ / #55: ✓✓✓✗✓✓✗ | T ✗: `test_universe_producers_merge` fails (a refresh drops symbols it did not fetch, and an unreadable registry rebuilds). The rest is unchanged. | 43 BUILT with no attestation. Green tests and CI. | Institutional |
| DP2 | Remove dormant/partial components | MISSING | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Nothing is deleted on either ref. | A retirement pass with a deletion ledger. | Institutional / Tier S |
| DP3 | Repair the validation defects | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | 0.014863 is still live. #52 is unmerged. `test_certificate_single_writer` (gauntlet archive) fails. | Merge #52 and migrate the lockbox certificates. | Institutional |
| DP4 | Clear the judging backlog | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | Unchanged. #85 adds more donations (class-book cells), which adds load. The judge_coverage conflict with #55 is resolved. | A post-#77 box reading with judged ≥ created. A clean seal. Green CI. | Institutional |
| DP5 | Measure actual independent breadth | PARTIAL | LIVE: ✓✓✓✓✓✓✗ / #55: ✓✓✓✓✓✓✗ | #85 adds class-book clusters to `alpha_clusters` and `mechanism_census`, which is more breadth sources. `CROSS_SECTIONAL_BREADTH.json` is not committed. `effective_breadth.jsonl` still ends 09-16. | Append the reading. A clean seal. Green CI. | Institutional |
| DP6 | Research-budget allocation sovereign | PARTIAL | LIVE: ✓✓✗✓✗✓✗ / #55: ✓✓✓✓✗✓✗ | Unchanged. `research_budget.json` is from 09-23 with `authoritative:false`. | An applied box reading with `authoritative:true`. | Institutional |
| DP7 | Allocator sovereign | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✗✗✓✗ | T ✗: 4 `test_scalp_promotion` tests fail (go-live, STANDBY→LIVE). #55 `2c8f80c4`: the allocator applies a Tier S factor below 0.5. #53 is unmerged. | Merge #53. Green promotion tests. A box pass. | Institutional |
| DP8 | Cost truth mandatory | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✗✗✗✗✗✗✗ | Unchanged. | Merge #52 and #53, migrate `sleeves.json`. | Institutional |
| DP9 | CI permanently green | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✗ (MISSING) | LIVE: the 02057ffa run was cancelled and the 69da0158 run is queued. 6 test files fail locally (quantbench, scalp_promotion, event_surprise, macro_regime, certificate_single_writer, universe_producers_merge). QB-002 contradicts the manifest. #55 merged: 2 manifest breaches plus QB-002. | Re-pin QB-002 (and normalise line endings). Fix the 5 failing files. One completed green run. Re-sign promoter and rails. | Institutional |
| DP10 | Recursive research competition | PARTIAL | LIVE: ✓✓✗✗✗✓✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | Unchanged. A cloud `QD.json` and `GENOMES.json` exist. | Winners gain only compute. 0 independent discoveries. | Tier S |
| DP11 | Accumulate untouched forward/live evidence | PARTIAL | LIVE: ✓✓✓✗✗✓✗ / #55: ✓✓✓✗✗✓✗ | LIVE `7117aa51`: clock recovery now runs enrolment on any census gap. T ✗: `test_scalp_promotion::test_the_forward_clock_is_the_scalp_lanes_certificate` fails. The local run logs ENROL-GAP for 6 certified keys with `shadow_spec.params` = None. There is no post-#84 box census. | A box census with `n_silent` 0 and ledgers advancing. Green scalp tests. Then time. | Institutional |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✗R✓(cloud)✓✗ | #55 S02: bitemporal PIT reads now feed the macro sweep (a real research path). On LIVE the data tests `event_surprise`, `macro_regime` and `universe_producers_merge` fail, so T ✗ on the merged tree. | The audit must gate certificate data. Green data tests. | TS |
| AC13 | Research methods compete experimentally | MISSING (branch-only) | LIVE: ✗✗✗✗✗✗✗ / #55: ✓✓✗✓R✓(cloud)✓✗ | #55 S33: genomes now compete on the real gauntlet's verdicts. Adoption does not take over judging. | Winning methods must take over real judging. | TS |

Counts on LIVE: DONE 0 / PARTIAL 15 / MISSING (branch-only) 12 / MISSING 1 / EXCLUDED 0 / TIME-BOUND 0 (28 rows). **No verdict changed.** Marks moved downward: T went ✗ on H2, H5, DP1, DP7, DP9 and DP11 (failing tests on LIVE). C stays ✗ everywhere, now for a stated reason (QB-002 vs manifest).
Counts if #55 merged: DONE 0 / PARTIAL 24 / MISSING (branch-only) 2 (DP3, DP8) / MISSING 2 (DP2, DP9) / EXCLUDED 0 / TIME-BOUND 0. No verdict changed. R is ✓ only as a cloud artifact on many H rows, not box evidence. The merge now conflicts only in the derived RUNTIME_STATE files.

### Top gaps
1. **Two seals disagree on LIVE.** Re-pin QB-002 in `data/quantbench/corpus.jsonl` to the signed manifest, or have the probe read `IMMUTABLE_MANIFEST.json`. Hash with normalised line endings: the allocator_proof and state_admission "drift" is CRLF vs LF only.
2. **5 more failing test files on LIVE** (scalp_promotion ×4, event_surprise, macro_regime, certificate_single_writer, universe_producers_merge ×2). PR #67 has skip-ports for two of them.
3. **No completed green CI on LIVE.** 02057ffa was cancelled and 69da0158 is queued.
4. **Re-sign promoter.py and rails.py** before #55 merges, otherwise the manifest goes 0 → 2 breaches.
5. **Box evidence is still absent.** #55 committed a cloud run that is not box evidence. Nothing on any ref comes from vmi3571445 for Tier S, forward census, judging or budget.
6. #52 and #53 are unmerged (DP3, DP7, DP8). The promoter's Tier S import path still fails open.
