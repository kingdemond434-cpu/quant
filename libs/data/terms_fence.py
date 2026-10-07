"""PLATFORM TERMS FENCES -- the named platforms whose own agreement bars this desk's automated use.

WHY THIS FILE EXISTS (2026-09-30, the project coordinator's Reddit ruling). Reddit's User Agreement
and its Data API terms govern ALL automated access -- the OAuth API, the anonymous `.json`
listings and the `.rss` feeds alike -- and require a separate agreement for commercial use. This
desk is commercial and holds no such agreement, so no Reddit-derived data may feed a cell, the
lake, trading or allocation. It is the same basis as the earlier Discord ruling (bot token only,
never a user token) and the keyed-sources fence on #144 (`machine_use_allowed=false` on the Reddit
OAuth rows). StockTwits is fenced on the same basis: its Terms s.5 forbid extracting data "by
automated means except as expressly authorized by us in writing or through an approved API", and
it licenses that data commercially instead.

HOW THIS SITS WITH LAWS s.5e, stated so a later session does not read it as a re-introduced brake.
s.5e deleted SELF-IMPOSED discovery brakes -- a robots Disallow, a generic `machine_use_allowed`
label, a quarantine on ACCESS_UNCLEAR -- because none of them "was ever a legal requirement". This
is not a label read as a refusal: it is a short, NAMED list of platforms whose contract with every
automated reader requires an agreement the desk does not hold, each with the ruling that put it
here. Nothing else is fenced by it, it never generalises from a label, and an entry leaves the
list the day an agreement exists (set `agreement` on the entry, with its reference).

THE FENCE IS AT THE SOURCE, and it is one function per question:

    fenced_url(url)      -> the terms reason when the URL is on a fenced platform, else None
    fenced_row(row, src) -> the platform when a discovery row came from one, else None
    check_url(url)       -> raises TermsFenced; the one guard every fetch helper calls
    check_request(u, h)  -> check_url plus the Discord rule (bot token only, never a user token)
    guarded_urlopen(req) -> urlopen whose REDIRECTS are fenced too (FencedRedirectHandler)
    quarantined_row(row) -> the platform when a row must not be judged (docket, backtest)
    quarantined_certificate(key) -> the refusal for a certificate judged under a fenced lineage

The fenced platforms (2026-09-30 ruling): Reddit and its mirrors (pushshift, pullpush,
photon-reddit), StockTwits, X/Twitter (no paid X, no scraping), and the Discord user token.
Wikipedia pageviews and GDELT are the substitutes; the gate fails closed.

NO BYPASS (audit of #162, 2026-10-07). A fence that matches one spelling of one host is walked
around, so the platform is matched however it is addressed: every Reddit FRONT-END (redlib,
libreddit, teddit, reveddit, unddit -- any host label naming one) is Reddit, every nitter mirror
and fork (any host label containing "nitter", xcancel, ...) is X, and a WRAPPER of a fenced URL
-- web.archive.org, archive.ph/.today/.is/.li/.vn/.md, r.jina.ai, 12ft.io, Google cache,
`*.translate.goog` and translate.google.com -- is the URL it wraps. Hosts are compared only after
`normalize_host` (NFKC, IDNA, lowercase, trailing dot stripped), so a fullwidth `reddit.com`
and REDDIT.COM. are reddit.com. The redirect guard calls the same `check_url`, so all of it
holds for every hop of a redirect chain too.

Every refusal carries its reason and its status, BLOCKED_WITH_SUBSTITUTE when the information
class it served has a lawful substitute wired (`substitutes`), so no fenced route ever reads as
silent, dead or UNMEASURED.

FENCED ROWS ARE QUARANTINED, NOT JUDGED (audit of #162, 2026-10-06). The organs that write
docket and candidate rows stamp `provenance_label` with the entry's `label` (`reddit_fenced`)
through `label_row`, and the docket build (merge_hypotheses) and the backtest stage
(run_external_backtest) then SKIP every `quarantined_row` with a counted reason, so no fenced
row reaches a judge. A certificate already earned under a fenced lineage is refused promotion
until re-certified on a clean one (`quarantined_certificate`).
"""
from __future__ import annotations

import contextlib
import json
import re
import unicodedata
import urllib.request
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

