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
#: JPX's site terms (Japanese and English pages), read 2026-10-14 for the pass-6 F4 holds. One
#: reading shared by every JPX route held on it (a value, not a second register).
_JPX_TERMS: dict[str, Any] = {
    "url": "https://www.jpx.co.jp/term-of-use/index.html", "checked_at": "2026-10-14",
    "clauses": {
        "secondary_use": ("当サイトに掲載されている情報について、有料・無料を問わずJPXからの許諾を"
                          "得ている場合を除き、商用目的によるデータ収集のほか如何なる用途に関わらず"
                          "二次利用及び再配信はできません。"),
        "automated": ("当サイトへの高頻度・高負荷に繋がる可能性のある自動取得等はご遠慮いただいて"
                      "おります。"),
        "en:collection": ("The collection of data or secondary use of information from this "
                          "website for commercial purposes is strictly prohibited [...] unless "
                          "JPX has granted prior permission or authorized such use under a paid "
                          "contract"),
        "en:automated": "Please refrain from automatic information retrieval and other operations"},
    "also_read": ("https://www.jpx.co.jp/english/term-of-use/index.html",
                  "https://www.jpx.co.jp/markets/statistics-equities/short-selling/index.html",
                  "https://www.jpx.co.jp/markets/statistics-equities/margin/index.html")}
def _cnx_row(sid: str, exch: str, *, url: str, host: str, why: str = "", unblock: str = "",
             clauses: dict[str, str] | None = None,
             unread: dict[str, str] | None = None) -> dict[str, Any]:
    """One China-exchange held route (the free-stack `cn_exchange` roster rows). Evidence read
    2026-10-06; a row with no clause is UNREAD (to_confirm), never permitted.

    `host` is the exchange's OWN domain, held WHOLE-HOST through `url_patterns` (pass-6 audit
    e5a1526f3 MUST-FIX 1): the asia_collector registry fetches the same exchange's pages
    (shfe_daily, cffex_member_rank, ...) under other ids, and the hold must bind the URL, not
    only the roster id. Whole-host because the evidence is whole-host: SHFE's statement governs
    "本网站的任何内容" (any content of this website), and an UNREAD exchange has no clause for
    any of its pages. Still IDEAS_ONLY (never METHOD_BLOCKED), so pages stay readable for ideas
    and only LIVE INPUT is refused (`input_source`)."""
    terms: dict[str, Any] = {"url": url, "checked_at": "2026-10-06"}
    if clauses:
        terms["clauses"] = dict(clauses)
    if unread:
        terms["unread"] = dict(unread)
    return {"hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
            "sources": (sid,),
            "url_patterns": (r"^(?:[^/]*\.)?" + re.escape(host) + "/",),
            "wanted": (f"{exch} daily member rankings, warehouse receipts and quotes (free-stack "
                       f"roster row {sid}): positioning, inventory and curve state for the "
                       "copper, gold, silver, oil, iron-ore and index complexes"),
            "why": why or (f"no terms read for {exch}, so to_confirm (fail closed; audit of PR "
                           "#224): UNREAD terms never permit automated input"),
            "robots": "not consulted: the terms already decide",
            "unblock": unblock or (f"{exch}'s own terms page read with a clause permitting the "
                                   "desk's use, quoted into this row, and the row flipped"),
            "terms": terms}


def terms_verdict(key: str) -> str:
    """The terms word an organ gates a fetch on, read from THIS register (never a roster field):
    `refused` -- a held route whose own clauses were read and do not grant the use; `to_confirm`
    -- a held route with no clause read, or no row at all (fail closed); `confirmed` -- a row that
    is not held, has a permitting status and quotes at least one clause. Flipping the row is the
    only unblock."""
    row = SOURCE_POLICY.get(key)
    if not row:
        return "to_confirm"
    clauses = (row.get("terms") or {}).get("clauses")
    if row.get("held_route"):
        return "refused" if clauses else "to_confirm"
    if row.get("status") in (PUBLIC_PAGE, API_PERMITTED) and clauses:
        return "confirmed"
    return "to_confirm"


