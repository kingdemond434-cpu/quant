# WEEKLY DEEP COLD AUDIT — DATA-INTELLIGENCE — 2026-07-29

Auditor: cold-sweep data-intelligence seat (read-only; retry of today's BRAIN_AUTH_FAILED 0-byte stub).
Doctrine: v2 core + exhaustion mandate. Scope: datasets (quality/coverage/latency/history/cost),
collection architecture, redundancy, vendor concentration, survivorship, timestamp consistency,
entity resolution, schema evolution, repair automation, backfill, metadata, versioning, lineage,
reproducibility, derived datasets, weak labels, cross-source enrichment, alt-language sources, archives.

RATCHET CONTEXT: the 2026-07-28 sweep (315 lines, COMPLETE) ranked 10 opportunities + 7 probes. This
sweep's first duty was DISPOSITION VERIFICATION on those, then NEW seams. Verdict up front: **zero of
the 07-28 sweep's items were actioned or even ledgered**, and this sweep found the mechanism (F1).
All commands run 2026-07-29 ~05:30–06:30 UTC from /home/quant/quant-platform.

STATUS: COMPLETE.

## SCORES

- current_capability_pct: **60** (down from 62 not because capability fell but because this sweep
  PROVED more of the meta-layer is broken: the DQS organ has three live false-verdict mechanisms, two
  research-critical daily feeds have no writer in the repo, and the audit→action pipeline is severed).
  Collection core remains genuinely strong (S1/S2: perfect 7-year daily continuity, live L2 moat).
- practical_ceiling_estimate: **90** (unchanged; bounded by free-only + single-box policy).
- ceiling_gap: **30 points**.
- opportunity_cost_1y: **UNBOUNDED LEFT TAIL (moat still 1 copy, no disk gauge, fuse re-measured
  ~55–60 days) + a poisoned prioritizer (conversion_engine inflates cost +0.5 on ≥7 falsely-DEAD
  sources) + one Holm forward slot burning at 0/40 days (cny clock starved since 07-23) + ~350
  option-surface-days/yr still being destroyed + the ENTIRE audit output stream evaporating
  (2 full sweep-days × 8 subsystems of findings never entered the driving ledger).**
- confidence: **0.85** on findings (every claim command-cited), **0.6** on ranking.
- unknown_unknown_score: **0.40** — I found at least one scheduler I could not identify read-only
  (something writes deribit_surface + crypto_regime daily at 00:02, and it is not in user crontab,
  the enumerated ops/*.sh, or daily_research_cycle), and two daily feeds whose writer is not in the
  repo at all. Machinery that an exhaustive read-only census cannot enumerate is the definition of
  unknown-unknown surface.
- info_gain_if_investigated: highest for the scheduler census (#8) and the vitals-fix regression (T1),
  because both un-blind every other monitor; then the bybit moat-weight anomaly (still unprobed).
- expected_alpha_contribution: direct moderate (surface family, ETF screen unblocked, cny clock
  revived); indirect HIGH (un-poisoning conversion costs; keeping Stage-B clocks fed is the only
  path to promotion under the two-stage law).
- expected_compounding_contribution: **VERY HIGH** — #1 (audit→action loop) re-arms every future
  audit; #2 (vitals) restores the only DQS organ; #4 (collector-handoff law) converts every future
  mined dataset into a durable feed instead of an organ-tended plant.
- CEILING EXPANSION: the 90 ceiling assumes free-only + single box + **LLM-organ labor for daily
  appends**. The third assumption is the soft one: collector_author (already built, never scheduled,
  attempts ledger 0 bytes) + a catalog would lift it at zero cash cost. The first two remain policy
  with documented lifting conditions (registry's tardis one-off clause; ~$1–2/mo object storage).

---

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**S1. Core price history is deep, continuous, and current — measured, not assumed.**
`.venv/bin/python` scan of `data/lake/bronze/crypto/BTCUSDT/D1/**`: **2,517 rows, 2019-09-08 →
2026-07-29 (today), day-gaps >1: 0**. 274 symbols in the family (07-28 sweep S4, unchanged).
The lake holds 28,247 files (`find data/lake -type f | wc -l`).

**S2. The moat records continuously through this morning.** `find data/moat/fut/BTCUSDT -name "*.gz"`
→ first `20260717_23`, latest `20260729_06` (this hour). Sizes: bybit 4.46G / fut 758M / spot 390M
(`du -s data/moat/*`). Vitals scores the moat dir OK at age 19s. Growth since yesterday's sweep
(bybit 4.1G→4.46G, fut 707M→758M) ≈ **0.4G/day → fuse to disk-full ≈ 55–60 days** (25G free, `df -h`).

**S3. Screen discipline caught its own would-be phantom — twice, independently.**
`data/batch_premium_screen.json`: bithumb_KR IC +0.722 self-flagged `"implausible_leak": true,
"verdict": "SUSPECT-LOOKAHEAD"` and rowed in `data/graveyard_resurrection_queue.json`
("bithumb_kr_premium_lookahead"); `data/data_sanity_report.json` independently flags the same number
CRITICAL ("daily-horizon IC above 0.5 implies near-perfect foresight"). Defense-in-depth on the
data→screen boundary is real, not configured.

**S4. The impossibility scanner is alive and its teeth are growing.** `data_sanity_report.json`
generated **2026-07-29T02:35** (today), 51 findings (16 CRITICAL / 26 HIGH / 9 MEDIUM) vs 37
yesterday — including flatline catches on `cny_premium.jsonl/p2p_cny` (5 identical), the
kr_perasset `fx_ffill` run, and 1,732 missing days inside the cny_otc wayback span (an honest
sparse-reconstruction disclosure).

**S5. Deterministic collection exists and is scheduled — the desk is NOT all-LLM at the base layer.**
`crontab -l`: defi_lending hourly (:17), oi_ls_live hourly (:32), coinmetrics daily 03:47,
dl_oi_ls_universe daily 06:20, ingest_axes daily 06:40, venue_divergence every 5m, recorders
re-spawned every 10m. `grep collect_ scripts/daily_research_cycle.py` → 16+ more collectors with
per-run timeout budgets (kimchi 90s, fred 120s, stablecoin_supply 120s, cny 60s…).

**S6. Forward clocks are honest.** `data/axis_shadow_state.json`: 4 Stage-B clocks all ACCRUING with
explicit need=40; kimchi_premium reports its own **negative** forward cum_return (−0.040, ann_sharpe
−9.4 at 6/40 days) rather than grading itself — "eligibility != deployment" pinned in the artifact.

**S7. Collector monitoring has teeth where it looks.** `data/collector_health.json` (updated today
02:35) holds the cny KILL ("FLATLINE p2p_cny=6.74 x5") and OK verdicts with row/age evidence for
kimchi (8 rows, 0.0h) and stablecoin_supply (7 rows, 0.0h).

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

- **What runs at 00:02.** deribit_surface.parquet last ts 2026-07-29T00:02:05, crypto_regime.json
  updated 00:02:08 — same batch. Not in user crontab (`crontab -l`), not in `ops/*.sh` grep for
  deribit/classify_regime, not in daily_research_cycle (cron-started 02:00). A scheduler exists that
  a read-only census cannot name. (Root crontab / another service unit are the suspects; I did not
  have visibility.)
- **Which organ writes kr_perasset_premium_history.jsonl and cfe_crypto_settlements.jsonl.**
  Zero in-repo references (`grep -rln "perasset" --include="*.py" …` → nothing;
  `grep -rln cfe_crypto_settlements scripts/ libs/ ops/` → nothing). Mtimes cluster at 15:09–15:46,
  right after the quant-frontier (15:00) / quant-dataaxis (14:00) systemd timers — LLM-organ
  authorship is near-certain but unproven (F3).
- **Whether CFE is stalled or just T+1.** Last settlement row 2026-07-27 (Monday); Tuesday's row was
  still absent at 06:30 UTC Wednesday. Resolves at today's 14:00–15:00 organ window; if 07-28 does
  not appear today, it is a stall.
- **Why the defi_utilisation clock shows forward_days=1, last=None** while its input collector
  (defi_lending, hourly cron) is healthy (live-check DQS 1.0). Unexplained clock-feed mismatch.
- **The bybit moat weight anomaly** (4.46G vs fut 758M for similar symbol counts) — carried from
  yesterday, still unprobed (T7 there, T6 here).
- **Whether coinmetrics' 2010-era rows are load-bearing** for its 4 real consumers
  (screen_fred_macro_axis, dependency_graph, stage_a_executor, screen_idle_axes) or dead weight that
  makes every full-file read slower.
- **Entity-resolution loss count.** HL funding joins on raw coin-string equality
  (`scripts/collect_hyperliquid_funding.py:52` — `both["coin"].unique()`); how many assets silently
  drop or misjoin (1000PEPE/kPEPE-style multiplier variants) is unmeasured (T5).
- **venue_divergence semantics**: latest row `venue_nav −23179 vs mark_nav +13185` (fresh, stale=false).
  Either a large real venue-mark dislocation being recorded or a sign/aggregation bug — execution's
  question, but the data recorder is the witness.

---

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

**#1 — CLOSE THE AUDIT→ACTION LOOP. The deep-sweep's entire output stream currently evaporates.
[COMPOUNDING — re-arms every past and future audit] — TOP FINDING OF THIS SWEEP.**
- Evidence (severed handoff): `python3 scripts/recommendations.py report` → 32 rows; the ONLY
  deep_sweep-sourced rows are R0001–R0009 from **07-26**; sources for everything later are
  `cycle`/`cycle-2026-07-28*`. The 07-28 sweep — 8 subsystems, 10 ranked opportunities in this
  subsystem alone — produced **zero ledger rows**. Two live cycles have run since (R0025–R0032 prove
  the 07-28 cycle wrote its OWN findings; data/sanity/vitals stamps 02:35 today prove the 07-29
  cycle ran) and neither picked the sweep up. The 07-28 report's own closing line ("per §41 they
  require ledger rows at next live cycle") was executed by nobody: the handoff has NO OWNER.
- Evidence (grace violations): the report command itself prints **13× "DEFECT [UNDISPOSED past
  grace]" at 2.4–2.8 days** (R0001, R0003–R0009, R0011–R0013, R0015–R0017) plus R0002
  "[SCHEDULED past due]". §41's one illegal state — silence — is the current steady state.
- Evidence (consequence, item by item, all still live today): MAX_ROWS still 3000
  (`grep -n MAX_ROWS scripts/data_vitals.py` → line 39); zero disk monitor (`grep -rn
  "statvfs|disk_usage|df -" scripts/watchdog.py scripts/run_alerts.py scripts/data_health.py` →
  empty); zero backup (`grep -rln "rclone|rsync|backup" ops/ scripts/` → only memory docs +
  git_snapshot); collector_attempts.jsonl **still 0 bytes** (`ls -la`); deribit surface still
  6-column summary, 72 rows (+2 days destroyed since yesterday); etf screen still `n_days 15/51`;
  futclose BTCUSDT content still ends 2026-06-30.
- Exactly-what: (a) a completion hook in the sweep path (or a mandatory first-item in the next
  brain cycle's carry-over brief) that parses each sweep report's ranked headers into
  `scripts/recommendations.py add` rows with `source=deep_sweep-<date>`; (b) a nightly §41 sweep
  that PAGES on `undisposed > 24h` — the report command already computes and prints the DEFECT
  lines; nothing consumes them (outcome-not-config: an alarm nobody reads is not an alarm).
- Complexity: hours. Dependencies: none. Validation: this report's items appear as ledger rows
  within 24h; undisposed-past-grace count trends to 0 over a week. Failure mode: rowing without
  disposing (the ledger becomes a second graveyard) — the pager on grace expiry is the counter.
  Maintenance: near-zero. Retirement: never (it IS §41). Horizons: 1w = 07-28+07-29 findings live;
  1y = audits compound instead of evaporate.

**#2 — FIX ALL THREE FALSE-DEAD MECHANISMS IN THE DQS ORGAN (not just yesterday's one). [COMPOUNDING]**
- The alarm is now ~90% false: 8 of 17 scored sources are flagged "DEAD -- FAILOVER"
  (`data/data_vitals.json`, updated today) and **at least 7 are demonstrably false**:
  - (a) **MAX_ROWS head-sampling** (yesterday's diagnosis, now with a SECOND victim proving it is
    progressive): `wc -l` → coinmetrics 9,872 rows (head ends 2018 → "age" 7.8y) and
    **kr_perasset 3,008 rows — it crossed the 3,000 cap this week and instantly went false-DEAD**
    (`tail -1` → date 2026-07-28, fresh; vitals says age 9.1d). Every append-only feed in the shop
    is on a countdown to this bug: the newest rows leave the sampled window forever.
  - (b) **median-gap-zero on batch-written files** (NEW): `oi_ls_live.jsonl` tail shows two rows
    with the IDENTICAL timestamp `2026-07-29T05:32:01.526901` — batch writes make the median
    pairwise gap 0, `if cadence_s and cadence_s > 0` fails, latency/completeness lock at 0.5, and
    the file lands at exactly 0.25 < 0.5 DEAD **while 227 seconds fresh**. Same mechanism:
    defi_lending (5,742 rows, hourly cron, live-check entry scores 1.0 in the SAME artifact),
    cfe_crypto_settlements, cfe_regulated_basis_daily, breadth_expansion. The scorer's own comment
    block memorializes this exact contradiction ("defi_lending scored 0.250 DEAD on its .jsonl
    while its heartbeat scored 1.000 OK") as the motivation for the new-file grace — the fix
    covered the symptom (few distinct timestamps) and left the mechanism (zero median gap) alive.
    The artifact now ships BOTH verdicts for two sources simultaneously.
  - (c) **event-log misclassification**: stage_a_verdicts.jsonl has 5 legitimate per-verdict-type
    key-sets (modal 16/38 = the 0.421 "schema_integrity"); it belongs in `_ARTIFACT_KIND` beside
    panel_verdicts, which already earned the exemption.
- Consequence is not cosmetic: `conversion_engine` adds +0.5 cost to every non-"OK" source
  (07-28 sweep, `scripts/conversion_engine.py` lines 43–60), so the research prioritizer is
  actively biased AGAINST the coinmetrics/kr-premium/oi-ls/defi/cfe families — and the one real
  kill (cny) is buried in seven false alarms, the exact reader-training failure the module's own
  docstring warns against.
- Exactly-what: full-pass max-timestamp per entity-group (10k rows is trivial); cadence from
  DISTINCT-timestamp gaps (dedupe same-stamp batches before the median); add stage_a_verdicts to
  _ARTIFACT_KIND; regression fixtures per mechanism (T1). Complexity: <1 day.

**#3 — MOAT SURVIVAL PACKAGE (carried, fuse re-measured).** Disk 25G free, moat ~5.6G growing
~0.4G/day → **~55–60 day fuse**; still zero disk monitor, zero backup, `regenerable: false` assets
in exactly one copy (all greps re-run today, all still empty — see #1 evidence). Everything in the
07-28 sweep's #1 stands verbatim; it is re-ranked #3 only because #1 is the reason it (and
everything else) went unactioned for a day+.

**#4 — COLLECTOR-HANDOFF LAW: no recurring dataset without a deterministic writer. [COMPOUNDING]**
- Evidence: kr_perasset_premium_history.jsonl (473KB, daily rows through 07-28, feeds the flagship
  Korean-premium research family) and cfe_crypto_settlements.jsonl (2,005 rows, the regulated-basis
  axis) have **no writer in scripts/, libs/, or ops/** — they are hand-appended by LLM organ
  sessions (mtimes 15:46/15:09, right after the 14:00/15:00 organ timers). The failure mode fired
  TODAY: this very report is the retry of a `BRAIN_AUTH_FAILED — pool drained` stub; on such days
  ghost feeds silently skip a day. Provenance for both: "UNKNOWN — not recorded" (vitals). An
  unauditable construction maintains the same family in which a sibling screen (bithumb) was just
  caught with lookahead (S3) — construction audit is impossible without construction code.
- Exactly-what: (a) rule: any dataset receiving its 3rd recurring append must have a scheduled
  deterministic collector (daily_research_cycle table or cron) within 7 days, or be stamped
  one-off-static in the catalog; (b) schedule `collector_author` — built precisely to industrialize
  this handoff, never fired (attempts ledger 0 bytes since 07-27) — or ledger its reasoned
  rejection (§41 allows a no; it forbids silence). Backfill the law over the two ghost files first.
- Validation: `grep -rln <file>` finds a writer for every feed with ≥3 appends; vitals provenance
  UNKNOWN count falls. Failure mode: collector_author's disclosed exec-LLM-code-on-key-host risk —
  its safety posture review is part of the scheduling decision, not a reason for silence.

**#5 — REPAIR LOOP FOR KILLED CLOCKS (carried, cost now measured).** cny_premium: feed KILLed
(FLATLINE ×5) with no failover attached → its pre-registered Stage-B clock reads **forward_days
0/40** (axis_shadow_state.json) since 07-23. Under MAX_FORWARD_SLOTS=12 that is a Holm slot
burning at zero accrual — the clock-saturation duty violated in the artifact. Attach the
CDX-replayed OTC-index construction (591 rows on disk) as the registered alternate; persist raw
top-10 quote arrays per poll so flatline root-cause becomes decidable (07-28 T6).

**#6 — STOP DESTROYING THE OPTION SURFACE (carried).** `deribit_surface.parquet` → 72 rows × 6
cols; +2 summary rows since yesterday = 2 more full-chain days permanently gone. ~30 LOC, KB/day.

**#7 — ETF-FLOWS BACKFILL (carried).** Screen still `n_days: 15, n_required: 51` — the farside
archive rows (already on disk as HTML) convert a 36-day wait into an afternoon.

**#8 — SCHEDULER + DATASET CENSUS: one catalog, generated monitors (extends 07-28 #8 one level
down). [COMPOUNDING]** Scheduling is now measured to be fragmented across ≥5 mechanisms: user cron
(22 active lines), 7 quant-* systemd timers (`systemctl list-timers`), daily_research_cycle's
internal 16-collector table, organ_catchup's serialized retry law, LLM ad-hoc appends (F3/#4) —
plus at least one writer NO census can name (the 00:02 batch). A `data_catalog.json` row per
dataset {path, writer, scheduler, cadence, provenance, screen artifact, conversion status,
regenerable, backup policy}, with vitals/health/collector_monitor/organ_owed scopes GENERATED from
it, ends the class of "no writer/no owner/no monitor" findings permanently. The 00:02 mystery is
item #1 in its intake queue.

**#9 — CANONICAL INSTRUMENT TABLE (entity resolution).** All cross-venue joins are raw
string-equality (HL `coin` join at collect_hyperliquid_funding.py:52; upbit/bybit/binance symbol
conventions differ, incl. 1000X/kX multiplier variants). One `instruments.json` (asset ↔ per-venue
symbol ↔ multiplier) consumed by every join. Cheap probe first: T5 counts what the current join
drops. Registry claims "205 matched perps" — how many SHOULD match is the unasked question.

**#10 — ZOMBIE MARKINGS + ROLLING HOLES (carried, sharpened).** fx/equity/energy/metal/index bronze
all last written **2026-06-21** (38 days; newest-mtime scan) — §36 demands TERMINAL-with-reason or
re-ownership; futclose_daily BTCUSDT content ends **2026-06-30** (29-day rolling hole; family
mtimes 07-23 prove partial touches); CME family's newest artifact ends 2026-07-20 (a one-off pull
now decaying under a converted screen — screen-then-starve); cot_zcache stale 38d. Mark or feed.

---

## 4. WHAT WE TEST NEXT (experiments, success criteria, retirement conditions)

- **T1 (vitals triple-fixture regression):** fixtures for all three mechanisms — (a) 4,000-row
  append-only file, fresh tail, stale head → must score OK; (b) batch-written file, 5 rows/stamp,
  hourly stamps, fresh → OK with cadence≈3600; (c) event-log with 5 key-sets → classified, not
  scored; (d) genuinely stale-tail file → still DEAD. Success: live artifact shows ≤1 DEAD flag
  (cny lineage only) same day. Retire when fixtures run in CI.
- **T2 (§41 loop-closure):** after #1 lands — this report's items appear as `deep_sweep-2026-07-29`
  ledger rows within 24h; a synthetic overdue row triggers the grace pager. Success: undisposed
  count 13→0 within a week. Retire: never (constitutional).
- **T3 (ghost-writer identification):** tail today's dataaxis/frontier organ logs after their
  14:00/15:00 runs; confirm which appends kr_perasset/cfe, then apply #4's law. Success: both files
  named in a collector script or stamped static within 7 days.
- **T4 (CFE stall disambiguation):** if 2026-07-28 settlement rows are absent after today's organ
  window, file the stall; if present, record cadence "T+1 via organ" in the catalog and let #4
  convert it to a deterministic collector anyway.
- **T5 (entity-resolution loss count):** list HL assets vs Binance perp universe with a
  multiplier-aware normalizer; report how many the string join drops/misjoins. Success: a number;
  if >0, #9 gets its EV justification. Cost: one afternoon.
- **T6 (bybit weight anomaly, carried):** decompress one bybit vs one binance hour, count
  msgs/levels; dedup saving directly extends the #3 fuse.
- **T7 (00:02 scheduler hunt):** enumerate root crontab + all service units for the writer of
  deribit_surface/crypto_regime; add to the census. Success: zero unattributed daily writers.
- **T8 (defi_utilisation clock probe):** explain forward_days=1/last=None against a healthy hourly
  collector; success = either a clock bug fixed or a documented warm-up rule.

---

## PERSPECTIVE COVERAGE LEDGER

- **INTERNAL (measured vs configured):** the two central organs disagree with reality in opposite
  directions — vitals cries DEAD on ~7 healthy feeds (#2) while the recommendation ledger stays
  silent on 2 sweeps of real defects (#1). Measured strengths: S1 (0 gaps in 2,517 days), S2
  (recorder current to the hour), S4 (sanity findings 37→51 in a day).
- **EXTERNAL (world-class desk):** would run alarm precision as a KPI (a 90%-false DEAD page is
  net-negative), one scheduler census (#8), no ghost feeds (#4), a canonical instrument table (#9),
  and treat audit output as a queue with an SLA (#1) — none of which needs new data, only plumbing.
- **FUTURE (2–3y):** unchanged from 07-28 and now sharper: the desk's own future design
  (catalog-driven, LLM-authored deterministic collectors behind static scan + autoscreen) is BUILT
  and idle — collector_author's attempts ledger is still 0 bytes. The future is a crontab line away.
- **CONTRARIAN (assumptions actively tested):** (i) "more monitoring = safer" is FALSE here today:
  the DQS organ at ~90% false-positive actively poisons conversion costs and trains readers to skip
  pages — until #2 lands, the desk would lose nothing by trusting collector_health + data_health
  alone. (ii) "LLM organs are the desk's superpower" — TRUE for digging (S3's bithumb catch came
  from an organ's screen), FALSE for deterministic daily appends, where today's BRAIN_AUTH_FAILED
  stub is the counterexample: the wrong tool for cron's job (#4). (iii) "the premium family is our
  cleanest discovery" — its screen base includes a ghost-written file with unrecorded provenance and
  a sanity-flagged ffill run; the family's honesty currently rests on S3's gate, not on lineage.
- **GREENFIELD:** rebuilt today: one catalog; every dataset born with {writer, scheduler, screen,
  provenance, backup policy}; monitors and organ-owed logic GENERATED from it; event-logs, state
  files and feeds as distinct first-class kinds (half the false-DEADs are kind-confusion).
  Current estate: 5 schedulers, 3 monitors with 3 scopes, 2 overlapping source catalogs,
  provenance dict covering 5 of ~38 scored files (~13%). Historical baggage: MT5-era frozen
  families (38d), a 232-file data/ root mixing feeds/state/logs/screens.
- **FRONTIER:** no NEW publicly-possible capability found this sweep beyond the 07-28 list — the
  frontier finding is that the existing frontier list is aging unexecuted: OKX portal (verified
  clean 07-22) unbuilt, binance.vision bookDepth/premiumIndexKlines probe unrun, farside archive
  unparsed, and `last_free_dig: 2026-07-22` — 7 days since the universe map's last dig entry.
  An unworked frontier decays into a catalog; #1 is again the binding fix.

## NEGATIVE-SPACE SWEEP (verified absences, with the checking command)

1. **No consumer of the §41 report's DEFECT lines** — the only place grace violations surface is a
   CLI nobody is scheduled to read (`grep -rn recommendations ops/*.sh crontab` → no consumer).
2. **No backup, no disk monitor** (re-verified today; greps in #1 evidence) — fuse ~55–60d.
3. **No schema versioning/manifests/checksums** anywhere (`grep -rn schema_version libs/ scripts/`
   → none; carried 3rd sweep running).
4. **No canonical entity table** (grep symbol_map/normalize_symbol → only store internals).
5. **No regime HISTORY** — `data/crypto_regime.json` is a single overwritten snapshot (updated
   00:02 today; no crypto_regime_history.jsonl exists) while rule-based and HMM regimes currently
   DISAGREE (`"trend": "bear"` vs `"hmm_regime": "bull/low_vol"`, `hmm_gmm_agree: false`) — the
   disagreement stream itself is an unrecorded dataset (R0006 open 2.8d).
6. **No per-poll raw quote persistence** for premium collectors — the cny flatline (KILL) remains
   root-cause-undecidable from stored data (carried; #5 fixes).
7. **No US-venue books in the moat** (Binance+Bybit only; carried).
8. **No owner for the sweep→ledger handoff** — the 07-28 report SAID "next live cycle" and two live
   cycles ignored it; an instruction without an owner is negative space (#1).
9. **Provenance recorded for 5 of ~38 scored artifacts** (~13%) — `PROVENANCE` dict in
   scripts/data_vitals.py vs the artifact's UNKNOWN entries.
10. **mine_generation_priors tracks exactly ONE source class** (n_seen=6) — the §33.4 reweighting
    law is live but its evidence base cannot yet rank anything (checked
    `data/mine_generation_priors.json`, generated today 06:00).

## CROSS-SUBSYSTEM HANDOFFS

- The 15 cost_model flat-slippage CRITICALs (data_sanity, again today) → execution; the fix is
  still book-depth data (#3 retention, T6, 07-28 T4 probe).
- venue_divergence `venue_nav −23179 vs mark_nav +13185` (fresh row, stale=false) → execution/risk
  must say whether that sign pattern is real dislocation or aggregation bug.
- The 13 undisposed §41 rows include validation-side defects (R0016/R0017 gate-optimality probe
  mis-wiring) — meta/validation subsystems inherit #1's fix.

## §33/§41 NOTE

This audit ran READ-ONLY: no ledgers written, no state touched. Its ranked items #1–#10 and probes
T1–T8 are carded output owed ledger rows (`scripts/recommendations.py add`, source
`deep_sweep-2026-07-29`) by the next live cycle — and #1 exists precisely because that sentence
failed to execute for the 07-28 sweep. If #1–#2 alone land this week, the alarm stream becomes
trustworthy and the audit stream becomes cumulative; those two properties compound every other
line in this report.
