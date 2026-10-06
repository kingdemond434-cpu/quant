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
boards, India's gold imports for the SGE premium, MoSPI's use-based IIP consumer goods on
data.gov.in (GODL) for NPCI UPI, Stats SA retail trade sales for BETI), and its status reads
BLOCKED+SUBSTITUTE:<ids>. NO_SUBSTITUTE is empty; SUBSTITUTE_SEARCH keeps how the last two closed.
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
    def sensor_dir(self) -> Path:
        """Per-source §2.5 sensor records (`sensor_records`), the newest points per series."""
        return self.desk / "data" / "alt_proxies" / "sensor"

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
    cells: dict[tuple[float, float], set[date]] = {}
    hits: list[tuple[date, tuple[float, float], str]] = []
    typed = False
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
        la, lo = _num(str(r.get("latitude") or "")), _num(str(r.get("longitude") or ""))
        if la is not None and lo is not None:
            cell = (round(la, 2), round(lo, 2))
            cells.setdefault(cell, set()).add(d)
            typed = typed or "type" in r
            hits.append((d, cell, str(r.get("type") or "").strip()))
    days = sorted(counts)
    if ctx.start is not None and ctx.end is not None:
        days = [ctx.start + timedelta(days=i) for i in range((ctx.end - ctx.start).days + 1)]
    # INDUSTRIAL vs TRANSIENT. A furnace, coke oven or flare burns at the same ~1 km cell day
    # after day; crop-residue and wild fires move. A detection is `persistent` when its 0.01-deg
    # cell is hot on >= 3 distinct days of this file. When the archive's `type` column is present
    # (0 vegetation fire, 2 other static land source), vegetation fires are counted apart.
    pers: dict[date, float] = {}
    veg: dict[date, float] = {}
    for d, cell, typ in hits:
        if len(cells[cell]) >= 3 and typ != "0":
            pers[d] = pers.get(d, 0.0) + 1.0
        if typ == "0":
            veg[d] = veg.get(d, 0.0) + 1.0
    part = ctx.part or "area"
    out: list[Obs] = []
    for d in days:
        out.append(Obs(f"{part}_count", d, counts.get(d, 0.0)))
        out.append(Obs(f"{part}_frp", d, round(frp.get(d, 0.0), 3)))
        out.append(Obs(f"{part}_persistent_count", d, pers.get(d, 0.0)))
        if typed:
            out.append(Obs(f"{part}_veg_count", d, veg.get(d, 0.0)))
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


#: PortWatch vessel-type and tonnage fields kept for the major Chinese ports (series suffix).
PORTWATCH_SEGMENTS = {"portcalls_container": "calls_container",
                      "portcalls_dry_bulk": "calls_dry_bulk", "portcalls_tanker": "calls_tanker",
                      "import": "import_t", "export": "export_t"}


def parse_portwatch_ports(body: bytes, ctx: Ctx) -> list[Obs]:
    """IMF PortWatch Daily_Ports_Data: port calls per port per day (AIS-derived). A China-wide
    page (`ctx.part` cn_page*) names its series `cn_<port>_portcalls`, and for the major ports
    adds the vessel-type split (container / dry bulk / tanker calls) and estimated import and
    export tonnes. Field names follow the Daily_Ports_Data layer; a field absent from the reply
    is simply not emitted (UNCONFIRMED against a live China-wide reply)."""
    cn = (ctx.part or "").startswith("cn_")
    out: list[Obs] = []
    for a in _arcgis_rows(body):
        d = _arcgis_date(a.get("date"))
        name = str(a.get("portname") or "")
        v = _num(str(a.get("portcalls") if a.get("portcalls") is not None else ""))
        if not (d and name and v is not None):
            continue
        slug = _slug(name)
        if not cn:
            out.append(Obs(f"{slug}_portcalls", d, v))
            continue
        out.append(Obs(f"cn_{slug}_portcalls", d, v))
        if slug in PORTWATCH_CN_MAJOR:
            for fld, suf in PORTWATCH_SEGMENTS.items():
                x = _num(str(a.get(fld) if a.get(fld) is not None else ""))
                if x is not None:
                    out.append(Obs(f"cn_{slug}_{suf}", d, x))
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
    ("ko_kospi", "ko.wikipedia", "코스피"),
    # The lawful substitute for the Baidu Index keyword basket (黄金 美元 失业 铜价 钢材 原油 汽油
    # 电动车 经济衰退 房价...): the zh.wikipedia article for each topic. Titles UNCONFIRMED from
    # the authoring box (zh.wikipedia unreachable); a missing article is reported, not fatal.
    ("zh_kw_gold", "zh.wikipedia", "金"), ("zh_kw_usd", "zh.wikipedia", "美元"),
    ("zh_kw_unemployment", "zh.wikipedia", "失业"), ("zh_kw_copper", "zh.wikipedia", "铜"),
    ("zh_kw_steel", "zh.wikipedia", "钢"), ("zh_kw_oil", "zh.wikipedia", "石油"),
    ("zh_kw_gasoline", "zh.wikipedia", "汽油"), ("zh_kw_ev", "zh.wikipedia", "电动汽车"),
    ("zh_kw_recession", "zh.wikipedia", "经济衰退"), ("zh_kw_property", "zh.wikipedia", "房地产"))
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
    (monthly) or YYYYMMDD; an ECOS error document (RESULT.CODE) parses to nothing. A table with a
    second dimension returns one row per ITEM_CODE2 per month; only the total (00) is kept."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = ((doc or {}).get("StatisticSearch") or {}).get("row") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        if str(r.get("ITEM_CODE2") or "00") != "00":
            continue                   # a second dimension's breakdown (은행계/비은행계): keep 합계
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


