"""JOBS-POSTINGS NOWCAST: a point-in-time postings index per country, and its surprise against
the last official print, landed in the world dataset hunter's store so `build_exposure` hands both
to `world_macro_proposer` (world_macro_state cells) for the related FX pair and index CFD.

NOTHING IS FETCHED HERE. The inputs are what other doors already landed:

    ADZUNA/POSTINGS_<CC>   live advert counts per country (world_dataset_hunter.jobs_doors; held
                           on Adzuna's terms until written consent, so normally empty)
    alt_us_usajobs_postings  the USAJOBS open-announcement count (alt_proxies, USAJOBS_API_KEY)
    BLS/JOLTS_CES          JOLTS openings, the official anchor (world_dataset_hunter.jobs_doors,
                           BLS_API_KEY)

DEFINITIONS (every point is stamped at the LATEST availability of everything it uses):

    index      100 * postings_t / mean(postings over the 365 days to t), from 4 observations
    surprise   100 * (postings_t / mean postings during month m - 1), where m is the reference
               month of the last JOLTS openings print available at t: how far postings have moved
               since the month the last official number describes -- the nowcast of the next
               print's change. Needs 3 postings observations inside month m; else no point.
    implied    the JOLTS openings level that change implies (last print * (1 + surprise/100)).

Only the US has an official anchor from a held key; every other country's surprise is
UNMEASURED (no point is written, and the report says so). Runs inside the hunter's hourly leg
(`world_dataset_hunter.run` -> `ingest`).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"
INDEX_WINDOW_D = 365
INDEX_MIN_N = 4
ANCHOR_MIN_N = 3
PROVIDER = "JOBS_NOWCAST"
#: The countries with an official anchor series in the store: (provider, dataset, series_code).
ANCHORS = {"us": ("BLS", "JOLTS_CES", "us_jolts_openings")}
USAJOBS_AXIS = "alt_us_usajobs_postings.json"
USAJOBS_SERIES = "usajobs_open_total.value"

#: One observation: (event date, available instant, value).
Obs = tuple[Any, Any, float]


def _ts(x: Any) -> Any:
    import pandas as pd
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def first_vintage_rows(frame: Any, code: str) -> list[Obs]:
    """(period_end, known instant, value) of one stored series, first vintage of each period,
    keyed exactly as `world_dataset_hunter.pit_series` keys it."""
    import pandas as pd
    if frame is None or not len(frame):
        return []
    rows = frame[frame["series_code"] == code]
    if rows.empty:
        return []
    rows = rows.sort_values("first_seen_utc").drop_duplicates("period", keep="first")
    first_fetch = rows["first_seen_utc"].min()
    watched = rows["first_seen_utc"] > first_fetch + pd.Timedelta(hours=36)
    known = rows["available_time"].where(~watched,
                                         rows[["available_time", "first_seen_utc"]].max(axis=1))
    return sorted((_ts(e), _ts(k), float(v)) for e, k, v in
                  zip(rows["period_end"], known, rows["value"], strict=False))


def axis_rows(doc: Any, series: str) -> list[Obs]:
    """(event date, available instant, value) from an alt_proxies axis document."""
    pts = (((doc or {}).get("series") or {}).get(series) or {}).get("points") or []
    out: list[Obs] = []
    for p in pts:
        try:
            out.append((_ts(p["d"]), _ts(p["available_time"]), float(p["v"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out)


def nowcast(postings: Iterable[Obs], anchor: Iterable[Obs] = ()) -> dict[str, list[Obs]]:
    """{index, surprise, implied} as (event date, available instant, value). Pure and causal:
    each point uses only observations available at or before its own available instant."""
    import pandas as pd
    post = sorted(postings, key=lambda o: o[1])
    anc = sorted(anchor, key=lambda o: o[1])
    out: dict[str, list[Obs]] = {"index": [], "surprise": [], "implied": []}
    for ev, av, v in post:
        seen = [o for o in post if o[1] <= av and av - o[1] <= pd.Timedelta(days=INDEX_WINDOW_D)]
        if len(seen) >= INDEX_MIN_N:
            base = sum(o[2] for o in seen) / len(seen)
            if base > 0:
                out["index"].append((ev, av, 100.0 * v / base))
        known = [a for a in anc if a[1] <= av]
        if not known:
            continue
        m_end, m_known, level = known[-1]
        in_m = [o[2] for o in post if o[1] <= av and o[0].year == m_end.year
                and o[0].month == m_end.month]
        if len(in_m) < ANCHOR_MIN_N:
            continue
        mean_m = sum(in_m) / len(in_m)
        if mean_m <= 0:
            continue
        s = 100.0 * (v / mean_m - 1.0)
        at = max(av, m_known)
        out["surprise"].append((ev, at, s))
        out["implied"].append((ev, at, level * (1.0 + s / 100.0)))
    return out


def as_series(country: str, parts: dict[str, list[Obs]],
              anchor_name: str = "") -> list[dict[str, Any]]:
    """Hunter series dicts: period = the event day, `available` = the point's own instant."""
    out = []
    for what, pts in parts.items():
        if not pts:
            continue
        code = (f"{country}_postings_{what}" if what == "index"
                else f"{country}_postings_{what}_vs_{anchor_name or 'official'}")
        per: dict[str, tuple[float, str]] = {}
        for ev, av, v in pts:
            per[ev.date().isoformat()] = (v, av.isoformat())       # last read of a day wins
        out.append({"code": code, "name": f"jobs postings nowcast {country.upper()} {what}",
                    "freq": "daily", "dims": {"country": country.upper()},
                    "points": [(p, v) for p, (v, _) in sorted(per.items())],
                    "available": {p: a for p, (_, a) in per.items()}})
    return out


