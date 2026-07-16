"""``libs.ops`` — disaster recovery, backup, and operational resilience.

Consistent SQLite backups with checksum manifests, a restore drill that proves recoverability,
a heartbeat watchdog, and a fail-closed safe-halt controller that fuses the platform's hard stop
signals. Recommend-only decisions; the execution/risk layers enforce them.
"""

from __future__ import annotations

from libs.ops.backup import BackupManager, BackupManifest, RestoreDrill
from libs.ops.errors import OpsError
from libs.ops.watchdog import HaltDecision, ProcessWatchdog, SafeHaltController

__all__ = [
    "BackupManager",
    "BackupManifest",
    "HaltDecision",
    "OpsError",
    "ProcessWatchdog",
    "RestoreDrill",
    "SafeHaltController",
]
