"""Chinese-language research discovery beyond Bilibili: Juejin (Sogou/WeChat is off-limits).

MEASURED 2026-08-01 from this box, because every one of these was previously recorded as simply
"blocked" and most of them were not:

    Juejin (掘金) search API   WORKS -- clean JSON, err_no 0, ~20 results per query. A large
                              Chinese developer community with substantial quant content.
    Sogou WeChat search       OFF-LIMITS (principal): never fetched, see libs/data/off_limits.py.
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
    from libs.data.off_limits import off_limits, redirected_off_limits
    refused = off_limits(url)
    if refused:
        raise PermissionError(refused)
    req = urllib.request.Request(url, headers={**_UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        hop = redirected_off_limits(url, fh.geturl())
        if hop:
            raise PermissionError(hop)
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
    """REFUSED, ALWAYS: WeChat (and Sogou, its public index) is a ground the principal put
    off-limits. Kept as a function so the callers that still route a `sogou` ground here
    (deep_forest_miner, blog_social_sources) receive a named refusal, never a request. The
    HTML parser it used to carry is gone with the fetch; see libs/data/off_limits.py."""
    from libs.data.off_limits import WHY, off_limits
    url = f"https://weixin.sogou.com/weixin?type=2&query={quote(keyword)}"
    return [], off_limits(url) or WHY


def probe_all() -> list[dict[str, Any]]:
    """One-line reachability for every declared source, re-measured rather than trusted.

    The desk has already been burned treating a recorded HTTP failure as permanent when it was a
    header problem (L0052) and treating a 412 as a block when it was a signing requirement. A
    declared status is a prior; this is the evidence.
    """
    rows: list[dict[str, Any]] = []
    items, err = juejin("量化 回测")
    rows.append({"source": "juejin", "ok": err is None, "n": len(items), "error": err})
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
