# DEEP COLD AUDIT — RESEARCH-ENGINE — 2026-07-31

STATUS: COMPLETE

Auditor: weekly deep cold audit, research-engine seat, 2026-07-31.
Prior art: `20260730_research-engine.md` (31 findings R-1..R-31, 13 opportunities O-1..O-13, completed 17:11Z 07-30).
This sweep is a **delta-and-depth audit**: (A) verify from artifacts which of yesterday's findings moved in the ~34h since;
(B) audit the research-engine organs BUILT AFTER yesterday's audit (strategic_director, fusion_search, label_factory,
run_cadence, intelligence-cycle rewrite) which have never been examined; (C) open seams yesterday never touched
(research friction/turnaround measurement, prompt versioning, agenda/state stores, cross-domain synthesis).
Method: OUTCOME-NOT-CONFIG — every claim carries its command + output.

## SCORES

- current_capability_pct: **35%** — screening/discipline organs are strong (fusion refusal, §33 priors, memory-writing), but autonomous
  generation is 0/day for 7 days, the review lane (panel/director/kimi) is 402-dead, memory is unread at generation time, and the nightly
  self-assessment reads a paper world. Down 5pts vs yesterday's implied level on the regression findings (E-7, E-5) despite the activation
  layer landing.
- practical_ceiling_estimate: **85%** with current staff/compute — nothing found requires new technology; every rank-1..6 item is wiring.
- ceiling_gap: **50pts**, of which ~30 are closable in ≤1 week (ranks 1-6 are hours-to-a-day each).
- opportunity_cost_1y: at tested=0 and a dead external-review lane, autonomous discovery contributes ~nothing for a year — the desk pays
  for 11,805 dormant lines (self-measured, E-6) and a growing findings pile at 17% implementation. Concretely: every validated-alpha path
  the factory/LLM/panel lane was built to produce, forgone; plus the compounding of decisions (E-12/E-13) made on wrong inputs.
- confidence: **0.85** on individual findings (each command-cited, re-measured today, not carried over); **0.55** on the ranking.
- unknown_unknown_score: **0.45** — the cron union's side effects, the unread-artifact consumers, and first-live-fire LLM behaviour are
  unprobed regions with known instances of surprise.
- info_gain_if_investigated: highest for T-5 (first funded review run) and T-7 (reader coverage) — both cheap, both open genuinely unknown
  territory.
- expected_alpha_contribution: indirect but real — restoring generation + honest steering (E-13) + memory-read (rank 3) raises the rate the
  Stage-A screen is fed; zero direct alpha claims made here (this seat has no promotion authority).
- expected_compounding_contribution: **high** — ranks 1-3 are multipliers (every future organ inherits a deduped scheduler, a funded/fallback
  LLM lane, and a memory that blocks re-digging dead ground).
- CEILING EXPANSION: the ceiling is ORGANIZATIONAL, not technological — defined by (a) disposition throughput (17%) and (b) one unfunded
  credit line. Both are movable this week; if both move, 85% is itself low: the honest ceiling with a funded review lane + reading memory is
  ~92%, limited then by calendar-time forward evidence, which no engineering buys.

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

1. **The multiplicity discipline survived being encoded into a new organ.** `data/fusion_search.json` → `status: REFUSED, effective_n_trials: 0`
   with per-axis exclusion reasons carrying the original single-axis verdicts (E-9). The desk's sharpest law (earn breadth before combining)
   now runs as a precondition, not prose. Likewise `fusion_engine`: "0/5 combinations beat their best component" — negatives reported as such.
2. **The research-memory DUTY is being exercised.** `sqlite3 data/sor_research.sqlite "select substr(created_at,1,10),count(*) from
   research_memory group by 1"` → 160 rows, 16 on 07-30 alone, including refutations with `predecessor_id` lineage (E-15). The desk writes
   its memory; the remaining defect is reading it at generation time.
3. **Literature finds are §33-governed.** `max_audit.py:2686` `_DIG_DOCS` includes `feed_inbox.md` + `literature_coverage.md`; the feed ran
   07-30 08:15 (`stat data/research_feed.json`). Scope law correctly applied (E-19).
4. **The activation layer exists and runs on schedule.** `web/intelligence_cycle.json` updated 2026-07-31T00:51Z, 13 capabilities exercised,
   NO-INPUT as a first-class verdict (E-6/E-21) — yesterday's greenfield prescription (activate, don't rebuild) was implemented in one day.