# ============================================================ PHYSICAL-ECONOMY EXHAUST (P4)
# Ports by port, freight by route, power by fuel, procurement by commodity basket, corporate
# activity by sector, thermal and NO2 by named facility, Korean search attention by topic. Every
# parser here emits named series only; nothing is aggregated across pages at parse time except
# what one document holds whole (one monthly port table, one release).
def _xlsx_sheets(body: bytes) -> list[list[list[str]]]:
    """A stdlib .xlsx reader: shared strings + every worksheet in order, as rows of cell text.
    Cached values only (formulas are never evaluated). A non-zip or a member larger than 64 MB
    uncompressed is nothing."""
    import xml.etree.ElementTree as ET
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
    except (zipfile.BadZipFile, ValueError):
        return []
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    if any(i.file_size > 64 * 1024 * 1024 for i in z.infolist()):
        return []
    names = z.namelist()
    shared: list[str] = []
    try:
        if "xl/sharedStrings.xml" in names:
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{m}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{m}t")))
        sheets = sorted((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                        key=lambda n: int(re.sub(r"\D", "", n.rsplit("/", 1)[1]) or 0))
        book: list[list[list[str]]] = []
        for sh in sheets:
            rows: list[list[str]] = []
            book.append(rows)
            for r in ET.fromstring(z.read(sh)).iter(f"{m}row"):
                cells: dict[int, str] = {}
                for c in r.findall(f"{m}c"):
                    letters = re.match(r"[A-Z]+", c.get("r") or "")
                    col = 0
                    for ch in letters.group(0) if letters else "":
                        col = col * 26 + (ord(ch) - 64)
                    col = col - 1 if col else len(cells)
                    v = c.find(f"{m}v")
                    t = c.get("t")
                    if t == "s" and v is not None and (v.text or "").isdigit():
                        k = int(v.text or 0)
                        text = shared[k] if k < len(shared) else ""
                    elif t == "inlineStr":
                        text = "".join(x.text or "" for x in c.iter(f"{m}t"))
                    else:
                        text = v.text or "" if v is not None else ""
                    cells[col] = text.strip()
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
    except (ET.ParseError, KeyError, ValueError):
        return []
    return book


#: MOT monthly port table names -> series slug. Only these ports are emitted; an unmapped row is
#: not guessed at. North/south and commodity membership are declared, not inferred.
CN_PORTS: dict[str, str] = {
    "全国": "national", "总计": "national", "全国合计": "national", "全国总计": "national",
    "沿海合计": "coastal",
    "内河合计": "inland", "上海": "shanghai", "宁波舟山": "ningbo_zhoushan",
    "宁波-舟山": "ningbo_zhoushan", "青岛": "qingdao", "天津": "tianjin", "大连": "dalian",
    "广州": "guangzhou", "深圳": "shenzhen", "日照": "rizhao", "唐山": "tangshan",
    "营口": "yingkou", "秦皇岛": "qinhuangdao", "烟台": "yantai", "连云港": "lianyungang",
    "厦门": "xiamen", "福州": "fuzhou", "泉州": "quanzhou", "湛江": "zhanjiang",
    "北部湾": "beibu_gulf", "黄骅": "huanghua", "锦州": "jinzhou", "丹东": "dandong",
    "威海": "weihai", "东莞": "dongguan", "珠海": "zhuhai", "苏州": "suzhou", "南通": "nantong"}
CN_NORTH_PORTS = frozenset({"dalian", "yingkou", "jinzhou", "dandong", "qinhuangdao", "tangshan",
                            "huanghua", "tianjin", "yantai", "weihai", "qingdao", "rizhao",
                            "lianyungang"})
CN_SOUTH_PORTS = frozenset({"shanghai", "ningbo_zhoushan", "xiamen", "fuzhou", "quanzhou",
                            "guangzhou", "shenzhen", "dongguan", "zhuhai", "zhanjiang",
                            "beibu_gulf"})
#: Dry-bulk (iron ore, coal) heavy ports: the commodity-port activity basket.
CN_COMMODITY_PORTS = frozenset({"tangshan", "rizhao", "qingdao", "tianjin", "dalian", "huanghua",
                                "qinhuangdao", "yingkou", "lianyungang"})


def _implied_yoy(rows: list[tuple[float, float]]) -> float | None:
    """Aggregate YoY of a basket from (level, yoy %) pairs: this year's sum over the implied
    prior-year sum (level / (1 + yoy/100)). Never an average of percentages."""
    cur = prev = 0.0
    for lvl, yoy in rows:
        if yoy <= -100.0:
            return None
        cur += lvl
        prev += lvl / (1.0 + yoy / 100.0)
    return (cur / prev - 1.0) * 100.0 if rows and prev > 0 else None


def parse_mot_port_monthly(body: bytes, ctx: Ctx) -> list[Obs]:
    """MOT monthly 港口货物、集装箱吞吐量 workbook (.xlsx). Format, as the MOT list describes the
    release: one sheet per measure, a title naming the year-month and the measure (货物 = cargo
    in 万吨; 集装箱 = containers in 万TEU), then one row per port: name, this month, this month's
    YoY %, year-to-date, YTD YoY %. Per mapped port: level and YoY; plus national throughput,
    container-port breadth (share of mapped coastal container ports with YoY > 0), commodity-
    port cargo YoY, north and south cargo YoY and their gap, and bulk-minus-container YoY."""
    blocks = [[r for r in sh if r] for sh in _xlsx_sheets(body)]
    got: dict[str, dict[str, tuple[float, float]]] = {"cargo": {}, "teu": {}}
    period: date | None = None
    for blk in blocks:
        head = " ".join(" ".join(r) for r in blk[:4])
        ym = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", head)
        if not ym or not 1 <= int(ym.group(2)) <= 12:
            continue
        p = _month_end(int(ym.group(1)), int(ym.group(2)))
        if period is not None and p != period:
            continue                                     # one month per workbook
        period = p
        kind = "teu" if re.search(r"集装箱|TEU|标箱", head, re.I) else "cargo"
        for r in blk:
            name = re.sub(r"[\s　]+", "", r[0] if r else "").removesuffix("港")
            slug = CN_PORTS.get(name)
            nums = [x for x in (_num(c) for c in r[1:]) if x is not None]
            if slug and len(nums) >= 2:
                got[kind].setdefault(slug, (nums[0], nums[1]))
    if period is None:
        return []
    out: list[Obs] = []
    unit = {"cargo": "cargo_10kt", "teu": "teu_10k"}
    for kind, ports in got.items():
        for slug, (lvl, yoy) in sorted(ports.items()):
            out.append(Obs(f"{slug}_{unit[kind]}", period, lvl))
            out.append(Obs(f"{slug}_{kind}_yoy", period, yoy))
    cargo, teu = got["cargo"], got["teu"]
    box = [yoy for s, (_l, yoy) in teu.items() if s in CN_NORTH_PORTS | CN_SOUTH_PORTS]
    if len(box) >= 5:
        out.append(Obs("container_port_breadth", period, sum(y > 0 for y in box) / len(box)))
    for name, members in (("commodity_ports", CN_COMMODITY_PORTS), ("north", CN_NORTH_PORTS),
                          ("south", CN_SOUTH_PORTS)):
        sel = [v for s, v in cargo.items() if s in members]
        if len(sel) >= 3 and (agg := _implied_yoy(sel)) is not None:
            out.append(Obs(f"{name}_cargo_yoy", period, round(agg, 4)))
    n, s_ = ([v for s, v in cargo.items() if s in grp] for grp in (CN_NORTH_PORTS, CN_SOUTH_PORTS))
    if len(n) >= 3 and len(s_) >= 3:
        a, b = _implied_yoy(n), _implied_yoy(s_)
        if a is not None and b is not None:
            out.append(Obs("north_minus_south_cargo_yoy", period, round(a - b, 4)))
    if "national" in cargo and "national" in teu:
        out.append(Obs("bulk_minus_container_yoy", period,
                       round(cargo["national"][1] - teu["national"][1], 4)))
    return out


_SSE_DATE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")
_SSE_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_SSE_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def parse_sse_routes(body: bytes, ctx: Ctx) -> list[Obs]:
    """Shanghai Shipping Exchange SCFI table as its page renders it (columns, verbatim from
    en.sse.net.cn/indices/scfinew.jsp: Description | Unit | Weighting | Previous Index | Current
    Index | Compare With Last Week; the period is the Friday printed beside it). One series per
    ROUTE, never one blended index: origin Shanghai x destination x unit is the series name.
    The previous-index column is the prior Friday's value as reprinted (a revision check)."""
    raw = body.decode("utf-8", errors="replace")
    dm = _SSE_DATE.search(_text(body))
    if not dm:
        return []
    try:
        cur = date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        return []
    out: list[Obs] = []
    for row in _SSE_ROW.findall(raw):
        cells = [_text(c.encode()) for c in _SSE_CELL.findall(row)]
        if len(cells) < 5:
            continue
        prev, now_v = _num(cells[3]), _num(cells[4])
        if now_v is None:
            continue
        desc = cells[0].lower()
        unit = re.sub(r"[^a-z]", "", cells[1].lower()).replace("usd", "usd_")
        if "comprehensive" in desc or "composite" in desc:
            name = "scfi_composite"
        else:
            dest = _slug(re.sub(r"\(.*?\)|service", "", desc))
            if not dest:
                continue
            name = f"shanghai__{dest}__{unit or 'index'}"
        out.append(Obs(name, cur, now_v))
        if prev is not None:
            out.append(Obs(name, cur - timedelta(days=7), prev))
    return _first_per_key(out)


def parse_bls_deepsea(body: bytes, ctx: Ctx) -> list[Obs]:
    """The BLS deep-sea-freight PPI (PCU483111483111) as FRED serves it."""
    return parse_fred_obs(body, Ctx(part="deep_sea_freight_ppi", fetched_at=ctx.fetched_at))


def parse_fred_obs(body: bytes, ctx: Ctx) -> list[Obs]:
    """FRED `series/observations` JSON (`observations[].date`, `.value`, '.' = missing) for ONE
    series, named by `ctx.part` (default `value`). Monthly dates are month starts; the period is
    the month's end."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    obs = doc.get("observations") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for o in obs if isinstance(obs, list) else []:
        v = _num(str((o or {}).get("value") or ""))
        try:
            d = date.fromisoformat(str((o or {}).get("date") or "")[:10])
        except ValueError:
            continue
        if v is not None:
            out.append(Obs(ctx.part or "value", _month_end(d.year, d.month), v))
    return out


#: NBS release tables and sentences: series key -> the row label printed in the release.
NBS_PRODUCTS: dict[str, str] = {
    "crude_steel": "粗钢", "steel_products": "钢材", "cement": "水泥",
    "nonferrous10": "十种有色金属", "primary_aluminium": "原铝", "autos": "汽车",
    "nev": "新能源汽车", "power_gen": "规模以上工业发电量", "thermal_power": "火力发电量",
    "hydro_power": "水力发电量", "nuclear_power": "核能发电量", "wind_power": "风力发电量",
    "solar_power": "太阳能发电量", "raw_coal": "原煤", "crude_oil": "原油",
    "crude_run": "原油加工量", "natural_gas": "天然气"}
_NBS_MONTH = re.compile(r"(\d{4})\s*年\s*(?:1\s*[—\-－–~]+\s*)?(\d{1,2})\s*月份?")  # noqa: RUF001
_NBS_SIGN = r"(增长|下降)"
_NBS_IP = re.compile(r"规模以上工业增加值(?:同比)?(?:实际)?" + _NBS_SIGN + r"\s*([\d.]+)\s*%")
_NBS_POWER = re.compile(r"规上工业发电量\s*([\d.]+)\s*亿千瓦时\s*[，,]?\s*同比" + _NBS_SIGN  # noqa: RUF001
                        + r"\s*([\d.]+)\s*%")
_NBS_FUEL = re.compile(
    r"(火电|水电|核电|风电|太阳能发电)\s*(?:同比)?" + _NBS_SIGN + r"\s*([\d.]+)\s*%")
_NBS_DAILY = re.compile(r"日均发电\s*([\d.]+)\s*亿千瓦时")
_NBS_PMI = re.compile(r"制造业采购经理指数\s*[（(]\s*PMI\s*[）)]\s*为\s*([\d.]+)\s*%")  # noqa: RUF001
_FUEL_KEY = {"火电": "thermal_power", "水电": "hydro_power", "核电": "nuclear_power",
             "风电": "wind_power", "太阳能发电": "solar_power"}


def _nbs_period_pub(text: str) -> tuple[date | None, datetime | None]:
    """The release's own month (the first 'YYYY年M月份' or 'YYYY年1—M月份') and its own stamp
    ('2026/09/15 10:00' Beijing, or '2026年09月15日'), converted to UTC."""
    pm = _NBS_MONTH.search(text)
    period = None
    if pm and 1 <= int(pm.group(2)) <= 12:
        period = _month_end(int(pm.group(1)), int(pm.group(2)))
    pub = None
    st = re.search(r"(20\d{2})[/年-](\d{1,2})[/月-](\d{1,2})日?\s*(\d{1,2}):(\d{2})", text)
    try:
        if st:
            pub = _utc(int(st.group(1)), int(st.group(2)), int(st.group(3)), int(st.group(4)),
                       int(st.group(5))) - timedelta(hours=8)
        elif (dm := _CN_DATE.search(text)):
            pub = _utc(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), 2)
    except ValueError:
        pub = None
    if period is not None and pub is not None and not (
            period < pub.date() <= period + timedelta(days=MAX_PUB_LAG_D)):
        pub = None
    return period, pub


def _signed2(word: str, v: str) -> float | None:
    x = _num(v)
    return None if x is None else (-x if word == "下降" else x)


def parse_nbs_industry(body: bytes, ctx: Ctx) -> list[Obs]:
    """NBS monthly industrial-production and energy-production releases (and the PMI release's
    headline). Table rows read as '<label>(<unit>) <month value> <YoY %>' (the release's own
    layout: 指标 | M月 | 同比增长(%) | 1-M月 | 同比增长(%)); the energy release's sentences
    ('规上工业发电量9438亿千瓦时,同比下降0.8%;日均发电304.4亿千瓦时', '火电同比下降4.3%,水电
    增长2.8%...') fill what the table lacks. Derived on the same page: industrial-power residual
    (generation YoY minus industrial value-added YoY) and power-minus-production divergence
    (generation YoY minus the mean YoY of crude steel, cement and ten non-ferrous metals)."""
    text = _text(body)
    period, pub = _nbs_period_pub(text)
    if period is None:
        return []
    out: list[Obs] = []
    vals: dict[str, float] = {}
    for key, label in NBS_PRODUCTS.items():
        m = re.search(r"(?<![一-鿿])" + re.escape(label)
                      + r"\s*[（(][^）)]{1,10}[）)]\s+(-?[\d.]+)\s+(-?[\d.]+)", text)  # noqa: RUF001
        if m and (lv := _num(m.group(1))) is not None and (y := _num(m.group(2))) is not None:
            vals[f"{key}_level"], vals[f"{key}_yoy"] = lv, y
    if (pw := _NBS_POWER.search(text)):
        lv2, y2 = _num(pw.group(1)), _signed2(pw.group(2), pw.group(3))
        if lv2 is not None and y2 is not None:
            vals.setdefault("power_gen_level", lv2)
            vals.setdefault("power_gen_yoy", y2)
    for fm in _NBS_FUEL.finditer(text):
        if (y3 := _signed2(fm.group(2), fm.group(3))) is not None:
            vals.setdefault(f"{_FUEL_KEY[fm.group(1)]}_yoy", y3)
    if (dl := _NBS_DAILY.search(text)) and (d := _num(dl.group(1))) is not None:
        vals["power_daily_avg"] = d
    if (ip := _NBS_IP.search(text)) and (y4 := _signed2(ip.group(1), ip.group(2))) is not None:
        vals["ip_va_yoy"] = y4
    if (pmi := _NBS_PMI.search(text)) and (p := _num(pmi.group(1))) is not None:
        vals["mfg_pmi"] = p
    if "power_gen_yoy" in vals and "ip_va_yoy" in vals:
        vals["industrial_power_residual"] = round(vals["power_gen_yoy"] - vals["ip_va_yoy"], 4)
    heavy = [vals[k] for k in ("crude_steel_yoy", "cement_yoy", "nonferrous10_yoy") if k in vals]
    if "power_gen_yoy" in vals and len(heavy) == 3:
        vals["power_minus_heavy_output_yoy"] = round(vals["power_gen_yoy"] - sum(heavy) / 3, 4)
    for k, v in sorted(vals.items()):
        out.append(Obs(k, period, v, pub))
    return out


_FAI_TOTAL = re.compile(r"全国固定资产投资[（(]不含农户[）)]\s*([\d.]+)\s*亿元\s*[，,]?\s*同比"  # noqa: RUF001
                        + _NBS_SIGN + r"\s*([\d.]+)\s*%")
_FAI_PART = {
    "infra_ytd_yoy": re.compile(r"基础设施投资(?:[（(][^）)]*[）)])?\s*(?:同比)?" + _NBS_SIGN  # noqa: RUF001
                                + r"\s*([\d.]+)\s*%"),
    "manuf_ytd_yoy": re.compile(r"制造业投资\s*(?:同比)?" + _NBS_SIGN + r"\s*([\d.]+)\s*%"),
    "realestate_ytd_yoy": re.compile(
        r"房地产开发投资\s*(?:同比)?" + _NBS_SIGN + r"\s*([\d.]+)\s*%"),
    "fai_mom": re.compile(r"从环比看\s*[，,]?\s*\d{1,2}\s*月份固定资产投资[（(]不含农户[）)]\s*"  # noqa: RUF001
                          + _NBS_SIGN + r"\s*([\d.]+)\s*%")}


def parse_nbs_fai(body: bytes, ctx: Ctx) -> list[Obs]:
    """NBS fixed-asset-investment release ('1—8月份,全国固定资产投资(不含农户)293092亿元,同比
    下降7.2%', '基础设施投资(口径详见附注1)同比下降4.0%', '从环比看,8月份固定资产投资(不含
    农户)下降0.5%'). Year-to-date YoY as printed; the month's own MoM where printed. The national
    infrastructure-order proxy the CCGP award indices would have measured by basket."""
    text = _text(body)
    if "固定资产投资" not in text:
        return []
    period, pub = _nbs_period_pub(text)
    if period is None:
        return []
    out: list[Obs] = []
    if (t := _FAI_TOTAL.search(text)):
        lv, y = _num(t.group(1)), _signed2(t.group(2), t.group(3))
        if lv is not None and y is not None:
            out += [Obs("fai_ytd_100m", period, lv, pub), Obs("fai_ytd_yoy", period, y, pub)]
    for key, pat in _FAI_PART.items():
        if (m := pat.search(text)) and (v := _signed2(m.group(1), m.group(2))) is not None:
            out.append(Obs(key, period, v, pub))
    return out


NBS_SECTORS: dict[str, str] = {
    "ferrous_smelting": "黑色金属冶炼和压延加工业",
    "nonferrous_smelting": "有色金属冶炼和压延加工业",
    "coal_mining": "煤炭开采和洗选业", "electrical_machinery": "电气机械和器材制造业",
    "oil_gas_extraction": "石油和天然气开采业", "chemicals": "化学原料和化学制品制造业",
    "electronics": "计算机、通信和其他电子设备制造业", "autos": "汽车制造业",
    "ferrous_mining": "黑色金属矿采选业"}
_PROFIT_YTD = re.compile(r"实现利润总额\s*([\d.]+)\s*亿元\s*[，,]?\s*同比" + _NBS_SIGN  # noqa: RUF001
                         + r"\s*([\d.]+)\s*%")
_PROFIT_MONTH = re.compile(r"\d{1,2}\s*月份\s*[，,]?\s*规模以上工业企业利润(?:同比)?" + _NBS_SIGN  # noqa: RUF001
                           + r"\s*([\d.]+)\s*%")


def parse_nbs_profits(body: bytes, ctx: Ctx) -> list[Obs]:
    """NBS industrial-enterprise profits release: total profit YTD (100m yuan and YoY), the
    month's own YoY, and sector profit YoY from the sector table (row: sector | revenue | YoY % |
    profit | YoY %; the profit YoY is the fourth number). Sector-level corporate activity --
    the aggregate the directive asks for in place of single-company supply-chain records."""
    text = _text(body)
    if "利润" not in text:
        return []
    period, pub = _nbs_period_pub(text)
    if period is None:
        return []
    out: list[Obs] = []
    if (t := _PROFIT_YTD.search(text)):
        lv, y = _num(t.group(1)), _signed2(t.group(2), t.group(3))
        if lv is not None and y is not None:
            out += [Obs("profit_ytd_100m", period, lv, pub), Obs("profit_ytd_yoy", period, y, pub)]
    if (mm := _PROFIT_MONTH.search(text)) and (v := _signed2(mm.group(1), mm.group(2))) is not None:
        out.append(Obs("profit_month_yoy", period, v, pub))
    for key, label in NBS_SECTORS.items():
        m = re.search(re.escape(label) + r"\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)",
                      text)
        if m and (y5 := _num(m.group(4))) is not None:
            out.append(Obs(f"{key}_profit_ytd_yoy", period, y5, pub))
    return out


#: CCGP award-notice baskets: basket -> ((ascii id, search keyword), ...). A keyword is a
#: commodity-intensity proxy (steel structures for steel, cable for copper, roads and bridges for
#: infrastructure, substations and PV for energy); the index is the count of award notices.
CCGP_BASKETS: dict[str, tuple[tuple[str, str], ...]] = {
    "steel": (("gangjiegou", "钢结构"), ("gangcai", "钢材")),
    "copper": (("dianlan", "电缆"), ("tongcai", "铜材")),
    "infrastructure": (("daolu", "道路工程"), ("qiaoliang", "桥梁")),
    "energy": (("biandianzhan", "变电站"), ("guangfu", "光伏"))}
CCGP_URL = ("http://search.ccgp.gov.cn/bxsearch?searchtype=1&page_index=1&bidSort=0&pinMu=0"
            "&bidType=7&kw={kw}&start_time={start}&end_time={end}&timeType=6&displayZone="
            "&zoneId=&pppStatus=0&agentName=")
CN_PROVINCES = ("北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海", "江苏",
                "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
                "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西", "甘肃", "青海", "宁夏",
                "新疆")
_CCGP_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S | re.I)
_CCGP_TOTAL = re.compile(r"共找到\s*(?:<[^>]+>\s*)*([\d,]+)\s*(?:<[^>]+>\s*)*条")
_CCGP_TIME = re.compile(r"(20\d{2})\.(\d{2})\.(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?")


def ccgp_items(body: bytes) -> list[dict[str, Any]]:
    """Award notices on one CCGP search-result page, as fields: title, publication_time (UTC),
    buyer, agency, notice_type, province, municipality (the buyer's 市/州 when it names one),
    project_class (货物类/工程类/服务类). Supplier, award value and duration are on the detail
    page and are NOT read here (UNMEASURED, never guessed)."""
    out: list[dict[str, Any]] = []
    for li in _CCGP_LI.findall(body.decode("utf-8", errors="replace")):
        text = _text(li.encode())
        tm = _CCGP_TIME.search(text)
        if not tm:
            continue
        title_m = re.search(r"<a[^>]*>(.*?)</a>", li, re.S)
        buyer = re.search(r"采购人[：:]\s*([^|｜\s]+)", text)  # noqa: RUF001
        agency = re.search(r"代理机构[：:]\s*([^|｜\s]+)", text)  # noqa: RUF001
        prov = next((p for p in CN_PROVINCES if re.search(r"(?:\||｜)\s*" + p + r"\s*(?:\||｜)",  # noqa: RUF001
                                                          text + "|")), None)
        cls = re.search(r"(货物类|工程类|服务类)", text)
        city = re.search(r"([一-鿿]{2,6}?[市州盟])", buyer.group(1)) if buyer else None
        try:
            t = _utc(*(int(tm.group(i)) for i in range(1, 6))) - timedelta(hours=8)
        except ValueError:
            continue
        out.append({"title": _text((title_m.group(1) if title_m else "").encode())[:200],
                    "publication_time": t.isoformat(timespec="minutes"),
                    "buyer": buyer.group(1).strip() if buyer else None,
                    "agency": agency.group(1).strip() if agency else None,
                    "notice_type": "中标公告" if "中标" in text else
                    ("成交公告" if "成交" in text else None),
                    "province": prov, "municipality": city.group(1) if city else None,
                    "project_class": cls.group(1) if cls else None})
    return out


def parse_ccgp_awards(body: bytes, ctx: Ctx) -> list[Obs]:
    """One CCGP search (award notices, one keyword, one calendar month; `ctx.part` =
    'basket:id:YYYY-MM'): the result count printed as '共找到 N 条' is that keyword's award count
    for the month, and the provinces on the first page are its (first-page) breadth."""
    parts = (ctx.part or "").split(":")
    tot = _CCGP_TOTAL.search(body.decode("utf-8", errors="replace"))
    if len(parts) != 3 or not tot or not re.fullmatch(r"\d{4}-\d{2}", parts[2]):
        return []
    basket, kid, ym = parts
    period = _month_end(int(ym[:4]), int(ym[5:]))
    n = _num(tot.group(1))
    if n is None:
        return []
    items = ccgp_items(body)
    provs = {i["province"] for i in items if i.get("province")}
    out = [Obs(f"{basket}__{kid}_awards", period, n)]
    if items:
        out.append(Obs(f"{basket}__{kid}_provinces_p1", period, float(len(provs))))
    return out


def parse_s5p_stats(body: bytes, ctx: Ctx) -> list[Obs]:
    """Sentinel Hub Statistical API reply (CDSE) for one facility box (`ctx.part`): per daily
    interval, the mean tropospheric NO2 column (mol/m2 -> umol/m2) of the valid pixels. A day
    with more than half its pixels masked (cloud, no overpass) is not a value: it is skipped,
    never zero-filled. The valid share is published beside it."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = doc.get("data") if isinstance(doc, dict) else None
    part = ctx.part or "area"
    out: list[Obs] = []
    for r in rows if isinstance(rows, list) else []:
        try:
            d = date.fromisoformat(str(((r or {}).get("interval") or {}).get("from") or "")[:10])
        except ValueError:
            continue
        outs = (r.get("outputs") or {}) if isinstance(r, dict) else {}
        band = next(iter(((outs.get("no2") or outs.get("default") or {}).get("bands") or {})
                         .values()), None)
        st = (band or {}).get("stats") or {}
        mean, n = _num(str(st.get("mean"))), _num(str(st.get("sampleCount")))
        nod = _num(str(st.get("noDataCount") or 0)) or 0.0
        if mean is None or not n or n <= 0:
            continue
        valid = max(0.0, (n - nod) / n)
        if valid < 0.5:
            continue
        out.append(Obs(f"{part}_no2_umol", d, round(mean * 1e6, 4)))
        out.append(Obs(f"{part}_no2_valid_share", d, round(valid, 4)))
    return out


#: Naver DataLab keyword groups (Korean). Every request carries the ANCHOR group, and a topic's
#: value is its ratio over the anchor's in the same reply: DataLab rescales each reply so its
#: largest point is 100, and the ratio of two groups in one reply is invariant to that rescale.
NAVER_ANCHOR = ("anchor", ("네이버",))
NAVER_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("fx", ("환율", "원달러환율", "달러")),
    ("semiconductor", ("반도체", "메모리 반도체", "HBM")),
    ("household_leverage", ("가계대출", "주택담보대출", "대출금리")),
    ("property", ("아파트값", "집값", "부동산")),
    ("recession", ("경기침체", "불황", "실업")),
    ("inflation", ("물가", "인플레이션", "금리인상")),
    ("energy", ("유가", "전기요금", "휘발유 가격")))
NAVER_URL = "https://openapi.naver.com/v1/datalab/search"


def parse_naver_datalab(body: bytes, ctx: Ctx) -> list[Obs]:
    """Naver DataLab search-trend reply (`results[].title/keywords/data[].period/ratio`, weekly
    timeUnit). Each topic's weekly ratio over the anchor's ratio in the same reply, dated at the
    week's LAST day (Naver labels the week by its first). A week with a zero anchor is skipped."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    res = doc.get("results") if isinstance(doc, dict) else None
    if not isinstance(res, list):
        return []
    series: dict[str, dict[date, float]] = {}
    for r in res:
        title = str((r or {}).get("title") or "")
        for p in (r or {}).get("data") or []:
            v = _num(str((p or {}).get("ratio")))
            with contextlib.suppress(ValueError):
                d = date.fromisoformat(str((p or {}).get("period") or "")[:10])
                if v is not None and title:
                    series.setdefault(title, {})[d] = v
    anchor = series.get(NAVER_ANCHOR[0])
    if not anchor:
        return []
    unit = str(doc.get("timeUnit") or "week")
    span = 6 if unit == "week" else 0
    out: list[Obs] = []
    for title, pts in sorted(series.items()):
        if title == NAVER_ANCHOR[0]:
            continue
        for d, v in sorted(pts.items()):
            a = anchor.get(d)
            end = d + timedelta(days=span)
            if a and a > 0 and end < ctx.fetched_at.date():
                out.append(Obs(f"{_slug(title)}_rel", end, round(v / a, 6)))
    return out


def load_clusters(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """The named industrial-cluster registry (desks/mt5/data/industrial_clusters.json): id ->
    {bbox (W,S,E,N), types, province, source}. Read at use, never hard-coded."""
    doc = _read_json(path or DESK / "data" / "industrial_clusters.json", {})
    r = float((doc or {}).get("radius_deg") or 0.25) if isinstance(doc, dict) else 0.25
    out: dict[str, dict[str, Any]] = {}
    for f in (doc or {}).get("facilities") or [] if isinstance(doc, dict) else []:
        try:
            lat, lon = float(f["lat"]), float(f["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        out[str(f["id"])] = {"bbox": (round(lon - r, 4), round(lat - r, 4), round(lon + r, 4),
                                      round(lat + r, 4)),
                             "types": tuple(f.get("types") or ()),
                             "province": f.get("province"), "source": f.get("source")}
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


_DGI_YM = re.compile(r"\b(20\d{2})\s*[-/]\s*(\d{1,2})\b")
_DGI_FY = re.compile(r"\b(20\d{2})\s*[-/]\s*(\d{2})\b")
_DGI_MON = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I)


def _dgi_period(row: dict[str, Any]) -> date | None:
    """A data.gov.in record's month from its month/year/period fields, never by position:
    `2026-03`, `Mar-2026`, or month `March` with a fiscal year `2025-26` (Jan-Mar belong to the
    fiscal year's second calendar year)."""
    txt = " ".join(str(v) for k, v in row.items()
                   if any(w in str(k).lower() for w in ("month", "year", "period", "date")))
    mn = _DGI_MON.search(txt)
    if mn:
        mo = _EN_MONTHS3[mn.group(1).lower()[:3]]
        fy = _DGI_FY.search(txt)
        yr = re.search(r"\b(20\d{2})\b", txt)
        if fy and int(fy.group(2)) == (int(fy.group(1)) + 1) % 100:
            y = int(fy.group(1)) + (mo <= 3)
        elif yr:
            y = int(yr.group(1))
        else:
            return None
        return _month_end(y, mo)
    ym = _DGI_YM.search(txt)
    if ym and 1 <= int(ym.group(2)) <= 12:
        return _month_end(int(ym.group(1)), int(ym.group(2)))
    return None


def parse_dgi_iip_consumer(body: bytes, ctx: Ctx) -> list[Obs]:
    """data.gov.in OGD API (`{"records": [...]}`) for ONE configured use-based IIP resource:
    the consumer-durables and consumer-non-durables index per month. Columns are matched by
    name (`consumer` + `durable`, with or without `non`); a growth-rate column (`growth`,
    `change`, `%`) is never read as an index. A reply with no such column is nothing."""
    try:
        doc = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        return []
    rows = doc.get("records") if isinstance(doc, dict) else None
    out: list[Obs] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict) or (d := _dgi_period(r)) is None:
            continue
        for k, v in r.items():
            kl = re.sub(r"[^a-z%]", "", str(k).lower())
            if ("consumer" not in kl or "durable" not in kl
                    or any(w in kl for w in ("growth", "change", "%", "weight"))):
                continue
            x = _num(str(v))
            if x is not None:
                name = "consumer_nondurables_index" if "non" in kl else "consumer_durables_index"
                out.append(Obs(name, d, x))
    return _first_per_key(out)


_ZA_RETAIL = re.compile(
    r"retail\s+trade\s+sales\s+(increased|decreased|rose|fell|declined|grew|contracted)\s+by\s+"
    r"(\d+(?:[.,]\d+)?)\s*%\s*(?:year[\s-]*on[\s-]*year|y/y)\s+in\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(20\d{2})", re.I)


def parse_statssa_retail(body: bytes, ctx: Ctx) -> list[Obs]:
    """Stats SA P6242.1 retail trade sales release text: 'Retail trade sales increased by 2,6%
    year-on-year in December 2025' (constant 2019 prices). South African decimals use a comma.
    The month comes from the sentence itself; a sentence naming no year is not read."""
    out: list[Obs] = []
    for m in _ZA_RETAIL.finditer(_text(body)):
        v = _num(m.group(2).replace(",", "."))
        if v is None:
            continue
        neg = m.group(1).lower() in ("decreased", "fell", "declined", "contracted")
        out.append(Obs("retail_sales_yoy", _month_end(int(m.group(4)),
                                                      _MONTHS[m.group(3).lower()]),
                       -v if neg else v))
    return _first_per_key(out)


def rule_in_iip(period: date) -> datetime:
    """MoSPI's IIP quick estimate for month M prints on the 28th of M+1 at 16:00 IST (10:30 UTC)
    on PIB (e.g. March 2026 on 28 Apr 2026, July 2025 on 28 Aug 2025); the data.gov.in upload
    follows it. Stamped the 28th of M+1 plus 7 days, 00:00 UTC, rolled to a weekday: a week of
    slack for the OGD upload and for a 28th that falls on a holiday. Late, never early."""
    y, m = period.year + (period.month == 12), 1 if period.month == 12 else period.month + 1
    return _roll_weekday(_utc(y, m, 28) + timedelta(days=7))


def rule_za_retail(period: date) -> datetime:
    """Stats SA prints P6242.1 retail trade sales for month M about seven weeks after it, 13:00
    SAST (11:00 UTC). Observed: Mar 2025 on 21 May 2025 (+51 d), Oct 2025 reported 11 Dec 2025
    (+41 d), Dec 2025 on 18 Feb 2026 (+49 d), Jun 2026 on 20 Aug 2026 (+51 d). Stamped at +56
    days 00:00 UTC, weekday-rolled: after every observed release."""
    return _roll_weekday(_utc(period.year, period.month, period.day) + timedelta(days=56))


def rule_estat_immig(period: date) -> datetime:
    """The Immigration Services Agency's monthly 出入国管理統計 tables (e-Stat 月次) are
    published about eight weeks after the month: Jan 2026 on 2026-03-25 (+53 d) and Feb 2026 on
    2026-04-24 (+55 d), per the e-Stat file lists (lid 000001478407 / 000001480323). Stamped at
    +60 days 00:00 UTC, weekday-rolled: after both. (The 45-day rule it replaces was EARLY.)"""
    return _roll_weekday(_utc(period.year, period.month, period.day) + timedelta(days=60))


#: Seollal and Chuseok (first day of the public holiday) 2018-2030: each closes Korean ministries
#: for three to five days, and a release due across one slips.
KR_LONG_HOLIDAYS: tuple[date, ...] = (
    date(2018, 2, 15), date(2018, 9, 23), date(2019, 2, 4), date(2019, 9, 12),
    date(2020, 1, 24), date(2020, 9, 30), date(2021, 2, 11), date(2021, 9, 20),
    date(2022, 1, 31), date(2022, 9, 9), date(2023, 1, 21), date(2023, 9, 28),
    date(2024, 2, 9), date(2024, 9, 16), date(2025, 1, 28), date(2025, 10, 3),
    date(2026, 2, 16), date(2026, 9, 24), date(2027, 2, 6), date(2027, 9, 14),
    date(2028, 1, 26), date(2028, 10, 2), date(2029, 2, 12), date(2029, 9, 21),
    date(2030, 2, 2), date(2030, 9, 11))


def rule_kr_mof_port(period: date) -> datetime:
    """MOF announces month M's national port throughput about 30 days after it (June 2026 on
    2026-07-30, reported 17:51 KST), and the data.go.kr API row follows the press release. The
    30-day rule it replaces stamped 00:00 UTC on that same day, BEFORE the release. Stamped at
    +45 days, plus 7 when Seollal or Chuseok falls inside that window, 00:00 UTC, weekday-
    rolled: a conservative bound, late never early."""
    t = period + timedelta(days=45)
    if any(period < h <= t for h in KR_LONG_HOLIDAYS):
        t += timedelta(days=7)
    return _roll_weekday(_utc(t.year, t.month, t.day))


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
    #: "current" when the endpoint serves only the latest revised vintage: every row read on a
    #: first (history) fetch is that vintage, not what was known at the time. Published with the
    #: series (axis file, roster) so no reader mistakes a backfill for a first release.
    vintage: str = ""
    #: Further env vars that must ALL be set beside key_env (a client id needs its secret).
    key_also: tuple[str, ...] = ()
    #: Env groups that satisfy key_env when the token helper can mint from them (CDSE).
    key_alts: tuple[tuple[str, ...], ...] = ()
    #: A paid vendor with no licence held: UNCONFIGURED (never BLOCKED_ON_TERMS) and never fetched.
    paid_licence: bool = False

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
        signal_series=("total_count", "facility_thermal_breadth", "steel_thermal_breadth",
                       "facility_thermal_anomaly_pct"),
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
            "singapore": {"XTIUSD": 1, "AUDUSD": 1},
            "cn_tanker": {"XTIUSD": 1, "XBRUSD": 1},
            "cn_bulk": {"AUDUSD": 1, "XCUUSD": 1},
            "cn_": {"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1}},
        signal_series=("port_hedland_portcalls", "shanghai_portcalls", "busan_portcalls",
                       "cn_total_portcalls", "cn_port_breadth", "cn_north_minus_south_calls",
                       "cn_bulk_minus_container_share", "cn_tanker_share"),
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
                            "zh_basket": {"USDCNH": 1, "XAUUSD": 1, "AUDUSD": -1},
                            "zh_kw_gold": {"XAUUSD": 1},
                            "zh_kw_copper": {"XCUUSD": 1},
                            "zh_": {"USDCNH": 1, "HK50": -1, "CHINAH": -1},
                            "ko_": {"USDKRW": 1}},
        signal_series=("ja_boj_views", "ja_nikkei_views", "zh_pboc_views", "zh_rmb_views",
                       "zh_hsi_views", "ko_bok_views", "ko_kospi_views", "zh_basket_breadth",
                       "zh_basket_anomaly_pct"),
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
        note=("minimal ECOS reader (no ECOS reader exists in the repo). Default codes 601Y003 / "
              "201010 (personal general-purchase credit-card spend, total of bank and non-bank "
              "issuers) read off ECOS's own item catalogue (CONFIG_DEFAULTS cites it); "
              "ALT_ECOS_CARD_STAT / ALT_ECOS_CARD_ITEM override. Without the key the row is "
              "BLOCKED_ON_KEY and nothing is requested")),
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
        rule=rule_estat_immig, transform="yoy_monthly", key_env="ESTAT_APP_ID",
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
        note=("stands in for jp_jnto_arrivals (JNTO site policy refuses reuse). statsDataId "
              "defaults to 0003449066 (国籍・地域別 入国外国人の在留資格, monthly, read off "
              "e-Stat's dbview page; CONFIG_DEFAULTS cites it). cdCat01 has NO default: its "
              "code is not printed on an official page, so the row stays UNCONFIGURED until "
              "ALT_ESTAT_IMMIG_CAT01 is read from getMetaInfo on the box; reuses jp_tokyo_cpi's "
              "e-Stat key")),
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
        vintage="current",
        note=("stands in for mx_antad_sss (ANTAD terms refuse reuse). NO DEFAULT CODE (no "
              "official page reachable without a token prints it; CONFIG_DEFAULTS says why): the "
              "BIE indicator id comes only from ALT_INEGI_EMEC_ID, and it MUST be the NSA 'serie "
              "original' retail index (the YoY transform compares the same month a year apart; "
              "a seasonally adjusted series is revised every month). The BIE API serves the "
              "current vintage only, so history rows are stamped vintage=current and "
              "pit_quality=backfill. Release: EMEC Feb 2026 on 2026-04-23 (+54 d), Mar 2026 on "
              "2026-05-21 (+51 d); the 55-day rule is after both. The desk's Banxico SIE rows "
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
        rule=rule_kr_mof_port, transform="yoy_monthly", key_env="DATA_GO_KR_KEY",
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
    Source(
        id="in_dgi_iip_consumer",
        name="MoSPI IIP consumer durables and non-durables, monthly (India, data.gov.in OGD API)",
        url=("https://api.data.gov.in/resource/{ALT_DGI_IIP_RESOURCE}?api-key={key}"
             "&format=json&limit=1000"),
        region="IN", language="en", cadence="monthly", parse=parse_dgi_iip_consumer,
        rule=rule_in_iip, transform="yoy_monthly", key_env="DATA_GOV_IN_KEY",
        config_env=("ALT_DGI_IIP_RESOURCE",),
        instruments={"USDINR": -1},
        signal_series=("consumer_nondurables_index", "consumer_durables_index"),
        mechanism=("output of consumer goods (non-durables: food, toiletries, medicines; "
                   "durables: two-wheelers, appliances) is what Indian households buy, read from "
                   "the factory gate a month after it happens: the retail demand a UPI-value print "
                   "shows from the payments rail, as an official index"),
        payer="INR and India-exposed holders waiting for quarterly GDP and RBI commentary",
        constraint="RBI manages INR volatility, so flow information reprices slowly",
        licence=("Government Open Data License - India (GODL, Gazette of India 2017): worldwide, "
                 "royalty-free, commercial use with attribution; free data.gov.in API key"),
        source_culture="IN/en", participant_structure=("retail_heavy", "policy_driven"),
        failure_mode_hypothesis=("fails when festival timing (Diwali in October or November) "
                                 "moves production between months, and on a base-year revision "
                                 "(2011-12 to 2022-23) that breaks the YoY comparison"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("stands in for in_npci_upi (NPCI robots-refused; RBI 'All Rights Reserved'). "
              "Production, not payments: it measures the goods households buy, not the payment "
              "flow. NO DEFAULT CODE: the use-based monthly IIP resource id comes only from "
              "ALT_DGI_IIP_RESOURCE (catalog: data.gov.in/catalog/monthly-time-series-use-based-"
              "indices-and-growth); confirm it carries the 2022-23 base on the box. Credit line "
              "when published: 'Ministry of Statistics and Programme Implementation, Index of "
              "Industrial Production, data.gov.in. Published under GODL-India'")),
    Source(
        id="za_statssa_retail",
        name="Stats SA P6242.1 retail trade sales, constant prices, YoY (South Africa)",
        url=os.environ.get("ALT_STATSSA_RETAIL_URL",
                           "https://www.statssa.gov.za/?page_id=1854&PPN=P6242.1"),
        region="ZA", language="en", cadence="monthly", parse=parse_statssa_retail,
        rule=rule_za_retail, transform="given",
        config_env=("ALT_STATSSA_RETAIL_URL",),
        instruments={"USDZAR": -1, "ZARJPY": 1},
        signal_series=("retail_sales_yoy",),
        mechanism=("the statistics office's monthly survey of retail sales at constant prices is "
                   "South African household spending, the consumer half of what the payments "
                   "clearing house's transaction index reads from the rail"),
        payer="ZAR carry holders pricing on commodity terms of trade alone",
        constraint="SARB and ZAR positioning reprice at data dates; GDP is quarterly and late",
        licence=("Stats SA publication notice: users may apply or process the data with Stats SA "
                 "acknowledged as the source; the data may not be sold without permission"),
        source_culture="ZA/en", participant_structure=("retail_heavy", "institutional"),
        failure_mode_hypothesis=("fails under load-shedding months and on Black Friday and "
                                 "SASSA grant-payment calendar shifts, and it prints about seven "
                                 "weeks after the month, later than BETI"),
        crowding_prior="low", substitutes_for=_CARD,
        note=("stands in for za_beti (PayInc terms unreadable; SARB requires written permission). "
              "Stats SA pages sit behind an Incapsula check, so the release URL (an HTML release "
              "page carrying the headline sentence) comes only from ALT_STATSSA_RETAIL_URL; unset "
              "the row is UNCONFIGURED and nothing is requested. Internal research use only: the "
              "data and anything derived from it are never sold or redistributed for sale. Credit "
              "line when published: 'Source: Statistics South Africa, P6242.1 Retail trade sales; "
              "analysis is the desk's own independent processing of the data'")),
)

# ---------------------------------------------------------------------------- physical exhaust (P4)
_FREIGHT = "container freight route indices (SCFI/CCFI, Drewry WCI, Freightos FBX)"
_CORP = "corporate supply-chain registries (Tianyancha, Qichacha)"
_PROC = "public-procurement award analytics (CCGP award aggregators)"
_SEARCH = "search-attention panels (Baidu Index, Naver DataLab)"
NBS_LIST_URL = "https://www.stats.gov.cn/sj/zxfb/"
CDSE_STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
S5P_EVALSCRIPT = ("//VERSION=3\nfunction setup(){return {input:[{bands:[\"NO2\",\"dataMask\"]}],"
                  "output:[{id:\"no2\",bands:1,sampleType:\"FLOAT32\"},{id:\"dataMask\",bands:1}]};}"
                  "\nfunction evaluatePixel(s){return {no2:[s.NO2],dataMask:[s.dataMask]};}")

PHYSICAL_SOURCES: tuple[Source, ...] = (
    Source(
        id="cn_mot_port_monthly",
        name="China MOT monthly port cargo and container throughput, by port (xlsx)",
        url=os.environ.get("ALT_CN_MOT_MONTHLY_URL",
                           "https://xxgk.mot.gov.cn/zhengceapp/863/868/list_7234.html"),
        region="CN", language="zh", cadence="monthly", parse=parse_mot_port_monthly,
        rule=_lag_rule(30, 0, weekday=True), transform="given",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1, "USDCNH": -1},
        series_instruments={"commodity_ports": {"AUDUSD": 1, "AUS200": 1, "XCUUSD": 1},
                            "container_port_breadth": {"CHINAH": 1, "HK50": 1, "USDCNH": -1},
                            "north_minus_south": {"AUDUSD": 1, "XCUUSD": 1},
                            "bulk_minus_container": {"AUDUSD": 1, "XCUUSD": 1}},
        signal_series=("national_cargo_yoy", "national_teu_yoy", "commodity_ports_cargo_yoy",
                       "container_port_breadth", "north_minus_south_cargo_yoy",
                       "bulk_minus_container_yoy"),
        mechanism=("the transport ministry's monthly port table counts cargo tonnes and boxes "
                   "port by port: dry-bulk ports (Tangshan, Rizhao, Qingdao) are iron-ore and coal "
                   "arrivals, container ports are export volume, and their divergence separates "
                   "industrial input demand from export demand weeks before customs values"),
        payer="China-trade proxies (AUD, copper, HK) waiting for value-based customs data",
        constraint="customs prints values, monthly and late; tonnes and boxes lead them",
        licence="Ministry of Transport of the PRC public statistics (terms not granted: see TERMS)",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis=("fails around Spring Festival (January-February combined base) "
                                 "and typhoon closures, and when transhipment double-counts boxes"),
        crowding_prior="low", substitutes_for=_SAT,
        note=("the monthly 港口货物、集装箱吞吐量 workbook linked from the MOT list; the "
              "parser reads the .xlsx itself (stdlib). BLOCKED until MOT terms grant reuse; the "
              "flip is one TERMS line. Release rule +30 days, late-biased (UNMEASURED on box)")),
    Source(
        id="cn_sse_scfi_routes",
        name="Shanghai Shipping Exchange SCFI by route (Shanghai x destination)",
        url="https://en.sse.net.cn/indices/scfinew.jsp", region="CN", language="en",
        cadence="weekly", parse=parse_sse_routes, rule=_lag_rule(0, 12, weekday=True),
        transform="given", instruments={"CHINAH": 1, "AUDUSD": 1},
        signal_series=("scfi_composite",),
        mechanism=("the spot container rate out of Shanghai by destination is export demand "
                   "against vessel supply, route by route"),
        payer="trade-cycle holders reading a single blended freight headline",
        constraint="freight contracts reprice weekly; trade data monthly",
        licence="Shanghai Shipping Exchange (All Rights Reserved; no reuse terms found)",
        source_culture="CN/zh", participant_structure=("physical_flow",),
        failure_mode_hypothesis="fails when carriers' blank sailings move rates without demand",
        crowding_prior="medium",
        note=("page is JS-rendered; the parser reads the rendered table layout. BLOCKED on terms; "
              "route granularity is lost in the substitute (a national freight PPI)")),
    Source(
        id="us_bls_deepsea_freight",
        name="BLS PPI: deep sea freight transportation (via FRED, monthly)",
        url=("https://api.stlouisfed.org/fred/series/observations?series_id=PCU483111483111"
             "&api_key={key}&file_type=json&observation_start=2008-01-01"),
        region="US", language="en", cadence="monthly", parse=parse_bls_deepsea,
        rule=_lag_rule(20, 13, weekday=True), transform="yoy_monthly", key_env="FRED_API_KEY",
        instruments={"AUDUSD": 1, "CHINAH": 1, "XCUUSD": 1},
        signal_series=("deep_sea_freight_ppi",),
        mechanism=("the producer price of deep-sea freight is what ocean carriers bill, an "
                   "official monthly index of the container and bulk rate cycle: a freight-cost "
                   "impulse is Asian export demand meeting vessel supply"),
        payer="trade-cycle and commodity-FX holders reading spot-rate headlines only",
        constraint="official price indices print monthly; spot rates are licensed",
        licence="US BLS public domain data (cite BLS); FRED API terms and notice",
        source_culture="US/en", participant_structure=("physical_flow", "institutional"),
        failure_mode_hypothesis=("fails because it blends routes and contract types, so a "
                                 "single-lane spike (Red Sea) is diluted; preliminary prints "
                                 "revise four months later"),
        crowding_prior="low", substitutes_for=_FREIGHT, vintage="current",
        note=("stands in for the SCFI/CCFI/WCI/FBX route indices, whose terms bar reuse: a "
              "NATIONAL aggregate, so route x origin x destination is NOT preserved by it. "
              "FRED serves the current vintage; history rows are backfill")),
    Source(
        id="cn_nbs_industry_power",
        name="NBS industrial production, energy production and PMI releases (China)",
        url=os.environ.get("ALT_NBS_LIST_URL", NBS_LIST_URL), region="CN", language="zh",
        cadence="monthly", parse=parse_nbs_industry, rule=_lag_rule(17, 2, weekday=True),
        transform="given",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1, "USDCNH": -1},
        series_instruments={"crude_steel": {"AUDUSD": 1, "AUS200": 1},
                            "primary_aluminium": {"XALUSD": -1},
                            "nonferrous10": {"XCUUSD": 1, "XZNUSD": 1},
                            "raw_coal": {"AUDUSD": -1},
                            "crude_run": {"XTIUSD": 1, "XBRUSD": 1},
                            "thermal_power": {"AUDUSD": 1, "XNGUSD": 1},
                            "power_gen": {"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1},
                            "industrial_power_residual": {"AUDUSD": 1, "XCUUSD": 1},
                            "power_minus_heavy": {"AUDUSD": -1, "XCUUSD": -1}},
        signal_series=("power_gen_yoy", "thermal_power_yoy", "hydro_power_yoy",
                       "crude_steel_yoy", "nonferrous10_yoy", "crude_run_yoy", "raw_coal_yoy",
                       "industrial_power_residual", "power_minus_heavy_output_yoy", "mfg_pmi"),
        mechanism=("generation by fuel is the economy's metered load: thermal burn against hydro "
                   "is coal demand, generation against industrial value added is the part of "
                   "the output print electricity does not confirm, and steel, aluminium and "
                   "crude runs are the commodity demand the AUD and metals price"),
        payer="China-proxy holders pricing the value-added headline alone",
        constraint="stimulus and commodity positioning reprice at monthly data dates only",
        licence="National Bureau of Statistics of China releases (public)",
        source_culture="CN/zh", participant_structure=("policy_driven", "physical_flow"),
        failure_mode_hypothesis=("fails in drought or flood months when hydro swaps with thermal "
                                 "for weather reasons, and on the January-February combined print"),
        crowding_prior="medium",
        note=("list page -> release pages whose title names the release (FOLLOW below), newest "
              "first, older list pages walked by a cursor; page stamp (Beijing) is the release")),
    Source(
        id="cn_nbs_fai",
        name="NBS fixed-asset investment: total, infrastructure, manufacturing (China)",
        url=os.environ.get("ALT_NBS_LIST_URL", NBS_LIST_URL), region="CN", language="zh",
        cadence="monthly", parse=parse_nbs_fai, rule=_lag_rule(17, 2, weekday=True),
        transform="given",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1},
        series_instruments={"infra": {"AUDUSD": 1, "XCUUSD": 1, "AUS200": 1},
                            "realestate": {"AUDUSD": 1, "CHINAH": 1, "HK50": 1}},
        signal_series=("infra_ytd_yoy", "manuf_ytd_yoy", "fai_ytd_yoy", "fai_mom"),
        mechanism=("infrastructure investment is the steel- and copper-intensive order book "
                   "that procurement awards record notice by notice; its year-to-date pace "
                   "against its own run-rate is the construction-demand state"),
        payer="iron-ore, copper and AUD holders reading stimulus headlines, not spend",
        constraint="local-government spending is announced long before it is spent",
        licence="National Bureau of Statistics of China releases (public)",
        source_culture="CN/zh", participant_structure=("policy_driven", "physical_flow"),
        failure_mode_hypothesis=("fails when the infrastructure definition (口径) is revised "
                                 "and on year-to-date base effects early in the year"),
        crowding_prior="medium", substitutes_for=_PROC,
        note=("stands in for ccgp_award_indices (CCGP terms grant no reuse): national, by sector, "
              "so provincial breadth and the commodity baskets are NOT preserved by it")),
    Source(
        id="cn_nbs_profits",
        name="NBS industrial-enterprise profits, total and by sector (China)",
        url=os.environ.get("ALT_NBS_LIST_URL", NBS_LIST_URL), region="CN", language="zh",
        cadence="monthly", parse=parse_nbs_profits, rule=_lag_rule(30, 2, weekday=True),
        transform="given",
        instruments={"AUDUSD": 1, "CHINAH": 1, "HK50": 1},
        series_instruments={"ferrous_smelting": {"AUDUSD": 1, "AUS200": 1},
                            "nonferrous_smelting": {"XCUUSD": 1, "XALUSD": 1},
                            "coal_mining": {"AUDUSD": 1},
                            "oil_gas": {"XTIUSD": 1}},
        signal_series=("profit_ytd_yoy", "profit_month_yoy", "ferrous_smelting_profit_ytd_yoy",
                       "nonferrous_smelting_profit_ytd_yoy", "coal_mining_profit_ytd_yoy"),
        mechanism=("sector profits of steel mills, smelters and miners are the margin state of "
                   "the commodity chain: mills squeezed cut ore purchases, smelters flush add "
                   "capacity -- corporate activity aggregated by sector, never one company"),
        payer="commodity and China-equity holders pricing output volumes, not margins",
        constraint="listed-company reports are quarterly; the sector aggregate is monthly",
        licence="National Bureau of Statistics of China releases (public)",
        source_culture="CN/zh", participant_structure=("institutional", "policy_driven"),
        failure_mode_hypothesis=("fails when sample changes (enterprises entering or leaving "
                                 "the 规模以上 threshold) move the base, and on price effects "
                                 "that are not activity"),
        crowding_prior="low", substitutes_for=_CORP,
        note=("stands in for Tianyancha / Qichacha (paid, unconfigured) and SAMR / Credit China "
              "/ CNINFO (no reuse terms): sector aggregates only; supplier and customer links "
              "are NOT preserved by it")),
    Source(
        id="cn_tianyancha_supply", name="Tianyancha enterprise and supply-chain records (paid)",
        url="https://open.tianyancha.com/", region="CN", language="zh", cadence="monthly",
        parse=None, rule=_lag_rule(30, 0, weekday=True), transform="given",
        key_env="TIANYANCHA_TOKEN", instruments={"CHINAH": 1},
        signal_series=(),
        mechanism=("registrations, tenders, supplier and customer links aggregated by sector are "
                   "corporate activity before it reaches any official count"),
        payer="China-equity holders waiting for quarterly reports",
        constraint="a paid licence; no contract held",
        licence="Tianyancha commercial API (paid licence; none held)",
        source_culture="CN/zh", participant_structure=("institutional",),
        failure_mode_hypothesis="fails when registry noise (shell entities) dominates counts",
        crowding_prior="low", paid_licence=True,
        note="UNCONFIGURED: no licence; asia_sources `tianyancha_supply` carries the same state"),
    Source(
        id="cn_samr_registrations",
        name="SAMR / Credit China enterprise registration counts (China)",
        url="https://www.samr.gov.cn/", region="CN", language="zh", cadence="monthly",
        parse=None, rule=_lag_rule(30, 0, weekday=True), transform="given",
        instruments={"CHINAH": 1}, signal_series=(),
        mechanism=("new market-entity registrations by sector are the entry side of corporate "
                   "activity"),
        payer="China-equity holders", constraint="published irregularly, by press conference",
        licence="SAMR / Credit China (no reuse terms found)",
        source_culture="CN/zh", participant_structure=("policy_driven",),
        failure_mode_hypothesis="fails when registration campaigns, not activity, move counts",
        crowding_prior="low", note="no terms page found on either site: never fetched"),
    Source(
        id="cn_ccgp_award_indices",
        name="CCGP award notices aggregated into commodity order indices (China)",
        url=CCGP_URL, region="CN", language="zh", cadence="monthly", parse=parse_ccgp_awards,
        rule=_lag_rule(5, 0, weekday=True), transform="yoy_monthly",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "USDCNH": -1, "CHINAH": 1},
        series_instruments={"steel": {"AUDUSD": 1, "AUS200": 1},
                            "copper": {"XCUUSD": 1, "AUDUSD": 1},
                            "energy": {"XCUUSD": 1, "XALUSD": 1}},
        signal_series=("infrastructure_awards", "steel_awards", "copper_awards", "energy_awards"),
        mechanism=("award notices for steel structures, cable, roads and substations are the "
                   "state's commodity-intensive order book, counted the month they are signed"),
        payer="iron-ore, copper and AUD holders reading stimulus announcements",
        constraint="the official investment print is monthly and year-to-date",
        licence="China Government Procurement Network (MOF, 版权所有; no reuse terms found)",
        source_culture="CN/zh", participant_structure=("policy_driven", "physical_flow"),
        failure_mode_hypothesis=("fails when notice-posting rules change and when the search "
                                 "counts duplicates across amendments"),
        crowding_prior="low",
        note=("one search per keyword per month; counts from '共找到 N 条', first-page provinces "
              "as breadth. Values, suppliers and durations live on detail pages and are not "
              "read. BLOCKED on terms")),
    Source(
        id="cn_s5p_no2_clusters",
        name="Copernicus Sentinel-5P NO2 over named Chinese industrial clusters (CDSE)",
        url=CDSE_STATS_URL, region="CN", language="en", cadence="daily",
        parse=parse_s5p_stats, rule=_lag_rule(5, 0), transform="anomaly_daily",
        key_env="CDSE_TOKEN",
        instruments={"AUDUSD": 1, "XCUUSD": 1, "CHINAH": 1},
        series_instruments={"steel_": {"AUDUSD": 1, "AUS200": 1},
                            "refining_": {"XTIUSD": 1, "XBRUSD": 1},
                            "port_": {"AUDUSD": 1, "CHINAH": 1}},
        signal_series=("steel_no2_breadth", "refining_no2_breadth", "port_no2_breadth",
                       "all_no2_breadth"),
        mechanism=("tropospheric NO2 over a steel, refining or port cluster against its own "
                   "seasonal and weekday baseline is combustion activity, and the share of "
                   "clusters running above baseline is industrial breadth seen from orbit"),
        payer="iron-ore, copper, crude and AUD holders waiting for monthly output data",
        constraint="official output prints monthly and three weeks late",
        licence="Copernicus Sentinel data licence (free, full, open; attribution)",
        source_culture="CN/zh", participant_structure=("physical_flow", "policy_driven"),
        failure_mode_hypothesis=("fails under winter heating and meteorology (boundary-layer "
                                 "trapping), output curbs for air-quality events, and city "
                                 "emissions inside a city-seat box"),
        crowding_prior="low", substitutes_for=_SAT,
        key_alts=(("CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET"), ("CDSE_USERNAME", "CDSE_PASSWORD")),
        note=("Sentinel Hub Statistical API on CDSE, one POST per facility (OFFL NO2, daily "
              "intervals, cloud-masked days skipped). Token from CDSE_TOKEN; libs.ops."
              "token_refresh (PR #218) mints it from long-lived credentials when that lands")),
    Source(
        id="kr_naver_datalab",
        name="Naver DataLab search attention by topic (Korea)",
        url=NAVER_URL, region="KR", language="ko", cadence="weekly",
        parse=parse_naver_datalab, rule=_lag_rule(1, 0, weekday=True), transform="level_dev",
        key_env="NAVER_CLIENT_ID", key_also=("NAVER_CLIENT_SECRET",),
        instruments={"USDKRW": 1},
        series_instruments={"semiconductor": {"USDKRW": -1, "NAS100": 1},
                            "inflation": {"USDKRW": -1}, "energy": {"XTIUSD": 1}},
        signal_series=("fx_rel", "semiconductor_rel", "household_leverage_rel", "property_rel",
                       "recession_rel", "inflation_rel", "energy_rel"),
        mechanism=("Korean households search the won, chips, loans, flats and prices before "
                   "they act: attention relative to a stable anchor, its acceleration and its "
                   "surprise are local retail pressure the English tape does not read"),
        payer="won and Korea-exposed holders who price institutional flow only",
        constraint="retail acts with a lag; institutions ignore search volume",
        licence="Naver Developers Open API (registered client id/secret; terms unread here)",
        source_culture="KR/ko", participant_structure=("retail_heavy",),
        failure_mode_hypothesis=("fails when a celebrity or news story hijacks a keyword and "
                                 "when the anchor's own volume shifts"),
        crowding_prior="low", substitutes_for=_SEARCH,
        note=("two POSTs per pass (anchor + up to four topic groups each), weekly since 2016; "
              "value = topic ratio / anchor ratio in the same reply. Low-prior conditioning only "
              "until validated")),
    Source(
        id="in_nse_option_chain",
        name="NSE option chain: NIFTY / BANKNIFTY / USDINR (PCR, OI by strike, ATM IV)",
        url="https://www.nseindia.com/option-chain", region="IN", language="en", cadence="daily",
        parse=None, rule=_lag_rule(1, 12), transform="given",
        instruments={"USDINR": 1}, signal_series=(),
        mechanism=("put-call ratio, open interest by strike and ATM implied volatility are "
                   "positioning and hedging demand in Indian index and rupee options"),
        payer="INR and India-exposed holders without options-flow state",
        constraint="option positioning reprices daily",
        licence="NSE terms of use: no automated collection, no storage without written permission",
        source_culture="IN/en", participant_structure=("institutional", "retail_heavy"),
        failure_mode_hypothesis="fails around expiry weeks when OI rolls mechanically",
        crowding_prior="medium",
        note="REFUSED by NSE terms (TERMS_EVIDENCE); a licensed NSE data feed is the only route"),
)

