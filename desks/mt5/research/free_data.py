"""FREE_DATA: keyless public-data collectors (no API keys, no paid feeds).

Sources (all lawful, public, first-party):
  - FRED / ALFRED fredgraph.csv (rates, policy, macro, gold, oil, DXY, VIX)
    vintage_date param => point-in-time history (no API key needed)
  - Yahoo Finance: CUT AS LIVE INPUT (2026-10-14). Yahoo is an IDEAS_ONLY row of
    libs/data/terms_fence.SOURCE_POLICY (its Terms 2.d.9 bar automated collection), so
    `yahoo_daily` asks THE ONE FETCH DOOR with live_input=True and is refused before any request.
    Each series it served is re-sourced by `licensed_daily` (FRED public-domain series, EIA, the
    desk's own MT5 bars) or reported UNMEASURED_NO_LICENSED_SOURCE with a missed_growth line.
  - Official government RSS feeds (Fed, BLS, ...; parsed with stdlib)
  - GitHub search + Reddit public JSON + Wikipedia pageviews (crowding/adoption proxies; no
    key). Reddit is IDEAS_ONLY in the per-source policy (libs/data/terms_fence.py, ruling of
    2026-10-13): read politely as a research proxy, never as a cell's live input data.

Every collector is isolated: one failing source never blocks the others.
Network timeouts are short; results are cached to data/free_data_cache/.
"""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
try:
    from libs.data.polite_fetch import DESK_UA
except ImportError:  # run as a script: the repo root is not on the path
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[3]))
    from libs.data.polite_fetch import DESK_UA

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "data" / "free_data_cache"
CACHE.mkdir(parents=True, exist_ok=True)

UA = DESK_UA


def _terms_fence():
    """libs.data.terms_fence, importable from a desk-rooted process too."""
    import sys as _sys
    _root = str(Path(__file__).resolve().parents[3])
    if _root not in _sys.path:
        _sys.path.insert(0, _root)
    from libs.data import terms_fence
    return terms_fence


def _get(url: str, timeout: int = 25, headers: dict | None = None, *,
         live_input: bool = True) -> bytes:
    # THE METHOD FENCE (libs/data/terms_fence.py): raises TermsFenced for a HELD source
    # (METHOD_BLOCKED, or NEEDS_KEY until its key exists) before any request is built.
    tf = _terms_fence()
    tf.check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    # A 30x into a held source or a login wall raises TermsFenced instead of being followed.
    # LIVE INPUT (macro_desk, news_desk): every redirect hop is re-checked against the live-input
    # rule too (`input_source`), so a 30x into an IDEAS_ONLY or held route is refused (pass-6
    # audit cf305e3d2 SHOULD-FIX 1). A caller whose FIRST URL is an IDEAS_ONLY row passes
    # live_input=False: its hops are still re-checked (`live_hops`), its first URL is unchanged.
    with tf.guarded_urlopen(req, timeout=timeout, live_input=live_input,
                            live_hops=True) as r:
        return r.read()


def _cache_file(name: str) -> Path:
    return CACHE / f"{name.replace('/', '_').replace('?', '_')}.json"


def _cache_get(name: str):
    p = _cache_file(name)
    if p.exists() and (time.time() - p.stat().st_mtime) < 21600:
        try:
            return json.loads(p.read_text("utf-8"))
        except Exception:
            pass
    return None


def _cache_put(name: str, obj) -> None:
    try:
        _cache_file(name).write_text(json.dumps(obj), "utf-8")
    except Exception as exc:
        # LOUD, NOT SILENT (2026-09-23 swallowed-write audit). A cache that silently never writes
        # re-fetches every call forever and looks exactly like a cache that is working.
        print(f"free_data: cache {name!r} NOT written ({type(exc).__name__}: {exc})", flush=True)


