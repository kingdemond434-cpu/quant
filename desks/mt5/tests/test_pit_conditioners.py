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


_USABLE_FEED = {"status": "FRESH", "usable": True, "why": "captured 1.0h ago"}


def _swap_fixture(tmp_path: Path, monkeypatch: Any, *, mode: int, long_: float,
                  short: float, bis_rows: list[dict] | None = None,
                  feed: dict | None = None, caps: list[dict] | None = None) -> Any:
    import pit_conditioners as pc

    from research import carry_state

    monkeypatch.setattr(carry_state, "swap_feed", lambda *a, **k: dict(feed or _USABLE_FEED))
    swaps = tmp_path / "broker_swaps"
    swaps.mkdir()
    caps = caps if caps is not None else [
        {"kind": "swap_table", "symbols": ["XAUUSD"], "swap_long": long_,
         "swap_short": short, "found_at": f"2026-08-{d:02d}T06:00:00+00:00"}
        for d in (26, 27)]
    (swaps / "discoveries_20260827_0600.json").write_text(json.dumps(caps), "utf-8")
    (tmp_path / "carry_state.json").write_text(json.dumps(
        {"symbols": {"XAUUSD": {"swap_mode": mode}}}), "utf-8")
    uni = tmp_path / "universe"
    uni.mkdir()
    (uni / "universe.json").write_text(json.dumps({"XAUUSD": {"tick_size": 0.01}}), "utf-8")
    idx = pd.date_range("2026-08-20", "2026-08-28", freq="h", tz="UTC")
    pd.DataFrame({"close": 2600.0}, index=idx).to_parquet(uni / "XAUUSD_H1.parquet")
    axes = tmp_path / "axes"
    axes.mkdir()
    (axes / "bis.json").write_text(json.dumps({"rows": bis_rows or []}), "utf-8")
    for name, val in (("SWAP_DIR", swaps), ("CARRY_STATE", tmp_path / "carry_state.json"),
                      ("UNIVERSE_DIR", uni), ("UNIVERSE_JSON", uni / "universe.json"),
                      ("AXES_DIR", axes),
                      ("SINCE", pd.Timestamp("2026-01-01", tz="UTC"))):
        monkeypatch.setattr(pc, name, val)
    return pc


def test_xauusd_carry_is_the_broker_swap_the_desk_actually_pays(tmp_path, monkeypatch) -> None:
    """The 44 XAUUSD carry refusals: no policy-rate pair speaks for gold, the broker's swap does.
    POINTS mode: (long - short) / 2 * tick / price, annualised -- PER SIDE, the BIS rows' unit;
    knowable at the capture's found_at."""
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45)
    got, meta = pc.carry()
    rows = next(f for f in got if f["key"].iloc[0] == "XAUUSD")
    assert set(rows["source"]) == {"broker_swap"}
    want = (-61.76 - 29.45) / 2.0 * 0.01 / 2600.0 * 365.0 * 100.0
    assert rows["value"].iloc[0] == pytest.approx(want)
    assert bool(rows["pressed"].iloc[0])                       # |-6.4% p.a.| >= 1.825%
    assert rows["knowable_at"].iloc[0] == pd.Timestamp("2026-08-26T06:00:00Z")
    assert rows["stale_after"].iloc[0] == pd.Timestamp("2026-08-31T06:00:00Z")
    assert meta["n_keys_broker_swap"] == 1


