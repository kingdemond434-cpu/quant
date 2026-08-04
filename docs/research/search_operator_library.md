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

### OP-025 stdlib-only PDF interior extraction (no install, no poppler)   [active]
class: verification
origin: Literature deep-miner run 3 (2026-07-26)   validated-gain: lifted a blocker that had capped
  TWO full literature runs to abstract-level evidence and left 5 findings unverified; on first use it
  CORRECTED THREE WRONG NUMBERS in a desk document (HXZ: actual 65% @ t>1.96, 82% @ the 2.78
  multiple-test hurdle, worst category trading frictions 102/106=96.2% — recorded as 64% / "85% @
  t-cutoff 3" / "liquidity 95 of 102 = 93%"). Cross-validated against an independent HTML rendering
  of a second paper: reproduces a table of parenthesised p-values to the digit.
technique: do NOT conclude "this box cannot read PDFs" from the absence of pypdf/fitz/pdfminer/
  pdftotext. PDF text lives in FlateDecode streams and the stdlib ships `zlib`. ~90 lines:
  (1) regex every `stream\r?\n ... endstream`; (2) `zlib.decompress` each (skip failures);
  (3) in each decompressed chunk pull operands of `Tj`/`TJ` — literal `(...)` strings with PDF
  escape/octal handling, and hex `<...>` strings (sniff UTF-16BE by counting zero bytes at even
  positions); (4) reconstruct inter-word spaces from TJ kern numbers more negative than ~-100;
  (5) newline on `Td`/`TD`/`T*`/`ET`. Upgrade path (worth it for CID/subset fonts): parse the xref
  object graph + object streams, build ToUnicode CMap font maps, and render per /Type/Page.
  ALWAYS grep-filter the output with a targeted regex — a 60-page paper will otherwise flood context.
  Ligatures render oddly (fi -> Þ): write regexes that avoid them (`signi` not `significance`).
  VALIDATE BEFORE TRUSTING: extract a paper whose numbers were already read from HTML and diff.
  An unvalidated extractor that mangles digits is a phantom-evidence factory.
  NOT DURABLE YET — /tmp prototype; landing it as `scripts/pdf_text.py` is GAP_REGISTER #70.
adaptations: language-independent by construction (byte-level). CN/JP/KR PDFs with CID fonts need
  the ToUnicode upgrade path above. Applies to EVERY digger, not just literature: exchange rulebooks,
  regulator filings, central-bank PDFs, vendor methodology docs, university theses — all were
  silently unreadable under the old false blocker.
counterfactual: LOW — two prior runs had the same task, the same box and the same freeze, and both
  inherited the blocker verbatim instead of testing it. This surfaced only because the premise was
  re-tested rather than re-read.

### OP-026 paywall-substitute route ladder (403 is a routing problem, not a wall)   [active]
class: source-expansion
origin: Literature deep-miner run 3 (2026-07-26)   validated-gain: SSRN/ScienceDirect/Wiley 403 from
  this VPS is the single largest cause of SUMMARY-ONLY grades, and SUMMARY-ONLY claims are BARRED
  from the graveyard — so this access gap was directly costing the desk verified negative knowledge
  (one finding, Li & Zhu crypto SIZE, is still stranded provisional purely because of it).
technique: on a 403/paywall, do NOT grade the paper SUMMARY-ONLY until this ladder is exhausted, in
  order: (1) `arxiv.org/html/<id>` and `ar5iv.labs.arxiv.org/html/<id>` — full text where the PDF
  fails; (2) NBER working-paper page (author-written abstracts, fetchable); (3) RePEc/IDEAS
  `ideas.repec.org` — carries VERBATIM abstracts, not summaries; (4) institutional open-access
  repositories hosting the publisher version legitimately (research-api.cbs.dk, open.icm.edu.pl,
  university self-archives, hec.ca, fmg.ac.uk); (5) author's own homepage/lab page self-archive;
  (6) the paper's public code+data repo (bkelly-lab/ReplicationCrisis, openassetpricing.com,
  jkpfactors.com) — often carries the tables directly; (7) OP-025 on any PDF the ladder yields.
  LEGITIMACY GATE (charter §13, absolute): the answer to a paywall is an OPEN mirror, an author
  self-archive, or doing without. NEVER circumvention. Every route above is publisher-sanctioned
  open access or an author's own posting.
