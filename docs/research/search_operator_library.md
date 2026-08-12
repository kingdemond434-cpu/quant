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