def test_an_interest_mode_swap_is_already_annual_percent(tmp_path, monkeypatch) -> None:
    pc = _swap_fixture(tmp_path, monkeypatch, mode=5, long_=-1.0, short=0.5)
    rows = next(f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD")
    assert rows["value"].iloc[0] == pytest.approx(-0.75)       # (long - short) / 2, per side
    assert not bool(rows["pressed"].iloc[0])                   # below the 1.825% floor


def test_the_broker_swap_carry_is_per_side_like_the_bis_differential(tmp_path,
                                                                     monkeypatch) -> None:
    """Long is paid ~(r_b - r_q) - markup, short ~(r_q - r_b) - markup: long - short is TWICE
    the differential. Halved, a broker key and a BIS key carry the same number for one rate gap:
    a 3% differential with a 0.25% markup each side reads 3.0, not 6.0."""
    pc = _swap_fixture(tmp_path, monkeypatch, mode=5, long_=3.0 - 0.25, short=-3.0 - 0.25)
    rows = next(f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD")
    assert rows["value"].iloc[0] == pytest.approx(3.0)


def test_an_unknown_swap_unit_is_unmeasured_by_name(tmp_path, monkeypatch) -> None:
    pc = _swap_fixture(tmp_path, monkeypatch, mode=7, long_=-1.0, short=0.5)
    got, meta = pc.carry()
    assert not got and meta["state"] == "UNMEASURED"
    assert "unit not established" in meta["unmeasured"]["XAUUSD"]


def test_the_policy_rate_differential_wins_where_bis_has_the_pair(tmp_path, monkeypatch) -> None:
    bis = [{"symbol": "XAUUSD", "knowable_at": "2026-08-25", "carry_differential": 3.0}]
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45, bis_rows=bis)
    rows = [f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD"]
    assert len(rows) == 1 and set(rows[0]["source"]) == {"bis_policy_rates"}


def test_a_broker_swap_carry_cell_is_applied_not_refused(tmp_path, monkeypatch) -> None:
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45)
    out = tmp_path / "pit.parquet"
    pd.concat(pc.carry()[0]).to_parquet(out, index=False)
    monkeypatch.setattr(cm, "PIT_FILE", out)
    mods = {"conditioner": "pit:carry:XAUUSD"}
    assert cm.refusal(mods) is None
    inside = _sig(pd.Timestamp("2026-08-28T00:00:00Z"))
    before = _sig(pd.Timestamp("2026-08-25T00:00:00Z"))       # before the first capture
    assert [s.time for s in cm.apply([before, inside], pd.DataFrame(), mods)] == [inside.time]


def test_an_unusable_swap_feed_clips_freshness_and_keeps_the_history(tmp_path,
                                                                     monkeypatch) -> None:
    """#244's gate, clipped not dropped: a dead feed keeps every capture on its own dates, but no
    row is fresh past the feed's last live capture -- and `_feed` says so by name."""
    dead = {"status": "STALE", "usable": False, "why": "captured 40.0h ago (stale past 26h)",
            "last_capture_at": "2026-08-27T06:00:00+00:00"}
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45, feed=dead)
    swaps, smeta = pc.swap_carry(None)
    assert len(swaps) == 1 and smeta["clip_at"] == pd.Timestamp("2026-08-27T06:00:00Z")
    assert smeta["unmeasured"]["_feed"].startswith("STALE")
    got, meta = pc.carry()
    rows = next(f for f in got if f["key"].iloc[0] == "XAUUSD")
    assert len(rows) == 2                                       # the history stands
    assert rows["stale_after"].max() == pd.Timestamp("2026-08-27T06:00:00Z")
    assert meta["unmeasured"]["_feed"].startswith("STALE")
    assert _carry_cell_keeps(pc, tmp_path, monkeypatch, "2026-08-26T12:00:00Z")
    assert not _carry_cell_keeps(pc, tmp_path, monkeypatch, "2026-08-28T00:00:00Z")


