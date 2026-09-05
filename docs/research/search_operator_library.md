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
adaptations: universal per venue. RETARGETED 2026-09-05 -- this line used to send regional miners at crypto exchange buckets (Upbit/Bithumb/bitFlyer/OKX/Gate), which the 2026-08-18 universe mandate retired; the TECHNIQUE is venue-agnostic and still active. Probe instead: broker and data-vendor public trees (Dukascopy datafeed, HistData, TrueFX, Forexite), exchange public FTP/S3 (CME, ICE, LME product and settlement files), LBMA benchmark archives, and central-bank/statistics-office bulk endpoints. The validated-gain above is the crypto era's record of the pattern working, kept as evidence that it does -- not as a list to re-probe.

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
adaptations: universal to any paginated forum/board. Pair with OP-020 for the thread reads. KR
  (2026-08-04): Ppomppu zboard — robots FORBIDS /search_bbs.php, so era-seek is the ONLY legal path;
  seek by post `no` binary-search (view.php?id=<board>&no=<n> → date), not page offset: ~190k posts,
  no=150 = 2014-07, live head 2026-08; decode cp949 errors=replace (strict euc-kr dies on stray bytes).
  For boards
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

_OP-022 field note (EN sG, 08-12): OPERATOR-DEFENSE MINING — in any platform/contest thread, the
platform's OWN EMPLOYEES' defensive replies enumerate their validation design in public (HN
9152332: fawce/dunster/jik laid out the full gate — 6 equal-weighted metrics, 2y backtest + 1mo
paper, locked-since-submission, default commission+slippage, source unread). That enumeration is
a free PRE-REGISTRATION of the platform's failure mode: pair it with the later outcome (the 2020
fund capital-return) and you hold a complete natural experiment — design, defense, and refutation,
all citable. Search key: site/thread + operator-handle replies, not the OP. Adaptations:
JP/CN=JoinQuant/BigQuant/myquant staff replies in BBS threads; WorldQuant staff forum replies
(their submission-bar defenses are FACTS ABOUT THEIR PROCESS, never gates for ours); KR=exchange
"official" accounts defending listing/delisting rules in cafe threads — same structure: the
defense names the gate, reality later grades it._

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

### OP-039 habr comments API — the full nested tree in one keyless call      [active]
class: community-discovery / operator
origin: RU frontier miner (2026-08-01)   validated-gain: on habr 911056 returned 66 comments to
  depth 7 in one call; the three highest-value findings of the session were ALL at depth>=1 and
  NONE were in the article body — incl. the cross-venue ticker-collision mechanism that a desk-side
  probe then DEMONSTRATED against our own join code.
technique: OP-003/OP-022's two-step shape, now runnable for RU. The library previously said only
  "habr comments endpoint" as an OP-003 adaptation and never gave a URL, so it was unexecutable.
  (1) DISCOVER: normal web/Yandex search for habr.com/ru/articles/<id>/
  (2) MINE DEPTH — ONE keyless GET, no auth, no JS wall:
      curl -H "User-Agent: Mozilla/5.0" https://habr.com/kek/v2/articles/<id>/comments/
      -> {"comments": {"<id>": {"parentId":..., "level":<depth>, "score":..., "message":"<html>"}}}
      `level` IS the depth, precomputed — no tree walk needed to satisfy the >=2 depth mandate.
      Strip HTML, then rank by MECHANISM-KEYWORD DENSITY, never by `score`: on 911056 the single
      most valuable comment (ticker collision + no-spot-short-on-MEXC + a 25-40 Mbit/s bandwidth
      figure) had score=0, and the top-voted comment carried nothing.
  NOTE the host is habr.com/kek/v2/ (not /api/), which is why it is not found by guessing.
adaptations: RU=habr (verified 2026-08-01). Same two-step shape as HN Algolia (OP-022), Reddit
  .json, Discourse /t/<id>.json, Zhihu answer API. CN/KR/JP equivalents already listed in OP-003.
counterfactual: LOW — the endpoint is undocumented publicly and the depth+density ranking is the
  part that actually surfaces the value; a reader of the article alone gets the debunking headline
  and none of the four mechanisms.

### OP-040 the venue that re-denominates in the TICKER vs in the CONTRACT SIZE   [active]
class: verification / reconstruction
origin: RU frontier miner (2026-08-01)   validated-gain: found 5 liquid perps (SHIB/PEPE/FLOKI/
  BONK/SATS) that OKX lists and the desk's string join silently drops
technique: before trusting ANY cross-venue symbol join, test the re-denomination convention, which
  differs BY VENUE for the same underlying: Binance puts the multiplier in the TICKER
  (`1000SHIBUSDT`), OKX puts it in the CONTRACT SIZE (`SHIB-USDT-SWAP`, ctVal=1,000,000 SHIB).
  A `symbol[:-4]` style join therefore MISSES the asset entirely rather than mismatching it.
  Probe: pull both venues' instrument lists, strip any leading numeric multiplier, and check the
  stripped form as well as the literal one; compare ctVal/contractSize before declaring a match.
adaptations: universal — any venue pair. Bybit/Binance mostly agree on the 1000 prefix; OKX does
  not; Bitget/Gate/HTX conventions unverified and are the next probe.
counterfactual: MED — a coverage gap is invisible by construction (the symbol just is not there),
  so nothing surfaces it until someone counts the join's hit rate.

## LEXICON — RU crypto-trading jargon (dark-forest search keys)
_Seeded by the RU frontier miner 2026-08-01. Terms VERIFIED in situ (seen in a real RU thread this
session) are marked [V]; terms carried in from the seat brief and NOT yet seen in the wild are
marked [UNVERIFIED] and must be negative-controlled before budget is spent on them (OP-037)._

| term | gloss | era | status | example query |
|---|---|---|---|---|
| перелив / переливать | "pouring over" — moving funds between venues to harvest a spread; the standard RU term for inter-exchange arb, and it does NOT translate as "arbitrage" | 2018- | [V] habr 911056/599551 | `перелив между биржами криптовалюта` |
| стакан | order book (lit. "glass") — the RU word; `orderbook` returns EN content, `стакан` returns RU practitioner content | perennial | [V] habr 911056 comments | `стакан глубина ликвидность бот` |
| щиткоин / щиток | shitcoin (transliterated + diminutive) | 2017- | [V] habr 911056 comments | `щиткоины арбитраж спред` |
| люфтить (курсом) | "to have play/slack" (mechanical term) — a venue whose quote drifts loosely vs consensus; names the thin-venue divergence cohort exactly | 2020s | [V] habr 911056 comment | `биржи которые люфтят курсом` |
| токсичные сделки | "toxic trades" — the VENUE's term for flow it bans; the binding constraint on retail cross-venue arb | 2020s | [V] habr 911056 comment | `бан за токсичные сделки биржа вывод` |
| спалиться | "to get burned/spotted" — to be detected by the venue's surveillance | perennial | [V] habr 911056 comment | `как не спалиться арбитраж биржа` |
| хомяк | "hamster" = retail bagholder (the RU equivalent of CN 韭菜) | 2017- | [UNVERIFIED] seat brief | `хомяки закупились памп` |
| памп / слив | pump / dump-and-drain | perennial | [UNVERIFIED] seat brief | `памп слив схема телеграм` |
| физлицо / физик | "natural person" — the P2P/tax-rail term for a retail individual counterparty | perennial | [UNVERIFIED] seat brief | `физлицо P2P лимиты банк` |
| календарный арбитраж | calendar spread arb (near vs far future) — the dominant RU statarb form on MOEX | perennial | [V] smart-lab 707565 | `календарный арбитраж фьючерс проскальзывание` |
| проскальзывание | slippage — the RU practitioner's named killer of statarb | perennial | [V] smart-lab 707565 | `статарбитраж проскальзывание не работает` |
| связка | "the link-chain" — a payment ROUTE tested end-to-end (venue→processor→bank/card); the folk term for rail combinations, and THE search key for corridor/obnal genre ("проверял связку") | 2013- | [V] btcsec 2047 reply 7 | `связка вывод биржа карта` |
| резерв(ы) | exchanger float/inventory — the capacity variable of the whole dealer layer; "резервов нет" = rail at capacity | 2013- | [V] btcsec 5848/3426 ("Апдейт, резервы актуальны") | `обменник резервы направление` |
| складчина | group-buy / cost-sharing (of bots, courses, signals) — finds the retail tooling-distribution layer and its monoculture (WS-010) | perennial | [V] btcsec 4382 reply 20 | `складчина бот стратегия торговый` |
| стенка | order-book wall (large limit order); "ловить стенку" = wall-catching, the era's book-reading verb — era bots shipped wall-filters with spoof-ignore limits | 2013- | [V] btcsec 4382 OP | `стенка стакан бот ловить` |
| сетка (тягать сетку) | the order GRID itself; "тягание сетки туда-сюда" (dragging the grid back and forth) is the vendor's own name for grid-bot order management — THE key for grid-bot content AND for venue cancel-policy discussions (fill-ratio enforcement killed the class on Bittrex) | 2013- | [V] ezhrd blog comment 2018-01-06 | `сетка ордеров бот биржа отмененные` |
| фикс / фикс-ордер | the take-profit CLOSE leg of a grid/ladder cycle ("бот не скорректировал фикс-ордер"); also фиксить убыток = realize a loss — the sizing/exit-discussion key | 2013- | [V] ezhrd blog comments 2015-08-24 + btcsec 6475 | `фикс ордер бот закуп` |
| депо | deposit = bankroll; the era's sizing unit ("торговля на 100% депо – это самоубийство") — finds position-sizing and risk folk-rails | perennial | [V] ezhrd blog comment 2017-02-05 | `какой процент депо бот торговля` |
| автоследование / автослед | **copy-trading / signal-following — and the English term finds NOTHING on RU ground.** The whole RU retail copy-flow layer (broker-hosted follower products, published track records, "Реформа автоследа в Т-банке") is titled with this word. Direct key to WS-010's modern echo | 2015- | [V] smart-lab 1335532 comment 19779413 + /algotrading/ section titles (2026-08-13) | `автоследование статистика просадка` |
| поделка / поделки | "shoddy knock-off" — the RU reviewer's standard word for a worthless commercial bot/EA. **The key to the REFUTATION genre**: independent teardowns of sold robots title themselves with it, and refutations are free graveyard material | perennial | [V] smart-lab 1335574 opening line (2026-08-13) | `поделки MQL5 независимый тест советник` |
| грааль / форекс грааль | "the grail" — the RU retail name for a supposed holy-grail system. Doubles as a **site keyword tag**, so it enumerates the whole over-claim corpus (and therefore the refutation corpus that answers it) | perennial | [V] smart-lab 1335532 body + 1335574 keyword tags (2026-08-13) | `форекс грааль разбор эквити` |
| ошибка выжившего | survivorship bias — the RU term, and a smart-lab keyword tag. Finds the RU data-hygiene corpus, which is where the point-in-time/universe discussion actually lives | perennial | [V] smart-lab 1336741 keyword tags (2026-08-13) | `ошибка выжившего бэктест состав индекса` |
| переподгонка | overfitting — RU practitioner term (not "оверфиттинг"); pairs with `подгонка` (fitting). Finds the validation-discipline layer rather than the vendor layer | perennial | [V] smart-lab 1335532 body (2026-08-13) | `переподгонка walk-forward количество попыток` |

### OP-041 CN deep-forest story grounds via search-engine `site:` routes           [active]
class: multilingual-pattern / route-ladder
origin: principal order 2026-09-04 ("the deep Chinese web is still absolutely worth mining")
technique: grounds that refuse a datacenter fetch (知乎 403, CSDN timeout, 雪球 WAF, 淘股吧, 经管之家) are
  reached through Bing (`site:zhihu.com 黄金 日内 交易 策略 实盘 经验`, setlang=zh-CN) with DuckDuckGo html as
  the second engine; platforms with APIs are read natively (Gitee api/v5 search+readme, Bilibili WBI search +
  player/v2 subtitles, 掘金 search_api, 微信 via 搜狗); JS shells (聚宽/优矿/米筐/BigQuant) through the
  rendered fetch. Query bank lives in desks/mt5/data/deep_forest_sources.json; every claim (quantity +
  direction + horizon, zh or en) is queued as story_mechanism with the instrument mapped to its MT5
  analogue and provenance; result URLs are fed to the world-crawler frontier. Competition records
  (期货日报实盘大赛, 蓝海密剑) and interviews (七禾网, 私募排排网) are the highest-yield register: numbers plus
  a stated method. A story's numbers are evidence about the story, never about the mechanism.
adaptations: per-region site: lists (KR: dcinside/naver blogs, JP: note/qiita, RU: smart-lab) reuse the same
  route ladder and claim grammar; add the region's instrument aliases to mechanism_claims.INSTRUMENT_ALIASES.

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
| 塞舌尔人 | saisheerren | "the Seychellois" = BitMEX + its degen crowd (Seychelles incorporation); era mock-slogan "塞舌尔人最低五十倍杠杆起步…唯有爆仓止损" | ✓(08-12) 8btc thread-166158 (2018-05) — the 2018 合约党 era key; finds BitMEX-era leverage lore official terms never reach |
| 对敲 | duiqiao | self-matched/wash prints — in era derivatives context, the manipulation allegation term (bots printing against themselves to move the mark) | ✓(08-12) 8btc thread-2352 (2013-12, 796 incident) — pairs with 插针/控盘 as the DERIVATIVES manipulation key |
| 抄币 | chaobi | "coin trading/speculation" — the PRE-炒币 era orthography (抄 for 炒), admin-register usage | ✓(08-19) coinsbbs admin post 2013-12-08 ("对抄币影响并不大") — search BOTH spellings on the 2013 stratum; the modern 炒币 alone under-recalls it |
| MT | — | CN-era abbreviation for MtGox ("MT大跌") | ✓(08-19) coinsbbs thread-120 #229 (2013-12-07) — era key; "门头沟" (the later folk name) post-dates the 2014 collapse, so MT is the IN-ERA search key |
| 搬砖群 / 板砖群 | banzhuanqun | closed QQ arb groups — the era's edge-distribution channel ("绝密", full by 2013-12); 板砖 is a live typo-variant of 搬砖 | ✓(08-19) coinsbbs thread-120 #171/#173 — search both orthographies; the group layer itself is §13-closed, but the term finds the RECRUITMENT/advertisement threads which are public |
| 回复可见 / 隐藏内容 / 阅读权限 | huifukejian / yincang neirong / yuedu quanxian | reply-to-view / hidden content / read-permission — Discuz gate MARKERS, method vocabulary not slang | ✓(08-19) OP-088's discovery inversion: query gate-marker + 教程/策略/搬砖 to enumerate exactly the threads the era gated — the ranked where-the-edges-were shortlist |
| 贴水 | tieshui | SGE gold trading BELOW international parity (antonym 升水 = premium; unobserved this session) | ✓(08-25, MT5-era row) cngold "贴水扩大至8.07元/克" — pair with 沪金/伦敦金 to find premium-regime threads |
| 延期补偿费 / 延期费 | yanqi buchangfei / yanqifei | SGE T+D deferred compensation fee — the funding-rate analog on CN gold/silver; direction set by delivery-declaration imbalance (递延费 is a common variant, unobserved this session) | ✓(08-25) SGE official spec + cngold; THE key for CN gold carry/positioning lore |
| 交收申报 / 中立仓 | jiaoshou shenbao / zhonglicang | delivery declaration / neutral-warehouse declaration — the 15:00–15:40 CST window that SETS the fee direction | ✓(08-25) SGE spec; microstructure vocabulary, finds rules + lore the retail words miss |
| 空头付多头 / 多付空 | kongtou fu duotou | shorts-pay-longs (fee direction reading); abbreviated 空付多/多付空 | ✓(08-25) cngold; the direction-flip event key |
| 对赌 / 对赌盘 | dudu/ dudupan (duìdǔ) | member-firm B-book — the house takes the other side of its own clients | ✓(08-25) 2014 南都 exposé + 武久文 legal analysis; THE bucket-shop-era mechanics key |
| 吃头寸 | chi toucun | "eating the position" = booking client losses as house revenue (头寸 = the client-loss pool rebated to member firms) | ✓(08-25) exposé, insider-quoted; finds B-book economics threads |
| 喊单 / 带盘 / 老师 / 托 | handan / daipan / laoshi / tuo | call-room signal-calling / guided trading / the "teacher" / the shill | ✓(08-25) exposé + legal analysis; the call-room-structure key set |
| 刷单 | shuadan | churning client accounts for fees (advisor-driven turnover) | ✓(08-25) exposé (¥500k → ¥40M turnover in 10 days); finds churn-complaint threads |
| 反向跟单 / 反跟单 | fanxiang gendan | reverse copy-trade — industrial fading of aggregate retail flow; an entire CN software-vendor genre | ✓(08-25) vendor corpus qhfgd.com (68-part series, unmined); BOTH orthographies needed |
| 滑点 | huadian | slippage — in bucket-shop context an ADMINISTERED per-client parameter, not a market outcome | ✓(08-25) back-office menu screenshot ("滑点金额：10"); pairs with 后台 for software-manipulation lore |
| 维权 | weiquan | victims' rights-defense — collapse/fraud aftermath threads (QQ groups, HQ sieges) | ✓(08-25) exposé; 维权 + venue name = the post-mortem layer of ANY dead CN platform, era-universal |
| 清理整顿 | qingli zhengdun | the State-Council venue cleanup (38号文 2011 / 37号文 2012 / 2017 回头看) | ✓(08-25) CSRC official Q&A; THE era-boundary key for the bucket-shop stratum |
| 现货白银 / 贵金属交易所 | xianhuo baiyin / guijinshu jiaoyisuo | "spot silver" / local precious-metals bourse — the 2011-2017 CFD-shaped retail era on gold/silver | ✓(08-25) all primary sources this run; the era's own name for itself |

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
addendum (CN miner 2026-08-12, board-233 measurement): **a max page-number URL in CDX is NOT board
  size — out-of-range Discuz page URLs alias to the last real page.** 8btc forum-233-1000.html
  (captured 2018-09) renders a thread list ~identical to forum-233-1.html: the board held ~31
  threads, not 1000 pages, and the 08-04 board map's "233 = 1000 pages" was this trap. Before
  budgeting a deep dig on a CDX-implied page count, fetch the claimed-distant page and DIFF THE
  EXTRACTED THREAD-ID SETS against page 1 — near-identical sets mean the board is small and fully
  enumerable in one pass (which is a GOOD outcome: section-exhaustion becomes claimable same-run).
  Regional adaptations: any Discuz/phpBB derivative (CN/KR/RU legacy boards) aliases the same way;
  vBulletin 404s instead, so absence-of-404 is itself the Discuz signature.

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

### OP-049 the ad board IS the data: service-ad census as a barrier-rent instrument   [active]
found: 2026-08-04, RU frontier miner s1-on-branch, answering the 2022 sanctions-diaspora
  standing question in ONE fetch after thread-search approaches would have taken days.
what: on any legacy community forum, the CURRENT front page of its services/P2P/obmen sections
  is a structured CENSUS of the gray-rail economy: each ad publicly quotes the rent (fee %,
  "AML < N%" ladders), the settlement unit (post-2022 RU: universally USDT-TRC20), the
  interface (Telegram bots), the corridors (currency lists), and the geography (cities where
  cash sits). Read 25 ad TITLES and you have the market structure without touching a single
  rail. Complementary reading: which sections DIED (era boards) vs which are ad-saturated
  (rails) maps where the community's economic weight went — the diaspora answer is in the
  section-level activity gradient, not in any thread's text.
why it beats thread-mining for this question: ads are written to be found and priced to clear —
  they are the one genre where the poster VOLUNTEERS the quantitative structure (rent, corridor,
  venue). Discussion threads hide this in 40 pages of chatter.
s13 note: the census is of PUBLIC ads only and produces STRUCTURE knowledge, never a source —
  the advertised layer (mixers, no-KYC processing, invite-only «закрытые площадки») is
  permanently untouchable; carding any of it as a data source is a hard stop. The instrument is
  legitimate precisely because it never enters the shop, it reads the shop window.
adaptations: RU=forum.bits.media sections 74/166 (done 08-04); CN=public layer thin (94-era
  precedent: conversion moved to private QQ/WeChat in 48h — census the OVERSEAS boards: OKX/Gate
  CN sections); KR=Naver cafe open boards + coin community 장터 sections (respect by-name robots
  refusals first); JP=5ch is name-blocked, use archived mirrors; BR/TR=Telegram-channel public
  previews (t.me/s/) carry the same ad genre. EVERY region: re-census quarterly — rent quotes
  move with the barrier, and the TIME SERIES of quoted rent ladders is itself a barrier-height
  proxy no vendor sells.
counterfactual: HIGH — the diaspora question stood open across multiple RU sessions; the answer
  was one public GET away the whole time. The class error was hunting DISCUSSIONS about where
  people went instead of reading the market that formed where they arrived.

