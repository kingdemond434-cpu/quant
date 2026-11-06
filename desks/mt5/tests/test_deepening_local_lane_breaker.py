"""The local lane stands down after LOCAL_OUTAGE_BREAK unavailable rows in a row (audit of
538cb964, SF10): a dead local server used to cost its full timeout on every row it reached."""
from __future__ import annotations

import sys
from pathlib import Path

_DESK = str(Path(__file__).resolve().parents[1])
if _DESK not in sys.path:
    sys.path.insert(0, _DESK)

from research import deepening_worker as dw  # noqa: E402


def _run(dispositions: list[str]) -> tuple[int, list[str]]:
    seen: list[str] = []
    it = iter(dispositions)
    done = dw.run_local_lane(
        [{"id": str(i)} for i in range(len(dispositions))],
        lambda task: ([], next(it)),
        lambda task, cands, disp, wall: seen.append(disp),
        lambda: "", lambda: False)
    return done, seen


def test_three_outages_in_a_row_end_the_lane() -> None:
    down = "BLOCKED_SEAT_UNAVAILABLE: connection refused"
    done, seen = _run([down] * 10)
    assert done == dw.LOCAL_OUTAGE_BREAK and len(seen) == dw.LOCAL_OUTAGE_BREAK


def test_a_decided_row_resets_the_count() -> None:
    down = "BLOCKED_SEAT_UNAVAILABLE: timeout"
    done, _ = _run([down, down, "REJECTED: no rule", down, down, "EXACT_RECIPE"])
    assert done == 6


def test_a_busy_box_yields_before_any_row() -> None:
    done = dw.run_local_lane([{"id": "a"}], lambda t: ([], "x"), lambda *a: None,
                             lambda: "judge running", lambda: False)
    assert done == 0