#: HELD ROUTES (2026-10-14, the GD queue rows; auditor: one register, so they live HERE). Routes
#: the queue asked for whose OWN terms were read and carry no clause permitting automated access
#: for internal research. Not URL-level (`hosts` is empty): the row governs the named ROUTE, so
#: other pages on these domains keep whatever row or default they had. IDEAS_ONLY = never live
#: input; `alt_proxies.HELD_ROUTES` is a read-only view that reports each by name as HELD. Each
#: row's `sources` is its own key, so `input_source("<route>")` resolves to the row.
#: Missed growth: each route's delta E[log W] is UNMEASURED until its `unblock` arrives.
_HELD_ROUTES: dict[str, dict[str, Any]] = {
    "cme_margin_changes": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("cme_margin_changes",),
        # the clearing-advisory and performance-bond routes (pass 6 delta). No organ requests
        # them today (grep 2026-10-14); the patterns make any future request name this row.
        "url_patterns": (
            r"^(?:[^/]*\.)?cmegroup\.com/notices/clearing/",
            r"^(?:[^/]*\.)?cmegroup\.com/notices\.html$",
            r"^(?:[^/]*\.)?cmegroup\.com/clearing/(?:margins|risk-management)/",
            r"^(?:[^/]*\.)?cmegroup\.com/solutions/risk-management/performance-bond",
            r"^(?:[^/]*\.)?cmegroup\.com/CmeWS/mvc/Margins/"),
        "wanted": ("CME Clearing performance-bond (margin) change advisories, PIT at notice "
                   "publication: a margin-hike regime for XAUUSD, XAGUSD, XTIUSD and indices"),
        "why": ("the licence (s.12) is personal and bars copying and derivative works, s.8(vi) "
                "bars data use for machine learning, and no clause permits automated access"),
        "robots": ("cmegroup.com/robots.txt disallows Python-urllib/1.17 entirely and many "
                   "/clearing/ sub-paths for every agent"),
        "unblock": "a written CME authorisation, or a public-domain mirror of the advisories",
        "terms": {"url": "https://www.cmegroup.com/files/terms-of-use.pdf",
                  "checked_at": "2026-10-14",
                  "clauses": {
                      "12": ("Except as expressly authorized by CME, you agree not to sell, "
                             "copy, distribute, or create derivative works based on the "
                             "Website, in whole or in part."),
                      "8(vi)": ("Your use of any data, databases, directories content, "
                                "information or materials (including associated metadata) on "
                                "the Website, in any manner for any machine learning and/or "
                                "artificial intelligence [...] is expressly prohibited.")}}},
    "cn_credit_contagion": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("cn_credit_contagion",),
        "wanted": ("GAP_MAP row 31: China credit/default-notice graph (CFETS ChinaMoney, "
                   "ChinaBond, PBoC) mapped to AUD, copper, HK50, CHINAH, USDCNH, gold"),
        "why": ("no official source's own terms could be read, so none has a permitting "
                "clause: UNREAD terms never permit automated input"),
        "robots": "pbc.gov.cn: ROBOTS_DISALLOWED to the reader on 2026-10-14",
        "unblock": ("a CFETS, ChinaBond or PBoC terms page read on the publisher's own domain "
                    "with a reuse clause"),
        "terms": {"url": "https://www.chinamoney.com.cn/chinese/flsm/",
                  "checked_at": "2026-10-14",
                  "unread": {
                      "pbc.gov.cn": "ROBOTS_DISALLOWED to the reader on 2026-10-14: UNREAD",
                      "chinamoney.com.cn": ("SITE_BLOCKED: the CFETS legal-statement page "
                                            "returned a fetch error on 2026-10-14: UNREAD"),
                      "chinabond.com.cn": ("no legal or copyright page found on the ChinaBond "
                                           "home page on 2026-10-14: UNREAD")}}},
    "cboe_delayed_index_values": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("cboe_delayed_index_values",),
        "wanted": ("Cboe delayed index values (VIX family) for #234's vol route (a note only; "
                   "#234 is not changed here)"),
        "why": ("s.2 grants one personal non-commercial copy and bars storing in a retrieval "
                "system or deriving from the Materials; no clause names delayed data or "
                "automated access: no permitting clause, so #234's vol route stays unadmitted"),
        "robots": "not consulted: the terms already decide",
        "unblock": "a Cboe 'Request to Use Cboe Content' consent, or a licensed data feed",
        "terms": {"url": "https://www.cboe.com/terms", "checked_at": "2026-10-14",
                  "clauses": {
                      "2": ("You may view, print and download one copy of the Materials for "
                            "your personal non-commercial use in connection with products and "
                            "services offered by Cboe, provided that you maintain all "
                            "copyright, trademark and other notices contained on the "
                            "Materials. You may not otherwise copy, reproduce, alter, store "
                            "either in hard copy or in an electronic retrieval system, create a "
                            "derivative work (for example, a financial product, service or "
                            "index) from, use to verify or correct other data or information, "
                            "publish, rent, sublicense, distribute, or otherwise use in whole "
                            "or in part in any other manner the Materials without Cboe's prior "
                            "written consent")}}},
    # ---- PASS 5 holds (2026-10-14; auditor: one register). Each USED to be a second register
    # (an alt_proxies Source/TERMS row, a `terms` field on the free-stack roster); the clauses
    # are the ones pass 5 quoted, moved here verbatim. Nothing is fetched for any of them.
    "us_finra_regsho_short_volume": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("us_finra_regsho_short_volume",),
        "wanted": ("FINRA Reg SHO daily short-sale volume (CNMS consolidated file): an extreme "
                   "market-wide short-volume ratio as a 1-5 day mean-reversion state for US500, "
                   "NAS100, US2000"),
        "why": ("FINRA's Terms of Use allow only non-commercial personal or professional use and "
                "bar data-mining tools, robots and building a database from the site; the Reg "
                "SHO daily-files page adds no licence: no permitting clause"),
        "robots": "not consulted: the terms already decide",
        "unblock": "a FINRA data licence or written permission for internal commercial research",
        "terms": {"url": "https://www.finra.org/terms-of-use", "checked_at": "2026-10-14",
                  "clauses": {
                      "use": ("shall be used ONLY for your own non-commercial personal or "
                              "professional use."),
                      "robots": ("use any data mining, scraping or harvesting tools (including "
                                 "robots)"),
                      "database": "develop or create a database of data using the FINRA Website"}}},
    "gb_adzuna_vacancies": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("gb_adzuna_vacancies",),
        "wanted": ("Adzuna job-advert counts (UK/EU/AU/CA) as a labour-demand nowcast for "
                   "GBPUSD, EURUSD, AUDUSD, USDCAD"),
        "why": ("the Adzuna API terms permit commercial use only inside a 14-day trial and bar "
                "aggregated vacancy counts for ongoing research without written consent; the key "
                "on the box does not change that"),
        "robots": "not consulted: the terms already decide",
        "unblock": "Adzuna's written consent to ongoing aggregate use of vacancy counts",
        "terms": {"url": "https://developer.adzuna.com/docs/terms_of_service",
                  "checked_at": "2026-10-14",
                  "clauses": {
                      "trial": ("Any other use of the Adzuna API by a commercial, government or "
                                "academic organisation ... is permitted subject to a 14 day "
                                "trial period."),
                      "aggregation": ("It may not be used in its original format or in "
                                      "aggregation (including but not limited to vacancy counts, "
                                      "average salaries etc) to deliver any ongoing work or "
                                      "research, apart from the purpose stated prior, without "
                                      "written consent.")}}},
    "congress_trades": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("congress_trades",),
        "wanted": ("US congressional periodic transaction reports (House Clerk index, Senate eFD) "
                   "and their community S3 mirror: filing-dated legislator net buying as informed-"
                   "flow evidence (free_stack_hunter row congress_trades)"),
        "why": ("the Ethics in Government Act restriction (now 5 U.S.C. 13107(c)) printed on the "
                "Senate eFD gate bars obtaining or using a report for any commercial purpose, "
                "binds House and Senate reports alike, and trading on them is a commercial "
                "purpose; the S3 mirror republishes the same reports with no licence of its own"),
        "robots": "not consulted: the terms already decide",
        "unblock": ("counsel or the principal clears the use; the PTR parser "
                    "(libs.data.free_stack.parse_ptr_trades) is built, so the lane is one terms "
                    "decision from running. Ideas from public news coverage stay mined"),
        "terms": {"url": "https://efdsearch.senate.gov/search/home/", "checked_at": "2026-10-14",
                  "clauses": {
                      "5 U.S.C. 13107(c)": (
                          "It shall be unlawful for any person to obtain or use a report: ... "
                          "for any commercial purpose, other than by news and communications "
                          "media for dissemination to the general public; ... for determining "
                          "or establishing the credit rating of any individual")},
                  "unread": {
                      "disclosures-clerk.house.gov": (
                          "the House Clerk page links a Terms of Service PDF that was not "
                          "readable from the authoring container on 2026-10-14: UNREAD")}}},
    # ---- PASS 6 holds (2026-10-14; one register). F2 (COMEX registered/eligible stocks, the
    # LME cancelled-warrant share) and F4 (JPX short-selling ratio, JPX margin balances): each
    # publisher's OWN terms were read and none carries a clause permitting automated access for
    # internal research, so all four are HELD and nothing is fetched. `url_patterns` make the
    # row URL-level for exactly its route (host + path), so `input_source(<url>)` answers for the
    # route even where a caller names no source; other pages on the host keep their own row or
    # default. The asia_collector registry rows that pointed at these routes (comex_warehouse,
    # lme_warehouse; jp_tocom_settlements has its own row) are held through the URL: the
    # collector's live-input check reads `input_source(url, id)`, and the URL names the row.
    # The FINRA margin-statistics route (an auditor should-fix) is held on FINRA's site-wide ToU.
    "comex_warehouse_stocks": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("comex_warehouse_stocks",),
        "url_patterns": (r"^(?:[^/]*\.)?cmegroup\.com/delivery_reports/",
                         # the same stocks through CME's depository web service and the
                         # warehouse-reports page (side_channels/probe_free*.py name both)
                         r"^(?:[^/]*\.)?cmegroup\.com/CmeWS/mvc/Metals/GetDepositary",
                         r"^(?:[^/]*\.)?cmegroup\.com/market-data/delayed-quotes/metals/"
                         r"warehouse-reports"),
        "wanted": ("COMEX registered vs eligible warehouse stocks (Gold_Stocks.xls, "
                   "Silver_stocks.xls, Copper_Stocks.xls): the registered share as the "
                   "deliverable float for XAUUSD, XAGUSD, XCUUSD"),
        "why": ("the delivery-report page carries no licence of its own, so CME's Terms of Use "
                "govern: s.12 bars copying and derivative works, s.8(vi) bars data use for "
                "machine learning, and the Data Terms of Use allow personal non-commercial "
                "access only and bar scripts and systematic retrieval without written permission"),
        "robots": ("cmegroup.com/robots.txt disallows Python-urllib/1.17 entirely; "
                   "/delivery_reports/ is not disallowed for other agents (the terms decide)"),
        "unblock": ("a written CME authorisation (Data Terms of Use: 'Unless CME Group gives "
                    "you prior written permission'), or a licensed vendor feed"),
        "terms": {"url": "https://www.cmegroup.com/files/terms-of-use.pdf",
                  "checked_at": "2026-10-14",
                  "clauses": {
                      "12": ("Except as expressly authorized by CME, you agree not to sell, "
                             "copy, distribute, or create derivative works based on the "
                             "Website, in whole or in part."),
                      "8(vi)": ("Your use of any data, databases, directories content, "
                                "information or materials (including associated metadata) on "
                                "the Website, in any manner for any machine learning and/or "
                                "artificial intelligence [...] is expressly prohibited."),
                      "data_tou:personal": ("You may access content only for your personal use "
                                            "for non-commercial purposes."),
                      "data_tou:automated": (
                          "use of any Web browsers (other than generally available third-party "
                          "browsers), engines, scripts, [...] to navigate, access, copy in bulk, "
                          "retrieve, harvest, index, search or analyze any portion of the "
                          "Website [...] Unless CME Group gives you prior written permission")},
                  "also_read": ("https://www.cmegroup.com/trading/"
                                "market-data-explanation-disclaimer.html",
                                "https://www.cmegroup.com/clearing/operations-and-deliveries/"
                                "nymex-delivery-notices.html")}},
    "lme_warehouse_stocks": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("lme_warehouse_stocks",),
        # A SITE-WIDE hold, deliberately (pass-6 audit SHOULD-FIX, documented): clause 3.1.11
        # bars an API or automated mechanism downloading Information "from any LME website", and
        # 1.1 defines Information as any information on any LME website, so no lme.com route is
        # live input. IDEAS_ONLY, so pages are still read for ideas (platform_of_url is None).
        "url_patterns": (r"^(?:[^/]*\.)?lme\.com/",),
        "wanted": ("LME warehouse stocks and the cancelled-warrant share of live tonnage: the "
                   "deliverable float for copper and the base complex (XCUUSD, XAGUSD)"),
        "why": ("the LME website terms grant a personal licence and bar copying, archiving, "
                "creating Derived Information and any API or automated mechanism to scrape or "
                "download Information from any LME website; the stocks page adds no licence and "
                "routes detailed stocks through licensed data vendors"),
        "robots": "not consulted: the terms already decide",
        "unblock": "an LME market-data licence (LME 'Market data licensing'), or LME's written "
                   "agreement under clause 3.1",
        "terms": {"url": "https://www.lme.com/en/legal/website-terms-and-conditions",
                  "checked_at": "2026-10-14",
                  "clauses": {
                      "2.1": ("grants to the Customer a limited, non-exclusive, revocable, "
                              "personal, and non-transferable licence"),
                      "3.1": "Unless specifically agreed with the LME in writing, the Customer "
                             "shall not",
                      "3.1.2": ("archive the Information, manipulate the information in any way "
                                "or create Derived Information from the Information;"),
                      "3.1.11": ("use an API (or equivalent automated mechanism) to scrape or "
                                 "otherwise download Information from any LME website."),
                      "stocks_page": ("Daily, one-day delayed detailed stock reports are "
                                      "available from our licensed data vendors.")},
                  "also_read": ("https://www.lme.com/en/market-data/reports-and-data/"
                                "warehouse-and-stocks-reports",)}},
    "jpx_short_selling_ratio": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("jpx_short_selling_ratio",),
        "url_patterns": (r"^(?:[^/]*\.)?jpx\.co\.jp/(?:english/)?markets/statistics-equities/"
                         r"short-selling/",),
        "wanted": ("JPX daily short-selling ratio (空売り比率), published after the close: an "
                   "extreme-shorting state for JPN225, USDJPY, EURJPY"),
        "why": ("JPX's site terms bar secondary use and redistribution of the site's information "
                "for any purpose, commercial data collection included, without JPX's permission, "
                "and ask users to refrain from automated retrieval; the statistics page carries "
                "no licence of its own"),
        "robots": "not consulted: the terms already decide",
        "unblock": "JPX's permission (許諾), free or paid, e.g. a JPX Market Information data "
                   "licence covering the short-selling statistics",
        "terms": _JPX_TERMS},
    "jpx_margin_balances": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("jpx_margin_balances",),
        "url_patterns": (r"^(?:[^/]*\.)?jpx\.co\.jp/(?:english/)?markets/statistics-equities/"
                         r"margin/",),
        "wanted": ("JPX weekly margin trading balances (信用取引残高 / 信用残): retail leverage "
                   "build and unwind for JPN225, USDJPY, EURJPY"),
        "why": ("JPX's site terms bar secondary use and redistribution of the site's information "
                "for any purpose without JPX's permission and ask users to refrain from automated "
                "retrieval; the margin page carries no licence of its own (it states only the "
                "schedule: 毎日の信用取引残高をその翌営業日に公表しています。)"),
        "robots": "not consulted: the terms already decide",
        "unblock": "JPX's permission (許諾), free or paid, covering the margin statistics",
        "terms": _JPX_TERMS},
    "jp_tocom_settlements": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("jp_tocom_settlements",),
        "url_patterns": (r"^(?:[^/]*\.)?jpx\.co\.jp/(?:english/)?markets/derivatives/",),
        "wanted": ("OSE (ex-TOCOM) commodity settlements and open interest: the yen gold basis "
                   "for XAUUSD, XAGUSD (asia_collector registry row jp_tocom_settlements)"),
        "why": ("the same JPX site terms (read for F4) bar secondary use of any information on "
                "the site without JPX's permission; found live in asia_sources.json in pass 6"),
        "robots": "not consulted: the terms already decide",
        "unblock": "JPX's permission (許諾), free or paid, covering derivatives settlement data",
        "terms": _JPX_TERMS},
    "us_finra_margin_statistics": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY, "held_route": True,
        "sources": ("us_finra_margin_statistics",),
        "url_patterns": (
            r"^(?:[^/]*\.)?finra\.org/investors/learn-to-invest/advanced-investing/"
            r"margin-statistics",
            r"^(?:[^/]*\.)?finra\.org/.*margin-statistics[^/]*\.xlsx$"),
        "wanted": ("FINRA margin debt and free credit balances (US pack POSITIONING_SOURCES): "
                   "the leverage stock US-F conditions on"),
        "why": ("the margin-statistics page carries no licence of its own (it says only that "
                "FINRA does not provide the data outside of the page and data feeds are not "
                "available), so FINRA's site-wide Terms of Use govern: non-commercial use only, "
                "no robots, no database built from the site. IDEAS_ONLY: the pack may surface "
                "it as an idea, never live input"),
        "robots": "not consulted: the terms already decide",
        "unblock": "a FINRA data licence or written permission for internal commercial research",
        "terms": {"url": "https://www.finra.org/terms-of-use", "checked_at": "2026-10-14",
                  "clauses": {
                      "use": ("shall be used ONLY for your own non-commercial personal or "
                              "professional use."),
                      "robots": ("use any data mining, scraping or harvesting tools (including "
                                 "robots)"),
                      "database": "develop or create a database of data using the FINRA Website",
                      "page": ("FINRA does not provide the data outside of this webpage and "
                               "data feeds are not available.")}}},
    # ---- THE CHINA EXCHANGE HOLDS (pass 6 delta, auditor ruling 2026-10-14: one register). The
    # free-stack roster used to hold these on its own `terms` / `terms_evidence` fields, a second
    # register; the clauses and unread reasons below are that evidence moved verbatim (read
    # 2026-10-06, audit of PR #224). The roster row keeps only a `terms_policy` pointer here.
    # free_stack_hunter holds each through `held_on_terms`; `free_stack_cnx` reads its gate from
    # `terms_verdict` (refused: clauses read that do not grant the use; to_confirm: unread). THE
    # UNBLOCK FLIPS THIS ROW (held_route off, a permitting status and the quoted grant), never a
    # roster field. Missed growth: each exchange's delta E[log W] is UNMEASURED until it flips.
    # WHOLE-HOST holds (pass-6 audit e5a1526f3 MUST-FIX 1), each on its OWN row: cnx_shfe holds
    # shfe.com.cn SITE-WIDE because its commercial bar covers "本网站的任何内容" (any content of
    # this website), as LME 3.1.11 does for lme.com; cnx_ine holds ine.cn on INE's own row (its
    # only clause is the parent's grant, which grants no commercial use, and its own page is
    # UNREAD); DCE, CZCE, GFEX and CFFEX hold their hosts because their terms are UNREAD, which
    # never permits. So the asia_collector registry rows on these hosts (shfe_daily,
    # shfe_member_rank, cffex_member_rank, ...) name these rows through `input_source(url)` and
    # are never requested as live input; ideas mining of the pages is untouched (IDEAS_ONLY).
    "cnx_shfe": _cnx_row(
        "cnx_shfe", "SHFE", host="shfe.com.cn",
        why=("the SHFE site statement grants NON-COMMERCIAL browse/download only (基于非商业目的"
             "浏览、下载) and bars use for profit without written permission; trading on the data "
             "is commercial use, which is not granted (fail closed; audit of PR #224)"),
        unblock="SHFE's written permission (书面许可), quoted into this row's terms",
        url="https://www.shfe.com.cn/disclaimer/",
        clauses={
            "grant": ("在遵守中国有关法律与本声明的前提下，任何机构或者个人可基于非商业目的浏览、"  # noqa: RUF001 -- verbatim
                      "下载本网站的内容。"),
            "commercial_bar": (
                "未经上海期货交易所书面许可，任何机构或者个人不得以向他人出售牟利为目的，使用本网站"  # noqa: RUF001 -- verbatim
                "的任何内容，此种使用包括但不限于拷贝、下载、存贮、通过硬拷贝或电子抓取系统、发送、"  # noqa: RUF001 -- verbatim
                "转换、出租、演示、转载、复制、修改、销售、传播、出版或任何其它形式的散发。")}),
    "cnx_ine": _cnx_row(
        "cnx_ine", "INE", host="ine.cn",
        why=("INE's own disclaimer could not be read (slider-captcha WAF); the parent exchange's "
             "statement (cnx_shfe) grants NON-COMMERCIAL use only and nothing read grants more "
             "(fail closed; audit of PR #224)"),
        unblock="INE's written permission, quoted into this row's terms",
        url="https://www.ine.cn/disclaimer/",
        clauses={"shfe_parent:grant": ("在遵守中国有关法律与本声明的前提下，任何机构或者个人可基于"  # noqa: RUF001 -- verbatim
                                       "非商业目的浏览、下载本网站的内容。")},
        unread={"ine.cn": ("not readable from the build sandbox: the host serves a "
                           "slider-captcha WAF page to the sandbox")}),
    "cnx_dce": _cnx_row(
        "cnx_dce", "DCE", host="dce.com.cn", url="http://www.dce.com.cn/",
        unread={"dce.com.cn": ("not readable from the build sandbox: robots.txt fetch timed out "
                               "from the sandbox")}),
    "cnx_czce": _cnx_row(
        "cnx_czce", "CZCE", host="czce.com.cn", url="http://www.czce.com.cn/",
        unread={"czce.com.cn": ("not readable from the build sandbox: the legal-statement link "
                                "returned HTTP 412 to the sandbox")}),
    "cnx_gfex": _cnx_row(
        "cnx_gfex", "GFEX", host="gfex.com.cn", url="http://www.gfex.com.cn/",
        unread={"gfex.com.cn": ("not readable from the build sandbox: TLS hostname mismatch on "
                                "the sandbox's robots.txt fetch")}),
    "cnx_cffex": _cnx_row(
        "cnx_cffex", "CFFEX", host="cffex.com.cn", url="http://www.cffex.com.cn/",
        unread={"cffex.com.cn": ("not readable from the build sandbox: robots.txt could not be "
                                 "fetched or parsed from the sandbox")}),
}
SOURCE_POLICY.update(_HELD_ROUTES)
#: THE ASIAN PHYSICAL-GOLD STATES (IDEA_QUEUE 245, 237, 228, 215; 2026-10-29). One row per
#: `alt_proxies` source id; `hosts` is empty so the row governs only that source NAME (the SGE
#: graph route `fetch_sge_premium` reads, and the country packs' idea grounds on these hosts,
#: keep whatever row or default they had). A row is LIVE only on a quoted clause of its own terms
#: page; the other three were not readable and are IDEAS_ONLY: never live input, ideas still
#: mined, parsers built on fixtures, and each carries its missed-growth line here and in the
#: state artifact (`asia_gold_physical.missed_growth_lines`). Flipping a row is the only unblock.
_GOLD_MISSED = ("delta E[log W] UNMEASURED: the {state} state for the gold_asia window cannot be "
                "judged until this row's terms are read with a clause permitting automated "
                "access for internal research; no conversion of it is on record")
