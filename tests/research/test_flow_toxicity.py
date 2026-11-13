"""Tick-tape flow, toxicity, impact and spread regime: arithmetic, point-in-time, accumulation,
and the door to the judge.

THE PROPERTIES THAT MAKE THE SERIES WORTH CONDITIONING ON:

    THE TICK TEST CARRIES A ZERO TICK, which is what separates it from the sign-of-mid flow the
    tape families already read.
    NOTHING IS SCALED BY THE FUTURE: a BVC bucket's z uses earlier buckets only, and every derived
    column at bar t is unchanged when later bars are cut off.
    THE SERIES OUTLIVES THE TAPE: a day file archived off the box leaves its bars in the series.
    THE CELLS ARE THE JUDGE'S OWN: they name a registered family, lag a full broker offset, and
    point at the lake file the judge rebuilds them from.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "desks" / "mt5"
for _p in (str(_ROOT), str(_DESK), str(_DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mt5desk import flow_toxicity as ft  # noqa: E402

from research import flow_toxicity_miner as ftm  # noqa: E402

POINT = 1e-5


def _ticks(n: int = 40_000, seed: int = 0, start: str = "2026-10-05",
           step_s: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=n, freq=pd.Timedelta(seconds=step_s), tz="UTC")
    moves = rng.choice([-1, 0, 1], n, p=[0.3, 0.4, 0.3])
    mid = 1.1 + np.cumsum(moves) * POINT
    sp = np.where(rng.random(n) < 0.5, 1, 2) * POINT
    return pd.DataFrame({"ts": ts, "bid": mid - sp / 2, "ask": mid + sp / 2})


# ----------------------------------------------------------------------------- arithmetic
def test_the_tick_test_carries_a_zero_tick() -> None:
    sign, moved = ft.tick_rule_signs(np.array([1.0, 1.0, 2.0, 2.0, 2.0, 1.0, 1.0]))
    assert sign.tolist() == [0.0, 0.0, 1.0, 1.0, 1.0, -1.0, -1.0]
    assert moved.tolist() == [False, False, True, False, False, True, False]


def test_bvc_scales_each_bucket_by_earlier_buckets_only() -> None:
    mid = 1.0 + np.cumsum(np.random.default_rng(1).normal(0, 1e-5, 5_000))
    oi, ends = ft.bvc_buckets(mid, 20)
    assert np.isnan(oi[: ft.BVC_MIN_SIGMA_BUCKETS]).all()
    bumped = mid.copy()
    bumped[-500:] += 0.01                      # a future shock
    oi2, _ = ft.bvc_buckets(bumped, 20)
    k = (len(mid) - 500) // 20 - 1
    np.testing.assert_allclose(oi[:k], oi2[:k], equal_nan=True)
    assert np.nanmin(oi) >= 0.0 and np.nanmax(oi) <= 1.0
    assert (ends[1:] - ends[:-1] == 20).all()


def test_kyle_lambda_recovers_one_point_per_unit_flow() -> None:
    agg = ft.bar_aggregates(_ticks(200_000), POINT, bucket_ticks=200)
    der = ft.derive(agg, POINT)
    lam = der["kyle_lambda"].dropna()
    assert len(lam) > 0
    np.testing.assert_allclose(lam.to_numpy(), 1.0, atol=0.02)
    assert set(ft.SIGNAL_COLUMNS) <= set(der.columns)
    assert (der["quote_imbalance_basis"] == "sign_only").all()


def test_a_thin_bar_states_no_number() -> None:
    t = _ticks(4_000, step_s=1.0)
    thin = t.iloc[::200]                       # ~20 ticks per hour, under MIN_TICKS_BAR
    der = ft.derive(ft.bar_aggregates(thin, POINT), POINT)
    assert der[list(ft.SIGNAL_COLUMNS)].isna().all().all()


def test_derived_columns_never_look_ahead() -> None:
    agg = ft.bar_aggregates(_ticks(200_000, seed=3), POINT, bucket_ticks=200)
    full = ft.derive(agg, POINT)
    cut = ft.derive(agg.iloc[:30], POINT)
    cols = list(ft.SIGNAL_COLUMNS)
    pd.testing.assert_frame_equal(full[cols].iloc[:30], cut[cols], check_freq=False)
    assert (full["available_time"] - full.index == pd.Timedelta("1h")).all()


def test_aggregates_merge_replaces_only_the_bars_recomputed() -> None:
    a = ft.bar_aggregates(_ticks(20_000, seed=4), POINT)
    b = ft.bar_aggregates(_ticks(20_000, seed=5, start="2026-10-05 03:00"), POINT)
    m = ft.merge_aggregates(a, b)
    assert m.index.is_monotonic_increasing and not m.index.duplicated().any()
    pd.testing.assert_frame_equal(m.loc[b.index], b, check_freq=False)
    keep = a.index[~a.index.isin(b.index)]
    pd.testing.assert_frame_equal(m.loc[keep], a.loc[keep], check_freq=False)


def test_the_unit_is_never_guessed() -> None:
    with pytest.raises(ValueError):
        ft.bar_aggregates(_ticks(100), 0.0)


# ----------------------------------------------------------------------------- the organ
def _write_day(root: Path, sym: str, day: str, seed: int, n: int = 30_000) -> None:
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    _ticks(n, seed=seed, start=day).to_parquet(d / f"{day}.parquet")


def test_the_series_accumulates_past_the_tape_window(tmp_path: Path) -> None:
    ticks, series = tmp_path / "ticks", tmp_path / "series"
    for i, day in enumerate(("2026-10-05", "2026-10-06", "2026-10-07")):
        _write_day(ticks, "EURUSD", day, seed=i)
    state: dict = {}
    r1 = ftm.accumulate("EURUSD", POINT, state, tick_root=ticks, series_root=series)
    assert r1["status"] == "MEASURED" and r1["days_folded"] == 3
    first = pd.read_parquet(series / "micro_EURUSD.parquet")
    # archive the oldest day off the box; add a new one
    (ticks / "EURUSD" / "2026-10-05.parquet").unlink()
    _write_day(ticks, "EURUSD", "2026-10-08", seed=9)
    r2 = ftm.accumulate("EURUSD", POINT, state, tick_root=ticks, series_root=series)
    # only the tail (newest two day files) is refolded, never the whole history
    assert r2["days_folded"] == 2
    second = pd.read_parquet(series / "micro_EURUSD.parquet")
    old_bars = first.index[first.index < pd.Timestamp("2026-10-06", tz="UTC")]
    assert len(old_bars) > 0 and old_bars.isin(second.index).all()
    assert second.index.max() > first.index.max()
    assert "available_time" in second.columns


def test_the_report_says_unmeasured_without_a_tape(tmp_path: Path) -> None:
    rep = ftm.run(tick_root=tmp_path / "none", series_root=tmp_path / "s",
                  report_path=tmp_path / "rep.json", probe_depth=False, propose_cells=False)
    assert rep["status"] == "UNMEASURED" and rep["why"]
    assert json.loads((tmp_path / "rep.json").read_text())["clock"] == "hourly_cycle:flow_toxicity"


def test_the_grid_names_registered_families_with_a_full_broker_lag() -> None:
    from mt5desk.families import get_family_func
    grid = ftm._grid("EURUSD")
    assert {f for f, _ in grid} == {"exogenous_conditioner", "alt_series_momentum"}
    for fam, params in grid:
        assert get_family_func(fam) is not None
        assert params["source"] == "micro_EURUSD"
        assert params["signal"] in ft.SIGNAL_COLUMNS
        assert params["lag_hours"] >= 3          # covers the +3h summer broker offset


def test_the_screen_rebuilds_cells_from_the_lake_file(tmp_path: Path) -> None:
    """The judge's own family reads the series this organ wrote, and the screen runs on it."""
    series = tmp_path / "series"
    rng = np.random.default_rng(7)
    idx = pd.date_range("2026-08-01", periods=1500, freq="1h", tz="UTC")
    close = 1.1 + np.cumsum(rng.normal(0, 5e-4, len(idx)))
    bars = pd.DataFrame({"open": close, "high": close + 4e-4, "low": close - 4e-4,
                         "close": close}, index=idx)
    sig = pd.Series(rng.normal(0, 1, len(idx)), index=idx)
    frame = pd.DataFrame({c: sig.to_numpy() for c in ft.SIGNAL_COLUMNS}, index=idx)
    frame["available_time"] = idx + pd.Timedelta("1h")
    series.mkdir()
    frame.to_parquet(series / "micro_EURUSD.parquet")
    rows = ftm.screen_symbol("EURUSD", bars, 1e-5, {}, series, idx[0])
    assert rows, "the judge's family produced no screenable signal from the lake file"
    assert all(r["params"]["source"] == "micro_EURUSD" for r in rows)
    assert all("oos_net_per_trade" in r and "pnl" not in r for r in rows)


