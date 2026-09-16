"""THE RECORD THAT MAKES A CERTIFICATE AUDITABLE: source -> claim -> hypothesis -> code ->
data -> config -> result -> review, hash-linked, append-only, never rewritten.

A CERTIFICATE IS A CLAIM. It says a cell passed ten gates. It does not say which bytes of which
parquet it was measured on, which revision of the family function produced the signals, which
gauntlet settings were in force, or whether anybody reproduced it afterwards. Every one of those
can change without the certificate changing, and when they do the certificate is still green and
no longer true. The chain is the record that turns the claim into something a later reader can
prosecute.

WHAT IS ACTUALLY MISSING TODAY, measured on this box 2026-09-16. All 3,364 rows of
`desks/mt5/data/hypotheses/gate_verdict_ledger.jsonl` carry exactly seven keys -- `at`, `cell`,
`sym`, `family`, `passed`, `terminal_gate`, `downstream_status` -- and not one of them names the
bars, the code or the config that produced the verdict. `libs/ops/compute_ledger.close_run`
publishes the provenance envelope (`commit_sha`, `config_hash`, `input_hash`, `output_hash`) per
RUN, which is the right envelope attached to the wrong noun: a run is an hour of the scheduler,
not an experiment, and the envelope dies with the row. So the desk can say what an hour cost and
what a cell scored, and cannot join the two.

A NEW EXPERIMENT IS A NEW ARTIFACT. Nothing here is ever updated in place. Re-running a cell on
fresher bars appends a NEW data record, a NEW config, a NEW result; the old ones stay exactly
where they were, still linked, still verifiable. That is not tidiness -- it is the only way a
result that was true in August and false in September reads as two facts instead of one
overwritten one. `libs/research/artifacts.py` carries the CANDIDATE whole from idea to
retirement and is the right object to hold mutable-by-transition state; this file is its
immutable shadow, and the two are joined by `hypothesis_payload(artifact=...)`.

IDENTITIES ARE IMPORTED, NEVER RE-DERIVED. `cell_id` comes from the desk's
`research/frontier_identity`, `code_hash` and `behaviour_hash` from `research/sleeve_registry`,
`vintage_id_for` from `libs/data/pit_stamp`, `commit_sha` from `libs/ops/compute_ledger`. This
desk has already paid for a second spelling of one identity -- `run_key` building `AUDCHF.asia#`
while `sleeve_key` built `AUDCHF.overnight_gap_decay.asia`, and the first check that ever compared
them reporting 34 of 35 running certificates as having no clock. A chain that minted its own cell
ids would be the same defect with a hash on it.

TWO HASHES PER RECORD, AND THEY CATCH DIFFERENT LIES.

    payload_hash  sha256 of the canonical payload. Editing what a record SAYS breaks it.
    chain_hash    sha256(previous line's chain_hash + this payload_hash). Inserting, deleting or
                  reordering lines breaks this even when every payload is untouched.

`artifact_id` is a sha256 over (kind, at, prev, the chain anchor, payload_hash): position is part
of identity, so the same payload appended twice is two artifacts and neither can be moved.
Forging a record therefore means rewriting every line after it, which is visible in one `git
diff` of an append-only file. `verify()` is the only reader that recomputes every hash; `append`
reads the file to resolve `prev` and the tail but hashes nothing, so the hot path stays cheap.

ORDER IS ENFORCED, AND EXACTLY ONE ORPHAN IS LEGAL. A record's kind must be the immediate
successor of its predecessor's: a result may follow a config and nothing else, a review may
follow a result and nothing else. The single exception is a hypothesis whose source is unknown --
the desk mints those (a family sweep is nobody's claim), and refusing to record them would mean
the chain holds only the minority of work that began in a document. Such a record starts its own
lineage and is flagged `orphan_lineage`, so "we cannot name where this came from" is a MEASURED
property of the chain rather than a silence.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

ROOT = Path(__file__).resolve().parents[2]
CHAIN = ROOT / "desks" / "mt5" / "data" / "research_artifacts.jsonl"

#: The spine, in order. `_ORDER` makes "immediate successor" arithmetic rather than a table.
KINDS: tuple[str, ...] = (
    "source", "claim", "hypothesis", "code", "data", "config", "result", "review",
)
_ORDER: dict[str, int] = {k: i for i, k in enumerate(KINDS)}

#: Kinds that may begin a lineage with no predecessor. `hypothesis` is here because the desk's
#: own sweeps mint hypotheses nobody claimed; it is flagged, never silently blessed.
ROOT_KINDS = frozenset({"source", "hypothesis"})

#: The blind reviewer's vocabulary, adopted unchanged. UNMEASURED is a verdict (L1.28a).
VERDICTS: tuple[str, ...] = ("PASS", "VETO", "UNMEASURED")

#: Keys every payload of a kind MUST carry. A value may be None -- that is "unknown", which is a
#: real answer -- but the KEY must be present, because an absent key cannot be told apart from a
#: field the writer forgot.
REQUIRED: dict[str, tuple[str, ...]] = {
    "source": ("source_id", "url_or_ground", "retrieved_at", "source_hash"),
    "claim": ("text_hash", "mechanism", "actor", "language"),
    "hypothesis": ("cell_id", "symbol", "family", "params", "falsifier"),
    "code": ("code_hash", "behaviour_hash", "family"),
    "data": ("bars_digest", "vintage_ids"),
    "config": ("config_hash", "settings_digest"),
    "result": ("stages_digest", "passed", "n", "expectancy", "t", "output_hash"),
    "review": ("verdict", "reviewer", "reproduced_digest"),
}

#: What `latest(kind, key)` will match a key against, per kind, newest first. `artifact_id` is
#: always accepted too, so a caller holding an id never needs to know which field names it.
KEY_FIELDS: dict[str, tuple[str, ...]] = {
    "source": ("source_id", "url_or_ground"),
    "claim": ("text_hash", "mechanism"),
    "hypothesis": ("cell_id", "symbol"),
    "code": ("code_hash", "behaviour_hash", "family"),
    "data": ("digest", "symbol"),
    "config": ("config_hash", "cell"),
    "result": ("output_hash", "cell", "stages_digest"),
    "review": ("cell", "reviewer", "verdict"),
}


class ChainError(RuntimeError):
    """The chain refused something. Raised, never logged-and-continued."""


class ChainOrderError(ChainError):
    """A kind that cannot follow its predecessor, or a lineage that does not match."""


class UnknownPrev(ChainError):
    """A predecessor that is not in the chain. A link to nothing is not provenance."""


class PayloadError(ChainError):
    """A payload missing a field its kind requires, or a verdict outside the vocabulary."""


# --------------------------------------------------------------------------------- hashing

def _canon(obj: Any) -> str:
    """One spelling per value. `default=str` on both sides of the file, so a Path hashed before
    the write and the string read back after it agree."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def digest(obj: Any) -> str:
    """sha256 of the canonical form of anything JSON can carry."""
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    """The bytes of one file, streamed. None when it cannot be read -- never an empty-file hash,
    which would make an unreadable parquet look identical to every other unreadable parquet."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            while True:
                block = fh.read(1 << 20)
                if not block:
                    break
                h.update(block)
    except OSError:
        return None
    return h.hexdigest()


def _chain_hash(prev_chain_hash: str | None, payload_hash: str) -> str:
    return hashlib.sha256(((prev_chain_hash or "") + payload_hash).encode("utf-8")).hexdigest()


def _artifact_id(kind: str, at: str, prev: str | None, anchor: str | None,
                 payload_hash: str) -> str:
    """Identity over the payload AND its position.

    `at` and `anchor` (the tail chain_hash this record was appended onto) ride in the preimage so
    that appending the same payload twice yields two artifacts. That is the point: a new
    experiment is a new artifact even when it is the same experiment run again.
    """
    seed = _canon({"kind": kind, "at": at, "prev": prev, "anchor": anchor,
                   "payload_hash": payload_hash})
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


# --------------------------------------------------------------------------------- records

@dataclass(frozen=True)
class Record:
    """One immutable link. Frozen: `record.payload = {}` raises rather than quietly succeeding."""

    artifact_id: str
    kind: str
    at: str
    prev: str | None
    lineage_id: str
    payload: dict[str, Any]
    payload_hash: str
    chain_hash: str
    orphan_lineage: bool = False

    def to_row(self) -> dict[str, Any]:
        return {"artifact_id": self.artifact_id, "kind": self.kind, "at": self.at,
                "prev": self.prev, "lineage_id": self.lineage_id, "payload": self.payload,
                "payload_hash": self.payload_hash, "chain_hash": self.chain_hash,
                "orphan_lineage": self.orphan_lineage}


@dataclass(frozen=True)
class Verification:
    """What a full walk of the chain found. `ok` False with `first_break` names the line."""

    n: int
    ok: bool
    first_break: int | None
    reason: str | None
    by_kind: dict[str, int]
    orphan_lineages: list[str]
    lineages: int
    path: str

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "ok": self.ok, "first_break": self.first_break,
                "reason": self.reason, "by_kind": dict(self.by_kind),
                "orphan_lineages": list(self.orphan_lineages), "lineages": self.lineages,
                "path": self.path}


def _to_record(row: Any) -> Record | None:
    """A parsed line as a Record, or None when the line is not one. Tolerant on purpose: the
    readers below must not die on a line the writers of tomorrow added a field to."""
    if not isinstance(row, dict):
        return None
    aid, kind = row.get("artifact_id"), row.get("kind")
    payload = row.get("payload")
    if not isinstance(aid, str) or not isinstance(kind, str) or not isinstance(payload, dict):
        return None
    prev = row.get("prev")
    return Record(artifact_id=aid, kind=kind, at=str(row.get("at") or ""),
                  prev=str(prev) if isinstance(prev, str) and prev else None,
                  lineage_id=str(row.get("lineage_id") or aid), payload=dict(payload),
                  payload_hash=str(row.get("payload_hash") or ""),
                  chain_hash=str(row.get("chain_hash") or ""),
                  orphan_lineage=bool(row.get("orphan_lineage")))


# --------------------------------------------------------------------------------- the lock

def _acquire(fh: BinaryIO, timeout_s: float) -> bool:
    """Exclusive lock on byte 0 of the sidecar, polled. False when the wait expired -- tolerant:
    a chain that stopped accepting appends because a stale lock outlived its process would lose
    evidence, and one whole line written under contention is still one whole line."""
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            if sys.platform == "win32":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, ImportError):
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


def _release(fh: BinaryIO) -> None:
    with suppress(OSError, ImportError):
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def lock_path(path: Path) -> Path:
    """The sidecar the lock is taken on. Never the chain itself: locking the file being appended
    to would make a reader's open the thing that blocks a write."""
    return path.with_name(path.name + ".lock")


