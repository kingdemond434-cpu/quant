# DEEP COLD AUDIT — DATA-INTELLIGENCE — 2026-07-26

**Subsystem:** every dataset (quality/coverage/latency/history/cost), collection architecture,
redundancy, vendor concentration, survivorship, timestamp consistency, entity resolution,
schema evolution, repair automation, backfill capability, metadata, versioning, lineage,
reproducibility; derived/synthetic datasets, weak-labels, cross-source enrichment,
alt-language sources, gov publications, archives.

**Auditor:** weekly deep cold audit (read-only). **Status:** COMPLETE.
**Method:** outcome-not-config — every claim below carries the command that proved it and what
the command printed. No claim is from a config file's promise.

## SCORES

- **current_capability_pct: 55%** — collection breadth/discipline is genuinely strong
  (3-venue L2 moat, uniform-schema 268-symbol lake, audited screen harness, live paid-data
  reconstructions); but the research surface is D1-only, the universe is survivorship-biased,
  health monitoring covers ~10% of datasets, and the irreplaceable forward captures have zero
  backup.
- **practical_ceiling_estimate: 90%** (of what a world-class free-first crypto data org on
  this budget achieves). ceiling_gap: **35 pts**.
- **opportunity_cost_1y: HIGH.** Three components: (1) the intraday hypothesis space —
  the largest untested orthogonal family — stays structurally untestable while the lake is
  D1-only (free to close via Binance Vision); (2) every cross-sectional backtest on the
  lake carries unquantified survivorship inflation → risk of a false promotion, which the
  doctrine prices as negative discovery; (3) a single disk failure erases every
  "destroyed-at-source, recorder-solves-forward" asset — the compounding moat thesis
  itself. Item 3 is a tail cost, not an expected cost, but it is the only tail in the data
  system that is 100% preventable for <$1/mo.
- **confidence: 0.8** on the findings (all command-verified today); **0.6** on the impact
  ranking.
- **unknown_unknown_score: 0.35** — the collection side is now well mapped; the usage side
  (which consumers silently assume survivorship-free data, actual 418 recurrence rate,
  wallet-label coverage %) still holds surprises.
- **info_gain_if_investigated: high** for survivorship quantification and moat-extraction
  pilot (both cheap, both produce reusable knowledge either way).
- **expected_alpha_contribution:** intraday lake + Tron stablecoin leg + universe-wide
  positioning history + COT revival = 3–4 new orthogonal, mechanism-backed axis families
  feeding the clock-saturation duty (currently only 3 clocks accruing vs need=40 days each).
- **expected_compounding_contribution:** registry-driven health coverage, offsite backup,
  and a shared Binance request budget each protect or multiply EVERY future dataset — the
  classic compounding-multiplier class.
- **CEILING EXPANSION:** the 90% ceiling assumes one VPS + free-data posture. Two cheap
  purchases move the ceiling itself: (a) S3-class cold storage (<$1/mo now, ~$2/mo at
  1-year moat size) makes every forward capture durable; (b) a second $5 collector VPS adds
  IP diversity (kills the 418 class permanently) and collection redundancy. Neither touches
  the paid-DATA posture — they are infrastructure, not data purchases.

---

## 1. WHAT WE KNOW (validated strengths, each with its proving command)

**S1. The forward-collection moat is real, live, and multi-venue.**
`ls -la data/*_heartbeat` + `date -u` → recorder/spot/bybit heartbeats at 11:19–11:20Z against
now=11:20Z. `find data/moat -type f -printf '%T+ %p\n' | sort -r | head` → files written at
11:20:44Z. Content check (`zcat data/moat/spot/BTCUSDT/20260726_10.jsonl.gz | head`) shows
top-20 L2 depth diffs with ms timestamps and update-ids for Binance spot, Binance futures, and
Bybit; recorder logs confirm trades captured alongside depth ("depth@1.0s trades@5.0s", weight
budget computed in `scripts/run_recorder_spot.py:97-116`). Sizes: bybit 2.8G, fut 508M, spot
235M (`du -sh data/moat/*`). No pruner exists (`grep -nE "prune|rotate|delete|unlink|retention"
scripts/run_recorder*.py scripts/ensure_recorder.py` → no hits) — earliest files are the
recorder START dates (fut 2026-07-17, spot/bybit 2026-07-21), so this is a compounding asset,
not a rolling window.