SOURCE_POLICY.update({
    "hk_gold_reexports": {
        "hosts": (), "url_level": False, "status": API_PERMITTED,
        "sources": ("hk_gold_reexports",),
        "why": ("C&SD trade statistics through the Trade-IDDS API published as a DATA.GOV.HK "
                "resource; the portal's terms (clauses quoted) permit downloading and "
                "reproducing the Data for commercial purposes with attribution, and the API is "
                "the portal's own machine route; robots.txt is read per request (a Disallow is "
                "a hold). One-line revert: status -> IDEAS_ONLY if the auditor reads the "
                "download grant as not covering automated access"),
        "api": "https://tradeidds.censtatd.gov.hk/api/get",
        "api_enquiry": ("https://data.gov.hk/en-data/dataset/hk-censtatd-trade-idds-trade/"
                        "resource/173a8d40-24ff-4e8e-b9f2-456b20208fa4"),
        "robots": ("tradeidds.censtatd.gov.hk refused the terms reader's agent by robots on the "
                   "API spec PDF (2026-10-29); polite_fetch reads robots for DESK_UA on every "
                   "request, and a Disallow is recorded as a hold, never routed around"),
        "credit": ("Source: Census and Statistics Department, HKSAR Government (via "
                   "DATA.GOV.HK); figures modified by the desk (net flow, z-score)"),
        "terms": {"url": "https://data.gov.hk/en/terms-and-conditions",
                  "checked_at": "2026-10-29",
                  "clauses": {
                      "use": ("You are allowed to browse, download, distribute, reproduce, "
                              "hyperlink to, and print the Data for both commercial and "
                              "non-commercial purposes on a free-of-charge basis"),
                      "data": ("“Data” mean the data and all contents provided by the "
                               "Government and/or other organisations"),
                      "attribution": "you shall identify clearly the source of the Data"},
                  "unread": {"https://tradeidds.censtatd.gov.hk/MetadataLink/ApiSpec/"
                             "API_eng.pdf": "ROBOTS_DISALLOWED to the reader on 2026-10-29: "
                                            "the response field names are UNREAD"}}},
    "vn_sjc_premium": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY,
        "sources": ("vn_sjc_premium",),
        "why": ("SJC's price board and the SBV central-rate page could not be read (client "
                "error to the reader, 2026-10-29), so their terms are UNREAD and UNREAD terms "
                "never permit automated live input; the parser is ready on fixtures"),
        "unblock": ("sjc.com.vn and sbv.gov.vn terms read with a clause permitting automated "
                    "access for internal research, quoted into this row, and the row flipped"),
        "missed_growth": {"delta_elogw": "UNMEASURED",
                          "cause": _GOLD_MISSED.format(state="Vietnam SJC premium")},
        "terms": {"url": "https://sjc.com.vn/", "checked_at": "2026-10-29",
                  "unread": {"https://sjc.com.vn/": "client_error to the reader on 2026-10-29",
                             "https://www.sbv.gov.vn/": ("client_error to the reader on "
                                                         "2026-10-29")}}},
    "th_gold_premium": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY,
        "sources": ("th_gold_premium",),
        "why": ("the Gold Traders Association's terms page renders its body by script and the "
                "reader saw navigation only (2026-10-29), so its terms are UNREAD and UNREAD "
                "terms never permit automated live input; the parser is ready on fixtures"),
        "unblock": ("goldtraders.or.th/terms-and-conditions read with a clause permitting "
                    "automated access for internal research (and the BoT reference-rate API's "
                    "terms), quoted into this row, and the row flipped"),
        "missed_growth": {"delta_elogw": "UNMEASURED",
                          "cause": _GOLD_MISSED.format(state="Thai 96.5% bar premium")},
        "terms": {"url": "https://www.goldtraders.or.th/terms-and-conditions",
                  "checked_at": "2026-10-29",
                  "unread": {"https://www.goldtraders.or.th/terms-and-conditions": (
                      "body rendered by script: the reader saw navigation and footer only "
                      "(footer: 'สงวนสิทธิ์ 2567 สมาคมค้าทองคำ') on 2026-10-29")}}},
    "cn_sge_deferral": {
        "hosts": (), "url_level": False, "status": IDEAS_ONLY,
        "sources": ("cn_sge_deferral",),
        "why": ("the SGE site prints only 'Copyright 2016 上海黄金交易所 All Right Reserved' and "
                "links no terms page (read 2026-10-29), so its terms are UNREAD and UNREAD "
                "terms never permit automated live input; the 交收方向 parser is ready on "
                "fixtures"),
        "unblock": ("an SGE statement permitting automated access to its daily quotation "
                    "table for internal research, quoted into this row, and the row flipped"),
        "missed_growth": {"delta_elogw": "UNMEASURED",
                          "cause": _GOLD_MISSED.format(state="SGE Au(T+D) deferral direction")},
        "terms": {"url": "https://www.sge.com.cn/", "checked_at": "2026-10-29",
                  "unread": {"https://www.sge.com.cn/": (
                      "no terms link; footer 'Copyright 2016 上海黄金交易所 All Right Reserved' "
                      "(2026-10-29)")}}},
})
#: The held-route rows, by key (read by `alt_proxies.HELD_ROUTES`).
HELD_ROUTE_KEYS: frozenset[str] = frozenset(
    k for k, r in SOURCE_POLICY.items() if r.get("held_route"))
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
    # THE POLITE CHECKS ON THE FETCH DOOR (audit GD_LANDING_TRAIN_6eb7a91b4 SHOULD-FIX): the
    # site's person-held access hold and its robots.txt, the same two `polite_fetch.get` applies.
    "access_hold": {"status": METHOD_BLOCKED, "reason": "access",
                    "why": ("the site refused the desk (401/403/429 or a WAF/challenge page); "
                            "held until a person releases it, never by a clock")},
    "robots_txt": {"status": METHOD_BLOCKED, "reason": "robots",
                   "why": ("robots.txt disallows this path to the desk's agent, or could not be "
                           "read this run (unreadable robots means no fetch)")},
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
        #: The missed-growth line of a CUT REDIRECT HOP (`record_redirect_cut`), else None.
        self.missed_growth: dict[str, Any] | None = None
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
        if len(segs) == 4 and segs[1] == "web" and segs[3] and ":" not in segs[2]:
            return segs[3] + tail
        if len(segs) >= 3 and segs[1] in ("wait", "save", "wayback", "web"):
            # archive.org/wait/<url>, /save/<url>, /web/<url> with no stamp (pass-6 lanes audit
            # a7698187e SF): the archived page is still the page.
            inner = _embedded("/".join(segs[2:]))
            return (inner + tail) if inner else None
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



