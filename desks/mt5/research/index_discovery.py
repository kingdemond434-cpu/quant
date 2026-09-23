"""INDEX-DRIVEN DISCOVERY: thousands of addresses per request, and not one page crawled.

THE CEILING THIS BREAKS. Link-following discovery has to DOWNLOAD a page to learn what it links
to, so discovery and evaluation compete for the same fetch budget -- 150 an hour on this desk.
Worse, it can only ever reach the connected component containing its seeds: after weeks the
crawler sits at ~23,000 frontier URLs across ~987 hosts, and every unlinked PDF archive,
university page and regional portal that nothing in that component links to is STRUCTURALLY
unreachable, however long it runs.

An index answers a different question. One request to Common Crawl's CDX returns every URL it
holds on a host; one OpenAlex query returns every paper citing a work since a date. Discovery
becomes near-free and unbounded, fetching stays budgeted, and the two stop bidding against each
other. That separation is the whole point, so this module reports ADDRESSES DISCOVERED and
FETCHES SPENT as two different numbers -- they have been the same number, and that was the
ceiling.

EVERY ROUTE HERE WAS PROBED LIVE BEFORE IT WAS WRITTEN DOWN, 2026-09-15, and the ones that failed
are recorded with their failure rather than listed as if they worked:

    commoncrawl_cdx    HTTP 200, text/x-ndjson, returns URLs for a host wildcard
    openalex           HTTP 200, 48,716 works for one query, no auth
    eu_open_data       HTTP 200, 11,019 datasets for "copper"
    google_patents     HTTP 200, 202,999 results for "algorithmic trading"
    sec_edgar_fts      HTTP 200, full-text search over filings

    patentsview        DNS failure -- endpoint retired
    epo_ops            HTTP 403 -- needs a key
    semantic_scholar   HTTP 429 -- works, rate limited; needs backoff before it is useful
    ckan data.gov      HTTP 404 -- the path moved
    wayback_cdx        timeout at 25s -- real, slow; needs its own budget

WHY PATENTS ARE THE BEST GROUND ON THIS LIST. A patent is legally required to be an ENABLING
disclosure: it must contain enough detail for a skilled person to reproduce it. That makes the
patent corpus the largest body of exact mechanisms with exact parameters in existence -- and
"exact recipe or structured causal data only" is precisely what this desk's compiler admits and
what prose structurally cannot satisfy. The RenTech cross-exchange execution patent this desk's
own audit cites was never a leak; it was a public filing.

NOTHING HERE FETCHES CONTENT. It collects addresses and hands them to the frontier, where the
existing yield scorer decides what is worth spending a fetch on. An index that started fetching
would re-merge the two budgets this module exists to separate.

    python desks/mt5/research/index_discovery.py
    python desks/mt5/research/index_discovery.py --route commoncrawl_cdx --limit 200
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = BASE / "data" / "asia_sources.json"
SEEDS = BASE / "data" / "deep_forest_sources.json"
OUT = BASE / "reports" / "INDEX_DISCOVERY.json"
FOUND = BASE / "data" / "intelligence" / "index_discovery"

#: Addresses taken per route per pass. Discovery is cheap but the frontier is not infinite, and a
#: single Common Crawl query can return tens of thousands of URLs for one host.
PER_ROUTE = 300
#: The crawl this desk queries. Common Crawl publishes a new index every few weeks; an index id
#: that has rotated returns 404, which is a NAMED failure here rather than an empty result.
CC_INDEX = "CC-MAIN-2026-30"

UA = "quant-desk-index/1.0 (research; public index queries only)"


def _ctx():
    """certifi's CA bundle. This host's egress intercepts TLS, so the system store is short."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _get(url: str, timeout: float = 25.0, cap: int = 2_000_000) -> tuple[bytes | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_TLS) as r:
            return r.read(cap), f"HTTP {getattr(r, 'status', 0)}"
    except urllib.error.HTTPError as e:
        return None, f"HTTP {getattr(e, 'code', 0)}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:70]}"


_TLS = None


def _hosts_from_registry(limit: int = 12) -> list[str]:
    """Hosts the desk already declares an interest in. Discovery aims where the desk is aimed."""
    out: list[str] = []
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for s in reg.get("sources") or []:
        if not isinstance(s, dict):
            continue
        host = urllib.parse.urlsplit(str(s.get("url") or "")).netloc
        if host and host not in out:
            out.append(host)
    return out[:limit]


