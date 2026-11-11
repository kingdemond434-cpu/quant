"""Both tick recorders attach to the desk's terminal BY PATH and refuse any other account.

THE COIN FLIP (2026-11-11, Desk health). The box runs Fusion and FTMO logged in side by side in
one Windows session. `moat_recorder` called `mt5.initialize()` with no path, so restart order
decided which broker's quotes it filed under Fusion symbols; `tick_recorder` passed the path but
never checked what it got. The tape is the desk's moat only if it is Fusion's.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.mt5_session import same_terminal, venue_refusal  # noqa: E402

FUSION_EXE = r"C:\Program Files\Fusion Markets MT5\terminal64.exe"
FUSION_DIR = r"C:\Program Files\Fusion Markets MT5"
FTMO_DIR = r"C:\Program Files\FTMO MT5"


class _Bridge:
    """A stand-in MetaTrader5 module: one attached terminal, its account, and what was asked."""

    def __init__(self, server: str = "FusionMarkets-Live", path: str = FUSION_DIR) -> None:
        self.server, self.path = server, path
        self.attached = False
        self.init_kwargs: list[dict] = []
        self.shutdowns = 0

    def initialize(self, **kw: object) -> bool:
        self.init_kwargs.append(kw)
        self.attached = True
        return True

    def terminal_info(self) -> SimpleNamespace | None:
        return SimpleNamespace(path=self.path, connected=True) if self.attached else None

    def account_info(self) -> SimpleNamespace | None:
        return SimpleNamespace(server=self.server) if self.attached else None

    def shutdown(self) -> None:
        self.shutdowns += 1
        self.attached = False

    def last_error(self) -> tuple[int, str]:
        return (0, "ok")

    def module(self) -> types.ModuleType:
        mod = types.ModuleType("MetaTrader5")
        for name in ("initialize", "terminal_info", "account_info", "shutdown", "last_error"):
            setattr(mod, name, getattr(self, name))
        return mod


def test_the_terminal_directory_matches_the_configured_executable() -> None:
    assert same_terminal(FUSION_EXE, FUSION_DIR)
    assert same_terminal(FUSION_EXE.replace("\\", "/"), FUSION_DIR.lower() + "\\")
    assert not same_terminal(FUSION_EXE, FTMO_DIR)
    assert not same_terminal(FUSION_EXE, None)


def test_only_the_fusion_account_on_the_configured_terminal_is_accepted() -> None:
    b = _Bridge()
    b.attached = True
    assert venue_refusal(b, FUSION_EXE) is None
    b.server = "FTMO-Server3"
    assert "FTMO-Server3" in str(venue_refusal(b, FUSION_EXE))
    b.server, b.path = "FusionMarkets-Live", FTMO_DIR
    assert "is not the configured" in str(venue_refusal(b, FUSION_EXE))
    assert venue_refusal(b, None) is None            # no path configured: the server still binds
    b.attached = False
    assert "(none)" in str(venue_refusal(b, FUSION_EXE))


def test_a_bridge_that_raises_is_a_refusal_not_an_acceptance() -> None:
    class Broken:
        def account_info(self) -> None:
            raise RuntimeError("IPC timeout")
    assert "raised RuntimeError" in str(venue_refusal(Broken(), FUSION_EXE))


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> _Bridge:
    b = _Bridge()
    monkeypatch.setitem(sys.modules, "MetaTrader5", b.module())
    return b


def test_the_tick_source_attaches_by_path_and_refuses_ftmo(bridge: _Bridge) -> None:
    from recorders.tick_source import Mt5TickSource
    src = Mt5TickSource(FUSION_EXE)
    assert src.initialize() is True and src.refusal is None
    assert bridge.init_kwargs[0]["path"] == FUSION_EXE

    bridge.server = "FTMO-Server3"                   # the terminal is logged into FTMO mid-run
    assert src.alive() is False                      # the cycle files SOURCE_UNAVAILABLE
    assert "FTMO-Server3" in str(src.refusal) and bridge.shutdowns == 1

    bridge.server = "FusionMarkets-Live"             # back on Fusion: the next cycle recovers
    assert src.alive() is True and src.refusal is None


def test_the_tick_source_refuses_a_bridge_already_attached_elsewhere(bridge: _Bridge) -> None:
    from recorders.tick_source import Mt5TickSource
    bridge.attached, bridge.path = True, FTMO_DIR    # the bridge already holds the other terminal
    src = Mt5TickSource(FUSION_EXE)
    assert src.initialize() is False
    assert "is not the configured" in str(src.refusal)


def _moat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bridge: _Bridge) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        "moat_recorder_venue_test", _DESK / "moat" / "moat_recorder.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "terminal_path.txt").write_text(FUSION_EXE + "\n", "utf-8")
    for name, val in (("TERMINAL_FILE", tmp_path / "terminal_path.txt"),
                      ("LOCK", tmp_path / "recorder.lock"), ("BRONZE", tmp_path / "bronze"),
                      ("CHECKPOINTS", tmp_path / "checkpoints"),
                      ("HEARTBEAT", tmp_path / "heartbeat.json")):
        monkeypatch.setattr(mod, name, val)
    monkeypatch.setattr(sys, "argv", ["moat_recorder.py", "--once"])
    return mod


def test_the_moat_recorder_refuses_ftmo_and_records_nothing(
        bridge: _Bridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _moat(monkeypatch, tmp_path, bridge)
    bridge.server = "FTMO-Server3"
    assert mod.main() == mod.EXIT_WRONG_VENUE
    assert bridge.init_kwargs[0]["path"] == FUSION_EXE
    assert bridge.shutdowns == 1
    assert not (tmp_path / "bronze").exists()


def test_the_moat_recorder_exits_when_the_account_changes_mid_run(
        bridge: _Bridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _moat(monkeypatch, tmp_path, bridge)
    bridge.attached = True
    rec = mod.Recorder()
    events: list[dict] = []
    monkeypatch.setattr(rec, "health_row", lambda **kw: events.append(kw))
    bridge.server = "FTMO-Server3"
    with pytest.raises(SystemExit) as stop:
        rec.cycle()
    assert stop.value.code == mod.EXIT_WRONG_VENUE
    assert events and events[0]["event"] == "wrong_venue"
