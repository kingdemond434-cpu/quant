# WEEKLY DEEP COLD AUDIT — DATA-INTELLIGENCE — 2026-07-31

STATUS: COMPLETE — 16 findings (DI-1..DI-16) + 8 ignorance-ledger rows + 10 ranked opportunities + 7 tests,
all command-cited; six perspectives covered; battery 10/10 run; ledger commands queued for the synthesis seat.

Auditor: cold-audit seat (data-intelligence), doctrine v2. Read-only sweep; only this report is written.
Scope: every dataset — quality/coverage/latency/history/cost — and collection architecture, redundancy,
vendor concentration, survivorship, timestamp consistency, entity resolution, schema evolution, repair
automation, backfill, metadata, versioning, lineage, reproducibility. Plus derived/synthetic datasets,
weak labels, cross-source enrichment, alt-language sources, gov publications, archives.

## HEADLINE — the five things that matter today

1. **The DR fix installed a second scheduler beside the first last night. Three collectors are measured at
   exactly 2× write rate since 23:00Z; the ingest_axes variants collide at 06:40Z TODAY with different args
   and non-excluding locks; the recorder respawn race is armed against the moat.** Fix before 06:40Z. → DI-1
2. **The LLM acquisition tier is funding-dead across BOTH providers, day 9** — Claude organs (no API-key
   fallback file) + kimi hunter (OpenRouter 402 with 59% of its monthly envelope unspent). Acquisition
   capacity 0; frontier/multilingual digging not running at all. → DI-2, DI-9
3. **Binance is 418-banning the desk's IP inside the daily cycle**, killing forward-evidence clocks
   (shadow_8h, axis_shadows) and the NAV truth chain intermittently — and DI-1 just doubled the poll rate
   feeding the ban. → DI-10
4. **Nobody owns crypto bronze freshness**: July partitions arrive as a 1–7 symbol/day consumer side-effect
   plus one unattributed 54-symbol rescue at 00:13Z today; 132 active symbols frozen since 2026-06-21. → DI-7
5. **The silent-anomaly class is fenceless**: rows/hour doubled on three feeds and NOTHING noticed — no
   write-rate fence exists on any collector output. The same blindness would hide a silent halving. → DI-13

## SCORES

| metric | value |
|---|---|
| current_capability_pct | **36%** (34% yesterday: +BTC/ETH revival, +options sprout, +stablecoin/liquidation axes verified alive; −scheduler duplication regression, −tier still dead) |
| practical_ceiling_estimate | **85%** (unchanged; majority of gap is wiring/funding/ownership, not new engineering) |
| ceiling_gap | **49 pts** |
| opportunity_cost_1y | **VERY HIGH** — dominated by the dead acquisition tier (discovery rate ≈0 from digs) + ban-risk on the single venue serving ~everything (F18) |
| confidence | **HIGH** on findings (all command-cited), **MEDIUM** on rankings |
| unknown_unknown_score | **7/10** — today proved an entire invisible failure class (write-rate anomalies); assume more classes are equally unfenced |
| info_gain_if_investigated | **VERY HIGH** (T2/T6/T7 are cheap and each resolves a live unknown) |
| expected_alpha_contribution | **HIGH, mostly indirect** (breadth restoration, options axis, funding-history depth feed screens; DI-12 is the most direct) |
| expected_compounding_contribution | **VERY HIGH** (single-source scheduler, born-fenced metrics, funded organs are all multipliers) |

**CEILING EXPANSION:** the 85% ceiling silently assumes (a) one egress IP and REST-first collection — a
second IP + WS-first design lifts the 418 constraint class entirely; (b) LLM organ capacity bounded by one
subscription seat — a metered API key with auto-top-up alerts removes the organ-death class rather than
retrying it; (c) collection bounded to this box — Binance Vision bulk + object storage would make history
depth a purchase-free download problem. All three assumptions are organizational, not technological.

## CONTEXT — RELATION TO THE 2026-07-30 SWEEP

