import json
from contextlib import contextmanager

import pytest

from libs.data.pit import is_stamped
from research import breadth_sweep, job_lock


@pytest.fixture
def bank(tmp_path, monkeypatch):
    path = tmp_path / "docket.json"
    monkeypatch.setattr(breadth_sweep, "DOCKET", path)

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
    with pytest.raises(RuntimeError, match="writer lane"):
        breadth_sweep.apply([{"symbol": "EURUSD", "family": "carry", "params": {}}])
    assert not bank.exists()
