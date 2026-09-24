"""Keep research workers from launching a competing MT5 terminal in Session 0."""
from __future__ import annotations

import os
from typing import Any


def windows_session_id() -> int | None:
    """Return the current Windows session, or None off Windows/when unreadable."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        value = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(value))
        return int(value.value) if ok else None
    except (AttributeError, OSError, ValueError):
        return None


def attach_or_initialize(
    mt5: Any,
    *,
    path: str | None = None,
    timeout: int | None = None,
    allow_autostart: bool = True,
) -> bool:
    """Attach to MT5 without ever spawning it from Windows Session 0.

    MT5's Python bridge is session-local while its MCP listener is machine-global.  A SYSTEM
    research worker that calls ``initialize`` therefore launches an unauthenticated Session-0
    terminal which can take the listener from the authenticated execution terminal.  Research
    must report its input as unavailable in that situation, never disable execution.
    """
    try:
        if mt5.terminal_info() is not None:
            return True
    except Exception:
        pass
    if not allow_autostart or windows_session_id() == 0:
        return False
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if timeout is not None:
        kwargs["timeout"] = timeout
    return bool(mt5.initialize(**kwargs))
