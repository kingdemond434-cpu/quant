#!/usr/bin/env python3
"""US TREASURY AUCTION RESULTS as a point-in-time series (B13, approved 2026-10-13).

    python desks/mt5/research/ust_auction_results.py --once
    python desks/mt5/research/ust_auction_results.py --once --no-fetch   # rebuild, no network

WHAT IT ADDS. `forced_flow_calendar` already carries the refunding auctions' DATES as the
`bond_auction` kind (a pattern, for the primary dealer's forced bid into the window). What it
cannot carry is the RESULT: whether the auction cleared weak or strong. This organ fetches the
results from the US Treasury's own public API and publishes them where the existing
`exogenous_conditioner` family reads a series (`data/lake/series/<id>.csv`), so a result conditions
next-day US index CFDs and USD pairs without a new family and without a second judge lane. The
cells themselves are minted by `research/specialist_cell.py` (mechanism `ust_auction_result`) and
reach the judge through its one proposer door.

THE SOURCE. FiscalData "Treasury Securities Auctions Data" (`v1/accounting/od/auctions_query`),
https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/ -- a keyless public API
of the US Treasury; US federal data, public domain, machine use is the API's stated purpose. Every
request goes through the robots gate of `research/index_discovery` (a Disallow, or robots that
cannot be read, stops the fetch) with this module's own honest User-Agent.

WHAT "TAIL" MEANS HERE, said plainly because it is not the trade-press number. The press tail is
the high yield minus the WHEN-ISSUED yield at the 1pm bidding deadline. The when-issued yield is
dealer-market data and is NOT in the Treasury's public results, so it is not available to this
desk. The closest field the public data has is the auction's own dispersion: `tail_bp` is
`high_yield - avg_med_yield` (the stop-out yield minus the median accepted yield), in basis points
-- how far up the bid stack the auction had to reach to fill. It is labelled `tail_kind:
high_minus_median` in the artifact, never called the when-issued tail.

`btc_surprise` is the bid-to-cover ratio minus the mean of the previous `BTC_TRAIL` auctions of
the SAME security term (2-year against 2-years, never against bonds, whose ratios sit lower), using
only auctions that closed strictly before it. Fewer than `BTC_MIN_PRIOR` earlier same-term
auctions: the surprise is UNMEASURED (left empty), never a zero.

POINT IN TIME. Results are published minutes after the competitive bidding closes. `available_time`
is the auction date at the competitive close (`closing_time_comp`, New York wall clock, via
zoneinfo) PLUS `PUBLISH_PAD_MIN`; a row whose close time is absent is stamped 17:00 New York, a
rule that can only be late. The family adds its own `lag_hours` on top before any bar sees it.
Coupon securities only (Notes and Bonds; TIPS and FRNs excluded: their yields are real or a
spread, not comparable).

UNMEASURED IS AN ANSWER. No fetch on this host, a refused robots file, a missing field: each is
named in `reports/UST_AUCTION_RESULTS.json`, and the series keeps whatever it last held.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent.parent          # desks/mt5
ROOT = BASE.parent.parent
for _p in (str(BASE), str(BASE / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE_ID = "ust_auction_results"
API = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/"
       "auctions_query")
DATASET_PAGE = "https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/"
UA = "quant-desk-research/1.0 (public US Treasury auction results; keyless API; low rate)"
SERIES = BASE / "data" / "lake" / "series" / f"{SOURCE_ID}.csv"
RAW = BASE / "data" / "lake" / "raw" / SOURCE_ID / "auctions.json"
OUT = BASE / "reports" / "UST_AUCTION_RESULTS.json"
UNMEASURED = "UNMEASURED"

BACKFILL_FROM = date(2012, 1, 1)
#: A fetch at most this often; the leg is hourly, coupon auctions are a few a week.
REFRESH_HOURS = 6.0
#: Re-read this far back on each refresh, so a late-posted row is caught.
OVERLAP_DAYS = 21
PAGE_SIZE = 500
MAX_PAGES = 20
PUBLISH_PAD_MIN = 30
FALLBACK_CLOSE = (17, 0)
NY = "America/New_York"
BTC_TRAIL = 6
BTC_MIN_PRIOR = 3
COUPON_TYPES = ("Note", "Bond")
#: The signal columns the series publishes (everything else on a row is identity or stamp).
SIGNALS = ("tail_bp", "btc_surprise", "bid_to_cover")


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ------------------------------------------------------------------------------ the fetch ---
def _gated_get(url: str, timeout: float = 30.0) -> tuple[bytes | None, str]:
    """GET through the desk's robots gate. A Disallow or unreadable robots refuses the fetch."""
    from research import index_discovery as idx
    parts = urllib.parse.urlsplit(url)
    rules = idx._robots_for(parts.scheme, parts.netloc)
    if isinstance(rules, str):
        return None, f"REFUSED: {rules}"
    if not rules.can_fetch(UA, url):
        return None, "REFUSED: robots.txt disallows this path"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(20_000_000), f"HTTP {getattr(r, 'status', 0)}"
    except Exception as exc:
        code = getattr(exc, "code", None)
        return None, f"HTTP {code}" if code else f"{type(exc).__name__}: {str(exc)[:80]}"


