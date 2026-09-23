"""NOTHING IS RETIRED ON AN ABSENCE (LAWS 7, 2026-09-23) -- the shared guard for every pass
that REMOVES rather than reports.

THE INCIDENT THIS EXISTS FOR, in one paragraph because the arithmetic was never wrong.
`certificate_truth.py --apply` was run on the trading box. It judged every derived store against
`desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json`, which at that moment held `n=0` and had not been
written for 46.7 hours. Against a reference that says nothing, "row X is not backed by the canon"
is true of EVERY row, so it retired 837 of them -- while the gauntlet sweep three hours earlier
had logged `Updated UNIVERSAL_SURVIVORS.json: 7 total (+7)`, 114 survivor-ledger claims and 1,240
cells cleared to gather forward evidence. An empty file retired the judge's fresh work. No line of
that pass was a bug. The defect was upstream of the arithmetic: the pass never asked whether its
reference was in a position to answer.

THE RULE, and it is general. A store that is EMPTY, STALE BEYOND ITS LEASE or UNREADABLE is
UNMEASURED, and UNMEASURED is a verdict about the MEASUREMENT, never a statement about the world
(L1.28a). "The canon does not back this row" and "the canon is not currently saying anything" are
different sentences, and only the first is a licence to remove. So every destructive pass proves
its reference is live BEFORE it removes anything, and stands down with the reason when it is not.

    from libs.ops.reference_freshness import require_live_reference, ReferenceNotLive

    state = require_live_reference(
        "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
        actor="certificate_truth.apply", action="retire unbacked rows",
        min_rows=1,
    )
    if not state.live:
        return stand_down(state)          # remove NOTHING; state.why says why, on the record

`strict=True` raises `ReferenceNotLive` instead, for callers whose correct degrade direction is to
abort the pass rather than to continue with the removals skipped.

WHERE THE LEASE COMES FROM, in order, and the order is the point:
  1. THE ARTIFACT'S OWN ENVELOPE (`libs/ops/control_plane/lease.py`). A lease is a producer's
     claim about how long its number is worth believing; an mtime is not a lease.
  2. THE COMPONENT REGISTRY's freshness row (`desks/mt5/reports/COMPONENT_REGISTRY.json`), matched
     by `outputs` -- the declared `max_silence_s` of whichever organ WRITES this reference.
  3. DERIVED FROM THE WRITING ORGAN'S CADENCE, at two cadences (the desk's standing rule for an
     hourly leg), and the derivation is RECORDED in `lease_source` so a reader can see that the
     number was inferred rather than declared. A derived lease is a finding, not a default.
  4. NOTHING. `lease_s is None` with `lease_source="UNMEASURED"` -- and an age can then never be
     judged, so the verdict is UNREADABLE rather than a silent FRESH. A reference whose staleness
     nobody has decided may not authorise a deletion.

FRESH-BUT-EMPTY IS NOT FRESH (R0159), which is the precise shape of the incident: the canon was
BOTH. The row count is measured from the store's own container (a list, or the first known
collection key in a dict) and never from a self-declared `n`, because `n` is exactly the field a
truncated write gets wrong.

WHAT IS DELIBERATELY NOT HERE. This module never decides WHAT to remove and never removes
anything; it answers one question and records the answer. It adds no cap, veto or shrink to any
risk or research path (growth governance): a live reference passes through untouched and the pass
does exactly what it did before. The only behaviour it changes is the case where the pass was
acting on nothing -- where the removals were never evidence-backed in the first place.

Stand-downs are appended to `desks/mt5/reports/REFERENCE_STANDDOWNS.jsonl` and emitted as
`REFERENCE_STAND_DOWN` events, so an operator meets the refusal without asking for it. Recording
is best-effort by design: a telemetry failure must never turn a refusal-to-delete into a deletion.

Fenced by `scripts/check_no_retirement_on_absence.py` (law gate), pinned by
`tests/ops/test_reference_freshness.py`.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
REPORTS = DESK / "reports"
#: Where an operator meets a refusal without having to ask for it.
STANDDOWN_LOG = REPORTS / "REFERENCE_STANDDOWNS.jsonl"
#: The registry freshness rows the component fence publishes (clock, cadence, max_silence).
COMPONENT_REGISTRY = REPORTS / "COMPONENT_REGISTRY.json"

#: Verdicts. FRESH is the only one that authorises a removal.
FRESH = "FRESH"
EMPTY = "EMPTY"
STALE = "STALE"
UNREADABLE = "UNREADABLE"
MISSING = "MISSING"
UNMEASURED = "UNMEASURED"

#: Every non-FRESH verdict is UNMEASURED in the L1.28a sense: it says the measurement failed, not
#: that the world is empty. Kept as a set so a caller can test membership rather than string-match.
NOT_LIVE = frozenset({EMPTY, STALE, UNREADABLE, MISSING})

#: How many cadences of silence turn a derived lease stale. Two is the desk's standing rule for an
#: hourly leg (`lease.TTL_BY_CLASS["hourly"] == 2 * 3600`), applied uniformly so the derivation is
#: one number a reader can check rather than a per-call judgement.
CADENCE_MULTIPLE = 2.0

#: Dict keys that hold the rows of a reference store, in the order they are tried. A store whose
#: collection is under none of these must name it with `rows_key=`; guessing further would let a
#: metadata dict masquerade as content, which is the failure this module exists to stop.
ROW_KEYS: tuple[str, ...] = (
    "survivors", "rows", "items", "entries", "records", "candidates", "certificates",
    "cells", "clocks", "sleeves", "components", "claims", "paths", "results", "data",
)

#: DERIVED LEASES, one row per reference the component registry does not yet claim an output for.
#: Each row RECORDS ITS DERIVATION rather than hiding it in a number: the organ that writes the
#: store, the clock that fires that organ, its cadence, and the arithmetic. A reference is only
#: allowed in here once someone has answered "who writes this and how often"; an entry with no
#: writer would be a default wearing a table's clothes, which is what step 4 refuses.
#:
#: {reference path: (lease seconds, writing organ, the derivation, floor rows)}
DERIVED_LEASES: dict[str, tuple[float, str, str, int]] = {
    # The MT5 symbol registry. Rebuilt from the terminal by the daily box task (the registry's own
    # `daily:refresh_bars` row declares cadence 86400 / max_silence 172800, which is the same two
    # cadences this table derives), and read as the authority on what can be traded.
    "desks/mt5/data/universe/universe.json": (
        172800.0, "desks/mt5/scripts/build_universe.py (box task MT5-Daily)",
        "cadence 86400s x 2 = 172800s; matches the registry's own daily:refresh_bars "
        "max_silence_s, so the derivation and the declaration agree", 50),
    # The one certificate authority. Written by the gauntlet sweep on the hourly cycle; the 837-row
    # incident is exactly a read of this file 46.7h after its writer last spoke.
    "desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json": (
        7200.0, "desks/mt5/scripts/external_gauntlet.py (hourly leg external_gauntlet)",
        "cadence 3600s x 2 = 7200s, the desk's standing hourly rule "
        "(lease.TTL_BY_CLASS['hourly'])", 1),
    "desks/mt5/reports/UNIVERSAL_SURVIVORS.json": (
        7200.0, "desks/mt5/scripts/external_gauntlet.py (hourly leg external_gauntlet)",
        "cadence 3600s x 2 = 7200s, the desk's standing hourly rule", 1),
}

#: Keys that are metadata, never content. Used only when a dict has no known collection key.
_META_KEYS = frozenset({
    "_envelope", "n", "count", "generated_at", "at", "swept_at", "note", "notes", "schema",
    "schema_version", "version", "gate_policy", "policy", "revoked_at", "rule", "ok", "fatal",
})


class ReferenceNotLive(RuntimeError):
    """Raised by `require_live_reference(strict=True)`. Carries the state, never just a message."""

    def __init__(self, state: ReferenceState) -> None:
        super().__init__(state.why)
        self.state = state


@dataclass(frozen=True)
class ReferenceState:
    """One reference store's fitness to authorise a removal, with the evidence attached."""

    path: str
    verdict: str
    live: bool
    rows: int | None
    min_rows: int
    rows_source: str
    age_s: float | None
    lease_s: float | None
    lease_source: str
    writer: str
    why: str
    at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat(timespec="seconds"))

    @property
    def unmeasured(self) -> bool:
        """True when the reference could not answer. Never the same as 'the world is empty'."""
        return self.verdict in NOT_LIVE

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- row counting

