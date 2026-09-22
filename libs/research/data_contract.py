"""THE DATASET CONTRACT, THE VINTAGE AND THE DATA-AS-CODE LINEAGE RECORD (LAWS 5m; RESEARCH 11).

Every dataset the desk holds carries a DatasetContract with exactly the fields RESEARCH 11 names:
source, owner, acquisition method, public or licensed, licence version, permitted uses,
redistribution rights, personal-data status, MNPI review status, jurisdiction, point-in-time
timestamp, revision policy, retention policy and compliance owner. `validate()` names every
missing field BY NAME -- a field left UNMEASURED is missing, because a blank that looks like a
review is the one thing a compliance record must never contain (L1.28a).

THE LEGALITY HARD GATE. `admissible()` is False for any BLOCKED provenance state, any unresolved
MNPI review, any refused access label and any incomplete contract. It takes NO value argument on
purpose: legality is never traded against profitability, so the gate cannot even be handed the
number it must not read. `gate()` carries an expected value BESIDE the verdict for the ledger,
and the verdict is computed before the value is looked at.

VINTAGE SEMANTICS. A snapshot is immutable: `snapshot()` content-hashes the rows into a Vintage
and a LineageRecord, and `revise()` never mutates the previous vintage -- it mints a successor
that names what it supersedes, or returns the previous one unchanged when the content did not
change. `timestamp_semantics` declares which clock a row's stamp is on (`available_time` = when
the desk could have read it, `period_time` = what it describes); `revision_policy` declares how
the SOURCE behaves, so a join knows whether the newest row is the newest KNOWABLE row; `schema`
is the data contract (field -> declared type), hashed into the lineage so a silent column change
is a different dataset version.

DATA AS CODE. A LineageRecord is a content-hashed, parent-linked, code-versioned record of one
dataset version. `replay_key()` is the string an experiment cites; `verify()` answers whether the
rows in hand are the rows the experiment ran on. Pure: no I/O, no clock of its own.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Final

from libs.research.access_classifier import ACCESS_LABELS, REFUSED_LABELS

UNMEASURED: Final = "UNMEASURED"

#: EXACTLY the fields RESEARCH 11 lists, in its order. A contract is complete when every one of
#: them is filled with something other than UNMEASURED.
CONTRACT_FIELDS: Final[tuple[str, ...]] = (
    "source", "owner", "acquisition_method", "public_or_licensed", "licence_version",
    "permitted_uses", "redistribution_rights", "personal_data_status", "mnpi_review_status",
    "jurisdiction", "point_in_time_timestamp", "revision_policy", "retention_policy",
    "compliance_owner",
)

PROVENANCE_STATES: Final[tuple[str, ...]] = ("CLEAR", "QUARANTINED", "BLOCKED", UNMEASURED)
MNPI_STATES: Final[tuple[str, ...]] = ("NOT_APPLICABLE", "REVIEWED_CLEAR", "PENDING", "FLAGGED",
                                       UNMEASURED)
#: The only two MNPI states that RESOLVE the review. PENDING, FLAGGED and UNMEASURED all leave
#: the gate shut: an unreviewed dataset is not a reviewed one that happens to lack paperwork.
MNPI_RESOLVED: Final[frozenset[str]] = frozenset({"NOT_APPLICABLE", "REVIEWED_CLEAR"})
REVISION_POLICIES: Final[tuple[str, ...]] = ("IMMUTABLE_VINTAGES", "REVISED_IN_PLACE",
                                             "APPEND_ONLY", "NEVER_REVISED", UNMEASURED)
RETENTION_POLICIES: Final[tuple[str, ...]] = ("INDEFINITE", "LICENCE_TERM", "ROLLING_WINDOW",
                                              "DELETE_ON_REQUEST", UNMEASURED)
PERSONAL_DATA_STATES: Final[tuple[str, ...]] = ("NONE", "AGGREGATED", "PSEUDONYMISED",
                                                "PERSONAL", UNMEASURED)
TIMESTAMP_SEMANTICS: Final[tuple[str, ...]] = ("available_time", "period_time", "both",
                                               UNMEASURED)
#: `public_or_licensed` is spelt in the access classifier's own vocabulary, so one label means
#: one thing across the router, the ingestion ledger and this contract.
PUBLIC_OR_LICENSED: Final[tuple[str, ...]] = tuple(ACCESS_LABELS)

LEGALITY_RULE: Final = ("legality is a hard gate on the acquisition scientist, never a term "
                        "traded against profitability: a BLOCKED provenance, an unresolved MNPI "
                        "review, a refused access label or an incomplete contract is inadmissible "
                        "at any expected value")
VINTAGE_RULE: Final = ("a snapshot is immutable; a revision is a new vintage that names what it "
                       "supersedes; the previous vintage is never rewritten")

_VOCABULARY: Final[dict[str, tuple[str, ...]]] = {
    "public_or_licensed": PUBLIC_OR_LICENSED,
    "personal_data_status": PERSONAL_DATA_STATES,
    "mnpi_review_status": MNPI_STATES,
    "revision_policy": REVISION_POLICIES,
    "retention_policy": RETENTION_POLICIES,
}


def canonical(obj: Any) -> str:
    """One spelling per object, so a hash is a property of the content and not of dict order."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str,
                      ensure_ascii=False)


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode("utf-8")).hexdigest()


