"""LAWFUL FEEDS FOR THE SIDE-CHANNEL MINERS WHOSE OWN SITE MAY NOT BE FETCHED (2026-11-19).

The principal's order of 2026-11-19 19:46Z: all 25 side-channel miners run and none is ever
switched off. At 19:58Z: where a site bans bots but has a free official API, use the API, and
where it has none, use a substitute source. The terms reads of the same day (quoted below, full
record in /mnt/project-files/terms/side_channel_terms_2026-11-19.md) found that:

* mql5.com (Terms 3.7: "not to access the website www.mql5.com through any automated means,
  including use of scripts, crawlers"), quantconnect.com (Terms v1.5 2026-10-08, 3.3(b)(x): "use
  any robot, spider, or other automatic device, process, or means to access the Site") and
  investing.com (Terms Aug 2026, 10(c): "expressly forbidden from employing any automated system
  or software to extract data") ban automated access outright;
* sec.gov's robots.txt disallows /cgi-bin for every agent, and trends.google.com's disallows
  /trends/explore?, the exact paths the sec_edgar and google_trends miners requested;
* tradingview, yahoo, reddit, cnn, eastmoney, zhihu, naver, tradingeconomics and ssrn could not
  be read to the end the same day, so their terms are UNCONFIRMED, and an unconfirmed site is
  not fetched (LAWS 5e act 6).

So each of those channels runs here on an official, keyless API whose terms ARE on record, and
writes to the channel's own seat under data/intelligence/<seat>/, where the compiler already
reads. No channel is SET_ASIDE for terms any more; a channel whose feed answers nothing reports
a zero, which is a measurement.

Every source below has its terms quoted (TERMS) and its robots.txt read at run time under the
same honest agent the feed then uses; robots that cannot be read, or that answer HTML, refuse
(fail closed: only 404/410 means no rules). No browser User-Agent, no login, no key, no account.
RESEARCH ONLY: rows go to the miner compiler and the judge, nothing else.
"""
from __future__ import annotations

import functools
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
INTEL = BASE / "data" / "intelligence"

ROBOTS_AGENT = "quant-desk-research"
HONEST_UA = f"{ROBOTS_AGENT}/1.0 (side-channel lawful feeds; research; honours robots.txt)"
TIMEOUT_S = 20

#: The terms on record for every host this module contacts. A host absent here is never fetched.
TERMS: dict[str, dict[str, str]] = {
    "api.github.com": {
        "url": "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service",
        "quote": ("H. API Terms: All use of the GitHub API is subject to these Terms of Service "
                  "and the GitHub Privacy Statement. [...] Abuse or excessively frequent "
                  "requests to GitHub via the API may result in the temporary or permanent "
                  "suspension of your Account's access to the API. (Effective April 27, 2026)"),
        "checked": "2026-11-19"},
    "api.gdeltproject.org": {
        "url": "https://gdeltproject.org/about.html",
        "quote": ("all datasets released by the GDELT Project are available for unlimited and "
                  "unrestricted use for any academic, commercial, or governmental use of any "
                  "kind without fee."),
        "checked": "2026-11-19"},
    "wikimedia.org": {
        "url": "https://dumps.wikimedia.org/other/pageviews/readme.html",
        "quote": "All Analytics datasets are available under the Creative Commons CC0 dedication.",
        "checked": "2026-11-19"},
    "export.arxiv.org": {
        "url": "https://info.arxiv.org/help/api/tou.html",
        "quote": ("make no more than one request every three seconds, and limit requests to a "
                  "single connection at a time."),
        "checked": "2026-11-19"},
    "data.sec.gov": {
        "url": "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        "quote": ("Current max request rate: 10 requests/second. [...] Please declare your user "
                  "agent in request headers"),
        "checked": "2026-11-19"},
    "www.sec.gov": {
        "url": "https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data",
        "quote": ("Current max request rate: 10 requests/second; robots.txt: "
                  "Allow: /Archives/edgar/data"),
        "checked": "2026-11-19"},
    "www.aaii.com": {
        "url": "https://www.aaii.com/privacy/tos",
        "quote": ("no clause on automated access, robots or scraping (silent); section 6: "
                  "\"No part of the contents of the website or newsletter may be copied or "
                  "forwarded to anyone else;\" -- rows carry readings only. robots.txt: "
                  "Crawl-delay: 10 (undated page)"),
        "checked": "2026-11-19"},
    "services9.arcgis.com": {
        "url": "https://www.imf.org/external/terms.htm",
        "quote": ("Users may download, extract, copy, create derivative works, publish, "
                  "distribute, and sell Data obtained from IMF Sites, including for commercial "
                  "purposes"),
        "checked": "2026-11-19"},
}

