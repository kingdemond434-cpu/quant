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
> - **THIRD INDEPENDENT RE-VERIFICATION 2026-08-11 (owed-work worker, web agent, robots-complied):**
>   upbit.com robots.txt is a blanket `User-agent: * / Disallow: /` (allowlist: Googlebot/MSNBot/
>   Yeti/Daumoa only — Claude not named, but `*` binds), so the portal FAQ itself was NOT re-fetched
>   first-party; two independent search-index renderings agree clause-for-clause with the 07-25
>   reading (provenance MEDIUM), and the first-party launch notice (api-manager.upbit.com notice
>   5419, host §13-clean, fetched in full) itself PROMOTES backtesting as an intended use, restricts
>   only "bulk download by abnormal means or causing system load", and re-confirms both hazards
>   (listed-assets-only survivorship; files mutable without notice). Open API terms rev. 2023-10
>   (first-party PDF, static.upbit.com): copyright in all data vests in Dunamu; no clause defines
>   "commercial use". NOTHING found resolves own-account prop trading in either direction — the
>   07-25 ambiguity STANDS, verbatim. **A written-clarification route exists and is stated in the
>   notice: `historical_data@upbit.com` — the principal can get the answer in writing instead of
>   ruling on ambiguity.**
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

### 3. bitFlyer getexecutions + self-recorded candles — grade: CLOSED restricted-by-licence, destroyed-at-source for desk use (ToS READ 2026-08-01 by the JP miner; card synced 2026-08-04; deduped 2026-08-12 — the superseded ruling below is demoted to h4 so it no longer parses as a second pending card) [§33: killed -> docs/graveyard.md `jp_bitflyer_direct_recording`]
> **CLOSED 2026-08-04 (EN frontier miner, backlog sync) — THE LICENCE WAS READ 2026-08-01 AND IT
> FORBIDS THE USE. The JP miner's seat-1 run resolved what four deferrals could not, by a fully
> §13-clean route: the "never archived" claim was a WRONG CDX HOST+SLUG (`bitflyer.jp` not `.com`,
> `terms-of-use` not `terms`); corrected, Wayback capture `20190601153535` of
> `bitflyer.jp/en-eu/terms-of-use` served the document first try. Operative clause: bitFlyer
> retains all rights in *"data such as transaction prices … which can be acquired by various
> external APIs"*, bars robots/scrapers, and limits use to "internal purposes … of the Service".**
> - VERDICT: `restricted-by-licence` → no recorder is ever started; the same clause pre-kills
>   `/v1/getchats`, `/v1/getfundingratehistory`, and the Wayback-archived keyless 15-min BTC/JPY
>   series (2014-10→). AN ARCHIVE COPY IS NOT A LICENCE — availability ≠ permission.
> - MECHANISM-OF-DEATH ARTIFACT: `docs/graveyard.md` entry `jp_bitflyer_direct_recording`
>   (restored to this branch line 2026-08-04 — it was written 2026-08-01 in `bd32eda` on master,
>   which this working line forked away from at `3bf89cd` 07-29; the fork is rowed separately).
> - HONEST RESIDUAL (unchanged from the ruling): the document read is the EU entity's 2019 ToS,
>   not the JP entity's current 利用規約. RE-ENTRY CONDITION: a JP-entity ToS or explicit
>   permission that does NOT retain rights in transaction prices. The endpoints working is not
>   new information.
> - GAP_REGISTER **#68 (human page-read of the live ToS) is MOOT** — the read happened via the
>   archive; the escalation should close. Licensed substitutes already owned: Tardis `bitflyer`
>   free 1st-of-month (2019-08-30→); GMO Coin keyless ticks (2018-09-05→); bitbank candles.
>
> _Superseded deferral block below, kept for the record:_
#### 3-RULING (2026-08-01 JP miner original, superseded by the sync card above — demoted from h3 2026-08-12 so the parser sees ONE card 3). bitFlyer getexecutions + self-recorded candles — RESTRICTED-BY-LICENCE — CLOSED 2026-08-01, DO NOT BUILD

