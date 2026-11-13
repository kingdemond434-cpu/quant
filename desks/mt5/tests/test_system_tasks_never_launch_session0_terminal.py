"""SYSTEM-run MT5 readers attach through mt5_session, never a bare initialize() (2026-11-13).

After the 2026-11-12 reboot a SYSTEM task's bare `mt5.initialize()` launched the Fusion terminal
headless in Session 0 with no login. MT5-TerminalBoot refused to launch beside it, so the Fusion
lane sat dark and E8's cross-account fence failed closed on every gold window.
"""
from __future__ import annotations

import re
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]

#: Files run by SYSTEM scheduled tasks (MT5-MoatRecorder, the spread tape) that once called
#: initialize() bare.
GUARDED = ("moat/moat_recorder.py", "research/fusion_spread_tape.py")

_BARE = re.compile(r"\bmt5\.initialize\(")


def test_system_readers_never_call_a_bare_initialize() -> None:
    for rel in GUARDED:
        src = (DESK / rel).read_text(encoding="utf-8")
        assert not _BARE.search(src), f"{rel} calls mt5.initialize() directly"
        assert "attach_or_initialize" in src, rel


def test_the_guard_refuses_session_zero() -> None:
    import sys

    sys.path.insert(0, str(DESK))
    from research import mt5_session

    class _NoTerminal:
        def terminal_info(self) -> None:
            return None

        def initialize(self, **_: object) -> bool:  # pragma: no cover - must never be reached
            raise AssertionError("a Session 0 caller launched a terminal")

    real = mt5_session.windows_session_id
    try:
        mt5_session.windows_session_id = lambda pid=None: 0  # type: ignore[assignment]
        assert mt5_session.attach_or_initialize(_NoTerminal()) is False
    finally:
        mt5_session.windows_session_id = real  # type: ignore[assignment]