def _inputs(W: Any) -> tuple[dict[str, list[Obs]], dict[str, list[Obs]], dict[str, str]]:
    postings: dict[str, list[Obs]] = {}
    sources: dict[str, str] = {}
    for spec in W.jobs_doors():
        if spec["provider"] != "ADZUNA":
            continue
        cc = spec["dataset"].split("_", 1)[1].lower()
        rows = first_vintage_rows(W._load_frame(W.dataset_path("ADZUNA", spec["dataset"])),
                                  f"{cc}_postings_total")
        if rows:
            postings[cc] = rows
            sources[cc] = "adzuna"
    axis = Path(W.DESK) / "data" / "axes" / USAJOBS_AXIS
    try:
        doc = json.loads(axis.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None
    usaj = axis_rows(doc, USAJOBS_SERIES)
    if usaj and "us" not in postings:
        # federal postings only stand in for the US when no all-economy count is held
        postings["us"] = usaj
        sources["us"] = "usajobs_federal"
    anchors = {cc: first_vintage_rows(W._load_frame(W.dataset_path(p, d)), code)
               for cc, (p, d, code) in ANCHORS.items()}
    return postings, anchors, sources


def ingest(now: datetime, qstats: Any) -> dict[str, Any]:
    """Compute and land every country's nowcast through the hunter's `ingest_series` (PIT merge,
    quality, pinned instruments). Returns the per-country reading for the report."""
    from research import world_dataset_hunter as W
    postings, anchors, sources = _inputs(W)
    report: dict[str, Any] = {}
    for cc in sorted(set(W.JOBS_PINS) | set(postings)):
        pts = postings.get(cc) or []
        if not pts:
            report[cc] = {"index": UNMEASURED, "surprise": UNMEASURED,
                          "why": "no postings observations landed for this country"}
            continue
        parts = nowcast(pts, anchors.get(cc) or ())
        series = as_series(cc, parts, "jolts" if cc in ANCHORS else "")
        res = (W.ingest_series(PROVIDER, cc.upper(), f"jobs postings nowcast {cc.upper()}",
                               series, now=now, base_score=4.0, qstats=qstats,
                               pin_instruments=W.JOBS_PINS.get(cc, ()))
               if series else {"rows_added": 0})
        report[cc] = {
            "source": sources.get(cc, UNMEASURED),
            "index_points": len(parts["index"]) or UNMEASURED,
            "surprise_points": (len(parts["surprise"]) or UNMEASURED) if cc in ANCHORS
            else UNMEASURED,
            "anchor": ("BLS JOLTS openings" if cc in ANCHORS
                       else "UNMEASURED: no official anchor from a held key"),
            "rows_added": res.get("rows_added", 0)}
    return report
