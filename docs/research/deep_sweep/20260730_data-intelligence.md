# WEEKLY DEEP COLD AUDIT — SUBSYSTEM: data-intelligence
**Date:** 2026-07-30 · **Mode:** read-only · **Doctrine:** v2 (principal-ratified 2026-07-24) + Exhaustion Mandate (2026-07-28)

> STATUS: **COMPLETE.** 27 findings, all command-cited. Full scores and the six-perspective coverage map in
> APPENDIX A. Every claim below was verified against an artifact or a command's output, never a config file.

## HEADLINE — the five things that matter
1. **The entire data-discovery organ tier is dead** — 4 systemd units `failed`, 1 reporting `success` while
   every region fails; measured quota-death rate **100 %**, diagnosed 8 days ago, still 100 %. Acquisition
   capacity is **zero**. Direct L1.8 violation, unpaged. → **F16**
2. **BTCUSDT and ETHUSDT daily bars stop 2026-06-20** (39 d); 197 of 277 crypto symbols stale. **All 88
   cross-asset instruments** (FX/equity/metal/index/energy, up to 26 y of history) dead 41–55 days, via a
   feed that is *structurally unrunnable on this Linux host*. → **F2, F3, F7**
3. **The data-health monitor's alert class is 100 % false positive — 8 of 8.** Two proven root causes. A gate
   that is always wrong has trained the desk to ignore the channel a real outage would use. → **F1**
4. **Every bond/credit ETF in the lake is price-only.** `SHY` records **−0.87 %/yr** over 6.2 years. If it was
   ever the risk-free comparator, L1.5's T-bill hurdle was enforced *negative*. → **F8**
5. **Eight capabilities exist as tested code with zero production callers** — versioning, snapshots, run
   stamps, silver/gold, the gap detector, two funding feeds, the collector author. The bottleneck is wiring,
   not engineering. → **F11, F12, F19, F23, and the CEILING EXPANSION note**

## SCORES
| metric | value |
|---|---|
| current_capability_pct | **34 %** |
| practical_ceiling_estimate | **85 %** (and the estimate is itself too low — see CEILING EXPANSION) |
| ceiling_gap | **51 pts**, majority wiring/monitoring rather than new capability |
| opportunity_cost_1y | **VERY HIGH** — dominated by F16 |
| confidence | **HIGH** on findings, **MEDIUM** on rankings |
| unknown_unknown_score | **HIGH (7/10)** |
| info_gain_if_investigated | **VERY HIGH** |
| expected_alpha_contribution | **HIGH, mostly indirect** |
| expected_compounding_contribution | **VERY HIGH** |

Basis for each score, plus the ceiling-expansion analysis and the six-perspective coverage map: **APPENDIX A**.

---

## 1. WHAT WE KNOW (validated strengths, each with proving command)

### S1. The microstructure recorder is genuinely alive and, for Bybit, hour-perfect
```
$ for d in data/moat/*/; do find "$d" -type f -printf "%T@ %p\n" | sort -rn | head -1; done
data/moat/bybit/OPUSDT/20260730_02.jsonl.gz      newest=0.00d ago
data/moat/fut/NEARUSDT/20260730_02.jsonl.gz      newest=0.00d ago
data/moat/spot/TRXUSDT/20260730_02.jsonl.gz      newest=0.00d ago
```
Hourly completeness over interior (non-edge) days:
```
--- bybit --- symbols=20 dates=20260721..20260730 interior=8d expected 192 h/sym
  hourly completeness: min=100.0% median=100.0% max=100.0%
  symbols below 99% complete: 0/20 ;  hours with ANY symbol missing: 0/192
--- spot --- symbols=30 interior=8d ; median=100.0% ; 10/30 below 99%
```
This is real, self-manufactured, proprietary data (L1.11) — 6.0 GB, 16,536 hourly gz shards. **It is the
single strongest thing in this subsystem.** Note the caveats in F5/F6 before treating it as a research asset.

### S2. `data/lake/bronze` is a properly hive-partitioned, tz-explicit, deep-history store
```
$ find data/lake/bronze/fx/EURUSD -type f | sort | head -2
data/lake/bronze/fx/EURUSD/D1/year=2000/month=1/part-0.parquet
$ .venv/bin/python -c "import pandas as pd; d=pd.read_parquet('data/lake/bronze/fx/EURUSD/D1/year=2000/month=1/part-0.parquet'); print(list(d.columns)); print(d.head(1).to_string())"
['timestamp', 'open', 'high', 'low', 'close', 'volume']
0 2000-01-03 00:00:00+00:00  1.0080  1.0285  1.0049  1.0246  20088.0
```
Timestamps are `datetime64[ns, UTC]` — timezone-explicit, not naive. 26 years of daily FX. Partition layout
(`symbol/timeframe/year=/month=/part-0.parquet`) supports predicate pushdown and incremental append. The
*architecture* here is good; §2/F3 shows the *feed* is not.

### S3. History depth is real where it exists
```
$ # crypto bronze, first-observation year histogram over all 277 symbols
FIRST-YEAR histogram: {2011: 2, 2016: 1, 2017: 1, 2019: 3, 2020: 37, 2021: 27,
                       2022: 10, 2023: 40, 2024: 58, 2025: 98}
```
67 symbols reach back to 2021 or earlier (multi-cycle), and FX/metals/indices reach 2000/2008/2012. The desk
is **not** starved of calendar length on daily data. Its problem is freshness, breadth of timeframe, and
utilization — not raw history.

### S4. `data_vitals.py` refuses to silently drop unscoreable files — a real, deliberate anti-denominator-shrink control
`scripts/data_vitals.py:129-141` returns a reported row with `action="TOO_SMALL -- reported, not scored"`
rather than skipping, with the reasoning inline:
> "REPORTED, NOT DROPPED. A silently skipped file vanishes from the denominator and is then
> indistinguishable from a file that passed -- coverage read 56.8% while the desk could not say what
> became of the other 43%."

The same file's `:189-193` comment correctly kills a constant term from the DQS product:
> "DQS excludes cross_validation: it is a CONSTANT 0.5 (no source has a second feed), so multiplying it in
> capped every score at 0.5 against a 0.5 threshold and marked 14/14 collectors DEAD regardless of health.
> A constant carries no information."

That is the GATE-OPTIMALITY DUTY applied correctly and it was hard-won. **It is also the only part of this
monitor that works** — see F1.

---

## FINDINGS LEDGER (defects, gaps, bottlenecks — every claim command-cited)

### F1 — **THE DATA HEALTH MONITOR'S ALERT CLASS IS 100% FALSE POSITIVE (8 of 8). IT CARRIES ZERO INFORMATION.**
**Severity: CRITICAL. This is the finding that explains every other finding in this report.**

`data/data_vitals.json` reports `"n_dead": 8` with `"action": "DEAD -- FAILOVER"`. I checked all eight against
the actual last record in each file:

```
$ .venv/bin/python  # read last non-empty line of each DEAD file, compare to vitals verdict
source                                      rows   vitals_says   first_ts     ACTUAL_LAST_ts        mtime_age
coinmetrics_flows.jsonl                     9872   age=2856.4d   2010-07-18   2026-07-28              0d
kr_perasset_premium_history.jsonl           3008   age=9.4d      2018-05-04   2026-07-28              1d
stage_a_verdicts.jsonl                        38   dqs=0.105     2026-07-28   2026-07-29T02:35:14     0d
breadth_expansion.jsonl                      215   dqs=0.242     2026-07-27   2026-07-29              0d
cfe_crypto_settlements.jsonl                2005   dqs=0.250     2025-09-29   2026-07-27              1d
defi_lending.jsonl                         11755   dqs=0.250     2026-07-28   2026-07-30T02:17:01     0d
oi_ls_live.jsonl                             640   dqs=0.250     2026-07-28   2026-07-30T01:32:01     0d
cfe_regulated_basis_daily.jsonl              207   dqs=0.339     2025-09-29   2026-07-27              1d
```

`defi_lending.jsonl` is flagged **DEAD** while holding a record written **at 02:17 today, minutes before this
audit ran**. Not one of the eight is actually dead.

**Two independent root causes, both in `scripts/data_vitals.py`:**

**(a) Head-truncation on ascending-sorted files.** `scripts/data_vitals.py:38,102`
```python
MAX_ROWS = 3000
...
for i, ln in enumerate(fh):
    if i >= MAX_ROWS:
        break          # <-- reads only the FIRST 3000 rows
```
then `:170` computes `age = (now - max(ts))`. For a chronologically-ascending file longer than 3000 rows,
`max(ts)` is the *3000th row's* timestamp, not the newest. `coinmetrics_flows.jsonl` has 9,872 rows starting
2010-07-18 → `max(ts)` lands in the early history → **age 2,856 days (7.8 years) for a file updated
yesterday**, dqs 0.000. `kr_perasset_premium_history.jsonl` (3,008 rows) and `defi_lending.jsonl` (11,755 rows)
are hit by the same cut. The bug is invisible on any file under 3000 rows, which is why it survived.

**(b) Panel-shaped data is structurally unscoreable and always lands at dqs ≤ 0.25.** `scripts/data_vitals.py:166-177`
```python
if len(ts) >= 8:
    gaps = sorted((b - a).total_seconds() for a, b in itertools.pairwise(ts) if b >= a)
    cadence_s = gaps[len(gaps) // 2] if gaps else None
    if cadence_s and cadence_s > 0:        # <-- median gap of a panel is 0
        ...
        lat = ...
comp = 0.5
if cadence_s and len(ts) >= 20:            # <-- also skipped
    ...
```
Any file with **multiple rows per timestamp** — one row per asset per date, one per protocol per poll, one per
contract per settlement — has a *median* pairwise gap of exactly **0**. `cadence_s > 0` is then false, so
`lat` keeps its default `0.5` and `comp` keeps its default `0.5`. With perfect schema and alignment the best
achievable score is `0.5 × 0.5 × 1.0 × 1.0 = 0.25`, hard against a `DQS_DEAD = 0.5` threshold. Verified against
the artifact: `cfe_crypto_settlements`, `defi_lending`, `oi_ls_live` all show exactly
`latency: 0.5, completeness: 0.5, schema_integrity: 1.0, temporal_alignment: 1.0` → `dqs: 0.250`. **Every
panel-shaped source on this desk is permanently DEAD by construction, and panel-shaped is the natural shape
of cross-sectional data.**

**Why this is the report's keystone.** GATE-OPTIMALITY DUTY: "A gate that accepts ~0% or rejects ~100% of
candidates carries ZERO information and is a defect to investigate, not a virtue." This gate rejects 100% of
its alert population *falsely*. The consequence is not merely a wrong JSON field — it is that **the desk has
been trained that "DEAD -- FAILOVER" means nothing**, so when something genuinely died (F2, F3 — 39-to-55 day
outages on BTC, ETH and all of FX) there was no channel left that anyone would believe. An alarm that is
always wrong is worse than no alarm: it consumes the attention budget a real alarm needs.

