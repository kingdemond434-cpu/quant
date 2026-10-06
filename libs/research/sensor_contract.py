"""THE UNIVERSAL SENSOR CONTRACT -- one observation shape for every kind of thing the desk can see.

THE PRINCIPAL'S ORDER (2026-10-05, binding header): "Create or extend ONE canonical structured
observation contract capable of representing non-text information ... Continuous observations
update STATE. Material discontinuities may mint EVENTS. Neither receives trading authority
directly." News is one sensor; a weather anomaly, a port call, a customs print, a payroll release
with its consensus and an options-surface state are others, and all of them land here first.

WHAT ALREADY EXISTED, AND WHY THIS EXTENDS RATHER THAN REPLACES IT.

  `libs.data.pit`        the ROW stamp (event_time / available_time / ingested_time /
                         payload_hash) and `usable_at`. Every observation here carries those four
                         names as aliases, so a joiner that only knows `pit.usable_at` reads a
                         sensor row correctly with no edit.
  `libs.tiers.bitemporal` the bitemporal store (valid time x knowledge time, revision, licence).
                         `to_datum()` hands an observation to it unchanged in meaning.
  `libs.research.vintage` the revision LOG for revised series. The ledger below obeys the same
                         rule -- a revision is a new row that names what it revises, never an
                         overwrite -- for every sensor class, not only for the panels vintage.py
                         was written for.

None of the three could hold a non-text observation WITH its expectation, surprise, measurement
uncertainty and licence on one record, and none of them separated the seven observation-side
clocks the PIT law names. That is the gap this module closes.

THE PIT LAW, MECHANICALLY (binding header, "PIT LAW").

  event_time               when the thing HAPPENED or the period the number describes
  scheduled_time           when the release was SCHEDULED (scheduled sources only)
  publication_time         the OFFICIAL publication instant (the agency's own stamp)
  source_publication_time  when the SOURCE we read published it (a wire, a calendar, GDELT)
  knowable_at              the first instant the WORLD could know it
  received_at              when THIS desk received the bytes
  parse_complete_at        when this desk finished turning the bytes into this row

Never one field for two facts. An absent clock is the string UNMEASURED, never a guess and never
a copy of a neighbouring clock: "never replace when the event happened with when the market could
know". The DOWNSTREAM clocks (decision-available, allocator, order-send, broker ack, fill) are not
on the observation -- they belong to the consumers -- and are appended as `clock` rows keyed by
`observation_id` through `stamp_downstream`, so the latency from a new observation to the decision
it caused is a JOIN on one id rather than an inference.

NO AUTHORITY. `authority` is the constant NONE on every observation and `route()` returns STATE or
EVENT -- never a side, a size or a weight. A sensor that wants capital goes through the canonical
gauntlet like everything else.

REVISIONS APPEND. The ledger keys a numeric observation on (sensor, entity, metric, event_time);
a second value for the same key arrives as a NEW row with `revision_of` set to the id it revises
and `revision_delta` its change. The first print is never edited, which is the only way a
backtest can ever ask what the desk knew on the morning of the release.

THROUGHPUT IS A MEASUREMENT, NOT A QUOTA. `intake_metrics` turns one day's ledger into the
numbers the header asks for -- raw observations, unique documents, stories, events, novel and
economically relevant events, the duplicate compression ratio, language/region/domain coverage,
source diversity and the publication->receipt and receipt->classification latency distributions
-- and every number with no stamps behind it is UNMEASURED, never zero.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

UNMEASURED = "UNMEASURED"
AUTHORITY = "NONE"
SCHEMA = "sensor_observation/1"

#: The observation-side clocks, in the order information flows through them.
CLOCKS: tuple[str, ...] = ("event_time", "scheduled_time", "publication_time",
                           "source_publication_time", "knowable_at", "received_at",
                           "parse_complete_at")
#: The consumer-side clocks, appended by whoever acts on an observation (`stamp_downstream`).
DOWNSTREAM_CLOCKS: tuple[str, ...] = ("decision_available_at", "forecast_updated_at",
                                      "cache_invalidated_at", "allocator_at", "order_sent_at",
                                      "broker_ack_at", "fill_at")
#: What an observation IS. A document is text whose meaning the classifier reads; a state is a
#: continuous level; an event is a discontinuity a producer declared or the router detected.
KINDS: tuple[str, ...] = ("state", "event", "document")
#: |surprise_z| at or above which a continuous observation is ROUTED as an event. A declared
#: prior -- a routing threshold, not a trading one -- and every routed row carries the basis.
DISCONTINUITY_Z = 2.0


@dataclass(frozen=True)
class SensorObservation:
    """One observation from any sensor. Every field the binding header lists is here."""

    sensor_id: str
    source_id: str
    metric: str
    entity: str = ""
    dataset_id: str = ""
    observation_id: str = ""
    kind: str = "state"
    sensor_class: str = ""
    geography: str = ""
    asset_domain: str = ""
    value: float | None = None
    unit: str = ""
    text: str = ""
    language: str = ""
    # the seven observation-side clocks
    event_time: str = UNMEASURED
    scheduled_time: str = UNMEASURED
    publication_time: str = UNMEASURED
    source_publication_time: str = UNMEASURED
    knowable_at: str = UNMEASURED
    received_at: str = UNMEASURED
    parse_complete_at: str = UNMEASURED
    # expectation and surprise
    expected_value: float | None = None
    consensus: float | None = None
    seasonal_expected: float | None = None
    raw_surprise: float | None = None
    surprise_z: float | None = None
    percentile: float | None = None
    delta: float | None = None
    acceleration: float | None = None
    # revision history
    revision_of: str = ""
    revision_delta: float | None = None
    revision_n: int = 0
    # quality, rights and provenance
    source_confidence: float | None = None
    measurement_uncertainty: float | None = None
    commercial_rights: str = UNMEASURED
    licence: str = UNMEASURED
    provenance_hash: str = ""
    raw_pointer: str = ""
    attributes: Mapping[str, Any] = field(default_factory=dict)
    authority: str = AUTHORITY
    schema: str = SCHEMA

    def to_row(self) -> dict[str, Any]:
        """The ledger row, with the `libs.data.pit` stamp aliases a PIT joiner already reads."""
        row = asdict(self)
        row["attributes"] = dict(self.attributes)
        row["authority"] = AUTHORITY
        row["source_version"] = str(self.attributes.get("source_version") or self.schema)
        # `available_time` is `pit.usable_at`'s field. Only the WORLD clock may fill it: a row
        # whose world-knowable instant is unmeasured is not usable by a PIT joiner at any time.
        row["available_time"] = self.knowable_at
        row["ingested_time"] = self.received_at
        row["payload_hash"] = self.provenance_hash
        return row

    def to_datum(self) -> Any:
        """The same fact as a `libs.tiers.bitemporal.Datum` (valid time x knowledge time)."""
        from libs.tiers.bitemporal import Datum
        return Datum(entity=self.entity or self.sensor_id, attribute=self.metric,
                     value=self.value, valid_time=self.event_time,
                     knowledge_time=self.knowable_at, source=self.source_id,
                     revision=int(self.revision_n),
                     latency_s=latency_s(self.knowable_at, self.received_at),
                     reliability=self.source_confidence, licence=self.licence)


_FIELD_NAMES = frozenset(f.name for f in fields(SensorObservation))


# ============================================================================== time helpers
def parse_time(value: Any) -> datetime | None:
    """An aware UTC datetime, or None. A naive stamp is read as UTC; UNMEASURED is None."""
    if value is None or value == UNMEASURED or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def iso(value: Any) -> str:
    """ISO-8601 UTC seconds, or UNMEASURED when the value is not a time."""
    dt = parse_time(value)
    return dt.isoformat(timespec="seconds") if dt else UNMEASURED


def latency_s(earlier: Any, later: Any) -> float | None:
    a, b = parse_time(earlier), parse_time(later)
    if a is None or b is None:
        return None
    return round((b - a).total_seconds(), 3)


def _f(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def content_hash(payload: Any) -> str:
    """sha256 of canonical JSON (or of raw bytes) -- the provenance hash of what was read."""
    if isinstance(payload, bytes | bytearray):
        blob = bytes(payload)
    else:
        blob = json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def observation_id(sensor_id: str, entity: str, metric: str, event_time: str,
                   value: Any, knowable_at: str, text: str = "", source_id: str = "",
                   raw_pointer: str = "") -> str:
    """Identity of ONE observation by ONE source. The same headline from two outlets is two
    observations (and one document); the same outlet's row read twice is one."""
    key = "|".join((sensor_id, source_id, entity, metric, event_time, repr(_f(value)),
                    knowable_at, text[:300], raw_pointer))
    return "ob_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]


