"""Chinese-language research discovery beyond Bilibili: Juejin and Sogou/WeChat.

MEASURED 2026-08-01 from this box, because every one of these was previously recorded as simply
"blocked" and most of them were not:

    Juejin (掘金) search API   WORKS -- clean JSON, err_no 0, ~20 results per query. A large
                              Chinese developer community with substantial quant content.
    Sogou WeChat search       REACHABLE -- 31KB of parseable HTML. WeChat (微信公众号) is where
                              a large share of Chinese quant writing actually lives, and it is
                              otherwise closed to the open web; Sogou is the only public index.
    Xueqiu (雪球)             HTML reachable but the API sits behind a WAF challenge that a
                              plain cookie handshake does not clear. Recorded, not solved.
    Zhihu (知乎)              HTTP 403 to unauthenticated requests, API included.
    JoinQuant / BigQuant      HTML shells; their APIs 404 or need auth.
    CSDN                      read timeout from this box.

WHY CHINESE SOURCES ARE WORTH THE EFFORT AT ALL. Not novelty -- the desk's measured conversion
record says what converts is a MEASUREMENT over many trials or an explicit PROCEDURE, and that
material is written in Chinese too, by people whose work never surfaces in an English search. The
first Juejin query returned an article on common traps in quant backtesting; that is the same
category as the transcripts that produced bar_permutation and lookahead_audit.

ONLY TITLES AND SNIPPETS ARE KEPT. These sources are indexed to decide what a human should go and
READ. Nothing archives article bodies.
"""

from __future__ import annotations

import html
import json
import math
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

_UA = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass(frozen=True)
class Article:
    source: str
    ident: str
    title: str
    url: str
    author: str = ""
    snippet: str = ""

    @property
    def searchable(self) -> str:
        """Title plus snippet. A Chinese title is often generic while the snippet carries the
        method words, so scoring the title alone under-ranks the material worth finding."""
        return f"{self.title} {self.snippet}"


