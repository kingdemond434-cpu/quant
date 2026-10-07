"""Clock fallback measurements must remain distinguishable from invented UTC labels."""
import json
import sys
from types import SimpleNamespace

import pytest

from libs.ops.mt5_readonly import wraps
from desks.mt5.research import session_phase as sp


@pytest.fixture
def clock_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "BROKER_CLOCK", tmp_path / "data/clock.json")
    monkeypatch.setattr(sp, "BROKER_CLOCK_MEASURED", tmp_path / "measured.json")
    return tmp_path


def test_live_offset_is_recorded_and_rounds_once(clock_paths, monkeypatch):
    terminal = object()
    monkeypatch.setitem(sys.modules, "MetaTrader5", terminal)
    monkeypatch.setitem(sys.modules, "h1_source", SimpleNamespace(
        broker_utc_offset_hours=lambda module: 2.8 if wraps(module, terminal) else None))
    assert sp.broker_utc_offset_h() == (3, "live_terminal")
    saved = json.loads(sp.BROKER_CLOCK.read_text())
    assert saved["utc_offset_hours"] == 3
    assert saved["source"] == "live_terminal"
    first = sp.BROKER_CLOCK.read_bytes()
    sp._record_broker_clock(3)
    assert sp.BROKER_CLOCK.read_bytes() == first
    saved["measured_at"] = "2020-01-01T00:00:00+00:00"
    sp.BROKER_CLOCK.write_text(json.dumps(saved))
    sp._record_broker_clock(3)
    assert json.loads(sp.BROKER_CLOCK.read_text())["measured_at"] != saved["measured_at"]


@pytest.mark.parametrize("record", [{}, {"status": "UNMEASURED", "utc_offset_hours": 2},
                                    {"status": "MEASURED", "utc_offset_hours": "bad"}])
def test_invalid_inference_remains_unknown(clock_paths, monkeypatch, record):
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    sp.BROKER_CLOCK_MEASURED.write_text(json.dumps(record))
    assert sp.broker_utc_offset_h() == (None, "unknown")


def test_failure_to_persist_is_loud_without_losing_live_measurement(clock_paths, capsys):
    sp.BROKER_CLOCK.parent.write_text("cannot be a directory")
    sp._record_broker_clock(2)
    assert "broker clock NOT written" in capsys.readouterr().out


def test_missing_and_malformed_returns_cannot_create_midnight_edge():
    rows = [{"r_multiple": 90}, {"entry_time": None, "time": "bad", "ts": "xT0"},
            {"time": "2026-10-05T07:00", "r_multiple": None},
            {"ts": "2026-10-05 07:00", "r_multiple": "not a number"},
            {"entry_time": "2026-10-05T07:00", "r_multiple": 1.5}]
    assert sp.returns_in_phase(rows, "LONDON_OPEN", broker_utc_offset_h=0).tolist() == [1.5]
    assert sp.returns_in_phase(rows, "ASIA_OPEN", broker_utc_offset_h=0).size == 0


def test_broken_phase_tiling_fails_instead_of_guessing(monkeypatch):
    monkeypatch.setattr(sp, "PHASES", (("ASIA_OPEN", 0, 2),))
    with pytest.raises(ValueError, match="no phase covers"):
        sp.phase_for_hour(7)