#: Hosts whose own terms ban automated access, kept so no later edit points a feed at them.
REFUSED_HOSTS: dict[str, str] = {
    "www.mql5.com": "Terms 3.7: not to access the website through any automated means",
    "www.quantconnect.com": "Terms 3.3(b)(x): no robot, spider or other automatic device",
    "www.investing.com": "Terms 10(c): expressly forbidden from employing any automated system",
    "kr.investing.com": "Terms 10(c): expressly forbidden from employing any automated system",
}

SYMBOLS = ("XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
           "NZDUSD", "EURJPY", "GBPJPY", "AUDJPY", "US500", "NAS100", "US30", "GER40", "UK100",
           "JPN225", "XTIUSD", "XBRUSD", "XNGUSD", "USDCNH", "USDKRW", "CHINAH", "AUS200")
PATTERNS = ("breakout", "mean reversion", "momentum", "trend following", "grid", "scalping",
            "carry", "session", "london open", "asia range", "order block", "liquidity",
            "pairs trading", "statistical arbitrage", "cointegration", "seasonality",
            "volatility", "news", "sentiment", "regime")

#: Seconds between requests to one host: arXiv's terms (3s), aaii's and PortWatch's robots
#: Crawl-delay (10s, 60s); everyone else 1s, which keeps EDGAR far under its 10 requests/second.
PACE_S: dict[str, float] = {"export.arxiv.org": 3.0, "www.aaii.com": 10.0,
                            "services9.arcgis.com": 60.0}

Getter = Callable[..., Any]


def _default_get() -> Getter:
    import requests
    return requests.get


