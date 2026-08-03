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
