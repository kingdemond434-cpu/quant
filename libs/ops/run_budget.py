"""ONE DEADLINE FOR THE WHOLE RUN -- the shared shape for every `--budget-s` organ.

THE DEFECT THIS EXISTS FOR (measured on the trading box 2026-10-29). `MT5-IndependenceIntake`
runs `independence_intake.py --once --budget-s 600` every 15 minutes under IgnoreNew with a 20
minute ExecutionTimeLimit. It sat in `Running` for more than 100 minutes, and every run due in
that window was dropped. The organ DID check its budget -- once, inside the grid filler, after
reading ~400k registry rows, grouping the whole candidate table for donors (twice) and building
the grid, none of which looked at the clock. A budget that is checked by one stage is a budget
for that stage; the rest of the run is unbounded, and an unbounded run on an IgnoreNew clock is
a dead clock.

THE SHAPE, three layers, each one cheap:

    RunBudget(budget_s)       one monotonic deadline, created at the TOP of the run. Stages ask
                              it `expired()` / `remaining()` between steps, and `stage()` records
                              what each step cost and which were skipped, so a partial artifact
                              names exactly what it did not do.
    guard(conn)               a SQLite progress handler that interrupts a query once the deadline
                              has passed. A full-table GROUP BY is the step that never returns;
                              this is what makes it return (sqlite3.OperationalError: interrupted).
    watchdog(grace_s, ...)    the backstop for anything the first two cannot reach (a lock wait,
                              a C call, a hung import). A daemon timer that, at budget + grace,
                              runs the organ's own "publish what you have, marked partial"
                              callback and then exits the process with EXIT_OVERRUN. The
                              scheduler's limit is then never the thing that stops the organ.

`python -u` (or PYTHONUNBUFFERED) is the other half: a log that only appears at exit cannot
show a run in progress. The installers' fence is `desks/mt5/tests/test_task_logs_are_unbuffered.py`.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

#: The exit code of a run the watchdog stopped. Distinct from 1 (an error) and 0 (done), so a
#: scheduler's LastTaskResult says "overran its own budget" and nothing else.
EXIT_OVERRUN = 124


class RunBudget:
    """A single deadline for a whole run, with a record of what each stage cost."""

    def __init__(self, budget_s: float, *, clock: Callable[[], float] = time.monotonic) -> None:
        self.budget_s = float(budget_s)
        self._clock = clock
        self.started = clock()
        self.deadline = self.started + self.budget_s
        self.stages: list[dict[str, Any]] = []
        self.skipped: list[str] = []
        self._timer: threading.Timer | None = None

    # -- the clock ---------------------------------------------------------------------------
    def elapsed(self) -> float:
        return self._clock() - self.started

    def remaining(self) -> float:
        return self.deadline - self._clock()

    def expired(self) -> bool:
        return self._clock() >= self.deadline

    # -- stages ------------------------------------------------------------------------------
    @contextlib.contextmanager
    def stage(self, name: str) -> Iterator[bool]:
        """`with rb.stage("donors") as go: if go: ...` -- go is False once the deadline passed.

        A skipped stage is recorded, never silent: the artifact's `stages` list is how a reader
        tells "ran and found nothing" from "never ran".
        """
        if self.expired():
            self.skipped.append(name)
            self.stages.append({"stage": name, "skipped": True,
                                "why": f"run deadline ({self.budget_s:g}s) already passed"})
            yield False
            return
        t0 = self._clock()
        row: dict[str, Any] = {"stage": name, "skipped": False}
        self.stages.append(row)
        try:
            yield True
        finally:
            row["elapsed_s"] = round(self._clock() - t0, 3)
            if self._clock() >= self.deadline:
                row["overran_deadline"] = True

    def summary(self) -> dict[str, Any]:
        return {"budget_s": self.budget_s, "elapsed_s": round(self.elapsed(), 3),
                "stages": list(self.stages), "skipped_stages": list(self.skipped),
                "expired": self.expired()}

    # -- SQLite -------------------------------------------------------------------------------
    def guard(self, conn: Any, every: int = 10_000) -> Any:
        """Interrupt any query on `conn` once the run deadline passes. Returns conn.

        A connection that cannot take a progress handler (a test double) is returned unchanged.
        """
        with contextlib.suppress(AttributeError, TypeError):
            conn.set_progress_handler(lambda: 1 if self.expired() else 0, int(every))
        return conn

    # -- the backstop --------------------------------------------------------------------------
    def watchdog(self, grace_s: float, on_expire: Callable[[], None] | None = None, *,
                 name: str = "run", exit_code: int = EXIT_OVERRUN,
                 _exit: Callable[[int], None] = os._exit) -> threading.Timer:
        """At budget + grace: publish what the run has (on_expire), say so, and exit.

        The cooperative checks above are how a run ends on time; this is how it ends when one of
        them could not fire. Daemon, so a run that finishes normally is never held open by it.
        """
        def _fire() -> None:
            try:
                if on_expire is not None:
                    on_expire()
            except BaseException as exc:                                 # pragma: no cover
                print(f"{name}: watchdog publish failed ({type(exc).__name__}: {exc})",
                      file=sys.stderr)
            print(f"{name}: OVERRAN its own budget ({self.budget_s:g}s + {grace_s:g}s grace) "
                  f"after {self.elapsed():.0f}s; published partial and exiting {exit_code}",
                  flush=True)
            with contextlib.suppress(Exception):
                sys.stdout.flush()
                sys.stderr.flush()
            _exit(exit_code)

        delay = max(0.0, self.remaining() + float(grace_s))
        timer = threading.Timer(delay, _fire)
        timer.daemon = True
        timer.start()
        self._timer = timer
        return timer

    def disarm(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def unbuffer_stdio() -> None:
    """Line-buffer stdout/stderr when they are redirected to a file -- the in-process half of
    `python -u`, for an organ started by a launcher that forgot the flag."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError, OSError):
            stream.reconfigure(line_buffering=True)  # type: ignore[union-attr]