def _get(url: str, *, referer: str, timeout: float = 25.0) -> str:
    req = urllib.request.Request(url, headers={**_UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def juejin(keyword: str, *, limit: int = 20) -> tuple[list[Article], str | None]:
    """Juejin (掘金) search. Returns (articles, error).

    The response nests differently per result type -- an article, a course, a user all arrive in
    the same list under `result_model`. Only rows carrying an `article_info.title` are kept, so a
    layout change degrades to fewer results rather than to garbage titles.
    """
    url = (f"https://api.juejin.cn/search_api/v1/search?query={quote(keyword)}"
           f"&id_type=0&limit={int(limit)}")
    try:
        body = json.loads(_get(url, referer="https://juejin.cn/"))
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    if body.get("err_no") != 0:
        return [], f"juejin err_no={body.get('err_no')} msg={body.get('err_msg')}"
    out: list[Article] = []
    for row in body.get("data") or []:
        info = ((row.get("result_model") or {}).get("article_info") or {})
        title = str(info.get("title") or "").strip()
        aid = str(info.get("article_id") or "")
        if not title or not aid:
            continue
        out.append(Article(
            source="juejin", ident=aid, title=title,
            url=f"https://juejin.cn/post/{aid}",
            author=str(((row.get("result_model") or {}).get("author_user_info") or {})
                       .get("user_name") or ""),
            snippet=str(info.get("brief_content") or "")[:400],
        ))
    return out, None


def sogou_weixin(keyword: str) -> tuple[list[Article], str | None]:
    """WeChat (微信公众号) articles via Sogou, the only public index of them.

    HTML-SCRAPED BECAUSE THERE IS NO API. WeChat is a closed platform and a large share of
    Chinese quant writing is published there and nowhere else, so an imperfect index of it beats
    a perfect index of nothing. The parse is deliberately shallow -- link plus title text -- so
    it degrades to zero results rather than to wrong ones when the markup shifts.

    Sogou rate-limits aggressively and will serve an anti-bot page; that returns an empty list
    with a reason rather than raising, so a daily sweep continues.
    """
    url = f"https://weixin.sogou.com/weixin?type=2&query={quote(keyword)}"
    try:
        # NOT named `html`: that is the stdlib module this file now needs for entity decoding, and
        # shadowing it here would leave `html.unescape` working in every OTHER function and dead
        # in this one -- the kind of breakage that surfaces only when someone later moves a line.
        page = _get(url, referer="https://weixin.sogou.com/")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    if "antispider" in page or "请输入验证码" in page:
        return [], "sogou served an anti-bot challenge (rate limited)"

    # PARSED BLOCK-WISE, and the summary is the whole reason. The first version scanned title
    # anchors globally and never touched `<p class="txt-info">`, so every WeChat article reached
    # the ranker as a BARE TITLE while Juejin arrived with brief_content and Bilibili with
    # description plus tags. Measured 2026-08-01: 3 of 40 WeChat articles cleared the threshold
    # (7.5%) against Juejin's 42% and Bilibili's 28% -- and the page was carrying all 10 summaries
    # the whole time. This module's own docstring states the requirement it was failing: "a Chinese
    # title is often generic while the snippet carries the method words, so scoring the title alone
    # under-ranks the material worth finding." Third instance of one class on this source (after
    # the CJK word-boundary bug and the attribute-order bug): the fetch was healthy and the PARSE
    # was starving the ranker.
    #
    # Block-wise rather than two global scans because pairing by document order across separate
    # regex passes would silently mis-pair the moment one result lacked a summary -- and scoring
    # article A on article B's body is far worse than scoring A on its title alone. Each
    # `txt-box` holds exactly one title anchor and one summary (verified across live pages), so
    # a block that does not is skipped rather than guessed at.
    out: list[Article] = []
    seen: set[str] = set()
    blocks = re.split(r'<div class="txt-box">', page)[1:]
    for block in blocks:
        art = _parse_wechat_block(block, seen)
        if art is not None:
            out.append(art)

    # FALLBACK to the title-only scan when the block structure is gone. Sogou's markup shifts, and
    # degrading to weaker results beats degrading to none -- but the caller is told, because a
    # silent downgrade to title-only scoring is exactly the defect above coming back unnoticed.
    if not out:
        for m in re.finditer(r'<a\b([^>]*uigs="article_title[^>]*)>(.*?)</a>', page, flags=re.S):
            art = _wechat_article(m.group(1), m.group(2), "", seen)
            if art is not None:
                out.append(art)
        if out:
            return out, (f"txt-box blocks missing; fell back to title-only scoring on {len(out)} "
                         "results -- snippets are NOT being scored, which under-ranks this source")
        return [], "page fetched but no article links parsed -- markup changed or empty result"
    return out, None


def _parse_wechat_block(block: str, seen: set[str]) -> Article | None:
    m = re.search(r'<a\b([^>]*uigs="article_title[^>]*)>(.*?)</a>', block, flags=re.S)
    if m is None:
        return None
    info = re.search(r'<p class="txt-info"[^>]*>(.*?)</p>', block, flags=re.S)
    return _wechat_article(m.group(1), m.group(2), info.group(1) if info else "", seen)


def _wechat_article(attrs: str, raw_title: str, raw_snippet: str,
                    seen: set[str]) -> Article | None:
    """Build one article. ORDER-AGNOSTIC on attributes: the anchor carries href BEFORE uigs, so a
    regex demanding uigs first matched nothing while the page was perfectly healthy."""
    href_m = re.search(r'href="([^"]+)"', attrs)
    if not href_m:
        return None
    # THE HREF IS AN HTML ATTRIBUTE, SO ITS SEPARATORS ARE ENTITY-ENCODED. Sogou writes
    # `?url=...&amp;type=2&amp;query=...`, and taking that literally produces a query parameter
    # actually named `amp;type` -- so every WeChat link the miner surfaced was DEAD, and dead in
    # the quiet way: the row looks complete, ranks normally, and only fails when a human finally
    # clicks it. A candidate the desk cannot open is a candidate the desk did not find.
    href = html.unescape(href_m.group(1))
    title = _text(raw_title)
    if not title or href in seen:
        return None
    seen.add(href)
    link = href if href.startswith("http") else f"https://weixin.sogou.com{href}"
    return Article(source="wechat", ident=href[-24:], title=title, url=link,
                   snippet=_text(raw_snippet)[:400])


def _text(raw: str) -> str:
    """Strip tags, decode entities, collapse whitespace.

    Sogou wraps matched terms in <em> highlights, and an unstripped '<em>回测</em>' would put
    markup into the text the ranker scores.

    THE UNESCAPE COMES AFTER TAG REMOVAL (2026-08-05) and the order is load-bearing: decode first
    and an encoded `&lt;em&gt;` becomes a real tag that the next step then eats, deleting text
    between two angle brackets that were never markup.

    Entities were reaching the ranker undecoded. `&quot;` is merely untidy; a NUMERIC entity is
    the real hazard, because `&#x91CF;&#x5316;` is how `量化` arrives from some encoders -- the
    scorer would find no Chinese in the title at all and rank a relevant article zero. Same
    failure mode as the CJK `\\b` bug, reached through a different door: a real edge made
    invisible to the gate rather than rejected by it.
    """
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw))).strip()


