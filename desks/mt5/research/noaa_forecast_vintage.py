"""NOAA CPC forecast VINTAGES -> dated revisions the desk may condition on (natgas, power, ags).

WHY THIS EXISTS (2026-11-11). Natural gas, power and the grains move on how the weather FORECAST
changes between issues, not on the weather. A revision series needs every issued forecast kept
with the instant it was issued, so a reader at time t sees only the issues knowable at t. The
free Open-Meteo API is non-commercial and stays fail-closed; NOAA's products are US-government
works (17 U.S.C. 105, public domain), so they may back a position.

WHAT IT READS (rows in `noaa_forecast_sources.json`; a new product is a row, never code).
  cpc_dd7_pipe          CPC's daily 7-day degree-day forecast from NDFD grids, by census
                        division, one file per weighting (utility gas, electricity, population)
                        in a dated archive `.../daily_forecasts_7day/YYYY/MM/DD/<W>.<Heating|
                        Cooling>.txt`, issued 0000 UTC every day, archived since 2014-12.
  cpc_dd_monthly_fixed  CPC's long-lead monthly total degree-day forecast (`ddforecast.txt`),
                        one block per census region / state, ~15 target months, overwritten in
                        place each month with its issue stamp in the header.
Text only: no GRIB library is used or needed.

POINT-IN-TIME. `issue_time_utc` is read from the product's OWN header; a file whose header
carries no issue stamp is rejected (counted, never guessed). `knowable_from_utc` is
    max(issue_time, min(fetch_time, issue_time + publish_lag_hours))
i.e. the fetch time when this pass saw the issue within its declared posting lag, and the
declared lag otherwise (an archived issue fetched years later was not unknowable until today).
The 7-day files are posted hours after their 0000 UTC stamp, so the lag is a conservative day.

STORAGE. `data/lake/forecast_vintages/<product>.jsonl.gz`: append-only gzip members, one row per
(issue, target period, region, measure). An issue is stored ONCE in its life, keyed by product +
issue time; a refetch of a stored issue adds nothing, and one whose content changed is counted in
the report (`same_issue_changed`) and never overwrites the vintage already held.

REVISIONS. For each (region, measure, target) the change from the PREVIOUS ISSUE that carried the
same target. `<product>.revisions.jsonl` (long form) holds every one; `data/lake/series/
noaa_<product>.parquet` holds one row per issue in the PIT envelope
`mt5desk/family_exogenous_conditioner.py` reads (`available_time`, `event_time`, `source_id`,
`vintage_id`, `retrieval_time` + numeric columns `<region>_<measure>_rev`, `_lvl`, `_nov`). A
first issue has no previous: its revision is null, UNMEASURED, never 0.

POLITENESS. `libs.data.polite_fetch` (shared host gate, honest UA) with retries OFF, a hard
per-pass fetch budget, robots.txt read first per host and obeyed per exact path (a Disallow is
ROBOTS_REFUSED with a missed_growth line; an unreadable robots.txt fetches nothing and is
UNMEASURED). 401/403/429/451 is a HARD STOP for that host, recorded, never retried in the pass and
never routed around; it is tried again after HARD_STOP_COOLDOWN, and the first refusal stops it
again.

    python desks/mt5/research/noaa_forecast_vintage.py --once
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import urllib.robotparser
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCES = Path(__file__).with_name("noaa_forecast_sources.json")
VINTAGES = DESK / "data" / "lake" / "forecast_vintages"
SERIES = DESK / "data" / "lake" / "series"
UNIVERSE = DESK / "data" / "universe" / "universe.json"
REPORT = DESK / "reports" / "NOAA_FORECAST_VINTAGES.json"

HARD_STOP = frozenset({401, 403, 429, 451})
HARD_STOP_COOLDOWN = timedelta(hours=24)
#: Product files fetched per pass, all products together. The 7-day archive is ~365 files a year
#: per weighting; at this rate the backfill drains in weeks while the host sees a slow reader.
MAX_FETCHES_PER_PASS = 48
#: An archived date that answers 404 this many times is given up on and named in the report.
MAX_MISSING_ATTEMPTS = 3
STATUSES = ("OK", "EMPTY", "HARD_STOP", "UNMEASURED", "ROBOTS_REFUSED")

Fetch = Callable[[str], tuple[int | None, str, str]]


# ----------------------------------------------------------------------------- parsers

def _ymd(s: str) -> str:
    """'20261110' -> '2026-11-10'."""
    return date(int(s[:4]), int(s[4:6]), int(s[6:8])).isoformat()


_DD7_HEAD = re.compile(r"Issued\s+(\d{2})(\d{2})UTC\s+(\d{8})")


def parse_cpc_dd7(text: str, product: Mapping[str, Any],
                  regions: Mapping[str, str]) -> tuple[datetime | None, list[dict[str, Any]]]:
    """CPC 7-day degree-day forecast (pipe-delimited) -> (issue time, rows).

    One row per (day, region) plus one `period_total` row per region from the file's own Total
    column. No `Issued HHMMUTC YYYYMMDD` header -> (None, []): an unstamped issue is unusable.
    """
    m = _DD7_HEAD.search(text)
    if not m:
        return None, []
    issue = datetime.strptime(m.group(3) + m.group(1) + m.group(2) + "+0000", "%Y%m%d%H%M%z")
    cols: list[str] = []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        if cells[0].lower() == "region":
            cols = cells
            continue
        if not cols:
            continue
        code = cells[0]
        name = str(regions.get(code) or f"region_{code}".lower())
        days = [c for c in cols[1:] if re.fullmatch(r"\d{8}", c)]
        for col, val in zip(cols[1:], cells[1:], strict=False):
            try:
                v = float(val)
            except ValueError:
                continue
            if re.fullmatch(r"\d{8}", col):
                d = _ymd(col)
                rows.append({"target_kind": "day", "target_start": d, "target_end": d,
                             "region": name, "region_code": code, "value": v})
            elif col.lower() == "total" and days:
                rows.append({"target_kind": "period_total",
                             "target_start": _ymd(days[0]), "target_end": _ymd(days[-1]),
                             "region": name, "region_code": code, "value": v})
    measure = str(product.get("measure") or "dd")
    for r in rows:
        r["measure"] = measure
    return issue, rows


_US_TZ = {"EDT": -4, "EST": -5, "CDT": -5, "CST": -6, "MDT": -6, "MST": -7, "PDT": -7,
          "PST": -8, "UTC": 0, "GMT": 0}
_MON_HEAD = re.compile(r"^\s*(\d{3,4})\s+(AM|PM)\s+([A-Z]{3})\s+[A-Z]{3}\s+(\d{1,2})\s+([A-Z]{3})"
                       r"\s+(\d{4})\s*$", re.M)
_REGION_HEAD = re.compile(r"^\s*([A-Z][A-Z .]+?)\s*\(([^)]*)\)\s+NORMALS\s+FORECAST", re.M)
_MONTH_ROW = re.compile(r"^\s*(\d{4})\s+(\d{1,2})\s+((?:-?[\d.]+\s+){9}-?[\d.]+)\s*$")
_MONTH_COLS = ("hdd_p90", "hdd_mean", "hdd_p10", "cdd_p90", "cdd_mean", "cdd_p10",
               "hdd_normal", "cdd_normal", "hdd_departure", "cdd_departure")


def monthly_issue_time(text: str) -> datetime | None:
    """`300 PM EDT THU 15 OCT 2026` -> 2026-10-15T19:00Z. None when absent or zone unknown."""
    m = _MON_HEAD.search(text)
    if not m or m.group(3) not in _US_TZ:
        return None
    hhmm = m.group(1).zfill(4)
    hour, minute = int(hhmm[:2]) % 12, int(hhmm[2:])
    if m.group(2) == "PM":
        hour += 12
    try:
        local = datetime.strptime(f"{m.group(4)} {m.group(5)} {m.group(6)} +0000",
                                  "%d %b %Y %z")
    except ValueError:
        return None
    return (local.replace(hour=hour, minute=minute)
            - timedelta(hours=_US_TZ[m.group(3)]))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


Parsed = tuple[datetime | None, list[dict[str, Any]]]


def parse_cpc_dd_monthly(text: str, product: Mapping[str, Any],
                         regions: Mapping[str, str]) -> Parsed:
    """CPC long-lead monthly degree-day forecast (fixed width) -> (issue time, rows).

    One row per (region block, target month, measure hdd|cdd): `value` is the MEAN, `values`
    carries the 90%/10% bounds, the normal and the departure exactly as printed.
    """
    issue = monthly_issue_time(text)
    if issue is None:
        return None, []
    rows: list[dict[str, Any]] = []
    region: str | None = None
    for line in text.splitlines():
        h = _REGION_HEAD.match(line)
        if h:
            region = _slug(h.group(1))
            continue
        m = _MONTH_ROW.match(line)
        if not m or region is None:
            continue
        try:
            nums = [float(x.rstrip(".") or "nan") for x in m.group(3).split()]
            y, mo = int(m.group(1)), int(m.group(2))
            start = date(y, mo, 1)
        except ValueError:
            continue
        end = (date(y + (mo == 12), mo % 12 + 1, 1) - timedelta(days=1))
        vals = dict(zip(_MONTH_COLS, nums, strict=True))
        for meas in ("hdd", "cdd"):
            rows.append({"target_kind": "month", "target_start": start.isoformat(),
                         "target_end": end.isoformat(), "region": region,
                         "region_code": region, "measure": meas,
                         "value": vals[f"{meas}_mean"],
                         "values": {k.split("_", 1)[1]: v for k, v in vals.items()
                                    if k.startswith(meas + "_")}})
    return issue, rows


PARSERS: dict[str, Callable[[str, Mapping[str, Any], Mapping[str, str]],
                            tuple[datetime | None, list[dict[str, Any]]]]] = {
    "cpc_dd7_pipe": parse_cpc_dd7,
    "cpc_dd_monthly_fixed": parse_cpc_dd_monthly,
}


# ----------------------------------------------------------------------------- PIT + store

def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def knowable_from(issue: datetime, fetched: datetime, lag_hours: float) -> tuple[datetime, str]:
    """max(issue, min(fetch, issue + lag)) and which bound set it."""
    bound = issue + timedelta(hours=float(lag_hours))
    if fetched <= bound:
        return max(issue, fetched), "fetch_time"
    return bound, "declared_publish_lag"


def store_path(pid: str, root: Path | None = None) -> Path:
    return (root or VINTAGES) / f"{pid}.jsonl.gz"


def read_vintages(path: Path) -> list[dict[str, Any]]:
    """Every stored row (all gzip members). A torn tail is dropped, never fatal."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except (OSError, EOFError):
        pass
    return out