def _route_path(path: str, *, params: str = "decoded", decodes: int = 3) -> str:
    """The path a route is matched on, as the server resolves it: percent-decoded (repeatedly,
    so a double-encoded `%255F` cannot hide `_`), NFKC-folded, every run of `/` collapsed, and the
    `.` / `..` dot segments removed (RFC 3986 5.2.4). `params` says where a `;param` is cut:
    "decoded" cuts it after decoding (a servlet container serves `/markets;v=1/x` as
    `/markets/x`; pass-6 audit SHOULD-FIX), "raw" cuts only a RAW `;` BEFORE decoding (so an
    encoded `%3B` stays part of its segment), "none" cuts nothing. Always starts with `/`."""
    p = str(path or "")
    if params == "raw":
        p = "/".join(seg.split(";", 1)[0] for seg in p.split("/"))
    for _ in range(max(0, int(decodes))):
        q = unquote(p)
        if q == p:
            break
        p = q
    p = unicodedata.normalize("NFKC", p).replace("\\", "/")
    out: list[str] = []
    for raw in re.sub(r"/+", "/", p).split("/"):
        seg = raw.split(";", 1)[0] if params == "decoded" else raw
        if seg == ".":
            continue
        if seg == "..":
            if out:
                out.pop()
            continue
        out.append(seg)
    tail = re.sub(r";[^/]*$", "", p) if params == "decoded" else p
    trail = tail.endswith(("/", "/.", "/.."))
    norm = "/" + "/".join(x for x in out if x)
    return norm + "/" if trail and norm != "/" else norm


