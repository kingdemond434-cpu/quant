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
#: HOW the knowable instant was established. A first-class field, never an attribute, because a
#: joiner must be able to refuse a row whose world clock is a guess:
#:   printed_stamp       the agency's or source's own publication stamp, read off the record
#:   calendar            a published release calendar's scheduled instant (the print was on time)
#:   declared_lag        the event/period time plus a lag the producer DECLARES (e.g. close + 1 day)
#:   bounded_by_receipt  no world stamp exists; knowable_at is set to receipt, the latest it can be
KNOWABLE_BASES: tuple[str, ...] = ("printed_stamp", "calendar", "declared_lag",
                                   "bounded_by_receipt")
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
    knowable_basis: str = UNMEASURED
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
    if obs.knowable_basis != UNMEASURED and obs.knowable_basis not in KNOWABLE_BASES:
        out.append(f"knowable_basis {obs.knowable_basis!r} is not one of {KNOWABLE_BASES}")
    if obs.knowable_at != UNMEASURED and obs.knowable_basis == UNMEASURED:
        out.append("knowable_at is stamped but knowable_basis is not: say whether it was printed, "
                   "scheduled, a declared lag or bounded by receipt")
    if (obs.knowable_basis == "bounded_by_receipt" and obs.knowable_at != UNMEASURED
            and obs.received_at != UNMEASURED and obs.knowable_at != obs.received_at):
        out.append("knowable_basis bounded_by_receipt requires knowable_at == received_at")
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


class LedgerIndexCorrupt(RuntimeError):
    """The revision index exists and cannot be read. Nothing is appended and nothing is reset:
    a silently re-created index would re-admit every vintage as new and every revision as a
    first print, which is exactly the corruption the index exists to prevent."""


def _vintage_key(knowable_at: str) -> datetime:
    return parse_time(knowable_at) or datetime.min.replace(tzinfo=UTC)


