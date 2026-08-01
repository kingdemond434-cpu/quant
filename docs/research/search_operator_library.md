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

**QUANTOPIAN LAYER (2015-2020 era, added 2026-07-28 session D — a different stratum than the
Bitcointalk rows above; here the era vocabulary IS strategy names + author handles, because the
platform pooled strategy discussion rather than venue/rail logistics):**

| term | gloss / era | use as search key |
|---|---|---|
| `In & Out` / `in_out` / `OUT_DAY` | THE late-Quantopian collaborative strategy family (risk-off rotation, Oct 2020) | finds the QC diaspora superthread ("Amazing returns" on QuantConnect) + all ports |
| `Quality Companies in an Uptrend` | the companion stock-selection superthread | its "Amazing returns = superior stock selection + superior in & out" post is the era's own combination experiment |
| `magic numbers` | era term for hardcoded overfit constants (the 58/15 debate) | finds the community's OWN sensitivity/overfit debates — free falsification material |
| `Tentor Testivis`, `Dan Whitnable`, `Vladimir`, `Thomas Chang`, `Peter Guenther`, `Guy Fleury` | the named In&Out-era leaders (shutdown-day thread R100 names exactly who the community said it would follow) | **handles are diaspora tracers** — search them on QuantConnect/Quantiacs/GitHub to find where each thread continued; `Guy Fleury` additionally finds the era's leverage-stacked-backtest pattern (61,617%-return posts — a named red-flag class) |

CROSS-REGION NOTE (charter §16): the same "search the defunct RAIL, not the strategy" heuristic
should port directly — CN era keys = 比特币中国/BTCChina, 支付宝 (Alipay) withdrawal threads, 火币
early era; KR = 김치프리미엄 + defunct venue names; RU = BTC-e's native-language threads (a large
RU-language user base). Each regional miner should run the same corpus-differencing method
(era topics vs modern topics on the same board) rather than guessing at slang. SECOND-STRATUM
COROLLARY (2026-07-28): on PLATFORM archives (Quantopian, BigQuant, FMZ, Quantiacs) the heuristic
INVERTS — there the era vocabulary is strategy names and author handles, so search the STRATEGY
and follow the HANDLE across platforms.

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
| 大饼 | dabing | "big pancake" = BTC. **Born after 2017-09-04** as WeChat keyword-filter evasion (see OP-036) | ✓✓ two independent sources on the origin; THE key for post-94 group/forum layer |
| 二饼 / 姨太 | erbing / yitai | "second pancake" / "auntie" = ETH (both coexist) | ✓ GTokenTool, udn, cngold, jb51 |
| 太子 / 末日战车 / 柚子 / 辣条 | taizi / moriz. / youzi / latiao | BCH / ETC / EOS / LTC | ✓ the coin-nickname euphemism class — finds text that never types the ticker |
| 薄饼 | baobing | "thin pancake" = **PancakeSwap, NOT bitcoin** | ✗ TRAP: looks like 大饼's sibling, is a DEX. Do not treat as a BTC key |
| 糖果 / 撸糖果 / 薅羊毛 | tangguo / lu tangguo / hao yangmao | airdrop / farming airdrops | ✓ finds the airdrop-aggregator layer (see venue finds) |
| 空气币 / 山寨币 / 传销币 / 韭菜币 | kongqibi / shanzhaibi / chuanxiaobi / jiucaibi | air-coin / altcoin / Ponzi-coin / leek-coin | ✓ all four organic in live text; 韭菜币 is new to this table |
| 狗庄 | gouzhuang | pejorative for 庄家, the manipulating operator | ✓ live 2025-09 usage (Gate square, Toutiao, Foresight) — **the term is 狗庄, never 狗商** |
| 大鳄 | da'e | "big alligator" = the wealthy big player | ✓ People's Daily 2021 — **never 大鳄鱼** |
| 小白 / 新韭菜 | xiaobai / xin jiucai | genuine newbie terms | ✓ — **never 新葱** |
| 猴市 | houshi | "monkey market" = choppy/range-bound regime (vs 牛市/熊市) | ✓ a REGIME term — the CN key for range-vs-trend discussion |
| 山寨季 / 山寨币季节 | shanzhai ji | altseason | ✓ — **never 牛季节** |
| 插针 / 瀑布 / 阴跌 / 腰斩 | chazhen / pubu / yindie / yaozhan | wick / waterfall dump / grinding decline / halved | ✓ price-action lore keys |
| 洗盘 / 控盘 / 诱多 / 诱空 / 砸盘 | xipan / kongpan / youduo / youkong / zapan | shakeout / float-control / bull trap / bear trap / dumping | ✓ **the manipulation-mechanics key set** — 控盘 (float control) is the mechanism-bearing one |
| 套牢 / 踏空 / 割肉 / 装死 / 纸手 / 钻石手 | taolao / takong / gerou / zhuangsi / zhishou / zuanshishou | trapped / missed the rally / cut losses / play dead / paper hands / diamond hands | ✓ retail POSITIONING/sentiment keys |

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
counterfactual: MEDIUM-HIGH — the thread was the run's only era find; discarding it as corrupt would
  have produced a false "CN era boards are unreadable" conclusion and, on the video-log precedent,
  could have gated a purchase or a "ground unreachable" note.

