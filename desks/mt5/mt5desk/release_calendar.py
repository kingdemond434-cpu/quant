"""Scheduled release instants by event type: ONE reader for the atlas and the family it feeds.

The leadership atlas (`side_channels/leadership_atlas_miner.py`) measures who moves first on each
release type; `family_release_lead_lag` trades that claim. If the two read different calendars,
or classified a release differently, the Judge would test a different event set than the one the
atlas measured -- so both import `release_instants` from here and nowhere else.

WHICH ROWS ARE INSTANTS (Auditor HOLD on #1146, SF3). Only a row whose `event_date` carries a
clock time AND a zone is an instant. A date-only or naive stamp is a DAY, and pinning it to
midnight would invent a release time. Rows from `alfred_first_release` are excluded too: ALFRED's
realtime_start is the day ALFRED loaded the print, which can be a day after the release, so it
dates a vintage, not the moment the market learned the number.

Sources, both scheduled in advance (so reading them at any time is point-in-time):
  * `data/calendar_backfill/*.jsonl.gz` -- release instants written by the futures_state leg
    (official publishers; ALFRED rows skipped as above);
  * `data/intelligence/ff_calendar_vintage/*` -- the calendar miner's vintages (title, currency,
    `event_date` with zone).
"""
from __future__ import annotations

import gzip
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
CALENDAR_BACKFILL = _DESK / "data" / "calendar_backfill"
FF_VINTAGES = _DESK / "data" / "intelligence" / "ff_calendar_vintage"

#: Release title / series -> the event type. First match wins; an unmatched release keys on its
#: own series id (or title), so nothing is dropped for want of a name.
EVENT_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"payems|nonfarm|non-farm|payroll", "US_NFP"), (r"cpilfe|core cpi", "US_CORE_CPI"),
    (r"cpiaucsl|\bcpi\b", "US_CPI"), (r"pcepi|\bpce\b", "US_PCE"),
    (r"icsa|jobless", "US_CLAIMS"), (r"rsafs|retail sales", "US_RETAIL"),
    (r"unrate|unemployment rate", "US_UNEMPLOYMENT"), (r"jtsjol|jolts", "US_JOLTS"),
    (r"indpro|industrial production", "US_INDPRO"),
    (r"fomc|federal funds rate|fredrel_101", "FOMC_Statement"),
    (r"\bppi\b|fredrel_46", "US_PPI"), (r"\bgdp\b|fredrel_53", "US_GDP"),
    (r"boj|bank of japan", "BOJ_Statement"), (r"boe|bank of england|bank rate", "BOE_Statement"),
    (r"ecb|main refinancing", "ECB_Statement"), (r"natural gas storage|eia", "EIA_Gas_Storage"),
    (r"export sales|usda", "USDA_Export_Sales"), (r"h\.?4\.?1|net liquidity", "Fed_H41"),
    (r"\btic\b|long-term securities", "US_TIC"),
)

#: Sources whose stamp is not the release instant (see the module note).
EXCLUDED_SOURCES = ("alfred_first_release",)
_HAS_CLOCK = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_HAS_ZONE = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def classify_event(title: str, series: str = "") -> str:
    text = f"{title} {series}".lower()
    for pat, et in EVENT_PATTERNS:
        if re.search(pat, text):
            return et
    return re.sub(r"[^A-Za-z0-9]+", "_", series or title).strip("_").upper() or "UNKNOWN"


def instant_of(raw: Any) -> pd.Timestamp | None:
    """A UTC instant from an `event_date`, or None for a date-only or naive stamp."""
    if isinstance(raw, pd.Timestamp):
        return raw.tz_convert("UTC") if raw.tzinfo is not None else None
    s = str(raw or "").strip()
    if not _HAS_CLOCK.search(s) or not _HAS_ZONE.search(s):
        return None
    try:
        t = pd.Timestamp(s)
    except (TypeError, ValueError):
        return None
    if pd.isna(t) or t.tzinfo is None:
        return None
    return t.tz_convert("UTC")


def _rows(path: Path) -> list[dict[str, Any]]:
    try:
        if path.name.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = path.read_text(encoding="utf-8")
    except (OSError, ValueError, EOFError):
        return []
    try:
        doc = json.loads(text)
        rows = doc if isinstance(doc, list) else (doc or {}).get("rows", [])
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except ValueError:
        pass
    out = []
    for ln in text.splitlines():
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def calendar_events(root: Path | None = None, vintages: Path | None = None,
                    counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    """Every held release instant, de-duplicated on (type, instant), oldest first.

    `counts` (optional) receives what was skipped and why, so a thinner calendar is never silent.
    """
    c = counts if counts is not None else {}
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    files: list[Path] = []
    for d, pat in ((root or CALENDAR_BACKFILL, "*.jsonl.gz"), (vintages or FF_VINTAGES, "*.json*")):
        if d.exists():
            files.extend(sorted(d.glob(pat)))
    for f in files:
        for r in _rows(f):
            src = str(r.get("source") or "")
            if src in EXCLUDED_SOURCES or "alfred" in str(r.get("instant_basis") or ""):
                c["skipped_alfred"] = c.get("skipped_alfred", 0) + 1
                continue
            t = instant_of(r.get("event_date"))
            if t is None:
                c["skipped_not_an_instant"] = c.get("skipped_not_an_instant", 0) + 1
                continue
            et = classify_event(str(r.get("title") or ""), str(r.get("series") or ""))
            seen.setdefault((et, t.isoformat()), {"event_type": et, "time": t,
                                                  "source": src or f.name})
    return sorted(seen.values(), key=lambda e: e["time"])


def release_instants(event_type: str, root: Path | None = None,
                     vintages: Path | None = None) -> list[pd.Timestamp]:
    """The UTC instants of one event type, oldest first."""
    return [e["time"] for e in calendar_events(root, vintages) if e["event_type"] == event_type]
