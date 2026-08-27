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
    out = {str(p): float(v) for p, v in zip(periods, values, strict=False)
           if v is not None and v == v}
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
        except Exception as exc:  # noqa: BLE001 -- each route's failure feeds the next
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            _record(f"macro:{series_id}", name, ok=False, why=str(exc)[:120])
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
