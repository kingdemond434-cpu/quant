"""Scheduled US event DATES from FRED's release calendar -> the event families' calendar backfill.

WHY (2026-11-10). The event families judged nothing because the desk's event index held twelve
weeks of a polled calendar. Release first prints (futures_state, mode first_release) recover the
history of the releases that have a headline number. The FOMC statement has no such series, and
PPI, GDP, trade and factory orders are not in that set. FRED publishes each release's dates,
past and scheduled, through its API; this writes them as the same calendar rows.

WHAT A ROW IS, AND IS NOT. Timing only: when a scheduled event happened or is due. There is no
actual, no forecast and no surprise in these rows. The date is FRED's; the time of day is the
publisher's fixed release time applied as a convention (`time_basis`), so a row is as right as
that convention was on that day. FRED lists a date when it loaded the release, which for these
releases is the release day; a weekend date cannot be one and is dropped and counted.

OUTPUT, outside `data/intelligence/` on purpose (the candidate compiler mints a cell per
calendar-shaped row it finds there):
    desks/mt5/data/calendar_backfill/backfill_fredrel_<slug>.jsonl.gz
    desks/mt5/reports/FRED_RELEASE_CALENDAR.json     per release: rows, span, drops, or why not

The key is read from the environment and never written, logged or put in an error: failures
are recorded by exception type and HTTP status only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(ROOT), str(DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REGISTRY = Path(__file__).with_name("fred_release_calendar.json")
CALENDAR_BACKFILL = DESK / "data" / "calendar_backfill"
REPORT = DESK / "reports" / "FRED_RELEASE_CALENDAR.json"
API = "https://api.stlouisfed.org/fred"
HARD_STOP = frozenset({401, 403, 429, 451})
UA = "quant-desk-research/1.0 (release calendar)"

Get = Callable[[str], tuple[int | None, Any]]


def _polite_get(url: str) -> tuple[int | None, Any]:
    from libs.data import polite_fetch
    r = polite_fetch.get(url, headers={"User-Agent": UA, "Accept": "application/json"},
                         timeout=40.0, retries=0, leg="release_calendar")
    if not r.ok:
        return r.status, None
    try:
        return r.status, json.loads(r.text)
    except ValueError:
        return r.status, None


def _replace(tmp: Path, p: Path) -> None:
    try:
        os.replace(tmp, p)
    except PermissionError:          # Windows: the destination is held open by a reader
        p.unlink(missing_ok=True)
        os.replace(tmp, p)


def _write_json(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), "utf-8")
    _replace(tmp, p)


def event_rows(rel: Mapping[str, Any], dates: list[str], today: date
               ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Calendar rows for one release, and what was left out and why."""
    tz = ZoneInfo(str(rel["tz"]))
    hh, mm = (int(x) for x in str(rel["at"]).split(":"))
    first = date.fromisoformat(str(rel.get("from") or "1900-01-01"))
    drops = {"before_from": 0, "weekend": 0, "unreadable": 0}
    rows: list[dict[str, Any]] = []
    for raw in sorted(set(dates)):
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            drops["unreadable"] += 1
            continue
        if d < first:
            drops["before_from"] += 1
            continue
        if d.weekday() >= 5:
            drops["weekend"] += 1
            continue
        when = datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz).astimezone(UTC)
        rows.append({"event_date": when.isoformat(), "currency": str(rel["currency"]),
                     "country": str(rel["currency"]), "title": str(rel["title"]),
                     "impact": str(rel.get("impact") or "High"),
                     "release_id": int(rel["rid"]), "source": "fred_release_dates",
                     "instant_basis": "fred_release_date",
                     "time_basis": f"convention {rel['at']} {rel['tz']}",
                     "scheduled": d > today, "timing_only": True, "backfill": True})
    return rows, drops


