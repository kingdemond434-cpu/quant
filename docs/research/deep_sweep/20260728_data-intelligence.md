# WEEKLY DEEP COLD AUDIT — DATA-INTELLIGENCE — 2026-07-28

Auditor: cold-sweep data-intelligence seat (read-only). Doctrine: v2 core + exhaustion mandate.
Scope: datasets (quality/coverage/latency/history/cost), collection architecture, redundancy,
vendor concentration, survivorship, timestamp consistency, entity resolution, schema evolution,
repair automation, backfill, metadata, versioning, lineage, reproducibility, derived datasets,
alt-language sources, archives.

STATUS: COMPLETE. Every claim below carries its proving command; commands were run 2026-07-28
~20:00–20:30 UTC from /home/quant/quant-platform.

## SCORES

- current_capability_pct: **62** — collection breadth, survivorship discipline, and screen-on-discovery
  are genuinely strong; durability (zero backup, no disk monitor), monitor correctness (live false-DEAD),
  options depth (6 scalars/day), and source-queue drain lag far behind.
- practical_ceiling_estimate: **90** (under the free-data-only, single-box constraint)
- ceiling_gap: **28 points**
- opportunity_cost_1y: **UNBOUNDED LEFT TAIL + material research drag.** One disk event before a backup
  exists destroys the desk's only `regenerable: false` asset (the moat) — the entire point-in-time
  advantage, unrecoverable at any price. Separately: ~350 option-surface-days/yr permanently destroyed
  (F4), whole hypothesis families delayed months behind queued-but-verified sources (F6), and a
  false-DEAD DQS organ quietly inflating conversion costs (F2).
- confidence: **0.8** on findings (all command-cited), **0.6** on the ranking.
- unknown_unknown_score: **0.35** — three overlapping monitors with three scopes leave gaps between
  them; the lake's parquet stores sit outside DQS scoring entirely.
- info_gain_if_investigated: highest for the binance.vision bookDepth/premiumIndexKlines probe (T4)
  and the bybit moat-weight anomaly (ignorance ledger).
- expected_alpha_contribution: moderate direct (options-surface family, queued source families),
  **high indirect** (deeper book history → cost-model calibration → sizing quality; the cost model is
  currently producing physically impossible flat curves — see data_sanity crossref).
- expected_compounding_contribution: **HIGH** — opportunities #1, #2, #8 are compounding multipliers
  (they raise the value of every future dataset).
