# Data-Axis Watchlist (Free-Data-Alternatives mission)

_Companion to `data/data_universe_map.json`. Session summaries logged here chronologically per
FREE_DATA_ALTERNATIVES_SPEC. This is the operator-visible "what did the data digger find" record._

**GRADE VOCABULARY IS MACHINE-READ (added 2026-08-19 AR s3, after 3 phantom-pending cards).**
`libs/research/source_backlog.py` classifies every `### N. … — grade: …` line and FAILS OPEN to
"pending verification" on unrecognized text. A card leaves the verify queue ONLY via: grade text
containing `verified-clean` or `destroyed-at-source`; or marker `[§33: killed …]`; or
`[§33: deferred(YYYY-MM-DD)]` with a future date. `needs-legitimacy-review` routes to the
legitimacy queue; `needs-monitoring` / `unverified` stay pending (by design — partial resolution
keeps the whole card pending). A terminal grade written as "MINED"/"BUILT"/"structural-reference"
WITHOUT one of the terminal substrings is served to every future cycle forever (F0002). Write the
substring.

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

### 1. Upbit Historical Market Data portal — grade: needs-legitimacy-review (data itself verified-clean; commercial-use licence is the open question, re-graded 2026-07-25) [§33: deferred(2026-09-15) tier:3]
> **§33 RE-DEFERRAL 2026-08-18 (free-data miner) — AND THE LAPSE IS THE HEADLINE: GAP_REGISTER #67's
> "RULE BY 2026-08-15" HAS PASSED WITH NO RULING.** Checked this run: `data/principal_replies.jsonl`
> carries no Upbit answer (latest entry is an unrelated 08-18 deadman page); row #67 is still `open`.
> This is now a principal-owed decision **one governance window overdue**. Everything an agent can do
> is DONE — licence read three independent times (07-25, 08-11, and the first-party notice), the
> question is compressed to one line ("research-only" or "full use"), and a written-clarification
> route exists (`historical_data@upbit.com`). Re-deferred to the NEXT monthly governance window
> (2026-09-15), the only honest date. **Cost of the lapse remains zero by the card's own analysis
> (static archive back to 2017, nothing decays), so this is not paged as urgent — but a second
> lapsed window on 09-15 should be, because at that point "no ruling" is functioning as a silent
> EXCLUDE that nobody decided (L1.51: an unpriced clamp).** The CM half of #67 was answered 07-26
> (recommended EXCLUDE); the Upbit half is the ONLY remaining blocker on the deepest free KR-venue
> archive known to the desk.
>
> _Prior deferral block below (unchanged, still the operative analysis):_
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

### 2. OKX official historical-data portal — grade: verified-clean [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 4. Bithumb (spot + futures) — grade: **spot VERIFIED-CLEAN-MECHANISM, DEEPEST free Korean-venue minute archive known to the desk (re-graded 2026-07-25); futures lead DEAD** [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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
>
> ⚠️ **CLOCK FENCE ADDED 2026-08-13 (KR frontier miner s3) — THE SENTENCE ABOVE IS TRUE OF THE
> SCHEMA AND FALSE OF THE SEMANTICS, AND THAT IS EXACTLY WHY IT IS DANGEROUS.** Two independent
> timezone facts, neither covered by the other, measured this session:
> **(1) THE REQUEST PARAMETER (new — OP-090; minted as OP-072 on the s3 branch, renumbered at landing).** `to=` is interpreted in **KST by Bithumb** and in
> **UTC by Upbit**. Both venues asked for `to=2024-01-15T12:00:00` return `11:59:00Z` (Upbit) and
> `02:59:00Z` (Bithumb) — **9h apart**. Adding 9h to the Bithumb request realigns them **to the
> minute** (verified 2024-01-15, 2020-03-13, 2018-01-11). The response field `candle_date_time_utc`
> is **honest UTC on both**, so the rows look perfectly normal — they are simply not the window you
> asked for. **"The desk's Upbit pagination code shape works nearly verbatim" is the precise
> statement that makes this bite:** a backfill loop reused verbatim walks a 9h-shifted window on
> *every* call and compounds it across the whole history, with no error, no gap and no anomalous
> value, passing every schema/freshness/provenance gate the desk owns.
> **(2) THE DAILY BAR BOUNDARY (already known, do not re-derive).** Upbit dailies are **UTC-days**;
> Bithumb dailies are **KST-days** (bar labelled `…T15:00:00Z`, last trade `…T14:59:5xZ` next day).
> The desk already killed this as `bithumb_kr_premium_lookahead` (docs/graveyard.md) and it is
> re-recorded here only because it is a *different* fact from (1) and fixing one leaves the other.
> **REMEDY, and it widens rather than narrows the card: 1-minute bars are honest UTC on BOTH venues
> and align exactly once the +9h request offset is applied**, so the intra-KR (Upbit−Bithumb) spread
> — the WS-011 control in which the cross-border capital-control term differences out — is cleanly
> constructible. The graveyard's framing reads as *"this venue is hazardous"*; the measurement says
> *"this ENDPOINT is hazardous and the hazard is removable"* (L1.25a: a blocked ROUTE is not a dead
> CAPABILITY). **BOUND: any intra-KR series is limited by the SHALLOWER leg — Upbit returns clean
> `[]` before ~2017-10 (re-probed this session at `to=2016-01-01` and `to=2014-06-01`), so Bithumb's
> 2014 depth buys nothing for a two-venue spread and everything for a single-venue KRW history.**
> **AND THE TAPE IS NOT CONTINUOUS:** Bithumb's 1m KRW-BTC has a **10.50h hole** on 2025-03-23/24
> (its NH→KB bank-rail migration) while Upbit ran through it — see `data/kr_venue_bank_rail.json`
> and WS-011 observation 2. Gap-check both legs before differencing; a hole reads as a spread.
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

### 5. Coincheck — grade: destroyed-at-source (for this session) [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
- **Provides / replaces:** would be the second Japanese-venue leg.
- **Provenance:** search returned no Coincheck-specific public historical archive — only generic
  cross-exchange aggregators (CoinGecko/CoinAPI/Bitquery), none of which are Coincheck-native.
- **Verify-don't-trust:** n/a — nothing found to verify.
- **Grade: destroyed-at-source for this session's search depth** (not a permanent claim — retry with
  narrower Japanese-language queries next cycle per Temporal Rediscovery).

### 6. Tardis vendor-replacement — grade: **VERIFIED-CLEAN (re-graded 2026-07-25)** — backfill claim REFUTED [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 7. Glassnode / CryptoQuant vendor-replacement — grade: **verified-clean at source level; §13 LEGITIMACY DECIDED 2026-08-25 (prospector): production adoption BARRED — Coin Metrics community terms are CC BY-NC, and a signal built on data the desk cannot use commercially is un-deployable (§13(1)), so the NC file class is not adopted; MANDATE RE-GRADE same day: the crypto on-chain metric program is retired with the universe — data/coinmetrics_flows.jsonl retained as research history only, its metric class already measured FLAT (4/4 SCREEN-WEAK banked 2026-07-26) and its sole tested consumer (cm_mvrv) graveyarded. §38 replacement hunt CLOSED WITHOUT SUCCESSOR: the exclusion removes no live capability — the consumer was removed by principal order, not the source** [§33: wired tier:1 -> data/coinmetrics_flows.jsonl]
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

### 9. Stablecoin mint/burn self-computation — grade: **verified-clean (mechanism; integer-exact on-chain reconciliation, 2026-07-25)** — but the registry's RPC chain is DEAD for logs [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 10. AWS Public Blockchain Data (registry.opendata.aws) — grade: verified-clean — **NEW SOURCE CLASS** [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 11. eth-labels (dawsbot/eth-labels) — grade: **verified-clean (verification complete 2026-07-25) — dataset DOWNGRADED to supplementary-only: systematic label corruption found** [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 12. cex-list (tradezon/cex-list) — grade: **verified-clean (content cross-checked 2026-07-25) — STALE-frozen snapshot (last commit 2023-07-27), no licence file: use as REFERENCE, not adopted dependency** [§33: killed tier:3 -> docs/graveyard.md `crypto_exchange_universe_banned_2026_08_18`]
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