Yesterday's data-intelligence sweep (20260730, 27 findings, COMPLETE) is the baseline. This sweep does three
things it could not: (1) verifies which of its critical findings MOVED in 24h, (2) audits the managed cron
manifest installed ~23:00–23:29Z last night (`# installed 2026-07-30T23:29Z by deploy/reconstitute_cron.sh
(gap #58)`) — AFTER that sweep ran, (3) opens seams it never opened. Unmoved findings are re-cited by number
(F1–F27 = yesterday's ledger), not re-derived.

## 1. WHAT WE KNOW (validated strengths, each with proving command)

### S1. The moat recorder tier is alive and producing tonight, single-instanced right now
```
$ pgrep -af 'run_recorder'
426218 .venv/bin/python scripts/run_recorder_bybit.py
483236 .venv/bin/python scripts/run_recorder_spot.py
483446 .venv/bin/python scripts/run_recorder.py
$ for d in bybit spot fut execution_tape; do find data/moat/$d -type f -newermt '2026-07-31 00:00' | wc -l; done
bybit 40 / spot 42 / fut 52 files since 00:00Z   (execution_tape 0 — event-driven, see DI-6)
```
6.8 GB moat (`du -s data/moat/*`: bybit 5.5G, fut 0.9G, spot 0.5G). One instance of each recorder running.
The caveat that this is only ~11 days of depth (F5) stands.

### S2. BTC/ETH bronze daily bars were REVIVED since yesterday's F2 — partially
```
$ python: pd.read_parquet('data/lake/bronze/crypto/BTCUSDT/D1/year=2026/month=7/part-0.parquet').timestamp.max()
2026-07-31 00:00:00+00:00      # yesterday this series ended 2026-06-20
$ symbols with a D1 year=2026/month=7 partition: 146/278
```
The flagship series is current again — evidence yesterday's F2 was partially acted on within 24h. But 132/278
symbols (47%) still have NO July data (see DI-4).

### S3. The bronze architecture remains the strongest design in the estate (unchanged)
Yesterday's S2/S3 (hive-partitioned, tz-aware UTC parquet; 26y FX history; first-year histogram back to 2011)
re-verified by the same read path above; not re-derived here.

## FINDINGS LEDGER (DI-#, every claim command-cited)

### DI-1 — **[NEW, CRITICAL] THE CRON RECONSTITUTION OF 2026-07-30 INSTALLED A SECOND SCHEDULER NEXT TO THE FIRST. EVERY SHARED COLLECTOR NOW RUNS TWICE. THREE FEEDS MEASURED AT EXACTLY 2× WRITE RATE SINCE 23:00Z.**

`crontab -l` contains BOTH the legacy hand-maintained block AND the managed block
(`# installed 2026-07-30T23:29Z by deploy/reconstitute_cron.sh (gap #58)`). The legacy block was never
removed. Duplicated jobs: watchdog (×2 every 3 min), run_venue_divergence_shadow (×2 every 5 min),
ensure_recorder + both recorder respawn lines (×2 every 10 min), collect_defi_lending (×2 hourly),
collect_oi_ls_live (×2 hourly), collect_coinmetrics_flows (×2 daily 03:47), dl_oi_ls_universe (×2 daily
06:20), ingest_axes (×2 daily 06:40), kimi_hunter (daily 06:00 + every 4h + weekly deep).

Measured at the data layer — rows per hour, before/after 23:00Z:
```
data/defi_lending.jsonl        22:17 → 278   23:17 → 556   00:17 → 556      (exactly 2×)
data/oi_ls_live.jsonl          ...16/hr through 22:00 → 32/hr at 23:00, 00:00 (exactly 2×)
data/venue_divergence_shadow.jsonl  12/hr → 24/hr at 23:00, 00:00            (exactly 2×)
```
Payload duplication measured: of 1112 defi rows written 23:00Z+, **564 are payload-identical duplicates**
(all non-ts fields equal, `json.dumps(sort_keys)` hash). The rest differ only by seconds-apart re-reads.
These files have live research consumers — `grep -rln`: `scripts/build_defi_axis.py` (axis construction),
`scripts/data_vitals.py`, `scripts/claim_verifier.py`, `scripts/run_venue_divergence_shadow.py` — so the
doubling propagates into axis builds (double-weighted hours, biased-down within-hour variance) not just disk.

Three aggravators beyond waste:
1. **Recorder double-spawn race.** Both respawn lines fire the same minute (`*/10`) with only a pgrep guard
   and `grep -n 'lock' scripts/run_recorder_bybit.py` shows NO internal single-instance lock (the only hit
   is the word "clock"). On the next recorder death, both crons pass pgrep in the same second and spawn two
   recorders appending to the SAME hourly `.jsonl.gz` shard paths — corrupting the desk's single strongest
   dataset (moat). This has not happened yet (`pgrep` shows 1 of each) — it is armed, not fired.
2. **ingest_axes runs with DIFFERENT ARGS under DIFFERENT LOCK FILES.** Legacy: `--tranche 400` under
   `/tmp/ingest_axes.lock`; manifest: NO tranche (=> `tranche=None`, uncapped — `scripts/ingest_axes.py:282`)
   under `data/.cron_ingest_axes.lock`. Different lockfiles = no mutual exclusion; both fire 06:40 daily and
   can write the same bronze partitions concurrently. First collision: TODAY 06:40Z.
3. **Two watchdogs.** Legacy holds `/tmp/watchdog.lock`; the manifest line has NO flock and logs to a
   different file (`data/watchdog.log`). Whatever watchdog respawns can now be double-respawned.

Every doubled API poll also doubles external rate-limit consumption (DefiLlama, Binance, CoinMetrics
community) — vendor-ban risk on feeds with exactly one source (F10/F18: zero redundancy).

### DI-2 — **[UNMOVED FROM F1+F16, DAY 9] THE DISCOVERY ORGAN TIER IS STILL DEAD AND THE HEALTH MONITOR STILL CRIES WOLF. THE TWO HIGHEST-SEVERITY FINDINGS OF YESTERDAY DID NOT MOVE.**

```
$ systemctl list-units --all 'quant-*' --no-pager --no-legend
● quant-cro-ai.service    failed    ● quant-dataaxis.service  failed
● quant-litminer.service  failed    ● quant-prospector.service failed
  quant-frontier.service  inactive/dead
$ ls data/secrets/          # _BRAIN_KEYFILE=data/secrets/anthropic_api_key (ops/brain_env.sh:14)
binance_live.json ... claude_oauth_token ... ntfy.json     → anthropic_api_key ABSENT
```
The fallback that would resurrect the tier is still gated on a keyfile that still does not exist. Quota-death
rate remains 100%; acquisition capacity of the LLM dig tier remains zero (L1.8 violation, 9th day).
`data/data_vitals.json` still reports `"n_dead": 8` (`updated 2026-07-30T08:41Z`) — the 100%-false-positive
alert class of F1, byte-identical a day later.

### DI-3 — **[NEW, downgraded after verification] THE DATA-HEALTH ARTIFACT REFRESHES ONLY WITH THE DAILY CYCLE AND NOTHING WATCHES *ITS* STALENESS.**
```
$ stat -c '%y' data/data_vitals.json → 2026-07-30 08:41:47Z (16.5h at audit time; daily-cycle cadence)
```
Initial read ("monitor died") was wrong — `data_vitals` runs as a step of `daily_research_cycle.py`
(log shows `[data_vitals] {'ok': True…}`), so ~16h age is within cadence. The residual defects are real:
(a) a DATA-health monitor that samples once a day cannot catch an intraday collector death until the next
morning; (b) no fence fires if data_vitals.json itself goes stale — a monitor-of-the-monitor gap; (c) its
verdicts are still the 100%-FP class of F1, unchanged.

### DI-4 — **[PARTIAL FIX + NEW ANGLE] BRONZE CRYPTO REVIVED FOR 146/278 SYMBOLS; THE STALE 132 ARE UNDIAGNOSED, AND STALE-BECAUSE-DELISTED IS INDISTINGUISHABLE FROM STALE-BECAUSE-BROKEN.**
```
$ crypto symbols with D1 month=7: 146/278   (yesterday: ~80/277 fresh)
```
No delisting/lifecycle flag exists anywhere in the lake (no metadata column, no registry field — see F13).
A symbol that stopped trading and a collector that stopped collecting look identical: both just stop. This
conflation also poisons survivorship handling: a universe built from "symbols with fresh data" silently
becomes survivor-only. (Diagnosis of the 132 completed in DI-7: collector rot, not delisting.)

### DI-5 — **[UNMOVED] CROSS-ASSET/MACRO LAKE (88 instruments, 26y) STILL FROZEN** — F3/F7/F9 unchanged: no
month=7 partitions exist under fx/equity/metal/index/energy (verified via the same find used for crypto; the
MT5 feed remains architecturally unrunnable on this host and the free replacement has produced zero bytes).

### DI-6 — **[OBSERVATION] execution_tape last wrote 2026-07-28 15:20Z (2.4d)** while quant-cashcarry.service
is active/running. Event-driven (no fills → no rows), so not a defect by itself, but the Execution Reality
Model's only food source has 0 new observations in 2.4 days of an active executor — worth a look from the
execution seat (fills happening but unrecorded would be silent ERM starvation).

### DI-7 — **[NEW, HIGH] NO ORGAN OWNS "EVERY CRYPTO SYMBOL CURRENT DAILY." BRONZE FRESHNESS IS A SIDE EFFECT OF WHOEVER HAPPENS TO READ A SYMBOL.**

Write-time histogram of all 146 July D1 partitions (`stat` over `crypto/*/D1/year=2026/month=7`):
```
07-03..07-30: 1–7 symbols/day, every day        ← on-demand trickle by consumer scripts
07-31 00:xx : 54 symbols in one batch            ← a rescue batch at ~00:13 today
```
The June-20 outage (F2) was "fixed" by consumers touching the symbols they need, not by restoring a
scheduled full-universe collector. The 132 still-frozen symbols cluster at last-bar **2026-06-21 (114 of
132)** and include indisputably active contracts (`1000PEPEUSDT`, `1000SHIBUSDT`, `1INCHUSDT`) — so this is
collector rot, not delisting. Until a job OWNS full-universe daily refresh, June-20 recurs whenever the
consumers' symbol set narrows. (Cross-sectional research on "all symbols with fresh data" silently becomes
research on "whatever the live sleeves happen to trade" — a selection-bias machine.)