def test_a_feed_with_no_capture_time_clips_at_the_newest_capture_on_disk(tmp_path,
                                                                        monkeypatch) -> None:
    dead = {"status": "MISSING", "usable": False, "why": "no box capture has ever been recorded"}
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45, feed=dead)
    rows = next(f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD")
    assert rows["stale_after"].max() == pd.Timestamp("2026-08-27T06:00:00Z")


def _one_cap(evidence: str | None) -> list[dict]:
    row = {"kind": "swap_table", "symbols": ["XAUUSD"], "swap_long": -61.76,
           "swap_short": 29.45, "found_at": "2026-08-21T06:00:00+00:00"}
    return [{**row, "last_evidence_at": evidence}] if evidence else [row]


def _carry_cell_keeps(pc: Any, tmp_path: Path, monkeypatch: Any, at: str) -> bool:
    out = tmp_path / "pit.parquet"
    pd.concat(pc.carry()[0]).to_parquet(out, index=False)
    monkeypatch.setattr(cm, "PIT_FILE", out)
    sig = _sig(pd.Timestamp(at))
    return [s.time for s in cm.apply([sig], pd.DataFrame(), {"conditioner": "pit:carry:XAUUSD"})
            ] == [sig.time]


def test_last_evidence_keeps_an_unchanged_swap_fresh_past_the_stale_window(
        tmp_path, monkeypatch) -> None:
    """found_at 08-21 alone is stale after 08-26 (1d cadence + 4d); evidence on 08-27 is a second
    knowable point at the evidence time, so 08-28 is still inside the window."""
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45,
                       caps=_one_cap("2026-08-27T05:00:00"))
    rows = next(f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD")
    assert list(rows["knowable_at"]) == [pd.Timestamp("2026-08-21T06:00:00Z"),
                                         pd.Timestamp("2026-08-27T05:00:00Z")]
    assert _carry_cell_keeps(pc, tmp_path, monkeypatch, "2026-08-28T00:00:00Z")


def test_without_evidence_an_unchanged_swap_goes_stale(tmp_path, monkeypatch) -> None:
    pc = _swap_fixture(tmp_path, monkeypatch, mode=1, long_=-61.76, short=29.45,
                       caps=_one_cap(None))
    rows = next(f for f in pc.carry()[0] if f["key"].iloc[0] == "XAUUSD")
    assert list(rows["stale_after"]) == [pd.Timestamp("2026-08-26T06:00:00Z")]
    assert not _carry_cell_keeps(pc, tmp_path, monkeypatch, "2026-08-28T00:00:00Z")


# --- second audit of #222 (2026-10-07): FRED fetch failure, FRED forward-fill staleness ---------


def _fred_fixture(tmp_path: Path, monkeypatch: Any, fail: set[str],
                  empty: frozenset[str] | set[str] = frozenset()) -> Any:
    import fetch_fred

    monkeypatch.setattr(fetch_fred, "OUT", tmp_path)

    def fake(sid: str) -> pd.DataFrame:
        if sid in fail:
            raise OSError(f"403 for {sid}")
        if sid in empty:
            return pd.DataFrame({sid: pd.Series(dtype=float)})
        return pd.DataFrame({sid: [1.0, 2.0]},
                            index=pd.DatetimeIndex(["2026-10-01", "2026-10-02"], tz="UTC"))

    monkeypatch.setattr(fetch_fred, "fetch", fake)
    return fetch_fred


def test_a_total_fred_fetch_failure_raises_and_is_recorded_failed(tmp_path, monkeypatch) -> None:
    import fetch_fred
    import state_lake_refresh as slr

    first, *rest = list(fetch_fred.SERIES)
    ff = _fred_fixture(tmp_path, monkeypatch, fail=set(rest), empty={first})
    with pytest.raises(ff.FredFetchFailed):
        ff.main()
    state = json.loads((tmp_path / "fred_fetch_state.json").read_text("utf-8"))
    assert state["status"] == "FAILED" and state["n_ok"] == 0       # an empty frame is a failure
    assert not list(tmp_path.glob("fred_*.parquet"))                 # nothing written, nothing lost
    # ... and the state lake driver records the step FAILED, so it is retried next pass.
    monkeypatch.setattr(slr, "REPORT", tmp_path / "STATE_LAKE.json")
    monkeypatch.setattr(slr, "free_states_end", lambda path=None: None)
    doc = slr.run(steps=(("fetch_fred", ff.main, 86400.0),), state_path=tmp_path / "s.json")
    assert doc["failing"] == ["fetch_fred"]
    assert "FredFetchFailed" in doc["steps"]["fetch_fred"]["why"]


def test_a_partial_fred_fetch_names_its_failures(tmp_path, monkeypatch) -> None:
    ff = _fred_fixture(tmp_path, monkeypatch, fail={"DGS2"})
    assert ff.main() == 0
    state = json.loads((tmp_path / "fred_fetch_state.json").read_text("utf-8"))
    assert state["status"] == "PARTIAL" and state["failed"] == ["DGS2"]
    assert state["n_ok"] == len(ff.SERIES) - 1


def test_the_state_lake_records_a_nonzero_return_as_failed(tmp_path, monkeypatch) -> None:
    import state_lake_refresh as slr

    monkeypatch.setattr(slr, "REPORT", tmp_path / "STATE_LAKE.json")
    monkeypatch.setattr(slr, "free_states_end", lambda path=None: None)
    doc = slr.run(steps=(("pit", lambda: 1, 0.0), ("ok", lambda: 0, 0.0),
                         ("none", lambda: None, 0.0)), state_path=tmp_path / "s.json")
    assert doc["failing"] == ["pit"] and "exit code 1" in doc["steps"]["pit"]["why"]


@pytest.mark.parametrize(("sid", "days"), [("VIXCLS", 5), ("DGS2", 5), ("WALCL", 17),
                                           ("PCOPPUSDM", 65), ("IR3TIB01JPM156N", 65)])
def test_the_fred_staleness_cap_is_two_release_periods_plus_a_weekend(sid: str, days: int) -> None:
    import free_shadows as fs

    assert fs.fred_max_staleness(sid) == pd.Timedelta(days=days)


def test_a_fred_value_past_its_cap_is_unmeasured_not_restated() -> None:
    import free_shadows as fs

    idx = pd.date_range("2026-01-01", "2026-02-15", freq="h", tz="UTC").as_unit("ms")
    sr = pd.Series([1.0, 2.0, 3.0],
                   index=pd.DatetimeIndex(["2026-01-05", "2026-01-06", "2026-01-07"], tz="UTC"))
    vix = fs.ff_daily(sr, idx, "VIXCLS")
    # 01-07 is known 01-08 03:00 (the declared 27h lag) and carried five days, to 01-13 03:00.
    assert vix.last_valid_index() == pd.Timestamp("2026-01-13T03:00:00Z")
    assert vix[pd.Timestamp("2026-01-13T03:00:00Z")] == 3.0
    assert np.isnan(vix[pd.Timestamp("2026-01-13T04:00:00Z")])
    assert bool(fs.stopped(vix)[pd.Timestamp("2026-02-01T00:00:00Z")])
    assert not bool(fs.stopped(vix)[pd.Timestamp("2026-01-02T00:00:00Z")])  # warm-up, not stopped
    # A broker price series (no FRED id) keeps its plain forward-fill.
    assert fs.ff_daily(sr, idx).last_valid_index() == idx[-1]


def test_a_nan_state_bar_keeps_no_signal(tmp_path, monkeypatch) -> None:
    """free_shadows writes NaN where an input stopped; the conditioner must not step back over it
    to the last measured bar."""
    idx = pd.date_range("2026-03-02", periods=48, freq="h", tz="UTC")
    vals = np.where(np.arange(48) < 24, 1.0, np.nan)
    p = tmp_path / "free_states.parquet"
    pd.DataFrame({"gold_risk_off_z": vals}, index=idx).to_parquet(p)
    monkeypatch.setattr(cm, "STATE_FILE", p)
    early, late = _sig(idx[10]), _sig(idx[30])
    kept = cm.apply([early, late], pd.DataFrame(), {"regime": "risk_off"})
    assert [s.time for s in kept] == [early.time]