def test_the_depth_probe_is_refreshed_or_named_unmeasured(tmp_path: Path) -> None:
    probe = tmp_path / "depth_probe.json"
    now = datetime.now(tz=UTC)
    probe.write_text(json.dumps({"at": now.isoformat(), "symbols": {"EURUSD": {}},
                                 "symbols_with_real_depth": []}))
    assert ftm.refresh_depth_probe(probe=probe)["status"] == "FRESH"
    probe.write_text(json.dumps({"at": (now - timedelta(days=30)).isoformat(), "symbols": {}}))

    def runner() -> int:
        probe.write_text(json.dumps({"at": now.isoformat(), "symbols": {"A": {}, "B": {}},
                                     "symbols_with_real_depth": []}))
        return 0
    got = ftm.refresh_depth_probe(probe=probe, runner=runner)
    assert got["status"] == "REPROBED" and got["n_probed"] == 2
    probe.write_text(json.dumps({"at": (now - timedelta(days=30)).isoformat(), "symbols": {}}))
    try:
        import MetaTrader5  # noqa: F401
    except Exception:
        assert ftm.refresh_depth_probe(probe=probe)["status"] == "UNMEASURED"


# ----------------------------------------------------------------------------- series gaps
def _series_on(path: Path, days: list[str]) -> None:
    """A micro series holding every hour of each named UTC date, and nothing else."""
    idx = pd.DatetimeIndex([], tz="UTC")
    for d in days:
        idx = idx.append(pd.date_range(d, periods=24, freq="1h", tz="UTC"))
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"n_ticks": np.full(len(idx), 100.0)}, index=idx).to_parquet(path)


