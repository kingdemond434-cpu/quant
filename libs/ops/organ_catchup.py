"""Quota-death organ catch-up: re-fire scheduled claude organs that died at birth.

2026-07-24: the Max-plan credit pool exhausted mid-day and EVERY scheduled organ (brain
08:45, dataaxis 14:00, frontier 15:00, prospector 18:00, litminer 19:00) died with
"out of usage credits" and stayed dead until its next timer fire a full day later --
the principal had to re-fire organs by hand after the 23:00 reset. This module is the
decision core of the automatic version: once quota is back, re-fire each organ whose
day's run died, one per tick, oldest-priority first.

Deliberately narrow: an organ is owed ONLY if its timer already fired today (an attempt
log exists) and no success-sized log exists today. First fires of the day stay owned by
systemd/cron schedules; this is a retry layer, never a scheduler.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# newest attempt must be at least this old before a re-fire (protects a running organ
# whose log is still small, and spaces retries so a dead quota window is probed slowly)
RETRY_COOLDOWN_S = 45 * 60


@dataclass(frozen=True)
class OrganSpec:
    name: str
    script: str          # bash entrypoint under ops/
    pattern: str         # log glob under data/cro_ai_logs/
    success_bytes: int   # a log this size or larger counts as a real run (max_audit parity)
    pgrep: str           # substring identifying a live run of this organ
    period_days: int = 1  # 1 = daily organ; 7 = weekly (widens the owed window)


# Priority order: the brain first (it advances clocks + triages), then diggers.
# Patterns/thresholds mirror scripts/max_audit.py ORGANS -- keep the two in sync.
ORGANS: tuple[OrganSpec, ...] = (
    OrganSpec("brain", "ops/run_cro_ai.sh", "20*_*.log", 2000, "run_cro_ai.sh"),
    OrganSpec("dataaxis", "ops/run_dataaxis_dig.sh", "dataaxis_*.log", 1500, "run_dataaxis_dig.sh"),
    OrganSpec("prospector", "ops/run_prospector_dig.sh", "prospector_*.log", 1500,
              "run_prospector_dig.sh"),
    OrganSpec("litminer", "ops/run_litminer_dig.sh", "litminer_*.log", 1500, "run_litminer_dig.sh"),
    OrganSpec("frontier", "ops/run_frontier_rotation.sh", "frontier_*.log", 1500,
              "run_frontier"),
    # WEEKLY: the deep cold audit must also complete once per INTERVAL even if its
    # Sunday 04:00Z window dies on a session limit -- otherwise it waits a full week.
    OrganSpec("deep_sweep", "ops/run_deep_sweep.sh", "deep_sweep_*.log", 2500,
              "run_deep_sweep", period_days=7),
)


def _window_logs(logdir: Path, pattern: str, now: datetime, period_days: int = 1) -> list[Path]:
    """Logs inside this organ's CURRENT scheduling interval. Daily organs look at today; a
    weekly organ looks back over its whole period, so a sweep killed on Sunday stays owed all
    week instead of silently waiting for the next timer."""
    cut = now.astimezone(UTC).timestamp() - period_days * 86400
    out = []
    for p in logdir.glob(pattern):
        try:
            if p.stat().st_mtime >= cut:
                out.append(p)
        except OSError:
            continue
    return out


def organ_owed(spec: OrganSpec, logdir: Path, now: datetime) -> bool:
    """Owed = attempted within this interval, no success-sized log in it, newest
    attempt past cooldown. Interval = spec.period_days (daily or weekly)."""
    logs = _window_logs(logdir, spec.pattern, now, spec.period_days)
    if not logs:
        return False                      # timer has not fired yet today -- not ours to start
    if any(p.stat().st_size >= spec.success_bytes for p in logs):
        return False                      # a real run already landed today
    newest = max(p.stat().st_mtime for p in logs)
    return (now.timestamp() - newest) >= RETRY_COOLDOWN_S


def pick_organ(
    logdir: Path,
    now: datetime,
    is_running: Callable[[str], bool],
) -> OrganSpec | None:
    """The single highest-priority owed organ that is not currently running, else None."""
    for spec in ORGANS:
        if is_running(spec.pgrep):
            continue
        if organ_owed(spec, logdir, now):
            return spec
    return None
