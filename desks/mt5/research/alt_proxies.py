"""FREE PUBLIC PROXIES FOR POS / CARD / RECEIPT / LOCATION / SATELLITE DATA, AS PIT SERIES.

WHAT THIS IS. Ten public (keyless or free-key) alternative-data sources, each parsed into a
point-in-time series and published through the doors the desk already has, so the same series
feeds all three uses at once:

  direct_cells     the series' own surprise as an `exogenous_conditioner` cell on the instruments
                   it is mapped to. A cell is donated through `proposer_common.donate` (the one
                   stamped, lane-filtered, pre-registered door) ONLY after the box measured it
                   against a shifted-release placebo (`libs.research.release_gain`) and every
                   cell tested this pass is charged as a trial.
  indirect_cells   the series as a CONDITIONING variable: (a) every series lands in
                   `data/axes/alt_<id>.json`, which `alpha_dsl.FieldCatalogue`, `world_model` and
                   therefore `representation_forge` (surprise / pace / z / revision transforms)
                   read unchanged; (b) conditioned variants of the desk's certified parents
                   ("session_range_breakout on AUDUSD only while KR export pace > 0") are donated
                   with `params.conditioner = "alt:<series>:<column>:<op>:<threshold>"`, which
                   `mt5desk.cell_modifiers` now applies in the gauntlet and the forward clock.
  allocation_intel `reports/ALT_PROXIES_ALLOCATION_INTEL.json`: per instrument, per day, the
                   PIT-available state of every mapped series. A READ-ONLY artifact; the
                   allocator is not edited and nothing here sizes anything.

WHAT THE DESK ALREADY HAD, SO NOTHING IS FETCHED TWICE. RSAFS (headline retail) comes from
`fetch_alfred` with vintages, so the Census leg here reads only the ex-autos cuts. `kr_exports_20d`,
`nasa_firms`, `sse_freight_indices`, `copernicus_s5p` and `baidu_index` are rows in
`asia_sources.json` whose collector reads a landing page (or, for FIRMS, the bare API root with no
key and no area): bytes, never a series. This organ builds the series those rows name. The SGE
premium is FETCHED by `fetch_sge_premium`; it is only READ here, from its own parquet.

POINT IN TIME, THREE STAMPS PER POINT. `event_time` is the period described; `available_time` is
the release instant -- parsed from the source's own page when it prints one, else the source's
release calendar pushed LATE (a rule that can only be late: early invents edge, late only costs
it), via `libs.data.pit_stamp.available_at`; `first_seen_at` is when this box first read the value
(the vintage), kept append-only with the first value seen, so a revision is a second vintage and
never an overwrite. A monthly print is visible only from its release instant.

LIVE YIELD IS UNMEASURED UNTIL THE TRADING BOX RUNS THIS. The fetchers were built against small
fixtures shaped like each publisher's page (tests/fixtures/alt_proxies); the cloud container that
wrote them cannot reach these hosts. A source whose key is absent is BLOCKED_ON_KEY:<ENV>, a named
state, never a silent skip; no key is ever printed, logged or vaulted (the vaulted URL is redacted).

    python desks/mt5/research/alt_proxies.py --once [--budget-s 300] [--dry-run]
    python desks/mt5/research/alt_proxies.py --once --no-fetch --fixtures tests/fixtures/alt_proxies
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import html as _html
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SOURCE = "alt_proxies"
INDIRECT_SOURCE = "alt_proxies_indirect"
UNMEASURED = "UNMEASURED"
UA = "quant-desk-alt-proxies/1.0 (+public statistics research)"
TIMEOUT = 30.0
MAX_BYTES = 16 * 1024 * 1024
#: The prefix a conditioner spec carries; `mt5desk.cell_modifiers` applies only this form.
CONDITIONER_PREFIX = "alt:"
#: Points a series needs before its surprise has a prior at all.
EXPECTATION_N = 6
#: A page's publication stamp is believed only within this many days after the period.
MAX_PUB_LAG_D = 70
SURPRISE_SD_MIN = 8
#: Post-release window the gain test reads, in H1 bars (~5 trading days).
HORIZON_BARS = 120
#: Conditioned variants minted per pass. The cursor rotates, so every (parent, series) pair is
#: reached across passes; this is a per-pass compute share, and what it leaves is owed, not refused.
INDIRECT_PER_PASS = 24
#: Parents per instrument read from the certified survivors.
PARENTS_PER_SYMBOL = 3
#: A component older than this (days since its release) no longer describes "now" in the
#: allocation-intel artifact. Keyed by cadence.
STALE_DAYS = {"daily": 10, "weekly": 21, "10-daily": 25, "monthly": 45}


@dataclass(frozen=True)
class Paths:
    desk: Path

    @property
    def state(self) -> Path:
        return self.desk / "data" / "alt_proxies" / "state.json"

    @property
    def obs_dir(self) -> Path:
        return self.desk / "data" / "alt_proxies" / "obs"

    @property
    def vault(self) -> Path:
        return self.desk / "data" / "lake" / "vault"

    @property
    def axes(self) -> Path:
        return self.desk / "data" / "axes"

    @property
    def series(self) -> Path:
        return self.desk / "data" / "lake" / "series"

    @property
    def universe(self) -> Path:
        return self.desk / "data" / "universe"

    @property
    def report(self) -> Path:
        return self.desk / "reports" / "ALT_PROXIES.json"

    @property
    def allocation_intel(self) -> Path:
        return self.desk / "reports" / "ALT_PROXIES_ALLOCATION_INTEL.json"

    @property
    def survivors(self) -> Path:
        return self.desk / "reports" / "UNIVERSAL_SURVIVORS.json"

    @property
    def sge_premium(self) -> Path:
        return self.desk / "data" / "lake" / "sge_premium.parquet"


DEFAULT_PATHS = Paths(DESK)


# ============================================================================ observations
@dataclass(frozen=True)
class Obs:
    """One parsed value: the period it describes and, when the page printed it, when it was
    published. Nothing else is inferred at parse time."""
    series: str
    period: date
    value: float
    published_at: datetime | None = None


@dataclass
class Ctx:
    """What a parser may know besides the bytes: which request part it is, and its date span."""
    part: str = ""
    start: date | None = None
    end: date | None = None
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _utc(y: int, m: int, d: int, hh: int = 0, mm: int = 0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


def _month_end(y: int, m: int) -> date:
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return nxt - timedelta(days=1)


def _roll_weekday(t: datetime) -> datetime:
    while t.weekday() >= 5:
        t += timedelta(days=1)
    return t


def _text(body: bytes) -> str:
    """Tags out, entities decoded, whitespace collapsed. Enough for a press release."""
    raw = body.decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", _html.unescape(raw)).strip()


def _num(s: str) -> float | None:
    try:
        v = float(str(s).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ============================================================================ release rules
def _lag_rule(lag_days: int, hour: int = 0, weekday: bool = False) -> Callable[[date], datetime]:
    """period_end + lag through `pit_stamp.available_at`, the desk's one publication-lag helper."""
    def rule(period: date) -> datetime:
        try:
            from libs.data.pit_stamp import available_at
            t = available_at(period, lag_days)
        except Exception:                                      # pragma: no cover - import guard
            t = _utc(period.year, period.month, period.day) + timedelta(days=lag_days)
        t = t.replace(hour=hour, minute=0, second=0, microsecond=0)
        return _roll_weekday(t) if weekday else t
    return rule


def rule_tsa(period: date) -> datetime:
    """TSA posts yesterday's count on weekday mornings (~09:00 ET). Fri/Sat/Sun counts appear
    Monday. 16:00 UTC is after 09:00 ET in both daylight regimes."""
    t = _utc(period.year, period.month, period.day, 16) + timedelta(days=1)
    return _roll_weekday(t)


def rule_jnto(period: date) -> datetime:
    """JNTO's monthly estimate lands on the third Wednesday of the following month, 16:15 JST.
    Fallback: that Wednesday + 1 day at 00:00 UTC (late on purpose)."""
    y, m = (period.year + (period.month == 12), 1 if period.month == 12 else period.month + 1)
    d = date(y, m, 15)
    while d.weekday() != 2:
        d += timedelta(days=1)
    return _utc(d.year, d.month, d.day) + timedelta(days=1)


def rule_tokyo_cpi(period: date) -> datetime:
    """Tokyo ku-area CPI for month M prints on the last Friday of M at 08:30 JST (23:30 UTC the
    Thursday). 00:00 UTC Friday is after it; an earlier release only makes this late."""
    d = _month_end(period.year, period.month)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return _utc(d.year, d.month, d.day)