def probe_all() -> list[dict[str, Any]]:
    """One-line reachability for every declared source, re-measured rather than trusted.

    The desk has already been burned treating a recorded HTTP failure as permanent when it was a
    header problem (L0052) and treating a 412 as a block when it was a signing requirement. A
    declared status is a prior; this is the evidence.
    """
    rows: list[dict[str, Any]] = []
    probes: tuple[tuple[str, str], ...] = (("juejin", "量化 回测"), ("wechat_sogou", "量化 回测"))
    for name, kw in probes:
        items, err = juejin(kw) if name == "juejin" else sogou_weixin(kw)
        rows.append({"source": name, "ok": err is None, "n": len(items), "error": err})
    for name, url, note in (
        ("xueqiu", "https://xueqiu.com/",
         "HTML reachable; API behind a WAF challenge a cookie handshake does not clear"),
        ("zhihu", "https://www.zhihu.com/api/v4/search_v3", "HTTP 403 unauthenticated"),
        ("joinquant", "https://www.joinquant.com/", "JS shell; API 404/auth"),
        ("csdn", "https://so.csdn.net/", "read timeout from this box"),
    ):
        try:
            body = _get(url, referer=url, timeout=15.0)
            # THE DECLARED REASON IS THE PRIOR AND MUST NOT BE WRITTEN INTO THE EVIDENCE FIELD.
            # This branch is the SUCCESS branch -- the fetch returned -- and it was reporting the
            # hardcoded note as `error` regardless. Measured 2026-08-06: csdn had been failing with
            # an SSL handshake timeout, then answered with 2,141 bytes, and the probe row said
            # `reachable: true, error: "read timeout from this box"`. Those two fields contradict
            # each other, and the false one is the one a reader believes, because it is the one
            # that names a cause. This file's own docstring states the rule it was breaking: "a
            # declared status is a prior; this is the evidence."
            #
            # WHAT IS STILL NOT ok. A response is not content: 2KB from a search endpoint is an
            # anti-bot shell or a redirect stub. So `ok` stays False and the row now says WHICH of
            # the two it is, because "unreachable" and "reachable but serving a shell" lead to
            # different work -- one is a network route to hunt, the other is a parser or a render
            # path. The threshold matches probe_cn's own `looks_like_content` cut.
            shell = len(body) <= 20_000
            rows.append({"source": name, "ok": False, "reachable": True, "bytes": len(body),
                         "looks_like_content": not shell,
                         "declared": note,
                         "error": (f"responded with {len(body)}B -- "
                                   + ("an anti-bot shell or stub, not content" if shell
                                      else "a full-size body; the declared blocker may be STALE, "
                                           "re-check whether this source is parseable now")
                                   + f" (declared prior: {note})")})
        except Exception as exc:
            rows.append({"source": name, "ok": False, "reachable": False,
                         "declared": note,
                         "error": f"{type(exc).__name__}: {str(exc)[:90]} :: {note}"})
    return rows


# ================================================================== retail boards (2026-10-13)
# THE BOARD LAYER: Eastmoney Guba and Xueqiu per-board post LISTS, for the point-in-time
# post-volume and post-text series `desks/mt5/research/cn_retail_posts.py` lands. The keyword
# search fetchers above (and `free_stack.fetch_cn_forum`, `blog_social_sources`) answer "what is
# the crowd saying about X"; a board list answers "how many posts did this board get in this
# hour", which is the attention series the literature measures on Guba.
#
# WHAT IS ALLOWED, AND WHY IT IS WRITTEN HERE (principal's ruling 2026-10-13): no source is banned
# as a category -- Eastmoney and Xueqiu are allowed -- and the off-limits things are METHODS:
# bypassing a login, paywall, CAPTCHA, slider, rate limit or region lock; stolen data; MNPI. A page
# that answers with a login or a challenge is recorded METHOD_BLOCKED with its evidence and never
# worked around (no rotating UA, no forged header, no cookie lifted from a logged-in session).
# robots.txt is respected and a host gets at most one request per 3 s. The terms each site
# publishes are recorded VERBATIM below so a reader sees what the site itself says, including the
# clauses that restrict; the ruling is the basis for fetching, the quotes are the provenance.

