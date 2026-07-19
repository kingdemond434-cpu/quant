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

## ARCHIVED
(none yet)