Note the irony: `data_vitals.py:145-149` already documents *this exact class of bug* being fixed once before
("defi_lending scored 0.250 DEAD on its .jsonl while its heartbeat scored 1.000 OK: the same source, two
verdicts, one of them false"). The fix added a `< 3 distinct timestamps` grace path but did not address the
`median gap == 0` path, so `defi_lending` **is still scored 0.250 DEAD today**. The lesson was recorded and
the defect was not actually closed — ADJACENCY was never swept.

---

### F2 — **BTCUSDT AND ETHUSDT DAILY BARS DIED 39 DAYS AGO. 197 OF 277 CRYPTO SYMBOLS (71%) ARE STALE. NOTHING NOTICED.**
**Severity: CRITICAL.**

```
$ .venv/bin/python  # per-symbol max(timestamp) over all 277 data/lake/bronze/crypto/*/D1/**
crypto bronze symbols: 277 ; read ok: 277 ; failed: 0
LAG BUCKETS: {'<=2d': 60, '3-7d': 20, '8-14d': 20, '15-30d': 35, '31-60d': 142}
STALEST (sample):
  lag=  39 BTCUSDT   ...  lag=  39 ETHUSDT   ...   (both end 2026-06-20)
  lag=  39 SOLUSDT   2020-10-01..2026-06-20 parts=141
  lag=  39 XRPUSDT   2020-01-06..2026-06-20 parts=157
  lag=  39 LTCUSDT   2020-01-09..2026-06-20 parts=157
FRESH(<=7d) n=80 ; STALE(>7d) n=197
```

The two most important instruments the desk trades have **no daily bar since 2026-06-20**. So do SOL, XRP,
LTC, BNB, ADA, AVAX, DOGE, ETH, LINK — i.e. the liquid majors. Meanwhile 80 symbols *are* current, so the
updater runs; it just does not cover the majors. The fresh/stale split is not alphabetical and not
capitalization-ordered:
```
FRESH: AAVEUSDT ACEUSDT ACHUSDT AEROUSDT ALGOUSDT ... TRXUSDT UNIUSDT ... ZKCUSDT ZROUSDT
STALE: ... ADAUSDT AVAXUSDT BNBUSDT BTCUSDT ... DOGEUSDT ... ETHUSDT ... SOLUSDT XRPUSDT
```
Cross-referenced against the live recorder universe, the split cuts straight through it:
```
moat symbols STALE in bronze: ADAUSDT AGLDUSDT AVAXUSDT BICOUSDT BNBUSDT BTCUSDT CELRUSDT
                              COOKIEUSDT DOGEUSDT EGLDUSDT ETHUSDT LINKUSDT LTCUSDT MANAUSDT
                              SOLUSDT XRPUSDT           (16 of 30)
moat symbols FRESH in bronze: AAVEUSDT APTUSDT ARBUSDT BCHUSDT DOTUSDT FILUSDT NEARUSDT OPUSDT
                              PEOPLEUSDT SUIUSDT TRXUSDT UNIUSDT XLMUSDT   (13 of 30)
moat symbols ABSENT from bronze: EDUUSDT   (1 of 30)
```
**The desk is recording a live microstructure tape on 16 symbols whose own daily bar history stopped 39 days
ago.** Any study that joins the tape to daily context on those symbols either fails or silently truncates.

Consequences, in order of cost:
1. **Any backtest run today against the bronze lake silently ends 2026-06-20 for the majors.** There is no
   error — `pandas.read_parquet` over a hive glob just returns fewer rows. A researcher gets a clean-looking
   result computed on a 39-day-truncated sample and no warning fires.
2. The most recent 39 days — the *only* period with live forward-clock evidence accruing — is the period
   missing from the majors' history. Forward-vs-backtest reconciliation (L1.4) is impossible on BTC/ETH.
3. `data_vitals.json` and `collector_health.json` do not monitor the lake at all (F4), so this is invisible.

---

### F3 — **THE ENTIRE CROSS-ASSET / MACRO LAKE HAS BEEN DEAD FOR 41–55 DAYS. 88 INSTRUMENTS, UP TO 26 YEARS OF HISTORY, FROZEN.**
**Severity: CRITICAL — and it is the exact data class the desk's own doctrine says it most needs.**

```
$ .venv/bin/python  # content max(timestamp) per axis, sampled symbols
axis/symbol            first        last         lag_d   parts
fx/AUDCAD              2000-01-03   2026-06-08      52      27
fx/AUDCHF              2000-01-03   2026-06-05      55      26
fx/AUDHUF              2017-10-01   2026-06-05      55      32
equity/CIBR            2019-12-19   2026-06-18      42      22
equity/EEM             2018-10-01   2026-06-18      42      37
equity/EMB             2020-10-01   2026-06-18      42      36
metal/XAUUSD           2008-01-02   2026-06-19      41      37
metal/XAGUSD           2008-01-01   2026-06-19      41      38
metal/XPDUSD           2015-10-01   2026-06-19      41      37
index/UK100            2012-10-01   2026-06-19      41      38
index/US2000           2012-10-01   2026-06-19      41      38
index/US30             2012-10-01   2026-06-19      41      38
energy/XBRUSD          2014-10-01   2026-06-19      41      38
energy/XTIUSD          2010-10-01   2026-06-19      41      41
energy/XNGUSD          2009-11-11   2026-06-19      41      25
```
Corroborated by mtime — these files have not been *written* in 38 days, so the content cannot be fresher:
```
$ # newest/oldest file mtime per bronze axis
axis                     files    size  newest_age_d  oldest_age_d
fx                       12069    146M         38.55         39.90
equity                    1693     21M         38.13         38.13
metal                      708    8.6M         38.55         38.55
index                      668    8.1M         38.55         38.55
energy                     531    6.5M         38.55         39.90
cme                          8    1.1G          8.94          9.08
futclose_daily             139    9.7M          6.15          6.21
```
Scope: **57 FX pairs + 20 equity/credit ETFs + 4 metals + 4 equity indices + 3 energy = 88 instruments**, all
frozen. FX reaches back to 2000; metals to 2008; indices to 2012.

Why this is the most expensive of the three staleness findings, not the cheapest: L1.18 (ALPHA DIVERSITY) wants
"maximum INDEPENDENT compounding sources," and the SCREEN-ON-DISCOVERY doctrine's own governing evidence is
that "420 price-family hypotheses produced 0 survivors, while ONE new axis (kimchi premium) ... produced IC
+0.148." The desk's stated theory of where edge lives is **orthogonal, non-crypto-price axes**. FX carry, real
rates via TLT/IEF/SHY, gold, oil, EM credit via EMB, and the dollar are the orthogonal axes it already owns —
and every one of them has been dark for six weeks. The desk is simultaneously (i) declaring price-only space
picked clean, and (ii) not collecting the non-price data it already had a working pipeline for. That is not a
data gap, it is an **unnoticed regression on the highest-priority axis class**.

Note also the internal inconsistency: `fx` stopped at **2026-06-05/06-08** for some pairs but **2026-06-19**
for metals/indices/energy, and equity at **2026-06-18**. So this was not one clean outage — it decayed over
two weeks, per-axis, with nothing reporting.

---

### F4 — **THE TWO HEALTH MONITORS BETWEEN THEM COVER 4 AND 0 OF THE LAKE'S ~400 SERIES. THE MONITORED SET IS ~1% OF THE DATA ESTATE.**
**Severity: CRITICAL — this is the mechanism by which F2 and F3 stayed invisible.**

```
$ .venv/bin/python -c "import json;d=json.load(open('data/collector_health.json'));print(d['updated'], len(d['collectors']));print([c['clock'] for c in d['collectors']])"
2026-07-29T08:46:11.736051+00:00 4
['kimchi_premium.jsonl', 'stablecoin_supply.jsonl', 'cny_premium.jsonl', 'onchain_activity.jsonl']
```
`collector_health.json` watches **four** files. All four are small hand-built premium/on-chain axes. It does
not watch the moat, the lake, FX, equity, CME, or the 240 other files in `data/`.

```
$ .venv/bin/python  # data_vitals.json coverage by verdict class
updated 2026-07-29T08:46:46 n_dead 8 n_collectors 44
  scored OK        :  9
  scored DEAD      :  8   (all 8 false — see F1)
  unscoreable/None : 27   (TOO_SMALL 15, EVENT_LOG 6, DERIVED 3, STATIC 2, NEW 2)
```
`data_vitals.json` reaches 44 sources, of which **27 (61%) it declares unscoreable** and 8 it scores wrongly.
The number of sources it both scores and scores correctly is **9**. Of the 44, exactly one entry
(`"data/moat (order books)"`) touches the lake/moat at all, and that one is a directory-mtime check
(`scripts/data_vitals.py:217-218`, `"kind": "DIR_GLOB", "glob": "**/*.jsonl.gz"`) — see F5 for why that
particular green is also false.

Denominator check — what a complete monitor would have to cover:
```
$ ls data | wc -l                                    → 242 entries
$ ls data/lake/bronze/crypto | wc -l                 → 277 symbols
$ ls data/lake/bronze/fx | wc -l                     →  57 pairs
$ ls data/lake/bronze/{equity,metal,index,energy} | wc -l → 31 instruments
$ ls data/moat/{fut,spot,bybit} | wc -l              →  80 symbol-venue pairs
```
Monitored: ~13 series (4 in collector_health + 9 correctly-scored in vitals). Population: **~400+ series.**
Coverage ≈ **3%**. And the 97% unmonitored share is where both real outages happened.

The two monitors also **disagree about the same file with no reconciliation**: `kimchi_premium.jsonl` is
`status: OK, age_h: 6.2` in `collector_health.json` and `action: "TOO_SMALL -- reported, not scored"` in
`data_vitals.json`. Two health systems, one file, two verdicts, no arbiter, no test that they agree.

---

### F5 — **THE PROPRIETARY MOAT IS 6.0 GB OF *TEN DAYS*. IT IS SCORED `dqs 1.000 OK`. `fut` IS 40% MISSING AND WILL NEVER BE BACKFILLED.**
**Severity: HIGH.**

```
$ # distinct dates and file counts per moat venue
--- bybit --- symbols: 20 ; distinct dates: 10 ; first=20260721 last=20260730 ; files 4200
--- fut   --- symbols: 30 ; distinct dates: 14 ; first=20260717 last=20260730 ; files 6370
--- spot  --- symbols: 30 ; distinct dates: 10 ; first=20260721 last=20260730 ; files 5966
```
The desk's flagship proprietary asset — 6.0 GB, 80% of all bytes on disk — holds **10 to 14 calendar days**.
Meanwhile:
```
$ .venv/bin/python -c "import json;d=json.load(open('data/data_vitals.json'));print([c for c in d['collectors'] if 'moat' in c['source']])"
{'source': 'data/moat (order books)', 'dqs': 1.0, 'age_s': 0.0, 'action': 'OK', ...}
```
`dqs 1.000 OK` — because the check is `newest = max(f.stat().st_mtime for f in p.glob("**/*.jsonl.gz"))`
(`scripts/data_vitals.py:266`). **It measures only that *one* file somewhere under `data/moat` is recent.** It
cannot see a missing symbol, a missing hour, a truncated shard, or a 10-day horizon. This is the archetypal
self-greening guard the doctrine names as prime quarry: a green light wired to a condition that a single
living file satisfies.

What the green light is hiding, on `fut`:
```
--- fut --- interior dates=12 ; expected hours/sym=288
  hourly completeness: min=60.4% (AAVEUSDT) median=72.2% max=98.3%
  symbols below 99% complete: 30/30
     AAVEUSDT 60.4% (174/288)   AGLDUSDT 60.4%   BICOUSDT 60.4%   CELRUSDT 60.4%
     COOKIEUSDT 60.4%   EDUUSDT 60.4%   EGLDUSDT 60.4%   MANAUSDT 60.4%
     PEOPLEUSDT 60.4%   XLMUSDT 60.4%   ADAUSDT 72.2%   APTUSDT 72.2%
  hours with ANY symbol missing: 114/288
     20260718_00 .. 20260718_14 (and on): 25 of 30 symbols missing
```
**Every one of 30 symbols is below 99%; the median symbol is missing 28% of its hours.** The missing-hours
pattern is not random dropout — it is contiguous blocks at the start (`20260718_*`: 25 symbols missing), i.e.
**the recorded universe was expanded in steps (20 → 30 symbols) and the earlier days were never backfilled.**
Two distinct problems follow:

1. **No backfill, and it is now unrecoverable.** Order-book depth snapshots are not retrievable after the
   fact from any free venue endpoint. Unlike a daily bar, a missed depth hour is gone permanently. Every hour
   not captured is a permanent hole in the one asset the constitution calls the moat.
2. **Universe-expansion selection bias, which is a live look-ahead risk in cross-sectional work.** The panel
   silently changes width mid-sample. If the added symbols were chosen for *recent* liquidity or *recent*
   interest — which is the normal reason to add a symbol — then a cross-sectional study over this tape
   conditions on information from the future of its own early sample. This is the mirror image of
   survivorship bias and it is not documented anywhere in the moat's metadata (there is no metadata: see F7).
   A study that ran on `fut` today would get 30 symbols for recent days and 20 for early days and **nothing
   would say so.**

---

### F6 — **THERE IS NO INTRADAY HISTORY BETWEEN "10 DAYS" AND "DAILY". THE MIDDLE OF THE FREQUENCY SPECTRUM IS EMPTY.**
**Severity: HIGH — this is a capability gap, not a bug.**

```
$ .venv/bin/python  # timeframe directories across ALL 277 crypto bronze symbols
ALL 277 symbols TIMEFRAME dirs: {'D1': 277, 'H8': 10}
```
277 symbols have **D1 only**. Ten have H8. Nothing else — no 1m, 5m, 15m, 1h, 4h at any depth.

The desk's frequency coverage is therefore:
| horizon | coverage |
|---|---|
| tick / depth / trades | 10–14 days (moat, 30 symbols) |
| 1m – 4h | **nothing, at any length, for any symbol** |
| 8h | 10 symbols |
| 1d | 277 symbols, up to 15 years |

The consequence is concrete and it constrains the *validation* system, not just research: hourly and 4-hourly
signals — the band where most crypto microstructure and funding-cycle effects live, and the band the desk's
own funding/basis/OI work implies — **cannot be backtested at all.** A signal discovered on the 10-day tape
has 10 days of history; the moment it needs a regime other than late-July-2026 it is unbackable. This is why
the moat (F5) cannot yet function as a research asset even though it is genuinely good data: **10 days spans
one regime, and a Sharpe estimated on one regime is not evidence.**

Note what makes this cheap to fix and therefore expensive to leave: Binance, Bybit and OKX all serve free
historical klines at 1m/5m/1h with multi-year depth, and the repo already contains a working hive-partitioned
parquet writer for exactly this shape (S2). The gap is not access and not architecture. See O2.

### F7 — **ALL 88 CROSS-ASSET INSTRUMENTS COME FROM ONE MT5 DEMO TERMINAL, WHICH IS *STRUCTURALLY UNRUNNABLE ON THIS HOST*. F3 IS NOT AN OUTAGE — THE FEED IS ARCHITECTURALLY DEAD.**
**Severity: CRITICAL. This is the root cause of F3 and it will not self-heal.**

```
$ head -12 scripts/ingest_multiasset.py
"""Targeted multi-asset D1 ingest for the cross-asset edge search (warm-terminal fast path).
Pulls a CURATED liquid cross-asset universe (FX majors/crosses, metals, energy, equity indices,
crypto CFDs) via ``copy_rates_range`` ...
This is the honest MT5 data-breadth lever: land every asset class the demo broker actually has..."""

$ sed -n '48,62p' scripts/ingest_history.py
def _connect(expected_server: str = ""):
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")
    acct = mt5.account_info()
    if acct is None or int(acct.trade_mode) != 0:
        mt5.shutdown()
        raise SystemExit("refusing to run: not connected to a DEMO account")

$ .venv/bin/python -c "import MetaTrader5"
ModuleNotFoundError: No module named 'MetaTrader5'
$ uname -sr
Linux 7.0.0-15-generic
```
`MetaTrader5` is a **Windows-only** package requiring a *running MT5 terminal process*. It is not installed,
it is not in `pyproject.toml`, and it cannot be installed on this Linux host. So the sole ingest path for
FX (57), equity (20), metal (4), index (4) and energy (3) — **88 instruments, up to 26 years of history —
cannot execute at all on the machine that runs the desk.**

Three compounding problems, in order of severity:

1. **Not repairable by restarting anything.** Every other staleness on this desk is a stopped job. This one
   is a platform incompatibility. Waiting, retrying, or adding a cron entry cannot fix it. It has to be
   *replaced*, and no replacement is written (F9 shows the intended replacement produces nothing).
2. **Vendor concentration is 100% on a single DEMO CFD broker.** Not one of the 88 instruments has a second
   route. Beyond the availability risk, **demo-broker CFD quotes are broker-specific synthetic prices** —
   marked up, indicative, and not the exchange print. Using them for gold, oil, index and ETF research means
   the price series contain a broker's spread policy as a component. Nothing in the metadata records this.
3. **`trade_mode != 0` → hard exit.** The DEMO assertion at `ingest_history.py:55-57` is correct as a safety
   rail but it also means the *only* sanctioned route requires a demo account to stay alive indefinitely.
   There is no lifting condition recorded and no free-primary fallback (L1.11 / FREE-FIRST).

The `PROACTIVE BATTERY` CONTINGENCY-BEFORE-FAILURE move applies exactly here and was never run: this
dependency's replacement was never named before the outage, and six weeks later it still has not been.

---

### F8 — **EVERY BOND AND CREDIT ETF IN THE LAKE IS PRICE-ONLY. THE COUPON — WHICH *IS* THE RETURN — IS MISSING. THIS DATASET IS ACTIVELY MISLEADING, NOT MERELY INCOMPLETE.**
**Severity: CRITICAL (CONTRARIAN perspective — a dataset that harms conclusions).**

Decisive test, needing no external reference. `SHY` is the iShares 1–3 Year Treasury ETF: duration ≈ 1.9y,
so its *price* is near-flat by construction and essentially all of its total return is distribution income.

```
$ .venv/bin/python  # cumulative CLOSE-to-CLOSE return per equity-lake symbol
SHY   2020-03-25..2026-06-18 n= 1567 yrs= 6.23 cum_price_ret= -5.30% cagr=-0.87%
IEF   2020-03-25..2026-06-18 n= 1567 yrs= 6.23 cum_price_ret=-21.23% cagr=-3.76%
TLT   2018-05-07..2026-06-18 n= 2041 yrs= 8.11 cum_price_ret=-27.02% cagr=-3.81%
LQD   2018-05-07..2026-06-18 n= 2041 yrs= 8.11 cum_price_ret= -4.78% cagr=-0.60%
EMB   2020-03-26..2026-06-18 n= 1566 yrs= 6.23 cum_price_ret= -3.02% cagr=-0.49%
XLU   2018-05-07..2026-06-18 n= 2041 yrs= 8.11 cum_price_ret=+74.43% cagr=+7.10%
```
`SHY` at **−0.87 %/yr** over a window in which short rates ran 0 % → ~5 % → back is arithmetically impossible
for a total-return series; a 1–3y Treasury fund earned solidly positive total return across it. The series is
**unadjusted price**. Same conclusion for `IEF`, `TLT`, `LQD` (−0.60 %/yr while yielding 4–5 %) and `EMB`
(−0.49 %/yr while yielding 5–6 %).

Confirmed structurally — the schema has no adjustment channel and the codebase has no corporate-action concept:
```
$ grep -n "BAR_COLUMNS" libs/data/schema.py
16:BAR_COLUMNS: tuple[str, ...] = (TIMESTAMP, *OHLC, VOLUME)

$ grep -rniE "adj_close|adjusted|dividend|split|total_return|corporate_action" --include=*.py libs scripts
  → every hit is a false positive on str.splitlines()/rsplit; ZERO real matches
```
So there is no `adj_close`, no dividend table, no split table, no total-return reconstruction — and therefore
**this cannot be corrected from anything on disk.** The information was never captured.

Why this is worse than a staleness bug: the desk *already ran cross-asset research on this data*.
`scripts/run_crossasset_shadow.py:48`, `scripts/run_crossasset_robust.py:34`, `scripts/run_mt5_portfolio.py:45`
all carry `_COST = {"fx": 1.0e-4, "metal": 2.0e-4, "energy": 2.5e-4, ...}` keyed to these asset classes, and
`data/crossasset_shadow_state.json` exists (38.5 d old). Any rates / duration / credit-spread /
flight-to-quality / risk-parity conclusion drawn from `SHY IEF TLT LQD EMB` was computed on a series
understating true return by roughly **3–6 % per year**, and understating it *systematically in one direction*.
A long-duration signal was scored against a benchmark missing its coupon. **This does not produce a noisy
answer; it produces a confidently wrong one, biased the same way every time.** It is precisely the CONTRARIAN
failure mode the doctrine names: "a dataset adding noise, a validation practice misleading."

L1.5 (EXECUTION PHYSICS) requires alpha to "beat T-bills net of costs." The desk's own T-bill proxy, `SHY`,
is recorded at **−0.87 %/yr**. If that series was ever used as the risk-free comparator, the bar it enforced
was **negative** — every strategy clears a hurdle that should have been ~+4 %.

---

### F9 — **THE FREE REPLACEMENT FOR MT5 IS ALREADY WRITTEN, HAS PRODUCED ZERO BYTES, AND REPORTS ITS OWN FAILURE TO STDOUT ONLY.**
**Severity: HIGH — and it makes F3/F7 much cheaper to fix than they look.**

`scripts/ingest_axes.py:230-246` fetches five cross-asset series from Stooq — free, HTTP, no terminal, works
on Linux:
```python
for sym, label in (("^spx", "SPX"), ("^ndq", "NASDAQ"), ("xauusd", "GOLD"),
                   ("cl.f", "WTI"), ("dx.f", "DXY_fut")):
    try:
        raw = fetch(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=45)
        if len(raw) > 1000 and b"Date" in raw[:100]:
            (out / f"stooq_{label}.csv").write_bytes(raw)
            print(f"  crossasset/{label}: {raw.count(chr(10).encode()):,} rows")
        else:
            print(f"  crossasset/{label}: stooq returned no data (symbol?)")   # <-- swallowed
```
Outcome, not config:
```
$ find data -name "stooq*" | wc -l
0
$ ls -la data/lake/bronze/crossasset/
-rw-rw-r-- 470881 Jul 29 06:44 VIX_history.csv        <-- CBOE path works
-rw-rw-r--  16978 Jul 29 06:44 ust_curve_2018.csv     <-- Treasury path works
... ust_curve_2019..2026.csv                          <-- 9 files, all fresh
                                                      <-- ZERO stooq_*.csv, ever
```
The ingest ran yesterday (06:44) and the two sibling sources in the same function landed fine. **All five
Stooq symbols returned nothing, on every run, and the only record is a `print()` into a log nobody keeps.**
The `else` branch is not a failure — the function returns normally and the caller sees success.

I ran the SCOPE-THE-NEGATIVE-RESULT probe (battery move #9) to separate *route failed* from *capability absent*:
```
$ for s in "^spx" "%5Espx" "xauusd" "cl.f" "dx.f" "spy.us" "tlt.us" "shy.us"; do
    curl -s -o /tmp/stq.csv -w "%{http_code}" --max-time 25 "https://stooq.com/q/d/l/?s=$s&i=d"; done
s=^spx    http=200 bytes=796 head='<!DOCTYPE html><html><head><meta charset="utf-8"...'
s=xauusd  http=200 bytes=796 head='<!DOCTYPE html><html><head><meta charset="utf-8"...'
s=tlt.us  http=200 bytes=796 head='<!DOCTYPE html><html><head><meta charset="utf-8"...'
   (identical 796-byte HTML for all 8 symbols)
```
**Diagnosis: HTTP 200 with a fixed 796-byte HTML body for every symbol — this is an interstitial/consent or
bot-gate page, not a per-symbol failure.** The route is blocked at the host level, *not* the symbols. The
guard `len(raw) > 1000 and b"Date" in raw[:100]` correctly rejects it but reports nothing durable, so a
**host-level block has been silently absorbed as "symbol?" for an unknown length of time.**

That is the whole finding's value: the desk concluded nothing because the code asked no question. Per battery
move #9, the correct scope of the negative result is *"this one HTTP route is gated"* — **not** "free
cross-asset data is unavailable." Free, Linux-native, dividend-adjusted alternatives were never tried:
```
$ for v in stooq yfinance pandas_datareader alphavantage tiingo eodhd twelvedata fredapi nasdaqdatalink; do
    grep -rli "$v" --include=*.py scripts libs | wc -l; done
stooq: 1 (blocked)   yfinance: 0   pandas_datareader: 0   alphavantage: 0
tiingo: 0   eodhd: 0   twelvedata: 0   fredapi: 0   nasdaqdatalink: 0
```
**Not one free cross-asset vendor other than the blocked Stooq route has ever been wired.** Meanwhile the
desk already proves it can pull free primary sources properly — CBOE's own CSV and the US Treasury's own CSV
both work in the same function. The capability is demonstrated; only this route is gated. And note the
FREE-FIRST DATA PROTOCOL standard: *"'No free source exists' requires EVIDENCE — a documented failed search
with its graded residual gap, never a default."* No such evidence exists for cross-asset, because the
failure was never recorded anywhere but stdout.

---

### F10 — **NOT ONE OF 44 SOURCES HAS A SECOND INDEPENDENT FEED. CROSS-VALIDATION COVERAGE IS EXACTLY ZERO.**
**Severity: HIGH.**
```
$ .venv/bin/python -c "import json,collections; d=json.load(open('data/data_vitals.json'));
  print(collections.Counter(c['components']['cross_validation_available'] for c in d['collectors']))"
Counter({False: 44})
```
`scripts/data_vitals.py:189-193` documents the consequence honestly ("ABSENCE IS NOT HEALTH: no second source
== 0.5, never 1.0") and then has to *remove the term from the score* because a constant carries no
information. That fix was right — but it converted a measured zero into an **unmeasured** zero. The
underlying capability gap is untouched: every price, premium, funding, on-chain and macro series on this desk
is single-sourced, so **no value on disk has ever been checked against an independent observation of the same
fact.**

This is not abstract. The desk's own record shows what single-sourcing costs: the retracted kimchi-premium
edge and the Coinbase- and Turkey-premium artifacts were all *cross-source composites* whose failure mode was
alignment, and the desk found them only by luck of a de-contamination gate, not by a second feed disagreeing.
One counter-example exists and shows the right shape — `data/batch_coinmetrics_screen.json` carries a computed
`verification` block (`median_abs_err_vs_binance_close_bps: 13.18` over `n_days: 3268`, plus an internal
supply reconciliation at corr 0.9989). **That is exactly the mechanism that should exist for every source and
exists for one, ad hoc, with no schema and no aggregation.**

Cheapest available cross-checks that are currently unexploited: Binance vs Bybit vs OKX klines for the same
symbol-day (all free, all already reachable — the moat already records two of the three venues); CoinMetrics
vs exchange close (proven to work); Treasury CSV vs FRED for the same yield curve point (both already ingested).

---

### F11 — **THE CONSTITUTIONALLY MANDATED "DATA GENOME" DOES NOT EXIST. THE REPRODUCIBILITY LAYER IS FULLY BUILT AND HAS ZERO ROWS. AND THE LAKE OVERWRITES HISTORY IN PLACE.**
**Severity: CRITICAL — this is the largest *compounding* loss in the subsystem.**

L1.11 mandates "a data genome tracking lineage and half-life." It exists only as prose:
```
$ find . -path ./.venv -prune -o \( -iname '*genome*' -o -iname '*lineage*' -o -iname '*provenance*' \) -print | wc -l
0
$ grep -rn "data genome\|data_genome" -i . | grep -v '\.venv/\|\.git/'
docs/CONSTITUTION.md:75      (the mandate)
ops/principal_doctrine.txt:30 (the same sentence)
```
The reproducibility machinery is *written, complete, and never called from production*:
```
$ .venv/bin/python  # row counts over all data/*.sqlite
data/alpha_registry.sqlite         snapshots=0 config_versions=0 trials_ledger=0 research_runs=0 alpha_cards=8 research_memory=0
data/sor_research.sqlite           snapshots=0 config_versions=0 trials_ledger=0 research_runs=0 research_memory=144
data/sor_crypto.sqlite             snapshots=0 config_versions=0 trials_ledger=0 research_runs=0
   ... 8 DBs, snapshots=0 / trials_ledger=0 / research_runs=0 / config_versions=0 in EVERY ONE
```
`libs/core/reproducibility.py` (`ReproducibilityStamp`, binds git commit + UTC ts + seed + config hash +
snapshot id) and `libs/store/snapshots.py` (`register_dataset_snapshot`, content-hashed parquet versions) have
**no callers outside `tests/`**. `TrialsLedger` has a `data_snapshot` column and 0 rows.

And the destructive part:
```
$ grep -n "existing_data_behavior" libs/data/lake.py
59:            existing_data_behavior="delete_matching",
```
Re-writing a month partition **deletes the previous contents in place**. `libs/data/lake.py:5` claims
"dataset-level immutability is enforced via the store's snapshot catalog" — that catalog has **0 rows**, so
nothing is enforced. Across 26,315 parquet files there is not one content hash:
```
$ grep -rl 'git_commit\|snapshot_id\|data_hash\|dataset_version\|content_hash' data/ reports/ web/
  → hits only inside data/rollback/*/libs/... i.e. copies of source code, not artifacts
$ find data/rollback -name '*.jsonl' -o -name '*.parquet' -o -name '*.sqlite'
  → empty   (rollback tracks CODE only: scripts/, libs/, tests/ — rollback_guard.py:41-43)
```

**Compounded consequence, stated plainly: no backtest this desk has ever run can be reproduced, and there is
no way to detect that it became irreproducible.** Combine with F2/F3 and it gets worse — a result computed
against BTCUSDT before 2026-06-20 and a result computed today read *different data through the same code path*,
with no version, no hash, and no warning. L1.4 (REALITY ANCHORING) requires that "every predicted-vs-realised
divergence triggers investigation." That investigation is currently impossible: you cannot ask what data the
prediction was made from.

This is the highest-leverage *compounding multiplier* in the subsystem because it multiplies the value of
every future experiment, and its absence silently devalues every past one.

---

### F12 — **THE "FAIL-CLOSED" DATA GATE HAS ZERO RESEARCH CALLERS. 12 OF 37 DATASETS ARE GRADED FAILED AND ARE FREELY READABLE ANYWAY.**
**Severity: HIGH — an inert lever, the doctrine's named quarry.**

`scripts/measurement_gate.py:26` asserts:
> "FAIL-CLOSED BY IMPORT. The gate is not advisory. Research code calls require_verified(name) and an
> UNVERIFIED dataset raises."

```
$ grep -rn "require_verified" --include=*.py . | grep -v '\.venv/'
scripts/verify_fixes.py:43,45,49,55      <-- a self-test OF the gate
scripts/module_justification.py:123      <-- a string literal in a wiring audit
scripts/measurement_gate.py:26,331,388   <-- the definition and its own docstrings
```
**Not one research, screen, backtest or factory script imports it.** The enforcement described in the
docstring does not exist. Current verdicts:
```
$ .venv/bin/python -c "...json.load(open('data/measurement_gate.json'))['datasets']..."
Counter({'TOO_SMALL': 16, 'FAILED': 12, 'VERIFIED': 9})
```
Twelve FAILED datasets, each with a specific and serious reason, all readable by any script with no error:
```
8btc_era_thread_catalog.jsonl     no timestamp field; NO PRODUCER -- cannot be regenerated
kr_perasset_premium_history.jsonl NO PRODUCER -- cannot be regenerated (3008 rows, feeds premium work)
cfe_crypto_settlements.jsonl      NO PRODUCER -- cannot be regenerated
cfe_regulated_basis_daily.jsonl   IRREGULAR SPACING: 22% of gaps deviate >75% from median 24.00h
venue_divergence_shadow.jsonl     SCHEMA UNSTABLE: only 79% share the modal key set
information_value.jsonl           field 'survived' FROZEN for 810/810 records -- dead while still writing
breadth_expansion.jsonl           field 'reachable' FROZEN for 38 consecutive of 208 -- dead while writing
kaiko_vwm_reference_rate.jsonl    no timestamp field; 'partition_s' FROZEN 132/132
stage_a_verdicts.jsonl            'n_eff','horizon_days','min_detectable_ic' each 31.6% null
defi_lending.jsonl                'debt_ceiling_usd' 34.3% null
blind_spot_ledger.jsonl           'baseline' 43.9% null and FROZEN 18 consecutive
micro_audit_log.jsonl             'response' 25.0% null
```
Note `information_value.jsonl`: `survived` frozen for **810 of 810** records. The gate's own diagnosis —
"collector likely dead while still writing" — is the exact self-greening pattern the doctrine hunts, and it
has been detected, written down, and not acted on. Note also `stage_a_verdicts.jsonl`: 31.6 % of the
SCREEN-ON-DISCOVERY verdict ledger is missing `n_eff` and `min_detectable_ic`, i.e. **a third of Stage-A
screens cannot state their own statistical power.**

Three datasets carry **NO PRODUCER** — nothing in `scripts/` can regenerate them. `kr_perasset_premium_history.jsonl`
(3,008 rows, 2018→2026, feeding the premium family) is an orphan: if it is lost or corrupted it is gone, and
no result derived from it is reproducible. That is F11 in miniature, already realized.

---

### F13 — **THE TWO REGISTRIES THAT DEFINE WHAT DATA EXISTS ARE HAND-WRITTEN PROSE WITH NO WRITER, ONE IS 21 DAYS PAST ITS OWN REVIEW DATE, AND THEIR QUALITY GRADES ARE FREE TEXT WITH ~30 DISTINCT VALUES.**
**Severity: MEDIUM-HIGH (it is the metadata layer everything else reasons from).**
```
$ grep -rn "data_universe_map\|data_registry" --include=*.py . | grep -v '\.venv/' \
    | grep -iE "write|dump|open\(.*w|save"
  → (no output)                       # every reference is a READ
$ stat -c '%y %s' data/data_registry.json
2026-07-08 23:07  3798 bytes         # 21 days stale
$ .venv/bin/python -c "import json;d=json.load(open('data/data_registry.json'));
   print(d['last_verified'], d['next_quarterly_review'], len(d['sources']))"
2026-07-09  2026-10-09  20
```
`data_registry.json` holds 20 sources with exactly four fields each (`tier, used_by, info, status`), `status`
being free text. It has no hash, version, schema or snapshot field, and **no code exists that could perform
the quarterly re-verification it schedules.** It describes 20 sources against a real estate of ~400 series
(F4) — a 5 % census.

`data/data_universe_map.json` (84 KB, 60 sources) grades every source with an unnormalized string:
```
$ grep -o '"grade"[^,]*' data/data_universe_map.json | sort | uniq -c | sort -rn
 18 needs-monitoring        17 catalogued        15 adopted-pending-verify
  5 UNVERIFIED               5 REDUNDANT-with-existing-collector
  3 verified-clean           2 principal-signup-gated
  1 verified-clean-mechanism (re-graded 2026-07-25; licence/ToS ... still unread...)
  1 needs-legitimacy-review (mechanism verified-clean; licence unread because ... WAF/geo-blocked...)
  ... ~14 further one-off prose variants, some with embedded newlines and dangling parens
```
Its `updated` field is itself narrative: `"2026-07-28T00:00:00+00:00 (EN frontier miner session D:
cboe_cfe_crypto_settlements added)"`. **These grades cannot be counted, filtered, ranked or trended — so no
automated process can act on data quality, and the DATA-TO-ALPHA CONVERSION RATIO cannot be computed per
source.** 17 sources sit at `catalogued`, which is precisely the state SCREEN-ON-DISCOVERY was written to
abolish ("DISCOVERING A DATASET IS HALF A DELIVERABLE"), and because the grade is prose no gate can detect them.

Provenance coverage in the one computed registry is also thin:
```
25 of 44 collectors report collection: "UNKNOWN";  39 of 44 have regenerable: null;
39 of 44 have timestamp_verified: null            (data/data_vitals.json, PROVENANCE dict = 5 entries)
```

---

### F14 — **TIMESTAMPS: PARQUET IS CLEAN; ROUGHLY HALF THE JSONL ESTATE IS TIMEZONE-IMPLICIT, AND BOTH VALIDATORS SILENTLY COERCE NAIVE → UTC, SO A VENUE SWITCHING TO LOCAL TIME WOULD PASS EVERY CHECK.**
**Severity: HIGH — this is the failure shape that already killed two "edges" on this desk.**

Parquet is genuinely correct and enforced (`libs/data/schema.py:34-37,50-51`; `libs/core/time.py:47-51`
rejects naive datetimes by design):
```
$ .venv/bin/python -c "import pyarrow.parquet as pq; print(pq.read_schema('data/lake/bronze/fx/EURUSD/D1/year=2000/month=1/part-0.parquet'))"
timestamp: timestamp[ns, tz=UTC]      <-- explicit
```
JSONL is not:
| tz-EXPLICIT (`+00:00`) | tz-IMPLICIT (bare date / epoch) |
|---|---|
| `defi_lending.jsonl` `ts` | `kimchi_premium.jsonl` `date` = `"2026-07-22"` — **LIVE clock** |
| `oi_ls_live.jsonl` `ts` | `cny_premium.jsonl` `date` = `"2026-07-23"` — **LIVE clock** |
| `venue_divergence_shadow.jsonl` `ts` | `stablecoin_supply.jsonl` `date` — **LIVE clock** |
| `information_value.jsonl` `ts` | `coinmetrics_flows.jsonl` `date`, `kr_perasset_premium_history.jsonl` `date` |
| `micro_audit_log.jsonl` `ts` | `moat/**/*.jsonl.gz` `t` = `1785297546174` (epoch ms, no zone) |

And the identical defect in both validators:
```
scripts/measurement_gate.py:73  →  return d if d.tzinfo else d.replace(tzinfo=UTC)
scripts/data_vitals.py:91       →  return d if d.tzinfo else d.replace(tzinfo=UTC)
```
Neither ever *flags* the coercion. The TIMESTAMP INTEGRITY check family
(`scripts/measurement_gate.py:18-21`) verifies parseability, ordering, uniqueness, future-stamps and spacing
regularity — **and never tz-explicitness.** A source that silently switched from UTC to exchange-local time
would pass all five checks while shifting the whole series 8–9 hours.

This matters more here than on a generic desk because the SCREEN-ON-DISCOVERY duty makes it law:
*"DECLARE TIMESTAMP ALIGNMENT for every cross-source series and flag look-ahead risk explicitly — a daily FX
close is NOT the crypto UTC close. Unstated alignment voids the screen."* The three **live** premium clocks —
kimchi, cny, stablecoin — are exactly cross-source composites and all three carry **bare dates**. The desk's
own retraction record (kimchi as artifact; Coinbase- and Turkey-premium as pure timing artifacts) is the
realized cost of this shape. One source self-declares the hazard in prose and is graded VERIFIED anyway:
```json
data/cny_otc_premium_history.jsonl:
{"date":"2020-03-16","usdt_cny_otc":7.43,"usd_cny_ref":6.9932,"premium":0.062461,
 "snapshot_local":"23:55 CST (UTC+8) assumed","provenance":"wayback-cdx-replay"}
```
`data_vitals.py:51-56` marks it `timestamp_verified: false` and notes it "Feeds M_STRUCTURAL_BARRIER, one of
two ALIVE mechanisms" — while `data/measurement_gate.json` grades the same file **VERIFIED**. Two gates, one
file, opposite verdicts, no arbiter (same pathology as F4's kimchi disagreement).

---

### F15 — **NO RESTATEMENT / VINTAGE TRACKING ANYWHERE. REVISION LOOK-AHEAD IS HANDLED BY DELETING THE ONE SERIES SOMEONE NOTICED.**
**Severity: HIGH.**
```
$ grep -rn "restate\|restatement\|revision\|revised\|vintage\|first_publish\|as_reported\|ALFRED" \
    --include=*.py -i . | grep -v '\.venv/'
  → every hit is prose in a docstring; no ALFRED client, no vintage store,
    no first_reported / revised_at / as_of_date column in any JSONL or parquet schema,
    no bi-temporal (valid_time, record_time) table anywhere
```
The one place the desk understood the problem, it solved it by exclusion — `scripts/screen_fred_macro_axis.py:38-42`:
> "M2SL … FRED serves the CURRENT VINTAGE of a series that is revised. A backtest on current-vintage M2 uses
> numbers that were not knowable at the time: look-ahead THROUGH REVISION, which no timestamp alignment can
> fix. Untestable honestly from this archive."

That reasoning is exactly right and it is **applied to one series out of the whole macro estate.** Every other
revised series in `data/fred_macro_deep.json` (1.7 MB) carries the same defect untreated, and the honest fix —
ALFRED, which serves free point-in-time vintages of every FRED series — is not wired anywhere.

Worse, the same blindness applies to *exchange* restatements: `libs/data/lake.py:59` `delete_matching`
overwrites a corrected month with **no diff and no record that a correction occurred** (F11). So a venue
silently restating a day of klines is undetectable by construction, and `cross_validation_available` is
`False` for all 44 sources (F10), so there is no second feed to notice either.

The desk's own register already knows: `docs/GAP_REGISTER.md:240` (GAP #30, **open** since 07-18) —
"No schema-contract/replay-verification on recorder + venue-truth reference values … a real data-lineage gap
once the recorder starts feeding TCA/execution research"; and GAP #28 (**queued**, due 2026-08-08) — a monthly
audit to "verify point-in-time correctness, no look-ahead/leakage", **never yet run**.

---

### F16 — **THE ENTIRE DATA-DISCOVERY ORGAN TIER IS DEAD. FOUR UNITS FAIL DAILY, ONE REPORTS *SUCCESS* WHILE EVERY REGION FAILS, AND ZERO LOG ARTIFACTS HAVE EVER BEEN WRITTEN. MEASURED QUOTA-DEATH RATE: 100%. DIAGNOSED 8 DAYS AGO. STILL 100%.**
**Severity: CATASTROPHIC. This is the single largest finding in this audit and it is a direct L1.8 violation.**

```
$ systemctl list-units --all 'quant-*' --no-pager --no-legend
● quant-cro-ai.service      loaded failed   failed  Quant CRO AI reasoning cycle (headless Claude Code)
● quant-dataaxis.service    loaded failed   failed  Quant free-data-alternatives weekly dig
● quant-litminer.service    loaded failed   failed  Quant Literature Deep-Miner biweekly dig
● quant-prospector.service  loaded failed   failed  Quant strategy Prospector biweekly dig
  quant-frontier.service    loaded inactive dead    Regional frontier miners -- 3 regions/day rotation
```
Every one of these is a **data-acquisition organ**: `dataaxis` = the free-data-alternatives dig,
`frontier` = the 7-region multilingual dig (en cn ru kr jp ar br), `prospector` = strategy prospecting,
`litminer` = literature mining, `cro-ai` = the reasoning cycle that converts them. **All five are the
subsystem this audit covers, and all five are non-functional.**

The timers fire correctly every day, which is what makes it invisible:
```
$ systemctl list-timers --all --no-pager | grep -i quant
Thu 2026-07-30 14:00:00 UTC  11h   Wed 2026-07-29 14:00:01 UTC  12h ago  quant-dataaxis.timer
Thu 2026-07-30 15:00:00 UTC  12h   Wed 2026-07-29 15:00:01 UTC  11h ago  quant-frontier.timer
Thu 2026-07-30 18:00:00 UTC  15h   Wed 2026-07-29 18:00:01 UTC   8h ago  quant-prospector.timer
Thu 2026-07-30 19:00:00 UTC  16h   Wed 2026-07-29 19:00:01 UTC   7h ago  quant-litminer.timer
```
Green timers, dead organs — the doctrine's exact phrase: *"A green timer with zero output is a dead organ."*

**(a) THE ROOT CAUSE — LLM credit exhaustion, and the fallback built to prevent it cannot fire.**
```
$ cat data/cro_ai_logs/frontier_cn_20260728T1524.log
=== frontier-cn start Tue Jul 28 03:24:39 PM UTC 2026 ===
You're out of usage credits · resets 8pm (UTC)
=== frontier-cn exit 1 at Tue Jul 28 03:48:28 PM UTC 2026 ===
```
`ops/brain_env.sh:37-40` documents the intended fix in its own words:
> "MODEL FALLBACK CHAIN (principal 2026-07-24): a STARVED MODEL must never kill the organ. … Tonight
> every organ died out-of-credits because no model fallback existed."

The chain is `_BRAIN_MODEL_CHAIN="claude-opus-5 claude-opus-4-8 claude-fable-5"` (`brain_env.sh:76`) — and
`brain_env.sh:73` states plainly that **opus-5 and opus-4-8 sit on the same Max subscription seat**. So when
that seat is out of credits, all three chain entries fail identically. The chain provides *no independent
route*. The one genuinely independent route — a metered API key — is gated on a file that does not exist:
```
$ grep -n "_BRAIN_KEYFILE" ops/brain_env.sh
14:_BRAIN_KEYFILE="/home/quant/quant-platform/data/secrets/anthropic_api_key"
52:    if printf '%s' "$out" | grep -qiE "limit|usage credits" && [ -f "$_BRAIN_KEYFILE" ]; then

$ ls -la /home/quant/quant-platform/data/secrets/anthropic_api_key
ls: cannot access '...': No such file or directory
$ ls data/secrets/
binance_spot_testnet.json  binance_testnet.json  claude_oauth_token  databento.json
fred.json  heartbeat_url.json  llm_panel.json  netlify.json  ngrok.json  ntfy.json
```
**The `[ -f ]` guard is permanently false, so the fallback branch at `brain_env.sh:52-60` is dead code.**
A fallback chain with three entries on one seat plus one branch behind a missing file is a fallback that
cannot fall back. This is the AUTONOMY CHECK (battery move #7) failing exactly as the move predicts: the
recovery was *configured*, never *seen to work*.

**(b) THE DESK ALREADY MEASURED THIS AT 100% AND NOTHING CHANGED FOR 8 DAYS.**
```
$ .venv/bin/python -c "import json;print(json.load(open('data/quota_watch.json')))"
{'baseline': '2026-07-22T00:27:16.560714+00:00',
 'verdict_sent': True, 'verdict': 'max_needed',
 'evidence': '30h clean window | cycles: 0 ok / 4 scheduled (1 quota-died) |
              miners: 0 ok / ~8 scheduled (0 quota-died) | overall quota-death rate 100%'}
$ stat -c%s data/cro_ai_logs/quota_watch.log
0
```
**`0 ok / 4 scheduled`, `0 ok / ~8 scheduled`, "overall quota-death rate 100%"** — measured, written down,
verdict `max_needed` *sent* on 2026-07-22, and eight days later the units are still `failed`. The monitor
worked. The escalation worked. **The loop from "detected" to "fixed" is the part that does not exist.**

**(c) A LITERAL SELF-GREENING EXIT CODE.** `quant-frontier` reports `Result=success ExecMainStatus=0`:
```
$ systemctl show quant-frontier.service -p Result -p ExecMainStatus
Result=success
ExecMainStatus=0
$ journalctl -u quant-frontier.service -n 6 -o cat
rotation: digging jp
rotation: jp failed -- next invocation resumes it
rotation: digging ar
rotation: ar failed -- next invocation resumes it
rotation: digging br
rotation: br failed -- next invocation resumes it
```
The cause is one line, `ops/run_frontier_rotation.sh:28`:
```bash
bash ops/run_frontier_miner.sh "$r" || echo "rotation: ${r} failed -- next invocation resumes it"
```
`|| echo` converts every failure into a successful `echo`, the loop completes, and the script exits 0.
**Three regions failed and systemd recorded SUCCESS.** The resume logic above it is careful and correct
(`-size +1500c`, "a stub does not count, per the outcome-not-config law") — the author clearly understood the
principle and then discarded the exit status one line later. Worth stating precisely: the *resumability* fix
works; the *reporting* is inverted.

**(d) THE DIGS HAVE NEVER PRODUCED A SINGLE LOG FILE — NOT EVEN A STUB.**
```
$ find data -name "dataaxis_*" -o -name "prospector_*" -o -name "litminer_*" | wc -l
0
$ git log --oneline --all -- 'data/cro_ai_logs/dataaxis_*' 'data/cro_ai_logs/prospector_*' \
      'data/cro_ai_logs/litminer_*'
  (no output)
$ journalctl -u quant-dataaxis.service -n 12 -o cat
  (empty)
```
Because `brain_auth_check || exit 1` sits at `ops/run_dataaxis_dig.sh:6` while the log is created at line 18,
the process dies *before* opening its log. Result: **no journal entry, no log file, no artifact, no trace** —
the failure is not merely unalerted, it is unrecorded. `data/cro_ai_logs/` contains logs for `defi_lending`,
`oi_ls_live`, `ingest_axes`, `dl_oils`, `max_audit`, `watchdog`, `deep_sweep`, `frontier_en`, `frontier_cn` —
and nothing whatsoever for the three digs. (The one stub that *does* exist, `frontier_cn_...log` at 168 B, is
the only reason the credit-exhaustion message is knowable at all.)

**(e) NOTHING PAGES ON A FAILED ONESHOT.**
```
$ sed -n '265,278p' scripts/max_audit.py
#: Long-lived daemons whose code is loaded ONCE at process start.
_DAEMONS = {
    "quant-cashcarry":   "scripts/run_cashcarry_executor.py",
    "quant-deadman":     "scripts/run_deadman_switch.py",
    "quant-liquidations":"scripts/liquidation_listener.py",
    "quant-dashboard":   "scripts/serve_dashboard.py",
}
```
The audit's daemon check covers **four always-on services**; all five discovery organs are
`Type=oneshot` timer-driven and are outside it. `scripts/run_alerts.py` pages on staleness for exactly two
heartbeats (`data/cashcarry_exec_heartbeat:158-164`, `data/recorder_heartbeat:182-186`) — **no page for
`recorder_spot_heartbeat`, `recorder_bybit_heartbeat`, `oi_ls_live_heartbeat`, `defi_lending_heartbeat`,
`liquidation_heartbeat`, and no page for any unit `Result=failed`.**

**THE CONSTITUTIONAL READING.** L1.8 PARALLEL MAXIMALISM: *"mining and acquisition run at absolute maximum
capacity, forbidden to throttle for conversion bottlenecks."* Acquisition capacity is currently **zero**, for
eight days, unpaged. L1.9 FRONTIER: *"default state is aggressive discovery."* The 7-region multilingual
frontier dig — the specific organ that hunts the Gitee/CSDN/8btc/Korean/Japanese/Russian/Arabic/Portuguese/
Turkish sources the doctrine names by name — has not completed a region since 2026-07-28, and reports success.
And the TIMIDITY clause is explicit that this is a *cost*, not a risk: **budgets unspent and cadences left
slow are real compounding losses reported as loudly as a risk breach.** This is a budget that cannot be spent.

---

### F17 — **A COLLECTOR RUNS AS STEP 5 OF THE DAILY CYCLE EVERY DAY, HAS NEVER PRODUCED A BYTE, AND KEEPS THE CYCLE GREEN BY DESIGN.**
**Severity: HIGH (self-greening organ).**
```
$ grep -n "naver" scripts/daily_research_cycle.py
38:    ("naver_krsearch", "scripts/collect_naver_krsearch.py", 60),  # KR attention (key-gated)

$ ls data/secrets/ | grep -i naver     → (nothing)
$ ls -la data/batch_krsearch_screen.json
ls: cannot access 'data/batch_krsearch_screen.json': No such file or directory
```
`collect_naver_krsearch.py:52-63` (`_keys()`) returns `None` when neither `NAVER_CLIENT_ID/SECRET` env vars
nor `data/secrets/naver.json` exist; `main()` then returns early. Neither the env vars (absent from every
unit's `Environment=`) nor the keyfile exist, so the step has **executed every day and produced nothing,
ever**, while counting as a completed step. The inline comment `# KR attention (key-gated)` documents the
gating, which is honest — but "documented no-op" and "monitored no-op" are different things, and nothing
counts it.

This matters beyond one file: Korean retail search attention is one of the highest-prior axes the desk has
(the kimchi-premium mechanism lives in the same market), and the collector for it is a permanent stub.

---

### F18 — **BINANCE IS A SINGLE POINT OF FAILURE FOR SUBSTANTIALLY THE ENTIRE CRYPTO DATA ESTATE. EXACTLY ONE AXIS ON THIS DESK HAS REDUNDANCY.**
**Severity: HIGH.**

A full grep for `fallback|mirror|failover|redundan|_ALT|alternate` across all collectors returns **one real
implementation**: `libs/data/onchain_flows.py:20-27`, four keyless Ethereum RPC mirrors
(`ethereum-rpc.publicnode.com`, `eth.llamarpc.com`, `cloudflare-eth.com`, `rpc.ankr.com/eth`) tried in order
at `_rpc():62-79`. That is the desk's only redundant data axis.

Everything Binance touches, single-routed:
| Consumer | Binance endpoint |
|---|---|
| `collect_oi_ls_live.py:42` | `fapi.binance.com/futures/data` (OI, long-short, taker) |
| `collect_binance_metrics.py` → `libs/data/crypto_source.py` | `api.binance.com` |
| `dl_oi_ls_universe.py:41-43` | `data.binance.vision` (both hostnames = same bucket) |
| `ingest_crypto_enriched.py` | `libs/data/crypto_source.py` → the bronze crypto lake |
| `run_recorder.py:31`, `run_recorder_spot.py:39` | `fapi.binance.com`, `api.binance.com` (2 of 3 moat venues) |
| `run_listing_watch.py:20` | `fapi.binance.com` |
| `collect_kimchi_premium.py:28`, `collect_cny_premium.py`, `collect_onchain_activity.py:35`, `collect_stablecoin_supply.py:30`, `collect_naver_krsearch.py:28` | **the USD price leg of every premium/attention composite** |

That last row is the sharpest part: **every cross-source premium axis on this desk uses Binance as its USD
reference leg.** A Binance outage, a regional block, or a silent restatement does not degrade one signal — it
corrupts the entire premium family simultaneously and identically, which is precisely the correlated failure
that cross-validation exists to catch (F10: `cross_validation_available: False` × 44).

Other single-routed axes with no second source: DeFi lending (`yields.llama.fi`), stablecoin supply series
(`stablecoins.llama.fi`), on-chain metrics (`api.blockchain.info`), exchange flows
(`community-api.coinmetrics.io`), liquidations (`stream.bybit.com`), options/vol surface (`www.deribit.com`),
CME (`hist.databento.com`, unscheduled).

Two routes are **already known-broken and were absorbed as directives rather than fixed**:
- `ingest_axes.py:194-205` — `farside.co.uk` **403s from this VPS**; the code prints "BLOCKED from VPS --
  registering directive for alternate route". `data/lake/bronze/etf_flows/` holds 6 raw HTML files.
  **Bitcoin-ETF flows — a top-tier orthogonal axis — are not being collected.**
- `ingest_axes.py:38-39` — "FRED is IP-blocked from this host since 2026-07-21", worked around by moving to
  NY Fed + Treasury primary publishers. *This one is the model of how to do it right* — a genuine
  primary-source substitution, logged, with the replacement wired. F9's Stooq block should have been handled
  the same way and was not.

And `libs/data/multiexchange.py:34,59` already contains `fetch_bybit_funding` and `fetch_okx_funding` —
**written, working, and called by no collector script.** The second and third funding feeds exist in the repo
and are not wired. That is the cheapest available fix for F10.

---

### F19 — **THERE IS EXACTLY ONE SELF-REPAIRING COLLECTOR, AND NO HOUR-GRANULARITY GAP REPAIR EXISTS ANYWHERE. EVERY MISSED HOUR IS PERMANENT.**
**Severity: HIGH.**

The one that works — and it is genuinely excellent — is `scripts/dl_oi_ls_universe.py`. `pull_metrics():131-186`
builds a `have` set from what is on disk, then re-walks the *entire* range `START=date(2021,6,1)` → yesterday
on **every run**, so any hole from any past failure is retried on the next cron tick:
```
$ tail data/cro_ai_logs/dl_oils_daily.log
RAYUSDT: +0 metric days (1662 missing)
...
DONE: 139 symbols
```
(Note the cost: it re-probes 1,662 permanently-absent days per delisted symbol every single day. Correct but
unbounded — it never learns that a delisted symbol's history is closed.)

Weaker but real: skip-existing in `ingest_axes.py:157-158`, date-dedupe in `collect_onchain_metrics.py:59-66`,
and full-rewrite-from-2010 in `collect_coinmetrics_flows.py:237` (gap-proof by construction, no detector).

**Nothing else repairs anything.** The hourly tier — `collect_oi_ls_live.py`, `collect_defi_lending.py`, and
all three moat recorders — is **append-only with no back-look**. There is no code anywhere that detects a
missing *hour* and refetches it. This is why F5's moat gaps (median symbol missing 28 % of hours on `fut`) are
permanent: not because depth snapshots are unrecoverable in principle, but because nothing ever looks.

Detectors exist and are wired to nothing:
- `libs/data/quality.py:44-53` `detect_missing_bars` (calendar-aware expected-vs-present), `:65-81`
  `detect_gaps`, `:84-131` `compute_quality_score` returning `n_missing`/`completeness`. **Only caller outside
  tests is `libs/data/medallion.py:16,35` in `build_silver`, and nothing acts on `n_missing`.** Worse, it
  operates on MT5-lake bar frames — which are frozen (F3/F7). The gap detector is pointed at dead data.
- `collector_monitor.py:88-94` emits `RATE-DROP {len(dates)}/{expected} expected days` as a string, and
  `:131` states outright it has "no authority to promote or resume anything."
- `data_vitals.py:204` emits `action: "DEAD -- FAILOVER"`. **There is no failover code path anywhere in the
  repo.** The word is a label, not a mechanism (and per F1 all eight of its uses are false anyway).

Two scripts named `backfill_*` do not backfill: `scripts/backfill_oi_ls_oos.py` and
`scripts/backfill_onchain_oos.py` write `reports/reconstructed_oos/*.json` — they are out-of-sample
*backtests* on already-archived data. Anyone searching the repo for backfill capability finds these first.

---

### F20 — **SIX DATASETS ON DISK HAVE NO PRODUCER AND NO CONSUMER IN COMMITTED CODE. THEY WERE WRITTEN BY AD-HOC SESSION CODE THAT WAS NEVER COMMITTED, AND THREE OF THEM ARE ACTIVELY SCORED BY THE HEALTH MONITOR AS "DEAD — FAILOVER" FOR A COLLECTOR THAT DOES NOT EXIST.**
**Severity: HIGH.**

Method: for every `data/*.jsonl` and `data/*.parquet`, `grep -rl <basename> scripts/ libs/ ops/ api/ app/ tools/`.

| orphan | size | last write | refs in code |
|---|---|---|---|
| `data/kr_perasset_premium_history.jsonl` | 473 KB | 2026-07-28 15:46 | **none** |
| `data/cfe_crypto_settlements.jsonl` | 217 KB | 2026-07-28 15:09 | **none** |
| `data/cfe_regulated_basis_daily.jsonl` | 45 KB | 2026-07-28 15:11 | **none** |
| `data/8btc_era_thread_catalog.jsonl` | 110 KB | 2026-07-28 15:48 | **none** |
| `data/try_premium.jsonl` | 58 B | 2026-07-23 00:12 | **none** |
| `data/venue_premium_coinbase.jsonl` | 57 B | 2026-07-23 00:02 | **none** |

Mtimes cluster tightly at 2026-07-28 15:09–15:48 — one uncommitted session. These are **non-regenerable,
unowned, and unmonitored-by-anything-that-could-fix-them**, yet three of them *are* scored by `data_vitals.py`
and flagged `"DEAD -- FAILOVER"` (F1) — the monitor is demanding failover for collectors that were never
written. `kr_perasset_premium_history.jsonl` is 3,008 rows spanning 2018→2026 feeding the premium family; if
it is corrupted it is gone.

Same class, non-orphan but explicitly non-regenerable — and this one is load-bearing.
`data/data_vitals.py:45-52` records for `cny_otc_premium_history.jsonl`:
```
"collection": "wayback-cdx-replay of history.btc126.com (UNCOMMITTED one-off)",
"regenerable": false, "timestamp_verified": false,
note: "Feeds M_STRUCTURAL_BARRIER, one of two ALIVE mechanisms."
```
**One of the desk's two live mechanisms is fed by a 134 KB file that no committed code can reproduce, whose
timestamp alignment is explicitly unverified (F14), and whose source is a Wayback replay.** That is a
single-file dependency under a live mechanism with no regeneration path.

The desk found this class of problem last cycle and it is unchanged —
`docs/research/deep_sweep/20260729_data-intelligence.md:98-100` asks "Which organ writes
kr_perasset_premium_history.jsonl and cfe_crypto_settlements.jsonl … → nothing". **Found, written down, not
fixed, and rediscovered by this audit** — the §35/§41 disposition failure applied to data ownership.

---

### F21 — **EIGHT SYSTEMD UNITS RUNNING PRODUCTION COLLECTION ARE NOT IN VERSION CONTROL, AND THE ONE UNIT THAT *IS* IN THE REPO POINTS AT A PATH THAT DOES NOT EXIST.**
**Severity: MEDIUM-HIGH (reproducibility of the collection layer itself).**

Repo contains: `ops/quant-{blindrediscovery,dataaxis,frontier,litminer,prospector}.{service,timer}` and
`deploy/quant-research.service`. The host additionally runs, with **no repo copy**:
`quant-cashcarry`, `quant-cro`, `quant-cro-ai`, `quant-dashboard`, `quant-deadman`, `quant-liquidations`,
`quant-refresh`, `quant-tunnel`.

Those eight include **`quant-liquidations`** (the Bybit liquidation feed), **`quant-refresh`** (which runs
`data_health` and `run_alerts` every 3 minutes), and **`quant-cashcarry`** — which per its own ExecStart also
performs the daily collector fan-out for `collect_binance_metrics`, `collect_market_breadth` and
`collect_deribit_surface` via `_daily_data_tasks` (`run_cashcarry_executor.py:72-97`). So **three collectors
are scheduled by an uncommitted unit file, inside the live trading executor.** Rebuilding this host from the
repo would silently lose them.

Meanwhile the one collection-related unit that *is* committed cannot run:
```
$ grep -n WorkingDirectory deploy/quant-research.service
14:WorkingDirectory=/opt/quant-platform          # path does not exist on this host
```

`daily_research_cycle.py` is also **double-scheduled** — cron (`0 2 * * *`, guarded by `pgrep`) and
`quant-cro.timer` (`08:01`, unguarded). Both fire; `quant-cro.timer` last ran 2026-07-29 08:01:03 while
`data/.last_cro_cycle` reads 2026-07-30 02:00. Two schedulers for one 66-step pipeline that includes the
collector steps, with only one of them guarded.

---

### F22 — **FIVE COLLECTORS ARE DEAD CODE WITH NO SCHEDULER, INCLUDING THE ONE THAT PRODUCED THE LARGEST SINGLE DATASET ON DISK (1.1 GB OF CME DATA).**
**Severity: MEDIUM-HIGH.**

| script | output | state |
|---|---|---|
| `scripts/pull_cme.py` | `data/lake/bronze/cme/*` — **1.1 GB, 8 files**, BTC/ETH futures 2018→2026-07-20 | zero cron, zero systemd, zero refs. Databento key **present** at `data/secrets/databento.json`. Last written 2026-07-21. |
| `scripts/reconstruct_kaiko_reference_rate.py` | `data/kaiko_vwm_reference_rate.jsonl` | zero refs; frozen 2026-07-26 |
| `scripts/dl_metrics_history.py` | `data/oi_ls_history.jsonl` | zero cron; **series ends 2023-12-03** |
| `scripts/make_archive.py` | — | zero refs |
| `scripts/collector_author.py` | `data/generated_collectors/` | zero refs. **Dir is EMPTY; `data/collector_attempts.jsonl` is 0 bytes.** Never produced a single collector. |
| `ops/run_oils_chain.sh` | chains `dl_oi_ls_universe` → `backfill_oi_ls_oos` | referenced by no scheduler |

`pull_cme.py` is the notable one: **1.1 GB — the largest non-moat dataset the desk owns, regulated CME
futures back to 2018, the single best instrument for the desk's basis/carry work — is a one-shot manual pull
with no automation, and it is already 9 days stale** (`newest file mtime 8.94 d`). It is also paid
(Databento), which under L1.11/FREE-FIRST makes its unscheduled state doubly odd: the desk paid for it (or
used a trial), landed it once, and wired no refresh. Contrast `data/lake/bronze/cfe_*` — CBOE's *free*
regulated crypto futures settlements, which the universe map added on 2026-07-28 and which is an orphan (F20).

`collector_author.py` deserves its own line: it is an LLM-driven collector *generator* — safety-scanned
(`:111`), isolated-run (`:124`), validated (`:153`) — i.e. exactly the SELF-IMPROVEMENT MULTIPLIER (L1.22)
capability that would let acquisition scale without human authoring. It has **never run** (empty output dir,
0-byte attempt log, no scheduler). Built, never wired, never measured.

---

### F23 — **THERE IS NO SILVER AND NO GOLD LAYER. THE MEDALLION ARCHITECTURE IS BUILT AND HAS NEVER RUN OUTSIDE TESTS, SO ZERO REUSABLE DERIVED DATASETS EXIST AND THE GAP DETECTOR HAS NEVER SEEN PRODUCTION DATA.**
**Severity: HIGH — the single biggest missed *compounding multiplier* in the subsystem.**
```
$ ls data/lake/
bronze                                  # <-- that is all

$ grep -n "class Layer" -A3 libs/data/lake.py
24:class Layer(StrEnum):
25:    BRONZE = "bronze"
26:    SILVER = "silver"
27:    GOLD = "gold"

$ grep -rn "build_silver\|build_gold\|Layer.SILVER\|Layer.GOLD" --include=*.py . | grep -v '\.venv'
tests/data/test_medallion.py:9,24,33,34,38,45     <-- tests
libs/data/medallion.py:30,44,48,50                <-- the definitions themselves
   (no other caller anywhere)
```
Consequences, and the second one is the sting:

1. **Every research script reads raw bronze and re-derives its own cleaning, alignment and features.**
   There is no shared cleaned series, no shared feature table, no shared resampling. Two screens on the same
   symbol can and will disagree because each cleaned it differently, and neither records how. This is the
   opposite of a compounding multiplier: the cost of every new experiment includes re-doing work that should
   have been done once.
2. **`libs/data/quality.py` — the desk's only real gap detector — has therefore never run on production data.**
   Its sole non-test caller is `libs/data/medallion.py:16,35`, inside `build_silver`. `build_silver` has never
   been called outside tests. So `detect_missing_bars`, `detect_gaps` and `compute_quality_score` exist,
   are tested, are correct, and have **never once been pointed at the 26,315 parquet files on disk.** Had they
   been, F2 (BTCUSDT 39 days stale) and F3 (FX dead 41–55 days) would have been caught the day they happened.

The gap between "we have a data-quality library" and "our data quality is measured" is exactly this one
uncalled function, and it is the cheapest high-value fix in this report.

---

### F24 — **THE EXECUTION REALITY MODEL NEVER EXHAUSTED A SINGLE ORDER BOOK IN 300 PROBES. IMPACT IS NOT MEASURED — HALF-SPREAD IS. 17 OF 60 LEGS HAVE EXACTLY ZERO SIZE-SLOPE, AND THEY ARE THE LIQUID MAJORS.**
**Severity: HIGH (CONTRARIAN — a validated-looking dataset that cannot answer its own question).**
```
$ .venv/bin/python  # size-slope of median_bps per symbol/leg over the 5 probe sizes
legs total=60   FLAT (zero size-slope)=17   rising=43
FLAT legs:
  BTCUSDT   spot_buy [0.001, 0.001, 0.001, 0.001, 0.001]      ETHUSDT  spot_buy [0.026 x5]
  BTCUSDT   fut_sell [0.008 x5]                               ETHUSDT  fut_sell [0.027 x5]
  BNBUSDT   spot_buy [0.088 x5]  fut_sell [0.088 x5]          SOLUSDT  spot_buy [0.662 x5] fut_sell [0.660 x5]
  ADAUSDT   fut_sell [3.028 x5]                               XRPUSDT  fut_sell [0.455 x5]
  DOGEUSDT  fut_sell [0.694 x5]                               TRXUSDT  spot_buy [1.519 x5] fut_sell [0.152 x5]
  OPUSDT    fut_sell [5.379 x5]   SUIUSDT fut_sell [0.697 x5] XLMUSDT  spot_buy [2.800 x5]
  COOKIEUSDT spot_buy [59.172 x5]

$ .venv/bin/python  # exhausted_frac across every symbol x leg x size cell
exhausted_frac distribution across ALL 300 cells: {0.0: 300}
```
**`exhausted_frac == 0.0` in all 300 cells is the whole diagnosis.** The probe never consumed level 1 of any
book, for any symbol, at any size. So the number being reported is the **level-1 half-spread**, and for the
liquid majors it is constant because $2,500 does not move BTC's top-of-book. `data/data_sanity_report.json`
flags 17 of these as CRITICAL with the reason *"a flat curve means the estimator returned a constant, so any
sizing decision using it is unfounded."* That reading is slightly wrong and the correction matters: **the
estimator is fine; the probe grid is too small to touch the book.**
```
$ cat data/cost_model.json | jq .sizes_usdt      → [100, 250, 500, 1000, 2500]
$ grep -o "ExecStart=.*" /etc/systemd/system/quant-cashcarry.service
... run_cashcarry_executor.py --live --top 10 --hold-top 3000 --capital 4500 --interval 600
```
At $4,500 total capital across 10 carries, $2,500 *is* roughly the real clip — so the model is adequate for
today and **structurally unable to inform any scaling decision whatsoever.** There is not one observation in
the dataset where size mattered. L1.5 (EXECUTION PHYSICS) requires alpha to survive "realistic slippage, fees
and impact"; the **impact** term is currently unmeasured by construction, and `median_pair_open_bps_at_500 =
2.872` is a spread cost masquerading as an impact curve. L1.18 declares alpha diversity "capacity-blind (§42)"
— fine as a *policy*, but here capacity is not deliberately ignored, it is **unmeasurable**, which is a
different thing and should not be conflated with the policy.

The fix is cheap and the data already exists: the moat holds 16,536 hourly L2 depth shards (S1). Extending
the probe grid to $10k / $50k / $250k against the recorded books would produce a real impact curve — and
would, in the same pass, finally give the 6 GB moat a research consumer (F5/F6).

---

### F25 — **FOUR OF TWELVE FORWARD SLOTS ARE OCCUPIED, ONE BY A RETRACTED ARTIFACT. TWO-THIRDS OF THE DESK'S VALIDATION CAPACITY IS IDLE — WHICH THE DOCTRINE SCORES AS A COST, NOT A SAFETY MARGIN.**
**Severity: HIGH (TIMIDITY defect).**
```
$ .venv/bin/python -c "import json;d=json.load(open('data/axis_shadow_state.json'));
   print(d['updated'], d['min_forward_days'], len(d['axes'])); [print(' ',a) for a in d['axes']]"
2026-07-29T08:46:54 min_forward_days=40 n_axes=4
  {'axis': 'kimchi_premium', 'last': '2026-07-29'}
  {'axis': 'defi_utilisation'}                          <-- no 'last' field
  {'axis': 'stablecoin_supply_momentum', 'last': '2026-07-29'}
  {'axis': 'cny_premium'}                               <-- no 'last' field

$ grep -rn "MAX_FORWARD_SLOTS" --include=*.py . | grep -v '\.venv'
libs/research/axis_screen.py:154: # and clocks are capped at MAX_FORWARD_SLOTS=12 and Holm-corrected...
```
**4 of 12 slots used. And `kimchi_premium` was retracted as a timing artifact** (commit `02f2917`:
"kimchi edge retracted as artifact") **while still holding a slot** — so 3 live clocks against a 12-slot
budget, i.e. **75 % of validation capacity idle.**

The doctrine is explicit that this is not prudence: *"idle capital, under-deployment … opportunities deferred
without evidence, capability left unused, budgets unspent, cadences left slow — every one is a REAL COMPOUNDING
COST."* And the CLOCK-SATURATION DUTY makes it concrete: *"every verified axis has a pre-registered hypothesis
ACCRUING within 7 days; an empty forward slot is idle capital's research twin."* There are eight empty slots.

The burden of proof sits on the conservative choice, and there is no documented push that failed here. What
makes it worse: the reason the slots are empty is **not** a shortage of candidates — F26 shows 32 catalogued
sources awaiting conversion and F16 shows the organs that would screen them are dead. Two of the four
occupied slots (`defi_utilisation`, `cny_premium`) do not even carry a `last` date, so their accrual cannot be
verified from the artifact.

Note the honest counterweight, which the desk got right: `min_forward_days: 40` and the note *"ELIGIBLE means
the evidence bar is met and a promotion decision may be taken — it is NOT an automatic deployment."* The
**bar** is sound. It is the **throughput** that is idle.

---

### F26 — **32 OF 60 CATALOGUED SOURCES (53%) HAVE NEVER BEEN CONVERTED. SEVENTEEN SIT AT LITERAL GRADE `catalogued` — THE EXACT STATE SCREEN-ON-DISCOVERY WAS WRITTEN TO ABOLISH.**
**Severity: HIGH.**
```
$ .venv/bin/python  # grade histogram over data/data_universe_map.json['sources'] (n=60)
  17  catalogued
  15  adopted-pending-verify
   5  REDUNDANT-with-existing-collector
   2  principal-signup-gated
   1  adopted                              <-- ONE source is plainly adopted
  ~20 one-off verified-clean / UNVERIFIED prose variants
```
The 17 at `catalogued` — none ingested, none screened:
```
37-dydx-numia-bigquery        public BQ: fills/positions/mempool-level
38-academic-lob-windows       published LOB windows (Bybit ~200-300ms, Binance events, LOBSTER)
42-gdelt                      15-min global news events, BQ public
43-google-trends-pytrends     fixed schedule + immutable raw archive
48-reddit-full-corpus         Watchful1 torrents 2005-2025 + Arctic Shift + PullPush
49-crypto-social-firehoses    Farcaster hubs, Bluesky firehose, Telegram (Telethon), Bitcointalk, /biz/
51-ethpandaops-xatu           public Parquet: first-seen, beacon, MEV relay; mainnet from 2023-03
52-mev-classification         zeromev per-tx MEV classes + EigenPhi/Flashbots
55-leaderboards-copytrading   Binance/Bybit/OKX/Bitget endpoints; documented decaying edges
56-bitfinex-margin-ls         oldest free positioning series (decade+)
59-competition-archives       Kaggle G-Research crypto, JS/Optiver, Numerai, Quantiacs
60-archived-community-knowledge  Quantopian archive, QuantFinance SE dumps, QuantConnect, Wilmott
61-free-institutional-research   BitMEX Research, Kaiko/Glassnode/CM weeklies (crowding proxy)
68-solana-old-faithful        full ledger from genesis (program-filtered slices)
70-cryptopanic                headline times + votes
72-airdrop-claim-calendars    unlock-adjacent scheduled sell-pressure
73-minor-fillers              Nasdaq DL BCHAIN; Hashrate Index (hashprice/miner economics)
```
Every one is **free, public, and named with its access route.** The SCREEN-ON-DISCOVERY duty is unambiguous:
*"DISCOVERING A DATASET IS HALF A DELIVERABLE … carry it through a Stage-A screen IN THE SAME RUN — do not
queue it, do not hand it off."* Seventeen were queued. And because the grade is unnormalized prose (F13),
**no gate can count them**, so §33's conversion pressure never fires on this list.

Two are especially costly to leave, given the desk's own stated theory that edge lives in orthogonal
non-price axes: `51-ethpandaops-xatu` (block first-seen times + MEV relay data — genuine microstructure with a
mechanism, free Parquet, from 2023-03) and `55-leaderboards-copytrading` (venue-published positioning of
identified traders, with the honest caveat "documented decaying edges" already recorded).

Credit where due — the map's `residual_gaps_unpurchasable` list is exactly the FREE-FIRST evidence standard
done right: 7 gaps, each with the *mechanism* of unavailability, e.g. *"tick-level Binance L2 diffs BEFORE the
recorder start date (destroyed at source; recorder solves forward)"*, *"bitFlyer pre-today tick history
(31-day API cutoff is a hard wall; only a forward recorder closes this)"*. That is a documented failed search
with a graded residual gap, not a default. **The catalogue's problem is not honesty, it is conversion.**

---

### F27 — **NEGATIVE SPACE: WHAT HAS NEVER BEEN COLLECTED, ASKED, OR SIMULATED**
Evidence-backed absences, each verified by search rather than assumed:

| absent capability | proving check | why it matters |
|---|---|---|
| **Point-in-time macro vintages (ALFRED)** | `grep -rniE "ALFRED\|vintage\|first_publish\|as_reported"` → prose only (F15) | Free. Would make the entire FRED estate honestly backtestable instead of one series excluded |
| **Dividend / total-return equity data** | `grep -rniE "adj_close\|dividend\|total_return"` → zero real matches (F8) | Free from several sources. Currently makes 5 bond/credit ETFs actively misleading |
| **Any intraday crypto history 1m–4h** | `{'D1': 277, 'H8': 10}` (F6) | Free from Binance/Bybit/OKX archives. Blocks the entire hourly signal band |
| **A second feed for anything except ETH RPC** | `cross_validation_available: {False: 44}` (F10, F18) | `libs/data/multiexchange.py:34,59` already has Bybit+OKX funding, unwired |
| **Delisted / dead-symbol survivorship set** | bronze crypto holds 277 *currently-listed* symbols; `dl_oi_ls_universe` re-probes delisted names as "1662 missing" rather than archiving them as terminated | Cross-sectional crypto studies are survivorship-biased and nothing records it |
| **Entity resolution across venues/chains** | no mapping table anywhere; `BTCUSD` (MT5 CFD) and `BTCUSDT` (Binance perp) coexist in bronze as unrelated symbols | Cross-venue joins are done ad hoc per script, unverifiable |
| **Synthetic black-swan stress data (L1.11 mandate)** | `data/black_swan_library.json` = 3 keys (`policy`, `updated`, `scenarios`) — a scenario list, not generated paths | Mandated by the constitution; currently a config file, not a data lab |
| **Order-book depth on any venue but Binance/Bybit** | `data/moat/` = `{bybit, fut, spot}`, 2 of 3 Binance (F18) | OKX/Deribit/Hyperliquid depth is free to record forward |
| **Options surface history** | `data/deribit_surface.parquet` exists; `collect_deribit_surface.py` has no retry and is scheduled inside the *trading executor* (F21) | Vol-surface term structure is a top orthogonal axis; single-routed and fragile |
| **A data-quality time series** | `data_vitals.json`/`collector_health.json` are **overwritten** each run — no history kept | Cannot answer "when did BTCUSDT stop updating" or trend quality; every outage must be re-derived forensically, as this audit just did |

That last row is worth isolating: **the desk's data-health artifacts have no history.** They are snapshots.
So there is no way to ask when a source died, how long it has been dead, or whether quality is improving —
and the RATCHET CHECK (battery move #10) cannot be applied to data quality at all, because there is no floor
recorded to ratchet. That is a one-line fix (append instead of overwrite) with permanent compounding value.

---

## 2. WHAT WE DON'T KNOW (ignorance ledger)

### Known unknowns — questions this audit could not answer

**U1. How long has FX/equity/metal/index/energy actually been dead, and was it ever alive on this host?**
Content ends 2026-06-05→06-19; mtimes are 38–40 d. But `MetaTrader5` cannot run on Linux (F7), so it is
unclear whether these partitions were ever produced *here* or were copied in from a Windows machine. If the
latter, the "outage" is really "a one-time manual import that was never repeatable," which is a materially
different (and worse) diagnosis. **Resolvable:** `git log` on the partition directories, and checking whether
any host ever had the terminal. I did not resolve it.

**U2. Which process wrote the six orphan datasets (F20)?** No committed code contains their names; mtimes
cluster at 2026-07-28 15:09–15:48. The prior sweep asked the same question and also failed to answer it. Until
answered, `kr_perasset_premium_history.jsonl` (473 KB, 2018→2026) and `cny_otc_premium_history.jsonl` (feeding
a LIVE mechanism) are unreproducible by anyone.

**U3. Is the moat's symbol-universe expansion (20→30) correlated with recent liquidity?** F5 establishes the
panel width changes mid-sample with no backfill. Whether the added symbols were selected on *recent* activity
— which would make cross-sectional studies on the tape look-ahead-contaminated — I could not determine; the
selection code and its as-of date are not recorded anywhere in the moat metadata (there is none).

**U4. Are the 41-day-stale FX/equity prices *point-in-time correct* for the period they do cover?** F8 proves
they are price-only. Whether the CFD series also embed broker-specific spread/rollover adjustments that drift
against exchange prints is untested — and untestable without a second feed (F10).

**U5. What is the desk's true data-to-alpha conversion ratio?** `research_memory` holds 144 rows spanning only
**2026-07-24 → 2026-07-29** (6 days), of which just **8 are `category='dataset'`**:
```
$ .venv/bin/python  # sqlite: data/sor_research.sqlite research_memory
rows: 144   by category: {construction: 94, hypothesis: 29, method: 10, dataset: 8, mission: 3}
by result: {failure: 122, success: 17, pending: 5}   date range: 2026-07-24 .. 2026-07-29
```
Eight dataset-level outcomes against ~400 series and 60 catalogued sources. The denominator is unknown
because nothing before 2026-07-24 was logged, so the ratio **cannot be computed**, only asserted. (The 8 rows
that exist are high quality — one of them *is* F3, recorded 2026-07-26: *"FX LAKE COVERAGE GAP: the ingested
fx axis holds 57 crosses and NOT ONE high-barrier currency."* Found four days before this audit, unfixed.)

**U6. Why do `quant-dataaxis`/`prospector`/`litminer` leave no journal entry at all?** `Type=oneshot` with
`ExecStart=/bin/bash …` should log to the journal. Empty journals plus zero log files means the failure path
is even earlier than `brain_auth_check` for at least some invocations. Unresolved; matters because it is the
difference between "credit exhaustion" and "the unit never executes."

**U7. Whether `libs/data/cot_source.py` (CFTC) and `libs/data/prediction_markets.py` (Polymarket) have any
live scheduler.** Neither appears in any `collect_*.py`; `data/cot_zcache.parquet` is frozen at 2026-06-21
(38 d) and is referenced only by `scripts/run_mt5_portfolio.py` — i.e. by a dead MT5 consumer. Two more
plausibly-orphaned axes.

### Suspected unknown unknowns (where confidence is lowest)

- **Silent truncation is the desk's dominant undetected failure mode, and I found it three times in one
  audit** (F1 `MAX_ROWS=3000`; F2/F3 hive globs returning fewer rows with no error; F9 a blocked HTTP route
  absorbed as "symbol?"). Each was invisible because *fewer rows is not an error anywhere in this codebase*.
  I expect more instances I did not find. **The generalisable defect: no read path in the repo asserts an
  expected row count or an expected end-date.**
- **Every number in `data/*.json` that no one has re-derived from source.** F1 showed the health monitor is
  100 % wrong in its alert class; F24 showed the cost model measures something other than what it is named
  for. Both looked authoritative. I checked perhaps a dozen artifacts against their sources; there are 240.
- **The moat's own contents.** I verified file *presence* per symbol-hour (F5) and never opened a shard to
  check that the depth snapshots inside are well-formed, non-duplicated, and tz-consistent. 6.0 GB, 16,536
  files, `t` = bare epoch ms (F14), zero schema contract (JSONL is uncontracted, F13/§3). **The desk's
  flagship asset has never had its contents validated by anything.**
- **Whether any *published* result on this desk was computed on stale or price-only data.** F11 makes this
  unanswerable in principle — no result carries a data version. Given F2/F3/F8 the base rate is unlikely to be
  zero.

---

## 3. WHAT COULD MATTER MOST (ranked opportunities)

Ranked by `expected impact × confidence / (cost × maintenance)`. ⚡ = compounding multiplier.

### O1 — Restore the data-discovery organ tier (fix F16). ⚡
**Exactly what:** (a) create `data/secrets/anthropic_api_key` so `brain_env.sh:52` can actually fall back to a
metered route, or replace the chain with one that has an independent seat; (b) change
`run_frontier_rotation.sh:28` from `|| echo …` to recording the failure **and** exiting non-zero once the loop
ends; (c) move `brain_auth_check` to *after* log creation in all three dig scripts so failures leave an
artifact; (d) add all five oneshot units to a `Result=failed` check that pages.
**Why:** acquisition capacity is zero for 8 days (L1.8 violation) and nothing pages. **Evidence:**
`systemctl list-units 'quant-*'` → 4 `failed`; `quota_watch.json` → `"quota-death rate 100%"`, `verdict_sent:
true`, dated 2026-07-22; `find data -name "dataaxis_*" → 0`; `ls data/secrets/anthropic_api_key` → absent.
**Benefit:** restores the *only* organs that produce new data axes. **Complexity:** low (one file, three
one-line edits, one keyfile). **Deps:** an independent LLM credit route. **Validation:** a `dataaxis_*.log`
> 1500 B exists tomorrow, and `systemctl is-failed` returns clean. **Failure modes:** metered spend
unbounded — cap it. **Alternatives:** lower dig frequency to fit the seat (rejected: that is throttling
acquisition, forbidden by L1.8). **ROI:** highest in this report. **Confidence:** high. **Retirement:** none —
this is a permanent rail. **Horizons:** 1w restores discovery; 3m+ every axis found compounds.

### O2 — Point `libs/data/quality.py` at the actual lake, on a schedule, with history. ⚡
**Exactly what:** a daily job that walks every bronze partition + every moat symbol-hour, computes
`max(timestamp)`, expected-vs-present bar counts and hourly completeness, **appends** to
`data/data_quality_history.jsonl`, and pages when any series' lag exceeds ~3× its own median cadence.
**Why:** this single job detects F2, F3, F5, F6, F19 and F27's missing history — five findings, one artifact.
**Evidence:** `build_silver` (the only caller of `quality.py`) has zero non-test callers; `collector_health.json`
covers 4 files of ~400; both health artifacts are overwritten, so no outage is reconstructible.
**Benefit:** ends the class of failure that produced most of this report. **Complexity:** low-medium — the
measurement code already exists and is tested; this is wiring plus a cron line. **Validation:** it must flag
BTCUSDT and the FX axis on its first run, or it is wrong. **Failure modes:** alert fatigue — so fix F1 first
or in the same pass, because a second always-wrong alarm is worse than none. **ROI:** very high.
**Confidence:** high. **Retirement:** never. **Monitoring:** the monitor's own artifact must itself be
freshness-checked (else it becomes F16). **Horizons:** 1w catches today's outages; 1y a real quality time
series enables the RATCHET CHECK on data.

### O3 — Fix the health monitor's two scoring bugs (F1) before adding any new alarm.
**Exactly what:** in `scripts/data_vitals.py`, (a) read the *tail* rather than the head — or compute
`max(ts)` streaming — so `MAX_ROWS` cannot truncate away the newest record; (b) handle panel-shaped data by
deriving cadence from **distinct** timestamps, not pairwise gaps, so a median gap of 0 stops forcing
`dqs ≤ 0.25`. Then re-baseline `n_dead`.
**Why:** 8 of 8 DEAD verdicts are false; the alert channel carries zero information and has trained the desk
to ignore it. **Evidence:** the F1 truth table — `defi_lending.jsonl` flagged DEAD with a record at
`2026-07-30T02:17`; `coinmetrics_flows.jsonl` age reported 2,856 d for a file updated yesterday.
**Benefit:** makes every subsequent data alarm believable — a precondition for O2. **Complexity:** low.
**Validation:** re-run; all eight must clear, and deliberately staling a test file must still flag it (test
both directions — GATE-OPTIMALITY DUTY). **ROI:** high and cheap. **Confidence:** high (root cause proven at
`data_vitals.py:102` and `:166-177`). **Retirement:** none. **Interaction:** `"DEAD -- FAILOVER"` should be
renamed until a failover exists (F19), or the string is a lie by itself.

### O4 — Replace the MT5 cross-asset feed with free Linux-native primaries, adjusted for distributions (F3+F7+F8+F9).
**Exactly what:** retire `ingest_history.py` / `ingest_multiasset.py` / `ingest_etfs.py` as the cross-asset
route. Land FX, metals, energy, indices and ETFs from free primary publishers with **total-return** or
explicit dividend data; keep the existing hive writer and `validate_bars` (both good). Record in the universe
map that Stooq is host-blocked, with the graded residual gap FREE-FIRST requires.
**Why:** 88 instruments with up to 26 years of history are dead and unrestorable on this host, and 5 of them
are actively misleading. **Evidence:** `import MetaTrader5` → `ModuleNotFoundError` on Linux; `find data -name
"stooq*"` → 0; `SHY` cumulative price return **−5.30 % over 6.23 y**. **Benefit:** restores the orthogonal
axis class the desk's own theory of edge depends on, and removes a systematically-biased dataset.
**Complexity:** medium (new fetchers) — but the lake, schema and validation layers already exist.
**Validation:** `SHY` total return must come out positive over 2020-03→2026 or the source is still price-only;
FX end-date must equal T-1. **Failure modes:** a new single vendor recreates F18 — wire two from the start.
**Alternatives:** reinstate a Windows MT5 host (rejected: reintroduces a demo-CFD price source, a Windows
dependency, and 100 % vendor concentration). **ROI:** high. **Confidence:** high on the diagnosis, medium on
which free source is best. **Retirement condition:** if a free adjusted source cannot be found, log the
failed search with its graded residual gap — do **not** silently keep the price-only series.

### O5 — Land free 1h/4h crypto klines at full depth (F6). ⚡
**Exactly what:** pull Binance/Bybit/OKX free historical klines at 1h (and 1m where cheap) for the 277-symbol
universe into the existing bronze layout as new timeframe partitions.
**Why:** the entire 1m–4h band is empty, so the whole hourly signal family — the band where funding-cycle,
basis and microstructure effects live — cannot be backtested at any length. **Evidence:**
`ALL 277 symbols TIMEFRAME dirs: {'D1': 277, 'H8': 10}`. **Benefit:** unlocks a signal family the desk cannot
currently test, and gives the 10-day moat (F5) a multi-year context series to be joined against.
**Complexity:** medium (bulk download + partitioning; `dl_oi_ls_universe.py` is a working template with real
gap-repair). **Validation:** ≥3 years of 1h bars for the top 30 symbols, hourly completeness ≥99 % measured by
O2's job. **Maintenance:** low once the daily incremental exists. **ROI:** high. **Confidence:** high.
**Interaction:** raises the value of O2 and O7. **Horizons:** 1m new hypothesis space; 1y a genuinely
multi-regime intraday sample.

### O6 — Turn on dataset versioning: the code is written and has zero rows (F11). ⚡⚡
**Exactly what:** call `register_dataset_snapshot` on every lake write and stamp every screen/backtest with
`ReproducibilityStamp`; stop `existing_data_behavior="delete_matching"` from destroying prior partition
contents without a recorded predecessor.
**Why:** no result on this desk can be reproduced, and L1.4's mandated predicted-vs-realised investigation is
impossible without knowing which data a prediction used. **Evidence:** `snapshots=0 / trials_ledger=0 /
research_runs=0 / config_versions=0` across all 8 SQLite DBs; `libs/data/lake.py:59`; no content hash on any
of 26,315 parquet files. **Benefit:** the largest compounding multiplier here — it raises the evidentiary
value of *every future experiment* and stops silently devaluing past ones. **Complexity:** low-medium (the
libraries exist and are tested; this is call-site wiring). **Validation:** re-run a screen twice and confirm
identical stamps; mutate a partition and confirm the stamp changes. **Maintenance:** low. **ROI:** highest on
a 1y horizon. **Confidence:** high. **Retirement:** never.

### O7 — Build silver/gold once, for real (F23). ⚡
**Exactly what:** run `build_silver`/`build_gold` over the bronze estate on a schedule so a cleaned series and
a feature table exist on disk instead of being re-derived per script.
**Why:** every experiment currently re-does cleaning, so experiments are not comparable; and it is the reason
`quality.py` has never seen production data. **Evidence:** `ls data/lake/` → `bronze` only; `build_silver`
callers = tests only. **Benefit:** comparability across screens plus a reusable feature layer.
**Complexity:** medium. **Interaction:** subsumes part of O2 and multiplies O5. **ROI:** high on 3m+.
**Confidence:** medium-high (needs a decision on what "silver" means per asset class). **Retirement:** none.

### O8 — Give the impact model a size grid that actually consumes the book (F24).
**Exactly what:** extend `sizes_usdt` to $10k/$50k/$250k and re-fit against the recorded moat depth shards;
require `exhausted_frac > 0` in at least one bucket per symbol or report the symbol as *impact-unmeasured*
rather than *cheap*.
**Why:** `exhausted_frac == 0.0` in all 300 cells means impact is unmeasured and capacity is asserted, so no
scaling decision has evidence. **Benefit:** makes L1.5 checkable at size and finally gives the 6 GB moat a
consumer. **Complexity:** low-medium (replay against data already on disk). **Validation:** BTCUSDT's curve
must become non-flat. **ROI:** medium-high, and it rises the moment capital does. **Confidence:** high.

### O9 — Wire the second and third feeds that already exist (F10, F18).
**Exactly what:** call `libs/data/multiexchange.py:34,59` (`fetch_bybit_funding`, `fetch_okx_funding`) and
add a daily reconciliation of Binance vs Bybit vs OKX closes per symbol-day, on the model of the *existing*
`batch_coinmetrics_screen.json` verification block (`median_abs_err_vs_binance_close_bps: 13.18`, n=3268).
**Why:** `cross_validation_available: {False: 44}`, and Binance is the USD reference leg of every premium
composite — a correlated failure across the whole family. **Complexity:** low (functions written, unused).
**Validation:** a divergence series exists and pages above a threshold. **ROI:** medium-high.
**Confidence:** high.

### O10 — Convert the 17 `catalogued` sources, highest-mechanism-prior first (F26); normalize the grade field to an enum so a gate can count them (F13).
**Why:** 53 % of the catalogue is unconverted and, because grades are prose, §33's conversion pressure cannot
even see it. **First two by mechanism prior:** `51-ethpandaops-xatu` (block first-seen + MEV relay, free
Parquet from 2023-03 — real microstructure with a stated mechanism) and `55-leaderboards-copytrading`
(venue-published identified-trader positioning). **Complexity:** medium per source; the enum is trivial.
**Validation:** each lands in bronze *and* returns a Stage-A verdict in the same run, per SCREEN-ON-DISCOVERY;
negative screens graveyarded with their reason. **ROI:** medium-high, and it is the only item here that
directly raises the data-to-alpha conversion ratio. **Confidence:** medium.

### O11 — Assert expected row counts and end-dates on every read path.
**Why:** silent truncation is the desk's dominant undetected failure mode and I found three instances in one
audit (F1, F2/F3, F9). No read path anywhere asserts what it expected to get. **Exactly what:** a
`read_bars`-level check that the returned frame's `max(timestamp)` is within tolerance of the caller's
declared as-of, raising otherwise. **Complexity:** low. **ROI:** high relative to cost; it converts a whole
*class* of silent failure into a loud one. **Confidence:** high (the class is empirically demonstrated).

### O12 — Own the orphans (F20) and schedule the abandoned collectors (F22).
**Exactly what:** write and commit producers for the six orphan datasets or formally graveyard them with the
mechanism of death; schedule `pull_cme.py` (1.1 GB, 9 d stale, no automation); decide `collector_author.py` —
wire it or retire it.
**Why:** one of two live mechanisms is fed by a non-regenerable Wayback replay; the largest non-moat dataset
has no refresh. **Complexity:** low-medium. **ROI:** medium. **Confidence:** high.

### Interactions worth stating
- **O3 gates O2.** Adding a second alarm on top of an always-wrong one wastes the fix.
- **O6 multiplies everything after it.** Snapshot before the O4/O5 backfills, or those become another
  unreproducible import.
- **O1 gates O10.** The organs that would convert the catalogue are the ones that are dead.
- **O5 and O8 both make the moat useful**, from opposite directions — one gives it context, the other gives
  it a consumer.

### Opportunity cost of not fixing, 1 year
- **F16 (dead discovery tier):** the desk's own evidence prices this. 420 price-family hypotheses → 0
  survivors; one new axis screened in ~an hour → IC +0.148. Acquisition capacity at zero for a year is
  therefore not "slower research" — it is **the removal of the only channel that has ever produced a
  survivor.** Highest opportunity cost in this report by a wide margin.
- **F11 (no versioning):** a year of experiments whose results cannot be reproduced or re-attributed. The
  loss is not the experiments — it is that L1.4 reality-anchoring stays impossible, so the desk cannot learn
  from divergence.
- **F2/F3 (stale majors + dead cross-asset):** a year of BTC/ETH research on a truncated sample and no
  orthogonal-axis research at all, on 88 instruments the desk already owns.
- **F8 (price-only bond ETFs):** every rates/credit conclusion biased one way by 3–6 %/yr — and if `SHY` was
  ever the risk-free comparator, a **negative** T-bill hurdle, i.e. L1.5 enforced backwards.
- **F25 (8 idle forward slots):** at ~40 days minimum per clock, eight empty slots is roughly **70 lost
  forward-validation-months per year** — the scarcest resource on the desk, since it is the only one that can
  promote anything to capital.

---

## 4. WHAT WE TEST NEXT

Each item: the experiment, its success criterion, and its retirement condition.

**T1. Prove the health monitor is fixed in both directions.** Re-run `scripts/data_vitals.py` after O3.
*Success:* all 8 current DEAD verdicts clear, **and** a deliberately-staled copy of a live file still scores
DEAD. *Retire:* if the false-positive rate cannot be driven to 0 without also losing true positives, the DQS
product is the wrong design — replace it with per-component thresholds rather than tuning it.

**T2. Measure the real lag distribution across the whole estate and publish it as a time series.** Run O2's
walker once, immediately, over all 277 crypto symbols + 88 cross-asset + 80 moat symbol-venues.
*Success:* it independently reproduces F2 (BTCUSDT lag 39 d), F3 (FX lag 41–55 d) and F5 (fut median symbol
72 % hourly completeness) **without being told to look for them**. *Retire:* if it cannot reproduce these
three, the walker is not measuring what this audit measured and one of us is wrong — resolve before trusting it.

**T3. Falsify the price-only conclusion on the equity lake.** Compare the lake's `SHY`/`TLT` series against
any independent total-return source over the same window. *Success:* the gap equals the known distribution
yield (≈4 %/yr for SHY), confirming F8 and quantifying the correction. *Retire:* if the gap is ~0, F8 is
wrong and the series is adjusted — retract F8 and investigate why `SHY` still shows −0.87 %/yr.

**T4. Test whether the moat's universe expansion is look-ahead contaminated.** For the 10 symbols added on
2026-07-22, compare their pre-addition liquidity rank to the 20 originals. *Success:* if the added symbols were
*not* systematically higher-activity beforehand, the panel is safe for cross-sectional work and we record that;
if they were, every cross-sectional study on `fut` must exclude the pre-expansion window. *Retire:* n=10 may
be too small to conclude — if so, record it as an unresolvable and mandate a fixed universe going forward.

**T5. Verify the discovery organs actually run, by artifact.** After O1, wait one timer cycle.
*Success:* `data/cro_ai_logs/dataaxis_*.log` exists at >1500 B, `systemctl is-failed quant-dataaxis` returns
non-failed, and `quant-frontier` exits **non-zero** when a region fails. *Retire:* if credit exhaustion
recurs with an independent route in place, the constraint is real spend, not configuration — then the
honest move is to price the dig and take it to the principal as a budget decision, **not** to quietly reduce
cadence (which L1.8 forbids and which the TIMIDITY clause scores as a defect).

**T6. Open the moat and validate its contents.** Sample 200 shards across symbols/hours/venues; check
well-formedness, duplicate timestamps, monotonicity, level counts, and tz handling of the bare-epoch `t`.
*Success:* <0.1 % malformed and no duplicate-timestamp clusters. *Retire:* if malformation is material, the
6 GB asset needs a repair pass before any research uses it — and that finding outranks O8.

**T7. Extend the impact grid and see the curve bend.** Re-fit the cost model at $10k/$50k/$250k against
recorded depth. *Success:* `exhausted_frac > 0` in ≥1 bucket for every symbol and BTCUSDT's curve becomes
monotonically rising. *Retire:* if even $250k does not touch BTC's book, report BTC impact as *below
measurement threshold at our capital* — which is a legitimate and useful answer, unlike the current
0.001 bps constant.

**T8. Snapshot-then-mutate, to prove versioning works.** After O6, register a snapshot, rewrite one month
partition, re-read. *Success:* the stamp changes, the predecessor is recoverable, and a re-run of the same
screen against the old stamp reproduces the old numbers exactly. *Retire:* if `delete_matching` cannot be
made non-destructive without a lake rewrite, escalate — that is an architecture decision, not a patch.

**T9. Convert two catalogued sources end-to-end as a rate measurement.** Take `51-ethpandaops-xatu` and
`55-leaderboards-copytrading` through ingest → Stage-A screen → verdict in a single run.
*Success:* both land in bronze with declared timestamp alignment and both return a logged verdict (positive
*or* negative — negatives are first-class). *Retire:* if a single source takes more than one run to convert,
the SCREEN-ON-DISCOVERY duty's "same run" requirement is mis-scoped for this class of source and should be
amended with evidence rather than silently violated.

---

## APPENDIX A: SCORES

| metric | value | basis |
|---|---|---|
| `current_capability_pct` | **34 %** | Architecture is strong (hive lake, tz-explicit parquet, `validate_bars`, PIT join, leakage detector, one genuinely self-repairing collector, a live 100 %-complete Bybit tape). Operation is not: 71 % of crypto symbols stale, 88 cross-asset instruments dead, 5/5 discovery organs down, 8/8 alerts false, snapshots/lineage/silver/gold at zero rows. |
| `practical_ceiling_estimate` | **85 %** | Reachable with free sources and code already in the repo. Not 100 %: some gaps are genuinely destroyed at source (pre-recorder L2 diffs, bitFlyer pre-today ticks) and are correctly documented as such. |
| `ceiling_gap` | **51 pts** | The majority is *wiring and monitoring*, not new capability — which is why the ROI is high and the cost is low. |
| `opportunity_cost_1y` | **VERY HIGH** | Dominated by F16: acquisition capacity at zero removes the only channel that has produced a survivor (420 price hypotheses → 0; one new axis → IC +0.148). Then F11 (a year of unreproducible work) and F25 (~70 lost forward-validation-months). |
| `confidence` | **HIGH** on findings, **MEDIUM** on rankings | Every finding carries a command and its output, and several are cross-confirmed two ways (content end-date *and* mtime; verdict *and* root-cause line number). Rankings depend on cost estimates I did not implement against. |
| `unknown_unknown_score` | **HIGH (7/10)** | I found silent truncation three times in one pass and expect more: no read path in the repo asserts an expected row count or end-date. 240 `data/` artifacts, ~12 audited against source. The moat's contents have never been opened by anything. |
| `info_gain_if_investigated` | **VERY HIGH** | T2 alone (one walker run) would independently confirm or refute three of the top findings and produce the desk's first data-quality time series. |
| `expected_alpha_contribution` | **HIGH, mostly indirect** | Little of this creates alpha directly. F8 *removes* a systematically wrong answer; F3/F5/F6 restore the axes and frequency bands where alpha could be found; F16 restores the organ that finds new axes at all. |
| `expected_compounding_contribution` | **VERY HIGH** | O6 (versioning), O2 (quality history), O7 (silver/gold) and O11 (row-count assertions) each raise the value of every future experiment. Three of the four are wiring for code that already exists and is already tested. |

### CEILING EXPANSION — what defines the 85 %, and what would move it
The ceiling is set by **organizational** constraints, not technical ones, and that is the important finding
here. Nothing in this report is blocked by compute, cost, or unavailable data. The binding constraints are:
(1) an LLM credit seat with no independent fallback, which caps *acquisition* at zero (F16); (2) a
detected→fixed loop that does not close — `quota_watch` diagnosed 100 % organ death 8 days ago, the prior
sweep found the orphan datasets, `research_memory` recorded the FX coverage gap on 2026-07-26, GAP #28 has
been queued since 07-18, and all four are unfixed; (3) written-but-unwired code, which is the single most
common shape in this audit — `require_verified`, `register_dataset_snapshot`, `ReproducibilityStamp`,
`build_silver`, `quality.detect_missing_bars`, `fetch_bybit_funding`, `fetch_okx_funding`,
`collector_author.py`. **Eight capabilities exist as tested code with zero production callers.**

That last item is what makes the 85 % estimate itself too low. If the desk's real bottleneck is *wiring
existing code* rather than *building new capability*, then the ceiling is bounded by attention, not
engineering — and a single mechanism that refuses to let a capability be merged without a production caller
(a "no dead capability" gate, the natural sibling of §36's NO UNGOVERNED ARTIFACT) would move the ceiling
above 85 % permanently. That is a **process** lever with a **data** payoff, and it is the highest
second-order-compounding item (L1.15) I can identify in this subsystem.

### The six perspectives — coverage map
| perspective | findings |
|---|---|
| **INTERNAL** (measured, not configured) | F1–F6, F16, F17, F19, F23–F25 — every one measured from an artifact or a command, never a config file |
| **EXTERNAL** (what another top team would do) | O2 (quality SLA per series with history), O6 (content-addressed snapshots + run stamps), O9 (multi-venue reconciliation), O11 (row-count assertions on every read). All four are table stakes elsewhere; all four are absent here |
| **FUTURE** (2–3 yr compute/AI/data) | O5+O7: with cheap storage and compute the natural design is full intraday depth for the whole universe plus a materialized feature layer — the desk's 10-day/daily barbell (F6) is a 2020-era shape. `collector_author.py` (LLM-authored collectors, F22) is the right 2026+ idea, built and never run |
| **CONTRARIAN** (assumptions wrong) | **F8 is the sharpest — a dataset producing confidently wrong answers, not noisy ones.** F24 (a model named for impact that measures spread). F1 (a monitor whose alerts are 100 % false). F5 (`dqs 1.000 OK` on a 10-day, 40 %-missing asset). Also tested and **not** found: parquet tz handling is genuinely correct (S2), and the DQS constant-term removal was genuinely the right call (S4) |
| **GREENFIELD** | Keep: the hive lake, `validate_bars`, `libs/core/time.py`'s naive-datetime refusal, `pit.py`, `leakage_detector.py`, `dl_oi_ls_universe.py`'s gap-repair pattern, the recorders. Discard: the entire MT5 path (F7), `data_registry.json` (hand-written, no writer, 5 % census), prose-graded universe entries (F13). Build first: versioning (O6) and the quality walker (O2) — both before any new data lands. Historical baggage is concentrated almost entirely in the MT5 lineage |
| **FRONTIER** (recently possible, unexploited) | The 17 unconverted `catalogued` sources (F26) are the frontier list and are dated: `51-ethpandaops-xatu` (free Parquet, mainnet from 2023-03), `52-mev-classification` (zeromev per-tx classes), `48-reddit-full-corpus` (Arctic Shift + PullPush post-API-lockdown), `49-crypto-social-firehoses` (Farcaster hubs, Bluesky firehose — both recent), `59-competition-archives`. Every one free, route documented, never ingested. The organ that would ingest them is dead (F16) — which is why F16 outranks everything |

### Battery moves run this audit, and what each produced
| move | produced |
|---|---|
| **CONTINGENCY BEFORE FAILURE** | F7 — MT5's replacement was never named; six weeks later still unnamed. F16 — the LLM fallback chain shares one seat and its independent branch is gated on a missing file |
| **ADJACENCY** | F1 — `data_vitals.py:145-149` records this exact bug class being fixed once; the sibling path (`median gap == 0`) was never swept, so `defi_lending` is *still* scored DEAD. The lesson was recorded and the defect was not closed |
| **CONFIG VS OUTCOME** | F2, F3, F9, F16, F17, F23 — six findings where a green config had zero output. F9 is the purest: code present, run yesterday, siblings succeeded, **zero bytes ever produced** |
| **REGRESSION SWEEP** | Nothing was changed (read-only audit), so nothing was made worse. Stated explicitly rather than skipped |
| **COST INVERSION** | F7/F9 — the paid/gated path (MT5 demo broker, Databento CME) has free primaries; one is already in the repo and host-blocked, and the block was never recorded |
| **GENERALISE THE RULE** | F19/F23 — `quality.py`'s gap detection is written for the MT5 bar path and is blind to jsonl, the moat, and the hourly tier. F1's `MAX_ROWS` truncation is duplicated in `measurement_gate.py:73` / `data_vitals.py:91` as the identical naive-tz coercion (F14) |
| **AUTONOMY CHECK** | F16 — the model-fallback recovery was configured 2026-07-24 and has **never been seen to work**; the `[ -f "$_BRAIN_KEYFILE" ]` branch is unreachable |
| **NEGATIVE SPACE** | F27 — 10 never-collected capabilities, each with its proving check. The one I did not expect: **the health artifacts keep no history**, so no data outage is reconstructible and the RATCHET CHECK cannot apply to data quality at all |
| **SCOPE THE NEGATIVE RESULT** | F9 — probed 8 Stooq symbols; identical 796-byte HTML on all 8 proves a **host-level gate**, not a symbol problem. The correct scope is "this route is blocked", not "free cross-asset data is unavailable" |
| **RATCHET CHECK** | Cannot be applied to data quality — there is no recorded floor to ratchet (F27). That absence is itself the finding, and O2 is the fix |

### Honest limits of this audit
- Read-only: I ran no collector, so every "would fix" is inference from code and artifacts, not from a
  repaired run.
- I audited ~12 of 240 `data/` artifacts against their sources. The 12 were chosen where confidence was
  lowest; the remaining 228 are unexamined and F1/F24 both showed that authoritative-looking artifacts can be
  wrong.
- I did not open a single moat shard (T6). The desk's largest asset is validated by file *presence* only.
- U1, U2, U6 and U7 are named and unresolved rather than papered over.

### Governance obligations this report creates
Per §35 and §41 every finding above needs a `GAP_REGISTER` row (`scripts/track_findings.py`) and every O-item
a `scripts/recommendations.py add` row with a disposition inside 24 h — build, reject with a substantive
reason, or schedule with an enforced due date. This audit is read-only and did **not** create those rows; they
are owed. Highest-tier first: **O1 (T1 defect-closer — a permanently-failing organ tier), O3 (a
permanently-firing false gate), then O2/O6.**

---

## APPENDIX B: environment of this audit
Read-only sweep from `/home/quant/quant-platform`, `2026-07-30T02:12Z → 03:0xZ`. No code, state, cron, systemd
unit or git object was modified; the only file written is this report. Python via `.venv/bin/python`
(pandas 2.3.3, duckdb 1.5.3) — note that system `python3` has no pandas, so any inspection command in this
report must be run with the venv interpreter to reproduce.

Concurrent modifications visible in `git status` during the sweep (`data/decision_ledger.json`,
`docs/GAP_REGISTER.md`, `docs/research/conversion_record.json`, `docs/research/recommendation_ledger.json`,
`scripts/max_audit.py`) were produced by the desk's own cron organs — `daily_research_cycle.py` was running
throughout (`ps` showed it live at 02:16, 16 m into its 66-step sequence) — **not by this audit.**