> **§33 DISPOSITION 2026-08-01 (JP frontier miner session 1) — THE DEFERRAL IS OVER. THE LICENCE HAS
> BEEN READ AND IT FORBIDS THE USE. The human page-read dependency below is DISCHARGED — nobody
> needs to open anything.**
>
> The blocker was never the licence's *existence*, it was four probes that all varied the same
> thing. Corrections to the record below, each against an artifact fetched 2026-08-01:
> - **"403 / WAF-blocked" is wrong.** TLS completes, cert verifies (`O="bitFlyer, Inc."`), the HTTP/2
>   stream OPENS, then `INTERNAL_ERROR (err 2)`; over HTTP/1.1 and IPv4 it **hangs to timeout**
>   (`code=000`). An Akamai tarpit, not a status code.
> - **"the block is not egress-specific" is right but was read backwards.** It is not about egress
>   because it is **per-hostname**: `api.bitflyer.com` and `lightning.bitflyer.com` both return
>   **200 from the identical edge IP `2a02:26f0:e80:588::2644`** that tarpits the apex. Only the
>   marketing/legal host is bot-managed. (⇒ **OP-043**.)
> - **"never usefully archived" is refuted — the CDX query used the wrong host AND the wrong slug.**
>   Pre-migration host is **`bitflyer.jp`**; slug is **`terms-of-use`**, not `terms`. Corrected query
>   returned `https://bitflyer.jp/en-eu/terms-of-use` (2019-06-01, **200**) on the first attempt.
>   (⇒ **OP-044**.)
>
> **THE OPERATIVE CLAUSE (verbatim, capture `20190601153535`):** *"The bitFlyer API is the copyrighted
> technology of bitFlyer and may not be copied, imitated or used, in whole or in part, outside of the
> API's intended use. bitFlyer retains all its rights related to its databases, websites, … **including
> chat text, the content of bitFlyer emails, and data such as transaction prices** — developed or
> provided by bitFlyer or its affiliates **which can be acquired by various external APIs**. bitFlyer
> may demand any third party stop using bitFlyer's API for any purposes not authorized by bitFlyer."*
> Reinforced by *"only for your internal purposes and solely as necessary for your use of the Service"*
> and a bar on *"any robot, spider, crawler, scraper, script … not authorized by us to access the
> Services, extract data"*.
>
> **VERDICT: `restricted-by-licence`. §13 is a HARD STOP. Do not build a bitFlyer direct-recording
> collector.** The same clause pre-emptively kills two endpoints verified live and keyless this run
> before either could be carded: **`/v1/getchats`** (real JP retail chat — clause names *"chat text"*)
> and **`/v1/getfundingratehistory`** (8-hourly JP funding — the desk's only repeat-surviving family,
> and the one most wanted). It also blocks the run's biggest find, **not carded on purpose**:
> `bitflyer.jp/api/chart/btc_jpy?start=&end=`, an undocumented keyless 15-minute BTC/JPY series, dead
> live (302) but **Wayback-captured 200 from 2015-08 (414,675 B ≈ 10 months per capture, back to
> 2014-10-16)**. Reading bitFlyer's data out of a third-party archive does not extinguish bitFlyer's
> stated rights in it — **"the Internet Archive had a copy" is not a licence.**
>
> **HONEST RESIDUAL:** the document read is the **EU entity's 2019** ToS, not the JP entity's current
> 利用規約 (JP-side `terms-of-use` paths have no CDX captures; the live host is tarpitted). This is
> bitFlyer *group's* stated position, strongly against — not a JP-entity ruling. §13 asks whether a
> licence forbids the use; the only bitFlyer terms document the desk has ever read says yes. Grading a
> restriction on the evidence we have beats a fifth deferral on evidence we cannot get.
>
> **L1.16a RE-ENTRY CONDITION:** a bitFlyer **JP-entity** ToS, or an explicit bitFlyer data-use
> permission, that does **not** retain rights in transaction prices.
>
> **LICENSED SUBSTITUTE, ALREADY OWNED:** Tardis.dev covers `bitflyer` **since 2019-08-30**, free
> first-of-month, internal research use **PERMITTED** (see entry 1's licence read). Residual gap is
> granularity (1 day/month), not availability. **Unrestricted JP alternatives found the same run:
> entry 27 (GMO Coin, free tick tape 2018-09-05→, 40 symbols) and entry 28 (bitbank).**

<details><summary>Superseded record (2026-07-25/26 deferral, kept for provenance — its factual claims are corrected above)</summary>

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

</details>

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
> **⚠️ DATA FENCE ADDED 2026-08-04 (KR frontier miner, primary-source event record): Bithumb
> mis-credit incident 2026-02-06 — an event reward was paid in BTC UNITS instead of KRW units
> (~620,000 BTC ≈ 60조원 phantom-credited at 19:00 KST; trading+withdrawals frozen 19:35–19:40;
> 1,788 BTC actually SOLD into the KRW book before the freeze and later covered from company
> assets; FSS on-site inspection 02-07). Consequences for any Bithumb-sourced series: (a) prints
> in the 2026-02-06 19:00–19:40 KST window contain a phantom-supply dump — fence them; (b) the
> freeze creates a stale/gap window through 02-07 on KRW pairs; (c) the withdrawal freeze is a
> BARRIER SPIKE — kimchi-premium constructions with a Bithumb leg will show a mechanical premium
> move that is venue-operational, not flow. Sources: Bithumb notice feed.bithumb.com/notice/1651924
> + namu.wiki incident page (velog @rivkode timeline, archived in data/velog_kr_quant_posts.jsonl).**
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

### 8. Kaiko vendor-replacement — grade: **verified-clean (method reconstructed on the TRUE constituent set, agreement bands MEASURED; residuals declared: LMAX leg forward-only, published prose pins the fixing only to ~5 bps — re-graded 2026-08-04)** [§33: wired tier:1 -> data/kaiko_vwm_reference_rate.jsonl]
> **RE-RUN EXECUTED 2026-08-04 (EN frontier miner) — the 07-26 correction's "RE-RUN REQUIRED
> against the true constituent set" is DONE. Artifact: `data/kaiko_true_constituent_rerun.json`
> (21 trials, EVERY construction logged, none cherry-picked). Design: same-tape comparisons on a
> 3600s fixing at 2026-08-04T15:05Z — TRUE set minus LMAX (bitstamp 2,062 + kraken 4,307 +
> crypto.com 13,695 + gemini 443 trades) vs the PRIOR set (coinbase 37,936 + bitfinex 3,565 +
> kraken + bitstamp) × published params (10 partitions, inverse-time weights) vs the desk's prior
> invented params (12 partitions, linear ramp); plus a HISTORICAL fixing 2026-08-03T20:00Z
> (16:00 ET) on a 3-of-5 tape vs the PBT futures daily settle.**
> - **CONSTITUENT-SET EFFECT: 0.30 bps** on calm tape. The 07-26 objection (2-of-5 overlap,
>   coinbase 80% of tape and not a constituent) was methodologically right and MEASURABLY SMALL —
>   in calm conditions the venue swap barely moves the fixing.
> - **PARAMETER EFFECT: 4.34 bps** (published vs invented params, same tape) — the desk's invented
>   parameters were ~14× the error source the constituent set was. Joint effect vs the prior
>   artifact's exact construction: 4.00 bps.
> - **THE PUBLISHED PROSE IS ITSELF AMBIGUOUS TO ~4.7 bps:** "weights inversely proportional to
>   time" supports both 1/rank and 1/midpoint-age readings, which differ by −4.75 bps here. So
>   WITHOUT Kaiko's exact formula, no reconstruction can claim better than ~5 bps fidelity —
>   a vendor-side bound, measured and declared, not a desk defect.
> - **VWM vs desk VWAP on the same true tape: 16.4 bps** this window — re-confirms the outlier-
>   resistant estimator is a real value-add (the 07-26 stress finding stands).
> - **VS A PUBLISHED NUMBER:** 3-of-5 fixing at 08-03 16:00 ET = **+8.5 bps vs PBT/Z35 daily
>   settle 63,832.00** (Cboe settlement CSV, free per-date:
>   `cboe.com/us/futures/market_statistics/settlement/csv/?dt=YYYY-MM-DD`; 07-24 was 64,156.00 —
>   route live and current). DECLARED: the PBT settle is a FUTURES settle (basis-contaminated),
>   so this is a sanity BAND, not a tracking proof. **No free intraday dissemination of the Kaiko
>   index exists: Cboe's us_indices API (2,483 definitions) carries CM, Lukka and CoinRoutes
>   RealPrice families but ZERO Kaiko entries** — the one BMR administrator NOT free through the
>   exchange is the one whose index underlies Cboe's own future.
> - **CONSTITUENT TAPE DEPTHS (route facts from session C 07-26 + today):** crypto.com
>   `public/get-trades` keyless, `end_ts` backward pagination verified, archive floor measured
>   between 1,370–1,420d (~3.8 YEARS of free tick history on a true constituent); **gemini's
>   public tape reaches back only ~40 min** (probed today: `since=` 19h ago returned the most
>   recent 43 min — corroborates session C's 0.67h; an archive floor, not a pagination bug);
>   **LMAX Digital: destroyed-at-source** (no public historical trades endpoint, forward WS only —
>   unchanged, a recorder remains the only path to that leg).
> - REMAINING OPEN, NAMED: nothing technical. The exact weight formula is vendor-side opacity
>   (bounded at ~5 bps above); the LMAX leg is a WIRING decision (start a recorder), not a
>   verification step.
>
### 8. Kaiko vendor-replacement — grade: **verified-clean (reconstruction executed + rulebook-verbatim methodology diff + stress test; re-graded 2026-07-31)** [§33: wired tier:1 -> data/kaiko_vwm_reference_rate.jsonl]
> **VERIFICATION CLOSE-OUT 2026-07-31 (litminer run 4 — this completes the backlog's "technical
> check: docs + endpoint" and the grade upgrade is earned, not administrative):**
> - **Docs half:** rulebook interior extracted from primary PDF + ESMA register independently
>   confirmed (run 3, `deep_sweep/T1a_kaiko_verification.md`); calculation rule re-read VERBATIM
>   from the vendor page 2026-07-26 (recency-weighted cross-partition average, not flat TWAP).
> - **Endpoint half:** replacement path DEMONSTRATED live — 132 fixings computed from a 174,199-trade
>   4-venue keyless public REST tape, artifact on disk (`data/kaiko_vwm_reference_rate.jsonl`,
>   confirmed non-empty 2026-07-31). Stress test: injected 5%-off print at 2% of window volume moves
>   VWM+TWAP 0.1 bps vs desk VWAP 9.8 bps (~100×) — the reconstruction exhibits the outlier
>   resistance the published rule is designed for.
> - **RESIDUAL GAP, documented per the free-frontier axiom (search run 2026-07-31, not a default):
>   fixing-level diff vs Kaiko's own published values.** Bulk/API fixing history is PAID-ONLY
>   (docs.kaiko.com historical-prices endpoint = keyed; stream replay = 72h). **FREE route found:
>   `explorer.kaiko.com` displays current BRR values without login** (BTC BRR 64,653.57 USD observed
>   2026-07-31, page dated 30/07/2026, with 1w/1m/1y chart views). Verification plan for a future
>   run: re-run the reconstruction over a fresh window and spot-diff its fixing against the
>   explorer-displayed BRR at the same timestamp — a one-observation ground-truth touch, free.
>   ToS-check the explorer before any STANDING collection (spot-read for verification is ordinary
>   public-web use; a scheduled scraper is not the same act).
> - NOTE: raw-ticks component re-graded with the card: the desk's replacement for Kaiko tick data
>   IS the 4-venue keyless tape, which the reconstruction run exercised end-to-end. No Kaiko
>   product is adopted; nothing here grants promotion authority to anything.
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

### 21. NAVER DataLab (Korean search-attention) — grade: needs-legitimacy-review (account-gating: the SOLE blocker is a free NAVER Developers key = a human registration step, GAP #69; technical verification COMPLETE — endpoint live-confirmed keyless 401/errorCode 024 on 2026-07-25, 2026-07-26 and 2026-08-04; collector built+wired, zero code owed) [§33: deferred(2026-08-25) tier:3]
> **§33 THIRD DEFERRAL 2026-08-11 (brain-hunter seat), blocker UNCHANGED and re-verified:**
> `data/secrets/` listed this run — **no `naver.json`**, no `NAVER_*` env. The sole blocker
> remains the principal's free NAVER Developers registration (GAP #69). Zero desk-side work owed;
> deferral date is a re-check date, not a work estimate. Escalation stands via GAP #69.
> **RE-QUEUED 2026-08-04 (EN frontier miner, backlog sync): this card sat in the TECHNICAL
> verification queue and was re-verified identically on three separate runs — a treadmill. There
> is no technical work left (the parser's own taxonomy files account-gating under the
> legitimacy/policy queue, which is where the remaining HUMAN step honestly belongs). Today's
> probe: unauthenticated POST → HTTP 401, NAVER error body `024 Authentication failed`, keyless,
> live. Unblock = GAP #69 (NAVER account + phone verify + drop `data/secrets/naver.json`); the
> key also unlocks `/search/blog` + `/search/cafearticle` = 3 KR grounds, not 1 axis.**
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

#### 21-RECORD (superseded twin, demoted from h3 2026-08-12 so the parser sees ONE card 21 — the live card with the honest needs-legitimacy-review grade is above the CFE entry). NAVER DataLab (Korean search-attention) — needs-monitoring (built, unrun)
> **§33 THIRD DEFERRAL 2026-08-11:** same single blocker as the twin card above — key absent
> (`data/secrets/` checked this run), principal-blocked (GAP #69). Re-check 2026-08-25.
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
> **LIVENESS RE-CONFIRMED 2026-07-31 (litminer run 4):** POST to `openapi.naver.com/v1/datalab/search`
> → HTTP 401 again, unchanged keyed-API shape. Card honestly STAYS pending-verification: the first
> live screen cannot run until the free NAVER Developers key (human step, GAP #69) lands.
> §33 deferral 2026-08-09 intact, not expired.
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

## 2026-08-04 — JP miner s1-on-branch: two rows

### binance premium-index klines (the PI under the FR) — free keyless resolution upgrade on an OWNED axis
- WHAT: Binance futures serves premium-index candles keyless (`/fapi/v1/premiumIndexKlines`,
  1m→1d intervals) — the minute-sampled divergence series FR is COMPUTED from. The desk's
  funding axis currently reads settled FR (8h prints, clamp-quantized: any PI in
  (−0.04%,+0.06%) prints as 0.01%; see improvement_inbox 2026-08-04). PI restores the
  information the clamp destroys and reveals intra-window sign flips the settled print hides.
- MECHANISM PRIOR (stated): carry/positioning signals built on FR inherit a quantizer;
  PI-based construction should dominate FR-based construction wherever the dead-band binds —
  testable as a screen-vs-screen comparison on the SAME windows (§26 construction-logging:
  both cells count).
- STATUS: catalogued + routed; Stage-A comparison NOT run this run (bounded-scope: this run's
  screen budget went to the 24h-lag contrarian cells, both logged SCREEN-WEAK; Binance 429 ban
  expired 08-02 so pulls must be gentle). [SUPERSEDED 2026-08-12 — see disposition below]

**DISPOSITION 2026-08-12 (JP miner, matured deferral worked on its due date+1). The 08-04
mechanism prior is CONFIRMED and the prize is MEASURED. `[§33: screened -> data/jp_funding_clamp_census.json]`**

- **THE CLAMP IS VERIFIED, NOT ASSUMED (positive control).** `F = P + clamp(I − P, ±0.05%)`, so
  `P ∈ [I−0.05%, I+0.05%]` collapses to `F = I` EXACTLY. Reconstructed the settled rate from 1m
  `premiumIndexKlines` averaged over the preceding window: **BTCUSDT 49/60 and DOGEUSDT 46/60**
  windows match to 2e-5. The residual misses are the averaging method (Binance uses an
  impact/time-weighted average; a plain mean of 1m PI closes is an approximation) — the model is
  verified, the misses are explained.
- **ALIGNMENT, DECLARED (L1.46):** `fundingTime` = PI-kline open **+1 ms**, so the rate settled at
  T is computed from the window **[T−8h, T)** — it belongs to the PRECEDING bar. Joining it to the
  bar that OPENS at T is a one-window look-ahead. (08-04 flagged OKX/BitMEX pay one period late;
  this is the Binance-side statement, now measured rather than asserted.)
- **HOW MUCH INFORMATION THE PRINT DESTROYS — owned panel** (SCANNED denominator: **10 symbols /
  68,893 8h windows / 2019-09-08→2026-06-20**; 10 is a small denominator and is declared, L1.57):
  **35.6% of settled prints are exactly 0.0001 and 6.1% exactly 0.0 → 41.6% carry ZERO magnitude
  information.** The censoring is INFORMATIVE, not random: the dead band *is* the low-premium
  region, so precisely the small-premium observations are collapsed onto a constant. Any
  regression or IC using settled FR as a continuous regressor is fitting a variable that is FLAT
  across its entire middle range.
- **AND IT DECAYS — the finding that changes what this axis is FOR.** Share exactly 0.0001 by year:
  **2019 68.8% → 2020 43.4% → 2021 41.1% → 2022 31.3% → 2023 43.9% → 2024 39.6% → 2025 26.1% →
  2026 10.7%.** So the PI upgrade is worth most to HISTORICAL work (up to two-thirds of windows
  censored) and least to live signalling today (~11%). **This is a backtest-integrity upgrade
  first, a live-signal upgrade second** — the opposite of how the 08-04 card framed it.
- **LIVE WHOLE-UNIVERSE CROSS-SECTION (one instant, 812 USDT-M perps, BTCDOM excluded):**
  **559/812 = 68.8% sit on one of THREE tie constants** — 0.00005 (n=270, of which 268 are 4h
  interval), 0.00000 (n=234, 227 8h), 0.00010 (n=56, all 8h). Only **255 distinct funding values
  exist across 812 symbols.**
- **THE TIE-BREAK TEST — why this is worth doing at all.** Inside the 56-name group ALL printing
  the identical `0.00010000`, the mark-vs-index premium still spans **−45.4 bps to +29.5 bps (74.9
  bps of dispersion)**. The tie is an artifact of the clamp, not an economic equality, and PI
  orders it. **This is the root cause of a defect the desk has already PAID for:** desk memory
  records "42 perps sat exactly at the 1bp floor; 'hold while in top-60' made membership random →
  159 closes in week one, fees −$60 against +$39 of funding". Those names were not at a *floor* —
  they were **censored at the dead-band constant**, and the fix was applied to the hysteresis
  rather than to the ranking variable. CAVEAT, stated because it decides deployability: the
  dispersion is concentrated in THIN names (ONE, MTL, BNT, BAND, GTC) where this desk has been
  burned on fees and capacity — the tie-break is real information, **not automatically tradeable**.
- **BONUS FINDING, and it corroborates L1.47 with a COUNT.** L1.47 warns that `held / 8.0`
  under-counts because "Binance sets 4h for many high-funding alts". Measured: **426 of 812
  (52.4%) are on a 4-hour interval and 2 on 1-hour — only 385 (47.4%) are actually on the 8h the
  arithmetic assumes.** "Many" is the MAJORITY. 4h names also carry more funding per day (median
  +0.000300/day vs +0.000000/day for 8h names), confirming the "4h is set for the hot alts"
  direction. Cross-sectional ranking on the RAW print mixes units, but honestly: the effect on
  top-N selection is **modest** (Spearman 0.959 vs a per-day rank; top-40 overlap 37/40) — the
  large error is in the ACCRUAL, which is L1.47's ground, not the ranking.
- **EV + novelty, run BEFORE any further screen (fixing 08-04's recorded ordering slip):**
  premium-index tie-break on the censored cross-section → **EV 0.0193 QUEUE** (p_survive 0.48,
  breadth_f 1.673, tags funding_family+new_orthogonal_data), **novelty 0.726, not redundant**
  (nearest `grave:cross-exchange funding dispersion`, sim 0.274, n=231 priors).
- **NOT PROMOTED, AND THE SCREEN IS NOT DONE.** This run measured the PRIZE (how much information
  the print destroys) — it did NOT run the construction-vs-construction IC comparison, because
  that needs a multi-day polite PI backfill the H8 lake does not hold. Two-stage law: zero
  promotion authority here regardless. **Next owner's job:** backfill 8h PI for the 10-symbol H8
  cohort, then screen PI-construction vs FR-construction on the SAME windows — both cells are
  DSR-counted trials (§26 construction logging).
- ALIGNMENT NOTE for whoever runs it: OKX/BitMEX apply FR one period LATE; Binance immediate —
  declare per venue before any join (§26(4)).

### qiita 仮想通貨botter advent calendar 2021-2025 — JP practitioner post-mortem corpus, mapped
- WHAT: 187 entries across 5 years mapped to data/jp_botter_advent_calendar.jsonl (year,
  series, day, title, author, url, host; hosts: note.com 91 / qiita 45 / zenn 24, all
  robots-clean this session). The JP record is structurally a POST-MORTEM archive (botters
  publish exhausted edges) → mine for deaths, decay dates, method defects. Adventar-hosted
  earlier years HARD-STOPPED (ClaudeBot named in robots, Cloudflare managed block).
- YIELD THIS RUN (5 full reads): graveyard ×3 (SFD boundary game dead-at-source w/ transferable
  class probe; intraday anomaly pair; ATR-limit timeframe-migration chain), funding-mechanics
  fence checklist (R0021), watchlist card ×1, JP lexicon seeded from observed usage.
  [§33: wired -> data/jp_botter_advent_calendar.jsonl]
- REMAINING: ~180 entries unread; highest-priority queue in prospector_coverage JP session
  note (next-run first items: 2023 s2d21 domestic-vs-overseas short-horizon dynamics;
  2025 s2d19 GMO-Bybit pair study — touches our LICENSED GMO tick source; 2022 s1d3+s1d21
  regression-bias pair; 2023 s1d24 limit-optimization under jumps).

### 22. aigu + ProBitForge (principal-named CN sources) — grade: UNRESOLVABLE, killed with a NAMED re-entry condition [§33: killed -> docs/graveyard.md `cn_aigu_probitforge_unresolvable`]
> **§33 KILLED 2026-08-11 (brain-hunter seat), mechanism not mood:** four independent searches
> (EN descriptive, EN exact-handle, CN descriptive, CN practitioner-corpus) resolve NEITHER
> entity; the only name-space collision is an active impersonation surface (ProBit Global scam
> warnings). A miner cannot be pointed at an address that does not resolve, and seeding a hunter
> with an unresolvable name fabricates coverage (this card's own analysis). **Re-entry condition
> (L1.16a, named):** one line from the principal — a URL or exact platform handle — converts the
> graveyard entry back to `pending-verification` immediately. Killing ≠ claiming the sources do
> not exist; it is retiring an unactionable pointer from the owed-work queue.

- **BRIEF:** principal named two sources to mine constantly *"if beneficial"* — **aigu** (described as
  a Chinese AI crypto quant research lab doing transparent paper trading, strategy evaluation and
  multi-agent experiments) and **ProBitForge** (described as publishing engineering posts on
  AI-driven crypto research systems, memory architectures and automated strategy development).
- **RESULT: NEITHER RESOLVES.** Four independent searches — English descriptive, English
  exact-handle, Chinese descriptive (`爱谷 AI 量化 加密货币 实验室 多智能体`), and Chinese
  practitioner-corpus — returned no entity of either name. "ProBitForge" collides with **ProBit
  Global**, an exchange whose own help centre states it has PERMANENTLY TERMINATED service and that
  any account claiming to represent it on social media is a scam. That collision is a reason for
  more care, not less: a miner pointed at a plausible-but-unverified handle in that name-space is
  pointed at an active impersonation surface.
- **GRADED: UNRESOLVED — do not adopt, do not crawl, do not seed the hunter.** Recorded rather than
  quietly dropped, per this file's own standard ("logged honestly as gaps, not painted over"), and
  per WS-005: absence must resolve to *not measured*, never to a clean verdict. **This is NOT a
  claim the sources do not exist** — a private account, a WeChat 公众号 (structurally unindexed), a
  Telegram channel or a very new handle would all produce exactly this result. It is a claim that
  the desk cannot presently point an automated miner at them, which is a different and weaker
  statement. **UNBLOCKED BY ONE LINE FROM THE PRINCIPAL:** a URL or exact platform handle converts
  this card to `pending-verification` immediately; nothing else is needed.
- **WHY THE HUNTER WAS NOT SEEDED ANYWAY.** `kimi_hunter` mechanically debits its source on a
  finding that maps to a family kill. Seeding it with an unresolvable name means either it invents
  a source (the worst outcome — an unsourced claim wearing a citation) or it silently mines nothing
  while the coverage file records the vector as EXPLORED, which retires the vector for
  `_VECTOR_COOLDOWN_D` days. A fabricated exploration is worse than no exploration, because it
  ALSO blocks the real one.

### 23. 中文 practitioner corpus (thuquant index / 数量技术宅 / 土法炼钢) — grade: verified-reachable (all three, 2026-08-11); corpus dig owed to the CN seat [§33: deferred(2026-08-18) tier:2]
> **§33 VERIFICATION DONE 2026-08-11 (brain-hunter seat), dig deferred to the CN miner seat:**
> (1) `cnblogs.com/robots.txt` — `User-Agent: * / Allow: /`, no agent disallowed; (2)
> `quant67.com/robots.txt` — `User-agent: * / Allow: /` + sitemap, fully permissive; (3)
> `github.com/thuquant/awesome-quant` — EXISTS, **MIT**, 5.6k stars, README indexes CN quant
> resources by category (数据源/数据库/量化交易平台). All three cleared the robots/licence
> reachability bar this run — the card's own "no robots.txt check, no licence read" gap is
> CLOSED. What remains is the language-depth CORPUS DIG (graveyard-ore first: sljsz's strategy-
> decay posts), which is the CN seat's ground — deferred(2026-08-18) to its next run. The §13
> caveat on WeChat/Zhihu (GAP #80, anti-bot ruling owed) is untouched by this verification: these
> three grounds need no gate defeated.

- **THE SUBSTITUTES, which do resolve, and why this is the same asset class.** The brief's intent —
  a constantly-mined Chinese practitioner corpus — is directly served by sources that verifiably
  exist. The precedent is this desk's own `jp_botter_advent_calendar` card: 187 JP entries mined as
  a POST-MORTEM archive yielded three graveyard entries, because practitioners publish edges they
  have already exhausted. Chinese-language 量化 writing has the identical shape and is currently
  UNMINED by this desk.
  1. **`thuquant/awesome-quant`** — 中国的Quant相关资源索引. An INDEX, so it is a breadth multiplier
     rather than a finding source: mine it for the source list, not for claims.
  2. **`cnblogs.com/sljsz` (数量技术宅)** — carries `再谈量化策略失效的问题` ("strategy decay,
     revisited"). **Highest priority of the three, and the reason is the desk's doctrine rather
     than the author's reputation:** writing explicitly about WHY A STRATEGY DIED is graveyard ore,
     and the graveyard is the one corpus this desk mines for transferable kill-conditions rather
     than for candidates.
  3. **`quant67.com` (土法炼钢兴趣小组)** — crypto strategy notes incl. funding-rate arbitrage,
     cross-exchange and DeFi yield. **CAUTION, and it is a real one:** funding-rate arb is the
     desk's OWN live strategy and `{"binance","funding"}` is a FORBIDDEN_SET in `kimi_hunter` —
     crowded beyond usefulness. Mine this for MECHANICS and failure modes (the fence checklist
     shape that R0021 took from the JP corpus), never for the signal itself.
- **STATUS:** all three catalogued, NONE verified — no robots.txt check, no licence read, no
  endpoint test has been run this session. They enter the ordinary
  catalogue → verify → resolve pipeline (`scripts/source_backlog_next.py`), which is the same bar
  every other source on this page had to clear. Cataloguing is not adoption.
- **§13 NOTE, stated before anyone hits it:** WeChat 公众号 content is structurally hostile to
  automated access and Zhihu serves an anti-bot gate. Row #80 of the GAP register is an OPEN,
  UNRULED question on exactly whether defeating an anti-bot gate is inside §13. Until the principal
  rules, these are read by hand or not at all — the ruling is not pre-empted by pointing a crawler
  at them first.

### 24. Foreign AI-quant RESEARCH SYSTEMS (VeighNa/vnpy.alpha, Qlib, JP/KR equivalents) — grade: verified + MINED (Qlib 2026-08-11; **vnpy.alpha code mined 2026-08-13**) [§33: wired -> docs/research/search_operator_library.md `qlib-alpha158` + `vnpy-alpha-dsl`]
> **§33 CONVERTED 2026-08-13 (CN frontier miner s8) — the vnpy HALF, which the 08-11 run left
> unread.** The 08-11 conversion read vn.py's LICENCE but mined only Qlib files (`qlib/data/ops.py`,
> `contrib/data/loader.py`, `contrib/data/handler.py` — all three Qlib paths). `vnpy/alpha` itself
> — a 12-file research system with a feature-expression DSL, a factor library, models, a
> backtester and an artifact store — was never opened. Now read in full → operator library anchor
> `vnpy-alpha-dsl`. **§13: MIT, read from the canonical LICENSE this run.**
> **THREE THINGS THAT CHANGE WHAT THIS CARD CLAIMS:**
> 1. **"Remaining diff" #2 below is REFUTED for vnpy.alpha.** It claims these systems have *"a
>    rolling walk-forward harness wired to the enumerator"*. vnpy.alpha has **none** — zero hits
>    for rolling/walk-forward/refit/retrain/expanding/fold across the whole module; it has a
>    STATIC three-way split and `lab.py` is a persistence layer, not a harness. The desk's gap is
>    real, but this system is not evidence for it and there is nothing here to port. (The Qlib
>    half of the claim was not re-tested this run and stands unexamined.)
> 2. **"Remaining diff" #1 (the feature-expression DSL) now has a 285-line reference
>    implementation**, and its architecture is the finding: an operator-overloaded proxy class +
>    `eval()`, no parser, no AST. Copy the proxy pattern; **reject `eval`** — generated or
>    LLM-authored expressions flowing into `eval()` is arbitrary code execution.
> 3. **The DERIVES-FROM is recorded so this is never miscounted as convergence:** `alpha_158.py`'s
>    own docstring says *"158 basic factors from Qlib"*. The factor set is DERIVED; only the
>    polars ENGINE is independent, so the divergences carry the information (GAP-#85 echo trap).
> **Corroborations worth their place:** the negative-delay leak rule is now confirmed in a second
> independently-written framework (family-level, not a qlib quirk); the Slope/Rsquare/Resi trio is
> independently present (strengthens its ranking as the real transform gap, with a closed-form
> recipe); and **neither framework ships group operators** — both presuppose a sector map, which
> corroborates the crypto grouping map as THE blocking input rather than a nicety.
> **The binding-constraint caveat stands UNCHANGED** — 16,560 trials blocked on transport. This
> extraction widens nothing until that moves.
> **§33 CONVERTED 2026-08-11 (brain-hunter seat).** The card's own owed verification axis is
> CLOSED: **Qlib LICENSE read = MIT (Microsoft); vn.py LICENSE read = MIT (Xiaoyou Chen)** —
> both from the canonical files this run, not "understood to be" (the row-#79 discipline). And
> the METHOD source was actually mined, not just verified: `qlib/data/ops.py` (1,681 lines, every
> operator class), `contrib/data/loader.py` (Alpha158 blocks) and `contrib/data/handler.py`
> (label + processors) read in full → extraction with exact semantics, five elided-semantic
> rules for reading mined qlib-dialect expressions (N-type-keyed Rolling, min_periods=1,
> future-Ref labels, negative-Ref leak rule, Greater=max), and per-family crypto analogues now in
> the Search Operator Library under anchor `qlib-alpha158`. The card's "remaining diff" list
> gains one measured item: the **Slope/Rsquare/Resi regression trio** is a concrete transform
> axis `combination_engine` lacks (adoption via pre-registration, universe cost priced first).
> The binding-constraint caveat (16,560 trials blocked on transport) stands UNCHANGED — this
> extraction widens nothing until that moves.

- **BRIEF (principal, 2026-08-06):** hunt the best Chinese/Japanese/etc AI-quant systems and *"copy
  their best research processes"* — explicitly the research operating system, not their signals.
  Named: **VeighNa (vn.py) 4.0 + `vnpy.alpha`** (feature-expression DSL, batch factor generation,
  ML templates, research lab, Alpha158-style factor sets) and **Microsoft Qlib** (dataset
  architecture, factor pipelines, experiment tracking, rolling validation, alpha-mining workflow).
- **A NEW SOURCE CLASS FOR THIS PAGE, worth saying out loud.** Every other card here catalogues a
  DATA source. This one catalogues a METHOD source: the artifact to extract is an architecture, and
  the "endpoint test" is a code read, not a pull. It is entered here anyway because the
  catalogue → verify → resolve discipline is what stops a named idea sitting unexamined, and that
  applies to a design as much as to a feed.
- **VERIFICATION IS A LICENCE READ FIRST, and the desk has been bitten here.** Qlib is MIT; vn.py
  is understood to be MIT/Apache-family. NEITHER HAS BEEN READ THIS SESSION, so both are UNVERIFIED
  on exactly the axis that killed the Coin Metrics adoption (row #79: a favourable read of a
  licence the desk had recorded wrong in its own favour). Copying an ARCHITECTURE is not copying
  code and carries no licence duty; lifting an implementation does. That distinction must be made
  before anything is ported, not after.
- **WHAT THE DESK ALREADY HAS, so the port is a DIFF and not a rebuild.** Checked against the tree
  rather than assumed: `hypothesis_engine` + `hypothesis_novelty` (generation, Jaccard
  de-duplication), `idea_ranking_engine` / `research_allocator` / `research_roi_engine`
  (prioritisation by information return), `research_memory` + `research_graph` (knowledge base),
  `alpha_family_tree` / `alpha_dna` / `strategy_similarity_engine` (lineage, redundancy),
  `concept_evolution_engine` (cross-pollination), `crowding_intelligence` / `capacity_intelligence`,
  `feature_drift_engine` / `half_life` / `lifecycle` (retirement), `libs/discovery/`
  (monte-carlo survival, parameter stability, fragility, regime diversification), the validation
  layer (DSR, PBO, CPCV, White's Reality Check, Romano-Wolf), plus the graveyard, mechanism board
  and pre-registration discipline. **The meta-research layer is not missing.** A port that
  re-implemented it would be duplication wearing the costume of progress.
- **THE ONE COMPONENT THAT WAS GENUINELY MISSING, now measured and closed.** `HypothesisEngine`
  walks a fixed template dict and can emit **7 hypotheses total from 13 features**, ever, without a
  human writing another template — while everything downstream is built for a large stream. The
  funnel was wide everywhere except at its mouth. `libs/alpha_factory/combination_engine.py`
  (2026-08-06) enumerates (feature × feature × operator × horizon × regime): the same 13 features
  now yield **14,040** distinct candidates. That is the "thousands of unique combinations" the
  brief asks for, and it is the piece a Qlib/vnpy.alpha read would have pointed at.
- **REMAINING DIFF, honest and ranked** — the two things those systems have that this desk does not:
  1. a **feature-expression DSL** (`rank(volume_change / ATR)` as a first-class parseable object,
     so the operator set is open rather than the fixed five enumerated today);
  2. a **rolling walk-forward harness wired to the enumerator**, so a space is swept across folds
     automatically rather than a study at a time.
  Both are real gaps. Neither is the binding constraint.
- **THE BINDING CONSTRAINT IS UNCHANGED AND MUST NOT BE OBSCURED BY THIS CARD.** 16,560
  pre-registered trials, ZERO run, blocked on research data that does not reach an analysis clone.
  A wider generator increases the number of untested hypotheses; it does not test one of them.
  Ranking a DSL above the transport would be optimising the part that is already ahead — the exact
  substitution WS-004 names, and the reason this card is graded UNVERIFIED rather than actioned.

### 25. EODHD.com (paid EOD/intraday vendor, $100/mo) — grade: KILLED as a purchase; coverage docs remain a free index [§33: killed -> docs/graveyard.md `eodhd_paid_vendor`]
> **§33 KILLED 2026-08-11 (brain-hunter seat), mechanism:** L1.11 — the moat law forbids
> purchasing commercial data outright, and this card's own analysis shows the free-first
> prerequisite (documented failed free hunt on the equity axis) has never been run, so the paid
> exception cannot even be claimed. For crypto it adds nothing over owned keyless Binance series.
> The one live value — reading its coverage docs as a FREE INDEX of what data exists — is already
> a validated technique in the Search Operator Library and needs no subscription. **Re-entry
> condition (named):** the desk expands to an equity/cross-asset book AND a documented free hunt
> on that axis fails at the charter bar.

- **WHERE IT CAME FROM:** a Reddit post claiming four backtested strategies built on 10 years of
  EODHD data. The strategies themselves were REJECTED by the claim screen
  (`libs/research/claim_screen.py`) — one reported out-of-sample BEATING in-sample by 47%, which
  means the held-out window was easier rather than the strategy better, and none carried a
  buy-and-hold benchmark. **Cataloguing the SOURCE is independent of rejecting the CLAIMS**, and
  keeping those two apart is the point of this card.
- **WHAT IT IS:** end-of-day and intraday history for equities, ETFs, forex and crypto, plus
  fundamentals, splits and dividends.
- **FOR CRYPTO IT ADDS NOTHING.** Every series this desk uses — klines, funding, OI, long/short,
  taker flow, basis — is already free and keyless from Binance. Its value would be the EQUITY /
  ETF / cross-asset axis, which is a different desk from the one that exists.
- **IT FAILS THE STANDING TEST AS THINGS STAND (DIGGING_CHARTER, FREE-FRONTIER AXIOM):** paid is a
  last resort permitted only by the evidence-gated exception AFTER a documented free hunt has
  failed. No free hunt has been run on the equity axis, so the exception cannot be claimed —
  not because the vendor is bad, but because the prerequisite is missing.
- **THE POSTER'S OWN SENTENCE IS THE ARGUMENT AGAINST RENTING:** *"I purchased the data for $100
  monthly and it just expired."* He can no longer re-run his own backtests. A rented dataset is a
  result that stops being reproducible the moment you stop paying, which is precisely why this
  desk records its own tape and treats the order-book archive as the moat.
- **THE FREE MOVE THAT IS AVAILABLE NOW**, and it is already in the Search Operator Library as a
  validated technique: *read a paid vendor's coverage documentation as a free INDEX of what data
  exists*, then hunt each axis free. EODHD's coverage docs are worth reading. Its subscription is
  not, yet.
- **STATUS:** catalogued, NOT verified — no licence read, no ToS read, no endpoint test, no free-
  alternative hunt. Enters the ordinary catalogue → verify → resolve queue. Cataloguing is not
  adoption.

### 26. Kraken downloadable historical OHLCVT archive (2015→, all timeframes, free) — grade: verified-live (support article read 2026-08-11); licence UNSTATED, bulk ingest owed [§33: deferred(2026-08-25) tier:3]
> **§33 VERIFICATION DONE 2026-08-11 (brain-hunter seat), ingest deferred:** the support article
> EXISTS and matches the claim — OHLCVT CSVs in ZIP archives at **8 intervals (1/5/15/30/60/240/
> 720/1440min)**, span "from each market's opening to the present", delivered via **Google Drive**
> (full-history archive + quarterly-update folder), no price named. Two honest corrections to the
> card: the "2015" start is NOT stated by Kraken (span is per-market-opening — potentially
> earlier); and the article carries **no data-licence language at all**, so the licence read owed
> at ingest is against Kraken's general ToS (row #79 discipline: read it, never assume in our
> favour). BLOCKER, named: bulk Google-Drive download + lake ingest needs a collector-capable run
> with disk budget — deferred(2026-08-25). The three declared uses (depth parity on an in-use
> axis, second venue for ETH/BTC rotation falsification, pre-Binance-futures 2015-2017 coverage)
> stand unchanged.

- **THE GAP THIS EXPOSES, and it is a real one.** `FREE_DATA_ALTERNATIVES_SPEC` names
  "exchange-native dumps & archives ... from every major AND regional venue" as source category
  **#1**, dug to exhaustion EVERY run. The desk has cards for Upbit, bitFlyer, Bithumb, Coincheck,
  OKX and the Binance archive. **It has no card for Kraken** — a top-tier venue with continuous
  history to 2015 — and the miss went unnoticed because Kraken is already *present* in the
  codebase, so a name-level check finds it and stops. That is the shape worth recording: **a
  source can be simultaneously USED and UNMINED, and the name being familiar is exactly what
  prevents the question being asked.**
- **HOW KRAKEN IS USED TODAY (shallow):** `scripts/reconstruct_kaiko_reference_rate.py:109` pulls
  the LIVE `api.kraken.com/0/public/Trades` endpoint with a `since` cursor, `max_calls=120` —
  recent trades only, rate-limited, 13,595 trades in the 4-venue joint tape. That is a live feed
  used as a live feed. The ARCHIVE is a different artifact entirely and has never been touched.
- **CLAIMED (unverified):** `support.kraken.com/.../downloadable-historical-ohlcvt-open-high-low-
  close-volume-trades-data` — OHLCV **and trades**, all timeframes, since 2015, free.
- **WHY IT IS WORTH REAL EFFORT, three specific uses rather than "more data":**
  1. **DEPTH PARITY (§32) on an axis the desk already owns shallow.** The reference-rate
     reconstruction is currently 120 API calls deep. An archive to 2015 takes the same axis to its
     archive floor — the charter's own rule that "depth always levels UP to whatever breadth
     reaches", applied to a source already in use.
  2. **A SECOND VENUE for the ETH/BTC rotation study** (card 24 / `ETHBTC_ROTATION_PREREGISTRATION`).
     That study currently loads Binance bars only. A rotation edge that exists on Binance and not
     on Kraken is a venue artifact, and cross-venue disagreement is the cheapest falsifier
     available — it needs no new hypothesis, only a second tape.
  3. **IT PREDATES BINANCE FUTURES.** Kraken from 2015 covers 2015-2017, which USD-M perp history
     cannot. Every study whose out-of-sample window is bounded by Binance's start date is bounded
     by a VENUE, not by the market.
- **STATUS: UNVERIFIED, and the unverified parts are named.** No licence or ToS read, no endpoint
  or download tested (this clone is network-policy-denied, GAP row 91), format unknown, and the
  2015 start is the poster's claim rather than a checked fact. **The licence read comes FIRST** —
  row #79 is the standing reminder that this desk once recorded a licence wrong in its own favour.
- **PROVENANCE:** a Reddit commenter answering "where do you get long crypto history". Worth
  stating that the desk's own weekly free-data mission should have found this before a forum
  comment did — the failure was not effort, it was that a familiar name reads as a covered one.
### 27. Crypto grouping map — THE BLOCKING INPUT for group_rank/group_zscore, built proprietary — grade: **BUILT from owned bars 2026-08-11 (L1.11: zero vendor, zero licence surface)** [§33: wired -> data/crypto_grouping_map.json]
> **BUILT 2026-08-11 (brain-hunter seat).** `wq_operators.group_rank/group_zscore` REFUSE without
> a `dict[symbol, group]` map; since 2026-08-07 all 179,712 cross-sectional cells could only ask
> "extreme vs ALL coins", never "vs PEERS". `data/crypto_grouping_map.json` now holds FOUR
> candidate maps over the 296-symbol D1 lake, quality MEASURED inside the artifact:
> **`corr_cluster_residual` (THE PEER MAP)** — average-linkage on 120d cross-sectionally demeaned
> return correlation, K=12, largest cluster 100/296; intra-cluster residual corr **+0.138** vs
> inter **−0.011** against the demeaning floor **−0.0034** (compared to the floor, not zero —
> desk lesson); **`corr_cluster`** (raw corr — MEASURED DEGENERATE, 268/296 in one cluster: raw
> co-movement IS the market factor, the desk's N_eff≈1.5 lesson reproduced from a new direction;
> kept as evidence, not for use); **`liq_tier`** (120d median dollar-volume quartiles);
> **`listing_cohort`** (first-partition half-year, static so no look-ahead). CONSUMER CONTRACT
> in the provenance block: choosing a map is a TRIAL DIMENSION — the pre-registration that
> adopts GROUP_TRANSFORMS must name its map(s) and price them in VARIANTS_TRIED. Consumer wiring
> routed to the ledger (alpha org; this seat is research-frozen out of libs/). Vendor
> taxonomies (CoinGecko categories) remain a possible ORTHOGONAL map — see card 28; not needed
> to unblock.
>
> **⚠ BEFORE ANY CONSUMER ADOPTS THIS MAP — READ R0583 (RU frontier miner s3, 2026-08-13).**
> Each of the four maps is a flat `dict[symbol,str]` with **no date axis**, and the provenance
> block reasons about look-ahead for **exactly one** of them (`listing_cohort`, "listing date is
> static"). The other three are **estimated from a recent window**: `liq_tier` from 120d median
> dollar volume, `corr_cluster*` from 120d return correlation over `year=2026` partitions. A
> cluster label derived from how a coin **co-moved recently**, then applied to 2021 dates, uses
> future returns to define the peer group that `group_rank`/`group_zscore` rank the signal
> *within* — the leak lands **inside the feature**, not beside it. `liq_tier` adds a second form:
> today's volume quartile is not 2021's, and it correlates with survivorship (the coins that grew
> into T4 are the ones that survived).
>
> **IT DEGRADES SILENTLY.** `libs/research/operators.py:297` accepts both shapes and its own
> docstring already names the trap — *"the same shape as `x`, **which is the case that matters for
> crypto** because sector membership is not static"*. The time-varying path is built (per-`t`
> codes); line 334 `np.broadcast_to` promotes a static map to every timestep with no error and no
> warning. The capability exists, the docstring names the hazard, and the artifact takes the
> hazardous branch **by default**.
>
> **EXPOSURE TODAY IS ZERO, WHICH IS WHY THIS IS CHEAP.** Nothing in `libs/`, `scripts/` or
> `tests/` reads `crypto_grouping_map` — verified by grep this run. No result is contaminated and
> the fix costs nothing *now*; it stops being free the moment the first `GROUP_TRANSFORMS`
> pre-registration adopts it. Suggested shape: recompute per-rebalance from a **trailing** window,
> and make a static map an explicit opt-in rather than a broadcast default.
>
> **INDEPENDENT CORROBORATION, opposite market:** a RU practitioner running the same construction
> on 30y US equities measured his best strategy deflate **Sharpe 0.77 → 0.49 (−36%)** from
> survivorship bias located *specifically in the sector data* (smart-lab 1335532, 2026-08-01).
> Same class as the desk's own `pct_circ_now` lesson — and that lesson records the direction that
> makes this urgent: **it fails toward a FALSE NULL, the one direction no gate here catches.**

### 28. CoinGecko category taxonomy (mechanism-based grouping: L1/L2/DeFi/meme/RWA) — grade: needs-legitimacy-review (ToS read FAILED this run, 403) [§33: deferred(2026-08-25) tier:4]
> **CARDED WITH ITS FAILED READ DOCUMENTED 2026-08-11 (brain-hunter seat):** the categories API
> (`/coins/categories/list` + per-coin categories, keyless free tier) would give the
> mechanism-based grouping (sector/narrative) that correlation clusters cannot express — an
> ORTHOGONAL fourth map for card 27. **BLOCKER, named:** `coingecko.com/en/api_terms` returns
> **HTTP 403** to this box's fetcher, so the commercial-use clause of the free tier is UNREAD —
> and the desk has been burned recording licences in its own favour (row #79). §13: no adoption
> before the read. Next route: the docs subdomain / a browser-capable session; if the free tier
> bars commercial use, the kill is L1.11 (no purchase) and the fallback is card 27's proprietary
> maps + DeFiLlama protocol categories (licence also unread — same read owed). Deferred
> 2026-08-25, tier 4 (blocked on a licence read, not on engineering).

## CN OSS EXTRACTION BATCH — 2026-07-31 (5 new axes; full record: cn_oss_extraction_20260731.md)

Verified same-day out of a principal-supplied survey of 10 CN-ecosystem OSS projects (8 real,
1 hallucinated, 1 proprietary — verdicts in the extraction record; MINE-NEVER-ADOPT applies).
Each axis carries a stated mechanism and awaits screen-on-discovery by the seat that ingests it:

1. **CN A-share flow microstructure (Eastmoney/AkShare/Tushare, free)** — ~~northbound Stock
   Connect flows~~, dragon-tiger lists, **margin balances**. Mechanism: mainland retail leverage
   appetite propagates into crypto via the CN-retail channel Card 9 validated (contrarian sign);
   margin balance is a direct leverage-cycle observable orthogonal to everything collected.
   > **⛔ CORRECTION 2026-08-01 (CN miner session 3) — NORTHBOUND FLOW IS DEAD. STRUCK, not
   > de-prioritised.** Confirmed by **two independent digs on the same day**: (a) 400 trading
   > sessions probed 2024-11-20→2026-07-31 — `hk2sh` all zeros, `hk2sz`/`s2n` one non-zero each;
   > (b) `RPT_MUTUAL_DEAL_HISTORY` returns `FUND_INFLOW/NET_DEAL_AMT/BUY_AMT/SELL_AMT/
   > HOLD_MARKET_CAP` all **null**, and the realtime `push2/kamt` endpoint returns empty. Cause is
   > not a broken route: **HKEX/SSE/SZSE ceased daily net-purchase disclosure on 2024-08-16.** Any
   > post-2024 use is impossible, incl. the `/northbound` route in the claw402 catalog.
   > **SURVIVING WORKAROUND:** per-stock northbound *holdings* are still published daily
   > (`RPT_MUTUAL_HOLD_DET`: `HOLD_NUM`, `HOLD_SHARES_RATIO`, `HOLD_MARKET_CAP` + 1/5/10d deltas),
   > so flow must be **reconstructed by differencing levels**, never read directly.
   > **SECOND, INDEPENDENT REASON TO DOWN-WEIGHT:** the CN sell-side reproduction repo
   > `hugo2046/QuantsPlaybook` contains a native study titled **北向资金交易能力一定强吗**
   > ("is northbound money actually smart?") — the premise this axis rests on is questioned in its
   > own literature. Dead feed *and* contested prior: down-weighted twice over.
   > **§13 STATUS OF THE REST OF THIS ROW IS UNRESOLVED — do not build yet.** Eastmoney
   > `datacenter-web` is a commercial aggregator with **no stated terms** (decision owed, **R0290**).
   > Where a first-party exchange route exists, **prefer it**: margin balances are published
   > directly by SSE (`query.sse.com.cn/marketdata/tradedata/queryMargin.do`, epoch **2010-03-31**,
   > 16.3y, per-security `rzye/rzmre/rzche/rqyl/rqmcl/rqchl`), SZSE and BSE — statutory public
   > disclosure, which is far cleaner provenance than an aggregator.
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

---

## LITMINER RUN-4 CARDS (2026-07-31, official-sector family first visit — BIS/Fed/IMF primary reads)

### 23. Carry↔liquidation mechanism family (BIS WP 1087, primary read) + COT-BTC extension — grade: needs-monitoring (mechanism prior on INGESTED axes; COT-BTC DATA LEG LANDED 2026-08-11, screen construction stays R0193) [§33: wired tier:2 -> data/cot_btc_panel.json]
> **§33 CONVERTED 2026-08-11 (brain-hunter seat).** The owed data leg is ON DISK:
> `data/cot_btc_panel.json` (845KB, provenance block inside) — CFTC legacy futures-only annual
> archives 2017→2026 pulled direct (public domain, raw zips cached at `data/scratch/cot/`),
> token-filtered BITCOIN/ETHER (token-level match so WEATHER can never match ETHER). What landed:
> **CME BITCOIN 435w 2018-04-10→2026-08-04**, CBOE BITCOIN-USD 72w 2017-12-19→2019-04-30 (predates
> the CME rows — extends the axis a full quarter earlier), MICRO BITCOIN 275w, ETHER 279w, MICRO
> ETHER 243w, plus **Coinbase Derivatives / LMX NANO + PERP-STYLE contracts** (55–89w each) — the
> perp-style COT rows are a BONUS carry-demand observable on §42 too-small-for-funds ground nobody
> asked for. All legacy (All) columns kept: noncomm/comm/**nonreportable** long/short/net/net-over-OI
> — nonreportables net-over-OI is the card's named carry-DEMAND variable. NOT DONE (unchanged
> owner): the Stage-A screen construction (carry_z → forward liquidation intensity, h∈{5d,20d})
> stays with **R0193** (re-scheduled 2026-08-24 this session), zero promotion authority, novelty
> gate re-run owed at screen time per the card's own note.
> **RE-VERIFIED 2026-08-12 (litminer run 6, §33(8) artifact check):** `data/cot_btc_panel.json`
> exists (845KB, mtime 2026-08-11 postdates find), provenance block present (CFTC legacy
> annual-archive URLs), 1,715 rows spanning 2017-12-19→2026-08-04 — matches the CBOE-1712→CME
> claim exactly. R0193 confirmed in the ledger: status=scheduled, due=2026-08-24, summary names
> this build. First-pass claims checked: 0 refuted.
- **Provides:** mechanism priors on data the desk ALREADY holds — basis, multi-venue funding
  (incl. BitMEX 2016–2026 decade), tick liquidation stream — plus a near-zero-cost extension of
  the EXISTING COT ingestion (`scripts/run_cot_screen.py`, public-domain archives) to the CME BTC
  futures contract.
- **Mechanism (Schmeling–Schrimpf–Todorov, BIS WP 1087 Oct-2025 rev, PRIMARY TEXT READ IN FULL —
  bis.org/publ/work1087.pdf):** +10% standardized carry ⇒ sell-side liquidations ≈ +22% of OI over
  the next month (sell-side ONLY; robust ex-profit-taking); high carry raises implied vol and
  predicts crashes. WHO LOSES: retail trend-chasers paying the premium for leveraged upside (CFTC
  nonreportables net-long; attention R²=12% on OKEx carry; micro-futures DiD +11% CME carry). WHY
  THEY PERSIST: leverage-through-derivatives IS the product. Why arb doesn't close it: at 10× the
  futures leg would have been liquidated in >half of sample months (no cross-margining).
- **Desk edge over the paper:** tick-level liquidation stream (paper is coarser); the UNTESTED
  extension is liquidation-flush as carry-ENTRY timing.
- **NOVELTY GATE, run 2026-07-31:** desk's 41y COT screen (24 charged trials) killed
  LAGGED-POSITIONING→RETURNS on 6 non-crypto contracts (GHR gate replicated; pooled t=−0.64).
  This card's construction is DIFFERENT — carry level/changes → forward LIQUIDATION intensity and
  crash conditioning, with COT-BTC nonreportables as the carry-DEMAND side variable, not a
  positioning-momentum signal. `funding_momentum` graveyard entry ≠ carry LEVEL (de-contamination
  angle-20 gate mandatory at screen time). Both prior kills stay dead.
- **Legitimacy (s13):** clean — BIS WP public; CFTC COT public domain; all desk-side data owned.
- **Screen plan (pre-registerable):** aligned (carry_z, forward liquidation intensity / forward
  crash indicator) at h∈{5d,20d}; timestamp alignment = desk UTC daily close on both legs, no
  cross-source lag ambiguity; every construction logged as a charged trial.
- **§33 disposition:** deferred(2026-08-07) — construction owed by the alpha org via ledger row
  (R-row this run); litminer freeze bars new runner code. Tier 2: mechanism prior on ingested axes.

### 24. Regulatory-event timeline (5-class taxonomy, Auer–Claessens) — grade: needs-monitoring (event gate EXISTS; timeline dataset is the owed build) [§33: deferred(2026-08-24) tier:3]
> **§33 RE-DEFERRED 2026-08-24 with a FAILED SEARCH DOCUMENTED (2026-08-11, brain-hunter seat).**
> The cheap path was probed and does not exist: the BIS QR Sep-2018 article page
> (`bis.org/publ/qtrpdf/r_qt1809f.htm`) links ONLY the 240KB article PDF — no annex, no online
> appendix, no dataset file; a targeted web search for a published Auer–Claessens event list
> (151 events, dates + classes) found the SSRN/CEPR/RePEc mirrors of the same article and no
> data artifact. So the timeline is a genuine RECONSTRUCTION job (regulator sites/archives, per
> the card's own free-reconstruction claim), not an extraction — it stays with **R0193**
> (re-scheduled 2026-08-24 this session). Blocker named: reconstruction labour by the alpha org;
> nothing external blocks it.
> **STRANDING RESOLVED 2026-08-12 (litminer run 6):** the [SUMMARY-ONLY — both routes 403'd]
> FRL follow-on is identified and has an OPEN author-archived version:
> **Saggu, Ante & Kopiec (2024), "Uncertain Regulations, Definite Impacts" — arxiv.org/abs/2412.02452**
> (FRL version sciencedirect S1544612324014429 stays paywalled; the arXiv copy is the legitimate
> route). Abstract-grade numbers verified verbatim: SEC classification-as-security events →
> **returns −12% over one week post-announcement, persisting for a month** (no reversal =
> underreaction gradient extends to the SEC era); **ex-ante abnormal VOLUME = pre-announcement
> informed trading**; severity conditions on sentiment, size, age, volatility, illiquidity —
> the heterogeneity conditioning for this card's event gate. **INTERIOR READ DONE SAME-RUN**
> (GAP #70's stdlib zlib extractor re-derived — the "needs poppler" claim was the exact
> inherited-false-limit #70 documents; 57,370 chars recovered): **48 events (IDs 1–48, DAO
> 25/07/2017 →), sub-samples Binance+Coinbase / Coinbase-insider / Bittrex; market model
> benchmarked on BITCOIN log returns ⇒ CARs are BTC-RELATIVE (the desk's own residualisation
> convention — these numbers survive the narrow-breadth kill by construction); pre-announcement
> CARs −2.4% INSIGNIFICANT while pre-announcement VOLUME is abnormal (the information is in
> volume, not price, ex-ante); insider subsample pre-AR −3.9% ("potential leaks"); gradient
> from −5.2% intensifying, −12%/1wk abstract-confirmed, persists a month.** The −17.2%/30d peak
> cell + exact window brackets sit in hex-encoded Tj strings the current extractor skips
> (limitation named in inbox 2026-08-12 entry). **BUILD SHORTCUT for R0193: the paper CONTAINS
> the dated 48-event table with tickers + reference documentation — the SEC-classification
> subset of this card is an EXTRACTION from an open source, not a regulator-site
> reconstruction.** McLean–Pontiff −58% haircut applies to all magnitudes as standing prior.
- **Provides:** dated, classified regulatory-event timeline (AML/CFT, interoperability-restricting,
  legal-status, CBDC, general-warning classes), reconstructable FREE from regulator sites/archives.
- **Mechanism (BIS QR Sep-2018 page-read + Dallas Fed WP 381 PDF read; 151 events 2015–18):**
  documented UNDERREACTION gradient — unfavourable −0.32% @120min → −3.12% @24h; AML/CFT −4pp
  median over 10 DAYS (−24pp multi-event days); interoperability −6.4pp/10d; spillover betas
  ETH/LTC/XMR ≈0.7–1.2× BTC. PRE-REGISTERED NULL CLASSES (free multiplicity savings): general
  warnings, CBDC statements — do NOT charge trials on them.
- **Persistence caveat, honest:** the 2024 FRL follow-on (SEC interventions, −5.2%/3d → −17.2%/30d)
  is [SUMMARY-ONLY — both routes 403'd]; NK-004 applies to the venue (FRL). McLean–Pontiff −58%
  haircut on all effect sizes; 2015–18 magnitudes will NOT be 2026 magnitudes.
- **Desk fit:** `libs/validation/event_study.py` is the event-shaped gate (§42: event-shaped edges
  go through the event-shaped gate; window/direction/threshold pre-registered as constants;
  VARIANTS_TRIED priced honestly).
- **§33 disposition:** deferred(2026-08-10) — timeline build owed (ledger row this run). Tier 3:
  new surface with a live gate path.

### 25. Stablecoin run signature — episodic conditioning on the EXISTING stablecoin_flows family — grade: needs-monitoring (SUPPLY-LEG VARIABLES BUILT 2026-08-11; mint/burn pair + premium legs stay R0193) [§33: wired tier:2 -> data/stablecoin_run_variables.json]
> **§33 CONVERTED 2026-08-11 (brain-hunter seat), honest scope.** `data/stablecoin_run_variables.json`
> (363KB) — DefiLlama `/stablecoincharts/all` (free, keyless, sr1073's own cited class): **USDT
> 3,178d 2017-11-29→2026-08-11, USDC 2,892d**, columns date/circulating/d1%/d7%/**burn_z63**
> (63d rolling z of daily supply delta — the burn-spike run signature). SANITY PROBES PASS on the
> two known runs: Terra window 2022-05/06 worst USDT d7 = **−10.2%**; SVB window 2023-03 worst
> USDC d7 = **−15.2%** — the signature is detectable in this data, measured not assumed.
> **DECLARED ABSENT (L1.55):** the price leg — CoinGecko market_chart FETCH-FAILED from this box,
> `peg_dev_bps` is null on every row and must never be read as "peg held"; the artifact's
> provenance block carries `measured: {supply_leg: true, price_leg: false}`. REMAINDER (unchanged
> owner, R0193 re-scheduled 2026-08-24): treasury-Transfer mint/burn PAIR (classifies which risk
> source is live), safe-coin premium off the desk's own 4-venue tape (better clock provenance than
> any vendor price anyway, L1.46), per-chain split if the family needs it.
> **RE-VERIFIED 2026-08-12 (litminer run 6, §33(8) artifact check):** column-oriented store
> reproduces every claim — USDT 3,178 rows 2017-11-29→2026-08-11, USDC 2,892; `peg_dev_bps`
> non-null count 0 (declared-absent honoured); sanity probes RECOMPUTED from the artifact:
> Terra worst USDT d7 = −10.23% (2022-05-18), SVB worst USDC d7 = −15.17% (2023-03-17) vs
> claimed −10.2/−15.2. First-pass claims checked: 0 refuted.
- **Provides:** episodic run-state classifier from data the desk can already reconstruct free:
  USDT/USDC treasury-Transfer mint/burn (the desk's corroborated reconstruction path), DefiLlama
  per-chain stablecoin circulation, CoinGecko stablecoin mcap (both free; sr1073's own sources),
  plus safe-coin premium off the desk's 4-venue tape.
- **Mechanism (NY Fed sr1073 June-2025 rev, PRIMARY via Boston Fed mirror after 403):** fixed-price
  primary redemption + secondary trading ⇒ MMF-type first-mover advantage; redemptions ACCELERATE
  below $1 (break-the-buck nonlinearity); crypto-native stress rotates offshore/algo→US-based
  (Frax −45%/15d, 2022); TradFi-reserve stress INVERTS the rotation (2023: USDC $0.88 secondary
  while primary held par, USDT bid $1.03); rotations ≈1:1 (R² 0.6–0.7). Burn-spike = real-time run
  signature; the mint/burn PAIR classifies which risk source is live.
- **NOT a new daily sleeve:** the desk's daily aggregate stablecoin supply signal is EV-gated/dead;
  this is EPISODIC conditioning (rare-event state variable) for the existing family — event-shaped,
  not continuous-statistic shaped.
- **§33 disposition:** deferred(2026-08-10) — variable construction owed with the family's next
  scheduled work (ledger row this run). Tier 2.

## WorldQuant BRAIN + the 101-alpha correlation benchmark (2026-08-01, transcript batch)

- **What it is:** a PUBLIC, free-to-join alpha research platform (~250k users across 100+
  countries) exposing ~125,000 data fields, an expression language, and an instant backtest
  simulator. Submitted alphas are scored and ranked; strong contributors are paid as research
  consultants. §13 status: public signup, own terms, nothing cracked or closed-group — the same
  class of source as any other public research venue. Standing miner lead for dataaxis and
  prospector: harvest the OPERATOR VOCABULARY and the DATA-FIELD TAXONOMY, which are the parts
  that transfer. Alpha expressions written there belong to whoever wrote them; the field taxonomy
  is a map of what alternative data institutions actually consider tradeable, and that map is the
  asset.
- **ADOPTED IMMEDIATELY, and it is the most useful number in the batch:** a published study of 101
  real production alphas measured their AVERAGE PAIRWISE CORRELATION at **15.9%**. Under an
  equicorrelation approximation that is `101 / (1 + 100 x 0.159)` = **6.0 independent bets**. A
  professional, deliberately-diversified hundred-signal library is SIX bets.
  Now in `libs/research/cohort_independence.py` as `BENCHMARK_MEAN_CORR`, so every campaign this
  desk runs can be read against an external standard instead of against zero.
- **Why it matters here:** it reproduces the desk's own measured "campaign WIDTH buys nothing"
  result from a completely independent direction. At that same correlation, going from 101 to 420
  candidates buys 6.0 -> 6.3 independent bets — three tenths of one bet for four times the
  multiplicity burden. The honest description of a 420-candidate campaign is not "420 hypotheses";
  it is N_eff, and the gap between the two is the size of the illusion. Locked by test.
- **Alpha decay, with its two causes named:** crowding (others find the edge and trade it away)
  and being flawed from the start (overfit, or the regime that produced it ended). The platform's
  entire thesis is that discovery RATE must outrun decay rate — which is this desk's second
  supreme objective, arrived at independently. Confirmation, not a new axis.
- **NOT adopted:** the three-layer repository -> combination-model -> optimizer architecture. This
  desk has ZERO validated alphas; a combination layer over an empty repository is infrastructure
  for a problem it does not have, and the two-stage law already says screening volume carries no
  promotion authority. Revisit when there are >=3 orthogonal validated sleeves — that is the
  lifting condition, recorded so it is not re-litigated.

---

## AXIS — `token_unlock_forced_supply` (DefiLlama unlocks) — SCREENED IN-RUN, UNMEASURED AT THE THRESHOLD THAT MATTERS
_CN frontier miner session 3, 2026-08-01. Screen-on-discovery duty discharged in the same run.
Artifact: `data/unlock_event_screen.json` · research-memory `rm-20260801T125319-a95125` · ledger `R0288`._

**HOW A CN LEXICON DIG ENDED ON A DATASET WE ALREADY OWNED.** Verifying the 控盘 (*kòngpán*,
"float control") term surfaced quantitative CN practitioner lore with THRESHOLDS attached: an
operator needs roughly **10% of float** to move a thin book short-term, **30%** medium-term and
**50%+** to run a full cycle, and *"low-circulation coins are particularly vulnerable... many newly
issued coins have highly concentrated chips, and large-scale makers can manipulate at very low
cost."* That is a stated economic mechanism with numbers, which is the class that actually converts
here (measured: from spoken/forum sources MECHANISMS convert 0/13, NUMBERS 4/4). It maps directly
onto `data/unlock_events.json` — **24,201 events, 5.2MB, s13-passed, and ZERO python readers.**

**MECHANISM (who is forced, and why they cannot stop):** insider and private-sale vesting releases
tokens to a holder with a ~zero cost basis on a **contractually fixed, publicly published date**.
They cannot sell before receipt, and fund lifecycles force distribution. Immutable schedule, forced
seller — structurally the same shape as funding/carry, this desk's only repeat survivor, and
explicitly NOT a price pattern (the 420/0-refuted class).
**FALSIFIER:** abnormal return to a short from unlock close D to close D+N is indistinguishable
from zero once multiplicity is priced.

**RESULT: 0 of 27 pre-registered cells pass.** All 27 cells reported, not just the best — every
category × threshold × window combination is a counted trial (`n_cohort=27`, Holm bars 2.24–2.90).
Powered cells are a genuine null (best |t| = 1.32 at `ALL/≥10%/N=10`, mean +6.09% to the short,
bar 2.24). Clock alignment declared (L1.46): DefiLlama date = UTC calendar day, bronze D1 = Binance
UTC close, entry at close of D so the whole return is strictly post-event. Survivorship biases a
SHORT study *against* an edge — the safe direction.

**TWO MEASUREMENT DEFECTS, and together they fully explain the empty buckets — this is the find:**
1. **The denominator has the wrong as-of date.** `pct_circ_now` is a percentage of **TODAY's**
   (2026-07-24) circulating supply, applied to events going back to 2016. Circulating supply grows,
   so an unlock that was a *huge* share of float at the time is recorded as a *small* share of
   today's float. The historical high-threshold bucket is therefore structurally emptied —
   insiders ≥10% has **14 events**, ≥30% has **0** — and the conditioning variable is not knowable
   at event time. **The field is clean prospectively and contaminated historically.**
2. **It is a snapshot, not a series.** One-shot scrape with no collector: the forward calendar spans
   only 2026-07-25 → **2026-08-23** (171 events, 45 symbols) and contains **zero** events at ≥10%.
   So the forward test the mechanism actually needs cannot be run from this artifact, and the file
   expires in three weeks.

**VERDICT: NOT REFUTED, NOT SUPPORTED — UNMEASURED where the mechanism lives.** Under L1.25 the
absence of a survivor here is a data/instrument limitation, not a fact about the market, and it is
recorded as such rather than as a kill. Not graveyarded: nothing was refuted, and a false kill would
poison the novelty gate against a live mechanism.
**RE-ENTRY CONDITION (L1.16a), narrow and named:** a recurring collector snapshotting the forward
calendar so unlocks accrue prospectively, PLUS circulating-supply-at-event-date to replace the
contaminated denominator. Re-test only when ≥20 insider events at ≥10% of *contemporaneous* float
exist. **A new window or threshold on this same snapshot is NOT an enabling change and would be
re-litigating** (L1.17). Collector rowed as **R0288**.

**GENERALISED LESSON (the part that transfers past this axis):** before conditioning on any
ratio-to-supply / ratio-to-total metric from any vendor, check the **as-of date of the DENOMINATOR**
separately from the numerator. A `_now` suffix on a field joined to historical events is a silent
look-ahead in the conditioning variable even when the return series is perfectly clean — and it
fails in the direction that manufactures a *false null*, which no gate on this desk would catch.

### ⚠ SAME-RUN CORRECTION — I TESTED THE WRONG WINDOW, and external evidence says so
_Added hours after the screen above, from the parallel Gitee/CN-GitHub dig. Recorded as a correction
to my own construction rather than quietly folded in._
Three independent external bodies — **Tokenomist (236 events)**, **Keyrock (16,000+ events)** and a
**PolyU study of 52 Binance listings** — agree that the unlock drawdown **concentrates in [T−30d, T],
i.e. BEFORE the unlock date, not after it.** The schedules are public, so the market front-runs them;
by the unlock date the supply is already priced.
**Every one of my 27 cells tested a POST-event window (D → D+N).** So the null above is *consistent
with* the external finding rather than contradicting it — but it is a null about the wrong window,
and reporting it without this caveat would have understated how much remains untested. My screen
does not test the hypothesis the outside evidence actually supports.
**The re-entry condition is amended accordingly:** the pre-registered construction is a **SHORT over
[T−30d, T]**, conditioned on unlock size vs float and on liquidity — not a short on the unlock date.
Note this ALSO partly sidesteps defect (1) above: a pre-event window still needs a
contemporaneous-float denominator, but the *timing* no longer depends on it.
**A naive short-on-unlock-date should FAIL — and mine did.** That makes the run above a cheap,
unplanned **positive control on the desk's own wiring**: our panel reproduced the externally-reported
null in the window where a null is expected. Weak evidence the instrument is sound (L1.25 diagnostic
step 1), obtained for free.

### 26. KR venue-state layer — Upbit + Bithumb event archive, market flags and rail state — grade: needs-monitoring (verified live, ingest STARTED, screen owed) [§33: screened -> data/upbit_trade_announcements.jsonl]
_Discovered and verified by the KR frontier miner, session 1, 2026-08-01. All endpoints keyless,
first-party, §13-clean (public documented venue APIs, no login, no paywall, no scraping)._
> **RE-VERIFIED 2026-08-12 (litminer run 6, §33(8) artifact check):**
> `data/upbit_trade_announcements.jsonl` exists (199KB), **737 rows** — the card's
> category=trade count exactly — spanning 2017-10-27→2026-07-31 (KST stamps), consistent with
> the 2017-10-24 open-beta claim (first *trade* announcement 3 days after open). Screen still
> owed (unchanged owner). First-pass claims checked: 0 refuted.

- **Provides — four distinct surfaces, all free:**
  1. `api-manager.upbit.com/api/v1/announcements` — **5,685 dated, categorised announcements back
     to Upbit's open-beta day, 2017-10-24.** `category=trade` → **737** listing/delisting/
     trading-support events. *Caps: `per_page<=20` (30 → 429, 100 → 400); needs ≥3s between pages.
     The category filter key is **English** (`trade`); the Korean literal `거래` returns HTTP 400.*
  2. `api.upbit.com/v1/market/all?isDetails=true` — per-asset `market_event.warning` (유의종목) plus
     `caution{PRICE_FLUCTUATIONS, TRADING_VOLUME_SOARING, DEPOSIT_AMOUNT_SOARING,
     GLOBAL_PRICE_DIFFERENCES, CONCENTRATION_OF_SMALL_ACCOUNTS}`.
  3. `api.bithumb.com/v1/market/all?isDetails=true` — second KR venue, same `market_warning` field.
  4. `api.bithumb.com/public/assetsstatus/ALL` — **per-asset deposit / withdrawal open-closed state.**
- **Mechanism (why this is not just more data):** Korean retail is a large, concentrated,
  KRW-rail-captive flow cohort, and these endpoints are **the venue's own labels on that cohort**.
  `CONCENTRATION_OF_SMALL_ACCOUNTS` is computed from Upbit's internal account-level book and is
  **structurally unbuyable** — no vendor sells it. The Bithumb rail state is an **independent
  measure of barrier height**, which breaks the circularity in which every prior KR premium study
  here inferred the barrier *from the premium itself*.
- **Measured live 2026-08-01T13:34Z (base rates, because a flag that never fires carries nothing):**
  Upbit 803 markets / 277 KRW — `warning` 6 KRW (2.2%), `TRADING_VOLUME_SOARING` 14 (5.1%),
  `DEPOSIT_AMOUNT_SOARING` 3 (1.1%), `GLOBAL_PRICE_DIFFERENCES` 1 (0.4%),
  `CONCENTRATION_OF_SMALL_ACCOUNTS` 0. Bithumb 487 markets → 470 NONE / **17 CAUTION**;
  `assetsstatus` 506 assets → withdrawal closed 4 (0.8%), **deposit closed 51 (10.1%)**.
  Cross-venue: **ZIL, STORJ, TT, BONK warned at BOTH**; Bithumb flags 17 vs Upbit's 6, so the
  **13-name disagreement set** is itself a candidate. ZIL is the live full-syndrome case (warned at
  both + deposit AND withdrawal closed).
- **THREE TRAPS, all measured, all of which would have produced a confident wrong answer:**
  1. **`GLOBAL_PRICE_DIFFERENCES` fires on 175/803 (22%) of ALL markets and 1/277 (0.4%) of KRW.**
     The 22% is thin USDT/BTC-book illiquidity, **not** a fiat premium. The biggest number on the
     page is the artifact. *Split by quote currency before reading any rate.*
  2. **Key events on `first_listed_at`, never `listed_at`** — they differ on 42.5% of rows (median
     2.08d, p90 9.30d, max 14.7d). Mechanism now known: Upbit *amends* the trading-start time after
     publishing (`(거래지원 개시 시점 변경 안내)`), and the amendment rewrites `listed_at`.
  3. **Announcements are KST (+09:00); Upbit daily candles close at 24:00 UTC** (proven from primary
     hourly data, PROSPECTOR 2026-07-30). A 17:00 KST announcement is 08:00 UTC *inside* that UTC
     day — the window must start at the **next** UTC close or it is look-ahead.
- **Event classes (in the 360 rows classified so far, 2023-02-15 →):** new listing 151;
  **KRW market addition 41** — asset *already* on Upbit's BTC/USDT books, KRW rail added, which
  **isolates rail access from discovery** and is the cleanest natural experiment in the set;
  warning ON 47; warning OFF 9; delisting 40.
- **Feasibility gate PASSED, measured with zero price data** (each delisting title carries its own
  effective timestamp): notice window **min 14.0d, median 30.9d, max 36.0d, 40/40 parsed** — a
  month-long, pre-announced, precisely-dated forced-unwind window. §42 names *"delisting unwinds"*
  as our ground.
- **Screen status — HONEST:** the pre-registered Upbit-KRW delisting event study is **IMPOSSIBLE**
  and that is a reported result, not a skip. The declared survivorship threat **fired 6/6**: Upbit
  returns HTTP 404 on `/v1/candles/days` for every delisted market, so the treatment group is
  **erased, not merely biased**. Scoped to the route: the *event dates* survive intact, and the
  study is **re-runnable on global prices** (the assets trade elsewhere with history intact) — which
  tests the sharper question of whether a KR delisting moves the asset's *global* price. Owed next
  run. **`axis_screen` is the WRONG instrument here** (~2 non-zero days in 30 reads as noise on
  every continuous statistic); this goes through `libs/validation/event_study.py`, `n_cohort=1`.
- **Irreplaceability — this is the part with a deadline.** Surfaces 2–4 are **snapshot-only, no
  history endpoint**, so the series can only ever begin the day recording begins. Worse, the purge
  means **the entire KRW price history of any asset is destroyed when it delists**, at ~**11.4
  markets/year**. **KRW-AQT and KRW-AERGO halt 2026-08-03; KRW-SPURS 2026-08-18; the desk holds
  history for none of them** (the 07-30 panel's `>=120 aligned days` filter excludes exactly the
  thin/new names that delist — **our own construction filter stacks with the venue's purge**).
- **Legitimacy (§13): clean.** Public, documented, unauthenticated first-party venue APIs. Rate
  limits observed and respected throughout (the 429s in this run were backed off, never evaded).
- **Routed:** `data/upbit_trade_announcements.jsonl`, `data/upbit_announcements.jsonl`,
  `data/data_universe_map.json` (4 entries), R0298–R0301, **R0303 (dated 08-03)**.
- **ERA MECHANISM PRIOR FOR THE OWED SCREEN (KR miner s2, 2026-08-12 — Ppomppu mania-window
  primary text, archived `data/ppomppu_kr_era_threads.jsonl`):** the 2017-18 era folk record
  states the rail-state→premium mechanism as RULES, not speculation: (1) "지갑 없이 신규상장시
  타거래소보다 매우 높은 시세" — a deposit-closed listing forms a fenced (가두리) captive market
  with structurally elevated venue price (live era example: BTG on Coinone at 66 vs global);
  (2) per-coin premium dispersion ∝ transfer friction (ERC-20 tokens tight, congested chains
  wide — same-day tape EOS 9-25% vs XRP 34%, Jan 2018); (3) venue↔bank binding makes rail
  throttles VENUE-level basis events (real-name era: Upbit-IBK, Bithumb-NH; beehive-kill forced
  selling = frozen-leg discounts). So the screen this card owes should key on **rail-state
  TRANSITIONS per asset** (deposit close/reopen), not on flag LEVELS — the levels are the fence
  standing, the transitions are the fence going up or coming down, and the era record says the
  price action lives at the transitions. Pre-registered design + falsifier + EV gate (0.0061
  QUEUE, novelty 0.772) live on `prospector_watchlist.md` card `kr_rail_state_transition_global_leg`
  (2026-08-12); the screen obligation stays HERE, one owner, now with its design. (JP venue, keyless, 2018-09-05 →) — grade: **verified-technically-clean, LICENCE READ 2026-08-12 — needs-legitimacy-review: the customer 基本約款 Art. 14(15) requires company consent for off-service use of service-obtained information; whether the anonymous keyless archive is inside 本サービス scope is a policy decision, not a technical read. Ingest stays gated.** [§33: deferred(2026-08-19) tier:3]
_Found by JP frontier miner session 1, 2026-08-01, as the licensed replacement for the §13-restricted bitFlyer axis._

> **§33 DISPOSITION 2026-08-12 — THE OWED READ IS DONE (R0309). LICENCE UNREAD → LICENCE READ.**
> The blocker named on 08-05 ("one PDF read, not a wall") was real and is now closed:
> - **WHAT WAS READ:** `kihon-yakkan.pdf?ver=20260725` (ＧＭＯコインサービス基本約款, 12 pp,
>   updated 2026-07-25), harvested from `coin.z.com/jp/corp/policy/terms/` this run. The PDF is a
>   subset-font/CID document; text was recovered stdlib-only (zlib streams + per-font ToUnicode
>   bfchar/bfrange maps, literal-string Tj decode) — 16,053 chars, all 26 articles legible.
>   Method reproducible from the URL; no install, no proxy.
> - **THE OPERATIVE CLAUSES, quoted:** Art. 14(15) 禁止事項: 「当社の承諾を得ることなく、本サービス
>   により取得した情報を本サービス利用以外の目的で利用し、又は第三者に開示し、若しくは漏洩する行為」
>   (without the company's consent, using information obtained through the Service for purposes
>   other than Service use, or disclosing it to third parties, is prohibited). Art. 7(1): use of
>   the Service is DEEMED ASSENT to the terms (「利用した場合は…同意しているものとみなします」).
>   Art. 7(3): customers acquire no IP or other rights in the Service.
> - **NO OTHER GOVERNING DOCUMENT EXISTS — searched, not assumed:** the policy index
>   (`/jp/corp/policy/`, all 9 documents enumerated) has no API約款, no site-use terms, no
>   copyright page; the API product page (`/jp/corp/product/info/api/`) links no API terms; the
>   archive index (`api.coin.z.com/data/trades/`) carries zero terms/notice text. The 基本約款 is
>   the whole licence surface.
> - **WHY THIS IS A DECISION AND NOT A VERDICT:** the archive is branded APIドキュメント (inside
>   the 暗号資産API surface) yet requires no account, no key, no click-through, robots explicitly
>   permissive. EITHER it is 本サービス — then Art. 7(1) deems the download assent and Art. 14(15)
>   gates desk research use on GMO's consent — OR it is outside 本サービス — then no licence
>   attaches to a public publication of non-copyrightable facts (JP has no sui generis database
>   right; 著作権法12条の2 needs creative selection/arrangement raw tick CSVs lack). The two
>   readings give opposite answers and choosing between them is a §13 POLICY call, same class as
>   the Upbit-portal row already in the DECIDE queue. Re-graded `needs-legitimacy-review` so the
>   backlog surfaces it there — the queue built for exactly this shape.
> - **Deferral is dated 2026-08-19 with the decision as the lifting condition.** This is not
>   flow-rot: the deferral's CONTENT changed (unread → read, clause identified, routed). If the
>   decision rules the 約款 governs, the honest next tag is `killed` (§13 hard stop, L1.16a
>   re-entry = written GMO consent); if it rules the archive public-unlicensed, next tag is
>   `wired` via a collector. Until then: **no collector, no ingest.**

> **§33 DISPOSITION 2026-08-12 — CORRECTED FROM `screened`, WHICH THIS CARD NEVER WAS.** The tag
> read `screened -> docs/research/prospector_coverage.md JP-s1` and was counted unbacked. Both
> halves were wrong, and only one of them was a formatting problem:
> - **The citation was malformed.** `path JP-s1` (bare space) parses as a single 47-character
>   filename that can never exist. The anchor form the checker accepts is a **backtick-quoted**
>   anchor — `` path `anchor` `` — and the anchor must actually appear in the file. `JP-s1` does
>   not appear anywhere in `prospector_coverage.md` (grepped this cycle: zero `XX-sN` matches).
> - **The disposition was wrong on the facts, and that is the part that mattered.** This card's own
>   grade says **LICENCE UNREAD**. §13 legitimacy is absolute and unresolved here, so a screen was
>   never run and could not legitimately have been run. Re-pointing the citation string would have
>   laundered a false claim into a passing one — the exact failure §33 credits artifacts to prevent.
> **ATTEMPTED THIS CYCLE, not deferred on assumption:** `coin.z.com/jp/corp/policy/terms/` returns
> an INDEX OF PDF LINKS (サービス基本約款 etc.), not clause text — so the substantive automated-access
> and data-reuse terms sit one layer deeper, in the linked PDFs, and were not read. That is the
> named blocker, and it is one fetch deep rather than a wall.
> **Driven by R0309** (READ THE GMO COIN LICENCE, then re-grade). Ingest stays gated until §13 is
> settled. Deferral is short deliberately: this is one PDF read, not an open-ended condition.

- **What it is.** GMO Coin (GMOコイン, a listed-group JP venue) publishes **daily tick-by-tick trade
  CSVs, gzipped, keyless, no account**, at:
  `https://api.coin.z.com/data/trades/{SYMBOL}/{YYYY}/{MM}/{YYYYMMDD}_{SYMBOL}.csv.gz`
- **VERIFIED THIS RUN, not inferred.** `20210301_BTC_JPY.csv.gz` → **200, 1,746,370 B**;
  `20210301_BTC.csv.gz` → **200, 97,373 B**. Decompressed header + rows:
  `symbol,side,size,price,timestamp` / `BTC,SELL,0.0100,4788420.000,2021-02-28 21:00:00.833`.
  **Millisecond timestamps, signed side, tick granularity.**
- **START DATE BINARY-SEARCHED to the day: 2018-09-05.** `20180904` → **403**, `20180905` → **200**,
  for BOTH the spot (`BTC`) and leveraged (`BTC_JPY`) products. (403-not-404 is the S3 object-absent
  shape, so the boundary is the data start, not an auth wall.) ⇒ **~7.9 years of JP tick tape.**
- **Universe (from the service's own index page):** 28 spot symbols —
  `BTC ETH BCH LTC XRP XEM XLM BAT OMG XTZ QTUM ENJ DOT ATOM MKR DAI XYM MONA FCR ADA LINK DOGE SOL
  ASTR NAC WILD SUI` — plus 12 margin pairs (`BTC/JPY ETH/JPY BCH/JPY LTC/JPY XRP/JPY DOT/JPY
  ATOM/JPY ADA/JPY LINK/JPY DOGE/JPY SOL/JPY SUI/JPY`). 8 of these spot-checked live at 200.
- **WHY THIS IS A MOAT AXIS AND NOT JUST MORE PRICE DATA (L1.11a standing test).** The interesting
  part is *not* BTC. It is **`MONA` (Monacoin), `XYM`, `FCR`, `NAC`, `WILD`, `XEM`** — JP-listing-
  specific assets with thin or absent coverage on global venues, at **tick** resolution, **free**.
  A competitor reconstructing this pays for a JP venue feed or does not have it. It is also the
  **spot ⊕ leveraged pair on the same venue** (`BTC` and `BTC_JPY` are separate books), which is a
  clean same-venue basis series most aggregators flatten away.
- **`robots.txt`: EXPLICITLY PERMISSIVE.** `coin.z.com/robots.txt` = `User-agent: * / Allow: /` with
  7 unrelated `Disallow`s (signup, LP pages, chart generator). **No ClaudeBot/AI-agent block.**
  `api.coin.z.com/robots.txt` → 404 (no directives).
- **§13 RESIDUAL — READ THIS BEFORE ANY COLLECTOR IS BUILT.** The service's own docs page carries
  **no terms, no licence, no disclaimer** (checked). The governing document is GMO Coin's site
  規約 at `coin.z.com/jp/corp/policy/terms/` and `/jp/corp/policy/` — both return **200 and are NOT
  bot-blocked**, but the body is **JS-rendered** (86,604 B / 64,607 B of shell; the 規約 text is not
  in the raw HTML). **LICENCE THEREFORE UNREAD.**
  **This is a materially better state than bitFlyer and must not be conflated with it:** bitFlyer's
  terms host *refuses us*; GMO's *serves us* and we simply have not rendered the body. Next action
  is an OP-038-class fetch of the JSON/API behind the JS shell, **not** a human page-read and **not**
  a proxy purchase.
- **NEXT ACTION (dated):** ~~render the terms page and re-grade~~ **DONE 2026-08-12** (see
  disposition block above — the 約款 is read; what remains is the §13 scope DECISION, owed by
  2026-08-19 via the legitimacy queue). Until decided: **no collector, no ingest.**
  Technically verified ≠ cleared.

---

### 28. bitbank public candlestick API (JP venue, keyless, whole-year-per-call) — grade: **verified-technically-clean WITH A CONFIRMED PHANTOM-HISTORY TRAP, LICENCE READ 2026-08-12 — needs-legitimacy-review: the ToS (Art. 17/19/20) contains NO data-reuse restriction and the venue's own support docs invite programmatic public-data retrieval; the one restrictive text is the site-footer disclaimer ("private use only, not for commercial purposes" over news/prices/data), whose scope over the public.bitbank.cc API subdomain is the open policy question. Ingest stays gated.** [§33: deferred(2026-08-19) tier:3]
_Found by JP frontier miner session 1, 2026-08-01._

> **§33 DISPOSITION 2026-08-12 — THE OWED READ IS DONE (R0310), AND THE EGRESS DIAGNOSIS IS
> CORRECTED.** The 08-04 attempt failed because it fetched the WRONG URL, not (only) the wrong box:
> `bitbank.cc/error/terms` is the SPA's error route — the 6,500 B "JS shell" IS the error page.
> The canonical terms live at **`bitbank.cc/doc/tos`**, which server-renders to plain curl from
> this box: HTTP 200, 686,453 B, the full 規約 embedded (double-entity-encoded; 86,728 chars
> extracted stdlib-only, ~4 service copies: spot/margin/lending/auto-invest).
> - **WHAT THE ToS SAYS (users = account holders):** Art. 17 禁止行為 has **no data-reuse,
>   no redistribution, no off-service-use clause** — prohibitions target account abuse, AML,
>   reverse-engineering the service (逆アセンブル…リバースエンジニアリング), competing-service
>   use, and 金商法 market-abuse articles. Art. 19 知的財産権: standard IP-ownership (no use
>   restriction beyond infringement). Art. 20 秘密保持 covers non-public information and
>   **excludes 公知 information by its own carve-outs** — public API data is outside it.
> - **THE ONE RESTRICTIVE TEXT, quoted:** the site-footer 免責事項: 「当サイトにおけるニュース、
>   取引価格、データ及びその他の情報などのコンテンツは…あくまでもお客様の私的利用のみのために
>   当社が提供しているものであって、商用目的のために提供されているものではありません」 (site
>   content incl. trading prices and data is provided solely for private use, not for commercial
>   purposes). Shape is standard JP editorial not-investment-advice boilerplate (the surrounding
>   sentences are about authors' views and solicitation), but the text names データ.
> - **AGAINST reading it as an API ban:** the API host `public.bitbank.cc` carries no terms, no
>   robots directives, no disclaimer; the official support article (support.bitbank.cc
>   360019410033) **positively describes programmatic retrieval of 板情報/チャートデータ as the
>   API's purpose**; the official api-docs repo (`bitbankinc/bitbank-api-docs`, no LICENSE file)
>   documents the public API for bot use. A reading that bans commercial API consumption would
>   make every bitbank trading bot a ToS breach — contradicting the venue's own documentation.
> - **No API-specific 約款 exists** — searched (policy pages, support KB, api-docs repo).
> - **ROUTED: needs-legitimacy-review** — same DECIDE queue as GMO (card 27) and the Upbit
>   portal, decision owed by **2026-08-19**. bitbank's case is cleaner than GMO's (no
>   consent-required reuse clause; positive invitation to programmatic use); if the decision
>   clears it, next tag is `wired` via a collector **with the 2017-02-14 true-start guard**
>   (the phantom-history trap below stands as an independent technical gate regardless).

> **§33 DISPOSITION 2026-08-12 — CORRECTED FROM `screened`, WHICH CONTRADICTED THIS CARD'S OWN
> GRADE.** The tag claimed a screen while the grade in the same heading reads *licence unread,
> ingest stays gated*. A card cannot simultaneously be screened and be gated against ingest. The
> citation was malformed in the same way as card 27 (`path JP-s1`, bare space, parses as a filename
> that cannot exist; the accepted form is a backtick-quoted anchor that must appear in the target).
> **THE BLOCKER IS EGRESS AND IT IS ALREADY MEASURED** — recorded in the grade above: the licence
> body is reachable only from a box with direct egress. A genuine external constraint, named.
> **Driven by R0310.** The confirmed phantom-history trap (volume 0.0000 pre-2017-02) is a SECOND,
> independent gate that stands regardless of how §13 resolves.

- **What it is.** `https://public.bitbank.cc/{pair}/candlestick/{type}/{YYYY}` returns **an entire
  year of OHLCV in one keyless call**. Payload: `[open, high, low, close, volume, timestamp_ms]`.
  Verified live at 200 for `btc_jpy/1day/{2014,2015,2016,2017,2018}`.
- **THE TRAP, AND IT IS THE ACTUAL DELIVERABLE HERE (see OP-045).** For **2014, 2015 and 2016** the
  endpoint returns `success: 1` with **362 / ~365 / 363 daily bars of populated, MOVING OHLC** —
  and **volume `0.0000` on every single bar.** Measured: `2014 bars=362 nonzero_vol=0`,
  `2016 bars=363 nonzero_vol=0`, `2017 bars=365 nonzero_vol=317 first_nz=1487030400000`
  (**2017-02-14**, bitbank's real BTC/JPY launch), `2018 bars=365 nonzero_vol=364`.
  ⇒ **~1,090 untradeable phantom bars are served ahead of the venue's own existence, flagged as
  success.** The price path moves, so no visual sanity-check catches it; **only the volume column
  does**. Any collector taking "bitbank since 2014" at face value poisons its earliest regime.
- **TRUE USABLE START: 2017-02-14.** Anything earlier is a reference/index backfill, not bitbank's
  tape, and must not enter a backtest.
- **Granularity caveat:** the year-per-call form works for `1day`; `1hour/2017` returned
  `{"success":0,"data":{"code":10000}}` — finer types need the `YYYYMMDD` form. Do not assume the
  year form generalises across `type`.
- **§13:** `bitbank.cc/robots.txt` → 200, **no ClaudeBot block**; `public.bitbank.cc/robots.txt` →
  404. The API docs repo `github.com/bitbankinc/bitbank-api-docs` (126★) carries **no LICENSE file**
  (`license: None` via the GitHub API), so the docs are unlicensed and the governing document is the
  site 規約 — canonical URL **`bitbank.cc/doc/tos`** (the earlier `/error/terms` URL was the SPA's
  error route). **LICENCE READ 2026-08-12** — see the disposition block above for the clauses.
- **NEXT ACTION (dated):** ~~extract the 規約 body and re-grade~~ **DONE 2026-08-12** (see
  disposition block above — full ToS read from `bitbank.cc/doc/tos`; what remains is the §13
  scope DECISION, owed by 2026-08-19 via the legitimacy queue). No ingest until decided.
- **Standing value even if the licence fails:** the phantom-history finding is venue-independent
  knowledge and is already generalised into **OP-045**.

---

### 29. RFB "Criptoativos — Dados Abertos" (Brazil, national MANDATORY crypto-reporting panel, 2019-08 → 2025-12) — grade: **verified-live, extracted, arithmetically self-validated; UNDERPOWERED FOR STAGE-A BY CONSTRUCTION (n=77 monthly) — catalogued, NOT screened, and the reason is stated** [§33: deferred(2026-09-05) tier:2]
_BR frontier miner session 1, 2026-08-01. Fetched, parsed and cross-checked this run — every number
below was read off the artifact, not a summary._

> **§33 DISPOSITION 2026-09-05 — CORRECTED FROM `screened`, WHICH THIS CARD'S OWN GRADE DENIES IN
> THE SAME SENTENCE.** The heading reads *"catalogued, NOT screened, and the reason is stated"* and
> the tag read `screened`. That is not a citation problem; a re-pointed artifact string would have
> converted an explicitly-disclaimed screen into a credited one. This is the mis-disposition the
> 2026-08-05 max_audit ack predicted would be found here, and it is confirmed.
> **THE SHORTFALL IS IN OBSERVATIONS, NOT IN DAYS (L1.48).** n=77 monthly points with a ~3.5-month
> reporting lag. The axis is not dead and it is not screened — it is **underpowered by construction
> for a standalone Stage-A screen**, and it accrues at 12 observations/year, so no realistic wait
> makes it powered as a standalone series.
> **THE DEFERRAL HAS A DECISION IN IT, NOT A WAIT.** By the date above, re-grade it for the use it
> can actually support — a low-frequency **conditioning / regime variable** joined to a
> higher-frequency target, or an event-study cut around the IN RFB 1888→2291 regime change — rather
> than re-attempting the standalone screen that its own n forbids. If that re-grade also fails, the
> honest next tag is `killed` with a graveyard entry, not another deferral.
> **CARRIES A KNOWN LOOK-AHEAD HAZARD** (desk lesson, BR seat): the RFB panel is REVISED — 42/42
> months revised, worst +40.9%. Any use must read point-in-time vintages (R0316), never the current
> published series, or the conditioning variable itself leaks the future.

**WHAT IT IS.** Under **IN RFB 1888/2019** (now superseded by **DeCripto, IN RFB 2291/2025**) every
exchange domiciled in Brazil must report **every crypto operation with no minimum value**, and every
resident person/company must report operations on **foreign** exchanges or **peer-to-peer** above
R$30k/month. Receita Federal publishes the aggregate as a free `.xls`/`.pdf`:
`https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-demonstrativos/criptoativos/arquivos/criptoativos_dados_abertos_20260415.xls`
(576,000 B, HTTP 200, keyless, no auth). Five sheets:
| Sheet | Content | Extracted |
|---|---|---|
| Relatorio1 | monthly R$mn split **foreign-exchange (PF/PJ) / no-exchange P2P (PF/PJ) / domestic exchanges** | **77 months, Ago-2019 → Dez-2025** |
| Relatorio2 | monthly **unique CPF (individuals) / CNPJ (companies)** | 77 months; Dez-2025 = **3,544,986 CPF / 67,324 CNPJ** |
| Relatorio3 | monthly **gender split** of operation count and value | 77 months |
| Relatorio4 | **per-asset per-month**: n operations, total R$, mean R$ | **4,206 rows, 66 assets** |

**SCALE (Dez-2025):** foreign-exchange R$6,906mn · P2P/no-exchange R$10,121mn · domestic exchanges
R$26,076mn · **Total R$43,103mn (~US$8bn) in one month.**
**ALL-TIME BY ASSET:** USDT **R$1.004 trillion** (44.9M ops) ≫ BTC R$269bn (150.7M ops) > USDC R$80bn
> ETH R$61bn > XRP R$42.8bn > **BRZ R$38bn on 92.4M operations** (the highest op-count of any asset).

**MECHANISM (stated before any screen, per SCREEN-ON-DISCOVERY (2)).** USDT declared value is **3.7×
BTC's**. Brazilians are overwhelmingly buying a **dollar proxy**, not a speculative asset — so
`declared_stablecoin_value / declared_BTC_value` is an **EM dollarization / capital-flight** measure
on a compelled-reporting basis. Who is forced to trade against it: residents hedging BRL debasement
who cannot cheaply access USD deposits. Testable against **BCB PTAX** (verified keyless this run:
`api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados?formato=json`).

**WHY IT IS NOT SCREENED THIS RUN, AND WHY THAT IS THE HONEST CALL.** n = **77 monthly** observations
with a **~3.5-month publication lag** (the 2026-04-15 file ends at Dez-2025). The desk's screen
requires ~4,268 independent observations (R0030). Running `axis_screen` here would produce a null
whose power is ~0 — **a manufactured false null on a genuinely novel axis, which L1.25 names as the
failure mode, and which would burn multiplicity budget for zero information.** Same call the CN seat
made on `unlock_events.json` (0/27 → *UNMEASURABLE, not dead*). Reported as **UNDERPOWERED**, not as
*no edge*. It is a **regime/conditioning variable and a validation ground-truth**, never a timing signal.
**ENABLING CHANGE that would make it screenable:** use it cross-sectionally (66 assets × 77 months =
4,206 asset-months) as a **retail-attention conditioner** on the desk's existing perp universe, where
breadth rather than length supplies the observations.

**THE REAL PRIZE — A FREE POINT-IN-TIME VINTAGE STACK (verified, not asserted).** RFB republishes the
whole file monthly under a **dated filename**, so every release is a **vintage**. Measured this run:
- 2023-05-03 vs 2023-08-07 vintages: **39 of 42** common months revised **within 3 months**.
- 2023-05-03 vs 2026-04-15: **42 of 42 revised.** Largest **Março-2023 R$15,828mn → R$22,308mn (+40.9%)**.
- 2022-01-04 vs 2026-04-15: Ago-2019 Total Geral **3,940.3 → 4,036.9 (+2.5%)** and unique CPF
  **160,589 → 182,935 (+13.9%)** — i.e. revisions still accrue on a month **2.4 years old**.
- Revisions are **systematically upward** (late and amended filings).
⇒ **Backtesting the CURRENT file is a look-ahead leak of up to +41% in the conditioning variable** —
the R0289 defect class exactly (a value whose as-of date ≠ its event date), and it fails toward a
FALSE result. The vintage stack is the fix and it is free. **23+ distinct publication dates recovered
from Wayback CDX**; a vintage that is **404 on the live server** (`..._04012022.xls`) was fully
recovered at 282,624 B via the raw-replay modifier
`https://web.archive.org/web/20220115123532id_/<url>` — **so point-in-time reconstruction back to
2021-09 is PROVEN feasible, not hoped for.**

**THE TRAP FOR WHOEVER BUILDS IT — a fixed-cell scraper silently produces a wrong series.** Across
eras the file changes **row offset** (data starts row 10 in 2022, row 8 in 2026), **column ORDER**
(2022 `MÊS/ANO | CNPJ | CPF` vs 2026 `MÊS/ANO | CPF | CNPJ` — **swapped**, so a fixed reader takes
CNPJ ≈ 2k as CPF ≈ 160k, an ~80× error that still *looks* like a plausible count), **number type**
(2022 = text with Brazilian thousands separators `160.589`; 2026 = native numerics) and **labels**
(`Exchanges / Somente PJ` → `Exchanges no Brasil*`). Parse by **header semantics per vintage**, never
by cell address. Generalised as the OP-035 BR extension.
**And the filename convention itself flips:** `DDMMYYYY` up to 2023-09 (`02092021`, `07082023`,
`25092023`) then **`YYYYMMDD`** from 2024-10 (`20241007`, `20250115`, `20260415`). A regex for one era
silently zero-hits the other. There is also a real **publication hiatus 2023-09 → 2024-10**.

**BR-ONLY TOKENIZED-RWA UNIVERSE (incidental discovery, in a government dataset).** Of the 66 assets:
`MBPRK02/03/04` (**tokenized *precatórios* — court-ordered Brazilian government debt**), `MBCONS02`
(*consórcio* credit), `IMOB01` (real estate), `CBRL`/`BRLT`/`BRZ`/`BRZX` (BRL stablecoins), `MCO2`
(tokenized carbon), `WBX`. These exist nowhere in the desk's universe and are not in any global
vendor's crypto taxonomy.

**§13:** `gov.br/robots.txt` — `User-agent: *` with **no AI-crawler block and no relevant Disallow**;
files are published under Brazil's open-data policy (LAI 12.527/2011). **CLEAN — no restriction.**
**VERIFICATION STATUS:** endpoint live ✓ · parsed ✓ · **arithmetic self-validated ✓** (OP-024: all
78 monthly rows satisfy PF+PJ=Subtotal and Subtotal₁+Subtotal₂+Domestic=TotalGeral with worst
residual **exactly 0.00**) · licence clean ✓ · **ingest NOT started** · **screen deliberately withheld
as underpowered, with the enabling change named above.**

---

**UPDATE 2026-08-12 (BR frontier miner s2) — THE VINTAGE STACK'S "DECAYING DEADLINE" IS NOW A
MEASURED LEVEL, AND ITS RATE IS EXPLICITLY UNMEASURED. s1's urgency claim was not evidenced.**

s1 called this *"the one item with a decaying deadline"* on the strength of **2 of 4** probed
vintages being live-404. That is a LEVEL observed on a 4-item sample, and a decay *rate* was
inferred from it that nobody had measured. Full census run this session (every known publication
date, both `.xls` and `.pdf`, ranged-GET against the live RFB server):

| | count | range |
|---|---|---|
| distinct publication dates known (Wayback CDX) | **23** | 2021-09-02 … 2025-11-12 |
| **LIVE on the RFB server** | **11** (+ `20260415` = **12**) | **2023-05-03 … 2026-04-15** |
| **404 on the RFB server** | **12** | 2021-09-02 … 2023-03-02 |
| of the dead, a DIRECT Wayback file capture exists | 8 | recoverable |
| of the dead, **no direct capture — AT RISK** | **4** | 2021-09-02, 2022-07-05, 2023-02-06, 2023-03-02 |

**The boundary is perfectly clean: everything published ≤ 2023-03-02 is dead, everything ≥
2023-05-03 is live.** The public page links **only** `20260415`; the other 11 are unlinked but
still served, so they are reachable only if you already know the filename — which is what makes the
date list above the actual asset.

**TWO HYPOTHESES FIT THIS EQUALLY WELL AND THEY IMPLY OPPOSITE URGENCY. Naming both instead of
picking the exciting one:**
- **(A) Rolling keep-last-N (N≈12).** 12 live / 12 dead is a suspiciously exact split. If true,
  **every new publication kills the oldest survivor** and mirroring is genuinely urgent.
- **(B) A one-time 2023-04/05 CMS migration cutoff.** gov.br has form for platform migrations, and
  a single cut at that boundary explains the data exactly as well. If true the live set is
  **stable** and there is no ongoing decay at all.

**I could not discriminate them, and I am recording that rather than resolving it** (L1.28a —
UNMEASURED is a real answer). The reason is concrete: Wayback captured these files essentially
**once each, at publication**, so the CDX status timeline cannot date any file's death.
**THE DISCRIMINATOR IS A SECOND CENSUS, AND THIS ENTRY EXISTS TO MAKE IT POSSIBLE** — s1 recorded
no date list, so no delta was computable this run; the table above is the baseline. **Falsifier:**
if a publication occurs after 2026-04-15 and the live floor moves from 2023-05-03 to 2023-06-08,
hypothesis (A) is confirmed and mirroring becomes urgent; if the floor holds, (B) is confirmed.
Re-probe: ranged-GET `.../criptoativos_dados_abertos_{DATE}.xls` for each date above.

**A SECOND, UNRELATED OBSERVATION WORTH MORE THAN THE DECAY QUESTION: the series may be in a
publication hiatus right now.** The newest vintage is **2026-04-15** — unchanged since s1 probed it
on 2026-08-01 and **~4 months old today**. This dataset has a documented prior hiatus
(2023-09 → 2024-10, i.e. **13 months**). So "the current file is 3.5 months lagged" may understate
the problem: the lag is not a fixed publication delay but a **variable one with a 13-month
precedent**, which matters for any conditioner built on it and is a far more serious constraint on
using this axis live than the archival decay is.

### 30. OpenMarket — synchronized millisecond Polymarket↔Binance BTC corpus (arXiv:2607.26245, HuggingFace, Apache-2.0) — grade: **verified-live, licence CLEAN for the data, sample ingested and measured; DEAD AS AN ALPHA AXIS by the authors' own out-of-sample null, KEPT as a clock-provenance reference** [§33: killed -> docs/graveyard.md lit_prediction_market_microstructure_vs_book]
- **Provides:** the first public millisecond-level paired Polymarket-BTC / Binance-BTCUSDT corpus
  with explicit pairing metadata. 727,098,247 deduplicated rows across 202 archival snapshots;
  2,936,031 explicit lead-lag pairs; event data on 54 Polymarket / 57 Binance days between
  2026-02-12 and 2026-05-15. Hive-partitioned parquet (`<table>/date=YYYY-MM-DD/`), four splits
  (`unified/` 504 files recommended, `full/` 3,312, a 9,352-row root sample, `features/`).
- **Verified first-hand 2026-08-06 from this box** (not from the paper's claims): arXiv abs HTTP 200;
  HF API `gated=false private=false disabled=false`, 4,253 files, 1,411 downloads, lastModified
  2026-07-31; **two sample parquet downloaded and parsed**. Registration artifact with the full
  measured schema: `docs/research/openmarket_corpus.json`.
- **Legitimacy (§13): CLEAN FOR THE DATA, UNRESOLVED FOR THE CODE — and the two are recorded
  separately on purpose.** The HF dataset declares `apache-2.0` in both `cardData` and the README
  front-matter. The GitHub pipeline repo returns `NOASSERTION` — **no recognised licence on the
  code**, so the Rust collector must not be vendored. Re-implementing from the paper's description
  is unaffected. (The mirror image of the bitFlyer ruling: there, availability was mistaken for
  permission; here, a permissive data licence must not be read across to unlicensed code.)
- **WHY IT IS KILLED AS AN ALPHA AXIS, not deferred:** the paper's central result is its own
  out-of-sample null — 43 microstructure features in a walk-forward logistic do not beat the
  probability already implied by Polymarket's own book, netting −0.116 normalized payoff units per
  trade after stated fees. The mechanism is general and is what makes it permanent: **the book you
  are trying to beat already aggregates the flow your features are derived from.** Graveyarded with
  that mechanism. The corpus is additionally in **archival shutdown** (frozen at tag v0.5.2, no new
  snapshots), so it can never become a live axis — it is a one-time historical reference.
- **WHAT SURVIVES THE KILL, and it is the reason this card exists at all — an L1.46 corroboration
  from outside this desk.** Every `lag_pairs_ms` row declares **three** clocks:
  `binance_source_ts_ms` and `polymarket_source_ts_ms` (venue stamps) plus `paired_at_ms`
  (collector stamp). An independent team treats `t_venue` and `t_recv` as separate first-class
  columns — exactly the discipline L1.46 installed here after 82% of desk data was found carrying
  an undeclared clock.
- **THE MEASURED WARNING, and it bears directly on R0117.** The authors report a 16 ms median
  venue-clock lag, drift bounded to ≤6 ms, and a residual **single-vantage constant-offset
  ambiguity of ≈ ±99 ms**. Measured here on the sample: median lead-lag **+14 ms, IQR [−38, +92] ms**
  — **the declared ambiguity is the size of the entire interquartile range.** A single-vantage
  collector cannot resolve a sub-100 ms cross-venue lead-lag however carefully it stamps; that is a
  structural limit of observing two venues from one point, not a data-quality failing. Their
  response is the transferable method: a **synchronization-free event study on the collector clock
  alone** (Polymarket quotes respond to large Binance moves after a median 347 ms) — an interval on
  ONE clock, never a difference between two. Corroborated here: `paired_at_ms − binance_source_ts_ms`
  has median **6,213 ms** (p95 18,698 ms), so the two bases are not interchangeable even roughly.
- **DATA CAVEAT FOUND HERE, not stated in the abstract:** `price_delta_bps` is degenerate in this
  split — every value lies in [−10000.0, −9999.9], because it differences a Polymarket probability
  (0..1) against a Binance USD price (~80,949). It is a unit-mismatch sentinel, not a spread. Do
  not consume that column.
- **L1.16a re-entry:** a named orthogonal use that does NOT re-run the graveyarded construction —
  e.g. using the corpus as declared-provenance ground truth to validate the desk's own cross-venue
  timing methodology. Absent that, the 727M-row split stays un-ingested.

## LITMINER RUN-6 CARDS (2026-08-12, arXiv q-fin full-subcategory sweep — first execution; ground file `deep_sweep/20260812_litminer_arxiv.md` carries full evidence + URLs)

### 27. Copula-state BTC-hedged alt spread reversion at 5-min (STAT-ARB — the desk's only never-tested family, n=0) — grade: needs-monitoring (screen construction owed; hourly rung of the family is graveyard-KILLED) [§33: deferred(2026-08-24) tier:2]
- **Provides:** the first testable construction for the STATISTICAL-ARBITRAGE family: 3-week
  formation / 1-week trading rolling cycles on Binance USDT-M perps; spread = BTC − β·ALT
  (Engle–Granger per cycle, re-selected — never static), copula conditional-probability entry
  (h(1|2)>0.7, h(2|1)<0.3), 5-MIN bars only.
- **Mechanism (desk-authored — the paper offers none, its weakest point):** coin-idiosyncratic
  unhedged retail flow (momentum chasers, liquidation cascades) pushes the alt leg off its
  BTC-cointegrated level; professionals don't close it because per-pair capacity ($3–11k,
  RU-measured) is below their fixed costs. Loser: the impatient alt-leg taker. Persistence:
  capacity-rationed competition. BTC-hedged by construction ⇒ the 1.54-effective-bets
  directional kill does not bind; 5-min ⇒ the daily price-only grave does not bind.
- **Evidence + replication state (honest):** Tadi–Witzany, Financial Innovation 11 (2025), OPEN
  (PRIMARY full-PDF read; arXiv 2305.06961): 5-min net Sharpe 3.77 claimed 2021-01→2023-01 —
  BUT in-paper baselines are net-negative (plain cointegration −18.7→−88.3%) and the
  independent QFE 10(2) 2026 near-replication kills the HOURLY rung at ALL cost levels with
  funding modeled (graveyard `lit_hourly_copula_pairs_netneg`, interior table extracted this
  run). Read the 3.77 as the selection tail of a mostly-negative family; the 5-min rung is the
  ONLY live region and it omitted funding.
- **Falsifiers (pre-registerable, in order):** (1) add desk funding-panel accrual in the paper's
  own window — flips ≤0 ⇒ dead as published; (2) OOS 2023-02→2026-08 net Sharpe <1 after −58%
  haircut ⇒ decayed; (3) own-fill slippage calibration kills it ⇒ execution-bound, feeds
  MM-execution family; (4) survives only 2021-22 alt-mania segment ⇒ regime artifact.
- **Capacity:** $3–11k/pair, weekly top-2 — fund-invisible, book-sized (§42 lane).
- **Graveyard-check:** family n=0; `statarb_kalman_hedge_ratio_refinement` kill is Kalman-β
  (this is static-EG-per-cycle — no conflict); hourly kill above is the family PRIOR, not a
  block on 5-min. JSAI-2020 instability caveat = why per-cycle re-selection is mandatory.
- **§33 blocker, named:** Stage-A screen construction needs runner code the litminer freeze
  bars; owed by the alpha org via **R0459** (due 2026-08-24). Novelty gate re-run
  owed at screen time; every construction (bar size, α₁, copula family) logged as a charged trial.

### 28. Quarter-hour clock: scheduled-algo order-imbalance leakage, 4–12h horizon (EVENT-AND-CALENDAR × ORDER-FLOW, sub-daily) — grade: needs-monitoring (dual-use; execution-hygiene leg needs NO alpha claim) [§33: deferred(2026-08-24) tier:2]
- **Provides:** clock-phase-resolved order-imbalance at :00/:15/:30/:45 marks → 4–12h forward
  returns, on the desk's OWN-CLOCK L2/trade recorder (the one instrument class R0117 taught the
  desk to demand); funding-window (00/08/16 UTC) conditioning as the desk's differentiator.
- **Mechanism:** interval-scheduled execution (TWAP/rebalance/funding-anchored bots) fires on
  round marks; the printed imbalance leaks persistent parent flow. Loser: the principal behind
  the clock-scheduled executor paying impact on a predictable schedule; persists because
  cron-shaped execution is operationally standard and its leakage is invisible in the
  executor's own benchmarks.
- **Evidence + replication state:** Kim & Hansen arXiv 2607.09426 (abstract + v2 ack read):
  OOS opening-return predictability; imbalance→4–12h; roundness drop = algo signature. Lineage
  REPLICATED+published: Hansen–Kim–Kimbrough JFEC (arXiv 2109.12142) ties vol/volume periodicity
  to algorithmic trading and FUNDING TIMES across three venues. Crowding caveat: QuantPedia
  publicises the 2021 periodicity layer; the 2026 return-predictability layer is new. No cost
  accounting in the abstract — net-tradability UNMEASURED, not claimed.
- **Falsifiers:** (1) own-data clock-phase replication fails ⇒ sampling artifact, dead;
  (2) predictability real but net<0 at desk size ⇒ demote to EXECUTION HYGIENE (don't execute
  ON marks — negative capacity requirement, feeds the 66bps execution-gap program) — that leg
  is valuable with NO alpha claim; (3) Binance-only ⇒ single-venue fragility; (4) sign flips
  across funding windows ⇒ confounded with carry (hunted family), demote.
- **Capacity:** most-liquid perps, hours-horizon — capacity unbinding; crowding is the risk.
- **Graveyard-check:** EVENT-AND-CALENDAR n=1 thin; flow-conditioned intraday ≠ the price-only
  graves (both 420/0-daily and the new `lit_intraday_ohlcv_mnq_14of14` 5-min OHLCV kill — this
  card is imbalance-conditioned, exactly the exception class those kills leave open). CAUTION
  for the builder: `libs/validation/event_study.py` is ONE-SIDED POSITIVE (desk memory) —
  handle negative-direction effects explicitly.
- **§33 blocker, named:** **R0459**, alpha org, due 2026-08-24; cheapest first build is
  the hygiene leg (mark-avoidance in the executor's child-order timing — but executor code is
  MONEY PATH: L1.38 change-window check applies to that consumer, not to the measurement).

### 29. Polymarket-vs-Deribit binary wedge on BTC threshold contracts (VOL-AND-OPTIONS relative value — NOT the EV-rejected DVOL variance-carry) — grade: needs-legitimacy-review (TRADING leg only; measurement leg is free and §13-clean) [§33: deferred(2026-08-24) tier:2]
- **Provides:** hourly wedge series = Polymarket Yes price − discounted option-implied binary
  (Deribit surface the desk already holds) at matched strike/maturity; wedge as (a) tradeable
  RV candidate, (b) zero-execution positioning-sentiment input to the options book.
- **Mechanism:** favourite-longshot demand — prediction-market bettors overpay low-probability
  Yes (lottery consumption); option MMs cannot close it: KYC/jurisdiction segmentation, no
  cross-margin, Polygon rails, UMA oracle-resolution risk ⇒ a REGULATORY-segmentation moat that
  does not decay via publication. Loser: the longshot bettor.
- **Evidence + replication state:** Portnaya arXiv 2606.19517 (abstract-grade): 5.6pp mean gap
  (t=6.46), pooled 6.3pp, **Deribit extension 11pp**, AR(1) half-life ≈4h, wedge concentrated
  at low-prob/long-maturity; delta-hedged proxy "profitable after conservative costs, marginal
  precision". No replication (2mo old). BOUNDARY mapped by an independent failure: the fast end
  is DEAD (graveyard `lit_polymarket_15min_binary_ml`, −0.116/trade) — the wedge lives ONLY at
  long-maturity/low-prob. 2026 practitioner corroboration logged in the ground file.
- **Falsifiers:** (1) desk-rebuilt wedge |mean| < both legs' fees+spread ⇒ measurement-only
  forever; (2) wedge only where Polymarket depth <$1k ⇒ below even this book, kill; (3) wedge
  profile vs time-to-resolution shows it is UMA-risk compensation ⇒ not mispricing;
  (4) legitimacy review refuses Polygon/Polymarket ops surface ⇒ signal-only permanently.
- **Capacity:** threshold books $10²–10⁴ deep — fund-invisible, desk-sized; Deribit leg deep.
- **Data leg [DATA-LOOT, catalogued this run]:** **OpenMarket** (arXiv 2607.26245) — CC-BY-4.0,
  727M rows, ms-paired Polymarket/Binance, 2.9M explicit lead-lag pairs
  (huggingface.co/datasets/gregyoung14/openmarket-btc-polymarket; verify LICENSE file at
  ingest). Dual use: free wedge-measurement backfill AND an R0117-grade synchronized lead-lag
  testbed (the named enabling-change class for that lane — subject to the raw-trades-not-marks
  rule, inbox 2026-08-12 G).
- **Graveyard-check:** VOL-AND-OPTIONS n=2 thin; distinct mechanism from the EV-rejected DVOL
  vol-carry (variance-premium harvesting ≠ cross-venue RV on binaries); no prediction-market
  graveyard rows. CLEAR for measurement.
- **§33 blocker, named:** measurement construction in **R0459** (alpha org, 2026-08-24);
  the TRADING leg additionally gated on a legitimacy/ops ruling (jurisdiction + Polygon rails +
  UMA risk) — routed to the needs-legitimacy-review queue via this card's grade, decision lane
  same as the KR/JP venue reads.

### 31. Binance COIN-M (dapi) public market data — the home venue's OTHER futures book, zero desk coverage — grade: **verified-clean 2026-08-12 — the BULK ARCHIVE half is now verified separately (checksum + ground-truth diff executed); "full-history depth unknown until pulled" is CLOSED. Collector constraint found: build the universe from the ARCHIVE listing, never from `exchangeInfo` (30 live vs 272 archived = 89% of instrument history omitted, incl. all 212 expired quarterlies the convexity screen needs).** [§33: screened -> data/data_universe_map.json `99-binance-coinm-vision-archive`]
> **PROBED 2026-08-12 (EN frontier miner session G, keyless, no auth):** `dapi.binance.com/dapi/v1/premiumIndex?symbol=BTCUSD_PERP` → live mark/index/funding (0.00003844) + `nextFundingTime`; `/dapi/v1/exchangeInfo` → **30 instruments: 20 COIN-M perps (BTC/ETH + 18 alts) + 5 quarterly-delivery underlyings (BTC/ETH/BNB/SOL/XRP × current+next quarter)**. Same endpoint family as the fapi (USDT-M) data the desk already collects — identical §13 posture, identical collector pattern; historical klines (`klines`, `markPriceKlines`, `indexPriceKlines`, `premiumIndexKlines`, `fundingRate`) serve keyless, so **backfill needs no standing daemon**. L1.46 note: dapi rows carry venue event-time fields exactly like fapi; stamp clock provenance at collection.
> **WHY (mechanism found same run, NP 161162 translation — the 1990s convexity-adjustment-neglect family):** inverse contracts settle PnL in coin ⇒ convex USD payoff ⇒ fair COIN-M basis differs from USDT-M basis by a computable convexity adjustment (the FRA-vs-futures wedge, crypto edition). The screen: measured COIN-M-vs-USDT-M same-expiry basis differential vs its theoretical convexity value across the 5 quarterly underlyings; residual = collateral-clientele segmentation premium (coin-collateral hedgers — miners, coin-custody entities — cannot switch margin currency without changing custody posture: the who-must-trade story). Secondary unlocks: 20-pair COIN-M/USDT-M funding-differential panel; COIN-M OI share as a positioning axis.
> **SCREEN-ON-DISCOVERY (run this session, at the only stage runnable without the data):** mechanism `coinm_usdtm_basis_convexity_rv` EV-gated honestly → **REJECT 0.0009** (p_survive 0.105, est_sharpe 0.5, breadth 5, orth 0.5, 12h/1.2×, tags funding_family+crowded_known; conservative narrow-tag reading also reported: 0.0002 — both logged, neither rescues). Mechanism → prospector_watchlist memory with a MEASUREMENT promotion trigger; the AXIS is the deliverable today: free, home-venue, feeds the screen the moment the panel exists. Full-history depth unknown until pulled (fapi-era caveat: gentle pulls, 429 discipline per entry 95).
> **SOURCE:** NP thread 161162 (2012-06-20→07-04, Wayback 20121015082245, posters MrKlugh/gill/sas) + first-party Binance API docs/probe. **DERIVES-FROM:** the 161162 thread cites nothing (checked — 3 posts, era lore + one risk.net link on reverse cliquets); the convexity-adjustment mechanism is textbook (independently derivable); the crypto translation is this desk's. Universe map: `98-binance-coinm-dapi`. Recommendation row filed this run (screen construction, engineering-enabled seat).
> **SECOND, INDEPENDENT mechanism prior (CN frontier miner 2026-08-12, era-archaeology — genuine cross-ecosystem convergence, queue place not lower bar):** the funding-differential panel has a DEMAND-side clientele the convexity story doesn't name: **synthetic-dollar holders**. 8btc thread-172717 (2018-05-26, BitMEX board, Wayback 20180902020842id_) shows CN practitioners deriving in public that a 1x coin-margined inverse short = USD account with no liquidation boundary (OP ran the testnet experiment: liq price "一亿", ≈+∞) and CHOOSING it over USDT — "比换成USDT更稳定更省手续费…做空的资金费率会更划算" (more stable than USDT, cheaper fees, and the short side's funding pays). Capital-control-barriered traders using inverse shorts as their dollar account = structural short-side flow on COIN-M ⇒ **persistent COIN-M-vs-USDT-M funding skew, widening when fiat rails are barriered and when stablecoin trust degrades**. Falsifier the era text supplies: the clientele needs coin-native holders barred from clean USD rails — if the skew doesn't co-move with rail-barrier proxies (stablecoin discount episodes, regional rail closures), the prior is wrong. SOURCE: 8btc thread-172717. DERIVES-FROM: NONE (checked — forum-native reasoning + testnet experiment; predates nothing it cites, independent of NP 161162's 1990s IR lore). Era corroboration for the linear-vs-inverse convexity confusion: the thread's first reply applies linear logic ("coin doubles ⇒ ruin") and is corrected by experiment — the exact confusion the convexity screen prices.

## 2026-08-12 — JP miner: マケデコ (market-api) calendar opened; one axis worth a decision

### 29. J-Quants API (JPX's own free JP-equity data, incl. 売買内訳データ = flow by investor category) — grade: **excluded-paid, VERIFIED 2026-08-12. The title of this card is FALSE on two counts: the investor-category axis is NOT free (投資部門別情報 = LIGHT ¥1,650/mo; 売買内訳データ = PREMIUM ¥16,500/mo, and they are DIFFERENT datasets the card conflated), and the v1 API it describes returns HTTP 410 GONE. §38 replacement found: JPX publishes the investor-type table free on its own website.** [§33: killed -> data/data_universe_map.json `100-jquants-api` + `101-jpx-investor-type-free`]
- **WHAT + HOW FOUND.** Surfaced by opening the マケデコ Advent Calendar (new ground this run,
  `qiita.com/advent-calendar/{2023,2024,2025}/market-api`, 74 entries mapped to
  `data/jp_makedeco_advent_calendar.jsonl`). J-Quants is **Japan Exchange Group's own** free API;
  four separate calendar entries are practitioner writeups of it, including a **V2 release**
  (2025 s2d22), an **index OHLC endpoint** (2023 s1d20) and — the interesting one —
  **売買内訳データ, trading value broken down BY INVESTOR CATEGORY** (2023 s1d23).
- **WHY THE FLOW TABLE IS THE ONLY PART THAT MATTERS HERE.** Per the translate-don't-copy duty,
  `commitment of traders → OI by venue + long/short account ratio`. JP equity flow-by-investor-type
  (foreign / individual / institution / prop) is a **positioning panel published by the exchange
  itself**, which is the structurally-unbuyable venue-truth class the moat doctrine prefers. That
  is a real orthogonal axis, not another price feed.
- **BUT BE HONEST ABOUT PRIORITY AND ABOUT WHAT I DID NOT DO.** This desk trades **Binance crypto**;
  JP cash equities are the lowest rung of the standing source priority. The axis is **CATALOGUED,
  NOT VERIFIED**: I did not read the licence, did not hit the endpoint, did not check the
  registration wall (J-Quants has free and paid tiers, and the free tier is understood to carry a
  **12-week data delay** — unconfirmed by me, so it stays a claim). No screen is owed on an axis
  whose licence has not been read.
- **§13 STATUS: UNREAD.** Decision owed 2026-08-19 alongside the other JP venue items.
- **THE TRANSFERABLE QUESTION IT RAISES (worth more than the axis itself):** does Binance publish
  any equivalent *category* breakdown of flow? The desk already collects the long/short **account**
  ratio and top-trader ratios — which are the closest existing analogue — so the honest prior is
  that this axis is **already partly held** and its marginal value is the JP-equity cross-section,
  which the desk does not trade. Recorded so the next reader does not re-discover it as novel.

---

## SESSION SUMMARY — 2026-08-12 (AR frontier miner, seat's first run)

**One axis carded, and it is carded WITH ITS CEILING** — the point of the card is to stop the desk
re-deriving a design that cannot work. Deliberately **no bulk-add** of the AR seed list: the desk's
measured bottleneck is verification, not cataloguing, and a source earns a graded card only by
producing something. Everything else found this run is recorded as leads in
`prospector_coverage.md` (AR row + session note), not as cards.

- **`hijri_calendar_overlay` — VERIFIED-CLEAN, and PERMANENTLY UNDERPOWERED AS AN ANNUAL EVENT.**
  Free and self-computable (no vendor, no key, no licence): the Hijri→Gregorian mapping is public
  and the Ramadan windows are tabulated. Produced a real artifact this run:
  **`data/ar_ramadan_power_check.json`** (BTCUSDT D1, 2019-09-09→2026-08-12, 2,530 days,
  208 Ramadan-days, **7 episodes**).
  - **Verified use:** as a **conditioning/exclusion variable** and for **cross-sectional** designs
    (7 events × N assets/venues), where it retains power.
  - **Killed use:** the **annual event study** — 80%-power MDE is **3–6× the observed effect** on
    returns, funding and basis; halving the MDE needs **28 episodes = 21 more years**. Graveyarded
    as `hijri_ramadan_calendar_axis` → `unmeasurable_by_construction` (**not** refuted; L1.25).
  - **Measurement caveat that is also a tradability caveat:** windows are **moon-sighted**, so the
    start date varies ±1 day by jurisdiction and is **not deterministic ex ante** — any design
    keying on the exact first day inherits an irreducible ±1d alignment error.
  - **Companion measurement (the reusable part):** within-event **ICC 0.000 / 0.525 / 0.695** for
    returns / funding / basis → design effects 1.0 / 16.1 / 21.0. See **OP-053** and inbox **#116**.

- **Leads found, NOT carded (unverified — recorded so they are not lost, not so they are trusted):**
  GCC regulator/exchange layer (VARA, ADGM, SCA, CMA Saudi, `bitoasis.net`, CoinMENA) — the AR
  analogue of the BR seat's government-dataset win, and the direction the AR ground actually
  rewards now that its premium axis is dead. Chainalysis MENA regional figures (7.5% of global
  on-chain value received, $338.7bn 2024; 93% in $10k+ transactions) are **summary-grade, read
  through search results, primary not opened** — do not cite as verified.

- **§13 note affecting future data digs:** `hawamer.com` (largest Gulf trading forum) **denies
  `ClaudeBot` by name** under Cloudflare-managed rules with an EU DSM Art.4 reservation and
  `Content-Signal: ai-train=no` — **HARD STOP, archives included**. `bitoasis.net` runs an AI-agent
  **allowlist** (OAI-SearchBot/ChatGPT-User/PerplexityBot allowed, CCBot denied, ClaudeBot unnamed →
  permitted under `*`). Per-agent policy is emerging; re-probe rather than carrying a binary prior.

---

## SESSION SUMMARY — 2026-08-12T15:31Z (FREE-DATA-ALTERNATIVES miner, standing weekly run)

**STATUS: IN PROGRESS — note written BEFORE researching per the COMPLETION CONTRACT (2026-07-25).**
Items resolve in place below; if this run is killed, this note is the durable resume point.

**Cadence defect found before any hunting:** `data/cadence_state.json.last_data_axis_dig` reads
**2026-07-19** — 24 days stale on a **weekly** mission. Runs have happened since (07-24, 07-25,
07-31, 08-12 seats all wrote cards here) but none stamped the key, so the desk's own cadence meter
has been reporting this mission as ~3.4 cadences overdue while it was in fact running. An organ
whose done-key is never stamped is indistinguishable from a dead one (L1.28a: unmeasured = zero).
Stamped at close of this run.

**WHY THESE ITEMS (§33 tier order, not convenience).** `source_backlog_next.py` reports 16 pending
verification + 6 pending legitimacy. §33 says work the expensive tier first; deferral expiry breaks
ties.

- **NOT TAKEN — card 1 Upbit portal (T3, due 08-15, soonest expiry).** Deliberately skipped and this
  is the disposition: it has been independently verified **three times** (07-25, 08-11, +1) and the
  blocker is a **principal ruling on commercial-use scope**, not anything an agent can test. Its own
  card says *"COST OF WAITING IS ZERO"* and *"DO NOT BUILD A COLLECTOR YET"*. A fourth verification
  would be re-litigating settled evidence (L1.16a) wearing a productivity costume. **The one unused
  lever is already named on the card and is the principal's to pull: written clarification from
  `historical_data@upbit.com`.** No agent sends that mail.
- **NOT TAKEN — card 23 中文 practitioner corpus (T2, due 08-18):** explicitly *"corpus dig owed to
  the CN seat"*. Taking another seat's owed work would double-count the conversion.

**ITEMS TAKEN THIS RUN (depth maxed, breadth bounded):**

1. **Card 31 — Binance COIN-M (dapi) ARCHIVE depth (T2, due 08-19).** The 08-12 probe verified the
   *live API*; the card states **"Full-history depth unknown until pulled"**. Category 1 of this
   mission is *exchange-native dumps/archives* — the bulk `data.binance.vision` bucket, which is a
   **different artifact from the REST API** and is the half that replaces a paid tick/kline vendor.
   Deliverable: measured archive depth per COIN-M instrument + a verify-don't-trust diff of the
   archive against the REST API for the same window.
2. **Card 29 — J-Quants API (T3, due 08-19).** Genuinely **catalogued-unverified**: licence unread,
   endpoint never hit, the claimed free-tier 12-week delay unconfirmed. Cheapest real close on the
   board and it is owed the same day as item 1.
3. **SEARCH-SPACE EXPANSION (≥25% reserve, mission §11/§12).** New source class, recorded below.

### ITEM 1 — RESOLVED. Card 31 Binance COIN-M: the ARCHIVE is verified-clean, and it is a
### materially different (and much larger) artifact than the API the 08-12 probe verified.

**GRADE: verified-clean** (checksum + ground-truth diff both executed this run, first party, keyless).
Card 31 is re-graded from *"verified-live; collector/backfill owed"* — the **"full-history depth
unknown until pulled"** clause is now CLOSED. Universe-map entry `98-binance-coinm-dapi` updated.

**VERIFY-DON'T-TRUST — EXECUTED, NOT PLANNED.** `BTCUSD_PERP-1d-2024-01.zip`:
- Published SHA256 sidecar `ef361aef…70b7` vs computed → **exact match**.
- Archive vs live `dapi/v1/klines` over the same 31 bars, 7 fields each (O/H/L/C/volume/baseVol/
  trades) → **0 mismatches, identical to the last decimal**. 217 field comparisons.

**MEASURED DEPTH (all first-party S3 listings, paginated):**

| dataset | tier | span | n | state |
|---|---|---|---|---|
| klines (15 intervals 1m→1mo) | monthly | 2020-08 → 2026-07 | 72 mo | live |
| metrics (OI + positioning) | daily | 2021-07-08 → **2026-08-11** | 1,754 d | **live, T+1** |
| fundingRate | monthly | 2022-07 → 2026-06 | 48 mo | live |
| liquidationSnapshot | daily | 2023-06-25 → **2024-10-14** | 472 d | **FROZEN ~22 mo** |

**FOUR FAILURE MODES, EACH FOUND BY HITTING IT — these are the deliverable, not the depth table:**

1. **THE S3 LISTING SILENTLY TRUNCATES AT `MaxKeys=1000`, AND IT NEVER THROWS.** The unpaginated
   listing of `metrics` returned exactly 500 zips (+500 checksums = the 1000 cap) and reported the
   series **ending 2022-11-24**. Paginated with `continuation-token`: **1,754 files ending
   2026-08-11**. A **3.7-year understatement that looks like a complete answer** — the desk's own
   documented lesson ("paginate every venue history endpoint; past the cap the numbers keep looking
   plausible") reproduced exactly, on a different endpoint class than the one it was learned on
   (Binance *income* REST). **Every S3-listing-driven depth claim in this file predating today
   should be treated as a lower bound until re-listed with pagination.**
2. **SCHEMA DRIFT AT A DATED BOUNDARY: the CSV header appears on 2022-07-01 and not before.**
   Bisected: `2022-06` has no header, `2022-07` onward does; 12 columns throughout. **The dangerous
   direction is silent:** a backfill hardcoding `header=0` (correct for everything after 2022-07)
   **silently deletes the first real bar of every pre-2022-07 monthly file** — no error, no warning,
   just a missing bar per month across the earliest 23 months, which is precisely the regime an OOS
   split is starved for. `header=None` fails loudly instead, which is the safe way to be wrong.
3. **THE MONTHLY AND DAILY TIERS ARE NOT NESTED — neither is a superset of the other.** monthly
   carries `fundingRate` and daily does **not**; daily carries `bookDepth`, `liquidationSnapshot`
   and `metrics` and monthly does **not**. A collector that reasonably assumes "monthly = aggregated
   daily" (the near-universal convention) never collects OI, book depth or liquidations at all, and
   one built off daily alone never collects funding. Verified on both `cm` and `um`.
4. **`liquidationSnapshot` EXISTS FOR COIN-M AND NOT FOR USDT-M.** `futures/um/daily/
   liquidationSnapshot/` returns the bare self-prefix (empty); `futures/cm/daily/` carries **118
   symbols**. The COIN-M window is frozen (2023-06-25 → 2024-10-14) with **6 interior missing days**
   (2023-09-09/23/25, 2024-06-01/11/12) — real gaps, not weekends, in a 24/7 market.

**SURVIVORSHIP — AND IT POINTS THE OPPOSITE WAY FROM UPBIT (card 1), WHICH IS THE REUSABLE PART.**
Archive holds **272 kline symbols; the live `exchangeInfo` returns 30**. So **242 instruments (89%)
are expired or delisted and invisible to any collector driven off `exchangeInfo`** — which is
exactly the collector pattern card 31 proposes ("identical collector pattern" to the fapi). Of the
242: **30 delisted perps** (LUNA, FTM, MATIC, XMR, OP, WLD, WIF, APT, ENS…) and **212 expired
quarterlies**. Set difference the other way is **empty** — no live instrument lacks an archive, so
the archive strictly dominates the API for history.
- **Upbit purges delisted candles (the desk's recorded lesson: "treatment group erased"). Binance
  RETAINS them.** Two venues, opposite survivorship polarity, and the *archive-vs-API* axis is
  where the difference lives — not the venue. **The rule this generalises to: for any venue, the
  instrument list is a point-in-time object, and reconstructing it from today's `exchangeInfo` is a
  look-ahead in the UNIVERSE rather than in the prices** — the same class as the `pct_circ_now`
  denominator leak already on the desk's lesson list, and it fails toward a FALSE NULL.
- **This is what makes the card-31 convexity screen buildable at all:** that mechanism prices
  COIN-M-vs-USDT-M *same-expiry* basis across quarterly underlyings. The quarterlies it needs are
  **212 expired contracts** — every one of them absent from the API and present in the archive. The
  screen was EV-rejected (0.0009) on its alpha claim and that rejection stands; the point here is
  narrower and it is a **data-availability** point: had the collector been built off `exchangeInfo`
  as proposed, the panel would have been **structurally incapable** of ever testing it, and the
  failure would have read as "no data" rather than "wrong collector".

**WHAT IT REPLACES (category 6).** `metrics` is a **5-minute positioning panel** —
`sum_open_interest`, `sum_open_interest_value`, `count_toptrader_long_short_ratio`,
`sum_toptrader_long_short_ratio`, `count_long_short_ratio`, `sum_taker_long_short_vol_ratio` — free,
5 years deep, T+1, first-party. That is the substance of **Coinglass's paid OI/long-short history**
for this venue. `liquidationSnapshot` is **per-order** (side, order_type, TIF, price, average_price,
fill quantities), i.e. **finer than the aggregated liquidation feeds vendors sell** — for its frozen
472-day window. Honest residual: the frozen window means COIN-M liquidations are **dead data**
(mandate §7) — one-time-exhaustible, will never extend, and worth archiving to Bronze *because*
nobody will regenerate it. **Forward liquidation coverage is destroyed-at-source on both books**
and is NOT replaced by this find.

**GAP OBSERVED, NOT YET EXPLAINED:** the 2026-08-11 metrics file holds **285 rows where a complete
5-min day is 288**. Three missing buckets in one spot-checked day; not characterised across the
series, so it is recorded as an open question, not a rate.

**§13:** first-party Binance public bucket, keyless, no auth, no robots restriction on
`data.binance.vision`; same posture as the USDT-M archive the desk already ingests. Clean.

**ROUTING.** No new alpha claim, so no EV-gate pre-registration is owed — the card-31 mechanism was
already EV-rejected this morning and nothing here rescues it. The deliverables are (a) the re-grade,
(b) the four failure modes, which are **collector-design constraints** and route to
`improvement_inbox.md`, and (c) the pagination trap, which is a **method defect affecting prior
depth claims in this very file** and is the highest-value thing found this run.

### ITEM 2 — RESOLVED, AND IT IS A CLEAN KILL. Card 29 J-Quants: the one axis with an economic
### story is the single most expensive rung on the venue's own price list.

**GRADE: excluded-paid (free-first protocol; paid-data trigger NOT met).** Card 29 goes from
*catalogued-unverified* to **CLOSED**. §13 question is moot — there is no licence dispute, there is
a price tag.

**FIRST-PARTY EVIDENCE** — JPX 総研 press release 2025-08-22, `www.jpx.co.jp/corporate/news/
news-releases/6020/20250822-01.html`, fetched in full and parsed (the app host `jpx-jquants.com`
CloudFront-403s every non-browser client including WebFetch; **the corporate host does not** — that
host split is the reason three prior readers had to rely on search-index renderings). The complete
plan matrix, verbatim from the release:

| dataset | 無料 ¥0 | ライト ¥1,650 | スタンダード ¥3,300 | プレミアム ¥16,500 |
|---|---|---|---|---|
| データ提供期間 | **過去2年 [12週間遅延]** | 過去5年 | 過去10年 | 提供期間全て |
| 上場銘柄一覧 / 株価四本値 / 財務情報 / 決算発表予定日 / 取引カレンダー | ✓ | ✓ | ✓ | ✓ |
| **投資部門別情報** (investor-category flow) | **–** | ✓ | ✓ | ✓ |
| **売買内訳データ** (the card's target axis) | **–** | **–** | **–** | **✓** |

**THREE THINGS THE CARD GOT WRONG, AND THE SECOND IS THE ONE WORTH REMEMBERING:**

1. **The 12-week free-tier delay was flagged "unconfirmed by me". It is now CONFIRMED first-party**
   — and it comes with a second limit the card never mentioned: **free history is 2 years**, not
   full depth.
2. **THE CARD'S CENTRAL EQUATION IS FALSE.** It states *"売買内訳データ = flow by investor
   category"*. These are **two different products at two different price points**: 売買内訳データ is
   the **order-attribute breakdown** (proprietary vs brokerage, short-sale flags) and sits at
   **PREMIUM ¥16,500/mo**; the by-investor-category flow the card actually wanted is **投資部門別情報**
   at **LIGHT ¥1,650/mo**. The card fused a cheap dataset's *meaning* onto an expensive dataset's
   *name* and then reasoned about the merged object. **Neither is free**, so the card's premise —
   *"JPX's own **free** API, incl. flow by investor category"* — is false on both readings.
3. **THE API THE CARD DESCRIBES NO LONGER EXISTS.** `api.jquants.com/v1/*` returns **HTTP 410 Gone**
   — `{"message": "J-QuantsはV2に移行しました。"}` — on every v1 path probed (`/v1/listed/info`,
   `/v1/token/auth_user`). V1 token auth is retired in favour of dashboard-issued API keys. **All
   four マケデコ Advent Calendar entries the card was built from (2023 s1d20, 2023 s1d23, 2025
   s2d22) document a dead API surface.** A practitioner-writeup corpus dates silently: the calendar
   entry is still up, still reads as current, and its endpoints are gone.

**§38 — THE EXCLUSION SPAWNED ITS HUNT, AND THE HUNT SUCCEEDED (partially).** Excluding a paid
source without finding its free primary would shrink the universe by attrition. **The primary here
is the exchange's own website, and it gives away what the API bills for:**
- **`www.jpx.co.jp/markets/statistics-equities/investor-type/`** (JA) and
  `…/english/markets/statistics-equities/investor-type/` (EN) — **投資部門別売買状況 published
  WEEKLY as free `.xls` + `.pdf`, no registration, no API key, no plan tier, no 12-week delay.**
  25 file links on the JA index (`stock_val_*` = value, `stock_vol_*` = volume, weekly stamps).
- **VERIFIED THIS FAR AND NO FURTHER — stated precisely because the difference matters:** HTTP 200,
  99,840 bytes, magic `d0cf11e0a1b11ae1` = **genuine OLE2/BIFF**, i.e. a real legacy Excel file and
  not an HTML error page wearing an `.xls` extension. **The column semantics are UNPARSED**: the
  box has no `xlrd` and this mission runs under the research freeze, so installing one is out of
  scope. **I did not read the table, so I do not claim its contents.**
- **Honest residual:** archive **depth UNMEASURED** — the current index carries recent weeks only
  and my guess at a back-number path 404'd. Whether history runs to 2015 or to last quarter is
  **unknown**, and the ¥1,650 tier's value is precisely that unknown.
- **The general shape, which outlives this card:** *the venue sells via API what it publishes free
  on its website, in a worse format.* Worth testing against every venue the desk pays or would pay
  for. That is the reusable finding here, not the JP equity axis.

**BUT THE HONEST BOTTOM LINE, AND IT IS NOT CLOSE.** This is **JP cash equities**; the desk trades
**Binance crypto**. The card itself said so. Free J-Quants gives OHLCV + financials on a market the
desk does not trade, 2 years deep, 12 weeks stale. Even the successful §38 replacement is a **weekly
JP-equity flow table in legacy Excel**. **Marginal value to `max E[log W_T]`: indistinguishable from
zero.** No screen is owed, no EV-gate pre-registration is owed, and no ingestion is proposed. The
deliverable is the **kill plus the three corrections**, so no future reader re-opens this believing
JPX hands out investor-flow data for free.

**INGESTION NOTE (routes to improvement_inbox):** legacy `.xls` (BIFF/OLE2) is a **recurring**
Japanese-government/exchange publication format and the desk cannot read it — `pandas.read_excel`
raises `ImportError: Missing optional dependency 'xlrd'`. Any future JP/KR government or exchange
ingestion hits this wall. Recording the dependency, not installing it.

---

### ITEM 3 — SEARCH-SPACE EXPANSION (≥25% reserve). New source class: **exchange-published
### bulk archives as a CLASS, audited for the tier-asymmetry defect found in item 1.**

Item 1 found that Binance's bulk bucket is **not** shaped the way a collector would assume: monthly
and daily tiers are **non-nested**, one book has liquidations the other does not, and the S3 lister
silently truncates at 1,000 keys. **That is a claim about `data.binance.vision`. It is worth knowing
whether it is a claim about the CLASS** — because every finding in item 1 is a collector-design
constraint the desk would otherwise re-learn per venue, at the cost of a silently-wrong backfill
each time.

**Probed this run (first-party, keyless, listing-only — no bulk pulls):**

| venue | bulk archive | reachable | shape finding |
|---|---|---|---|
| Binance | `data.binance.vision` (S3-XML) | ✅ | tiers **non-nested**; lister truncates at 1000 keys; header drift 2022-07-01 |
| Bybit | `public.bybit.com/trading/` | ✅ | **HTML directory listing** (`Directory listing for /trading/`), **1,889 symbol dirs in one response, no cap, no pagination** |
| OKX | `www.okx.com/cdn/okex/traderecords/` | ✅ files, ❌ index | per-day zips fetch fine (`…/20260810/BTC-USDT-trades-2026-08-10.zip` → **200, 2.34 MB**; 2025-06-10 → **200, 5.41 MB**) but the directory itself returns **HTTP 200 with a ZERO-BYTE body** |

**THE CLASS-LEVEL FINDING — a taxonomy of how bulk archives are ENUMERATED, which is the thing that
actually breaks backfills:**
- **S3-XML listers (Binance)** — enumerable, and **silently truncate**. Failure is *invisible*: you
  get a plausible short answer.
- **HTML directory listings (Bybit)** — enumerable, no key cap, but schema-fragile to site redesign.
- **Soft-empty index (OKX)** — **not enumerable, and it lies in the safe-looking direction.** The
  files are real and serve fine, but the directory returns **200 with a zero-byte body** rather than
  404. **A liveness check written as `if resp.status_code == 200` passes against nothing at all** —
  the exact heartbeat-vs-payload defect on the desk's lesson list ("a heartbeat proves the loop is
  alive, never that the pipe is"), reappearing as an *archive* rather than a websocket. Every URL
  must be constructed from a date grid and probed individually, so **absence of a file is
  indistinguishable from a gap in the data** unless the venue documents its calendar — "absence
  resolves to a clean verdict", WS-005, relocated into the data layer.
- **The transferable rule:** *before trusting any bulk-archive depth figure, ask which of the three
  enumeration modes produced it.* A depth claim from mode 1 is a **lower bound** (truncation), from
  mode 3 it is a **guess** (construction). Only mode 2 gives a real count. **This desk has depth
  claims from all three modes recorded in this file with no distinction between them.**

**HONEST LIMIT ON THIS ITEM:** reachability and enumeration-mode were probed; **no cross-venue
depth or content verification was performed** (that is the next run's work, and it is named below).
This item is graded **UNVERIFIED for content, verified for reachability + enumeration mode**.

---

## NEXT UN-EXHAUSTED GROUND (L1.35 — named so the chain survives this run)

1. **Re-list every S3-derived depth claim in this file with pagination.** Item 1 proved the
   unpaginated lister understates by years and never errors. Prior depth figures here are lower
   bounds of unknown tightness. **Highest-value item on the board** — it re-grades existing cards
   rather than adding new ones, and it is pure verification, which is the desk's stated bottleneck.
2. **Bybit + OKX bulk archives to item-1 depth** — checksum discipline, ground-truth diff, tier
   nesting, survivorship (delisted instruments present or purged). Item 3 established *how to
   enumerate* them; the verification itself is undone.
3. **The archive-vs-API survivorship polarity test, run across venues.** Item 1 found Binance
   retains 242 delisted/expired instruments the API hides (89%) while Upbit purges. **Neither is
   the default.** Every venue the desk collects needs this checked, because the failure is a
   look-ahead in the *universe* and it fails toward a false null.
4. **COIN-M `metrics` 285-vs-288 row question** — three missing 5-min buckets in the one day spot-
   checked; unknown whether that is routine or episodic. Cheap to characterise across 1,754 files.
5. **Card 1 Upbit remains blocked on the principal**, not on research. Untouched by design.

## 2026-08-12 — BRAIN hunter s2: the field taxonomy, and what it says about the desk's data surface

### 32. WorldQuant BRAIN data-field catalogue (USA TOP3000, delay=1) — a competitor's ENTIRE feature surface, enumerated — grade: **structural-reference, no ingest possible (equities), routed for its SHAPE not its contents** [§33: screened -> docs/research/search_operator_library.md]

**SOURCE:** `QuantML-Research/wq-alpha-research`, `references/wq_usa_top3000_delay1_data_fields_summary.json` — a machine-generated summary of a 219-page field enumeration. **NO LICENCE FILE ⇒ all-rights-reserved**; counts and categories are facts, extracted as such, **no verbatim text or bulk data reused**, nothing installed. DERIVES-FROM: **NONE (checked)** — no desk artifact references this repo.

**THE FIELD SURFACE, 4,367 fields:**

| category | fields | share | crypto analogue on this desk |
|---|---:|---:|---|
| fundamental | 1,652 | 37.8% | **near-total gap.** On-chain fundamentals: supply/emission schedules, unlocks, TVL, protocol revenue, treasury flows, staking ratio, active addresses |
| analyst | 1,324 | 30.3% | no sell-side analogue, but the *forward-expectation* role maps to funding, basis term structure, options-implied, prediction markets |
| news | 996 | 22.8% | exchange announcements (listing/delisting), governance votes, incident feeds |
| pv (price-volume) | **195** | **4.5%** | **the desk's near-entire surface** |
| option | 138 | 3.2% | Deribit IV surface, 25Δ skew, put/call — reachable and largely unmined |
| model | 40 | 0.9% | derived/model factors |
| socialmedia | 22 | 0.5% | the **smallest** category on a platform that has it |

By **type**: MATRIX 2,828 · **VECTOR 1,387** · **GROUP 142** · UNIVERSE 6 · SYMBOL 4.

**THE TWO NUMBERS THAT MATTER, AND THE THIRD THAT CONSTRAINS THEM.**

**(1) GROUP is a first-class data TYPE, and there are 142 of them.** The desk's 08-07 gap was framed as "we have no sector column". That framing was too small: on a mature platform *grouping is a whole data family* — 142 distinct ways to partition the same universe. Session 1 built **4** maps (`data/crypto_grouping_map.json`). That is the correct start and it is 3% of the analogous surface. **The gap is not one map, it is a taxonomy axis**, and it is now the clearest instance of the desk's L1.11 moat law: groupings are *manufactured* from owned data, carry zero licence surface (session 1 built all four from desk-owned D1 bars), and each one is a new orthogonal question to ask of every existing signal.

**(2) VECTOR-typed fields are 32% of the surface and the desk has no vector type at all.** Multi-venue funding, per-level L2 depth, multi-pool lending rates and per-exchange OI are all natively one-symbol-many-values, and the desk reduces them to a scalar *at ingest* — before any operator can choose the reduction. Keeping the vector and reducing late (`vec_avg`/`vec_sum`, OP-066) is an ENGINE change, routed to improvement_inbox, not a data acquisition.

**(3) THE YIELD-BY-CATEGORY CLAIM, AND EXACTLY WHAT IT DOES NOT LICENSE.** The same repo reports submission pass rate by data type: **fundamental 40% > mixed 12.7% > pure technical 5.3% > other 0%**, with failure causes LOW_SHARPE 90.7% / LOW_FITNESS 66.2% / LOW_SUB_UNIVERSE_SHARPE 51.0%.

**This is MINED ORE — a claim from an unlicensed repo, on US equities, against THEIR in-sample submission filter. It is not evidence and it has not been verified here.** Its denominator, sample and selection are all unstated, and a pass rate against a permissive in-sample bar is not a statement about alpha existence.

**It must NOT be read as "price-only alpha is dead." L1.25 forbids that reading and the desk has already retracted that narrative once** (the 420/0 record was an instrument artifact; the kimchi screen passed and was then refuted at full depth). What it *is* legitimately: **an independent, differently-instrumented data point that yield-per-trial differs by roughly 7.5× across data classes, and that the desk is confined to the lowest-yield class.** Read that way it is a **generation prior** — it says where to spend trials, never what is true — and it converges with the desk's own measured record from a completely different direction: funding/carry, a *non-pv* axis, is the lone repeat survivor, while 129/129 price-only directional mechanisms failed at max OOS Sharpe 0.100.

**AND THE MECHANISM IS NAMED, WHICH IS THE PART WORTH HAVING.** The failure is not "price carries no information" — it is **turnover**. Fitness = `Sharpe × sqrt(|R| / max(TO, 0.125))` divides by turnover; the same source's expected-turnover table puts technical factors at **15–35%** against fundamental at **2–8%**, and describes LOW_FITNESS as "the softer version of HIGH_TURNOVER". Price-derived signals decay fastest, so they trade most, so the churn eats them. **That is the desk's own most expensive lesson in another ecosystem's handwriting** — WS-006 order-flow momentum cleared Holm at t=+3.95 and still netted −0.656 bp/bar; the carry sleeve's loss was 88.3% **fees**, not thesis.

**THE ACQUISITION IMPLICATION (L1.11, and it is the honest one):** the highest-yield categories are exactly the ones the desk cannot buy and must manufacture — on-chain fundamentals and forward-expectation series. **No purchase is proposed and none is needed**; every analogue above is public. **[§33: screened -> docs/research/search_operator_library.md `wq-brain-pipeline` + this card]** — screened, not wired: this is a reference axis (equities, un-ingestible), and its deliverable is the SHAPE it gives the crypto-side hunt, already routed.

**RESIDUAL GAP, graded:** the 4,367-field *contents* (2.8MB JSON) were **not** pulled — no desk use for equity field IDs, and bulk-copying an unlicensed artifact is not defensible under §13. The category/type counts are the whole transferable payload. **Re-entry condition (L1.16a):** if the desk ever builds a fundamentals-shaped crypto surface, the GROUP-typed field list becomes worth enumerating as a taxonomy menu.