### DI-8 — **[NEW, HIGH] THE OI/METRICS ARCHIVE COLLECTOR KEEPS CURRENT BUT REPAIRS NOTHING: ITS OWN LOG ADMITS 300–1,663-DAY HOLES PER SYMBOL EVERY DAY, AND THE `futclose` SIDE HAS FLATLINED AT +0.**
```
$ tail data/cro_ai_logs/dl_oils_daily.log
TRXUSDT: +1 metric days (312 missing), +0 closes
RENUSDT: +0 metric days (915 missing), +0 closes
RAYUSDT: +0 metric days (1663 missing), +0 closes ... DONE: 139 symbols
$ find data/lake/bronze/futclose_daily -type f -printf '%T@\n' | sort -rn | head -1 → 7.1 days old
```
Every day it appends yesterday's file (+1) and re-prints the same hole counts; the holes never shrink.
`+0 closes` on ALL 139 symbols and a 7.1-day-old futclose_daily while sibling classes updated 18h ago =
the closes code path is dead. This is yesterday's F19 (no gap repair) at day-granularity, self-documented
daily and never actioned — the exact "green log, no outcome" class.

### DI-9 — **[NEW, HIGH] THE PAID HUNTER ORGAN (kimi_hunter) IS 402-BLOCKED WITH 59% OF ITS MONTHLY BUDGET UNSPENT. COMBINED WITH F16, THE *ENTIRE* LLM ACQUISITION TIER IS FUNDING-DEAD ACROSS BOTH PROVIDERS.**
```
$ tail data/cro_ai_logs/kimi_hunter.log
budget: MTD $49.66 of $120.00 envelope
WAVE 1 -- SHADOW MAPPING → FAILED (HTTPError 402)  "OpenRouter is out of credit."
```
Claude-side organs: dead on subscription quota with no API-key fallback (DI-2). OpenRouter-side hunter:
dead on balance while $70.34 of authorized envelope sits unspent (L1.28a: idle budget = idle capital).
Adjacency (battery move 2): the same failure SHAPE — LLM organ dies on funding, exits politely, nothing
pages — now exists in two independent providers. No alert class exists for "organ blocked on funding."

