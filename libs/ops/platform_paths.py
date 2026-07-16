"""Cross-platform venv interpreter resolution.

The desk was authored on Windows (.venv/Scripts/python.exe) and migrated to a Linux VPS
(.venv/bin/python) 2026-07-12. Interpreter paths must resolve on BOTH so the same code runs
on the laptop and the server. ``windowless`` picks pythonw.exe on Windows (no console flash
for detached spawns); on POSIX there is no windowless variant, so it returns plain python.
"""

from __future__ import annotations

import os
from pathlib import Path


def venv_python(root: Path, *, windowless: bool = False) -> str:
    """Absolute path to this repo's venv interpreter for the current OS."""
    if os.name == "nt":
        exe = "pythonw.exe" if windowless else "python.exe"
        return str(root / ".venv" / "Scripts" / exe)
    return str(root / ".venv" / "bin" / "python")
