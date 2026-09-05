"""A day already stamped must still run a step that has never run.

WHAT HAPPENED (gap-fixer 2026-08-28). `daily_cycle.main()` skips when the stamp's `last_run` is
today. The stamp recorded THAT the day ran and never WHAT ran, so the two facts could disagree --
and on this day they did. The Windows box ran the cycle at 00:01 on a six-step version of the
file, stamped 2026-08-28 done, and the fourteen-step chain then shipped to it. `check_desk_module
_drift.py` correctly reported "all 50 match HEAD on both boxes": the code was THERE. It simply
could not run, because a stamp written by the version it replaced said the day was finished.

WHAT THAT COST, MEASURED THE SAME HOUR: execution_quality.json 43.1h stale against a 36h limit
with the PROMOTION GATE as its consumer; decay_live.json 43.1h against 26h, so LAWS L1.59's fade
and retire ladder had no clock; forward_reconcile.json 39.1h against 26h. Three reds on the
freshness fence and `live_readiness` held at rung 0 -- from a skip that was right about the date
and wrong about the work. The desk's own lesson names this class: a heartbeat proves the loop is
alive, never that the pipe is.

These two tests are the pipe check. The first fails against the old unconditional skip; the
second pins the property that made the skip worth having, so the fix cannot be "run everything
every hour" -- a step that already ran today is still never re-run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHAIN = ROOT / "desks" / "mt5" / "research" / "daily_cycle.py"


@pytest.fixture
def cycle(tmp_path, monkeypatch):
    """Import the chain in isolation and point every write at tmp_path.

    Import-and-patch, never `cwd`: STAMP and LOG resolve from `__file__`, so a test that merely
    ran from a temporary directory would have written the LIVE stamp and started the REAL chain.
    sys.path is restored because the module inserts three desk directories into it at exec time.
    """
    saved = list(sys.path)
    spec = importlib.util.spec_from_file_location("_daily_cycle_under_test", CHAIN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path[:] = saved

    monkeypatch.setattr(mod, "STAMP", tmp_path / "daily_cycle_state.json")
    monkeypatch.setattr(mod, "LOG", tmp_path / "logs" / "daily_cycle.log")
    return mod


def _stamp(mod, steps: dict) -> None:
    mod.STAMP.write_text(json.dumps({
        "last_run": mod.datetime.now(mod.UTC).date().isoformat(),
        "steps": steps,
    }), encoding="utf-8")


def test_a_step_the_stamp_never_named_runs_on_a_day_already_stamped(cycle) -> None:
    """The exact failure: eight new steps shipped, the day was stamped, nothing ran."""
    ran: list[str] = []
    cycle.STEPS = (("old_step", lambda: ran.append("old_step")),
                   ("decay", lambda: ran.append("decay")))
    # The box's stamp: today, and it names only the step the previous version of the file knew.
    _stamp(cycle, {"old_step": {"ok": True, "seconds": 0.1}})

    assert cycle.main([]) == 0

    assert ran == ["decay"], "the step the stamp never named must run; the one it named must not"
    after = json.loads(cycle.STAMP.read_text(encoding="utf-8"))
    # Merge, never replace -- erasing the earlier outcome would make the next tick re-run it.
    assert set(after["steps"]) == {"old_step", "decay"}
    assert after["steps"]["old_step"]["ok"] is True
    assert after["steps"]["decay"]["ok"] is True


def test_a_fully_stamped_day_still_runs_nothing(cycle) -> None:
    """The property the skip exists for: no step is ever re-run inside the same day."""
    ran: list[str] = []
    cycle.STEPS = (("a", lambda: ran.append("a")), ("b", lambda: ran.append("b")))
    _stamp(cycle, {"a": {"ok": True, "seconds": 0.1}, "b": {"ok": False, "seconds": 0.2}})

    assert cycle.main([]) == 0

    assert ran == [], "a step that already ran today -- pass or FAIL -- must not run again"
