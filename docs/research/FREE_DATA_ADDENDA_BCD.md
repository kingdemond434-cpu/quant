# FREE-DATA ADDENDA B, C, D (principal, 2026-07-20 — APPEND-ONLY, canonical desk copy)
_Continuation of the free-data source campaign (items continue from 34; Addendum A lives in
the principal's records — its items 30-31 = the desk's verify-don't-trust + sustainability +
Bronze-archive rules in FREE_DATA_ALTERNATIVES_SPEC §§4-6, which BIND every source below
before pipeline use). Integrated into data_universe_map.json + search_operator_library.md
same day. AD-HOC SCANNING CLOSED per item 75 — future discovery routes through the standing
cadence (missions/diggers), never a fifth ad-hoc round._

## B1. HISTORICAL L2 / MICROSTRUCTURE — the hard target
35. **BitMEX public archive** (public.bitmex.com, AWS bucket): daily gzipped CSVs — full TRADE
    + top-of-book QUOTE history back to ~2014, free, no key; community scraper
    bmoscon/bitmex_historical_scraper. L1 not L2, but a DECADE of tick-grade bid/ask+trades
    from the venue that WAS the perp market 2016-2020: long-history microstructure features,
    funding-era studies, multi-cycle regime work.
36. **Databento free credits → CME crypto order book**: $125 signup credits, valid on ALL
    historical data incl. CME GLBX.MDP3 (BTC/MBT/ETH futures + options) from tick trades
    through MBP-10 (L2) to full MBO (L3), direct colo-feed sourced. The CME leg = basis
    trade / ETF hedging / institutional positioning at book granularity. CREDITS ARE
    ONE-TIME: surgical windows only (cascade days, CPI/FOMC, expiry weeks), never bulk.
    NEEDS PRINCIPAL SIGNUP — page when a pull is planned.
37. **dYdX v4 via Numia**: public BigQuery tables (mempool-level txs, hourly subaccount
    equity/positions), free within BQ quota. Honest: complete FILLS+positions+state; live
    book sits in validator memory → order placements forward-recordable only.
38. **Academic companion windows**: published crypto LOB windows (Bybit ~200-300ms snapshot
    sets, Binance event datasets), LOBSTER free equity samples. Fragmentary (days-weeks):
    pipeline validation + prototyping ONLY, never continuous history. Zenodo/arXiv companion
    repos = standing Prospector hunting ground.
39. **CryptoDataDownload — upgraded**: now ships free ORDER-BOOK CSVs alongside OHLCV/trades,
    25+ exchanges, daily refresh, no login. Verify per-venue granularity before reliance.
40. **Alpaca crypto data** (free w/ account): historical + realtime trades/quotes/bars,
    US-aggregated; L1 convenience + recorder quote-stream redundancy. Needs signup.

## B2. UNEXPLORED CLASSES
41. **Spot-ETF flow tables**: Farside Investors daily BTC/ETH creation/redemption per fund
    since launch (+ SoSoValue cross-check). Post-2024 marginal flow driver. Tables get
    REVISED — snapshot to Bronze.
42. **GDELT**: full-history 15-min global news events, free (BigQuery public). EVENT-TIMESTAMP
    source for unscheduled-news drift. Massive+noisy: event times, not sentiment truth.
43. **Google Trends via pytrends**: retail-attention proxy (documented in literature).
    Relative-normalized + sampled: fixed schedule, fixed term sets, archive raw pulls
    immutably or the series is incomparable over time.
44. **Exchange announcement/listing calendars**: Binance/Bybit/OKX announcement pages
    (RSS/API-scrapeable) — listing/delisting/contract-change events with timestamps; own
    Bronze archive = timestamp integrity layer.
45. **Kraken CSV dumps** (full-history OHLCVT, quarterly refresh) + **standing prospecting
    grounds**: GitHub topics orderbook-tick-data / historical-data as RECURRING Prospector
    sweeps, not one-time sources.