class _Gate:
    """robots.txt per host, read once per run under HONEST_UA; refuse on anything but a parse."""

    def __init__(self, get: Getter, ua: Callable[[str], str]) -> None:
        self.get = get
        self.ua = ua
        self.cache: dict[str, urllib.robotparser.RobotFileParser | None | str] = {}

    def refusal(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc
        if host in REFUSED_HOSTS:
            return f"TERMS_REFUSED: {REFUSED_HOSTS[host]}"
        if host not in TERMS:
            return "TERMS_UNCONFIRMED: no terms on record for this host"
        if host not in self.cache:
            try:
                resp = self.get(f"{parts.scheme}://{host}/robots.txt",
                                headers={"User-Agent": self.ua(host)}, timeout=TIMEOUT_S)
                status = getattr(resp, "status_code", None)
                body = str(getattr(resp, "text", "") or "")
                if status in (404, 410):
                    self.cache[host] = None
                elif status != 200:
                    self.cache[host] = f"ROBOTS_REFUSED: robots.txt answered {status}"
                elif body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                    self.cache[host] = "ROBOTS_REFUSED: robots.txt answered HTML"
                else:
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(body.splitlines())
                    self.cache[host] = rp
            except Exception as exc:                    # an unreadable gate refuses
                self.cache[host] = f"ROBOTS_REFUSED: robots.txt unreadable ({type(exc).__name__})"
        rule = self.cache[host]
        if isinstance(rule, str):
            return rule
        if rule is not None and not rule.can_fetch(ROBOTS_AGENT, url):
            return f"ROBOTS_REFUSED: robots.txt disallows {parts.path}"
        return None


def _edgar_ua() -> str:
    try:
        from sec_edgar_miner import edgar_ua
    except ModuleNotFoundError:
        from side_channels.sec_edgar_miner import edgar_ua
    return edgar_ua()


def _ua_for(host: str) -> str:
    """SEC's fair-access policy wants the declared contact string; everyone else gets HONEST_UA."""
    if host.endswith("sec.gov"):
        return _edgar_ua() or ""
    return HONEST_UA


class Feed:
    """One run's fetcher: gate, honest agent, polite pacing per host, and a report of refusals."""

    def __init__(self, get: Getter | None = None, *, pace_s: float | None = None) -> None:
        self.get = get or _default_get()
        self.gate = _Gate(self.get, _ua_for)
        self.refused: dict[str, str] = {}
        self.errors: dict[str, str] = {}
        self.pace_s = pace_s
        self._last: dict[str, float] = {}

    def _pace(self, host: str) -> None:
        gap = self.pace_s if self.pace_s is not None else PACE_S.get(host, 1.0)
        wait = self._last.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    def json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self._fetch(url, params, as_json=True)

    def text(self, url: str, params: dict[str, Any] | None = None) -> str | None:
        return self._fetch(url, params, as_json=False)

    def _fetch(self, url: str, params: dict[str, Any] | None, *, as_json: bool) -> Any:
        host = urllib.parse.urlsplit(url).netloc
        ua = _ua_for(host)
        if not ua:
            self.refused[host] = "UNCONFIGURED: no EDGAR contact string (EDGAR_UA)"
            return None
        why = self.gate.refusal(url)
        if why:
            self.refused[host] = why
            return None
        self._pace(host)
        headers = {"User-Agent": ua}
        if host == "api.github.com" and os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {os.environ['GITHUB_TOKEN']}"
        try:
            resp = self.get(url, params=params, headers=headers, timeout=TIMEOUT_S)
            status = getattr(resp, "status_code", None)
            if status in (401, 403, 429, 451):          # a hard stop: never retried
                self.refused[host] = f"HARD_STOP: HTTP {status}"
                return None
            if status != 200:
                self.errors[host] = f"HTTP {status}"
                return None
            return resp.json() if as_json else str(resp.text)
        except Exception as exc:
            self.errors[host] = f"{type(exc).__name__}: {str(exc)[:120]}"
            return None


def _symbols(text: str) -> list[str]:
    up = text.upper()
    return [s for s in SYMBOLS if s in up]


def _patterns(text: str) -> list[str]:
    low = text.lower()
    return [p for p in PATTERNS if p in low]


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ----------------------------------------------------------------------------- the four feeds

def github_code(feed: Feed, channel: str, queries: tuple[str, ...]) -> list[dict[str, Any]]:
    """Repositories naming a mechanism: the official, documented GitHub search API."""
    since = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%d")
    rows: list[dict[str, Any]] = []
    for q in queries:
        got = feed.json("https://api.github.com/search/repositories",
                        {"q": f"{q} pushed:>{since}", "sort": "updated", "order": "desc",
                         "per_page": 20})
        for item in (got or {}).get("items", []) if isinstance(got, dict) else []:
            text = f"{item.get('name', '')} {item.get('description') or ''}"
            syms, pats = _symbols(text), _patterns(text)
            if not syms and not pats:
                continue
            rows.append({"source": channel, "feed": "github_api", "query": q,
                         "title": item.get("full_name", ""), "url": item.get("html_url", ""),
                         "description": (item.get("description") or "")[:500],
                         "stars": item.get("stargazers_count", 0),
                         "updated": item.get("updated_at", ""), "symbols": syms,
                         "patterns": pats, "discovered_at": _now()})
    return rows


def gdelt_news(feed: Feed, channel: str, queries: tuple[str, ...]) -> list[dict[str, Any]]:
    """Articles and their tone from the GDELT DOC 2.0 API (unrestricted use, no key)."""
    rows: list[dict[str, Any]] = []
    for q in queries:
        got = feed.json("https://api.gdeltproject.org/api/v2/doc/doc",
                        {"query": q, "mode": "artlist", "format": "json", "maxrecords": 50,
                         "timespan": "3d", "sort": "datedesc"})
        for art in (got or {}).get("articles", []) if isinstance(got, dict) else []:
            title = str(art.get("title") or "")
            rows.append({"source": channel, "feed": "gdelt_doc", "query": q, "title": title[:300],
                         "url": art.get("url", ""), "seendate": art.get("seendate", ""),
                         "domain": art.get("domain", ""), "language": art.get("language", ""),
                         "sourcecountry": art.get("sourcecountry", ""),
                         "symbols": _symbols(title), "patterns": _patterns(title),
                         "discovered_at": _now()})
    return rows


def gdelt_tone(feed: Feed, channel: str, queries: tuple[str, ...]) -> list[dict[str, Any]]:
    """Average news tone per query over the last week: a fear/greed reading from the news flow."""
    rows: list[dict[str, Any]] = []
    for q in queries:
        got = feed.json("https://api.gdeltproject.org/api/v2/doc/doc",
                        {"query": q, "mode": "timelinetone", "format": "json", "timespan": "7d"})
        series = ((got or {}).get("timeline") or [{}])[0].get("data", []) \
            if isinstance(got, dict) else []
        vals = [float(p["value"]) for p in series if isinstance(p, dict)
                and isinstance(p.get("value"), (int, float))]
        if not vals:
            continue
        last, mean = vals[-1], sum(vals) / len(vals)
        rows.append({"source": channel, "feed": "gdelt_timelinetone", "query": q,
                     "title": f"news tone {q}: last {last:.2f} vs 7d mean {mean:.2f}",
                     "tone_last": last, "tone_mean_7d": mean, "tone_delta": last - mean,
                     "points": len(vals), "symbols": _symbols(q), "patterns": ["sentiment"],
                     "discovered_at": _now()})
    return rows


def wiki_attention(feed: Feed, channel: str, articles: dict[str, tuple[str, ...]]
                   ) -> list[dict[str, Any]]:
    """Daily English-Wikipedia pageviews (CC0): retail attention per instrument, last 30 days."""
    end = datetime.now(UTC) - timedelta(days=1)
    start = end - timedelta(days=30)
    rows: list[dict[str, Any]] = []
    for article, syms in articles.items():
        url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
               f"all-access/user/{urllib.parse.quote(article, safe='')}/daily/"
               f"{start:%Y%m%d}00/{end:%Y%m%d}00")
        got = feed.json(url)
        items = (got or {}).get("items", []) if isinstance(got, dict) else []
        views = [int(i.get("views", 0)) for i in items if isinstance(i, dict)]
        if len(views) < 8:
            continue
        base = sum(views[:-7]) / max(1, len(views) - 7)
        recent = sum(views[-7:]) / 7
        rows.append({"source": channel, "feed": "wikimedia_pageviews", "article": article,
                     "title": f"attention {article}: 7d {recent:.0f}/day vs prior {base:.0f}/day",
                     "views_7d_mean": recent, "views_prior_mean": base,
                     "attention_ratio": (recent / base) if base else None,
                     "symbols": list(syms), "patterns": ["sentiment"], "discovered_at": _now()})
    return rows