# ----------------------------------------------------------------- FRED ----
FRED_FIELDS = {"DGS2", "DGS10", "T10Y2Y", "DFEDTARU", "DFF", "SOFR", "RRPONTSYD",
               "WALCL", "T10YIE", "T5YIE", "PAYEMS", "UNRATE", "INDPRO",
               "CPIAUCSL", "CPILFESL", "RETAILSMxSA", "UMCSENT", "VIXCLS",
               "GOLDAMGBD228NLBM", "DCOILWTICO", "DTWEXBGS", "DTWEXM",
               "CP0000EZ19M086NEST", "JPNCPIALLMINMEI", "BAMLH0A0HYM2",
               "DEXJPUS", "DEXUSEU", "DEXCAUS", "DEXUSUK", "DEXCHUS"}


def fred_series(series_id: str, start: str = "2010-01-01",
                vintage: str | None = None, *, alternate: bool = True) -> dict[str, float] | None:
    """Fetch a FRED series as {iso_date: value}. Keyless via fredgraph.csv.
    vintage_date => ALFRED point-in-time view of that series. `alternate=False` refuses the
    DBnomics mirror: a licensed substitute is read from the row whose terms were read, never a
    mirror whose own terms were not.

    A series owned by a third party (terms_fence `fred_copyrighted`: its FRED notes carry a
    copyright notice) is REFUSED AS LIVE INPUT before any URL is built: no request, no cache
    read, no mirror. The caller sees None and records `fred_cut_line` (UNMEASURED, never zero)."""
    if _terms_fence().fred_series_source(series_id):
        return None
    base = "https://alfred.stlouisfed.org/graph/fredgraph.csv" if vintage \
        else "https://fred.stlouisfed.org/graph/fredgraph.csv"
    q = {"id": series_id, "cosd": start}
    if vintage:
        q["vintage_date"] = vintage
    url = base + "?" + urllib.parse.urlencode(q)
    key = f"fred_{series_id}_{vintage or 'cur'}"
    hit = _cache_get(key)
    if hit:
        return hit
    try:
        raw = _get(url).decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(raw)))
        out: dict[str, float] = {}
        for row in rows[1:]:
            if len(row) < 2 or row[0].startswith("."):
                continue
            v = row[1].strip()
            if v and v != ".":
                try:
                    out[row[0]] = float(v)
                except ValueError:
                    pass
        if len(out) > 30:
            _cache_put(key, out)
            return out
        return _fred_alternate(series_id, vintage, key) if alternate else None
    except Exception:
        # A BLOCKED PRIMARY MUST NOT STARVE THE FAMILY (2026-08-27: FRED timed out for days,
        # macro_state went 5 days stale, and macro_conditional produced zero signals on 297
        # straight sweep passes while the staleness read as quiet ground). The alternate route
        # registry (scripts/data_alternates) serves the same series from the DBnomics mirror,
        # with provenance recorded -- a switched source is a fact, never a silent substitution.
        return _fred_alternate(series_id, vintage, key) if alternate else None


def _fred_alternate(series_id: str, vintage: str | None, cache_key: str):
    if vintage:
        return None          # point-in-time vintages exist only at ALFRED; never fake one
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[3] / "scripts")
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from data_alternates import dbnomics_route
        out = dbnomics_route(series_id)
        if len(out) > 30:
            _cache_put(cache_key, out)
            print(f"free_data: {series_id} served by DBNOMICS mirror (primary blocked)")
            return out
    except Exception:
        pass
    return None


def fred_vintage_series(series_id: str, vintage_dates: list[str],
                        start: str = "2010-01-01") -> dict[str, dict[str, float]]:
    """Point-in-time lake: {vintage_date: {date: value}} as of each vintage."""
    out: dict[str, dict[str, float]] = {}
    for vd in vintage_dates:
        s = fred_series(series_id, start=start, vintage=vd)
        if s:
            out[vd] = s
    return out


# ---------------------------------------------------------------- YAHOO ----
YAHOO_TICKERS = {"DX-Y.NYB": "DXY", "^VIX": "VIX", "^TNX": "TNX", "^GSPC": "SPX",
                 "GC=F": "GC", "CL=F": "CL", "^N225": "NKY", "EURUSD=X": "EURUSD",
                 "USDJPY=X": "USDJPY", "GBPUSD=X": "GBPUSD", "AUDUSD=X": "AUDUSD",
                 "USDCAD=X": "USDCAD", "NZDUSD=X": "NZDUSD", "USDCHF=X": "USDCHF"}

