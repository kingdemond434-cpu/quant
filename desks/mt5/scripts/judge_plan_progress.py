"""Name the step a judge sweep's "plan" phase is in, and how far it has got.

WHY (2026-10-20, box sweep started 21:34:49Z). `run_sharded_gauntlet` stamps phase "plan" before it
imports the sealed judge and changes it only when the first shard wave starts. That one phase holds:

* the lane locks and the docket read;
* gate 0 and the build preflight;
* the cache prune and the order;
* novelty and the yield allocation;
* the WHOLE pre-warm pool (now published as its own phase, "prewarm"), which runs until
  `_build_t0 + GAUNTLET_FRESH_BUDGET_SEC` (8,640 s on the box).

The last two plans took 9,302 s and 9,729 s. Nothing inside them was published until the pool's
closing "PRE-WARM:" line, so a plan 1h45m in could not be told from a hung one.

Two sources, and both are reports only. Neither can change a gate, a verdict, a trial count or a
time budget.

* **The judge's own log lines.** `PlanTracker.tee` wraps the sweep's log stream and moves
  `plan_step` when a line the sealed judge already prints marks a step boundary (`Gate 0:`,
  `docket order:`, ...). It works on today's sealed image unchanged.
* **The judge's progress hook,** when the sealed image has one (`PLAN_PROGRESS_HOOK`, patch
  `judge_plan_phase`). The judge reports its step and counts from inside each long loop (rows read,
  specs gated, pre-warm submitted/warmed/hit/failed, in flight, the oldest in-flight age and the
  seconds left in the budget). `attach` sets the hook only where the attribute exists.

Both write into the launcher's own phase document (`JUDGE_SWEEP_PHASE.json`). The resident already
folds that document into `JUDGE_RESIDENT.json` on every heartbeat, so the step is visible wherever
the phase already is.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: (pattern, step that RUNS AFTER the line). First match wins; matched only while phase == plan.
#: These are the sealed judge's own prints, in the order a plan emits them.
MARKERS: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), s) for p, s in (
    (r": waiting for room", "lane_admission_wait"),
    (r": room found", "docket"),
    (r"Loaded \d+ external survivors", "docket_grouping"),
    (r"^Unique cells to evaluate: \d+", "gate0"),
    (r"^PLAN RESUMED", "resumed"),
    (r"^PLAN RE-MADE", "gate0"),
    (r"^Gate 0: ", "preflight"),
    (r"^Build preflight: ", "cache_prune"),
    (r"^CACHE PRUNE: ", "order"),
    (r"^  (banned families|breadth|re-mint):", "order"),
    (r"^  novelty", "yield_allocation"),
    (r"^  docket order: ", "prewarm"),
    (r"^PRE-WARM START: ", "prewarm"),
    (r"^PRE-WARM: ", "plan_handoff"),
    (r"^PLAN PERSISTED", "plan_handoff"),
    (r"^SHARDED SWEEP: ", "dispatch"),
))
#: Counts read off the marker lines: (regex, field); the first group is the count.
COUNTS: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), f) for p, f in (
    (r"Loaded (\d+) external survivors", "docket_rows"),
    (r"^Unique cells to evaluate: (\d+)", "unique_cells"),
    (r"^Gate 0: (\d+) advance; (\d+) terminal", "gate0_advance"),
    (r"^PRE-WARM START: (\d+) cell", "prewarm_cells"),
    (r"^SHARDED SWEEP: (\d+) planned", "planned_cells"),
))
#: Steps that are SWEEP PHASES of their own (desk health, 2026-10-21: "publish prewarm as its own
#: phase"). The pre-warm pool is most of what used to read "plan" -- 8,640 s of a 9,729 s plan --
#: so it gets its own entry in `phases`, its own phase-start stamp and, under the stall watchdog,
#: its own SLOW threshold. The plan's earlier steps stay phase "plan"; the pool's closing line
#: through the first dispatch (`plan.pkl`, resume record) is "plan_handoff".
PHASE_OF_STEP = {"prewarm": "prewarm", "plan_handoff": "plan_handoff"}
#: The sweep phases this tracker reads lines in.
PLAN_PHASES = frozenset({"plan", *PHASE_OF_STEP.values()})
#: Seconds between progress writes; a step change always writes.
WRITE_EVERY_S = 15.0
#: The longest unfinished line kept while scanning for markers (a huge print is passed through,
#: never buffered without bound).
MAX_PENDING_CHARS = 8192


def _iso(t: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if t is None else t, UTC).isoformat(
        timespec="seconds")


class PlanTracker:
    """Hold the plan's step and progress inside `doc` (the launcher's phase document)."""

    def __init__(self, doc: dict[str, Any], path: Path, *, clock: Any = time.time,
                 on_phase: Any = None) -> None:
        self.doc, self.path, self.clock = doc, Path(path), clock
        #: The launcher's `_phase`: called when a step is a sweep phase of its own.
        self.on_phase = on_phase
        self._last_write = 0.0
        self._step_t: float | None = None

    # ---------------------------------------------------------------- state
    def _in_plan(self) -> bool:
        return self.doc.get("phase") in PLAN_PHASES

    def step(self, name: str, line: str | None = None) -> None:
        """Open step `name` (closing the current one) and write the phase document now."""
        now = self.clock()
        cur = self.doc.get("plan_step")
        if cur == name:
            if line:
                self.doc["plan_last_marker"] = line[:200]
            return
        steps = self.doc.setdefault("plan_steps", {})
        if cur and self._step_t is not None:
            steps[cur] = round(float(steps.get(cur, 0.0)) + now - self._step_t, 1)
        self._step_t = now
        self.doc["plan_step"] = name
        self.doc["plan_step_started_utc"] = _iso(now)
        if line:
            self.doc["plan_last_marker"] = line[:200]
        phase = PHASE_OF_STEP.get(name)
        if phase and self.on_phase is not None and self.doc.get("phase") != phase:
            try:
                self.on_phase(phase)        # writes the document itself
                return
            except Exception:
                pass
        self.flush(force=True)

    def progress(self, step: str | None = None, **counts: Any) -> None:
        """The sealed judge's hook: its step and counts from inside a loop."""
        if not self._in_plan():
            return
        clean = {k: v for k, v in counts.items() if isinstance(v, (int, float, str, type(None)))}
        self.doc["plan_progress"] = {"step": step or self.doc.get("plan_step"),
                                     "at": _iso(self.clock()), **clean}
        if step and step != self.doc.get("plan_step"):
            self.step(step)                 # a step change writes at once
        else:
            self.flush()

    def line(self, text: str) -> None:
        """One complete log line from the sweep."""
        if not self._in_plan():
            return
        for rx, field in COUNTS:
            m = rx.search(text)
            if m:
                self.doc.setdefault("plan_counts", {})[field] = int(m.group(1))
        for rx, name in MARKERS:
            if rx.search(text):
                self.step(name, text)
                return

    def flush(self, force: bool = False) -> None:
        now = self.clock()
        if not force and now - self._last_write < WRITE_EVERY_S:
            return
        self._last_write = now
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.plan.tmp")
            tmp.write_text(json.dumps({k: v for k, v in self.doc.items()
                                       if not str(k).startswith("_")}, indent=1, default=str),
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except (OSError, RuntimeError):
            # RuntimeError: `self.doc` is the launcher's `_PHASE_DOC`, and this flush iterates it
            # without `_PHASE_LOCK`; a dispatch thread changing it mid-walk raises "dictionary
            # changed size during iteration" (audit of a971d83da, should-fix 2). The stamp is
            # skipped, the next flush writes it.
            pass  # a progress stamp is a report; judging never stops for it

    # ---------------------------------------------------------------- wiring
    def tee(self, inner: Any) -> _Tee:
        return _Tee(inner, self)

    def attach(self, judge: Any) -> bool:
        """Give the sealed judge the hook, only where its image declares one."""
        if not hasattr(judge, "PLAN_PROGRESS_HOOK"):
            return False
        judge.PLAN_PROGRESS_HOOK = self.progress
        return True


class _Tee:
    """A text stream that passes everything through and shows each finished line to the tracker."""

    def __init__(self, inner: Any, tracker: PlanTracker) -> None:
        self._inner, self._tracker, self._pending = inner, tracker, ""

    def write(self, s: str) -> int:
        n = int(self._inner.write(s) or 0)
        try:
            if self._tracker._in_plan():
                self._pending += s
                if "\n" in self._pending:
                    *done, self._pending = self._pending.split("\n")
                    for ln in done:
                        self._tracker.line(ln)
                if len(self._pending) > MAX_PENDING_CHARS:
                    self._pending = ""
            else:
                self._pending = ""
        except Exception:
            pass  # never let a report break the log it reads
        return n

    def flush(self) -> None:
        self._inner.flush()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