### DI-10 — **[NEW, HIGH] BINANCE IS TEAPOT-BANNING THE DESK'S IP (HTTP 418) INSIDE THE DAILY CYCLE — THE ORGANS DYING ARE FORWARD-EVIDENCE CLOCKS AND THE NAV TRUTH CHAIN. THE CRON DOUBLING (DI-1) DOUBLES THE REQUEST RATE FEEDING THE BAN.**
```
$ grep -c 418 data/cro_ai_logs/daily_research_cycle.log → 11
organs hit (grep -B1): shadow_8h, axis_shadows, cost_model, cny_premium, nav_attest, listing_watch
[axis_shadows] {'ok': False, 'tail': "HTTPError 418: I'm a teapot"}   ← 2026-07-30 cycle
```
418 is Binance's escalating auto-ban for IP-level request-weight abuse. Victims include `shadow_8h` (the
√3× evidence-density panel) and `axis_shadows` (Stage-A forward clocks) — i.e. **Stage-B evidence accrual
stalls on ban days**, and `nav_attest` (the live-book truth every capacity ratio reads). These 418s predate
DI-1 (11 hits across several daily runs) — the duplication makes an already-banning request pattern 2× worse
tonight. No request-weight budget, backoff coordinator, or per-organ rate accounting exists desk-wide; a
dozen organs poll one venue from one IP without a shared limiter.

### DI-11 — **[NEW, MEDIUM] COT Z-CACHE FROZEN AT 2026-06-21 — A SIXTH WEEKLY CFTC REPORT MISSED — SAME DEATH DATE AS THE MT5 ESTATE (F7 CASUALTY LIST GROWS).**
```
$ python: pd.read_parquet('data/cot_zcache.parquet') → (8405, 11), max ts 2026-06-21
```
Columns are MT5-style instruments (XAUUSD, EURUSD…) — the COT positioning axis rode the MT5 pipeline and
died with it. CFTC data itself is free and publishes weekly (govt portal — FREE-FRONTIER source class);
only the transport died. Nothing flagged a 40-day-stale weekly series.

### DI-12 — **[NEW, POSITIVE + OPPORTUNITY] A LIVE DERIBIT OPTIONS SURFACE COLLECTOR EXISTS AND WROTE TODAY — THE OPTIONS AXIS HAS SPROUTED, BUT AT ~2 SNAPSHOTS/DAY AND ATM-ONLY IT IS TOO THIN TO SCREEN THE VRP RESURRECTION IT UNLOCKS.**
```
$ pd.read_parquet('data/deribit_surface.parquet') → (76, 6) [ts, currency, atm_iv, skew, term, spot]
   range 2026-06-26 → 2026-07-31T00:11Z  (~2.2 rows/day; producer scripts/collect_deribit_surface.py,
   read by run_cashcarry_executor.py)
```
35 days × 2/day × ATM-only is not a surface — it is a pulse. The alpha-discovery seat flagged the options
VRP graveyard entry as resurrectable on new data; the enabling collector EXISTS and is alive, so the
cheapest unlock is cadence (hourly) + a few strikes per expiry, not new engineering.

### DI-13 — **[NEW] THE RECOMMENDATION LEDGER DOES NOT KNOW ABOUT DI-1. NOTHING TRACKS THE DUPLICATION; 33 OF 69 ROWS SIT OPEN.**
```
$ python parse docs/research/recommendation_ledger.json → 69 rows {open:33, scheduled:20, rejected:4, implemented:12}
   rows mentioning cron/manifest/duplicate/reconstitute: 3 — none about dual-scheduler duplication
```
The doubling began ~23:00Z and no organ noticed by 01:00Z: not watchdog (it is itself doubled), not
data_vitals (daily cadence, wrong verdicts anyway), not check_ratchets. **There is no write-rate anomaly
fence on any collector output** — rows/hour doubling is invisible to every existing monitor. (Ledger rows
for every DI finding are queued in the RECOMMENDATION LEDGER COMMANDS section — this seat is read-only.)