### OP-034 Quantopian forum archaeology — the extraction recipe                [active]
class: extraction
origin: EN frontier miner session D (2026-07-28), first two threads mined to exhaustion
validated-gain: 52,187 unique forum threads confirmed archived (CDX, statuscode:200, collapsed by
  urlkey) — essentially the WHOLE forum, a finite one-time-exhaustible era mine. Two threads fully
  extracted first try once the traps below were solved; produced 1 graveyard entry, 1 inbox
  principle, a WS-003 confirmation, and the era's complete diaspora record.
technique, in order of the traps actually hit:
  (1) GROUND SURVEY: `web.archive.org/cdx/search/cdx?url=quantopian.com/posts/*&collapse=urlkey&`
      `filter=statuscode:200` — 52,187 rows. Per-thread lookup: same query with the slug.
  (2) STORED-GZIP: `id_` raw captures of quantopian.com are gzip-on-disk (magic `1f8b`) —
      decompress BEFORE decoding or the page reads as mojibake indistinguishable from a corrupt
      capture. This is OP-033's cousin at the COMPRESSION layer, same false-negative shape.
  (3) SINGLE-QUOTE ATTRIBUTES: the markup uses `class='post-container'` — a grep for
      `class="post` silently zero-hits. Structure: one `post-container` (OP) + N
      `post-container response-container` blocks, each with `author-name`, `posted-at`,
      `response-text`. Split on the response-container div and regex per block.
  (4) OP OFTEN MISSING: late-2020 captures frequently omit the OP body (login-gated render)
      while ALL replies survive. Do not discard the capture — reconstruct the OP from reply
      quotes, and expect the COMPLETE final code verbatim in late replies: when the shutdown
      was announced (2020-10-28), users began pasting full source into reply text because
      attachments were dying. The best-preserved code is at the END of big threads.
  (5) DIASPORA IS IN THE LAST WEEK: replies dated after the shutdown announcement are an
      explicit, named record of where each community moved (QuantConnect canonical; Quantiacs
      futures branch; self-host branch = yfinance + IBridgePy/PythonAnywhere/EC2; plus
      closed-group Slacks — existence noteable, content out of s13 scope).