#: THE TERMS GATE, FAIL CLOSED. `confirmed` only where the licence is plainly open: government
#: open data under a stated open licence, CC/CC0 data, public statistics behind a documented API,
#: or a publisher's written "anyone may use this". Everything else is `to_confirm` until a human
#: reads the terms, and a `to_confirm` or `refused` source is NEVER fetched (BLOCKED_ON_TERMS).
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
    "kr_bok_card_spend": ("confirmed", "BOK ECOS documented Open API"),
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
    "in_dgi_iip_consumer": ("confirmed", "GODL-India: worldwide, royalty-free licence for "
                            "commercial and non-commercial use, with attribution; data.gov.in "
                            "documented OGD API (free key)"),
    "za_statssa_retail": ("confirmed", "Stats SA publication notice: users may apply or process "
                          "the data with Stats SA acknowledged; no sale without permission"),
    # ---- physical exhaust (P4), reviewed 2026-10-06
    "cn_mot_port_monthly": ("to_confirm", "MOT disclaimer bars commercial verbatim reprint and "
                            "claims copyright; it grants no reuse licence"),
    "cn_sse_scfi_routes": ("to_confirm", "Shanghai Shipping Exchange: 'All Rights Reserved', no "
                           "terms or reuse page"),
    "us_bls_deepsea_freight": ("confirmed", "BLS public domain ('free to use ... without specific "
                               "permission'), served by the FRED API with its notice"),
    "cn_nbs_industry_power": ("confirmed", "NBS terms of service (as cn_nbs_retail): download and "
                              "use of NBS's own statistics welcomed with attribution"),
    "cn_nbs_fai": ("confirmed", "NBS terms of service (as cn_nbs_retail)"),
    "cn_nbs_profits": ("confirmed", "NBS terms of service (as cn_nbs_retail)"),
    "cn_tianyancha_supply": ("to_confirm", "paid commercial API; no licence held"),
    "cn_samr_registrations": ("to_confirm", "SAMR and Credit China: no terms, copyright or reuse "
                              "page found"),
    "cn_ccgp_award_indices": ("to_confirm", "CCGP footer '中华人民共和国财政部 版权所有'; no "
                              "terms or reuse page, no robots.txt"),
    "cn_s5p_no2_clusters": ("confirmed", "Copernicus Sentinel data licence: free, full and open; "
                            "reproduction, distribution, adaptation allowed with attribution"),
    "kr_naver_datalab": ("to_confirm", "Naver Developers terms could not be read (site blocked "
                         "to the authoring fetcher); accepted at app registration on the box"),
    "in_nse_option_chain": ("refused", "NSE terms: systematic or automated data collection "
                            "prohibited; no storing or reproduction without written permission"),
}
TERMS_VALUES = ("confirmed", "to_confirm", "refused")

