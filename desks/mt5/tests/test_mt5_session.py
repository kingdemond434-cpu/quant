from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import mt5_session  # noqa: E402


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

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe", timeout=15000) is True
    assert fake.initialize_calls == [{"path": "terminal64.exe", "timeout": 15000}]
