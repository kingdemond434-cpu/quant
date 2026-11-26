"""The forge loop stall guard: a silent pass ends itself; a child in its timeout never does."""
from __future__ import annotations

from ops.box_git import box_loop as bl


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_silence_past_the_limit_is_a_stall_with_the_stage_named() -> None:
    c = Clock()
    g = bl.StallGuard(600, clock=c)
    g.beat("gate")
    c.t += 599
    assert g.stalled() is None
    c.t += 2
    assert g.stalled() == {"stage": "gate", "silent_s": 601, "stall_s": 600}


def test_a_child_inside_its_own_timeout_is_alive() -> None:
    c = Clock()
    g = bl.StallGuard(600, clock=c)
    g.child(3600)
    c.t += 3000
    assert g.stalled() is None          # a long suite run is not a stall
    c.t += 3600 + 60 - 3000 + 601       # past the child's deadline AND the silence limit
    assert g.stalled() is not None


def test_the_end_of_a_child_restarts_the_clock() -> None:
    c = Clock()
    g = bl.StallGuard(600, clock=c)
    g.child(100)
    c.t += 150
    g.child_done()
    c.t += 599
    assert g.stalled() is None


def test_run_marks_the_child_and_clears_it() -> None:
    c = Clock()
    seen: list[float] = []
    bl.GUARD = g = bl.StallGuard(600, clock=c)
    try:
        orig = g.child
        g.child = lambda t: (seen.append(t), orig(t))[1]  # type: ignore[method-assign]
        rc, _ = bl._run(["git", "--version"], timeout=42)
        assert rc == 0 and seen == [42] and g.until == 0.0
    finally:
        bl.GUARD = None


def test_watch_calls_on_stall_once() -> None:
    import threading
    c = Clock()
    hit = threading.Event()
    got: list[dict] = []
    g = bl.StallGuard(10, clock=c, on_stall=lambda why: (got.append(why), hit.set()))
    c.t += 11
    g.watch(every_s=0.01)
    assert hit.wait(5) and got[0]["stage"] == "start"