#: Evidence for the terms decisions reviewed on 2026-09-30 (the 13 former `to_confirm` sources).
#: terms_quote is verbatim from terms_url as fetched that day, or says the page could not be read.
#: robots is what robots.txt said for the source's host and path. See
#: /mnt/project-files/reports/asia_source_terms_2026-09-30.md.
_CHK = "2026-09-30"
#: e-Stat API terms (every e-Stat row): content follows the e-Stat terms of use (Art. 6) and a
#: service built on the API must show where it comes from (Art. 7), with the credit line below.
_ESTAT_API: dict[str, str] = {
    "api_terms_url": "https://www.e-stat.go.jp/api/agreement",
    "api_terms_quote": ("第６条 本機能が提供する情報（以下「コンテンツ」という。）の利用条件等は、"  # noqa: RUF001
                        "「政府統計の総合窓口（e-Stat）利用規約」に準じるものとします。 / 第７条 "  # noqa: RUF001
                        "利用者は、本機能を利用したサービスを提供する場合には、別途定める方法により、"
                        "本機能を利用している出所等を明示するものとします。"),
    "credit_url": "https://www.e-stat.go.jp/api/en/api-info/credit",
    "credit": ("このサービスは、政府統計総合窓口(e-Stat)のAPI機能を使用していますが、"
               "サービスの内容は国によって保証されたものではありません。 / This service uses API "
               "functions from e-Stat, however its contents are not guaranteed by government."),
}
_IMF_EV: dict[str, str] = {
    "terms_url": "https://www.imf.org/external/terms.htm",
    "terms_quote": ("Users may download, extract, copy, create derivative works, publish, "
                    "distribute, and sell Data obtained from IMF Sites, including for commercial "
                    "purposes"),
    "policy_url": "https://portwatch.imf.org/pages/data-and-methodology",
    "policy_quote": ("All data and content in the IMF PortWatch are provided by the IMF unless "
                     "mentioned otherwise."),
    "judgement": ("PortWatch points to the IMF terms for copyright and usage; the live terms "
                  "read 2026-09-30 grant commercial reuse (an older copy asked commercial users "
                  "to email copyright@imf.org). Attribution required"),
    "robots": "services9.arcgis.com FeatureServer is PortWatch's documented ArcGIS API",
    "credit": "Source: International Monetary Fund (IMF PortWatch).",
    "checked_at": _CHK,
}
_OI_EV: dict[str, str] = {
    "terms_url": "https://github.com/opportunityinsights/economictracker",
    "terms_quote": ("Anyone is welcome to use this data; we simply we ask that you: 1. List the "
                    "name of the data provider(s) for the particular series you use. 2. "
                    "Attribute our work by citing or linking to the accompanying paper and the "
                    "Economic Tracker at https://tracktherecovery.org."),
    "robots": "raw.githubusercontent.com serves the repository CSVs",
    "credit": ("Opportunity Insights Economic Tracker (Chetty, Friedman, Stepner and the OI "
               "Team), https://tracktherecovery.org"),
    "checked_at": _CHK,
}
_CHK2 = "2026-10-06"
#: The NBS evidence every NBS row shares (the retail row's, re-read for the same site).
_NBS_EV: dict[str, str] = {
    "terms_url": "https://www.stats.gov.cn/wzgl/202302/t20230217_1912857.html",
    "terms_quote": "用户可以在本网站下载和使用国家统计局发布的统计数据",
    "judgement": ("the same NBS terms as cn_nbs_retail (exclusions a-f re-read 2026-09-30): the "
                  "industrial-production, energy, investment, profit and PMI releases are NBS's "
                  "own signed public statistics"),
    "robots": "www.stats.gov.cn/robots.txt 404 (no rules)",
    "credit": "数据来源：国家统计局 (Source: National Bureau of Statistics of China)"}  # noqa: RUF001
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
        **_ESTAT_API,
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
    "in_dgi_iip_consumer": {
        "terms_url": "https://smartcities.data.gov.in/government-open-data-license-india",
        "terms_quote": ("all users are provided a worldwide, royalty-free, non-exclusive license "
                        "to use, adapt, publish (either in original, or in adapted and/or "
                        "derivative forms), translate, display, add value, and create derivative "
                        "works (including products and services), for all lawful commercial and "
                        "non-commercial purposes"),
        "mirror_url": ("https://en.wikisource.org/wiki/Page:Government_Open_Data_License_"
                       "(India).pdf/5"),
        "attribution_quote": ("The user must acknowledge the provider, source, and license of "
                              "data by explicitly publishing the attribution statement"),
        "release_url": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2256241&reg=3&lang=2",
        "judgement": ("robots.txt refusing WebFetch's crawler on www.data.gov.in is a crawler "
                      "rule, not a licence term; GODL's text grants commercial reuse with "
                      "attribution, and api.data.gov.in with DATA_GOV_IN_KEY is the portal's "
                      "documented programmatic route. Only personal information is exempted"),
        "robots": ("www.data.gov.in pages robots-disallowed to the authoring fetcher; "
                   "api.data.gov.in is the documented keyed API"),
        "credit": ("Ministry of Statistics and Programme Implementation, Index of Industrial "
                   "Production (use-based), data.gov.in. Published under the Government Open "
                   "Data License - India: https://data.gov.in/government-open-data-license-india"),
        "checked_at": _CHK},
    "za_statssa_retail": {
        "terms_url": ("https://nationalgovernment.co.za/department_annual/531/2024-statistics-"
                      "south-africa-(stats-sa)-annual-report.pdf"),
        "terms_quote": ("Users may apply or process this data, provided Statistics South Africa "
                        "(Stats SA) is acknowledged as the original source of the data; that it "
                        "is specified that the application and/or analysis is the result of the "
                        "user's independent processing of the data; and that neither the basic "
                        "data nor any reprocessed version or application thereof may be sold or "
                        "offered for sale in any form whatsoever without prior permission from "
                        "Stats SA."),
        "judgement": ("Stats SA's standard imprint notice, read from a mirror of its 2023/24 "
                      "Annual Report because statssa.gov.za serves an Incapsula check to "
                      "fetchers; the same notice is printed in its statistical releases. The "
                      "desk applies and processes the data for its own trading research and "
                      "never sells it: allowed, with the acknowledgement below"),
        "robots": "statssa.gov.za serves an Incapsula challenge to fetchers (not a robots rule)",
        "credit": ("Source: Statistics South Africa (Stats SA), P6242.1 Retail trade sales. The "
                   "analysis is the result of the user's independent processing of the data."),
        "checked_at": _CHK},
    # ---- every other confirmed source, verified 2026-09-30 (the evidence test covers all)
    "kr_exports_early": {
        "terms_url": "https://www.data.go.kr/data/15157901/openapi.do",
        "terms_quote": "이용허락범위 제한 없음",
        "judgement": ("Korea Customs Service's own licence on the national portal for its "
                      "10-day provisional trade statistics, the statistics its 1-10 / 1-20 day "
                      "press releases print; customs.go.kr's copyright page timed out"),
        "robots": "customs.go.kr copyright page timed out 2026-09-30 (not read)",
        "checked_at": _CHK},
    "us_tsa_throughput": {
        "terms_url": "https://catalog.data.gov/dataset/covid-19-passenger-throughput",
        "terms_quote": "License: https://www.usa.gov/government-works",
        "robots": "catalog.data.gov lists the TSA checkpoint series as access level 'public'",
        "checked_at": _CHK},
    "us_census_marts_ex_autos": {
        "terms_url": "https://www.census.gov/data/developers/about/terms-of-service.html",
        "terms_quote": ("You may use the Census Bureau API to develop a service or service to "
                        "search, display, analyze, retrieve, view and otherwise 'get' information "
                        "from Census Bureau data."),
        "robots": "api.census.gov is the documented public API",
        "credit": ("This product uses the Census Bureau Data API but is not endorsed or "
                   "certified by the Census Bureau."),
        "checked_at": _CHK},
    "jp_tokyo_cpi": {
        "terms_url": "https://www.e-stat.go.jp/terms-of-use",
        "terms_quote": ("複製、公衆送信、翻訳・変形等の翻案等、自由に利用できます / "
                        "本利用ルールはクリエイティブ・コモンズ・ライセンスの表示 4.0 国際"
                        "...と互換性があり"),
        **_ESTAT_API,
        "robots": "api.e-stat.go.jp is the documented API (free appId)",
        "checked_at": _CHK},
    "cn_firms_industrial": {
        "terms_url": ("https://earthdata.nasa.gov/learn/articles/nasa-earth-science-data-yours-"
                      "use-fully-and-without-restrictions"),
        "terms_quote": ("NASA's data policy ensures that all NASA data are available fully, "
                        "openly, and without restrictions."),
        "robots": "firms.modaps.eosdis.nasa.gov/api is the documented keyed API (MAP_KEY)",
        "checked_at": _CHK},
    "imf_portwatch_ports": {**_IMF_EV},
    "imf_portwatch_chokepoints": {**_IMF_EV},
    "in_gold_imports": {
        "terms_url": "https://www.pib.gov.in/content/102_2_Copyright-Policy.aspx?reg=3&lang=1",
        "terms_quote": ("Material featured on this website may be reproduced free of charge and "
                        "there is no need for any prior approval for using the content. [...] "
                        "Wherever the material is being published or issued to others, the "
                        "source must be prominently acknowledged."),
        "robots": "pib.gov.in press-release pages fetched",
        "credit": "Source: Press Information Bureau, Government of India (pib.gov.in)",
        "checked_at": _CHK},
    "gdelt_events_country": {
        "terms_url": "https://gdeltproject.org/about.html",
        "terms_quote": ("all datasets released by the GDELT Project are available for unlimited "
                        "and unrestricted use for any academic, commercial, or governmental use "
                        "of any kind without fee."),
        "robots": "data.gdeltproject.org is the documented raw-file host",
        "credit": "The GDELT Project, https://www.gdeltproject.org/",
        "checked_at": _CHK},
    "wiki_asia_attention": {
        "terms_url": "https://dumps.wikimedia.org/other/pageviews/readme.html",
        "terms_quote": ("All Analytics datasets are available under the Creative Commons CC0 "
                        "dedication."),
        "robots": "wikimedia.org/api/rest_v1 is the documented pageviews API",
        "checked_at": _CHK},
    "us_oi_card_spend": {**_OI_EV},
    "us_oi_google_mobility": {**_OI_EV},
    "kr_bok_card_spend": {
        "terms_url": "https://www.data.go.kr/data/15059638/openapi.do?recommendDataYn=Y",
        "terms_quote": "이용허락범위: 이용허락범위 제한 없음",
        "judgement": ("the Bank of Korea's own licence on the national portal for its ECOS "
                      "statistics (a LINK-type entry to the ECOS API); ecos.bok.or.kr/api/ "
                      "returned 404 to the fetcher"),
        "robots": "ecos.bok.or.kr/api is the documented Open API (free key)",
        "checked_at": _CHK},
    "jp_meti_retail": {
        "terms_url": "https://www.meti.go.jp/main/rules.html",
        "terms_quote": ("経済産業省ウェブサイトで掲載・発信している情報の著作権は、特記されて"
                        "いない限り経済産業省に帰属し、権利表記の記載がない限り"
                        "『公共データ利用規約（第1.0版）』（PDL1.0）に準拠した利用条件の下で、"  # noqa: RUF001
                        "利用することができます。"),
        "robots": "meti.go.jp statistics pages fetched",
        "credit": "出典：『商業動態統計』（経済産業省）",  # noqa: RUF001
        "checked_at": _CHK},
    "kr_kobis_box_office": {
        "terms_url": "https://www.data.go.kr/data/3070263/openapi.do?recommendDataYn=Y",
        "terms_quote": "이용허락범위 제한 없음",
        "judgement": ("the Korean Film Council's own licence on the national portal for its "
                      "box-office DB, the data the KOBIS open API serves"),
        "robots": "kobis.or.kr/kobisopenapi is the documented Open API (free key)",
        "checked_at": _CHK},
    "kr_seoul_subway": {
        "terms_url": "https://data.seoul.go.kr/dataList/OA-12914/S/1/datasetView.do",
        "terms_quote": "공공누리 1유형 : 출처표시 (상업적 이용 및 변경 가능)",
        "robots": "openapi.seoul.go.kr is the documented Open API (free key)",
        "credit": "출처: 서울 열린데이터광장 (data.seoul.go.kr), 공공누리 제1유형",
        "checked_at": _CHK},
    # ---- physical exhaust (P4): read 2026-10-06 with the fetcher this session had
    "cn_mot_port_monthly": {
        "terms_url": "https://www.mot.gov.cn/wangzhangongneng/202512/t20251216_4181727.html",
        "terms_quote": ("任何媒体、互联网站和商业机构不得利用本网站发布的内容进行商业性的原版原式地"
                        "转载，也不得歪曲和篡改本网站所发布的内容。 / 本网站所涉及到的版权归本网站"  # noqa: RUF001
                        "所属"),
        "judgement": ("re-read 2026-10-06: the disclaimer claims copyright and bars commercial "
                      "verbatim reprint; it grants no reuse of the statistics. Stays to_confirm "
                      "(fail closed) until a human settles it; the parser is ready"),
        "robots": "www.mot.gov.cn/robots.txt 404 (no rules)",
        "checked_at": _CHK2},
    "cn_sse_scfi_routes": {
        "terms_url": "https://en.sse.net.cn/",
        "terms_quote": ("(© 2001-2026 Shanghai Shipping Exchange Institute(Prep.) All Rights "
                        "Reserved. -- no terms, disclaimer or reuse page linked)"),
        "robots": "the SCFI page is JS-rendered (querySCFI2); no robots rule read",
        "checked_at": _CHK2},
    "us_bls_deepsea_freight": {
        "terms_url": "https://www.bls.gov/opub/copyright-information.htm",
        "terms_quote": ("You are free to use our public domain material without specific "
                        "permission, although we do ask that you cite the Bureau of Labor "
                        "Statistics as the source."),
        "api_terms_url": "https://fred.stlouisfed.org/docs/api/terms_of_use.html",
        "api_terms_quote": ("Before using data series owned by third parties for anything other "
                            "than your own personal use, you must contact the data owner to "
                            "obtain permission."),
        "judgement": ("the data owner is BLS, whose copyright page grants use without specific "
                      "permission; FRED is the transport and its notice is carried. api.bls.gov "
                      "itself is robots-disallowed to fetchers, so it is not used"),
        "robots": "api.stlouisfed.org is the documented FRED API (free key)",
        "credit": ("Source: U.S. Bureau of Labor Statistics, PPI Deep Sea Freight Transportation "
                   "(PCU483111483111), via FRED. This product uses the FRED® API but is not "
                   "endorsed or certified by the Federal Reserve Bank of St. Louis."),
        "checked_at": _CHK2},
    "cn_samr_registrations": {
        "terms_url": "https://www.samr.gov.cn/",
        "terms_quote": ("(not found: no copyright, terms or disclaimer statement in the served "
                        "home pages of samr.gov.cn or creditchina.gov.cn)"),
        "robots": "home pages fetched 2026-10-06; no rule read",
        "checked_at": _CHK2},
    "cn_ccgp_award_indices": {
        "terms_url": "http://www.ccgp.gov.cn/",
        "terms_quote": "© 1999-2025 中华人民共和国财政部 版权所有 (no terms or reuse page linked)",
        "robots": ("www.ccgp.gov.cn/robots.txt 404; search.ccgp.gov.cn answered "
                   "'您的访问过于频繁,请稍后再试。' (rate limit) to one request"),
        "checked_at": _CHK2},
    "cn_s5p_no2_clusters": {
        "terms_url": "https://dataspace.copernicus.eu/terms-and-conditions",
        "terms_quote": ("The access and use of Copernicus Sentinel data is available on a free, "
                        "full and open basis through the Copernicus Data Space Ecosystem"),
        "licence_url": "https://ads.atmosphere.copernicus.eu/licences/ec-sentinel",
        "licence_quote": ("reproduction; distribution; communication to the public; adaptation, "
                          "modification and combination with other data and information"),
        "robots": "sh.dataspace.copernicus.eu is the documented Sentinel Hub API (CDSE account)",
        "credit": "Contains modified Copernicus Sentinel data [year]",
        "checked_at": _CHK2},
    "kr_naver_datalab": {
        "terms_url": "https://developers.naver.com/products/terms/",
        "terms_quote": ("(not readable: developers.naver.com was blocked to the authoring "
                        "fetcher on 2026-10-06)"),
        "robots": "not read",
        "checked_at": _CHK2},
    "in_nse_option_chain": {
        "terms_url": "https://www.nseindia.com/static/nse-terms-of-use",
        "terms_quote": ("User is prohibited to conduct any systematic or automated data "
                        "collection activities (including scraping, data mining, data extraction "
                        "and data harvesting) on or in relation to our Website / Mobile "
                        "Application."),
        "robots": "not needed: the terms refuse automated collection outright",
        "checked_at": _CHK2},
    "cn_tianyancha_supply": {
        "terms_url": "https://open.tianyancha.com/",
        "terms_quote": "(paid commercial API: a licence contract is the terms; none held)",
        "robots": "not fetched",
        "checked_at": _CHK2},
    **{sid: {**_NBS_EV, "checked_at": _CHK2}
       for sid in ("cn_nbs_industry_power", "cn_nbs_fai", "cn_nbs_profits")},
    "sg_port_throughput": {
        "terms_url": "https://singstat.gov.sg/our-services-tools-surveys/singstat-mobile-app/tou",
        "terms_quote": ("Use of Datasets provided in this application is subject to the terms "
                        "of the Singapore Open Data Licence on the use of statistical data from "
                        "this Website (\"ODL\")."),
        "licence_url": "https://data.gov.sg/open-data-licence",
        "licence_quote": ("You can use, access, download, copy, distribute, transmit, modify and "
                          "adapt the datasets, or any derived analyses or applications, whether "
                          "commercially or non-commercially."),
        "robots": "tablebuilder.singstat.gov.sg/api is the documented Table Builder API",
        "checked_at": _CHK},
}

