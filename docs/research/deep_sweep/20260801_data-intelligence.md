# WEEKLY DEEP COLD AUDIT — DATA-INTELLIGENCE — 2026-08-01

STATUS: COMPLETE — 35 findings (DI-1..DI-35), 5 validated strengths, 8 ignorance-ledger rows,
15 ranked opportunities, 7 tests. Every claim command-cited; all six perspectives covered; the
negative-space sweep and the full 10-move proactive battery reported. Three TIER1 re-grades proposed.

Auditor: cold-audit seat (data-intelligence), doctrine v2. Read-only sweep; only this report is written.
Scope: every dataset — quality / coverage / latency / history / cost — plus collection architecture,
redundancy, vendor concentration, survivorship, timestamp consistency, entity resolution, schema
evolution, repair automation, backfill capability, metadata, versioning, lineage, reproducibility.
Plus derived/synthetic datasets, weak labels, cross-source enrichment, alt-language sources,
government publications, archives.

Baseline: `docs/research/deep_sweep/20260731_data-intelligence.md` (16 findings, COMPLETE) and
`20260730_data-intelligence.md` (27 findings, COMPLETE). Prior findings are referenced by number
(DI-n = 07-31 ledger, F-n = 07-30 ledger) and **verified for movement**, not re-derived.

## HEADLINE — the five things that matter today

1. **Every crypto backtest this desk has ever run is survivorship-biased at the source.** The panel is
   selected on *today's* liquidity (`status=="TRADING"` + top-N by current 24h volume) and then
   backfilled seven years. LUNA, UST, FTT, SRM are all absent — the desk has never backtested a token
   dying. No point-in-time universe exists. → **DI-28**
2. **The 7.2 GB moat has zero backups and zero readers.** `backups/moat/` is an empty directory created
   by the backup script's own `mkdir`; a T4-defect-closed claim was recorded against it. Meanwhile
   0 of 15 screens and 0 backtests read any moat data, and its 6.1 GB Bybit half has no reader at
   all. → **DI-31, DI-32**
3. **The data-quality monitor reads the OLDEST 3000 rows of every append-only log.** It reports
   `bitmex_funding` 6.5 *years* stale (truth: 20h), flags healthy feeds DEAD, and — the worse half —
   goes permanently blind to any feed over 3000 rows. Two live feeds cross that line this week. → **DI-1**
4. **All five non-crypto asset classes died on the same day, 43 days ago, unnoticed.** 26y FX, 18y
   metals, 16y energy, 13y index, 8y equity — one shared bridge, one silent death, no monitor covers
   any of them. → **DI-30**
5. **"We own 26 years of data nothing reads" is an instrument artifact.** The registry registers lake
   assets under a `**` glob, greps for that literal string, finds nothing, and pays a +10 research-value
   bonus for the "unread"ness. 53 scripts actually read the lake. → **DI-8**

## SCORES

| metric | value |
|---|---|
| current_capability_pct | **31%** (36% claimed 07-31; the drop is measurement, not regression — DI-28 survivorship and DI-31 zero-backup were not known then, and both are foundational) |
| practical_ceiling_estimate | **85%** (unchanged; the majority of the gap remains wiring, ownership and fences — not new engineering) |
| ceiling_gap | **54 pts** |
| opportunity_cost_1y | **VERY HIGH** — dominated by DI-28 (a survivorship-biased panel silently inflates every cross-sectional result the desk will produce for a year, and the validation stack cannot detect it) and DI-31 (a single disk failure permanently erases the only non-replicable asset) |
| confidence | **HIGH** on findings (every claim command-cited and independently re-verified), **MEDIUM** on rankings |
| unknown_unknown_score | **8/10** — up from 7. This sweep found that the two instruments the desk relies on to see its own data (`data_vitals`, `data_assets`) are both wrong in ways that produce *confident* output. When the measuring devices are the defect, the residual unknown is larger than the found set |
| info_gain_if_investigated | **VERY HIGH** — T1 (survivorship counterfactual) and T2 (moat restore drill) each resolve a live foundational unknown for hours of work |
| expected_alpha_contribution | **HIGH, mostly corrective** — DI-28 does not add alpha, it removes phantom alpha; DI-32 (moat unmined) and DI-23 (970d positioning history) are the direct-additive ones |
| expected_compounding_contribution | **VERY HIGH** — point-in-time universe, tail-read freshness, moat replicas and per-feed write-rate fences are all multipliers on every future study |

**CEILING EXPANSION — what defines the 85%, and what would move it.** The ceiling assumes (a) *one
egress IP and REST-first collection* — a second IP plus WS-first design deletes the 418/ban constraint
class outright (DI-14) rather than mitigating it; (b) *collection bounded to this box* — Binance Vision
/ OKX / Upbit bulk archives plus cheap object storage turn history depth from a collection problem into
a download problem (DI-23 is 970 days available for one cron line); (c) *one seat of LLM capacity* gates
the acquisition tier, so the source→ingest conversion ratio (DI-27: 1 LIVE / 41 graded) is a funding
constraint wearing a research costume. All three assumptions are **organizational, not technological** —
which means the ceiling is lower than physics requires, and that is the honest reading.

## SIX-PERSPECTIVE COVERAGE

| perspective | outcome |
|---|---|
| **1. INTERNAL** | 35 findings, all command-cited. Dominant theme: the desk's *measuring instruments* for data are themselves defective (DI-1, DI-2, DI-3, DI-8, DI-19, DI-22) — so internal performance has been reported through broken gauges. |
| **2. EXTERNAL (cohort)** | Three concrete transfers below. |
| **3. FUTURE (~2–3y)** | Below. |
| **4. CONTRARIAN** | Tested, and it fired twice: the "unread 26-year lake" narrative is **false** (DI-8), and the "frozen symbols are a writer bug" assumption is **false** — it is the universe rule (DI-29). One core assumption survived testing: the parquet lake's timestamp/schema integrity is genuinely clean (zero dup timestamps, zero within-symbol drift, verified across 279 symbols). |
| **5. GREENFIELD** | Below. |
| **6. FRONTIER** | Below. |

**2. EXTERNAL — the motive-similar tier-1 cohort.** Benchmarked against RenTech/Medallion (the standing
ceiling exemplar), XTX, Jane Street, Jump, HRT; crypto-native Wintermute/GSR/B2C2; negative exemplars
Alameda/LTCM/Archegos.
- **XTX (data-quality obsession) → DI-28 is the transfer that matters.** A point-in-time universe with
  full delisting history is table stakes at every firm in this cohort; equity shops solved it decades ago
  with CRSP-style PIT files. The desk's crypto panel would not pass a first-day data review anywhere in
  the cohort. This is not a capacity-band-dependent practice — it is free and it is missing.
- **RenTech/Medallion — "would this process be recognisable inside Medallion?"** Two answers: the
  *self-recorded tape* absolutely would (recording your own microstructure because no vendor sells it is
  exactly the Medallion instinct); **the fact that nothing reads it would not** (DI-32). Medallion's edge
  was mining exactly this kind of proprietary microstructure. The desk has built the asset and not the
  extraction. That is the single widest gap to the ceiling exemplar in this subsystem.
- **Wintermute / post-FTX venue breadth → DI-25.** `cross_validation_available: 0/51`, Binance at 34% of
  all URL references and 62% of collectors. The FTX lesson is *counterparty and source redundancy as
  default*; the desk has one genuine multi-source failover in the entire data layer
  (`onchain_flows.py`, 4 RPCs).
- **Negative exemplars — which rail would have caught them, and does it fire?** Alameda died of
  commingling and no capital-event ledger: the desk *names* `capital_events` as an asset and the file
  **does not exist** (DI-10). That specific rail is declared and absent.
- **Tier grades this evidence moves** (per the standing rule that the sweep re-grades `TIER1_BENCHMARK.md`):
  `data_engineering` **T2 → T3** (survivorship at the source + 40% frozen panel + 5 dead asset classes is
  below "serious prop"); `data_moat` **T2 → T3** (zero replicas of the irreplaceable asset + zero research
  readers); `vol_surface_expertise` **T3 → T4** (1 obs/day, executor-coupled, 15 gaps >24h — DI-9).

**3. FUTURE (~2–3 years out).** With cheap object storage and commodity columnar engines, the correct
design is: (a) **immutable event-sourced ingestion** — raw venue responses persisted verbatim and
forever, with every derived table a *reproducible projection*, which would have made DI-24's 9.3 MB of
uncommitted-code research data regenerable and DI-29's frozen cohort a re-materialisation rather than a
loss; (b) **the universe as a time series, not a query** — DI-28 disappears by construction; (c) LLM-cheap
**schema and semantic drift detection** on every partition write, so DI-34's naive-timestamp families and
DI-29's 3-way schema split are caught at write time. None of this is exotic in 2026 — it is a design the
desk could adopt incrementally starting with (b).

**5. GREENFIELD — rebuild from scratch with only validated knowledge.** Keep: the hive-partitioned
tz-aware parquet lake (verified clean), the self-recorded moat concept, `data_assets.json`'s *schema*
(span/quality/consumers/replication/moat_score is the right model), the `libs/ops/fresh.py`
consumption-time freshness contract (right idea, 1.8% deployed). Discard: `data_vitals`'s head-truncated
DQS (DI-1) and its hand-maintained allowlist (DI-3) — replace with tail-reads plus a classifier;
the second health verdict in `web/health.json` (DI-19) — one health artifact, one denominator; the
`.exists()` capability detectors (DI-22). Historical baggage carried without justification: four dead SOR
sqlite databases (1.1 MB, all 2026-06-20, all empty tables), `data/sor.sqlite` with **zero tables** still
serving as the dashboard's default `--db`, and `data/data_registry.json` orphaned since 2026-07-08 while
a differently-named successor is built nightly.

**6. FRONTIER — what became publicly possible that this subsystem does not exploit.**
- **`data.binance.vision` bulk archives** are live and free and would close DI-23's 970-day positioning
  gap, deepen the moat's *historical* half (the recorder only archives forward), and provide the
  delisted-symbol history DI-28 needs. The desk uses this host in exactly 3 URL references.
- **OKX historical-data portal** (graded `verified-clean`, `confirmed` in the universe map: tick trades
  since 2021-09, L2 order book since 2023-03, funding since 2022-03) — a second venue's *L2 depth
  history*, which is the one thing the desk's own recorder cannot backfill. Status: `queued`, unbuilt.
- **AWS Public Blockchain Data** (registry.opendata.aws, `verified-clean`) — the stablecoin mint/burn
  reconstruction path, independently corroborated by a Fed FEDS Note using the same dataset for the same
  analysis. Mechanism confirmed, query never run.
- **Free video/audio transcripts** are a first-class dig source via `scripts/fetch_video_transcript.py`
  (YouTube + Bilibili) — zero data-intelligence artifacts currently derive from it.

## NEGATIVE-SPACE SWEEP (what has never been looked at at all)

- **Point-in-time universe / delisting history: never collected.** The `exchangeInfo` call that would
  provide it is made on every ingest run and thrown away (DI-28). This is the largest negative space here.
- **No dataset has a second source.** `cross_validation_available: 0/51`. The question "does our number
  agree with anyone else's number?" has never been asked of any feed (DI-25).
- **The moat has never been mined.** 0/15 screens, 0 backtests, 7.2 GB (DI-32). Microstructure questions —
  queue imbalance, depth resilience, trade-sign autocorrelation, venue-lead/lag at sub-second resolution —
  are entirely unexplored, and they are the questions the tape exists to answer.
- **No restore drill has ever run** on any dataset (DI-31). "Can we recover?" is untested for the entire
  estate, not just the moat.
- **No collector failure is recorded anywhere.** `collector_attempts.jsonl` is 0 bytes; every failure-rate
  number in this report had to be reconstructed from mtimes and gz row counts (DI-6, DI-13).
- **Languages/regions catalogued but never ingested:** Upbit's official archive (blocked on a *licence
  ruling a human must make*, deferred to 2026-08-15 — a decision, not a search failure), Bithumb,
  bitFlyer (ToS host WAF/geo-blocked from this VPS), Naver KR search interest (blocked on an absent
  `data/secrets/naver.json` with no register row). Four Asian-venue paths, four different blockers, none
  on the gap register (DI-26, DI-27).
- **Never simulated:** a venue delisting mid-backtest; a feed silently halving; a schema column
  disappearing; the moat disk failing. All four are live risks in this report and none has a drill.

