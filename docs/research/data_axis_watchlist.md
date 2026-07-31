# Data-Axis Watchlist (Free-Data-Alternatives mission)

_Companion to `data/data_universe_map.json`. Session summaries logged here chronologically per
FREE_DATA_ALTERNATIVES_SPEC. This is the operator-visible "what did the data digger find" record._

---

## SESSION SUMMARY — 2026-07-19T00:00:00+00:00 (first manual run, operator-triggered)

- **Queries used:** 12 / 12 web searches + 7 WebFetch deep-dives (WebFetch does not count against
  the search budget). Coverage hit: Korean venues (Upbit, Bithumb), Japanese venues (bitFlyer,
  Coincheck), OKX official portal, Tardis/Glassnode-CryptoQuant/Kaiko vendor-replacement paths,
  stablecoin mint/burn + exchange-label reconstruction, and community data lakes (Kaggle/HuggingFace).
- **Sources graded this session:** 17 new/updated entries in `data/data_universe_map.json`.
  - **verified-clean (URL opened + directly confirmed):** 3 — OKX historical-data portal, AWS
    Public Blockchain Data (registry.opendata.aws), the desk's own recorder (pre-existing).
  - **needs-monitoring (corroborated, not diffed vs ground truth):** 7 — Upbit historical-data
    portal, bitFlyer getexecutions+self-record mechanism, stablecoin mint/burn self-computation,
    eth-labels, plus 3 pre-existing entries left unchanged.
  - **UNVERIFIED (found, not confirmed — do not adopt):** 6 — Bithumb spot API, Bithumb Futures
    API, tradezon/cex-list, the Glassnode/CryptoQuant Dune-replacement claim, Kaggle btcusdt
    dataset, HuggingFace sebdg/crypto_data.
  - **destroyed-at-source (honest negative/residual):** 1 new — Coincheck (no free bulk historical
    archive found this session); plus 2 vendor-residual notes added (Kaiko's index methodology,
    CryptoQuant's proprietary indicator formulas).
- **Best vendor-replacement finding:** stablecoin mint/burn reconstruction (USDT/USDC Transfer-events
  off the canonical treasury contracts, via the desk's existing free RPC fallback chain OR the AWS
  Public Blockchain Data lake) — independently corroborated by a Federal Reserve FEDS Note that uses
  the *same* AWS dataset for the *same* analysis. Strong non-crypto-native validation of both the
  mechanism and the source. Mechanism is confirmed; the desk has not yet run the query (research-only
  under the freeze).
- **Best regional-venue finding:** Upbit's official Historical Market Data portal — genuine
  exchange-native CSV/ZIP archive (candles from 2022-05-01, 1m from 2023-07-01, trades separately),
  a real Korean-venue analog to data.binance.vision. Bithumb and Coincheck, by contrast, turned up
  **no comparable free bulk archive** this session — logged honestly as gaps, not painted over.
- **Honest verdict:** a genuinely new source-class was found (AWS Public Blockchain Data, see
  SEARCH-SPACE EXPANSION below) and one regional-venue exchange-native win (Upbit). But roughly a
  third of what was found this session graded UNVERIFIED or worse — the Glassnode/CryptoQuant
  "free replacement via Dune" claim in particular is a secondary-source assertion, not a verified
  diff, and is explicitly NOT presented as adopted. Bithumb and Coincheck (2 of 4 mandatory regional
  targets) came back empty-handed on bulk archives — a real result, not a search failure to hide.

### STEP 0 — Watchlist review
No prior data-axis watchlist exists (this is this mission's first run). Nothing to promote/hold/drop.

---

## SOURCE CARDS (graded; full genealogy in `data/data_universe_map.json`)

### 1. Upbit Historical Market Data portal — grade: needs-legitimacy-review (data itself verified-clean; commercial-use licence is the open question, re-graded 2026-07-25) [§33: deferred(2026-08-15) tier:3]
> **§33 DISPOSITION 2026-08-15 — DATED DEFERRAL ON A HUMAN RULING. Unlike bitFlyer, this licence
> HAS been read; the blocker is not access, it is AUTHORITY. An agent may not self-approve it.**
> - **THE QUESTION, STATED SO THE PRINCIPAL CAN ANSWER IT IN ONE LINE:** Upbit's usage guide
>   explicitly PERMITS *"use for non-commercial and private purposes such as developing one's own
>   strategy and backtesting"* and *"storing and utilizing data on a personal PC"*, and explicitly
>   PROHIBITS *"commercial use, redistribution, processing, and sale"* including *"services or
>   platforms to help others make investment decisions"*. **A prop desk trading only its own
>   capital, redistributing nothing and advising no one, sits precisely on that line.** Research
>   and backtesting read as permitted; deploying a derived signal to trade own capital is the
>   contested half. Two rulings are possible and both are workable — research-only, or full use.
> - **THIS CARD DEFERS RATHER THAN CONVERTS BY ITS OWN INSTRUCTION** ("DO NOT BUILD A COLLECTOR
>   YET"). Overriding that to book a conversion would be the §33 failure mode wearing a compliance
>   costume: an UN-DEPLOYABLE signal is worthless now, not later (§13.1).
> - **NOT LAUNDERED THROUGH THE LICENSED ALTERNATIVE EITHER.** Tardis covers `upbit` since
>   2021-03-03 with a ToS that permits internal research, and converting through it would produce a
>   real artifact — but it would convert CARD 6, not this one. Pointing this card at a Tardis
>   artifact is exactly the fuzzy-credit laundering §33.16 exists to stop.
> - **COST OF WAITING IS ZERO, unlike card 3:** the portal is a static archive back to 2017-10-24
>   and destroys nothing while the ruling is pending. That is why this date is the monthly
>   governance window (2026-08-15) and card 3's is 14 days.
> - **UNBLOCKING STEP:** principal answers "research-only" or "full use" on the personal-vs-
>   commercial scope. **Routed to GAP_REGISTER #67 (shared legitimacy-ruling row with the CC BY-NC
>   question — one ruling session, two answers).**
>
> _Pre-deferral verification notes below (unchanged, still valid):_
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). File downloaded, checksum
> verified, values ground-truthed against the live API. 4 of 5 factual claims in the old card were
> WRONG. The blocker has MOVED from "is the data real?" to "are we allowed to use it?"**
>
> **DIRECT FILE PATHS FOUND** (the old card's "JS shell, no detail" blocker is solved — the real API
> was extracted from the portal's webpack chunk `sri-v2-chunk-gJZ6LcBG.js`):
> - Listing API (200, JSON, unauthenticated): `https://crix-data-api.upbit.com/api/v1/market-data/listing?prefix=`
> - File host (200, application/zip): `https://crix-data.upbit.com/<key>`
> - Tree: `{candle|trade}/<MARKET>/{daily|monthly}/<interval>/<year>/` → `.zip` + `.zip.checksum`
> - Intervals: `1s 1m 3m 5m 10m 15m 30m 60m 240m day week month`; **786 markets (KRW 270, BTC 308, USDT 208)**
> - Integrity: published SHA256 `.checksum` sidecars — one verified, **computed hash matched exactly**
>
> **REFUTED CLAIMS (4 of 5):**
> 1. **"candle depth from 2022-05-01" → WRONG. Actual: 2017-10-24** (Upbit's launch day), confirmed
>    by Upbit's own guide string and by the 2017 bucket files.
> 2. **"1m from 2023-07-01" → WRONG, AND IT WAS A TRANSLATION ERROR. 1m goes back to 2017-10-24.**
>    The source notice says **초봉 = SECOND-bars (1s)**, which someone read as 분봉 (minute-bars).
>    Only 1s starts 2023-07. Opened the 2017 1m file: 10,232 real minute bars,
>    2017-10-24T00:00:00 → 2017-10-31T23:59:00. **A 5.7-year understatement of the best free
>    Korean-venue dataset — caused by one mistranslated Korean character.**
> 3. The **2022-05** date is real but belongs to a DIFFERENT product — **trade/tick data**, not
>    candles. The old card conflated the two.
> 4. **"daily 14:00 KST upload" → WRONG. Observed 01:00 UTC (10:00 KST)**, five consecutive
>    `lastModified` stamps. Korean **매일 14시 전까지** = "BY 14:00" — a DEADLINE, misread as a
>    schedule. Cadence is T+1 and complete (205 files for 205 elapsed days of 2026).
> 5. **"license unstated" → WRONG. It is explicitly and restrictively stated** (see below).
>
> **VERIFY-DON'T-TRUST: DONE — the old card's own diff plan is now CLOSED.** `KRW-BTC_candle-day_201710.csv`
> vs `api.upbit.com/v1/candles/days` → **all 8 overlapping days matched to the last decimal on
> O/H/L/C/volume.** Public REST candle API works unauthenticated, `count` max 200, `to=` pagination
> reaches 2017-10-24, self-reported limit `600/min, ~10/sec` for the candles group.
>
> **⚠️ LICENSE — CHARTER §13 DECISION REQUIRED, NOT A TECHNICAL GATE. DO NOT BUILD A COLLECTOR YET.**
> Upbit's "Copyright and usage restrictions" guide states data may be used **"only for personal
> purposes"** and that the ToS **"prohibit the use of such data for commercial use, redistribution,
> processing, and sale."** Prohibited acts explicitly include *"Using it for services or platforms to
> help others make investment decisions"* and *"all actions that involve third-party use, profit
> generation, or violation of laws... beyond personal use."* Cutting the OTHER way, explicitly
> PERMITTED: *"Use for non-commercial and private purposes such as developing one's own strategy and
> backtesting"* and *"storing and utilizing data on a personal PC."* **A prop desk trading its own
> capital sits exactly on that line. This is a human/legal ruling, not an agent call** — routed to
> the legitimacy queue, deliberately NOT self-approved.
> **LICENSED ALTERNATIVE ALREADY IN HAND:** entry 6 confirms **Tardis covers `upbit` since
> 2021-03-03**, and Tardis's ToS explicitly permits internal research use. For verification/diffing
> purposes the desk can use the Tardis first-of-month upbit files with a clean licence while the
> Upbit-portal question is decided.
>
> **TWO HAZARDS THE OLD CARD NEVER FLAGGED:**
> - **SURVIVORSHIP BIAS, STRUCTURAL:** guide states *"Data for delisted coins is not provided."*
>   Every backtest on this dataset is survivorship-biased by construction — a research-VALIDITY
>   defect, not a plumbing one. (Compare the desk's own survivorship-aware L1 commit-velocity test.)
> - **FILES ARE MUTABLE:** *"data for the relevant period may be modified and re-uploaded without
>   prior notice."* Checksums verify a download; they do NOT pin a version. Archive on ingest.
> - `www.upbit.com/robots.txt` = `Disallow: /` (allowlists Googlebot/Yeti/etc). The *file* hosts
>   serve no robots.txt, so a direct-file collector never touches a disallowed host — but note it.

_Superseded original grading below (kept for the record):_
### 1-OLD. Upbit Historical Market Data portal — grade: needs-monitoring
- **Provides / replaces:** Korean-venue klines + trade/execution history, CSV/ZIP. Serves the
  regional exchange-native dump target; would substitute for a Korean-venue leg of any consolidated
  vendor feed (Kaiko-class).
- **Provenance:** WebFetch'd `https://www.upbit.com/historical_data/main` (JS shell, no detail) and
  `https://www.upbit.com/service_center/notice?id=5419` (confirmed candle+trade categories exist in
  the notice's own text). Cross-referenced against the WebSearch summary describing CSV/ZIP format,
  daily 14:00 KST upload, candle depth from 2022-05-01 (1m from 2023-07-01).
- **Verify-don't-trust:** NOT diffed vs ground truth this session (no file actually downloaded).
  Verify plan: pull one BTC-KRW daily CSV, cross-check close prices for an overlapping date against
  Upbit's live ticker API (or a third-party aggregator) before any pipeline trusts it.
- **Genealogy:** URL above · method = official dev-center download page + separate paginated REST
  candle API · license unstated in fetched excerpt, check Upbit ToS before redistribution · cadence
  daily · failure modes: 1m-candle depth is shorter than other intervals; portal is JS-rendered so
  automated scraping needs the direct file paths, not the HTML shell.
- **Grade: needs-monitoring.**

### 2. OKX official historical-data portal — grade: verified-clean
- **Provides / replaces:** tick trades (since 2021-09), OHLC candles (since 2023-07), funding
  (since 2022-03), L2 order book (since 2023-03), borrow rates (since 2021-12). Replaces/corroborates
  the previously-logged "OKX public dumps / third-party mirrors" entry with an **official first-party
  source**.
- **Provenance:** WebFetch'd `https://www.okx.com/en-us/historical-data` directly; confirmed category
  list and start dates in the page's own text.
- **Verify-don't-trust:** file format and auth requirements not disclosed on the landing page itself —
  confirm at the actual per-category download link before building a collector. Diff plan: OI/funding
  history vs the desk's own OKX-collected values once the connector exists.
- **Genealogy:** cadence/coverage as above · license = OKX site terms (not restated on this page) ·
  failure modes: non-uniform start dates per data type (do not assume uniform depth).
- **Grade: verified-clean** (portal existence + categories), pending format/auth confirmation.

### 3. bitFlyer getexecutions + self-recorded candles — grade: needs-legitimacy-review (mechanism verified-clean, destroyed-at-source residual confirmed; ToS host WAF-blocked so licence is unread, re-graded 2026-07-25) [§33: deferred(2026-08-09) tier:2]
> **§33 DISPOSITION 2026-08-09 — DATED DEFERRAL, BLOCKER NAMED. A THIRD AND FOURTH INDEPENDENT
> ROUTE TO THE ToS FAILED 2026-07-26. The licence is genuinely unread, so no verdict is written:
> fabricating one would be exactly the hand-wave §13 exists to stop.**
> - **ROUTE 3 — A DIFFERENT EGRESS ENTIRELY (the specific thing routes 1-2 could not test):** the
>   ToS was requested from an off-VPS fetcher, i.e. a different IP and a different network path.
>   `bitflyer.com/en-jp/terms` → **403**; `bitflyer.com/ja-jp/terms` → **403**. This kills the
>   "it is only this VPS's IP" hypothesis — the block is not egress-specific.
> - **ROUTE 4 — ALTERNATE HOSTS:** `lightning.bitflyer.com/terms` → 404, `.../docs/term` → 404,
>   `bitflyer.com/en-jp/api-terms` → connection dropped, `bitflyer.jp/en-jp/terms` → does not
>   resolve. The reachable docs page was re-read in full and carries **rate limits only, no licence
>   language** — so the field cannot be closed from any surface that answers.
> - **NO ATTEMPT WAS MADE TO DEFEAT THE BLOCK** (no proxy, no reader-service laundering, no UA
>   games beyond a plain browser UA). §13 is a hard boundary, not a hurdle.
> - **STATE: nothing prohibits use, nothing permits it.** That fails §13's "clear permitted-usage
>   licence" test, so a forward recorder is NOT started. Four routes have now failed (direct VPS,
>   Wayback/CDX, off-box egress, alternate hosts) — this is a documented search that failed, which
>   is the evidence §28 requires, not a shrug.
> - **UNBLOCKING STEP, SPECIFIC AND SINGLE:** a human (or any organ on a non-blocked network) opens
>   `bitflyer.com/en-jp/terms` ONCE and pastes the data-usage clause into this card. One page-read
>   closes the field.
> - **WHY THE DATE IS SHORT (2026-08-09, 14 days):** the 31-day rolling wall means each day of
>   delay permanently destroys a day of the only history that will ever be recoverable, and the
>   backfill itself is ~32 minutes once permitted. A long deferral here is not patience, it is
>   silent data destruction. **Routed to GAP_REGISTER #68.**
>
> _Pre-deferral verification notes below (unchanged, still valid):_
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). First-party docs opened AND the
> live API probed. This entry was graded on ">=4 Japanese blog posts" with no primary source — and
> the bloggers were RIGHT on all three load-bearing claims. NO refutations. Logged as a case where
> cross-source consensus earned its keep (the opposite outcome to entries 1/6/8).**
>
> - **"NO native candle API" — CONFIRMED** from `lightning.bitflyer.com/docs?lang=en`. Full public
>   endpoint scrape: `/v1/{markets,getmarkets,ticker,getticker,gethealth,getfundingratehistory,`
>   `getfundingrate,getexecutions,getcorporateleverage,getboardstate,getboard,executions,board}` —
>   **zero candle/OHLC/kline endpoints.** Self-bucketing from executions is genuinely the only path.
> - **"31-day hard lookback" — CONFIRMED THREE WAYS.** (i) Docs: *"As of December 19, 2018, the
>   execution history obtainable through the before parameter will be limited to the most recent 31
>   days."* (ii) API error: `{"status":-156,"error_message":"Execution history is limited to the most
>   recent 31 days."}` (iii) **Empirically binary-searched to the exact execution** (31 iterations):
>   oldest reachable `id 2646808096` @ `2026-06-24T04:00:02.637`; `before=2646808096` → -156. The wall
>   is one id wide and exact, and sits **exactly 31 days** back from probe date 2026-07-25.
> - **ESCAPE-HATCH TESTED AND CLOSED.** The docs scope the limit to `before`, which reads like a
>   loophole; the `after` parameter was probed at 5 values (1 … 2646000000) and every one returned the
>   same NEWEST execution (results sort descending; `after` only raises the floor).
>   **No parameter combination reaches older data — the destroyed-at-source framing is CORRECT.**
> - **"~500 calls/5min" — CONFIRMED exactly.** Docs: *"Same IP Address: 500 queries per 5 minutes"*;
>   live headers `x-ratelimit-period: 300`, `x-ratelimit-remaining: 499`. `count` max 500 (1000
>   silently caps), default 100.
> - **CAPACITY MATH (new, actionable):** BTC_JPY runs **~51.5k executions/day** (1,597,767 over the
>   31-day window). Recorder ceiling is 500 calls × 500 exec = 250k executions/5min — **the rate limit
>   is nowhere near binding.** A full 31-day backfill is ~3,200 calls ≈ **32 minutes**.
> - **LICENSE: UNCONFIRMED, and here is exactly what blocked it.** `bitflyer.com` (the ToS host) is
>   unreachable from this VPS — 403 via curl and WebFetch, connection dropped with a browser UA.
>   Looks like a WAF/geo-block, NOT an auth wall; no login was presented and **no attempt was made to
>   defeat it** (§13). `lightning.bitflyer.com` and `api.bitflyer.com` serve fine, so it is
>   host-specific. The docs page carries no data-licensing/redistribution language at all — only a
>   load restriction. **So: nothing yet prohibits use, but nothing yet permits it either.** Fetch the
>   ToS from a non-blocked egress to close this field.
> - **NEXT STEP — TIME-SENSITIVE:** the 31-day wall means **every day of delay is history permanently
>   destroyed.** Start the forward recorder as soon as the licence field is closed; the ~32-minute
>   backfill captures the only 31 days that will ever be recoverable.
> - **LICENCE-CLOSE ATTEMPT #2 FAILED (2026-07-25, session B): Wayback route exhausted.**
>   `archive.org/wayback/available` empty for all 5 candidate terms URLs (en-jp/ja-jp/api-terms/
>   terms, lightning docs path); CDX domain queries for `bitflyer.com/{en-jp,ja-jp}/*` return no
>   terms/policy captures — bitFlyer's JS app was never usefully archived. **Two independent
>   failed routes now logged (direct = WAF/geo-block; archive = no snapshots). Lifting
>   condition: fetch the ToS from any non-blocked egress (different IP/organ or human) — one
>   page-read closes the field and starts the clock on the ~32-minute backfill.**

_Superseded original grading below (kept for the record):_
### 3-OLD. bitFlyer getexecutions + self-recorded candles — grade: needs-monitoring
- **Provides / replaces:** Japanese-venue trade executions, self-bucketed into OHLC (bitFlyer has NO
  native candle API). Serves the regional exchange-native target, same "recorder" shape as the desk's
  existing forward-only philosophy.
- **Provenance:** cross-corroborated across >=4 independent Japanese-language blog/note.com write-ups
  describing the same **31-day hard lookback cutoff** on execution history and a ~500-calls/5-min
  rate limit. No first-party bitFlyer doc page opened this session.
- **Verify-don't-trust:** mechanism graded on cross-source consensus, not primary confirmation —
  flagged for a direct docs.bitflyer.com open next cycle before deeper reliance.
- **Genealogy:** auth none for public execution endpoint · cadence real-time forward-only · **failure
  mode is severe and confirmed: pre-today history is DESTROYED AT SOURCE** — only a forward recorder
  (started today) closes this, structurally identical to the desk's pre-recorder Binance L2 gap.
- **Grade: needs-monitoring** (mechanism), but logged as a destroyed-at-source residual for anything
  before a recorder start date.

### 4. Bithumb (spot + futures) — grade: **spot VERIFIED-CLEAN-MECHANISM, DEEPEST free Korean-venue minute archive known to the desk (re-graded 2026-07-25); futures lead DEAD**
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). Live API probed directly —
> the "no free bulk archive, paid-Amberdata-only" gap is REFUTED, and by a wide margin.**
>
> - **Bithumb's v1 REST API is Upbit-SCHEMA-COMPATIBLE, keyless, and paginates to venue launch:**
>   `api.bithumb.com/v1/candles/days?market=KRW-BTC&count=N&to=<ISO>` returns Upbit-style JSON
>   (`candle_date_time_utc`, `opening_price`, …) — the desk's Upbit pagination code shape works
>   nearly verbatim (option value: one collector pattern, two Korean venues).
> - **DEPTH, probed empirically:** daily candles reach **2014-01-13** (`to=2013-06-01` → clean
>   empty `[]`; epoch ≈ Bithumb/Xcoin launch). **1-minute candles reach at least 2014-05-31**
>   (probed 2019/2017/2015/2014 — all served). That is **4.7 years DEEPER than the Amberdata
>   paid mirror (2018-10-09)** the old card cited as the only deep source, and **3.5 years deeper
>   than Upbit's portal (2017-10-24)** — the deepest free KRW minute data known to the desk.
> - **VERIFY-DON'T-TRUST:** same-venue two-API diff — legacy `public/candlestick/BTC_KRW/24h`
>   vs v1 for 2026-07-24: **O/H/L/C/volume identical to the last decimal** (93667000/94090000/
>   93404000/93920000/137.36337738). Deep-history plausibility consistent (2014 ≈ 464k, 2015 ≈
>   506k, 2016-12 ≈ 1,192k KRW). **HONEST LIMIT: the deep diff is SAME-SOURCE only** — the
>   planned independent diff via CryptoCompare failed because **min-api.cryptocompare.com now
>   requires an API key** (Coindesk-era change; ecology shift logged). Kimchi premium makes
>   cross-venue price diffs unusable as exact checks.
> - **RATE LIMIT (headers):** `x-ratelimit-burst-capacity: 150, replenish-rate: 150` — a full
>   1m backfill 2014→now ≈ 6.3M bars ≈ ~32k calls at 200/call: tractable in hours.
> - **FUTURES LEAD DEAD:** `bithumbfutures.github.io/bithumb-futures-api-doc/` → **404**. The
>   old card's futures claim now has no living source; retry via `apidocs.bithumb.com` next
>   cycle.
> - **OPEN FIELDS:** licence/ToS for bulk collection not yet read (apidocs.bithumb.com was a JS
>   shell last session — re-probe or fetch its API-terms path before building a collector);
>   delisted-market survivorship behaviour unknown; whether v1 serves non-KRW quote markets
>   unprobed.
>
_Superseded original grading below (kept for the record):_
### 4-OLD. Bithumb (spot + futures) — grade: UNVERIFIED
- **Provides / replaces:** would serve as the second Korean-venue leg alongside Upbit.
- **Provenance:** search surfaced a Bithumb Futures API docs page (bar/candle history) and a Bithumb
  spot API docs site, but WebFetch of `apidocs.bithumb.com` returned only a navigation shell — no
  endpoint/depth/rate-limit/auth detail confirmed. The only DEEP historical OHLCV (since 2018-10-09)
  found for Bithumb is Amberdata's **paid** mirror.
- **Verify-don't-trust:** not verified this session. Do not adopt.
- **Grade: UNVERIFIED.** Honest gap: unlike Upbit, no confirmed free bulk archive for Bithumb spot.

### 5. Coincheck — grade: destroyed-at-source (for this session)
- **Provides / replaces:** would be the second Japanese-venue leg.
- **Provenance:** search returned no Coincheck-specific public historical archive — only generic
  cross-exchange aggregators (CoinGecko/CoinAPI/Bitquery), none of which are Coincheck-native.
- **Verify-don't-trust:** n/a — nothing found to verify.
- **Grade: destroyed-at-source for this session's search depth** (not a permanent claim — retry with
  narrower Japanese-language queries next cycle per Temporal Rediscovery).

### 6. Tardis vendor-replacement — grade: **VERIFIED-CLEAN (re-graded 2026-07-25)** — backfill claim REFUTED
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). The prior grade was written from
> search summaries and was WRONG in the desk's DISFAVOUR. Files were actually downloaded this time.**
> - **OP-008's dependency is SOUND** — the free first-of-month tier is real and primary-confirmed.
>   Docs (`docs.tardis.dev/downloadable-csv-files`, 200): *"Historical datasets for the first day of
>   each month are available to download without API key."* Strongest artifact = the API's own 401
>   body: *"For unauthorized requests, only historical CSV market datasets for the first day of each
>   month are available."* Negative control: day 02 and day 15 → 401. Day 01 → 200.
> - **THE "destroyed-at-source (backfill)" GRADE IS REFUTED AS WRITTEN.** Downloaded
>   `deribit/incremental_book_L2/2020/04/01/BTC-PERPETUAL.csv.gz` → 200, 159,259,129 B,
>   **19,239,595 rows**, initial snapshot **2,115 price levels (1,149 bid / 966 ask)** — FULL-DEPTH,
>   tick-by-tick, a complete UTC day, free. Also pulled binance trades 2020-06-01 (826,963 rows),
>   upbit KRW-BTC 2024-01-01 (111,522 rows), bitflyer FX_BTC_JPY 2024-01-01 (10,491 rows).
>   The real residual gap is **GRANULARITY (1 day per month), NOT AVAILABILITY** — that is a
>   materially different and much smaller gap than "destroyed at source".
> - **SCOPE was understated:** all 9 CSV types free on the 1st (`trades, incremental_book_L2, quotes,
>   book_snapshot_5/25, book_ticker, derivative_ticker, liquidations, options_chain`), across every
>   venue tested (binance, binance-futures, deribit, bybit, okex, coinbase, kraken, kucoin, gate-io,
>   bitstamp, bitget, hyperliquid, mexc, upbit, bitflyer), for **every month 2019-04 → 2026-07**.
>   ⇒ ~88 monthly full-depth L2 days exist for research the desk believed it did not have.
> - **NEW FREE DIFF TARGETS for entries 1 and 3:** Tardis covers `upbit` (since 2021-03-03) and
>   `bitflyer` (since 2019-08-30) — neither entry previously had an identified ground-truth target.
> - **CORROBORATES entries 4 and 5:** `bithumb` and `coincheck` are ABSENT from Tardis's 62-venue
>   catalog — independent support for those two honest gaps.
> - **LICENSE (binds free users; `docs.tardis.dev/legal/terms-of-service`):** internal business /
>   research / educational use **PERMITTED** (desk diffing is fine). Redistribution barred except
>   aggregated Derived Data at **≥10-minute** resolution where raw data cannot be reconstructed;
>   reformatted/filtered/resampled ticks explicitly do NOT count as Derived Data. **Clause 23:
>   Coinbase venue data must be treated as QUARANTINED** (no third-party display/redistribution, no
>   use to create financial products). Charter §13 note: free ≠ unrestricted — honour these terms.
> - **HONEST LIMIT:** OP-008 diffs anchor ONLY on first-of-month dates. A pipeline verified on the
>   1st is UNVERIFIED for the other ~29 days. The prior wording hid this; state it explicitly.
> - **DEFECT FOUND ELSEWHERE (flagged, not edited — freeze):** `data/data_registry.json` lists Tardis
>   at ~$599/mo. **No such tier exists.** Published: Academic $350–650, Solo $700–1,200, Professional
>   $1,000–2,200, Business $3,000–6,000/mo, $300 min order. Brain should correct the registry.
> - **NEXT STEP:** run OP-008 for real — diff `binance/trades/2026/07/01/BTCUSDT` against the desk's
>   own recorder for that date. That is the first true ground-truth diff and it is now unblocked.

