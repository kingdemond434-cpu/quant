# Blueprint verification matrix

Independent check of every blueprint the principal gave on 2026-09-29, verified against the code rather than the builders' ledgers.
**Re-scored in full 2026-09-30 ~13:30Z under the principal's strict definition of DONE**, against the live branch `claude/llm-auto-upgrade-verify-gcjac3` at `d30be2ce` (the sealed merge of #52, #53 and #55). The code findings were re-checked at the live tip `aadf1e49`, whose only changes are the gauntlet preflight (re-signed in fc6c34e5), the QB-002 re-pin, test fixes (#96, #97) and a CRO doc (#105). Tier S is on LIVE, so every row now carries one mark set.
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

**C on LIVE.** The two seals now agree at the tip `aadf1e49`: `check_immutable_evaluator.py` reports OK (18 frozen, 0 breaches) and `test_quantbench` passes. The seal was briefly broken at `515d665e` (Codex 4678fe4f edited `external_gauntlet.py`) until fc6c34e5 re-signed it about two minutes later. C still fails on every row for two reasons. First, the law gate CI runs (`run_law_gate.py --laws-only`) fails at the tip on `check_birth_obligations`: `judging_burndown.py`, `check_formal_claim.py` and `check_tier_s_program.py` arrived without their clock, artifact, consumer and attestation row. Second, no CI run on LIVE has completed green: the run on `d30be2ce` (36718891804) was cancelled, as were the ones after it. `check_runtime_attestation` also fails in the cloud, but that check can only be measured on the box.

## Headline (strict)

| Blueprint | Items | DONE | PARTIAL | MISSING (branch-only) | MISSING | EXCLUDED | TIME-BOUND |
|---|---|---|---|---|---|---|---|
| Audit: critical sequence, named defects, 10/10 acceptance table | 43 | 0 | 37 | 0 | 3 | 1 | 2 |
| Audit: 20 implementation items + pipeline chain | 21 | 0 | 20 | 0 | 0 | 0 | 1 |
| Tier S: 15-layer table + sections 1–15 | 30 | 0 | 30 | 0 | 0 | 0 | 0 |
| Tier S: sections 16–30 + final loop | 16 | 0 | 16 | 0 | 0 | 0 | 0 |
| 16 hardening + depth priorities + admission rule | 28 | 0 | 27 | 0 | 1 | 0 | 0 |
| **Total** | **138** | **0** | **130** | **0** | **4** | **1** | **3** |