def hash_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[str, int]:
    """(content hash, row count) over rows in the ORDER GIVEN. Order is part of the content: a
    reordered file is a different file to a replay that reads it sequentially."""
    digest = hashlib.sha256()
    n = 0
    for row in rows:
        digest.update(canonical(row).encode("utf-8"))
        digest.update(b"\n")
        n += 1
    return digest.hexdigest(), n


def hash_schema(schema: Mapping[str, str]) -> str:
    return sha({str(k): str(v) for k, v in schema.items()})


# ------------------------------------------------------------------------------ the vintage
@dataclass(frozen=True)
class Vintage:
    """One immutable snapshot of one dataset: what it hashed to, when it was knowable, and which
    earlier vintage it supersedes (None for the first)."""

    vintage_id: str
    dataset_id: str
    snapshot_hash: str
    schema_hash: str
    point_in_time_timestamp: str
    n_rows: int
    supersedes: str | None = None
    revision_note: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> Vintage:
        return cls(vintage_id=str(doc.get("vintage_id") or ""),
                   dataset_id=str(doc.get("dataset_id") or ""),
                   snapshot_hash=str(doc.get("snapshot_hash") or ""),
                   schema_hash=str(doc.get("schema_hash") or ""),
                   point_in_time_timestamp=str(doc.get("point_in_time_timestamp") or UNMEASURED),
                   n_rows=int(doc.get("n_rows") or 0),
                   supersedes=(str(doc["supersedes"]) if doc.get("supersedes") else None),
                   revision_note=str(doc.get("revision_note") or ""))


# ------------------------------------------------------------------------------ the contract
@dataclass(frozen=True)
class Admission:
    """The legality verdict. `expected_value` is CARRIED for the ledger; it is never an input."""

    admitted: bool
    reasons: tuple[str, ...]
    expected_value: float | None = None
    rule: str = LEGALITY_RULE

    def to_json(self) -> dict[str, Any]:
        return {"admitted": self.admitted, "reasons": list(self.reasons),
                "expected_value": self.expected_value, "rule": self.rule}