_OP-049 EXTENSION (RU s2-on-branch, 08-12): a dealer's TWO-SIDED fee ladder is a FLOW-DIRECTION
gauge, not just a rent quote. Read IN vs OUT fees per instrument-leg: symmetric fees = balanced
flow; a SIGN FLIP (customer PAID a premium on one side — btcsec 3426: BTC-E RUB-codes IN "от 3%
премия" while RUB OUT charged 7%) = one-directional net retail flow, with the asymmetry
magnitude pricing the direction. This is the graveyard demand-direction variable (7th/8th
instances) read as an INSTRUMENT: era fee-ladders are point-in-time flow-direction records no
vendor archives, and modern P2P ad ladders (the OP-049 census) carry the same readable sign.
Per-region: works on any dealer-ad genre with quoted two-sided pricing. Trap: slug/URL numbers
are punctuation-stripped ("ot-18" = 1.8%) — read the thread body, never the slug, for fees._

_OP-034 field note (RU s1-on-branch, 08-04): Wayback REPLAY of querystring URLs (IPB/IPS
`index.php?/topic/...`) 302s to the canonical capture timestamp — curl WITHOUT -L writes 0
bytes, which looks exactly like a dead capture. It is the route, not the archive. Always `-L`
on replay; CDX hit + 0-byte replay = redirect trap until proven otherwise (pairs with OP-030)._

### OP-050 Apollo-SSR platforms: the API lies politely, the page tells the truth   [active]
class: operator
origin: KR frontier miner (2026-08-04, velog.io) — but the pattern is platform-class-general
  (any Apollo-GraphQL + SSR site: velog, some Medium clones, many Next.js community platforms).
what: velog's keyless GraphQL (`v3.velog.io/graphql`, introspection OPEN) has FOUR silent-failure
  modes that each look like "no data" and are actually route defects:
  (1) INVALID FIELD → HTTP 200 with EMPTY BODY, not a GraphQL error object (bare `username` vs
      correct `user { username }` cost 8 queries before bisection found it). Bisect the field list
      before concluding an endpoint is dead — same law as OP-034's gzip-sniff: 200 ≠ content.
  (2) STRICT-AND search: compound native phrases 0-hit while single folk terms hit
      (업비트 자동매매=0 but 업비트 API=486; 호가창=157). Search SINGLE terms, intersect client-side.
  (3) NO-MATCH FALLBACK: an unmatched query returns the GENERIC corpus with count=10000 sentinel —
      a plausible-looking result set with zero relevance. Treat count=10000 as "no match".
  (4) STALE INDEX: search returns DELETED posts (the best kimchi-arb-bot lead 404'd on read, no
      Wayback capture). 404-check before carding anything from a search index.
  RECOVERY ROUTE: when GraphQL `post.body` is null but the post is live, the SSR page embeds the
  full content in `window.__APOLLO_STATE__` — `json.JSONDecoder().raw_decode()` past the trailing
  JS. Comments, user objects and series structure ride in the same cache.
validated-gain: 6-post deep-read corpus (data/velog_kr_quant_posts.jsonl) including 2 bodies the
  API refused; the 486/207/157/55/20 term-count map of the KR practitioner corpus.
adaptations: KR=velog (this entry); CN=check Gitee Pages/juejin for the same Apollo pattern;
  ALL=any `__APOLLO_STATE__` / `__NEXT_DATA__` / `__NUXT__` blob outranks the public API when the
  two disagree. Pair with OP-038 (HTML-vs-API split) — this is its inverse: API walled, page open.

## LEXICON — KR crypto-trading jargon (dark-forest search keys)
_Charter dark-forest deliverable #2, KR seat. Convention per EN/CN lexicons: term | gloss | era |
example query. OBSERVED = verified in a real search/post this session; SEED = from the seat brief,
not yet field-verified — verify before building queries on them._
| term | gloss | era | note / example query |
|---|---|---|---|
| 김프 | kimchi premium (김치 프리미엄 abbrev) | 2017→live | OBSERVED — **COLLISION: also the KR transliteration of GIMP** (image editor); "김프 설치하기" = installing GIMP. Disambiguate: search 김치프리미엄, or 김프 with 코인/바낸/역프 context. velog: 김치프리미엄=55 |
| 역프 | REVERSE premium (KR below global) | 2018→live | SEED (seen in passing this run, not yet used as a key) — the sign-flip regime the CN premium-SIGN law predicts for coin-leg barriers |
| 오지급 | mis-credit / erroneous payout | live | OBSERVED — venue-incident search key; found the Bithumb 2026-02-06 620k-BTC event (data fence now on watchlist card #4). Query: <venue> 오지급 |
| 호가창 | order book (lit. quote window) | all | OBSERVED — velog 157 hits; the KR word for L2/orderbook content, finds microstructure builds that "orderbook" never will |
| 펀딩비 | funding rate/fee | 2020→live | OBSERVED — velog 20 hits; perp-funding content key |
| 자동매매 | auto-trading | all | OBSERVED in titles — pair with venue name as SINGLE terms (OP-050 strict-AND) |
| 재정거래 | arbitrage (formal/textbook term) | all | OBSERVED 0-hit as compound on velog — KR retail says 김프/갭 for the premium trade, NOT 재정거래; the formal term finds textbooks, the folk term finds practice (OP-030 lexical-zero class) |
| 한강 수온 | "Han river water temperature" — rekt/despair meme (한강 = where blown-up traders go) | 2017→live | OBSERVED live: coincoin.kr ships a real-time Han-river water-temp widget as a joke; 한강 posts = capitulation-sentiment marker in era archaeology |
| 떡상 / 떡락 | moon / crash (tteoksang/tteokrak) | 2017→live | SEED — era boards; not yet used as a key this run |
| 존버 | diamond-hands / hold through pain (jonbeo) | 2017→live | SEED — era boards; not yet used as a key this run |

### OP-051 community annual series (advent calendars / year-end retrospectives) as finite era-stratified corpora   [active]
class: source-expansion
origin: JP frontier miner s1-on-branch (2026-08-04, Qiita 仮想通貨botter Advent Calendar)
validated-gain: 187 practitioner entries across 5 years mapped in 5 fetches (data/
  jp_botter_advent_calendar.jsonl); 5 deep-reads yielded 3 graveyard entries (one with a full
  dated 2017→2024 venue-rule lifecycle), a live-family fence checklist (R0021), 1 watchlist
  card, and a dated triple era boundary (2024-03: SFD abolished + 12H ATR-reversion died +
  regime shift) — density far above ambient blog mining.
technique: developer platforms run ANNUAL themed series (JP: Qiita/Adventar advent calendars —
  25 slots/day/series, community-curated; analogues elsewhere). These are the highest-yield
  entry point into a regional practitioner community because they are (1) FINITE and countable
  — a mapped calendar is an exhaustible ground with honest progress tracking, unlike an open
  blog firehose; (2) DATED — era stratification for free (compare the same community's topics
  across years to read diaspora/pivot: JP 2021 CEX-bot-heavy → 2024-25 DEX/atomic/Hyperliquid-
  heavy); (3) CURATED BY THE COMMUNITY — the year's respected voices self-select; (4) in
  post-mortem cultures (JP botters publish EXHAUSTED edges, never live ones) the series is a
  decay-date mine: hunt "その後/消えた/思い出/振り返り" (what-happened-after / vanished /
  memories / retrospective) titles FIRST. Extraction: the calendar page embeds the full entry
  table machine-readably (Qiita: react-on-rails `data-component-name` JSON block — largest
  application/json script tag carries adventCalendars.tableAdventCalendars[].items[] with
  url/title/author/day); one fetch per year replaces per-entry discovery.
adaptations: JP=Qiita `advent-calendar/<year>/botter` (+ マケデコ market-making calendar, same
  platform, untouched); KR=velog/tistory 회고 (year-end retrospective) tag sweeps; CN=Zhihu
  年终总结/复盘 + juejin 年度征文 collections; RU=habr "итоги года" tag; EN=r/algotrading
  year-in-review threads + QuantConnect yearly writeup roundups. Adventar.org itself is
  ClaudeBot-blocked (universe row 94) — platform robots gate each instance, check per ground.
counterfactual: LOW-MED — English-language quant research never reads these (language moat,
  OP-017), and even JP-fluent crawlers read entries individually; treating the SERIES as a
  finite mapped corpus with decay-title triage is desk discipline.

_OP-050 addendum (JP miner, 08-04): the Rails equivalent of `__APOLLO_STATE__`/`__NEXT_DATA__`
is react-on-rails `<script type="application/json" data-component-name="...">` blocks — on
Qiita the CALENDAR component carries the full data table, but ARTICLE bodies live in a
server-rendered `div#personal-public-article-body` NOT in the component JSON: on hybrid-SSR
platforms check BOTH the state blob and the rendered DOM before concluding content is
API-only. note.com bodies: `div.note-common-styles__textnote-body` in plain HTML (robots-legal
page route; its /api/* is disallowed)._

### OP-052 robots.txt is NOT the access policy: probe the CONTENT PATH with your own UA   [active]
class: legitimacy-gate / §13 instrument
origin: JP frontier miner (2026-08-12), found by re-verifying robots on entry per standing law
validated-gain: caught note.com + zenn.dev refusing this desk's named agent AT THE CDN EDGE while
  both robots.txt files are CLEAN of any ClaudeBot rule. 116 of the JP seat's 187-entry mapped
  corpus (62%) is out of bounds, including all three of that run's planned deep-read targets. Two
  prior JP sessions (08-01, 08-04) read note.com bodies successfully, so the change is DATED to
  between 2026-08-04 and 2026-08-12 — a live rollout, not a standing condition.
technique: every seat establishes §13 posture by reading `robots.txt`. **That is necessary and no
  longer sufficient.** A CDN can carry an access policy the published robots.txt does not state,
  and the two can disagree in either direction. Establish the posture with a UA MATRIX against a
  real content path, not a policy file:
  ```
  for ua in ClaudeBot GPTBot CCBot Bytespider Claude-User Googlebot SomeRandomBot/1.0 curl/8.0; do
    curl -s -o /dev/null -w "$ua %{http_code}\n" -A "$ua" "<a real article url>"; done
  ```
  READ THE SHAPE, because the shape is the finding:
  * **our agent 403, generic bot 200, Googlebot 200** → a CURATED AI-CRAWLER DENYLIST. This is a
    deliberate, legible policy about bulk AI collection. Measured on note.com: ClaudeBot/GPTBot/
    CCBot/Bytespider all 403 while `SomeRandomBot/1.0` and `curl/8.0` get 200 — which PROVES it is
    not a generic "non-browser UA" heuristic. **HARD STOP, archives included** (origin-domain
    policy governs Wayback mining too, per the RU/btcsec fleet ruling).
  * **everything 403 including browsers** → infrastructure/WAF, may be transient; re-probe later.
  * **robots.txt itself 403s to our UA** → the edge is filtering before the policy layer; read the
    policy with a neutral UA (you cannot comply with a policy you cannot read) and then apply the
    content-path verdict. Reading the POLICY is not routing around access control; fetching BODIES
    under a different UA is, and it is forbidden.
  **THE TRAP THAT MAKES THIS URGENT, and it is not about robots at all:** a blocked ground and an
  exhausted ground look IDENTICAL to a digger whose fetch path treats a non-200 as "no content".
  The seat then records **"this ground is thin"** when the truth is **"we are blocked"** — opposite
  facts, and the wrong one silently retires a whole region (WS-005 / L1.28a: absence must never
  resolve to a clean verdict). Any seat reporting thinning ground on a previously-rich source must
  run the UA matrix BEFORE writing that verdict.
  **`Claude-User` returning 200 is a FACT TO RECORD, NEVER A ROUTE TO USE.** It is the
  user-initiated-fetch agent; bulk-mining 91 posts under it is the same activity the venue denied,
  wearing a different name. Log it so a future principal decision has the evidence, and stop.
adaptations: JP=note.com **CLOSED** (2026-08-12), zenn.dev **CLOSED**, qiita.com **OPEN** (article
  body served, 145 kB), adventar.org CLOSED (robots-stated, 08-04); KR=re-probe velog/tistory,
  DCInside already robots-stated; CN=Gate WALLED at edge-403 (CN seat 08-12 — SAME CLASS, found
  independently the same day and previously read as a site-specific quirk rather than an instance);
  RU=re-probe habr/smart-lab; EN=Wilmott CF-403 on robots (08-12) is this shape one layer earlier.
counterfactual: HIGH — without the matrix this run would have recorded "note.com deep-reads
  returned nothing" and the JP ground would have looked exhausted rather than closed.

## LEXICON — JP crypto-trading jargon (dark-forest search keys)
_Charter dark-forest deliverable #2, JP seat. Convention per EN/CN/KR tables. OBSERVED =
verified in a real post/text this session (CN OP-037 lesson: 0/7 unverified seeds survived —
only observed terms enter as active keys; unobserved seeds stay marked SEED)._
| term | gloss | era | note / example query |
|---|---|---|---|
| 養分 | "nutrients" = exit liquidity, prey | 2018→live | OBSERVED (Hoheto: 養分にされてしまう; Ros: 他人の爆益で退場). Seed VERIFIED. Query: <strategy> 養分 finds farmed-bot post-mortems |
| イナゴ | swarm-chasers (locusts) | 2017→live | OBSERVED (Hoheto: イナゴ参加者 as hourly-anomaly mechanism prior). Seed VERIFIED. イナゴタワー = pump spike |
| 乖離 | divergence/premium (formal) | all | OBSERVED throughout SFD corpus — THE JP term for spot-deriv premium; 乖離率 = premium %. JP twin of KR 김프 search role |
| SFD / SFD焦らし / SFDファクター | the bitFlyer boundary fee; "SFD teasing" (boundary stall); received/paid ratio | 2018-2024 DEAD | OBSERVED (era-specific). Era-archaeology keys for 2018-2024 bitFlyer content; mechanism graveyarded jp_sfd_boundary_game |
| 買い抜け | escaping a short at boundary−1 tick without paying SFD | 2018-2024 DEAD | OBSERVED (Hoheto's coinage) — appears in SFD-bot writeups only; high-precision era key |
| 現物操作組 / 現物板観測組 | spot-manipulation vs spot-book-watcher bot cohorts | 2018-2024 | OBSERVED (Hoheto) — venue-game ecology vocabulary |
| 担がれる | getting squeezed against a short | all | OBSERVED (both SFD posts) — finds squeeze post-mortems |
| ドテン君 | THE published-then-farmed reversal bot (2018); リメンバードテンくん = cautionary meme | 2018→ | OBSERVED (Hoheto) — era incident marker; query ドテン君 finds the publish-your-logic-get-farmed literature |
| 老人会 / bF民 | "elders' club" (2018-era veterans) / bitFlyer folk | 2020→live | OBSERVED (both posts self-describe) — finds era memoirs |
| C級/A級/S級botter | botter class ladder (C ≈ ¥10k/mo … S = professional) | 2021→live | OBSERVED (multiple calendar titles) — S級 finds the serious-capital cohort's writeups |
| 億り人 | "100-millionaire" (made ≥¥100M) | 2017→live | OBSERVED in derived form only (億ウォレ pun, 2024 calendar title). Seed WEAK-VERIFIED |
| ガチホ | hard hold (gachi-hold) | 2017→live | SEED — NOT observed this run; do not build queries on it yet |
| 爆益 / 退場 | explosive profit / blown-out exit | 2017→live | OBSERVED (Ros) — 退場 finds ruin post-mortems |
| 鞘 (さや) | the arb spread itself; 鞘取り = arbitrage | all | OBSERVED (shidokamo, DEX-CEX post: 「DEX-CEXの鞘が10%」). THE JP word for a spread — 乖離 is the *state*, 鞘 is the *harvestable gap*. Query: 鞘取り bot finds arb writeups that 裁定取引 misses |
| アビトラ | arbitrage (katakana clip of arbitrage) | 2017→live | OBSERVED (shidokamo title 「DEX-CEXアビトラの思ひ出」). Retail/botter register; the formal 裁定取引 finds academic/broker content instead. HIGH-VALUE KEY |
| 見せ板 | spoofing (lit. "show board") | all | OBSERVED (blog_UKI, BitMEX spoofing post). The folk term; スプーフィング is the loan-word used in titles. Query 見せ板 finds manipulation-mechanics discussion |
| お蔵入り | shelved / never shipped (of a strategy) | all | OBSERVED (blog_UKI: 「この戦略はお蔵入りしたのでした」). **A NEGATIVE-RESULT KEY** — finds abandoned strategies with stated reasons, i.e. free graveyard material |
| 反面教師 | cautionary counter-example ("teacher by negative example") | all | OBSERVED (perp-screener: 「反面教師になればうれしい」). Authors flag their own failures with it — pairs with お蔵入り as the JP failure-post search pair |
| チャッピー | ChatGPT (JP affectionate nickname) | 2023→live | OBSERVED (perp-screener: 「チャッピーの解説によると」). **NOT a trading term — an LLM-CONTAMINATION MARKER (OP-072).** Grep it to demote a page from independent node to echo |
| 限月 | contract expiry month (futures/options) | all | OBSERVED (perp-screener). 期近 = near expiry, 期先 = far expiry — the JP calendar-spread vocabulary |
| 爆損 | catastrophic loss (mirror of 爆益) | 2018→live | OBSERVED (マケデコ title 「機械学習モデルが爆損したときにやること」). Ruin-post key |
| キムチパンプ | "kimchi pump" — KR retail chase filling a listing/TGE pop | ~2021→live | OBSERVED (rarirure 2024: 「Tier1なりキムチパンプによって暴騰」 as the named driver of listing TP-reach). JP practitioners attribute listing-pop fills to KR retail flow — a cross-region flow prior AND a search key for listing-mechanics posts |
| 脳筋 / 脳筋bot | "musclebrain" — no-model, speed/simplicity-only bot logic | ~2020→live | OBSERVED (rarirure title). Self-deprecating genre marker for latency/news-race bots; finds the simple-mechanism posts the ML-heavy corpus buries. Query: 脳筋 bot 仮想通貨 |
| 鉄火場 | gambling den = a fresh/chaotic market window (TGE, listing day) | all | OBSERVED (shidokamo starter-trader: 「鉄火場ではスピードが命」「正確さより早さ」). PROCESS vocabulary: posts using it discuss speed-vs-rigor tradeoffs in short-runway windows — the capacity-runway race from the retail side |
| 野良SDK | "stray SDK" — unofficial community venue client | ~2020→live | OBSERVED (rarirure: fears malicious-code injection, greps then FORKS every dependency; found MEXC's stray Go SDK doing a TCP handshake per request). Supply-chain vocabulary + a venue-SDK-quality tell |
| 無限買い | "infinite buying" — leveraged always-buy DCA bot class | 2023→live | OBSERVED (shidokamo 「Botで気軽にビットコイン無限買い」, serverless-ape-bot). Names the levered-accumulation genre; its posts carry margin/liquidation-management folk practice |
| アシスタンスファンド / AF | Hyperliquid's official buyback fund (support bid) | 2024→live | OBSERVED (shidokamo: unannounced AF buyback as HYPE's floor support — condition (3) of the TGE dip template). An OBSERVABLE support-bid actor; search key for HL-mechanics posts |
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
| 유의종목 | yuui-jongmok | "investment-warning designation" — Upbit/Bithumb's formal caution label | ✓ CONFIRMED live in the venue API (`market_event.warning`); the KR delisting-risk event word |
| 상장 / 신규 거래지원 | sangjang / singyu georaejiwon | listing. 상장 = retail register; **신규 거래지원 안내 = the exact phrase Upbit titles its listing notices** | ✓ CONFIRMED in 737 `category=trade` announcements — use the formal phrase to hit the venue archive, the slang to hit retail threads |
| 거래지원 종료 | georaejiwon jongryo | "trading-support termination" = **delisting**, the venue's own euphemism | ✓ the KR delisting event key; 상장폐지/상폐 is the retail word for the same thing |
| 상폐 | sangpye | delisting (retail contraction of 상장폐지) | retail panic threads around a 유의종목 designation |
| 입출금 | ipchulgeum | deposit/withdrawal — the **rail-state** word | ✓ CONFIRMED as an Upbit announcement category; the barrier-height key |
| 유의 촉구 | yuui chokgu | "caution URGED" — a softer tier BELOW formal designation | ✓ CONFIRMED in the Upbit archive; the early-warning tier most people miss |
| 유의 종목 지정 기간 연장 | ...gigan yeonjang | designation period EXTENDED = the venue saying it is still unresolved | ✓ a distinct, informative event; modelling 유의종목 as binary discards it |
| 원화 / 원화마켓 | wonhwa | "won" — **the EARLY register for what is now written KRW** | ✓ CONFIRMED: `원화 마켓 신규 상장` (18) + `원화마켓 신규 상장` (12, NO SPACE) + `원화 마켓 디지털 자산 추가` (7). Search BOTH spellings AND both spacings or you lose half the KRW-rail events |
| 코인 추가 → 디지털 자산 추가 | ...chuga | "coin added" (2018 register) became "digital asset added" (2020+) | ✓ the same event renamed; an era-blind selector zero-hits 75 rows of it |
| 가두리 | gaduri | "fish-pen / fenced enclosure" — a market whose deposit or withdrawal rail is CLOSED, so price is trapped and runs away from global. Per-ASSET, not per-venue | ✓ OBSERVED (Ppomppu 21343, 2017-12-23 "리플은 이와중에 가두리"). The retail name for the mechanism behind card `kr_rail_state_transition_global_leg`; the folk word finds the lore that 입출금 (the venue's formal word) does not |
| 보따리상 | bottarisang | "bundle/shuttle merchant" — the physical-arbitrage carrier who buys abroad and sells into the KR book. **The era's name for the marginal premium arbitrageur** | ✓ OBSERVED (Ppomppu 22072, 2017-12-24: "보따리상들이 국내로 코인들고와서 팔아야되는데 지금 코인들 전송이 안됩니다"). THE supply-side premium key: finds threads about why the premium PERSISTS (carrier capacity) rather than that it exists |
| 벌집계좌 | beoljip-gyejwa | "beehive account" — the omnibus/pooled corporate bank account (법인계좌 with many individual sub-accounts under it) small venues used when banks refused them individual 가상계좌 (virtual accounts) | ✓ OBSERVED (Ppomppu 76535, 2018-01-29). The 2018-01 real-name law split KR venues into a virtual-account tier (Upbit/Bithumb/Coinone/Korbit) and a beehive tier — this term is the search key for the venue-tier / rail-access era layer and for forced-exit events at cut-off venues. **PRIMARY LIST RECOVERED (KR s3, 2026-08-13, body of 76535 quoting 한국블록체인협회 as of 01-23): the 7 cut-off venues are CPDAX(법인플러그), 고팍스(스트리미), 코인네스트, 코인이즈, HTS코인(한국블록체인거래소), 코인링크(써트온), 이야랩스** — users ~500k/350k/151k/57.6k/55k/14k/10k, >1M total. **AND THE CORRECTION, 44 MINUTES LATER (76551): HTS코인 and 코인네스트 both posted notices calling the report 오보 (false).** Carding the headline without the reply layer would have entered a disputed event as fact |
| 허매수 / 허매도 | heo-maesu / heo-maedo | "fake bid / fake ask" = **spoofed walls** | ✓ OBSERVED (Ppomppu 77829, 2018-01-31: bots posting second-granularity walls). The KR key for retail-observed spoofing/microstructure lore; English "spoofing" zero-hits KR retail boards |
| 한프 / 코프 | hanpeu / kopeu | premium abbreviations formed like 김프, almost certainly per-venue or per-country (한국/코인원?) — **gloss UNVERIFIED, recorded as observed rather than guessed** | SEED (Ppomppu 22072 title: "한프 김프 코프 하는데 궁금점요"). Worth resolving: if these are per-VENUE premium words the era had a folk vocabulary for intra-KR dispersion, which is exactly the WS-011 axis |

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

### OP-041 read robots.txt BEFORE you dig — the ground list is not an authorisation   [active]
class: legitimacy / ground-selection
origin: KR frontier miner session 1 (2026-08-01), first run on the KR ground
validated-gain: **three of the five grounds named in that seat's own brief refuse this agent family
  by name**, and nobody had ever checked. `cafe.naver.com` is `Disallow: /` to everyone plus a prose
  header forbidding RAG use; `blog.naver.com` names `ClaudeBot` and `Claude-SearchBot`;
  `gall.dcinside.com` names `ClaudeBot`, `anthropic-ai` and `Claude-Web` under the header
  `# ----- AI 학습 크롤러 차단 -----`. In the same pass it **REVERSED** the desk's standing guess in
  the other direction: `coinpan.com`, which `data_axis_watchlist.md` had excluded as "ToS-grey",
  denies only `/inquiry/`. Cost: five `curl` calls, under a minute.
technique: `curl -s https://HOST/robots.txt` on every ground **before** spending a query on it, and
  read THREE things, not one:
    (a) the `User-agent: *` block — what a generic collector may do;
    (b) **any block naming an AI/LLM crawler** (`ClaudeBot`, `Claude-Web`, `Claude-SearchBot`,
        `anthropic-ai`, `GPTBot`, `OAI-SearchBot`, `PerplexityBot`, `Google-Extended`, `CCBot`,
        `Bytespider`, `cohere-ai`, `meta-externalagent`) — this is the one aimed at YOU;
    (c) prose comment headers, which increasingly carry the operator's stated intent in plain
        language and are not machine-readable at all.
  **THE RULE THAT MATTERS: a permissive `User-agent: *` is NOT a loophole around a block that names
  your family.** Choosing a different UA to slip past a directive aimed at you by name is precisely
  the "routing around a venue's own access control" that §13 forbids. Where the two sections
  disagree, that gap is a PRINCIPAL DECISION, not something a miner grants itself in either
  direction — record the ambiguity rather than inventing a verdict.
adaptations: universal, and the AI-crawler block is spreading fastest through **consumer-web
  portals** (KR: Naver, DCInside; JP: Yahoo/note; CN: Zhihu/Weibo) while **developer and venue
  infrastructure stays wide open** (velog.io has zero rules; bithumb.com has no `Disallow` at all;
  exchange APIs are unrestricted). Expect the community layer to close and the API layer to stay
  open — and aim the seat accordingly instead of reporting the ground as thin.
counterfactual: HIGH and BIDIRECTIONAL — without it this seat would have scraped three grounds it is
  named-blocked from, and would have gone on skipping the one KR forum that is actually clean.

### OP-042 a venue's own state flags are a free proprietary axis — and the biggest flag is the artifact   [active]
class: data-axis discovery
origin: KR frontier miner session 1 (2026-08-01)
validated-gain: `api.upbit.com/v1/market/all?isDetails=true` publishes, keylessly and per asset, the
  venue's own `warning` designation plus `caution{PRICE_FLUCTUATIONS, TRADING_VOLUME_SOARING,
  DEPOSIT_AMOUNT_SOARING, GLOBAL_PRICE_DIFFERENCES, CONCENTRATION_OF_SMALL_ACCOUNTS}`.
  `CONCENTRATION_OF_SMALL_ACCOUNTS` is a **retail-crowding measure computed from the venue's
  internal account-level book** — structurally unbuyable from any vendor. Bithumb publishes the
  same warning field plus `public/assetsstatus/ALL`, a per-asset deposit/withdrawal open-closed
  state = **an independent measure of barrier height**.
technique: on every venue, ask what STATE it publishes about its own market, not just prices —
  `isDetails=true`, `assetsstatus`, `system_status`, announcement categories, risk/caution labels.
  Then run the two checks that decide whether it is worth anything:
    1. **DOES IT FIRE?** A flag that is always false or always true carries zero information
       (L1.43). Measure the base rate before believing anything about it.
    2. **SPLIT BY QUOTE CURRENCY BEFORE READING ANY RATE.** `GLOBAL_PRICE_DIFFERENCES` fires on
       **175/803 (22%)** of all Upbit markets and on **1/277 (0.4%)** of KRW markets. The 22% is
       thin USDT/BTC-book illiquidity, not a fiat premium. **The biggest number on the page was the
       artifact**, and only the split catches it.
  And check for a history endpoint: these are **SNAPSHOT-ONLY**, so the series can only ever begin
  the day you start recording (L1.46) — which makes starting cheap and starting late irreversible.
adaptations: universal. Every venue with a retail-protection or risk-labelling regime publishes
  something like this (KR 유의종목; JP JVCEA designations; EU MiCA disclosures). Regulated retail
  venues are the richest ground because the labels are compliance obligations, so they are
  published on a schedule and cannot quietly stop.
counterfactual: HIGH — this seat's assigned community ground was 100% closed, and this is the axis
  that replaced it. Found only by asking a venue API what it publishes BESIDES prices.

### OP-038 REFINEMENT (KR frontier miner, 2026-08-01): the wall can be at the CDN EDGE
OP-038 says a JS wall on the HTML is not a wall on the API, and it is right — but it has a boundary
that cost this run its only clean KR forum. **`coinpan.com` returns Cloudflare's `Just a moment...`
interstitial on `/`, `/free`, `/rss` AND `/index.php?mid=X&act=rss` alike — HTTP 403 on every
content route, with only `/sitemap.xml` serving.** When the challenge sits at the CDN edge rather
than in the page renderer, the API and feed routes are behind the SAME wall and OP-038's split does
not apply. **Diagnostic:** if the JSON/RSS route returns the same interstitial HTML as the page,
the wall is at the edge — stop, and grade the venue WALLED. Solving the challenge is defeating an
access control (§13 HARD STOP), and it stays walled no matter how good the scraper gets.

### OP-035 EXTENSION (KR frontier miner, 2026-08-01): the CONVENTION changes, not just the markup
OP-035 warns that a selector validated on one era zero-hits another because the **markup** changed.
The same failure arrives through **the source's own vocabulary**, and it is harder to see because
nothing errors — you simply get a smaller number and believe it. **Measured on Upbit's own
announcement archive: 332/680 rows (49%) fell through a selector fitted on modern titles.** In eight
years the venue renamed its event classes at least five times — `코인 추가` → `디지털 자산 추가`,
`원화 마켓` → `KRW 마켓`, `상장` → `신규 거래지원` — **and shipped a whitespace variant of its own
term** (`원화 마켓` vs `원화마켓`). The pure rail-access event class was **43 by modern keys and
~83+ in truth**.
**TECHNIQUE — do this before trusting any count off an archive you did not write:**
  1. Bucket rows **per year** and check the per-class count against total volume. A class that
     starts abruptly mid-archive (`신규 거래지원`: zero before 2024-04-23) is a **rename**, never a
     behaviour change — the events did not begin then, the words did.
  2. **Strip parentheticals and symbols, then histogram the title TAILS** (`title[-28:]`). Recurring
     stems fall out immediately and hand you the era forms you never guessed.
  3. Report **UNCLASSIFIED as a first-class number.** A classifier that silently drops half the
     archive looks exactly like a classifier that works.
  4. Search the OLD register AND the new one AND their spacing variants — non-segmenting scripts
     (KR/JP/CN) make whitespace optional, so one term is genuinely two search keys.
**Why this matters beyond hygiene:** an era-fitted selector biases coverage toward the RECENT era,
which is the crowded one. The dark-forest premium is in the old era, and this defect silently
deletes it while the run still reports a healthy count.

---

### OP-043 diagnose a block by varying ONE thing against the SAME edge IP   [active]
_Added by JP frontier miner, session 1, 2026-08-01._

**Problem it solves.** A digger hits a host, gets nothing, and writes "our IP is blocked" or
"WAF 403" in the card. That verdict then propagates as fact, downgrades the source, and — worst
case — creates a *human dependency* ("someone please open this page for us"). It is usually a guess,
because the probe varied nothing.

**The operator.** Before recording ANY block verdict, run the 2x2 against the same target:
1. **Sibling hostname** on the same service (`api.`, `docs.`, `lightning.`, `public.`, `static.`)
2. **IP family** (`curl -4` vs `-6`) — and **record `%{remote_ip}`**, always
3. **HTTP version** (`--http1.1` vs h2)
4. **Exact failure shape**: `curl -sv` and read whether it is a status code, a TLS failure, a
   silent hang (`code=000`), or a stream error. **A tarpit and a 403 are different findings.**

**Worked instance, and it overturned a standing card.** `bitflyer.com/ja-jp/terms` was recorded as
"403, WAF-blocked, cannot be defeated, needs a human". Actual: TLS completes, cert verifies,
HTTP/2 stream opens, then `INTERNAL_ERROR (err 2)`; on HTTP/1.1 and on IPv4 it **hangs to timeout**
(`code=000`) — an Akamai tarpit, never a 403. And **`api.bitflyer.com` + `lightning.bitflyer.com`
both return 200 from the identical edge IP `2a02:26f0:e80:588::2644` that tarpits the apex.** Same
node, same TLS, different `Host` header. So the policy was **per-hostname on the marketing/legal
site**; the API and docs hosts were open the whole time.

**Why it matters beyond one card.** "Our IP is banned" and "this one hostname is bot-managed" imply
opposite next moves: the first says give up or buy a proxy, the second says *use another hostname*.
Getting it wrong bought a 4-session deferral and a paid-proxy argument that was never needed.
Same family as OP-038 (a JS wall on the HTML is not a wall on the API) one layer down the stack.

**Per-region adaptation.** CN/KR/JP venues commonly bot-manage the *retail marketing* domain hard
while leaving `api.*` / `public.*` wide open, because the API host must serve their own trading
clients. Always try the API host before declaring a venue unreachable.

---

### OP-044 a negative CDX result is a statement about your QUERY, not about the archive   [active]
_Added by JP frontier miner, session 1, 2026-08-01._

**Problem it solves.** "Wayback has nothing" is one of the cheapest false negatives in the digger's
repertoire, and it is almost always a wrong *query*, not an empty archive. It reads as thorough
because a CDX call was genuinely made.

**The operator.** Before concluding a page was never archived, vary — in this order:
1. **HOST, including the pre-migration domain.** Companies migrate ccTLD → .com and Wayback keys on
   the host that existed *then*. Check the old domain even if it no longer resolves today.
2. **SLUG.** `terms` / `terms-of-use` / `tos` / `agreement` / `kiyaku` / `規約` / `legal` / `policy`
   are not interchangeable and CDX prefix-matching will not bridge them.
3. **Drop to `matchType=domain`** and grep the whole key list, rather than guessing paths.
4. **Locale segment**: `/ja-jp/`, `/en-jp/`, `/en-eu/`, `/en-us/`, bare.

**Worked instance.** A card recorded: "CDX domain queries for `bitflyer.com/{en-jp,ja-jp}/*` return
no terms captures — bitFlyer's JS app was never usefully archived", and deferred the item on it.
The pre-migration host is **`bitflyer.jp`** and the slug is **`terms-of-use`**, not `terms`. The
corrected query returned `https://bitflyer.jp/en-eu/terms-of-use` (2019-06-01, **200**) plus
`bitflyer.jp/pub/terms-comparison-table-201711-ja.pdf` on the first try — and that capture contained
the exact IP clause the desk had been deferring on for four sessions.

**Bonus that falls out of step 3.** The full-domain key dump is itself a find: the same sweep
surfaced `bitflyer.jp/api/chart/btc_jpy?start=&end=`, an **undocumented keyless price endpoint, dead
on the live site, captured 200 from 2015**. You cannot discover an endpoint you never listed —
so run the domain dump even when you are hunting something else.

---

### OP-045 `success: 1` is not `data: real` — structural-zero test before trusting pre-launch history   [active]
_Added by JP frontier miner, session 1, 2026-08-01._

**Problem it solves.** A venue endpoint that answers `success:1` with well-formed, *moving* OHLC for
dates **before the venue existed**. Nothing in the response says so. A collector ingests it, a
backtest trades it, and the phantom era silently sets the in-sample regime.

**The operator.** For every historical series, before ingesting: pull the **earliest** window and
count rows where a *liquidity* column (volume, trade count, notional) is **exactly zero**. If there
is a contiguous leading block of structural zeros, the venue is serving a **reference/index series**,
not its own tape. Find the first non-zero bar and treat that as the true start — never the API's.
Cross-check against the venue's publicly-known launch date.

**Worked instance.** `public.bitbank.cc/btc_jpy/candlestick/1day/{YYYY}` returns
`success:1` for **2014, 2015 and 2016** — 362, ~365 and 363 daily bars, OHLC populated and moving
(`79324, 79546, 78476, 79516`). **Volume is `0.0000` on every single one of those bars.** First
non-zero volume is `1487030400000` = **2017-02-14**, bitbank's actual BTC/JPY launch. So the
endpoint hands you **~1,100 untradeable phantom bars** with a success flag on top.
The price path is *not* flat, so no eyeball sanity-check catches it — only the volume column does.

**Generalises past candles.** Any series where the venue backfills from a third-party index:
funding rates before the perp launched, open interest before the product listed, "since inception"
marks on a relisted ticker. **The tell is always a liquidity column that is structurally zero while
a price column moves.**

---

### OP-041 REFINEMENT (JP frontier miner, 2026-08-01): the ClaudeBot block is CLOUDFLARE-MANAGED, so treat it as a PLATFORM rollout, not a site decision

OP-041 (read robots.txt before you dig) fired again on a second region in two days: **5ch.net and
every sister host (`itest.`, `egg.`, `kizuna.`) carry `User-agent: ClaudeBot` → `Disallow: /`.**
Two refinements the fleet should carry:

1. **READ THE DELIMITERS.** The 5ch block sits inside
   `# BEGIN Cloudflare Managed content` … `# END Cloudflare Managed Content`, emitting a *standard*
   AI-crawler list (`ClaudeBot`, `GPTBot`, `CCBot`, `Google-Extended`, `Applebot-Extended`,
   `Bytespider`, `meta-externalagent`, `CloudflareBrowserRenderingCrawler`). This is **not a
   judgement 5ch made about us** — it is a toggle in a CDN dashboard. So the correct prior is no
   longer "some sites block us" but **"any Cloudflare-fronted community site is likely to refuse
   this agent by name"**, and the robots check is therefore *cheapest first, per ground*.
   Corollary: this list will keep growing as the feature rolls out. A ground that was clean last
   month is not known-clean today — **re-check on entry, do not cache the verdict**.
2. **A PERMISSIVE `User-agent: *` IS NOT A PERMISSION.** The same 5ch file grants
   `Content-Signal: search=yes, ai-train=no, use=reference` and `Allow: /` to `*`, which read alone
   would have produced a clean "reference use is fine" verdict. The **named-agent `Disallow: /`
   overrides it.** The KR seat warned of exactly this loophole on 2026-08-01; this is the
   independent second-region confirmation. Always grep the file for the agent BY NAME before
   reading the generic block.

### OP-046 stdlib-only .xls (OLE2 + BIFF8) extraction — the xlrd blocker is false   [active]
class: verification / extraction
origin: BR frontier miner session 1 (2026-08-01), on the Receita Federal crypto open-data file
validated-gain: the desk's box has **no xlrd, no openpyxl, no olefile** and installs are frozen, so
  `pandas.read_excel` cannot open a `.xls` at all. That would have reduced a **576 KB national
  mandatory-reporting dataset** (77 months × 4 report tables + a 4,206-row per-asset panel) to a
  screenshot-grade citation. Written from the format specs in ~200 lines of pure stdlib (`struct`
  only) and it read every sheet correctly on the first validated pass.
technique: exactly the OP-025 premise one format across — do NOT conclude "this box cannot read
  `.xls`" from a missing library. A legacy `.xls` is two documented layers and both are byte-level:
    (1) **OLE2 / Compound File**: header at 0x1E→sector shift, 0x2C→#FAT sectors, 0x30→dir start,
        0x3C→miniFAT, 0x44/0x48→DIFAT. Sector *n* lives at `(n+1)*sectorsize`. Walk DIFAT→FAT→chain.
        Directory entries are 128 B (UTF-16LE name, type at 0x42, start 0x74, size 0x78).
        **Streams < 4096 B live in the miniFAT inside the root entry's stream** — miss that and small
        sheets vanish silently.
    (2) **BIFF8 records** in the `Workbook` stream: `<HH>` opcode+length, then walk. Cells:
        `0x00FD` LABELSST (index into SST), `0x0203` NUMBER (f64), `0x027E` RK, `0x00BD` MULRK,
        `0x0204` LABEL. `0x0085` BOUNDSHEET names each sheet. **RK decoding**: bit0 ⇒ ÷100,
        bit1 ⇒ signed int `v>>2`, else the top 30 bits are the HIGH half of an IEEE double
        (`(v & 0xFFFFFFFC) << 32`).
  **THE TWO BUGS THAT PRODUCE PLAUSIBLE-BUT-WRONG OUTPUT, both hit live in this run:**
  **(a) SHEET COLLISION.** Keying cells on `(row, col)` merges every sheet into one grid. It does not
  crash and it does not look wrong — it produced a row reading `CRIPTOATIVO | MÊS/ANO | ... | 899.79
  | 990.46`, a header spliced onto another report's numbers. **Cells carry no sheet id; the only
  attribution is the record's absolute stream OFFSET compared against the BOUNDSHEET positions.**
  **(b) SST CONTINUE BOUNDARIES.** The shared-string table spans `0x003C` CONTINUE records and **the
  1-byte compressed/wide flag REPEATS at every continuation boundary, mid-string**. Ignore it and
  strings silently become mojibake from the boundary onward.
  **THEN VALIDATE WITH OP-024 BEFORE TRUSTING ANY NUMBER** — see the counterfactual.
adaptations: universal and language-independent (byte-level). Government, regulator, central-bank and
  exchange publications are **disproportionately legacy `.xls`** precisely because they are old
  institutional pipelines — which is the same reason they are under-mined. Same move applies to `.doc`
  (OLE2 + WordDocument stream) and `.ppt`. `.xlsx` needs none of this: it is a zip of XML.
counterfactual: HIGH, and the **validation** is the transferable half. Rather than diff the PDF twin
  (whose text layer is CID-encoded and would have needed its own unvalidated extractor), the file's
  own **arithmetic identities** were used: PF+PJ=Subtotal and Subtotal₁+Subtotal₂+Domestic=TotalGeral
  across **78 monthly rows → 0 violations, worst residual exactly 0.00e+00**. That is a far stronger
  proof than text agreement, because it spans three independent column groups **and both RK- and
  NUMBER-encoded cells**, so a decoder bug in either could not cancel. **Pair every hand-rolled
  binary extractor with a conservation law from inside the data (OP-024); an extractor validated only
  by "it looks right" is a phantom-evidence factory (OP-025's own warning).**

### OP-047 a dated-filename publication series is a FREE POINT-IN-TIME PANEL — and its latest file is a look-ahead trap   [active]
class: data-axis discovery / leak-prevention
origin: BR frontier miner session 1 (2026-08-01), Receita Federal `criptoativos_dados_abertos_<date>`
validated-gain: **measured, not argued.** Three vintages of the same series were parsed and diffed:
  **39 of 42** common months changed within **3 months**; **42 of 42** changed by the latest vintage;
  worst **Março-2023 R$15,828mn → R$22,308mn (+40.9%)**; and a month **2.4 years old** at first
  publication still moved (+2.5% value, **+13.9% unique-taxpayer count**). Revisions are
  **systematically upward** — late and amended filings accrue for years.
technique: whenever an institution republishes a whole dataset under a **dated filename or URL**
  (`..._20260415.xls`, `report_2024Q3.pdf`, `data_v7.csv`), you are not looking at one dataset. You
  are looking at a **stack of vintages**, and:
    1. **THE CURRENT FILE IS THE LEAKY ONE.** Its historical rows carry information that did not
       exist on those dates. Backtesting it embeds a look-ahead **in the conditioning variable** —
       the R0289 class (a value whose as-of date ≠ its event date), which fails toward a **false
       result** and is invisible to every return-series leak check, because the RETURNS are spotless.
    2. **THE FIX IS FREE.** Enumerate the vintages (Wayback CDX + the live directory), download each,
       and key every observation by `(reference_month, vintage_date)`. You now hold what was
       *actually knowable* on each date — the thing vendors charge for and mostly do not have.
    3. **RECOVER DEAD VINTAGES WITH THE RAW-REPLAY MODIFIER.** Publishers delete old files: 2 of 4
       tried were **404 on the live server**. `https://web.archive.org/web/<timestamp>id_/<url>`
       returns the **unrewritten original bytes** — verified here recovering a 282,624 B `.xls` with
       an intact `d0cf11e0` OLE2 magic. Without `id_`, Wayback injects its banner and corrupts binaries.
    4. **THE REVISION IS ITSELF A SERIES** — `revision(t, v)` measures reporting completeness and lag,
       and is a candidate axis in its own right, not just a hazard to neutralise.
  **AND THE COST OF NOT DOING IT IS ASYMMETRIC:** a revised-data backtest overstates, so it produces
  FALSE POSITIVES that survive to a forward clock and waste a Holm slot.
adaptations: universal, and richest where reporting is **compelled and late-arriving** — tax
  authorities, central banks, regulators, statistical offices, exchange volume reports, on-chain
  indexers that reorg. Macro desks call this a real-time/vintage database (ALFRED, OECD); crypto has
  essentially none, so building one from a government file series is a genuine asymmetry (L1.11a).
counterfactual: HIGH. The axis reads as an ordinary monthly macro series; only diffing two vintages
  reveals that **every single historical value is wrong by construction** in the obvious build.

### OP-035 EXTENSION (BR frontier miner, 2026-08-01): the SCHEMA changes between eras, not just the markup — and column ORDER is the silent one
OP-035 (a selector validated on one era zero-hits another) and its KR extension (the *convention*
changes) both describe failures that **produce nothing**, so you notice. The BR instance is the
dangerous inversion: **it produces a full, plausible, wrong series.** Across vintages of one
government file the following all moved:
| What changed | 2022 vintage | 2026 vintage | Failure if unhandled |
|---|---|---|---|
| **Column ORDER** | `MÊS/ANO \| CNPJ \| CPF` | `MÊS/ANO \| CPF \| CNPJ` | **~80× error** — CNPJ ≈2k read as CPF ≈160k, still a plausible count |
| Row offset of first data row | 10 | 8 | header parsed as data, or 2 months dropped |
| Number encoding | **text** `160.589` (BR thousands sep `.`) | native numeric | `float("160.589")` = **160.589**, not 160,589 — a **1000× silent error** |
| Column label | `Exchanges / Somente PJ` | `Exchanges no Brasil*` | label-matching parser zero-hits |
| Filename date code | `DDMMYYYY` (`07082023`) | **`YYYYMMDD`** (`20260415`) | enumerator silently misses a whole era |
**THE RULE: parse by HEADER SEMANTICS per vintage, never by cell address — and re-derive the header
for every vintage rather than once.** A fixed-offset reader over a multi-vintage series is not a
scraper, it is a random number generator with good manners. **The `160.589` case is the one to fear:
locale-dependent decimal separators mean a wrong-but-parseable float, and no exception is ever raised.**

### OP-041 CORRECTION (BR frontier miner, 2026-08-01): the AI-crawler block is REGIONAL, not global — do not carry a region's verdict forward as a prior
OP-041 fired on two consecutive first-run seats (KR: 3 of 5 grounds named-blocked; JP: 5ch + all
sister hosts), and its adaptation note generalised that to *"expect the community layer to close and
the API layer to stay open."* **A third region falsifies the general form.** An 18-host full-file
sweep of the BR ground (bastter, InfoMoney, MQL5, Investing BR, bitcointalk, YouTube, Telegram,
SmarttBot, Nelogica, Clear, B3, BCB, gov.br, Mercado Bitcoin) found **zero blocks naming any AI
crawler**. The KR/JP result is a property of **those regions' consumer-web portals** (Naver,
DCInside, 5ch behind Cloudflare's managed list), **not a platform-wide rollout**.
**THE OPERATIVE CORRECTION:** run the sweep **per region, every time**, and treat a prior region's
verdict as **zero evidence** about the next. Carrying "the community layer is closed" forward would
have made this seat abandon an open ground and report it as thin — the exact failure L1.25a names
(a statement about your attention dressed as a statement about the world).
**AND THE INVERSION WORTH KNOWING:** BR's only hard stop is **`reddit.com` (`User-agent: *` →
`Disallow: /`)**, a **global platform** decision that happens to bite regions whose retail community
lives on Reddit. So the axis that predicts a block is **platform**, not **geography** — sweep the
hosts, never the country.
**PROCEDURAL NOTE, learned by nearly getting it wrong:** grep the **whole** robots.txt, not a
truncated head. My first pass cut at 1,200 bytes; GitHub's and MQL5's files are longer than that and
a by-name block further down would have been invisible. A truncated read that finds nothing is
**not** a clean verdict.

## OPERATOR SEMANTICS — Qlib expression engine, exact reads (MIT, 2026-08-11) `qlib-alpha158`

**PROVENANCE:** `microsoft/qlib` raw files read IN FULL this run — `qlib/data/ops.py` (1,681
lines, every operator class enumerated), `qlib/contrib/data/loader.py` (Alpha158 field blocks),
`qlib/contrib/data/handler.py` (label + processor config). LICENCE: **MIT, read from the
canonical LICENSE file this run** (Microsoft). vn.py LICENSE also read: **MIT** (Xiaoyou Chen).
DERIVES-FROM: WorldQuant-style expression DSL — this is the ALTERNATIVE-IMPLEMENTATION node the
BRAIN charter ranks highest: a reimplementor had to make every elided semantic explicit in code.
Converts data_axis_watchlist card 24 (VeighNa/Qlib) [§33 backing artifact for that card].

**THE FIVE ELIDED SEMANTICS a summary would blur (each is a mechanical rule for reading ANY
mined qlib-dialect expression):**
1. **`Rolling(x, N)` has THREE semantics keyed on N's TYPE:** integer N → `rolling(N,
   min_periods=1)`; **N=0 → EXPANDING window** (inception-to-date); **float 0<N<1 → EWM with
   alpha=N**. A mined `Mean($close, 0.06)` is an EMA in disguise, not a bug.
2. **`min_periods=1` everywhere:** every rolling stat emits from bar 1 on partial windows — a
   mined backtest's early-window values rest on tiny samples; the desk convention (NaN until the
   window fills) is STRICTER, so naive replication shifts early-sample behaviour.
3. **Labels are future-Ref and CROSS-SECTIONALLY NORMALISED:** verbatim `Ref($close, -2)/
   Ref($close, -1) - 1` (handler.py:90) — decide at t close, enter t+1, book t+2: ONE BAR of
   execution slack built into the target; and `CSZScoreNorm` is applied to the LABEL
   (handler.py:39) — Alpha158 models learn RELATIVE (cross-sectional) returns, which is this
   desk's own TARGET/HORIZON duty arriving from an independent direction.
4. **Negative `Ref` = future reference, legal ONLY in labels.** MECHANICAL LEAK RULE for every
   mined expression: `Ref(x, -k)` inside a FEATURE is pre-falsified as leakage — kill on sight,
   no screen owed.
5. **`Greater/Less` are elementwise MAX/MIN, not comparisons** (`Gt/Ge/Lt/Le` are the booleans).
   Reading a mined `Greater(a,b)` as a predicate silently rewrites the strategy.

**VOCABULARY (crypto analogue + data-needed per the 3-question duty):**
- **Regression trio `Slope/Rsquare/Resi(x,N)`** — rolling OLS of x on time index: trend rate,
  trend QUALITY, deviation-from-trend. THE TRANSFORM AXIS THE DESK'S `combination_engine` LACKS.
  Crypto analogue: apply to funding, basis, OI, taker_buy_frac (NOT price-only — graveyard
  prior). Data needed: none new. Adoption = pre-registration (universe grows; the
  `UNIVERSE_IF_ADOPTED` discipline in `wq_operators` prices the bar move BEFORE it is paid).
- **`Rank(x,N)` is TS-RANK** — percentile of today within OWN trailing window, NOT
  cross-sectional. The exact universe-vs-peer confusion class that spawned this organ, in the
  reimplementation direction. Desk: `ts_rank` candidate; distinct from `rank` AND `group_rank`.
- **`IdxMax/IdxMin/IMXD(x,N)`** — bars-since-high/low (Aroon family). Analogue: bars since
  funding peak / OI peak. Data: none new.
- **`RSV` (stochastic position in rolling hi-lo range), `QTLU/QTLD` (rolling 0.8/0.2 close
  quantiles)** — price-only, LOW prior here (slow price-only is dead ground at daily res); log
  for completeness, spend nothing.
- **`Corr(x,y,N)/Cov` pair-rolling; Alpha158's `CORD` = Corr(returns, Δlog volume)** — the
  volume-interaction block is the transferable half; desk analogue: Corr(funding change, taker
  flow), Corr(basis, OI change). Data: owned.
- **`WVMA`** — volume-weighted price-change volatility. Analogue on taker_buy_frac-weighted
  moves. Data: owned.
- **`ChangeInstrument(inst, expr)`** — evaluate expr on ANOTHER instrument (e.g. BTC state
  inside an alt's signal). Desk analogue: regime conditioning on BTC/market factor — EXISTS
  partially (combination_engine regimes); the operator generalises it to any pair.
- **`Mask/If/And/Or` + `trade_when`** — conditional persistence family; desk has `trade_when`
  (turnover-preserving hold) since 2026-08-07; `If` is its stateless sibling.
- **KBAR block** (KMID/KLEN/KMID2/KUP/KLOW/KSFT wick anatomy) — intrabar shape features;
  desk analogue exists on H8 bars; price-only prior applies.
- **Alpha158 structure:** ~20 named blocks over windows {5,10,20,30,60} — a factor-set MAP of
  what a production equities shop considers worth computing. The map is the asset; the
  price-only factors are not (desk graveyard). Route: push the desk's OWN axes
  (funding/basis/OI/taker flow) through the same transform blocks.

**METHOD NOTE (routed to improvement inbox + ledger):** Qlib does cross-sectional normalisation
in the PROCESSOR layer (`CSRankNorm/CSZScoreNorm`), never in the expression — features stay
time-series, the cross-section is a TRAINING-TIME choice. Clean separation the desk can copy:
`group_rank`-style ops stay in the feature layer ONLY when the peer set is part of the
hypothesis; universe-relative normalisation belongs downstream.

### OP-053 a calendar axis has a HARD event ceiling — compute the MDE before you spend the run   [active]
class: power / pre-flight arithmetic
origin: AR frontier miner (2026-08-12), found by testing the seat's own replacement axis
validated-gain: killed an entire axis design in one command **after** the literature search and
  **before** any screen, and produced the number that makes the kill permanent: an annual event over
  a 7-year liquid history is **n=7**, and its 80%-power MDE was **3–6× the observed effect** on all
  three channels tested. Halving that MDE needs **28 episodes = 21 more years**, so the design can
  never be rescued by waiting — a fact no screen output would have stated.
technique: for any calendar/seasonal/event axis, the sample size is **the number of EVENTS, never the
  number of DAYS inside them** (gap-register row 85). Before mining or screening, compute:
  ```
  n_events  = occurrences of the event in the liquid sample      # annual => 7-10, monthly => 80+
  MDE_80    = (t_crit(n-1) + 0.842) * sd(per-event effect) / sqrt(n_events)
  ratio     = |observed| / MDE_80        # < 1  =>  the test CANNOT see a real effect
  years_to_halve_MDE = 3 * current_span  # MDE ~ 1/sqrt(n)
  ```
  **READ THE RATIO, NOT THE p-VALUE.** A null with ratio 0.2 says *the instrument is blind*, not
  *the effect is absent* — and the two demand opposite responses (L1.25: re-aim vs retire).
  Report `unmeasurable_by_construction`, retire the **DESIGN**, and name the enabling change that
  would restore power — for an annual event that is almost always **cross-sectional expansion**
  (n_events × N assets/venues), never a longer wait.
  **THE COMPANION TRAP, which is the half that surprises:** the same run must check the **ICC** of
  the series being tested, because the naive daily-dummy test is honest on some series and badly
  broken on others. Measured on this desk's BTCUSDT D1:
  * **returns: ICC 0.000, design effect 1.00** — a daily dummy is fine.
  * **funding: ICC 0.525 (DE 16.1)**, **basis: ICC 0.695 (DE 21.0)** — a daily dummy inflates t by
    **≈4.0× and ≈4.6×**.
  So *"is a daily calendar dummy valid?"* has no general answer: it depends on the **persistence of
  the series**, not on the test. Any event test on funding, basis, OI or spread must cluster at the
  event level. This matters most precisely where the desk should be hunting — the direction-agnostic
  channels — so the trap sits on the good path, not the bad one.
adaptations: AR=Hijri/Ramadan (n=7, killed as a design); universal — applies to halving cycles (n≈4),
  quarterly expiries (n≈28), CME rolls (n≈80, the first annual-class axis with real power), unlock
  events (n=24,201 but see the `pct_circ_now` conditioning-variable trap, R0289).
counterfactual: HIGH — without the MDE the run would have reported "Ramadan shows no effect in
  crypto" as a finding. That sentence is false in a specific and expensive way: it reads as *tested
  and dead* when the truth is *never testable this way*, which would have retired the mechanism
  along with the design and blocked the cross-sectional version that is still open.

## LEXICON — AR crypto/trading jargon (dark-forest search keys)
_Charter dark-forest deliverable #2, AR seat, session 1. Convention per EN/CN/KR/JP/RU tables.
OBSERVED = seen in live AR text this session; SEED = supplied/inferred and NOT yet verified, per the
CN OP-037 lesson (0/7 unverified seeds survived there — unobserved terms are not search keys yet)._

| term | gloss | era | note / example query |
|---|---|---|---|
| المراجحة | arbitrage | all | **OBSERVED** — the standard AR term; `المراجحة العملات الرقمية` finds AR arb writeups |
| العقود الدائمة | perpetual contracts (perps) | 2020→ | **OBSERVED** — the AR perp term; pairs with `التمويل` for funding-rate content |
| التمويل / معدل التمويل | funding / funding rate | 2020→ | **OBSERVED** — note the collision: التمويل is also "financing" in the Islamic-finance sense, so this key returns BOTH trading and fiqh material. **That collision is a feature** — it is the bridge to the doctrinal layer |
| التداول الشبكي | grid trading | 2021→ | **OBSERVED** — AR grid-bot content |
| تتبع الاتجاه | trend following | all | **OBSERVED** |
| بوت تداول / التداول الآلي | trading bot / automated trading | 2020→ | **OBSERVED** — `التداول الآلي` is the higher-yield of the two |
| الرافعة المالية | leverage | all | **OBSERVED** — in fiqh contexts it is the flag for the riba objection |
| التقابض / التقابض الفوري | possession / immediate possession (settlement) | doctrinal | **OBSERVED** — **the load-bearing doctrinal term**: the requirement that kills deferred settlement and derivatives. The precise key for the participant-exclusion layer |
| الغرر / الميسر | gharar (uncertainty) / maysir (gambling) | doctrinal | **OBSERVED** — the two named grounds for the derivatives prohibition |
| الربا | riba (interest) | doctrinal | **OBSERVED** — the ground for the margin/funding objection |
| زكاة العملات الرقمية | zakat on digital currencies | 2018→ | **OBSERVED** — the forced-flow key; finds the 2.5%-levy rulings and calculators |
| حلال / حرام + تداول | halal/haram + trading | all | **OBSERVED** — the retail-facing framing; high volume, mostly SEO-grade, but it names the constraint retail actually applies |
| حوامير | "whales" (lit. groupers) — **and the name of the largest Gulf forum** | all | **OBSERVED** — `حوامير` is both the slang for big players and the brand `hawamer.com`. **Note the §13 status: that forum is a HARD STOP (ClaudeBot denied by name)**, so the term is a search key for *other* venues quoting it, not for mining the forum itself |
| سيولة / السيولة | liquidity | all | SEED — standard finance vocabulary, low discrimination |

---

### OP-054 the native key is not the translated key — verify the search term against the ground before grading it THIN   [active]
class: search / instrument hygiene
origin: BR frontier miner session 2 (2026-08-12)
validated-gain: measured on GitHub repo search, same corpus, same minute:
  - `pairs+trading+brasil` -> **0 repos**
  - `cointegracao` (the native PT term) -> **30 repos**, essentially all genuine pairs-trading /
    statistical-arbitrage work, several crypto-native
  A seat that queried the English term and stopped would have graded BR statistical arbitrage a
  DEAD GROUND on a clean zero. The ground holds at least 30 repos. **Zero was a property of the
  QUERY, not of the forest.**
technique: for every family you hunt, the region names it with a NATIVE technical term that is
  usually NOT the translation of the English one. Before recording any ground as thin or
  exhausted, find the term the practitioners themselves use — normally by reading one known-good
  artifact from that ground and harvesting its vocabulary, not by translating your own.
  In PT-BR the family keys are `cointegração` (the method, and the highest-yield single key),
  `long e short` / `long&short` (the retail name of the trade — B3 retail culture calls the trade
  after its LEGS, not after the statistic), `arbitragem estatística`, `pares` / `par cointegrado`.
  **`pairs trading` is not used.**
adaptations: universal, and it composes with OP-030 (negative-control every zero-hit) and OP-037
  (negative-control a supplied glossary). OP-030 says a zero needs a control; OP-037 says a
  supplied TERM may be fake; **OP-054 says a REAL, correct, well-formed English term can still
  return a structural zero because the ground does not speak it.** All three failure modes end in
  the same artifact — a false EXHAUSTED — and that is the one verdict this desk cannot afford,
  because a ground graded dead is never re-entered.
counterfactual: HIGH. STATISTICAL-ARBITRAGE is the desk's **only NEVER-HUNTED family**
  (`data/strategy_coverage.json`: 0 of 14 hunted), so the one family most in need of ground was
  the one being hidden by vocabulary.

### OP-055 in a mined replication repo, DIFF THE CONFIG COMMENTS AGAINST THE CONFIG VALUES   [active]
class: extraction / evidence grading
origin: BR frontier miner session 2 (2026-08-12)
validated-gain: `mateusmartinelli/tcc` (crypto pairs trading, 3 method implementations,
  ~1,384-1,464 lines each). **Three contradictions, all in the config block, found in under a
  minute by one grep:**
  - `TRANSACTION_COST = 0.001  # 0.05% por trade` — 0.001 is **0.1%**, i.e. **2x** the commented
    intent. Identical in all three files (copy-pasted), so the whole comparison shares it.
  - `Z_ENTRY_THRESHOLD = 1.5  # 2 standard deviations for entry (as per paper)` — the value is
    **1.5σ**, the comment claims **2σ "as per paper"**. Looser entry ⇒ more trades ⇒ interacts
    directly with the mis-stated cost.
  - `LOOKBACKS = [90]  # 12 months formation period (252 trading days)` — the formation window is
    **90 days**, not the paper's 252.
technique: the comment is the author's statement of INTENT; the value is what actually RAN. On a
  replication or thesis repo the two drift apart silently, and the write-up is generated from the
  intent. One grep over the config block prices the gap between what a paper-replication claims to
  have replicated and what it executed. Do this BEFORE reading any result the repo reports.
  Grade the direction too: charging 2x cost is conservative and does not inflate a result, while a
  looser entry threshold and a shorter formation window are NOT conservative.
adaptations: universal — any language, any replication repo, thesis code, notebook, or bot config.
  Pairs with the backtest-miner cost-accounting duty: absence of a cost model is a finding, and a
  cost model that contradicts its own comment is a **better** one, because it is evidence about
  the author's process rather than about their taste.
counterfactual: MEDIUM-HIGH — the artifact reads as unusually rigorous on the surface (it loads a
  T-bill series and computes excess returns, which most retail backtests never do), so it is
  precisely the kind of repo a seat would quote approvingly without opening the config.

### OP-056 a mined VALIDATION module is tested by INVARIANCE: does its null actually move its statistic?   [active]
class: extraction / adversarial verification
origin: BR frontier miner session 2 (2026-08-12)
validated-gain: `pedhsm/systematic-research-framework` — "Biblioteca de validação de estratégias
  quantitativas ... e testes de Monte Carlo (MCPT)". Its `mcp/tester.py` permutes the **realised
  return series** and recomputes `sharpe = mean/std*sqrt(252)`, `cagr = exp(sum(r))**(1/years)-1`,
  `vol = std*sqrt(252)`. **All three are order-invariant** (mean, std and sum are each invariant
  under permutation), so the permuted statistic IS the real statistic.
  Verified numerically by independent reimplementation of the arithmetic (NOT by executing the
  repo — supply-chain rule), 500 permutations x 4 synthetic return series:
  **max-min spread across permutations = 1.1e-15 (machine epsilon).**
  The consequence is worse than an uninformative test. Because floating-point summation is not
  associative, `perm_score >= real_score` resolves on ROUNDING ORDER, so the p-value is a hash of
  FP dust rather than a statistic: measured p = 0.978 for a strong winner (mu=+0.15%/d) and
  p = 0.618 for a catastrophe (mu=-0.20%/d) — **the disaster scored "better" than the winner**.
  At any conventional alpha nothing ever passes: it is a **WALL, not a bar** (L1.49's exact case).
technique: for any mined backtest/validation library, do not read its null — TEST it. Ask whether
  the statistic it scores is mathematically invariant to the resampling it performs. If it is, the
  gate carries zero information no matter how sophisticated it looks. The test is cheap: permute
  twice and check the statistic moved by more than machine epsilon.
  **The general rule the desk should carry outward: a permutation null must destroy the thing the
  statistic is supposed to measure.** Permuting realised strategy returns to test a Sharpe destroys
  nothing, because the P&L has already been computed. The correct null permutes the PRICE PATH and
  re-runs the strategy (destroying timing skill while preserving the marginal distribution), or
  permutes the SIGNAL against fixed returns.
adaptations: universal — every language, every mined validation/backtest framework.
  **CROSS-ECOSYSTEM CONVERGENCE, and it is genuine rather than an echo:** this desk's own
  `libs/validation/bar_permutation.py` independently documents the identical trap (its docstring:
  total log return over the permuted window EQUALS the real one, so buy-and-hold "scores
  identically on the permutation and gets p ~ 1"), permutes bars rather than returns, and handles
  the FP-dust tie problem the BR repo falls into via a measured `_TIE_RTOL = 1e-4` plus the
  add-one correction `(sum(s >= real - tol) + 1)/(n + 1)`. Two ecosystems, no citation link in
  either direction, same trap, one solved and one not. Per the provenance rule that buys the
  finding a QUEUE PLACE, not a lower bar — and here it buys **confirmation of an existing desk
  design**, not a new build. The desk is AHEAD on this one; the value is the operator, not a fix.
counterfactual: HIGH for the fleet — miners are explicitly told to route AI-quant structures and
  validation frameworks to the improvement inbox as ENGINE ideas, and this is the screen that
  separates an engine idea worth importing from one that would import a welded gate.

---

## NATIVE LEXICON — BR / PT-BR (Brazilian Portuguese)
_Charter dark-forest deliverable #2, BR seat, session 2 (2026-08-12). No BR lexicon existed before
this run (`grep -c alavancado` = 0). OBSERVED = seen in live PT-BR artifacts this session (repo
titles/descriptions in the 30-repo `cointegração` corpus); SEED = supplied/inferred and NOT yet
verified. Per OP-037, a SEED is a lead, never a search key._

| term | gloss | era | note / example query |
|---|---|---|---|
| **cointegração** | cointegration | all | **OBSERVED — the single highest-yield PT-BR quant key found this run.** 30 repos vs **0** for `pairs trading brasil`. This is OP-054's proving instance |
| **long e short** / **long&short** | the pairs trade, named after its LEGS | all | **OBSERVED** — B3 retail culture names the TRADE, not the statistic. **Two collisions poison it as a bare key** (see below) — always pair with `cointegração` or `ações` |
| par cointegrado / pares | cointegrated pair / pairs | all | **OBSERVED** |
| arbitragem estatística | statistical arbitrage | all | **OBSERVED** (as `arbitragem estatistica`, unaccented, in repo text) — lower volume than `cointegração` |
| **TCC** | *trabalho de conclusão de curso* — undergraduate final thesis | all | **OBSERVED and now MEASURED (s3) — a STRUCTURAL key, and a PRECISION one, not a recall one.** `TCC bitcoin` **29**, `TCC trading` **18**, `TCC criptomoedas` **15** — but `TCC cointegração` **1** against **30** for `cointegração` alone. **Never AND it with a topical key** (OP-081); union instead. Everything it returns is genuine thesis code (L1.34 #6: rigorous-looking, never out-of-sampled, unread by the English crowd), but counts **overstate** — student repos are disproportionately vendored framework forks |
| **dissertação** | dissertation (the *formal* thesis word) | all | **OBSERVED-NEGATIVE (s3) — a measured ZERO: `dissertação trading` = 0 repos.** Recorded precisely because a clean zero on a correct, well-formed native word reads exactly like an empty ground (OP-054's third false-exhaustion mode). Within one country only the **colloquial abbreviation** survives as a repo label. Do not spend budget here |
| **prazo** | lit. "term/deadline" — in BR pairs practice, **the lookback window** | all | **OBSERVED (s3, video `vaDLuXYDSJ8`)** — *"no prazo de 240"*. The window length is called a *prazo*, not a *janela*. A query for `janela` misses the practitioner layer |
| **beta rotation** | rolling hedge-ratio stability | all | **OBSERVED (s3) — an ENGLISH term used untranslated inside PT-BR practice**, and independently a function name in `zecontinha` (`analysis.py:beta_rotation`). Selection criterion, not just a diagnostic: *"beta rotation mais estável"*. A PT-only query misses it — this is OP-079's boundary running through the vocabulary itself |
| **enquadrado** | "well-fitted / well-framed" (of a pair) | all | **OBSERVED (s3)** — *"o par está melhor enquadrado"*, i.e. the best-fitting pair. Folk term for the selection step; no English equivalent in the literature |
| ações | equities/stocks | all | **OBSERVED** — the disambiguator that rescues `long short` from the LSTM collision |
| criptomoedas | cryptocurrencies | all | **OBSERVED** — note `cripto` alone did NOT conjoin usefully in repo search (`cointegracao+cripto` = 0 while crypto repos exist in the `cointegracao` corpus): search the broad key and filter, do not conjoin |
| alavancado | leveraged | all | **SEED — NEGATIVE-CONTROLLED AND DOWNGRADED (OP-037).** The word is real standard Portuguese, but it is *standard financial vocabulary*, not slang, so it carries no discrimination as a search key — the CN `亏损/kuisun` case exactly. Not a dark-forest key |
| laranja | lit. "orange" — a nominee / straw-man account holder | all | **SEED — real BR term, but §13 AWARENESS ONLY.** It indexes fraud and money-laundering material, not trading mechanism. Not a research key for this desk |
| HODLar | to HODL, verbified with the PT infinitive `-ar` | 2017→ | **SEED — NOT CONFIRMED.** A targeted search surfaced BR Bitcoin communities but no evidence of this specific coinage in use. Morphologically plausible (PT productively verbifies loanwords) but **unobserved**; do not spend query budget on it until seen in live text |

**THE TWO COLLISIONS THAT POISON `long short` IN A PT-BR CORPUS** — measured this run, and either
one alone is enough to make a rich ground look picked clean:
1. **LSTM.** `Long Short-Term Memory` is written out in full in Portuguese ML repo descriptions.
   `long+short+acoes` returned 18 repos of which **3 of the top 5 were neural-network repos**.
2. **C/C++ type keywords.** `"long e short"` returns `MODIFICADORES-DE-TIPOS-DE-DADOS-Unsigned-Long-e-Short`
   — teaching repos about integer types. Two of the top 5.
The rescue is the native method key (`cointegração`), not a better English phrasing. This is the
vocabulary-collision sibling of the RU seat's TICKER-collision finding: same failure mode
(a homonym silently empties a result set), different layer of the stack.

### OP-057 the arXiv `/pdf/` route SILENTLY FABRICATES from this box — HTML/ar5iv is the only trusted route   [active]
class: routing / source integrity
origin: litminer run 7 (2026-08-12), AI-methods seat + parent adversarial re-test
validated-gain: prevented an unknown number of fabricated figures from entering desk artifacts,
  and bounded the retroactive damage to ZERO for the prior run.

**THE FINDING.** `WebFetch` against `arxiv.org/pdf/<id>` does not reliably return the paper. The
AI-methods seat measured **4 of 4 PDF fetches producing figures the VERBATIM ABSTRACTS
CONTRADICT**, and on `2311.10685` the fabricated number pointed the **OPPOSITE DIRECTION** from
the real headline. The same seat measured `arxiv.org/html/` clean **11 of 11**.

**THE PARENT'S ADVERSARIAL RE-TEST, AND WHY IT MAKES THE RULE STRONGER RATHER THAN WEAKER.**
Re-tested independently on `2605.05089v1`: the PDF route **REFUSED** — twice — returning PDF
object structure and stating it could not locate the section. **So the failure mode is NOT
uniform.** The route sometimes refuses honestly (safe) and sometimes confabulates (catastrophic),
**and the caller cannot tell which one they received.** That is precisely the desk's own
ABSENT-vs-UNREADABLE collapse (L1.55) — arriving at the TOOL layer, where every organ is exposed.
A route that fails loudly can be trusted; a route that fails loudly *most of the time* cannot.

**THE RULE.**
1. **Read arXiv via `arxiv.org/html/<id>` or `ar5iv.labs.arxiv.org/html/<id>`. Always.** Both were
   measured clean and both need no extractor. The parent pulled a full interior — boundary
   formulas, per-asset tables, live-execution figures — from the HTML route today.
2. **A `/pdf/`-sourced number is QUARANTINED** unless independently confirmed against the abstract,
   the HTML mirror, or a stdlib extraction. Mark it `[UNVERIFIED-PDF-ROUTE]` rather than dropping
   it silently — the mark is what lets a later run re-check it.
3. **A LOCAL extraction is a different mechanism and is NOT covered by this rule.** The retraction
   seat stdlib-extracted a CREATES PDF successfully the same day; that path parses bytes this box
   holds, rather than asking a summariser what a binary said.
4. `export.arxiv.org` **429s from this box** — walk listing pages serially, never the API.

**RETROACTIVE DAMAGE, BOUNDED NOT ASSERTED.** run 6's arXiv ground file contains **zero**
`arxiv.org/pdf/` URLs (grep count 0) against 2 html/ar5iv routes, so its figures are uncontaminated.
The check is one grep and should be run on any ground file whose numbers are about to be relied on.

**THE GENERAL LESSON, worth more than the arXiv instance:** an information channel that
*sometimes* fabricates is more dangerous than one that always fails, because the failure carries
no signal. Ask of every fetch route: **what does its failure look like, and is that
distinguishable from success?** If it is not, the route needs a second source or a quarantine mark.

## OPERATOR SEMANTICS — WorldQuant BRAIN pipeline, exact reads (2026-08-12) `wq-brain-pipeline`

**BRAIN HUNTER session 2.** Session 1 closed the *grouping* half of the 08-07 gap (`data/crypto_grouping_map.json`, R0437). This section closes the half nobody had asked about: **what the platform DOES with an alpha vector after your expression returns it.** The desk adopted four operators on 08-07 from a screenshot; it never had the pipeline they sit inside.

**SOURCES + PROVENANCE (two independent lineages, no citation link between them — genuine convergence, not an echo):**
- `efJerryYang/worldquant-brain-simulator` — **GPL-3.0**, 32★, pushed 2026-05-02. Read as TEXT for mechanism extraction; **no code copied, nothing installed or run** (supply-chain rule). Its own header credits `yli188/WorldQuant_alpha101_code` as the expression lineage.
- `QuantML-Research/wq-alpha-research` `SKILL.md` — **NO LICENCE FILE ⇒ all-rights-reserved.** 349★. Facts and measurements extracted; **no verbatim text reused.** Chinese-language (L1.34 §5, the CN AI-quant layer).
- DERIVES-FROM: the 08-07 principal screenshot — **checked, and this corroborates it from two directions.**
- Official `platform.worldquantbrain.com/learn/...` — **WALLED (JS/login shell, returns title only). Route TRIED AND FAILED 2026-08-12.** Naming what is behind it is legitimate; going behind it is not (§13).

### OP-058 — THE POST-PROCESSING PIPELINE: neutralize → truncate → normalize

The order is the finding, and no public doc states it. Reconstructed from the simulator's `post_processing`, and consistent with the community settings payload:

1. **NEUTRALIZATION** = subtract the cross-sectional mean of the alpha vector, per day.
2. **TRUNCATION** = clip to ±`truncation` (platform default **0.08**, valid ≤0.1).
3. **NORMALIZATION** = divide by `sum(|alpha|)`, so the book always satisfies **Σ|w| = 1**.

**CRYPTO ANALOGUE — this is directly usable and the desk already has every input.** Step 1 is precisely the desk's own measured remedy for its worst structural problem: `reports/cross_section_breadth.json` records raw cross-sectional N_eff **1.54** vs leave-one-out-demeaned N_eff **29**. BRAIN neutralizes *by default, on every alpha, before anything else*. The desk's `combination_engine` does not.

**WHAT THE DESK MUST NOT COPY VERBATIM:** truncation applied *before* normalization does **not** bound the final weight — normalization rescales afterwards, so the effective cap is `0.08 / Σ|clipped α|`, a number that moves with the cross-section. The correct construction caps *post*-normalization and must **iterate**, because clipping changes the sum that normalization divides by. **The simulator's own README flags this: truncation "not necessarily working".** Recorded so the next seat does not inherit a one-pass clip believing it enforces a cap.

### OP-059 — `rank(x, rate=2)`: uncentered [0,1], and that is a long-only tilt

The simulator quotes the platform doc directly and implements `(rank − 1)/(N − 1)`, giving floats **equally distributed on [0.0, 1.0] inclusive**.

**THE TRAP, and it is a real portfolio consequence:** an uncentered rank is **non-negative everywhere**. Feed it straight to weights and every name is a LONG — the bottom-ranked name gets weight 0.0, not a short. `rank()` is only a long/short signal *because* neutralization (OP-058 step 1) subtracts the mean afterwards. **Any desk organ that applies a rank transform without a following demean is building a long-only book and calling it cross-sectional.** Worth one grep against `combination_engine`.

### OP-060 — `decay_linear(x, n)`: exact weights, newest heaviest

Weight vector `w_i = i / (n(n+1)/2)` for `i = 1..n` over the window ordered oldest→newest, so the **newest bar carries the largest weight** `n/(n(n+1)/2)` and `Σw = 1`. Precise enough to implement without the source.

**CRYPTO ANALOGUE:** a turnover suppressant. See the improvement_inbox entry — decay is prescribed *by data-arrival rate*, not swept.

### OP-061..066 — operators the desk still lacks (named, with analogues)

The 08-07 screenshot named four (`group_rank`, `group_zscore`, `ts_backfill`, `trade_when`). The community operator table names these **additional** ones the desk has no equivalent for:

| Operator | What it computes | Crypto analogue / desk note |
|---|---|---|
| **`group_neutralize(x, g)`** | subtract the **group** mean, not the universe mean | **The highest-value missing one.** Makes OP-058 step 1 available *inside* the expression against a *different* grouping than the portfolio uses. Runnable today against `corr_cluster_residual` in `data/crypto_grouping_map.json`. |
| **`winsorize(x, std=4)`** | cross-sectional clip at ±4σ | Crypto cross-sections are fat-tailed (desk lesson: the `pd.cut` fat-tail trap). A 4σ winsorize *before* ranking is a cheap robustness transform the desk lacks. |
| **`ts_zscore(x, n)`** | z-score against the symbol's **own** trailing window | Normalizes a signal against its own history rather than its peers — the time-series half of the two-stage construct in OP-067. |
| **`group_backfill(x, g, n)`** | fill a symbol's hole from its **group's** value | Sparse crypto axes (funding on a thin pair, OI on a new listing) have holes a peer group can cover where ffill cannot. |
| **`if_else(c, a, b)`** | elementwise branch | Distinct from `trade_when`: `if_else` substitutes, `trade_when` **holds**. Different turnover profiles ⇒ different hypotheses. |
| **`vec_avg` / `vec_sum`** | reduce a **VECTOR-typed** field | See the data_axis_watchlist entry: 1,387 of BRAIN's 4,367 fields are VECTOR-typed. Multi-venue funding and L2 depth are natively vector-shaped and the desk flattens them at ingest. |

### OP-067 — the canonical two-stage construct ("黄金组合")

`group_rank(ts_rank(signal, N), group)` — with N=126 (≈6 months) in every published template.

**MECHANISM, which is the transferable part:** `ts_rank` makes a signal comparable **across time for one asset** (strips level and scale drift); `group_rank` then makes it comparable **across assets within a peer set** (strips the group's common movement). Two orthogonal normalizations composed. The equity templates wrapped around it are fundamental ratios (ROE trend, EPS yield, FCF yield) and are **correctly not importable** — the *structure* is what transfers.

**CONFIRMED, NOT ASSUMED — the desk's `fitness()` matches an independent source exactly.** `libs/alpha_factory/wq_operators.py` reproduces `Sharpe × sqrt(|annual return| / max(turnover, 0.125))` from the 08-07 screenshot; the CN skill states the identical formula **including the 0.125 floor**, from a separate lineage. Cross-source convergence on a formula the desk had from one screenshot only. **The thresholds attached to it remain FACTS ABOUT THEIR PROCESS and are not adopted** — the desk's bar is a deflated t of 5.236 (L1.6).

---

### OP-068 SPA archaeology: the archive stores the SHELL, so a 200 with no content is a THIRD false-null class   [active]

**Origin:** EN frontier miner s H (2026-08-13), opening the Kaggle competition ground (never touched
by any seat since 07-25). Generalises OP-052 (probe the CONTENT PATH, not robots) one layer down:
OP-052 assumes that once you reach the content path with a 200 you have the content. On a
JS-rendered platform you do not, and **neither robots.txt nor the status code nor the byte count
tells you** — the shell is a plausible 5–6 KB of HTML.

**THE THREE FALSE-NULL CLASSES, now complete** (R0466 named the first two; this is the third):
| class | what a fetch-only route sees | why it is dangerous |
|---|---|---|
| WALLED (403/robots) | non-200 | loud, gets logged correctly |
| EXHAUSTED (genuinely empty) | 200, no matter | the true null |
| **REACHABLE-BUT-CONTENTLESS** | **200 + rendered shell** | **indistinguishable from EXHAUSTED to any pipeline that treats 200 as success** |

**MEASURED ON KAGGLE, 2026-08-13** (every line a probe run this session, not an inference):
- `robots.txt` → **404 for every UA** (ClaudeBot / curl / Googlebot alike). No exclusion exists, so
  §13 is clean on the robots axis — and a seat that stops at robots concludes "open ground".
- `/competitions/<slug>/discussion/<id>` → **200, 5.6 KB, JS shell.** Zero topic content.
- `/competitions/<slug>/writeups/<slug>` → 200, 6.2 KB. `og:title` carries the writeup TITLE,
  `og:description` is **empty** — so search engines index a title the fetcher cannot back with a body.
- **`/c/<compId>/publicleaderboarddata.zip` → HTTP 200, `content-type: text/html`, 5,593 bytes.**
  The single nastiest case: a naive `curl -o lb.zip` **succeeds**, writes a file with the right
  name, and the ground reads as harvested. **Always assert the content-type and magic bytes on any
  archive/export route** (`od -c | head -1` — a real zip starts `PK`).
- Live gRPC-web API: `POST /api/i/discussions.DiscussionsService/GetTopicListByForumId` → **400**
  (route exists, body/session wrong); sibling method names → 404. **400 vs 404 is the method-name
  oracle** — 400 means you found a real endpoint and only the body is wrong.

**THE ASYMMETRY THAT MAKES THE GROUND PARTLY MINEABLE — and it is not guessable, only measurable:**
Kaggle embeds `Kaggle.State.push({...})` in the served HTML, and **what it contains depends on the
page type**:
- **discussion / leaderboard pages → competition-level state ONLY.** The topic body and the
  leaderboard rows are XHR-loaded, so **they never entered Wayback at all**, at any timestamp. No
  amount of re-probing recovers them; this is a property of the capture, not of the crawl.
- **notebook (`/code/<user>/<slug>`) pages → FULL kernel state** (`kernel`, `kernelRun`, `author`,
  `versions`, `dataSources`, `renderedOutputUrl`, `downloadAllFilesUrl`, vote counts). **So on this
  platform the notebook layer is archived and the forum layer is not** — which inverts the usual
  digging order: go to the CODE tab first, and treat forum prose as the walled half.
- `renderedOutputUrl` is a **signed** `kaggleusercontent.com` URL and returns **403** years later —
  recoverable metadata pointing at unrecoverable content. Record it as a lead, never as a source.

**THE ROUTE, reusable as-is** (worked this session on a 2022 capture):
1. CDX-map the ground: `web.archive.org/cdx/search/cdx?url=<host>/<path>*&fl=timestamp,original,statuscode,length&collapse=urlkey`.
2. **Rank captures by LENGTH, not recency** — the 20 KB 2021–22 captures carry state; the 4–5 KB
   2023+ ones are the modern shell. A ground can be archived and still be *unreadable at the wrong
   timestamp*, so a single recent probe under-reads it.
3. Fetch with the `id_` suffix (`/web/<ts>id_/<url>`) to get raw stored bytes.
4. **Gzip-sniff and decompress** — `id_` returns the stored encoding, so the file is gzip and every
   text tool reports binary garbage (OP-034's discipline; it cost a wasted probe again this run).
5. Extract state by **brace-matching** from `Kaggle.State.push(` — a regex to the closing paren
   fails on nested objects. Same shape as `__NEXT_DATA__` / `__APOLLO_STATE__` (OP-050).

**REGIONAL ADAPTATION (charter §16 — the fleet upgrades together):** the pattern is the platform
class, not the platform. Any React/Vue/Rails-SPA community serves this shape; the state key is the
only thing that changes. Known keys to try in order: `__NEXT_DATA__`, `__NUXT__`, `__APOLLO_STATE__`,
`window.__INITIAL_STATE__`, `Kaggle.State.push` (Kaggle), Rails `data-react-props`/`gon` (OP-050's
velog case, KR). **CN/JP/KR/RU/BR seats: when a ground reads THIN through a fetch-only route, this
operator is the first thing to rule out before writing the null** — the JP seat's R0466 exists
because a blocked ground and an exhausted one look identical, and a shell-served ground looks
identical to BOTH.

---

## OPERATOR SEMANTICS — VeighNa `vnpy.alpha` expression engine, exact reads (MIT, 2026-08-13) `vnpy-alpha-dsl`

**PROVENANCE:** `vnpy/vnpy` raw files read IN FULL this run — `vnpy/alpha/dataset/utility.py`
(285 lines, the whole DSL), `dataset/template.py` (305), `dataset/processor.py`,
`dataset/ts_function.py`, `dataset/cs_function.py`, `dataset/math_function.py`,
`datasets/alpha_158.py`, `datasets/alpha_101.py` (100 features), `lab.py`. LICENCE: **MIT, read
from the canonical LICENSE file this run** (Xiaoyou Chen) — §13 PASS, and read, not "understood
to be" (the row-#79 discipline).
**DERIVES-FROM — READ THIS BEFORE COUNTING IT AS CONVERGENCE:** `alpha_158.py`'s own docstring
says *"158 basic factors from Qlib"*. The FACTOR SET is **derived from Qlib**, so it is NOT an
independent confirmation node and must never be counted as one (the GAP-#85 echo trap). The
**ENGINE** is an independent polars reimplementation, and it is the DIVERGENCES below that carry
information. Sibling anchor to `qlib-alpha158`; closes the vnpy half of data_axis_watchlist
card 24, which had the LICENCE read but the CODE unread.

**THE ARCHITECTURE — a 285-line reference implementation of the desk's named gap #1.**
A feature-expression DSL with **no parser and no AST**: `DataProxy` wraps a 3-column polars frame
(`datetime`, `vt_symbol`, `data`) and overloads every dunder (`+ - * / // % ** abs neg > >= < <=
== !=`); `calculate_by_expression` builds a dict mapping every data column → `DataProxy` and every
operator → function, then calls `eval(expression, {}, d)`. Open operator set via
`register_functions([...])` keyed on `func.__name__`.
**COPY THE PATTERN, REJECT THE MECHANISM.** `eval()` on an expression string is arbitrary code
execution. The desk's `combination_engine` enumerates expressions and any LLM-generated expression
would land in the same call — so an operator-overloaded proxy is the right design, and the
evaluator must be an `ast.parse` walk with a whitelisted node set (Name/Call/BinOp/UnaryOp/Constant,
names resolved only from the registry), never `eval`.

**THE DIVERGENCES FROM QLIB — each a mechanical rule for reading a mined vnpy-dialect expression:**
1. **`ts_delay(x, n)` is polars `shift(n)`; NEGATIVE n = FUTURE.** Same leak rule as qlib's
   negative `Ref`, now confirmed in a SECOND, independently-written framework — so it is a
   **family-level property of the whole expression-DSL class**, not a qlib quirk. Kill any mined
   feature containing a negative delay on sight; no screen owed.
2. **The label is NOT qlib's label, despite the "from Qlib" docstring.** Verbatim (both datasets):
   `ts_delay(close, -3) / ts_delay(close, -1) - 1` — decide at t, enter t+1, book t+3: **two bars
   held** with one bar of execution slack. Qlib's is `-2/-1` (one bar held). Mining the two as the
   same target silently doubles the horizon.
3. **`min_samples` is INCONSISTENT WITHIN THE LIBRARY** — qlib's is uniformly 1, this one is three
   different conventions: `min_samples=1` (ts_min, ts_max, ts_mean, ts_std, ts_corr) emit from bar
   1 on partial windows; polars default `=window` (ts_sum, ts_argmax, ts_argmin, ts_rank,
   ts_quantile, ts_decay_linear, ts_product) null until full; explicit `=window` (ts_slope,
   ts_rsquare, ts_resi). **CONSEQUENCE:** a composite like `ts_std(close,60)/ts_mean(close,60)`
   returns non-null numbers computed on TWO observations in the early window, while a sibling term
   in the same expression is still null. The early sample is silently garbage rather than absent —
   **WS-005's shape (absence resolving to a clean value) at the FEATURE layer**, and no null-filter
   downstream can catch it.
4. **`cs_rank` is NOT Alpha101 `rank`.** It is bare polars `rank()` → **1..N, un-normalised**, with
   no divide-by-count. Demonstrable from their own code, which is why this is a fact and not a
   reading: `process_cs_rank_norm` writes `rank("average") / count` when it wants [0,1], and their
   Alpha101 `alpha1` centres with `cs_rank(...) - 0.5`, an idiom that presupposes [0,1].
   **165 `cs_rank` call sites across their 100-feature Alpha101 port inherit the mismatch**, and it
   is worse in crypto than in equities: a raw rank's scale moves with the number of listed symbols,
   so in a time-varying universe the feature is not comparable across dates. RULE: read any mined
   vnpy-dialect `cs_rank` as a raw rank and re-normalise before use.
5. **`ts_rank(x,N)` = `percentileofscore(window, window[-1])/100`** → [0,1] TS percentile (qlib's
   TS-rank sense, NOT cross-sectional). `ts_argmax/argmin` return `arg_max()+1` → 1-indexed, and
   Alpha158 divides by w → (0,1]. Off-by-one conventions are exactly what silently rewrites a
   mined factor's meaning.
6. **`ts_less`/`ts_greater` are elementwise MIN/MAX, not comparisons** (same trap as qlib's
   `Greater/Less`). The real comparisons (`>`, `<`) return **Int32 0/1 series**, which is a
   deliberate masking idiom: `ts_mean(close > ts_delay(close,1), w)` is the up-bar fraction.
7. **Regression trio `ts_slope`/`ts_rsquare`/`ts_resi` present INDEPENDENTLY of qlib** and
   implemented **closed-form** — rolling sums with `(window-1-j)*shift(j)` building `sum_xy`
   against a linear time index, so no per-window fit. Its independent presence in a second
   framework corroborates card 24's ranking of the trio as the desk's real transform gap, and this
   is a directly usable implementation recipe.
8. **`quesval(threshold, x, a, b)` / `quesval2`** — ternary, `a if threshold < x else b`. The
   conditional family. **Argument order is threshold-FIRST** and the comparison is a strict `<`;
   easy to mis-port silently.
9. **`cs_scale`** = `x / Σ|x|` per date (Alpha101 `scale`) — the gross-exposure normaliser for
   cross-sectional weights.
10. **NO group operators — and that is the informative absence.** vnpy.alpha ships zero
    `group_rank`/`group_zscore`, exactly like the desk. Two mature frameworks independently lack
    them because both presuppose a sector map. This corroborates that the **crypto grouping map is
    THE blocking input** (data_axis_watchlist backlog), not an optional nicety.

**THE PROCESSOR LEAK SURFACE — the half a summary never mentions.**
- **The fit window is OPTIONAL and defaults to None.** `process_ts_norm` and
  `process_robust_zscore_norm` take `fit_start_time`/`fit_end_time`; when omitted they compute
  mean/std over the **ENTIRE panel including valid and test**. Full-sample z-score is look-ahead,
  and here it is the DEFAULT.
- **`process_replace_inf` has no fit window at all** and replaces infinities with a per-symbol mean
  computed over ALL time — an **unconditional** full-sample leak, worse than the two above because
  it offers no control to omit.
- **SAFE BY CONSTRUCTION:** `process_cs_norm`, `process_cs_rank_norm`, `process_cs_fill_na` — all
  `.over("datetime")`, within-timestamp only, so they use no future information.
- **THE GENERAL RULE, worth more than the instances:** *a transform that aggregates ACROSS TIME
  needs a fit window; a transform that aggregates WITHIN a timestamp is causally safe by
  construction.* Useful as a triage rule when reading ANY mined feature pipeline: you can classify
  a transform's leak risk from its aggregation axis alone, before reading its fit logic.
- **AND THE DESK IS AHEAD HERE — checked this run, not assumed.** A draft of this note claimed the
  desk's causal guard is blind to full-sample normalisation, citing R0289. **That claim is STALE
  and was removed before it was published.** R0289 is `implemented`, and
  `libs/features/validation.py:_perturbable` now perturbs **every** numeric/bool/datetime column
  (with an explicit `untestable` bucket — absence stays absence). Because `run_leakage_test`
  mutates FUTURE bars and asserts PAST values are invariant, a full-sample mean/std recomputed over
  a perturbed panel moves, so **the desk's guard would catch exactly the default that vnpy.alpha
  ships**. The finding is therefore a foreign framework confirming a class the desk has already
  closed — not a live blind spot. Recorded because the near-miss is the lesson: a recalled defect
  is a claim about the past, and R0289's row said `implemented` one grep away.
- **HONEST SCOPE, do not overstate:** Alpha158 and Alpha101 add NO processors in their
  constructors, so the shipped datasets do not trip any of this. It is a latent footgun the user
  opts into, not a shipped leak.

**CORRECTION TO data_axis_watchlist CARD 24 (load-bearing).** The card's "remaining diff" #2 says
these systems have *"a rolling walk-forward harness wired to the enumerator"* the desk lacks.
**vnpy.alpha has no such harness** — zero hits for rolling / walk-forward / refit / retrain /
expanding / fold across the entire module. It has a **static three-way split** (`Segment.TRAIN/
VALID/TEST`, fixed date tuples), and `lab.py` is a **persistence layer** (save/load bars, datasets,
models, signals), not a harness. The desk's gap is real; this system is not evidence for it, and
porting from here would be porting a thing that is not there.

**THE ONE PROCESS PATTERN WORTH TAKING — point-in-time universe membership.**
`lab.load_component_filters` reconstructs, per symbol, the **contiguous intervals** during which it
was an index constituent, correctly emitting **multiple (start, end) spells** for a symbol that was
added, dropped and re-added; `prepare_data(filters=...)` then slices the panel by them. That is a
survivorship-bias control at the universe layer, and it is the correct shape of the fix for the
desk's own recorded defect that **`exchangeInfo` is a look-ahead in the UNIVERSE** (free-data
miner, 2026-08-12) — same defect class, solved.

### OP-069 a Wayback `id_` 503 is TRANSIENT and PER-RECORD — and "refetch a different URL" is an INVALID control   [active]

**FOUND (CN frontier miner s8, 2026-08-13) while diff-verifying 8btc board page counts. It
produced TWO opposite false conclusions inside ten minutes before the real cause surfaced.**

**THE FAILURE, in the order it happened:** `web.archive.org/web/<ts>id_/<url>` returned a
**107-byte `503 Service Unavailable` body** for `forum-61-1000.html` and `forum-61-999.html`.
Reading #1: *"the archive captured an archived error page"* — i.e. the site was down when crawled,
so this is dead ground. To test the competing rate-limit hypothesis I refetched a **different**
record I knew was good (`forum-2-1009.html`): it returned 255,508 bytes. I concluded *not
rate-limited*, therefore *archived 503*, therefore *board 61 is dead ground*. **Both readings were
wrong.** Refetching **the same record** minutes later returned **236,208 bytes of intact GBK
HTML** — the record was always fine.

**THE MECHANISM:** the throttle/failure on the `id_` raw route is **transient and per-record**,
not global and not per-session. So a successful fetch of URL B carries **zero information** about
whether URL A's failure was real. It is a control that cannot fail, which is why it produced a
confident wrong answer — the welded-gate shape (L1.43) arriving inside a research method.

**THE RULE — three parts, cheapest first:**
1. **CDX `length` IS THE REFEREE, and it is free.** Request `fl=timestamp,original,statuscode,length`.
   CDX said this record was **25,431 bytes**; the body was 107. *The disagreement itself is the
   signal* — a short body against a large CDX length is a TRANSPORT failure, never evidence about
   content. OP-034 already prescribes length-rank triage; **this run skipped it and paid for it.**
2. **The ONLY valid liveness control is refetching THE SAME record** after a pause. Never a sibling
   URL, never a different board, never "the archive seems up".
3. **`statuscode` in CDX is the ORIGINAL crawl status and does not describe what replay returns.**
   Neither field alone is sufficient: status says what the site said, length says how much was
   stored, and only the body says what you actually got. Cross-check all three before writing any
   null.

**WHY THIS BELONGS WITH OP-068 AND OP-034 — one family, three layers.** OP-033 is ENCODING, OP-034
is COMPRESSION, OP-068 is a rendered SHELL, and this is **TRANSPORT**. Every one of them makes a
retrievable page look like an empty or dead one, and every one of them is a **false null that
reads as an exhausted ground**. A miner who writes "this board is dead" from any of the four has
recorded a fact about their fetch, not about the world (L1.28a: unmeasured is never a clean
verdict). **PROPAGATE TO ALL SEATS (§16):** every region seat using Wayback is exposed, and the
cost of the mistake is silently retiring live ground.

_OP-069 field note (CN s9, 2026-08-19): a THIRD transport-layer false-null shape, cheaper than the
503 and easier to mass-produce. An `id_` fetch at a NON-EXACT timestamp answers 302, and curl
without `-L` writes a ZERO-BYTE file for a record whose exact-timestamp fetch returns 55–59KB
intact — six of eight pages of coinsbbs thread-120 read "empty" in one batch because page 1's
timestamp was reused for pages 2–8. Rule: fetch each record at ITS OWN CDX timestamp, always pass
`-L`, and treat a 0-byte body as a fetch-side artifact to re-check against CDX `length` (the same
free referee as the 503 case) — never as evidence about the record, and never as grounds to grade
a capture set hollow._

### OP-070 out-of-range Discuz page aliasing means YOU EXCEEDED THE COUNT — it is not a property of the URL scheme   [active]

**CORRECTS the OP-034 addendum this seat wrote on 2026-08-12**, which concluded from board 233
that *"the board map's page counts for OTHER boards are now suspect the same way"* and flagged
boards 2 / 82 / 61 for re-verification. **That generalisation is now REFUTED by direct content
diff, and the corrected rule is more useful than the warning it replaces.**

**MEASURED (8btc, 2026-08-13, adjacent-page content diff on thread ids):**
- **Board 2 — REAL.** 128 CDX-200 captures, **128/128 above 2 KB** (zero soft-errors), max real
  page **1009**. Pages 1008 vs 1009 share only 24 of ~70 tids; page 1000 (2017) shares **zero**
  with either 2018 page.
- **Board 61 — REAL.** 58/58 captures real, p999 vs p1000 overlap **zero**. Genuine pagination.
- **Board 82 — 26/26 captures real**, max page 1000; not adjacent-diffed, so it stays UNTESTED
  rather than assumed either way.
- **Board 233 — still ~31 threads**, as found 08-12. The aliasing there was real.

**THE RULE:** out-of-range page aliasing occurs **only when the requested page exceeds the board's
real page count** — it is a symptom of asking for a page that does not exist, not a property of
Discuz URLs. So aliasing is a *useful binary-search probe for the true page count*, not a reason to
distrust page counts generally. Small boards alias early; large boards paginate honestly to ~1000+.

**AND THE TEST HAS ONE TRAP, which cost a false hypothesis this run.** Adjacent pages on a
last-reply-sorted board **legitimately share threads** (a thread reordered between two captures two
days apart appears on both), so an *overlap* is NOT evidence of aliasing. I first read the 24
shared tids as pinned stickies; a three-page test refuted that (**zero** recurred across all three).
**Use the set difference, and prefer non-adjacent pages or same-capture pairs:** aliasing means the
sets are IDENTICAL, not merely overlapping.

**CONSEQUENCE FOR THE ERA PLAN:** board 2's ~1009 pages are confirmed real, so the 8btc era plan
built on that count is SOUND and the ground is far larger than the 128 captured pages — the
constraint is capture coverage, not board size.

### OP-071 on a last-reply-sorted board, PAGE DEPTH is a second era axis — and it runs BACKWARDS from the capture date   [active]

**CORRECTS this seat's own s7 method note (2026-08-12)**, which prescribed *"era-seek by CAPTURE
TIMESTAMP of pages 1–9"*. That is right for shallow pages and **inverted for deep ones**, and the
error wastes a whole fetch-and-decode cycle on the wrong decade.

**MEASURED (8btc board 2, 2026-08-13):** capture `20131213073329` of `forum-2-26.html` — a
December-2013 crawl, squarely in the PBoC ban window — returns threads with ids **1–66 dated
September 2012**, not ban-window material at all. Discuz sorts by **last reply**, so a deep page
holds the board's **stalest** threads. The capture date is only an **upper bound** on what can
appear; page depth then walks *backwards* from it.

**THE RULE — read (capture_date, page_number) as a 2-D era selector:**
- **Hunting a dated EVENT window** (a ban, a hack, an exchange failure): take a capture from just
  after the event and read **LOW page numbers**. Event discussion is by definition freshly-replied.
- **Hunting the OLDEST era strata**: take **any** later capture and read **HIGH page numbers**. A
  2018 capture at page 1000 reaches further back than a 2013 capture at page 5.
- **Corollary that saves real budget:** the archive's *capture* coverage and the board's *era*
  coverage are different quantities. 128 captured pages of a ~1009-page board is not "128/1009 of
  the era" — deep captures reach strata that no shallow capture of any date contains.

**FIELD DETAIL for 8btc/Discuz of this era (saves a probe every run):** posts live in
`<div class="t_f" id="postmessage_NN">`, **not** the `<td class="t_f">` that later Discuz skins use;
`t_msgfont` and `postcontent` are both absent. Quoted replies repeat the parent's text with a
`<author> 发表于 <date>` header, so a naive post count **double-counts** a reply chain — dedupe on
the quote header before claiming a thread depth. GBK throughout.

_OP-071 field note (CN s9, 2026-08-19): the post selector varies WITHIN one forum ACROSS capture
dates — 8btc thread pages in the 2014-03 crawl carry `<td class="t_f" id="postmessage_NN">` while
the 2013-12 stratum this note was written from uses `<div class="t_f">`. Parse
`<(?:td|div) class="t_f"[^>]*>` from the first fetch; a 0-match parse on a capture whose CDX
length says it is full-size is a SELECTOR-DRIFT tell, never an empty thread (OP-034's era-selector
trap, one venue narrower). Two more skin details that cost a probe each: coinsbbs writes
`<div id="post_NNN" >` with a space before `>` (anchor with `\s*>`), and 8btc board-list pages
carry titles in `class="s xst"` anchors inside `tbody id="normalthread_TID"` rows — the
thread-URL fragment `thread-TID-1-1` poisons naive date regexes on those rows (strip URLs before
scanning for dates)._

### OP-072 THE POST-2023 PRACTITIONER CORPUS IS LLM-CONTAMINATED, AND THE CONVERGENCE MODULE CANNOT SEE IT   [active]
class: provenance / anti-echo
origin: JP frontier miner s4 (2026-08-13), `perp-screener.com/posts/btc-bot` (2025-12-04)
validated-gain: one carded mechanism demoted from "independent practitioner node" to "LLM echo"
BEFORE it could be counted as convergence; a detectable, datable contamination boundary (~2023)
established for every seat's corpus.

**THE PROBLEM, AND IT IS THE PROVENANCE MANDATE'S OWN FAILURE MODE ARRIVING BY A NEW ROUTE.** The
desk elevates a mechanism when researchers in unrelated ecosystems reach it independently, and the
provenance mandate already names the trap: three regions describing one effect are usually three
readings of one English paper (GAP #85). **Since ~2023 there is a second and much larger shared
upstream: the frontier LLMs.** A JP botter, a KR botter and a BR botter who each ask ChatGPT to
explain their spread's greeks will produce three writeups that agree — **because they queried the
same weights**, not because the market taught them the same thing. Their agreement is a fact about
the model, and `libs/research/convergence.py` cannot distinguish it from a fact about the world.
This is strictly worse than the paper-echo case: an arXiv echo leaves a citation, an LLM echo
leaves **nothing** unless the author volunteers it.

**THE TELL IS TEXTUAL, CHEAP AND HIGH-PRECISION.** Practitioners disclose it casually, in the body,
in their own language. Grep every mined page for:
| region | markers |
|---|---|
| JP | チャッピー (ChatGPT's JP nickname), ChatGPTに聞く／聞いた, GPTに, AIに聞いて, 生成AI, ～によると（AI） |
| EN | "I asked ChatGPT/Claude", "per GPT", "ChatGPT says", "according to the AI", "o3/4o told me" |
| CN | 问了ChatGPT, 用GPT分析, 让AI解释, 大模型说, 豆包／文心 |
| KR | 지피티／챗지피티에게 물어보니, AI에게 물어봤다 |
| RU | спросил у ChatGPT, GPT говорит |
| BR/PT | perguntei ao ChatGPT, segundo o GPT |

**THE RULE — three parts, and the third is the one that keeps this from becoming an excuse to skip
sources.**
1. **A `DERIVES-FROM` field is INCOMPLETE unless it records LLM consultation.** Write
   `DERIVES-FROM: <cites> + LLM (ChatGPT, self-disclosed)`. A page with no disclosure and no
   citations is `DERIVES-FROM: NONE (checked)` **only for pre-2023 material**; post-2023 the honest
   value is **`UNVERIFIABLE`**, because absence of disclosure is not evidence of absence (L1.28a —
   absence must never resolve to a clean verdict, and "independent" is the clean verdict here).
2. **SEPARATE THE OBSERVATION LAYER FROM THE EXPLANATION LAYER, then grade them differently.** What
   the practitioner *did, ran, held and lost* is a first-class observation and LLM contamination
   does not touch it. What the page *concludes about why* may be model output. In the proving
   instance the kill stands at full strength (his realised P&L and his own greeks snapshot) while
   the surrounding mechanism prose is demoted — **the same page yields evidence at one layer and an
   echo at the other**, so this is never a reason to discard a source.
3. **A CONVERGENCE CLAIM ACROSS TWO POST-2023 PAGES MUST NAME THE OBSERVATION THEY SHARE, not the
   conclusion.** If both nodes' agreement lives only in the explanation, it is one node.

**WHY THIS IS A SCOPE EXPANSION AND NOT A FILTER (the mine-everything rule is untouched).** Nothing
here rejects a page, ranks a source lower, or excuses a skipped read. It changes exactly one number:
how much a *second* agreeing source raises confidence. Under-counting real convergence costs a queue
place; over-counting it promotes a mechanism above its evidence, and that reaches capital.

**COROLLARY FOR THE ERA MANDATE, and it makes dead ground MORE valuable rather than less.** Every
archive with a hard end-date before ~2023 — 8btc, btcsec, Ppomppu's legal era, Mt.Gox-era 2ch, the
Quantopian corpus — is **structurally uncontaminated**. Era-archaeology now buys a provenance
guarantee that no living-web source can offer, which is a new and independent reason to keep
digging it.

**ADDENDUM (JP s5, 2026-08-19) — TWO SHARPENINGS FROM THE EARLIEST DOCUMENTED JP WIRING
(`blog.shidokamo.com/trading-bitcoin-with-gpt/`, 2023-12-04):**
1. **THE CONTAMINATION IS BIASED, NOT NOISY — it tilts toward TEXTBOOK CONSENSUS.** The author
   documents GPT-4 in 2023 refusing persona instructions on investment topics and regressing to
   優等生 (honor-student) answers: 「投資関連の話題だから優等生的な回答をするように訓練されている」.
   RLHF pushes financial explanations toward the safe consensus prior, so LLM-echo convergence
   does not just duplicate ONE upstream — it systematically reproduces the CROWD's textbook view.
   Operational edge of the rule: cross-region agreement on a CONSENSUS-SHAPED mechanism is the
   weakest possible convergence evidence post-2023; agreement on a WEIRD mechanism retains more
   value, because the shared-weights explanation predicts consensus, not weirdness.
2. **A THIRD CONTAMINATION LAYER: INTERFACE, below explanation and signal.** The earliest JP
   wiring put the LLM in the CHAT/PSYCHOLOGY loop only (LINE → GPT parses the human's instruction
   → writes trade config to a DB → a dumb executor reads it; the HUMAN decides direction and
   price). Marker taxonomy: INTERFACE contamination (narrative/affect only, decisions human) <
   EXPLANATION contamination (the page's mechanism story is model output) < SIGNAL contamination
   (the model chooses trades). Only the last two demote a convergence node; interface-wired pages
   remain independent nodes for their DECISIONS while their prose still gets the layer-2 check.

### OP-073 WHEN A REGION'S BIG HOSTS CLOSE, THE SAME COMMUNITY'S SELF-HOSTED TAIL IS STILL WIDE OPEN   [active]
class: access / §13 posture
origin: JP frontier miner s4 (2026-08-13), UA-matrix probe over 10 hosts
validated-gain: recovered a mineable JP ground the day after 62% of the mapped corpus was ruled
CLOSED — 8/9 self-hosted blogs serve 200 to `ClaudeBot`, and the run's two best finds came from them.

**MEASURED (2026-08-13, honest UA `ClaudeBot`, content path per OP-052):**
| layer | hosts | robots.txt | content path |
|---|---|---|---|
| big platforms | note.com | **403** (robots itself) | **403** |
| big platforms | zenn.dev | **200, and it ALLOWS `*`** | **403** `{"message":"Please contact the site owner for access."}` |
| big platforms | qiita.com | 200 | **200** (122 kB article body) |
| self-hosted tail | gitan.dev, perp-screener.com, blog.shidokamo.com, pasokon.blog | **404 — no robots.txt at all** | **200** |
| self-hosted tail | rarirure.rip, mirumi.me, yard.tips, coin-news.xyz | 200, clean | **200** |

**THE MECHANISM, WHICH IS WHY THIS GENERALISES.** A curated AI-crawler denylist is a **product
decision made by a platform's legal/infra function**. An individual practitioner running WordPress
on their own domain has no such function, no incentive, and usually **no robots.txt at all**. So the
closure of a region's community layer is a property of the *hosting concentration*, never of the
region — and the writers did not leave, only their landlord changed the lock.

**THE OPERATIONAL RULE:** when a big host closes, **do not re-scope the region — re-scope the HOST
COLUMN.** Any corpus map with a `host` field converts to a work queue in one pass. The JP calendar
map (`data/jp_botter_advent_calendar.jsonl`, 187 rows) went from "62% closed, ground thinning" to
"20 entries across 12 open self-hosted domains, never touched by any seat in four sessions" with a
single group-by. **Build the host column into every corpus map for exactly this reason** — a map
without one cannot be re-aimed when access changes, and access now changes on a timescale of days.

**AND THE PRIZE IS BETTER, NOT JUST AVAILABLE.** The self-hosted tail is written by people who
maintain their own domain to write about one thing for years. It is the deep-forest layer by
construction: no recommendation algorithm, no engagement incentive, no SEO, frequently no comment
section — and in this run it held a **year-over-year venue microstructure survey by the same author**
(`gitan.dev`, 2023 and 2024 editions, a free longitudinal diff) that no platform-hosted post matched.

**§13 UNCHANGED AND EXPLICITLY SO:** this widens WHERE you look and never HOW you get in. `note.com`
and `zenn.dev` remain HARD STOP including their archives; the only fetches made against them this
run were `robots.txt` and zero-body status probes to re-verify the block.

### OP-074 `robots.txt` ANSWERS "MAY I?", NEVER "IS THERE ANYTHING HERE?" — GRADE EXISTENCE SEPARATELY   [active]
class: access / ground validation
origin: AR frontier miner s2 (2026-08-13), correcting the AR seat's own s1 grade
validated-gain: killed a #1-priority ground that never existed, before it consumed a second run.

**THE ERROR, and it is mine.** AR s1 (2026-08-12) ran the OP-052 UA matrix over 16 hosts and graded
`mql5.com/ar` **OPEN — "correct path not yet found (`/ar/code` is a uniform 404)"**, then carried it
to the **top** of the next-ground list as the region's EXECUTABLE-tier prize. Measured this run:
MQL5 publishes **11 hreflang locales** (`en ru zh es pt de ja ko fr it tr`) and **`ar` is not one of
them**. Control: `/{loc}/code` returns **200 for 11/11 real locales, 404 for `ar` alone`**.
**There is no Arabic MQL5.** The 404 was never a wrong sub-path — it was the site saying the locale
does not exist, and a whole run was queued against a ground that was never there.

**THE MECHANISM.** `robots.txt` is served by the **policy layer**, which answers a question about
*permission* and is completely indifferent to whether any content sits behind the path. A clean
`robots.txt` on `example.com` says nothing whatever about `example.com/ar`. OP-052 already warned
that robots is necessary and not sufficient **for access** — this is the same gap pointed at
**existence**, one axis over, and it is easier to fall into because a clean robots feels like good news.

**THE OPERATIONAL RULE — two independent gradings, never one:**
| question | instrument | failure if skipped |
|---|---|---|
| *May I fetch it?* | `robots.txt` + content-path probe under the honest UA (OP-052) | you dig a ground that refuses you |
| *Does it exist at all?* | **the site's own enumeration** — `hreflang`, sitemap, locale switcher, API index — plus a **sibling control** | you queue runs against a ground that was never there |

**THE SIBLING CONTROL IS THE CHEAP HALF AND IT IS WHAT SETTLES IT.** A bare 404 is ambiguous between
*wrong path* and *no such thing*. Probe the **same path shape across every sibling** the site does
publish: 11/11 siblings 200 and yours alone 404 converts an ambiguous 404 into a **measurement**.
This is the L1.62 discipline (a denominator that was assumed is not a measurement) applied to a ground.

**FLEET NOTE:** a ground graded from robots alone must carry the grade **`OPEN (existence UNMEASURED)`**,
never bare `OPEN`. Absence of a block is not presence of a corpus, and a next-ground list is exactly
where that conflation gets expensive — it is inherited and acted on by a future run that cannot see
how the grade was reached.

---

### OP-075 THE LANGUAGE IS NOT ALWAYS THE MOAT — MEASURE WHETHER THE REGION'S PRACTITIONERS WRITE IN IT   [active]
class: region strategy / seat aiming
origin: AR frontier miner s2 (2026-08-13); calibrated against CN/RU/KR on the same instrument
validated-gain: re-aimed the AR seat off a layer that structurally cannot hold an edge.

**THE PREMISE EVERY REGIONAL SEAT INHERITS:** dig in language X and you reach material the
English-speaking crowd cannot read. **It is true for CN/KR/JP/RU/PT and it is FALSE for AR**, and no
seat can tell which case it is in without measuring.

**MEASURED — native-key repo search (OP-054), one instrument, four scripts:**
| script | "arbitrage" term | repos | max ★ |
|---|---|---|---|
| **CN** | `套利` | **1,174** | 671 |
| **RU** | `арбитраж` | 24 | 12 |
| **KR** | `차익거래` | 6 | 2 |
| **AR** | `المراجحة` / `مراجحة` / `أربيتراج` | **1 / 0 / 0** | 0 |

AR `التداول الكمي` (quantitative trading) = **0**; `اكسبيرت` (expert advisor) = **0**. Every hit
across seven AR terms has **0–1 stars** and is a Telegram signal-bot promising *نسبة نجاح ٩٥٪*.

**TWO HYPOTHESES SURVIVE THAT TABLE AND THEY DEMAND OPPOSITE ACTIONS — SO RUN THE DISCRIMINATOR:**
**H1** the practitioner population does not exist → the region is genuinely empty, deprioritise it.
**H2** it exists and **writes in English** → the region is fine, the *language layer* is the wrong door.
**Discriminator: search the developer population by LOCATION instead of by language**, with a control:
| location + "trading" | users | | control | users |
|---|---|---|---|---|
| **UAE** | **67** | | **Korea** | **59** |
| Egypt | 24 | | Egypt + "quant" | 7 |
| Saudi Arabia | 8 | | Saudi + "quant" | 1 |

**H1 REFUTED, H2 CONFIRMED:** ~99 AR-region developers mention trading — **UAE alone exceeds the KR
control** — while the AR-language corpus is 0–1. The people are there; the *language* is not where
they write. *(`location:` is self-reported and sparse and I queried `UAE`/`Korea` rather than the
full names, so both sides are undercounted **by the same mechanism** — a lower bound on each, which
is why the direction is robust while the levels are not.)*

**THE CONSEQUENCE, and it is the operator:**
> Where a region's technical class writes in English, its native-language layer is **not a hidden
> technical corpus — it is the retail/promotional layer**, and that is exactly and only what a
> native-key search will return. Worse, anything technical those practitioners *do* produce is
> **already inside the EN seat's ground**, so there is no language arbitrage to win, and further
> native-key digging cannot create one.

**WHAT A SEAT IN THIS POSITION SHOULD HUNT INSTEAD:** what is native-language **by institutional
construction** and therefore *cannot* migrate to English — regulator publications, exchange notices
and rulebooks, court/enforcement records, national statistics, and any religious/legal certification
layer. Those are written in the local language because an institution is **required** to write them
that way, which is a far more durable moat than a preference a developer can drop at any time.

**RUN THIS PROBE ON EVERY REGIONAL SEAT — IT IS ~8 CHEAP QUERIES** and it decides whether the seat's
entire premise holds. **AND DO NOT GENERALISE THE AR ANSWER**: the CN column is a 1,174-repo corpus
where the language absolutely is the moat. The point is not that language never matters — it is that
**which case you are in is a measurement, and every seat has been assuming it.**

---

### AR (ARABIC) LEXICON — dark-forest deliverable #2, seeded s1, extended s2 (2026-08-13)
_Search keys, not trivia. Counts are GitHub repo-search totals under the honest UA, 2026-08-13._

| term | gloss | era | status / example query |
|---|---|---|---|
| `تداول` | trading | all | 260 repos — **the broad key**; retail-dominated |
| `تداول آلي` | automated trading | all | 11 repos — the closest AR key to "algo trading" |
| `بوت تداول` | trading bot | 2020→ | dominant AR framing; almost always Telegram-signal shaped |
| `المراجحة` / `مراجحة` | arbitrage (formal) | all | **1 / 0** — and the 1 is car pricing, not markets |
| `أربيتراج` | arbitrage (transliterated) | 2017→ | **0 on GitHub, ABUNDANT on YouTube** — the AR arb vocabulary lives in video, not code |
| `فرق السعر بين المنصات` | "price difference between platforms" | all | **the folk term for cross-venue arb** — outperforms `المراجحة` on video search by a wide margin |
| `التداول الكمي` | quantitative trading | — | **0** — the concept has no AR-language footprint |
| `اكسبيرت` | expert advisor (MT4/5 EA) | MT4 era | **0** — note KR/RU/CN all have EA corpora; AR does not |
| `العقود الآجلة` | futures contracts | all | the standard AR term; high-volume on video |
| `العقود الدائمة` | perpetual contracts | 2019→ | perps specifically — distinguishes from `الآجلة` |
| `رسوم التمويل` | funding fees | 2020→ | **the funding key** — maps to the desk's only repeat-survivor family |
| `التصفية` / `التصفية القسرية` | liquidation / forced liquidation | all | liquidation-cascade vocabulary |
| `السيولة` | liquidity | all | general |
| `تحليل فني` | technical analysis | all | 12 repos; the dominant retail frame |
| `عملات رقمية` / `العملات المشفرة` | digital currencies / cryptocurrencies | all | 27 repos; the broad crypto key |
| `مضاربة` | speculation / short-term trading | all | folk term, carries a mildly pejorative/religious charge |
| `تقابض فوري` | immediate possession (Sharia) | doctrinal | **the fatwa-layer key** (s1) — the constraint that makes a doctrinal pool spot-only |
| `زكاة` | zakat (2.5% mandatory wealth levy) | doctrinal | s1's forced-flow candidate; calendar-predictable obligation |

**THE LEXICON'S OWN LESSON (s2):** `أربيتراج` returns **0 GitHub repos and a full page of YouTube
results**. A term's count is **per-surface**, and grading a term dead from one surface is the
false-exhaustion mode OP-054 names. Record the surface beside the count, always.

#### OP-074 ADDENDUM (AR miner s2, 2026-08-13): on WordPress, `Disallow: /wp-content/uploads/` DISALLOWS THE ENTIRE DOCUMENT CORPUS

**MEASURED:** `aaoifi.com` (AAOIFI — the Islamic-finance standards body, and under **OP-075** exactly
the institutionally-native Arabic layer an AR seat should hunt). `robots.txt` = **200**, `User-agent: *`,
**no by-name refusal of any AI agent** — a host any seat would grade **OPEN**. Its disallow list is the
stock WordPress boilerplate: `/wp-admin/`, `/wp-content/`, **`/wp-content/uploads/`**, `/uploads/`.

Then the content path: `https://aaoifi.com/shariaa-standards/?lang=en` = **200**, fully readable — and
**every single document link on it** resolves to `https://aaoifi.com/wp-content/uploads/YYYY/MM/*.pdf`.

**THE POINT:** on WordPress, `/wp-content/uploads/` **is** the media store. A host that allows `*`
everywhere *except* uploads has therefore **disallowed its whole PDF/document corpus** while presenting
as open. The HTML is browsable; the standards, rulings, research papers and conference reports — the
only part with research value — are not fetchable under §13.

**WHY IT BITES PRECISELY THE CAREFUL SEAT:** the boilerplate exists to stop media-file indexing, not to
protect a corpus, so it reads as housekeeping and gets skimmed. A seat that grades the host OPEN from
the preamble and then harvests PDFs **is violating robots while believing it is compliant** — the
§13 gate failing silently in the one direction the gate cannot self-report.

**THE RULE:** grade the **path the documents actually live on**, never the host. Resolve one real
document URL and re-check it against the disallow list *before* claiming a corpus is reachable.
`Allow: /` on the host and `Disallow:` on its media root is a **CLOSED corpus on an OPEN site**, and it
is the single most common shape on the WordPress-hosted institutional web — regulators, standards
bodies, central banks and exchanges are overwhelmingly WordPress.

### OP-076 PERMISSION AND REACHABILITY ARE INDEPENDENT — IN BOTH DIRECTIONS, ON THE SAME HOST   [active]
class: access / §13 posture
origin: AR frontier miner s2 (2026-08-13), GCC exchange + regulator layer, honest UA `ClaudeBot`
validated-gain: caught a host that **permits us by name and serves us nothing**, and a sibling host that
**refuses its own robots.txt and serves a full JSON trade tape** — the same venue, opposite failures.

**THE PROVING INSTANCE — one venue, `bitoasis.net`, measured the same minute:**
| surface | robots.txt | content | reading |
|---|---|---|---|
| `bitoasis.net` | **200 — `User-agent: ClaudeBot` / `Allow: /`** (and `anthropic-ai` Allow; `CCBot` Disallow) | **403** on `/`, `/en/`, `/en/prices`, `/en_sitemap.xml`, `blog.` | **permitted and unreachable** |
| `api.bitoasis.net` | **403 — the policy file itself is refused** | **200 JSON**, incl. a real trade tape (`id/type/price/amount/timestamp`) | **unstated and fully reachable** |

**Neither surface's policy predicts its own reachability, and the two point opposite ways.** The
edge/CDN layer and the policy layer are configured by different teams with different intents, and
nothing reconciles them — so a seat that infers one from the other is wrong roughly half the time,
in whichever direction it happens to guess.

**THE §13 CONSEQUENCE, AND IT IS NOT SYMMETRIC.** These two errors are *not* equally bad and must not
be traded off:
- Inferring **permission from reachability** ("it served me, so I may") is the one that **breaches
  §13**. A 200 is never an authorisation.
- Inferring **unreachability from refusal** ("robots 403s, so the host is closed") merely **loses
  ground** — here it would have cost a live venue tape.
So: **read the policy where it is stated, and measure reachability separately — never substitute
either for the other.** Where policy is genuinely unstated (a 403 or 404 on `robots.txt`), that is
**UNMEASURED**, not permission, and the honest move is to record it as such.

**AND TWO FALSE-200 CLASSES FOUND IN THE SAME SWEEP** (both extend OP-068 — a 200 that is not content):
1. **`coinmena.com/robots.txt` → HTTP 200, `text/html`, a Next.js `__next_error__` shell, ZERO
   directives.** A parser reading this as "permissive robots, no rules" gets the answer exactly
   backwards: nothing is served at all. **A robots.txt that is not `text/plain` is not a robots.txt** —
   check the content type before parsing a permission from it.
2. **`sca.gov.ae` (now `uaecma.gov.ae`) open-data section → every page HTTP 200, every dataset behind
   `POST /api/PublicApi/GetContentList` returning 401.** The 200s are real; the data is not retrievable
   through them. A status-code-only crawl scores this host **open and productive** and harvests nothing.

**THE RULE THAT COVERS ALL THREE:** a host has **three independent properties** — *stated policy*,
*reachability*, and *whether the reachable thing is the payload* — and this desk had instruments for
only the first two. Grade all three, and let **UNMEASURED** stand where you only measured some
(L1.28a: absence must never resolve to a clean verdict).

**FLEET NOTE — the positive half is worth carrying too:** `bitoasis.net` is the **first host in the
fleet's whole access map to name `ClaudeBot` with `Allow: /`**. Every by-name mention found until now
was a refusal (hawamer, 5ch, DCInside, EliteTrader, Gate). Per-agent policy is real and it cuts **both**
ways, so re-probe rather than carrying a binary open/closed prior — and note that AR s1 read this same
file on 2026-08-12 as *"ClaudeBot unnamed, falls to `*`"*. Either it misread or the file changed inside
24h; **either way the lesson is the same — a policy read is a dated observation, not a standing fact.**

#### OP-076 ADDENDUM (AR s3, 2026-08-19): PROBE BOTH HOSTS AND USE GET — an apex robots-403 said nothing about www

`adgm.com/robots.txt` → **403** (Akamai edge, `errors.edgesuite.net`), and s2 recorded the ground
UNMEASURED on that basis. Measured today: `www.adgm.com/robots.txt` → **GET 200 `text/plain`**, a
real 9-directive policy naming exactly which paths are closed — which flipped a 5,302-URL corpus
(1,111 dated announcements + 3,848 register pages) from UNMEASURED to **readable-policy OPEN** in
one request. Second GCC host with a per-host policy split (bitoasis apex-vs-api was the first).
And on `vara.ae` the same day: `HEAD /robots.txt` → 404 HTML while `GET` → 200 robots-format
(JAMstack/CDN edges special-case HEAD). **Rule: a robots grade is per-HOST (apex ≠ www ≠ api) and
per-METHOD (GET only, never HEAD); an UNMEASURED verdict requires the www + GET probe to have been
run before it is recorded.**

---

### OP-077 AN ADF p-VALUE ON OLS RESIDUALS IS NOT A COINTEGRATION p-VALUE — AND THE GAP IS 3.6× NOMINAL   [active]
class: mined-artifact validation / statistical
origin: BR frontier miner s3 (2026-08-13), `Vido/zecontinha` (Apache-2.0, 14★, live since 2019)
validated-gain: **measured** the actual size of a live public pair-trading screen at **17.97% against
its own nominal 5%**, by Monte Carlo on its exact window, rather than asserting the textbook objection.

**THE PATTERN, and it is the single most common defect in mined pairs-trading code.** An
Engle–Granger implementation does:

```python
X   = sm.add_constant(series_x.values)
res = sm.OLS(series_y, X).fit()
adf = adfuller(res.resid, autolag='AIC')     # <-- p-value taken from HERE
```

`adfuller` returns Dickey–Fuller p-values, which are correct for a series **given in advance**. These
residuals are not given in advance: OLS *chose* β to minimise their variance, so they are the most
stationary-looking linear combination available in-sample. The test therefore over-rejects "no
cointegration". `statsmodels.tsa.stattools.coint()` exists precisely to apply the MacKinnon critical
values that correct for the estimated cointegrating vector.

**MEASURED (4,000 trials, two INDEPENDENT random walks, n=120 — the exact window this system
broadcasts; seed 20260813):**

| pipeline | rejections at α=0.05 | rate | 95% CI |
|---|---|---|---|
| `adfuller(OLS.resid)` — theirs | 719 / 4000 | **0.1797** | [0.168, 0.192] |
| `coint(y, x)` — MacKinnon | 304 / 4000 | 0.0760 | [0.068, 0.084] |

**3.59× its own nominal size; 2.37× the correctly-sized test.** (`coint()` at 7.6% is itself a little
above 5% at n=120 — finite sample — which is worth knowing before anyone treats the correct test as
exact at short windows.) The null used here is *independent* random walks; real crypto perps are
strongly co-moving, which makes spurious residual stationarity **more** likely, so 17.97% is a
conservative floor rather than a worst case.

**THE OPERATOR:** in any mined pairs/statarb artifact, grep for `adfuller` applied to a regression
residual. If the residual came from a fitted model and the p-value came from `adfuller`, **the stated
significance is wrong in a known direction and can be re-priced in minutes**. Do not argue it — run the
null through their own window and report the realised size. Applies identically to
`ts.OLS → adfuller`, `np.polyfit → adfuller`, and any hand-rolled "spread" z-test.

**TRANSFERS BEYOND COINTEGRATION:** the general form is *a test statistic evaluated against critical
values derived for a quantity that was not estimated from the same data*. Same error class as scoring
an in-sample-selected feature with textbook t critical values.

---

### OP-078 A FORK TREE AND A FILE HISTORY BOTH LOSE MEMBERS SILENTLY — COUNT THE ATTRITION (L1.60 applied to MINING)   [active]
class: enumeration / denominator integrity
origin: BR frontier miner s3 (2026-08-13), `Vido/zecontinha` fork tree + `binance_futures.py` history
validated-gain: two independent silent-loss channels found in one repo walk, both of which make a
ground look **smaller and duller than it is**, and one of which makes a 404 indistinguishable from a null.

**CHANNEL 1 — TOMBSTONE FORKS. `/forks` over-reports; the count under-reports; neither is the tree.**
`Vido/zecontinha` publishes `forks_count: 6`. The `/forks` endpoint returns **8**. The two extra
(`yoshimorimori`, `igor110055`) are **HTTP 404 on both API and HTML** — deleted or renamed accounts
still served as fork entries. Divergence over the 6 live forks:

| fork | status |
|---|---|
| bryantoken, marcosilvaa | identical (ahead 0) |
| kenanfint | behind 10 |
| marcusfreire0504, IlmerO, webclinic017 | behind 144 |
| yoshimorimori, igor110055 | **404 — tombstone** |

**ZERO forks ahead by even one commit.** So "6 forks" was a *popularity* signal, not a development
signal — and a fork-walker that treats non-200 as "skip" drops the tombstones out of its denominator
and reports "6 forks, all clean" when what it measured was 6 of 8. **A tombstone 404, a rate-limit
block and a network failure are byte-identical to that walker** — R0466's false-null, and exactly the
attrition L1.60 fences inside this desk, here firing on a mining instrument instead.
**Count the 404s and name them as a third state.**

**CHANNEL 2 — `?path=` IS RENAME-BLIND, AND IT COST 73% OF THE HISTORY.**
`GET /repos/{r}/commits?path=src/coint/binance_futures.py` → **3 commits, oldest 2025-11-18**.
That oldest commit is *"Moves django files to src/"*. Re-querying the pre-move path
`coint/binance_futures.py` → **8 more, oldest 2020-06-28**. True history **11**; the obvious query
reports **3**. A seat dating an artifact from the current path would have called a 2020 file a 2025
one and mis-dated everything derived from it.
**Operator: when the oldest commit a path returns is a move/rename/restructure commit, that is not the
beginning — it is the seam. Re-query the old path (and repeat).**

---

### OP-079 IN A NON-ENGLISH REPO, THE CODE LAYER AND THE NEGOTIATION LAYER ARE IN DIFFERENT LANGUAGES — QUERY BOTH   [active]
class: lexicon / language routing — refines OP-075 from the opposite direction
origin: BR frontier miner s3 (2026-08-13), `Vido/zecontinha` PR threads #27/#28/#30/#35
validated-gain: names *where inside one artifact* the native-language moat actually sits, after
AR s2's OP-075 established that a region's practitioners may simply write in English.

**THE PROVING INSTANCE — one repo, one thread, two languages, stated as policy by the maintainer:**

> **Vido (2025-10-22):** *"I believe all public communications (and code base) should be in English.
> Hopefully this will grant this project the greatest reach and it will be accessible to the most
> developers — **not just the lusophones**."*

…written in reply to a Brazilian contributor who had just asked, **in Portuguese**, which language to
use (*"Salve @Vido, você prefere que eu siga com as mensagens dos PR em ingles ou portugues?"*).

So on this artifact: **code, identifiers, commit messages and PR titles are English by explicit policy;
the human negotiation around them is Portuguese.** OP-075 measured that an AR-region population writes
its *code* in English and concluded the language is not a moat there. This is the refinement: the
language boundary does not run around the repo, **it runs through it**, and it separates the layer that
is easy to find from the layer that carries the reasoning.

**THE CONSEQUENCE FOR SEARCH:** an English-key search finds this repo and its code. A Portuguese-key
search finds the *discussion*. They are the same artifact and only the second contains the maintainer
explaining what the system actually does (see OP-080). A seat that queries one key and grades the
ground has measured **half** of it — and it is the half the crowd already has.

**Residual traces even under an English-only policy** (these are the greppable seams): early
identifiers the policy was adopted too late to remove — `gera_pares`, `calcula_modelo`, `PERIODOS_CALCULO`,
`ativo_x`/`ativo_y` — plus Portuguese code comments (`# limpa o canvas`, `# TODO: descobrir qual é correto`).
**Grep the identifiers, not the prose:** a project can enforce English on prose far more easily than it
can rename its own variables.

---

### OP-080 THE MAINTAINER'S OWN WORDS IN A PR THREAD OUTRANK THE README — AND SOMETIMES REFUTE THE SYSTEM   [active]
class: depth / comment layer
origin: BR frontier miner s3 (2026-08-13), `Vido/zecontinha` PR #30
validated-gain: a single reply established that a public signal feed had been **broadcasting a uniform
random draw** — a fact absent from the README, the code comments, and every surface description.

**THE COMMENT (PR #30, maintainer, 2025-10-21), and nothing else on the artifact says it:**

> *"`select_pair(n)` was just a silly function to **draw a pair**, to show case it on Telegram.
> What ends up happening was **Telegram folks see it as recommendations. Which they are NOT!**
> Let's face it: this silly function is now a major interaction point with the users.
> I don't think a random draw is applicable any more."*

The surface — a live site, a Telegram channel, a cointegration engine, an ADF/Hurst/half-life panel —
reads as a signal service. The comment layer says the selection step was **`order_by('?')`**, Django's
random ordering, and that the audience had been reading noise as advice for years.

**THE OPERATOR:** on any mined system that emits a signal, find the code path from *table* to
*published output* and then find the **maintainer's own commentary on that specific function**. The
README describes the machinery; the PR thread is where someone admits what the machinery is *for* and
what it is *not*. Ranked by yield, on this artifact: PR review comments ≫ issues ≫ commit messages ≫ README.

**AND THE RESEARCH ASSET IT CREATES — a documented control arm, which is the rarer half of this find.**
Because the switch from random draw to screened selection is **dated and attributable** (PR #30 merged
2025-11-06; template versioned `v3`, now `v4`), the channel's own public history contains a
**random-pair-selection baseline followed by a screened one, on the same universe, published with
timestamps**. Any future test of "does a cointegration screen beat drawing a pair out of a hat" has its
control arm already broadcast in public. **Look for the regime change, not just the current behaviour.**

---

### OP-081 A GENRE KEY AND A TOPIC KEY SELECT ON DIFFERENT AXES — UNION THEM, NEVER `AND` THEM   [active]
class: query construction / lexicon — the structural sibling of OP-054
origin: BR frontier miner s3 (2026-08-13), `TCC` as a search key over BR quant repos
validated-gain: graded a queue item predicted "RICH SEAM" as **narrow**, with the number that shows why,
and salvaged the key's real use instead of discarding it.

**MEASURED, one instrument, same minute (GitHub repo search):**

| query | repos | |
|---|---|---|
| `TCC bitcoin` | **29** | the genre key works |
| `TCC trading` | **18** | works |
| `TCC criptomoedas` | **15** | works |
| `TCC cointegração` | **1** | **genre ∩ topic ≈ ∅** |
| `cointegração` alone (BR s2) | **30** | the topic key alone |
| `dissertação trading` | **0** | the *formal* genre word is dead |
| `"undergraduate thesis" trading` (EN control) | 8 | the EN genre word is weaker |

**THE RULE.** A **genre/structural key** (`TCC`, thesis, dissertation, 卒論, 졸업논문, 毕业设计,
дипломная работа) selects on *document type*. A **topical key** (`cointegração`) selects on *subject*.
They are near-independent, so **ANDing them multiplies two already-small selectivities** and collapsed a
30-repo corpus to **1**. Union them; run each separately and merge.

**A GENRE KEY IS A PRECISION KEY, NOT A RECALL KEY.** Everything `TCC` returns really is thesis code —
which is worth having, because thesis code is rigorous-looking, uniformly never out-of-sampled, and
unread by the English crowd (L1.34 #6). Use it to *characterise* a corpus you found some other way,
never as your way in.

**TEST EVERY GENRE WORD; DO NOT ASSUME THE FORMAL ONE.** `dissertação` → **0** while `TCC` → 29, in the
same country, in the same language. Only one of a region's several thesis words survives as a repo
label, and it is generally the **colloquial abbreviation**, not the formal noun. Guessing costs a clean
zero that reads exactly like an empty ground — the OP-054 false-exhaustion failure arriving through the
genre axis instead of the topic axis.

**AND GRADE BY NON-UPSTREAM PATHS, NOT BY REPO COUNT.** `cadilhe/freqtrade_2020_tcc` is a **vendored
fork of freqtrade** — 428 blobs, of which the student's own work is a handful of files under
`user_data/`. Student repos are disproportionately whole-framework forks, so a genre key's raw counts
**overstate** the corpus. Open one before believing the number.

---

### OP-082 WHEN A BACKTEST PUBLISHES AN IMPLAUSIBLE WIN RATE, LOOK FOR THE TRADES IT PUT IN A DIFFERENT FILE   [active]
class: backtest mining / survivorship
origin: BR frontier miner s3 (2026-08-13), `cadilhe/freqtrade_2020_tcc` backtest artifacts
validated-gain: turned an **87.1% win rate, +8.78%** headline into a measured **+5.87%** in one fetch —
a **49.6% overstatement** — using only arithmetic already present in the repo.

**THE PATTERN.** Backtesting frameworks report positions still open when the run ended **separately**
from closed trades, because they have no exit price for them. The headline table is therefore a table
of **trades that closed**, and in any strategy that exits winners on a target while letting losers run,
**closing is correlated with winning**. The open-trade file is where the losers accumulate.

**MEASURED on one artifact** (freqtrade, Binance spot /BTC, 23 pairs, 5m):

| file | trades | win | loss | win rate | tot profit |
|---|---|---|---|---|---|
| `backtesting_report_*.txt` (headline) | 411 | 358 | 53 | **87.1%** | **+8.78%** |
| `left_open_*.txt` (a *separate file*) | 14 | 1 | **13** | 7.1% | **−2.91%** |
| **true combined** | 425 | 359 | 66 | 84.5% | **+5.87%** |

Average duration gives it away independently: **4d23h** for the left-open set against **1d0h** for the
closed set — the trapped losers are ~5× older than the trades that got counted.

**THE OPERATOR:** an implausible win rate (>80%) with a **small average profit per trade** is the
signature. Before reading anything else, (1) find the open-trades/unclosed report and add it back;
(2) check for an exit rule that can only fire in profit (`sell_profit_only`, "only sell green",
take-profit-without-stop) — that is the mechanism that *manufactures* the pattern; (3) compare average
durations between the two sets. **Do not report the headline number even to dismiss it** — recompute
and report the combined one.

**AND KEEP THE MECHANISM SEPARATE FROM THE ARITHMETIC.** On this artifact the arithmetic is certain and
the *cause* is not: `Strategy001.py` sets `sell_profit_only = True` while `config.binance.json` sets it
`false`, and **config overrides strategy** — so which was live is undeterminable from the repo. State
the recomputed number as fact and the mechanism as a hypothesis with its falsifier. (The vendored OHLCV
under `user_data/data/` makes that falsifier genuinely runnable, which is what EXECUTABLE tier means.)

---

## OP-083 — THE DESK IMPORTED BRAIN'S **THRESHOLDS** (which do not port) AND MISSED ITS **RATIOS** (which do)

**SOURCE:** `rocky-d/wqb` v0.2.5 (**MIT**, 272★, `wqb/wqb_session.py` + `wqb/wqb_urls.py`), read as
text 2026-08-13. **DERIVES-FROM:** independent of `libs/validation/brain_calibration.py`, which was
built from a *webinar transcript* — different artifact, different author, no shared lineage.
**§13:** MIT, read-only, mined as text. **No credential was held, sought or used, and no call was made
to `api.worldquantbrain.com`** — the library is an authenticated client and this seat does not touch
authenticated surfaces.

**THE FIND IS A NEGATIVE SPACE, not a new operator.** `brain_calibration.py` already imports BRAIN's
constants — fitness bar 1.0, Sharpe bar 1.0, Sharpe target 1.25, self-correlation cap 0.7, truncation
band, recent-Sharpe floor, IS/OOS score weights. Its own docstring then spends ten lines warning that
these are US-equity, daily-rebalanced, dollar-neutral numbers on the platform's own PnL and
annualisation conventions, **"COMPARABLE IN ORDER OF MAGNITUDE ONLY"**, and that *"a reader who takes
1.25 as a threshold has misused this module"*. That warning is correct.

**But a transcript states THRESHOLDS and an API states the MEASUREMENT NAMESPACE, and the desk only
ever had the transcript.** `filter_alphas_limited` enumerates the platform's queryable alpha metrics,
and four of them are **dimensionless ratios of two quantities measured the same way** — so every
convention difference the caveat warns about (annualisation, cost base, return definition,
periodicity) **cancels in the numerator and denominator**. The un-portable half was imported; the
portable half was never seen.

| BRAIN metric (API name) | what it computes | crypto analogue | desk status |
|---|---|---|---|
| `os.osISSharpeRatio` | OOS Sharpe ÷ IS Sharpe — one number for *how much of the backtest survived contact with unseen data* | forward-clock Sharpe ÷ Stage-A screen Sharpe, per candidate | **ABSENT** (grep: no `os_is`/`oos_is`/`degradation` metric) |
| `os.sharpe60/125/250/500` | OOS Sharpe re-measured at four horizons — a **decay ladder**, not one verdict | same ladder in **OBSERVATIONS, never days** (L1.48): a perp desk funding 3×/day accrues evidence ~3× faster than a daily-rebalanced equity book, so copying 60/125/250/500 as *days* would import an equity sampling convention as if it were a law | **ABSENT** (grep: zero hits) |
| `os.preCloseSharpe`, `os.preCloseSharpeRatio` | Sharpe recomputed at pre-close vs at the close print — *does this edge only exist at the stamp?* | entry shifted off the UTC bar boundary / off the funding settlement stamp | **PARTIAL** — `earnability.phase_sensitivity` already tests *funding-settlement binning* (L1.47's instrument) and is well-built; it does **not** test *decision-timestamp* sensitivity, which is the different question |
| `is.selfCorrelation` **vs** `is.prodCorrelation` | **two** correlation gates: against your own prior alphas, and against the **production book** | candidate vs desk's own screened pool; candidate vs **capital already deployed** | **HALF** — `BRAIN_SELF_CORRELATION_CAP = 0.7` imported; the **prod** half absent |

**WHY THE `prodCorrelation` HALF IS THE ONE THAT MATTERS (L1.18).** `selfCorrelation` asks "have I
already tried this?"; `prodCorrelation` asks **"does this duplicate what is already taking capital?"**
Only the second one protects the geometric-growth argument, because two correlated deployed sleeves
draw down together. The desk has `cohort_independence`, `effective_bets` and `panel_breadth`, but
grep finds **no candidate-vs-deployed gate at promotion time**. The objection writes itself — the desk
runs ~1 deployed sleeve, so the gate is near-vacuous today — and it is exactly backwards: **a gate is
cheapest to build while its denominator is 1 and binding from the moment the second sleeve lands.**

**THE TRANSFERABLE RULE, and it generalises past this platform (L1.34/L1.11a).** When mining any
foreign venue, asset class or institution: **a threshold is asset-class-bound and does not travel; a
ratio of two like-measured quantities is unit-free and travels intact.** Prefer the ratio every time.
This is why an equities platform can still teach a perp desk something — the caveat that correctly
blocks its *numbers* does not touch its *instruments*.

**HONEST LIMITATION OF THE SOURCE.** Every enum in `wqb/__init__.py` (`Neutralization`, `NanHandling`,
`Pasteurization`, `UnitHandling`, `Region`, `Universe`, …) is aliased to `Any`. The library gives the
**parameter namespace and exact API paths, not the value sets** — so this find names *what the platform
measures*, and cannot name *what values it accepts*. Recorded so the next seat does not re-open it
expecting enums.

**Also confirmed from the wild (see OP-084): `ts_zscore`, `ts_av_diff`, `ts_corr`, `group_rank` are
real platform operators** — `ts_zscore` is one of the six this desk still lacks.

### 2026-08-30 addendum — OP-083 now has executable population semantics and four falsifiers

Public MIT `myacgl/ProdMemo` at `c0e2402bb199c2aef82d6377ccb44e8bde671711` gives the first
reproducible specification found for the *population* behind BRAIN correlation diagnostics. It
first-differences cumulative PnL over four calendar years, compares within region, separates the
user's OS pool from `POWER_POOL:POWER_POOL_ELIGIBLE`, and persists pool size, window, algorithm
version and a pool fingerprint. Platform production correlation is a third, distinct record and is
cached with its own timestamp. That sharpens OP-083: **candidate-vs-prior, candidate-vs-peer pool,
and candidate-vs-production are three denominators, never aliases.** DERIVES-FROM: NONE declared
for the local correlation implementation (checked README and source). [§33: screened ->
`data/brain_hunter_s35_active_book_correlation_audit.json`]

Public MIT `Fin-Agentian/openalpha` at `405828e54f2be8c1d8b5facead3f537f8490727c` independently
states the correct portfolio question—rank passing candidates by residual PnL variance against the
ACTIVE book—but its implementation supplies four **negative controls** for any R0602 repair:

1. it refuses to measure a book with fewer than two incumbents, although one incumbent is already a
   valid candidate-vs-book comparison;
2. it selects the 200 highest-Sharpe candidates *before* independence, deleting modest-standalone,
   high-marginal candidates before the relevant score exists;
3. `LinAlgError` returns `resid_frac=1.0`, awarding a failed projection maximum independence; and
4. its PnL cache has no TTL or content revision, so a live portfolio decision can consume an
   arbitrarily stale return panel.

The MT5 analogue is candidate net-R versus every deployed Fusion sleeve and the book aggregate on
jointly observable forward timestamps, using point-in-time bid/ask, fills, spread, commission, swap
and markout. `translate_to_mt5("production correlation active portfolio orthogonality")` currently
returns no row, so this explicit mapping is also a named translation-table gap; absence was not read
as no analogue. Thresholds do not transfer. The instrument does. OpenAlpha explicitly derives from
a private IQC 2026 harness and named legacy scripts, so it is convergence at the **method** level,
not an independent implementation lineage.

---

## OP-084 — MEASURED: THE INDEPENDENCE CAME FROM THE **DATA**, NOT THE **MATH** (49 fields, 8 operators, 48/50 single-operator)

**SOURCE:** `CrisperX/50_WorldQuant_Alpha_Examples_for_Alphathon` (85★, **NO LICENCE ⇒
all-rights-reserved**), `alpha50.csv`, 14,891 B, last pushed 2023-10-30. **DERIVES-FROM:** named as
the specific prize in this organ's own s2 next-ground list; no other seat has touched it. **§13:**
public repo, read in place; **aggregate statistics and mechanism extracted, no formula or code copied
into this repo** — an unlicensed artifact is mineable as *text* and not reproducible as *content*.
**CLAIMED-IS-NOT-VERIFIED:** the README is an advertisement for paid tutoring and every performance
number is the author's own, unverified, on US equities. **What is measured below are properties of
the FILE, which I computed myself, not claims about the market.**

The repo's premise is the desk's own independence problem stated in the platform's terms: *50 alphas
that can pass the mutual correlation test if submitted together.* The desk's version is L1.18 (maximum
INDEPENDENT compounding sources) against a cross-section measured at **N_eff 1.54 raw / 29
market-neutral**. So: how does a working practitioner actually manufacture 50 mutually-uncorrelated
signals?

**MEASURED OVER ALL 50 ROWS:**

| quantity | measurement |
|---|---|
| distinct **data fields** | **49** (for 50 alphas; max reuse 3) |
| distinct **operator tokens** | **8** — `rank` 30, `ts_mean` 18, `ts_zscore` 2, `sum`/`delay`/`group_rank`/`ts_av_diff`/`ts_corr` 1 each |
| expression depth (paren count) | min 1, **median 1**, max 15 |
| **single-operator alphas** | **48 / 50** |
| neutralization | Subindustry 19, Market 17, Sector 8, Industry 4, **None 2** — i.e. **96% neutralized** |
| universe | TOP200 27, TOP1000 12, TOP500 9, TOP3000 2 |
| turnover | median **0.0205** (≈2%), max 0.212 |
| decay | median 10, mean 19.6, max 95 |

**THE MECHANISM: 48 of 50 are one operator applied to one field.** `rank(mdf_pva)`,
`-rank(mdf_ite_q)`, `-rank(fnd6_newa1v1300_epspi)`. Diversity of *expression* contributes essentially
nothing to passing the correlation test; **diversity of underlying field contributes everything.**
Eight operators sufficed for fifty independent signals.

**WHY THIS MATTERS HERE, AND IT IS A RE-RANKING OF THIS SEAT'S OWN BRIEF.** This organ exists partly
to hunt operators, and the strongest evidence it has yet produced says **operators are the low-yield
axis and fields are the high-yield one.** It independently corroborates the desk's single most
expensive research lesson from a completely different market, institution and asset class: the
2026-08-01 campaign ran **129 mechanisms, all price-derived, all directional, and all 129 failed** at
max OOS Sharpe 0.100. Another *transform* of price cannot manufacture an independent bet — only
another *source* can. **The desk's alpha-diversity law is a DATA-ACQUISITION problem wearing a
modelling costume**, and that is now measured from outside rather than argued from inside.

**THE THRESHOLD-HUGGING RESULT, and it survives the source being untrustworthy.** Sharpe: **min 1.2500,
median 1.2500, max 1.2900**; 26 of 50 sit at *exactly* 1.25; **70% within [1.24, 1.26]; 100% below
1.30.** The platform's stated submission target — already in this repo as
`BRAIN_SHARPE_TARGET = 1.25` — is the **floor, the median and very nearly the maximum** of the
accepted population. That is the signature of a search that stops the instant the bar is cleared.
**And the finding does not depend on the numbers being real:** if they are honest, the accepted
population is dominated by marginal candidates; if they are fabricated, the author fabricated them
*to hug the threshold*, which reveals the same selection norm. Either way it is direct external
evidence for the desk's own law that **throughput must come from screening more, never from passing
more** — and a live demonstration of why L1.6 forbids importing that 1.25 as a gate (OP-083).

**CRYPTO ANALOGUE / WHAT IT WOULD NEED.** The construction that ports is *one cheap transform over
many orthogonal fields*, not *many clever transforms over price*. The desk's binding input is
unchanged and this sharpens it: 96% of these alphas neutralize against a **grouping** (subindustry
most often — the *finest* available), and `data/crypto_grouping_map.json` exists with its consumer
wiring still owed at **R0437**. Field-count, not operator-count, is the axis to grow —
routed to `data_axis_watchlist.md`.

---

## OP-085 — COMPETITION-PODIUM LADDER (JP proven; adapt per region) (litminer run 8, 2026-08-18)

**Operator:** for any data-vendor or exchange-run ML competition, the runnable alpha layer is not
the leaderboard — it is the POST-COMPETITION WRITEUP with a repo. Ladder: (1) find the competition's
official tutorial/rules repo (org GitHub); (2) search the region's writeup platforms for podium
language + the competition name — JP: `"{comp}" 優勝 OR 準優勝 site:zenn.dev OR site:note.com OR
site:qiita.com`; KR: `"{comp}" 우승 OR 입상 site:velog.io OR site:tistory.com`; CN: `"{comp}" 冠军
OR 亚军 site:zhihu.com`; (3) the writeup names the author's GitHub — the solution repo carries the
feature set + target construction the leaderboard never shows; (4) read the TUTORIAL layer and the
WINNER layer separately: discipline (purging, eval design) lives in the tutorial; alpha claims live
in the winner code, and neither implies the other (measured on J-Quants: JPX tutorial teaches
1-month purge buffers; the runner-up's public predictor has no CV at all).

**Proven yield (first application):** J-Quants Fundamentals Challenge → UKI000/JQuants-Forum
(107★) → full runner-up predictor source: path-extreme `label_high_20/low_20` targets +
guidance-vs-realized `m_*` surprise features (improvement_inbox 2026-08-18). Cost: 2 fetches.
**Caveat that travels:** competition writeup PDFs on GitHub must NOT be read through WebFetch
summarisation (OP-057 fabrication class) — read the `.py` via raw.githubusercontent instead; the
code outranks the PDF anyway.

## OP-086 — WAYBACK CDX CANONICALIZES QUERY PARAMS ALPHABETICALLY: PAGINATION PROBES NEED `filter=`, NEVER A TRAILING-PARAM PREFIX (prospector, 2026-08-18)

**THE TRAP, measured this run:** a thread's pagination URLs (`Show Post.aspx?PostIDKey=112425&PageIndex=2`)
canonicalize in the CDX index with params SORTED — urlkey = `...?pageindex=2&postidkey=112425`. A
prefix probe on `...?PostIDKey=112425&*` therefore returns **[] even when every page is archived**
(it did: 6/6 pages existed). A clean [] from a prefix probe on a parameterised URL is a FALSE
EXHAUSTION — the third false-null class of this genre (after the JS-shell 200 and the robots-only
pass).

**THE OPERATOR:** probe pagination with a server-side regex filter over the path prefix instead:
`cdx?url=<host>%2F<path>&matchType=prefix&filter=urlkey:.*<idparam>=<id>.*&collapse=urlkey`
— one call returns every archived page of the thread regardless of param order. Confirmed on two
NP threads (112425: 7 urlkeys; 4851: 27 of 45 pages, page-list printed in one pass).

**PAIRED CAVEAT (capture-lattice honesty):** deep pages are captured in DIFFERENT YEARS, so a
thread's final state can be partially lost even with "all pages archived" — 112425's page-3 final
state predates its fill (sole 2011-01 capture). Claim EXHAUSTED against the ARCHIVED lattice and
name the lost interval; never claim the thread's true final state.

**ADAPTATION HOOKS (§16):** any forum with `?topic=<id>&page=<n>` URL grammar (Discuz `tid=`
pages, phpBB `start=`, vBulletin `page=`) hits the same alphabetization; the filter form ports
verbatim. Regional seats: apply when era-mining dead boards via CDX (KR Ppomppu era-seek already
pages by URL param — same trap class).

## OP-087 — THE VENUE'S OWN CODE-HOSTING ORG IS A LEGITIMACY INSTRUMENT: READ `license.spdx_id` ACROSS ITS OFFICIAL CLIENTS BEFORE RULING ON AN AMBIGUOUS DATA-USE TEXT (EN frontier miner s-I, 2026-08-19)
class: §13 legitimacy / evidence acquisition — the conduct axis the document read misses
origin: bitbank card 28 (footer-disclaimer scope question, open since 08-12, decided in one org listing)
validated-gain: one GitHub API call (`/orgs/{org}/repos`, read `license.spdx_id` + repo NAMES)
decided a licence question two document-reads could not, in BOTH directions the same day:
bitbank → LEGITIMATE (MIT-licensed official Public+Private API clients, `sample-market-making-bot`
×2, an official Discord botter-community repo, an official historical-data distribution repo — a
venue soliciting commercial programmatic use cannot coherently ban it by footer); GMO → the
ABSENCE of any org/SDK/grant-language became half the RESTRICTED ruling (clause + silence).
HOW: (1) hit `/orgs/{candidates}/repos?per_page=100` for the venue's plausible org names; (2)
read three fields — `license.spdx_id` (MIT/Apache on an official API client = venue-granted
commercial-use code for that API), repo NAMES (`sample-*-bot`, `*-mcp-server`, community repos =
solicitation), and descriptions (which subdomain/API each covers); (3) weigh CODE licences as
conduct evidence about the API's intended use — they do NOT override an explicit DATA-reuse
clause (the GMO boundary: an MIT client cannot grant what Art.14(15) reserves); (4) the org
listing also surfaces DATA AXES the marketing site never mentions (bitbank's L2 orderbook S3
docs repo — card 34 — was found exactly this way). Per-region adaptation: JP venues cluster on
GitHub (bitbankinc, bitFlyer's org); CN venues on Gitee mirrors — same read, `license` field in
the Gitee API; KR venues often publish under team accounts, search `{venue} official github` +
the API docs' footer links rather than guessing org slugs.   [active]


## OP-088 — A REPLY-TO-VIEW GATE MAKES AN ARCHIVED THREAD'S PAYLOAD STRUCTURALLY UNARCHIVED: THE GUEST VIEW IS THE ADVERTISEMENT, NOT THE CONTENT (CN frontier miner s9, 2026-08-19)

class: false-null family, FIFTH member (OP-033 encoding / OP-034 compression / OP-068 SPA shell /
OP-069 transport / OP-088 application-layer content gate) — and unlike the other four, this page
is genuine, complete, intact and correctly decoded. The lie is one layer deeper: the payload was
never SERVED to the crawler, so no amount of fetch hygiene recovers it.

origin: coinsbbs.com thread-120 (the btc-e 搬砖 tutorial, 2013-12) — 8 pages / 70 posts fetched
intact, decoded clean, mined to full depth, and the tutorial itself was in NONE of them. Discuz
回复可见 (reply-to-view) renders to a guest — and Wayback crawls as a guest — only the intro plus
"游客，如果您要查看本帖隐藏内容请 回复". The stronger variant, 阅读权限/member-tier (coinsbbs
thread-183, "另外一个不被人所知的搬砖站点"), returns a bare Discuz 提示信息 permission page: even
the intro is absent, so the advertised venue's NAME is unrecoverable from the archive.

THE TELLS, all cheap, all high-precision: (1) the literal markers 回复可见 / 隐藏内容 / 提示信息;
(2) the reply signature — a long run of contentless one-liners (谢谢/学习/看看/顶) at high
velocity; those are UNLOCK ATTEMPTS, not discussion, and their count is a DEMAND METER for the
gated payload (70 in 9 days here, during the ban week); (3) a tutorial-promising title over a
body far too short to be one.

WHAT REMAINS MINEABLE — it inverts: the metadata layer survives perfectly. Who sought the edge,
when, how many, how fast (the crowding clock), what the era considered secret enough to gate.
Two payload-recovery routes, both legitimacy-clean: (a) CROSS-POSTS — the same author advertising
on a sibling venue pastes the intro + pointer ungated; 8btc thread-1983 is how thread-120 was
found at all, and its hotlinked coinsbbs screenshots survive inside the 8btc capture. Hunt the
title string on sibling venues before declaring a payload lost. (b) the /archiver/ layer — some
old Discuz archiver builds rendered hide-blocks to guests; coinsbbs's archiver THREAD pages were
never captured (index only, 1.7KB), so for that venue the probe is UNTESTED, not failed — record
which. What is NEVER done: registering or replying on a live descendant, or any route around an
access control — the gate is a §13 boundary in every language, and the gate being DEAD does not
change whose content it is.

DISCOVERY INVERSION, the reusable half: the gate markers are SEARCH KEYS. Query a forum's index
or site-search for 回复可见 + 搬砖/教程/策略 and you enumerate precisely the threads the era's
practitioners thought worth gating — a ranked shortlist of where the edges were, which is the
right place to START cross-post hunts. Per-region adaptations (charter §16): KR boards gate with
비밀글 and 등업 (level-up) walls; RU forums with [hide]/спасибо-unlock plugins (forum.bits.media
lineage); EN-era vBulletin/XenForo with "like/thanks to see" plugins. Same tells, same metadata
inversion, same §13 line everywhere.

## OP-089 — A FAILED VIDEO FETCH IS FOUR DIFFERENT FACTS: TRIAGE PRIVATE / IP-WALL / DEAD ROUTE / DISABLED ENDPOINT BEFORE LOGGING ANYTHING (RU frontier miner s3, 2026-08-19)

The wrapper (scripts/fetch_video_transcript.py) prints ONE error for all four states — and only
one of the four is the class the paid-unlock gate (GAP #26) exists for. Query a live relay
directly (`api.piped.private.coffee/streams/<id>`, per the BR-s3 finding) and read the RELAYED
exception, not the wrapper's summary:
  1. `PrivateContentException` = content WITHDRAWN by the author. UNBUYABLE — a paid proxy cannot
     unlock a private video, so this must NEVER be logged to video_locked_log (it would corrupt
     the purchase-evidence gate with rows no purchase can satisfy). It IS its own finding:
     back-catalog privatization measures a corpus rotating free content into a paid funnel —
     mine such channels PROMPTLY on discovery, the back-catalog is unstable.
  2. `SignInConfirmNotBotException` = per-IP anonymous-access wall. THE locked class; loggable.
  3. A hollow 200 whose BODY is a service-shutdown notice ("Piped has shutdown", 18 bytes,
     api.piped.projectsegfau.lt) = the ROUTE FAMILY is dying, not the video. 6th member of the
     false-null family (OP-033 encoding / OP-034 compression / OP-068 SPA shell / OP-069
     transport / OP-088 content gate / OP-089 route obituary) — parse the body for shutdown
     markers before concluding anything about the CONTENT.
  4. An Invidious instance with content endpoints disabled still serves the caption LIST
     (`/api/v1/captions/<id>` on inv.nadeko.net) = a free EXISTENCE PROOF that a transcript
     track exists. Cite it in the locked-log row: the purchase gate should know the thing it
     would buy provably exists.
MEASURED 2026-08-19 (@crypto_maniacdt corpus): 3 videos → 2 PRIVATE + 1 IP-walled with a PROVEN
RU auto-caption track; 10 routes tried (1 live relay, 2× 502, 2× 301, 2 DNS-dead, 1 shutdown
notice, 1 content-disabled, 1 401). Per-region adaptations (charter §16): Bilibili 私享/充电专属
= private/member-gated (triage the same way before logging); VK Video and Rutube walls are
region-reversed (open from RU IPs, walled from abroad) so a wall verdict must name the PROBE
ORIGIN; JP/KR: ニコニコ有料/멤버십 gates are PAID classes — loggable, they are what GAP #26 buys.

## OP-090 — A REQUEST PARAMETER CARRIES ITS OWN TIMEZONE CLAIM, SEPARATE FROM THE RESPONSE FIELD — AND ONLY THE RESPONSE FIELD IS EVER AUDITED (KR frontier miner s3, 2026-08-13; landed 2026-08-19)   [active]

_ID PROVENANCE: minted as "OP-072" on the unmerged branch `claude/kr-miner-s3-20260813` (2026-08-13);
the JP s4 seat took OP-072 (LLM-contamination) the same day on the live branch, so this operator was
RENUMBERED to OP-090 at landing (KR s4, 2026-08-19). Any reference to an "OP-072" about request
timezones — including the KR s3 session memory — means THIS operator. The collision rule this
minted: an operator id claimed on a side branch is not claimed; re-read the live library's max id
at LANDING time and renumber the incoming operator plus every reference inside the same landing
commit._

**MEASURED 2026-08-13 (KR seat s3), Upbit vs Bithumb, both keyless, both "Upbit-schema-compatible":**
the `to=` pagination parameter is interpreted in **UTC by Upbit and in KST by Bithumb**. Ask both for
`to=2024-01-15T12:00:00` and Upbit returns the bar ending `2024-01-15T11:59:00Z` while Bithumb returns
`2024-01-15T02:59:00Z` — **exactly 9h apart**. Add 9h to the Bithumb request and the two align **to the
minute** (verified on 2024-01-15, 2020-03-13, 2018-01-11; the 4th test date failed for an unrelated
reason — it landed inside a real venue outage, which is itself the finding below).

**WHY EVERY EXISTING CLOCK CHECK IS BLIND TO THIS.** L1.46 made the desk declare the stamping clock of
every record it *receives*. This is the clock of the request it *sends*, and the two are independent
claims. The response here is **honest**: `candle_date_time_utc` really is UTC on both venues, so a
provenance checker reading returned rows sees nothing wrong. The rows are simply **not the window you
asked for** — no error, no gap, no warning, no anomalous value. A paginating backfill written against
one venue and pointed at the other walks a 9h-shifted window on *every* call and compounds it across
the entire history, and the output passes every schema, freshness and provenance gate the desk owns.

**THE RULE, GENERAL:** for any historical endpoint, the timezone of the *request* is a separate
measurement from the timezone of the *response*, and it is verified the same way — **round-trip it**.
Ask for a known instant, read back the stamp you got, and check they agree. One call. Do this before
any backfill loop is pointed at a second venue, however identical the schema looks. **Schema
compatibility is precisely what makes this dangerous:** it is the reason nobody re-checks.

**SEPARATE FROM, AND NOT COVERED BY, THE EXISTING KILL.** `bithumb_kr_premium_lookahead`
(docs/graveyard.md) records that Bithumb's *daily bar boundary* is KST-day-open. That is a fact about
the **bar**; this is a fact about the **query**. Both are live, they are different, and fixing one
leaves the other. Re-derived independently this session before the graveyard was checked — recorded
because the novelty gate catching a re-derivation is the gate working, not a finding.

**KR ADAPTATION / WHAT IT UNBLOCKS.** The graveyard's framing reads as *"this venue is hazardous"*.
The measurement says *"this ENDPOINT is hazardous and the hazard is removable"*: **1-minute bars are
honest UTC on both venues and align exactly once the +9h request offset is applied**, so the intra-KR
(Upbit−Bithumb) spread — the control WS-011 asked for, and the one construction where the cross-border
capital-control term differences out — is cleanly constructible after all. That is the L1.25a
distinction in its data-layer form: a blocked ROUTE is not a dead CAPABILITY.

## OP-091 — AN ARCHIVE YOU OWN IS ONLY AS COMPLETE AS ITS COLLECTOR'S FILTER, AND THE FILTER IS INVISIBLE IN THE ROWS: SCAN THE SOURCE'S CATEGORY ENUM BEFORE TRUSTING ANY IN-REPO CORPUS AS "THE RECORD" (KR frontier miner s4, 2026-08-19)   [active]

**7th member of the false-null family** (OP-033 encoding / OP-034 compression / OP-068 SPA shell /
OP-069 transport / OP-088 content gate / OP-089 route obituary / **OP-091 collection scope**) — and
unlike the other six, this one lives INSIDE the desk: the ground was never fetched wrong, it was
never fetched at all, and nothing in the artifact says so.

**MEASURED (this run):** s3's enumeration plan said "count KR rail transitions from
`data/upbit_trade_announcements.jsonl`". Scanned: **0 bank hits in 737 rows.** Not because Upbit
never announced bank events — because the file is `category=trade` ONLY (one `Counter()` call shows
it) while the SOURCE serves five+ categories: `notice` (776 rows — every bank/rail/real-name event),
`event` (312), `all` (5,736 ⇒ ~3,900 rows in classes nobody has enumerated). The premise was false
at COLLECTION time, a year before the query.

**WHY EVERY EXISTING CHECK IS BLIND:** a category-filtered lake passes every fence the desk owns —
rows well-formed, dates continuous, freshness green, no 4xx anywhere — because the filter ran at the
producer and left no mark in the product. WS-005's shape (absence resolving to a clean verdict) at
the collection layer. The zero-hit scan is byte-identical to "the venue never announced bank
events", and only the category enum distinguishes them.

**THE RULE:** before using any in-repo corpus as "the record of X", (1) find its producer and read
the REQUEST it makes — every filter parameter (category/type/tag/lang/date) is a scope claim about
the lake; (2) probe the source's enum ONCE (cheap: fire the invalid value, read the error; fire
candidate values, read total_count); (3) if the lake is a subset, say which subset IN THE QUERY
RESULT — "0 hits in the trade category" and "0 hits at Upbit" are different findings. Per-region
adaptation is direct: Discuz `fid` boards, Naver cafe menus, Telegram topic threads, GitHub
issue-vs-discussion tabs are all the same enum-vs-lake trap — a mined board is not a mined forum.

---

## OP-092 — A JAMSTACK SITE SHIPS ITS CMS AS STATIC JSON: THE DATA LAYER DEFEATS THE SPA-SHELL FALSE NULL WITHOUT TOUCHING ANY ACCESS CONTROL (AR frontier miner s3, 2026-08-19)   [active]
class: access / extraction — the structured escape hatch for the "200 + JS shell" false-null class
origin: VARA (vara.ae, Gatsby 4 over Umbraco); full regulatory corpus extracted in 6 requests
validated-gain: the notice/circular lists render client-side (curl on the HTML sees banner text
only), yet the ENTIRE corpus — 21 circulars + 41 notice bodies + 37 enforcement rows + 77-entity
register with per-entity licence scope — sits in typed JSON at documented static paths. What a
browser-less session would have graded "thin/WALLED" is the region's richest institutional ground.

**THE MECHANISM.** Static-site generators pre-serialize every CMS query at build time and ship it
beside the HTML. The SPA shell fetches these SAME files — so reading them routes around NOTHING
(§13 unchanged: same public content, same server, no auth, no gate; VARA additionally serves
`disableSearchEngineIndexing:false` in the payload itself).
| framework | data layer path | how to enumerate |
|---|---|---|
| Gatsby | `/page-data/<path>/page-data.json` | mirror the page URL; per-page `staticQueryHashes[]` → `/page-data/sq/d/<hash>.json` (site-wide lists live HERE, not in the page) |
| Next.js | `/_next/data/<buildId>/<path>.json` | `buildId` from `__NEXT_DATA__` in any page's HTML |
| Nuxt | `/_payload.json` (3.x) or inline `__NUXT__` | append `/_payload.json` to the page URL |

**THE TWO NON-OBVIOUS HALVES, measured on vara.ae:**
1. **The list you want is usually in the STATIC QUERY, not the page.** `/en/regulations/regulatory-notices/`
   page-data carries only the banner; the 41 notice bodies hang off `staticQueryHashes` → `sq/d/2952670578.json`.
   A digger who stops at the page-data concludes "empty list" — the same false null one level deeper.
2. **The build ships EVERY locale's queries together.** The EN page's hashes resolved
   `allVaraNoticeAr`/`allVaraNewsAr` alongside the EN sets — the bilingual corpus arrives in one
   pull, and locale-diffing (which items exist in AR only) becomes a one-line set operation.

**INSTRUMENT NOTES (access-map hygiene):** on this host `HEAD /robots.txt` → 404 HTML while
`GET` → 200 robots-format (Cloudflare/JAMstack edge behaviour): **grade policy from GET, never
HEAD**. And a Gatsby 404 page is itself a 200-shaped shell (111KB of HTML on `/sitemap.xml` with
status 404) — read the status code, not the body size.

**PER-REGION ADAPTATION:** regulator/exchange/foundation sites region-wide are increasingly
JAMstack (GCC government portals conspicuously so). Before grading any modern institutional site
THIN or WALLED from curl-rendered HTML: view source for `gatsby`/`__NEXT_DATA__`/`__NUXT__`
markers, then probe the data layer. Pairs with OP-091 (the payload names its own collection scope:
`contentTypeAlias`, query names like `allVaraNotice` are the site's own enum) and OP-074 (the data
layer answers "what exists" independently of robots' "may I").

---

## OP-093 — THE VECTOR/REDUCE LAYER IS A DATA SHAPE, NOT AN OPERATOR SET — AND THE DESK ALREADY OWNS A RICHER VECTOR THAN THE PLATFORM DOES (BRAIN hunter s4, 2026-08-19)   [active]
class: feature construction / data shape — the transferable half of an equities platform
origin: `zhutoutoutousan/worldquant-miner` @ `master`, `generation_two/constants/operatorRAW.json`
(**Apache-2.0**, 724★, 192 forks, pushed 2026-02-22). Catalogue artifact:
`data/brain_operator_catalogue.json`.

**THIS CLOSES S3'S NAMED LIMITATION.** s3 mined `rocky-d/wqb` and recorded honestly that the client
gives *"the namespace and exact API paths, never the value sets"* — every enum aliased to `Any`.
`operatorRAW.json` **is** the value set: **98 operators** with name, category, scope, level and
semantics. §13 held: no credential held/sought/used, no call to `api.worldquantbrain.com`.

**MEASURED DESK COVERAGE** (a *definition* search — `^\s*def <name>\b` over `libs/` — not a mention
search; 26 operators whose names are python builtins or generic verbs are counted NEITHER way):

| category | total | defined in `libs/` | absent |
|---|---|---|---|
| **Reduce** | 14 | **0** | **14** |
| **Vector** | 4 | **0** | **4** |
| Time Series | 29 | 1 | 28 |
| **Group** | 10 | 2 | **8** |
| Cross Sectional | 8 | 1 | 3 |
| Special | 3 | 0 | 2 |
| **TOTAL** | **98** | **5** | **67** |

The five: `ts_backfill`, `vector_neut`, `trade_when`, `group_zscore`, `group_rank`.

### THE FIND IS NOT THE 67 MISSING OPERATORS. IT IS WHAT 18 OF THEM IMPLY.

`vec_*` (4) and `reduce_*` (14) are **18 operators that only make sense if a field can hold a VECTOR
per instrument per day.** The platform's own worked example is explicit: *input = vector of values of
1 instrument in a day, `(2, 3, 5, 6, 3, 8, 10)`; `vec_sum` → 37.* `reduce_*` is the general form —
it takes a `(D × N)` or `(D × N × N)` matrix and collapses the **last** dimension.

So the platform ships a **two-stage feature pipeline**: `raw vector field → reduce → scalar → the
other 80 operators`. **The desk's pipeline has no first stage at all.** It begins at the scalar.

**This is why it matters more here than there.** An equity vector field is thin — analyst estimates,
a day's news items. The desk's per-instrument-day vectors are *dense and proprietary*:

| desk-owned vector (verified on disk) | size | what one element is |
|---|---|---|
| `data/geckoterminal_trades.jsonl` | 153MB, **322,187 rows** | one DEX trade: signed `kind` buy/sell, `volume_usd`, **`tx_from` (wallet)**, `t_venue`+`t` dual clock |
| `data/bybit_l2_samples` | 149MB | one order-book level |
| `data/upbit_snapshot` | 412MB | one venue snapshot |

**MEASURED ABSENCE, stated as a fact rather than an impression:** `grep -rEn "skew|kurtosis"` over
`libs/features/` and `libs/alpha_factory/` returns **nothing**. The desk computes no distributional
moment of any intraday vector, anywhere.

### THE THREE MANDATED QUESTIONS

**1. WHAT DOES IT COMPUTE?** `reduce_<stat>(input, threshold=0)` applies `<stat>` along the last
axis, returning NaN when valid-value count falls below `threshold` — the missing-data floor is a
*first-class parameter*, not an afterthought. Variants worth naming: `reduce_percentage(x, p)`
(p-quantile, median at 0.5), `reduce_count(x, threshold)` (count above a cut), `reduce_ir`,
`reduce_skewness`, `reduce_kurtosis`, `reduce_range`, `reduce_choose(x, nth)`.

**2. CRYPTO ANALOGUE — and it is strictly richer than the equity original.** Over one pool-day of
the DEX tape: `reduce_skewness(volume_usd)` = whale-vs-retail size mix; `reduce_count(volume_usd, k)`
= large-trade count; `reduce_percentage(volume_usd, 0.5)` = median trade size (a size distribution is
*not* recoverable from a daily volume total — that is precisely the information the scalar collapse
destroys); signed variants keyed on `kind` give buy/sell pressure asymmetry. And `tx_from` supports a
reduction **equities have no analogue for at all**: unique-wallet count, repeat-wallet concentration,
and new-vs-returning wallet mix per pool-day. Add these to
`libs/research/evidence_tier.translate_to_crypto()` when the frozen seat lifts.

**3. WHAT DATA WOULD IT NEED THAT THE DESK LACKS?** For the *DEX* tape — nothing. It is on disk,
paid for, and (per R0637) **has no analytical reader at all**. For a Binance-perp equivalent the desk
would need the per-symbol aggTrade tape, which it does not currently retain.

### THE SHARPEST SINGLE OPERATOR ON THE GROUND: `self_corr`

`self_corr(x)` takes `(D × N)` with lookback `K` and returns `(D × N × N)` — every pairwise rolling
correlation — and then `reduce_*` collapses the last axis. So `reduce_avg(self_corr(returns))` is
**a per-symbol, per-day scalar: how correlated is this asset to the rest of the universe right now.**

That is the desk's own breadth problem, expressed as a *feature* rather than a *diagnostic*:

- `libs/research/cohort_independence.measure()` returns ONE `Independence` object with scalar
  `mean_corr` / `n_eff` for a whole cohort. Breadth is a **global number, computed after the fact.**
- `reports/cross_section_breadth.json` records the desk's cost of that: N_eff **1.54 raw**, 29
  market-neutral. One number for the whole book.
- `data/crypto_grouping_map.json` `corr_cluster` is a **static** assignment built once (2026-08-11,
  296 symbols). Crypto correlation structure is regime-dependent; a static cluster map is a known
  weakness, and `self_corr` is exactly the operator that makes it time-varying.

**Two uses, and the second is the one the desk is blocked on:** (a) a *conditioning variable* — size
into names that are currently decorrelated from the book; (b) a **dynamic grouping input**, which is
the blocking input this organ has carried since 2026-08-07 (`group_rank`/`group_zscore` REFUSE
without a map; wiring row **R0437** is OVERDUE, due 2026-08-18).

**HONEST LIMITATION.** All of this is **mined ore, not evidence** — nothing here has been run on desk
data. `reduce_*` on the DEX tape is a *feature family*, and a feature family is a DSR-counted trial
set, not an edge. Nothing in this entry carries promotion authority. And the platform's own
submission bar (IS Sharpe ≥ 1.25) is recorded as **a fact about their process, never a gate for
ours** — L1.6, unchanged.

---

## OP-094 — INFORMATION-DRIVEN BARS: THE SAMPLING CLOCK IS A FREE AXIS THE DESK HAS RE-DISCOVERED THREE TIMES AND NEVER BUILT (BRAIN hunter s4, 2026-08-19)   [active]
class: sampling / data construction — a clock change, not a signal
origin: `worldquant-miner` `paper/chapters/crypto-trading-strategies.tex` → **its citation**, which
is the real find (recursive-expansion mandate: repo → author → cited paper → primary source).

**PROVENANCE MATTERS HERE AND THE CHAPTER'S OWN NUMBERS ARE SECOND-HAND.** The .tex chapter presents
a comparison table (time bars Sharpe 0.85 → CUSUM 1.28) that is **`\cite{gradzki2025}` — attributed,
not measured by that author.** Its unattributed claims ("cross-exchange arbitrage provides consistent
2–5% monthly returns") carry no evidence at all. **Take the citation, drop the chapter's numbers.**

**THE PRIMARY SOURCE, verified via Crossref (`api.crossref.org`, not the publisher wall):**
Grądzki, Wójcik & Lessmann, *"Algorithmic crypto trading using information-driven bars, triple
barrier labeling and deep learning"*, **Financial Innovation 11:136 (2025-12-15)**,
`10.1186/s40854-025-00866-w`. **Licence: CC BY 4.0** (Crossref reports it for both `tdm` and `vor`
versions) — **fully open access and legally minable.** Abstract confirms: tick-level BTC/ETH,
**Jan 2018 → Jun 2023**; CUSUM-filtered sampling + Triple Barrier labeling beats time bars +
next-bar prediction **after transaction costs**; Transformer variants (vanilla encoder, FEDformer,
Autoformer) evaluated against classical ML — a *negative-results* layer worth mining separately.

**ACCESS NOTE (§13, and a reusable instrument fact):** `doi.org` → `link.springer.com` →
`idp.springer.com/authorize` (303), and the SpringerOpen journal host `jfin-swufe.springeropen.com`
**301s back into the same loop**. That is a **cookie/consent redirect on an article that is CC BY**,
not a paywall — so the correct move is a metadata/OA route (Crossref worked in one call), never
credentialed egress. Do not grade a CC-BY article WALLED from a redirect loop.

**THE DESK-SIDE FIND, which is bigger than the paper.** `grep` over `libs/` and `scripts/`:
**zero** implementations of CUSUM, dollar bars, volume bars, imbalance bars, or any changepoint
detector. Triple Barrier, by contrast, **already exists** (`libs/features/labels.py`) — so the desk
built the labeling half and never the sampling half. The sampling gap has been independently
re-reported **three times**:
- `docs/research/adoption_queue.md:13` — queued, trigger never fired
- `capability_hunt/20260805_s0_proposals.md:39` — *"zero changepoint detectors of any kind"*
- `capability_hunt/20260801_s3_proposals.md:48` — *"`tests/validation/conftest.py:40` declares the
  decay-detection method as CUSUM on live IC … a test fixture documenting a detector never built"*

**WHY IT NEVER CLOSED IS A STRUCTURAL DEFECT, NOT A PRIORITISATION CALL — see R0638.** The adoption
queue gates dollar/volume bars on *"a bar-sampled (non-time-bar) alpha enters the pipeline"*, under a
header that rules "build nothing until the trigger fires". **A bar-sampled alpha cannot exist before
the bar sampler does.** The precondition is unreachable by construction — the exclusion-cycle shape
L1.45 names ("ask of any exclusion: what is the path back?"). There is none.

**CONVERGENCE WITH A LAW THE DESK ALREADY OWNS.** L1.46 established that a *configured constant is
not evidence of a cadence*, and R0117's sampling-phase aliasing concern is the same axis one layer
down. The desk has a **law** about sampling clocks and an **adoption queue structurally unable to
adopt the sampling-clock fix**. Information-driven bars are also the concrete form of L1.28c's
"event-driven firing" — the named way past an information-arrival ceiling.

**CLAIMED IS NOT VERIFIED:** the 1.28-vs-0.85 comparison is *their* measurement on BTC/ETH tick data,
not ours. It is a hypothesis with an unusually good provenance (peer-reviewed, CC BY, costs
included), not a result this desk may cite as its own.

### OP-072 a CAPABILITY verdict needs a repeat and a control — and YouTube's bot gate is a FULL-SIZE HTTP 200 hollow shell   [active]

origin: RU frontier miner s3 (2026-08-13)   validated-gain: re-opened a ground the whole fleet had
been told was closed, then correctly closed it again for a *different* reason with the evidence a
purchase decision needs.

**FIFTH MEMBER of the false-null family** — OP-033 (encoding) / OP-034 (compression) / OP-068 (SPA
shell) / OP-069 (transport) / **OP-072 (anti-bot gate)**. All five make live ground read as
exhausted. This one is the nastiest of the five because *the body is the right size*.

**PART 1 — THE CAPABILITY VERDICT.** On 2026-08-12 a seat probed the video fetcher's four hardcoded
Piped proxies, measured 4/4 down, and wrote a **permanent desk-wide verdict** ("the fetcher is
INERT for YouTube") into memory and a ledger row. **Refuted on the first call the next day**: the
*first* proxy in the rotation returned a full transcript, twice, three minutes apart.

> A capability graded from a **single-instant probe of N endpoints** is a measurement with no
> repeat. Rotating public infrastructure is *expected* to have members down; the correct question
> is never "are all N up?" but **"does the ROTATION succeed?"** — which is what the tool already
> does and what the probe bypassed.

**RE-PROBE BEFORE INHERITING A CAPABILITY VERDICT.** A dated "X is dead" in seat memory is a
hypothesis with a timestamp, not a fact — and it is the *expensive* kind of wrong, because unlike a
false find it produces no artifact anyone will ever audit. It just quietly removes a ground.

**PART 2 — WHAT THE WALL ACTUALLY IS, AND WHY THE FIRST DIAGNOSIS INVERTED IT.** The 08-12 row
argued: `www.youtube.com` returns 200 from this box ⇒ the source is not walled ⇒ the desk-side tool
is dead. **The 200 is a hollow shell.** Measured from one box, one minute, one UA, one route:

| video | bytes | `captionTracks` | `LOGIN_REQUIRED` | `<title>` |
|---|---|---|---|---|
| `dQw4w9WgXcQ` (1.6B views) | 1,312,898 | **yes** | no | full |
| `VseWNnQmmy0` (RU algo, cold) | 1,265,891 | no | **yes** | **empty** |
| `eb5ywYlw6E4` (RU algo, cold) | 1,204,592 | no | **yes** | **empty** |

**A blocked body is ~96% the size of a good one.** Status code, byte count, "did it return
something", `len(html) > 0`, even `len(html) > 1_000_000` — every cheap liveness test passes on the
shell. Only **content inspection against a known-good field** separates them.

Proxy side shows the identical split *and adds a third state*: the popular video returns 6 subtitle
tracks; one RU video returns HTTP 500 `SignInConfirmNotBotException ... LOGIN_REQUIRED: "Sign in to
confirm that you're not a bot"`; the other returns **HTTP 200 with `subtitles: []` and an empty
title** — a *hollow success*, which any fetcher reports identically to "this video genuinely has no
captions". That is the desk's most-repeated defect shape (absence resolving to a clean verdict)
arriving from outside.

**THE GATE IS KEYED TO POPULARITY, NOT TO YOUR IP.** Cached/popular videos resolve through the same
egress that is refused for cold ones. **So the capability is INVERTED against the dark-forest
mandate**: video access works where the desk has no edge (popular English content) and fails where
its edge would be (cold, low-view, non-English). Any seat that tests the capability on a video it
picked *because it was easy to find* will measure GREEN and conclude the ground is open.

**THE REFEREE, and it is one extra call:** fetch a **known-good control through the SAME route in
the SAME minute**. Control passes + target fails ⇒ per-record, and the ground may still be
partially open. Control fails too ⇒ your route or your egress. Getting this backwards is OP-069's
lesson (a *different* URL is an invalid control) one level up — at the capability layer instead of
the record layer.

adaptations: **all regions.** The desk's video grounds are RU YouTube, CN Bilibili, JP note/YouTube,
KR YouTube, EN conference talks. Only the *content* check is platform-specific: YouTube =
`captionTracks` present and `<title>` non-empty; Piped = `subtitles` non-empty **and** `title`
non-null (the empty-title tell is what distinguishes a hollow success from a genuinely
caption-less video). Bilibili is untested against this and should not inherit the verdict.

### OP-073 `t.me/s/<channel>` — the keyless public text mirror, and the video→Telegram substitution   [active]

origin: RU frontier miner s3 (2026-08-13)   validated-gain: recovered a readable practitioner
surface from a channel whose video layer is bot-gated (OP-072), and supplied the "why text mirrors
were insufficient" column that makes a `video_locked` row decision-grade instead of anecdotal.

**THE ROUTE.** `https://t.me/s/<channel>` renders a **public** Telegram channel's recent posts as
plain server-side HTML — no auth, no API key, no app, no join. Messages sit in
`class="tgme_widget_message_text"`. Verified 2026-08-13: `t.me/s/crypto_maniacdt` → 26 messages,
101 KB, keyless.

**§13 IS SATISFIED AND THE DISTINCTION IS LOAD-BEARING:** `/s/` is the channel owner's own public
web preview, served to anonymous browsers by design. It is **not** a route around access control —
a channel that is private, invite-only or has disabled the preview returns **0 bytes**, and a
0-byte response is a **HARD STOP, never a prompt to find another way in**. Measured the same run:
`t.me/s/cryptomaniac_products_bt` (the advertised "free 85-page algotrading course") → **0 bytes**.
Note the failure mode is the *opposite* of OP-072's: here absence is honest and unambiguous.

**THE PATTERN WORTH GENERALISING — WHEN THE VIDEO IS LOCKED, FIND THE AUTHOR'S TEXT SURFACE.** A RU
practitioner's output is typically mirrored across **YouTube + Telegram + GitHub + a forum
cross-post** (this author: 5 surfaces, incl. smart-lab and Dzen). Video being gated says nothing
about the other four. **Check them before logging `video_locked`** — the log's "why text mirrors
were insufficient" column is what turns it into purchase evidence, and a row that never checked is
not evidence.

**BUT MIRRORS ARE NOT COPIES, AND THAT IS THE FINDING.** Same author, same week: the **video** layer
carries the funding-arbitrage screener build; the **Telegram** layer carries discretionary
`XAU m5 / SMT` calls; the **GitHub** layer carries event-announcement bots. Three surfaces, three
disjoint content classes. So "the mechanism is mirrored in text" must be **verified per mechanism**,
never assumed from the author having a blog.

adaptations: RU/global = Telegram `t.me/s/`. CN = the author's 公众号 mirror or Gitee README. JP =
note.com/Zenn cross-post. KR = velog/tistory. EN = Substack. **Same two-step shape as OP-039** —
discover the handle on the video/repo page, then read the keyless mirror endpoint.

**ENUMERATION FOOTNOTE (YouTube channels, measured 2026-08-13):** three of four listing routes are
dead from this box — `/channel/<id>/videos` **302s to 0 bytes**, `feeds/videos.xml?channel_id=`
**404s**, and Piped `/channels/tabs` throws a NewPipe `NullPointerException`. What works is **Piped
`/search?q=<terms>&filter=videos`, then filter on `uploaderName`** — a search-shaped route to a
listing-shaped question. Composite: **enumerate via Piped search → transcribe via Piped
`/streams/`** (subject to OP-072).

**METHOD CAVEAT on mechanism-keyword density ranking** (the habr lesson, now fleet-standard): on a
page where the comment container is the **last** block, a naive split leaves the final comment
absorbing the page's sidebar and "read next" chrome. Measured on smart-lab 1335532: the top-ranked
comment scored `density=20` with roughly half its tokens from nav furniture, against `13` for the
genuine best. **Truncate each block at the site's nav marker** (smart-lab: `Читайте на SMART-LAB:`)
before scoring, or the ranker systematically promotes whichever comment is last.

## OP-095 — TRANSFORM THE ARRIVALS, NOT THE EMPTY DAYS: MATCH THE OPERATOR CLOCK TO THE SOURCE CLOCK (BRAIN hunter s5, 2026-08-24)   [active]

**SOURCE:** `zl3311/alpha-mining` public research archive, `POSTMORTEM.md` plus all 28 indexed
`data/knowledge/dead_zones/*.md` analyses (MIT for methodology/author analysis; its `DATA-NOTICE.md`
explicitly withholds reuse authority for submitted formulas and platform-derived field metadata).
Read as text only: no BRAIN credential, API call, formula reuse or third-party execution.
**DERIVES-FROM:** NONE (checked in each dead-zone note; session ids are internal evidence links,
not citations to an outside method). Desk-side convergence is independent: the COT/macro stack
already preserves release/vintage semantics, but the operator library had no general cadence rule.

**WHAT IT COMPUTES / REFUSES.** Before applying a rolling transform, measure the source's genuine
update process. For a field that is flat between discrete releases, do **not** manufacture daily
"observations" and then apply overlapping-window differences, `delta/std`, a fast sign gate, or a
short-vs-long window subtraction. Those transformations mostly measure distance from the last
release and denominator noise. Represent the new information as:

1. the point-in-time release innovation at first availability;
2. an event clock since release; or
3. a slow state held unchanged until the next legitimate update.

This is a search operator, not a universal negative claim. The same window transform can be valid
on a dense price, quote, IV or execution series; the refusal is **field-clock specific**. The source
itself contains the falsifier: multi-horizon transforms remained explicitly untested on dense
series and therefore cannot be graveyarded there.

**FUSION MT5 ANALOGUE — exact and point-in-time.** `translate_to_mt5()` returns no row for the
phrase "update cadence"; that empty result is recorded as a mapping gap, not permission to reuse a
crypto destination. The manual active-venue translation is weekly CFTC COT pressure and scheduled
macro releases mapped to Fusion `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD` (and their cross-pair
descendants). COT's Tuesday reference state becomes observable only at the official Friday release;
a revised macro value is unavailable before its vintage timestamp. Use H1/D1 decisions after
first-seen, and price every candidate with the Fusion contract's observed median spread points ×
tick value plus long/short swap across any held rollover. Never forward-fill a future release into
earlier bars and never count the unchanged days as independent observations.

**SAME-RUN VERDICT.** `[§33: screened]` as methodology, not alpha: repository audit found no new
tradeable hypothesis was created, so no Stage-A trial or forward clock was minted. The public
equity backtests are selection-biased ore and do not establish a Fusion return. Artifact:
`data/brain_hunter_s5_20260824.json`.

---

## OP-096b — CDX ATTACHMENT-CORPUS HARVEST: a dead vBulletin board's file uploads are a minable code corpus (EN miner s-J, 2026-08-25)

**THE OPERATOR.** For any dead/archived vBulletin-era forum, the Wayback CDX index exposes the
board's ATTACHMENT namespace as a flat, filterable file corpus — no thread crawling needed:

    http://web.archive.org/cdx/search/cdx?url=<domain>&matchType=domain
      &filter=original:.*attachments/<subforum-slug>.*&filter=statuscode:200
      &collapse=urlkey&fl=timestamp,original

Demonstrated live on forex-tsd.com (dead pre-MQL5 MT4/MT5 EA community, 2005–2015): the PUBLIC
`attachments/digital-filters/` namespace returns archived `.mq4`/`.mqh` SOURCE FILES with 200s
(Jurik JJMASeries.mqh, jvel1, AMA 2007, DTM 2007, T3 variants) plus posted MT4 equity statements
(`*mtstatement*.htm` — era-authentic BACKTEST-MINER ore, claimed-not-verified). File-ID URL
schemes carry POST DATES in the slug (`100541d1271046538` = attachment 100541, unix 1271046538),
so the corpus is datable without the thread. Thread TEXT lives in parallel under the pre-2013
URL shape `/<subforum>/<id>-<slug>-<page>.html` with `-print` variants (clean text, ~10 posts/pp).
**ROUTE NOTE (this box, measured 2026-08-25): web.archive.org is UNREACHABLE via WebFetch but
fully reachable via curl — use the shell route for Wayback, always.**

**§13 BOUNDARY, encoded as a PATH RULE:** on forex-tsd.com the paid closed-group areas live under
`attachments/advanced-elite/`, `attachments/elite-section/`, `/forum/exclusive-forum/*` — HARD
STOP even though Wayback captured them (mining a paid section via the archive is routing around
access control). The free-registration public subforums (`digital-filters`, `trading-systems/
graduated/*`, `broker-talks`, `indicators-expert-systems`) are in scope. Apply the same
path-partition test to every archived board before mining it.

**PER-REGION ADAPTATIONS (charter §16):** RU — the same vBulletin attachment shape on archived
forex.kbpauk.ru / onix boards; the RU school is the ORIGIN of this corpus (see OP-096c provenance).
CN — Discuz! boards use `attachment.php?aid=` (query-string, needs `matchType=domain` + filter on
`attachment`); JP — 2ch-era boards carry no attachments (text-only; skip the operator, mine dat
mirrors). EN — Steve Hopwood forums / Donna Forex (both dead) publish the same shape; NEXT GROUND.

## OP-096c — RETAIL DSP FILTER FAMILY as unary feature transforms + the ADAPTIVE-LENGTH composition pattern (era-archaeology, Forex-TSD digital-filters 2005–2013)

**WHAT THE ERA BUILT** (public subforum, thread 198 "jurik", 29 archived pages 2007–2009, read
this run): a coherent school of LOW-LAG SMOOTHERS used as feature transforms on FX/gold/index
bars — exactly the MT5 universe. Family: **JMA** (Jurik adaptive MA; phase param −100..+100),
**JRSX** (noise-reduced RSI), **CFB** (composite fractal behavior — a market-state functional
returning an ADAPTIVE LENGTH), **AMA** (Kaufman), **T3** (Tillson), **FATL/SATL/RFTL/RSTL**
(Finware fixed-coefficient spectral FIR filters), **NRTR** (trailing-reverse state). All were
MT4-implementable and traded on exactly Fusion's instruments (EURUSD/GBPUSD/XAUUSD, H1 and
below).

**THE TRANSFERABLE PATTERN (the process, not the formula):** the era separated the SMOOTHER from
the PERIOD-SELECTOR — `adaptive_length = f(market_state)` composed with ANY base operator:
thread-documented construction `JRSX.length = ceil(Lo + norm(CFB) * (Hi − Lo))`. That is a
first-class operator-library pattern: `base_op(series, length=state_fn(series))` — an unary
transform whose window is itself a feature. The desk's operator set has fixed-window transforms;
a state-driven window is the structural upgrade this ground contributes. MT5 translation: apply
to H1 FX/gold features (trend-state estimator drives lookback of momentum/zscore transforms);
price with Fusion spread+swap as always; every (state_fn, base_op, hi, lo) cell is a DSR-counted
trial — the era swept these visually, which is precisely why its curves cannot be trusted.

**PROVENANCE / DERIVES-FROM (recorded so convergence cannot be double-counted, GAP #85):** the EN
Forex-TSD corpus is substantially a TRANSLATION LAYER over the RU MQL school — thread-explicit:
"I translated those mt4 indicators from russian language"; JJMASeries.mqh authored by **Nikolay
Kositsin** (RU; his libraries live on today, public, in the MQL5 codebase); FATL/SATL are Finware
(RU) filters. ANY future EN↔RU "independent convergence" on this family is ONE reading of one
school, not two events.

**FREE FALSIFICATION CONTEXT (era's own debunking layer, harvested):** (1) REPAINT SIGNATURE
spotted by a user in 2007 in the thread's own words — "a 3rd color … can be seen on older data,
but on current data only two colors are seen": an indicator whose HISTORICAL bars differ from its
LIVE bars is repainting, and every visual/era backtest of a repainting construct is invalid. TEST:
record live values, recompute historically, diff. (2) The era's equity evidence is posted MT4
statements on B-book demo/micro accounts, pre-cost — ore, never evidence. `[§33: screened]` as
methodology: no tradeable hypothesis minted this run, no Stage-A trial, no forward clock; the
contribution is the operator pattern + provenance + the two falsifiers, routed here.

## OP-097 — EASTMONEY `push2his` KLINE BY MARKET NAMESPACE: CN-listed non-equity instruments have a keyless daily-history API, and its rate limit masquerades as a DEAD ROUTE (CN frontier miner s12, 2026-08-25)   [active]

**THE ROUTE.** `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=<MKT>.<CODE>&klt=101`
`&fqt=0&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&beg=0&end=20500101`
`&lmt=<N>` with `Referer: https://quote.eastmoney.com/`. Keyless, JSON, daily rows as CSV strings
`date,open,close,high,low,volume,amount,amplitude`. `klt` 102/103 = weekly/monthly (untested).
**THE NAMESPACE IS THE FIND**: `<MKT>` selects an EXCHANGE, and the coverage extends far past
A-shares. VERIFIED this run: **118 = Shanghai Gold Exchange** — `118.AU9999` (Au99.99 spot
benchmark, daily from **2004-01-02**, 5,511 rows, CNY/gram), `118.AUTD` (gold T+D from
2012-06-05). UNVERIFIED leads for the MT5 translation layer (probe with the same recipe): SHFE /
INE / DCE / CZCE / CFFEX market codes would give 沪铜/沪银/SC crude etc. — the 内外盘 ratio legs
for copper/silver/oil CFDs; akshare/efinance source code is the free market-code index.
**THE THROTTLE MASQUERADES AS A DEAD ROUTE (false-null family, OP-069's transport class):** burst
calls are answered with a **TLS drop** — curl `SSL_read: unexpected eof`, urllib
`RemoteDisconnected` — never HTTP 429, and the cooldown persists ≥30min once tripped. Two
correct calls then hard EOFs on every subsequent attempt looks EXACTLY like "the route died";
it is the rate limiter. RECIPE: space calls ≥10-20s, window bulk history via `beg`/`end`
year-chunks, and treat a TLS-layer failure on a route that JUST worked as a cooldown signal —
switch task and return, never re-probe in a loop (each probe may extend the window).
**PER-REGION ADAPTATIONS (charter §16):** CN — as above; the same host also serves guba sentiment
(source_alternatives.py already catalogues it) so one cooldown can starve two collectors: schedule
them apart. KR/JP — Naver/Rakuten finance chart APIs are the analogous quote-page backends; when
one "dies" mid-session, test the TLS-drop-vs-429 distinction before recording a WALLED verdict.
ALL SEATS — a venue-adjacent PORTAL (financial-media quote API) often carries longer clean history
for a venue's instruments than the venue's own site, whose official endpoint serves only the
current session (measured here: SGE official = today's minute tape; Eastmoney = 22 years) — probe
the portal layer FIRST for history, the venue for provenance/spec.

---

## OP-098 — WAYBACK CDX IS THE POPULATION ENUMERATOR FOR ANY TRACK-RECORD SITE WHOSE PER-ENTITY ROUTE IS PUBLIC AND WHOSE LISTING IS HIDDEN (unified frontier dig, 2026-08-27)   [active]

**THE CLASS.** A track-record ground has TWO routes and they fail independently: the **per-entity**
route (one trader's page) and the **population** route (who exists). Sites routinely leave the
first wide open and the second behind a JS filter, a POST search or an investor login. The
standing failure mode is to confirm the per-entity route, fail to find a listing, and stop —
which is exactly where the FX Blue dig stopped on 2026-08-25 ("sitemap.xml enumerates exactly ONE
user, `/users/example` — there is no population route, and a track-record ground without a
population cannot be mined"). **That verdict was wrong, and the correction is one command.**

**THE OPERATOR.** The archive's URL index is a population enumerator. It is not a content fetch —
it is a keyless list of every URL ever crawled under a prefix, so it recovers the listing the
site declines to publish, INCLUDING entities the current site has delisted:

```
curl -sS "http://web.archive.org/cdx/search/cdx?url=<host>/<entity-path>/*\
&output=text&fl=original&collapse=urlkey&limit=40000&filter=statuscode:200"
```

Then regex the entity id out of the URLs and de-duplicate. **Measured 2026-08-27, both in one
session:** `fxblue.com/users/*` -> **5,077 handles**; `darwinex.com/invest/*` -> **1,479 DARWIN
tickers**. Both grounds had been recorded as population-blocked. The hits are LIVE against the
current site, not archive reads — CDX supplies only the identifier list, and every subsequent
fetch goes to the origin, so archive staleness cannot contaminate the data (it costs only a dead
rate: measured ~0-33% dead handles, which is itself a real attrition number to record, never to
hide).

**WHY IT GENERALISES.** The prerequisite is only that entity pages were once publicly crawlable
under a stable path prefix. That is true of essentially every leaderboard, signal marketplace,
copy-trading platform and public-statement host — the ground RESEARCH §4 calls first-class.
Standing targets to run this against before declaring any of them population-blocked: Myfxbook
`/members/*` and `/portfolio/*`, Collective2 `/strategies/*`, ZuluTrade `/traders/*`, eToro
`/people/*`, MQL5 `/signals/*` (already enumerated natively, use as the CONTROL — if CDX recovers
a comparable count there, the operator is validated against a known population).

**THE TWO CAVEATS, both real.** (1) Path-prefix CDX is **subdomain-blind** (OP, AR s4 2026-08-20) —
enumerate each host separately. (2) **robots is not a reuse grant** (OP-096): CDX legitimises
DISCOVERY of identifiers, never the licence to redistribute what you then fetch. The §13 read on
the origin still has to happen and is unchanged by the enumeration route.

**COROLLARY — "no population route" is a claim requiring the CDX probe.** Under L1.51 ("exhausted"
requires evidence), a track-record ground may not be graded population-blocked until this command
has been run against it and returned nothing. It costs one request.

## OP-099 — THE PRE-COMPUTE DUPLICATE GATE: STRUCTURAL FINGERPRINTS BEAT RETURNS CORRELATION BECAUSE A SKELETON IS A FACT AND A CORRELATION IS AN ESTIMATE (BRAIN hunter s6, 2026-08-28)   [active]

**SOURCE:** `github.com/aircrushin/wq-alpha-agent` (MIT, 12★, pushed 2026-08-03), file
`wq_alpha_agent/diversity.py`, read in full. Reached from the s5 session note's own named next
ground ("RICH, UNMINED beyond README/licence"). **DERIVES-FROM:** BRAIN → alternative agent
implementations → this repo. Its FAMILY_RULES/field vocabulary is BRAIN-platform-specific and is
NOT imported; the mechanism is.

**WHAT IT COMPUTES.** Before any simulation, each candidate expression is reduced to four
comparable objects and checked against the already-held ("protected") set:
  1. `skeleton` — whitespace collapsed, lowercased, **every numeric literal replaced by `#`**.
     Two candidates differing only in lookbacks/weights collapse to the SAME string.
  2. `field_skeleton` — the skeleton with every *operand* replaced by `FIELD` and every local
     assignment by `VAR`. This is the layer the desk does not have: it separates *same shape,
     different data* from *same shape, same data, different parameter*.
  3. field-set **Jaccard**, and a **multi-set** operator overlap (Counter `&` / `|`, so using
     `ts_mean` three times is not the same usage as once).
  4. a family label from distinctive (non-common) fields.
Rejection fires on: exact skeleton match; OR same `field_skeleton` with field-Jaccard ≥ 0.7; OR
same family with key-field ≥ 0.67, field ≥ 0.5 and operator ≥ 0.6 overlap.

**THE MECHANISM WORTH TAKING, stated as the desk's own argument.** A duplicate detected by
*returns correlation* is detected by an ESTIMATE over a finite sample, after the compute is
already spent. A duplicate detected by *skeleton identity* is a FACT, costs nothing, and is
available before the first bar is read. Under L1.60/L1.61 the desk pays a multiplicity charge per
trial and selects on marginal independence: a re-parameterisation therefore costs twice — the
compute AND the budget a genuinely new question needed — and the statistical cost is the larger
one. The `#`-collapse is the precise instrument for "is this a new question or the same question
with a knob turned".

**CONVERGENT, NOT NOVEL — and the provenance matters.** The desk built this argument
independently: `libs/research/variation_blocker.py` (HYPOTHESIS_MAX #3) blocks on mechanism
fingerprint and states the same multiplicity reasoning almost word for word, is wired through
`scripts/run_generation_diversity.py`, and is **live on a 6-hourly cron** (`ops/crontab.manifest`
:1122) writing `data/gen_diversity.json`. So this is a genuine cross-ecosystem CONVERGENCE on the
same mechanism, not an echo — which raises confidence in the mechanism and lowers the value of
the import. **What the desk does NOT have is layer 2**, the `field_skeleton`: the desk's
fingerprints are semantic tuples (`liquidity/reversal/unspecified`), which cannot distinguish
"same structure over a different instrument/field" from "same structure, same field". That is the
one importable delta and it is a small one.

**MT5 ANALOGUE.** Direct, on the desk's candidate expressions; `translate_to_mt5` is not needed
because this operates on *candidate syntax*, not on market data — it is universe-agnostic and
therefore survives the MT5 mandate unchanged, which is rare on this ground.

**WHAT IS DELIBERATELY NOT IMPORTED (L1.6, and the standing refusal on this ground).** The four
thresholds (0.7 / 0.67 / 0.5 / 0.6) and `self_correlation_max=0.7` are **facts about their
process, never gates for ours**: they are tuned for a submission funnel whose expensive
out-of-sample stage is paid by the platform, not by the tuner. The desk's own variation_blocker
states the opposite bias explicitly and correctly — "the timid error here is the more expensive
one" (L1.21a), so it blocks only on EXACT fingerprint match. Importing these thresholds would
narrow the desk's search space to fit a stranger's cost structure.

**THE ONE NUMBER THIS DIG ACTUALLY SURFACED, and it is not about diversity code.** The live
6-hourly artifact reports `market_breadth: 11` over a 200-candidate batch, against a canonical
registry of **251 symbols** — 4.4% — and `feature_breadth 0.060`, with verdict `OK` and zero
flags. Instrumentation that reports a 4.4% breadth as OK is not measuring against the universe
(L1.61: the hunted ground is every tradable Fusion symbol). Routed as a separate item, not fixed
here: this seat is research-only.

---

## OP-100 — the BRAIN post-processing pipeline, in its exact order, and why the order is the semantics

**Source:** `github.com/efJerryYang/worldquant-brain-simulator` (GPL-3.0, 32★, public), an
independent offline reimplementation of the BRAIN simulator. **Read for MECHANISM ONLY — GPL-3.0,
so no line of it is copied into this desk and none is proposed for copying.** Found by the
RECURSIVE EXPANSION mandate: BRAIN → alternative implementations → the people who had to
*understand* the semantics in order to rebuild them. The brief predicted this node would be the
highest-yield one on this ground and it was.

**What the official documentation elides and this implementation states, from `simulate.py`:**

The daily loop is `(prev_day, today)` and the whole pipeline is:

1. **Universe selection on `prev_day`** — `nlargest(top, "cumulative_liq")` over the *previous*
   day's liquidity. Point-in-time by construction.
2. **Alpha computed on a window ending at `prev_day`** (`start_day <= date <= prev_day_dt`).
   **This is what `delay: 1` actually IS** — not a `shift()` applied to the finished signal, but a
   truncation of the input data window, with the return realised on `today`. That is a materially
   stronger formulation than shifting: a shifted signal can still have been *built* from a
   full-sample statistic, which is the desk's own R0289 causal-guard blind spot (a `z(funding)`
   over the whole sample passes `check_causal` today). Windowing the input cannot express that leak.
3. **Neutralization** — `alpha = alpha - alpha.mean()`, cross-sectional over the universe.
4. **Truncation** — `alpha.clip(-boundary, +boundary)`.
5. **Normalization** — `alpha = alpha / alpha.abs().sum()`, i.e. **unit gross book**.
6. **PnL** — `(weights · today's returns) * booksize`.

**THE ORDER IS LOAD-BEARING AND IT IS NOT THE INTUITIVE ONE.** Truncation runs *before*
normalization, so the `truncation` setting is **not a cap on final portfolio weight** — it clips
the un-normalised, mean-subtracted alpha, and the subsequent divide rescales everything. Measured
on random draws, with `truncation = 0.01`:

| universe N | `sum(|clipped|)` | final `max(|w|)` | exceeds the bound? |
|---|---|---|---|
| 20 | 0.191 | 0.0523 | **YES — 5.2x the bound** |
| 50 | 0.500 | 0.0200 | **YES — 2x** |
| 100 | 1.000 | 0.0100 | at the bound exactly |
| 251 | 2.506 | 0.0040 | no |
| 3000 | 29.90 | 0.0003 | no |

The crossover is exactly **N = 1/boundary**: below it the normalisation *inflates* past the
truncation bound, above it the bound never binds on the final weight at all. On a Top3000 equity
universe the setting is nearly inert; the same code on a small book silently levers the largest
name. **The desk's canonical MT5 registry is 251 symbols — above the crossover — but any
asset-class or currency-bucket sub-book is comfortably under 100, which is precisely where the
bound inverts.** Recorded as a fact about their construction, never as a gate for ours (L1.6).

The reason the order is nonetheless *correct* is the one thing the settings file never says:
clip-before-normalize yields gross exposure of exactly 1.0 always, whereas normalize-before-clip
measured **0.956** on the same draw — clipping after normalisation breaks the unit-gross book,
which is the invariant the whole PnL line depends on. Anyone reimplementing this who "fixes" the
order to make truncation behave like a weight cap silently un-normalises their book.

**MT5 analogue:** steps 3–5 are a complete, grouping-map-free portfolio-construction spec that the
desk can run on 251 Fusion symbols today. See OP-101, which is the actionable half.

**What it needs that the desk lacks:** nothing for the market arm. The `Sector`/`Industry`/
`Subindustry` arms need the grouping map that is still this ground's blocking input.

---

## OP-101 — market neutralization needs NO grouping map, and the desk never noticed it was unblocked

**This is the session's real find, and like s6's it is about the desk rather than the platform.**

The desk adopted four BRAIN operators on 2026-08-07 (`group_rank`, `group_zscore`, `ts_backfill`,
`trade_when`). Two of them refuse to compute without a grouping map the desk does not have, and
that dependency has been carried ever since as *the* blocking input on this ground.

**Verified state, read this session, not inherited:**
- `libs/alpha_factory/wq_operators.py` defines `_require_groups`, `group_rank`, `group_zscore`,
  `ts_backfill`, `trade_when`, `fitness` — **and no neutralization function of any kind.**
- `grep -rn "neutraliz" libs/ desks/mt5/ --include=*.py` returns exactly three live hits:
  `libs/risk/overlays.py:36 beta_neutralize` (a regression-based *risk overlay*, not a
  portfolio-construction step), a data-cleaning docstring, and
  `libs/research/evidence_tier.py:235-236`, which maps *"sector neutral" / "industry neutral"* →
  *"neutralize by MT5 asset class and currency-risk bucket"*.

So the entire neutralization axis was translated into the desk's own mapping table **as a
group-conditional operation**, and therefore inherited the grouping-map block wholesale.

**But the platform's own neutralization ladder is `None / Market / Sector / Industry /
Subindustry`, and the `Market` rung is `alpha - alpha.mean()` over the point-in-time universe.
It takes no taxonomy at all.** It is one line, it runs on the 251-symbol registry today, and it
has been sitting unbuilt behind a dependency it does not have.

Why this matters beyond one missing line:

1. **It is the control arm the desk's own regime law already requires.** Any future
   asset-class/currency-bucket neutralization must prove itself *against* an unconditional
   control. Market-neutral IS that control, and it is cheaper than the thing it controls for.
2. **It converts the grouping map from a blocker into a measurable increment.** Today "we have no
   grouping map" is an unfalsifiable reason to build nothing. With the market arm running, the
   question becomes "what does bucketing add over demeaning?" — a number, gate-able, and a
   perfectly good null if it adds nothing.
3. **`_require_groups` refusing is the correct behaviour and is not the defect.** The defect is
   that the ladder's bottom rung was never separated from its top rungs when the axis was
   translated, so a map-free operation was filed under a map-dependent heading and disappeared.

**Routed, not built — this seat is research-only (freeze).** The exact prescription: add a
`market_neutralize(x)` = cross-sectional demean over the point-in-time universe to
`wq_operators.py`, and extend the `evidence_tier` mapping rows at lines 235–236 so the ladder's
rungs are distinguishable rather than collapsed onto the group-conditional translation.

**CAVEAT, stated because it cuts against the find.** Market-neutralizing is not free on an MT5
book the way it is on a Top3000 equity cross-section. Demeaning across 251 heterogeneous
instruments (FX crosses, gold, indices, energy, share CFDs) subtracts a mean that has no single
economic meaning — and the desk has already measured the shape of this failure: removing a common
factor *manufactures* negative residual correlation, and residual correlation must be compared to
−1/(N−1), never to zero (`demeaning_floor()` in `libs/research/cohort_independence.py`; the
64.4-independent-bets error). The honest form of this item is therefore *within-asset-class*
demeaning, which needs only the asset-class label the registry already carries — still no
taxonomy purchase, still unblocked, and it is the version that should be built.

**Verified this session (not inherited): the label exists and the buckets are measured.**
`desks/mt5/data/universe/universe.json` carries `asset_class` on **248 of 251** symbols:
Equities 103 · Forex Exotics 57 · Forex 29 · Indices 16 · Crypto 14 · Commodities 12 ·
Soft Commodity 11 · Bonds 3 · Energy 3 · **unlabelled 3**. So within-asset-class demeaning is
buildable today with zero new data.

Two consequences worth carrying forward:

- **Only ONE bucket clears OP-100's `N = 1/boundary` crossover.** With `truncation = 0.01` the
  crossover is 100 names, and Equities (103) is the sole bucket above it. Every other bucket —
  including all of FX — sits in the zone where clip-before-normalize *inflates* the largest
  weight past its own stated bound, by 2x at N=50 and 5.2x at N=20. **A truncation setting
  imported from an equity venue is not just inert on this desk's books, it is inverted on eight
  of nine of them.** If a bounded per-instrument weight is wanted here, the bound must be applied
  after normalisation and the gross re-scaled explicitly — which is a different construction, not
  a parameter change.
- **The 3 unlabelled symbols are a real gap, not a rounding error**, because an unlabelled
  instrument cannot be demeaned within its class and would silently fall into whatever the
  grouping code's default bucket is. That is the WS-005 shape (absence read as a clean verdict);
  it should fail loud, not default. Named here, routed, not patched — research-only freeze.

---

## OP-102 — MUTUAL INDEPENDENCE IS BOUGHT WITH FIELD BREADTH, NOT OPERATOR BREADTH (BRAIN hunter s8, 2026-08-29)   [active]

**Source.** `github.com/CrisperX/50_WorldQuant_Alpha_Examples_for_Alphathon` (85★, 2023-10, **no
licence — all rights reserved, read for MECHANISM ONLY**, statistics computed over it, not one
expression copied here). Its entire stated purpose is the desk's own scarcest axis: *"50 alphas
that can pass the correlation test if they are submitted together."* s7 ranked it #1 on the
measured population precisely because it is boring; that ranking was right.

**WHAT IT COMPUTES — measured over all 50 rows of `alpha50.csv`, not read off the README:**

| quantity | value |
|---|---|
| alphas | 50 |
| **distinct data fields** | **50** |
| distinct operators | **8** — `rank` 28, `ts_mean` 18, `ts_zscore` 2, `sum`/`delay`/`group_rank`/`ts_av_diff`/`ts_corr` 1 each |
| median formula length | **20 characters** (min 13, max 137) |
| field families | `mdf_*` model-derived 22 · `fnd6_*` fundamentals 18 · price/volume 6 · ratio/analyst/sector 5 |

`rank` + `ts_mean` cover **46 of 50**. The median alpha is literally a field wrapped in one
operator. The README's proprietary-sounding *"unique method"* that found *"over 400"* such alphas
is, structurally, **enumerate the field catalogue and rank each field**.

**THE MECHANISM, stated so it can be implemented without the source.** Two alphas over the same
input field cannot be independent however different their operators — the operator is a monotone
or near-monotone re-expression of one underlying quantity, so the cross-sectional orderings stay
coupled. Two `rank()`s over *different* fields are close to independent **by construction**,
because their correlation is inherited from the correlation of the raw fields and nothing else.
**Operator variety re-describes one signal; field variety adds signals.** Independence is
therefore purchased in the units of the DATA CATALOGUE, and the number of mutually-independent
alphas a research process can produce is bounded above by its count of weakly-correlated input
FIELDS, not by the size of its expression grammar.

**MT5 ANALOGUE AND WHY IT MATTERS HERE.** The desk's marginal-independence problem (L1.18,
L1.61 — *"selection optimises MARGINAL INDEPENDENCE directly, so a second copy of a held edge
scores ~0"*) has been attacked from the OPERATOR side for six BRAIN sessions (OP-093…OP-101) and
by the generic search's ~4,900 primitives per symbol. This artifact says the attack is on the
wrong axis. `edge_search.build_primitives` derives **>130 named transforms and ~4,900 primitives
including pairwise interactions from a raw intake of OHLCV + spread/volume** — one field family.
An interaction `x_a__b` of two transforms of `close` is not a new field; it is a fourth
re-description of the same field, and it is counted as a trial while contributing nothing to
independence. **The desk is transform-rich and field-poor, which is the exact inverse of the one
published artifact whose purpose is constructing an independent set.**

**THE OPERATIONAL CONSEQUENCE, and it is a reallocation, not a note.** Marginal spend on the
independence axis belongs on RAW FIELD INTAKE — the free-data seats, the macro/COT/curve/flow
axes, the desk's own tape aggregates — ahead of further operator or interaction expansion. A new
field is worth more than a new operator whenever the desk already holds more operators than
fields, which it does by two orders of magnitude. This is the value-of-information argument
behind the free-data mining seats, and it now has a measurement behind it rather than a prior.

**AND IT IS WHY THIS SESSION WENT AND COUNTED — see OP-103.** Applying this operator to the desk
itself was what surfaced R0715: the desk's live generic discovery engine consumes **zero**
external fields, because the whole external axis raises and is swallowed.

**Trial-accounting fact recorded about their process, NEVER imported as a gate (L1.6).** Sharpe
across the 50 is min = median = **1.25** = the platform's stated submission bar, max 1.29 — a
mass point at a threshold, not a distribution. The settings grid (Universe × Decay × Truncation ×
Neutralization) carries eleven singleton non-round `Decay` values (13, 18, 52, 55, 65, 70, 78, 90,
95), so each published alpha is the **argmax over an unreported per-alpha settings search**. The
performance column is informative about the filter and uninformative about edge. Their bar is a
fact about them; ours is 5.236 deflated and does not move.

**Base rate for OP-101, measured here:** **48 of 50** alphas carry a neutralization setting
(Subindustry 19 · Market 17 · Sector 8 · Industry 4); only 2 run `None`. Neutralization is the
default in the reference process and is entirely absent from `wq_operators.py`.

---

## OP-103 — APPLY EVERY MINED OPERATOR TO THIS DESK BEFORE FILING IT: OP-102 POINTED AT R0715 IN ONE COUNT (BRAIN hunter s8, 2026-08-29)   [active]

**The pattern, and it is a research method rather than a finding.** OP-102 says independence is
bought in units of input FIELDS. The next action after extracting a mechanism is not to file it —
it is to **run its measurement against this desk's own artifacts** and see what the number says
here. That single step, costing one command, converted a mined observation about a stranger's
equity alphas into a live defect in the desk's nightly discovery engine:

- Count the desk's raw input fields → read `edge_search.resolve_inputs` → **run it** →
  `TypeError: Cannot join tz-naive with tz-aware DatetimeIndex` at `edge_search.py:296`, on the
  first symbol tried.
- Verify from the OUTPUT rather than the code (the standing lesson): today's
  `edge_search_results.json` — 3,543 hypotheses, written 05:55 — contains **ZERO** features
  matching `ext_`. Not one peer residual, lead-lag, cross-sectional, triangular, tick-book, swap,
  macro or COT feature has entered the desk's generic search.
- Root cause, measured: **173 of 197 universe `_H1.parquet` files are tz-naive and 24 are
  tz-aware UTC** — the partial-sync generation split recorded on 2026-08-28. The cross-section
  `pd.concat` at line 296 therefore always mixes generations. The caller at line 612 catches the
  raise into a `print` and continues on pure OHLCV, and because the raise unwinds the whole
  function it **discards the peer/lead/corr keys already built above it** (one family's failure
  destroys 1..N−1).

**Ledgered R0715 (tz + per-family isolation), R0716 (macro reader reads the wrong nesting level
and would broadcast a scalar), R0717 (COT reader names `.json` files that are parquet
directories). Not patched — research-only freeze.**

**The transferable rule:** a mined mechanism is a *measuring instrument*. File the mechanism, but
point it at this desk first — the yield from measuring ourselves with a stranger's ruler beat the
yield from the stranger's alphas by a wide margin this session, and it will usually do so, because
nobody else has ever measured us.

---

## OP-104 — `bfill` INSIDE A FEATURE TRANSFORM IS A LOOK-AHEAD THE CAUSAL GUARD CANNOT SEE (BRAIN hunter s8, 2026-08-29)   [active]

**Source.** `efJerryYang/worldquant-brain-simulator` → `src/alpha_pool/expression.py` (GPL-3.0,
mechanism-only read; note the path — s7's handoff recorded `src/simulator/alpha_pool/…`, which
**404s**; correct path is `src/alpha_pool/expression.py`). The file credits
`yli188/WorldQuant_alpha101_code` as its origin, so this is the ancestor of a widely-forked
alpha101 lineage rather than one author's slip.

**Three documented defects in the reference implementation, all of them classes this desk knows:**

1. **`decay_linear` calls `df.fillna(method="bfill")` before weighting.** Backfill inside a
   feature transform fills a missing observation with a **future** one. It is a look-ahead in the
   FEATURE, and it survives every guard that checks the alignment of signal to return — the
   desk's own R0289 blind spot exactly (`check_causal` passes a full-sample `z(funding)`). The
   function's own comment says *"The backtest engine should assure to be snooping bias free"*,
   which is the assumption that lets the leak live: **the engine cannot repair a feature that was
   built from the future before the engine ever saw it.**
   *Verified against this desk the same session: `grep` for `bfill` / `fillna(method=` across
   `libs/` and `desks/mt5/` returns **no hits in any feature builder** — the only matches are the
   word "backfill" in `perishability.py` and friends. **The desk is clean on this class**, and
   that is a verified negative worth recording rather than an assumption.*
2. **`rank(df, rate=2)` accepts the `rate` parameter and never reads it.** The official operator
   is documented *in the file's own quoted description* as approximate by default —
   *"When rate is set to 0, the sorting is done precisely. The default value of rate is 2"* — so
   the platform's canonical `rank`, the operator carrying 28 of OP-102's 50 independent alphas,
   is a **quantised** rank unless explicitly told otherwise. The reimplementation silently does
   an exact `df.rank()`.
3. **`decay_linear` also calls `df.as_matrix()`**, removed from pandas in 1.0 (2020), and returns
   `columns=["CLOSE"]` — collapsing a multi-symbol panel to one hardcoded column name. The
   function cannot execute on any modern pandas.

**THE TRANSFERABLE LESSON, now on its second instance in this one repo.** s7 found
`simulate.py:257` parsing `neutralization` into a variable never read again. Here, `rank` parses
`rate` and never reads it. **A settings key that is parsed but not consumed is indistinguishable,
from the outside, from one that works** — and this repo's README carries the open question
*"results are still different from the platform's"* with two such keys sitting unread in it. The
desk's own version of this is the gap-wirer class: *a producer computes a distinction, the
consumer collapses it.* Where a config key is accepted, assert it is consumed.

## OP-103 — THE FIELD-REACHABILITY PARTITION: 50.5% of canonical alpha101 is reachable on the desk's tape, and the entire gap is THREE named items (brain-hunter s10, 2026-08-29)

s9 measured this desk's **external** field breadth at **1** (every one of 1730 `ext_` names is a
function of peer close price) and named the alpha101 field-vector extraction as the way to get the
comparison number — *how many distinct input fields the reference set spans, and how many have an
MT5 analogue.* That ratio estimates the desk's reachable independence ceiling. It is now measured.

**SOURCE:** `efJerryYang/worldquant-brain-simulator` `src/alpha_pool/alpha101.py`, GPL-3.0,
43,486 b, fetched from `raw.githubusercontent.com`. Read by SCRIPT, not into context: methods split
on `def alpha\d+`, raw fields taken as the `self.<name>` reference set per method.

### THE MEASURED FIELD VECTOR — the reference set runs on EIGHT raw fields

| field | alphas using it (of 82 implemented) |
|---|---|
| `close` | 53 | 
| `volume` | 53 |
| `high` | 31 |
| `vwap` | 30 |
| `low` | 28 |
| `open` | 25 |
| `returns` | 12 |
| `cap` | 1 |

Mean **2.84** distinct fields per alpha (median 2.5, min 1, max 6). This is the OP-102 ruler
confirmed on an independent artifact: independence is bought in units of the DATA CATALOGUE, and
each individual alpha is field-shallow — the *set* is broad because the catalogue is.

### THE REACHABILITY PARTITION AGAINST THE DESK'S ACTUAL TAPE

Desk tape measured, not assumed: **197/197** `*_H1.parquet` share one schema —
`open high low close tick_volume spread real_volume`. Mapping `volume → tick_volume` (a proxy, see
caveat) and `returns → derived from close`:

```
101  canonical alphas
 -18  require IndNeutralize(..., IndClass.sector/industry/subindustry)  -> NO GROUPING MAP
 ---
  82  implemented in the OSS port
 -30  require vwap                                                     -> NOT ON THE TAPE
  -1  requires cap                                                     -> NOT ON THE TAPE
 ---
  51  REACHABLE  = 62% of implemented, 50.5% of canonical
```

**There is no long tail.** Beyond the grouping map, exactly TWO fields — `vwap` and `cap` — account
for the entire remaining gap. That is a shopping list, not a research programme.

### THE INDEPENDENT CONFIRMATION, AND IT ARRIVES FROM THE OPPOSITE DIRECTION

The 18 missing alphas are **not stubbed and not partial — they are absent from the file entirely**
(`alpha48/58/59/63/67/69/70/76/79/80/82/87/89/90/91/93/97/100` return `NOT MENTIONED ANYWHERE` on a
source search). They survive only as **commented formulas**, and every one of those comments carries
`IndNeutralize(..., IndClass.*)`.

So the most-used open-source alpha101 reimplementation hit the desk's own blocking input, and
**dropped 17.8% of the canonical set rather than solve it.** This desk's missing grouping map is not
a local gap in a corner of one engine; it is the same wall an independent implementer hit and
declined. That is external corroboration of the brief's standing claim — *a grouping the desk can
actually build is worth more right now than another operator it cannot apply* — and it now carries a
number: **18 reference alphas, 17.8% of the canonical set.**

### VWAP IS THE SINGLE HIGHEST-LEVERAGE MISSING FIELD, AND IT IS NOT ONE FLAG AWAY

`vwap` blocks **30/82 (37%)** of implemented alphas — more than every other missing field combined.
The tempting conclusion is that it is cheap, since MT5 serves sub-H1 bars from the same terminal the
desk already pulls H1 from (`fetch_universe.py:94` pins `mt5.TIMEFRAME_H1`). **Measured, that
conclusion is wrong.** Sub-H1 coverage on the box is **4 symbols of 197** (3 FX crosses at M15,
`XAUUSD` at M1/M5/M15), and the only M1 artifact — `XAUUSD_M1.parquet`, 20,000 rows — spans
**2026-08-03 → 2026-08-21, eighteen days**, against an H1 history reaching back to 1984 on some
symbols. Broker M1 retention, not collector scope, is the binding limit.

**Therefore:** a *true* intrabar VWAP is not reconstructable over the backtest window. What IS
available is a tick_volume-weighted typical-price **proxy** at H1 — a different object, and any
alpha built on it is *inspired-by*, never a replication. Label it as a proxy at construction or the
provenance is lost the moment it enters the gauntlet. **Recovering vwap over history is a DATA-AXIS
item (a tick or M1 archive), not an engineering one** — routed to `data_axis_watchlist.md`.

### SIDE MEASUREMENT — `real_volume` IS ADVERTISED ON 197 SYMBOLS AND DEAD ON 195

`real_volume` is in the schema of all 197 files and is **all-zero on 195**. The only two exceptions
are US share CFDs (`BlackRock` 5,637/13,480 non-zero from 1999-10; `CVSHealth` 9,374/17,219 from
1984-12) and both are *partially* populated. `tick_volume` and `spread` are populated everywhere.

`edge_search.py:210` admits the column on `if col in d.columns` — **presence, not content**, the
WS-005 shape. Checked downstream before reporting it: `edge_search_results.json` contains **zero**
`real_volume` hypotheses out of 3,543, so the constant-zero and all-NaN columns are filtered later
and **this is dead weight today, not a live defect.** Reported as the honest null it is.

**But it is a loaded gun for exactly the operators this seat is trying to add.** A cross-sectional
`rank`/`zscore`/`group_rank` over `real_volume` puts those 2 symbols above 195 structural zeros **by
construction, forever** — a degenerate ordering that reads as a signal. The desk is actively working
to point group operators at this universe, so the guard should become content-aware (`nunique > 1`)
*before* that happens, not after.

---

## THE BLOCKING INPUT IS UNBLOCKED — `data/mt5_grouping_map.json` (BRAIN HUNTER s11, 2026-08-29)

`group_rank` and `group_zscore` have been inert since adoption for want of a peer map (s10 measured
the cost from the other side: **18 of 101 canonical alphas, 17.8%**, unimplementable without one).
The map now exists, built from data already on the box by
`data/brain_hunter_s11_build_grouping_map.py`, and **the operators were run against it** — both
return a series on all five schemes rather than `None`.

| scheme | symbols | groups | median group | max group | mean \|corr\| vs universe-wide `rank` |
|---|---|---|---|---|---|
| `asset_class` | 194 | 7 | 15 | 64 | **0.819** |
| `currency_base` | 80 | 8 | 7 | 21 | **0.716** |
| `currency_quote` | 79 | 19 | 4 | 13 | **0.493** |
| `corr_cluster` k=8 (2025) | 192 | 6 | 9 | **125** | **0.852** |
| `corr_cluster` k=24 (2025) | 183 | 13 | 5 | 67 | **0.716** |

Window 2024-01-01..2025-12-31, daily log returns, baseline = universe-wide `rank` over the same
members, per-symbol correlation then averaged. Saved: `data/brain_hunter_s11_group_independence.json`.

**THE FINDING, and it decides which scheme to point the search at: a grouping is not automatically a
new axis.** `asset_class` — the obvious `IndClass.sector` analogue, and the one the desk would have
adopted by default — reproduces the universe-wide rank at **0.82**, because its largest group *is*
most of the universe (103 equity CFDs of 251). The `k=8` correlation cluster is worse still at
**0.85**: clustering "succeeded" and produced **one 125-member blob** plus five fragments. Both
would consume a whole new arm of the search space to recompute something the desk already has —
precisely the failure `_require_groups` was written to refuse, arriving through the front door with
a legitimate map instead of a missing one.

**Independence tracks median PEER-GROUP SIZE, not the sophistication of the grouping.** The ranking
above is monotone in it. `currency_quote` (19 groups, median 4 members) is the only scheme that buys
a genuinely different question, and it is the one with **no equity counterpart at all** — "is EURUSD
extreme against the other things quoted in USD?" is not a factor BRAIN can express. It is the
recommended first arm; `currency_base` and `corr_cluster k=24` are the second tier; **`asset_class`
and `corr_cluster k=8` should not be given a search arm on this measurement.**

**The cluster maps are point-in-time by construction.** Key `Y` is estimated on year `Y-1` daily
returns only; no bar is ever grouped using its own future. A whole-sample cluster map would be
lookahead and is deliberately not produced. Both cut heights (8, 24) are fixed a priori and carried
side by side rather than tuned — the peer-size axis is left visible to the consumer.

Unlabelled symbols are **omitted, never pooled** into an `other` bucket, and singleton groups are
dropped at build time (a group of one has no rank to compute).

### INDEPENDENT CORROBORATION OF s10 — THE IndClass WALL IS UNIVERSAL TO THE PUBLIC LINEAGE

s10 found the most-used OSS port dropped 18 canonical alphas rather than solve the grouping problem.
Checked against the **upstream original it credits**, `yli188/WorldQuant_alpha101_code`
(851★, `101Alpha_code_1.py`, 44,512 b, HTTP 200 from `raw.githubusercontent.com`):

```
upstream implemented        83
port implemented            82
missing from BOTH           18  = {48,58,59,63,67,69,70,76,79,80,82,87,89,90,91,93,97,100}
                                  every one present only as a COMMENTED formula carrying
                                  IndNeutralize(..., IndClass.*)
port minus upstream          1  = alpha56 -- the `cap` alpha, s10's other named field gap
```

Two independent public implementations, the same 18 alphas, the same stated reason, and the single
divergence between them lands exactly on the *other* field s10 named. **The public lineage has never
solved this; it has routed around it twice.** That makes the map above the differentiating asset on
this ground rather than a catch-up item — and it is why the independence table matters more than the
map's existence: the desk can now ask the question, and only one of its five ways of asking it is
worth a search arm.

---

## `correlation` / `covariance` and binary `min`/`max` — BRAIN hunter s12 (2026-08-29)

Source: `yli188/WorldQuant_alpha101_code` (851★) `101Alpha_code_2.py` (111,340 b) — a
**machine-transpiled** Quantopian `CustomFactor` implementation, a different artifact from the
hand-written `101Alpha_code_1.py` s11 exhausted. Public route only (`raw.githubusercontent.com`,
`api.github.com`; robots 404 = ALLOW-ALL under RFC 9309). Raw:
`data/brain_hunter_s12_alpha101_code2.json`.

### 1. THE TRANSPILER COMPUTES THE OTHER OPERATOR — 47/47 call sites, exactly inverted

| | in the expression comment | in the emitted code |
|---|---|---|
| `correlation(...)` | 45 | `.rolling(d).cov(...)` ×45, `.corr(` ×0 |
| `covariance(...)`  | 2  | `.rolling(d).corr(...)` ×2, `.cov(` ×0 |

Not a rounding of intent — a **symbol-table inversion in the code generator**, both directions,
zero exceptions, affecting **35 of the 77 alphas it implements**. `correlation` is the most-used
binary operator in the canonical corpus, so the single most-copied public alpha101 implementation
silently ships the wrong one on 45% of its output. Anyone who lifted a formula from this file
lifted `cov` where the paper says `corr`.

### 2. AND THE DISTINCTION IS LOAD-BEARING — measured on the desk's own tape

`cov = corr · sd_x · sd_y`, so the swap injects a volatility tilt that survives the cross-sectional
`rank` wrapped around it. Measured as mean daily Spearman between the two cross-sectional orderings,
24 Fusion symbols (FX majors/crosses, XAUUSD, XAGUSD, BTCUSD, ETHUSD), D1 from `_H1`, 2018-01-02 →
2026-08-17, ~2,230 days:

| input shape | d | mean Spearman(corr-order, cov-order) | p05 | days < 0.90 |
|---|---|---|---|---|
| rank-transformed (alpha2 shape) | 5 | **0.920** | 0.840 | 23.6% |
| rank-transformed | 6 | 0.933 | 0.866 | 14.9% |
| rank-transformed | 10 | 0.952 | 0.901 | 5.0% |
| **raw** (`close`, `tick_volume`) | 5 | **0.775** | **0.597** | — |
| raw | 10 | 0.786 | 0.593 | — |

Rank inputs are the *best* case: bounded [0,1] ranks compress the `sd_x·sd_y` multiplier, and even
there the orderings disagree on a quarter of days at d=5. On raw inputs they are plainly different
operators. **They are two operators, not one with a scaling quirk — and this desk has NEITHER.**
`libs/alpha_factory/wq_operators.py` exposes five functions (`group_rank`, `group_zscore`,
`ts_backfill`, `trade_when`, `fitness`) and no pairwise operator at all; `edge_search.py` uses
`.rolling().corr()` only as a *feature* against a fixed peer list (line 283), never as an operator
over arbitrary field pairs, and `.cov(` appears nowhere in either.

One hypothesis of mine did **not** survive its own control: I expected the cov ordering on raw
inputs to collapse into the price-level ordering, since the panel spans 109,119× in price
(0.59 → 64,382). It does not — mean |Spearman| against the price-level rank is only **0.33**. The
divergence is driven by the *volume* standard deviation, not the price scale. Recorded because the
plausible version of this claim is the one a reader would assume.

**MT5 analogue:** direct, no equity dependency — `ts_correlation(x, y, d)` and `ts_covariance(x, y, d)`
over any two per-symbol series (price, return, range, `tick_volume`, spread, swap), then a
cross-sectional wrapper. `translate_to_mt5` needs no new mapping; this is a pure operator gap.

### 3. THE SECOND MISSING PARTITION IS AN OPERATOR GAP, NOT A DATA GAP

`code_2` implements 77 and skips 24 — six *more* than `code_1`'s 18. The partition is exact and
mutually exclusive:

- **18** (`{48,58,59,63,67,69,70,76,79,80,82,87,89,90,91,93,97,100}`) — every one carries
  `IndNeutralize(..., IndClass.*)`. The s10/s11 wall, a **data** gap, and the one s11 closed for
  MT5 with `data/mt5_grouping_map.json`.
- **6** (`{71,73,77,88,92,96}`) — **not one contains `IndClass`**. All six are
  `min(...)`/`max(...)` of *two composite branches*, and **zero of the 77 implemented alphas use
  that form**. 6/6 and 0/77: a clean split. The transpiler handles the unary time-series
  `ts_min/ts_max` and cannot emit a binary elementwise combinator over two full sub-expressions.

Alpha73 is the proof the driver is min/max rather than anything else — it has no `correlation` and
no `IndClass`, only `max(rank(decay_linear(...)), Ts_Rank(decay_linear(...)))`, and it is skipped.

**The mechanism worth extracting is the SHAPE, not the formulas.** `min`/`max` over two independent
branches is a *disjunctive* hypothesis — "fire on whichever of two distinct mechanisms is stronger
today" — as opposed to the product/sum forms that dominate the desk's combination engine, which are
conjunctive and average away a branch that is silent. This is regime-specialisation expressed inside
a single expression (LAWS §5, the regime specialization law) rather than across sleeves.
`np.minimum`/`np.maximum` appear **0 times** in `edge_search.py` or `libs/alpha_factory/`: the desk
cannot currently express a disjunctive candidate at all.

### 4. THE PDF IS NOT LOCKED, IT IS DIAGNOSED

`101 Formulaic Alphas.pdf` (244,416 b) is the *original paper*, not a port. Streams decompress
cleanly; the text is font-subsetted. I harvested 96 `ToUnicode` CMap entries, but the file carries
multiple subset fonts sharing one code space, so a single merged CMap collides (`a`→`^`). The route
is **per-font CMap binding via the page resource dict / `Tf` operator** — ~40 more lines. No PDF
tooling exists on the box (`pdftotext`, `pdfminer`, `fitz`, `PyPDF2`, `pypdf` all absent) and the
freeze forbids installs. Graded EXTRACTABLE-BUT-BLOCKED with the exact cause, never `locked`.

## THE CANONICAL OPERATOR TABLE, FROM THE PAPER ITSELF (BRAIN HUNTER s13, 2026-08-29)

s12 left `101 Formulaic Alphas.pdf` as EXTRACTABLE-BUT-BLOCKED with a diagnosed route. The route
works: `data/brain_hunter_s13_pdf_cmap_extract.py` binds each `/ToUnicode` CMap to its own font
resource name and switches tables on the `Tf` operator, which is what the merged-CMap collision
needed. A **second** bug was in the way and is the more general one: a `\r?\n`-anchored `endstream`
regex silently dropped **21 of the paper's 22 pages**, because Flate payloads abut `endstream` with
no trailing EOL. Index-based slicing recovers all 22. The extractor is pure stdlib — the box has no
PDF tooling and the freeze forbids installs — so **every PDF ground on this desk is now open**, not
just this one. All 101 Appendix-A formulas recovered. Math-subset glyphs carry no ToUnicode entry
and extract empty, so Tables 1–5 lose their symbol labels; body text and formulas are complete.

**§13/licence:** arXiv robots **Allows `/pdf` and `/html`, Disallows `/e-print` and `/src`** — the
easy LaTeX-source route is barred and was not used. Appendix B of the paper asserts **WorldQuant
LLC copyright over the Appendix A formulae**, so no verbatim formula corpus is stored in this repo;
`data/brain_hunter_s13_alpha101_paper.json` holds derived structure, counts and the short factual
operator definitions only.

### The definitions the reimplementations paraphrase (authoritative, Appendix A.1)

| operator | canonical definition | desk status |
|---|---|---|
| `correlation(x,y,d)` | time-serial correlation over past d days | **absent** (R0729) |
| `covariance(x,y,d)` | time-serial covariance over past d days | **absent** (R0729) |
| `rank(x)` | cross-sectional rank | present, universe-wide |
| `scale(x,a)` | rescale so `sum(abs(x)) = a`, default `a=1` | absent |
| `decay_linear(x,d)` | weighted MA, linearly decaying weights `d, d-1, …, 1`, rescaled to sum to 1 | absent |
| `indneutralize(x,g)` | **x cross-sectionally DEMEANED within each group g** | **absent — see below** |
| `min(x,d)` / `max(x,d)` | `= ts_min(x,d)` / `= ts_max(x,d)` — **window forms only** | n/a |
| non-integer `d` | **"converted to `floor(d)`"**, stated explicitly | n/a |

### `indneutralize` IS NOT `group_zscore`, and on an MT5 book that is expensive

The canonical operator **demeans within group and stops**. `wq_operators.group_zscore` demeans and
then divides by the within-group cross-sectional sd; the desk exposes no demean-only operator, so it
cannot express the operator that **18 of the 101** canonical alphas call — the exact 18 that s11's
grouping map was built to unblock. Measured on the desk's own tape (52 Fusion symbols, 5 groups,
D1 from `_H1`, 2021-01-04 → 2026-08-26, 1,449 days, s11's `asset_class` arm): daily cross-sectional
Spearman between the two orderings **mean 0.914, p05 0.857, 29.3% of days below 0.90**.

The driver is stated rather than assumed: median within-group cross-sectional sd spans **6.2×**
(Forex 0.00172 → Crypto 0.01063). Dividing each group by a different constant re-interleaves the
pooled cross-section, systematically **amplifying the lowest-dispersion group and suppressing the
highest**. On the paper's own venue within-sector dispersion is broadly comparable, so the
substitution is nearly harmless *there* — this is a venue-specific failure of an equity-venue
assumption, not a general one. → **R0732**.

**Population stated:** 52 of 251 registry symbols (partial parquet sync). An earlier pass over the
full 1970–2026 span returned a Spearman of exactly **1.000**, which was an artifact — only ONE group
(Crypto, 14 symbols) populated any given day, so the sd divisor was a single positive constant and
could not reorder anything. Recorded so it is not re-derived.

### `floor(d)`, and the reimplementation rounds

The paper mandates `floor(d)` for non-integer windows. `yli188/…/101Alpha_code_2.py` **ROUNDS on
14 of the 14 windows where floor and round differ, and floors on none**. Worst case alpha98
`d=4.58418 → 5` instead of `4`: a **25% window error** on a short window. Anyone who lifted windows
from that file inherited it. → **R0733**.

### Binary `min`/`max` blocks NINE alphas, not six — a correction to s12

s12 recorded the shape in `{71,73,77,88,92,96}` and `implemented_using_binary_minmax: []`. It is
actually in **`{71,73,76,77,82,87,88,92,96}`**: **76, 82 and 87 carry BOTH `IndClass` and binary
min/max**, and s12 attributed them to `IndClass` alone. The operative consequence is a claim the
desk is currently acting on: **s11's grouping map unblocks 15 of the 18 IndClass alphas, not 18** —
the other three stay blocked on an operator the desk does not have. R0730's expressibility gap is
confirmed at the primary source and is 50% larger than recorded. → **R0734**. → **R0734**.

And the reason every reimplementation diverges at exactly these nine: **the paper's own operator
table never defines a binary min/max.** It defines `min(x,d) = ts_min(x,d)`. Under the paper's own
definitions, `max(rank(...), Ts_Rank(...))` parses as a time-series window whose *length is an
expression*. The canonical source is internally inconsistent here — the ambiguity is upstream of
every port, which is why no two ports agree.

## OP-102 — GID-BLOCK RECOVERY: reading a PDF whose font subset stripped every Unicode channel

**Provenance:** BRAIN HUNTER s14, 2026-08-29, on `arXiv:1601.00991`. **SOURCE:** the file itself.
**DERIVES-FROM:** s13's per-font `/ToUnicode` binding extractor (`brain_hunter_s13_pdf_cmap_extract.py`),
whose proposed successor route (AGL glyph names) was refuted here.
**Tool:** `data/brain_hunter_s14_gid_recover.py` (pure stdlib; `--diagnose` prints the channel audit).

**WHAT IT COMPUTES.** When a PDF's embedded subset font offers no usable Unicode mapping, recover
text from the *glyph index*, which is a POSITION in the original font's glyph order and therefore
contiguous across an alphabet. Derive each block's base GID from the codes that DO carry a
`/ToUnicode` entry, requiring **≥2 mutually consistent observations** per block (one point fits any
offset). Anything still unmapped renders as a visible `<gNNNN>`.

**THE FOUR CHANNELS TO AUDIT BEFORE CONCLUDING A PDF IS UNREADABLE** — check all four, because
three of them can return a clean-looking answer that is meaningless:
1. `/ToUnicode` — may be present but PARTIAL. Count entries against `/FirstChar…/LastChar`.
2. `/Encoding /Differences` — may carry AGL names (recoverable) or `/gNNNN` glyph indices (not).
3. embedded `post` table — format 2.0 carries names; **format 3.0 carries none by design**.
4. embedded `cmap` — may be a **synthetic PUA identity** (code C → U+F000+C), which re-encodes the
   code rather than mapping it. *This is the trap*: the lookup succeeds and the answer is fiction.

**THE TWO RULES THAT MADE IT WORK, and they are not PDF-specific:**
- **NEVER RENDER A MISSING GLYPH AS `""`.** A silent drop is indistinguishable from "this cell has
  no label", so a solvable extraction gets written up as an unsolvable one. A visible placeholder
  makes the gap named, countable and anchorable (412 → 307 resolved, 105 enumerable residual).
- **WHEN THE FONT HAS NO ANCHORS, THE DOCUMENT DOES.** Prose names its own symbols immediately
  before showing them ("the annualized Sharpe ratio `<g1845>`"). Harvest anchors from captions and
  definitions, record the originating sentence as evidence, and refuse to extend a block that the
  anchors do not support — italic Greek was left un-guessed here for exactly that reason.

**MT5 ANALOGUE:** none needed — this is an extraction capability, not a market operator. It applies
to every PDF ground the desk mines: central-bank annexes, exchange contract specs, CFTC/regulator
filings, theses and conference decks, which are disproportionately the ones with subset math fonts.

**DATA THE DESK LACKS:** nothing. Pure stdlib, no install, works under the research freeze.

---

## BRAIN HUNTER s28 (2026-08-29) — THE OPERATOR SET HAS A TYPE ALGEBRA, AND THE DESK NEVER HAD IT

**Source:** `AshSwing/FastPlus` `src/operator.rs` (MIT, public, branch `dev`) — a Rust/PyO3
reimplementation of WorldQuant's Fast Expression Language. Mined as TEXT; nothing installed or
executed (supply-chain rule). Full parsed census: `data/brain_hunter_s28_operator_typespec.json`
(**108 operators parsed, exactly the count the README claims** — so the registry is complete for
Expert scope, not a sample).

**THE FIND IS NOT THE OPERATOR NAMES. IT IS THE TYPES.** The desk's catalogue records operators
as names and prose. The reimplementation had to encode what the docs assume, and it is a typed
algebra over four kinds — `Matrix` (date × symbol panel), `Vector`, `Group` (a labelling),
and constants (`PositiveInt`/`Int`/`Boolean`/`Number`) — with a hard rule: **a signal must be
Matrix-compatible.** 108 operators collapse to **14 signature classes**:

| n | signature | reading |
|--:|---|---|
| 34 | `(Matrix)->Matrix` | unary transforms |
| 25 | `(Matrix,PositiveInt)->Matrix` | the time-series family — window is a TYPE, not a number |
| 16 | `(Matrix,Matrix)->Matrix` | binary combiners |
| 9 | `(Matrix,Group)->Matrix` | **the peer-group family** |
| 8 | `(Vector)->Matrix` | vector-field reducers (no MT5 analogue, see below) |
| 6 | `(Matrix,Matrix,PositiveInt)->Matrix` | pairwise time-series |
| 2 | `(Matrix,Matrix,Group)->Matrix` | per-group neutralisation |
| 1 each | `(Group)->Group`, `(Matrix)->Group`, `(Int)->Matrix`, … | grouping constructors |

**WHY A TYPE ALGEBRA IS WORTH MORE THAN AN OPERATOR:** the desk's generator has no type
discipline, so it can emit expressions that are not bad alphas but MALFORMED, and it only finds
out by evaluating them. A parse-time type check kills those before they consume an evaluation
AND before they enter the trial count — which is the thing the desk actually pays for twice
(compute, and multiplicity). `vec_avg(rank(x))` is rejected statically because `rank` returns
Matrix and `vec_avg` demands Vector; `bucket(...)` returning Group can never be a signal.

**THE GROUPING MAP UNLOCKS FOURTEEN OPERATORS AND THE DESK BUILT TWO.** Group-consuming
operators in the registry: `densify`, `group_backfill`, `group_cartesian_product`, `group_count`,
`group_max`, `group_mean`, `group_min`, `group_neutralize`, `group_rank`, `group_scale`,
`group_std_dev`, `group_sum`, `group_vector_neut`, `group_zscore`. **`grep -rl "def <op>" libs/`
finds exactly two: `group_rank` and `group_zscore` (`libs/research/operators.py`). The other
twelve are ABSENT.** Six sessions were spent choosing which grouping arm to use; the arm now
feeds 2/14 of the operators it exists to serve. `group_neutralize` is the most consequential
absence — it is the operator the entire sector-neutralisation methodology is built on, and its
MT5 analogue (neutralise within asset-class / currency bucket / PIT correlation cluster) is
exactly the transform `docs/LAWS.md`-mandated cross-asset conditioning wants.

**29 OPERATORS THE DESK'S CATALOGUE DOES NOT NAME AT ALL** (full list + descriptions in the
artifact). The ones with an immediate MT5 analogue and no data gap:
- `ts_ir(x,d)` = `ts_mean/ts_std_dev` — a rolling information ratio as a FEATURE, not a metric.
- `ts_max_diff(x,d)` = `x - ts_max(x,d)` — distance-below-rolling-high; the drawdown-state
  feature the desk computes ad hoc in several places and has never had as an operator.
- `ts_vector_proj(x,y,d)` / `ts_vector_neut(x,y,d)` — **time-series** projection and residual.
  This is beta-hedging as an operator: neutralise a symbol's feature against a reference market
  over a rolling window. Direct MT5 use — neutralise any FX leg against DXY/gold/index state.
- `ts_co_skewness`, `ts_kurtosis`, `ts_triple_corr` — higher-moment and three-way dependence.
- `clamp`, `purify`, `pasteurize`, `nan_mask`, `is_not_finite` — the HYGIENE layer. `pasteurize`
  ("NaN if the instrument is not in the alpha universe") is the platform's own answer to the
  point-in-time universe problem, and it is an OPERATOR there, not an afterthought.
- `ts_target_tvr_hump` — tunes hump until turnover hits a TARGET. The platform treats turnover as
  a controlled quantity with a solver, not a reported diagnostic.

**NO MT5 ANALOGUE — the data-axis routing.** The 8 `(Vector)->Matrix` operators (`vec_count`,
`vec_norm`, `vec_range`, `vec_stddev`, `vec_avg`, …) presuppose a **vector field**: multiple
values per (date, symbol) — e.g. every analyst estimate for one name on one day. The MT5 book has
no such field today. It names a real axis: per-(date,symbol) multi-valued data the desk could
own — every tick in the bar, the full depth ladder, every calendar event for a currency that day.
Routed to `docs/research/data_axis_watchlist.md`.

**NOT IMPORTED (L1.6):** nothing about the platform's thresholds, fitness bar or submission
filter is taken from this repo. The type algebra is a correctness property; it has no bar.

---

## BRAIN s29 — 2026-08-29 — `efJerryYang/worldquant-brain-simulator` (GPL-3.0), mined as TEXT

s28's next-ground item 4. The brief's argument for opening a reimplementation is that *a
simulator exposes the semantics documentation elides*. It does — and on this one the loudest
semantics are the ones the simulator **advertises and then never applies**.

**THE ONE SEMANTIC THE DESK ACTUALLY NEEDED — the post-processing ORDER.** `Simulator.post_processing`
is the entire alpha→weights path and it is four lines, in this order:

1. **neutralize** — `alpha = alpha - alpha.mean()` (cross-sectional demean)
2. **truncate** — `alpha = alpha.clip(-boundary, +boundary)`, `boundary = settings["truncation"]`
3. **normalize** — `alpha = alpha / alpha.abs().sum()` (gross book = 1)

Neutralise → truncate → normalise. The desk's own cells (s28) do demean-then-gross-normalise with
no truncation step at all, so the ordering is now pinned against an independent implementation.

**BUT THE TRUNCATION IS SCALE-INHOMOGENEOUS AND THEREFORE MEANINGLESS AS WRITTEN.** The clip is
applied to the RAW alpha value, BEFORE normalisation. Alpha units are arbitrary — a `rank()` alpha
lives in [0,1], a raw-price alpha lives in the hundreds — so `truncation: 0.01` either clips
nothing (rank alpha demeaned into [−0.5,0.5]… actually clips most of it) or clips everything,
purely as a function of the expression's scale. On the platform truncation is a cap on the FINAL
weight as a fraction of book, i.e. it must come AFTER normalisation, and it must be re-normalised
afterwards or the book no longer sums to 1. **The MT5 lesson, and it is the s21 test again:
`score(k·alpha)` must equal `score(alpha)`. Any desk-side truncation/hump/cap must be applied to
normalised weights, and re-normalised, or it is a hidden function of expression scale.**

**`rank(x, rate=2)` — the platform's default rank is APPROXIMATE.** The repo quotes the official
description verbatim with its URL: rank returns floats equally distributed in [0,1], *"when rate
is set to 0, the sorting is done precisely. The default value of rate is 2."* The desk's `rank`
has no `rate` and is exact. **This matters for reading any published BRAIN result**: an alpha
tuned under bucketed ranking is not the same alpha as one tuned under exact ranking, and the
difference is largest exactly where the cross-section is thin — which is the MT5 book's normal
state (s28 measured a mean cross-section of ~140 names, against the platform's Top3000). Logged as
a FACT ABOUT THEIR PROCESS (L1.6); the desk imports no rate parameter and no bar.

**DELAY IS STRUCTURAL, NOT A SETTING.** `process_day(prev_day, today)` computes the alpha from
data up to and including `prev_day` and applies it to `today`'s returns. `delay: 1` is hardcoded
by the loop's shape; `delay: 0` is unreachable. This is the same construction s28's cells use, so
the desk's PIT convention is confirmed against an independent build.

**THE UNIVERSE OPERATOR — worth stealing, and it is free.** `filter_by_universe(prev_day)` ranks
by `cumulative_liq = rolling_90d_sum(log(volume × close))` and takes the top N **as of the
previous day**, with an 89-row per-symbol burn-in dropped and any date carrying fewer than 200
names dropped entirely. MT5 analogue exists today: `log(tick_volume × close)` summed over 90 days
per symbol, ranked PIT. BRAIN s24 already killed liquidity tier as a *grouping*; this is a
different use — a PIT UNIVERSE FILTER, not a peer group — and it is untested on the desk.

### WHAT THE SIMULATOR PARSES AND THEN THROWS AWAY (four settings, zero readers)

`settings.yaml` declares `neutralization`, `decay`, `pasteurization`, `nan-handling`. Greping the
whole repo for their readers:

| setting | read? | applied? |
|---|---|---|
| `neutralization: Market\|Sector\|Industry\|Subindustry\|None` | `by_what = settings.get(...)` assigned | **NEVER USED** — the next line demeans unconditionally |
| `decay: 30` | never read | no (`decay_linear` exists in `expression.py` as an alpha101 primitive only) |
| `pasteurization: True` | never read | no |
| `nan-handling: False` | never read | no |
| `unit-handling`, `instrument-type` | commented `# No usage` (honest) | no |

**The consequence is a hard scope limit and it must be recorded before anyone cites this repo:
this simulator cannot answer a neutralisation question.** Every setting from `None` to
`Subindustry` produces byte-identical market-neutral output. Its `docs/*_platform.png`
side-by-side comparisons against the real platform were therefore run with the platform
neutralising by sector and the local build neutralising by market, whatever the yaml said. This
is the parsed-but-unread-settings-key class (BRAIN s7): **a dead key is indistinguishable from a
live one at the call site, and here it silently voids the one axis this desk came for.**

### A SILENT WINDOW TRUNCATION — the s28 calendar bug's cousin, in someone else's code

`process_day` hands the alpha function `s.df.query("... @start_day_dt <= date <= @prev_day_dt")`
with `start_day_dt = prev_day − 60 CALENDAR days` — about **41 trading days**. Nothing checks it.
Every alpha101 expression with a window past ~41 bars (and there are many: `ts_rank(…, 250)`,
`correlation(…, 250)`, `sum(…, 220)`) returns NaN or a short-window value **with no error and no
warning**, exactly like s28's union-calendar collapse. It is the same defect class for the third
run in a row: *a window silently served fewer observations than it asked for, and the output
looked clean.* The habit that catches it is unchanged — **print `n` beside every number**, where
here `n` is the count of bars the window actually consumed.

### PROVENANCE — and a correction to the desk's own s12 finding

`expression.py` opens `# yli188's original work here: https://github.com/yli188/WorldQuant_alpha101_code`.
BRAIN s12 proved yli188's `code_2` inverts `correlation`/`covariance` at 47/47 sites. **This
descendant does NOT carry the inversion**: `correlation` returns `x.rolling(w).corr(y)` and
`covariance` returns `x.rolling(w).cov(y)`, both correct. So a public corrected fork of the
inverted file exists, and s12's finding is a property of yli188's file, never of the lineage.
SOURCE: `efJerryYang/worldquant-brain-simulator` (GPL-3.0). DERIVES-FROM: yli188 (stated by the
file itself). No third-party code was installed, executed or vendored — read as TEXT via
`raw.githubusercontent.com`.

**NOT IMPORTED (L1.6):** no threshold, no fitness bar, no booksize, no submission filter.
`booksize = 20_000_000  # should not change` is a fact about their harness and nothing else.

### BRAIN s29 (2026-08-29) — `rank(x, rate)` granularity, and the post-processing order

Source: `efJerryYang/worldquant-brain-simulator` (GPL-3.0), `src/alpha_pool/expression.py:154`
and `src/simulator/simulate.py:252-264`. Mined as TEXT; nothing installed or vendored.

- **`rank(x, rate=2)`** — the platform's own description, quoted verbatim in that file: ranks x
  among all instruments returning floats **equally distributed on [0.0, 1.0]**; `rate=0` sorts
  precisely, and **the default is rate=2, i.e. deliberately imprecise**. MT5 analogue: bucketed
  cross-sectional rank, `ceil(pct * B) / B`. **MEASURED AND REFUTED as a turnover lever**
  (`data/brain_hunter_s29b_coarse_rank.json`): precise → 3 buckets moves daily turnover 1.467 →
  1.452 on `reversal_1|ward_k24`, non-monotone, effect size indistinguishable from noise on all
  three cells tried. Retained as a documented operator, **not** as a cost lever — the family's
  turnover is set by the feature's autocorrelation, not by ranking granularity.
- **Checked null, recorded so nobody re-derives it:** the platform's `(rank−1)/(n−1)` and the desk's
  `rank(pct=True)` = `rank/n` are affine transforms of one another. Demeaning removes the offset and
  gross-normalisation removes the scale, so the resulting weights are **identical**. No change owed.
- **Post-processing ORDER: neutralise → truncate → normalise.** The desk's cells currently do
  demean → gross-normalise with **no truncation stage**. Flagged as a **spec question, not a spec**:
  this implementation clips in raw-alpha units *before* normalising, which is not the same as
  bounding a normalised weight, and clip-then-renormalise is not idempotent. The author's own hidden
  README TODO reads *"Truncation correctness (current not necessarily working)"*. A per-name weight
  cap is worth testing on desk cells on its own merits (concentration control), but this source
  cannot settle what the platform actually does.
- **Do not read this simulator's `settings.yaml` as the platform's parameter list.**
  `neutralization` is read into a variable that is never used (`simulate.py:257`) — all four modes
  silently execute market neutralisation — and `decay`, `delay`, `pasteurization`, `nan-handling`
  and `unit-handling` appear in no `settings.get` call at all. Six of twelve settings are inert.

---

## BRAIN HUNTER s30 (2026-08-29) — three findings inside an artifact s28 had already exhausted

**FIRST, THE DEFECT, AND IT IS MINE.** s28 marked `AshSwing/FastPlus` `src/operator.rs`
**"fully parsed, 108/108"** in the exhaustion list, with the census committed as
`data/brain_hunter_s28_operator_typespec.json`. This session re-fetched and re-parsed the same
file from scratch before reading that line, and produced a strictly *worse* duplicate (no kwarg
defaults, no variadic arity). The duplicate artifact has been **deleted**; s28's typespec remains
the desk's operator registry. The exhaustion list did its job and I failed to read it first —
recorded because the whole point of a dated exhaustion claim is that the next session does not
re-spend on it, and the claim is only as good as the habit of reading it before fetching.

Everything below is what re-reading the same file surfaced that s28's note did **not** carry.
Source unchanged: `AshSwing/FastPlus` (MIT, 4★, pushed 2026-08-13), read as TEXT over
raw.githubusercontent; nothing installed, executed or vendored. §13 clean. **CLAIMED, not
verified** — the descriptions are the platform's documentation as transcribed by that author, and
nothing here has been run on desk data.

### 1. `Group` is a PRODUCED type — the grouping is manufactured, never sourced
s28 counted the 14 group-**consuming** operators and concluded the desk needs a grouping map.
It did not report the other side of the type algebra: **three operators RETURN `Group`.**

**And the data was already on disk.** `data/brain_hunter_s28_operator_typespec.json` records
`(Matrix)->Group` and `(Group,Group)->Group` among its fourteen signature classes. s28 captured
the fact and did not read it; this session re-fetched the source to rediscover something the
desk's own artifact already held. That is the owned-data breach in miniature — the re-fetch was
waste, but the *unread artifact* was the more expensive of the two, and it went unnoticed for a
session because the census was reported as a count rather than interrogated as a structure.

- **`bucket(x, range=…|buckets=…, skipBoth=, NaNGroup=) → Group`** — converts **any numeric
  field** into a grouping by ranking to [0,1] and cutting into buckets. The registry's own
  description ends with the platform's documented idiom, verbatim: *"most common usage is
  `bucket(rank(x), range='0,1,0.1')`"*. Hidden `(-inf,start]` / `[end,+inf)` buckets by default;
  `NaNGroup=True` gives NaNs their own bucket instead of dropping them.
- **`group_cartesian_product(g1, g2) → Group`** — cross two groupings into `len_1 × len_2` cells.
- **`densify(g) → Group`** — collapse a many-bucket grouping to only its occupied buckets.

**Consequence, and it is six sessions wide.** s11–s28 treated the missing grouping as a
**data-acquisition** problem: hunt a taxonomy, build ward clusters, argue about k for four
sessions. The platform's canonical route sources no taxonomy at all — it builds the grouping from
a numeric field you already own, per bar, **PIT by construction** (unlike the year-lagged ward
clusters). On MT5 that needs nothing new: `bucket(rank(ts_std_dev(ret,60)))` is a volatility tier,
`bucket(rank(ADV))` a liquidity tier, `bucket(rank(ts_corr(ret, XAUUSD, 120)))` a gold-beta tier.
Routed as an axis to `data_axis_watchlist.md`; **named as s31's first ground**; **untested**.

### 2. The turnover family is a SOLVER, not a grid — and turnover is this desk's binding constraint
s28 listed `ts_target_tvr_hump` among "operators not named in the desk catalogue" and moved on.
Reading the descriptions, there are **six** operators aimed at turnover and **three of them invert
the problem** — you state the turnover you want and they solve for the smoothing parameter,
optimising λ inside a stated `lambda_min, lambda_max`:

| operator | what it computes |
|---|---|
| `ts_decay_linear(x, d, dense=)` | linear-weighted MA over the last d values |
| `hump(x, hump=)` | limits the amount **and magnitude** of change in the input |
| `jump_decay(x, d, stddev=, sensitivity=, force=)` | `abs(x−ts_delay(x,1)) > sensitivity·ts_stddev(x,d) ? ts_delay(x,1)+ts_delta(x,1)·force : x` — a vol-scaled **gap filter**: a jump bigger than the threshold is only partially followed |
| `ts_target_tvr_decay(x, target_tvr=, lambda_min=, lambda_max=)` | tunes the decay so **realised turnover equals a target** |
| `ts_target_tvr_hump(...)` | same, solving for the hump threshold |
| `ts_target_tvr_delta_limit(x, y, ...)` | same, solving a delta limit; `y` may be `adv20`/volume **or a constant** |

All six have direct MT5 analogues and need no grouping and no new data. `jump_decay` is the
pointed one: an MT5 book takes weekend and session gaps that this operator exists to absorb, and
the desk has no equivalent. Methodology consequence routed to `improvement_inbox.md`.

### 3. The desk implements SIX of 108 — across TWO modules, three of them implemented twice
**Corrected mid-session, and the correction is the finding.** My first pass counted 4 by treating
`libs/alpha_factory/wq_operators.py` as the desk's only WQ operator module. It is not: a second
module, **`libs/research/operators.py`**, implements `group_rank`, `group_zscore`, `vector_neut`,
`ts_backfill` and `ts_information_ratio` (= the registry's `ts_ir`). I found it only because a
sibling session's abandoned script quoted it. The true union is **6 of 108 (5.6%)**:

| operator | `libs/alpha_factory/wq_operators.py` | `libs/research/operators.py` |
|---|---|---|
| `group_rank` | ✔ | ✔ |
| `group_zscore` | ✔ | ✔ |
| `ts_backfill` | ✔ | ✔ |
| `trade_when` | ✔ | — |
| `vector_neut` | — | ✔ |
| `ts_ir` (as `ts_information_ratio`) | — | ✔ |

**Two defects fall out of that table.** (1) **Three operators are implemented twice, in two
modules, with no shared source** — two independent definitions of `group_rank` that no test
compares, which is a divergence waiting to be discovered as an unexplained result difference
between two cells. (2) **`vector_neut` is implemented and has never been consumed by a
hypothesis**, while three consecutive session notes (s28, s29, s30) carried it forward as an
un-built "next ground". A capability that exists but is invisible to the seats that need it is
the III.16 shape, and it cost this ground three sessions of misdirected priority.

**The measurement trap, recorded because it is what produced my wrong number.** A `def <name>`
grep across `libs/` and `desks/` returns 14 matches. Nine — `add`, `log`, `or`, `quantile`,
`rank`, `reverse`, `scale`, `sign`, `bucket` — are **name collisions with unrelated desk
functions**; `vector_neut` and `ts_information_ratio` are **real and were nearly discarded as
collisions**. So the naive grep is wrong in *both* directions at once: it over-counts by 9 and,
once you start pruning collisions by eye, it invites you to prune the true positives too. The only
reliable method is to enumerate the modules that exist, which is what the table above does.

### Still not buildable under this seat
This seat is research-frozen (docs/research + data only). Every operator above is a `libs/` change
and is named here as a **specification**, not as work done.
`data/brain_hunter_s28_operator_typespec.json` is the machine-readable input for a seat that can
write code. `group_neutralize`, `ts_vector_proj`/`ts_vector_neut` and `ts_regression(rettype 0–9)`
remain genuinely absent. **`vector_neut` does NOT** — it is implemented in
`libs/research/operators.py` and has simply never been consumed; carrying it as an un-built
"next ground" for three sessions was an error of inventory, not of capability, and the correct
next step for it is a HYPOTHESIS, not a build.

### 4. Operator shapes the BRAIN registry does NOT contain — `GaomingOrion/qweave` (MIT), read as TEXT

qweave is a **computation engine**, not a parser, so its AST is a claim about semantics rather
than signatures. Its expression enum (`crates/qweave-core/src/expr.rs`) carries several shapes
absent from the 108-operator BRAIN Expert registry:

- **`Sma(x, n, m)` — the Chinese recursive smoother.** Confirmed from the repo's own docs
  (`docs/gtja_alpha191.md`): *"`SMA(A,n,m)` 使用递归平滑系数 `m/n`"* — an EWMA with smoothing
  coefficient **m/n**, not a moving average. This is the signature operator of the CN factor
  libraries and BRAIN has no equivalent.
- **`Wma(x, n)` with `0.9^i` weights** — same doc: the GTJA research report's own definition is
  **geometric**, not linear. BRAIN's `ts_decay_linear` uses linear weights d, d−1, …, 1. Two
  different kernels on the same axis, and the desk has now measured only one of them.
- **`ConditionalBeta`** — beta estimated conditional on a state. No BRAIN analogue; `ts_regression`
  is unconditional.
- **`Resi` / `MultiResi` / `RollingBeta` / `Slope` / `Rsquare`** — regression residuals and
  diagnostics as first-class nodes (BRAIN folds these into `ts_regression(rettype 0–9)`).
- **`ScanMul`** — an *expanding* cumulative product; BRAIN's `ts_product` is windowed.

**The immediate consequence for s30c's refutation, and it is a pre-registerable follow-up.** s30c
refuted **linear** decay as a cost lever on `reversal_1`, and the mechanism of the refutation was
that smoothing deletes signal faster than it deletes turnover, because a one-day reversal's
information is concentrated in the most recent bar. That mechanism makes a **directional
prediction about other kernels**: a kernel that concentrates more weight on the newest bar should
lose less signal per unit of turnover reduction than linear decay did. `Sma(x, n, m)` (EWMA, tuned
by m/n) and `Wma` at `0.9^i` are exactly that, and the desk has neither.

**Declare the sign before running it** (s29's rule, and it is the whole point of writing it here
rather than after): at a **matched turnover reduction**, EWMA/geometric smoothing loses **less**
gross Sharpe than linear decay. If it loses the same or more, the kernel axis is closed and the
family's cost problem is confirmed as kernel-independent — which would be the stronger and more
useful result of the two.

---

## BRAIN HUNTER s31 (2026-08-29) — the eval kernel, not the AST: exact arithmetic for five operators s30 could only name

s30 read `crates/qweave-core/src/expr.rs` and marked the artifact "AST fully enumerated". An AST
node is a **name and an arity**; it is not semantics. s30's `Sma` entry therefore rested on one
sentence of the repo's own Chinese documentation (`使用递归平滑系数 m/n`), which is a paraphrase of
the GTJA report, not the code. This session read `crates/qweave-core/src/alpha_eval.rs` (86 KB,
never opened by any session) and `crates/qweave-factors/src/qlib_alpha158.rs`, both MIT, both as
TEXT. The shapes s30 named are confirmed; the arithmetic below is new, and two of the four calibers
would have produced a wrong implementation if taken from the AST alone.

### `Sma(x, n, m)` — EWMA at α = m/n, **and the state resets to NaN on any gap**

```
alpha = m / n                         # guard: NaN everywhere if n == 0 or m > n
state = alpha*value + (1-alpha)*state   if value is finite and state is finite
state = value                           if value is finite and state is NaN  (seeds on first obs)
state = NaN                             if value is NOT finite               (RESETS)
```

**The caliber that matters on this desk and appears nowhere in the docs: a single non-finite input
DESTROYS the accumulator, it does not skip the bar.** A conventional `ewm(adjust=False)` carries
its state across a missing observation. On the desk's MT5 tape — holidays, per-symbol calendars,
the union-index NaNs that silently ate 89% of the cross-section in s28 — those two conventions are
materially different operators wearing one name, and the difference grows with window length.
Any desk implementation must choose the convention **explicitly and say which**.

### `Wma(x, n)` — geometric weights, and the direction is the opposite of the naive read

```
w_oldest = 0.9^(n-1) ... w_newest = 0.9^0 = 1     # weight /= 0.9 walking forward
result   = sum(w_i * x_i) / sum(w_i)              # normalised, so it is a weighted MEAN
```

`0.9^i` is ambiguous until you see the loop: the **newest** bar carries the largest weight and the
decay runs backwards in time. It is also **normalised**, where BRAIN's `ts_decay_linear` is
conventionally a weighted sum. A desk implementation copying "0.9^i" from s30's note without the
loop direction would build the time-reversed operator and get a result that is not wrong-looking.

### `ConditionalBeta(y, x, cond, n)` — the conditioning shape with no BRAIN analogue, exactly

```
over the trailing n bars, keep index i iff cond[i] == 1.0 AND y[i], x[i] both finite
if fewer than 2 survive -> NaN
else -> OLS beta on the SURVIVING SUBSET
```

Note the two calibers: the condition is compared to `1.0` **exactly** (it is a boolean-valued
expression, not a truthiness test), and the estimator uses a **variable sample size** — the window
is n bars but the regression may be fit on 2. That is an unadvertised power problem, and any desk
use needs a minimum-sample guard the source does not have.

### `Slope(x, n)` / `Rsquare(x, n)` / `Resi(x, n)` — regression against the TIME INDEX

Unary, so the regressor is the bar index, not another series. These are the rolling trend-strength
diagnostics: slope of the fitted line, its R², and the residual of the newest bar.

**A CORRECTION TO THIS SESSION'S OWN FIRST DRAFT, and the correction is the better finding.** The
draft said the desk has no rolling-regression operator of any kind, on the evidence that
`libs/research/operators.py` and `libs/alpha_factory/wq_operators.py` expose eight public functions
between them (`group_rank`, `group_zscore`, `vector_neut`, `trade_when`, `ts_backfill`,
`ts_information_ratio`, `fitness`, `_as_panel`) and not one is a regression. That is true of those
two files and false of the desk. **`libs/ict/cross_sectional.py` has carried
`rolling_beta(sym, idx, window)` and `residualise(sym_ret, idx_ret, beta)` the whole time**, and
neither operator module references either, nor did any of the thirty-one operator censuses this
seat has written. Searching the operator layer and reporting its emptiness as the desk's inventory
is the same defect shape as an empty collector artifact asserting absence: **I searched where the
answer was supposed to live, not where it was.** The standing repair is one grep across `libs/`
rather than across the two files whose names contain "operator".

The precise gap, restated: `rolling_beta` is **bivariate** (a symbol against an index). There is no
**unary** regression against the time index anywhere on the desk, hence no trend-QUALITY measure of
any kind. `Rsquare` remains the highest-value item of the seven — it separates "moved a lot" from
"moved monotonically", precisely the distinction every momentum feature in s28/s31 cannot make —
and its absence is now established against the whole tree, not against two files.

### `Quantile(x, n, q)` — rolling quantile, and s30's list omitted it

Also present, also absent from the desk. Named here for completeness; it is the cheapest of the
six to implement and the one with the weakest mechanism story.

### The corpus find: `qlib_alpha158.rs` — a FOURTH factor library on this ground, never named

Twenty-three sessions of coverage on the BRAIN ground name alpha101, GTJA alpha191 and the BRAIN
operator registry. The same repo carries **Microsoft Qlib's Alpha158** (9 kbar + 4 price + 29
rolling groups × 5 windows ∈ {5,10,20,30,60}), and it is the only one of the three whose factors
are **entirely per-symbol time-series with no cross-section at all** — which makes it the single
most MT5-transferable of the three libraries, because it needs no grouping map, no universe and no
peer set. Every blocker six sessions argued about (s24–s27, and s31's own bucket work) is
irrelevant to it. The file's own header also documents two calibration divergences from upstream
qlib (`min_periods=1` vs full-window; 0- vs 1-based `IdxMax`), which is a reimplementation telling
you where it disagrees with its source — the highest-value kind of README line.

**Routing:** Alpha158 is logged as the next-ground item, NOT as a claim. The prior on published
factor libraries measured on this desk is bad and stated in `prospector_watchlist.md`
(alpha101 median Sharpe 0.518 on independent audit, s28). What is different here is the *shape*,
not the expected return: a library with no cross-sectional dependency is testable on the desk's
tape without settling any of the grouping questions.

### Boundary

Public MIT source, `raw.githubusercontent.com` and the public contents API, no auth, no wall
touched, nothing installed or executed (supply-chain rule: mined as TEXT).

### Artifacts exhausted this session (do not re-surface-scan)

`GaomingOrion/qweave`: `crates/qweave-core/src/alpha_eval.rs` — the six kernels above read in
full; the remainder is the cross-sectional and arithmetic node set already covered by s28.
`crates/qweave-core/src/alpha.rs` (constructor signatures, complete).
`crates/qweave-factors/src/gtja_alpha191.rs` — **censused for OPERATORS, which was the assigned
task, and it is now closed on that axis**: the 191 formulas use exactly the vocabulary
{`delay` 294, `rank` 139, `ts_sum` 134, `abs`, `ts_mean`, `sma` 82, `where_` 77, `correlation` 55,
`decay_linear` 33, `delta`, `ts_rank`, `ts_min`/`max`, `power`, `ts_std`, `wma` 2, `slope` 3,
`ts_argmin`/`argmax`, `covariance`, plus the CN directional primitives `tr`/`hd`/`ld`/`dtm`/`dbm`}.
**There is no conditioning shape in the 191 that is not already in alpha101 or in the six kernels
above** — the library's distinctiveness is its *fields* (`amount`, `vwap`, `volume`) and its
recursive smoother, not its operator algebra. That is a negative result and it closes item 4 of
s30's next-ground list.

---

## BRAIN HUNTER s32 (2026-08-30) — Alpha158 formulas, reciprocal conventions, and near-duplicate columns

Source: public MIT `GaomingOrion/qweave`, branch `master`,
`crates/qweave-factors/src/qlib_alpha158.rs`, read as text and checked against the repository's
public documentation. The file expands 29 rolling groups over `[5, 10, 20, 30, 60]` and contains
no group/fundamental inputs.

### Exact implementation calibers

- Level-valued rolling groups divide by the **current close**: `MA`, `STD`, `BETA`, `RESI`,
  `MAX`, `MIN`, `QTLU`, `QTLD`; `RSQR` is already unitless. In particular,
  `BETA = slope(close,d)/close`, so a raw slope port would make a multi-asset cross-section mostly
  a price-level comparison.
- `ROC = delay(close,d)/close`, the reciprocal of the usual `close/delay(close,d)`. A
  cross-sectional rank is therefore reversed relative to the conventional implementation.
- `VMA` and `VSTD` divide a rolling volume statistic by the **current** volume. They use the
  opposite orientation from the price-level groups: a low current bar raises the ratio.

### The honest redundancy result: near-affine away from all-flat windows, not exact

Let `P=sum(max(delta,0))`, `N=sum(max(-delta,0))`, `D=P+N`, and `Q=D+eps`. The source computes
`SUMP=P/Q`, `SUMN=N/Q`, and `SUMD=(P-N)/Q`. Therefore `SUMD = SUMP-SUMN` exactly, while
`SUMP+SUMN=D/(D+eps)` — **not exactly one**. When `D` is ordinary-sized the three are numerically
near-affine; when the whole window is flat they all collapse to zero. The same holds for
`VSUMP/VSUMN/VSUMD`.

Across five windows, 20 named columns (`SUMN`, `SUMD`, `VSUMN`, `VSUMD`) are consequently
near-duplicates of their `*SUMP` sibling on active windows, but the epsilon/all-flat behavior is a
real exception and must not be erased as “exact redundancy.” A feature-selection or trial-count
audit should measure the exceptions on Fusion bars rather than assume either independence or
identity.

The count family carries a different result: `CNTD = CNTP-CNTN`, but `CNTP+CNTN < 1` whenever
closes tie because a flat bar contributes to neither side. That makes tie density/stale-bar rate a
separate MT5-native liquidity and data-quality axis.

### MT5 mapping and verification asset

Price-only families map directly to Fusion OHLC. MT5 `volume` is broker tick count, not traded
size, and CFD `vwap` is absent; all 40 columns in the eight volume groups plus `VWAP0` therefore
require an explicit substitution hypothesis or a named data gap, never a silent rename.

The repository commits `golden_qlib_alpha158.parquet`, `golden_alphas.parquet`, and
`golden_gtja_alpha191.parquet` under `crates/qweave-factors/tests/fixtures/`. These are free,
independent expected-output fixtures for any desk port. The source also documents a warm-up
caliber: qweave requires a full non-NaN window where upstream Qlib uses `min_periods=1`.

---

## BRAIN HUNTER s39 (2026-08-30) — three price-only distribution/state transforms from `alpha-gauntlet`

Source: public MIT `openclaw-pza/alpha-gauntlet` at
`c05298cb966e655a5efcf689468371365f6fbcc3`, read as text only. `NOTICE` declares derivation from
QuantaAlpha (MIT) for its extended WQ operator/DSL/re-skin layer and from Kakushadze's public
Alpha101 paper for formulas. The three shapes below live outside that formula layer and are exact
code semantics, not copied performance claims.

### `downside_var_ratio_168h` — realised downside semivariance share

For H1 close (C_t), set (r_t=\Delta\log C_t). Over the trailing 168 observed bars, with at
least 120 present:

```
sum(min(r, 0)^2) / (sum(r^2) + 1e-12)
```

It computes the fraction of realised variance carried by negative returns, bounded near [0,1].
The source attaches a rebound intuition; that sign is ore and is **not** imported.

**MT5 analogue:** compute from PIT H1 `close` on every currently tradable terminal-enumerated
Fusion symbol, then rank only symbols with a bar genuinely available at the common decision time.
Do not forward-fill a closed share/soft session into a fresh FX/index cross-section. No new data is
needed. `translate_to_mt5("downside semivariance share")` currently returns `[]`; this explicit
mapping is therefore a documentation-level extension under the research freeze, not a hidden
fallback to another venue.

### `tail_ratio_168h` — non-parametric return-tail asymmetry

Over 168 simple H1 returns, with at least 120 present:

```
rolling_quantile(return, 0.95) / (abs(rolling_quantile(return, 0.05)) + 1e-12)
```

It compares positive and negative realised tail sizes without fitting a distribution. The source's
"lottery-like overpriced" direction is explicitly refused: the operator computes shape; the Fusion
gauntlet must learn whether either sign pays.

**MT5 analogue:** same terminal-enumerated H1 ground and PIT mixed-calendar rule as semivariance.
The input is only `time, close, symbol-session availability`; no volume substitute is involved.
`translate_to_mt5("tail ratio")` returns `[]`, so the mapping is recorded here rather than
fabricated by the function.

### `ou_rev_press` — deviation multiplied by relative mean-reversion speed

Over a right-aligned 168-bar window, source arithmetic is:

```
logp  = log(close)
mu    = rolling_mean(logp, 168)
y     = logp - mu
b     = rolling_cov(diff(y), lag(y), 168) / rolling_var(lag(y), 168)
theta = -log(1+b) for -1 < b < 0; 0 for b >= 0; NaN for b <= -1
z     = (logp-mu) / rolling_std(logp, 168)
score = -tanh(z) * sqrt(clip(theta / rolling_median(theta, 168), 0, 5))
```

This is a **relative pressure score**, not an OU half-life estimate: the source itself records
small-sample upward bias in theta. Trending states mute to zero; oscillatory-divergent estimates
become missing rather than fake super-fast reversion.

**MT5 analogue:** H1 price-only state per terminal-enumerated Fusion symbol, optionally ranked at
the same PIT common decision time. `translate_to_mt5("OU reversion pressure")` returns `[]`; no
data gap exists for the transform, but its sign and horizon remain unmeasured. Source comments
claim positive h1/h4/h24 t-statistics; those are external ore with no accepted result cells here.

### One cost door, one policy door

Any future construction must declare each target horizon as a counted trial and charge fresh
symbol-native spread, commission, realised slippage/partial-fill markout and rollover swap. The
current registry demonstrates why no common scalar is valid: at read time EURUSD spread was 1
point with swaps -7.16/+3.04, US500 spread 36 with swaps -5.90/+1.54, and XAUUSD spread 20
(realised-fill median 14.5) with swaps -67.06/+32.75. Those are consumption-time examples, not
frozen backtest inputs.

The repository's Bonferroni candidate-count threshold and attempt-inflated champion ratchet are
**not imported**. They would add private gates before/around the canonical ten; L1.60 allows the
operator language to expand and reserves every verdict for the one canonical pipeline. Evidence:
`data/brain_hunter_s39_alpha_gauntlet_operator_screen.json`. Three operator specifications, zero
desk constructions, zero target-horizon cells, zero survivors.
