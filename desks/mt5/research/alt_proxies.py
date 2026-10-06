"""FREE PUBLIC PROXIES FOR POS / CARD / RECEIPT / LOCATION / SATELLITE DATA, AS PIT SERIES.

PAID SUBSTITUTES (SUBSTITUTE_SOURCES). Twenty more rows stand in for four paid panel classes --
RavenPack news analytics (GDELT 2.0 country x day x theme, ja/zh/ko Wikipedia attention), card
panels (Opportunity Insights/Affinity, BOK ECOS, METI, NBS, MCT/UnionPay holidays, NPCI UPI, BKM,
Cielo ICVA, ANTAD, BETI), foot traffic (Google mobility, KOBIS, Seoul subway, Maoyan, Baidu
migration) and satellite/AIS (Busan, SingStat, China MOT ports). Each row names what it
`substitutes_for`; `substitute_agreement` measures each against an overlapping free series on the
same keys (the paid originals are not held). They ride this organ's hourly clock unchanged.

BLOCKED+SUBSTITUTE. A source the terms gate blocks is never fetched, but coverage does not shrink:
SUBSTITUTED_BY names the confirmed-terms rows standing in for it (e-Stat immigration for JNTO,
HK Immigration crossings for Baidu migration / Maoyan / the holiday tallies, TÜİK for BKM, BCB
Open Data for Cielo, INEGI EMEC for ANTAD, data.go.kr MOF containers and PortWatch for the port
boards, India's gold imports for the SGE premium), and its status reads BLOCKED+SUBSTITUTE:<ids>.
`--write-rosters` regenerates the committed roster YAML and the paid-substitute engine's rows.

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
import bisect
import contextlib
import gzip
import hashlib
import html as _html
import io
import itertools
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
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
#: Forward window (H1 bars) each parent signal's return is read over in the conditioned test.
CHILD_HORIZON_BARS = 24
#: Parents per instrument read from the certified survivors.
PARENTS_PER_SYMBOL = 3
#: A component older than this (days since its release) no longer describes "now" in the
#: allocation-intel artifact. Keyed by cadence.
STALE_DAYS = {"daily": 10, "weekly": 21, "10-daily": 25, "monthly": 45, "event": 30}

# ONE KEY, ONE NAME (2026-10-06): BOK_API_KEY, when it is the only name set, is adopted as
# ECOS_API_KEY for this process. Names only; no value is printed or returned.
with contextlib.suppress(ImportError):
    from libs.data import key_aliases as _key_aliases
    _key_aliases.adopt()


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
    def digest(self) -> Path:
        """The small COMMITTED digest (reports/ is gitignored)."""
        return self.desk / "data" / "digests" / "asia_alt_data_digest.json"

    @property
    def survivors(self) -> Path:
        return self.desk / "reports" / "UNIVERSAL_SURVIVORS.json"

    @property
    def equity_handoff(self) -> Path:
        """COMMITTED hand-off to the cross-sectional equity book (share CFDs never mint here)."""
        return self.desk / "data" / "digests" / "alt_proxies_equity_handoff.json"

    @property
    def null_trials(self) -> Path:
        """Side ledger of trials from passes that donated nothing (`experiment_ledger` reads it)."""
        return self.desk / "data" / "null_pass_trials.jsonl"

    @property
    def sge_premium(self) -> Path:
        return self.desk / "data" / "lake" / "sge_premium.parquet"

    @property
    def nlp_series(self) -> Path:
        """`nlp_event_factors` writes its per-country tagger panel here (nlp_events_<CC>)."""
        return self.series


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
#: RELEASE CALENDARS (audit of PR #239, 2026-10-06). An official publisher in Seoul or Hong Kong
#: does not publish on a Saturday, a Sunday or a public holiday, so a release rule that lands on
#: one of those days is LOOK-AHEAD for the Sunday FX open: it is rolled forward to the next
#: business day of that calendar. The closed days come from the `holidays` package when it is
#: installed, joined with the country packs' own sourced closure tables
#: (`countries/<cc>/pack.py` HOLIDAYS_RULE: the public-holiday decree / General Holidays
#: Ordinance plus the exchange's own closures). A year neither source covers has NO calendar:
#: `merge_vintages` then stamps the row no earlier than the instant it was first seen.
_CAL_PACK = {"KR": "kr", "HK": "hk"}
_CAL_CACHE: dict[tuple[str, int], frozenset[str] | None] = {}


def _closed_days(cal: str, year: int) -> frozenset[str] | None:
    """ISO dates on which `cal`'s publishers are shut in `year` (weekends excluded), or None when
    no calendar for that year is available here."""
    key = (cal, year)
    if key in _CAL_CACHE:
        return _CAL_CACHE[key]
    days: set[str] = set()
    known = False
    with contextlib.suppress(Exception):
        import holidays as _holidays  # optional dependency
        for d in getattr(_holidays, cal)(years=year):
            days.add(d.isoformat())
        known = True
    cc = _CAL_PACK.get(cal)
    if cc:
        table: dict[str, str] = {}
        for mod in (f"research.countries.{cc}.pack", f"countries.{cc}.pack"):
            with contextlib.suppress(Exception):
                import importlib
                table = dict(importlib.import_module(mod).holidays(year) or {})
                break
        if table:
            days |= set(table)
            known = True
    out = frozenset(days) if known else None
    _CAL_CACHE[key] = out
    return out


def release_calendar_known(cal: str, year: int) -> bool:
    return _closed_days(cal, year) is not None


def roll_business_day(t: datetime, cal: str) -> datetime:
    """`t` moved forward, a day at a time with its clock time kept, until it is a weekday that is
    not a `cal` holiday. An unknown year is rolled over weekends only (merge_vintages adds the
    first-seen floor for it)."""
    for _ in range(31):
        if t.weekday() < 5 and t.date().isoformat() not in (_closed_days(cal, t.year) or ()):
            return t
        t += timedelta(days=1)
    return t


def _lag_rule(lag_days: int, hour: int = 0, weekday: bool = False,
              calendar: str | None = None) -> Callable[[date], datetime]:
    """period_end + lag through `pit_stamp.available_at`, the desk's one publication-lag helper.
    `calendar` ("KR"/"HK") rolls the instant past weekends AND that place's public holidays."""
    def rule(period: date) -> datetime:
        try:
            from libs.data.pit_stamp import available_at
            t = available_at(period, lag_days)
        except Exception:                                      # pragma: no cover - import guard
            t = _utc(period.year, period.month, period.day) + timedelta(days=lag_days)
        t = t.replace(hour=hour, minute=0, second=0, microsecond=0)
        if calendar:
            return roll_business_day(t, calendar)
        return _roll_weekday(t) if weekday else t
    rule.calendar = calendar  # type: ignore[attr-defined]
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



# ============================================================================ paid substitutes
# FREE SUBSTITUTES FOR FOUR PAID PANEL CLASSES. Each parser below reads a public page or API
# whose numbers stand in for a vendor panel (the `substitutes_for` field of its Source row):
#
#   news analytics (RavenPack)       GDELT 2.0 Events, 15-minute export files, folded into a
#                                    country x day x theme panel; Asian-language Wikipedia
#                                    attention read from the bronze files `ingest_axes` fetches
#   card-spend panels (Second        Opportunity Insights / Affinity card spend (archive), BOK
#   Measure, Earnest, BofA)          ECOS card series, METI commercial dynamics, NBS retail
#                                    sales, MCT/UnionPay holiday spend, NPCI UPI, BKM (TR),
#                                    Cielo ICVA (BR), ANTAD (MX), BankservAfrica BETI (ZA)
#   foot traffic (SafeGraph,         Google mobility via Opportunity Insights (archive), KOBIS
#   Placer.ai)                       box office, Seoul subway card taps, Maoyan box office,
#                                    Baidu migration
#   satellite / AIS (Orbital         Busan Port Authority, SingStat sea cargo, China MOT weekly
#   Insight, SpaceKnow)              port throughput (FIRMS and PortWatch were already here)
#
# A text parser reads the number and the page's own publication stamp and nothing else; a page
# whose wording does not match emits nothing, never a guess.

GDELT_URL = "http://data.gdeltproject.org/gdeltv2/{slot}.export.CSV.zip"
#: FIPS 10-4 country code (GDELT's ActionGeo_CountryCode) -> ISO code used for series names.
GDELT_COUNTRIES: dict[str, str] = {
    "CH": "CN", "HK": "HK", "JA": "JP", "KS": "KR", "TW": "TW", "IN": "IN", "US": "US",
    "BR": "BR", "RS": "RU", "SF": "ZA", "MX": "MX", "TU": "TR", "AS": "AU"}
#: A day is emitted only when this many of its 96 slots were read (a 404 slot counts as read,
#: empty -- GDELT has gaps); more gaps than this and the day is dropped, not guessed.
GDELT_MAX_MISSING_SLOTS = 8
GDELT_MIN_EVENTS = 20
GDELT_FWD_PER_PASS = 12
GDELT_BACK_PER_PASS = 12
GDELT_BACK_DEPTH_D = 730
#: CAMEO themes counted per country-day. Keyed on root code (2 chars) or base code (3 chars).
GDELT_THEMES: dict[str, tuple[str, ...]] = {
    "protest": ("14",), "coerce": ("17",), "violence": ("18", "19", "20"),
    "sanction": ("163",), "econ_coop": ("061",)}


def _gdelt_rows(body: bytes) -> list[list[str]]:
    import zipfile
    raw = body
    if body[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                names = zf.namelist()
                if not names:
                    return []
                raw = zf.read(names[0])
        except (zipfile.BadZipFile, OSError):
            return []
    out = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        cols = line.split("\t")
        if len(cols) >= 60 and cols[0].isdigit():
            out.append(cols)
    return out


def parse_gdelt_events(body: bytes, ctx: Ctx) -> list[Obs]:
    """ONE GDELT 2.0 Events export file (15 minutes) -> per-country PARTIAL SUMS.

    Series are `<ISO>|<sum>`; they are never merged as values. `gdelt_accumulate` adds them into
    the day they were added to GDELT (DATEADDED) and `gdelt_complete_days` turns a day whose 96
    slots have all been read into the country x day x theme panel. Columns (0-based, GDELT 2.0):
    26 EventCode, 27 EventBaseCode, 28 EventRootCode, 29 QuadClass, 30 GoldsteinScale,
    33 NumArticles, 34 AvgTone, 53 ActionGeo_CountryCode, 59 DATEADDED."""
    sums: dict[tuple[str, date], float] = {}
    for c in _gdelt_rows(body):
        iso = GDELT_COUNTRIES.get(c[53].strip())
        added = c[59].strip()
        if not iso or len(added) < 8 or not added[:8].isdigit():
            continue
        try:
            d = date(int(added[:4]), int(added[4:6]), int(added[6:8]))
        except ValueError:
            continue
        art = _num(c[33]) or 0.0
        tone, gold = _num(c[34]), _num(c[30])
        if art <= 0 or tone is None or gold is None:
            continue
        quad = c[29].strip()
        country: str = iso

        def add(k: str, v: float, iso: str = country, d: date = d) -> None:
            sums[(f"{iso}|{k}", d)] = sums.get((f"{iso}|{k}", d), 0.0) + v

        add("n", 1.0)
        add("art", art)
        add("tone_art", tone * art)
        add("gold_art", gold * art)
        add("conflict_art", art if quad in ("3", "4") else 0.0)
        root, base = c[28].strip().zfill(2), c[27].strip()
        for theme, codes in GDELT_THEMES.items():
            if root in codes or base in codes:
                add(f"theme_{theme}", 1.0)
    return [Obs(k, d, v) for (k, d), v in sums.items()]


def gdelt_slots(start: datetime, end: datetime) -> list[str]:
    """15-minute slot ids from `start` to `end` inclusive (both floored to the quarter hour)."""
    t = start.replace(minute=start.minute - start.minute % 15, second=0, microsecond=0)
    out = []
    while t <= end:
        out.append(t.strftime("%Y%m%d%H%M%S"))
        t += timedelta(minutes=15)
    return out


def gdelt_accumulate(acc: dict[str, Any], slot: str, obs: Iterable[Obs] | None) -> None:
    """Add one slot's partial sums to its day. `obs=None` is a slot GDELT does not have (404):
    read, empty, and counted against the day's gap allowance. Idempotent per slot."""
    day = f"{slot[:4]}-{slot[4:6]}-{slot[6:8]}"
    e = acc.setdefault(day, {"slots": [], "missing": [], "sums": {}})
    if slot in e["slots"] or slot in e["missing"]:
        return
    if obs is None:
        e["missing"].append(slot)
        return
    e["slots"].append(slot)
    for o in obs:
        e["sums"][o.series] = e["sums"].get(o.series, 0.0) + o.value


def gdelt_complete_days(acc: dict[str, Any]) -> tuple[list[Obs], list[str]]:
    """Obs for every day whose 96 slots are read; the day leaves the accumulator either way.
    Returns (panel obs, days dropped for too many gaps)."""
    out: list[Obs] = []
    dropped: list[str] = []
    for day in sorted(acc):
        e = acc[day]
        if len(e["slots"]) + len(e["missing"]) < 96:
            continue
        del acc[day]
        if len(e["missing"]) > GDELT_MAX_MISSING_SLOTS:
            dropped.append(day)
            continue
        d = date.fromisoformat(day)
        by: dict[str, dict[str, float]] = {}
        for k, v in e["sums"].items():
            iso, _, name = k.partition("|")
            by.setdefault(iso, {})[name] = v
        for iso, s in sorted(by.items()):
            n, art = s.get("n", 0.0), s.get("art", 0.0)
            if n < GDELT_MIN_EVENTS or art <= 0:
                continue
            out.append(Obs(f"{iso}_events", d, n))
            out.append(Obs(f"{iso}_tone", d, round(s.get("tone_art", 0.0) / art, 6)))
            out.append(Obs(f"{iso}_goldstein", d, round(s.get("gold_art", 0.0) / art, 6)))
            out.append(Obs(f"{iso}_conflict_share", d,
                           round(s.get("conflict_art", 0.0) / art, 6)))
            for theme in GDELT_THEMES:
                out.append(Obs(f"{iso}_theme_{theme}", d, s.get(f"theme_{theme}", 0.0)))
    return out, dropped


#: Asian-language articles read for local attention: (label, project, exact title). The English
#: macro list stays with `scripts/ingest_axes.py` (VPS bronze); these are different articles for a
#: consumer on the trading box, so nothing is fetched twice.
WIKI_ASIA_ARTICLES: tuple[tuple[str, str, str], ...] = (
    ("ja_boj", "ja.wikipedia", "日本銀行"), ("ja_nikkei", "ja.wikipedia", "日経平均株価"),
    ("zh_pboc", "zh.wikipedia", "中国人民银行"), ("zh_rmb", "zh.wikipedia", "人民币"),
    ("zh_hsi", "zh.wikipedia", "恒生指数"), ("ko_bok", "ko.wikipedia", "한국은행"),
    ("ko_kospi", "ko.wikipedia", "코스피"))
WIKI_URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/"
            "all-access/user/{title}/daily/{start}/{end}")


def parse_wikimedia(body: bytes, ctx: Ctx) -> list[Obs]:
    """Wikimedia pageviews per-article JSON (`items[].timestamp YYYYMMDD00`, `views`).
    `ctx.part` is the article label; the API serves complete days only."""
    try:
        items = json.loads(body.decode("utf-8", errors="replace")).get("items")
    except (ValueError, AttributeError):
        return []
    label = ctx.part or "article"
    out: list[Obs] = []
    for it in items if isinstance(items, list) else []:
        ts = str((it or {}).get("timestamp") or "")
        v = _num(str((it or {}).get("views") if isinstance(it, dict) else ""))
        with contextlib.suppress(ValueError):
            if len(ts) >= 8 and ts[:8].isdigit() and v is not None:
                out.append(Obs(f"{label}_views", date(int(ts[:4]), int(ts[4:6]), int(ts[6:8])),
                               v))
    return out


def _oi_csv(body: bytes, cols: dict[str, str]) -> list[Obs]:
    """Opportunity Insights EconomicTracker CSV (year,month,day,...; '.' is missing)."""
    import csv
    text = body.decode("utf-8", errors="replace")
    if not text.startswith("year,month,day"):
        return []
    out: list[Obs] = []
    for r in csv.DictReader(io.StringIO(text)):
        try:
            d = date(int(r["year"]), int(r["month"]), int(r["day"]))
        except (KeyError, TypeError, ValueError):
            continue
        for col, name in cols.items():
            v = _num(str(r.get(col) or ""))
            if v is not None:
                out.append(Obs(name, d, v))
    return out


OI_SPEND_COLS = {"spend_all": "spend_all", "spend_retail_no_grocery": "spend_retail_no_grocery",
                 "spend_inperson": "spend_inperson", "spend_acf": "spend_food_accommodation",
                 "spend_aer": "spend_arts_entertainment", "spend_all_q1": "spend_low_income",
                 "spend_all_q4": "spend_high_income"}
OI_MOBILITY_COLS = {"gps_retail_and_recreation": "retail_and_recreation",
                    "gps_transit_stations": "transit_stations", "gps_workplaces": "workplaces",
                    "gps_grocery_and_pharmacy": "grocery_and_pharmacy"}


def parse_oi_spend(body: bytes, ctx: Ctx) -> list[Obs]:
    """Affinity card spend (7-day average, seasonally adjusted, change vs January 2020)."""
    return _oi_csv(body, OI_SPEND_COLS)


def parse_oi_mobility(body: bytes, ctx: Ctx) -> list[Obs]:
    """Google community-mobility visits by place category (change vs the Jan-Feb 2020 base)."""
    return _oi_csv(body, OI_MOBILITY_COLS)


def parse_ecos(body: bytes, ctx: Ctx) -> list[Obs]:
    """BOK ECOS StatisticSearch JSON for ONE item (the URL filters to it). TIME is YYYYMM
    (monthly) or YYYYMMDD; an ECOS error document (RESULT.CODE) parses to nothing."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = ((doc or {}).get("StatisticSearch") or {}).get("row") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        t, v = str(r.get("TIME") or ""), _num(str(r.get("DATA_VALUE") or ""))
        if v is None or not t.isdigit():
            continue
        with contextlib.suppress(ValueError):
            if len(t) == 6:
                out.append(Obs("card_spend", _month_end(int(t[:4]), int(t[4:])), v))
            elif len(t) == 8:
                out.append(Obs("card_spend", date(int(t[:4]), int(t[4:6]), int(t[6:])), v))
    return out


def _page_date_after(text: str, period: date, pat: re.Pattern[str],
                     hour_utc: int = 0) -> datetime | None:
    """The first full date on a page later than the period it describes (the release stamp)."""
    for dm in pat.finditer(text):
        with contextlib.suppress(ValueError):
            cand = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), hour_utc)
            if period < cand.date() <= period + timedelta(days=MAX_PUB_LAG_D):
                return cand
    return None


_METI_RETAIL = re.compile(r"小売業(?:販売額)?[^。]{0,80}?前年同月比\s*([▲△\-]?)\s*([\d.]+)\s*%"
                          r"\s*(?:の)?\s*(増加|減少|上昇|低下)?")
_JP_MONTH = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")


def parse_meti_retail(body: bytes, ctx: Ctx) -> list[Obs]:
    """METI 商業動態統計 (commercial dynamics) flash: retail sales, year on year. `▲` is minus.
    The month is the LAST `YYYY年M月` written before the retail sentence (a release names the
    month once, then says `うち小売業販売額は...` in the next sentence)."""
    text = _text(body)
    out: list[Obs] = []
    for m in _METI_RETAIL.finditer(text):
        months = list(_JP_MONTH.finditer(text, 0, m.start()))
        if not months:
            continue
        y, mo = int(months[-1].group(1)), int(months[-1].group(2))
        v = _num(m.group(2))
        if v is None or not 1 <= mo <= 12:
            continue
        neg = m.group(1) in ("▲", "△", "-") or m.group(3) in ("減少", "低下")
        period = _month_end(y, mo)
        out.append(Obs("retail_yoy", period, -v if neg else v,
                       _page_date_after(text, period, _JP_DATE)))
    return _first_per_key(out)


def _first_per_key(obs: list[Obs]) -> list[Obs]:
    seen: set[tuple[str, date]] = set()
    out = []
    for o in obs:
        if (o.series, o.period) not in seen:
            seen.add((o.series, o.period))
            out.append(o)
    return out


_CN_DATE = re.compile(r"(\d{4})[-年/.]\s*(\d{1,2})[-月/.]\s*(\d{1,2})日?")
_NBS_RETAIL = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月份?\s*[，,]?\s*社会消费品零售总额\s*"  # noqa: RUF001
                         r"([\d.]+)\s*亿元\s*[，,]?\s*同比(增长|下降)\s*([\d.]+)\s*%")  # noqa: RUF001


def parse_nbs_retail(body: bytes, ctx: Ctx) -> list[Obs]:
    """NBS monthly release: total retail sales of consumer goods, level (100m yuan) and YoY.
    A cumulative `1—8月份` figure is not matched (the month must stand alone)."""
    text = _text(body)
    out: list[Obs] = []
    for m in _NBS_RETAIL.finditer(text):
        y, mo = int(m.group(1)), int(m.group(2))
        lvl, yoy = _num(m.group(3)), _num(m.group(5))
        if not 1 <= mo <= 12 or lvl is None or yoy is None:
            continue
        # "1-8月份" ends in "8月份" too: a dash or 至 right before the month is cumulative.
        if re.search(r"[—\-－~至]\s*$", text[max(0, m.start(2) - 2): m.start(2)]):  # noqa: RUF001
            continue
        period = _month_end(y, mo)
        pub = _page_date_after(text, period, _CN_DATE, 2)
        out.append(Obs("retail_level_100m_cny", period, lvl, pub))
        out.append(Obs("retail_yoy", period, -yoy if m.group(4) == "下降" else yoy, pub))
    return _first_per_key(out)


_CN_HOLIDAY = re.compile(r"(春节|清明节?|劳动节|五一|端午节?|中秋节?|国庆节?)[^。]{0,120}?"
                         r"国内(?:旅游)?出游\s*([\d.]+)\s*(亿|万)人次\s*[，,]?\s*同比增长\s*"  # noqa: RUF001
                         r"([\d.]+)\s*%[^。]{0,120}?(?:国内游客)?出游总花费\s*([\d.]+)\s*亿元\s*"
                         r"[，,]?\s*同比增长\s*([\d.]+)\s*%")  # noqa: RUF001
_CN_UNIONPAY = re.compile(r"(?:银联|网联)[^。]{0,80}?(?:金额|交易额)[^。]{0,30}?同比增长\s*"
                          r"([\d.]+)\s*%")


def parse_cn_holiday(body: bytes, ctx: Ctx) -> list[Obs]:
    """MCT (文旅部) holiday tourism tally and the UnionPay/NetsUnion holiday payment release.

    The period is the day BEFORE the page's own date (the holiday's last day; MCT publishes that
    evening or the next day) and the release instant is the page date. A page with no date emits
    nothing: the holiday calendar moves with the lunar year and is not guessed."""
    text = _text(body)
    dm = _CN_DATE.search(text)
    if not dm:
        return []
    try:
        pub = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), 12)
    except ValueError:
        return []
    period = pub.date() - timedelta(days=1)
    out: list[Obs] = []
    h = _CN_HOLIDAY.search(text)
    if h:
        ty, sy = _num(h.group(4)), _num(h.group(6))
        if ty is not None and sy is not None:
            out.append(Obs("trips_yoy", period, ty, pub))
            out.append(Obs("spend_yoy", period, sy, pub))
            out.append(Obs("spend_per_trip_yoy", period,
                           round(((1 + sy / 100) / (1 + ty / 100) - 1) * 100, 4), pub))
    u = _CN_UNIONPAY.search(text)
    if u and (uv := _num(u.group(1))) is not None:
        out.append(Obs("unionpay_amount_yoy", period, uv, pub))
    return out


_EN_MONTHS3 = {m[:3]: i for m, i in _MONTHS.items()}
_NPCI_ROW = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[\s\-']+"
                       r"(\d{2}|\d{4})\b\s+(\d{1,4})\s+([\d,]+\.\d+)\s+([\d,]+\.\d+)", re.I)


def parse_npci_upi(body: bytes, ctx: Ctx) -> list[Obs]:
    """NPCI UPI product statistics table: month | banks live | volume (Mn) | value (Cr)."""
    text = _text(body)
    out: list[Obs] = []
    for m in _NPCI_ROW.finditer(text):
        mo = _EN_MONTHS3.get(m.group(1).lower()[:3])
        y = int(m.group(2)) + (2000 if len(m.group(2)) == 2 else 0)
        vol, val = _num(m.group(4)), _num(m.group(5))
        if mo and vol is not None and val is not None:
            out.append(Obs("upi_volume_mn", _month_end(y, mo), vol))
            out.append(Obs("upi_value_cr", _month_end(y, mo), val))
    return _first_per_key(out)


_TR_MONTHS = {m: i for i, m in enumerate(("ocak", "şubat", "mart", "nisan", "mayıs", "haziran",  # noqa: RUF001
                                          "temmuz", "ağustos", "eylül", "ekim", "kasım",  # noqa: RUF001
                                          "aralık"), start=1)}  # noqa: RUF001
_BKM = re.compile(r"(Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)"  # noqa: RUF001
                  r"\s+(?:ayında\s+)?(\d{4})?[^.]{0,220}?kartl[ıi]\s+ödeme[^.]{0,160}?"  # noqa: RUF001
                  r"%\s*([\d]+(?:[.,]\d+)?)\s*(artış|art|azal|düş)", re.I)  # noqa: RUF001
_TR_YEAR = re.compile(r"\b(20\d{2})\b")
_TR_DATE = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")


def parse_bkm(body: bytes, ctx: Ctx) -> list[Obs]:
    """BKM (Interbank Card Center, Turkey) monthly card-payment release, NOMINAL YoY %. Turkish
    decimals use a comma. Year: the one in the phrase, else the first year on the page."""
    text = _text(body)
    out: list[Obs] = []
    for m in _BKM.finditer(text):
        mo = _TR_MONTHS.get(m.group(1).lower().replace("i̇", "i"))
        yr = m.group(2) or (_TR_YEAR.search(text) or [None, None])[1]
        v = _num((m.group(3) or "").replace(",", "."))
        if not mo or not yr or v is None:
            continue
        period = _month_end(int(yr), mo)
        pub = None
        for dm in _TR_DATE.finditer(text):
            with contextlib.suppress(ValueError):
                c = _utc(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)), 12)
                if period < c.date() <= period + timedelta(days=MAX_PUB_LAG_D):
                    pub = c
                    break
        neg = m.group(4).lower().startswith(("azal", "düş"))
        out.append(Obs("card_payments_nominal_yoy", period, -v if neg else v, pub))
    return _first_per_key(out)


_PT_MONTHS = {m: i for i, m in enumerate(("janeiro", "fevereiro", "março", "abril", "maio",
                                          "junho", "julho", "agosto", "setembro", "outubro",
                                          "novembro", "dezembro"), start=1)}
_ICVA_MONTH = re.compile(r"(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|"
                         r"outubro|novembro|dezembro)\s+(?:de\s+)?(\d{4})", re.I)
_ICVA_DEF = re.compile(r"ICVA\s+deflacionado[^.]{0,120}?(alta|crescimento|aumento|avanço|queda|"
                       r"recuo|retração)\s+de\s+([\d]+(?:,\d+)?)\s*%", re.I)
_ICVA_NOM = re.compile(r"ICVA\s+nominal[^.]{0,120}?(alta|crescimento|aumento|avanço|queda|"
                       r"recuo|retração)\s+de\s+([\d]+(?:,\d+)?)\s*%", re.I)
_BR_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def parse_icva(body: bytes, ctx: Ctx) -> list[Obs]:
    """Cielo ICVA (Índice Cielo do Varejo Ampliado): retail card-sales index, YoY, deflated and
    nominal, from Cielo's monthly Portuguese release."""
    text = _text(body)
    mm = _ICVA_MONTH.search(text)
    if not mm:
        return []
    period = _month_end(int(mm.group(2)), _PT_MONTHS[mm.group(1).lower()])
    pub = None
    for dm in _BR_DATE.finditer(text):
        with contextlib.suppress(ValueError):
            c = _utc(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)), 12)
            if period < c.date() <= period + timedelta(days=MAX_PUB_LAG_D):
                pub = c
                break
    out = []
    for pat, name in ((_ICVA_DEF, "icva_deflated_yoy"), (_ICVA_NOM, "icva_nominal_yoy")):
        m = pat.search(text)
        if m and (v := _num(m.group(2).replace(",", "."))) is not None:
            neg = m.group(1).lower() in ("queda", "recuo", "retração")
            out.append(Obs(name, period, -v if neg else v, pub))
    return out