def arxiv_papers(feed: Feed, channel: str, queries: tuple[str, ...]) -> list[dict[str, Any]]:
    """Recent q-fin papers through the arXiv API (its terms permit it at 1 request per 3s)."""
    rows: list[dict[str, Any]] = []
    for q in queries:
        body = feed.text("https://export.arxiv.org/api/query",
                         {"search_query": q, "sortBy": "submittedDate", "sortOrder": "descending",
                          "max_results": 25})
        if not body:
            continue
        for entry in re.findall(r"<entry>(.*?)</entry>", body, flags=re.S):
            title = re.sub(r"\s+", " ", (re.findall(r"<title>(.*?)</title>", entry, re.S)
                                         or [""])[0]).strip()
            link = (re.findall(r"<id>(.*?)</id>", entry) or [""])[0].strip()
            summary = re.sub(r"\s+", " ", (re.findall(r"<summary>(.*?)</summary>", entry, re.S)
                                           or [""])[0]).strip()
            rows.append({"source": channel, "feed": "arxiv_api", "query": q, "title": title,
                         "url": link, "abstract": summary[:800],
                         "symbols": _symbols(f"{title} {summary}"),
                         "patterns": _patterns(f"{title} {summary}"), "discovered_at": _now()})
    return rows


#: The large 13F filers the sec_edgar miner tracked, read through data.sec.gov (robots-allowed,
#: fair-access UA) instead of /cgi-bin/browse-edgar, which sec.gov's robots.txt disallows.
FUND_CIKS = {"Bridgewater": "0001350694", "Renaissance": "0001037389",
             "Citadel": "0001423053", "Two Sigma": "0001179392", "DE Shaw": "0001009207",
             "Millennium": "0001273087", "AQR": "0001167557"}


