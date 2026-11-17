"""Keep research workers from launching a competing MT5 terminal in Session 0."""
from __future__ import annotations

import os
from typing import Any


def windows_session_id(pid: int | None = None) -> int | None:
    """Return the current Windows session, or None off Windows/when unreadable."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        value = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.ProcessIdToSessionId(
            os.getpid() if pid is None else pid, ctypes.byref(value))
        return int(value.value) if ok else None
    except (AttributeError, OSError, ValueError):
        return None


def competing_terminal(session: int | None, path: str | None) -> bool:
    """Refuse a launch when the terminal's Windows session cannot be reconciled."""
    if os.name != "nt":
        return False
    if session is None:
        return True
    import psutil

    for process in psutil.process_iter(attrs=["name", "exe"]):
        if str(process.info.get("name") or "").lower() != "terminal64.exe":
            continue
        executable = process.info.get("exe")
        if path and executable and os.path.normcase(executable) != os.path.normcase(path):
            continue
        if windows_session_id(process.pid) != session:
            return True
    return False


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
    session = windows_session_id()
    if not allow_autostart or session == 0 or competing_terminal(session, path):
        return False
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if timeout is not None:
        kwargs["timeout"] = timeout
    return bool(mt5.initialize(**kwargs))


#: The desk's execution account is Fusion. A tape recorded off FTMO, E8 or a demo is the wrong
#: broker's quotes filed under Fusion symbols -- spreads, hours and price feed all differ.
EXPECTED_SERVER_PREFIX = "FusionMarkets-"


def same_terminal(configured: str, attached_dir: str | None) -> bool:
    """`terminal_info().path` is the terminal's DIRECTORY; terminal_path.txt names its exe."""
    if not attached_dir:
        return False

    def norm(x: str) -> str:
        return x.replace("/", "\\").rstrip("\\").lower()
    conf = norm(configured)
    if conf.endswith("\\terminal64.exe"):
        conf = conf[: -len("\\terminal64.exe")]
    return conf == norm(attached_dir)


def venue_refusal(mt5: Any, path: str | None,
                  expected_prefix: str = EXPECTED_SERVER_PREFIX) -> str | None:
    """Why the terminal this process is attached to is NOT the desk's, or None when it is.

    THE COIN FLIP (2026-11-11, Desk health). The box runs two logged-in terminals in one
    session, Fusion and FTMO, and an attach without a path takes whichever the bridge sees
    first, so restart order decided which broker an organ read. Attaching by path is the pin;
    this is the proof: the attached account's server must be Fusion's and, when a path is
    configured, the attached terminal must be that one. An unreadable answer is a refusal.

    THE REASON IS PUBLISHED (2026-11-14, Auditor MF1 on #982): it reaches report fields, the
    spread tape's `why` and leg tails in a public repository, so it is a fixed phrase. It never
    carries the attached server name or either terminal path -- only the expected prefix, which
    is the desk's own constant.
    """
    try:
        info = mt5.account_info()
    except Exception as exc:
        return f"account_info() raised {type(exc).__name__}"
    server = str(getattr(info, "server", "") or "") if info is not None else ""
    if not server.startswith(expected_prefix):
        return (f"attached server is not {expected_prefix}*" if server
                else "attached terminal reports no server")
    if path:
        try:
            tinfo = mt5.terminal_info()
        except Exception as exc:
            return f"terminal_info() raised {type(exc).__name__}"
        attached = str(getattr(tinfo, "path", "") or "") if tinfo is not None else ""
        if not same_terminal(path, attached):
            return ("attached terminal is not the configured one" if attached
                    else "attached terminal reports no path")
    return None
