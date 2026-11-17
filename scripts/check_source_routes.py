"""Is each data endpoint still THERE, or has it moved and started lying?

THE FAILURE THIS EXISTS FOR IS IN THIS REPO'S OWN HISTORY. NOAA renamed
`CurrentSummaries.json` to `CurrentStorms.json`. The old path kept answering -- with a 404 page,
as HTML, with HTTP 200 in front of a CDN error document. The miner parsed it, found no storm
records, and reported NO ACTIVE STORMS. Four hurricanes were live at the time.

That is the worst shape a data fault can take, and it is the shape this desk keeps finding in
other clothes: `live: 0` meaning "I could not read the file", a routing decision reported as
thirteen lost candidates, an enrolment census reported as a crash. A moved endpoint does not
report an error. It reports ABSENCE, and absence is indistinguishable from a quiet world.

SO THE PROBE ASKS A DIFFERENT QUESTION than "did it respond". It asks whether what came back is
still the SHAPE the caller expects:

    OK           reachable, and the body parses as the declared type
    MOVED        reachable, HTTP 200, and the body is the WRONG TYPE -- almost always an error
                 page served as HTML where JSON/CSV/XML was declared. This is the NOAA case and
                 the one that must never be read as "no data".
    HTTP_ERROR   an honest non-200. Bad, but at least it is loud.
    UNREACHABLE  DNS, TLS or timeout. The network, not the route.
    UNMEASURED   no probe could be made at all -- reported, never scored as a pass.

NOTHING IS FETCHED FOR CONTENT. This reads the first few KB and looks at the shape. It is a route
check, not an acquisition run, and it must stay cheap enough to run every hour beside everything
else.

WHY THIS IS THE FIRST COMMIT OF ANY DATA PROGRAMME, not a later one. Every source added to this
desk inherits the NOAA failure by default: a government portal renames a path, the fetcher keeps
returning empty, and a family quietly concludes its signal has gone flat. Building acquisition
before this is building on ground that can vanish without saying so.

    python scripts/check_source_routes.py
    python scripts/check_source_routes.py --timeout 20
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "desks" / "mt5" / "reports" / "SOURCE_ROUTES.json"

#: (name, url, expected shape). The shape is what makes a MOVED verdict possible: without a
#: declared expectation, an HTML error page and a real response are both just "bytes".
#:
#: Probes are HEAD-like GETs of a few KB. Endpoints needing a key are declared with `needs_key`
#: so an auth failure is never confused with a route change.
ROUTES: tuple[dict[str, Any], ...] = (
    {"name": "fred_series", "url": "https://api.stlouisfed.org/fred/series/observations",
     "expect": "json", "needs_key": True},
    {"name": "fred_release_dates", "url": "https://api.stlouisfed.org/fred/release/dates",
     "expect": "json", "needs_key": True},
    {"name": "fred_graph_csv",
     "url": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10", "expect": "csv"},
    {"name": "ecb_eurofxref_hist",
     "url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml", "expect": "xml"},
    {"name": "dukascopy_datafeed", "url": "https://datafeed.dukascopy.com/datafeed",
     "expect": "any"},
    {"name": "sge_quotations", "url": "https://www.sge.com.cn/graph/quotations", "expect": "any"},
    {"name": "gld_holdings",
     "url": "https://www.spdrgoldshares.com/usa/assets/uploads/GLD_US_holdings.xlsx",
     "expect": "binary"},
    {"name": "yahoo_chart",
     "url": "https://query1.finance.yahoo.com/v8/finance/chart/GC=F", "expect": "json"},
)

#: Content types that satisfy each declared shape. Deliberately generous -- the check is for a
#: WRONG shape (an error page), not for strict conformance.
_ACCEPT = {
    "json": ("json", "javascript"),
    "csv": ("csv", "text/plain", "octet-stream"),
    "xml": ("xml",),
    "binary": ("octet-stream", "excel", "spreadsheet", "zip"),
    "any": (),
}

#: A body this small from an endpoint that should carry data is empty even if it parses.
MIN_BODY_BYTES = 64


def probe(route: dict[str, Any], timeout: float = 15.0) -> dict[str, Any]:
    """One route, one verdict. Never raises: an unprobed route is UNMEASURED, not a pass."""
    name, url = str(route.get("name")), str(route.get("url"))
    expect = str(route.get("expect") or "any")
    out: dict[str, Any] = {"name": name, "url": url, "expect": expect}
    req = urllib.request.Request(url, headers={"User-Agent": "quant-desk-route-probe/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = int(getattr(r, "status", 0) or 0)
            ctype = str(r.headers.get("Content-Type") or "").lower()
            body = r.read(4096)
    except urllib.error.HTTPError as e:
        # AN HONEST NON-200 IS THE GOOD CASE. It is loud, and nothing downstream can read it as
        # an empty world. 401/403 on a keyed endpoint is auth, not a route change.
        code = int(getattr(e, "code", 0) or 0)
        out.update({"status": "HTTP_ERROR", "http": code,
                    "why": ("authentication, not a route change" if code in (401, 403)
                            and route.get("needs_key") else f"HTTP {code}")})
        return out
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        out.update({"status": "UNREACHABLE", "why": f"{type(e).__name__}: {str(e)[:90]}"})
        return out
    except Exception as e:
        out.update({"status": "UNMEASURED", "why": f"{type(e).__name__}: {str(e)[:90]}"})
        return out

    out["http"] = status
    out["content_type"] = ctype
    out["bytes_read"] = len(body)
    accept = _ACCEPT.get(expect, ())
    looks_html = ("html" in ctype) or body[:200].lstrip().lower().startswith(
        (b"<!doctype html", b"<html"))

    if accept and looks_html:
        # THE NOAA CASE, EXACTLY. HTTP 200, HTML body, a caller expecting structured data. Read
        # as "no records" by any parser that does not check, which is how four live hurricanes
        # became zero.
        out.update({"status": "MOVED",
                    "why": (f"HTTP 200 but the body is HTML where {expect} was declared -- an "
                            f"error or landing page. A parser will read this as NO DATA.")})
        return out
    if accept and not any(a in ctype for a in accept):
        out.update({"status": "MOVED",
                    "why": f"content-type {ctype!r} does not match declared {expect!r}"})
        return out
    if len(body) < MIN_BODY_BYTES:
        out.update({"status": "MOVED",
                    "why": f"only {len(body)} bytes returned: reachable but carrying nothing"})
        return out
    out["status"] = "OK"
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args(argv)

    results = [probe(r, args.timeout) for r in ROUTES]
    census: dict[str, int] = {}
    for r in results:
        census[str(r["status"])] = census.get(str(r["status"]), 0) + 1
    moved = [r for r in results if r["status"] == "MOVED"]

    doc = {
        "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": ("a route that answers 200 with the WRONG SHAPE is MOVED, not empty. The NOAA "
                 "rename served a 404 page as HTML and the miner read it as 'no active storms' "
                 "with four hurricanes live."),
        "n_routes": len(results),
        "census": census,
        "moved": moved,
        "routes": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1), encoding="utf-8")

    print(f"source routes: {len(results)} probed -> {census}")
    for r in results:
        mark = {"OK": "  ok    ", "MOVED": "  MOVED ", "HTTP_ERROR": "  http  ",
                "UNREACHABLE": "  unrch ", "UNMEASURED": "  unmsr "}.get(str(r["status"]), "  ?    ")
        print(f"{mark}{r['name']!s:22} {str(r.get('why') or r.get('content_type') or '')[:70]}")
    print(f"  -> {OUT}")
    # MOVED is the only fatal verdict. An honest HTTP error or an unreachable host is loud and
    # self-announcing; a moved route is the one that silently becomes "no data".
    return 1 if moved else 0


if __name__ == "__main__":
    raise SystemExit(main())
