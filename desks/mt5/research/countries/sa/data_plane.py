"""SAUDI DATA PLANE -- and THE MIDDLE EAST LANE BASE the UAE and Israeli planes build on.

WHY THE BASE LIVES HERE. Three Gulf/Levant planes share one store, one network door, one key
file and one report shape; `middle_east_interaction.default_series` already reads the point-in-time
store through `countries.sa.data_plane:read_series`. Putting the base in this file (and importing
it from `ae` and `il`) keeps ONE implementation of the point-in-time semantics rather than three.

WHAT A LANE IS. A lane is one institution's catalogue of datasets (`CatalogueRow`), a single
network door (`Guard`) that `no_fetch` turns into a FIXTURE READER over
`<fixtures>/<lane>/<dataset_id>.json` -- so the parse path the tests exercise is the live one --
and a parser into `Observation`s stamped with the instant they became KNOWABLE.

THE RULES A LANE MAY NOT BREAK:
  * An absent key makes a dataset UNMEASURED BY NAME, with the key path in the row and a discovery
    recorded that names it (L1.28a). An empty frame is indistinguishable from a barren ground.
  * No key VALUE ever leaves `read_keys`: rows, notes, errors and reports carry PRESENT/ABSENT.
  * The store is APPEND-ONLY. A flash and its final are two observations of one period, and
    `as_of` answers what was knowable at an instant, not what is true now.
  * A payload the parser cannot read is "shape unrecognised, not barren".
  * A state verdict carries its control; a short series is UNMEASURED, never NEUTRAL.

NETWORK OWNERSHIP. The hourly acquirer (`_declared_data_plane.ACQUISITION_OWNER`) is the desk's
network owner; every clock that calls `run()` here passes `no_fetch=True`, an explicit ownership
boundary published in every report (`no_fetch_is_owned`). Every URL in these catalogues is
DECLARED and `verified=False` until it has returned bytes on this box.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path
from typing import Any, ClassVar

from countries._declared_data_plane import ACQUISITION_OWNER, declared_lanes
from countries._declared_data_plane import report_path as _report_path
from countries._declared_data_plane import run as _declared_run

CODE = "sa"
DESK = Path(__file__).resolve().parents[3]
SECRETS_REL = "data/secrets/mena_apis.json"
SECRETS = DESK / SECRETS_REL
REPORT = _report_path(CODE)
#: the pack's declared dataset names, measured by the acquisition registry (`declared` section)
DECLARED = declared_lanes(CODE)

GENERATOR = "mena:data_plane"
UA = "quant-desk-research/1.0 (+official statistics reader)"
TIMEOUT_S = 20.0

#: point-in-time verdicts a catalogue row may carry
PIT_SAFE, NOT_PIT_SAFE, UNMEASURED = "PIT_SAFE", "NOT_PIT_SAFE", "UNMEASURED"
PIT_LABELS = (PIT_SAFE, NOT_PIT_SAFE, UNMEASURED)
#: access classes: a LICENSED product is catalogued so its absence is a decision, never fetched
PUBLIC, LICENSED = "PUBLIC", "LICENSED"
#: the ONLY key names `data/secrets/mena_apis.json` may hold for these lanes
KEY_NAMES: tuple[str, ...] = ("sama", "cbuae", "boi")
PRESENT, ABSENT = "PRESENT", "ABSENT"

#: a state needs this many periods; below it the verdict is UNMEASURED, never NEUTRAL
MIN_N = 12
#: the trailing window a level z-score is measured against
WINDOW = 52
Z_BAND = 0.5

OBS_FIELDS: tuple[str, ...] = ("series", "value", "period_time", "publication_time",
                               "available_time", "vintage", "vintage_id", "source_id")

RULE = ("Middle East official series are point-in-time SENSORS: every observation is stamped with "
        "the instant it became knowable, the store appends vintages and never overwrites, an "
        "absent key or an unreadable payload is UNMEASURED by name, and no key value ever "
        "leaves the secrets file")


# ------------------------------------------------------------------------------ clocks
def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _midnight(day: date) -> datetime:
    return datetime.combine(day, dtime(0, 0), tzinfo=UTC)


def _instant(stamp: str) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(stamp))
    except ValueError:
        return None
    return got if got.tzinfo is not None else got.replace(tzinfo=UTC)


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _cutoff(when: str | date | datetime) -> datetime | None:
    """The exclusive upper bound for `when`. A date-only `when` includes its whole day, exactly
    as `libs.research.vintage.as_of` reads it."""
    if isinstance(when, datetime):
        stamp = when if when.tzinfo is not None else when.replace(tzinfo=UTC)
        return stamp + timedelta(microseconds=1)
    if isinstance(when, date):
        return _midnight(when) + timedelta(days=1)
    text = str(when).strip()
    if len(text) == 10:
        try:
            return _midnight(date.fromisoformat(text)) + timedelta(days=1)
        except ValueError:
            return None
    got = _instant(text)
    return got + timedelta(microseconds=1) if got is not None else None


# ------------------------------------------------------------------------------ secrets
def read_keys(path: Path | None = None) -> dict[str, str]:
    """Key name -> value. The ONLY function that holds a value; `{}` when the file is absent."""
    try:
        doc = json.loads(Path(path or SECRETS).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, Mapping):
        return {}
    out: dict[str, str] = {}
    for name, value in doc.items():
        got = value.get("key") or value.get("api_key") if isinstance(value, Mapping) else value
        if isinstance(got, str) and got.strip():
            out[str(name)] = got.strip()
    return out


def key_status(source: Path | Mapping[str, str] | None = None) -> dict[str, str]:
    """PRESENT/ABSENT per declared key name. Never a value, never a prefix, never a length."""
    keys = dict(source) if isinstance(source, Mapping) else read_keys(source)
    return {name: PRESENT if str(keys.get(name) or "").strip() else ABSENT
            for name in KEY_NAMES}


def redact(text: Any, secrets: Iterable[str]) -> str:
    """Every occurrence of every secret value (raw or URL-quoted) replaced by `***`."""
    out = str(text)
    for secret in sorted({str(s) for s in secrets if s}, key=len, reverse=True):
        out = out.replace(secret, "***")
        quoted = urllib.parse.quote(secret, safe="")
        if quoted != secret:
            out = out.replace(quoted, "***")
    return out


# ------------------------------------------------------------------------------ the catalogue
@dataclass(frozen=True)
class CatalogueRow:
    """One dataset a lane knows about -- declared, licensed, and with a point-in-time verdict."""

    dataset_id: str
    institution: str
    coverage: str
    frequency: str
    revisions: str
    licence: str
    history_from: str
    how_to_fetch: str
    publication_lag_days: float
    pit_feasible: str = PIT_SAFE
    access: str = PUBLIC
    url: str = ""
    series: tuple[str, ...] = ()
    key_required: bool = False
    key_name: str = ""
    key_param: str = ""
    vintage: str = "final"
    #: series -> the SDMX key values that identify it; exact membership, never a substring
    aliases: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: earned by bytes on this box, never declared
    verified: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_REQUIRED_FIELDS = ("dataset_id", "institution", "coverage", "frequency", "revisions",
                    "licence", "history_from", "how_to_fetch")


def check_catalogue(rows: Sequence[CatalogueRow]) -> list[str]:
    """Every problem with a catalogue, by row. `[]` is the only passing answer."""
    problems: list[str] = []
    seen: set[str] = set()
    for row in rows:
        rid = row.dataset_id or "<unnamed>"
        if rid in seen:
            problems.append(f"{rid}: duplicate dataset_id")
        seen.add(rid)
        for name in _REQUIRED_FIELDS:
            if not str(getattr(row, name) or "").strip():
                problems.append(f"{rid}: {name} is empty")
        if row.pit_feasible not in PIT_LABELS:
            problems.append(f"{rid}: pit_feasible {row.pit_feasible!r} is not a verdict")
        if row.access not in (PUBLIC, LICENSED):
            problems.append(f"{rid}: access {row.access!r} is not an access class")
        lag = row.publication_lag_days
        if not (isinstance(lag, int | float) and math.isfinite(lag) and lag >= 0):
            problems.append(f"{rid}: publication_lag_days must be a finite non-negative number")
        if row.key_required and row.key_name not in KEY_NAMES:
            problems.append(f"{rid}: key_required names {row.key_name!r}, not a key the "
                            f"secrets file holds ({', '.join(KEY_NAMES)})")
        if row.access == LICENSED and (row.series or row.url):
            problems.append(f"{rid}: a licensed product may not declare series or a url")
        if row.verified:
            problems.append(f"{rid}: verified=True is earned by bytes on this box, not declared")
        if row.access == PUBLIC and row.url and not row.series:
            problems.append(f"{rid}: a fetchable row that declares no series stores nothing")
    return problems


# ------------------------------------------------------------------------------ the network door
class Guard:
    """THE ONE NETWORK DOOR. `no_fetch` makes it a fixture reader and nothing else opens a socket.

    Fixtures live at `<fixtures>/<lane>/<dataset_id>.json`. Every error string leaving this door
    has been through `redact`, so a key embedded in a URL cannot reach a note.
    """

    def __init__(self, *, no_fetch: bool = True, fixtures: Path | None = None,
                 budget_s: float = 120.0, timeout_s: float = TIMEOUT_S,
                 secrets: Iterable[str] = ()) -> None:
        self.no_fetch = bool(no_fetch)
        self.fixtures = Path(fixtures) if fixtures is not None else DESK / "data" / "mena_fixtures"
        self.budget_s = float(budget_s)
        self.timeout_s = float(timeout_s)
        self.started = time.monotonic()
        self.calls = 0
        self._secrets = tuple(s for s in secrets if s)

    def over(self) -> bool:
        return (time.monotonic() - self.started) >= self.budget_s

    def fixture(self, lane: str, dataset_id: str) -> tuple[Any, str]:
        path = self.fixtures / lane / f"{dataset_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8-sig")), f"fixture {lane}/{path.name}"
        except OSError:
            return None, f"no fixture for {lane}/{dataset_id}"
        except ValueError as exc:
            return None, f"fixture {lane}/{path.name} is not JSON: {type(exc).__name__}"

    def get(self, url: str, *, lane: str, dataset_id: str,
            params: Mapping[str, str] | None = None) -> tuple[Any, str]:
        """Parsed JSON, or (None, why). In `no_fetch` mode the url is never touched."""
        if self.no_fetch:
            return self.fixture(lane, dataset_id)
        if self.over():
            return None, f"budget {self.budget_s:.0f}s exhausted before {lane}/{dataset_id}"
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            return None, "refused: only http(s) grounds are fetched"
        full = url
        if params:
            full = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(dict(params))}"
        req = urllib.request.Request(full, headers={"User-Agent": UA,
                                                    "Accept": "application/json"})
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=min(self.timeout_s,
                                                         max(1.0, self.budget_s))) as resp:
                raw = resp.read()
        except (OSError, ValueError) as exc:
            return None, redact(f"{type(exc).__name__}: {exc}", self._secrets)
        try:
            return json.loads(raw.decode("utf-8-sig")), f"fetched {lane}/{dataset_id}"
        except (UnicodeDecodeError, ValueError) as exc:
            return None, f"{lane}/{dataset_id} answered non-JSON: {type(exc).__name__}"


# ------------------------------------------------------------------------------ payload readers
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_WRAPPERS = ("data", "records", "items", "rows", "results", "result", "value", "observations")
_DATE_FIELDS = ("week_end", "date", "period", "time_period", "TIME_PERIOD", "month", "day",
                "as_of", "reference_date")
_AR_DECIMAL, _AR_THOUSANDS = chr(0x066B), chr(0x066C)
_NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")


def rows_of(payload: Any) -> list[dict[str, Any]]:
    """The record list inside whatever wrapper this release uses; `[]` when there is none."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, Mapping):
        for name in _WRAPPERS:
            if name in payload:
                got = rows_of(payload[name])
                if got:
                    return got
    return []