_Superseded original grading below (kept for the record):_
### 6-OLD. Tardis vendor-replacement — grade: needs-monitoring (forward) / destroyed-at-source (backfill)
- **Provides / replaces:** Tardis.dev tick/L2 history subscription.
- **Free path:** exchange-native dumps (Binance/OKX/Upbit portals + Bybit bucket) for anything before
  the recorder's start, plus the desk's own mainnet recorder (LIVE, forward-only since 2026-07-17
  23:16Z) for everything after.
- **Provenance:** Tardis docs pages (`docs.tardis.dev/historical-data-details/*`) confirming
  free first-of-month CSV samples surfaced in search results; not independently re-opened this
  session (was previously logged).
- **Verify-don't-trust:** diff plan unchanged from prior session — every free pipeline gets diffed
  against a Tardis free first-of-month sample before being trusted.
- **Residual gap: pre-recorder-start L2 tick diffs are destroyed at source** — no free or paid
  provider reconstructs history the recorder didn't capture forward. Already logged, unchanged.

### 7. Glassnode / CryptoQuant vendor-replacement — grade: **VERIFIED FREE PRIMARY FOUND for the metric class (Coin Metrics community), needs-legitimacy-review for production use (CC BY-NC) — re-graded 2026-07-25** [§33: wired tier:1 -> data/coinmetrics_flows.jsonl]
> **§33 CONVERSION 2026-07-26 — FOUND became WIRED. `scripts/collect_coinmetrics_flows.py`,
> BUILT AND RUN; the free primary is now INGESTED, DIFF-VERIFIED and SCREENED, not catalogued.**
> - **INGESTED AT FULL ARCHIVE DEPTH (§33.7 depth parity — full history, not a slice):**
>   `data/coinmetrics_flows.jsonl`, **9,866 daily rows** — btc **2010-07-18 → 2026-07-25** (5,852d,
>   flows populated from 2011-04-24, 5,571 flow-days) and eth **2015-07-30 → 2026-07-25** (4,014d).
>   The live keyless community API, not the stale repo CSV. **Trap logged for the operator library:
>   the API pages from the END by default — without `paging_from=start` a 15-year archive silently
>   returns three days and reads as a thin source.**
> - **VERIFY-DON'T-TRUST — TWO DIFFS RUN, NOT REFERENCED.** (i) INTERNAL: d(SplyExNtv) vs
>   (FlowIn−FlowOut) over 5,570d btc → **corr 0.999**, median residual ~0 of median flow; eth 4,012d
>   → corr 0.758 (weaker, expected: ETH supply nets internal exchange transfers the directional
>   series does not). (ii) EXTERNAL: CM `PriceUSD` vs Binance BTCUSDT, **3,265 overlapping days**,
>   median **13.2 bps**.
> - **A FIRST-PASS ASSUMPTION WAS REFUTED BY ITS OWN CHECK (§33.8, and the reason the check exists):**
>   the price stamp was coded to CM's documented START-of-UTC-day convention. Measured, `PriceUSD[d]`
>   sits **13.2 bps from Binance CLOSE[d] and 150.3 bps from OPEN[d]** — it is the END-of-day price.
>   The screen alignment was corrected and re-run; the original build would have lagged every screen
>   by one day. The check re-runs on every execution, so a re-stamp by CM surfaces as an error.
> - **SCREENED ON THE FULL WINDOW (§26, audited `libs.research.axis_screen`, artifact gate ON):**
>   **all four constructions logged, win or lose (§26.3 — reporting only the printer is p-hacking).**
>   `cm_netflow_native_btc` n=5,549 IC −0.0075 → **SCREEN-WEAK**; `cm_netflow_over_exchange_supply_btc`
>   n=5,549 IC +0.0095 → **SCREEN-WEAK**; eth native n=3,982 IC +0.0039 → **SCREEN-WEAK**; eth
>   normalised n=3,982 IC +0.0031 → **SCREEN-WEAK**. All in `data/batch_coinmetrics_screen.json`
>   and in research_memory (`--axis coinmetrics_flows`, 4 hypotheses + 1 dataset row).
> - **THE NEGATIVE IS THE DELIVERABLE (§26.6):** the aggregate exchange-flow metric class carries no
>   daily-horizon edge over 15 years. That is precisely the information $799/mo × 2 was being asked
>   for, now owned at $0 with the vendors' own metric class measured FLAT.
> - **⚠️ LICENCE — CC BY-NC 4.0, STILL OPEN, DELIBERATELY NOT SELF-APPROVED.** What was done here is
>   internal research/verification/diff use by a private desk that redistributes nothing — the
>   defensible interim scope named on this card. Using the series as a PRODUCTION signal input is a
>   NonCommercial question and remains a human ruling. Stage A carries zero promotion authority in
>   any case, so nothing downstream depends on the ruling today. **Routed to GAP_REGISTER #67.**
>
> _Superseded pre-conversion notes below (kept for the record):_
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down — the inbox #54 handoff, last
> search-summary-provenance card). The claimed Dune path is key-gated and stays unverified; a
> BETTER free primary was found, downloaded, and live-probed instead.**
>
> - **THE CLAIMED PATH (Dune) IS NOT KEYLESS-VERIFIABLE:** `api.dune.com` → 401 `invalid API Key`
>   keyless; `dune.com/queries/<id>` → 403 to this VPS. Dune's free tier exists but requires
>   registration (human step). DEMOTED to secondary path; the claim "Dune replicates CryptoQuant"
>   remains unverified as written.
> - **VENDOR APIS 401 KEYLESS** (no free diff target without login): `api.cryptoquant.com` → 401
>   token-required; `api.glassnode.com` → 401 nginx.
> - **THE FIND — COIN METRICS COMMUNITY DATA covers the metric CLASS free:**
>   `raw.githubusercontent.com/coinmetrics/data/master/csv/btc.csv` → 200, **2,482,497 B, 6,352
>   rows, 2009-01-03 → 2026-05-23**, columns include **FlowInExNtv/FlowInExUSD/FlowOutExNtv/
>   FlowOutExUSD (aggregate exchange in/out flows → netflow = in − out), SplyExNtv/SplyExUSD
>   (supply on exchanges), CapMVRVCur (MVRV), CapMrktCurUSD, HashRate, AdrActCnt, SplyCur**.
>   Flow columns populated 2011-04-24 →; MVRV 2010-07-18 →. `eth.csv` carries the same flow
>   columns. **Repo is STALE (last commit 2026-05-24) — the live path is the keyless community
>   API:** `community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=
>   FlowInExNtv,FlowOutExNtv,SplyExNtv` → 200 unauthenticated, current through T+1 (2026-07-20
>   values observed, status "flash", completion ~01:44-02:50Z next day). Note: metric name
>   `FlowNetExNtv` is NOT served — request in/out and difference locally.
> - **⚠️ LICENSE — CC BY-NC 4.0** (repo LICENSE file read; community API terms page redirects —
>   read the current terms before any ruling). NonCommercial is a REAL question for a prop desk:
>   using it as a production signal input needs a legitimacy ruling (same queue as Upbit).
>   Internal verification/diff use during research is the defensible interim scope. NOT
>   self-approved — routed to the legitimacy queue.
> - **SCREEN-ON-DISCOVERY DONE IN SAME RUN (charter §26):** the new MVRV axis was Stage-A
>   screened via `libs.research.axis_screen` → **TIMING-ARTIFACT** (same-period corr 0.416; the
>   20d-z of a price-numerator ratio is momentum in disguise) — graveyarded with escalation
>   pre-registration (weekly/orthogonalized construction). Netflow is NOT a new axis (desk
>   already owns `onchain_flows.py`); CM's series is its **backfill + independent diff target**
>   — 15 years of history the desk's own collector cannot reach (started 2026-07).
> - **RESIDUAL GAP (unchanged, honest):** CryptoQuant's real-time granular per-exchange
>   indicators and Glassnode's curated composite models are NOT replicated; CM community is
>   aggregate + T+1. The metric CLASS (netflow/exchange-supply/MVRV family) is what's covered.
> - **NEXT STEP:** diff desk `onchain_flows.py` netflow vs CM FlowIn−FlowOut for the overlapping
>   window (both exist since 2026-07) — two INDEPENDENT constructions of the same quantity; then
>   the legitimacy ruling decides production use.
>
_Superseded original grading below (kept for the record):_
### 7-OLD. Glassnode / CryptoQuant vendor-replacement — grade: UNVERIFIED
- **Provides / replaces:** Glassnode $799/mo, CryptoQuant $799/mo (both already blocked from
  purchase by the desk's free-proxy rule).
- **Claimed free path:** Dune Analytics community dashboards + self-written SQL over labeled chain
  data (eth-labels/cex-list) to compute exchange netflow / whale-transfer / stablecoin-supply
  metrics.
- **Provenance:** this claim comes from search-engine listicles/blog comparisons (stingray.fi,
  findmymoat.com, mirkaso.com) asserting Dune "replicates" CryptoQuant metrics. **No Dune dashboard
  was opened, no query run, no diff performed against a real CryptoQuant number this session.**
- **Verify-don't-trust:** explicitly graded UNVERIFIED — this is a secondary-source assertion, not
  evidence. Verify plan for next cycle: pull one Dune community netflow query (BTC or ETH), diff its
  output against a CryptoQuant free-tier chart for an overlapping exchange/date.
- **Residual gap:** CryptoQuant's proprietary real-time granular indicators and Glassnode's curated
  composite on-chain valuation models are not reconstructed by any free tool found this session —
  the underlying MECHANISM (netflow/whale/stablecoin) is reconstructable; the specific proprietary
  formulas are not.
- **Grade: UNVERIFIED.** Do not present as an adopted replacement yet.

### 8. Kaiko vendor-replacement — grade: **needs-monitoring (raw ticks) / RECONSTRUCTABLE (index methodology — re-graded 2026-07-25)** [§33: wired tier:1 -> data/kaiko_vwm_reference_rate.jsonl]
> **§33 CONVERSION 2026-07-26 — RECONSTRUCTABLE became RECONSTRUCTED. This card's own NEXT STEP
> ("price the published VWM+TWAP rule against the desk's own cross-venue normalizer") was EXECUTED:
> `scripts/reconstruct_kaiko_reference_rate.py`, built and run.**
> - **THE RULE WAS RE-READ FROM THE VENDOR PAGE 2026-07-26 AND QUOTED, NOT PARAPHRASED:** *"The
>   calculation window is split into equal time partitions, with each partition subject to a
>   volume-weighted median — the price at the 50% cumulative volume mark — which is outlier-resistant
>   by design"*, then *"greater weight to the most recent partitions, before a final time-weighted
>   average"*, over *"only executed trades … with no order book data used"*, *"up to five exchanges"*.
>   **NEW vs this card's 2026-07-25 reading: the cross-partition average is RECENCY-WEIGHTED, not a
>   flat TWAP** — the card said "VWM + TWAP", which understates the rule.
> - **RUN, NOT DESCRIBED:** `data/kaiko_vwm_reference_rate.jsonl` — **132 fixings** over a **11.99h
>   joint 4-venue tape, 174,199 trades** (coinbase 139,661 / kraken 13,595 / bitfinex 10,733 /
>   bitstamp 10,210), all keyless public REST. Gemini was **EXCLUDED with its reason recorded** (its
>   public endpoint served 0.67h of the 12h window — no working backward pagination), rather than
>   silently truncating everyone else's window to its own; that is Kaiko's own "data reliability"
>   vetting criterion, applied.
> - **THE ANSWER TO "IS THE DESK'S NORMALIZER ALREADY EQUIVALENT?" IS: ONLY IN CALM TAPE.**
>   |VWM+TWAP − desk cross-venue VWAP| = **median 1.42 bps, p95 5.83 bps, max 6.98 bps**. But the
>   stress that actually separates a median from a mean — one injected print 5% off market at 2% of
>   window volume — moves the **VWM+TWAP 0.1 bps and the desk's VWAP 9.8 bps (~100×)**. A comparison
>   run only on clean tape would have concluded "already equivalent" and been WRONG: the outlier
>   resistance IS the value-add, and it is now owned at $0.
> - **HONEST LIMITS, STATED NOT BURIED:** window length, partition count and the recency decay are
>   NOT published (60min / 12×5min / linear ramp are DESK parameters), and the rulebook PDF interior
>   is still unextracted (no PDF tooling on this box — the same limit this card already flagged). So
>   this reproduces the METHOD, not Kaiko's exact fixing NUMBER. Constituent set is five clean public
>   USD venues, not Kaiko's own vetted list (not public per-rate).
>
> ---
> **⚠️ CORRECTION 2026-07-26 (literature deep-miner run 3, [T1-a] verification). EVERY ONE OF THE
> THREE "HONEST LIMITS" ABOVE IS REFUTED, AND THE HEADLINE AGREEMENT NUMBER DOES NOT MEAN WHAT THE
> CARD IMPLIES. Left above intact; corrected here.**
> - **"window length, partition count and recency decay are NOT published" — FALSE. All three are
>   published**, in the *Benchmark Rates Rulebook* (reachable only via a PDF `/URI` link annotation
>   inside the Indices Rulebook — the Indices Rulebook was the wrong document). Actual: **10 equal
>   partitions** (not the desk's 12), **weights inversely proportional to time** (not a linear ramp),
>   windows **static 300s real-time / 3600s fixing** for Reference Rates (not 60min). The dynamic
>   Benchmark Rates selection rule and its thresholds are published and computable from free trade
>   data. **The desk was running invented parameters where published ones exist.**
> - **"the rulebook PDF interior is still unextracted (no PDF tooling on this box)" — FALSE**, and it
>   had been inherited across three runs. Extracted with stdlib `zlib` alone, zero installs. See
>   improvement_inbox #59 / GAP_REGISTER #70.
> - **"Kaiko's own vetted list (not public per-rate)" — FALSE for BTC.** The Cboe rule filing to the
>   CFTC names the constituents: **Bitstamp, Crypto.com, Gemini, Kraken, LMAX Digital.**
> - **THEREFORE THE 1.42 bps FIGURE IS NOT EVIDENCE OF TRACKING KAIKO.** The reconstruction ran
>   coinbase/kraken/bitfinex/bitstamp — **2-of-5 overlap** with the real constituent set. **Coinbase
>   is 139,661 of 174,199 trades (80% of the tape) and is NOT a Kaiko constituent at all**, while
>   **Gemini, which the card excluded for a documented and otherwise-sound reliability reason, IS
>   one.** The number is a real measurement of "this method vs the desk's VWAP"; it is not a
>   measurement of "this reconstruction vs Kaiko". The stress-test result (VWM 0.1 bps vs VWAP
>   9.8 bps under an injected outlier) **stands unaffected** — that finding is about the method, not
>   the constituents, and remains the card's genuine win.
> - **RE-RUN REQUIRED** against Bitstamp + Crypto.com + Gemini + Kraken + LMAX before any
>   tracking claim. **One constituent is unrecoverable historically: LMAX Digital's free API has no
>   trades endpoint** (forward-only via WS ticker), so its history is destroyed-at-source — start a
>   recorder now or that leg is permanently unreconstructable.
> - ESMA independently confirmed, with two precision corrections: the registered entity is
>   **Kaiko Indices SAS** (esmaId `FRBMR2019000003`, LEI `969500BKJ2X29T7NJH85`, France/AMF), status
>   **"Registration under Art. 34" — registered, not authorised** — and the rulebook copyright owner
>   is a *third* entity, **Challenger Deep SAS**.
> - **REPLACEABILITY, correctly split** (conflating these is why this card was vague): **RATES =
>   FULLY reconstructable. INDICES = PARTIALLY** — blocked only on Kaiko's proprietary restrictive
>   *circulating supply* definition, which binds indices and **not** rates.
> - Full record: `docs/research/deep_sweep/T1a_kaiko_verification.md`.
> - **DEPTH CEILING, MEASURED NOT ASSUMED:** free public tick endpoints are ROLLING windows;
>   bitstamp's `time=day` (24h) is the binding cap on a joint multi-venue tape. 12h is the archive
>   floor reached, not a convenient slice (§32 bounded-honestly clause).
> - **LICENCE:** nothing rehosted. The methodology PDFs were not redistributed; the rule was read
>   from the public page and re-implemented. Trade data is the venues' own keyless public REST.
> - Logged to research_memory (`--axis kaiko_reference_rate`); summary
>   `data/batch_kaiko_reconstruction.json`.
>
> _Superseded pre-conversion notes below (kept for the record):_
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). Same root defect as entry 6:
> the grade had been written from search summaries. Two claims refuted.**
> - **"Index methodology is proprietary and not reconstructable" — REFUTED.** Kaiko is an
>   **EU-BMR-registered benchmark administrator under AMF supervision**, and BMR/IOSCO status makes
>   methodology publication effectively mandatory. The rulebook is public and unauthenticated:
>   `25446524.fs1.hubspotusercontent-eu1.net/hubfs/25446524/Factsheets/Kaiko%20Indices%20Rulebook.pdf`
>   → 200, application/pdf, 2,527,759 B ("Rulebook — Kaiko Benchmark Indices — April 2025 — v2.0").
>   `kaiko.com/resources/categories/methodologies` → 200, lists 6 further methodology PDFs.
>   The outlier rule is stated in plain text on `kaiko.com/indices/reference-rates/crypto-rates`:
>   **Volume-Weighted Median (VWM) + TWAP, outlier rejection at the 50% cumulative-volume mark,
>   trades only, no order-book data.** That is reconstructable by the desk's own normalizer.
> - **"$1,000–2,500/mo" — REFUTED / STRIKE IT.** `kaiko.com/pricing` → **404**; the contracts page
>   states pricing is custom/quote-only. The figure had zero primary support (the only dollar amount
>   published anywhere on kaiko.com is a $60/yr research promo). Do not repeat search-derived pricing.
> - **Free/open surfaces confirmed:** `explorer.kaiko.com` (200, no login — live index levels and
>   constituents), `instruments.kaiko.com` (200), public Q3-2025 rebalancing report PDF (200).
>   `github.com/kaikodata` = 12 public repos, but SDKs/protobufs/icons only — **no market data**.
> - **LICENSE: unstated** on the methodology PDFs — openly published, but no redistribution grant
>   found. Read them, reconstruct the method, do not rehost the PDFs.
> - **HONEST LIMITS (what was NOT confirmed):** the rulebook's *interior* text was not independently
>   re-extracted (no PDF tooling on this box) — the refutation rests on the reference-rates HTML page,
>   which states the methodology on its own, not on those quotes. **ESMA register not independently
>   checked** (JS-driven UI), so BMR-registered status rests on Kaiko's own documents — precisely the
>   single-source failure mode that produced the bad pricing figure. Flagged, not papered over.
> - **NEXT STEP:** price the published VWM+TWAP rule against the desk's own cross-venue normalizer;
>   if they agree, Kaiko's core value-add is fully replaced at $0.

_Superseded original grading below (kept for the record):_
### 8-OLD. Kaiko vendor-replacement — grade: needs-monitoring (raw ticks) / destroyed-at-source (index methodology)
- **Provides / replaces:** Kaiko consolidated L1/L2 aggregations, $1,000–2,500/mo tiers.
- **Free path:** the desk's own multi-exchange native recorder + REST/WS collection per venue,
  normalized in-house — Kaiko's core value-add (cross-venue normalization) is exactly what the desk
  already owns the methodology for.
- **Provenance:** Kaiko product/pricing pages read via search summary only, not WebFetched directly
  this session — pricing figures are as-reported by search, not primary-confirmed.
- **Residual gap:** Kaiko's exact curated reference-rate/index weighting and outlier-rejection rules
  are proprietary and not reconstructable; long-tail illiquid venue/pair coverage likely exceeds what
  the desk will ever natively collect.
- **Grade: needs-monitoring** for raw consolidated ticks (self-collectable); **destroyed-at-source**
  for the exact index methodology.

### 9. Stablecoin mint/burn self-computation — grade: **verified-clean (mechanism; integer-exact on-chain reconciliation, 2026-07-25)** — but the registry's RPC chain is DEAD for logs
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). The query was actually RUN
> (ad-hoc research, no code shipped — freeze respected).**
> - **MECHANISM VERIFIED END-TO-END, EXACTLY:** over a 24h window (blocks 25,602,972→25,610,172),
>   USDC Transfer-from-0x0 (mints) = 2,404 events / 375,834,141 USDC; Transfer-to-0x0 (burns) =
>   1,656 events / 564,594,019 USDC; net −188,759,878 vs on-chain `totalSupply()` delta
>   −188,760,098 — residual 219.879396 USDC **fully explained by the boundary block** (block
>   `frm` held exactly one 219.8794-USDC mint already inside the "then" supply). **CONVENTION,
>   load-bearing: supply(now) − supply(then) = events in blocks (then, now] — fromBlock must be
>   then+1.** After the fix the reconciliation is integer-exact.
> - **FAILURE MODE CONFIRMED LIVE:** top mint recipient of the day = `0x55fe002a…` (Circle's own
>   treasury/operator wallet, 300.7M of 375.8M) — mints land treasury-FIRST, so mint events ≠
>   immediate exchange flow. The card's treasury-shuffle warning is real, not theoretical.
> - **⚠️ CRITICAL DEFECT FOR THE COLLECTOR PLAN (flagged, not fixed — freeze):**
>   `data_registry.json`'s `eth_public_rpc` chain (publicnode/llamarpc/cloudflare/ankr) is
>   **effectively dead for `eth_getLogs`**: publicnode now demands a personal token for
>   non-recent log queries and intermittently 403s; **ankr requires an API key outright**;
>   llamarpc is Cloudflare-challenged from this VPS; cloudflare-eth returns internal error.
>   `balanceOf`-at-latest (what `onchain_flows.py` does) still works — the LIVE collector is
>   unaffected — but any event-based or historical backfill collector needs a new chain.
>   **Working keyless getLogs set (probed 2026-07-25): rpc.flashbots.net and rpc.mevblocker.io
>   (≥700-block ranges), eth-pokt.nodies.app (250), 1rpc.io/eth (50), blastapi (10);
>   eth.meowrpc.com serves no getLogs at all.**
> - **USDT NOTE:** USDT's mint mechanics differ (Issue/treasury events, not clean 0x0
>   transfers) — do NOT copy the USDC construction blind; verify per-token event models.
>
_Superseded original grading below (kept for the record):_
### 9-OLD. Stablecoin mint/burn self-computation — grade: needs-monitoring
- **Provides / replaces:** CryptoQuant/Glassnode stablecoin supply and mint-burn-flow metrics.
- **Free path:** filter ERC-20 Transfer events to/from the null address on the canonical USDC
  contract (`0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`) and the USDT contract, using the desk's
  existing free RPC fallback chain (publicnode/llamarpc/cloudflare/ankr — already LIVE per
  `data/data_registry.json` `eth_public_rpc`) or the AWS Public Blockchain Data lake (see below) for
  historical bulk.