_ES_MONTHS = {m: i for i, m in enumerate(("enero", "febrero", "marzo", "abril", "mayo", "junio",
                                          "julio", "agosto", "septiembre", "octubre",
                                          "noviembre", "diciembre"), start=1)}
_ANTAD = re.compile(r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
                    r"noviembre|diciembre)\s+(?:de\s+)?(\d{4})[^.]{0,200}?tiendas\s+iguales"
                    r"[^.]{0,80}?(crecimiento|incremento|aumento|alza|caída|decremento|baja)?"
                    r"\s*(?:de|del)?\s*(-?[\d]+(?:\.\d+)?)\s*%", re.I)


def parse_antad(body: bytes, ctx: Ctx) -> list[Obs]:
    """ANTAD (Mexico) monthly same-store (`tiendas iguales`) sales growth, nominal YoY %."""
    text = _text(body)
    out: list[Obs] = []
    for m in _ANTAD.finditer(text):
        v = _num(m.group(4))
        if v is None:
            continue
        period = _month_end(int(m.group(2)), _ES_MONTHS[m.group(1).lower()])
        neg = (m.group(3) or "").lower() in ("caída", "decremento", "baja") and v > 0
        out.append(Obs("same_store_sales_yoy", period, -v if neg else v))
    return _first_per_key(out)


_BETI = re.compile(r"BETI[^.]{0,200}?(increased|rose|grew|gained|decreased|fell|declined|"
                   r"dropped|contracted)\s+(?:by\s+)?([\d.]+)\s*%\s*(?:month[- ]on[- ]month|m/m)"
                   r"[^.]{0,80}?\bin\s+(January|February|March|April|May|June|July|August|"
                   r"September|October|November|December)\s+(\d{4})?", re.I)


def parse_beti(body: bytes, ctx: Ctx) -> list[Obs]:
    """BankservAfrica / PayInc Economic Transactions Index (South Africa), month-on-month %."""
    text = _text(body)
    out: list[Obs] = []
    for m in _BETI.finditer(text):
        v = _num(m.group(2))
        yr = m.group(4) or (_TR_YEAR.search(text) or [None, None])[1]
        if v is None or not yr:
            continue
        period = _month_end(int(yr), _MONTHS[m.group(3).lower()])
        neg = m.group(1).lower() in ("decreased", "fell", "declined", "dropped", "contracted")
        out.append(Obs("beti_mom", period, -v if neg else v))
    return _first_per_key(out)


def parse_kobis(body: bytes, ctx: Ctx) -> list[Obs]:
    """KOBIS daily box office (top 10): summed audience and sales for the day in showRange."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    res = (doc or {}).get("boxOfficeResult") if isinstance(doc, dict) else None
    if not isinstance(res, dict):
        return []
    rng = str(res.get("showRange") or "")[:8]
    rows = res.get("dailyBoxOfficeList")
    if not rng.isdigit() or not isinstance(rows, list) or not rows:
        return []
    try:
        d = date(int(rng[:4]), int(rng[4:6]), int(rng[6:8]))
    except ValueError:
        return []
    aud = sum(_num(str(r.get("audiCnt") or "")) or 0.0 for r in rows if isinstance(r, dict))
    sales = sum(_num(str(r.get("salesAmt") or "")) or 0.0 for r in rows if isinstance(r, dict))
    return [Obs("audience_top10", d, aud), Obs("sales_top10_krw", d, sales)]


def parse_seoul_subway(body: bytes, ctx: Ctx) -> list[Obs]:
    """Seoul open data CardSubwayStatsNew: boardings per station per day, summed to the city.
    A page that does not hold every row of the day (list_total_count) emits nothing -- a partial
    sum frozen as a first vintage would be a false low. Old and new field names both read."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    blk = (doc or {}).get("CardSubwayStatsNew") if isinstance(doc, dict) else None
    rows = (blk or {}).get("row") if isinstance(blk, dict) else None
    if not isinstance(rows, list) or not rows:
        return []
    total = int(_num(str((blk or {}).get("list_total_count") or "")) or 0)
    if total and len(rows) < total:
        return []
    days: dict[date, float] = {}
    regs: dict[date, date] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        ds = str(r.get("USE_YMD") or r.get("USE_DT") or "")
        v = _num(str(r.get("GTON_TNOPE") if r.get("GTON_TNOPE") is not None
                     else r.get("RIDE_PASGR_NUM") or ""))
        if len(ds) != 8 or not ds.isdigit() or v is None:
            continue
        with contextlib.suppress(ValueError):
            d = date(int(ds[:4]), int(ds[4:6]), int(ds[6:]))
            days[d] = days.get(d, 0.0) + v
            rs = str(r.get("REG_YMD") or r.get("WORK_DT") or "")
            if len(rs) == 8 and rs.isdigit():
                regs[d] = date(int(rs[:4]), int(rs[4:6]), int(rs[6:]))
    # REG_YMD is the registration DATE in KST; its end (15:00 UTC) is late by construction.
    return [Obs("boardings", d, v,
                _utc(regs[d].year, regs[d].month, regs[d].day, 15) if d in regs else None)
            for d, v in sorted(days.items())]


def parse_maoyan(body: bytes, ctx: Ctx) -> list[Obs]:
    """Maoyan Pro daily dashboard: the national box office of the day the response names.

    LENIENT, SHAPE UNCONFIRMED AGAINST A LIVE RESPONSE: reads `nationBoxSplitUnit {num, unit}`
    (unit 万/亿) and the day from `showDate`/`selectDate`; anything else emits nothing. Only a
    day already over (before `ctx.fetched_at`'s date) is emitted -- today's number is partial."""
    raw = body.decode("utf-8", errors="replace")
    dm = re.search(r'"(?:showDate|selectDate|queryDate)"\s*:\s*"?(\d{4})-?(\d{2})-?(\d{2})', raw)
    bm = re.search(r'"nationBoxSplitUnit"\s*:\s*\{\s*"num"\s*:\s*"?([\d.]+)"?\s*,\s*'
                   r'"unit"\s*:\s*"(万|亿)"', raw)
    if not dm or not bm:
        return []
    try:
        d = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        return []
    v = _num(bm.group(1))
    if v is None or d >= ctx.fetched_at.date():
        return []
    return [Obs("box_office_cny_10k", d, v * (10_000.0 if bm.group(2) == "亿" else 1.0))]


BAIDU_CITIES: dict[str, str] = {"beijing": "110000", "shanghai": "310000",
                                "guangzhou": "440100", "shenzhen": "440300", "wuhan": "420100"}


def parse_baidu_migration(body: bytes, ctx: Ctx) -> list[Obs]:
    """Baidu migration (百度迁徙) history curve, JSONP: `cb({"data":{"list":{"YYYYMMDD": v}}})`.
    `ctx.part` names the city."""
    raw = body.decode("utf-8", errors="replace").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        doc = json.loads(m.group(0))
    except ValueError:
        return []
    lst = ((doc or {}).get("data") or {}).get("list") if isinstance(doc, dict) else None
    if not isinstance(lst, dict):
        return []
    city = ctx.part if ctx.part in BAIDU_CITIES else "city"
    out: list[Obs] = []
    for k, v in lst.items():
        x = _num(str(v))
        with contextlib.suppress(ValueError):
            if len(str(k)) == 8 and x is not None:
                d = date(int(str(k)[:4]), int(str(k)[4:6]), int(str(k)[6:]))
                if d < ctx.fetched_at.date():
                    out.append(Obs(f"{city}_move_in", d, x))
    return out


_BUSAN = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월[^.]{0,120}?(?:물동량|처리\s*실적|처리량)"
                    r"[^.]{0,40}?([\d,.]+)\s*만\s*(?:TEU|teu)[^.]{0,80}?전년\s*동월\s*대비\s*"
                    r"([\d.]+)\s*%\s*(증가|감소)")


def parse_busan_port(body: bytes, ctx: Ctx) -> list[Obs]:
    """Busan Port Authority monthly container throughput (Korean release): 10k TEU and YoY."""
    text = _text(body)
    out: list[Obs] = []
    for m in _BUSAN.finditer(text):
        y, mo = int(m.group(1)), int(m.group(2))
        lvl, yoy = _num(m.group(3)), _signed(m.group(4), m.group(5))
        if not 1 <= mo <= 12 or lvl is None or yoy is None:
            continue
        period = _month_end(y, mo)
        pub = None
        dm = _KR_DATE.search(text)
        if dm:
            with contextlib.suppress(ValueError):
                c = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                pub = c if c.date() > period else None
        out.append(Obs("container_10k_teu", period, lvl, pub))
        out.append(Obs("container_yoy", period, yoy, pub))
    return _first_per_key(out)


_SS_MONTH = re.compile(r"^(\d{4})\s*([A-Za-z]{3})")


def parse_singstat_port(body: bytes, ctx: Ctx) -> list[Obs]:
    """SingStat TableBuilder JSON (`Data.row[].rowText`, `columns[].key 'YYYY Mon'`): Singapore
    container throughput and total cargo, monthly."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = ((doc or {}).get("Data") or {}).get("row") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for r in rows if isinstance(rows, list) else []:
        name = str((r or {}).get("rowText") or "").lower()
        series = ("container_throughput_k_teu" if "container" in name else
                  "total_cargo_kt" if "total cargo" in name else None)
        if series is None:
            continue
        for c in (r or {}).get("columns") or []:
            m = _SS_MONTH.match(str((c or {}).get("key") or ""))
            v = _num(str((c or {}).get("value") or ""))
            mo = _EN_MONTHS3.get(m.group(2).lower()) if m else None
            if m and mo and v is not None:
                out.append(Obs(series, _month_end(int(m.group(1)), mo), v))
    return _first_per_key(out)


_MOT_WEEK = re.compile(r"(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*[—\-－~至]+\s*(?:(\d{1,2})\s*月\s*)?"  # noqa: RUF001
                       r"(\d{1,2})\s*日")
_MOT_CARGO = re.compile(r"港口(?:完成)?货物吞吐量\s*([\d.]+)\s*亿吨\s*[，,]?\s*环比(增长|下降)\s*"  # noqa: RUF001
                        r"([\d.]+)\s*%")
_MOT_BOX = re.compile(r"集装箱吞吐量\s*([\d.]+)\s*万标箱\s*[，,]?\s*环比(增长|下降)\s*([\d.]+)\s*%")  # noqa: RUF001


def parse_mot_port(body: bytes, ctx: Ctx) -> list[Obs]:
    """China MOT weekly logistics bulletin: national port cargo (100m t) and container (10k TEU)
    throughput with week-on-week %. The week's last day is the period; the year comes from the
    page's own date, which is also the release stamp."""
    text = _text(body)
    wk, dm = _MOT_WEEK.search(text), _CN_DATE.search(text)
    if not wk or not dm:
        return []
    try:
        pub = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), 12)
        end_m = int(wk.group(3) or wk.group(1))
        y = pub.year - (1 if end_m > pub.month else 0)
        period = date(y, end_m, int(wk.group(4)))
    except ValueError:
        return []
    if not period < pub.date() <= period + timedelta(days=MAX_PUB_LAG_D):
        pub = None                                            # type: ignore[assignment]
    out: list[Obs] = []
    c = _MOT_CARGO.search(text)
    if c and (lv := _num(c.group(1))) is not None and (w := _num(c.group(3))) is not None:
        out.append(Obs("port_cargo_100m_t", period, lv, pub))
        out.append(Obs("port_cargo_wow", period, -w if c.group(2) == "下降" else w, pub))
    b = _MOT_BOX.search(text)
    if b and (lv2 := _num(b.group(1))) is not None and (w2 := _num(b.group(3))) is not None:
        out.append(Obs("container_10k_teu", period, lv2, pub))
        out.append(Obs("container_wow", period, -w2 if b.group(2) == "下降" else w2, pub))
    return out


# ------------------------------------------------ lawful substitutes for BLOCKED sources
def parse_estat_level(body: bytes, ctx: Ctx) -> list[Obs]:
    """e-Stat getStatsData JSON for a LEVEL table (the immigration statistics' foreign entries).
    The request filters to one category; if the table still carries sub-rows per month (ports,
    nationalities), the month's LARGEST cell is taken, because a total row is never smaller than
    its parts and a partial sum is never invented. A non-zero RESULT.STATUS is an error."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    root = (doc or {}).get("GET_STATS_DATA") if isinstance(doc, dict) else None
    if not isinstance(root, dict):
        return []
    if str(((root.get("RESULT") or {}).get("STATUS")) or "0") not in ("0", "1"):
        return []
    values = (((root.get("STATISTICAL_DATA") or {}).get("DATA_INF") or {}).get("VALUE") or [])
    if isinstance(values, dict):
        values = [values]
    best: dict[date, float] = {}
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, dict):
            continue
        tcode, x = str(v.get("@time") or ""), _num(str(v.get("$") or ""))
        if len(tcode) != 10 or x is None or not tcode[:4].isdigit() or not tcode[6:8].isdigit():
            continue
        y, m = int(tcode[:4]), int(tcode[6:8])
        if 1 <= m <= 12:
            d = _month_end(y, m)
            best[d] = max(best.get(d, x), x)
    return [Obs("foreign_entries", d, v) for d, v in sorted(best.items())]


_HK_DATE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$")


def parse_hk_immd(body: bytes, ctx: Ctx) -> list[Obs]:
    """HK Immigration Department daily passenger traffic CSV (DATA.GOV.HK). Columns: Date
    (DD-MM-YYYY), Control Point, Arrival / Departure, Hong Kong Residents, Mainland Visitors,
    Other Visitors, Total. Summed over every control point per day: mainland visitor ARRIVALS
    (Chinese outbound travel and spend) and HK resident DEPARTURES (northbound spending). The
    fetch day itself is never emitted -- a day still being filled would freeze a false low."""
    import csv as _csv
    text = body.decode("utf-8-sig", errors="replace")
    rdr = _csv.reader(io.StringIO(text))
    head = next(rdr, None)
    if not head:
        return []
    cols = [h.strip().lower() for h in head]

    def idx(*words: str) -> int | None:
        for i, h in enumerate(cols):
            if all(w in h for w in words):
                return i
        return None

    i_d, i_ad = idx("date"), idx("arrival")
    i_hk, i_ml = idx("hong kong resident"), idx("mainland")
    if None in (i_d, i_ad, i_hk, i_ml):
        return []
    assert i_d is not None and i_ad is not None and i_hk is not None and i_ml is not None
    arr: dict[date, float] = {}
    dep: dict[date, float] = {}
    today = ctx.fetched_at.date()
    for r in rdr:
        if len(r) <= max(i_d, i_ad, i_hk, i_ml):
            continue
        m = _HK_DATE.match(r[i_d].strip())
        ml, hk = _num(r[i_ml]), _num(r[i_hk])
        if not m or ml is None or hk is None:
            continue
        try:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        if d >= today:
            continue
        way = r[i_ad].strip().lower()
        if way.startswith("arr"):
            arr[d] = arr.get(d, 0.0) + ml
        elif way.startswith("dep"):
            dep[d] = dep.get(d, 0.0) + hk
    return ([Obs("mainland_visitor_arrivals", d, v) for d, v in sorted(arr.items())]
            + [Obs("hk_resident_departures", d, v) for d, v in sorted(dep.items())])


_BR_PERIOD_KEYS = ("anomes", "ano_mes", "datames", "data_mes", "mes", "data", "database")
_BR_VALUE_WORDS = ("cartao", "cartoes", "credito", "debito", "prepago", "pix", "boleto")


def _br_period(v: Any) -> date | None:
    s = str(v or "").strip().replace("-", "").replace("/", "")[:6]
    if len(s) != 6 or not s.isdigit():
        return None
    y, m = int(s[:4]), int(s[4:])
    return _month_end(y, m) if 1 <= m <= 12 and y > 1990 else None


def parse_bcb_mpv(body: bytes, ctx: Ctx) -> list[Obs]:
    """BCB Olinda `MPV_DadosAbertos` monthly payments (ODbL). OData `{"value": [...]}`. The period
    is the row's year-month field; the value is the sum of every `valor*` field naming a retail
    instrument (card, Pix, boleto) -- field names are matched, never assumed by position, and a
    reply with no such field parses to nothing. Values are BRL, summed per month."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = doc.get("value") if isinstance(doc, dict) else None
    tot: dict[date, float] = {}
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        low = {str(k).lower(): v for k, v in r.items()}
        d = next((p for k in _BR_PERIOD_KEYS if k in low
                  and (p := _br_period(low[k])) is not None), None)
        if d is None:
            continue
        vals = [x for k, v in low.items() if k.startswith("valor")
                and any(w in k for w in _BR_VALUE_WORDS)
                and (x := _num(str(v))) is not None]
        if vals:
            tot[d] = tot.get(d, 0.0) + sum(vals)
    return [Obs("retail_payments_value_brl", d, v) for d, v in sorted(tot.items())]


