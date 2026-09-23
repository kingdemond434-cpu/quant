"""FRESHNESS IS A LEASE, NOT A FILE MTIME.

An mtime answers "when did some process last touch these bytes", which is not the question. It
says nothing about WHO wrote them, from WHICH code, off WHICH inputs, for WHICH controller epoch,
or for how long the number inside is still worth believing. Every one of those has been guessed on
this desk, and each guess became an incident: a report re-stamped by a formatter and read as
fresh; a verdict attributed to the wrong commit because the seal named the commit before the one
that shipped; a pass certified green off a WIRING_CEO.json written an hour earlier.

So every report carries an ENVELOPE, and freshness is computed from the envelope's lease:

    {artifact_id, producer_component_id, producer_run_id, epoch_id, code_sha, config_hash,
     input_artifact_ids, started_at, finished_at, schema_version, content_hash, created_at,
     valid_until, producer_generation, input_watermarks}

and every CONSUMER records an acknowledgement:

    {consumer_component_id, consumed_artifact_id, consumer_run_id, consumed_at}

Lineage is then PROVEN -- a producer run id and a consumer's acknowledgement of that exact
artifact -- instead of inferred from two timestamps that happen to be close together.

TTLs ARE PER CLASS, because "stale" means something different for a tick tape and for a CPI
release. The table below is the desk's, and a class it does not know is UNMEASURED rather than
defaulted: an artifact whose staleness nobody has decided is a finding.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
ACK_LOG = DESK / "data" / "artifact_acks.jsonl"
ENVELOPE_SUFFIX = ".envelope.json"
#: Where the envelope lives INSIDE a json document, so a report and its lease travel together.
ENVELOPE_KEY = "_envelope"

SCHEMA_VERSION = "1"

#: Per-class time-to-live, in seconds. The classes are the desk's own cadences.
TTL_BY_CLASS: dict[str, int] = {
    "tick": 300,                 # seconds-to-minutes: a tape older than five minutes is history
    "quote": 120,
    "news": 900,                 # minutes
    "minute": 1_800,
    "fifteen_minute": 2_700,     # the 15-minute box tasks (clock fixer, allocator fast lane)
    "hourly": 7_200,             # an hourly leg: two cadences, the standing rule
    "half_daily": 50_400,
    "daily": 93_600,             # 26 h, the desk's existing daily freshness limit
    "weekly": 864_000,           # 10 days
    #: CPI-LIKE: monthly cadence, but REVISION-SENSITIVE. The lease expires on the cadence and the
    #: envelope carries `revision_sensitive`, so a consumer knows that a still-valid lease can be
    #: invalidated early by a revision rather than by the clock.
    "monthly": 2_764_800,        # 32 days
    "monthly_revision_sensitive": 2_764_800,
    "static": 31_536_000,
}

#: Classes whose value can be superseded before their lease expires.
REVISION_SENSITIVE: frozenset[str] = frozenset({"monthly_revision_sensitive", "news"})

UNMEASURED = "UNMEASURED"


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).isoformat(timespec="seconds")


def new_run_id(component_id: str) -> str:
    """One id per PROCESS RUN. Ownership of an artifact is proven by this, never by an mtime."""
    return f"{component_id}@{_iso(_now())}#{uuid.uuid4().hex[:8]}"


def ttl_for(artifact_class: str) -> int | None:
    """Seconds this class stays believable. None = this desk has not decided, which is a finding
    the reconciler reports as UNMEASURED rather than treating as immortal."""
    return TTL_BY_CLASS.get(str(artifact_class))


def content_hash(doc: Any) -> str:
    payload = json.dumps(doc, sort_keys=True, default=str) if not isinstance(doc, (bytes,
                                                                                  bytearray)) \
        else bytes(doc)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def artifact_id(path: str | Path, root: Path | None = None) -> str:
    """The stable name of an artifact: its repo-relative path. Two producers writing the same
    path is a WRITE-AUTHORITY conflict the reconciler must see, and it can only see it if both
    writes carry the same artifact_id."""
    p = Path(path)
    base = root or ROOT
    with contextlib.suppress(ValueError):
        return p.resolve().relative_to(base).as_posix()
    return p.as_posix()


def envelope_for(path: str | Path, component: Any, inputs: Iterable[str] = (),
                 ttl: int | str | None = None, *, doc: Any = None,
                 run_id: str | None = None, epoch_id: str | None = None,
                 started_at: str | None = None, generation: int | None = None,
                 input_watermarks: Mapping[str, Any] | None = None,
                 root: Path | None = None) -> dict[str, Any]:
    """Build the lease envelope for one artifact.

    `component` is a ComponentSpec or a component_id string -- the spec form also stamps the code
    and config identity, which is the half that lets a later reader tell a code change from a
    data one. `ttl` is a class name from TTL_BY_CLASS, an explicit number of seconds, or None (in
    which case the component's own artifact_class decides, and UNMEASURED if it declares none).
    """
    cid = getattr(component, "component_id", None) or str(component)
    identity = (component.code_identity(root)
                if hasattr(component, "code_identity")
                else {"code_sha": UNMEASURED, "config_hash": UNMEASURED})
    klass = ttl if isinstance(ttl, str) else getattr(component, "artifact_class", UNMEASURED)
    seconds = ttl if isinstance(ttl, int) else ttl_for(str(klass))
    now = _now()
    valid_until = _iso(now + timedelta(seconds=seconds)) if seconds else None
    return {
        "artifact_id": artifact_id(path, root),
        "producer_component_id": cid,
        "producer_run_id": run_id or new_run_id(cid),
        "epoch_id": epoch_id or UNMEASURED,
        "code_sha": identity.get("code_sha", UNMEASURED),
        "config_hash": identity.get("config_hash", UNMEASURED),
        "input_artifact_ids": sorted({str(i) for i in inputs}),
        "started_at": started_at or _iso(now),
        "finished_at": _iso(now),
        "schema_version": SCHEMA_VERSION,
        "content_hash": content_hash(doc) if doc is not None else UNMEASURED,
        "created_at": _iso(now),
        "valid_until": valid_until or UNMEASURED,
        "ttl_s": seconds,
        "artifact_class": str(klass),
        "revision_sensitive": str(klass) in REVISION_SENSITIVE,
        "producer_generation": generation if generation is not None else 1,
        "input_watermarks": dict(input_watermarks or {}),
    }


def write_report(path: str | Path, doc: Any, component: Any, inputs: Iterable[str] = (),
                 ttl: int | str | None = None, *, run_id: str | None = None,
                 epoch_id: str | None = None, sidecar: bool = True,
                 root: Path | None = None, **envelope_kw: Any) -> dict[str, Any]:
    """Write `doc` to `path` WITH its lease. Returns the envelope.

    The envelope goes inside the document under `_envelope` when the document is a mapping (so a
    consumer that already reads the report gets the lease for free) and, when `sidecar`, beside it
    as `<path>.envelope.json` (so a non-JSON artifact -- a parquet, a csv, a log -- can be leased
    too). Atomic: tmp + os.replace, the desk's standing rule for any file another process reads.
    """
    p = Path(path)
    env = envelope_for(p, component, inputs, ttl, doc=doc, run_id=run_id, epoch_id=epoch_id,
                       root=root, **envelope_kw)
    payload = doc
    if isinstance(doc, dict):
        payload = {**doc, ENVELOPE_KEY: env}
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)
    if sidecar:
        side = p.with_name(p.name + ENVELOPE_SUFFIX)
        stmp = side.with_suffix(side.suffix + ".tmp")
        stmp.write_text(json.dumps(env, indent=1, default=str), encoding="utf-8")
        os.replace(stmp, side)
    record_artifact(env)
    return env


def stamp_sidecar(path: str | Path, component: Any, inputs: Iterable[str] = (),
                  ttl: int | str | None = None, *, run_id: str | None = None,
                  epoch_id: str | None = None, root: Path | None = None) -> dict[str, Any]:
    """Lease an artifact SOMEONE ELSE'S WRITER already wrote, by sidecar only.

    For the organs whose output path is not json, or whose write is a `write_text` deep inside a
    function nobody should rewrite for telemetry: call this right after the write and the file
    gets its `<path>.envelope.json`, its lineage row and its content hash, with the document
    itself untouched. Never raises -- an organ must not die because its lease could not be
    stamped; the reconciler reports the artifact UNLEASED, which is the finding.
    """
    p = Path(path)
    try:
        raw: Any = p.read_bytes()
    except OSError:
        raw = None
    env = envelope_for(p, component, inputs, ttl, doc=raw, run_id=run_id, epoch_id=epoch_id,
                       root=root)
    try:
        side = p.with_name(p.name + ENVELOPE_SUFFIX)
        stmp = side.with_suffix(side.suffix + ".tmp")
        stmp.write_text(json.dumps(env, indent=1, default=str), encoding="utf-8")
        os.replace(stmp, side)
        env["written"] = True
    except OSError as exc:
        env["written"] = False
        env["why"] = f"{type(exc).__name__}: {exc}"
    record_artifact(env)
    return env


def read_envelope(path: str | Path) -> dict[str, Any] | None:
    """The lease for one artifact: from inside the document, else from its sidecar, else None.

    None is UNLEASED, which is a real finding -- an artifact nobody has claimed authorship of --
    and it must never be silently upgraded to "fresh because the file is recent".
    """
    p = Path(path)
    if p.suffix == ".json":
        try:
            doc = json.loads(p.read_text(encoding="utf-8-sig"))
            env = doc.get(ENVELOPE_KEY) if isinstance(doc, dict) else None
            if isinstance(env, dict):
                return env
        except (OSError, ValueError):
            pass
    side = p.with_name(p.name + ENVELOPE_SUFFIX)
    try:
        env = json.loads(side.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None
    return env if isinstance(env, dict) else None


def valid(envelope: Mapping[str, Any] | None, now: datetime | None = None) -> bool | None:
    """True = inside its lease; False = expired; None = UNMEASURED (no lease, or no TTL)."""
    if not envelope:
        return None
    until = str(envelope.get("valid_until") or "")
    if not until or until == UNMEASURED:
        return None
    try:
        t = datetime.fromisoformat(until)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now or _now()) <= t


def staleness(paths: Iterable[str | Path], now: datetime | None = None,
              root: Path | None = None) -> dict[str, dict[str, Any]]:
    """The freshness verdict for a set of artifacts, computed FROM LEASES, never from mtimes.

    Verdicts: VALID (inside its lease), STALE (expired), UNLEASED (exists, no envelope),
    MISSING (no file), UNMEASURED (leased but the class declares no TTL).
    """
    t = now or _now()
    out: dict[str, dict[str, Any]] = {}
    for raw in paths:
        p = Path(raw)
        aid = artifact_id(p, root)
        if not p.exists():
            out[aid] = {"verdict": "MISSING", "why": f"{aid} does not exist"}
            continue
        env = read_envelope(p)
        if env is None:
            out[aid] = {"verdict": "UNLEASED",
                        "why": (f"{aid} exists with no envelope: nobody claims authorship, so "
                                f"its freshness cannot be decided (an mtime is not a lease)")}
            continue
        v = valid(env, t)
        if v is None:
            out[aid] = {"verdict": "UNMEASURED", "producer": env.get("producer_component_id"),
                        "why": f"{aid} is leased but its class declares no TTL"}
        else:
            out[aid] = {"verdict": "VALID" if v else "STALE",
                        "producer": env.get("producer_component_id"),
                        "producer_run_id": env.get("producer_run_id"),
                        "epoch_id": env.get("epoch_id"),
                        "valid_until": env.get("valid_until"),
                        "revision_sensitive": env.get("revision_sensitive"),
                        "why": "" if v else f"{aid} lease expired at {env.get('valid_until')}"}
    return out


# --------------------------------------------------------------------------- acknowledgements
def ack(consumer: Any, consumed_artifact_id: str, *, consumer_run_id: str | None = None,
        epoch_id: str | None = None, path: Path | None = None,
        producer_run_id: str | None = None) -> dict[str, Any]:
    """Record that `consumer` READ `consumed_artifact_id`. This is what proves an edge.

    NEVER RAISES, for the reason `watermarks.progress` does not: an organ that dies because its
    lineage record failed is worse than one that runs unrecorded, and an absent ack shows up as
    an unproven edge, which is the finding.
    """
    cid = getattr(consumer, "component_id", None) or str(consumer)
    row = {
        "consumer_component_id": cid,
        "consumed_artifact_id": str(consumed_artifact_id),
        "consumer_run_id": consumer_run_id or new_run_id(cid),
        "consumed_at": _iso(_now()),
        "epoch_id": epoch_id or UNMEASURED,
        "producer_run_id": producer_run_id or UNMEASURED,
    }
    target = path or ACK_LOG
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        row["written"] = True
    except OSError as exc:
        row["written"] = False
        row["why"] = f"{type(exc).__name__}: {exc}"
    with contextlib.suppress(Exception):
        from libs.ops.control_plane import edges as _edges
        _edges.record_ack(row)
    return row


def ack_artifact(consumer: Any, path: str | Path, *, root: Path | None = None,
                 **kw: Any) -> dict[str, Any]:
    """`ack` for a consumer holding the PATH rather than the id: reads the producer's run id out
    of the artifact's own envelope, so the acknowledgement names the exact run it consumed.

    THE ID IS THE PRODUCER'S. The envelope already carries the artifact_id the producer
    registered in the lineage store; an id recomputed here against a different root would name
    a different artifact and the edge would read UNACKED forever, with both sides honest.
    """
    env = read_envelope(path) or {}
    aid = str(env.get("artifact_id") or artifact_id(path, root))
    return ack(consumer, aid, producer_run_id=env.get("producer_run_id"), **kw)


def acks(path: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    target = path or ACK_LOG
    rows: list[dict[str, Any]] = []
    try:
        text = target.read_text(encoding="utf-8-sig")
    except OSError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-limit:] if limit else rows


def acks_for(consumed_artifact_id: str, path: Path | None = None) -> list[dict[str, Any]]:
    return [r for r in acks(path) if r.get("consumed_artifact_id") == consumed_artifact_id]


def record_artifact(envelope: Mapping[str, Any]) -> None:
    """Push a written envelope into the lineage store. Best-effort by design: the store is an
    index over facts that already exist in the envelopes, never their only copy."""
    with contextlib.suppress(Exception):
        from libs.ops.control_plane import edges as _edges
        _edges.record_artifact(envelope)
