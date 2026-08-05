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
LANGUAGES: Final[dict[str, tuple[str, ...]]] = {
    "ja": QUERIES_JA,
    "ko": QUERIES_KO,
    "ru": QUERIES_RU,
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
    out: list[Article] = []
    for r in (doc.get("articles") or []) if isinstance(doc, dict) else []:
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
SOURCES: Final[dict[str, tuple[Any, str]]] = {
    "qiita": (qiita, "ja"),
    "zenn": (zenn, "ja"),
    "hatena": (hatena, "ja"),
    "dcinside": (dcinside, "ko"),
    "habr": (habr, "ru"),
}


def probe_all() -> list[dict[str, Any]]:
    """One cheap query per source, for the health ledger. Same contract as cn_sources.probe_all.

    `ok` means the source returned USABLE ROWS, never merely that it answered with HTTP 200 -- a
    200 carrying an anti-bot page or an empty result set is not a working source, and recording it
    as one is how a dead lane stays green on a dashboard.
    """
    out: list[dict[str, Any]] = []
    for name, (fn, lang) in SOURCES.items():
        probe_kw = LANGUAGES[lang][0]
        try:
            arts, err = fn(probe_kw)
        except Exception as exc:
            out.append({"source": name, "lang": lang, "ok": False, "error": _err(exc)})
            continue
        out.append({"source": name, "lang": lang, "ok": bool(arts) and err is None,
                    "n": len(arts), "error": err})
    return out
