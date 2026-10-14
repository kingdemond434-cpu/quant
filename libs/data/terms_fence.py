"""PER-SOURCE POLICY -- how this desk may reach each source. NO SOURCE IS BANNED.

THE RULING (principal 2026-10-13, verbatim: "no its not banned wtv dont ban it i never banned it"
/ "no source should be banned"). This module used to hold a list of fenced PLATFORMS (Reddit,
StockTwits, X, the Discord user token) refused as a category. That list is retired. Every source
is now one row of `SOURCE_POLICY`, with a status and a one-line `why`:

    API_PERMITTED   an official API or free tier, within its published limits; NEEDS_KEY when the
                    row's key is absent from the environment (presence is checked, never read);
    PUBLIC_PAGE     fetch the public page politely (any host not listed);
    IDEAS_ONLY      read public posts for mechanism IDEAS; never live input data -- a cell built
                    from the idea trades on the desk's own MT5 data;
    METHOD_BLOCKED  only when the ONLY route would bypass a login, paywall, CAPTCHA, rate limit
                    or region lock (the reason is named; a permitted route is offered).

WHAT STAYS OFF IS THE METHOD, NOT THE SOURCE: bypassing a login, paywall, CAPTCHA, rate limit or
region lock; stolen data; MNPI. So the fetch guard (`check_url`, `guarded_urlopen`, the redirect
handler) refuses only a HELD source (METHOD_BLOCKED, or NEEDS_KEY until its key exists) and a
redirect INTO a login wall; an anti-bot or CAPTCHA page is recorded and never routed around.

IDEA PROVENANCE NEVER BLOCKS A CELL (rule 4). `fenced_row` / `quarantined_row` answer only for a
row whose LIVE INPUT DATA is declared from an IDEAS_ONLY or held source; a row whose idea came from
Reddit, X or any forum is labelled (`label_row`) and judged like any other. No certificate is
quarantined for its idea lineage (the 2026-10-07 certificate quarantine and its re-certification
queue are retired with the fence).

The function names are kept from the fence this replaces, so every caller reads the new policy:

    policy_of_url(url)   -> the effective row for a URL (wrappers resolve to what they wrap)
    platform_of_url(url) -> the HELD source key for a URL, else None
    check_url / check_request / guarded_urlopen -> raise TermsFenced for a held source or a
                            redirect into a login wall (the Discord rule: a user token driving the
                            API is a self-bot -> METHOD_BLOCKED; a bot token is the official API)
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any
from urllib.parse import ParseResult, parse_qs, unquote, urlparse

API_PERMITTED = "API_PERMITTED"
PUBLIC_PAGE = "PUBLIC_PAGE"
IDEAS_ONLY = "IDEAS_ONLY"
METHOD_BLOCKED = "METHOD_BLOCKED"
NEEDS_KEY = "NEEDS_KEY"
#: A source whose own terms page has not been read into its row (`terms`). For LIVE INPUT this is
#: never read as permitted: only a row's quoted clause, or the desk's PUBLIC_PAGE default for an
#: unlisted host, is the evidence a live-input organ acts on.
UNREAD = "UNREAD"
#: The statuses that HOLD a source (nothing is fetched from it).
HOLDING: frozenset[str] = frozenset({METHOD_BLOCKED, NEEDS_KEY})
#: Kept names: older artifacts and callers spell a refusal with these.
BLOCKED_WITH_SUBSTITUTE = "BLOCKED_WITH_SUBSTITUTE"
BLOCKED_TERMS = "BLOCKED_TERMS"

#: Reddit's Data API wiki, read 2026-10-13 (the User Agreement page was SITE_BLOCKED to the reader).
_REDDIT_DATA_API_WIKI = ("https://support.reddithelp.com/hc/en-us/articles/"
                         "16160319875092-Reddit-Data-API-Wiki")
_REDDIT_DATA_API_CLAUSES: dict[str, str] = {
    "rate_limits": ("We enforce rate limits for those eligible for free access usage of our "
                    "Data API."),
    "qpm": "100 queries per minute (QPM) per OAuth client id",
    "oauth": ("Reddit requires OAuth for authentication. Clients must authenticate with a "
              "registered OAuth token."),
    "unauthenticated": ("Traffic not using OAuth or login credentials will be blocked, and the "
                        "default rate limit will not apply."),
}

#: THE TABLE. One row per source (or host family). `hosts` match the domain and every subdomain;
#: `host_labels` match any DNS label containing the fragment; `sources` / `source_prefixes` are
#: discovery-row source names; `routes` are deep-forest ground routes. `why` is one line.
#: `permits_live_input` (optional, default False) is the row's explicit claim that its own terms
#: permit AUTOMATED LIVE INPUT for internal research (series-level readers such as
#: `recorders/vol_archive.py` act on it). It is VALIDATED at import (`validate_permits_live_input`):
#: a row may carry it True only with status API_PERMITTED or PUBLIC_PAGE AND its own terms page
#: (`terms.url`) AND at least one verbatim clause (`terms.clauses`). Absent or False is never
#: read as permission; a True without that evidence fails the import, never silently admits.
SOURCE_POLICY: dict[str, dict[str, Any]] = {
    "x_api": {"hosts": ("api.x.com", "api.twitter.com"), "status": API_PERMITTED,
              "key_env": ("X_BEARER_TOKEN",), "routes": ("x_api", "twitter_api"),
              "sources": ("x_api", "twitter_api"),
              "why": "X's official API: the permitted route to X posts, within its tier limits"},
    "x_web": {"hosts": ("x.com", "twitter.com", "twimg.com", "t.co", "fxtwitter.com",
                        "vxtwitter.com", "fixupx.com", "fixvx.com"),
              "status": IDEAS_ONLY, "sources": ("twitter", "x_twitter", "miner:twitter"),
              "source_prefixes": ("twitter_",), "routes": ("twitter",),
              "why": ("public X posts may be read for ideas; never live input data: X's terms "
                      "page refused the reader (robots) on 2026-10-13, so its terms are UNREAD "
                      "and UNREAD terms never permit automated live input; data goes through "
                      "x_api"),
              "terms": {"url": "https://x.com/en/tos", "checked_at": "2026-10-13",
                        "unread": {"https://x.com/en/tos":
                                   "ROBOTS_DISALLOWED to the reader on 2026-10-13: UNREAD"}}},
    "nitter": {"hosts": ("xcancel.com", "twiiit.com", "twstalker.com", "sotwe.com"),
               "host_labels": ("nitter",), "routes": ("nitter",),
               "sources": ("nitter", "xcancel"), "source_prefixes": ("nitter_",),
               "status": METHOD_BLOCKED, "reason": "login", "permitted_route": "x_api",
               "why": ("a third-party front-end that exists to get around X's login wall; the "
                       "permitted route is X's official API")},
    "reddit_api": {"hosts": ("oauth.reddit.com",), "status": API_PERMITTED,
                   "key_env": ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"),
                   "sources": ("reddit_api",),
                   "why": ("Reddit's official Data API (OAuth, application-only) within its "
                           "free-access limit of 100 queries per minute per client id"),
                   "terms": {"url": _REDDIT_DATA_API_WIKI, "checked_at": "2026-10-13",
                             "clauses": _REDDIT_DATA_API_CLAUSES}},
    "reddit": {"hosts": ("reddit.com", "redd.it", "redditmedia.com", "redditstatic.com",
                         "reddituploads.com", "redditblog.com", "pushshift.io", "pullpush.io",
                         "photon-reddit.com", "reveddit.com", "unddit.com", "libredd.it",
                         "safereddit.com", "troddit.com", "removeddit.com", "ceddit.com",
                         "resavr.com", "redditsearch.io", "reddit.app.link"),
               "host_labels": ("redlib", "libreddit", "teddit", "reveddit", "unddit"),
               "sources": ("reddit", "miner:reddit", "pushshift", "pullpush", "photon_reddit",
                           "redlib", "libreddit", "teddit", "reveddit", "unddit"),
               "source_prefixes": ("ext_reddit_", "reddit_", "pushshift_", "pullpush_"),
               "routes": ("reddit", "redlib", "libreddit", "teddit"), "status": IDEAS_ONLY,
               "live_route": "reddit_api", "permitted_route": "reddit_api",
               "why": ("public subreddit pages, feeds and archives read politely for ideas; "
                       "Reddit's Data API terms block traffic not using OAuth, so LIVE INPUT "
                       "from Reddit goes through reddit_api only (NEEDS_KEY until its keys exist)"),
               "terms": {"url": _REDDIT_DATA_API_WIKI, "checked_at": "2026-10-13",
                         "clauses": _REDDIT_DATA_API_CLAUSES,
                         "unread": {"https://redditinc.com/policies/user-agreement":
                                    "SITE_BLOCKED to the reader on 2026-10-13: UNREAD"}}},
    "stocktwits_api": {"hosts": ("api.stocktwits.com",), "status": API_PERMITTED,
                       "key_env": ("STOCKTWITS_ACCESS_TOKEN",),
                       "why": "StockTwits' approved API (its Terms s.5 name it the automated "
                              "route)"},
    "stocktwits": {"hosts": ("stocktwits.com",), "status": IDEAS_ONLY,
                   "sources": ("stocktwits", "miner:stocktwits"),
                   "source_prefixes": ("stocktwits_",), "routes": ("stocktwits",),
                   "why": ("its Terms s.5 bar automated extraction of its pages, so public "
                           "posts are read for ideas only; data goes through its API")},
    "telegram": {"hosts": ("t.me", "telegram.me"), "routes": ("telegram",),
                 "sources": ("telegram",), "status": IDEAS_ONLY,
                 "why": ("auditor ruling 2026-10-13: the content-licensing terms bar scraping, "
                         "aggregation or AI/ML use of platform data (llm_ai clause below), so "
                         "public t.me/s previews are read for ideas only, never live input. "
                         "One-line revert: status -> PUBLIC_PAGE if the licence changes"),
                 "terms": {"url": "https://telegram.org/tos/content-licensing",
                           "checked_at": "2026-10-13",
                           "clauses": {
                               "intro": ("Telegram provides a platform where users can upload, "
                                         "share and view content in public and private chats."),
                               "llm_ai": ("For clarity, Telegram firmly prohibits the scraping, "
                                          "indexing, harvesting, aggregation or use of data "
                                          "obtained from its platform to train, fine-tune, "
                                          "validate or otherwise engage in the development, "
                                          "enhancement, benchmarking or deployment of artificial "
                                          "intelligence, machine learning models and similar "
                                          "technologies."),
                               "use": ("Access to user-generated content for any purpose other "
                                       "than ordinary, legitimate, and intended use of the "
                                       "Telegram platform as its user is prohibited.")},
                           "reading": ("IDEAS_ONLY on the auditor's 2026-10-13 ruling: the "
                                       "'llm_ai' and 'use' clauses bar scraping and aggregation, "
                                       "so a t.me/s preview is read for ideas, never live input. "
                                       "Both clauses are kept verbatim so the principal can "
                                       "overrule.")}},
    "discord_bot": {"hosts": ("discord.com", "discordapp.com", "discord.gg"),
                    "status": API_PERMITTED, "key_env": ("DISCORD_BOT_TOKEN",),
                    "url_level": False,
                    "why": ("Discord's API with a bot token is the permitted route; a user "
                            "token driving it is a self-bot (METHOD_BLOCKED, check_request)")},
    "mql5": {"hosts": ("mql5.com",), "status": IDEAS_ONLY,
             "sources": ("mql5", "miner:mql5"),
             "why": ("public articles, codebase and forum pages read politely for mechanism "
                     "ideas; ToU 3.7 names automated access, so an mql5 page is never live "
                     "input and no content is reproduced -- the cell trades on MT5 data"),
             "terms": {"url": "https://www.mql5.com/en/about/terms", "checked_at": "2026-10-13",
                       "clauses": {
                           "3.7": ("You agree not to use the website www.mql5.com by any means "
                                   "other than through the interface that is provided by "
                                   "MetaQuotes Ltd on www.mql5.com or the MetaQuotes Software "
                                   "interface, unless You have been specifically allowed to do "
                                   "so in a separate agreement with MetaQuotes Ltd. You "
                                   "specifically agree not to access the website www.mql5.com "
                                   "through any automated means, including use of scripts, "
                                   "crawlers, or similar technologies.")}}},
    "yahoo": {"hosts": ("yahoo.com", "yahoo.co.jp"), "status": IDEAS_ONLY,
              "sources": ("yahoo", "yahoo_finance"),
              "why": ("public finance pages read for ideas; its Terms 2.d bar automated "
                      "collection without express permission, so prices come from MT5"),
              "terms": {"url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
                        "checked_at": "2026-10-13",
                        "clauses": {
                            "2.d.9": ("access or collect data, or attempt to access or collect "
                                      "data, from our Services using any automated means, "
                                      "devices, programs, algorithms or methodologies, including "
                                      "but not limited to robots, spiders, scrapers, data mining "
                                      "tools, or data gathering or extraction tools, for any "
                                      "purpose without our express, prior permission.")}}},
    # SERIES-LEVEL ROWS (url_level False: they govern LIVE INPUT of named series, never a host,
    # so FRED's own public-domain series and cboe.com pages keep their PUBLIC_PAGE default).
    # `recorders/vol_archive.py` reads its register from these rows and the yahoo row above.
    "fred_cboe": {"hosts": (), "url_level": False, "status": IDEAS_ONLY,
                  "sources": ("fred_cboe",),
                  "why": ("FRED's republished CBOE vol indices (VIXCLS family) are third-party "
                          "copyrighted series; FRED's legal terms clause requires the owner's "
                          "permission beyond personal use, so they are never live input"),
                  "terms": {"url": "https://fred.stlouisfed.org/legal/", "checked_at": "2026-10-06",
                            "clauses": {
                                "third_party": ("BEFORE USING DATA SERIES OWNED BY THIRD PARTIES "
                                                "FOR ANYTHING OTHER THAN YOUR OWN PERSONAL USE, "
                                                "YOU MUST CONTACT THE DATA OWNER TO OBTAIN "
                                                "PERMISSION."),
                                "label": ("Copyright, 2016, Chicago Board Options Exchange, "
                                          "Inc. Reprinted with permission. (the label on "
                                          "VIXCLS and GVZCLS)")}}},
    "cboe_vol_indices": {"hosts": (), "url_level": False, "status": IDEAS_ONLY,
                         "sources": ("cboe_vol_indices",),
                         "why": ("CBOE's use-of-content terms require a signed licence for its "
                                 "data, so its index values are a source of ideas, not live input"),
                         "terms": {"url": "https://www.cboe.com/use-of-content",
                                   "checked_at": "2026-10-06",
                                   "clauses": {
                                       "approval": ("In order to use any Cboe logo, data, "
                                                    "photo/image or other content contained in "
                                                    "Cboe websites (collectively \"Cboe "
                                                    "Content\"), you must receive approval in "
                                                    "advance from Cboe."),
                                       "licence": ("You are not approved to use Cboe Content "
                                                   "until a license agreement has been signed "
                                                   "by both you and Cboe.")}}},
    "paywall_proxy": {"hosts": ("12ft.io",), "status": METHOD_BLOCKED, "reason": "paywall",
                      "why": "a proxy whose purpose is to get around paywalls"},
}


def _feed_row(feed_url: str, status_: str, why: str, terms_url: str, read: str,
              clause: str = "") -> dict[str, Any]:
    """One macro event-ledger RSS feed's row (desks/mt5/macro/sources.py `_OFFICIAL_FEEDS`),
    keyed `macro_feed:<ID>`. Reached by `feed_policy(source_id, url)` only: no hosts, sources or
    routes, so the publisher's OTHER routes (an IMF data API, a BOE statistics page) are judged by
    their own rows, never by this feed's terms."""
    terms: dict[str, Any] = {"url": terms_url, "checked_at": "2026-10-07"}
    if clause:
        terms["clauses"] = {"reuse": clause}
    else:
        terms["unread"] = {terms_url or feed_url: read}
    return {"hosts": (), "url_level": False, "feed_url": feed_url, "status": status_,
            "why": why, "terms": terms}