def _rel(path: str | Path) -> str:
    p = Path(path)
    try:
        return p.resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _abs(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p)


def count_rows(path: str | Path, *, rows_key: str | None = None) -> tuple[int | None, str]:
    """(row count, how it was measured). None means the store could not be read at all.

    A self-declared `n` is never trusted: a truncated write is exactly the case where `n` and the
    container disagree, and the container is the one holding the evidence.
    """
    p = _abs(path)
    suffix = p.suffix.lower()
    try:
        if suffix in {".jsonl", ".ndjson"}:
            n = 0
            with p.open("r", encoding="utf-8-sig") as fh:
                for line in fh:
                    if line.strip():
                        n += 1
            return n, "jsonl:non-blank-lines"
        if suffix in {".sqlite", ".sqlite3", ".db"}:
            return _count_sqlite(p, rows_key)
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, sqlite3.Error):
        return None, "unreadable"
    return count_rows_in(doc, rows_key=rows_key)


def _count_sqlite(p: Path, table: str | None) -> tuple[int | None, str]:
    """A sqlite reference counts one named table; with no table named, it counts every user table,
    because "the database exists" has never been evidence that the table the pass judges against
    has anything in it."""
    try:
        con = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None, "unreadable"
    try:
        cur = con.cursor()
        if table:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - caller-declared table
            row = cur.fetchone()
            return (int(row[0]) if row else 0), f"sqlite:{table}"
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%'")
        names = [str(r[0]) for r in cur.fetchall()]
        total = 0
        for name in names:
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')  # noqa: S608 - name from sqlite_master
            row = cur.fetchone()
            total += int(row[0]) if row else 0
        return total, f"sqlite:{len(names)} tables"
    except sqlite3.Error:
        return None, "unreadable"
    finally:
        con.close()


def count_rows_in(doc: Any, *, rows_key: str | None = None) -> tuple[int | None, str]:
    """Row count for an already-parsed document. Split out so a caller holding the payload in
    memory measures it the same way the file reader does."""
    if doc is None:
        return None, "unreadable"
    if isinstance(doc, (list, tuple)):
        return len(doc), "list"
    if isinstance(doc, Mapping):
        if rows_key is not None:
            container = doc.get(rows_key)
            if isinstance(container, (list, tuple, Mapping)):
                return len(container), f"dict[{rows_key}]"
            return 0, f"dict[{rows_key}]:absent"
        for key in ROW_KEYS:
            container = doc.get(key)
            if isinstance(container, (list, tuple, Mapping)):
                return len(container), f"dict[{key}]"
        content = [k for k in doc if k not in _META_KEYS]
        return len(content), "dict:non-metadata-keys"
    return None, f"unreadable:{type(doc).__name__}"


# --------------------------------------------------------------------------- lease resolution

def _registry_rows(registry: str | Path | None = None) -> list[dict[str, Any]]:
    p = _abs(registry) if registry is not None else COMPONENT_REGISTRY
    try:
        doc = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return []
    rows = doc.get("freshness") if isinstance(doc, Mapping) else None
    return [r for r in rows if isinstance(r, Mapping)] if isinstance(rows, list) else []


