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
