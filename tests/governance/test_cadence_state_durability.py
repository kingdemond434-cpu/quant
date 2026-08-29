"""The cadence engine must BANK completed duties even when a later one raises.

MEASURED 2026-08-05, live: OpenRouter balance -$0.59, so run_external_panel.py hung the full
720s; subprocess.TimeoutExpired propagated out of main(); and because cadence state is written
ONCE at the end of main(), data/cadence_state.json was never rewritten -- mtime stayed 07:13 while
the run ended at 23:03. Every duty that had already completed that cycle was forgotten.

The engine therefore had a single point of failure in an EXTERNAL PAID API: while credits are out
the panel cannot produce, so nothing ordered after it in main() can ever record that it ran, and
its timestamp stays stale forever. Stale timestamps are indistinguishable from "the cadence engine
is not running", which is exactly how cadence starvation has presented on this desk before.

FLOORS ARE NOT TOUCHED BY ANY OF THIS and the last test here pins that: _assert_floors still
raises through the finally, so a breached floor still fails the run loudly. What changed is only
whether work that ALREADY happened is remembered.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "_cadence", _ROOT / "scripts" / "run_cadence.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _isolate(m, tmp_path, monkeypatch):
    """Point the module's state files at tmp so no test can touch the live cadence."""
    state = tmp_path / "cadence_state.json"
    state.write_text(json.dumps({"last_panel": "2026-01-01T00:00:00+00:00"}), "utf-8")
    monkeypatch.setattr(m, "_STATE", state)
    monkeypatch.setattr(m, "_STAGE", tmp_path / "stage.json")
    return state


def test_state_is_persisted_even_when_a_duty_raises(tmp_path, monkeypatch):
    """THE regression. A hanging external API may not erase the rest of the cycle's work."""
    m = _mod()
    state = _isolate(m, tmp_path, monkeypatch)

    def _boom(now, st, stage, fired):
        st["last_meta_research"] = "2026-08-05T23:00:00+00:00"   # a duty that DID complete
        raise subprocess.TimeoutExpired(cmd="run_external_panel.py", timeout=720)

    monkeypatch.setattr(m, "_main_body", _boom)
    with pytest.raises(subprocess.TimeoutExpired):
        m.main()                       # the failure must still be LOUD
    saved = json.loads(state.read_text("utf-8"))
    assert saved["last_meta_research"] == "2026-08-05T23:00:00+00:00", (
        "a duty that completed before the exception must not be forgotten")


def test_a_breached_floor_still_raises(tmp_path, monkeypatch):
    """Floors are Tier-3-class. Banking state must not swallow a floor breach."""
    m = _mod()
    _isolate(m, tmp_path, monkeypatch)

    def _floor_breach(now, st, stage, fired):
        raise AssertionError("cadence floor breached")

    monkeypatch.setattr(m, "_main_body", _floor_breach)
    with pytest.raises(AssertionError):
        m.main()


def test_panel_timeout_returns_false_and_does_not_escape(monkeypatch):
    """A timed-out panel is a FAILED PANEL, not a failed cadence run.

    Returning False leaves the duty OWED, because the caller only stamps last_panel on True --
    strictly stricter than before, and no floor is involved.
    """
    m = _mod()
    calls = {"n": 0}

    def _fake_run(cmd, **kw):
        calls["n"] += 1
        if calls["n"] == 1:                       # the dossier regen succeeds
            return subprocess.CompletedProcess(cmd, 0, "", "")
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=720)

    monkeypatch.setattr(m.subprocess, "run", _fake_run)
    assert m._run_panel(None) is False


def test_successful_run_still_writes_state(tmp_path, monkeypatch):
    """The happy path is unchanged: state is written exactly once, with the duties recorded."""
    m = _mod()
    state = _isolate(m, tmp_path, monkeypatch)
    monkeypatch.setattr(m, "_main_body",
                        lambda now, st, stage, fired: st.__setitem__("last_panel", "2026-08-05"))
    m.main()
    assert json.loads(state.read_text("utf-8"))["last_panel"] == "2026-08-05"