### DI-14 — **[NEW, MEDIUM] THE DAILY CYCLE RUNS TWO STEPS WITH A MALFORMED INVOCATION THAT CAN NEVER SUCCEED — `'scripts/research_exchange.py brief'` PASSED AS ONE FILENAME — AND THE CYCLE STAYS GREEN AROUND THEM (F17'S SHAPE, TWO MORE INSTANCES).**
```
[desk_brief]        {'ok': False, 'rc': 2, 'tail': "can't open file '…/scripts/research_exchange.py brief'"}
[contributor_score] {'ok': False, 'rc': 2, 'tail': "can't open file '…/scripts/research_exchange.py score'"}
```
Structural, not transient: the arg is concatenated into the path, so these fail every run, forever, and
have — the cycle proceeds regardless. Also present in the same run: `reject_rescore` reports "re-eval hook
not wired on this host" (honest, but another configured-not-wired organ).

### DI-15 — **[NEW] PANEL CLAIM "69k THREAD CATALOG BUILT" vs 713 ROWS ON DISK — THE ERA-ARCHAEOLOGY CONVERSION IS OVERSTATED ~97× IN THE PANEL INBOX.**
```
$ wc -l data/8btc_era_thread_catalog.jsonl → 713    (only artifact matching *8btc*/*era_thread* in data/)
docs/research/panel_inbox.md:35: "Era-archaeology: … 69k thread catalog built"
docs/research/prospector_coverage.md:459: "Catalogs → data/8btc_era_thread_catalog.jsonl"
```
§33: conversion is credited from artifacts on disk, never from reports. Either 68k rows were never written,
or they live in an unscanned location — both are defects (the second fires mine-scope-unmonitored). The
CN archaeology axis (L1.11a names pre-ban CN explicitly) is real but ~1% the size its own paperwork claims.

