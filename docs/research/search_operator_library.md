# SEARCH OPERATOR LIBRARY — canonical, versioned (git), single source of truth
_Charter §15/§16. Every digger DRAWS from this at session start and CONTRIBUTES back before
session end. Operators scored on VALIDATED information gain. Retired entries move to the
ARCHIVE section — never deleted. Pointered from data/data_universe_map.json._

## Entry schema
```
### OP-<nnn> <short name>                        [status: active|watch|archived]
class: operator | query-template | multilingual-pattern | citation-follow | repo-discovery |
       source-expansion | community-discovery | verification | reconstruction | cadence-mechanism
origin: <digger + date>            validated-gain: <evidence one-liner>
technique: <the actual operator/method, copy-runnable>
adaptations: CN=<...> RU=<...> KR=<...> JP=<...> AR=<...> PT=<...> (or "blocked: <reason+condition>")
counterfactual: <would this class of find surface anyway? low/med/high>
```
Blocked adaptations are reviewed by the Discovery Bottleneck Detector duty each cycle.

## ACTIVE — seeded 2026-07-19 (consolidated from FREE_DATA_ALTERNATIVES_SPEC §8 Query
## Evolution, the Chinese Quant Expansion package, and the Prospector Source Universe)

### OP-001 GitHub-maximal dig chain                                [active]
class: repo-discovery
origin: Digging Charter §2 (2026-07-18)   validated-gain: primary source of every expansion package's finds
technique: repo -> README -> Issues + Discussions -> forks (diverged forks especially) -> contributor
  profiles -> their OTHER repos + starred lists -> org members. Always >=2 levels deep.
adaptations: CN=Gitee same chain + Gitee Explore trending; RU=GitHub RU-language READMEs via
  lang:ru search + habr.com linked repos; KR=GitHub KR + velog/tistory linked repos; JP=GitHub JP +
  Qiita/Zenn linked repos; AR/PT=GitHub topic search in local language terms.

### OP-002 Native-language quant query templates                   [active]
class: multilingual-pattern
origin: Free-data mission + CN expansion (2026-07-18/19)   validated-gain: CJK finds English-only search never surfaced
technique: search the CONCEPT in the local language, not transliterated English. Templates:
  CN (Baidu/Zhihu/Xueqiu): "量化交易 数据 免费" / "资金费率 套利" / "网格 回测 框架"
  RU (Yandex/habr): "квант трейдинг открытые данные" / "фандинг арбитраж крипто"
  KR (Naver/DCInside): "퀀트 트레이딩 오픈소스" / "펀딩비 차익거래"
  JP (Yahoo!JP/Qiita): "クオンツ 仮想通貨 データセット" / "資金調達率 裁定"
  AR (Google.ae forums): "تداول كمي بيانات مجانية"
  PT-BR (Google.com.br): "trading quantitativo dados gratuitos criptomoedas"
adaptations: native per-region by construction; new regions seed their row on first session.

### OP-003 Comment/reply-layer mining                              [active]
class: community-discovery
origin: Charter §9 (2026-07-18)   validated-gain: mechanism/refinement/debunking found 2-3 replies deep
technique: read FULL threads >=2 levels; the best comment can outrank the OP; harvest debunking
  replies as free graveyard entries (pre-emptive falsification).
adaptations: CN=Zhihu answers + comment chains, Xueqiu comments; RU=habr comments, smart-lab
  forums; KR=Naver cafe threads; JP=5ch finance boards + Qiita comments; ALL=YouTube/Reddit/X replies.

### OP-004 Citation-chain follow (2-level)                         [active]
class: citation-follow
origin: Literature Deep-Miner spec (2026-07-17)   validated-gain: replication-scan layer of LITERATURE_SPEC
technique: paper -> its citations + who-cites-it (Semantic Scholar/Google Scholar) -> repeat once;
  prioritize FAILED replications and critique papers.
adaptations: CN=CNKI-indexed open-access via Google Scholar CN titles (never CNKI mirrors — §13);
  RU=cyberleninka.ru open archive; JP/KR=J-STAGE / KISS open tiers; ALL subject to §13 gate.

