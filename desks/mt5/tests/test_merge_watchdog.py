import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import merge_hypotheses as merger


def test_ceiling_dumps_stacks_and_exits(tmp_path):
    hit = threading.Event()
    log = tmp_path / "stacks.log"
    stop = merger.start_watchdog(max_s=0.2, every_s=0, log_path=log, exit_fn=hit.set)
    try:
        assert hit.wait(5)
    finally:
        stop()
    text = log.read_text(encoding="utf-8")
    assert "armed" in text and "CEILING" in text
    assert "Thread" in text or "File" in text


def test_stop_disarms_before_ceiling(tmp_path):
    hit = threading.Event()
    stop = merger.start_watchdog(max_s=0.3, every_s=0, log_path=tmp_path / "s.log",
                                 exit_fn=hit.set)
    stop()
    time.sleep(0.6)
    assert not hit.is_set()


def test_periodic_dump_writes_stacks(tmp_path):
    log = tmp_path / "p.log"
    stop = merger.start_watchdog(max_s=60, every_s=0.2, log_path=log, exit_fn=lambda: None)
    time.sleep(0.7)
    stop()
    assert log.read_text(encoding="utf-8").count("Thread") >= 1


def test_run_cli_disarms_after_main(monkeypatch):
    from contextlib import contextmanager

    from research import job_lock

    @contextmanager
    def acquire(name, **kwargs):
        yield True

    events = []
    monkeypatch.setattr(job_lock, "exclusive_job", acquire)
    monkeypatch.setattr(merger, "start_watchdog",
                        lambda: (events.append("armed"), lambda: events.append("stopped"))[1])
    monkeypatch.setattr(merger, "main", lambda: events.append("main") or 0)
    assert merger.run_cli() == 0
    assert events == ["armed", "main", "stopped"]