def row_value(row: Mapping[str, Any], name: str = "value") -> float | None:
    """A number from one cell: Arabic-Indic digits, thousands separators and `..` handled."""
    raw = row.get(name) if isinstance(row, Mapping) else None
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw) if math.isfinite(float(raw)) else None
    text = str(raw).translate(_DIGITS).strip()
    text = text.replace(_AR_DECIMAL, ".").replace(_AR_THOUSANDS, "").replace(",", "")
    text = re.sub(r"[\s']", "", text)   # unicode \s covers NBSP and narrow NBSP
    if not _NUMBER.fullmatch(text):
        return None
    got = float(text)
    return got if math.isfinite(got) else None


def parse_day(text: Any) -> date | None:
    """YYYY-MM-DD (or an ISO timestamp) -> that day; YYYY-MM -> the month's LAST day."""
    value = str(text or "").translate(_DIGITS).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", value):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if m and 1 <= int(m.group(2)) <= 12:
        return month_end(int(m.group(1)), int(m.group(2)))
    return None


def row_date(row: Mapping[str, Any]) -> date | None:
    """The period a row DESCRIBES, from the first date field it carries; None if unreadable."""
    if not isinstance(row, Mapping):
        return None
    for name in _DATE_FIELDS:
        if row.get(name) not in (None, ""):
            return parse_day(row[name])
    return None