### DI-16 — **[BARELY MOVED FROM F11] THE DATA GENOME HOLDS 4 ENTRIES AGAINST A ~60-SOURCE ESTATE — 93% OF LINEAGE/HALF-LIFE UNMAPPED.**
```
$ python: json.load('data/knowledge_engine.json') → {'corpus_size': 247, 'genome': 4, ...}
```
Yesterday: zero rows. Today: 4. The constitutionally mandated lineage layer (L1.11: "a data genome tracking
lineage and half-life") covers ~7% of catalogued sources. The machine-writable registry that could feed it
(`scripts/build_data_registry.py --deep` → `data/data_assets.json`) has NEVER produced — first cron fire is
04:27Z today (`ls data/data_assets.json` → No such file). Same for the label factory
(`data/label_registry.json` absent, first fire 04:52Z) and `check_utilisation.py` (log exists, empty, first
fire 06:27Z). Three organs installed last night are configured-but-never-run as of 01:15Z — grade them
tomorrow by artifact, not by cron entry.

## 2. WHAT WE DON'T KNOW (ignorance ledger)

1. **Which process wrote the 54-symbol bronze rescue batch at 00:13Z today.** Not identifiable from cron
   schedules (nothing fires at :13); organ_catchup logged "nothing owed" at 00:10. An unattributed writer
   mutating the lake is itself a lineage gap (no run-stamp layer — F11's wiring gap made concrete).
   `find data/cro_ai_logs -newermt '00:05' ! -newermt '00:25'` narrows to 6 logs, none of which is a
   kline refresher.
2. **Whether the two ingest_axes variants (--tranche 400 vs uncapped) corrupt binance_metrics partitions
   when they collide at 06:40Z today.** Unknown until it happens — DO NOT let it happen (see §3 rank 1).
3. **Whether 418 bans are request-weight escalation or datacenter-IP classification.** If the latter, a
   limiter won't fix it and a second egress IP / WS-first collection is the only route. Distinguishable:
   log ban duration + Retry-After headers on next occurrence (T6).
4. **Whether moat spot/fut depth records (top ~20 levels) are sufficient for the ERM's impact modelling** —
   F24 showed 300 probes never exhausted a book; unclear if that is thin books or truncated depth capture.
5. **Whether any live screen actually consumes moat-derived features** (feature_library.json is produced
   daily — its downstream consumption is unverified this sweep).
6. **Whether the "69k" era-catalog exists somewhere unscanned** (DI-15) — resolvable by asking the CN miner
   session for its artifact path, or re-running the catalog build.
7. **The blast radius of double-watchdog side effects** (alerts double-sent? respawn races beyond
   recorders?) — organ_catchup double-logging pattern observed ("nothing owed" twice per tick, 0.3s apart)
   but not conclusively attributed; the collector row-rate doublings are conclusive, watchdog's are not.
8. **Data-cost ledger**: no artifact prices the estate (API quotas consumed/day, kimi $/find, disk GB/axis).
   check_utilisation.py may cover part after its first fire.

## 3. WHAT COULD MATTER MOST (ranked by impact × confidence / (cost × maintenance))

**Rank 1 — De-duplicate the scheduler TODAY, before 06:40Z (DI-1).** Migrate the legacy-only cron jobs
(cro_ai, max_audit, growth_audit, quota_verdict, roster, crypto_factory, daily cycle 02:00, organ_catchup,
page_digest, deep_sweep, old kimi/defi/oils lines) INTO `ops/crontab.manifest`, then delete the legacy block
from the live crontab once. pull_deploy now self-installs the manifest on hash change (hook newly added —
observed live in deploy/pull_deploy.sh during this audit), so
manifest-only is durable; hand-editing the managed block is futile by design. Expected benefit: stops 2×
writes on ≥3 feeds, disarms the recorder double-spawn trap and the 06:40 ingest_axes collision, halves
Binance poll load. Complexity: LOW (hours). Failure mode: dropping a legacy-only job during migration —
diff `crontab -l` before/after against the union. Validation: T1/T2. Maintenance: none (single source).
Retirement: never (this IS the single-source end state). Alternative considered: comment out manifest
duplicates instead — rejected, reconstitute reinstalls them. Interaction: gap #58 row (operator crontab
paste due 2026-08-05) should close with this.

**Rank 2 — Re-fund the LLM acquisition tier (DI-2 + DI-9): create `data/secrets/anthropic_api_key` and
top up / re-route OpenRouter.** The entire dig tier (dataaxis, frontier×7 languages, prospector, litminer,
cro-ai, kimi) is funding-dead. This is the subsystem's L1.13 bottleneck: no engineering below this line
matters while acquisition capacity is 0 and $70/mo of authorized spend sits idle. Principal action required
(minutes). Validation: next timer fire produces a log artifact with a non-402/non-quota exit. Add an alert
class: organ exits on quota/402/credit → page (currently exits politely, invisible).

**Rank 3 — Give bronze crypto an OWNER (DI-7).** One manifest job: full-universe daily kline refresh
(Binance Vision bulk for backfill, REST for the tail), per-symbol status artifact, write-rate fence. Also
backfills the 132 frozen symbols (40 days each, free). Benefit: kills the June-20 rot class; restores the
full cross-section (survivorship-clean universes need symbols that DIED to stay collected too). Complexity:
LOW-MED. Validation: T4 (278/278 fresh). Maintenance: the fence watches it.

**Rank 4 — Venue request-weight coordinator + 418 circuit breaker (DI-10).** Shared token bucket per
(venue, IP) in libs/, all REST pollers route through it; on 418/429: exponential hold, page, and log
Retry-After. Protects forward clocks (shadow_8h, axis_shadows), NAV attestation, and cost model — the
organs that convert data into Stage-B evidence. Complexity: MED. Failure mode: a limiter set too low
starves collectors — start at 50% of Binance's published weight and ratchet UP on zero-418 weeks (L1.0).

**Rank 5 — Write-rate anomaly fence for every appending collector (DI-13).** Extend check_ratchets: per
JSONL/parquet output, expected rows/period (learned trailing median) with ±50% alarm. Today's doubling and
any future silent HALVING both become page-able events. Cheap (one script + one committed floor artifact),
catches an entire failure class, compounding multiplier. Validation: it must fire on the current defi file
retroactively.

**Rank 6 — Thicken the Deribit surface (DI-12): hourly snapshots + 3–5 strikes/expiry.** Collector exists
and is alive; this is a cadence knob, not new engineering. Unblocks the VRP resurrection screen (named
enabling change per L1.16a) once ~60 daily observations accrue. Low cost, direct new-axis alpha shot.

**Rank 7 — Repair the OI/metrics archive (DI-8): fix the dead futclose path, add a hole-draining tranche
(N oldest missing days/symbol/day).** The code already prints its own holes; consume that list. At even
+50 days/symbol/day the 312-day median hole closes in a week instead of a year.

**Rank 8 — Revive COT via CFTC direct (DI-11).** Free weekly government CSV; drop the MT5 transport
dependency. Also the proving instance for "free primary behind a dead paid-ish transport" (battery move 5).

**Rank 9 — Genome/registry coverage 4→60 (DI-16).** Tomorrow, verify `data_assets.json` + `label_registry.json`
exist and are non-trivial (first fires 04:27/04:52Z today); wire registry output INTO the genome so lineage
coverage is generated, not hand-written. If the fires produced nothing, that is a day-one F-class finding.

**Rank 10 — Correct the era-archaeology record (DI-15).** Either locate/produce the 69k catalog or amend
panel_inbox to 713; §33 credit must match disk.

## 4. WHAT WE TEST NEXT (experiments w/ success criteria)

- **T1 (post-Rank-1):** 24h after de-dup, `defi_lending` back to ~278 rows/hr, `oi_ls_live` 16/hr,
  `venue_divergence` 12/hr, zero payload-duplicate hashes. Success = all three at baseline. Also decide
  and execute dedup/annotation of the contaminated 23:00Z→fix window (consumers must not average it).
- **T2 (TODAY 06:40Z watch):** if Rank 1 lands first — nothing to test. If not: immediately after 06:40,
  `pgrep -af ingest_axes` during the window + parquet integrity scan of binance_metrics partitions written
  today (readable, row counts sane, no duplicate dates). Failure → quarantine today's partitions.
- **T3 (recorder respawn drill, after Rank 1):** kill run_recorder_spot in a controlled minute; success =
  exactly ONE new PID within 10 min and the hour's shard has no duplicate (t, u) records. (Autonomy check:
  respawn has been configured for weeks but double-spawn safety has never been SEEN.)