(The C section's table also lists AC3 and AC13. They are counted once, in A1.)

**Bottom line: 0 of 138 rows meet the strict definition, and nothing is branch-only any more.** #52, #53 and #55 are on LIVE, so the 22 branch-only rows are now PARTIAL. D13 has six marks and fails only C.

What stops rows reaching DONE, in order of how many rows each blocks:

1. **No box evidence (R, almost every row).** The box has not yet committed anything produced by the merged code. No `data/tier_s/box_evidence.json` from vmi3571445 exists. The committed `sleeves.json` and `RELEASE.json` date from 09-28. `UNIVERSAL_SURVIVORS.json` still holds the 58 v2-policy certificates, none re-certified under the v4 lockbox. The only Tier S outputs come from a cloud run that marks itself `counts_toward_done: false`.
2. **No green CI on LIVE (C, every row).** The law gate's birth-obligation breach is fixed on LIVE (584498cfc, 14be56cb1), so `--laws-only` passes. It still goes red about 2h after every cloud attestation, because `check_runtime_attestation` judges staleness on host `vm`; the structural fix is routed to Institutional. CI on LIVE is red on the same set every PR shows. `mt5-money-path` fails the promoter, recertification, marginal-admission and certificate tests: 29 of these fail on `REPLICATION.json absent`, and #113's fixture fixes them. It also fails the country-pack registry tests and `test_gauntlet_annotations`. `quality` fails 15 tests, among them the Tier-1 checker's 21 LIEs (fixed by #135 or #117), the dashboard pages and `test_live_infrastructure_is_not_published`.
3. **Hand-set bars presented as measured.** The DSR variance is 0.0002 in `gate_spec.yaml:70`, set by hand on the same benchmark that reports the success. `effective_trials.py:309` still falls back to 0.014863, and `gate_spec.yaml` is not in the sealed manifest. The "15/130 real, 0/318 traps" result appears only in a commit message: the `dsr/LOCKBOX_BAR.md` the code cites does not exist. `universal_gate.py:280` still judges the lockbox as Sharpe ≥ 0 while stamping its report v4.
4. **Outputs nothing reads, and gaps that let exposure back in.** `live_door.json` has no reader, so the door never reviews rows that are already LIVE. S01 does not reach the gauntlet. S12 `firewall.may` is called only inside Tier S. An exchange zero lowers the mean, not the weight, and `book_fallback` funds it again (pf_allocator 2123–2140, 4015–4023). `split_fills` is only a hook, and matched fills are 0. Rollback is manual.
5. **Committed state contradicts the rules.** 24 LIVE rows are the banned `discovered` family. 31 are admission UNMEASURED and kept indefinitely. The promoter never reads `principal_override`. `certificate_truth --apply` has never run. `research_budget` is `authoritative:false`. The Tier-1 ledger's P1 and P13 rows still say those refusals are pinned, while #53 dropped the 0.02 gold floor under sovereignty and arms the margin clause by default. `check_tier1_program.py` exits 1.
6. **Still missing everywhere:** CS5, D7 and D9 (UNMEASURED and override sleeves keep their risk) and DP2 (dormant components removed).

**Capital event to watch at the first box pass.** #53's cost-basis demotion is wired into `save_sleeves`. With `universe.json` present, 27 LIVE rows pass on the universe and 1 on clock identity, so 12 demote to STANDBY on the next promoter pass. All 12 are banned `discovered` rows on zero-spread FX majors, so the demotion is intended. A checkout without `universe.json` would show all of them demoting. `sleeves.json` now holds 66 rows: 39 LIVE, 26 STANDBY and 1 NORMAL_DAY. Separately, the Tier S door withholds every new LIVE row as DOOR_ERROR until the box has run both `tier_s` and `replication_civilization` once. Both are now always-run legs.

## Routing

- **Institutional truth discipline fixes:** items CS*, D*, AC*, I*, P1, DP2–DP4, DP6–DP10, and cross-cutting gaps 1–3, 8, 9 and 10.
- **Tier S research institution build:** items L*, T*, LOOP, H*, ADM, and cross-cutting gaps 4–7.
- No item fell outside both threads' scope.


## Re-verification log

### 2026-09-30 16:10Z: builder batches #104 and #113–#148 (LIVE `14be56cb1`)

Twenty-six PRs were re-scored against LIVE by read-only passes: #104 (merged), #113, #117–#120, #123–#125, #127, #129–#140, #142–#145, #147 and #148. **None moves a row to DONE, and the headline is unchanged: 0 DONE, 130 PARTIAL, 4 MISSING, 1 EXCLUDED, 3 TIME-BOUND.** Every open PR still lacks box evidence (R), and none is merged (D). The full per-PR findings went to the owners through the coordinator. Scratch reports are in the verifier thread.

Corrections to this matrix:

- **T is overstated on LIVE** for CS1/D1/AC1/I2, I5/DP7/CS3, I1 and DP11. The 29 promoter tests those rows cite fail on any clean LIVE checkout (`REPLICATION.json absent`) and pass only on #113.
- **L15 lost C at #130 `aac670ba` and got it back at `86716a68`.** The placement-interlock fence still only reports, so A stays ✗. After 24h a fully dead gateway reads UNMEASURED, which exits 0.
- **I10 lost C at #133 `8c1ca077`** (law gate red) and got it back at `5b3def4a`.
- **DP4 would lose A if #143 merged as it stands.** Its stage-1 screen is miscalibrated: a planted t≈3 edge is rejected and only t≈10 passes. A stage-1 reject is demoted to tier 4, which is never judged, so the screen acts as a kill.

Defects found in this pass, beyond what the builders claimed:

- **Sealed judge, desktop pass 2:** the 3x cost-stress arm prices from a 0 median spread on 14 FX majors (`external_gauntlet.py:347/686/2417`). On EURUSD the stress arm reads better than the base arm.
- **Money path:** #132's filled-leg check matches only side and price within 0.05, so a stale fill on another instrument can cancel a live bracket. #145 marks 601 variants DEAD that still fire, among them two ten-gate-certified sleeves.
- **Box state:** the state push has been refused since 09-11 by the pre-push law gate (`ops/githooks/pre-push:22-26`). #99 and #141 detect the stall but do not cure it, and the durable cure (a state-only lane) is the principal's call.
- **Placeholder claims:** `live_door.json` still has no reader, and seven LIVE rows are code-hash MISMATCH. #137's 14,794 producers come from about 51 code paths. #131's placebo gate covers one of its four admission paths.

### 2026-09-30 13:30Z: full re-score after the sealed merge (LIVE `d30be2ce`, checked again at tip `aadf1e49`)

#52, #53 and #55 were merged with one reviewed re-sign. All 138 rows were re-scored on LIVE by five independent read-only passes, with about 1,400 tests run under the CI's pinned pandas 2.3.3. Result: **0 DONE, 130 PARTIAL, 0 branch-only, 4 MISSING, 1 EXCLUDED, 3 TIME-BOUND.**

The coordinator's claims, checked against the code:

- **Verified:** the three-read lockbox wired into gate 9; per-day trade summing; the Tier S door failing closed, including the promoter wrapper on import error; the gateway no-quote and crash fixes; the QB-002 re-pin with line endings normalised; promoter.py and rails.py signed; the `tier_s` and `replication_civilization` legs running every hour; FREEZE reaching the allocator as a heat-neutral tilt; the pandas-3 fix in `synthetic_regimes`; tests for `theory.compose` and the honesty channel.
- **Not as stated:** the DSR variance is 0.0002 set by hand, not measured. "15/130 real, 0/318 traps" has no committed artifact.
- **Found broken:** the law gate (birth obligations for three #55/#77 files); `test_gauntlet_annotations` (pins the pre-#52 lockbox); `test_event_surprise` and `test_certificate_single_writer` at `d30be2ce` (#97 fixed event_surprise and the argv failure at the tip).
- **Seal window:** 4678fe4f (Codex) broke the seal at `515d665e` for about two minutes, until fc6c34e5 re-signed it. The box adopts without checking CI or the seal.

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

Re-scored 2026-09-30 ~13:20Z against `d30be2ce8`, the sealed-pass merge that brought #52 (true lockbox), #53 (allocator sovereignty) and #55 (Tier S) into LIVE with one manifest re-sign (`1ed475a93`). Baseline: v1 at `6c8a71a4`.

**LIVE has already moved past d30be2ce.** `origin/claude/llm-auto-upgrade-verify-gcjac3` is now at `515d665e3` (Codex, 14:04 +0100). It carries `4678fe4fc` "preflight unsupported gauntlet parameters", which edits the sealed `external_gauntlet.py` one minute after the re-sign. The rows below are scored at d30be2ce, and the facts about the tip are noted where they change a verdict.

Marks, in order: I (implemented), W (wired on a box schedule), A (authoritative), T (tests exist and pass), R (artifact from a scheduled run, committed), D (deployed on LIVE), C (internally consistent).

## Facts checked (verify, don't trust)

**Seal at d30be2ce: clean.**
- `scripts/check_immutable_evaluator.py` returns **OK, 0/18**, rc 0.
- `desks/mt5/tests/test_quantbench.py` passes (2/2). The QB-002 re-pin now hashes line-ending-normalised files, as `1ed475a93` claims.

**Seal at the LIVE tip 515d665e: broken again.**
- The manifest and the QB-002 corpus both pin `external_gauntlet.py` = `a8ba567cdb9a4118`.
- The tip's file hashes to `47c59fd29d04f9d1`, with LF and CRLF agreeing.
- So both seals breach at the tip (1/18). CI on the tip (run 36719037244) is **pending**.
- This is the third post-sign Codex edit to the judge in two days (7379cbf, e7eace7, now 4678fe4f).

**`gate_spec.yaml` is not sealed.**
- The new DSR variance (0.0002) and the v4 lockbox parameters (`tail_fraction`, `max_half_degradation_z`) live in `desks/mt5/policy/gate_spec.yaml`.
- That file is not in the 18-file manifest, so the bar that most changes certification can move without a re-sign.

**CI for d30be2ce: cancelled.**
- Run 36718891804 was cancelled. The run on 2ac3454f (36718731168) was also cancelled, and 00defad5 is queued.
- There is still **no completed green CI run on LIVE**: UNMEASURED.

**Law gate `--laws-only` (the CI and pre-push mode) FAILS at d30be2ce HEAD.**
- The failing fence is `check_birth_obligations.py` (rc 2).
- Three executables arrived without their obligation (a clock, an artifact, a named consumer and an attested row): `desks/mt5/research/judging_burndown.py`, `scripts/check_formal_claim.py` and `scripts/check_tier_s_program.py`.
- CI's law-gate step (`ci.yml:54,70`) will therefore go red, whatever the seal says.

**`scripts/check_tier1_program.py` exits 1.**
- It reports LIE M26 and PACK1, which cite nonexistent files.
- Its P1 and P13 rows still describe the refusals, which the merged code now contradicts:
  - P1 says "size can only rise".
  - P13 says the test "pins the REFUSAL".
- `CLAUDE.md` also still says the 0.02 gold floor and P1/P13 stay as they are.

**Tests.** 266 tests over 25 desk files, plus 5 root files, all pass under pandas 2.3.3.
- Desk files: lockbox bar and daily series, allocator sovereignty, canonical reserved lockbox, lockbox independence, heal identity cost and swap, live rows need a cost basis, residual cost-basis fence, margin reaches the envelope, Tier S door, Tier S gateway drill (now green; it failed in the prior session), quantbench, effective trials, the fixed trial charge, certificate truth, family policy, shadow log lazy, cost surfaces, experimental budget, forward evidence, alpha breadth, markout, ops redundancy, judging rate and speed, cycle pricing.
- Root files: moat backup, research budget, independence graph, trade identity, and the immutable-evaluator wall.
- A pandas 3.0.6 spot run of 4 key files also passed. No pandas-3-only failure was seen.
- The run dirtied `desks/mt5/data/events.jsonl` and added 4 untracked data files in the worktree. Nothing was committed.

**Committed state has not moved since 09-28 (`0ba716ab`, Codex).**
- `sleeves.json` has 40 LIVE rows:
  - 24 are `discovered`.
  - 31 have admission UNMEASURED.
  - 40/40 have `artifact.ok` false.
  - 7 have `principal_override`.
- `UNIVERSAL_SURVIVORS.json` has 58 rows, swept 2026-09-16 under policy `...-v2`, with the old `0.014863` basis. Nothing has been re-certified under the v3 or v4 lockbox.
- These artifacts are still not committed: `CERTIFICATE_TRUTH`, `PRODUCTIVITY_CENSUS`, `JUDGING_RATE`, `JUDGING_BURNDOWN`, `COST_SURFACES`, `DRIFT`, `EXPERIMENT_LEDGER`, `FORMAL`, and `data/tier_s/*`.
- Stale artifacts:
  - `markout.json`: `usable:false`, 0 matched.
  - `research_budget.json`: `authoritative:false`.
  - `effective_breadth.jsonl`: last row 09-16, 2.057/160.
  - `merge_report.json`: 09-23, 57,538 total.

**What the cost-basis demotion would do next pass.**
- `promoter.cost_basis_of` was run read-only on committed `sleeves.json` and the committed universe.
- 28/40 LIVE rows have a cost basis. **12/40 would be demoted LIVE→STANDBY**, mostly "registry cost fields incomplete" (AUDUSD ×4, EURGBP, EURUSD, USDCAD ×2 each).
- No committed box pass shows this yet.

**Master divergence.** LIVE is 244 commits ahead of `origin/master` (`cbc4ebde4`).

## Critical sequence

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE @d30be2ce) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| CS1 | True reserved lockbox; re-certify every survivor | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | Gate 9 is `gate_policy.lockbox_stage(lock_daily, …, dev=arr, sr0=dsr.sr0_threshold)` (`external_gauntlet.py:~2618`). It is v4: the held-out Sharpe, the last-30% Sharpe and the half-split z all clear sr0. `test_canonical_reserved_lockbox`, `test_lockbox_independence` and `test_lockbox_bar_and_daily_series` pass | No survivor has been re-certified. `UNIVERSAL_SURVIVORS.json` is still v2 with 58 rows from 09-16. The "15/130 real, 0/318 traps" result has no committed artifact: `dsr/LOCKBOX_BAR.md`, cited in the code, does not exist. The law gate fails at HEAD, and the tip seal is broken | INST |
| CS2 | Unmeasured costs fail closed (swap, instrument execution) | PARTIAL | ✓✓✓✓✗✓✗ | The `swap_cost` stage now passes only when a registry basis or the live cost is measured (`external_gauntlet.py:2663`, "UNMEASURED cost fails closed"). The promoter demotes LIVE rows with no cost basis (`promoter.py:344-356`) | `COST_SURFACES.json` still has no consumer and no committed artifact. Costs are not measured from fills (0 matched). There is no box pass showing the fail-closed path | INST |
| CS3 | Allocator sovereignty: zero→no order; below-min→skip | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | `decision_core.py:564-666,743-760`: `allocator_sovereign()` is on by default, and `implementable_lot` refuses to size below `volume_min`. The gold floor is bypassed when sovereign. The gateway's `if not (lot > 0)` skips at `gateway.py:3226,3650,4372`. `test_allocator_sovereignty` passes | No box evidence of a zero or below-minimum allocation sending no order. The `ALLOCATOR_SOVEREIGN.json` file-switch revert is kept. It contradicts the committed Tier-1 P1 row and `CLAUDE.md` (0.02 gold floor, "NEVER REDUCE AGGRESSIVENESS"), which carry no recorded principal order dated 09-29 | INST |
| CS4 | Certificate-truth migration; banned discovered physically absent | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. The law gate reports "migrate once on the box: certificate_truth.py --once --apply" | Run `--apply` and commit `CERTIFICATE_TRUTH.json`. 24 `discovered` rows are still LIVE | INST |
| CS5 | No LIVE sleeve with UNMEASURED marginal indefinitely | MISSING | ✗✗✗✗✗✗✗ | `promoter.py:1431-1434` still reads "not a refusal… risk already held is not removed". `2efe53b3` (same-mechanism join) may shrink the count, but it adds no time bound | A time bound or quarantine rule, a test, and a committed demotion | INST |
| CS6 | Law gate + MT5 money-path CI green on clean machine | PARTIAL | ✓✓✗✗✗✓✗ | The d30be2ce CI run was cancelled and no green run exists. `run_law_gate.py --laws-only` FAILS at HEAD on `check_birth_obligations` (judging_burndown, check_formal_claim, check_tier_s_program). The tip seal breaks via 4678fe4f | Attest the three executables. A completed green run. CI must block merges to the box branch | INST |
| CS7 | Margin/survival above aggressiveness | PARTIAL | ✓✓✓✓✗✓✗ | The margin clause is now armed by default (`pf_allocator.py:3526`, revert with `MARGIN_CLAUSE_DISABLED`). The test was flipped to "feeds by default" | The gateway heat check is still a tripwire. No artifact shows the clause bind. It contradicts the Tier-1 P13 row ("pins the REFUSAL") and `CLAUDE.md` ("P13 REFUSED") | INST |
| CS8 | Attack the 55k judging backlog, not the generator | PARTIAL | ✓✓✓✓✗✓✗ | A new hourly leg `judging_burndown` (`hourly_cycle.py:974,4519`) sits beside `judging_throughput` | No committed `JUDGING_RATE` or `JUDGING_BURNDOWN`. `merge_report` (09-23) is 57,538. `judging_burndown.py` is one of the law-gate birth-obligation breaches | INST |
| CS9 | Measure effective independent breadth | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. `effective_breadth.jsonl` last row is 09-16, 2.057/160. Tier S topology is now on LIVE (`libs/tiers/`) | Breadth does not reach sizing or admission. The artifact is 2 weeks stale (R now ✗) | TS/INST |
| CS10 | Research-budget allocation authoritative | PARTIAL | ✓✓✗✓✓✓✗ | Unchanged. `research_budget.json` is `authoritative:false` | Authoritative, with evidence | TS |
| CS11 | Independent broker/data/execution domain | EXCLUDED | ––––––– | — | Multi-venue excluded by user | — |
| CS12 | Accumulate untouched forward/live evidence | TIME-BOUND | ✓✓✗✓✓✓✗ | Unchanged | The forward verdict does not gate LIVE (D9) | INST |

## Named defects

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE @d30be2ce) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| D1 | lockbox_sharpe = wf_oos (58/58 certs equal) | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | The code now reads a reserved tail (see CS1) | The committed 58 certificates are still the v2 lockbox==WF rows. Re-certify and commit | INST |
| D2 | Fixed DSR n_trials=597 / var 0.014863 | PARTIAL | ✓✓✓✓✗✓✗ | `gate_spec.yaml:70` sets `fixed_variance_of_sharpes: 0.0002`, still a **constant** ("both inputs remain constants"). The trial charge is now `max(campaign, family lifetime)` (`charged_lifetime_trials`, `external_gauntlet.py:2345,2568`). sr0 at 109 trials drops from 0.312 to **0.036** (~9× lower bar) | The variance is calibrated on the benchmark it is scored on, not measured from the desk's own trials. No survivor has been re-judged. `gate_spec.yaml` is unsealed. `effective_trials.py:309` still falls back to 0.014863 | INST |
| D3 | swap UNMEASURED → passed | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | `external_gauntlet.py:2663-2676` fails closed. `test_heal_identity_cost_and_swap` passes | No box certificate judged under it. No broker-measured swap artifact | INST |
| D4 | sleeves.json 40 LIVE all artifact.ok=false "no cost basis" | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | `promoter.save_sleeves` demotes to STANDBY when there is no cost basis. `cost_basis_of` gives 28/40 a basis, so 12 would demote. `test_live_rows_need_a_cost_basis` and `test_residual_cost_basis_fence` pass | The committed `sleeves.json` (09-28) still shows 40/40 `artifact.ok` false. The 12 rows need registry cost fields, not only demotion. There is no box pass | INST |
| D5 | decision_core min-lot on zero allocation + gold minimum floor | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | See CS3 | See CS3 | INST |
| D6 | Banned 'discovered' still in sleeves/certificates/clocks | PARTIAL | ✓✓✓✓✗✓✗ | Unchanged. 24 LIVE rows are `discovered` | The migration, and a committed store without them | INST |
| D7 | 31 LIVE with UNMEASURED marginal admission | MISSING | ✗✗✗✗✗✗✗ | Unchanged (31/40) | See CS5 | INST |
| D8 | 7 principal overrides | PARTIAL | ✓✓✗✓✗✓✗ | `SEPARATE_EXPERIMENTAL_BOOK = False` (`experimental_budget.py:65`). No `data/experimental_budget.json` | Unchanged | INST |
| D9 | Non-significant forward verdict LIVE under override | MISSING | ✗✗✗✗✗✗✗ | `promoter.py` never reads `principal_override`, and there is no significance rule | Any retire or quarantine rule | INST |
| D10 | Law gate: immutable-evaluator drift | PARTIAL | ✓✓✓✓✗✓✗ | At d30be2ce: 0/18, and QB-002 passes. At tip 515d665e: `external_gauntlet.py` breaches both seals (a8ba567c pinned, 47c59fd2 on disk) | Drift recurs after every sign, and CI does not block it. `gate_spec.yaml` (the DSR/lockbox bar) is outside the manifest | INST |
| D11 | Law gate: productivity-census evidence | PARTIAL | ✓✓✓✓✗✓✗ | Unchanged. The box-mode fence reports "no census artifact" | A committed census | INST |
| D12 | Law gate: certificate-truth | PARTIAL | ✓✓✓✓✗✓✗ | Unchanged. The box mode BREACHes with "migrate once" | `--apply`, then commit | INST |
| D13 | shadow.log test-collection failure | PARTIAL | ✓✓✓✓✓✓✗ | `test_shadow_forward_log_lazy` passes | — | INST |
| D14 | Ruff/MyPy excluding desks/mt5 | PARTIAL | ✓✓✓✗✗✓✗ | `pyproject.toml:120` still excludes `desks/mt5` | Full lint and type checking over desks/mt5 | INST |
| D15 | master vs deployment branch divergence | PARTIAL | ✓✗✗✗✗✓✗ | LIVE is 244 commits ahead of master `cbc4ebde4` | A recurring sync job | INST |
| D16 | Research-budget allocator authoritative:false | PARTIAL | ✓✓✗✓✓✓✗ | See CS10 | See CS10 | TS |

