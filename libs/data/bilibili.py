"""Bilibili (B站) research discovery: WBI-signed search and structured video metadata.

WHY THIS EXISTS. Bilibili's search API answers HTTP 412 to an unsigned request, which the desk
first recorded as simply "blocked". It is not blocked -- it requires WBI request signing, which is
a documented client-side algorithm and is implemented here. Once signed, the API returns code 0
and real results. That is the same shape as lesson L0052 (a 403 that was a User-Agent bot filter):
a deterministic protocol requirement recorded as an outage.

WHAT IS AND IS NOT AVAILABLE, measured on 2026-08-01 rather than assumed:

    WBI-signed search        WORKS -- 20 results/page, paginated, any keyword
    video detail (/view)     WORKS -- title, description, tags, duration, view count, author
    player/wbi/v2            WORKS -- returns code 0
    SUBTITLE TRACKS          EMPTY without login. Measured across 14 quant videos: 0 of 14
                             exposed a subtitle track to an unauthenticated request.

So this is a DISCOVERY source, not a transcript source, and the module does not pretend otherwise.
That is the same conclusion the YouTube path reached by a different route, and it is worth stating
plainly: on both platforms the desk can find out what exists and rank it, and cannot read it.

WHAT MAKES IT WORTH HAVING ANYWAY. Bilibili's API returns STRUCTURED metadata -- description,
tags, duration, play count -- where the YouTube listing gives a title and nothing else. The
desk's triage ranker scores text, so a description and a tag list are several times more signal
per candidate than a title alone. The Chinese-language quant scene is also largely absent from
English YouTube results, so this is genuinely new coverage rather than a second view of the same
material.

ONLY METADATA IS STORED. The miner keeps titles, descriptions and tags for RANKING -- deciding
what a human should go and watch. It does not archive video content.
"""

from __future__ import annotations

import hashlib
import html
import json
import time
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

_UA = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    # The Referer is REQUIRED. Without it the API returns 412 even with a valid signature --
    # which is the failure most likely to be misread as "the signing is wrong".
    "Referer": "https://www.bilibili.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

#: The WBI mixin-key permutation table. A fixed client-side constant, not a secret and not
#: derived -- the key it produces rotates because its INPUTS rotate (see `wbi_keys`), which is
#: the whole point of the scheme.
_MIXIN_TAB = (
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19,
    29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
)

_API = "https://api.bilibili.com"
_CACHE: dict[str, tuple[float, str]] = {}
#: The WBI keys rotate daily. Re-fetching them on every call would be a needless request per
#: search page; caching them forever would start failing silently at the rotation boundary.
_KEY_TTL = 1800.0


def _get(url: str, *, timeout: float = 25.0) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body: str = fh.read().decode("utf8", errors="ignore")
    return body


def _get_json(url: str, *, timeout: float = 25.0) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(_get(url, timeout=timeout))
    return parsed


def wbi_keys() -> str:
    """The 32-char mixin key, cached for its rotation window.

    Built from the two image filenames the nav endpoint hands out: concatenate them, reorder by
    the permutation table, truncate to 32. The keys rotate, which is why this is fetched rather
    than hardcoded -- a pinned key works until it silently does not.
    """
    now = time.time()
    hit = _CACHE.get("mixin")
    if hit and now - hit[0] < _KEY_TTL:
        return hit[1]
    img = _get_json(f"{_API}/x/web-interface/nav")["data"]["wbi_img"]
    ik = str(img["img_url"]).rsplit("/", 1)[-1].split(".")[0]
    sk = str(img["sub_url"]).rsplit("/", 1)[-1].split(".")[0]
    raw = ik + sk
    mixin = "".join(raw[i] for i in _MIXIN_TAB if i < len(raw))[:32]
    _CACHE["mixin"] = (now, mixin)
    return mixin