- **T4 (post-Rank-3):** `crypto symbols with D1 month=7 == 278/278`; spot-check 10 backfilled symbols for
  bar-close ≤ now (no look-ahead) and continuity across the 2026-06-21 seam.
- **T5 (post-Rank-6):** when surface has ≥60 hourly rows: pre-register VRP screen through
  libs.research.axis_screen (mechanism prior: variance risk premium; target: mechanism-appropriate, NOT
  reflexive next-day-BTC; log every construction per the target/horizon sweep duty).
- **T6 (next 418):** capture ban duration + Retry-After; classification decides Rank 4's design (limiter
  vs second egress). Success = a written verdict in the reality-gap log, either way.
- **T7 (tomorrow):** artifact-grade the three organs that first-fire today (data_assets.json,
  label_registry.json, utilisation.log non-empty with ceilings enumerated). Success = all three non-empty
  and sane; any empty one gets a finding row same day.

## SIX-PERSPECTIVE COVERAGE TABLE

| Perspective | Findings (all command-cited above) |
|---|---|
| INTERNAL | DI-1 (2× write rates measured at the row level), DI-7 (mtime histogram proves ownerless refresh), DI-8 (self-logged holes, +0 closes), DI-3 (monitor cadence + no meta-fence) |
| EXTERNAL | A world-class desk would run: a per-venue request-weight budgeter (Rank 4), a second independent feed for majors (F10 still at zero; free candle APIs exist at Coinbase/Kraken/OKX), and an exchangeInfo-snapshot delisting calendar so entity lifecycle is data, not inference (DI-4). None exist here. |
| FUTURE | The pull_deploy self-installing manifest (newly landed) is the right 2–3y pattern — schedulers as derived state; extend it to the systemd units (8 of them uncommitted per F21). Immutable/vintage lake writes (fixes F11/F15 overwrite-in-place) become cheap with parquet snapshot layers; plan for it rather than more in-place writers. Funding-fixed LLM organs make multilingual archaeology (L1.11a) scale at ~zero marginal engineering — the constraint is DI-2/DI-9, not capability. |
| CONTRARIAN | Tested and REJECTED my own first read of DI-3 ("monitor died" → actually daily cadence; report corrected in place). Tested "more polling = more data": FALSE at the margin — the 418 evidence (DI-10) shows added pollers now REDUCE delivered data by feeding bans; complexity measurably reducing robustness. "Bronze architecture is good" holds for layout/tz but NOT for mutability: in-place overwrites (F11) mean a bad write destroys history with no vintage to roll back to. |
| GREENFIELD | Rebuild would have: ONE scheduler source (exists as of last night — finish it, Rank 1), ONE collector framework with shared rate budget + backfill-on-start, ONE recorder schema (today: bybit `depth/trades/meta` vs spot/fut `d/t` — two dialects, every consumer needs two parsers), ONE research DB (today: 7 `sor_*.sqlite` variants incl. `sor_research_lake.sqlite` AND `sor_research_lake_v2.sqlite` — schema evolution by file proliferation). Baggage score: moderate and mostly cheap to retire. |
| FRONTIER | Deribit surface collector already live (DI-12) — thicken, don't build. CFTC direct weekly CSV replaces the dead MT5 COT transport (DI-11). Binance Vision bulk archives cover the 132-symbol backfill AND deep funding history free. farside ETF flows already collected daily (verified fresh 07-30) — a genuinely current frontier axis already owned. |

## NEGATIVE-SPACE SWEEP (never collected / asked / simulated — with what was checked)

- **Languages:** KR=5 datasets, CN=2 (`ls data | grep` counts); AR/RU/JP/TR/PT = **zero artifacts**
  (grep for jp_/ru_/arab/turk/brl/_pt over data/ → empty). The organ that would dig them (quant-frontier,
  7-region rotation) is dead (DI-2). Either dig or grade residual_gap per the FREE-FRONTIER duty — currently
  neither: the search has simply not run.
- **Entity resolution:** no symbol/entity map anywhere (`grep -rln symbol_map|SYMBOL_MAP|entity_map libs/
  scripts/` → empty). Cross-venue joins rely on string equality of venue tickers.