# ------------------------------------------------------------------------------ observations
@dataclass
class Observation:
    """One value, with the period it DESCRIBES and the instant it became KNOWABLE kept apart."""

    series: str
    value: float
    period_time: str
    publication_time: str
    available_time: str
    vintage: str
    vintage_id: str
    source_id: str
    meta: dict[str, Any] = field(default_factory=dict)

    def point(self) -> dict[str, Any]:
        out: dict[str, Any] = {name: getattr(self, name) for name in OBS_FIELDS}
        out["knowable_at"] = str(self.available_time)[:10]
        if self.meta:
            out["meta"] = dict(self.meta)
        return out


def observe(series: str, value: float, period: date, *, lag_days: float, vintage: str,
            source_id: str, meta: Mapping[str, Any] | None = None) -> Observation:
    """Stamp one value: the period it describes, plus the declared publication lag."""
    period_time = _midnight(period)
    stamp = (period_time + timedelta(days=float(lag_days))).isoformat()
    digest = hashlib.sha1(f"{series}|{period_time.isoformat()}|{vintage}|{stamp}|"
                          f"{float(value)!r}".encode(), usedforsecurity=False).hexdigest()[:12]
    return Observation(series=series, value=float(value), period_time=period_time.isoformat(),
                       publication_time=stamp, available_time=stamp, vintage=vintage,
                       vintage_id=f"{vintage}:{digest}", source_id=source_id,
                       meta=dict(meta or {}))


