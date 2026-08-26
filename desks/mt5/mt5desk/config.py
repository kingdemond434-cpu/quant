"""Shared execution-surface config: terminal path + pause flag.

Terminal path: data/terminal_path.txt (one line, the terminal64.exe path)
overrides the VIG default - lets the desk switch brokers (Vantage -> Fusion)
with one file. Pause: data/GATEWAY_PAUSED exists -> gateway main() returns
without trading (used when the live surface is being moved).
"""

from __future__ import annotations

import os
from pathlib import Path

#: Legacy absolute root. Kept ONLY as the last fallback so an existing box that runs the desk
#: from outside its own tree keeps working unchanged.
_LEGACY_BASE = Path(r"C:\Users\dell\mt5-research")


def desk_root() -> Path:
    """The desk's own directory. THE SINGLE SOURCE OF TRUTH FOR EVERY PATH ON THIS DESK.

    Twenty-one files hardcoded `C:\\Users\\dell\\...` across thirty lines, which meant the desk
    could only ever run on one machine under one username. That is not a portability nicety: the
    execution surface has to survive the laptop being closed, and a hosted box cannot reproduce a
    developer's home directory. It also made the research half unrunnable anywhere else, so the
    Linux VPS could never share the load.

    Resolution order, most explicit first:
      1. ``MT5_DESK_ROOT`` -- an operator override, for running against a copy of the tree.
      2. This file's own location (``desks/mt5``), which is correct by construction wherever the
         repo is checked out, on any OS, with no configuration at all.
      3. The legacy Windows path, if it still exists on this machine.

    Deliberately a FUNCTION and not a module constant computed at import: the override has to be
    settable by a caller that imports this module, and a constant frozen at first import cannot
    be. ``BASE`` below stays as a constant for the existing call sites, evaluated once here.
    """
    env = os.environ.get("MT5_DESK_ROOT", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve().parents[1]
    if (here / "mt5desk").is_dir():
        return here
    return _LEGACY_BASE


BASE = desk_root()
DATA = BASE / "data"
REPORTS = BASE / "reports"
LOGS = BASE / "logs"

DEFAULT_TERMINAL = r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"
TERMINAL_FILE = DATA / "terminal_path.txt"
PAUSE_FILE = DATA / "GATEWAY_PAUSED"


def terminal_path() -> str:
    if TERMINAL_FILE.exists():
        p = TERMINAL_FILE.read_text(encoding="utf-8").strip()
        if p:
            return p
    return DEFAULT_TERMINAL


def gateway_paused() -> bool:
    return PAUSE_FILE.exists()