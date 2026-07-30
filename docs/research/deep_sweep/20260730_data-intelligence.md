# WEEKLY DEEP COLD AUDIT — SUBSYSTEM: data-intelligence
**Date:** 2026-07-30 · **Mode:** read-only · **Doctrine:** v2 (principal-ratified 2026-07-24) + Exhaustion Mandate (2026-07-28)

> STATUS: **IN PROGRESS** — skeleton written first per COMPLETION CONTRACT §1. Findings appended incrementally as verified.

## SCORES (filled at end)
| metric | value |
|---|---|
| current_capability_pct | TBD |
| practical_ceiling_estimate | TBD |
| ceiling_gap | TBD |
| opportunity_cost_1y | TBD |
| confidence | TBD |
| unknown_unknown_score | TBD |
| info_gain_if_investigated | TBD |
| expected_alpha_contribution | TBD |
| expected_compounding_contribution | TBD |

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

## 2. WHAT WE DON'T KNOW (ignorance ledger)

_pending_

## 3. WHAT COULD MATTER MOST (ranked opportunities)

_pending_

## 4. WHAT WE TEST NEXT

_pending_

---

## APPENDIX: raw evidence log

_pending_
