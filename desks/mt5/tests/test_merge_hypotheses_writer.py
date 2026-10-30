import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import job_lock
from research import merge_hypotheses as merger


def test_cli_defers_before_touching_sources_when_writer_is_busy(monkeypatch):
    claims = []

    @contextmanager
    def acquire(name, **kwargs):
        claims.append((name, kwargs))
        yield False

    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    def forbidden_merge():
        raise AssertionError("second writer ran")

    monkeypatch.setattr(merger, "main", forbidden_merge)
    assert merger.run_cli() == 75
    assert claims == [("merge_hypotheses", {"need_mb": 14000})]


def test_cli_keeps_writer_ownership_until_merge_returns(monkeypatch):
    active = False

    @contextmanager
    def acquire(name, **kwargs):
        nonlocal active
        active = True
        try:
            yield True
        finally:
            active = False

    def merge():
        assert active
        return 7

    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    monkeypatch.setattr(merger, "main", merge)
    assert merger.run_cli() == 7
    assert not active


def test_a_re_minted_row_keeps_its_earliest_first_seen():
    """Audit of #330: re-docketing never resets a cell's age (the pre-judge flag bound reads it)."""
    from datetime import UTC, datetime

    mh = merger
    now = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    row = {"first_seen": "2026-10-13T11:00:00+00:00"}
    mh.keep_earliest_first_seen(row, {"first_seen": "2026-10-01T00:00:00Z"}, now)
    assert row["first_seen"] == "2026-10-01T00:00:00Z"
    mh.keep_earliest_first_seen(row, {"first_seen": "2026-10-12T00:00:00+00:00"}, now)
    assert row["first_seen"] == "2026-10-01T00:00:00Z"
    fresh: dict = {}
    mh.keep_earliest_first_seen(fresh, {"merged_at": "garbage"}, now)
    assert fresh["first_seen"] == now.isoformat()