#: Per site: the robots/terms evidence read on the check date, the basis for fetching, and the
#: public list route. `post_route` is what the organ fetches; robots is re-read live each day and
#: a disallowed route is METHOD_BLOCKED before any request is made to it.
RETAIL_SITES: dict[str, dict[str, Any]] = {
    "guba": {
        "host": "guba.eastmoney.com",
        "list_url": "https://guba.eastmoney.com/list,{code}{page}.html",
        "page_suffix": "_{n}",
        "basis": ("principal's ruling 2026-10-13: Eastmoney allowed; public list pages fetched "
                  "politely, robots respected, 1 request / 3 s per host"),
        "checked": "2026-10-13",
        "robots_url": "https://guba.eastmoney.com/robots.txt",
        "robots_evidence": ("guba.eastmoney.com/robots.txt could not be read from the build "
                            "session (fetch error); www.eastmoney.com/robots.txt reads "
                            "'User-agent: *' / 'Allow: /'. The organ re-reads guba's own "
                            "robots.txt live and fetches nothing it disallows"),
        "terms_url": "https://emuserh5.eastmoney.com/useragreement",
        "terms_quote": (
            "东方财富软件许可及服务协议: "
            "\"本“产品”及其相关服务仅供个人用户用于非商业环境及非盈利活动。\" "
            "3.2.3: \"未经东方财富信息股份有限公司书面同意，"  # noqa: RUF001
            "用户不得擅自实施包括但不限于下列行为："  # noqa: RUF001
            "使用、复制、修改、链接、转载、汇编、发表、出版\" "
            "-- the app licence; no clause found that names crawlers or automated access "
            "either way"),
        "terms_reading": ("no clause permitting automated access was found; the closest clause "
                          "restricts copying/compiling product content without written consent. "
                          "Only titles, counts and times are kept, internally, never "
                          "redistributed"),
        "probe_2026_10_13": ("build session, one request to list,zssh000016.html: the page "
                             "served a '身份核实' (identity verification) interstitial and no "
                             "posts -- METHOD_BLOCKED from this vantage; the cloud container's "
                             "own proxy refuses CONNECT to the host (403). The box's first pass "
                             "is the first reading from the desk's own vantage"),
    },
    "xueqiu": {
        "host": "xueqiu.com",
        "list_url": ("https://xueqiu.com/query/v1/symbol/search/status.json?count=20"
                     "&comment=0&symbol={code}&hl=0&source=all&sort=time&page={n}"),
        "page_suffix": "",
        "basis": "principal's ruling 2026-10-13: Xueqiu allowed by category; methods bind",
        "checked": "2026-10-13",
        "robots_url": "https://xueqiu.com/robots.txt",
        "robots_evidence": ("xueqiu.com/robots.txt, User-agent: * -> 'Disallow: /*.json', "
                            "'Disallow: /query/', 'Disallow: /v5/stock/', 'Disallow: /stock/'. "
                            "Every route that lists a symbol's posts is a /query/ .json route"),
        "terms_url": "https://xueqiu.com/about/terms",
        "terms_quote": (
            "3.5(2) \"使用任何漫游器、网络蜘蛛、网络爬虫、抓取工具、"
            "网站搜索/检索应用程序或其他手段访问、抓取、爬取\"; "
            "3.5(3) \"违反、规避或不遵守雪球Robots协议等\"; "
            "3.5(7) \"以机器人软件、蜘蛛软件、爬虫软件、刷屏软件等非人工方式，"  # noqa: RUF001
            "使用雪球网站或服务\"; "
            "3.6(4) \"未经雪球或雪球用户同意的情况下，"  # noqa: RUF001
            "将雪球或其他雪球用户发布的内容上传或提供到您使用的AI上\"; "
            "robots.txt notice: \"Creation of Datasets: Without our express permission, you "
            "are prohibited from creating or providing\" \"archival or cache datasets that "
            "include our content for use by others.\""),
        "terms_reading": ("the site's own terms prohibit crawler/robot access and AI use of its "
                          "content, and robots.txt disallows every post-list route; the route is "
                          "METHOD_BLOCKED by robots before terms are even reached"),
        "probe_2026_10_13": ("build session, one request to /S/SH000016 (a robots-allowed HTML "
                             "page): an Alibaba Cloud WAF JavaScript challenge (meta "
                             "aliyun_waf_*, an obfuscated script and a _waf_ token), no posts"),
    },
}

