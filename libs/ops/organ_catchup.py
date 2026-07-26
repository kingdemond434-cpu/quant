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
    artifacts: tuple[str, ...] = ()  # repo-relative deliverables; a fresh one = produced
    # (claude writes via FILE TOOLS, so a successful run can leave a ~58b log and
    #  megabytes of artifacts -- log size alone produced false 'never fired' verdicts)


# Priority order: the brain first (it advances clocks + triages), then diggers.
# Patterns/thresholds mirror scripts/max_audit.py ORGANS -- keep the two in sync.
ORGANS: tuple[OrganSpec, ...] = (
    OrganSpec("brain", "ops/run_cro_ai.sh", "20*_*.log", 2000, "run_cro_ai.sh",
              artifacts=()),   # EXCLUSIVITY (2026-07-26): the ledger is written by every commit and
              # several organs, and cadence_duties by run_cadence -- both made a dead cycle
              # read as produced (the 10:20 529-Overloaded death was never retried). No
              # exclusive artifact exists, so fall back to log size: weaker but honest.
    OrganSpec("dataaxis", "ops/run_dataaxis_dig.sh", "dataaxis_*.log", 1500,
              "run_dataaxis_dig.sh",
              artifacts=("docs/research/data_axis_watchlist.md",)),   # universe map is SHARED
    OrganSpec("prospector", "ops/run_prospector_dig.sh", "prospector_*.log", 1500,
              "run_prospector_dig.sh",
                            # coverage is SHARED with frontier and the brain -- not exclusive
              artifacts=("docs/research/prospector_watchlist.md",)),
    OrganSpec("litminer", "ops/run_litminer_dig.sh", "litminer_*.log", 1500,
              "run_litminer_dig.sh",
              artifacts=()),   # improvement_inbox is appended by many organs -- not exclusive
    OrganSpec("frontier", "ops/run_frontier_rotation.sh", "frontier_*.log", 1500,
              "run_frontier",
              artifacts=("docs/research/search_operator_library.md",)),   # coverage has THREE
              # writers (prospector dig, the 8 frontier prompts, run_cro_ai.sh)
    # WEEKLY: the deep cold audit must also complete once per INTERVAL even if its
    # Sunday 04:00Z window dies on a session limit -- otherwise it waits a full week.
    # TWO paths write logs here and the glob must see both: ops/run_deep_sweep.sh (what
    # catch-up fires) writes deep_sweep_<date>.log, while cron invokes the python directly
    # with `>> deep_sweep.log`. The cron redirect is the BETTER attempt marker -- it exists
    # the moment cron fires, even if the run dies before opening its own log. Matching only
    # the dated form meant deleting the failure stubs erased every attempt marker, and
    # organ_owed's `if not logs` branch then hid the weekly audit completely (07-26).
    OrganSpec("deep_sweep", "ops/run_deep_sweep.sh", "deep_sweep*.log", 1200,
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
        return False                      # a substantial log = clearly landed
    # ARTIFACT CHECK (2026-07-25): claude writes deliverables via file tools, so a SUCCESSFUL run
    # often leaves only the shell's start/exit header in the log. If any declared artifact was
    # written inside this interval, the organ produced -- re-firing it would burn a window on
    # already-completed work (frontier_en ran 3x on 07-25 for exactly this reason).
    # ARTIFACT MUST POSTDATE THIS ORGAN'S OWN ATTEMPT (2026-07-26). Organs SHARE artifacts --
    # the frontier rotation and prospector both write prospector_coverage.md -- so crediting any
    # write inside the period let frontier's dig silently mark prospector as produced, and two
    # genuine quota deaths were never retried. An artifact only counts if it landed AT OR AFTER
    # this organ's newest attempt, exactly as §33(17)(b) requires of a mined find's receipt.
    newest_attempt = max(p.stat().st_mtime for p in logs)
    repo = logdir.parent.parent if logdir.name == "cro_ai_logs" else logdir
    for rel in spec.artifacts:
        try:
            if (repo / rel).stat().st_mtime >= newest_attempt:
                return False
        except OSError:
            continue
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