adaptations: any Rails/Discourse-era platform archive (BigQuant, FMZ, JoinQuant BBSs, Quantiacs'
  dead forum): expect the same login-walled-OP + surviving-replies shape, and mine the final
  weeks of any DYING platform for both verbatim code and diaspora pointers. Pair with OP-021
  (board-tail era-seek) for section-by-section exhaustion, and check CDX capture count FIRST
  (OP-031's precondition) before promising history.
counterfactual: HIGH on trap 2/3 — either one silently zero-hits the whole 52k-thread archive and
  would have produced a false "Quantopian forum is not recoverable from Wayback" conclusion,
  closing the region's largest finite era mine on a method artifact.

## LEXICON — KR crypto-trading jargon (dark-forest search keys)
_Seeded by the PROSPECTOR 2026-07-30 KR ground survey (charter §15/§30). Terms marked ✓ were
CONFIRMED IN LIVE USE this run (search results + tracker-site names), not assumed._

| term | romanization | gloss / era | use as search key |
|---|---|---|---|
| 김프 | kimpeu | kimchi premium (the abbreviation natives actually use — not 김치프리미엄) | ✓ finds the tracker ecosystem + trading threads; pair with 사이트/차트/매매 |
| 역프 | yeokpeu | REVERSE premium (KR below global) — the regime word English sources lack | ✓ regime-detection threads; "역프 진입" = regime-flip chatter |
| 따리 | ttari | premium slang (tracker "더따리" is named from it) | folk term for premium-harvest trades; finds retail arb lore |
| 코인별 / 종목별 | coinbyeol / jongmokbyeol | "per-coin / per-ticker" qualifier | ✓ 코인별 김프 = per-asset premium — the exact key that surfaced 6 live per-coin trackers |
| 재정거래 | jaejeong-georae | arbitrage (formal/textbook register) | finds analytical/academic KR content vs retail chatter |
| 잡코인 | japkoin | "junk coins"/alts (retail register) | KR alt-frenzy threads — the dispersion axis's behavioral layer |

### OP-035 platform archives change their MARKUP between eras — a selector validated on one era silently zero-hits another   [active]
class: extraction
origin: EN frontier miner session E (2026-08-01), mining the Quantopian OLMAR cluster
validated-gain: OP-034's selectors were derived from LATE-2020 captures. Applied unchanged to the
  SAME SITE's 2014 captures they returned **0 posts on a 79KB page that contains 7** — a silent
  false negative that reads exactly like "this capture is empty/corrupt". Generalised selector
  recovered 7/7, then 65 posts on the 2014 implementation thread and 40 on the 2019 comparison
  thread first try.
technique:
  (1) NEVER anchor on the START of a class attribute. Quantopian 2020 emits
      `class='post-container'`; Quantopian 2014 emits `class='container bg-white margin_15t
      post-container'` — the SAME token, last instead of first. Match the token ANYWHERE:
      `<div class=['\"][^'\"]*post-container[^'\"]*['\"]` (and accept both quote styles, OP-034 trap 3).
  (2) FIELD NAMES DRIFT TOO, so resolve each field through an ERA-ORDERED FALLBACK CHAIN rather
      than one name: body = `body-text-container` (2014) -> `response-text` (2020) -> `body-text`;
      date = `quanto-date` (2014) -> `posted-at` (2020). Take the first that hits.
  (3) DIAGNOSE ZERO-HITS BY CLASS CENSUS, never by eye: `grep -o "class=['\"][a-z0-9_ -]*['\"]"
      FILE | sort | uniq -c | sort -rn | head -30` names the era's real selectors in one command.
      This is the OP-030 negative-control discipline applied to EXTRACTION rather than to search.
  (4) KNOW WHAT THE CAPTURE CANNOT CONTAIN: Quantopian's backtest stat tables (`top-level-stat` /
      `stat-value` / `stat-label`) are AJAX-loaded, so every captured value is the placeholder
      `--`. 21-77 stat fields per thread, ALL empty. **Published performance numbers survive in
      that archive only as TEXT claims inside reply bodies, never as the platform's own computed
      stats** — so an era performance claim there is unverifiable at source by construction, and
      must be treated as a CLAIM (and is exactly why the era's own recomputations in the reply
      chain, e.g. the margin catch, are the most valuable objects in the thread).
adaptations: applies to ANY long-lived platform archive spanning a redesign — BigQuant, FMZ,
  JoinQuant, Xueqiu, note.com, old vBulletin/Discourse boards. Before declaring a stratum thin,
  re-run the class census on ONE page from THAT stratum. Pair with OP-034 (the Quantopian recipe)
  and OP-033 (encoding) — the three are one family: **encoding, compression and MARKUP-ERA are
  three independent layers at which a rich ground silently reads as empty.**
counterfactual: HIGH. The 2014 stratum is the ORIGINAL OLMAR wave and contains the paper author's
  own in-thread admission; a run that trusted the zero-hit would have concluded "the 2014 captures
  are login-walled/empty" and closed the era's most load-bearing evidence on a selector artifact.