def sec_filings(feed: Feed, channel: str, forms: tuple[str, ...]) -> list[dict[str, Any]]:
    """Recent filings of the given forms by the tracked filers (EDGAR submissions API)."""
    rows: list[dict[str, Any]] = []
    for fund, cik in FUND_CIKS.items():
        got = feed.json(f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json")
        recent = ((got or {}).get("filings") or {}).get("recent") or {} \
            if isinstance(got, dict) else {}
        for form, date, acc in list(zip(recent.get("form", []), recent.get("filingDate", []),
                                        recent.get("accessionNumber", []), strict=False))[:40]:
            if form not in forms:
                continue
            rows.append({"source": channel, "feed": "sec_submissions_api", "fund": fund,
                         "cik": cik, "form": form, "title": f"{fund} filed {form} {date}",
                         "filing_date": date, "accession": acc,
                         "url": (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                                 f"{acc.replace('-', '')}/"),
                         "symbols": [], "patterns": ["positioning"], "discovered_at": _now()})
    return rows


def sec_daily_8k(feed: Feed, channel: str, days: int = 5) -> list[dict[str, Any]]:
    """8-K counts per business day from the EDGAR daily form index (/Archives, robots-allowed):
    the intensity of the earnings and guidance season, not any single name."""
    rows: list[dict[str, Any]] = []
    day = datetime.now(UTC).date()
    seen = 0
    for back in range(1, days * 2 + 4):
        d = day - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        q = (d.month - 1) // 3 + 1
        body = feed.text(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/"
                         f"form.{d:%Y%m%d}.idx")
        if body is None:
            continue
        n8k = sum(1 for line in body.splitlines() if line.startswith("8-K "))
        rows.append({"source": channel, "feed": "sec_daily_form_index", "date": d.isoformat(),
                     "title": f"8-K filings {d.isoformat()}: {n8k}", "count_8k": n8k,
                     "symbols": ["US500", "NAS100", "US30"], "patterns": ["news"],
                     "discovered_at": _now()})
        seen += 1
        if seen >= days:
            break
    return rows


def portwatch_chokepoints(feed: Feed, channel: str) -> list[dict[str, Any]]:
    """Daily transit calls through the shipping chokepoints (IMF PortWatch, IMF data terms)."""
    url = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
           "Daily_Chokepoints_Data/FeatureServer/0/query")
    since = (datetime.now(UTC) - timedelta(days=21)).strftime("%Y-%m-%d")
    got = feed.json(url, {"where": f"date >= DATE '{since}'", "outFields": "portname,date,n_total",
                          "orderByFields": "date DESC", "resultRecordCount": 2000, "f": "json"})
    feats = (got or {}).get("features", []) if isinstance(got, dict) else []
    by_port: dict[str, list[float]] = {}
    for f in feats:
        a = (f or {}).get("attributes") or {}
        if a.get("portname") and isinstance(a.get("n_total"), (int, float)):
            by_port.setdefault(str(a["portname"]), []).append(float(a["n_total"]))
    rows: list[dict[str, Any]] = []
    for port, vals in by_port.items():
        if len(vals) < 8:
            continue
        recent, prior = sum(vals[:7]) / 7, sum(vals[7:]) / len(vals[7:])
        rows.append({"source": channel, "feed": "imf_portwatch_chokepoints", "port": port,
                     "title": f"{port} transits 7d {recent:.1f}/day vs prior {prior:.1f}/day",
                     "transits_7d": recent, "transits_prior": prior,
                     "transit_ratio": (recent / prior) if prior else None,
                     "symbols": ["XTIUSD", "XBRUSD", "XNGUSD"], "patterns": ["seasonality"],
                     "discovered_at": _now()})
    return rows