- **Provenance:** treasury contract address independently corroborated by a **Federal Reserve FEDS
  Note** (federalreserve.gov) that uses AWS Public Blockchain Data for exactly this analysis —
  unusually strong non-crypto-native validation of both mechanism and source.
- **Verify-don't-trust:** mechanism confirmed by a credible independent (non-financially-interested)
  source; the desk has NOT run this query itself yet (research-only, no code under the freeze). Next
  step is implementation + cross-check against issuer-published circulating-supply figures.
- **Failure modes:** non-standard treasury-shuffle patterns can look like mint/burn but aren't; this
  approach also misses off-chain book-entry adjustments before an issuer broadcasts on-chain.
- **Grade: needs-monitoring.**

### 10. AWS Public Blockchain Data (registry.opendata.aws) — grade: verified-clean — **NEW SOURCE CLASS**
- **Provides / replaces:** full Bitcoin + Ethereum chain data as partitioned Parquet, plus 9 more
  chains (Arbitrum/Base/Optimism/Aptos/BNB Chain/Cronos/Provenance/Stellar/TON/XRP Ledger) from other
  maintainers in the same bucket. Replaces the need to run/rent a full node for raw chain access.
- **Provenance:** WebFetch'd `https://registry.opendata.aws/aws-public-blockchain/` directly;
  confirmed bucket path (`s3://aws-public-blockchain/`), no-auth access
  (`aws s3 ls --no-sign-request ...`), Parquet format, and Apache-2.0-style license/citation
  requirement in the page's own content.
