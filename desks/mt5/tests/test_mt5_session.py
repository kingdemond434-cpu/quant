from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import mt5_session


class FakeMT5:
    def __init__(self, ok: bool = True) -> None:
        self.initialize_calls: list[dict] = []
        self.shutdowns = 0
        self.ok = ok

    def terminal_info(self):
        return None

    def initialize(self, **kwargs):
        self.initialize_calls.append(kwargs)
        return self.ok

    def shutdown(self) -> None:
        self.shutdowns += 1


def _no_terminal_running(monkeypatch) -> None:
    """Nothing to attach to, so every decision below is about a LAUNCH."""
    monkeypatch.setattr(mt5_session, "terminal_pids", lambda path=None: set())


def _terminal_already_running(monkeypatch, *, spawns: bool = False) -> None:
    """One terminal is up.  ``spawns`` makes the census grow across ``initialize``."""
    census = {"pids": {4242}}

    def pids(path: str | None = None) -> set[int]:
        current = set(census["pids"])
        if spawns:
            census["pids"] = census["pids"] | {9999}
        return current

    monkeypatch.setattr(mt5_session, "terminal_pids", pids)


# ---------------------------------------------------------------- the launch guards stand

def test_session_zero_cannot_launch_terminal(monkeypatch) -> None:
    """THE LAW THIS MODULE EXISTS FOR: Session 0 never STARTS a terminal.

    An unauthenticated Session-0 terminal can take the machine-global listener from the
    authenticated execution terminal, so with nothing already running there is nothing to
    attach to and the answer is "unavailable", never a launch.
    """
    fake = FakeMT5()
    _no_terminal_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 0)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe") is False
    assert fake.initialize_calls == []


def test_interactive_worker_cannot_launch_against_wrong_session_terminal(monkeypatch):
    fake = FakeMT5()
    _no_terminal_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: True)
    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe") is False
    assert fake.initialize_calls == []


def test_interactive_session_can_launch_terminal(monkeypatch) -> None:
    fake = FakeMT5()
    _no_terminal_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: False)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe", timeout=15000) is True
    assert fake.initialize_calls == [{"timeout": 15000, "path": "terminal64.exe"}]


def test_autostart_refused_still_never_launches(monkeypatch) -> None:
    fake = FakeMT5()
    _no_terminal_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: False)
    assert mt5_session.attach_or_initialize(fake, path="t.exe", allow_autostart=False) is False
    assert fake.initialize_calls == []


# ------------------------------------------------- attaching to a terminal that is already up

def test_session_zero_may_attach_to_a_running_terminal(monkeypatch) -> None:
    """THE 2026-11-12 REGRESSION.  A terminal in an unreconcilable session blinded every organ.

    The Fusion terminal came up in Session 0 at 11:24Z and ``attach_or_initialize`` then refused
    every attach for the rest of the day -- 82 ``MT5_UNAVAILABLE`` e8 passes, so the live prop
    account placed nothing, plus a 23h-stale account_state and a dead shadow lane.  Attaching to
    a terminal that is ALREADY RUNNING takes the listener from nothing, so it is allowed.
    """
    fake = FakeMT5()
    _terminal_already_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 0)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe", timeout=15000) is True
    assert fake.initialize_calls == [{"timeout": 15000, "path": "terminal64.exe"}]


def test_attach_survives_a_wrong_session_terminal_in_the_interactive_lane(monkeypatch) -> None:
    fake = FakeMT5()
    _terminal_already_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 2)
    monkeypatch.setattr(mt5_session, "competing_terminal", lambda session, path: True)

    assert mt5_session.attach_or_initialize(fake, path="terminal64.exe") is True


def test_pinned_path_falls_back_to_the_pipe_holder(monkeypatch) -> None:
    """``path`` is a launch target, not an address: MT5 answers from whichever terminal owns the
    machine's IPC pipe.  Measured 2026-11-12: ``initialize(path=<Fusion>)`` gave
    ``(-10005, 'IPC timeout')`` while the pathless call attached and answered."""

    class PinnedFails(FakeMT5):
        def initialize(self, **kwargs):
            self.initialize_calls.append(kwargs)
            return "path" not in kwargs

    fake = PinnedFails()
    _terminal_already_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 0)

    assert mt5_session.attach_running(fake, path="pinned.exe", timeout=15000) is True
    assert fake.initialize_calls == [{"timeout": 15000, "path": "pinned.exe"},
                                     {"timeout": 15000}]


def test_an_attach_that_spawns_a_terminal_is_refused(monkeypatch) -> None:
    """NEVER SPAWN is audited, not assumed: if the census grows across ``initialize`` the handle
    is shut and the attach refused, whatever MT5 returned."""
    fake = FakeMT5()
    _terminal_already_running(monkeypatch, spawns=True)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda: 0)

    assert mt5_session.attach_running(fake, path="terminal64.exe") is False
    assert fake.shutdowns == 1


