"""CROWD VENUES -- the public places where each country's retail trading crowd actually talks.

WHY THIS FILE EXISTS (zuck 2026-11-03): "tap into the local niches of every country ... where most
of their trading crowd is". The desk already read the ENGINEERING writing of a few languages
(foreign_sources: Qiita, Zenn, Habr ...) and one Chinese article index (cn_sources: Sogou-WeChat).
It did not read the BIG CROWDS: Eastmoney Guba (China's largest retail board), Baidu Tieba,
niconico, Yahoo! Finance Japan boards, 5ch market boards, Naver stock discussion, and the Discourse
forums India's retail crowd uses (Zerodha TradingQnA, ValuePickr). Every one is mined here
LOGGED OUT, at a polite per-source pace, and STOPS FOR THE RUN on the first 429 or access wall.

HARD LIMITS, NOT PREFERENCES (and the reason some famous venues are absent):
  * no login, no cookies, no proxies, no IP rotation, no CAPTCHA solving, no paywall bypass;
  * a captcha / security-check / login page is an ACCESS WALL: the source is backed off for the
    rest of the process and the error says so -- never retried around;
  * WeChat GROUPS, Xueqiu search, Baidu Index, Weibo search, Zhihu search, Stockbit and
    KakaoTalk need an account or a cookie and are therefore NOT built (see crowd_venues.json,
    status BLOCKED_AUTH). Public WeChat ARTICLES are already read through cn_sources.sogou_weixin.

Only titles, snippets and tags are kept, as for every other forest: they feed the mechanism-claim
extractor (which reads zh/ja/ko natively) and the claim goes to the gauntlet. Nothing here can
reach live sizing.

EVERY PARSER IS DEFENSIVE AND UNMEASURED FROM THE CLOUD (the container has no egress to these
hosts). Each returns (rows, error); "no rows parsed" is reported as an error naming the likely
cause, so the box's first run tells us which parser needs a fix instead of silently scoring zero.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Final
from urllib.parse import quote

from libs.data.foreign_sources import Article, _err, _text

#: Seconds between two requests to one source. Crowd boards are run by companies that throttle
#: scrapers hard, so these start conservative; the box run re-measures them.
_MIN_INTERVAL_S: Final[dict[str, float]] = {
    "niconico": 2.0,
    "guba": 3.0,
    "tieba": 5.0,
    "yahoo_jp_board": 4.0,
    "fivech": 4.0,
    "naver_board": 3.0,
    "discourse": 2.5,
}

#: Strings that mean "this is an access wall, not content". Seeing one backs the source off.
_WALL_MARKERS: Final[tuple[str, ...]] = (
    "百度安全验证", "wappass.baidu.com", "安全验证", "请输入验证码", "captcha", "CAPTCHA",
    "recaptcha", "hcaptcha", "cf-challenge", "Just a moment...", "Access Denied",
    "ログインしてください", "로그인이 필요", "請登入", "请登录",
)

_UA: Final[dict[str, str]] = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/html, */*",
}

_LAST: dict[str, float] = {}
_STOPPED: dict[str, str] = {}


def _pace(source: str) -> None:
    gap = _MIN_INTERVAL_S.get(source.split(":")[0], 2.0)
    last = _LAST.get(source)
    if last is not None:
        wait = gap - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _LAST[source] = time.monotonic()


def _stopped(source: str) -> tuple[list[Article], str] | None:
    why = _STOPPED.get(source)
    return ([], f"{source} stopped for this run: {why}") if why else None


def _stop(source: str, why: str) -> None:
    _STOPPED.setdefault(source, why)


def reset() -> None:
    """Forget per-process stop/pace state (tests; a new run in the same process)."""
    _LAST.clear()
    _STOPPED.clear()


def _decode(raw: bytes, content_type: str, default: str = "utf-8") -> str:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        enc = m.group(1)
    else:
        mb = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4096], re.I)
        enc = mb.group(1).decode("ascii", "ignore") if mb else default
    enc = {"x-sjis": "shift_jis", "sjis": "shift_jis", "ms932": "cp932",
           "euc-kr": "cp949", "gb2312": "gb18030", "gbk": "gb18030"}.get(enc.lower(), enc)
    try:
        return raw.decode(enc, errors="ignore")
    except LookupError:
        return raw.decode(default, errors="ignore")


def _get(url: str, *, referer: str = "", lang: str = "", default_enc: str = "utf-8",
         timeout: float = 25.0) -> str:
    hdr = dict(_UA)
    if referer:
        hdr["Referer"] = referer
    if lang:
        hdr["Accept-Language"] = f"{lang},{lang.split('-')[0]};q=0.9,en;q=0.5"
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return _decode(fh.read(), fh.headers.get("Content-Type", ""), default_enc)


def _fetch(source: str, url: str, **kw: Any) -> tuple[str | None, str | None]:
    """Paced GET with the two stop rules: HTTP 429 and an access wall both stop the source."""
    _pace(source)
    try:
        body = _get(url, **kw)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 403, 401):
            _stop(source, f"HTTP {exc.code} (rate limit / access refused) -- not retried")
        return None, _err(exc)
    except Exception as exc:
        return None, _err(exc)
    head = body[:20000]
    for marker in _WALL_MARKERS:
        if marker in head:
            _stop(source, f"access wall ({marker!r}) -- never bypassed")
            return None, f"{source}: access wall ({marker!r}); stopped for this run"
    return body, None


def _walk_dicts(node: Any, depth: int = 0) -> list[dict[str, Any]]:
    """Every dict inside a JSON tree (bounded), for APIs whose shape drifts."""
    if depth > 12:
        return []
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            out.extend(_walk_dicts(v, depth + 1))
    elif isinstance(node, list):
        for v in node:
            out.extend(_walk_dicts(v, depth + 1))
    return out


def _tags_text(tags: Any) -> str:
    if isinstance(tags, str):
        tags = tags.split()
    if not isinstance(tags, list):
        return ""
    return " ".join(f"#{str(t).strip()}" for t in tags[:20] if str(t).strip())


# ------------------------------------------------------------------------------ JAPAN (ja)

def niconico(keyword: str, *, limit: int = 50) -> tuple[list[Article], str | None]:
    """niconico video via the OFFICIAL public Snapshot Search API v2 (documented, keyless).
    Title + description + tags; tags become `#tag` so the query learner can expand from them."""
    hit = _stopped("niconico")
    if hit:
        return hit
    url = ("https://snapshot.search.nicovideo.jp/api/v2/snapshot/video/contents/search"
           f"?q={quote(keyword)}&targets=title,description,tags"
           "&fields=contentId,title,description,tags,viewCounter,startTime"
           f"&_sort=-startTime&_limit={int(limit)}&_context=quant-research-miner")
    body, err = _fetch("niconico", url)
    if body is None:
        return [], err
    try:
        doc = json.loads(body)
    except Exception as exc:
        return [], f"niconico: non-JSON answer ({_err(exc)})"
    rows = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return [], "niconico: no `data` list -- API shape changed"
    out: list[Article] = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("contentId"):
            continue
        cid = str(r["contentId"])
        out.append(Article(source="niconico", ident=cid, title=_text(str(r.get("title") or "")),
                           url=f"https://www.nicovideo.jp/watch/{cid}",
                           snippet=(_text(str(r.get("description") or ""))[:400] + " "
                                    + _tags_text(r.get("tags"))).strip()))
    return out, None


def yahoo_jp_board(code: str) -> tuple[list[Article], str | None]:
    """Yahoo! Finance Japan 掲示板 for one quote code (e.g. 1540.T gold ETF, 1542.T silver,
    1671.T WTI, 998407.O Nikkei). Japan's single biggest retail board. Server-rendered page; the
    comment texts are read from the embedded state JSON, falling back to visible text."""
    hit = _stopped("yahoo_jp_board")
    if hit:
        return hit
    url = f"https://finance.yahoo.co.jp/quote/{quote(code)}/forum"
    body, err = _fetch("yahoo_jp_board", url, lang="ja-JP")
    if body is None:
        return [], err
    texts: list[str] = []
    m = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*</script>", body, re.S)
    if m:
        try:
            for d in _walk_dicts(json.loads(m.group(1))):
                for k in ("body", "comment", "text", "message"):
                    v = d.get(k)
                    if isinstance(v, str) and len(v) >= 12:
                        texts.append(_text(v))
        except Exception:
            pass
    if not texts:
        texts = [_text(x) for x in re.findall(r"<p[^>]*class=\"[^\"]*(?:comment|Comment|body)"
                                              r"[^\"]*\"[^>]*>(.*?)</p>", body, re.S)]
    texts = [t for t in dict.fromkeys(texts) if len(t) >= 12][:60]
    if not texts:
        return [], "yahoo_jp_board: page fetched, no comments parsed -- markup changed"
    return [Article(source="yahoo_jp_board", ident=f"{code}:{i}", title=t[:80], url=url,
                    snippet=t[:400]) for i, t in enumerate(texts)], None


def fivech(board: str) -> tuple[list[Article], str | None]:
    """5ch market boards: thread titles from the public subject list, e.g.
    `egg.5ch.net/stockb` (株式), `egg.5ch.net/market` (市況), `kizuna.5ch.net/livemarket1`."""
    hit = _stopped("fivech")
    if hit:
        return hit
    host_board = board.strip("/")
    url = f"https://{host_board}/subback.html"
    body, err = _fetch("fivech", url, default_enc="cp932", lang="ja-JP")
    if body is None:
        return [], err
    out: list[Article] = []
    for href, title in re.findall(r'<a href="([^"]+)"[^>]*>\s*\d+:\s*(.*?)</a>', body, re.S):
        t = re.sub(r"\(\d+\)\s*$", "", _text(title)).strip()
        if not t:
            continue
        host, _, b = host_board.partition("/")
        tid = href.split("/")[0]
        out.append(Article(source="fivech", ident=f"{b}:{tid}", title=t,
                           url=f"https://{host}/test/read.cgi/{b}/{tid}/"))
    if not out:
        return [], "fivech: subject list fetched, no threads parsed -- markup changed"
    return out[:120], None


# ------------------------------------------------------------------------------ CHINA (zh)

def guba(keyword: str, *, size: int = 20) -> tuple[list[Article], str | None]:
    """Eastmoney 股吧 post search -- China's largest retail investor board. Public search JSON
    used by the logged-out site; parsed shape-tolerantly (any dict with a title)."""
    hit = _stopped("guba")
    if hit:
        return hit
    param = {"uid": "", "keyword": keyword, "type": ["gubaArticleWeb"], "client": "web",
             "clientVersion": "curr", "clientType": "web",
             "param": {"gubaArticleWeb": {"searchScope": "default", "sort": "time",
                                          "pageIndex": 1, "pageSize": int(size),
                                          "preTag": "", "postTag": ""}}}
    url = ("https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param="
           + quote(json.dumps(param, ensure_ascii=False, separators=(",", ":"))))
    body, err = _fetch("guba", url, referer="https://so.eastmoney.com/", lang="zh-CN")
    if body is None:
        return [], err
    m = re.search(r"^[\w$.]*\((.*)\)\s*;?\s*$", body.strip(), re.S)
    try:
        doc = json.loads(m.group(1) if m else body)
    except Exception as exc:
        return [], f"guba: unparseable answer ({_err(exc)})"
    out: list[Article] = []
    seen: set[str] = set()
    for d in _walk_dicts(doc.get("result") if isinstance(doc, dict) else doc):
        title = _text(str(d.get("title") or d.get("postTitle") or ""))
        if not title:
            continue
        pid = str(d.get("postId") or d.get("post_id") or d.get("id") or "")
        link = str(d.get("url") or "")
        if not link and pid:
            code = str(d.get("code") or d.get("stockbarCode") or "")
            link = f"https://guba.eastmoney.com/news,{code},{pid}.html"
        key = pid or link or title
        if key in seen:
            continue
        seen.add(key)
        out.append(Article(source="guba", ident=key[-40:], title=title,
                           url=link or "https://guba.eastmoney.com/",
                           author=str(d.get("nickname") or d.get("userNickName") or ""),
                           snippet=_text(str(d.get("content")
                                             or d.get("postContent") or ""))[:400]))
    if not out and '"result"' not in body:
        return [], "guba: answer had no `result` -- API shape changed"
    return out, None


def tieba(keyword: str) -> tuple[list[Article], str | None]:
    """Baidu 贴吧 full-text post search (public, logged out). Baidu answers bots with a security
    check page; that is an access wall and stops the source for the run."""
    hit = _stopped("tieba")
    if hit:
        return hit
    url = f"https://tieba.baidu.com/f/search/res?ie=utf-8&qw={quote(keyword)}"
    body, err = _fetch("tieba", url, referer="https://tieba.baidu.com/", lang="zh-CN",
                       default_enc="gb18030")
    if body is None:
        return [], err
    out: list[Article] = []
    for block in re.findall(r'<div class="s_post">(.*?)</div>\s*</div>', body, re.S) or \
            re.findall(r'<div class="s_post">(.*?)<div class="s_post"', body, re.S):
        a = re.search(r'<a[^>]+href="(/p/\d+[^"]*)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        snip = re.search(r'<div class="p_content[^"]*">(.*?)</div>', block, re.S)
        bar = re.search(r'class="p_forum"[^>]*>(.*?)</a>', block, re.S)
        out.append(Article(source="tieba", ident=a.group(1)[:40], title=_text(a.group(2)),
                           url=f"https://tieba.baidu.com{_text(a.group(1))}",
                           author=_text(bar.group(1)) if bar else "",
                           snippet=_text(snip.group(1))[:400] if snip else ""))
    if not out and "s_post" in body:
        return [], "tieba: result blocks present, none parsed -- markup changed"
    return out, None


# ------------------------------------------------------------------------------ KOREA (ko)

def naver_board(code: str) -> tuple[list[Article], str | None]:
    """Naver Finance 종목토론실 (the stock discussion room), one KRX code per call, e.g.
    132030 KODEX 골드선물(H), 144600 KODEX 은선물(H), 261220 KODEX WTI원유선물(H). Korea's largest
    retail board; titles only from the public list page."""
    hit = _stopped("naver_board")
    if hit:
        return hit
    url = f"https://finance.naver.com/item/board.naver?code={quote(code)}"
    body, err = _fetch("naver_board", url, referer="https://finance.naver.com/",
                       lang="ko-KR", default_enc="cp949")
    if body is None:
        return [], err
    out: list[Article] = []
    for href, title in re.findall(
            r'<a href="(/item/board_read\.naver\?code=\d+&(?:amp;)?nid=\d+[^"]*)"[^>]*'
            r'title="([^"]+)"', body):
        h = href.replace("&amp;", "&")
        out.append(Article(source="naver_board", ident=h.split("nid=")[-1][:20],
                           title=_text(title), url=f"https://finance.naver.com{h}"))
    if not out:
        return [], "naver_board: list fetched, no posts parsed -- markup changed"
    return out, None


# ------------------------------------------------------------------------ DISCOURSE (any)

def discourse(spec: str) -> tuple[list[Article], str | None]:
    """Any public Discourse forum's documented search JSON. `spec` is `host::query`, e.g.
    `tradingqna.com::gold` (Zerodha's retail Q&A, India) or `forum.valuepickr.com::commodity`."""
    host, sep, q = spec.partition("::")
    if not sep or not host or not q:
        return [], "discourse: spec must be host::query"
    hit = _stopped(f"discourse:{host}")
    if hit:
        return hit
    url = f"https://{host}/search.json?q={quote(q)}"
    # Keyed per HOST: one forum's 429 or wall never stops a different forum.
    body, err = _fetch(f"discourse:{host}", url)
    if body is None:
        return [], err
    try:
        doc = json.loads(body)
    except Exception as exc:
        return [], f"discourse {host}: non-JSON ({_err(exc)})"
    topics = {t.get("id"): t for t in (doc.get("topics") or []) if isinstance(t, dict)}
    out: list[Article] = []
    for p in doc.get("posts") or []:
        if not isinstance(p, dict):
            continue
        t = topics.get(p.get("topic_id")) or {}
        title = _text(str(t.get("title") or p.get("name") or ""))
        slug = str(t.get("slug") or "t")
        out.append(Article(source=f"discourse:{host}", ident=str(p.get("id")), title=title,
                           url=(f"https://{host}/t/{slug}/{p.get('topic_id')}/"
                                f"{p.get('post_number', 1)}"),
                           author=str(p.get("username") or ""),
                           snippet=_text(str(p.get("blurb") or ""))[:400]))
    return out, None


#: The deep-forest route allowlist for `route: crowd` grounds (fn name -> callable).
CROWD_FNS: Final[dict[str, Any]] = {
    "niconico": niconico, "yahoo_jp_board": yahoo_jp_board, "fivech": fivech,
    "guba": guba, "tieba": tieba, "naver_board": naver_board, "discourse": discourse,
}


def probe_all() -> list[dict[str, Any]]:
    """One cheap call per fn, same contract as foreign_sources.probe_all (OK/WALLED/EMPTY)."""
    probes = {"niconico": "金価格", "yahoo_jp_board": "1540.T", "fivech": "egg.5ch.net/stockb",
              "guba": "黄金", "tieba": "黄金 期货", "naver_board": "132030",
              "discourse": "tradingqna.com::gold"}
    out: list[dict[str, Any]] = []
    for name, kw in probes.items():
        try:
            arts, err = CROWD_FNS[name](kw)
        except Exception as exc:
            arts, err = [], _err(exc)
        out.append({"source": name, "ok": bool(arts) and err is None, "n": len(arts),
                    "posture": "WALLED" if err else ("OK" if arts else "EMPTY"), "error": err})
    return out