5. **§33 generation priors are measured, not asserted.** `data/mine_generation_priors.json` (01:56 today): conversion_rate 0.5,
   median_latency 0.25d for the one tracked class, favour/starve lists live.
6. **The GAP register remains the one process organ that drives work** (yesterday's R-31; today rows 88-90 show live re-ranking, closures,
   and a fixed-verified escalation-channel repair). Not re-proved here; no contrary evidence found.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

- **Who consumes the new intelligence artifacts.** No reader identified for `web/intelligence_cycle.json` or `data/strategic_director.json`
  (built yesterday). If none lands, the R-8 write-only shape has recurred one level up. → probe: `grep -rn "intelligence_cycle.json\|strategic_director.json" scripts/ libs/ app/ web/ --include="*.py" --include="*.html"`.
- **Whether the doubled */5 venue-divergence sampling has already contaminated the gap-#19 breaker-band calibration series** (E-7): two
  lockless writers since ~07-30. Needs a timestamp-spacing histogram over the divergence artifact before/after 07-30.
- **Whether the 95-line cron union holds MORE colliding pairs** than the 6 verified in E-7 — I diffed the obvious research organs only.
- **Live-fire behaviour of the strategic director and the 13-seat panel** — never observed (402 since inception/Jul-21). First funded run is
  genuinely unknown territory, including whether `openai/gpt-9` respects the JSON contract.
- **Which of the 7 `sor_research` reader files touch the `research_memory` TABLE** (vs orders/fills/campaigns) — reader coverage of the real
  memory store is unmeasured (E-15).
- **Whether "the price family is dead" survives the fixed per-candidate gate** — the 420 have still never been re-scored (E-3, cross-ref
  20260731_alpha-discovery). Until that runs, the factory's nightly banner (E-22) is an artifact-backed claim.
- **Whether the 8 datasets with >1y history and NO reader** (data_registry, E-6 output) contain screenable axes — idle data is a defect
  (L1.8); nobody has looked.
- **Whether the two 02:00 daily-cycle twins have already produced interleaved/corrupt cycle-log entries** — `data/` state predates the check
  I could design read-only.

## 3. WHAT COULD MATTER MOST (ranked opportunities; impact × confidence / (cost × maintenance); ⚡ = compounding multiplier)

1. ⚡ **Build the $0 LLM fallback lane + keep the $120 page alive** (E-14, E-21). One unfunded line idles 6+ organs including the desk's only
   non-Claude reviewer and the unknown-unknown hunter, 10 days and growing. Desk-side (no spend, no Tier-3): route dry-runs/cheap seats
   through free tiers with the §13 licence gate; re-page the top-up with its measured blast radius. Cost ~1 day; unblocks an entire review
   lane. THE constraint on external adversarial validation.
2. ⚡ **De-duplicate the scheduler** (E-7). Replace-not-append in the installer; one line per organ; single lock namespace. Removes same-minute
   races on `research_state.json`, halves waste on 2 cores, stops the divergence-series contamination. Cost hours; prevents a class, not an
   instance (the R0048 lesson finishing its migration from brains to cron).
3. ⚡ **Wire the novelty gate to the TF-IDF retriever + one canonical prior store** (E-1/E-2, R0004 — day 5 open, yesterday's rank 1,
   unmoved). Every generation cycle without it re-burns multiplicity on dead ground. The parts all exist in-repo; ~1 day.
4. **Make nonzero-exit = ERROR in `_subprocess_cap` and fix `label_factory.py:296` (.iloc / reset_index) + regression test with a duplicated
   index** (E-6/E-8). Two one-liners; restores truthful organ status and turns the label factory from crash-reported-as-data-gap into a
   producer.
5. **Point the research layer at NAV-chain equity** (E-12). One loader swap in `daily_research_cycle.py:161` (+ mark paper sleeves
   excluded); ends the third source of truth before another organ is built on it.
6. **Wire `research_priority` to the real family-kill record or label it DATA-FREE** (E-13). The search-steering organ must not rank
   constants while reporting ACTIVE.
7. **Raise the disposition drain rate — the standing bottleneck** (E-4). 33 open (+6 net in 34h) at 17% implementation. Every finding above
   is worthless if it just joins the pile; yesterday's O-5 stands, now with worse numbers.
8. **Schedule-or-retire autonomous axis generation; refresh or terminal-mark `research_agenda.json`** (E-16). The generation layer currently
   exists only when a human session runs.