- **Delisting/lifecycle calendar:** does not exist; DI-4 shows the cost (stale-vs-dead indistinguishable).
- **Restatement/vintage tracking:** F15 unchanged — no vintages anywhere in the lake.
- **Order book beyond top-of-book bands:** bybit 25 levels, spot/fut ~20 (measured in DI shard census);
  full-depth never archived. Pre-2026 L2: correctly graded residual_gap previously (destroyed at source).
- **Deep funding-rate history:** hyperliquid_funding.parquet = 17,596 rows; bybit funding only via 11 days
  of moat meta records. Multi-year funding archives (free on venue archives) never pulled — this axis
  (thin-pair funding, §42 named ground) runs on a puddle.
- **Exchange status/incident feeds:** never collected; venue maintenance windows would explain data gaps
  and de-noise the ban/outage attribution this report struggled with (DI-10 unknown #3).
- **Simulations never run:** collector-death drill (T3 is the first), venue-ban failure mode (being run
  involuntarily in production instead), lake-corruption restore drill (rollback/ dir exists, 104MB, never
  exercised per absence of any drill artifact — checked cro_ai_logs filenames for 'drill'/'restore': none).
- **Alive-and-well negative-space closures found this sweep (credit where due):** stablecoin supply
  (900-day history, z-scored, daily), liquidations listener (parquet written 01:13Z today), ETF flows
  (farside HTML daily through 07-30), CNY OTC premium (n=8 building), Deribit surface (DI-12).

## PROACTIVE BATTERY MOVES RUN (all 10; per-move outcome)

1. Contingency-before-failure → recorder double-spawn is ARMED with no lock (DI-1 aggravator 1); MT5
   replacement still zero bytes (F9 unchanged). 2. Adjacency → kimi-402 matches Claude-quota organ-death
shape (DI-9); COT and crypto bars share the June-21 death date (DI-11). 3. Config-vs-outcome → three organs
installed last night have zero artifacts (DI-16); utilisation fence never fired (empty log). 4. Regression
sweep → what gap #58's fix made worse: DI-1, measured. 5. Cost inversion → kimi paid route dead while $70
free-to-spend envelope idles; COT's free primary (CFTC) was behind a dead transport. 6. Generalise-the-rule
→ no write-rate fence exists for ANY collector, not just the three caught (DI-13). 7. Autonomy check →
respawn configured-but-never-drilled (T3); manifest self-install SEEN working (reconstitute_auto.log) but
produced DI-1. 8. Negative space → section above. 9. Scope-the-negative → 418 = ROUTE (this IP, REST)
blocked, not "Binance data unavailable" (WS recorders unaffected, running); my own DI-3 first-read narrowed
from capability-death to cadence-limit. 10. Ratchet check → bronze freshness, collector row-rates, genome
coverage, language-axis counts all have NO floor artifact today; Ranks 3/5/9 create them born-fenced.

## RECOMMENDATION LEDGER COMMANDS (for the synthesis/disposition seat — this seat is read-only by charter)

```sh
p=.venv/bin/python
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 80 \
  --summary "DI-1: remove legacy cron block, migrate legacy-only jobs into ops/crontab.manifest; 3 feeds measured at 2x write rate since 23:00Z; ingest_axes arg/lock divergence collides 06:40Z daily; recorder double-spawn armed"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 120 \
  --summary "DI-2/DI-9: fund LLM acquisition tier -- create data/secrets/anthropic_api_key + restore OpenRouter balance (59% of kimi envelope idle); add page-on-quota/402 alert class; tier dead day 9"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 60 \
  --summary "DI-7: create owned full-universe daily crypto kline job + backfill 132 symbols frozen since 2026-06-21 (Binance Vision, free); freshness currently a consumer side-effect"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 50 \
  --summary "DI-10: per-venue request-weight coordinator + 418 circuit breaker; bans currently killing shadow_8h/axis_shadows/nav_attest inside daily cycle (11 hits)"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 40 \
  --summary "DI-13: write-rate anomaly fence (learned rows/period +-50%) for every appending collector output, committed floor artifact, retro-fires on current defi file"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 35 \
  --summary "DI-12: Deribit surface to hourly + 3-5 strikes/expiry; unlocks pre-registered VRP resurrection screen (collector already live)"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 30 \
  --summary "DI-8: fix dead futclose path (+0 closes x139 symbols, 7d stale) and add hole-draining tranche to dl_oi_ls_universe (312-1663d holes self-logged daily, never repaired)"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 25 \
  --summary "DI-11: revive COT axis via CFTC direct weekly CSV (free), retiring the dead MT5 transport; frozen 2026-06-21"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 20 \
  --summary "DI-16: wire build_data_registry output into knowledge-engine genome; coverage 4/60 sources; artifact-grade the three first-fire organs (T7)"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 10 \
  --summary "DI-15: reconcile era-archaeology claim (panel_inbox '69k catalog') with disk artifact (713 rows); SS33 credit must match artifacts"
$p scripts/recommendations.py add --source deep_sweep/20260731_data-intelligence.md --roi-bps 15 \
  --summary "DI-14: fix malformed daily-cycle invocations (research_exchange.py 'brief'/'score' passed as one filename, rc=2 every run) or retire the steps"
```
