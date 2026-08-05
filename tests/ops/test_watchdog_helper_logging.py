"""The watchdog's per-tick helpers must leave evidence -- and must not be able to kill the tick.

Both halves are regressions the desk has already paid for:

  * `run_alerts.py` reports a failed pager push by PRINTING, not by raising or exiting nonzero.
    The watchdog captured that stdout and discarded it, so the only witness to a dead pager was
    thrown away every 3 minutes. The pager has since died silently twice.
  * `subprocess.run(timeout=...)` RAISES TimeoutExpired. Nothing caught it, so one slow helper
    aborted main() before the pager, the CRO daily cycle and the netlify publish ever ran.

These tests drive `_run_logged` against real child processes rather than mocks: the failure modes
being fenced are all about what a real child does to its parent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "watchdog.py"
_SPEC = importlib.util.spec_from_file_location("watchdog", _PATH)
assert _SPEC and _SPEC.loader
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


def _harness(tmp_path, monkeypatch):
    """Point the module at a throwaway log and run helpers under this interpreter."""
    log = tmp_path / "watchdog.log"
    monkeypatch.setattr(_M, "_WD_LOG", log)
    monkeypatch.setattr(_M, "_PY", sys.executable)
    return log


def test_failing_helper_output_reaches_the_log(tmp_path, monkeypatch) -> None:
    log = _harness(tmp_path, monkeypatch)
    _M._run_logged(["-c", "import sys; print('pager push failed: boom'); sys.exit(3)"],
                   "alerts", 30)
    body = log.read_text("utf-8")
    assert "pager push failed: boom" in body
    assert "watchdog/alerts" in body and "rc=3" in body


def test_stderr_alone_is_enough_to_log(tmp_path, monkeypatch) -> None:
    # exit 0 with a complaint on stderr is the shape a "best-effort" helper uses to fail quietly.
    log = _harness(tmp_path, monkeypatch)
    _M._run_logged(["-c", "import sys; print('warn: no channel armed', file=sys.stderr)"],
                   "alerts", 30)
    assert "no channel armed" in log.read_text("utf-8")


def test_clean_run_logs_nothing(tmp_path, monkeypatch) -> None:
    # Noise discipline: a log that grows every tick is a log nobody reads.
    log = _harness(tmp_path, monkeypatch)
    _M._run_logged(["-c", "print('all quiet')"], "data-health", 30)
    assert not log.exists()


def test_keep_stdout_records_a_successful_pager_tick(tmp_path, monkeypatch) -> None:
    # The pager's delivery count is wanted even on success -- that is the record of it running.
    log = _harness(tmp_path, monkeypatch)
    _M._run_logged(["-c", "print('alerts: 2 page(s) sent')"], "alerts", 30, keep_stdout=True)
    assert "alerts: 2 page(s) sent" in log.read_text("utf-8")


def test_timeout_is_caught_and_logged_not_raised(tmp_path, monkeypatch) -> None:
    # THE TICK-KILLER: an uncaught TimeoutExpired here disarmed every helper after it.
    log = _harness(tmp_path, monkeypatch)
    _M._run_logged(["-c", "import time; time.sleep(30)"], "leverage-opt", 1)
    assert "TIMEOUT after 1s" in log.read_text("utf-8")


def test_unspawnable_helper_does_not_raise(tmp_path, monkeypatch) -> None:
    log = _harness(tmp_path, monkeypatch)
    monkeypatch.setattr(_M, "_PY", str(tmp_path / "no-such-interpreter"))
    _M._run_logged(["-c", "print(1)"], "netlify", 5)
    assert "watchdog/netlify" in log.read_text("utf-8")


def test_log_is_capped_so_a_chatty_helper_cannot_fill_the_disk(tmp_path, monkeypatch) -> None:
    log = _harness(tmp_path, monkeypatch)
    monkeypatch.setattr(_M, "_WD_LOG_CAP", 4096)
    log.write_text("x" * 9000 + "\n", "utf-8")
    _M._append_log(["fresh line"])
    assert log.stat().st_size < 9000
    assert "fresh line" in log.read_text("utf-8")


def test_logging_failure_never_breaks_the_tick(tmp_path, monkeypatch) -> None:
    # A log path that cannot be written (here: a directory) must be swallowed, not propagated.
    monkeypatch.setattr(_M, "_PY", sys.executable)
    monkeypatch.setattr(_M, "_WD_LOG", tmp_path)          # a directory -> open("a") raises
    _M._run_logged(["-c", "import sys; sys.exit(1)"], "alerts", 30)