def _route_paths(path: str) -> tuple[str, ...]:
    """Every reading of `path` a route is matched on -- FAIL CLOSED (pass-6 audit cf305e3d2
    SHOULD-FIX 2): the path with nothing cut, with only RAW `;params` cut before decoding, and
    with `;params` cut after decoding. A route held under ANY reading is held, so neither
    `..;x` nor `..%3Bx` can pop a segment out of a held folder."""
    # EVERY DECODE DEPTH, not only the deepest (pass-6 lanes audit a7698187e SHOULD-FIX): a
    # server that decodes once serves `%252e%252e` as the literal segment `%2e%2e` -- INSIDE the
    # held folder -- while a three-fold decode reads it as `..` and pops out. Held under any
    # depth (0 to 3) is held, so neither the double- nor the triple-encoded dot-dot leaves it.
    return tuple(dict.fromkeys(_route_path(path, params=m, decodes=d)
                               for m in ("none", "raw", "decoded") for d in (3, 2, 1, 0)))


def _pattern_source(url: str) -> str | None:
    """The ROUTE row whose `url_patterns` match this URL's normalized `host + path`, else None.
    A route row (e.g. a held route) governs exactly that route; the rest of its host keeps
    whatever row or default it had. The path is normalized first (`_route_path`), and it is
    matched both as it stands and with a trailing `/`, so `.../short-selling` is the folder
    `.../short-selling/` (pass-6 audit MUST-FIX 1)."""
    parts = _parse(url)
    h = _host(url)
    if parts is None or not h:
        return None
    targets = tuple(t for path in _route_paths(parts.path or "/")
                    for t in (h + path, h + path.rstrip("/") + "/"))
    for name, p in SOURCE_POLICY.items():
        for pat in p.get("url_patterns") or ():
            if any(re.search(pat, t, re.I) for t in targets):
                return name
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
    kp = _pattern_source(url)
    if kp:
        # a route row (`url_patterns`: host + path) names this exact route; a HOLDING host row
        # above still wins, being the stricter answer
        return kp
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
    moved page walks straight through.

    `live_input=True` (a LIVE-INPUT organ's fetch: asia_collector, free_stack, the acquirers)
    also re-runs THE LIVE-INPUT CHECK (`input_source`) on every hop, so a 30x into an IDEAS_ONLY
    held route (JPX short-selling, CME delivery_reports, lme.com, an exchange host) is refused
    exactly as the first URL would have been (pass-6 audit e5a1526f3 MUST-FIX 2). An ideas fetch
    keeps the held-only rule: IDEAS_ONLY pages are still read for ideas."""

    def __init__(self, live_input: bool = False) -> None:
        super().__init__()
        #: Every hop this opener was asked to follow, [(code, from, to)] -- redirects are VISIBLE.
        self.chain: list[tuple[int, str, str]] = []
        self.live_input = bool(live_input)

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        first = self.chain[0][1] if self.chain else str(req.full_url)
        self.chain.append((int(code), str(req.full_url), str(newurl)))
        held = platform_of_url(newurl)
        ideas = input_source(newurl) if (self.live_input and not held) else None
        if ideas and same_source_hop(first, newurl):
            # A hop that stays inside the FIRST URL's own registered source (one policy row:
            # query1 -> query2.finance.yahoo.com, www -> old.reddit.com) is the same read the
            # first URL already was, never a route into ANOTHER held route (pass-6 lanes audit
            # a7698187e MUST-FIX 3). A route row is its own source, so a hop from an open
            # jpx.co.jp page into the held short-selling folder is still cut.
            ideas = None
        # METHOD: a redirect into a held source or a login / CAPTCHA wall is refused, never
        # followed; the 3xx response's socket is released before the refusal is raised. Every
        # cut hop leaves its missed-growth line (`record_redirect_cut`), never a silent None.
        cut = held or ideas or ("login_wall" if login_wall(newurl) else None)
        if cut:
            with contextlib.suppress(Exception):
                fp.read()
                fp.close()
            exc = TermsFenced(cut, newurl)
            exc.missed_growth = record_redirect_cut(cut, str(req.full_url), str(newurl),
                                                    first, live_input=bool(ideas))
            raise exc
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            check_request(new.full_url, _req_headers(new))
        return new


def same_source_hop(first_url: str, new_url: str) -> bool:
    """True when a redirect from a chain that began at `first_url` lands on the SAME policy row
    (`source_of_url`) -- the first URL's own registered source -- and that row is not held. A
    row is the register's unit of a source, so a route row (a held folder on an open host) is
    never the same source as the host's open pages."""
    k2 = source_of_url(new_url)
    return k2 is not None and k2 == source_of_url(first_url) and status(k2) not in HOLDING


#: Where every cut redirect hop's missed-growth line is appended (state, one JSON per line).
#: `QUANT_REDIRECT_CUTS` overrides it; under pytest with no override the line is kept in
#: memory only, so a test never writes the box's ledger.
REDIRECT_CUTS_PATH = (os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "desks", "mt5", "data", "redirect_cuts.jsonl"))
#: The process's recent cut-hop lines (bounded), for an organ that reports them in-process.
REDIRECT_CUTS: list[dict[str, Any]] = []
_REDIRECT_CUTS_MAX = 500


