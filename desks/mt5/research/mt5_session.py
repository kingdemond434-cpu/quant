"""Keep research workers from launching a competing MT5 terminal in Session 0."""
from __future__ import annotations

import contextlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: WHICH TERMINAL IS THE DESK ACTUALLY TALKING TO.  Nothing on the box answered that question
#: before 2026-11-12, and the whole day's outage turned on it: two terminals were up (Fusion in
#: Session 0, FTMO in Session 1), the pinned Fusion path answered `(-10005, 'IPC timeout')`, and
#: MT5's bridge serves whichever terminal owns the machine's IPC pipe -- so an organ that asked
#: for Fusion could be reading FTMO and no artifact would say so.  Every successful attach stamps
#: this file with what was ASKED FOR and what ANSWERED, so a venue substitution is measurable
#: instead of a guess.  Best-effort: a failed write never costs an attach.
ATTACH_IDENTITY = (Path(__file__).resolve().parents[1] / "data" / "mt5_attach_identity.json")


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


def terminal_pids(path: str | None = None) -> set[int]:
    """PIDs of every running ``terminal64.exe``, narrowed to ``path`` when one is given.

    A process whose executable this account cannot read is COUNTED (with no path filter): the
    safe reading of "I cannot tell what that terminal is" is that a terminal exists, which is
    the answer that refuses a launch.  ``competing_terminal`` leaves such a process out on
    purpose -- it is asking a different question, whose safe answer is the opposite one.
    """
    if os.name != "nt":
        return set()
    import psutil

    pids: set[int] = set()
    for process in psutil.process_iter(attrs=["name", "exe"]):
        if str(process.info.get("name") or "").lower() != "terminal64.exe":
            continue
        executable = process.info.get("exe")
        if path and (not executable
                     or os.path.normcase(executable) != os.path.normcase(os.path.normpath(path))):
            continue
        pids.add(process.pid)
    return pids


def record_attach_identity(mt5: Any, requested: str | None, *, substituted: bool) -> None:
    """Stamp ``ATTACH_IDENTITY`` with the terminal that answered.  Never raises.

    The login is never written: this is the same rule the account publisher follows, and the
    repository is public.  ``company``/``server`` are what identify the venue.
    """
    temporary = ATTACH_IDENTITY.with_suffix(f".json.tmp{os.getpid()}")
    try:
        info = mt5.terminal_info()
        account = mt5.account_info()
        record = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "requested_path": requested,
            "attached_path": getattr(info, "path", None),
            "company": str(getattr(account, "company", "") or "") or None,
            "server": str(getattr(account, "server", "") or "") or None,
            "connected": getattr(info, "connected", None),
            "trade_allowed": getattr(info, "trade_allowed", None),
            "windows_session": windows_session_id(),
            "pid": os.getpid(),
            "path_substituted": substituted,
        }
        ATTACH_IDENTITY.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(record, indent=1), encoding="utf-8")
        temporary.replace(ATTACH_IDENTITY)
    except Exception:
        with contextlib.suppress(Exception):
            temporary.unlink()