def parse_inegi_bie(body: bytes, ctx: Ctx) -> list[Obs]:
    """INEGI Banco de Indicadores API v2.0 JSON for ONE configured EMEC indicator:
    `Series[0].OBSERVATIONS[].{TIME_PERIOD "YYYY/MM", OBS_VALUE}`. An error reply is nothing."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    series = doc.get("Series") if isinstance(doc, dict) else None
    if not isinstance(series, list) or not series or not isinstance(series[0], dict):
        return []
    out: list[Obs] = []
    for o in series[0].get("OBSERVATIONS") or []:
        if not isinstance(o, dict):
            continue
        tp, x = str(o.get("TIME_PERIOD") or ""), _num(str(o.get("OBS_VALUE") or ""))
        parts = tp.split("/")
        if x is None or len(parts) != 2 or not all(p.isdigit() for p in parts):
            continue
        y, m = int(parts[0]), int(parts[1])
        if 1 <= m <= 12:
            out.append(Obs("retail_index", _month_end(y, m), x))
    return out


_TUIK_TITLE = re.compile(r"Perakende\s+Satış\s+Endeksleri\s*,\s*(Ocak|Şubat|Mart|Nisan|Mayıs|"  # noqa: RUF001
                         r"Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık)\s+(20\d{2})",  # noqa: RUF001
                         re.IGNORECASE)
_TUIK_YOY = re.compile(r"perakende\s+satış\s+hacmi[^%]{0,120}?yıllık\s*%\s*([\d]+(?:,\d+)?)\s*"  # noqa: RUF001
                       r"(arttı|azaldı)", re.IGNORECASE)  # noqa: RUF001


def parse_tuik_retail(body: bytes, ctx: Ctx) -> list[Obs]:
    """TÜİK retail sales index bulletin: constant-price retail sales volume, year-on-year %.
    The month comes from the bulletin title; the release stamp is the bulletin's own date when
    it prints one after the period. Turkish decimals use a comma."""
    text = _text(body)
    t, y = _TUIK_TITLE.search(text), _TUIK_YOY.search(text)
    if not t or not y:
        return []
    mon = _TR_MONTHS.get(t.group(1).lower())
    v = _num(y.group(1).replace(",", "."))
    if mon is None or v is None:
        return []
    period = _month_end(int(t.group(2)), mon)
    pub = None
    for dm in _TR_DATE.finditer(text):
        with contextlib.suppress(ValueError):
            cand = _utc(int(dm.group(3)), int(dm.group(2)), int(dm.group(1)), 10)
            if period < cand.date() <= period + timedelta(days=MAX_PUB_LAG_D):
                pub = cand
                break
    return [Obs("retail_volume_yoy", period, -v if y.group(2).lower() == "azaldı" else v, pub)]  # noqa: RUF001


_KR_MOF_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_KR_MOF_TAG = re.compile(r"<(useYm|eContnTeuTotal|tContnTeuTotal)>\s*([^<]*?)\s*</\1>")


def parse_kr_mof_container(body: bytes, ctx: Ctx) -> list[Obs]:
    """data.go.kr MOF `SsopCargContnImxprt2`: import (eContnTeuTotal) plus export
    (tContnTeuTotal) container TEU per `useYm`, summed over every row of the month (the reply is
    per region/port). JSON (`response.body.items.item`) or XML (`<item>`) replies both read; a
    page that does not hold every row (totalCount) emits nothing: a partial month is a false
    low."""
    raw = body.decode("utf-8", errors="replace")
    items: list[dict[str, Any]] = []
    total = 0
    try:
        doc = json.loads(raw)
        bd = ((doc or {}).get("response") or {}).get("body") or {}
        it = (bd.get("items") or {}).get("item") if isinstance(bd.get("items"), dict) else None
        items = [it] if isinstance(it, dict) else [x for x in (it or []) if isinstance(x, dict)]
        total = int(_num(str(bd.get("totalCount") or "")) or 0)
    except (ValueError, AttributeError):
        for blk in _KR_MOF_ITEM.findall(raw):
            items.append(dict(_KR_MOF_TAG.findall(blk)))
        tc = re.search(r"<totalCount>\s*(\d+)\s*</totalCount>", raw)
        total = int(tc.group(1)) if tc else 0
    if not items or (total and len(items) < total):
        return []
    tot: dict[date, float] = {}
    for r in items:
        ym = str(r.get("useYm") or "")
        e, t = _num(str(r.get("eContnTeuTotal") or "")), _num(str(r.get("tContnTeuTotal") or ""))
        if len(ym) != 6 or not ym.isdigit() or e is None or t is None:
            continue
        m = int(ym[4:])
        if 1 <= m <= 12:
            d = _month_end(int(ym[:4]), m)
            tot[d] = tot.get(d, 0.0) + e + t
    return [Obs("container_teu", d, v) for d, v in sorted(tot.items())]


# ======================================================================= KR / HK official planes
# THE KOREA AND HONG KONG OFFICIAL PLANES (asia directive PARTS X and XI, audit rows 31-33,
# 2026-10-06).
# Two documented, keyed-or-keyless official APIs, parsed into PIT series that ride this organ's
# clock, doors and three uses unchanged. KRX and HKEX are NOT here: their published terms refuse
# commercial use / systematic retrieval, so the fail-closed terms gate below never builds them a
# fetcher (the refusals and their verbatim quotes are in `KR_HK_TERMS_EVIDENCE` and are carried by
# `countries/kr|hk/official_plane.py` into the departments' reports).

def _ecos_period(t: str) -> date | None:
    """ECOS TIME: YYYYMMDD (daily), YYYYMM (monthly -> month end), YYYYQn (quarter end)."""
    t = str(t or "").strip()
    with contextlib.suppress(ValueError):
        if len(t) == 8 and t.isdigit():
            return date(int(t[:4]), int(t[4:6]), int(t[6:]))
        if len(t) == 6 and t.isdigit():
            return _month_end(int(t[:4]), int(t[4:]))
        if len(t) == 6 and t[4] == "Q" and t[:4].isdigit() and t[5] in "1234":
            return _month_end(int(t[:4]), 3 * int(t[5]))
    return None


def make_ecos_parser(series: str) -> Callable[[bytes, Ctx], list[Obs]]:
    """A StatisticSearch parser for ONE ECOS item, named `series`. The URL filters to the item, so
    every row is that item; an ECOS error document (`RESULT.CODE`, e.g. INFO-200 no data or
    INFO-100 bad key) parses to nothing and the pass names it, never a zero."""

    def parse(body: bytes, ctx: Ctx) -> list[Obs]:
        try:
            doc = json.loads(body.decode("utf-8", errors="replace"))
        except ValueError:
            return []
        rows = ((doc or {}).get("StatisticSearch") or {}).get("row") \
            if isinstance(doc, dict) else None
        out: list[Obs] = []
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            period, v = _ecos_period(str(r.get("TIME") or "")), _num(str(r.get("DATA_VALUE") or ""))
            if period is not None and v is not None:
                out.append(Obs(series, period, v))
        return out

    parse.__name__ = f"parse_ecos_{series}"
    return parse


def _hkma_records(body: bytes) -> list[dict[str, Any]]:
    """HKMA Open API envelope: {"header": {"success": true, ...}, "result": {"datasize": n,
    "records": [...]}}. A `success: false` header (bad segment, bad page) is no records."""
    try:
        doc = json.loads(body.decode("utf-8-sig", errors="replace"))
    except ValueError:
        return []
    if not isinstance(doc, dict) or not (doc.get("header") or {}).get("success", False):
        return []
    recs = (doc.get("result") or {}).get("records")
    return [r for r in recs if isinstance(r, dict)] if isinstance(recs, list) else []


def _hkma_obs(body: bytes, ctx: Ctx, date_key: str, fields: dict[str, str],
              spreads: tuple[tuple[str, str, str], ...] = ()) -> list[Obs]:
    out: list[Obs] = []
    today = ctx.fetched_at.date()
    for r in _hkma_records(body):
        try:
            d = date.fromisoformat(str(r.get(date_key) or "")[:10])
        except ValueError:
            continue
        if d >= today:                 # a figure still being filled for today is never frozen
            continue
        vals: dict[str, float] = {}
        for field_name, series in fields.items():
            v = _num(str(r.get(field_name))) if r.get(field_name) not in (None, "") else None
            if v is not None:
                vals[series] = v
                out.append(Obs(series, d, v))
        for name, hi, lo in spreads:
            if hi in vals and lo in vals:
                out.append(Obs(name, d, round(vals[hi] - vals[lo], 6)))
    return out


#: Daily Figures of Interbank Liquidity (apidocs.hkma.gov.hk, read 2026-10-06), HK$ million and
#: % p.a. `forex_trans_t1` is the FX transaction booked for T+1 -- the Convertibility Undertaking
#: leg: positive when the HKMA sold HKD at the strong side (inflow), negative when it bought HKD
#: at the weak side (outflow defence, which drains the aggregate balance).
HKMA_LIQUIDITY_FIELDS: dict[str, str] = {
    "closing_balance": "aggregate_balance_hkd_mn", "hibor_overnight": "hibor_overnight",
    "hibor_fixing_1m": "hibor_1m", "twi": "hkd_twi", "disc_win_base_rate": "base_rate",
    "forex_trans_t1": "cu_forex_trans_t1_hkd_mn",
    "forecast_aggregate_bal_t1": "aggregate_balance_forecast_t1_hkd_mn"}
#: Hong Kong Interbank Interest Rates, segment hibor.fixing (HKAB fixing, 11:15 HKT), % p.a.
HKMA_HIBOR_FIELDS: dict[str, str] = {
    "ir_overnight": "hibor_on", "ir_1w": "hibor_1w", "ir_1m": "hibor_1m", "ir_3m": "hibor_3m",
    "ir_6m": "hibor_6m", "ir_12m": "hibor_12m"}
#: Daily Figures of Monetary Base, HK$ million. EF bills and notes enter as their OUTSTANDING
#: amount here; the per-issue EFBN yields endpoint serves the latest day only and is a Refinitiv
#: feed, so it is not read.
HKMA_MB_FIELDS: dict[str, str] = {
    "aggr_balance_af_disc_win": "aggregate_balance_hkd_mn",
    "outstanding_efbn": "efbn_outstanding_hkd_mn",
    "cert_of_indebt": "certificates_of_indebtedness_hkd_mn",
    "mb_bf_disc_win_total": "monetary_base_hkd_mn"}


def parse_hkma_liquidity(body: bytes, ctx: Ctx) -> list[Obs]:
    """HKMA daily interbank liquidity: aggregate balance, CU FX leg, HIBOR, TWI."""
    return _hkma_obs(body, ctx, "end_of_date", HKMA_LIQUIDITY_FIELDS,
                     (("aggregate_balance_forecast_gap_hkd_mn",
                       "aggregate_balance_forecast_t1_hkd_mn", "aggregate_balance_hkd_mn"),))


def parse_hkma_hibor(body: bytes, ctx: Ctx) -> list[Obs]:
    """HKMA HIBOR fixings by tenor plus the term spread (3M over overnight), % p.a."""
    return _hkma_obs(body, ctx, "end_of_day", HKMA_HIBOR_FIELDS,
                     (("hibor_3m_on_spread", "hibor_3m", "hibor_on"),
                      ("hibor_12m_1m_spread", "hibor_12m", "hibor_1m")))


def parse_hkma_monetary_base(body: bytes, ctx: Ctx) -> list[Obs]:
    """HKMA daily monetary base: aggregate balance, outstanding EF bills/notes, CIs, total."""
    return _hkma_obs(body, ctx, "end_of_date", HKMA_MB_FIELDS)


#: The date field each HKMA endpoint sorts on, for the paged request.
HKMA_DATE_KEY: dict[str, str] = {"hk_hkma_interbank_liquidity": "end_of_date",
                                 "hk_hkma_hibor_fixing": "end_of_day",
                                 "hk_hkma_monetary_base": "end_of_date"}
HKMA_PAGE = 1000
#: Pages read on the first pass (about sixteen years of business days); one page afterwards.
HKMA_BACKFILL_PAGES = 4


def _hkma_requests(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    pages = 1 if state.get("full_done") else HKMA_BACKFILL_PAGES
    state["full_done_next"] = True
    sep = "&" if "?" in src.url else "?"
    sort = HKMA_DATE_KEY.get(src.id, "end_of_date")
    return [Request(f"{src.url}{sep}pagesize={HKMA_PAGE}&offset={k * HKMA_PAGE}"
                    f"&sortby={sort}&sortorder=desc", Ctx(part=f"page{k}", fetched_at=now))
            for k in range(pages)]


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
    #: A local read in place of a fetch (a series another organ already fetches).
    reader: Callable[[Paths], list[Obs]] | None = None
    #: The paid panel this free source stands in for (roster `substitutes_for`).
    substitutes_for: str = ""
    #: The publisher stopped updating: history only. Such a source is DEAD, never live.
    archive_until: str | None = None
    #: confirmed | to_confirm | refused. FAIL CLOSED: only `confirmed` is ever fetched. Set per
    #: source in TERMS below, never by this default.
    terms: str = "to_confirm"
    #: Env vars that must hold REAL codes before a request may be built (no placeholder default).
    config_env: tuple[str, ...] = ()

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
        crowding_prior="low", note="no fetch: fetch_sge_premium already records it",
        reader=read_sge_premium),
)

# ---------------------------------------------------------------------------- paid substitutes
def _gdelt_series_map() -> dict[str, dict[str, int]]:
    """Per-country instrument legs. Tone up = risk-on for that country's assets; the conflict
    share takes the opposite leg. The prior is only a starting sign: a PASSING gain test's
    measured IC sign replaces it everywhere it is used."""
    legs: dict[str, dict[str, int]] = {
        "CN": {"AUDUSD": 1, "CHINAH": 1, "HK50": 1, "XCUUSD": 1, "USDCNH": -1},
        "HK": {"HK50": 1, "CHINAH": 1}, "JP": {"JPN225": 1, "USDJPY": 1},
        "KR": {"USDKRW": -1}, "TW": {"TSMC": 1}, "US": {"US500": 1, "NAS100": 1},
        "IN": {"USDINR": -1}, "BR": {"USDBRL": -1}, "RU": {"USDRUB": -1, "EURRUB": -1},
        "ZA": {"USDZAR": -1, "ZARJPY": 1}, "MX": {"USDMXN": -1, "MXNJPY": 1},
        "TR": {"USDTRY": -1, "EURTRY": -1}, "AU": {"AUDUSD": 1, "AUS200": 1}}
    out: dict[str, dict[str, int]] = {}
    for iso, m in legs.items():
        out[f"{iso}_conflict_share"] = {k: -v for k, v in m.items()}
        out[f"{iso}_"] = m
    return out


_NEWS = "RavenPack-style news analytics (event counts, tone, themes per entity)"
_CARD = "card-spend panels (Second Measure, Earnest, Bank of America card data)"
_FOOT = "foot-traffic / location panels (SafeGraph, Placer.ai)"
_SAT = "satellite / AIS activity panels (Orbital Insight, SpaceKnow)"
_TRAVEL = "travel-arrival panels (JNTO estimates, ForwardKeys / OAG arrivals)"
_GOLD = "physical gold-demand panels (SGE premium feeds, Metals Focus / GFMS flows)"

SUBSTITUTE_SOURCES: tuple[Source, ...] = (
    Source(
        id="gdelt_events_country", name="GDELT 2.0 Events: country x day x theme tone panel",
        url=GDELT_URL, region="GLOBAL", language="multi", cadence="daily",
        parse=parse_gdelt_events, rule=_lag_rule(1, 1), transform="level_dev",
        instruments={"US500": 1}, series_instruments=_gdelt_series_map(),
        signal_series=tuple(f"{iso}_{s}" for iso in sorted(set(GDELT_COUNTRIES.values()))
                            for s in ("tone", "conflict_share")),
        mechanism=("machine-coded events from the world's broadcast, print and web news in 100+ "
                   "languages, every 15 minutes: the article-weighted tone and conflict share of "
                   "what is happening IN a country is the news-flow state a RavenPack sentiment "
                   "feed sells, computed from the same kind of text"),
        payer=("holders of EM and Asian FX/index risk who reprice on the headline they read, "
               "not on the day's aggregate flow of local-language coverage"),
        constraint=("a desk reads a handful of English wires; GDELT's translated local press is "
                    "too large to read, so its aggregate state is not in the price by hand"),
        licence="GDELT Project open data (unrestricted use with citation); no key",
        source_culture="GLOBAL/multi",
        participant_structure=("institutional", "retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails when a single mega-story (a war, an election) dominates "
                                 "every country's coverage, and when GDELT's source list or "
                                 "translation pipeline changes, which moves tone for no reason "
                                 "in the markets"),
        crowding_prior="medium", substitutes_for=_NEWS,
        note=("15-minute export files are read forward and back from resumable cursors, summed "
              "per slot and published only for days whose 96 slots were all read (<= 8 gaps). "
              "GKG themes are not read (files are 10x larger); CAMEO roots stand in for themes")),
    Source(
        id="wiki_asia_attention", name="Asian-language Wikipedia attention (ja/zh/ko pageviews)",
        url=WIKI_URL, region="ASIA",
        language="ja/zh/ko", cadence="daily", parse=parse_wikimedia,
        rule=_lag_rule(1, 12), transform="anomaly_daily",
        instruments={"USDJPY": -1},
        series_instruments={"ja_boj": {"USDJPY": -1, "EURJPY": -1},
                            "ja_nikkei": {"JPN225": -1},
                            "zh_": {"USDCNH": 1, "HK50": -1, "CHINAH": -1},
                            "ko_": {"USDKRW": 1}},
        signal_series=("ja_boj_views", "ja_nikkei_views", "zh_pboc_views", "zh_rmb_views",
                       "zh_hsi_views", "ko_bok_views", "ko_kospi_views"),
        mechanism=("a Japanese, Chinese or Korean reader looks up the central bank, the currency "
                   "or the index in their own language before acting; an attention spike in the "
                   "local language is local retail attention the English Wikipedia list misses"),
        payer="local retail positioning that chases the move after the attention spike",
        constraint="retail acts on attention with a lag; institutions ignore pageviews",
        licence="Wikimedia pageviews API (CC0 data); no key",
        source_culture="JP/ja,CN/zh,KR/ko", participant_structure=("retail_heavy",),
        failure_mode_hypothesis=("fails when bots or a main-page feature inflate views, and "
                                 "zh.wikipedia is blocked in mainland China so its readers are "
                                 "TW/HK/diaspora, not the onshore retail base"),
        crowding_prior="low", substitutes_for=_NEWS,
        note=("full history once, then the last 45 days each pass; the English macro list "
              "stays in scripts/ingest_axes.py")),
    Source(
        id="us_oi_card_spend", name="Opportunity Insights / Affinity card spend (US, by sector)",
        url=("https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/"
             "Affinity%20-%20National%20-%20Daily.csv"),
        region="US", language="en", cadence="weekly", parse=parse_oi_spend,
        rule=_lag_rule(10, 0, weekday=True), transform="level_dev",
        instruments={"US500": 1, "Visa": 1, "Mastercard": 1, "AmericanExpress": 1,
                     "Walmart": 1, "Target": 1},
        series_instruments={"spend_food": {"McDonalds": 1, "Starbucks": 1},
                            "spend_arts": {"Netflix": 1, "Booking": 1}},
        signal_series=("spend_all", "spend_retail_no_grocery", "spend_food_accommodation"),
        mechanism=("de-identified credit and debit card spend from Affinity Solutions by sector "
                   "and income quartile, seasonally adjusted against 2019 -- the same kind of "
                   "panel Second Measure and Earnest sell, published free by Opportunity Insights"),
        payer="consumer-equity and index holders who wait for Census retail sales",
        constraint="the official receipts survey is monthly and two weeks late",
        licence=("Opportunity Insights Economic Tracker README: 'Anyone is welcome to use this "
                 "data' with the provider (Affinity Solutions) named and Chetty et al. cited; "
                 "no formal licence file"),
        source_culture="US/en", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails because the feed ENDED (last rows 2024-06): it is a "
                                 "2020-2024 backfill for history-only tests, and it over-weights "
                                 "the pandemic regime in any fit"),
        crowding_prior="high", substitutes_for=_CARD, archive_until="2024-06",
        note=("DEAD: the feed ended 2024-06-16 (re-read from GitHub raw 2026-09-30). History for "
              "the agreement check only; never a live source, never a direct cell. No free "
              "successor was wired: none was reachable to verify from the authoring box")),
    Source(
        id="kr_bok_card_spend", name="BOK ECOS card spending (Korea, one configured item)",
        url=("https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/1000/"
             "{ALT_ECOS_CARD_STAT}/M/201801/{yyyymm}/{ALT_ECOS_CARD_ITEM}"),
        region="KR", language="ko", cadence="monthly", parse=parse_ecos,
        rule=_lag_rule(25, 0, weekday=True), transform="yoy_monthly", key_env="ECOS_API_KEY",
        config_env=("ALT_ECOS_CARD_STAT", "ALT_ECOS_CARD_ITEM"),
        instruments={"USDKRW": -1},
        signal_series=("card_spend",),
        mechanism=("Korean card use is near-universal, so the BOK's card-spending series is "
                   "household consumption itself, printed a month before the national accounts"),
        payer="won holders and Korea-exposed books waiting for GDP and retail surveys",
        constraint="BOK policy and won positioning reprice at the monthly data calendar",
        licence="BOK ECOS Open API (free key; attribution to the Bank of Korea)",
        source_culture="KR/ko", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails around Chuseok/Lunar New Year month shifts and "
                                 "government consumption-voucher programmes"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("minimal ECOS reader (no ECOS reader exists in the repo). NO DEFAULT CODES: the "
              "stat and item codes come only from ALT_ECOS_CARD_STAT / ALT_ECOS_CARD_ITEM, read "
              "off ECOS StatisticItemList on the box; until both and the key are set the row is "
              "BLOCKED_ON_KEY / UNCONFIGURED and nothing is requested")),
    Source(
        id="jp_meti_retail", name="METI commercial dynamics flash: retail sales YoY (Japan)",
        url=os.environ.get("ALT_METI_RETAIL_URL",
                           "https://www.meti.go.jp/statistics/tyo/syoudou/result/sokuho_2.html"),
        region="JP", language="ja", cadence="monthly", parse=parse_meti_retail,
        rule=_lag_rule(33, 0, weekday=True), transform="given",
        instruments={"JPN225": 1, "USDJPY": -1, "EURJPY": -1},
        signal_series=("retail_yoy",),
        mechanism=("METI's survey of retailers' sales is Japan's monthly consumption print; a "
                   "firm print feeds BoJ normalisation pricing and domestic-demand equities"),
        payer="yen-funded carry and JPN225 holders leaning on weak Japanese demand",
        constraint="BoJ-path positioning reprices at data and meeting dates only",
        licence="METI statistics (Government of Japan standard terms, attribution)",
        source_culture="JP/ja", participant_structure=("policy_driven", "retail_heavy"),
        failure_mode_hypothesis=("fails when fuel subsidies or a consumption-tax change move "
                                 "nominal sales mechanically"),
        crowding_prior="medium", substitutes_for=_CARD,
        note="page URL overridable (ALT_METI_RETAIL_URL); confirm route on the box"),
    Source(
        id="cn_nbs_retail", name="NBS retail sales of consumer goods (China)",
        url=os.environ.get("ALT_NBS_RETAIL_URL", "https://www.stats.gov.cn/sj/zxfb/"),
        region="CN", language="zh", cadence="monthly", parse=parse_nbs_retail,
        rule=_lag_rule(17, 2, weekday=True), transform="given",
        instruments={"AUDUSD": 1, "CHINAH": 1, "HK50": 1, "XCUUSD": 1, "USDCNH": -1},
        signal_series=("retail_yoy",),
        mechanism=("China's official consumption print against its own run-rate: a miss is "
                   "stimulus odds up and a China-demand repricing in AUD, copper and HK equity"),
        payer="China-proxy holders (AUD, copper, HK50) pricing on PMI headlines alone",
        constraint="stimulus expectations move only at State Council and data dates",
        licence="National Bureau of Statistics of China releases (public)",
        source_culture="CN/zh", participant_structure=("policy_driven", "institutional"),
        failure_mode_hypothesis=("fails when the January-February combined print and base "
                                 "effects dominate, and when stimulus is already announced"),
        crowding_prior="high", substitutes_for=_CARD),
    Source(
        id="cn_holiday_spend", name="MCT holiday tourism spend and UnionPay holiday payments",
        url=os.environ.get("ALT_CN_HOLIDAY_URL", "https://www.mct.gov.cn/whzx/whyw/"),
        region="CN", language="zh", cadence="event", parse=parse_cn_holiday,
        rule=_lag_rule(2, 0, weekday=True), transform="given",
        instruments={"CHINAH": 1, "HK50": 1, "AUDUSD": 1, "Baidu": 1},
        signal_series=("spend_per_trip_yoy", "spend_yoy"),
        mechanism=("the Golden Week and Spring Festival tallies (trips and spend, YoY) are the "
                   "only same-week read of Chinese discretionary spending; spend PER TRIP is "
                   "consumer confidence net of the travel-count headline"),
        payer="HK and China-consumer holders reading the trip-count headline only",
        constraint="onshore data is monthly; the holiday tally lands the evening it ends",
        licence="Ministry of Culture and Tourism / UnionPay public releases",
        source_culture="CN/zh", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails when holiday length changes (the calendar is set by the "
                                 "State Council each year) and when official tallies are "
                                 "managed upward"),
        crowding_prior="medium", substitutes_for=_CARD),
    Source(
        id="in_npci_upi", name="NPCI UPI monthly volumes and value (India)",
        url="https://www.npci.org.in/what-we-do/upi/product-statistics",
        region="IN", language="en", cadence="monthly", parse=parse_npci_upi,
        rule=_lag_rule(2, 0, weekday=True), transform="yoy_monthly",
        instruments={"USDINR": -1},
        signal_series=("upi_value_cr",),
        mechanism=("UPI carries most Indian retail payments; its monthly value is a card-panel "
                   "substitute for the whole economy, out on day one of the next month"),
        payer="INR and India-exposed holders waiting for MOSPI and RBI data",
        constraint="RBI manages INR volatility, so flow information reprices slowly",
        licence="NPCI public product statistics",
        source_culture="IN/en", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails because structural adoption growth dominates YoY; "
                                 "a surprise is small against the trend and festivals shift it"),
        crowding_prior="low", substitutes_for=_CARD),
    Source(
        id="tr_bkm_card", name="BKM card payments (Turkey), nominal YoY",
        url=os.environ.get("ALT_BKM_URL", "https://bkm.com.tr/en/press-releases/"),
        region="TR", language="tr", cadence="monthly", parse=parse_bkm,
        rule=_lag_rule(20, 0, weekday=True), transform="given",
        instruments={"USDTRY": 1, "EURTRY": 1},
        signal_series=("card_payments_nominal_yoy",),
        mechanism=("Turkish card spend in nominal lira is inflation plus demand; a hot print is "
                   "pressure on the CBRT and the lira before CPI prints"),
        payer="lira carry holders who price on the policy rate alone",
        constraint="CBRT-managed lira and capital-flow rules slow the repricing",
        licence="BKM public press releases",
        source_culture="TR/tr", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails because nominal growth is mostly inflation: the "
                                 "surprise is dominated by CPI, not demand"),
        crowding_prior="low", substitutes_for=_CARD),
    Source(
        id="br_cielo_icva", name="Cielo ICVA retail card sales (Brazil)",
        url=os.environ.get("ALT_ICVA_URL", "https://www.cielo.com.br/icva/"),
        region="BR", language="pt", cadence="monthly", parse=parse_icva,
        rule=_lag_rule(15, 0, weekday=True), transform="given",
        instruments={"USDBRL": -1},
        signal_series=("icva_deflated_yoy",),
        mechanism=("Cielo's acquirer data is Brazil's card panel: deflated retail card sales "
                   "YoY, out weeks before IBGE's PMC retail survey"),
        payer="BRL carry holders waiting for IBGE retail and Copom",
        constraint="Copom and BRL positioning reprice on official data dates",
        licence="Cielo public ICVA releases",
        source_culture="BR/pt", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails when calendar (working-day) effects and Black Friday "
                                 "timing dominate the month"),
        crowding_prior="low", substitutes_for=_CARD),
    Source(
        id="mx_antad_sss", name="ANTAD same-store sales (Mexico)",
        url=os.environ.get("ALT_ANTAD_URL", "https://antad.net/indicadores/"),
        region="MX", language="es", cadence="monthly", parse=parse_antad,
        rule=_lag_rule(12, 0, weekday=True), transform="given",
        instruments={"USDMXN": -1, "MXNJPY": 1, "Walmart": 1},
        signal_series=("same_store_sales_yoy",),
        mechanism=("the retailers' association prints same-store sales two weeks after month "
                   "end, a month before INEGI retail; Walmex dominates the panel"),
        payer="MXN carry holders waiting for INEGI and Banxico",
        constraint="Banxico-path positioning reprices at data dates",
        licence="ANTAD public monthly indicator",
        source_culture="MX/es", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails around Easter and El Buen Fin timing shifts"),
        crowding_prior="low", substitutes_for=_CARD),
    Source(
        id="za_beti", name="BankservAfrica/PayInc economic transactions index (South Africa)",
        url=os.environ.get("ALT_BETI_URL", "https://www.payinc.co.za/beti/"),
        region="ZA", language="en", cadence="monthly", parse=parse_beti,
        rule=_lag_rule(12, 0, weekday=True), transform="given",
        instruments={"USDZAR": -1, "ZARJPY": 1},
        signal_series=("beti_mom",),
        mechanism=("the interbank clearing house's count and value of electronic transactions "
                   "is South African activity read from the payments rail, weeks before Stats SA"),
        payer="ZAR carry holders pricing on commodity terms of trade alone",
        constraint="Stats SA GDP and retail are quarterly/monthly and late",
        licence="BankservAfrica / PayInc public releases",
        source_culture="ZA/en", participant_structure=("institutional", "physical_flow"),
        failure_mode_hypothesis="fails under load-shedding months and payday-calendar shifts",
        crowding_prior="low", substitutes_for=_CARD),
    Source(
        id="us_oi_google_mobility", name="Google mobility via Opportunity Insights (US)",
        url=("https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/"
             "Google%20Mobility%20-%20National%20-%20Daily.csv"),
        region="US", language="en", cadence="daily", parse=parse_oi_mobility,
        rule=_lag_rule(5, 0), transform="level_dev",
        instruments={"US500": 1, "Uber": 1, "Lyft": 1, "Booking": 1},
        series_instruments={"retail": {"US500": 1, "Target": 1, "Walmart": 1}},
        signal_series=("retail_and_recreation", "transit_stations"),
        mechanism=("phone-location visits to retail and transit places against a pre-2020 base "
                   "-- the product SafeGraph and Placer.ai sell, published free by Google"),
        payer="consumer and travel holders waiting for earnings and monthly surveys",
        constraint="visit counts were never part of any official calendar",
        licence=("Google COVID-19 Community Mobility Reports as redistributed by Opportunity "
                 "Insights ('Anyone is welcome to use this data', provider named, OI cited)"),
        source_culture="US/en", participant_structure=("retail_heavy", "physical_flow"),
        failure_mode_hypothesis=("fails because the feed ENDED (2022-10): a pandemic-era "
                                 "history for history-only tests"),
        crowding_prior="high", substitutes_for=_FOOT, archive_until="2022-10",
        note=("DEAD: Google stopped the reports; last row 2022-10-15 (re-read from GitHub raw "
              "2026-09-30). History for the agreement check only; never live, never a cell")),
    Source(
        id="kr_kobis_box_office", name="KOBIS daily box office (Korea, top 10)",
        url=("https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
             "searchDailyBoxOfficeList.json?key={key}&targetDt={date}"),
        region="KR", language="ko", cadence="daily", parse=parse_kobis, rule=_lag_rule(1, 0),
        transform="yoy_daily", key_env="KOBIS_API_KEY",
        instruments={"USDKRW": -1},
        signal_series=("audience_top10",),
        mechanism=("cinema admissions are a daily count of discretionary outings, the "
                   "foot-traffic panel for Korean leisure spend"),
        payer="won and Korea-consumer holders waiting for monthly retail data",
        constraint="nothing official prints Korean leisure spend daily",
        licence="KOBIS Open API (free key; Korean Film Council)",
        source_culture="KR/ko", participant_structure=("retail_heavy",),
        failure_mode_hypothesis=("fails when one blockbuster release dominates a week and "
                                 "holiday dates shift against the 364-day comparison"),
        crowding_prior="low", substitutes_for=_FOOT),
    Source(
        id="kr_seoul_subway", name="Seoul subway boardings by day (card taps, all stations)",
        url="http://openapi.seoul.go.kr:8088/{key}/json/CardSubwayStatsNew/1/1000/{date}",
        region="KR", language="ko", cadence="daily", parse=parse_seoul_subway,
        rule=_lag_rule(4, 0), transform="yoy_daily", key_env="SEOUL_API_KEY",
        instruments={"USDKRW": -1},
        signal_series=("boardings",),
        mechanism=("every Seoul subway card tap, summed per day: commuting and outing volume in "
                   "the capital, the location panel for Korean activity"),
        payer="Korea-exposed holders waiting for monthly activity data",
        constraint="no official daily activity measure exists",
        licence="Seoul Open Data Plaza (free key; KOGL type 1)",
        source_culture="KR/ko", participant_structure=("retail_heavy", "physical_flow"),
        failure_mode_hypothesis=("fails on public-holiday misalignment and fare changes that "
                                 "move ridership mechanically"),
        crowding_prior="low", substitutes_for=_FOOT),
    Source(
        id="cn_maoyan_box_office", name="Maoyan Pro national box office (China, daily)",
        url="https://piaofang.maoyan.com/dashboard-ajax?showDate={date}",
        region="CN", language="zh", cadence="daily", parse=parse_maoyan, rule=_lag_rule(1, 0),
        transform="yoy_daily",
        instruments={"CHINAH": 1, "HK50": 1},
        signal_series=("box_office_cny_10k",),
        mechanism=("China's national box office by day is discretionary spending read from the "
                   "ticketing platform, weeks before NBS retail"),
        payer="China-consumer and HK equity holders waiting for NBS",
        constraint="onshore consumption data is monthly",
        licence="Maoyan Pro public dashboard (terms to confirm; read-only daily total)",
        source_culture="CN/zh", participant_structure=("retail_heavy",),
        failure_mode_hypothesis=("fails when release-slate timing (Spring Festival films) "
                                 "dominates, and when the dashboard's anti-scraping changes "
                                 "the response"),
        crowding_prior="low", substitutes_for=_FOOT,
        note="response shape UNCONFIRMED against a live reply; the parser emits nothing on a miss"),
    Source(
        id="cn_baidu_migration", name="Baidu migration index: move-in by city (China)",
        url="https://huiyan.baidu.com/migration/historycurve.jsonp?dt=city&id={city}&type=move_in",
        region="CN", language="zh", cadence="daily", parse=parse_baidu_migration,
        rule=_lag_rule(1, 12), transform="anomaly_daily",
        instruments={"CHINAH": 1, "HK50": 1, "AUDUSD": 1, "XCUUSD": 1},
        signal_series=tuple(f"{c}_move_in" for c in BAIDU_CITIES),
        mechanism=("phone-location migration into China's tier-1 cities is the return-to-work "
                   "and travel pulse after holidays, the location panel no Western vendor sells"),
        payer="China-demand holders (AUD, copper, HK) waiting for PMI and NBS activity",
        constraint="onshore activity data is monthly and three weeks late",
        licence="Baidu Huiyan public migration map (terms to confirm)",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis=("fails around the lunar calendar (Spring Festival moves each "
                                 "year) and when Baidu suspends the map, as it has before"),
        crowding_prior="low", substitutes_for=_FOOT),
    Source(
        id="kr_busan_port", name="Busan Port Authority monthly container throughput",
        url=os.environ.get("ALT_BUSAN_PORT_URL",
                           "https://www.busanpa.com/index.bpa?menuCd=DOM_000000105005001003"),
        region="KR", language="ko", cadence="monthly", parse=parse_busan_port,
        rule=_lag_rule(20, 0, weekday=True), transform="given",
        instruments={"USDKRW": -1, "XCUUSD": 1, "CHINAH": 1},
        signal_series=("container_yoy",),
        mechanism=("Busan is the world's second transhipment hub: its monthly boxes are North "
                   "Asian trade volume counted at the quay, the AIS/satellite port panel's "
                   "output as an official number"),
        payer="trade-cycle holders waiting for customs totals",
        constraint="official trade data is value-based and late",
        licence="Busan Port Authority public releases",
        source_culture="KR/ko", participant_structure=("physical_flow",),
        failure_mode_hypothesis=("fails when transhipment re-routing (Red Sea, US tariffs) moves "
                                 "Busan's share rather than total trade"),
        crowding_prior="low", substitutes_for=_SAT,
        note=("URL moved 2026-09-30: the old Board.do?mCode=MN1003 is 404; the current page is "
              "부산항 통계 > 항만운영 통계 > 부두별 컨테이너 처리실적 "
              "(index.bpa, table loaded by JS, so the parser may read nothing from the "
              "served HTML). Overridable "
              "(ALT_BUSAN_PORT_URL); confirm the route on the box")),
    Source(
        id="sg_port_throughput", name="SingStat sea cargo: Singapore container throughput",
        url=("https://tablebuilder.singstat.gov.sg/api/table/tabledata/"
             + os.environ.get("ALT_SINGSTAT_PORT_TABLE", "M650631")),
        region="SG", language="en", cadence="monthly", parse=parse_singstat_port,
        rule=_lag_rule(20, 0, weekday=True), transform="yoy_monthly",
        instruments={"USDSGD": -1, "SGDJPY": 1, "CHINAH": 1},
        signal_series=("container_throughput_k_teu",),
        mechanism=("Singapore's container throughput is Asia-Europe and intra-Asia trade at the "
                   "Malacca chokepoint, monthly and official"),
        payer="SGD and Asian trade-cycle holders waiting for NODX and customs",
        constraint="MAS manages SGD on a policy band; trade data reprices it slowly",
        licence="SingStat Table Builder API (Singapore Open Data Licence)",
        source_culture="SG/en", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis=("fails under route shifts (Red Sea diversions) that add "
                                 "transhipment"),
        crowding_prior="low", substitutes_for=_SAT,
        note="table id overridable (ALT_SINGSTAT_PORT_TABLE); confirm the id on the box"),
    Source(
        id="cn_mot_port_weekly", name="China MOT weekly port cargo and container throughput",
        url=os.environ.get("ALT_CN_MOT_PORT_URL",
                           "https://xxgk.mot.gov.cn/zhengceapp/863/868/list_7234.html"),
        region="CN", language="zh", cadence="weekly", parse=parse_mot_port,
        rule=_lag_rule(3, 0, weekday=True), transform="anomaly_monthly",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1, "USDCNH": -1},
        signal_series=("container_10k_teu", "port_cargo_100m_t"),
        mechanism=("the transport ministry's weekly national port tally is China's trade volume "
                   "a month before customs: the port-activity reading a satellite panel sells"),
        payer="China-trade proxies (AUD, copper, HK) waiting for monthly customs",
        constraint="customs data is monthly and value-based",
        licence="Ministry of Transport of the PRC public bulletins",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis="fails around Spring Festival and typhoon port closures",
        crowding_prior="low", substitutes_for=_SAT,
        note=("URL moved 2026-09-30: www.mot.gov.cn/tongjishuju/ is 404; MOT statistics now "
              "sit on the government-information list xxgk.mot.gov.cn/zhengceapp/863/868/"
              "list_7234.html, which carries the MONTHLY 港口货物、集装箱吞吐量 "
              "release (an .xlsx); "
              "no weekly bulletin was found there. Overridable (ALT_CN_MOT_PORT_URL)")),
    # ---- lawful substitutes for the BLOCKED sources (SUBSTITUTED_BY below): government open
    # data or an explicit reuse licence, each verified on 2026-09-30 (TERMS_EVIDENCE).
    Source(
        id="jp_estat_immigration",
        name="Immigration Services Agency entries of foreign nationals (e-Stat, monthly)",
        url=("https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData?appId={key}"
             "&statsDataId={ALT_ESTAT_IMMIG_STATS_ID}&cdCat01={ALT_ESTAT_IMMIG_CAT01}"),
        region="JP", language="ja", cadence="monthly", parse=parse_estat_level,
        rule=_lag_rule(45, 0, weekday=True), transform="yoy_monthly", key_env="ESTAT_APP_ID",
        config_env=("ALT_ESTAT_IMMIG_STATS_ID", "ALT_ESTAT_IMMIG_CAT01"),
        instruments={"USDJPY": -1, "EURJPY": -1, "JPN225": 1},
        signal_series=("foreign_entries",),
        mechanism=("foreign nationals counted through Japanese immigration are the arrivals JNTO "
                   "estimates, from the border record itself: inbound visitors convert foreign "
                   "currency into yen at the till, a services-export flow the goods balance hides"),
        payer="yen shorts funding carry who ignore services-account flows",
        constraint="carry books are sized on rate differentials, not border counts",
        licence=("e-Stat (Government of Japan statistics): Government Standard Terms of Use, CC "
                 "BY 4.0 compatible; free application ID"),
        source_culture="JP/ja", participant_structure=("physical_flow", "retail_heavy"),
        failure_mode_hypothesis=("fails when visa policy or a China group-tour ban moves "
                                 "arrivals for reasons the yen already priced, and it prints "
                                 "later than JNTO's estimate"),
        crowding_prior="low", substitutes_for=_TRAVEL,
        note=("stands in for jp_jnto_arrivals (JNTO site policy refuses reuse). NO DEFAULT "
              "CODES: statsDataId and cdCat01 of the 出入国管理統計 foreign-entries "
              "table come only "
              "from ALT_ESTAT_IMMIG_STATS_ID / ALT_ESTAT_IMMIG_CAT01 (candidate table: statdisp "
              "0003287527, 港別 出入国者 月次); reuses jp_tokyo_cpi's e-Stat key")),
    Source(
        id="hk_immd_passenger",
        name="HK Immigration daily passenger traffic: mainland visitor arrivals (DATA.GOV.HK)",
        url=("https://www.immd.gov.hk/opendata/eng/transport/immigration_clearance/"
             "statistics_on_daily_passenger_traffic.csv"),
        region="HK", language="en", cadence="daily", parse=parse_hk_immd,
        rule=_lag_rule(2, 0), transform="yoy_daily",
        instruments={"HK50": 1, "CHINAH": 1},
        series_instruments={"hk_resident_departures": {"HK50": -1}},
        signal_series=("mainland_visitor_arrivals", "hk_resident_departures"),
        mechanism=("every crossing at every Hong Kong control point, by day: mainland visitor "
                   "arrivals are Chinese outbound discretionary travel and spend (Golden Week and "
                   "Spring Festival read the day after), the mobility pulse Baidu's migration map "
                   "and the holiday tallies sell; HK residents heading north is spend leaving HK"),
        payer="HK equity and China-consumer holders waiting for NBS retail and HK retail sales",
        constraint="onshore consumption and HK retail data are monthly and weeks late",
        licence=("DATA.GOV.HK Terms and Conditions: browse, download, distribute, reproduce for "
                 "commercial and non-commercial purposes free of charge, with attribution"),
        source_culture="HK/en", participant_structure=("retail_heavy", "physical_flow"),
        failure_mode_hypothesis=("fails when border policy (visa schemes, quarantine) or a new "
                                 "crossing moves the count mechanically, and on lunar-calendar "
                                 "holiday shifts against the 364-day comparison"),
        crowding_prior="low", substitutes_for=_FOOT,
        note=("stands in for cn_baidu_migration, cn_holiday_spend (with cn_nbs_retail) and, at "
              "class level only, cn_maoyan_box_office; one CSV, whole history, keyless")),
    Source(
        id="br_bcb_payments", name="BCB monthly retail payments (Pix, cards, boletos), Brazil",
        url=("https://olinda.bcb.gov.br/olinda/servico/MPV_DadosAbertos/versao/v1/odata/"
             "MeiosdePagamentosMensalDA?$format=json&$top=10000"),
        region="BR", language="pt", cadence="monthly", parse=parse_bcb_mpv,
        rule=_lag_rule(20, 0, weekday=True), transform="yoy_monthly",
        instruments={"USDBRL": -1},
        signal_series=("retail_payments_value_brl",),
        mechanism=("the central bank's own count of retail payment value (Pix, cards, boletos) "
                   "is Brazil's card panel from the payments rail, out on the 17th of the next "
                   "month, weeks before IBGE's PMC retail survey"),
        payer="BRL carry holders waiting for IBGE retail and Copom",
        constraint="Copom and BRL positioning reprice on official data dates",
        licence="BCB Open Data portal: Open Data Commons Open Database License (ODbL)",
        source_culture="BR/pt", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails because Pix adoption growth dominates the nominal "
                                 "value, and on working-day and Black Friday calendar shifts"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("stands in for br_cielo_icva (Cielo terms refuse reuse). Same host and no-key "
              "rule as the Brazil lane's bcb_olinda provider (research/countries/br/"
              "data_plane.py), which carries no payments series. Field names UNCONFIRMED "
              "against a live reply; the parser emits nothing on a miss")),
    Source(
        id="mx_inegi_emec", name="INEGI EMEC retail trade index (Mexico, one configured series)",
        url=("https://www.inegi.org.mx/app/api/indicadores/desarrolladores/jsonxml/INDICATOR/"
             "{ALT_INEGI_EMEC_ID}/es/0700/false/BIE/2.0/{key}?type=json"),
        region="MX", language="es", cadence="monthly", parse=parse_inegi_bie,
        rule=_lag_rule(55, 0, weekday=True), transform="yoy_monthly", key_env="INEGI_TOKEN",
        config_env=("ALT_INEGI_EMEC_ID",),
        instruments={"USDMXN": -1, "MXNJPY": 1},
        signal_series=("retail_index",),
        mechanism=("INEGI's monthly survey of retail businesses is the official read of Mexican "
                   "store sales that ANTAD's same-store print front-runs; against its own run-rate "
                   "it reprices the Banxico path"),
        payer="MXN carry holders waiting for Banxico",
        constraint="Banxico-path positioning reprices at data dates",
        licence=("INEGI Términos de Libre Uso: copy, distribute, adapt and exploit commercially "
                 "with credit to INEGI; free API token"),
        source_culture="MX/es", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails around Easter and El Buen Fin timing shifts, and it "
                                 "prints about seven weeks after the month"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("stands in for mx_antad_sss (ANTAD terms refuse reuse). NO DEFAULT CODE: the BIE "
              "indicator id comes only from ALT_INEGI_EMEC_ID. The desk's Banxico SIE rows "
              "(research/countries/br/data_plane.py) carry no retail series, so none is reused")),
    Source(
        id="tr_tuik_retail", name="TÜİK retail sales volume index, YoY (Turkey)",
        url=os.environ.get("ALT_TUIK_RETAIL_URL", "https://veriportali.tuik.gov.tr/"),
        region="TR", language="tr", cadence="monthly", parse=parse_tuik_retail,
        rule=_lag_rule(42, 0, weekday=True), transform="given",
        config_env=("ALT_TUIK_RETAIL_URL",),
        instruments={"USDTRY": 1, "EURTRY": 1},
        signal_series=("retail_volume_yoy",),
        mechanism=("the statistics office's constant-price retail volume is Turkish demand net "
                   "of inflation, the part of a card-spend print the CPI does not explain; a hot "
                   "print is pressure on the CBRT and the lira"),
        payer="lira carry holders who price on the policy rate alone",
        constraint="CBRT-managed lira and capital-flow rules slow the repricing",
        licence=("TÜİK legal notice: data may be reused without permission provided the source "
                 "is cited"),
        source_culture="TR/tr", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails when a minimum-wage step or a tax change moves volume "
                                 "mechanically, and it prints later than BKM"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("stands in for tr_bkm_card (BKM refuses reuse). CBRT EVDS card spending "
              "(TP.KKHARTUT) is NOT used: the CBRT terms put commercial use under written "
              "permission. The TÜİK data portal is a JS app, so the bulletin URL comes only from "
              "ALT_TUIK_RETAIL_URL; unset, the row is UNCONFIGURED and nothing is requested")),
    Source(
        id="kr_mof_container_teu",
        name="MOF import/export container TEU by month (Korea, data.go.kr)",
        url=os.environ.get("ALT_KR_MOF_CONTAINER_URL",
                           "https://apis.data.go.kr/1192000/SsopCargContnImxprt2?serviceKey={key}"
                           "&sym=201801&eym={yyyymm}&pageNo=1&numOfRows=5000&type=json"),
        region="KR", language="ko", cadence="monthly", parse=parse_kr_mof_container,
        rule=_lag_rule(30, 0, weekday=True), transform="yoy_monthly", key_env="DATA_GO_KR_KEY",
        instruments={"USDKRW": -1, "XCUUSD": 1, "CHINAH": 1},
        signal_series=("container_teu",),
        mechanism=("the ministry's monthly count of import and export boxes through Korean ports "
                   "(Busan carries three quarters of them) is North Asian trade volume at the "
                   "quay, the AIS/satellite port panel's output as an official number"),
        payer="trade-cycle holders waiting for customs totals",
        constraint="official trade data is value-based and late",
        licence=("data.go.kr (Ministry of Oceans and Fisheries): 이용허락범위 제한 없음 "
                 "(unrestricted use); free service key"),
        source_culture="KR/ko", participant_structure=("physical_flow",),
        failure_mode_hypothesis=("fails when transhipment re-routing (Red Sea, US tariffs) moves "
                                 "Korean ports' share rather than total trade"),
        crowding_prior="low", substitutes_for=_SAT,
        note=("stands in for kr_busan_port (BPA shows no KOGL mark). Endpoint as listed on "
              "data.go.kr/data/15059131; the operation path is overridable "
              "(ALT_KR_MOF_CONTAINER_URL); confirm the route on the box")),
)

#: THE TERMS GATE, FAIL CLOSED. `confirmed` only where the licence is plainly open: government
#: open data under a stated open licence, CC/CC0 data, public statistics behind a documented API,
#: or a publisher's written "anyone may use this". Everything else is `to_confirm` until a human
#: reads the terms, and a `to_confirm` or `refused` source is NEVER fetched (BLOCKED_ON_TERMS).
# ---------------------------------------------------------------------------- KR / HK planes
ECOS_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/10000/"
#: ECOS item paths (STAT/CYCLE/START/END/ITEM[/ITEM2]). Each is overridable on the box; a wrong code
#: returns an ECOS error document, which parses to nothing and is reported -- never a value.
ECOS_PATHS: dict[str, str] = {
    "kr_ecos_base_rate": os.environ.get("ALT_ECOS_BASE_RATE_PATH",
                                        "722Y001/D/20150101/{yyyymmdd}/0101000"),
    "kr_ecos_call_rate": os.environ.get("ALT_ECOS_CALL_RATE_PATH",
                                        "817Y002/D/20150101/{yyyymmdd}/010101000"),
    "kr_ecos_fx_reserves": os.environ.get("ALT_ECOS_FX_RESERVES_PATH",
                                          "732Y001/M/201001/{yyyymm}/99"),
    "kr_ecos_export_prices": os.environ.get("ALT_ECOS_EXPORT_PRICES_PATH",
                                            "402Y014/M/201001/{yyyymm}/*AA/W"),
}
HKMA_BASE = "https://api.hkma.gov.hk/public/market-data-and-statistics/"
_BOK = "Bank of Korea ECOS Open API (free key; attribution to the Bank of Korea)"
_HKMA = ("HKMA Open API, published on DATA.GOV.HK: free commercial and non-commercial reuse "
         "with attribution to the HKMA and DATA.GOV.HK; no key")
_ECOS_NOTE = ("parsed ECOS item; the code path is overridable (ALT_ECOS_*_PATH) and is verified "
              "on the box against StatisticItemList -- a wrong code parses to nothing, never a "
              "value. Key: ECOS_API_KEY (BOK_API_KEY is adopted as its alias)")

KR_HK_PLANE_SOURCES: tuple[Source, ...] = (
    Source(
        id="kr_ecos_base_rate", name="Bank of Korea base rate (ECOS 722Y001, daily)",
        url=ECOS_URL + ECOS_PATHS["kr_ecos_base_rate"], region="KR", language="ko",
        cadence="daily", parse=make_ecos_parser("base_rate"),
        rule=_lag_rule(0, 1, calendar="KR"),
        transform="given", key_env="ECOS_API_KEY", instruments={"USDKRW": -1},
        signal_series=("base_rate",),
        mechanism=("the BOK policy rate is the anchor of KRW carry; a move (or the end of a "
                   "cycle) reprices the won against the dollar before Korean flows adjust"),
        payer="won carry positions sized on the prior policy path",
        constraint="FX swap and NDF books reprice only at MPC dates",
        licence=_BOK, source_culture="KR/ko", participant_structure=("policy_driven",),
        failure_mode_hypothesis=("fails when the move was fully priced by the KTB curve and "
                                 "when Fed surprises dominate the same week"),
        crowding_prior="high", note=_ECOS_NOTE),
    Source(
        id="kr_ecos_call_rate", name="Korea interbank call rate, overnight (ECOS 817Y002)",
        url=ECOS_URL + ECOS_PATHS["kr_ecos_call_rate"], region="KR", language="ko",
        cadence="daily", parse=make_ecos_parser("call_rate_1d"),
        rule=_lag_rule(1, 9, calendar="KR"),
        transform="given", key_env="ECOS_API_KEY", instruments={"USDKRW": -1},
        signal_series=("call_rate_1d",),
        mechanism=("the KRW interbank call rate against the base rate is onshore won liquidity: "
                   "a call rate trading over the base rate is a funding squeeze that forces "
                   "dollar selling by onshore banks"),
        payer="offshore NDF holders who do not see onshore funding until it moves spot",
        constraint="onshore/offshore won markets are segmented by capital controls",
        licence=_BOK, source_culture="KR/ko",
        participant_structure=("institutional", "settlement_constrained"),
        failure_mode_hypothesis=("fails at quarter- and year-end balance-sheet dates, which "
                                 "move the call rate mechanically"),
        crowding_prior="low", note=_ECOS_NOTE),
    Source(
        id="kr_ecos_fx_reserves", name="Korea official FX reserves (ECOS 732Y001, monthly)",
        url=ECOS_URL + ECOS_PATHS["kr_ecos_fx_reserves"], region="KR", language="ko",
        cadence="monthly", parse=make_ecos_parser("fx_reserves_usd_k"),
        rule=_lag_rule(7, 0, weekday=True, calendar="KR"), transform="mom_monthly",
        key_env="ECOS_API_KEY",
        instruments={"USDKRW": -1}, signal_series=("fx_reserves_usd_k",),
        mechanism=("the monthly change in reserves net of valuation is the footprint of BOK "
                   "smoothing operations: a drawdown is the authority selling dollars into a "
                   "weak won, which it cannot do forever"),
        payer="won shorts who read intervention only after the fact",
        constraint="the BOK publishes intervention net totals quarterly, with a lag",
        licence=_BOK, source_culture="KR/ko", participant_structure=("policy_driven",),
        failure_mode_hypothesis=("fails when valuation (EUR/JPY moves, bond prices) dominates "
                                 "the monthly change, which a raw MoM cannot separate"),
        crowding_prior="low", note=_ECOS_NOTE),
    Source(
        id="kr_ecos_export_prices", name="Korea export price index, won basis (ECOS 402Y014)",
        url=ECOS_URL + ECOS_PATHS["kr_ecos_export_prices"], region="KR", language="ko",
        cadence="monthly", parse=make_ecos_parser("export_price_index"),
        rule=_lag_rule(20, 0, weekday=True, calendar="KR"), transform="yoy_monthly",
        key_env="ECOS_API_KEY",
        instruments={"USDKRW": -1, "AUDUSD": 1}, signal_series=("export_price_index",),
        mechanism=("Korean export prices are the pricing power of the Asian manufacturing "
                   "chain (chips, petrochemicals, steel): rising export prices are terms of "
                   "trade for the won and a demand read for the commodity bloc"),
        payer="slow repricers of Asian terms of trade",
        constraint="price indices print monthly and three weeks late",
        licence=_BOK, source_culture="KR/ko",
        participant_structure=("physical_flow", "institutional"),
        failure_mode_hypothesis=("fails when the won-basis index moves on the won itself "
                                 "(a translation effect) rather than on contract prices"),
        crowding_prior="low", note=_ECOS_NOTE),
    Source(
        id="hk_hkma_interbank_liquidity",
        name="HKMA daily interbank liquidity (aggregate balance, CU FX leg, HIBOR, TWI)",
        url=HKMA_BASE + "daily-monetary-statistics/daily-figures-interbank-liquidity",
        region="HK", language="en", cadence="daily", parse=parse_hkma_liquidity,
        rule=_lag_rule(1, 1, calendar="HK"), transform="level_dev",
        instruments={"HK50": 1, "USDHKD": 1, "AUDUSD": 1},
        series_instruments={"hibor": {"USDHKD": -1, "HK50": -1},
                            "cu_forex": {"USDHKD": 1, "HK50": 1, "USDCNH": -1}},
        signal_series=("aggregate_balance_hkd_mn", "cu_forex_trans_t1_hkd_mn"),
        mechanism=("under the currency board the aggregate balance IS HKD liquidity: a "
                   "weak-side Convertibility Undertaking purchase drains it, HIBOR rises toward "
                   "SOFR and the HKD carry trade unwinds; a strong-side sale floods it"),
        payer="HKD carry trades and HK equity holders who wait for HIBOR to move",
        constraint="the CU settles T+2 and the balance moves on a fixed schedule",
        licence=_HKMA, source_culture="HK/en",
        participant_structure=("policy_driven", "settlement_constrained"),
        failure_mode_hypothesis=("fails around IPO subscription and dividend seasons, when "
                                 "HIBOR spikes on locked liquidity without a CU leg"),
        crowding_prior="medium",
        note=("asia_sources `hkma_open_api` fetches the same endpoint as one generic frame; "
              "this is the parsed, paged series with currency-board semantics")),
    Source(
        id="hk_hkma_hibor_fixing", name="HKMA HIBOR fixings by tenor (HKAB, 11:15 HKT)",
        url=(HKMA_BASE + "monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily"
             "?segment=hibor.fixing"),
        region="HK", language="en", cadence="daily", parse=parse_hkma_hibor,
        rule=_lag_rule(0, 4, calendar="HK"), transform="level_dev",
        instruments={"USDHKD": -1, "HK50": -1, "USDCNH": -1},
        signal_series=("hibor_1m", "hibor_3m_on_spread"),
        mechanism=("the HIBOR term structure is the price of HKD funding; a rising 1M fixing or "
                   "a steepening 3M-over-overnight spread is the offshore market pricing a "
                   "liquidity drain before the aggregate balance shows it"),
        payer="HKD carry and HK equity books funded at HIBOR",
        constraint="the fixing is set once a day by the HKAB panel",
        licence=_HKMA, source_culture="HK/en", participant_structure=("institutional",),
        failure_mode_hypothesis=("fails in quarter-end and IPO lock-up spikes that mean-revert "
                                 "within days"),
        crowding_prior="medium"),
    Source(
        id="hk_hkma_monetary_base", name="HKMA daily monetary base (aggregate balance, EFBN)",
        url=HKMA_BASE + "daily-monetary-statistics/daily-figures-monetary-base",
        region="HK", language="en", cadence="daily", parse=parse_hkma_monetary_base,
        rule=_lag_rule(1, 2, calendar="HK"), transform="level_dev",
        instruments={"HK50": -1, "USDHKD": -1},
        series_instruments={"aggregate_balance": {"HK50": 1, "USDHKD": 1}},
        signal_series=("efbn_outstanding_hkd_mn",),
        mechanism=("Exchange Fund Bill issuance is the HKMA's own liquidity tool: issuing bills "
                   "moves cash out of the aggregate balance as surely as a CU purchase"),
        payer="HK equity and HKD funding positions that read only HIBOR",
        constraint="EFBN tenders are scheduled; their liquidity effect lands on settlement",
        licence=_HKMA, source_culture="HK/en", participant_structure=("policy_driven",),
        failure_mode_hypothesis=("fails when issuance is a pre-announced roll with no net "
                                 "change in outstanding"),
        crowding_prior="low"),
)

#: Terms for the plane rows, read 2026-10-06 (TERMS_EVIDENCE for the 2026-09-30 review is
#: separate and pinned to that review).
KR_HK_TERMS: dict[str, tuple[str, str]] = {
    # FAIL CLOSED (audit of PR #239, 2026-10-06): the ECOS terms page could not be read (it is a
    # JavaScript app, and ecos.bok.or.kr / www.bok.or.kr / data.go.kr refuse this container's
    # proxy), so no clause permitting use has been quoted. A documented free-key API is not a
    # licence. Fenced until a human reads the 이용약관 and quotes the permitting clause.
    "kr_ecos_base_rate": ("to_confirm", "BOK ECOS Open API: terms of use not read, no "
                          "permitting clause quoted (2026-10-06)"),
    "kr_ecos_call_rate": ("to_confirm", "BOK ECOS Open API: terms of use not read, no "
                          "permitting clause quoted (2026-10-06)"),
    "kr_ecos_fx_reserves": ("to_confirm", "BOK ECOS Open API: terms of use not read, no "
                            "permitting clause quoted (2026-10-06)"),
    "kr_ecos_export_prices": ("to_confirm", "BOK ECOS Open API: terms of use not read, no "
                              "permitting clause quoted (2026-10-06)"),
    "hk_hkma_interbank_liquidity": ("confirmed", "DATA.GOV.HK terms: commercial and "
                                    "non-commercial reuse, free, with attribution"),
    "hk_hkma_hibor_fixing": ("confirmed", "DATA.GOV.HK terms: commercial and non-commercial "
                             "reuse, free, with attribution"),
    "hk_hkma_monetary_base": ("confirmed", "DATA.GOV.HK terms: commercial and non-commercial "
                              "reuse, free, with attribution"),
}
_CHK_PLANES = "2026-10-06"
_DGH = {"terms_url": "https://data.gov.hk/en/terms-and-conditions",
        "terms_quote": ("You are allowed to browse, download, distribute, reproduce, hyperlink "
                        "to, and print the Data for both commercial and non-commercial purposes "
                        "on a free-of-charge basis"),
        "api_doc_quote": ("No application, registration or certification is required for using "
                          "the Open API offered by the HKMA's website. It is also free of "
                          "charge. (apidocs.hkma.gov.hk/abouthkmasapi)"),
        "robots": "api.hkma.gov.hk is the documented Open API host",
        "checked_at": _CHK_PLANES}
#: The HKMA's own API documentation page for EACH row's dataset (read 2026-10-06; the earlier
#: listing cited the end-of-period interbank-rate table, a different dataset).
_HKMA_DOC = "https://apidocs.hkma.gov.hk/documentation/market-data-and-statistics/"
_HKMA_LISTING: dict[str, dict[str, str]] = {
    "hk_hkma_interbank_liquidity": {
        "listing_url": _HKMA_DOC + "daily-monetary-statistics/daily-figures-interbank-liquidity",
        "listing_quote": ("Daily Figures of Interbank Liquidity - Hong Kong Monetary Authority; "
                          "https://api.hkma.gov.hk/public/market-data-and-statistics/"
                          "daily-monetary-statistics/daily-figures-interbank-liquidity")},
    "hk_hkma_hibor_fixing": {
        "listing_url": _HKMA_DOC + "monthly-statistical-bulletin/er-ir/hk-interbank-ir-daily",
        "listing_quote": ("Hong Kong Interbank Interest Rates - Daily figures - Hong Kong "
                          "Monetary Authority; HIBOR fixings 'usually released on the website "
                          "of the HKAB each business day (excluding Saturdays) at 11.15 a.m.'")},
    "hk_hkma_monetary_base": {
        "listing_url": _HKMA_DOC + "daily-monetary-statistics/daily-figures-monetary-base",
        "listing_quote": ("Daily Figures of Monetary Base - Hong Kong Monetary Authority; "
                          "https://api.hkma.gov.hk/public/market-data-and-statistics/"
                          "daily-monetary-statistics/daily-figures-monetary-base")},
}
#: The ECOS terms attempt, recorded so the next reader knows what was tried.
_ECOS_TERMS_ATTEMPT = {
    "terms_url": "https://ecos.bok.or.kr/api/",
    "terms_quote": ("(not readable: ecos.bok.or.kr/api is a JavaScript app; the page and its "
                    "terms route returned 404 to the reader and ecos.bok.or.kr, www.bok.or.kr "
                    "and www.data.go.kr are refused by this container's proxy. Web search "
                    "found no copy of the ECOS Open API 이용약관. No clause permitting use has "
                    "been quoted, so the rows stay to_confirm)"),
    "robots": "not readable from the authoring container",
    "decision": "to_confirm",
    "box_action": ("read https://ecos.bok.or.kr/api/ (이용약관 / 이용안내) on the box, quote the "
                   "clause that permits use of the data, and only then set these rows confirmed"),
    "checked_at": _CHK_PLANES}
#: Evidence for the plane rows AND for the two refused hosts no fetcher is built for.
KR_HK_TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    **{sid: {**_DGH, **_HKMA_LISTING[sid]} for sid in _HKMA_LISTING},
    **{sid: dict(_ECOS_TERMS_ATTEMPT)
       for sid in ("kr_ecos_base_rate", "kr_ecos_call_rate", "kr_ecos_fx_reserves",
                   "kr_ecos_export_prices")},
    "kr_krx_market_data": {
        "terms_url": "https://openapi.krx.co.kr/contents/OPP/INFO/OPPINFO005.jsp",
        "terms_quote": ("Art. 6(2): API Users may only use the API Service for non-commercial "
                        "purposes and may not charge third parties any consideration for the "
                        "results of the API Service. Art. 11(2): The API User may not provide "
                        "the data provided by the KRX to any third parties."),
        "robots": "not read: the terms alone refuse commercial use",
        "decision": "refused",
        "checked_at": _CHK_PLANES},
    "hk_hkex_stock_connect": {
        "terms_url": "https://www.hkex.com.hk/Global/Exchange/Terms-of-Use",
        "terms_quote": ("You are not permitted to ... create or compile derivative works "
                        "(including, without limitation, through framing or systematic "
                        "retrieval to create collections, compilations, databases or "
                        "directories) from the Information ... You are not permitted to "
                        "conduct, facilitate, enable, authorise or permit any text or data "
                        "mining or web scraping in relation to this Website"),
        "robots": "not read: the terms alone refuse systematic retrieval",
        "decision": "refused",
        "checked_at": _CHK_PLANES},
}
#: What each refused host would have carried, and the lawful series standing nearest to it.
KR_HK_REFUSED: dict[str, dict[str, Any]] = {
    "kr_krx_market_data": {
        "would_carry": ["daily investor-type net buying (foreign / institutional / retail) "
                        "for KOSPI and KOSDAQ", "program trading (arbitrage / non-arbitrage)",
                        "short-selling balances", "KOSPI200 futures and options open interest"],
        "status": "BLOCKED_ON_TERMS:refused",
        # The directive's Korea-superplane rows this refusal leaves without a lawful source.
        "directive_rows": {
            "ASIA-0465": "BLOCKED: program trading -- KRX terms refused, no lawful substitute",
            "ASIA-0466": "BLOCKED: short selling -- KRX terms refused, no lawful substitute",
            "ASIA-0467": "BLOCKED: derivatives OI -- KRX terms refused, no lawful substitute"},
        # The ECOS rows are themselves to_confirm (2026-10-06): nearest, not yet lawful-confirmed.
        "nearest_lawful": ["kr_ecos_call_rate", "kr_ecos_fx_reserves", "kr_exports_early"],
        "why_not_a_substitute": ("no free public source with commercial reuse publishes "
                                 "investor-type flows or KOSPI200 OI; the nearest lawful series "
                                 "measure onshore funding and the authority's FX footprint, "
                                 "not who is buying")},
    "hk_hkex_stock_connect": {
        "would_carry": ["Northbound / Southbound daily net buy and turnover"],
        "status": "BLOCKED_ON_TERMS:refused",
        "nearest_lawful": ["hk_hkma_interbank_liquidity"],
        "why_not_a_substitute": ("the CU FX leg and the aggregate balance measure the HKD side "
                                 "of cross-border flow, not the mainland equity leg")},
}

TERMS: dict[str, tuple[str, str]] = {
    "kr_exports_early": ("confirmed", "KOGL public-sector open licence"),
    "us_tsa_throughput": ("confirmed", "US federal work, public domain"),
    "us_census_marts_ex_autos": ("confirmed", "US Census documented public API, public domain"),
    "jp_jnto_arrivals": ("refused", "JNTO site policy: unauthorised duplication or transmission of "
                         "published works (incl. databases) is copyright infringement"),
    "jp_tokyo_cpi": ("confirmed", "e-Stat documented API, Government of Japan statistics"),
    "cn_firms_industrial": ("confirmed", "NASA open data, documented API"),
    "imf_portwatch_ports": ("confirmed", "IMF PortWatch public statistics, documented ArcGIS API"),
    "imf_portwatch_chokepoints": ("confirmed", "IMF PortWatch public statistics, documented "
                                  "ArcGIS API"),
    "in_gold_imports": ("confirmed", "Government of India press releases (PIB), public"),
    "cn_sge_premium": ("to_confirm", "SGE site shows only 'All Right Reserved'; no terms or "
                       "licence page found, no robots.txt"),
    "gdelt_events_country": ("confirmed", "GDELT: unrestricted use with citation"),
    "wiki_asia_attention": ("confirmed", "Wikimedia pageviews API, CC0"),
    "us_oi_card_spend": ("confirmed", "OI README: 'Anyone is welcome to use this data'"),
    "kr_bok_card_spend": ("to_confirm", "BOK ECOS Open API: a documented free-key API is not "
                          "a licence; the terms of use were never read or quoted (re-audited "
                          "2026-10-06, see KR_HK_TERMS_EVIDENCE)"),
    "jp_meti_retail": ("confirmed", "Government of Japan Standard Terms of Use (CC BY compatible)"),
    "cn_nbs_retail": ("confirmed", "NBS terms of service: users may download and use NBS "
                      "statistics; reuse welcomed with attribution, except items a-f (third-"
                      "party links and works, marked no-reprint content, site graphics and "
                      "programs, registered-user content, content barred by law or deemed "
                      "unsuitable) -- NBS's own public retail-sales release falls under none; "
                      "no robots.txt"),
    "cn_holiday_spend": ("refused", "MCT disclaimer: no reprint, link or other copying without "
                         "written authorisation from the MCT Information Centre"),
    "in_npci_upi": ("refused", "npci.org.in robots.txt disallows automated agents on the "
                    "statistics path and the disclaimer page"),
    "tr_bkm_card": ("refused", "BKM legal notice: no copying or reproduction without prior "
                    "written permission; no commercial use"),
    "br_cielo_icva": ("refused", "Cielo terms: copying, reproduction or any other use of content "
                      "is forbidden; content only by the means made available"),
    "mx_antad_sss": ("refused", "ANTAD terms: copy only for personal use; electronic "
                     "reproduction, publication or distribution prohibited"),
    "za_beti": ("to_confirm", "PayInc site is a JS app; no terms page or robots.txt could be "
                "read"),
    "us_oi_google_mobility": ("confirmed", "OI README: 'Anyone is welcome to use this data'"),
    "kr_kobis_box_office": ("confirmed", "KOBIS documented Open API (Korean Film Council)"),
    "kr_seoul_subway": ("confirmed", "Seoul Open Data Plaza, KOGL type 1"),
    "cn_maoyan_box_office": ("refused", "piaofang.maoyan.com robots.txt disallows automated agents "
                             "on the dashboard-ajax endpoint"),
    "cn_baidu_migration": ("to_confirm", "Baidu terms (baidu.com/duty) blocked by robots.txt, so "
                           "unread; huiyan has no robots.txt"),
    "kr_busan_port": ("to_confirm", "BPA copyright policy / KOGL mark not found; robots.txt "
                      "only names Yeti and Googlebot"),
    "sg_port_throughput": ("confirmed", "SingStat Table Builder API, Singapore Open Data Licence"),
    "cn_mot_port_weekly": ("to_confirm", "MOT disclaimer bars commercial verbatim reprint but "
                           "grants no reuse licence; no robots.txt"),
    "jp_estat_immigration": ("confirmed", "e-Stat terms: free reuse incl. commercial, CC BY 4.0 "
                             "compatible"),
    "hk_immd_passenger": ("confirmed", "DATA.GOV.HK terms: commercial and non-commercial reuse, "
                          "free, with attribution"),
    "br_bcb_payments": ("confirmed", "BCB Open Data portal, ODbL"),
    "mx_inegi_emec": ("confirmed", "INEGI Términos de Libre Uso: commercial exploitation "
                      "allowed with credit"),
    "tr_tuik_retail": ("confirmed", "TÜİK legal notice: reuse without permission, source cited"),
    "kr_mof_container_teu": ("confirmed", "data.go.kr: 이용허락범위 제한 없음 (unrestricted)"),
}
TERMS_VALUES = ("confirmed", "to_confirm", "refused")

#: Evidence for the terms decisions reviewed on 2026-09-30 (the 13 former `to_confirm` sources).
#: terms_quote is verbatim from terms_url as fetched that day, or says the page could not be read.
#: robots is what robots.txt said for the source's host and path. See
#: /mnt/project-files/reports/asia_source_terms_2026-09-30.md.
_CHK = "2026-09-30"
TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "cn_maoyan_box_office": {
        "terms_url": "https://piaofang.maoyan.com/i/rules/privacy-agreement?pid=64",
        "terms_quote": "(not readable: the page and the data endpoint are robots.txt-disallowed)",
        "robots": "disallowed: robots check refused /robots.txt, /i/rules/ and /dashboard-ajax",
        "checked_at": _CHK},
    "cn_baidu_migration": {
        "terms_url": "https://www.baidu.com/duty/",
        "terms_quote": "(not readable: baidu.com/duty is robots.txt-disallowed; huiyan footer "
                       "links only '使用百度前必读')",
        "robots": "huiyan.baidu.com/robots.txt 404 (no rules); historycurve.jsonp fetched",
        "checked_at": _CHK},
    "jp_jnto_arrivals": {
        "terms_url": "https://www.jnto.go.jp/site-info/site-policy.html",
        "terms_quote": ("掲載著作物をJNTOをはじめとする権利者に無断で"
                        "転⽤、複製、送信、放送、配布、貸与、翻訳、変造する事は"
                        "著作権侵害となり、法的に罰せられることがあります。"),
        "robots": "www.jnto.go.jp/robots.txt 404 (no rules)",
        "checked_at": _CHK},
    "cn_sge_premium": {
        "terms_url": "https://www.sge.com.cn/",
        "terms_quote": "Copyright 2016 上海黄金交易所 All Right Reserved (no terms page found)",
        "robots": "www.sge.com.cn/robots.txt 404 (no rules)",
        "checked_at": _CHK},
    "cn_nbs_retail": {
        "terms_url": "https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html",
        "terms_quote": ("用户可以在本网站下载和使用国家统计局发布的统计数据 / "
                        "欢迎转载或引用本网所载内容，但以下内容除外：a.本网所指向的非本网内容的相关"  # noqa: RUF001
                        "链接内容；b.已作出不得转载或未经许可不得转载声明的内容；c.未由本网署名或本网"  # noqa: RUF001
                        "引用、转载的他人作品等非本网版权内容；d.本网中特有的图形、标志、页面风格、"  # noqa: RUF001
                        "编排方式、程序等；e.本网中必须具有特别授权或具有注册用户资格方可知晓的内容；"  # noqa: RUF001
                        "f.其他法律不允许或本网认为不适合转载的内容。"),
        "judgement": ("re-read 2026-09-30 with the exclusions: the monthly retail-sales release is "
                      "NBS's own signed, public statistics -- not a link (a), not marked "
                      "no-reprint (b), not a third-party work (c), not site design (d), not "
                      "registered-user content (e); (f) is discretionary and names nothing. "
                      "Stays confirmed"),
        "robots": "www.stats.gov.cn/robots.txt 404 (no rules); terms name no crawler clause",
        "checked_at": _CHK},
    "cn_holiday_spend": {
        "terms_url": "https://www.mct.gov.cn/dbdh/mzsm/201902/t20190202_837199.html",
        "terms_quote": ("任何单位和个人未经文化和旅游部信息中心书面授权"
                        "不得转载、链接、转贴或以其他方式复制发表。"),
        "robots": "www.mct.gov.cn/robots.txt 404 (no rules)",
        "checked_at": _CHK},
    "in_npci_upi": {
        "terms_url": "https://www.npci.org.in/disclaimer",
        "terms_quote": "(not readable: the disclaimer page is robots.txt-disallowed)",
        "robots": "disallowed: robots check refused /robots.txt, /disclaimer and "
                  "/what-we-do/upi/product-statistics",
        "checked_at": _CHK},
    "tr_bkm_card": {
        "terms_url": "https://bkm.com.tr/bkm/yasal-uyari/",
        "terms_quote": ("Burada mevcut olan bilgiler BKM'nin önceden "
                        "yazılı izni alınmaksızın kısmen "  # noqa: RUF001
                        "veya tamamen kopya edilemez, "
                        "dağıtılamaz, kiralanamaz, çoğaltılamaz"),  # noqa: RUF001
        "robots": "allowed: 'User-agent: * Disallow: /wp-admin/' only",
        "checked_at": _CHK},
    "br_cielo_icva": {
        "terms_url": "https://www.cielo.com.br/termos-condicoes-de-uso/",
        "terms_quote": "todo o Conteúdo é de propriedade exclusiva da CIELO [...] sendo vedada sua "
                       "cópia, reprodução, ou qualquer outro tipo de utilização",
        "robots": ("allowed for /icva/ (blocks /admin, /login, /busca/, /search/ and named "
                   "SEO bots)"),
        "checked_at": _CHK},
    "mx_antad_sss": {
        "terms_url": "https://antad.net/admin/wp-content/uploads/2024/10/"
                     "terminos-y-condiciones-de-uso.pdf",
        "terms_quote": ("El usuario sólo podrá imprimir y/o copiar cualquier información "
                        "contenida o publicada en el sitio web www.antad.net exclusivamente "
                        "para uso personal"),
        "robots": "allowed: 'User-agent: * Disallow: /wp-admin/' and an ftp tmp folder only",
        "checked_at": _CHK},
    "za_beti": {
        "terms_url": "https://www.payinc.co.za/",
        "terms_quote": "(not readable: JS-only site, no terms link in served HTML)",
        "robots": "not readable: robots.txt URL returned the JS shell, not a robots file",
        "checked_at": _CHK},
    "kr_busan_port": {
        "terms_url": "https://www.busanpa.com/index.bpa?menuCd=DOM_000000105005001003",
        "terms_quote": ("(not found: no 저작권정책 or 공공누리 mark in the served HTML of the "
                        "home page or of the current statistics page; old board URL 404)"),
        "robots": "rules only for Yeti and Googlebot (Disallow /iam/, /cms/, /board/download.*); "
                  "none for other agents",
        "checked_at": _CHK},
    "cn_mot_port_weekly": {
        "terms_url": "https://www.mot.gov.cn/wangzhangongneng/202512/t20251216_4181727.html",
        "terms_quote": ("任何媒体、互联网站和商业机构不得利用本网站发布的内容"
                        "进行商业性的原版原式地转载"),
        "robots": "www.mot.gov.cn/robots.txt 404 (no rules); xxgk.mot.gov.cn list read "
                  "2026-09-30 shows no statement beyond the site disclaimer",
        "checked_at": _CHK},
    # ---- the lawful substitutes (terms verified by fetching the terms page, 2026-09-30)
    "jp_estat_immigration": {
        "terms_url": "https://www.e-stat.go.jp/terms-of-use",
        "terms_quote": ("複製、公衆送信、翻訳・変形等の翻案等、自由に利用できます / "
                        "本利用ルールはクリエイティブ・コモンズ・ライセンスの表示 4.0 国際"
                        "...と互換性があり"),
        "robots": "api.e-stat.go.jp is the documented API (free appId)",
        "checked_at": _CHK},
    "hk_immd_passenger": {
        "terms_url": "https://data.gov.hk/en/terms-and-conditions",
        "terms_quote": ("You are allowed to browse, download, distribute, reproduce, hyperlink "
                        "to, and print the Data for both commercial and non-commercial purposes "
                        "on a free-of-charge basis"),
        "robots": ("dataset page data.gov.hk/en-data/dataset/hk-immd-set5-statistics-daily-"
                   "passenger-traffic names the CSV and these terms"),
        "checked_at": _CHK},
    "br_bcb_payments": {
        "terms_url": "https://dadosabertos.bcb.gov.br/dataset/estatisticas-meios-pagamentos",
        "terms_quote": "Open Data Commons Open Database License (ODbL)",
        "robots": "olinda documentation page robots-unreadable from the authoring box; the "
                  "OData endpoint is the portal's own listed resource",
        "checked_at": _CHK},
    "mx_inegi_emec": {
        "terms_url": "https://www.inegi.org.mx/inegi/terminos.html",
        "terms_quote": ("Puede explotar comercialmente la información, utilizándola como insumo "
                        "para generar otros productos o servicios. / Debe otorgar los créditos "
                        "correspondientes al INEGI como autor"),
        "robots": "the BIE API is INEGI's documented developer API (free token)",
        "checked_at": _CHK},
    "tr_tuik_retail": {
        "terms_url": "https://www.tuik.gov.tr/Kurumsal/Yasal_Uyari",
        "terms_quote": ("İnternet sitemizden, yayınlarımızdan veya veri "  # noqa: RUF001
                        "tabanlarımızdan elde edilen verilerin, kaynak gösterilmek "  # noqa: RUF001
                        "suretiyle herhangi bir izine gerek duymaksızın yeniden "  # noqa: RUF001
                        "kullanımı mümkündür."),  # noqa: RUF001
        "robots": "veriportali.tuik.gov.tr is a JS app; bulletin URL configured on the box",
        "checked_at": _CHK},
    "kr_mof_container_teu": {
        "terms_url": "https://www.data.go.kr/data/15059131/openapi.do",
        "terms_quote": "이용허락범위 제한 없음",
        "policy_url": "https://www.data.go.kr/ugs/selectPortalPolicyView.do",
        "policy_quote": ("공공데이터포털을 통해 제공 중인 공공데이터는 "
                         "별도의 신청절차 없이 이용 가능"),
        "robots": "apis.data.go.kr is the portal's documented Open API (free service key)",
        "checked_at": _CHK},
}

TERMS.update(KR_HK_TERMS)
TERMS_EVIDENCE["kr_bok_card_spend"] = dict(_ECOS_TERMS_ATTEMPT)

#: HOSTS GOVERNED BY A TERMS ROW (the mechanism of PR #229, carried here for the KR/HK hosts and
#: the asia collector's keyed sources; audit of PR #239, 2026-10-06). One decision binds every
#: organ that touches the host: `asia_collector` asks `terms_gate` before it sends ANY request
#: (robots.txt included), so a refused or to_confirm host is sent nothing. Matched on the host's
#: registrable suffix, so www./data./openapi. sub-hosts are governed together.
TERMS_HOSTS: dict[str, str] = {
    "krx.co.kr": "kr_krx_market_data",              # data., openapi., marketdata. -- refused
    "hkex.com.hk": "hk_hkex_stock_connect",         # refused
    "ecos.bok.or.kr": "kr_bok_card_spend",          # ECOS Open API -- to_confirm
    "api.hkma.gov.hk": "hk_hkma_interbank_liquidity",
    "index.baidu.com": "asia_baidu_index",          # login cookie -- refused
}

#: GATE-ONLY TERMS ROWS: decisions for feeds that are not alt_proxies sources (so they stay out
#: of TERMS, whose keys are exactly this organ's sources) but are fetched by another organ
#: through `terms_gate` -- here the asia collector's rows, named by their `terms_ref`. Same
#: vocabulary, same fail-closed rule, same evidence shape.
_KEYED = "a keyed fetch sends a credential, so it waits on a quoted permitting clause"
GATE_TERMS: dict[str, tuple[str, str]] = {
    "kr_krx_market_data": ("refused", "KRX OPEN API terms Art. 6(2) non-commercial only, "
                           "Art. 11(2) no provision to third parties"),
    "hk_hkex_stock_connect": ("refused", "HKEX Terms of Use: no systematic retrieval, no text "
                              "or data mining or web scraping"),
    "asia_baidu_index": ("refused", "Baidu Index is read only through a logged-in account "
                         "cookie: a private session credential, outside lawful public access"),
    "asia_tushare": ("to_confirm", "TuShare Pro: the user agreement was not readable (the "
                     "pricing page names it but does not carry it); " + _KEYED),
    "asia_collective2": ("to_confirm", "Collective2 API terms not read; " + _KEYED),
    "asia_darwinex": ("to_confirm", "Darwinex API terms not read; " + _KEYED),
    "asia_banxico_series": ("to_confirm", "Banxico SIE API terms page not readable (404 / "
                            "empty to the reader); " + _KEYED),
    "asia_eia_energy": ("confirmed", "EIA copyrights and reuse: US government publications "
                        "are public domain; data may be used and distributed"),
    "asia_nasa_firms": ("confirmed", "NASA Earth science data policy: available fully, "
                        "openly and without restrictions, including corporate use"),
}
GATE_TERMS_EVIDENCE: dict[str, dict[str, str]] = {
    "kr_krx_market_data": KR_HK_TERMS_EVIDENCE["kr_krx_market_data"],
    "hk_hkex_stock_connect": KR_HK_TERMS_EVIDENCE["hk_hkex_stock_connect"],
    "asia_baidu_index": {
        "terms_url": "https://index.baidu.com/",
        "terms_quote": ("(the registry row authenticates with BAIDU_INDEX_COOKIE, a logged-in "
                        "session cookie; no public, unauthenticated route exists)"),
        "decision": "refused", "checked_at": _CHK_PLANES},
    "asia_tushare": {
        "terms_url": "https://tushare.pro/document/1?doc_id=290",
        "terms_quote": ("(not a terms page: the permissions/pricing table links a separate "
                        "User Agreement and Service Agreement, which were not read)"),
        "decision": "to_confirm", "checked_at": _CHK_PLANES},
    "asia_collective2": {"terms_url": "https://api.collective2.com/",
                         "terms_quote": "(not read)", "decision": "to_confirm",
                         "checked_at": _CHK_PLANES},
    "asia_darwinex": {"terms_url": "https://api.darwinex.com/",
                      "terms_quote": "(not read)", "decision": "to_confirm",
                      "checked_at": _CHK_PLANES},
    "asia_banxico_series": {
        "terms_url": "https://www.banxico.org.mx/SieAPIRest/service/v1/?locale=en",
        "terms_quote": ("(not readable: the API landing page returned no text to the reader and "
                        "/SieAPIRest/service/v1/doc/terminosUso returned 404)"),
        "decision": "to_confirm", "checked_at": _CHK_PLANES},
    "asia_eia_energy": {
        "terms_url": "https://www.eia.gov/about/copyrights_reuse.php",
        "terms_quote": ("U.S. government publications are in the public domain and are not "
                        "subject to copyright protection. / You may use and/or distribute any "
                        "of our data, files, databases, reports, graphs, charts, and other "
                        "information products that are on our website or that you receive "
                        "through our email distribution service."),
        "attribution": "Source: U.S. Energy Information Administration (<publication date>)",
        "decision": "confirmed", "checked_at": _CHK_PLANES},
    "asia_nasa_firms": {
        "terms_url": ("https://www.earthdata.nasa.gov/learn/articles/"
                      "nasa-earth-science-data-yours-use-fully-and-without-restrictions"),
        "terms_quote": ("NASA's data policy ensures that all NASA data are available fully, "
                        "openly, and without restrictions. / These data are not just for "
                        "individual use, but also are freely available for corporate use as "
                        "well."),
        "decision": "confirmed", "checked_at": _CHK_PLANES},
}


def terms_gate(ref_or_url: str) -> tuple[str, str]:
    """(state, why) for a TERMS id or a URL. `confirmed` / `to_confirm` / `refused` for a governed
    id or host, `ungoverned` for a URL on no governed host. FAIL CLOSED: an id this table does not
    know is `to_confirm`, never permission."""
    ref = str(ref_or_url or "")
    if "://" in ref or ref.startswith("//"):
        host = urllib.parse.urlsplit(ref if "://" in ref else "https:" + ref).netloc.lower()
        host = host.split(":")[0]
        sid = next((v for k, v in TERMS_HOSTS.items() if host == k or host.endswith("." + k)),
                   None)
        if sid is None:
            return "ungoverned", ""
        ref = sid
    state, why = TERMS.get(ref) or GATE_TERMS.get(
        ref, ("to_confirm", f"{ref}: no terms row -- fail closed"))
    ev = TERMS_EVIDENCE.get(ref) or GATE_TERMS_EVIDENCE.get(ref) or {}
    if ev.get("terms_url"):
        why = f"{why} [{ev['terms_url']}, checked {ev.get('checked_at', '?')}]"
    return state, why


SOURCES = tuple(replace(s, terms=TERMS.get(s.id, ("to_confirm", ""))[0])
                for s in (*SOURCES, *SUBSTITUTE_SOURCES, *KR_HK_PLANE_SOURCES))
SUBSTITUTE_SOURCES = tuple(s for s in SOURCES if s.substitutes_for)
BY_ID = {s.id: s for s in SOURCES}

#: COVERAGE DOES NOT SHRINK WHEN TERMS BLOCK A SOURCE. Each blocked source (terms refused or
#: to_confirm) names the lawful source(s) standing in for it: every id here is a `confirmed`
#: source of this organ, verified from its own terms page (TERMS_EVIDENCE). Such a source reports
#: BLOCKED+SUBSTITUTE:<ids> and is counted as substituted, not lost. It is still NEVER fetched.
#: A blocked source absent from this table has no verified lawful substitute and stays
#: BLOCKED_ON_TERMS (see NO_SUBSTITUTE for why).
SUBSTITUTED_BY: dict[str, tuple[str, ...]] = {
    "jp_jnto_arrivals": ("jp_estat_immigration",),
    "cn_holiday_spend": ("cn_nbs_retail", "hk_immd_passenger"),
    "tr_bkm_card": ("tr_tuik_retail",),
    "br_cielo_icva": ("br_bcb_payments",),
    "mx_antad_sss": ("mx_inegi_emec",),
    "cn_maoyan_box_office": ("hk_immd_passenger",),
    "cn_sge_premium": ("in_gold_imports",),
    "cn_baidu_migration": ("hk_immd_passenger",),
    "kr_busan_port": ("kr_mof_container_teu", "imf_portwatch_ports"),
    "cn_mot_port_weekly": ("imf_portwatch_ports",),
}
#: Blocked sources with NO verified lawful substitute, and why (each has a box action queued in
#: /mnt/project-files/patches/DESKTOP_PASS2_STATUS.md).
NO_SUBSTITUTE: dict[str, str] = {
    "in_npci_upi": ("RBI payment-system indicators carry '© Reserve Bank of India. All Rights "
                    "Reserved' and no reuse grant; data.gov.in (GODL) pages are robots-disallowed "
                    "to the authoring fetcher, so no licence text could be read"),
    "za_beti": ("SARB disclaimer: IP 'cannot be used without written permission'; Stats SA's "
                "copyright page and PDFs are behind an Incapsula wall, so no reuse text could be "
                "read"),
}
#: The paid-substitute engine (#152) reads Asia-thread rows from
#: data/paid_data_substitutes_*.json; this is that file (regenerate with --write-rosters).
ENGINE_ROWS_FILE = DESK / "data" / "paid_data_substitutes_asia_blocked.json"
ROSTER_FILE = DESK / "data" / "source_rosters" / "asia_paid_substitutes_consumer.yaml"


def status_of(src: Source, environ: dict[str, str] | None = None) -> str:
    """One named state per source. Nothing here claims live yield: a source that has not returned
    real data on the box is UNMEASURED_LIVE_YIELD, and the pass report says what it parsed.
    `environ` replaces os.environ (the committed roster uses {} -- its status as declared)."""
    env: Any = os.environ if environ is None else environ
    if src.archive_until:
        return f"DEAD:{src.archive_until}"
    if src.terms != "confirmed":
        subs = SUBSTITUTED_BY.get(src.id)
        return (f"BLOCKED+SUBSTITUTE:{','.join(subs)}" if subs
                else f"BLOCKED_ON_TERMS:{src.terms}")
    if src.key_env and not env.get(src.key_env):
        return f"BLOCKED_ON_KEY:{src.key_env}"
    missing = [e for e in src.config_env if not env.get(e)]
    if missing:
        return "UNCONFIGURED:" + ",".join(missing)
    return "UNMEASURED_LIVE_YIELD"


def is_dead(src: Source) -> bool:
    return bool(src.archive_until)


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
    if src.id == "gdelt_events_country":
        return _gdelt_requests(src, now, state)
    if src.id in DATED_SOURCES:
        recent, lag, back = DATED_SOURCES[src.id]
        return _dated_requests(src, key, now, state, recent=recent, lag=lag, back=back)
    if src.id == "wiki_asia_attention":
        wstart = ((now - timedelta(days=45)).strftime("%Y%m%d") if state.get("full_done")
                  else "20150701")
        state["full_done_next"] = True
        return [Request(WIKI_URL.format(project=proj, title=urllib.parse.quote(title, safe=""),
                                        start=wstart, end=now.strftime("%Y%m%d")),
                        Ctx(part=label, fetched_at=now))
                for label, proj, title in WIKI_ASIA_ARTICLES]
    if src.id == "cn_baidu_migration":
        return [Request(src.url.replace("{city}", cid), Ctx(part=city, fetched_at=now))
                for city, cid in BAIDU_CITIES.items()]
    if src.id == "us_tsa_throughput":
        # The current page carries this year only; the year-on-year comparison needs last year's
        # page, which TSA publishes at /<year>.
        return [Request(src.url, Ctx(fetched_at=now)),
                Request(f"{src.url}/{now.year - 1}", Ctx(part="prior_year", fetched_at=now))]
    if src.id in HKMA_DATE_KEY:
        return _hkma_requests(src, now, state)
    url = (src.url.replace("{key}", key).replace("{yyyymmdd}", now.strftime("%Y%m%d"))
           .replace("{yyyymm}", now.strftime("%Y%m")))
    for env in src.config_env:
        code = os.environ.get(env, "").strip()
        if not code:
            return []                  # never a request built on a placeholder code
        url = url.replace("{" + env + "}", urllib.parse.quote(code, safe=""))
    return [Request(url, Ctx(fetched_at=now))]


#: Per-date sources: (recent days re-read each pass, publication lag in days, backfill days per
#: pass). The backfill walks back from `backfill_to` and commits only on an error-free pass.
DATED_SOURCES: dict[str, tuple[int, int, int]] = {
    "kr_kobis_box_office": (7, 1, 14), "kr_seoul_subway": (5, 4, 10),
    "cn_maoyan_box_office": (3, 1, 7)}
DATED_BACKFILL_DEPTH_D = 3 * 365


def _dated_requests(src: Source, key: str, now: datetime, state: dict[str, Any], *,
                    recent: int, lag: int, back: int) -> list[Request]:
    end = (now - timedelta(days=lag)).date()
    days = [end - timedelta(days=i) for i in range(recent)]
    cur = state.get("backfill_to")
    bf_end = date.fromisoformat(cur) if cur else days[-1] - timedelta(days=1)
    if bf_end > (now - timedelta(days=DATED_BACKFILL_DEPTH_D)).date():
        bf = [bf_end - timedelta(days=i) for i in range(back)]
        days += bf
        state["backfill_to_next"] = (bf[-1] - timedelta(days=1)).isoformat()
    return [Request(src.url.replace("{key}", key).replace("{date}", d.strftime("%Y%m%d")),
                    Ctx(part=d.isoformat(), start=d, end=d, fetched_at=now)) for d in days]


def _gdelt_requests(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    """Forward from `fwd` (next unread slot) to 30 minutes ago, then back from `back`, a fixed
    number of slots each way per pass. Cursors move in `collect_gdelt`, only over slots read."""
    last = now - timedelta(minutes=30)
    day0 = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    fwd = _t(state.get("fwd")) or day0
    fwd_slots = gdelt_slots(fwd, last)[:GDELT_FWD_PER_PASS]
    back_to = _t(state.get("back")) or (day0 - timedelta(minutes=15))
    floor = now - timedelta(days=GDELT_BACK_DEPTH_D)
    back_slots: list[str] = []
    t = back_to
    while len(back_slots) < GDELT_BACK_PER_PASS and t > floor:
        back_slots.append(t.strftime("%Y%m%d%H%M%S"))
        t -= timedelta(minutes=15)
    return ([Request(src.url.replace("{slot}", s), Ctx(part=f"fwd:{s}", fetched_at=now))
             for s in fwd_slots]
            + [Request(src.url.replace("{slot}", s), Ctx(part=f"back:{s}", fetched_at=now))
               for s in back_slots])


def _slot_time(slot: str) -> datetime:
    return datetime.strptime(slot, "%Y%m%d%H%M%S").replace(tzinfo=UTC)


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
    """Append-only: a key's FIRST value and first-seen instant never change; every different
    later value is APPENDED to the row's `vintages` as its own vintage, stamped with the instant
    it was seen (its knowable_at). `value_last` / `revision_time` / `n_revisions` summarise the
    newest vintage for older readers; nothing is ever overwritten in `vintages`."""
    added = revised = 0
    stamp = seen_at.isoformat(timespec="seconds")
    cal = getattr(src.rule, "calendar", None)
    for o in obs:
        k = f"{o.series}|{o.period.isoformat()}"
        rule_at = src.rule(o.period)
        basis = "release_rule"
        if cal and not release_calendar_known(cal, rule_at.year) and rule_at < seen_at:
            # No holiday calendar for that year here: the honest floor is the instant we saw it.
            rule_at, basis = seen_at, "first_seen_no_calendar"
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
                        "published_basis": "page" if pub else basis,
                        "revision_time": None, "n_revisions": 0, "vintages": []}
            added += 1
            continue
        row["last_seen_at"] = stamp
        if pub is not None and row.get("published_basis") != "page":
            row["published_time"] = pub.isoformat(timespec="seconds")
            row["published_basis"] = "page"
        elif row.get("published_basis") == "release_rule" and cal:
            # A row stamped before its rule learned the calendar is moved LATER, never earlier.
            old_t = _t(row.get("published_time"))
            if old_t is not None and rule_at > old_t and basis == "release_rule":
                row["published_time"] = rule_at.isoformat(timespec="seconds")
        if not math.isclose(float(row["value_last"]), o.value, rel_tol=1e-9, abs_tol=1e-12):
            vins = row.get("vintages")
            if not isinstance(vins, list):
                vins = row["vintages"] = _legacy_vintages(row)
            vins.append({"value": o.value, "seen_at": stamp})
            row["value_last"] = o.value
            row["revision_time"] = stamp
            row["n_revisions"] = int(row.get("n_revisions") or 0) + 1
            revised += 1
    return {"added": added, "revised": revised}


def _legacy_vintages(row: dict[str, Any]) -> list[dict[str, Any]]:
    """A row written before `vintages` existed kept only its LAST revision: that one is
    recovered (stamped at its own revision_time, flagged reconstructed); any between are lost."""
    if row.get("revision_time") and row.get("value_last") is not None:
        return [{"value": row["value_last"], "seen_at": row["revision_time"],
                 "reconstructed": True}]
    return []


def row_vintages(row: dict[str, Any]) -> list[dict[str, Any]]:
    """The revision vintages of one stored row, oldest first (the first print is not one)."""
    vins = row.get("vintages")
    if not isinstance(vins, list):
        vins = _legacy_vintages(row)
    return sorted((v for v in vins if isinstance(v, dict) and v.get("seen_at")
                   and v.get("value") is not None), key=lambda v: str(v["seen_at"]))


def revision_points(src: Source, store: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """EVERY REVISION IS ITS OWN VINTAGE (audit of PR #239, 2026-10-06). Per series, one point per
    revision vintage, knowable ONLY from the instant that vintage was first seen: `knowable_at` =
    `available_time` = its `received_at`. `revision_delta` is that vintage's value minus the
    PREVIOUS vintage's (the first print for the first revision); `revision_of` names the
    previous vintage's id. A revision is never put on the first print's stamp.

    This is the hook for the sensor ledger (PR #208): the asia sensor adapter maps these vintage
    rows onto it; this organ keeps them in its own vintage store and writes no second store."""
    out: dict[str, list[dict[str, Any]]] = {}
    for row in store.values():
        if not isinstance(row, dict) or not row.get("series"):
            continue
        vins = row_vintages(row)
        if not vins:
            continue
        name = str(row["series"])
        prev_val = float(row["value_first"])
        prev_id = _vintage(src.id, row.get("first_seen_at"), row["value_first"])
        for n, v in enumerate(vins, start=1):
            seen = str(v["seen_at"])
            vid = _vintage(src.id, seen, v["value"])
            out.setdefault(name, []).append({
                "d": str(row["period"]), "event_time": str(row["period"]),
                "available_time": seen, "knowable_at": seen, "received_at": seen,
                "first_seen_at": seen, "retrieval_time": seen, "revision_time": seen,
                "published_time": seen, "publication_time": str(row.get("published_time")),
                "vintage_id": vid, "vintage_n": n, "revision_of": prev_id,
                "reconstructed": bool(v.get("reconstructed")), "pit_quality": "live",
                "value": v["value"],
                "revision_delta": round(float(v["value"]) - prev_val, 6),
                "source_id": src.id, "metric": name})
            prev_val, prev_id = float(v["value"]), vid
    for pts in out.values():
        pts.sort(key=lambda p: (p["available_time"], p["d"]))
    return out


def as_of(points: dict[str, list[dict[str, Any]]], t: datetime
          ) -> dict[str, list[dict[str, Any]]]:
    """Only the points knowable at `t` (knowable_at, else available_time, <= t)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for name, pts in points.items():
        keep = [p for p in pts
                if (k := _t(p.get("knowable_at") or p.get("available_time"))) is not None
                and k <= t]
        if keep:
            out[name] = keep
    return out


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
            elif src.transform == "yoy_monthly":
                p0 = periods[i]
                back = pos.get(_month_end(p0.year - 1, p0.month))
                x = ((v / vals[back] - 1.0) * 100.0 if back is not None and back < i
                     and vals[back] > 0 else None)
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
        seen_sorted: list[float] = []
        prev_delta: float | None = None
        for i, r in enumerate(rows):
            x = pace[i]
            surprise = z = exp = None
            # LEVEL / CHANGE / ACCELERATION on the first-seen value, in availability order (the
            # five alpha objects of the alt-data factory: level, change, acceleration, surprise,
            # revision). Each uses only what was knowable at this point.
            delta = vals[i] - vals[i - 1] if i >= 1 else None
            accel = delta - prev_delta if delta is not None and prev_delta is not None else None
            prev_delta = delta
            pct = (bisect.bisect_left(seen_sorted, vals[i]) / len(seen_sorted)
                   if len(seen_sorted) >= EXPECTATION_N else None)
            bisect.insort(seen_sorted, vals[i])
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
                "revision_time": None,                 # the first print; see revision_points
                "vintage_id": _vintage(src.id, r.get("first_seen_at"), r["value_first"]),
                "pit_quality": quality,
                "value": r["value_first"],
                "pace": None if x is None else round(x, 6),
                "surprise": None if surprise is None else round(surprise, 6),
                "surprise_z": None if z is None else round(z, 4),
                "delta": None if delta is None else round(delta, 6),
                "acceleration": None if accel is None else round(accel, 6),
                # The FIRST print revises nothing: a later revision is its own vintage, stamped
                # at its own first-seen instant, in `revision_points` -- never on this stamp.
                "revision_delta": None,
                # MANDATE 2026-10-06 s2.5 names, beside the desk's own (same values, never a
                # second clock): the sensor ledger and its adapter read these verbatim.
                "source_id": src.id, "metric": name,
                "knowable_at": str(r["published_time"]),
                "publication_time": str(r["published_time"]),
                "received_at": r.get("first_seen_at"),
                "expected_value": None if exp is None else round(exp, 6),
                "raw_surprise": None if surprise is None else round(surprise, 6),
                "percentile": None if pct is None else round(pct, 4),
                "revision_of": None})
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
        for col in ("value", "pace", "surprise_z", "delta", "acceleration"):
            keep = [{"d": p["d"], "v": p.get(col), "available_time": p["available_time"],
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
            "shape": ("series[<series>.<value|pace|surprise_z|delta|acceleration>].points, "
                      "joined on available_time"),
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
                            "surprise_z": p["surprise_z"], "pit_quality": p["pit_quality"],
                            "delta": p.get("delta"), "acceleration": p.get("acceleration"),
                            "revision_delta": p.get("revision_delta")}
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


DIRECT_FAMILY = "exogenous_conditioner"


def may_mint(sym: str, family: str = DIRECT_FAMILY) -> bool:
    """THE TWO-LANE ORDER, by ASSET CLASS from `universe_policy` (never a symbol list). A share
    CFD mints only in CROSS_SECTIONAL_FAMILIES or the news lane, so it is never a direct or
    conditioned cell here; its series go to the equity hand-off instead."""
    from research import universe_policy
    return bool(universe_policy.may_hypothesise(sym, family))


def equity_handoff(sources: Iterable[Source] = SOURCES) -> dict[str, Any]:
    """(series, share symbols, prior sign) for every mapped share CFD, for the cross-sectional
    equity book to consume as a conditioner or ranking axis. Nothing here is a cell or a trial."""
    from research import universe_policy
    rows: list[dict[str, Any]] = []
    for src in sources:
        for series in src.signal_series:
            shares = {sym: int(sgn) for sym, sgn in sorted(src.instruments_for(series).items())
                      if universe_policy.is_equity(sym)}
            if shares:
                rows.append({"source": src.id, "series": series,
                             "lake_file": lake_file(src, series), "columns": ["surprise_z",
                                                                               "pace"],
                             "shares": shares, "prior_sign_basis": "declared prior, untested",
                             "dead": is_dead(src), "terms": src.terms,
                             "usable": not is_dead(src) and src.terms == "confirmed"})
    return {"use": "equity_handoff", "producer": "desks/mt5/research/alt_proxies.py",
            "consumer": ("the cross-sectional equity book "
                         "(universe_policy.CROSS_SECTIONAL_FAMILIES)"),
            "rule": ("share CFDs never mint as alt-proxy direct or conditioned cells (two-lane "
                     "order, asset class from universe_policy). Each row is a PIT lake series "
                     "(data/lake/series/<lake_file>.csv) and the share CFDs it bears on with the "
                     "declared prior sign; the equity book decides and charges any test"),
            "rows": rows}


def gain_tests(paths: Paths, points_by_source: dict[str, dict[str, list[dict[str, Any]]]],
               ) -> dict[str, dict[str, Any]]:
    """Every (source, signal series, mapped instrument) cell, tested once, charged together.

    Only instruments the two-lane order lets this family mint on are tested (share CFDs go to
    the equity hand-off), and a DEAD source is never tested: its conditioner can never fire."""
    from libs.research.release_gain import release_gain
    cells: list[tuple[str, str, str]] = []
    for sid, per in points_by_source.items():
        src = BY_ID[sid]
        if is_dead(src):
            continue
        for series in src.signal_series:
            if per.get(series):
                cells.extend((sid, series, sym) for sym in src.instruments_for(series)
                             if may_mint(sym))
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
        if is_dead(src) or not may_mint(sym):
            continue
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
                                               "horizon_bars", "min_detectable_ic", "why")},
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