# ============================================================================ parsers
_KR_HEAD = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*1\s*일?\s*[~∼\-–]\s*(\d{1,2})\s*일")  # noqa: RUF001
_KR_EXPORT = re.compile(r"수출(?:액)?\s*[은는]?\s*([\d,.]+)\s*억\s*달러")
_KR_YOY = re.compile(r"전년\s*동기\s*대비\s*([\d.]+)\s*%\s*(증가|감소)")
_KR_DAILY = re.compile(r"일평균\s*수출(?:액)?[^%]{0,40}?([\d.]+)\s*%\s*(증가|감소)")
_KR_SEMI = re.compile(r"반도체\s*\(\s*([△▲+\-]?)\s*([\d.]+)\s*%\s*\)")
_KR_DATE = re.compile(r"(?:등록일|작성일|게시일|배포일시?)\s*[:：]?\s*"  # noqa: RUF001
                      r"(\d{4})[.\-/]\s*(\d{1,2})[.\-/]\s*(\d{1,2})")


def _signed(v: str, word: str) -> float | None:
    x = _num(v)
    return None if x is None else (-x if word in ("감소", "減", "減少") else x)


def parse_kr_exports(body: bytes, ctx: Ctx) -> list[Obs]:
    """Korea Customs Service 1-10 / 1-20 day export prints (Korean press release text).

    `△` is the Korean statistical minus. The release instant is the page's own registration date
    at 09:00 KST (00:00 UTC); a block with no date falls back to the calendar rule."""
    text = _text(body)
    heads = list(_KR_HEAD.finditer(text))
    # A release names its window in the title AND again in the body: consecutive mentions of the
    # same window are ONE release, so their text is joined before any field is read.
    blocks: list[tuple[tuple[int, int, int], str]] = []
    for i, h in enumerate(heads):
        key = (int(h.group(1)), int(h.group(2)), int(h.group(3)))
        seg = text[h.start(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        if blocks and blocks[-1][0] == key:
            blocks[-1] = (key, blocks[-1][1] + " " + seg)
        else:
            blocks.append((key, seg))
    out: list[Obs] = []
    for (y, m, dend), block in blocks:
        if not (1 <= m <= 12 and dend in (10, 20)):
            continue
        period = date(y, m, dend)
        pub: datetime | None = None
        dm = _KR_DATE.search(block)
        if dm:
            with contextlib.suppress(ValueError):
                pub = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        if pub is not None and pub.date() <= period:
            pub = None
        ex = _KR_EXPORT.search(block)
        if ex and (v := _num(ex.group(1))) is not None:
            out.append(Obs("exports_usd_bn", period, round(v / 10.0, 4), pub))
        yo = _KR_YOY.search(block)
        if yo and (v2 := _signed(yo.group(1), yo.group(2))) is not None:
            out.append(Obs("headline_yoy", period, v2, pub))
        da = _KR_DAILY.search(block)
        if da and (v3 := _signed(da.group(1), da.group(2))) is not None:
            out.append(Obs("daily_avg_yoy", period, v3, pub))
        se = _KR_SEMI.search(block)
        if se and (v4 := _num(se.group(2))) is not None:
            out.append(Obs("semis_yoy", period, -v4 if se.group(1) in ("△", "-") else v4, pub))
    return out


_TSA_ROW = re.compile(r"<tr[^>]*>\s*<td[^>]*>\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*</td>\s*"
                      r"<td[^>]*>\s*([\d,]+)\s*</td>", re.I)


def parse_tsa(body: bytes, ctx: Ctx) -> list[Obs]:
    """TSA checkpoint travel numbers: an HTML table of (date, travellers). A multi-year table
    carries the current year in its first number column, which is the only one read."""
    out: list[Obs] = []
    for mo, d, y, n in _TSA_ROW.findall(body.decode("utf-8", errors="replace")):
        v = _num(n)
        with contextlib.suppress(ValueError):
            if v is not None:
                out.append(Obs("travelers", date(int(y), int(mo), int(d)), v))
    return out


#: Census MARTS category codes read here. The headline (44X72) is NOT read: RSAFS already comes
#: from ALFRED with its vintages. Codes to confirm on the box against the API's own metadata.
MARTS_CATEGORIES = {"44Y72": "ex_autos", "44Z72": "ex_autos_gas"}


def parse_census_marts(body: bytes, ctx: Ctx) -> list[Obs]:
    """Census EITS time-series API (JSON array of arrays, header first). Sales, SA, level."""
    try:
        rows = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(rows[0], list):
        return []
    head = [str(h) for h in rows[0]]
    col = {h: i for i, h in enumerate(head)}
    need = ("cell_value", "data_type_code", "category_code", "time")
    if any(k not in col for k in need):
        return []
    out: list[Obs] = []
    for r in rows[1:]:
        if not isinstance(r, list) or len(r) < len(head):
            continue
        if str(r[col["data_type_code"]]) != "SM":
            continue
        if "seasonally_adj" in col and str(r[col["seasonally_adj"]]).lower() not in ("yes", "true"):
            continue
        name = MARTS_CATEGORIES.get(str(r[col["category_code"]]))
        v = _num(str(r[col["cell_value"]]))
        mt = re.match(r"^(\d{4})-(\d{2})$", str(r[col["time"]]))
        if name and v is not None and mt:
            out.append(Obs(f"sales_{name}", _month_end(int(mt.group(1)), int(mt.group(2))), v))
    return out


_JNTO_BLOCK = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月の?訪日外客数"
                         r"(?:[（(][^）)]{0,8}[）)])?は\s*"  # noqa: RUF001
                         r"([\d,]+)\s*人[^。]{0,40}?前年同月比\s*([\d.]+)\s*%\s*(増|減)")
_JP_DATE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def parse_jnto(body: bytes, ctx: Ctx) -> list[Obs]:
    """JNTO monthly visitor-arrivals estimate (Japanese press release). The release instant is
    the first full date on the page later than the reference month, at 16:15 JST (07:15 UTC)."""
    text = _text(body)
    out: list[Obs] = []
    for mt in _JNTO_BLOCK.finditer(text):
        y, m = int(mt.group(1)), int(mt.group(2))
        if not 1 <= m <= 12:
            continue
        period = _month_end(y, m)
        pub = None
        for dm in _JP_DATE.finditer(text):
            with contextlib.suppress(ValueError):
                cand = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), 7, 15)
                if cand.date() > period:
                    pub = cand
                    break
        v = _num(mt.group(3))
        if v is not None:
            out.append(Obs("arrivals", period, v, pub))
        yoy = _num(mt.group(4))
        if yoy is not None:
            out.append(Obs("arrivals_yoy", period, -yoy if mt.group(5) == "減" else yoy, pub))
    return out