@contextmanager
def _locked(path: Path, timeout_s: float = 10.0) -> Iterator[bool]:
    """Serialise appends across processes. Yields whether the lock was actually held, and ALWAYS
    releases -- the sidecar is left on disk (deleting it races every other holder on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path(path)
    try:
        fh = lock.open("a+b")
    except OSError:
        yield False
        return
    held = False
    try:
        if fh.tell() == 0:
            fh.write(b"\0")
            fh.flush()
        held = _acquire(fh, timeout_s)
        yield held
    finally:
        if held:
            _release(fh)
        with suppress(OSError):
            fh.close()


# --------------------------------------------------------------------------------- appending

@dataclass(frozen=True)
class _Index:
    ids: dict[str, tuple[str, str]]     # artifact_id -> (kind, lineage_id)
    tail: str | None                    # chain_hash of the last line
    n: int


def _read_index(path: Path) -> _Index:
    """One cheap pass: what ids exist, and what the tail hash is. No hashing -- `verify` owns
    that. A chain that does not parse RAISES: appending onto an unreadable history would put a
    valid-looking record on top of a corrupt one and hide the corruption under it."""
    try:
        text = path.read_text("utf-8")
    except FileNotFoundError:
        return _Index({}, None, 0)
    except OSError as exc:
        raise ChainError(f"{path} exists but could not be read ({type(exc).__name__}: {exc}); "
                         f"refusing to treat an unreadable chain as an empty one") from exc
    ids: dict[str, tuple[str, str]] = {}
    tail: str | None = None
    n = 0
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ChainError(f"{path}: line {lineno} is not JSON ({exc}); refusing to append "
                             f"onto a broken chain -- run verify() and repair by appending, "
                             f"never by editing") from exc
        rec = _to_record(row)
        n += 1
        if rec is not None:
            ids[rec.artifact_id] = (rec.kind, rec.lineage_id)
            if rec.chain_hash:
                tail = rec.chain_hash
    return _Index(ids, tail, n)


def _write_line(path: Path, row: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        fh.flush()


def _validated(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(payload)
    missing = [f for f in REQUIRED[kind] if f not in body]
    if missing:
        raise PayloadError(
            f"{kind} payload is missing {', '.join(missing)}. A value that is unknown must be "
            f"present and None; an absent key cannot be told apart from a forgotten one.")
    if kind == "review":
        verdict = str(body.get("verdict") or "")
        if verdict not in VERDICTS:
            raise PayloadError(f"review verdict {verdict!r} is not one of {VERDICTS}; an "
                               f"unrecognised verdict must never resolve to PASS or to VETO")
    return body


def append(kind: str, payload: Mapping[str, Any], prev: str | None = None,
           lineage_id: str | None = None, path: Path | None = None) -> Record:
    """Add one link. The ONLY writer. Refuses an unknown `prev`, a kind out of order, a payload
    missing a required field, and a `lineage_id` that disagrees with the predecessor's."""
    p = CHAIN if path is None else Path(path)
    k = str(kind).strip().lower()
    if k not in _ORDER:
        raise ChainOrderError(f"kind {kind!r} is not one of {KINDS}")
    body = _validated(k, payload)
    payload_hash = digest(body)
    at = datetime.now(tz=UTC).isoformat(timespec="microseconds")

    with _locked(p):
        idx = _read_index(p)
        orphan = False
        lin: str | None
        if prev is None:
            if k not in ROOT_KINDS:
                raise ChainOrderError(
                    f"a {k} record cannot start a lineage: it has to follow a "
                    f"{KINDS[_ORDER[k] - 1]}. Only {sorted(ROOT_KINDS)} may begin one, and a "
                    f"hypothesis that does is recorded as an orphan lineage.")
            orphan = k == "hypothesis"
            lin = None
        else:
            if prev not in idx.ids:
                raise UnknownPrev(f"prev={prev!r} is not in {p.name}; a link to a record the "
                                  f"chain does not hold is not provenance")
            prev_kind, prev_lineage = idx.ids[prev]
            if _ORDER.get(prev_kind, -99) + 1 != _ORDER[k]:
                raise ChainOrderError(
                    f"a {k} record cannot follow a {prev_kind or 'unknown'} record. The spine is "
                    f"{' -> '.join(KINDS)}; each kind follows exactly its predecessor.")
            if lineage_id is not None and lineage_id != prev_lineage:
                raise ChainOrderError(f"lineage_id={lineage_id!r} disagrees with prev's "
                                      f"{prev_lineage!r}; a record belongs to one lineage")
            lin = prev_lineage

        aid = _artifact_id(k, at, prev, idx.tail, payload_hash)
        if lin is None:
            if lineage_id is not None and lineage_id != aid:
                raise ChainOrderError("a record that starts a lineage IS its lineage; pass "
                                      "lineage_id=None or its own id")
            lin = aid
        rec = Record(artifact_id=aid, kind=k, at=at, prev=prev, lineage_id=lin,
                     payload=body, payload_hash=payload_hash,
                     chain_hash=_chain_hash(idx.tail, payload_hash), orphan_lineage=orphan)
        _write_line(p, rec.to_row())
    return rec


