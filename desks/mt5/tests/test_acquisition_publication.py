"""Acquisition survives copied outputs and interruptions without manufacturing PIT authority."""
from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK))
from desks.mt5.research import job_lock  # noqa: E402

from research import acquire_datasets as ac  # noqa: E402
from research import hourly_discovery as hd  # noqa: E402


@pytest.fixture
def acquisition(tmp_path, monkeypatch):
    store = tmp_path / "acquired"
    store.mkdir()
    monkeypatch.setattr(ac, "STORE", store)
    monkeypatch.setattr(ac, "REGISTRY", store / "registry.json")
    monkeypatch.setattr(ac, "REPORT", tmp_path / "report.json")
    monkeypatch.setattr(ac, "WORLD", tmp_path / "world")
    monkeypatch.setattr(job_lock, "LOCK_ROOT", tmp_path / "locks")
    monkeypatch.setattr(ac, "path_for", lambda name: tmp_path / "certs" / f"{name}.json")
    urls = ("https://official.example/first.csv", "https://official.example/second.csv")
    monkeypatch.setattr(ac, "_SEED_ENDPOINTS", urls)
    frame = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=220),
                          "observation": range(220)})
    raw = frame.to_csv(index=False).encode()
    monkeypatch.setattr(ac, "_fetch", lambda url: (raw, "text/csv"))
    return store, urls


def test_copied_outputs_publish_and_real_reader_withholds_unmeasured_pit(acquisition):
    store, _ = acquisition
    ac.REGISTRY.write_text('{"by_url": {}, "series": {}}')
    ac.REPORT.write_text('{"old": true}')
    for path in (ac.REGISTRY, ac.REPORT):
        path.chmod(0o444)
    if os.name == "posix" and os.geteuid() != 0:
        with pytest.raises(PermissionError):
            ac.REGISTRY.open("w")
    report = ac.acquire(limit=1)
    assert report["datasets_kept"] == 1
    reg = json.loads(ac.REGISTRY.read_text())
    meta = next(iter(reg["series"].values()))
    assert (store / meta["path"]).exists()
    assert len(meta["sha256"]) == len(meta["source_sha256"]) == 64
    assert not meta["pit_authority"] and meta["pit_blocking"]
    assert ac.acquired_series() == {}
    diagnostic = ac.acquired_series(require_authority=False)
    assert len(diagnostic) == 1 and len(next(iter(diagnostic.values()))) == 220
    assert json.loads(ac.REPORT.read_text())["attempts"][0]["stored_series"]
    assert not list(store.glob("*.tmp"))


@pytest.mark.parametrize("contents", ["{", "[]", '{"series": []}'])
def test_corrupt_registry_is_preserved_and_not_read_as_new_ground(acquisition, contents):
    ac.REGISTRY.write_text(contents)
    with pytest.raises(ValueError):
        ac.acquire()
    assert ac.REGISTRY.read_text() == contents


def test_completed_endpoint_survives_next_fetch_interruption(acquisition, monkeypatch):
    _, urls = acquisition
    fetch = ac._fetch

    def interrupted(url):
        if url == urls[1]:
            raise KeyboardInterrupt("interrupted next endpoint")
        return fetch(url)

    monkeypatch.setattr(ac, "_fetch", interrupted)
    with pytest.raises(KeyboardInterrupt):
        ac.acquire()
    assert set(json.loads(ac.REGISTRY.read_text())["by_url"]) == {urls[0]}
    assert ac._endpoints(40) == [(urls[1], "official.example")]
    monkeypatch.setattr(ac, "_fetch", fetch)
    assert ac.acquire()["datasets_kept"] == 1
    assert ac.acquire()["endpoints_tried"] == 0


def test_yesterdays_endpoint_refreshes_without_overwriting_prior_snapshot(acquisition, monkeypatch):
    store, _ = acquisition
    ac.acquire(limit=1)
    reg = json.loads(ac.REGISTRY.read_text())
    before = next(iter(reg["series"].values()))
    original = (store / before["path"]).read_bytes()
    next(iter(reg["by_url"].values()))["at"] = "2000-01-01T00:00:00Z"
    ac.REGISTRY.write_text(json.dumps(reg))
    fetch = ac._fetch
    monkeypatch.setattr(ac, "_fetch", lambda url: (
        fetch(url)[0].replace(b",219", b",999"), "text/csv"))
    assert ac.acquire(limit=1)["datasets_kept"] == 1
    after = next(iter(json.loads(ac.REGISTRY.read_text())["series"].values()))
    assert before["path"] != after["path"]
    assert (store / before["path"]).read_bytes() == original


def test_failed_parquet_write_preserves_registry_and_retries_url(acquisition, monkeypatch):
    ac.acquire(limit=1)
    before = ac.REGISTRY.read_bytes()

    def fail(frame, path, **kwargs):
        Path(path).write_bytes(b"partial")
        raise OSError("disk write failed")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", fail)
    with pytest.raises(OSError, match="disk write failed"):
        ac.acquire()
    assert ac.REGISTRY.read_bytes() == before
    assert len(ac._endpoints(40)) == 1
    assert not list(ac.STORE.glob("*.tmp"))


def test_failed_registry_replace_preserves_prior_and_retries(acquisition, monkeypatch):
    ac.REGISTRY.write_text('{"by_url": {}, "series": {}}')
    before = ac.REGISTRY.read_bytes()
    original = ac.os.replace

    def fail(src, dst):
        if Path(dst) == ac.REGISTRY:
            raise PermissionError("registry directory denied")
        original(src, dst)

    monkeypatch.setattr(ac.os, "replace", fail)
    with pytest.raises(PermissionError, match="registry directory denied"):
        ac.acquire()
    assert ac.REGISTRY.read_bytes() == before
    assert len(ac._endpoints(40)) == 2


@pytest.mark.parametrize("foreign", [
    "C:\\opt\\quant\\data\\series.parquet", "/old/host/series.parquet"])
def test_copied_registry_paths_resolve_in_local_store(acquisition, foreign):
    s = pd.Series([1., 2.], index=pd.date_range("2020", periods=2, tz="UTC"), name="value")
    s.to_frame().to_parquet(ac.STORE / "series.parquet")
    ac.REGISTRY.write_text(json.dumps({"series": {"observed": {"path": foreign,
                                                             "pit_authority": False}}}))
    pd.testing.assert_series_equal(ac.acquired_series(require_authority=False)["observed"], s,
                                   check_freq=False)


def test_missing_file_is_retried_even_if_endpoint_is_marked_done_today(acquisition):
    _, urls = acquisition
    ac.REGISTRY.write_text(json.dumps({"by_url": {urls[0]: {
        "at": datetime.now(UTC).isoformat(), "series": ["missing"]}},
        "series": {"missing": {"path": "missing.parquet"}}}))
    assert ac._endpoints(1)[0][0] == urls[0]


def test_hourly_budget_reaches_acquirer_and_zero_budget_fetches_nothing(acquisition, monkeypatch):
    assert ac.acquire(budget_s=0)["endpoints_tried"] == 0
    monkeypatch.setitem(sys.modules, "acquire_datasets", ac)
    monkeypatch.setattr(ac, "acquire", lambda **kw: kw)
    assert hd.run_organ("acquire_datasets", 12.5) == {"result": {"budget_s": 12.5}}


def test_existing_writer_is_not_duplicated(acquisition):
    with job_lock.exclusive_job("acquire_datasets") as owned:
        assert owned
        with pytest.raises(RuntimeError, match="existing writer"):
            ac.acquire()
    assert not ac.REGISTRY.exists()
