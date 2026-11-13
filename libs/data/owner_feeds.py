"""THE PUBLIC-DOMAIN OWNERS' OWN FEEDS -- the fitted macro inputs FRED used to carry, read from the
executive agency that publishes them (coordinator ruling on FRED ToU prohibition (j), 2026-10-07).

FRED/ALFRED may no longer be an input to any fitted model (`libs.data.terms_hold` holds every
`fred:`/`alfred:` id from the gauntlet). The series the desk fits on are works of the United States
Government (17 U.S.C. 105), so they are read where the government publishes them:

    treasury   home.treasury.gov daily PAR yield curve CSV (3m/2y/5y/10y/30y -> DGS3MO DGS2 DGS5
               DGS10 DGS30) and daily REAL (TIPS) yield curve CSV (5y/10y -> DFII5 DFII10). No key.
               T10Y2Y = DGS10 - DGS2, T5YIE = DGS5 - DFII5, T10YIE = DGS10 - DFII10 are computed
               here from those (FRED's own definitions of the three).
    bls        api.bls.gov v2: CPI-U all items, seasonally adjusted CUSR0000SA0 (the series FRED
               republishes as CPIAUCSL) and not seasonally adjusted CUUR0000SA0 (never revised).
               Key: BLS_API_KEY (registry, env or data/secrets/bls.json).
    eia        api.eia.gov v2 seriesid: the Weekly Petroleum Status Report headline stocks
               WCESTUS1 WCSSTUS1 WGTSTUS1 WDISTUS1 and refinery utilisation WPULEUS3.
               Key: EIA_API_KEY (registry, env or data/secrets/eia.json).

HELD, NOT FETCHED: BEA (PCE) -- no BEA key is held and BEA's terms are unquoted; the Fed board's
H.10 dollar index and G.19 -- the Board's site terms are unquoted. Both stay out of every fitted
model until a quoted basis exists; they are named in the archive's `held` block, never zero.

THE ARCHIVE (`data/owner_macro.json`, box-local, gitignored) has the shape of `data/fred_macro.json`
so a reader of `r[0], r[1]` reads it unchanged, plus a third field per point:

    {"series": {"DGS10": [["2026-10-06", 4.12, "<first_seen ISO UTC>"], ...], ...},
     "source_ids": {"DGS10": "treasury:DGS10", ...}, "feeds": {...status...}, "held": {...}}

`first_seen` is the instant this desk first held the point. A point's AVAILABLE TIME is the
EARLIER of that and the owner's declared publication instant (`declared_available`): the first
is a measured upper bound (the desk held it then), the second a conservative calendar bound for
history the desk never watched arrive.

LIVE BEHAVIOUR IS UNMEASURED until the box runs it: the cloud container cannot reach any of the
three hosts, so the parsers are built against the documented formats and tested on fixtures.
"""
from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "data" / "owner_macro.json"
ET = ZoneInfo("America/New_York")
UNMEASURED = "UNMEASURED"

TREASURY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
                "daily-treasury-rates.csv/{year}/all?type={kind}&field_tdr_date_value={year}"
                "&page&_format=csv")
TREASURY_NOMINAL_KIND = "daily_treasury_yield_curve"
TREASURY_REAL_KIND = "daily_treasury_real_yield_curve"
#: Treasury CSV column (lower-cased, spaces collapsed) -> the desk's series name.
TREASURY_NOMINAL: dict[str, str] = {"3 mo": "DGS3MO", "2 yr": "DGS2", "5 yr": "DGS5",
                                    "10 yr": "DGS10", "30 yr": "DGS30"}
TREASURY_REAL: dict[str, str] = {"5 yr": "DFII5", "10 yr": "DFII10"}
#: Computed here: name -> (minuend, subtrahend).
TREASURY_DERIVED: dict[str, tuple[str, str]] = {"T10Y2Y": ("DGS10", "DGS2"),
                                                "T5YIE": ("DGS5", "DFII5"),
                                                "T10YIE": ("DGS10", "DFII10")}
#: The first year fetched on an empty archive: the latent-state filter needs ~4 years of trading
#: days before its first contract, and FRED's collector held ~11.5.
TREASURY_FIRST_YEAR = 2014

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SERIES = ("CUSR0000SA0", "CUUR0000SA0")
#: BLS v2 with a registration key serves at most 20 years per request.
BLS_MAX_YEARS = 20
BLS_KEY_NAMES = ("BLS_API_KEY", "BLS_KEY", "BLS_REGISTRATION_KEY")

EIA_URL = "https://api.eia.gov/v2/seriesid/PET.{series}.W"
EIA_SERIES = ("WCESTUS1", "WCSSTUS1", "WGTSTUS1", "WDISTUS1", "WPULEUS3")
EIA_KEY_NAMES = ("EIA_API_KEY", "EIA_KEY")