def _parent_signal_returns(paths: Paths, par: dict[str, Any]) -> Any:
    """(bar index, parent signal bar positions, side-signed forward log returns) for a certified
    parent, replayed through the desk's one call shape (`mt5desk.family_call.signals`) on this
    box's H1 bars -- or a string naming why it could not be replayed (the child is then
    UNMEASURED and not donated)."""
    import numpy as np
    import pandas as pd
    sym = str(par.get("symbol") or "")
    path = paths.universe / f"{sym}_H1.parquet"
    if not path.exists():
        return f"no {sym}_H1 bars on this box"
    try:
        from mt5desk.executables import resolve_family
        from mt5desk.family_call import signals as family_signals
        fn = resolve_family(str(par.get("family") or ""))
        if fn is None:
            return f"no code on this tree answers to family {par.get('family')!r}"
        bars = pd.read_parquet(path)
        bars.index = pd.DatetimeIndex(pd.to_datetime(bars.index, utc=True, errors="coerce"))
        bars = bars[bars.index.notna()].sort_index()
        params = dict(par.get("params") or {})
        if par.get("selector") and "session" not in params:
            params["session"] = str(par["selector"])
        side = -1 if str(par.get("side") or "").strip().upper() in {"SHORT", "-1"} else 1
        sigs = list(family_signals(fn, bars, side=side, params=params))
    except Exception as exc:
        return f"parent replay raised {type(exc).__name__}: {str(exc)[:100]}"
    idx = pd.DatetimeIndex(bars.index)
    close = bars["close"].to_numpy(dtype=float)
    pos = idx.get_indexer(pd.DatetimeIndex([pd.Timestamp(s.time) for s in sigs]
                                           ).tz_convert("UTC")) if sigs else np.array([], int)
    sides = np.asarray([int(s.side) for s in sigs], dtype=float)
    keep = (pos >= 0) & (pos + CHILD_HORIZON_BARS < close.size)
    pos, sides = pos[keep], sides[keep]
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = sides * np.log(close[pos + CHILD_HORIZON_BARS] / close[pos])
    return idx, pos, ret


