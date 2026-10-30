"""Every certificate's forward clock either accrues or names, as one enum, why it does not.

Pins the diagnostic (`research/clock_accrual.py`) and the causes it found, each fixed in the organ
that owns it:

  * warmup starvation   -- `shadow_forward.FETCH_DAYS` was 45; the MT5 route returns exactly
                           that range and `family_clock_transition` needs sixty days of bars;
  * coverage of the warmup's first instant -- a broker reply for gold opens at 01:00 and never
                           "covered" a midnight start (`h1_source.fetch_h1(cover_from=...)`);
  * a flat six-hour staleness rule on D1 bars stamped at their open (`Bars.covers(per_chart=)`);
  * a family with no constructor skipped WITHOUT writing the row;
  * scalp and qquant clocks keyed differently from the H1 key everyone derived for them.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import clock_accrual as ca  # noqa: E402
import shadow_forward  # noqa: E402

from research import h1_source  # noqa: E402

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
FRESH = (NOW - timedelta(minutes=10)).isoformat()


def _run(**kw: Any) -> dict[str, Any]:
    base = {"certificate": "external.EURUSD.x", "symbol": "EURUSD",
            "family": "session_range_breakout", "selector": "asia", "params": {},
            "side": "LONG"}
    base.update(kw)
    return base


def _judge(row: dict[str, Any] | None, *, run: dict[str, Any] | None = None,
           lane_rows: dict[str, Any] | None = None, host_live: bool = True,
           lane_age_h: float | None = 0.1) -> dict[str, Any]:
    r = run or _run()
    lane, key = ca.clock_address(r)
    lmap = dict(lane_rows or {})
    if row is not None:
        lmap[key] = row
    return ca.judge(r, lane, key, row, lmap, ref=NOW, lane_age_h=lane_age_h,
                    host_live=host_live, gaps={}, universe={"EURUSD", "XAUUSD"})


# ---------------------------------------------------------------- one reason per certificate
def test_a_clock_with_forward_observations_is_accruing() -> None:
    e = _judge({"status": "ACTIVE", "n": 3, "last_attempt_at": FRESH,
                "last_entry": "2026-09-29T10:00:00+00:00",
                "forward_start": "2026-09-01T00:00:00+00:00"})
    assert e["reason"] == ca.ACCRUING and e["accruing"] is True
    assert e["enrolled"] is True and e["n"] == 3 and e["last_attempt_at"] == FRESH


def test_a_young_clock_with_no_observation_is_warming_not_stuck() -> None:
    e = _judge({"status": "ACTIVE", "n": 0, "last_attempt_at": FRESH,
                "forward_start": (NOW - timedelta(hours=5)).isoformat()})
    assert e["reason"] == ca.WARMING and e["accruing"] is True


def test_an_old_silent_clock_names_whether_its_gate_ever_opened() -> None:
    old = (NOW - timedelta(days=10)).isoformat()
    never = _judge({"status": "ACTIVE", "n": 0, "n_historical": 0, "last_attempt_at": FRESH,
                    "forward_start": old})
    assert never["reason"] == ca.GATE_NEVER_OPENS and never["accruing"] is False
    quiet = _judge({"status": "ACTIVE", "n": 0, "n_historical": 7, "last_attempt_at": FRESH,
                    "forward_start": old})
    assert quiet["reason"] == ca.NO_SIGNAL_SINCE_FORWARD_START


def test_no_bars_splits_on_whether_the_chart_file_exists(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ca, "UNIVERSE", tmp_path)
    row = {"status": "BLOCKED_NO_BARS", "n": 0, "last_attempt_at": FRESH}
    missing = _judge(dict(row))
    assert missing["reason"] == ca.BAR_FILE_MISSING
    assert missing["bars_wanted"] == {"symbol": "EURUSD", "timeframe": "H1"}
    (tmp_path / "EURUSD_H1.parquet").write_bytes(b"x")
    assert _judge(dict(row))["reason"] == ca.NO_BARS


def test_a_row_the_pass_never_reached_is_engine_not_reached() -> None:
    stale = (NOW - timedelta(hours=9)).isoformat()
    e = _judge({"status": "ACTIVE", "n": 4, "last_attempt_at": stale})
    assert e["reason"] == ca.ENGINE_NOT_REACHED
    assert _judge({"status": "ACTIVE", "n": 4})["reason"] == ca.ENGINE_NOT_REACHED


def test_a_silent_lane_convicts_only_on_a_host_that_runs_clocks() -> None:
    row = {"status": "ACTIVE", "n": 4, "last_attempt_at": FRESH}
    assert _judge(dict(row), host_live=True, lane_age_h=40.0)["reason"] == ca.ENGINE_NOT_REACHED
    assert _judge(dict(row), host_live=False, lane_age_h=40.0)["reason"] == ca.ACCRUING


def test_status_blockers_map_to_named_reasons() -> None:
    cases = {"BLOCKED_INPUTS_UNAVAILABLE": ca.INPUTS_UNAVAILABLE,
             "BLOCKED_FAMILY_UNBUILDABLE": ca.FAMILY_UNBUILDABLE,
             "BLOCKED_SLEEVE_ERROR": ca.ENGINE_ERROR, "IDENTITY_BROKEN": ca.IDENTITY_BROKEN,
             "QUARANTINED_FORWARD_CLOCK_BREACH": ca.QUARANTINED,
             "RETIRED_ORPHAN": ca.RETIRED_WHILE_CERTIFIED,
             "REFUSED_BY_UNIVERSE_POLICY": ca.UNIVERSE_POLICY_REFUSED,
             "KILL": ca.DECIDED, "SOMETHING_NEW": ca.BLOCKED_UNNAMED}
    for status, reason in cases.items():
        e = _judge({"status": status, "n": 0, "last_attempt_at": FRESH})
        assert e["reason"] == reason, status
        assert e["reason"] in ca.REASONS


def test_no_row_is_not_enrolled_or_a_key_mismatch() -> None:
    e = _judge(None)
    assert e["reason"] == ca.NOT_ENROLLED and e["enrolled"] is False
    run = _run(params={"rr": 1.5})
    near = {"EURUSD.asia#rr=2.5": {"status": "ACTIVE", "n": 1}}
    e = _judge(None, run=run, lane_rows=near)
    assert e["reason"] == ca.KEY_MISMATCH and e["near_keys"] == ["EURUSD.asia#rr=2.5"]


def test_the_engines_own_gates_name_a_certificate_it_will_never_enrol() -> None:
    assert _judge(None, run=_run(selector="no_such_window"))["reason"] == ca.SELECTOR_UNMAPPED
    assert _judge(None, run=_run(family="no_such_family", selector="x"))["reason"] \
        == ca.FAMILY_UNBUILDABLE
    assert _judge(None, run=_run(family="discovered", selector="x"))["reason"] == ca.BANNED_FAMILY


# ---------------------------------------------------------------- where each lane keeps its clock
def test_each_lane_is_addressed_by_its_own_key() -> None:
    assert ca.clock_address({"certificate": "scalp.xau_m5_x", "lane": "scalp",
                             "selector": "xau_m5_x"}) == (ca.SCALP_LANE, "xau_m5_x")
    q = "qquant.hunt16.json.AUDNZD dav SHORT afternoon NORMAL_DAY"
    assert ca.clock_address({"certificate": q}) == (ca.QQUANT_LANE, q)
    lane, key = ca.clock_address(_run(family="carry", selector="continuous", side="SHORT"))
    assert lane == ca.H1_LANE and key == "EURUSD.carry.continuous.SHORT"


def test_the_scalp_lanes_nested_sleeves_are_read(tmp_path) -> None:
    (tmp_path / "scalp_shadow_state.json").write_text(json.dumps(
        {"updated_at": FRESH, "sleeves": {"xau_m5_x": {"status": "ACCUMULATING", "n": 5}}}),
        "utf-8")
    rows, meta = ca.lane_rows(tmp_path)
    assert rows[ca.SCALP_LANE] == {"xau_m5_x": {"status": "ACCUMULATING", "n": 5}}
    assert meta[ca.H1_LANE] == {"readable": False}


# ---------------------------------------------------------------- the artifact
def _write_lane(tmp_path: Path, rows: dict[str, Any]) -> None:
    (tmp_path / "shadow_state.json").write_text(
        json.dumps({"updated_at": FRESH, **rows}), "utf-8")


def test_headline_is_the_non_accruing_count_by_reason(tmp_path) -> None:
    runs = [_run(certificate="a", selector="asia"),
            _run(certificate="b", selector="london_am"),
            _run(certificate="c", selector="ny_open")]
    _write_lane(tmp_path, {
        "EURUSD.asia": {"status": "ACTIVE", "n": 2, "last_attempt_at": FRESH},
        "EURUSD.london_am": {"status": "BLOCKED_SLEEVE_ERROR", "n": 0,
                             "last_attempt_at": FRESH}})
    doc = ca.build(now=NOW, shadow_dir=tmp_path, runs=runs, dropped=[], host_live=True)
    h = doc["headline"]
    assert doc["status"] == "MEASURED"
    assert h["n_certificates"] == 3 and h["n_enrolled"] == 2 and h["n_accruing"] == 1
    assert h["non_accruing_by_reason"] == {ca.ENGINE_ERROR: 1, ca.NOT_ENROLLED: 1}
    assert h["n_non_accruing"] == 2
    for e in doc["certificates"]:
        assert {"enrolled", "last_attempt_at", "last_entry", "n", "reason"} <= set(e)


def test_an_unreadable_lane_is_unmeasured_never_zero(tmp_path) -> None:
    doc = ca.build(now=NOW, shadow_dir=tmp_path, runs=[_run()], dropped=[], host_live=True)
    assert doc["status"] == ca.UNMEASURED
    assert doc["headline"]["n_non_accruing"] == ca.UNMEASURED
    assert doc["certificates"][0]["reason"] == ca.UNMEASURED


def test_an_admission_drop_is_params_unresolved(tmp_path) -> None:
    _write_lane(tmp_path, {})
    doc = ca.build(now=NOW, shadow_dir=tmp_path, runs=[],
                   dropped=[{"certificate": "external.X", "why": "params is NoneType"}],
                   host_live=True)
    assert doc["headline"]["non_accruing_by_reason"] == {ca.PARAMS_UNRESOLVED: 1}


def test_bars_wanted_round_trips_to_the_collectors(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ca, "UNIVERSE", tmp_path / "universe")
    _write_lane(tmp_path, {"EURUSD.asia": {"status": "BLOCKED_NO_BARS", "n": 0,
                                           "last_attempt_at": FRESH}})
    doc = ca.build(now=NOW, shadow_dir=tmp_path, runs=[_run()], dropped=[], host_live=True)
    out = tmp_path / "CLOCK_ACCRUAL.json"
    ca.write(doc, out)
    assert ca.bars_wanted(out) == [("EURUSD", "H1")]
    assert ca.bars_wanted(tmp_path / "absent.json") == []


# ---------------------------------------------------------------- the causes, in their organs
def _bars(start: str, periods: int, freq: str) -> h1_source.Bars:
    idx = pd.date_range(start, periods=periods, freq=freq, tz="UTC")
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}, index=idx)
    return h1_source.Bars(df, "MT5:Test", "now")


def test_a_d1_series_is_not_stale_for_being_stamped_at_its_open() -> None:
    today = pd.Timestamp.now(tz="UTC").normalize()
    b = _bars(str((today - pd.Timedelta(days=199)).date()), 200, "D")
    start = (today - pd.Timedelta(days=100)).to_pydatetime()
    assert abs(b.bar_span_hours() - 24.0) < 1e-9
    assert b.stale_allowance_h(per_chart=False) == h1_source.STALE_AFTER_H
    assert b.stale_allowance_h(per_chart=True) == h1_source.STALE_AFTER_H + 24.0
    # The chart-aware rule accepts a D1 series whose freshest bar is today's open.
    assert b.covers(start, per_chart=True)[0]


def test_coverage_is_of_the_window_not_of_the_warmups_first_instant(monkeypatch) -> None:
    """A broker reply for gold opens at 01:00: it never covers a midnight warmup start."""
    start = datetime(2026, 7, 2, tzinfo=UTC)
    reply = _bars("2026-07-02 01:00", 24 * 90, "h")
    monkeypatch.setattr(h1_source, "from_mt5", lambda sym, s, tf="H1": reply)
    monkeypatch.setattr(h1_source, "from_cache", lambda sym, s, tf="H1": None)
    monkeypatch.setattr(h1_source, "EXTRA_SOURCES", [])
    end = reply.df.index.max().to_pydatetime()
    monkeypatch.setattr(h1_source, "trading_lag_hours", lambda last, e: 0.0)
    assert h1_source.fetch_h1("XAUUSD", start, require_coverage=True) is None
    got = h1_source.fetch_h1("XAUUSD", start, require_coverage=True,
                             cover_from=datetime(2026, 8, 16, tzinfo=UTC))
    assert got is reply and end > start


def test_the_engine_asks_for_a_warmup_longer_than_any_family_lookback(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake(sym, start, **kw):
        seen.update(kw, start=start)
        return None

    monkeypatch.setattr(h1_source, "fetch_h1", fake)
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)
    assert shadow_forward.fetch_h1("EURUSD", "D1") is None
    assert shadow_forward.FETCH_DAYS >= 365, "clock_transition alone needs sixty days of bars"
    assert seen["cover_from"] == shadow_forward.SHADOW_START
    assert seen["per_chart_staleness"] is True and seen["timeframe"] == "D1"
    assert seen["start"] <= shadow_forward.SHADOW_START - timedelta(days=365)


@dataclass
class _FakeBars:
    df: pd.DataFrame
    source: str = "MT5:Test"
    evidence_venue: str = "Test"
    stale: bool = False
    promotion_authority: bool = True

    def stamp(self) -> dict[str, Any]:
        return {"bar_source": self.source}


def test_an_unbuildable_family_writes_its_row_instead_of_vanishing(tmp_path, monkeypatch) -> None:
    universe = tmp_path / "universe"
    universe.mkdir()
    (universe / "universe.json").write_text("{}", "utf-8")
    shadow_dir = tmp_path / "shadow"
    shadow_dir.mkdir()
    idx = pd.date_range("2026-08-16", periods=48, freq="h", tz="UTC")
    bars = _FakeBars(pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0},
                                  index=idx))
    monkeypatch.setattr(shadow_forward, "UNI", universe)
    monkeypatch.setattr(shadow_forward, "SHADOW_DIR", shadow_dir)
    monkeypatch.setattr(shadow_forward, "SLEEVES", [])
    monkeypatch.setattr(shadow_forward, "certified_sleeves",
                        lambda: [("EURUSD", "continuous", {}, "carry", "LONG")])
    monkeypatch.setattr(shadow_forward, "fetch_h1", lambda sym, timeframe="H1": bars)
    monkeypatch.setattr(shadow_forward, "_family_fn", lambda fam: None)
    monkeypatch.setattr(shadow_forward, "slog", lambda *a: None)
    import sleeve_registry
    monkeypatch.setattr(sleeve_registry, "REGISTRY", tmp_path / "sleeve_registry.json")

    shadow_forward.main()

    row = json.loads((shadow_dir / "shadow_state.json").read_text("utf-8"))[
        "EURUSD.carry.continuous"]
    assert row["status"] == "BLOCKED_FAMILY_UNBUILDABLE"
    assert row["last_attempt_at"] and "carry" in row["last_error"]
    lane, key = ca.clock_address(_run(family="carry", selector="continuous"))
    e = ca.judge(_run(family="carry", selector="continuous"), lane, key, row, {key: row},
                 ref=NOW, lane_age_h=0.0, host_live=False, gaps={}, universe=None)
    assert e["reason"] == ca.FAMILY_UNBUILDABLE