def signed_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET a WBI-signed endpoint.

    The signature is md5(sorted-urlencoded-params-including-wts + mixin_key). Parameter ORDER is
    load-bearing: the server re-sorts and re-hashes, so an unsorted query string produces a valid
    request with an invalid signature and a 412 that looks exactly like a block.
    """
    p = dict(params)
    p["wts"] = int(time.time())
    query = urlencode(sorted(p.items()))
    p["w_rid"] = hashlib.md5((query + wbi_keys()).encode()).hexdigest()
    return _get_json(f"{_API}{path}?{urlencode(sorted(p.items()))}")


@dataclass(frozen=True)
class Video:
    bvid: str
    title: str
    author: str = ""
    description: str = ""
    tags: tuple[str, ...] = ()
    duration_s: int = 0
    views: int = 0
    published: int = 0

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def searchable(self) -> str:
        """Everything the triage ranker should score: title, description and tags together.

        Bilibili titles are frequently marketing ("B站最全教程!"), while the description and tags
        carry the method words that actually predict conversion. Scoring the title alone would
        systematically under-rank the exact material worth finding.
        """
        return " ".join([self.title, self.description, " ".join(self.tags)])


def search(keyword: str, *, page: int = 1, order: str = "") -> tuple[list[Video], str | None]:
    """WBI-signed video search. Returns (videos, error).

    ERRORS ARE RETURNED, NOT RAISED, so one bad keyword in a daily sweep does not abort the other
    eleven -- the same rule the YouTube miner follows.
    """
    params: dict[str, Any] = {"search_type": "video", "keyword": keyword, "page": page}
    if order:
        params["order"] = order
    try:
        body = signed_get("/x/web-interface/wbi/search/type", params)
    except Exception as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:140]}"
    if body.get("code") != 0:
        return [], f"bilibili code={body.get('code')} msg={body.get('message')}"
    # AN EMPTY RESULT SET IS A REFUSAL, NEVER "NO MATCHES", and that is measured rather than
    # assumed. Bilibili's search answers a keyword that cannot possibly match anything
    # (`zzqqxxjjvv不存在的关键词9182`) with numResults=1000 and 20 generic fallback rows -- it does
    # not have an empty state for a text query. So `code=0` with nothing in `result` means the API
    # declined to serve THIS request, and returning ([], None) for it tells the caller the query
    # was healthy and the corpus was empty. Both halves of that are false.
    #
    # THE COST, measured on the 2026-08-06 06:33 sweep: 17 of 34 queries -- the LAST 17, contiguous,
    # after ~68 signed requests -- came back ([], None). The miner recorded them as healthy zeros,
    # so half the desk's highest-yielding source silently produced nothing, appeared in no blocked
    # list, opened no route hunt and reached the source-health ledger as HEALTHY. The same queries
    # returned 19 rows each when re-run standalone minutes later. Third instance of one class on
    # the Chinese lane (after the CJK word-boundary bug and the Sogou attribute-order bug): the
    # FETCH was fine and the desk was told there was nothing there.
    data = body.get("data") or {}
    rows = data.get("result") or []
    if not rows:
        return [], ("bilibili returned code=0 with an empty result set -- a SOFT REFUSAL, not an "
                    f"empty corpus (numResults={data.get('numResults')!r}); this API serves "
                    "fallback rows even for a nonsense keyword, so it has no genuine empty state")
    out: list[Video] = []
    for r in rows:
        bvid = str(r.get("bvid") or "")
        if not bvid:
            continue
        out.append(Video(
            bvid=bvid,
            title=_strip(str(r.get("title") or "")),
            author=str(r.get("author") or ""),
            description=_strip(str(r.get("description") or "")),
            tags=tuple(t for t in str(r.get("tag") or "").split(",") if t),
            duration_s=_dur(str(r.get("duration") or "")),
            views=int(r.get("play") or 0),
            published=int(r.get("pubdate") or 0),
        ))
    return out, None


def subtitle_status(bvid: str) -> dict[str, Any]:
    """Does this video expose a subtitle track to an UNAUTHENTICATED request?

    Kept as a probe rather than deleted, because the answer is a fact about today's auth policy
    and not about the code. Measured 2026-08-01: 0 of 14 quant videos exposed one. If that ever
    changes, this is what notices -- and the desk gets a real transcript source rather than a
    discovery-only one.
    """
    try:
        view = _get_json(f"{_API}/x/web-interface/view?bvid={bvid}")
        data = view.get("data") or {}
        cid = data.get("cid") or ((data.get("pages") or [{}])[0].get("cid"))
        player = signed_get("/x/player/wbi/v2",
                            {"aid": data.get("aid"), "cid": cid, "bvid": bvid})
        subs = ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        return {"bvid": bvid, "reachable": True, "n_tracks": len(subs),
                "languages": [s.get("lan") for s in subs]}
    except Exception as exc:
        return {"bvid": bvid, "reachable": False,
                "error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def _strip(text: str) -> str:
    """Search results wrap matched terms in <em> highlight tags.

    ENTITIES ARE DECODED AFTER TAG REMOVAL (2026-08-05), and the order is the whole point: unescape
    first and an encoded `&lt;em&gt;` would BECOME a tag this stripper then eats, silently deleting
    the text between two literal angle brackets that were never markup.

    Why it matters beyond tidiness. The stripped title is what video_triage SCORES, so an entity
    the ranker cannot read is a keyword the ranker cannot see. `&quot;` merely looks untidy in a
    Latin title; a NUMERIC entity is the real hazard, because `&#x91CF;&#x5316;` is exactly how
    `量化` arrives from some encoders -- the scorer would find no Chinese at all and rank a
    perfectly relevant article at zero. That is the CJK `\\b` bug's failure mode reached through a
    different door: a real edge made invisible to the gate rather than rejected by it.
    """
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return html.unescape("".join(out)).strip()


def _dur(text: str) -> int:
    """'12:34' or '1:02:03' -> seconds. Zero when unparseable rather than raising."""
    try:
        parts = [int(p) for p in text.split(":")]
    except ValueError:
        return 0
    total = 0
    for p in parts:
        total = total * 60 + p
    return total