SOURCES = tuple(replace(s, terms=TERMS.get(s.id, ("to_confirm", ""))[0])
                for s in (*SOURCES, *SUBSTITUTE_SOURCES, *PHYSICAL_SOURCES))
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
    "in_npci_upi": ("in_dgi_iip_consumer",),
    "za_beti": ("za_statssa_retail",),
    "cn_holiday_spend": ("cn_nbs_retail", "hk_immd_passenger"),
    "tr_bkm_card": ("tr_tuik_retail",),
    "br_cielo_icva": ("br_bcb_payments",),
    "mx_antad_sss": ("mx_inegi_emec",),
    "cn_maoyan_box_office": ("hk_immd_passenger",),
    "cn_sge_premium": ("in_gold_imports",),
    "cn_baidu_migration": ("hk_immd_passenger",),
    "kr_busan_port": ("kr_mof_container_teu", "imf_portwatch_ports"),
    "cn_mot_port_weekly": ("imf_portwatch_ports",),
    "cn_mot_port_monthly": ("imf_portwatch_ports",),
    "cn_sse_scfi_routes": ("us_bls_deepsea_freight", "imf_portwatch_chokepoints"),
    "cn_ccgp_award_indices": ("cn_nbs_fai",),
    "cn_tianyancha_supply": ("cn_nbs_profits",),
    "cn_samr_registrations": ("cn_nbs_profits",),
    "kr_naver_datalab": ("wiki_asia_attention",),
}
#: Blocked sources with NO verified lawful substitute, and why (each has a box action queued in
#: /mnt/project-files/patches/DESKTOP_PASS2_STATUS.md).
NO_SUBSTITUTE: dict[str, str] = {
    "in_nse_option_chain": ("no public options-positioning series for India carries reuse terms: "
                            "NSE refuses automated collection and storage; a licensed NSE data "
                            "feed is the route, a principal decision (2026-10-06)")}