# ----------------------------------------------------------------------------- the channels

#: channel -> (seat directory, the original host the substitute replaces, the feed, why)
SUBSTITUTES: dict[str, tuple[str, str, Callable[[Feed, str], list[dict[str, Any]]], str]] = {
    "mql5_codebase": ("mql5", "www.mql5.com", functools.partial(
        github_code, queries=("mql5 expert advisor", "mt5 expert advisor strategy")),
        "mql5.com bans automated access (Terms 3.7); its EAs are mirrored on GitHub"),
    "mql5_articles": ("mql5", "www.mql5.com", functools.partial(
        github_code, queries=("mql5 indicator", "metatrader 5 trading strategy")),
        "mql5.com bans automated access (Terms 3.7); article code lives on GitHub"),
    "mql5_signals": ("mql5", "www.mql5.com", functools.partial(
        github_code, queries=("mt5 signal copier", "forex signal provider strategy")),
        "mql5.com bans automated access (Terms 3.7)"),
    "mql5_forum": ("mql5", "www.mql5.com", functools.partial(
        gdelt_news, queries=('"MetaTrader 5" trading', '"expert advisor" forex')),
        "mql5.com bans automated access (Terms 3.7)"),
    "tradingview": ("tradingview", "www.tradingview.com", functools.partial(
        github_code, queries=("pine script strategy", "tradingview strategy backtest")),
        "tradingview terms unconfirmed; Pine strategies are published on GitHub"),
    "quantconnect": ("quantconnect", "www.quantconnect.com", functools.partial(
        github_code, queries=("quantconnect lean algorithm", "lean algorithm forex")),
        "quantconnect.com bans robots (Terms 3.3(b)(x)); Lean algorithms are on GitHub"),
    "reddit": ("reddit", "www.reddit.com", functools.partial(
        wiki_attention, articles={"Gold_as_an_investment": ("XAUUSD",),
                                  "Euro": ("EURUSD",), "Japanese_yen": ("USDJPY",),
                                  "S&P_500": ("US500",), "Nasdaq-100": ("NAS100",),
                                  "Petroleum": ("XTIUSD",), "Silver": ("XAGUSD",)}),
        "reddit terms unconfirmed and its API needs an account; Wikipedia attention instead"),
    "forexfactory": ("forexfactory", "www.forexfactory.com", functools.partial(
        gdelt_news, queries=('"nonfarm payrolls"', '"CPI" inflation data',
                             '"rate decision" central bank', '"PMI" manufacturing')),
        "Forex Factory's and faireconomy.media's terms could not be read; GDELT release news"),
    "sec_edgar": ("sec_edgar", "www.sec.gov/cgi-bin", functools.partial(
        sec_filings, forms=("13F-HR", "13F-HR/A", "SC 13G", "SC 13D")),
        "sec.gov robots disallows /cgi-bin; the EDGAR submissions API is the documented route"),
    "earnings": ("earnings", "finance.yahoo.com", sec_daily_8k,
                 "yahoo terms unconfirmed; EDGAR's daily 8-K index measures the season"),
    "fear_greed": ("fear_greed", "production.dataviz.cnn.io", functools.partial(
        gdelt_tone, queries=('"stock market"', "recession", "gold price", '"oil price"')),
        "cnn terms unconfirmed; the news-flow tone is the fear/greed reading"),
    "investing": ("investing", "www.investing.com", functools.partial(
        gdelt_news, queries=("forex central bank", "gold price", "oil prices OPEC")),
        "investing.com bans automated systems (Terms 10(c))"),
    "google_trends": ("google_trends", "trends.google.com/trends/explore", functools.partial(
        wiki_attention, articles={"Recession": ("US500", "NAS100"),
                                  "Inflation": ("XAUUSD", "EURUSD"),
                                  "Gold": ("XAUUSD",), "Unemployment": ("US500",),
                                  "Stock_market_crash": ("US500", "NAS100"),
                                  "Federal_Reserve": ("EURUSD", "USDJPY")}),
        "trends.google.com robots disallows /trends/explore?; Wikipedia search attention"),
    "academic": ("academic", "papers.ssrn.com", functools.partial(
        arxiv_papers, queries=("cat:q-fin.TR", "cat:q-fin.ST", "cat:q-fin.PM")),
        "ssrn terms unconfirmed; the arXiv API only"),
    "shipping": ("shipping", "tradingeconomics.com", portwatch_chokepoints,
                 "tradingeconomics terms unconfirmed and investing.com refused; IMF PortWatch"),
    "china": ("china", "so.eastmoney.com", functools.partial(
        gdelt_news, queries=("sourcecountry:CH economy", "sourcecountry:CH yuan",
                             "sourcecountry:CH commodities"))),
    "korea": ("korea", "finance.naver.com", functools.partial(
        gdelt_news, queries=("sourcecountry:KS economy", "sourcecountry:KS won",
                             "sourcecountry:KS semiconductor exports"))),
}
# The two regional channels' reasons (kept short above so the table stays readable).
SUBSTITUTES["china"] = (*SUBSTITUTES["china"][:3],
                        "eastmoney and zhihu terms unconfirmed; GDELT's Chinese-source news")
