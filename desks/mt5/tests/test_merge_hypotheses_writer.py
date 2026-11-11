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


def test_a_run_past_the_wall_dumps_its_stacks_and_exits_non_zero(monkeypatch):
    """Box 2026-11-11: one run blocked 16 h with zero CPU and I/O, holding the hourly trigger."""
    import faulthandler
    import threading

    armed, timers, exits = [], [], []
    monkeypatch.setattr(faulthandler, "dump_traceback_later",
                        lambda t, exit=False, file=None: armed.append((t, exit)))
    monkeypatch.setattr(faulthandler, "cancel_dump_traceback_later", lambda: armed.clear())

    class _Timer:
        def __init__(self, t, fn):
            self.t, self.fn, self.daemon, self.cancelled = t, fn, False, False
            timers.append(self)

        def start(self):
            pass

        def cancel(self):
            self.cancelled = True

    monkeypatch.setattr(threading, "Timer", _Timer)
    monkeypatch.setattr(merger.os, "_exit", lambda code: exits.append(code))
    assert merger._arm_wall(60.0) is True
    assert armed == [(60.0, False)] and timers[0].t == 61.0 and timers[0].daemon
    timers[0].fn()                                   # the wall passes
    assert exits == [merger.MERGE_WALL_EXIT] and merger.MERGE_WALL_EXIT != 0
    merger._disarm_wall()
    assert armed == [] and timers[0].cancelled
    assert merger._arm_wall(0) is False


def test_the_wall_is_disarmed_when_the_merge_returns_or_raises(monkeypatch):
    calls = []

    @contextmanager
    def acquire(name, **kwargs):
        yield True

    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    monkeypatch.setattr(merger, "_arm_wall", lambda wall_s=None: calls.append("arm") or True)
    monkeypatch.setattr(merger, "_disarm_wall", lambda: calls.append("disarm"))
    monkeypatch.setattr(merger, "main", lambda: 0)
    assert merger.run_cli() == 0 and calls == ["arm", "disarm"]

    def boom():
        raise RuntimeError("x")

    calls.clear()
    monkeypatch.setattr(merger, "main", boom)
    try:
        merger.run_cli()
    except RuntimeError:
        pass
    assert calls == ["arm", "disarm"]


def test_the_wall_waits_for_a_run_already_writing_its_ledgers(monkeypatch):
    """preregistrations.jsonl's reader stops at its first torn line: never exit mid-append."""
    import threading

    timers, exits, order = [], [], []
    monkeypatch.setattr(merger.os, "_exit", lambda code: exits.append(code))

    class _Timer:
        def __init__(self, t, fn):
            self.fn, self.daemon = fn, False
            timers.append(self)

        def start(self):
            pass

        def cancel(self):
            pass

    monkeypatch.setattr(threading, "Timer", _Timer)
    import faulthandler
    monkeypatch.setattr(faulthandler, "dump_traceback_later", lambda *a, **k: None)
    monkeypatch.setattr(faulthandler, "cancel_dump_traceback_later", lambda: None)
    assert merger._arm_wall(60.0)
    merger._enter_writes()
    t = threading.Thread(target=lambda: (timers[0].fn(), order.append("exit")))
    t.start()
    t.join(0.3)
    assert exits == [] and t.is_alive()              # held while the writes run
    order.append("writes done")
    merger._leave_writes()
    t.join(5)
    assert exits == [merger.MERGE_WALL_EXIT] and order == ["writes done", "exit"]
    merger._disarm_wall()

    monkeypatch.setattr(merger, "WRITE_GRACE_S", 0.05)
    exits.clear()
    merger._enter_writes()                           # a hang inside the writes still ends
    timers[0].fn()
    assert exits == [merger.MERGE_WALL_EXIT]
    merger._leave_writes()