# --------------------------------------------------------------------------------- reading

def read_all(path: Path | None = None) -> list[Record]:
    """Every record in append order. Tolerant: a line that is not a record is skipped here and
    NAMED by `verify` -- reading must not be the thing that fails on a corrupt chain."""
    p = CHAIN if path is None else Path(path)
    try:
        text = p.read_text("utf-8")
    except OSError:
        return []
    out: list[Record] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        rec = _to_record(row)
        if rec is not None:
            out.append(rec)
    return out


def verify(path: Path | None = None) -> Verification:
    """Walk every line, recompute every hash and every prev link, stop at the first break.

    The three lies and the check that catches each: an edited payload breaks `payload_hash`; a
    payload edited together with its hash breaks `chain_hash`; all three edited together breaks
    `artifact_id`, because the id is taken over the position as well as the content.
    """
    p = CHAIN if path is None else Path(path)
    by_kind: dict[str, int] = {}
    orphans: list[str] = []
    ids: dict[str, tuple[str, str]] = {}
    lineages: set[str] = set()
    tail: str | None = None
    n = 0
    break_at: int | None = None
    reason: str | None = None

    try:
        text = p.read_text("utf-8")
    except FileNotFoundError:
        return Verification(0, True, None, None, {}, [], 0, str(p))
    except OSError as exc:
        return Verification(0, False, None, f"unreadable: {type(exc).__name__}: {exc}",
                            {}, [], 0, str(p))

    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        n += 1
        try:
            row = json.loads(line)
        except ValueError as exc:
            break_at, reason = lineno, f"line is not JSON: {exc}"
            break
        rec = _to_record(row)
        if rec is None:
            break_at, reason = lineno, "line is not an artifact record"
            break
        if rec.kind not in _ORDER:
            break_at, reason = lineno, f"kind {rec.kind!r} is not one of {KINDS}"
            break
        if digest(rec.payload) != rec.payload_hash:
            break_at, reason = lineno, "payload_hash mismatch: the payload was edited"
            break
        if _chain_hash(tail, rec.payload_hash) != rec.chain_hash:
            break_at, reason = lineno, ("chain_hash mismatch: a record was inserted, removed, "
                                        "reordered or rewritten")
            break
        if _artifact_id(rec.kind, rec.at, rec.prev, tail, rec.payload_hash) != rec.artifact_id:
            break_at, reason = lineno, "artifact_id mismatch: the record's identity was rewritten"
            break
        if rec.artifact_id in ids:
            break_at, reason = lineno, f"duplicate artifact_id {rec.artifact_id}"
            break
        if rec.prev is None:
            if rec.kind not in ROOT_KINDS:
                break_at, reason = lineno, f"a {rec.kind} record cannot start a lineage"
                break
            if rec.lineage_id != rec.artifact_id:
                break_at, reason = lineno, "a lineage head must be its own lineage_id"
                break
        else:
            if rec.prev not in ids:
                break_at, reason = lineno, f"prev {rec.prev} is not earlier in the chain"
                break
            prev_kind, prev_lineage = ids[rec.prev]
            if _ORDER.get(prev_kind, -99) + 1 != _ORDER[rec.kind]:
                break_at, reason = lineno, f"a {rec.kind} record cannot follow a {prev_kind}"
                break
            if rec.lineage_id != prev_lineage:
                break_at, reason = lineno, "lineage_id disagrees with prev's lineage"
                break

        ids[rec.artifact_id] = (rec.kind, rec.lineage_id)
        lineages.add(rec.lineage_id)
        by_kind[rec.kind] = by_kind.get(rec.kind, 0) + 1
        if rec.orphan_lineage and rec.lineage_id not in orphans:
            orphans.append(rec.lineage_id)
        tail = rec.chain_hash

    return Verification(n=n, ok=break_at is None, first_break=break_at, reason=reason,
                        by_kind=by_kind, orphan_lineages=orphans, lineages=len(lineages),
                        path=str(p))