def _redirect_cuts_path() -> str | None:
    env = os.environ.get("QUANT_REDIRECT_CUTS", "").strip()
    if env:
        return None if env.lower() in ("off", "0", "none") else env
    return None if os.environ.get("PYTEST_CURRENT_TEST") else REDIRECT_CUTS_PATH


def record_redirect_cut(cut: str, from_url: str, to_url: str, first_url: str = "", *,
                        live_input: bool = False) -> dict[str, Any]:
    """GROWTH GOVERNANCE: the missed-growth line a CUT REDIRECT HOP carries (kind redirect_cut,
    delta E[log W] UNMEASURED, never zero, with its cause). Kept in `REDIRECT_CUTS` and appended
    to the ledger (`_redirect_cuts_path`); a failed write is LOUD, never fatal to the refusal."""
    from datetime import UTC, datetime
    try:
        v = _view(cut)
        policy_status, why = str(v.get("status") or ""), str(v.get("reason") or "")
    except Exception:
        policy_status, why = "", ""
    line: dict[str, Any] = {
        "kind": "redirect_cut", "source": cut, "policy_status": policy_status,
        "status": IDEAS_ONLY if live_input else (policy_status or "REFUSED"),
        "from": str(from_url)[:300], "to": str(to_url)[:300], "first_url": str(first_url)[:300],
        "delta_elogw": "UNMEASURED",
        "at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "cause": (f"a redirect hop into {cut} ({why or 'refused'}) was cut "
                  f"{'as live input ' if live_input else ''}and never followed, so the series "
                  "the first URL would have returned was not read; the growth forgone is "
                  "UNMEASURED, never zero"),
        "unblock": ("the source's own terms permitting automated access for this use (a "
                    "SOURCE_POLICY row change), or a fetcher whose first URL is that source")}
    REDIRECT_CUTS.append(line)
    del REDIRECT_CUTS[:-_REDIRECT_CUTS_MAX]
    path = _redirect_cuts_path()
    if path:
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, sort_keys=True) + "\n")
        except OSError as exc:
            print(f"terms_fence: redirect cut line NOT written ({type(exc).__name__}: {exc})",
                  flush=True)
    return line