9. **Give literature a conversion step** (E-19, yesterday's O-13): one mechanism-priored paper → axis-screen path per week would beat 83
   papers at zero screens forever.
10. **Populate-or-retire the empty audit spine** (E-15, R0008): trials_ledger/research_runs/alpha_registry at 0 rows are unvoted complexity
    per L1.12 — either the duty writes there or the tables go.

## 4. WHAT WE TEST NEXT (concrete experiments, success criteria, retirement conditions)

- **T-1 (today 05:45Z, free):** verify first cron fires of the new organs: `ls -la data/data_assets.json data/cro_ai_logs/{data_registry,label_factory,fusion_search,strategic_director}.log`.
  SUCCESS: data_assets.json exists (director's dossier self-heals next run); label_factory.log shows the E-8 crash (then fix per rank 4).
  FAILURE MODE: no logs → manifest lines not actually installed → E-7 investigation widens.
- **T-2 (today 08:25Z):** `graveyard_resurrect` first fire: log exists AND `data/graveyard_resurrection_queue.json` mtime advances AND a
  reader is named for the queue (else it remains write-only with a cron line — config, not outcome).
- **T-3 (after rank-2 fix):** `crontab -l | grep -vE '^#|^$' | sort | uniq -d` → empty; venue-divergence inter-sample spacing returns to
  ~300s median. RETIRE the check once a scheduler-lint runs in CI.
- **T-4 (after rank-3 fix):** recall test — feed all graveyard titles through the new gate; SUCCESS ≥90% flagged as prior art (yesterday's
  measured baseline: 0/43). Pre-register the threshold; a gate that flags 100% of NOVEL controls too is the opposite defect (gate-optimality).
- **T-5 (on funding):** first live panel/director run — `data/panel_verdicts.jsonl` mtime advances; director output validates against its
  JSON contract; log the first-run failure modes (unknown territory per §2).
- **T-6 (after rank-5 fix):** `research_state.json .deployed.equity` within 1% of the NAV attestation head; `deployed_sharpe` either real-book
  or absent.
- **T-7 (anytime, read-only):** reader-coverage probe for `intelligence_cycle.json`/`strategic_director.json`/research_memory TABLE (closes
  three §2 unknowns in one grep session).

## PROACTIVE BATTERY (moves run, and what each produced)

1. Contingency-before-failure → E-14/E-21: the LLM lane has NO named replacement; single paid provider. Produced rank-1.
2. Adjacency → E-7 (R0048's lock-split shape found again in cron); E-6/E-8 (unit-tested-≠-runs found again on real data); E-12 (two-source
   equity found a THIRD source).
3. Config-vs-outcome → whole report method; sharpest instances E-13 (ACTIVE ranking of constants), E-18 (collector with no artifact).
4. Regression sweep → the 07-30 deploy night made scheduling WORSE (E-7) and doctrine 39% heavier (E-5) while genuinely activating 9 organs.
5. Cost inversion → E-14: before any paid-proxy argument, free-tier model lanes exist and are unexploited (licence gate applies).
6. Generalise-the-rule → E-6's lesson (exit codes are first-class) applies to `organ_catchup.py:68,78` and `rollback_guard.py:82` (same
   returncode→bool truncation; noted, unverified severity).
7. Autonomy check → graveyard_resurrect has a schedule but recovery has never been SEEN (first fire 08:21 today; T-2).
8. Negative space → E-16 (no standing axis generation), E-18 (no non-English text collection artifact), E-15 (empty audit spine),
   translation still 0 lines.
9. Scope-the-negative-result → 402 is a ROUTE failure, not a capability failure (harnesses intact by their own logs); E-14.
10. Ratchet check → no floor artifact exists for implementation-rate (17%) or doctrine size (53,435B vs 16k guard — a guard that does not
    bite, R0002 scheduled). Proposed: both become ratchet metrics the day they are next measured.

## §33/§35 NOTE (read-only run — rows OWED by the next live cycle)

This audit ran read-only per its charter; the following owe ledger/register rows: E-6 (+E-8) exit-code conflation + label crash; E-7
scheduler double-install; E-12 third equity source; E-13 data-free ranking; E-16 agenda fossil / unscheduled generation; E-18 absent KR
collector artifact; E-22 banner-on-broken-instrument. E-1..E-5, E-14, E-15, E-17, E-19, E-20 map to EXISTING rows (R0004, R0002, R0008,
R0030, R0056, register row 89) — dispose those, do not duplicate them.

## FINDINGS LOG (command-cited; perspectives tagged)

### PART A — DELTA ON YESTERDAY'S 31 FINDINGS (what moved in ~34h, verified from artifacts)

### E-1 [INTERNAL, delta] The #1-ranked fix (novelty gate → TF-IDF) is UNTOUCHED; the gate is byte-identical since 07-23
`stat -c '%y' libs/alpha_factory/hypothesis_novelty.py` → `2026-07-23 15:40:15` (before yesterday's audit; before R0004 was even rowed).
`grep -n "tfidf\|TfidfVectorizer\|idf\|cosine" libs/alpha_factory/hypothesis_novelty.py` → **empty**.
R0004 ("wire hypothesis_novelty into live generation + ONE canonical machine-readable graveyard") status: **open** (rowed 07-26, now day 5).
Yesterday's O-1 established: 0/43 recall on verbatim graveyard entries, threshold mathematically unreachable for 70–94% of pairs, and the
strictly-better IDF-weighted cosine already exists at `scripts/knowledge_engine.py:80-99`. Nothing moved. Every day this stands, every generator
re-runs dead ground invisibly (yesterday's R-10 measured 4 netflow experiments re-run at IC identical to 4 decimals, scored 97.3% "novel").

### E-2 [INTERNAL, delta] Research memory is still write-only — the three reader-zero stores still have exactly one code reference each (the writer), and the phantom `research_memory.db` still has 4 production readers
`grep -rn "graveyard_resurrection_queue\|negative_knowledge.json\|knowledge_engine.json" --include="*.py" scripts/ libs/ | grep -v test` →
exactly 3 hits: `graveyard_resurrect.py:22` (writer), `knowledge_engine.py:47` (writer), `negative_knowledge.py:31` (writer). Zero readers.
`grep -rn "research_memory.db" --include="*.py" scripts/ libs/` → still 4 refs (`run_promotion_queue.py:47`, `run_generation_diversity.py:46`,
`max_audit.py:1467,1665`) pointing at a file that has never existed (real store: `data/sor_research.sqlite`). All four silently degrade to empty.
One genuine delta: `graveyard_resurrect.py` now HAS a scheduler line (live `crontab -l` line: `21 8 * * * … graveyard_resurrect.py`), but
`data/cro_ai_logs/graveyard_resurrect.log` does not exist yet — first fire is 08:21Z today, after this audit. Verify-condition logged in §4.

### E-3 [INTERNAL, delta] Generation is now at DAY 7 of tested=0 — and the two factory lines feeding it are DOUBLE-SCHEDULED
`tail data/cro_ai_logs/crypto_factory_cron.log` (run of 2026-07-31T01:30Z): H8 `tested=0 … skipped_dup=140`, D1 `tested=0 … skipped_dup=420`,
`info_bits/exp=0.2345` — still the algebraic constant (-log2(0.85)) yesterday's R-2 proved is emitted for 1244/1244 rows. The 420 price
candidates have still never been re-scored under the fixed per-candidate gate (cross-confirmed by today's alpha-discovery sweep).
The factory also runs TWICE daily now — see E-7.

### E-4 [INTERNAL, delta] The remediation bottleneck got WORSE, in numbers: 23 rows added vs 6 implemented in ~34h; open grew 27→33
`python -c` over `docs/research/recommendation_ledger.json` → total 69 (yesterday 46), status Counter: **open 33, scheduled 20, implemented 12,
rejected 4**. Implementation rate 12/69 = 17% (yesterday 6/46 = 13%). The absolute open pile GREW by 6 despite 6 implementations — diagnosis
continues to outrun remediation ~4:1. Yesterday's O-5 ("dispose the 27 before generating one more finding") was not only unmet; the desk added
23 new rows. This audit itself adds to the pile — the marginal value of finding #70 is near zero until the drain rate rises (see §3 rank 1).

### E-5 [INTERNAL, delta] Doctrine bloat: +39% in one day, AFTER being flagged two audits running
`stat -c '%s' ops/principal_doctrine.txt` → **53,435 bytes** (yesterday's R-26 measured 38.3k, itself +42% after the defect was first raised;
R0002 "consolidate doctrine vs 16k guard" sits status=scheduled). The doctrine prepended to every organ call has tripled past its own guard.
Every LLM organ pays this tax on every call; at 3 CRO fires + 8-seat sweeps + miners daily, ~50k chars × dozens of calls/day of pure prefix.

### PART B — THE FIVE ORGANS BUILT AFTER YESTERDAY'S AUDIT (never before examined)

### E-6 [INTERNAL, NEW ORGAN] `run_intelligence_cycle.py` activates 9 dormant capabilities — genuinely good — but its `_subprocess_cap` maps EVERY nonzero exit to "NO-INPUT", so a crashing organ reads as a benign data gap
`scripts/run_intelligence_cycle.py:208`: `"ACTIVE" if p.returncode == 0 else "NO-INPUT"` — only timeout/missing-file produce ERROR, and
`main()` returns 0 unless ERROR. Proof it already bit, on day one: `web/intelligence_cycle.json` (updated 2026-07-31T00:51Z) reports
`label_factory NO-INPUT — scripts/build_labels.py exit=1: ValueError: operands could not be broadcast together with shapes (3019,) (303,)`.
That is a CRASH classified as "needs data". The organ's own docstring says "NO-INPUT is a first-class verdict, never a silent skip" — but a
raise-every-day subprocess will never fail this organ and never page anyone. This is the self-greening-guard shape (the desk's prime quarry)
rebuilt into its newest organ 8 hours after an audit documented the pattern. Counts today: 9 ACTIVE / 4 NO-INPUT, one of the 4 a live crash.

### E-7 [INTERNAL, systemic, NEW] The self-installing scheduler APPENDED the manifest to the live crontab instead of replacing it: 95 active lines, ≥6 research organs double-scheduled under DIFFERENT lock files
`crontab -l | grep -vE "^#|^$" | wc -l` → **95**. Verified duplicates (legacy block + manifest block, mutually invisible locks):
- `watchdog.py`: `*/3` with `/tmp/watchdog.lock` AND `*/3` with **no lock** (different logs) — two watchdogs, overlap possible.
- `run_venue_divergence_shadow.py`: `*/5` twice, both lockless — the divergence series now samples at 2× its assumed cadence (data
  contamination vector for the gap-#19 breaker band calibration).
- crypto factory: `30 3 * * *` (`/tmp/crypto_factory.lock`) AND `30 1 * * *` (`data/.cron_crypto_factory.lock`) — log proves BOTH fire
  (`=== done 2026-07-30T03:30:24Z ===` and `=== done 2026-07-31T01:30:32Z ===`). Full pipeline 2×/day on a 2-core box.
- `daily_research_cycle.py`: TWO entries at `0 2 * * *` — one pgrep-guarded, one flock on `data/.cron_daily_cycle.lock`. Same-minute race;
  pgrep check-then-act vs flock in a different namespace = the EXACT mutual-exclusion-split root-caused as R0048/brain_mutex on 07-30,
  reintroduced by the deploy that same night. Both write `research_state.json` and the cycle's step artifacts.
- `kimi_hunter.py`: FOUR entries (06:00 w/ `/tmp/kimi_hunt.lock`; every 3h at :05 lockless; `--deep` 05:35 Sun/Wed; roster refresh separately).
- `kimi_hunter` every-3h line and others share NO lock with their legacy twins (different lock paths or none).
This is a scheduler-layer defect with research-engine blast radius: doubled compute on 2 cores (memory: CI already contends), doubled venue
QPS, same-minute writers on shared state files, and organ cadences that no longer match any single source of truth. The manifest's own header
says "reconstructed, NOT verified against the live box" — the installer then made the live box the union of both worlds.

### E-8 [INTERNAL, NEW ORGAN] `label_factory` crashed on its first real input — the pandas non-unique-index trap at `label_factory.py:296` — after passing its unit tests; the orphan-law lesson ("unit-tested ≠ runs") recurring as "unit-tested ≠ runs on real data"
Reproduced read-only: `.venv/bin/python scripts/build_labels.py` → `ValueError: operands could not be broadcast together with shapes (3019,)
(303,)` at `libs/research/label_factory.py:296` in `_mutate_from` (`out.loc[idx, c] = out.loc[idx, c].to_numpy() * factors`). 3019/303 ≈ 9.96:
`idx` holds ~303 sampled index labels but the panel's index is non-unique (multi-symbol/multi-bar concat), so `.loc[idx, c]` resolves each
label to ~10 rows → 3019-row LHS vs 303-length `factors`. `tests/research/test_label_factory.py` passed (committed green 07-30) because
synthetic fixtures use unique indexes. Consequences: the leakage-check (`leakage_check`, the factory's OWN safety gate) is what crashes, so
NO labels are produced at all; and per E-6 the crash is reported as "NO-INPUT". Fix is one line (sample positionally: `.iloc`, or
`reset_index` before mutation) plus a regression test with a duplicated index.

### E-9 [STRENGTH, NEW ORGAN] `fusion_search` REFUSED to run — and that refusal is the best-designed piece of research discipline shipped this month
`data/fusion_search.json` (generated 2026-07-31T00:50Z): `status: REFUSED, detail: "0 axis/axes have earned breadth; a width-3 search needs 3
… searching combinations of axes that failed their own single-axis screens manufactures survivors from noise. Earn an axis first."` It logs
per-axis exclusion WITH the original single-axis verdict text, records `grid_hash` + `effective_n_trials: 0`, and burns zero multiplicity.
This is the multiplicity discipline the constitution demands, encoded as a precondition rather than prose. Contrast E-6: the same day's
engineering produced both the best-disciplined and the worst-instrumented organ. (Also honest: `fusion_engine` prints `0/5 combinations beat
their best component` — negative result reported as such.)

### E-10 [INTERNAL, NEW ORGAN] The strategic director — the desk's ONLY non-Claude reasoning seat — is activation-blocked on the same unfunded $120 OpenRouter line that now idles THREE organs and 5 triage components
`libs/research/strategic_director.py:28`: "Execution is blocked on OpenRouter credit — the same 402 that…"; `run_strategic_director.py:106`
treats 402 as "NOT an error: the designed state until credit lands". Live cron `40 5,17 * * * … --ledger` will fire today and no-op politely.
`data/strategic_director.json` (dry-run, 00:50Z): model `openai/gpt-9`, status READY, `n_seen: 0`. GAP_REGISTER row 89 already counted this
blocker's blast radius on 07-29 (13-seat panel 189h stale, 5 triage components #22-#26, adaptive review pinned at floor); the director —
built AFTER that row — adds one more organ to the same purchase. The desk keeps building activation-ready consumers of a dependency nobody
has funded: the marginal build is ~free but the marginal REVIEW capacity is zero until one ~$120 decision lands (it sits on
`data/PRINCIPAL_ACTION.md` §2, principal-blocked). Cheapest capability unlock in the entire engine, and it is not the desk's to make —
which is exactly why the page must not rot (verify-condition in §4).

### E-11 [INTERNAL, NEW ORGAN, wiring] The director navigates by a dossier missing 3/10 artifacts — one of which (`data/data_assets.json`) the intelligence cycle COMPUTES 6×/day and throws away
`data/strategic_director.json` → `dossier_missing: [data_registry (data/data_assets.json), enforcement_matrix, gate_histogram]`.
`ls data/data_assets.json` → MISSING. Yet `web/intelligence_cycle.json` shows `data_registry ACTIVE — 61 assets, 46 MEASURED spans…` (computed
in-process via `data_registry.build()`, persisted only inside the cycle's own JSON). The writer that would create the file the director reads
(`scripts/build_data_registry.py`, OUT=`data/data_assets.json`) got its first-ever cron line at `27 4 * * *` — first fire after this audit.
Two organs built the same evening, one reading a path the other doesn't write. Also: director dossier says `dormant_count: 162` while the
dormancy hunter 34s later reports 131 — two dormancy numbers from two snapshots, neither reconciled.
Note the dossier's composition gap: it includes desk_brief/dormancy/execution_intel/gap_register/moat_audit/reality_gap/recommendation_ledger
but NOT the graveyard and NOT negative_knowledge — the independent reviewer cannot see the desk's 124 recorded refutations, so its
recommendations can and will re-propose dead ground (the E-1/E-2 blindness propagated into the newest organ on day one).

### PART C — REMAINING DELTAS AND NEW SEAMS

### E-12 [INTERNAL, CONTRARIAN] The research engine's nightly self-assessment navigates by a PAPER-BLENDED portfolio: a third equity source of truth
`web/portfolio.json` (mtime **2026-07-31 03:07** — actively regenerated): `{'equity': 18674.09, 'net_pnl': 3674.09, 'start_capital': 15000.0,
'days_live': 28.91, 'deployed_sharpe': 12.48, 'sleeves': ['cash_and_carry (real)', 'perp_ls (paper)']}`. The NAV attestation chain
(`data/nav_attestation.jsonl`) and venue truth put the real book at ~$5.7k; L1.28a's first run already found TWO equity sources (13,155 vs
4,500) — this is a third, blending a paper sleeve's PnL and a 15k paper base into "deployed". Consumers: `daily_research_cycle.py:161`
(`port = _load("web/portfolio.json").get("deployed")` → written into the dated cycle log and `research_state.json`), plus `claim_verifier.py`,
`rollback_guard.py`, `classify_regime.py`, `run_factor_model.py`. Effect: the CRO's nightly "binding_constraint" / bottleneck_rankings and a
"deployed_sharpe: 12.48" fantasy are recorded as institutional state. Every capacity band is a ratio to equity; a research layer reasoning
from 18.7k on a 5.7k book mis-sizes everything it prioritizes.

### E-13 [INTERNAL, CONTRARIAN] `research_priority` reports "ACTIVE — ranked 6 research categories by decay pressure" while ranking SIX HARDCODED CONSTANTS
`run_intelligence_cycle.py:146-154`: it looks for `family_survival` in `data/executive_kpis.json`; measured: `keys: ['policy','updated',
'review_cadence','CRO','CIO','RISK','CTO','CDO','CEO']`, `family_survival present: False` → the fallback dict `{"price_only": 1.0,
"attention_social": 1.0, "trader_behavioural": 1.0, "funding_positioning": 0.5, "onchain_flow": 0.8, "regional_premium": 0.9}` is what gets
ranked, EVERY run. The output is a configured prior wearing a measurement costume — the exact instrument-artifact shape L1.25 warns about,
in the organ whose whole job is to steer search. Either wire the real family-survival record (it exists — the graveyard's family kills) or
report the status as DATA-FREE, never ACTIVE.

### E-14 [EXTERNAL, FRONTIER, cost] The OpenRouter 402 blast radius grew again: kimi_hunter now fires up to 9×/day and 402s every time; the 13-seat panel is 10 days silent
`tail data/cro_ai_logs/kimi_hunt.log` and `kimi_hunter.log` → both end `WAVE 1 -- SHADOW MAPPING / FAILED (HTTPError 402) / OpenRouter is out
of credit`. Live crontab holds FOUR kimi_hunter lines (daily 06:00, every 3h at :05, `--deep` 05:35 Sun/Wed — plus the legacy 06:00 twin).
`ls -la data/panel_verdicts.jsonl` → **Jul 21 09:27** = ~237h/10d without an external verdict. Register row 89 (07-29) already counted this
blocker at "1 purchase blocks 8 defects"; since then the desk ADDED two more consumers (strategic director E-10, kimi_hunter's expanded
schedule). Running total idled by one unfunded ~$120 line: LLM hypothesis generator (never run once), 13-seat panel, adaptive review,
5 triage components (#22-#26), strategic director, kimi_hunter unknown-unknown battery. The purchase sits principal-blocked on
`data/PRINCIPAL_ACTION.md` §2. The desk-side gap (buildable without spending a cent): NO free-tier fallback lane exists — every one of these
organs hard-depends on one paid provider (contingency-before-failure battery move: no named replacement for the single LLM dependency).

### E-15 [INTERNAL] The research DB's audit spine is designed-but-empty: trials_ledger 0 rows, research_runs 0, alpha_registry 0, snapshots 0, config_versions 0 — while the one live table (research_memory, 160 rows) is still unread at generation time
`sqlite3 data/sor_research.sqlite`: `trials_ledger 0` (R0008 open), `research_runs 0`, `alpha_registry 0`, `snapshots 0`, `config_versions 0`;
`research_memory 160` with honest daily cadence (07-30: 16 rows, 07-29: 4, 07-28: 14, 07-26: 124) INCLUDING negative outcomes and
`predecessor_id` lineage — the RESEARCH-MEMORY DUTY is genuinely being exercised by live organs. But the generation-time dedup path still
reads none of it (E-1: the novelty gate reads only 43-row `docs/graveyard.md`; the 4 phantom `research_memory.db` refs read nothing).
7 files reference `sor_research` (`run_worker.py, run_research_tick.py, run_research_lake.py, max_audit.py, experiment_registry.py,
run_supervisor.py, research_memory.py`) — which of them read the research_memory TABLE is unmeasured (logged in §2).

### E-16 [INTERNAL, NEGATIVE SPACE] The NEW-axis hypothesis generator is a one-shot that has not run in 8+ days, and the agenda 4 organs read is a fossil
`crontab -l | grep -c axis_generate` → **0**; no manifest entry; no log. `run_axis_generate.py` docstring: "Scoped GENERATE run for all 13
Bronze axes (clock-saturation breach, principal 2026-07-23)" — an episodic patch, never made a standing organ. Its output
`research_agenda.json` mtime **2026-07-22** (9 days stale) while `daily_research_cycle.py`, `rollback_guard.py`, `run_alpha_factory.py`,
`run_axis_generate.py` all read it. With the factory at tested=0 (E-3), the LLM tier 402-dead (E-14), and axis generation unscheduled, the
desk's ONLY standing hypothesis-generation surfaces are session-based diggers/prospectors — the autonomous generation layer is entirely idle.

### E-17 [INTERNAL, delta] `steps_ok` still has ZERO readers
`grep -rn "steps_ok" scripts/ libs/ --include="*.py" | grep -v daily_research_cycle` → empty. Yesterday's R-4 (the cycle records its own
step failures into a field nothing reads) is unchanged: a step can fail every night forever and nothing fires.

### E-18 [INTERNAL, FRONTIER-negative, delta] The Korean-language collector's output artifact does not exist at all
Yesterday's R-5: `collect_naver_krsearch.py` reports `ok: True` while collecting nothing. Today:
`stat data/batch_krsearch_screen.json` → `No such file or directory` — the collector's own OUT path (`collect_naver_krsearch.py:38`) has no
artifact on disk. Non-English collection is not degraded; it is absent, while KR *price* data (kr_perasset panels, rebuilt 07-30) is rich —
the desk mines Korean prices but zero Korean language/attention surfaces, and translation capability remains zero lines (R-19 unchanged).

### E-19 [INTERNAL, delta — partial strength] Literature: the feed IS running and IS §33-governed; conversion to screens is still zero
`stat data/research_feed.json docs/research/feed_inbox.md` → both **2026-07-30 08:15** (live). `max_audit.py:2686-2691` `_DIG_DOCS` includes
`feed_inbox.md` and `literature_coverage.md` — finds there owe §33 dispositions (scope law correctly applied; I verified before assuming
otherwise). What has NOT moved: yesterday's R-21 — 83 ingested papers, zero have ever reached an axis screen; `literature_coverage.md` mtime
07-26. The pipe runs; the conversion step still does not exist.

### E-20 [INTERNAL, meta, delta] The sweep runner still does not rotate seats: today's roster order is identical, and the seat that has never completed is again LAST
`data/cro_ai_logs/deep_sweep_20260731T0035.log`: alpha-discovery → data-intelligence → data-moat → infrastructure → execution-growth →
validation-stats → research-engine (this seat) → meta-and-blindspots last. Yesterday's O-4 (rotate seats, synthesis-first) unimplemented;
position-8 starvation risk (memory: sweep runner starves position 8 + synthesis) persists by construction. Mitigation since `fccc580`
(sentinel grading, .FAILED sidecars) is real but ordering is untouched.

### E-21 [FUTURE, GREENFIELD — delta on R-29/R-30] The activation layer the greenfield redesign called for WAS built (intelligence cycle) — the missing halves are a consumer and a fallback
Yesterday's R-30: ~60% of the engine would not be rebuilt; the redesign centers activation-not-architecture. `run_intelligence_cycle.py` is
exactly that move, one day later — credit where due. Two greenfield gaps remain: (a) NO consumer: nothing reads `web/intelligence_cycle.json`
or `data/strategic_director.json` yet (unverified reader = the R-8 write-only shape one level up; logged in §2); (b) NO degraded-mode lane:
every LLM organ hard-fails to a single paid provider (E-14) — a 2-3y-out design would route dry-runs and cheap seats through free tiers and
keep paid models for verdict-grade work only.

### E-22 [CONTRARIAN, self-applied] The factory's own banner conclusion rests on the broken instrument
`crypto_factory_cron.log` prints nightly: "the constraint is DATA/MECHANISM, not volume. Do NOT rent hardware yet" — justified by
`info_bits/exp=0.2345`, which R-2 proved is an algebraic constant emitted for 1244/1244 rows (all rejects at a hardcoded 0.15 prior). The
conclusion may well be TRUE (420 re-scored candidates pending — alpha-discovery audit), but its printed evidence is an artifact of the
instrument — the exact L1.25 shape (an instrument defect read as a fact about the market) recurring INSIDE the organ that prints the law.