#: THE MACRO FEEDS (folded in from #262's `data/macro_feed_terms.json` gate, 2026-10-13 audit
#: PR162_357 MF1). A feed whose own terms restrict reuse to non-commercial use is IDEAS_ONLY:
#: still fetched, its headlines read as events and ideas, never redistributed or used as a data
#: series. A feed whose terms page was unread, or carries no reuse clause, is a PUBLIC_PAGE. No
#: macro feed is held, so nothing LIVE fetched stops. Feeds absent here are PUBLIC_PAGE too
#: (their permitting clauses stay quoted in data/macro_feed_terms.json as evidence).
_NONCOMMERCIAL = ("its terms restrict reuse to non-commercial use (clause quoted), so headlines "
                  "are read as events and ideas, never redistributed or used as a data series")
_UNREAD = "terms page UNREAD or without a reuse clause: a public page, fetched politely"
SOURCE_POLICY.update({
    "macro_feed:BOJ": _feed_row(
        "https://www.boj.or.jp/en/announcements/rss.rdf", IDEAS_ONLY, _NONCOMMERCIAL,
        "https://www.boj.or.jp/en/about/copyright.htm", "",
        "The copying or reproduction of the content for commercial purposes."),
    "macro_feed:BOE": _feed_row(
        "https://www.bankofengland.co.uk/rss/news", IDEAS_ONLY, _NONCOMMERCIAL,
        "https://www.bankofengland.co.uk/legal", "",
        "You may download, display or print the Resources for personal use or internal use "
        "within an individual organisation for non-commercial purposes."),
    "macro_feed:SNB": _feed_row(
        "https://www.snb.ch/en/node/10532/rss", IDEAS_ONLY, _NONCOMMERCIAL,
        "https://www.snb.ch/en/srv/disclaimer_copyright", "",
        "... used in other ways, for non-commercial purposes, compatible with the purpose of such "
        "information or data."),
    "macro_feed:IMF": _feed_row(
        "https://www.imf.org/en/News/RSS?Language=ENG", IDEAS_ONLY, _NONCOMMERCIAL,
        "https://www.imf.org/external/terms.htm", "",
        "for personal, noncommercial usage only"),
    "macro_feed:UN_NEWS": _feed_row(
        "https://news.un.org/feed/subscribe/en/news/region/all/feed/rss.xml", IDEAS_ONLY,
        _NONCOMMERCIAL, "https://www.un.org/en/about-us/copyright", "",
        "News-related material can be used as long as the appropriate credit is given and the "
        "United Nations is advised."),
    "macro_feed:SP_INDICES": _feed_row(
        "https://www.spglobal.com/spdji/en/rss/index-announcements/", IDEAS_ONLY,
        "its terms restrict copying and distribution of the Content (clause quoted), so "
        "announcements are read as events and ideas, never redistributed",
        "https://www.spglobal.com/en/terms-of-use", "",
        "You shall not distribute, transfer, sub-license, ... copy, ... or change all or any "
        "portion of the Content."),
    "macro_feed:OPEC": _feed_row(
        "https://www.opec.org/opec_web/en/press_room/28.htm", PUBLIC_PAGE, _UNREAD, "",
        "terms page not read: opec.org terms URL returned HTTP 402 (2026-10-07)"),
    "macro_feed:USTR": _feed_row(
        "https://ustr.gov/rss.xml", PUBLIC_PAGE, _UNREAD, "https://ustr.gov/privacy-legal",
        "no reuse / automated-access clause found on the page as read (2026-10-07)"),
    "macro_feed:TREASURY_OFAC": _feed_row(
        "https://ofac.treasury.gov/system/files/126/ofac.xml", PUBLIC_PAGE, _UNREAD,
        "https://home.treasury.gov/subfooter/site-policies-and-notices",
        "no reuse / copyright statement found (2026-10-07)"),
    "macro_feed:US_TREASURY": _feed_row(
        "https://home.treasury.gov/rss/press.xml", PUBLIC_PAGE, _UNREAD,
        "https://home.treasury.gov/subfooter/site-policies-and-notices",
        "no reuse / copyright statement found (2026-10-07)"),
    "macro_feed:IMO_SHIPPING": _feed_row(
        "https://www.imo.org/en/MediaCentre/PressBriefings/_vti_bin/RSS.svc/news", PUBLIC_PAGE,
        _UNREAD, "", "terms page not read: imo.org refused the fetch (robots.txt redirect loop)"),
})