## 10/10 acceptance conditions

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE @d30be2ce) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| AC1 | Every cert has truly independent dev/OOS/lockbox | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | See CS1 | Re-certified, committed certificates | INST |
| AC2 | Every trial ever contributes to selection-bias accounting | PARTIAL | ✓✓✓✓✗✓✗ | Family-lifetime trials are now charged. `online_fdr` is on LIVE and gates the promotion door (`promotion_authority.py:130,247`) | The variance is a constant. There is no committed FDR ledger from the box | INST/TS |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | **PARTIAL** (was MISSING branch-only) | ✓✓✗✓✗✓✗ | `libs/tiers/bitemporal.py` is on LIVE and is read by `run_edges_macro_fusion_sweep.py:55,291`. The `tier_s` hourly leg runs (`hourly_cycle.py:850,2072`) | It does not gate the data certificates use. There is no box artifact (`data/tier_s/*` is uncommitted) | TS |
| AC4 | Spread+commission+swap+slippage+impact+latency from reality | PARTIAL | ✓✓✓✓✗✓✗ | Swap is now fail-closed, and the cost-basis demotion is in place. `markout.json` has 0 matched and `usable:false` | Costs are not measured from fills. There is no impact or latency model | INST |
| AC5 | One sovereign optimizer; 0 exposure = 0 position | **PARTIAL** (was MISSING branch-only) | ✓✓✓✓✗✓✗ | See CS3 | Box evidence. The 7 overrides are still LIVE. The ledger and CLAUDE.md contradict the code | INST |
| AC6 | Ruin/margin/corr/tail constraints not overridable downstream | PARTIAL | ✓✓✗✓✗✓✗ | The margin clause is armed. `constrained_book` still has `FEEDS_LIVE=False` | A binding gateway gate, and the constrained book fed live | INST |
| AC7 | Signal→decision→order→fill→markout measured | PARTIAL | ✓✓✗✓✓✓✗ | `gateway.py:949-953`: `no_quote_at_decision` is now recorded as an execution reason | 0 matched fills | INST/TS |
| AC8 | Many independent mechanisms, not clones | PARTIAL | ✓✓✗✓✗✓✗ | See CS9 | Breadth does not steer capital | TS |
| AC9 | Discovery ≤ validation capacity; negligible backlog | PARTIAL | ✓✓✓✓✗✓✗ | See CS8 | A committed drain reading | INST |
| AC10 | Green deterministic CI/release on clean hardware | PARTIAL | ✓✓✗✗✗✓✗ | See CS6. The law gate fails and CI was cancelled | A green run that blocks merges | INST |
| AC11 | One source of truth for cert, clock, sleeve, allocation | PARTIAL | ✓✓✗✓✗✓✗ | See CS4/D12 | The migration | INST |
| AC12 | Long forward/live history with attribution and drift | TIME-BOUND | ✓✓✓✗✗✓✗ | Unchanged. There is no drift_monitor test | Unchanged | INST |
| AC13 | Research methods compete experimentally | **PARTIAL** (was MISSING branch-only) | ✓✓✗✓✗✓✗ | `red_queen`, `meta_benchmark` and the gauntlet arena are on LIVE through the `tier_s` leg (`tier_s.py:76,883,1020-1088`). The one committed run is from the cloud and says "NOT box evidence" | Adoption must change the real gauntlet or scheduler. Box evidence | TS |
| AC14 | Second machine/data/broker; recovery tested | PARTIAL (broker part EXCLUDED) | ✓✓✗✓✗✓✗ | Unchanged | A restore drill and failover | INST |
| AC15 | Reproduce any trade/cert from hashes alone | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. `test_trade_identity` passes | The identity is not stamped on fills | TS |

Counts: DONE 1 / PARTIAL 36 / MISSING (branch-only) 0 / MISSING 3 / EXCLUDED 1 / TIME-BOUND 2 (43 rows)

Verdict changes vs baseline: CS1, CS3, D1, D3, D4, D5, AC1, AC3, AC5 and AC13 move from MISSING (branch-only) to PARTIAL. Mark changes that keep the same verdict:
- A ✓ for CS2, CS7, AC2 and AC4.
- R ✗ for CS9 and AC8 (stale).
- T ✗ for CS6 and AC10 (law gate fails).
- D10 stays PARTIAL: clean at d30be2ce, broken at the tip.

## Claims

**Verified**
- The DSR variance is now 0.0002 in `gate_spec.yaml`.
- The lockbox has three reads (held, last-30% tail, half-split z), all at the cell's sr0, and it is wired into gate 9.
- Trades are summed per day in `daily_series`, and a test pins it.
- The Tier S door fails closed: `tier_s_block` returns `DOOR_ERROR` on an import or raise, and a test pins it.
- Gateway: no quote means no send and a `no_quote_at_decision` decision row. A raising `order_send` becomes a failed leg, not a crash.
- QB-002 was re-pinned with line-ending normalisation. The seal is 0/18 at d30be2ce and quantbench passes.
- The swap stage fails closed.
- Allocator sovereignty is on by default.
- The cost-basis demotion is in place.
- All related tests pass under pandas 2.3.3.

**Failed or unverifiable**
- **"Measured" DSR variance: FAILED as worded.**
  - 0.0002 is still a hand-set constant, and the spec text itself says "both inputs remain constants".
  - It was chosen on the same sealed suite that is then used to report the success.
  - It lowers sr0 about 9× (0.312 → 0.036 at 109 trials).
- **"15/130 real, 0/318 traps": UNVERIFIABLE.**
  - It appears only in a commit message and a test docstring ("desktop re-run").
  - `dsr/LOCKBOX_BAR.md`, cited in `gate_policy.py`, does not exist, and no suite result is committed.
- **"One reviewed re-sign" held for about 1 minute.** Codex 4678fe4f edited `external_gauntlet.py` and pushed to LIVE (515d665e), and both seals breach there.
- **CI green: UNMEASURED.** The d30be2ce run was cancelled, and `--laws-only` fails locally at HEAD on birth obligations.

## Top gaps

1. **The law gate fails at d30be2ce HEAD.** `check_birth_obligations` flags `judging_burndown.py`, `check_formal_claim.py` and `check_tier_s_program.py` with no attested obligation. CI will go red. There is no completed green run on LIVE.
2. **The seal broke again at the LIVE tip.** 4678fe4f (Codex) edits the sealed gauntlet after the re-sign. `gate_spec.yaml`, which now carries the decisive DSR and lockbox bar, is not sealed at all.
3. **The fixes are code-only.** No box pass has re-certified survivors (58 rows, still v2), demoted the 12 no-cost-basis rows, or shown a sovereign zero-lot skip. Every PARTIAL that was branch-only lacks R.
4. **The DSR bar dropped about 9× on an uncommitted benchmark claim.** The variance is still a constant, and it was tuned on the suite it is scored on.
5. **Governance contradicts the code.** The Tier-1 P1 and P13 rows and `CLAUDE.md` still pin the refusals, while sovereignty removes the 0.02 gold floor and the margin clause is armed by default. `check_tier1_program.py` exits 1.
6. **Unchanged MISSING rows.** CS5 and D7 (31 UNMEASURED-marginal LIVE rows kept indefinitely), and D9 (the promoter never reads `principal_override`, and a non-significant override stays LIVE). 24 banned `discovered` rows are LIVE, and `certificate_truth --apply` has never been run.

## A2 — Audit 20 implementation items (I) and pipeline chain (P1)