def test_every_attach_stamps_which_terminal_answered(tmp_path, monkeypatch) -> None:
    """THE DETECTOR THIS INCIDENT NEEDED. Two terminals were up, the pinned path timed out, and
    MT5 answers from whichever one owns the IPC pipe -- so an organ asking for Fusion could be
    reading FTMO with no artifact saying so. Every successful attach now stamps what was asked
    for against what answered, and never the login."""
    import json as _json
    import types

    class Identified(FakeMT5):
        def initialize(self, **kwargs):
            self.initialize_calls.append(kwargs)
            return "path" not in kwargs

        def terminal_info(self):
            return types.SimpleNamespace(path=r"C:\FTMO", connected=True, trade_allowed=True)

        def account_info(self):
            return types.SimpleNamespace(company="FTMO Global Markets Ltd",
                                         server="FTMO-Server2", login=5551234)

    out = tmp_path / "mt5_attach_identity.json"
    monkeypatch.setattr(mt5_session, "ATTACH_IDENTITY", out)
    _terminal_already_running(monkeypatch)
    monkeypatch.setattr(mt5_session, "windows_session_id", lambda pid=None: 0)

    fake = Identified()
    # terminal_info() answers here, so go through attach_running directly: attach_or_initialize's
    # fast path would short-circuit on it.
    assert mt5_session.attach_running(fake, path=r"C:\Fusion\terminal64.exe") is True
    rec = _json.loads(out.read_text(encoding="utf-8"))
    assert rec["requested_path"] == r"C:\Fusion\terminal64.exe"
    assert rec["attached_path"] == r"C:\FTMO"
    assert rec["company"] == "FTMO Global Markets Ltd"
    assert rec["path_substituted"] is True
    assert "5551234" not in out.read_text(encoding="utf-8")
    assert list(tmp_path.iterdir()) == [out]


def test_identity_stamp_never_breaks_an_attach(tmp_path, monkeypatch) -> None:
    """Best-effort: an unwritable artifact path must not cost the desk its terminal."""
    monkeypatch.setattr(mt5_session, "ATTACH_IDENTITY",
                        tmp_path / "no" / "such" / "dir" / "x" / "id.json")
    monkeypatch.setattr(mt5_session.Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    _terminal_already_running(monkeypatch)
    fake = FakeMT5()
    assert mt5_session.attach_running(fake, path="terminal64.exe") is True


def test_attach_running_refuses_when_nothing_is_running(monkeypatch) -> None:
    fake = FakeMT5()
    _no_terminal_running(monkeypatch)
    assert mt5_session.attach_running(fake, path="terminal64.exe") is False
    assert fake.initialize_calls == []


# ---------------------------------------------------------------------------- the census itself

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


def test_terminal_pids_counts_an_unreadable_terminal(monkeypatch):
    """The safe answer to "I cannot read that terminal's path" is that a terminal EXISTS: it
    refuses a launch.  ``competing_terminal`` leaves it out because its safe answer is the
    opposite one."""
    from types import SimpleNamespace

    import psutil

    monkeypatch.setattr(mt5_session.os, "name", "nt")
    monkeypatch.setattr(psutil, "process_iter", lambda **kwargs: [
        SimpleNamespace(pid=7, info={"name": "terminal64.exe", "exe": None}),
        SimpleNamespace(pid=8, info={"name": "terminal64.exe", "exe": r"C:\a\terminal64.exe"}),
        SimpleNamespace(pid=9, info={"name": "chrome.exe", "exe": r"C:\c\chrome.exe"})])
    assert mt5_session.terminal_pids() == {7, 8}
    assert mt5_session.terminal_pids(r"C:\a\terminal64.exe") == {8}
    assert mt5_session.terminal_pids(r"C:\b\terminal64.exe") == set()


# -------------------------------------------------------- the two callers that pin the old law

def test_tick_source_cannot_autostart_terminal_in_session_zero(monkeypatch):
    from recorders.tick_source import Mt5TickSource

    from research import mt5_session as session

    fake = FakeMT5()
    source = Mt5TickSource("terminal64.exe")
    monkeypatch.setattr(source, "_mt5", lambda: fake)
    monkeypatch.setattr(session, "terminal_pids", lambda path=None: set())
    monkeypatch.setattr(session, "windows_session_id", lambda: 0)
    assert source.initialize() is False
    assert source.alive() is False
    assert fake.initialize_calls == []


def test_hourly_tape_cannot_spawn_session_zero_terminal(monkeypatch):
    from mt5desk import tape

    from research import mt5_session as session

    fake = FakeMT5()
    fake.last_error = lambda: (-10003, "unavailable")
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    monkeypatch.setattr(session, "terminal_pids", lambda path=None: set())
    monkeypatch.setattr(session, "windows_session_id", lambda: 0)
    assert tape.main([]) == 1
    assert fake.initialize_calls == []