BLOCKED_WITH_SUBSTITUTE = "BLOCKED_WITH_SUBSTITUTE"
BLOCKED_TERMS = "BLOCKED_TERMS"

#: The Reddit ruling, verbatim in every artifact that refuses a Reddit route.
REDDIT_TERMS_REASON = (
    "Reddit's User Agreement and Data API terms cover all automated access, including RSS and the "
    "anonymous JSON listings, and require a separate agreement for commercial use; this desk is "
    "commercial and holds none, so no Reddit data may feed cells, the lake, trading or allocation "
    "(project coordinator ruling 2026-09-30, same basis as the Discord ruling)")

STOCKTWITS_TERMS_REASON = (
    "StockTwits Terms s.5 forbid extracting data from the Service by automated means except as "
    "expressly authorized in writing or through an approved API, and s.8 reserves commercial "
    "licensing of that data to StockTwits; the desk holds no authorization, so no StockTwits data "
    "may feed cells, the lake, trading or allocation (checked 2026-09-30 at "
    "stocktwits.com/about/legal/terms)")

X_PAID_REASON = (
    "X's Developer Agreement makes its paid API the only authorized automated access and its Terms "
    "forbid crawling or scraping without prior written consent; the principal ruled no paid X "
    "(2026-09-30), so no X/Twitter data is fetched by any route -- API, web or mirror -- and none "
    "may feed cells, the lake, trading or allocation")

DISCORD_USER_REASON = (
    "Discord's Terms and Developer Policy permit automation only through a bot account; a user "
    "token driving the API is a self-bot and is barred (the Discord ruling: bot token only, never "
    "a user token; principal 2026-09-30). A discord.com API request is refused unless it is "
    "authorized as `Bot <token>` or carries no credential at all")

#: platform -> the fence. `hosts` match the registrable domain and every subdomain. `sources` are
#: the discovery-row source names (intelligence directory / `source` field) the platform wrote.
PLATFORMS: dict[str, dict[str, Any]] = {
    "reddit": {
        # pushshift / pullpush / photon-reddit are Reddit MIRRORS: the data is Reddit's and the
        # ruling covers it wherever it is served from.
        # redlib / libreddit / teddit / reveddit / unddit are Reddit FRONT-ENDS: every page they
        # serve is fetched from Reddit, so they are Reddit under the same ruling (audit of #162,
        # 2026-10-07). `host_labels` fences ANY host with a DNS label containing one of them, so
        # an instance nobody listed yet is fenced too.
        "hosts": ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com",
                  "reddituploads.com", "redditblog.com", "pushshift.io", "pullpush.io",
                  "photon-reddit.com", "reveddit.com", "unddit.com", "libredd.it",
                  "safereddit.com", "troddit.com", "removeddit.com", "ceddit.com",
                  "resavr.com"),
        "host_labels": ("redlib", "libreddit", "teddit", "reveddit", "unddit"),
        "sources": ("reddit", "miner:reddit", "pushshift", "pullpush", "photon_reddit",
                    "redlib", "libreddit", "teddit", "reveddit", "unddit"),
        "source_prefixes": ("ext_reddit_", "reddit_", "pushshift_", "pullpush_", "redlib_",
                            "libreddit_", "teddit_"),
        "routes": ("reddit", "redlib", "libreddit", "teddit"),
        "reason": REDDIT_TERMS_REASON,
        "status": BLOCKED_WITH_SUBSTITUTE,
        "label": "reddit_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        # The information class Reddit served -- retail attention and practitioner chatter -- and
        # the lawful doors that now carry it (desks/mt5/research/attention_substitutes.py).
        "substitutes": ("wikipedia_pageviews", "gdelt_doc_timeline", "google_trends"),
    },
    "stocktwits": {
        "hosts": ("stocktwits.com",),
        "sources": ("stocktwits", "miner:stocktwits"),
        "source_prefixes": ("stocktwits_",),
        "routes": ("stocktwits",),
        "reason": STOCKTWITS_TERMS_REASON,
        "status": BLOCKED_WITH_SUBSTITUTE,
        "label": "stocktwits_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        "substitutes": ("wikipedia_pageviews", "gdelt_doc_timeline", "google_trends"),
    },
    "x_paid": {
        # Nitter and its forks are X MIRRORS: every page is X's data fetched from X, so no
        # mirror is a lawful route to it (audit of #162, 2026-10-07: deep_forest's `nitter`
        # route still reached X through nitter.privacydev.net and nitter.poast.org). Any host
        # with a DNS label containing "nitter" is fenced, plus the forks that dropped the name.
        "hosts": ("x.com", "twitter.com", "api.twitter.com", "api.x.com", "twimg.com",
                  "nitter.net", "nitter.privacydev.net", "nitter.poast.org", "nitter.cz",
                  "nitter.it", "nitter.1d4.us", "nitter.kavin.rocks", "nitter.unixfox.eu",
                  "nitter.moomoo.me", "nitter.fdn.fr", "nitter.lacontrevoie.fr",
                  "nitter.esmailelbob.xyz", "nitter.woodland.cafe", "nitter.space",
                  "xcancel.com", "twiiit.com", "fxtwitter.com", "vxtwitter.com",
                  "fixupx.com", "fixvx.com", "twstalker.com", "sotwe.com"),
        "host_labels": ("nitter",),
        "sources": ("twitter", "x_twitter", "twitter_api", "x_api", "miner:twitter", "nitter",
                    "xcancel"),
        "source_prefixes": ("twitter_", "nitter_"),
        "routes": ("twitter", "x_api", "nitter"),
        "reason": X_PAID_REASON,
        "status": BLOCKED_WITH_SUBSTITUTE,
        "label": "x_paid_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        "substitutes": ("gdelt_doc_timeline", "wikipedia_pageviews"),
    },
    # A REQUEST-LEVEL fence, not a host fence: a bot token is allowed, so discord.com itself is
    # not refused -- a discord API request authorized by anything but `Bot <token>` is
    # (`check_request`). `hosts` here are only the hosts that rule reads.
    "discord_user": {
        "hosts": ("discord.com", "discordapp.com"),
        "url_fenced": False,
        "sources": (),
        "source_prefixes": (),
        "routes": ("discord_user",),
        "reason": DISCORD_USER_REASON,
        "status": BLOCKED_TERMS,
        "label": "discord_user_fenced",
        "fenced_at": "2026-09-30T00:00:00+00:00",
        "agreement": None,
        "substitutes": ("discord_bot_token",),
    },
}