# ------------------------------------------------------------------------------ the PIT store
def series_path(axes: Path, country: str, lane: str, series: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in series)
    return Path(axes) / f"{country}_{lane}_{safe}.json"


def _load_points(axes: Path, country: str, lane: str, series: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads(series_path(axes, country, lane, series).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    points = doc.get("points") if isinstance(doc, Mapping) else None
    return [p for p in (points or []) if isinstance(p, dict) and p.get("period_time")]


def _at(point: Mapping[str, Any]) -> datetime:
    return _instant(str(point.get("available_time") or "")) or _EPOCH


def _latest(points: Sequence[Mapping[str, Any]], upto: datetime | None = None
            ) -> dict[str, Mapping[str, Any]]:
    """Per period, the point with the LATEST available time -- never the latest WRITTEN."""
    best: dict[str, tuple[datetime, int]] = {}
    out: dict[str, Mapping[str, Any]] = {}
    for index, point in enumerate(points):
        at = _at(point)
        if upto is not None and at >= upto:
            continue
        period = str(point["period_time"])
        rank = (at, index)
        if period not in best or rank >= best[period]:
            best[period] = rank
            out[period] = point
    return out


def store_series(axes: Path, country: str, lane: str, series: str,
                 observations: Iterable[Observation]) -> dict[str, Any]:
    """APPEND what is new or CHANGED; never overwrite. Returns the doc plus `added`.

    A changed value arriving with an available time no later than the one it revises cannot have
    been knowable then -- the desk SAW it now -- so it is restamped to now, closing the look-ahead
    a lag-derived stamp would otherwise hand a revision.
    """
    points = _load_points(axes, country, lane, series)
    ids = {(str(p["period_time"]), str(p.get("vintage_id"))) for p in points}
    added = 0
    for obs in observations:
        if obs.series != series or (obs.period_time, obs.vintage_id) in ids:
            continue
        mine = [p for p in points if str(p["period_time"]) == obs.period_time]
        latest = _latest(mine).get(obs.period_time)
        if latest is not None and float(latest.get("value")) == float(obs.value):
            continue
        point = obs.point()
        if mine:
            prior = max(_at(p) for p in mine)
            if (_instant(point["available_time"]) or _EPOCH) <= prior:
                seen = max(datetime.now(tz=UTC), prior + timedelta(seconds=1))
                point["available_time"] = seen.isoformat(timespec="seconds")
                point["knowable_at"] = point["available_time"][:10]
                point["restamped"] = True
        point["revision_n"] = len(mine)
        points.append(point)
        ids.add((obs.period_time, obs.vintage_id))
        added += 1
    doc = {"country": country, "lane": lane, "series": series, "rule": RULE,
           "updated_at": now_iso(), "n": len(points),
           "n_periods": len({str(p["period_time"]) for p in points}),
           "n_vintages": sum(1 for p in points if int(p.get("revision_n") or 0) > 0),
           "points": points}
    if added:
        path = series_path(axes, country, lane, series)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n",
                       encoding="utf-8")
        tmp.replace(path)
    return {**doc, "added": added}


def as_of(axes: Path, country: str, lane: str, series: str,
          when: str | date | datetime) -> dict[str, float]:
    """{period_time: value} exactly as KNOWN at `when`. A period not yet knowable is ABSENT."""
    cutoff = _cutoff(when)
    if cutoff is None:
        return {}
    got = _latest(_load_points(axes, country, lane, series), upto=cutoff)
    return {period: float(point["value"]) for period, point in sorted(got.items())}


def read_series(axes: Path, country: str, lane: str, series: str) -> list[tuple[str, float]]:
    """Every stored point as (available_time, value), in LEARNING order, revisions included."""
    points = sorted(_load_points(axes, country, lane, series),
                    key=lambda p: (_at(p), str(p["period_time"])))
    return [(str(p["available_time"]), float(p["value"])) for p in points]


# ------------------------------------------------------------------------------ states
def zscore(values: Sequence[float], window: int = WINDOW) -> float:
    """The latest value's z against its own trailing window; 0.0 for a flat window."""
    tail = list(values)[-window:]
    if len(tail) < 2:
        return 0.0
    mean = sum(tail) / len(tail)
    sd = math.sqrt(sum((v - mean) ** 2 for v in tail) / (len(tail) - 1))
    return 0.0 if sd <= 1e-12 else (tail[-1] - mean) / sd


def level_state(values: Sequence[float], *, label: str, up: str, down: str,
                min_n: int = MIN_N, window: int = WINDOW) -> dict[str, Any]:
    """Where the latest level sits in its own trailing window. A short series is UNMEASURED."""
    n = len(values)
    if n < min_n:
        return {"state": UNMEASURED, "label": label, "n": n, "z": None, "min_n": min_n,
                "why": f"UNMEASURED: {n} period(s) stored, a state needs {min_n}"}
    z = zscore(values, window)
    state = up if z > Z_BAND else (down if z < -Z_BAND else "NEUTRAL")
    span = min(window, n)
    return {"state": state, "label": label, "n": n, "z": round(z, 4), "min_n": min_n,
            "window": span, "why": f"latest level z={z:+.2f} over a {span}-period window"}


# ------------------------------------------------------------------------------ the lane base
@dataclass
class FetchResult:
    lane: str
    country: str
    key_present: bool
    mode: str
    fetched: int = 0
    stored: int = 0
    vintages: int = 0
    rows: list[Observation] = field(default_factory=list)
    series_written: list[str] = field(default_factory=list)
    unmeasured: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    why: str = ""

    def row(self) -> dict[str, Any]:
        """The report row: counts, names and verdicts. Never an observation dump, never a key."""
        return {"lane": self.lane, "country": self.country, "mode": self.mode,
                "key_present": self.key_present, "fetched": self.fetched, "stored": self.stored,
                "vintages": self.vintages, "observations": len(self.rows),
                "series_written": list(self.series_written), "unmeasured": list(self.unmeasured),
                "notes": list(self.notes), "why": self.why}


class MenaLane:
    """One institution's lane. Subclasses declare LANE, COUNTRY, KEY and CATALOGUE."""

    LANE: ClassVar[str] = ""
    COUNTRY: ClassVar[str] = ""
    #: the key name in `mena_apis.json`, or "" for a ground that documents no key
    KEY: ClassVar[str] = ""
    CATALOGUE: ClassVar[tuple[CatalogueRow, ...]] = ()

    def __init__(self, *, desk: Path | None = None, axes: Path | None = None,
                 fixtures: Path | None = None, no_fetch: bool = True, dry_run: bool = False,
                 keys: Mapping[str, str] | None = None, secrets_path: Path | None = None) -> None:
        self.desk = Path(desk) if desk is not None else DESK
        self.axes = Path(axes) if axes is not None else self.desk / "data" / "axes"
        self.fixtures = (Path(fixtures) if fixtures is not None
                         else self.desk / "data" / "mena_fixtures")
        self.no_fetch = bool(no_fetch)
        self.dry_run = bool(dry_run)
        self.secrets_path = (Path(secrets_path) if secrets_path is not None
                             else self.desk / SECRETS_REL)
        self._keys = dict(keys) if keys is not None else read_keys(self.secrets_path)
        self.recorded: list[dict[str, Any]] = []

    # -- identity and keys
    def catalogue(self) -> list[CatalogueRow]:
        return list(self.CATALOGUE)

    def key_present(self) -> bool:
        return not self.KEY or bool(str(self._keys.get(self.KEY) or "").strip())

    def _secret_values(self) -> list[str]:
        return [str(v) for v in self._keys.values() if v]

    # -- discoveries
    def record(self, *, dataset: str, mechanism: str, payload: Mapping[str, Any]) -> None:
        """The question stays on the books when the answer is blocked: the backlog of blocked
        datasets IS the acquisition plan. Held in memory and carried by the report."""
        self.recorded.append({
            "source_id": f"{self.LANE}:{dataset}", "source_type": "mena_data_plane",
            "generator": f"{GENERATOR}:{self.LANE}", "origin": "EXTERNAL",
            "mechanism": mechanism[:400],
            "payload": {**dict(payload), "lane": self.LANE, "country": self.COUNTRY,
                        "rule": RULE}})

    # -- parsing
    def parse(self, row: CatalogueRow, payload: Any) -> list[Observation]:
        """A flat table: one date field per record and one column per declared series."""
        out: list[Observation] = []
        for rec in rows_of(payload):
            day = row_date(rec)
            if day is None:
                continue
            for name in row.series:
                value = row_value(rec, name)
                if value is None and len(row.series) == 1:
                    value = row_value(rec, "value")
                if value is None:
                    continue
                out.append(observe(name, value, day, lag_days=row.publication_lag_days,
                                   vintage=row.vintage, source_id=f"{self.LANE}:{row.dataset_id}"))
        return out

    # -- the pass
    def _blocked_on_key(self, res: FetchResult, row: CatalogueRow) -> None:
        res.unmeasured.append({
            "dataset": row.dataset_id, "verdict": UNMEASURED, "key_name": row.key_name,
            "key_path": SECRETS_REL,
            "why": f"UNMEASURED: key {row.key_name!r} is absent from {SECRETS_REL}; the "
                   f"dataset is blocked, not barren"})
        self.record(dataset=row.dataset_id,
                    mechanism=f"{row.institution}: {row.coverage} -- blocked on the "
                              f"{row.key_name!r} key",
                    payload={"dataset": row.dataset_id, "verdict": UNMEASURED,
                             "key_name": row.key_name, "key_path": SECRETS_REL,
                             "series": list(row.series)})

    def fetch(self, budget_s: float = 120.0) -> FetchResult:
        present = self.key_present()
        res = FetchResult(lane=self.LANE, country=self.COUNTRY, key_present=present,
                          mode="no-fetch" if self.no_fetch else "live")
        secrets = self._secret_values()
        guard = Guard(no_fetch=self.no_fetch, fixtures=self.fixtures, budget_s=budget_s,
                      secrets=secrets)
        blocked: list[str] = []
        written: dict[str, dict[str, Any]] = {}
        for row in self.catalogue():
            if row.access == LICENSED:
                res.unmeasured.append({
                    "dataset": row.dataset_id, "verdict": UNMEASURED, "licence": row.licence,
                    "why": f"UNMEASURED: licensed product, deliberately not fetched -- "
                           f"{row.how_to_fetch}"})
                continue
            if row.key_required and not str(self._keys.get(row.key_name) or "").strip():
                blocked.append(row.dataset_id)
                self._blocked_on_key(res, row)
                continue
            if not row.url:
                res.unmeasured.append({"dataset": row.dataset_id, "verdict": UNMEASURED,
                                       "why": "UNMEASURED: no machine-readable endpoint "
                                              "declared"})
                continue
            params = ({row.key_param: str(self._keys[row.key_name])}
                      if row.key_param and row.key_required else None)
            payload, why = guard.get(row.url, lane=self.LANE, dataset_id=row.dataset_id,
                                     params=params)
            why = redact(why, secrets)
            if payload is None:
                res.unmeasured.append({"dataset": row.dataset_id, "verdict": UNMEASURED,
                                       "why": f"UNMEASURED: {why}"})
                continue
            obs = self.parse(row, payload)
            if not obs:
                res.unmeasured.append({
                    "dataset": row.dataset_id, "verdict": UNMEASURED,
                    "why": "UNMEASURED: payload shape unrecognised, not barren -- the parser "
                           "read nothing it could attribute"})
                self.record(dataset=row.dataset_id,
                            mechanism=f"{row.institution}: {row.coverage} -- payload shape "
                                      f"unrecognised",
                            payload={"dataset": row.dataset_id, "verdict": UNMEASURED,
                                     "why": "shape unrecognised, not barren"})
                continue
            res.fetched += 1
            res.rows.extend(obs)
            for name in row.series:
                mine = [o for o in obs if o.series == name]
                if not mine:
                    continue
                if name not in res.series_written:
                    res.series_written.append(name)
                if not self.dry_run:
                    written[name] = store_series(self.axes, self.COUNTRY, self.LANE, name, mine)
        res.stored = len(written)
        res.vintages = sum(int(doc.get("n_vintages") or 0) for doc in written.values())
        if self.dry_run:
            res.notes.append("dry run: parsed and measured, nothing stored")
        if blocked:
            res.why = (f"UNMEASURED: {len(blocked)} dataset(s) need the {self.KEY!r} key, absent "
                       f"from {SECRETS_REL}: {', '.join(blocked)}")
        elif res.fetched == 0:
            res.why = f"UNMEASURED: nothing read ({len(res.unmeasured)} dataset(s) named)"
        else:
            res.why = (f"{res.fetched} dataset(s) read, {len(res.series_written)} series, "
                       f"{res.stored} stored")
        return res

    # -- readers
    def series(self, name: str) -> list[tuple[str, float]]:
        return read_series(self.axes, self.COUNTRY, self.LANE, name)

    def as_of(self, name: str, when: str | date | datetime) -> dict[str, float]:
        return as_of(self.axes, self.COUNTRY, self.LANE, name, when)

    def known(self, name: str, when: str | date | datetime | None = None) -> dict[str, float]:
        """{period_time: value} at the vintage knowable at `when` (default: now)."""
        return self.as_of(name, when if when is not None else datetime.now(tz=UTC))

    def panel(self, name: str, when: str | date | datetime | None = None) -> list[float]:
        """Values in PERIOD order, each at the vintage knowable at `when` (default: now)."""
        got = self.known(name, when)
        return [got[p] for p in sorted(got)]

    def states(self) -> list[dict[str, Any]]:
        return []


# ------------------------------------------------------------------------------ SAMA
#: DECLARED root of the SAMA open-data platform; verified=False until it returns bytes here
_SAMA_API = "https://opendata.sama.gov.sa/api/v1/datasets"


class SamaLane(MenaLane):
    """The Saudi Central Bank: the Gulf's ONLY weekly official demand and money series."""

    LANE = "sama"
    COUNTRY = "sa"
    KEY = "sama"
    CATALOGUE = (
        CatalogueRow("sama_pos_weekly", "Saudi Central Bank (SAMA)",
                     "weekly point-of-sale transaction value, count and terminal stock",
                     "weekly", "none observed; the weekly print is final",
                     "free, public (SAMA open-data terms)", "2019-01",
                     "SAMA open-data platform weekly release; store the publication timestamp "
                     "with the value", 3.0, url=f"{_SAMA_API}/pos-weekly/records",
                     series=("pos_value_sar", "pos_transactions", "pos_terminals"),
                     key_required=True, key_name="sama", key_param="apikey"),
        CatalogueRow("sama_money_weekly", "Saudi Central Bank (SAMA)",
                     "weekly money supply and bank deposits (the high-frequency liquidity read)",
                     "weekly", "provisional; restated into the monthly bulletin",
                     "free, public (SAMA open-data terms)", "2016-01",
                     "SAMA open-data monetary statistics; the weekly series is provisional and "
                     "both vintages are kept", 7.0, url=f"{_SAMA_API}/money-weekly/records",
                     series=("money_supply_weekly_sar", "bank_deposits_weekly_sar"),
                     key_required=True, key_name="sama", key_param="apikey",
                     vintage="provisional"),
        CatalogueRow("sama_monetary_monthly", "Saudi Central Bank (SAMA)",
                     "monthly M3 and its components", "monthly",
                     "revised in the following bulletin; vintages matter",
                     "free, public (SAMA open-data terms)", "1993-01",
                     "SAMA monthly statistical bulletin via the open-data platform", 30.0,
                     url=f"{_SAMA_API}/monetary-monthly/records", series=("m3_sar",),
                     key_required=True, key_name="sama", key_param="apikey"),
        CatalogueRow("sama_net_foreign_assets", "Saudi Central Bank (SAMA)",
                     "SAMA net foreign assets (reserve assets)", "monthly",
                     "minor; a PIF transfer is a reclassification, not a drain",
                     "free, public (SAMA open-data terms)", "1993-01",
                     "SAMA open-data external-sector statistics", 30.0,
                     url=f"{_SAMA_API}/net-foreign-assets/records",
                     series=("net_foreign_assets_sar",),
                     key_required=True, key_name="sama", key_param="apikey"),
        CatalogueRow("saibor_daily", "Saudi Central Bank (SAMA)",
                     "SAIBOR fixings by tenor", "daily", "none once fixed",
                     "free, public (SAMA open-data terms)", "2007-01",
                     "SAMA statistics; published about 11:00 AST (08:00 UTC)", 0.4,
                     url=f"{_SAMA_API}/saibor/records", series=("saibor_3m",),
                     key_required=True, key_name="sama", key_param="apikey"),
        CatalogueRow("sar_forward_points_dealer", "interbank dealers (licensed terminals)",
                     "USD/SAR forward points, the market's own price of peg risk", "daily",
                     "not applicable", "LICENSED: dealer terminal data, not redistributable",
                     "2000-01",
                     "NOT AVAILABLE TO THIS DESK: catalogued so the absence is a decision",
                     0.0, pit_feasible=NOT_PIT_SAFE, access=LICENSED),
    )

    def _with_control(self, name: str, series: str, label: str, control: str) -> dict[str, Any]:
        state = level_state(self.panel(series), label=label, up="EXPANSION",
                            down="CONTRACTION")
        leg = level_state(self.panel(control), label=control, up="EXPANSION",
                          down="CONTRACTION")
        state["control"] = {"series": control, "state": leg["state"], "z": leg["z"],
                            "n": leg["n"]}
        return {"lane": self.LANE, "name": name, "series": series, **state}

    def demand_state(self) -> dict[str, Any]:
        """Weekly POS value against its own year; the transaction COUNT is the control, because
        a value surge the count does not share is price, not demand."""
        return self._with_control("demand_state", "pos_value_sar", "domestic_demand",
                                  "pos_transactions")

    def liquidity_state(self) -> dict[str, Any]:
        """Weekly money supply against its own year; bank deposits are the control leg."""
        return self._with_control("liquidity_state", "money_supply_weekly_sar",
                                  "domestic_liquidity", "bank_deposits_weekly_sar")

    def states(self) -> list[dict[str, Any]]:
        return [self.demand_state(), self.liquidity_state()]


LANES: tuple[type[MenaLane], ...] = (SamaLane,)


# ------------------------------------------------------------------------------ the report
def merge_report(section: Mapping[str, Any], *, path: Path, dry_run: bool) -> dict[str, Any]:
    """Update, never clobber: another lane's sections in the same report survive."""
    try:
        existing = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        existing = {}
    doc = {**(existing if isinstance(existing, dict) else {}), **dict(section)}
    if not dry_run:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1, default=str) + "\n",
                       encoding="utf-8")
        tmp.replace(target)
    return doc