#: Paid vendors barred by the public/licensed-only rule (no licence held). They live as rows of
#: asia_sources.json (`paid_blocked: true`), which asia_collector never fetches; they are listed
#: here so the paid-substitute engine rows name them. Nothing in this organ fetches them.
PAID_BLOCKED: dict[str, dict[str, str]] = {
    "rqdata": {"name": "RQData / RiceQuant", "class": "exchange market data (CN futures, ticks)",
               "status": "PAID_BLOCKED",
               "why": ("paid subscription, no licence held; the exchanges' own public files "
                       "(free_stack SHFE/DCE/CZCE/INE fetchers) are the lawful route")},
    "wind": {"name": "Wind API", "class": "institutional China data terminal",
             "status": "PAID_BLOCKED",
             "why": ("paid subscription, no licence held; NBS/SAFE/CFETS official releases (this "
                     "organ and asia_parser) are the lawful route")}}
#: How the last two gaps (NPCI UPI, BETI) were closed on 2026-09-30: every candidate searched, its
#: URL and why it was taken or rejected. Kept as the closing evidence (report: /mnt/project-files/
#: reports/asia_source_terms_2026-09-30.md).
SUBSTITUTE_SEARCH: dict[str, tuple[tuple[str, str, str], ...]] = {
    "cn_sse_scfi_routes": (
        ("BLS PPI deep sea freight (FRED)", "https://www.bls.gov/opub/copyright-information.htm",
         "TAKEN: public domain; national aggregate, so route granularity is lost"),
        ("Drewry World Container Index", "https://www.drewry.co.uk/supply-chain-advisors/supply-"
         "chain-expertise/world-container-index-assessed-by-drewry", "rejected: no use statement "
         "on the WCI page and drewry.co.uk terms are robots-disallowed to fetchers (unread)"),
        ("Freightos Baltic Index (FBX)", "https://www.balticexchange.com/en/news-and-events/news/"
         "member-news/2018/freightos-balticglobalcontainerindexnowavailable.html", "rejected: "
         "distributed under Baltic Exchange / Barchart data licences; freightos.com terms 404"),
        ("IMF PortWatch chokepoint transits", "https://www.imf.org/external/terms.htm",
         "TAKEN: route-level volume (transits per chokepoint), not rates"),
    ),
    "cn_tianyancha_supply": (
        ("NBS industrial profits by sector", "https://www.stats.gov.cn/wzgl/202302/"
         "t20230217_1912857.html", "TAKEN: sector-level corporate activity, NBS terms"),
        ("CNINFO announcements", "https://www.cninfo.com.cn/new/index", "rejected: '深圳证券信息"
         "有限公司 版权所有' and a liability disclaimer; no reuse grant"),
        ("SAMR / Credit China registrations", "https://www.samr.gov.cn/", "rejected: no terms "
         "page found on either site"),
    ),
    "in_npci_upi": (
        ("data.gov.in use-based IIP (GODL)", "https://smartcities.data.gov.in/government-open-"
         "data-license-india", "TAKEN: GODL text read on a data.gov.in property and on the "
         "Wikisource copy of the Gazette PDF; api.data.gov.in is the documented keyed API"),
        ("data.gov.in UPI tables", "https://www.data.gov.in/resource/year-wise-details-digital-"
         "payments-transactions-including-transactions-through-unified", "rejected: annual "
         "Parliament-answer tables, not a monthly flow"),
        ("RBI payment-system indicators", "https://www.rbi.org.in/", "rejected: '(c) Reserve "
         "Bank of India. All Rights Reserved', no reuse grant"),
        ("MoSPI eSankhyiki API", "https://github.com/nso-india/esankhyiki-mcp", "not used: the "
         "MIT licence covers the MCP code only; no data licence text found and the portal was "
         "unreachable (proxy 403 / fetch not permitted)"),
        ("PIB IIP quick-estimate releases", "https://www.pib.gov.in/content/102_2_Copyright-"
         "Policy.aspx?reg=3&lang=1", "confirmed reusable (PIB copyright policy) and used as the "
         "release calendar; the OGD API is the machine route"),
        ("dataful.in / Kaggle UPI copies", "https://dataful.in/datasets/432/", "rejected: "
         "republished NPCI/RBI data; a mirror cannot grant rights NPCI did not"),
    ),
    "za_beti": (
        ("Stats SA P6242.1 retail trade sales", "https://nationalgovernment.co.za/department_"
         "annual/531/2024-statistics-south-africa-(stats-sa)-annual-report.pdf", "TAKEN: Stats "
         "SA's own publication notice (mirrored; statssa.gov.za is behind Incapsula) lets users "
         "apply or process the data with acknowledgement, no sale"),
        ("SARB statistics", "https://www.resbank.co.za/", "rejected: IP 'cannot be used without "
         "written permission'"),
        ("PayInc/BankservAfrica BETI", "https://www.payinc.co.za/", "rejected: JS-only site, no "
         "terms readable"),
    ),
}
#: The paid-substitute engine (#152) reads Asia-thread rows from
#: data/paid_data_substitutes_*.json; this is that file (regenerate with --write-rosters).
ENGINE_ROWS_FILE = DESK / "data" / "paid_data_substitutes_asia_blocked.json"
ROSTER_FILE = DESK / "data" / "source_rosters" / "asia_paid_substitutes_consumer.yaml"


#: Documented defaults for config ids, each read off the provider's own catalogue on 2026-10-06
#: and cited next to it. The env var of the same name still overrides. An id that could not be
#: verified from an official page has NO entry here and its row stays UNCONFIGURED.
CONFIG_DEFAULTS: dict[str, str] = {
    # BOK ECOS table 601Y003 "7.5.1. 신용카드" (monthly 200301-202606 when read), item 201010
    # "개인 일반구매 이용금액" (personal general-purchase spend, 백만원): household card spend,
    # excluding cash advances. Read from the ECOS Open API's own item catalogue:
    #   https://ecos.bok.or.kr/api/StatisticItemList/sample/json/kr/21/30/601Y003
    # and served by https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/1/3/601Y003/M/
    # 202601/202601/201010 (three rows a month: ITEM_CODE2 00 합계, 10 은행계, 20 비은행계;
    # parse_ecos keeps 00). The older 601Y002 (by region) ENDS 202308, so it is not used.
    "ALT_ECOS_CARD_STAT": "601Y003",
    "ALT_ECOS_CARD_ITEM": "201010",
    # e-Stat statsDataId 0003449066, 出入国管理統計 "国籍・地域別 入国外国人の在留資格" (monthly,
    # 2020-06..2026-07 when read; cat01 has the single item 入国外国人, cat02 国籍・地域 with
    # 総数, cat03 在留資格 with 総数): https://www.e-stat.go.jp/dbview?sid=0003449066
    # ALT_ESTAT_IMMIG_CAT01 has NO default: the official dbview page names the cat01 item but
    # does not print its code, and the code is not guessed. Read it on the box with getMetaInfo
    # (appId + statsDataId=0003449066) and set the env var. Note for whoever does: the full
    # table is ~209 x 41 x 70 cells, above getStatsData's 100,000-row page, so the request should
    # also pin cat02/cat03 to their 総数 codes (from the same getMetaInfo reply).
    "ALT_ESTAT_IMMIG_STATS_ID": "0003449066",
    # ALT_INEGI_EMEC_ID has NO default: the BIE indicator id of the EMEC retail revenue index
    # (serie original) is not printed on any INEGI page reachable without a token (the BIE web
    # app at https://www.inegi.org.mx/app/indicadores/ is a JS shell and the EMEC programme page
    # https://www.inegi.org.mx/programas/emec/2018/ carries no series keys). Read it from the
    # BIE catalogue on the box (CL_INDICATOR with INEGI_TOKEN) and set the env var.
}


def config_value(name: str, environ: Any = None) -> str:
    """The env override if set, else the documented default, else ''."""
    env: Any = os.environ if environ is None else environ
    return str(env.get(name) or "").strip() or CONFIG_DEFAULTS.get(name, "")


def status_of(src: Source, environ: dict[str, str] | None = None) -> str:
    """One named state per source. Nothing here claims live yield: a source that has not returned
    real data on the box is UNMEASURED_LIVE_YIELD, and the pass report says what it parsed.
    `environ` replaces os.environ (the committed roster uses {} -- its status as declared)."""
    env: Any = os.environ if environ is None else environ
    if src.archive_until:
        return f"DEAD:{src.archive_until}"
    if src.paid_licence and not (src.key_env and env.get(src.key_env)):
        subs = SUBSTITUTED_BY.get(src.id)
        return (f"UNCONFIGURED+SUBSTITUTE:{','.join(subs)}" if subs
                else f"UNCONFIGURED:{src.key_env}")
    if src.terms != "confirmed":
        subs = SUBSTITUTED_BY.get(src.id)
        return (f"BLOCKED+SUBSTITUTE:{','.join(subs)}" if subs
                else f"BLOCKED_ON_TERMS:{src.terms}")
    for k in (src.key_env, *src.key_also) if src.key_env else ():
        if not env.get(k) and not (k == src.key_env and _alt_key_ready(src, env)):
            return f"BLOCKED_ON_KEY:{k}"
    missing = [e for e in src.config_env if not config_value(e, env)]
    if missing:
        return "UNCONFIGURED:" + ",".join(missing)
    return "UNMEASURED_LIVE_YIELD"


def _token_helper() -> Any:
    """`libs.ops.token_refresh.get_token` when that module is on this tree (PR #218), else None.
    TODO(#218): once merged, drop the env fallback in `source_key` and this guard."""
    try:
        import importlib
        return importlib.import_module("libs.ops.token_refresh").get_token
    except Exception:
        return None


def _alt_key_ready(src: Source, env: Any) -> bool:
    """A long-lived credential group stands in for a short-lived token ONLY when the helper that
    mints from it is present; otherwise the token itself is required."""
    return bool(src.key_alts and _token_helper() is not None
                and any(all(env.get(k) for k in grp) for grp in src.key_alts))


def source_key(src: Source) -> str:
    """The credential a request carries, from env only and never logged. CDSE_TOKEN goes through
    the token helper when it is merged (it refreshes from long-lived credentials); until then
    the pasted CDSE_TOKEN is read as before."""
    if not src.key_env:
        return ""
    helper = _token_helper() if src.key_alts else None
    if helper is not None:
        with contextlib.suppress(Exception):
            res = helper(src.key_env)
            if getattr(res, "ok", False) and getattr(res, "token", ""):
                return str(res.token)
    return os.environ.get(src.key_env, "")


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
    for k in (src.key_env, *src.key_also) if src.key_env else ():
        key = os.environ.get(k or "", "")
        if key:
            url = url.replace(key, f"<{k}>")
    return url


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
    #: A POST body (JSON) and its headers; credentials ride ONLY in headers, never in `url`.
    data: bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)


def http_send(req: Request) -> tuple[bytes, str]:
    """POST `req.data` with `req.headers` (the S5P statistics and Naver DataLab calls)."""
    r = urllib.request.Request(req.url, data=req.data, method="POST",
                               headers={"User-Agent": UA, "Accept": "application/json",
                                        "Content-Type": "application/json", **req.headers})
    with urllib.request.urlopen(r, timeout=TIMEOUT, context=_tls()) as resp:
        return resp.read(MAX_BYTES), str(resp.headers.get("Content-Type") or "")


