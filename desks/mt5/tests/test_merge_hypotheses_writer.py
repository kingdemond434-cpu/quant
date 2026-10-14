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


def test_a_duplicate_row_never_drops_the_later_screen_read():
    """Audit must-fix 2 on the gauntlet patch for #392: the first row per identity is kept, so
    the latest `screen_read_until` across the duplicates must be folded into it."""
    kept = {"family": "f"}
    merger.keep_latest_screen_read(kept, {"screen_read_until": "2024-05-01"})
    merger.keep_latest_screen_read(kept, {"screen_read_until": "2023-01-01"})
    merger.keep_latest_screen_read(kept, {})
    assert kept["screen_read_until"] == "2024-05-01"
