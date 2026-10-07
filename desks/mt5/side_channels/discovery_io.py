"""Atomic miner discovery output through the canonical provenance door."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.data.pit import stamp_or_refuse  # noqa: E402
from libs.ops.secret_scrub import scrub  # noqa: E402


def write_discoveries(path: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Refuse malformed batches before replacing an existing discovery artifact."""
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: discovery batch must be a list of objects")
    # Scraped text and LLM answers carry other people's keys: scrub before the provenance stamp,
    # so the stamp's content hash describes exactly what is written (libs/ops/secret_scrub.py).
    stamped, refused = stamp_or_refuse(scrub(rows), path.parent.name)
    if refused:
        raise ValueError(f"{path}: {len(refused)} discovery rows refused for missing provenance")
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
    return stamped
