"""ALTERNATIVE DATA ROUTES -- when a primary feed is blocked, the fixer switches source, now.

WHY (principal 2026-08-27: "data blocked -> the fixers always immediately find alternative
ecosystem data"). Three families starved on every one of 297 sweep passes today because their
inputs went stale and every producer knew only ONE upstream: FRED for macro, CFTC for COT, one
calendar mirror for events. A single blocked endpoint idled whole families for days while the
staleness read as "quiet ground".

DESIGN. One registry: feed -> ordered routes. A route is a callable returning the feed's rows
or raising; the fixer walks routes in order and the first success wins. Every fetch records
WHICH route served it, because silently switching sources changes data provenance and the desk's
laws require provenance to travel. DBnomics (db.nomics.world) is the standing foreign-ecosystem
mirror: a keyless aggregator of BLS/FRB/OECD/IMF series that keeps serving when FRED throttles.
Stooq (stooq.com, PL) is the market-series alternate. Routes that need packages the box does not
have (AkShare) are declared but report UNAVAILABLE rather than half-importing.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVENANCE = ROOT / "data" / "data_route_provenance.json"
TIMEOUT = 30
UA = {"User-Agent": "Mozilla/5.0 (quant-desk data fixer)"}
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))
from libs.data.refused_hosts import guard  # noqa: E402 -- fail closed: no list, no module


def _get(url: str) -> bytes:
    guard(url)                      # a host whose terms refuse automated contact: never the wire
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


#: DBNOMICS TERMS READING (2026-11-18, read from db.nomics.world/about and
#: docs.db.nomics.world/legal-terms, web-api and faq). Quoted: "Data distributed by DBnomics is
#: subject to the same license and terms of use as its original source provider."; "The DBnomics
#: aggregated datasets are distributed under the Open Database License (ODbL)."; the Web API
#: "can be used by any programming language able to make HTTP requests" and "allows to automate
#: the process"; it is "designed to query focused data ... not to download large datasets", with
#: a cache recommended. No key, no account, no prohibition on automated access was found.
#: Every mapped series below is a BLS or Federal Reserve Board (FED) original, US federal works,
#: never a FRED-provider copy, so FRED's refusal does not travel through the mirror. The API
#: host's robots.txt was NOT read from the cloud (its proxy refused the host), so it is read on
#: every pass before the first request: unread robots are not permission.
DBNOMICS_TERMS = {
    "status": "READ",
    "read_on": "2026-11-18",
    "sources": ["https://db.nomics.world/about", "https://docs.db.nomics.world/legal-terms/",
                "https://docs.db.nomics.world/web-api/", "https://docs.db.nomics.world/faq/"],
    "providers_mapped": ["BLS", "FED"],
    "conditions": ("per-provider licence (BLS/FRB: US federal works); ODbL on aggregates; "
                   "focused queries only, cached"),
}
_ROBOTS: dict[str, object] = {}


def _robots_allows(url: str) -> None:
    """robots.txt for the URL's host, read once per process. 404/410 is an empty file; any other
    non-2xx, an unreadable file or a disallow raises: unread robots are not permission."""
    import urllib.error
    import urllib.parse
    import urllib.robotparser
    parts = urllib.parse.urlsplit(url)
    key = f"{parts.scheme}://{parts.netloc.lower()}"
    if key not in _ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(f"{key}/robots.txt", headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                text = r.read().decode("utf-8", "replace")
            if text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
                _ROBOTS[key] = "robots.txt answered HTML"   # a page parses as allow-all
            else:
                rp.parse(text.splitlines())
                _ROBOTS[key] = rp
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                rp.parse([])
                _ROBOTS[key] = rp
            else:
                _ROBOTS[key] = f"robots.txt answered HTTP {e.code}"
        except Exception as e:  # any failure to read is a refusal
            _ROBOTS[key] = f"robots.txt unreadable ({type(e).__name__})"
    rules = _ROBOTS[key]
    if isinstance(rules, str):
        raise PermissionError(f"{rules}; unread robots are not permission")
    assert isinstance(rules, urllib.robotparser.RobotFileParser)
    if not rules.can_fetch(UA["User-Agent"], url):
        raise PermissionError("robots.txt disallows this path for our agent")


# --------------------------------------------------------------------------- macro series
#: FRED id -> DBnomics (provider, dataset, series) mirror. The ids differ per provider, so the
#: map is explicit -- a wrong guess would splice a DIFFERENT series under a familiar name.
DBNOMICS_MIRROR: dict[str, tuple[str, str, str]] = {
    "UNRATE": ("BLS", "ln", "LNS14000000"),          # U-3 unemployment rate, SA
    "INDPRO": ("FED", "G17_IP_MAJOR_INDUSTRY_GROUPS", "IP.B50001.S"),  # IP total index, SA
    "CPIAUCSL": ("BLS", "cu", "CUSR0000SA0"),        # CPI-U all items, SA
    "FEDFUNDS": ("FED", "H15", "RIFSPFF_N.M"),       # effective federal funds rate, monthly
    # Rates + labour + core inflation axes (2026-08-27: 19 of 22 macro series were failing
    # through the blocked primary, so Growth was the ONLY axis the desk could see -- macro
    # states, differentials and every macro_conditional cell were reading one dimension).
    # Each id below was probed live against DBnomics before being mapped; a wrong mapping
    # would splice a different series under a familiar name, which is worse than a gap.
    "DGS10": ("FED", "H15", "RIFLGFCY10_N.B"),       # 10y treasury constant maturity, daily
    "DGS2": ("FED", "H15", "RIFLGFCY02_N.B"),        # 2y treasury constant maturity, daily
    "DFF": ("FED", "H15", "RIFSPFF_N.D"),            # effective fed funds, daily
    "PAYEMS": ("BLS", "ce", "CES0000000001"),        # total nonfarm payrolls, SA
    "CPILFESL": ("BLS", "cu", "CUSR0000SA0L1E"),     # CPI core (less food & energy), SA
}


def fred_route(series_id: str) -> dict[str, float]:
    """FRED is REFUSED for every automated fetch (terms ruling 2026-11-13; BACKLOG 609). The route
    stays named so provenance can say so, and raises before any request is built."""
    from libs.data.refused_hosts import RefusedSource, refusal
    why = refusal("https://fred.stlouisfed.org/graph/fredgraph.csv") or \
        "FRED: refused for all automated fetches (terms ruling 2026-11-13)"
    raise RefusedSource(f"BLOCKED_ON_TERMS: {why} ({series_id} not fetched)")


def dbnomics_route(series_id: str) -> dict[str, float]:
    """Foreign-ecosystem mirror: DBnomics, keyless JSON."""
    triple = DBNOMICS_MIRROR.get(series_id)
    if triple is None:
        raise LookupError(f"no DBnomics mirror mapped for {series_id}")
    prov, dataset, sid = triple
    _robots_allows("https://api.db.nomics.world/v22/series")
    raw = _get(f"https://api.db.nomics.world/v22/series/{prov}/{dataset}/{sid}"
               f"?observations=1&format=json")
    doc = json.loads(raw)
    series = (doc.get("series") or {}).get("docs") or []
    if not series:
        raise ValueError(f"DBnomics empty for {prov}/{dataset}/{sid}")
    periods = series[0].get("period") or []
    values = series[0].get("value") or []
    # DBnomics encodes gaps as the STRING "NA" (holidays on daily series), not null. float("NA")
    # raises, which failed the whole route and sent the caller to "ALL routes failed" -- one
    # holiday in a decade of treasury yields was enough to starve the axis (2026-08-28).
    out: dict[str, float] = {}
    for per, val in zip(periods, values, strict=False):
        if val is None:
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue                      # "NA"/"" are absent observations, not failures
        if f == f:
            out[str(per)] = f
    if not out:
        raise ValueError(f"DBnomics no usable observations for {series_id}")
    return out


def stooq_route(symbol: str) -> dict[str, float]:
    """Market series alternate (daily closes) from Stooq."""
    raw = _get(f"https://stooq.com/q/d/l/?s={symbol}&i=d")
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))):
        if row.get("Date") and row.get("Close") not in (None, "", "N/D"):
            out[row["Date"]] = float(row["Close"])
    if not out:
        raise ValueError(f"stooq returned no rows for {symbol}")
    return out


#: feed -> ordered (route_name, callable) pairs. First success wins; provenance is recorded.
#: FRED left the route list on 2026-11-18 (terms refusal, BACKLOG 609): the primary publishers'
#: own series, mirrored by DBnomics, are the only macro route.
MACRO_ROUTES: list[tuple[str, Callable[[str], dict[str, float]]]] = [
    ("dbnomics", dbnomics_route),
]


def fetch_macro_series(series_id: str) -> tuple[dict[str, float], str]:
    """Walk the macro routes; return (observations, route_used). Raises only if ALL fail."""
    errors: list[str] = []
    for name, fn in MACRO_ROUTES:
        try:
            data = fn(series_id)
            _record(f"macro:{series_id}", name, ok=True)
            return data, name
        except Exception as exc:
            import urllib.error as _ue
            kind = ("AUTH_FAILED" if isinstance(exc, _ue.HTTPError)
                    and exc.code in (401, 403) else "BLOCKED")
            errors.append(f"{name}: {kind}: {type(exc).__name__}: {exc}")
            # AUTH_FAILED is a KEY problem, not a network problem: rerouting around it forever
            # hides a rotten credential; the health fence reads this marker and pages rotation.
            _record(f"macro:{series_id}", name, ok=False, why=f"{kind}: {str(exc)[:100]}")
    raise RuntimeError(f"ALL routes failed for {series_id} -- " + " | ".join(errors))


def _record(feed: str, route: str, *, ok: bool, why: str = "") -> None:
    try:
        doc = json.loads(PROVENANCE.read_text("utf-8"))
    except (OSError, ValueError):
        doc = {}
    rows = doc.setdefault("feeds", {}).setdefault(feed, [])
    rows.append({"at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
                 "route": route, "ok": ok, **({"why": why} if why else {})})
    doc["feeds"][feed] = rows[-40:]
    PROVENANCE.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE.write_text(json.dumps(doc, indent=1), "utf-8")


if __name__ == "__main__":
    import sys
    for sid in sys.argv[1:] or ["UNRATE"]:
        try:
            data, route = fetch_macro_series(sid)
            last = sorted(data)[-1]
            print(f"{sid}: {len(data)} obs via {route}; last {last} = {data[last]}")
        except RuntimeError as exc:
            print(f"{sid}: {exc}")