def _lanes_of(registry: Any, default: Sequence[type[MenaLane]]) -> list[type[MenaLane]]:
    got = [c for c in (registry or ()) if isinstance(c, type) and issubclass(c, MenaLane)]
    return got or list(default)


def run(*, desk: Path | None = None, axes: Path | None = None, fixtures: Path | None = None,
        keys: Mapping[str, str] | None = None, no_fetch: bool = True, dry_run: bool = False,
        report_path: Path | None = None, report_default: Path | None = None,
        budget_s: float = 300.0, registry: Any = None,
        secrets_path: Path | None = None) -> dict[str, Any]:
    """Every lane in `registry` (default: this module's LANES), one pass, one merged report.

    `registry` and `report_default` are what `_data_plane_miner` passes; `report_path` wins over
    both. A dry run parses and measures but writes nothing: no axis file, no report.
    """
    lanes = _lanes_of(registry, LANES)
    code = lanes[0].COUNTRY or CODE
    home = Path(desk) if desk is not None else DESK
    secrets_file = Path(secrets_path) if secrets_path is not None else home / SECRETS_REL
    held = dict(keys) if keys is not None else read_keys(secrets_file)
    per_lane = max(1.0, float(budget_s) / max(1, len(lanes)))
    rows: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    catalogue: list[CatalogueRow] = []
    discoveries: list[dict[str, Any]] = []
    for cls in lanes:
        lane = cls(desk=home, axes=axes, fixtures=fixtures, no_fetch=no_fetch, dry_run=dry_run,
                   keys=held, secrets_path=secrets_file)
        catalogue.extend(lane.catalogue())
        res = lane.fetch(budget_s=per_lane)
        rows.append({**res.row(), "catalogue": [r.dataset_id for r in lane.catalogue()]})
        states.extend(lane.states())
        discoveries.extend(lane.recorded)
    doc: dict[str, Any] = {
        "at": now_iso(), "rule": RULE, "country": code,
        "mode": "no-fetch" if no_fetch else "live", "dry_run": bool(dry_run),
        "acquisition_owner": ACQUISITION_OWNER, "no_fetch_is_owned": bool(no_fetch),
        "lanes": rows, "catalogue_problems": check_catalogue(catalogue),
        "key_status": key_status(held), "states": states, "discoveries": discoveries,
        "stored": sum(int(r.get("stored") or 0) for r in rows),
        "vintages": sum(int(r.get("vintages") or 0) for r in rows),
    }
    if home == DESK:
        # The acquired-registry measurement is this desk's own state; a redirected desk (a test,
        # a scratch box) must not have the production registry folded into its report.
        try:
            declared = _declared_run(code=code, no_fetch=no_fetch, dry_run=True)
            doc["declared"] = {k: declared.get(k) for k in
                               ("declared", "acquired", "pit_usable", "unresolved", "lanes")}
        except Exception as exc:          # pragma: no cover -- a pack mid-edit is not fatal
            doc["declared"] = {"verdict": UNMEASURED, "why": type(exc).__name__}
    doc = json.loads(redact(json.dumps(doc, ensure_ascii=False, default=str),
                            [str(v) for v in held.values() if v]))
    target = report_path or report_default or _report_path(code)
    return merge_report(doc, path=Path(target), dry_run=dry_run)