### OP-005 Vendor-replacement reconstruction                       [active]
class: reconstruction
origin: Free-data mission (2026-07-18)   validated-gain: replaced ~$1.5k/mo paid basket at $0
technique: identify the FREE raw a vendor repackages (exchange dumps, on-chain, official S3);
  rebuild the metric with owned methodology; diff vs ground-truth sample before trusting.
adaptations: region-equivalent = regional exchanges' native dump/archive endpoints (see universe map).

### OP-006 Exchange-native archive hunt                            [active]
class: source-expansion
origin: Free-data mission (2026-07-18)   validated-gain: source-of-truth-first finds (data.binance.vision class)
technique: for each venue: /data subdomain, S3 buckets, "historical data" docs page, GitHub org
  sample repos, status/changelog pages for deprecation notices.
adaptations: CN=OKX/Bybit/Gate CN-language doc trees; KR=Upbit/Bithumb dev portals; JP=bitFlyer/
  Coincheck APIs; RU=regional venue docs; each miner owns its region's venue list.

### OP-007 Ex-employee / insider long-form layer                   [active]
class: community-discovery
origin: Prospector source universe (2026-07-17)   validated-gain: anti-consensus priority class, hand-picked cap slot
technique: podcasts (Chat With Traders class), ex-quant blogs/Substacks, conference talk Q&A,
  post-mortem writeups; mine for MECHANISMS not stories.
adaptations: CN=Bilibili quant lectures + Xueqiu columns; RU=habr long-reads + YouTube RU;
  KR=Naver blogs; JP=note.com finance writers; PT=YouTube BR fintwit.

### OP-008 Verify-don't-trust data diff                            [active]
class: verification
origin: Free-data mission §4 (2026-07-18)   validated-gain: blocks the silent-zero-data + fabrication classes
technique: before ANY pipeline relies on a free source, diff a sample vs ground truth
  (exchange-native / Tardis free sample); check row counts, gaps, timezone, unit scale.
adaptations: universal verbatim — no language dependence (log n/a-with-reason per §16).

### OP-009 public.<venue>.com bucket probing                      [active]
class: source-expansion
origin: principal addenda B (2026-07-20)   validated-gain: BitMEX decade archive, Bybit, data.binance.vision all fit the pattern
technique: probe public data buckets on any venue: public.<venue>.com, data.<venue>.com/.vision, <venue> S3 listing.
adaptations: universal per venue; regional miners probe their region's venues (Upbit/Bithumb/bitFlyer/OKX/Gate).

### OP-010 vendor-docs-as-map                                     [active]
class: source-expansion
origin: principal addenda B   validated-gain: Tardis per-exchange docs = free INDEX of what exists per venue
technique: read a paid vendor's per-exchange documentation as a catalog, then source each item free.
adaptations: CN=Wind/Tushare doc trees; JP/KR=local vendor catalogs; universal.

### OP-011 scraper-repo-as-evidence                               [active]
class: repo-discovery
origin: principal addenda B   validated-gain: bmoscon scraper proved BitMEX bucket exists
technique: a GitHub scraper existing for a venue proves a hidden public source exists -- find the scraper, find the bucket.
adaptations: Gitee scrapers for CN venues; universal.

### OP-012 vendor free credits -> surgical institutional pulls    [active]
class: reconstruction
origin: principal addenda B   validated-gain: Databento $125 -> CME MBO/MBP windows
technique: search "<vendor> free credits <asset>"; spend one-time credits on highest-value windows only.
adaptations: universal; log every credit spend to ledger (one-time resource).

### OP-013 BigQuery public dataset <protocol>                     [active]
class: source-expansion
origin: principal addenda B   validated-gain: dYdX/Numia, Solana, GDELT, HN, GH Archive all live there
technique: protocol ecosystems fund public BQ indexing grants; the tables outlive announcements.
adaptations: universal; CN equivalent = MaxCompute public sets (probe).

### OP-014 successor-project search                               [active]
class: community-discovery
origin: principal addenda C   validated-gain: Pushshift -> Arctic Shift/Academic Torrents
technique: famous dead tool -> search its community successor before declaring the data lost.
adaptations: universal; RU/CN forums often mirror dead-tool archives.