def validate_permits_live_input(policy: Mapping[str, Mapping[str, Any]] | None = None) -> None:
    """Raise ValueError for any row carrying `permits_live_input` that its evidence cannot carry:
    a non-bool value, or True without status API_PERMITTED / PUBLIC_PAGE, its own terms page and
    a verbatim permitting clause. Run at import, so a bad row never reaches a reader."""
    bad: list[str] = []
    for key, row in (SOURCE_POLICY if policy is None else policy).items():
        if "permits_live_input" not in row:
            continue
        v = row["permits_live_input"]
        if not isinstance(v, bool):
            bad.append(f"{key}: permits_live_input must be a bool, got {type(v).__name__}")
            continue
        if not v:
            continue
        terms = row.get("terms") or {}
        if str(row.get("status")) not in (API_PERMITTED, PUBLIC_PAGE):
            bad.append(f"{key}: permits_live_input with status {row.get('status')}")
        if not terms.get("url") or not terms.get("clauses"):
            bad.append(f"{key}: permits_live_input without its own terms url and a quoted clause")
    if bad:
        raise ValueError("terms_fence.SOURCE_POLICY: " + "; ".join(bad))


def permits_live_input(key: str) -> bool:
    """The row's validated `permits_live_input` claim (False when absent)."""
    return SOURCE_POLICY.get(key, {}).get("permits_live_input") is True