#: Hosts whose path or query WRAPS another URL: an archive, cache, reader or proxy copy of a
#: fenced page IS that page (audit of #162, 2026-10-07). Each wraps its target its own way; the
#: target is extracted (`_wrapped_url`) and fenced exactly as if it had been asked for directly.
_ARCHIVE_HOSTS = ("web.archive.org", "archive.org")
_ARCHIVE_TODAY = ("archive.ph", "archive.today", "archive.is", "archive.li", "archive.vn",
                  "archive.md", "archive.fo")
_READER_HOSTS = ("r.jina.ai", "12ft.io")
_GOOGLE_CACHE = ("webcache.googleusercontent.com",)
_GOOGLE_TRANSLATE = ("translate.google.com", "translate.googleusercontent.com")
#: Google Translate's proxy encodes the target host into ONE label of `*.translate.goog`:
#: every "." becomes "-" and every original "-" is doubled (www-reddit-com.translate.goog).
_TRANSLATE_GOOG = "translate.goog"
#: Full stops that IDNA treats as label separators (ideographic, fullwidth, halfwidth).
_DOTS = ("\u3002", "\uff0e", "\uff61")


class TermsFenced(RuntimeError):
    """A fetch was asked for a URL on a fenced platform. Carries the platform and its reason."""

    def __init__(self, platform: str, url: str) -> None:
        self.platform = platform
        self.reason = str(PLATFORMS[platform]["reason"])
        self.status = str(PLATFORMS[platform]["status"])
        super().__init__(f"{self.status}:{platform}: {url[:120]} -- {self.reason}")


def _active(platform: str) -> bool:
    return not PLATFORMS[platform].get("agreement")


