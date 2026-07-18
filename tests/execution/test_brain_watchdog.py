"""DRILL: simulate a brain-cycle failure and verify the auto-retry watchdog fires + de-dupes.

This is the 2026-07-18 self-heal drill (principal-requested): prove that a failed daily brain
cycle triggers an automatic re-run without human intervention, and that the trigger is
rate-limited and never fires for human-only conditions.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_alerts.py"
_SPEC = importlib.util.spec_from_file_location("run_alerts", _PATH)
assert _SPEC and _SPEC.loader
_M = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)

should = _M._brain_should_trigger
NOW = 1_800_000_000.0


def test_failed_cycle_auto_retries_after_reset() -> None:
    # brain cycle unhealthy today + past 11:00 UTC -> auto-retry fires (the 07-18 lost-day fix)
    assert should({}, set(), healthy_today=False, hour=13, now=NOW) == "auto-retry"


def test_healthy_cycle_does_not_trigger() -> None:
    assert should({}, set(), healthy_today=True, hour=13, now=NOW) is None


def test_no_trigger_before_reset_hour() -> None:
    # before ~11:00 UTC we don't retry (session limit may not have reset yet)
    assert should({}, set(), healthy_today=False, hour=9, now=NOW) is None


def test_remediable_alert_event_triggers() -> None:
    assert should({}, {"cadence_floor_violation"}, healthy_today=False, hour=9, now=NOW) == "event"


def test_human_only_alert_never_triggers() -> None:
    # deadman_latched / growth_defect are NOT in _EVENT_TRIGGER -> never loop the brain on them
    assert should({}, {"deadman_latched"}, healthy_today=True, hour=13, now=NOW) is None
    assert should({}, {"growth_defect"}, healthy_today=True, hour=13, now=NOW) is None


def test_rate_limited_to_one_per_3h() -> None:
    st = {"_brain_trigger": NOW - 1800}          # triggered 30 min ago
    assert should(st, set(), healthy_today=False, hour=13, now=NOW) is None
    st2 = {"_brain_trigger": NOW - 4 * 3600}     # triggered 4h ago -> allowed again
    assert should(st2, set(), healthy_today=False, hour=13, now=NOW) == "auto-retry"
