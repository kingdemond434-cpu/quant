"""taiwan_options (ASIA-0510): TAIFEX TXO put/call state -- parse, resumable fetch, PIT rows,
GAIN on a planted effect and not on noise, cells held on terms. Synthetic only."""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK.parents[1]), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from macro import taiwan_options as tw  # noqa: E402

from libs.research import sensor_engines as se  # noqa: E402

N = 1100


def _days(n: int = N) -> list[date]:
    out, d = [], date(2021, 1, 4)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _world(tmp: Path, planted: bool, seed: int = 3) -> tuple[Path, Path]:
    rng = np.random.default_rng(seed)
    days = _days()
    oi = 100.0 + 15.0 * rng.standard_normal(len(days))
    vol = 90.0 + 12.0 * rng.standard_normal(len(days))
    store = tmp / "pc_ratio.csv"
    tw.save_store({d.isoformat(): {"date": d.isoformat(), "put_vol": 1.0, "call_vol": 1.0,
                                   "pcr_vol": float(v), "put_oi": 1.0, "call_oi": 1.0,
                                   "pcr_oi": float(o), "fetched_at": "t"}
                   for d, o, v in zip(days, oi, vol, strict=True)}, store)
    # the trailing z the engine will compute, to plant the next-day effect on it
    z = [(oi[i] - oi[max(0, i - 252):i].mean()) / oi[max(0, i - 252):i].std(ddof=1)
         if i >= 60 else 0.0 for i in range(len(days))]
    px, close = 100.0, []
    for i in range(len(days)):
        close.append(px)
        drift = 0.006 if (planted and z[i] >= 1.0) else 0.0
        px *= 1.0 + drift + 0.01 * rng.standard_normal()
    uni = tmp / "universe"
    uni.mkdir()
    idx = pd.DatetimeIndex([datetime(d.year, d.month, d.day, 20, tzinfo=UTC) for d in days])
    pd.DataFrame({"close": close}, index=idx).to_parquet(uni / "TSMC_H1.parquet")
    return store, uni


def _sandbox(tmp: Path, monkeypatch) -> None:
    monkeypatch.setattr(se, "LAKE", tmp / "lake")
    monkeypatch.setattr(se, "CONTRACTS", tmp / "contracts")
    monkeypatch.setattr(se, "ROLLUP", tmp / "SENSOR_CONTRACTS.json")


def test_parse_reads_the_big5_download_by_position() -> None:
    body = ("日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,"
            "買賣權未平倉量比率%\r\n2026/10/05,\"312,455\",\"287,001\",108.87,\"98,765\","
            "\"87,654\",112.68\r\n2026/10/02,1,2,50.00,3,4,75.00\r\n").encode("cp950")
    rows = tw.parse_csv(body)
    assert [r["date"] for r in rows] == ["2026-10-05", "2026-10-02"]
    assert rows[0]["put_vol"] == 312455.0 and rows[0]["pcr_oi"] == 112.68


def test_refresh_is_resumable_and_rereads_only_the_newest_chunk(tmp_path) -> None:
    calls: list[tuple[date, date]] = []

    def fake(lo: date, hi: date) -> list[dict]:
        calls.append((lo, hi))
        return [{"date": (lo + timedelta(days=i)).isoformat(), "put_vol": 1.0, "call_vol": 1.0,
                 "pcr_vol": 100.0, "put_oi": 1.0, "call_oi": 1.0, "pcr_oi": 100.0}
                for i in range((hi - lo).days + 1)]

    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    store = tmp_path / "pc.csv"
    first = tw.refresh(90, now, store, fake)
    assert first["status"] == "OK" and len(calls) == 4
    calls.clear()
    tw.refresh(90, now, store, fake)
    assert len(calls) == 1 and calls[0][1] == now.date()       # the newest chunk only


def test_rows_are_point_in_time() -> None:
    days = _days(300)
    store = {d.isoformat(): {"pcr_oi": float(i % 7), "pcr_vol": float(i % 5)}
             for i, d in enumerate(days)}
    rows = tw.build_rows(store)
    assert rows[0]["pcr_oi_z"] is None                       # no trailing year yet
    r = rows[200]
    assert r["available_time"].startswith(r["event_time"] + "T10:00")
    # the z of day d uses only days before d: changing a later day leaves it unchanged
    later = dict(store)
    later[days[250].isoformat()] = {"pcr_oi": 1e6, "pcr_vol": 1e6}
    assert tw.build_rows(later)[200]["pcr_oi_z"] == r["pcr_oi_z"]


def test_planted_hedging_relief_is_gain_and_noise_is_not(tmp_path, monkeypatch) -> None:
    _sandbox(tmp_path, monkeypatch)
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    for planted, sub in ((True, "p"), (False, "n")):
        (tmp_path / sub).mkdir()
        store, uni = _world(tmp_path / sub, planted)
        rep = tw.run(fetch_live=False, now=now, store_path=store, universe_dir=uni)
        got = {c["label"]: c["verdict"] for c in rep["contracts"] if c["symbol"] == "TSMC"}
        if planted:
            assert got["puts_heavy->long"] == se.GAIN
        else:
            assert se.GAIN not in got.values()
        assert rep["targets"]["NAS100"]["status"] == "UNMEASURED"


def test_cells_are_held_on_terms_until_cleared(tmp_path, monkeypatch) -> None:
    _sandbox(tmp_path, monkeypatch)
    store, uni = _world(tmp_path, planted=False)
    rep = tw.run(fetch_live=False, now=datetime(2026, 10, 6, 12, tzinfo=UTC),
                 store_path=store, universe_dir=uni)
    assert rep["terms"]["gauntlet"] == "HELD"
    assert rep["cells"]["status"] == "HELD_TERMS" and rep["cells"]["emitted"] == 0