PROVIDER: dict[str, str] = {
    **dict.fromkeys((*TREASURY_NOMINAL.values(), *TREASURY_REAL.values(), *TREASURY_DERIVED),
                    "treasury"),
    **dict.fromkeys(BLS_SERIES, "bls"),
    **dict.fromkeys(EIA_SERIES, "eia"),
}

#: Owners with no admitted basis: named, never fetched, never fitted.
HELD: dict[str, str] = {
    "bea:PCEPI": "BEA PCE price index: no BEA API key is held and BEA's terms are unquoted",
    "frb:DTWEXBGS": "Fed board H.10 broad dollar index: the Board's site terms are unquoted",
    "frb:G19": "Fed board G.19 consumer credit: the Board's site terms are unquoted",
}

#: CPI release instants that the declared lag below would place too EARLY: the 2025 lapse in
#: appropriations moved the September 2025 print to 24 October and the November print to
#: 18 December (October 2025 was never published). Reference month -> release instant (ET).
#: Owed a check against BLS's own schedule page on the box.
BLS_RELEASE_OVERRIDES: dict[str, str] = {"2025-09": "2025-10-24T08:30",
                                         "2025-11": "2025-12-18T08:30"}
#: Reference month's first day -> knowable, for a CPI print the desk did not watch arrive. The
#: same conservative lag `macro.latent_states` declared for CPIAUCSL (BLS publishes ~10-15 days
#: after the month ends, 08:30 ET).
BLS_LAG_D = 45


def source_id(sid: str) -> str:
    """The gauntlet id of a series in this archive: '<owner>:<series>'."""
    return f"{PROVIDER[sid]}:{sid}"


# ============================================================================== declared clocks
def declared_available(sid: str, day: str) -> datetime:
    """The owner's conservative publication instant for the point dated `day`.

    treasury  the next calendar day 09:00 ET (Treasury posts the curve the same evening; this
              bound can only arrive late)
    bls       the overridden release instant, else the reference month's first day + 45 days
              at 13:30 UTC
    eia       the week-end (Friday) + 6 days at 12:00 ET: the Thursday-noon holiday stamp, later
              than the regular Wednesday 10:30 ET release (`macro.physical_state` keeps the full
              holiday calendar and is what the inventory engine reads)
    """
    d = date.fromisoformat(str(day)[:10])
    owner = PROVIDER.get(sid, "")
    if owner == "bls":
        over = BLS_RELEASE_OVERRIDES.get(f"{d.year:04d}-{d.month:02d}")
        if over:
            return datetime.fromisoformat(over).replace(tzinfo=ET).astimezone(UTC)
        return datetime(d.year, d.month, 1, 13, 30, tzinfo=UTC) + timedelta(days=BLS_LAG_D)
    if owner == "eia":
        t = d + timedelta(days=6)
        return datetime(t.year, t.month, t.day, 12, 0, tzinfo=ET).astimezone(UTC)
    t = d + timedelta(days=1)
    return datetime(t.year, t.month, t.day, 9, 0, tzinfo=ET).astimezone(UTC)


def _ts(text: Any) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return got if got.tzinfo else got.replace(tzinfo=UTC)


def available(sid: str, row: Sequence[Any]) -> datetime:
    """min(first_seen, declared): the earliest instant the point is PROVABLY knowable."""
    declared = declared_available(sid, str(row[0]))
    seen = _ts(row[2]) if len(row) > 2 else None
    return min(declared, seen) if seen is not None else declared


