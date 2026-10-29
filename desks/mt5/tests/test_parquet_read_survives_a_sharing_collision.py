"""A parquet another process holds mid-rewrite is retried, never read as missing data.

Measured 2026-10-29: two of fifteen build shards died on PermissionError [Errno 13] opening a
universe H1 parquet that was being rewritten, each costing hours. The read now retries.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "scripts", DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import external_gauntlet as eg  # noqa: E402


def _flaky(monkeypatch, fails: int, exc: type[BaseException] = PermissionError) -> list[int]:
    calls = [0]
    real = pd.read_parquet

    def read(path, *a, **k):
        calls[0] += 1
        if calls[0] <= fails:
            raise exc(13, "Permission denied", str(path))
        return real(path, *a, **k)

    monkeypatch.setattr(eg.pd, "read_parquet", read)
    return calls


@pytest.fixture
def parquet(tmp_path):
    idx = pd.date_range("2026-01-01", periods=48, freq="h")
    df = pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1}, index=idx)
    path = tmp_path / "US500_H1.parquet"
    df.to_parquet(path)
    return path


def test_a_collision_is_retried_and_the_frame_comes_back(monkeypatch, parquet) -> None:
    calls, slept = _flaky(monkeypatch, fails=2), []
    got = eg._read_parquet_shared(parquet, sleep=slept.append)
    assert len(got) == 48 and calls[0] == 3
    assert slept == [0.5, 1.0]


def test_a_collision_that_outlasts_the_retries_still_raises(monkeypatch, parquet) -> None:
    calls = _flaky(monkeypatch, fails=99)
    with pytest.raises(PermissionError):
        eg._read_parquet_shared(parquet, sleep=lambda _s: None)
    assert calls[0] == eg.PARQUET_READ_ATTEMPTS


def test_a_non_io_error_is_not_retried(monkeypatch, parquet) -> None:
    calls = _flaky(monkeypatch, fails=99, exc=ValueError)
    with pytest.raises(ValueError):
        eg._read_parquet_shared(parquet, sleep=lambda _s: None)
    assert calls[0] == 1


def test_bars_for_reads_through_the_retry(monkeypatch, parquet) -> None:
    monkeypatch.setattr(eg, "UNI", parquet.parent)
    monkeypatch.setattr(eg, "_FRAME_CACHE", type(eg._FRAME_CACHE)())
    monkeypatch.setattr(eg.time, "sleep", lambda _s: None)
    calls = _flaky(monkeypatch, fails=1)
    frame = eg._bars_for("US500", "H1")
    assert frame is not None and len(frame) == 48 and calls[0] == 2