## B3. VERDICT
46. **Residual truth (sharpened)**: continuous pre-recorder Binance perp L2 diffs do not
    exist free (mostly not paid either). Free approximation basket: bookDepth snapshots +
    BitMEX L1-since-2014 + CME MBO/MBP via credits + Bybit archive + Hyperliquid full
    history + CryptoHFTData + academic windows — EXCEEDS requirements for every live card
    and watchlist item. Full L2 diffs matter mainly for queue-position games already ruled
    structurally disadvantaged for this desk. The remaining gap is in a game we chose not
    to play.

## C1. SOCIAL / COMMUNITY CORPORA
48. **Reddit full-history corpus**: Watchful1 Academic Torrents dumps (2005-2025 per-subreddit
    zstd NDJSON, monthly increments); Arctic Shift (Pushshift successor: API + bulk +
    HuggingFace Parquet); PullPush keyword search. Uses: attention/sentiment, event studies,
    retail-mania regime markers. HONEST: weak-signal class, crowded — Weak Signal Registry
    material + regime context, never primary edge.
49. **Crypto-native social firehoses** (forward-collect): Farcaster hubs (full graph),
    Bluesky firehose, Telegram public channels (Telethon), Bitcointalk archives (ANN threads
    = token-launch event history to 2009), 4chan /biz/ archives, HackerNews full history
    (API + BigQuery), Alternative.me Fear&Greed (formalized as weak proxy). Per-platform ToS:
    personal research, no redistribution; sustainability rule applies.

## C2. MEV / MEMPOOL / NETWORK MICROSTRUCTURE (data-moat class)
50. **Flashbots Mempool Dumpster**: free daily Parquet/CSV mempool archives (multi-provider),
    CC-0, + BigQuery/Dune. CLOSES the historical-mempool gap at $0: first-seen→inclusion
    latency, congestion, private-flow share.
51. **ethPandaOps Xatu**: public Parquet — mempool first-seen, beacon events, MEV relay
    events, canonical chain from genesis; mainnet events from 2023-03. Foundation-funded.
52. **MEV classification layers**: zeromev per-tx classification (sandwich/toxic/liquidation +
    user loss, explorer+API); EigenPhi + Flashbots dashboards as cross-checks. Honest:
    ETH-centric — CONTEXT/toxicity-regime features for a CEX-perp desk, self-computed moat
    class.

## C3. POSITIONING & FLOW TRANSPARENCY
53. **Binance Vision metrics — already in hand**: the daily futures metrics files carry
    top-trader long/short account AND position ratios + taker buy/sell ratio columns — name
    them explicitly in the feature factory so they are never rediscovered.
54. **Hyperliquid full position transparency** (unique): every account's positions public by
    design (info API by wallet, leaderboards, daily account snapshots). Most complete free
    positioning dataset in crypto: whale-flow, crowding, copy-flow studies.
55. **Exchange leaderboards & copy-trading feeds** (Binance/Bybit/OKX/Bitget, scrapeable,
    community repos exist): documented, DECAYING-edge class — forward-collect to Bronze.
56. **Bitfinex margin long/short** (public API): oldest free positioning series in crypto
    (decade+), niche venue.

## C4. PREDICTION MARKETS
57. **Polymarket + Kalshi free APIs**: real-money event odds (Fed, CPI ranges, elections,
    crypto price events) → prior-probability features for post-macro-print drift + regime
    conditioning; the market-implied surprise measure no free macro calendar carries.

## C5. CROSS-ASSET FREE LAYER
58. **Traditional-market free history**: Stooq full-history CSVs (indices/FX/DXY/commodities),
    yfinance convenience, CBOE historical VIX CSVs, US Treasury yield-curve API, CME delayed
    CVOL. The entire risk-on/off + rates-sensitivity feature layer at $0.

## C6. QUANT-KNOWLEDGE MINES (hypothesis fuel → Prospector)
59. **Competition archives**: Kaggle G-Research Crypto Forecasting winning solutions
    (crypto-specific feature/validation craft), Jane Street/Optiver comps, Numerai
    forum/docs, Quantiacs public contest algos.
60. **Archived community knowledge**: Quantopian archive (lectures + algos on GitHub), Quant
    Finance StackExchange full dumps (offline-queryable), QuantConnect forums, Wilmott.
