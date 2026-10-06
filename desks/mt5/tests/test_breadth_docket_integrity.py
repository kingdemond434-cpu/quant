import json
from contextlib import contextmanager

import pytest

from libs.data.pit import is_stamped
from research import breadth_sweep, job_lock
from research import merge_hypotheses as mh


@pytest.fixture
def bank(tmp_path, monkeypatch):
    path = tmp_path / "docket.json"
    monkeypatch.setattr(breadth_sweep, "DOCKET", path)
    monkeypatch.setattr(mh, "DEFERRED_DIR", tmp_path / "deferred")

    @contextmanager
    def owned(name, **kwargs):
        assert name == "merge_hypotheses"
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", owned)
    return path


def test_corrupt_existing_bank_is_never_replaced(bank):
    bank.write_bytes(b"[truncated")
    with pytest.raises(ValueError):
        breadth_sweep.apply([{"symbol": "EURUSD", "family": "carry", "params": {}}])
    assert bank.read_bytes() == b"[truncated"


def test_stamps_new_rows_and_preserves_existing_records(bank):
    old = {"sym": "EURUSD", "family": "carry", "params": {}, "old_metadata": 7}
    bank.write_text(json.dumps([old]))
    same = {"symbol": "EURUSD", "family": "carry", "params": {}}
    new = {"symbol": "USDJPY", "family": "carry", "params": {}}
    assert breadth_sweep.apply([same, new, dict(new)]) == (1, 2)
    rows = json.loads(bank.read_text())
    assert rows[0] == old
    assert is_stamped(rows[1])
    assert len(list(bank.parent.iterdir())) == 1


def test_refused_lane_never_reads_or_publishes_bank(bank, monkeypatch):
    @contextmanager
    def refused(*args, **kwargs):
        yield False

    monkeypatch.setattr(job_lock, "exclusive_job", refused)
    monkeypatch.setattr(mh, "DEFER_BACKOFF_S", 0.0)
    assert breadth_sweep.apply([{"symbol": "EURUSD", "family": "carry", "params": {}}]) == (0, -1)
    assert not bank.exists()


def test_refused_lane_retries_then_defers_and_the_next_pass_merges_first(bank, monkeypatch):
    """Since 03dad3864 a refused lane RAISED and the pass's rows were lost. Now: bounded retry
    with backoff, then the rows persist and the next pass merges them before its own."""
    calls: list[int] = []
    naps: list[float] = []

    @contextmanager
    def refused(*args, **kwargs):
        calls.append(1)
        yield False

    monkeypatch.setattr(job_lock, "exclusive_job", refused)
    first = {"symbol": "EURUSD", "family": "carry", "params": {}}
    got = mh.merge_or_defer("breadth_sweep", [first],
                            lambda rows: breadth_sweep._apply_locked(rows, 10),
                            breadth_sweep._docket_key, attempts=3, backoff_s=5.0,
                            sleep=naps.append)
    assert got == (0, -1) and len(calls) == 3 and naps == [5.0, 10.0]
    assert mh.read_deferred("breadth_sweep") == [first]
    assert mh.LAST_MERGE["breadth_sweep"]["deferred"] == 1

    @contextmanager
    def owned(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", owned)
    second = {"symbol": "AUDUSD", "family": "carry", "params": {}}
    # The per-run cap admits ONE row: the deferred row is merged ahead of this pass's own.
    assert breadth_sweep.apply([second, dict(first)], max_new=1) == (1, 1)
    assert [r["symbol"] for r in json.loads(bank.read_text())] == ["EURUSD"]
    assert mh.read_deferred("breadth_sweep") == []
    assert not mh.deferred_path("breadth_sweep").exists()


def test_a_failed_merge_keeps_the_rows_for_the_next_pass(bank):
    bank.write_bytes(b"[truncated")
    row = {"symbol": "EURUSD", "family": "carry", "params": {}}
    with pytest.raises(ValueError):
        breadth_sweep.apply([row])
    assert mh.read_deferred("breadth_sweep") == [row]