def lineage(artifact_id: str, path: Path | None = None) -> list[Record]:
    """Every record of the lineage that holds `artifact_id`, in append order. Accepts a record id
    or a lineage id; the `prev` links give the path through it."""
    recs = read_all(path)
    want = str(artifact_id)
    by_id = {r.artifact_id: r for r in recs}
    target = by_id.get(want)
    lin = target.lineage_id if target is not None else want
    return [r for r in recs if r.lineage_id == lin]


def latest(kind: str, key: str, path: Path | None = None) -> Record | None:
    """The newest record of `kind` whose identifying field (or artifact_id) equals `key`."""
    k = str(kind).strip().lower()
    want = str(key)
    fields = KEY_FIELDS.get(k, ())
    for rec in reversed(read_all(path)):
        if rec.kind != k:
            continue
        if rec.artifact_id == want:
            return rec
        for f in fields:
            value = rec.payload.get(f)
            if value is not None and (str(value) == want or _canon(value) == want):
                return rec
    return None


# --------------------------------------------------------------------------------- payloads

def source_payload(source_id: str, url_or_ground: str, retrieved_at: str | None = None,
                   source_hash: str | None = None, **extra: Any) -> dict[str, Any]:
    """A ground the desk read. `source_hash` is the digest of the bytes, when they were kept."""
    return {"source_id": str(source_id), "url_or_ground": str(url_or_ground),
            "retrieved_at": str(retrieved_at) if retrieved_at else None,
            "source_hash": str(source_hash) if source_hash else None, **extra}