Checked against LIVE = `d30be2ce8` (detached worktree `wt_full`; the merge of #52 true lockbox, #53 allocator sovereignty and #55 Tier S, plus the re-sign `1ed475a93`), 2026-09-30. This was a read-only pass: `git`, grep, the seal checker, and pytest run in the worktree. The tracked and untracked files the tests dirtied were restored afterwards.

**The live branch moved during the audit.** `origin/claude/llm-auto-upgrade-verify-gcjac3` went from `d30be2ce8` to `515d665e3` and then to `aadf1e491` (11 commits):
- **`515d665e3` briefly BREACHED the seal.** Codex `4678fe4fc` ("preflight unsupported gauntlet parameters") edited `external_gauntlet.py`, and `check_immutable_evaluator.py` returned `BREACH … a8ba567cdb9a4118 -> 47c59fd29d04f9d1`.
- **`fc6c34e59` re-signed it.** At `aadf1e491` the seal is OK again.
- **The rest of the diff since `d30be2ce8` touches nothing A2 scores.** It is 9 files: preflight, the manifest, the QB-002 re-pin, and tests.
- **The breach window was 13:04 to 13:06 UTC.** That does not overlap the box's :12 adopt slot, so the box probably never adopted the breached tree. That is not evidenced either way.

## Claims verified (concretely, in code, and by running tests)

| Claim | Verdict | Evidence |
|---|---|---|
| DSR variance 0.0002 | **TRUE, but it is a recalibrated constant, not a measurement** | `policy/gate_spec.yaml:70` `fixed_variance_of_sharpes: 0.0002`; `gate_policy.py:35` reads it; `external_gauntlet.py:2476-2479` applies it. The sweep prints "measured this sweep 0.000000" beside it and does not use that value. `effective_trials.py:309` still falls back to `0.014863` when the spec is unreadable. The spec comment at `:68-69` still says "0.014863 is the dispersion that yields sr0 = 0.3786", which is stale. Units are consistent: `sharpe_ratio` and sr0 are both per-period |
| Three-read lockbox | **TRUE in code** | `gate_policy.lockbox_stage` (`:195-218`) passes only if all three hold: held Sharpe ≥ sr0, last-30% Sharpe ≥ sr0, and half-split z ≤ 0.5. It is called with `dev=arr, sr0=dsr.sr0_threshold` at `external_gauntlet.py:2618`. `carve_lockbox` runs before the matrix (`:2418-2420`) |
| 15/130 real, 0/318 traps | **UNVERIFIABLE from the repo** | It appears only in the `fa51bc5a3` commit message and a docstring. The `dsr/LOCKBOX_BAR.md` cited at `gate_policy.py:184` does not exist in the tree, and no suite result is committed |
| Per-day trade summing | **TRUE** | `external_gauntlet.daily_series` (`:349-358`) now builds one row per trade, then groups by day and sums. Pinned by `test_two_trades_on_one_day_are_summed` (pass) |
| Tier S door fails closed | **TRUE for new promotions** | `promoter.tier_s_block` (`:1671-1687`) returns `DOOR_ERROR` on exception. `promotion_authority.block` (`:218-240`) withholds on any raising check and requires four fresh verdict files. Called at `promoter.py:1925` (qquant) and `:2070` (main). **Gap 1:** `authority.suspended(organ)` exempts the fdr, immune and truth_kernel checks. **Gap 2:** `data/tier_s/live_door.json`, the door's verdict on rows already LIVE, is written at `tier_s.py:4122` but has **no reader** anywhere, although its own docstring says the promoter's retirement reads it |
| Gateway no-quote and crash fixes | **Present, tested** | `gateway.place_bracket` in `fa51bc5a3`. The tests pass |
| QB-002 re-pinned | **TRUE, and re-pinned again** | In `1ed475a93`. It had to be re-pinned again in `fc6c34e59` after `4678fe4fc`. `test_quantbench.py` passes |
| Lockbox #52 and sovereignty #53 on live | **TRUE** | `carve_lockbox`/`lockbox_stage`, `allocator_sovereign()` (`decision_core.py:577`), `implementable_lot`, and the `sizing.py:112` and `gateway.py:259` callers. `test_canonical_reserved_lockbox.py`, `test_allocator_sovereignty.py` and `test_tier_s_door.py` pass |

**Tests run.** 36 files, about 470 tests: `test_lockbox_bar_and_daily_series`, `effective_trials`, `canonical_reserved_lockbox`, `lockbox_independence`, `allocator_sovereignty`, `tier_s_door`/`gateway_drill`/`enforcement`/`organs`, plus every I-item test named in the baseline. The log is `rescore/A2_v5_tests.log`.
- **Under pandas 2.3.3 (the CI pin): 1 failure.** `test_gauntlet_annotations.py::test_run_gauntlet_result_carries_independence_and_the_trial_ledger` asserts `lockbox_restates_walk_forward == {n:1, of:1}` and gets `{n:0}`. The test is stale: it pins the pre-#52 restatement, which #52 removed. It fails under both pandas versions, lives in `desks/mt5/tests` (the CI money-path suite), and is unchanged at `aadf1e491`. **The money-path suite is therefore red at the live head.**
- **Under pandas 3.0.6: 2 more failures, both pandas-3-only.** They are `test_replication_civilization.py::test_load_bars_reads_a_parquet_*` (two tests), and they pass on 2.3.3.

**CI.** Run 36718891804 on `d30be2ce8` was **cancelled**, superseded by later pushes, so no CI verdict exists for the audited commit. The latest run, 36719423822 on `aadf1e491`, was still pending when read.

## Facts that hold across the section (measured at `d30be2ce8`)

- **Committed state is unchanged since 2026-09-28** (`0ba716ab9`, Codex).
  - `sleeves.json` has 66 rows: 40 LIVE and 26 STANDBY.
  - Of the 40 LIVE rows, 24 are banned `discovered` rows.
  - 31 LIVE rows have `admission = UNMEASURED`.
  - All 40 LIVE rows have `artifact.ok = false`.
  - All 40 LIVE rows have `delta_elogw_per_day = null`.
  - `desks/mt5/data/RELEASE.json` was last committed 09-28, so **box adoption of `d30be2ce8` is not evidenced**.
- **No committed certificate is valid under the live policy.** `reports/UNIVERSAL_SURVIVORS.json` (n=58, committed 09-28) carries policy `…-v2-calibrated-inputs`, and `gate_policy.is_exact_policy` returns **False** on it (version, trial_count_basis, lockbox_basis and lifetime_trial_floor all differ). "Re-certify every survivor" is not evidenced by any committed file.
- **The second validator still runs the v3 lockbox under a v4 stamp.** `research/universal_gate.py:280` still passes gate 9 on `lock_sr >= 0.0`, yet stamps `GATE_POLICY = ATTESTATION` (v4 basis) into `UNIVERSAL_GATE_CANDIDATES.json` (`:509-512`). That file is report-only, with no authority, so this is a mis-attestation, not a bypass.
- **Stale policy text.** `ATTESTATION["lockbox_oos_sharpe_min"] = 0.0` (`gate_policy.py:111`) and the gate_spec lockbox `description` ("Sharpe >= 0 on the reserved final 20%") are both stale against the v4 bar.
- **Organ artifacts.** `**/reports/*` is gitignored (`.gitignore:153`), and none of the organ artifacts are committed: REPLICATION, IDENTITY_CHAIN, EXPERIMENT_LEDGER, CERTIFICATE_TRUTH, COST_SURFACES, JUDGING_RATE, FACTORY_CONTRACTS, PLACEBO, LIVE_CALIBRATION, CONSTRAINED_BOOK, EXPERIMENTAL_BUDGET, OPS_REDUNDANCY, FORWARD_EVIDENCE and tier_s/*. So R = ✗ throughout.
- **Governance contradiction (C).** `decision_core.py:564-575` cites a principal order of 2026-09-29 that supersedes the gold floor. CLAUDE.md, a standing law, still says "the 0.02-lot gold floor … stay as they are". One of the two is wrong, and nothing in the repo reconciles them.

Marks: I Implemented, W Wired, A Authoritative, T Tested (exist and pass), R Artifact, D Deployed (on the live branch; box adoption unevidenced), C Consistent.

| ID | Item | Verdict | I W A T R D C | Evidence (LIVE file:line, caller, test, artifact) | What is missing for strict DONE | Owner |
|---|---|---|---|---|---|---|
| I1 | One immutable research identity, raw data to live P&L | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. `identity_chain.py` and `trade_identity.py` run hourly, and their tests pass. `frontier_identity.cell_id` still has no data, PIT, code, cost or seed hash | Stamp the id on orders and fills. Add the five hashes. Make promotion and attribution join on the id rather than the sleeve name. Commit the chain artifact | Unowned |
| I2 | True lockbox, sole certification path, separate process/store | PARTIAL | ✓✓✓✗✗✓✗ | **Changed since baseline (was ✗✗✗✓✗✗✗).** The reserved tail is carved before the matrix (`external_gauntlet.py:2418-2420`), and gate 9 is the v4 three-read at sr0 (`:2618`, `gate_policy.py:195`). Tests: `test_lockbox_bar_and_daily_series`, `test_canonical_reserved_lockbox`, `test_lockbox_independence` pass. `test_gauntlet_annotations` fails because it pins the old restatement. It runs **in the same process and store** as the other nine gates. The committed canon (n=58, v2) fails `is_exact_policy`, and there is no committed re-certification. `universal_gate.py:280` stays at v3 but carries the v4 stamp. The 15/130 vs 0/318 figure has no committed evidence | Separate lockbox process and store (one-shot, access-logged). Commit a re-certified canon under v4. Fix the stale test (the money-path suite is red). Align universal_gate, `ATTESTATION.lockbox_oos_sharpe_min` and the spec description. Commit `LOCKBOX_BAR.md` or the suite result | Truth-fixes |
| I3 | Lifetime global trial ledger feeding DSR/PBO/SPA | PARTIAL | ✓✓✓✗✗✓✗ | **A changed from ✗ to ✓.** `charged_lifetime_trials` (`external_gauntlet.py:2345-2363`, used at `:2568`) charges DSR the max of the campaign charge and the family's lifetime trials. PBO and SPA are not charged. The variance is the constant 0.0002, recalibrated by hand rather than measured per sweep (the sweep prints "measured 0.000000" beside it). The `test_gauntlet_annotations` failure also asserts the ledger "never sets the bar", which contradicts the code | Charge PBO and SPA from the ledger as well. Make the variance a measured quantity with a published derivation. Fix the stale test. Commit EXPERIMENT_LEDGER | Truth-fixes |
| I4 | Sovereign certificate store; check_certificate_truth permanently green | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. The committed `sleeves.json` still has 40 LIVE rows (24 banned, 31 UNMEASURED), and the committed canon is v2, which is not exact policy under v4 | A scheduled `--apply` and `--require-state` in the gate. Migrate the stores to 0 banned and 0 unbacked rows. Commit CERTIFICATE_TRUTH | Truth-fixes |
| I5 | Allocator sovereignty: zero stays zero, below-min is zero; principal sleeve separate | PARTIAL | ✓✓✓✓✗✓✗ | **Changed since baseline (was ✗ on all 7).** `allocator_sovereign()` (`decision_core.py:577`) and `implementable_lot` (`:589`) snap down and refuse below the venue minimum. Wired at `:614`, `:654`, `:743`, `:755`, `sizing.py:112` and `gateway.py:259`. `test_allocator_sovereignty.py` passes. It is still file-switch reversible (`data/ALLOCATOR_SOVEREIGN.json {"enabled": false}`; the file is absent, so the default is sovereign). There is no separate budgeted principal sleeve. CLAUDE.md still orders the 0.02 gold floor kept | Remove the reversal switch or put it behind a principal-signed gate. Build the separate principal sleeve. Reconcile CLAUDE.md with the 2026-09-29 order. Evidence box adoption | Truth-fixes |
| I6 | Risk as hard constraints inside E[log W] | PARTIAL | ✓✓✗✓✗✓✓ | Unchanged. `constrained_book` still has `FEEDS_LIVE = False`. P1 and P13 are REFUSED | The principal's decision. The constrained solve must feed pf_allocator. Commit the artifact | Unowned |
| I7 | Cost truth before capital; multi-dimension cost surfaces | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. The gauntlet's `swap_cost` fails closed on an UNMEASURED cost (seen in the test run). The 6-D `cost_surfaces` has no consumer. 40/40 LIVE rows have `artifact.ok = false` | Admission and sizing read the 6-D surfaces. matched_fills > 0. The live book must fail closed on no cost basis | Truth-fixes |
| I8 | Judging throughput ≥ creation; cheap gates first | PARTIAL | ✓✓✓✓✗✓✗ | The `judging_*` tests pass, including the new `test_judging_burndown`. `merge_report.json` still shows `unjudged_total: 55811`. No committed JUDGING_RATE. R is corrected from the baseline's ✓: `merge_report` is backlog evidence, not a rate artifact | A box JUDGING_RATE reading showing judging ≥ creation. Drain the backlog | Truth-fixes |
| I9 | Effective breadth via independence graph; north star = independent alpha rank | PARTIAL | ✓✓✗✓✗✓✓ | Unchanged in substance. The Tier S `allocator_tilts` reach pf_allocator (`pf_allocator.py:2094-2099`), but they carry the exchange, capture and freeze factors, not the alpha rank | Rank must steer promotion and allocation. Commit the artifact | Tier S |
| I10 | Closed-loop world discovery map + per-source info value | PARTIAL | ✓✓✗✓✗✓✓ | Unchanged. `research_budget.json` is `authoritative: false` | A six-axis map. Measured per-source value that moves budget | Unowned |
| I11 | Factories measured on 7 metrics; compute reallocated | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. `cycle_pricing` weights factory contracts at 0.15, and the budget is non-authoritative | The full contract. An evidenced reallocation. Commit FACTORY_CONTRACTS | Truth-fixes / Tier S |
| I12 | Research self-improvement as experiment | PARTIAL | ✓✓✗✓✗✓✓ | `researcher_market` and `meta_benchmark` are now on live, run inside the hourly `tier_s` organ (`hourly_cycle.py:850,2072`). Tested via `test_tier_s_organs`/`measurement`. They hold no budget authority | A scored tournament with a randomized budget holdout, linked to realized P&L, with adoption authority | Tier S |
| I13 | Small pure components, typed contracts, property tests | PARTIAL | ✓–✗✗✗✓✗ | The monoliths remain (`external_gauntlet` grew by 151 lines; `tier_s.py` is new at 4,461 lines). T is ✗ because the money-path suite has one stale failure | Split the monoliths. Typed interfaces. A green suite | Unowned |
| I14 | Production-grade CI; signed artifacts; prod accepts only green | PARTIAL | ✓✓✗✓✗✓✗ | The CI run on `d30be2ce8` was cancelled, so it has no verdict. The seal is OK at `d30be2ce8`, BREACHED at `515d665e3`, and OK again at `aadf1e491` after `fc6c34e59`: a Codex edit reached the live branch unsigned. The money-path suite carries a stale failure. The box adopts without a green-CI check | CI green on the head. The box refuses any release without a green CI hash and a clean seal | Truth-fixes |
| I15 | Independent implementation verifier | PARTIAL | ✓✓✓✓✗✓✗ | **A changed from ✗ to ✓.** `promotion_authority._replication` (`:113-126`) blocks a NEW promotion on MISMATCH, and the promoter calls it at `:1925,2070`. `replication_civilization` writes `verdicts` rows with a `key`, a format the door reads. **Rows already LIVE are not covered:** `live_door.json` has no reader. `test_replication_civilization` passes on pandas 2.3.3 and fails 2 parquet tests on pandas 3 | A reader for `live_door.json` (retirement on MISMATCH). Trade- and timestamp-level comparison. Commit REPLICATION.json | Tier S |
| I16 | Continuous placebo/adversarial tests with audit-recall | PARTIAL | ✓✓✓✓✗✓✗ | **A changed from ✗ to ✓ (partly).** `promotion_authority._freeze` honours the immune FREEZE on promotion, and `allocator_tilts` applies a freeze factor. The door exempts a suspended immune organ. The power-greater-than-zero claim (15/130) is uncommitted. PLACEBO_AUDIT still has no direct consumer | Commit the recall/power evidence. Remove the suspension escape or put it behind a gate. Commit the artifact | Tier S |
| I17 | Live attribution as final judge; overstating priors downweighted | PARTIAL | ✓✓✓✓✗✓✓ | Now also reaches pf_allocator through `allocator_tilts.capture_factor` (live mean R vs forward expectancy, heat-neutral). This is inert while matched_fills = 0, when the factor reads UNMEASURED and equals 1.0 | matched fills > 0. Commit the artifact | Tier S |
| I18 | Human experimentation in a separate budgeted sleeve | PARTIAL | ✓✓✗✓✗✓✗ | Unchanged. Overrides are still in-book (`principal_override` on the LIVE rows). `discretionary_sleeve.py` has no caller | Split the budget and ledger in the money path | Unowned |
| I19 | Operational redundancy (second broker EXCLUDED) | PARTIAL | ✓✓✗–✗✓✗ | The Tier S `gateway_drill`/`chaos` organs now run hourly and `test_tier_s_gateway_drill.py` passes. `dr_drill.py` and `run_restore_drill.py` still have no tests. There is no standby, no failover and no encrypted backup | A standby with failover. Drills on real box state. Encrypted backups. A committed drill artifact. The broker part is EXCLUDED | Tier S (chaos) / Unowned |
| I20 | Let time complete: forward/live evidence | TIME-BOUND | ✓✓✗✓✗✓✗ | Unchanged. 31 UNMEASURED LIVE rows. The committed canon is not exact policy under v4, so clock backing depends on an uncommitted re-certification | Time, plus a committed tracker artifact and certificate-backed clocks | n/a |
| P1 | Pipeline with no bypass arrow | PARTIAL | ✓✓✗✗✗✓✗ | See the arrows below. The lockbox, allocator and multiplicity arrows are now closed in code. The forward-clock and live-door arrows are still bypassed | Migrate the certificates. A reader for live_door. Cost fail-closed on the live book. A green suite | Both |

### P1 arrows (not counted)

| Arrow | Strict status on LIVE | Key evidence / gap |
|---|---|---|
| World data → PIT lake | PARTIAL | Unchanged |
| PIT lake → representation factory | PARTIAL | Unchanged |
| → Hypothesis swarms | PARTIAL | Unchanged |
| → Lifetime multiplicity ledger | **Authoritative (DSR only)**, was BYPASSED | `charged_lifetime_trials` at `external_gauntlet.py:2568`. PBO and SPA are not charged |
| → Cheap falsification | Authoritative | Unchanged |
| → CPCV/PBO/SPA/DSR | **Authoritative; power claimed, not committed** | Variance is 0.0002, a hand-set constant. The "15/130 real" suite result is not in the repo |
| → Sealed true lockbox | **Authoritative in code**, was BYPASSED | Carved before the matrix, three reads at sr0. Same process. No committed v4 canon |
| → Forward clock | BYPASSED | 24 banned and 31 UNMEASURED LIVE rows. The canon is v2 and not exact policy |
| → Live cost calibration | Advisory | matched_fills = 0. 40/40 `artifact.ok = false` |
| → Sovereign E[log W] allocator | **Authoritative in code**, was BYPASSED | `implementable_lot` refuses below-minimum targets. File-switch reversible. Box adoption unevidenced |
| → Promotion door (Tier S) | PARTIAL | New promotions: fail closed. LIVE rows: `live_door.json` has no reader |
| → Execution → fills | PARTIAL | No-quote means no send (`place_bracket`). The fill surface falls back to a spread prior |
| → Attribution | PARTIAL | Joins by sleeve name |
| → Posterior update | PARTIAL | `capture_factor` reaches the allocator, but is inert at 0 fills |
| → Research credit → search | PARTIAL | `research_budget` is `authoritative: false` |

Counts: DONE 0 / PARTIAL 20 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 1 (21 rows; the I19 second-broker sub-part is EXCLUDED).

**Verdicts changed versus baseline: none. Marks changed:**
- **I2:** from ✗✗✗✓✗✗✗ to ✓✓✓✗✗✓✗.
- **I5:** from ✗ on all 7 to ✓✓✓✓✗✓✗.
- **I3, I15 and I16:** A moved from ✗ to ✓.
- **I8:** R moved from ✓ to ✗ (correction).
- **I13:** T moved from ✓ to ✗ (stale money-path failure).
- **I19:** T moved from ✗ to partial.
- **P1:** three arrows moved from BYPASSED to authoritative in code.

### Top gaps

1. **The money-path suite is red on live.** `test_gauntlet_annotations::test_run_gauntlet_result_carries_independence_and_the_trial_ledger` still pins the pre-#52 lockbox restatement and "never sets the bar". It fails on pandas 2.3.3 and 3, and is unfixed at `aadf1e491`.
2. **Re-certification under v4 is not evidenced.** The committed canon (n=58) is v2 and fails `is_exact_policy`. The 40 LIVE rows, 24 of them banned, are unchanged since 09-28. The "15/130 real, 0/318 traps" result has no committed artifact: `dsr/LOCKBOX_BAR.md` is cited but absent.
3. **The DSR variance 0.0002 is a hand-recalibrated constant, not a measurement.** The per-sweep measured value is printed and ignored, and the spec comment still justifies 0.014863.
4. **The Tier S door does not cover the LIVE book.** `live_door.json` is written with no reader. `authority.suspended()` can exempt the fdr, immune and truth_kernel checks.
5. **The seal is not a release precondition.** Codex `4678fe4fc` pushed an unsigned `external_gauntlet.py` edit to live (breach at `515d665e3`, re-signed 2 minutes later in `fc6c34e59`). The box adopts without a CI or seal gate, and CI on `d30be2ce8` was cancelled, so no verdict exists.
6. **Stale v3 surfaces remain.** `universal_gate.py:280` uses v3 (Sharpe ≥ 0) under a v4 stamp, and `ATTESTATION.lockbox_oos_sharpe_min = 0.0` and the gate_spec lockbox description are stale. Sovereignty remains file-switch reversible and contradicts CLAUDE.md's gold-floor order.
7. **R is ✗ everywhere.** Every organ report is gitignored, and box adoption of `d30be2ce8` is unevidenced (RELEASE.json was last committed 09-28).

## B1 — Tier S 15-layer table (L) and sections 1–15 (T)

> **Reconciliation note:** this pass marked C ✓ from the seal and the Tier S checker alone. The matrix-wide rule under "C on LIVE" (law gate red, no green CI) makes C ✗ on every row. No verdict changes, because R already fails.

Checked 2026-09-30 ~14:15Z. LIVE = `d30be2ce` (merge of `origin/claude/tier-s-institution` @ `8b5c97a6` into live, incl. #52/#53), scored in the detached worktree `scratchpad/wt_full`. Origin LIVE has since moved to `aadf1e49` (+9 files: external_gauntlet preflight, IMMUTABLE_MANIFEST re-sign, QB-002 re-pin to the new gauntlet hash, tests, CRO doc). None of those touch Tier S, promoter, rails, pf_allocator, allocator_evidence or hourly_cycle, so no mark changes.

**Facts (measured, not taken from the builder):**
- **Seal: CLEAN.** `check_immutable_evaluator.py` OK (18 frozen files, 0 breaches). `check_immutable_rails.py` "seal HELD", 67 rails. `check_constitution_core.py` intact. v4's 2 breaches (promoter.py, rails.py) are gone.
- **QB-002: RECONCILED.** All 4 pinned sha256s (external_gauntlet, promoter, allocator_proof, state_admission) match on d30be2ce. On aadf1e49 the corpus re-pins external_gauntlet to its new hash `47c59fd2…`, which matches.
- **Checker:** `check_tier_s_program.py` rc 0: **BUILT 43 / PARTIAL 1 (S12) / BLOCKED_ON_USER 2 (S01, S30)**, 0 DONE. Consistent with the code.
- **Tests:** 16 `test_tier_s_*` files (incl. gateway_drill), `tests/tiers`, and test_quantbench: **288 collected, all pass under pandas 3.0.6 AND under the pinned 2.3.3** (`PYTHONPATH=pd233`). The v4 pandas-3 failure is fixed: `synthetic_regimes._scale_col` now uses `np.array(..., copy=True)`. closure_agent_worlds + gateway_drill + quantbench re-run on their own: 13 passed. CI for d30be2ce was not measured (the Actions listing through MCP came back stale, and `gh` is not installed).
- **promoter.tier_s_block: FIXED, now fails closed.** promoter.py:1671-1687: `except Exception` now returns `DOOR_ERROR: the Tier S door did not load …`. Inside `promotion_authority.block` every check that raises also withholds (`DOOR_ERROR: the <label> check raised`).
- **W: every hour, never rotated.** `tier_s` is in `CORE_LEGS` (hourly_cycle.py:850) and in `leg_rotation.ALWAYS_RUN` (leg_rotation.py:117), which is exempt from the budget-overrun deferral. Its cap is `LEG_BUDGET_SEC["tier_s"]=1_500` s (~10 min measured, inside the PT40M core window).
- **Stale-door risk: SMALLER, but one input is still at risk.** The door needs 4 files present and fresh (≤6h): door_verdicts, ONLINE_FDR_ROWS and PROMOTION_FREEZE, all written by `tier_s` every hour, plus `reports/REPLICATION.json` from `replication_civilization`. That leg is also in ALWAYS_RUN, but it belongs to the `validate` department resident, not the core plan. So any gap of 6h or more in that resident withholds EVERY new LIVE row as DOOR_ERROR. This fails closed, not open, and `door_inputs()` publishes its health each hour. **On the box no `desks/mt5/data/tier_s/*` and no `reports/REPLICATION.json` are committed, so until the box has run both legs once, every new promotion is withheld.**
- **`live_door.json`: still NO consumer.** Only `tier_s.py:4121` writes it (`review_live`). No promoter or retirement code reads it, and the cloud copy still says `"consumer": "… (desktop batch: promoter.py is sealed)"`.
- **ALPHA_RANK artifact: now EXISTS, but only from the cloud.** `docs/research/tier_s_runs/2026-09-30_cloud/ALPHA_RANK.json` (status MEASURED, EIAR 2.5365 over 58 certificates, 15 same-bet clusters). It is not a box artifact.
- **FREEZE→allocator: WIRED.** `tier_s.py:3431` passes `freeze=promotion_authority._freeze() is not None` into `allocator_tilts.build`. freeze_factor = 1+0.5·(2s−1), where s = n_oos/(n_oos+20), and it is heat-neutral. It reaches `pf_allocator` through `allocator_evidence.tier_s_factors`.
- **Exchange zero: still zeroes the MEAN, not the weight.** `TIER_S_TILT_LO=0.0`, and `EXCHANGE_LO=0.0` lets the tilt reach 0. pf_allocator:2123-2140 then applies `arr += (tilt−1)·|mean|`. With tilt 0, a positive-mean sleeve's mean becomes 0 and a negative-mean sleeve's mean doubles. Variance and covariance are untouched, so the optimiser, or the 20% heat-floor fill, can still fund a ZERO/EXIT sleeve. `sum(ex×cap×fz)` is still not renormalised after clipping.
- **S01 → gauntlet: still unwired.** `external_gauntlet.py` has no `constitution` reference, and S01 is BLOCKED_ON_USER.
- **S12 firewall at the gates: still PARTIAL.** `firewall.may` is called only inside `libs/tiers` (the door's reads and its ledger write) and `tier_s.py`. There is no call in `external_gauntlet`, the sealed gate path, or `promoter` outside the door.
- **R: still no box evidence.** No `desks/mt5/data/tier_s/box_evidence.json` on d30be2ce or aadf1e49. The only copy is the cloud one (`host: vm`, `counts_toward_done: false`). R ✗ on every row.
- Side effect of my run: the test suite dirtied `desks/mt5/data/events.jsonl` and some untracked data files in wt_full. I did not commit anything.

Marks order: I W A T R D C. T = pass at pandas 2.3.3 (CI pin), and here also at 3.0.6. C = evaluator + rails seal held, QB-002 clean, tier_s checker consistent. CI was not measured.

| ID | Item | Verdict | Marks (LIVE d30be2ce) | Evidence on LIVE | Still missing | Owner |
|---|---|---|---|---|---|---|
| L1 | Truth Kernel | PARTIAL | ✓✓✓✓✗✓✓ | truth_kernel, constitution; door withholds loosened constitution; fail-closed in block AND in promoter wrapper | S01 blocked (gauntlet ignores constitution); box R | Tier S build |
| L2 | World Data OS | PARTIAL | ✓✓✓✓✗✓✓ | macro-fusion sweep conditions via `BitemporalStore.latest_known` (S02) | One sweep only; no provenance on main data path; box R | Tier S build |
| L3 | World Model | PARTIAL | ✓✓✗✓✓✓✓ | world_edges → compiler rows | Hypothesis generation only; stale graph; no flows/regional | Tier S build |
| L4 | Researcher Civilization | PARTIAL | ✓✓✓✓✗✓✓ | researcher_prices → cycle_pricing; runtime blinding strips outcomes (S04) | No new non-LLM processes; box R | Tier S build |
| L5 | Hypothesis Ecology | PARTIAL | ✓✓✗✓✗✓✓ | QD/genomes/theory rows to intelligence/tier_s | Populations decide nothing | Tier S build |
| L6 | Research-Program Evolution | PARTIAL | ✓✓✗✓✗✓✓ | program_evolution in hourly tier_s leg | Challengers report only | Tier S build |
| L7 | Adversarial Science | PARTIAL | ✓✓✓✓✗✓✓ | prejudge flags in run_external_backtest; merge_hypotheses demotes in-family; S33 on real verdicts | Reorder-only; box R | Tier S build |
| L8 | Universal Validation | PARTIAL | ✓✓✓✓✗✓✓ | **Now fails closed end to end** (promoter.py:1685 DOOR_ERROR); seal clean; #52 merged | live_door.json unconsumed; REPLICATION.json freshness depends on validate resident; box R | Both threads |
| L9 | Alpha Topology | PARTIAL | ✓✓✓✓✗✓✓ | alpha_rank two-sided in cycle_pricing; **ALPHA_RANK.json now produced (cloud)** | Box ALPHA_RANK; two rank organs | Tier S build |
| L10 | Portfolio Intelligence | PARTIAL | ✓✓✓✓✗✓✓ | clamp fix; **FREEZE → allocator_tilts (freeze_factor)**; #53 merged | Exchange zero zeroes mean not weight; ex×cap×fz not renormalised after clip; tilts cloud-only | Other slices |
| L11 | Execution Intelligence | PARTIAL | ✓✓✓✓✗✓✓ | S23 alpha/exec-drag split; capture_factor into tilts | 0 matched fills → inert | Other slices |
| L12 | Live Reality Engine | PARTIAL | ✓✓✓✓✓✓✓ | THEORY_REFUTED withholds; forward_reconcile.json; review_live → live_door.json | live_door reaches no retirement (no reader); R here is the forward_reconcile box artifact, the Tier S half has none | Other slices |
| L13 | Meta-Science | PARTIAL | ✓✓✓✓✗✓✓ | research_bandit leg (core, hourly) publish() | research_budget.json authoritative:false | Tier S build |
| L14 | Architecture Evolution | PARTIAL | ✓✓✗✓✗✓✓ | twin, self_model (+twin consumer test), shadow_desk, rollback | S30 blocked; propose-only | Other slices |
| L15 | Operational Kernel | PARTIAL | ✓✓✗✓✗✓✓ | gateway drill passes; drill in organ_chaos | Report only; no standby/failover | Other slices |
| T1 | Truth Kernel spec | PARTIAL | ✓✓✓✓✗✓✓ | journal, seal (clean), constitution withhold | S01; no order-time lineage | Tier S build |
| T2 | World Data OS spec | PARTIAL | ✓✓✓✓✗✓✓ | PIT reads in macro sweep | Not on acquire_datasets; no € costs | Tier S build |
| T3 | World model graphs | PARTIAL | ✓✓✗✓✓✓✓ | world_edges classification | No flows/regional; decides nothing | Tier S build |
| T4 | Researcher civilization + blinding | PARTIAL | ✓✓✓✓✗✓✓ | runtime blinding, blinding_runtime.jsonl | No independent-discovery evidence | Tier S build |
| T5 | AlphaEvolve-for-alpha | PARTIAL | ✓✓✗✓✗✓✓ | evolution, program_evolution | No LLM-in-loop code evolution | Tier S build |
| T6 | MAP-Elites 12 axes | PARTIAL | ✓✓✗✓✗✓✓ | qd_axes | Steers nothing | Tier S build |
| T7 | Researcher genomes | PARTIAL | ✓✓✗✓✗✓✓ | RESEARCHER_GENES | Steers tier_s rows only | Tier S build |
| T8 | Researcher market | PARTIAL | ✓✓✓✓✗✓✓ | prices 0.15 + bandit 0.20 → cycle_pricing | FLOOR 1.0: nothing loses compute | Tier S build |
| T9 | Red Queen per researcher | PARTIAL | ✓✓✓✓✗✓✓ | prejudge demotion; gauntlet_arena | Demote-only, never at the sealed gate | Tier S build |
| T10 | Planted traps / FREEZE | PARTIAL | ✓✓✓✓✗✓✓ | _freeze in fail-closed door; **FREEZE now tilts the allocator toward OOS-evidenced sleeves** | review_live unconsumed; box R | Tier S build |
| T11 | Adaptive multiplicity | PARTIAL | ✓✓✓✓✗✓✓ | online_fdr withholds over_budget; #52 merged | Proxy p-values; box R | Tier S |
| T12 | Epistemic firewall | PARTIAL | ✓✓✗✓✗✓✓ | firewall.may on door reads/ledger write | S12 PARTIAL: no may() in gauntlet/sealed gates or promoter proper | Tier S build |
| T13 | Negative knowledge | PARTIAL | ✓✓✓✓✗✓✓ | breadth_sweep reads failure_memory (S13) | Other generators don't; reorder only | Tier S build |
| T14 | Ancestry graph | PARTIAL | ✓✓✓✓✗✓✓ | effective_discoveries → alpha_rank | No code/data ancestry | Tier S build |
| T15 | Effective Independent Alpha Rank | PARTIAL | ✓✓✓✓✗✓✓ | alpha_rank two-sided; docket_keff; ALPHA_RANK.json (cloud, EIAR 2.54 / 58 certs) | Box ALPHA_RANK | Tier S build |

Counts LIVE (d30be2ce): DONE 0 / PARTIAL 30 / MISSING-branch 0 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0.
- Every row now has I, W, T, D and C. 20 of 30 rows also have A.
- 28 rows fail R. L3/T3 have their world-graph R, but no A.
- L12 is the only row with 6 of 7 marks and R ✓. It misses nothing but DONE-grade R for its Tier S half and a live_door reader. Strictly its A is ✓ through THEORY_REFUTED, so it is the closest to DONE.

Movement vs v4 (LIVE column):
- Tier S is now on live, so LIVE takes v4's "#55" marks.
- C ✗→✓ on all 30: seal clean, QB-002 reconciled, checker consistent.
- New since v4: the promoter wrapper fails closed; the pandas-3 break is fixed; FREEZE→allocator is wired; an ALPHA_RANK artifact exists (cloud); tier_s is on the core plan and in ALWAYS_RUN.
- No row reaches DONE: R ✗ blocks every one.

### Remaining gaps
1. **Box R.** Get one box pass of `tier_s` and `replication_civilization`, with `desks/mt5/data/tier_s/box_evidence.json` (host vmi3571445) committed by the sync. Until then the fail-closed door withholds every new LIVE row as DOOR_ERROR.
2. **REPLICATION.json staleness.** Its writer runs on the `validate` resident, not the core plan. If that resident is down for 6h or more, the door blocks all promotions. Either put it on the core plan or alarm on `door_inputs`.
3. **`live_door.json` has no reader.** Wire it into promoter retirement. That needs a signed promoter edit.
4. **Exchange ZERO/EXIT zeroes the posterior mean, not the weight.** A negative-mean sleeve's mean is doubled, and the optimiser or the heat-floor fill can still fund the sleeve. Also, ex×cap×fz is not renormalised after clipping.
5. **S01 and S12.** S01: `external_gauntlet` never reads the constitution. S12: no `firewall.may` at the sealed gates.
6. **ALPHA_RANK and allocator_tilts.** Both exist only as cloud artifacts; they need box versions.
7. **FLOOR 1.0 in cycle_pricing.** No researcher or leg can lose compute below its base.
8. **Execution intelligence.** Stays inert until matched fills > 0.
9. **CI conclusion for d30be2ce / aadf1e49 not measured.** Confirm the `quality` job is green.

## B2 — Tier S sections 16–30 (T) and final loop

LIVE = claude/llm-auto-upgrade-verify-gcjac3 @ d30be2ce. It merges `claude/tier-s-institution` @ 8b5c97a6 (PR #55), plus #52/#53 (b8f53cd0 allocator sovereignty is an ancestor), with one reviewed manifest re-sign (1ed475a9).
Marks: I W A T R D C, in that order. **LIVE only.** The "#55" column is gone because #55 is now on LIVE.
Baseline: B2_v4 (LIVE @ 69da0158, TIERS @ 25e14650).
New since v4 on the Tier S side:
- 3851a402 / b3620bb5: a door input missing for more than 2 h fails the leg loudly.
- 4905e47d: the pandas-3 fix for `_scale_col`.
- f28d21c2 / 68430a19: `tier_s` and `replication_civilization` are in ALWAYS_RUN.
- 5c18fd02: consumers for TWIN.json and the world flags, the honesty-channel fix, and `compose`'s falsifier.
- 3c9b44cf / 96c378a3: tests for all of the above.
- bb384529: FREEZE now tilts the allocator.
- fa51bc5a: the promoter door fails closed. DSR variance 0.014863 → 0.0002.
Origin LIVE has since moved 11 commits further, to aadf1e49. **Those commits are not scored.**

### Facts (checked on d30be2ce)
- **Seal is clean now.**
  - `check_immutable_evaluator.py`: OK (exit 0). The v4 breaches in promoter.py and rails.py were re-signed.
  - `check_constitution_core.py`: intact.
  - No conflict markers are left in `runtime_state.json` or `RUNTIME_STATE.md`.
- **Ledger:** `check_tier_s_program.py` exits 0 and prints "46 layers; BUILT 43; PARTIAL 1; BLOCKED_ON_USER 2". It still claims no DONE, so it stays consistent. `check_formal_claim.py` exits 0 on its own, but reads UNMEASURED.
- **Law gate: FAIL** (`run_law_gate.py`, 87 fences).
  - Most breaches are about artifacts absent from a cloud host (no pf_allocation, census or rotation record). Those are not attributable to Tier S.
  - **One code-level breach is Tier S's own.** `check_birth_obligations.py`: "3 arrived without its obligation (a clock, an artifact, a named consumer and a row in the runtime attestation)". It names `scripts/check_tier_s_program.py` and `scripts/check_formal_claim.py`, both from #55, plus `judging_burndown.py`.
  - `check_dead_architecture` is over its ratchets (CONTESTED 68 > 66, BURNING 61 > 50). None of the contested or burning entries is a Tier S organ.
- **CI on d30be2ce: cancelled** (run 36718891804), so there is no green verdict. The head it went to, aadf1e49, is pending. **C ✗ on every row**, for the birth-obligation breach and because CI has no verdict.
- **Tests: 317 pass under pandas 2.3.3 AND 317 pass under pandas 3.0.6.** The run was `python -m pytest -q -p no:cacheprovider` over `desks/mt5/tests/test_tier_s_*.py`, `test_cycle_pricing.py`, `test_synthetic_regimes.py` and `tests/tiers`.
  - The v4 pandas-3-only failures (`test_tier_s_closure_agent_worlds` ×2) are fixed. `_scale_col` now copies its column (4905e47d).
  - No pandas-3-only failures remain.
- **Still no box artifact.**
  - The tree has no committed `desks/mt5/data/tier_s/*`, and no `reports/TWIN.json`, `EXECUTION_SCIENCE.json` or `TIER_S.json`. That is true of d30be2ce and of origin LIVE @ aadf1e49.
  - The only bundle is `docs/research/tier_s_runs/2026-09-30_cloud/`, which declares itself not box evidence. **Every R is ✗** except T24/T27, which rest on pre-existing box artifacts, as in v4.
- **Re-checking the v4 gaps:**
  - **execution_science is scheduled on LIVE: YES.** `hourly_cycle.execution_science()` (L2097) runs the leg via `_costed("execution_science", …)` (L4719). T23 W goes back to ✓.
  - **TWIN.json has a reader: YES.** `tier_s._consume_shadow_verdicts` (L3734) is called from `organ_twin` on every `twin` run.
    - A shadow **REJECT** marks the challenger REJECTED. That frees its replay slot, keeps the adoption REJECTED and withdraws any proposal.
    - A **PROPOSE/PROMOTE** goes to `data/tier_s/twin_proposals.json` for the principal. It adopts nothing (money path).
    - The self-model reads TWIN.json as a deficiency (`_shadow_doc_for_self_model`; stale for more than 6 h reads UNMEASURED).
  - **Closure/agent world flags have a reader: YES.** `review_panel.ecologist` reads `ev["worlds"]`:
    - `CLOSURE_GAP_LOSS` (HIGH) fires when the candidate's own positive edge turns negative in a gap world.
    - `LOSES_IN_EVERY_ECOLOGY` (HIGH) fires when it is negative in all three ecologies.
    - Both resolvers are candidate-specific. A HIGH finding feeds `REVIEW_PANEL_FAILED` at the withhold-only door.
  - **FREEZE → allocator: YES, wired.**
    - `_allocator_tilts` reads `promotion_authority._freeze()`.
    - `allocator_tilts.build(freeze=…)` applies freeze_factor = 1 + 0.5·(2s−1), with s = n_oos/(n_oos+20). It is heat-neutral.
    - `pf_allocator` reads it through `tier_s_factors`.
    - Tested in `test_tier_s_door.py`.
  - **Promoter fail-open: FIXED.** `promoter.tier_s_block` (L1679–1687) now returns `DOOR_ERROR …; withheld until it does` on any exception. It was `return None`.
  - **Growth-block risk of the stale-door withhold: MITIGATED.** `tier_s` and `replication_civilization` are now in `leg_rotation.ALWAYS_RUN`, so the leg is never rotated out.
    - It is still capped at 1,500 s. The first adoption, before any box pass, still withholds new LIVE rows until the first pass.
    - No missed-growth line was measured for that window.
  - **Automatic rollback: STILL MANUAL.** `tier_s.py --rollback-to X --apply-rollback` (L4365) is a human act. `Adopt-And-Seal.ps1`/`Adopt-Release.ps1` contain no rollback or regression stop.
  - **split_fills / matched fills: UNCHANGED.** `execution_science.split_fills` is still described as a "hook" (L160). Its only callers are tests. `matched_fills` is still 0 (`capacity.py`), so live fills do not recalibrate anything.
  - **theory.compose and honesty-channel tests: PRESENT AND GREEN.**
    - `tests/tiers/test_theory_compose_and_honesty.py` covers compose's identity, order sensitivity and the execution falsifier.
    - `desks/mt5/tests/test_tier_s_honesty_channel.py` covers the real-state posterior. It pins the fix where a measured honesty of 0 had been turned into 1.
  - **synthetic_regimes pandas-3 fix: DONE** (see Tests).
  - **Still open:**
    - `live_door.json` still has no reader. `git grep` finds only the writer and the sync script.
    - The exchange ZERO still leaks through the fallback. `contest(ev, funded, …)` builds its baselines over every `ev` name, and `book_fallback` is taken from them (pf_allocator L4015–4023). A zero tilt zeroes the mean, not the baseline weight.
    - The DSR variance is still a fixed spec constant. It is now 0.0002 in `gate_spec.yaml` (fa51bc5a), not measured per campaign, and `effective_trials.py:309` still defaults to 0.014863.

| ID | Item | Verdict | Marks (LIVE) | Evidence on LIVE | Still missing | Owner |
|---|---|---|---|---|---|---|
| T16 | Counterfactual World Lab | PARTIAL | ✓✓✓✓✗✓✗ | Closure and agent worlds run in `synthetic_regimes` (scheduled) and are joined per certificate. **A gained:** the ecologist's HIGH `CLOSURE_GAP_LOSS` / `LOSES_IN_EVERY_ECOLOGY` withholds at the door. **The pandas-3 failure is fixed**, so both pins pass. | No box artifact. C: birth obligations fail, and CI has no verdict. | Tier S build |
| T17 | Alpha Theory Compiler | PARTIAL | ✓✓✗✓✗✓✗ | **T gained:** `compose` is tested (identity, order, and the execution falsifier in the composite). | No authority over any decision. No artifact. C. | Tier S build |
| T18 | Theory↔Evidence graph | PARTIAL | ✓✓✓✓✗✓✗ | `THEORY_REFUTED` withholds. **The promoter wrapper now fails closed** (DOOR_ERROR). The stale-input withhold rides an ALWAYS_RUN leg. | `live_door.json` has no reader. The first-adoption withhold window is unmeasured. No artifact. C. | Tier S build |
| T19 | Heterogeneous non-LLM intelligence | PARTIAL | ✗✓✗✓✗✓✗ | Unchanged. | No solver or prover. No authority. No artifact. C. | Tier S build |
| T20 | AI peer review panels | PARTIAL | ✓✓✓✓✗✓✗ | The ecologist now reads the world flags. `REVIEW_PANEL_FAILED` withholds, and the promoter fails closed. | The reviewers are fixed if-rules. The live-row review (`live_door.json`) has no consumer. No artifact. C. | Tier S build |
| T21 | Auto-invent new tests | PARTIAL | ✓✓✓✓✗✓✗ | Unchanged. Ratified gates reorder the docket via `prejudge_verdict` / `merge_hypotheses`. | No ratified rule exists on any ref. Demotion only reorders. DSR variance is a constant (0.0002). No artifact. C. | Tier S build |
| T22 | Auto-invent research grammars | PARTIAL | ✗✓✗✓✗✓✗ | Unchanged. | No new representation class. No budget authority. No artifact. C. | Tier S build |
| T23 | Execution as autonomous science | PARTIAL | ✗✓✓✓✗✓✗ | **W regained on LIVE:** `hourly_cycle.execution_science` is costed every pass. Drag reaches the exchange bids, and capture reaches pf_allocator. Tests pass. | `split_fills` is a hook with test-only callers. matched_fills = 0. No slicing, urgency or adverse-selection model. No artifact. C. | Tier S build |
| T24 | No-trade first-class | PARTIAL | ✗✓✓✓✓✓✗ | #53 is merged (allocator sovereignty: zero or below-min sends no order). A factor below 0.5 is applied. | The exchange ZERO is a zero mean, not a zero weight. The `book_fallback` baselines over every `ev` name still re-fund it. C. | Tier S build / Institutional |
| T25 | Opportunity Exchange | PARTIAL | ✓✓✓✓✗✓✗ | The chain holds, with drag in the bids. **FREEZE now tilts heat toward OOS-evidenced sleeves**, heat-neutrally. The control arm is exactly 1.0. | The ZERO→fallback leak. No box artifact. C. | Tier S build |
| T26 | Live prediction-accounting | PARTIAL | ✗✓✓✓✗✓✗ | Unchanged. | No vol, factor or correlation forecasts, and none per model. No artifact. C. | Tier S build |
| T27 | Live reality outranks backtests | PARTIAL | ✓✓✓✓✓✓✗ | **The honesty channel is now tested, and a real defect was fixed:** the exchange posterior turned a measured honesty of 0 into 1. It now reads the writer's certificate→factory map and respects the predictions suspension. | C only: the birth-obligation breach and no CI verdict. It still does not reach admission for new discoveries. | Tier S build |
| T28 | Digital twin (shadow desk) and rollback | PARTIAL | ✓✓✓✓✗✓✗ | **A gained:** `_consume_shadow_verdicts` turns a LOSS into a REJECTED challenger (slot freed, adoption blocked) and a WIN into a principal proposal. The self-model counts a losing twin as a deficiency. Tested in `test_tier_s_twin_consumer.py`. | Rollback is still a manual `--apply-rollback`. Adopt-And-Seal has no regression stop. No artifact. C. | Tier S build |
| T29 | Self-model | PARTIAL | ✓✓✗✓✗✓✗ | It now also reads TWIN.json as a deficiency. | No authority. p_fix and cost are hand-set. No artifact. C. | Tier S build |
| T30 | Architecture evolution | PARTIAL | ✗✓✗✓✗✓✗ | Unchanged. The ledger says BLOCKED_ON_USER. | Money-path adoption is refused. No regression stop. No artifact. | Tier S build |
| LOOP | Closed research→capital loop inside a Truth Kernel | PARTIAL | ✗✓✗✗✗✓✗ | On LIVE now: the promoter fails closed; FREEZE reaches the allocator; TWIN and world flags have consumers; #52/#53 are merged; the seal is clean. | The fallback re-funds exchange zeros. `live_door.json` has no reader. The DSR variance is a constant. Rollback is manual. `split_fills` is a hook. There is no end-to-end loop test and no box artifact. The law gate's birth-obligation breach covers Tier S checkers. CI on d30be2ce was cancelled. | Tier S build / Institutional |

Counts on LIVE: DONE 0 / PARTIAL 16 / MISSING 0 / EXCLUDED 0 / TIME-BOUND 0 (16 rows).
- **Marks gained vs v4 LIVE:** every row gained, because #55 is now on LIVE. Against the v4 "#55" projection:
  - T16 A
  - T17 T
  - T23 W (restored)
  - T24 D (#53 merged)
  - T28 A
- **Best rows:** T27 at 6/7. T16, T18, T20, T21, T25 and T28 at 5/7.
- **No row can reach DONE:** R (no box artifact) and C (law-gate birth-obligation breach, and no CI verdict) fail on every row. The seal itself is now clean.

### Remaining gaps
1. **Box artifacts, zero of them:** the box must adopt d30be2ce+, then run a `tier_s` pass. After that, commit `data/tier_s/box_evidence.json` from vmi3571445 and add `reports/TWIN.json` / `EXECUTION_SCIENCE.json` to the sync.
2. **C:**
   - Give `check_tier_s_program.py` and `check_formal_claim.py` their birth obligations (clock, artifact, consumer, attestation row), or retire them.
   - Get a completed green CI run on a LIVE head (d30be2ce's was cancelled).
3. **Exchange zero ≠ zero weight:** `book_fallback` baselines are still built over every `ev` name, so a sleeve with a ZERO tilt is re-funded on a failed or stale proof.
4. **`live_door.json` has no reader.** The door's review of live sleeves is a report only.
5. **Rollback is manual.** There is no regression stop in Adopt-And-Seal, and a TWIN loss rejects a challenger but never rolls back a release.
6. **`split_fills` is still a hook:** matched_fills = 0, so live fills do not recalibrate.
7. **DSR variance is a fixed constant** (0.0002, down from 0.014863), not measured per campaign.
8. **The first-adoption door withhold** (before any box tier_s pass) has no missed-growth ledger line.
9. **No end-to-end LOOP test.**

## C — 16 hardening items (H), depth priorities (DP), admission rule (ADM)

Re-scored 2026-09-30 ~13:15Z. The scored tree is **LIVE @ `d30be2ce`**, the worktree `wt_full`. It is on `origin/claude/llm-auto-upgrade-verify-gcjac3`, reached from `69da0158` through 141 commits. It merges #52 (true lockbox, `0b220216`), #53 (allocator sovereignty, `f604ec86`), #55 (Tier S, several merges ending in `d30be2ce`), the sealed pass `fa51bc5a`, and the re-sign `1ed475a9`.
Marks are in the order I W A T R D C. There is no "#55" column any more: everything is scored on LIVE only. R counts a committed artifact from any host. `R✓(cloud)` means a committed artifact that is not box evidence.

**Note on the live head.** origin has already moved past `d30be2ce`, and those later commits are **not scored here**:
- `4678fe4f` changes the preflight for gauntlet parameters, and `fc6c34e5` re-signs external_gauntlet for it.
- #96 fixes the alt-data test.
- #97 ("give the event-surprise collector its grounds, fix the fetch_universe tests' argv") targets two of the four failures below.
- #105 is CRO D14.
- The next re-score should move to the #97 head.

**Row count.** The table has **30 rows**: H1–H16, ADM, DP1–DP11, AC3 and AC13. v4's count line said 28 and 12 MISSING (branch-only), but its own table listed 14 branch-only rows. v5 counts all 30.

## Verified claims (d30be2ce)

| Claim | Verified? | How |
|---|---|---|
| DSR variance 0.0002 | YES | `desks/mt5/policy/gate_spec.yaml:70` has `fixed_variance_of_sharpes: 0.0002`. 0.014863 now survives only as the no-spec fallback in `effective_trials.py:309` and in a history string in `gate_policy.py:84`. |
| Lockbox with three reads (held-out Sharpe, last-30% Sharpe, half-split persistence clear the cell's own deflated hurdle) | YES, the code and tests are present | `fa51bc5a`, lockbox v4. `test_lockbox_bar_and_daily_series`, `test_canonical_reserved_lockbox` and `test_lockbox_independence` pass. The claimed "15/130 real, 0/318 traps" has **no committed artifact**: it is only in the commit message. |
| Trades summed per day | YES | `external_gauntlet.daily_series` (`fa51bc5a`). The test passes. |
| Tier S door fails closed | YES | `promoter.tier_s_block`, `except Exception` → returns `DOOR_ERROR: … did not load`. The v4 gap is closed. `test_tier_s_door` passes. |
| Gateway: no quote means no send, and a crashing `order_send` counts as a failed leg | YES | `gateway.place_bracket` (`fa51bc5a`). The drill and tier_s tests are green. |
| QB-002 re-pinned, line endings normalised | YES | `quantbench._sha` normalises line endings. `1ed475a9` re-pins `corpus.jsonl`. `test_quantbench.py` passes (2/2). |
| Seal | **CONSISTENT** | `scripts/check_immutable_evaluator.py`: **OK**, 18 frozen files, 0 breaches. QB-002 agrees. promoter.py and rails.py are signed. The v4 "two seals disagree" finding is **resolved**. |

## Tests (pandas 3.0.6 local AND pandas 2.3.3 venv, the CI pin)

- **Now passing:**
  - `test_quantbench` (2)
  - `test_scalp_promotion` (15, all). The 4 failures from v4 are gone.
  - The new and merged suites: allocator_sovereignty, live_rows_need_a_cost_basis, superseded_policy, all 3 lockbox files, residual_cost_basis_fence, all 18 `test_tier_s_*` files and `tests/tiers`. **344 passed, 0 failed** (pandas 2.3.3). The log is `rescore/c_v5_tests.log`.
- **Still failing**, with the same result on pandas 2.3.3 and 3.0.6, so **no failure is specific to pandas 3**:
  1. `test_event_surprise::test_the_registered_grounds_file_on_this_tree_is_mined_and_labelled`. `desks/mt5/data/event_consensus_sources.json` is absent. #97, after d30be2ce, targets it.
  2. `test_macro_regime::test_load_history_adds_real_yield`. `REAL_YIELD_10Y` is empty (0 rows > 1000 fails). Run by itself, the file **fails to collect** (`No module named 'mt5desk'`: the test has no `sys.path` insert and depends on another file's). In the full suite it only resolves through file-order side effects.
  3. `test_certificate_single_writer::test_external_gauntlet_recovers_only_exact_gate_archive_rows`. This is a source-grep test: `DATA / "UNIVERSAL_SURVIVORS.canon.json"` is no longer in `external_gauntlet.py`. It is either a stale test or a removed recovery path in the sealed judge. Unresolved either way.
  4. `test_universe_producers_merge` (2 tests). `SystemExit: 2`, because argparse reads pytest's argv. It fails under a bare `pytest <file>` and **passes under the CI shape** (`-n 2 --dist loadfile`, with worker argv). It depends on how pytest is invoked, and #97 fixes it after d30be2ce.

## CI

- The d30be2ce run, **36718891804**, completed as **cancelled**.
- Every run on LIVE since then has been cancelled or is pending:
  - 2ac3454f: cancelled
  - 515d665e: cancelled
  - fc6c34e5: cancelled
  - #105: cancelled
  - #96: cancelled
  - #97 (`aadf1e49`): pending
  - #87: queued
- **No completed green run on LIVE: UNMEASURED.**

## Committed artifacts (box evidence)

- `docs/research/tier_s_runs/2026-09-30_cloud/`: a cloud run. Its ABOUT says "NOT box evidence".
- `desks/mt5/data/tier_s/box_evidence.json` from vmi3571445: none on this tree.
- `desks/mt5/data/research_budget.json`: last committed 09-28, `authoritative:false`.
- `effective_breadth.jsonl`: the last row is 2026-09-16.
- `desks/mt5/data/sleeves.json`: last committed 09-28. It has 66 rows, 40 of them LIVE, and **0/40 carry `cost_hash`**, because #53's demotion has not yet run on the box.
- `data/tier_s/grammar.json` and `desks/mt5/reports/acceptance_properties.json` are absent.
- `check_formal_claim.py`: UNMEASURED, 0/6 invariants backed by the gateway. `--require-state` exits 2.
- `check_tier_s_program.py`: rc 0, 46 layers: 43 BUILT / 1 PARTIAL / 2 BLOCKED_ON_USER / 0 DONE.

**Meaning of C in v5.** C (the tree is self-consistent) is no longer ✗ because of the seal. It stays ✗ on every row because LIVE has no completed green CI run and still has 4 failing test files.

| ID | Item | Verdict | Marks (LIVE d30be2ce) | Evidence | Still missing | Owner |
|---|---|---|---|---|---|---|
| H1 | Formal verification of money path | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | #55 on LIVE. The `check_formal_claim --require-state` fence is present. The drill is green, and the gateway no-quote and crash fixes (`fa51bc5a`) close the 2 send-path defects. The cloud FORMAL.json is committed. | A VERIFIED claim, meaning the gateway backs every invariant (it backs 0/6). A box FORMAL.json. Green CI. | Tier S |
| H2 | Independent evaluator civilization | PARTIAL | ✓✓✓✗R✓(cloud)✓✗ | The seal is consistent: 0/18, and QB-002 agrees. The door now fails closed on a load error (DOOR_ERROR). T ✗: `test_certificate_single_writer` (the gauntlet archive-recovery source check) fails. | Resolve the archive-recovery test (stale or a regression). A separate evaluator stack. Green CI. | Tier S |
| H3 | Architecture evolution, sealed suites | PARTIAL (was MISSING branch-only) | ✓✓✗✓R✓(cloud)✓✗ | S33 (`gauntlet_arena.py`) is on LIVE: genomes are judged against the real gauntlet's verdicts. | Adoption must change the real gauntlet, scheduler or execution. | Tier S |
| H4 | Immutable meta-benchmark, thousands of cases | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | QB-002 re-pinned with normalised line endings (`1ed475a9`). `test_quantbench` passes, so T ✓. The sealed suite of 448 cases is cited only in a commit message. | A committed immune score from the box. Thousands of cases. A release gate on the score. | Tier S |
| H5 | Active information acquisition (EVOI) | PARTIAL | ✓✓✗✗R✓(cloud)✓✗ | T ✗: `test_event_surprise` (grounds file absent) and `test_macro_regime` real yield (empty series; the file does not collect standalone). Both fail on pandas 2.3.3 as well. | A value-driven data buy. Green data tests (#97 addresses event_surprise after d30be2ce). | Tier S |
| H6 | Research-search frontier estimator | PARTIAL | ✓✓✓✓R✓(cloud)✓✗ | A cloud FRONTIER.json is on LIVE. | The estimator is floored at 1.0. No box artifact. | Tier S |
| H7 | Epistemic uncertainty engine, 5 levels | PARTIAL (was MISSING branch-only) | ✓✓✗✓R✓(cloud)✓✗ | A cloud EPISTEMIC.json exists. It has no acting reader. | A consumer that refuses on "not enough evidence". | Tier S |
| H8 | Cross-engine independent replication | PARTIAL | ✓✓✓✓R✓(cloud)✓✗ | `live_door.json` is published by the box sync. Grep shows the promoter still does not read it. | A second engine. A reader for live_door. | Tier S |
| H9 | Counterfactual failure search, architecture level | PARTIAL (was MISSING branch-only) | ✓✓✗✓R✓(cloud)✓✗ | Report-only, on LIVE. | A search that changes the factory or allocator. | Tier S |
| H10 | Compute OS | PARTIAL | ✓✓✓✓✗✓✗ | Unchanged. | CPU seconds only. No authoritative budget. | Tier S |
| H11 | Global state replay at any second | PARTIAL (was MISSING branch-only) | ✓✓✗✓R✓(cloud)✓✗ | A cloud REPLAY.json exists. It has no reader. | Market, model and budget state. A consumer. | Tier S |
| H12 | Continual recovery / chaos experiments | PARTIAL | ✓✓✗✓R✓(cloud)✓✗ | The drill is green. The gateway no-quote and crash fixes land. A cloud CHAOS.json exists. | A real kill, disconnect or VPS-loss drill. The drill must gate something. A box artifact. | Tier S |
| H13 | Mechanism discovery from non-finance fields | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | On LIVE. | A judged or certified conversion on the box. | Tier S |
| H14 | Automated abstraction discovery | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | `grammar_bias` is consumed by expression_factory and alpha_evolution. `data/tier_s/grammar.json` is ABSENT. | Grammar at the path that is consumed. Learned primitives > 0. | Tier S |
| H15 | Scientific memory compression | PARTIAL | ✓✓✗✓✗✓✗ | Failure memory orders `breadth_sweep`. | Consumed as authority. | Tier S |
| H16 | Human–machine separation of powers | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | promoter.py and rails.py are re-signed in the reviewed pass (`1ed475a9`). The manifest is 0/18. | S01 is BLOCKED_ON_USER. | Tier S |
| ADM | Subsystem admission rule (8 gains) | PARTIAL (was MISSING branch-only) | ✓✓✓✓R✓(cloud)✓✗ | `check_tier_s_program` rc 0: 43 BUILT / 1 PARTIAL / 2 BLOCKED / 0 DONE. A cloud CONTRACTS.json exists. | Nothing is removed. No box attestation. | Tier S |
| DP1 | Finish/wire everything | PARTIAL | ✓✓✓✗✓✓✗ | T ✗: 4 failing test files. `universe_producers_merge` fails only under a bare invocation (it passes under the CI xdist shape). | Box attestation for 43 BUILT. Green tests and CI. | Institutional |
| DP2 | Remove dormant/partial components | MISSING | ✗✗✗✗✗✗✗ | Nothing is deleted. | A retirement pass with a deletion ledger. | Inst / TS |
| DP3 | Repair the validation defects | PARTIAL (was MISSING branch-only) | ✓✓✓✗✗✓✗ | #52 is merged. Measured DSR variance of 0.0002, lockbox v4 with three reads, and the per-day trade sum are live, with their tests green. T ✗: `test_certificate_single_writer` (gauntlet archive recovery). R ✗: the 15/130 and 0/318 result is not committed, and the certificates have not been re-judged or migrated on the box. | Commit the sealed-suite result. A box re-judge of standing certificates under v4. Resolve the archive-recovery test. | Institutional |
| DP4 | Clear the judging backlog | PARTIAL | ✓✓✓✓✓✓✗ | Unchanged. | A post-#77 box reading with judged ≥ created. Green CI. | Institutional |
| DP5 | Measure actual independent breadth | PARTIAL | ✓✓✓✓✓✓✗ | `effective_breadth.jsonl` still ends 09-16. | Append a current reading. Green CI. | Institutional |
| DP6 | Research-budget allocation sovereign | PARTIAL | ✓✓✓✓✗✓✗ | `research_budget.json` (09-28) has `authoritative:false`. | An applied box reading with `authoritative:true`. | Institutional |
| DP7 | Allocator sovereign | PARTIAL | ✓✓✓✓✗✓✗ | #53 is merged (decision_core, sizing, pf_allocator, promoter). `test_allocator_sovereignty` passes, and `test_scalp_promotion` is 15/15 now, so T ✓. | A box pass showing the allocator's fractions deployed. Green CI. | Institutional |
| DP8 | Cost truth mandatory | PARTIAL (was MISSING branch-only) | ✓✓✓✓✗✓✗ | #53: `promoter.save_sleeves` demotes a LIVE row with no cost basis to STANDBY (`cost_basis_of`: the row, then the clock identity, then the registry). `test_live_rows_need_a_cost_basis` passes. R ✗: the committed `sleeves.json` shows 0/40 LIVE rows carrying `cost_hash`. | A box promoter pass that stamps or demotes every LIVE row, committed. | Institutional |
| DP9 | CI permanently green | PARTIAL | ✓✓✓✗✗✓✗ | The seal is consistent now: manifest 0/18, and QB-002 passes. 4 test files still fail (event_surprise, macro_regime, certificate_single_writer, and universe_producers_merge depending on invocation). None of them is specific to pandas 3. The d30be2ce CI run was cancelled. | One completed green run. The 4 files fixed (#97 covers 2, after d30be2ce). A `sys.path` fix in test_macro_regime. | Institutional |
| DP10 | Recursive research competition | PARTIAL | ✓✓✗✓R✓(cloud)✓✗ | Cloud QD.json and GENOMES.json. | Winners gain only compute. 0 independent discoveries. | Tier S |
| DP11 | Accumulate untouched forward/live evidence | PARTIAL | ✓✓✓✓✗✓✗ | `test_scalp_promotion` (the forward clock as certificate) now passes, so T ✓. There is no post-#84 box census. | A box census with `n_silent` 0 and ledgers advancing. Then time. | Institutional |
| AC3 | PIT, survivorship-safe, revision-aware, provenance-hashed data | PARTIAL (was MISSING branch-only) | ✓✓✗✗R✓(cloud)✓✗ | S02 bitemporal PIT reads in the macro sweep are on LIVE. T ✗: event_surprise and macro_regime fail (pandas 2.3.3 too). | The audit must gate certificate data. Green data tests. | TS |
| AC13 | Research methods compete experimentally | PARTIAL (was MISSING branch-only) | ✓✓✗✓R✓(cloud)✓✗ | S33 genomes compete on the real gauntlet's verdicts, on LIVE. | Winning methods must take over real judging. | TS |

**Counts on LIVE (30 rows):** DONE 0 / PARTIAL 29 / MISSING (branch-only) 0 / MISSING 1 (DP2) / EXCLUDED 0 / TIME-BOUND 0.

**Verdict changes vs v4 (LIVE):**
- 14 rows moved MISSING (branch-only) → PARTIAL: H1, H3, H4, H7, H9, H11, H13, H14, H16, ADM, DP3, DP8, AC3 and AC13. v4 said 12 but listed 14.
- Marks moved up:
  - T ✓ on H4 (quantbench), DP7 and DP11 (scalp_promotion 15/15).
  - The seal is consistent, so C is no longer ✗ *because of the seal*.
- Marks still ✗:
  - C, on every row: no green CI and 4 failing files.
  - R: box evidence is still absent on every row.

### Top gaps

1. **No completed green CI on LIVE.** The d30be2ce run and every later push run were cancelled. #97 is pending.
2. **4 failing test files on d30be2ce.** None of them is specific to pandas 3.
   - event_surprise: grounds file absent.
   - macro_regime: empty real yield, and the file does not collect standalone because the `mt5desk` path is missing.
   - certificate_single_writer: `UNIVERSAL_SURVIVORS.canon.json` recovery is missing from the sealed judge. Decide whether the test is stale or this is a regression.
   - universe_producers_merge: argv, and it depends on invocation.
   - #97 covers the first and the last, after d30be2ce.
3. **The lockbox v4 / DSR 0.0002 result is not committed as an artifact.** "15/130 real, 0/318 traps" is only in the commit message, and no standing certificate has been re-judged under v4 on the box.
4. **#53's cost truth has not run on the box.** The committed `sleeves.json` shows 0/40 LIVE rows with `cost_hash`. The next box promoter pass should stamp them or demote up to 40 LIVE rows to STANDBY. That is a large capital event worth watching.
5. **Box evidence is absent for all Tier S rows.** There is only the cloud run (`counts_toward_done:false`). The formal claim is 0/6 backed.
6. **The worktree was dirtied by the test runs.** The tests modified `desks/mt5/data/events.jsonl` and left untracked `artifact_acks.jsonl`, `ingestion_floor.json`, `lineage.sqlite` and `sandbox_liveness_state.json` in `wt_full/desks/mt5/data/`. My cleanup was blocked by the permission classifier, so the owner of wt_full should restore them.