- **Verify-don't-trust:** AWS itself flags the dataset "experimental, not recommended for production
  workloads" — treat as research-grade until spot-checked against a second chain source (e.g. the
  desk's own `eth_public_rpc` balance queries for an overlapping address/block).
- **Genealogy:** cadence = new partitions daily · license Apache 2.0 + citation requirement · failure
  modes: schema/partition versioning differs by chain (v1.0 BTC/ETH vs v1.1 others), do not assume a
  uniform schema.
- **Grade: verified-clean.** See SEARCH-SPACE EXPANSION below — this is a materially new access
  pattern for the desk's on-chain data posture.

### 11. eth-labels (dawsbot/eth-labels) — grade: **verified-clean (verification complete 2026-07-25) — dataset DOWNGRADED to supplementary-only: systematic label corruption found**
> **RE-VERIFIED 2026-07-25 (EN frontier miner, backlog burn-down). The CSV was actually
> downloaded and cross-diffed — the old card's gentle "labels can mislabel/lag" caveat
> understates what's wrong.**
> - **Artifact:** `data/csv/accounts.csv` @ branch **v1** (the default branch is `v1`, NOT
>   `main` — raw links against main 404; this cost a probe) → 200, **12,262,957 B, 144,379
>   rows** (86,924 chainId=1), schema `address,chainId,label,nameTag`.
> - **CROSS-DIFF vs tradezon/cex-list** (`data/ethereum-mainnet.json`, 373 addrs / 23
>   exchanges): 276/373 present in eth-labels (74%), name-agreement 237/276 with most
>   disagreements benign taxonomy (HTX≡Huobi rebrand, Paxos-BUSD, Tether-multisig-at-Bitfinex).
> - **BUT — SYSTEMATIC DEFECTS FOUND:**
>   (a) **all three canonical Binance wallets are ABSENT** from eth-labels chainId=1: Binance 8
>   cold `0xF977814e…`, Binance 1 `0x3f5CE5FB…`, Binance 14 `0x28C6c062…` — these are
>   2018-era-famous addresses, so this is scrape INCOMPLETENESS, not label lag;
>   (b) **label/nameTag columns contradict each other at scale**: thousands of rows carry label
>   `bilaxy` with nameTag "Binance Dep: 0x…" (deposit addresses mis-attributed at the label
>   level); top labels are polluted (bitget 19,067 rows, bilaxy 5,005 — deposit-address dumps).
> - **On-chain check:** `0x3f5CE5FB…` balance today = 0.17 ETH — Binance rotated away from it,
>   so for CURRENT flows its absence is survivable; for HISTORICAL netflow reconstruction the
>   era-correct wallet set is missing entirely.
> - **VERDICT:** usable as a SUPPLEMENTARY tag source only. **NEVER the primary wallet set for
>   exchange-netflow construction.** cex-list is cleaner but tiny (hot wallets, 20+ venues incl.
>   KR). The desk's own `onchain_flows.py` wallet set should be diffed against BOTH — flagged as
>   the follow-up.
> - MIT licence confirmed (unchanged). Live re-scraper remains fragile/ToS-adjacent — unchanged.
>
_Superseded original grading below (kept for the record):_
### 11-OLD. eth-labels (dawsbot/eth-labels) — grade: needs-monitoring
- **Provides / replaces:** 169k+ labeled addresses (115k+ accounts, 54k+ tokens) across
  Ethereum/Base/Arbitrum/Optimism/BSC/Gnosis/Celo. Feeds exchange-netflow / whale-transfer labeling
  (Nansen/Arkham-class labels at $0).
