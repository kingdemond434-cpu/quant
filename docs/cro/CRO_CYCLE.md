# CRO_CYCLE
## Twice-Daily Autonomous CRO / Builder Procedure

### EXECUTION RULE

**THIS IS AN ACTION CYCLE, NOT A REPORTING CYCLE.**

When safe, authorized, material work exists, this cycle must produce at least one evidence-backed completed outcome:

- a verified implementation/release;
- a completed repair;
- a verified runtime/reconciliation result;
- a completed validation/adjudication;
- a justified park/retire/reopen decision;
- a verified bottleneck reduction;
- or another measurable closure of material work.

If actionable material work is available and authorized but the cycle only produces analysis, recommendations, TODOs or status prose, **the cycle failed**.

Do not create code churn merely to satisfy this rule. A no-change decision is valid only when supported by measured evidence.

**CYCLE-SCOPE RULE:** The numbered steps are ordered control priorities, not a demand to exhaust every subsystem or every possible work item in one run. A cycle is complete when it has:
1. checked capital-path integrity;
2. verified material prior changes that are due for verification;
3. performed the lightweight whole-desk census;
4. identified the current binding constraint;
5. closed or materially advanced at least one highest-value authorized item through evidence-backed action;
6. left durable canonical state so continuous workers can proceed.

Do not spend the run rereading or resummarizing the entire institution when the current binding constraint is already known and evidenced.