# --------------------------------------------------------------------------------------------
# THE `finally` NEVER COVERED THE FAILURE THAT ACTUALLY HAPPENS HERE (regression, 2026-08-28).
#
# main()'s docstring promises to bank completed duties through "an OOM kill". A Python `finally`
# does not run on SIGTERM -- the default disposition terminates the process without unwinding --
# so that promise was false for the only failure mode the box was producing. quant-cadence.service
# was OOM-killed 35 times in 36 hours; each kill discarded the whole cycle's progress, the duties
# re-fired next tick and hit the same wall, and their timestamps stayed frozen. Six duties were
# owed, one 11.6x overdue and two never run. State now writes through on every stamp, which also
# survives SIGKILL -- no in-process handler can.
# --------------------------------------------------------------------------------------------

def test_a_stamp_is_on_disk_before_the_next_duty_starts(tmp_path, monkeypatch):
    """Write-through, not write-at-end: the guarantee the finally could not give."""
    m = _mod()
    state = _isolate(m, tmp_path, monkeypatch)
    seen = {}

    def _body(now, st, stage, fired):
        st["last_meta_research"] = "2026-08-28T12:00:00+00:00"
        # Read the FILE, mid-cycle, exactly as a kill would leave it.
        seen["mid_cycle"] = json.loads(state.read_text("utf-8"))
        raise RuntimeError("killed here")

    monkeypatch.setattr(m, "_main_body", _body)
    with pytest.raises(RuntimeError):
        m.main()
    assert seen["mid_cycle"].get("last_meta_research") == "2026-08-28T12:00:00+00:00", (
        "the stamp must be durable the moment it is made; anything later is lost to SIGKILL")


def test_the_state_write_is_atomic_and_leaves_no_partial_file(tmp_path, monkeypatch):
    """A torn state file reads as unparseable, and _days_since reads unparseable as 'never ran'.

    One kill mid-write would therefore re-fire EVERY duty at once -- strictly worse than the bug
    being fixed. So the write goes through a temp file and os.replace.
    """
    m = _mod()
    state = _isolate(m, tmp_path, monkeypatch)
    st = m._DurableState(state, {"a": 1})
    st["b"] = 2
    assert json.loads(state.read_text("utf-8")) == {"a": 1, "b": 2}
    assert not list(tmp_path.glob("*.tmp")), "the temp file must not survive the replace"


def test_update_also_writes_through(tmp_path, monkeypatch):
    """dict.update bypasses __setitem__; a stamp made that way must not be lost."""
    m = _mod()
    state = _isolate(m, tmp_path, monkeypatch)
    st = m._DurableState(state, {})
    st.update({"last_panel": "2026-08-28T00:00:00+00:00"})
    assert json.loads(state.read_text("utf-8"))["last_panel"] == "2026-08-28T00:00:00+00:00"


def test_a_real_sigterm_does_not_erase_a_completed_duty(tmp_path):
    """END TO END, with a real signal, because the unit test cannot prove the claim.

    This is the measured failure: systemd SIGTERMs the unit on the cgroup OOM event and on
    TimeoutStartSec. A `finally` does not run; a write-through does not need to.
    """
    import os
    import signal
    import time

    state = tmp_path / "cadence_state.json"
    state.write_text("{}", "utf-8")
    ready = tmp_path / "ready"
    driver = tmp_path / "driver.py"
    driver.write_text(f'''
import importlib.util, sys, time
from pathlib import Path
sys.path.insert(0, {str(_ROOT)!r})
spec = importlib.util.spec_from_file_location("_c", {str(_ROOT / "scripts" / "run_cadence.py")!r})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
m._STATE = Path({str(state)!r})
m._STAGE = Path({str(tmp_path / "stage.json")!r})
m._law_guard = lambda *a, **k: None
def body(now, st, stage, fired):
    st["last_meta_research"] = "2026-08-28T12:00:00+00:00"
    Path({str(ready)!r}).write_text("go", "utf-8")
    time.sleep(120)                      # the long duty that gets killed
m._main_body = body
m.main()
''', "utf-8")

    proc = subprocess.Popen([sys.executable, str(driver)])
    try:
        for _ in range(300):                      # wait for the stamp, up to 30s
            if ready.exists():
                break
            time.sleep(0.1)
        assert ready.exists(), "driver never reached the stamp"
        os.kill(proc.pid, signal.SIGTERM)
        rc = proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

    assert rc == -signal.SIGTERM or rc == 143, f"expected death by SIGTERM, got rc={rc}"
    saved = json.loads(state.read_text("utf-8"))
    assert saved.get("last_meta_research") == "2026-08-28T12:00:00+00:00", (
        "a duty that completed before the SIGTERM must survive it -- this is the exact loss that "
        "froze six deep-review duties for six weeks while the engine restarted every ten minutes")