- **Provenance:** WebFetch'd `https://github.com/dawsbot/eth-labels` directly; confirmed entry
  counts, chain coverage, and provenance (originally Etherscan's own label data, re-published) in the
  repo's own README.
- **Verify-don't-trust:** not diffed against a second labeling source this session. Static published
  snapshot is the safe artifact; the repo's own live re-scraper depends on solving Etherscan CAPTCHAs
  (fragile, ToS-adjacent) — do not rely on the live scraper.
- **Genealogy:** license MIT (confirmed) · cadence unclear exact refresh interval (115 commits,
  ongoing) · failure modes: source labels can mislabel/lag new exchange wallets since Etherscan's own
  curation is the ultimate root.
- **Grade: needs-monitoring.**

### 12. cex-list (tradezon/cex-list) — grade: **verified-clean (content cross-checked 2026-07-25) — STALE-frozen snapshot (last commit 2023-07-27), no licence file: use as REFERENCE, not adopted dependency**
> **RE-VERIFIED 2026-07-25 (EN frontier miner, in the eth-labels cross-diff):**
> `data/ethereum-mainnet.json` downloaded (200, 22,482 B) → **373 addresses / 23 exchanges**
> (incl. the KR venues). Content quality CONFIRMED against eth-labels + spot on-chain checks:
> it carries the canonical Binance wallets eth-labels is MISSING (0x3f5CE5FB…, 0xF977814e…,
> 0x28C6c062…) and its labels agreed on 237 of the 276 overlapping addresses (disagreements
> mostly benign taxonomy: HTX≡Huobi, Paxos-BUSD). **The staleness the old card feared is real
> but cuts differently than assumed: last commit 2023-07-27 means NO post-2023 wallets, so
> treat as an era-correct 2023 snapshot** — good for historical reconstruction, must be
> supplemented for current flows. No LICENSE file (unchanged): raw addresses are facts (not
> copyrightable), but do not redistribute the file itself. Verdict: the cleaner of the two
> label sources per-address, the smaller by 230x — use BOTH plus desk-owned wallet curation.
>
_Superseded original grading below (kept for the record):_
### 12-OLD. cex-list (tradezon/cex-list) — grade: UNVERIFIED
- **Provides / replaces:** would fill the ONE gap eth-labels' Etherscan-only lineage doesn't cover
  directly — curated CEX hot-wallet addresses for 20 exchanges **including Bithumb, Coinone, Korbit**
  (regional Korean coverage).
- **Provenance:** WebFetch'd `https://github.com/tradezon/cex-list` directly; confirmed the exchange
  list includes bithumb/coinone/korbit, and confirmed the ABSENCE of any license file or documented
  sourcing/maintenance methodology.
- **Verify-don't-trust:** only 4 total commits, no releases — addresses are likely stale (exchanges
  rotate hot wallets); no disclosed methodology means false-positive/negative rate is unknown.