# ============================================================================== parsers
def _num(text: Any) -> float | None:
    try:
        v = float(str(text).strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _iso(text: str) -> str | None:
    t = str(text or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(t, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def parse_treasury_csv(text: str, columns: Mapping[str, str]) -> dict[str, dict[str, float]]:
    """{series: {date: value}} from one Treasury yield-curve CSV. Columns are matched by name,
    case- and spacing-insensitively ('10 Yr', '10 YR'); a blank or 'N/A' cell is absent."""
    out: dict[str, dict[str, float]] = {sid: {} for sid in columns.values()}
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if not header:
        return out
    norm = [" ".join(h.strip().lower().split()) for h in header]
    if "date" not in norm:
        return out
    di = norm.index("date")
    cols = {i: columns[h] for i, h in enumerate(norm) if h in columns}
    for row in reader:
        if len(row) <= di:
            continue
        day = _iso(row[di])
        if day is None:
            continue
        for i, sid in cols.items():
            v = _num(row[i]) if i < len(row) else None
            if v is not None:
                out[sid][day] = v
    return out


def bls_payload(series: Sequence[str], start: int, end: int, key: str | None) -> dict[str, Any]:
    body: dict[str, Any] = {"seriesid": list(series), "startyear": str(start),
                            "endyear": str(end)}
    if key:
        body["registrationkey"] = key
    return body


def parse_bls(doc: Any) -> tuple[dict[str, dict[str, float]], str]:
    """({series: {YYYY-MM-01: value}}, status). Monthly periods M01..M12 only (M13 is the annual
    average); a '-' value (a month BLS did not publish) is absent, never zero."""
    out: dict[str, dict[str, float]] = {}
    if not isinstance(doc, dict):
        return out, "unparseable response"
    status = str(doc.get("status") or "")
    for s in ((doc.get("Results") or {}).get("series") or []):
        if not isinstance(s, dict):
            continue
        sid = str(s.get("seriesID") or "")
        rows: dict[str, float] = {}
        for r in s.get("data") or []:
            per = str((r or {}).get("period") or "")
            if not (per.startswith("M") and per[1:].isdigit() and 1 <= int(per[1:]) <= 12):
                continue
            v = _num((r or {}).get("value"))
            try:
                y = int(str(r.get("year")))
            except (TypeError, ValueError):
                continue
            if v is not None:
                rows[f"{y:04d}-{int(per[1:]):02d}-01"] = v
        if sid:
            out[sid] = rows
    return out, status


def parse_eia(doc: Any) -> dict[str, float]:
    """{week-end date: value} from an api.eia.gov v2 seriesid response."""
    out: dict[str, float] = {}
    data = ((doc or {}).get("response") or {}).get("data") if isinstance(doc, dict) else None
    for r in data or []:
        if not isinstance(r, dict):
            continue
        day = _iso(str(r.get("period") or ""))
        v = _num(r.get("value"))
        if day is not None and v is not None:
            out[day] = v
    return out


def derive(values: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    """The three Treasury spreads, on the dates both legs carry."""
    out: dict[str, dict[str, float]] = {}
    for name, (a, b) in TREASURY_DERIVED.items():
        va, vb = values.get(a) or {}, values.get(b) or {}
        out[name] = {d: round(va[d] - vb[d], 6) for d in va if d in vb}
    return out


# ============================================================================== the archive
def merge(prev: Sequence[Sequence[Any]] | None, fresh: Mapping[str, float], seen_at: str
          ) -> list[list[Any]]:
    """Rows [date, value, first_seen]: a date keeps its first_seen across runs (the owner's
    revision of a value is the vintage store's business, not a new arrival); new dates are
    stamped `seen_at`; dates the fresh fetch did not return are kept (absent is not deleted)."""
    seen: dict[str, str] = {}
    vals: dict[str, float] = {}
    for r in prev or []:
        try:
            d, v = str(r[0])[:10], float(r[1])
        except (TypeError, ValueError, IndexError):
            continue
        if math.isfinite(v):
            vals[d] = v
            seen[d] = str(r[2]) if len(r) > 2 and r[2] else seen_at
    for d, v in fresh.items():
        vals[d] = float(v)
        seen.setdefault(d, seen_at)
    return [[d, vals[d], seen[d]] for d in sorted(vals)]


def load_archive(path: Path | None = None) -> dict[str, list[tuple[str, float, str]]]:
    """{series: [(date, value, first_seen)]} sorted; {} when the archive is absent (UNMEASURED,
    never an empty series read as zero)."""
    try:
        doc = json.loads(Path(path or ARCHIVE).read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[str, list[tuple[str, float, str]]] = {}
    for sid, rows in ((doc or {}).get("series") or {}).items() if isinstance(doc, dict) else ():
        if not isinstance(rows, list):
            continue
        clean = []
        for r in rows:
            try:
                v = float(r[1])
            except (TypeError, ValueError, IndexError):
                continue
            if math.isfinite(v):
                clean.append((str(r[0])[:10], v, str(r[2]) if len(r) > 2 and r[2] else ""))
        if clean:
            out[str(sid)] = sorted(clean)
    return out


def observations(series: Mapping[str, Sequence[Sequence[Any]]], sid: str
                 ) -> list[tuple[datetime, float]]:
    """[(available instant, value)] for one series of the archive."""
    out = []
    for r in series.get(sid) or []:
        try:
            out.append((available(sid, r), float(r[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return out


__all__ = ["ARCHIVE", "BLS_SERIES", "EIA_SERIES", "HELD", "PROVIDER", "TREASURY_DERIVED",
           "TREASURY_NOMINAL", "TREASURY_REAL", "available", "declared_available", "derive",
           "load_archive", "merge", "observations", "parse_bls", "parse_eia",
           "parse_treasury_csv", "source_id"]