#: The status a series carries when Yahoo was its only reader and no licensed source exists. It
#: is never filled, never forward-filled and never zero: the column is absent and the line says so.
UNMEASURED_NO_LICENSED_SOURCE = "UNMEASURED_NO_LICENSED_SOURCE"


def yahoo_daily(ticker: str) -> dict[str, float] | None:
    """REFUSED AS LIVE INPUT (2026-10-14). Yahoo is an IDEAS_ONLY row, so this asks THE ONE FETCH
    DOOR with `live_input=True`, which refuses the URL before any request is built, and returns
    None. The cache is NOT read: a cached Yahoo series is the same Yahoo series. Live organs call
    `licensed_daily` instead; this stays so a stale caller fails closed rather than crashing."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/" +
           urllib.parse.quote(ticker) + "?range=10y&interval=1d")
    try:
        _get(url, timeout=20, live_input=True)
    except Exception:
        return None
    return None                                   # unreachable while the row is IDEAS_ONLY


#: EVERY SERIES A LIVE ORGAN READ FROM YAHOO, AND WHAT STANDS IN FOR IT. `route` is the licensed
#: row (terms_fence.SOURCE_POLICY) the substitute is read from; None means no licensed source
#: exists and the series is UNMEASURED_NO_LICENSED_SOURCE. `pit_source` names the data_os lag the
#: substitute is admissible under (late-biased: a daily MT5 close is read under the anchors' own
#: 27h `cross_asset_anchors` lag, not the H1 bar's 1h); `pit_lag_h` overrides it where the
#: publisher's calendar is slower than any declared lag (H.10 is weekly).
YAHOO_SUBSTITUTES: dict[str, dict[str, Any]] = {
    "DX-Y.NYB": {"name": "DXY", "route": "mt5_own_bars", "series": "USDX",
                 "pit_source": "cross_asset_anchors",
                 "note": "Fusion's own dollar-index CFD (ICE basket); level tracks DXY"},
    "^VIX": {"name": "VIX", "route": None, "series": None,
             "why": ("Cboe index values are a held route (cboe_delayed_index_values: s.2 bars "
                     "storage and derived use) and FRED's VIXCLS carries Cboe's copyright, "
                     "which FRED cannot license; no MT5 VIX CFD is on this account")},
    "^TNX": {"name": "TNX", "route": "fred_public_domain", "series": "DGS10",
             "pit_source": "fred_macro",
             "note": "H.15 10y constant-maturity yield in percent (^TNX quotes the same yield)"},
    "^IRX": {"name": "IRX", "route": "fred_public_domain", "series": "DTB3",
             "pit_source": "fred_macro",
             "note": "H.15 3-month T-bill secondary-market rate (scripts/hurdle_rate.py)"},
    "^GSPC": {"name": "SPX", "route": "mt5_own_bars", "series": "US500",
              "pit_source": "cross_asset_anchors", "note": "Fusion US500 CFD daily close"},
    "GC=F": {"name": "GC", "route": "mt5_own_bars", "series": "XAUUSD",
             "pit_source": "cross_asset_anchors",
             "note": "spot XAUUSD, not the COMEX front month: the futures basis is not carried"},
    "CL=F": {"name": "CL", "route": "mt5_own_bars", "series": "XTIUSD",
             "pit_source": "cross_asset_anchors",
             "note": "Fusion WTI CFD; EIA/FRED DCOILWTICO (Cushing spot) stays its own column"},
    "^N225": {"name": "NKY", "route": "mt5_own_bars", "series": "JPN225",
              "pit_source": "cross_asset_anchors", "note": "Fusion JPN225 CFD daily close"},
    **{f"{p}=X": {"name": p, "route": "fred_public_domain", "series": sid,
                  "pit_source": None, "pit_lag_h": 8 * 24.0,
                  "pit_basis": ("assumed, conservative: H.10 daily rates are released weekly "
                                "(Monday, for the prior week), so a day's rate can be ~8 days old "
                                "when first public; fred_macro's 27h does not hold for H.10"),
                  "note": "Federal Reserve H.10 noon buying rate (New York), same orientation"}
       for p, sid in (("EURUSD", "DEXUSEU"), ("USDJPY", "DEXJPUS"), ("GBPUSD", "DEXUSUK"),
                      ("AUDUSD", "DEXUSAL"), ("USDCAD", "DEXCAUS"), ("NZDUSD", "DEXUSNZ"),
                      ("USDCHF", "DEXSZUS"))},
}

#: The desk's own bar lake, in preference order of resolution (the same order
#: exposure_decomposition.load_bars reads).
UNIVERSE_DIR = BASE / "data" / "universe"
_BAR_TFS = ("H1", "D1", "H4", "M15")


def mt5_daily(symbol: str, universe_dir: Path | None = None) -> dict[str, float] | None:
    """Daily last close {broker_date: close} from the desk's own MT5 parquets, or None when this
    host holds no bars for `symbol`. The index is broker time under a UTC tzinfo, so a date is the
    broker's trading day; its close is known at the day's end (data_os `mt5_h1_universe`)."""
    root = universe_dir or UNIVERSE_DIR
    for tf in _BAR_TFS:
        path = root / f"{symbol}_{tf}.parquet"
        if not path.exists():
            continue
        try:
            import pandas as pd
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if "close" not in frame.columns:
            continue
        idx = frame.index
        if not isinstance(idx, pd.DatetimeIndex):
            col = next((c for c in ("time", "date", "timestamp") if c in frame.columns), None)
            if col is None:
                continue
            idx = pd.DatetimeIndex(pd.to_datetime(frame[col], utc=True, errors="coerce"))
        close = pd.Series(pd.to_numeric(frame["close"], errors="coerce").to_numpy(), index=idx)
        close = close[close > 0].dropna()
        if close.empty:
            continue
        daily = close.groupby(close.index.date).last()
        out = {str(d): float(v) for d, v in daily.items()}
        if len(out) > 3:
            return out
    return None


def _pit_lag_h(source: str | None) -> float | None:
    """The declared publication lag (hours) of a substitute's data_os source, or None."""
    if not source:
        return None
    try:
        import sys as _sys
        _root = str(Path(__file__).resolve().parents[3])
        if _root not in _sys.path:
            _sys.path.insert(0, _root)
        from libs.tiers import data_os
        return round(data_os.lag_of(source).total_seconds() / 3600.0, 2)
    except Exception:
        return None


