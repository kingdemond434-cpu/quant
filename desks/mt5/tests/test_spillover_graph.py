"""spillover_graph: Diebold-Yilmaz connectedness on desk bars, report only."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from research import spillover_graph as sg


def _bars(close: np.ndarray, start: str = "2022-01-03") -> pd.DataFrame:
    idx = pd.date_range(start, periods=close.size, freq="1h", tz="UTC")
    rng = np.abs(close) * 0.002 + 1e-4
    return pd.DataFrame({"open": close, "high": close + rng, "low": close - rng, "close": close},
                        index=idx)


def _write_universe(tmp: Path, days: int = 600, seed: int = 7) -> None:
    """LEAD's daily shock reaches LAG the next day; NOISE is independent."""
    r = np.random.default_rng(seed)
    lead_d = r.normal(0, 0.01, days)
    lag_d = 0.8 * np.concatenate([[0.0], lead_d[:-1]]) + r.normal(0, 0.004, days)
    noise_d = r.normal(0, 0.01, days)

    def hourly(daily_ret: np.ndarray) -> np.ndarray:
        h = np.repeat(daily_ret / 24.0, 24)
        return 100.0 * np.exp(np.cumsum(h))

    tmp.mkdir(parents=True, exist_ok=True)
    for name, d in (("US500", lead_d), ("XAUUSD", lag_d), ("EURUSD", noise_d)):
        _bars(hourly(d)).to_parquet(tmp / f"{name}_H1.parquet")


@pytest.fixture()
def roster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sg, "ROSTER", {"indices": ("US500",), "metals": ("XAUUSD",),
                                       "fx": ("EURUSD", "USDJPY")})


def test_gfevd_rows_sum_to_one_and_independent_series_do_not_spill() -> None:
    r = np.random.default_rng(1)
    x = r.normal(size=(800, 3))
    coefs, sigma, _n = sg.fit_var(x, 1)
    theta = sg.gfevd(coefs, sigma, 10)
    assert np.allclose(theta.sum(axis=1), 1.0)
    assert sg.connectedness(theta, ["a", "b", "c"])["total"] < 5.0


def test_the_leader_is_the_net_transmitter(tmp_path: Path, roster: None) -> None:
    _write_universe(tmp_path)
    doc = sg.run(universe_dir=tmp_path, out=tmp_path / "out.json", force=True)
    ret = doc["channels"]["returns"]
    assert ret["status"] == "MEASURED"
    assert ret["nodes"]["US500"]["net"] > 0 > ret["nodes"]["XAUUSD"]["net"]
    assert ret["pairs"][0]["from"] == "US500" and ret["pairs"][0]["to"] == "XAUUSD"
    assert 0.0 <= ret["total"] <= 100.0
    assert ret["rolling_total"], "a rolling series is published"
    assert doc["missing"] == ["USDJPY"], "an absent file is named, never zero-filled"


def test_too_little_history_reads_unmeasured(tmp_path: Path, roster: None) -> None:
    _write_universe(tmp_path, days=60)
    doc = sg.run(universe_dir=tmp_path, out=tmp_path / "out.json", force=True)
    assert doc["channels"]["returns"]["status"] == sg.UNMEASURED


def test_unchanged_inputs_stand_down_inside_the_refresh_window(tmp_path: Path,
                                                               roster: None) -> None:
    _write_universe(tmp_path)
    out = tmp_path / "out.json"
    first = sg.run(universe_dir=tmp_path, out=out, force=True)
    sg._write(out, first)
    again = sg.run(universe_dir=tmp_path, out=out)
    assert again["stood_down"] is True
    assert again["channels"] == json.loads(out.read_text("utf-8"))["channels"]


def _daily_bars(closes: list[float], days: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=12) for d in days])
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c}, index=idx)


def test_a_missing_day_never_yields_a_mismatched_interval_row() -> None:
    """B has no bar on day 3. Diffed before the join, B's day-4 row would be a two-day return
    (day 2 -> day 4) beside A's one-day return (day 3 -> day 4). Joined first, every row spans
    the same interval: the day-4 row is day 2 -> day 4 for BOTH symbols."""
    days = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    a = _daily_bars([100.0, 101.0, 110.0, 121.0], days)
    b = _daily_bars([50.0, 51.0, 60.0], [days[0], days[1], days[3]])
    ret = sg.channels({"A": a, "B": b})["returns"]
    assert list(ret.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-04"]
    assert ret.loc["2024-01-04", "A"] == pytest.approx(np.log(121.0 / 101.0))
    assert ret.loc["2024-01-04", "B"] == pytest.approx(np.log(60.0 / 51.0))
    cov = sg.coverage({"A": a, "B": b})
    assert cov["common_days"] == 3
    assert cov["symbol_days"] == {"A": 4, "B": 3}
    assert cov["common_share"] == {"A": 0.75, "B": 1.0}


def test_run_reports_common_days_against_each_symbols_own(tmp_path: Path, roster: None) -> None:
    _write_universe(tmp_path)
    doc = sg.run(universe_dir=tmp_path, out=tmp_path / "out.json", force=True)
    cov = doc["coverage"]
    assert set(cov["symbol_days"]) == {"US500", "XAUUSD", "EURUSD"}
    assert all(cov["common_days"] <= n for n in cov["symbol_days"].values())