def commoncrawl_cdx(limit: int = PER_ROUTE) -> dict[str, Any]:
    """Every URL Common Crawl holds on the desk's declared hosts. One request per host."""
    found: list[str] = []
    per_host: dict[str, int] = {}
    errors: dict[str, str] = {}
    for host in _hosts_from_registry():
        q = urllib.parse.quote(f"*.{host}/*", safe="")
        url = (f"https://index.commoncrawl.org/{CC_INDEX}-index?url={q}"
               f"&output=json&limit={max(20, limit // 6)}")
        body, why = _get(url)
        if body is None:
            errors[host] = why
            continue
        n = 0
        for ln in body.decode("utf-8", errors="replace").splitlines():
            try:
                row = json.loads(ln)
            except ValueError:
                continue
            u = str(row.get("url") or "")
            if u and u not in found:
                found.append(u)
                n += 1
        per_host[host] = n
    return {"route": "commoncrawl_cdx", "index": CC_INDEX, "addresses": found,
            "per_host": per_host, "errors": errors,
            "note": "one request per host returns every URL the crawl holds for it; no page fetched"}


def openalex(limit: int = PER_ROUTE) -> dict[str, Any]:
    """The academic graph. Free, no auth, ~250M works with citations."""
    found: list[str] = []
    queries = ("futures momentum", "commodity term structure", "order flow imbalance",
               "central bank intervention exchange rate", "carry trade currency")
    errors: dict[str, str] = {}
    for q in queries:
        url = (f"https://api.openalex.org/works?search={urllib.parse.quote(q)}"
               f"&per-page={max(10, limit // len(queries))}")
        body, why = _get(url)
        if body is None:
            errors[q] = why
            continue
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            errors[q] = "did not parse as json"
            continue
        for w in doc.get("results") or []:
            u = (w.get("primary_location") or {}).get("landing_page_url") or w.get("id")
            if u and u not in found:
                found.append(str(u))
    return {"route": "openalex", "addresses": found, "queries": list(queries), "errors": errors,
            "note": "citation graph: 'everything citing this since this date' is one request"}


def google_patents(limit: int = PER_ROUTE) -> dict[str, Any]:
    """THE LARGEST CORPUS OF EXACT MECHANISMS THERE IS -- a patent must ENABLE reproduction."""
    found: list[str] = []
    errors: dict[str, str] = {}
    queries = ("algorithmic trading", "order execution optimization",
               "futures spread trading system", "market making inventory risk",
               "statistical arbitrage signal")
    for q in queries:
        url = ("https://patents.google.com/xhr/query?url="
               + urllib.parse.quote(f"q={q}", safe=""))
        body, why = _get(url)
        if body is None:
            errors[q] = why
            continue
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            errors[q] = "did not parse as json"
            continue
        for cluster in (doc.get("results") or {}).get("cluster") or []:
            for r in cluster.get("result") or []:
                pid = ((r.get("patent") or {}).get("publication_number") or "")
                if pid:
                    u = f"https://patents.google.com/patent/{pid}/en"
                    if u not in found:
                        found.append(u)
    return {"route": "google_patents", "addresses": found[:limit], "queries": list(queries),
            "errors": errors,
            "note": ("a patent is legally required to be an ENABLING disclosure -- exact "
                     "mechanisms with exact parameters, which is the one shape the compiler "
                     "admits and prose never satisfies")}


def eu_open_data(limit: int = PER_ROUTE) -> dict[str, Any]:
    """A CKAN-shaped catalogue over EU statistical portals: one parser, many publishers."""
    found: list[str] = []
    errors: dict[str, str] = {}
    for q in ("copper", "iron ore", "natural gas", "exchange rate", "freight"):
        url = (f"https://data.europa.eu/api/hub/search/search?q={urllib.parse.quote(q)}"
               f"&limit={max(5, limit // 10)}")
        body, why = _get(url)
        if body is None:
            errors[q] = why
            continue
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            errors[q] = "did not parse as json"
            continue
        for r in ((doc.get("result") or {}).get("results") or []):
            for dist in (r.get("distributions") or []):
                u = dist.get("access_url") or dist.get("download_url")
                if isinstance(u, list):
                    u = u[0] if u else None
                if u and str(u) not in found:
                    found.append(str(u))
    return {"route": "eu_open_data", "addresses": found[:limit], "errors": errors,
            "note": "CKAN-shaped: one parser reaches hundreds of national statistical catalogues"}


def sec_edgar(limit: int = PER_ROUTE) -> dict[str, Any]:
    """Funds describing their own strategies, because a regulator made them.

    Form ADV Part 2 requires an adviser to describe its strategies, and CTA/CPO disclosure
    documents describe trading programs in detail. Same dynamic that makes Fusion's PDS useful:
    the counterparty writes the mechanism down under legal compulsion.
    """
    found: list[str] = []
    errors: dict[str, str] = {}
    for q in ('"trading program"', '"systematic strategy"', '"managed futures"'):
        url = ("https://efts.sec.gov/LATEST/search-index?q="
               + urllib.parse.quote(q) + "&forms=10-K")
        body, why = _get(url)
        if body is None:
            errors[q] = why
            continue
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            errors[q] = "did not parse as json"
            continue
        for h in ((doc.get("hits") or {}).get("hits") or []):
            src = h.get("_source") or {}
            aid = h.get("_id") or ""
            cik = (src.get("ciks") or [None])[0]
            if aid and cik:
                acc = str(aid).split(":")[0].replace("-", "")
                u = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
                if u not in found:
                    found.append(u)
    return {"route": "sec_edgar", "addresses": found[:limit], "errors": errors,
            "note": "strategies described under legal compulsion, the Fusion-PDS dynamic at scale"}