def yahoo_cut_line(ticker: str, consumer: str, *, status: str,
                   past: dict | None = None) -> dict[str, Any]:
    """The missed-growth line a cut Yahoo input carries (terms_fence.held_missed_growth, kind
    ideas_only_refusal): delta E[log W] UNMEASURED, never zero, with the substitute or the
    UNMEASURED_NO_LICENSED_SOURCE status beside it."""
    sub = YAHOO_SUBSTITUTES.get(ticker) or {}
    line = _terms_fence().held_missed_growth(
        "yahoo", past, source=f"{consumer}:{sub.get('name') or ticker}", live_input_refusal=True)
    line.update({"yahoo_symbol": ticker, "series_status": status,
                 "substitute": (f"{sub['route']}:{sub['series']}" if sub.get("route") else None)})
    if status == UNMEASURED_NO_LICENSED_SOURCE:
        line["why_unsubstituted"] = str(sub.get("why") or "no licensed source is registered")
    return line


def licensed_daily(ticker: str, consumer: str = "free_data", *,
                   universe_dir: Path | None = None,
                   fred: Any = None, mt5: Any = None) -> tuple[dict[str, float] | None,
                                                               dict[str, Any]]:
    """(series, provenance) for a series a live organ used to read from Yahoo.

    The substitute comes from its licensed row only (no mirror, no Yahoo cache, no fill). An
    unknown ticker, a series with no licensed source, or a substitute this host cannot read is
    (None, provenance) with its status and its missed-growth line: UNMEASURED is never zero.
    `fred` / `mt5` are injectable readers for tests."""
    sub = YAHOO_SUBSTITUTES.get(ticker)
    if not sub or not sub.get("route"):
        prov = {"yahoo_symbol": ticker, "status": UNMEASURED_NO_LICENSED_SOURCE,
                "substitute": None, "pit_lag_h": None}
        prov["missed_growth"] = yahoo_cut_line(ticker, consumer,
                                               status=UNMEASURED_NO_LICENSED_SOURCE)
        return None, prov
    route, sid = str(sub["route"]), str(sub["series"])
    prov = {"yahoo_symbol": ticker, "substitute": f"{route}:{sid}", "route": route,
            "terms_url": str((_terms_fence().SOURCE_POLICY[route].get("terms") or {})
                             .get("url") or ""),
            "pit_source": sub.get("pit_source"),
            "pit_lag_h": (sub["pit_lag_h"] if sub.get("pit_lag_h") is not None
                          else _pit_lag_h(sub.get("pit_source"))),
            "note": sub.get("note", "")}
    if sub.get("pit_basis"):
        prov["pit_basis"] = sub["pit_basis"]
    try:
        if route == "mt5_own_bars":
            got = mt5_daily(sid, universe_dir) if mt5 is None else mt5(sid)
        else:
            got = (fred or (lambda x: fred_series(x, alternate=False)))(sid)
    except Exception:
        got = None
    if got:
        prov["status"] = "SUBSTITUTED"
        prov["n_obs"] = len(got)
        prov["first"], prov["last"] = min(got), max(got)
        # the cut itself still carries its line: Yahoo's own series is no longer read
        prov["missed_growth"] = yahoo_cut_line(ticker, consumer, status="SUBSTITUTED")
        return dict(got), prov
    prov["status"] = ("UNMEASURED_NO_BARS_ON_HOST" if route == "mt5_own_bars"
                      else "UNMEASURED_SUBSTITUTE_UNREACHABLE")
    prov["missed_growth"] = yahoo_cut_line(ticker, consumer, status=prov["status"])
    return None, prov