def claim_payload(text: str, mechanism: str, actor: str, language: str = "en",
                  **extra: Any) -> dict[str, Any]:
    """A verbatim claim, recorded by its HASH and never by its prose.

    The blind reviewer refuses a string by construction so no rationale can move a number it has
    already computed. The chain keeps that property: it proves the text a later reader holds is
    the text that was tested, and gives persuasion no route in.
    """
    body = str(text)
    return {"text_hash": digest(body), "mechanism": str(mechanism), "actor": str(actor),
            "language": str(language), "chars": len(body), **extra}


def cell_id_for(symbol: str, family: str, params: Mapping[str, Any] | None = None) -> str:
    """The desk's own executable identity, imported from `frontier_identity`."""
    try:
        from desks.mt5.research.frontier_identity import cell_id
    except ImportError as exc:                              # pragma: no cover - packaging only
        raise ChainError(
            "the desk's research.frontier_identity is not importable, and cell identity is the "
            "desk's to compute; re-deriving it here is how two ids for one cell get minted"
        ) from exc
    return str(cell_id({"sym": str(symbol), "family": str(family), "params": dict(params or {})}))


def hypothesis_payload(symbol: str, family: str, params: Mapping[str, Any] | None,
                       falsifier: str | None, artifact: Any = None,
                       **extra: Any) -> dict[str, Any]:
    """A testable cell. `artifact` may be a `libs.research.artifacts.ResearchArtifact`, whose id
    and fingerprint are carried across so the mutable candidate and its immutable record join."""
    body: dict[str, Any] = {
        "cell_id": cell_id_for(symbol, family, params), "symbol": str(symbol),
        "family": str(family), "params": dict(params or {}),
        "falsifier": str(falsifier) if falsifier else None, **extra,
    }
    if artifact is not None:
        body["candidate_id"] = getattr(artifact, "artifact_id", None)
        fingerprint = getattr(artifact, "fingerprint", None)
        body["candidate_fingerprint"] = fingerprint() if callable(fingerprint) else None
    return body


