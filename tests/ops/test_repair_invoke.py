"""Tests for libs/ops/repair_invoke.py -- the shared rate limit on the repair organ.

Five fences invoke quant-gap-wirer.service and only ONE had a cooldown. The other four fired on
every breaching run at cadences as fast as 10 minutes, so a persistent breach -- the normal state
of a breach, since repair takes hours -- re-spawned a multi-hour Claude seat continuously. The
journal for one night: started 03:12 (OOM-killed), 03:20 (OOM-killed), 03:32 (47min, 1.6GB peak),
04:20, against a WEEKLY timer. Each start holds the desk-wide brain mutex, so the repair organ
was starving the discovery organs it exists to serve.
"""
from __future__ import annotations

import json
import time

from libs.ops import repair_invoke


def _harness(tmp_path, monkeypatch, *, running: bool = False):
    started: list[list[str]] = []
    monkeypatch.setattr(repair_invoke, "STAMP", tmp_path / "gap_wirer_last_fired")
    monkeypatch.setattr(repair_invoke, "_already_running", lambda: running)
    monkeypatch.setattr(repair_invoke.subprocess, "Popen", lambda argv, **k: started.append(argv))
    return started


def test_first_call_fires_and_second_is_rate_limited(tmp_path, monkeypatch) -> None:
    """The whole point: a breach that persists must not re-spawn the actuator every tick."""
    started = _harness(tmp_path, monkeypatch)

    assert repair_invoke.request_repair("first breach") is True
    assert len(started) == 1
    assert "quant-gap-wirer.service" in started[0]

    # A second fence, seconds later, sees the SAME stamp -- this is why the stamp is shared.
    assert repair_invoke.request_repair("a different fence, same window") is False
    assert len(started) == 1, "a five-fence pile-up inside one window is the defect itself"


def test_cooldown_expiry_re_fires(tmp_path, monkeypatch) -> None:
    """Rate-limited is not silenced: a breach outliving the window gets another repair run."""
    started = _harness(tmp_path, monkeypatch)
    repair_invoke.request_repair("first")
    (tmp_path / "gap_wirer_last_fired").write_text(
        json.dumps(time.time() - repair_invoke.COOLDOWN_S - 1), encoding="utf-8")

    assert repair_invoke.request_repair("still broken") is True
    assert len(started) == 2


def test_never_starts_a_second_seat_while_one_is_running(tmp_path, monkeypatch) -> None:
    """A run can outlive the cooldown -- the 03:32 run took 47 minutes and a full cycle takes
    hours. Two headless brains on one working tree is the contention the brain mutex exists to
    prevent; measured 2026-07-30, one agent committed a working tree it did not author."""
    started = _harness(tmp_path, monkeypatch, running=True)
    assert repair_invoke.request_repair("breach while busy") is False
    assert started == []


def test_missing_stamp_fires_rather_than_waits(tmp_path, monkeypatch) -> None:
    """Fail OPEN on an absent stamp. A fresh clone has never fired, so the honest reading of
    'no stamp' is 'never repaired', not 'repaired just now' -- the latter would silently
    suppress the first repair on every new box."""
    started = _harness(tmp_path, monkeypatch)
    assert not (tmp_path / "gap_wirer_last_fired").exists()
    assert repair_invoke.request_repair("fresh clone") is True
    assert len(started) == 1


def test_corrupt_stamp_fires_rather_than_waits(tmp_path, monkeypatch) -> None:
    """Same direction for an unparseable stamp: a broken rate-limiter must not be able to hold
    the repair path shut forever, which would be the outage it exists to shorten."""
    started = _harness(tmp_path, monkeypatch)
    (tmp_path / "gap_wirer_last_fired").write_text("not json", encoding="utf-8")
    assert repair_invoke.request_repair("corrupt stamp") is True
    assert len(started) == 1
