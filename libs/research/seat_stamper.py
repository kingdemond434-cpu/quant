"""SEAT STAMPER: a name-stamped reading for every intelligence seat whose files carry no time.

THE GAP (measured 2026-09-30, the D18 fence). Five enrolled seats were UNFED with "no snapshot file
carries a time in its name": `brain` (peer_group_maps.json), `cohorts` (cohort_registry.json),
`fxmerge` (fxmerge_archived_records.json), `mql5_reputation` (reputation_history.jsonl) and, until
dataset_series learnt YAML, `hypotheses`. Each is a STATE FILE rewritten in place. `dataset_series`
reads a seat only through file names that say when the desk knew their contents, and refuses an
mtime (an mtime is when git checked the file out, not when the desk learnt it) -- correctly. So a
seat whose writer overwrites one file can never hold a series, however long it runs.

THE FIX, without inventing a single timestamp. Two honest clocks say when the desk knew a state
file's contents:

    git       every committed version of the file, at its COMMIT time (the box commits its state
              hourly; the content existed at or before the commit, so the stamp is conservative);
    this      every content change this organ sees, at the moment it sees it.

Each is written as a DIGEST -- `{"records": <rows in the file>, "bytes": <size>}` -- under
`data/dataset_stamps/<seat>/stamp_<YYYYMMDD_HHMMSS>_<file>.json`, which `dataset_series` reads as a
third intelligence root. A digest is a READING (how much the seat held when the desk knew it), not a
claim: it sits outside `data/intelligence/**` on purpose, so the compiler never reads it twice.

Runs inside the hourly `dataset_exploitation` leg, before discovery. Idempotent: a ledger per seat
records the versions already stamped. Never raises; an unreadable version is skipped and named.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DESK = ROOT / "desks" / "mt5"
STAMPS = DESK / "data" / "dataset_stamps"
#: Git versions stamped per file per pass (the backfill is incremental across passes).
BACKFILL_PER_PASS = 200
#: Files larger than this are digested by size and line count only (never parsed whole).
PARSE_MAX_BYTES = 64 * 1024 * 1024
_SUFFIXES = (".json", ".jsonl", ".yaml", ".yml")


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", name.rsplit(".", 1)[0]).strip("-")[:40] or "file"


def records_in(blob: bytes, name: str) -> int:
    """How many records a state file holds: a JSONL's lines, a list's items, a mapping's largest
    list (a document's payload, e.g. `rows` or `maps`) or else its keys. 0 when unreadable."""
    if name.endswith(".jsonl"):
        return sum(1 for ln in blob.splitlines() if ln.strip())
    if len(blob) > PARSE_MAX_BYTES:
        return 0
    try:
        if name.endswith((".yaml", ".yml")):
            import yaml
            doc = yaml.safe_load(blob.decode("utf-8", "replace"))
        else:
            doc = json.loads(blob.decode("utf-8", "replace"))
    except Exception:
        return 0
    if isinstance(doc, list):
        return len(doc)
    if isinstance(doc, dict):
        payload = [len(v) for k, v in doc.items() if isinstance(v, (list, dict))
                   and not str(k).startswith("_")]
        # A mapping of records keyed by id (cohort_registry) is its own payload.
        if payload and max(payload) > 1:
            return max(payload) if len(doc) < 64 else len(doc)
        return len(doc)
    return 1


def unstamped_seats(roots: tuple[Path, ...] | None = None) -> dict[str, list[Path]]:
    """{seat: its non-empty state files} for every seat none of whose files is name-stamped."""
    from mt5desk import dataset_series as DS
    roots = roots or tuple(r for r in DS.INTEL_ROOTS if r != DS.STAMPS_ROOT)
    seats = sorted({d.name for r in roots if r.is_dir() for d in r.iterdir()
                    if d.is_dir() and not d.name.startswith((".", "_"))})
    out: dict[str, list[Path]] = {}
    for seat in seats:
        dirs = [r / seat for r in roots if (r / seat).is_dir()]
        if DS.snapshot_files(dirs, 0):
            continue
        files = [p for d in dirs for p in sorted(d.iterdir()) if p.is_file()
                 and p.name.endswith(_SUFFIXES) and p.stat().st_size > 2]
        if files:
            out[seat] = files
    return out


def _git_versions(path: Path) -> list[tuple[str, datetime]]:
    try:
        rel = str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        out = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%H %cI", "--", rel],
                             capture_output=True, text=True, timeout=120, check=False).stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    got: list[tuple[str, datetime]] = []
    for ln in out.splitlines():
        sha, _, when = ln.partition(" ")
        try:
            got.append((sha, datetime.fromisoformat(when.strip()).astimezone(UTC)))
        except ValueError:
            continue
    return sorted(got, key=lambda t: t[1])


def _git_blob(sha: str, path: Path) -> bytes | None:
    try:
        rel = str(path.resolve().relative_to(ROOT)).replace("\\", "/")
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{sha}:{rel}"],
                           capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _write_stamp(seat_dir: Path, when: datetime, f: Path, blob: bytes, basis: str) -> str:
    seat_dir.mkdir(parents=True, exist_ok=True)
    name = f"stamp_{when:%Y%m%d_%H%M%S}_{_slug(f.name)}.json"
    doc = [{"file": f.name, "records": records_in(blob, f.name), "bytes": len(blob),
            "basis": basis}]
    tmp = seat_dir / (name + ".tmp")
    tmp.write_text(json.dumps(doc), "utf-8")
    os.replace(tmp, seat_dir / name)
    return name


def run(now: datetime | None = None, *, stamps: Path | None = None,
        roots: tuple[Path, ...] | None = None, git: bool = True) -> dict[str, Any]:
    """Stamp every unstamped seat: its git versions (backfill, incremental) and its current
    content when this organ has not seen it. Returns the census of what was written."""
    now = now or datetime.now(UTC)
    base = stamps or STAMPS
    report: dict[str, Any] = {"generated_at": now.isoformat(timespec="seconds"), "seats": {}}
    for seat, files in unstamped_seats(roots).items():
        sd = base / seat
        led_p = sd / "_ledger.json"
        try:
            led = json.loads(led_p.read_text("utf-8"))
        except (OSError, ValueError):
            led = {}
        seen: dict[str, list[str]] = dict(led.get("seen") or {})
        wrote: list[str] = []
        for f in files:
            key = f.name
            have = set(seen.get(key) or [])
            if git:
                n = 0
                for sha, when in _git_versions(f):
                    if f"git:{sha}" in have or n >= BACKFILL_PER_PASS:
                        continue
                    blob = _git_blob(sha, f)
                    have.add(f"git:{sha}")
                    if blob is None:
                        continue
                    have.add(hashlib.sha256(blob).hexdigest())
                    wrote.append(_write_stamp(sd, when, f, blob,
                                              f"git commit {sha[:10]}: the desk held this "
                                              "version at or before its commit time"))
                    n += 1
            try:
                blob = f.read_bytes()
            except OSError:
                continue
            h = hashlib.sha256(blob).hexdigest()
            if h not in have:
                have.add(h)
                wrote.append(_write_stamp(sd, now, f, blob,
                                          "content first seen by seat_stamper at this time"))
            seen[key] = sorted(have)
        if wrote or not led_p.exists():
            sd.mkdir(parents=True, exist_ok=True)
            led_p.write_text(json.dumps({"seat": seat, "seen": seen,
                                         "rule": "versions already stamped; never rewritten"},
                                        indent=1), "utf-8")
        report["seats"][seat] = {"files": [f.name for f in files], "stamped_now": len(wrote)}
    report["n_seats"] = len(report["seats"])
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