def page_url(since: date, page: int) -> str:
    q = {"filter": f"auction_date:gte:{since.isoformat()}",
         "sort": "auction_date", "format": "json",
         "page[size]": str(PAGE_SIZE), "page[number]": str(page)}
    return API + "?" + urllib.parse.urlencode(q, safe=":,[]()")


def fetch(since: date, get: Any = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Every auction row from `since`, paged. Returns (rows, fetch report)."""
    get = get or _gated_get
    rows: list[dict[str, Any]] = []
    rep: dict[str, Any] = {"since": since.isoformat(), "requests": 0, "pages": 0}
    for page in range(1, MAX_PAGES + 1):
        body, why = get(page_url(since, page))
        rep["requests"] += 1
        if body is None:
            rep["status"] = UNMEASURED if page == 1 else "PARTIAL"
            rep["why"] = why
            return rows, rep
        try:
            doc = json.loads(body)
        except ValueError:
            rep.update(status=UNMEASURED, why="response is not JSON")
            return rows, rep
        data = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(data, list):
            rep.update(status=UNMEASURED, why="response carries no data list")
            return rows, rep
        rows.extend(r for r in data if isinstance(r, dict))
        rep["pages"] = page
        total = ((doc.get("meta") or {}).get("total-pages") if isinstance(doc, dict) else None)
        if not data or (isinstance(total, int) and page >= total):
            break
        time.sleep(1.0)                                  # polite: one request a second
    rep["status"] = "OK"
    return rows, rep


# -------------------------------------------------------------------------- normalisation ---
def _num(v: Any) -> float | None:
    try:
        x = float(str(v).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _close_hm(raw: Any) -> tuple[int, int] | None:
    """'01:00 PM' -> (13, 0). None when it does not parse."""
    s = str(raw or "").strip().upper()
    for fmt in ("%I:%M %p", "%H:%M"):
        try:
            t = time.strptime(s, fmt)
            return t.tm_hour, t.tm_min
        except ValueError:
            continue
    return None


def _is_coupon(r: dict[str, Any]) -> bool:
    if str(r.get("security_type") or "").strip() not in COUPON_TYPES:
        return False
    for flag in ("tips", "inflation_index_security", "floating_rate"):
        if str(r.get(flag) or "").strip().lower() in ("yes", "y", "true"):
            return False
    term = str(r.get("security_term") or "").upper()
    return "TIPS" not in term and "FRN" not in term


def normalise(raw_rows: list[dict[str, Any]], retrieved: datetime
              ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Coupon results as stamped rows, oldest first, with the same-term bid-to-cover surprise."""
    counts = {"rows_in": len(raw_rows), "not_coupon": 0, "no_result_yet": 0,
              "close_time_fallback": 0, "btc_surprise_unmeasured": 0}
    seen: dict[str, dict[str, Any]] = {}
    for r in raw_rows:
        if not _is_coupon(r):
            counts["not_coupon"] += 1
            continue
        hy, med, btc = (_num(r.get("high_yield")), _num(r.get("avg_med_yield")),
                        _num(r.get("bid_to_cover_ratio")))
        try:
            day = date.fromisoformat(str(r.get("auction_date") or "")[:10])
        except ValueError:
            counts["no_result_yet"] += 1
            continue
        if hy is None or btc is None:
            counts["no_result_yet"] += 1          # announced, not yet auctioned
            continue
        hm = _close_hm(r.get("closing_time_comp"))
        if hm is None:
            counts["close_time_fallback"] += 1
            hm = FALLBACK_CLOSE
        closed = datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=ZoneInfo(NY))
        avail = (closed + timedelta(minutes=PUBLISH_PAD_MIN)).astimezone(UTC)
        key = f"{r.get('cusip')}|{day.isoformat()}"
        seen[key] = {
            "event_time": closed.astimezone(UTC).isoformat(),
            "published_time": avail.isoformat(), "available_time": avail.isoformat(),
            "retrieval_time": retrieved.isoformat(), "source_id": SOURCE_ID,
            "vintage_id": f"{SOURCE_ID}:{key}", "cusip": str(r.get("cusip") or ""),
            "security_term": str(r.get("security_term") or "").strip(),
            "security_type": str(r.get("security_type") or "").strip(),
            "auction_date": day.isoformat(), "high_yield": hy, "avg_med_yield": med,
            "tail_bp": None if med is None else round((hy - med) * 100.0, 4),
            "bid_to_cover": btc, "btc_surprise": None,
        }
    rows = sorted(seen.values(), key=lambda x: (x["available_time"], x["cusip"]))
    by_term: dict[str, list[float]] = {}
    for row in rows:
        hist = by_term.setdefault(row["security_term"], [])
        prior = hist[-BTC_TRAIL:]
        if len(prior) >= BTC_MIN_PRIOR:
            row["btc_surprise"] = round(row["bid_to_cover"] - sum(prior) / len(prior), 4)
        else:
            counts["btc_surprise_unmeasured"] += 1
        hist.append(float(row["bid_to_cover"]))
    return rows, counts