SUBSTITUTES["korea"] = (*SUBSTITUTES["korea"][:3],
                        "naver and kr.investing terms unconfirmed or refused; GDELT Korean news")


def run_channel(channel: str, get: Getter | None = None, *, write: bool = True,
                pace_s: float | None = None) -> list[dict[str, Any]]:
    """Run one channel's lawful feed and write its seat file. Returns the stamped rows."""
    seat, replaced, fn, why = SUBSTITUTES[channel]
    feed = Feed(get, pace_s=pace_s)
    rows = fn(feed, channel)
    for r in rows:
        r.setdefault("replaces", replaced)
        r.setdefault("substitute_why", why)
    report = {"channel": channel, "rows": len(rows), "refused": feed.refused,
              "errors": feed.errors, "at": _now()}
    print(f"{channel}: {len(rows)} rows via lawful feed"
          + (f"; refused {feed.refused}" if feed.refused else "")
          + (f"; errors {feed.errors}" if feed.errors else ""))
    if not write:
        return rows
    out = INTEL / seat / f"discoveries_{channel}_{datetime.now(UTC):%Y%m%d_%H%M}.json"
    try:
        from side_channels.discovery_io import write_discoveries
    except ModuleNotFoundError:
        from discovery_io import write_discoveries
    stamped = write_discoveries(out, rows)
    (INTEL / seat).mkdir(parents=True, exist_ok=True)
    (INTEL / seat / f"lawful_feed_{channel}.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")
    return stamped


def runner(channel: str) -> Callable[[], list[dict[str, Any]]]:
    """A picklable zero-argument entry for run_all_miners' per-miner process (spawn on Windows)."""
    return functools.partial(run_channel, channel)


if __name__ == "__main__":
    for name in (sys.argv[1:] or list(SUBSTITUTES)):
        run_channel(name)