# ============================================================================== construction
def make(**kw: Any) -> SensorObservation:
    """Build an observation from loose keyword input: clocks normalised, ids and hashes filled.

    Unknown keys go to `attributes` rather than being dropped, so a producer's extra fact is
    kept and visible. `authority` cannot be set by a producer.
    """
    kw.pop("authority", None)
    kw.pop("schema", None)
    extras = {k: kw.pop(k) for k in list(kw) if k not in _FIELD_NAMES}
    attrs = dict(kw.pop("attributes", None) or {})
    attrs.update(extras)
    for clock in CLOCKS:
        kw[clock] = iso(kw.get(clock))
    for num in ("value", "expected_value", "consensus", "seasonal_expected", "raw_surprise",
                "surprise_z", "percentile", "delta", "acceleration", "revision_delta",
                "source_confidence", "measurement_uncertainty"):
        if num in kw:
            kw[num] = _f(kw[num])
    if kw.get("raw_surprise") is None and kw.get("value") is not None:
        ref = kw.get("consensus") if kw.get("consensus") is not None else kw.get("expected_value")
        if ref is not None:
            kw["raw_surprise"] = round(float(kw["value"]) - float(ref), 12)
    kw.setdefault("sensor_id", "")
    kw.setdefault("source_id", kw["sensor_id"])
    kw.setdefault("metric", "")
    if not kw.get("provenance_hash"):
        kw["provenance_hash"] = content_hash({k: kw.get(k) for k in (
            "sensor_id", "source_id", "entity", "metric", "value", "text", "event_time",
            "publication_time", "raw_pointer")})
    if not kw.get("observation_id"):
        kw["observation_id"] = observation_id(
            str(kw["sensor_id"]), str(kw.get("entity") or ""), str(kw["metric"]),
            str(kw["event_time"]), kw.get("value"), str(kw["knowable_at"]),
            str(kw.get("text") or ""), str(kw.get("source_id") or ""),
            str(kw.get("raw_pointer") or ""))
    return SensorObservation(attributes=attrs, **kw)