def attach_running(
    mt5: Any,
    *,
    path: str | None = None,
    timeout: int | None = None,
) -> bool:
    """Attach to a terminal that is ALREADY RUNNING, in any session, and never spawn one.

    WHY THIS EXISTS, MEASURED 2026-11-12.  ``ops/ensure_terminal.ps1`` is the only organ allowed
    to launch the Fusion terminal and it only ever launches one into the interactive session.  At
    11:24Z something else brought the Fusion terminal up in Session 0 instead, and
    ``attach_or_initialize`` then refused EVERY attach for the rest of the day: from Session 0 by
    its ``session == 0`` arm, and from the interactive session by ``competing_terminal``, which
    sees a terminal at the pinned path in a session it cannot reconcile.  The cost was not a
    research input:

      * ``prop/e8_gold.py`` -- 82 consecutive ``MT5_UNAVAILABLE`` passes, last good pass
        2026-11-11T19:01:44Z, so ``prop/ftmo_follower.py`` skipped every pass of the live
        99,588 USD prop account with "E8's last pass is 'MT5_UNAVAILABLE', not OK";
      * ``ops/publish_account_state.py`` -- 53 refusals, ``data/account_state.json`` 23h stale;
      * ``research/shadow_cycle.py`` (MT5-Shadow rc=1), ``research/h1_source.py``,
        ``recorders/tick_source.py``, ``mt5desk/tape.py`` -- the forward lane and the
        own-observation moat, both blind.

    The refusal was a FALSE NEGATIVE the whole time: measured in the same sitting, a Session-0
    process called ``initialize()`` and attached to the authenticated terminal (connected,
    trade_allowed, equity answering) and the ``terminal64.exe`` census was byte-identical before
    and after -- nothing was spawned.

    So the guard's real protection is kept exactly: NEVER SPAWN.  Attaching to a terminal that is
    already up cannot take the listener from anything, because the thing holding the listener is
    what we attach to.  This function therefore refuses when no terminal is running at all (that
    case belongs to the launch path and its session guards), and audits the process census around
    ``initialize`` so a spawn is caught even if MT5 does one anyway.

    THE PINNED PATH IS A LAUNCH TARGET, NOT AN ADDRESS.  MT5's Python bridge talks to whichever
    terminal owns the machine's IPC pipe; ``path`` only decides what ``initialize`` would START.
    Measured the same sitting: ``initialize(path=<Fusion>)`` returned ``(-10005, 'IPC timeout')``
    while the pathless call attached and answered.  That is also the behaviour the desk ran on for
    12,915 e8 passes -- the lane pinned the Fusion path and read the prop account through it.  So
    a failed pinned attach falls back to the pathless one, and says so on stderr: a caller that
    needs a specific venue must check ``account_info().company``, never the path it asked for.
    """
    before = terminal_pids()
    if not before:
        return False
    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    attempts: list[dict[str, Any]] = []
    if path:
        attempts.append({**kwargs, "path": path})
    attempts.append(dict(kwargs))
    for n, attempt in enumerate(attempts):
        try:
            ok = bool(mt5.initialize(**attempt))
        except Exception:
            ok = False
        if terminal_pids() - before:
            # initialize spawned one after all: shut the handle and refuse, so this never becomes
            # the Session-0 terminal the guard exists to prevent.
            with contextlib.suppress(Exception):
                mt5.shutdown()
            print("mt5_session: initialize spawned a terminal; refusing the attach",
                  file=sys.stderr)
            return False
        if ok:
            if n and path:
                print(f"mt5_session: attached to the terminal holding the IPC pipe, not the "
                      f"pinned {path}; check account_info().company if the venue matters",
                      file=sys.stderr)
            record_attach_identity(mt5, path, substituted=bool(n and path))
            return True
        with contextlib.suppress(Exception):
            mt5.shutdown()
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

    An ATTACH to a terminal that is already running is not that situation and is tried first
    (``attach_running``, which audits the process census and never spawns).  The session and
    competing-terminal guards below now gate only the LAUNCH -- the one act they were written to
    prevent -- so a terminal in an unreconcilable session no longer blinds every organ on the
    box.  ``allow_autostart=False`` keeps meaning "never start one", which is what the attach
    does, so those callers get the attach too.
    """
    try:
        if mt5.terminal_info() is not None:
            return True
    except Exception:
        pass
    if attach_running(mt5, path=path, timeout=timeout):
        return True
    session = windows_session_id()
    if not allow_autostart or session == 0 or competing_terminal(session, path):
        return False
    kwargs: dict[str, Any] = {}
    if path:
        kwargs["path"] = path
    if timeout is not None:
        kwargs["timeout"] = timeout
    launched = bool(mt5.initialize(**kwargs))
    if launched:
        record_attach_identity(mt5, path, substituted=False)
    return launched
