"""NEEDS_DATA: a never-firing cell that lacks an input is named for the input, never dropped.

    python -m pytest desks/mt5/tests/test_fireable_specs.py -q

`research/fire_inputs.py` answers NEEDS_DATA only when the family's own code, on the inputs
`external_gauntlet.build_cell` would hand it, returns no signal on any bars. These tests pin:
  1. each NEEDS_DATA answer is exact: the family really returns [] on real-shaped bars;
  2. anything the probe cannot settle is UNMEASURED and is never tagged (fail open);
  3. judge_coverage names, routes, re-admits and orders such cells without dropping one.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parent.parent
for p in (DESK, DESK / "research", DESK.parent.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mt5desk.families_orthogonal import family_cot_positioning  # noqa: E402
from mt5desk.family_event_reaction import family_event_reaction  # noqa: E402
from mt5desk.family_inputs import events_for_symbol  # noqa: E402

from libs.research import bar_clock  # noqa: E402
from research import fire_inputs as F  # noqa: E402
from research import judge_coverage as jc  # noqa: E402
from research import orthogonal_sweep as inputs  # noqa: E402


def _bars(n: int = 3000, start: str = "2026-05-01") -> pd.DataFrame:
    rng = np.random.default_rng(7)
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    close = 100 + np.cumsum(rng.normal(0, 0.2, n))
    return pd.DataFrame({"open": close, "high": close + 0.3, "low": close - 0.3,
                         "close": close, "tick_volume": 1}, index=idx)


def _cot(n: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2020-01-03", periods=n, freq="W-FRI", tz="UTC")
    return pd.DataFrame({"net": np.sin(np.arange(n) / 7.0)}, index=idx)


# ------------------------------------------------------------------ 1. exact NEEDS_DATA

def test_cot_without_a_series_is_needs_data_and_the_family_returns_nothing(monkeypatch) -> None:
    monkeypatch.setattr(inputs, "_cot_frame", lambda symbol=None: None)
    got = F.probe("EURCZK", "cot_positioning")
    assert got["status"] == F.NEEDS_DATA
    assert got["missing_input"] == "cot_series:EURCZK"
    # exact: the family itself, on real-shaped bars and the input the judge would hand it
    assert family_cot_positioning(_bars(), cot=inputs._cot_frame("EURCZK")) == []


def test_cot_with_a_series_is_present(monkeypatch) -> None:
    monkeypatch.setattr(inputs, "_cot_frame", lambda symbol=None: _cot())
    assert F.probe("XAUUSD", "cot_positioning")["status"] == F.PRESENT


def _events(monkeypatch, stamps: list[str]) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(pd.to_datetime(stamps, utc=True))
    monkeypatch.setattr(inputs, "_event_index", lambda: idx)
    return idx


def test_event_reaction_without_a_bar_clock_is_needs_data(monkeypatch) -> None:
    ev = _events(monkeypatch, ["2026-06-05 12:30", "2026-07-03 12:30"])
    monkeypatch.setattr(bar_clock, "offsets", lambda root=None: {})
    got = F.probe("EURUSD", "event_reaction")
    assert got["status"] == F.NEEDS_DATA and got["missing_input"] == "bar_clock"
    assert family_event_reaction(_bars(), events=events_for_symbol(ev, "EURUSD"),
                                 symbol="EURUSD", clock="utc") == []


def test_event_reaction_in_shoulder_months_only_is_needs_data(monkeypatch) -> None:
    ev = _events(monkeypatch, ["2026-10-02 12:30", "2026-10-09 12:30"])
    monkeypatch.setattr(bar_clock, "offsets", lambda root=None: {"summer": 3, "winter": 2})
    got = F.probe("EURUSD", "event_reaction")
    assert got["status"] == F.NEEDS_DATA and got["missing_input"] == "event_calendar_history"
    assert family_event_reaction(_bars(4000), events=events_for_symbol(ev, "EURUSD"),
                                 symbol="EURUSD", clock="utc") == []


def test_event_reaction_with_placeable_events_is_present(monkeypatch) -> None:
    _events(monkeypatch, ["2026-06-05 12:30", "2026-07-03 12:30"])
    monkeypatch.setattr(bar_clock, "offsets", lambda root=None: {"summer": 3, "winter": 2})
    got = F.probe("EURUSD", "event_reaction")
    assert got["status"] == F.PRESENT and got["placeable_events"] == 2


# ------------------------------------------------------------------ 2. fail open

def test_unprobed_families_and_errors_are_unmeasured(monkeypatch) -> None:
    assert F.probe("EURUSD", "carry")["status"] == F.UNMEASURED
    assert F.probe("", "cot_positioning")["status"] == F.UNMEASURED

    def boom(symbol=None):
        raise OSError("disk")
    monkeypatch.setattr(inputs, "_cot_frame", boom)
    assert F.probe("EURUSD", "cot_positioning")["status"] == F.UNMEASURED


def test_no_calendar_at_all_is_left_to_the_judge(monkeypatch) -> None:
    monkeypatch.setattr(inputs, "_event_index", lambda: None)
    assert F.probe("EURUSD", "event_reaction")["status"] == F.UNMEASURED


# ------------------------------------------------------------------ 3. judge_coverage

def _report(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "gates.json"
    p.write_text(json.dumps({"verdicts": rows}), "utf-8")
    return p


def _unknown(cell: str, sym: str, fam: str) -> dict:
    return {"cell": cell, "sym": sym, "family": fam, "unmeasured": True, "days": 0,
            "params": {}, "unknown_reason": "no_signals"}


def test_name_unknowns_names_the_missing_input(tmp_path, monkeypatch) -> None:
    def fake(sym, fam):
        return ({"status": "NEEDS_DATA", "missing_input": f"cot_series:{sym}", "why": "w",
                 "stamp": "absent"} if fam == "cot_positioning" else {"status": "UNMEASURED"})
    monkeypatch.setattr(jc, "_fire_probe", fake)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1000)
    named = jc.name_unknowns(_report(tmp_path, [
        _unknown("EURCZK.cot_positioning.p=1", "EURCZK", "cot_positioning"),
        _unknown("EURUSD.carry.p=2", "EURUSD", "carry")]))
    a, b = named["EURCZK.cot_positioning.p=1"], named["EURUSD.carry.p=2"]
    assert a["reason"] == "needs_data" and a["missing_input"] == "cot_series:EURCZK"
    assert b["reason"] == "never_fires"
    assert "needs_data" in jc.NOT_TESTABLE_REASONS
    assert jc.FAILURE_ROUTES[jc.failure_class("needs_data") or ""]["owner"] == "converter"
    assert jc._missing_input("needs_data", a)["input"] == "cot_series:EURCZK"


def test_needs_data_returns_when_the_input_appears_not_when_bars_grow(monkeypatch) -> None:
    now = datetime(2026, 10, 20, tzinfo=UTC)
    row = {"reason": "needs_data", "sym": "EURCZK", "family": "cot_positioning", "tf": "H1",
           "days": 0, "bar_bytes": 100, "parked_at": (now - timedelta(days=5)).isoformat()}
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 10_000)        # bars grew 100x
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: {"status": "NEEDS_DATA"})
    assert jc.readmit_due(row, now=now) is False
    old = {**row, "parked_at": (now - timedelta(days=jc.READMIT_MAX_DAYS + 1)).isoformat()}
    assert jc.readmit_due(old, now=now) is True
    for status in ("PRESENT", "UNMEASURED"):
        monkeypatch.setattr(jc, "_fire_probe", lambda s, f, st=status: {"status": st})
        assert jc.readmit_due(row, now=now) is True, status


def test_intake_order_tails_needs_data_and_keeps_every_row(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 1_000)
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: (
        {"status": "NEEDS_DATA", "missing_input": "bar_clock"} if f == "event_reaction"
        else {"status": "UNMEASURED", "why": "family not probed"}))
    rows = [{"sym": "EURUSD", "family": "event_reaction", "n": 0},
            {"sym": "EURUSD", "family": "carry", "n": 1},
            {"sym": "GBPUSD", "family": "event_reaction", "n": 2},
            {"sym": "GBPUSD", "family": "carry", "n": 3}]
    out, doc = jc.fireability_order(list(rows))
    assert [r["n"] for r in out] == [1, 3, 0, 2]
    assert sorted(map(id, out)) == sorted(map(id, rows)), "no row dropped or copied"
    assert doc["rows_needs_data_to_tail"] == 2
    assert doc["by_missing_input"] == {"bar_clock": 2}


def test_never_fire_ground_still_counts_renamed_cells() -> None:
    bank = {f"c{i}": {"reason": "needs_data", "family": "event_reaction", "sym": "EURUSD"}
            for i in range(jc.SIBLING_NEVER_FIRES_MIN)}
    assert jc.never_fire_pairs(bank, set()) == {("event_reaction", "EURUSD")}


@pytest.mark.parametrize("fam", F.PROBED)
def test_probed_families_resolve_to_the_function_the_judge_calls(fam) -> None:
    fn = F._resolved(fam)
    assert fn is (family_cot_positioning if fam == "cot_positioning" else family_event_reaction)


# ------------------------------------------------------------- audit of c72ecfc53 (should-fixes)

def test_a_missing_season_offset_is_named_bar_clock_not_calendar_history(monkeypatch) -> None:
    """Summer measured, winter not: a winter-only calendar lacks the CLOCK, not history."""
    _events(monkeypatch, ["2026-01-08 12:30", "2026-01-15 12:30"])
    monkeypatch.setattr(bar_clock, "offsets", lambda root=None: {"summer": 3})
    got = F.probe("EURUSD", "event_reaction")
    assert got["status"] == F.NEEDS_DATA and got["missing_input"] == "bar_clock"
    assert got["dropped"] == {bar_clock.UNMEASURED: 2}


def test_the_probe_leaves_the_familys_drop_counter_as_it_found_it(monkeypatch) -> None:
    from mt5desk import family_event_reaction as fer
    _events(monkeypatch, ["2026-10-02 12:30"])
    monkeypatch.setattr(bar_clock, "offsets", lambda root=None: {"summer": 3, "winter": 2})
    monkeypatch.setattr(fer, "_DROPPED", {"X": 7})
    F.probe("EURUSD", "event_reaction")
    assert fer._DROPPED == {"X": 7}


def test_intake_order_does_not_tail_a_needs_data_row_with_no_bars(monkeypatch) -> None:
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: (
        {"status": "NEEDS_DATA", "missing_input": "bar_clock"} if f == "event_reaction"
        else {"status": "UNMEASURED", "why": "family not probed"}))
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 0 if sym == "NOBARS" else 1_000)
    rows = [{"sym": "NOBARS", "family": "event_reaction", "n": 0},
            {"sym": "EURUSD", "family": "event_reaction", "n": 1},
            {"sym": "EURUSD", "family": "carry", "n": 2}]
    out, doc = jc.fireability_order(list(rows))
    assert [r["n"] for r in out] == [0, 2, 1]
    assert doc["rows_needs_data_to_tail"] == 1 and doc["rows_needs_data_kept_no_bars"] == 1


def test_the_readmit_clock_is_exactly_ninety_days(monkeypatch) -> None:
    assert jc.READMIT_MAX_DAYS == 90.0
    now = datetime(2026, 10, 20, tzinfo=UTC)
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 100)
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: {"status": "NEEDS_DATA"})
    base = {"reason": "needs_data", "sym": "EURCZK", "family": "cot_positioning", "tf": "H1",
            "days": 0, "bar_bytes": 100}
    for age, due in ((89.9, False), (90.0, True), (90.1, True)):
        row = {**base, "parked_at": (now - timedelta(days=age)).isoformat()}
        assert jc.readmit_due(row, now=now) is due, age
    never = {**base, "reason": "never_fires"}
    for age, due in ((89.9, False), (90.0, True)):
        row = {**never, "parked_at": (now - timedelta(days=age)).isoformat()}
        assert jc.readmit_due(row, now=now) is due, age


def test_a_clock_readmitted_cell_still_missing_its_input_keeps_its_handoff_row(
        tmp_path, monkeypatch) -> None:
    now = datetime(2026, 10, 20, tzinfo=UTC)
    bank_path = tmp_path / "unrunnable_specs.json"
    row = {"reason": "needs_data", "sym": "EURCZK", "family": "cot_positioning", "tf": "H1",
           "days": 0, "bar_bytes": 100, "missing_input": "cot_series:EURCZK",
           "parked_at": (now - timedelta(days=91)).isoformat()}
    bank_path.write_text(json.dumps({"EURCZK.cot_positioning.p=1": row}), "utf-8")
    monkeypatch.setattr(jc, "_bar_bytes", lambda sym, tf="H1": 100)
    status = {"v": "NEEDS_DATA"}
    monkeypatch.setattr(jc, "_fire_probe", lambda s, f: {"status": status["v"]})
    got = jc.update_unrunnable_bank({}, at=now.isoformat(), path=bank_path)
    assert got["bank_size"] == 0 and got["needs_data_outstanding"] == 1
    out = jc.needs_data_outstanding(tmp_path / jc.NEEDS_DATA_OUTSTANDING.name)
    handoff = tmp_path / "conversion_handoff.json"
    assert jc.write_conversion_handoff({}, at="t", path=handoff, outstanding=out) == 1
    hrow = json.loads(handoff.read_text("utf-8"))["rows"][0]
    assert hrow["still_missing_after_readmit"] is True
    assert hrow["missing_input"]["input"] == "cot_series:EURCZK"
    status["v"] = "PRESENT"                                    # the input appeared
    got = jc.update_unrunnable_bank({}, at=now.isoformat(), path=bank_path)
    assert got["needs_data_outstanding"] == 0


def test_needs_data_axes_name_only_organs_that_read_them() -> None:
    axes = jc.FAILURE_ROUTES["needs_data"]["axes"]
    assert "acquire_named_input" not in axes and "proxy_series" not in axes