def code_payload(fn: Any, family: str, **extra: Any) -> dict[str, Any]:
    """The code identity of a family function, from the sleeve registry's own two hashes.

    Both, never one. `code_hash` moves when a COMMENT moves (which broke 15 of 52 live clocks on
    2026-09-03); `behaviour_hash` moves only when the bytecode does. A chain that recorded one
    would either see edits that changed nothing or miss edits that changed everything.
    """
    try:
        from desks.mt5.research.sleeve_registry import behaviour_hash, code_hash
    except ImportError as exc:                              # pragma: no cover - packaging only
        raise ChainError("the desk's research.sleeve_registry is not importable; code identity "
                         "is the registry's to compute") from exc
    return {"code_hash": code_hash(fn), "behaviour_hash": behaviour_hash(fn),
            "family": str(family), **extra}


def data_payload(bars: Mapping[tuple[str, str], Path | str],
                 vintage_ids: Sequence[str] | None = None, **extra: Any) -> dict[str, Any]:
    """The bytes an experiment ran on: sha256 per (symbol, timeframe) parquet.

    An unreadable file hashes to None and is NAMED in `unreadable` rather than dropped -- a
    missing axis is a hole in the evidence, not an axis that was never asked for. When the caller
    declares no vintages one is derived per axis from `pit_stamp.vintage_id_for` on the file's own
    modification time, which is the honest bound this box can actually observe.
    """
    from libs.data.pit_stamp import vintage_id_for

    digests: dict[str, str | None] = {}
    derived: list[str] = []
    for (symbol, timeframe), raw in bars.items():
        p = Path(raw)
        axis = f"{symbol}|{timeframe}"
        digests[axis] = sha256_file(p)
        if vintage_ids is None:
            fetched: str | None = None
            with suppress(OSError):
                fetched = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC).isoformat(
                    timespec="seconds")
            vid = vintage_id_for(axis, fetched, None)
            if vid:
                derived.append(vid)
    return {"bars_digest": digests, "digest": digest(digests),
            "vintage_ids": list(vintage_ids) if vintage_ids is not None else derived,
            "vintage_basis": "declared" if vintage_ids is not None else "derived_from_mtime",
            "unreadable": sorted(k for k, v in digests.items() if v is None), **extra}