def redirect_cut_lines(path: str | None = None, *, limit: int = 200) -> list[dict[str, Any]]:
    """The last `limit` cut-hop missed-growth lines on the ledger (an absent ledger: none)."""
    p = path or _redirect_cuts_path() or REDIRECT_CUTS_PATH
    try:
        with open(p, encoding="utf-8") as fh:
            rows = fh.read().splitlines()[-max(0, int(limit)):]
    except OSError:
        return list(REDIRECT_CUTS[-limit:])
    out: list[dict[str, Any]] = []
    for ln in rows:
        with contextlib.suppress(ValueError):
            row = json.loads(ln)
            if isinstance(row, dict):
                out.append(row)
    return out


class TermsGuardProcessor(urllib.request.BaseHandler):
    """Runs on EVERY request the opener sends, the first and each redirected one: a fenced
    request raises before a connection is opened."""

    handler_order = 100

    def http_request(self, req: urllib.request.Request) -> urllib.request.Request:
        check_request(req.full_url, _req_headers(req))
        return req

    https_request = http_request


class AccessRefused(TermsFenced):
    """The fetch door refused a URL on the polite checks: a person-held access hold on its site
    (`platform == "access_hold"`) or its origin's robots.txt (`"robots_txt"`). `verdict` is the
    access record's own word (METHOD_BLOCKED, NEEDS_KEY, ROBOTS_DISALLOW, ROBOTS_UNREADABLE ...)."""

    def __init__(self, verdict: str, url: str) -> None:
        self.verdict = str(verdict or "")
        word = self.verdict.split(" ")[0].split(":")[0].upper()
        super().__init__("robots_txt" if word.startswith(("ROBOTS", "SCHEME")) else
                         "access_hold", url)