def parse_estat_cpi(body: bytes, ctx: Ctx) -> list[Obs]:
    """e-Stat getStatsData JSON. `@time` is YYYY00MMMM; the value is the year-on-year rate of
    the category/area the request filtered to. A non-zero RESULT.STATUS is an error, not data."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    root = (doc or {}).get("GET_STATS_DATA") if isinstance(doc, dict) else None
    if not isinstance(root, dict):
        return []
    status = str(((root.get("RESULT") or {}).get("STATUS")) or "0")
    if status not in ("0", "1"):
        return []
    values = (((root.get("STATISTICAL_DATA") or {}).get("DATA_INF") or {}).get("VALUE") or [])
    if isinstance(values, dict):
        values = [values]
    out: list[Obs] = []
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, dict):
            continue
        tcode = str(v.get("@time") or "")
        x = _num(str(v.get("$") or ""))
        if len(tcode) != 10 or x is None or not tcode[:4].isdigit():
            continue
        try:
            y, m = int(tcode[:4]), int(tcode[6:8])
        except ValueError:
            continue
        if 1 <= m <= 12:
            out.append(Obs("core_cpi_yoy", _month_end(y, m), x))
    return out


def parse_firms(body: bytes, ctx: Ctx) -> list[Obs]:
    """NASA FIRMS area CSV for ONE declared industrial footprint (`ctx.part`). Detections at
    nominal/high confidence only; every day of the requested span is emitted, a day with no
    detection as a measured 0 (the satellite passed; clouds make a 0 noisy, not missing)."""
    import csv
    text = body.decode("utf-8", errors="replace")
    if not text.lower().startswith("latitude"):
        return []
    counts: dict[date, float] = {}
    frp: dict[date, float] = {}
    for r in csv.DictReader(io.StringIO(text)):
        conf = str(r.get("confidence") or "").strip().lower()
        if conf in ("l", "low"):
            continue
        if conf.isdigit() and int(conf) < 30:
            continue
        try:
            d = date.fromisoformat(str(r.get("acq_date") or "")[:10])
        except ValueError:
            continue
        counts[d] = counts.get(d, 0.0) + 1.0
        f = _num(str(r.get("frp") or ""))
        frp[d] = frp.get(d, 0.0) + (f or 0.0)
    days = sorted(counts)
    if ctx.start is not None and ctx.end is not None:
        days = [ctx.start + timedelta(days=i) for i in range((ctx.end - ctx.start).days + 1)]
    part = ctx.part or "area"
    out: list[Obs] = []
    for d in days:
        out.append(Obs(f"{part}_count", d, counts.get(d, 0.0)))
        out.append(Obs(f"{part}_frp", d, round(frp.get(d, 0.0), 3)))
    return out


def _arcgis_rows(body: bytes) -> list[dict[str, Any]]:
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    feats = doc.get("features") if isinstance(doc, dict) else None
    return [f["attributes"] for f in feats or [] if isinstance(f, dict)
            and isinstance(f.get("attributes"), dict)]


def _arcgis_date(v: Any) -> date | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return datetime.fromtimestamp(float(v) / 1000.0, tz=UTC).date()
    with contextlib.suppress(ValueError):
        return date.fromisoformat(str(v)[:10])
    return None


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def parse_portwatch_ports(body: bytes, ctx: Ctx) -> list[Obs]:
    """IMF PortWatch Daily_Ports_Data: port calls per port per day (AIS-derived)."""
    out: list[Obs] = []
    for a in _arcgis_rows(body):
        d = _arcgis_date(a.get("date"))
        name = str(a.get("portname") or "")
        v = _num(str(a.get("portcalls") if a.get("portcalls") is not None else ""))
        if d and name and v is not None:
            out.append(Obs(f"{_slug(name)}_portcalls", d, v))
    return out


def parse_portwatch_chokepoints(body: bytes, ctx: Ctx) -> list[Obs]:
    """IMF PortWatch Daily_Chokepoints_Data: transits per chokepoint per day."""
    out: list[Obs] = []
    for a in _arcgis_rows(body):
        d = _arcgis_date(a.get("date"))
        name = str(a.get("portname") or "")
        v = _num(str(a.get("n_total") if a.get("n_total") is not None else ""))
        if d and name and v is not None:
            out.append(Obs(f"{_slug(name)}_transits", d, v))
    return out


_MONTHS = {m: i for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"), start=1)}
_PIB_POSTED = re.compile(r"Posted On:\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*"
                         r"(AM|PM)", re.I)
_PIB_MONTH = re.compile(r"\b(January|February|March|April|May|June|July|August|September|"
                        r"October|November|December)\s*,?\s*(\d{4})\b", re.I)
_PIB_METAL = re.compile(r"\b(gold|silver)\b[^.]{0,160}?(?:US\s*\$|USD)\s*([\d.]+)\s*billion",
                        re.I)


def parse_pib_trade(body: bytes, ctx: Ctx) -> list[Obs]:
    """India's monthly merchandise-trade press release on PIB: gold and silver import values.
    The release instant is PIB's own 'Posted On' stamp in IST."""
    text = _text(body)
    pub = None
    pm = _PIB_POSTED.search(text)
    if pm:
        mon = next((i for n, i in _MONTHS.items() if n[:3] == pm.group(2).lower()), 0)
        hh = int(pm.group(4)) % 12 + (12 if pm.group(6).upper() == "PM" else 0)
        with contextlib.suppress(ValueError):
            if mon:
                pub = (datetime(int(pm.group(3)), mon, int(pm.group(1)), hh, int(pm.group(5)),
                                tzinfo=UTC) - timedelta(hours=5, minutes=30))
    mm = _PIB_MONTH.search(text)
    if not mm:
        return []
    period = _month_end(int(mm.group(2)), _MONTHS[mm.group(1).lower()])
    if pub is not None and pub.date() <= period:
        pub = None
    out: list[Obs] = []
    seen: set[str] = set()
    for metal, v in _PIB_METAL.findall(text):
        key = metal.lower()
        x = _num(v)
        if key in seen or x is None:
            continue
        seen.add(key)
        out.append(Obs(f"{key}_imports_usd_bn", period, x, pub))
    return out


def read_sge_premium(paths: Paths) -> list[Obs]:
    """The SGE premium `fetch_sge_premium` already records -- READ, never re-fetched."""
    p = paths.sge_premium
    if not p.exists():
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:
        return []
    if "premium_pct" not in df.columns:
        return []
    out: list[Obs] = []
    for idx, v in df["premium_pct"].items():
        x = _num(str(v))
        with contextlib.suppress(Exception):
            if x is not None:
                out.append(Obs("premium_pct", pd.Timestamp(str(idx)).date(), x))
    return out


# ============================================================================ the sources
@dataclass(frozen=True)
class Source:
    id: str
    name: str
    url: str
    region: str
    language: str
    cadence: str
    parse: Callable[[bytes, Ctx], list[Obs]] | None
    rule: Callable[[date], datetime]
    transform: str
    instruments: dict[str, int]
    signal_series: tuple[str, ...]
    mechanism: str
    payer: str
    constraint: str
    licence: str
    source_culture: str
    participant_structure: tuple[str, ...]
    failure_mode_hypothesis: str
    crowding_prior: str
    key_env: str | None = None
    series_instruments: dict[str, dict[str, int]] = field(default_factory=dict)
    note: str = ""

    def instruments_for(self, series: str) -> dict[str, int]:
        for prefix, m in self.series_instruments.items():
            if series.startswith(prefix):
                return m
        return self.instruments


#: Industrial footprints read by FIRMS. Bounding boxes (W,S,E,N) around steel, coke and smelting
#: clusters; a detection outside a box is discarded, never averaged in.
FIRMS_CLUSTERS: dict[str, tuple[float, float, float, float]] = {
    "tangshan_steel": (117.8, 39.3, 119.3, 40.2),
    "handan_steel": (113.8, 36.3, 114.8, 36.9),
    "shanxi_coke": (111.9, 37.0, 113.2, 38.1),
    "rizhao_linyi_steel": (118.3, 34.9, 119.7, 35.6),
    "baotou_steel_alu": (109.6, 40.4, 110.3, 40.8),
}
FIRMS_URL = ("https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{product}/{bbox}/{days}/"
             "{day}")
PORTWATCH_BASE = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
                  "{svc}/FeatureServer/0/query")
PORTS = ("Shanghai", "Ningbo-Zhoushan", "Busan", "Port Hedland", "Singapore")
CHOKEPOINTS = ("Strait of Hormuz", "Suez Canal", "Bab el-Mandeb Strait", "Malacca Strait")