**S2. The crypto research lake has uniform schema across its full 7-year span.**
268 symbols, D1 (`python: os.listdir('data/lake/bronze/crypto')` → 268; timeframes {D1: 268,
H8: 10}). BTCUSDT D1 spans 2019-10-01 → 2026-07-26 (83 partition files). Schema check on
ARBUSDT 2023 vs 2025 vs BTCUSDT 2019: identical 9 columns
`[timestamp, open, high, low, close, volume, taker_buy_frac, funding, basis]`, tz-aware UTC.
Derived enrichments (funding, basis, taker fraction) are unified into the same table — this is
what a good research surface looks like, at the granularity it covers.

**S3. The screen harness enforces timestamp-alignment and lookahead rails in code.**
`grep -nE "alignment|lookahead" libs/research/axis_screen.py` → lines 39-40 document the
KST-candle lookahead failure mode; line 107 the misalignment signature; line 114 the
implausibility rail (`abs(ic) > ic_ceiling or best > sharpe_ceiling`). The de-contamination
gate that graveyarded Coinbase-premium and Turkey-premium is baked into the one audited
entrypoint. (The 1-row `data/try_premium.jsonl` / `data/venue_premium_coinbase.jsonl` files are
remnants of those killed axes, not frozen clocks — verified against
`data/axis_shadow_state.json`, which shows the real Stage-B roster.)

**S4. Free-first reconstruction of paid products is live and measurably tight.**
`head data/kaiko_vwm_reference_rate.jsonl` → 5-min Kaiko-rule VWM/TWAP vs desk cross-venue
VWAP, diff −3.0 to −3.6 bps, 132 rows, updated 2026-07-26 00:59. CoinMetrics flows
reconstruction: 9,866 rows back to 2010-07-18 (`wc -l`, `head`), updated 00:54 today. The
universe map posture line ("~$1.5k paid basket replaced at $0") is, on these two exhibits,
earned rather than claimed.

**S5. Negative knowledge is a first-class output — including for paid data.**
The $2 Databento CME foundation pull (provenance in `scripts/pull_cme.py` docstring: broad
cheap layer now, $0.76/day MBP-10 reserve held) was converted to a screen within days:
`grep cme docs/research/AXIS_PREREGISTRATIONS.md` → `cme_anchored_basis_dislocation | 0.0326 |
0.48 | REJECT (EV below thresh)`. Screened, rejected, logged. The discipline pipeline
(mechanism → screen → verdict → registry) demonstrably runs end-to-end on new axes.

**S6. Organ resilience recovered this morning's rate-limit failures.**
02:00Z daily-cycle steps `axis_shadows`, `shadow_8h`, `listing_watch` failed with Binance
HTTP 418 (`grep -B2 -A1 418 data/cro_ai_logs/daily_research_cycle.log`), yet
`data/axis_shadow_state.json` shows updated 08:32Z with kimchi `last: 2026-07-26`, and
`data/kimchi_premium.jsonl` has today's row. The `organ_catchup` cron (every 5 min) re-fired
the failed organs after the ban lapsed. Failure → automatic recovery, observed, same day.

**S7. Survivorship-complete data EXISTS on disk — in the secondary datasets.**
`wc -l data/lake/bronze/futclose_daily/SRMUSDT.jsonl` → 1,093 rows (from 2021-06-01);
WAVESUSDT → 1,851 rows. The 139-symbol futclose/oi_ls universe includes delisted names. The
raw material for a survivorship-free universe is already collected daily.

**S8. The transactional store has real versioning discipline.**
`sqlite3 ... "select name from sqlite_master"` on sor/alpha_registry DBs → `schema_migrations`,
`snapshots`, `config_versions`, `audit_log`, `trials_ledger` tables present. Schema evolution
on the system-of-record side is governed. (The LAKE has no equivalent — see W4.)

**S9. Disk headroom is currently comfortable and measured.**
`df -h /home/quant` → 38G disk, 9.5G used, 27G free (27%). At the moat's observed ~400MB/day
(3.5GB over ~9 days), ~67 days of headroom before pressure — enough time to implement tiering,
not enough to ignore it (see W9).

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

**U1. How much survivorship bias is already baked into past cross-sectional results.**
The D1 lake excludes every delisted symbol: `for s in SRMUSDT TOMOUSDT WAVESUSDT FTTUSDT
LUNAUSDT; [ -d data/lake/bronze/crypto/$s ]` → all five ABSENT, while `listing_universe.json`
(the feeder universe, refreshed 08:32 today) contains only currently-listed perps. LUNA and FTT
— the two most catastrophic delistings in the asset class — are invisible to every backtest run
on this lake. Unknown: the magnitude (could be small at short horizons; must be measured, see
T2) and which past rejections/acceptances it touched.