### 21. NAVER DataLab (Korean search-attention) — grade: needs-legitimacy-review (account-gating: the SOLE blocker is a free NAVER Developers key = a human registration step, GAP #69; technical verification COMPLETE — endpoint live-confirmed keyless 401/errorCode 024 on 2026-07-25, 2026-07-26 and 2026-08-04; collector built+wired, zero code owed) [§33: deferred(2026-09-08) tier:3]
> **§33 FOURTH DEFERRAL + MANDATE RE-GRADE 2026-08-25 (EN frontier miner).** Blocker UNCHANGED
> (key absent; the GAP #69 operator step has now lapsed TWICE — BY 08-09 and BY 08-19 both
> passed). RE-GRADED under the MT5 universe order (2026-08-18), split per the R0637 precedent:
> the value case that priced this key — kimchi-premium companion attention + KR CRYPTO community
> grounds — is DEAD (banned universe; and no KRW/KOSPI instrument exists in the MT5 universe,
> checked desks/mt5 this run). **WHAT SURVIVES, re-stated so the principal can re-price the
> 5-minute step:** the same free key remains the ONLY §13-licensed route into Naver blogs/cafes
> (robots.txt hard-stops every other path), and those cafes host Korea's retail 해외선물
> (overseas-futures: gold, index, FX futures) communities — an MT5-NATIVE intelligence ground for
> the KR seat — plus DataLab attention series on MT5 instruments (retail gold attention:
> 금시세/금값 vs XAUUSD). Ceiling LOWER than the dead crypto case; still the only licensed door
> into that ground. If registration proves Korea-resident-gated, kill with that mechanism (the
> GAP row's own standing instruction). Re-check 2026-09-08; escalation stands via GAP #69
> (re-dated this run).
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

### 23. 中文 practitioner corpus (thuquant index / 数量技术宅 / 土法炼钢) — grade: verified-clean (MINED 2026-08-18: sljsz corpus + thuquant index; quant67.com CONTENT-REFUTED = destroyed-at-source) [§33: screened -> data/data_universe_map.json]
> _Regrade 2026-08-19 (CN miner s9), content unchanged: the 08-18 dig was complete (universe map
> 104/105/106 verified present this run) but the grade token "MINED" is outside
> `source_backlog._classify`'s vocabulary, which fail-opens the card back into every cycle's
> verification queue. "verified-clean" is the recognized terminal token for the same fact. The
> parser's fail-open default is BY DESIGN and untouched; residual WeChat/Zhihu §13 boundary work
> stays tracked in GAP #80, not here._
> **§33 CONVERTED 2026-08-18 (free-data miner, standing daily run) — the deferral date arrived and
> this seat dug it rather than rolling the date. Full record: universe map entries 104/105/106 +
> research_memory rm-20260818T151218-{d3916c,f21b8d,e38daf}. What the dig established:**
> 1. **`cnblogs.com/sljsz` (数量技术宅): ENUMERATION SECTION-EXHAUSTED** — all 9 pages, 81 posts
>    2020-09-18 → 2026-05-11, six deep-read. The card's "graveyard ore" framing was HALF right:
>    the two strategy-decay posts (2022-09 + 2024-06) are GENERIC listicles (8 textbook causes, one
>    toy example — low mechanism density; the 2022 post's only concrete data: SSE index strategy
>    1131× to 2018 then 1.3%/yr for a decade; turtle-decay reference). The real ore was elsewhere:
>    - **CN retail funding-capture template, dated 2021-05** (spot-long/perp-short, dual
>      funding+spread entry gate, ask5/bid5 conservative pricing, chase-order logic, batch
>      execution; failure modes named: unfilled legs, small-cap impact, CN-IP blocks). A dated
>      crowding-timeline datum for the desk's ONLY live family.
>    - **Dated retail-visible quarterly-basis marks:** Huobi 2021-02-15: BTC current-q 3.39%/62d
>      (~20% ann), next-q 5.68%/153d (~13.5% ann); 2024-11-30: next-q +5%/~4mo (~15% ann), 489
>      contracts/0.519 BTC worked example. Same ~15% retail carry across two bull eras, 3.75y apart.
>      Era risk named by the author himself: OTC fund freezes + USDT/CNY exposure.
>    - **OKCoin 2016 zero-fee HFT bot, mechanism-complete graveyard entry** (2021-01 post): burst
>      momentum over 5-6 candle extremes + 50/50 inventory balancing (price-neutral), golden-ratio
>      0.618/0.382 book-weighted pricing, 3-level reference (0.35/0.10/0.05), ±2% rebalance band,
>      6k→250k CNY in 7mo. **Death cause dated and named: fees introduced + margin removed + 2017
>      regulation. Re-entry condition (L1.16a): any zero-fee promo venue resurrects the class** —
>      fee-schedule watch (universe map 102) is the tripwire.
>    - **Independent decay claim on perp-premium timing:** author's own 2025-06 test (jcrate =
>      perp/spot − 1, BTC/ETH/SOL, daily+30m, 2020-2025) — single-coin REVERSED vs theory,
>      multi-coin lead **decayed post-2023**. Free out-of-sample corroboration for the desk's own
>      funding/basis-timing screens; secondary evidence, not desk-measured.
>    - **Method corroboration for L1.46:** the 2020-11 spread-calculation post independently names
>      same-timestamp ticks arriving SEQUENTIALLY, per-leg frequency mismatch (IC 2 ticks/s vs
>      500ETF 1/3s), and the merge-direction taxonomy (which leg DRIVES the spread series) —
>      routed to improvement_inbox.
> 2. **`quant67.com` is CONTENT-REFUTED as carded.** Live site 2026-08-18 = infrastructure blog
>    (Linux/eBPF/K8s/LLM, 1,756 articles, zero quant); `/post/` 403; **Wayback availability API:
>    ZERO snapshots ever** — the "crypto strategy notes" claim is unverifiable even historically.
>    The 08-11 robots-only pass verified REACHABILITY of a site whose CONTENT never matched the
>    card. Lesson logged: reachability-verified ≠ content-verified. §38 replacement: the corpus
>    need is served by sljsz (above) + FMZ 文库 (assessed 2026-08-01) + cn_oss batch; no further
>    hunt owed for a source that never demonstrably existed at this URL.
> 3. **`thuquant/awesome-quant` (MIT) index mined for its data/platform sections:** akshare, FMZ/
>    BotVS, tqsdk, pytdx, zvt all previously known/assessed. **One NEW crypto-specific find:
>    `godzilla-foundation/godzilla-community` (Apache-2.0, 370★)** — C++/Python funding-arb + MM
>    infrastructure, 121-135µs claimed tick-to-trade → universe map 106, ENGINE-idea routed to
>    improvement_inbox (mine-as-text, never installed). The index's remaining sections are A-share
>    tooling breadth, not depth ground.
> **WeChat/Zhihu §13 boundary (GAP #80) untouched, exactly as the 08-11 note required: nothing
> gated was fetched; sljsz's WeChat-only code was NOT pursued — mechanism captured from the public
> posts, code left where it is.**
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

### 24. Foreign AI-quant RESEARCH SYSTEMS (VeighNa/vnpy.alpha, Qlib, JP/KR equivalents) — grade: verified-clean + MINED (Qlib 2026-08-11; vnpy.alpha 2026-08-13; **JP/KR half MINED 2026-08-18**; grade made parser-terminal 2026-08-19 AR s3 — was phantom-pending, F0002 class) [§33: wired -> docs/research/search_operator_library.md `qlib-alpha158` + `vnpy-alpha-dsl`]
> **§33 JP/KR HALF MINED 2026-08-18 (litminer run 8) — the card's titular JP/KR equivalents were
> never previously opened; now measured.** JP HAS a real equivalent layer: **J-Quants-Tutorial**
> (JPX-official six-stage ML pipeline; 1-month purge buffers because labels embed 20d forward
> paths; "cumulative adjustment factor = unmeasurable future information" leak flag; Spearman-only
> eval) + the **competition-solution layer** (UKI000/JQuants-Forum 107★ — runner-up predictor code
> read in full: path-extreme `label_high_20/low_20` targets, guidance-vs-realized `m_*` surprise
> features, honest gap: no CV/purging in the public code). **KR has NO research-system equivalent**
> (measured negative → `negative_knowledge.md` kr-open-research-systems-layer; open KR layer is
> data-access + book code; residual idiom: krx-quant-dataloader's survivorship-free-universe-as-
> deliverable). Engine findings + transfers routed to `improvement_inbox.md` 2026-08-18 (path-
> extreme targets; surprise features CORROBORATE card 25's mint/burn remainder; contract-multiplier
> leak question named against entry 44). J-Quants DATA verdict unchanged (100-jquants-api:
> excluded-paid 2026-08-12 — this run added the METHOD layer only). Tutorial licence still
> UNREAD from the canonical file — read-before-port stands.
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

### 26. Kraken downloadable historical OHLCVT archive (2015→, all timeframes, free) — grade: verified-live + LICENCE READ DONE 2026-08-25 (ToS §8/§9: internal own-benefit use inside the grant, redistribution barred); uses re-scoped to MT5 crypto CFDs; bulk ingest owed [§33: deferred(2026-09-08) tier:3]
> **§33 RE-GRADE + LICENCE READ 2026-08-25 (EN frontier miner).** (1) **THE LICENCE READ THE 08-11
> DEFERRAL NAMED FIRST IS DONE** — kraken.com/legal/global-terms read this run. §8 "Content;
> Feedback": *"We or our licensors own (1) our services and Platforms, (2) all content, materials,
> software … So long as you comply with these Terms, you are permitted to use our services, and
> Our Content made available to you as part of our services, but only for your own benefit. We can
> take away this permission at any time."* §9 "Restrictions" bars *"web scraping, web harvesting,
> or data extraction methods"*, bots/automation against Our Content, and *"use, license,
> sublicense, sell, resell, transfer, assign, distribute or otherwise commercially exploit or make
> available to any third party Our Content"*. **VERDICT: internal desk research on the archive
> Kraken ITSELF offers for download (the support-article Google-Drive folders) sits inside the §8
> own-benefit grant — downloading an offered file is not §9 scraping; ANY redistribution or
> republication of the data or derived series is BARRED; the grant is revocable, so the lake copy
> must carry a non-redistributable label.** Grey zone named, not assumed away (row #79):
> "otherwise commercially exploit" is read as the third-party-conveyance class (ejusdem generis
> with license/sell/distribute); if the desk ever wanted to PUBLISH derived data, that needs a
> fresh read. (2) **MANDATE RE-GRADE (MT5 universe order 2026-08-18): all three declared uses are
> STRUCK** — Kaiko reference-rate depth parity, ETH/BTC rotation second venue, and
> pre-Binance-futures coverage are crypto-exchange-universe studies the desk may no longer hunt.
> **SURVIVING USE, named and checked this run:** reference tape for the MT5 desk's OWN crypto CFD
> instruments — BTCUSD_H1.parquet and ETHUSD_H1.parquet are live in the 19-symbol MT5 universe
> (broker history 2018→ only, H1-and-coarser), and 8 more Fusion-executable crypto CFDs are
> in-universe (universe.py `_CRYPTO`). Kraken OHLCVT extends exactly those symbols pre-2018 and
> below-H1 (1/5/15/30m) — "crypto reference data informing an MT5 instrument", the one form the
> mandate permits. (3) **STILL OWED:** the bulk Google-Drive pull + lake ingest needs a
> collector-capable run with disk budget — deferred(2026-09-08), scoped to MT5-universe symbols
> ONLY (a full-venue pull would be hunting the banned universe with extra steps).
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
### 27. Crypto grouping map — THE BLOCKING INPUT for group_rank/group_zscore, built proprietary — grade: **verified-clean — BUILT from owned bars 2026-08-11 (L1.11: zero vendor, zero licence surface; grade made parser-terminal 2026-08-19 AR s3 — was phantom-pending, F0002 class; consumer wiring = R0437, tracked in the ledger not here)** [§33: wired -> data/crypto_grouping_map.json]
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

### 28. CoinGecko category taxonomy (mechanism-based grouping: L1/L2/DeFi/meme/RWA) — grade: KILLED by mandate re-grade 2026-08-25 (sole consumer voided; licence still unread after two attempts) [§33: killed tier:4 -> docs/graveyard.md `coingecko_category_taxonomy`]
> **§33 KILL 2026-08-25 (EN frontier miner) — MANDATE RE-GRADE, the R0637 precedent.** The MT5
> UNIVERSE MANDATE (2026-08-18) bans the crypto-exchange cross-section; card 27's group-transform
> program over 296 perps was this taxonomy's ONLY consumer, and the ~10 Fusion-executable crypto
> CFDs that remain in-universe already carry the desk's own asset-class grouping
> (desks/mt5/mt5desk/universe.py `_CRYPTO`). The licence read stays UNREAD — api_terms 403'd again
> from this box 2026-08-25 and web.archive.org is unreachable from this fetcher — recorded as
> attempted-twice, and moot while the consumer is dead. Mechanism + narrow re-open door in the
> graveyard entry. A licence-read deferral on a dataset with no lawful consumer would have been
> the treadmill §33 exists to stop.
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

### 23. Carry↔liquidation mechanism family (BIS WP 1087, primary read) + COT-BTC extension — grade: **verified-clean — SCREENED 2026-08-18 (C1/C2 underpowered + echo-dominated, trials charged 4) + MANDATE RE-GRADE 2026-08-25 (prospector): the C3/C4 forward-liquidation remainder and its corrupt-liq-archive dependency are VOID — the crypto liquidation tape is retired with the universe (2026-08-18 mandate, recorders off), so no repair and no screen is owed. SURVIVING HALF, named: data/cot_btc_panel.json (public-domain CFTC, 1,715 rows 2017-12→2026-08) stands as a positioning-reference axis for the Fusion BTCUSD/ETHUSD CFDs — COT/TFF positioning is a named first-class MT5 axis (RESEARCH §2); any future screen is a NEW preregistration under the MT5 desk's gauntlet. CITATION FIXES: the comm_*-duplication builder defect is R0613 (this line previously mis-cited R0616 = the listing-comparables handoff row); the body's liq-parquet patch cite "R0615" is also a collision (R0615 = Appendix-A principal row) — moot, the archive is retired** [§33: screened -> data/carry_liq_screen.json]
> **§33 SCREENED 2026-08-18 (litminer run 8) — the R0193 screen remainder for THIS card is EXECUTED.**
> Novelty gate re-run (owed at screen time): novelty 0.70 vs 268 priors, nearest sim 0.30, NOT
> redundant. Pre-registered cells: **C1/C2 (carry_z63 → fwd 5d/20d BTC absolute return, 5.2y
> aligned, BitMEX signal declared)** — direct fully-forward diagnostic reads corr **−0.031 / −0.038**
> (t≈−0.6/−0.4): right SIGN for WP 1087's crash direction, indistinguishable from zero;
> **SCREEN-UNDERPOWERED at ic_min=0.03** (needs n_eff≈4,400 single-series; have 364/90). Raw IC
> +0.25/+0.31 is **100% past-return echo** (funding follows the premium; echo corr +0.29/+0.32) —
> the trap any naive carry screen falls into. NO clock, nothing refuted, nothing interesting.
> **C3/C4 (→ forward liquidation intensity): UNMEASURABLE-INPUT-CORRUPT** — `data/liquidations.parquet`
> is a truncated parquet (writer non-atomic; R0615 carries the exact patch). **M1 (mechanism check,
> not a trial): retail carry-demand (COT nonrep net/OI) co-moves with carry, Spearman +0.23 n=435w**
> — WHO-side direction consistent with the paper. **FOUND WHILE SCREENING: the COT panel's `comm_*`
> columns duplicate `noncomm_*` on 100% of CME BTC rows (R0616, builder column-map defect;
> `nonrep_*` verified independent)** — and the sweep-harness h>1 window defect (R0614, see
> `improvement_inbox.md` 2026-08-18). Powered path if ever wanted: multi-symbol carry PANEL — a NEW
> charged construction, deliberately not run this session. Tail/crash-indicator construction also
> not run (was not pre-registered). Trials charged: 4 (C1, C2, C3, C4 — blocked cells charged as
> attempted forks; zero information extracted from C3/C4).
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

### 24. Regulatory-event timeline (5-class taxonomy, Auer–Claessens) — grade: verified-clean (two regulator-native jurisdiction columns now exist; the original 151-event table remains a reconstruction reference, not an absent dataset) [§33: wired -> data/vara_regulatory_events.json + data/adgm_regulatory_events.json]
> **§33 CLOSED 2026-08-24 (BRAIN hunter s5).** The card no longer has an absent producer:
> `data/vara_regulatory_events.json` and `data/adgm_regulatory_events.json` both postdate the find,
> are non-empty machine-readable regulator-native event corpora, declare clocks/provenance, and name
> R0193 as consumer. This does **not** claim the Auer–Claessens 151-event appendix was recovered or
> that any event alpha survived; it closes the dataset-build obligation with two independently
> reconstructed jurisdiction columns. Active Fusion translation is a separate hypothesis step:
> regulatory events must map to exact traded underlyings (for example USD, gold or an equity index)
> and be evaluated through the event-shaped gate on Fusion-native point-in-time bars.
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
- **DESIGN INPUT from primary era text (2026-08-19, CN miner s9 — evidence append only, deferral
  untouched):** the 2013-12-05 289号 exemplar, read from in-window forum captures, adds TWO
  schema requirements the 5-class taxonomy does not yet carry. (1) **NAMED-SCOPE field per
  event:** 289号 named ONLY Bitcoin; the crowd spotted the LTC exemption the next morning and
  altcoin banzhuan was standard practice within 4 days (WS-014) — without a named-instrument
  field, the sibling-migration cell is unmeasurable by construction. (2) **ANNOUNCEMENT date vs
  RAIL-CUT date as separate columns:** the notice's payment-processor scope was read correctly
  within hours, but domestic rails were cut ~2 weeks later, and the offshore route (graveyard
  10th instance, era_crossvenue_fiat_premium_arb) was already operational — an event study keyed
  to announcement dates mis-times the treatment by weeks. The KR 9th instance carries the same
  lesson from the enforcement side (venue-bank rail terminations, not laws, moved the premium).

### 25. Stablecoin run signature — episodic conditioning on the EXISTING stablecoin_flows family — grade: **verified-clean — supply leg BUILT 2026-08-11, re-verified 08-12 (probes recomputed, 0 refuted) + MANDATE RE-GRADE 2026-08-25 (prospector): surviving scope = episodic run-state conditioning for the Fusion BTCUSD/ETHUSD CFDs ONLY (crypto reference data informing an MT5 instrument — the LAWS §1 carve-out); the R0193-owned remainder (treasury mint/burn pair + safe-coin premium off the desk's 4-venue tape) is VOID — the venue tape is retired (RECORDERS_OFF) and crypto-exchange constructions may not be hunted. The price leg stays declared-absent and must never read as "peg held". Nothing further owed unless an MT5 crypto-CFD sleeve preregisters an episodic-conditioning hypothesis** [§33: wired tier:2 -> data/stablecoin_run_variables.json]
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

### 26. KR venue-state layer — Upbit + Bithumb event archive, market flags and rail state — grade: KILLED by mandate re-grade 2026-08-25 (prospector; crypto-exchange-native ground banned 2026-08-18 — the cb74d2e0/R0637 precedent; collector already stopped: data/kr_venue_flags.jsonl last write 2026-08-20, flag surface stale 5d; artifacts retained on disk as provenance; the owed screen dies UNRUN — no trial charged, no forward clock ever minted) [§33: killed tier:3 -> docs/graveyard.md `kr_venue_state_layer`]
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
  (2026-08-12); the screen obligation stays HERE, one owner, now with its design.

### 27. GMO Coin free tick-trade archive (JP venue, keyless, 2018-09-05 →) — grade: **§13 DECIDED 2026-08-19: RESTRICTED-PENDING-CONSENT — Art. 14(15) consent-required reuse + Art. 7(1) deemed assent over an ambiguous 本サービス scope, and ZERO affirmative venue conduct (no GitHub org, no licensed SDKs, no grant language on the archive page — the exact opposite evidence profile from bitbank, decided the same day on the same protocol). NO INGEST without written consent; the consent request is the ledgered re-entry path.** [§33: killed -> docs/graveyard.md `jp_gmo_tick_archive_direct_ingest`]

> **§13 DECISION 2026-08-19 (EN frontier miner s-I), one paragraph — full reasoning in the
> graveyard entry:** bitbank was cleared today because its ToS has NO reuse clause AND the venue
> affirmatively solicits programmatic use (MIT clients, sample MM bots, botter community,
> official data distribution). GMO fails on BOTH axes: an explicit consent-required
> information-reuse clause (Art. 14(15), deemed assent Art. 7(1)) and no affirmative conduct
> found (org search gmo-coin/gmocoin/GMOcoin: Not Found/empty; archive page = bare symbol listing
> in the API docs, no usage language; robots 404; no API-specific terms per the 08-12 search).
> §13 demands CLEAR permitted usage; a restrictive clause plus silence resolves AGAINST ingest.
> **This is evidence-gated caution, not timidity (L1.27):** the named unlock is one support
> ticket — written consent — ledgered with an owner and a date; consent granted re-opens the card
> at verified-technically-clean. The kill protects the desk's legitimacy boundary, not its
> comfort.

> **HEADING RESTORED 2026-08-19 (EN frontier miner, session I).** An 08-13 edit destroyed this
> card's `### 27.` heading line, gluing its grade + §33 tag onto the tail of the KR venue-state
> card's paragraph above. Because `mine_conversion._ITEM_RE` matches cards ONLY on `### N.`
> heading lines, the effect was that **this card's `deferred(2026-08-19)` obligation — which
> matured TODAY — was invisible to `mine_gate`, to `source_backlog_next` (it vanished from the
> DECIDE queue), and to the vanished-item detector** (the tag TEXT survived in the file, so no
> item "vanished"; it just stopped being parseable as an item). Six days of a matured T3
> obligation outside every gate's field of view — the L1.49 shape (a gate that cannot see the
> item cannot fire) delivered by a markdown edit. Heading text restored verbatim from commit
> 5361358.
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

### 28. bitbank public candlestick API (JP venue, keyless, whole-year-per-call) — grade: **verified-clean (technically clean; §13 DECIDED LEGITIMATE 2026-08-19 on NEW venue-conduct evidence (MIT-licensed official Public-API clients + published sample market-making bots + official botter community + official historical-data distribution — kill/re-entry condition on card); phantom-history trap GUARDED in the wired artifact. Grade token normalised 2026-08-19 by JP s5: the prior wording "verified-technically-clean" plus §33 verb `wired` both miss `_classify`'s resolved vocabulary, so this terminal card was re-listing in the verify queue every cycle — the R0514/R0617 fail-open; parser fix stays engineering-owned, this is the KR-s4-precedent card-side close)** [§33: wired -> data/bitbank_1day.jsonl]
_Found by JP frontier miner session 1, 2026-08-01._

> **§33 DISPOSITION 2026-08-19 — THE §13 DECISION IS MADE: LEGITIMATE, AND THE AXIS IS WIRED IN
> THE SAME RUN (EN frontier miner, session I).**
> **THE RULING:** the site-footer 免責事項 does NOT govern `public.bitbank.cc`; keyless public
> market-data retrieval, including for this desk's commercial research, is inside the venue's
> invited use. **DECIDED ON NEW EVIDENCE, NOT BY RE-WEIGHING THE OLD** — the 08-12 seat ruled the
> scope question not-seat-decidable on ToS+footer alone; L1.16a's narrow door: a named enabling
> change addressing the original mechanism of uncertainty. The change (all fetched 2026-08-19 via
> the GitHub API `license.spdx_id` field, org `bitbankinc`):
> - **The venue licences its own Public-API clients MIT**: `python-bitbankcc` ("Public & Private
>   API を…扱うライブラリ", MIT, 66★), `node-bitbankcc` (MIT), `java-bitbankcc` (MIT),
>   `bitbank-mcp-server` (MIT). MIT expressly permits commercial use — a venue cannot coherently
>   ship commercial-use-licensed client code for an API whose data is private-use-only.
> - **The venue publishes `sample-market-making-bot` + `sample-xrp-market-making-bot`** —
>   market-making is commercial API use by definition; it is solicited, not tolerated.
> - **`bitbank-botters-labo`** — code the venue distributed at its OFFICIAL Discord botter
>   community (ビボラボ): an official botter community is an invitation.
> - **`bitbank-historical-orderbooks-docs`** — the venue OFFICIALLY runs a historical
>   order-book distribution service (→ card 34): a venue distributing its historical data is not
>   one whose footer bans data use.
> - Standing 08-12 evidence unchanged: ToS Art. 17/19/20 carry no data-reuse clause and no
>   bitFlyer-style anti-robot clause; the API host carries no terms/robots/disclaimer (robots 404
>   re-confirmed 2026-08-19); support KB 360019410033 describes programmatic retrieval as the
>   API's purpose (08-12 read; today the KB sits behind a Cloudflare JS challenge — noted, not
>   routed around, and no longer load-bearing given the org evidence).
> **THE COHERENT SCOPE of the footer** is the marketing/news site's editorial content (liability
> + anti-solicitation boilerplate); the reading that bans commercial API consumption would make
> the venue's own published MM bots a ToS breach.
> **NAMED RESIDUAL (honest):** no single explicit written grant covers the public API; the ruling
> rests on the venue's aggregate conduct. **KILL / RE-ENTRY CONDITION:** any venue communication
> (ToS amendment, API terms doc, KB update, or notice) asserting the 免責事項 or a new clause
> covers `public.bitbank.cc` data → ingest STOPS, card re-grades restricted-by-licence, artifact
> quarantined. An explicit future API-terms grant retires the residual entirely.
> **WIRED IN THE SAME RUN:** `data/bitbank_1day.jsonl` (untracked-on-disk per data/* convention;
> meta line 1 = clock provenance + guard + per-pair coverage) — **100,885 kept rows, all 62 live
> pairs (46 _jpy + 16 _btc), 2017-02-14 → 2026-08-18**, 620 keyless calls (330 served; 290
> pre-listing years refused as **HTTP 404 + `code 10000`**, re-probed 5/5 to confirm the class —
> a naive non-200=failure fetcher mis-classifies every pre-listing year, L1.60). **Guard
> applied:** per-pair leading zero-volume bars dropped — btc_jpy dropped 43 phantom bars, true
> start **2017-02-14 exactly as this card measured** (OP-045 validated end-to-end). **Two
> measured facts new to the desk:** (1) daily bars are **UTC-midnight aligned** (offset 0 ms on
> all 3,474 btc_jpy bars) — NOT JST; never assume venue-local day boundaries on cross-venue
> joins (L1.46). (2) xrp_jpy runs from 2017-05-25 with zero phantom bars — the phantom backfill
> is btc_jpy-only, i.e. a reference-index import, not a venue-wide defect.
> **FORWARD REFRESHER OWED: R0619** (engine seat — this seat is research-frozen); until wired the
> tape ages at 1 day/day, priced negligible for daily research bars (the backfill is the value).

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

### 27. Copula-state BTC-hedged alt spread reversion at 5-min (STAT-ARB — the desk's only never-tested family, n=0) — grade: needs-monitoring (screen construction owed; hourly rung of the family is graveyard-KILLED) [§33: deferred(2026-09-01) tier:2]
> **§33 RE-DEFERRED 2026-08-24 with the active-venue blocker made explicit.** The original 5-minute
> crypto construction still lacks its declared 5-minute multi-symbol panel, and the current venue
> mandate is Fusion MT5 rather than Binance. `translate_to_mt5()` returns no mapping for this
> construction. The legitimate analogue is a rolling, re-selected cointegration/residual-reversion
> study over Fusion FX/metals pairs (candidate basket: EURUSD/GBPUSD or XAUUSD/XAGUSD), but the exact
> 5-minute panel is absent for those pairs: only XAUUSD_M5 is present. Rebuilding at H1/M15 would be
> an unregistered construction substitution. Lifting condition: point-in-time Fusion M5 bars for
> both legs, executable spread/swap from the symbol contract, and a newly registered MT5-specific
> hypothesis before the audited screen. No crypto-only screen is authorized by this deferral.
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

### 28. Quarter-hour clock: scheduled-algo order-imbalance leakage, 4–12h horizon (EVENT-AND-CALENDAR × ORDER-FLOW, sub-daily) — grade: needs-monitoring (dual-use; execution-hygiene leg needs NO alpha claim) [§33: deferred(2026-09-01) tier:2]
> **§33 RE-DEFERRED 2026-08-24 for an MT5 measurement gap, not lack of a mechanism.** Running
> `translate_to_mt5("order imbalance")` maps this to broker-native bid/ask tick-change imbalance,
> with DOM only when real. The current Fusion research inventory has bars and spread metadata but no
> point-in-time bid/ask tick-change or DOM tape carrying receipt and venue clocks, so the named
> conditioner cannot be built honestly. Exact target surface after the tape exists: Fusion
> EURUSD/GBPUSD/USDJPY/XAUUSD at :00/:15/:30/:45, 4h/8h/12h forward returns, M15 decision grid;
> executable cost is each symbol's observed spread/tick value plus swap across held rollovers.
> Lifting condition: Fusion-native tick/quote tape with clock provenance and a pre-registered MT5
> trial grid. OHLCV bar direction is not substituted for order imbalance.
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

### 29. Polymarket-vs-Deribit binary wedge on BTC threshold contracts (VOL-AND-OPTIONS relative value — NOT the EV-rejected DVOL variance-carry) — grade: needs-legitimacy-review (TRADING leg only; measurement leg is free and §13-clean) [§33: deferred(2026-09-01) tier:2]
> **§33 RE-DEFERRED 2026-08-24 because the active destination has no matching instrument.**
> `translate_to_mt5()` returns no mapping for prediction-market binary contracts. The current
> Fusion universe contains spot/CFD symbols (including BTCUSD/ETHUSD) but no listed binary option or
> expiry/strike surface, so an exact hedge cannot be expressed and a crypto-only output is forbidden
> by the venue override. Named data gap: Fusion's complete option/share-CFD symbol catalogue with
> expiry, strike, exercise convention, session, spread, swap and contract specifications; absent a
> matched binary instrument this remains measurement-only external ore. Lifting condition: an exact
> Fusion-tradeable binary/option analogue plus point-in-time quotes, or a formal disposition that the
> broker offers none. The Polymarket trading-leg legitimacy gate remains untouched.
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

### 32. WorldQuant BRAIN data-field catalogue (USA TOP3000, delay=1) — a competitor's ENTIRE feature surface, enumerated — grade: **verified-clean — structural-reference, no ingest possible (equities), routed for its SHAPE not its contents (grade made parser-terminal 2026-08-19 AR s3 — was phantom-pending, F0002 class)** [§33: screened -> docs/research/search_operator_library.md]

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

### 33. VARA (Dubai) crypto regulatory-event stream — dated licence register + named unlicensed-VASP blacklist + enforcement notices — grade: **verified-clean — FULL CORPUS EXTRACTED 2026-08-19 (AR s3, deferral worked 5 days early because R0193 is due 08-24): 21 dated policy circulars 2023-02→2026-06 + 30 EN / 1 AR-only notice BODIES 2022-11→2026-07 + 37 enforcement rows + 38 unlicensed + 77-entity register w/ per-entity activities & institutional scope, all machine-readable, endpoints + clock declaration in the artifact** [§33: wired -> data/vara_regulatory_events.json]

**WHY THIS IS CARDED AT ALL, AND IT IS NOT "a regulator publishes things".** Card 24
(`Regulatory-event timeline, 5-class taxonomy, Auer–Claessens`) is graded *"event gate EXISTS; the
timeline dataset is the owed build"*, and its note records a **targeted web search for a published
Auer–Claessens event list that FAILED** — the desk needs a dated regulatory-event dataset, could not
find one, and scheduled a reconstruction (**R0193, due 2026-08-24**). This card exists **because that
build has a documented data hole**, not because a source was spotted.

**VERIFIED FIRST-HAND THIS RUN (honest UA `ClaudeBot`, s13 gate passed — `vara.ae/robots.txt` 200 and
contains ZERO non-comment directive lines, so nothing is disallowed and no agent is named):**
| artifact | URL | HTTP | verified content |
|---|---|---|---|
| public register | `/en/licenses-and-register/public-register/` | **200** | **51 licence refs** `VL/YY/MM/NNN` — the ref itself encodes **year/month** (`VL/26/08/002`, `VL/26/07/002`…), server-rendered, plus per-row issue date, licence type, activities, status |
| **unlicensed-VASP blacklist** | `/en/enforcement/unlicensed-vasps/` | **200** | **38 dated rows**, named entities, `YYYY/MM/DD`, spanning **2023/04/12 → 2025/05/15** |
| enforcement + warning notices | `/en/enforcement/`, `/en/regulations/regulatory-notices/` | **200** | dated notices, split Enforcement / Warning |
| sitemap | `/sitemap/sitemap-index.xml` → `/sitemap/sitemap-0.xml` | **200** | 311 URLs (**no `lastmod`** — so the sitemap dates nothing; the dates live in the page bodies) |

**THE ONE GENUINELY NICE PROPERTY:** every register row carries **its own issue date**, so a *single*
pull already yields a point-in-time panel on the **entry** side — no repeated capture needed to know
when each licence was granted. **Exits/revocations still require snapshots**, because a row that
disappears leaves no trace; that asymmetry is the collector's design constraint, not a nice-to-have.

**HONEST LIMITS — stated because the card is worth less than it first looks and the next reader must
not inherit my enthusiasm:**
1. **ONE JURISDICTION.** Auer–Claessens is a multi-country policy panel; VARA is Dubai. This is *a*
   column, never the table.
2. **WRONG EVENT CLASS, mostly.** The 5-class taxonomy classifies **national policy** actions (bans,
   restrictions, AML/CFT regimes). VARA's stream is dominated by **entity-level** licensing and
   small-VASP enforcement. The classes overlap only partially, and pretending otherwise would
   contaminate the panel with events of a different kind.
3. **ALMOST CERTAINLY NOT DIRECTLY TRADEABLE.** A Dubai enforcement notice against a small unlicensed
   VASP has no plausible channel to BTC/ETH on Binance. **No mechanism is claimed here**, and none
   should be inferred: this is timeline *material* for a build that already exists, not an axis.
4. **NOT A PREMIUM PLAY.** The obvious GCC-venue idea is graveyarded — `era_crossvenue_fiat_premium_arb`
   is buried 7×, the class is declared exhausted, and kimchi (its lone survivor) was killed 2026-08-01.

**DISPOSITION:** `deferred(2026-08-24)` — deliberately aligned to **R0193's own due date**, because this
is an *input* to that build and dating it separately would just create a second clock for one piece of
work. This is alignment, not a snooze: the consuming recommendation is live, dated and owned.

**2026-08-19 (AR s3) — DEFERRAL CONVERTED 5 DAYS EARLY; the corpus is now ON DISK for R0193:**
`data/vara_regulatory_events.json` (96KB) holds the FULL machine-readable corpus, pulled from the
Gatsby data layer (`/page-data/<path>/page-data.json` + `/page-data/sq/d/<hash>.json` — see the
`gatsby-page-data` operator added to the operator library this run; the SPA renders these same
payloads, nothing is routed around): **21 dated policy circulars** 2023-02-10 → 2026-06-01 (Travel
Rule 2026-02-24, CARF consultation 2025-10-10, FATF-list updates, AML decree gap-assessment, licence-
code creations — the POLICY-level rows the A–C classes actually want, which the s2 read undersold
because the circulars hide under News, not Notices), **30 EN + 1 AR-only notice bodies** 2022-11-22 →
2026-07-24 (incl. FTX MVP suspension, KuCoin + MEXC warning→fine pairs, CoinMENA + FUZE licensed-
entity fines), **37 enforcement actions** (structured entity/date/category/detail/types — no PDF
parsing needed), **38 unlicensed-VASP rows**, **77-entity register summary** (58 broker-dealer / 14
exchange / 3 VA-derivatives; **65/77 institutional-scoped** — Dubai's licensed VA market is
institutional by construction). EN↔AR circular date sets are IDENTICAL (21/21): the corpus is
bilingual-by-construction, so the AR seat's edge here was structural (endpoint knowledge), not
translation. Clock declaration inside the artifact (all dates = publisher's CMS stamps; register
`createDate` is a listed-by proxy, NOT issue date). Honest limits 1–4 above STAND unchanged.

**ALSO ENUMERATED, GRADED, AND DELIBERATELY NOT CARDED** (the desk's measured bottleneck is
verification, not cataloguing — a source earns a card by serving a named need):
- **Saudi CMA open-data API** (`opendataapi.cma.gov.sa`, OpenAPI 3.0.1, **no auth**): 2,156 private
  funds **fully dated**, 382 public funds, 230 institutions. Real and free — but **equities/funds, zero
  crypto or virtual-asset content**. No desk need it serves. *(Trap worth recording: `PublicFunds`
  advertises the same date keys as `PrivateFunds` and they are **null in 382/382** — a consumer keyed
  on "the API returns dates" passes silently and gets nothing.)*
- **`api.bitoasis.net`** — live AED trade tape (`/v1/exchange/trades/BTC-AED` **200**, real `id/type/
  price/amount/timestamp`). Collectible, but its natural mechanism is the graveyarded regional-premium
  family, so it gets **no card without a mechanism that is not already dead**.
- **ADGM** — `sitemap.xml` 200 with **1,109 dated announcement URLs carrying `lastmod`** (FSRA fines,
  fraud alerts, licence cancellations). The **second-best** artifact in the set and the natural next
  jurisdiction column if R0193 wants one; the index page is client-side-paginated and useless, the
  sitemap is the route.
- **UNMEASURED, and kept distinct from empty:** SCA/UAE CMA (pages **200**, register data behind a
  **401** API), QFMA (**200** Handlebars shells, 0 dates, and **zero** occurrences of "virtual asset"/
  "crypto"/"VASP"), `rain.bh` / `cbb.gov.bh` / `saudiexchange.sa` (**403** on every path; `saudiexchange.sa`
  apex has **no DNS record at all**), `coinmena.com` (`robots.txt` returns **200 with a Next.js error
  shell and zero directives**). None of these is "closed" and none is "empty" — they are unmeasured,
  and a status-code-only crawl would have scored several of them as open and harvested nothing.

## SESSION NOTE — 2026-08-18 (FREE-DATA-ALTERNATIVES miner, standing daily run) — WRITTEN FIRST, updated as items resolve

**§33 state at open:** 2 items owe (T2 CN practitioner corpus, due today; T3 Upbit portal, past due
08-15). Mine-gate CONVERT-FIRST honoured: both are this run's first work, highest tier first.

**ITEMS TAKEN THIS RUN (bounded per the completion contract; depth unbounded):**
1. **[A — §33 T2] 中文 practitioner corpus dig (card 23).** The deferral date is TODAY and the CN
   seat has not converted it; a dated deferral that merely rolls forward on its due date is the
   snooze §33 forbids. This seat digs it NOW: cnblogs.com/sljsz (数量技术宅) strategy-decay posts
   as graveyard ore first, quant67.com (土法炼钢) crypto notes second, thuquant/awesome-quant as
   index-for-breadth third. STATUS: **CONVERTED [§33: screened -> data/data_universe_map.json]** —
   sljsz enumeration section-exhausted (81 posts, 6 deep-read, 4 dated extractions); quant67.com
   CONTENT-REFUTED (live = infra blog, Wayback empty); thuquant mined → 1 new find (godzilla,
   Apache-2.0). 3 research_memory rows, 3 universe-map entries (104/105/106), 2 inbox routes.
2. **[B — §33 T3] Upbit portal legitimacy (card 1).** Principal-reply channel checked this run:
   NO ruling (only an unrelated deadman page 08-18 01:43Z). Row #67 rule-by 2026-08-15 has LAPSED.
   Disposition: re-defer to the next governance window WITH the lapse recorded loudly.
   STATUS: **CONVERTED [§33: deferred(2026-09-15)]** — lapse recorded on the card; a SECOND lapsed
   window on 09-15 escalates to a page, because at that point "no ruling" is a silent EXCLUDE
   nobody decided (L1.51 unpriced clamp).
3. **[C — named next-ground item 1, scoped] S3-pagination re-verification of one existing depth
   claim (Bybit bulk archive), from the 08-12 note's own top item.** STATUS: **taken if budget
   allows after A+B; otherwise named for next run.**

**Not taken, named so the chain survives:** next-ground items 2–4 from the 08-12 note (OKX bulk
depth, survivorship-polarity sweep across venues, COIN-M 285-vs-288) remain open and ranked.

### SESSION CLOSE 2026-08-18 (free-data miner) — item C result, DEPTH line, categories, next ground

**ITEM C CLOSED: Bybit bulk archive verified to item-1 depth (universe map `cex_trades_ohlcv` →
`public.bybit.com` upgraded to verified-clean).** The numbers, all first-hand this run:
- **Depth, GAPLESS:** derivatives `trading/BTCUSD/` = 2,513 daily files, **2019-10-01 → 2026-08-17
  (T+1), ZERO missing days** by full date-grid diff. `spot/BTCUSDT/` starts only **2022-11-10**.
- **Survivorship polarity: RETAINS.** 1,912 symbol dirs vs 850 live v5 instruments (paginated):
  **1,065 dirs (55.7%) are dead/expired instruments the live API no longer serves** — including
  the whole hyphenated expired-delivery-futures family (`BTC-01DEC23/`…). Live coverage 847/850;
  the 3 absentees (DDOG/ISRG/MNST tokenized-stock perps) all **launched today** — T+1 lag, not
  exclusion. Polarity matches Binance (89% retained), opposes Upbit (purges). Next-ground item 3
  is now answered for **Bybit**; remaining venues still owe the test.
- **Dead tapes serve and are immutable:** `10000NFTUSDT2022-11-01.csv.gz` → 200, last-modified
  2022-11-02. **No checksum sidecars anywhere** (unlike Binance/Upbit) — integrity = re-download.
- **Schema fragility, now MEASURED not asserted, three inconsistencies in ONE bucket:** trailing
  slash in `trading/` hrefs but not `spot/`; filename separator differs by family
  (`BTCUSD2019-10-01` vs `BTCUSDT_2022-11-10`); a `[A-Z0-9]+` symbol regex silently drops 751
  hyphenated dirs. **Two instrument errors were caught mid-run by switching instruments:** a
  page-capped summarising fetcher reported the tape ending 2024-09-19 (it ends yesterday), and
  the first regex under-counted 1,161 vs 1,912. Enumerate archives with `curl` + raw counts, never
  through a summariser.

**CATEGORIES COVERED THIS RUN (honest):** cat 1 exchange-native (Bybit verified; Upbit ruling
re-dated), cat 3 non-English (CN corpus dug), cat 4 community lakes (thuquant index; godzilla
repo), cat 5-adjacent (retail positioning intelligence from the CN carry posts), cat 6
vendor-replacement (godzilla connectors as endpoint enumerator — routed). **Cat 2 on-chain: NOT
touched this run** — named, not hidden; it stays on the board. Search-space expansion (≥25%):
the CN corpus + godzilla + the production-infra-connector-repos-as-endpoint-catalogues class are
this run's expansion ground.

**DEPTH LINE (mandate):** sljsz corpus — archive ENUMERATED to exhaustion (9/9 pages), 6 posts
deep-read, comment layers checked (zero comments exist on sampled posts — the depth the mandate
asks for is structurally absent on this blog); thuquant — index mined, one fork-out (godzilla)
followed to repo+licence depth; quant67 — surface + /post/ + Wayback = refuted; Bybit — full
listing enumeration + live-API diff + dead-file servability probe. No reply-chains ≥2 existed to
mine on any ground touched this run (cnblogs comments empty, GitHub README-level) — stated rather
than performed as theater.

**NO NEW EV-GATE PRE-REGISTRATION OWED:** nothing surfaced today is a new tradable axis with an
economic story (Bybit was already catalogued — this run VERIFIED it; the CN finds are crowding/
graveyard/method intelligence, routed to research_memory + inbox, not axes).

## NEXT UN-EXHAUSTED GROUND (2026-08-18 — supersedes the 08-12 list)

1. **OKX bulk archive to item-1 depth** (mode-3 soft-empty index: date-grid construction + probe;
   depth + survivorship + checksum discipline). The Bybit half of the old item 2 is DONE.
2. **Archive-vs-API survivorship polarity, remaining venues** (Kraken CSV dumps, OKX, bitFlyer/
   GMO, Gate, KuCoin) — Bybit now answered (RETAINS).
3. **COIN-M `metrics` 285-vs-288 row question** — unchanged from 08-12, still cheap.
4. **Re-list remaining S3-derived depth claims with pagination** — Binance done 08-12, Bybit done
   today; sweep the rest of the file's S3-mode claims.
5. **sljsz deep-read tail** — ~74 enumerated posts un-deep-read; mechanism-dense titles first
   (低风险稳健策略：BTC套利 2022-08; 数字货币合约做市 2021-06; 稳定币网格做市 2021-07/2023-01).
6. **FMZ 文库 strategy-square dig** (assessed RICH-ish 08-01, never dug) — the sljsz HFT post's
   bot lives on FMZ; the public strategy layer is the natural next CN ground.
7. **Cat 2 on-chain reconstruction** — untouched two runs; owes a session.

---

### 34. bitbank official historical ORDER-BOOK snapshots (S3, registration-granted) — grade: **verified-documented, NOT SCREENABLE TODAY: access is a venue-granted registration (named human step, GAP #69 class) — mechanism prior stated, screen owed on access grant** [§33: deferred(2026-09-02) tier:2]
_Discovered by EN frontier miner session I, 2026-08-19, while gathering §13 evidence for card 28
(the org listing surfaced `bitbankinc/bitbank-historical-orderbooks-docs`). SOURCE:
`github.com/bitbankinc/bitbank-historical-orderbooks-docs` README.md (read in full via
raw.githubusercontent this run). DERIVES-FROM: NONE (checked — it is the venue's own primary
documentation, citing only AWS setup guides)._

- **What it is.** The venue OFFICIALLY distributes L2 order-book snapshots from its production
  exchange: **200 levels above and 200 below best bid/ask, ~2 snapshots/minute**, CSV in
  `.csv.gz` daily objects, updated T+2 (~23:00 JST), via S3 bucket
  `564226375708-historical-order-books`, path `orderbook-snapshot/${TICKER}JPY/YYYY_MM/`.
- **Coverage (from the venue's own table):** BTC + XRP **2019-03-13 →** (≈7.4y of JP-venue L2
  depth); ETH/DOGE/XLM/ADA/LTC/LINK/AVAX **2023-07-24 →**; SOL **2024-11-21 →**. JPY-quoted.
- **§13:** the CLEANEST form available — access is not scraped but **GRANTED BY THE VENUE** after
  AWS-account-ID or IP registration ("After registration, the Company will grant you access").
  Public repo documents it; no licence file in the repo (the grant itself is the permission
  surface; read any terms presented at registration and record them on this card).
- **Why it matters (mechanism prior, stated before any screen):** the desk's own-book L2
  archives start far later; a **7.4-year JP retail-venue depth tape** spans the 2019 pre-halving
  regime, COVID, the 2021 cycle and the 2022 deleveraging. Priors it can serve without any alpha
  claim: (a) book-imbalance/depth-slope features at a venue the desk never recorded; (b)
  cross-venue liquidity-migration studies (JP retail vs global) with era-archaeology value; (c)
  execution-reality calibration for any future JP-venue routing. ~2/min sampling bounds it to
  slow features — it cannot serve sub-minute microstructure, and that limit is stated now, not
  discovered later.
- **NOT SCREENABLE TODAY, and why that is not a §33 dodge:** ingest requires the registration
  grant — a human/ops step this research-frozen seat cannot execute. Same pattern as NAVER card
  21. **Routed: R0620** (registration decision + execution, principal/ops). §33 deferral dated
  to R0620's resolve-by window; on grant, screen-on-discovery applies to the FIRST pulled month
  in the same run that pulls it.
- **Discovery counterfactual (charter s17):** found only because the card-28 legitimacy hunt read
  the venue's whole GitHub org instead of stopping at the two repos already cited — the marginal
  cost of listing an org is one API call; the habit generalises (see operator note this session).

### 35. KR venue↔bank fiat-rail registry — the venue-ASYMMETRIC barrier regressor (R0299's missing input) — grade: **verified-clean — ENUMERATED 2026-08-19 (KR s4): ~0.9 sharp episodes/yr measured vs ≥8/yr needed → event-study alpha use KILLED (graveyard `kr_bank_rail_event_study`); registry KEPT as tape-provenance layer (WS-011 gate); grade made parser-terminal same-day 2026-08-19 by AR s3 (F0002 prevention — verdict untouched)** [§33: screened -> data/kr_bank_rail_transitions.json] _(minted as "card #33" on the unmerged KR-s3 branch 2026-08-13; renumbered at landing 2026-08-19 — live #33=VARA, #34=bitbank had taken the number)_
- **Provides:** a per-venue, per-date KRW fiat-rail state for the licensed Korean venues. Korean
  regulation binds each VASP to **exactly one** partner bank for KRW deposit/withdrawal (2018
  real-name system, still in force 2026), so this is not a market variable — it is a **regulatory
  exclusivity** that makes every bank-level event a shock to ONE venue and not its competitor.
- **Why the desk wants it, specifically.** R0299 needs a barrier-height regressor **independent of
  the premium it explains**, because the KR-premium construction is circular and was retracted at
  ~73% timestamp artifact. KR-s2 showed the **intra-KR (Upbit−Bithumb) spread differences out the
  cross-border capital control** — both legs sit behind the same control — so the residual is
  venue-specific, and the fiat rail is the largest venue-specific state variable available. It is
  also **structurally unbuyable**: no vendor sells "which bank is contracted to which Korean
  exchange this quarter", and it is not derivable from price.
- **Current mapping (2026):** Upbit→K-Bank (contract expires **Oct-2026**), Bithumb→KB Kookmin
  (**migrated from NH 2025-03-24**), Coinone→Kakao, Korbit→Shinhan, Gopax→Jeonbuk.
  **2018 era mapping** (primary, Ppomppu): Upbit→IBK, Bithumb→NH중앙회 only (지역농협 rejected as
  2금융권), Bithumb→Shinhan **announced but never delivered**.
- **MEASURED instance, not asserted:** Bithumb's 1m KRW-BTC tape has a **10.50h hole** across its
  2025-03-24 bank migration (last bar 2025-03-23T15:30Z, next 2025-03-24T02:00Z, +51bp across the
  halt) while Upbit ran continuous. **The rail event is observable in market data as an absence** —
  which is also the WS-011 confounder in its sharpest form (the halting venue *is* the treated one,
  so tape liveness correlates with treatment).
- **Free path / cost:** free. Venue notice archives — the desk already collects
  `data/upbit_trade_announcements.jsonl` (737 rows, 2017-10-27→) and Bithumb's `feed.bithumb.com`
  notice feed is catalogued on card #4. Regulatory/press record for contract signings and renewals.
  No paid tier required, no licence obstacle identified (§13: public corporate announcements).
- **THE BLOCKING MEASUREMENT, and it decides the axis:** nobody has counted the treatment. The EV
  gate run this session lands at **0.0019 vs a 0.002 threshold on breadth 6/yr — REJECT — and flips
  to QUEUE at breadth 8.** So the deciding quantity is the transition count, and it has never been
  enumerated. **Enumerate first; do not screen n=1** (L1.62: never certify a verdict on a sample
  size nobody measured).
  **→ ENUMERATED 2026-08-19 (KR s4, `data/kr_bank_rail_transitions.json`): ~0.9 sharp
  episodes/yr (8 in 8.6y; ONE since 2021-09), ~2.2/yr counting every weak row. EV re-run:
  0.0004–0.0006, REJECT with no knife-edge left. The 6/yr hand estimate was 6× the measurement
  because it lacked class boundaries (renewal noise + VASP crypto-leg suspensions counted as
  treatments). Event-study use graveyarded; the registry's provenance role stands. Re-open only
  on the one-bank-rule repeal transition (named enabling change).**
- **METHOD FENCE for that enumeration (paid for by the comment layer, 2026-08-13):** the
  **announcement date is NOT the treatment date.** Ppomppu 76535's "7 venues cut off" headline was
  **disputed by two of the named venues within 44 minutes** (76551), and a commenter notes the cut
  venues *"어차피 현금 입금 안되던 곳"* — the rail had already died quietly. Keying an event study on
  announcement timestamps would mis-date its own treatment and, worse, would inherit press errors
  as events.
- **Honest limits.** (a) Current mapping is **reported, not venue-confirmed** — only the 2025-03-24
  migration is corroborated by desk measurement. (b) **NAMED KILL CONDITION:** Woori Bank's CEO is
  publicly lobbying to repeal the one-bank rule; repeal ends the asymmetry the axis rests on, so
  this axis has an expiry rather than assumed persistence. (c) The desk holds **no KRW rail**, so
  the KR leg is untradeable directly — any transmission is via the global leg, as on card
  `kr_rail_state_transition_global_leg` (which is the **crypto** per-coin rail; this card is the
  **fiat** per-venue rail — adjacent layers, different mechanisms, novelty 0.899 against it).

### 36. ADGM/FSRA (Abu Dhabi) dated announcement corpus + FSRA register pages — grade: **verified-clean — MINED 2026-08-19 (AR s3): 230 crypto/enforcement-tagged events dated FROM PAGE META 2016-05-10 → 2026-08-11, attrition 230/230 fetched 0 failed; clock calibration measured (sitemap lastmod is migration-flattened, 728/1111 stamps bulk-2024; `article:published_time` SURVIVES migration and is day-first, validated 128 day>12 / 0 month>12); 881 untagged rows kept as index; `/public-registers/fsra` 3,848 pages named UNMINED** [§33: wired -> data/adgm_regulatory_events.json]

**WHY CARDED:** the second jurisdiction column for **R0193** (regulatory-event timeline, due
2026-08-24) — sibling column to card 33 (VARA/Dubai, wired same run). s2 enumerated this ground
2026-08-13 and deliberately did not card it; it earns the card today by producing the artifact.

**§13, RESOLVED THIS RUN (was UNMEASURED under OP-076 since s2):** apex `adgm.com` 403s
`/robots.txt` itself (Akamai edge) — but `www.adgm.com/robots.txt` is **GET 200 text/plain**:
`User-agent: * / Allow: /` with Disallow on `/episerver /util /mediacentre/ /media-center/
/doing-business/ /adgm-academy/ /api/`. The corpus lives at `/media/announcements/` and
`/public-registers/` — **not covered by any Disallow** — and the sitemap is advertised in robots
itself. Disallowed paths were not fetched. (Grade robots from **www + GET**, never apex or HEAD —
same host-pair split OP-076 documented on bitoasis, now on a second GCC host.)

**HEADLINE POLICY-CLASS ROWS (A–C-classifiable, from the artifact):** Binance **global licence
under ADGM framework 2025-12-08** (the desk's own venue, dated); staking framework finalised
2026-04-29 (proposed 2025-10-01 — a dated proposal→final pair); fiat-referenced-token/stablecoin
framework finalised 2025-11-03 (proposed 2025-09-09); digital-asset framework amendments
2026-06-10→2025-06-10; crypto-mining discussion paper 2026-01-28; broker classification framework
2026-07-31; TON DLT Foundation base 2025-02-12; Coinbase tokenization hub 2026-08-13. Enforcement
layer is mostly fraud-website alerts + small fines (e.g. USD 5,000 Elmar Capital) — entity-level,
kept tag-separated exactly as on card 33.

**HONEST LIMITS:** (1) one jurisdiction — a column, never the table; (2) the corpus is a
REGULATOR'S PRESS FEED: licence-grant PR and alerts dominate; the policy-class subset is the
value and it is a minority of rows; (3) slug-keyword tagging is precision-biased and
recall-UNMEASURED — the 881 untagged rows may hide relevant events (they are kept in the artifact
so R0193's build can re-tag from titles at zero fetch cost); (4) no mechanism is claimed — this is
timeline material for an existing ledgered build, not an axis; the regional-premium family stays
graveyarded.

### 37. Wallet-resolved signed DEX trade tape (OWNED, frozen 2026-08-20, and absent from every catalogue the miners read) — grade: KILLED by mandate re-grade 2026-08-25 (prospector): the mining program this card demanded is banned ground (DEX-native cross-section); the collector stopped in the 08-20 retirement wave (data/geckoterminal_trades.jsonl frozen at 197MB, 2026-08-11→08-20), so the custodial-urgency argument — forward-only-unrecoverable accrual — is moot. Tape stays owned on disk as provenance. UNIVERSE-INDEPENDENT HALVES stay live in R0637 (open; split prescribed by brain-s5 2026-08-20, owner = brain seat): (a) utilisation-meter blindness to registered-but-uncatalogued collectors; (b) the vec_*/reduce_* vector-operator gap (0 of 18 implemented) — the identical data shape exists on the MT5 desk's own per-tick tape, which is where that capability belongs now [§33: killed tier:3 -> docs/graveyard.md `dex_wallet_tape_mining`]

**THIS IS NOT A SOURCE TO ACQUIRE. THE DESK ALREADY OWNS IT AND HAS NEVER READ IT.**
`scripts/collect_geckoterminal_trades.py` has been writing `data/geckoterminal_trades.jsonl` since
2026-08-12 (R0291). The reason nobody mined it is partly that **nobody could see it**: it appears in
neither `data/data_universe_map.json` nor this watchlist — the two catalogues the miners and the §33
generation priors actually read. A collector registered in governance but absent from the map is
invisible to exactly the organs whose job is to mine it. **Carding it here is the visibility half of
the fix**; the reader half is R0637.

**MEASURED FIRST-HAND 2026-08-19 by parsing the file (not from the collector's claims):**
- **322,187 rows, 0 malformed.** Venue-clock span **2026-08-11T01:53Z → 2026-08-19T07:45Z** (live
  today; ~8 days deep and accruing).
- **68 distinct pools**; networks solana 249,338 / eth 72,849.
- **93,241 distinct wallets** (`tx_from`).
- Signed: buy 169,555 / sell 152,632 (52.6% buy).
- `volume_usd`: median **$18.82**, mean **$1,336.47** (mean/median ≈ **71×**), max $2,702,801.
- **187 pool-day cells, 181 of them with n ≥ 30 trades**; median cell n = **804**, max 7,245.

**WHY IT IS A VECTOR FIELD AND WHAT THAT UNLOCKS (see OP-093).** Each pool-day is a *vector* of
individual signed trades — the exact data shape WorldQuant BRAIN's 18 `vec_*`/`reduce_*` operators
exist for, and the desk implements **0 of those 18**. Demonstrated non-degenerate on the richest
cell (n=7,245): trade-size **skew = 11.19**, p90/p50 = **17.6×**. *A daily volume total cannot
contain that number* — the size distribution is precisely the information the scalar collapse
destroys. Candidate reductions, all computable today with zero new collection:
`reduce_skewness/kurtosis(volume_usd)` (whale-vs-retail mix), `reduce_count(volume_usd, k)`
(large-trade count), `reduce_percentage(·, 0.5)` (median trade size), signed variants keyed on
`kind` (buy/sell pressure asymmetry), and — with **no equity analogue whatsoever** —
`tx_from`-based unique-wallet count, repeat-wallet concentration and new-vs-returning wallet mix.

**CLOCK PROVENANCE IS ALREADY CORRECT (L1.46):** every row carries `t_venue` (chain stamp) beside
`t` with `"c":"recv"` — dual clocks declared at the row level. This tape is *not* part of the 82%
undeclared-clock corpus.

**WHAT THIS CARD DOES NOT CLAIM.** 8 days and 181 usable pool-day cells is a **short, narrow panel**.
Under L1.62 the cross-sectional denominator here is unmeasured, so **no screen may call itself
powered on it and nothing here is a candidate.** This is an axis to mine *as it accrues*, not an
edge. The urgency is not statistical, it is custodial: the collector's own registration records
venue retention at **~300 trades/pool**, so capture is **forward-only-unrecoverable** — every day
this sits unread is a day of an irreplaceable series that is mined by nobody and cannot be re-earned
(L1.28a; §33 "unmined proprietary data is edge already paid for and declined").

**CROSS-REFS:** R0637 (write-only tape + invisible to `moat_utilisation`, whose inventory globs only
`data/moat/<venue>/<SYMBOL>/*.jsonl.gz` and therefore counts this file in neither numerator nor
denominator); OP-093 (the reduce/vector shape); R0291 (the collector's origin).

### 38. CN gold layer — SGE Au99.99/Au(T+D) premium vs XAUUSD + 递延费 (deferred-fee) direction — grade: **verified-clean 2026-08-26 (independent diff, free-data dig): endpoint keyless POST 2016-12→T-1, premium vs desk XAUUSD n=633 mean +36bps sd 78 AR1 0.907; fee direction closed via the Au(T+D)−Au99.99 basis. WIRED: quant-sge-premium.timer 07:45 UTC (R0649) — but its XAUUSD leg reads the wrong bar, see R0660** [§33: wired tier:2 -> desks/mt5/data/lake/sge_daily.parquet]

**MT5-MANDATE NATIVE: this is an XAUUSD/XAGUSD conditioning layer, not a crypto axis.** First CN
dig under the 2026-08-18 universe order. The MT5 desk already believed in this axis enough to build
`desks/mt5/research/fetch_sge_premium.py` — which has ZERO callers, zero output artifacts, and a
sole configured source its own parser cannot parse (III.16 built-never-run; repair = R0649).
**WIRED 2026-08-26 (this repo, same-day):** `_parse_graph` rebuilt against the live payload shape
(`times`/`data`/`heyue`/`delaystr`; fixture test `desks/mt5/tests/test_sge_premium.py`); both
contracts pulled per run (`?instid=Au99.99` and `Au(T+D)` — the endpoint's silent fallback to
Au99.99 on unknown instid is refused by the `heyue` check); history self-records forward into
`desks/mt5/data/lake/sge_daily.parquet` (upsert by Beijing session date from `delaystr`, so cadence
cannot duplicate); premium legs: desk Fusion XAUUSD 07:00Z H1 close (FRED's LBMA series is 404 —
withdrawn) + ECB same-snapshot USDCNY cross (FRED DEXCHUS fallback); scheduled by
`quant-sge-premium.timer` daily 07:45 UTC (15:45 Beijing, just after day-session close).
`agtd_basis_cny_g` (Au(T+D) − Au99.99) is recorded per day — the market-priced read on the 递延费
pressure side; the *published* fee-direction notice remains a separate, still-unwired leg (named
below).

**MECHANISM (two-sided, regime-labelled — primary CN sources, read this run):**
- China is the largest physical consumer; imports need a per-shipment PBoC permit
  (《中国人民银行黄金及黄金制品进出口准许证》), so the SGE↔London arb is QUOTA-GATED and the
  premium does not self-equalise. Structural cost floor ≈ few $/oz (freight/insurance/customs/vault).
- **Premium (+) regime = quota binding.** PBoC tightens quotas precisely when CNY depreciates fast
  (gold-as-capital-flight channel), so premium spikes carry USDCNH-pressure information, not just
  jewellery demand. Sept-2023 episode (Tianfeng macro, primary): premium ≈ **5%**, SGE briefly
  >470 CNY/g, gold-implied CNY rate 7.6–7.7 vs 7.3 actual; July-2023 HK→mainland imports −26% m/m
  (quota evidence); H1-2023 consumption 554.9t vs domestic production 178.6t (3.1× import
  dependence). Their falsifier: premium persists until FX expectations stabilise; quota relaxation
  is the narrowing mechanism.
- **Discount (−) regime = demand weak / quota slack** (2020 COVID; and LIVE NOW: cngold 2026-07-01
  reports 贴水 8.07 CNY/g with the deferred fee negative). End-to-end unit sanity this run: SGE
  intraday last 990.08 CNY/g → $4,564/oz (via DEXCHUS 6.7474) vs desk XAUUSD H1 $4,643 ≈ −1.7%,
  consistent sign. Historical base rates (CN financial-media layer): premium positive 81% of
  2002-10→2019-12; long-run mean ≈ +$6/oz.
- **递延费/延期补偿费 (deferred compensation fee) = the funding-carry-family observable on SGE
  gold.** Direction set DAILY by physical delivery-declaration imbalance (交收申报 15:00–15:30
  CST; 中立仓 15:31–15:40; the side with FEWER declarations pays the side with more), official
  spec fetched this run: **1.75bp of contract value per NATURAL day** (≈6.4%/yr one-sided).
  Direction knowable ~**07:40 UTC** daily → clean Asia-close → London/NY forward alignment for
  XAUUSD. The desk's only repeat-survivor family (funding/carry) in MT5-universe form. SIGN
  SEMANTICS UNRESOLVED (weak signal): cngold reads 空付多 as bearish futures sentiment; the
  mechanical rule implies take-delivery demand > make-delivery supply. Resolving needs the
  declaration QUANTITIES, not just direction (the desk's own R0021 lesson: read the underlying
  imbalance, not the quantized fee). CROWDING MARKER: CN retail media is running "躺着赚钱"
  carry articles on the fee (2026-07) — the carry is advertised, price accordingly.

**ROUTES (all keyless, probed 2026-08-25):**
- HISTORY: Eastmoney `push2his.eastmoney.com/api/qt/stock/kline/get?secid=118.<CODE>&klt=101` —
  `118.AU9999` 5,511 daily rows from **2004-01-02**; `118.AUTD` 3,456 from **2012-06-05**; CNY/g.
  `118.AGTD` (silver leg → XAGUSD premium) claimed by analogy, **UNVERIFIED** (throttle hit first).
  RATE-LIMIT SEMANTICS: burst → TLS drop (curl SSL EOF / urllib RemoteDisconnected), NOT 429; IP
  cooldown ≥30min observed. Bulk recipe: window `beg`/`end` in year-chunks, 20–30s gaps, or pull
  from the VPS box. klt=102/103 (weekly/monthly) untested.
- LIVE INTRADAY: `sge.com.cn/graph/quotations` HTTP 200 from this box — Au99.99 current-session
  minute tape `{times:[782],data:[floats],heyue:"Au99.99"}`, night session 19:50→02:30 books to
  next day (payload starts 20:00). This is the payload the existing collector cannot parse (R0649).
- FEE DIRECTION: **CLOSED 2026-08-26 (free-data dig)** — notices route unreachable, but the fee's
  price footprint is the Au(T+D)−Au99.99 basis from the SAME endpoint (mean −3.2bps, sd 7.6bps,
  one extra POST). Original notices feed downgraded to residual/needs-monitoring (§38 hunt logged).
- FX LEG: FRED DEXCHUS is **~2.5wk stale** (last 08-07 on 08-25) — fine for history, names the
  freshness cap; USDCNH absent from the 19-symbol MT5 universe (R0649 names the option).
**CLOCKS (L1.46):** SGE venue-local CST trading-day labels; day close 15:30 CST = 07:30 UTC;
declarations→fee direction ~07:40 UTC; XAUUSD 24h; DEXCHUS NY-noon rate lagged weeks. Any premium
series mixes three clocks — declare per-leg at screen time; predicting post-07:40-UTC XAUUSD from
same-day SGE close is the leak-free construction.
**§13:** public quote APIs serving the venues' own public pages, keyless, no licence text
encountered barring research use (own-benefit posture, same grade as Kraken card 26); SGE spec page
public. Zhihu practitioner layer WALLED ×2 (question 403, zhuanlan 403) — recorded, not routed
around.
**DERIVES-FROM:** Tianfeng Securities macro note 2023-09 (林彦), sina mirror (original CN
sell-side analysis); cfbond/中国财富网 explainer 2021 (CN financial media; the zhuanlan copy is the
SAME article — one source, not two); cngold.org 2026-07-01 fee article; SGE official contract spec
+ quotations endpoint (primary). The premium PHENOMENON is internationally known (Reuters quotes
SGE premia weekly) — what is CN-native here is the quota-FX mechanism quantification, the
declaration microstructure, and the fee-direction lore. NOT an independent-convergence claim.
**FALSIFIERS / KILL PATHS:** (a) premium is quota-policy-driven → regime breaks on import
liberalisation (named enabling change for re-open); (b) if premium extremes carry no XAUUSD
forward information at any mechanism-appropriate horizon (screen through the MT5 desk's own
gauntlet — this card grants ZERO promotion authority); (c) fee-direction signal dies if
declaration imbalance is dominated by warehouse logistics rather than positioning (test needs
declaration quantities); (d) 2013-era premium spikes coincide with the 中国大妈 retail-mania
window — any backtest must separate demand-shock from quota-shock episodes or it conflates two
mechanisms.
**NEXT:** bulk pull on cooldown expiry → `data/sge_daily_klines.jsonl` (script staged this run at
/tmp/sge_fetch.py, windowing owed); AGTD verification; fee-direction notice route mapping; then
hand to the MT5 desk's screen via R0649.

---

## PRINCIPAL SEED DROP — 2026-08-25 (daily research cycles: hunt these grounds and more)

Seeds, NEVER boundaries (anti-hardcode law, LAWS §1): each is an entry point whose graph the
diggers expand — repos lead to maintainers, forums to authors, statements to calendars. Every
find flows through the unchanged §13 legitimacy gate, screen-on-discovery, and §33 dispositions.
YouTube transcripts are EXCLUDED for now: transcript retrieval measured unreachable from this
box (principal 2026-08-25) — re-probe quarterly like any walled source, do not burn daily budget.

### 41. [seed S1] MQL5 full surface — grade: **verified-clean 2026-08-26 (prospector; live probe + robots read in full + 1,715-row harvest on disk). NOT walled — the desk's own collector was broken (R0660)** [§33: screened -> data/intelligence/mql5_prospector/]
- **§13:** robots.txt read in full today. ALLOWED for `*`: `/en/code/*`, `/en/code/mt5/<section>/pageN`,
  `/en/signals/mt5/list/pageN`, `/en/articles`, forum threads. DISALLOWED and untouched:
  `/*/code/viewcode/*`, `/*/code/download/*/`, `/*/signals/*/deals|positions|pending-orders/page*`,
  `/*/signals/*/reviews`, `/*/search*`, `/data*`. **Mechanism TEXT yes; source download and
  per-trade history NO.**
- **Measured:** `/en/code/mt5/{experts,indicators,libraries,scripts}` -> 1,715 free open-source
  entries harvested (600/600/395/120), each with id + title + full mechanism description + rating;
  40 tiles/page in `div.code-tile`. Artifact: `data/intelligence/mql5_prospector/codebase_catalog_20260826.json`.
- **First-pass mechanism tagging (n=1,715):** trend/momentum 397 · mean-reversion 230 ·
  options/vol 60 · grid-martingale 58 · session/time-of-day 47 · vol-regime 34 · ML/AI 30 ·
  news/calendar 28 · carry-swap 20 · order-flow 20 · pairs/cointegration 14 · arbitrage/latency 10 ·
  seasonality 3 · **unmatched 986**. The distribution is the finding: this ground is
  overwhelmingly desk-dead families, and its thin tails (carry, session, pairs) are ground the
  desk already holds. **Yield as an ALPHA source: LOW and now measured, not assumed.**
- **Rate limit (operator-library entry):** ~50-60 sequential list pages at 1.5s then HTTP 403 for
  the IP, persisting on a bare probe minutes later. A production collector must pace >=5s or
  rotate sections across days, and must treat 403 as BACK-OFF, never as an empty result.
- **Residual UNMINED:** forum reply layer (thread bodies, >=2 levels — the collector is title-only),
  `/en/articles` (never once parsed), and per-signal detail roots.

Codebase (public .mq4/.mq5), Articles, **Signals** (verified track records — RESEARCH §4
black-box reverse-engineering ground), Forum reply layers, Market teardowns/reviews (refutation
genre). The MT5 universe's NATIVE ecosystem; currently the thinnest-covered major source
(1 doc mentions it vs 8+ for TradingView/CN grounds).

### 42. [seed S2] GitHub code repos, systematic (not incidental) — grade: **route verified-live 2026-08-26 (unified frontier dig; keyless probe)** [§33: deferred(2026-09-05) tier:3]
- **Measured 2026-08-26:** `api.github.com/search/repositories?q=topic:mql5` returns HTTP 200
  keyless, `total_count=646`. Route confirmed; the unauthenticated search rate limit (10 req/min)
  is the pacing constraint a collector must respect, and a 403 there is BACK-OFF, never an empty
  result (the MQL5 rate-limit precedent, card 41). Corpus build itself is still owed.
Beyond ad-hoc searches: topic/language sweeps for MT5/MQL/FX strategy repos, fork graphs of
high-star strategy repos, Issues/Discussions of broker-API wrappers, dead-repo archaeology
(L1.11a). GitHub maximalism is already law; this seed makes the DAILY cycle own it.

### 43. [seed S3] TradingView public scripts — grade: **KILLED 2026-08-27 — duplicate of seed S12 (card 52), which this run closed on §13: the robots `ClaudeBot` group bars /scripts/* and /script/*. Recorded as ONE kill, not two** [§33: killed tier:3 -> docs/graveyard.md `tradingview_pine_agentic_mining`]
- **Merged, not double-counted:** S3 and S12 are the same ground described twice (S12's own text
  concedes S3 is "already covered in 8 docs — the seed here is the DAILY cadence, not novelty").
  S12 carries the live deferral and owns the work; this card is a pointer, so that the pair is one
  item in the backlog rather than two (RESEARCH: convergence is recorded, never counted twice).
Pine Script public library: strategy scripts with visible logic + boosts/comments as a crowding
signal. Already covered in 8 docs — the seed here is the DAILY cadence, not novelty.

### 44. [seed S4] QuantConnect — grade: **route verified-live + §13 BOUNDARY READ 2026-08-26** [§33: deferred(2026-09-05) tier:3]
- **robots.txt read 2026-08-26 (HTTP 200, 851b):** `Disallow: /api`, `/api/*`, `/index.php`,
  `/processSignUp`. **The API is barred to crawlers; the public algorithm/forum pages are not.**
  Any collector built here reads pages and must never touch `/api` — the same shape as MQL5's
  "mechanism TEXT yes, source download NO" boundary. Duplicate of S15, which owns the corpus work.
Public algorithms, forum, Alpha league results. Mechanism extraction + the failure genre
(live-vs-backtest divergence threads are free execution-reality data).

### 45. [seed S5] Trump Truth Social — grade: needs-legitimacy-review (NOT probed 2026-08-26 — deliberately deferred, reason named) [§33: deferred(2026-09-12) tier:3]
- **Not worked today and the skip is a decision, not an omission:** the §13 question (platform ToS
  on automated reuse) is the binding constraint, and it is a READ, not a probe — running the probe
  first would generate corpus the desk may not be permitted to keep. The legitimacy read is the
  whole of the next unit of work here.
- **Ranked BELOW S6/S21 on mechanism, not on effort:** a policy statement from a central bank is a
  scheduled, dated, market-moving event with a forced counterparty; a social post is an
  unscheduled headline whose event-study window is contaminated by every other headline in it.
  S6/S21 were funded first this run for that reason and produced a wired artifact.
Macro/policy event source for the MT5 universe (DXY, gold, indices, energy): tariff/Fed/dollar
statements move hunted instruments. Route: public web/archives only, timestamps preserved
point-in-time; event-study gate (RESEARCH §6) is the ONLY admissible test shape.

### 46. [seed S6] Central-bank statements, systematic — grade: **verified-clean + WIRED 2026-08-26 (unified frontier dig): the miner that was supposed to own this ground was structurally incapable of producing a dated series, and is now repaired and producing one** [§33: wired tier:2 -> desks/mt5/data/intelligence/central_banks/cb_documents.jsonl]
- **§13:** public RSS/RDF feeds published by each institution for syndication, read at their
  documented endpoints, no account, no crawl of disallowed paths, no paywall. Fed press releases
  are US-Government public domain; BIS/ECB/BoJ/BoE/BoC feeds are the banks' own distribution
  channel. Nothing here is cracked, gated or closed-group.
- **THE DEFECT (this is the finding, not the feed list).** `desks/mt5/side_channels/central_bank_miner.py`
  was already wired into `run_all_miners.py` and already flagged ZERO-YIELD by
  `scripts/check_miner_conversion.py` (20+ rows, 0 survivors in 14d). The reason was structural, and
  reading the file rather than the fence explains it:
  1. **No timestamp anywhere in its output.** It scraped each bank's HTML *landing page* and kept
     `re.sub(r'<[^>]+>', ' ', text)[:2000]` — the first 2000 characters after tag-stripping, i.e.
     navigation chrome — then counted policy keywords in it. A keyword count on today's landing page
     is not an event. **The desk's two absent-but-reachable families, `event_reaction` (needs an
     economic calendar) and `macro_conditional` (needs a macro state series), could never be fed by
     it**, because an event study is impossible without a publication stamp.
  2. **`_extract_symbols` matched instrument tickers as literal substrings of a central bank page.**
     "EURUSD" does not appear on federalreserve.gov. Positive control run against `git show HEAD:`
     of the old file: `_extract_symbols("Federal Reserve Board monetary policy USD press release")`
     -> `[]`, on every run, so the fallback `f"{currency}USD"` fired and emitted **"USDUSD"** for the
     Fed — not an instrument.
  3. `confidence = len(signals) * 0.3` is a popularity score, not a mechanism.
  This is the WS-005 shape at source level: the fence could see the miner producing nothing of value
  but not *why*, and "zero-yield source" and "broken reader pointed at a good source" look identical
  from the outside — the same class as card 41's MQL5 collector (R0660).
- **THE REPAIR (same change as the diagnosis).** The miner now reads dated syndication feeds and
  archives point-in-time documents. Probed live 2026-08-26, all keyless HTTP 200 with per-item
  stamps: Fed `feeds/press_monetary.xml` (pubDate, CDATA-wrapped), ECB `rss/press.html`, BoJ
  `en/rss/whatsnew.xml`, BoE `rss/news`, BoC press-release feed, BIS `doclist/cbspeeches.rss`
  (RDF `dc:date`, not `pubDate` — a pubDate-only reader returns zero rows here and reads as a clean
  empty, so both tag families are parsed). Instruments are now **derived from the speaking bank's
  currency**, never substring-matched. An undated item is **DROPPED, never stamped with `now`** —
  a collection time standing in for a publication time is the L1.46 clock-provenance defect.
- **Measured first run:** **162 dated documents**, 0 undated, span 2026-03-18 -> 2026-08-26, across
  BoE 50 / BoJ 47 / BIS 25 / Fed 15 / ECB 15 / BoC 10. Artifact:
  `desks/mt5/data/intelligence/central_banks/cb_documents.jsonl` (append-only, deduped on bank|link).
  Seven regression tests in `tests/test_central_bank_miner.py`, each naming the defect it catches;
  the two structural ones were positive-controlled against the pre-fix file.
- **RESIDUALS, named rather than left to read as success:**
  1. **RBA is DEAD from this box.** Both published feed paths return HTTP 403 under two distinct
     user agents — an edge block on the IP, not an absent feed. The row is deliberately KEPT in the
     seed dict so the miner REPORTS the dead leg every run; **AUD has no central-bank coverage and
     that must not read as a clean verdict** (WS-005). §38 replacement route is owed.
  2. **SNB not yet routed** — the obvious path 404s; CHF uncovered.
  3. **Only 2 of 162 rows carry a policy signal**, because RSS titles/descriptions are terse. The
     keyword layer needs the *document body* behind `link`, which this pass does not fetch. **This is
     an attention stream, not yet a hawkish/dovish series**, and it must not be scored as one.
  4. **RSS is a rolling window: this axis CANNOT backfill.** It accrues forward from today, so the
     families it feeds gain power with calendar time. That is a real cost of the six months this
     miner spent broken, and it is the argument for fixing readers the moment a fence calls a source
     zero-yield rather than accepting the source verdict.
- **Convergence with [seed S21] BIS central-banker speeches:** S21 asked for exactly this PIT text
  layer ("no per-CB scrapers needed"). The BIS feed is now wired here, so S21's route half is
  **satisfied by this card** and its remaining novelty is the full-text speech bodies (residual 3
  above). Recorded as one discovery reached from two seeds, not two.
Fed/ECB/BoJ/BoE/SNB/RBA/RBNZ/BoC full text + minutes + speaker calendars, diffed
statement-over-statement (hawkish/dovish delta as a data axis, ALFRED-style point-in-time).
Macro is a first-class edge axis (RESEARCH §2); this is its primary free document stream.

### 47. [seed S7] CN ground: Bilibili + Zhihu — grade: pending verification (NOT worked 2026-08-26 — owned by the CN miner, skip reason named) [§33: deferred(2026-09-05) tier:3]
- **Skip reason:** Zhihu is recorded WALLED twice by the CN miner (s12, 2026-08-25) and this seed
  asks for a *cadence*, not a route — cadence is the CN seat's to set, and a unified dig probing
  the same wall a third time would burn budget to re-derive a known verdict. The open unit here is
  the Bilibili half, which has never been probed; it stays with the CN seat.
Already first-class in the CN miner (8–9 docs); seed confirms DAILY cadence and extends to the
quant-video/column layers the frontier digs have not yet exhausted.

### 48. [seed S8] KR ground continuation — grade: pending verification (NOT worked 2026-08-26 — owned by the KR miner, skip reason named) [§33: deferred(2026-09-05) tier:3]
- **Skip reason:** the seed extends an operator set the KR seat already holds, and the KR venue-state
  layer it used to feed was KILLED by the 2026-08-18 mandate re-grade (card 26 above), so the ground
  needs re-scoping to MT5 instruments before any cadence question is even well-posed. Re-scoping is
  the owed unit and it belongs to the KR seat.
Naver blogs/cafes covered (3 docs); extend to KR quant communities per the KR miner's existing
operator set, daily.

### 39. Session-fix / benchmark-auction window family (WMR 4pm London FX · LBMA gold-silver auctions · Tokyo 09:55 nakane) — grade: **verified-clean 2026-08-26 (LBMA daily auction JSON, keyless, 1968→T-1, diffed against the desk XAUUSD tape); literature CONVERGENT, mechanism EQUILIBRIUM-GRADE; desk's own gotobi screen: replicated 2018–2020, DEAD in current regime; residual: IBA per-round reports** [§33: screened -> data/gotobi_screen.json]
- **Provenance (litminer run 10, 2026-08-25):** Osler–Turnbull *JBF 2026* "Dealer misconduct and
  price dynamics at the fix" (WP: Brandeis 101R, 403-walled; EconPapers abstract read) — model:
  dealers holding advance client fix orders extract the signal; predicts pre-fix accelerating
  drift + partial retracement in ALL THREE regimes (independent/info-sharing/collusion), i.e.
  **predictability is an equilibrium feature of benchmark execution, not a misconduct residue**.
  Ito–Yamada *JIMF 2018* (VERBATIM abstract, RePEc): volume spike died post-2015 reform, price
  anomalies PERSIST, passive execution "generates another predictability". Ito–Yamada NBER w22820:
  Tokyo-fix order imbalances predictable in direction. Bessho–Sugimoto–Suzuki arXiv 2301.13204
  (ar5iv full read): gotobi USDJPY drift onset ~03:00 JST, strategy PF 2.60 (N=167, EBS 2018–2020),
  specificity control PF~0.5 on non-gotobi. Decay layer: month-end fix crowding −45% YoY
  (run 9, RELAYED); JP retail EA/TradingView productization of gotobi (MQL5 product 162603 etc.).
- **Mechanism (who is forced, why they persist):** benchmark-tracking clients (index/FX-hedged
  funds at WMR; importers' invoice custom at nakane; ETF/OTC settlement at LBMA auctions) MUST
  transact at the print; dealers/banks internalize the flow and execute into the window. The flow
  is contractual/customary — it cannot stop; only its footprint migrates as execution style shifts.
- **Desk evidence THIS RUN (`data/gotobi_screen.json`, preregistered, 3 trials):** JST
  03:00→10:00 USDJPY on own broker tape: 2018–2020 gotobi excess **+5.33bp/d, t=2.55, p=0.006**
  (independent replication of the paper on different data); **2021–2026 OOS +0.43bp, t=0.26 —
  gross below the 1.02bp RT cost; current-regime NET-NEGATIVE.** Full-sample p=0.0499 knife-edge,
  carried entirely by the dead years → NOT queued to the gauntlet; graveyarded with re-open
  trigger (see `gotobi_nakane_drift`).
- **Open ends, ranked:** (a) **LBMA auction path**: DAILY LEG **VERIFIED-CLEAN 2026-08-26**
  (prices.lbma.org.uk/json/{gold_am,gold_pm,silver}.json, keyless, 1968→T-1); residual is the
  IBA per-round transparency reports (price,
  bid/offer volume, participants per 45s round) publish FREE same-day; **historical bulk is
  licence-gated (Historical Access License) — §13: bulk NOT touchable; daily-report reuse terms
  UNRESOLVED, read ICE ToU before any collector**; PRIMARY-source alternative needing no IBA data:
  desk's own XAUUSD M1 around 10:30/15:00 London (M1 pull needed — universe lake is H1;
  gateway serves M1). **15:00-London ≡ 10:00-NY US-release confound is a MANDATORY control**
  (LBMA rebuttal, run 9). (b) WMR month-end M1 screen on majors — same M1 data need. (c) EFMA2017_0580
  "Transparency in Commodities Markets" — the ONLY direct post-reform predictability-decay study
  found; UNREADABLE (efmaefm.org TLS broken server-side, 2 routes, 2 runs) and author identity
  unfound after 3 searches — recovery route: EFMA 2017 Athens programme page. (d) Crain–Hoelscher–
  Jones ACRN 2020 (open, PDF on disk /tmp lost at reboot; acrn-journals.eu/resources/jofrp09m.pdf):
  Benford/clustering structural break at reform — manipulation-forensics grade, no exploitability
  test. On-box extractor cannot decode its fonts (font-subsetting class — known GAP#70 limitation).
- **CLOCK-PROVENANCE DEFECT found en route (L1.46, routed to ledger this run):** every
  `desks/mt5/data/universe/*_H1.parquet` timestamp is broker SERVER time (NY-anchored UTC+2/+3)
  **labeled UTC** (`gateway.py:1268` stamps `utc=True` on server epochs). Proven: zero Sunday
  bars, Fridays→23:00, NFP/CPI spike at labeled hour 15 on USDJPY AND EURUSD. Every session-logic
  or macro-calendar join on these files is 2–3h wrong until repointed.

### 40. COT position-CHANGE liquidity premium on MT5 legs (KRT channel — the construction the 41y screen never charged) — grade: **SCREEN-KILLED 2026-08-25 (preregistered bar): pooled Δ1w NW t=−0.41 (n=12,356, 10 assets, 26 trials), recent-24m sign POSITIVE (t=+0.24), XS IC −0.011 (t=−0.92)** [§33: killed -> data/cot_change_screen.json]
- **Provenance (litminer run 10, 2026-08-25):** Kang–Rouwenhorst–Tang *JF 2020* (197 citers) —
  TWO premiums: hedging-pressure LEVEL earns an insurance premium at long horizons; position
  CHANGES earn a LIQUIDITY-PROVISION premium at ~weekly horizon (commercials smooth
  noncommercials' demand; change-chasers pay, faders earn). Replication state, checked this run:
  **Maréchal *JFM 2023* 43(5):580-614 "A tale of two premiums revisited"** (1994–2017, open drafts:
  acfr.aut.ac.nz P3.pdf + loicmarechal.dev): **liquidity premium ROBUST to risk adjustments
  (momentum, basis, basis-momentum, OI, crowding) and to financialization; insurance premium decays
  0.43→0.34, 1%→10% significance, "eventually vanishes"** (RELAYED from search+abstract; draft PDF
  is open for verbatim numbers). BoE WP 2025 (liquidity/monetary-policy interaction) downloaded,
  UNREADABLE on-box (extractor limitation, see run note). RT2012 already flagged the change-return
  correlation weakening in recent samples — decay watch is part of the falsifier.
- **Desk prior it does NOT re-litigate (L1.17):** `COT_SCREEN_RESULT.md` killed the LEVEL/lagged
  construction (pooled NW t=−0.64, 41y, 6 contracts, 24 trials) — that kill is now
  LITERATURE-CONVERGENT (Maréchal's vanishing insurance premium). This card is the OTHER channel:
  weekly net-position CHANGES → short-horizon reversal/liquidity premium, untested on desk data.
- **Mechanism (who pays, why they persist):** noncommercials demanding immediacy in size move
  futures away from fundamental value; commercials accommodate and earn the reversion. Persistent
  because speculative flow is momentum/mandate-driven and commercial capacity is balance-sheet
  bound — neither side can stop.
- **MT5 mapping:** COT/TFF covers the desk's XAUUSD, XAGUSD, WTI/Brent, NatGas, SP500/NAS100/US30,
  EUR/JPY/GBP/AUD/CAD/CHF/NZD legs → breadth ~12 (N_eff lower; measure). Price legs: desk's own
  H1 parquets (2018→) resampled weekly; deeper history via the licence-clean FRED legs already
  used by `run_cot_screen.py`.
- **Falsifier / prereg constants (to fix in AXIS_PREREGISTRATIONS before any computation):**
  release-aligned (Friday 15:30 ET publication of Tuesday snapshot — NO use of Tuesday info before
  release; the desk's PIT discipline), Δnet_noncommercial (1w and 4w) → next-week return, sign
  NEGATIVE (reversal), per-instrument time-series AND small-cross-section forms, trials counted
  per cell. KILL: pooled effect ≥ 0 or indistinguishable at the standard bar.
- **Dependencies, named:** (a) parser: REUSE `run_cot_screen.py`'s era-alias/prefix-anchored
  parser (its self-found defects are already fixed) — do NOT reuse the `cot_btc_panel.json`
  builder (R0613 comm==noncomm defect OPEN); (b) clock: parquet timestamps are server-time
  mislabeled UTC (this run's L1.46 find) — weekly resampling must use the corrected clock or
  release-day boundaries are wrong by 2–3h (usually sub-material at weekly horizon, still fix).
- **EV gate (this run, honest inputs logged):** est_sharpe 0.35 (published, post-risk-adj),
  breadth 12, orthogonality 0.7 vs trend/breakout book, effort 12h, tags [new_orthogonal_data]
  (NOT crowded_known — retail COT folklore trades level-extremes, not changes) → **EV 0.0032,
  p_survive 0.24, QUEUE**. Run-9 note for contrast: both its session-fix candidates scored 0.0001.

## PRINCIPAL SEED DROP 2 — 2026-08-25 evening (miner breadth-out: maximum survivor hunting)

Same rules as Drop 1: seeds never boundaries, §13 gate unchanged, screen-on-discovery, §33
dispositions. PRIORITY ORDER IS THE MEASURED SOURCE-CLASS ROI: creator/track-record grounds
produced 94 stage-A survivors and the desk's only exact certificate; build those miners first.
Each card is a PYTHON-MINABLE enumeration target (token-free collector -> data/intelligence/*),
with Claude judging afterward — the corpora-first split, by construction.

### 49. [seed S9] MQL5 Signals leaderboard deep-miner — grade: **verified-clean 2026-08-26 (prospector; FULL population enumerated: 2,529 signals over 53 pages, page 54 = HTTP 404)** [§33: screened -> data/intelligence/mql5_prospector/verification_20260826.json]
- **Route:** `https://www.mql5.com/en/signals/mt5/list/pageN`, 48 rows/page in `div.row signal`.
  **18 fields per row plus a 20-point equity sparkline** carried in a hidden input: name, author,
  real-vs-demo, price, total growth, profit/month, subscribers, funds, balance, weeks live,
  %-traded-by-EA, trades, win%, activity%, profit factor, expected payoff, max drawdown, leverage.
- **Measured cross-section (n=2,529, all REAL accounts):** growth med 29% (p10 -13, p90 288) ·
  profit/month med 4% (p10 -12, p90 27) · weeks live med 23 (p10 4, p90 102) · EA-traded med 97% ·
  trades med 302 (p90 2,427) · win% med 68 (p90 88) · profit factor med 1.34 (p10 0.86) ·
  **max drawdown med 25%, p90 63%**. A survivorship-selected leaderboard whose MEDIAN member
  runs 25% drawdown for 4%/month — the selection bias is the headline, and it is now quantified.
- **NO CARD MINTED.** The obvious mechanism — fade the copy-trading crowd / trade subscriber-flow
  crowding — is **pre-emptively graveyarded** by `cn_bucketshop_retail_loss_as_directional_signal`,
  whose row states it falsifies *every* retail-sentiment-contrarian hypothesis including the
  reverse-copy-trade (反向跟单) industry built on it. Discarded at the graveyard gate, not re-logged.
- **CAVEAT, reported because it is mine:** the 2,529-row raw file was destroyed by my own re-run —
  a second crawl launched to fix two numeric-parse bugs hit the 403 above and wrote its empty
  result over the only good harvest. Every statistic above was computed from the full population
  BEFORE the overwrite and is measured; the row-level file needs a paced re-crawl.

Per-signal public stat pages: growth curve, drawdown, trade count, weekly history, subscriber
count. LIVE verified track records on the desk's own platform — the single richest black-box
reverse-engineering ground (RESEARCH §4). Extract stats + rank deltas; flag high-growth/low-dd
signals for mechanism inference. [§33: deferred(2026-09-01) tier:1]

### 50. [seed S10] Myfxbook public systems + community outlook — grade: **WALLED-AT-EDGE 2026-08-27 (unified frontier dig): Cloudflare managed challenge returns **HTTP 403 on robots.txt itself** — the §13 read is not merely unfavourable, it is UNOBTAINABLE from this box, which is its own status and NOT a licence verdict (L1.28a / WS-005). This is a ROUTE problem, not a ground verdict: OP-098 (CDX over `myfxbook.com/members/*`) is the untried rediscovery route and is the owed unit** [§33: deferred(2026-09-03) tier:1]
Verified track records (equity curves, per-trade history where public) AND the community outlook
endpoint (retail % long/short per pair) — the positioning axis, consumed WITH the standing
B-book debias prior (retail ruin is cost extraction, never naive fade).

### 51. [seed S11] Darwinex public DARWIN metrics — grade: **route HALF-SOLVED 2026-08-27 (unified frontier dig). POPULATION SOLVED: Wayback CDX over `darwinex.com/invest/*` = **1,479 DARWIN tickers** (OP-098). Per-entity page live and keyless — `/darwin/<T>` 302s to `/invest/<T>`, 165KB, robots-permitted (`Disallow` covers /api, /private, /darwinex-index, not /invest). RESIDUAL, stated so nothing reads as done: the 12 investable attributes + D-Score are client-side and the XHR was NOT found in the landing bundle — metrics extraction is OWED. `/api` is robots-BARRED, so that route is closed by §13, not by difficulty** [§33: deferred(2026-09-03) tier:1]
Public API: d-scores, return series, investor capacity per DARWIN. A regulated, curated
track-record universe with its own risk-normalization to reverse-engineer.

### 52. [seed S12] TradingView public Pine library, systematic — grade: **KILLED on §13 2026-08-27 (unified frontier dig; robots read in full and group-scoped, the KR-s5 discipline). TradingView publishes a SECOND user-agent group naming `ClaudeBot` alongside 15 other AI crawlers, and that group's rules are `Disallow: /ideas/*, /scripts/*, /script/*, /v/*, /u/*, /chat/*, /chart/*, /watchlists/*` — it bars EXACTLY the ground this seed wanted. The `*` group permits /scripts/, so a naive one-group read INVERTS the verdict (OP-103 class). The desk's agent is Claude-family; §13 is absolute; this ground is closed to agentic mining and no UA-substitution route will be built** [§33: killed tier:3 -> docs/graveyard.md `tradingview_pine_agentic_mining`]
Open-source script pages (full Pine source = direct strategy corpus), per-script boost/use
counts, author graphs, per-symbol ideas streams. hunt16's families were TradingView-style
indicator recreations — this is that ground, mined at the source.

### 53. [seed S13] FX Blue public profiles — grade: **verified-clean — POPULATION SOLVED AND CORPUS BUILT 2026-08-27 (unified frontier dig). The 08-25 verdict "there is no population route" was WRONG: Wayback CDX over `fxblue.com/users/*` enumerates **5,077 handles** (OP-098). Data layer fully resolved keyless — liveness `strivewidget.aspx?displayUserId=`, headline `wl/view.aspx?id=&mode=overview`, and **51 mechanism charts** `wl/charts/<ch>.aspx?id=` whose numbers are literal in a Google-Charts `addRows([...])` block (hour-of-day, per-symbol, direction, duration, day-of-week, lot sizing = the §4 black-box axes). §13: `Allow: /`; no robots on the api host. **MEASURED on a 117-handle stride sample: 83 data-bearing / 25 shell / 9 dead ⇒ ~71%, i.e. ~3,600 mineable MT5-native track records.** Instrument mix is 100% inside the mandate (EURUSD 51% of accounts, GBPUSD 41%, USDJPY 35%, XAUUSD 22%). SELF-CORRECTION recorded in the miner: the first harvest called 95/120 "live" on BYTE COUNT and every one was a zero-filled shell — the population is BLOCK-STRUCTURED (contiguous bulk-registered `22-*` runs), so liveness is now `has_data` (a non-zero number in a chart) and sampling is STRIDED. Harvester + summariser wired** [§33: wired tier:1 -> desks/mt5/data/intelligence/fxblue/track_records_spread.jsonl]
Public stats pages of live accounts (many prop-firm passers publish here).

### 54. [seed S14] Collective2 public strategy leaderboards — grade: pending verification [§33: deferred(2026-09-05) tier:2]
Cross-asset strategies with published records + fee/capacity data.

### 55. [seed S15] QuantConnect forum + published algorithms — grade: pending verification [§33: deferred(2026-09-05) tier:2]
Shared LEAN algorithms (source available), forum strategy threads, league rankings.

### 56. [seed S16] ForexPeaceArmy performance tests + review corpus — grade: pending verification [§33: deferred(2026-09-05) tier:2]
The EN refutation genre (RU поделка analogue): independent live performance tests of EAs and
signal services — free graveyard material + occasional real survivors.

### 57. [seed S17] ForexFactory Trade Explorer public profiles — grade: pending verification [§33: deferred(2026-09-05) tier:2]
Live retail trade streams from linked accounts; plus PIT calendar REVISION capture (the
existing calendar miner keeps only current values — vintages are the revision-aware layer
h19-003 needs).

### 58. [seed S18] Wayback CDX walker for dead EA forums — grade: pending verification [§33: deferred(2026-09-08) tier:2]
Forex-TSD attachments corpus (OP-096b, already carded by the EN dig): flat CDX enumeration of
.mq4 sources + posted MT4 statements from the pre-MQL5 era. Pure python; web.archive.org works
via curl from this box (measured).

### 59. [seed S19] quant.stackexchange full dump — grade: pending verification [§33: deferred(2026-09-08) tier:3]
Stack Exchange data dumps (CC BY-SA, archive.org): every quant Q&A ever, offline-minable —
mechanism folklore + refutations at zero marginal cost.

### 60. [seed S20] arXiv q-fin API daily feed — grade: pending verification [§33: deferred(2026-09-08) tier:3]
Keyless Atom API: new q-fin abstracts daily into the corpus; the monthly lit dig then judges a
pre-built month instead of browsing.

### 61. [seed S21] BIS central-banker speeches full-text — grade: **needs-monitoring** (source route VERIFIED 2026-08-28 by the free-data-alternatives miner; PENDING because the licence is noncommercial-only and the wired consumer carries a measured 2.5% venue-attribution defect with an exact patch owed — see ITEM 1 below) — **CLOSED 2026-08-28 — bodies acquired (20,728 dated speeches, 1996–2026), tone series built, and the directional hypothesis it existed to produce is REFUTED** [§33: screened tier:2 -> desks/mt5/reports/cb_tone_screen.json]
- **The residual below is discharged, by a route nobody had looked for.** The owed item was "the
  speech BODIES behind each `link`", assumed to be a 215-request crawl of per-bank landing pages.
  BIS publishes a **pre-compiled full-text extract of every speech it has collected since 1996**
  at `https://www.bis.org/speeches/speeches.zip` — one request, one 390MB CSV, 20,728 rows of
  `url,title,description,date,text,author`, offered explicitly "to assist researchers" with terms
  permitting noncommercial use and **no robots bar on `/speeches/`**. Free-frontier: the body
  layer was never a crawl problem, it was a *route-not-found* problem.
- **§13 DEFECT FOUND IN THE WIRED MINER, repaired in the same change.** The feed this card
  celebrates above — `bis.org/doclist/cbspeeches.rss` — sits under `Disallow: /doclist/` in
  bis.org/robots.txt. `central_bank_miner.py` had been reading a robots-barred path since
  2026-08-26. The feed row is removed (`side_channels/central_bank_miner.py`); its currency was
  `XXX`, so no MT5 leg loses coverage. The access boundary is a hard limit, not a preference.
- **Two uncovered currency legs close by route, not by retrying a blocked one.** RBA/AUD has been
  a dead 403 leg since 2026-08-26 and SNB/CHF had no feed at all. Both speak in this corpus:
  **AUD 589 and CHF 437 attributed speeches.** Full attribution: EUR 2742, USD 2567, GBP 812,
  JPY 801, CAD 613, AUD 589, CHF 437, NZD 209 — 8,770 of 20,728 attributed to an MT5 currency's
  own central bank; the other 11,956 name no listed bank and are DROPPED, never defaulted to a
  currency (the `USDUSD` class of defect this corpus replaces). 2 future-dated rows dropped as a
  look-ahead.
- **Artifacts:** `desks/mt5/side_channels/bis_speech_tone.py` (builder),
  `.../central_banks/bis_speech_tone.jsonl` (per speech), `.../cb_tone_series.jsonl` (7,420
  dated per-(date,currency) rows), `desks/mt5/research/cb_tone_screen.py` (screen),
  `desks/mt5/reports/cb_tone_{screen,surprise_screen,vol_screen}.json`.
- **THE VERDICT — REFUTED, and this is the run's most valuable output (a disproof withdraws
  capital from a false edge and retires search space).** Three pre-stated arms, all null at
  lag 2 / horizon 5 trading days:
  - **tone LEVEL → own currency vs USD:** pooled t = **−0.777** (n 688 hawk / 3508 dove); every
    per-currency |t| < 1.7 and the signs disagree (CHF −1.69, GBP +0.36).
  - **tone SURPRISE** (z vs the currency's own trailing 250-obs baseline — run because the
    lexicon is 5:1 dove-skewed by base rate, so a *level* is confounded): pooled t = **−1.309**.
    EUR −1.97 and JPY +2.05 are opposite-signed at 7 tests: that is multiplicity, not two edges.
  - **direction-agnostic volatility arm** (the desk's own measured prior says direction is not
    predictable and volatility is): forward/prior vol ratio on speech days **0.903** vs an
    all-days control of **0.888**, n 5,008 vs 90,165; splits on speech count t = **0.105** and on
    |net tone| t = **−0.633**. Central-bank speech days are not even *volatile* days.
  - No threshold was applied in either direction and nothing was promoted (L1.60); these are
    sorting numbers on non-independent currency-days, never admission statistics.
- **What survives the refutation:** the corpus itself, which is a genuine 30-year PIT text asset
  and the input h19-003 (news/event trading) needs. What died is the *daily-aggregated
  directional* reading of it. The untested residual is the **intraday event window** — this lake
  is daily, so a 5-minute reaction to a scheduled speech is UNMEASURED, not absent (L1.28a).

### 61-legacy note (the state this card was in before 2026-08-28) [§33: superseded(2026-08-28) tier:3]
- **Convergence, recorded once (not two discoveries):** this seed's stated ask was a dated PIT
  text layer with "no per-CB scrapers needed". `https://www.bis.org/doclist/cbspeeches.rss` is
  now probed, parsed and wired by the repaired central-bank miner — 25 dated speech rows in the
  first archive run. Note the feed is **RDF with `dc:date`**, not RSS `pubDate`; a pubDate-only
  reader returns zero rows and reads as an empty feed.
- **Residual owed here:** the speech BODIES behind each `link`. The feed carries title + date
  only, which is why just 2 of 162 archived documents currently match a policy keyword — the
  hawkish/dovish delta this seed exists to produce needs the full text and does not exist yet.
bis.org aggregates ALL central banks' speeches with dates — the PIT text layer behind h19-003's
event trading, no per-CB scrapers needed.

### 62. [seed S22] Broker swap/spread tables across MT5 brokers — grade: **route re-graded 2026-08-26 (prospector) — the SINGLE-broker half is ALREADY BUILT; only the CROSS-broker half is novel** [§33: deferred(2026-09-08) tier:2]
- MQL5's codebase surfaces a whole genre of live swap panels (`Swap Meter`, `Swap Fee Monitor
  Panel`, `Quantora Trading Cost Calculator`) that read swap from the terminal, not from broker
  web tables. Checked against the desk: `desks/mt5/side_channels/seed_miners.py:238` already
  states and implements exactly that — `symbol_info.swap_long/swap_short` as authoritative and
  point-in-time — and `expand_universe.py:109` records it per symbol. **No finding; recorded so
  no future run re-discovers it.** The card's remaining novelty is strictly the CROSS-BROKER
  dispersion (one terminal cannot see another broker's swap menu).

Extend broker_physics_miner: daily swap-table snapshots across brokers = the carry structure of
the CFD universe (swap arbitrage/carry tilt axis) + spread menus for the cost surface.

### 63. [seed S23] GitHub topic/star-delta novelty sweeps — grade: pending verification [§33: deferred(2026-09-08) tier:3]
Systematic (not incidental) sweeps of mql4/mql5/pine/forex-ea/backtesting topics with star/fork
DELTAS as the novelty signal; fork-graph expansion from any repo that converts.

### 64. [seed S24] Prop-firm public leaderboards (FTMO et al.) — grade: pending verification [§33: deferred(2026-09-08) tier:3]
Passer/payout leaderboards + published stats where public: a survivorship-heavy but
selection-documented track-record ground; selection-bias defense (master 23) mandatory.

---

## SESSION 2026-08-26 (free-data-alternatives miner) — IN PROGRESS

Items taken this run (bounded per COMPLETION CONTRACT; both are the ONLY rows the source backlog
lists as pending technical verification, so the backlog is cleared to zero pending this run):
1. **CN gold layer** — SGE Au99.99 / Au(T+D) premium vs XAUUSD + 递延费 (deferred-fee) direction.
2. **Session-fix / benchmark-auction window family** — WMR 4pm London FX · LBMA gold+silver
   auctions · Tokyo 09:55 nakane (TTB/TTS fixing).
Both are MT5-universe axes (XAUUSD, XAGUSD, FX majors) under the standing universe mandate.

**RESULT: both items CLOSED verified-clean, backlog pending-verification -> 0. Plus one
cross-cutting defect that neither item was looking for (R0660), which is the run's real find.**

### THE FIND — the MT5 lake's timestamps are labelled UTC and are not UTC (R0660, ledgered)
Verifying the LBMA auction against the desk's own XAUUSD tape is a CLOCK test before it is a
price test, and the clock failed. LBMA PM is 15:00 London year-round. Fitting `XAUUSD_H1` closes
to it (n=667, since 2024-01-01):

| bar hour label | all | Jun-Aug | Dec-Feb |
|---|---|---|---|
| 15 | sd 45.0 bps | 37.7 | 40.3 |
| **16** | **sd 21.0** | **11.3** | **19.9** |
| 17 | — | 31.4 | 49.3 |

Bar 16 wins in BOTH seasons, i.e. its CLOSE (17:00 server) is 14:00 UTC in summer and 15:00 UTC
in winter — exactly EEST/EET (UTC+3 / UTC+2), the Fusion server clock. Corroborated independently
and without any external data: EURUSD/USDJPY/XAUUSD all carry Friday bars at 21:00, 22:00 and
23:00 "UTC" and zero Sunday bars, while FX actually shuts at 21:00 UTC — impossible under the
label, exact under EET/EEST.

**This is not latent.** `desks/mt5/research/fetch_sge_premium.py:190` takes `df.index.hour == 7`
believing it is 07:00 UTC (the bar containing the 15:30 CST SGE close). The true bar is 10 (EEST)
/ 9 (EET). Measured cost on that wired daily axis: swapping to the correct bar changes the leg by
sd **17.14 USD/oz** (p95 34.2) against a premium whose own sd is **20.78 USD/oz** — about **40% of
the wired premium's variance is pure clock artifact**. Every session/calendar/event-window study on
this lake carries the same 2-3h misattribution, with a DST-dependent seam.
FIX (research-freeze: named, not applied): one shared loader that does
`idx.tz_localize(None).tz_localize('Europe/Athens').tz_convert('UTC')` at read time, plus a fence
asserting no bar exists after Friday 21:00 UTC (the label's own contradiction). Routed to R0660.

### Item 1 — CN gold layer (card 38) — CLOSED verified-clean
Card 38 was WIRED this morning by the collector seat; what it lacked was an INDEPENDENT
verification and a fee-direction feed. Both delivered:
- `POST https://www.sge.com.cn/graph/Dailyhq` body `instid=Au99.99` (and `Au(T+D)`) — keyless,
  2,350 rows 2016-12-16 -> 2026-08-25. **A GET returns an all-zeros skeleton rather than an
  error** — the silent-null failure mode; a naive collector records a dead market and no gauge fires.
- Premium vs desk XAUUSD with the ECB CNY leg: n=633 since 2024-01-01, mean **+36 bps**, sd 78,
  **AR(1) 0.907**, max +283 bps. Persistent and shaped like the quota-gated arb card 38 describes.
  Weak fwd-5d corr with XAUUSD (-0.069) — that is the gauntlet's verdict to make, not mine.
- **递延费 gap closed WITHOUT the notices feed:** the 延期费 announcement route is not reachable
  (`/sjzx/yqf` carries no fee table; `/protal/article/articleSearch` returns `code 9999` on every
  payload shape tried). But the fee is *what makes the basis*: **Au(T+D) − Au99.99 = mean −3.2 bps,
  sd 7.6 bps**, one extra POST to the same verified endpoint. Card 38's "collector owed — FEE
  DIRECTION" no longer blocks the axis. Residual (the exact fee RATE) graded needs-monitoring with
  a `replacement_hunts` entry (§38).
- Schema drift caught in passing: `api.frankfurter.app` now **301s**; use `api.frankfurter.dev/v1`.
  Without `-L` you get HTML and a collector that parses it as an outage.

### Item 2 — Session-fix / benchmark-auction family (card 39) — data leg CLOSED verified-clean
Card 39's open end (a) was "LBMA auction path". The data leg exists, keyless and complete:
`https://prices.lbma.org.uk/json/{gold_am,gold_pm,silver}.json` — `[{d, v:[USD,GBP,EUR]}]`,
**1968-01-02 -> 2026-08-25**, 14,669 / 14,821 / 14,832 rows, fresh to T-1, no auth, no throttle.
That is a 58-year PIT benchmark-window series for XAUUSD/XAGUSD at zero cost — and, as above, a
permanent independent **clock oracle** for any MT5 metals feed, which is worth more than the
prices. Structural caveat: the auction is a discrete event, so a ~10-20 bps spot-vs-auction basis
is real and is not error. Per-round transparency (price/volume by round) is still IBA-report-only
and remains card 39's residual — NOT in this feed.

**CLOCK ORACLE, THIRD AND DECISIVE PASS (added same run, next-ground item (ii) pulled forward).**
The offset is now pinned season-by-season with no external data at all: the trading week ends at
the **24:00 server boundary in BOTH seasons** — Friday's last H1 bar is labelled 23 in summer
(EURUSD n=117, XAUUSD n=113) *and* winter (109 / 100), while the FX week actually closes 21:00 UTC
under BST and 22:00 UTC under GMT. Only a UTC+3 / UTC+2 server clock puts both at 24:00 local.
Monday's first bar is 00 for FX and 01 for gold (the metals session opens an hour later) — again
local-clock behaviour, not UTC.
A fourth pass against the ECB 14:15 CET reference is **consistent but NOT discriminating**, and is
recorded as such rather than dressed up: EURUSD and USDJPY both fit bar 14 in both seasons at sd
3-4 bps (vs 10-20 either side), but the ECB fix carries its own DST shift which cancels against the
broker's, so that test cannot separate the offsets. The LBMA fit and the week-boundary do.

**DEPTH:** item 1 exhausted (both contracts pulled to first row, three fee-notice routes probed
and failed with their error codes recorded, premium computed and cross-checked against two
independent USD legs); item 2 exhausted for the daily-benchmark layer, residual named (IBA
per-round reports). Depth is what produced R0660 — a surface link-grab of the LBMA JSON would
have adopted it and never diffed it.

**NEXT UN-EXHAUSTED GROUND (next run):** (i) IBA per-round LBMA transparency reports — card 39
residual; (ii) the same clock oracle applied to the FX legs (ECB 14:15 CET reference vs EURUSD,
Tokyo 09:55 nakane vs USDJPY) to confirm R0660's offset symbol-wide and date the DST seams
exactly; (iii) the 24-symbol lake vs the far larger universe registry — every axis above is
gated on symbols the lake does not hold (no USDCNH is why item 1 needed an external FX leg).

## SESSION 2026-08-27 (free-data-alternatives miner, standing daily run) — CLOSED

Backlog: `source_backlog_next.py` reports **0 pending verification, 0 pending legitimacy** (39
resolved, 29 deferred to 2026-09-01 → 09-15). Mining authorised; the three items are exactly the
un-exhausted ground the 08-26 note named.

**RESULT: all three items closed. One new free axis ADOPTED (verified-clean), one residual graded
needs-monitoring with its documented failed search (§38), and — the run's real find — R0660 was
shown to be measured on only 12% of the lake, then independently re-confirmed on the other 88%.**

### THE FIND — the lake is TWO lakes with different clock semantics (extends R0660)
A tz census of all 197 `*_H1.parquet`:

| index dtype | symbols | which |
|---|---|---|
| tz-**aware**, stamped UTC | **24** | AUDCAD…USDCHF, XAGUSD, **XAUUSD, EURUSD, USDJPY**, BTCUSD, ETHUSD |
| tz-**naive** | **173** | everything else (shares, indices, exotics, base metals, XPTUSD…) |

That 24/173 split is **exactly** GAP #148's tracked-vs-gitignored split — two producers write one
lake with two clock conventions. R0660 was measured on XAUUSD, EURUSD and USDJPY, **all three of
which are in the tz-aware 24**. So the 08-26 finding covered 12% of the lake and the other 88% had
never been clock-tested. The aware 24 are the worse half: they carry a *false* UTC tz stamp over
server-local wall time, so the natural loader call `idx.tz_convert('UTC')` is a **silent no-op**
that preserves the whole 2–3h error while being type-correct and passing mypy.

**Re-confirmed on the naive half, price-anchored, with a second metal.** LBMA Platinum PM (14:00
London) fitted to `XPTUSD_H1` (tz-naive), n=609 since 2024-01-01:

| bar label | sd all | summer | winter |
|---|---|---|---|
| 14 | 73.4 bps | 67.8 | 87.0 |
| **15** | **35.5** | **26.3** | **34.9** |
| 16 | 63.2 | 59.7 | 65.3 |
| 17 | 93.6 | 85.8 | 115.1 |

Bar 15 closes 16:00 server = 14:00 London in **both** seasons ⟹ server = London+2 = **EEST (UTC+3)
summer / EET (UTC+2) winter**. Independent of the gold evidence, on the opposite half of the lake.
**R0660 is now universe-wide.** The 08-26 fix as named
(`tz_localize(None).tz_localize('Europe/Athens').tz_convert('UTC')`) was checked against both
halves this run and is correct for both — I had expected it to raise on the naive index; it does
not.

**A correction to my own 08-26 note, because it matters for what counts as evidence.** That note
argued the offset from the *week boundary* ("Friday's last bar is 23 in both seasons ⟹ UTC+3/+2").
That argument does **not** hold. I tested every session edge across the 2025/2026 DST **mismatch
windows** — the ~3 weeks in March and ~1 week in Oct/Nov when the US and EU shift on different
dates, which is the only in-lake period that can separate a European clock from a US one:

- FX Friday-last label: **23 in every window, every year** (EURUSD, USDJPY, XAUUSD).
- US share CFD session: **first=16, last=22 on every single day**, straight through both windows.

Session boundaries are pinned to *server local time* and are therefore label-constant **by
construction** — true for any server offset, so they carry no information about which offset.
Only the **price-anchored** fits (gold on 08-26, platinum today) discriminate. A weekly US 08:30-ET
jobless-claims volatility beacon was also tried as a seam-dating instrument and is reported as
**non-discriminating**: n=27 and n=13 Thursdays in the mismatch windows, peak hours scattered
(h18/h10/h16), noise well above the 1-hour effect. **The exact DST seam dates remain UNMEASURED** —
that is a real answer, not a clean verdict (L1.28a).

### Item 3 — NEW FREE AXIS, adopted: LBMA **Platinum + Palladium** benchmarks (verified-clean)
Chasing card 39's per-round residual through the IBA/ICE page surfaced a press release that IBA now
operates the LBMA **Platinum and Palladium** Prices from 2026-07-01 — so I probed the free JSON host
for the new metals and they are there, keyless:
`https://prices.lbma.org.uk/json/{platinum_am,platinum_pm,palladium_am,palladium_pm}.json` —
**1990-04-02 → 2026-08-26**, n=9198/9129/9198/9132, **zero nulls in the USD leg**, fresh to T-1.
**XPTUSD and XPDUSD are both in the MT5 registry and both have H1 parquets** — 36 years of
point-in-time benchmark history for two already-traded symbols, at zero cost. Verified against the
desk's own tape (the table above), not merely opened.
**Failure mode worth the card on its own:** `/json/platinum.json` and `/json/palladium.json` both
**404** — only the `_am`/`_pm` suffixed files exist. A collector probing the bare metal name
records a live source as dead. Same silent-null class as the SGE GET-returns-zeros trap.

### Item 3 residual — per-round transparency: needs-monitoring, NOT destroyed-at-source (§38)
`gold_pm_rounds.json` / `auction_rounds.json` → 404. `theice.com/iba/lbma-gold-price` → 200 but the
only downloads are the Gold Auction *Specification* and the Gold/Silver *Factsheet* — methodology,
not data. `theice.com/iba/lbma-silver-price` → 404. **§13 boundary respected and recorded:**
`theice.com/robots.txt` disallows `/report-center/category/` and `/report-partial/`, so the
report-center category listing was **not** crawled; `/report-center` itself is permitted and is the
named next probe. Replacement hunt opened in the universe map.

### Item 2 — lake-vs-universe coverage: symbol gap CLOSED, residual moved to TIMEFRAME
Measured, not assumed: **197/197 registry symbols now have an H1 parquet; zero missing; zero orphan
parquet stems.** The 08-26 note's 24-symbol lake is superseded — that number was the *tz-aware*
subset, not the lake. The honest residual is depth, not breadth:

| timeframe | symbols |
|---|---|
| H1 | **197** |
| M15 | 4 |
| M5 | 1 |
| M1 | 1 |

Sub-hourly coverage is **~2%** of the universe. This is the JP-s6 finding recurring on MT5 ground:
candidates that prescribe M1–M15 cannot be tested on this lake. Recorded as the standing next
ground, not silently absorbed. Incidental: 64 symbols carry Sunday bars and 22 carry Saturday bars
(weekend-quoting CFDs) — any day-of-week or weekly-resample study must handle it explicitly.

**DEPTH:** item 2 exhausted (census over all 197 files, both axes, argmax + volatility profiles);
the clock item taken to **exhaustion and past it** — four instruments (LBMA gold, LBMA platinum,
session boundaries, US-anchored claims beacon), two of which I report as *non-discriminating*
rather than dressing them as confirmation, plus a correction to my own prior note; item 3 exhausted
on the free-host side (five endpoint probes, three ICE pages, robots read before crawling) with the
residual named and a replacement hunt opened. Depth is again what produced the find: a surface
adoption of the platinum JSON would have shipped it, and the tz census only happened because a
`TypeError` on a *different* symbol forced me to look at dtypes.

**NEXT UN-EXHAUSTED GROUND (next run):** (i) sub-hourly lake depth — which MT5 symbols can be
pulled at M15/M5/M1 and what the terminal actually retains, since ~2% coverage gates every
intraday candidate the desk has carded; (ii) `/report-center` permitted report ids for IBA
auction-results (card 39 residual); (iii) date the DST seams with a genuinely US-anchored
*price* instrument (CME metals/FX settlement times) rather than a volatility beacon — the one
thing this run could not measure.


---

## 2026-08-27 (session B) — FREE-DATA-ALTERNATIVES, standing daily run

**Backlog checked first (RESUME order):** `source_backlog_next.py --limit 6` → **68 catalogued, 42
resolved, 0 pending verification, 0 pending a legitimacy decision, 26 deferred** (next returns
2026-09-01). Nothing to verify; cataloguing is not the bottleneck this cycle, so this run goes to
the ground the 08-27 session-A note named.

**ITEMS TAKEN THIS RUN (bounded per the completion contract):**
1. **Sub-hourly lake depth** — named standing next ground: H1 covers 197/197 symbols but M15/M5/M1
   cover ~2%, which gates every intraday candidate the desk has carded. Measure what is actually
   retrievable, not what is stored.
2. **IBA `/report-center` permitted report ids** — card 39 residual (per-round LBMA auction data).
3. **Free sub-hourly FX/metals replacement hunt (§38)** — if the terminal cannot supply M1/M5
   depth, the exclusion spawns a hunt for a free primary source that can.

*(items resolved below as they close — never held in context)*

### Item 1 — sub-hourly gap: the cause is a HARDCODED TIMEFRAME, not terminal retention
The ~2% sub-hourly coverage was read last run as a lake-depth fact. It is a producer defect:
`desks/mt5/research/fetch_universe.py:54` calls `copy_rates_range(sym, mt5.TIMEFRAME_H1, ...)` — the
one producer that fills the lake for all 197 symbols is **hardcoded to H1**, so no amount of
terminal retention could ever have produced M15/M5/M1 breadth. Current census: **H1 221 files,
M15 8, M5 1, M1 1** (the sub-hourly six are XAUUSD, AUDCAD, AUDNZD, NZDCAD and duplicates). This
is the anti-hardcode class (LAWS §1, L1.61): a literal that silently caps exploration.
**What the terminal actually retains at M1/M5 is UNMEASURED from this box** — `MetaTrader5` does
not import here (`ModuleNotFoundError`) and there is no code-sync route to the Windows box. That is
a real answer, not a clean verdict (L1.28a). Routed to the ledger, not fixed here (research freeze).

### Item 3 — §38 replacement, ADOPTED: **Dukascopy tick datafeed** (verified-clean)
Because the terminal is unreachable and the producer is capped, the exclusion spawned its hunt.
`https://datafeed.dukascopy.com/datafeed/<SYM>/<YYYY>/<MM-1>/<DD>/<HH>h_ticks.bi5` — keyless, no
registration, **millisecond bid/ask ticks from ~2003 to T-1**, decodable with stdlib `lzma` +
`struct` (`>IIIff`). Probed live: EURUSD 200/28,952B (**5,626 ticks in one hour**), XAUUSD 200/
38,977B, USA500IDXUSD 200/4,085B — FX, metals and index CFDs all served. robots read **in full and
group-scoped** (KR-s5 lesson): the `*` group ends `Allow: /`, and the datafeed host serves no
robots of its own. This is a strictly better source than the terminal for the sub-hourly gap: tick,
not M1, and it needs no Windows box.
**Failure modes that would have silently corrupted a collector, all measured:** the URL **month is
ZERO-INDEXED** (January = `00`) — a 1-indexed collector pulls the wrong month and every derived
number still looks plausible; **throttling** returns 503/107B or resets the connection on the 2nd
request in a tight loop (stable at ~12–20s spacing — my first three-date batch reported all-dead
purely from pacing, the "records a live source as dead" class); symbol naming is Dukascopy's own,
not the MT5 registry's.

### THE FIND OF THE RUN — the broker clock follows **US** DST, and the offset is **not a constant**
Diffing Dukascopy (true UTC) against `EURUSD_H1.parquet` did not merely confirm the known offset —
it measured its **rule**. Method: decode a known-UTC tick hour, aggregate to OHLC, and let the
matching tape bar's index be the argmin. Discrimination is clean (best-vs-runner-up abs error
differs 10–20×), and the dates were chosen **inside the US/EU DST disagreement windows** so the two
rule-sets give different answers:

| true-UTC hour | DST state | measured tape offset | abs err (runner-up) |
|---|---|---|---|
| 2024-01-02 10:00 | both off | **+2h** | 0.00021 |
| **2024-03-20 10:00** | **US on, EU off** | **+3h** | 0.00021 |
| 2024-07-02 10:00 | both on | **+3h** | 0.00025 |
| 2024-10-25 10:00 | both on | **+3h** | 0.00023 |
| **2024-10-30 10:00** | **EU off, US on** | **+3h** | 0.00020 (+2h: 0.00264) |
| 2024-11-06 10:00 | both off | **+2h** | 0.00025 (+1h: 0.00450) |

**Both disagreement probes side with the US calendar.** The Fusion server clock is UTC+2/UTC+3
switching on the **2nd Sunday of March / 1st Sunday of November** — so the obvious guess,
`Europe/Athens` EET/EEST, is wrong for ~3 weeks each March and ~1 week each autumn.
Independent free corroboration from the tape alone: EURUSD carries **zero Sunday bars** and 447–449
Friday bars at hours 22 and 23 — impossible in real UTC (the FX week closes Friday 20:00–21:00 UTC),
exactly right for a server clock whose week ends Friday 23:59.

**This closes the residual the 08-26 and 08-27(A) notes both carried as UNMEASURED**, for free and
with no terminal — after session A's two volatility-beacon attempts were honestly reported as
non-discriminating. A price-anchored instrument was the right shape; Dukascopy supplied it.

**Honest scoping — I am not claiming a live bug.** `h1_source.py:195` already documents the offset
(measured 2026-08-26 by live tick), and I checked every caller of `broker_utc_offset_hours()`:
`scalp_shadow.py:83` and `shadow_forward.py:329` both compare a **live** clock to a **live** clock,
which is correct. The defect is **latent and specific**: the function returns ONE scalar from a
live tick, and `h1_source.py:292` publishes it in the `Bars` description for a history spanning
2018→now. **The offset is not constant.** Any consumer that converts *history* with that scalar is
wrong by exactly 1 hour for ~5 months a year, with the errors sitting precisely on the DST seams.
The correct object is a **function of timestamp**, and this run establishes the rule to write it.

### Item 2 — IBA per-round auction data: §13 WALL, family confirmed to exist
`theice.com/report-center` → 301 → `ice.com/report-center` (200, 108,449B). The page names an
**"ICE Benchmark Administration — LIBOR, ICE Swap Rate, LBMA Gold and Silver prices and treasuries"**
category and an **"Auction Historical Transparency reports"** family (single-day and multi-day). But
it is a client-side selector: the report ids load from routes under `/report-center/category/`,
which is **exactly what `theice.com/robots.txt` disallows**. Boundary respected, not circumvented.
Card 39's residual is upgraded from "endpoints 404" to "the family exists; its ids sit behind a
robots-barred route" — graded **UNVERIFIED**, not destroyed-at-source; the §38 hunt stays open.

**CROSS-SOURCE PAIR (joint value > either alone):** *Dukascopy ticks × the desk's own MT5 tape.*
Neither carries a clock verdict alone — the tape has no true-UTC anchor and Dukascopy has no
knowledge of the broker. Joined, the pair is a **point-in-time clock instrument for any past date**,
which is what turned a known scalar into a measured rule. It also generalises: the same diff prices
the desk's spread and fill quality against an independent venue on any historical hour.

**DEPTH:** item 1 → exhausted to the producer line that causes it (census → producer → `git`-visible
hardcode → every `broker_utc_offset_hours` caller read); item 3 → **exhausted and past it** (three
asset classes probed, binary format decoded and OHLC-verified against the desk tape, three silent-
corruption failure modes measured rather than guessed, robots read in full and group-scoped); the
clock question → **taken well past where I would have stopped**: a surface run would have stopped at
"+3h, confirms the known offset"; going one layer past produced the *seam rule*, and the two probes
that decide it were placed specifically where US and EU calendars disagree. Item 2 → exhausted on
the permitted surface, closed at a §13 wall with the wall's exact path named.
**Not breadth-theater:** 3 items, 1 adopted verified-clean source, 1 rule measured, 1 honest wall.

**NEXT UN-EXHAUSTED GROUND (next run):** (i) **Dukascopy symbol-map ← MT5 registry** — enumerate
Dukascopy's instrument list and map it onto all 197 registry symbols, so the sub-hourly gap can be
closed at tick resolution without the terminal; the unmapped residue is the honest gap. (ii) Extend
the clock probe **backwards to 2018** and forwards — a handful of cheap probes converts the measured
*rule* into a verified per-year seam table covering the whole tape. (iii) The §38 IBA replacement:
LBMA's own site and the auction operator's publications for per-round data on a permitted route.

### 65. [dig 2026-08-28] FX Blue track-record corpus — grade: **verified-clean** (3/3 accounts re-fetched live 2026-08-28, all 24 hourly cells identical; see ITEM 2 below, which also REFUTED H-20260828-006) — **CONVERTED — the ground's only consumer had been silently empty, and it now carries two preregistered hypotheses** [§33: wired tier:1 -> data/intelligence/hypotheses/H-20260828-006.yaml]
The 08-27 debt was "the corpus is a hypothesis SOURCE and has produced none yet". The reason was
not the corpus. `fxblue_mechanism_summary.py` read ONE file and filtered `status == "has_data"`;
the first-generation harvest labels the same records `live`, so the summariser printed
**`n=0 accounts` over 120 records** — and printed it as a result, not as an unreadable input. A
ground was graded barren because its reader could not see it. Repaired to read every wave,
de-dup by account, and re-derive liveness from the chart data rather than from a stored label.
- **Corpus now 293 records / 111 mineable**, wave-2 harvest (700 accounts) still running.
- **The retail MT5 flow clock, per-account normalised (n=107, uniform baseline 4.17%/hr):**
  15:00-17:00 UTC = 7.45 / 7.23 / 6.96% (~1.8x, the NY/London overlap); **00:00 = 5.84%**, the
  biggest hour outside the overlap while 22:00 (3.30%) and 01:00 (3.25%) sit at baseline —
  00:00 server time is the **swap boundary**, which is the desk's only repeat-survivor mechanism
  wearing an order-flow costume (L1.47).
- **Instrument mix:** EURUSD 51.4% of accounts, GBPUSD 42.3%, USDJPY 37.8%, AUDUSD 32.4%,
  XAUUSD 21.6%.
- **Preregistered:** `H-20260828-005` (overlap-hour flow absorption) and `H-20260828-006`
  (swap-boundary imbalance; Wednesday triple-swap as a SEPARATE arm so a 3x weekday effect
  cannot be laundered through a pooled average).
- **Bias discipline:** these are ACTIVITY-half cards. Survivorship selects which accounts stay
  visible; it does not invent the hour at which they trade. The PERFORMANCE half (61.3% of
  accounts profitable at 15:00 — z~2.4 across 24 hourly tests, not significant under Holm, and
  the accounts are not independent) is recorded as a pointer and is NOT the basis of either rule.

### 66. [dig 2026-08-28] A running miner writing into an ORPHANED INODE — silent, and a class not a bug [§33: wired tier:1 -> desks/mt5/data/intelligence/fxblue/track_records_wave3a.jsonl]
Found live, mid-dig. Both FX Blue harvesters logged row 50 while their output files held 28 rows;
the `shell`/`dead` counts matched exactly and only the large `has_data` records were missing.
`/proc/<pid>/fd/4 -> ...track_records_wave2a.jsonl (deleted)` — the file had been **unlinked and
replaced by a stale snapshot at 06:24** and both processes carried on appending to orphaned
inodes. **Nothing errored; a reader would have seen a clean, short, plausible file.**
- **Cause:** `desks/mt5/data/` is git-TRACKED, and this box's automation (`auto_push.sh` every 10
  minutes, the hourly cycle) checks files out from under long-running processes. Same launder
  class the desk has paid for repeatedly — new costume: it eats *live process output*, not commits.
- **Recovery route worth keeping:** a write-only fd is still readable through its `/proc` symlink,
  so `cat /proc/<pid>/fd/N` recovered every lost row (152 vs the 57 on disk) without stopping the
  run. That is the general rescue for any truncated-under-a-live-writer artifact.
- **Repair:** the miner appends to a staging file OUTSIDE the repo and publishes to the tracked
  artifact in one pass at the end — the window a checkout can eat shrinks to a single rename, and
  the staging file makes an interrupted run replayable.
- **RESIDUAL, explicitly not done:** every other long-running writer under `desks/mt5/data/` has
  the same failure available to it. That audit is owed, and until it runs the scope of this defect
  is UNMEASURED, not one file (L1.28a).

### 65b. [dig 2026-08-28, same run] FX Blue corpus 111 -> 525 mineable accounts: the CLOCK confirms out-of-sample, the PERFORMANCE half decays [§33: wired tier:1 -> desks/mt5/data/intelligence/fxblue/track_records_wave3a.jsonl]
Re-harvested 700 further accounts (stride 7, offsets 1 and 3) on the repaired writer path — a
positive control for card 66's fix as well as a corpus expansion: **700/700 rows landed, against
57/700 on the pre-fix path.** Corpus is now **887 records / 525 mineable**, and the wave-2/3
accounts are DIFFERENT accounts from the 111 that produced H-005/H-006, so this is an
out-of-sample read on both cards' premises.
- **The clock holds and sharpens** (per-account normalised, n=499, baseline 4.17%/hr):
  15:00-17:00 = **7.13 / 6.87 / 6.91%** (was 7.45 / 7.23 / 6.96 at n=107), and
  **00:00 = 6.59%, UP from 5.84%** — the swap-boundary spike is now the second-largest hour of
  the day and sits 1.58x baseline between neighbours at 3.54% (22:00) and 2.82% (01:00). A sharp,
  isolated, contract-mechanic-aligned spike that grew with the sample is the opposite of what a
  small-sample artifact does. **H-20260828-006 is the stronger of the two cards on this evidence.**
- **Instrument mix stable:** EURUSD 48.2%, GBPUSD 36.2%, USDJPY 28.2%, AUDUSD 24.8%,
  USDCHF 23.4%, XAUUSD 16.2% of live accounts.
- **THE SELF-CHECK THAT PAID:** the performance half's headline — "61.3% of accounts profitable
  at 15:00" (n=111) — **decays to 53.7% at n=525**, and 16:00 likewise 55.9% -> 54.1%. Neither
  rule was based on it, on the stated ground that it is survivorship-conditioned and that 24
  hourly tests do not survive Holm. Had it been the basis, this run would have been a promotion
  built on a number that lost half its excess to a 4.7x sample. Recorded because *refusing* a
  tempting number is only worth something if the desk checks later whether the refusal was right.
- **Cost paid, recorded (my error):** the first 700-account harvest ran on the pre-fix path; I
  recovered its orphaned inodes ONCE at row ~50 and not again, so when both processes exited the
  kernel freed ~500 harvested records that no longer exist anywhere. The re-run cost ~40 minutes
  of wall clock. The rule that follows: while a writer is known to be orphaned, re-recover on a
  timer, or restart it on the fixed path immediately — a single rescue is a snapshot, not a save.

---

## SESSION 2026-08-28 (free-data-alternatives miner, standing daily) — COMPLETE (3 items taken, 3 closed)

Items taken this run (bounded per completion contract; depth per item unbounded):
1. **BACKLOG VERIFY — [seed S21] BIS central-banker speeches full-text.** Carded 2026-08-28 by
   the frontier seat as "20,728 dated speeches in ONE request"; PENDING TECHNICAL VERIFICATION.
   Close it: open the exact URL, count rows, check date coverage + CB coverage (the card claims
   it closes the AUD and CHF gaps), read the licence, name the failure modes.
2. **BACKLOG VERIFY — FX Blue track-record corpus.** Carded by cards 65/65b/66 above; the corpus
   exists on disk but has never been verified as a SOURCE (licence, cadence, survivorship,
   schema drift, re-harvest reproducibility).
3. **SEARCH-SPACE EXPANSION (>=25% of run)** — one new source CLASS for the MT5 universe, chosen
   after items 1-2 resolve. Recorded below as it happens.

Status: note written before any searching. Findings appended in place as each item resolves.

### ITEM 1 RESOLVED — [seed S21] BIS central-bankers' speech corpus: **verified-clean as a ROUTE, restricted on LICENCE, and the wired consumer has a measured 2.5% attribution defect**

**Provenance (every URL opened this run, nothing claimed unread):**
`https://www.bis.org/robots.txt` (200, 24 lines) · `https://www.bis.org/cbspeeches/download.htm`
(200, the offer page) · `https://www.bis.org/terms_conditions.htm` (200, the licence) ·
`https://www.bis.org/speeches/speeches.zip` (200, **129,497,217 bytes**, `application/zip`,
one member `speeches.csv` at 389,624,169 bytes).

**COUNTS — independently reproduced, not taken from the carding seat.** 20,728 rows, fields
`url,title,description,date,text,author`. **Every row is dated and every row has a body** —
0 rows under 200 characters, median text length **15,955 chars**. Dates span
**1996-09-10 → 2026-06-xx**. The frontier seat's "20,728 dated speeches in ONE request" is
**CONFIRMED exactly**. `csv.field_size_limit` must be raised or the reader dies at row 1 —
the default 131,072 is smaller than a speech.

**AUD and CHF gaps: CONFIRMED CLOSED.** RBA 590 rows (latest 2026-06-04), SNB 445 rows
(latest 2026-06-18). Every one of the desk's eight majors is present: EUR 2,750 / USD 1,078 /
GBP 861 / JPY 826 / CAD 623 / AUD 590 / NZD 210 / CHF 445 by institution mention.

**FAILURE MODES — measured, not listed:**
1. **RIGHT-EDGE TRUNCATION, ~2 months, and it is stated at the source.** The download page reads
   *"Last updated on 1 Jul 2026"* and the corpus carries nothing after June 2026. Monthly 2026
   counts are 15 / 52 / 84 / 58 / 96 / 55 against a historical ~750-800/yr, so even the tail
   months are still back-filling. **A live consumer of this file has a two-month blind edge and
   a ragged one-month partial edge.** Cadence is periodic republication, NOT a feed.
2. **THE `date` FIELD IS DELIVERY DATE, NOT AVAILABILITY DATE — and the gap is now quantified.**
   The BIS review URL encodes its own publication date (`/review/r<YYMMDD><letter>.htm`), which
   parses for **10,222 of the 20,728 rows** and gives a free independent clock. Publication lag
   (pub − delivery): **median 4 days, p90 28 days, p99 87 days.** A backtest stamping tone at the
   speech date grants itself up to a month of hindsight at the 90th percentile. The builder's
   docstring warns a consumer to lag it; **nothing measures the lag, so nothing can size it** —
   this run does: **lag the series by 28 days for a p90-safe read, 4 days is the median and is
   NOT safe.**
3. **28 rows have dates that are provably wrong**, caught by the same URL cross-check: they are
   off-by-a-year typos (e.g. `r230407a.htm` dated 2024-05-07) plus **2 future-dated rows**
   (`r250710i.htm` dated 2027-07-09; `r260603d.htm` dated 2027-05-28). Small, but a future-dated
   row in a state series is a phantom that no downstream check would question.
4. **No duplicate URLs, no blank URLs** across all 20,728 rows.

**§13 LICENCE — the finding that matters, and it applies to a source the desk has ALREADY WIRED.**
The download page: *"Use of the content is allowed for noncommercial purposes."* The terms page,
verbatim: *"Users may download, display, print out, photocopy or redistribute any BIS Material for
non-commercial purposes."* **This desk is a commercial trading operation, so the grant does not
cover it.** The honest split, and it is not a dodge: copyright attaches to the speech TEXT, never
to the FACTS about it, and the desk's derived artifact is `(date, currency, hawk_count,
dove_count)` — facts, reconstructable from the central banks' own publications. So:
- **Corpus:** `desks/mt5/data/intelligence/central_banks/bis_speeches/speeches.zip` (129MB) is
  **already gitignored** (`.gitignore:229`) — verified — so the desk is not redistributing it.
  It is a local working copy, and that is the least-bad standing, not a clean one.
- **Grade: `restricted-licence`.** Derived facts retainable; the corpus is not a desk asset to
  redistribute, publish or rely on permanently.
- **§38 REPLACEMENT HUNT OPENED (an exclusion is half a deliverable):** the primary source is each
  central bank's own speech archive — the BIS is an aggregator, and the aggregation is the only
  thing that is BIS's. Fed material is US-Government public domain outright; ECB/BoE/BoJ/BoC/RBA/
  SNB/RBNZ each publish their own speeches under their own reuse terms. That route is per-bank
  crawling (which is what RBA's 403 killed on 2026-08-26) — **so the corpus is the cheap route and
  the CB sites are the licensed one, and the desk currently has the cheap one.** Carried to the
  universe map as an open replacement_hunt; not closed this run.

**A CONFIRMED DEFECT IN THE WIRED CONSUMER — venue contamination, 2.5% overall and 6.8% on GBP.**
`bis_speech_tone.py` attributes a speech to a currency by matching institution phrases against
`title + description`. But the BIS description format is
*"Speech by the <role> of the <SPEAKER'S BANK>, Mr X, **at the** <VENUE>"* — **and the venue is
usually also a central bank.** Measured over all 8,770 tone rows by splitting the description at
the venue marker: **8,555 attributed from the speaker segment (correct), 215 attributed ONLY from
the venue segment (wrong)** — 2.5%, and per-currency **GBP 55/812 = 6.8%**, USD 81/2,567 = 3.2%,
EUR 59/2,742 = 2.2%. The first row in the file is the archetype: *"Speech by the Deputy Governor
of the People's Bank of China, Mr. Chen Yuan, at the Bank of England Seminar"* → filed as **GBP**.
Also **154 rows match more than one bank** and are silently assigned to whichever key iterated
first. Only **700 of 8,770** rows were attributed from the title at all; 8,070 came from the
description, so the description parser is doing essentially all the work and it is unanchored.
- **THE EXACT PATCH (not applied — this seat is under the research-only freeze; routed to the
  inbox):** cut the description at the first of `" at the "` / `" at a "` / `" to the "` /
  `" before the "` and match institution phrases **only in the prefix**, falling back to the title.
  That is the same computation used to measure the defect, so its positive control already ran:
  it reproduces 8,555 correct attributions and rejects the 215.
- **A second, unrelated coverage gap in the same map:** `BANKS` holds the ECB alone for EUR, so
  **Bundesbank / Banque de France / other Eurosystem NCB governors — who vote — enter the EUR
  series only by venue accident.** Adding them is adding rows to a dict the module itself calls a
  seed, not a boundary.

**And the honest denominator:** 20,728 speeches in, **8,770 tone rows out — 58% of the corpus is
dropped** by the 9-institution map. That is by design (the desk trades eight currencies), but it
is the number to quote before anyone calls this corpus "fully mined".

**Grade: `needs-monitoring`** (route verified-clean; licence restricted; consumer defective).
**Backlog item S21: VERIFICATION CLOSED.**

### ITEM 2 RESOLVED — FX Blue track-record corpus: **verified-clean as a source (3/3 exact re-fetch), and the verification KILLED one of the two hypotheses it produced**

**Provenance:** `https://www.fxblue.com/robots.txt` (200, **68 bytes**, `User-Agent: *` /
`Allow: /` — fully open, no exclusions at all; the earlier "blocked" grading in the desk's notes
does not survive a direct read) · `https://api.fxblue.com/wl/charts/ch_hourtrades.aspx?id=<u>`
(200, keyless, ~2.85KB per chart).

**REPRODUCIBILITY — the verify-don't-trust test, and it PASSES cleanly.** Re-fetched three stored
accounts live (`0-lisa`, `1000pipsmonth`, `105901`) and diffed all 24 hourly cells against the
archived rows: **0 cells differing on 3/3 accounts**, totals 1,687 / 346 / 10,655 matching exactly.
The harvester is faithful to its source and the `addRows([...])` parse is correct. Corpus on disk:
**771 unique accounts carrying an hour chart**, 471 of them with ≥20 trades.

**AND THE VERIFICATION EARNED ITS COST — `H-20260828-006` (swap-boundary imbalance) is REFUTED at
its premise.** The card rested on "00:00 = 6.59% of trades, 1.58x baseline, and it GREW with
sample". Both halves fail a robustness test the original never ran (471 accounts, ≥20 trades,
per-account normalised, uniform baseline 4.17%/hr):

| hour | mean share | drop top-10 | drop top-25 | 10%-trimmed | median |
|---|---|---|---|---|---|
| **00:00** | 6.11% | **4.14%** | **2.80%** | 2.29% | **1.90%** |
| 15:00 | 7.38% | 6.87% | 6.49% | 6.82% | 6.85% |
| 16:00 | 7.12% | 6.68% | 6.29% | 6.65% | 6.70% |
| 01:00 | 2.83% | — | — | 2.08% | 1.96% |

**Dropping ten accounts sends 00:00 to the uniform baseline; dropping twenty-five sends it BELOW
it. The median 00:00 share (1.90%) is lower than 01:00 (1.96%) and 02:00 (1.94%).** The
overlap-hour peak survives the identical treatment untouched.

**The cause is a data defect, and it is nameable: 00:00 is this corpus's missing-timestamp dumping
bucket.** Of the accounts booking ≥99% of their trades into a SINGLE hour, **7 of 10 book it at
00:00** (one each at 09:00 / 22:00 / 23:00), and five sit at exactly **100.0%** —
`3962256`, `algotrader_v9-2`, `forex-kore-ea`, `frzfxblue`, `algotraderv9_1`. No account trades
every position in one hour; that is an unknown hour rendered as zero.

**THE LESSON, and it is the reusable half: "the effect GREW with the sample" is not evidence
against an artifact.** The prior run read 5.84% (n=107) → 6.59% (n=525) as out-of-sample
confirmation. But the contaminating class scales with n too, so a mean-of-shares statistic rises
with sample *because* of the artifact. Growth-with-sample only argues against an artifact once the
artifact class has been shown not to scale — and a mean over per-account shares gives a
20-trade account with a broken clock the same weight as a 10,655-trade account with a good one.
**Every per-account-normalised statistic on this desk needs a trimmed or median twin before it is
believed.**
- **Routed:** `H-20260828-006` marked `status: refuted_at_premise` in its own preregistration with
  the numbers (its stated kill condition — "the 00:00 concentration disappears" — fired).
  `H-20260828-005` is untouched and is now the **stronger** of the pair, having passed a
  robustness test its sibling failed.

**GENEALOGY / FAILURE MODES:**
- **Licence/§13:** robots fully open; the endpoint is keyless and public. The charts are numeric
  facts about public accounts. Grade **clean**; no ToS page exists at `/termsandconditions` (404).
- **Cadence:** live on request — accounts update continuously, so a harvest is a SNAPSHOT and
  `harvested_utc` is the only honest as-of stamp. There is no archive; re-harvesting later gives a
  different, longer record for the same account.
- **Survivorship (unchanged and still binding):** the population is accounts that chose to publish
  and still exist. Fine for ACTIVITY (when they trade), never for PERFORMANCE.
- **NEW failure mode, this run:** **hour-bucket contamination at 00:00** — unknown/zero timestamps
  render as midnight. Any hour-of-day statistic on this corpus must exclude single-hour accounts
  or use a trimmed statistic. **This is now a documented property of the source, not a surprise.**
- **Schema drift:** the chart payload is keyless `addRows([...])` positional data — a column
  reorder upstream would be silent. The stored `columns` header is the only guard and it should be
  asserted on every read, not just captured.

**Grade: `verified-clean` (source) / `needs-monitoring` (the 00:00 bucket).**
**Backlog item: VERIFICATION CLOSED.**

### ITEM 3 — SEARCH-SPACE EXPANSION, a NEW SOURCE CLASS for MT5 ground: **official-sector FX intervention operations** — and the official CSV under-reports by ~50%

**Why this is a new CLASS and not another site.** `data/data_universe_map.json` is ~90% the banned
crypto-exchange universe; its MT5-ground half holds price/venue sources and essentially no
**forced-participant, dated, sovereign flow**. This class is the purest forced counterparty the
desk can name: **a finance ministry selling USDJPY for policy reasons, in trillions, on a
published date, unable to stop and not trying to hide.** It is the mechanism test's ideal answer.

**Provenance — every URL opened:** `https://www.mof.go.jp/robots.txt` (**404 — no robots file**;
pages carry `meta robots index,follow`) · `.../international_policy/index.html` (200) ·
`.../reference/feio/index.html` (200) ·
`.../feio/foreign_exchange_intervention_operations.csv` (200, **43,477 bytes**, cp932) ·
`.../feio/quarter/index.html` (200, 18 quarterly releases linked) · 18 quarterly pages fetched ·
`.../feio/monthly/20260828e.html` (200, released **today**).

**VERIFIED CONTENT.** The headline CSV is a clean panel: **40 dated events, 1991-05-13 →
2026-04-30**, amount in ¥100m, with the operation **signed in words** (`the US dollar (sold) the
Japanese yen (bought)`) — direction is given, not inferred. Latest: **2026-04-30, ¥6,278.7bn,
USD sold / JPY bought.**

**THE FIND — THE OFFICIAL "HISTORICAL DATA" CSV SILENTLY DROPS HALF THE DAILY EVENTS.** Diffed the
CSV against the quarterly releases, which are the authoritative daily tables:

| year | quarterly releases | headline CSV | missing |
|---|---|---|---|
| 2024 | Apr 29, **May 1**, Jul 11, **Jul 12** | Apr 29, Jul 11 | **2 of 4** |
| 2026 | Apr 30, **May 4**, **May 6** | Apr 30 | **2 of 3** |

Amounts on the rows that ARE in both match to the yen (CSV `62,787`×¥100m = ¥6,278.7bn ✓), so this
is not a units or parse problem — **the obvious, well-formed, official, machine-readable file is
simply incomplete, and nothing on the page says so.** Anyone building this axis from the CSV (the
route any reasonable person takes) gets an event list missing the follow-up days — and the
follow-up day is precisely where a "does the sovereign come back tomorrow" study lives.
**The quarterly HTML releases are the source of truth; the CSV is a summary wearing a data
format.**

**Point-in-time structure, and it is a two-speed clock — this is the part that decides how the
axis may ever be used:**
- **Monthly release: the AGGREGATE only**, published ~2 days after a 27th-to-26th window (today's
  covers Jul 30 – Aug 26 and was released 2026-08-28). So *"did the MoF intervene at all last
  month, and for how much"* is knowable with a **~2-day lag** — this is what converts stealth
  intervention from rumour into fact.
- **Quarterly release: the DAILY breakdown**, ~40 days after quarter end (Q1-2023 released
  2023-05-10). So **which day** is not knowable for up to ~4 months.
- **A backtest that stamps a daily intervention at its trade date has granted itself up to four
  months of hindsight.** Same class as the BIS delivery-vs-availability gap in Item 1, and it is
  the failure this source will cause if anyone is careless with it.

**Absence is a MEASURED ZERO here, which is rare and worth saying.** Quarters with no event do not
omit a table — they state *"Total amount of foreign exchange intervention operations for the period
… : ¥ 0"*. Verified on 2023-Q1. The control periods are explicit, so this axis does not have the
WS-005 problem.

**FAILURE MODES:** (1) the CSV under-reporting above — **use the quarterly pages**; (2) cp932
encoding, bilingual header rows, Japanese-era years (`令和8年`) alongside Gregorian — the Gregorian
columns are present, use those; (3) **the four 2022 quarterly pages are linked from the official
index and return 404** — a broken official link, so 2022's events (incl. the 2022-10-24 stealth
operation) are reachable only via the CSV or the Japanese-side pages, un-cross-checkable; (4)
rounding is disclosed by the source ("figures … are rounded off, they do not necessarily add up").

**HONEST GRADING, and it is the part that stops this being a link dump: `n` KILLS IT AS A SLEEVE.**
Seven daily events on the cross-checkable panel; forty in thirty-five years. That is not a
tradable signal at any bar and I am not preregistering it as one — a candidate with n=7 cannot
reach the ten gates' sufficiency requirement and pretending otherwise would be padding. **What it
IS:** a **conditioning/state variable** — "the sovereign is active in USDJPY this month", known at
~2-day lag — and a clean **event-study control set** with explicit zeros. USDJPY is the desk's #3
instrument by retail exposure (28.2% of FX Blue accounts). Carded as a covariate axis, not a
sleeve.

**THE CLASS IS BIGGER THAN THIS MEMBER — the next ground, named as required.** SNB
(`https://www.snb.ch/robots.txt`, 200, **64 bytes, `User-agent: *` with NO Disallow — fully open**)
publishes **weekly sight-deposit balances**, the standard CHF intervention proxy, at weekly cadence
rather than quarterly — a materially higher-n member of the same class and the obvious next item.
Then Banxico, CNB, RBI, and BoJ's own daily operations. **Not opened this run; recorded as the
next un-exhausted ground so the chain holds.**

**Artifact written:** `data/mof_fx_intervention_daily.json` — the 7 cross-checked daily events with
units, lags, the CSV-under-reporting defect and the §13 grade recorded on the object itself.
**Grade: `verified-clean` (the quarterly route) / `needs-monitoring` (the headline CSV is known-
incomplete).**

### 67. [dig 2026-08-28] Japan MoF Foreign Exchange Intervention Operations — grade: **verified-clean** (quarterly route opened and cross-checked this run; the headline CSV is known-incomplete and is NOT the route) [§33: wired tier:2 -> data/mof_fx_intervention_daily.json]
Full detail in ITEM 3 above. NEW SOURCE CLASS on MT5 ground: official-sector forced-participant
flow. n=7 cross-checkable daily events kills it as a sleeve; carded as a conditioning/state axis.

### 68. [dig 2026-08-28] SNB weekly sight deposits (CHF intervention proxy) — grade: **verified-clean AS A SERIES / needs-monitoring AS A SIGNAL** (data opened, cadence and completeness verified, and diffed against three known intervention episodes this run — 2026-08-28 (b), see ITEM 1 below) [§33: screened tier:2 -> data/snb_sight_deposits_weekly.json]
Same class as card 67 and a materially higher-n member: WEEKLY cadence (n=784) against MoF's
quarterly daily-breakdown. **OPENED AND VERIFIED 2026-08-28 (b).** Route is keyless and open:
`https://data.snb.ch/api/cube/snbgwdchfsgw/data/csv/en`, §13 clean on BOTH hosts (`snb.ch` and
`data.snb.ch` each serve a single `User-agent: *` group with ZERO `Disallow` — group-scoped read,
the KR-s5 discipline). Series `TG` = total CHF sight deposits at the SNB, `GI` = domestic banks,
`UEB` = other. **The signal is contaminated by domestic emergency liquidity and the contamination
is not separable from the D0 split — that is the finding, and it is why the grade is split.**

---

## SESSION 2026-08-28 CLOSE — free-data-alternatives miner

**Items taken: 3. Items closed: 3.** No padding, no fourth item opened.

**Verified vs UNVERIFIED this run: 3 sources opened first-party and diffed against ground truth
(BIS corpus, FX Blue, MoF); 1 recorded UNVERIFIED and honestly labelled (SNB, robots read only).**

**BEST VENDOR-REPLACEMENT of the run:** the MoF quarterly releases replacing the MoF's own
headline CSV — a vendor-replacement where the "vendor" is the source's own convenience file.
Runner-up and the one with money behind it: **the BIS speech corpus is itself a replacement for
per-central-bank crawling, but its licence is noncommercial-only, so the replacement hunt runs the
other way — back to the individual central banks, who own the speeches BIS aggregates.**

**CROSS-SOURCE PAIR whose joint value exceeds either alone:** *MoF intervention dates × FX Blue
retail hour-of-day activity on USDJPY.* An intervention is a dated, signed, enormous forced order
in the desk's #3 instrument, and the FX Blue corpus says what retail was doing around it. Neither
alone is a sleeve — n=7 on one side, survivorship on the other — but the pair is a clean natural
experiment on who is on the other side of a sovereign. Recorded; not worked this run.

**NEW SOURCE CLASSES DISCOVERED: 1** — official-sector FX intervention and reserve operations
(members: MoF Japan verified; SNB sight deposits named; Banxico / CNB / RBI / BoJ daily operations
unopened). The desk's data universe map held ~90% banned crypto ground and no forced-participant
sovereign flow at all.

**DEPTH LINE (mandated):**
- *BIS corpus* — **EXHAUSTED for this item.** Not a surface touch: 20,728 rows parsed end to end;
  an independent clock built from the review-URL date stamp and used to measure a publication lag
  the source never states; the licence read to its verbatim clause; and the wired consumer's
  attribution measured row-by-row against the raw description text. **What depth surfaced that the
  surface did not:** the surface says "20,728 speeches, one request, gaps closed" — all true. Depth
  says the licence does not cover a commercial desk, 2.5% of the tone rows name the wrong currency,
  and the date field grants up to 87 days of hindsight.
- *FX Blue* — **reply-chain equivalent: re-fetched the live source and re-ran the desk's own
  statistic three ways.** Depth killed a preregistered hypothesis the surface had just promoted.
- *MoF* — **followed the chain past the CSV** to the quarterly index, then to all 18 quarterly
  releases, then into the zero-quarters to prove absence was a measured zero. **The CSV is the
  surface and it is wrong; the depth is two clicks further and nobody goes there.**
- **Honest self-assessment:** this run is NOT breadth-theater — 3 items, 3 exhausted, one
  preregistered hypothesis killed, one licence defect and one under-reporting defect found. It is
  also NOT full category coverage: the mandate's six categories are largely written for the banned
  crypto universe and I did not pretend to sweep them.

**THE BLUNT PART.** The desk's `data_universe_map.json` is a **crypto-exchange artifact** — of 93
prior source families, the overwhelming majority are Binance/Bybit/OKX/on-chain ground that the
2026-08-18 mandate permanently bars from being hunted. My own mission brief still orders six
categories that are almost entirely that banned universe (exchange dumps, on-chain reconstruction,
vendor-replacement for Glassnode/CryptoQuant/Coinglass). **I did not dig them, and I am not going
to pretend a run that swept them would have been worth anything.** The honest statement is that
**this seat's mandate has not been rewritten for the MT5 universe**, and until it is, "all 6
categories to exhaustion" is a coverage metric measured against a dead map. That is a defect in the
brief, not a licence for me to do less — so I spent the run on MT5 ground and opened a new class
there. **Recorded as owed: the free-data mission brief and the universe map both need an MT5
rewrite; three of my six categories currently point at ground no seat may legally hunt.**

**NEXT UN-EXHAUSTED GROUND (the chain holds):**
1. **SNB weekly sight deposits** (card 68) — open the data, verify the weekly series, grade it.
2. The rest of the official-sector-flow class: Banxico, CNB, RBI, BoJ daily operations.
3. **The BIS §38 replacement hunt** — per-central-bank speech archives under their own licences,
   starting with the Fed (US-Gov public domain, unambiguous) and SNB.
4. The audit card 66 left owed: every other long-running writer under `desks/mt5/data/` shares the
   orphaned-inode failure mode, and its scope is UNMEASURED.

---

## SESSION 2026-08-28 (b) — free-data-alternatives miner, standing daily run

**WRITE-FIRST NOTE (completion contract §1).** Items taken THIS RUN, resuming the chain the
08-28 (a) note left — no restart, no re-surface-scan of BIS/FX Blue/MoF:

1. **Card 68 — SNB weekly sight deposits (CHF intervention proxy).** Owed §33 disposition AND the
   backlog's pending-verification item. Open the data, verify the weekly series against ground
   truth, grade it, dispose the card *legally*.
2. **The §38 replacement hunt the BIS licence opened.** BIS speeches are noncommercial-only, so
   the corpus this desk wired cannot be used commercially. Hunt the PRIMARY sources BIS
   aggregates — individual central banks under their own licences, Fed first (US-Gov public
   domain).
3. **Official-sector-flow class expansion** (the new class opened in 08-28 (a)): Banxico / CNB /
   RBI / BoJ daily operations — the un-opened members named as next ground.

**DEFECT FOUND BEFORE ANY SEARCHING (recorded now so it survives a mid-run kill):** card 68's
disposition tag was written `[§33: deferred until 2026-08-30 -> ...]`. `_DISP_RE` in
`libs/research/mine_conversion.py` requires the date in PARENTHESES — `deferred(2026-08-30)` —
so the tag parsed as verb=`deferred`, until=`None`, i.e. **"deferred with NO date", an ILLEGAL
disposition**, and the card sat in the backlog owing a decision while reading to a human as
cleanly deferred. Third instance of the same class in this desk's memory ("§33 tags fail silently
in two grammar shapes"). Being fixed by DISPOSING the card properly this run, not by editing the
grammar to defer it again.

*(items resolve below as they close)*

### ITEM 1 RESOLVED — card 68, SNB weekly sight deposits: **the series is verified-clean; the SIGNAL is contaminated, and the contamination is not separable**

**Route (first-party, opened this run).** `https://data.snb.ch/api/cube/snbgwdchfsgw/data/csv/en` —
keyless, no auth, CSV. §13 read on BOTH hosts and group-scoped: `snb.ch/robots.txt` and
`data.snb.ch/robots.txt` each serve a single `User-agent: *` group with a `Sitemap:` line and
**zero `Disallow`**. Dimensions from `.../dimensions/en`: `GI` = sight deposits of domestic banks,
`UEB` = other CHF sight deposits, `TG` = total.

**POPULATION ENUMERATOR (the reusable find, worth more than the one cube).** `data.snb.ch/sitemap`
is a **1.9MB XML enumerating the entire portal — 416 distinct cube ids**. The SNB portal is
therefore fully enumerable keylessly and no future SNB question needs to guess a cube id again
(my first three guesses all 404'd; the sitemap answered it in one request). Same class as OP-098,
the Wayback CDX population enumerator — *the index is the find, not the series.*

**VERIFIED, not asserted:**
- **784 `TG` observations, 2011-08-19 → 2026-08-21. Every single one is a Friday; every spacing is
  exactly 7 days; ZERO missing weeks in 15 years.** This is the cleanest cadence the seat has
  measured.
- **Ground-truth diff against three known episodes — it reproduces all three with the correct sign
  and timing, without being told about them:**
  - 2011 EURCHF floor: **+52.4bn** in the week to 2011-08-26 — and note it **LEADS the 2011-09-06
    announcement by 11 days**. The balance sheet moved before the press release.
  - 2015 floor removal: **+26.2bn** week to 2015-01-23.
  - 2022–23 SNB FX *selling*: **−77.5bn** week to 2022-09-30, the largest move in the whole
    series, with the **correct negative sign**.

**THE FINDING, and it is why the grade is split.** The **second-largest positive move in the entire
series — +51.9bn in the week to 2023-03-24 — is NOT an FX intervention. It is Credit Suisse
emergency liquidity** (the UBS takeover was announced 2023-03-19; −31.3bn follows on 2023-04-07 as
it is repaid). A desk reading `TG` as a clean CHF-intervention proxy would have read the CS rescue
as a colossal CHF-selling intervention and taken the wrong side. **I checked whether the D0 split
rescues it: it does not — `GI` +40.5bn and `UEB` +11.3bn BOTH jump, so neither sub-series isolates
FX operations.** Domestic emergency liquidity and FX intervention enter the same number, and this
source cannot separate them.

**Genealogy / failure modes** (all in `data/snb_sight_deposits_weekly.json`): 87.8% of CSV rows are
**empty daily calendar scaffold** — a naive read-and-forward-fill manufactures a daily series that
does not exist; `PublishingDate` is a **portal-wide release stamp shared across cubes** (identical
value on `snbgwdmigirow` and `snbgwdzid`), not a per-observation stamp; **publication lag measured
ONCE (n=1)** at 3 calendar days (Friday data, Monday 10:00 CET release) — **stamped n=1, not
asserted as stable**, and the consumption rule is to take the Friday observation no earlier than
Monday 10:00 CET, because indexing it on its own Friday stamp grants hindsight (the exact defect
the BIS item found at up to 87 days); and `TG`/`UEB` start 2011 while `GI` starts 2009, so a joined
frame silently truncates 2.5 years.

**Grade: verified-clean AS A SERIES / needs-monitoring AS A SIGNAL.** Artifact:
`data/snb_sight_deposits_weekly.json`. Not pre-registered as a hypothesis — the contamination has
to be controlled for first, and 13 CHF instruments are in the live universe so the ground is real.

### ITEM 2 RESOLVED — the §38 replacement hunt the BIS licence forced: **the Fed's own index replaces the Board subset outright; the residual is 12 named sources, not a dead end**

**Why this was owed.** Session 08-28 (a) wired a 20,728-speech BIS corpus and then read the licence:
**noncommercial-only**, which does not cover this desk. §38 says an exclusion is half a deliverable —
so the replacement hunt goes to **the primary sources BIS aggregates**, since facts are not
copyrightable and the central banks own their own speeches.

**Found, first-party:** `https://www.federalreserve.gov/json/ne-speeches.json` — **the Fed serves
its ENTIRE speech index as one keyless 440KB JSON**: date, title, speaker, location, link.
**1,330 speeches, 2006-06 → 2026-08, 42 speaker strings.** Bodies extractable — probed
`cook20260805a.htm` and pulled **23,618 chars of clean prose**. The corpus is buildable end to end.

**Licence, stated as measured rather than as a certificate:** federalreserve.gov serves **NO
robots.txt** (404 HTML) and I found **no copyright notice** on the speech page, the About page, or
`/publications/copyright.htm` (404). That is an **absence of restriction** plus the 17 USC §105
US-Government posture — **it is not an explicit reuse grant, and I will not write one down as
though it were.** It is nonetheless materially freer than BIS's verbatim noncommercial-only clause,
which is the whole point of the hunt.

**COVERAGE DIFF (the actual §38 test, run rather than assumed).** BIS holds **2,567 "Fed" rows
(1996→2026)**; the Board's own index holds **1,330 (2006→)**. I chased where the gap lives:
- **1,976** BIS Fed rows are post-2006 vs the Board's 1,330 → **~646 unmatched**.
- Title-matching for regional banks found only 5 mentions, so titles do **not** explain it. The
  decisive test was the **speaker list: all 42 strings carry a Board title (Chairman / Chair /
  Vice Chair / Governor) and NOT ONE regional Reserve Bank president appears** — no Bullard, no
  Kashkari, no Williams, no Bostic, no Daly. **The route is Board-only, proven, not assumed.**
- **Residual, enumerable: ~646 post-2006 regional Reserve Bank speeches (12 banks, each with its
  own public site) + 591 pre-2006 rows predating this index.** The replacement is **PARTIAL and the
  residual is 12 named successor sources**, which is a finding, never a default.

**Failure modes worth the run on their own** (in `data/fed_board_speeches_index.json`):
- The JSON array's **last element is a metadata row** `{"updateDate": ...}` with no `d` key — a
  naive comprehension raises `KeyError`. **It did, on me, in this run.** Filter on key presence.
- **SPEAKER STRINGS ARE NOT NORMALISED and fragment one person across title changes.** **Jerome H.
  Powell appears under 4 distinct strings** (Governor / Chair / Chairman / Chair Pro Tempore),
  **Randal K. Quarles under 5**, and Bernanke / Yellen / Brainard / Kohn / Bowman / Barr / Clarida /
  Jefferson under 2 each — **10 speakers fragmented in total**. A speaker-fixed-effects or
  per-speaker tone panel grouping on the raw string **silently splits one speaker into several
  entities**, which is exactly how a hawkishness-drift study dies without an error. `"Chairman  Ben
  S. Bernanke"` additionally carries a **double space** as its own 2nd string.
- File is served with a **UTF-8 BOM** (`encoding='utf-8-sig'` required); dates are US `M/D/YYYY`.

**Grade: verified-clean.** Artifact: `data/fed_board_speeches_index.json` (index + fragmentation map
+ coverage diff). This does **not** retire the BIS corpus — it gives the desk a licence-clean route
for the largest single bank in it.

### 69. [dig 2026-08-28] Czech National Bank open API — official-sector-flow class member #3, and a free official CARRY series — grade: **verified-clean (forward points) / UNVERIFIED (open market operations)** [§33: screened tier:2 -> data/cnb_forward_points.json]

**Why the CNB and not the next country on a list.** Chosen from the **live universe registry, not
from my assumptions** (anti-hardcode): the 251-symbol universe was decomposed into its constituent
currencies and **CZK is in it**. The CNB then ranks first in the class on mechanism strength — it
ran an **explicit EURCZK 27.00 floor from 2013-11 to 2017-04**, the same forced-participant
mechanism as the SNB's EURCHF floor, and it publishes its open market operations daily.

**Route.** `https://api.cnb.cz/cnbapi/` — **keyless and SELF-DESCRIBING**: `.../api-docs` returns a
Swagger 2.0 spec enumerating **22 endpoints across 7 tags** (czeonia, exrates, forward, fxrates,
**omo**, pribor, skd). §13: `cnb.cz/robots.txt` is a single `*` group disallowing only
`/export/sites/nc/` and `/export/sites/pnu/` — the API and all data paths are permitted.
**The spec is the population enumerator here, exactly as the sitemap was for the SNB.**

**VERIFIED — FX forward points: 26,523 observations over 6,908 distinct dates, 1998-12-31 →
2026-08-28**, for `EUR_TO_CZK` and `USD_TO_CZK` at 3M and 6M. **27 years of free, official forward
points for an in-universe pair.** This lands on `carry` — **one of the 8 families the desk's own
book-breadth report lists as REACHABLE but ABSENT**, against a book that is 87% one family.

**THE FINDING — A SILENT SERVER-SIDE ROW CAP AT 10,000, and it is the desk's ranked lesson #4
reproduced on a brand-new source.** A single request for `dateFrom=2000-01-01&dateTo=2026-08-28`
returns **HTTP 200, no error, no truncation flag, and exactly 10,000 rows ending 2010-08-04**.
Every value in that truncated response is plausible and the series simply *stops* 16 years early.
The chunked pull (4-year windows, deduped on date×pair×maturity) returns 26,523 — so **the naive
single read silently loses 62% of the series.** Any derived carry statistic computed from the
one-shot call would be a confident number about 1998–2010 wearing a 2026 label.

**Other failure modes** (all in the artifact): **query params are NOT the response field names** —
the response says `ccyPair`/`validFor` but the query wants `currencyPair`/`dateFrom`/`dateTo`, and
guessing from the response schema returns HTTP 400 (it did, on me); **`lang=EN` does not localise
enum VALUES** on `/omo`, which returns `"Depozitní facilita"` and `"Stažení"` in Czech even under
`lang=EN`, so **a consumer filtering on English strings gets zero rows and reads it as "no
operations"** — the WS-005 shape, absence read as a clean verdict; `EUR_TO_CZK` has 6,369 dates vs
`USD_TO_CZK`'s 6,893, so a joined frame silently truncates; and these are forward **points**, not
outright rates.

**HONEST RESIDUAL, stamped UNVERIFIED rather than implied:** `/omo` was opened and confirmed rich —
full bid/allotment detail, marginal and average rates, 242KB for 2015 alone — but was **not pulled
in full and not diffed against the 2013–2017 floor episode this run.** That is the named next unit.
Adopting it today on the strength of one 200 would be exactly the "impressive and unverified" the
brief forbids.

### SESSION 2026-08-28 (b) — CLOSE

**Items taken: 3. Items closed: 3.** Plus one owed §33 disposition cleared and eight stale ones.
No fourth item opened, no padding.

**Categories covered / not covered — stated honestly rather than claimed.** The brief orders six
categories; **five of them (exchange-native dumps, on-chain reconstruction, non-English exchange
data, and vendor-replacement for Glassnode/CryptoQuant/Coinglass/Kaiko) are written for the
crypto-exchange universe the 2026-08-18 mandate permanently bars.** Session (a) recorded this as a
defect in the brief. **This run acted on it instead of recording it again:** the eight verified
crypto cards still sitting untagged in the §33 backlog were **disposed as `killed`** with the
mandate as the mechanism (`docs/graveyard.md` →
`crypto_exchange_universe_banned_2026_08_18`), which is the honest verb the backlog was missing —
they were never defective, they became out of scope. **The §33 backlog for this document is now 0
(was 9).** Category 4 (community/institutional data lakes) is the one category that transfers
intact, and all three items this run sit in it.

**Verified vs UNVERIFIED: 3 sources opened first-party and verified against ground truth (SNB,
Fed, CNB forward points); 1 residual explicitly stamped UNVERIFIED (CNB `/omo`) rather than
adopted on a 200.**

**BEST VENDOR-REPLACEMENT of the run:** the **Fed Board speech index** — a genuine §38 replacement
that removes a *licence* obstruction rather than a price one. The BIS corpus this desk wired last
session is noncommercial-only; the Fed's own index covers the largest bank in it, under a
materially freer posture, in a single keyless request. **The residual was measured, not waved at:
~646 post-2006 regional Reserve Bank speeches across 12 individually-public sites, plus 591
pre-2006 rows.**

**CROSS-SOURCE PAIRS whose joint value exceeds either alone:**
1. **SNB sight deposits × CNB open market operations.** Two central banks that ran *explicit
   currency floors* (EURCHF 1.20, EURCZK 27.00) and both publish the balance-sheet trace. Two
   independent realisations of one mechanism — a floor defence — is what turns an n=1 anecdote into
   something with a control. Neither alone survives a multiplicity correction; together they are a
   family.
2. **CNB forward points × CNB `/omo`.** Carry leg and intervention leg from the same institution on
   the same clock, which is exactly the join a vendor charges for.
3. Carried forward unworked from (a): MoF intervention dates × FX Blue retail hour-of-day.

**NEW SOURCE CLASSES: 0 new, 1 materially extended.** The official-sector-flow class opened in (a)
with one member now has **three verified members** (MoF / SNB / CNB) and a named unopened frontier
(Banxico, RBI, CBRT, MNB, NBP — all with in-universe currencies: MXN 4 pairs, TRY 3, HUF 6, PLN 4,
INR 1). A class with one member is an anecdote; with three it is a family worth a generator.

**DEPTH LINE (mandated, per lead):**
- **SNB — EXHAUSTED for this item.** Not a surface touch: robots read and **group-scoped on both
  hosts**; the portal's **entire 416-cube id space enumerated** from a 1.9MB sitemap after three
  guessed ids 404'd; cadence verified point-by-point (784/784 Fridays, zero missing weeks); and a
  ground-truth diff run against three known episodes. **What depth surfaced that the surface did
  not:** the surface is "weekly CHF intervention proxy, clean series, verified." Depth says **the
  second-largest positive move in the whole series is the Credit Suisse rescue, not an
  intervention — and the D0 split does not separate them.** A desk trading the surface reading
  takes the wrong side of the biggest CHF event of 2023.
- **Fed — EXHAUSTED as a route, residual enumerated.** Followed the chain past the index: probed
  the licence on three separate pages, extracted a full body to prove the corpus is buildable, and
  then **diffed coverage against the BIS corpus the desk already holds** — first by title
  (inconclusive, 5 hits) and then by **speaker list, which was decisive**. **What depth surfaced:**
  the index is **Board-only, proven not assumed**, and the speaker field **fragments Powell into 4
  entities and Quarles into 5** — a defect that would silently destroy any speaker-fixed-effects
  tone panel without ever raising an error.
- **CNB — forward points EXHAUSTED, `/omo` opened and honestly left UNVERIFIED.** Went past the
  first 200: pulled the **OpenAPI spec as the population enumerator** (22 endpoints), corrected my
  own parameter names off the spec after an HTTP 400, and then **chunk-pulled and deduped the full
  history**. **What depth surfaced that the surface did not — the single most valuable finding of
  the run:** the endpoint has a **silent 10,000-row server-side cap**. One request returns HTTP
  200, no flag, and a perfectly plausible series that **stops 16 years early and omits 62% of the
  data.** A one-shot read would have produced a confident carry statistic about 1998–2010 wearing
  a 2026 label. This is the desk's own ranked lesson #4 reproduced on brand-new ground.
- **Honest self-assessment: this is not breadth-theater** — 3 items, 3 closed, 3 first-party
  verifications, 3 distinct silent-failure modes found, 9 §33 dispositions cleared. It is also
  **not** six-category exhaustion, and I have said plainly why that metric is measured against a
  dead map.

**THE BLUNT PART.** Two of my three finds are **failure modes, not data** — the SNB contamination
and the CNB 10,000-row cap. That is the right ratio and I am not going to dress it up as three new
alphas. The CNB cap in particular is worth more than the forward series it hid: **the desk now has
a fourth independent instance of "HTTP 200 + plausible values + silent truncation"**, and every
history endpoint the desk reads in one shot should be assumed guilty until chunk-diffed. The
official-sector-flow class is genuinely promising — forced participants who publish — but **not one
of these three is a sleeve yet, and none was pre-registered**, because the SNB signal needs the
liquidity contamination controlled first and the CNB carry leg needs `/omo` verified to be worth
anything.

**NEXT UN-EXHAUSTED GROUND (the chain holds):**
1. **CNB `/omo` in full** — pull it chunked (the cap applies), and diff against the 2013-11 →
   2017-04 EURCZK floor. This is the owed half of card 69.
2. **The 12 regional Reserve Bank speech sites** — the enumerated §38 residual behind the Fed
   index, and the half of the BIS Fed subset that is still licence-blocked.
3. **Banxico / CBRT / RBI / MNB / NBP** — the remaining official-sector-flow frontier, ordered by
   in-universe pair count (HUF 6, MXN 4, PLN 4, TRY 3, INR 1).
4. Still owed from (a): the orphaned-inode failure mode's scope across every long-running writer
   under `desks/mt5/data/` is UNMEASURED.
