"""Crypto leverage history: PIT stamps, accrual, the hard stop, robots, and CFD-only cells."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import shadow_institutional as si  # noqa: E402

H = 3_600_000


def _fake(funding_t0: int = 1_700_000_000_000):
    calls: list[str] = []

    def get(url: str):
        calls.append(url)
        if "fundingRate" in url:
            return [{"fundingTime": funding_t0 + i * 8 * H, "fundingRate": "0.0001"}
                    for i in range(3)]
        if "openInterestHist" in url:
            return [{"timestamp": funding_t0 + i * H, "sumOpenInterestValue": "1e9"}
                    for i in range(2)]
        return [{"timestamp": funding_t0, "longShortRatio": "1.8"}]
    return get, calls


def test_period_aggregates_are_available_one_period_after_their_stamp(tmp_path):
    get, _ = _fake()
    rep = si.collect_leverage(get=get, root=tmp_path)
    f = pd.read_parquet(tmp_path / "crypto_lev_btcusdt.parquet")
    oi = f.dropna(subset=["oi_usd"])
    assert ((oi["available_time"] - oi["event_time"]) == pd.Timedelta(hours=1)).all()
    fu = f.dropna(subset=["funding_rate"])
    assert (fu["available_time"] == fu["event_time"]).all()
    assert rep["series"]["BTCUSDT"]["cfd"] == "BTCUSD"


def test_funding_resumes_after_the_last_held_row_and_never_duplicates(tmp_path):
    get, _ = _fake()
    si.collect_leverage(get=get, root=tmp_path)
    get2, calls2 = _fake()
    si.collect_leverage(get=get2, root=tmp_path)
    f = pd.read_parquet(tmp_path / "crypto_lev_btcusdt.parquet")
    assert not f.duplicated(["event_time", "available_time"]).any()
    assert f["funding_rate"].notna().sum() == 3 and f["oi_usd"].notna().sum() == 2
    assert any("startTime=" in u for u in calls2 if "fundingRate" in u)


def test_a_hard_status_stops_the_pass(tmp_path):
    def get(url: str):
        raise si.LeverageStop(451, url)
    rep = si.collect_leverage(get=get, root=tmp_path)
    assert rep["hard_stop"]["code"] == 451 and not list(tmp_path.iterdir())


def test_robots_disallow_is_a_label_and_the_fetch_proceeds(tmp_path):
    """LAWS 5e: a Disallow labels the series PUBLIC_WITH_TERMS, redistribution withheld."""
    get, calls = _fake()
    rep = si.collect_leverage(get=get, root=tmp_path,
                              robots=lambda u: ("futures/data" not in u, "robots disallows"))
    assert any("futures/data" in u for u in calls)
    row = rep["series"]["BTCUSDT"]
    assert row["access_label"] == "PUBLIC_WITH_TERMS" and row["redistribute_allowed"] is False
    df = pd.read_parquet(tmp_path / "crypto_lev_btcusdt.parquet")
    assert set(df["access_label"]) == {"PUBLIC_WITH_TERMS"} and not df["redistribute_allowed"].any()
    again = si.collect_leverage(get=get, root=tmp_path)
    assert again["series"]["BTCUSDT"]["access_label"] == "PUBLIC"


def test_unreadable_robots_is_access_unclear_not_a_refusal(tmp_path):
    get, calls = _fake()
    rep = si.collect_leverage(get=get, root=tmp_path,
                              robots=lambda u: (True, "robots.txt unreadable: URLError"))
    assert rep["series"]["ETHUSDT"]["access_label"] == "ACCESS_UNCLEAR"
    assert len(calls) == 3 * len(si.LEVERAGE_PERPS)


def test_cells_condition_the_mt5_cfd_only():
    seen: list[dict] = []

    def enqueue(**kw):
        seen.append(kw)
        return "id", True
    rep = {"series": {"ETHUSDT": {"cfd": "ETHUSD", "rows": 10}}}
    n = si.mint_leverage_cells(rep, enqueue=enqueue)
    assert n == len(seen) == 3 * 2 * 3
    assert {k["symbol"] for k in seen} == {"ETHUSD"}
    assert {k["family"] for k in seen} == {"exogenous_conditioner"}
