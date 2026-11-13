"""Phase stamps: a killed organ still says where it died.

WHY THIS EXISTS (2026-11-03, dead-producer triage). `descendants`, `graveyard_resurrection`,
`axis_registry` and `qd_frontier` were killed at their leg caps on every pass for weeks (1,833 and
1,934 TIMEOUTs on the box's compute ledger), and a process killed at a cap writes no report. So the
only evidence of WHERE the time went was a profile someone had to run by hand on the trading box --
and a cProfile run of `descendants.build` did not return in 30 minutes. Each phase now overwrites
one small file before it starts, so the next kill leaves the slow phase named on disk:
`{"organ", "pid", "started_at", "phase", "phase_started_at", "elapsed_s", "phases": [...]}`.

It never raises: a stamp that cannot be written costs the stamp, never the organ's pass.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class PhaseStamp:
    """`stamp.enter("graph_fates")` before each phase; `stamp.done()` when the pass completes."""

    def __init__(self, organ: str, path: Path) -> None:
        self.organ = organ
        self.path = path
        self.t0 = time.monotonic()
        self.started_at = _now()
        self.phases: list[dict[str, Any]] = []
        self._phase_t0 = self.t0

    def _close_open_phase(self) -> None:
        if self.phases and "s" not in self.phases[-1]:
            self.phases[-1]["s"] = round(time.monotonic() - self._phase_t0, 2)

    def _write(self, phase: str, state: str) -> None:
        doc = {"organ": self.organ, "pid": os.getpid(), "started_at": self.started_at,
               "phase": phase, "state": state, "phase_started_at": _now(),
               "elapsed_s": round(time.monotonic() - self.t0, 2), "phases": self.phases}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
            try:
                os.replace(tmp, self.path)
            except OSError:                     # WinError 5 onto a held destination
                self.path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        except OSError:
            pass

    def enter(self, phase: str) -> None:
        self._close_open_phase()
        self._phase_t0 = time.monotonic()
        self.phases.append({"phase": phase, "at_s": round(self._phase_t0 - self.t0, 2)})
        self._write(phase, "RUNNING")

    def done(self) -> list[dict[str, Any]]:
        self._close_open_phase()
        self._write("done", "DONE")
        return list(self.phases)