- CEILING EXPANSION: the 90% ceiling is defined by POLICY (free-only, single box), not physics. Its own
  lifting conditions already exist in the registry: the evidence-gated paid exception ("tardis one-off
  pull … when real capital justifies", `data_registry.json`) and object storage at pennies/GB/mo for
  moat redundancy. Neither survival rail nor proven-edge law binds here; the ceiling moves the day the
  desk decides durability is worth ~$1–2/mo.

---

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**S1. Free-first is real at the artifact level, not just posture.** `ls -la data/paid/` → only
`README.md` (433 bytes). Registry policy pins tiering and the 90%-free-reconstructable rule;
universe map header: "~$1.5k paid basket replaced at $0 + cents of S3 egress."
`python3 -c "json.load(open('data/data_registry.json'))"` → 20 sources, all live ones Tier 1–2.

**S2. Survivorship discipline is pinned in code, not prose.** `sed -n 1,50p scripts/dl_oi_ls_universe.py`:
universe enumerated from the archive's own S3 listing (906 symbol dirs INCLUDING delisted), field
mapping pinned against the forward collector (contracts vs USD; global LS vs top-trader), tranche-1
cohort = metrics by 2022-07-01. `ls data/lake/bronze/oi_ls_daily | wc -l` → 139 symbols; cron log
tail → "130/139 symbols complete … DONE: 139 symbols".

**S3. Screen-on-discovery is mechanically implemented for the whole lake.** `ls reports/axis_screens/`
→ 15 family artifacts (binance_metrics, cme, crossasset, energy, equity, etf_flows, fed, futclose_daily,
fx, index, metal, mining, oi_ls_daily, wikipedia) **plus `_raw_trials.json`** (trial ledger — forking-paths
control). Each artifact DECLARES alignment (mining: "blockchain.com daily points stamped 00:00 UTC";
wikipedia: Wikimedia stamp note) and carries honest negatives: `tail data/stage_a_verdicts.jsonl` →
SCREEN-NULL (onchain tx_count, ic −0.0085), UNDERPOWERED (venue_divergence abs_diff, 5 < 60 days).
The gate discriminates — verdicts vary (WEAK/NULL/UNDERPOWERED), it is not a 0%/100% constant.

**S4. Price/derivatives history is deep, hive-partitioned, and includes a regulated-venue axis.**
`ls data/lake/bronze/crypto | wc -l` → 274 symbols; `ls data/lake/bronze/crypto/BTCUSDT/D1/` →
`year=2019 … year=2026/month=…`. `ls data/lake/bronze/cme/` → BTC+ETH FUT definition/ohlcv-1d (2018→
2026-07-20)/ohlcv-1h (2021→)/statistics, 1.1G total, already converted (`reports/axis_screens/cme.json`,
`data/cme_basis_screen.json`, `data/cfe_regulated_basis_screen.json` all exist).

**S5. The moat records real L2, and its continuity since start is measured-good.** `zcat` of newest
bybit/BTCUSDT hour → depth snapshot + diff stream with update-ids @1s, trades @5s (recorder.log:
"20 symbols | depth@1.0s trades@5.0s"). Gap enumeration over `moat/fut/BTCUSDT` filenames →
first 2026-07-17 23:00, last 2026-07-28 20:00, 257 files, **one 5h gap (07-21 02:00→08:00), 98.1%**;
spot+bybit continuous 180/180 hours since 07-21 09:00.

**S6. Monitoring exists on three axes and has caught real failures.** `collector_health.json` KILLed
cny_premium on "FLATLINE p2p_cny=6.74 x5" (detection with teeth); `data_vitals.py` encodes three
past false-verdict lessons in comments (new-file grace, too-small-reported, constant-cross-val
excluded); `stat web/health.json` → written 2026-07-28 20:25 (watchdog line 215 runs data_health
every 3-min tick). `data_sanity_report.json` → 37 findings (17 CRITICAL) proving the impossibility
scanner actually fires.

**S7. Conversion pressure is mechanized, not aspirational.** `scripts/conversion_engine.py` builds the
queue from unread fields + uncrossed pairs + unmodelled entities (`data/conversion_queue.json`, n=214)
and **injects the top-40 into the research CIO schedule** ("THE PART THAT MAKES IT UTILISATION RATHER
THAN A LIST"). `data/idle_axis_screen.json` (updated today) screens idle axes against the
data-utilization defect from max_audit.

**S8. Alt-language and archival digging is live and converting.** `data/8btc_era_thread_catalog.jsonl`
→ 713 threads (today); `data/cny_otc_premium_history.jsonl` → 591 rows reconstructed via CDX replay
(OP-031); `data/kr_perasset_premium_history.jsonl` → 3,008 rows; wikipedia pageviews screened in
5 languages (`data/batch_altdata_screen.json`: wiki_btc_{en,ja,ko,ru,zh}, decontam_passed=true).

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

- **Why bybit moat is 8× heavier than binance fut** (4.1G/7.4d ≈ 550MB/day vs fut 707M/11d ≈ 64MB/day
  for similar symbol counts). Uncompacted dupes? Deeper levels? Unaudited. High info-gain probe.
- **Whether `bookDepth` / `premiumIndexKlines` exist on data.binance.vision for our window** — if
  bookDepth does, it partially revises the desk's "pre-recorder L2 destroyed at source" residual-gap
  claim (snapshots, not tick diffs, so the claim stays technically true — but cost-model calibration
  doesn't need tick diffs). Needs one external S3 listing probe (T4).
- **CNY flatline root cause**: OKX P2P median genuinely pinned at 6.74 five polls running, or the
  collector caching/erroring to a constant? Indistinguishable from current logs (raw top-10 quote
  arrays are not persisted per poll). T6 resolves it.
- **Whether the vitals false-DEAD suppressed real work**: conversion_engine provably inflates cost
  (+0.5) for sources not vitals-"OK" (`sed -n 43,60p scripts/conversion_engine.py` — `live = "OK" in
  action`); coinmetrics fields carry that penalty today. Second-order effects (failover pages,
  measurement_gate verdicts) untraced.
- **collector_attempts.jsonl**: 0 bytes with mtime 07-27 14:04 — never-ran vs truncated: undetermined.
- **Whether lake ingest verifies gaps** (ingest_crypto internals unaudited this sweep).
- **Whether venue_divergence conclusions change with US venues** (Coinbase/Kraken books absent from
  the moat and the poll set).

---

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

**#1 — MOAT SURVIVAL PACKAGE (durability): backup + disk monitor + retention policy. [COMPOUNDING]**
- Evidence: `df -h /home/quant/quant-platform` → **38G disk, 25G free**. Moat 5.1G growing ~0.6–0.7G/day
  (bybit 4.1G in 7.4 days) → **~5 weeks to disk-full**, which kills the recorder, heartbeats, executor
  and every collector at once. `grep -rn "statvfs|disk_usage|df -h" scripts/watchdog.py
  scripts/run_alerts.py scripts/data_health.py` → **zero disk monitoring anywhere**.
  `git check-ignore -v data/moat` → gitignored; `grep -rln "rsync|rclone|backup" ops/ scripts/` →
  only memory docs + git_snapshot (git-only). The desk's own vitals mark the moat and
  venue_divergence "regenerable: false" — **the only irreplaceable assets exist in exactly one copy
  on a disk with a ~5-week fuse and no gauge.**
- Exactly-what: (a) watchdog disk check paging at 80/90%; (b) hourly `rclone` of data/moat + the
  regenerable:false jsonls to any object store (Cloudflare R2 free tier 10GB / B2 ~$0.006/GB ≈
  $0.5–2/mo at current rates — within free-first spirit; a second VPS also qualifies); (c) age-based
  gz compaction/offload so the local window stays bounded.
- Complexity: hours. Dependencies: none. Validation: kill-test restore of one hour-file; pager drill
  at threshold. Failure modes: credentials on box (scope token to write-only bucket); silent rclone
  breakage (monitor the backup's own age — outcome, not config). Maintenance: near-zero.
  ROI: protects every other line in this report. Retirement: never (constitutional-class durability).
  Horizons: 1w = fuse defused; 1y = moat compounding uninterrupted; 3y = multi-year proprietary book
  history no vendor sells.

**#2 — FIX THE FALSE-DEAD DQS (monitor correctness). [COMPOUNDING]**
- Evidence: `grep -n MAX_ROWS scripts/data_vitals.py` → `MAX_ROWS = 3000`, `_rows()` reads the FIRST
  3000 lines. `head -1 data/coinmetrics_flows.jsonl` → btc **2010-07-18**; `tail -1` → eth
  **2026-07-27** (fresh, 9,870 rows, asset-partitioned btc-block-then-eth-block). Head sample ends
  ~2018 → `age_s=246,712,882` (7.8 years) → latency 0, completeness 0, **"DEAD -- FAILOVER" on a
  healthy collector** (`data/data_vitals.json`). The file's own comments memorialize three prior
  false-verdict classes; this is the fourth, live. Consumers that inherit the error:
  daily_research_cycle, measurement_gate, conversion_engine (cost +0.5 for non-"OK" sources).
- Exactly-what: score on head+tail sample (or streaming max-ts full pass — 9.8k rows is nothing);
  compute cadence per monotonic run or per entity-group; add a regression fixture: a fresh-mtime,
  stale-head, sorted-by-entity file must score OK, and a genuinely stale-tail file must still DIE.
- Complexity: <1 day. ROI: restores trust in the ONLY DQS organ; un-poisons conversion costs.
  Failure mode: tail-only scoring hides a dead entity inside a multi-entity file — group-aware max
  handles it. Monitoring: vitals disagreement vs data_health freshness = page.

**#3 — STOP DESTROYING THE OPTION SURFACE (data destruction, irreversible daily).**
- Evidence: `libs/data/deribit.py:vol_surface` fetches the ENTIRE option book
  (`get_book_summary_by_currency`) then reduces to `{atm_iv, skew, term, spot}`;
  `data/deribit_surface.parquet` → **70 rows × 6 cols for 32 days** (2.2 rows/day, one snapshot/day).
  The desk's own universe map lists per-strike IV history as unpurchasable-residual; its own collector
  docstring says "Per-strike IV has NO free history, so we snapshot … and build our OWN history" —
  and then keeps 6 numbers of the ~hundreds-of-instruments book it already paid the network cost for.
- Exactly-what: persist the full per-instrument rows (exp, strike, type, iv, spot, ts) to a
  hive-partitioned parquet next to the summary; raise cadence to hourly (still trivial: ~24 calls/day).
  ~30 LOC. Storage: KB/day gz. Every day of delay is permanently destroyed smile/wing/term dynamics —
  the input to RR/fly/VRP families the summary cannot reconstruct.
- Validation: 3-day diff — summary recomputed from full rows must equal the archived summary (T3).

**#4 — SCHEDULE OR FORMALLY RETIRE collector_author (dead-on-arrival organ).**
- Evidence: built 07-27 as "closes the desk's real conversion bottleneck … end-to-end, **daily**"
  (`sed -n 1,30p scripts/collector_author.py`); `grep -rn collector_author ops/*.sh
  scripts/daily_research_cycle.py scripts/organ_catchup.py` + crontab → **no scheduler anywhere**;
  no log in data/cro_ai_logs; its ledger `data/collector_attempts.jsonl` = **0 bytes**. Config
  without outcome — the exact organ-death mode (watchdog 11.5-day lesson) recurring.
- Also carries disclosed residual risk (executes LLM-written code on the key-holding host behind a
  static scan + subprocess). Decision needed either way under §41: schedule it (with its safety
  posture reviewed) or ledger a reasoned rejection. Silence is the one illegal state.

**#5 — DRAIN THE QUEUED-FOREVER SOURCE FAMILIES (catalogue-vs-ingest leak at the SOURCE level).**
- Evidence: universe map per-family statuses → cex_trades_ohlcv **4/6 queued** (incl
  data.binance.vision, literally annotated "source of truth, to launch"), cex_l2_depth 4/5 queued,
  oi_funding_liquidations 2/2, options_vol 1/1, validation_ground_truth 1/1 queued; OKX portal
  **verified-clean this month, unbuilt**; `last_free_dig` 2026-07-22. The desk's oldest leak
  (catalog ≫ ingested) re-forming one level up from axes.
- Exactly-what, EV-ordered: (a) binance.vision trades/aggTrades/premiumIndexKlines pull for the
  moat symbols (premiumIndexKlines = 1m premium index → years of funding-basis microstructure at $0);
  (b) OKX portal collector (already verified-clean; tick trades since 2021-09, L2 since 2023-03,
  funding since 2022-03 — a second-venue deep history that also de-concentrates Binance vendor risk);
  (c) bybit public dumps. Each lands as bronze + mandatory Stage-A screen per SCREEN-ON-DISCOVERY.
- Note the vendor-concentration angle: nearly all derivatives history currently keys off one vendor's
  archive goodwill (Binance). OKX portal is the cheap hedge.

**#6 — ETF-FLOWS BACKFILL: the screen is starving next to a full pantry.**
- Evidence: `reports/axis_screens/etf_flows.json` → `n_days: 15, n_required: 51, range 2026-07-06 →
  2026-07-24` (UNDERPOWERED); farside publishes the full daily table back to 2024-01 (same page the
  collector already parses — `data/lake/bronze/etf_flows/farside_btc_20260728.html` is on disk).
  Parsing the archive rows instead of waiting converts a 36-day wait into an afternoon.

**#7 — REPAIR LOOP FOR KILLED CLOCKS (detection exists, repair doesn't).**
- Evidence: cny_premium KILLed (flatline ×5) in `data/collector_health.json`; `grep cny
  data/blind_spot_ledger.jsonl` → nothing filed; no failover construction configured; the CDX-replay
  OTC route with 591 days of history sits on disk unattached. Kill-and-sit is half a repair loop.
- Exactly-what: on KILL, auto-file a recommendations row (§41) + attempt the registered alternate
  construction (here: OTC-index route) in shadow; persist raw quote arrays per poll so flatline root
  cause is diagnosable (T6).

**#8 — ONE DATASET CATALOG DRIVING ALL MONITORS (greenfield seed). [COMPOUNDING]**
- Evidence of fragmentation: collector_health = 4 clocks (`sed -n 33,36p scripts/collector_monitor.py`);
  data_vitals = 38 data/*.jsonl entries + hand-list (parquet stores absent: `grep -n "deribit|parquet"
  scripts/data_vitals.py` → no hits); data_health = freshness only; plus data_registry.json (20
  sources, drifted — says binance_vision "used_by unused" while `grep -rln binance.vision scripts/`
  → dl_metrics_history.py, dl_oi_ls_universe.py, ingest_axes.py…) and data_universe_map.json (~40
  entries) overlapping without reconciliation. Five places, no single truth; every new dataset must
  be hand-added to up to 3 monitor configs, and misses are silent.
- Exactly-what: one `data_catalog.json` row per dataset {path, owner_collector, cadence, monitor
  policy, screen artifact, conversion status, regenerable, backup policy}; generate vitals/health/
  collector_monitor scopes FROM it; auto-derive `used_by` via grep at write time. This is the
  metadata multiplier the doctrine flags — it raises the value of every future dataset.

**#9 — futclose daily-zip top-up.** Evidence: `pull_klines` uses monthly zips only
(`grep -n klines scripts/dl_oi_ls_universe.py` → `monthly/klines/...`); `tail -1
data/lake/bronze/futclose_daily/BTCUSDT.jsonl` → 2026-06-30 — a rolling ≤31-day hole the same
archive's daily zips close for pennies of egress.

**#10 — Registry hygiene + zombie ledger.** cot_zcache.parquet stale 37d (2000→2026-06-21; consumer
run_mt5_portfolio.py unscheduled), fx/equity/energy/metal/index bronze frozen 2026-06-20/21 (mtimes),
`grep -rn schema_version libs/ scripts/` → **no schema versioning anywhere**. Mark the MT5-era
families TERMINAL-with-reason per §36 (or re-own them), and stamp bronze writers with a schema hash
so upstream drift (e.g., farside HTML) fails loudly instead of silently.

---

## 4. WHAT WE TEST NEXT (experiments, success criteria, retirement conditions)

- **T1 (vitals fix regression):** synthetic fixtures — (a) fresh-mtime entity-partitioned file with
  ancient head, (b) genuinely stale-tail file, (c) 5-row new file. Success: (a) OK, (b) DEAD,
  (c) NEW. Then live: coinmetrics DQS ≥0.9 same day. Retire when fixtures run in CI.
- **T2 (durability drill):** after #1 lands — restore one random moat hour-file from backup, byte-diff
  vs original; pager fires in a disk-threshold simulation. Success: restore identical + page <5 min.
  Repeat monthly (outcome-not-config: monitor the BACKUP'S age, not the cron line).
- **T3 (surface archiver):** run summary-vs-full-chain in parallel 3 days; recomputed summary from
  full rows == archived summary; gz ≤50KB/day. Success → cut over, keep both.
- **T4 (bookDepth/premiumIndexKlines probe):** S3-list `data/futures/um/daily/bookDepth/BTCUSDT/` and
  `premiumIndexKlines`. If present: register in universe map with availability window + EV-score
  backfill vs cost-model need (data_sanity's 17 flat-slippage CRITICALs are the demand signal).
  If absent: log the failed search as the graded residual gap the FREE-FRONTIER axiom requires.
- **T5 (etf backfill):** parse farside archive → n_days ≥51 → rerun screen; success = verdict leaves
  UNDERPOWERED (either direction; a NULL is a legitimate paid-for answer 36 days early).
- **T6 (cny root cause):** persist raw top-10 quote arrays per poll for 3 days. Identical arrays
  poll-over-poll = collector bug; varying arrays with constant median = genuine pin → keep KILL,
  switch weight to the OTC-index construction.
- **T7 (bybit weight anomaly):** decompress one bybit vs one binance hour, count msgs/levels; success
  = explained ratio + (if dupes) dedup saving ~½ of moat growth, directly extending the disk fuse.

---

## PERSPECTIVE COVERAGE LEDGER

- **INTERNAL** (measured, not configured): F#1 disk/backup void, #2 false-DEAD, #7 kill-without-repair
  — plus measured strengths S5 (98.1% fut continuity), S6 (monitors that fire), S3 (screens with
  honest negatives). Verdict: collection is healthy; the meta-layer around it has the defects.
- **EXTERNAL** (how a world-class desk would differ): no irreplaceable data on one spindle (#1);
  full-chain option archives as a matter of course (#3); one catalog driving monitors (#8); a second
  independent venue archive to break single-vendor history concentration (#5b).
- **FUTURE** (2–3y redesign): the desk already BUILT its future organ — LLM-authored collectors with
  static-scan + sandbox + Stage-A autoscreen (collector_author). It is one crontab line from
  existing (#4). Catalog-driven auto-generated collectors (#8 + #4 composed) IS the 2-3y design,
  available now.
- **CONTRARIAN** (core assumption tested): "more sources = more alpha" is now the WRONG binding
  constraint. Evidence: moat is 11 days old; Stage-B needs forward windows; cost model starves on
  book depth (17 CRITICAL flat-slippage findings in data_sanity_report.json); meanwhile the source
  catalog outruns ingestion 4-queued-to-1-built in the biggest family. The binding constraint is
  DEPTH×TIME×DURABILITY of what already records — which is why #1 outranks every new source.
  Second contrarian probe: the 90%-free-reconstructable rule survives evidence (kimchi came free;
  ~$1.5k/mo replaced at $0) — keep, with the registry's own paid-exception clause as documented.
- **GREENFIELD**: rebuilt today it would be: one catalog, bronze-only writers with schema hashes,
  monitors generated from the catalog, every dataset born with {screen artifact, conversion row,
  backup policy}. Current estate approximates this in 5 drifting places (#8 evidence). Historical
  baggage: 232-file data/ dir mixing state/feeds/logs/screens; MT5-era zombie families (#10);
  two overlapping source catalogs. Replaceability of everything except the moat: high (bronze is
  re-pullable); the moat is the ONLY thing a rebuild cannot recreate — which is again #1.
- **FRONTIER** (recently-possible, unexploited): binance.vision endpoints beyond metrics/1d-klines
  (bookDepth, premiumIndexKlines, aggTrades — T4 probe); OKX official historical portal (verified
  clean IN the desk's own map this month, unbuilt); farside's full archive (T5); the desk's own
  CDX-replay operator OP-031 (proven on CNY-OTC, 591 rows) generalizes to any capped JSON API —
  a reusable frontier technique already in-house.

## NEGATIVE-SPACE SWEEP (verified absences)

1. **No disk-space monitor** (grep across watchdog/run_alerts/data_health: zero hits) — with a
   measured ~5-week fuse.
2. **No backup of any data artifact** (data/* gitignored; no rsync/rclone/offsite anywhere in ops/
   or scripts/) — including `regenerable: false` assets.
3. **No schema versioning/manifests/checksums** (`grep -rn schema_version` → none).
4. **No cross-source alignment verifier**: vitals' temporal_alignment is within-file only; cross-source
   joins rely on per-screen declared alignment (good practice, S3) with no mechanical re-verification
   on live clocks.
5. **No US-venue books in the moat** (Binance+Bybit only; Coinbase appears solely as a killed premium
   axis, 1 row).
6. **Options = Deribit summary only**: no full chain (F#3), no second options venue, no intraday.
7. **collector_attempts ledger empty** — the organ meant to industrialize collector-writing has never
   logged an attempt (#4).
8. **Funding-settlement timing microdata** (exact per-venue funding timestamps/settlement windows)
   not archived anywhere I could find — relevant to the carry family the desk actively trades;
   checked data/ listings and lake families. (Seam checked; nothing found = gap named.)

## CROSS-SUBSYSTEM HANDOFFS

- The 17 CRITICAL flat-slippage cost-model findings (`data/data_sanity_report.json`) belong to
  execution, but their FIX is data: book-depth history (T4/T7, moat retention #1).
- conversion_engine cost inflation from vitals false-DEAD (#2) touches research prioritization.

## §33/§35 NOTE

Recommendations #1–#10 and probes T1–T7 above are this report's carded output; per §41 they require
ledger rows (scripts/recommendations.py) at next live cycle — this audit ran READ-ONLY and did not
write ledgers. Highest-tier defect-closers: #1 (durability) and #2 (monitor correctness).
