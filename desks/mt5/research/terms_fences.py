"""Sources whose terms forbid commercial use do not reach the candidate compiler.

The desk's rule: a source whose own terms forbid machine or commercial use stays fail-closed.
The BIS speech feed was read on 2026-11-10 as "allowed for noncommercial purposes" and its rows
sat in the donation tree, where the compiler reads every file. This is the fence: a matching
file is parked (left on disk, counted, named with what it costs) and not read.

FAIL-CLOSED IN BOTH DIRECTIONS. The registry (`terms_fences.json`) can add fences and can reopen
one, but a fence built into this module is enforced even if the registry is missing, unreadable,
has had the row removed or has had its patterns emptied or narrowed; and a fence is open only
with `open: true` AND a pasted permitting clause, so a stray flag cannot reopen it.
"""
from __future__ import annotations

import fnmatch
import json
from collections.abc import Mapping
from pathlib import Path, PurePath
from typing import Any

REGISTRY = Path(__file__).with_name("terms_fences.json")

#: Enforced whatever the registry says, unless the registry reopens it with a clause.
BUILT_IN: tuple[dict[str, Any], ...] = (
    {"id": "bis_speeches",
     "match": ["bis_speeches/*", "central_banks/bis_speech_tone.jsonl",
               "central_banks/cb_tone_series.jsonl"],
     "seats": ["bis_speeches"],
     "reason": "BIS terms allow noncommercial use only",
     "missed_growth": "central bank speech titles and tone from BIS are not compiled into "
                      "candidates"},
    {"id": "congress_trades",
     "match": ["congress_trades/*", "free_stack/congress_trades*"],
     "seats": ["congress_trades"],
     "reason": "5 U.S.C. 13107(c) makes commercial use of congressional disclosure reports "
               "unlawful",
     "missed_growth": "congressional disclosure series are not fetched or compiled into cells"},
)


def is_open(fence: Mapping[str, Any]) -> bool:
    """Reopened only on the flag AND a permitting sentence someone pasted from the terms page."""
    return fence.get("open") is True and len(str(fence.get("permit_clause") or "").strip()) >= 20


_CACHE: dict[str, Any] = {"key": None, "fences": None}


def current() -> list[dict[str, Any]]:
    """The shipped registry's fences, cached per process and re-read when the file's mtime (or
    its presence) changes -- so a per-cell caller does not re-parse the registry every call."""
    try:
        key: Any = (str(REGISTRY), REGISTRY.stat().st_mtime_ns)
    except OSError:
        key = (str(REGISTRY), "absent")
    if _CACHE["fences"] is None or _CACHE["key"] != key:
        _CACHE.update({"key": key, "fences": load()})
    return list(_CACHE["fences"])


def load(registry: Path | None = None) -> list[dict[str, Any]]:
    """The fences in force: the registry's rows, plus any built-in one the registry lacks."""
    try:
        doc = json.loads((registry or REGISTRY).read_text("utf-8"))
        rows = [dict(f) for f in doc.get("fences") or [] if isinstance(f, dict) and f.get("id")]
    except (OSError, ValueError, AttributeError):
        rows = []
    # A registry row may ADD patterns or seats to a built-in fence and may reopen it with a
    # clause; it can never narrow it. An emptied or shortened `match` is the same as a removed
    # row: the built-in patterns are still enforced.
    by_id = {str(f["id"]): f for f in rows}
    for built in BUILT_IN:
        row = by_id.get(built["id"])
        if row is None:
            rows.append(dict(built))
            continue
        for key in ("match", "seats"):
            got = row.get(key)
            mine: list[Any] = list(got) if isinstance(got, list) else []
            row[key] = mine + [x for x in built.get(key) or [] if x not in mine]
        for key in ("reason", "missed_growth"):
            row[key] = row.get(key) or built.get(key, "")
    return [f for f in rows if not is_open(f)]


def path_fenced(path: Path | str, fences: list[dict[str, Any]] | None = None
                ) -> dict[str, Any] | None:
    """THE ONE PREDICATE for a file: is it behind a closed fence? The path is read relative to
    the last `intelligence` directory in it; a path outside any intelligence tree is not fenced.
    Every reader whose output can reach a candidate, a factor, a verdict or sizing calls this
    (or `seat_fenced`) before it reads."""
    parts = PurePath(path).parts
    if "intelligence" not in parts:
        return None
    i = len(parts) - 1 - parts[::-1].index("intelligence")
    rel = PurePath(*parts[i + 1:]) if parts[i + 1:] else None
    if rel is None:
        return None
    return fence_for(rel, current() if fences is None else fences)