def requests_for(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    """The requests one pass makes for a source. Paged and area sources expand here."""
    key = source_key(src)
    if src.id == "cn_firms_industrial":
        out: list[Request] = []
        end = (now - timedelta(days=1)).date()
        start = end - timedelta(days=9)
        for name, box in firms_areas().items():
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
            for name, box in firms_areas().items():
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
        if src.id == "imf_portwatch_ports":
            reqs += _portwatch_cn_requests(src, now, state)
        return reqs
    if src.id == "gdelt_events_country":
        return _gdelt_requests(src, now, state)
    if src.id == "cn_ccgp_award_indices":
        return _ccgp_requests(src, now, state)
    if src.id == "cn_s5p_no2_clusters":
        return _s5p_requests(src, key, now, state)
    if src.id == "kr_naver_datalab":
        return _naver_requests(src, now)
    if src.id in FOLLOW:
        return _list_requests(src, now, state)
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
    url = src.url.replace("{key}", key).replace("{yyyymm}", now.strftime("%Y%m"))
    for env in src.config_env:
        code = config_value(env)
        if not code:
            return []                  # never a request built on a placeholder code
        url = url.replace("{" + env + "}", urllib.parse.quote(code, safe=""))
    return [Request(url, Ctx(fetched_at=now))]


def firms_areas() -> dict[str, tuple[float, float, float, float]]:
    """FIRMS footprints: the five legacy boxes (their history keeps its names) plus every named
    facility in the cluster registry."""
    out = dict(FIRMS_CLUSTERS)
    for fid, f in load_clusters().items():
        out.setdefault(fid, f["bbox"])
    return out


#: China-wide PortWatch query: every Chinese port PortWatch publishes (ISO3 = 'CHN'), read from
#: a resumable date cursor so a pass re-reads the last 14 days (late AIS) plus what is new.
PORTWATCH_CN_PAGES = 40
PORTWATCH_CN_DEPTH_D = 800
#: Ports whose vessel-type split (container / dry bulk / tanker calls, import and export tonnes)
#: is kept; every other Chinese port keeps its total calls only (store size).
PORTWATCH_CN_MAJOR = frozenset({"shanghai", "ningbo_zhoushan", "qingdao", "tianjin", "dalian",
                                "guangzhou", "shenzhen", "rizhao", "tangshan", "xiamen",
                                "yingkou", "lianyungang", "qinhuangdao", "yantai", "zhanjiang"})


def _portwatch_cn_requests(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    cur = state.get("cn_since")
    floor = (now - timedelta(days=PORTWATCH_CN_DEPTH_D)).date()
    since = max(floor, date.fromisoformat(cur) - timedelta(days=14)) if cur else floor
    state["cn_since_next"] = (now - timedelta(days=1)).date().isoformat()
    reqs = []
    for k in range(PORTWATCH_CN_PAGES):
        q = urllib.parse.urlencode({
            "where": f"ISO3 = 'CHN' AND date >= timestamp '{since.isoformat()} 00:00:00'",
            "outFields": "*", "orderByFields": "date,portname",
            "resultOffset": k * 2000, "resultRecordCount": 2000, "f": "json"})
        reqs.append(Request(f"{src.url}?{q}", Ctx(part=f"cn_page{k * 2000}", fetched_at=now)))
    return reqs


CCGP_BACK_DEPTH_M = 36


def _months_back(d: date, n: int) -> date:
    y, m = d.year, d.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


def _ccgp_requests(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    """Last month and the one before it re-read (late postings are revisions), plus ONE older
    month per pass walking back from `back_to`, 36 months deep."""
    this = date(now.year, now.month, 1)
    months = [_months_back(this, 1), _months_back(this, 2)]
    cur = state.get("ccgp_back_to")
    nxt = date.fromisoformat(cur) if cur else _months_back(this, 3)
    if nxt >= _months_back(this, CCGP_BACK_DEPTH_M):
        months.append(nxt)
        state["ccgp_back_to_next"] = _months_back(nxt, 1).isoformat()
    out = []
    for m0 in months:
        end = _month_end(m0.year, m0.month)
        for basket, kws in CCGP_BASKETS.items():
            for kid, kw in kws:
                out.append(Request(src.url.format(kw=urllib.parse.quote(kw),
                                                  start=m0.strftime("%Y:%m:%d"),
                                                  end=end.strftime("%Y:%m:%d")),
                                   Ctx(part=f"{basket}:{kid}:{m0:%Y-%m}", fetched_at=now)))
    return out


S5P_TYPES = ("steel", "refining", "port", "copper", "aluminium", "coal")


def _s5p_requests(src: Source, key: str, now: datetime, state: dict[str, Any]) -> list[Request]:
    """One Statistical-API POST per facility over the last 10 days (OFFL lands within ~5), plus a
    30-day backfill window walking back from `s5p_back_to`, three years deep."""
    end = (now - timedelta(days=1)).date()
    windows = [(end - timedelta(days=9), end)]
    cur = state.get("s5p_back_to")
    bf_end = date.fromisoformat(cur) if cur else windows[0][0] - timedelta(days=1)
    if bf_end > (now - timedelta(days=3 * 365)).date():
        windows.append((bf_end - timedelta(days=29), bf_end))
        state["s5p_back_to_next"] = (bf_end - timedelta(days=30)).isoformat()
    out = []
    for fid, f in load_clusters().items():
        if not set(f["types"]) & set(S5P_TYPES):
            continue
        for a, b in windows:
            body = {"input": {"bounds": {"bbox": list(f["bbox"]), "properties": {
                        "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
                              "data": [{"type": "sentinel-5p-l2",
                                        "dataFilter": {"timeliness": "OFFL"}}]},
                    "aggregation": {"timeRange": {"from": f"{a.isoformat()}T00:00:00Z",
                                                  "to": f"{(b + timedelta(days=1)).isoformat()}"
                                                        "T00:00:00Z"},
                                    "aggregationInterval": {"of": "P1D"},
                                    "evalscript": S5P_EVALSCRIPT, "resx": 0.05, "resy": 0.05}}
            out.append(Request(src.url, Ctx(part=fid, start=a, end=b, fetched_at=now),
                               data=json.dumps(body).encode(),
                               headers={"Authorization": f"Bearer {key}"} if key else {}))
    return out


def _naver_requests(src: Source, now: datetime) -> list[Request]:
    """Weekly attention since 2016, the anchor group in every reply (<= 5 groups per call)."""
    cid = os.environ.get("NAVER_CLIENT_ID", "")
    sec = os.environ.get("NAVER_CLIENT_SECRET", "")
    out = []
    for k in range(0, len(NAVER_GROUPS), 4):
        groups = [NAVER_ANCHOR, *NAVER_GROUPS[k:k + 4]]
        body = {"startDate": "2016-01-04", "endDate": now.date().isoformat(), "timeUnit": "week",
                "keywordGroups": [{"groupName": g, "keywords": list(kw)} for g, kw in groups]}
        out.append(Request(src.url, Ctx(part=f"groups{k}", fetched_at=now),
                           data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                           headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}))
    return out


#: Release-list sources: the list page links each release; a link whose text carries one of these
#: words is followed (newest first, never twice). A followed page that parses to nothing has its
#: own links read once more (MOT: list -> notice -> .xlsx attachment).
FOLLOW: dict[str, tuple[str, ...]] = {
    "cn_nbs_industry_power": ("规模以上工业增加值", "能源生产情况", "采购经理指数"),
    "cn_nbs_fai": ("固定资产投资",),
    "cn_nbs_profits": ("工业企业利润",),
    "cn_mot_port_monthly": ("港口货物", "集装箱吞吐量", ".xlsx")}
FOLLOW_PER_PASS = 8
LIST_BACK_PAGES = 24
_HREF = re.compile(r"<a\s[^>]*href=[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.S | re.I)


def _list_requests(src: Source, now: datetime, state: dict[str, Any]) -> list[Request]:
    """The list page, plus ONE older list page per pass (index_<k>.html) walking back."""
    out = [Request(src.url, Ctx(part="list", fetched_at=now))]
    k = int(state.get("list_back") or 1)
    if src.url.endswith("/") and k <= LIST_BACK_PAGES:
        out.append(Request(f"{src.url}index_{k}.html", Ctx(part="list", fetched_at=now)))
        state["list_back_next"] = k + 1
    return out


def follow_links(src: Source, body: bytes, base: str, seen: Iterable[str]) -> list[str]:
    """Links on a list/notice page whose anchor text or target carries a FOLLOW word, absolute,
    unseen, in page order (lists are newest first)."""
    words = FOLLOW.get(src.id, ())
    done = set(seen)
    out: list[str] = []
    for href, txt in _HREF.findall(body.decode("utf-8", errors="replace")):
        label = _text(txt.encode()) + " " + href
        if not any(w in label for w in words):
            continue
        url = urllib.parse.urljoin(base, _html.unescape(href.strip()))
        if url.startswith(("http://", "https://")) and url not in done and url not in out:
            out.append(url)
    return out


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
        fac = factory_features(vals, periods, src.cadence)
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
                "surprise_z": None if z is None else round(z, 4),
                **fac[i],
                "value_last": r.get("value_last", r["value_first"]),
                "n_revisions": int(r.get("n_revisions") or 0)})
        out[name] = pts
    # FIRMS: a total across the declared footprints, per day, from the per-cluster counts.
    if src.id == "cn_firms_industrial":
        out.update(_firms_total(src, out))
    if src.id in AGGREGATES:
        out.update(AGGREGATES[src.id](src, out))
    return out


# ============================================================================ the factory
#: Same-period-a-year-earlier windows (days either side) per cadence, and the weekday fallback.
SEASONAL_TOL_D = {"daily": 3, "weekly": 4, "10-daily": 6, "monthly": 3, "event": 7}
SEASONAL_YEARS = 3
FACTORY_MIN_N = 8


def factory_features(vals: list[float], periods: list[date], cadence: str
                     ) -> list[dict[str, Any]]:
    """The alt-data factory's five objects per point, each from a STRICT PREFIX in availability
    order (index < i), so nothing is known before its own release:

      delta, acceleration   change on the prior released point, and the change of that change
      seasonal_expected     mean of the same period 1..3 years earlier (daily/weekly: 364-day
                            steps, weekday-aligned), else the same weekday over the prior 8 weeks
                            for daily data (`seasonal_basis` says which); None when neither exists
      raw_surprise          value - seasonal_expected
      seasonal_z            raw_surprise / sd of the prior raw surprises (>= 8 of them)
      percentile            rank of the value among all prior values (>= 8 of them)

    The REVISION object is not here: a revision is known only at its own revision_time, so it
    rides the sensor record (revision_delta, knowable_at = revision_time), never this row."""
    pos: dict[date, int] = {}
    for i, p in enumerate(periods):
        pos.setdefault(p, i)
    tol = SEASONAL_TOL_D.get(cadence, 3)
    step = 364 if cadence in ("daily", "weekly") else 365
    out: list[dict[str, Any]] = []
    raws: list[float] = []
    prev_delta: float | None = None
    for i, v in enumerate(vals):
        delta = v - vals[i - 1] if i >= 1 else None
        accel = delta - prev_delta if delta is not None and prev_delta is not None else None
        prev_delta = delta
        same: list[float] = []
        for k in range(1, SEASONAL_YEARS + 1):
            tgt = periods[i] - timedelta(days=step * k)
            if cadence == "monthly":
                y, m = periods[i].year - k, periods[i].month
                tgt = _month_end(y, m)
            for off in sorted(range(-tol, tol + 1), key=abs):
                j = pos.get(tgt + timedelta(days=off))
                if j is not None and j < i:
                    same.append(vals[j])
                    break
        basis = "same_period_prior_years" if same else None
        if not same and cadence == "daily":
            same = [vals[j] for k in range(1, 9)
                    if (j := pos.get(periods[i] - timedelta(days=7 * k))) is not None and j < i]
            basis = "same_weekday_8w" if len(same) >= 4 else None
            same = same if basis else []
        exp = _mean(same)
        raw = v - exp if exp is not None else None
        sd = _sd(raws) if len(raws) >= FACTORY_MIN_N else None
        sz = raw / sd if raw is not None and sd else None
        if raw is not None:
            raws.append(raw)
        prior = vals[:i]
        pct = ((sum(1 for x in prior if x <= v) / len(prior))
               if len(prior) >= FACTORY_MIN_N else None)
        out.append({"delta": None if delta is None else round(delta, 6),
                    "acceleration": None if accel is None else round(accel, 6),
                    "seasonal_expected": None if exp is None else round(exp, 6),
                    "seasonal_basis": basis,
                    "raw_surprise": None if raw is None else round(raw, 6),
                    "seasonal_z": None if sz is None else round(sz, 4),
                    "percentile": None if pct is None else round(pct, 4)})
    return out


def _synthetic(src: Source, rows: dict[str, dict[str, Any]], suffix: str = "_agg"
               ) -> dict[str, list[dict[str, Any]]]:
    """Feature points for derived series (the store shape build_points reads), built under a
    sub-source id so no aggregate recurses."""
    if not rows:
        return {}
    sub = Source(**{**src.__dict__, "id": src.id + suffix})
    return build_points(sub, rows)


def _row(series: str, d: str, v: float, members: list[dict[str, Any]]) -> dict[str, Any]:
    """A derived point is published when its LAST member is, and first seen when its last member
    was: never before any input it is made of."""
    pub = max(str(p["published_time"]) for p in members)
    seen = max(str(p.get("first_seen_at") or "") for p in members) or None
    basis = "page" if all(p.get("published_basis") == "page" for p in members) else "release_rule"
    return {"series": series, "period": d, "value_first": v, "value_last": v,
            "first_seen_at": seen, "published_time": pub, "published_basis": basis}


def breadth_rows(per: dict[str, list[dict[str, Any]]], members: list[str], name: str, *,
                 recent: int = 7, base: int = 90, min_share: float = 0.6
                 ) -> dict[str, dict[str, Any]]:
    """Facility / port BREADTH per day: the share of members whose mean over the last `recent`
    points is above their own mean over the `base` points before that (each member against its
    own history, so a big city never outweighs a small mill). A day is published only when at
    least `min_share` of the members have a reading; plus the mean anomaly (%) beside it."""
    anom: dict[str, dict[str, tuple[float, dict[str, Any]]]] = {}
    for m in members:
        pts = sorted(per.get(m) or [], key=lambda p: p["d"])
        vals = [float(p["value"]) for p in pts]
        for i, p in enumerate(pts):
            rec = vals[max(0, i - recent + 1): i + 1]
            bas = vals[max(0, i - recent + 1 - base): max(0, i - recent + 1)]
            mb = _mean(bas)
            if len(bas) >= 28 and mb:
                anom.setdefault(p["d"], {})[m] = ((_mean(rec) or 0.0) / mb - 1.0, p)
    out: dict[str, dict[str, Any]] = {}
    need = max(1, math.ceil(min_share * len(members)))
    for d, got in anom.items():
        if len(got) < need:
            continue
        xs = [a for a, _p in got.values()]
        ps = [p for _a, p in got.values()]
        out[f"{name}_breadth|{d}"] = _row(f"{name}_breadth", d,
                                          round(sum(x > 0 for x in xs) / len(xs), 4), ps)
        out[f"{name}_anomaly_pct|{d}"] = _row(f"{name}_anomaly_pct", d,
                                              round(100.0 * sum(xs) / len(xs), 4), ps)
    return out


def _agg_firms(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Thermal breadth over the named-facility registry (persistent detections only, so crop and
    wild fires do not count), by facility type and overall."""
    reg = load_clusters()
    rows: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[str]] = {"facility": list(reg)}
    for fid, f in reg.items():
        for t in f["types"]:
            groups.setdefault(t, []).append(fid)
    for g, ids in groups.items():
        if len(ids) >= 2:
            rows.update(breadth_rows(per, [f"{i}_persistent_count" for i in ids],
                                     f"{g}_thermal"))
    return _synthetic(src, rows)


def _agg_s5p(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """NO2 breadth by facility type and overall: the share of clusters above their own baseline."""
    reg = load_clusters()
    rows: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[str]] = {"all": [i for i, f in reg.items()
                                            if set(f["types"]) & set(S5P_TYPES)]}
    for fid, f in reg.items():
        for t in f["types"]:
            if t in S5P_TYPES:
                groups.setdefault(t, []).append(fid)
    for g, ids in groups.items():
        if len(ids) >= 2:
            rows.update(breadth_rows(per, [f"{i}_no2_umol" for i in ids], f"{g}_no2"))
    return _synthetic(src, rows)


def _agg_portwatch(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """China-wide port features from the per-port PortWatch panel: national calls (days on which
    at least 80% of the ports ever seen reported), north share and north-minus-south, container
    and dry-bulk shares of the major ports' calls and their gap, port breadth."""
    cn = {k[3:-len("_portcalls")]: v for k, v in per.items()
          if k.startswith("cn_") and k.endswith("_portcalls")}
    if not cn:
        return {}
    by_day: dict[str, dict[str, dict[str, Any]]] = {}
    for port, pts in cn.items():
        for p in pts:
            by_day.setdefault(p["d"], {})[port] = p
    need = math.ceil(0.8 * len(cn))
    rows: dict[str, dict[str, Any]] = {}
    for d, got in by_day.items():
        if len(got) < need:
            continue
        ps = list(got.values())
        tot = sum(float(p["value"]) for p in ps)
        rows[f"cn_total_portcalls|{d}"] = _row("cn_total_portcalls", d, tot, ps)
        nth = [float(p["value"]) for k, p in got.items() if k in CN_NORTH_PORTS]
        sth = [float(p["value"]) for k, p in got.items() if k in CN_SOUTH_PORTS]
        if nth and sth and tot > 0:
            rows[f"cn_north_share|{d}"] = _row("cn_north_share", d, round(sum(nth) / tot, 6), ps)
            rows[f"cn_north_minus_south_calls|{d}"] = _row(
                "cn_north_minus_south_calls", d, sum(nth) - sum(sth), ps)
    seg: dict[str, dict[str, float]] = {}
    seg_pts: dict[str, list[dict[str, Any]]] = {}
    for k, pts in per.items():
        for suf in ("calls_container", "calls_dry_bulk", "calls_tanker"):
            if k.startswith("cn_") and k.endswith("_" + suf):
                for p in pts:
                    seg.setdefault(p["d"], {}).setdefault(suf, 0.0)
                    seg[p["d"]][suf] += float(p["value"])
                    seg_pts.setdefault(p["d"], []).append(p)
    for d, sv in seg.items():
        t = sum(sv.values())
        if t > 0 and len(sv) == 3:
            c, b = sv["calls_container"] / t, sv["calls_dry_bulk"] / t
            rows[f"cn_container_share|{d}"] = _row("cn_container_share", d, round(c, 6),
                                                   seg_pts[d])
            rows[f"cn_bulk_minus_container_share|{d}"] = _row(
                "cn_bulk_minus_container_share", d, round(b - c, 6), seg_pts[d])
            rows[f"cn_tanker_share|{d}"] = _row("cn_tanker_share", d,
                                                round(sv["calls_tanker"] / t, 6), seg_pts[d])
    rows.update(breadth_rows(per, [f"cn_{p}_portcalls" for p in cn], "cn_port", min_share=0.8))
    return _synthetic(src, rows)


def _agg_ccgp(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Basket order indices: the month's award count summed over the basket's keywords (a month
    is published only when EVERY keyword was read), mean first-page provincial breadth, and the
    all-basket infrastructure order index."""
    rows: dict[str, dict[str, Any]] = {}
    months: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for basket, kws in CCGP_BASKETS.items():
        by: dict[str, list[dict[str, Any]]] = {}
        for kid, _kw in kws:
            for p in per.get(f"{basket}__{kid}_awards") or []:
                by.setdefault(p["d"], []).append(p)
        for d, ps in by.items():
            if len(ps) == len(kws):
                rows[f"{basket}_awards|{d}"] = _row(f"{basket}_awards", d,
                                                    sum(float(p["value"]) for p in ps), ps)
                months.setdefault(d, {})[basket] = ps
        for d in by:
            br = [p for kid, _kw in kws for p in per.get(f"{basket}__{kid}_provinces_p1") or []
                  if p["d"] == d]
            if len(br) == len(kws):
                rows[f"{basket}_provincial_breadth|{d}"] = _row(
                    f"{basket}_provincial_breadth", d,
                    round(sum(float(p["value"]) for p in br) / len(br) / len(CN_PROVINCES), 4),
                    br)
    for d, got in months.items():
        if len(got) == len(CCGP_BASKETS):
            ps = [p for v in got.values() for p in v]
            rows[f"all_order_index|{d}"] = _row("all_order_index", d,
                                                sum(float(p["value"]) for p in ps), ps)
    return _synthetic(src, rows)


def _agg_wiki(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """The lawful Baidu-basket substitute: breadth across the Chinese-language keyword articles
    (share above their own baseline) and the mean anomaly -- relative attention, never a level."""
    members = [f"{lab}_views" for lab, proj, _t in WIKI_ASIA_ARTICLES
               if proj == "zh.wikipedia" and lab.startswith("zh_kw_")]
    return _synthetic(src, breadth_rows(per, members, "zh_basket")) if len(members) >= 3 else {}


def _agg_nbs(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Power-PMI divergence: z(generation YoY) minus z(PMI - 50), each standardised over its own
    prior points only, on months where both printed."""
    pg = {p["d"]: p for p in per.get("power_gen_yoy") or []}
    pm = {p["d"]: p for p in per.get("mfg_pmi") or []}
    rows: dict[str, dict[str, Any]] = {}
    hist_a: list[float] = []
    hist_b: list[float] = []
    for d in sorted(set(pg) & set(pm)):
        a, b = float(pg[d]["value"]), float(pm[d]["value"]) - 50.0
        if len(hist_a) >= FACTORY_MIN_N:
            sa, sb = _sd(hist_a), _sd(hist_b)
            ma, mb = _mean(hist_a) or 0.0, _mean(hist_b) or 0.0
            if sa and sb:
                rows[f"power_pmi_divergence|{d}"] = _row(
                    "power_pmi_divergence", d, round((a - ma) / sa - (b - mb) / sb, 4),
                    [pg[d], pm[d]])
        hist_a.append(a)
        hist_b.append(b)
    return _synthetic(src, rows)


AGGREGATES: dict[str, Callable[[Source, dict[str, list[dict[str, Any]]]], dict[str, Any]]] = {
    "cn_firms_industrial": _agg_firms, "cn_s5p_no2_clusters": _agg_s5p,
    "imf_portwatch_ports": _agg_portwatch, "cn_ccgp_award_indices": _agg_ccgp,
    "wiki_asia_attention": _agg_wiki, "cn_nbs_industry_power": _agg_nbs}


def _firms_total(src: Source, per: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    ncl = len(FIRMS_CLUSTERS)
    legacy = {f"{c}_count" for c in FIRMS_CLUSTERS}
    days: dict[str, dict[str, Any]] = {}
    for name, pts in per.items():
        if name not in legacy:
            continue
        for p in pts:
            e = days.setdefault(p["d"], {"n": 0, "v": 0.0, "p": p})
            e["n"] += 1
            e["v"] += float(p["value"])
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
        for col in ("value", "pace", "surprise_z", "acceleration", "seasonal_z"):
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
            **({"credit": c} if (c := credit_of(src.id)) else {}),
            **({"vintage": src.vintage} if src.vintage else {}),
            "at": now.isoformat(timespec="seconds"), "region": src.region,
            "cadence": src.cadence, "n_series": len(series),
            "pit_fields": ["event_time", "published_time", "available_time", "first_seen_at",
                           "revision_time", "vintage_id"],
            "shape": ("series[<series>.<value|pace|surprise_z|acceleration|seasonal_z>].points, "
                      "joined on available_time"),
            "vintage_note": ("first value seen is the value; a revision is recorded with its own "
                             "revision_time and never back-dated"),
            "series": series}


#: The universal sensor contract (MANDATE 2026-10-06 §2.5), field for field. A field this organ
#: cannot know is None, never a stand-in: no consensus is held, so `consensus` is None and
#: `expected_value` is the run-rate expectation the surprise was measured against.
SENSOR_FIELDS: tuple[str, ...] = (
    "sensor_id", "source_id", "dataset_id", "observation_id", "entity", "geography",
    "asset_domain", "metric", "value", "unit", "event_time", "scheduled_time",
    "publication_time", "knowable_at", "received_at", "parse_complete_at", "expected_value",
    "consensus", "seasonal_expected", "raw_surprise", "surprise_z", "percentile", "delta",
    "acceleration", "revision_of", "revision_delta", "source_confidence",
    "measurement_uncertainty", "commercial_rights", "licence", "provenance_hash", "raw_pointer")
SENSOR_KEEP = 60


def sensor_records(src: Source, points: dict[str, list[dict[str, Any]]]
                   ) -> list[dict[str, Any]]:
    """Each point as a §2.5 observation (the newest SENSOR_KEEP per series; the full history is
    the vintage store and the lake CSV). A revision is its OWN observation (`revision_of` names
    the first, `revision_delta` = last - first, `knowable_at` = its revision_time), never a
    rewrite of the first value."""
    out: list[dict[str, Any]] = []
    rights = {"confirmed": "reuse_confirmed", "to_confirm": "unconfirmed",
              "refused": "refused"}.get(src.terms, "unconfirmed")
    for name, pts in sorted(points.items()):
        for p in pts[-SENSOR_KEEP:]:
            oid = f"{src.id}|{name}|{p['d']}"
            pace, sur = p.get("pace"), p.get("surprise")
            base = {
                "sensor_id": f"alt_proxies:{src.id}:{name}", "source_id": src.id,
                "dataset_id": lake_file(src, name), "observation_id": oid,
                "entity": name, "geography": src.region, "asset_domain": "macro_physical",
                "metric": name, "value": p["value"], "unit": None,
                "event_time": p["event_time"], "scheduled_time": None,
                "publication_time": p["published_time"], "knowable_at": p["available_time"],
                "received_at": p.get("first_seen_at"),
                "parse_complete_at": p.get("first_seen_at"),
                "expected_value": (None if pace is None or sur is None
                                   else round(float(pace) - float(sur), 6)),
                "consensus": None, "seasonal_expected": p.get("seasonal_expected"),
                "raw_surprise": p.get("raw_surprise"), "surprise_z": p.get("surprise_z"),
                "percentile": p.get("percentile"), "delta": p.get("delta"),
                "acceleration": p.get("acceleration"), "revision_of": None,
                "revision_delta": None,
                "source_confidence": ("page_stamp" if p.get("published_basis") == "page"
                                      else "release_rule"),
                "measurement_uncertainty": None, "commercial_rights": rights,
                "licence": src.licence, "provenance_hash": p.get("vintage_id"),
                "raw_pointer": f"data/lake/vault/alt_{src.id}/"}
            out.append(base)
            last = p.get("value_last")
            if p.get("revision_time") and last is not None and p.get("n_revisions"):
                out.append({**base, "observation_id": oid + "|rev", "value": last,
                            "revision_of": oid,
                            "revision_delta": round(float(last) - float(p["value"]), 6),
                            "knowable_at": p["revision_time"], "received_at": p["revision_time"],
                            "parse_complete_at": p["revision_time"]})
    return out


def credit_of(sid: str) -> str:
    """The attribution line a publisher's terms require wherever its data is published (the
    axis file, the roster rows), from TERMS_EVIDENCE; empty when the terms ask for none."""
    return TERMS_EVIDENCE.get(sid, {}).get("credit", "")


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
                            # the factory's objects (sensor-contract names), all PIT on the row
                            "knowable_at": p["available_time"], "received_at": p["retrieval_time"],
                            "delta": p.get("delta"), "acceleration": p.get("acceleration"),
                            "seasonal_expected": p.get("seasonal_expected"),
                            "raw_surprise": p.get("raw_surprise"),
                            "seasonal_z": p.get("seasonal_z"), "percentile": p.get("percentile")}
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
    cells: list[tuple[str, str, str, str]] = []
    for sid, per in points_by_source.items():
        src = BY_ID[sid]
        if is_dead(src):
            continue
        for series in src.signal_series:
            if per.get(series):
                for col in signal_columns(src):
                    cells.extend((sid, series, sym, col) for sym in src.instruments_for(series)
                                 if may_mint(sym))
    out: dict[str, dict[str, Any]] = {}
    closes: dict[str, Any] = {}
    for sid, series, sym, col in cells:
        if sym not in closes:
            closes[sym] = _bars_close(paths, sym)
        close = closes[sym]
        key = gain_key(sid, series, sym, col)
        if close is None:
            out[key] = {"verdict": UNMEASURED, "why": f"no {sym}_H1 bars on this box"}
            continue
        pts = points_by_source[sid][series]
        ev = [(p["available_time"], float(p[col])) for p in pts if p.get(col) is not None]
        res = release_gain(ev, close, horizon_bars=HORIZON_BARS, n_cells=len(cells)).as_dict()
        res["backfill_share"] = (round(sum(1 for p in pts if p["pit_quality"] == "backfill")
                                       / len(pts), 3) if pts else None)
        out[key] = res
    return out


#: Sources whose cells test the factory's seasonal surprise beside the run-rate surprise: the
#: physical-exhaust rows and the panels they extended. Each column is its own charged trial.
FACTORY_SIGNAL_SOURCES = frozenset({
    "cn_mot_port_monthly", "us_bls_deepsea_freight", "cn_nbs_industry_power", "cn_nbs_fai",
    "cn_nbs_profits", "cn_ccgp_award_indices", "cn_s5p_no2_clusters", "kr_naver_datalab",
    "cn_firms_industrial", "imf_portwatch_ports", "wiki_asia_attention", "cn_sse_scfi_routes"})


def signal_columns(src: Source) -> tuple[str, ...]:
    return ("surprise_z", "seasonal_z") if src.id in FACTORY_SIGNAL_SOURCES else ("surprise_z",)


def gain_key(sid: str, series: str, sym: str, col: str = "surprise_z") -> str:
    """`sid|series|sym` for the run-rate surprise (the historic key), `sid|series#col|sym` else."""
    return f"{sid}|{series}|{sym}" if col == "surprise_z" else f"{sid}|{series}#{col}|{sym}"


def direct_cells(gains: dict[str, dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """PASSING cells only, as `exogenous_conditioner` recipes the gauntlet rebuilds from the lake
    series itself. The side is the MEASURED sign of the IC, never the prior."""
    out: list[dict[str, Any]] = []
    for key, g in sorted(gains.items()):
        if g.get("verdict") != "PASS" or not g.get("ic"):
            continue
        sid, series_col, sym = key.split("|")
        series, _, col = series_col.partition("#")
        col = col or "surprise_z"
        src = BY_ID[sid]
        if is_dead(src) or not may_mint(sym):
            continue
        side = 1 if float(g["ic"]) > 0 else -1
        params = {"source": lake_file(src, series), "signal": col,
                  "transform": "level_z", "threshold": 1.0, "side_when_high": side,
                  "lag_hours": 24, "ttl_bars": HORIZON_BARS}
        out.append({
            "source": SOURCE, "kind": "hypothesis", "symbol": sym, "symbols": [sym],
            "family": "exogenous_conditioner", "params": params, "url": "",
            "cell": (f"{sym}.exogenous_conditioner.{lake_file(src, series)}"
                     + ("" if col == "surprise_z" else f".{col}")),
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
        for ext in ("html", "json", "csv", "txt", "xlsx"):
            p = fixtures / f"{name}.{ext}"
            if p.exists() and (i == 0 or name != src.id):
                return p.read_bytes()
    return None


def collect(paths: Paths, src: Source, state: dict[str, Any], now: datetime, *,
            fetch: bool, fixtures: Path | None, deadline: float,
            getter: Callable[[str], tuple[bytes, str]] = http_get,
            sender: Callable[[Request], tuple[bytes, str]] = http_send) -> dict[str, Any]:
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
    if src.paid_licence and status_of(src).startswith("UNCONFIGURED"):
        rec.update({"requests": 0, "why": "paid licence not held: never fetched",
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
    parsed = fetched = followed = 0
    errors: list[str] = []
    exhausted: set[str] = set()
    queue = list(reqs)
    seen = list(sst.get("followed") or [])
    i = 0
    while queue:
        req = queue.pop(0)
        if time.monotonic() > deadline:
            errors.append("budget reached: the remaining requests are owed to the next pass")
            break
        group = req.ctx.part.rstrip("0123456789").removesuffix("page")
        if src.id.startswith("imf_portwatch") and group in exhausted:
            continue
        body: bytes | None = None
        if fixtures is not None:
            body = _load_fixture(fixtures, src, req, i)
            i += 1
            if body is None:
                continue
        elif fetch:
            try:
                body, ctype = sender(req) if req.data is not None else getter(req.url)
                fetched += 1
                vault(paths, src, body, req.url, ctype, now)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {_redact(str(exc), src)[:120]}")
                if isinstance(exc, urllib.error.HTTPError):
                    exc.close()
                if req.ctx.part.startswith("follow") and req.url in seen:
                    seen.remove(req.url)                 # a failed release page is retried
                if src.id == "wiki_asia_attention" and getattr(exc, "code", None) == 404:
                    errors.pop()                         # an absent article is a fact, not a
                    rec.setdefault("missing", []).append(req.ctx.part)   # failed pass
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
            exhausted.add(group)                               # paging exhausted
        if group == "cn_" and obs:
            sst["cn_read"] = True
        if (src.id in FOLLOW and fixtures is None and not obs
                and req.ctx.part in ("list", "follow1")):
            for url in follow_links(src, body, req.url, seen)[:FOLLOW_PER_PASS - followed]:
                followed += 1
                seen.append(url)
                queue.append(Request(url, Ctx(part="follow1" if req.ctx.part == "list"
                                              else "follow2", fetched_at=now)))
    if not sst.pop("cn_read", False):
        sst.pop("cn_since_next", None)          # the China query read nothing: cursor holds
    if src.id in FOLLOW:
        sst["followed"] = seen[-400:]
        rec["followed"] = followed
    if src.id == "cn_firms_industrial" and "firms_backfill_to_next" in sst and not errors:
        sst["firms_backfill_to"] = sst.pop("firms_backfill_to_next")
    for k in ("backfill_to_next", "full_done_next", "cn_since_next", "ccgp_back_to_next",
              "s5p_back_to_next", "list_back_next"):
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
                _atomic(paths.sensor_dir / f"{src.id}.json",
                        {"contract": "MANDATE 2026-10-06 §2.5", "fields": list(SENSOR_FIELDS),
                         "at": now.isoformat(timespec="seconds"),
                         "records": sensor_records(src, pts)})
        rec["series"] = {k: len(v) for k, v in sorted(pts.items())}
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


#: Annual cost of a source in USD where a price is HELD. Every source this organ fetches is free
#: (0); a paid vendor with no quote held is UNMEASURED, never a guessed price.
ANNUAL_COST_USD: dict[str, Any] = {
    "cn_tianyancha_supply": UNMEASURED, "rqdata": UNMEASURED, "wind": UNMEASURED}


def rent_of(sid: str, n_axes: int, report: dict[str, Any] | None = None) -> dict[str, Any]:
    """The RENT row (audit row 51): annual cost, unique axes (signal series), cells tested and
    gain-test survivors from the last pass's report on THIS box, and cost per survivor. No
    report here -> cells and survivors are UNMEASURED (a verdict, not a zero)."""
    cost = ANNUAL_COST_USD.get(sid, 0)
    gains = (report or {}).get("gain_tests") or {}
    mine = {k: g for k, g in gains.items() if k.split("|", 1)[0] == sid}
    tested = sum(1 for g in mine.values() if (g or {}).get("verdict") in
                 ("PASS", "FAIL", "UNDERPOWERED"))
    passed = sum(1 for g in mine.values() if (g or {}).get("verdict") == "PASS")
    have = bool(report)
    per = (UNMEASURED if not have or not isinstance(cost, (int, float))
           else (None if not passed else round(float(cost) / passed, 2)))
    return {"annual_cost_usd": cost, "unique_axes": int(n_axes),
            "cells_tested": tested if have else UNMEASURED,
            "survivors": passed if have else UNMEASURED,
            "cost_per_survivor_usd": per,
            "rule": ("information per unit of rent: a paid source renews only on measured "
                     "survivors per dollar against its free substitutes")}


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
                     "status": status_of(s, environ), "terms": s.terms, **_meta(s),
                     "rent": rent_of(s.id, len(s.signal_series), _rent_report())})
        if credit_of(s.id):
            rows[-1]["credit"] = credit_of(s.id)
        if s.vintage:
            rows[-1]["vintage"] = s.vintage
        if s.id in SUBSTITUTED_BY:
            rows[-1]["substituted_by"] = list(SUBSTITUTED_BY[s.id])
        if s.substitutes_for:
            rows[-1].update({"substitutes_for": s.substitutes_for, "fetcher": "owned",
                             "owner": "asia_gap_thread"})
    return rows


def _rent_report() -> dict[str, Any] | None:
    """The last pass's report on this box, or None (the committed roster is written off-box, so
    its rent cells read UNMEASURED there)."""
    doc = _read_json(DEFAULT_PATHS.report, None)
    return doc if isinstance(doc, dict) and doc.get("gain_tests") is not None else None


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
            elif k == "rent":
                row[k] = {**v, "cells_tested": UNMEASURED, "survivors": UNMEASURED,
                          "cost_per_survivor_usd": UNMEASURED}     # committed: off-box
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
             _NEWS: "news", _TRAVEL: "foot traffic (travel arrivals)", _GOLD: "gold premium",
             _FREIGHT: "freight (route indices)", _CORP: "corporate supply chain",
             _PROC: "procurement awards", _SEARCH: "search attention"}
    blocked_class = {"jp_jnto_arrivals": _TRAVEL, "cn_sge_premium": _GOLD,
                     "cn_sse_scfi_routes": _FREIGHT, "cn_ccgp_award_indices": _PROC,
                     "cn_tianyancha_supply": _CORP, "cn_samr_registrations": _CORP,
                     "kr_naver_datalab": _SEARCH, "in_nse_option_chain": "options positioning"}
    rows: list[dict[str, Any]] = []
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
            "rent": rent_of(sid, len(src.signal_series)) | {
                "cells_tested": UNMEASURED, "survivors": UNMEASURED,
                "cost_per_survivor_usd": UNMEASURED},
        })
    for vid, v in sorted(PAID_BLOCKED.items()):
        rows.append({"class": v["class"], "paid": f"{v['name']} [{vid}]", "free": "",
                     "region": "CN", "measure": "", "frequency": "on demand",
                     "status": v["status"], "terms": "paid_blocked",
                     "blocked_because": v["why"], "unsubstituted_because": v["why"],
                     "evidence": "desks/mt5/data/asia_sources.json (paid_blocked: true)",
                     "rent": {"annual_cost_usd": ANNUAL_COST_USD.get(vid, UNMEASURED),
                              "unique_axes": 0, "cells_tested": UNMEASURED,
                              "survivors": UNMEASURED, "cost_per_survivor_usd": UNMEASURED}})
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
                         _TRAVEL: "foot_traffic", _GOLD: "commodities_physical",
                         _FREIGHT: "shipping_freight", _CORP: "corporate_activity",
                         _PROC: "procurement", _SEARCH: "search_attention"}.get(
                             s.substitutes_for, "macro")],
            "region": s.region, "frequency": s.cadence,
            "auth": "free_key" if s.key_env else "none", "auth_env": s.key_env or "",
            "languages": [s.language], "instruments": sorted(s.instruments),
            "participant_structure": s.participant_structure[0], "licence": s.licence,
            "terms": s.terms, "terms_quote": ev.get("terms_quote", ""),
            "credit": ev.get("credit", ""),
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
