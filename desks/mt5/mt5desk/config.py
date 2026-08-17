"""Shared execution-surface config: terminal path + pause flag.

Terminal path: data/terminal_path.txt (one line, the terminal64.exe path)
overrides the VIG default - lets the desk switch brokers (Vantage -> Fusion)
with one file. Pause: data/GATEWAY_PAUSED exists -> gateway main() returns
without trading (used when the live surface is being moved).
"""

from __future__ import annotations

from pathlib import Path

BASE = Path(r"C:\Users\dell\mt5-research")
DEFAULT_TERMINAL = r"C:\Program Files\VIG Group MT5 Terminal\terminal64.exe"
TERMINAL_FILE = BASE / "data" / "terminal_path.txt"
PAUSE_FILE = BASE / "data" / "GATEWAY_PAUSED"


def terminal_path() -> str:
    if TERMINAL_FILE.exists():
        p = TERMINAL_FILE.read_text(encoding="utf-8").strip()
        if p:
            return p
    return DEFAULT_TERMINAL


def gateway_paused() -> bool:
    return PAUSE_FILE.exists()