- **Grade: UNVERIFIED.** Real find for a real gap, but not adopted until license is clarified and
  addresses are cross-checked against an independent source.

### 13–14. Community data lakes (Kaggle btcusdt, HuggingFace sebdg/crypto_data) — grade: UNVERIFIED
- Both surfaced via WebSearch only; neither opened/downloaded this session. Logged as leads for
  next cycle, explicitly NOT presented as findings. Verify plan: download the Kaggle 196-pairs 1-min
  file for one symbol/date, diff against data.binance.vision for the same interval before any use.

---

## SEARCH-SPACE EXPANSION

**New source class discovered:** cloud-provider **Open Data Parquet lakes** for raw blockchain data
(AWS Public Blockchain Data being the concrete instance found this session — `s3://aws-public-blockchain/`,
11 chains, no-auth, Athena/Redshift/SageMaker-queryable). This is structurally different from what
the desk's prior on-chain posture covered (run-your-own-RPC-node, or Dune/Flipside/BigQuery curated
SQL layers): it is a **pre-built, analytics-ready, multi-chain raw data lake with zero infrastructure
to run**, at zero cost beyond optional AWS compute if queried through AWS services directly (a local
Parquet reader avoids even that). Worth folding into future rotations for:
- multi-chain bridge-flow / L2 activity reconstruction (Arbitrum/Base/Optimism/TON data sits in the
  SAME bucket, no extra integration cost),
- as a bulk historical alternative to running the desk's own RPC fallback chain for anything
  requiring full historical backfill rather than forward-only queries,
- cross-checking `eth_public_rpc`-derived balances/flows against a second independent raw source.

Retire/deprioritize note: none this session — no source reached sustained low-yield status yet since
this is the mission's first run.

## OPEN QUESTIONS FOR NEXT CYCLE
1. Does Upbit's data survive an actual downloaded-file diff vs a live-ticker cross-check? (needs an
   actual file pull, not just doc confirmation.)
2. Is there ANY free bulk historical archive for Bithumb spot or Coincheck, or are both genuinely
   destroyed-at-source? Retry with narrower, more targeted Korean/Japanese-language queries.
3. Does a real Dune community query actually reproduce a CryptoQuant netflow number within a
   reasonable tolerance? (The single highest-value unresolved claim this session.)
4. What is cex-list's (tradezon) actual address accuracy — cross-check a sample against the desk's
   own recorder-observed deposit/withdrawal address clustering.

## NEW AXES (principal 2026-07-20 -- charter section 25; dig to exhaustion, free-first)
5. Congressional trading disclosures (Senate/House PTR public filings; Quiver-class free
   mirrors) + SEC EDGAR full-text -- regulatory/political flow as a crypto-adjacent axis
   (ETF issuers, MSTR-class proxies, miner 10-Ks with BTC treasury + energy contracts).
6. DeFi composability / forced mechanics: DefiLlama TVL flows (free API), Uniswap V3 tick-
   range liquidity distributions (public subgraphs), Chainlink oracle update latencies
   (on-chain, reconstructable) -- forced-flow + liquidation-adjacent mechanics.
7. Energy/mining physical layer: regional grid spot prices for mining hubs (ERCOT public,
   Nordpool), hashprice indices (Luxor public), ASIC resale/depreciation curves (public
   listings) -- miner-capitulation and hashprice-breakeven signal family.
8. Patent databases (Google Patents/WIPO, free) -- exchange/HFT infrastructure patents as
   leading indicators of venue mechanics changes (when relevant; low cadence).

## HUNT NOW — ADDENDA B/C/D (principal 2026-07-20; full record: FREE_DATA_ADDENDA_BCD.md)
Verify-don't-trust + liveness + Bronze rules (spec sections 4-6) bind every item. Priority order:
9.  Dev-activity factor (GH Archive x crypto-ecosystems JOIN) -- best find, owned methodology.
10. BitMEX decade archive (trades+L1 to 2014) -- longest free perp microstructure history.
11. Spot-ETF flow tables (Farside daily, Bronze snapshots -- revised silently).
12. Binance metrics positioning columns (ALREADY DOWNLOADED -- name in feature factory).
13. Deribit block-print filter (institutional options flow) + Volmex/BitVol cross-checks.
14. Fed liquidity plumbing (RRP+TGA+H.4.1 -> self-computed net-liquidity).
15. Mempool Dumpster + Xatu (historical mempool/network events, CC-0).
16. Venue-stress observables (insurance funds, PoR Bronze snapshots, status-page JSON).
17. Wikipedia pageviews + prediction-market odds (Polymarket/Kalshi) as event priors.
18. Hyperliquid position transparency + leaderboards (decaying class, forward-collect).
19. JP botter ecosystem (richmanbtc line) via OP-017 -- Prospector co-target.
20. Reddit corpus + firehoses (weak-signal registry class, regime markers only).
Signup-gated (page principal only when a pull is planned): Databento credits (surgical CME
windows), Alpaca, Kaggle datasets.


## FREE-ALTERNATIVES DIG (manual, CRO web search) -- 2026-07-22T23:21Z

Triggered by gap #48 (paid CME barely cleared; free axes ~0). Verify-don't-trust grades; nothing adopted until diffed vs ground truth.