## OPPORTUNITY COST OF NOT FIXING, ONE YEAR

- **DI-28 (survivorship):** every cross-sectional crypto result produced for a year carries an unknown
  upward bias. The cost is not one bad strategy — it is that the desk cannot distinguish real from
  inflated in *any* of them, so the DSR/Holm/forward-clock machinery spends its multiplicity budget on a
  corrupted panel. Highest opportunity cost in this report.
- **DI-31 (no moat backup):** expected cost = P(disk failure in 1y) × 7.2 GB of permanently
  unreconstructable proprietary data + the ~10 months of forward recording needed to rebuild depth.
  Small probability, effectively infinite loss, mitigation cost ≈ one working cron line.
- **DI-1/DI-19 (broken health instruments):** the desk cannot currently tell when a feed dies — proven
  twice over in this sweep (5 asset classes dark 43 days, 53% of an hour's depth lost silently). The
  compounding cost is every *future* silent death going undetected for weeks.
- **DI-32 (moat unmined) + DI-23 (970d positioning history):** the direct alpha-discovery cost —
  ~600 MB/day of the desk's only proprietary asset accumulating with zero research surface, and 2.6 years
  of free positioning history one cron line away.

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**S1. The moat recorder tier is alive, single-instanced, and gap-free at the calendar level.**
```
$ pgrep -af 'run_recorder'      → 3 processes (bybit 426218, spot 483236, fut 483446), one each
$ find data/moat -newermt '2026-08-01 00:00' | head   → shards at 20260801_00 for fut/spot/bybit
fut 16 distinct days (20260717-20260801), bybit 12, spot 12 — zero missing calendar days,
zero 0-byte or <1 KB shards.
```
Depth is 16 days (fut) / 12 (bybit, spot) — up from the 11 measured on 07-31. The tape itself is sound;
every defect found against it (DI-13/14/15/16/31/32) is about supervision, backup and use, not corruption.

**S2. The parquet lake's integrity is genuinely clean — this survived deliberate contrarian testing.**
```
$ .venv/bin/python /tmp/di_verify.py    (279 crypto D1 symbols, full partition scan)
symbols scanned: 279 | errors: {}
duplicate timestamps: 0 across all 279 symbols
within-symbol schema drift: 0 of 279
all parquet dtype: timestamp[ns, tz=UTC]
USDT-perp series: zero missing days (BTCUSDT 2520 rows, 2019-09-08→2026-08-01, 0 gaps, 0 nulls)
```
Only 6 symbols exceed 1% missing days and they are exactly the 6 coin-margined `*USD` legacy names.
FX/equity "gaps" reconcile to market holidays under a business-day calendar. The *storage* layer is a
real strength; the *coverage* and *universe* layers are where this report's findings live.

**S3. Consumption-time freshness contracts (L1.44) are correctly designed where deployed.**
```
$ cat data/freshness_status.json → status OK, n_contracts 5, fresh_fraction 1.0, FOREIGN 28
$ sed -n '32,33p' libs/ops/fresh.py → kind='state' MEANS GUARDIAN-LIVENESS, NEVER OWN-AGE
```
`data/stage_state.json` is 15 days old and correctly **not** flagged, because its contract is
guardian-based (`live_guard.json`, age 0.03h). The instrument also correctly labels pytest rows `FOREIGN`
rather than counting them. The design is right; the deployment is 1.8% (DI-21).

**S4. The cron double-scheduler regression of 2026-07-30 was found and fixed inside 24 hours.**
```
$ crontab -l | grep -n installed → 27: installed 2026-07-31T21:30Z by deploy/reconstitute_cron.sh
$ crontab -l | grep -v '^#' | grep -oP 'scripts/\S+\.py' | sort | uniq -c | sort -rn | head -3
      2 scripts/kimi_hunter.py       (by design)
      2 scripts/check_freshness.py   (residual straggler, DI-7)
      1 scripts/watchdog.py
```
The 2× write-rate regression and the armed recorder double-spawn race are closed. Worth stating plainly:
the sweep→fix loop worked on the highest-severity finding of the previous day.

**S5. The data-asset registry's *schema* is the right model, and it self-reports its own gaps.**
`data_assets.json` carries span/quality/consumers/dependencies/replication/moat_score/`last_validated`
per asset and publishes `unread_long_history`, `unscheduled_collectors` and an absent-count. Three of
this report's findings (DI-9, DI-10, DI-12) were found *by reading fields the registry already computes*.
Its two defects (DI-8's glob blindness, DI-11's missing moat) are corrections to a fundamentally correct
instrument, not a case for replacing it.

## 2. WHAT WE DON'T KNOW (the ignorance ledger)

**Known-unknowns:**
1. **Is there a genuine unread long-history asset?** DI-8 invalidated the existing answer; nobody has
   computed the honest one.
2. **What is the true magnitude of the survivorship bias?** DI-28 establishes the mechanism; the effect
   size on the desk's actual results is unmeasured. → T1.
3. **Can the moat be restored?** No drill has ever run, and there is nothing to restore from (DI-31). → T2.
4. **Why did all five non-crypto classes die on 2026-06-18/19?** The shared bridge is unidentified — this
   report establishes the *fact* and not the *cause* (DI-30). → T3.
5. **How much data have the recorders silently dropped in total?** DI-14 measures one hour (53%). There is
   no failure record (DI-6), so the cumulative figure is unknown for the entire moat lifetime.
6. **Is the frozen 112-symbol cohort recoverable?** These symbols have live Binance history; whether a
   re-ingest would backfill them or whether the top-N filter blocks it is untested.
7. **What is inside the 6.1 GB Bybit tape?** Never read by anything. Its schema, quality and usable
   content are asserted from file listing only.
8. **Does `micro_factory`'s cron line work?** Output is 4.9 days stale; log rotation (DI-33) destroyed
   the evidence either way.

**Suspected unknown-unknowns:** the two instruments the desk uses to see its own data (`data_vitals`,
`data_assets`) were both found wrong *in this single sweep*, and both produce confident, structured,
plausible output when wrong. That is the profile of a class, not two instances. I would assign high
probability that at least one more data-layer gauge is confidently wrong in a way no fence can see —
the prime suspects being anything computing a statistic over a *sample* of a large file (the
`SAMPLE_FILES=6` in `moat_audit.py` and `_MAX_SNAPSHOTS=300` in `run_cost_model.py` are the same
head/sample-truncation shape as DI-1, unaudited).

## 3. WHAT COULD MATTER MOST (ranked by impact × confidence ÷ cost × maintenance)

| # | opportunity | finding | impact | conf | cost | notes |
|---|---|---|---|---|---|---|
| **1** | **Persist `exchangeInfo` daily (all statuses) → point-in-time universe; stop filtering history on present-day status** | DI-28 | **critical** | high | **low** — the call is already made and discarded | ⚑ compounding multiplier: fixes every future cross-sectional study, and is the only item here the whole tier-1 cohort would treat as non-negotiable |
| **2** | **Make the moat backup actually produce, then run a restore drill** | DI-31 | **critical** (unbounded, irreversible) | high | low | script exists; needs a working window + verification that it wrote bytes |
| **3** | **Tail-read instead of head-read in `data_vitals._rows` (`deque(fh, maxlen=N)`)** | DI-1 | high | **certain** | **trivial** (one line) | restores freshness truth on all 5 currently-blind feeds and stops the blindness spreading; also fixes cadence/completeness |
| **4** | **One health artifact with one denominator; delete the second verdict** | DI-19, DI-2, DI-4 | high | high | low | `web/health.json` (5 datasets, `all_ok:true`) vs `data_vitals` (13 DEAD/51) must not coexist; schedule the survivor |
| **5** | **Per-feed write-rate fence (rows/hour, two-sided, with a floor artifact)** | DI-17, DI-14 | high | high | low-med | ⚑ the one fence that would have caught the 2× duplication *and* the 53% depth loss; born with its floor per L1.0/L2.0 |
| **6** | **Diagnose and revive the 5 dead non-crypto asset classes** | DI-30 | high | high | med | 43 days dark; restores the desk's entire orthogonal-source dimension |
| **7** | **Fix consumer matching by path prefix in the registry; add `data/moat` as an asset** | DI-8, DI-11 | med-high | certain | trivial | ⚑ un-corrupts the research-value ranking the desk prioritises from |
| **8** | **Schedule `collect_deribit_surface` hourly, decoupled from the executor** | DI-9 | med-high | high | trivial | irreplaceable forward archive currently at 1 obs/day; TIER1 closer is literally "thickened hourly" |
| **9** | **Mine the moat: first microstructure screen on the Bybit tape** | DI-32 | high (direct alpha) | med | med-high | 80% of desk data, zero readers; the widest genuinely-untested space the desk owns |
| **10** | **Backfill `oi_ls_history` to present (970 days, free bulk source)** | DI-23 | med | high | trivial | one cron line; positioning is a live axis |
| **11** | **Per-job log retention instead of keep-30-across-all** | DI-33 | med | certain | trivial | restores cron→output attribution, which every liveness claim depends on |
| **12** | **Second source for the top-5 feeds (`multiexchange.py` already exists, one backtest-only consumer)** | DI-25 | med-high | high | med | ⚑ moves `cross_validation_available` off 0/51 for the first time |
| **13** | **Widen L1.44 freshness contracts past 5 artifacts; contract `shadow_sleeves.json` first** | DI-21, DI-18 | med-high | high | low | the empty roster loosening the Holm bar is the highest-consequence uncontracted read |
| **14** | **Wire or retire: 3 unread fence outputs, 4 unread heartbeats, 8 write-only stores, 21 zero-reference files** | DI-20, DI-16, DI-24 | med | certain | low | §42: name the production caller or it is not done |
| **15** | **Replace the `_ARTIFACT_KIND` allowlist with a classifier; replace `.exists()` detectors** | DI-3, DI-22 | med | certain | low | both are instance-fixes that must become class-fixes, or they regrow |

## 4. WHAT WE TEST NEXT (concrete, with success criteria and retirement conditions)

**T1 — Quantify the survivorship bias.** Reconstruct a delisted-symbol panel from
`data.binance.vision` for ≥20 names absent from the lake (LUNA, UST, FTT, SRM, MATIC, FTM, WAVES…), then
re-run one existing cross-sectional screen with and without them.
*Success:* a measured delta in mean return / Sharpe attributable to survivorship, with a sign and a
magnitude. *Failure is informative:* if the delta is small the desk learns its universe rule is
tolerable — but it will know rather than assume. *Retire when:* a point-in-time universe file exists and
every screen reads it. *Validation:* the reconstructed names must reproduce known price paths (LUNA→0 in
2022-05).

**T2 — Moat restore drill.** Run `run_moat_backup.py` to a scratch destination; verify byte count,
manifest, and that a randomly chosen shard restores and decompresses to identical content.
*Success:* `backup_status.json` exists with a passing `restore_drill_passed` and ≥7 GB written.
*Retirement:* drill runs monthly on a schedule with its own floor artifact.

**T3 — Non-crypto bridge autopsy.** Identify the writer for `lake/{fx,equity,index,metal,energy}` and
determine what changed on 2026-06-18/19. *Success:* named cause + one restored partition dated after
2026-06-19. *Retirement:* the five classes are in a health artifact with a max-age fence.

**T4 — Head/tail truncation sweep (the class, not the instance).** Audit every analysis that samples a
bounded slice of a large file — `data_vitals._rows` (MAX_ROWS=3000), `moat_audit.SAMPLE_FILES=6`,
`run_cost_model._MAX_SNAPSHOTS=300`, `micro_factory.N_FILES=60` — for whether the slice is
representative or positionally biased. *Success:* each site is either justified in a comment or fixed.
*Why:* DI-1 is one instance; the shape is repo-wide and unaudited.

**T5 — Write-rate fence dry-run.** Compute rows/hour for the last 14 days on all 51 feeds, publish the
distribution, and set two-sided bounds per feed. *Success:* a committed floor artifact + a check that
fails on a 2× or 0.5× excursion. *Validation:* it must retroactively fire on 2026-07-30 23:00Z
(the duplication) and on `20260731_08` (the 53% depth loss) — a fence that cannot detect the two known
events is not calibrated.

**T6 — First moat screen.** Take one microstructure hypothesis with a stated mechanism (e.g. depth
imbalance at the top of book predicting short-horizon signed flow), run it through
`libs.research.axis_screen` on the Bybit tape. *Success:* a verdict either way, logged with its full
construction set per the screen-on-discovery duty. *Why this one:* it converts the desk's largest and
least-used asset into either an axis or a documented empty seam, and both outcomes are deliverables.

**T7 — Frozen-cohort recovery probe.** Attempt a re-ingest of 5 frozen symbols and observe whether the
top-N filter blocks them. *Success:* either 5 symbols advance past 2026-06-21, or a named mechanism for
why they cannot. Cheap, and it decides whether DI-29 is a 112-symbol data loss or a configuration flag.

## PROACTIVE BATTERY (which moves were run, and what each produced)

Per the standing duty, all ten reported — including the ones that produced nothing.

1. **CONTINGENCY BEFORE FAILURE** — produced DI-25 (Binance = 62% of collectors, no replacement named
   for any of them) and DI-31 (the moat's replacement is an empty directory).
2. **ADJACENCY** — the highest-yield move this sweep. Yesterday's fix for the *scheduler* duplication
   was verified (DI-7), and the same *shape* — a fix applied to an instance rather than a class — was
   then found in four more places: DI-3 (event-log allowlist), DI-22 (`.exists()` detectors), DI-24
   (`defi_lending` write-only fixed, pattern not), DI-16 (fabricated docstring, one day after the same
   class was logged).
3. **CONFIG VS OUTCOME** — ran on every liveness claim; forced the whole report onto output artifacts
   after DI-33 showed log files are rotated away. Produced DI-31 (empty backup dir vs "T4 defect
   closed"), DI-32 (`micro_features.json` 4.9d stale under a daily cron), DI-35 (0-byte log, 8 runs/day).
4. **REGRESSION SWEEP — what this report makes worse:** the capability score drops 36% → 31%. That is a
   *measurement* change, not a regression, and I state it explicitly so the ratchet is not read as a
   fall (L1.0(a)). No floor artifact falls as a result of this sweep. Second-order risk: DI-8 retires a
   narrative ("26 years unread") the desk has been citing — anything that cited it needs re-checking.
5. **COST INVERSION** — produced the frontier list: `data.binance.vision`, OKX portal and AWS Public
   Blockchain Data are free primaries for capabilities currently absent (DI-23, DI-28's delisted history,
   stablecoin flows). No paid path is proposed anywhere in this report.
6. **GENERALISE THE RULE** — produced DI-3 explicitly (a rule written for nine filenames is a blind spot
   on every other artifact) and T4 (the head/sample-truncation shape audited as a class, not an instance).
7. **AUTONOMY CHECK** — *has this recovery been SEEN to work?* Moat backup: **no** (DI-31). Restore:
   **never tested, anywhere**. Collector gap repair: **does not exist** — the four `backfill_*`/`reconcile_*`
   scripts are OOS-research and NAV-accounting tools, none is triggered by a missed window.
   `ensure_recorder` is the only real repair automation and its log shows it has never had to act.
8. **NEGATIVE SPACE** — the dedicated section above. Largest item: point-in-time universe, never
   collected, from a call already being made and discarded.
9. **SCOPE THE NEGATIVE RESULT** — applied to the Asian-venue gap and it split cleanly into four
   *different* blockers, none of which is "the capability is unavailable": Upbit = a licence *ruling* a
   human must make (deferred to 2026-08-15); bitFlyer = ToS host WAF/geo-blocked *from this VPS*
   (a route failure, not a capability failure); Naver = an absent credentials file; Bithumb = a lead that
   died before verification. Reporting these as one "Asian data is hard" would have been the exact error
   the move exists to prevent.
10. **RATCHET CHECK** — produced the report's sharpest structural finding: **DI-1's monitor coverage is a
    ratchet running BACKWARDS.** Blind feeds grow monotonically with data accumulation (5 today, +2 this
    week), today's value is not a floor, and *nothing fires when it falls*. Newly-measured quantities in
    this sweep that have no floor artifact and should be born with one (L2.0): feeds-over-blind-threshold,
    crypto-symbols-fresh (62/279), non-crypto-class staleness, moat-bytes-with-a-reader,
    moat-bytes-replicated (currently 0).

## LEDGER / DISPOSITION NOTE

This seat is **read-only**; only this report was written. No `scripts/recommendations.py`,
`track_findings.py`, `blind_spot.py` or `research_memory.py` rows were created from here. Under §35/L2.3
every finding above needs a register row, and under L1.39 the routing is owed in the same cycle — so
the 35 DI-numbered findings and the 15 ranked opportunities are handed to the synthesis seat for
ledgering. Flagged for that seat as **the three that should not wait for a weekly re-rank**: DI-28
(survivorship — corrupts every cross-sectional result produced until fixed), DI-31 (zero moat replicas —
irreversible loss), DI-1 (the freshness instrument's blindness is spreading on a ~1.4-day clock).

Three grades this sweep proposes for `docs/research/TIER1_BENCHMARK.md` per its standing rule
(sweep and register must agree, and the sweep re-grades in the same session): `data_engineering` T2→T3,
`data_moat` T2→T3, `vol_surface_expertise` T3→T4. Evidence is in the EXTERNAL perspective above.

## FINDINGS LEDGER

### DI-1 [NEW, CRITICAL] — THE DATA-QUALITY MONITOR READS THE *OLDEST* 3000 ROWS OF EVERY APPEND-ONLY LOG AND REPORTS THEIR AGE AS THE FEED'S FRESHNESS. IT IS SIMULTANEOUSLY CRYING WOLF ON HEALTHY FEEDS AND STRUCTURALLY BLIND TO THE DEATH OF EVERY FEED THAT MATTERS.

`scripts/data_vitals.py` is the desk's only per-dataset quality instrument (DQS: latency,
completeness, schema integrity, temporal alignment). Its row reader is head-truncated:

```
$ grep -n "MAX_ROWS" scripts/data_vitals.py
39:MAX_ROWS = 3000
102:                if i >= MAX_ROWS:
$ sed -n '97,114p' scripts/data_vitals.py   # _rows()
    for i, ln in enumerate(fh):
        if i >= MAX_ROWS:
            break
```
and freshness is then `age_s = (now - max(ts))` over that window (`data_vitals.py:202`).
For an **append-only log the first 3000 lines are the OLDEST lines**, so `max(ts)` is the newest
timestamp *inside the oldest slice of history* — a number that stops moving the moment a file
exceeds 3000 rows.

**Measured, head-window vs. truth (recomputed with the script's own `_parse_ts`/`_TIME_KEYS` logic):**

| feed | rows | head-window max ts | TRUE max ts | head age_h | true age_h |
|---|---|---|---|---|---|
| bitmex_funding.jsonl | 11148 | 2020-01-21T12:00Z | 2026-07-31T04:00Z | **57204.1** | **20.1** |
| coinmetrics_flows.jsonl | 9876 | 2021-06-29T00:00Z | 2026-07-30T00:00Z | **44616.1** | **48.1** |
| defi_lending.jsonl | 25732 | 2026-07-28T23:17Z | 2026-07-31T23:17Z | **72.8** | **0.8** |
| oi_ls_live.jsonl | 1456 | 2026-07-31T23:32Z | 2026-07-31T23:32Z | 0.5 | 0.5 |
| venue_divergence_shadow.jsonl | 2591 | 2026-08-01T00:00Z | 2026-08-01T00:00Z | 0.1 | 0.1 |

The two files **under** 3000 rows agree exactly; every file **over** 3000 rows is wrong. That is the
mechanism, isolated. `bitmex_funding` is reported 6.5 **years** stale while being 20h old — an error
of 57,184 hours on a feed that landed yesterday.

**Consequence 1 — false DEAD flags.** The live artifact carries `n_dead: 13` of 51, and at least
three of those are pure head-truncation artifacts (`bitmex_funding`, `coinmetrics_flows`,
`defi_lending`; `defi_lending` was 48 minutes old when flagged `DEAD -- FAILOVER`):
```
$ .venv/bin/python -c "import json;d=json.load(open('data/data_vitals.json'));print(d['updated'],d['n_dead'],len(d['collectors']))"
2026-07-31T08:36:19.522501+00:00 13 51
```
Per L1.43 this is the failure mode that kills enforcement: **a gate that cries wolf gets ignored**,
and the real deaths hiding in the same list (`kr_perasset_premium_history` genuinely 96.1h stale,
`cfe_regulated_basis_daily` genuinely 120.1h stale on a 24h cadence) are camouflaged by the noise.

**Consequence 2 — and this is the worse half — the instrument is INERT on large feeds.** Once a file
passes 3000 rows its head window freezes, so its computed age becomes a constant that **cannot
respond to the feed dying**. `defi_lending.jsonl` writes 3676 rows/day; if that collector stopped
right now, `data_vitals` staleness for it would not move by one second. The monitor is blind to
exactly the feeds with the most history.

**Consequence 3 — the blindness is SPREADING on a measurable clock.** Blind = rows > 3000. Today 5 of
51; the two highest-cadence live feeds cross the line this week:

| feed | rows | rows/day (7d) | days until blind |
|---|---|---|---|
| venue_divergence_shadow.jsonl | 2591 | 296.6 | **1.4** |
| oi_ls_live.jsonl | 1456 | 208.0 | **7.4** |
| information_value.jsonl | 1244 | 62.0 | 28.3 |
| experiment_registry.jsonl | 548 | 38.0 | 64.5 |
| breadth_expansion.jsonl | 220 | 31.4 | 88.5 |
| defi_lending / bitmex_funding / coinmetrics_flows / kr_perasset ×2 | — | — | **ALREADY BLIND** |

Every append-only feed crosses 3000 eventually. **Monitor coverage is a monotonically decaying
function of the desk's own data accumulation** — the instrument goes blind to a feed precisely as
that feed becomes valuable. Nothing measures this decay; there is no floor artifact for it (L1.0(a):
a metric with no recorded floor is a defect).

**Fix (cheap, exact):** read the tail, not the head — `collections.deque(fh, maxlen=MAX_ROWS)` is a
one-line change that makes freshness correct and bounded-memory for any file size. Note cadence and
completeness are computed over the same window and are equally head-biased: `defi_lending`'s cadence
is currently inferred from 2026-07-28 traffic, so a genuine cadence change is also undetectable.

---

### DI-2 [NEW, HIGH] — THE SAME FEED APPEARS TWICE IN THE SAME ARTIFACT WITH OPPOSITE VERDICTS. TWO SOURCES OF TRUTH INSIDE ONE FILE.

`data_vitals.json` scores raw files (`score()`) and a hand-listed set of named sources
(`score_extra()`, `data_vitals.py:210-289`) into **one flat `collectors` list**, and two feeds are in
both halves:

```
$ .venv/bin/python -c "...for x in d['collectors']: if 'oi_ls_live' in x['source'] or 'defi_lending' in x['source']: ..."
oi_ls_live.jsonl                     dqs=0.2494  age_s=257     action=DEAD -- FAILOVER
oi_ls_live (Binance positioning)     dqs=1.0     age_s=243     action=OK
defi_lending.jsonl                   dqs=0.25    age_s=217158  action=DEAD -- FAILOVER
defi_lending (Aave/Compound/Morpho)  dqs=1.0     age_s=1157    action=OK
```

Same feed, same instant, `DEAD -- FAILOVER` and `OK` side by side — and for `defi_lending` the two
halves disagree about the feed's age by **216,001 seconds (60 hours)** because one path reads content
timestamps through the head-truncated window (DI-1) and the other reads a heartbeat. The desk has a
standing ban on two sources of truth for one number (the 13,155/4,500 equity split, L1.28a first
run); this is the same defect inside a single JSON file. Any consumer that iterates `collectors` and
takes the first match gets a verdict determined by list order.

The code even documents this exact collision as *already fixed*
(`data_vitals.py:147`: "defi_lending scored 0.250 DEAD on its .jsonl while its heartbeat scored 1.000
OK: the same source, two verdicts, one of them false") — the NEW-FILE GRACE guard was added for it,
but the guard only fires when `<3` distinct timestamps exist, which never applies once a feed has
history. **The recorded fix does not cover the case its own comment describes.**

---

### DI-3 [NEW, HIGH] — "IS THIS AN EVENT LOG?" IS A HAND-MAINTAINED ALLOWLIST OF 9 FILENAMES. EVERY EVENT LOG NOT ON THE LIST IS SCORED AS A DEAD LIVE FEED, BY CONSTRUCTION, FOREVER.

```
$ sed -n '64,76p' scripts/data_vitals.py
# live-feed latency rules produced 9 DEAD flags of which only one was real -- and an alarm that
    "oi_ls_history.jsonl": ("STATIC", ...),
    "cny_otc_premium_history.jsonl": ("STATIC", ...),
    "experiment_registry.jsonl": ("DERIVED", ...),
    "panel_verdicts.jsonl": ("EVENT_LOG", ...),
    "external_panel_log.jsonl": ("EVENT_LOG", ...),
    "micro_audit_log.jsonl": ("EVENT_LOG", ...),
    "mine_conversion_log.jsonl": ("EVENT_LOG", ...),
    "blind_spot_ledger.jsonl": ("EVENT_LOG", ...),
    "information_value.jsonl": ("DERIVED", ...),
```
Nine literal filenames. Event logs written since that list was authored are absent and are therefore
scored with live-feed latency rules, which they cannot pass: `alert_delivery.jsonl` (1.1h old,
`cadence_s: 0.3` inferred from burst writes → `latency: 0.0` → `dqs: 0.0` → `DEAD -- FAILOVER`),
plus `pre_filter_ledger.jsonl` (0.2h old, DEAD), `stage_a_verdicts.jsonl` (DEAD),
`breadth_expansion.jsonl` (DEAD), `signal_halflife.jsonl` (DEAD).

```
$ .venv/bin/python -c "...print(x['source'], x['dqs'], x['cadence_s'], x['action'])"
alert_delivery.jsonl      dqs=0.0   cadence_s=0.3   age_s=3943    action=DEAD -- FAILOVER
pre_filter_ledger.jsonl   dqs=0.0   cadence_s=0.0   age_s=603     action=DEAD -- FAILOVER
```
`alert_delivery.jsonl` is the **pager delivery ledger** — the artifact the monitoring ratchet reads to
prove alerts reach the principal. Its newest row is `{"ts":"2026-07-31T23:48:25Z","channel":"ntfy","ok":true,"detail":"http 200"}`.
It is working, and the data-quality instrument calls it dead.

This is the generalisable defect, and it is the one the desk keeps re-learning: **the previous fix for
this exact symptom was an allowlist, so the defect regrows every time a new artifact appears.** A
classifier (does this file's cadence distribution look bursty / is it registered as a producer in the
scheduler manifest?) fixes the class; nine hardcoded names fix nine instances and decay from day one.
Per the proactive battery move (6) GENERALISE THE RULE: the rule was written for nine files and is a
blind spot on every other.

---

### DI-4 [NEW, HIGH] — THE DATA-QUALITY CENSUS IS NOT SCHEDULED. IT RUNS WHEN A HUMAN REMEMBERS.

```
$ crontab -l | grep -E 'data_vitals|collector_author|collector_health' || echo "NOT SCHEDULED"
NOT SCHEDULED
$ ls -la data/data_vitals.json data/collector_health.json
-rw-rw-r-- 1 quant quant 24735 Jul 31 08:36 data/data_vitals.json
-rw-rw-r-- 1 quant quant   762 Jul 31 08:35 data/collector_health.json
```
Both artifacts are ~15.5h old at the time of this audit and nothing on the 121-line crontab refreshes
them. This is the desk's own OUTCOME-NOT-CONFIG lesson pointed at its data layer: the instrument
exists, is well-designed in parts, and **produces on human presence** — exactly the failure that left
forward clocks frozen for 11.5 days when `watchdog.py` was the only scheduler (documented in the
crontab's own header comments). Under L1.28c every cadence must be a *decision*; this one has no
cadence at all, so its ceiling type is unnamed and its utilisation is, per L1.28a, zero by default.

`data/collector_health.json` — the narrower live-clock monitor — covers **4 clocks**
(`kimchi_premium`, `stablecoin_supply`, `cny_premium`, `onchain_activity`) against **33 collector
scripts** and **51 scored feeds**:
```
$ ls scripts/ | grep -cE '^(collect|ingest|fetch|dl_|run_recorder|download)'
33
$ .venv/bin/python -c "import json;print([c['clock'] for c in json.load(open('data/collector_health.json'))['collectors']])"
['kimchi_premium.jsonl', 'stablecoin_supply.jsonl', 'cny_premium.jsonl', 'onchain_activity.jsonl']
```
One of the four monitored clocks (`kimchi_premium`) feeds an axis **refuted at full depth on
2026-07-30** and another is annotated in the artifact itself as `"(retired axis -- input store only)"`.
So half the desk's continuously-monitored data surface is watching retired ground.

---

### DI-5 [NEW, MEDIUM] — PROVENANCE IS A DECLARED, EMPTY COLUMN: 32/51 FEEDS "UNKNOWN", 46/51 WITH NO REGENERABILITY OR TIMESTAMP-VERIFICATION RECORD, AND CROSS-VALIDATION AVAILABLE ON ZERO.

The schema is right; the population is not.
```
$ .venv/bin/python -c "...prov histogram / counts..."
provenance.collection histogram: {'UNKNOWN': 32, 'JSON_STATE': 6, 'EVENT_LOG': 5, 'DERIVED': 2,
  'coinmetrics community API': 1, 'self-recorded multi-venue poll': 1, 'public chain API': 1,
  'binance futures API': 1, 'wayback-cdx-replay of history.btc126.com (UNCOMMITTED one-off)': 1,
  'DIR_GLOB': 1}
regenerable recorded:        5 / 51
timestamp_verified recorded: 5 / 51
cross_validation_available TRUE: 0 / 51
```
Three consequences that bear directly on research validity:
1. **`timestamp_verified` is null for 46/51 feeds.** The screen-on-discovery duty makes timestamp
   alignment a *voiding* condition ("a daily FX close is NOT the crypto UTC close" — unstated
   alignment voids the screen). The desk has no per-feed record of whether alignment was ever
   checked, so every cross-source screen asserts alignment on faith.
2. **`regenerable` is null for 46/51.** Nothing distinguishes a feed that can be re-downloaded from
   one that is irreplaceable if lost — which is the input a backup policy must be built on. One
   entry is explicitly flagged `UNCOMMITTED one-off` (`cny_otc_premium_history.jsonl`, a
   wayback-cdx replay): a non-regenerable, uncommitted dataset, named as such, with no backup duty
   attached to that fact.
3. **`cross_validation_available` is FALSE on all 51.** Not one desk feed has a second independent
   source to check it against. That is the vendor-concentration finding stated as a data property
   (see the collector-architecture section): every number this desk trades on is single-sourced and
   unverifiable against anything.

---

### DI-6 [NEW, MEDIUM] — `collector_attempts.jsonl` HAS BEEN A ZERO-BYTE FILE SINCE 2026-07-27. THE COLLECTOR-AUTHORING ORGAN HAS NEVER PRODUCED, AND IT IS NOT SCHEDULED.

```
$ ls -la data/collector_attempts.jsonl
-rw-rw-r-- 1 quant quant 0 Jul 27 14:04 data/collector_attempts.jsonl
$ grep -rn "collector_attempts" scripts/ libs/ --include=*.py
scripts/collector_author.py:46:DONE = ROOT / "data/collector_attempts.jsonl"
$ crontab -l | grep collector_author || echo NOT SCHEDULED
NOT SCHEDULED
```
`collector_author.py` is the organ that writes new collectors — the desk's mechanism for converting a
*discovered* source into an *ingested* one. It has exactly one writer reference, an empty output, no
schedule, and five days of silence. This is the built-never-wired class inside the acquisition
pipeline itself (§42 "an orphan is fixed by a caller, not by deletion" — name the production caller;
there is none). It also means the SCREEN-ON-DISCOVERY duty's upstream half has no automation: every
new axis requires a human-driven session to become a collector.

---

### DI-7 [NEW, LOW/MEDIUM] — THE CRON RECONSTITUTION FIXED THE DOUBLE-SCHEDULER (DI-1 of 07-31) BUT LEFT ONE DUPLICATED LINE OUTSIDE THE MANAGED BLOCK.

Movement check on yesterday's critical finding — **largely fixed**:
```
$ crontab -l | grep -n 'installed'
27:# installed 2026-07-31T21:30Z by deploy/reconstitute_cron.sh (gap #58)
$ crontab -l | grep -v '^#' | grep -oP 'scripts/[a-z_0-9]+\.py' | sort | uniq -c | sort -rn | head -3
      2 scripts/kimi_hunter.py
      2 scripts/check_freshness.py
      1 scripts/watchdog.py
```
The legacy block's collector duplicates (watchdog, venue_divergence, recorders, defi_lending,
oi_ls_live, coinmetrics, dl_oi_ls_universe, ingest_axes) are gone — the 2× write-rate regression and
the armed recorder double-spawn race are closed. Residual:
```
$ crontab -l | grep -n check_freshness
25:52 * * * * ... scripts/check_freshness.py >> data/cro_ai_logs/freshness.log 2>&1
60:52 * * * * ... scripts/check_freshness.py >> data/cro_ai_logs/freshness.log 2>&1
```
Line 25 is a legacy straggler *above* the managed-block marker at line 26; line 60 is the manifest
copy. Both fire at :52 every hour with no flock, writing the same log. Harmless in cost (a fence, not
a collector) but it falsifies the "single scheduler" property that DI-1's fix was supposed to
establish, and `check_scheduler_manifest.py` evidently does not catch a duplicate that sits outside
the managed block. `kimi_hunter.py` ×2 is by design (different cadences/args — daily deep vs. periodic).

---

### DI-8 [NEW, CRITICAL] — "WE OWN 26 YEARS OF DATA THAT NOTHING READS" IS AN INSTRUMENT ARTIFACT. THE REGISTRY REGISTERS PARTITIONED ASSETS UNDER A GLOB PATH, GREPS FOR THAT LITERAL STRING, FINDS NOTHING, AND SCORES THEM UNREAD — THEN PAYS THEM A +10 RESEARCH-VALUE BONUS FOR IT.

`data/data_assets.json` (61 assets, rebuilt daily at 04:27 `--deep`, the desk's data registry) publishes a
headline gap field:
```
$ .venv/bin/python -c "import json;d=json.load(open('data/data_assets.json'));print(d['unread_long_history'])"
['lake_crypto', 'lake_futclose_daily', 'lake_oi_ls_daily', 'lake_fx', 'lake_equity', 'lake_index', 'lake_metal', 'lake_energy']
```
Those are the desk's eight highest-research-value assets — `lake_crypto` alone is 5609 days × 278 symbols
× 362,145 rows, `research_value 97.8`, the top of the register. All eight report **zero consumers**.

**The eight "unread" assets are exactly the eight assets registered under a glob path, and a glob path
cannot match:**
```
$ .venv/bin/python -c "...for x in assets if kind=='partitioned'..."
lake_crypto          path=data/lake/bronze/crypto/**          consumers=0  rval=97.8
lake_futclose_daily  path=data/lake/bronze/futclose_daily/**  consumers=0  rval=83.9
lake_oi_ls_daily     path=data/lake/bronze/oi_ls_daily/**     consumers=0  rval=83.9
lake_fx              path=data/lake/bronze/fx/**              consumers=0  rval=75.7
lake_equity          path=data/lake/bronze/equity/**          consumers=0  rval=72.0
lake_index           path=data/lake/bronze/index/**           consumers=0  rval=70.4
lake_metal           path=data/lake/bronze/metal/**           consumers=0  rval=70.4
lake_energy          path=data/lake/bronze/energy/**          consumers=0  rval=70.3
$ grep -rn 'data/lake/bronze/crypto/\*\*' scripts/ libs/ --include=*.py | wc -l
0
```
Consumer detection is a literal-string grep (`libs/research/data_registry.py:356-381`
`_writers_and_readers`), so the `**` suffix guarantees zero hits for every partitioned asset. It is a
100%-constant result — the welded-gate pattern the desk hunts (L1.43), inside its own data registry.

**The truth, measured independently:**
```
$ grep -rln "lake/bronze\|libs\.data\.lake\|read_bronze\|load_bronze" scripts/ libs/ --include=*.py | wc -l
53
```
**53 scripts read the bronze lake** — `run_discovery.py`, `build_labels.py`, `run_carry_harvest.py`,
seven `screen_*` scripts, `run_cashcarry_backtest.py`, `run_crypto_portfolio.py`, `max_audit.py` and
more. The lake is one of the most-read things in the estate. `unread_long_history` has a **100%
false-positive rate**.

**Why this is worse than a cosmetic bug — it corrupts the desk's research priority ordering.** The
research-value formula pays a bonus for being unread:
```
$ sed -n '344,352p' libs/research/data_registry.py
    span_pts = min(60.0, days / 365.0 * 20.0)
    breadth_pts = min(30.0, breadth / 10.0)
    unread = 10.0 if (days > 365 and not asset.consumers) else 0.0   # #77's paralysis bonus
    return round(moat, 1), round(min(100.0, span_pts + breadth_pts + unread), 1)
```
Every glob-pathed asset collects the +10 automatically and permanently, so the registry **systematically
over-ranks partitioned lake assets and under-ranks flat files**, through a channel that looks like
evidence. This is the desk's own named cautionary class (L1.25): the 420/0 record was an instrument
artifact misread as a fact about the market; `unread_long_history` is an instrument artifact misread as
a fact about the desk's own data paralysis. It has been feeding the "we collect and never convert"
narrative with a number that measures a glob character.

**Fix:** match consumers by path *prefix* (strip the `**`) or resolve through the lake helper module —
`libs/research/data_registry.py:378`. One-line class of change; then re-derive whether any genuine
unread long-history asset exists (the honest version of this finding is currently unknown, which is
itself the point).

---

### DI-9 [NEW, HIGH] — THE DESK'S ONLY OPTIONS / VOL-SURFACE DATASET IS A SIDE EFFECT OF THE TRADING EXECUTOR, IT IS FORWARD-ARCHIVE-ONLY (UNRECOVERABLE IF MISSED), AND IT HAS 15 GAPS >24h IN 35 DAYS.

`collect_deribit_surface.py` appears **nowhere in cron** and nowhere in the manifest:
```
$ crontab -l | grep -c deribit_surface
0
$ grep -n "deribit" ops/crontab.manifest
33:# paste closes -- e.g. the unknown 00:02 writer of deribit_surface/crypto_regime
```
The manifest itself records the writer as **unknown**. It is not unknown — it is the executor:
```
$ grep -rn "collect_deribit_surface" scripts/ libs/ | grep -v '^scripts/collect_deribit_surface.py'
scripts/run_crypto_testnet.py:65:     "scripts/collect_deribit_surface.py", "scripts/classify_regime.py",
scripts/run_cashcarry_executor.py:85: "scripts/collect_deribit_surface.py", "scripts/classify_regime.py",
```
**Data acquisition is coupled to trading activity.** The vol surface is archived only when the cash-carry
executor's flywheel runs. This inverts the correct dependency: the book is frozen or de-risked precisely
during the stress regimes when a vol surface is most informative, so the feed thins exactly when its
information value peaks. It also violates L1.28b(f) in spirit — collectors run at full cadence
unconditionally, never gated on another organ's state.

**And the data is irreplaceable.** `libs/data/deribit.py:48`: *"Per-strike IV has NO free history, so this
is archived FORWARD."* Every missed observation is permanently lost — there is no backfill.

**Measured cadence on an irreplaceable forward archive:**
```
$ .venv/bin/python -c "df=pd.read_parquet('data/deribit_surface.parquet')..."
rows 78  span_days 35   per-currency {'BTC': 39, 'ETH': 39}
BTC obs 39   median gap 0 days 23:58:03   max gap 4 days 18:30:21
gaps > 24h: 15
5 largest gaps:
  2026-06-28 14:28 -> 2026-07-03 08:58  = 4 days 18:30
  2026-07-13 00:02 -> 2026-07-16 08:08  = 3 days 08:06
  2026-06-26 00:15 -> 2026-06-27 20:18  = 1 day 20:03
daily obs (last 14d): 1,1,1,1,1,2,2,2,1,1,1,1,1,1
```
**39 observations in 35 days — one per day — against a TIER1 register whose stated closer for
`vol_surface_expertise` (T3) is literally "Deribit collector thickened hourly".** At 1/day the clock
started 2026-06-26 needs decades to support any surface-dynamics study; at hourly it would already hold
~840 observations instead of 39. The 8.1 days lost to the two largest gaps are gone forever.
Optiver/SIG is the cohort exemplar here and the gap is not methodology — it is a missing cron line.

---

### DI-10 [NEW, MEDIUM] — THREE ORGANS READ A STORE THAT HAS BEEN ZERO BYTES FOR FOUR DAYS, AND EIGHT REGISTERED ASSETS DO NOT EXIST AT ALL.

```
$ ls -la data/suggestion_ledger.jsonl && wc -l data/suggestion_ledger.jsonl
-rw-rw-r-- 1 quant quant 0 Jul 28 11:23 data/suggestion_ledger.jsonl
0 data/suggestion_ledger.jsonl
$ .venv/bin/python -c "...consumers of suggestion_ledger..."
['scripts/kimi_hunter.py', 'scripts/meta_architect.py', 'scripts/research_exchange.py']
```
Three organs — including the second-family hunter and the meta-architect — read a **zero-byte** store
with **no writer registered** (`collector: None`). Whatever cross-organ suggestion flow this was meant
to carry has carried nothing since 2026-07-28. Note the contrast with DI-6: `collector_attempts.jsonl`
is zero-byte with a writer and no readers; this one is zero-byte with readers and no writer. Both halves
of the same broken pipe exist, separately.

Eight registered assets have no file on disk at all:
```
$ .venv/bin/python -c "...print(d['counts'])"
{'assets': 61, 'measured': 47, 'absent': 8}
absent: ['capital_events', 'code_audit', 'fusion_trials', 'gen_diversity_history',
         'hypothesis_queue', 'knowledge_graph_edges', 'subaccount_ledger', 'variation_ledger']
```
`capital_events` is named in doctrine as a survival-relevant ledger (the Alameda control-group lesson:
"the capital-event ledger"); `hypothesis_queue` and `variation_ledger` are generation-side stores;
`knowledge_graph_edges` and `fusion_trials` are knowledge-reuse stores — the `knowledge_reuse_read_side`
layer is graded **T4** in the TIER1 register, and this is the physical evidence for that grade. 13% of
the registry is a declaration with nothing behind it.

---

### DI-11 [NEW, MEDIUM] — THE 7.2 GB MOAT — 82% OF ALL DESK DATA — IS NOT IN THE DATA ASSET REGISTRY.

```
$ du -sh data/moat data/lake
7.2G    data/moat
1.5G    data/lake
$ .venv/bin/python -c "...[x['id'] for x in assets if 'moat' in x['id'].lower() or 'moat' in str(x.get('path','')).lower()]"
['cashcarry_trades']
```
The registry enumerates 61 assets covering the 1.5 GB lake and the small flat files, and contains **no
entry for `data/moat`** (the sole hit is a substring collision on an unrelated asset). The desk's largest
dataset — its self-recorded order-book/trade tape, the one asset whose `replication` grade would *not*
be `public-refetchable`, i.e. **the only genuine moat in the estate** — is invisible to the instrument
that exists to score moat value.

Consequences: (a) `moat_score` reads 0.0 on 56 of 61 assets and the registry cannot see the one asset
that would score high, so the entire moat dimension measures nothing; (b) no span, quality, gap,
`last_validated`, replication grade or consumer count for 82% of desk data; (c) L1.28a — unmeasured
counts as zero: 7.2 GB of irreplaceable self-recorded data has no measured utilisation at all.

---

### DI-12 [NEW, MEDIUM] — `last_validated` FROZE 41 DAYS AGO ON EVERY NON-CRYPTO LONG-HISTORY ASSET.

```
$ .venv/bin/python -c "...sorted by span..."
cot_zcache      span 9667d  last_validated 2026-06-21
lake_fx         span 9665d  last_validated 2026-06-20
lake_metal      span 6745d  last_validated 2026-06-21
lake_energy     span 6065d  last_validated 2026-06-20
lake_index      span 5066d  last_validated 2026-06-21
lake_equity     span 2965d  last_validated 2026-06-21
swap_log        span    1d  last_validated 2026-06-21
```
Against `lake_crypto` (2026-07-16) and the live flat feeds (2026-07-31). The pattern is clean: the
**non-crypto** long-history assets — 26 years of FX, 18 of metals, 16 of energy, 13 of index, 8 of
equity, and the 26-year COT cache — froze together on 2026-06-20/21 and nothing has re-validated them in
41 days. These are exactly the cross-asset breadth the doctrine calls for (fusion of 3+ orthogonal
sources, L1.11) and the widest untested space the desk owns. Whether they are stale-but-fine or silently
broken is unknown — which is the finding.

---

### DI-13 [NEW, CRITICAL] — ALL THREE MOAT RECORDERS SWALLOW 100% OF FETCH FAILURES AND THEN WRITE THEIR HEARTBEAT UNCONDITIONALLY. 82% OF DESK DATA SITS BEHIND A LIVENESS SIGNAL THAT CANNOT GO RED.

```
$ sed -n '230,262p' scripts/run_recorder.py
        for sym in symbols:
            try:
                d = _get("/fapi/v1/depth", f"symbol={sym}&limit=20")
                buf[sym].append({...})
            except Exception:
                pass                                # transient venue hiccup: skip one tick
        ...
                    trades = _get("/fapi/v1/aggTrades", q)
                    ...
                except Exception:
                    pass
        ...
        with contextlib.suppress(OSError):
            _HB.write_text(datetime.now(tz=UTC).isoformat(), "utf-8")
```
The heartbeat write is at the **end of the loop body, outside every success path**. Depth failure →
`pass`. Trade failure → `pass`. Disk failure → `buf.clear()`. Then the heartbeat is stamped regardless.
**A recorder whose every single fetch fails is indistinguishable, from the outside, from a healthy one.**
Same pattern in `run_recorder_spot.py:246,263` and `run_recorder_bybit.py:118` (`return None  # a dropped
poll is a gap, never a crash`).

This is the desk's own SILENT-EXCEPT defect lens (L1.40) sitting on **7.2 GB / 82% of all desk data** —
`bybit 5.8G, fut 966M, spot 531M` — and on the only asset in the estate that is *not*
public-refetchable. Every dropped poll is permanently unrecoverable, and none of them is counted
anywhere. There is no artifact recording a single recorder fetch failure:
```
$ ls -la data/collector_attempts.jsonl
-rw-rw-r-- 1 quant quant 0 Jul 27 14:04 data/collector_attempts.jsonl
```

---

### DI-14 [NEW, CRITICAL] — THE RECORDERS DO NOT HONOUR THE BAN LATCH. DURING THE 2026-07-31 418 THE FUT TAPE LOST 53% OF AN HOUR'S DEPTH SNAPSHOTS AND NOTHING RECORDED IT.

```
$ for f in scripts/run_recorder.py scripts/run_recorder_spot.py scripts/run_recorder_bybit.py; do
    echo "$f BAN_UNTIL=$(grep -c BAN_UNTIL $f) crypto_source=$(grep -c crypto_source $f)"; done
scripts/run_recorder.py       BAN_UNTIL=0 crypto_source=0
scripts/run_recorder_spot.py  BAN_UNTIL=0 crypto_source=0
scripts/run_recorder_bybit.py BAN_UNTIL=0 crypto_source=0
```
The ban latch (`data/BINANCE_BAN_UNTIL`, honoured by `libs/data/crypto_source.py`) is invisible to all
three recorders — they carry their own `_get`. During an IP ban the recorders keep hammering the venue,
**extending the very ban the latch exists to end**.

**Measured at the tape** (depth snapshots/hour, fut BTCUSDT, 2026-07-31; the 418 window was ~08:35–09:31Z):
```
$ for h in 05 06 07 08 09 10 11 12; do echo "$h $(zcat data/moat/fut/BTCUSDT/20260731_$h.jsonl.gz | grep -c '"k":"d"')"; done
05 355   06 359   07 355   08 167   09 431   10 355   11 350   12 357
```
Hour 08 = **167 vs a 355 baseline — 53% of that hour's order-book depth is simply missing** from an
irreplaceable self-recorded tape. Hour 09's 431 is the catch-up overshoot. No log line, no artifact, no
page: the loss is visible only by decompressing the shards and counting rows, which is what this audit
had to do. This is DI-13's silent-except and the missing write-rate fence (DI-17) producing a real,
permanent, measured data loss — not a hypothetical.

---

### DI-15 [NEW, HIGH] — THE FUT RECORDER RUNS AT 49% OF ITS OWN CONFIGURED CADENCE AND ITS DOCSTRING OVERSTATES IT BY 10×. NOTHING MEASURES EITHER.

```
$ grep -n "_DEPTH_EVERY_S" scripts/run_recorder.py
111:_DEPTH_EVERY_S = 5.0   # 1.0 -> 4.0 when symbols went 5 -> 20 (weight budget)
$ sed -n '5p' scripts/run_recorder.py
perps: top-20 order book at ~1s cadence + every aggTrade.
```
Configured 5.0 s → **720 snapshots/hour** nominal. Measured **355/hour** (above, eight consecutive clean
hours, tight variance 350–359). The recorder achieves **49% of its configured rate**, steadily, and the
module docstring still advertises "~1s cadence" — **9.9% of the documented rate**.

The loop is `time.sleep(max(0.0, _DEPTH_EVERY_S - (time.time() - t0)))`, so the shortfall is 20 serial
symbol fetches taking ~5 s of wall clock on top of the 5 s sleep. This is not a bug in the sense of
crashing — it is a **capability running at half its declared ceiling with no measurement** (L1.28a:
unmeasured utilisation counts as zero; "we are at max" requires a documented push that failed). Async or
batched depth fetches would roughly double the desk's highest-value proprietary dataset's resolution at
zero marginal data cost.

---

### DI-16 [NEW, HIGH] — FOUR COLLECTOR HEARTBEATS ARE WRITTEN EVERY CYCLE AND READ BY NOTHING. ONE RECORDER'S DOCSTRING CLAIMS AN ALERT THAT DOES NOT EXIST.

```
$ sed -n '22,23p' scripts/run_recorder_spot.py
Supervision: liveness = data/recorder_spot_heartbeat (alerted if stale); a 10-minute cron
pgrep-guard respawns it (mirrors run_recorder_bybit.py).
$ grep -rn "recorder_spot_heartbeat\|recorder_bybit_heartbeat" scripts/ libs/ --include=*.py | grep -v run_recorder
(no output)
```
**"alerted if stale" is a fabricated docstring** — no alerter reads that file. `run_alerts.py` reads only
`data/recorder_heartbeat` and `data/cashcarry_exec_heartbeat`; `recorder_spot_heartbeat`,
`recorder_bybit_heartbeat`, `oi_ls_live_heartbeat` and `defi_lending_heartbeat` are written forever and
consumed by nothing. The **5.8 GB Bybit tape — the single largest dataset on the desk — has no liveness
alert at all**, only a pgrep respawn that cannot tell a hung recorder from a working one (and per DI-13
the heartbeat could not tell either).

This is the same inert-fix class the desk logged on 2026-07-31 (fabricated docstring + no parity test).
It recurred, in the same subsystem, within one day.

---

### DI-17 [CARRIED, UNMOVED] — DI-13 OF 2026-07-31 STANDS: NO FEED HAS A WRITE-RATE FENCE. THE ONLY TWO RATE CHECKS ARE DAILY-GRANULARITY, COVER 4 OF ~29 FEEDS, ARE ONE-SIDED, AND ARE UNSCHEDULED.

```
$ grep -rniE "rows_per_hour|rows/h|write_rate|row_rate|RATE_DROP|expected_rows" scripts/ libs/ tests/
scripts/collector_monitor.py:40:RATE_DROP = 0.5           # days-present vs days-spanned, 4 clocks, DAILY granularity, not on cron
scripts/data_vitals.py:175:    comp = min(1.0, len(recent) / 20.0)   # clamped at 1.0 -> a DOUBLING scores 1.0
```
`data_vitals`'s completeness is `min(1.0, ...)`: **a feed that doubles its write rate scores a perfect
1.0 and is invisible by construction** — which is precisely the failure that went undetected for a full
day when the duplicate scheduler doubled three feeds on 2026-07-30. Both checks are unscheduled (DI-4).
The DI-14 53% depth loss is the same blindness pointed the other way.

---

### DI-18 [NEW, CRITICAL — CROSS-SUBSYSTEM] — AN EMPTY, NINE-DAY-FROZEN JSON FILE IS AN INPUT TO THE MULTIPLE-TESTING DENOMINATOR, AND THE ERROR DIRECTION IS TOWARD PHANTOM EDGES.

```
$ ls -la data/shadow_sleeves.json && cat data/shadow_sleeves.json
-rw-rw-r-- 1 quant quant 2 Jul 22 22:50 data/shadow_sleeves.json
[]
$ grep -n "_SLEEVE_ROSTER\|_OUT" libs/research/slot_registry.py
57:_SLEEVE_ROSTER = "data/shadow_sleeves.json"
58:_OUT = "data/forward_slots.json"
100:    roster = _read_json(_SLEEVE_ROSTER)
```
`slot_registry.py` composes the forward-slot cohort — the `m` in the Holm correction — from several
sources, one of which is this file. It has been `[]` since 2026-07-22. The module's own header:

> *"Measured 2026-07-30: the axis clocks applied holm_bar(4)=2.24 while the true cohort was 12-13
> (bar 2.64-2.67) — alpha 0.0125 per clock against an intended 0.05/13=0.0038, a realized family-wise
> error rate ~3.2x the design. **Understating m LOOSENS the bar, so the error ran in the PHANTOM-EDGE
> direction. Three deep sweeps (2026-07-26/28/29) each found this and each carried it.**"*

Four sweeps now. It belongs in this report because it is a **data-freshness defect with a validation
blast radius**: a stale empty file silently loosening the promotion bar is the exact L1.44
STALE-CONSUMED pattern, and it is the highest-consequence instance of it on the desk. The file is not
under a freshness contract (DI-21). Whether the roster *should* be non-empty is the open question — but
an empty roster and a broken writer are indistinguishable today, and only one of them is safe.

---

### DI-19 [NEW, MEDIUM] — TWO HEALTH VERDICTS WITH OPPOSITE SIGNS. THE DASHBOARD SHOWS THE NARROWER ONE.

```
$ .venv/bin/python -c "import json;d=json.load(open('web/health.json'));print(d['all_ok'], len(d['datasets']), d['updated'])"
True 5 2026-08-01T00:09:20Z
$ .venv/bin/python -c "import json;d=json.load(open('data/data_vitals.json'));print(d['n_dead'],'/',len(d['collectors']),d['updated'])"
13 / 51 2026-07-31T08:36:19Z
```
`web/health.json` — the artifact on the dashboard, refreshed every 3 minutes inside the watchdog —
reports `all_ok: true` over **5 datasets** (`oi_ls_taker`, `market_breadth`, `stablecoin_flows`,
`fred_macro`, `liquidations`). `data_vitals.json` reports **13 DEAD of 51** but is 15.5h stale and
unscheduled. Neither covers the moat. Two sources of truth for "is the data healthy", the green one is
the one anybody actually sees, and its denominator is 5 of ~60 datasets — **8% coverage reported as
100% health**. Per L1.28a an unmeasured ceiling counts as zero; here it is worse, it counts as green.

---

### DI-20 [NEW, MEDIUM] — THREE CRON-SCHEDULED FENCES WRITE NIGHTLY ARTIFACTS THAT NOTHING READS.

```
$ for a in organ_liveness sizing_derivation return_targeting; do grep -rn "data/$a.json" scripts/ libs/ tests/ api/ app/ --include=*.py; done
scripts/check_organ_liveness.py:205:    out = _ROOT / "data/organ_liveness.json"
scripts/check_sizing_derivation.py:185:    out = _ROOT / "data/sizing_derivation.json"
scripts/check_return_targeting.py:154:    out = _ROOT / "data/return_targeting.json"
$ ls -la data/organ_liveness.json data/sizing_derivation.json data/return_targeting.json
... 11629 Aug  1 00:05 data/organ_liveness.json
...  4846 Aug  1 00:05 data/sizing_derivation.json
...   737 Aug  1 00:05 data/return_targeting.json
```
One reference each — the writer. Compare the wired fences: `build_standard`, `law_families`,
`exploration_status`, `change_window`, `law_gate`, `replacement_rate` are all in
`check_fence_yield.py:53-64`, and `calibration_status`, `conversion_status`, `freshness_status` are all
consumed by `run_max_push.py:239,294,314`. These three were built to the same standard and **never
wired to a caller** — 11.6 KB of fresh organ-liveness evidence produced nightly and opened by nobody.
§42: "an orphan is fixed by a caller, not by deletion. Before calling any knob, governor or helper done,
name the production caller." There is none for these three.

---

### DI-21 [NEW, MEDIUM] — THE L1.44 FRESHNESS LEDGER COVERS 5 OF ~279 ARTIFACTS AND 85% OF ITS ROWS ARE PYTEST TEMP PATHS.

```
$ wc -l data/freshness_contracts.jsonl        → 33
$ grep -c '/tmp/pytest' data/freshness_contracts.jsonl → 28
$ cat data/freshness_status.json
"status": "OK", "n_contracts": 5, "fresh_fraction": 1.0,
"by_verdict": {"FRESH": 5, "STALE-CONSUMED": 0, "STALE-UNREAD": 0, "MISSING": 0, "FOREIGN": 28}
```
Five real contracts, from two callers (`run_cashcarry_executor`, `run_conviction_trader`). The law
that exists to catch stale inputs steering live decisions currently watches **1.8% of the estate**, and
`STALE-CONSUMED: 0` is true only because almost nothing is under contract — the census in this sweep
found at least eight genuine stale-consumed pairs (DI-18, DI-22, `cot_zcache` at 41d read by
`run_cot_screen.py`, `crypto_trades.sqlite` at 33d read by three scripts, `sor.sqlite` 0-tables as the
dashboard's default `--db`, `batch_*_screen.json` at 8d read by `data_sanity.py`).

Separately: **the production contract ledger is polluted by the test suite** — 28 of 33 rows are
`/tmp/pytest-of-quant/pytest-29*/...` paths. The instrument correctly labels them `FOREIGN` rather than
counting them, which is good design, but a fence whose ledger is 85% test garbage will not survive
contact with growth, and the writes prove pytest runs mutate a production artifact.

---

### DI-22 [NEW, MEDIUM] — A `.exists()` DETECTOR REPORTS FOUR CAPABILITIES GREEN OFF FILES 20–41 DAYS COLD, INCLUDING ONE THE DAILY REGISTRY BUILD RENAMED A MONTH AGO.

```
$ grep -n "data_registry\|executive_kpis\|black_swan_library" scripts/research_cycle.py
119:        "data_registry": (_ROOT / "data/data_registry.json").exists(),
121:        "executive_kpis": (_ROOT / "data/executive_kpis.json").exists(),
122:        "black_swan_library": (_ROOT / "data/black_swan_library.json").exists(),
$ ls -la data/data_registry.json data/executive_kpis.json data/black_swan_library.json
... Jul  8 23:07 data/data_registry.json          (24 days)
... Jul  8      data/executive_kpis.json          (23 days)
... Jul 11      data/black_swan_library.json      (20 days)
$ grep -n "OUT" scripts/build_data_registry.py
27:OUT = ROOT / "data/data_assets.json"
```
The nightly `build_data_registry.py --deep` writes **`data_assets.json`**; the detector checks
**`data_registry.json`**, a file abandoned on 2026-07-08. It has reported green for 24 days off an
orphaned filename. The same dict block in the same file already carries the desk's own lesson verbatim:

> *"A FILE-EXISTENCE detector marked this done on 2026-07-18 and kept marking it done for 8 days while
> the connector and the stage machine had no production caller at all — measuring the proxy (a file on
> disk) instead of the thing the row names"*

One row was upgraded to a real check; **four rows in the same dict were left as `.exists()` and three of
those four now point at cold files.** The fix was applied to the instance, not the class — the same
shape as DI-3. This is the OUTCOME-NOT-CONFIG lesson failing inside the code that documents it.

---

### DI-23 [NEW, MEDIUM] — A BACKFILL STOPPED 2.6 YEARS SHORT OF ITS OWN TARGET, NOTHING READS THE RESULT, AND NOTHING REPORTS THE GAP.

```
$ head -c 95 data/oi_ls_history.jsonl;  tail -c 95 data/oi_ls_history.jsonl
{"date": "2021-06-01", "oi_value": 1383639090.74, "ls_ratio": 1.13461, ...}
{"date": "2023-12-03", "oi_value": 3236379444.75, "ls_ratio": 1.18112, ...}
$ sed -n '13,16p' scripts/dl_metrics_history.py
OUT   = Path(".../data/oi_ls_history.jsonl")
BASE  = "https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT"
start = date(2021, 6, 1)
end   = datetime.now(tz=UTC).date() - timedelta(days=1)
```
The downloader targets 2021-06-01 → yesterday; the file ends **2023-12-03**. ~970 days of BTC OI /
long-short / taker-ratio history are missing from a **free, still-live, bulk-downloadable source**
(`data.binance.vision`). The script is unscheduled (last run 8.1 days ago), the file has zero consumers,
and `data_vitals` classifies it `STATIC -- historical backfill, ends 2023-12-03 BY DESIGN` — the
truncation has been **annotated as intentional in the monitoring allowlist**, which is how it stopped
being a gap. Positioning data is one of the desk's live axes (`M_FORCED_DELEVERAGE`); this is 2.6 years
of its history available for the cost of a cron line.

---

### DI-24 [NEW, MEDIUM] — 21 FILES (9.97 MB, 28% OF THE FLAT-FILE ESTATE BY BYTES) HAVE NO WRITER AND NO READER ANYWHERE IN THE REPO.

Census (`find data -maxdepth 2`, 279 artifacts, 36.0 MB; classes LIVE 165 / STALE 60 / FROZEN 39 /
DEAD 15). Zero python reference anywhere:
```
data/unlock_events.json                    5,216,307  FROZEN 2026-07-24
data/kr_perasset_panel_400d.json           2,859,327  STALE  2026-07-30
data/kr_perasset_premium_rebuilt.jsonl       548,588  STALE  2026-07-30
data/kr_perasset_legs_raw.json               485,925  STALE  2026-07-30
data/kr_perasset_premium_history.jsonl       473,204  STALE  2026-07-28
data/cfe_crypto_settlements.jsonl            216,945  STALE  2026-07-28
data/8btc_era_thread_catalog.jsonl           110,458  STALE  2026-07-28
data/cfe_regulated_basis_daily.jsonl          44,916  STALE  2026-07-28
data/max_audit_directives_archive.json         5,320  LIVE   2026-07-31 07:31
... 12 more
```
`unlock_events.json` (5.0 MB — token unlock schedules, a live event-study axis) plus the
`kr_perasset_*` family (4.3 MB — the Korean per-asset premium panel) are **9.3 MB of research data
produced by session code that was never committed**. They survive only as citations in
`docs/research/deep_sweep/*.md`. That is a reproducibility failure of the first order: the data exists,
the code that made it does not, and nothing can regenerate or extend it. `8btc_era_thread_catalog.jsonl`
is L1.11a archaeology output (pre-ban CN ecosystem) in the same state.

`max_audit_directives_archive.json` is the sharpest: written **yesterday**, and
`grep -rn 'max_audit_directives_archive' . --exclude-dir=.git --exclude-dir=.venv` returns only a
`.gitignore` match. Something that no longer exists in the tree wrote it 17 hours ago.

Separately, ~8 stores are **write-only** (a live writer, zero readers): `oi_ls_live.jsonl` (383 K,
hourly), `hyperliquid_funding.parquet` (18,292 rows), `levered_lab_state.json` (186 K, rewritten
today), `conversion_queue.json`, `fred_macro_deep.json` (1.6 MB), `kaiko_vwm_reference_rate.jsonl`,
`idle_axis_screen.json`, `tail_funding_divergence.jsonl`. The desk has already diagnosed this class once
by name — `scripts/screen_collateral_allocation.py:7` says verbatim *"`data/defi_lending.jsonl` has been
collected DAILY and read by nothing"* — **that one instance was fixed and the pattern was not.**

---

### DI-25 [NEW, HIGH] — VENDOR CONCENTRATION: BINANCE IS 34% OF ALL URL REFERENCES AND TAKES OUT 18 OF 29 COLLECTORS. CROSS-VALIDATION IS AVAILABLE ON 0 OF 51 SOURCES.

```
$ grep -rhoP 'https?://[a-zA-Z0-9.-]+' scripts/ libs/ | sort | uniq -c | sort -rn | head
 31 https://api.binance.com      10 https://stats-data.hyperliquid.xyz
 24 https://fapi.binance.com     10 https://api.llama.fi
 12 https://ntfy.sh               9 https://api.hyperliquid.xyz
$ grep -rln "libs.data.crypto_source" scripts/ libs/ | wc -l
39
```
Binance = **62 of ~180 URL references (34%)** across four hostnames, and 39 files import the
Binance-only fetch layer — including `run_cashcarry_executor.py`, the live money path. If Binance bans
or dies, **18 of 29 collectors (62%) stop or degrade**: both Binance moat tapes, `oi_ls_live`,
`crypto_metrics`, `market_breadth`, `ingest_crypto*`, `dl_oi_ls_universe`, and — because Binance is the
USD leg — `kimchi_premium` and `tail_funding_divergence` become *undefined*, not merely stale. Bybit is
second (5.8 GB of moat), DefiLlama third (three feeds).

Redundancy is not thin, it is **absent**:
```
$ .venv/bin/python -c "...cross_validation_available TRUE count..."
cross_validation_available TRUE: 0 / 51
$ sed -n '186p' scripts/data_vitals.py
# DQS excludes cross_validation: it is a CONSTANT 0.5 (no source has a second feed)
```
`libs/data/multiexchange.py` (Binance+Bybit+OKX funding) exists and its only consumer is
`run_crossexchange_backtest.py` — a backtest, not a collector. `libs/data/onchain_flows.py:20` (4 public
ETH RPCs in order) is the **only genuine multi-source failover in the entire data layer**. Every other
`_FALLBACK` is a fallback *symbol list*, not a fallback *source*.

The cohort benchmark is unambiguous here: XTX's data-quality obsession and Wintermute's post-FTX venue
breadth both rest on multi-source cross-validation as the *default*, not the aspiration. This is the
`venue_breadth_counterparty: T4` row in the TIER1 register showing up as a data property.

---

### DI-26 [NEW, MEDIUM] — 11 OF 29 COLLECTORS HAVE NO SCHEDULER; 9 MORE EXIST ONLY INSIDE ONE DAILY SCRIPT. THREE HAVE NEVER PRODUCED AT ALL.

Unscheduled anywhere: `collect_hyperliquid_funding`, `collect_bitmex_funding`, `dl_metrics_history`,
`collect_deribit_surface` (DI-9), `collect_binance_metrics`, `collect_market_breadth`, `pull_cme`,
`ingest_crypto`, `ingest_crypto_enriched`, `ingest_etfs`, `ingest_multiasset`. Nine more run only inside
`daily_research_cycle.py` at 02:00 — one script failing takes out nine feeds simultaneously, which is a
correlated-failure mode nothing monitors.

Never produced: `collect_naver_krsearch.py` (`data/secrets/naver.json` absent — Korean search-interest
axis, an L1.11a non-English source, blocked on a missing credential file with no register row),
`pull_cme.py` (never run), `collect_free_signals.py` (orphan — its only caller `run_daily_research.py`
is not in cron; 63.5h stale).

Permanently degraded: `collect_announcements.py` is **DEGRADED on 40 of 40 runs**
(`data/announcement_collector.json`): `binance_announcements: "HTTP 400 -- CMS endpoint requires a
signed context"`, `bybit_announcements: "CloudFront blocks this egress country"`. Exchange
announcements are the input to the listing-event study (`libs/validation/event_study.py`,
`listing_events.py`) — the desk's named §42 event-shaped edge — and **both tier-1 venue feeds are
permanently dead** while the collector reports itself as running.

---

### DI-27 [NEW, MEDIUM] — THE SOURCE UNIVERSE MAP HAS 41 GRADED SOURCES AND EXACTLY ONE IS LIVE. THE LAST FREE DIG WAS 9 DAYS AGO.

```
$ .venv/bin/python -c "...status/grade histogram over data/data_universe_map.json..."
categories 64  total source entries 41
STATUS: queued 17 | confirmed 3 | (none) 3 | verified-mechanism 2 | lead-only 2 | leads-only 1 |
        LIVE 1 | verified-downloaded 1 | dead-link 1 | not-found 1 | catalogued 1 | (+8 one-off strings)
GRADE : needs-monitoring 19 | UNVERIFIED 5 | verified-clean 3 | (+13 one-off strings)
$ .venv/bin/python -c "...print(d['last_free_dig'])"
2026-07-22T23:21:50.541800+00:00     # 9.0 days ago
```
**17 of 41 sources (41%) are `queued`** — found, graded, and not ingested. One is `LIVE`. Ten of 64
declared categories hold any source at all; `options_vol` holds exactly one, `validation_ground_truth`
one, `universe` one. The status vocabulary itself has degraded into free text (18 distinct status
strings for 41 rows, several being whole sentences), so the map cannot be aggregated or gated on
without hand-parsing — which is why nothing gates on it.

This is the acquisition→ingestion conversion ratio stated in the desk's own artifact: **1 LIVE / 41
graded**. Under §33 every one of those queued rows owes a disposition. Under L1.28a the last free dig
being 9 days old, against a doctrine that calls the hunt never-ending (L1.35), is idle capacity with no
named binding constraint.

---

### DI-28 [NEW, CRITICAL — THE MOST CONSEQUENTIAL FINDING IN THIS SWEEP] — THE CRYPTO PANEL IS SELECTED ON *TODAY'S* LIQUIDITY AND THEN BACKFILLED SEVEN YEARS. EVERY CRYPTO BACKTEST THIS DESK HAS EVER RUN IS CONDITIONED ON THE SYMBOL STILL BEING LIQUID TODAY, AND HAS NEVER SEEN A TOKEN DIE.

```
$ sed -n '105,127p' libs/data/crypto_source.py
def list_perp_symbols() -> list[str]:
    """All actively-trading USDT-margined perpetuals (the free cross-sectional universe)."""
    return sorted(s["symbol"] for s in syms
        if s.get("contractType") == "PERPETUAL"
        and s.get("quoteAsset") == "USDT"
        and s.get("status") == "TRADING")          # <-- only CURRENTLY listed

def list_liquid_perps(*, top_n: int = 100) -> list[str]:
    """Top-N USDT perps by 24h quote volume -- the TRADEABLE universe (realistic-cost names)."""
    rows.sort(key=lambda x: x[1], reverse=True)
    return [s for s, _ in rows[:top_n]]            # <-- top-N by TODAY's volume
$ grep -n "list_liquid_perps" scripts/ingest_crypto_enriched.py
22:    ap.add_argument("--top", type=int, default=150)
30:    universe = list_liquid_perps(top_n=args.top)   # then backfills FULL history for that set
```

**Two compounding biases:**
1. `status == "TRADING"` — a delisted name can never enter the lake, at any point in history.
2. `top_n` by **current** 24h quote volume — the panel is selected on *future* liquidity relative to
   every historical bar, then backfilled to 2019.

**Verified directly against the lake:**
```
$ cd data/lake/bronze/crypto && for s in LUNAUSDT USTUSDT FTTUSDT SRMUSDT MATICUSDT FTMUSDT WAVESUSDT BTCUSDT ETHUSDT; do ...; done
LUNAUSDT     ABSENT      USTUSDT      ABSENT      FTTUSDT      ABSENT
SRMUSDT      ABSENT      MATICUSDT    ABSENT      FTMUSDT      ABSENT
WAVESUSDT    ABSENT      BTCUSDT      PRESENT     ETHUSDT      PRESENT
$ ls -d */ | wc -l
279
```
**LUNA, UST, FTT and SRM — the four largest go-to-zero events of the sample period — are all absent.**
So are MATIC, FTM and WAVES (renamed/delisted). A broader probe of 41 known-dead Binance USD-M perps
found 3 present, and those three are accidental fossils inside the frozen cohort, not deliberate
retention. There is **no delisting log, no `status` column, and no point-in-time universe file anywhere
in the repo**.

**What this invalidates:** every cross-sectional crypto study the desk runs off this lake — the carry
and basis work, the funding screens, `screen_*` cross-sectional ranks, the trend gauntlet, `build_labels`
— inherits an upward return bias of exactly the kind that killed the strategies in the desk's own
negative-exemplar list. The desk names Alameda/FTX as its control group; the data that would let it
study that collapse is excluded by construction. This is not a marginal statistical nit: survivorship
of this severity is the single most common way a backtest lies, and the desk's validation stack
(DSR, PBO, Holm, forward clocks) is entirely blind to it because it corrupts the *input panel*, not the
test.

The FX lake shows the correct behaviour and proves it is achievable here: `EURRUB` is retained, frozen
at 2022-02-28 — a genuine delisting preserved rather than deleted.

**Cheapest honest fix:** persist `exchangeInfo` daily (all statuses, not just TRADING) into a
point-in-time universe file, and stop filtering the historical panel on present-day status. The
exchangeInfo call is already made on every ingest run — the data is being fetched and thrown away.

---

### DI-29 [CARRIED, UNMOVED, NOW EXPLAINED] — 112 OF 279 CRYPTO SYMBOLS (40%) ARE FROZEN AT 2026-06-21, AND THE FROZEN SET IS *EXACTLY* THE NO-`basis` SCHEMA CLASS. ONLY 62/279 (22%) ARE FRESH.

Independently re-measured (my first attempt at this silently swallowed a `KeyError` on the wrong column
name and printed a vacuously-true result on an empty set — the exact defect class this report audits;
the corrected script asserts a non-empty denominator before reporting):
```
$ .venv/bin/python /tmp/di_verify.py
symbols scanned: 279 | errors: {}
frozen (last bar <= 2026-06-21): 112
no-basis schema class: 112
crosstab (is_frozen, has_basis): {(False, True): 167, (True, False): 112}
EXACT frozen-set == no-basis-set ? True
last-bar histogram (top 6): [('2026-06-21', 112), ('2026-08-01', 52), ('2026-07-30', 11),
                             ('2026-07-31', 10), ('2026-06-22', 8), ('2026-06-27', 6)]
fresh (last bar >= 2026-07-31): 62/279
```
The crosstab is perfectly diagonal — zero off-diagonal cells. **Frozen ⟺ missing `basis`/`taker_buy_frac`.**
Yesterday's DI-4 (132/278 frozen) has not moved; it is now explained: these symbols fell out of the
top-N liquidity window, the enricher stopped writing them, and the enrichment columns simply never
arrived. It is not a writer bug — **it is DI-28's universe rule printed into the data.**

Two silent consequences for every screen: any screen using `basis` or `taker_buy_frac` **silently drops
40% of the disk universe** (8 call sites defensively do `if "taker_buy_frac" in df.columns`, which
changes the panel size run-to-run without saying so); any screen not using them **mixes 6-week-stale
prices with live ones in the same cross-section**. And beyond the frozen cohort the "live" majority is
not live either: only 62/279 have a bar for 2026-07-31 or later.

Root cause of the throughput half:
```
$ crontab -l | grep -c ingest_crypto_enriched
0
```
The enricher is in **no crontab**; it is reachable only through `run_daily_research.py` **with
`--top 80`**, which overrides the script's own `default=150`. `ops/VPS_DEPLOY_PROMPT.md` warns to
"verify the scheduler isn't overriding `--top`". It is.

---

### DI-30 [NEW, CRITICAL] — ALL FIVE NON-CRYPTO ASSET CLASSES DIED ON THE SAME DAY, 43 DAYS AGO. NOTHING NOTICED.

```
$ .venv/bin/python /tmp/di_verify.py
fx       files=12069  global_max_ts=2026-06-19
equity   files=1693   global_max_ts=2026-06-18
index    files=668    global_max_ts=2026-06-19
metal    files=708    global_max_ts=2026-06-19
energy   files=531    global_max_ts=2026-06-19
```
(crypto H8 likewise ends 2026-06-20.) **Five asset classes, one death date, 43 days of silence.** One
shared bridge died and no monitor covers any of them — they are absent from `web/health.json`'s
5 datasets (DI-19), absent from `collector_health.json`'s 4 clocks (DI-4), and present in
`data_assets.json` only as `last_validated: 2026-06-20/21` (DI-12), which is the same fact recorded
without an alarm attached.

This is the desk's entire cross-asset dimension: 26 years of FX (57 pairs), 18 of metals, 16 of energy,
13 of index, 8 of equity ETFs. L1.11 calls for fusion of 3+ orthogonal sources; the orthogonal sources
have been dark for six weeks. The doctrine's own framing applies exactly — an unmeasured ceiling counts
as zero utilisation, and here the *measurement existed* (`last_validated`) with **no fence reading it**.

---

### DI-31 [NEW, CRITICAL] — THE 7.2 GB MOAT HAS NEVER BEEN BACKED UP. `backups/moat/` IS AN EMPTY DIRECTORY CREATED BY THE BACKUP SCRIPT'S OWN `mkdir`.

```
$ ls -la backups/moat && du -sh backups
total 52
drwxrwxr-x 2 quant quant 4096 Jul 31 13:51 .
drwxrwxr-x 3 quant quant 4096 Jul 31 13:51 ..
52K     backups
$ ls -la data/backup_status.json
ls: cannot access 'data/backup_status.json': No such file or directory
$ git log --oneline --diff-filter=A -- scripts/run_moat_backup.py
12cea2a Moat backup wired (T4 defect closed) + TIER1 benchmark register...
$ sed -n '139,141p' scripts/run_moat_backup.py
    dest = dest or root / "backups/moat"
    dest.mkdir(parents=True, exist_ok=True)
```
The directory exists and is **empty** — no shards, no `manifest.json`, no restore-drill record. The
`mkdir` ran; nothing else did. The TIER1 register's `data_moat` row states its closer as *"backups/moat
replicas live (run_moat_backup)"* and the commit message declares *"T4 defect closed"*.

**The single irreplaceable asset on this desk — 7.2 GB of self-recorded order-book and trade tape that
no vendor sells and no re-download can reconstruct — has zero replicas.** A disk failure erases it
permanently. Note the directory's existence would satisfy any `.exists()` check (cf. DI-22), which is
precisely how this stays invisible.

*Honest caveat, stated because the distinction matters:* `run_moat_backup.py` is scheduled at `55 3`
daily and `check_fence_yield.py` at `25 7`; the managed cron block was reinstalled at 2026-07-31T21:30Z,
so **neither window has come round since reinstall**. The `mkdir`-only state dates from 13:51 on 07-31,
before that. So this is not yet proof the cron line is broken — it *is* proof that as of now, 2026-08-01
00:20Z, no backup of the moat exists on disk, and that a T4-defect-closed claim was recorded against an
empty directory.

---

### DI-32 [NEW, HIGH] — 80% OF THE MOAT HAS ZERO READERS. NO SCREEN AND NO BACKTEST READS ANY OF IT.

```
$ grep -ln "data/moat" scripts/screen_*.py | wc -l          → 0
$ grep -ln "data/moat" scripts/*backtest*.py | wc -l         → 0
$ grep -rn "moat.*bybit\|bybit.*moat" scripts/ libs/ --include=*.py | grep -v run_recorder_bybit
(no output)
```
**Zero of 15 screens. Zero backtests.** `data/moat/bybit` — 6.1 GB, 80.4% of the moat and ~70% of all
desk data — has no reader but its own writer. The 22 files that do reference `data/moat` are entirely
QA, cost and governance instrumentation (`moat_audit`, `run_cost_model`, `data_vitals`, `max_audit`,
`check_gate0_ready`, `run_moat_backup`, `dependency_graph`...), and even those sample thinly:
`moat_audit.py` reads 6 files/symbol (≈1.8% of 20,207 shards) and `micro_factory.py` covers 5 of 30
symbols × 60 files (≈1.5%).

And the one organ that extracts *features* from the tape is stale:
```
$ crontab -l | grep micro_factory
30 5 * * * ... flock -n data/.cron_micro_factory.lock .venv/bin/python scripts/micro_factory.py ...
$ ls -la data/micro_features.json
-rw-rw-r-- 1 quant quant 1785 Jul 27 18:21 data/micro_features.json
```
A **daily** job whose output is **4.9 days old** — four consecutive missed windows, independent of any
log-file question. Its single downstream reader (`research_exchange.py`) pastes it into a text brief.

Reconciling with L1.28a: the moat is the desk's only genuine moat, it is being written at ~600 MB/day,
and its measured research utilisation is **~0**. The 07-31 blind-rediscovery note already recorded
"data/moat 7.1GB = 82% of desk data, zero screens"; **one day later it is 7.2 GB and still zero.**

---

### DI-33 [NEW, MEDIUM] — CRON→OUTPUT ATTRIBUTION IS DESTROYED BY A KEEP-30 LOG ROTATION ACROSS 100 DECLARED LOG DESTINATIONS.

```
$ crontab -l | grep -oP '(?<=>> )\S+\.log' | sort -u | wc -l      → ~100 distinct log destinations
$ ... | while read l; do [ -f "$l" ] || echo MISSING $l; done | wc -l   → 62 missing
$ grep -rn "cro_ai_logs" ops/run_cro_ai.sh | grep rm
99:ls -1t data/cro_ai_logs/*.log | tail -n +31 | xargs -r rm -f
```
**The rotation keeps the 30 most-recently-modified logs across the whole directory and deletes the
rest.** With ~100 declared destinations and several jobs writing every 3–15 minutes, a *daily* job's log
is mathematically guaranteed to be deleted before anyone reads it. That is why 62 logs are missing, and
it is why I could not use log existence as evidence of execution anywhere in this report — every
liveness claim here had to be reconstructed from output artifacts instead.

This is an observability defect with a direct research cost: when a collector silently drops data
(DI-14) the log is the only forensic trail, and the trail is deleted on a rolling ~hours horizon.
Per-job log files with per-job retention (or size-capped rotation per file) costs nothing and restores
the attribution.

---

### DI-34 [NEW, MEDIUM] — TIMESTAMP CONVENTIONS SPLIT CLEANLY IN TWO, AND ONE HALF IS NAIVE AND FORMAT-INCONSISTENT.

All parquet in the lake is `timestamp[ns, tz=UTC]` — consistent across every dataset, zero duplicate
timestamps anywhere in 279 crypto symbols, zero within-symbol schema drift. That half is genuinely good
and is recorded as a strength (S3).

The non-parquet half is not: `cme/*.csv`, `crossasset/*.csv`, `fed/*.csv`, `mining/*.csv`,
`oi_ls_daily/*.jsonl`, `futclose_daily/*.jsonl`, `wikipedia/*.json` carry **naive date strings in at
least three mutually incompatible formats** (`01/02/1990`, `2021-10-01`, `2018031500`). Any join across
the two families is a silent tz/parse hazard, and the SCREEN-ON-DISCOVERY duty makes unstated timestamp
alignment a *voiding* condition for a screen — the desk cannot currently state alignment for half its
lake. Worse, `data/lake/bronze/mining/*.csv` have **no header row**, so the first data row is consumed
as column names (`cols=['2009-01-03 00:00:00','1.0']`): one observation is silently lost and every
column is mislabelled.

Related storage/consistency defects in the same tier: `etf_flows` is **8 raw unparsed HTML files** with
no extraction step; `fed/` and `etf_flows/` store dated **full snapshots rather than deltas** (eight
near-identical 1.146 MB `nyfed_rrp_*.json` copies differing by ~150 bytes — unbounded growth for ~1 KB/day
of information); `futclose_daily` stops 2026-06-30 while its sibling `oi_ls_daily` (same 139-symbol
universe) runs to 2026-07-29, a 29-day divergence between two datasets that should move together; and
`binance_metrics/SOLUSDT` holds 223 days ending 2023-08-11 against 1,306 for BTC/ETH.

---

### DI-35 [NEW, MEDIUM] — THE QUOTA TRIPWIRE HAS BEEN LATCHED SHUT FOR NINE DAYS AND ITS CRON LOG IS ZERO BYTES.

```
$ cat data/quota_watch.json
{"baseline": "2026-07-22", "verdict_sent": true}
$ grep -n "verdict_sent" scripts/quota_verdict.py
23,59:  if st.get("verdict_sent"): return
$ ls -la data/cro_ai_logs/quota_verdict_cron.log
-rw-rw-r-- 1 quant quant 0 Jul 31 21:00 data/cro_ai_logs/quota_verdict_cron.log
```
Scheduled `0 */3 * * *` — eight runs a day since 2026-07-22 — and every one returns on line 1. Nine
days of a no-op tripwire, with a zero-byte log as the only trace. Included here because LLM quota is the
binding constraint on the acquisition tier (the digging/mining organs that turn discovered sources into
ingested ones), so a dead quota watch is a data-acquisition blind spot, not just an ops one.