def _regime_mask(paths: Paths, src: Source, series: str, op: str, idx: Any) -> Any:
    """The child's regime on every bar, exactly as `cell_modifiers._alt_filter` applies it."""
    from mt5desk import cell_modifiers as cm
    s = cm._alt_series(lake_file(src, series), "pace", root=paths.series)
    if s is None or len(s) == 0:
        return None
    known = s.reindex(s.index.union(idx)).ffill().reindex(idx)
    return cm.ALT_OPS[op](known.astype(float), 0.0).to_numpy(dtype=bool)


def indirect_cells(paths: Paths, points_by_source: dict[str, dict[str, list[dict[str, Any]]]],
                   state: dict[str, Any], now: datetime,
                   limit: int = INDIRECT_PER_PASS,
                   replay: Callable[[Paths, dict[str, Any]], Any] | None = None,
                   ) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]]]:
    """Certified parents on each mapped instrument, conditioned on the series' pace sign.

    Two children per (parent, series): pace > 0 and pace < 0 -- the two halves of one split, so
    neither is chosen after seeing which paid. Only series with live-yield points (not a fixture,
    at least 24 released points) mint; a rotating cursor spreads the per-pass share so every
    pair is reached.

    THE PLACEBO-CONDITIONED GATE. A child is donated only when the parent's signals inside its
    regime beat the same signals inside random regimes of the same duty cycle
    (`release_gain.regime_placebo`, circular shifts of the regime mask), Bonferroni-charged over
    every child tested this pass. A child whose parent cannot be replayed here, or whose regime
    holds too few signals, is UNMEASURED and not donated.

    Returns (passing candidates, pairs owed to later passes, one gate row per minted child)."""
    parents = _parents(paths)
    pairs: list[tuple[str, str, dict[str, Any]]] = []
    for sid, per in sorted(points_by_source.items()):
        src = BY_ID[sid]
        if is_dead(src):
            continue
        for series in src.signal_series:
            pts = [p for p in per.get(series, []) if p.get("pace") is not None]
            if len(pts) < 24:
                continue
            for sym in src.instruments_for(series):
                for par in parents.get(sym, [])[:PARENTS_PER_SYMBOL]:
                    if may_mint(sym, str(par.get("family") or "")):
                        pairs.append((sid, series, par))
    if not pairs:
        return [], 0, []
    start = int(state.get("indirect_cursor") or 0) % len(pairs)
    take = (pairs[start:] + pairs[:start])[: max(0, limit // 2)]
    state["indirect_cursor"] = (start + len(take)) % len(pairs)
    out: list[dict[str, Any]] = []
    minted: list[tuple[dict[str, Any], dict[str, Any], Source, str, str]] = []
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
            minted.append((out[-1], par, src, series, op))
    passed, gates = _gate_children(paths, minted, replay or _parent_signal_returns)
    return passed, max(0, len(pairs) - len(take)), gates


def _gate_children(paths: Paths,
                   minted: list[tuple[dict[str, Any], dict[str, Any], Source, str, str]],
                   replay: Callable[[Paths, dict[str, Any]], Any],
                   ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from libs.research.release_gain import regime_placebo
    replays: dict[str, Any] = {}
    inputs: list[tuple[dict[str, Any], Any]] = []
    for cand, par, src, series, op in minted:
        name = str(par.get("name") or cand["parent"])
        if name not in replays:
            replays[name] = replay(paths, par)
        got = replays[name]
        if isinstance(got, str):
            inputs.append((cand, got))
            continue
        idx, pos, ret = got
        mask = _regime_mask(paths, src, series, op, idx)
        inputs.append((cand, "no conditioning series in the lake on this box" if mask is None
                       else (pos, ret, mask)))
    n_trials = max(1, sum(1 for _c, x in inputs if not isinstance(x, str)))
    passed: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    for cand, x in inputs:
        if isinstance(x, str):
            res: dict[str, Any] = {"verdict": UNMEASURED, "why": x}
        else:
            seed = int(hashlib.sha256(cand["cell"].encode()).hexdigest()[:8], 16)
            res = regime_placebo(x[0], x[1], x[2], n_trials=n_trials, seed=seed)
        gates.append({"cell": cand["cell"], "parent": cand["parent"], "family": cand["family"],
                      **res})
        if res.get("verdict") == "PASS":
            cand["evidence"] = {k: res.get(k) for k in (
                "n_in", "n_signals", "duty_cycle", "mean_in", "placebo_mean", "placebo_p95",
                "p_placebo", "p_charged", "n_trials", "n_masks", "why")}
            passed.append(cand)
    return passed, gates


def _donate(paths: Paths, source: str, cands: list[dict[str, Any]], tests_run: int,
            by_family: dict[str, int], now: datetime) -> dict[str, Any]:
    """Donate the passing cells, and CHARGE EVERY TESTED CELL EITHER WAY.

    A discovery file carries `tests_run` for the whole pass (passes and fails), and
    `experiment_ledger` counts it. A pass with nothing to donate -- or whose donation the door
    turned away -- writes no discovery file, so its trials would vanish from the lifetime count;
    those go to the side ledger `paths.null_trials` instead. Exactly one of the two carries a
    pass's trials, so nothing is counted twice."""
    res: dict[str, Any] = {"donated": 0, "path": None}
    if cands:
        try:
            from research import proposer_common as pc
            path = pc.donate(source, cands, max(1, tests_run))
            res = {**pc.donation_counts(), "path": str(path) if path else None}
        except Exception as exc:
            res = {"donated": 0, "path": None,
                   "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
    if tests_run > 0 and not res.get("path"):
        row = {"at": now.isoformat(timespec="seconds"), "source": source,
               "tests_run": int(tests_run),
               "by_family": {k: int(v) for k, v in sorted(by_family.items()) if v},
               "why": "tested cells charged; no discovery file carried them this pass"}
        try:
            paths.null_trials.parent.mkdir(parents=True, exist_ok=True)
            with paths.null_trials.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            res["null_trials_charged"] = int(tests_run)
        except OSError as exc:
            res["null_trials_error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    return res


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
    if src.terms != "confirmed":
        rec.update({"status": status_of(src), "requests": 0,
                    "why": (f"terms {src.terms}: not fetched until a human confirms the "
                            f"licence ({TERMS.get(src.id, ('', 'unknown'))[1]})"),
                    "store_rows": len(store)})
        return rec
    if src.parse is None:                  # a local read of a series another organ fetches
        obs = src.reader(paths) if src.reader is not None else []
        rec.update({"requests": 0, "parsed": len(obs),
                    "why": f"read locally ({src.url})" if obs else
                    f"{src.url} absent or empty here: UNMEASURED"})
        rec["merge"] = merge_vintages(store, src, obs, now)
        _atomic(store_p, store)
        rec["store_rows"] = len(store)
        return rec
    blocked = (rec["status"].startswith(("BLOCKED_ON_KEY", "UNCONFIGURED"))
               and fixtures is None)
    if blocked:
        rec["why"] = (f"{src.key_env} is not set: a named state, never a dead endpoint"
                      if rec["status"].startswith("BLOCKED_ON_KEY") else
                      f"{rec['status']}: no request is built on a placeholder code")
        rec["store_rows"] = len(store)
        return rec
    sst = state.setdefault("sources", {}).setdefault(src.id, {})
    if src.id == "gdelt_events_country":
        rec.update(collect_gdelt(paths, src, sst, store, now, fetch=fetch, fixtures=fixtures,
                                 deadline=deadline, getter=getter))
        _atomic(store_p, store)
        rec["store_rows"] = len(store)
        return rec
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
    for k in ("backfill_to_next", "full_done_next"):
        if k in sst:
            nxt = sst.pop(k)
            if not errors and fixtures is None and fetch:
                sst[k[: -len("_next")]] = nxt
    rec.update({"requests": len(reqs), "fetched": fetched, "parsed": parsed,
                "errors": errors[:6], "store_rows": len(store)})
    if not parsed and not errors:
        rec["why"] = "nothing parsed this pass (no fetch, or the page carried no rows)"
    _atomic(store_p, store)
    return rec


def collect_gdelt(paths: Paths, src: Source, sst: dict[str, Any], store: dict[str, Any],
                  now: datetime, *, fetch: bool, fixtures: Path | None, deadline: float,
                  getter: Callable[[str], tuple[bytes, str]] = http_get) -> dict[str, Any]:
    """GDELT's own loop: read slots, fold them into their day, publish the days that closed.

    A 404 is a slot GDELT does not have (read, empty); any other error stops that direction for
    this pass so its cursor never skips an unread slot. With fixtures, the fixture files are the
    slots (`gdelt_events_country[.N].csv`) and no cursor moves."""
    acc: dict[str, Any] = sst.setdefault("acc", {})
    errors: list[str] = []
    fetched = parsed = 0
    if fixtures is not None:
        for fp in sorted(fixtures.glob(f"{src.id}*.csv")):
            obs = parse_gdelt_events(fp.read_bytes(), Ctx(fetched_at=now))
            parsed += len(obs)
            for day in sorted({o.period for o in obs}):
                for k in range(96):                      # a fixture file stands for its day
                    slot = f"{day:%Y%m%d}{k // 4:02d}{(k % 4) * 15:02d}00"
                    gdelt_accumulate(acc, slot, [o for o in obs if o.period == day]
                                     if k == 0 else [])
        reqs: list[Request] = []
    else:
        reqs = requests_for(src, now, sst)
    stopped: set[str] = set()
    for req in reqs if fetch else []:
        direction, _, slot = req.ctx.part.partition(":")
        if direction in stopped:
            continue
        if time.monotonic() > deadline:
            errors.append("budget reached: the remaining slots are owed to the next pass")
            break
        try:
            body, ctype = getter(req.url)
            fetched += 1
            vault(paths, src, body, req.url, ctype, now)
            obs2: list[Obs] | None = parse_gdelt_events(body, req.ctx)
            parsed += len(obs2 or [])
        except Exception as exc:
            try:
                if getattr(exc, "code", None) != 404:
                    errors.append(f"{slot}: {type(exc).__name__}: {str(exc)[:100]}")
                    stopped.add(direction)
                    continue
                obs2 = None
            finally:
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
        gdelt_accumulate(acc, slot, obs2)
        if direction == "fwd":
            sst["fwd"] = (_slot_time(slot) + timedelta(minutes=15)).isoformat()
        else:
            sst["back"] = (_slot_time(slot) - timedelta(minutes=15)).isoformat()
    done, dropped = gdelt_complete_days(acc)
    m = merge_vintages(store, src, done, now)
    return {"requests": len(reqs), "fetched": fetched, "parsed": parsed, "merge": m,
            "days_published": sorted({o.period.isoformat() for o in done}),
            "days_dropped_for_gaps": dropped, "days_open": len(acc), "errors": errors[:6]}


# ============================================================================ agreement
def _vals(per: dict[str, list[dict[str, Any]]] | None, series: str) -> dict[date, float]:
    return {date.fromisoformat(p["d"]): float(p["value"]) for p in (per or {}).get(series, [])
            if p.get("value") is not None}


def _monthly_mom(daily: dict[date, float], *, index_base: float = 0.0) -> dict[Any, float]:
    """Month mean, then month-on-month % change of (index_base + mean), keyed (year, month)."""
    by: dict[tuple[int, int], list[float]] = {}
    for d, v in daily.items():
        by.setdefault((d.year, d.month), []).append(index_base + v)
    months = sorted(by)
    means = {k: sum(v) / len(v) for k, v in by.items()}
    out: dict[Any, float] = {}
    for a, b in itertools.pairwise(months):
        if (b[0] * 12 + b[1]) - (a[0] * 12 + a[1]) == 1 and means[a] > 0:
            out[b] = (means[b] / means[a] - 1.0) * 100.0
    return out


def _weekly_change(daily: dict[Any, float], anchor_weekday: int = 6) -> dict[Any, float]:
    """NON-OVERLAPPING 7-day changes: one per week, on `anchor_weekday` (Sunday, the day the
    Opportunity Insights weekly rows carry). Keys are dates or (date, country) pairs. Overlapping
    daily 7-day differences are one observation counted seven times."""
    out: dict[Any, float] = {}
    for k, v in daily.items():
        d, rest = (k[0], k[1:]) if isinstance(k, tuple) else (k, ())
        prev = (d - timedelta(days=7), *rest) if rest else d - timedelta(days=7)
        if d.weekday() == anchor_weekday and prev in daily:
            out[k] = v - daily[prev]
    return out


#: Agreement is reported per regime: the pandemic swing (2020) makes any two activity series
#: co-move in levels, so a pooled number is mostly COVID. 2021+ is the regime that trades now.
AGREEMENT_REGIMES: tuple[tuple[str, date | None, date | None], ...] = (
    ("all", None, None), ("pre_2021", None, date(2021, 1, 1)),
    ("2021_plus", date(2021, 1, 1), None))


def _key_day(k: Any) -> date:
    if isinstance(k, date):
        return k
    if isinstance(k, tuple) and k and isinstance(k[0], date):
        return k[0]
    return date(int(k[0]), int(k[1]), 1)                      # (year, month)


def _by_regime(a: dict[Any, float], b: dict[Any, float], min_n: int) -> dict[str, Any]:
    from libs.research.event_factors import agreement
    out: dict[str, Any] = {}
    for name, lo, hi in AGREEMENT_REGIMES:
        def keep(k: Any, lo: date | None = lo, hi: date | None = hi) -> bool:
            d = _key_day(k)
            return (lo is None or d >= lo) and (hi is None or d < hi)
        out[name] = agreement({k: v for k, v in a.items() if keep(k)},
                              {k: v for k, v in b.items() if keep(k)}, min_n=min_n)
    return out


#: D19, each paid class against the paid original's PUBLIC outputs. A number appears here only if
#: it was computed from data this box fetched; every other entry is UNMEASURED with its reason.
PAID_ORIGINAL_AGREEMENT: dict[str, dict[str, Any]] = {
    "news_analytics": {
        "paid_original": "RavenPack", "substitutes": ["gdelt_events_country",
                                                      "wiki_asia_attention"],
        "public_outputs": ("academic papers quote summary statistics of RavenPack sentiment "
                           "(ESS/relevance distributions, event counts), never a daily series"),
        "verdict": UNMEASURED,
        "why": ("no public RavenPack series exists to align on the same keys, and the GDELT host "
                "answered 403 to the authoring box, so there is no GDELT panel to compare "
                "either")},
    "card_panels": {
        "paid_original": "Bank of America card data / Second Measure / Earnest",
        "substitutes": ["us_oi_card_spend", "kr_bok_card_spend", "jp_meti_retail",
                        "cn_nbs_retail", "in_npci_upi", "tr_bkm_card", "br_cielo_icva",
                        "mx_antad_sss", "za_beti"],
        "public_outputs": ("BofA Institute 'Consumer Checkpoint' monthly releases print card "
                           "spending per household YoY/MoM in prose and charts"),
        "verdict": UNMEASURED,
        "why": ("the BofA Institute page offers no downloadable series (checked 2026-09-30) and "
                "its host is not reachable through this box's proxy; transcribing ~24 monthly "
                "figures from release prose was not done, so no number is claimed. The only "
                "measured card comparison is OI vs Google mobility (substitute vs substitute)")},
    "foot_traffic": {
        "paid_original": "Placer.ai / SafeGraph",
        "substitutes": ["us_oi_google_mobility", "kr_kobis_box_office", "kr_seoul_subway",
                        "cn_maoyan_box_office", "cn_baidu_migration"],
        "public_outputs": ("Placer.ai publishes mall and retail visit indexes in blog posts "
                           "and monthly reports (charts, some tables)"),
        "verdict": UNMEASURED,
        "why": ("no Placer.ai index was fetched: its host is not reachable through this box's "
                "proxy and no machine-readable history is published; SafeGraph patterns are "
                "licensed, not public")},
    "satellite": {
        "paid_original": "Orbital Insight / SpaceKnow",
        "substitutes": ["kr_busan_port", "sg_port_throughput", "cn_mot_port_weekly",
                        "imf_portwatch_ports", "cn_firms_industrial"],
        "public_outputs": ("SpaceKnow's China Satellite Manufacturing Index was published in "
                           "press releases (2016-2019); Orbital Insight publishes no index"),
        "verdict": UNMEASURED,
        "why": ("no SpaceKnow SMI history was fetched (not reachable from this box, and "
                "discontinued as a public print), and none of the port substitutes returned data "
                "here to compare")},
}


def _nlp_panel(paths: Paths, iso: str, column: str) -> dict[date, float]:
    fp = paths.nlp_series / f"nlp_events_{iso}.parquet"
    if not fp.exists():
        return {}
    try:
        import pandas as pd
        df = pd.read_parquet(fp)
    except Exception:
        return {}
    if column not in df.columns or "period" not in df.columns:
        return {}
    out: dict[date, float] = {}
    for d, v in zip(df["period"], df[column], strict=True):
        with contextlib.suppress(ValueError, TypeError):
            if v == v:
                out[date.fromisoformat(str(d)[:10])] = float(v)
    return out


def substitute_agreement(paths: Paths, pts: dict[str, dict[str, list[dict[str, Any]]]]
                         ) -> dict[str, Any]:
    """Each free substitute against an OVERLAPPING free series on the same keys, ON CHANGES and
    split by regime (all / pre_2021 / 2021_plus). Levels are reported only as context beside the
    changes, never alone: two activity series that both fell in 2020 agree in levels whatever
    they measure. `paid_original_agreement` is the D19 block (the paid originals' public
    outputs). `event_factors.agreement` is the one metric."""
    oi, gm = pts.get("us_oi_card_spend"), pts.get("us_oi_google_mobility")
    out: dict[str, Any] = {}
    # 1. card panel vs the official receipts survey, monthly MoM (both seasonally adjusted).
    card_m = _monthly_mom(_vals(oi, "spend_all"), index_base=1.0)
    official = _monthly_mom(_vals(pts.get("us_census_marts_ex_autos"), "sales_ex_autos_gas"))
    out["oi_card_vs_census_marts_mom"] = {
        "what": "OI/Affinity spend_all month-mean MoM vs Census MARTS ex-autos-and-gas MoM",
        "basis": "changes",
        **({"changes": _by_regime(card_m, official, 12)} if card_m and official else {
            "verdict": UNMEASURED,
            "why": ("no Census MARTS vintages on this box (api.census.gov unreachable from the "
                    "authoring container)" if not official else "no OI card-spend points")})}
    # 2. card panel vs foot traffic (Google mobility): weekly changes, levels as context only.
    spend = _vals(oi, "spend_retail_no_grocery")
    visits = _vals(gm, "retail_and_recreation")
    out["oi_card_vs_google_mobility"] = {
        "what": ("OI spend_retail_no_grocery vs Google retail_and_recreation visits: "
                 "non-overlapping Sunday-to-Sunday changes on the same weeks"),
        "basis": "changes",
        **({"changes": _by_regime(_weekly_change(spend), _weekly_change(visits), 30),
            "levels_context_only": _by_regime(spend, visits, 30)} if spend and visits else {
            "verdict": UNMEASURED, "why": "one of the two archives is not held"})}
    # 3. GDELT vs this desk's own event tagger on the same country-days, weekly changes.
    g = pts.get("gdelt_events_country") or {}
    ours_c: dict[Any, float] = {}
    theirs_c: dict[Any, float] = {}
    theirs_t: dict[Any, float] = {}
    for iso in sorted(set(GDELT_COUNTRIES.values())):
        for d, v in _nlp_panel(paths, iso, "geopolitical_risk_intensity").items():
            ours_c[(d, iso)] = v
        for d, v in _vals(g, f"{iso}_conflict_share").items():
            theirs_c[(d, iso)] = v
        for d, v in _vals(g, f"{iso}_tone").items():
            theirs_t[(d, iso)] = -v
    for name, theirs in (("gdelt_conflict_share_vs_tagger_geopolitical_risk", theirs_c),
                         ("gdelt_negative_tone_vs_tagger_geopolitical_risk", theirs_t)):
        out[name] = {"what": ("pooled country-weeks where both GDELT and nlp_events have a "
                              "value: non-overlapping 7-day changes"),
                     "basis": "changes",
                     **({"changes": _by_regime(_weekly_change(ours_c), _weekly_change(theirs),
                                               30),
                         "levels_context_only": _by_regime(ours_c, theirs, 30)}
                        if ours_c and theirs else {
                         "verdict": UNMEASURED,
                         "why": ("no GDELT days on this box (data.gdeltproject.org answered 403 "
                                 "to the authoring container)" if not theirs else
                                 "no nlp_events_<CC>.parquet tagger panel on this box")})}
    out["paid_original_agreement"] = PAID_ORIGINAL_AGREEMENT
    return out


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
        if src.terms != "confirmed":
            records[src.id] = {**rec, "series": {}}     # a stored history is not read either
            continue
        store = _read_json(paths.obs_dir / f"{src.id}.json", {})
        pts = build_points(src, store) if store else {}
        if pts:
            points_by_source[src.id] = pts
            if not dry_run:
                _atomic(paths.axes / f"alt_{src.id}.json", axis_doc(src, pts, now))
                rec["lake_series"] = write_lake_series(paths, src, pts)
        rec["series"] = {k: len(v) for k, v in sorted(pts.items())}
        revs = revision_points(src, store) if store else {}
        rec["revision_vintages"] = {k: len(v) for k, v in sorted(revs.items())}
        records[src.id] = rec
    gains = gain_tests(paths, points_by_source) if points_by_source else {}
    live = dict(points_by_source) if fixtures is None else {}
    direct = direct_cells(gains, now) if fixtures is None else []
    indirect, owed, child_gates = indirect_cells(paths, live, state, now)
    tested = ("PASS", "FAIL", "UNDERPOWERED")
    n_children_tested = sum(1 for g in child_gates if g.get("verdict") in tested)
    n_tested = sum(1 for g in gains.values() if g.get("verdict") in tested)
    child_fams: dict[str, int] = {}
    for g in child_gates:
        if g.get("verdict") in tested:
            child_fams[str(g.get("family"))] = child_fams.get(str(g.get("family")), 0) + 1
    donations: dict[str, Any] = {"direct": {"donated": 0}, "indirect": {"donated": 0}}
    if donate and not dry_run:
        donations["direct"] = _donate(paths, SOURCE, direct, n_tested,
                                      {DIRECT_FAMILY: n_tested}, now)
        donations["indirect"] = _donate(paths, INDIRECT_SOURCE, indirect, n_children_tested,
                                        child_fams, now)
    intel = allocation_intel(points_by_source, gains, now)
    handoff = equity_handoff()
    from libs.research.release_gain import TARGET_IC
    report = {
        "at": now.isoformat(timespec="seconds"), "organ": "alt_proxies",
        "mode": "fixtures" if fixtures is not None else ("fetch" if fetch else "no_fetch"),
        "sources": records,
        "gain_tests": gains,
        "n_cells_tested": n_tested, "n_cells_total": len(gains),
        "power": {"target_ic": TARGET_IC,
                  "n_underpowered": sum(1 for g in gains.values()
                                        if g.get("verdict") == "UNDERPOWERED"),
                  "rule": ("each gain row carries min_detectable_ic (80% power at its n and "
                           "Bonferroni charge); a miss above target_ic is UNDERPOWERED, not FAIL")},
        "equity_handoff": {"path": str(paths.equity_handoff), "n_rows": len(handoff["rows"]),
                           "rule": handoff["rule"]},
        "dead_sources": sorted(s.id for s in SOURCES if is_dead(s)),
        "blocked_on_terms": sorted(s.id for s in SOURCES if s.terms != "confirmed"),
        "blocked_substituted": {sid: list(SUBSTITUTED_BY[sid]) for sid in sorted(SUBSTITUTED_BY)},
        "blocked_unsubstituted": {sid: NO_SUBSTITUTE[sid] for sid in sorted(NO_SUBSTITUTE)},
        "direct_cells": {"n": len(direct), "donation": donations["direct"],
                         "rule": ("an exogenous_conditioner cell is donated only after its gain "
                                  "test PASSED on this box; every tested cell is charged")},
        "indirect_cells": {"n": len(indirect), "owed_to_later_passes": owed,
                           "n_minted": len(child_gates), "n_tested": n_children_tested,
                           "gates": child_gates[:48],
                           "donation": donations["indirect"],
                           "rule": ("certified parents conditioned on pace>0 / pace<0 via "
                                    "params.conditioner, applied by mt5desk.cell_modifiers; a "
                                    "child is donated only when its in-regime parent return "
                                    "beats circularly shifted regimes of the same duty cycle, "
                                    "Bonferroni over every child tested")},
        "allocation_intel": {"path": str(paths.allocation_intel),
                             "n_instruments": len(intel["instruments"])},
        "substitute_agreement": substitute_agreement(paths, points_by_source),
        "keys": {s.key_env: bool(os.environ.get(s.key_env)) for s in SOURCES if s.key_env},
        "live_yield": ("UNMEASURED until the trading box runs this leg: the fetchers were built "
                       "against fixtures because the authoring container cannot reach the hosts"),
    }
    state["last_run"] = report["at"]
    if not dry_run:
        _atomic(paths.state, state)
        _atomic(paths.allocation_intel, intel)
        _atomic(paths.equity_handoff, handoff)
        _atomic(paths.report, report)
        from libs.research import asia_alt_digest
        asia_alt_digest.publish(SOURCE, digest_section(report), paths.digest)
    return report


def digest_section(report: dict[str, Any]) -> dict[str, Any]:
    """This organ's section of the committed digest: points per source, gain verdicts per cell,
    and what the direct and indirect gates let through."""
    from libs.research import asia_alt_digest
    recs = report.get("sources") or {}
    pts = {sid: sum((r.get("series") or {}).values()) for sid, r in recs.items()}
    measured = [sid for sid, n in pts.items() if n > 0]
    live = report.get("mode") == "fetch" and any(
        int(r.get("parsed") or 0) > 0 and not str(r.get("status") or "").startswith("DEAD")
        for r in recs.values())                          # a DEAD archive is never "live"
    ind = report.get("indirect_cells") or {}
    return asia_alt_digest.section(
        at=str(report.get("at")),
        status=("LIVE" if live else "FIXTURES" if report.get("mode") == "fixtures"
                else "UNMEASURED_LIVE_YIELD"),
        rows=sum(pts.values()), measured=measured,
        unmeasured=[sid for sid in recs if sid not in measured],
        gain={k: (g or {}).get("verdict", UNMEASURED)
              for k, g in (report.get("gain_tests") or {}).items()},
        source_status={sid: str(r.get("status")) for sid, r in sorted(recs.items())},
        direct_cells=int((report.get("direct_cells") or {}).get("n") or 0),
        indirect_cells={"minted": int(ind.get("n_minted") or 0),
                        "tested": int(ind.get("n_tested") or 0),
                        "passed": int(ind.get("n") or 0)},
        power={"target_ic": (report.get("power") or {}).get("target_ic"),
               "min_detectable_ic": {k: (g or {}).get("min_detectable_ic") for k, g in
                                     sorted((report.get("gain_tests") or {}).items())[:40]}})


def _cursor(s: Source) -> str:
    if s.id == "cn_firms_industrial":
        return "firms_backfill_to (10 days/cluster/pass, archive product)"
    if s.id.startswith("imf_portwatch"):
        return "resultOffset paging; 800-day window"
    if s.id == "gdelt_events_country":
        return (f"fwd/back 15-minute slot cursors ({GDELT_FWD_PER_PASS}+{GDELT_BACK_PER_PASS} "
                f"slots/pass, {GDELT_BACK_DEPTH_D}d deep); open days held in state.acc")
    if s.id in DATED_SOURCES:
        r, lag, b = DATED_SOURCES[s.id]
        return (f"last {r} days (lag {lag}d) re-read each pass + backfill_to walking back "
                f"{b} days/pass, {DATED_BACKFILL_DEPTH_D}d deep")
    return "vintage store keyed series|period (append-only)"


def roster_rows(sources: Iterable[Source] = SOURCES,
                environ: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """One roster row per source, for the mining roster (the same metadata the cells carry)."""
    rows = []
    for s in sources:
        uses = ["direct_cells", "indirect_cells", "allocation_intel"]
        rows.append({"id": s.id, "name": s.name,
                     "url": s.url.split("?")[0].replace("{key}", "<key>"),
                     "region": s.region, "language": s.language, "cadence": s.cadence,
                     "auth": f"free_key:{s.key_env}" if s.key_env else "none",
                     "licence": s.licence,
                     "cursor": _cursor(s),
                     "pit": ("available_time = page publication stamp else release-calendar rule "
                             "(late-biased); first_seen_at = vault fetch instant"),
                     "uses": uses, "consumer": "desks/mt5/research/alt_proxies.py",
                     "status": status_of(s, environ), "terms": s.terms, **_meta(s)})
        if s.id in SUBSTITUTED_BY:
            rows[-1]["substituted_by"] = list(SUBSTITUTED_BY[s.id])
        if s.substitutes_for:
            rows[-1].update({"substitutes_for": s.substitutes_for, "fetcher": "owned",
                             "owner": "asia_gap_thread"})
    return rows


def substitute_roster_rows(environ: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Roster rows for the paid-substitute sources only (the repo roster file's content)."""
    return roster_rows(SUBSTITUTE_SOURCES, environ)


_CADENCE_MIN = {"daily": 1440, "event": 1440, "weekly": 10080, "10-daily": 14400,
                "monthly": 43200}
ROSTER_HEADER = (
    "# Paid-dataset substitutes (RavenPack / card-spend / foot-traffic / satellite panels),\n"
    "# built by the asia_gap_thread in desks/mt5/research/alt_proxies.py, which FETCHES\n"
    "# every row itself (fetcher: owned). Generated from alt_proxies.roster_file_rows()\n"
    "# (python desks/mt5/research/alt_proxies.py --write-rosters); regenerate rather than\n"
    "# hand-edit. status is as declared with no keys set; live yield is UNMEASURED except\n"
    "# where the status says otherwise. A BLOCKED+SUBSTITUTE:<ids> row is never fetched: its\n"
    "# terms block it and the named confirmed rows stand in for it.\n")


def roster_file_rows() -> list[dict[str, Any]]:
    """The committed roster file's rows: substitute_roster_rows() with the status taken as
    declared (no keys), the auth in the roster's none|key form and the cadence in minutes."""
    out = []
    for r in substitute_roster_rows(environ={}):
        row: dict[str, Any] = {}
        for k, v in r.items():
            if k == "auth":
                key = str(v).removeprefix("free_key:") if v != "none" else ""
                row["auth"] = "key" if key else "none"
                if key:
                    row["auth_env"] = key
            elif k == "participant_structure":
                row[k] = list(v)
            else:
                row[k] = v
        row["cadence_minutes"] = _CADENCE_MIN.get(str(r["cadence"]), 1440)
        row["kind"] = "mechanics"
        out.append(row)
    return out


def engine_rows() -> dict[str, Any]:
    """Rows for the paid-substitute engine (#152), in the two shapes it reads: `rows`, the
    Asia-thread table it parses from data/paid_data_substitutes_*.json (class / paid / free /
    region / measure / frequency, found by header words), and `library_rows`, the shape of its
    free-source library (data/paid_substitute_library.json), ready to merge once #152 lands.
    Every blocked source is marked BLOCKED+SUBSTITUTE:<ids> or BLOCKED_ON_TERMS (unsubstituted)."""
    klass = {_CARD: "card", _FOOT: "foot traffic", _SAT: "satellite (port / AIS activity)",
             _NEWS: "news", _TRAVEL: "foot traffic (travel arrivals)", _GOLD: "gold premium"}
    blocked_class = {"jp_jnto_arrivals": _TRAVEL, "cn_sge_premium": _GOLD}
    rows: list[dict[str, str]] = []
    for sid in sorted({*SUBSTITUTED_BY, *NO_SUBSTITUTE}):
        src = BY_ID[sid]
        paid_cls = src.substitutes_for or blocked_class.get(sid, "")
        subs = SUBSTITUTED_BY.get(sid, ())
        rows.append({
            "class": klass.get(paid_cls, paid_cls),
            "paid": f"{src.name} [{sid}]",
            "free": "; ".join(f"{BY_ID[x].name} [{x}]" for x in subs),
            "region": src.region,
            "measure": src.signal_series[0] if src.signal_series else "",
            "frequency": src.cadence,
            "status": status_of(src, {}),
            "terms": src.terms,
            "blocked_because": TERMS.get(sid, ("", ""))[1],
            "unsubstituted_because": NO_SUBSTITUTE.get(sid, ""),
            "evidence": "; ".join(f"{x}: {TERMS_EVIDENCE[x]['terms_url']}" for x in subs
                                  if x in TERMS_EVIDENCE),
        })
    lib: list[dict[str, Any]] = []
    for x in sorted({x for v in SUBSTITUTED_BY.values() for x in v}):
        s = BY_ID[x]
        ev = TERMS_EVIDENCE.get(x, {})
        lib.append({
            "id": f"asia_{x}", "name": s.name,
            "publisher_type": "statistics_office_or_central_bank",
            "url": ev.get("terms_url") or s.url.split("?")[0],
            "endpoint": None if "{" in s.url else s.url,
            "classes": [{_CARD: "card_consumer", _FOOT: "foot_traffic", _SAT: "shipping_ais",
                         _TRAVEL: "foot_traffic", _GOLD: "commodities_physical"}.get(
                             s.substitutes_for, "macro")],
            "region": s.region, "frequency": s.cadence,
            "auth": "free_key" if s.key_env else "none", "auth_env": s.key_env or "",
            "languages": [s.language], "instruments": sorted(s.instruments),
            "participant_structure": s.participant_structure[0], "licence": s.licence,
            "terms": s.terms, "terms_quote": ev.get("terms_quote", ""),
            "consumer": "desks/mt5/research/alt_proxies.py", "owner": "asia_gap_thread",
            "substitutes_for_blocked": sorted(k for k, v in SUBSTITUTED_BY.items() if x in v),
        })
    return {"note": ("Asia gap thread: lawful substitutes for sources the terms gate blocks. "
                     "Generated by desks/mt5/research/alt_proxies.py --write-rosters; the "
                     "paid-substitute engine reads `rows` as an Asia-thread table. alt_proxies "
                     "fetches every substitute itself; nothing here is fetched twice."),
            "rows": rows, "library_rows": lib}


def write_rosters() -> list[Path]:
    """Regenerate the committed roster YAML and the engine rows file from the code."""
    import yaml  # type: ignore[import-untyped,unused-ignore]
    body = yaml.safe_dump({"sources": roster_file_rows()}, sort_keys=False, allow_unicode=True,
                          width=100)
    ROSTER_FILE.write_text(ROSTER_HEADER + body, "utf-8")
    ENGINE_ROWS_FILE.write_text(json.dumps(engine_rows(), indent=1, ensure_ascii=False) + "\n",
                                "utf-8")
    return [ROSTER_FILE, ENGINE_ROWS_FILE]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--budget-s", type=float, default=300.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--fixtures", type=Path, default=None)
    ap.add_argument("--no-donate", action="store_true")
    ap.add_argument("--write-rosters", action="store_true",
                    help="regenerate the committed roster YAML and engine rows, then exit")
    a = ap.parse_args(argv)
    if a.write_rosters:
        for fp in write_rosters():
            print(f"wrote {fp}")
        return 0
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
