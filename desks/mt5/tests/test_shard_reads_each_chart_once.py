"""A build shard reads each chart once, not once per spec.

Measured 2026-10-29 on the box: a shard's ~19,700 specs arrive in priority order, which
interleaves symbols, so the bounded frame cache evicted each chart before its next spec and every
spec re-read a parquet only to learn the day that keys its cache entry. 945 replayed cells took
3,123 s. The shard now remembers each chart's day per parquet version.
"""
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
for p in (DESK, DESK / "scripts", DESK / "research"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import external_gauntlet as eg  # noqa: E402

SYMS = ("AAA", "BBB", "CCC")


def _write(uni: Path, sym: str, periods: int) -> None:
    idx = pd.date_range("2026-01-01", periods=periods, freq="h")
    pd.DataFrame({"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1},
                 index=idx).to_parquet(uni / f"{sym}_H1.parquet")


@pytest.fixture
def shard(monkeypatch, tmp_path):
    uni = tmp_path / "universe"
    uni.mkdir()
    for s in SYMS:
        _write(uni, s, 48)
    monkeypatch.setattr(eg, "UNI", uni)
    monkeypatch.setattr(eg, "_FRAME_CACHE", type(eg._FRAME_CACHE)())
    monkeypatch.setattr(eg, "FRAME_CACHE_ROWS", 1)       # evict on every new chart
    reads: list[str] = []
    real = eg._read_parquet_shared

    def counted(pq, **k):
        reads.append(Path(pq).stem)
        return real(pq, **k)

    monkeypatch.setattr(eg, "_read_parquet_shared", counted)
    keys: list[str] = []

    def cached(key):
        keys.append(key)
        s = pd.Series([0.0], index=pd.DatetimeIndex(["2026-01-01"]))
        return s, s

    monkeypatch.setattr(eg, "cache_load", cached)
    monkeypatch.setattr(eg, "stage0_record", lambda *a, **k: None)
    # interleaved, as the priority order lays a shard's specs out
    specs = [{"sym": SYMS[i % 3], "family": "fam", "params": {"n": i}} for i in range(30)]
    return uni, specs, reads, keys


def _run(specs, memo):
    blocked: list = []
    acc = eg._build_specs(specs, {}, 0.0, {}, {}, set(), blocked, last_days=memo)
    return acc, blocked


def test_the_shard_reads_each_chart_once(shard) -> None:
    _, specs, reads, keys = shard
    acc, blocked = _run(specs, {})
    assert sorted(reads) == [f"{s}_H1" for s in SYMS]
    assert acc["cache_hits"] == 30 and not blocked and len(keys) == 30


def test_without_the_memo_every_spec_still_reads(shard) -> None:
    _, specs, reads, _ = shard
    _run(specs, None)
    assert len(reads) == 30            # the old lines, unchanged for every other caller


def test_the_memo_keys_the_same_cache_entries_as_the_old_lines(shard) -> None:
    _, specs, _, keys = shard
    _run(specs, None)
    old = list(keys)
    keys.clear()
    _run(specs, {})
    assert keys == old


def test_a_parquet_rewritten_mid_shard_is_read_again(shard) -> None:
    uni, specs, reads, keys = shard
    memo: dict = {}
    _run(specs[:3], memo)
    _write(uni, "AAA", 96)                                # two days later
    st = (uni / "AAA_H1.parquet").stat()
    os.utime(uni / "AAA_H1.parquet", ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    keys.clear()
    _run(specs[:3], memo)
    assert reads.count("AAA_H1") == 2 and reads.count("BBB_H1") == 1
    assert keys[0] == eg._cache_key("AAA", "fam", {"n": 0}, "2026-01-04", "H1")
    assert keys[1] == eg._cache_key("BBB", "fam", {"n": 1}, "2026-01-02", "H1")


def test_a_missing_chart_is_blocked_with_or_without_the_memo(shard) -> None:
    uni, specs, _, _ = shard
    (uni / "CCC_H1.parquet").unlink()
    for memo in (None, {}):
        _, blocked = _run(specs[:6], memo)
        assert [b["sym"] for b in blocked] == ["CCC", "CCC"]
        assert {b["downstream_status"] for b in blocked} == {"NOT_RUN_DATA_MISSING"}
