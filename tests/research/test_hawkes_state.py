"""Hawkes tick-intensity state: the fit recovers a known branching ratio, and no row sees later
ticks (row 73 of the 2026-11-18 build check)."""
from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hawkes_state as H  # noqa: E402
import state_conditioner as sc  # noqa: E402


def _simulate(mu: float, n: float, beta: float, horizon: float, seed: int) -> np.ndarray:
    """Ogata thinning for an exponential-kernel Hawkes process."""
    rng = np.random.default_rng(seed)
    t, acc, last, out = 0.0, 0.0, 0.0, []
    while True:
        bound = mu + n * beta * acc * math.exp(-beta * (t - last))
        t += rng.exponential(1.0 / bound)
        if t > horizon:
            return np.asarray(out)
        acc = acc * math.exp(-beta * (t - last))
        last = t
        if rng.uniform() * bound <= mu + n * beta * acc:
            acc += 1.0
            out.append(t)


@pytest.mark.parametrize("n", [0.0, 0.6])
def test_fit_recovers_the_branching_ratio(n: float) -> None:
    ev = _simulate(0.4, n, 2.0, 3600.0, seed=7)
    fit = H.fit_hawkes(ev, 3600.0)
    assert fit is not None
    assert abs(fit["branching_ratio"] - n) < 0.15
    assert fit["lambda_end"] > 0 and fit["excitation"] >= 1.0 - 1e-9


def test_too_few_events_is_no_fit() -> None:
    assert H.fit_hawkes([1.0, 2.0, 3.0], 3600.0) is None


def _ticks(start_ms: int, hours: int, seed: int) -> np.ndarray:
    parts = [start_ms + h * H.HOUR_MS + (_simulate(0.2, 0.4, 1.0, 3599.0, seed + h) * 1000)
             .astype("int64") for h in range(hours)]
    return np.unique(np.concatenate(parts)) if parts else np.zeros(0, dtype="int64")


def test_no_row_sees_a_later_tick() -> None:
    start = int(datetime(2026, 11, 2).timestamp() * 1000)
    ms = _ticks(start, 8, seed=3)
    hours = [start + k * H.HOUR_MS for k in range(8)]
    base = H.hour_rows(ms, hours)
    assert len(base) == 8
    # a violent burst AFTER hour 4: 20,000 arrivals packed into hour 5's first second
    cut = start + 5 * H.HOUR_MS
    burst = cut + np.arange(20_000, dtype="int64") // 20
    later = np.unique(np.concatenate([ms[ms < cut], burst]))
    again = H.hour_rows(later, hours)
    for a, b in zip(base[:5], again[:5], strict=True):
        assert a == b
    assert again[5] != base[5]
    # the state is stamped at the TRUE UTC close of its broker hour, never earlier
    for k, row in enumerate(base):
        close_wall = datetime(2026, 11, 2) + timedelta(hours=k + 1)
        assert datetime.fromisoformat(row["available_time"]) == sc.broker_to_utc(close_wall)
        assert datetime.fromisoformat(row["available_time"]) < close_wall.replace(tzinfo=UTC)


def test_trailing_z_never_reads_itself_or_later() -> None:
    z = sc.trailing_z([1.0, 2.0, 3.0, 100.0, 2.0], window=10, min_n=3)
    assert z[:3] == [None, None, None]
    assert z[3] is not None and z[3] > 10
    assert sc.trailing_z([1.0, 2.0, 3.0, 100.0], 10, 3)[3] == z[3]


def test_a_pass_publishes_state_series_and_never_fits_the_open_hour(tmp_path: Path,
                                                                     monkeypatch) -> None:
    monkeypatch.setattr(H, "MIN_ROWS_TO_MINT", 10 ** 9)       # this test never donates
    ticks = tmp_path / "ticks"
    (ticks / "EURUSD").mkdir(parents=True)
    day = datetime(2026, 11, 2)
    start = int(day.replace(tzinfo=UTC).timestamp() * 1000)
    ms = _ticks(start, 6, seed=11)
    pd.DataFrame({"time_msc": ms, "bid": 1.0, "ask": 1.0}).to_parquet(
        ticks / "EURUSD" / "2026-11-02.parquet")
    # broker wall 05:30 on that day, i.e. hour 5 is still open and must not be fitted
    now = sc.broker_to_utc(day + timedelta(hours=5, minutes=30))
    rep = tmp_path / "HAWKES_STATE.json"
    doc = H.run(ticks=ticks, series_root=tmp_path / "series", state_path=tmp_path / "s.json",
                report=rep, now=now, budget_s=60)
    sym = doc["symbols"]["EURUSD"]
    assert doc["verdict"] == "MEASURED"
    assert sym["rows"] == 5 and sym["broker_hour"] == "2026-11-02T04:00:00"
    assert 0.0 <= sym["branching_ratio"] < 1.0
    assert json.loads(rep.read_text())["symbols"]["EURUSD"]["rows"] == 5
    series = pd.read_csv(tmp_path / "series" / "hawkes_EURUSD.csv")
    assert {"available_time", "event_time", "intensity_z", "branching_ratio"} <= set(series)
    # a second pass at the same instant adds nothing (the cursor holds)
    doc2 = H.run(ticks=ticks, series_root=tmp_path / "series", state_path=tmp_path / "s.json",
                 report=rep, now=now, budget_s=60)
    assert doc2["symbols"]["EURUSD"]["new_rows"] == 0


def test_cells_are_minted_once_and_carry_the_safe_lag(tmp_path: Path, monkeypatch) -> None:
    calls: list[int] = []

    class _PC:
        @staticmethod
        def donate(seat, rows, tests_run):
            calls.append(len(rows))
            return tmp_path / "d.json"

        @staticmethod
        def donation_counts():
            return {"donated": calls[-1]}

    monkeypatch.setitem(sys.modules, "proposer_common", _PC)
    from research import proposer_common as real
    monkeypatch.setattr(_PC, "candidate", staticmethod(real.candidate), raising=False)
    rows = sc.cell_rows("hawkes_state", "hawkes_EURUSD", "EURUSD", ("intensity_z",), "m")
    assert {r["params"]["lag_hours"] for r in rows} == {sc.CELL_LAG_HOURS}
    assert sc.CELL_LAG_HOURS > 3                  # above the broker clock's largest offset
    first = sc.mint_once("hawkes_state", rows, tmp_path / "st.json")
    second = sc.mint_once("hawkes_state", rows, tmp_path / "st.json")
    assert first["donated"] == len(rows) and second["new"] == 0 and calls == [len(rows)]
