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

import json
import re
import urllib.request
from dataclasses import dataclass
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
        html = _get(url, referer="https://weixin.sogou.com/")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    if "antispider" in html or "请输入验证码" in html:
        return [], "sogou served an anti-bot challenge (rate limited)"
    out: list[Article] = []
    seen: set[str] = set()
    # ORDER-AGNOSTIC. The anchor carries href BEFORE uigs, so a regex that demanded uigs first
    # matched nothing while the page was perfectly healthy -- the parse reported "markup changed"
    # on 10 present results. Match any anchor tagged as an article title, then pull href out of
    # whatever position it occupies.
    for m in re.finditer(r'<a\b([^>]*uigs="article_title[^>]*)>(.*?)</a>', html, flags=re.S):
        attrs, raw = m.group(1), m.group(2)
        href_m = re.search(r'href="([^"]+)"', attrs)
        if not href_m:
            continue
        href = href_m.group(1)
        title = re.sub(r"<[^>]+>", "", raw).strip()
        if not title or href in seen:
            continue
        seen.add(href)
        link = href if href.startswith("http") else f"https://weixin.sogou.com{href}"
        out.append(Article(source="wechat", ident=href[-24:], title=title, url=link))
    if not out:
        return [], "page fetched but no article links parsed -- markup changed or empty result"
    return out, None


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
            rows.append({"source": name, "ok": False, "reachable": True, "bytes": len(body),
                         "error": note})
        except Exception as exc:
            rows.append({"source": name, "ok": False, "reachable": False,
                         "error": f"{type(exc).__name__}: {str(exc)[:90]} :: {note}"})
    return rows