adaptations: CN=CN-author arXiv clusters + author self-archives (CNKI/Wanfang stay EXCLUDED per §13);
  RU=CyberLeninka; JP=J-STAGE + CiNii; BR/LatAm=SciELO; KR=KCI/RISS open subsets; EU=DART-Europe +
  DiVA + theses.fr for the thesis layer.
counterfactual: MED — each route is individually known; the gain is making it a MANDATORY ORDERED
  LADDER before the SUMMARY-ONLY grade is allowed, which is what converts it into verified evidence.

### OP-027 false-friend / transliteration lexical audit BEFORE declaring a corpus empty   [active]
class: multilingual-pattern
origin: Literature deep-miner run 3, ground [LIT-d] (2026-07-26)   validated-gain: converted an
  apparent "Russian academia has no crypto microstructure" null into a MEASURED null with a known
  lexical cause — the difference between "we found nothing" and "we searched wrong".
technique: before recording a non-English corpus as empty, audit the QUERY TERMS for false friends
  and failed transliterations. Measured examples: **`арбитраж` in Russian means *arbitration*** and
  routes into criminal/commercial law, not trading arbitrage; **`фандинг` matches only *фандрайзинг***
  (fundraising); **`перпетуал` returns 1 hit, about Chinese diplomacy**. RU academic and practitioner
  corpora are lexically DISJOINT — the practitioner term is not the academic term. Also measured:
  **cross-CJK term borrowing FAILS** — the Chinese `市場微観構造` scores 0 on J-STAGE; each CJK
  language needs its own native construction, not a borrowed one. And long native queries against
  general web search **dilute to SEO** — keep them short and route them at the corpus's own search.
adaptations: CN=verify the term against Chinese-language finance usage before concluding absence;
  JP=build the term natively, never borrow from Chinese; KR=check Sino-Korean vs native-Korean forms;
  AR/PT=check the regional register. Applies to EVERY digger running a non-English null.
counterfactual: LOW — an English-first searcher records the null and moves on; the lexical cause is
  invisible without native-term inspection.

### OP-028 keyless corpus-count APIs as EXHAUSTION instruments                       [active]
class: verification
origin: Literature deep-miner run 3 (2026-07-26)   validated-gain: turned "we looked at CyberLeninka"
  into 16 native queries with recorded hit counts, i.e. a null another run can audit and resume from.
technique: when a corpus exposes a keyless search/count endpoint, record the QUERY AND ITS HIT COUNT,
  not a prose impression. A null with a number is falsifiable and resumable; "found nothing" is not.
  Distinguish **empty** from **blocked** every time — SciELO returned **403 (blocked, not empty)** and
  its resume door is `articlemeta.scielo.org/api/v1/`, which returns 200. Recording those as the same
  thing would have retired a live corpus.
adaptations: RU=CyberLeninka open search API; JP=J-STAGE + CiNii result counts; KR=KCI; BR/LatAm=
  SciELO ArticleMeta; CN=open-access aggregator counts. Same discipline for any repo/forum search.
counterfactual: MED — the corpora are known; recording counts instead of impressions is the gain.

### OP-029 SRO / regulator statistics beat exchange-reported data                    [active]
class: source-expansion
origin: Literature deep-miner run 3, ground [LIT-d] (2026-07-26)   validated-gain: surfaced JVCEA —
  monthly aggregate data across ALL licensed Japanese exchanges since 2018-09, publishing 売建数/買建数
  (long and short OI SEPARATELY), plausibly the only regulator-supervised L/S series in crypto.