def config_payload(settings: Mapping[str, Any], config_hash: str | None = None,
                   **extra: Any) -> dict[str, Any]:
    """The settings in force, by digest, with the tree that held them.

    Only the KEYS of the settings are carried in the clear. The digest is what a reproduction has
    to match; the key list is what lets a reader see that a setting existed at all.
    """
    from libs.ops.compute_ledger import commit_sha

    body = dict(settings)
    settings_digest = digest(body)
    return {"config_hash": str(config_hash) if config_hash else settings_digest,
            "settings_digest": settings_digest, "settings_keys": sorted(body),
            "commit_sha": commit_sha(), **extra}


def result_payload(stages: Any, passed: bool | None, n: int | None = None,
                   expectancy: float | None = None, t: float | None = None,
                   output_hash: str | None = None, **extra: Any) -> dict[str, Any]:
    """What the run measured. Every number may be None, which reads as UNMEASURED, never as 0."""
    return {"stages_digest": digest(stages), "passed": None if passed is None else bool(passed),
            "n": None if n is None else int(n),
            "expectancy": None if expectancy is None else float(expectancy),
            "t": None if t is None else float(t),
            "output_hash": str(output_hash) if output_hash else None, **extra}


def review_payload(verdict: str, reviewer: str, reproduced: Any = None,
                   **extra: Any) -> dict[str, Any]:
    """An independent re-execution's verdict, by the blind reviewer's own vocabulary."""
    return {"verdict": str(verdict).upper(), "reviewer": str(reviewer),
            "reproduced_digest": digest(reproduced if reproduced is not None else {}), **extra}


# --------------------------------------------------------------------------------- adapters

