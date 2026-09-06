"""A seat may not be admitted at a memory level it has already been observed to die at.

1500MB WAS THE SECOND GUESS. 500MB was chosen as "enough that the launch does not immediately
die", and the measured outcome was that seats died anyway: six gap-wirer launches OOM-killed on
2026-08-28, three more in the 24h to 2026-09-05, gap-wirer and video-hunter both at ZERO produced
in seven days. Raising a guess to a bigger guess is the move that already failed.

So the floor is learned from evidence the desk already collects. `brain_mem_gate` prints the level
it admitted a launch at into that seat's own log; `check_seat_launch_yield` already classifies
every launch and knows which were DIED_AFTER_START -- the OOM shape. Joining the two gives, per
seat, the highest level at which it was let in and then killed.

THE RULE IS MINIMAL ON PURPOSE: the floor must merely EXCEED that level. No headroom constant, no
multiplier, nothing invented -- if the seat dies again higher up, the floor rises again next pass.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "_sly", _ROOT / "scripts" / "check_seat_launch_yield.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def sly():
    return _load()


def test_the_gate_line_is_parsed_from_a_seat_log(sly) -> None:
    """The join between the two halves. If the gate's wording drifts, this fails rather than the
    floor silently never being learned -- which would look exactly like "no seats have died"."""
    line = "brain_mem_gate: 1732 MB available >= 1500 MB floor -- go"
    m = sly._ADMITTED_RE.search(line)
    assert m and int(m.group(1)) == 1732


def test_the_gate_wording_this_parses_still_exists(sly) -> None:
    """Read the SHELL, not a remembered copy of it.

    A test that only checks its own fixture string passes forever after the gate is reworded, and
    the floor then stops being learned with nothing failing. This asserts the producer still emits
    what the consumer parses.
    """
    gate = (_ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    assert "brain_mem_gate: %d MB available" in gate, (
        "the gate no longer prints the admitted level in the form the yield checker parses -- the "
        "floor would silently stop being learned")


def test_a_seat_that_died_gets_a_floor_above_the_level_it_died_at(
        sly, tmp_path, monkeypatch) -> None:
    """The whole point: gap-wirer admitted at 1600MB and killed must never see 1600 again."""
    out = tmp_path / "seat_memory_floor.json"
    monkeypatch.setattr(sly, "MEM_FLOOR", out)
    monkeypatch.setattr(sly, "OUT", tmp_path / "yield.json")
    monkeypatch.setattr(sly, "FLOOR", tmp_path / "floor.json")
    monkeypatch.setattr(sly, "scan", lambda days: {
        "measured_at": "2026-09-06T00:00:00Z", "window_days": days, "launches": 2,
        "billable": 2, "produced": 0, "yield_pct": 0.0, "outcomes": {"DIED_AFTER_START": 2},
        "by_hour": {}, "dead_hours_utc": [], "starved_hours_utc": [], "died_recent_24h": 2,
        "dead_seats": [], "not_expected_to_launch": [], "not_expected_note": "",
        "productive_hours_utc": [], "quota_walls": {},
        "fatal_admission_mb": {"gap-wirer": 1600, "video-hunter": 1520},
    })
    monkeypatch.setattr(sys, "argv", ["x", "--days", "7"])
    sly.main()

    floors = json.loads(out.read_text("utf-8"))["floors"]
    assert floors["gap-wirer"] == 1601, "the floor does not exceed the level that killed it"
    assert floors["video-hunter"] == 1521


def test_the_floor_only_ever_rises(sly, tmp_path, monkeypatch) -> None:
    """A quiet box must not lower a bar a busy one has already broken."""
    out = tmp_path / "seat_memory_floor.json"
    out.write_text(json.dumps({"floors": {"gap-wirer": 2400}}), "utf-8")
    monkeypatch.setattr(sly, "MEM_FLOOR", out)
    monkeypatch.setattr(sly, "OUT", tmp_path / "yield.json")
    monkeypatch.setattr(sly, "FLOOR", tmp_path / "floor.json")
    monkeypatch.setattr(sly, "scan", lambda days: {
        "measured_at": "2026-09-06T00:00:00Z", "window_days": days, "launches": 1,
        "billable": 1, "produced": 0, "yield_pct": 0.0, "outcomes": {"DIED_AFTER_START": 1},
        "by_hour": {}, "dead_hours_utc": [], "starved_hours_utc": [], "died_recent_24h": 1,
        "dead_seats": [], "not_expected_to_launch": [], "not_expected_note": "",
        "productive_hours_utc": [], "quota_walls": {},
        "fatal_admission_mb": {"gap-wirer": 900},
    })
    monkeypatch.setattr(sys, "argv", ["x", "--days", "7"])
    sly.main()
    assert json.loads(out.read_text("utf-8"))["floors"]["gap-wirer"] == 2400


def test_the_reader_the_gate_uses_has_a_writer(sly) -> None:
    """The defect this whole file is built to avoid repeating.

    `brain_mem_gate` reads data/seat_memory_floor.json. Adding that reader without a producer
    would have made it one more of the 166 artifacts `check_read_without_writer.py` counts as
    read-by-production-code-with-no-writer -- a fence that quietly always returns the default.
    """
    gate = (_ROOT / "ops" / "brain_env.sh").read_text("utf-8")
    assert "seat_memory_floor.json" in gate, "the gate no longer reads the learned floor"
    src = (_ROOT / "scripts" / "check_seat_launch_yield.py").read_text("utf-8")
    assert "MEM_FLOOR.write_text" in src, "nothing writes the floor the gate reads"