#: Markers of a page that is not content: a login wall, a CAPTCHA, a slider or a WAF challenge.
#: Matched on the raw body. A hit is recorded as METHOD_BLOCKED with the marker as evidence.
CHALLENGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("身份核实", "identity-verification interstitial (身份核实)"),
    ("acw_sc__v2", "Alibaba Cloud WAF cookie challenge (acw_sc__v2)"),
    ("aliyun_waf", "Alibaba Cloud WAF JavaScript challenge (aliyun_waf)"),
    ("_waf_", "WAF challenge token (_waf_)"),
    ("请输入验证码", "CAPTCHA (请输入验证码)"),
    ("滑动验证", "slider verification (滑动验证)"),
    ("拖动滑块", "slider verification (拖动滑块)"),
    ("安全验证", "security verification (安全验证)"),
    ("请登录后", "login wall (请登录后)"),
    ("\"error_code\":\"400016\"", "Xueqiu login-required error 400016"),
)


def challenge_of(body: bytes | str | None) -> str | None:
    """The first challenge marker in a body, or None when it looks like a page of content."""
    if body is None:
        return None
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    for needle, label in CHALLENGE_MARKERS:
        if needle in text:
            return label
    return None


def robots_allows(robots_txt: str, url: str, agent: str = "*") -> bool:
    """Standard robots.txt semantics (stdlib parser plus `*`/`$` path wildcards, which Xueqiu's
    file uses and `urllib.robotparser` does not understand). Longest matching rule wins."""
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(val.lower())
        elif key in ("allow", "disallow") and agents:
            rules.append((key, val))
    if agents:
        groups.append((agents, rules))
    chosen = next((r for a, r in groups if agent.lower() in a), None)
    if chosen is None:
        chosen = next((r for a, r in groups if "*" in a), [])
    best: tuple[int, bool] = (-1, True)
    for kind, pattern in chosen:
        if not pattern:
            continue                      # an empty Disallow allows everything
        rx = "^" + re.escape(pattern).replace(r"\*", ".*")
        if rx.endswith(r"\$"):
            rx = rx[:-2] + "$"
        if re.match(rx, target) and len(pattern) > best[0]:
            best = (len(pattern), kind == "allow")
    return best[1]


def _cn_time(raw: str, fetched_at: Any) -> tuple[str | None, list[str]]:
    """A Beijing-time stamp as UTC ISO. Guba's HTML list prints `MM-DD HH:MM` with no year: the
    year is taken from the fetch time (the previous year when that would land in the future) and
    the row is FLAGGED, never silently trusted."""
    cst = timezone(timedelta(hours=8))
    s = (raw or "").strip()
    flags: list[str] = []
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=cst).astimezone(
                UTC).isoformat(), flags
        except ValueError:
            continue
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", s)
    if m and isinstance(fetched_at, datetime):
        mo, d, hh, mi = (int(x) for x in m.groups())
        local_now = fetched_at.astimezone(cst)
        try:
            dt = datetime(local_now.year, mo, d, hh, mi, tzinfo=cst)
        except ValueError:
            return None, ["time_unparsed"]
        if dt > local_now + timedelta(minutes=5):
            dt = dt.replace(year=dt.year - 1)
        return dt.astimezone(UTC).isoformat(), ["year_inferred"]
    return None, ["time_unparsed"]


def _count(v: Any) -> int | None:
    try:
        s = str(v).strip().replace(",", "")
        if s.endswith("万"):
            return int(float(s[:-1]) * 1e4)
        return int(float(s))
    except (TypeError, ValueError):
        return None


