"""BLOG AND SOCIAL GROUNDS FOR THE ATTENTION/MOOD INDICES -- Japanese, Korean, Chinese retail.

WHAT IS NEW HERE AND WHAT IS REUSED. `foreign_sources` (Hatena Bookmark search, note, DCInside
search) and `cn_sources` (Juejin, Sogou-WeChat) already fetch titles and snippets by keyword; they
are CALLED, not copied. What they do not carry is what an attention index needs: a publication
time where the feed has one, an AUTHOR (the bot filter's burst test is per account), and the
retail forums proper. So this module adds:

  rss            any RSS 2.0 / RDF / Atom feed, with pubDate / dc:date / published and
                 dc:creator / author parsed (Hatena Bookmark keyword search and hot-entry
                 categories; Ameblo and livedoor public per-blog feeds named in the config file)
  dcinside_list  the DCInside stock-gallery LIST page, which carries a writer and a timestamp per
                 row where the search page carries neither
  weibo_mobile   Weibo's public mobile search JSON                    (expected WALLED; recorded)
  xueqiu_search  Xueqiu status search JSON behind its WAF             (expected WALLED; recorded)

NETWORK HONESTY. The cloud session that wrote this could reach none of these hosts (its proxy
answers 403 to CONNECT), so every parser is exercised on small fixtures and every live yield is
UNMEASURED until the trading box runs it. `fetch` returns a POSTURE per source -- OK / WALLED /
EMPTY, the same three `foreign_sources.probe_all` publishes -- so a blocked ground is never read as
an empty one.

ONLY TITLES AND SNIPPETS ARE KEPT, as everywhere in the desk's forest miners. `first_seen_at` is
stamped by the CALLER at fetch time and never overwritten; it is the index's PIT clock.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

from libs.data import foreign_sources as fs
from libs.research.social_mood import Post

POSTURE_OK, POSTURE_WALLED, POSTURE_EMPTY = fs.POSTURE_OK, fs.POSTURE_WALLED, fs.POSTURE_EMPTY
UNMEASURED_LIVE_YIELD = "UNMEASURED_LIVE_YIELD"

#: The instrument-tied keywords each region's crowd is searched for.
KEYWORDS: dict[str, tuple[str, ...]] = {
    "ja": ("日経平均", "日本株", "円安", "円高", "ドル円"),
    "ko": ("코스피", "삼성전자", "반도체", "환율"),
    "zh": ("A股", "港股", "人民币", "恒指"),
}

Getter = Callable[[str], str]


@dataclass(frozen=True)
class SourceSpec:
    """One ground. The roster row in /mnt/project-files/mining/asia_thread_sources.yaml is written
    from these fields, so the code and the roster cannot describe two different sources."""

    id: str
    name: str
    kind: str
    url: str
    region: str
    lang: str
    cadence: str = "hourly"
    auth: str = "none"
    licence: str = "public page; titles and snippets only, no bodies archived"
    cursor: str = "(source, ident) seen-set with first_seen_at"
    participant_structure: tuple[str, ...] = ("retail_heavy",)
    failure_mode_hypothesis: str = ""
    crowding_prior: str = "low"
    keyword: bool = True
    notes: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


SOURCES: tuple[SourceSpec, ...] = (
    SourceSpec(
        "hatena_bookmark_search_rss", "Hatena Bookmark keyword search (RSS)", "rss",
        "https://b.hatena.ne.jp/search/text?q={kw}&mode=rss", "JP", "ja",
        licence="public RSS; Hatena ToS permits feed reading, 6s pacing per foreign_sources",
        failure_mode_hypothesis=("JP retail attention peaks around the March tax-year end and "
                                 "NISA flows, not the US calendar, so its overreactions cluster "
                                 "on different dates than an English-news attention index"),
        notes="reuses foreign_sources pacing; the RSS carries dc:date and dc:creator"),
    SourceSpec(
        "hatena_hotentry_economics_rss", "Hatena Bookmark hot entries, economics", "rss",
        "https://b.hatena.ne.jp/hotentry/economics.rss", "JP", "ja", keyword=False,
        licence="public category RSS",
        failure_mode_hypothesis=("hot-entry ranking is crowd-voted by JP readers, so it lags "
                                 "Tokyo-session moves by hours and fails when a move is "
                                 "US-session led")),
    SourceSpec(
        "ameblo_user_rss", "Ameblo public blog feeds (configured ids)", "rss",
        "https://rssblog.ameba.jp/{id}/rss20.xml", "JP", "ja", keyword=False,
        licence="public per-blog RSS; ids listed in desks/mt5/data/blog_social_feeds.json",
        failure_mode_hypothesis=("Ameblo's investor bloggers are small-account Nikkei/FX "
                                 "retail, whose loss-driven capitulation posts come after the "
                                 "move, the opposite timing to institutional commentary"),
        notes="no feed id ships by default; the box operator lists them"),
    SourceSpec(
        "livedoor_user_rss", "livedoor Blog public feeds (configured ids)", "rss",
        "https://blog.livedoor.jp/{id}/index.rdf", "JP", "ja", keyword=False,
        licence="public per-blog RDF; ids listed in desks/mt5/data/blog_social_feeds.json",
        failure_mode_hypothesis=("livedoor 'matome' blogs aggregate 5ch market threads, so they "
                                 "measure the most leveraged JP retail crowd with a lag of a "
                                 "few hours"),
        notes="no feed id ships by default; the box operator lists them"),
    SourceSpec(
        "note_search", "note.com keyword search (foreign_sources.note)", "fs_note",
        "https://note.com/api/v3/searchs?q={kw}", "JP", "ja",
        failure_mode_hypothesis=("note writers are self-selected 'botter'/FX retail who post "
                                 "post-mortems after losses, so their mood lags drawdowns"),
        notes="endpoint answered 404 in foreign_sources' 2026-08-05 probe; kept, posture recorded"),
    SourceSpec(
        "dcinside_stock_gallery", "DCInside stock gallery list (neostock)", "dcinside_list",
        "https://gall.dcinside.com/board/lists/?id=neostock", "KR", "ko", keyword=False,
        licence="public forum list page; titles, nick and timestamp only",
        failure_mode_hypothesis=("KR retail is the majority of KOSPI turnover and trades with "
                                 "leveraged ETFs and margin, so its herding peaks on KRX "
                                 "limit days and foreign-selling days, not on US data"),
        notes="list page carries gall_writer data-nick/data-uid and gall_date title"),
    SourceSpec(
        "dcinside_search", "DCInside post search (foreign_sources.dcinside)", "fs_dcinside",
        "https://search.dcinside.com/post/q/{kw}", "KR", "ko",
        failure_mode_hypothesis=("keyword search surfaces KR retail threads across galleries; "
                                 "semis talk tracks Samsung/Hynix retail flows that front-run "
                                 "or lag US semis on KRX hours")),
    SourceSpec(
        "juejin_search", "Juejin search (cn_sources.juejin)", "cn_juejin",
        "https://api.juejin.cn/search_api/v1/search?query={kw}", "CN", "zh",
        participant_structure=("retail_heavy", "policy_driven"),
        crowding_prior="low",
        failure_mode_hypothesis=("A-share retail trades under T+1 and daily limits, so a "
                                 "mood extreme cannot be unwound same-day and reverses on a "
                                 "different clock than a T+0 market")),
    SourceSpec(
        "sogou_weixin_search", "Sogou WeChat article search (cn_sources.sogou_weixin)",
        "cn_sogou", "https://weixin.sogou.com/weixin?type=2&query={kw}", "CN", "zh",
        participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("WeChat public accounts amplify policy signals (State Council, "
                                 "national team) that retail then chases, so attention spikes "
                                 "follow policy days, not earnings"),
        notes="Sogou rate-limits hard and serves anti-bot pages; posture recorded"),
    SourceSpec(
        "weibo_mobile_search", "Weibo mobile search JSON", "weibo_mobile",
        "https://m.weibo.cn/api/container/getIndex?containerid=100103type%3D1%26q%3D{kw}",
        "CN", "zh", participant_structure=("retail_heavy", "policy_driven"),
        licence="public mobile endpoint; often requires login -- WALLED is the expected posture",
        failure_mode_hypothesis=("Weibo attention is censored and policy-steered, so negative "
                                 "mood is under-expressed and reversals follow policy "
                                 "support announcements")),
    SourceSpec(
        "xueqiu_status_search", "Xueqiu status search JSON", "xueqiu",
        "https://xueqiu.com/query/v1/search/status.json?q={kw}", "CN", "zh",
        participant_structure=("retail_heavy",), auth="cookie behind WAF",
        licence="public site behind a WAF; cn_sources recorded it unsolved 2026-08-01",
        failure_mode_hypothesis=("Xueqiu is the CN/HK retail stock-picker crowd; its mood "
                                 "extremes on HK names reverse with southbound-flow days")),
)
BY_ID: dict[str, SourceSpec] = {s.id: s for s in SOURCES}


# ------------------------------------------------------------------------------------ parsing
def _when(raw: str) -> datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


_KST = timedelta(hours=9)


def _kst(raw: str) -> datetime | None:
    """A bare `YYYY-MM-DD HH:MM:SS` from a Korean page is KST; the offset is applied, not guessed
    away as UTC (which would stamp every DCInside post nine hours late)."""
    m = re.match(r"(\d{4})[-./](\d{2})[-./](\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?",
                 (raw or "").strip())
    if not m:
        return None
    y, mo, d, hh, mm, ss = (int(x or 0) for x in m.groups())
    return datetime(y, mo, d, hh, mm, ss, tzinfo=UTC) - _KST


def parse_rss(body: str, source: str, lang: str, now: datetime) -> list[Post]:
    """RSS 2.0 <item>, RDF <item> and Atom <entry>; title required, link required."""
    blocks = fs._rss_items(body) or re.findall(r"<entry[^>]*>(.*?)</entry>", body, flags=re.S)
    out: list[Post] = []
    for b in blocks:
        title = fs._tag(b, "title")
        link = fs._tag(b, "link")
        if not link:
            m = re.search(r'<link[^>]*href="([^"]+)"', b)
            link = m.group(1) if m else ""
        if not title or not link:
            continue
        author = fs._tag(b, "dc:creator") or fs._tag(b, "name") or fs._tag(b, "author")
        pub = _when(fs._tag(b, "pubDate") or fs._tag(b, "dc:date") or fs._tag(b, "published")
                    or fs._tag(b, "updated"))
        snippet = (fs._tag(b, "description") or fs._tag(b, "summary"))[:360]
        out.append(Post(source=source, ident=link[-80:], title=title, first_seen_at=now,
                        snippet=snippet, author=author[:60], url=link, lang=lang,
                        published_at=pub))
    return out


def parse_dcinside_list(body: str, source: str, now: datetime) -> list[Post]:
    """One post per `<tr class="ub-content ...">` row: title, writer nick/uid, gall_date."""
    out: list[Post] = []
    for tr_attrs, row in re.findall(r'<tr([^>]*class="ub-content[^"]*"[^>]*)>(.*?)</tr>', body,
                                    flags=re.S):
        if "icon_notice" in tr_attrs or "icon_ad" in tr_attrs:
            continue                 # pinned notices and ads are the gallery's, not the crowd's
        a = re.search(r'<td[^>]*class="gall_tit[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                      row, flags=re.S)
        if not a:
            continue
        href, title = a.group(1), fs._text(a.group(2))
        if not title:
            continue
        w = re.search(r'class="gall_writer[^"]*"([^>]*)>', row)
        attrs = w.group(1) if w else ""
        uid = re.search(r'data-uid="([^"]*)"', attrs)
        ip = re.search(r'data-ip="([^"]*)"', attrs)
        nick = re.search(r'data-nick="([^"]*)"', attrs)
        author = ((uid.group(1) if uid and uid.group(1) else "")
                  or (f"{nick.group(1) if nick else ''}@{ip.group(1)}" if ip and ip.group(1)
                      else (nick.group(1) if nick else "")))
        d = re.search(r'class="gall_date"[^>]*title="([^"]+)"', row)
        link = href if href.startswith("http") else f"https://gall.dcinside.com{href}"
        no = re.search(r"no=(\d+)", href)
        out.append(Post(source=source, ident=no.group(1) if no else link[-60:], title=title,
                        first_seen_at=now, author=author, url=link, lang="ko",
                        published_at=_kst(d.group(1)) if d else None))
    return out


def parse_weibo(body: str, source: str, now: datetime) -> list[Post]:
    doc = json.loads(body)
    cards = ((doc.get("data") or {}).get("cards") or []) if isinstance(doc, dict) else []
    out: list[Post] = []
    for c in cards:
        groups = [c, *list(c.get("card_group") or [])] if isinstance(c, dict) else []
        for g in groups:
            mb = g.get("mblog") if isinstance(g, dict) else None
            if not isinstance(mb, dict) or not mb.get("id"):
                continue
            text = fs._text(str(mb.get("text") or ""))
            if not text:
                continue
            u = mb.get("user")
            user: dict[str, Any] = u if isinstance(u, dict) else {}
            out.append(Post(source=source, ident=str(mb["id"]), title=text[:200],
                            first_seen_at=now, author=str(user.get("id") or ""),
                            url=f"https://m.weibo.cn/status/{mb['id']}", lang="zh",
                            published_at=_when(str(mb.get("created_at") or ""))))
    return out


def parse_xueqiu(body: str, source: str, now: datetime) -> list[Post]:
    doc = json.loads(body)
    rows = doc.get("list") if isinstance(doc, dict) else None
    out: list[Post] = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        text = fs._text(str(r.get("title") or r.get("text") or r.get("description") or ""))
        if not text:
            continue
        u = r.get("user")
        user: dict[str, Any] = u if isinstance(u, dict) else {}
        ts = r.get("created_at")
        pub = (datetime.fromtimestamp(float(ts) / 1000.0, tz=UTC)
               if isinstance(ts, (int, float)) else None)
        out.append(Post(source=source, ident=str(r["id"]), title=text[:200], first_seen_at=now,
                        author=str(user.get("id") or ""), url=f"https://xueqiu.com/{r['id']}",
                        lang="zh", published_at=pub))
    return out


def _from_articles(arts: Sequence[Any], source: str, lang: str, now: datetime) -> list[Post]:
    return [Post(source=source, ident=str(a.ident), title=str(a.title), first_seen_at=now,
                 snippet=str(a.snippet or ""), author=str(a.author or ""), url=str(a.url),
                 lang=lang) for a in arts]


# ------------------------------------------------------------------------------------ fetching
def _default_get(url: str) -> str:
    return fs._get(url, timeout=20.0)


def _urls(spec: SourceSpec, feed_ids: Sequence[str]) -> list[tuple[str, str]]:
    if "{id}" in spec.url:
        return [(spec.url.format(id=quote(i)), i) for i in feed_ids]
    if spec.keyword and "{kw}" in spec.url:
        return [(spec.url.format(kw=quote(k)), k) for k in KEYWORDS.get(spec.lang, ())]
    return [(spec.url, "")]


def fetch(spec: SourceSpec, now: datetime, *, get: Getter | None = None,
          feed_ids: Sequence[str] = (), pause_s: float = 1.5) -> dict[str, Any]:
    """Every request this ground needs this pass. Never raises; returns posts and a posture."""
    getter = get or _default_get
    posts: list[Post] = []
    errors: list[str] = []
    calls = 0
    lang = spec.lang
    if spec.kind in ("fs_note", "fs_dcinside", "cn_juejin", "cn_sogou") and get is None:
        from libs.data import cn_sources as cn
        table: dict[str, Callable[[str], tuple[Sequence[Any], str | None]]] = {
            "fs_note": fs.note, "fs_dcinside": fs.dcinside, "cn_juejin": cn.juejin,
            "cn_sogou": cn.sogou_weixin}
        fn = table[spec.kind]
        for kw in KEYWORDS.get(lang, ()):
            calls += 1
            try:
                arts, err = fn(kw)
            except Exception as exc:
                arts, err = [], f"{type(exc).__name__}: {str(exc)[:120]}"
            if err:
                errors.append(str(err)[:160])
            posts += _from_articles(arts, spec.id, lang, now)
    else:
        targets = _urls(spec, feed_ids)
        if not targets:
            return {"id": spec.id, "posture": "UNCONFIGURED", "n": 0, "calls": 0, "posts": [],
                    "errors": ["no feed id configured in desks/mt5/data/blog_social_feeds.json"]}
        for i, (url, _label) in enumerate(targets):
            if i and pause_s > 0:
                time.sleep(pause_s)
            calls += 1
            try:
                body = getter(url)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {str(exc)[:120]}")
                continue
            try:
                got = parse_body(spec, body, now)
            except Exception as exc:
                errors.append(f"parse {type(exc).__name__}: {str(exc)[:100]}")
                continue
            posts += got
    posture = (POSTURE_OK if posts else POSTURE_WALLED if errors else POSTURE_EMPTY)
    return {"id": spec.id, "posture": posture, "n": len(posts), "calls": calls, "posts": posts,
            "errors": errors[:5]}


def parse_body(spec: SourceSpec, body: str, now: datetime) -> list[Post]:
    if spec.kind == "rss":
        return parse_rss(body, spec.id, spec.lang, now)
    if spec.kind == "dcinside_list":
        return parse_dcinside_list(body, spec.id, now)
    if spec.kind == "weibo_mobile":
        return parse_weibo(body, spec.id, now)
    if spec.kind == "xueqiu":
        return parse_xueqiu(body, spec.id, now)
    raise ValueError(f"no body parser for kind {spec.kind!r}")