validate_permits_live_input()

#: A redirect INTO one of these paths is a login / CAPTCHA wall; it is refused, never followed.
LOGIN_WALL = re.compile(r"(?i)/(?:i/flow/)?(?:log[-_]?in|sign[-_]?in|signin|accounts?/login|"
                        r"session/new|oauth2?/authorize|authorize|sso|captcha|"
                        r"cdn-cgi/challenge-platform)"
                        r"(?:[/?#.]|$)")
#: The method rows a refusal can name that are not sources.
METHOD_ROWS: dict[str, dict[str, Any]] = {
    "login_wall": {"status": METHOD_BLOCKED, "reason": "login",
                   "why": "a redirect into a login or CAPTCHA wall is never followed"},
    "discord_user": {"status": METHOD_BLOCKED, "reason": "login",
                     "why": "a user token driving Discord's API is a self-bot; bot token only"},
}


def _row(key: str) -> dict[str, Any]:
    return SOURCE_POLICY.get(key) or METHOD_ROWS[key]


def status(key: str) -> str:
    """The EFFECTIVE status of a policy row: API_PERMITTED becomes NEEDS_KEY when any of its
    keys is absent. Only presence is checked; no key is read or printed."""
    row = _row(key)
    st = str(row["status"])
    if st == API_PERMITTED and not all(os.environ.get(k) for k in row.get("key_env") or ()):
        return NEEDS_KEY
    return st