#: THE FRED SERIES THIRD PARTIES OWN (terms_fence `fred_copyrighted`) and what stands in for each
#: as live input. `route` None: no licensed source exists -> UNMEASURED_NO_LICENSED_SOURCE. The
#: gold fix's stand-in is the desk's own XAUUSD, carried under its OWN name (the anchors' `GC`
#: column, `GOLD_USD_MT5` in macro_state) -- never stored under the fix's id.
FRED_COPYRIGHTED_SUBSTITUTES: dict[str, dict[str, Any]] = {
    "VIXCLS": {"route": None, "series": None,
               "why": ("Cboe owns VIX (FRED notes: 'Copyright, 2016, Chicago Board Options "
                       "Exchange'); Cboe's own index-value route is held; no MT5 volatility-index "
                       "CFD is in the universe registry. A realised-vol proxy from own bars is "
                       "published under its OWN name (anchors `US500_RV21`), never as VIX")},
    "BAMLH0A0HYM2": {"route": None, "series": None,
                     "why": ("ICE Data Indices owns the ICE BofA HY OAS ('Reproduction of this "
                             "data in any form is prohibited except with the prior written "
                             "permission of ICE Data Indices'); no licensed credit-spread series "
                             "is registered")},
    "UMCSENT": {"route": None, "series": None,
                "why": ("University of Michigan owns the sentiment index (FRED notes: 'Copyright, "
                        "2016, Surveys of Consumers'); no licensed substitute is registered")},
    "GOLDAMGBD228NLBM": {"route": "mt5_own_bars", "series": "XAUUSD",
                         "note": ("spot XAUUSD daily close from the desk's own bars, not the LBMA "
                                  "AM fix: carried as anchors `GC` / macro_state `GOLD_USD_MT5`")},
}