**AMENDMENT: EVERY PASS IS THE LAST CHANCE (principal's standing order, 2026-09-30; supersedes the scope limit above wherever they conflict).** Each pass works on every material item it notices, broad and deep, and carries each one fully to completion within that same pass. That means no partials, no deferring to tomorrow, and no stopping early or taking breaks while an item is still open. Treat the pass as if no cycle follows. The guards still bind: no forced or fake work on areas measured optimal (D12), a fix counts only when fully wired (D11), never lower a gate, and never route around a permission refusal. An item that is still blocked when the pass ends is recorded as BLOCKED with the exact reason and the exact unblock needed, never as done, partial or "next cycle".

**AMENDMENT: GET PAST TECHNICAL BLOCKS ALONE (principal's standing order, 2026-09-30).** The principal will not be there, so the pass clears every technical obstacle itself. That covers a failed fetch, a broken build, bad or missing data, a flaky or failing test, a stale artifact, a parked session, a crashed leg, a timeout and a merge conflict. For each one the pass retries with backoff, tries an alternate source or path, fixes the root cause, and carries on with everything else while it does. Every such workaround is recorded with its cause. **One boundary is absolute:** a permission or safety refusal (auto-mode, the permission classifier, a device or desktop rule, a sealed-judge or live-money fence) is NOT a technical error. It is never retried in another form, split up, or routed around. It is recorded as BLOCKED with the exact refusal and the exact approval that would clear it, and the pass finishes everything else.

**AMENDMENT: NEVER ASK THE PRINCIPAL (principal's standing order, 2026-09-30).** The principal will not be there. The pass never asks for permission, approval, a go, a sign-off or a re-sign, for anything, and never posts a question or an ask to the principal. It decides and acts on everything it is able to do. When a tool, fence or safety check refuses a step, the pass writes that item into the ledger as BLOCKED with the exact reason, and does not turn it into a request. It then finishes everything else.

**AMENDMENT: NEVER JUST NOTICE (principal's standing order, 2026-09-30 20:31Z: "for cro cycles every gap named by anything every gap it all notices the breadth section in general everything it must fully 100% close n maximise all the same time never just notice n report only"; also 20:29-20:30Z: "never just report always maximise", "always close things u named").** Every gap named by anything (a duty, check, fence, artifact, tensor, committee, the STEP 4B breadth review, or the pass itself) is closed to 100% and maximised in the same pass. A gap counts as closed only with three things: a fix commit, proof that the fix is wired (it runs on a schedule and leaves an artifact, D11), and an after-metric measured on that artifact. Noticing or reporting a gap without its closing fix is MISSED, never "reported", "tracked" or "next cycle". Where 100% is physically impossible, the pass drives the gap to its measured ceiling and publishes that ceiling with its evidence; the gap stays MISSED until the ceiling is reached. The guards above still bind: a permission or safety refusal is BLOCKED with its exact reason and never routed around, and no gate is ever lowered to close a gap. The next pass closes every gap the previous pass left unclosed FIRST (the previous ledger row's `gaps_named` minus `gaps_closed`), before it takes any new item.

Read `CRO_CYCLE.md` first.

Then load `QUANT_CONSTITUTION.md` for governing laws.

Load `QUANT_REFERENCE.md` only on demand for the subsystem currently being investigated, changed, or deeply audited. Do not reread the full reference every cycle unless a specific failure requires it.

Never refer to this desk as Aurum.

---

## STEP 0 — LOAD AUTHORITY + CURRENT STATE

Read current:

- sealed/canonical policy;
- repository and branch/worktree state;
- deployment/release identity;
- supervisor/work queue;
- manifest;
- research/evidence registries;
- unresolved high-priority work;
- live broker/account state where authorized;
- current alerts/incidents;
- previous material CRO changes.

If a named canonical capability is missing, nonfunctional, or cannot be proven operational, do not pretend the normal cycle can proceed in degraded form. Treat restoration of that canonical capability as the binding infrastructure defect and primary material item for the cycle. Repair it if safely authorized; otherwise stop dependent work and report the exact blocker/authorization needed.

Do not invent duplicate control planes.

---

## STEP 1 — CAPITAL-PATH INTEGRITY FIRST

Verify current critical path:

- broker/account/environment identity;
- positions;
- internal-vs-broker reconciliation;
- order ownership;
- unresolved UNKNOWN order outcomes;
- deadman/kill-switch state;
- live sleeve arm/allocation state;
- stale price/feed conditions;
- execution/reconciliation alarms.

Repair authorized operational defects immediately.

Do not modify validated trading logic merely because recent P&L is poor.

Do not manufacture trades.

---

## STEP 2 — VERIFY PREVIOUS MATERIAL CHANGES

For important changes from the previous Claude/Codex cycle, verify:

- canonical integration;
- tests;
- release identity;
- deployment identity;
- actual downstream consumption;
- post-change measurement;
- absence of regression.

Do not trust the previous report by itself.

If verification fails, create owned repair work and fix it.

---

## STEP 3 — WHOLE-DESK LIGHTWEIGHT CENSUS

Check the versioned manifest.

Identify:

- FAILED;
- DEGRADED;
- STALE;
- UNMEASURED;
- UNKNOWN;
- overdue deep reviews;
- unexplained zero production;
- queue aging;
- missing consumer receipts;
- stale success artifacts;
- recurring failures;
- blocked high-value work.

Do not deep-audit healthy unchanged components without reason.

---

## STEP 4 — RESEARCH FUNNEL HEALTH

Inspect the current flow:

DISCOVERY/ACQUISITION  
→ RECONSTRUCTION/GENERATION  
→ CONVERSION  
→ GAUNTLET  
→ FORWARD/SHADOW  
→ PROMOTION

For each stage inspect:

- throughput;
- backlog age;
- novelty;
- silent loss;
- blocker counts;
- completed work;
- current capacity.

Identify the current binding constraint.

Examples:

- acquisition;
- duplicate generation;
- poor conversion;
- evaluator throughput;
- sample insufficiency;
- forward evidence;
- missing data;
- broken provider;
- stale sandbox;
- broken handoff.

Do not celebrate upstream volume when the downstream constraint is unchanged.

---

## STEP 4B — DAILY TIER-1 BREADTH REVIEW (principal's standing order, 2026-09-30)

Every pass, without exception, asks and answers two questions from LIVE box data, never from docs or memory:

1. **Are breadth, research production and global ingestion/mining maxed out at tier-1 level?**
2. **What tier is the quant today?**

Benchmark against Western tier-1 firms (Renaissance, D.E. Shaw, Two Sigma, Citadel/Jane Street class) AND Asian ones (the Chinese quant majors such as High-Flyer, Ubiquant, Minghong, Lingjun; Japanese and Korean systematic/prop shops). Public figures are estimates and are labelled as estimates.

**Start from `desks/mt5/reports/TIER1_GAP.json`** (hourly leg `tier1_gap`, `desks/mt5/research/tier1_gap.py`): it re-measures most rows below from the box's own artifacts every hour and ranks them by orders of magnitude short of tier-1. Check its `sources` mtimes for staleness; fill in the rows it reads as UNMEASURED by hand.

Measure at least, with day-over-day change:

- instruments and datasets ingested; alt-platform yield (platforms yielding / platforms wired);
- source coverage by region and language (Western, Chinese, Japanese, Korean, Russian forests);
- cells mined per day and cells judged per day; judge capacity;
- UNKNOWN verdict rate and build/data-failure rate before judging;
- true backlog (all unjudged cells, not one queue) and its daily growth;
- certificates by family, family concentration, effective independent bets (k_eff) against the k_eff the return target needs, and empty risk clusters;
- certificate-to-forward rate, forward-ledger freshness, and symbols traded live per day;
- broker instruments with fresh bars that no book uses yet.

Baseline (2026-09-30, `/mnt/project-files/reports/tier1_breadth_gap_2026-09-30.md`): 249 instruments; 4 datasets; 0 of 14 alt platforms yielding; ~8.3k cells/day mined, ~5.3k/day judged; 43% UNKNOWN; 69% build/data failures; backlog ~1.4M growing ~3k/day; 837 certs from 10 families (41% cross_asset_residual); k_eff 2.53 against ~7 needed; 6 of 15 risk clusters empty; 9% cert-to-forward. Verdict: tier 3 overall.

**Sources, both every pass (principal, 2026-09-30):** read git (origin and its committed artifacts) AND the desktop (the desktop checkout plus the box read through it). Desktop/box data is the more accurate source. Where they differ, the table uses the desktop/box number, records the git value beside it, and flags the git copy STALE with its age. A value found only in git is marked GIT-ONLY and is never presented as live.

**Minimum table, reproduced every pass with fresh numbers** (columns: Measure | Us, desktop/box | Git value if different | Yesterday | Tier-1, public estimate | Gap). The 2026-09-30 baseline is shown; add any row that limits breadth:

| Measure | Baseline 2026-09-30 | Tier-1 (estimate) | Gap |
|---|---|---|---|
| Tradable universe | 249 symbols, one broker, 238/239 timeframes fresh | tens of thousands of instruments | ~100x |
| Datasets in use | 4 of 15 registered (10 only DISCOVERED) | thousands of datasets (Two Sigma cites >10k sources) | ~1000x |
| Alt-data platforms yielding | 0 of 14 | hundreds of vendor feeds | total |
| Deep-forest vectors | 502 named, 10 yielded (2%), 467 never attempted | — | 98% unyielded |
| Ingestion | 9,716 ledger rows/24h; 152,777/7d | — | — |
| Raw cells mined | 1,583,193 total, ~8,303/day, 86 families mined, 10 unmined | millions of hypotheses/day | ~10-100x |
| Judged | 5,266-5,915 verdicts/day (219/h), 18 cores | 10k-100k+ cores | ~1000x compute |
| Wasted verdicts | 43% UNKNOWN (53,460 of 124,342, 7d) | — | fixable |
| Never judged | 69% of prewarms fail build/data (20,247 of 29,466) | — | fixable |
| Unjudged backlog | 1,398,253, oldest 747h, growing ~3k/day | cleared continuously | growing |
| Certified | 837 certs, 10 families, 56 symbols, judged-to-cert 2.9% | — | — |
| Cert concentration | cross_asset_residual 344 (41%), macro_conditional 152, carry 144, formula 92, other 6 families 105 | — | concentrated |
| Effective breadth | k_eff 2.53 on 453 nominal; 6 of 15 risk clusters empty | hundreds to thousands of independent bets | ~100-1000x |
| Cert to forward | 9.1%; forward ledgers updated in 7d: 0 | — | stalled |
| Live | 21 LIVE sleeves (6 UNMEASURED); 249 trades/30d on 13 symbols; one symbol on 11 of 15 days | thousands of positions/day | — |

**THE DUTIES: explicit, numbered, and every one checked on every pass.** Nothing here is implied. Each duty has a named metric, a target, and the action the pass takes when the target is missed. Record each duty's metric value and a MET / MISSED / OPTIMAL / BLOCKED status in `TIER1_BREADTH_REVIEW.json` under `duties`, keyed by the duty number.

| # | Duty | Named metric | Target | Action on a miss (same pass, fully wired per D11) |
|---|---|---|---|---|
| D1 | **Read desktop over git** | `source_of_each_row` (DESKTOP/BOX, STALE-GIT, GIT-ONLY) | every row sourced from the desktop checkout or the box read through it | Re-read from the desktop or box. Put the git value in the "Git value if different" column, flagged STALE with its age. A row only git holds is marked GIT-ONLY and never presented as live. |
| D2 | **Tier verdict** | `tier_verdict` against Western tier-1s (Renaissance, D.E. Shaw, Two Sigma, Citadel/Jane Street class) and Asian ones (High-Flyer, Ubiquant, Minghong, Lingjun; Japanese and Korean systematic shops), with public figures labelled as estimates | a tier stated with the evidence for it | State the verdict. "Maxed out" or "exhausted" needs per-axis evidence (L1.51); without it the answer is NO. Never assume the machinery is at its peak or exhausted. |
| D3 | **Judging throughput to maximum** | `judged_per_day`, `created_per_day`, `judge_capacity_cores`; from `desks/mt5/reports/UNKNOWN_SHARE_CENSUS.json`: `sampled_plus_siblings` UNKNOWN share of judged cells and its named causes; first rulings per hour against created per hour (`first_rulings_per_hour`, `created_per_hour` in `reports/JUDGING_BURNDOWN.json`, which must be no older than 2h: an older burndown is itself the gap); busy judge cores against planned workers (`busy_cores`, `planned_workers`) | judged/day > created/day every day, heading for millions judged a day | Add judging capacity, cut UNKNOWN verdicts and build/data failures, and remove whatever stalls the judge. Never lower a gate. If another thread owns a throughput build, build on it and name the owner. |
| D4 | **Permanent backlog guard** | `backlog_total` (all unjudged cells, not one queue), `backlog_growth_per_day`, `backlog_oldest_hours`; the share of UNKNOWN verdicts that are never-fire or too-rare cells (`never_fires_days_0`, `too_rare_1_to_59_days` in `reports/JUDGE_COVERAGE.json`); requeued cells still without a terminal verdict (`requeued_without_terminal`) | growth <= 0 every day and the oldest cell getting younger; every requeued cell reaches a terminal verdict (`requeued_without_terminal` = 0) | Growth > 0 is a MISSED duty that the same pass fixes through D3. It is never cleared by deleting or skipping cells, and never by cutting mining. |
| D5 | **Same-day certificate and clock** | `verdict_to_cert_hours` (median, p95), `cert_to_clock_hours` (median, p95), `passing_cells_without_cert`, `certs_without_clock` | every passing cell certified, and every certificate on a running forward clock, the same day (p95 < 24h, both counts 0) | Unblock the handoff that stalls: the certifier, the promoter, the forward clock. The certificate still needs its full evidence. Source: `desks/mt5/reports/CONVERSION_FUNNEL.json` `cro_duties.D5` (hourly leg `conversion_funnel`), with every loss named in `certificates.lost` and `clocks.lost`. |
| D6 | **Conversions per stage to maximum** | `conv_ingested_to_mined`, `conv_mined_to_judged`, `conv_judged_to_cert`, `conv_cert_to_forward`, `conv_forward_to_live`, each with its day-over-day change | each stage flat or rising, avoidable loss falling | Take the stage with the worst avoidable loss and fix its waste (UNKNOWN, build/data failure, dropped handoff, stale clock, duplicate). Never loosen a gate. Source: `CONVERSION_FUNNEL.json` `cro_duties.D6`, and `verdicts.by_subclass.UNKNOWN` for the UNKNOWN causes. |
| D7 | **Dataset hunting at world scale** | `datasets_in_use`, `datasets_registered`, `alt_platforms_yielding / wired`, `forest_vectors_yielded / named / never_attempted`, `ingestion_rows_24h`, coverage by region and language | datasets in use rising toward thousands; every alt platform and forest vector attempted and yielding | Wire the next highest-value unused datasets, fix the fetch path of each non-yielding platform, and attempt the vectors never attempted. Never cut ingestion. |
| D8 | **Hypothesis volume** | `cells_mined_per_day`, `families_mined / unmined`, `tradable_universe_symbols`, `broker_symbols_fresh_but_unused` | mined/day rising toward millions a day, every family mined, every fresh broker symbol used | Start mining the unmined families and unused symbols, and raise generation. Never cut mining or research generation. |
| D9 | **Breadth of the book** | `k_eff`, `k_eff_needed`, `empty_risk_clusters`, `family_concentration_top_share`, `live_symbols_30d`; from `desks/mt5/reports/CULTURE_ORTHOGONALITY.json`: `k_eff_survivors` (nominal vs merged, SAME_EDGE groups counted once), `pair_counts` (DIVERGE / SAME_EDGE / UNMEASURED), `per_culture.*.independent_edges_proven`, `crowding_prior_survival.verdict` | k_eff rising toward what the return target needs; empty clusters falling; top family's share falling; cross-culture pairs moving from UNMEASURED to DIVERGE | Steer judging and certification toward the empty clusters and the independent families. A culture whose pairs come back SAME_EDGE is coverage, not breadth: steer toward cultures with proven DIVERGE edges. |
| D10 | **Machinery gaps to tier-1** | `ranked_gaps` (biggest first), each with a size in numbers | the biggest gaps closing day over day | Reverse-engineer the tier-1 mechanism behind the top gap and build the fix this pass, or park it with evidence and name the thread that owns it. |
| D11 | **Fully wired or it does not count** | per fix: `caller`, `schedule`, `decision_changed`, `artifact`, `artifact_fresh_on_box` | every fix called by the canonical cycle or a scheduled box task, steering a real mine/ingest/judge/forward/allocate decision, with a fresh artifact confirmed on the box after adoption | A report-only module, a shadow module, an unscheduled script or a flag left off is not a fix (III.16). Record it as BLOCKED with the exact reason. The next pass re-verifies that yesterday's fixes still produce. |
| D12 | **No forced or fake work** | `optimal_areas` with their evidence | work goes only where a real gap is measured | An area measured as optimal is marked OPTIMAL with the number and the reason no material gain is available, then left alone. Never manufacture changes, churn or busywork. OPTIMAL is re-measured every pass and holds only while the evidence does. |
| D13 | **Every item fully completed this pass** | `items_noticed`, `items_completed`, `items_blocked` (each with its exact reason), `items_partial`, `gaps_named`, `gaps_named_not_closed` (NEVER JUST NOTICE) | `items_partial` = 0, `items_noticed` = `items_completed` + `items_blocked` + `items_optimal`, and `gaps_named_not_closed` = 0 (a gap at its published measured ceiling counts as closed; a BLOCKED gap carries its exact refusal) | Keep working in the same pass until every noticed item is completed and fully wired, or is BLOCKED with its exact reason. Never end the pass holding a partial, and never defer to the next cycle. |
| D14 | **Every producer maximally broad, unknown-unknowns mined** | per-producer symbol, timeframe and family coverage from `PRODUCER_BREADTH.json`; `producers_total`, `producers_active`, `producers_idle`, `producers_narrow`; `testable_cell_share` (cells the gauntlet can judge / cells emitted); `cluster_occupancy` (risk clusters fed / 15); `unknown_unknown_cells_per_day` | every producer (thousands of them) active and emitting across the full hypothesis-lane universe, symbols x timeframes x families; `testable_cell_share` near 100%; every risk cluster fed; unknown-unknown mining running and emitting daily | Fix every idle, narrow or untestable-emitting producer that same pass, fully wired: widen its symbol, timeframe and family coverage, repair its cell schema so the gauntlet can judge what it emits, restart unknown-unknown mining if it did not emit today. Never narrow or cut a producer. |

**Reality and flow duties (principal, 2026-09-30).** These use the same record, statuses and D11 wiring rule as D1-D14. Each one names the artifact it reads. When that artifact is absent or stale, the duty is UNMEASURED, which counts as MISSED (L1.28a). A step the lane's CLI refused (a tool outside its allowlist) is the same UNMEASURED: `scripts/record_agent_denials.py` writes one `permission_denied` row per refusal to `cro_cycle_ledger.jsonl` and marks the duty that step served MISSED in `TIER1_BREADTH_REVIEW.json`, whatever the pass claimed. Where the artifact's producer is still an open PR, the PR is named: the duty stays UNMEASURED until that PR is merged and its artifact is fresh on the box.

| # | Duty | Named metric (artifact) | Target | Action on a miss |
|---|---|---|---|---|
| D15 | **Judging rate on target** | `mass_screen_per_day`, `full_gauntlet_per_day`, `backlog_net_change_per_day` (`reports/JUDGING_BURNDOWN.json`, `reports/JUDGE_COVERAGE.json`) | net change < 0 every day, and mass-screen plus full-gauntlet volume within 100k-500k cells a day | Add judging capacity through D3. Never delete, skip or down-sample cells to shrink the backlog. |
| D16 | **UNKNOWN verdicts by cause** | `unknown_share` of judged cells over 7 days, split by cause (build, data, timeout, schema, other) (`data/hypotheses/gate_verdict_ledger.jsonl` via `JUDGING_BURNDOWN.json`) | trending down every pass toward < 10% | Fix the largest cause this pass. A cause with no name is itself the defect to fix. |
| D17 | **Box state is fresh in git** | `box_state_age_hours` (`reports/BOX_STATE_FRESHNESS.json` from `scripts/check_box_state_freshness.py`) | < 6h | Find why the box's state push was refused: the pre-push hook, the adoption task, or the sync script. Fix it or record it BLOCKED. Every R mark and six-event items 1, 3, 4 and 5 depend on this. |
| D18 | **No unfed datasets** | `unfed_datasets` across all three uses: direct cells, conditioning and cost/risk (Breadth's unused-dataset rule) | 0 | Wire each unfed dataset into at least one use this pass, following Breadth's rule. |
| D19 | **Paid-substitute coverage** | `paid_sources_substituted / paid_sources_named` and `substitute_match_strength` (correlation or hit rate against the paid series where measurable) | coverage rising; each substitute's strength measured | Find or build a free substitute for the highest-value unsubstituted source. A substitute whose strength is unmeasured counts as uncovered. |
| D20 | **Cross-culture orthogonality** | `culture_orthogonality_verdicts` (Tier S cross-culture test, #113) and `cells_with_known_culture / cells` (`CELL_CULTURE_INDEX.jsonl`) | verdicts rising; known-culture share rising toward 100% of survivors | Backfill culture on unlabelled survivors, and run the cross-culture test on any culture pair that has no verdict. |
| D21 | **No live code drift** | `live_code_hash_mismatch` (`live_door.json`, promoter retirement lands in desktop pass 2) | 0 | Each MISMATCH sleeve is re-certified on its current code or retired by the promoter. Until the promoter reads `live_door.json`, list each one BLOCKED on the pass-2 patch. |
| D22 | **Decay and markout ran** | last run of `decay_monitor` (`data/decay_live.json`) and of `fill_markout` / `markout` (`reports/markout.json`) | both within 24h, and decay checked against the current LIVE roster | Restart the missed leg and fix why it missed its clock. Six-event item 6 cannot be PROVEN while decay is stale. |
| D23 | **Confident kills per day** | `confident_kills_per_day` (kills-per-day ledger, #120; mining `kill_class` = confident_kill) | rising; fail-closed kills are reported separately and never counted | Raise judging on the families with the fewest decisive verdicts. A kill that is fail-closed is a data defect, which D16 handles. |
| D24 | **Credential coverage** | keys missing, with what each one unlocks (`reports/CREDENTIAL_COVERAGE.json` from the hourly `credential_coverage` leg, which lands with #144; until then the secrets-file inventory in `python scripts/check_credentials.py --json`) | 0 missing, or each missing key named with its unlock | Name each missing key and its unlock in one line for the principal, once. Keep working around it with free sources. Never print a key. |
| D25 | **Desktop pass-2 queue age** | `oldest_pass2_item_hours` and `pass2_items_open` (`/mnt/project-files/patches/DESKTOP_PASS2_STATUS.md`) | oldest < 24h | Name the oldest item and what it blocks. The sealed and money-path queue moves only through the desktop pass; never route around it. |
| D26 | **Six-event trend** | `six_events_proven` today against the last 7 passes (`reports/six_event_trace.json`, STEP 4C) | 6 of 6 PROVEN, count never falling | Any fall is the pass's top defect: name the organ that stopped producing. |
| D27 | **Committee health per specialist** | for each of the six committees and each specialist: `calibration`, `false_alarm_rate`, `experiments_saved`, `overlap`, `ablation_value` and `roi` (`reports/COMMITTEE_HEALTH.json`, built by the committees thread; until it exists, UNMEASURED) | every specialist measured on all six; none with ablation value ≤ 0 or rising false alarms | Weak seats are auto-retired: a specialist with ablation value ≤ 0 over 14 days loses its seat, and its missed-growth line is recorded (Rule 1). |
| D28 | **Global coverage tensor** | nominal, distinct and effective-independent coverage, the proven-path covered share and the top missions (`reports/GLOBAL_COVERAGE_TENSOR.json`, hourly; until Breadth publishes it, `reports/COVERAGE_TENSOR.json` from `desks/mt5/research/coverage_tensor.py`) | published within the hour; proven-path covered share never falls | Route the top missions to producers and the judge this pass. Never reclassify a cell to raise the share. |
| D29 | **Deep-forest never-attempted = 0** | `never_attempted` (`reports/BREADTH_MANDATE.json`, `scripts/check_breadth_mandate.py --json`) | 0, every day | Each vector is attempted, or retired LOW_EV with its evidence and a reopen condition. Nothing carries to the next day. |
| D30 | **Stranded ingestion = 0** | stranded ingestion units, each with age (`reports/INGESTION_EXPLOITATION.json`, `desks/mt5/research/ingestion_ledger.py`) | 0 older than 24h | Route every stranded unit to a consumer (direct cells, conditioner or cost/risk input) within 24h. |
| D31 | **Silent organs = 0** | organs SILENT or NOT_SCHEDULED (`reports/SILENT_ORGANS.json` from the hourly `silent_organs` fence, which lands with #157, and `reports/dead_architecture.json` from `scripts/check_dead_architecture.py`; while the scheduler read is UNMEASURED, the duty is UNMEASURED, never green) | 0; any new one is red the pass it appears | Schedule or retire the organ this pass. A new silent organ is the pass's top defect. |
| D32 | **No empty risk clusters** | clusters with no cell minted in the last 24h, of 15, and the six previously empty ones until they hold judged cells (`reports/EMPTY_CLUSTER_FORCER.json`, `desks/mt5/research/empty_cluster_forcer.py`) | 15 of 15 minted every 24h; the six tracked clusters reach judged cells | Force cells into each empty cluster through the forcer this pass. An empty cluster with no producer is a producer defect for Breadth. |
| D33 | **Source ROI** | per source: funnel (fetched → cells → judged → survivors), marginal information gain per compute hour and incremental k_eff (`reports/SOURCE_ROI.json`, Breadth; until it exists, UNMEASURED) | every source publishes all three | Auto-retire redirects budget away from the weakest sources and never deletes a source. A source with no funnel is the defect. |
| D34 | **Backpressure** | `judged_per_day` against `created_per_day` (`reports/GAUNTLET_BACKPRESSURE.json`, `desks/mt5/research/gauntlet_backpressure.py`) | judged ≥ created, every day | Raise judge capacity (backpressure goes to the judge only). Never throttle onboarding, mining or research generation. |
| D35 | **GitHub resident miner** | delta cursors advanced since the last pass, `repos_mined_per_day`, `cells_extracted_per_day` (`reports/GITHUB_RESIDENT_MINER.json`, owned by "Mine the EliteQuant list"; until it exists, UNMEASURED) | cursors advance every day; repos and cells per day rising | Restart a stalled cursor and fix why it stalled. A repo mined with no cells extracted is an extraction defect. |
| D36 | **QuantConnect, WorldQuant and fund civilizations** | lane status per civilization under the 30-day EVALUATED rule: at least one EVALUATED verdict in the last 30 days (`reports/CIVILIZATION_LANES.json`, owned by "QuantConnect, WorldQuant and fund miners"; until it exists, UNMEASURED) | every lane ACTIVE | Revive any lane with no EVALUATED verdict in 30 days: name its blocker and fix it this pass. |
| D37 | **Institutional coverage per jurisdiction** | coverage over jurisdiction × source class, with its status distribution and the age of each latent actor state (`reports/INSTITUTIONAL_COVERAGE.json`, owned by "Institutional flow in country packs"; `desks/mt5/research/institutional_footprint.py` (hourly leg `institutional_footprint`) writes it and supplies the actor states, each with `age_hours` and `status`, a state past 7 days reading UNMEASURED; `reports/INSTITUTIONAL_STATE.json` carries the regimes; until the leg has run on the box, UNMEASURED) | no empty jurisdiction × class cell without a named reason; every latent state < 7 days old | Source the largest uncovered jurisdiction × class this pass, and refresh the stalest actor state. |
| D38 | **Judge efficiency** | prewarm seconds per attempt, shards completed over shards launched, verdicts committed per attempt, build failures, and worker peak memory against the declared model, prewarm warm rate (`warm_rate`), cold-build seconds (`cold_build_seconds`) and failed builds by cause (`build_failures_by_cause`) (`reports/JUDGING_THROUGHPUT.json`, `reports/JUDGING_BURNDOWN.json`, `reports/JUDGE_COVERAGE.json`; `desks/mt5/scripts/run_sharded_gauntlet.py` is the sharded launcher; a counter the launcher does not yet publish reads UNMEASURED) | no all-or-nothing batch and no repeated prewarm; every shard commits its verdicts resumably; completed / launched ≥ 0.95; a verdict reaches its certificate and forward clock the same day | Fix the worst stage first (prewarm, shard loss or memory), make the missing counter publish, and re-run the failed shards from their checkpoint, never the batch. |
| D39 | **Effective breadth, not saturation** | N_CERT against N_EFFECTIVE_CERT, economic clusters, independent forward and live streams, stress and tail k_eff, saturated against empty clusters, duplicate compute share per producer, Δk_eff and quality gain per compute-hour, and the breadth-debt queue (`reports/EFFECTIVE_BREADTH.json`, `reports/JUDGE_COVERAGE.json`; `reports/GLOBAL_COVERAGE_TENSOR.json` for clusters) | N_EFFECTIVE_CERT and stress k_eff rise pass over pass; duplicate compute share falls; Δk_eff per compute-hour > 0 | Move compute from the most saturated cluster to the breadth-debt queue's head. Evolve the anti-saturation law from this evidence; breadth steers compute and never decides what passes. |
| D40 | **Timeframe and session breadth** | discovery and certificate share by M1, M5, M15, M30, H1, H4, D1 and event clock, and by session (`reports/TIMEFRAME_COVERAGE.json` from `desks/mt5/scripts/check_timeframe_coverage.py`, `reports/SESSION_ALLOCATION.json` from `desks/mt5/research/session_allocator.py`) | no single clock above half of discoveries or certificates; an H1-dominated pass is MISSED | Route the next producer batch to the thinnest clock and session, and convert their declared selectors into executable cells. |
| D41 | **Nothing is a museum** | datasets, models and organs with no verified consumer or no resident 24/7 worker (`reports/dead_architecture.json` from `scripts/check_dead_architecture.py`, `reports/SILENT_ORGANS.json`, and the unfed-dataset count from D18) | 0 | Wire each one to a consumer and a clock this pass, or retire it with its evidence. |
| D42 | **Ontology never closed** | new information classes, sources, actors, mechanisms, representations and methods found since the last pass, each with its stage: PIT, gauntlet, forward, ROI (`reports/UNSEEN_FRONTIER.json` from `desks/mt5/research/unseen_frontier.py`, `reports/FRONTIER_INTELLIGENCE.json`, `reports/INSTITUTIONAL_COVERAGE.json` future-source watcher) | at least one new item every day, each advancing a stage | Open the largest unsampled ground or class this pass and push its first item to PIT. |
| D43 | **Allocator integrity** | solver optimality gap, pending events lost, scenario-cache fingerprint freshness, two-sided calibrated decay, hard-coded symbol or bracket rules, gateway-consumed decision trace, event-to-decision p95 (`reports/ALLOCATOR_PROOF.json`, `reports/ALLOCATOR_LIVENESS.json`, `reports/pf_allocation.json`) | gap reported, 0 lost events, fresh fingerprint, no hard-coded rule, trace consumed, p95 measured | Allocator and gateway code is money path: BLOCKED to the desktop "Growth allocator overhaul" session. Write the finding there with its evidence; never patch it from this lane. |
| D44 | **Self-evolution** | evidence-backed machinery improvements landed this pass, each with its before and after metric (`machinery_improvements` in `reports/TIER1_BREADTH_REVIEW.json`, this pass) | ≥ 1 every pass, never by weakening a gate | Pick the measured worst bottleneck in D38-D43 and land one improvement with its after-metric before the pass ends. |

**The duty artifacts are measured by the launcher, not by the pass (2026-10-06).** `scripts/check_cro_duties.py` reads every artifact a row above names, on the host the pass runs on, and writes `desks/mt5/reports/CRO_DUTIES.json` before the agent starts; the counters each duty must carry are listed in `docs/cro/cro_duty_metrics.json`. An artifact absent, unreadable or older than its window, or a counter no fresh artifact carries, is UNMEASURED and counts as MISSED. After the pass it re-runs with `--review`, and any duty the pass scored MET or OPTIMAL that it cannot back is rewritten MISSED, with the claim kept under `status_claimed`. A new duty row is checked the moment it names its artifact.

Standing rules for every duty: never cut mining, ingestion or research generation, and never lower a validation gate to raise a number. The duty work competes in STEP 7 and usually wins when capital-path integrity is clean.

Write the table, the duty statuses, the tier verdict, the ranked gaps, the change since the last pass and each fix's wiring proof to `desks/mt5/reports/TIER1_BREADTH_REVIEW.json` (append to its `history` array). Carry `tier_verdict`, `k_eff`, `top_breadth_gaps`, `duties_missed`, `gaps_named` and `gaps_closed` in the cycle ledger row; each `gaps_closed` entry names its fix commit, its wiring proof and its after-metric.

**PASS QUESTIONS (ARCH-30, principal 2026-10-06; live in the noon routine 2026-10-07).** Every pass answers Q1-Q7 after the duties. Each answer cites box evidence in a form the checker can resolve: `<artifact path>@<ISO timestamp>` for a file on the box, `ledger:<row id>` for a `cro_cycle_ledger.jsonl` row (`<lane>-<date>`) or work item, or a commit sha. Any other citation reads MISSED (`evidence_unresolvable`); the sweep items below follow the same rule. An answer that is UNMEASURED or cites nothing counts as MISSED (L1.28a). Write the answers to `desks/mt5/reports/TIER1_BREADTH_REVIEW.json` under `pass_questions`, keyed `Q1`..`Q7`, each with `answer`, `evidence` and `status` (ANSWERED / MISSED). Carry `pass_questions_missed` in the cycle ledger row.

| Q | Question | What counts as an answer |
|---|---|---|
| Q1 | **What is the best work waiting?** | The highest-value item not yet started, ranked by expected ΔE[log W], with the artifact that ranks it. It competes in STEP 7. |
| Q2 | **Which producers added distinct validated information?** | Per producer, the gain in k_eff or in independent cluster count from what it validated since the last pass. Cell counts and candidate counts do not count. A producer with zero gain is named. |
| Q3 | **What opportunities were missed?** | Named trades, cells or sources that a working desk would have taken this window, from the missed-growth ledger and the missed-trade archaeologist, each with its cause. |
| Q4 | **Did the allocator beat its baselines?** | The allocator's book against equal-risk, inverse-vol and best-single-sleeve baselines, measured on the executable book after lot rounding and costs. A loss to any baseline goes to the desktop "Growth allocator" session with its evidence. Allocator code is money path and is never patched from this lane. |
| Q5 | **What did stale information, costs or defects cost?** | The measured loss, or the forgone E[log W], from stale inputs, cost slippage against the model and defects since the last pass, each with its cause. |
| Q6 | **Which components can be removed?** | Components with no consumer, no measured contribution, or a duplicate of another, each with its evidence (D41's dead-architecture report). Removal still follows the retirement law: a named falsifier, never silence. |
| Q7 | **What is the most valuable new capability?** | The one capability (a source, method, actor model or organ) whose addition the evidence ranks first, with what it would unlock. It competes in STEP 7. |

**JUDGING BOTTLENECK SWEEP (principal 2026-10-07; live in the noon routine).** Every pass runs sweep items (a) to (g) and records each one under `judging_sweep` in `TIER1_BREADTH_REVIEW.json`, keyed `a`..`g`, each with `finding`, `evidence` and `status`. The ledger row carries `judging_sweep` too, as the list of missed items. An item that is UNMEASURED or cites no evidence counts as MISSED. `scripts/check_cro_duties.py --review` enforces this alongside the pass questions. Baseline (2026-10-07): 1,389,434 cells unjudged and growing by about 90k a day, 0 first rulings per hour, 1-2 busy judge cores, and 0 cells warmed in 3,662s.

| Item | Sweep | Evidence |
|---|---|---|
| a | **Rulings rate**: first rulings per hour against cells created per hour | `reports/JUDGING_BURNDOWN.json`, no older than 2h (D3) |
| b | **Never-fire share**: the share of UNKNOWN that is never-fire or too-rare, and whether every requeued cell reached a terminal verdict | `reports/JUDGE_COVERAGE.json` (D4) |
| c | **Prewarm and cold builds**: warm rate, cold-build seconds, failed builds by cause | `reports/JUDGING_THROUGHPUT.json`, `reports/JUDGING_QUEUE_AGE.json` (D38) |
| d | **Busy cores against CPU and RAM consumers**: busy judge cores against planned workers, and what else holds the box's CPU and RAM | `stall_watch.json` and the judge's worker census |
| e | **Fences**: the `coverage_drain` and `judge_coverage` fences pass | their fence output this pass |
| f | **Failed task changes**: any `schtasks /Change` that failed, with its error | the task log on the box |
| g | **swap_cost fails closed**: a missing or stale swap cost blocks the cell, never prices it at zero | `reports/BROKER_SWAPS_FRESHNESS.json` and the swap_cost guard |

Act on the worst item in the same pass. Backpressure goes to the judge only: never throttle onboarding, mining or research generation, and never lower a gate.

## STEP 4C — SIX-EVENT REALITY TRACE (principal's standing test, 2026-09-30)

The desk is real only if six events have happened, each provable from recorded artifacts by ids and timestamps, never by code or documents that claim them:

1. one source mined end-to-end into one cell;
2. one cell preregistered with a sealed contract before its judgement;
3. one gauntlet verdict with its rejection reason logged;
4. one survivor forward-observed over real wall-clock time;
5. one live allocation with a reconciled fill;
6. one decay detection that retired something (and was not later voided).

The `six_event_trace` step of `daily_cycle` writes `desks/mt5/reports/six_event_trace.json` once a UTC day. Each pass, read it on the box, or re-run it with `python -m libs.ops.six_event_trace`. Each event reads PROVEN (latest instance within 7 days), STALE (older) or MISSING (never recorded).

Every STALE or MISSING event is a defect in the organ that should produce it, and it competes in STEP 7. Name the organ, fix it this pass or record it BLOCKED with the exact reason, and never mark an event PROVEN from anything but the trace. Carry `six_events` (the six verdicts) in the cycle ledger row.

---

## STEP 5 — PREREGISTRATION / EVIDENCE-INTEGRITY CHECK

For new serious candidates or material validation changes verify:

- preregistration exists before decisive evidence;
- hypothesis/version is frozen;
- data cutoff is recorded;
- acceptance criteria are fixed;
- multiplicity/adaptive lineage is preserved;
- forward requirements are fixed;
- rule changes are prospective;
- failed trials are retained.

If the current evaluator cannot prove this, evidence integrity becomes a binding defect.

Never lower validation because certificate production is slow.

---

## STEP 6 — FAILURE / BLIND-SPOT CHECK

Search for things that should have happened but did not.

Examples:

- expected job absent;
- producer output missing;
- consumer receipt absent;
- evaluation never started;
- forward clock stale;
- promotion state inconsistent;
- allocator ignoring eligible sleeve;
- valid signal disappearing;
- broker reconciliation missing;
- watchdog stale;
- deployment SHA inconsistent.

If a real failure escaped detection, fix both:

1. the failure;
2. the missing detector/invariant/probe.

---

## STEP 7 — CHOOSE THE HIGHEST-VALUE ACTIONABLE ITEM

Rank material work by:

- capital/evidence-integrity impact;
- expected contribution to retained net log wealth;
- bottleneck impact;
- research information value;
- opportunity cost;
- implementation risk;
- dependencies;
- effort;
- authorized capacity.

Preserve required exploration.

Do not choose work merely because it is easy.

Do not choose work merely because it sounds sophisticated.

Select the highest-value feasible item.

---

## STEP 8 — IMPLEMENT, CHECK, RELEASE, MEASURE

For the selected item:

OBSERVE  
→ VERIFY  
→ ROOT CAUSE  
→ MEASURE GAP  
→ IMPLEMENT  
→ TEST  
→ INDEPENDENT CHECK  
→ RESOLVE CONFLICTS  
→ CANONICAL INTEGRATION  
→ RELEASE/ADOPT  
→ PROVE DOWNSTREAM CONSUMPTION  
→ MEASURE AFTER STATE  
→ MEASURE REMAINING GAP.

If the remaining material improvement still outranks competing work, continue.

Otherwise disposition as:

MAXIMIZED_AND_VERIFIED  
NO_FURTHER_MATERIAL_GAIN_WITH_EVIDENCE  
RETIRED_OR_PARKED_WITH_EVIDENCE  
BLOCKED_BY_EXACT_EXTERNAL_CONSTRAINT  
SUPERSEDED_BY_BETTER_VERIFIED_SOLUTION

Record reopen triggers for parked/retired items.

---

## STEP 9 — VERIFY 24/7 RESEARCH CONTINUES AFTER THIS RUN

Confirm the canonical supervisor can continue eligible:

- acquisition;
- mining;
- generation;
- reconstruction;
- conversion;
- evaluation;
- forward observation;
- sandbox;
- research-method work

without waiting for the next CRO run.

Do not create another scheduler.

Provider outage must not disable deterministic trading protection/reconciliation.

---

## STEP 10 — LEAVE DURABLE CANONICAL STATE

Before finishing:

- no material discovered issue is silently lost;
- unfinished work is checkpointed;
- owner/state/next action are explicit;
- parked/retired work has reopen triggers;
- current binding constraint is recorded;
- release/deployment identity is recorded;
- research workers continue according to canonical scheduling.

---

# COMPACT REPORT

Return only:

1. **Release / deployment / account identity**
2. **Capital-path status**
3. **Material defects found**
4. **Material work completed + proof**
5. **Previous-cycle changes verified**
6. **Research funnel binding constraint**
6b. **Tier verdict + breadth: maxed out? (measured table vs tier-1 benchmarks, ranked gaps, what this pass did about them)**
7. **Gauntlet / forward / promotion material changes**
8. **Live execution / reconciliation material changes**
9. **Parked / retired / reopened work**
10. **External/authorization blockers**
11. **Current highest-value next action**

Use canonical artifact pointers for detailed evidence.

Do not dump the entire institution into the human report.

Do not claim 100% completion of an open-ended system.
