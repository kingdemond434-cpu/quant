"""The cost surface's tick-measured hours and H1 ATR (2026-10-14).

The bar surface drops zero-spread bars as absence; on this raw-FX account a zero spread is a real
quote, so a mostly-locked symbol (USDSGD) read "1 pt" from hour 01 to 23. `tick_hours` measures
every tick's quoted spread with zeros included, per venue hour, and `atr20_h1_pts` publishes the
scale the cost repricing divides by. Pinned: zeros count, the nonzero p50 is beside them, a thin
hour is UNMEASURED, a missing tape is NO_TAPE (never a zero cost), and ATR is the mean true range.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK / "research"), str(DESK), str(DESK.parents[1])):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cost_surface as CS  # noqa: E402

POINT = 1e-5
H = 3_600_000


def _tape(root: Path, sym: str, hour: int, spreads_pts: list[float], day: str = "2026-10-13"):
    base = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000) + hour * H
    n = len(spreads_pts)
    bid = np.full(n, 1.30000)
    df = pd.DataFrame({"time_msc": base + np.arange(n) * 100, "bid": bid,
                       "ask": bid + np.asarray(spreads_pts) * POINT})
    d = root / sym
    d.mkdir(parents=True, exist_ok=True)
    df.to_parquet(d / f"{day}.parquet")


def test_zero_spread_ticks_count_and_the_nonzero_p50_sits_beside_them(tmp_path: Path) -> None:
    _tape(tmp_path, "USDSGD", 1, [0.0] * 300 + [1.0] * 100)
    _tape(tmp_path, "USDSGD", 0, [95.0] * 50, day="2026-10-12")
    prof = CS.tick_profile("USDSGD", POINT, root=tmp_path)
    assert prof is not None
    h1 = prof["hours"]["1"]
    assert h1["status"] == "MEASURED" and h1["p50"] == 0.0 and h1["p50_nonzero"] == 1.0
    assert h1["zero_frac"] == 0.75 and h1["n_ticks"] == 400
    assert prof["hours"]["0"]["status"] == "UNMEASURED" and "p50" not in prof["hours"]["0"]


def test_no_tape_is_none_never_a_zero_cost(tmp_path: Path) -> None:
    assert CS.tick_profile("CHFDKK", POINT, root=tmp_path) is None
    assert CS.tick_profile("CHFDKK", 0.0, root=tmp_path) is None


def test_atr20_is_the_mean_true_range_of_the_newest_twenty_bars() -> None:
    idx = pd.date_range("2026-10-01", periods=30, freq="h", tz="UTC")
    close = pd.Series(1.0, index=idx)
    df = pd.DataFrame({"high": close + 0.001, "low": close - 0.001, "close": close})
    assert abs(CS.atr_h1(df) - 0.002) < 1e-12
    assert CS.atr_h1(df.iloc[:10]) is None
    assert CS.atr_h1(df[["close"]]) is None


def test_atr_carries_the_bar_it_was_computed_through() -> None:
    """Audit 2026-10-14: an ATR with no as-of date cannot be told from a stale one."""
    idx = pd.date_range("2026-10-01", periods=30, freq="h", tz="UTC")
    df = pd.DataFrame({"high": 1.001, "low": 0.999, "close": 1.0}, index=idx)
    assert CS.atr_through(df) == idx[-1].isoformat()
    assert CS.atr_through(df.iloc[:0]) is None


# --------------------------------------------- the fill minute, not only the fill hour (2026-11-11)

def _minute_tape(spec: dict[tuple[int, int], tuple[float, int]], days: int = 4):
    """time_msc/pts series: for each (hour, minute), `n` ticks a day at `pts`, over `days` days."""
    t, p = [], []
    for d in range(days):
        day0 = int(pd.Timestamp("2026-11-02", tz="UTC").timestamp() * 1000) + d * 86_400_000
        for (h, m), (pts, n) in spec.items():
            for k in range(n):
                t.append(day0 + h * H + m * 60_000 + k * 100)
                p.append(pts)
    return pd.Series(t, dtype="int64"), pd.Series(p, dtype=float)


def test_the_post_rollover_minute_is_published_and_the_rest_of_its_hour_is_not() -> None:
    # EURCHF's shape: 62 pts in 01:00, ~2 pts for the rest of the hour.
    spec = {(1, 0): (62.0, 10), **{(1, m): (2.0, 30) for m in range(1, 60)}}
    t, p = _minute_tape(spec)
    hours = {"1": {"status": "MEASURED", "p50": float(p[(t // H) % 24 == 1].median())}}
    out = CS.spike_minutes(t, p, hours)
    assert list(out) == ["01:00"], out
    assert out["01:00"]["p50"] == 62.0 and out["01:00"]["n_days"] == 4
    assert out["01:00"]["hour_p50"] == 2.0


def test_a_thin_minute_or_an_unmeasured_hour_publishes_nothing() -> None:
    spec = {(1, 0): (62.0, 10), **{(1, m): (2.0, 30) for m in range(1, 60)}}
    t, p = _minute_tape(spec, days=2)                     # below SPIKE_MIN_DAYS
    assert CS.spike_minutes(t, p, {"1": {"status": "MEASURED", "p50": 2.0}}) == {}
    t, p = _minute_tape(spec)
    assert CS.spike_minutes(t, p, {"1": {"status": "UNMEASURED"}}) == {}


def test_a_locked_hour_does_not_flag_every_quoted_minute() -> None:
    # p50 0 (locked) is floored at one point: a 1-pt minute is not a spike, a 5-pt one is.
    spec = {(3, 0): (5.0, 30), (3, 1): (1.0, 30), **{(3, m): (0.0, 30) for m in range(2, 60)}}
    t, p = _minute_tape(spec)
    out = CS.spike_minutes(t, p, {"3": {"status": "MEASURED", "p50": 0.0}})
    assert list(out) == ["03:00"]


class _Sig:
    def __init__(self, ts: str, wait_bars: int = 1, trigger: float | None = None) -> None:
        self.time, self.wait_bars, self.trigger = pd.Timestamp(ts, tz="UTC"), wait_bars, trigger


def test_a_fill_is_the_next_bars_open_whatever_wait_bars_says() -> None:
    # The engine fills a market signal at the open of the bar AFTER its signal bar.
    sigs = [_Sig("2026-11-02 00:00"), _Sig("2026-11-02 23:00", wait_bars=6)]
    assert CS.fill_minutes(sigs, "H1") == [(1, 0), (0, 0)]
    assert CS.fill_minutes([_Sig("2026-11-02 13:55", wait_bars=0)], "M5") == [(14, 0)]


def test_with_the_bars_the_fill_is_read_off_the_index_across_a_gap() -> None:
    idx = pd.DatetimeIndex(["2026-11-06 21:00", "2026-11-06 22:00", "2026-11-09 00:00",
                            "2026-11-09 01:00", "2026-11-09 02:00"], tz="UTC")
    # Friday's last bar fills at Monday 00:00 (not 23:00); a trigger never lands on a minute.
    sigs = [_Sig("2026-11-06 22:00"), _Sig("2026-11-09 00:00"),
            _Sig("2026-11-09 00:00", trigger=1.1)]
    assert CS.fill_minutes(sigs, "H1", idx) == [(0, 0), (1, 0), (-1, -1)]
    # A signal on the last bars has no next bar to fill on, as in the engine.
    assert CS.fill_minutes([_Sig("2026-11-09 02:00")], "H1", idx) == []


def test_a_tick_with_no_time_is_dropped_not_fatal() -> None:
    spec = {(1, 0): (62.0, 10), **{(1, m): (2.0, 30) for m in range(1, 60)}}
    t, p = _minute_tape(spec)
    t = t.astype("float64")
    t.iloc[0] = float("nan")
    assert list(CS.spike_minutes(t, p, {"1": {"status": "MEASURED", "p50": 2.0}})) == ["01:00"]


def test_a_fill_on_a_spike_minute_pays_it_and_the_charge_never_falls() -> None:
    surf = {"symbols": {"EURCHF": {"tick_hours": {"spike_minutes": {
        "01:00": {"p50": 62.0}, "05:00": {"p50": 3.0}}}}}}
    fills = [(1, 0)] * 3 + [(2, 0)]
    got = CS.fill_spread_pts(surf, "EURCHF", fills, 7.0)
    assert got["spike_share"] == 0.75 and got["minutes"] == {"01:00": 3}
    assert got["spread_pts"] == (3 * 62.0 + 7.0) / 4
    # a "spike" cheaper than the charge already given lowers nothing
    low = CS.fill_spread_pts(surf, "EURCHF", [(5, 0)], 7.0)
    assert low["spike_share"] == 0.0 and low["spread_pts"] == 7.0
    assert CS.fill_spread_pts(surf, "EURCHF", [], 7.0)["spread_pts"] is None
    assert CS.fill_spread_pts(surf, "EURCHF", fills, None)["spread_pts"] is None