def lease_for(path: str | Path, *, registry: str | Path | None = None,
              rows: Iterable[Mapping[str, Any]] | None = None) -> tuple[float | None, str, str]:
    """(lease seconds, where it came from, the organ that writes this reference).

    The order is envelope -> declared `max_silence_s` -> cadence x CADENCE_MULTIPLE -> nothing, and
    the DERIVATION IS RECORDED rather than folded into the number, because a reader who cannot tell
    a declared lease from an inferred one cannot tell a fresh reference from an unjudged one.
    """
    target = _rel(path)
    env = _read_envelope(_abs(path))
    writer = UNMEASURED
    if env:
        writer = str(env.get("producer_component_id") or UNMEASURED)
    candidates = list(rows) if rows is not None else _registry_rows(registry)
    match: Mapping[str, Any] | None = None
    for row in candidates:
        outs = row.get("outputs")
        if isinstance(outs, (list, tuple)) and any(_rel(o) == target for o in outs):
            match = row
            break
    if match is not None:
        if writer == UNMEASURED:
            writer = str(match.get("component_id") or UNMEASURED)
        silence = match.get("max_silence_s")
        if isinstance(silence, (int, float)) and float(silence) > 0:
            return float(silence), "registry:max_silence_s", writer
        cadence = match.get("cadence_s")
        if isinstance(cadence, (int, float)) and float(cadence) > 0:
            return (float(cadence) * CADENCE_MULTIPLE,
                    f"derived:cadence_s({int(cadence)}s)x{CADENCE_MULTIPLE:g}", writer)
    if env:
        span = _envelope_lease_seconds(env)
        if span is not None:
            return span, "envelope:valid_until", writer
    declared = DERIVED_LEASES.get(target)
    if declared is not None:
        span, organ, derivation, _floor = declared
        return span, f"derived:{derivation}", (writer if writer != UNMEASURED else organ)
    return None, UNMEASURED, writer


def declared_floor(path: str | Path, default: int = 1) -> int:
    """The minimum row count this reference must carry to answer at all, where the desk has
    decided one. A stump is a reference that says nothing, however recently it was written."""
    row = DERIVED_LEASES.get(_rel(path))
    return int(row[3]) if row else int(default)


def _read_envelope(p: Path) -> Mapping[str, Any] | None:
    try:
        from libs.ops.control_plane import lease as _lease
    except ImportError:  # pragma: no cover - control plane always present in this tree
        return None
    try:
        env = _lease.read_envelope(p)
    except (OSError, ValueError):
        return None
    return env if isinstance(env, Mapping) else None


def _envelope_lease_seconds(env: Mapping[str, Any]) -> float | None:
    """The envelope's own window, as a span rather than a deadline, so it composes with the age
    measured below instead of being a second, disagreeing clock."""
    start = _parse_iso(env.get("finished_at") or env.get("created_at") or env.get("started_at"))
    until = _parse_iso(env.get("valid_until"))
    if start is None or until is None:
        return None
    span = (until - start).total_seconds()
    return span if span > 0 else None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value or value == UNMEASURED:
        return None
    try:
        t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def _age_seconds(p: Path, doc_stamp: Any = None, now: datetime | None = None) -> float | None:
    """CONTENT STAMP OUTRANKS MTIME (the fresh.py rule): a deploy, a formatter or a puller's
    revert rewrites a file and makes an mtime lie FRESH, which is the dangerous direction."""
    t = now or datetime.now(tz=UTC)
    stamped = _parse_iso(doc_stamp)
    if stamped is not None:
        return max(0.0, (t - stamped).total_seconds())
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
    except OSError:
        return None
    return max(0.0, (t - mtime).total_seconds())


_STAMP_KEYS = ("generated_at", "swept_at", "at", "written_at", "updated_at", "created_at",
               "measured_at", "as_of")


def _doc_stamp(doc: Any) -> Any:
    if not isinstance(doc, Mapping):
        return None
    env = doc.get("_envelope")
    if isinstance(env, Mapping):
        for key in ("finished_at", "created_at"):
            if env.get(key):
                return env[key]
    for key in _STAMP_KEYS:
        if doc.get(key):
            return doc[key]
    return None


# --------------------------------------------------------------------------- the guard