SOURCES: tuple[Source, ...] = (
    Source(
        id="kr_exports_early", name="Korea Customs Service 1-10 / 1-20 day exports",
        url=os.environ.get("ALT_KR_EXPORTS_URL",
                           "https://www.customs.go.kr/kcs/na/ntt/selectNttList.do?mi=2891&bbsId=1362"),
        region="KR", language="ko", cadence="10-daily", parse=parse_kr_exports,
        rule=_lag_rule(2, 0, weekday=True), transform="given",
        instruments={"USDKRW": -1, "AUDUSD": 1, "XCUUSD": 1, "JPN225": 1, "NAS100": 1,
                     "CHINAH": 1, "TSMC": 1, "MicronTechnology": 1, "NVIDIA": 1, "AMD": 1},
        series_instruments={"semis_yoy": {"USDKRW": -1, "NAS100": 1, "TSMC": 1,
                                          "MicronTechnology": 1, "NVIDIA": 1, "AMD": 1}},
        signal_series=("daily_avg_yoy", "semis_yoy"),
        mechanism=("Korea's customs office prints exports for the first 10 and 20 days of the "
                   "month, weeks before any other country's monthly trade figure; semiconductor "
                   "exports are the global chip cycle read at the dock"),
        payer=("slow repricers of Asian trade and chip-cycle risk who wait for the monthly "
               "MOTIE/customs totals and the chipmakers' own guidance"),
        constraint=("institutional FX and equity books rebalance on month-end official data and "
                    "earnings calendars, not on a partial-month Korean press release"),
        licence=("Korea Customs Service public press releases (KOGL public-sector open licence, "
                 "attribution); no login, no key"),
        source_culture="KR/ko", participant_structure=("institutional", "physical_flow"),
        failure_mode_hypothesis=("fails when working-day and holiday shifts (Chuseok, Lunar New "
                                 "Year) distort a partial month, which does not coincide with "
                                 "US data-surprise regimes"),
        crowding_prior="medium",
        note=("asia_sources.json `kr_exports_20d` vaults the UNI-PASS landing page only; this "
              "is the parsed series. URL overridable with ALT_KR_EXPORTS_URL; route to confirm "
              "on the box")),
    Source(
        id="us_tsa_throughput", name="US TSA checkpoint travel numbers",
        url="https://www.tsa.gov/travel/passenger-volumes",
        region="US", language="en", cadence="daily", parse=parse_tsa, rule=rule_tsa,
        transform="yoy_daily",
        instruments={"US500": 1, "XTIUSD": 1, "Boeing": 1, "Booking": 1, "Airbnb": 1,
                     "Uber": 1},
        signal_series=("travelers",),
        mechanism=("daily airport screenings are a same-week count of discretionary travel "
                   "spending, published the next morning, weeks before airline or card data"),
        payer="travel-exposed equity and jet-fuel holders who price on quarterly reports",
        constraint="sell-side travel estimates move on earnings calendars, not daily counts",
        licence="US federal government work (public domain)",
        source_culture="US/en", participant_structure=("retail_heavy", "physical_flow"),
        failure_mode_hypothesis=("fails around holiday-date misalignment (Thanksgiving, Easter "
                                 "shifting against the 364-day comparison) and weather groundings"),
        crowding_prior="high"),
    Source(
        id="us_census_marts_ex_autos", name="US Census advance retail sales, ex-autos cuts",
        url=("https://api.census.gov/data/timeseries/eits/marts?get=cell_value,data_type_code,"
             "time_slot_id,category_code,seasonally_adj&time=from+2015"),
        region="US", language="en", cadence="monthly", parse=parse_census_marts,
        rule=_lag_rule(17, 13, weekday=True), transform="mom_monthly",
        instruments={"US500": 1, "USDJPY": 1, "EURUSD": -1, "XAUUSD": -1},
        signal_series=("sales_ex_autos_gas",),
        mechanism=("the receipts-based advance retail survey's ex-autos-and-gas cut is the "
                   "consumption input to GDP; its month-on-month change against its own run-rate "
                   "reprices the Fed path"),
        payer="rates and USD holders positioned on the prior consumption run-rate",
        constraint="policy-path positioning adjusts only at data releases",
        licence="US Census public API (public domain; keyless below the daily query limit)",
        source_culture="US/en", participant_structure=("institutional", "policy_driven"),
        failure_mode_hypothesis=("fails when the headline and control group disagree and when "
                                 "revisions to the prior month dominate the new print"),
        crowding_prior="high",
        note=("RSAFS headline already vintaged by fetch_alfred; only 44Y72/44Z72 read here. The "
              "API serves the CURRENT vintage, so backfilled rows are revised values "
              "(pit_quality=backfill)")),
    Source(
        id="jp_jnto_arrivals", name="JNTO monthly visitor arrivals (estimate)",
        url=os.environ.get("ALT_JNTO_URL", "https://www.jnto.go.jp/news/press/"),
        region="JP", language="ja", cadence="monthly", parse=parse_jnto, rule=rule_jnto,
        transform="given", instruments={"USDJPY": -1, "EURJPY": -1, "JPN225": 1},
        signal_series=("arrivals_yoy",),
        mechanism=("inbound visitors convert foreign currency into yen at the till: tourism "
                   "receipts are a services-export flow the goods trade balance does not show"),
        payer="yen shorts funding carry who ignore services-account flows",
        constraint="carry books are sized on rate differentials, not tourism receipts",
        licence="JNTO public press releases (free to cite with attribution)",
        source_culture="JP/ja", participant_structure=("physical_flow", "retail_heavy"),
        failure_mode_hypothesis=("fails when policy (visa rules, China group-tour bans) moves "
                                 "arrivals for reasons the FX market already priced"),
        crowding_prior="low"),
    Source(
        id="jp_tokyo_cpi", name="Tokyo ku-area CPI early print (e-Stat API)",
        url=("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData?appId={key}&statsDataId="
             + os.environ.get("ALT_TOKYO_CPI_STATS_ID", "0003427113")
             + "&cdArea=13A01&cdCat01=" + os.environ.get("ALT_TOKYO_CPI_CAT01", "0161")
             + "&cdTab=3"),
        region="JP", language="ja", cadence="monthly", parse=parse_estat_cpi,
        rule=rule_tokyo_cpi, transform="given", key_env="ESTAT_APP_ID",
        instruments={"USDJPY": -1, "EURJPY": -1, "JPN225": -1},
        signal_series=("core_cpi_yoy",),
        mechanism=("Tokyo's ex-fresh-food CPI prints three weeks before the national figure and "
                   "leads BoJ normalisation pricing"),
        payer="JGB and yen positions leaning on a slow BoJ",
        constraint="BoJ-path positioning only reprices at data and meeting dates",
        licence="e-Stat API terms (free application ID; attribution to the Statistics Bureau)",
        source_culture="JP/ja", participant_structure=("policy_driven", "institutional"),
        failure_mode_hypothesis=("fails when energy-subsidy and education-fee policy moves the "
                                 "print mechanically, a Japan-specific calendar"),
        crowding_prior="medium",
        note="statsDataId/cat01 overridable (ALT_TOKYO_CPI_STATS_ID / _CAT01); confirm on box"),
    Source(
        id="cn_firms_industrial", name="NASA FIRMS thermal detections over Chinese heavy industry",
        url=FIRMS_URL, region="CN", language="en", cadence="daily", parse=parse_firms,
        rule=_lag_rule(1, 12), transform="anomaly_daily", key_env="FIRMS_MAP_KEY",
        instruments={"XCUUSD": 1, "AUDUSD": 1, "CHINAH": 1, "HK50": 1},
        signal_series=("total_count",),
        mechanism=("VIIRS thermal detections inside declared steel, coke and smelter footprints "
                   "are blast-furnace and coke-oven activity, observed daily from orbit before "
                   "any NBS output print"),
        payer="iron-ore, copper and AUD holders who wait for monthly Chinese activity data",
        constraint="China's official industrial data arrive monthly and three weeks late",
        licence="NASA open data (free MAP_KEY; no restriction on use; cite FIRMS)",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis=("fails under output curbs ordered for air-quality events and "
                                 "winter heating season, and under persistent cloud cover"),
        crowding_prior="low",
        note="asia_sources `nasa_firms` fetches the bare API root; this builds the area queries"),
    Source(
        id="imf_portwatch_ports", name="IMF PortWatch daily port calls",
        url=PORTWATCH_BASE.format(svc="Daily_Ports_Data"),
        region="GLOBAL", language="en", cadence="daily", parse=parse_portwatch_ports,
        rule=_lag_rule(10, 0), transform="anomaly_daily",
        instruments={"AUDUSD": 1},
        series_instruments={
            "port_hedland": {"AUDUSD": 1, "AUS200": 1},
            "shanghai": {"XCUUSD": 1, "AUDUSD": 1, "CHINAH": 1},
            "ningbo": {"XCUUSD": 1, "AUDUSD": 1, "CHINAH": 1},
            "busan": {"USDKRW": -1},
            "singapore": {"XTIUSD": 1, "AUDUSD": 1}},
        signal_series=("port_hedland_portcalls", "shanghai_portcalls", "busan_portcalls"),
        mechanism=("AIS-counted port calls are physical trade volume by port, weekly and "
                   "public, ahead of customs values"),
        payer="commodity-FX and metals holders pricing monthly trade and PMI releases",
        constraint="monthly customs data and PMIs lag the ships by weeks",
        licence="IMF PortWatch open data (free, attribution required)",
        source_culture="GLOBAL/en", participant_structure=("physical_flow",),
        failure_mode_hypothesis=("fails when AIS coverage gaps or port-calling pattern changes "
                                 "(larger ships, fewer calls) move counts without volume"),
        crowding_prior="low"),
    Source(
        id="imf_portwatch_chokepoints", name="IMF PortWatch daily chokepoint transits",
        url=PORTWATCH_BASE.format(svc="Daily_Chokepoints_Data"),
        region="GLOBAL", language="en", cadence="daily", parse=parse_portwatch_chokepoints,
        rule=_lag_rule(10, 0), transform="anomaly_daily",
        instruments={"XTIUSD": -1, "XBRUSD": -1},
        signal_series=("strait_of_hormuz_transits", "bab_el_mandeb_strait_transits"),
        mechanism=("fewer transits through oil chokepoints is supply friction; the tanker count "
                   "moves before any inventory report"),
        payer="short-dated crude holders pricing weekly inventories",
        constraint="EIA and OPEC data are weekly/monthly, the ships are daily",
        licence="IMF PortWatch open data (free, attribution required)",
        source_culture="GLOBAL/en", participant_structure=("physical_flow",),
        failure_mode_hypothesis=("fails when rerouting is already priced by freight markets "
                                 "before the transit counts publish"),
        crowding_prior="low"),
    Source(
        id="in_gold_imports", name="India monthly gold and silver imports (PIB trade release)",
        url=os.environ.get("ALT_PIB_TRADE_URL", "https://pib.gov.in/PressReleasePage.aspx"),
        region="IN", language="en", cadence="monthly", parse=parse_pib_trade,
        rule=_lag_rule(16, 12, weekday=True), transform="anomaly_monthly",
        instruments={"XAUUSD": 1, "XAGUSD": 1},
        series_instruments={"silver": {"XAGUSD": 1}},
        signal_series=("gold_imports_usd_bn", "silver_imports_usd_bn"),
        mechanism=("India imports nearly all its gold; the monthly import bill is physical "
                   "jewellery and investment demand at a price, reported by the government"),
        payer="London/NY paper-gold positioning that ignores physical Asian offtake",
        constraint="import duty changes and festival calendars bind Indian demand, not the COMEX",
        licence="Press Information Bureau releases (Government of India, public)",
        source_culture="IN/en", participant_structure=("physical_flow", "tax_driven",
                                                        "retail_heavy"),
        failure_mode_hypothesis=("fails around import-duty changes and wedding/festival "
                                 "seasons, which move Indian demand off the Western cycle"),
        crowding_prior="low",
        note=("history accumulates forward from the release pages; the release URL of each "
              "month is overridable (ALT_PIB_TRADE_URL)")),
    Source(
        id="cn_sge_premium", name="Shanghai gold premium (read from fetch_sge_premium)",
        url="file:data/lake/sge_premium.parquet", region="CN", language="zh", cadence="daily",
        parse=None, rule=_lag_rule(1, 0), transform="level_dev",
        instruments={"XAUUSD": 1, "XAGUSD": 1},
        signal_series=("premium_pct",),
        mechanism=("licensed import quotas stop the SGE price arbitraging to London; a widening "
                   "premium is Chinese physical demand the Western tape has not seen"),
        payer="Western gold holders pricing on real yields and the dollar only",
        constraint="PBoC import licences cap how fast the premium can close",
        licence="read from the desk's own recorded SGE series (fetch_sge_premium provenance)",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven",
                                                        "settlement_constrained"),
        failure_mode_hypothesis=("fails when PBoC quota decisions, not demand, move the premium "
                                 "-- a policy clock unrelated to the Fed"),
        crowding_prior="low", note="no fetch: fetch_sge_premium already records it"),
)
BY_ID = {s.id: s for s in SOURCES}