def normalize_host(host: str) -> str:
    """The one spelling a host is matched under: percent-decoded, NFKC (fullwidth and
    compatibility forms fold to ASCII: a fullwidth reddit.com -> reddit.com), every IDNA full stop
    made a dot, IDNA-encoded where it can be (non-ASCII labels become their xn-- form, which
    is the host a resolver would actually be asked for), lowercased, trailing dot stripped.
    A host that will not encode keeps its NFKC form, so it is still matched, never dropped."""
    h = unicodedata.normalize("NFKC", unquote(str(host or "")).strip())
    for d in _DOTS:
        h = h.replace(d, ".")
    h = h.lower().rstrip(".")
    if h and not h.isascii():
        with contextlib.suppress(UnicodeError, ValueError):
            h = h.encode("idna").decode("ascii")
    return h.lower().rstrip(".")


def _parse(url: str) -> ParseResult | None:
    # NFKC first: a fullwidth solidus or colon in the authority would otherwise make urlsplit raise,
    # and an unparseable URL must not read as an unfenced one.
    u = unicodedata.normalize("NFKC", str(url or "")).strip()
    for d in _DOTS:
        u = u.replace(d, ".")
    if not u:
        return None
    # A scheme with collapsed or missing slashes (`https:/reddit.com`, `//reddit.com`) is
    # still that host.
    u = re.sub(r"^([A-Za-z][A-Za-z0-9+.-]*):/*", r"\1://", u) if re.match(
        r"^[A-Za-z][A-Za-z0-9+.-]*:/", u) else u
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", u):
        # Schemeless (`archive.li/?url=https://...` carries "://" only in its QUERY).
        u = "https://" + u.lstrip("/")
    try:
        return urlparse(u)
    except ValueError:
        return None


def _host(url: str) -> str:
    parts = _parse(url)
    if parts is None:
        return ""
    try:
        raw = parts.hostname or ""
    except ValueError:
        return ""
    return normalize_host(raw)


def _host_platform(h: str, *, request_level: bool = False) -> str | None:
    h = normalize_host(h)
    labels = h.split(".") if h else []
    for name, p in PLATFORMS.items():
        if not _active(name) or bool(p.get("url_fenced", True)) == request_level:
            continue
        for dom in p["hosts"]:
            if h == dom or h.endswith("." + dom):
                return name
        for frag in p.get("host_labels") or ():
            if any(frag in lab for lab in labels):
                return name
    return None


def _on(h: str, roots: tuple[str, ...]) -> bool:
    return any(h == a or h.endswith("." + a) for a in roots)


def _decode_translate_goog(label: str) -> str:
    """`www-reddit-com` -> `www.reddit.com`: Google's proxy turns "." into "-" and doubles an
    original "-"."""
    return label.replace("--", "\x00").replace("-", ".").replace("\x00", "-")


def _embedded(rest: str) -> str | None:
    """The target inside a reader / archive path: the first `scheme:/...` in it, else the first
    path segment that looks like a host (has a dot), with everything after it."""
    rest = unquote(rest or "").lstrip("/")
    if not rest:
        return None
    m = re.search(r"[A-Za-z][A-Za-z0-9+.-]*:/+\S*", rest)
    if m:
        return m.group(0)
    segs = rest.split("/")
    for i, seg in enumerate(segs):
        if "." in seg and not seg.replace(".", "").isdigit():
            return "/".join(segs[i:])
    return None