def from_row(row: Mapping[str, Any]) -> SensorObservation:
    """A ledger row back into an observation (the pit aliases are dropped, not trusted)."""
    clean = {k: v for k, v in row.items() if k in _FIELD_NAMES}
    clean.pop("authority", None)
    clean.pop("schema", None)
    return SensorObservation(**clean)


# ============================================================================== validation
def defects(obs: SensorObservation) -> list[str]:
    """Everything wrong with an observation at the contract boundary. Empty means admitted.

    A defect is not repaired here: the producer is told, and the row is refused, because a row
    repaired at the boundary is a row whose provenance is no longer what it says.
    """
    out: list[str] = []
    if not obs.sensor_id:
        out.append("sensor_id is empty")
    if not obs.metric:
        out.append("metric is empty")
    if obs.kind not in KINDS:
        out.append(f"kind {obs.kind!r} is not one of {KINDS}")
    if obs.kind == "document" and not (obs.text or obs.raw_pointer):
        out.append("a document carries neither text nor a raw_pointer to it")
    if obs.kind != "document" and obs.value is None and not obs.attributes.get("categorical"):
        out.append("a state/event observation carries no finite value")
    for clock in CLOCKS:
        raw = getattr(obs, clock)
        if raw != UNMEASURED and parse_time(raw) is None:
            out.append(f"{clock} {raw!r} is not an ISO time")
    if obs.authority != AUTHORITY:
        out.append("a sensor observation can never carry trading authority")
    received, parsed = parse_time(obs.received_at), parse_time(obs.parse_complete_at)
    knowable = parse_time(obs.knowable_at)
    if received and parsed and parsed < received:
        out.append("parse_complete_at precedes received_at")
    if knowable and received and received < knowable - timedelta(seconds=1):
        out.append("received_at precedes knowable_at: the desk cannot hold what the world could "
                   "not yet know -- a stamp is wrong or the row is a look-ahead")
    for name in ("source_confidence",):
        val = getattr(obs, name)
        if val is not None and not 0.0 <= val <= 1.0:
            out.append(f"{name} {val} is outside [0, 1]")
    if obs.measurement_uncertainty is not None and obs.measurement_uncertainty < 0:
        out.append("measurement_uncertainty is negative")
    if obs.percentile is not None and not 0.0 <= obs.percentile <= 1.0:
        out.append(f"percentile {obs.percentile} is outside [0, 1]")
    if obs.revision_of and obs.revision_n < 1:
        out.append("a revision must carry revision_n >= 1")
    return out