technique: hunt the SELF-REGULATORY ORGANISATION and the supervising regulator, not just the venue.
  Exchange-reported positioning is self-reported and unaudited; SRO/regulator aggregates are neither,
  which makes them **verification assets even when they fail the EV gate as signals** (JVCEA is
  monthly, n≈94, breadth≈3 — correctly parked as alpha, valuable as ground truth). Also read the
  **TAX CODE**: Japan's 雑所得 treatment (gains taxed ≤55%, losses neither offsettable nor carried
  forward) gives a fair bet an expectation of **−27.5%**, structurally identifying a non-return-
  maximising cohort — and reforms carry DATED EXPIRIES (enacted 2026-03-31, 20% flat + 3yr
  carryforward, effective ~2028-01-01), so the cohort has a known end date.
adaptations: JP=JVCEA + JFSA; KR=FSC/FSS + DAXA; US=CFTC COT + SEC; EU=ESMA registers (and note the
  ESMA register has a public unauthenticated Solr backend); BR=CVM; RU=CBR.
counterfactual: LOW — the desk was reading venue APIs, not SRO filings.

### OP-030 negative control on every zero-hit search                                 [active]
class: verification
origin: Literature deep-miner run 3, ground [T1-a] (2026-07-26)   validated-gain: prevented a
  confident FALSE refutation — `q=kaiko` on the ESMA register's default field returns **0 hits**,
  while the core holds **28,134 docs** and the entity is in fact registered (`Kaiko Indices SAS`,
  esmaId FRBMR2019000003). Stopping at the zero would have "disproved" a true fact.
technique: a zero-hit result is a claim about YOUR QUERY until proven a claim about the WORLD. Before
  recording any absence: (1) confirm the index/core is non-empty and how many docs it holds; (2) try
  the FIELDED form, not just the default field; (3) try the entity's LEGAL name, not its brand — the
  registered entity was `Kaiko Indices SAS`, the copyright owner a third name, `Challenger Deep SAS`;
  (4) prefer the machine backend over the UI. Absence claims need a positive control that the search
  works at all.
adaptations: universal — registers, repos, corpora, APIs, in any language. Pairs with OP-027 (the
  zero may be lexical) and OP-028 (record the count).
counterfactual: LOW — two prior runs recorded "ESMA register not independently checked" rather than
  a false negative, but the failure mode was one query away.

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

### OP-031 Wayback-replay a JSON API to defeat a rolling-window cap            [active]
class: acquisition
origin: CN frontier miner session 1, axis #76 usdt-cny-otc-premium (2026-07-26)
validated-gain: turned an **unscreenable 4-row** axis into a **591-row, 6.4-year** screened series.
  `history.btc126.com/usdt/api.php` serves a daily USDT/CNY OTC series but hard-caps at a rolling
  ~177 rows; TEN parameter guesses (`limit/all/days/page/start+end/num/count/type/year/id`) every one
  returned the identical 177 rows. The cap is server-side and unliftable — but the ENDPOINT ITSELF is
  archived, and each capture is a frozen 177-row window from ITS date. Replaying 4 captures recovered
  414 additional days (2020-03-16..2021-05-07) that the live route can never serve.
