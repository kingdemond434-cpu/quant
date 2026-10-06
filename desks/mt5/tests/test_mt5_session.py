from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import mt5_session


class FakeMT5:
    def __init__(self) -> None:
        self.initialize_calls: list[dict] = []

    def terminal_info(self):
        return None

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)
        return True


def test_session_zero_cannot_launch_terminal(monkeypatch) -> None:
    fake = FakeMT5()
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 0)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe") is False
    assert fake.initialize_calls == []


def test_interactive_session_can_launch_terminal(monkeypatch) -> None:
    fake = FakeMT5()
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: False)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe", timeout=15000) is True
    assert fake.initialize_calls == [{"path": "terminal64.exe", "timeout": 15000}]


def test_interactive_worker_cannot_launch_against_wrong_session_terminal(monkeypatch):
    fake = FakeMT5()
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: True)
    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe") is False
    assert fake.initialize_calls == []


def test_competing_terminal_detects_foreign_session(monkeypatch):
    from types import SimpleNamespace

    import psutil

    monkeypatch.setattr(mt5_session.os, "name", "nt")
    monkeypatch.setattr(psutil, "process_iter", lambda **kwargs: [
        SimpleNamespace(pid=123, info={"name": "terminal64.exe", "exe": "fusion.exe"})])
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda pid=None: 0)
    assert mt5_session.competing_terminal(2, "fusion.exe") is True
    assert mt5_session.competing_terminal(2, "other_broker.exe") is False
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda pid=None: 2)
    assert mt5_session.competing_terminal(2, "fusion.exe") is False


def test_tick_source_cannot_autostart_terminal_in_session_zero(monkeypatch):
    from recorders.tick_source import Mt5TickSource

    from research import mt5_session as session

    fake = FakeMT5()
    source = Mt5TickSource("terminal64.exe")
    monkeypatch.setattr(source, "_mt5", lambda: fake)
    monkeypatch.setattr(session, "windows_session_id", lambda: 0)
    assert source.initialize() is False
    assert source.alive() is False
    assert fake.initialize_calls == []
