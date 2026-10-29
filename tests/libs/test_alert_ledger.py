"""AN ALERT THAT NOBODY CLOSES IS A NOTIFICATION, NOT A CONTROL LOOP.

Every ntfy path in this repo was a sender. `run_alerts.py` pushes to the principal's phone, dedupes
six hours, and stops; `data/.last_alerts.json` records when something last fired, which is dedup
state and not lifecycle. An alert firing every six hours forever was indistinguishable, on the
phone and on disk, from one that fired once and was fixed -- so the human had to tell them apart,
which is exactly the work the principal asked not to be doing.

The two properties these tests exist for: FIXED requires re-run evidence, and a condition that
returns after being fixed is a REGRESSION rather than a fresh alert.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.ops.alert_ledger import OPEN_STATES, Alert, AlertLedger


def _led(tmp_path) -> AlertLedger:
    return AlertLedger(tmp_path / "alerts.json")


def test_a_new_condition_opens(tmp_path) -> None:
    a = _led(tmp_path).observe("x", "broken")
    assert a.state == "OPEN" and a.open


def test_fixed_requires_a_rerun_not_an_absence_of_complaint(tmp_path) -> None:
    """A condition nobody re-tested is not fixed. Marking it so is the desk's own
    'not measured = fine' failure applied to its own repairs -- the worst place for it, because
    everything downstream trusts the all-clear."""
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.attempted("x", "ran the producer")
    assert led.alerts["x"].state == "ATTEMPTED", "running something is not fixing something"
    led.verify("x", still_firing=True)
    assert led.alerts["x"].state == "FAILED"


def test_a_verified_silence_closes_it(tmp_path) -> None:
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.attempted("x", "ran the producer")
    led.verify("x", still_firing=False)
    assert led.alerts["x"].state == "FIXED"
    assert not led.alerts["x"].open
    assert led.alerts["x"].fixed_at


def test_a_condition_returning_after_a_fix_is_a_regression(tmp_path) -> None:
    """Different information from a new alert: the fix did not hold. Reporting it as new lets the
    loop apply the same failing remediation forever while the attempt counter resets."""
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.attempted("x", "fix")
    led.verify("x", still_firing=False)
    led.observe("x", "broken again")
    assert led.alerts["x"].state == "REGRESSED"
    assert any("REGRESSED" in h for h in led.alerts["x"].history)


def test_needs_human_stays_open_but_is_never_retried_as_fixable(tmp_path) -> None:
    """It is not resolved -- it is not resolvable by the desk. Both facts have to survive."""
    led = _led(tmp_path)
    led.observe("x", "needs credits")
    led.needs_human("x", "funding, not engineering")
    assert led.alerts["x"].state == "NEEDS_HUMAN"
    assert led.alerts["x"].open
    assert "NEEDS_HUMAN" in OPEN_STATES


def test_absent_conditions_are_closed_but_needs_human_survives(tmp_path) -> None:
    """Leaving everything open forever turns the ledger into a graveyard nobody reads -- how the
    original pager failed. But a credit shortage does not stop being true because a sweep did not
    mention it this run."""
    led = _led(tmp_path)
    led.observe("gone", "was firing")
    led.observe("human", "needs credits")
    led.needs_human("human", "funding")
    cleared = led.resolve_absent(seen_ids=set())
    assert [c.id for c in cleared] == ["gone"]
    assert led.alerts["human"].state == "NEEDS_HUMAN"


def test_escalation_covers_what_the_desk_tried_and_could_not(tmp_path) -> None:
    led = _led(tmp_path)
    led.observe("f", "x")
    led.attempted("f", "try")
    led.verify("f", still_firing=True)
    assert [e.id for e in led.escalations()] == ["f"]


def test_a_fresh_human_only_alert_does_not_page_immediately(tmp_path) -> None:
    """Paging at 3am about a credit top-up is how a pager gets muted, and a muted pager is worse
    than none."""
    led = _led(tmp_path)
    led.observe("h", "needs credits")
    led.needs_human("h", "funding")
    assert led.escalations(min_age_h=24.0) == []


def test_an_aged_human_only_alert_does_page(tmp_path) -> None:
    led = _led(tmp_path)
    led.observe("h", "needs credits")
    led.needs_human("h", "funding")
    led.alerts["h"].first_seen = (datetime.now(tz=UTC) - timedelta(days=3)).isoformat()
    assert [e.id for e in led.escalations(min_age_h=24.0)] == ["h"]


def test_the_lifecycle_survives_the_process(tmp_path) -> None:
    """A lifecycle that dies with the process is not one."""
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.attempted("x", "ran it")
    led.save()
    again = AlertLedger(tmp_path / "alerts.json")
    assert again.alerts["x"].state == "ATTEMPTED"
    assert again.alerts["x"].attempts == 1


def test_an_unknown_field_on_disk_does_not_crash_the_load(tmp_path) -> None:
    """A ledger that refuses to load after a schema change loses every open alert silently."""
    p = tmp_path / "alerts.json"
    p.write_text('{"alerts": {"x": {"state": "OPEN", "message": "m", "future_field": 1}}}', "utf-8")
    assert AlertLedger(p).alerts["x"].state == "OPEN"


def test_a_corrupt_ledger_starts_empty_rather_than_raising(tmp_path) -> None:
    p = tmp_path / "alerts.json"
    p.write_text("{not json", "utf-8")
    assert AlertLedger(p).alerts == {}


def test_age_is_measured_from_first_seen(tmp_path) -> None:
    a = Alert(id="x", first_seen=(datetime.now(tz=UTC) - timedelta(hours=5)).isoformat())
    assert 4.9 < a.age_hours() < 5.1


# v5e (2026-10-21): save() is atomic -- temp file, fsync, os.replace under a lock -- and retries
# a Windows PermissionError from os.replace.
def test_save_is_atomic_and_leaves_no_temp_or_lock(tmp_path) -> None:
    import json
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.save()
    assert json.loads((tmp_path / "alerts.json").read_text("utf-8"))["alerts"]["x"]["state"] \
        == "OPEN"
    # the OS lock's sidecar stays (v5f: deleting it races other openers); no temp file does
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alerts.json", "alerts.json.flock"]


def test_save_retries_a_permission_error_from_replace(tmp_path, monkeypatch) -> None:
    import os

    from libs.ops import alert_ledger as al
    real = os.replace
    calls: list[int] = []

    def flaky(a, b) -> None:
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("in use (WinError 5)")
        real(a, b)

    monkeypatch.setattr(al.os, "replace", flaky)
    monkeypatch.setattr(al.time, "sleep", lambda s: None)
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.save()
    assert len(calls) == 3 and AlertLedger(tmp_path / "alerts.json").alerts["x"].open
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alerts.json", "alerts.json.flock"]


def test_concurrent_saves_never_tear_the_ledger(tmp_path) -> None:
    import json
    import threading
    errors: list[BaseException] = []

    def writer(i: int) -> None:
        try:
            for j in range(20):
                led = _led(tmp_path)
                led.observe(f"a{i}", f"m{j}")
                led.save()
                json.loads((tmp_path / "alerts.json").read_text("utf-8"))
        except BaseException as exc:   # collected and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["alerts.json", "alerts.json.flock"]
    # v5f: every writer's alert survives -- the save merges under the lock, never a stale copy
    assert set(AlertLedger(tmp_path / "alerts.json").alerts) == {f"a{i}" for i in range(6)}


def test_a_leftover_v5e_lock_file_never_blocks_a_writer(tmp_path) -> None:
    """The v5e O_EXCL lock file is not the lock any more: an orphan one is ignored, not broken."""
    import os
    import time
    lock = tmp_path / "alerts.json.lock"
    lock.write_text("")
    old = time.time() - 3600
    os.utime(lock, (old, old))
    led = _led(tmp_path)
    led.observe("x", "broken")
    led.save()
    assert (tmp_path / "alerts.json").exists()


# v5f (2026-10-21, audit on v5e): load, modify and save under ONE lock; never save over a ledger
# that failed to read; and a lock two processes can never hold at once.
_HOLD = """
import sys, time
from pathlib import Path
from libs.ops.alert_ledger import os_lock
lock, log, n = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
for _ in range(n):
    with os_lock(lock, timeout_s=60):
        with open(log, "a") as fh:
            fh.write("in\\n"); fh.flush()
        time.sleep(0.01)
        with open(log, "a") as fh:
            fh.write("out\\n"); fh.flush()