**U2. Actual Binance 418 recurrence rate and its trigger.**
Only one day's evidence in the logs (`grep -c 418 data/cro_ai_logs/daily_research_cycle.log` →
3, all this morning; no other log contains 418). 22 scripts hit Binance
(`grep -rlE "binance\.(com|vision)|fapi\.binance" scripts/*.py | wc -l` → 22) with NO shared
rate budget (`grep -rn "rate" libs/data/*.py | grep -iE "limit|throttle"` → only comments; the
spot recorder self-budgets, `run_recorder_spot.py:97`, but nothing coordinates ACROSS
processes). Unknown: which organ spikes the weight, how often bans recur, whether they'll hit
the live trading path (today's `crypto_target.json` refreshed fine at 08:30).

**U3. Exchange-wallet label coverage and decay.**
`grep -cE "0x" libs/data/onchain_flows.py` → 18 hardcoded addresses drive the stablecoin
reserve/netflow signal. Unknown: what fraction of true exchange reserves those 18 wallets
capture today, and the decay rate as exchanges rotate wallets. No refresh process, no drift
alarm. The signal will degrade silently by construction.

**U4. Whether the moat's top-20 depth is deep enough for the execution research we'll want.**
Recorder captures 20 levels (`zcat ... | head` shows b/a arrays capped at 20). Sufficient for
spread/imbalance/near-touch work; NOT for deep-book resilience or large-cascade impact studies.
Unknown until a concrete microstructure card demands more. Cheap to raise (depth limit=100
costs the same weight class on Binance REST: `run_recorder_spot.py:102` notes limit≤100 = 5
weight) — but only worth it once a card asks.

**U5. Whether stooq blocks or the symbols are wrong on the dead cross-asset legs.**
`tail data/cro_ai_logs/ingest_axes_cron.log` → `crossasset/SPX: stooq returned no data
(symbol?)` — same for NASDAQ, GOLD, WTI, DXY_fut. Only VIX (CBOE official, 9,237 rows) and UST
curve (9 files) are alive. Untested: corrected stooq tickers (`^spx`, `xauusd`, `cl.f`) vs
datacenter-IP blocking vs endpoint change.

**U6. COT cache contents and Linux runnability.**
`data/cot_zcache.parquet` spans 2000-01-03 → 2026-06-21, 8,405 rows, stale 5 weeks — it died
the same date as the whole MT5-era pipeline. `libs/data/cot_source.py` exists; no cron
schedules it (`crontab -l | grep -i cot` → nothing). Unknown: whether the cache includes CME
BTC/ETH markets and whether the collector runs on Linux unmodified. CFTC data is free and
weekly; CME Bitcoin/Ether leveraged-fund positioning is a documented, mechanism-backed axis the
desk has never screened (distinct mechanism from the rejected basis-dislocation construct).

**U7. Whether anything still believes the dead non-crypto lake is alive.**
fx (12,069 files), equity (1,693), metal, index, energy partitions all end 2026-06-21
(`find data/lake/bronze/fx -type f -printf '%T+\n' | sort -r | head -1` → 2026-06-21). The
writers (`scripts/ingest_multiasset.py`, MT5 group taxonomy in `libs/data/instruments.py:30`)
are Windows/MT5-bound and cannot run on this host (`data/logs/tick.log` still shows
`C:\Users\dell\...` stack traces). Unknown: whether any doc/organ counts fx/equity as live
coverage. Nothing in `data_registry.json` marks them TERMINAL.

**U8. Binance Vision per-symbol metrics availability span.**
The metrics backfiller verified BTCUSDT zips parse (288 rows/day, positioning columns present —
ingest log "METRICS VERIFY"). Assumed but unverified: most USDⓈ-M symbols have metrics dumps
back to ~2021-12. Affects sizing of opportunity O4.

**U9. Lake growth trajectory beyond the moat.**
CME pull added 1.1GB in one day (`ls -la data/lake/bronze/cme/`). Lumpy acquisitions plus
~400MB/day moat vs 27G free: the 67-day runway (S9) is an estimate with high variance.
No capacity alarm exists anywhere (data_health checks freshness, never disk).

---

## 3. WHAT COULD MATTER MOST (ranked: impact × confidence / (cost × maintenance))

**O1. Offsite backup of the irreplaceable forward captures — the only preventable
catastrophic tail in the data system.** [COMPOUNDING MULTIPLIER + TAIL-KILL]
Evidence of absence: `libs/ops/backup.py` covers only the SOR sqlite ("Backup and restore for
the SQLite system of record", `_DB_NAME = "sor.sqlite"`); `crontab -l | grep -i backup` →
nothing scheduled — even the SOR backup never runs; `data/rollback/` is code-deploy snapshots.
Meanwhile the desk's own registry classifies pre-recorder L2 and 2021-25 liquidation cascades
as "destroyed at source" (`data/data_universe_map.json` residual_gaps) — and is accumulating
exactly that data class (moat 3.5GB since 07-17, liquidations.parquet since 07-09, Deribit
surface "per-strike IV has NO free history" per `collect_deribit_surface.py` docstring, kaiko
recon, nav attestations, forward clocks) on ONE disk, ZERO copies.
Exactly-what: nightly rclone sync of `data/moat/`, `data/liquidations.parquet`,
`data/deribit_surface.parquet`, `data/*.jsonl` forward series, and the SOR backup output to
S3-class cold storage (B2/R2, ~$0.006/GB/mo → <$1/mo now, ~$2.5/mo at 1y size). Complexity:
LOW (one rclone config + one cron line + restore drill). Failure modes: silent sync breakage →
monitor with a weekly restore-one-file drill and age alarm on the remote manifest; credentials
on-host → scoped write-only app key. Validation: restore a random file, sha256 vs source
(backup.py already has the manifest pattern to reuse). Maintenance: ~zero. Retirement: never
(standing rail). Interaction: none with trading path. ROI: essentially infinite in the loss
branch; the premium is <$30/yr. Confidence: 0.95. Horizon: protects everything from week 1
forever. This is not a data purchase — the free-first posture is untouched.

**O2. Intraday research lake from Binance Vision (free, includes delisted symbols).**
[BIGGEST SURFACE UNLOCK]
The lake is D1-only for 268 symbols + H8 for 10 (`timeframes: {'D1': 268, 'H8': 10}` — command
in S2). No H1/M5/M1 anywhere; no silver tier (`ls data/lake` → bronze only). The desk's own
registry lists binance_vision as "unused — free deep history, candidate for backfills"
(`data/data_registry.json` sources.binance_vision). Consequence: every intraday alpha family —
funding-cycle (8h) timing, liquidation-cascade reversion, hourly momentum/lead-lag, session
effects (the kimchi mechanism is a SESSION phenomenon) — is structurally untestable today. The
420-price-hypothesis/0-survivor result was a D1-space result; intraday is the orthogonal
continuation of the axis-not-breadth lesson, and it is $0.
Exactly-what: extend the existing Vision ingester pattern (ingest_axes already downloads/
verifies Vision zips) to 1h klines for the FULL perp universe INCLUDING delisted (Vision
retains them), 2020→present; 1m for a top-20 set; write as new lake timeframes (H1/M1) in the
S2 schema. Size estimate: 1h full universe ≈ low-GB compressed; bound M1 to top-20 to respect
disk (with O1/W9 in place). Complexity: MEDIUM (a day of work; the download/verify/partition
machinery exists). Validation: row-count + gap-scan vs expected bars per listing window;
schema equality check like S2's. Failure mode: disk growth → gate on O1 + capacity alarm.
Mechanism-first guard: this expands the TESTABLE surface; screens still require pre-registered
mechanisms (contrarian C1). Alternatives considered: aggTrades instead of klines (richer,
10-50x larger — defer; klines carry taker_buy volume which covers most first hypotheses).
ROI: highest of any single data action available to the desk. Confidence: 0.75. Horizon: 1m
usable pilots; 3m full family screens; 1y this is where the next kimchi-class hit most likely
lives (it cannot live in D1 — that space is mined out by the desk's own 420/0 evidence).

**O3. Survivorship repair + quantification of the D1 lake.** [VALIDITY DEBT]
Evidence: U1/S7 commands. Two moves: (a) measure — rerun one archived cross-sectional screen
on lake-universe vs lake+delisted (futclose_daily already holds the dead names' closes) and
publish the Sharpe/IC delta; (b) repair — backfill delisted symbols into the lake from Vision
(free; zips persist post-delisting), flag `delisted_date` in a universe table so backtests can
opt into point-in-time membership. Complexity: LOW-MEDIUM. Validation: LUNA/FTT present with
correct final rows; a known-date listing test. Failure mode: partial Vision coverage for old
delistings → log residual honestly. ROI: protects every future promotion decision; possibly
invalidates none (if delta is small — which is itself bankable knowledge that our short-horizon
results are robust). Confidence: 0.8 that it matters to measure; unknown which way. Horizon:
1w to measure, 1m to repair.

**O4. Un-cap the Binance metrics backfiller: BTCUSDT-hardcoded → full universe.**
[ONE-LINE-CLASS FIX, YEARS OF POSITIONING HISTORY]
Evidence: `scripts/ingest_axes.py:175` → `zips = sorted((BRONZE / "binance_metrics" /
"BTCUSDT").glob("*.zip"))` — the ingester is hardcoded to one symbol. Lake state confirms:
`ls data/lake/bronze/binance_metrics/` → `BTCUSDT` only (835 files, 10.1MB), while the forward
collector logs "312–1659 missing metric days" PER SYMBOL across 139 symbols
(`tail data/cro_ai_logs/dl_oils_daily.log`). The docstring's promise ("backfills years...
keeps it current forever") is true for 1/139 symbols. When BTC completes, the cron dead-ends
silently ("missing 0"). Exactly-what: generalize to the oi_ls_daily 139-symbol list,
breadth-first (newest 400 days × all symbols before deep history — cross-sectional factors
need breadth first), raise tranche 400→4,000+ (files are ~12KB; Vision is a public CDN; the
whole universe ≈ 236k files ≈ 2.9GB — at 400/day it takes 590 days, at 4,000/day 2 months).
Complexity: LOW. Validation: symbol-count in lake ratchets to 139; per-symbol VERIFY parse
like the existing one. ROI: universe-wide 5-min OI/long-short/taker history (2021→now) — the
raw material for cross-sectional positioning factors — for ~3GB disk and zero dollars.
Confidence: 0.9. Horizon: 1m to complete at raised tranche.

**O5. Tron leg for stablecoin flows — the accruing clock is watching half the flow.**
Evidence: `libs/data/onchain_flows.py` is ETH-only (eth_call balanceOf, 18 0x addresses; U3
command), while USDT-TRC20 is roughly half of USDT supply and the dominant Asia rail — the
same session whose premium axes (kimchi, CNY) are the desk's best screens. And
`stablecoin_supply_momentum` is 1 of only 3 accruing Stage-B clocks
(`data/axis_shadow_state.json`). Exactly-what: add trongrid (free) TRC20 balanceOf for the
top exchange wallets + Tron USDT total supply; publish combined and per-chain series; DECLARE
the timestamp alignment per screen duty. Complexity: LOW (same pattern, different RPC).
Validation: per-chain series vs known public dashboards on 3 spot dates; divergence of
combined vs ETH-only series measured — if negligible, the ETH-only proxy is validated
(either result is knowledge, logged). Failure mode: trongrid rate limits → key is free;
fallback tronscan API. Confidence: 0.7. Horizon: 1w build; improves a LIVE clock's fidelity
immediately. Note: mid-clock construction changes must be logged as a new construction trial
(garden-of-forking-paths rule) — run parallel series, don't silently swap the accruing one.

**O6. Registry-driven data_health — from 4 datasets to all of them.**
[COMPOUNDING MULTIPLIER — the class that would have caught both silent deaths]
Evidence: `scripts/data_health.py` `_DATASETS` covers exactly 2 parquet + 2 JSON archives + 2
heartbeats + liquidation special-case. It never watched cot_zcache (silently stale 5 weeks) or
the fx/equity lake (silently dead 5 weeks) — both discovered by THIS audit, not by monitoring
(`stat data/cot_zcache.parquet` → 2026-06-21; find on fx partitions → 2026-06-21). The desk was
already burned once by exactly this class (docstring: "the mode that froze the OI archive at
one snapshot"). Exactly-what: drive the check FROM the registry — every entry in
data_registry.json/universe map declares path, cadence, max-age, min-row-delta; data_health
iterates ALL of them; unknown-cadence entries get a default weekly-staleness rule; add ONE
disk-capacity check (W9/U9). New datasets inherit monitoring by registration, not by
remembering to edit `_DATASETS`. Complexity: LOW-MEDIUM. Validation: first run must flag
cot_zcache + fx lake (known-dead canaries) — if it doesn't, the generalization failed.
Maintenance: near-zero after. ROI: converts "audit finds corpses quarterly" into "alert fires
day 2". Confidence: 0.9. Horizon: permanent.

**O7. Shared Binance request budget across the 22 callers.** [SYSTEMIC-RISK REMOVAL]
Evidence: U2 commands (22 scripts, zero cross-process coordination, one IP; today's 418s).
Exactly-what: a small module (file-lock + token bucket keyed on Binance weight rules — the
recorder already computes weights correctly, generalize that) that every caller imports;
plus jittered retry-after-honoring on 418/429. Complexity: MEDIUM (touch many callers —
mechanical). Failure mode: a non-adopting script still burns the shared IP → lint/grep gate in
CI for raw binance URLs outside the module. Alternative (cheaper, also solves redundancy): the
second-VPS split from CEILING EXPANSION — recorders on one IP, research pulls on another.
ROI: removes a whole failure class that today cost three organs their 02:00 run (recovered by
catchup this time — S6 — but recovery is not immunity; a multi-hour ban during a funding window
would touch the live path). Confidence: 0.7. Horizon: 1m.

**O8. COT revival + CME BTC/ETH positioning screen.** [FREE WEEKLY INSTITUTIONAL AXIS]
Evidence: U6 (collector exists, cache to 2026-06-21, no scheduler on this host; CFTC free).
Mechanism prior: CME leveraged-funds/asset-manager net positioning in BTC futures — an
institutional-flow axis orthogonal to everything the desk has screened (basis-dislocation
REJECT was a different mechanism). Exactly-what: weekly cron for cot refresh (Fri release),
verify Linux-runnable, then axis_screen with pre-registered hypothesis + declared weekly→daily
alignment. Complexity: LOW. Confidence: 0.6 on screen value; 0.9 on data revival. Horizon: 2w.

**O9. Deribit surface densification: daily → hourly snapshots.** [OWNED-ASSET 24×]
Evidence: `collect_deribit_surface.py` docstring — "per-strike implied vol has NO free
history, so we snapshot... daily"; 66 rows/30d confirms 2 assets × 1/day. The desk's own
thesis (forward captures of unobtainable data compound) argues for hourly at near-zero cost —
same free API, 24× the owned history density, unlocks intraday vol-regime features later.
Add OI-by-strike to the snapshot (free book summaries) for future dealer-positioning proxies.
Complexity: TRIVIAL (cron cadence + one more field). Disk: negligible (8KB/month currently).
Confidence: 0.8. Horizon: value realizes in 6-12m — exactly why it must start now.

**O10. KR/JP frontier profiles (foreign-frontier at 1/8 doctrine regions).**
Evidence: `ls data/frontier_profiles/` → `CN.json` only, despite the axiom naming KR, JP, RU,
AR, PT, TR, ES and the desk's single best screen hit (kimchi) being a KOREAN-market mechanism
with Upbit already integrated (`collect_kimchi_premium.py` → api.upbit.com). KR first (Naver
finance/blogs, Upbit/Bithumb notices, Korean quant theses), JP second (bitFlyer residual gap
is already documented in the universe map). Complexity: LOW per profile (CN.json is the
template). Confidence: 0.65. Horizon: feeds diggers within a week.

**O11. Moat → silver extraction pipeline (first features from the 3.5GB).**
Evidence: `ls data/lake` → no silver tier; `data/moat/execution_tape/` holds only
cashcarry_trades.jsonl (127KB) — the depth captures have zero downstream consumers today
(9 days old, so early — but no pipeline EXISTS either; per the utilization law, build the
engine before the backlog grows). Exactly-what: hourly job compacting yesterday's moat files
into silver parquet: spread, top-5/top-20 imbalance, depth-at-bps, quote-life, trade-flow
aggressor ratios at 1s/1m bars for the ~32 recorded symbols. Feeds execution cost model
(live money path benefits immediately: `cost_model` step already prices pair-open at 2.854
bps from coarser inputs) and future microstructure screens. Complexity: MEDIUM. Confidence:
0.7. Horizon: 1m; compounding thereafter.

**O12. Fix the dead cross-asset legs (stooq symbols) or route around.**
Evidence: U5. Five of seven legs dead-on-arrival in a LIVE daily feed. Try corrected stooq
tickers; fallback: yahoo chart API (already used for KRW=X) or FRED for GOLD/WTI/DXY.
Complexity: TRIVIAL. Confidence: 0.8. Horizon: days.

**Explicitly NOT recommended:** buying any dataset (no residual gap is currently the proven
binding constraint — Discovery Bottleneck rule holds); reviving the MT5 fx/equity pipeline
(dead heritage, no crypto-desk mechanism demands it — mark TERMINAL in the registry instead,
per U7); raising moat depth to 100 levels today (U4 — wait for a card to demand it).

---

## 4. WHAT WE TEST NEXT (concrete experiments, success criteria, retirement conditions)

**T1. Backup + restore drill (O1).** Configure rclone → B2/R2 for the forward-capture set +
scheduled SOR backup; then restore 3 random files and diff sha256 vs source.
Success: clean restore, remote manifest age < 26h, cost < $1/mo confirmed on the bill.
Validation cadence: weekly automated restore-one-file check (alert on failure/staleness).
Retirement: never — this is a standing rail. Rollback: none needed (additive).

**T2. Survivorship delta measurement (O3a).** Take one archived cross-sectional D1 screen
(e.g., a rejected momentum variant from the 420 campaign), rerun on (a) current lake universe,
(b) universe ∪ futclose_daily delisted names.
Success criterion: the delta is MEASURED and logged either way; decision rule: |ΔSharpe| >
0.10 or |ΔIC| > 0.01 → flag all prior cross-sectional conclusions as survivorship-suspect in
the registry and prioritize O3b repair; below → log "short-horizon results robust to
survivorship at measured magnitude" as banked negative knowledge.
Retirement: after O3b lands and one full re-screen cycle uses point-in-time membership.

**T3. Vision 1h pilot + one pre-registered intraday screen (O2).** Backfill 1h klines,
2024→now, full perp universe (bounded pilot); pre-register ONE mechanism-backed hypothesis
(candidate: funding-cycle-anchored 8h seasonality in perp returns, mechanism = carry-trader
rebalancing pressure at funding timestamps; construction and alignment declared BEFORE
looking). Run axis_screen on the full window.
Success: Stage-A verdict either way within 14 days of start; the negative screen is a
first-class deliverable. Failure mode guarded: no breadth-mining — ONE construction, logged;
additional constructions each logged as trials.
Retirement of pilot: superseded by full 2020→now backfill if the surface proves live.

**T4. Metrics backfiller generalization (O4).** Code change + raised tranche; breadth-first.
Success: ≥50 symbols present in bronze/binance_metrics within 2 weeks, 139/139 within 6;
per-symbol VERIFY parse passes; forward cron keeps all current (
"missing 0" only when truly complete).
Retirement: when 139/139 complete AND daily increment confirmed for 2 weeks.

**T5. Tron divergence test (O5).** Build combined ETH+TRX reserve/supply series alongside
(not replacing) the accruing ETH-only clock.
Success: 30-day parallel run; report divergence stats. Decision: material divergence →
pre-register the combined construction as a NEW trial (never silently swap); negligible →
bank the ETH-proxy validation.

**T6. Registry-driven health canary test (O6).** Generalize data_health; first run MUST flag
cot_zcache and the fx lake as stale (the two known corpses are the acceptance test), plus a
disk-capacity line.
Success: both canaries fire; zero false-green. Retirement: never; the canary pair rotates as
corpses get buried (registry entries marked TERMINAL stop alerting).

**T7. 418 forensics + budget module (O7).** One week of per-script Binance call/weight
logging (read-only wrapper) to identify the spike source; then the shared budget module.
Success: zero 418s for 30 days post-deploy under unchanged workload; CI grep-gate prevents
raw-URL regressions. Alternative validated in parallel: price the $5 second-VPS split.

---

## SIX-PERSPECTIVE COVERAGE (explicit, per doctrine)

**INTERNAL (measured performance):** health monitoring covers ~4/30+ datasets (O6 evidence);
two silent 5-week corpses found by audit, not alerts (U6/U7); metrics backfiller scope-capped
to 1/139 symbols (O4); 418 class live today, recovered by catchup (S6/U2); moat/lake/recon
pipelines genuinely healthy (S1/S2/S4).

**EXTERNAL (how a world-class team would differ):** they would have (a) offsite replication of
irreplaceable captures as a day-1 invariant (O1), (b) intraday bars as the DEFAULT research
granularity with D1 as the aggregate, not the primary (O2), (c) point-in-time universe
membership everywhere (O3), (d) one rate-budget module per venue (O7), (e) label-refresh
pipelines with drift alarms for wallet entity resolution (U3). None require money; all are
practice gaps, not resource gaps.

**FUTURE (2-3y redesign pressure):** object storage + query-in-place (duckdb over remote
parquet — the client already exists, `libs/data/duckdb_client.py query_lake`) makes the
one-disk architecture obsolete; agentic per-region collectors make the frontier-profile
model (O10) the scaling unit; LLM-driven label curation makes hardcoded wallet lists (U3)
look like hardcoded stock tickers. Design moves that age well: registry-as-single-source
(O6), lake tiers (O11), backup-first (O1).

**CONTRARIAN (test our assumptions):** (C1) "More data = more alpha" is FALSE on this desk's
own evidence — 420 price-family hypotheses → 0 survivors; one new AXIS → the best screen ever.
O2/O4 are defensible only as AXIS expansions with mechanism-first screening intact — volume of
bars is not the point; the untested SPACE is. (C2) "The non-crypto lake dying was a loss" —
probably the opposite: focus. The correct act is formal TERMINAL marking (U7), not revival.
(C3) "Survivorship bias invalidates our results" — unproven; at 1-5 day horizons on liquid
perps it may be small. That is why T2 measures before O3b spends. (C4) "The moat compounds
value" — only if retained AND extracted; unbacked (O1) and unconsumed (O11) it is risk plus
disk cost. The contrarian view is what makes O1/O11 urgent rather than optional.

**GREENFIELD (rebuild-from-scratch delta):** a fresh build would have ONE registry declaring
every dataset (source, cadence, schema, health rule, backup class, owner organ, lineage), with
collectors, health checks, and backup manifests GENERATED from it; a bronze/silver/gold lake
with delisted-inclusive point-in-time universe tables; no MT5 heritage in `instruments.py`; no
split-brain between `data/` flat files (137 entries) and `data/lake/`. Historical-baggage
score: MODERATE — the split-brain and heritage code add friction but the crypto-side schema
discipline (S2) means migration is mechanical, not conceptual. Replaceability: high.

**FRONTIER (recently possible, unexploited):** Binance Vision metrics dumps (used at 1/139
scope — O4); Vision klines/aggTrades incl. delisted (unused — O2); trongrid free TRC20 reads
(O5); CFTC socrata API for COT (O8); Deribit free book summaries incl. OI-by-strike (O9);
Hyperliquid's public historical archives (funding already collected; trades/book archives
exist on their S3 — a candidate for the next dig, logged here as a lead, not a claim).

**NEGATIVE-SPACE SWEEP (never-asked / never-collected):** languages: KR/JP/RU/TR profiles
never built (O10) despite KR hosting the best hit; venues: no Upbit/Bithumb NOTICE stream
(listing/delisting announcements — the kimchi mechanism's event calendar), no bitFlyer/
Coincheck forward recorder despite the registry naming the 31-day wall (residual_gaps);
datasets: options OI-by-strike never snapshotted (O9), CEX announcement calendars never
archived cross-venue, ETF holdings FILES (issuer XLSX) never pulled (only farside HTML
scrape), 8h-native funding lake exists for only 10 symbols (H8 dir — S2 command), CME COT
never screened (O8); methods: weak-label event library (liquidation cascades from the moat +
liquidations.parquet) never constructed — a synthetic-dataset opportunity that turns forward
captures into a labeled training/eval corpus; failure modes never simulated: disk-loss drill
(O1/T1), registry-vs-disk drift audit (O6 covers the recurring version).

---

## OPPORTUNITY COST OF NOT FIXING, 1 YEAR (top items)

- **O1 (backup):** expected-cost framing is wrong for tails; the right frame: ~$30/yr premium
  vs total loss of every unrecoverable dataset the strategy is built to compound. One disk
  failure in year 1 at even 5% probability dominates every other number in this report.
- **O2 (intraday):** if the next validated axis lives intraday (the D1 space is self-evidenced
  as mined out: 420/0), every quarter of delay is a quarter of forward-clock evidence that
  never started — the exact failure mode objective #2 names. Cost: 1-2 validated-axis-years.
- **O3 (survivorship):** one false cross-sectional promotion traced to universe bias would
  cost real capital plus the doctrine's "negative discovery" penalty; one week of measurement
  removes the uncertainty.
- **O4 (metrics scope):** at tranche 400/day depth-first, universe positioning history
  completes in ~590 days — i.e., never, effectively. The fix converts that to ~60 days.
- **O6 (health):** the two corpses this audit found took 5 weeks to surface. At the desk's
  organ count, un-monitored freshness guarantees the NEXT silent death; each costs weeks of
  un-accrued evidence exactly where the desk claims its edge (forward clocks).

---

*Audit complete 2026-07-26. All commands run read-only from /home/quant/quant-platform.
No code, state, cron, or git was modified. Per §35, each O-item above is a candidate register
row for the synthesis organ; none are self-graded as converted.*
