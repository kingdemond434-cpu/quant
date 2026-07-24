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

### 1. Upbit Historical Market Data portal — grade: needs-monitoring
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

### 3. bitFlyer getexecutions + self-recorded candles — grade: needs-monitoring
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

### 4. Bithumb (spot + futures) — grade: UNVERIFIED
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

### 6. Tardis vendor-replacement — grade: needs-monitoring (forward) / destroyed-at-source (backfill)
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

### 7. Glassnode / CryptoQuant vendor-replacement — grade: UNVERIFIED
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

### 8. Kaiko vendor-replacement — grade: needs-monitoring (raw ticks) / destroyed-at-source (index methodology)
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

### 9. Stablecoin mint/burn self-computation — grade: needs-monitoring
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

### 11. eth-labels (dawsbot/eth-labels) — grade: needs-monitoring
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

### 12. cex-list (tradezon/cex-list) — grade: UNVERIFIED
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

### 21. NAVER DataLab (Korean search-attention) — grade: needs-monitoring (built, unrun)
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