| source | replaces | cost | grade | value |
|---|---|---|---|---|
| [coinalyze_api](https://api.coinalyze.net/v1/doc/) | Coinglass ($29-699/mo) | FREE (free key, 40 req/min) | needs-monitoring | HIGH |
| [cme_free_futures](https://finance.yahoo.com/quote/BTC=F) | the PAID CME pull flagged in gap #48 | FREE (Yahoo Finance BTC=F/ET | needs-verification | HIGH |
| [farside_etf_flows](https://farside.co.uk/btc/) | Coinglass ETF endpoint / any paid ETF-flow feed | FREE (Farside table; also Th | needs-monitoring | MEDIUM |
| [dune_flipside_onchain](https://dune.com) | Glassnode / CryptoQuant exchange-flow + stablecoin products | FREE (Dune free SQL tier, 10 | needs-monitoring | HIGH |
| [fundingpulse_apify](https://apify.com/fraktalapi/funding-pulse) | Coinglass | claims FREE public API | UNVERIFIED | LOW-until-verified (redundant with Coinalyze which is doc-verified free) |

**Headline:** the PAID CME feed (gap #48) is replaceable with FREE daily settlement (Yahoo BTC=F / Investing / Nasdaq Data Link) -- do not renew it; build the one queued cme hypothesis on free data. **Best NEW axis:** Coinalyze free API = cross-exchange funding/OI/liquidations (the desk is Binance-only today) -- feeds the queued cross-venue-dispersion sleeve at zero cost. On-chain reconstruction (Dune/Flipside/DefiLlama free) covers the Glassnode/CryptoQuant flow+stablecoin products.

---

## SESSION SUMMARY — 2026-07-24 (CN/KR/JP retail-attention batch; coverage-not-volume applied to sourcing)

A 35-item external list (CN/KR/JP social+search, on-chain graph, MEV, dev, NFT, prediction-market,
regulatory, macro sources) was reviewed against the existing catalogue. ~18 items were already
logged under different vendor names (Arkham/Dune/Flipside = on-chain flows; EigenPhi/Blocknative =
MEV/mempool; GitLab/StackOverflow/NPM = developer-activity factor #65; Telegram/Discord/Farcaster =
"crypto-native social firehoses" #49; Manifold/Metaculus = prediction markets #57; SEC EDGAR/BIS/IMF
= macro/regulatory families already ingested or catalogued). Of the genuinely-new CN/KR/JP
retail-attention layer, **one** source was built (mechanism-first, not volume); the rest are logged
here as excluded, not silently dropped (charter s27 "log every negative").

### 22. CFE regulated crypto futures complex (Cboe settlements: FBT/PBT/XBTF + FET/PET) — grade: **verified-clean (probed + full history pulled + screened 2026-07-28) — series too young to power a screen; accruing** [§33: screened -> data/cfe_regulated_basis_screen.json]
- **What it is:** the full CFTC-regulated crypto futures complex on Cboe Futures Exchange, free
  daily settlements per date: `cboe.com/us/futures/market_statistics/settlement/csv/?dt=YYYY-MM-DD`
  (keyless CSV; session C 2026-07-26 found PBT only — session D found the COMPLEX: **FBT** monthly
  BTC futures with a 4-point term structure, **PBT** Continuous BTC futures (2035 expiry,
  funding-style daily cash adjustment — a US-regulated perp analog), **XBTF** mini, **FET/PET**
  the Ether pair). Launch dates measured by probe: FBT+FET 2025-09-29, XBTF 2025-11-26,
  PBT+PET 2025-12-15.
- **Why it matters (mechanism prior):** regulated-venue basis/funding prints come from an
  access-segmented participant set (US institutions barred from offshore perps). The
  PBT-vs-offshore-perp funding SPREAD and the FBT term-carry curve are institutional-positioning
  observables the desk's carry book (offshore perp funding) cannot see. Novelty-gated 2026-07-28:
  graveyard kills (`funding_momentum`, cross-exchange funding dispersion) are OFFSHORE-perp
  constructions; nearest live relative is the carry book itself — distinct participant set,
  distinct construction.
- **History pulled:** `data/cfe_crypto_settlements.jsonl` — 2,005 rows, 207 trading days,
  2025-09-29 → 2026-07-27, ALL five products, all listed expiries per day. Derived series
  `data/cfe_regulated_basis_daily.jsonl`: spot-referenced PBT premium + front-FBT annualized
  basis (front = nearest expiry ≥7d, roll rule declared).
- **Alignment declared (charter duty):** settlement = 16:00 ET, DST-aware (20:00 UTC EDT /
  21:00 UTC EST boundary 2025-11-02/2026-03-08); spot ref = Binance BTCUSDT 1h close at that
  hour; signal forward-filled ≤3 calendar days over venue closures (honestly stale); predicts
  next-UTC-day close-to-close — 4h dead gap, forward-only, no look-ahead.
- **Stage-A screen (audited harness, ALL 4 pre-declared cells logged, levels only, no transform
  shopping):** pbt_funding_prem h1d **SCREEN-UNDERPOWERED** (n=204, IC 0.007, min-detectable
  0.137); h5d **INSUFFICIENT-DATA** (n=24); fbt_front_basis_ann h1d **SCREEN-UNDERPOWERED**
  (n=281, IC 0.016, min-detectable 0.117); h5d **SCREEN-UNDERPOWERED** (n=39, IC 0.070,
  min-detectable 0.702). **Honest verdict: uninformative in BOTH directions — no edge claimed,
  no negative recorded; the complex is 10 months old.** Full JSON:
  `data/cfe_regulated_basis_screen.json`.
- **What IS informative now (descriptives):** FBT front annualized basis mean **+6.73%**
  (std 3.78%, range **−5.67% → +15.79%** — real backwardation excursions); PBT premium to spot
  mean −0.05%, std 0.09% (the funding mechanism binds tight). Hazard for any future screen:
  PBT premium same-period corr 0.434 (spot in denominator) — orthogonalize or screen the
  PBT-minus-FBT / regulated-minus-offshore SPREAD, not the raw premium.
- **Standing plan (dated):** series accrues free daily; re-screen when powered — at current
  min-detectable-IC trajectory that is **≈2027-H2 for h1d** (n≈500). Revisit date in the §33
  sense: re-screen 2027-01-04 (n≈320) IF the desk wants an early underpowered read, else
  2027-07-01. ETH pair (FET/PET vs ETHUSDT) deliberately NOT screened this run (bounded scope;
  same mechanism, would double multiplicity) — carded here as the follow-up.
- **Legitimacy (s13):** Cboe's own public market-statistics CSVs, keyless, no login, no ToS
  click-through on the route; these are the exchange's OWN settlement prices (no vendor value
  redisseminated — the Kaiko-index distinction from T1a holds).

### 21. NAVER DataLab (Korean search-attention) — grade: needs-monitoring (built, unrun) [§33: deferred(2026-08-09) tier:3]
> **§33 DISPOSITION 2026-08-09 — THE COLLECTOR WAS RUN 2026-07-26. It did not produce an artifact,
> and the honest disposition is a dated deferral rather than a manufactured one.**
> - **RUN, VERBATIM OUTPUT:** `.venv/bin/python scripts/collect_naver_krsearch.py` →
>   `collect_naver_krsearch: no NAVER_CLIENT_ID/SECRET (env or data/secrets/naver.json) --
>   graceful skip, cycle stays green` (exit 0). `data/batch_krsearch_screen.json` **does not
>   exist**. Re-confirmed there is no key on the box: `data/secrets/` holds binance/databento/fred/
>   heartbeat/llm_panel/netlify/ngrok/ntfy — **no naver.json** — and no `NAVER_*` env var is set.
> - **THIS WAS THE CHEAPEST ITEM IN THE BACKLOG AND IT STILL COULD NOT CONVERT.** That is worth
>   recording rather than smoothing over: "built, unrun" reads like one command away, and the
>   remaining step is not technical at all. Zero code is owed.
> - **NO SUBSTITUTE PATH WAS TAKEN, DELIBERATELY.** `datalab.naver.com`'s web UI has an
>   unauthenticated endpoint behind it, and scraping it would have produced a file today. That is
>   the exact class this same session's page EXCLUDED as ToS-grey (Baidu Index, Weibo/Zhihu,
>   Coinpan/DCInside, 5ch). Producing an artifact by doing the thing the card refused to do is a
>   fake conversion, and §33.2 counts a claim without legitimate backing as unconverted anyway.
> - **UNBLOCKING STEP:** free NAVER Developers registration (a NAVER account + phone verification —
>   a human step an agent cannot complete), then drop
>   `data/secrets/naver.json {"client_id": "...", "client_secret": "..."}`. The collector is already
>   wired into the daily cadence and already uses the audited `axis_screen` harness, so the first
>   live screen lands on the next run with no further work. **Routed to GAP_REGISTER #69.**
> - Endpoint liveness re-confirmed 2026-07-25 (401 `errorCode 024, "Not Exist Client ID"` — the
>   shape of a real keyed API); nothing about the source has changed, only the key is missing.
- **Provides:** relative daily search-interest index for KR crypto terms (비트코인/암호화폐/코인),
  official NAVER Developers / NAVER Cloud Platform API.
- **Mechanism:** Korean retail sentiment/positioning propagates through a distinct information
  ecosystem from Western Crypto Twitter -- a natural attention-layer companion to the kimchi-premium
  axis the desk already treats as real and orthogonal (both Korean-venue-sourced, neither price-
  derived from the same construction).
- **Legitimacy (s13):** clean -- official keyed developer API (client_id/client_secret via free
  registration), not scraped HTML, not a login-gated session token.
- **Verify-don't-trust:** collector built (`scripts/collect_naver_krsearch.py`), wired into daily
  cadence (key-gated, graceful no-op without credentials -- same convention as collect_fred_macro.py),
  screened via the audited `libs.research.axis_screen.stage_a_screen` harness (never hand-rolled,
  charter s26). NOT yet run against the live API -- needs a free NAVER Developers key dropped at
  `data/secrets/naver.json`. Grade upgrades to verified-clean/UNVERIFIED once the first live screen
  result lands.
- **Grade: needs-monitoring** (mechanism-first, single hypothesis, zero promotion authority --
  Stage-A screen only, exactly like every other axis onboarded this way).
> **VERIFICATION ADDENDUM 2026-07-25 (EN frontier miner):** endpoint LIVE-CONFIRMED —
> unauthenticated POST to `openapi.naver.com/v1/datalab/search` returns HTTP 401 with NAVER's
> own error body (`errorCode 024, "Not Exist Client ID"`), exactly the expected shape for a
> real keyed API. `data/secrets/naver.json` does NOT exist. **Zero technical work remains; the
> SOLE blocker is a free NAVER Developers key (human step — NAVER account registration).**
> Surfaced per the bottleneck-surfacing rule: one registration unlocks an already-built,
> already-wired, already-screen-harnessed collector.

### EXCLUDED this round (found, explicitly NOT built — logged so nothing is silently dropped)
- **Baidu Index** — grade: needs-legitimacy-review. Requires a Baidu-account OAuth token refreshed
  via manual login (24h expiry, "non-Baidu-Index-authorized users get error 9016002"). This is
  credentialed/account-gated access, not a clean public API -- fails s13 the same way a paywalled
  vendor feed would. Not built without an explicit legitimacy decision (and would need the
  principal's personal Baidu account, which the desk should not request lightly).
- **Weibo / Zhihu crypto sentiment** — grade: needs-legitimacy-review. No official low-friction
  public API for either; genuine access is either paid enterprise API or HTML-scraping a
  platform-hosted community, which sits in real ToS grey zone. Not built.
- **Korean forums (Coinpan, DCInside crypto boards)** — grade: needs-legitimacy-review. Same class
  as Weibo/Zhihu -- public-but-platform-hosted community scraping, ToS-grey. Not built.
- **Japanese forums (5ch crypto boards) / Yahoo Japan realtime search trends** — grade:
  needs-legitimacy-review. 5ch is community-board scraping (ToS-grey); Yahoo Japan's "realtime
  search trends" is a portal feature with no confirmed official low-friction developer API (unlike
  NAVER, which has one) -- unconfirmed, not asserted clean.
- **Jin10 (Chinese financial news)** — grade: UNVERIFIED. Typically an app/paid-tier product;
  no confirmed free official API found this round.

**Headline:** coverage-not-volume applied to the SOURCING layer, not just hypotheses -- one clean,
mechanism-first, legitimately-public source built and queued for its first live screen, rather than
five source cards racing to add scraped social data to an already-~50-deep verification backlog.

---

## CARD 9 — USDT/CNY OTC PREMIUM (universe-map axis #76) — INGESTED + STAGE-A SCREENED
_CN frontier miner, 2026-07-26. Stage A only: **ZERO promotion authority** (two-stage law)._

**WHAT CHANGED.** Axis #76 sat catalogued-but-never-ingested since 2026-07-22 on the claim
*"no clean free API found; TradingView script is a lead, not a feed; park until a clean source
appears."* **That claim is REFUTED.** Three independent free routes exist, all keyless, all probed
200 this run. The axis is now ingested (`data/cny_otc_premium_history.jsonl`, 591 daily rows) and
screened through the audited harness. This is the screen-on-discovery leak closed on one axis:
the desk already had a live recorder (`data/cny_premium.jsonl`) holding **4 rows** — unscreenable.

**ROUTES (all keyless, 2026-07-26).**
| Leg | Route | Notes |
|---|---|---|
| OTC quote | `okx.com/v3/c2c/tradingOrders/books?quoteCurrency=cny&baseCurrency=usdt&side={buy,sell}` | 200 buy + 193 sell ads, full depth (price, availableAmount, order min/max, merchant stats) |
| OTC quote | POST `p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` | 10 rows/page |
| History | `history.btc126.com/usdt/api.php` | daily `usdt`+`usd`; **rolling ~177-row cap** — no param lifts it (10 tried) |
| Deep history | OP-019 Wayback CDX replay of *the same api.php* | recovers 2020-03-16..2021-05-07 |
| FX leg | `api.frankfurter.app` (ECB) | free, daily, back to 1999 |

**MEASUREMENT IS REAL — three constructions agree on the same date (2026-07-25/26):**
desk-computed OKX C2C mid ÷ ECB USD/CNY = **−0.623%**; btc126 published index = **−0.62%**;
desk live recorder (Binance P2P, own FX leg) = **−0.618%**.

**ALIGNMENT DECLARED (per screen-on-discovery rule 4).** btc126 stamps `23:55:01` daily, assumed
23:55 CST (UTC+8) = 15:55 UTC on date D. The screen predicts the **UTC-day D+1** return
(00:00 D+1 → 00:00 D+2): an 8h05m forward gap. **Robust to the timezone ambiguity** — if the stamp
were really UTC the gap shrinks to 5 minutes but stays forward-only, so no cell can be
lookahead-contaminated either way. Quantization checked: OTC px is 2-decimal, 1 tick = 0.147% of
price; premium std/tick = 9.5 (block1) / 4.0 (block2), both above the 3.0 usable floor — signal,
not rounding.

**ALL FOUR TRIALS LOGGED (no best-cell cherry-pick — rule 3).** Blocks screened separately; the
4.7-year gap is never bridged by the z-window.

| cell | window | n | IC | Sharpe(rev) | same-per corr | resid IC | de-contam | verdict |
|---|---|---|---|---|---|---|---|---|
| block1 h=1d | 2020-03-16..2021-05-07 | 392 | −0.0266 | +0.95(mom) | −0.084 | −0.0315 | PASS | SCREEN-UNDERPOWERED |
| block1 h=5d | 2020-03-16..2021-05-04 | 71 | −0.0652 | −0.16 | **−0.281** | −0.0514 | **FAIL** | SCREEN-UNDERPOWERED |
| block2 h=1d | 2026-01-27..2026-07-25 | 155 | **−0.0748** | **+1.39** | −0.088 | −0.0659 | PASS | SCREEN-INTERESTING |
| block2 h=5d | 2026-01-27..2026-07-25 | 36 | — | — | — | — | — | INSUFFICIENT-DATA |

**HONEST VERDICT — no promotable edge, and the best cell is NOT significant.** block2 h=1d earns
`SCREEN-INTERESTING` from the harness, but it carries `powered=false`: minimum detectable IC is
0.157 against an observed |IC| of 0.075. The IC is **not distinguishable from zero at 95%**. The
one genuinely notable feature is that **all four cells are negative** across a 4.7-year gap.

**TWO FINDINGS THAT SURVIVE THE NULL (both contradict the catalogued prior):**
1. **SIGN IS BACKWARDS.** Entry #76's prior was *"premium up = capital seeking crypto = bullish."*
   Every cell says the opposite: premium up → next-day BTC return **down** (reversal). If anything
   is here, mainland OTC premium is a *contrarian//exhaustion* mark, not an inflow confirmation.
2. **MAGNITUDE PRIOR FALSIFIED — barrier height does not set premium size.** Dispersion collapsed
   between eras: std **1.397% (2020-21) → 0.580% (2026)**, now **~4× smaller than kimchi**
   (bithumb 2.269%, coinone 2.021%). Mainland China has the world's highest capital barrier and the
   world's *smallest* stablecoin premium. The reconciling variable is **merchant-network depth** —
   393 live ads on a single venue is a deep, professionalised arb layer that grinds the premium
   flat despite the barrier. This refines the desk's own `era_crossvenue_fiat_premium_arb`
   graveyard rule (*premium tracks barrier height*): barrier sets the premium's **ceiling**,
   merchant density sets where inside it the premium actually sits.

**DISPOSITION.** Stage A earns a forward clock, never capital — and given `powered=false` this one
is weak even for a clock. Recommended: keep the existing live recorder accruing (it is already
running and is the *primary* route — see failure mode below), revisit at n≥400 live rows
(~2027-06) when min-detectable IC falls to ~0.098. **Do not size. Do not pre-register a Holm slot
on this evidence.**

**FAILURE MODE TO WATCH.** ChaiNext — the original publisher of this index family — is **DEAD**
(NXDOMAIN). btc126 is a surviving mirror, so the history route is single-point-of-failure and
undocumented. The desk's own recorder must stay primary; btc126 is backfill, not a dependency.

[§33: screened -> data/cny_otc_premium_history.jsonl]

## CN OSS EXTRACTION BATCH — 2026-07-31 (5 new axes; full record: cn_oss_extraction_20260731.md)

Verified same-day out of a principal-supplied survey of 10 CN-ecosystem OSS projects (8 real,
1 hallucinated, 1 proprietary — verdicts in the extraction record; MINE-NEVER-ADOPT applies).
Each axis carries a stated mechanism and awaits screen-on-discovery by the seat that ingests it:

1. **CN A-share flow microstructure (Eastmoney/AkShare/Tushare, free)** — northbound Stock
   Connect flows, dragon-tiger lists, **margin balances**. Mechanism: mainland retail leverage
   appetite propagates into crypto via the CN-retail channel Card 9 validated (contrarian sign);
   margin balance is a direct leverage-cycle observable orthogonal to everything collected.
2. **Liquidation-heatmap / cost-basis reconstruction** — rebuild free from the Coinalyze lead +
   OI/funding already collected; never buy the proprietary (Claw402) feed. Mechanism: clustered
   liquidation prices are pre-committed forced flow; cascade fuel measurable ex-ante.
3. **DexScreener long-tail DEX liquidity + new-listing feed (keyless)** — DEX-first price
   discovery; deployer/LP behaviour leads CEX listing flows; invisible in current venue feeds.
4. **Token-holder concentration deltas (Ethplorer/Etherscan family, free tiers)** — supply
   concentration marks accumulation/distribution before exchange netflow prints; complements the
   flat-screened Coin Metrics aggregates at wallet resolution.
5. **Perp-DEX funding, access-segmented venues (Aster/Lighter)** — participant-segmentation
   (card 22 logic, opposite end): degen-retail funding cohort vs CEX funding spread.

## ALPHA-HUNT CANDIDATES — 2026-07-31 (SCREEN-OWED, Claude family; full record: alpha_hunt_20260731.md)

These are NOT idle: each is routed here for screen-on-discovery by the next box cycle that can
reach the lake. Zero-idle = each advances to its NEXT stage (a Stage-A screen) immediately; it does
NOT mean capital (L1.6 -- a candidate is not an edge). R-rows: R0115-R0118.

1. **cross_exchange_funding_spread** (R0115, HIGHEST EV) — long funding cheap venue / short rich
   venue when |spread|>round-trip cost. Decorrelated 2nd sleeve (earns the spread, not the level).
   Data: funding on hyperliquid/bitmex/+ already collected. SCREEN-OWED: spread series → Sharpe
   after costs, per venue pair.
2. **post_liquidation_reversion** (R0116) — 5–30min after a liquidation-intensity z-score spike>k,
   does price revert a fraction of the cascade? Regime-gated on the z-score. Data:
   liquidation_listener.py owned. SCREEN-OWED.
3. **cross_venue_quote_lead_lag** (R0117, pure moat) — which venue's book-imbalance leads others'
   mid at own synchronized L2 timestamps. Extends micro_factory. SCREEN-OWED (box-local L2).
4. **event_density_promotion_clock** (R0118) — multiplier, not an edge: event-driven survivors
   clock per-event not per-day. Build into the promotion-latency path.
5. **funding_boundary_micro_reversal** — pre/post 8h-settlement drift+reversal on 2nd-tier perps.
6. **newlylisted_perp_funding_normalization** — fade extreme early funding toward the norm
   (small-cap frontier, L1.18a).
7. **high_funding_regime_carry_sizing** — size the deployed carry UP only in the detectable
   high-funding regime; pure Sharpe-per-turn on an owned edge.
8. **realized_vs_modeled_slippage_regime** — proprietary liquidity-stress gauge from tape vs
   cost_model; bootstraps on live fills (R0106).