def stored_issues(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """{issue_time_utc: content sha256} of the issues held."""
    return {str(r["issue_time_utc"]): str(r.get("content_sha256", "")) for r in rows
            if r.get("issue_time_utc")}


def append_issue(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append one issue as its own gzip member. Never rewrites what is already there."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "ab") as fh:
        fh.write("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                         for r in rows).encode("utf-8"))


def vintage_rows(pid: str, product: Mapping[str, Any], issue: datetime,
                 parsed: list[dict[str, Any]], *, fetched: datetime, url: str,
                 raw: str, terms: str) -> list[dict[str, Any]]:
    kf, basis = knowable_from(issue, fetched, float(product.get("publish_lag_hours", 24)))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    vid = f"{pid}@{_iso(issue)}"
    return [{**r, "product": pid, "issue_time_utc": _iso(issue),
             "knowable_from_utc": _iso(kf), "knowable_basis": basis,
             "fetched_utc": _iso(fetched), "units": product.get("units", ""),
             "weights": product.get("weights", ""), "source_url": url,
             "content_sha256": digest, "vintage_id": vid, "terms": terms} for r in parsed]


# ----------------------------------------------------------------------------- revisions

def revisions(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """For each (region, measure, target_kind, target), the change from the previous issue that
    carried the same target. Issues are ordered by issue time, never by fetch order, so a
    backfilled older issue slots in where it belongs."""
    by_key: dict[tuple[str, str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("value") is None:
            continue
        by_key[(str(r["region"]), str(r["measure"]), str(r["target_kind"]),
                str(r["target_start"]), str(r["target_end"]))].append(r)
    out: list[dict[str, Any]] = []
    for (region, meas, kind, ts, te), vs in by_key.items():
        vs = sorted(vs, key=lambda r: str(r["issue_time_utc"]))
        prev: Mapping[str, Any] | None = None
        for r in vs:
            if prev is not None and prev["issue_time_utc"] == r["issue_time_utc"]:
                continue
            rev = None if prev is None else round(float(r["value"]) - float(prev["value"]), 6)
            out.append({"product": r["product"], "region": region, "measure": meas,
                        "target_kind": kind, "target_start": ts, "target_end": te,
                        "issue_time_utc": r["issue_time_utc"],
                        "prev_issue_time_utc": None if prev is None else prev["issue_time_utc"],
                        "value": float(r["value"]),
                        "prev_value": None if prev is None else float(prev["value"]),
                        "revision": rev,
                        # usable only once BOTH issues were knowable
                        "available_time": max(str(r["knowable_from_utc"]),
                                              str((prev or r)["knowable_from_utc"])),
                        "units": r.get("units", ""), "vintage_id": r.get("vintage_id", "")})
            prev = r
    out.sort(key=lambda x: (x["issue_time_utc"], x["region"], x["measure"], x["target_start"],
                            x["target_kind"]))
    return out


def series_frame(revs: list[dict[str, Any]], pid: str, product: Mapping[str, Any]) -> Any:
    """One row per issue in the lake's PIT envelope.

    `<region>_<measure>_rev`  sum of revisions over the targets this issue shares with the one
                              before it (daily targets for the 7-day product, months for the
                              monthly); null for a first issue, UNMEASURED.
    `<region>_<measure>_lvl`  the issue's level: its own period total (7-day) or its front
                              target month (monthly).
    `<region>_<measure>_nov`  how many shared targets the revision is summed over.
    """
    import pandas as pd

    rev_kind = "day" if product.get("format") == "cpc_dd7_pipe" else "month"
    lvl_kind = "period_total" if rev_kind == "day" else "month"
    per: dict[str, dict[str, Any]] = {}
    front: dict[tuple[str, str], str] = {}
    for r in revs:
        it = str(r["issue_time_utc"])
        row = per.setdefault(it, {"event_time": it, "available_time": r["available_time"],
                                  "vintage_id": r["vintage_id"]})
        row["available_time"] = max(str(row["available_time"]), str(r["available_time"]))
        col = f"{r['region']}_{r['measure']}"
        if r["target_kind"] == rev_kind and r["revision"] is not None:
            row[f"{col}_rev"] = float(row.get(f"{col}_rev") or 0.0) + float(r["revision"])
            row[f"{col}_nov"] = int(row.get(f"{col}_nov") or 0) + 1
        if r["target_kind"] == lvl_kind:
            k = (it, col)
            if lvl_kind == "period_total" or k not in front or r["target_start"] < front[k]:
                front[k] = str(r["target_start"])
                row[f"{col}_lvl"] = float(r["value"])
    if not per:
        return pd.DataFrame(columns=["available_time", "event_time", "source_id", "vintage_id",
                                     "retrieval_time"])
    df = pd.DataFrame(sorted(per.values(), key=lambda x: x["event_time"]))
    df["available_time"] = pd.to_datetime(df["available_time"], utc=True)
    df["event_time"] = pd.to_datetime(df["event_time"], utc=True)
    df["source_id"] = f"noaa_{pid}"
    df["retrieval_time"] = _iso(datetime.now(UTC))
    stamp = ["available_time", "event_time", "source_id", "vintage_id", "retrieval_time"]
    return df[stamp + sorted(c for c in df.columns if c not in stamp)]


def write_series(df: Any, pid: str, root: Path | None = None) -> Path:
    base = root or SERIES
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"noaa_{pid}.parquet"
    tmp = p.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, p)
    return p


# ----------------------------------------------------------------------------- the pass

def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False), "utf-8")
    try:
        os.replace(tmp, p)
    except PermissionError:          # Windows: a reader holds the destination
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def _polite_fetch(agent: str) -> Fetch:
    from libs.data import polite_fetch

    def fetch(url: str) -> tuple[int | None, str, str]:
        # retries OFF: 429 is in polite_fetch's retry set, and a refusal is never retried here
        r = polite_fetch.get(url, headers={"User-Agent": agent}, retries=0,
                             leg="noaa_forecast_vintage")
        return r.status, r.text, r.error
    return fetch


def robots_allows(robots_text: str, url: str, agent: str) -> bool:
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_text.splitlines())
    return rp.can_fetch(agent, url)


def candidate_urls(product: Mapping[str, Any], today: date, done: set[str],
                   given_up: set[str]) -> list[tuple[str, str]]:
    """[(date key, url)] to try this pass, newest first: the live lookback window every pass,
    then the archive back to `backfill_from`, skipping dates already held or given up on.
    A fixed URL (no {yyyy}) is one candidate keyed 'current', fetched every pass."""
    tmpl = str(product["url"])
    if "{yyyy}" not in tmpl:
        return [("current", tmpl)]
    try:
        floor = date.fromisoformat(str(product.get("backfill_from") or today.isoformat()))
    except ValueError:
        floor = today
    floor = min(floor, today - timedelta(days=int(product.get("lookback_days", 3)) - 1))
    out: list[tuple[str, str]] = []
    d = today
    while d >= floor:
        k = d.isoformat()
        if k not in done and k not in given_up:
            out.append((k, tmpl.format(yyyy=f"{d.year:04d}", mm=f"{d.month:02d}",
                                       dd=f"{d.day:02d}")))
        d -= timedelta(days=1)
    return out


def instruments_in_universe(product: Mapping[str, Any], universe: Mapping[str, Any]
                            ) -> tuple[list[str], list[str]]:
    want = [str(s) for s in product.get("instruments") or []]
    return [s for s in want if s in universe], [s for s in want if s not in universe]


def refresh(*, fetch: Fetch | None = None, registry: Mapping[str, Any] | None = None,
            vintages: Path | None = None, series: Path | None = None,
            report: Path | None = None, universe: Mapping[str, Any] | None = None,
            now: datetime | None = None, max_fetches: int = MAX_FETCHES_PER_PASS,
            write_lake: bool = True) -> dict[str, Any]:
    """One pass over every registered product. Returns the report (also written)."""
    reg = registry if registry is not None else _read_json(SOURCES, {})
    vdir = vintages or VINTAGES
    report = report or REPORT
    uni = universe if universe is not None else (_read_json(UNIVERSE, {}) or {})
    now = now or datetime.now(UTC)
    today = now.date()
    agent = str(reg.get("user_agent") or "quant-desk-research/1.0")
    terms = str(reg.get("terms") or "unverified")
    regions = {str(k): str(v) for k, v in (reg.get("census_divisions") or {}).items()}
    get = fetch or _polite_fetch(agent)
    state = _read_json(vdir / "state.json", {})
    stops: dict[str, Any] = state.setdefault("hard_stops", {})
    missing: dict[str, int] = state.setdefault("missing_attempts", {})
    given_up_all: dict[str, list[str]] = state.setdefault("given_up", {})
    robots_cache: dict[str, str | None] = {}
    budget = max_fetches
    rep: dict[str, Any] = {"generated_at": _iso(now), "products": {}, "fetches": 0,
                           "terms": terms, "terms_basis": reg.get("terms_basis", ""),
                           "statuses": list(STATUSES)}

    def host_stopped(host: str) -> bool:
        s = stops.get(host)
        if not s:
            return False
        try:
            if now - datetime.fromisoformat(str(s["at"])) >= HARD_STOP_COOLDOWN:
                stops.pop(host, None)
                return False
        except (KeyError, TypeError, ValueError):
            pass
        return True

    def robots_for(host_base: str) -> str | None:
        if host_base not in robots_cache:
            st, txt, _e = get(host_base + "/robots.txt")
            rep["fetches"] += 1
            if st in HARD_STOP:
                stops[urlsplit(host_base).netloc] = {"code": st, "url": host_base + "/robots.txt",
                                                    "at": _iso(now)}
                robots_cache[host_base] = None
            elif st is not None and 200 <= st < 300:
                robots_cache[host_base] = txt
            elif st == 404:
                robots_cache[host_base] = ""     # no robots.txt: nothing is disallowed
            else:
                robots_cache[host_base] = None
        return robots_cache[host_base]

    products = list(reg.get("products") or [])
    # a fair share each, so one product's backfill can never starve another's live issue
    share = max(1, -(-max_fetches // max(1, len(products))))
    last_fixed: dict[str, str] = state.setdefault("fixed_last_fetch", {})
    for product in products:
        pid = str(product["id"])
        mine = share
        fmt = str(product.get("format") or "")
        ok_syms, absent = instruments_in_universe(product, uni)
        p: dict[str, Any] = {"format": fmt, "url": product.get("url"),
                             "cadence": product.get("cadence"), "instruments": ok_syms,
                             "instruments_absent": absent, "new_issues": 0, "fetched": 0,
                             "not_yet_posted": 0, "parse_failed": 0, "same_issue_changed": 0,
                             "robots_refused": 0, "errors": []}
        rep["products"][pid] = p
        if absent:
            p["missed_growth_instruments"] = (
                f"{', '.join(absent)} named for {pid} but absent from the universe registry: "
                "not mapped, and nothing trades them off this series")
        parser = PARSERS.get(fmt)
        path = store_path(pid, vdir)
        held_rows = read_vintages(path)
        held = stored_issues(held_rows)
        done_dates: set[str] = set(state.setdefault("done", {}).setdefault(pid, []))
        given_up = set(given_up_all.setdefault(pid, []))
        host_base = "{0.scheme}://{0.netloc}".format(urlsplit(str(product["url"])))
        host = urlsplit(host_base).netloc
        status: str | None = None
        if parser is None:
            p["errors"].append(f"no parser for format {fmt!r}")
            status = "UNMEASURED"
        elif host_stopped(host):
            status = "HARD_STOP"
        else:
            robots = robots_for(host_base)
            if host_stopped(host):
                status = "HARD_STOP"
            elif robots is None:
                status = "UNMEASURED"
                p["errors"].append("robots.txt unreadable: nothing fetched (never assumed open)")
            else:
                saw_parse = False
                todo = candidate_urls(product, today, done_dates, given_up)
                if todo and todo[0][0] == "current":
                    try:
                        recent = now - datetime.fromisoformat(last_fixed.get(pid, "")) < \
                            timedelta(hours=float(product.get("min_refetch_hours", 6)))
                    except ValueError:
                        recent = False
                    if recent:
                        todo = []
                        p["skipped_recent_fetch"] = last_fixed[pid]
                for key, url in todo:
                    if budget <= 0 or mine <= 0:
                        p["budget_exhausted"] = True
                        break
                    if not robots_allows(robots, url, agent):
                        p["robots_refused"] += 1
                        continue
                    st, txt, err = get(url)
                    budget -= 1
                    mine -= 1
                    rep["fetches"] += 1
                    p["fetched"] += 1
                    if key == "current":
                        last_fixed[pid] = _iso(now)
                    if st in HARD_STOP:
                        stops[host] = {"code": st, "url": url, "at": _iso(now)}
                        status = "HARD_STOP"
                        break
                    if st == 404:
                        # today's file is posted hours after its stamp; an archived date that
                        # stays missing is given up on after MAX_MISSING_ATTEMPTS
                        if key != "current" and key < (today - timedelta(days=int(
                                product.get("lookback_days", 3)))).isoformat():
                            mk = f"{pid}:{key}"
                            missing[mk] = int(missing.get(mk, 0)) + 1
                            if missing[mk] >= MAX_MISSING_ATTEMPTS:
                                given_up.add(key)
                                missing.pop(mk, None)
                        else:
                            p["not_yet_posted"] += 1
                        continue
                    if st is None or not 200 <= st < 300:
                        p["errors"].append({"url": url, "status": st, "error": (err or "")[:80]})
                        continue
                    issue, parsed = parser(txt, product, regions)
                    if issue is None or not parsed:
                        p["parse_failed"] += 1
                        continue
                    saw_parse = True
                    it = _iso(issue)
                    rows = vintage_rows(pid, product, issue, parsed, fetched=now, url=url,
                                        raw=txt, terms=terms)
                    if it in held:
                        if held[it] and held[it] != rows[0]["content_sha256"]:
                            p["same_issue_changed"] += 1
                    else:
                        append_issue(path, rows)
                        held[it] = rows[0]["content_sha256"]
                        held_rows.extend(rows)
                        p["new_issues"] += 1
                    if key != "current":
                        done_dates.add(key)
                if status is None:
                    if p["robots_refused"] and not p["fetched"]:
                        status = "ROBOTS_REFUSED"
                    elif held:
                        status = "OK"
                    elif p["parse_failed"] or saw_parse or p["not_yet_posted"]:
                        status = "EMPTY"
                    else:
                        status = "UNMEASURED"
        state["done"][pid] = sorted(done_dates)
        given_up_all[pid] = sorted(given_up)
        if host in stops:
            p["hard_stop"] = stops[host]
        p["status"] = status
        p["issues_held"] = len(held)
        if held:
            p["first_issue"], p["last_issue"] = min(held), max(held)
        if status == "HARD_STOP":
            p["missed_growth"] = (f"{pid} unread since {host} answered "
                                  f"{(stops.get(host) or {}).get('code')}; its revisions are "
                                  "UNMEASURED, not zero")
        elif status == "ROBOTS_REFUSED" or p["robots_refused"]:
            p["missed_growth"] = (f"{p['robots_refused']} {pid} URL(s) not fetched because "
                                  "robots.txt disallows them; those issues are UNMEASURED")
        elif status in ("UNMEASURED", "EMPTY"):
            p["missed_growth"] = f"{pid} holds no usable issue: its revisions are UNMEASURED"
        p["errors"] = p["errors"][:10]

        revs = revisions(held_rows)
        p["revision_rows"] = len(revs)
        p["revisions_path"] = str((vdir / f"{pid}.revisions.jsonl").relative_to(ROOT)) \
            if vdir.is_relative_to(ROOT) else str(vdir / f"{pid}.revisions.jsonl")
        if held_rows:
            vdir.mkdir(parents=True, exist_ok=True)
            tmp = vdir / f"{pid}.revisions.jsonl.tmp"
            tmp.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in revs), "utf-8")
            os.replace(tmp, vdir / f"{pid}.revisions.jsonl")
            if write_lake:
                df = series_frame(revs, pid, product)
                sp = write_series(df, pid, series)
                p["series"] = {"path": sp.name, "rows": len(df),
                               "columns": [c for c in df.columns
                                           if c.endswith(("_rev", "_lvl", "_nov"))][:60]}

    _write_json(vdir / "state.json", state)
    rep["status_counts"] = {s: sum(1 for v in rep["products"].values() if v["status"] == s)
                            for s in STATUSES}
    rep["missed_growth"] = [f"{k}: {v['missed_growth']}" for k, v in rep["products"].items()
                            if v.get("missed_growth")]
    rep["left_out"] = {
        "cpc_6_10_8_14_outlooks": "station probability files (fcst610.*.data) served as binary "
                                  "to the reader that surveyed them; layout unverified, so no "
                                  "parser ships until a real sample is held",
        "week_3_4": "published as maps/GIS only; no text form found",
        "open_meteo": "free API is non-commercial: fail-closed",
    }
    _write_json(report, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.add_argument("--max-fetches", type=int, default=MAX_FETCHES_PER_PASS)
    args = ap.parse_args(argv)
    rep = refresh(max_fetches=args.max_fetches)
    print(json.dumps({"fetches": rep["fetches"], "status_counts": rep["status_counts"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