def _wrapped_url(url: str) -> str | None:
    """The URL (or bare host) a wrapper address wraps, else None. An archived, cached, proxied,
    translated or reader-mode copy of a fenced page is the fenced page:

        web.archive.org/web/<ts>/<url>, archive.org/wayback/available?url=<url>
        archive.ph|today|is|li|vn|md/[newest/|oldest/|<ts>/]<url>, ...?url=<url>
        r.jina.ai/<url>, 12ft.io/[proxy?q=]<url>
        webcache.googleusercontent.com/search?q=cache:[<id>:]<url>
        <host-with-dashes>.translate.goog/<path>, translate.google.com/translate?u=<url>
    """
    parts = _parse(url)
    if parts is None:
        return None
    try:
        h = normalize_host(parts.hostname or "")
    except ValueError:
        return None
    if not h:
        return None
    qs = parse_qs(parts.query)
    tail = ("?" + parts.query) if parts.query else ""
    if h.endswith("." + _TRANSLATE_GOOG):
        sub = h[: -len("." + _TRANSLATE_GOOG)]
        return _decode_translate_goog(sub.split(".")[-1]) + (parts.path or "/")
    if _on(h, _GOOGLE_TRANSLATE):
        for k in ("u", "url", "sl_url"):
            if qs.get(k):
                return unquote(qs[k][0])
        return None
    if _on(h, _GOOGLE_CACHE):
        q = unquote((qs.get("q") or [""])[0])
        if q.lower().startswith("cache:"):
            q = q[len("cache:"):]
            m = re.match(r"^[A-Za-z0-9_-]{6,}:(?!//)(.+)$", q)
            if m and "." in m.group(1).split("/")[0]:
                q = m.group(1)
            return q or None
        return None
    if _on(h, _ARCHIVE_HOSTS):
        qv = qs.get("url")
        if qv:
            return unquote(str(qv[0]))
        segs = parts.path.split("/", 3)
        if len(segs) == 4 and segs[1] == "web" and segs[3]:
            return segs[3] + tail
        return None
    if _on(h, _ARCHIVE_TODAY) or _on(h, _READER_HOSTS):
        for k in ("url", "q", "u"):
            if qs.get(k):
                inner = _embedded(qs[k][0])
                if inner:
                    return inner
        inner = _embedded(parts.path)
        return (inner + tail) if inner else None
    return None


def platform_of_url(url: str, _depth: int = 0) -> str | None:
    """The fenced platform a URL belongs to, or None. Subdomains match (old.reddit.com), and so
    does an archive copy (web.archive.org/web/2026/https://www.reddit.com/...). Request-level
    platforms (discord_user) never fence a bare URL; `check_request` reads them."""
    h = _host(url)
    if not h:
        return None
    p = _host_platform(h)
    if p:
        return p
    inner = _wrapped_url(url) if _depth < 4 else None
    return platform_of_url(inner, _depth + 1) if inner else None


def fenced_url(url: str) -> str | None:
    """The terms reason when `url` is on a fenced platform, else None."""
    p = platform_of_url(url)
    return str(PLATFORMS[p]["reason"]) if p else None


def check_url(url: str) -> None:
    """Raise `TermsFenced` for a URL on a fenced platform. EVERY fetch helper calls this first."""
    p = platform_of_url(url)
    if p:
        raise TermsFenced(p, str(url))


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    for k, v in (headers.items() if hasattr(headers, "items") else []):
        if str(k).lower() == name.lower():
            return str(v or "")
    return ""


def fenced_request(url: str, headers: Any = None) -> str | None:
    """The fenced platform a REQUEST belongs to: `platform_of_url`, plus the Discord rule -- a
    discord.com / discordapp.com API request authorized by anything but `Bot <token>` (a user
    token, `/users/@me` driven as a person) is a self-bot and is refused. No credential at all is
    not a user token, so a public, unauthenticated endpoint stays open."""
    p = platform_of_url(url)
    if p:
        return p
    h = _host(url)
    d = _host_platform(h, request_level=True) if h else None
    if d == "discord_user":
        auth = _header(headers, "Authorization").strip()
        path = urlparse(url if "://" in url else "https://" + url).path.lower()
        if path.startswith("/api") and auth and not auth.startswith("Bot "):
            return d
    return None


def check_request(url: str, headers: Any = None) -> None:
    """Raise `TermsFenced` for a request `fenced_request` refuses."""
    p = fenced_request(url, headers)
    if p:
        raise TermsFenced(p, str(url))


def _req_headers(req: urllib.request.Request) -> dict[str, str]:
    return {**dict(req.unredirected_hdrs), **dict(req.headers)}


class FencedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """urllib's redirect handler, except a 30x pointing at a fenced platform raises `TermsFenced`
    instead of being followed. A fence that checks only the FIRST URL is a fence any shortener or
    moved page walks straight through."""

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        check_url(newurl)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            check_request(new.full_url, _req_headers(new))
        return new


class TermsGuardProcessor(urllib.request.BaseHandler):
    """Runs on EVERY request the opener sends, the first and each redirected one: a fenced
    request raises before a connection is opened."""

    handler_order = 100

    def http_request(self, req: urllib.request.Request) -> urllib.request.Request:
        check_request(req.full_url, _req_headers(req))
        return req

    https_request = http_request