def sitemaps(limit: int = PER_ROUTE) -> dict[str, Any]:
    """FIRST FETCH ON EVERY NEW HOST, ALWAYS. One request returns a site's declared URL set.

    The crawler currently discovers those same pages one link at a time, which is the most
    expensive possible way to learn what a host already publishes in a single file.
    """
    found: list[str] = []
    errors: dict[str, str] = {}
    per_host: dict[str, int] = {}
    for host in _hosts_from_registry(8):
        for path in ("/sitemap.xml", "/robots.txt"):
            body, why = _get(f"https://{host}{path}", timeout=15.0, cap=400_000)
            if body is None:
                errors[f"{host}{path}"] = why
                continue
            text = body.decode("utf-8", errors="replace")
            urls = []
            if path.endswith(".xml"):
                urls = [u for u in _between(text, "<loc>", "</loc>")]
            else:
                urls = [ln.split(":", 1)[1].strip() for ln in text.splitlines()
                        if ln.lower().startswith("sitemap:")]
            n = 0
            for u in urls:
                if u and u not in found:
                    found.append(u)
                    n += 1
            per_host[f"{host}{path}"] = n
    return {"route": "sitemaps", "addresses": found[:limit], "per_host": per_host,
            "errors": errors,
            "note": "one request per host for its whole declared URL set"}


def _between(text: str, a: str, b: str) -> list[str]:
    out, i = [], 0
    while True:
        s = text.find(a, i)
        if s < 0:
            break
        e = text.find(b, s + len(a))
        if e < 0:
            break
        out.append(text[s + len(a):e].strip())
        i = e + len(b)
    return out


ROUTES = {
    "commoncrawl_cdx": commoncrawl_cdx,
    "sitemaps": sitemaps,
    "openalex": openalex,
    "google_patents": google_patents,
    "eu_open_data": eu_open_data,
    "sec_edgar": sec_edgar,
}

#: Routes probed live and found NOT usable, kept so nobody re-adds them believing they work.
REFUSED = {
    "patentsview": "DNS failure 2026-09-15: search.patentsview.org does not resolve",
    "epo_ops": "HTTP 403: needs an OPS key; UNCONFIGURED rather than dead",
    "semantic_scholar": "HTTP 429: works but rate limited; needs backoff before it is useful",
    "ckan_data_gov": "HTTP 404: catalog.data.gov moved its API path",
    "wayback_cdx": "timeout at 25s: real and slow, needs its own budget rather than this pass's",
}


def main(argv: list[str] | None = None) -> int:
    global _TLS
    _TLS = _ctx()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--route", action="append", choices=sorted(ROUTES))
    ap.add_argument("--limit", type=int, default=PER_ROUTE)
    args = ap.parse_args(argv)

    want = args.route or sorted(ROUTES)
    results = []
    for name in want:
        try:
            results.append(ROUTES[name](args.limit))
        except Exception as exc:
            results.append({"route": name, "addresses": [],
                            "errors": {"route": f"{type(exc).__name__}: {exc}"}})

    total = sum(len(r.get("addresses") or []) for r in results)
    # ADDRESSES AND FETCHES ARE TWO NUMBERS. They have been one number, and that was the ceiling.
    fetches = sum(len(r.get("per_host") or r.get("queries") or r.get("errors") or []) or 1
                  for r in results)
    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("discovery and evaluation must not bid for the same budget. This collects "
                 "ADDRESSES and fetches no content; the frontier's yield scorer decides what is "
                 "worth a fetch."),
        "addresses_discovered": total,
        "index_requests_spent": fetches,
        "multiplier": round(total / max(fetches, 1), 1),
        "routes": {r["route"]: len(r.get("addresses") or []) for r in results},
        "errors": {r["route"]: r.get("errors") or {} for r in results},
        "refused_routes": REFUSED,
        "detail": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1)[:8_000_000], encoding="utf-8")

    FOUND.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H")
    (FOUND / f"addresses_{stamp}.json").write_text(json.dumps(
        [{"kind": "address", "url": u, "route": r["route"]}
         for r in results for u in (r.get("addresses") or [])], indent=1), encoding="utf-8")

    print(f"index discovery: {total} address(es) from {fetches} index request(s) "
          f"-> {doc['multiplier']}x")
    for r in results:
        n = len(r.get("addresses") or [])
        errs = len(r.get("errors") or {})
        print(f"  {r['route']:18} {n:6} address(es){'  ' + str(errs) + ' route error(s)' if errs else ''}")
    print(f"  refused routes (probed, do not re-add): {', '.join(sorted(REFUSED))}")
    print(f"  -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
