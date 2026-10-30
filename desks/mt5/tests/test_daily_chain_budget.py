"""The daily chain cannot be starved by one step (2026-10-29).

MT5-Daily (PT10H, 21:50Z) logged "36 step(s) of 37 never did" every day: research_gap_map took
2h20m and refresh_bars 6h34m, factor_residual failed, and the task limit killed the run before
`shadow`. Pinned here: refresh_tail is bounded, skips what cannot have new bars, does not rewrite
an unchanged file, and resumes stalest-first; a non-critical step only starts when it leaves the
critical steps their measured room; every step's last completed run is recorded; and a step with
none in two days is RED.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_DESK / "scripts"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import daily_cycle  # noqa: E402
import refresh_tail as rt  # noqa: E402

from libs.ops import seat_clocks  # noqa: E402


@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_cycle, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(daily_cycle, "LOG", tmp_path / "daily_cycle.log")
    monkeypatch.setitem(daily_cycle._DEADLINE, "seconds", None)
    monkeypatch.setitem(daily_cycle._DEADLINE, "t0", None)
    clock = {"t": 0.0}
    monkeypatch.setattr(daily_cycle.time, "monotonic", lambda: clock["t"])
    return tmp_path, clock


def test_a_long_research_step_is_deferred_so_the_critical_steps_run(chain, monkeypatch):
    tmp, clock = chain
    calls: list[str] = []

    def step(name, secs):
        def fn():
            calls.append(name)
            clock["t"] += secs
        return fn

    monkeypatch.setattr(daily_cycle, "STEPS", (
        ("research_gap_map", step("research_gap_map", 8400)),
        ("cost_fields", step("cost_fields", 100)),
        ("shadow", step("shadow", 600)), ("promoter", step("promoter", 300)),
        ("markout", step("markout", 300))))
    (tmp / "daily_step_history.json").write_text(json.dumps({
        "research_gap_map": {"last_seconds": 8400}, "shadow": {"last_seconds": 600},
        "promoter": {"last_seconds": 300}, "markout": {"last_seconds": 300}}), "utf-8")
    daily_cycle._DEADLINE.update({"t0": 0.0, "seconds": 3000.0, "basis": "test"})
    assert daily_cycle._run_chain(force=False) == 0
    assert calls == ["cost_fields", "shadow", "promoter", "markout"]
    stamp = json.loads((tmp / "daily_cycle_state.json").read_text("utf-8"))
    assert "research_gap_map" not in stamp["steps"]          # left for a later pass
    hist = json.loads((tmp / "daily_step_history.json").read_text("utf-8"))
    assert hist["shadow"]["last_ok"] is True and hist["shadow"]["last_ok_at"]
    # a pass with room runs it
    daily_cycle._DEADLINE.update({"t0": clock["t"], "seconds": 20000.0})
    daily_cycle._run_chain(force=False)
    assert calls[-1] == "research_gap_map"


def test_without_a_deadline_nothing_is_deferred(chain, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(daily_cycle, "STEPS", tuple(
        (n, (lambda n=n: calls.append(n))) for n in ("research_gap_map", "shadow")))
    daily_cycle._run_chain(force=False)
    assert calls == ["research_gap_map", "shadow"]


def test_the_proposers_see_only_the_time_the_critical_steps_leave(chain, monkeypatch):
    daily_cycle._DEADLINE.update({"t0": 0.0, "seconds": 1000.0, "basis": "test"})
    monkeypatch.setitem(daily_cycle._RESERVE, "s", 700.0)
    assert daily_cycle._research_left_s() == 300.0


def test_the_critical_steps_are_real_steps():
    names = {n for n, _ in daily_cycle.STEPS}
    assert daily_cycle.CRITICAL_STEPS <= names
    assert set(daily_cycle.STEP_EXPECTED_CAP_S) <= names


def test_red_names_a_step_with_no_completed_run_in_two_days(tmp_path):
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    now = seat_clocks._iso_ts("2027-01-15T12:00:00+00:00")
    (desk / "data" / "daily_step_history.json").write_text(json.dumps({
        "shadow": {"last_ok_at": "2027-01-15T00:00:00+00:00"},
        "factor_residual": {"last_ok_at": "2027-01-10T00:00:00+00:00",
                            "last_error": "AttributeError: 'NaTType' ..."}}), "utf-8")
    red = seat_clocks.red_daily_steps(now, desk, ["shadow", "factor_residual", "markout"])
    assert [r["seat"] for r in red] == ["factor_residual", "markout"]
    assert "NaTType" in red[0]["why"] and "never recorded" in red[1]["why"]
    assert len(seat_clocks._daily_steps(_DESK)) == len(daily_cycle.STEPS)


# ------------------------------------------------------------------------- refresh_tail


class _FakeMT5:
    TIMEFRAME_H1 = 16385

    def __init__(self, bars_per_call: int = 3):
        self.calls: list[str] = []
        self.n = bars_per_call

    def symbol_select(self, sym, on):
        return True

    def copy_rates_from_pos(self, sym, period, start, count):
        self.calls.append(sym)
        end = pd.Timestamp.now(tz="UTC").floor("h")
        times = pd.date_range(end=end, periods=self.n, freq="h")
        return np.array([(int(t.timestamp()), 1.0, 1.0, 1.0, 1.0, 1, 1, 0) for t in times],
                        dtype=[("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                               ("close", "f8"), ("tick_volume", "i8"), ("spread", "i8"),
                               ("real_volume", "i8")])

    def last_error(self):
        return (0, "")


def _lake(tmp: Path, ages_h: dict[str, float]) -> Path:
    out = tmp / "data" / "universe"
    out.mkdir(parents=True)
    now = pd.Timestamp.now(tz="UTC").floor("h")
    for sym, age in ages_h.items():
        idx = pd.date_range(end=now - pd.Timedelta(hours=age), periods=50, freq="h", name="time")
        pd.DataFrame({c: 1.0 for c in ("open", "high", "low", "close")} | {
            "tick_volume": 1, "spread": 1, "real_volume": 0}, index=idx).to_parquet(
            out / f"{sym}_H1.parquet")
    return out


def test_a_series_with_nothing_new_closed_is_neither_fetched_nor_rewritten(tmp_path,
                                                                            monkeypatch):
    out = _lake(tmp_path, {"FRESH": 0.0, "STALE": 10.0})
    fake = _FakeMT5()
    monkeypatch.setattr(rt, "OUT", out)
    monkeypatch.setattr(rt, "mt5", fake)
    before = (out / "FRESH_H1.parquet").stat().st_mtime_ns
    assert rt.refresh_symbol("FRESH", "H1").startswith("fresh")
    assert fake.calls == []
    assert (out / "FRESH_H1.parquet").stat().st_mtime_ns == before
    assert rt.refresh_symbol("STALE", "H1").startswith("+")
    assert fake.calls == ["STALE"]


def test_a_bounded_run_resumes_with_the_stalest(tmp_path, monkeypatch):
    out = _lake(tmp_path, {s: 10.0 for s in ("AAA", "BBB", "CCC", "DDD")})
    monkeypatch.setattr(rt, "OUT", out)
    monkeypatch.setattr(rt, "STATE", tmp_path / "data" / "refresh_tail_state.json")
    monkeypatch.setattr(rt, "desk_root", lambda: tmp_path)
    clock = {"t": 0.0}
    monkeypatch.setattr(rt.time, "monotonic", lambda: clock["t"])
    seen: list[str] = []

    def fake_refresh(sym, tf):
        seen.append(sym)
        clock["t"] += 100.0
        return "+1 bars"

    monkeypatch.setattr(rt, "refresh_symbol", fake_refresh)
    monkeypatch.setattr(rt, "derive_all", lambda symbols=None: {"series": {}, "skipped": {}})

    class _Terminal(_FakeMT5):
        def terminal_info(self):
            return object()

        def account_info(self):
            return None

        def symbol_info(self, sym):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(rt, "mt5", _Terminal())
    assert rt.main(["--budget-s", "150"]) == 0
    assert seen == ["AAA", "BBB"]
    time.sleep(0.01)
    assert rt.main(["--budget-s", "150"]) == 0
    assert seen[2:] == ["CCC", "DDD"]
    st = json.loads((tmp_path / "data" / "refresh_tail_state.json").read_text("utf-8"))
    assert st["last_run_deferred"] == 2