def fred_cut_line(series_id: str, consumer: str, *, status: str,
                  past: dict | None = None) -> dict[str, Any]:
    """The missed-growth line a refused third-party FRED series carries (kind
    ideas_only_refusal, policy row `fred_copyrighted`): delta E[log W] UNMEASURED, never zero."""
    sub = FRED_COPYRIGHTED_SUBSTITUTES.get(series_id) or {}
    line = _terms_fence().held_missed_growth(
        "fred_copyrighted", past, source=f"{consumer}:{series_id}", live_input_refusal=True)
    line.update({"fred_series": series_id, "series_status": status,
                 "substitute": (f"{sub['route']}:{sub['series']}" if sub.get("route") else None),
                 "fred_notes": _terms_fence().FRED_COPYRIGHTED_NOTES.get(series_id, "")})
    if status == UNMEASURED_NO_LICENSED_SOURCE:
        line["why_unsubstituted"] = str(sub.get("why") or "no licensed source is registered")
    return line


def fred_refusal(series_id: str, consumer: str, *, substituted: bool = False
                 ) -> dict[str, Any] | None:
    """None for a series FRED may serve as live input; else its provenance row: status
    (SUBSTITUTED when the caller carries the licensed stand-in, else
    UNMEASURED_NO_LICENSED_SOURCE), the policy row, and its missed-growth line."""
    if not _terms_fence().fred_series_source(series_id):
        return None
    sub = FRED_COPYRIGHTED_SUBSTITUTES.get(series_id) or {}
    st = "SUBSTITUTED" if (substituted and sub.get("route")) else UNMEASURED_NO_LICENSED_SOURCE
    return {"fred_series": series_id, "status": st, "policy_row": "fred_copyrighted",
            "substitute": (f"{sub['route']}:{sub['series']}" if sub.get("route") else None),
            "missed_growth": fred_cut_line(series_id, consumer, status=st)}


# ------------------------------------------------------------------ RSS ----
RSS_FEEDS = {
    "FED": "https://www.federalreserve.gov/feeds/press_all.xml",
    "BLS": "https://www.bls.gov/feed/news_release_all.xml",
    "ECB": "https://www.ecb.europa.eu/rss/press.html",
    "BOJ": "https://www.boj.or.jp/en/announcements/rss.rdf",
    "BOE": "https://www.bankofengland.co.uk/rss/news",
    "SNB": "https://www.snb.ch/en/node/10532/rss",
}


def rss_fetch(url: str) -> list[dict]:
    """Parse an RSS/Atom feed into [{title, link, pub, guid}]. Stdlib only."""
    out: list[dict] = []
    try:
        raw = _get(url, timeout=15)
        root = ET.fromstring(raw)
        for item in root.iter():
            tag = item.tag.rsplit("}", 1)[-1]
            if tag in ("item", "entry"):
                d: dict[str, str] = {}
                for child in item:
                    t = child.tag.rsplit("}", 1)[-1]
                    if t in ("title", "link", "pubDate", "published", "updated", "guid", "id"):
                        d[t] = (child.text or "").strip()
                if d.get("title") or d.get("link"):
                    out.append(d)
    except Exception:
        pass
    return out


# -------------------------------------------------------- CROWDING (free) --
GITHUB_QUERIES = [
    "quant trading strategy", "trading bot forex", "gold trading algorithm",
    "mean reversion forex", "breakout trading", "xauusd strategy",
]


def github_search(query: str) -> dict:
    """Unauthenticated GitHub search (rate-limited ~10/min; call sparingly)."""
    url = ("https://api.github.com/search/repositories?q=" +
           urllib.parse.quote(query) + "&sort=stars&order=desc&per_page=5")
    try:
        data = json.loads(_get(url, headers={"Accept": "application/vnd.github+json"}))
        repos = data.get("items", [])
        return {"count": data.get("total_count", 0),
                "top_stars": [r.get("stargazers_count", 0) for r in repos[:5]],
                "top_names": [r.get("full_name", "") for r in repos[:5]]}
    except Exception:
        return {}