def to_series(rows: list[dict[str, Any]]) -> Any:
    """One row per `available_time` (two results published at the same minute are averaged), the
    envelope `family_exogenous_conditioner.conditioner` reads."""
    import pandas as pd
    if not rows:
        return pd.DataFrame(columns=["available_time", *SIGNALS])
    df = pd.DataFrame(rows)
    stamp_cols = ["event_time", "published_time", "retrieval_time", "source_id", "vintage_id",
                  "cusip", "security_term", "auction_date"]
    agg: dict[str, Any] = dict.fromkeys(stamp_cols, "first")
    agg["vintage_id"] = lambda s: "+".join(map(str, s))
    agg.update(dict.fromkeys(SIGNALS, "mean"))
    out = df.groupby("available_time", sort=True).agg(agg).reset_index()
    return out[["available_time", *stamp_cols, *SIGNALS]]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text, "utf-8")
    os.replace(tmp, path)


def _load_raw() -> list[dict[str, Any]]:
    try:
        doc = json.loads(RAW.read_text("utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in doc if isinstance(r, dict)] if isinstance(doc, list) else []


def _last_report() -> dict[str, Any]:
    try:
        doc = json.loads(OUT.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


# ----------------------------------------------------------------------------------- pass ---
def run(*, fetch_now: bool = True, get: Any = None, now: datetime | None = None,
        out: Path | None = None) -> dict[str, Any]:
    at = now or _now()
    prev = _last_report()
    raw = _load_raw()
    fetched: dict[str, Any] = {"status": "SKIPPED", "why": "--no-fetch"}
    last_ok = str(prev.get("last_fetch_ok_at") or "")
    if fetch_now:
        due = True
        if last_ok:
            try:
                age = (at - datetime.fromisoformat(last_ok)).total_seconds()
                due = age >= REFRESH_HOURS * 3600
            except ValueError:
                due = True
        if not due:
            fetched = {"status": "NOT_DUE",
                       "why": f"last fetch {last_ok}, cadence {REFRESH_HOURS}h"}
        else:
            known = [str(r.get("auction_date") or "")[:10] for r in raw]
            since = BACKFILL_FROM
            if known:
                since = max(BACKFILL_FROM,
                            date.fromisoformat(max(known)) - timedelta(days=OVERLAP_DAYS))
            new_rows, fetched = fetch(since, get)
            if new_rows:
                merged = {f"{r.get('cusip')}|{str(r.get('auction_date'))[:10]}": r for r in raw}
                merged.update({f"{r.get('cusip')}|{str(r.get('auction_date'))[:10]}": r
                               for r in new_rows})
                raw = sorted(merged.values(), key=lambda r: str(r.get("auction_date")))
                _atomic_write(RAW, json.dumps(raw))
            if fetched.get("status") == "OK":
                last_ok = at.isoformat()
    rows, counts = normalise(raw, at)
    series_rows = 0
    if rows:
        frame = to_series(rows)
        _atomic_write(SERIES, frame.to_csv(index=False))
        series_rows = len(frame)
    fields_seen = sorted({k for r in raw[:50] for k in r})
    missing = [f for f in ("high_yield", "avg_med_yield", "bid_to_cover_ratio",
                           "closing_time_comp", "security_type", "security_term")
               if raw and f not in fields_seen]
    latest = rows[-1] if rows else None
    doc = {
        "at": at.isoformat(), "organ": "desks/mt5/research/ust_auction_results.py",
        "source": {"api": API, "dataset": DATASET_PAGE, "terms": (
            "US Treasury FiscalData, keyless public API; US federal data in the public domain"),
            "robots_gate": "research.index_discovery._robots_for, own UA", "user_agent": UA},
        "fetch": fetched, "last_fetch_ok_at": last_ok or None,
        "status": "MEASURED" if rows else UNMEASURED,
        "why": None if rows else (fetched.get("why") or "no auction result held on this host"),
        "raw_rows": len(raw), "coupon_results": len(rows), "series_rows": series_rows,
        "series_path": str(SERIES.relative_to(BASE)) if rows else None,
        "counts": counts, "fields_missing": missing,
        "columns": {
            "tail_bp": {"tail_kind": "high_minus_median",
                        "definition": "(high_yield - avg_med_yield) x 100, basis points",
                        "not": "the when-issued tail: the WI yield is not in the public data"},
            "btc_surprise": {"definition": (f"bid_to_cover minus the mean of the previous "
                                            f"{BTC_TRAIL} same-term auctions (>= {BTC_MIN_PRIOR} "
                                            "required, else empty)")},
            "bid_to_cover": {"definition": "bid_to_cover_ratio as published"}},
        "point_in_time": (f"available_time = competitive close ({NY} wall clock) + "
                          f"{PUBLISH_PAD_MIN} min; absent close time -> 17:00 {NY}. The family "
                          "adds lag_hours before a bar may see it"),
        "latest": latest,
        "consumer": ("mt5desk/family_exogenous_conditioner.py (event_window_hours) via "
                     "research/specialist_cell.py mechanism ust_auction_result -> "
                     "data/intelligence/specialist_cell/ -> the docket -> build_cell (sealed)"),
    }
    _atomic_write(out or OUT, json.dumps(doc, indent=1, default=str))
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the scheduled form)")
    ap.add_argument("--no-fetch", action="store_true", help="rebuild from the raw store only")
    args = ap.parse_args(argv)
    doc = run(fetch_now=not args.no_fetch)
    print(f"ust_auction_results: {doc['status']} fetch={doc['fetch'].get('status')} "
          f"raw={doc['raw_rows']} coupons={doc['coupon_results']} series={doc['series_rows']} "
          f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
