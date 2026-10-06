"""Publish complete bar files without exposing a truncated footer to readers."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any


def atomic_parquet(frame: Any, destination: Path, **kwargs: Any) -> None:
    """Keep the previous generation until serialization and fsync both succeed.

    The unique sibling also isolates concurrent publishers. Permission failures propagate;
    publication never falls back to overwriting the live file in place.
    """
    destination = Path(destination)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.publishing")
    try:
        frame.to_parquet(temporary, **kwargs)
        with temporary.open("r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