def terms_state(key: str) -> str:
    """READ when the row carries its own terms page and at least one verbatim clause, else
    UNREAD. Presence of a quote is evidence; its absence is never read as permission."""
    t = (_row(key).get("terms") or {})
    return "READ" if t.get("url") and t.get("clauses") else UNREAD


def live_input_status(key: str) -> str:
    """The status that governs LIVE INPUT from a row: its `live_route` row's effective status
    when it names one (Reddit pages -> reddit_api: NEEDS_KEY until its keys exist), else its
    own effective status."""
    route = _row(key).get("live_route")
    return status(str(route)) if route else status(key)


def _view(key: str) -> dict[str, Any]:
    row = _row(key)
    perm = row.get("permitted_route")
    return {**row, "status": status(key), "reason": row["why"], "label": f"{key}_policy",
            "substitutes": (perm,) if perm else ()}


class _Platforms(Mapping[str, dict[str, Any]]):
    """`PLATFORMS[key]` as the callers of the old fence read it: status (effective), reason
    (the row's why), label, substitutes (the permitted route)."""

    def __getitem__(self, key: str) -> dict[str, Any]:
        return _view(key)

    def __iter__(self) -> Any:
        return iter([*SOURCE_POLICY, *METHOD_ROWS])

    def __len__(self) -> int:
        return len(SOURCE_POLICY) + len(METHOD_ROWS)


PLATFORMS: Mapping[str, dict[str, Any]] = _Platforms()