"""


def test_two_processes_never_hold_the_lock_at_once(tmp_path) -> None:
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    lock, log = tmp_path / "x.flock", tmp_path / "log.txt"
    procs = [subprocess.Popen([sys.executable, "-c", _HOLD, str(lock), str(log), "15"],
                              cwd=str(root)) for _ in range(3)]
    assert [p.wait(timeout=120) for p in procs] == [0, 0, 0]
    lines = log.read_text().split()
    assert len(lines) == 90
    assert lines == ["in", "out"] * 45, "two holders interleaved inside the lock"


def test_a_holder_that_dies_releases_the_lock(tmp_path) -> None:
    import subprocess
    import sys
    from pathlib import Path

    from libs.ops.alert_ledger import os_lock
    root = Path(__file__).resolve().parents[2]
    lock = tmp_path / "x.flock"
    code = ("import os, sys; from pathlib import Path; from libs.ops.alert_ledger import os_lock\n"
            "with os_lock(Path(sys.argv[1])):\n    os._exit(0)\n")
    subprocess.run([sys.executable, "-c", code, str(lock)], cwd=str(root), check=True,
                   timeout=60)
    with os_lock(lock, timeout_s=2):   # no stale state to break: the kernel released it
        pass


def test_a_held_lock_raises_busy_and_never_proceeds_unlocked(tmp_path) -> None:
    import pytest

    from libs.ops.alert_ledger import AlertLedgerBusy, os_lock
    p = tmp_path / "alerts.json"
    led = AlertLedger(p)
    led.observe("x", "m")
    with os_lock(p.with_name("alerts.json.flock")), pytest.raises(AlertLedgerBusy):
        from libs.ops import alert_ledger as al
        with al.os_lock(p.with_name("alerts.json.flock"), timeout_s=0.2):
            pass
    assert not p.exists()


def test_a_ledger_that_fails_to_read_is_never_saved_over(tmp_path, monkeypatch) -> None:
    import pytest

    from libs.ops.alert_ledger import AlertLedgerUnreadable
    p = tmp_path / "alerts.json"
    good = _led(tmp_path)
    good.observe("keep", "an open alert")
    good.save()
    before = p.read_bytes()
    real = type(p).read_text

    def flaky(self, *a, **k):
        if self == p:
            raise PermissionError("transient (WinError 32)")
        return real(self, *a, **k)

    monkeypatch.setattr(type(p), "read_text", flaky)
    led = AlertLedger(p)
    assert led.alerts == {} and led.load_error and "PermissionError" in led.load_error
    led.observe("new", "m")
    with pytest.raises(AlertLedgerUnreadable):
        led.save()
    with pytest.raises(AlertLedgerUnreadable), AlertLedger.transaction(p) as t:
        t.observe("new", "m")
    monkeypatch.setattr(type(p), "read_text", real)
    assert p.read_bytes() == before, "a transient read failure emptied the ledger"


def test_a_save_after_a_transient_failure_merges_onto_what_is_on_disk(
        tmp_path, monkeypatch) -> None:
    p = tmp_path / "alerts.json"
    good = _led(tmp_path)
    good.observe("keep", "an open alert")
    good.save()
    real = type(p).read_text
    calls = {"n": 0}

    def once(self, *a, **k):
        if self == p and calls["n"] == 0:
            calls["n"] += 1
            raise PermissionError("transient")
        return real(self, *a, **k)

    monkeypatch.setattr(type(p), "read_text", once)
    led = AlertLedger(p)          # this read failed ...
    led.observe("new", "m")
    led.save()                    # ... the save re-reads under the lock and merges
    assert set(AlertLedger(p).alerts) == {"keep", "new"}


def test_a_stale_copy_never_overwrites_another_writers_alert(tmp_path) -> None:
    p = tmp_path / "alerts.json"
    a, b = AlertLedger(p), AlertLedger(p)
    a.observe("from_a", "m")
    b.observe("from_b", "m")
    a.save()
    b.save()
    assert set(AlertLedger(p).alerts) == {"from_a", "from_b"}


def test_a_transaction_holds_the_lock_from_read_to_write(tmp_path) -> None:
    import threading

    p = tmp_path / "alerts.json"
    for i in range(5):
        with AlertLedger.transaction(p) as t:
            t.observe(f"seed{i}", "m")

    def bump() -> None:
        for _ in range(10):
            with AlertLedger.transaction(p) as t:
                a = t.alerts.get("n") or t.observe("n", "counter")
                a.attempts += 1

    threads = [threading.Thread(target=bump) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    led = AlertLedger(p)
    assert led.alerts["n"].attempts == 40, "a read-modify-write was lost"
    assert len(led.alerts) == 6


def test_an_unparseable_ledger_is_set_aside_never_lost(tmp_path) -> None:
    p = tmp_path / "alerts.json"
    p.write_text("{not json", "utf-8")
    led = AlertLedger(p)
    led.observe("x", "m")
    led.save()
    assert AlertLedger(p).alerts["x"].open
    kept = [q for q in tmp_path.iterdir() if q.name.startswith("alerts.json.unparseable-")]
    assert len(kept) == 1 and kept[0].read_text("utf-8") == "{not json"