def parse_guba_list(body: bytes | str | None, fetched_at: Any = None) -> list[dict[str, Any]]:
    """One row per post on an Eastmoney Guba board list page. NEVER DROPS AN UGLY ROW: a row whose
    time or counts do not parse is kept with `parse_flags` naming what failed.

    Two layouts, both public: the embedded `var article_list={"re":[...]}` JSON (publish time,
    click and comment counts per post) and, when that is absent, the HTML table rows
    (`<tr class="listitem">` with read / reply / title / update cells), whose only time is the
    LAST-UPDATE time -- flagged `time_is_last_update`, because it is not a publication time.
    """
    if not body:
        return []
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    out: list[dict[str, Any]] = []
    m = re.search(r"var\s+article_list\s*=\s*(\{.*?\})\s*;", text, re.S)
    if m:
        try:
            doc = json.loads(m.group(1))
        except ValueError:
            doc = None
        if isinstance(doc, dict):
            for r in doc.get("re") or []:
                if not isinstance(r, dict):
                    out.append({"post_id": None, "title": str(r)[:400], "published_raw": "",
                                "published_time": None, "read_count": None, "reply_count": None,
                                "user": "", "url": "", "parse_flags": ["row_not_object"]})
                    continue
                raw_t = str(r.get("post_publish_time") or "")
                pub, flags = _cn_time(raw_t, fetched_at)
                reads, replies = _count(r.get("post_click_count")), _count(
                    r.get("post_comment_count"))
                if reads is None:
                    flags.append("read_count_missing")
                if replies is None:
                    flags.append("reply_count_missing")
                title = _text(str(r.get("post_title") or ""))
                if not title:
                    flags.append("title_empty")
                pid = r.get("post_id")
                code = str(r.get("stockbar_code") or "")
                out.append({"post_id": str(pid) if pid is not None else None, "title": title,
                            "published_raw": raw_t, "published_time": pub,
                            "last_reply_raw": str(r.get("post_last_time") or ""),
                            "read_count": reads, "reply_count": replies,
                            "user": str(r.get("user_id") or ""),
                            "url": (f"https://guba.eastmoney.com/news,{code},{pid}.html"
                                    if pid is not None and code else ""),
                            "parse_flags": flags})
            return out
    for row in re.findall(r'<tr[^>]*class="[^"]*listitem[^"]*"[^>]*>(.*?)</tr>', text, re.S):
        def cell(cls: str, row: str = row) -> str:
            c = re.search(rf'<div[^>]*class="[^"]*\b{cls}\b[^"]*"[^>]*>(.*?)</div>', row, re.S)
            return c.group(1) if c else ""
        a = re.search(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', cell("title"), re.S)
        title = _text(a.group(2)) if a else _text(cell("title"))
        href = html.unescape(a.group(1)) if a else ""
        pid_m = re.search(r",(\d+)\.html", href)
        raw_t = _text(cell("update"))
        pub, flags = _cn_time(raw_t, fetched_at)
        flags.append("time_is_last_update")
        reads, replies = _count(_text(cell("read"))), _count(_text(cell("reply")))
        if reads is None:
            flags.append("read_count_missing")
        if replies is None:
            flags.append("reply_count_missing")
        if not title:
            flags.append("title_empty")
        out.append({"post_id": pid_m.group(1) if pid_m else None, "title": title,
                    "published_raw": raw_t, "published_time": pub, "read_count": reads,
                    "reply_count": replies, "user": "",
                    "url": (href if href.startswith("http")
                            else f"https://guba.eastmoney.com{href}" if href else ""),
                    "parse_flags": flags})
    return out


def parse_xueqiu_list(body: bytes | str | None, fetched_at: Any = None) -> list[dict[str, Any]]:
    """Xueqiu's symbol status list JSON, the same shape `free_stack.parse_xueqiu` reads. Present
    so a robots change on Xueqiu's side is a configuration event, not a code change; while its
    robots.txt disallows the route, the organ never calls the route this parses."""
    if not body:
        return []
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    try:
        doc = json.loads(text)
    except ValueError:
        return []
    out: list[dict[str, Any]] = []
    for r in (doc.get("list") or []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict):
            continue
        flags: list[str] = []
        ts = r.get("created_at")
        pub = (datetime.fromtimestamp(float(ts) / 1000.0, tz=UTC).isoformat()
               if isinstance(ts, (int, float)) else None)
        if pub is None:
            flags.append("time_unparsed")
        title = _text(str(r.get("title") or r.get("text") or r.get("description") or ""))
        user = r.get("user") if isinstance(r.get("user"), dict) else {}
        out.append({"post_id": str(r.get("id")) if r.get("id") is not None else None,
                    "title": title, "published_raw": str(ts or ""), "published_time": pub,
                    "read_count": _count(r.get("view_count")),
                    "reply_count": _count(r.get("reply_count")),
                    "user": str((user or {}).get("id") or ""),
                    "url": f"https://xueqiu.com/{(user or {}).get('id')}/{r.get('id')}",
                    "parse_flags": flags})
    return out


# ======================================================== CN public state pages (2026-10-13)
# China stress and flow STATES from public pages, for CN50 / HK50 / USDCNH cells: Eastmoney's
# Stock Connect flows, limit-up / limit-down pools and institutional holdings, and JiSiLu's
# convertible-bond index and list. The routes are the ones AKShare (MIT licence, read
# 2026-10-13) calls; they are called directly here, so no package is installed. Fetched by
# `free_stack.fetch_cn_public_state` (hunter leg `free_stack_hunt`), reported per source by
# `research/cn_retail_posts.py` in `reports/CN_RETAIL_POSTS.json`.

EM_DATACENTER = "https://datacenter-web.eastmoney.com/api/data/v1/get"
#: Stock Connect channel -> MUTUAL_TYPE (AKShare stock_hsgt_hist_em's map).
EM_CONNECT_TYPES: dict[str, str] = {"north": "005", "south": "006", "sh_south": "002",
                                    "sz_south": "004"}
EM_ZT_POOL = ("https://push2ex.eastmoney.com/getTopicZTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
              "&dpt=wz.ztzt&Pageindex=0&pagesize=10000&sort=fbt%3Aasc&date={date}")
EM_DT_POOL = ("https://push2ex.eastmoney.com/getTopicDTPool?ut=7eea3edcaed734bea9cbfc24409ed989"
              "&dpt=wz.ztzt&Pageindex=0&pagesize=10000&sort=fund%3Aasc&date={date}")
JSL_INDEX = "https://www.jisilu.cn/webapi/cb/index_history/"
JSL_LIST = "https://www.jisilu.cn/data/cbnew/cb_list_new/?___jsl=LST___t={ms}"

#: Markers of a JiSiLu answer that is a login wall or a guest-truncated table, not the table.
JSL_LOGIN_MARKERS: tuple[tuple[str, str], ...] = (
    ("游客", "guest-limited table (游客)"),
    ("请登录", "login wall (请登录)"),
    ("登录后", "login wall (登录后)"),
    ("\"isGuest\":true", "guest-limited table (isGuest)"),
)


def em_connect_url(mutual_type: str, page_size: int = 60) -> str:
    from urllib.parse import urlencode

    return EM_DATACENTER + "?" + urlencode({
        "sortColumns": "TRADE_DATE", "sortTypes": "-1", "pageSize": str(page_size),
        "pageNumber": "1", "reportName": "RPT_MUTUAL_DEAL_HISTORY", "columns": "ALL",
        "source": "WEB", "client": "WEB", "filter": f'(MUTUAL_TYPE="{mutual_type}")'})


def em_orghold_url(code: str) -> str:
    """Eastmoney's institutional-holding report for one security. ROUTE UNVERIFIED: the report
    name is the data centre's 主力持仓 table as the build session understood it; a box pass that
    parses no rows says so (EMPTY with this note), never a zero."""
    from urllib.parse import urlencode

    return EM_DATACENTER + "?" + urlencode({
        "reportName": "RPT_MAIN_ORGHOLD", "columns": "ALL", "source": "WEB", "client": "WEB",
        "sortColumns": "REPORT_DATE", "sortTypes": "-1", "pageSize": "50", "pageNumber": "1",
        "filter": f'(SECURITY_CODE="{code}")'})


def parse_em_datacenter(raw: bytes | str | None) -> tuple[list[dict[str, Any]], str | None]:
    """(rows, problem). `result.data` of the data centre's JSON; a null result is a problem with
    the server's own message, never an empty success."""
    if not raw:
        return [], "empty body"
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    try:
        doc = json.loads(text)
    except ValueError:
        return [], "not JSON"
    res = doc.get("result") if isinstance(doc, dict) else None
    if not isinstance(res, dict):
        return [], f"no result (code={doc.get('code') if isinstance(doc, dict) else '?'}, " \
                   f"message={str(doc.get('message') if isinstance(doc, dict) else '')[:80]})"
    data = res.get("data")
    return ([r for r in data if isinstance(r, dict)] if isinstance(data, list) else []), None


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def connect_flow_points(rows: list[dict[str, Any]]) -> tuple[list[tuple[str, float]], int]:
    """(date, net deal amount) per trading day, and how many days carried NO disclosed figure --
    northbound daily net buying stopped being published in August 2024, and such a day is
    UNMEASURED, never a zero flow."""
    out: list[tuple[str, float]] = []
    missing = 0
    for r in rows:
        d = str(r.get("TRADE_DATE") or "")[:10]
        v = _num(r.get("NET_DEAL_AMT"))
        if v is None:
            v = _num(r.get("FUND_INFLOW"))
        if not d:
            continue
        if v is None:
            missing += 1
            continue
        out.append((d, v))
    return sorted(out), missing


def parse_em_pool(raw: bytes | str | None) -> int | None:
    """Size of a limit-up / limit-down pool. None when the answer carries no pool at all (a
    non-trading day or a refusal): absence is not a count of zero."""
    if not raw:
        return None
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    data = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(data, dict):
        return None
    pool = data.get("pool")
    if isinstance(pool, list):
        return len(pool)
    tc = _num(data.get("tc"))
    return int(tc) if tc is not None else None


def jsl_problem(raw: bytes | str | None) -> str | None:
    """A JiSiLu answer that is a login wall or a guest-limited table, or a challenge page."""
    if raw is None:
        return None
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    hit = challenge_of(text)
    if hit:
        return hit
    for needle, label in JSL_LOGIN_MARKERS:
        if needle in text:
            return label
    return None


def parse_jsl_index(raw: bytes | str | None) -> list[dict[str, Any]]:
    """JiSiLu's convertible-bond equal-weight index history: one dict per day. `data` arrives
    either as a list of row dicts or as a dict of parallel columns; both are read."""
    if not raw:
        return []
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    try:
        doc = json.loads(text)
    except ValueError:
        return []
    data = doc.get("data") if isinstance(doc, dict) else None
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        cols = {k: v for k, v in data.items() if isinstance(v, list)}
        n = max((len(v) for v in cols.values()), default=0)
        rows = [{k: (v[i] if i < len(v) else None) for k, v in cols.items()} for i in range(n)]
    out = []
    for r in rows:
        d = str(r.get("price_dt") or r.get("date") or "")[:10]
        if d:
            out.append({**r, "price_dt": d})
    return out


def parse_jsl_list(raw: bytes | str | None) -> list[dict[str, Any]]:
    """The convertible-bond list's `rows[].cell` dicts."""
    if not raw:
        return []
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
    try:
        doc = json.loads(text)
    except ValueError:
        return []
    return [r["cell"] for r in (doc.get("rows") or []) if isinstance(doc, dict)
            and isinstance(r, dict) and isinstance(r.get("cell"), dict)]


def jsl_list_stress(cells: list[dict[str, Any]]) -> dict[str, float]:
    """Cross-sectional stress of the convertible list: median conversion premium, median YTM,
    and the share of bonds priced below par (credit distress)."""
    def pct(v: Any) -> float | None:
        return _num(str(v).rstrip("%")) if v is not None else None

    prem = sorted(x for c in cells if (x := pct(c.get("premium_rt"))) is not None)
    ytm = sorted(x for c in cells if (x := pct(c.get("ytm_rt"))) is not None)
    px = [x for c in cells if (x := _num(c.get("price"))) is not None]
    out: dict[str, float] = {"n_bonds": float(len(cells))}
    if prem:
        out["median_premium_rt"] = prem[len(prem) // 2]
    if ytm:
        out["median_ytm_rt"] = ytm[len(ytm) // 2]
    if px:
        out["share_below_par"] = round(sum(1 for x in px if x < 100.0) / len(px), 4)
    return out