def assess_reference(path: str | Path, *, min_rows: int = 1, lease_s: float | None = None,
                     rows: int | None = None, rows_key: str | None = None,
                     registry: str | Path | None = None,
                     now: datetime | None = None) -> ReferenceState:
    """FRESH / EMPTY / STALE / UNREADABLE / MISSING for one reference store, with the evidence.

    `rows=` lets a caller that has already loaded the store hand in its own count rather than
    paying to read it twice; `lease_s=` overrides the resolved lease for a reference whose window
    the caller genuinely owns. Neither can turn a non-live reference live: both feed the same
    judgement below, which is the only place a verdict is decided.
    """
    p = _abs(path)
    rel = _rel(path)
    if not p.exists():
        return ReferenceState(
            path=rel, verdict=MISSING, live=False, rows=None, min_rows=min_rows,
            rows_source="absent", age_s=None, lease_s=lease_s,
            lease_source="explicit" if lease_s is not None else UNMEASURED, writer=UNMEASURED,
            why=(f"{rel} does not exist: the reference is UNMEASURED, which is a verdict about "
                 f"the measurement and never a statement that the world is empty (L1.28a)"))

    doc: Any = None
    measured = rows
    source = "caller"
    if measured is None:
        if p.suffix.lower() == ".json":
            try:
                doc = json.loads(p.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                return ReferenceState(
                    path=rel, verdict=UNREADABLE, live=False, rows=None, min_rows=min_rows,
                    rows_source=f"unreadable:{type(exc).__name__}", age_s=None, lease_s=lease_s,
                    lease_source="explicit" if lease_s is not None else UNMEASURED,
                    writer=UNMEASURED,
                    why=(f"{rel} could not be parsed ({type(exc).__name__}): an unreadable "
                         f"reference is UNMEASURED and never a licence to remove"))
            measured, source = count_rows_in(doc, rows_key=rows_key)
        else:
            measured, source = count_rows(p, rows_key=rows_key)

    resolved, lease_source, writer = lease_for(p, registry=registry)
    if lease_s is not None:
        resolved, lease_source = float(lease_s), "explicit"
    if doc is None and p.suffix.lower() == ".json" and rows is not None:
        try:
            doc = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            doc = None
    age = _age_seconds(p, _doc_stamp(doc), now=now)

    if measured is None:
        return ReferenceState(
            path=rel, verdict=UNREADABLE, live=False, rows=None, min_rows=min_rows,
            rows_source=source, age_s=age, lease_s=resolved, lease_source=lease_source,
            writer=writer,
            why=(f"{rel} exists but its rows could not be counted ({source}): UNREADABLE is "
                 f"UNMEASURED, and UNMEASURED never authorises a removal"))
    if measured < max(1, int(min_rows)):
        return ReferenceState(
            path=rel, verdict=EMPTY, live=False, rows=measured, min_rows=min_rows,
            rows_source=source, age_s=age, lease_s=resolved, lease_source=lease_source,
            writer=writer,
            why=(f"{rel} holds {measured} rows ({source}), below the floor of {min_rows}: a "
                 f"reference that says nothing is not a reference that says no. Its writer "
                 f"({writer}) owes it content before anything is removed against it"))
    if resolved is None:
        return ReferenceState(
            path=rel, verdict=UNREADABLE, live=False, rows=measured, min_rows=min_rows,
            rows_source=source, age_s=age, lease_s=None, lease_source=UNMEASURED, writer=writer,
            why=(f"{rel} has {measured} rows but NO lease and no cadence to derive one from "
                 f"(writer {writer}): its staleness has never been decided, so its age cannot be "
                 f"judged and it may not authorise a removal"))
    if age is None:
        return ReferenceState(
            path=rel, verdict=UNREADABLE, live=False, rows=measured, min_rows=min_rows,
            rows_source=source, age_s=None, lease_s=resolved, lease_source=lease_source,
            writer=writer,
            why=f"{rel} has {measured} rows but no readable age (no stamp, no mtime): UNMEASURED")
    if age > resolved:
        return ReferenceState(
            path=rel, verdict=STALE, live=False, rows=measured, min_rows=min_rows,
            rows_source=source, age_s=age, lease_s=resolved, lease_source=lease_source,
            writer=writer,
            why=(f"{rel} is {age / 3600.0:.1f}h old against a {resolved / 3600.0:.1f}h lease "
                 f"({lease_source}): stale beyond its lease is UNMEASURED. Its writer ({writer}) "
                 f"has not spoken since, so nothing may be removed on its authority"))
    return ReferenceState(
        path=rel, verdict=FRESH, live=True, rows=measured, min_rows=min_rows, rows_source=source,
        age_s=age, lease_s=resolved, lease_source=lease_source, writer=writer,
        why=(f"{rel} is live: {measured} rows ({source}), {age / 3600.0:.1f}h old inside a "
             f"{resolved / 3600.0:.1f}h lease ({lease_source}, writer {writer})"))


def assess_rows(name: str, rows: Any, *, min_rows: int = 1, measured: bool = True,
                source: str = "computed-this-pass") -> ReferenceState:
    """The same verdict for a reference that is a COLLECTION rather than a file.

    Some destructive passes judge against something they computed a line earlier -- the set of
    payloads a conversion produced, the rows a query returned. That reference has no mtime and no
    lease (it is zero seconds old by construction), but it has the failure this law is about: when
    the producer upstream silently yielded nothing, "not in the live set" becomes true of
    EVERYTHING. `measured=False` is for the case where the producer could not run at all, which is
    UNREADABLE rather than EMPTY -- a distinction the caller knows and this module cannot infer.
    """
    n: int | None
    if rows is None:
        n = None
    elif isinstance(rows, int):
        n = int(rows)
    else:
        try:
            n = len(rows)
        except TypeError:
            n = None
    if not measured or n is None:
        return ReferenceState(
            path=name, verdict=UNREADABLE, live=False, rows=n, min_rows=min_rows,
            rows_source=source, age_s=0.0, lease_s=None, lease_source="in-memory",
            writer=UNMEASURED,
            why=(f"{name} could not be measured this pass: UNMEASURED is a verdict about the "
                 f"measurement and never a licence to remove (L1.28a)"))
    if n < max(1, int(min_rows)):
        return ReferenceState(
            path=name, verdict=EMPTY, live=False, rows=n, min_rows=min_rows, rows_source=source,
            age_s=0.0, lease_s=None, lease_source="in-memory", writer=UNMEASURED,
            why=(f"{name} came back with {n} rows ({source}), below the floor of {min_rows}: a "
                 f"reference that says nothing is not a reference that says no"))
    return ReferenceState(
        path=name, verdict=FRESH, live=True, rows=n, min_rows=min_rows, rows_source=source,
        age_s=0.0, lease_s=None, lease_source="in-memory", writer=UNMEASURED,
        why=f"{name} is live: {n} rows ({source}), computed this pass")


def require_live_rows(name: str, rows: Any, *, actor: str, action: str, min_rows: int = 1,
                      measured: bool = True, source: str = "computed-this-pass",
                      strict: bool = False, record: bool = True) -> ReferenceState:
    """`require_live_reference` for an in-memory reference. Same contract, same recording."""
    state = assess_rows(name, rows, min_rows=min_rows, measured=measured, source=source)
    if state.live:
        return state
    if record:
        record_stand_down(state, actor=actor, action=action)
    if strict:
        raise ReferenceNotLive(state)
    return state


def require_live_reference(path: str | Path, *, actor: str, action: str, min_rows: int = 1,
                           lease_s: float | None = None, rows: int | None = None,
                           rows_key: str | None = None, registry: str | Path | None = None,
                           strict: bool = False, record: bool = True,
                           now: datetime | None = None) -> ReferenceState:
    """The one call every destructive pass makes before it removes anything.

    Returns the state. `state.live` is True only for FRESH; every other verdict is a stand-down,
    recorded where an operator sees it. `strict=True` raises `ReferenceNotLive` instead, for a
    caller whose correct degrade direction is to abort rather than to continue with the removals
    skipped. The live path is untouched: a fresh reference returns and the pass proceeds exactly
    as it did before this module existed.
    """
    state = assess_reference(path, min_rows=min_rows, lease_s=lease_s, rows=rows,
                             rows_key=rows_key, registry=registry, now=now)
    if state.live:
        return state
    if record:
        record_stand_down(state, actor=actor, action=action)
    if strict:
        raise ReferenceNotLive(state)
    return state


def stand_down(state: ReferenceState, *, actor: str, action: str,
               **extra: Any) -> dict[str, Any]:
    """The record a destructive pass RETURNS when it removes nothing, so the refusal is a
    published verdict rather than a quiet no-op."""
    return {
        "stood_down": True, "actor": actor, "action": action, "at": state.at,
        "reference": state.path, "verdict": state.verdict, "why": state.why,
        "rows": state.rows, "min_rows": state.min_rows, "rows_source": state.rows_source,
        "age_s": state.age_s, "lease_s": state.lease_s, "lease_source": state.lease_source,
        "writer": state.writer, "removed": 0, "law": "LAWS 7: NOTHING IS RETIRED ON AN ABSENCE",
        **extra,
    }


def record_stand_down(state: ReferenceState, *, actor: str, action: str,
                      path: Path | None = None) -> dict[str, Any]:
    """Append the refusal to the operator-visible log and emit the event.

    Best-effort BY DESIGN: a telemetry failure must never convert a refusal-to-delete back into a
    deletion. The failure is still loud -- the fence reads an empty log as UNMEASURED.
    """
    row = stand_down(state, actor=actor, action=action)
    target = path if path is not None else _resolved_log()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(f"reference_freshness: stand-down NOT logged ({type(exc).__name__}: {exc})",
              flush=True)
    try:
        from libs.ops import events as _events
        _events.emit("REFERENCE_STAND_DOWN", actor=actor, action=action, reference=state.path,
                     verdict=state.verdict, rows=state.rows, age_s=state.age_s,
                     lease_s=state.lease_s, lease_source=state.lease_source, why=state.why)
    except Exception as exc:  # telemetry never breaks a refusal
        print(f"reference_freshness: stand-down event NOT emitted ({type(exc).__name__}: {exc})",
              flush=True)
    return row


def _resolved_log() -> Path:
    """The log path, overridable by env so a test never writes a tracked artifact."""
    override = os.environ.get("QUANT_REFERENCE_STANDDOWN_LOG")
    return Path(override) if override else STANDDOWN_LOG


def stand_downs(limit: int | None = None, path: Path | None = None) -> list[dict[str, Any]]:
    """The recorded refusals, newest last. An unreadable log returns [] -- which the fence reports
    as UNMEASURED rather than as 'no refusals happened'."""
    target = path if path is not None else _resolved_log()
    try:
        lines = target.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
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


# --------------------------------------------------------------------------- the inventory

@dataclass(frozen=True)
class DestructivePath:
    """One act in this tree that REMOVES rather than reports, and the reference it judges against.

    `status`:
      * ``guarded``      -- calls this module before removing; the fence proves the call is there.
      * ``positive``     -- removes only on POSITIVE evidence (a venue said no, a row was voided by
                            a reading that exists), so an absent reference already removes nothing.
                            This is the gauntlet's pattern and the one the desk copies.
      * ``sealed``       -- inside an immutable file; reported for the principal, never edited.
      * ``unguarded``    -- still to do. The fence's ratchet counts these and they may only fall.
    """

    path_id: str
    module: str
    function: str
    removes: str
    reference: str
    status: str
    #: The function in `module` that holds the guard call. Usually `function` itself; a caller one
    #: hop up when the removal is a helper the guarded entry point wraps.
    guard_site: str = ""
    #: Why a `positive`/`sealed` row needs no guard, or what an `unguarded` row is waiting on.
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["guard_site"] = self.guard_site or self.function
        return row


#: EVERY destructive path this desk knows about. Adding a removal without adding a row here is
#: what the fence's tree scan catches; the scan finds candidates, this list says what was DECIDED
#: about each one. A row is never deleted -- an act that stops removing becomes `positive` with a
#: note, so the history of what once removed on an absence stays readable.
DESTRUCTIVE_PATHS: tuple[DestructivePath, ...] = (
    DestructivePath(
        path_id="certificate_truth.apply",
        module="desks/mt5/research/certificate_truth.py",
        function="apply",
        removes="rows in every derived certificate store (survivor ledger, sleeve registry, "
                "shadow/lane states, sleeves.json, forward_reconcile)",
        reference="desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
        status="unguarded",
        note="THE PROVING INSTANCE: 837 rows retired against an empty 46.7h-stale canon. Owned "
             "by another builder this session (restoring the rows); the guard call lands there, "
             "not here. Guard usage: require_live_reference(canon, actor='certificate_truth."
             "apply', action='retire unbacked rows', min_rows=1, strict=False).",
    ),
    DestructivePath(
        path_id="certificate_truth.ledger_claims",
        module="desks/mt5/research/certificate_truth.py",
        function="apply",
        removes="SURVIVORS_LEDGER.json claims flipped to status=RETIRED (CLAIM_NOT_IN_CANON)",
        reference="desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
        status="unguarded",
        note="The ledger branch is NOT behind the `lane_settled` gate that protects the clock "
             "rows two blocks below, so an unsettled or empty canon still retires ledger claims. "
             "Same file and same owner as certificate_truth.apply above; one guard at the top of "
             "apply() closes both. Reported, not edited, to avoid racing that builder.",
    ),
    DestructivePath(
        path_id="certificate_truth.clock_rows",
        module="desks/mt5/research/certificate_truth.py",
        function="apply",
        removes="clock/registry/shadow rows flipped to RETIRED with promotion_authority=False",
        reference="desks/mt5/data/UNIVERSAL_SURVIVORS.canon.json",
        status="positive",
        guard_site="apply",
        note="ALREADY CORRECT and the strongest existing instance: `lane_settled` requires the "
             "canon to read EXACT with n>0 and zero restorable retirements before a single clock "
             "row is touched. It is the shape this module generalises.",
    ),
    DestructivePath(
        path_id="retire_uncashable_certs.retire",
        module="desks/mt5/scripts/retire_uncashable_certs.py",
        function="retire",
        removes="survivors moved to retired_certificates in UNIVERSAL_SURVIVORS.json and the "
                "canon",
        reference="desks/mt5/data/universe/universe.json",
        status="guarded",
        guard_site="main",
        note="Had `if not meta` but no STUMP FLOOR and no age: a 23-symbol registry passed and "
             "would have retired the whole book. Now require_live_reference(min_rows=50).",
    ),
    DestructivePath(
        path_id="retire_untradeable.retire",
        module="desks/mt5/research/retire_untradeable.py",
        function="retire",
        removes="survivors dropped from UNIVERSAL_SURVIVORS.json into retired_certificates",
        reference="desks/mt5/data/universe/universe.json",
        status="guarded",
        note="The predicate demands positive venue evidence but READS it out of the registry, "
             "which was loaded with an unguarded json.loads. Now floored and aged.",
    ),
    DestructivePath(
        path_id="purge_untradeable_certs.main",
        module="scripts/purge_untradeable_certs.py",
        function="main",
        removes="survivors dropped from the canon into data/UNTRADEABLE_CERTS.json",
        reference="desks/mt5/data/universe/universe.json",
        status="positive",
        note="THE MODEL GUARD this law generalises: `if len(syms) < 50: return 1` -- 'a truncated "
             "universe would retire the whole book'. Left as it is; its floor is the number the "
             "two guarded siblings above now use.",
    ),
    DestructivePath(
        path_id="screen_conversion.write_converted",
        module="libs/research/screen_conversion.py",
        function="write_converted",
        removes="conv_*.json screen artifacts unlinked from the canonical axis directory",
        reference="convert_all() payloads (in-memory, computed this pass)",
        status="guarded",
        note="THE WORST UNGUARDED CASE FOUND. convert_all skips every source it cannot read, so "
             "one upstream outage returned zero payloads and 'absent from the live set' became "
             "true of every converted screen on disk. Now require_live_rows(min_rows=1).",
    ),
    DestructivePath(
        path_id="workers.prune",
        module="libs/ops/workers.py",
        function="prune",
        removes="rows DELETEd from the workers sqlite table",
        reference="the workers table's own last_seen heartbeats",
        status="guarded",
        note="An unconditional DELETE on a timestamp: a dead stamper, a clock skew or a restore "
             "makes every row look stale at once and erases the live fleet. Now stands down when "
             "the table is non-empty and NO row is inside the window.",
    ),
    DestructivePath(
        path_id="proctree.reap_orphaned_workers",
        module="libs/ops/proctree.py",
        function="reap_orphaned_workers",
        removes="pool worker PROCESSES, killed",
        reference="the live process table (psutil scan)",
        status="guarded",
        note="'Orphan' means 'parent pid absent from the table', so an empty or partial table "
             "manufactures orphans out of well-parented workers and kills them. The table is now "
             "required to contain this process's own pid before anything is killed.",
    ),
    DestructivePath(
        path_id="certificate_hygiene.apply",
        module="desks/mt5/research/certificate_hygiene.py",
        function="apply",
        removes="survivors popped out of UNIVERSAL_SURVIVORS.json and the canon into "
                "UNIVERSAL_SURVIVORS_UNRUNNABLE.json",
        reference="build()'s per-row unrunnable_reason verdicts",
        status="positive",
        note="Correct as written: every moved key carries a POSITIVE per-row reason from "
             "survivor_publication.unrunnable_reason, and build() returns UNMEASURED with no "
             "`unrunnable` list when the judge or the registry is unreadable, so apply() moves "
             "nothing. A partial registry yields FEWER evictions, never more.",
    ),
    DestructivePath(
        path_id="forward_reconcile.orphan_clocks",
        module="desks/mt5/research/forward_reconcile.py",
        function="main",
        removes="shadow clock rows flipped to RETIRED_ORPHAN / RETIRED_UNRECONSTRUCTIBLE",
        reference="desks/mt5/reports/UNIVERSAL_SURVIVORS.json (via certified_clock_keys) and the "
                  "enrolment set (via enrolled_keys)",
        status="positive",
        note="Already correct: enrolled_keys() returns None for UNKNOWN and never the empty set, "
             "`unknown_enrolment` suppresses the orphan branch, and `if not certs: return 0` "
             "refuses the unreconstructible branch outright.",
    ),
    DestructivePath(
        path_id="clock_retirement.accept",
        module="libs/research/clock_retirement.py",
        function="accept",
        removes="a forward slot, permanently, by appending to the retirement ledger (shrinks the "
                "Holm cohort m)",
        reference="the live sweep payload passed in by run_clock_retirement_sweep",
        status="positive",
        note="Exemplary and untouched: refuses BLOCKED, refuses ACCRUING/protected, refuses any "
             "name absent from THIS sweep, demands an attributed decider, and keeps "
             "multiplicity_floor as a high-water mark so m can never be silently shrunk.",
    ),
    DestructivePath(
        path_id="run_paper_sleeve_spawner.retire_axis_slot",
        module="scripts/run_paper_sleeve_spawner.py",
        function="_retire_axis_slot",
        removes="an axis row flipped to verdict=RETIRED in data/axis_shadow_state.json",
        reference="data/axis_shadow_state.json, re-read at the moment of the write",
        status="positive",
        note="Already correct: refuses when the state file is missing or unreadable and when the "
             "row has vanished; an already-retired row is a no-op.",
    ),
    DestructivePath(
        path_id="job_lock.steal_stale",
        module="desks/mt5/research/job_lock.py",
        function="exclusive_job",
        removes="another process's job lock file",
        reference="the owner pid's liveness, read at the moment of the steal",
        status="positive",
        note="Already correct: liveness VETOES age -- a lock older than STALE_SECONDS whose owner "
             "is alive is left alone, and release only unlinks while the token still matches.",
    ),
    DestructivePath(
        path_id="git_writer_lock.steal_stale",
        module="libs/ops/git_writer_lock.py",
        function="_acquire_file",
        removes="another writer's claim on the git writer lock",
        reference="lock-file age AND the owner pid's liveness",
        status="positive",
        note="Already correct: both conditions are required before a steal.",
    ),
    DestructivePath(
        path_id="worktree_reaper.remove_checkout",
        module="libs/ops/worktree_reaper.py",
        function="remove_checkout",
        removes="a git worktree checkout, escalating to `worktree remove --force`",
        reference="`git status --porcelain`, re-read AT removal time",
        status="positive",
        note="Already correct: the re-verification at removal time is the race-safety argument, "
             "and an unreadable status refuses rather than reaps.",
    ),
    DestructivePath(
        path_id="protected_artifacts.restore",
        module="libs/ops/protected_artifacts.py",
        function="restore",
        removes="a protected artifact that did not exist before the run",
        reference="the pre-run Snapshot",
        status="positive",
        note="Already correct: unlinks only where the snapshot POSITIVELY says the file did not "
             "exist, never where the snapshot simply has no opinion.",
    ),
    DestructivePath(
        path_id="archive_tape.delete_after_upload",
        module="desks/mt5/scripts/archive_tape.py",
        function="main",
        removes="irreplaceable tape parquet partitions, deleted after archiving",
        reference="the verified upload/copy result for that exact partition",
        status="positive",
        note="Already correct: the manifest is appended BEFORE the delete and the unlink happens "
             "only on a verified ok; a failure keeps the source and reports.",
    ),
    DestructivePath(
        path_id="run_miner_maintenance.sweep_locks",
        module="scripts/run_miner_maintenance.py",
        function="sweep_locks",
        removes="job lock files belonging to other jobs",
        reference="the owner pid's liveness",
        status="positive",
        note="Already correct: deletes only on alive is False; unreadable is UNREPAIRABLE and "
             "left in place; old-but-alive is LEFT_ALONE.",
    ),
    DestructivePath(
        path_id="disk_guard.reap_tmpfs_worktrees",
        module="scripts/disk_guard.py",
        function="reap_tmpfs_worktrees",
        removes="git worktrees on tmpfs",
        reference="live process cwds, `git status --porcelain`, `git branch --contains HEAD`",
        status="positive",
        note="Already correct: four positive gates, every refusal named.",
    ),
    DestructivePath(
        path_id="disk_guard.reap_tmpfs",
        module="scripts/disk_guard.py",
        function="reap_tmpfs",
        removes="scratch files under /tmp",
        reference="the live open-file table and the registered-worktree list",
        status="positive",
        note="Already correct: registered checkouts are excluded wholesale and a retention cutoff "
             "bounds the rest, so an empty open-file table reaps nothing it should keep.",
    ),
    DestructivePath(
        path_id="watchdog.reap_deadman",
        module="scripts/watchdog.py",
        function="_reap_deadman",
        removes="the deadman marker file",
        reference="the marker's own presence (a self-clearing flag)",
        status="positive",
        note="A single-shot consume of a flag this process owns; there is no reference store "
             "whose emptiness could widen it.",
    ),
    DestructivePath(
        path_id="run_law_gate.reap_stale_checkouts",
        module="scripts/run_law_gate.py",
        function="_reap_stale_checkouts",
        removes="orphaned lawgate-head-* tmpfs checkouts, force-removed",
        reference="its own directory prefix and an age floor a live run cannot reach",
        status="positive",
        note="Already correct: it only reaps directories it alone creates.",
    ),
    DestructivePath(
        path_id="reclaim_disk.shed",
        module="desks/mt5/scripts/reclaim_disk.py",
        function="shed_bars_to_target",
        removes="bar-lake parquet files and the MetaTrader history cache",
        reference="live free-space readings from shutil.disk_usage",
        status="positive",
        note="Already correct: an unreadable disk sheds nothing, `_is_protected` is applied, and "
             "it stops the moment the target is met.",
    ),
    DestructivePath(
        path_id="knowledge_graph.evict_leads",
        module="desks/mt5/research/knowledge_graph.py",
        function="evict_leads",
        removes="lead nodes, their edges and their index entries from the graph store",
        reference="MAX_LEAD_NODES, a capacity cap (no external store)",
        status="positive",
        note="A size cap, not a judgement: it evicts oldest-first only when the store is OVER "
             "capacity, so an empty or unreadable anything evicts nothing.",
    ),
    DestructivePath(
        path_id="campaign_queue.cleanup",
        module="libs/ops/campaign_queue.py",
        function="cleanup",
        removes="terminal campaign rows DELETEd from the campaigns table",
        reference="each row's own finished_at against a retention cutoff",
        status="positive",
        note="Scoped to rows that positively declare themselves done or cancelled AND carry a "
             "finished_at past the cutoff; the audit table is untouched.",
    ),
    DestructivePath(
        path_id="moat_registry.retire_crypto_cards",
        module="libs/moat/registry.py",
        function="_retire_crypto_cards",
        removes="alpha_cards flipped to status=retired in the moat sqlite",
        reference="the card's own name/market against CRYPTO_MARKETS (the universe mandate)",
        status="positive",
        note="Positive per-row predicate carrying an alpha_events audit row; an empty table "
             "retires nothing. The mandate it enforces is LAWS 1, not a freshness question.",
    ),
    DestructivePath(
        path_id="lifecycle_actions.apply_retirement",
        module="libs/self_improvement/lifecycle_actions.py",
        function="apply_retirement",
        removes="one alpha card transitioned to RETIRED (archived, audited, never deleted)",
        reference="the caller's named candidate id and the lifecycle state machine",
        status="positive",
        note="A single-id transition on a positively named card, idempotent through the state "
             "machine. There is no reference store whose emptiness could widen it.",
    ),
    DestructivePath(
        path_id="external_gauntlet.certificate_purge",
        module="desks/mt5/scripts/external_gauntlet.py",
        function="main",
        removes="survivors moved out of UNIVERSAL_SURVIVORS.json into retired_certificates",
        reference="desks/mt5/data/universe/universe.json meta, judged by "
                  "certificate_retirement_reason",
        status="positive",
        note="SEALED and already correct: `if meta:` skips the whole purge block on an empty "
             "registry, a shrink guard and a never-write-empty guard sit above it, and the "
             "restore loop re-asks the predicate every pass. This is the pattern the rest of the "
             "desk copies. FOR THE PRINCIPAL: it carries no STUMP FLOOR -- a truncated registry "
             "passes `if meta:` -- which is the one gap the sealed file cannot be edited to fix "
             "from here (`scripts/purge_untradeable_certs.py:43` shows the fix: len(syms) < 50).",
    ),
    DestructivePath(
        path_id="promoter.retire_unrunnable",
        module="desks/mt5/research/promoter.py",
        function="retire_unrunnable",
        removes="LIVE/STANDBY sleeve rows flipped to RETIRED with risk_frac=0",
        reference="desks/mt5/reports/UNIVERSAL_SURVIVORS_UNRUNNABLE.json",
        status="positive",
        note="SEALED and already correct: `if not keys: return False` -- an empty or unreadable "
             "eviction file retires nothing, and rows carrying explicit params are skipped.",
    ),
    DestructivePath(
        path_id="promoter.retire_banned",
        module="desks/mt5/research/promoter.py",
        function="retire_banned",
        removes="sleeve rows flipped to RETIRED and queued into RETIRED_CLOSE_QUEUE.json",
        reference="research/family_policy.py + data/banned_families.json, with parole evidence "
                  "from reports/shadow/ledger_<clock>.json",
        status="sealed",
        note="FOR THE PRINCIPAL. A ban is a decision rather than a measurement, so the ban half "
             "is correctly absence-insensitive. But the PAROLE half is an evidence door that "
             "fails toward retiring: an unreadable ledger reads as 'not paroled' and the sleeve "
             "is retired anyway. That is the LAWS 7 shape -- an absent reading standing in for a "
             "negative one -- inside a sealed file. The fix would be to treat an unreadable "
             "parole ledger as UNMEASURED and leave the row alone until it can be read.",
    ),
    DestructivePath(
        path_id="promoter.gold_retired_revalidation",
        module="desks/mt5/research/promoter.py",
        function="retirement_void_reason",
        removes="GOLD_RETIRED entries (voided to GOLD_RETIRED_VOIDED.json)",
        reference="the live account's own deal ledger",
        status="positive",
        note="SEALED and already correct: an entry is voided on POSITIVE evidence only (a "
             "degenerate admissible series, or n rows stamped to another account); an empty, "
             "short, unreadable or unstamped ledger never voids.",
    ),
    DestructivePath(
        path_id="promoter.apply_live_policy",
        module="desks/mt5/research/promoter.py",
        function="_apply_live_policy",
        removes="every LIVE/STANDBY row the live policy refuses, flipped to RETIRED in "
                "sleeves.json, on every save_sleeves",
        reference="mt5desk.live_policy.policy()",
        status="sealed",
        note="FOR THE PRINCIPAL. An ImportError returns 0 (correct), but a policy object that "
             "imports and comes back EMPTY is not checked -- and an empty policy refuses "
             "everything, which retires the whole live book on the next save. Same shape as the "
             "canon incident, inside a sealed file. The fix would be one emptiness floor on "
             "`pol` before the loop.",
    ),
    DestructivePath(
        path_id="state_admission.graveyard",
        module="libs/regime/state_admission.py",
        function="admitted",
        removes="nothing -- a GRAVEYARD dimension is excluded from the returned tuple",
        reference="n/a (report-only classifier)",
        status="positive",
        note="SEALED and CLEARED: no write, no file, no row leaves any store. Recorded here so "
             "the next audit does not have to re-read the sealed file to find that out.",
    ),
    DestructivePath(
        path_id="allocator_proof.no_destructive_path",
        module="libs/portfolio/allocator_proof.py",
        function="certify",
        removes="nothing",
        reference="n/a",
        status="positive",
        note="SEALED and CLEARED: zero removal acts in the file. Recorded so the audit is a "
             "measurement rather than an absence.",
    ),
)


def inventory_rows() -> list[dict[str, Any]]:
    """The declared inventory as plain rows, for the fence and the artifact."""
    return [p.as_dict() for p in DESTRUCTIVE_PATHS]


def by_id(path_id: str) -> DestructivePath | None:
    for p in DESTRUCTIVE_PATHS:
        if p.path_id == path_id:
            return p
    return None


def unguarded() -> list[DestructivePath]:
    """The paths that still remove without proving their reference. Ratchets DOWN only."""
    return [p for p in DESTRUCTIVE_PATHS if p.status == "unguarded"]


def guard_call_names() -> tuple[str, ...]:
    """The call names that COUNT as a guard, for the fence's AST proof."""
    return ("require_live_reference", "assess_reference", "reference_is_live",
            "require_live_rows", "assess_rows")


def reference_is_live(path: str | Path, *, min_rows: int = 1,
                      registry: str | Path | None = None) -> bool:
    """The one-line form, for a call site that only needs the boolean. It still records nothing
    and decides nothing -- a caller that removes on `False` has inverted the law."""
    return assess_reference(path, min_rows=min_rows, registry=registry).live


def summarise(states: Sequence[ReferenceState]) -> dict[str, Any]:
    """A verdict histogram for an organ that checks several references in one pass."""
    counts: dict[str, int] = {}
    for s in states:
        counts[s.verdict] = counts.get(s.verdict, 0) + 1
    return {
        "n": len(states),
        "live": sum(1 for s in states if s.live),
        "by_verdict": dict(sorted(counts.items())),
        "not_live": [{"path": s.path, "verdict": s.verdict, "why": s.why}
                     for s in states if not s.live],
    }
