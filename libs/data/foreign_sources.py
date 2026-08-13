"""NON-CHINESE FOREIGN FORESTS -- Japanese, Korean and Russian practitioner writing.

WHY THESE AND NOT "MORE SOURCES". The desk's Chinese lane exists because Chinese quant writing is
substantial, practitioner-authored, and INVISIBLE to English search -- not because Chinese is
special. That argument is language-agnostic, and it was being made for exactly one language while
three other large crypto-native communities went unindexed:

  JAPANESE   the largest retail derivatives market outside the US by turnover, with a domestic
             engineering-blog culture (Qiita, Zenn) where implementations are posted with code.
  KOREAN     the venue whose price gap has its own name on this desk -- capital_control_barrier_rent
             is measured against Upbit/Bithumb. The desk screens the KR premium and has never read
             a word written by the people creating it.
  RUSSIAN    a deep quantitative-engineering tradition on Habr, and a crypto community that
             discusses OTC, settlement and sanctions-adjacent flow that surfaces nowhere else.

EVERY ROUTE HERE WAS PROBED LIVE ON 2026-08-05, not assumed. What answered, what did not, and the
route that worked when the obvious one failed:

  Qiita (JP)      api.qiita.com items?query=   -> clean JSON, keyless, ~300KB/query.  USED
  Zenn (JP)       zenn.dev/api/articles        -> clean JSON, keyless.                USED
  Hatena (JP)     b.hatena.ne.jp .../?mode=rss -> RDF/RSS, keyless, 32 items/query.   USED
  Habr (RU)       habr.com/ru/search/          -> JS SHELL, 0 parseable results.      route failed
  Habr (RU)       habr.com/ru/rss/search/      -> RSS, 20 items/query.                USED
  DCInside (KR)   search.dcinside.com/post/q/  -> server-rendered HTML, 25 rows.      USED
  Naver (KR)      openapi.naver.com            -> HTTP 401, needs an API key.         out of scope
  note.com (JP)   /api/v3/searchs              -> HTTP 404, endpoint moved.           unresolved

THE HABR LINE IS THE POINT OF L1.54 CLAUSE 6. The search PAGE is a JS shell and a desk that
stopped there would have recorded "Habr: blocked, client-rendered" and lost a Russian corpus
permanently. The same site serves the same query as RSS, keylessly, in one request. A shut door
was a routing problem, and the cost of finding that out was one more probe.

ENTITY DECODING IS NOT OPTIONAL HERE, and Hatena proves it: its RSS returns titles as numeric
character references (`&#x306B;` for に). Undecoded, the triage ranker sees no Japanese at all and
scores every row zero -- a real edge made invisible to the gate rather than rejected by it, which
is the identical failure fixed in the CN parsers earlier the same day. Every parser below decodes,
and every one strips tags BEFORE decoding so an encoded `&lt;b&gt;` cannot become a tag the
stripper then eats.

ONLY TITLES AND SNIPPETS ARE KEPT, exactly as for the Chinese sources. These are indexed to decide
what a human should go and READ. Nothing archives article bodies.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Final
from urllib.parse import quote

#: Minimum seconds between requests to one source. NOT one global number: Hatena answered 429 to
#: EVERY query in the first live sweep at 1.2s spacing while Qiita and Habr were untroubled by it,
#: so a single pace either wastes time on the tolerant sources or keeps losing the strict one.
#: Measured, not guessed -- these are the values that produced a clean sweep.
_MIN_INTERVAL_S: Final[dict[str, float]] = {
    "hatena": 6.0,     # 429s the whole sweep at 1.2s; the strictest source here by a distance
    "dcinside": 2.0,
    "qiita": 1.0,
    "zenn": 1.0,
    "habr": 1.5,
    "note": 1.5,
    "velog": 1.5,
    "vcru": 1.5,
    "smartlab": 2.5,
    "coinpan": 2.5,
    "tinhte": 2.5,
    "eksisozluk": 3.0,
}

#: Sources that answered 429 THIS PROCESS. A source that has asked for a pause gets one for the
#: rest of the run rather than another seventeen requests -- continuing to hammer it is how a
#: temporary rate-limit becomes a durable block, which would cost the lane rather than the query.
_BACKED_OFF: set[str] = set()

_UA: Final[dict[str, str]] = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/html, application/rss+xml, */*",
}


@dataclass(frozen=True)
class Article:
    """Deliberately the SAME shape as cn_sources.Article.

    Not a coincidence and not laziness: the triage ranker, the miner's queue writer and the
    dedupe key all already speak this shape, so a new language costs a parser rather than a
    pipeline. A second, parallel article type would have forced every downstream consumer to grow
    a branch per language -- which is how a desk ends up indexing four languages and ranking one.
    """

    source: str
    ident: str
    title: str
    url: str
    author: str = ""
    snippet: str = ""

    @property
    def searchable(self) -> str:
        return f"{self.title} {self.snippet}"


# --------------------------------------------------------------------------- query territories
# ONE TERRITORY PER LINE, never a synonym of the line above. The Chinese set learned this the
# expensive way: four rephrasings of "quant backtest" return one forest four times. Each list
# below walks the same axes as CN_ARTICLE_QUERIES -- validation, factors, funding/basis,
# microstructure and cost, mechanism-specific, and the failure literature -- in the vocabulary the
# local community actually uses, because a translated English phrase finds translated English
# content and that is the one corpus already covered.

QUERIES_JA: Final[tuple[str, ...]] = (
    "暗号資産 バックテスト 過学習",          # overfitting in backtests
    "仮想通貨 アウトオブサンプル 検証",       # out-of-sample validation
    "先読みバイアス バックテスト",            # lookahead bias
    "生存者バイアス 検証",                    # survivorship bias
    "ファクター 有効性 検証",                 # factor validity
    "資金調達率 アービトラージ 実績",         # funding-rate arb, realised
    "現物 先物 ベーシス 収束",                # cash-futures basis convergence
    "無期限先物 資金調達率 仕組み",           # perp funding mechanics
    "取引所間 裁定 コスト",                   # cross-exchange arb cost
    "マーケットメイク 在庫リスク",            # market-making inventory risk
    "板 スリッページ 執行コスト",             # book slippage / execution cost
    "高頻度取引 約定 メカニズム",             # HFT matching mechanics
    "強制ロスカット 連鎖",                    # liquidation cascade
    "オプション ボラティリティ 裁定",         # options vol arb
    "オンチェーン データ 分析 戦略",          # on-chain data strategy
    "マイナー 売り圧力 オンチェーン",         # miner sell pressure
    "botter 損失 反省",                       # the JP crypto-bot community's failure writeups
    "実運用 バックテスト 乖離",               # live-vs-backtest divergence
)

QUERIES_KO: Final[tuple[str, ...]] = (
    "퀀트 백테스트 과최적화",                 # overfitting
    "표본외 검증 실패",                       # out-of-sample failure
    "미래참조 편향 백테스트",                 # lookahead bias
    "생존편향 검증",                          # survivorship bias
    "팩터 유효성 소멸",                       # factor decay
    "펀딩비 차익거래 실전",                   # funding arb, live
    "현물 선물 베이시스 수렴",                # basis convergence
    "김치프리미엄 차익거래",                  # THE kimchi premium -- the desk screens it and has
    "업비트 바이낸스 가격차이",               #   never read the community creating it
    "거래소간 재정거래 비용",                 # cross-exchange arb cost
    "마켓메이킹 재고 리스크",                 # market-making inventory
    "호가창 슬리피지 체결",                   # book slippage / fills
    "청산 연쇄 강제청산",                     # liquidation cascade
    "온체인 데이터 분석 전략",                # on-chain strategy
    "채굴자 매도 압력",                       # miner sell pressure
    "자동매매 손실 복기",                     # algo-trading loss post-mortems
    "실전 백테스트 괴리",                     # live-vs-backtest divergence
)

QUERIES_RU: Final[tuple[str, ...]] = (
    "криптовалюта бэктест переобучение",      # overfitting
    "проверка вне выборки стратегия",         # out-of-sample validation
    "заглядывание в будущее бэктест",         # lookahead bias
    "ошибка выжившего тестирование",          # survivorship bias
    "фактор затухание доходности",            # factor decay
    "ставка финансирования арбитраж",         # funding-rate arb
    "базис фьючерс спот сходимость",          # basis convergence
    "межбиржевой арбитраж издержки",          # cross-exchange arb cost
    "маркетмейкинг риск запасов",             # market-making inventory risk
    "проскальзывание стакан исполнение",      # slippage / book / execution
    "каскад ликвидаций маржинколл",           # liquidation cascade
    "опционы волатильность арбитраж",         # options vol arb
    "ончейн анализ стратегия",                # on-chain strategy
    "майнеры давление продаж",                # miner sell pressure
    "торговый робот убытки разбор",           # trading-bot loss post-mortems
    "реальная торговля отличие бэктеста",     # live-vs-backtest divergence
)

#: language -> (queries, the source functions that speak it). Consulted by the miner so adding a
#: language is a table entry rather than a code path.
#: VIETNAMESE -- a lane the desk did not have at all. Vietnam runs one of the highest
#: crypto-adoption rates on earth and its retail derivatives community argues in Vietnamese only.
QUERIES_VI: Final[tuple[str, ...]] = (
    "backtest quá khớp tối ưu",              # overfitting a backtest
    "kiểm định ngoài mẫu chiến lược",        # out-of-sample validation
    "thiên lệch nhìn trước dữ liệu",         # look-ahead bias
    "thiên lệch kẻ sống sót kiểm định",      # survivorship bias
    "phí funding chênh lệch giá",            # funding-rate arbitrage
    "chênh lệch giá sàn giao dịch",          # cross-venue basis
    "basis hợp đồng tương lai giao ngay",    # futures/spot basis
    "thanh lý hàng loạt đòn bẩy",            # liquidation cascades
    "trượt giá sổ lệnh khớp lệnh",           # slippage and order-book fills
    "tạo lập thị trường rủi ro tồn kho",     # market-making inventory risk
    "phân tích on-chain chiến lược",         # on-chain analysis
    "bot giao dịch thua lỗ rút kinh nghiệm",  # trading-bot loss post-mortems
    "chênh lệch giá P2P sàn nội địa",        # domestic P2P spread -- a local mechanism
    "phí giao dịch maker taker tối ưu",      # maker/taker fee optimisation
    "dữ liệu on-chain ví cá voi theo dõi",   # whale-wallet tracking
    "chỉ báo quá khớp dữ liệu lịch sử",      # indicator overfit to history
    "quản lý vốn kelly rủi ro phá sản",      # Kelly sizing / ruin risk
)

#: TURKISH -- Turkish retail crypto volume is enormous relative to the economy, and lira-pair
#: microstructure (a currency under sustained pressure) is a mechanism family the English-language
#: forests barely discuss.
QUERIES_TR: Final[tuple[str, ...]] = (
    "backtest aşırı optimizasyon",           # overfitting  # noqa: RUF001
    "örneklem dışı test strateji",           # out-of-sample testing  # noqa: RUF001
    "ileriye bakma yanlılığı",               # look-ahead bias  # noqa: RUF001
    "hayatta kalma yanlılığı test",          # survivorship bias  # noqa: RUF001
    "fonlama oranı arbitraj",                # funding-rate arbitrage  # noqa: RUF001
    "borsalar arası arbitraj maliyet",       # cross-venue arbitrage cost  # noqa: RUF001
    "vadeli spot baz farkı",                 # futures/spot basis  # noqa: RUF001
    "zincirleme likidasyon kaldıraç",        # liquidation cascades  # noqa: RUF001
    "emir defteri kayma slipaj",             # order-book slippage
    "piyasa yapıcılığı envanter riski",      # market-making inventory risk  # noqa: RUF001
    "zincir üstü veri analiz strateji",      # on-chain analysis
    "alım satım botu zarar analiz",          # bot loss post-mortems  # noqa: RUF001
    "lira paritesi kripto arbitraj",         # lira-pair arbitrage -- the local mechanism
    "yerli borsa fiyat farkı arbitraj",      # domestic-venue price gap  # noqa: RUF001
    "maker taker komisyon optimizasyon",     # maker/taker fee optimisation
    "kelly kriteri pozisyon büyüklüğü",      # Kelly sizing
    "balina cüzdan takip zincir analizi",    # whale-wallet tracking
)


LANGUAGES: Final[dict[str, tuple[str, ...]]] = {
    "ja": QUERIES_JA,
    "ko": QUERIES_KO,
    "ru": QUERIES_RU,
    "vi": QUERIES_VI,
    "tr": QUERIES_TR,
}


# ------------------------------------------------------------------------------------ helpers

_LAST_CALL: dict[str, float] = {}


def _pace(source: str) -> None:
    """Sleep just long enough that this source's minimum interval is respected."""
    gap = _MIN_INTERVAL_S.get(source, 1.0)
    last = _LAST_CALL.get(source)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _LAST_CALL[source] = time.monotonic()


