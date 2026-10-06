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


def write_discoveries(path: Path, rows: list[dict[str, Any]],
                      quarantine: Path | None = None) -> WrittenDiscoveries:
    """Write every good row atomically; quarantine (never raise on) each bad one.

    A batch that is not a list at all is still refused whole -- there is no row to keep."""
    if not isinstance(rows, list):
        raise ValueError(f"{path}: discovery batch must be a list of objects")
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