def from_cell(symbol: str, family: str, params: Mapping[str, Any] | None = None,
              path: Path | None = None) -> Record | None:
    """The hypothesis record for a cell, by the desk's `cell_id`. None when it was never written
    -- which is "this cell has no recorded provenance", not "this cell does not exist"."""
    return latest("hypothesis", cell_id_for(symbol, family, params), path=path)


def _num(row: Mapping[str, Any], names: Sequence[str]) -> float | None:
    """The first of `names` that holds a real number. A bool is not a number here."""
    for name in names:
        value = row.get(name)
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _anchor_for(cell: str, kind: str, path: Path | None) -> str:
    """The record in `cell`'s lineage that a new `kind` must follow."""
    hypothesis = latest("hypothesis", cell, path=path)
    if hypothesis is None:
        raise ChainOrderError(
            f"no hypothesis record for cell {cell!r}: a result whose hypothesis was never "
            f"recorded is not a link in a chain. Append the hypothesis first (orphan when its "
            f"source is unknown), then its code and data.")
    for rec in reversed(lineage(hypothesis.artifact_id, path=path)):
        if rec.kind == kind:
            return rec.artifact_id
    raise ChainOrderError(
        f"lineage {hypothesis.lineage_id} holds no {kind} record, so cell {cell!r} cannot attach "
        f"a {KINDS[_ORDER[kind] + 1]} to it. The chain will not record a result whose "
        f"{kind} identity is unknown -- that is the gap it exists to close.")


def from_gate_verdict(row: Mapping[str, Any], prev: str | None = None,
                      path: Path | None = None) -> Record:
    """One `gate_verdict_ledger.jsonl` row -> a config record and the result that followed it.

    Returns the RESULT record; the config is reachable through its `prev`. `prev` defaults to the
    data record of the cell's own lineage, so the gauntlet appends with one call and still cannot
    record a verdict whose bars were never identified.
    """
    cell = str(row.get("cell") or "")
    stages = row.get("gates") or row.get("stages") or {
        "terminal_gate": row.get("terminal_gate"), "passed": row.get("passed")}
    config = config_payload(
        {"cell": cell, "family": row.get("family"), "symbol": row.get("sym") or row.get("symbol"),
         "terminal_gate": row.get("terminal_gate"),
         "downstream_status": row.get("downstream_status")},
        cell=cell)
    expectancy = _num(row, ("expectancy", "mean_r", "exp_r"))
    trades = _num(row, ("n", "n_trades", "trades"))
    result = result_payload(
        stages=stages, passed=row.get("passed"),
        n=None if trades is None else int(trades), expectancy=expectancy,
        t=_num(row, ("t", "t_stat", "t_value")), output_hash=digest(dict(row)),
        cell=cell, terminal_gate=row.get("terminal_gate"), at=str(row.get("at") or ""))
    anchor = prev if prev is not None else _anchor_for(cell, "data", path)
    config_rec = append("config", config, prev=anchor, path=path)
    return append("result", result, prev=config_rec.artifact_id, path=path)


def from_blind_review(row: Mapping[str, Any], prev: str | None = None,
                      path: Path | None = None) -> Record:
    """One `blind_review_ledger.jsonl` row -> a review record. Tolerant of the ledger's shape.

    A verdict outside the vocabulary becomes UNMEASURED, never PASS and never VETO: a reviewer
    whose answer this cannot read has not cleared the cell and has not condemned it either.
    """
    cell = str(row.get("cell") or "")
    verdict = str(row.get("verdict") or "").upper()
    if verdict not in VERDICTS:
        verdict = "UNMEASURED"
    reproduced = row.get("reproduced")
    body = review_payload(
        verdict, str(row.get("reviewer") or "blind_reviewer"),
        reproduced if isinstance(reproduced, dict) else {},
        cell=cell, basis=row.get("basis"),
        hostile=(row.get("hostile") or {}).get("status") if isinstance(row.get("hostile"), dict)
        else None,
        at=str(row.get("at") or ""))
    anchor = prev if prev is not None else _anchor_for(cell, "result", path)
    return append("review", body, prev=anchor, path=path)