class TermsFenced(urllib.error.URLError, RuntimeError):
    """A fetch was asked for a HELD source, or a redirect led into a login wall.

    ONE refusal type for THE ONE FETCH DOOR (`guarded_urlopen`, re-exported as
    `polite_fetch.fenced_urlopen` / `polite_fetch.MethodRefused`). It is a `URLError`, so a caller
    that only knows urllib's errors still records a failed fetch rather than crashing, and it is
    deterministic, so no caller retries it. `reason` is the full refusal
    (`STATUS:source: url -- why`), `why` the row's one line, `status` / `platform` the parts."""

    def __init__(self, platform: str, url: str) -> None:
        self.platform = platform
        v = _view(platform)
        self.why = str(v["reason"])
        self.status = str(v["status"])
        self.url = str(url)
        msg = f"{self.status}:{platform}: {self.url[:160]} -- {self.why}"
        super().__init__(msg)
        self.args = (msg,)

    def __str__(self) -> str:
        return str(self.reason)


_ARCHIVE_HOSTS = ("web.archive.org", "archive.org")
_ARCHIVE_TODAY = ("archive.ph", "archive.today", "archive.is", "archive.li", "archive.vn",
                  "archive.md", "archive.fo")
_READER_HOSTS = ("r.jina.ai", "12ft.io")
_GOOGLE_CACHE = ("webcache.googleusercontent.com",)
_GOOGLE_TRANSLATE = ("translate.google.com", "translate.googleusercontent.com")
#: Google Translate's proxy encodes the target host into ONE label of `*.translate.goog`:
#: every "." becomes "-" and every original "-" is doubled (www-reddit-com.translate.goog).
_TRANSLATE_GOOG = "translate.goog"
#: News hosts behind a subscription paywall: an archive.today copy of one of their pages is the
#: paywall route (`paywall_proxy`, METHOD_BLOCKED). The host itself stays a PUBLIC_PAGE.
PAYWALLED_HOSTS = ("ft.com", "wsj.com", "bloomberg.com", "economist.com", "nytimes.com",
                   "barrons.com", "nikkei.com", "washingtonpost.com", "thetimes.co.uk",
                   "telegraph.co.uk", "theinformation.com", "caixin.com", "handelsblatt.com",
                   "lesechos.fr", "risk.net")
#: Full stops that IDNA treats as label separators (ideographic, fullwidth, halfwidth).
_DOTS = ("\u3002", "\uff0e", "\uff61")



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



def _host_source(h: str) -> str | None:
    """The policy row a host belongs to (URL-level rows only), or None (PUBLIC_PAGE)."""
    h = normalize_host(h)
    labels = h.split(".") if h else []
    for name, p in SOURCE_POLICY.items():
        if p.get("url_level") is False:
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
            # `cache:<id>:<url>`: strip the id when what follows is a URL (`https://...`) or a
            # bare host (`reddit.com/...`); a bare `host:port` is left alone.
            m = re.match(r"^[A-Za-z0-9_-]{6,}:(?!//)(.+)$", q)
            if m and (re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:/", m.group(1))
                      or "." in m.group(1).split("/")[0]):
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



def source_of_url(url: str, _depth: int = 0) -> str | None:
    """The policy row a URL belongs to, or None (unlisted: PUBLIC_PAGE). A wrapper (archive,
    cache, reader, translate proxy) resolves to what it wraps when that is held."""
    h = _host(url)
    if not h:
        return None
    k = _host_source(h)
    if k and status(k) in HOLDING:
        return k
    inner = _wrapped_url(url) if _depth < 4 else None
    if inner and _on(h, _ARCHIVE_TODAY) and _on(_host(inner), PAYWALLED_HOSTS):
        # archive.today is the common route around a paywall: an archive.today copy of a
        # paywalled page is the paywall proxy (METHOD_BLOCKED), exactly as 12ft.io is.
        return "paywall_proxy"
    if inner:
        k2 = source_of_url(inner, _depth + 1)
        # A wrapper reads as what it wraps: always when the target is held, and whenever the
        # wrapper itself is unlisted (an archive copy of a Reddit page is a Reddit page).
        if k2 and (status(k2) in HOLDING or k is None):
            return k2
    return k


def policy_of_url(url: str) -> dict[str, Any]:
    """{source, status, why, ...} for a URL; PUBLIC_PAGE for an unlisted host."""
    k = source_of_url(url)
    if not k:
        return {"source": _host(url), "status": PUBLIC_PAGE, "why": "unlisted host: public page"}
    return {"source": k, **{x: y for x, y in _view(k).items()
                             if x in ("status", "why", "reason", "permitted_route")}}


def platform_of_url(url: str, _depth: int = 0) -> str | None:
    """The HELD source a URL belongs to (METHOD_BLOCKED, or NEEDS_KEY until its key exists), or
    None. A source that is merely listed (IDEAS_ONLY, PUBLIC_PAGE, a keyed API) is not held."""
    k = source_of_url(url, _depth)
    return k if k and status(k) in HOLDING else None


def fenced_url(url: str) -> str | None:
    """The hold reason when `url` is on a held source, else None."""
    p = platform_of_url(url)
    return str(_view(p)["reason"]) if p else None


def check_url(url: str) -> None:
    """Raise `TermsFenced` for a URL on a held source. Every fetch helper calls this first."""
    p = platform_of_url(url)
    if p:
        raise TermsFenced(p, str(url))