def status_of(src: Source) -> str:
    if src.key_env and not os.environ.get(src.key_env):
        return f"BLOCKED_ON_KEY:{src.key_env}"
    return "UNMEASURED_LIVE_YIELD"


# ============================================================================ fetching
def _tls() -> Any:
    with contextlib.suppress(Exception):
        from research import asia_collector
        make: Any = asia_collector._tls_context
        return make()
    return None


def _redact(url: str, src: Source) -> str:
    key = os.environ.get(src.key_env or "", "") if src.key_env else ""
    return url.replace(key, f"<{src.key_env}>") if key else url


def http_get(url: str) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_tls()) as r:
        return r.read(MAX_BYTES), str(r.headers.get("Content-Type") or "")


def vault(paths: Paths, src: Source, body: bytes, url: str, ctype: str,
          fetched_at: datetime) -> dict[str, Any]:
    """Raw bytes under their content hash, never overwritten; the URL is stored REDACTED."""
    digest = hashlib.sha256(body).hexdigest()
    d = paths.vault / f"alt_{src.id}"
    d.mkdir(parents=True, exist_ok=True)
    blob = d / f"{digest[:16]}.gz"
    if not blob.exists():
        blob.write_bytes(gzip.compress(body))
        (d / f"{digest[:16]}.meta.json").write_text(json.dumps({
            "source_id": src.id, "url": _redact(url, src), "content_type": ctype,
            "sha256": digest, "bytes": len(body),
            "fetched_utc": fetched_at.isoformat(timespec="seconds")}, indent=1), "utf-8")
    return {"sha256": digest[:16], "bytes": len(body)}


@dataclass
class Request:
    url: str
    ctx: Ctx


