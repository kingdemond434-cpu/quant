"""``libs.ops`` — disaster recovery, backup, and operational resilience.

Consistent SQLite backups with checksum manifests, a restore drill that proves recoverability,
a heartbeat watchdog, and a fail-closed safe-halt controller that fuses the platform's hard stop
signals. Recommend-only decisions; the execution/risk layers enforce them.

WHY THE RE-EXPORTS ARE LAZY (gap-fixer 2026-08-28). This file used to import ``backup``,
``errors`` and ``watchdog`` eagerly. Python runs a package's ``__init__`` before ANY submodule,
so ``from libs.ops.disk import headroom`` -- a helper whose own imports are ``shutil``,
``pathlib`` and ``typing`` -- paid for all three. ``watchdog`` reaches ``libs.risk.drawdown`` and
``backup`` reaches ``libs.store.connection``, so the chain ended in **numpy and scipy**.

MEASURED on this box: ``libs.ops.disk`` cost **107.5 MB** through the package and **13.8 MB**
loaded alone -- 93.7 MB per process, to reach a disk-space helper. **255 files import
``libs.ops.*``, 157 of them in ``scripts/``**: the timer-driven organs, dozens of which run
concurrently on a 3.8 GB box with NO SWAP. That is the memory story behind the OOM storm the
fences kept reporting as individual unit failures -- ``quant-cadence`` killed 37 times in 24h
(18 of 55 runs completed) and the auto-push guard 19 times, each one looking like its own bug.

PEP 562 keeps the public API byte-identical: ``from libs.ops import BackupManager`` still works
and still returns the same object, it is just resolved on first touch and then cached in
``globals()`` so the second access is an ordinary dict lookup. ``__getattr__`` raises
``AttributeError`` -- never ``ImportError`` -- because ``from libs.ops import desk_host`` relies
on that failure to fall through to the normal submodule import, and eight test modules do
exactly that.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # keeps mypy and editors resolving these exactly as the eager form did
    from libs.ops.backup import BackupManager, BackupManifest, RestoreDrill
    from libs.ops.errors import OpsError
    from libs.ops.watchdog import HaltDecision, ProcessWatchdog, SafeHaltController

#: public name -> the submodule that defines it. Adding a re-export means adding it here AND to
#: ``__all__``; the test pins the two lists against each other so they cannot drift apart.
_LAZY: dict[str, str] = {
    "BackupManager": "libs.ops.backup",
    "BackupManifest": "libs.ops.backup",
    "RestoreDrill": "libs.ops.backup",
    "OpsError": "libs.ops.errors",
    "HaltDecision": "libs.ops.watchdog",
    "ProcessWatchdog": "libs.ops.watchdog",
    "SafeHaltController": "libs.ops.watchdog",
}

__all__ = [
    "BackupManager",
    "BackupManifest",
    "HaltDecision",
    "OpsError",
    "ProcessWatchdog",
    "RestoreDrill",
    "SafeHaltController",
]


if not TYPE_CHECKING:  # HIDDEN FROM MYPY ON PURPOSE -- see below

    def __getattr__(name: str) -> Any:
        module = _LAZY.get(name)
        if module is None:
            # AttributeError, not ImportError: `from libs.ops import <submodule>` depends on
            # this raising so the import machinery falls through to importing the submodule.
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        value = getattr(importlib.import_module(module), name)
        globals()[name] = value
        return value


# WHY `if not TYPE_CHECKING` (gap-fixer 2026-08-29). A module-level ``__getattr__`` returning
# ``Any`` tells mypy that EVERY attribute of ``libs.ops`` exists. MEASURED before this guard:
# `from libs.ops import totally_bogus_module_xyz` type-checked clean, and the deliberate
# fail-closed `# type: ignore[attr-defined]` in libs/ops/deepseek_cycle.py:249 turned
# `[unused-ignore]` -- which is how this was found: it took ops/gates.sh RED, and a red gate
# blocks the pre-push hook for EVERY organ on the box, so nothing could push at all.
# 255 files import ``libs.ops.*`` (157 of them in scripts/); silently accepting a typo or a
# deleted submodule in any of them is a gate that passes 100% of the time, which carries zero
# information (RESEARCH §6, gate-optimality).
# Hiding the function from mypy costs NOTHING at runtime -- ``TYPE_CHECKING`` is False there,
# so the lazy resolution and its measured 93.7 MB/process saving are byte-for-byte unchanged --
# while mypy falls back to the ``if TYPE_CHECKING`` re-exports above plus ordinary submodule
# resolution, exactly what the eager form gave it. Both properties, no trade.


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY))
