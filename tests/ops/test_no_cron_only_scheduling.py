"""No desk work may be scheduled by cron alone (CRO cycle 2026-08-28).

`cron.service` on this box reads `Active: failed (Result: oom-kill) since Thu 2026-08-20
20:48:44 UTC`, peak 3.1G on a 4GB machine, and restarting a system unit needs root that user
`quant` does not have by design. Every crontab line has been inert since. Six organs -- the unit
healer, the governance pulse, the auto-pusher, the bar-span ratchet, the restore drill and the
COT z-cache -- had no executor at all for eight days, and the guard that carries the only
"CRON IS NOT RUNNING" alarm was itself one of the six, so the outage suppressed its own alarm.

TWO PROPERTIES, both mechanical, both cheap:

1. ops/crontab.required demands nothing. A demanded line in a dead crontab READS as a fence and
   is not one; check_unit_health would merge it back and log "restored N fence line(s)", a
   work-shaped action with no effect sitting next to the honest alarm and blunting it. The
   file's own header forbids re-adding lines "to be safe" -- this is that prohibition with
   teeth.

2. The cron-liveness arm still exists in check_unit_health. It is the one thing on this box that
   says the scheduler is dead; a refactor that drops it restores the exact eight-day silence.

A schedule is not a scheduler, and a dead scheduler is indistinguishable from an unwired script
from the artifact side -- only one of them is fixed by wiring.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_crontab_required_demands_nothing_because_cron_cannot_run_it():
    """Every line here was migrated to a systemd user timer. Comments carry the mapping and the
    reason; a non-comment line is a fence that cannot fire."""
    req = ROOT / "ops" / "crontab.required"
    assert req.exists(), "the file must stay present -- check_unit_health's OSError branch " \
                         "reports 'guard cannot verify', which is weaker than an empty list"
    live = [ln for ln in req.read_text("utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]
    assert live == [], (
        "cron.service is OOM-dead and unrestartable without root, so these lines cannot run: "
        f"{live}. Give the organ a systemd user timer with a committed copy in ops/ instead.")


def test_the_cron_liveness_alarm_still_exists():
    """POSITIVE CONTROL for the alarm itself. Emptying the required list only stays safe while
    something still reports that the scheduler is dead."""
    src = (ROOT / "scripts" / "check_unit_health.py").read_text("utf-8")
    assert "CRON IS NOT RUNNING" in src, "the only cron-death alarm on this box was removed"
    assert '"systemctl", "is-active", "cron"' in src, \
        "the alarm must ask the DAEMON, not read a config file"