def requests_for(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    """The requests one pass makes for a source. Paged and area sources expand here."""
    key = os.environ.get(src.key_env or "", "") if src.key_env else ""
    if src.id == "cn_firms_industrial":
        out: list[Request] = []
        end = (now - timedelta(days=1)).date()
        start = end - timedelta(days=9)
        for name, box in FIRMS_CLUSTERS.items():
            bbox = ",".join(str(x) for x in box)
            out.append(Request(FIRMS_URL.format(key=key, product="VIIRS_SNPP_NRT", bbox=bbox,
                                                days=10, day=start.isoformat()),
                               Ctx(part=name, start=start, end=end, fetched_at=now)))
        # BACKFILL, RESUMABLE: ten days per cluster per pass from the archive product, walking
        # back from the last date reached, three years deep at most.
        cur = state.get("firms_backfill_to")
        bf_end = date.fromisoformat(cur) if cur else start - timedelta(days=1)
        if bf_end > (now - timedelta(days=3 * 365)).date():
            bf_start = bf_end - timedelta(days=9)
            for name, box in FIRMS_CLUSTERS.items():
                bbox = ",".join(str(x) for x in box)
                out.append(Request(FIRMS_URL.format(key=key, product="VIIRS_SNPP_SP", bbox=bbox,
                                                    days=10, day=bf_start.isoformat()),
                                   Ctx(part=name, start=bf_start, end=bf_end, fetched_at=now)))
            state["firms_backfill_to_next"] = (bf_start - timedelta(days=1)).isoformat()
        return out
    if src.id in ("imf_portwatch_ports", "imf_portwatch_chokepoints"):
        names = PORTS if src.id.endswith("ports") else CHOKEPOINTS
        since = (now - timedelta(days=800)).date().isoformat()
        quoted = ",".join("'" + n.replace("'", "''") + "'" for n in names)
        reqs = []
        for offset in range(0, 20_000, 2_000):
            q = urllib.parse.urlencode({
                "where": f"portname IN ({quoted}) AND date >= timestamp '{since} 00:00:00'",
                "outFields": "date,portname,portcalls,n_total", "orderByFields": "date",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"})
            reqs.append(Request(f"{src.url}?{q}", Ctx(part=f"page{offset}", fetched_at=now)))
        return reqs
    if src.id == "us_tsa_throughput":
        # The current page carries this year only; the year-on-year comparison needs last year's
        # page, which TSA publishes at /<year>.
        return [Request(src.url, Ctx(fetched_at=now)),
                Request(f"{src.url}/{now.year - 1}", Ctx(part="prior_year", fetched_at=now))]
    return [Request(src.url.replace("{key}", key), Ctx(fetched_at=now))]


# ============================================================================ the vintage store
def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return default


def _atomic(p: Path, doc: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(doc, indent=1, default=str, ensure_ascii=False), "utf-8")
    os.replace(tmp, p)


def merge_vintages(store: dict[str, Any], src: Source, obs: Iterable[Obs],
                   seen_at: datetime) -> dict[str, int]:
    """Append-only: a key's FIRST value and first-seen instant never change; a different later
    value is recorded as a revision beside it with the instant it was seen."""
    added = revised = 0
    stamp = seen_at.isoformat(timespec="seconds")
    for o in obs:
        k = f"{o.series}|{o.period.isoformat()}"
        rule_at = src.rule(o.period)
        pub = o.published_at
        # A page stamp far after the period is a LATER document quoting an old value (a release
        # citing last year's figure), not that value's release: the calendar rule governs it.
        if pub is not None and not 0 <= (pub.date() - o.period).days <= MAX_PUB_LAG_D:
            pub = None
        row = store.get(k)
        if row is None:
            store[k] = {"series": o.series, "period": o.period.isoformat(),
                        "value_first": o.value, "value_last": o.value,
                        "first_seen_at": stamp, "last_seen_at": stamp,
                        "published_time": (pub or rule_at).isoformat(timespec="seconds"),
                        "published_basis": "page" if pub else "release_rule",
                        "revision_time": None, "n_revisions": 0}
            added += 1
            continue
        row["last_seen_at"] = stamp
        if pub is not None and row.get("published_basis") != "page":
            row["published_time"] = pub.isoformat(timespec="seconds")
            row["published_basis"] = "page"
        if not math.isclose(float(row["value_last"]), o.value, rel_tol=1e-9, abs_tol=1e-12):
            row["value_last"] = o.value
            row["revision_time"] = stamp
            row["n_revisions"] = int(row.get("n_revisions") or 0) + 1
            revised += 1
    return {"added": added, "revised": revised}


# ============================================================================ features
def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _sd(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    v = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(v) if v > 0 else None


def build_points(src: Source, store: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Per series: PIT points carrying value, pace (the transform), surprise and surprise_z.

    Every statistic at point i uses only points before i in AVAILABILITY order -- strict prefix
    -- so nothing a point carries was unknowable at its own available_time. The first value seen
    is used (value_first): a later revision is its own stamped fact, never back-dated."""
    by: dict[str, list[dict[str, Any]]] = {}
    for row in store.values():
        if isinstance(row, dict) and row.get("series"):
            by.setdefault(str(row["series"]), []).append(row)
    out: dict[str, list[dict[str, Any]]] = {}
    for name, rows in by.items():
        rows.sort(key=lambda r: (str(r.get("published_time")), str(r.get("period"))))
        vals = [float(r["value_first"]) for r in rows]
        periods = [date.fromisoformat(str(r["period"])) for r in rows]
        pos = {p: i for i, p in enumerate(periods)}
        pace: list[float | None] = []
        for i, v in enumerate(vals):
            x: float | None = None
            if src.transform == "given":
                x = v
            elif src.transform == "yoy_daily":
                raw = []
                for j in range(max(0, i - 6), i + 1):
                    back = pos.get(periods[j] - timedelta(days=364))
                    if back is not None and back < i and vals[back] > 0:
                        raw.append(vals[j] / vals[back] - 1.0)
                mr = _mean(raw) if len(raw) >= 4 else None
                x = mr * 100.0 if mr is not None else None
            elif src.transform == "mom_monthly":
                x = (v / vals[i - 1] - 1.0) * 100.0 if i >= 1 and vals[i - 1] > 0 else None
            elif src.transform == "anomaly_daily":
                recent, base = vals[max(0, i - 6): i + 1], vals[max(0, i - 97): max(0, i - 6)]
                mb = _mean(base)
                x = ((_mean(recent) or 0.0) / mb - 1.0) * 100.0 if len(base) >= 28 and mb else None
            elif src.transform == "anomaly_monthly":
                base = vals[max(0, i - 6): i]
                mb = _mean(base)
                x = (v / mb - 1.0) * 100.0 if len(base) >= 3 and mb else None
            elif src.transform == "level_dev":
                base = vals[max(0, i - 20): i]
                mb = _mean(base)
                x = v - mb if len(base) >= 5 and mb is not None else None
            pace.append(x)
        surprises: list[float] = []
        pts: list[dict[str, Any]] = []
        prior_x: list[float] = []
        for i, r in enumerate(rows):
            x = pace[i]
            surprise = z = None
            if x is not None:
                exp = _mean(prior_x[-EXPECTATION_N:]) if len(prior_x) >= 3 else None
                if exp is not None:
                    surprise = x - exp
                    sd = _sd(surprises) if len(surprises) >= SURPRISE_SD_MIN else None
                    z = surprise / sd if sd else None
                    surprises.append(surprise)
                prior_x.append(x)
            first_seen = _t(r.get("first_seen_at"))
            published = _t(r.get("published_time"))
            quality = ("live" if first_seen and published
                       and first_seen <= published + timedelta(days=2) else "backfill")
            pts.append({
                "d": str(r["period"]), "event_time": str(r["period"]),
                "available_time": str(r["published_time"]),
                "published_time": str(r["published_time"]),
                "published_basis": r.get("published_basis"),
                "first_seen_at": r.get("first_seen_at"),
                "retrieval_time": r.get("first_seen_at"),
                "revision_time": r.get("revision_time"),
                "vintage_id": _vintage(src.id, r.get("first_seen_at"), r["value_first"]),
                "pit_quality": quality,
                "value": r["value_first"],
                "pace": None if x is None else round(x, 6),
                "surprise": None if surprise is None else round(surprise, 6),
                "surprise_z": None if z is None else round(z, 4)})
        out[name] = pts
    # FIRMS: a total across the declared footprints, per day, from the per-cluster counts.
    if src.id == "cn_firms_industrial":
        out.update(_firms_total(src, out))
    return out


def _firms_total(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    days: dict[str, dict[str, Any]] = {}
    for name, pts in per.items():
        if not name.endswith("_count"):
            continue
        for p in pts:
            e = days.setdefault(p["d"], {"n": 0, "v": 0.0, "p": p})
            e["n"] += 1
            e["v"] += float(p["value"])
    ncl = len(FIRMS_CLUSTERS)
    store = {f"total_count|{d}": {"series": "total_count", "period": d, "value_first": e["v"],
                                   "value_last": e["v"],
                                   "first_seen_at": e["p"]["first_seen_at"],
                                   "published_time": e["p"]["published_time"],
                                   "published_basis": e["p"]["published_basis"]}
             for d, e in days.items() if e["n"] == ncl}
    if not store:
        return {}
    sub = Source(**{**src.__dict__, "id": src.id + "_total"})
    got = build_points(sub, store)
    return {"total_count": got.get("total_count", [])}


def _vintage(source_id: str, first_seen: Any, value: Any) -> str | None:
    try:
        from libs.data.pit_stamp import vintage_id_for
        return vintage_id_for(source_id, str(first_seen) if first_seen else None, str(value))
    except Exception:                                          # pragma: no cover - import guard
        return None


# ============================================================================ publishing
def axis_doc(src: Source, points: dict[str, list[dict[str, Any]]], now: datetime) -> dict[str, Any]:
    """The axis door's shape (`series[name].points` with `available_time` on every point), which
    alpha_dsl.axis_fields, world_model.load_inputs and representation_forge read unchanged."""
    series: dict[str, Any] = {}
    for name, pts in sorted(points.items()):
        for col in ("value", "pace", "surprise_z"):
            keep = [{"d": p["d"], "v": p[col], "available_time": p["available_time"],
                     "published_time": p["published_time"], "event_time": p["event_time"],
                     "first_seen_at": p["first_seen_at"], "revision_time": p["revision_time"],
                     "vintage_id": p["vintage_id"], "pit_quality": p["pit_quality"]}
                    for p in pts if p.get(col) is not None]
            if keep:
                series[f"{name}.{col}"] = {"what": f"{src.name}: {name} {col}", "n": len(keep),
                                           "first": keep[0]["d"], "last": keep[-1]["d"],
                                           "points": keep}
    return {"axis": "alt_proxy", "id": f"alt_{src.id}", "source": src.url.split("?")[0],
            "at": now.isoformat(timespec="seconds"), "region": src.region,
            "cadence": src.cadence, "n_series": len(series),
            "pit_fields": ["event_time", "published_time", "available_time", "first_seen_at",
                           "revision_time", "vintage_id"],
            "shape": "series[<series>.<value|pace|surprise_z>].points, joined on available_time",
            "vintage_note": ("first value seen is the value; a revision is recorded with its own "
                             "revision_time and never back-dated"),
            "series": series}


def lake_file(src: Source, series: str) -> str:
    return f"alt_{src.id}__{series}"


def write_lake_series(paths: Paths, src: Source, points: dict[str, list[dict[str, Any]]]
                      ) -> list[str]:
    """One CSV per series under data/lake/series, in the envelope `exogenous_conditioner` reads."""
    import pandas as pd
    written: list[str] = []
    paths.series.mkdir(parents=True, exist_ok=True)
    for name, pts in points.items():
        if not pts:
            continue
        df = pd.DataFrame([{"event_time": p["event_time"], "available_time": p["available_time"],
                            "published_time": p["published_time"],
                            "retrieval_time": p["retrieval_time"],
                            "revision_time": p["revision_time"], "source_id": src.id,
                            "vintage_id": p["vintage_id"], "value": p["value"], "pace": p["pace"],
                            "surprise_z": p["surprise_z"], "pit_quality": p["pit_quality"]}
                           for p in pts])
        target = paths.series / f"{lake_file(src, name)}.csv"
        tmp = target.with_suffix(f".tmp{os.getpid()}")
        df.to_csv(tmp, index=False)
        os.replace(tmp, target)
        written.append(target.name)
    return written


def allocation_intel(points_by_source: dict[str, dict[str, list[dict[str, Any]]]],
                     gains: dict[str, dict[str, Any]], now: datetime,
                     days: int = 30) -> dict[str, Any]:
    """Per instrument, per day: the PIT-available surprise of every mapped series.

    `tilt` = mean over live components of sign * clip(surprise_z, -3, 3), where sign is the
    MEASURED sign of the gain-test IC when that test passed and the declared prior otherwise
    (`sign_basis` says which). A component is live on day D only if its available_time <= D and
    it is not older than its cadence's staleness bound. Nothing here sizes a book."""
    inst: dict[str, dict[str, Any]] = {}
    day_list = [(now - timedelta(days=k)).date() for k in range(days - 1, -1, -1)]
    for sid, per in points_by_source.items():
        src = BY_ID[sid]
        stale = STALE_DAYS.get(src.cadence, 45)
        for series in src.signal_series:
            pts = [p for p in per.get(series, []) if p.get("surprise_z") is not None]
            if not pts:
                continue
            stamps = [(_t(p["available_time"]), p) for p in pts]
            for sym, prior in src.instruments_for(series).items():
                g = gains.get(f"{sid}|{series}|{sym}") or {}
                measured = g.get("verdict") == "PASS" and g.get("ic")
                sign = (1 if float(g["ic"]) > 0 else -1) if measured else int(prior)
                e = inst.setdefault(sym, {"components": [], "daily": {}})
                last = None
                for day in day_list:
                    cut = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=UTC)
                    known = [p for t, p in stamps if t is not None and t <= cut]
                    if not known:
                        continue
                    p = known[-1]
                    at = _t(p["available_time"])
                    if at is None or (cut - at).days > stale:
                        continue
                    z = max(-3.0, min(3.0, float(p["surprise_z"])))
                    e["daily"].setdefault(day.isoformat(), []).append(sign * z)
                    last = p
                if last is not None:
                    e["components"].append({
                        "source": sid, "series": series, "surprise_z": last["surprise_z"],
                        "pace": last["pace"], "available_time": last["available_time"],
                        "period": last["d"], "pit_quality": last["pit_quality"],
                        "sign": sign, "sign_basis": "measured_ic" if measured else "prior",
                        "gain_verdict": g.get("verdict", UNMEASURED), "ic": g.get("ic")})
    out: dict[str, Any] = {}
    for sym, e in sorted(inst.items()):
        daily = [{"date": d, "tilt": round(sum(v) / len(v), 4), "n": len(v)}
                 for d, v in sorted(e["daily"].items())]
        out[sym] = {"tilt": daily[-1]["tilt"] if daily else None,
                    "as_of": daily[-1]["date"] if daily else None,
                    "components": e["components"], "daily": daily}
    return {"generated_at": now.isoformat(timespec="seconds"), "use": "allocation_intel",
            "rule": ("read-only PIT summary: tilt = mean(sign * clip(surprise_z, +-3)) over the "
                     "components released and not stale on that day. It sizes nothing; the "
                     "allocator is not wired to it"),
            "instruments": out}


# ============================================================================ cells
def _bars_close(paths: Paths, sym: str) -> Any:
    p = paths.universe / f"{sym}_H1.parquet"
    if not p.exists():
        return None
    try:
        import pandas as pd
        df = pd.read_parquet(p)
    except Exception:
        return None
    if "close" not in df.columns or df.empty:
        return None
    idx = pd.DatetimeIndex(pd.to_datetime(df.index, utc=True, errors="coerce"))
    s = pd.Series(df["close"].to_numpy(dtype=float), index=idx)
    return s[s.index.notna()].sort_index()


def _meta(src: Source) -> dict[str, Any]:
    return {"mechanism": src.mechanism, "payer": src.payer, "constraint": src.constraint,
            "source_culture": src.source_culture,
            "participant_structure": list(src.participant_structure),
            "failure_mode_hypothesis": src.failure_mode_hypothesis,
            "crowding_prior": src.crowding_prior}


def gain_tests(paths: Paths, points_by_source: dict[str, dict[str, list[dict[str, Any]]]],
               ) -> dict[str, dict[str, Any]]:
    """Every (source, signal series, mapped instrument) cell, tested once, charged together."""
    from libs.research.release_gain import release_gain
    cells: list[tuple[str, str, str]] = []
    for sid, per in points_by_source.items():
        src = BY_ID[sid]
        for series in src.signal_series:
            if per.get(series):
                cells.extend((sid, series, sym) for sym in src.instruments_for(series))
    out: dict[str, dict[str, Any]] = {}
    closes: dict[str, Any] = {}
    for sid, series, sym in cells:
        if sym not in closes:
            closes[sym] = _bars_close(paths, sym)
        close = closes[sym]
        key = f"{sid}|{series}|{sym}"
        if close is None:
            out[key] = {"verdict": UNMEASURED, "why": f"no {sym}_H1 bars on this box"}
            continue
        pts = points_by_source[sid][series]
        ev = [(p["available_time"], float(p["surprise_z"])) for p in pts
              if p.get("surprise_z") is not None]
        res = release_gain(ev, close, horizon_bars=HORIZON_BARS, n_cells=len(cells)).as_dict()
        res["backfill_share"] = (round(sum(1 for p in pts if p["pit_quality"] == "backfill")
                                       / len(pts), 3) if pts else None)
        out[key] = res
    return out


def direct_cells(gains: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """PASSING cells only, as `exogenous_conditioner` recipes the gauntlet rebuilds from the lake
    series itself. The side is the MEASURED sign of the IC, never the prior."""
    out: list[dict[str, Any]] = []
    for key, g in sorted(gains.items()):
        if g.get("verdict") != "PASS" or not g.get("ic"):
            continue
        sid, series, sym = key.split("|")
        src = BY_ID[sid]
        side = 1 if float(g["ic"]) > 0 else -1
        params = {"source": lake_file(src, series), "signal": "surprise_z",
                  "transform": "level_z", "threshold": 1.0, "side_when_high": side,
                  "lag_hours": 24, "ttl_bars": HORIZON_BARS}
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
            "family": "exogenous_conditioner", "params": params, "url": "",
            "cell": f"{sym}.exogenous_conditioner.{lake_file(src, series)}",
            "title": f"{src.name}: {series} surprise -> {sym} ({'+' if side > 0 else '-'})"[:120],
            "available_time": now.isoformat(timespec="seconds"),
            "event_time": now.isoformat(timespec="seconds"),
            **_meta(src),
            "prior_sign": src.instruments_for(series).get(sym),
            "falsifier": (f"IC of {series} surprise on {sym} {HORIZON_BARS}-bar post-release "
                          "returns no longer beats the shifted-release placebo at p<=0.05"),
            "evidence": {k: g.get(k) for k in ("ic", "n", "t", "p_t", "p_placebo",
                                               "placebo_abs_ic_p95", "backfill_share",
                                               "horizon_bars", "why")},
            "provenance": {"organ": "alt_proxies", "use": "direct_cells", "source_id": sid,
                           "series": series, **_meta(src)}})
    return out


def conditioner_spec(src: Source, series: str, column: str, op: str, thr: float) -> str:
    return f"{CONDITIONER_PREFIX}{lake_file(src, series)}:{column}:{op}:{thr:g}"


def _parents(paths: Paths) -> dict[str, list[dict[str, Any]]]:
    doc = _read_json(paths.survivors, {})
    rows = (doc or {}).get("survivors") if isinstance(doc, dict) else None
    out: dict[str, list[dict[str, Any]]] = {}
    for name, v in sorted((rows or {}).items()) if isinstance(rows, dict) else []:
        spec = (v or {}).get("shadow_spec") if isinstance(v, dict) else None
        if not isinstance(spec, dict) or not spec.get("family") or not spec.get("symbol"):
            continue
        out.setdefault(str(spec["symbol"]), []).append({"name": name, **spec})
    return out


def indirect_cells(paths: Paths, points_by_source: dict[str, dict[str, list[dict[str, Any]]]],
                   state: dict[str, Any], now: datetime,
                   limit: int = INDIRECT_PER_PASS) -> tuple[list[dict[str, Any]], int]:
    """Certified parents on each mapped instrument, conditioned on the series' pace sign.

    Two children per (parent, series): pace > 0 and pace < 0 -- the two halves of one split, so
    neither is chosen after seeing which paid. Only series with live-yield points (not a fixture,
    at least 24 released points) mint; a rotating cursor spreads the per-pass share so every
    pair is reached. Returns (candidates, pairs owed to later passes)."""
    parents = _parents(paths)
    pairs: list[tuple[str, str, dict[str, Any]]] = []
    for sid, per in sorted(points_by_source.items()):
        src = BY_ID[sid]
        for series in src.signal_series:
            pts = [p for p in per.get(series, []) if p.get("pace") is not None]
            if len(pts) < 24:
                continue
            for sym in src.instruments_for(series):
                for par in parents.get(sym, [])[:PARENTS_PER_SYMBOL]:
                    pairs.append((sid, series, par))
    if not pairs:
        return [], 0
    start = int(state.get("indirect_cursor") or 0) % len(pairs)
    take = (pairs[start:] + pairs[:start])[: max(0, limit // 2)]
    state["indirect_cursor"] = (start + len(take)) % len(pairs)
    out: list[dict[str, Any]] = []
    for sid, series, par in take:
        src = BY_ID[sid]
        for op in ("gt", "lt"):
            params = dict(par.get("params") or {})
            if par.get("selector") and "session" not in params:
                params["session"] = str(par["selector"])
            params["conditioner"] = conditioner_spec(src, series, "pace", op, 0.0)
            sym = str(par["symbol"])
            out.append({
                "source": INDIRECT_SOURCE, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
                "family": str(par["family"]), "params": params, "url": "",
                "cell": f"{par['name']}|{params['conditioner']}",
                "title": (f"{par['family']} on {sym} only while {series} pace "
                          f"{'>' if op == 'gt' else '<'} 0")[:120],
                "available_time": now.isoformat(timespec="seconds"),
                "event_time": now.isoformat(timespec="seconds"),
                **_meta(src),
                "falsifier": ("the conditioned child's gauntlet verdict is no better than its "
                              "certified parent's on the same window"),
                "parent": par["name"],
                "provenance": {"organ": "alt_proxies", "use": "indirect_cells",
                               "source_id": sid, "series": series, **_meta(src)}})
    return out, max(0, len(pairs) - len(take))


def _donate(source: str, cands: list[dict[str, Any]], tests_run: int) -> dict[str, Any]:
    if not cands:
        return {"donated": 0, "path": None}
    try:
        from research import proposer_common as pc
        path = pc.donate(source, cands, tests_run)
        return {**pc.donation_counts(), "path": str(path) if path else None}
    except Exception as exc:
        return {"donated": 0, "path": None, "error": f"{type(exc).__name__}: {str(exc)[:160]}"}


# ============================================================================ the pass
def _load_fixture(fixtures: Path, src: Source, req: Request, i: int) -> bytes | None:
    for name in (f"{src.id}.{i}", src.id):
        for ext in ("html", "json", "csv", "txt"):
            p = fixtures / f"{name}.{ext}"
            if p.exists() and (i == 0 or name != src.id):
                return p.read_bytes()
    return None


def collect(paths: Paths, src: Source, state: dict[str, Any], now: datetime, *,
            fetch: bool, fixtures: Path | None, deadline: float,
            getter: Callable[[str], tuple[bytes, str]] = http_get) -> dict[str, Any]:
    """Fetch (or read fixtures), parse, and merge into the source's vintage store."""
    rec: dict[str, Any] = {"id": src.id, "status": status_of(src)}
    store_p = paths.obs_dir / f"{src.id}.json"
    store = _read_json(store_p, {})
    if src.parse is None:                                    # the SGE premium: a local read
        obs = read_sge_premium(paths)
        rec.update({"requests": 0, "parsed": len(obs),
                    "why": "read from fetch_sge_premium's parquet" if obs else
                    "sge_premium.parquet absent or empty here: UNMEASURED"})
        rec["merge"] = merge_vintages(store, src, obs, now)
        _atomic(store_p, store)
        rec["store_rows"] = len(store)
        return rec
    blocked = rec["status"].startswith("BLOCKED_ON_KEY") and fixtures is None
    if blocked:
        rec["why"] = f"{src.key_env} is not set: a named state, never a dead endpoint"
        rec["store_rows"] = len(store)
        return rec
    sst = state.setdefault("sources", {}).setdefault(src.id, {})
    reqs = requests_for(src, now, sst)
    parsed = fetched = 0
    errors: list[str] = []
    for i, req in enumerate(reqs):
        if time.monotonic() > deadline:
            errors.append("budget reached: the remaining requests are owed to the next pass")
            break
        body: bytes | None = None
        if fixtures is not None:
            body = _load_fixture(fixtures, src, req, i)
            if body is None:
                continue
        elif fetch:
            try:
                body, ctype = getter(req.url)
                fetched += 1
                vault(paths, src, body, req.url, ctype, now)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {_redact(str(exc), src)[:120]}")
                continue
        if body is None:
            continue
        obs = src.parse(body, req.ctx)
        parsed += len(obs)
        m = merge_vintages(store, src, obs, now)
        rec.setdefault("merge", {"added": 0, "revised": 0})
        rec["merge"]["added"] += m["added"]
        rec["merge"]["revised"] += m["revised"]
        if src.id.startswith("imf_portwatch") and not obs:
            break                                              # paging exhausted
    if src.id == "cn_firms_industrial" and "firms_backfill_to_next" in sst and not errors:
        sst["firms_backfill_to"] = sst.pop("firms_backfill_to_next")
    rec.update({"requests": len(reqs), "fetched": fetched, "parsed": parsed,
                "errors": errors[:6], "store_rows": len(store)})
    if not parsed and not errors:
        rec["why"] = "nothing parsed this pass (no fetch, or the page carried no rows)"
    _atomic(store_p, store)
    return rec


def run(paths: Paths = DEFAULT_PATHS, *, budget_s: float = 300.0, fetch: bool = True,
        fixtures: Path | None = None, dry_run: bool = False, donate: bool = True,
        now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    deadline = time.monotonic() + budget_s * 0.6
    state = _read_json(paths.state, {})
    records: dict[str, Any] = {}
    points_by_source: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for src in SOURCES:
        rec = collect(paths, src, state, now, fetch=fetch, fixtures=fixtures, deadline=deadline)
        store = _read_json(paths.obs_dir / f"{src.id}.json", {})
        pts = build_points(src, store) if store else {}
        if pts:
            points_by_source[src.id] = pts
            if not dry_run:
                _atomic(paths.axes / f"alt_{src.id}.json", axis_doc(src, pts, now))
                rec["lake_series"] = write_lake_series(paths, src, pts)
        rec["series"] = {k: len(v) for k, v in sorted(pts.items())}
        records[src.id] = rec
    gains = gain_tests(paths, points_by_source) if points_by_source else {}
    live = dict(points_by_source) if fixtures is None else {}
    direct = direct_cells(gains, now) if fixtures is None else []
    indirect, owed = indirect_cells(paths, live, state, now)
    n_tested = sum(1 for g in gains.values() if g.get("verdict") in ("PASS", "FAIL"))
    donations: dict[str, Any] = {"direct": {"donated": 0}, "indirect": {"donated": 0}}
    if donate and not dry_run:
        donations["direct"] = _donate(SOURCE, direct, max(1, n_tested))
        donations["indirect"] = _donate(INDIRECT_SOURCE, indirect, max(1, len(indirect)))
    intel = allocation_intel(points_by_source, gains, now)
    report = {
        "at": now.isoformat(timespec="seconds"), "organ": "alt_proxies",
        "mode": "fixtures" if fixtures is not None else ("fetch" if fetch else "no_fetch"),
        "sources": records,
        "gain_tests": gains,
        "n_cells_tested": n_tested, "n_cells_total": len(gains),
        "direct_cells": {"n": len(direct), "donation": donations["direct"],
                         "rule": ("an exogenous_conditioner cell is donated only after its gain "
                                  "test PASSED on this box; every tested cell is charged")},
        "indirect_cells": {"n": len(indirect), "owed_to_later_passes": owed,
                           "donation": donations["indirect"],
                           "rule": ("certified parents conditioned on pace>0 / pace<0 via "
                                    "params.conditioner, applied by mt5desk.cell_modifiers")},
        "allocation_intel": {"path": str(paths.allocation_intel),
                             "n_instruments": len(intel["instruments"])},
        "keys": {s.key_env: bool(os.environ.get(s.key_env)) for s in SOURCES if s.key_env},
        "live_yield": ("UNMEASURED until the trading box runs this leg: the fetchers were built "
                       "against fixtures because the authoring container cannot reach the hosts"),
    }
    state["last_run"] = report["at"]
    if not dry_run:
        _atomic(paths.state, state)
        _atomic(paths.allocation_intel, intel)
        _atomic(paths.report, report)
    return report


def roster_rows() -> list[dict[str, Any]]:
    """One roster row per source, for the mining roster (the same metadata the cells carry)."""
    rows = []
    for s in SOURCES:
        uses = ["direct_cells", "indirect_cells", "allocation_intel"]
        rows.append({"id": s.id, "name": s.name, "url": s.url.split("?")[0].replace("{key}",
                                                                                   "<key>"),
                     "region": s.region, "language": s.language, "cadence": s.cadence,
                     "auth": f"free_key:{s.key_env}" if s.key_env else "none",
                     "licence": s.licence,
                     "cursor": ("firms_backfill_to (10 days/cluster/pass, archive product)"
                                if s.id == "cn_firms_industrial" else
                                "resultOffset paging; 800-day window"
                                if s.id.startswith("imf_portwatch") else
                                "vintage store keyed series|period (append-only)"),
                     "pit": ("available_time = page publication stamp else release-calendar rule "
                             "(late-biased); first_seen_at = vault fetch instant"),
                     "uses": uses, "consumer": "desks/mt5/research/alt_proxies.py",
                     "status": status_of(s), **_meta(s)})
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--no-donate", action="store_true")
    a = ap.parse_args(argv)
    rep = run(budget_s=a.budget_s, fetch=not a.no_fetch, fixtures=a.fixtures,
              dry_run=a.dry_run, donate=not a.no_donate)
    print(f"alt_proxies ({rep['mode']}): {len(rep['sources'])} sources, "
          f"{rep['n_cells_tested']}/{rep['n_cells_total']} cells gain-tested, "
          f"direct {rep['direct_cells']['n']}, indirect {rep['indirect_cells']['n']}")
    for sid, r in rep["sources"].items():
        n = sum((r.get("series") or {}).values())
        print(f"  {sid:<28} {r['status']:<30} points={n:<6} "
              f"{'; '.join(r.get('errors') or [])[:80] or r.get('why', '')[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