def login_wall(url: str) -> bool:
    """A URL that is a login / CAPTCHA wall (a redirect target the desk never follows)."""
    parts = _parse(url)
    return bool(parts is not None and LOGIN_WALL.search(parts.path or ""))


def _header(headers: Any, name: str) -> str:
    if headers is None:
        return ""
    for k, v in (headers.items() if hasattr(headers, "items") else []):
        if str(k).lower() == name.lower():
            return str(v or "")
    return ""



def fenced_request(url: str, headers: Any = None) -> str | None:
    """The held source a REQUEST belongs to: `platform_of_url`, plus the Discord rule -- a
    discord API request authorized by anything but `Bot <token>` (a user token) is a self-bot
    and is METHOD_BLOCKED. No credential at all is not a user token."""
    p = platform_of_url(url)
    if p:
        return p
    h = _host(url)
    if h and any(h == d or h.endswith("." + d) for d in SOURCE_POLICY["discord_bot"]["hosts"]):
        auth = _header(headers, "Authorization").strip()
        path = urlparse(url if "://" in url else "https://" + url).path.lower()
        if path.startswith("/api") and auth and not auth.startswith("Bot "):
            return "discord_user"
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

    def __init__(self) -> None:
        super().__init__()
        #: Every hop this opener was asked to follow, [(code, from, to)] -- redirects are VISIBLE.
        self.chain: list[tuple[int, str, str]] = []

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        self.chain.append((int(code), str(req.full_url), str(newurl)))
        held = platform_of_url(newurl)
        # METHOD: a redirect into a held source or a login / CAPTCHA wall is refused, never
        # followed; the 3xx response's socket is released before the refusal is raised.
        if held or login_wall(newurl):
            with contextlib.suppress(Exception):
                fp.read()
                fp.close()
            raise TermsFenced(held or "login_wall", newurl)
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