61. **Free institutional research streams**: BitMEX Research (microstructure-grade), Kaiko/
    Glassnode/CoinMetrics free weeklies (ALSO a crowding tell — what free research
    popularizes is what crowds), Binance/Galaxy Research, arXiv q-fin + SSRN feeds, AQR/Man.
62. **Japanese botter ecosystem (anti-consensus gem)**: richmanbtc mlbot_tutorial (original
    techniques: richman non-stationarity score, p-mean evaluation) + crypto_data_fetcher +
    note.com/btcml series + book; the wider note.com botter community publishes code-included
    strategies largely untranslated — the language barrier IS the moat, LLM translation
    removes it for us not the crowd. Next such grounds: JoinQuant/myquant CN BBSs.

## C7. HONEST GRADING (64)
Social/sentiment: weak-signal, crowded → registry. MEV/mempool: context/toxicity, ETH-centric
→ moat data, indirect. Positioning/leaderboards: documented decaying edges → forward-collect,
short half-lives expected. Knowledge mines: hypothesis fuel, not data — everything still
enters via economic-prior gate + gauntlet. Items 30-31 rules apply to every source.

## D1. FUNDAMENTAL / FACTOR LAYERS
65. **Developer-activity factor — self-computed (best find of round D)**: GH Archive (complete
    GitHub event history, BigQuery public) JOIN electric-capital/crypto-ecosystems (asset→repo
    taxonomy) = cross-sectional developer-activity factor (commits, contributors, dev
    momentum) across the entire perp universe. Documented in literature, owned methodology,
    $0 — nobody sells this cheaper than free.
66. **Wikipedia pageviews API**: per-article daily views, official+free; attention factor,
    cleaner + longer-history than Trends' normalized index. Bronze the raw pulls.
67. **Fed liquidity plumbing**: NY Fed markets API (RRP, SOMA), Treasury FiscalData (TGA
    daily), H.4.1 via FRED — compute the net-liquidity series ourselves, canonical + daily.

## D2. SOLANA LAYER
68. **Old Faithful**: Solana-Foundation-sponsored full-ledger archive from genesis (CAR files
    per epoch, files.old-faithful.net, Jetstreamer backfill). SCALE CAVEAT: hundreds of TB —
    program-filtered slices ONLY (OpenBook/DEX + perp protocols → reconstructable on-chain
    book/perp events). BigQuery Solana public dataset + Dune for light queries; Jito for MEV.

## D3. OPTIONS / VOL FLOW
69. **Institutional block flow via the Deribit public tape**: Paradigm-negotiated blocks print
    on Deribit's PUBLIC tape flagged as block trades → institutional options flow capturable
    free by filtering block prints; Paradigm's research blog documents methodology. Free vol
    cross-checks: Volmex/BitVol/T3.

## D4. EVENT / NEWS + VENUE-STRESS
70. **CryptoPanic free API**: crypto-headline event times + community votes; simpler than
    GDELT for coin-level event studies.
71. **Venue-stress observables** (Seat-5, free): insurance-fund balance endpoints (Bybit/
    Binance/Deribit), proof-of-reserves pages (snapshot to Bronze — they change silently),
    status-page JSON APIs (machine-readable incident histories). A free venue-health series
    for counterparty monitoring + failover research.
72. **Airdrop/claim calendars** (CryptoRank, airdrops.io): unlock-adjacent scheduled
    sell-pressure events; same event-study pipeline as unlocks.

## D5. FILLERS + TAIL
73. Minor: Nasdaq Data Link free BCHAIN series; Hashrate Index free charts (hashprice/miner
    economics — capitulation regime context).
75. **THE TAIL DECLARATION**: four rounds in, marginal LISTING hour < marginal INGESTING hour.
    Ad-hoc scanning COMPLETE TO THE TAIL. Ongoing discovery is institutionalized (Prospector
    sweeps, event triggers, free-first mandatory scans, standing grounds 45/38/62). Future
    "find more sources" requests route to the STANDING PROCESS — this is the handoff the
    system was built to make.
