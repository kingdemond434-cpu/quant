"""Atomic miner discovery output through the canonical provenance door.

ONE BAD ROW NEVER COSTS THE BATCH (2026-10-06). `write_discoveries` used to raise on the first
malformed or unstampable row, so a single row without provenance threw away every good row the
miner produced that pass -- research generation cut by the door that was meant to admit it. Now
the bad row alone is QUARANTINED: appended to `QUARANTINE` (one JSON line per row, carrying the
destination, the reason and the row as it arrived) and counted on the return value, and every
good row is written. The provenance law is unchanged: no unstamped row ever reaches the artifact.

The quarantine lives OUTSIDE `data/intelligence/`, deliberately: the compiler reads
`data/intelligence/*/*.jsonl`, and a quarantine file there would be ingested as discoveries.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.pit import stamp_or_refuse  # noqa: E402

#: Every row the door refused, one JSON object per line, with its reason. Append-only.
QUARANTINE = ROOT / "desks" / "mt5" / "data" / "quarantine" / "discoveries.jsonl"
#: ONE RECEIPT PER WRITE, whether or not anything was quarantined: the producer (its seat, the
#: discovery file's directory), the artifact written, and how many rows were written and
#: quarantined. Written by the one door every miner calls, so every miner reports -- including
#: one added tomorrow -- and a zero is a MEASURED zero rather than an absence (L1.28a).
#: `research/producer_breadth.py` publishes the per-producer totals from it.
#: Both files live under `desks/mt5/data/`, which `libs/ops/release.STATE_PREFIXES` already
#: classifies as box state: they are the box's own record and cannot be regenerated.
RECEIPTS = ROOT / "desks" / "mt5" / "data" / "quarantine" / "write_receipts.jsonl"


#: BOUNDED, WITH EXACT RUNNING TOTALS (audit of #222). Both files are append-only and written by
#: every miner every pass. When the live file passes MAX_SEGMENT_BYTES it is renamed to `<name>.1`
#: (the previous `.1` is first FOLDED into `<name>.totals.json` -- per-producer counts -- and then
#: deleted). So disk holds at most two segments, the last 7 days stay readable line by line, and
#: totals.json + `.1` + the live file is the exact all-time count. The fold is idempotent: the
#: totals record the folded segment's digest, so a pass that died between the fold and the
#: delete does not count the segment twice.
MAX_SEGMENT_BYTES = 8 * 1024 * 1024


def _tally_receipts(lines: list[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        slot = out.setdefault(str(r.get("producer") or "?").lower(),
                              {"writes": 0, "written": 0, "quarantined": 0})
        slot["writes"] += 1
        slot["written"] += int(r.get("written") or 0)
        slot["quarantined"] += int(r.get("quarantined") or 0)
    return out


def _tally_quarantine(lines: list[str]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        producer = Path(str(r.get("destination") or "?")).parent.name.lower() or "?"
        out.setdefault(producer, {"quarantined": 0})["quarantined"] += 1
    return out


def totals_path(path: Path) -> Path:
    return path.with_name(path.name + ".totals.json")


def _fold(segment: Path, tally: Any) -> None:
    import hashlib

    blob = segment.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    tpath = totals_path(segment.with_name(segment.name[: -len(".1")]))
    try:
        doc = json.loads(tpath.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    if doc.get("last_folded_sha256") == digest:
        return                                   # already counted by a pass that died after
    lines = blob.decode("utf-8", "replace").splitlines()
    by = doc.setdefault("by_producer", {})
    for producer, counts in tally(lines).items():
        slot = by.setdefault(producer, {})
        for k, v in counts.items():
            slot[k] = int(slot.get(k, 0)) + int(v)
    doc["folded_lines"] = int(doc.get("folded_lines", 0)) + len(lines)
    doc["folded_segments"] = int(doc.get("folded_segments", 0)) + 1
    doc["last_folded_sha256"] = digest
    doc["at"] = datetime.now(UTC).isoformat(timespec="seconds")
    fd, tmp = tempfile.mkstemp(prefix=f".{tpath.name}.", suffix=".tmp", dir=tpath.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=1)
    os.replace(tmp, tpath)


def _rotate(path: Path, tally: Any, max_bytes: int | None = None) -> None:
    """Rotate `path` once it passes the cap. Never raises: a rotation never costs a write."""
    cap = MAX_SEGMENT_BYTES if max_bytes is None else max_bytes
    try:
        if path.stat().st_size < cap:
            return
    except OSError:
        return
    lock = path.with_name(path.name + ".rotate.lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if datetime.now(UTC).timestamp() - lock.stat().st_mtime > 600:
                lock.unlink(missing_ok=True)      # a rotator that died; the next pass rotates
        except OSError:
            pass
        return
    except OSError:
        return
    try:
        old = path.with_name(path.name + ".1")
        if old.exists():
            _fold(old, tally)
            old.unlink()
        os.replace(path, old)
    except OSError:
        pass                                      # e.g. another process holds it open (Windows)
    finally:
        os.close(fd)
        lock.unlink(missing_ok=True)


class WrittenDiscoveries(list[dict[str, Any]]):
    """The stamped rows that were written (a list, so every caller keeps working), plus the
    count and location of the rows quarantined on the way."""

    quarantined: int = 0
    quarantine_path: Path | None = None


def _quarantine(path: Path, bad: list[dict[str, Any]], qpath: Path) -> None:
    if not bad:
        return
    qpath.parent.mkdir(parents=True, exist_ok=True)
    at = datetime.now(UTC).isoformat(timespec="seconds")
    with qpath.open("a", encoding="utf-8") as handle:
        for entry in bad:
            handle.write(json.dumps({"at": at, "destination": str(path), **entry},
                                    default=str, ensure_ascii=False) + "\n")
    _rotate(qpath, _tally_quarantine)


def _receipt(path: Path, written: int, quarantined: int, rpath: Path) -> None:
    try:
        rpath.parent.mkdir(parents=True, exist_ok=True)
        with rpath.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "at": datetime.now(UTC).isoformat(timespec="seconds"),
                "producer": path.parent.name, "artifact": path.name,
                "written": int(written), "quarantined": int(quarantined)}) + "\n")
        _rotate(rpath, _tally_receipts)
    except OSError:
        pass                                   # a receipt never costs the discoveries


def write_discoveries(path: Path, rows: list[dict[str, Any]],
                      quarantine: Path | None = None,
                      receipts: Path | None = None) -> WrittenDiscoveries:
    """Write every good row atomically; quarantine (never raise on) each bad one.

    A batch that is not a list at all is still refused whole -- there is no row to keep."""
    if not isinstance(rows, list):
        raise ValueError(f"{path}: discovery batch must be a list of objects")
    env_dir = os.environ.get("QUANT_DISCOVERY_QUARANTINE_DIR")
    if quarantine is None and env_dir:
        # Test isolation (desks/mt5/tests/conftest.py) and any off-box dry run.
        quarantine = Path(env_dir) / QUARANTINE.name
    qpath = quarantine if quarantine is not None else QUARANTINE
    bad: list[dict[str, Any]] = []
    stamped: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            bad.append({"index": i, "why": f"not an object: {type(row).__name__}",
                        "row": repr(row)[:2000]})
            continue
        # Row by row through the ONE door, so a refusal is attributable to the row it names.
        ok, refused = stamp_or_refuse([row], path.parent.name)
        if refused:
            bad.append({"index": i, "why": f"missing provenance: {refused[0].get('why')}",
                        "row": row})
            continue
        stamped.extend(ok)
    _quarantine(path, bad, qpath)
    out = WrittenDiscoveries(stamped)
    out.quarantined = len(bad)
    out.quarantine_path = qpath if bad else None
    _receipt(path, len(stamped), len(bad), receipts if receipts is not None
             else (qpath.parent / RECEIPTS.name if quarantine is not None else RECEIPTS))
    if bad and not stamped and path.exists():
        # Nothing good to write: an empty list must not replace what an earlier pass wrote.
        return out
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            json.dump(stamped, handle, indent=1, default=str, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return out