def guarded_urlopen(req: Any, *, timeout: float | None = 30.0, context: Any = None) -> Any:
    """THE ONE FETCH DOOR (`polite_fetch.fenced_urlopen` is this function): `urlopen` with the
    fence. The URL is checked BEFORE any request is built (a held source, or a first URL that is
    itself a login wall, raises `TermsFenced`); a redirect into a held source or a login wall
    raises instead of being followed; every hop followed is kept on the response as
    `.redirects` [(code, from, to)]. `timeout=None` means the socket default."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    hdrs = _req_headers(req) if isinstance(req, urllib.request.Request) else None
    check_request(url, hdrs)
    if login_wall(url):
        raise TermsFenced("login_wall", url)
    opener = guarded_opener(context)
    fh = opener.open(req) if timeout is None else opener.open(req, timeout=timeout)
    chain = next((h.chain for h in getattr(opener, "handlers", ())
                  if isinstance(h, FencedRedirectHandler)), [])
    with contextlib.suppress(AttributeError):
        fh.redirects = list(chain)
    return fh


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
    """The HELD source a discovery SOURCE name belongs to (used before FETCHING a source by
    id), or None. A listed but unheld source (Reddit, StockTwits, X pages) is not held."""
    k = source_key(source)
    return k if k and status(k) in HOLDING else None


def source_key(source: str) -> str | None:
    """The policy row a source NAME belongs to ("miner:reddit", "ext_reddit_EURUSD_x"), or None."""
    forms = _source_forms(source)
    for name, p in SOURCE_POLICY.items():
        for f in forms:
            if f in (p.get("sources") or ()) or any(
                    f.startswith(x) for x in (p.get("source_prefixes") or ())):
                return name
    return None


_URL_FIELDS = ("url", "link", "source_url", "permalink", "canonical_url")
#: Fields a row uses to DECLARE its live input data (a series or feed it reads at decision time).
_INPUT_FIELDS = ("input_data", "input_sources", "data_source", "data_sources", "series_source",
                 "live_inputs")


def _input_refs(row: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for f in _INPUT_FIELDS:
        v = row.get(f)
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, (list, tuple)):
            out.extend(str(x) for x in v if x)
    return out


def input_source(*refs: Any) -> str | None:
    """THE LIVE-INPUT CHECK: the policy row that forbids using any of `refs` (source names or
    URLs) as LIVE INPUT DATA -- an IDEAS_ONLY source (read for ideas, never data) or a held one --
    else None. Data organs (acquirer, collectors, free stack, pack cells) call this; discovery and
    idea organs call `platform_of_url` (held only)."""
    for ref in refs:
        r = str(ref or "").strip()
        if not r:
            continue
        is_url = "/" in r or "." in r.split(":")[0]
        k = source_of_url(r) if is_url else None
        if k:
            # A URL is the route it names: an IDEAS_ONLY page is never live input, even when
            # the same source has a permitted API route (www.reddit.com is not oauth.reddit.com).
            if status(k) in (IDEAS_ONLY, *HOLDING):
                return k
            continue
        k = source_key(r)
        if not k:
            continue
        # A source NAME is live input through its `live_route` when it has one (the free
        # stack's reddit row fetches oauth.reddit.com): permitted once that route is.
        route = _row(k).get("live_route")
        if route:
            if status(str(route)) in (IDEAS_ONLY, *HOLDING):
                return str(route)
            continue
        if status(k) in (IDEAS_ONLY, *HOLDING):
            return k
    return None


def fenced_row(row: Mapping[str, Any], source: str = "") -> str | None:
    """RULE 4: the source a row's declared LIVE INPUT DATA comes from, when that source is
    IDEAS_ONLY or held -- else None. A row's IDEA provenance (its source name, route, url or
    contributing sources) never makes it fenced: such a row is labelled and judged."""
    if not isinstance(row, Mapping):
        return None
    return input_source(*_input_refs(row))


def fenced_ground(g: Mapping[str, Any]) -> str | None:
    """The HELD source a registered deep-forest GROUND belongs to (its route, url, site, feeds or
    mirrors), or None. Only a held ground is left unscheduled; IDEAS_ONLY grounds are mined."""
    if not isinstance(g, Mapping):
        return None
    route = str(g.get("route") or "").lower()
    for name, spec in SOURCE_POLICY.items():
        if route in (spec.get("routes") or ()) and status(name) in HOLDING:
            return name
    for k in ("url", "site", "feed"):
        p = platform_of_url(str(g.get(k) or ""))
        if p:
            return p
    for k in ("feeds", "mirrors", "urls", "seeds"):
        for f in g.get(k) or []:
            p = platform_of_url(str(f or ""))
            if p:
                return p
    return None


def touched_row(row: Mapping[str, Any]) -> str | None:
    """The listed source a row's IDEA came from (source, route, url, contributing source) -- for
    the LABEL only. Never a reason to refuse or quarantine (rule 4)."""
    if not isinstance(row, Mapping):
        return None
    for s in (row.get("source"), row.get("origin"), row.get("miner")):
        k = source_key(str(s or ""))
        if k:
            return k
    route = str(row.get("route") or "").split(":", 1)[0].lower()
    for name, spec in SOURCE_POLICY.items():
        if route and route in (spec.get("routes") or ()):
            return name
    for f in _URL_FIELDS:
        v = row.get(f)
        if isinstance(v, str):
            k = source_of_url(v)
            if k:
                return k
    cs = row.get("contributing_sources")
    for s in cs if isinstance(cs, list) else []:
        k = source_key(str(s or ""))
        if k:
            return k
    return None


def label_row(row: dict[str, Any]) -> str | None:
    """Stamp `provenance_label` and `terms_fence` (the source's policy) on a row a listed source
    touched. A LABEL: nothing about the row's verdict, identity, ordering or eligibility changes,
    and no reader may refuse a row for it (rule 4). Idempotent; `provenance` is not touched."""
    k = touched_row(row)
    if not k:
        return None
    lab = f"{k}_policy"
    row["provenance_label"] = lab
    row["terms_fence"] = {"platform": k, "status": status(k), "reason": _row(k)["why"],
                          "blocks": False}
    return lab


def quarantined_row(row: Mapping[str, Any]) -> str | None:
    """RULE 4: a docket / backtest row is withheld from a judge ONLY when its declared live input
    data comes from an IDEAS_ONLY or held source (`fenced_row`). Idea provenance and an older
    `provenance_label` never quarantine a row."""
    return fenced_row(row)


def registry_rows() -> list[dict[str, Any]]:
    """One row per policy entry: source, effective status, why, hosts, permitted route."""
    return [{"platform": name, "source": name, "status": status(name), "why": p["why"],
             "reason": p["why"], "label": f"{name}_policy", "hosts": list(p["hosts"]),
             "permitted_route": p.get("permitted_route"), "live_route": p.get("live_route"),
             "terms_state": terms_state(name),
             "terms_url": (p.get("terms") or {}).get("url"),
             "substitutes": [p["permitted_route"]] if p.get("permitted_route") else []}
            for name, p in SOURCE_POLICY.items()]


def feed_policy(source_id: str, url: str) -> dict[str, Any]:
    """The policy for one macro RSS feed: its `macro_feed:<ID>` row when it has one (and the row
    was read for this exact URL), else the URL's own policy (PUBLIC_PAGE when unlisted). Only a
    HOLDING status (METHOD_BLOCKED / NEEDS_KEY) stops a fetch."""
    key = f"macro_feed:{source_id}"
    row = SOURCE_POLICY.get(key)
    if row is not None and row.get("feed_url") == url:
        return {"source": key, **_view(key)}
    return policy_of_url(url)


def refusal(platform: str, **extra: Any) -> dict[str, Any]:
    """The artifact a HELD route writes instead of data: status, source, reason, permitted
    route. Only METHOD_BLOCKED and NEEDS_KEY sources ever produce one."""
    v = _view(platform)
    return {"status": v["status"], "platform": platform, "source": platform,
            "reason": v["reason"], "why": f"source policy ({platform}): {v['reason']}",
            "substitutes": list(v["substitutes"]), "fetched": 0, **extra}


if __name__ == "__main__":
    print(json.dumps(registry_rows(), indent=1))
