"""The sweep writes every thread's stack on a C-level timer, so a wedged sweep says where."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import run_sharded_gauntlet as rsg  # noqa: E402


def test_stacks_are_dumped_on_the_timer_and_old_files_pruned(tmp_path: Path) -> None:
    for i in range(5):
        old = tmp_path / f"MT5-Gauntlet.stacks.{1000 + i}.log"
        old.write_text("x")
        os.utime(old, (1_000_000 + i, 1_000_000 + i))
    try:
        path = rsg._arm_stack_dumps(tmp_path, every_s=0.2)
        assert path is not None and path.name == f"MT5-Gauntlet.stacks.{os.getpid()}.log"
        deadline = time.monotonic() + 5.0
        while "test_sweep_stack_dumps" not in path.read_text("utf-8") \
                and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        rsg._disarm_stack_dumps()
    text = path.read_text("utf-8")
    assert text.startswith(f"# sweep pid {os.getpid()} armed")
    assert "test_sweep_stack_dumps" in text          # this very test's frame was dumped
    kept = sorted(p.name for p in tmp_path.glob("MT5-Gauntlet.stacks.*.log"))
    assert len(kept) == rsg.STACK_DUMP_KEEP
    assert "MT5-Gauntlet.stacks.1004.log" in kept and "MT5-Gauntlet.stacks.1003.log" in kept


def test_an_unwritable_log_dir_never_stops_the_sweep(tmp_path: Path) -> None:
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    assert rsg._arm_stack_dumps(blocker / "logs") is None
    rsg._disarm_stack_dumps()