def _backed_off(source: str) -> tuple[list[Article], str] | None:
    """A short-circuit for a source that already answered 429 in this process."""
    if source in _BACKED_OFF:
        return [], (f"{source} returned HTTP 429 earlier in this run -- backed off for the rest "
                    "of it rather than hammering a source that asked for a pause")
    return None


def _note_429(source: str, exc: Exception) -> None:
    if getattr(exc, "code", None) == 429:
        _BACKED_OFF.add(source)


def _get(url: str, *, referer: str = "", timeout: float = 25.0) -> str:
    hdr = dict(_UA)
    if referer:
        hdr["Referer"] = referer
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def _post(url: str, payload: bytes, *, timeout: float = 20.0) -> str:
    """POST for the GraphQL-only sources. Same UA and timeout discipline as _get.

    Velog exposes search ONLY over GraphQL, and refusing to speak POST would have meant recording
    Korea's largest engineering-writeup platform as unreachable when it answers fine -- a routing
    problem misfiled as an absent forest (L1.54).
    """
    req = urllib.request.Request(
        url, data=payload, headers={**_UA, "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return str(resp.read().decode("utf-8", errors="replace"))



def _text(raw: str) -> str:
    """Strip tags, drop CDATA wrappers, decode entities, collapse whitespace -- IN THAT ORDER.

    The order is load-bearing and Hatena is the proof: its RSS titles arrive as numeric character
    references (`&#x306B;`), so an undecoded title contains no Japanese at all as far as the
    triage ranker is concerned and scores zero. Decoding BEFORE stripping would be the opposite
    error -- an encoded `&lt;b&gt;` would become a real tag that the stripper then eats, deleting
    text that was never markup.
    """
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", raw, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _rss_items(body: str) -> list[str]:
    """Item blocks from RSS 2.0 or RDF/RSS 1.0. Hatena serves the latter, Habr the former."""
    return re.findall(r"<item[^>]*>(.*?)</item>", body, flags=re.S)


def _tag(block: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", block, flags=re.S)
    return _text(m.group(1)) if m else ""


def _err(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:140]}"


# ------------------------------------------------------------------------------- JAPANESE (ja)

def qiita(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """Qiita -- Japan's largest engineering-writeup community. Keyless JSON API.

    Only rows carrying both a title and an id are kept, so an API shape change degrades to fewer
    results rather than to rows with empty titles that the ranker would score as zero and the
    desk would read as "nothing found in Japanese".
    """
    hit = _backed_off("qiita")
    if hit is not None:
        return hit
    _pace("qiita")
    url = f"https://qiita.com/api/v2/items?query={quote(keyword)}&per_page={int(limit)}"
    try:
        rows = json.loads(_get(url))
    except Exception as exc:
        _note_429("qiita", exc)
        return [], _err(exc)
    if not isinstance(rows, list):
        return [], "qiita returned a non-list payload -- API shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title, ident = _text(str(r.get("title") or "")), str(r.get("id") or "")
        if not title or not ident:
            continue
        tags = " ".join(str(t.get("name", "")) for t in (r.get("tags") or [])
                        if isinstance(t, dict))
        out.append(Article(source="qiita", ident=ident, title=title,
                           url=str(r.get("url") or f"https://qiita.com/items/{ident}"),
                           author=str((r.get("user") or {}).get("id") or ""),
                           snippet=f"{tags} {_text(str(r.get('body') or ''))[:360]}".strip()))
    return out, None


def zenn(keyword: str) -> tuple[list[Article], str | None]:
    """Zenn -- the newer Japanese engineering publication platform. Keyless JSON."""
    hit = _backed_off("zenn")
    if hit is not None:
        return hit
    _pace("zenn")
    url = f"https://zenn.dev/api/articles?keyword={quote(keyword)}&order=latest"
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("zenn", exc)
        return [], _err(exc)
    # R0466: THE SHAPE GUARD ITS SIBLINGS ALL HAVE. Without it a 200 carrying anything that is
    # not the expected document -- an anti-bot interstitial, a changed API, an error envelope --
    # fell through the `if isinstance(doc, dict)` into an empty list and returned ([], None): a
    # CLEAN NULL, byte-identical to "searched Zenn and it really has nothing on this". Those are
    # opposite facts and only one of them is a reason to stop digging a ground (WS-005/L1.28a).
    # zenn.dev is one of the two hosts R0466 measured 403ing our named agent at the CDN edge
    # while its robots.txt stayed clean, so this is the exact path where a BLOCKED ground would
    # have recorded as a THIN one.
    rows = doc.get("articles") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [], "zenn returned no `articles` list -- API shape changed or the reply is not JSON"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title, path = _text(str(r.get("title") or "")), str(r.get("path") or "")
        if not title or not path:
            continue
        out.append(Article(source="zenn", ident=str(r.get("id") or path), title=title,
                           url=f"https://zenn.dev{path}",
                           author=str((r.get("user") or {}).get("username") or ""),
                           snippet=str(r.get("article_type") or "")))
    return out, None


def hatena(keyword: str) -> tuple[list[Article], str | None]:
    """Hatena Bookmark search as RSS -- what Japanese engineers SAVE, not merely what they wrote.

    A bookmark count is a weak crowd filter the other sources do not carry, and it is orthogonal
    to the triage ranker's vocabulary scoring: one measures what practitioners thought worth
    keeping, the other measures what the text says.
    """
    hit = _backed_off("hatena")
    if hit is not None:
        return hit
    _pace("hatena")
    url = f"https://b.hatena.ne.jp/search/text?q={quote(keyword)}&mode=rss"
    try:
        body = _get(url)
    except Exception as exc:
        _note_429("hatena", exc)
        return [], _err(exc)
    out: list[Article] = []
    for block in _rss_items(body):
        title = _tag(block, "title")
        link = _tag(block, "link")
        if not title or not link:
            continue
        out.append(Article(source="hatena", ident=link[-40:], title=title, url=link,
                           snippet=_tag(block, "description")[:360]))
    if not out:
        return [], "hatena RSS fetched but no <item> blocks parsed -- feed shape changed"
    return out, None


# --------------------------------------------------------------------------------- KOREAN (ko)

def dcinside(keyword: str) -> tuple[list[Article], str | None]:
    """DCInside post search -- Korea's largest forum, and where the KR premium is discussed.

    Server-rendered HTML, so the parse is deliberately shallow (link + title text) and degrades to
    zero results rather than to wrong ones when the markup shifts. This desk MEASURES the Korean
    venue premium as a mechanism class and had never read a word written by the participants
    creating it, which is a strange asymmetry for a lane it already screens.
    """
    hit = _backed_off("dcinside")
    if hit is not None:
        return hit
    _pace("dcinside")
    url = f"https://search.dcinside.com/post/q/{quote(keyword)}"
    try:
        body = _get(url, referer="https://search.dcinside.com/")
    except Exception as exc:
        _note_429("dcinside", exc)
        return [], _err(exc)
    out: list[Article] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*class="tit_txt"[^>]*>(.*?)</a>',
                         body, flags=re.S):
        href, title = m.group(1), _text(m.group(2))
        if not title or href in seen:
            continue
        seen.add(href)
        out.append(Article(source="dcinside", ident=href[-40:], title=title,
                           url=href if href.startswith("http") else f"https:{href}"))
    if not out:
        # The class attribute may precede href; try the other order before reporting empty. A
        # regex that demanded one attribute order is exactly how the Sogou parser lost a working
        # source for a week, and that lesson is cheaper to reuse than to relearn.
        for m in re.finditer(r'<a[^>]+class="tit_txt"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                             body, flags=re.S):
            href, title = m.group(1), _text(m.group(2))
            if title and href not in seen:
                seen.add(href)
                out.append(Article(source="dcinside", ident=href[-40:], title=title,
                                   url=href if href.startswith("http") else f"https:{href}"))
    if not out:
        # AN EMPTY RESULT IS NOT A BROKEN PARSER, and conflating them sends the next reader to
        # the wrong place entirely: "markup changed" says go rewrite the regex, "no results" says
        # the query found nothing and the source is fine. DCInside says so on the page itself.
        # Found by running it -- 4 of 17 Korean queries reported "markup changed" while the same
        # parser worked on the other 13, which is the signature of a false diagnosis rather than
        # a real break.
        if "결과가 없" in body or "검색결과가 없" in body:
            return [], None
        return [], "dcinside page fetched but no result links parsed -- markup changed"
    return out, None


# -------------------------------------------------------------------------------- RUSSIAN (ru)

def habr(keyword: str) -> tuple[list[Article], str | None]:
    """Habr search via RSS.

    THE HTML SEARCH PAGE IS A JS SHELL -- probed 2026-08-05: 39KB with zero parseable result
    links. A desk that stopped there records "Habr: client-rendered, blocked" and loses a Russian
    corpus permanently. The SAME query served as RSS returns 20 items in one keyless request.
    L1.54 clause 6: a shut door named a ROUTE, not the source, and finding that out cost one probe.
    """
    hit = _backed_off("habr")
    if hit is not None:
        return hit
    _pace("habr")
    url = f"https://habr.com/ru/rss/search/?q={quote(keyword)}&target_type=posts&order=relevance"
    try:
        body = _get(url)
    except Exception as exc:
        _note_429("habr", exc)
        return [], _err(exc)
    out: list[Article] = []
    for block in _rss_items(body):
        title, link = _tag(block, "title"), _tag(block, "link")
        if not title or not link:
            continue
        out.append(Article(source="habr", ident=link[-40:], title=title, url=link,
                           author=_tag(block, "dc:creator"),
                           snippet=_tag(block, "description")[:360]))
    if not out:
        return [], "habr RSS fetched but no <item> blocks parsed -- feed shape changed"
    return out, None


#: source name -> (callable, language). The miner iterates this rather than a hardcoded list, so a
#: new forest is one entry and its queries, never a new branch in the mining loop.


# ======================================================================= THE DEEP LOCAL FORESTS
# WHY THESE AND NOT MORE BLOG PLATFORMS. Qiita, Zenn, Habr and the rest above are POLISHED
# publication venues: people write there to be seen being competent, so the failure literature --
# the part that is actually worth mining -- is systematically under-represented. The candid
# material lives on FORUMS, where practitioners complain, post their losses, argue about fills and
# name the venue that front-ran them. That is the register the Chinese lane already reaches through
# Bilibili comment culture, and every non-Chinese lane was missing it entirely.
#
# EACH SOURCE IS A LOCAL FOREST, not a translation of an English one. A Russian algo trader posts
# on smart-lab, not on Reddit; a Korean crypto trader posts on Coinpan, not on Bitcointalk. The
# whole point of a foreign lane is the material that never crosses into English, and it is exactly
# that material which sits behind a forum login-wall culture rather than an API.
#
# A BLOCKED SOURCE IS RECORDED, NEVER DROPPED. Several of these sit behind anti-bot layers that
# may answer 403 or serve a challenge page. `probe_all` marks such a lane BLOCKED with the reason,
# and it stays in the roster: a lane nobody can reach today is a routing problem to solve, not a
# verdict that the forest is empty (L1.54). Dropping it from SOURCES would erase the evidence that
# it was ever wanted.


def note(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """note.com -- where Japan's `botter` community actually publishes.

    The single highest-value Japanese venue for this desk: Japanese crypto bot operators write
    post-mortems here, including the losses, in a way they do not on Qiita. Keyless JSON search.
    """
    hit = _backed_off("note")
    if hit is not None:
        return hit
    _pace("note")
    url = ("https://note.com/api/v3/searchs?context=note&mode=search&size="
           f"{int(limit)}&q={quote(keyword)}")
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("note", exc)
        return [], _err(exc)
    data = doc.get("data") if isinstance(doc, dict) else None
    notes = (data or {}).get("notes") if isinstance(data, dict) else None
    rows = notes.get("contents") if isinstance(notes, dict) else notes
    if not isinstance(rows, list):
        return [], "note.com returned no `data.notes.contents` list -- API shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title, key = _text(str(r.get("name") or "")), str(r.get("key") or r.get("id") or "")
        if not title or not key:
            continue
        _u = r.get("user")
        user: dict[str, Any] = _u if isinstance(_u, dict) else {}
        urlname = str(user.get("urlname") or "")
        out.append(Article(source="note", ident=key, title=title,
                           url=str(r.get("noteUrl") or f"https://note.com/{urlname}/n/{key}"),
                           author=urlname,
                           snippet=_text(str(r.get("body") or r.get("description") or ""))[:360]))
    return out, None


def velog(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """Velog -- the Korean engineering-writeup platform. GraphQL, keyless.

    Korea's Qiita. Paired with Coinpan below it covers both registers: the polished writeup and
    the trading-floor argument.
    """
    hit = _backed_off("velog")
    if hit is not None:
        return hit
    _pace("velog")
    # DIRECT ARGUMENTS, not an input object. The input-object form is what the schema browser
    # suggests and it answers HTTP 400; measured against the live endpoint, `searchPosts` takes
    # keyword/offset/limit at the top level. Recorded because a 400 here is indistinguishable from
    # a dead source unless somebody has checked.
    query = ("query($keyword:String!,$offset:Int,$limit:Int){"
             "searchPosts(keyword:$keyword,offset:$offset,limit:$limit){"
             "posts{id title short_description url_slug user{username}}}}")
    payload = json.dumps({
        "query": query,
        "variables": {"keyword": keyword, "offset": 0, "limit": int(limit)}}).encode()
    try:
        raw = _post("https://v2cdn.velog.io/graphql", payload)
        doc = json.loads(raw)
    except Exception as exc:
        _note_429("velog", exc)
        return [], _err(exc)
    if isinstance(doc, dict) and doc.get("errors"):
        return [], f"velog GraphQL errors: {str(doc['errors'])[:140]}"
    node = ((doc.get("data") or {}).get("searchPosts") or {}) if isinstance(doc, dict) else {}
    rows = node.get("posts")
    if not isinstance(rows, list):
        return [], "velog returned no data.searchPosts.posts list -- GraphQL shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = _text(str(r.get("title") or ""))
        slug, ident = str(r.get("url_slug") or ""), str(r.get("id") or "")
        if not title or not ident:
            continue
        _u = r.get("user")
        user: dict[str, Any] = _u if isinstance(_u, dict) else {}
        who = str(user.get("username") or "")
        out.append(Article(source="velog", ident=ident, title=title,
                           url=f"https://velog.io/@{who}/{slug}" if who and slug
                               else f"https://velog.io/search?q={quote(keyword)}",
                           author=who,
                           snippet=_text(str(r.get("short_description") or ""))[:360]))
    return out, None


def coinpan(keyword: str) -> tuple[list[Article], str | None]:
    """Coinpan (코인판) -- Korea's crypto forum, and a genuine dark forest.

    The kimchi-premium trade, Upbit/Bithumb listing mechanics and the domestic arbitrage routes are
    discussed here in a detail that never reaches English. HTML search, so the parser is deliberate
    about distinguishing "no results" from "markup changed" -- collapsing those is how a live
    source gets recorded as dead.
    """
    hit = _backed_off("coinpan")
    if hit is not None:
        return hit
    _pace("coinpan")
    url = ("https://coinpan.com/index.php?mid=free&search_target=title"
           f"&search_keyword={quote(keyword)}")
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("coinpan", exc)
        return [], _err(exc)
    rows = re.findall(
        r'<a href="(/(?:free|index\.php)[^"]*document_srl=(\d+)[^"]*)"[^>]*>(.*?)</a>',
        page, flags=re.S)
    if not rows:
        if re.search(r"검색결과|내용이 없|게시물이 없", page):
            return [], None                    # a MEASURED empty result, not a parser failure
        return [], "coinpan fetched but no document links parsed -- markup changed or challenged"
    out: list[Article] = []
    seen: set[str] = set()
    for href, srl, raw_title in rows:
        title = _text(raw_title)
        if not title or srl in seen:
            continue
        seen.add(srl)
        out.append(Article(source="coinpan", ident=srl, title=title,
                           url=f"https://coinpan.com{href}" if href.startswith("/") else href))
    return out, None


def vcru(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """vc.ru -- Russian tech/finance long-form with an open JSON search."""
    hit = _backed_off("vcru")
    if hit is not None:
        return hit
    _pace("vcru")
    url = f"https://api.vc.ru/v2.1/search?q={quote(keyword)}&sorting=date&count={int(limit)}"
    try:
        doc = json.loads(_get(url))
    except Exception as exc:
        _note_429("vcru", exc)
        return [], _err(exc)
    # `items` AT THE TOP LEVEL. The documented envelope is `result`, and the live endpoint does not
    # use it -- measured 2026-08-05, both v2.1 and v2.5 answer `{"items": [...]}`. Both spellings
    # are accepted so a rollback of theirs is not an outage of ours.
    rows = None
    if isinstance(doc, dict):
        rows = doc.get("items")
        if rows is None:
            res = doc.get("result")
            rows = res.get("items") if isinstance(res, dict) else res
    if not isinstance(rows, list):
        keys = sorted(doc)[:6] if isinstance(doc, dict) else "?"
        return [], f"vc.ru returned no item list (top keys: {keys})"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        _d = r.get("data")
        data: dict[str, Any] = _d if isinstance(_d, dict) else r
        title = _text(str(data.get("title") or ""))
        ident = str(data.get("id") or "")
        if not title or not ident:
            continue
        out.append(Article(source="vcru", ident=ident, title=title,
                           url=str(data.get("url") or f"https://vc.ru/{ident}"),
                           snippet=_text(str(data.get("intro") or ""))[:360]))
    return out, None


def smartlab(keyword: str) -> tuple[list[Article], str | None]:
    """smart-lab.ru -- the Russian retail-algo trading forum.

    Russia's densest concentration of people who actually run systematic strategies and post the
    equity curves when they break. HTML search.
    """
    hit = _backed_off("smartlab")
    if hit is not None:
        return hit
    _pace("smartlab")
    url = f"https://smart-lab.ru/search/?q={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("smartlab", exc)
        return [], _err(exc)
    # PROMOTED COMPANY BLOGS ARE NOT SEARCH RESULTS, and a parser that cannot tell the difference
    # is worse than one that returns nothing. Measured 2026-08-05: smart-lab's search page ships
    # NO results in its HTML -- they are fetched by script -- while the sidebar carries five
    # /company/<name>/blog/<id>.php promos on every page regardless of query. A naive link regex
    # returned those five as "results", so a query about backtesting produced Russian corporate
    # news and the lane looked healthy while indexing noise. That is a fail-OPEN in the one
    # direction a miner must never fail: fabricated yield hides a dead source forever.
    rows = re.findall(
        r'<a[^>]+href="(https?://smart-lab\.ru/(?!company/)[^"]+/(\d+)\.php)"[^>]*>(.*?)</a>',
        page, flags=re.S)
    if not rows:
        if re.search(r"ничего не найден|нет результат", page, flags=re.I):
            return [], None                    # a MEASURED empty result
        return [], ("smart-lab search results are rendered by script, not served in HTML -- the "
                    "page carries only sidebar company-blog promos, which are NOT results. Needs "
                    "a render path (Chromium is present) or the forum's own RSS per section; "
                    "recorded as a ROUTING problem, never as an empty forest")
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="smartlab", ident=ident, title=title, url=href))
    return out, None


def tinhte(keyword: str) -> tuple[list[Article], str | None]:
    """Tinh te -- Vietnam's largest tech community. Vietnamese is a real crypto-retail forest and
    the desk had NO Vietnamese lane at all."""
    hit = _backed_off("tinhte")
    if hit is not None:
        return hit
    _pace("tinhte")
    url = f"https://tinhte.vn/search/?q={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("tinhte", exc)
        return [], _err(exc)
    rows = re.findall(r'<a[^>]+href="(/thread/[^"]+\.(\d+)/?)"[^>]*>(.*?)</a>', page, flags=re.S)
    if not rows:
        if re.search(r"không tìm thấy|không có kết quả", page, flags=re.I):
            return [], None
        return [], "tinhte fetched but no thread links parsed -- markup changed or challenged"
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="tinhte", ident=ident, title=title,
                           url=f"https://tinhte.vn{href}"))
    return out, None


def eksisozluk(keyword: str) -> tuple[list[Article], str | None]:
    """Eksi Sozluk -- Turkey's collaborative dictionary, and the country's real public square.

    Turkish crypto retail is enormous relative to the economy and argues here rather than on a
    forum. Heavy anti-bot; a challenge page is reported as a BLOCKER, never as an empty forest.
    """
    hit = _backed_off("eksisozluk")
    if hit is not None:
        return hit
    _pace("eksisozluk")
    url = f"https://eksisozluk.com/?q={quote(keyword)}"
    try:
        page = _get(url)
    except Exception as exc:
        _note_429("eksisozluk", exc)
        return [], _err(exc)
    rows = re.findall(r'<a[^>]+href="(/[^"?]+--(\d+))"[^>]*>(.*?)</a>', page, flags=re.S)
    if not rows:
        return [], "eksisozluk fetched but no entry links parsed -- markup changed or challenged"
    out: list[Article] = []
    seen: set[str] = set()
    for href, ident, raw_title in rows:
        title = _text(raw_title)
        if not title or ident in seen:
            continue
        seen.add(ident)
        out.append(Article(source="eksisozluk", ident=ident, title=title,
                           url=f"https://eksisozluk.com{href}"))
    return out, None


SOURCES: Final[dict[str, tuple[Any, str]]] = {
    # POLISHED PUBLICATION VENUES -- competence on display, failure under-represented.
    "qiita": (qiita, "ja"),
    "zenn": (zenn, "ja"),
    "hatena": (hatena, "ja"),
    "habr": (habr, "ru"),
    "velog": (velog, "ko"),
    "vcru": (vcru, "ru"),
    # THE DEEP LOCAL FORESTS -- where practitioners are candid, which is the material worth mining.
    "note": (note, "ja"),
    "dcinside": (dcinside, "ko"),
    "coinpan": (coinpan, "ko"),
    "smartlab": (smartlab, "ru"),
    "tinhte": (tinhte, "vi"),
    "eksisozluk": (eksisozluk, "tr"),
}


def probe_all() -> list[dict[str, Any]]:
    """One cheap query per source, for the health ledger. Same contract as cn_sources.probe_all.

    `ok` means the source returned USABLE ROWS, never merely that it answered with HTTP 200 -- a
    200 carrying an anti-bot page or an empty result set is not a working source, and recording it
    as one is how a dead lane stays green on a dashboard.

    `posture` SPLITS THE TWO WAYS `ok=False` HAPPENS, WHICH DEMAND OPPOSITE RESPONSES (R0466):

      OK      -- rows came back.
      WALLED  -- the source refused or answered with something unusable. The ground is UNKNOWN,
                 and the next move is a UA matrix against a real content path (OP-052), never a
                 verdict about the ground.
      EMPTY   -- the source answered cleanly and genuinely has nothing for this probe keyword.
                 Only THIS one is evidence about the ground, and even then only about the keyword.

    A single boolean made a BLOCKED ground and an EXHAUSTED ground byte-identical to any reader,
    which is how a whole region gets silently retired on evidence that never existed. The error
    string always carried the distinction; nothing surfaced it, so nothing could act on it.
    """
    out: list[dict[str, Any]] = []
    for name, (fn, lang) in SOURCES.items():
        probe_kw = LANGUAGES[lang][0]
        try:
            arts, err = fn(probe_kw)
        except Exception as exc:
            out.append({"source": name, "lang": lang, "ok": False, "posture": "WALLED",
                        "n": 0, "error": _err(exc)})
            continue
        out.append({"source": name, "lang": lang, "ok": bool(arts) and err is None,
                    "posture": "WALLED" if err is not None else ("OK" if arts else "EMPTY"),
                    "n": len(arts), "error": err})
    return out
