"""Free space on a volume, read-only.

Its own module so `desk_self_heal` can measure disk headroom without naming `shutil` or `os`:
that organ's test enumerates the names it may never reference (so it can never delete, move or
arm anything), and a read-only stat is the one thing it needs from those modules.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def free_gb(root: Path | str) -> float:
    """Free gigabytes on the volume holding `root`. Raises OSError when it cannot be stat'ed."""
    return shutil.disk_usage(str(root)).free / (1024 ** 3)