def usable_at(obs: SensorObservation | Mapping[str, Any], decision_time: Any,
              basis: str = "desk") -> bool:
    """May a decision at `decision_time` use this observation?

    `world`: only once the world could know it. `desk` (the default, and the one a live replay
    must use): only once the world could know it AND this desk had received it. An unmeasured
    clock is never permission.
    """
    get = (obs.get if isinstance(obs, Mapping) else lambda k, d=None: getattr(obs, k, d))
    t = parse_time(decision_time)
    knowable = parse_time(get("knowable_at"))
    if t is None or knowable is None or knowable > t:
        return False
    if basis == "world":
        return True
    received = parse_time(get("received_at"))
    return received is not None and received <= t


def route(obs: SensorObservation, threshold_z: float = DISCONTINUITY_Z) -> dict[str, Any]:
    """STATE or EVENT, with the basis. Never a side, a size or a weight."""
    if obs.kind == "event":
        return {"route": "event", "basis": "the producer declared a discontinuity",
                "authority": AUTHORITY}
    z = obs.surprise_z
    if z is not None and abs(z) >= threshold_z:
        return {"route": "event", "basis": f"|surprise_z| {abs(z):.2f} >= {threshold_z:g}",
                "authority": AUTHORITY}
    if obs.kind == "document":
        return {"route": "document", "basis": "text: the classifier decides",
                "authority": AUTHORITY}
    return {"route": "state", "basis": ("no measured surprise" if z is None else
                                        f"|surprise_z| {abs(z):.2f} < {threshold_z:g}"),
            "authority": AUTHORITY}


# ============================================================================== the ledger
def default_root() -> Path:
    env = os.environ.get("QUANT_SENSOR_LEDGER")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "desks" / "mt5" / "data" / "sensors"


