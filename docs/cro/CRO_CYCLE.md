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

**Minimum table, reproduced every pass with fresh numbers** (columns: Measure | Us, live box | Yesterday | Tier-1, public estimate | Gap). The 2026-09-30 baseline is shown; add any row that limits breadth:

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

**Targets driven every day, none ever treated as exhausted:** dataset hunting and ingestion at the scale of thousands of valuable world datasets, not ten; every alt platform and forest vector attempted and yielding; judging yield toward 100% (UNKNOWN and build/data failures toward zero); judging capacity above creation so the backlog shrinks; mining toward millions of hypotheses a day; certificates spread into empty risk clusters so k_eff rises; every certificate reaching forward; live breadth across many symbols; tier-1 machinery architecture reverse-engineered and its biggest gaps closed.

Then:

- Rank what holds breadth down, biggest first.
- **Never assume the machinery is at its peak or exhausted.** "Maxed out" or "exhausted" needs per-axis evidence (L1.51); absent that, the answer is NO.
- Act on the biggest gaps in the same pass: build, test and merge a fix, or park it with evidence naming the thread that owns it. The gap work competes in STEP 7 like any other item and usually wins when capital-path integrity is clean.
- Never cut mining, ingestion or research generation, and never lower a validation gate to raise throughput.
- Write the measurements, the tier verdict, the ranked gaps and the change since the last pass to `desks/mt5/reports/TIER1_BREADTH_REVIEW.json` (append to its `history` array) and carry `tier_verdict`, `k_eff` and `top_breadth_gaps` in the cycle ledger row.

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