def reddit_hot(subreddit: str = "algotrading", limit: int = 25) -> list[dict]:
    """The public hot listing of one subreddit (crowding_miner's retail-adoption proxy).

    Reddit is IDEAS_ONLY in the per-source policy (libs/data/terms_fence.py; the 2026-10-13
    ruling retired the 2026-09-30 category fence): a public page read politely, one request per
    cycle, never a cell's live input data. [] on any failure."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        data = json.loads(_get(url, headers={"User-Agent": "research-crowding/1.0"},
                               live_input=False))     # IDEAS_ONLY (see above): hops re-checked
        posts = []
        for c in data.get("data", {}).get("children", []):
            p = c.get("data", {})
            posts.append({"title": p.get("title", ""), "score": p.get("score", 0),
                          "num_comments": p.get("num_comments", 0),
                          "created_utc": p.get("created_utc", 0)})
        return posts
    except Exception:
        return []


#: Wikipedia articles that stand for "retail attention to systematic trading" -- the information
#: class r/algotrading hot proxies for crowding_miner, from a second source. English edition, user agents only.
ATTENTION_ARTICLES = ("Algorithmic_trading", "Day_trading", "Foreign_exchange_market",
                      "Technical_analysis", "Retail_forex")


def wiki_pageviews(article: str, project: str = "en.wikipedia", days: int = 60,
                   end: datetime | None = None) -> list[tuple[str, int]]:
    """Daily user pageviews for one article from the Wikimedia REST API (keyless; the Wikimedia
    pageview data is CC0). Returns [(YYYYMMDD, views)] oldest first, or [] on any failure."""
    from datetime import timedelta
    e = (end or datetime.now(UTC)) - timedelta(days=1)
    b = e - timedelta(days=max(1, days) - 1)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           f"{project}/all-access/user/{urllib.parse.quote(article, safe='')}/daily/"
           f"{b:%Y%m%d}/{e:%Y%m%d}")
    try:
        data = json.loads(_get(url, headers={
            "User-Agent": "quant-research-desk/1.0 (attention research; keyless REST client)"}))
    except Exception:
        return []
    out = []
    for it in data.get("items", []) or []:
        ts = str(it.get("timestamp") or "")[:8]
        if ts:
            out.append((ts, int(it.get("views") or 0)))
    return sorted(out)


def attention_proxy(articles: tuple[str, ...] = ATTENTION_ARTICLES) -> dict:
    """Retail attention to systematic trading, from Wikipedia pageviews: the lawful substitute for
    and complement to the r/algotrading hot listing. `latest_views` is the sum of the last full day, `z_7d` the
    last seven days against the prior fifty-three. UNMEASURED (never 0) when nothing answered."""
    per: dict[str, list[tuple[str, int]]] = {a: wiki_pageviews(a) for a in articles}
    got = {a: v for a, v in per.items() if v}
    if not got:
        return {"status": "UNMEASURED", "why": "no Wikimedia pageview series answered",
                "source": "wikipedia_pageviews", "articles": list(articles)}
    days: dict[str, int] = {}
    for rows in got.values():
        for d, v in rows:
            days[d] = days.get(d, 0) + v
    series = [days[d] for d in sorted(days)]
    recent, base = series[-7:], series[:-7]
    z = None
    if len(base) >= 14:
        mu = sum(base) / len(base)
        sd = (sum((x - mu) ** 2 for x in base) / len(base)) ** 0.5
        z = round(((sum(recent) / len(recent)) - mu) / sd, 3) if sd > 0 else None
    return {"status": "MEASURED", "source": "wikipedia_pageviews",
            "articles": sorted(got), "articles_missing": sorted(set(articles) - set(got)),
            "latest_day": sorted(days)[-1], "latest_views": series[-1],
            "mean_7d": round(sum(recent) / len(recent), 1), "z_7d": z, "n_days": len(series)}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