class SensorLedger:
    """Append-only, day-sharded observation ledger with revision detection.

    Shards are `observations/<YYYY-MM-DD>.jsonl` by RECEIPT day, so a day's intake is one file
    and the throughput meter reads exactly one shard. Numeric revisions are detected against a
    small index of the latest value per (sensor, entity, metric, event_time); documents are
    deduplicated by observation id within the shard.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_root()
        self.obs_dir = self.root / "observations"
        self.clock_dir = self.root / "clocks"
        self.index_path = self.root / "latest_numeric.json"
        self._index: dict[str, list[Any]] | None = None
        self._seen: dict[str, set[str]] = {}

    # -- internals
    def _shard(self, day: str, kind: str = "observations") -> Path:
        base = self.obs_dir if kind == "observations" else self.clock_dir
        return base / f"{day}.jsonl"

    def _load_index(self) -> dict[str, list[Any]]:
        if self._index is None:
            try:
                doc = json.loads(self.index_path.read_text(encoding="utf-8"))
                self._index = doc if isinstance(doc, dict) else {}
            except (OSError, ValueError):
                self._index = {}
        return self._index

    def _seen_ids(self, day: str) -> set[str]:
        if day not in self._seen:
            ids: set[str] = set()
            path = self._shard(day)
            if path.exists():
                with path.open(encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        i = line.find('"observation_id": "')
                        if i >= 0:
                            j = line.find('"', i + 19)
                            ids.add(line[i + 19:j])
            self._seen[day] = ids
        return self._seen[day]

    @staticmethod
    def revision_key(obs: SensorObservation) -> str:
        return "|".join((obs.sensor_id, obs.entity, obs.metric, obs.event_time))

    # -- public
    def append(self, observations: Iterable[SensorObservation],
               now: datetime | None = None) -> dict[str, Any]:
        """Append what is new; turn a changed value into a revision row. Returns the census."""
        when = now or datetime.now(UTC)
        index = self._load_index()
        by_day: dict[str, list[str]] = {}
        refused: list[dict[str, Any]] = []
        n_new = n_dup = n_rev = 0
        for obs in observations:
            bad = defects(obs)
            if bad:
                refused.append({"observation_id": obs.observation_id, "defects": bad[:4]})
                continue
            received = parse_time(obs.received_at) or when
            day = received.date().isoformat()
            if obs.value is not None and obs.kind != "document" and obs.event_time != UNMEASURED:
                key = self.revision_key(obs)
                prior = index.get(key)
                if prior is not None and _f(prior[1]) == obs.value:
                    n_dup += 1
                    continue
                if prior is not None and not obs.revision_of:
                    obs = make(**{**asdict(obs), "revision_of": str(prior[0]),
                                  "revision_delta": round(obs.value - float(prior[1]), 12),
                                  "revision_n": int(prior[2]) + 1, "observation_id": ""})
                    n_rev += 1
                index[key] = [obs.observation_id, obs.value, obs.revision_n]
            seen = self._seen_ids(day)
            if obs.observation_id in seen:
                n_dup += 1
                continue
            seen.add(obs.observation_id)
            by_day.setdefault(day, []).append(json.dumps(obs.to_row(), default=str,
                                                         ensure_ascii=False))
            n_new += 1
        for day, lines in by_day.items():
            path = self._shard(day)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
        if n_rev or any(by_day.values()):
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.index_path)
        return {"appended": n_new, "duplicates": n_dup, "revisions": n_rev,
                "refused": len(refused), "refusals": refused[:8],
                "shards": sorted(by_day)}

    def stamp_downstream(self, observation_ids: Sequence[str], clock: str, at: Any,
                         consumer: str, detail: Mapping[str, Any] | None = None) -> int:
        """A consumer says when it acted on observations. Appended, never edited."""
        if clock not in DOWNSTREAM_CLOCKS:
            raise ValueError(f"{clock!r} is not a downstream clock {DOWNSTREAM_CLOCKS}")
        stamp = iso(at)
        if stamp == UNMEASURED or not observation_ids:
            return 0
        path = self._shard(stamp[:10], "clocks")
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [json.dumps({"observation_id": oid, "clock": clock, "at": stamp,
                            "consumer": consumer, **(dict(detail or {}))}, default=str)
                for oid in observation_ids]
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
        return len(rows)

    def rows(self, day: str, limit: int | None = None) -> list[dict[str, Any]]:
        path = self._shard(day)
        out: list[dict[str, Any]] = []
        if not path.exists():
            return out
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    out.append(row)
                    if limit is not None and len(out) >= limit:
                        break
        return out

    def clock_rows(self, day: str) -> list[dict[str, Any]]:
        path = self._shard(day, "clocks")
        if not path.exists():
            return []
        out = []
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
        return out


# ============================================================================== the meter
def percentiles(values: Sequence[float], qs: Sequence[float] = (0.5, 0.95, 0.99)
                ) -> dict[str, Any]:
    vals = sorted(v for v in values if v is not None and math.isfinite(v))
    if not vals:
        return {"n": 0, **{f"p{round(q * 100)}": UNMEASURED for q in qs}}
    out: dict[str, Any] = {"n": len(vals)}
    for q in qs:
        pos = q * (len(vals) - 1)
        lo, hi = math.floor(pos), math.ceil(pos)
        out[f"p{round(q * 100)}"] = round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 3)
    out["max"] = round(vals[-1], 3)
    return out


def _effective_n(counts: Mapping[str, int]) -> float | None:
    total = sum(counts.values())
    if total <= 0:
        return None
    hhi = sum((c / total) ** 2 for c in counts.values())
    return round(1.0 / hhi, 3) if hhi > 0 else None


def intake_metrics(rows: Sequence[Mapping[str, Any]],
                   clock_rows: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
    """The day's intake, measured. Every count is over rows that exist; no stamp, no number.

    `raw_observations` counts every row including syndicated copies (`attributes.copies`), so the
    compression ratio is raw / unique documents: how much echo the dedup removed.
    """
    raw = 0
    docs: set[str] = set()
    stories: set[str] = set()
    events: set[str] = set()
    novel: set[str] = set()
    relevant: set[str] = set()
    langs: Counter[str] = Counter()
    regions: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    classes: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    pub_to_rx: list[float] = []
    rx_to_parse: list[float] = []
    knowable_known = received_known = 0
    for row in rows:
        raw_attrs = row.get("attributes")
        attrs: Mapping[str, Any] = raw_attrs if isinstance(raw_attrs, Mapping) else {}
        copies = int(_f(attrs.get("copies")) or 0)
        raw += 1 + max(0, copies)
        if row.get("kind") == "document":
            docs.add(str(row.get("provenance_hash") or row.get("observation_id")))
        if attrs.get("story_id"):
            stories.add(str(attrs["story_id"]))
        eid = attrs.get("event_id")
        if eid:
            events.add(str(eid))
            if (_f(attrs.get("novelty")) or 0.0) >= 0.5:
                novel.add(str(eid))
            if str(attrs.get("event_kind") or "other") != "other":
                relevant.add(str(eid))
        langs[str(row.get("language") or UNMEASURED)] += 1
        regions[str(row.get("geography") or UNMEASURED)] += 1
        domains[str(row.get("asset_domain") or UNMEASURED)] += 1
        classes[str(row.get("sensor_class") or UNMEASURED)] += 1
        sources[str(row.get("source_id") or UNMEASURED)] += 1
        pub = row.get("source_publication_time")
        if pub in (None, UNMEASURED):
            pub = row.get("publication_time")
        if pub in (None, UNMEASURED):
            pub = row.get("knowable_at")
        lat = latency_s(pub, row.get("received_at"))
        if lat is not None:
            pub_to_rx.append(lat)
        lat2 = latency_s(row.get("received_at"), row.get("parse_complete_at"))
        if lat2 is not None:
            rx_to_parse.append(lat2)
        knowable_known += int(parse_time(row.get("knowable_at")) is not None)
        received_known += int(parse_time(row.get("received_at")) is not None)
    n = len(rows)
    downstream: dict[str, list[float]] = {}
    if clock_rows:
        by_id = {str(r.get("observation_id")): r for r in rows}
        for c in clock_rows:
            src = by_id.get(str(c.get("observation_id")))
            if src is None:
                continue
            lat = latency_s(src.get("received_at"), c.get("at"))
            if lat is not None:
                downstream.setdefault(str(c.get("clock")), []).append(lat)
    unique_docs = len(docs)
    return {
        "rows": n,
        "raw_observations": raw,
        "unique_documents": unique_docs if n else UNMEASURED,
        "unique_stories": len(stories) if n else UNMEASURED,
        "unique_events": len(events) if n else UNMEASURED,
        "novel_events": len(novel) if n else UNMEASURED,
        "economically_relevant_events": len(relevant) if n else UNMEASURED,
        "duplicate_compression_ratio": (round(raw / unique_docs, 4) if unique_docs
                                        else UNMEASURED),
        "languages": dict(langs.most_common(60)),
        "regions": dict(regions.most_common(80)),
        "asset_domains": dict(domains.most_common(40)),
        "sensor_classes": dict(classes.most_common(40)),
        "source_diversity": {"distinct_sources": len(sources),
                             "effective_n": _effective_n(sources) or UNMEASURED,
                             "top": dict(sources.most_common(15))},
        "latency_s": {"publication_to_receipt": percentiles(pub_to_rx),
                      "receipt_to_classification": percentiles(rx_to_parse),
                      **{f"receipt_to_{k}": percentiles(v) for k, v in sorted(downstream.items())}},
        "pit_completeness": {
            "knowable_at": round(knowable_known / n, 4) if n else UNMEASURED,
            "received_at": round(received_known / n, 4) if n else UNMEASURED},
    }