class AccessGuardProcessor(urllib.request.BaseHandler):
    """THE POLITE CHECKS ON EVERY REQUEST THE DOOR SENDS, the first and each redirect hop: the
    site's person-held hold and the hop's own origin robots.txt (`polite_fetch.HostAccess.permits`,
    the same record `polite_fetch.get` uses) are asked BEFORE the request goes out; a refusal
    raises `AccessRefused` and nothing is sent. A 401/403/429 -- or a challenge recognised by
    header or status -- records a person-held hold on the site that REFUSED (the hop's own URL,
    not the first one), so nothing else is sent to it by any route until a person releases it.

    robots.txt itself is read through `polite_fetch.open_no_redirect` (the door's opener WITHOUT
    this processor), so the check never recurses into itself."""

    handler_order = 110

    def __init__(self, access: Any = None) -> None:
        self.access = access

    def _acc(self) -> Any:
        if self.access is None:
            from libs.data import polite_fetch as _pf
            self.access = _pf.default_access()
        return self.access

    def http_request(self, req: urllib.request.Request) -> urllib.request.Request:
        ok, why = self._acc().permits(req.full_url)
        if not ok:
            raise AccessRefused(why, req.full_url)
        return req

    https_request = http_request

    def http_response(self, req: urllib.request.Request, resp: Any) -> Any:
        from libs.data import polite_fetch as _pf
        code = int(getattr(resp, "code", None) or getattr(resp, "status", None) or 0)
        if code in _pf.BLOCK_STATUS:
            self._acc().block(req.full_url, code)
        else:
            marker = _pf.looks_challenged(b"", getattr(resp, "headers", None), code)
            if marker:
                self._acc().block(req.full_url, "WAF", "METHOD_BLOCKED",
                                  f"challenge ({marker!r}) at the fetch door, HTTP {code}")
        return resp

    https_response = http_response


def guarded_opener(context: Any = None, *handlers: Any,
                   live_input: bool = False) -> urllib.request.OpenerDirector:
    """An opener whose redirects and requests are terms-fenced. `context` is the SSL context the
    caller would have passed to `urlopen`; `live_input` re-checks `input_source` on every hop."""
    hs: list[Any] = [FencedRedirectHandler(live_input=live_input), TermsGuardProcessor()]
    if context is not None:
        hs.append(urllib.request.HTTPSHandler(context=context))
    return urllib.request.build_opener(*hs, *handlers)


def guarded_urlopen(req: Any, *, timeout: float | None = 30.0, context: Any = None,
                    live_input: bool = False, live_hops: bool = False,
                    access: Any = None) -> Any:
    """THE ONE FETCH DOOR (`polite_fetch.fenced_urlopen` is this function): `urlopen` with the
    fence. The URL is checked BEFORE any request is built (a held source, or a first URL that is
    itself a login wall, raises `TermsFenced`); a redirect into a held source or a login wall
    raises instead of being followed; every hop followed is kept on the response as
    `.redirects` [(code, from, to)]. `timeout=None` means the socket default. `live_input=True`
    (a live-input organ) refuses an IDEAS_ONLY or held first URL and every such redirect hop
    (`input_source`), not only the held ones. `live_hops=True` re-checks every redirect HOP that
    way but leaves the first URL to the held-only rule: a live fetcher whose first URL is itself
    an IDEAS_ONLY row it already reads (Yahoo) can never be redirected into another held route
    (pass-6 audit cf305e3d2 SHOULD-FIX 1), while what it reads first is unchanged.

    THE POLITE CHECKS (audit GD_LANDING_TRAIN_6eb7a91b4): every request -- the first URL and
    each redirect hop -- also passes `AccessGuardProcessor`: the site's person-held hold and the
    hop's origin robots.txt, from `access` (default `polite_fetch.default_access()`, the record
    `pf.get` uses), refuse BEFORE anything is sent; a 401/403/429 or challenge holds the refusing
    site until a person releases it."""
    url = req.full_url if isinstance(req, urllib.request.Request) else str(req)
    hdrs = _req_headers(req) if isinstance(req, urllib.request.Request) else None
    check_request(url, hdrs)
    if login_wall(url):
        raise TermsFenced("login_wall", url)
    if live_input:
        k = input_source(url)
        if k:
            raise TermsFenced(k, url)
    guard = AccessGuardProcessor(access)
    guard.http_request(req if isinstance(req, urllib.request.Request)
                       else urllib.request.Request(url))     # refuse before building anything
    opener = guarded_opener(context, guard)
    for h in getattr(opener, "handlers", ()):
        if isinstance(h, FencedRedirectHandler):
            h.live_input = h.live_input or bool(live_input) or bool(live_hops)  # every hop
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


#: The status a live-input organ records for a source this register holds on its terms.
HELD_ON_TERMS = "HELD_ON_TERMS"


def held_on_terms(key: str) -> bool:
    """True only for a HELD ROUTE of this register (`held_route`): a route whose own terms carry
    no permitting clause, so nothing is fetched for it at all. An IDEAS_ONLY source is NOT held
    here (auditor ruling 2026-10-14): it keeps being read for ideas and is labelled IDEAS_ONLY;
    the live-input check (`input_source`) alone keeps it out of live input data. A NEEDS_KEY row
    and an unlisted key are not held on terms either."""
    row = SOURCE_POLICY.get(key)
    return bool(row and row.get("held_route"))


def held_missed_growth(key: str, past: Mapping[str, Any] | None = None, *,
                       source: str | None = None, live_input_refusal: bool = False
                       ) -> dict[str, Any]:
    """GROWTH GOVERNANCE: the missed-growth line a hold carries. A held route stops a fetch
    (kind terms_hold, HELD_ON_TERMS); an IDEAS_ONLY row refused as LIVE INPUT stops a live series
    while its ideas are still mined (kind ideas_only_refusal, IDEAS_ONLY). Either way the line
    names what was converted before (`past`, the organ's own record) or says that no conversion
    is on record; delta E[log W] is UNMEASURED, never zero. `source` is the organ's row id when it
    differs from the policy key."""
    row = SOURCE_POLICY[key]
    what = ("refused as live input, ideas still mined" if live_input_refusal
            else "held on terms")
    line: dict[str, Any] = {"source": source or key,
                            "kind": "ideas_only_refusal" if live_input_refusal else "terms_hold",
                            "status": IDEAS_ONLY if live_input_refusal else HELD_ON_TERMS,
                            "policy_row": key,
                            "policy_status": str(row["status"]), "delta_elogw": "UNMEASURED",
                            "terms_url": str((row.get("terms") or {}).get("url") or ""),
                            "unblock": str(row.get("unblock") or row.get("permitted_route")
                                           or "")}
    if past:
        line["past_conversion"] = dict(past)
        line["cause"] = (f"{what} ({row['why']}); the conversion recorded before the hold is in "
                         "past_conversion; the growth forgone is UNMEASURED until the unblock "
                         "arrives and the cells are judged")
    else:
        line["cause"] = (f"{what} ({row['why']}); no measured conversion on record (no "
                         "observation, cell or gain test of this source exists in the organ's "
                         "record), so the growth forgone is UNMEASURED, never zero")
    return line


if __name__ == "__main__":
    print(json.dumps(registry_rows(), indent=1))
