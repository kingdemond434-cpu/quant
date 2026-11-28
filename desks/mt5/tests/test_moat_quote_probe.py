"""The moat recorder's terminal quote probe: what it writes, and what it may re-select.

The probe is the one reading that splits "the broker is not quoting this class" from "our writers
are missing it", and `tape_liveness.terminal_block` only trusts it under a lease. These tests pin
the fields that lease reads and the Market Watch repair's reach.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class _Terminal:
    """A stand-in for the MetaTrader5 module: quotes and Market Watch visibility per symbol."""

    def __init__(self) -> None:
        self.quotes: dict[str, int] = {}
        self.visible: dict[str, bool] = {}
        self.selected: list[str] = []

    def symbol_info(self, sym: str) -> SimpleNamespace | None:
        if sym not in self.visible:
            return None
        return SimpleNamespace(path=f"Group\\{sym}", visible=self.visible[sym])

    def symbol_info_tick(self, sym: str) -> SimpleNamespace | None:
        return SimpleNamespace(time_msc=self.quotes[sym]) if sym in self.quotes else None

    def symbol_select(self, sym: str, on: bool) -> bool:
        self.selected.append(sym)
        return True


@pytest.fixture
def rig(tmp_path, monkeypatch):
    term = _Terminal()
    fake = types.ModuleType("MetaTrader5")
    for name in ("symbol_info", "symbol_info_tick", "symbol_select"):
        setattr(fake, name, getattr(term, name))
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    spec = importlib.util.spec_from_file_location(
        "moat_recorder_under_test", _DESK / "moat" / "moat_recorder.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "QUOTES", tmp_path / "terminal_quotes.json")
    monkeypatch.setattr(mod, "CHECKPOINTS", tmp_path / "checkpoints")
    monkeypatch.setattr(mod, "BRONZE", tmp_path / "bronze")
    clock = {"mono": 1000.0}
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock["mono"])
    rec = mod.Recorder()
    events: list[dict] = []
    monkeypatch.setattr(rec, "health_row", lambda **kw: events.append(kw))
    return SimpleNamespace(mod=mod, term=term, rec=rec, clock=clock, events=events,
                           out=tmp_path / "terminal_quotes.json")


def _read(rig) -> dict:
    return json.loads(rig.out.read_text("utf-8"))


def test_the_probe_writes_the_fields_the_liveness_lease_reads(rig):
    rig.term.quotes = {"BTCUSD": 5_000_000, "Apple": 5_000_000 - 17 * 3_600_000}
    rig.term.visible = {"BTCUSD": True, "Apple": True}
    rig.rec.universe = ["BTCUSD", "Apple", "Gone"]
    rig.rec.zero_pulls = {"Apple": 9}
    rig.rec.quote_probe()
    got = _read(rig)
    assert got["terminal_newest_ms"] == 5_000_000 and got["newest_stalled_s"] == 0
    assert isinstance(got["now_ms"], int) and got["at"] and got["probe_s"] == rig.mod.QUOTE_PROBE_S
    assert got["symbols"]["Apple"] == {"path": "Group\\Apple", "visible": True,
                                       "quote_ms": 5_000_000 - 17 * 3_600_000, "zero_pulls": 9}
    # A symbol the terminal does not know is a row, never a crash and never a guess.
    assert got["symbols"]["Gone"] == {"path": None, "visible": None, "quote_ms": None,
                                      "zero_pulls": 0}


def test_a_frozen_terminal_is_counted_on_the_monotonic_clock(rig):
    """Every quote ages together on a disconnected terminal; only "did the newest move" sees it."""
    rig.term.quotes, rig.term.visible = {"BTCUSD": 5_000_000}, {"BTCUSD": True}
    rig.rec.universe = ["BTCUSD"]
    rig.rec.quote_probe()
    rig.clock["mono"] += 2400
    rig.rec.quote_probe()
    assert _read(rig)["newest_stalled_s"] == 2400
    rig.term.quotes["BTCUSD"] += 1
    rig.clock["mono"] += 300
    rig.rec.quote_probe()
    assert _read(rig)["newest_stalled_s"] == 0


def test_only_a_symbol_out_of_market_watch_is_reselected_and_at_most_hourly(rig):
    """Auditor: visible symbols were re-selected every hour all weekend (~100 calls + a row)."""
    old = 5_000_000 - 17 * 3_600_000
    rig.term.quotes = {"BTCUSD": 5_000_000, "Apple": old, "Tesla": old, "Nvidia": old}
    rig.term.visible = {"BTCUSD": True, "Apple": True, "Tesla": False, "Nvidia": False}
    rig.rec.universe = list(rig.term.visible)
    rig.rec.zero_pulls = {"Apple": 9, "Tesla": 9, "Nvidia": 1}     # Nvidia: too few empty pulls
    rig.rec.quote_probe()
    assert rig.term.selected == ["Tesla"]
    assert _read(rig)["symbols"]["Tesla"]["reselected"] is True
    assert "reselected" not in _read(rig)["symbols"]["Apple"]
    assert rig.events == [{"event": "market_watch_reselect", "symbols": ["Tesla"], "n": 1}]
    rig.clock["mono"] += rig.mod.RESELECT_S - 1
    rig.rec.quote_probe()
    assert rig.term.selected == ["Tesla"]
    rig.clock["mono"] += 2
    rig.rec.quote_probe()
    assert rig.term.selected == ["Tesla", "Tesla"]