### OP-015 foundation-funded open data                            [active]
class: source-expansion
origin: principal addenda C+D   validated-gain: EF->Xatu, Flashbots->Mempool Dumpster, Solana->Old Faithful, dYdX->Numia
technique: search "<foundation> open dataset grant" / "<foundation> historical archive project" FIRST when a chain matters.
adaptations: universal per-chain.

### OP-016 CC-0 / public-domain license filter                    [active]
class: query-template
origin: principal addenda C   validated-gain: narrows to the genuinely free + redistribution-safe
technique: add "CC-0" / "public domain" / license:cc0 to dataset searches.
adaptations: universal; strengthens charter s13 compliance.

### OP-017 translate-the-niche                                    [active]
class: multilingual-pattern
origin: principal addenda C   validated-gain: JP botter ecosystem (richmanbtc et al) -- language barrier IS the moat
technique: LLM-translate non-English practitioner communities the English crowd never reads; prioritize code-included writeups.
adaptations: JP=note.com botters; CN=JoinQuant/myquant BBSs; KR=Naver blogs; RU=habr/smart-lab -- each miner owns its ground.

### OP-018 competition post-mortems as literature                 [active]
class: community-discovery
origin: principal addenda C   validated-gain: Kaggle G-Research winners = applied crypto research with skin in the game
technique: mine winning-solution threads of quant competitions as validated applied methods.
adaptations: universal; CN=Tianchi comps; JP=SIGNATE.

### OP-019 Wayback CDX API reconstruction                         [active]
class: reconstruction
origin: principal addenda D   validated-gain: deleted announcements/leaderboards/fee schedules recoverable
technique: programmatic Wayback CDX queries -- data that no longer exists live often exists in the archive.
adaptations: universal; RU/CN archives: archive.today mirrors.

### OP-020 SMF `action=printpage` whole-thread extraction          [active]
class: operator
origin: EN frontier miner (2026-07-25)   validated-gain: pulled a 301-post Bitcointalk thread in ONE
  request; 48-post thread = 42KB via printpage vs 121KB for the FIRST 20-post page of the themed view
technique: SMF-powered forums expose a printer-friendly view that returns the ENTIRE topic, all pages,
  in one clean minimal-HTML request with no theme markup, no sidebars, no pagination:
    https://<forum>/index.php?action=printpage;topic=<id>.0
  Parse with: `Post by: <b>AUTHOR</b> on <b>DATE</b> <hr /> <div style="margin: 0 5ex;">BODY</div>`.
  Cuts request count by ~Npages and bytes-per-post by ~5-8x. Public endpoint, no auth, robots-noindex
  (so it is ALSO content Google never indexed -- anti-consensus by construction).