def refresh(*, get: Get | None = None, registry: Mapping[str, Any] | None = None,
            out: Path | None = None, report: Path | None = None, today: date | None = None,
            key: str | None = None) -> dict[str, Any]:
    """One pass. Each release is asked at most once a day; a day's answer is kept on a failure."""
    reg = registry if registry is not None else json.loads(REGISTRY.read_text("utf-8"))
    out = out or CALENDAR_BACKFILL
    report = report or REPORT
    today = today or datetime.now(UTC).date()
    get = get or _polite_get
    if key is None:
        key = next((os.environ.get(k) for k in reg.get("key_env") or [] if os.environ.get(k)), "")
    try:
        prev = json.loads(report.read_text("utf-8"))
    except (OSError, ValueError):
        prev = {}
    rep: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                           "releases": {}, "requests": 0,
                           "rows_are": "timing only: no actual, forecast or surprise"}
    stopped = prev.get("hard_stop") if prev.get("hard_stop_day") == today.isoformat() else None
    for rel in reg.get("releases") or []:
        slug = str(rel["slug"])
        old = (prev.get("releases") or {}).get(slug) or {}
        path = out / f"backfill_fredrel_{slug}.jsonl.gz"
        if old.get("fetched") == today.isoformat() and path.exists():
            rep["releases"][slug] = old
            continue
        r: dict[str, Any] = {**old, "rid": int(rel["rid"]), "title": rel["title"]}
        rep["releases"][slug] = r
        if not key:
            r["status"] = "UNMEASURED: no FRED key in the environment"
            continue
        if stopped:
            r["status"] = f"UNMEASURED: FRED answered HTTP {stopped} today; not asked again"
            continue
        base = {"release_id": int(rel["rid"]), "api_key": key, "file_type": "json"}
        try:
            st, doc = get(f"{API}/release?{urllib.parse.urlencode(base)}")
            rep["requests"] += 1
            if st in HARD_STOP:
                stopped = int(st or 0)
                r["status"] = f"UNMEASURED: HTTP {stopped}"
                continue
            name = str(((doc or {}).get("releases") or [{}])[0].get("name") or "")
            r["fred_name"] = name
            if str(rel["name_contains"]).lower() not in name.lower():
                r["status"] = "UNMEASURED: FRED's name for this id is not the release expected"
                continue
            st, doc = get(f"{API}/release/dates?" + urllib.parse.urlencode(
                {**base, "include_release_dates_with_no_data": "true", "limit": 10000,
                 "sort_order": "asc"}))
            rep["requests"] += 1
            if st in HARD_STOP:
                stopped = int(st or 0)
                r["status"] = f"UNMEASURED: HTTP {stopped}"
                continue
            dates = [str(x.get("date")) for x in (doc or {}).get("release_dates") or []]
        except Exception as exc:                      # the URL holds the key: type name only
            r["status"] = f"UNMEASURED: {type(exc).__name__}"
            continue
        rows, drops = event_rows(rel, dates, today)
        if not rows:
            r["status"] = f"UNMEASURED: no usable dates (HTTP {st})"
            continue
        out.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            fh.write("\n".join(json.dumps(x, sort_keys=True) for x in rows) + "\n")
        _replace(tmp, path)
        r.update({"status": "ok", "fetched": today.isoformat(), "rows": len(rows),
                  "scheduled_ahead": sum(1 for x in rows if x["scheduled"]),
                  "first": rows[0]["event_date"], "last": rows[-1]["event_date"],
                  "dropped": drops, "file": path.name})
    if stopped:
        rep["hard_stop"], rep["hard_stop_day"] = stopped, today.isoformat()
    rep["rows_total"] = sum(int(x.get("rows") or 0) for x in rep["releases"].values()
                            if x.get("status") == "ok")
    rep["unmeasured"] = sorted(s for s, x in rep["releases"].items() if x.get("status") != "ok")
    _write_json(report, rep)
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true", help="one pass (the default)")
    ap.parse_args(argv)
    rep = refresh()
    print(json.dumps({"rows_total": rep["rows_total"], "requests": rep["requests"],
                      "unmeasured": rep["unmeasured"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