def guarded_opener(context: Any = None, *handlers: Any) -> urllib.request.OpenerDirector:
    """An opener whose redirects and requests are terms-fenced. `context` is the SSL context the
    caller would have passed to `urlopen`."""
    hs: list[Any] = [FencedRedirectHandler(), TermsGuardProcessor()]
    if context is not None:
        hs.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*hs, *handlers)


def guarded_urlopen(req: Any, *, timeout: float = 30.0, context: Any = None) -> Any:
    """`urllib.request.urlopen` with the fence: the URL is checked BEFORE any request is built,
    and a redirect to a fenced host raises `TermsFenced` instead of being followed."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    hdrs = _req_headers(req) if isinstance(req, urllib.request.Request) else None
    check_request(url, hdrs)
    return guarded_opener(context).open(req, timeout=timeout)


#: Generic producer prefixes stripped from a source name before it is matched, so
#: `external_reddit`, `ext_reddit_EURUSD_x` and `miner_stocktwits` read as their platform.
_SOURCE_PREFIXES = ("external_", "ext_", "miner_", "seat_", "src_", "source_", "intel_",
                    "side_")


def _source_forms(source: str) -> list[str]:
    """The spellings one source name is matched under: as given, with every `ns:` namespace
    stripped (`miner:asia:stocktwits_macro` -> `stocktwits_macro`), and with generic producer
    prefixes stripped from that (`external_reddit` -> `reddit`). Only WHOLE prefixes come off,
    so `redditch_weather` stays `redditch_weather` and matches nothing."""
    s = str(source or "").strip().lower()
    if not s:
        return []
    forms = [s]
    tail = s.rsplit(":", 1)[-1].strip()
    for _ in range(4):
        if tail and tail not in forms:
            forms.append(tail)
        nxt = next((tail[len(x):] for x in _SOURCE_PREFIXES if tail.startswith(x)), tail)
        if nxt == tail:
            break
        tail = nxt
    return forms


def fenced_source(source: str) -> str | None:
    """The platform a discovery SOURCE name belongs to ("reddit", "miner:reddit",
    "ext_reddit_EURUSD_...", "asia:stocktwits_macro", "external_reddit"), or None."""
    forms = _source_forms(source)
    if not forms:
        return None
    for name, p in PLATFORMS.items():
        if not _active(name):
            continue
        for f in forms:
            if f in p["sources"] or any(f.startswith(x) for x in p["source_prefixes"]):
                return name
    return None


_URL_FIELDS = ("url", "link", "source_url", "permalink", "canonical_url")


def fenced_row(row: Mapping[str, Any], source: str = "") -> str | None:
    """The fenced platform a discovery / candidate / docket row came from, or None.

    A row is platform-derived when its intake source, its own `source`, any `contributing_sources`
    entry, its `route` (deep_forest's ground route) or any of its URL fields names the platform.
    `contributing_sources` makes a cell that ANOTHER miner also proposed count as touched; the
    labeller stamps it, but the compiler refuses only the fenced ROW, so the other miner's
    proposal still reaches the docket on its own evidence.
    """
    if not isinstance(row, Mapping):
        return None
    for s in (source, row.get("source"), row.get("origin"), row.get("miner")):
        p = fenced_source(str(s or ""))
        if p:
            return p
    route = str(row.get("route") or "").split(":", 1)[0].lower()
    for name, spec in PLATFORMS.items():
        if _active(name) and route in spec["routes"]:
            return name
    for f in _URL_FIELDS:
        v = row.get(f)
        if isinstance(v, str):
            p2 = platform_of_url(v)
            if p2:
                return p2
    return None


def fenced_ground(g: Mapping[str, Any]) -> str | None:
    """The fenced platform a registered GROUND belongs to -- its route, url, site or feeds -- or
    None. Read by the deep-forest miner (never fetch it, never schedule it) and by
    `research/forest_attempts.py` (a fenced ground is neither never-attempted nor overdue)."""
    if not isinstance(g, Mapping):
        return None
    route = str(g.get("route") or "").lower()
    for name, spec in PLATFORMS.items():
        if _active(name) and route in spec["routes"]:
            return name
    for k in ("url", "site", "feed"):
        p = platform_of_url(str(g.get(k) or ""))
        if p:
            return p
    # Every address the ground could be fetched from: its feeds and its MIRRORS (a nitter
    # ground lists its mirrors bare: `nitter.poast.org`).
    for k in ("feeds", "mirrors", "urls", "seeds"):
        for f in g.get(k) or []:
            p = platform_of_url(str(f or ""))
            if p:
                return p
    return None


def touched_row(row: Mapping[str, Any]) -> str | None:
    """`fenced_row`, plus any contributing source -- the LABELLER's test (a cell one fenced
    platform helped propose carries the label even when another miner proposed it too)."""
    p = fenced_row(row)
    if p:
        return p
    cs = row.get("contributing_sources") if isinstance(row, Mapping) else None
    for s in cs if isinstance(cs, list) else []:
        p = fenced_source(str(s or ""))
        if p:
            return p
    return None


def label_row(row: dict[str, Any]) -> str | None:
    """Stamp `provenance_label` (and `terms_fence`) on a row a fenced platform touched.

    Returns the label it stamped, or None. Idempotent. `provenance` itself is NOT overwritten:
    several readers treat it as a dict (`(row.get("provenance") or {}).get(...)`), so a string
    there would crash them. Nothing about the row's verdict, identity or ordering changes.
    """
    p = touched_row(row)
    if not p:
        return None
    lab = str(PLATFORMS[p]["label"])
    row["provenance_label"] = lab
    row["terms_fence"] = {"platform": p, "status": PLATFORMS[p]["status"],
                          "reason": PLATFORMS[p]["reason"]}
    return lab


_LABELS = {str(p["label"]): name for name, p in PLATFORMS.items()}


def quarantined_row(row: Mapping[str, Any]) -> str | None:
    """THE QUARANTINE TEST (fails closed): the platform when a docket / candidate / backtest row
    is fenced by its own source, route or URL, was touched by a fenced contributing source, or
    already carries a fenced `provenance_label`. A quarantined row is NOT judged: the docket
    build and the backtest stage skip it and count it. None for a clean row."""
    if not isinstance(row, Mapping):
        return None
    p = touched_row(row)
    if p:
        return p
    lab = str(row.get("provenance_label") or "")
    if lab in _LABELS:
        return _LABELS[lab]
    tfv = row.get("terms_fence")
    if isinstance(tfv, Mapping) and str(tfv.get("platform") or "") in PLATFORMS:
        return str(tfv["platform"])
    return None


#: CERTIFICATES JUDGED UNDER A FENCED LINEAGE (audit of #162, 2026-10-06). The three STANDBY
#: USDJPY session_range_breakout sleeves were certified from `ext_reddit_USDJPY_session_range_
#: breakout` (Reddit-sourced external_backtest_results.json rows). They are refused promotion and
#: capital until the cell is RE-CERTIFIED on the Forex Factory / central-bank lineage alone: the
#: re-certification rows sit in desks/mt5/data/hypotheses/terms_recert_queue.json, which
#: merge_hypotheses admits to the docket on every run, and a certificate counts as re-earned only
#: when its `gated_at` is AFTER `requeued_at` -- judged from a docket every fenced row is now
#: quarantined out of. The rr=2.5 certificate came from the same lineage and has no sleeve; it is
#: held the same way so it cannot become one.
QUARANTINED_CERTIFICATES: dict[str, dict[str, Any]] = {
    f"external.USDJPY.session_range_breakout{sfx}": {
        "platform": "reddit", "lineage": "ext_reddit_USDJPY_session_range_breakout",
        "symbol": "USDJPY", "family": "session_range_breakout", "selector": "asia",
        "params": params, "sleeve": sleeve,
        "recert_lineage": ("forexfactory", "central_bank"),
        "requeued_at": "2026-10-06T00:00:00+00:00"}
    for sfx, params, sleeve in (
        ("", {}, "usdjpy_session_range_breakout_asia_session_range_breakout"),
        (".rr=1.5_wb=12", {"rr": 1.5, "wait_bars": 12},
         "usdjpy_session_range_breakout_asia_5_wb_12"),
        (".rr=2.0_wb=12", {"rr": 2.0, "wait_bars": 12},
         "usdjpy_session_range_breakout_asia_0_wb_12"),
        (".rr=2.5_wb=12", {"rr": 2.5, "wait_bars": 12}, None))
}


def _after_iso(a: Any, b: Any) -> bool:
    try:
        x, y = datetime.fromisoformat(str(a)), datetime.fromisoformat(str(b))
    except (TypeError, ValueError):
        return False
    if x.tzinfo is None or y.tzinfo is None:
        return False
    return x > y


def _norm_params(p: Any) -> dict[str, float | str]:
    out: dict[str, float | str] = {}
    for k, v in (p.items() if isinstance(p, Mapping) else []):
        if k == "timeframe":
            continue
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            out[str(k)] = str(v)
    return out


def quarantined_certificate(key: str = "", *, spec: Mapping[str, Any] | None = None,
                            sleeve: str = "", gated_at: Any = None) -> str | None:
    """The refusal when a certificate -- named by key, by sleeve, or by its spec's symbol /
    family / selector / params -- was judged under a fenced lineage and has NOT been re-certified
    since its re-certification was queued; None otherwise. Read by the promoter and the
    allocator (sealed: through the patches under /mnt/project-files/patches/pr162_*)."""
    k = str(key or "")
    for ck, q in QUARANTINED_CERTIFICATES.items():
        hit = bool(k) and (k == ck or k == ck.split(".", 1)[1])
        hit = hit or (bool(sleeve) and sleeve == q.get("sleeve"))
        if not hit and isinstance(spec, Mapping):
            hit = (str(spec.get("symbol") or spec.get("sym") or "").upper() == q["symbol"]
                   and str(spec.get("family") or "") == q["family"]
                   and str(spec.get("selector") or spec.get("window") or "") == q["selector"]
                   and _norm_params(spec.get("params")) == _norm_params(q["params"]))
        if not hit:
            continue
        if gated_at is not None and _after_iso(gated_at, q["requeued_at"]):
            return None
        p = PLATFORMS[q["platform"]]
        return (f"{p['status']}:{q['platform']}: certificate {ck} was judged under the fenced "
                f"lineage {q['lineage']}; refused promotion and capital until re-certified on the "
                f"{' / '.join(q['recert_lineage'])} lineage alone (queued {q['requeued_at']} in "
                f"data/hypotheses/terms_recert_queue.json)")
    return None


def recert_queue_rows() -> list[dict[str, Any]]:
    """The docket rows that re-certify each quarantined certificate on its clean lineage --
    the content of data/hypotheses/terms_recert_queue.json, derived here so the file and the
    quarantine can never disagree."""
    return [{"symbol": q["symbol"], "family": q["family"], "selector": q["selector"],
             "params": dict(q["params"]),
             "source": "terms_recert:" + "+".join(q["recert_lineage"]),
             "lineage": list(q["recert_lineage"]), "recertifies": ck,
             "replaces_lineage": q["lineage"], "sleeve": q["sleeve"],
             "requeued_at": q["requeued_at"], "status": "QUEUED"}
            for ck, q in QUARANTINED_CERTIFICATES.items()]


def registry_rows() -> list[dict[str, Any]]:
    """One row per fenced platform, for the source registry and the roster reports."""
    return [{"platform": name, "status": p["status"] if _active(name) else "AGREEMENT_HELD",
             "reason": p["reason"], "label": p["label"], "fenced_at": p["fenced_at"],
             "hosts": list(p["hosts"]), "substitutes": list(p["substitutes"]),
             "agreement": p.get("agreement")}
            for name, p in PLATFORMS.items()]


def refusal(platform: str, **extra: Any) -> dict[str, Any]:
    """The artifact a fenced route writes instead of data: status, platform, reason, substitutes."""
    p = PLATFORMS[platform]
    return {"status": p["status"], "platform": platform, "reason": p["reason"],
            "why": f"terms fence ({platform}): {p['reason']}",
            "substitutes": list(p["substitutes"]), "fetched": 0, **extra}


if __name__ == "__main__":
    print(json.dumps(registry_rows(), indent=1))