### OP-026a Fed/Man-family 403-bypass routes (amendment to the OP-026 ladder)   [active]
class: source-expansion
origin: Literature deep-miner run 4 (2026-07-31), official-sector + buy-side sweeps
technique: three VALIDATED additions to the OP-026 substitute ladder — (a) NY Fed
  `newyorkfed.org/medialibrary/media/research/staff_reports/srNNNN.pdf` serves the PDF when the
  staff_reports HTML page 403s (validated: sr1052 read in full); (b) Boston Fed mirrors NY Fed
  staff-report content at `bostonfed.org/-/media/Documents/Workingpapers/...` (validated: sr1073);
  (c) the Duke Harvey archive `people.duke.edu/~charvey/Research/Published_Papers/` is a reliable
  author-self-archive bypass for the ENTIRE Man Group/Harvey paper family (validated: JPM 2022
  crypto guide + JPM 2018 vol-targeting, both read in full). Also negative route knowledge: SSRN
  `Delivery.cfm` direct-PDF is INSIDE the 403 block; retractiondatabase.org redirect-loops from
  this box; PubPeer 403s (bot-gate — do not defeat, #80 ruling pending).
validated-gain: 4 primary reads this run that would otherwise have been SUMMARY-ONLY, incl. two
  that produced watchlist cards (23, 25) and one that landed the −58% decay prior numerically.
propagation (§16): every digger adopts its own-domain equivalent — author self-archive pages and
  institutional medialibrary/mirror paths BEFORE grading any 403'd paper SUMMARY-ONLY.

### OP-036 censorship-evasion slang has a BIRTH DATE — pick the key by ERA      [active]
class: search / lexicon
origin: CN frontier miner session 3 (2026-08-01), verifying the principal's unverified-slang block
validated-gain: resolved 7/7 unverified terms and produced an era-dating rule that changes which
  key is correct for which decade of archive. CONFIRMED by two independent CN sources, verbatim:
  "最开始叫大饼的是比特天空的群，自从去年94事件之后，为防止敏感词语导致群被封，比特天空让大家把比特币称之为大饼"
  — BTC came to be called 大饼 ("big pancake") specifically so WeChat groups would not be banned
  for typing a filtered word, DATED to the 2017-09-04 "94" ban.
technique: censorship-evasion vocabulary is not timeless slang — it is BORN at a regulatory event
  and spreads afterwards. So the search key is a function of the ERA of the ground:
  (1) searching POST-2017-09 CN group/forum text for 比特币 systematically under-recalls the exact
      layer that matters, because that layer deliberately stopped typing it;
  (2) searching PRE-2017-09 archives for 大饼 returns near-zero — the term did not exist yet, and
      that zero is a FALSE NEGATIVE about the era, not evidence the ground is empty;
  (3) therefore date the ground FIRST, then choose the key. For a ground spanning the event, run
      BOTH keys and treat the union as the recall set.
  The coin-nickname class is the highest-value instance because it is the layer that never types a
  ticker: 大饼 BTC, 二饼/姨太 ETH, 太子 BCH, 末日战车 ETC, 柚子 EOS, 辣条 LTC. Trap: 薄饼 is
  PancakeSwap, NOT bitcoin — a near-homograph of 大饼 that means something unrelated.
adaptations (§16 — the mechanism is language-general, only the trigger event changes): KR — the
  2017-12/2018-01 exchange crackdown and the real-name-account rule; RU — post-2022 sanctions
  vocabulary; TR — post-2021 payment ban; any region whose community moved under legal pressure.
  The standing question for every region seat: WHAT REGULATORY EVENT HIT THIS GROUND, AND WHAT DID
  THE VOCABULARY DO ON THAT DATE? The diaspora mandate already asks where they went; this asks
  what they started calling things when they got there.
counterfactual: HIGH for era-archaeology. The desk's CN era ground (8btc/ChainNode/Tieba, 2011-2021)
  straddles the 94 event, so a single-key search of it was guaranteed to half-miss regardless of
  effort — and would have read as "the archive is thin" rather than "the key was wrong for the era".
  Pairs permanently with OP-030 (a zero is a claim about your query) and OP-032 (search native first).

### OP-037 negative-control a SUPPLIED glossary before spending budget on it     [active]
class: search / instrument hygiene
origin: CN frontier miner session 3 (2026-08-01)
validated-gain: **0 of 7** supplied unverified terms survived contact with live sources — a 100%
  noise rate on that block. Killed with the real form named in 6 cases: 牛季节→牛市/山寨季,
  蜡烛猴→蜡烛图 (chart) or 猴市 (choppy regime, a real and useful term), 新葱→小白/新韭菜,
  韭菜盒→not crypto at all (韭菜盒子 is a FOOD; the real adjacent term is 韭菜币), 狗商→狗庄,
  大鳄鱼→大鳄. "Kuisancle" is not pinyin and stayed unresolvable (亏损 kuisun = loss is the
  probable intent, but it is standard financial vocabulary, so it carries no search-key value).
technique: a glossary handed to a seat — by a principal, an LLM, a blog, a "top 50 terms" post — is
  a LEAD LIST, never a fact list, and it must be negative-controlled BEFORE any budget is spent
  querying it. Method: (a) run a VERIFIED term first as a positive control on your own search
  method, so a later zero is attributable to the term and not to the pipeline; (b) query each
  candidate quoted, in a native-language context; (c) on a zero, hunt the NEAREST REAL FORM rather
  than just deleting the row — that is where the value is, since a garbled term usually orbits a
  real one; (d) record kills permanently so the same bad row is never re-queried by the next run.
  WHY THIS IS NOT PEDANTRY: querying invented slang does not merely waste the query. It returns a
  clean zero, and a clean zero on a native term reads as "this ground has no coverage" — so bad
  vocabulary makes a RICH ground look picked clean, and the seat rationally deprioritises it
  forever. A wrong glossary is therefore worse than no glossary: it manufactures false exhaustion.
adaptations: every region seat, and every future principal-supplied or LLM-generated list of any
  kind (venues, endpoints, repos, forums) — same discipline: positive control, quote the query,
  hunt the near form, record the kill. Pair with OP-030 and OP-027.
counterfactual: HIGH — the block shipped in this seat's own prompt with an explicit warning that it
  might be invented, so every CN run until now either spent budget on noise or skipped the terms
  and left the instrument un-repaired. This closes it permanently for the whole fleet.

### OP-038 a JS anti-bot wall on the HTML is not a wall on the API      [active]
class: extraction / repo-discovery
origin: CN frontier miner session 3 (2026-08-01), first real session on the Gitee chain
validated-gain: unblocked a ground CARRIED AND NEVER STARTED across 3 prior sessions. Gitee HTML is
  behind a JS shim (`nox_*.js`): WebFetch returns **HTTP 405**, plain curl returns an empty `<body>`,
  and the API *search* endpoint returns `[]` without a token — four separate signals that all read
  as "this ground is walled". It is not. Three keyless routes work and carried the whole session.
technique: when a site's HTML is bot-walled, do NOT record the GROUND as walled — test its API and
  raw-content routes separately, because they are usually governed by different infrastructure.
  For Gitee specifically (copy-runnable):
    gitee.com/api/v5/repos/{owner}/{repo}                              -> metadata incl. LICENCE + fork parent
    gitee.com/api/v5/repos/{owner}/{repo}/git/trees/{branch}?recursive=1 -> full file tree
    gitee.com/{owner}/{repo}/raw/{branch}/{path}   (curl -sL; 302s without -L) -> raw source text
  Discovery pattern that composes with it: find repos via a SEARCH ENGINE (they index Gitee fine),
  then READ them via the API — i.e. split discovery and retrieval across two different systems
  rather than abandoning the ground when one of them refuses.
  NOTE the boundary this does NOT cross (§13): this uses the platform's own public, documented,
  unauthenticated API. It is not defeating an access control and it never touches a closed group —
  a login wall, a paid wall or a private repo remains a HARD STOP. Discovery widens WHERE you look,
  never HOW you get in.
adaptations: universal. Any bot-walled host — check `/api/`, `/raw/`, `?format=json`, an RSS/Atom
  feed, a sitemap, or the mobile endpoint before grading it WALLED. KR/JP/RU/CN portals commonly
  serve clean JSON behind a JS-rendered front. Pair with OP-030 (a zero is a claim about your
  method) and the §9 rule that a negative result is about the ROUTE, never the CAPABILITY.
counterfactual: HIGH — this ground had been deferred three sessions running and would plausibly have
  been graded "Gitee is walled from this VPS", which is exactly the false-exhaustion class OP-037
  describes, arrived at by a different door.
