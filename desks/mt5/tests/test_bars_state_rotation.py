"""ROW 74: EVERY BAR FILE IS READ WITHIN A BOUNDED NUMBER OF PASSES, AND THE FX FENCE IS RED.

On the trading box one 20 s pass read 251 of 1,722 footers and always the same alphabetical
head, so 79 of 86 FX symbols never had a freshness check. These pin the rotation (oldest check
first), the carry (bounded by CARRY_MAX_H, after which a file is UNMEASURED), and the FX fence
(RED on a missing, stale or unread FX timeframe; UNMEASURED, never GREEN, when nothing is FX).
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bars_state as bs  # noqa: E402

#: A Tuesday, US daylight time: the server is UTC+3.
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
FX = ("EURUSD", "GBPUSD", "USDJPY")


def _bars(path: Path, end_utc: datetime, freq: str = "1min") -> None:
    wall = (end_utc + timedelta(hours=3)).replace(tzinfo=None)
    idx = pd.date_range(end=wall, periods=5, freq=freq, name="time")
    df = pd.DataFrame({"open": 1.0, "close": 1.0}, index=idx)
    pq.write_table(pa.Table.from_pandas(df), path)


def _universe(tmp: Path, *, last: datetime, syms: tuple[str, ...] = FX) -> Path:
    uni = tmp / "universe"
    uni.mkdir()
    for s in syms:
        for tf in bs.FX_TIMEFRAMES:
            _bars(uni / f"{s}_{tf}.parquet", last)
    return uni


class Clock:
    """Each call advances one second: the budget admits `budget_s / BARS_BUDGET_SHARE` reads."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def _pass(uni: Path, tmp: Path, prior: dict | None, now: datetime, budget: float = 8.0) -> dict:
    return bs.measure(universe=uni, ticks=tmp / "ticks", tape_state=tmp / "none.json",
                      budget_s=budget, clock=Clock(), now=now, prior=prior,
                      classify=lambda s: s in FX)


def test_every_file_is_read_within_a_bounded_number_of_passes(tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30))
    n_files = len(list(uni.glob("*.parquet")))
    prior: dict | None = None
    read: set[str] = set()
    for i in range(n_files):
        doc = _pass(uni, tmp_path, prior, NOW + timedelta(hours=i))
        read |= {r["file"] for r in doc["bars"] if r.get("check_age_h") == 0.0}
        prior = json.loads(json.dumps(doc))
        if len(read) == n_files:
            break
    per_pass = doc["summary"]["bar_files_read_this_pass"]
    assert 0 < per_pass < n_files, "the budget must actually bind in this test"
    assert len(read) == n_files
    assert i + 1 <= -(-n_files // per_pass) + 1


def test_a_carried_reading_beyond_the_bound_is_unmeasured_and_the_fence_red(
        tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30))
    first = json.loads(json.dumps(_pass(uni, tmp_path, None, NOW, budget=1000.0)))
    assert first["fx_freshness"]["verdict"] == "GREEN"
    later = NOW + timedelta(hours=bs.CARRY_MAX_H + 1)
    doc = _pass(uni, tmp_path, first, later, budget=3.0)
    carried_out = [r for r in doc["bars"] if "carry bound" in str(r.get("carry"))]
    assert carried_out and all(r["status"] == "UNMEASURED" for r in carried_out)
    assert doc["fx_freshness"]["verdict"] == "RED"
    assert doc["fx_freshness"]["fx_unmeasured"] >= len(carried_out)


def test_an_unchanged_file_ages_between_reads(tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30))
    first = json.loads(json.dumps(_pass(uni, tmp_path, None, NOW, budget=1000.0)))
    doc = _pass(uni, tmp_path, first, NOW + timedelta(hours=10), budget=3.0)
    carried = [r for r in doc["bars"] if r.get("carried")]
    assert carried and all(r["age_h"] > 10 for r in carried)
    m1 = [o for o in doc["fx_freshness"]["offenders"] if o["timeframe"] == "M1"]
    assert m1 and all(o["state"] in ("STALE", "UNMEASURED") for o in m1)


def test_a_missing_fx_timeframe_is_red(tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30))
    (uni / "EURUSD_H4.parquet").unlink()
    doc = _pass(uni, tmp_path, None, NOW, budget=1000.0)
    fx = doc["fx_freshness"]
    assert fx["verdict"] == "RED" and fx["fx_missing"] == 1
    assert {"symbol": "EURUSD", "timeframe": "H4", "state": "MISSING",
            "why": "no bar file for this timeframe"} in fx["offenders"]


def test_the_weekend_does_not_read_as_stale(tmp_path: Path) -> None:
    friday_close = datetime(2026, 10, 23, 20, 30, tzinfo=UTC)
    uni = _universe(tmp_path, last=friday_close)
    sunday = datetime(2026, 10, 25, 18, 0, tzinfo=UTC)
    doc = _pass(uni, tmp_path, None, sunday, budget=1000.0)
    assert doc["fx_freshness"]["verdict"] == "GREEN", doc["fx_freshness"]["offenders"][:3]


def test_no_fx_classified_is_unmeasured_never_green(tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30), syms=("XAUUSD",))
    doc = _pass(uni, tmp_path, None, NOW, budget=1000.0)
    assert doc["fx_freshness"]["verdict"] == "UNMEASURED"


def test_the_prior_report_round_trips_through_the_writer(tmp_path: Path) -> None:
    uni = _universe(tmp_path, last=NOW - timedelta(minutes=30))
    out = tmp_path / "BARS_STATE.json"
    bs.write(_pass(uni, tmp_path, None, NOW, budget=1000.0), out)
    prior = bs.read_prior(out)
    assert prior is not None
    doc = _pass(uni, tmp_path, prior, NOW + timedelta(hours=1), budget=3.0)
    assert doc["summary"]["bar_files_carried"] > 0
