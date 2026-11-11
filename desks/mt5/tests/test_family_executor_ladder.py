"""The family executor runs the certificate's own chart, and takes one entry a day on all of them.

THE STATE THIS REPLACES, 2026-09-05. The sweep gained the M1..D1 ladder and every `family_market`
path in the gateway still called `copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 400)`
unconditionally. A certificate IS enrolment, so a matured M5 candidate would have been promoted to
a live row and had its signals computed FROM HOURLY BARS -- a real position in a strategy nobody
certified, under the name of one that was, with every artifact agreeing.
`executables.GATEWAY_FAMILY_TIMEFRAMES = ("H1",)` held those rows out of the book while that was
true. That was the honest state, not the destination.

Two things had to be right before the tuple could widen, and they are what these tests pin:

  THE CHART   `gateway._family_chart` reads it off the certificate's own params, scales the bar
              count so every chart gets the same MARKET TIME rather than the same bar count, and
              REFUSES BY NAME for a chart the box has no constant for -- never falling back to
              hourly, which is the one outcome that would put the original defect back.
  THE ENTRY   `decision_core.family_bar_due` fired on `last_bar.hour == sig_hour`, which is one
              bar a day on H1 and TWELVE on M5, SIXTY on M1. A sleeve certified to take one entry
              a day would have taken sixty. It now also requires the bar to START the hour.

H1 MUST COME THROUGH BOTH UNCHANGED, byte for byte, or every certificate written before the ladder
silently changes meaning. That is asserted here rather than assumed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

dc = pytest.importorskip("mt5desk.decision_core")
ex = pytest.importorskip("mt5desk.executables")

_LADDER = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def _closed(*stamps: str) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(s, tz="UTC") for s in stamps])
    return pd.DataFrame({"close": [1.0] * len(idx)}, index=idx)


class TestTheEntryRuleIsOnePerDayOnEveryChart:
    def test_h1_is_unchanged(self) -> None:
        """Every H1 bar begins on the hour, so the added `minute == 0` test is always true there
        and cannot alter a single decision any existing certificate has ever made."""
        for hour in range(24):
            frame = _closed(f"2026-09-04T{hour:02d}:00:00")
            assert dc.family_bar_due(frame, hour) is not None
            assert dc.family_bar_due(frame, (hour + 1) % 24) is None

    @pytest.mark.parametrize(("minute", "due"), [(0, True), (5, False), (30, False), (55, False)])
    def test_only_the_bar_that_starts_the_hour_is_due_on_m5(self, minute: int, due: bool) -> None:
        """THE DEFECT, directly: on M5 an hour holds twelve bars and the bare hour test made all
        twelve due. Twelve entries for a strategy certified to take one."""
        frame = _closed(f"2026-09-04T09:{minute:02d}:00")
        assert (dc.family_bar_due(frame, 9) is not None) is due

    def test_an_m1_hour_yields_exactly_one_due_bar_out_of_sixty(self) -> None:
        due = [m for m in range(60)
               if dc.family_bar_due(_closed(f"2026-09-04T09:{m:02d}:00"), 9) is not None]
        assert due == [0], f"expected one due bar in the hour, got {len(due)}"

    def test_the_wrong_hour_is_never_due_whatever_the_minute(self) -> None:
        for minute in (0, 5, 30):
            assert dc.family_bar_due(_closed(f"2026-09-04T08:{minute:02d}:00"), 9) is None


class TestTheExecutorRunsTheWholeLadder:
    def test_every_swept_chart_is_executable(self, monkeypatch) -> None:
        """The point of the change: a certificate on any chart the sweep hunts reaches capital by
        the same path as an H1 one, instead of being parked as an executor_gap forever."""
        monkeypatch.setattr(ex, "population_of", lambda fam: "hunt16")
        for tf in _LADDER:
            assert ex.executor_gap("session_range_breakout", tf) is None, tf

    def test_the_boundary_still_exists_for_a_chart_nothing_sweeps(self, monkeypatch) -> None:
        """NOT deleted, widened. The day an eighth timeframe joins the sweep it is a named
        executor_gap until the executor is shown to run it -- which is the whole reason this
        constant was introduced rather than the H1 read simply being edited."""
        monkeypatch.setattr(ex, "population_of", lambda fam: "hunt16")
        gap = ex.executor_gap("session_range_breakout", "W1")
        assert gap is not None and "W1" in gap
        assert "never certified on" in gap

    def test_the_declared_ladder_matches_what_the_sweep_hunts(self) -> None:
        assert set(ex.GATEWAY_FAMILY_TIMEFRAMES) == set(_LADDER)

    def test_the_gap_message_no_longer_describes_a_hardcoded_hourly_read(self, monkeypatch) -> None:
        """The message named `copy_rates_from_pos(..., TIMEFRAME_H1, 0, 400)` as the reason. That
        call is gone, and a fence that explains itself with code that no longer exists sends the
        reader to fix the wrong thing."""
        monkeypatch.setattr(ex, "population_of", lambda fam: "hunt16")
        gap = ex.executor_gap("session_range_breakout", "W1") or ""
        assert "TIMEFRAME_H1" not in gap
        assert "_family_chart" in gap


#: The MT5 timeframe constants `_family_chart` resolves against. Real values from the terminal's
#: own enum, so a stub cannot disagree with the box about which chart a name means.
_MT5_ENUM = {"TIMEFRAME_M1": 1, "TIMEFRAME_M5": 5, "TIMEFRAME_M15": 15, "TIMEFRAME_M30": 30,
             "TIMEFRAME_H1": 16385, "TIMEFRAME_H4": 16388, "TIMEFRAME_D1": 16408}


@pytest.fixture
def gw(monkeypatch):
    """`mt5desk.gateway` with a stand-in MetaTrader5, so the chart resolver is TESTED rather than
    SKIPPED off the trading box.

    The three tests below were skipping on every machine that is not the Windows box -- including
    CI -- which for a change to the money path is the worst place to have no coverage: the one
    host that could run them is the one where a mistake trades real capital. Only the TIMEFRAME_*
    enum is stubbed, with the terminal's real values, because that is all `_family_chart` reads.
    """
    import types
    stub = types.ModuleType("MetaTrader5")
    for name, value in _MT5_ENUM.items():
        setattr(stub, name, value)
    monkeypatch.setitem(sys.modules, "MetaTrader5", stub)
    return pytest.importorskip("mt5desk.gateway")


class TestTheChartComesFromTheCertificate:
    def _chart(self, tf: str | None, gw=None):
        row = {"symbol": "EURUSD", "params": ({} if tf is None else {"timeframe": tf})}
        return gw, gw._family_chart(row)

    def test_an_absent_timeframe_resolves_to_h1_and_its_original_bar_count(self, gw) -> None:
        """Absent means H1 -- the desk-wide spelling. Every certificate written before the ladder
        must resolve to exactly what it resolved to before, including the 400-bar read."""
        gw, (tf, const, bars) = self._chart(None, gw)
        assert tf == "H1" and const is not None
        assert bars == gw._FAMILY_H1_BARS

    def test_every_chart_gets_enough_bars_for_the_family_helpers(self, gw) -> None:
        """The invariant is ENOUGH BARS, not equal market time, and this test was written the
        other way round first. Scaling 400 hours onto D1 gives seventeen bars -- fewer than ATR_N
        needs -- so the floor raises it to 60, which is 60 DAYS and far more market time than H1's
        400 hours. Each chart gets what its own lookbacks require; insisting on equal market time
        would starve the slow end of the ladder to match the fast one."""
        gw, _ = self._chart("H1", gw)
        for tf in _LADDER:
            _, const, bars = gw._family_chart({"symbol": "EURUSD", "params": {"timeframe": tf}})
            assert const is not None, tf
            assert bars >= 60, f"{tf} would be handed {bars} bars, below the executor's own guard"
            assert bars <= gw._FAMILY_MAX_BARS, f"{tf} exceeds the per-call cap"

    def test_the_fast_charts_are_scaled_up_and_capped(self, gw) -> None:
        """M1/M5 must get MORE bars than H1 (same market time is the goal there) but never an
        unbounded read: 400 hours of M1 is 24,000 bars on a box that already runs out of memory."""
        gw, _ = self._chart("H1", gw)
        counts = {tf: gw._family_chart({"symbol": "EURUSD", "params": {"timeframe": tf}})[2]
                  for tf in ("M1", "M5", "H1")}
        assert counts["M5"] > counts["H1"]
        assert counts["M1"] >= counts["M5"]
        assert counts["M1"] == gw._FAMILY_MAX_BARS, "the M1 read must hit the cap, not 24,000"

    def test_an_unknown_chart_is_refused_by_name_and_never_falls_back_to_hourly(self, gw) -> None:
        """THE ONE OUTCOME THAT MUST NOT DEGRADE GRACEFULLY. Falling back to H1 here is exactly
        the defect the whole change removes, arriving through the error path instead."""
        gw, (tf, const, bars) = self._chart("W1", gw)
        assert tf == "W1"
        assert const is None and bars == 0