class SensorLedger:
    """Append-only, day-sharded observation ledger with vintage-keyed revision detection.

    Shards are `observations/<YYYY-MM-DD>.jsonl` by RECEIPT day, so a day's intake is one file
    and the throughput meter reads exactly one shard. Documents are deduplicated by observation
    id within the shard.

    NUMERIC OBSERVATIONS ARE KEYED BY (series, period, vintage): series = sensor|entity|metric,
    period = event_time, vintage = knowable_at. The index holds every vintage of every key, so:
      * the same vintage re-sent is a DUPLICATE (same value) or a refused CONFLICT (a different
        value for a vintage already held), never a new row;
      * an observation id ever admitted under a key is a duplicate, so a producer that re-sends
        its first print after the revision (every pass, every day) appends nothing;
      * a new vintage revises the vintage BEFORE it in knowable order (revision_of, delta, n),
        and a vintage that arrives late (older than one already held) is appended as history
        with `late_vintage`, never as a revision of the newer value;
      * the index is updated only AFTER the shard write succeeded, and a corrupt index fails
        closed (`LedgerIndexCorrupt`): nothing is appended and nothing is reset.
    `as_of` answers what the ledger said a key was worth at any instant; `latest` the newest.

    The shards are box-local state and are NOT committed (`.gitignore`): the hourly
    `sensor_ledger` leg publishes `desks/mt5/reports/SENSOR_LEDGER.json` (see `digest`) instead.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_root()
        self.obs_dir = self.root / "observations"
        self.clock_dir = self.root / "clocks"
        self.index_path = self.root / "latest_numeric.json"
        self._index: dict[str, dict[str, Any]] | None = None
        self._seen: dict[str, set[str]] = {}

    # -- internals
    def _shard(self, day: str, kind: str = "observations") -> Path:
        base = self.obs_dir if kind == "observations" else self.clock_dir
        return base / f"{day}.jsonl"

    @staticmethod
    def _entry(raw: Any) -> dict[str, Any]:
        """One index entry in the vintage form. The pre-vintage list form [id, value, n, ids]
        is read as a single vintage of unknown knowable instant."""
        if isinstance(raw, dict) and isinstance(raw.get("vintages"), list):
            return {"vintages": [list(v) for v in raw["vintages"]],
                    "ids": [str(i) for i in raw.get("ids") or []]}
        if isinstance(raw, list) and len(raw) >= 3:
            ids = [str(raw[0])] + ([str(i) for i in raw[3]] if len(raw) > 3
                                   and isinstance(raw[3], list) else [])
            return {"vintages": [[UNMEASURED, str(raw[0]), _f(raw[1]), int(raw[2])]],
                    "ids": sorted(set(ids))}
        raise LedgerIndexCorrupt(f"unreadable index entry {str(raw)[:80]!r}")

    def _load_index(self) -> dict[str, dict[str, Any]]:
        if self._index is None:
            if not self.index_path.exists():
                self._index = {}
                return self._index
            try:
                doc = json.loads(self.index_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise LedgerIndexCorrupt(f"{self.index_path}: {type(exc).__name__}: "
                                         f"{str(exc)[:120]}") from exc
            if not isinstance(doc, dict):
                raise LedgerIndexCorrupt(f"{self.index_path}: not a JSON object")
            self._index = {str(k): self._entry(v) for k, v in doc.items()}
        return self._index

    def _seen_ids(self, day: str) -> set[str]:
        if day not in self._seen:
            ids: set[str] = set()
            path = self._shard(day)
            if path.is_file():
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

    @staticmethod
    def _key(sensor_id: str, entity: str, metric: str, event_time: Any) -> str:
        return "|".join((sensor_id, entity, metric, iso(event_time)))

    # -- public
    def latest(self, sensor_id: str, entity: str, metric: str, event_time: Any
               ) -> dict[str, Any] | None:
        """The newest vintage held for one key: {observation_id, value, revision_n, knowable_at,
        known_ids}, or None. The public read of the index; never open `index_path` directly."""
        entry = self._load_index().get(self._key(sensor_id, entity, metric, event_time))
        if not entry or not entry["vintages"]:
            return None
        v = max(entry["vintages"], key=lambda r: _vintage_key(r[0]))
        return {"observation_id": str(v[1]), "value": _f(v[2]), "revision_n": int(v[3]),
                "knowable_at": str(v[0]), "known_ids": sorted(entry["ids"])}

    def as_of(self, sensor_id: str, entity: str, metric: str, event_time: Any, at: Any
              ) -> dict[str, Any] | None:
        """What the ledger held for one key at instant `at`: the newest vintage whose knowable
        instant is at or before it. A vintage of unmeasured knowable instant is never returned."""
        t = parse_time(at)
        entry = self._load_index().get(self._key(sensor_id, entity, metric, event_time))
        if t is None or not entry:
            return None
        held = [v for v in entry["vintages"]
                if parse_time(v[0]) is not None and _vintage_key(v[0]) <= t]
        if not held:
            return None
        v = max(held, key=lambda r: _vintage_key(r[0]))
        return {"observation_id": str(v[1]), "value": _f(v[2]), "revision_n": int(v[3]),
                "knowable_at": str(v[0])}

    def latest_index(self) -> dict[str, dict[str, Any]]:
        """Every key's newest vintage, keyed `sensor|entity|metric|event_time`."""
        out: dict[str, dict[str, Any]] = {}
        for k, entry in self._load_index().items():
            if entry["vintages"]:
                v = max(entry["vintages"], key=lambda r: _vintage_key(r[0]))
                out[k] = {"observation_id": str(v[1]), "value": _f(v[2]),
                          "revision_n": int(v[3])}
        return out

    def append(self, observations: Iterable[SensorObservation],
               now: datetime | None = None) -> dict[str, Any]:
        """Append what is new; a new vintage becomes a revision row. Returns the census."""
        when = now or datetime.now(UTC)
        try:
            index = self._load_index()
        except LedgerIndexCorrupt as exc:
            return {"status": "INDEX_CORRUPT", "why": str(exc), "appended": 0,
                    "duplicates": 0, "revisions": 0, "conflicts": 0, "refused": 0,
                    "refusals": [], "shards": []}
        staged: dict[str, dict[str, Any]] = {}
        by_day: dict[str, list[str]] = {}
        new_ids: dict[str, set[str]] = {}
        refused: list[dict[str, Any]] = []
        n_new = n_dup = n_rev = n_conf = 0
        for obs in observations:
            bad = defects(obs)
            if bad:
                refused.append({"observation_id": obs.observation_id, "defects": bad[:4]})
                continue
            received = parse_time(obs.received_at) or when
            day = received.date().isoformat()
            seen = self._seen_ids(day) | new_ids.get(day, set())
            key = ""
            if obs.value is not None and obs.kind != "document" and obs.event_time != UNMEASURED:
                key = self.revision_key(obs)
                if key in staged:
                    entry = staged[key]
                elif key in index:
                    entry = self._entry(index[key])          # a copy: staged until written
                else:
                    entry = {"vintages": [], "ids": []}
                if obs.observation_id in entry["ids"]:
                    n_dup += 1
                    continue
                same = [v for v in entry["vintages"] if v[0] == obs.knowable_at]
                if same:
                    if _f(same[0][2]) == obs.value:
                        n_dup += 1
                    else:
                        n_conf += 1
                        refused.append({"observation_id": obs.observation_id,
                                        "defects": [f"vintage conflict: {key} @ "
                                                    f"{obs.knowable_at} is already held as "
                                                    f"{same[0][2]}, not {obs.value}"]})
                    continue
                order = sorted(entry["vintages"], key=lambda r: _vintage_key(r[0]))
                before = [v for v in order if _vintage_key(v[0]) < _vintage_key(obs.knowable_at)]
                later = len(before) < len(order)
                pred = before[-1] if before else None
                if pred is not None and _f(pred[2]) == obs.value and not later:
                    n_dup += 1                     # restated unchanged: nothing new to hold
                    continue
                if obs.observation_id in seen:
                    n_dup += 1
                    continue
                if pred is not None and not obs.revision_of:
                    attrs = dict(obs.attributes)
                    if later:
                        attrs["late_vintage"] = True
                    obs = make(**{**asdict(obs), "revision_of": str(pred[1]),
                                  "revision_delta": round(obs.value - float(pred[2]), 12),
                                  "revision_n": int(pred[3]) + 1, "observation_id": "",
                                  "attributes": attrs})
                    n_rev += 1
                elif later:
                    obs = make(**{**asdict(obs), "observation_id": "",
                                  "attributes": {**dict(obs.attributes), "late_vintage": True}})
                entry["vintages"].append([obs.knowable_at, obs.observation_id, obs.value,
                                          obs.revision_n])
                entry["ids"] = sorted(set(entry["ids"]) | {obs.observation_id})
                staged[key] = entry
            elif obs.observation_id in seen:
                n_dup += 1
                continue
            new_ids.setdefault(day, set()).add(obs.observation_id)
            by_day.setdefault(day, []).append(json.dumps(obs.to_row(), default=str,
                                                         ensure_ascii=False))
            n_new += 1
        written: list[str] = []
        try:
            for day, lines in by_day.items():
                path = self._shard(day)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as fh:
                    fh.write("\n".join(lines) + "\n")
                written.append(day)
                self._seen_ids(day).update(new_ids.get(day, set()))
        except OSError as exc:
            return {"status": "WRITE_FAILED", "why": f"{type(exc).__name__}: {exc}",
                    "appended": 0, "duplicates": n_dup, "revisions": 0, "conflicts": n_conf,
                    "refused": len(refused), "refusals": refused[:8], "shards": written}
        if staged:
            # THE INDEX MOVES ONLY AFTER THE ROWS IT DESCRIBES ARE ON DISK.
            index.update(staged)
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(index, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.index_path)
        return {"status": "OK", "appended": n_new, "duplicates": n_dup, "revisions": n_rev,
                "conflicts": n_conf, "refused": len(refused), "refusals": refused[:8],
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


# ============================================================================== the digest
def digest(ledger: SensorLedger | None = None, now: datetime | None = None,
           days: int = 2) -> dict[str, Any]:
    """What the ledger holds, published where git can carry it. The shards themselves stay on
    the box; this is their measured summary: per receipt day the intake metrics (with the
    downstream clock joins), and for the whole ledger the shard count and bytes, the revision
    index size and how many keys were revised. A ledger with no shard is UNMEASURED, never 0."""
    led = ledger or SensorLedger()
    when = now or datetime.now(UTC)
    shards = sorted(led.obs_dir.glob("*.jsonl")) if led.obs_dir.exists() else []
    try:
        index = led.latest_index()
        index_status = "OK"
    except LedgerIndexCorrupt as exc:
        index, index_status = {}, f"INDEX_CORRUPT: {exc}"
    per_day: dict[str, Any] = {}
    for back in range(max(1, days)):
        day = (when - timedelta(days=back)).date().isoformat()
        rows = led.rows(day)
        per_day[day] = (intake_metrics(rows, led.clock_rows(day)) if rows
                        else {"rows": 0, "status": UNMEASURED,
                              "why": "no observation shard for this receipt day"})
    return {
        "schema": "sensor_ledger_digest/1",
        "at": when.isoformat(timespec="seconds"),
        "root": str(led.root),
        "status": "MEASURED" if shards else UNMEASURED,
        "why": "" if shards else "the ledger has no observation shard on this host yet",
        "shards": len(shards),
        "shard_bytes": sum(p.stat().st_size for p in shards),
        "first_day": shards[0].stem if shards else UNMEASURED,
        "last_day": shards[-1].stem if shards else UNMEASURED,
        "index_status": index_status,
        "index_keys": len(index),
        "revised_keys": sum(1 for v in index.values() if v["revision_n"] > 0),
        "days": per_day,
        "authority": AUTHORITY,
    }
