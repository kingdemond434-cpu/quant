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


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


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
    """Primary: keyless fredgraph CSV."""
    raw = _get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")
    out: dict[str, float] = {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8", "replace"))):
        val = row.get(series_id) or row.get("VALUE") or ""
        date = row.get("DATE") or row.get("observation_date") or ""
        if date and val not in ("", "."):
            out[date] = float(val)
    if not out:
        raise ValueError(f"fredgraph returned no rows for {series_id}")
    return out


def dbnomics_route(series_id: str) -> dict[str, float]:
    """Foreign-ecosystem mirror: DBnomics, keyless JSON."""
    triple = DBNOMICS_MIRROR.get(series_id)
    if triple is None:
        raise LookupError(f"no DBnomics mirror mapped for {series_id}")
    prov, dataset, sid = triple
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
MACRO_ROUTES: list[tuple[str, Callable[[str], dict[str, float]]]] = [
    ("fred", fred_route),
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
