from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pandas as pd
import pytest
from research.parquet_publication import atomic_parquet


def test_reader_keeps_complete_generation_during_serialization(tmp_path):
    destination = tmp_path / "EURUSD_H1.parquet"
    old = pd.DataFrame({"close": [1.0, 2.0]})
    new = pd.DataFrame({"close": [3.0, 4.0]})
    old.to_parquet(destination)
    started, finish = Event(), Event()

    class SlowWriter:
        def to_parquet(self, path, **kwargs):
            Path(path).write_bytes(b"PAR1partial")
            started.set()
            assert finish.wait(10)
            new.to_parquet(path, **kwargs)

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(atomic_parquet, SlowWriter(), destination, compression="zstd")
        try:
            assert started.wait(10)
            for _ in range(20):
                pd.testing.assert_frame_equal(pd.read_parquet(destination), old)
        finally:
            finish.set()
        future.result(timeout=10)
    pd.testing.assert_frame_equal(pd.read_parquet(destination), new)
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_writer_preserves_previous_file_and_cleans_temporary(tmp_path):
    destination = tmp_path / "bars.parquet"
    pd.DataFrame({"close": [1.0]}).to_parquet(destination)
    previous = destination.read_bytes()

    class BrokenWriter:
        def to_parquet(self, path, **kwargs):
            Path(path).write_bytes(b"partial")
            raise OSError("serialization failed")

    with pytest.raises(OSError, match="serialization failed"):
        atomic_parquet(BrokenWriter(), destination)
    assert destination.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [destination]


def test_permission_refusal_never_overwrites_destination(tmp_path, monkeypatch):
    from research import parquet_publication

    destination = tmp_path / "bars.parquet"
    destination.write_bytes(b"previous")

    def denied(*args):
        raise PermissionError("publication denied")

    monkeypatch.setattr(parquet_publication.os, "replace", denied)
    with pytest.raises(PermissionError, match="publication denied"):
        atomic_parquet(pd.DataFrame({"close": [2.0]}), destination)
    assert destination.read_bytes() == b"previous"
    assert list(tmp_path.iterdir()) == [destination]