adaptations: universal to any SMF forum (Bitcointalk + a large share of legacy crypto//regional boards).
  phpBB equivalent = `viewtopic.php?t=<id>&view=print`; vBulletin = `printthread.php?t=<id>`;
  Discourse = `/t/<slug>/<id>.json` (full topic JSON). CN/RU/KR/JP legacy boards are mostly phpBB/Discuz
  -- Discuz equivalent = `forum.php?mod=viewthread&tid=<id>&_dsign=` (no print view; use `archiver/?tid-<id>.html`).
counterfactual: LOW -- nobody digs legacy forums at scale because the themed view is expensive to crawl;
  this operator is what makes era-archaeology cheap enough to actually exhaust.

### OP-021 board-tail pagination as era-seek                       [active]
class: operator
origin: EN frontier miner (2026-07-25)   validated-gain: located Bitcointalk's 2011-2014 era EXACTLY
  (board 8 offsets 14480-18640) and turned "dig the founding era" into a bounded 103-page crawl
technique: legacy forums list topics NEWEST-FIRST, so the founding era sits at the MAXIMUM page offset --
  not reachable by search, only by pagination. (1) Read the board index for the max offset link
  (`board=<n>.<maxoff>`) = board size. (2) Binary-probe ~8 offsets, reading each page's last-post dates,
  to build an offset->date map. (3) Crawl ONLY the offset window covering your target era.
  This converts an unbounded "search the archive" job into a FINITE, exhaustible, countable crawl --
  which is what lets a dead-forum ground be honestly marked EXHAUSTED.
  Measured: Bitcointalk board 8 (Trading Discussion) = 18,640 topics, 2011-2014 era = offsets
  14480-18640; board 78 (Securities) = 2,376 topics TOTAL (whole board is era material, fully finite).
adaptations: universal to any paginated forum/board. Pair with OP-020 for the thread reads. For boards
  that expose `;sort=replies`, sort AFTER era-slicing, never before (sorting destroys the era window).
counterfactual: LOW -- the crowd searches; searching cannot reach unindexed tail pages at all.

### OP-022 HN Algolia items API for full comment trees             [active]
class: operator
origin: EN frontier miner (2026-07-25)   validated-gain: pulled complete nested comment trees with depth
  labels (e.g. HN 9638748: 65 comments, 53 of them at depth>=2) -- satisfies the reply-chain>=2 depth
  mandate programmatically instead of by hand
technique: TWO-STEP, and the second step is the one people skip.
  (1) DISCOVER threads: `https://hn.algolia.com/api/v1/search?query=<q>&tags=story&hitsPerPage=50`
  (2) MINE DEPTH: `https://hn.algolia.com/api/v1/items/<story_id>` returns the FULL nested tree
      (`children` recursively) -> walk it, tag each comment with its depth, rank by mechanism-keyword
      density rather than by score. The best comment is routinely at depth 4-6 and has 0 visible points.
  CAVEAT (learned the hard way): Algolia's `query` is fuzzy OR-matching, so comment-level keyword search
  returns heavy junk (a "market maker inventory skew" query returned veterinary-startup threads).
  Use search for STORY discovery only; get precision from the tree walk + local keyword scoring.
adaptations: universal (HN is EN-centric but hosts practitioner comments in all languages).
  Equivalents: Reddit `/comments/<id>.json?limit=500&depth=10`; Discourse `/t/<id>.json`;
  Zhihu answers via question API; habr comments endpoint. Same two-step shape everywhere.
counterfactual: MED -- HN search is well known; walking the tree by DEPTH and scoring locally is not.

### OP-023 per-method RPC capability matrix (probe, never assume)   [active]
class: verification
origin: EN frontier miner (2026-07-25)   validated-gain: found the desk's registry RPC chain 3/4
  dead for eth_getLogs (publicnode token-gated, ankr key-walled, llamarpc CF-challenged,
  cloudflare broken) and located the working free set in ~10 minutes of probes
technique: before building ANY collector on "public" endpoints, probe each endpoint PER METHOD
  with one cheap real call and record the actual cap (range limit / auth / challenge), because
  free tiers enclose silently and docs lie by omission. For EVM logs specifically: MEV-relay RPCs
  (rpc.flashbots.net, rpc.mevblocker.io) are the structurally-stable free class -- their business
  is RECEIVING order-flow, not monetizing RPC, so they serve >=700-block getLogs keyless while
  "public node" providers key-wall. Re-probe on a canary cadence; each enclosure triggers
  targeted rediscovery (charter s21).
adaptations: universal to any API class, not just EVM -- for exchange REST: probe count-caps +
  pagination depth per endpoint (the Bithumb v1 depth probe is the same move); CN=BSC/Tron public
  endpoints via same matrix; SOL=public mainnet-beta caps notoriously tight, probe getSignatures
  ranges; the matrix result belongs in the universe map entry, never in a prompt's assumption.
counterfactual: MED -- individual outages get noticed eventually; the MATRIX habit (per-method,
  per-endpoint, recorded) is what prevents silent collector death.

### OP-024 conservation-law reconciliation as data verification      [active]
class: verification
origin: EN frontier miner (2026-07-25)   validated-gain: proved the USDC mint/burn free path
  INTEGER-EXACT (24h of events vs on-chain totalSupply delta; 219.88-USDC residual traced to the
  window-boundary block, then exact) -- upgraded a needs-monitoring card to verified-mechanism in
  one run
technique: when a derived series claims to measure a stock's CHANGE (supply, reserves, inventory,
  float), verify it against the stock's own conservation law over a bounded window:
  sum(inflow events) - sum(outflow events) over (t0, t1] MUST equal stock(t1) - stock(t0)
  EXACTLY (integer-exact for on-chain quantities -- no tolerance band). Any residual is a BUG
  with a findable cause; the classic one is the boundary convention (events in block t0 are
  already inside stock(t0) -- use fromBlock=t0+1). A residual you can EXPLAIN to the last unit
  is stronger verification than a small residual you wave through.