def seat_fenced(seat: str, fences: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """The same question for a whole source directory or miner name (`seats` in the fence)."""
    for f in (current() if fences is None else fences):
        if str(seat).lower() in {str(x).lower() for x in f.get("seats") or []}:
            return f
    return None


def fence_for(rel: PurePath | str, fences: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The closed fence this intelligence-relative path falls behind, if any."""
    s = PurePath(rel).as_posix().lower()
    for f in fences:
        if any(fnmatch.fnmatchcase(s, str(pat).lower()) for pat in f.get("match") or []):
            return f
    return None


# ------------------------------------------------------------------ the quarantine sweep ----
#: Where the free-stack hunter publishes `fs_<seat>` frames and the exogenous conditioner reads
#: them (`family_exogenous_conditioner.SERIES_DIR`; named here from this file's location so the
#: research side never imports the money path to find it).
DESK = Path(__file__).resolve().parents[1]
SERIES_DIR = DESK / "data" / "lake" / "series"
#: Outside the series dir, under the hunter's own (gitignored) store: a frame parked here can no
#: longer be found by any reader that looks for `fs_<seat>` in SERIES_DIR.
QUARANTINE_DIR = DESK / "data" / "free_stack" / "terms_quarantine"
QUARANTINE_LEDGER = DESK / "data" / "free_stack" / "terms_quarantine.jsonl"
_FRAME_SUFFIXES = (".parquet", ".csv")


def _sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _frame_columns(path: Path) -> list[str]:
    """The frame's signal columns, best effort, for the missed-growth line. Never raises."""
    stamp = {"event_time", "published_time", "available_time", "revision_time",
             "retrieval_time", "ingested_time", "source_id", "vintage_id", "period_end",
             "first_seen"}
    cols: list[str] = []
    try:
        if path.suffix == ".csv":
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                cols = [c.strip() for c in fh.readline().strip().split(",") if c.strip()]
        else:
            import pyarrow.parquet as pq
            cols = [str(c) for c in pq.read_schema(path).names]
    except Exception:
        return []
    return [c for c in cols if c not in stamp]


def _free_destination(qdir: Path, name: str) -> Path:
    """A destination that does not exist yet: never overwrite (and so never meet a read-only
    destination on Windows); a collision keeps both, the newcomer with a numbered suffix."""
    dest = qdir / name
    n = 1
    while dest.exists():
        p = PurePath(name)
        dest = qdir / f"{p.stem}.q{n}{p.suffix}"
        n += 1
    return dest


def quarantine_fenced_frames(series_dir: Path | None = None, quarantine_dir: Path | None = None,
                             ledger_path: Path | None = None, now: Any = None,
                             fences: list[dict[str, Any]] | None = None
                             ) -> list[dict[str, Any]]:
    """Move every `fs_<seat>` frame whose seat is behind a closed fence OUT of the series dir.

    Data harvested before a fence closed must stop feeding the exogenous conditioner, which reads
    the series dir by name and does not consult the fence itself. The frame is RENAMED, never
    deleted (its bytes and sha256 are kept, and the ledger says where it went), so reopening the
    fence is a move back. One append-only ledger line per frame, with the fence's reason and the
    conditioned arms that lost an input (`missed_growth`). Idempotent: once the series dir holds
    no fenced frame, a run moves nothing and writes nothing. Never touches an unfenced or a
    non-`fs_` frame. Returns the ledger lines it wrote.
    """
    import os
    from datetime import UTC, datetime
    sdir = Path(series_dir or SERIES_DIR)
    qdir = Path(quarantine_dir or QUARANTINE_DIR)
    ledger = Path(ledger_path or QUARANTINE_LEDGER)
    when = now or datetime.now(UTC)
    stamp = when.isoformat(timespec="seconds") if hasattr(when, "isoformat") else str(when)
    fs_now = current() if fences is None else fences
    if not sdir.is_dir():
        return []
    wrote: list[dict[str, Any]] = []
    for p in sorted(sdir.iterdir()):
        if not (p.is_file() and p.name.startswith("fs_") and p.suffix in _FRAME_SUFFIXES):
            continue
        fence = seat_fenced(p.stem[3:], fs_now)
        if fence is None:
            continue
        digest = _sha256(p)
        cols = _frame_columns(p)
        qdir.mkdir(parents=True, exist_ok=True)
        dest = _free_destination(qdir, p.name)
        os.replace(p, dest)
        line = {"at_utc": stamp, "path": str(p), "quarantined_to": str(dest), "sha256": digest,
                "bytes": dest.stat().st_size, "fence": str(fence.get("id", "")),
                "reason": str(fence.get("reason", "")),
                "missed_growth": {
                    "arms_lost_input": [f"exogenous_conditioner:{p.stem}"]
                    + [f"exogenous_conditioner:{p.stem}:{c}" for c in cols],
                    "what": str(fence.get("missed_growth", "")),
                    "reading": "those arms read UNMEASURED and emit nothing until the fence "
                               "is reopened and the frame moved back"},
                "reopen": "terms_fences.json: open=true with the permitting clause pasted, "
                          "then move quarantined_to back to path (sha256 above)"}
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
        wrote.append(line)
    return wrote

