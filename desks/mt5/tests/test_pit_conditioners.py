"""Per-symbol PIT conditioners, the residual factor on the forward clock, and the state lake's
clock (2026-10-06). Every test here fails on LIVE, where none of these exist."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research"), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import cell_modifiers as cm  # noqa: E402
from mt5desk.engine import Signal  # noqa: E402

T0 = pd.Timestamp("2026-03-02", tz="UTC")


def _sig(t: pd.Timestamp) -> Signal:
    return Signal(time=t, side=1, stop=99.0, target=102.0, ttl_bars=5, tag="t")


def _pit_file(tmp_path: Path, rows: list[dict[str, Any]]) -> Path:
    p = tmp_path / "pit.parquet"
    pd.DataFrame(rows).to_parquet(p, index=False)
    return p


def _row(axis: str, key: str, at: pd.Timestamp, pressed: bool, cadence_d: float) -> dict:
    return {"axis": axis, "key": key, "knowable_at": at,
            "stale_after": at + pd.Timedelta(days=cadence_d) + cm.STATE_MAX_AGE,
            "value": 1.0, "pressed": pressed}


def test_the_conditioner_names_axis_and_symbol() -> None:
    assert cm.pit_conditioner("pit:positioning:eurusd") == ("positioning", "EURUSD")
    assert cm.pit_conditioner("pit:macro:EURUSD") is None          # a global axis, not per-symbol
    assert cm.pit_conditioner("positioning") is None
    assert cm.pit_key("event", "EURUSD") == "USD" and cm.pit_key("event", "EURJPY") is None
    assert cm.pit_key("cross_asset", "XAGUSD") == "gold"
    assert cm.pit_key("cross_asset", "XAUUSD") == "usd"
    assert cm.pit_key("cross_asset", "EURGBP") == "equity"


def test_a_pressed_fresh_row_keeps_and_a_stale_or_quiet_row_drops(tmp_path, monkeypatch) -> None:
    rows = [_row("positioning", "EURUSD", T0, True, 7.0),
            _row("positioning", "EURUSD", T0 + pd.Timedelta(days=7), False, 7.0)]
    monkeypatch.setattr(cm, "PIT_FILE", _pit_file(tmp_path, rows))
    mods = {"conditioner": "pit:positioning:EURUSD"}
    assert cm.refusal(mods) is None
    before = _sig(T0 - pd.Timedelta(hours=1))                  # nothing known yet
    pressed = _sig(T0 + pd.Timedelta(days=3))
    quiet = _sig(T0 + pd.Timedelta(days=8))
    stale = _sig(T0 + pd.Timedelta(days=7 + 7 + 5))            # past cadence + 4 days
    kept = cm.apply([before, pressed, quiet, stale], pd.DataFrame(), mods)
    assert [s.time for s in kept] == [pressed.time]


def test_a_symbol_with_no_series_is_refused_unmeasured_by_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cm, "PIT_FILE", _pit_file(tmp_path, [_row("carry", "EURUSD", T0, True,
                                                                  1.0)]))
    assert "UNMEASURED" in cm.refusal({"conditioner": "pit:carry:XAUUSD"})
    assert "UNMEASURED" in cm.refusal({"conditioner": "pit:event:EURJPY"})
    monkeypatch.setattr(cm, "PIT_FILE", tmp_path / "absent.parquet")
    assert "not on this box" in cm.refusal({"conditioner": "pit:carry:EURUSD"})


def test_positioning_uses_the_family_s_own_window_and_tails(tmp_path, monkeypatch) -> None:
    import pit_conditioners as pc

    weeks = pd.date_range("2020-01-04", periods=200, freq="7D", tz="UTC")
    vals = np.r_[np.linspace(-0.1, 0.1, 199), 0.5]             # the last reading is extreme
    axes = tmp_path / "axes"
    axes.mkdir()
    (axes / "cot.json").write_text(json.dumps({"rows": [
        {"symbol": "EURUSD", "knowable_at": str(w.date()), "net_pct_oi": float(v)}
        for w, v in zip(weeks, vals, strict=True)]}), "utf-8")
    monkeypatch.setattr(pc, "AXES_DIR", axes)
    monkeypatch.setattr(pc, "SINCE", pd.Timestamp("2019-01-01", tz="UTC"))
    got, meta = pc.positioning()
    frame = got[0]
    assert meta["state"] == "OK" and "156w" in meta["rule"]
    assert bool(frame["pressed"].iloc[-1]) and frame["value"].iloc[-1] == 1.0
    assert (frame["stale_after"] - frame["knowable_at"]).iloc[0] == pd.Timedelta(days=11)


def test_event_rows_stop_at_the_calendar_s_declared_end(tmp_path, monkeypatch) -> None:
    import pit_conditioners as pc

    cal = tmp_path / "event_calendar.json"
    cal.write_text(json.dumps({"valid_through": "2026-03-31", "events": [
        {"utc": "2026-03-18T18:00:00Z", "impact": "high", "name": "FOMC decision"}]}), "utf-8")
    monkeypatch.setattr(pc, "EVENT_CALENDAR", cal)
    got, meta = pc.event()
    rows = got[0]
    assert meta["keys"] == ["USD"]
    hot = rows[rows["pressed"]]["knowable_at"].dt.date.astype(str).tolist()
    assert hot == ["2026-03-18", "2026-03-19"]
    assert rows["stale_after"].max() <= pd.Timestamp("2026-04-01", tz="UTC")


def test_cross_asset_falls_back_to_the_dollar_basket_and_names_it(tmp_path, monkeypatch) -> None:
    import pit_conditioners as pc

    uni = tmp_path / "universe"
    uni.mkdir()
    idx = pd.date_range("2024-01-01", periods=24 * 600, freq="h", tz="UTC")
    rng = np.random.default_rng(3)
    for sym, _sign in pc.USD_BASKET[:5]:
        c = np.exp(np.cumsum(rng.normal(0, 0.001, len(idx))))
        pd.DataFrame({"close": c}, index=idx).to_parquet(uni / f"{sym}_H1.parquet")
    monkeypatch.setattr(pc, "UNIVERSE_DIR", uni)
    got, meta = pc.cross_asset()
    assert [str(f["key"].iloc[0]) for f in got] == ["usd"]
    assert "basket of 5 majors" in meta["sources"]["usd"]
    assert "absent" in meta["sources"]["gold"] and "absent" in meta["sources"]["equity"]


def test_the_forward_inputs_carry_the_residual_factor_only_where_the_family_needs_it(
        monkeypatch) -> None:
    from mt5desk import family_inputs

    frame = pd.DataFrame({"close": [1.0, 2.0]},
                         index=pd.date_range("2026-01-01", periods=2, freq="h", tz="UTC"))
    monkeypatch.setattr(family_inputs, "_runtime_bars",
                        lambda _i, sym, _tf, _p: frame if sym == "USDX" else None)
    extra, why = family_inputs.resolve("EURUSD", "trend_ma_cross", {"residual": "usd"}, frame)
    assert why == "ok" and extra["residual_factor_bars"] is frame
    gone, why = family_inputs.resolve("EURUSD", "trend_ma_cross", {"residual": "equity"}, frame)
    assert gone is None and "US500" in why                     # a gap, never an un-residualised run
    plain, _ = family_inputs.resolve("EURUSD", "trend_ma_cross", {}, frame)
    assert "residual_factor_bars" not in (plain or {})


def test_free_shadows_refuses_to_publish_zeros_for_an_absent_fred_input(tmp_path,
                                                                        monkeypatch) -> None:
    import free_shadows as fs

    empty = fs.load_fred("NOT_A_SERIES_ON_DISK")
    assert empty.empty and str(empty.index.tz) == "UTC"
    src = Path(fs.__file__).read_text("utf-8")
    assert "NOT rebuilt (UNMEASURED past its last bar)" in src


def test_fred_writes_where_free_shadows_reads() -> None:
    import fetch_fred
    import free_shadows

    assert fetch_fred.OUT == free_shadows.LAKE
    assert "dell" not in str(fetch_fred.OUT).lower()


def test_the_state_lake_runs_every_due_step_and_one_failure_stops_none(tmp_path,
                                                                     monkeypatch) -> None:
    import state_lake_refresh as slr

    monkeypatch.setattr(slr, "REPORT", tmp_path / "STATE_LAKE.json")
    monkeypatch.setattr(slr, "free_states_end", lambda path=None: None)
    calls: list[str] = []

    def boom() -> None:
        calls.append("a")
        raise RuntimeError("publisher 403")

    steps = (("a", boom, 86400.0), ("b", lambda: calls.append("b"), 0.0))
    doc = slr.run(steps=steps, state_path=tmp_path / "s.json")
    assert calls == ["a", "b"] and doc["failing"] == ["a"]
    assert "publisher 403" in doc["steps"]["a"]["why"]
    # A failed daily step is retried next pass (no success recorded); a success is not.
    slr.run(steps=steps, state_path=tmp_path / "s.json")
    assert calls == ["a", "b", "a", "b"]
    ok = (("c", lambda: calls.append("c"), 86400.0),)
    slr.run(steps=ok, state_path=tmp_path / "s.json")
    slr.run(steps=ok, state_path=tmp_path / "s.json")
    assert calls.count("c") == 1


def test_the_state_lake_is_on_the_hourly_organ_battery() -> None:
    import batteries

    assert "desks/mt5/research/state_lake_refresh.py" in {
        e.path for e in batteries.ROSTERS["organs"]}


@pytest.mark.parametrize("axis", sorted(cm.PIT_AXES))
def test_every_pit_axis_has_a_builder(axis: str) -> None:
    import pit_conditioners as pc

    assert axis in pc.BUILDERS