adaptations: universal -- exchange reserves via balanceOf deltas vs transfer events; UTXO chains
  via coinbase issuance vs supply; funding payments vs position P&L; CN/KR/JP venue "proof of
  reserves" claims re-checkable by the same law. Pair with OP-008 (diff-vs-ground-truth): OP-008
  compares two SOURCES, OP-024 checks one source against ITSELF -- run both.
counterfactual: LOW -- practitioner writeups diff sources against each other; closing the loop
  against the conservation law (and refusing tolerance bands) is desk discipline, not crowd
  practice.

## LEXICON — EN crypto-trading era jargon (dark-forest search keys)
_Charter dark-forest mandate deliverable #2. Slang/era-jargon is HOW you reach the folk layer:
official vocabulary finds official content. Terms below were DERIVED EMPIRICALLY, not guessed —
frequency of a 5,702-topic Bitcointalk 2010-2014 corpus vs the same boards' 2016+ topics
(ratio = era rate / modern rate). Added 2026-07-25 by the EN frontier miner._

**THE FINDING THE LEXICON ITSELF PROVES:** the era's most distinctive trading vocabulary is almost
entirely **defunct VENUE names and defunct FIAT-RAIL names** — not strategy names. The top 25
era-distinctive terms contain zero indicator/strategy words. This independently corroborates the
`era_crossvenue_fiat_premium_arb` graveyard entry: in 2011-2014 the edge WAS rail access, so the
vocabulary is about rails. Search the RAIL, not the strategy, to find era alpha discussion.

| term | ratio | gloss / era | use as search key |
|---|---|---|---|
| `gox` / `mtgox` / `mt.gox` | 43x / 13x / 17x | Mt. Gox, dominant venue to Feb-2014 collapse | the single highest-yield era key; `gox arbitrage`, `gox premium`, `gox lag` |
| `btc-e` | 22x | Russian-operated venue, 2011-2017 | pairs with gox in every era cross-venue thread |
| `glbse` | 7x | Global Bitcoin Stock Exchange — on-chain "securities", closed Oct-2012 | finds era fund/IPO/short mechanics |
| `mpex` | 5.4x | Romanian-run exchange w/ BTC-denominated options | era options + synthetic-short construction |
| `tradehill`, `cryptsy`, `bitcoinica`, `bitfloor` | 16x/11x/7x/6x | defunct venues (Bitcoinica = leveraged trading, hacked 2012) | `bitcoinica` finds the era's leverage/margin lore |
| `dwolla` | 14x | US ACH-ish rail; the Gox USD on-ramp | **rail key** — `dwolla gox` finds the premium mechanics |
| `okpay`, `bitinstant`, `sepa`, `wire`, `dwolla` | 4.9-14x | era fiat rails | the barrier-rent thesis lives in these threads |
| `localbitcoins` | 4.9x | P2P cash trading | finds capital-control workaround discussion |
| `asicminer` | 6.6x | the era's flagship on-chain security | era dividend/valuation threads |
| `wts` / `wtb` | 6.3x | "want to sell"/"want to buy" — marketplace shorthand | era OTC-flow discovery |
| `bearwhale` | (2014, low-freq) | the 30k-BTC Oct-2014 sell wall | canonical era market-impact event study |
| `willy` / `markus` | (post-2014) | alleged Gox wash-trading bots named in leaked logs | era wash-trade/volume-integrity discussion |

CROSS-REGION NOTE (charter §16): the same "search the defunct RAIL, not the strategy" heuristic
should port directly — CN era keys = 比特币中国/BTCChina, 支付宝 (Alipay) withdrawal threads, 火币
early era; KR = 김치프리미엄 + defunct venue names; RU = BTC-e's native-language threads (a large
RU-language user base). Each regional miner should run the same corpus-differencing method
(era topics vs modern topics on the same board) rather than guessing at slang.

## ARCHIVED
(none yet)