_TODAY = datetime(2026, 11, 2, 12, tzinfo=UTC)          # a Monday


def test_a_five_trading_day_hole_is_reported(tmp_path: Path) -> None:
    p = tmp_path / "micro_EURUSD.parquet"
    # Mon 2026-10-05 .. Fri 10-09, then nothing until Mon 10-19: the week of 10-12 is missing.
    week1 = [f"2026-10-0{d}" for d in range(5, 10)]
    week3 = [f"2026-10-{d}" for d in range(19, 24)]
    _series_on(p, week1 + week3)
    g = ftm.series_gaps(p, today=datetime(2026, 10, 23, 18, tzinfo=UTC))
    assert g["status"] == "MEASURED"
    assert g["gap_count"] == 1 and g["longest_gap_trading_days"] == 5
    assert g["longest_gap"] == {"trading_days": 5, "after": "2026-10-09", "before": "2026-10-19"}
    assert g["start"] == "2026-10-05" and g["end"] == "2026-10-23"
    assert g["trailing_gap_trading_days"] == 0


def test_a_weekend_is_not_a_gap(tmp_path: Path) -> None:
    p = tmp_path / "micro_EURUSD.parquet"
    # Fri 10-09 then Mon 10-12 (plus the Sunday-evening open stub on 10-11).
    _series_on(p, ["2026-10-08", "2026-10-09", "2026-10-11", "2026-10-12", "2026-10-13"])
    g = ftm.series_gaps(p, today=datetime(2026, 10, 14, tzinfo=UTC))
    assert g["status"] == "MEASURED"
    assert g["gap_count"] == 0 and g["longest_gap_trading_days"] == 0
    assert g["longest_gap"] is None and g["trailing_gap_trading_days"] == 0
    # on a venue that quotes every day, the same Saturday IS a missing day
    every = ftm.series_gaps(p, trades_weekends=True, today=datetime(2026, 10, 14, tzinfo=UTC))
    assert every["gap_count"] == 1 and every["longest_gap_trading_days"] == 1


def test_an_absent_or_empty_series_is_unmeasured_never_zero(tmp_path: Path) -> None:
    absent = ftm.series_gaps(tmp_path / "micro_GBPUSD.parquet", today=_TODAY)
    assert absent["status"] == "UNMEASURED" and absent["why"]
    assert "gap_count" not in absent and "longest_gap_trading_days" not in absent
    empty = tmp_path / "micro_USDJPY.parquet"
    pd.DataFrame({"n_ticks": pd.Series([], dtype=float)},
                 index=pd.DatetimeIndex([], tz="UTC")).to_parquet(empty)
    e = ftm.series_gaps(empty, today=_TODAY)
    assert e["status"] == "UNMEASURED" and "gap_count" not in e
    rep = ftm.gap_report(["GBPUSD", "USDJPY"], tmp_path, today=_TODAY)
    assert rep["status"] == "UNMEASURED" and rep["worst_gap"] is None
    assert rep["symbols_unmeasured"] == ["GBPUSD", "USDJPY"]
    assert str(tmp_path) not in json.dumps(rep)


def test_the_report_summarises_the_worst_gap_and_the_stalls(tmp_path: Path) -> None:
    series, ticks = tmp_path / "series", tmp_path / "ticks"
    _series_on(series / "micro_EURUSD.parquet",
               ["2026-10-05", "2026-10-06", "2026-10-14", "2026-10-15"])   # 5-day hole
    _series_on(series / "micro_AUDUSD.parquet", ["2026-10-14", "2026-10-15"])  # clean
    rep = ftm.run(tick_root=ticks, series_root=series, report_path=tmp_path / "rep.json",
                  probe_depth=False, propose_cells=False)
    g = json.loads((tmp_path / "rep.json").read_text())["series_gaps"]
    assert g == json.loads(json.dumps(rep["series_gaps"]))
    assert g["status"] == "MEASURED" and g["symbols_measured"] == 2
    assert g["worst_gap"]["symbol"] == "EURUSD" and g["worst_gap"]["trading_days"] == 5
    assert g["symbols_gap_over_threshold"] == ["EURUSD"]
    # both series end in the past, so both are stale against today
    assert set(g["symbols_stale_over_threshold"]) == {"AUDUSD", "EURUSD"}
    assert g["by_symbol"]["EURUSD"]["series"] == "micro_EURUSD.parquet"
    assert str(tmp_path) not in json.dumps(g)