technique: when a data endpoint truncates history, stop attacking the parameters and archive the
  ENDPOINT: (1) `web.archive.org/cdx/search/cdx?url=<host>/<path.json|.php>&output=json&filter=statuscode:200`
  — query the API path, NOT the HTML page (people CDX the page and miss that the XHR is archived too);
  (2) dedupe captures by the CDX `digest` column so identical snapshots aren't refetched;
  (3) fetch each with the `id_` raw-content flag: `web.archive.org/web/<timestamp>id_/<url>`
  (without `id_` you get Wayback's rewritten HTML wrapper, not the raw JSON);
  (4) union the captures into a date-keyed dict — overlapping windows self-reconcile;
  (5) **record the gaps** — capture density is the binding constraint, not the cap. Here only 4
  captures existed, so 2021-05-08..2026-01-26 is permanently unrecoverable and is declared as such.
adaptations: universal to any capped/rolling JSON, GraphQL or CSV endpoint in any language — regional
  data sites are the best hunting ground because they are widely archived and rarely paywalled. Pair
  with OP-019 (CDX on pages) — OP-019 reconstructs DOCUMENTS, OP-031 reconstructs SERIES. Check
  `id`-like monotonic row keys to infer the true series origin (`id=10` on 2020-03-16 proved the
  series starts ~2020-03-06, so the gap is bounded and known rather than open-ended).
counterfactual: HIGH — the axis had been PARKED for 4 days on "no clean free API found"; without this
  the desk would have waited ~11 months of forward recording to reach a screenable n.
ADJACENCY TEST RUN THE SAME DAY — **NEGATIVE, and it calibrates the operator.** Applied immediately to
  the desk's other known capped endpoint of the identical shape: `bitcoin-data.com/v1/{mvrv,realized-cap,
  realized-price}` (keyless JSON, hard 1,461-row 4-year rolling window, `?startday=`/`?since=` accepted
  and IGNORED — the same accepted-and-ignored signature as btc126). CDX returns **0 captures** for all
  three API paths, so nothing is recoverable. CONCLUSION: OP-031's success rate is set by ARCHIVE
  DENSITY, not by the cap — and API paths are archived far more sparsely than HTML pages (btc126's page
  had captures back to 2020 while its api.php had only 4). CHECK CDX COUNT FIRST; it is one cheap call
  and it tells you whether the operator applies before you build anything.

### OP-032 search the native language FIRST, not as a fallback                  [active]
class: discovery
origin: CN frontier miner session 1 (2026-07-26)   validated-gain: a controlled A/B on the SAME
  question, run in the same minute. **English** ("USDT/CNY OTC premium historical data free API") →
  CoinGecko/CMC/Yahoo/CoinAPI generic Tether pages and the explicit conclusion *"OTC premiums and
  China-specific USDT pricing dynamics may not be readily available through standard free APIs."*
  **Chinese** (`USDT 场外价格 历史数据 API 人民币 溢价指数`) → the formal index DEFINITION (ChaiNext
  折溢价指数 = OTC price ÷ **offshore CNH** × 100) plus two live data sites, one of which serves the
  free daily history. The English search did not merely rank the source lower — it returned a
  confident FALSE NEGATIVE that would have closed the lead.
technique: for any region-specific quantity, issue the native query FIRST and treat an English null as
  carrying **zero** evidential weight about existence. Compose native queries from the domain noun +
  the data-shape noun: 场外价格 (OTC price) + 历史数据 (historical data) + API + 指数 (index). Never
  translate an English phrase word-for-word — use the term the locals actually type.
adaptations: the failure is language-general. KR 시세/과거 데이터, JP 過去データ/取得, RU исторические
  данные, TR geçmiş veri, PT dados históricos, ES datos históricos. Pair with OP-027 (a zero may be
  lexical) and OP-030 (a zero is a claim about your query until proven otherwise).
counterfactual: HIGH — this single query is the whole reason axis #76 got un-parked.

## LEXICON — CN crypto-trading jargon (dark-forest search keys)
_Charter dark-forest mandate deliverable #2, CN region. Seeded from the principal's list; terms
marked ✓ were CONFIRMED IN USE this run (2026-07-26) against live CN pages/APIs rather than assumed._

| term | pinyin | gloss / era | use as search key |
|---|---|---|---|
| 场外 / 场外价格 | changwai | OTC / OTC price — the standard term for the P2P stablecoin market | ✓ the key that unlocked axis #76; pair with 历史数据 or API |
| 折溢价指数 | zhe-yijia zhishu | discount/premium index (ChaiNext's formal name for the USDT premium) | ✓ finds the formal index definition, not retail chatter |
| 溢价率 | yijia lü | premium rate (%) | ✓ btc126 page title |
| 承兑商 | chengduishang | OTC "acceptor"/merchant — the professional market-making layer of the P2P book | the merchant-density variable that explains why CN premium < kimchi |
| 搬砖 | banzhuan | lit. "moving bricks" = cross-border/cross-venue arb; the 2013-17 era's core trade | era-archaeology key for 8btc/ChainNode/Tieba archives |
| 韭菜 / 割韭菜 | jiucai / ge jiucai | retail "leeks" / harvesting them | finds retail-behaviour and market-manipulation lore |
| 爆仓 | baocang | liquidation/blown account | finds leverage post-mortems |
| 插针 | chazhen | "needle insertion" = wick / stop-hunt | microstructure lore, exchange-wick disputes |
| 庄家 | zhuangjia | the "operator"/whale manipulating a book | manipulation-mechanics threads |
| 梭哈 | suoha | all-in (from "show hand") | retail sentiment marker |
| 合约党 | heyue dang | the perp-contract crowd | finds derivatives-retail cohort discussion |
| 走势图 | zoushitu | trend chart | pairs with 历史 to find chart pages that have a data endpoint behind them |
| 内盘 / 外盘 | neipan / waipan | domestic vs overseas venues (also: a DEX's internal book, e.g. BTS 内盘) | ✓(08-04, era text) pair with 差价 to find spread/premium threads across ALL eras |
| B网 / P网 / 果盘 | B-wang / P-wang / guopan | Bittrex / Poloniex / collectively the domestic venues (era) | ✓ single-letter venue names defeat keyword search — search the NICKNAME, not "Bittrex" |
| 辣条 | latiao | "spicy stick" = LTC/Litecoin | ✓(08-04) finds LTC threads no English or official term reaches |
| 郭嘉 | guojia | censorship homophone for 国家 (the state); Three-Kingdoms name used to dodge filters | ✓(08-04, two posts) THE censorship-evolution class the mandate predicts — search it to find state-action threads that survived moderation |
| 央妈 | yangma | "central mama" = PBOC | ✓(08-04) finds central-bank-action threads in retail register |
| 被墙 | beiqiang | GFW-blocked | ✓(08-04) dates access-barrier events from primary sources (e.g. 2017-09-20 exchange blocking) |
| 提币 / 提现 | tibi / tixian | withdraw COINS vs withdraw FIAT — the freeze-era distinction that sets premium sign | ✓(08-04) the pair disambiguates which LEG a barrier froze; search both, never one |
| 转外网 | zhuan waiwang | "move to the overseas net" — the diaspora act itself | ✓(08-04) THE diaspora search key for every CN regime event |
| 结售汇 | jieshouhui | official FX settlement/purchase system | ✓(08-04) finds the fiat-rail chokepoint discussion |
| 搬砖砸脚 | banzhuan zajiao | "dropping the brick on your own foot" — in-flight transfer loss | era name for transfer-latency risk (inbox #70; confirmed s1) |

### OP-033 legacy regional forums are NOT UTF-8 — decode before you judge     [active]
class: extraction
origin: CN frontier miner session 1, 8btc era thread (2026-07-26)
validated-gain: prevented discarding a live find as a corrupt capture. `8btc.com/thread-53689-1-1.html`
  (Discuz, 2017) is **GBK/GB2312**. Decoded as UTF-8 it renders as solid mojibake — the exact signature
  of a broken/truncated archive capture, and the natural next move is to drop the source and move on.
  Re-decoded as GBK it is clean primary text and produced a graveyard entry plus an execution rule.
technique: for any pre-~2018 regional forum, archive capture, or national-portal page, do NOT trust the
  default decode. (1) Read the declared charset (`<meta charset>` / `Content-Type`) — legacy Discuz,
  phpBB and vBulletin installs commonly declare gb2312, gbk, big5, euc-kr, shift_jis, windows-1251;
  (2) treat mojibake as an ENCODING hypothesis, never as evidence the capture is bad; (3) decode with
  `errors='replace'` so a few bad bytes don't abort the whole page. Wayback serves the ORIGINAL bytes
  under the `id_` raw flag, so the original charset — not UTF-8 — is what you get.
adaptations: CN gbk/gb2312 (simplified, mainland), big5 (traditional, TW/HK); KR euc-kr; JP shift_jis /
  euc-jp; RU windows-1251/koi8-r; TR iso-8859-9. This is a general precondition for ERA-ARCHAEOLOGY in
  every region — the older the ground, the less likely it is UTF-8, so the dark-forest mandate and this
  operator are permanently paired. Pair with OP-027 (a zero may be lexical) and OP-030 (a zero is a
  claim about your method until proven otherwise): a mojibake page is the *extraction-layer* form of the
  same false negative.
addendum (CN miner s2, 2026-08-04): charset failures can be PER-POST, not per-page — user-pasted
  content inside an otherwise-clean GBK page can carry big5/utf-8 fragments (8btc thread-75923 post #6:
  clean page, mojibake post). A garbled POST is not a garbled PAGE: keep the page, flag the post. Also:
  the SAME thread's page-1 and page-2 captures can come from different template eras with different
  date markup (relative-date `<span title="...">` vs literal) — parse both forms before concluding a
  page has "no posts".
counterfactual: MEDIUM-HIGH — the thread was the run's only era find; discarding it as corrupt would
  have produced a false "CN era boards are unreadable" conclusion and, on the video-log precedent,
  could have gated a purchase or a "ground unreachable" note.

### OP-034 dead-forum CDX index + capture triage (length-rank, gzip-sniff)   [active]
class: reconstruction
origin: EN frontier miner (2026-08-04, Quantopian archive dig)   validated-gain: turned a DEAD
  Rails forum (quantopian.com HTTP 000, 12 CDX pages of /posts/*) into a mapped, finite,
  exhaustible ground in 3 calls, and rescued a "corrupt" capture that was actually gzip.
technique: for a dead forum whose live route is gone: (1) INDEX: CDX-query the POSTS PATH with
  `collapse=urlkey` — the slug list IS the board index (OP-021's era-seek equivalent for dead
  sites; slugs are human-readable, so topic search works on the index itself, no page fetches).
  (2) TRIAGE BY THE LENGTH COLUMN before fetching: on late-era captures of JS-migrating platforms,
  ~9KB captures are empty client-side shells while 30-60KB captures are server-rendered FULL
  threads — the CDX length field separates them for free (Quantopian: shutdown-week captures ~9KB
  useless; the same thread's earlier capture 54KB carried 100+ replies). Prefer the LARGEST
  capture of a URL, not the latest. (3) SNIFF BYTES on every `id_` fetch: Wayback stores some
  responses gzip-COMPRESSED and `id_` serves the stored bytes verbatim with no Content-Encoding
  header — magic bytes `1f 8b` → gunzip before judging. Mojibake-looking output is an
  ENCODING/COMPRESSION hypothesis first (OP-033's content-encoding cousin), never proof of a bad
  capture. (4) Then exhaust section-by-section per OP-021 and mark EXHAUSTED honestly.
adaptations: universal to any dead board (Discuz/phpBB/vBulletin/Rails/Discourse) in any region —
  CN=8btc/ChainNode dead boards (pair with OP-033 GBK decode); KR=defunct cafe mirrors; JP=dead
  5ch mirrors via archived hosts; RU=dead bitcointalk-RU sections. The length-triage matters MOST
  for 2018+ platforms that migrated to client-side rendering before dying.
counterfactual: LOW-MED — Wayback digging is common; ranking captures by CDX LENGTH to dodge
  JS shells and the gzip magic-byte sniff are both desk discipline that turns "archive is broken"
  false negatives into reads.

### OP-047 equal-width binning on fat tails voids a factor test (pd.cut ≠ pd.qcut)   [active]
_(numbered past OP-046: this working tree is the forked branch whose library ends at OP-034, but
master already holds OP-035..046 — skipping ahead avoids a renumber collision at merge, per the
EN-s4 union+renumber-once convention.)_
class: verification
origin: CN frontier miner s2 (2026-08-04), forensics on the 39-star HKU replication of
  Liu-Tsyvinski-Wu (J. Finance 2022)   validated-gain: reversed a false falsification before it
  entered the desk's priors — the repo + its issue thread read as "LTW crypto momentum fails to
  replicate", but the momentum functions bin with `pd.cut(week_ret_lag1, bins=5)` = FIVE EQUAL-WIDTH
  bins over the RANGE of fat-tailed weekly crypto returns, so "quintile 5" is really the 1-3 moonshot
  outliers and "quintile 1" the worst crashes; the size functions correctly use `pd.qcut`. The
  "momentum test" never tested momentum.
technique: in ANY third-party factor code (and our own), check the binning primitive against the
  variable's distribution BEFORE reading the results table: equal-frequency (qcut/percentile) is the
  factor-literature convention; equal-width (cut/linspace) on heavy-tailed inputs concentrates ~all
  mass in interior bins and turns the extreme bins into outlier detectors. Red flags: `pd.cut` on
  returns/volume/mcap; bin counts wildly unequal; "top quintile" holding <5 names. Second forensic
  layer from the same repo: selection helper reassigned from the FULL panel (`data = df[...]` after
  `data = df[week==t-1]`), so bin edges were fit on pooled history = look-ahead edges + cross-week
  name pollution. A replication with either defect is evidence about NOTHING (neither for nor
  against the paper) — but its ISSUE THREAD can still carry independent evidence: here a second
  replicator's EW-vs-VW significance flip (logged as a weak signal) survives the code's death.
adaptations: universal to all regions' practitioner code; highest density in course-project and
  blog-tutorial repos (CN 课程复现/知乎 walkthroughs, KR/JP blog backtests, RU habr posts) where the
  author states methods honestly enough to audit. Pair with OP-030 (a zero is a claim about the
  method): a NON-replication is a claim about the replication's method until the binning is checked.
counterfactual: MEDIUM-HIGH — a digger citing "CN replication: LTW momentum insignificant" without
  this check would have banked a false negative against the exact factor family the desk trades
  cross-sectionally.

### OP-048 Gitee is discovery-walled but content-open — route around, not through   [active]
class: source-route
origin: CN frontier miner s2 (2026-08-04), four-route probe
validated-gain: turned "Gitee unreachable" into a working access map in 6 calls.
technique: measured state 2026-08-04, from a datacenter IP with curl: (1) robots.txt is allow-all
  (crawl-delay 1, no Claude-by-name block) but disallows /api/v*, /raw/*, /tree/*; (2) API v5
  search answers HTTP 200 with an EMPTY array anonymously — a silent null, not an error (OP-030
  class: looks like "no results", is actually "no access"); (3) web search 301s to so.gitee.com, a
  JS SPA whose Indexea widget backend (`so.gitee.com/v1/widgets/search/<id>`, widget id readable in
  the public bundle) returns 401 anonymously; (4) /explore and /search serve a "nox" JS anti-bot
  challenge (HTTP 405) to non-browser clients — BUT (5) direct REPO LANDING PAGES return HTTP 200
  to a plain browser UA. So: content reachable if you already hold the path; every on-site
  discovery surface is walled. DISCOVER ELSEWHERE, READ ON SITE: (a) Baidu/Bing `site:gitee.com`
  operators (OP-002), (b) GitHub-side discovery then check the author's Gitee for the CN-only
  counterpart, (c) Wayback CDX of gitee.com/explore* as a frozen category index (captures span
  2021-2025 with lang/license/order facets; taxonomy holds NO crypto-quant category — `quantum` is
  quantum computing, so category browse was never the route).
adaptations: the SHAPE generalises (JP seat's bitFlyer per-hostname finding is the same law:
  blocks are per-SURFACE, not per-site — always probe content routes after a discovery surface
  blocks). KR: naver blocks by name in robots (hard stop, different class). Re-probe Gitee
  quarterly; anti-bot walls are config, not policy, and this one carries no §13 signal (no licence
  or ToS refusal involved).
counterfactual: MED — the natural conclusion after /explore 405s is "Gitee is closed"; the desk's
  region ground would have been falsely written off.