@dataclass(frozen=True)
class DatasetContract:
    """The fourteen RESEARCH-11 fields plus the vintage/snapshot semantics that make a dataset
    a replayable, versioned, legally-described object rather than a file."""

    dataset_id: str
    source: str = UNMEASURED
    owner: str = UNMEASURED
    acquisition_method: str = UNMEASURED
    public_or_licensed: str = UNMEASURED
    licence_version: str = UNMEASURED
    permitted_uses: tuple[str, ...] = ()
    redistribution_rights: str = UNMEASURED
    personal_data_status: str = UNMEASURED
    mnpi_review_status: str = UNMEASURED
    jurisdiction: str = UNMEASURED
    point_in_time_timestamp: str = UNMEASURED
    revision_policy: str = UNMEASURED
    retention_policy: str = UNMEASURED
    compliance_owner: str = UNMEASURED
    #: CLEAR / QUARANTINED / BLOCKED / UNMEASURED, from the access router's verdict.
    provenance_state: str = UNMEASURED
    #: The data contract: field -> declared type. Hashed into every lineage record.
    schema: Mapping[str, str] = field(default_factory=dict)
    timestamp_semantics: str = UNMEASURED
    vintage: Vintage | None = None
    notes: str = ""

    # -- completeness ----------------------------------------------------------------------
    def missing(self) -> tuple[str, ...]:
        """The RESEARCH-11 fields this contract has not filled, by name, in the law's order."""
        out: list[str] = []
        for name in CONTRACT_FIELDS:
            value = getattr(self, name)
            if name == "permitted_uses":
                if not value:
                    out.append(name)
            elif not isinstance(value, str) or not value.strip() or value == UNMEASURED:
                out.append(name)
        return tuple(out)

    def validate(self) -> list[str]:
        """Every problem, each one starting with the field it is about. Empty means complete."""
        problems = [f"{name}: missing" for name in self.missing()]
        for name, vocabulary in _VOCABULARY.items():
            value = getattr(self, name)
            if value != UNMEASURED and value not in vocabulary:
                problems.append(f"{name}: {value!r} is not one of {list(vocabulary)}")
        if self.provenance_state not in PROVENANCE_STATES:
            problems.append(f"provenance_state: {self.provenance_state!r} is not one of "
                            f"{list(PROVENANCE_STATES)}")
        if self.timestamp_semantics not in TIMESTAMP_SEMANTICS:
            problems.append(f"timestamp_semantics: {self.timestamp_semantics!r} is not one of "
                            f"{list(TIMESTAMP_SEMANTICS)}")
        if not self.dataset_id.strip():
            problems.append("dataset_id: missing")
        return problems

    @property
    def complete(self) -> bool:
        return not self.validate()

    # -- the legality hard gate --------------------------------------------------------------
    def admission(self) -> Admission:
        """Why the gate is open or shut. No profitability term exists in this method."""
        reasons: list[str] = []
        if self.provenance_state == "BLOCKED":
            reasons.append("provenance_state is BLOCKED")
        elif self.provenance_state == "QUARANTINED":
            reasons.append("provenance_state is QUARANTINED: metadata kept, content not consumed")
        elif self.provenance_state == UNMEASURED:
            reasons.append("provenance_state is UNMEASURED: absence is not permission")
        if self.mnpi_review_status not in MNPI_RESOLVED:
            reasons.append(f"mnpi_review_status {self.mnpi_review_status!r} is unresolved")
        if self.public_or_licensed in REFUSED_LABELS:
            reasons.append(f"access label {self.public_or_licensed} is refused")
        if self.personal_data_status == "PERSONAL":
            reasons.append("personal data without aggregation or pseudonymisation")
        problems = self.validate()
        if problems:
            reasons.append("contract incomplete: " + "; ".join(problems[:6]))
        return Admission(admitted=not reasons, reasons=tuple(reasons))

    def admissible(self) -> bool:
        return self.admission().admitted

    # -- serialisation -----------------------------------------------------------------------
    def to_json(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["permitted_uses"] = list(self.permitted_uses)
        doc["schema"] = dict(self.schema)
        doc["vintage"] = self.vintage.to_json() if self.vintage is not None else None
        doc["contract_hash"] = self.content_hash()
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> DatasetContract:
        kw: dict[str, Any] = {}
        for name in (*CONTRACT_FIELDS, "provenance_state", "timestamp_semantics", "notes"):
            if name != "permitted_uses" and doc.get(name) is not None:
                kw[name] = str(doc[name])
        uses = doc.get("permitted_uses")
        kw["permitted_uses"] = tuple(str(u) for u in uses) if isinstance(uses, (list, tuple)) \
            else ()
        schema = doc.get("schema")
        kw["schema"] = {str(k): str(v) for k, v in schema.items()} \
            if isinstance(schema, Mapping) else {}
        vintage = doc.get("vintage")
        kw["vintage"] = Vintage.from_json(vintage) if isinstance(vintage, Mapping) else None
        return cls(dataset_id=str(doc.get("dataset_id") or ""), **kw)

    def content_hash(self) -> str:
        """The contract's own identity: every field except the vintage (which hashes the data)."""
        doc = asdict(self)
        doc.pop("vintage", None)
        doc["permitted_uses"] = sorted(self.permitted_uses)
        return sha(doc)


def provenance_from_verdict(*, refused: bool, quarantine: bool) -> str:
    """The access router's verdict in this contract's vocabulary."""
    if refused:
        return "BLOCKED"
    if quarantine:
        return "QUARANTINED"
    return "CLEAR"


def gate(contract: DatasetContract, expected_value: float | None) -> Admission:
    """The verdict, with the expected value CARRIED beside it for the ledger.

    The verdict is fully computed before `expected_value` is touched, and `expected_value` is
    only ever copied into the record: a BLOCKED contract is inadmissible at any value.
    """
    verdict = contract.admission()
    return replace(verdict, expected_value=expected_value)


# ------------------------------------------------------------------------------ lineage
@dataclass(frozen=True)
class LineageRecord:
    """Data as code: one dataset version, content-hashed, parent-linked and code-versioned."""

    dataset_id: str
    vintage_id: str
    content_hash: str
    schema_hash: str
    contract_hash: str
    parents: tuple[str, ...]
    transform: str
    code_version: str
    recorded_at: str
    n_rows: int = 0

    @property
    def lineage_id(self) -> str:
        return sha({"dataset_id": self.dataset_id, "vintage_id": self.vintage_id,
                    "content_hash": self.content_hash, "schema_hash": self.schema_hash,
                    "contract_hash": self.contract_hash, "parents": list(self.parents),
                    "transform": self.transform, "code_version": self.code_version})[:32]

    def to_json(self) -> dict[str, Any]:
        doc = asdict(self)
        doc["parents"] = list(self.parents)
        doc["lineage_id"] = self.lineage_id
        doc["replay_key"] = replay_key(self)
        return doc

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> LineageRecord:
        parents = doc.get("parents")
        return cls(dataset_id=str(doc.get("dataset_id") or ""),
                   vintage_id=str(doc.get("vintage_id") or ""),
                   content_hash=str(doc.get("content_hash") or ""),
                   schema_hash=str(doc.get("schema_hash") or ""),
                   contract_hash=str(doc.get("contract_hash") or ""),
                   parents=tuple(str(p) for p in parents) if isinstance(parents, list) else (),
                   transform=str(doc.get("transform") or ""),
                   code_version=str(doc.get("code_version") or UNMEASURED),
                   recorded_at=str(doc.get("recorded_at") or UNMEASURED),
                   n_rows=int(doc.get("n_rows") or 0))


@dataclass(frozen=True)
class Snapshot:
    contract: DatasetContract
    vintage: Vintage
    lineage: LineageRecord


def replay_key(record: LineageRecord) -> str:
    """What an experiment cites: dataset, vintage, content and code, in one string."""
    return (f"{record.dataset_id}@{record.vintage_id}#{record.content_hash[:16]}"
            f"~{record.code_version[:12] or UNMEASURED}")


def verify(record: LineageRecord, rows: Iterable[Mapping[str, Any]]) -> bool:
    """Are these rows the rows the record hashed? The replay question, answered exactly."""
    digest, n = hash_rows(rows)
    return digest == record.content_hash and n == record.n_rows


def snapshot(contract: DatasetContract, rows: Sequence[Mapping[str, Any]], *, at: str,
             code_version: str, parents: Sequence[str] = (), transform: str = "ingest",
             vintage_id: str | None = None) -> Snapshot:
    """An immutable first vintage of `rows` under `contract`, with its lineage record.

    The vintage id is derived from the content unless the caller names one, so the same rows
    under the same contract snapshot to the same id on every machine.
    """
    digest, n = hash_rows(rows)
    schema_hash = hash_schema(contract.schema)
    vid = vintage_id or f"v-{digest[:12]}"
    vintage = Vintage(vintage_id=vid, dataset_id=contract.dataset_id, snapshot_hash=digest,
                      schema_hash=schema_hash, point_in_time_timestamp=at, n_rows=n)
    stamped = replace(contract, vintage=vintage,
                      point_in_time_timestamp=(contract.point_in_time_timestamp
                                               if contract.point_in_time_timestamp != UNMEASURED
                                               else at))
    lineage = LineageRecord(dataset_id=contract.dataset_id, vintage_id=vid, content_hash=digest,
                            schema_hash=schema_hash, contract_hash=stamped.content_hash(),
                            parents=tuple(parents), transform=transform,
                            code_version=code_version, recorded_at=at, n_rows=n)
    return Snapshot(contract=stamped, vintage=vintage, lineage=lineage)


def revise(previous: Snapshot, rows: Sequence[Mapping[str, Any]], *, at: str, code_version: str,
           note: str = "") -> Snapshot:
    """A successor vintage, or `previous` itself when the content is unchanged.

    `previous` is never mutated -- every object here is frozen -- and the successor names what it
    supersedes, so a join can walk back to the vintage an experiment actually ran on. Under
    REVISED_IN_PLACE the SOURCE overwrote history; the desk still keeps both vintages, which is
    the only way "what did the desk know at t" stays answerable.
    """
    digest, n = hash_rows(rows)
    if digest == previous.vintage.snapshot_hash and n == previous.vintage.n_rows:
        return previous
    contract = previous.contract
    schema_hash = hash_schema(contract.schema)
    vid = f"v-{digest[:12]}"
    vintage = Vintage(vintage_id=vid, dataset_id=contract.dataset_id, snapshot_hash=digest,
                      schema_hash=schema_hash, point_in_time_timestamp=at, n_rows=n,
                      supersedes=previous.vintage.vintage_id,
                      revision_note=note or f"revision under {contract.revision_policy}")
    stamped = replace(contract, vintage=vintage)
    lineage = LineageRecord(dataset_id=contract.dataset_id, vintage_id=vid, content_hash=digest,
                            schema_hash=schema_hash, contract_hash=stamped.content_hash(),
                            parents=(previous.lineage.lineage_id,), transform="revise",
                            code_version=code_version, recorded_at=at, n_rows=n)
    return Snapshot(contract=stamped, vintage=vintage, lineage=lineage)


def lineage_chain(records: Iterable[LineageRecord], lineage_id: str, *, depth: int = 64
                  ) -> list[LineageRecord]:
    """The record and its ancestors, nearest first, as far as the records in hand reach."""
    by_id = {r.lineage_id: r for r in records}
    out: list[LineageRecord] = []
    frontier = [lineage_id]
    seen: set[str] = set()
    while frontier and len(out) < depth:
        current = frontier.pop(0)
        rec = by_id.get(current)
        if rec is None or current in seen:
            continue
        seen.add(current)
        out.append(rec)
        frontier.extend(rec.parents)
    return out


__all__ = [
    "CONTRACT_FIELDS", "LEGALITY_RULE", "MNPI_RESOLVED", "MNPI_STATES", "PERSONAL_DATA_STATES",
    "PROVENANCE_STATES", "PUBLIC_OR_LICENSED", "RETENTION_POLICIES", "REVISION_POLICIES",
    "TIMESTAMP_SEMANTICS", "UNMEASURED", "VINTAGE_RULE", "Admission", "DatasetContract",
    "LineageRecord", "Snapshot", "Vintage", "canonical", "gate", "hash_rows", "hash_schema",
    "lineage_chain", "provenance_from_verdict", "replay_key", "revise", "sha", "snapshot",
    "verify",
]
