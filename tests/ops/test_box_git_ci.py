"""Box CI never takes what trading needs, and nothing untested is ever promoted."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ops.box_git import box_ci as C  # noqa: E402
from ops.box_git.impacted import ALL  # noqa: E402

ORDER = ["h1", "h2", "h3", "h4"]


def anc(a: str, b: str) -> bool:
    return ORDER.index(a) <= ORDER.index(b)


def test_ci_stops_first_when_disk_runs_short() -> None:
    assert C.DISK_FLOOR_GB > 5.0, "above the desk's own 5 GB floor, so CI yields first"
    assert not C.disk_ok(10.0)[0]
    assert not C.disk_ok(None)[0]
    assert C.disk_ok(60.0)[0]


def test_only_idle_cores_minus_a_reserve() -> None:
    busy = [95.0] * 14 + [3.0] * 4
    assert C.idle_workers(busy) == 2
    assert C.idle_workers([95.0] * 18) == C.FLOOR_WORKERS == 1  # one idle-priority worker
    assert C.idle_workers([95.0] * 18, floor=0) == 0
    assert C.idle_workers([0.0] * 32) == C.MAX_WORKERS
    assert C.idle_workers(None) == 0


def test_merges_during_a_run_coalesce_into_one_next_run() -> None:
    assert C.plan_full_run({}, "h1").start == "h1"
    s = {"full_running": "h1"}
    p = C.plan_full_run(s, "h2")
    assert p.start is None and p.pending == "h2"
    s["full_pending"] = "h2"
    assert C.plan_full_run(s, "h3").pending == "h3"
    s = {"full_results": [{"head": "h3", "kind": C.FULL, "ok": True}]}
    assert C.plan_full_run(s, "h3").start is None


def test_only_a_fully_green_head_is_promotable_and_never_backwards() -> None:
    s: dict = {}
    C.record(s, head="h1", kind=C.FULL, ok=True, why="")
    C.record(s, head="h2", kind=C.IMPACTED, ok=True, why="")
    C.record(s, head="h3", kind=C.FULL, ok=False, why="1 failed")
    assert C.promotable(s, anc) == "h1"
    C.record(s, head="h4", kind=C.FULL, ok=True, why="")
    assert C.promotable(s, anc) == "h4"
    s["promoted"] = "h4"
    assert C.promotable(s, anc) is None


def test_pytest_runs_the_selection_or_everything(tmp_path: Path) -> None:
    j = tmp_path / "j.xml"
    assert C.pytest_argv("py", ["tests/a.py"], 1, j)[-1] == "tests/a.py"
    full = C.pytest_argv("py", ALL, 4, j)
    assert "-n" in full and not any(a.startswith("tests/") for a in full)


def test_ci_directories_inherit_the_parent_acl_never_mkdtemp(tmp_path) -> None:
    """Defect 9 (box 2026-11-20): mkdtemp is owner-only on Windows (Python 3.13+), so the CI
    worker could not read the worktrees. Shared directories come from shared_dir only."""
    a, b = C.shared_dir(tmp_path, "wt_"), C.shared_dir(tmp_path, "wt_")
    assert a != b and a.is_dir() and a.parent == tmp_path and a.name.startswith("wt_")
    root = Path(__file__).resolve().parents[2] / "ops" / "box_git"
    for f in ("box_loop.py", "pin_writer.py"):
        assert "mkdtemp(" not in (root / f).read_text(encoding="utf-8"), f
